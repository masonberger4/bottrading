"""Schwab Trader API adapter (the API behind thinkorswim).

Schwab's API places equity and option orders only; futures (/ES, /MES) cannot be
sent through it and it serves no futures price history. So the automated path
trades SPY/QQQ as the index proxy, while /MES is tested visually in thinkorswim
paperMoney with the thinkScript strategy.

Two modes:
  * dry_run=True (default): simulates fills locally on live Schwab bars via
    PaperBroker and logs the exact order JSON it WOULD send. This is the paper
    trading mode, since Schwab's API cannot reach a paperMoney account.
  * dry_run=False: sends a real bracket order (limit entry that triggers an OCO
    target + stop). Requires the environment variable SB_ALLOW_LIVE=1 as a second
    lock. Not used or tested in this project yet.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from .config import Instrument, Params
from .execution import PaperBroker
from .strategy import Bar, Setup

log = logging.getLogger("silver_bullet")


def make_client(api_key: str, app_secret: str, callback_url: str = "https://127.0.0.1:8182",
                token_path: str = "schwab_token.json"):
    """OAuth via schwab-py. The first run opens a browser to log in; later runs reuse the token."""
    from schwab.auth import easy_client
    return easy_client(api_key, app_secret, callback_url, token_path)


def bracket_order(symbol: str, qty: int, s: Setup):
    """Limit entry at the FVG edge, then OCO: limit target / stop at the swing."""
    from schwab.orders.common import (Duration, EquityInstruction, OrderStrategyType, OrderType,
                                      Session, first_triggers_second, one_cancels_other)
    from schwab.orders.equities import (equity_buy_limit, equity_buy_to_cover_limit,
                                        equity_sell_limit, equity_sell_short_limit)
    from schwab.orders.generic import OrderBuilder

    px = lambda v: f"{v:.2f}"
    if s.direction > 0:
        entry = equity_buy_limit(symbol, qty, px(s.entry))
        target = equity_sell_limit(symbol, qty, px(s.target))
        stop_instr = EquityInstruction.SELL
    else:
        entry = equity_sell_short_limit(symbol, qty, px(s.entry))
        target = equity_buy_to_cover_limit(symbol, qty, px(s.target))
        stop_instr = EquityInstruction.BUY_TO_COVER
    stop = (OrderBuilder()
            .set_order_type(OrderType.STOP)
            .set_session(Session.NORMAL)
            .set_duration(Duration.DAY)
            .set_stop_price(px(s.stop))
            .set_order_strategy_type(OrderStrategyType.SINGLE)
            .add_equity_leg(stop_instr, symbol, qty))
    return first_triggers_second(entry, one_cancels_other(target, stop))


class SchwabBroker:
    """Same interface as PaperBroker: submit / cancel / flatten / on_bar / position / pending / trades."""

    def __init__(self, client, inst: Instrument, params: Params, qty: Optional[int] = None,
                 dry_run: bool = True, account_hash: Optional[str] = None):
        self.client, self.inst, self.p = client, inst, params
        self.qty = qty or inst.default_qty
        self.dry_run = dry_run
        self.sim = PaperBroker(inst, params, self.qty)   # mirrors state in both modes
        self.order_id: Optional[str] = None
        if not dry_run:
            if os.environ.get("SB_ALLOW_LIVE") != "1":
                raise RuntimeError("Live orders are locked. Set SB_ALLOW_LIVE=1 to unlock.")
            if account_hash is None:
                r = client.get_account_numbers()
                r.raise_for_status()
                account_hash = r.json()[0]["hashValue"]
        self.account_hash = account_hash

    # state is mirrored from the simulator; in live mode it is reconciled in on_bar
    @property
    def position(self):
        return self.sim.position

    @property
    def pending(self):
        return self.sim.pending

    @property
    def trades(self):
        return self.sim.trades

    def submit(self, s: Setup, now: datetime):
        spec = bracket_order(self.inst.symbol, self.qty, s).build()
        if self.dry_run:
            log.info("%s  [dry-run] would place: %s", now, json.dumps(spec))
        else:
            from schwab.utils import Utils
            r = self.client.place_order(self.account_hash, spec)
            r.raise_for_status()
            self.order_id = Utils(self.client, self.account_hash).extract_order_id(r)
            log.info("%s  placed Schwab order %s", now, self.order_id)
        self.sim.submit(s, now)

    def cancel(self, now: datetime, reason: str = ""):
        if not self.dry_run and self.order_id and self.sim.position == 0:
            self.client.cancel_order(self.order_id, self.account_hash)
            self.order_id = None
        self.sim.cancel(now, reason)

    def flatten(self, now: datetime, reason: str = ""):
        if not self.dry_run and self.sim.position:
            from schwab.orders.equities import equity_buy_to_cover_market, equity_sell_market
            if self.order_id:
                self.client.cancel_order(self.order_id, self.account_hash)  # kills the OCO legs
            o = (equity_sell_market if self.sim.position > 0 else equity_buy_to_cover_market)(
                self.inst.symbol, self.qty)
            self.client.place_order(self.account_hash, o.build()).raise_for_status()
            self.order_id = None
        self.sim.flatten(now, reason)

    def on_bar(self, bar: Bar):
        ev = self.sim.on_bar(bar)
        if not self.dry_run and self.order_id:
            # Reconcile with the broker: log what Schwab reports so drift is visible.
            r = self.client.get_order(self.order_id, self.account_hash)
            if r.status_code == 200:
                o = r.json()
                kids = [c.get("status") for c in o.get("childOrderStrategies", [])
                        for c in c.get("childOrderStrategies", [c])]
                log.info("%s  Schwab order %s status %s children %s", bar.ts, self.order_id,
                         o.get("status"), kids)
                if o.get("status") in ("CANCELED", "REJECTED", "EXPIRED") and self.sim.pending:
                    self.sim.cancel(bar.ts, f"broker {o.get('status')}")
        return ev
