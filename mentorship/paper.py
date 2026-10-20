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
from .strategy import Params, run_day


SCHWAB_1M_DAYS = 48        # Schwab keeps roughly 48 calendar days of 1-minute bars


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
            trades, log = snapshot(c, symbol, partner, minutes, p, risk_state=rs_try, week=wk_)
            rs_day = rs_try
        except Exception as e:                        # keep going through API hiccups
            print(f"{now:%H:%M:%S} fetch failed: {e}"); trades, log = [], []
        for ev in log:
            if ev not in seen_arm:
                seen_arm.add(ev)
                print(f"{ev[0]:%H:%M} ARMED {ev[2]} {ev[3]} after {ev[4]} sweep: limit {ev[5]:.2f} "
                      f"stop {ev[6]:.2f} t1 {ev[7]:.2f}")
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
