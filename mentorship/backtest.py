"""Backtest the ICT Mentorship model on SPY (QQQ as the SMT partner) or on a random walk."""
from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from claude_hf.daytypes import JOBS, is_trading_day
from . import htf
from .entries import new_risk_state
from .strategy import ROUND_STEP, Params, resolve_session_close, run_day

DATA = Path("data/mentorship")
NY = "America/New_York"


def _read(path: Path) -> pd.DataFrame:
    """CSV bars in New York time. A parquet copy next to the CSV (rebuilt whenever the CSV
    is newer) makes repeat loads ~50x faster."""
    pq = path.with_suffix(".parquet")
    if pq.exists() and pq.stat().st_mtime >= path.stat().st_mtime:
        return pd.read_parquet(pq)
    df = pd.read_csv(path, index_col=0)
    df.index = pd.to_datetime(df.index, utc=True).tz_convert(NY)
    df = df[["open", "high", "low", "close", "volume"]].sort_index()
    try:
        tmp = pq.with_suffix(f".{os.getpid()}.tmp")
        df.to_parquet(tmp)
        os.replace(tmp, pq)                     # atomic: parallel workers never see half a file
    except OSError:
        pass
    return df


def load(symbol: str, minutes: int, rth_history: bool = True, source: str = "schwab") -> pd.DataFrame:
    """Extended-hours bars, extended back with regular-session-only bars (`*_rth.csv`)
    for the days the extended pull doesn't reach. Those days have no pre-market, so their
    'midnight open' falls back to the 09:30 open and they have no pre-market high/low."""
    if source == "databento":                    # CME ES / NQ / YM futures, see databento_data.py
        return _read(DATA / f"{symbol}_{minutes}min_db.csv")
    if source == "merged":                       # HistData, holes filled from Dukascopy
        from .histdata import fix_sessions, merge
        h = fix_sessions(_read(DATA / f"{symbol}_{minutes}min_hd.csv"))
        dk = DATA / f"{symbol}_{minutes}min_duka.csv"
        return merge(h, _read(dk), minutes) if dk.exists() else h
    if source == "histdata":                     # index CFDs, see histdata.py (SPX, NDX)
        from .histdata import fix_sessions
        return fix_sessions(_read(DATA / f"{symbol}_{minutes}min_hd.csv"))
    if source == "alpaca":                       # see alpaca_data.py: years, with extended hours
        return _read(DATA / f"{symbol}_{minutes}min_alpaca.csv")
    df = _read(DATA / f"{symbol}_{minutes}min.csv")
    extra = DATA / f"{symbol}_{minutes}min_rth.csv"
    if rth_history and extra.exists():
        old = _read(extra)
        old = old[old.index.normalize() < df.index[0].normalize()]
        df = pd.concat([old, df])
    return df


def fetch(symbols=("SPY", "QQQ"), c=None) -> None:
    """Schwab price history with extended hours (pre-market gives the 04:00 'midnight' proxy).
    Schwab returns ~6.5 months of 5-minute and ~6 weeks of 1-minute bars this way, plus
    regular-session-only 5-minute bars back to late January."""
    import time
    from claude_hf.data import client
    from silver_bullet.data import schwab_history
    c = c or client()
    DATA.mkdir(parents=True, exist_ok=True)
    for m, d, ext, tag in ((5, 280, True, ""), (1, 50, True, ""), (5, 400, False, "_rth")):
        for s in symbols:
            df = schwab_history(c, s, days=d, minutes=m, extended_hours=ext)
            df.to_csv(DATA / f"{s}_{m}min{tag}.csv")
            print(s, m, tag, len(df), df.index[0], df.index[-1])
            time.sleep(5)


