"""Order execution: a local paper-trading simulator, plus the shared run loop.

PaperBroker fills limit entries, stops and targets against each new bar with
conservative rules:
  * an order placed after bar i can only fill from bar i+1;
  * a limit entry fills at the limit, or at the open if price gaps through it;
  * on the entry bar only the stop is checked (we can't know the intrabar order);
  * if a bar touches both stop and target, the stop wins;
  * stops and flattening pay `slippage_ticks`; commissions are charged per side.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable, Optional

from .config import Instrument, Params
from .strategy import Action, Bar, Setup, Strategy

log = logging.getLogger("silver_bullet")


@dataclass
class Trade:
    window: str
    direction: int
    entry_time: datetime
    entry: float
    exit_time: datetime
    exit: float
    reason: str
    stop: float
    target: float
    draw_name: str
    points: float
    pnl: float           # dollars, after commissions

    def as_dict(self):
        d = asdict(self)
        d["side"] = "long" if self.direction > 0 else "short"
        return d


class PaperBroker:
    """Simulated broker. Also used by the live paper runner on real-time bars."""

    def __init__(self, inst: Instrument, params: Params, qty: Optional[int] = None):
        self.inst, self.p = inst, params
        self.qty = qty or inst.default_qty
        self.pending: Optional[Setup] = None
        self.pending_from: Optional[datetime] = None
        self.position = 0
        self.setup: Optional[Setup] = None
        self.entry_px = 0.0
        self.entry_time = None
        self.trades: list[Trade] = []
        self._flatten_next = False

    # --- order API (what a real broker adapter also implements) ---
    def submit(self, s: Setup, now: datetime):
        self.pending, self.pending_from = s, now
        log.info("%s  ORDER  %s", now, s.describe())

    def cancel(self, now: datetime, reason: str = ""):
        if self.pending:
            log.info("%s  CANCEL %s (%s)", now, self.pending.window, reason)
        self.pending = None

    def flatten(self, now: datetime, reason: str = ""):
        self._flatten_next = True
        self._flatten_reason = reason

    # --- simulation ---
    def _close(self, bar: Bar, px: float, reason: str):
        s = self.setup
        pts = (px - self.entry_px) * self.position
        pnl = pts * self.inst.point_value * self.qty - 2 * self.inst.commission_per_side * (
            self.qty if self.inst.is_future else 1)
        t = Trade(s.window, self.position, self.entry_time, self.entry_px, bar.ts, px, reason,
                  s.stop, s.target, s.draw_name, round(pts, 4), round(pnl, 2))
        self.trades.append(t)
        log.info("%s  EXIT   %s %s @ %.2f  %+.2f pts  $%+.2f", bar.ts, s.window, reason, px, pts, pnl)
        self.position, self.setup = 0, None

    def on_bar(self, bar: Bar) -> list[str]:
        """Process fills for this bar. Returns events: 'filled', 'exited'."""
        ev = []
        tick = self.inst.tick_size
        slip = self.p.slippage_ticks * tick
        if self._flatten_next and self.position:
            px = bar.open - slip * self.position
            self._close(bar, px, self._flatten_reason or "flatten")
            ev.append("exited")
        self._flatten_next = False

        fill_bar = False
        s = self.pending
        if s and self.position == 0:
            if s.direction > 0 and bar.low <= s.entry:
                self.entry_px = min(s.entry, bar.open)
            elif s.direction < 0 and bar.high >= s.entry:
                self.entry_px = max(s.entry, bar.open)
            else:
                s = None
            if s:
                self.position, self.setup, self.entry_time = s.direction, s, bar.ts
                self.pending = None
                fill_bar = True
                ev.append("filled")
                log.info("%s  FILL   %s %s @ %.2f", bar.ts, s.window,
                         "long" if s.direction > 0 else "short", self.entry_px)

        if self.position:
            s, d = self.setup, self.position
            through = self.p.target_through_ticks * tick
            stop_hit = bar.low <= s.stop if d > 0 else bar.high >= s.stop
            tgt_hit = (bar.high >= s.target + through) if d > 0 else (bar.low <= s.target - through)
            if stop_hit:
                px = min(s.stop, bar.open) if d > 0 else max(s.stop, bar.open)
                self._close(bar, px - slip * d, "stop")
                ev.append("exited")
            elif tgt_hit and not fill_bar:
                px = max(s.target, bar.open) if d > 0 else min(s.target, bar.open)
                self._close(bar, px, "target")
                ev.append("exited")
        return ev


def apply_actions(broker, strat: Strategy, actions: Iterable[Action], now: datetime):
    for a in actions:
        if a.kind == "submit":
            broker.submit(a.setup, now)
        elif a.kind == "cancel":
            broker.cancel(now, a.reason)
        elif a.kind == "flatten":
            broker.flatten(now, a.reason)


def step(strat: Strategy, broker, bar: Bar):
    """One bar of the shared loop: fills first, then the strategy decides."""
    pending_setup = broker.pending
    ev = broker.on_bar(bar)
    if "filled" in ev and pending_setup is not None:
        strat.notify_filled(pending_setup)
    acts = strat.on_bar(bar, position=broker.position, pending=broker.pending is not None)
    apply_actions(broker, strat, acts, bar.ts)
    return ev, acts
