"""Narrow morning engine (PR #82 option D; Mase 2026-11-16). Switch: Params.narrow = "am" (default "off").

With the switch on, run_day runs ONLY this model and none of the rulebook setups. It is built from what ICT does in
his live NQ videos, not from the rulebook count:

  1. Window: nar_win (09:30-11:30). No lunch, no PM, no order-block-before-the-break entry.
  2. Sweep: price trades through a resting pool by one tick: prior day's RTH high / low ("pd"), overnight 00:00-09:30
     high / low ("on"), London 02:00-05:00 high / low ("lon"), 08:30-09:30 high / low ("pre"), or a short-term swing
     since 08:30 ("sw"). A pool counts only while it is still untouched since it formed.
  3. Shift: after the sweep extreme, a bar CLOSES beyond the last swing (nar_shift_n candles each side) that formed
     before that extreme, within nar_shift_within bars of the sweep.
  4. Gap: a fair value gap printed in the leg from the sweep extreme through the shift (the last one, >= nar_gap_min).
  5. Entry (nar_entry):
       "react"  wait for price to trade back into the gap and then for a bar to close back out of it in the trade's
                direction; buy / sell the NEXT bar's open at market. A close through the far side of the gap kills it.
       "limit"  the old way: a resting limit at the gap's near edge (or its CE with Params.entry == "ce").
  6. Stop (nar_stop): "ext" one tick beyond the sweep extreme; "gap" one tick beyond the gap's first candle.
  7. Target (nar_target): a number = that many R; "pool" = the nearest untouched opposing pool at least nar_min_rr away
     (no pool: skip the trade).
  8. Flat at nar_flat (12:00). One position at a time, nar_max_trades a day.
  9. Direction filter (nar_bias): "none" (the sweep decides), "midnight" / "open830" (longs only below that opening
     price, shorts only above), "prevday" (with the prior RTH day's open-to-close direction), "anti_prevday",
     "read" (PR #101: only with the coded ICT direction read, ict_read.py, taken from the bars before the entry bar;
     no read = no trade).
 10. nar_on_block (0 = off; 0.67): no long while price sits above that share of the range since 18:00, no short
     while it sits below 1 - that share (a trade toward the overnight extreme price is already at).
 11. nar_entry "open" (PR #103, option C): no sweep / shift / gap. Buy or sell the open of the first bar of nar_win
     in the direction of the read, stop nar_open_stop_pct % of price away, target and flat time as above.
 12. nar_day_skip: days ICT says he passes on. Any of "news" (an event in nar_skip_news), "holiday_eve", "prev_big"
     (yesterday's range over nar_prev_big x the 20-day average), "small_gap" (the 09:30 open within nar_small_gap x
     the average range of yesterday's settlement), "friday". Empty = off.

"read", nar_on_block, "open", "prev_big" and "small_gap" need the bars before today (run_day `past`, see
ict_read.past_bars; backtest.day_kwargs passes them). Without them the day is skipped ("no_past").

Every decision uses closed bars only: a swing is known nar_shift_n bars after it, a gap after its third candle, the
reaction after its bar closes, and the market entry is the next bar's open. Prices are mirrored for shorts, so one set
of long rules serves both sides. Points are ES points x Params.es_pt, as in the main engine.
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from . import ict_read as _RD

FUNNEL = Counter()        # how far the setups got (per process; the runner prints it): sweep / shift / gap / order / trade

MODES = ("off", "am")
ENTRIES = ("react", "limit", "open")
STOPS = ("ext", "gap")
BIASES = ("none", "midnight", "open830", "prevday", "anti_prevday", "read")
SKIPS = ("news", "holiday_eve", "prev_big", "small_gap", "friday")
POOLS = ("pd", "on", "lon", "pre", "sw")


def check_params(p) -> None:
    if p.narrow not in MODES:
        raise ValueError(f"narrow {p.narrow!r}")
    if p.nar_entry not in ENTRIES:
        raise ValueError(f"nar_entry {p.nar_entry!r}")
    if p.nar_stop not in STOPS:
        raise ValueError(f"nar_stop {p.nar_stop!r}")
    if p.nar_bias not in BIASES:
        raise ValueError(f"nar_bias {p.nar_bias!r}")
    if p.nar_target != "pool" and not (isinstance(p.nar_target, (int, float)) and p.nar_target > 0):
        raise ValueError(f"nar_target {p.nar_target!r}")
    if not set(p.nar_pools) <= set(POOLS) or not p.nar_pools:
        raise ValueError(f"nar_pools {p.nar_pools!r}")
    if int(p.nar_shift_n) < 1 or int(p.nar_max_trades) < 1:
        raise ValueError("nar_shift_n / nar_max_trades >= 1")
    if not set(p.nar_day_skip) <= set(SKIPS):
        raise ValueError(f"nar_day_skip {p.nar_day_skip!r}")
    if p.nar_on_block and not 0.5 <= float(p.nar_on_block) < 1.0:
        raise ValueError(f"nar_on_block {p.nar_on_block!r}: 0 (off) or 0.5 to 1")
    if not float(p.nar_open_stop_pct) > 0:
        raise ValueError(f"nar_open_stop_pct {p.nar_open_stop_pct!r}")


def needs_past(p) -> bool:
    """True when the switches read bars from before today (the caller passes run_day `past`)."""
    return p.narrow != "off" and (p.nar_bias == "read" or p.nar_entry == "open" or bool(p.nar_on_block)
                                  or bool({"prev_big", "small_gap"} & set(p.nar_day_skip)))


class _S:
    """One side's view of the day in 'long' terms (shorts: every price negated, high and low swapped)."""

    def __init__(self, o, h, l, c, sign):
        self.sign = sign
        if sign > 0:
            self.o, self.h, self.l, self.c = o, h, l, c
        else:
            self.o, self.h, self.l, self.c = -o, -l, -h, -c
        self.sw = None            # active sweep: dict(name, level, i0, ext, ext_i)
        self.ref = None           # swing high to close above (price) once the sweep is on
        self.shift_i = None
        self.gap = None           # (bottom, top, c1_low, known_i)
        self.tagged = False
        self.limit = None         # resting limit: (price, stop, meta)
        self.spent = set()        # pool names already swept today on this side

    def real(self, x):
        return x * self.sign

    def reset(self):
        self.sw = self.ref = self.shift_i = self.gap = self.limit = None
        self.tagged = False