def days(df: pd.DataFrame, tf: int, partial_last: bool = False, close: int = 960) -> list[pd.DataFrame]:
    """Complete sessions only: midnight (SPY: 04:00) to the session close (`close`: 16:00, or
    16:15 for index futures - owner #1) bars of days whose regular session is >= 90% present
    and runs to the last bar before 16:00 (the final day may be partial with `partial_last`,
    as in live trading)."""
    t = df.index.hour * 60 + df.index.minute
    df = df[t < max(960, close)]
    out = []
    groups = list(df.groupby(df.index.date))
    for k, (d, g) in enumerate(groups):
        tt = g.index.hour * 60 + g.index.minute
        rth = g[tt >= 570]
        if len(rth) >= 0.9 * 390 / tf and (rth.index[-1].hour * 60 + rth.index[-1].minute) >= 960 - tf:
            out.append(g)
        elif partial_last and k == len(groups) - 1 and len(g):     # live: today so far, pre-open too
            out.append(g)
    return out


def rth(g: pd.DataFrame) -> pd.DataFrame:
    """09:30-16:00 only: the history frames stay the regular session even when the day frame
    runs to 16:15 (prior-day levels, NWOG, ORG and SMT history unchanged; owner #1)."""
    t = g.index.hour * 60 + g.index.minute
    return g[(t >= 570) & (t < 960)]


_META: dict = {}


def load_meta(symbol: str, minutes: int, source: str = "databento") -> pd.DataFrame | None:
    """#13 (DATA1): per-bar [adj, instrument_id, roll] for the databento series, on the same
    index as load(). adj = back-adjusted - raw (real front-month price = engine - adj). Taken
    from the `adj` column when the CSV was built with it (databento_data.back_adjust), else
    derived from <S>_1min_db.csv - <S>_1min_dbraw.csv; 5-minute meta = the last 1-minute bar of
    each bucket (roll = any). None for other sources or when the raw file is missing."""
    if source != "databento":
        return None
    key = (symbol, minutes)
    if key in _META:
        return _META[key]
    pq = DATA / f"{symbol}_{minutes}min_dbmeta.parquet"
    adj_f, raw_f = DATA / f"{symbol}_1min_db.csv", DATA / f"{symbol}_1min_dbraw.csv"
    if pq.exists() and adj_f.exists() and pq.stat().st_mtime >= adj_f.stat().st_mtime:
        _META[key] = pd.read_parquet(pq)
        return _META[key]
    if not (adj_f.exists() and raw_f.exists()):
        return None
    a = pd.read_csv(adj_f, index_col=0)
    a.index = pd.to_datetime(a.index, utc=True).tz_convert(NY)
    a = a[~a.index.duplicated(keep="last")].sort_index()
    if "adj" in a:
        m = a[["adj"]].copy()
    else:
        r = pd.read_csv(raw_f, index_col=0)
        r.index = pd.to_datetime(r.index, utc=True).tz_convert(NY)
        r = r[~r.index.duplicated(keep="last")]
        m = pd.DataFrame({"adj": (a.close - r.close.reindex(a.index)).round(6)})
    m["instrument_id"] = a["instrument_id"] if "instrument_id" in a else np.nan
    if "roll" in a:
        m["roll"] = a["roll"].astype(bool)
    else:
        m["roll"] = m.instrument_id.ne(m.instrument_id.shift()) & m.instrument_id.shift().notna()
    if minutes != 1:
        g = m.groupby(m.index.floor(f"{minutes}min"))
        m = pd.DataFrame({"adj": g.adj.last(), "instrument_id": g.instrument_id.last(), "roll": g.roll.any()})
    try:
        m.to_parquet(pq)
    except OSError:
        pass
    _META[key] = m
    return m


def lock_cuts(p: Params) -> set:
    """#9: the draw-lock minutes in use (one htf table each): the AM / PM session starts, the
    09:45 / 10:00 release locks, 07:00 / 09:00 pre-open windows, Ma Deuce 08:00 and the London
    Silver Bullet 02:00 (review fix: London now gets its own cut table like the others)."""
    cuts = {p.am[0] or 570, p.pm[0] or 810, 585, 600}
    if p.pre_0700:
        cuts.add(420)
    if p.pre_0900 or p.post_news:
        cuts.add(540)
    if p.ma_deuce:
        cuts.add(480)
    if p.sb_model and p.sb_london:
        cuts.add(120)
    if (p.last_hour_own_slot or p.last_hour_setup) and not p.lh_no_lock:
        cuts.add(p.last_hour[0])                  # setups_models: the own last-hour slot's 15:00 lock
    return cuts


