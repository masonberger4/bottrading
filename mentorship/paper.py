"""Paper mode: run the model on live Schwab bars as they close and log what it would do.
It never sends an order; there is no order code in this package."""
from __future__ import annotations

import csv
import json
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import backtest as B
from . import dwc3 as _DWC3
from .strategy import Params, run_day


SCHWAB_1M_DAYS = 48        # Schwab keeps roughly 48 calendar days of 1-minute bars


class StopAckWatch:
    """new-no-working-stop-close-exit (093 ~00:14:12; Params.stop_ack_sec, management_exits #3/3). The decision logic of a position whose protective stop was not confirmed at the broker (paper / live
    layer only - the backtest is unaffected, and this package places no order: the caller feeds the facts and acts on the answers). `tick(now, acked)` marks the position `unprotected` once
    `stop_ack_sec` seconds passed since the entry fill without an acknowledgement; then `ladder()` is ONE 100 % rung at rung 1 (the nearby liquidity objective where the first partial would have gone,
    the far target is not held for) and `adverse_close(close)` is True when a bar CLOSES against the entry by more than one tick (the caller exits at market). With stop_ack_sec 0 it is inert."""

    def __init__(self, p: Params, side: str, entry: float, levels, fracs, filled_at):
        self.p, self.side, self.entry = p, side, float(entry)
        self.levels, self.fracs = list(levels), list(fracs)
        self.filled_at = pd.Timestamp(filled_at)
        self.unprotected = False

    def tick(self, now, acked: bool) -> bool:
        if self.p.stop_ack_sec > 0 and not acked and not self.unprotected and (pd.Timestamp(now) - self.filled_at).total_seconds() >= self.p.stop_ack_sec:
            self.unprotected = True
        return self.unprotected

    def ladder(self):
        """(levels, fracs) to work: unchanged while protected; one 100 % rung at rung 1 once unprotected."""
        if self.unprotected and self.levels:
            return [self.levels[0]], [1.0]
        return list(self.levels), list(self.fracs)

    def adverse_close(self, close: float) -> bool:
        if not self.unprotected:
            return False
        s = 1.0 if self.side == "long" else -1.0
        return bool(s * (self.entry - float(close)) > self.p.tick + 1e-12)


def watch_open_trades(watches: dict, trades, now, p: Params, acked=None, last_close: float | None = None) -> list:
    """new-no-working-stop-close-exit (stop_ack_sec; paper order handling): one StopAckWatch per OPEN simulated trade (no exit yet), ticked once per poll. `acked(trade)` says whether the broker has
    acknowledged the protective stop (None = the paper layer places no real order, so the stop counts as acknowledged at once). Returns the actions for the caller: ("unprotected", entry_time,
    (levels, fracs)) the first time a position goes unprotected (work ONE 100 % rung at rung 1), and ("exit_market", entry_time, close) when a bar closes against an unprotected position."""
    acts: list = []
    if p.stop_ack_sec <= 0:
        return acts
    for tr in trades:
        if tr.exits or tr.entry_time is None:
            continue
        w = watches.get(tr.entry_time)
        if w is None:
            w = watches[tr.entry_time] = StopAckWatch(p, tr.side, tr.entry, [tr.t1] + ([tr.t2] if tr.t2 is not None else []), [1.0], tr.entry_time)
        was = w.unprotected
        if w.tick(now, True if acked is None else bool(acked(tr))) and not was:
            acts.append(("unprotected", tr.entry_time, w.ladder()))
        if last_close is not None and w.adverse_close(last_close):
            acts.append(("exit_market", tr.entry_time, float(last_close)))
    return acts


def history_days(minutes: int) -> int:
    """Calendar days to fetch (review fix): at least backtest.HIST_DAYS + 1 sessions, like the
    backtest (IPDA 40/60, ipda_eq_day, org_days > 5); 1-minute bars are capped by Schwab."""
    need = (B.HIST_DAYS + 1) * 7 // 5 + 10              # sessions -> calendar days, with holidays
    return min(need, SCHWAB_1M_DAYS) if minutes == 1 else need


def short_history(n_prior: int, p: Params) -> str | None:
    """A warning when the prior sessions are too few for a long-history switch (paper vs backtest)."""
    need = 0
    if p.ipda_pools or p.ipda_next or p.ipda_eq_day != "off":
        need = 60                                        # the 60-day range (and ipda_eq_day's three)
    if p.org_days > 5:
        need = max(need, p.org_days + 1)
    if p.ipda_anchor != "rolling" and (p.ipda_pools or p.ipda_next or p.ipda_eq_day != "off"):
        need = max(need, 100)                            # caption-gap B21: the windows end before the last closed month's first day
    if p.ipda_pools or p.ipda_next or p.ipda_eq_day != "off":
        need = max(need, max(p.ipda_windows) + 1)             # caption-gap levels_detectors #3/3: the 3 / 6 / 12-month windows
    if p.monthly_ohlc:
        need = max(need, 90)
    if p.tf_lookback.get("D"):
        need = max(need, int(p.tf_lookback["D"]) + 1)
    if p.ipda_beyond_days:
        need = max(need, p.ipda_beyond_days + 1)
    if n_prior < min(need, B.hist_days(p)):
        return f"paper history has {n_prior} prior sessions; the ipda / org_days switches need {need}"
    return None


