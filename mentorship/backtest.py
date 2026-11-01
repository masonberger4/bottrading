"""Backtest the ICT Mentorship model on SPY (QQQ as the SMT partner) or on a random walk."""
from __future__ import annotations

import json
import os
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from mentorship.calendar import JOBS_SET as JOBS, is_trading_day
from . import htf
from . import sm4 as _SM4
from . import es3 as _ES3
from . import tp4 as _TP4
from . import me2 as _ME2
from . import dwc2 as _DWC2
from . import dwc3 as _DWC3
from .entries import new_risk_state
from .strategy import ROUND_STEP, SMT_PICKS, Params, resolve_session_close, run_day

DATA = Path("data/mentorship")
ACCEPT = dict(dd_ok=15, dd_max=25, ret_lo=18, ret_hi=25)   # caption-gap OT-backtest-acceptance (cc02_004 ~00:19:52; cc05_013 ~00:02:17): annual drawdown % tolerable / unacceptable, annual return % target band
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


def load_raw(symbol: str, minutes: int) -> pd.DataFrame | None:
    """Caption-gap OT-htf-array-data-series (bias_htf#7/7): the UNADJUSTED front-month series (`<S>_1min_dbraw.csv`, roll gaps left in) at `minutes`-minute bars (the 1-minute file resampled), or None
    when the file is missing."""
    f = DATA / f"{symbol}_1min_dbraw.csv"
    if not f.exists():
        return None
    r = _read(f)
    if minutes != 1:
        g = r.groupby(r.index.floor(f"{minutes}min"))
        r = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(), "volume": g.volume.sum() if "volume" in r else 0.0})
    return r


def series_fallback(p: Params, symbol: str, meta: pd.DataFrame | None) -> Params:
    """htf_series='contract' (056 exact) needs per-contract raw prints; a source without the databento roll meta (CFD / ETF) warns and falls back to the adjusted series (review fix: only databento data may
    reach htf.table's NotImplementedError)."""
    if p.htf_series == "contract" and (meta is None or "adj" not in meta):
        warnings.warn(f"htf_series='contract': no front-month roll meta for {symbol} (CFD / ETF source): the adjusted frame is used", stacklevel=3)
        return replace(p, htf_series="adjusted")
    return p


def raw_series(p: Params, symbol: str, minutes: int, meta: pd.DataFrame | None, df: pd.DataFrame | None = None) -> tuple:
    """(raw frame, adj Series) for htf.table when a bias_htf#7/7 series switch asks for the raw front-month series (htf_series 'raw' / htf_monthly_series 'raw'); (None, None) otherwise. Without the
    databento meta (CFD / ETF sources have no roll data) every non-"adjusted" value warns and falls back to the adjusted frame."""
    want = p.htf_series == "raw" or (p.htf_monthly_series == "raw" and (p.htf_monthly or p.htf_monthly_arrays))
    if not want:
        return None, None
    if meta is None or "adj" not in meta:
        warnings.warn(f"htf_series={p.htf_series!r} / htf_monthly_series={p.htf_monthly_series!r}: no front-month roll meta for {symbol} (CFD / ETF source): the adjusted frame is used", stacklevel=3)
        return None, None
    raw = load_raw(symbol, minutes)
    if raw is None:
        warnings.warn(f"htf_series raw: {symbol}_1min_dbraw.csv is missing: the adjusted frame is used", stacklevel=3)
        return None, None
    if df is not None and len(df):
        raw = raw.loc[df.index[0]:df.index[-1]]          # review fix (cost + look-ahead): only the engine frame's own span, not the 2019-2026 history (a truncated run never sees raw bars after its cut)
    return raw, meta["adj"]


def lock_cuts(p: Params) -> set:
    """#9: the draw-lock minutes in use (one htf table each): the AM / PM session starts, the
    09:45 / 10:00 release locks, 07:00 / 09:00 pre-open windows, Ma Deuce 08:00 and the London
    Silver Bullet 02:00 (review fix: London now gets its own cut table like the others)."""
    cuts = {p.am_win[0] or 570, p.pm[0] or 810, 585, 600}
    if p.pre_0700:
        cuts.add(420)
    if p.pre_0900 or p.post_news:
        cuts.add(540)
    if p.ma_deuce:
        cuts.add(480)
    if p.sb_model and p.sb_london:
        cuts.add(120)
    if p.sb_model and p.sb_0700:
        cuts.add(360)                             # SB package: the 07:00 window's own lock (leg start 06:00)
    if p.sb_model and p.sb_draw_first and (p.sb_last_hour or p.sb_moc_extra):
        cuts.add(870)                             # SB package: the 15:00 / 15:15 windows' own draw lock
    if (p.last_hour_own_slot or p.last_hour_setup) and not p.lh_no_lock:
        cuts.add(p.lh_freeze_t if p.lh_draw_freeze else p.last_hour[0])      # setups_models: the own last-hour slot's 15:00 lock (caption-gap M5: the frozen noon lock)
    from . import newscal as _NC
    cuts |= _NC.lock_cuts_extra(p)                # news_calendar_times: PRE8 08:20, LON, the 08:30 AM
    return cuts


def lock_tables(df: pd.DataFrame, p: Params, bias_table: pd.DataFrame | None = None, wk_joint: dict | None = None, raw: pd.DataFrame | None = None, adj: pd.Series | None = None) -> dict:
    """#9: one htf table per draw-lock minute in use (bars closed by that minute), cut 570 being
    the ordinary bias table. {cut: table}; empty without overnight bars or with draw_lock off."""
    if p.draw_lock == "off" or not htf.has_overnight(df):
        return {}
    out = {}
    for m in sorted(lock_cuts(p)):
        if m == 570 and bias_table is not None:
            out[m] = bias_table
        else:
            out[m] = htf.table(df, p.es_pt, cut_min=m, vi=p.vi_arrays, flip_triggers=p.flip_triggers, wk_joint=wk_joint,
                               **table_kw(p, raw, adj))
    return out


HIST_DAYS = 61                    # prior sessions handed to run_day (backtest and paper alike); 61 =
                                  # the IPDA 60-day look-back + 1 (B21, levels_detectors; was 45)