def lock_tables(df: pd.DataFrame, p: Params, bias_table: pd.DataFrame | None = None) -> dict:
    """#9: one htf table per draw-lock minute in use (bars closed by that minute), cut 570 being
    the ordinary bias table. {cut: table}; empty without overnight bars or with draw_lock off."""
    if p.draw_lock == "off" or not htf.has_overnight(df):
        return {}
    out = {}
    for m in sorted(lock_cuts(p)):
        if m == 570 and bias_table is not None:
            out[m] = bias_table
        else:
            out[m] = htf.table(df, p.es_pt, cut_min=m, vi=p.vi_arrays, flip_triggers=p.flip_triggers,
                               **htf_kw(p))
    return out


HIST_DAYS = 61                    # prior sessions handed to run_day (backtest and paper alike); 61 =
                                  # the IPDA 60-day look-back + 1 (B21, levels_detectors; was 45)


def htf_kw(p: Params) -> dict:
    """levels_detectors switches that change the htf table / confluence arrays (A5 c2 check, A9 VI
    size and death rule). Empty at the old values, so cached tables keep their meaning."""
    kw = {}
    if p.fvg_c2_dir:
        kw["c2_dir"] = True
    if p.vi_min_gap_pts:
        kw["vi_min_gap"] = p.vi_min_gap_pts * p.es_pt
    if p.vi_body_death:
        kw["vi_body_death"] = True
    return kw


@dataclass
class Prepared:
    """Everything run_day needs that is built once per instrument frame. Shared by backtest.run
    and paper mode, so the paper lock / cap / gaps / confluence equal the backtest's (owner #9
    test i; review: paper used to pass no conf, gaps or closes)."""
    p: Params
    df: pd.DataFrame
    tf: int
    symbol: str
    ds: list
    bt: pd.DataFrame | None
    cuts: dict
    og: pd.DataFrame | None
    closes: dict
    cf: object
    meta: pd.DataFrame | None
    eth: dict | None = None        # L2 / L3 / L10 / Ep08.10: {date: (open, high, low, close)} of full sessions


def prepare(df: pd.DataFrame, tf: int, symbol: str = "SPY", p: Params | None = None,
            partial_last: bool = False, bias_table: pd.DataFrame | None = None,
            confluence: bool = True, meta: pd.DataFrame | None = None,
            lock_cuts: dict | None = None) -> Prepared:
    p = resolve_session_close(p or Params(), df, symbol)        # owner #1: 16:15 futures, 16:00 SPY
    ov = htf.has_overnight(df)
    inert = meta is None or p.price_frame == "back_adjusted"
    if p.round_pools and symbol.upper() in ROUND_STEP and inert and p.price_frame != "raw":
        warnings.warn(f"#13: round_pools is on but inert for {symbol} (price_frame={p.price_frame!r}, "
                      f"meta {'missing' if meta is None else 'given'}): no front-month mapping",
                      stacklevel=3)
    bt = bias_table if bias_table is not None else (
        htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **htf_kw(p)) if ov else None)
    cuts = lock_cuts if lock_cuts is not None else lock_tables(df, p, bt)
    og = htf.opening_gaps(df, p.es_pt) if ov else None
    tt = df.index.hour * 60 + df.index.minute
    pre = df[(tt >= 570) & (tt < (p.org_close or p.session_close or 960))]   # L7: per symbol
    closes = pre.groupby(pre.index.date).close.last().to_dict()     # ORG close per day
    cf = None
    if confluence and ov:
        from .confluence import Confluence
        cf = Confluence(df, tf, p.es_pt, vi=p.vi_arrays, breakers=p.conf_breakers, **htf_kw(p))
    ds = days(df, tf, partial_last, p.session_close)
    eth = None
    ipda_on = p.ipda_pools or p.ipda_next or p.ipda_eq_day != "off"
    if (p.pd_hl_session == "eth" or p.matrix_full or p.wick_session == "eth" or p.pw_pm_full_session
            or (ipda_on and p.ipda_session == "eth") or (p.ma_deuce and p.md_eth)):   # M15 md_eth (review fix)
        se = htf.sessions(df)                  # full sessions (evening reopen -> close), by trading date
        eth = {t.date(): (float(r.open), float(r.high), float(r.low), float(r.close)) for t, r in se.iterrows()}
    return Prepared(p, df, tf, symbol, ds, bt, cuts, og, closes, cf, meta, eth)


