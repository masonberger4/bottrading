"""Caption-gap pass, package bias_htf#7/7 - TABLE SIDE (digests/rulebook_gaps/models_setups_entries.md items 177, 178, 179, 205, 215 (engine only), other.md item 5, times_sessions_macros.md items 42, 65).

The daily columns the switches of this package need. Everything here is a pure function of COMPLETED sessions (the sessions before the row's day): the row of session k never reads session k's high /
low / close nor an incomplete week, and the 1h reading (h1_sponsor) uses only 1h bars that ended before session k opened. The engine side (the side gates, the AM side inputs, the targets) is `bh7e.py`;
the research-only items of the package are `bh7s.py` / `stocks.py` / `stocks_watch.py`. `bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b7"; `finish7` runs at the
end of `htf.table` (after bh6.finish6). Thresholds the sources never give are marked [our interpretation]; every rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  range_q / range_lo / range_hi   (A21-longs-above-eq-subrange-discount)  the quadrant (1-4) of the prior close in the 60-session BODY range (completed sessions), and the range's body low / high
  flip_turn                       (new-after-of-shift-sell-any-premium-array)  +1 / -1 = the table's stateful bias `flip` turned to that side inside the current week (it differs from the week's first row), else 0
  h1_sponsor                      (B6-intraweek-reversal-1h-confirmation)  Wed-Fri only: +1 once, after a Tue / Wed week low that reacted at a bullish daily / weekly array, a 1h close broke the latest short-term 1h swing
                                  high, kept while every later 1h bullish OB holds (no 1h close under its MT); -1 the bearish mirror; 0 otherwise or after a failed OB
  array_lost / array_lost_tgt     (new-stopout-at-planned-array-next-day-flip)  +1 when yesterday's close went through the nearest daily bullish array under its open (the planned support), -1 the bearish
                                  mirror; the target = the top (bottom) of the next lower (higher) live daily array, NaN without one
  brk_react                       (T13-po3-breaker-regime)  -1 / +1: the side of the last daily breaker price REACTED from (a touch of the zone followed by a daily close away from it), 0 before any (the older
                                  formation-based reading is `brk_regime` of bh4 / `breaker_regime`; this one is read with htf_bias="breaker")
"""
from __future__ import annotations

import dataclasses
import warnings

import numpy as np
import pandas as pd

from . import bh2 as BH2
from . import levels as L

HITS = BH2.HITS
NAN = float("nan")
sw = BH2.sw


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b7" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.pd_subrange:
        c["rq"] = 60
    if p.weekly_flip_follow:
        c["ft"] = 1
    if p.htf_bias == "h1_sponsor":
        c["h1"] = 1
    if p.array_lost_flip:
        c["al"] = 1
    if p.htf_bias == "breaker":
        c["br"] = 1
    if p.true_day == "ipda":
        c["td"] = 1
    if p.htf_series != "adjusted":
        c["hs"] = p.htf_series
    if p.htf_monthly_series == "raw" and (p.htf_monthly or p.htf_monthly_arrays):
        c["ms"] = "raw"
    return c


# --------------------------------------------------------------------------------------------------------------
# new-ipda-true-day: the 00:00-15:00 daily candle
# --------------------------------------------------------------------------------------------------------------

def sessions_true_day(df: pd.DataFrame, end_min: int = 900) -> pd.DataFrame:
    """The IPDA true day (cc08_002 ~00:05:19: 'every day at 3 PM New York time ends the IPDA true day'): per trading date the candle of the bars from 00:00 NY to `end_min` (15:00): open = the first bar at /
    after 00:00, close = the last bar ending at / before 15:00 (the evening reopen 18:00-24:00 belongs to the NEXT date's session and is not part of the candle). A date with fewer than 60 bars of the frame (or
    whose bars are under an hour in total) is dropped like a stub session."""
    from .htf import bar_minutes
    bm = bar_minutes(df)
    t = df.index.hour * 60 + df.index.minute
    sel = df[(t < end_min) & (t + bm <= end_min)]
    g = sel.groupby(sel.index.normalize().tz_localize(None))
    d = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(), "n": g.close.size()})
    d.index = pd.to_datetime(d.index)
    return d[d.n * bm >= 60].drop(columns="n")


# --------------------------------------------------------------------------------------------------------------
# OT-htf-array-data-series: the raw front-month table
# --------------------------------------------------------------------------------------------------------------