def load_risk_state(path: Path, today, p: Params) -> dict | None:
    """E10 loss_halving carry-over for paper mode (review fix: it started fresh every day). The file holds
    {date, start, end}: `start` = the state before that day, `end` = after it. A restart on the same day
    reuses `start` (the day is re-simulated from the bars); a later day starts from `end`."""
    if not p.loss_halving:
        return None
    from .entries import new_risk_state
    try:
        d = json.loads(Path(path).read_text())
        if d.get("date") == str(today):
            return dict(d["start"])
        if d.get("date") and d["date"] < str(today):
            return dict(d["end"])
    except (OSError, ValueError, KeyError):
        pass
    return new_risk_state()


def save_risk_state(path: Path, today, start: dict | None, end: dict | None) -> None:
    """Persist the E10 state after today's simulated trades (see load_risk_state)."""
    if start is None or end is None:
        return
    Path(path).write_text(json.dumps(dict(date=str(today), start=start, end=end)))


def week_state(out_dir: Path, symbol: str, today) -> dict:
    """X15 / D19 the week's trade state before `today` for paper mode (the backtest's backtest.week_state): read from the
    paper CSVs already written for the earlier days of the same Monday-Friday week (one row per trade; a trade that
    was logged again when it closed counts once, the last row wins). {n, net, final_hits, all_final}."""
    wk = today.isocalendar()[:2]
    last: dict = {}
    for f in sorted(Path(out_dir).glob(f"paper_{symbol}_*.csv")):
        try:
            d = datetime.strptime(f.stem.rsplit("_", 1)[1], "%Y%m%d").date()
        except ValueError:
            continue
        if d >= today or d.isocalendar()[:2] != wk:
            continue
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                last[(d, r.get("entry_time"))] = r
    n = len(last)
    fh_ = sum(1 for r in last.values() if str(r.get("final_hit")).lower() == "true")
    net = 0.0
    for r in last.values():
        try:
            net += float(r.get("net") or 0.0)
        except ValueError:
            pass
    return dict(n=n, net=net, final_hits=fh_, all_final=bool(n) and fh_ == n)