def day_kwargs(pr: Prepared, k: int, equity: float | None = None, intermarket: dict | None = None) -> dict:
    """run_day inputs for day k of pr.ds (the partner / log / locks plumbing is the caller's)."""
    p, g = pr.p, pr.ds[k]
    d = g.index[0].date()
    return dict(df=g, hist=[rth(x) for x in pr.ds[max(0, k - HIST_DAYS):k]], symbol=pr.symbol, p=p, tf=pr.tf,
                bias=pr.bt.loc[d].to_dict() if pr.bt is not None and d in pr.bt.index else None,
                conf=pr.cf,
                gaps=htf.gaps_for_day(pr.og, d, p.nwog_keep, p.nwog_days, p.nwog_skip_holiday,
                                      p.nwog_trading_days) if pr.og is not None else None,
                eth=pr.eth,
                closes=pr.closes, evening=_evening(pr.df, d) if p.globex_pool else None,
                intermarket=intermarket, equity=equity,
                bias_by_cut={m: t_.loc[d].to_dict() for m, t_ in pr.cuts.items() if d in t_.index},
                meta=pr.meta)


def run(df: pd.DataFrame, tf: int, symbol: str = "SPY", p: Params | None = None,
        partner: pd.DataFrame | None = None, warmup: int = 3, partial_last: bool = False,
        bias_table: pd.DataFrame | None = None, confluence: bool = True,
        partner2: pd.DataFrame | None = None, intermarket: dict | None = None,
        meta: pd.DataFrame | None = None, lock_cuts: dict | None = None) -> pd.DataFrame:
    """Backtest one instrument. `meta` (#13): databento meta (load_meta) for the front-month
    price frame; `lock_cuts` (#9): {minute: htf table cut there} (built here when None).
    The result's attrs carry "days", "locks" (one row per session lock) and "skips"."""
    pr = prepare(df, tf, symbol, p, partial_last, bias_table, confluence, meta, lock_cuts)
    p, ds = pr.p, pr.ds
    pmap = {g.index[0].date(): g for g in days(partner, tf, partial_last, p.session_close)} if partner is not None else {}
    pmap2 = {g.index[0].date(): g for g in days(partner2, tf, partial_last, p.session_close)} if partner2 is not None else {}
    locks, skips = [], []
    hist_p: list[pd.DataFrame] = []
    hist_p2: list[pd.DataFrame] = []
    rows = []
    rs = new_risk_state() if p.loss_halving else None     # E10: carried across days
    for k, g in enumerate(ds):
        d = g.index[0].date()
        pa = None
        if d in pmap and len(hist_p) >= warmup:
            pa = (pmap[d], hist_p)
        pa2 = (pmap2[d], hist_p2) if d in pmap2 and len(hist_p2) >= warmup else None
        if k >= warmup:
            wk = d.isocalendar()[:2]
            n_wk = sum(1 for r in rows if r["date"].isocalendar()[:2] == wk) if p.max_trades_week else 0
            if p.max_trades_week and n_wk >= p.max_trades_week:
                continue
            eq = None
            if p.risk_basis == "equity":               # #12: start-of-day equity, closed trades only
                eq = p.account_equity + sum(r["net"] for r in rows)
            kw = day_kwargs(pr, k, eq, (intermarket or INTERMARKET()).get(d))
            day_trades = run_day(partner=pa, partner2=pa2, locks=locks, skips=skips, risk_state=rs, **kw)
            if p.max_trades_week:
                day_trades = day_trades[:p.max_trades_week - n_wk]
            for tr in day_trades:
                rows.append(tr.row(p.cost_per_share))
        if d in pmap:
            hist_p = (hist_p + [rth(pmap[d])])[-21:]
        if d in pmap2:
            hist_p2 = (hist_p2 + [rth(pmap2[d])])[-21:]
    out = pd.DataFrame(rows)
    if len(out):                           # several setups per day: report in time order
        out = out.sort_values(["entry_time", "setup"], kind="stable").reset_index(drop=True)
        out.attrs["days"] = len(ds) - warmup
    out.attrs["locks"] = locks
    out.attrs["skips"] = skips
    return out