def adj_before(adj: pd.Series, day, tz, cut_min: int = 570, bm: int = 1) -> float:
    """The adj (engine - raw) of the last bar that had CLOSED by the row's cut: the bar starting at or before `day` 00:00 + cut_min - bm minutes (the session's 09:30 table cut by default; `bm` = the bar
    length in minutes). 0.0 when the series starts later. No look-ahead: only bars before the cut are read. (The spec says 'before the session'; the cut is the later, equally causal moment at which the
    row's own price is observed, so the mapping of the row's price is exact on a roll day too.)"""
    if adj is None or not len(adj):
        return 0.0
    t0 = pd.Timestamp(day).normalize()
    t0 = t0.tz_localize(None) if t0.tzinfo is not None else t0
    t0 = t0 + pd.Timedelta(minutes=int(cut_min) - int(bm))
    if getattr(adj.index, "tz", None) is not None:
        t0 = pd.Timestamp(t0, tz=adj.index.tz)
    k = int(adj.index.searchsorted(t0, side="right")) - 1
    return float(adj.iloc[k]) if k >= 0 and adj.iloc[k] == adj.iloc[k] else 0.0


def price_like_columns(tbl: pd.DataFrame) -> list:
    """The float columns of an htf table that hold PRICES (the ones that move with the frame): the column median within 25 % of the median `px` [our interpretation: the table has no schema of its price
    columns]."""
    if "px" not in tbl or not len(tbl):
        return []
    ref = float(np.nanmedian(tbl["px"].values.astype(float)))
    out = []
    for c in tbl.columns:
        if c in ("px",) or tbl[c].dtype.kind != "f":
            continue
        v = tbl[c].values.astype(float)
        if np.isfinite(v).any() and ref > 0 and abs(float(np.nanmedian(v)) / ref - 1.0) < 0.25:
            out.append(c)
    return ["px"] + out


def raw_table(table_fn, df: pd.DataFrame, raw: pd.DataFrame, adj: pd.Series, kw: dict, bx: str, X: dict) -> pd.DataFrame:
    """htf_series='raw' (056 ~00:01:13: 'the continuous contract is not going to show you the inefficiencies of the delivery month'): the table built on the unadjusted front-month series `raw` (the
    roll gaps stay in, as on an unadjusted continuous chart) and every price column mapped into the engine frame by adding the adj of the last closed bar before the row's session (engine = raw + adj; the same
    mapping `strategy._round_levels` uses). A level formed before a roll therefore sits (adj_then - adj_now) away from where the adjusted frame draws it; one formed after the last roll is identical."""
    import json
    x = dict(X)
    b7 = dict(x.get("b7") or {})
    b7.pop("hs", None)
    b7.pop("ms", None)                                  # (the monthly arrays of the raw table are raw already)
    x["b7"] = b7
    if not b7:
        x.pop("b7", None)
    bx2 = json.dumps(x, sort_keys=True, separators=(",", ":")) if x else ""
    tbl = table_fn(raw, bx=bx2, raw=None, adj=None, **kw)
    if not len(tbl):
        return tbl
    tz = df.index.tz
    cols = price_like_columns(tbl)
    from .htf import bar_minutes
    cut, bm = int(kw.get("cut_min", 570)), bar_minutes(raw)
    shift = np.array([adj_before(adj, pd.Timestamp(i), tz, cut, bm) for i in tbl.index])
    for c in cols:
        tbl[c] = tbl[c].values.astype(float) + shift
    sw("htf_series_raw")
    tbl["adj_map"] = shift
    return tbl


def shifted(a, adj_k: float):
    """A copy of the array `a` with its levels moved by adj_k (the per-day mapping of a raw-series array into the engine frame)."""
    return dataclasses.replace(a, top=a.top + adj_k, bottom=a.bottom + adj_k, ce=a.ce + adj_k)


def monthly_raw_arrays(raw: pd.DataFrame, d: pd.DataFrame, pos: dict, arrays_fn, known_fn_args) -> list:
    """htf_monthly_series='raw' (078 ~00:35:43: monthly / weekly on the continuous chart): the monthly arrays drawn on the raw front-month series, marked `rawk` so the table maps them per day (shifted)."""
    from .htf import months, sessions
    dr = sessions(raw)
    mth = months(dr)
    if not len(mth):
        return []
    ml = [pos.get(t) for t in mth["last"]]
    keep = [k for k, v in enumerate(ml) if v is not None]
    if len(keep) != len(ml):
        warnings.warn("htf_monthly_series='raw': raw and engine sessions differ; the monthly arrays of unmatched months are dropped", stacklevel=3)
    out = arrays_fn(*(mth[k].values.astype(float) for k in ("open", "high", "low", "close")), "M", lambda i: (ml[i] + 1 if ml[i] is not None else 10 ** 9), *known_fn_args)
    for a in out:
        a.rawk = True
    return out