def _pivot_high_before(s: _S, upto: int, known_by: int, n: int, lo: int):
    """The last swing high at j < upto (n lower highs each side), confirmed by bar known_by, not older than lo."""
    h = s.h
    for j in range(min(upto - 1, known_by - n), max(lo, n) - 1, -1):
        v = h[j]
        if v > h[j - n:j].max() and v > h[j + 1:j + n + 1].max():
            return float(v)
    return None


def _levels(s: _S, t, hist, p, tick):
    """Sell-side pools in this side's frame: name -> (level, index from which it must have stayed untouched)."""
    out = {}
    w0 = int(np.searchsorted(t, p.nar_win[0]))
    if "pd" in p.nar_pools and hist:
        prev = hist[-1]
        out["pd"] = (float(prev.low.min()) if s.sign > 0 else -float(prev.high.max()), 0)
    if "on" in p.nar_pools and w0 > 0:
        out["on"] = (float(s.l[:w0].min()), w0)
    for name, a, b in (("lon", 120, 300), ("pre", 510, 570)):
        if name in p.nar_pools:
            i0, i1 = int(np.searchsorted(t, a)), int(np.searchsorted(t, b))
            if i1 > i0:
                out[name] = (float(s.l[i0:i1].min()), i1)
    return out


def _intact(s: _S, level: float, frm: int, i: int, tick: float) -> bool:
    return frm >= i or float(s.l[frm:i].min()) > level - tick + 1e-9


def _swing_pools(s: _S, t, i: int, p, tick):
    """Short-term swing lows since 08:30 (nar_sw_n candles each side), known by bar i and untouched since."""
    n = int(p.nar_sw_n)
    a = max(int(np.searchsorted(t, 510)), n)
    out = []
    l = s.l
    for j in range(a, i - n):
        v = l[j]
        if v < l[j - n:j].min() and v < l[j + 1:j + n + 1].min() and float(l[j + 1:i].min()) > v - tick + 1e-9:
            out.append((f"sw{int(t[j]) // 60:02d}{int(t[j]) % 60:02d}", float(v)))
    return out


