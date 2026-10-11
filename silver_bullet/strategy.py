"""ICT Silver Bullet rules as a bar-by-bar state machine.

The same Strategy object drives the backtester, the paper trader and the Schwab
runner, so what you backtest is exactly what you paper trade.

Rules (codified from the ICT 2023 mentorship Silver Bullet lesson):
  1. Only look for entries inside the three New York windows: 3-4am, 10-11am, 2-3pm.
  2. Draw on liquidity: the nearest unswept session high (for longs) or low (for
     shorts) among prior day, prior week, Asia, London, NY AM and NY lunch ranges.
  3. A market structure shift (MSS): a close through the most recent confirmed
     swing high (bullish) or swing low (bearish), in the direction of the draw.
  4. A fair value gap (FVG) formed inside the window by that displacement leg
     (three-candle gap: bar[j].low > bar[j-2].high for bullish).
  5. The framework: the draw must be at least `min_framework_pts` (10 handles on
     ES) from the entry. The trade itself only aims for `target_pts` (5 handles).
  6. Entry: limit order at the near edge of the FVG, valid until the window closes.
     Stop: just beyond the swing extreme that began the displacement leg.
  7. Held past the window if needed; flat by `flat_time`.

Nothing here looks ahead: every decision on bar i uses bars <= i, and orders it
emits can only fill from bar i+1 on.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Optional

from .config import WINDOWS, Instrument, Params

NY = "America/New_York"


@dataclass
class Bar:
    ts: datetime          # bar OPEN time, tz-aware America/New_York
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Setup:
    direction: int        # +1 long, -1 short
    window: str
    entry: float
    stop: float
    target: float
    draw: float
    draw_name: str
    created: datetime
    expires: datetime     # window end; unfilled orders are cancelled then

    def describe(self) -> str:
        side = "LONG" if self.direction > 0 else "SHORT"
        return (f"{side} {self.window} entry {self.entry:.2f} stop {self.stop:.2f} "
                f"target {self.target:.2f} draw {self.draw_name} {self.draw:.2f}")


@dataclass
class Level:
    name: str
    price: float
    side: str             # "high" (buy-side liquidity) or "low" (sell-side)
    swept: bool = False


@dataclass
class Action:
    kind: str             # "submit" | "cancel" | "flatten"
    setup: Optional[Setup] = None
    reason: str = ""


# Session ranges whose highs/lows become liquidity once the session closes (NY time).
SESSIONS = (
    ("Asia", time(20, 0), time(0, 0)),
    ("London", time(2, 0), time(5, 0)),
    ("NY AM", time(9, 30), time(12, 0)),
    ("NY Lunch", time(12, 0), time(13, 30)),
)


def trading_day(ts: datetime):
    """CME-style trading day: the session that opens at 18:00 belongs to the next date."""
    return (ts + timedelta(hours=6)).date()


def _in_session(t: time, start: time, end: time) -> bool:
    if start < end:
        return start <= t < end
    return t >= start or t < end  # wraps midnight


class Strategy:
    def __init__(self, instrument: Instrument, params: Params, bar_minutes: int = 1):
        self.inst = instrument
        self.p = params
        self.bar_delta = timedelta(minutes=bar_minutes)
        self.windows = [w for w in WINDOWS if w.name in params.windows]
        self.bars: deque[Bar] = deque(maxlen=2000)
        self.n = 0                       # absolute index of the latest bar
        # liquidity
        self.levels: list[Level] = []
        self.day = None
        self.day_hi = self.day_lo = None
        self.week = None
        self.week_hi = self.week_lo = None
        self.prev_week_levels: list[Level] = []
        self.sess_rng: dict[str, list] = {}
        self.sess_open: dict[str, bool] = {}
        # structure
        self.swing_hi: Optional[tuple[float, int]] = None   # (price, abs index)
        self.swing_lo: Optional[tuple[float, int]] = None
        self.swing_hi_broken = True
        self.swing_lo_broken = True
        self.intraday_swings: list[Level] = []
        # per-window state
        self.armed: Optional[dict] = None   # {"dir", "extreme", "extreme_idx", "window"}
        self.pending: Optional[Setup] = None
        self.trades_in_window: dict[tuple, int] = {}

    # ---------- helpers ----------
    def _bar(self, abs_idx: int) -> Bar:
        return self.bars[abs_idx - (self.n - len(self.bars) + 1)]

    def _oldest_idx(self) -> int:
        return self.n - len(self.bars) + 1

    def active_window(self, bar: Bar):
        t0 = bar.ts.timetz().replace(tzinfo=None)
        end = (bar.ts + self.bar_delta).timetz().replace(tzinfo=None)
        for w in self.windows:
            if w.start <= t0 and end <= w.end and t0 < w.end:
                return w
        return None

    def _window_end(self, bar: Bar, w) -> datetime:
        return bar.ts.replace(hour=w.end.hour, minute=w.end.minute, second=0, microsecond=0)

    def draw_levels(self):
        lv = [l for l in self.levels if not l.swept]
        if self.p.include_swing_levels:
            lv += [l for l in self.intraday_swings if not l.swept]
        return lv

    def nearest_draw(self, direction: int, price: float) -> Optional[Level]:
        if direction > 0:
            c = [l for l in self.draw_levels() if l.side == "high" and l.price > price]
            return min(c, key=lambda l: l.price) if c else None
        c = [l for l in self.draw_levels() if l.side == "low" and l.price < price]
        return max(c, key=lambda l: l.price) if c else None

    # ---------- liquidity bookkeeping ----------
    def _update_liquidity(self, bar: Bar):
        d = trading_day(bar.ts)
        if d != self.day:
            if self.day is not None and self.day_hi is not None:
                # new day: yesterday's extremes become liquidity; drop stale session levels
                self.levels = [l for l in self.levels if l.name.startswith("PW")]
                self.levels += [Level("PDH", self.day_hi, "high"), Level("PDL", self.day_lo, "low")]
                # carry over sessions from the day that just ended which closed late (none by default)
            self.day, self.day_hi, self.day_lo = d, bar.high, bar.low
            self.intraday_swings = []
            self.sess_rng, self.sess_open = {}, {}
            wk = d.isocalendar()[:2]
            if wk != self.week:
                if self.week is not None and self.week_hi is not None:
                    self.levels = [l for l in self.levels if not l.name.startswith("PW")]
                    self.levels += [Level("PWH", self.week_hi, "high"), Level("PWL", self.week_lo, "low")]
                self.week, self.week_hi, self.week_lo = wk, bar.high, bar.low
        # sweep check runs before this bar extends today's ranges
        for l in self.levels + self.intraday_swings:
            if not l.swept and ((l.side == "high" and bar.high > l.price) or
                                (l.side == "low" and bar.low < l.price)):
                l.swept = True
        self.day_hi, self.day_lo = max(self.day_hi, bar.high), min(self.day_lo, bar.low)
        self.week_hi, self.week_lo = max(self.week_hi, bar.high), min(self.week_lo, bar.low)
        t = bar.ts.timetz().replace(tzinfo=None)
        for name, s, e in SESSIONS:
            inside = _in_session(t, s, e)
            if inside:
                r = self.sess_rng.get(name)
                self.sess_rng[name] = [bar.high, bar.low] if r is None else [max(r[0], bar.high), min(r[1], bar.low)]
                self.sess_open[name] = True
            elif self.sess_open.get(name):
                hi, lo = self.sess_rng[name]
                self.levels += [Level(f"{name} high", hi, "high"), Level(f"{name} low", lo, "low")]
                self.sess_open[name] = False
                # re-check sweep for this bar against the just-closed session
                for l in self.levels[-2:]:
                    if (l.side == "high" and bar.high > l.price) or (l.side == "low" and bar.low < l.price):
                        l.swept = True

    # ---------- structure ----------
    def _update_swings(self):
        k = self.p.swing_len
        if len(self.bars) < 2 * k + 1:
            return
        c = self.n - k
        cb = self._bar(c)
        left = [self._bar(i) for i in range(c - k, c)]
        right = [self._bar(i) for i in range(c + 1, c + k + 1)]
        if all(cb.high > b.high for b in left) and all(cb.high >= b.high for b in right):
            self.swing_hi, self.swing_hi_broken = (cb.high, c), False
            self.intraday_swings.append(Level("swing high", cb.high, "high"))
        if all(cb.low < b.low for b in left) and all(cb.low <= b.low for b in right):
            self.swing_lo, self.swing_lo_broken = (cb.low, c), False
            self.intraday_swings.append(Level("swing low", cb.low, "low"))

    def _find_fvg(self, direction: int, start_idx: int, w, only_last: bool):
        """Most recent unfilled FVG in `direction` formed at/after start_idx+2 inside window w.
        Returns (top, bottom, formed_idx)."""
        lo = max(start_idx + 2, self._oldest_idx() + 2)
        rng = [self.n] if only_last else range(self.n, lo - 1, -1)
        for j in rng:
            if j < lo:
                continue
            b2, b0 = self._bar(j - 2), self._bar(j)
            if self.active_window(b0) is not w:
                continue
            if direction > 0 and b0.low > b2.high:
                top, bot = b0.low, b2.high
                if all(self._bar(m).low > top for m in range(j + 1, self.n + 1)):
                    return top, bot, j
            if direction < 0 and b0.high < b2.low:
                top, bot = b2.low, b0.high
                if all(self._bar(m).high < bot for m in range(j + 1, self.n + 1)):
                    return top, bot, j
        return None

    def _build_setup(self, direction, fvg, w, bar) -> Optional[Setup]:
        top, bot, _ = fvg
        tick = self.inst.tick_size
        buf = self.p.stop_buffer_ticks * tick
        ext = self.armed["extreme"]
        if direction > 0:
            entry, stop = top, ext - buf
        else:
            entry, stop = bot, ext + buf
        risk = abs(entry - stop)
        if risk > self.p.max_stop_pts or risk < self.p.min_stop_pts:
            return None
        draw = self.nearest_draw(direction, entry)
        if draw is None or abs(draw.price - entry) < self.p.min_framework_pts:
            return None
        if self.p.target_mode == "draw":
            target = draw.price
        else:
            target = entry + direction * self.p.target_pts
        return Setup(direction, w.name, entry, stop, round(target / tick) * tick, draw.price,
                     draw.name, bar.ts, self._window_end(bar, w))

    # ---------- main entry point ----------
    def on_bar(self, bar: Bar, position: int = 0, pending: bool = False) -> list[Action]:
        """Feed one CLOSED bar. `position`/`pending` describe the executor's state
        after it processed this bar. Returns actions to apply before the next bar."""
        self.bars.append(bar)
        self.n += 1
        self._update_liquidity(bar)
        self._update_swings()
        actions: list[Action] = []
        bar_end = bar.ts + self.bar_delta
        t_end = bar_end.timetz().replace(tzinfo=None)

        if not pending:
            self.pending = None
        # flat-time rule
        if position != 0 and t_end >= self.p.flat_time and bar.ts.timetz().replace(tzinfo=None) < time(18, 0):
            actions.append(Action("flatten", reason="flat time"))
            return actions
        # pending order maintenance
        if self.pending is not None:
            s = self.pending
            if bar_end >= s.expires:
                actions.append(Action("cancel", reason="window closed"))
                self.pending = None
            elif (s.direction > 0 and bar.high >= s.target) or (s.direction < 0 and bar.low <= s.target):
                actions.append(Action("cancel", reason="target reached before fill"))
                self.pending = None

        w = self.active_window(bar)
        # structure breaks (tracked always so swings outside the window can be used)
        mss = 0
        if self.swing_hi and not self.swing_hi_broken and bar.close > self.swing_hi[0]:
            self.swing_hi_broken, mss = True, 1
        if self.swing_lo and not self.swing_lo_broken and bar.close < self.swing_lo[0]:
            self.swing_lo_broken, mss = True, -1
        if w is None:
            self.armed = None
            return actions
        key = (self.day, w.name)
        if self.trades_in_window.get(key, 0) >= self.p.max_trades_per_window or position != 0:
            return actions
        if self.p.bias == "long" and mss < 0 or self.p.bias == "short" and mss > 0:
            mss = 0

        if mss:
            ref_idx = (self.swing_hi if mss > 0 else self.swing_lo)[1]
            ref_idx = max(ref_idx, self._oldest_idx())
            idxs = range(ref_idx, self.n + 1)
            if mss > 0:
                ext_idx = min(idxs, key=lambda i: self._bar(i).low)
                ext = self._bar(ext_idx).low
            else:
                ext_idx = max(idxs, key=lambda i: self._bar(i).high)
                ext = self._bar(ext_idx).high
            self.armed = {"dir": mss, "extreme": ext, "extreme_idx": ext_idx, "window": w}
            if self.pending is not None and self.pending.direction != mss:
                actions.append(Action("cancel", reason="opposite structure shift"))
                self.pending = None
        elif self.armed is not None:
            a = self.armed
            if a["window"] is not w or (a["dir"] > 0 and bar.close < a["extreme"]) or \
                    (a["dir"] < 0 and bar.close > a["extreme"]):
                self.armed = None

        if self.armed is not None and self.pending is None:
            a = self.armed
            fvg = self._find_fvg(a["dir"], a["extreme_idx"], w, only_last=not mss)
            if fvg:
                s = self._build_setup(a["dir"], fvg, w, bar)
                if s is not None:
                    self.pending = s
                    self.armed = None
                    actions.append(Action("submit", setup=s))
        return actions

    def notify_filled(self, setup: Setup):
        key = (trading_day(setup.created), setup.window)
        self.trades_in_window[key] = self.trades_in_window.get(key, 0) + 1
        self.pending = None