_IM = None


def INTERMARKET() -> dict:
    """date -> {"dxy": +1/-1, "tnx": +1/-1}: the prior day's close vs its 20-day mean for the
    dollar index and the 10-year yield (free Yahoo daily data, data/mentorship/yahoo)."""
    global _IM
    if _IM is None:
        _IM = {}
        y = DATA / "yahoo"
        cols = {}
        for n in ("DXY", "TNX"):
            f = y / f"{n}_1d.csv"
            if f.exists():
                s = pd.read_csv(f, index_col=0).iloc[:, :]
                s.columns = [c.lower() for c in s.columns]
                c = pd.to_numeric(s["close"], errors="coerce")
                c.index = pd.to_datetime(c.index.str[:10])
                cols[n.lower()] = np.sign(c - c.rolling(20).mean()).shift(1)   # prior day only
        if cols:
            t = pd.DataFrame(cols).dropna(how="all")
            full = pd.date_range(t.index[0], t.index[-1] + pd.Timedelta(days=3))
            t = t.reindex(full).ffill()
            _IM = {k.date(): {c: (0 if pd.isna(v) else int(v)) for c, v in r.items()}
                   for k, r in t.iterrows()}
    return _IM


def _evening(df: pd.DataFrame, d) -> pd.DataFrame:
    """Bars from the prior evening's 18:00 reopen to midnight of day d."""
    a = pd.Timestamp(d, tz=NY)
    return df[(df.index >= a - pd.Timedelta(hours=6)) & (df.index < a)]


def stats(t: pd.DataFrame, account: float = 100_000.0) -> dict:
    if t is None or not len(t):
        return {"trades": 0}
    eq = t.sort_values("entry_time").net.cumsum()
    dd = float((eq.cummax().clip(lower=0) - eq).max())
    wins, losses = t.net[t.net > 0].sum(), -t.net[t.net < 0].sum()
    return {"trades": int(len(t)), "win_rate": round(float((t.net > 0).mean()), 3),
            "profit_factor": round(float(wins / losses), 2) if losses else float("inf"),
            "avg_R": round(float(t.R.mean()), 3), "net": round(float(t.net.sum()), 2),
            "gross": round(float(t.gross.sum()), 2), "costs": round(float(t.costs.sum()), 2),
            "max_dd": round(dd, 2), "max_dd_pct": round(100 * dd / account, 2)}


def report(t: pd.DataFrame) -> dict:
    out = {"all": stats(t)}
    if not len(t):
        return out
    for col in ("setup", "side", "day_type", "unicorn", "unicorn_side", "lh_sweet", "capped", "lock_capped",
                "sloppy", "draw_side", "entry_kind", "smt", "swept", "exit_reason"):
        if col not in t:
            continue
        out[f"by_{col}"] = {str(k): stats(g) for k, g in t.groupby(t[col].astype(str))}
    t = t.assign(month=pd.to_datetime(t.entry_time.astype(str).str[:10]).dt.strftime("%Y-%m"))
    out["by_month"] = {k: stats(g) for k, g in t.groupby("month")}
    return out