# --------------------------------------------------------------------------------------------------------------
# A21-longs-above-eq-subrange-discount: range_q
# --------------------------------------------------------------------------------------------------------------

def range_columns(o, c, ks, n: int = 60) -> dict:
    """range_q / range_lo / range_hi per row k: the BODY range (max(open, close) / min(open, close)) of the last n completed sessions k-n .. k-1 and the quadrant (1 = lowest .. 4) of the close of session k-1.
    NaN / 0 with fewer than 10 sessions."""
    nrow = len(ks)
    q = np.zeros(nrow, int)
    lo = np.full(nrow, NAN)
    hi = np.full(nrow, NAN)
    top = np.maximum(o, c)
    bot = np.minimum(o, c)
    for r, k in enumerate(ks):
        k = int(k)
        a = max(0, k - n)
        if k - a < 10:
            continue
        h_, l_ = float(top[a:k].max()), float(bot[a:k].min())
        lo[r], hi[r] = l_, h_
        if h_ > l_:
            q[r] = min(4, int((float(c[k - 1]) - l_) / (h_ - l_) * 4) + 1) if c[k - 1] >= l_ else 1
    return dict(range_q=q, range_lo=lo, range_hi=hi)


def quadrant(price: float, lo: float, hi: float) -> int:
    """The quadrant (1-4, 0 = no range) of `price` in [lo, hi] (below lo = 1, above hi = 4)."""
    if not (lo == lo and hi == hi and hi > lo):
        return 0
    return int(min(4, max(1, int((price - lo) / (hi - lo) * 4) + 1))) if price >= lo else 1


# --------------------------------------------------------------------------------------------------------------
# new-after-of-shift-sell-any-premium-array: flip_turn
# --------------------------------------------------------------------------------------------------------------

def flip_turn_column(flip, ks, d) -> np.ndarray:
    """flip_turn per row: the table's stateful bias `flip` of the row when it differs from the flip of the week's first row and is nonzero (the bias turned INSIDE the week), else 0. The week = the
    W-FRI period of the session label (a holiday week starts at its first session)."""
    fl = np.asarray(flip, int)
    wid = np.asarray(d.index.to_period("W-FRI").astype(str))
    out = np.zeros(len(fl), int)
    r0 = 0
    for r in range(len(fl)):
        if r == 0 or wid[int(ks[r])] != wid[int(ks[r - 1])]:
            r0 = r
        if r != r0 and fl[r] != 0 and fl[r] != fl[r0]:
            out[r] = fl[r]
    return out


# --------------------------------------------------------------------------------------------------------------
# B6-intraweek-reversal-1h-confirmation: h1_sponsor
# --------------------------------------------------------------------------------------------------------------