def _bias_ok(s: _S, kind: str, entry: float, t, hist) -> bool:
    if kind in ("none", "read"):                  # "read" is checked in run_day (it needs the bars before today)
        return True
    if kind in ("midnight", "open830"):
        k = 0 if kind == "midnight" else int(np.searchsorted(t, 510))
        if k >= len(s.o):
            return False
        return entry < s.o[k]                     # long below the opening price (mirrored for shorts)
    if not hist:
        return False
    up = float(hist[-1].close.iloc[-1]) - float(hist[-1].open.iloc[0])
    d = (1 if up > 0 else -1 if up < 0 else 0) * s.sign
    return d > 0 if kind == "prevday" else d < 0


def _target(s: _S, t, hist, p, i: int, entry: float, risk: float, tick: float):
    if p.nar_target != "pool":
        return entry + float(p.nar_target) * risk, f"{float(p.nar_target):g}R"
    cands = []
    if hist:
        prev = hist[-1]
        cands.append(("pd", float(prev.high.max()) if s.sign > 0 else -float(prev.low.min()), 0))
    w0 = int(np.searchsorted(t, p.nar_win[0]))
    if w0 > 0:
        cands.append(("on", float(s.h[:w0].max()), w0))
    for name, a, b in (("lon", 120, 300), ("pre", 510, 570)):
        i0, i1 = int(np.searchsorted(t, a)), int(np.searchsorted(t, b))
        if i1 > i0:
            cands.append((name, float(s.h[i0:i1].max()), i1))
    if i > w0:
        cands.append(("hod", float(s.h[w0:i].max()), i))
    ok = [(lv, nm) for nm, lv, frm in cands
          if lv >= entry + p.nar_min_rr * risk and (frm >= i or float(s.h[frm:i].max()) < lv + tick - 1e-9)]
    if not ok:
        return None, ""
    lv, nm = min(ok)
    return lv - tick, nm                           # one tick in front of the pool


