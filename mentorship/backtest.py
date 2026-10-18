"""Backtest the ICT Mentorship model on SPY (QQQ as the SMT partner) or on a random walk."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from claude_hf.daytypes import JOBS, is_trading_day
from . import htf
from .strategy import Params, run_day

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


def days(df: pd.DataFrame, tf: int, partial_last: bool = False) -> list[pd.DataFrame]:
    """Complete sessions only: 00:00-16:00 bars of days whose regular session is >= 90%
    present and runs to the last bar before 16:00 (the final day may be partial with
    `partial_last`, as in live trading)."""
    t = df.index.hour * 60 + df.index.minute
    df = df[t < 960]                                  # midnight (SPY: 04:00) to 16:00
    out = []
    groups = list(df.groupby(df.index.date))
    for k, (d, g) in enumerate(groups):
        tt = g.index.hour * 60 + g.index.minute
        rth = g[tt >= 570]
        if len(rth) >= 0.9 * 390 / tf and (rth.index[-1].hour * 60 + rth.index[-1].minute) >= 960 - tf:
            out.append(g)
        elif partial_last and k == len(groups) - 1 and len(rth):
            out.append(g)
    return out


def rth(g: pd.DataFrame) -> pd.DataFrame:
    return g[(g.index.hour * 60 + g.index.minute) >= 570]


def run(df: pd.DataFrame, tf: int, symbol: str = "SPY", p: Params | None = None,
        partner: pd.DataFrame | None = None, warmup: int = 3, partial_last: bool = False,
        bias_table: pd.DataFrame | None = None, confluence: bool = True,
        partner2: pd.DataFrame | None = None, intermarket: dict | None = None) -> pd.DataFrame:
    p = p or Params()
    bt = bias_table if bias_table is not None else (htf.table(df, p.es_pt) if htf.has_overnight(df) else None)
    og = htf.opening_gaps(df, p.es_pt) if htf.has_overnight(df) else None
    tt = df.index.hour * 60 + df.index.minute
    pre = df[(tt >= 570) & (tt < p.org_close)]
    closes = pre.groupby(pre.index.date).close.last().to_dict()     # ORG close per day
    cf = None
    if confluence and htf.has_overnight(df):
        from .confluence import Confluence
        cf = Confluence(df, tf, p.es_pt)
    ds = days(df, tf, partial_last)
    pmap = {g.index[0].date(): g for g in days(partner, tf, partial_last)} if partner is not None else {}
    pmap2 = {g.index[0].date(): g for g in days(partner2, tf, partial_last)} if partner2 is not None else {}
    hist_p: list[pd.DataFrame] = []
    hist_p2: list[pd.DataFrame] = []
    rows = []
    for k, g in enumerate(ds):
        d = g.index[0].date()
        pa = None
        if d in pmap and len(hist_p) >= warmup:
            pa = (pmap[d], hist_p)
        pa2 = (pmap2[d], hist_p2) if d in pmap2 and len(hist_p2) >= warmup else None
        if k >= warmup:
            b = bt.loc[d].to_dict() if bt is not None and d in bt.index else None
            wk = d.isocalendar()[:2]
            n_wk = sum(1 for r in rows if r["date"].isocalendar()[:2] == wk) if p.max_trades_week else 0
            if p.max_trades_week and n_wk >= p.max_trades_week:
                continue
            day_trades = run_day(g, [rth(x) for x in ds[max(0, k - 21):k]], symbol, p, tf, pa, bias=b, conf=cf,
                                 gaps=htf.gaps_for_day(og, d) if og is not None else None,
                                 closes=closes, evening=_evening(df, d) if p.globex_pool else None,
                                 partner2=pa2, intermarket=(intermarket or INTERMARKET()).get(d))
            if p.max_trades_week:
                day_trades = day_trades[:p.max_trades_week - n_wk]
            for tr in day_trades:
                rows.append(tr.row(p.cost_per_share))
        if d in pmap:
            hist_p = (hist_p + [rth(pmap[d])])[-21:]
        if d in pmap2:
            hist_p2 = (hist_p2 + [rth(pmap2[d])])[-21:]
    out = pd.DataFrame(rows)
    if len(out):
        out.attrs["days"] = len(ds) - warmup
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
    for col in ("setup", "side", "day_type", "unicorn", "smt", "swept", "exit_reason"):
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


def combine(*runs: pd.DataFrame) -> pd.DataFrame:
    """Trade one instrument per session (watch one market, rules Ep 05): of the setups the
    instruments produced, keep the first to fill. On a tie, keep the one whose SMT check
    didn't show its partner holding stronger. Uses only what was known at the fill."""
    t = pd.concat([r for r in runs if len(r)], ignore_index=True)
    if not len(t):
        return t
    t = t.assign(_weak=t.smt.eq(True)).sort_values(["entry_time", "_weak"])
    return t.groupby(["date", "session"], sort=False).head(1).drop(columns="_weak").sort_values("entry_time")