def h1_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Clock-aligned 1h bars of the minute frame with the time each completes (`end`)."""
    g = df.groupby(df.index.floor("60min"))
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    out["end"] = out.index + pd.Timedelta(minutes=60)
    return out


def sponsor_state(ho, hh, hl, hc, jl: int, side: int, last: int) -> int:
    """The 1h sponsorship reading (bullish terms; a bearish reading runs the mirrored prices) from the candidate extreme bar `jl` to the last completed 1h bar `last`: +1 once a 1h close breaks the latest
    short-term (3-bar) 1h swing high that was confirmed before `jl`, and no 1h bullish order block formed since the break has had a 1h close under its mean threshold. A bullish OB = a down-close 1h
    bar whose next bar closes above its high (formed, i.e. known, at that next bar); its MT = the midpoint of the bar's range ['holds' = no later 1h body close below the MT - our interpretation]. 0 before the
    break or after a failed OB. `side` = +1 bullish / -1 bearish (mirror)."""
    if side < 0:
        ho, hh, hl, hc = -ho, -hl, -hh, -hc
    if jl < 2 or last <= jl:
        return 0
    ph, _ = L.pivots(hh[:jl + 1], hl[:jl + 1], 1)
    cand = [q for q in ph if q.known <= jl]
    if not cand:
        return 0
    ref = cand[-1].price
    jb = None
    for j in range(jl + 1, last + 1):
        if hc[j] > ref:
            jb = j
            break
    if jb is None:
        return 0
    for j in range(max(jl + 1, jb - 1), last):
        if hc[j] < ho[j] and hc[j + 1] > hh[j] and j + 1 >= jb:
            mt = (hh[j] + hl[j]) / 2.0
            if (hc[j + 2:last + 1] < mt).any():
                return 0                                       # a failed OB weakens the reversal idea
    return 1


def h1_sponsor_column(df: pd.DataFrame, d: pd.DataFrame, arrs: list, ks) -> np.ndarray:
    """h1_sponsor per row (see the module doc). For a Wed / Thu / Fri row: the week's lowest (highest) low (high) so far must have been made on a Tuesday or Wednesday session at a daily / weekly array of
    the right colour known before that session (the low reached the array's top and the session closed above its bottom); the reading then runs on the 1h bars that ended before the row's session opened.
    When both a bullish and a bearish candidate exist the later one wins."""
    h1 = h1_frame(df)
    ho, hh, hl, hc = (h1[k].values.astype(float) for k in ("open", "high", "low", "close"))
    ends = h1["end"].values
    starts = h1.index.values
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    wid = np.asarray(d.index.to_period("W-FRI").astype(str))
    wd = d.index.weekday
    tz = df.index.tz
    out = np.zeros(len(ks), int)
    cand_arrs = [a for a in arrs if a.tf in ("D", "W") and a.typ in ("fvg", "ob")]
    for r, k in enumerate(ks):
        k = int(k)
        if wd[k] < 2:
            continue
        k0 = k
        while k0 - 1 >= 0 and wid[k0 - 1] == wid[k]:
            k0 -= 1
        if k0 >= k:
            continue
        open_ts = (pd.Timestamp(d.index[k]).normalize().tz_localize(None) - pd.Timedelta(hours=7))
        open_ts = pd.Timestamp(open_ts, tz=tz)
        n1 = int(np.searchsorted(ends, np.datetime64(open_ts.tz_convert("UTC").tz_localize(None)), side="right"))        # 1h bars that ended by the open
        best = (0, -1)
        for side in (1, -1):
            seg = slice(k0, k)
            q = int(np.argmin(l[seg])) + k0 if side > 0 else int(np.argmax(h[seg])) + k0
            if wd[q] not in (1, 2):
                continue
            ok = False
            for a in cand_arrs:
                if a.known > q:
                    continue
                if side > 0 and a.kind == "bull" and l[q] <= a.top and c[q] >= a.bottom:
                    ok = True
                    break
                if side < 0 and a.kind == "bear" and h[q] >= a.bottom and c[q] <= a.top:
                    ok = True
                    break
            if not ok:
                continue
            # the 1h bar holding the extreme: inside session q's time span
            s0 = pd.Timestamp(pd.Timestamp(d.index[q]).normalize().tz_localize(None) - pd.Timedelta(hours=7), tz=tz)
            s1 = s0 + pd.Timedelta(hours=24)
            i0 = int(h1.index.searchsorted(s0))
            i1 = int(h1.index.searchsorted(s1))
            if i1 <= i0 or i1 > n1:
                continue
            ext = hl[i0:i1] if side > 0 else hh[i0:i1]
            jl = i0 + (int(np.argmin(ext)) if side > 0 else int(np.argmax(ext)))
            st = sponsor_state(ho[:n1], hh[:n1], hl[:n1], hc[:n1], jl, side, n1 - 1)
            if st and q >= best[1]:
                best = (side, q)
        out[r] = best[0]
    return out


# --------------------------------------------------------------------------------------------------------------
# new-stopout-at-planned-array-next-day-flip: array_lost
# --------------------------------------------------------------------------------------------------------------

def _d_alive(a, o, h, l, c, lo: int, hi: int) -> bool:
    """A daily array is still valid after the sessions lo .. hi-1: no close through it (an OB: through its mean threshold; an FVG: through its far edge)."""
    cl = c[lo:hi]
    if not len(cl):
        return True
    if a.kind == "bull":
        return not (cl.min() < (a.ce if a.typ == "ob" else a.bottom))
    return not (cl.max() > (a.ce if a.typ == "ob" else a.top))


def array_lost_columns(d: pd.DataFrame, arrs: list, ks) -> dict:
    """array_lost (+1 / -1 / 0) and array_lost_tgt per row k, from the session j = k-1: the planned support = the nearest live daily bullish FVG / OB whose top is under j's open (alive on the closes before j);
    it is lost when j closed through it (an OB: under its MT; an FVG: under its bottom) -> +1; the target = the top of the next lower daily bullish array still alive after j (NaN without one). The
    bearish mirror gives -1 and the bottom of the next higher bearish array. [our interpretation: 'the planned support array' = the nearest live array under the previous day's open.]"""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    dar = [a for a in arrs if a.tf == "D" and a.typ in ("fvg", "ob")]
    n = len(ks)
    al = np.zeros(n, int)
    tg = np.full(n, NAN)
    for r, k in enumerate(ks):
        j = int(k) - 1
        if j < 1:
            continue
        res = []
        for side in (1, -1):
            kind = "bull" if side > 0 else "bear"
            pool = [a for a in dar if a.kind == kind and a.known <= j and _d_alive(a, o, h, l, c, a.known, j)]
            if side > 0:
                under = [a for a in pool if a.top < o[j]]
                if not under:
                    continue
                A = max(under, key=lambda a: a.top)
                if _d_alive(A, o, h, l, c, A.known, j + 1):
                    continue
                lower = [a for a in pool if a is not A and a.top < A.bottom and _d_alive(a, o, h, l, c, a.known, j + 1)]
                res.append((1, max((a.top for a in lower), default=NAN)))
            else:
                over = [a for a in pool if a.bottom > o[j]]
                if not over:
                    continue
                A = min(over, key=lambda a: a.bottom)
                if _d_alive(A, o, h, l, c, A.known, j + 1):
                    continue
                higher = [a for a in pool if a is not A and a.bottom > A.top and _d_alive(a, o, h, l, c, a.known, j + 1)]
                res.append((-1, min((a.bottom for a in higher), default=NAN)))
        if len(res) == 1:
            al[r], tg[r] = res[0]
    return dict(array_lost=al, array_lost_tgt=tg)


# --------------------------------------------------------------------------------------------------------------
# T13-po3-breaker-regime: brk_react
# --------------------------------------------------------------------------------------------------------------

def breaker_react_column(d: pd.DataFrame, ks, n: int = 2) -> np.ndarray:
    """brk_react per row k: the side of the last daily breaker (`levels.breakers`, known at its closing break) that price REACTED from by session k-1: the first session after the breaker whose range touched
    the zone and that closed away from it (a bearish breaker: high >= its bottom and close < its bottom; a bullish one: low <= its top and close > its top) = a reaction (-1 / +1) in force from the next
    row; a first touching session that closes through the far side kills the zone. The latest reaction (by session) rules; 0 before any."""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    zs = L.breakers(o, h, l, c, n)
    react = []                                         # (session of the reaction, side)
    for z in zs:
        for q in range(z.i + 1, len(c)):
            if z.kind == "bear":
                if h[q] >= z.bottom:
                    if c[q] < z.bottom:
                        react.append((q, -1))
                    break
            else:
                if l[q] <= z.top:
                    if c[q] > z.top:
                        react.append((q, 1))
                    break
    react.sort()
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        cur = 0
        for q, s in react:
            if q <= int(k) - 1:
                cur = s
            else:
                break
        out[r] = cur
    return out


# --------------------------------------------------------------------------------------------------------------
# finish7
# --------------------------------------------------------------------------------------------------------------

def finish7(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, df=None) -> pd.DataFrame:
    """Add the b7 columns named in `cfg` to the table `out` (one row per trading day)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    if "rq" in cfg:
        for k_, v_ in range_columns(o, c, ks, int(cfg["rq"])).items():
            out[k_] = v_
        sw("pd_subrange")
    if "ft" in cfg:
        out["flip_turn"] = flip_turn_column(out.flip.values if "flip" in out else np.zeros(len(out), int), ks, d)
        sw("weekly_flip_follow")
    if "h1" in cfg and df is not None:
        out["h1_sponsor"] = h1_sponsor_column(df, d, arrs, ks)
        sw("h1_sponsor")
    if "al" in cfg:
        for k_, v_ in array_lost_columns(d, arrs, ks).items():
            out[k_] = v_
        sw("array_lost_flip")
    if "br" in cfg:
        out["brk_react"] = breaker_react_column(d, ks)
        sw("htf_bias_breaker")
    return out