def run_day(df, hist, symbol, p, tf, equity=None, skips=None, live=False, past=None):
    """Trades of one day for the narrow morning engine. df: the day's bars from midnight; hist: prior RTH frames;
    past: the bars before midnight (ict_read.past_bars), needed only by the switches in needs_past()."""
    from . import strategy as ST
    day = df.index[0].date()
    t = (df.index.hour * 60 + df.index.minute).to_numpy()
    o, h, l, c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    n = len(df)
    w0, w1 = int(np.searchsorted(t, p.nar_win[0])), int(np.searchsorted(t, p.nar_win[1]))
    flat_i = int(np.searchsorted(t, p.nar_flat))          # first bar at / after the flat time: exit at its open
    if w1 <= w0 or w0 >= n:
        return []
    tick = 0.25 * p.es_pt
    gap_min, rmin, rmax = p.nar_gap_min * p.es_pt, p.nar_min_risk_pts * p.es_pt, p.nar_max_risk_pts * p.es_pt
    sn = int(p.nar_shift_n)
    eq = equity if equity is not None else p.account_equity
    sides = [_S(o, h, l, c, +1), _S(o, h, l, c, -1)]
    pools = {s.sign: _levels(s, t, hist, p, tick) for s in sides}
    try:
        news = ST.news(day)
    except Exception:
        news = "none"
    trades, pos = [], None
    pending = None                                        # market order for the next bar's open: (side, stop_px, meta)

    def skip(why):
        if skips is not None:
            skips.append((day, symbol, "narrow", why))

    # --- the coded direction read (ict_read.py): bars before today + today's bars, read as of bar i (bars < i only)
    need = needs_past(p)
    arr, cache = [], {}

    def rd(i):
        if i not in cache:
            if not arr:
                cols = [past[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close")]
                arr.append([np.r_[_RD.minutes(past.index), _RD.minutes(df.index)]]
                           + [np.r_[a, b] for a, b in zip(cols, (o, h, l, c))])
            cache[i] = _RD.read(*arr[0], len(past) + i)
        return cache[i]

    if need and (past is None or not len(past)):
        skip("no_past")
        return []
    if p.nar_day_skip:
        from . import calendar as _CAL
        ds_ = set(p.nar_day_skip)
        why = None
        if "news" in ds_ and _CAL.events(day) & set(p.nar_skip_news):
            why = "news"
        elif "holiday_eve" in ds_ and _CAL.is_holiday_eve(day):
            why = "holiday_eve"
        elif "friday" in ds_ and day.weekday() == 4:
            why = "friday"
        elif ds_ & {"prev_big", "small_gap"}:
            i930 = int(np.searchsorted(t, 570))
            r = rd(i930) if i930 < n else None       # as of the 09:30 open: bars before it, and that bar's open
            if r is None:
                why = "no_history"
            elif "prev_big" in ds_ and r["prev_rng"] > p.nar_prev_big:
                why = "prev_big"
            elif "small_gap" in ds_ and abs(o[i930] - r["settle"]) < p.nar_small_gap * r["adr"]:
                why = "small_gap"
        if why:
            skip("day_" + why)
            return []

    def open_trade(s, i, entry, stop, meta):
        risk = entry - stop
        if risk < rmin or risk > rmax:
            skip("risk_small" if risk < rmin else "risk_big")
            return None
        if not _bias_ok(s, p.nar_bias, entry, t, hist):
            skip("bias")
            return None
        if p.nar_bias == "read" or p.nar_on_block:
            r = rd(i)
            if r is None:
                skip("no_history")
                return None
            if p.nar_bias == "read" and r["side"] != s.sign:
                skip("bias")
                return None
            x = float(p.nar_on_block)
            if x and (r["on_pos"] > x if s.sign > 0 else r["on_pos"] < 1 - x):
                skip("on_ext")
                return None
        tgt, tname = _target(s, t, hist, p, i, entry, risk, tick)
        if tgt is None:
            skip("no_target")
            return None
        units = ST._first_units(p, eq, risk, abs(entry))
        if units <= 0:
            skip("size")
            return None
        tr = ST.Trade(date=day, symbol=symbol, session="AM", setup="nar_am", side="long" if s.sign > 0 else "short",
                      swept=meta["swept"], unicorn=False, smt=None, armed=df.index[meta["shift_i"]],
                      entry_time=df.index[i], entry=s.real(entry), stop=s.real(stop), t1=s.real(tgt), t2=None,
                      shares=units, news=news, weekday=day.weekday(), entry_kind=p.nar_entry,
                      ext_px=s.real(meta["ext"]), lv_tags=f"tgt_{tname}")
        return dict(s=s, tr=tr, entry=entry, stop=stop, tgt=tgt, risk=risk, be=False)

    def close(i, px, why):
        nonlocal pos
        s, tr = pos["s"], pos["tr"]
        tr.exits.append((df.index[i], s.real(px), tr.shares, why))
        trades.append(tr)
        pos = None
        for x in sides:
            x.reset()

    for i in range(w0, n):
        # --- orders decided on the previous bar's close: a market order fills at this bar's open, a resting limit
        #     fills when this bar prints through it
        fill_bar = False
        if p.nar_entry == "open" and i == w0 and i < flat_i:       # option C: the read's side at the window's first open
            r = rd(i)
            if r is None or r["side"] == 0:
                skip("no_history" if r is None else "no_read")
            else:
                s = sides[0] if r["side"] > 0 else sides[1]
                e_ = float(s.o[i])
                pos = open_trade(s, i, e_, e_ - p.nar_open_stop_pct / 100.0 * abs(e_),
                                 dict(swept="read", shift_i=i, ext=e_))
        if pos is None and pending is not None:
            s, stop, meta = pending
            if i < flat_i and s.o[i] > stop:
                pos = open_trade(s, i, float(s.o[i]), stop, meta)
            s.reset()
        pending = None
        if pos is None and i < w1 and i < flat_i and len(trades) < p.nar_max_trades:
            for s in sides:
                if s.limit is None:
                    continue
                px, stop, meta = s.limit
                if ST._prints_through(float(s.l[i]), px, p):
                    fill = min(px, float(s.o[i]))
                    if fill > stop:
                        pos = open_trade(s, i, fill, stop, meta)
                        fill_bar = pos is not None
                    s.reset()
                    if pos is not None:
                        break
        # --- manage the open position on this bar (the entry bar included)
        if pos is not None:
            s = pos["s"]
            if i >= flat_i:
                close(i, float(s.o[i]), "time")
            else:
                hit_s = s.l[i] <= pos["stop"]
                # on a limit's fill bar the high may have printed before the fill: the target counts only on the close
                hit_t = (s.c[i] >= pos["tgt"]) if fill_bar else (s.h[i] >= pos["tgt"])
                if hit_s and (not hit_t or p.ambiguous == "stop"):
                    close(i, min(pos["stop"], float(s.o[i])), "be" if pos["be"] else "stop")
                elif hit_t:
                    close(i, max(pos["tgt"], float(s.o[i])) if not fill_bar else pos["tgt"], "target")
                elif p.nar_be_at and not pos["be"] and s.h[i] >= pos["entry"] + p.nar_be_at * pos["risk"]:
                    pos["stop"], pos["be"] = pos["entry"], True
            if pos is not None and i == n - 1:
                if live:
                    trades.append(pos["tr"])
                    pos = None
                else:
                    close(i, float(pos["s"].c[i]), "eod")
        if pos is not None:
            continue
        if p.nar_entry == "open":
            break
        if i >= w1 or len(trades) >= p.nar_max_trades or i + 1 >= min(n, flat_i):
            break
        # --- look for the setup on each side (bar i is closed)
        for s in sides:
            lv = dict(pools[s.sign])
            if "sw" in p.nar_pools:
                for nm, v in _swing_pools(s, t, i, p, tick):
                    lv[nm] = (v, i)
            # 2. sweep (a pool taken later re-anchors the sweep)
            for nm, (level, frm) in lv.items():
                if nm in s.spent:
                    continue
                if s.l[i] <= level - tick + 1e-9:
                    was_intact = _intact(s, level, frm, i, tick)
                    s.spent.add(nm)
                    if was_intact:
                        s.reset()
                        s.sw = dict(name=nm, level=level, i0=i, ext=float(s.l[i]), ext_i=i)
                        FUNNEL["sweep"] += 1
            if s.sw is None:
                continue
            sw = s.sw
            if s.shift_i is None:
                if s.l[i] < sw["ext"]:
                    sw["ext"], sw["ext_i"] = float(s.l[i]), i
                if i - sw["i0"] > p.nar_shift_within:
                    s.reset()
                    continue
                # 3. shift: a close above the last swing high that formed before the sweep extreme
                if i > sw["ext_i"]:
                    ref = _pivot_high_before(s, sw["ext_i"], i, sn, max(0, sw["ext_i"] - p.nar_swing_lookback))
                    if ref is not None and s.c[i] > ref:
                        s.shift_i = i
                        FUNNEL["shift"] += 1
                if s.shift_i is None:
                    continue
            elif s.l[i] < sw["ext"]:                   # the sweep extreme failed after the shift: the setup is void
                s.reset()
                continue
            # 4. the last gap of the leg (third candle between the extreme and shift + fvg_wait)
            if i <= s.shift_i + p.fvg_wait:
                for k in range(i, max(sw["ext_i"] + 1, 2) - 1, -1):
                    if s.l[k] - s.h[k - 2] >= gap_min - 1e-9:
                        if s.gap is None or k > s.gap[3]:
                            FUNNEL["gap"] += s.gap is None
                            s.gap, s.tagged, s.limit = (float(s.h[k - 2]), float(s.l[k]), float(s.l[k - 2]), k), False, None
                        break
            if s.gap is None:
                if i >= s.shift_i + p.fvg_wait:
                    s.reset()
                continue
            bottom, top, c1_low, known = s.gap
            if i - s.shift_i > p.nar_entry_within or s.c[i] < bottom:      # too late, or a close through the gap
                s.reset()
                continue
            stop = (sw["ext"] if p.nar_stop == "ext" else c1_low) - tick
            meta = dict(swept=sw["name"], shift_i=s.shift_i, ext=sw["ext"])
            if p.nar_entry == "limit":
                s.limit = ((top + bottom) / 2 if p.entry == "ce" else top, stop, meta)      # rests from the next bar
            elif i > known:                            # the gap's own third candle is not a return to it
                # 5. reaction: traded into the gap, then a bar closes back above it, up on the bar
                if s.l[i] <= top:
                    s.tagged = True
                if s.tagged and s.c[i] > top and s.c[i] > s.o[i] and pending is None:
                    pending = (s, stop, meta)
                    FUNNEL["order"] += 1
    return trades