def paper_rows(out_dir: Path, symbol: str, today) -> list:
    """Caption-gap pass day_week_context#3/3 (the month / week budgets: max_trades_month, weekly_target_pct / weekly_cap_pts, skip_fri_if_week_up, aug_dd_stop_pct, low_mag_week_cap): the trade rows
    of every earlier paper day as the backtest's `rows` ({date, net, gross, shares, side, entry_time}), one per trade (a trade logged again at its close counts once, the last row wins)."""
    last: dict = {}
    for f in sorted(Path(out_dir).glob(f"paper_{symbol}_*.csv")):
        try:
            d = datetime.strptime(f.stem.rsplit("_", 1)[1], "%Y%m%d").date()
        except ValueError:
            continue
        if d >= today:
            continue
        with f.open(newline="") as fh:
            for r in csv.DictReader(fh):
                last[(d, r.get("entry_time"))] = r
    rows = []
    for (d, et), r in sorted(last.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        def num(k):
            try:
                return float(r.get(k) or 0.0)
            except ValueError:
                return 0.0
        rows.append(dict(date=d, net=num("net"), gross=num("gross"), shares=int(num("shares")), side=r.get("side", ""), entry_time=et, exit_reason=r.get("exit_reason", "")))
    return rows


def snapshot(c, symbol: str, partner: str | None, minutes: int, p: Params, risk_state: dict | None = None,
             week: dict | None = None):
    """Today's trades and armed setups from the bars closed so far (Schwab). `risk_state` (E10) is
    advanced in place by the simulated day - pass a copy of the day's starting state."""
    from silver_bullet.data import schwab_history
    days = history_days(minutes)
    now = pd.Timestamp.now(tz=B.NY)
    df = schwab_history(c, symbol, days=days, minutes=minutes)
    q = schwab_history(c, partner, days=days, minutes=minutes) if partner else None
    ref = None
    if p.bias_open_src == "es_map":              # bias_htf D22: the futures midnight open mapped onto this instrument
        try:                                      # [not exercised against the live feed: Schwab futures symbols vary]
            ref = schwab_history(c, p.es_symbol, days=days, minutes=minutes)
        except Exception as e:                    # no futures bars: the frame's own midnight stand-in is used
            warnings.warn(f"bias_open_src='es_map': no {p.es_symbol} bars ({e}); using the frame's own midnight open")
    trades, log, _ = evaluate(df, symbol, minutes, p, now, q, risk_state=risk_state, week=week, ref_df=ref)
    return trades, log


def evaluate(df: pd.DataFrame, symbol: str, minutes: int, p: Params, now: pd.Timestamp,
             partner_df: pd.DataFrame | None = None, meta: pd.DataFrame | None = None,
             risk_state: dict | None = None, week: dict | None = None, ref_df: pd.DataFrame | None = None):
    """The paper decision for `now` from a recorded / live frame: closed bars only, today's
    session as a partial day, built by backtest.prepare / day_kwargs exactly like a backtest
    (same session close, lock tables, confluence, gaps, history length). Returns (trades, log,
    locks); ([], [], []) when today is not in the frame."""
    df = df[df.index + pd.Timedelta(minutes=minutes) <= now]          # closed bars only
    pr = B.prepare(df, minutes, symbol, p, partial_last=True, meta=meta, ref_df=ref_df)   # owner #1 resolved inside
                                                                          # (ref_df: D22 es_map - the futures frame whose midnight is mapped)
    ds = pr.ds
    if len(ds) < 4 or ds[-1].index[0].date() != now.date():
        return [], [], []
    pa = None
    if partner_df is not None:
        q = partner_df[partner_df.index + pd.Timedelta(minutes=minutes) <= now]
        qs = B.days(q, minutes, partial_last=True, close=pr.p.session_close)
        if qs and qs[-1].index[0].date() == now.date():
            pa = (qs[-1], [B.rth(x) for x in qs[:-1]][-21:])
    log: list = []
    locks: list = []
    kw = B.day_kwargs(pr, len(ds) - 1, week=week)
    msg = short_history(len(kw["hist"]), pr.p)
    if msg:
        warnings.warn(msg)
    trades = run_day(partner=pa, log=log, live=True, locks=locks, risk_state=risk_state, **kw)
    return trades, log, locks


def run(symbol="SPY", partner="QQQ", minutes=1, p: Params | None = None, out="runs/mentorship"):
    from claude_hf.data import client
    p = p or Params()
    c = client()
    Path(out).mkdir(parents=True, exist_ok=True)
    seen_arm, seen_tr = set(), {}
    watches: dict = {}
    rs_path = Path(out) / f"risk_state_{symbol}.json"
    rs_start = load_risk_state(rs_path, datetime.now().date(), p)     # E10 carried across days
    rs_day = None
    path = Path(out) / f"paper_{symbol}_{datetime.now():%Y%m%d}.csv"
    print(f"paper mode {symbol} {minutes}m (partner {partner}); simulated only, logging to {path}")
    while True:
        now = pd.Timestamp.now(tz=B.NY)
        if now.hour * 60 + now.minute > 16 * 60 + 5:
            save_risk_state(rs_path, now.date(), rs_start, rs_day)
            print("session over"); break
        try:
            rs_try = None if rs_start is None else dict(rs_start)
            wk_ = week_state(Path(out), symbol, now.date()) if p.dw_needs_week else None   # X15 / D19 weekly cap
            why3 = None
            if _DWC3.needs_week(p):                   # caption-gap pass day_week_context#3/3: the month / week budgets, from the earlier paper days (the backtest's week_extra)
                wk_, why3 = _DWC3.week_extra(wk_, paper_rows(Path(out), symbol, now.date()), now.date(), p)
            if why3:
                trades, log = [], []                  # the budget stopped the day
            else:
                trades, log = snapshot(c, symbol, partner, minutes, p, risk_state=rs_try, week=wk_)
                trades = _DWC3.cap_day_trades(trades, p, wk_)
            rs_day = rs_try
        except Exception as e:                        # keep going through API hiccups
            print(f"{now:%H:%M:%S} fetch failed: {e}"); trades, log = [], []
        for ev in log:
            if ev not in seen_arm:
                seen_arm.add(ev)
                print(f"{ev[0]:%H:%M} ARMED {ev[2]} {ev[3]} after {ev[4]} sweep: limit {ev[5]:.2f} "
                      f"stop {ev[6]:.2f} t1 {ev[7]:.2f}")
        for act in watch_open_trades(watches, trades, now, p):                # caption-gap new-no-working-stop-close-exit: the stop acknowledgement watch of the open positions
            print(f"{now:%H:%M} STOP-ACK {act[0]} {act[1]} {act[2]}")
        for tr in trades:
            r = tr.row(p.cost_per_share)
            key = (r["entry_time"], r["exit_reason"])
            if seen_tr.get(r["entry_time"]) != key:
                seen_tr[r["entry_time"]] = key
                print(f"{now:%H:%M} {r['side']} {r['shares']} @ {r['entry']:.2f} -> {r['exit_reason']} "
                      f"net {r['net']:+.2f}")
                new = not path.exists()
                with path.open("a", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=list(r))
                    if new:
                        w.writeheader()
                    w.writerow(r)
        wait = minutes * 60 - (time.time() % (minutes * 60)) + 5    # just after the next close
        time.sleep(wait)