def synthetic(start="2026-03-30", end="2026-10-14", tf=5, seed=0, price=700.0,
              partner_price=600.0, rho=0.9) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Two correlated random walks on the 04:00-16:00 grid of each trading day, with a
    U-shaped intraday volatility profile. There is nothing to find here, so a sound
    backtest should lose roughly its costs."""
    rng = np.random.default_rng(seed)
    a, b = [], []
    pa, pb = price, partner_price
    for d in pd.bdate_range(start, end):
        if not is_trading_day(d.date()):
            continue
        idx = pd.date_range(pd.Timestamp(d, tz=NY) + pd.Timedelta(hours=4), periods=720 // tf,
                            freq=f"{tf}min")
        m = idx.hour * 60 + idx.minute
        vol = np.where(m < 570, 0.35, 1.0) * np.where((m >= 570) & (m < 630) | (m >= 900), 1.5, 1.0)
        vol = vol * 0.0006 * np.sqrt(tf)
        z1 = rng.standard_t(4, len(idx)) / np.sqrt(2)
        z2 = rho * z1 + np.sqrt(1 - rho ** 2) * rng.standard_t(4, len(idx)) / np.sqrt(2)
        for z, out, p0 in ((z1, a, pa), (z2, b, pb)):
            c = p0 * np.exp(np.cumsum(z * vol))
            o = np.concatenate([[p0], c[:-1]])
            w = np.abs(rng.normal(0, 0.5, (2, len(idx)))) * vol * p0
            out.append(pd.DataFrame({"open": o, "high": np.maximum(o, c) + w[0],
                                     "low": np.minimum(o, c) - w[1], "close": c,
                                     "volume": 1000.0}, index=idx).round(2))
        pa, pb = float(a[-1].close.iloc[-1]), float(b[-1].close.iloc[-1])
    return pd.concat(a), pd.concat(b)


def save(t: pd.DataFrame, rep: dict, out: str) -> None:
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(out, index=False)
    Path(out).with_suffix(".json").write_text(json.dumps(rep, indent=1, default=str))


def combine(*runs: pd.DataFrame, pick: str = "first") -> pd.DataFrame:
    """Trade one instrument per session (watch one market, rules Ep 05): of the setups the
    instruments produced, keep the first to fill. On a tie, keep the one whose SMT check
    didn't show its partner holding stronger. Uses only what was known at the fill.
    setups_models Ep03.11 / D15 `pick` (Params.smt_pick): "leader" keeps only fills whose own SMT
    check did NOT show the sister holding stronger (smt is not True: this index made the cleaner
    extreme, 003); "laggard" only those where it did (the sick sister, 045 / 053). Each fill's
    smt tag is known at its sweep, so skipping one instrument's fills is causal. Same-bar ties:
    the larger (leader) / smaller (laggard) relative leg (leg_hi_px - ext_px) / ext_px."""
    t = pd.concat([r for r in runs if len(r)], ignore_index=True)
    if not len(t):
        return t
    if pick not in ("first", "leader", "laggard"):
        raise ValueError(f"pick {pick!r}")
    if pick != "first":
        lag = t.smt.eq(True)
        t = t[lag if pick == "laggard" else ~lag]
        if not len(t):
            return t
        if {"ext_px", "leg_hi_px"} <= set(t.columns):
            rel = ((t.leg_hi_px - t.ext_px).abs() / t.ext_px.abs()).fillna(0.0)
            t = t.assign(_rel=-rel if pick == "leader" else rel).sort_values(["entry_time", "_rel"], kind="stable")
            return t.groupby(["date", "session"], sort=False).head(1).drop(columns="_rel").sort_values("entry_time")
    t = t.assign(_weak=t.smt.eq(True)).sort_values(["entry_time", "_weak"])
    return t.groupby(["date", "session"], sort=False).head(1).drop(columns="_weak").sort_values("entry_time")