def hist_days(p: Params) -> int:
    """Prior sessions handed to run_day. Caption-gap B21 ipda_anchor "month" / "swing": the windows end up to ~43 sessions before
    yesterday (the first trading day of the last closed month; the last daily MSS), so 60 more sessions of history are kept.
    Caption-gap levels_detectors #3/3: the longest ipda window (63 / 126 / 252 sessions), tf_lookback["D"], the 3 completed months of monthly_ohlc (90),
    ipda_beyond_days, org_days > 60 and the forward intervals of ipda_forward (60 more) widen it; the defaults keep 61."""
    ext = 45 if getattr(p, "ipda_anchor", "rolling") != "rolling" else 0
    n = HIST_DAYS + ext
    n = max(n, max(getattr(p, "ipda_windows", (60,))) + 1 + ext)
    if getattr(p, "ipda_forward", False):
        n += 60
    if getattr(p, "monthly_ohlc", False):
        n = max(n, 90)
    if getattr(p, "tf_lookback", None) and p.tf_lookback.get("D"):
        n = max(n, int(p.tf_lookback["D"]) + 1)
    if getattr(p, "ipda_beyond_days", 0):
        n = max(n, p.ipda_beyond_days + 1)
    n = max(n, getattr(p, "dw2_hist", 0))           # caption-gap pass day_week_context#2/3: the 60-session ADR5 tercile / 60-day EQ
    n = max(n, getattr(p, "dw1_hist", 0))           # caption-gap pass day_week_context#1/3: the seasonal windows / 252-session trend / monthly closes
    if getattr(p, "htf_history_months", 0):
        n = max(n, int(p.htf_history_months) * 21 + 1)      # caption-gap B5-htf-lookback-9-18-months (bias_htf#4/7): the months of daily history the weekly / monthly arrays need
    if getattr(p, "pd_grid", False) or getattr(p, "grade_confluence", False) or getattr(p, "pd_need_array", False) or getattr(p, "nested_pd_bias", False):
        n = max(n, int(getattr(p, "pd_grid_days", 60)) + 1)            # caption-gap A21-60day-body-range (bias_htf#4/7): the body range's sessions
    return max(n, getattr(p, "org_days", 0) + 1)


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
    # caption-gap pass (levels_detectors #1/3): the VI definition / death rule / two-sided draw and the IPDA array window
    if not p.vi_wick_overlap:
        kw["vi_wick_overlap"] = False
    if p.vi_multi:
        kw["vi_multi"] = True
    if p.vi_dead_rule != "full_span":
        kw["vi_dead_rule"] = p.vi_dead_rule
    if p.ipda_arrays_first20:
        kw["ipda_first20"] = True
    # caption-gap pass (levels_detectors #2/3): the CFD NWOG source and the HTF array definitions
    if p.nwog_cfd_src != "auto":
        kw["nwog_cfd_src"] = p.nwog_cfd_src
    if p.void_rt_ob:
        kw["void_rt_ob"] = True
    # caption-gap pass (levels_detectors #3/3): the per-timeframe look-back windows (array lives)
    if p.tf_lookback:
        kw["tf_lookback"] = dict(p.tf_lookback)
    return kw


def table_kw(p: Params, raw: pd.DataFrame | None = None, adj: pd.Series | None = None) -> dict:
    """htf.table keywords: htf_kw plus the bias_htf column configuration `bx` (Params.bx; absent when empty, so the old table
    and its cache keys are unchanged). The Confluence arrays take htf_kw only."""
    kw = htf_kw(p)
    if p.bx:
        kw["bx"] = p.bx
    if p.vi_two_sided_draw:
        kw["vi_two_sided"] = True       # htf.table only (the Confluence arrays have no draw list)
    # caption-gap pass (levels_detectors #2/3), htf.table only: the daily single-pass draw, the 1h order-block drill, which closes balance an array
    if p.single_pass_draw:
        kw["single_pass_draw"] = True
    if p.htf_ob_ltf_drill:
        kw["htf_ob_ltf_drill"] = True
    # caption-gap pass (levels_detectors #3/3 review), htf.table only: monthly PD arrays (L3-htf-pd-arrays-intraday), the rejection-block closes (A17)
    if p.htf_monthly_arrays:
        kw["monthly_arrays"] = True
    if p.rb_pools:
        kw["rb_closes"] = True
    if p.ipda_arrays:
        kw["ipda_window"] = p.ipda_anchor     # B21 ipda_arrays: the table's daily arrays / swing draws only from the IPDA window of the anchor
    if p.ob_reach == "body":
        kw["ob_reach"] = "body"         # caption-gap A12-ob-reached-body: htf.table only
    if raw is not None and adj is not None:
        kw["raw"], kw["adj"] = raw, adj   # caption-gap OT-htf-array-data-series (bias_htf#7/7): the unadjusted front-month series and its adj
    kw["balance_tf"] = p.balance_tf     # always explicit (review fix #75: the default is now "own", so the cache file of the old default must not be reused)
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
    eve: dict | None = None        # day_week_context: {date: (open, high, low, close)} of the evening session before that date
    midnight_map: dict | None = None   # bias_htf D22 bias_open_src="es_map": {date: the futures midnight open mapped to this instrument}
    reb: dict | None = None        # caption-gap L5 nwog_rebalanced: {(high, low): (known_time, near_edge, exit_edge)} of the rebalanced NWOGs
    daily_all: dict | None = None  # caption-gap pass day_week_context#1/3 (season_min_rank): {date: RTH close} of every session (run_day reads prior years only)


def prepare(df: pd.DataFrame, tf: int, symbol: str = "SPY", p: Params | None = None,
            partial_last: bool = False, bias_table: pd.DataFrame | None = None,
            confluence: bool = True, meta: pd.DataFrame | None = None,
            lock_cuts: dict | None = None, ref_df: pd.DataFrame | None = None, wk_joint: dict | None = None) -> Prepared:
    p = resolve_session_close(p or Params(), df, symbol)        # owner #1: 16:15 futures, 16:00 SPY
    ov = htf.has_overnight(df)
    p = series_fallback(p, symbol, meta)
    inert = meta is None or p.price_frame == "back_adjusted"
    if p.round_pools and symbol.upper() in ROUND_STEP and inert and p.price_frame != "raw":
        warnings.warn(f"#13: round_pools is on but inert for {symbol} (price_frame={p.price_frame!r}, "
                      f"meta {'missing' if meta is None else 'given'}): no front-month mapping",
                      stacklevel=3)
    if p.wk_dc_joint and wk_joint is None and "wk_dc" in p.flip_triggers:
        warnings.warn("wk_dc_joint is on but no partner-index flag map was given (backtest.run builds it from the partner frame): the wk_dc -1 flip runs unrestricted", stacklevel=3)     # caption-gap BH-B8-weekly-ith-both-indices-close (review round 1)
    raw_, adj_ = raw_series(p, symbol, tf, meta, df) if ov else (None, None)          # caption-gap OT-htf-array-data-series (bias_htf#7/7)
    bt = bias_table if bias_table is not None else (
        htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, wk_joint=wk_joint, **table_kw(p, raw_, adj_)) if ov else None)
    cuts = lock_cuts if lock_cuts is not None else lock_tables(df, p, bt, wk_joint, raw_, adj_)
    og = htf.opening_gaps(df, p.es_pt, 1.0, p.nwog_cfd_src, p.gap_views, p.org_close or p.session_close or 960) if ov else None   # (gap_views "both": + the RTH weekend gap)
    reb = htf.nwog_rebalanced(df, og, p.tick) if (ov and p.nwog_rebalanced) else None       # caption-gap L5 nwog_rebalanced
    tt = df.index.hour * 60 + df.index.minute
    pre = df[(tt >= 570) & (tt < (p.org_close or p.session_close or 960))]   # L7: per symbol
    closes = pre.groupby(pre.index.date).close.last().to_dict()     # ORG close per day
    cf = None
    if confluence and ov:
        from .confluence import Confluence
        cf = Confluence(df, tf, p.es_pt, vi=p.vi_arrays, breakers=p.conf_breakers, **htf_kw(p),
                        **({"ob_anchor": "open"} if p.htf_ob_anchor == "open" else {}))      # (caption-gap A12-ob-anchor-level)
    ds = days(df, tf, partial_last, p.session_close)
    eth = None
    ipda_on = p.ipda_pools or p.ipda_next or p.ipda_eq_day != "off"
    if (p.pd_hl_session == "eth" or p.matrix_full or p.wick_session == "eth" or p.pw_pm_full_session
            or (ipda_on and p.ipda_session == "eth") or (p.ma_deuce and p.md_eth) or p.week_pools
            or p.tgif_zone or p.dw_needs_eth):   # M15 md_eth (review fix); M14.2 the weekly range from Sunday 18:00; day_week_context
        se = htf.sessions(df)                  # full sessions (evening reopen -> close), by trading date
        eth = {t.date(): (float(r.open), float(r.high), float(r.low), float(r.close)) for t, r in se.iterrows()}
    eve = evenings(df) if (ov and p.dw_needs_eve) else None
    mm = None
    if p.bias_open_src == "es_map":
        if ref_df is None:
            warnings.warn("bias_open_src='es_map' needs a futures / CFD frame (prepare(ref_df=...)): the frame's own midnight is used")
        else:
            from .levels import map_midnight
            mm = map_midnight(ref_df, df)
    da = {g.index[0].date(): float(rth(g).close.iloc[-1]) for g in ds} if p.season_min_rank > 0 else None
    return Prepared(p, df, tf, symbol, ds, bt, cuts, og, closes, cf, meta, eth, eve, mm, reb, da)


def evenings(df: pd.DataFrame) -> dict:
    """{date: (open, high, low, close)} of the evening session (18:00-24:00) BEFORE each date: the Sunday 18:00 reopen
    for a Monday (B16 Sunday scenarios, N9.2 eve draw, on_range_from="globex")."""
    t = df.index
    ev = df[t.hour >= 18]
    if not len(ev):
        return {}
    lab = (ev.index.normalize() + pd.Timedelta(days=1)).date
    g = ev.groupby(lab)
    return {d: (float(o), float(h), float(l), float(c)) for d, o, h, l, c in
            zip(g.open.first().index, g.open.first(), g.high.max(), g.low.min(), g.close.last())}


def week_state(rows: list, d) -> dict:
    """The week's trade state before day d from the trade rows so far: n trades, net P&L, how many hit their last
    target (final_hit) and whether every one did (X15 / D19 weekly budget, N10.4 friday_week_done="trades")."""
    wk = d.isocalendar()[:2]
    mine = [r for r in rows if r["date"].isocalendar()[:2] == wk and r["date"] < d]
    fh = sum(1 for r in mine if r.get("final_hit"))
    out = dict(n=len(mine), net=float(sum(r["net"] for r in mine)), final_hits=fh, all_final=bool(mine) and fh == len(mine))
    if any("flat_week" in str(r.get("exit_reason", "")) for r in mine):
        out["flat_done"] = True                                  # caption-gap new-late-week-close-flat (cc02_005 ~00:08:05): a recovery re-entry closed the week flat - no more trades this week
    if any("htf_stall" in str(r.get("exit_reason", "")) for r in mine):
        out["reversal_watch"] = _ME2.week_watch(rows, d)         # caption-gap X8-profitable-stall-exit (cc07_007 ~00:22:33): the directions with no new setup the session after an htf_stall exit
    return out


def day_kwargs(pr: Prepared, k: int, equity: float | None = None, intermarket: dict | None = None,
               week: dict | None = None) -> dict:
    """run_day inputs for day k of pr.ds (the partner / log / locks plumbing is the caller's)."""
    p, g = pr.p, pr.ds[k]
    d = g.index[0].date()
    return dict(df=g, hist=[rth(x) for x in pr.ds[max(0, k - hist_days(p)):k]], symbol=pr.symbol, p=p, tf=pr.tf,
                bias=pr.bt.loc[d].to_dict() if pr.bt is not None and d in pr.bt.index else None,
                conf=pr.cf,
                gaps=htf.gaps_for_day(pr.og, d, p.nwog_keep, p.nwog_days, p.nwog_skip_holiday,
                                      p.nwog_trading_days, reb=pr.reb, holiday_pick=p.nwog_holiday_pick,
                                      ref_px=float(g.open.iloc[0])) if pr.og is not None else None,
                prev_full=pr.ds[k - 1] if (k > 0 and (p.prev_london_pool or p.london_lr_zone != "off" or p.prev_eq_long or p.entry_pd_frame != "leg")) else None,
                eth=pr.eth,
                closes=pr.closes, evening=_evening(pr.df, d) if p.globex_pool else None,
                intermarket=({**(intermarket or {}), "ext_midnight": pr.midnight_map[d]}
                             if pr.midnight_map and d in pr.midnight_map else intermarket), equity=equity,
                bias_by_cut={m: t_.loc[d].to_dict() for m, t_ in pr.cuts.items() if d in t_.index},
                meta=pr.meta, week=week, eve=(pr.eve or {}).get(d),
                post_eve=_SM4.post_evening(pr.df, d) if p.asia_session else None,
                daily_all=pr.daily_all)


def run(df: pd.DataFrame, tf: int, symbol: str = "SPY", p: Params | None = None,
        partner: pd.DataFrame | None = None, warmup: int = 3, partial_last: bool = False,
        bias_table: pd.DataFrame | None = None, confluence: bool = True,
        partner2: pd.DataFrame | None = None, intermarket: dict | None = None,
        meta: pd.DataFrame | None = None, lock_cuts: dict | None = None,
        ref_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Backtest one instrument. `meta` (#13): databento meta (load_meta) for the front-month
    price frame; `lock_cuts` (#9): {minute: htf table cut there} (built here when None);
    `ref_df` (D22 bias_open_src="es_map"): the futures / CFD frame whose midnight open is mapped to this instrument.
    The result's attrs carry "days", "locks" (one row per session lock) and "skips"."""
    from . import calendar as _CAL
    _CAL.use((p or Params()).news_cal, (p or Params()).news_cal_path, (p or Params()).gdp_tags)     # coverage gap 1: the event calendar of this run (day lists, skips)
    wk_joint = None
    if (p or Params()).wk_dc_joint and partner is not None and htf.has_overnight(partner):       # caption-gap B8-weekly-ith-both-indices-close: the partner index's weeks decide the joint flag (the partner frame needs overnight bars; without them the flag is False = no wk_dc -1 flip)
        from . import bh1
        wk_joint = bh1.wk_joint_map(df, partner)
    elif (p or Params()).wk_dc_joint:
        wk_joint = {}
    pr = prepare(df, tf, symbol, p, partial_last, bias_table, confluence, meta, lock_cuts, ref_df, wk_joint)
    p, ds = pr.p, pr.ds
    dsmt = None
    from . import bh3 as _bh3                          # caption-gap pass bias_htf#3/7: the SMT also qualifies the seasonal windows, composes the weekly / daily checklists, sets the fall-low and poised maps
    fall_low = poised = None
    if (p.dsmt_bias or _bh3.needs_dsmt(p)) and partner is not None:           # caption-gap B18-htf-daily-smt (bias_htf#2/7): the daily ES / NQ SMT of the two frames (known before each session), passed to run_day with the intermarket values
        from . import bh2
        dsmt = bh2.dsmt_map(df, partner, p.dsmt_days, float(p.event_wick_mult) if p.event_wick_ignore else None)
        if p.fall_low_bias:
            fall_low = _bh3.fall_low_map(df, partner, dsmt)
        if p.season_poised:
            poised = _bh3.poised_map(df, partner, dsmt)
    elif p.dsmt_bias:
        warnings.warn("dsmt_bias is on but backtest.run got no partner frame: the daily SMT bias is inert (B18-htf-daily-smt)", stacklevel=2)
    elif _bh3.needs_dsmt(p):
        warnings.warn("bias_htf#3/7: a switch that reads the daily SMT / the second index is on but backtest.run got no partner frame: its SMT part is inert", stacklevel=2)
    msmt = None
    if p.monthly_ctrl_smt:                             # caption-gap new-monthly-structure-control (bias_htf#5/7): the monthly SMT of the two frames confirms the monthly control
        if partner is not None:
            from . import bh5 as _bh5
            msmt = _bh5.monthly_smt_map(df, partner)
        else:
            warnings.warn("monthly_ctrl_smt is on but backtest.run got no partner frame: the monthly SMT confirmation is inert", stacklevel=2)
    if not p.stock_intraday and str(symbol).upper() not in _DWC3.INDEX_SYMBOLS:
        warnings.warn(f"{symbol}: individual stocks are swing-only (OT-stocks-swing-only, cc10_018 ~33:36) - run_day returns no intraday trades (stock_intraday=True lifts it)", RuntimeWarning, stacklevel=2)
    pmap = {g.index[0].date(): g for g in days(partner, tf, partial_last, p.session_close)} if partner is not None else {}
    pmap2 = {g.index[0].date(): g for g in days(partner2, tf, partial_last, p.session_close)} if partner2 is not None else {}
    locks, skips, objective = [], [], []
    dsum: list = []
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
            wk_ = week_state(rows, d) if p.dw_needs_week else None
            why3 = None
            if _DWC3.needs_week(p):                    # caption-gap pass day_week_context#3/3: the month / week budgets (monthly cap, weekly goal, Friday after a profitable week, August drawdown)
                wk_, why3 = _DWC3.week_extra(wk_, rows, d, p)
                if why3:
                    skips.append((d, symbol, "day_week", why3))
            if why3 is None:
                if p.rr_month_gate:                        # caption-gap new-rr-month-gate (cc02_001 ~12:11): the big winners (>= rr_big R) closed in this calendar month so far
                    wk_ = dict(wk_ or {}, month_big=_TP4.month_big(rows, d, p))
                im_d = (intermarket or INTERMARKET(p.im_source, p.im_bond)).get(d)
                if dsmt is not None:
                    im_d = {**(im_d or {}), "dsmt": dsmt.get(d, 0)}
                if msmt is not None:
                    im_d = {**(im_d or {}), "msmt": msmt.get(d, 0)}
                if fall_low is not None:
                    im_d = {**(im_d or {}), "fall_low": fall_low.get(d, 0)}
                if poised is not None:
                    im_d = {**(im_d or {}), "poised": poised.get(d, 0)}
                kw = day_kwargs(pr, k, eq, im_d, wk_)
                if p.target_stage:                         # caption-gap OT-target-progression (099 ~40:55): the week's staged fixed target (10 -> 15 -> 20); the risk / size never change
                    kw["p"] = _TP4.stage_params(rows, d, kw["p"])
                if p.trader_mode or p.freq_ref > 0:       # caption-gap E8-new-trader-graduation / E9-frequency-small-size: the track record and the last 5 sessions size the day
                    kw["p"] = _ES3.day_params(kw["p"], rows, {x.index[0].date() for x in ds[max(0, k - 5):k]})
                day_trades = run_day(partner=pa, partner2=pa2, locks=locks, skips=skips, risk_state=rs, objective=objective, **kw)
                try:                                       # caption-gap pass day_week_context#2/3 (LLT 63 / 157 / 160, 118, 207): the per-day reporting fields, no trading effect
                    dsum.append(_DWC2.day_summary(g, kw["hist"], p, kw.get("bias"), tf))
                except Exception as e_:                    # a reporting field never stops a backtest, but the failure is not silent
                    warnings.warn(f"day_summary failed on {d}: {e_!r}", RuntimeWarning)
                if p.max_trades_week:                        # X15: the week's budget is applied in ENTRY-time order (run_day did it
                    day_trades = sorted(day_trades, key=lambda t_: t_.entry_time)[:p.max_trades_week - n_wk]   # already; the main loop first, then
                                                             # the Silver Bullet / Ma Deuce: the old slice dropped the earlier trade)
                day_trades = _DWC3.cap_day_trades(day_trades, p, wk_)           # caption-gap X15-monthly-cap: the month's budget in entry-time order
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
        if p.max_exposure_pct:             # caption-gap E11-portfolio-exposure-cap (review fix): the single book honours the cap too (combine re-applies it across instruments)
            attrs = dict(out.attrs)
            out = _ES3.exposure_filter(out, p.max_exposure_pct)
            out.attrs.update(attrs)
    out.attrs["locks"] = locks
    out.attrs["skips"] = skips
    out.attrs["day_summary"] = dsum
    if objective:                          # D15 laggard_objective: the per-day, per-instrument draw-met moments (also for days without a trade)
        out.attrs["objective_met"] = {(r["date"], r["symbol"]): r["t"] for r in objective}
    return out


_IM: dict = {}


def _im_close(name: str, source: str, bond: str) -> pd.Series | None:
    """Daily closes indexed by date: 'DXY' / 'TNX' from the Databento futures (im_source="databento": DX, and the `bond`
    futures inverted to a yield direction) or from the Yahoo files; 'GSPC' always from Yahoo."""
    if source == "databento" and name in ("DXY", "TNX"):
        from .databento_extra import intermarket_daily
        f = intermarket_daily(name, bond)
        return None if f is None else f.close.dropna()
    f = DATA / "yahoo" / f"{name}_1d.csv"
    if not f.exists():
        return None
    s = pd.read_csv(f, index_col=0)
    s.columns = [c.lower() for c in s.columns]
    c = pd.to_numeric(s["close"], errors="coerce")
    c.index = pd.to_datetime(c.index.str[:10])
    return c                                     # (NaN rows kept: the yahoo path computes exactly as before)


def INTERMARKET(source: str = "databento", bond: str = "ZN") -> dict:
    """date -> {"dxy": +1/-1, "tnx": +1/-1, ...}: the prior day's close vs its 20-day mean for the dollar index and the
    10-year yield. Source (Params.im_source): "databento" = DX futures (2019 onward) and the ZN / ZB futures inverted to a
    yield direction (2016 onward), see databento_extra.py; "yahoo" = the free daily DXY / ^TNX files (data/mentorship/yahoo)."""
    key = (source, bond)
    if key not in _IM:
        im = _IM[key] = {}
        cols = {}
        ser = {}
        for n_, f_ in (("dxy", "DXY"), ("tnx", "TNX"), ("spx", "GSPC")):
            c = _im_close(f_, source, bond)
            if c is None or not len(c):
                continue
            if n_ != "spx":
                cols[n_] = np.sign(c - c.rolling(20).mean()).shift(1)   # prior day only
            ser[n_] = c.dropna()
        if cols:
            t = pd.DataFrame(cols).dropna(how="all")
            full = pd.date_range(t.index[0], t.index[-1] + pd.Timedelta(days=3))
            t = t.reindex(full).ffill()
            im.update({k.date(): {c: (0 if pd.isna(v) else int(v)) for c, v in r.items()}
                       for k, r in t.iterrows()})
            try:                                    # caption-gap bias_htf#2/7 (NEW-rates-dxy-fx-direction, B19-bond-stock-dxy-sign, B19-four-asset-risk-map): the slow yield side, the correlations, the S&P trend
                from . import bh2
                ex = bh2.im_columns(ser.get("dxy"), ser.get("tnx"), ser.get("spx"))
                from . import bh3                    # caption-gap bias_htf#3/7: notes_dxy, the trend ratios, bond_lt
                ex3 = bh3.im3_columns(ser.get("dxy"), ser.get("tnx"))
                if len(ex3):
                    ex = ex3 if not len(ex) else pd.concat([ex, ex3], axis=1)
                if len(ex):
                    ex = ex.reindex(full).ffill()
                    for k_, r_ in ex.iterrows():
                        dd = im.setdefault(k_.date(), {})
                        for c_, v_ in r_.items():
                            if isinstance(v_, str):
                                dd[c_] = v_
                            elif not pd.isna(v_):
                                dd[c_] = int(v_) if c_ in ("tnx_slow", "rates_dxy_agree", "spx20", "bond_lt") else float(v_)
            except Exception as e_:                  # the extra columns are tags: a failure never stops the base intermarket values
                warnings.warn(f"INTERMARKET extras failed: {e_!r}", RuntimeWarning)
    return _IM[key]


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
    out = {"trades": int(len(t)), "win_rate": round(float((t.net > 0).mean()), 3),
           "profit_factor": round(float(wins / losses), 2) if losses else float("inf"),
           "avg_R": round(float(t.R.mean()), 3), "net": round(float(t.net.sum()), 2),
           "gross": round(float(t.gross.sum()), 2), "costs": round(float(t.costs.sum()), 2),
           "max_dd": round(dd, 2), "max_dd_pct": round(100 * dd / account, 2)}
    out.update(acceptance(t, account))
    return out


def acceptance(t: pd.DataFrame, account: float = 100_000.0) -> dict:
    """OT-backtest-acceptance (cc02_004 ~00:19:52; cc05_013 ~00:02:17): avg_win_R, avg_loss_R, expectancy_R (= mean R = p * avg_win_R + (1 - p) * avg_loss_R), R_per_month (sum R / the distinct
    months traded), ann_ret_pct (the mean over calendar years of the year's net in % of the account), ann_dd_pct_max (the largest within-year max drawdown in % of the account, reset each
    1 January) and accept: "reject" when expectancy_R <= 0 or ann_dd_pct_max > ACCEPT["dd_max"], "tolerable" above ACCEPT["dd_ok"], else "ok". Reporting only; the trades are unchanged."""
    R = pd.to_numeric(t.R, errors="coerce")
    ts = pd.to_datetime(t.entry_time.astype(str).str[:10] if "entry_time" in t else t.date.astype(str).str[:10])
    win, los = R[t.net > 0], R[t.net <= 0]
    exp = float(R.mean())
    months = ts.dt.strftime("%Y-%m").nunique()
    order = np.argsort(ts.values, kind="stable")
    net = t.net.values[order]
    yrs = ts.dt.year.values[order]
    ann, ddy = [], []
    for y in sorted(set(yrs)):
        n_y = net[yrs == y]
        e_y = np.cumsum(n_y)
        ann.append(float(n_y.sum()) / account * 100.0)
        ddy.append(float((np.maximum.accumulate(np.maximum(e_y, 0.0)) - e_y).max()) / account * 100.0)
    dd_pct = max(ddy) if ddy else 0.0
    accept = "reject" if (exp <= 0 or dd_pct > ACCEPT["dd_max"]) else ("tolerable" if dd_pct > ACCEPT["dd_ok"] else "ok")
    return {"avg_win_R": round(float(win.mean()), 3) if len(win) else 0.0, "avg_loss_R": round(float(los.mean()), 3) if len(los) else 0.0,
            "expectancy_R": round(exp, 3), "R_per_month": round(float(R.sum()) / months, 3) if months else 0.0,
            "ann_ret_pct": round(float(np.mean(ann)), 2) if ann else 0.0, "ann_dd_pct_max": round(dd_pct, 2), "accept": accept}


def report(t: pd.DataFrame) -> dict:
    out = {"all": stats(t)}
    if not len(t):
        return out
    for col in ("setup", "side", "day_type", "unicorn", "unicorn_side", "lh_sweet", "capped", "lock_capped",
                "sloppy", "draw_side", "entry_kind", "smt", "swept", "exit_reason", "wk_profile"):
        if col not in t:
            continue
        out[f"by_{col}"] = {str(k): stats(g) for k, g in t.groupby(t[col].astype(str))}
    if "capture" in t and t.capture.notna().any():        # X3h: the share of the best-case run the exits took
        c = t.capture.dropna()
        w = c[t.loc[c.index, "net"] > 0]
        out["capture"] = {"trades": int(len(c)), "mean": round(float(c.mean()), 3),
                          "winners_mean": round(float(w.mean()), 3) if len(w) else None,
                          "winners_median": round(float(w.median()), 3) if len(w) else None}
    if t.attrs.get("day_summary"):        # caption-gap pass day_week_context#2/3: PDH / PDL touch rate, 5-handle legs, the ADR fib close zone
        out["day_summary"] = _DWC2.summary_stats(t.attrs["day_summary"])
    if "dw_tags" in t:                    # caption-gap pass day_week_context#1/3 (B23 "no map, tag or report"): the seasonal / week-template tags, one row per tag
        ex = t.assign(_tag=t.dw_tags.fillna("").astype(str).str.split("|")).explode("_tag")
        ex = ex[ex._tag.str.startswith(DW1_REPORT_TAGS)]
        if len(ex):
            out["by_dw_tag"] = {str(k): stats(g.drop(columns="_tag")) for k, g in ex.groupby("_tag")}
    out.update(_DWC3.journal_report(t))   # caption-gap OT-X16-time-to-move-journal: by_pre_fomc and the time-to-move medians (only when journal_timing filled the columns)
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


DW1_REPORT_TAGS = ("season_", "win_", "regime_", "sr_", "nwog_", "profile_", "wk_profile_", "mon_how", "wk_push_range", "iw_reversal", "one_sided", "mo_overdue", "pre_cpi_mon", "day4",
                   "august_mode", "macro_risk", "sd_intraday", "post_holiday_trigger",      # day_week_context#1/3 tags reported by report()
                   "expansion_candidate", "thu_reversal", "wk_ext_candidate", "adr_contracted", "adr_filled_news", "late_week", "wk_reversal_flag", "consol_mode_", "trend_side_",
                   "wed_low", "wed_high", "wed_week_extreme", "mon_big", "tgif_fvg_cap", "thu_rev_setup")      # day_week_context#2/3 tags


CONSOL_MARKS = ("consol_", "daily_range", "inside_day", "big_prev", "inside_week", "bh_nwog_cons", "bh_bond_range", "bh_chop",
                "low_vol")


def consolidation_day(row) -> bool:
    """D15: a trade's day is a consolidation day when its day tags (strategy.day_context: inside_day, big_prev ...) or the DayPlan
    tags (dw_tags: consol_*, daily_range, inside_week, bias_htf nwog_cons / bond_range / chop ...) name one."""
    s = f"{row.get('day_tags', '')}|{row.get('dw_tags', '')}"
    et = pd.Timestamp(row.get("entry_time")) if row.get("entry_time") is not None else None
    marks = CONSOL_MARKS
    if et is not None and et == et and et.hour * 60 + et.minute < 570:
        # (review fix) the bias_htf day tags are put on the DayPlan from the 09:30 row (overnight range, 09:30 price): a fill before
        # 09:30 must not be classified with information through 09:30
        marks = tuple(m for m in marks if m not in ("bh_nwog_cons", "bh_bond_range", "bh_chop"))
    return any(m in s for m in marks)


ES_SYMBOLS = ("ES", "MES")           # D15 pick="fixed_es" (cc10_012 / cc10_014: the crack in any index signals the trade in ES)


def _met_map(runs, t: pd.DataFrame) -> dict | None:
    """{(date, symbol): the moment that instrument's own draw was met (None = not met)} from the runs' `attrs["objective_met"]` (backtest.run: engine level,
    days without a trade included) and the trades' `obj_met_t` column; None when neither exists (hand-made books: the trade-outcome fallback)."""
    m = {}
    have = False
    for r in runs:
        om = getattr(r, "attrs", {}).get("objective_met")
        if om is not None:
            have = True
            m.update(om)
    if "obj_met_t" in t.columns:
        have = True
        for (d, s), g in t.groupby(["date", "symbol"]):
            v = g.obj_met_t.dropna()
            if len(v) and (d, s) not in m:
                m[(d, s)] = v.iloc[0]
    return m if have else None


def objective_met_filter(t: pd.DataFrame, consol_only: bool = False, met: dict | None = None) -> pd.DataFrame:
    """BH-D15-sick-sister-laggard (056 ~9:10; 070 ~18:41; 099 ~26:53): once one instrument's objective is met - the draw of its OWN htf.table row traded
    since it was formed, computed inside `run_day` per instrument (`sm2.objective_record`, `met` = {(date, symbol): moment}) - its own later fills go
    (a fill at or after the moment) and only the instruments that have NOT met theirs keep trading (the 'sick sister', routed to its own analogous
    target). Fills before the moment are untouched (a past moment at every later entry: causal). `consol_only` (the 053 statement, D15 option B's narrow
    form): only on consolidation days (`consolidation_day`); every other day keeps all fills, ready for the plain first-fill pick.
    Without `met` (hand-made books) the old read from the trades is the fallback: an instrument's objective counts as met when one of its trades reached
    its last ladder level (`final_hit`) and exited at T."""
    if not {"exit_time", "symbol", "entry_time"} <= set(t.columns) or not len(t):
        return t
    keep = pd.Series(True, index=t.index)
    if met is not None:
        for d, day in t.groupby("date"):
            if consol_only and not day.apply(consolidation_day, axis=1).any():
                continue
            for sym, g in day.groupby("symbol"):
                T = met.get((d, sym))
                if T is not None and T == T:
                    keep.loc[g[g.entry_time >= T].index] = False
        return t[keep]
    if "final_hit" not in t.columns:
        return t
    done = t[t.final_hit.eq(True) & t.exit_time.notna()]
    for d, g in done.groupby("date"):
        day = t[t.date == d]
        if consol_only and not day.apply(consolidation_day, axis=1).any():
            continue
        first = g.sort_values("exit_time", kind="stable").iloc[0]
        late = day.entry_time >= first.exit_time
        keep.loc[day[late & (day.symbol == first.symbol)].index] = False
        keep.loc[day[late & (day.symbol != first.symbol)].index] = True
    return t[keep]


def laggard_draw_tag(t: pd.DataFrame, met: dict | None = None) -> pd.DataFrame:
    """new-laggard-slow-delivery: column `laggard_draw` = another instrument's draw was already met (moment <= this fill's entry_time) the same day. `met` = {(date, symbol): moment}; without it the
    final_hit / exit_time of the books' own trades are read."""
    t = t.copy()
    t["laggard_draw"] = False
    if not len(t) or not {"date", "symbol", "entry_time"} <= set(t.columns):
        return t
    moments: dict = {}
    if met is not None:
        moments = {k: v for k, v in met.items() if v is not None and v == v}
    elif {"final_hit", "exit_time"} <= set(t.columns):
        for (d, s), g in t[t.final_hit.eq(True) & t.exit_time.notna()].groupby(["date", "symbol"]):
            moments[(d, s)] = g.exit_time.min()
    for i, r in t.iterrows():
        t.at[i, "laggard_draw"] = any(d == r["date"] and s != r["symbol"] and T <= r["entry_time"] for (d, s), T in moments.items())
    return t


def _fixed_es(t: pd.DataFrame) -> pd.DataFrame:
    """BH D15-which-index-contradiction: only ES fills stay; an ES fill is SMT-qualified when EITHER instrument's SMT tag of its slot (date + session)
    shows a divergence at the sweep (the other index's tag counts: the crack in any index signals the trade in ES)."""
    if "smt" not in t.columns:
        return t[t.symbol.isin(ES_SYMBOLS)]
    div = t.assign(_d=t.smt.eq(True)).groupby(["date", "_sk"])._d.transform("any")
    t = t.assign(smt=t.smt.where(~div, True).astype(object))
    return t[t.symbol.isin(ES_SYMBOLS)]


def _group_pick(t: pd.DataFrame, pick: str) -> pd.DataFrame:
    """D15 picks that choose among the instruments' fills of one slot (date + session): "middle" (the middle of three by `move_pct`, the move from the
    session open in the trade direction; a slot without three instruments' fills keeps the first), "clean_swing" (a fill with a 15m pivot between its
    entry and T1; none = the first), "depth" (the larger `array_depth`, ties by `array_respect`, then the earlier fill)."""
    rows = []
    t = t.sort_values("entry_time", kind="stable")
    for _, g in t.groupby(["date", "_sk"], sort=False):
        if pick == "middle":
            gg = g.drop_duplicates("symbol")
            if len(gg) >= 3 and "move_pct" in gg and gg.move_pct.notna().all():
                r = gg.sort_values("move_pct", kind="stable").iloc[len(gg) // 2]
            else:
                r = g.iloc[0]
        elif pick == "clean_swing":
            c = g[g.clean_swing.eq(True)] if "clean_swing" in g else g.iloc[:0]
            r = (c if len(c) else g).iloc[0]
        elif pick == "clean":                       # caption-gap D15-one-clean-gap-instrument (061 ~01:49:01): the fill whose area is ONE clean gap (gap_count == 1), else the first
            c = g[g.gap_count.eq(1)] if "gap_count" in g else g.iloc[:0]
            r = (c if len(c) else g).iloc[0]
        else:
            if "array_depth" not in g or g.array_depth.isna().all():
                r = g.iloc[0]
            else:
                gg = g.assign(_d=g.array_depth.fillna(-1.0), _r=(g.array_respect.fillna(-1.0) if "array_respect" in g else -1.0))
                r = gg.sort_values(["_d", "_r", "entry_time"], ascending=[False, False, True], kind="stable").iloc[0]
        rows.append(r)
    if not rows:
        return t.iloc[:0]
    out = pd.DataFrame(rows)
    return out.drop(columns=[c for c in ("_d", "_r") if c in out.columns]).sort_values("entry_time")


def combine(*runs: pd.DataFrame, pick: str = "first", one_market: bool = False, sb_one_market: bool = False,
            sb_am_done: bool = False, laggard_consol_only: bool = False, dual_deal: str = "", exec_exclude: tuple = ("YM",), prefer: str = "none",
            max_exec: int = 2, max_exposure_pct: float = 0.0, laggard_tag: bool = False) -> pd.DataFrame:
    """Caption-gap new-laggard-slow-delivery (090 ~01:49:28; management_exits #3/3): `laggard_tag` adds the column `laggard_draw` - True on a fill taken at or after the moment ANOTHER instrument's own draw was met
    (the real-draw read of `_met_map`; the final_hit/exit_time read for hand-made books). REPORT ONLY (the in-run `Trade.laggard` flag, which drives the longer time-stop window, is the engine proxy).
    Caption-gap OT-D15-default-instrument / OT-max-two-correlated-markets (028 ~00:23:58; 055 ~00:27:38; setups_models #7/7): `exec_exclude` (Params.combine_exec_exclude, default ("YM",)) = the
    symbols that are never EXECUTED - their rows are dropped before the pick (YM is the Dow: a reference for SMT only, it already enters as partner2 / smt2, so the bot's trades do not change; the
    "middle" pick, which ranks all three indices, drops them AFTER the pick); `prefer` (Params.combine_prefer) "es" = on a same-bar tie (same entry_time) keep the S&P row (ES / SPX / SPY) over
    the Nasdaq one (NQ / NDX / QQQ), ahead of the weak / relative-leg tie-break; `max_exec` (Params.max_exec_markets, default 2): at most two execution symbols may remain and, with two, they must be
    one S&P and one Nasdaq instrument (watch two CLOSELY CORRELATED indices, never add markets to find setups) - otherwise ValueError (0 = no cap).
    Caption-gap D15-dual-dealing (069 ~00:19:09; setups_models #5/7): `dual_deal` "" (the default) = the one-instrument-per-session pick below; "split" / "full" = when BOTH instruments (two or more
    symbols) filled the same side in the same session slot of one day (the same Judas / MSS / FVG window on ES and NQ), keep every one of those trades instead of the pick - "split" at HALF risk each
    (gross / costs / net / risk columns x 0.5, column dual_risk 0.5), "full" at full risk (dual_risk 1.0); everything else goes through the ordinary pick. ICT states neither the conditions nor the
    allocation: the two variants are the test. Conflicts with Ep 05 "watch one market only" and with D15.
    POST-HOC APPROXIMATION (review note): "split" is decided AFTER the books are finished - a trade is halved once the other symbol is seen filling the same date / slot / side, which at the first
    fill's entry time is not yet knowable (and the slot is the date / session / side, not the same entry window). The dual rows carry `dual_alloc` = "posthoc" and the result must be read as an
    allocation study, not a causal live rule; the engine does not size a second leg (owner question).
    """
    if prefer not in ("none", "es"):
        raise ValueError(f"prefer {prefer!r}: expected 'none' or 'es'")
    kw = dict(pick=pick, one_market=one_market, sb_one_market=sb_one_market, sb_am_done=sb_am_done, laggard_consol_only=laggard_consol_only, exec_exclude=tuple(exec_exclude), prefer=prefer,
              max_exec=int(max_exec))
    out = _combine_dual(runs, dual_deal, kw) if dual_deal else _combine(*runs, **kw)
    if laggard_tag:
        out = laggard_draw_tag(out, _met_map(runs, out))
    return _ES3.exposure_filter(out, max_exposure_pct) if max_exposure_pct else out       # caption-gap E11-portfolio-exposure-cap (Params.max_exposure_pct): open risk of all concurrent trades + the new one <= the cap


SPX_SYMS = frozenset({"ES", "SPX", "SPY", "MES"})           # the S&P instruments (OT-max-two-correlated-markets)
NDX_SYMS = frozenset({"NQ", "NDX", "QQQ", "MNQ"})           # the Nasdaq instruments


def _index_of(sym: str) -> str:
    s = str(sym).upper()
    return "spx" if s in SPX_SYMS else ("ndx" if s in NDX_SYMS else s)


def exec_cap(symbols, max_exec: int) -> None:
    """OT-max-two-correlated-markets (Ep05 / 055 ~00:27:38): at most `max_exec` execution symbols, and two only when they are one S&P and one Nasdaq instrument. ValueError otherwise."""
    syms = sorted({str(s) for s in symbols})
    if not max_exec or len(syms) <= 1:
        return
    if len(syms) > max_exec:
        raise ValueError(f"execution symbols {syms}: at most {max_exec} closely correlated markets (ES + NQ); never add markets to find setups")
    if {_index_of(s) for s in syms} != {"spx", "ndx"}:
        raise ValueError(f"execution symbols {syms}: two markets must be one S&P and one Nasdaq instrument (closely correlated), not the same index twice")


def _slot(r: pd.DataFrame) -> pd.Series:
    """The session slot of a book's trades (a Silver Bullet window is its own slot, as in combine)."""
    if "setup" not in r.columns:
        return r.session
    return r.session.where(~r.setup.astype(str).str.startswith("sb_"), r.setup)


def _combine_dual(runs, mode: str, kw: dict) -> pd.DataFrame:
    if mode not in ("split", "full"):
        raise ValueError(f"dual_deal {mode!r}: expected '', 'split' or 'full'")
    books = [r for r in runs if len(r)]
    if not books:
        return runs[0] if runs else pd.DataFrame()
    excl = set(kw.get("exec_exclude") or ())
    exec_cap([s_ for r in books for s_ in r.symbol.unique() if s_ not in excl], kw.get("max_exec", 0))       # review fix: the two-market cap sees the dual rows too
    books = [r[~r.symbol.isin(excl)] if excl else r for r in books]                                           # ... and a never-executed symbol (YM) is not a second market of a dual slot
    books = [r for r in books if len(r)]
    if not books:
        return _combine(*runs, **kw)
    keys = pd.concat([pd.DataFrame({"date": r.date.values, "slot": _slot(r).values, "side": r.side.values, "symbol": r.symbol.values}) for r in books], ignore_index=True)
    multi = set(map(tuple, keys.groupby(["date", "slot", "side"]).symbol.nunique().loc[lambda x: x >= 2].index))
    rest, dual = [], []
    for r in runs:
        if not len(r):
            rest.append(r)
            continue
        m = pd.Series([(d, sl, sd) in multi and sy not in excl for d, sl, sd, sy in zip(r.date, _slot(r), r.side, r.symbol)], index=r.index)
        rest.append(r[~m])
        dual.append(r[m])
    out = _combine(*rest, **kw) if any(len(r) for r in rest) else (rest[0] if rest else pd.DataFrame())
    d = pd.concat([x for x in dual if len(x)], ignore_index=True) if any(len(x) for x in dual) else None
    if d is None:
        return out.assign(dual_risk=1.0) if len(out) else out
    f = 0.5 if mode == "split" else 1.0
    for col in ("gross", "costs", "net", "entry_risk_pct", "peak_risk_pct"):
        if col in d.columns and f != 1.0:
            d[col] = d[col] * f
    d["dual_risk"] = f
    d["dual_alloc"] = "posthoc"
    out = out.assign(dual_risk=1.0) if len(out) else out
    res = pd.concat([x for x in (out, d) if len(x)], ignore_index=True)
    return res.sort_values("entry_time", kind="stable").reset_index(drop=True) if "entry_time" in res.columns else res


def _combine(*runs: pd.DataFrame, pick: str = "first", one_market: bool = False, sb_one_market: bool = False,
             sb_am_done: bool = False, laggard_consol_only: bool = False, exec_exclude: tuple = (), prefer: str = "none", max_exec: int = 0) -> pd.DataFrame:
    """Trade one instrument per session (watch one market, rules Ep 05): of the setups the
    instruments produced, keep the first to fill. On a tie, keep the one whose SMT check
    didn't show its partner holding stronger. Uses only what was known at the fill.
    setups_models Ep03.11 / D15 `pick` (Params.smt_pick): "leader" keeps only fills whose own SMT
    check did NOT show the sister holding stronger (smt is not True: this index made the cleaner
    extreme, 003); "laggard" only those where it did (the sick sister, 045 / 053). Each fill's
    smt tag is known at its sweep, so skipping one instrument's fills is causal. Same-bar ties:
    the larger (leader) / smaller (laggard) relative leg (leg_hi_px - ext_px) / ext_px.
    bias_htf D15: pick="trend" = "leader" on trend days and "laggard" on consolidation days (ICT's reconciliation: the sick sister
    only in consolidation, 053 ~08:20; consolidation_day reads the trades' day tags); one_market=True (Ep 05 "watch one market
    only"): once the day's first fill is chosen, the other instrument's trades of that date are dropped.
    Caption-gap pass (setups_models #1/7) D15 picks: "laggard_objective" (once an instrument's objective is met - a trade reached its last ladder
    level - only the other, unmet instrument's later fills stay; `laggard_consol_only`: only on consolidation days), "middle" (three runs: the
    instrument whose move from the session open to the fill is the middle one; fewer than three runs raise ValueError), "clean_swing" (the fill with a
    15m pivot between its entry and T1), "depth" (the fill that ran deeper into its HTF array), "swept" (= "laggard": the index whose sweep made the
    new extreme, cc10_011), "fixed_es" (only ES fills; SMT-qualified when either instrument's tag diverged at that slot, cc10_012 / cc10_014)."""
    if pick not in SMT_PICKS:
        raise ValueError(f"pick {pick!r}")
    if pick == "middle" and len(runs) < 3:
        raise ValueError("pick 'middle' needs three runs (ES / NQ / YM): rank the instruments by their move and keep the middle one")
    t = pd.concat([r for r in runs if len(r)], ignore_index=True)
    if not len(t):
        return t
    if "symbol" in t.columns:
        if exec_exclude and pick != "middle":
            t = t[~t.symbol.isin(exec_exclude)]            # OT-D15-default-instrument: YM (the Dow) is a reference only - never executed
            if not len(t):
                return t
        exec_cap([s_ for s_ in t.symbol.unique() if s_ not in exec_exclude], max_exec)       # OT-max-two-correlated-markets
        if prefer == "es":
            t = t.assign(_pref=t.symbol.map(lambda s_: 1 if _index_of(s_) == "ndx" else 0))
    out = None
    # SB package (M3.9): a Silver Bullet window is its own slot - the key was (date, session), so an SB trade of the
    # London / AM window (session "AM") shut the main engine's AM trade of the other market out and vice versa.
    # sb_one_market (046 ~55:21: don't switch markets): later SB windows keep only the first SB trade's market.
    # sb_am_done (048 ~1:35): done for the AM once an SB AM trade reached its target: later AM trades of the day go.
    if "setup" not in t.columns:
        t = t.assign(setup="")                        # (hand-made books without the setup column: one slot per session)
    t = t.assign(_sk=t.setup.where(t.setup.astype(str).str.startswith("sb_"), t.session))
    if sb_one_market and t.setup.astype(str).str.startswith("sb_").any():
        sbm = t[t.setup.astype(str).str.startswith("sb_")].sort_values("entry_time").groupby("date").symbol.first()
        keep = ~t.setup.astype(str).str.startswith("sb_") | (t.symbol == t.date.map(sbm))
        t = t[keep]
    if sb_am_done and "exit_time" in t.columns:
        won = t[(t.setup == "sb_am") & t.exit_reason.astype(str).str.contains(r"(?:^|\+)t\d+(?:\+|$)", regex=True)]
        if len(won):
            done = won.groupby("date").exit_time.min()
            later = (t.session == "AM") & (t.setup != "sb_am") & (t.entry_time > t.date.map(done))
            t = t[~later]
    if pick == "laggard_objective":                    # D15 (caption-gap BH-D15-sick-sister-laggard): the unmet instrument after a leader met its objective
        t = objective_met_filter(t, laggard_consol_only, _met_map(runs, t))
        pick = "first"
    elif pick == "swept":                              # D15 (BH D15-which-index-contradiction): the swept index (turtle soup) = the SMT tag True: "laggard"
        pick = "laggard"
    elif pick == "fixed_es":
        t = _fixed_es(t)
        pick = "first"
        if not len(t):
            return t.drop(columns=[c_ for c_ in ("_sk", "_pref") if c_ in t.columns])
    if pick in ("middle", "clean_swing", "depth", "clean"):
        out = _group_pick(t, pick)
        out = out.drop(columns=[c_ for c_ in ("_sk", "_pref") if c_ in out.columns])
        if exec_exclude and pick == "middle" and "symbol" in out.columns:
            out = out[~out.symbol.isin(exec_exclude)]      # the middle index may be the Dow: never executed
    elif pick != "first":
        lag = t.smt.eq(True)
        if pick == "trend":
            cons = t.apply(consolidation_day, axis=1)
            keep = (lag & cons) | (~lag & ~cons)          # laggards on consolidation days, leaders on trend days
            lead_row = ~cons
        else:
            keep = lag if pick == "laggard" else ~lag
            lead_row = pd.Series(pick == "leader", index=t.index)
        t = t[keep]
        lead_row = lead_row[keep]
        if not len(t):
            return t.drop(columns=[c_ for c_ in ("_sk", "_pref") if c_ in t.columns])
        if {"ext_px", "leg_hi_px"} <= set(t.columns):
            rel = ((t.leg_hi_px - t.ext_px).abs() / t.ext_px.abs()).fillna(0.0)
            t = t.assign(_rel=rel.where(~lead_row, -rel)).sort_values((["entry_time", "_pref"] if "_pref" in t.columns else ["entry_time"]) + ["_rel"], kind="stable")
            out = t.groupby(["date", "_sk"], sort=False).head(1).drop(columns=["_rel", "_sk"] + (["_pref"] if "_pref" in t.columns else [])).sort_values("entry_time")
    if out is None:
        t = t.assign(_weak=t.smt.eq(True)).sort_values((["entry_time", "_pref"] if "_pref" in t.columns else ["entry_time"]) + ["_weak"])
        out = t.groupby(["date", "_sk"], sort=False).head(1).drop(columns=["_weak", "_sk"] + (["_pref"] if "_pref" in t.columns else [])).sort_values("entry_time")
    if one_market and len(out):
        first = out.sort_values("entry_time", kind="stable").groupby("date").symbol.first()
        out = out[out.symbol == out.date.map(first)]
    return out
