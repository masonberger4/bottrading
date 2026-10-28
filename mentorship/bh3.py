"""Caption-gap pass, package bias_htf#3/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 172-174, 177, 179, 180, 184-190, 195, 197, 198, 215, 216, 221, 222, 224-227) - TABLE SIDE.

The daily / weekly / monthly columns, the INTERMARKET columns (items 152, 167, 168) and the day maps (items 215, 216) these switches need. Everything here is a pure function of COMPLETED daily /
weekly / monthly candles (sessions before the row's day) and of the arrays `htf.table` already built (`Arr.known` = the first session index at which an array may be used): a value in the row of
session k never reads session k or later. The engine side (side gates, scalps, sizes, tags, locks) is `bh3e.py`; the COT data and its two states are `cot.py`. `bx_cfg(p)` is the JSON-able
configuration `bias_htf.bx_string` stores under the key "b3"; `finish3` runs at the end of `htf.table` (after bh2.finish). Thresholds the sources never give are marked [our interpretation]; every
rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  wpr_d                                      (172)       the daily Williams %R(15) side (0..100 scale: below 50 = +1) with a +-5 band that keeps the side most recently left
  profile / profile_dir / wm_zones           (174)       the weekly market profile ("consol" / "trend" / "retrace" / "") over 52 weeks, its trend sign, the live weekly / monthly arrays (lo, hi, dir)
  held_arrays / held_pause                   (185)       opposing arrays touched and held (a daily close back on the bias-opposing side) since the flip state began; the increment of the row
  mo_pd / wk_pd / wk_expand                  (186)       the prior close in the month's / week's range (0..1); consecutive expanding weeks of this month in the monthly bias direction
  in_play                                    (195)       +1 / -1: a daily or 4h array of that side was traded into within in_play_days sessions and a later daily close went beyond it (daily iof not against)
  iof_ob_bounce / iof_gap_fill_rally / iof_premium_broken / iof_sum   (197)   the three extra B6 components over the last 10 sessions and their sum (iof_mode 'score' rewrites iof / combo2)
  wk_pre_bias / wk_obj                       (190)       the weekly bias from the last array touched (premium = -1) and the nearest opposing array within 2 x ADR5 x 5, set on the week's first session
  mo_bias                                    (221)       the monthly draw side (monthly, else weekly) at each month start, held 63 sessions (84 max) unless the flip state opposes it
  q_dir / q_obj_dir                          (222)       the quarterly shift direction from monthly closes and the weekly array objective in that direction
  wk_control                                 (225)       the controlling weekly swing tier: +1 intact ITL below the price and the last ITH broken, -1 the mirror
  wk_chk_tail / wk_consol / d_head / d_tail  (224, 227)  the table parts of the weekly / daily checklist composers (the engine adds the SMT, COT and harmony parts: bh3e.compose_week / compose_day)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import bh2 as BH2

HITS = BH2.HITS
NAN = float("nan")
sw = BH2.sw
_row_state = BH2._row_state


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def needs_iof(p) -> bool:
    """The switches that read the daily `iof` column (B6) beside htf_bias 'iof' / 'combo2'."""
    return bool(p.cot_gate != "off" or p.hallmarks_tag or p.bias_dh != "off" or p.iof_premium_wait or p.pd_needs_iof or p.in_play_gate or p.iof_sponsor_gate != "off"
                or p.htf_bias in ("week_check", "wd_check") or p.ny_continue_london or p.iof_mode == "score")


def bx_cfg(p) -> dict:
    """The "b3" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.wpr_daily_tag:
        c["wprd"] = 1
    if p.profile_gate or p.htf_bias in ("week_check", "wd_check") or p.iof_sponsor_gate != "off":
        c["prof"] = 2 if p.profile_gate else 1                # 2 = also the weekly / monthly zones (the retrace gate)
    if p.retire_arrays:
        c["ret"] = 1
    if p.pause_on_hold:
        c["hold"] = 1
    if p.mw_bookkeeping:
        c["mw"] = 1
    if p.in_play_gate:
        c["inplay"] = int(p.in_play_days)
    if p.iof_mode == "score":
        c["iofx"] = 1
    if p.htf_bias == "week_pre":
        c["wkpre"] = 1
    if p.mo_bias_gate or p.wk_struct_weight:
        c["mo"] = 1
    if p.q_dir_tag:
        c["qdir"] = 1
    if p.wk_struct_weight:
        c["wkc"] = 1
    if p.htf_bias in ("week_check", "wd_check") or p.iof_sponsor_gate != "off":
        c["chk"] = [int(p.iof_w_weeks), int(p.iof_min)]
    if "tue_fail" in p.flip_triggers:
        c["fl"] = {"tuef": 4.0 * float(p.eq_tol_pts)}
    return c


def flip_cfg(b3: dict | None, es_pt: float) -> dict:
    """The part of the "b3" block `htf._flip` reads: the tue_fail tolerance (eq_tol_pts x 4, in price units)."""
    fl = dict((b3 or {}).get("fl") or {})
    if "tuef" in fl:
        return {"tue_tol": float(fl["tuef"]) * float(es_pt)}
    return {}


# --------------------------------------------------------------------------------------------------------------
# small helpers on the daily book
# --------------------------------------------------------------------------------------------------------------

def _pos(d):
    return {t: q for q, t in enumerate(d.index)}


def _slope(y) -> float:
    y = np.asarray(y, float)
    return float(np.polyfit(np.arange(len(y)), y, 1)[0])


def tf_bars(d, rule: str):
    """Completed bars of a timeframe of the daily book: o, h, l, c, `last` (the session position completing each bar)."""
    g = d.groupby(d.index.to_period(rule))
    pos = _pos(d)
    last = np.array([pos[x.index[-1]] for _, x in g])
    return (g.open.first().values.astype(float), g.high.max().values.astype(float), g.low.min().values.astype(float), g.close.last().values.astype(float), last)


def month_arrays(d, arrs) -> list:
    """The monthly arrays: those `htf.table` built (monthly_arrays) or, without them, built here from the monthly bars (usable the session after the month's last session). Never changes the table's bias."""
    have = [a for a in arrs if a.tf == "M"]
    if have:
        return have
    from .htf import _arrays
    mo, mh, ml, mc, mlast = tf_bars(d, "M")
    if len(mc) < 3:
        return []
    return _arrays(mo, mh, ml, mc, "M", lambda i: int(mlast[i]) + 1)


# --------------------------------------------------------------------------------------------------------------
# item 172: the daily Williams %R(15)
# --------------------------------------------------------------------------------------------------------------

def wpr_daily_state(h, l, c, n: int = 15, band: float = 5.0) -> np.ndarray:
    """B20-williams-r (cc12_002 ~13:41; cc06_007 ~25:49): per session j the side after the session completes - %R(n) on the 0..100 scale (0 = the n-session low, 100 = the high), at or below
    50 = oversold / buy area = +1, above 50 = overbought / sell area = -1; while %R hovers inside 50 +- `band` the side most recently left (the last reading outside the band) holds
    [our interpretation of 'favour the side of the condition most recently left'; before any reading outside the band: 0]."""
    D = len(c)
    st = np.zeros(D, int)
    cur = 0
    for j in range(D):
        if j >= n - 1:
            hh, ll = h[j - n + 1:j + 1].max(), l[j - n + 1:j + 1].min()
            if hh > ll:
                r = 100.0 * (c[j] - ll) / (hh - ll)
                if r < 50.0 - band:
                    cur = 1
                elif r > 50.0 + band:
                    cur = -1
        st[j] = cur
    return st


def wpr_daily_column(h, l, c, ks) -> np.ndarray:
    return _row_state(wpr_daily_state(h, l, c), ks, 0)


# --------------------------------------------------------------------------------------------------------------
# items 174 / 222: the weekly market profile and the quarterly direction
# --------------------------------------------------------------------------------------------------------------

def profile_of(wh, wl, wc, n: int) -> tuple:
    """X3-htf-market-profile (cc06_001 ~2:43, ~5:34, ~3:52): (profile, trend sign) of the first n weekly bars [our interpretation of '9-18 months': 52 weeks]. 'consol' when the 26-week range is under
    1.5 x the 52-week mean weekly range x 6; 'trend' when the last 13 weekly closes slope one way and the last close is beyond the 26-week EQ that way; 'retrace' when the trend holds but the last 4
    weeks moved against it (close[-1] against close[-5]); '' when fewer than 26 weeks exist or none of the three applies."""
    if n < 26:
        return "", 0
    rng26 = float(wh[n - 26:n].max() - wl[n - 26:n].min())
    m = min(52, n)
    mean_rng = float((wh[n - m:n] - wl[n - m:n]).mean())
    if mean_rng > 0 and rng26 < 1.5 * mean_rng * 6:
        return "consol", 0
    if n < 13:
        return "", 0
    s = int(np.sign(_slope(wc[n - 13:n])))
    eq = (float(wh[n - 26:n].max()) + float(wl[n - 26:n].min())) / 2
    if s == 0 or (s > 0 and wc[n - 1] <= eq) or (s < 0 and wc[n - 1] >= eq):
        return "", 0
    if n >= 5 and np.sign(wc[n - 1] - wc[n - 5]) == -s:
        return "retrace", s
    return "trend", s


def wm_zones_of(arrs_w, arrs_m, k: int, o, h, l, c, wo, wc, wl) -> tuple:
    """The live weekly / monthly FVG and OB arrays at row k as a tuple of (bottom, top, dir): known by k and not closed through (htf._arr_alive; weekly arrays are judged by completed weekly closes)."""
    from .htf import _arr_alive
    out = []
    for a in list(arrs_w) + list(arrs_m):
        if a.typ not in ("fvg", "ob") or a.known > k:
            continue
        if _arr_alive(a, k, o, h, l, c, wo, wc, wl, False, "full_span", bal="own"):
            out.append((float(a.bottom), float(a.top), 1 if a.kind == "bull" else -1))
    return tuple(out)


def profile_columns(d, w, arrs, ks, zones: bool = True) -> dict:
    """The profile columns (item 174) on the completed weekly bars before each row."""
    pos = _pos(d)
    wlast = np.array([pos[t] for t in w["last"]])
    wh, wl_, wc_ = (w[k].values.astype(float) for k in ("high", "low", "close"))
    n = len(ks)
    prof = np.empty(n, dtype=object)
    pdir = np.zeros(n, int)
    for r, k in enumerate(ks):
        m = int(np.searchsorted(wlast, k, side="left"))               # weeks whose last session is before the row's session
        prof[r], pdir[r] = profile_of(wh, wl_, wc_, m)
    res = dict(profile=prof, profile_dir=pdir)
    if zones:
        o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
        wo = w.open.values.astype(float)
        wlist = [int(x) + 1 for x in wlast]
        aw = [a for a in arrs if a.tf == "W"]
        am = month_arrays(d, arrs)
        zs = np.empty(n, dtype=object)
        for r, k in enumerate(ks):
            zs[r] = wm_zones_of(aw, am, int(k), o, h, l, c, wo, wc_, wlist)
        res["wm_zones"] = zs
    return res


def q_dir_column(d, ks) -> np.ndarray:
    """B22-quarterly-shift-direction (cc12_001 ~20:16): from the completed monthly bars - when the last 12 monthly closes trend (the item 174 test on monthly bars: the slope sign and the last close beyond
    the 12-month EQ that way, and the net move covers at least half of the range [our interpretation: a flat year is consolidating]) the next shift is expected to continue that trend: q_dir = the trend sign; otherwise the last 3-4 months reverse: q_dir = -sign(close[-1] - close[-5]) (the net change over the
    last 4 months). 0 without 12 completed months or without a net change."""
    mo, mh, ml, mc, mlast = tf_bars(d, "M")
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        n = int(np.searchsorted(mlast, k, side="left"))
        if n < 12:
            continue
        s = int(np.sign(_slope(mc[n - 12:n])))
        hi, lo = float(mh[n - 12:n].max()), float(ml[n - 12:n].min())
        eq = (hi + lo) / 2
        net = float(mc[n - 1] - mc[n - 12])
        if s != 0 and ((s > 0 and mc[n - 1] > eq) or (s < 0 and mc[n - 1] < eq)) and s * net >= 0.5 * (hi - lo):         # [our interpretation] a trend: the 12-month net move covers at least half of the 12-month range
            out[r] = s
        else:
            out[r] = int(-np.sign(mc[n - 1] - mc[n - 5]))
    return out


def q_obj_dir_column(arrs, ks, px, h, l, c, qdir) -> np.ndarray:
    """B22-quarterly-shift-direction -> item 83: the near edge of the nearest weekly FVG in the q_dir direction beyond the 60-session range (the weekly bull FVG below for -1; the bear FVG above for +1),
    valid while unrebalanced (the q_obj rule of bh2.qshift_columns); NaN without one."""
    wk = [a for a in arrs if a.tf == "W" and a.typ == "fvg"]
    out = np.full(len(ks), NAN)
    for r, k in enumerate(ks):
        s = int(qdir[r])
        if not s or k < 1:
            continue
        lo60, hi60 = l[max(0, k - 60):k].min(), h[max(0, k - 60):k].max()
        if s < 0:
            cs = [a for a in wk if a.kind == "bull" and a.known <= k and a.top < lo60 and c[a.known:k].min(initial=np.inf) >= a.bottom]
            if cs:
                out[r] = float(max(cs, key=lambda x: x.top).top)
        else:
            cs = [a for a in wk if a.kind == "bear" and a.known <= k and a.bottom > hi60 and c[a.known:k].max(initial=-np.inf) <= a.top]
            if cs:
                out[r] = float(min(cs, key=lambda x: x.bottom).bottom)
    return out


# --------------------------------------------------------------------------------------------------------------
# item 185: arrays that hold on the way
# --------------------------------------------------------------------------------------------------------------

def held_columns(flip, arrs, ks, h, l, c) -> dict:
    """B9-ltf-arrays-break-in-succession (cc07_001 ~14:48): within each run of one non-zero flip state, the count of OPPOSING daily arrays (bull arrays in a bearish state, bear arrays in a bullish one)
    that were touched in the run and then produced a daily close back on the bias-opposing side (a close above a touched bull array's top / below a touched bear array's bottom) - 'held' - counted
    from the session after that close. held_pause = 1 on the row where the count rose (the next session after the holding close) [our interpretation: a holding array is a reason to pause]."""
    n = len(ks)
    held = np.zeros(n, int)
    pause = np.zeros(n, int)
    da = [a for a in arrs if a.tf == "D" and a.typ in ("fvg", "ob", "vi")]
    r0 = 0
    for r in range(n):
        s = int(flip[r])
        if r == 0 or s != int(flip[r - 1]):
            r0 = r
        if s == 0:
            continue
        k, k0 = int(ks[r]), int(ks[r0])
        cnt = 0
        for a in da:
            if a.kind != ("bull" if s < 0 else "bear") or a.known > k - 1:
                continue
            for t in range(max(k0, a.known), k):                      # sessions of the run before the row
                if (l[t] <= a.top and h[t] >= a.bottom):             # traded into the array
                    seg = c[t:k]
                    if (s < 0 and seg.max() > a.top) or (s > 0 and seg.min() < a.bottom):
                        cnt += 1
                    break
        held[r] = cnt
        if r > 0 and int(flip[r - 1]) == s and cnt > held[r - 1]:
            pause[r] = 1
    return dict(held_arrays=held, held_pause=pause)


# --------------------------------------------------------------------------------------------------------------
# item 186: the month / week range bookkeeping
# --------------------------------------------------------------------------------------------------------------

def mw_columns(d, ks, bias_m=None) -> dict:
    """B5-monthly-weekly-range-bookkeeping (cc07_001 ~34:13, ~35:56): mo_pd / wk_pd = the prior close's position (0 = low, 1 = high) in the range of the current month / week up to the prior session (on
    the month's / week's first session the previous month's / week's range [our interpretation]); wk_expand = the count of consecutive completed weeks of this month that made a new extreme (a higher
    high for a bullish monthly bias, a lower low for a bearish one) over the week before, counted back from the last completed week. The monthly bias is `bias_m` when given and non-zero, else the
    previous completed month's candle direction [our interpretation]. Tags only."""
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    o = d.open.values.astype(float)
    mon = d.index.to_period("M")
    wkp = d.index.to_period("W-FRI")
    n = len(ks)
    mo_pd = np.full(n, NAN)
    wk_pd = np.full(n, NAN)
    wk_ex = np.zeros(n, int)
    # weekly bars of the book: (period, first idx, last idx)
    wk_first, wk_last = {}, {}
    for q, p_ in enumerate(wkp):
        wk_first.setdefault(p_, q)
        wk_last[p_] = q
    wk_order = list(wk_first)
    for r, k in enumerate(ks):
        k = int(k)
        if k < 1:
            continue

        def pdpos(a, b):
            hi, lo = h[a:b].max(), l[a:b].min()
            return float((c[k - 1] - lo) / (hi - lo)) if hi > lo else NAN
        m0 = next(q for q in range(k, -1, -1) if q == 0 or mon[q - 1] != mon[k])        # first session of the row's month
        mo_pd[r] = pdpos(m0, k) if m0 < k else (pdpos(next(q for q in range(m0 - 1, -1, -1) if q == 0 or mon[q - 1] != mon[m0 - 1]), m0) if m0 >= 1 else NAN)
        w0 = wk_first[wkp[k]]
        wk_pd[r] = pdpos(w0, k) if w0 < k else (pdpos(wk_first[wkp[w0 - 1]], w0) if w0 >= 1 else NAN)
        # monthly bias direction
        bm = int(bias_m[r]) if bias_m is not None else 0
        if not bm and m0 >= 1:
            pm0 = next(q for q in range(m0 - 1, -1, -1) if q == 0 or mon[q - 1] != mon[m0 - 1])
            bm = int(np.sign(c[m0 - 1] - o[pm0]))
        if not bm:
            continue
        cur = wkp[k]
        wi = wk_order.index(cur)
        cnt = 0
        for j in range(wi - 1, 0, -1):                                # completed weeks, newest first
            pj = wk_order[j]
            if mon[wk_last[pj]] != mon[k]:
                break
            a1, b1 = wk_first[pj], wk_last[pj]
            a0, b0 = wk_first[wk_order[j - 1]], wk_last[wk_order[j - 1]]
            if bm > 0 and h[a1:b1 + 1].max() > h[a0:b0 + 1].max():
                cnt += 1
            elif bm < 0 and l[a1:b1 + 1].min() < l[a0:b0 + 1].min():
                cnt += 1
            else:
                break
        wk_ex[r] = cnt
    return dict(mo_pd=mo_pd, wk_pd=wk_pd, wk_expand=wk_ex)


# --------------------------------------------------------------------------------------------------------------
# item 195: the HTF arrays are respected and in play
# --------------------------------------------------------------------------------------------------------------

def four_hour_events(df, d, arrs_fn=None):
    """The 4h arrays of the intraday frame as [(kind, top, bottom, touch session positions list)] helpers for in_play: returns a list of (kind, top, bottom, [(session_pos, touched)])"""
    from .htf import _arrays
    if df is None or not len(df):
        return []
    g = df.groupby(df.index.floor("240min"))
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    if len(b) < 8:
        return []
    lab = (b.index + pd.Timedelta(minutes=239) + pd.Timedelta(hours=7)).tz_localize(None).normalize()          # the session label of the bar's LAST minute
    pos = {t: q for q, t in enumerate(d.index)}
    sess = np.array([pos.get(t, -1) for t in lab])
    o4, h4, l4, c4 = (b[k].values.astype(float) for k in ("open", "high", "low", "close"))
    zs = _arrays(o4, h4, l4, c4, "4h", lambda i: i + 1)
    out = []
    for a in zs:
        if a.typ not in ("fvg", "ob"):
            continue
        touches = [int(sess[t]) for t in range(a.known, len(b)) if sess[t] >= 0 and l4[t] <= a.top and h4[t] >= a.bottom]
        out.append((a.kind, float(a.top), float(a.bottom), int(sess[a.known]) if a.known < len(b) else -1, touches))
    return out


def in_play_column(h, l, c, arrs, ks, days: int, iof, ev4=None) -> np.ndarray:
    """B5-htf-arrays-respected-and-in-play (cc09_001 ~3:30; cc08_006 ~21:14): +1 when, within the last `days` completed sessions, a daily (or 4h) bull array was traded into (the session's low reached its
    top) and a daily close at or after that session was above its top (the reaction), and the daily iof is not -1; -1 for the mirror (bear array, a close below its bottom, iof not +1); both: the later
    reaction wins, a tie is 0. A daily array closed through (a close under a bull array's bottom) before the touch or before the reaction is invalid; a 4h array is known from the session after it formed."""
    n = len(ks)
    out = np.zeros(n, int)
    da = [(a.kind, float(a.top), float(a.bottom), int(a.known), None) for a in arrs if a.tf == "D" and a.typ in ("fvg", "ob", "vi")]
    ev = da + list(ev4 or [])
    for r, k in enumerate(ks):
        k = int(k)
        best = {1: -1, -1: -1}
        for kind, top, bot, known, touches in ev:
            if known > k - 1:
                continue
            sg = 1 if kind == "bull" else -1
            if touches is None:
                cand = [t for t in range(max(known, k - days), k) if l[t] <= top and h[t] >= bot]
            else:
                cand = [t for t in touches if k - days <= t <= k - 1]
            if not cand:
                continue
            t0 = cand[0]
            if touches is None:
                pre = c[known:t0]
                if (sg > 0 and pre.min(initial=np.inf) < bot) or (sg < 0 and pre.max(initial=-np.inf) > top):
                    continue
            q = None
            for j in range(t0, k):
                x = c[j]
                if (sg > 0 and x < bot) or (sg < 0 and x > top):
                    break
                if (sg > 0 and x > top) or (sg < 0 and x < bot):
                    q = j
                    break
            if q is not None:
                best[sg] = max(best[sg], q)
        io = int(iof[r])
        up = best[1] >= 0 and io != -1
        dn = best[-1] >= 0 and io != 1
        if up and dn:
            out[r] = 1 if best[1] > best[-1] else (-1 if best[-1] > best[1] else 0)
        else:
            out[r] = 1 if up else (-1 if dn else 0)
    return out


# --------------------------------------------------------------------------------------------------------------
# item 197: the extra B6 components
# --------------------------------------------------------------------------------------------------------------

def iof_components(o, h, l, c, arrs, ks, n: int = 10) -> dict:
    """B6-iof-checklist-extended (cc08_007 ~6:10; cc10_002 ~5:58): over the last `n` completed sessions, each component is the sign of its events (+1 bullish, -1 bearish, 0 none or tied):
      iof_ob_bounce        a bull OB touched (low reached its top) and the session closed above its top (+1); a bear OB touched and the session closed below its bottom (-1)
      iof_gap_fill_rally   a bull FVG filled (a low at or under its bottom) and then a close above its top (+1); a bear FVG filled (a high at or over its top) then a close below its bottom (-1)
      iof_premium_broken   a bear OB / FVG closed through (a close above its top) (+1); a bull OB / FVG closed through (a close below its bottom) (-1)
    Arrays count from the session after they formed (`known`); each array scores at most once per component. iof_sum = the three components summed."""
    da = [a for a in arrs if a.tf == "D" and a.typ in ("fvg", "ob")]
    m = len(ks)
    ob = np.zeros(m, int)
    gf = np.zeros(m, int)
    pb = np.zeros(m, int)
    D = len(c)
    # event sessions per array (computed once)
    ev_ob, ev_gf, ev_pb = [], [], []
    for a in da:
        s = a.known
        bull = a.kind == "bull"
        if a.typ == "ob":
            for j in range(s, D):
                if l[j] <= a.top and h[j] >= a.bottom:                  # touched
                    if bull and c[j] > a.top:
                        ev_ob.append((j, 1))
                    elif (not bull) and c[j] < a.bottom:
                        ev_ob.append((j, -1))
                    if (bull and c[j] < a.bottom) or ((not bull) and c[j] > a.top) or (bull and c[j] > a.top) or ((not bull) and c[j] < a.bottom):
                        break                                           # scored or failed: once per array
        if a.typ == "fvg":
            for j in range(s, D):
                if bull and l[j] <= a.bottom:
                    q = next((x for x in range(j, D) if c[x] > a.top), None)
                    if q is not None:
                        ev_gf.append((q, 1))
                    break
                if (not bull) and h[j] >= a.top:
                    q = next((x for x in range(j, D) if c[x] < a.bottom), None)
                    if q is not None:
                        ev_gf.append((q, -1))
                    break
        for j in range(s, D):
            if (not bull) and c[j] > a.top:
                ev_pb.append((j, 1))
                break
            if bull and c[j] < a.bottom:
                ev_pb.append((j, -1))
                break
    for r, k in enumerate(ks):
        lo = int(k) - n
        for ev, arr in ((ev_ob, ob), (ev_gf, gf), (ev_pb, pb)):
            sgn = sum(s for j, s in ev if lo <= j <= k - 1)
            arr[r] = int(np.sign(sgn))
    return dict(iof_ob_bounce=ob, iof_gap_fill_rally=gf, iof_premium_broken=pb, iof_sum=ob + gf + pb)


def apply_iof_score(out: pd.DataFrame) -> pd.DataFrame:
    """iof_mode 'score' (item 197): the daily iof column = sign(iof_sum) when |iof_sum| >= 2 else 0; combo2 follows (react, then iof, then the P/D reading)."""
    sc = out.iof_sum.values
    out["iof"] = np.where(sc >= 2, 1, np.where(sc <= -2, -1, 0))
    if "combo2" in out:
        out["combo2"] = [int(r) if r else (int(i) if i else int(p_)) for r, i, p_ in zip(out.react, out.iof, out.pd)]
    sw("iof_mode")
    return out


# --------------------------------------------------------------------------------------------------------------
# item 190: the weekly bias before the week opens
# --------------------------------------------------------------------------------------------------------------

def wk_pre_columns(d, arrs, ks, px, o, h, l, c, look: int = 20) -> dict:
    """B13-weekly-bias-from-daily-arrays (cc08_001 ~26:26; cc07_006 ~16:09) [CC; conflicts with B16]: on the first session of each week, the weekly bias from the last HTF (daily, weekly or monthly) array
    that price traded INTO (within the last `look` completed sessions): a premium (bear) array = -1, a discount (bull) array = +1 (the nearest to that session's close when several). wk_obj = the near
    edge of the nearest opposing array (a bull array's top for -1, a bear array's bottom for +1) within 2 x ADR5 x 5 of the price [our interpretation of 'reasonably reach']. Both are held for the whole week."""
    pool = [a for a in arrs if a.typ in ("fvg", "ob", "vi") and a.tf in ("D", "W", "M")]
    n = len(ks)
    pre = np.zeros(n, int)
    obj = np.full(n, NAN)
    wkp = d.index.to_period("W-FRI")
    cur_wk, cur_pre, cur_obj = None, 0, NAN
    for r, k in enumerate(ks):
        k = int(k)
        if cur_wk != wkp[k]:
            cur_wk = wkp[k]
            cur_pre, cur_obj = 0, NAN
            if k >= 6:
                for j in range(k - 1, max(-1, k - 1 - look), -1):
                    hit_ = [a for a in pool if a.known <= j and l[j] <= a.top and h[j] >= a.bottom]
                    if hit_:
                        a = min(hit_, key=lambda x: abs(c[j] - x.ce))
                        cur_pre = 1 if a.kind == "bull" else -1
                        break
                if cur_pre:
                    adr5 = float((h[k - 5:k] - l[k - 5:k]).mean())
                    reach = 2.0 * adr5 * 5.0
                    x = float(px[r])
                    cs = []
                    for a in pool:
                        if a.known > k:
                            continue
                        if cur_pre < 0 and a.kind == "bull" and a.top < x and c[a.known:k].min(initial=np.inf) >= a.bottom and x - a.top <= reach:
                            cs.append((x - a.top, float(a.top)))
                        if cur_pre > 0 and a.kind == "bear" and a.bottom > x and c[a.known:k].max(initial=-np.inf) <= a.top and a.bottom - x <= reach:
                            cs.append((a.bottom - x, float(a.bottom)))
                    if cs:
                        cur_obj = min(cs)[1]
        pre[r], obj[r] = cur_pre, cur_obj
    return dict(wk_pre_bias=pre, wk_obj=obj)


# --------------------------------------------------------------------------------------------------------------
# items 221 / 225: the monthly bias and the controlling weekly structure
# --------------------------------------------------------------------------------------------------------------

def mo_bias_column(d, ks, bias_m, bias_w, flip=None, hold: int = 63, cap: int = 84) -> np.ndarray:
    """MB-monthly-bias-routine (cc12_001 ~11:22, ~12:08, ~27:01, ~52:52): at the first session of each month the monthly bias = the side of the monthly draw (the item 116 'M' logic: monthly, else weekly, else
    none) from the prior month-end data. A non-zero reading is held for `hold` (63) sessions - at most `cap` (84) since the side was first set - and renewed by a reading of the same side at a later month
    start; a reading of 0 keeps the held side; a flip state opposing it (flip == -side) ends it."""
    mon = d.index.to_period("M")
    n = len(ks)
    out = np.zeros(n, int)
    cur, born, last = 0, -1, -1
    for r, k in enumerate(ks):
        k = int(k)
        if k >= 1 and mon[k] != mon[k - 1]:
            m0 = int(bias_m[r]) or int(bias_w[r])
            if m0:
                if m0 != cur:
                    cur, born = m0, k
                last = k
        if cur and (k - last >= hold or k - born >= cap or (flip is not None and int(flip[r]) == -cur)):
            cur = 0
        out[r] = cur
    return out


def wk_control_column(d, w, ks, px) -> np.ndarray:
    """B10-weekly-structure-control (cc12_002 ~17:43): swing_tiers on the completed weekly bars. +1 when the most recent unbroken weekly ITL (intermediate-term low, known) is below the price and the last
    ITH (intermediate-term high) was broken (a later weekly high above it) - the intermediate lows control a rising market; -1 for the mirror; else 0 [our operationalisation: the controlling swing is the
    most recent unbroken ITH / ITL]."""
    pos = _pos(d)
    wlast = np.array([pos[t] for t in w["last"]])
    wh, wl_ = w.high.values.astype(float), w.low.values.astype(float)
    t = L.swing_tiers(wh, wl_, 1)
    ith, itl = t["itl"]
    n = len(ks)
    out = np.zeros(n, int)
    for r, k in enumerate(ks):
        m = int(np.searchsorted(wlast, k, side="left"))
        if m < 6:
            continue
        x = float(px[r])
        hs = [q for q in ith if q.known <= m - 1]
        ls = [q for q in itl if q.known <= m - 1]
        if not hs or not ls:
            continue
        lh, ll = hs[-1], ls[-1]
        h_broken = wh[lh.i + 1:m].max(initial=-np.inf) > lh.price
        h_intact = not h_broken
        l_broken = wl_[ll.i + 1:m].min(initial=np.inf) < ll.price
        l_intact = not l_broken
        if l_intact and ll.price < x and h_broken:
            out[r] = 1
        elif h_intact and lh.price > x and l_broken:
            out[r] = -1
    return out


# --------------------------------------------------------------------------------------------------------------
# items 224 / 227: the table parts of the checklist composers
# --------------------------------------------------------------------------------------------------------------

def chk_columns(out: pd.DataFrame) -> dict:
    """The table side of the weekly (item 224) and daily (item 227) checklist composers. wk_chk_tail = 0 when the weekly profile is 'consol' (the cascade stops with a neutral result), else the first
    non-zero of the weekly iof (iof_w) and the weekly draw (wk_bias); wk_consol flags the profile; d_head = the daily iof; d_tail = the first non-zero of the flip state (the B8 / d_breaker reading) and the
    table draw. The engine adds the SMT, COT and harmony parts in the ICT order (bh3e.compose_week / compose_day)."""
    n = len(out)

    def col(nm):
        return out[nm].values.astype(float) if nm in out else np.zeros(n)

    def first(*cols):
        r = np.zeros(n, int)
        for x in cols[::-1]:
            r = np.where(np.nan_to_num(x) != 0, np.sign(np.nan_to_num(x)).astype(int), r)
        return r
    cons = (out.profile.values == "consol") if "profile" in out else np.zeros(n, bool)
    tail = np.where(cons, 0, first(col("iof_w"), col("wk_bias")))
    return dict(wk_chk_tail=tail.astype(int), wk_consol=cons.astype(int), d_head=first(col("iof")), d_tail=first(col("flip"), col("draw")))


# --------------------------------------------------------------------------------------------------------------
# the whole-table pass (htf.table, after bh2.finish)
# --------------------------------------------------------------------------------------------------------------

def finish3(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, df=None) -> pd.DataFrame:
    """Add the b3 columns named in `cfg` to the table `out` (one row per trading day)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    px = out.px.values.astype(float)
    n = len(out)
    if "wprd" in cfg:
        out["wpr_d"] = wpr_daily_column(h, l, c, ks)
    if "prof" in cfg:
        for k_, v_ in profile_columns(d, w, arrs, ks, cfg["prof"] == 2).items():
            out[k_] = v_
    need_m = "mo" in cfg or "qdir" in cfg
    bm = out.bias_m.values if "bias_m" in out else None
    bw = out.bias_w.values if "bias_w" in out else None
    if "mo" in cfg and bm is None:
        bt = BH2.btf_columns(list(arrs) + [a for a in month_arrays(d, arrs) if a.tf == "M" and a not in arrs], ks, px, h, l, c, d, False, True, False)
        bm, bw = bt["bias_m"], bt["bias_w"]
    if "mw" in cfg:
        for k_, v_ in mw_columns(d, ks, bm).items():
            out[k_] = v_
    if "hold" in cfg and "flip" in out:
        for k_, v_ in held_columns(out.flip.values, arrs, ks, h, l, c).items():
            out[k_] = v_
    if "inplay" in cfg:
        iof = out.iof.values if "iof" in out else np.zeros(n, int)
        out["in_play"] = in_play_column(h, l, c, arrs, ks, int(cfg["inplay"]), iof, four_hour_events(df, d))
    if "iofx" in cfg:
        for k_, v_ in iof_components(o, h, l, c, arrs, ks).items():
            out[k_] = v_
        out = apply_iof_score(out)
    if "wkpre" in cfg:
        for k_, v_ in wk_pre_columns(d, arrs, ks, px, o, h, l, c).items():
            out[k_] = v_
        sw("week_pre")
    if "mo" in cfg:
        out["mo_bias"] = mo_bias_column(d, ks, bm, bw, out.flip.values if "flip" in out else None)
        sw("mo_bias_gate")
    if "qdir" in cfg:
        out["q_dir"] = q_dir_column(d, ks)
        out["q_obj_dir"] = q_obj_dir_column(arrs, ks, px, h, l, c, out.q_dir.values)
    if "wkc" in cfg:
        out["wk_control"] = wk_control_column(d, w, ks, px)
    if "chk" in cfg:
        if "iof_w" not in out:
            out["iof_w"] = BH2.iof_w_column(d, w, ks, int(cfg["chk"][0]), int(cfg["chk"][1]))
        for k_, v_ in chk_columns(out).items():
            out[k_] = v_
    return out


# --------------------------------------------------------------------------------------------------------------
# INTERMARKET extras (backtest.INTERMARKET): items 152, 167, 168
# --------------------------------------------------------------------------------------------------------------

def _trend_ratio(s: pd.Series, n: int = 20) -> pd.Series:
    """|n-session regression slope| / mean |daily change| of the same window, from the closes up to the previous session (shift(1)) [our interpretation of 'slope / ATR': only closes are loaded]."""
    sl = s.rolling(n).apply(_slope, raw=True)
    mad = s.diff().abs().rolling(n).mean()
    return (sl.abs() / mad.replace(0, np.nan)).shift(1)


def im3_columns(dxy: pd.Series | None, tnx: pd.Series | None) -> pd.DataFrame:
    """X3-notes-dollar-regime (cc05_006 ~10:16 ...), X3-swing-two-group-trending-gate (cc06_007 ~9:14), X3-bonds-lead-stocks (cc05_009 ~13:48): extra INTERMARKET columns, every value for date t built from
    the closes up to t-1 only.
      notes_dxy   'tandem' / 'opposed': the 10Y NOTE price direction (= -sign of the 20-session slope of the yield) against the dollar's (sign of the 20-session slope of the DXY): equal = tandem
      tr_tnx / tr_dxy   |20-session slope| / the mean absolute daily change (the trend ratio; > trend_slope_min = trending)
      bond_lt     -sign(the 126-session change of the yield): the bond price proxy's long-term direction (bonds lead stocks by 6-12 months)"""
    cols: dict = {}
    if tnx is not None and len(tnx) > 130:
        cols["tr_tnx"] = _trend_ratio(tnx)
        cols["bond_lt"] = -np.sign(tnx.shift(1) - tnx.shift(127))
    if dxy is not None and len(dxy) > 22:
        cols["tr_dxy"] = _trend_ratio(dxy)
    if tnx is not None and dxy is not None and len(tnx) > 22:
        sn = -np.sign(tnx.rolling(20).apply(_slope, raw=True)).shift(1)
        sd = np.sign(dxy.rolling(20).apply(_slope, raw=True)).shift(1).reindex(sn.index).ffill()
        both = (sn.fillna(0) != 0) & (sd.fillna(0) != 0)
        cols["notes_dxy"] = pd.Series(np.where(both, np.where(sn == sd, "tandem", "opposed"), ""), index=sn.index)
    if not cols:
        return pd.DataFrame()
    return pd.concat(cols, axis=1)


# --------------------------------------------------------------------------------------------------------------
# day maps (backtest.run with a partner): items 215, 216
# --------------------------------------------------------------------------------------------------------------

def _daily_pair(df_a, df_b):
    from .htf import sessions
    a, b = sessions(df_a), sessions(df_b)
    idx = a.index.intersection(b.index)
    return a.loc[idx], b.loc[idx]


def poised_map(df_a, df_b, dsmt: dict | None = None, n: int = 20) -> dict:
    """B23-market-poised-first (cc10_016 ~1:51; cc11_003 ~4:37): {date: +1 / -1 / 0}, known before that session. +1 = the broad market is poised to rally: both indices' n-session slopes (of the closes through
    the prior session) are positive, or the daily SMT (dsmt) is +1 with the prior close below the 60-session EQ; -1 = the mirror (both falling, or dsmt -1 with the close above the EQ). A third index
    (the Dow) is not loaded."""
    a, b = _daily_pair(df_a, df_b)
    ca, cb = a.close.values.astype(float), b.close.values.astype(float)
    ha, la = a.high.values.astype(float), a.low.values.astype(float)
    out = {}
    for k in range(len(a)):
        v = 0
        if k >= n + 1:
            sa, sb = _slope(ca[k - n:k]), _slope(cb[k - n:k])
            if sa > 0 and sb > 0:
                v = 1
            elif sa < 0 and sb < 0:
                v = -1
        if v == 0 and dsmt is not None and k >= 61:
            s = int(dsmt.get(a.index[k].date(), 0) or 0)
            eq = (ha[k - 60:k].max() + la[k - 60:k].min()) / 2
            if s > 0 and ca[k - 1] < eq:
                v = 1
            elif s < 0 and ca[k - 1] > eq:
                v = -1
        out[a.index[k].date()] = v
    return out


def fall_low_map(df_a, df_b, dsmt: dict, windows=None) -> dict:
    """B23-fall-seasonal-low-setup (cc10_018 ~34:58): {date: +1 / -1 / 0} known before that session. +1 is set on a session with the daily SMT dsmt == +1 (one index fails to make a lower low) inside a
    bullish seasonal window (the calendar windows whose direction is +1: the fall low win_long_fall / the spring window win_long_spring ..., calendar.SEASON_WINDOWS) with the prior close below the 60-session
    EQ, and persists until a session takes the 60-session high that stood when it was set; the mirror (dsmt -1 in a bearish window with the close above the EQ) is -1 until the 60-session low is taken."""
    from . import calendar as CAL
    a, _b = _daily_pair(df_a, df_b)
    h, l, c = (a[k].values.astype(float) for k in ("high", "low", "close"))
    wins = windows if windows is not None else CAL.SEASON_WINDOWS
    out = {}
    cur, lvl = 0, NAN
    for k in range(len(a)):
        day = a.index[k].date()
        if cur > 0 and h[k - 1] >= lvl or cur < 0 and l[k - 1] <= lvl:
            cur = 0                                                   # the 60-session extreme that stood at the set was taken by the prior session
        if k >= 61:
            s = int(dsmt.get(day, 0) or 0)
            dr = 0
            for nm_, d_, x_, y_ in wins:
                if CAL._in_window(day, x_, y_):
                    if nm_ in ("win_long_fall", "win_long_spring"):
                        dr = 1                                        # the spec's bullish windows: the fall low and Feb-May
                        break
                    if int(d_) < 0:
                        dr = -1                                       # [our interpretation] the mirror: the bearish windows
            eq = (h[k - 60:k].max() + l[k - 60:k].min()) / 2
            if s > 0 and dr > 0 and c[k - 1] < eq and cur <= 0:
                cur, lvl = 1, float(h[k - 60:k].max())
            elif s < 0 and dr < 0 and c[k - 1] > eq and cur >= 0:
                cur, lvl = -1, float(l[k - 60:k].min())
        out[day] = cur
    return out


# --------------------------------------------------------------------------------------------------------------
# item 188: the Tuesday failure swing (flip trigger tue_fail)
# --------------------------------------------------------------------------------------------------------------

class TueFail:
    """B8-tuesday-failure-swing-flip (cc07_004 ~11:30; one FX example, so start as a tag): evaluated at a Tuesday's close (session k, the Monday k-1 being a session of the same week). -1 when Tuesday's
    high is above Monday's high, within `tol` (eq_tol_pts x 4) of a prior daily pivot high, weekly pivot high or monthly high (the prior completed months and the month so far), and Tuesday closed below
    Monday's close and in the lower third of its own range [our interpretation of 'broke down']: the state becomes -1 for Wed-Fri (the caller reverts it at the week's end). +1 for the mirror (a lower
    low at a prior low, a close above Monday's close and in the upper third). Only pivots known by the close of Tuesday count (a 3-bar pivot needs its right neighbour)."""

    def __init__(self, d, w, tol: float):
        self.tol = float(tol)
        self.h, self.l, self.c = (d[k].values.astype(float) for k in ("high", "low", "close"))
        self.ph, self.pl = L.pivots(self.h, self.l, 1)
        pos = _pos(d)
        self.wlast = np.array([pos[t] for t in w["last"]])
        self.wh, self.wl = w.high.values.astype(float), w.low.values.astype(float)
        self.wph, self.wpl = L.pivots(self.wh, self.wl, 1)
        mo, mh, ml, mc, mlast = tf_bars(d, "M")
        self.mh, self.ml, self.mlast = mh, ml, mlast
        self.mon = d.index.to_period("M")

    def _near(self, x: float, levels) -> bool:
        return any(abs(x - v) <= self.tol for v in levels)

    def step(self, k: int) -> int:
        h, l, c = self.h, self.l, self.c
        if k < 2:
            return 0
        rng = h[k] - l[k]
        if rng <= 0:
            return 0
        dh = [p.price for p in self.ph if p.known <= k and p.i <= k - 2]
        dl = [p.price for p in self.pl if p.known <= k and p.i <= k - 2]
        nw = int(np.searchsorted(self.wlast, k, side="left"))                 # weeks completed before Tuesday
        wh_ = [p.price for p in self.wph if p.known <= nw - 1]
        wl_ = [p.price for p in self.wpl if p.known <= nw - 1]
        nm = int(np.searchsorted(self.mlast, k, side="left"))
        a0 = next((q for q in range(k, -1, -1) if q == 0 or self.mon[q - 1] != self.mon[k]), 0)
        mh_ = list(self.mh[:nm]) + ([float(h[a0:k].max())] if a0 < k else [])
        ml_ = list(self.ml[:nm]) + ([float(l[a0:k].min())] if a0 < k else [])
        if h[k] > h[k - 1] and c[k] < c[k - 1] and c[k] <= l[k] + rng / 3 and self._near(float(h[k]), dh + wh_ + mh_):
            return -1
        if l[k] < l[k - 1] and c[k] > c[k - 1] and c[k] >= h[k] - rng / 3 and self._near(float(l[k]), dl + wl_ + ml_):
            return 1
        return 0


# --------------------------------------------------------------------------------------------------------------
# items 177 / 179 / 180: the per-timeframe B10 test, the case-specific cancel, the case C -> B upgrade
# --------------------------------------------------------------------------------------------------------------

def tf_state3(o, h, l, c, arrs_tf, mult: float = 1.5, nbar: int = 10) -> np.ndarray:
    """X3-b10-tf-test (cc06_004 ~3:13; cc06_005 ~1:15): per bar j the state of a timeframe after the bar completes - +1 when the LAST array touch (a bar whose range reached an array of the timeframe known
    by then; the nearest to the close when several) was a discount (bull) array and a displacement bar followed it (the touch bar itself included [our interpretation]: range >= `mult` x the mean range of
    the previous `nbar` bars with the close in the top third); -1 for the bearish mirror; the state holds until the other side's own touch + displacement turns it. `arrs_tf` carry `known` in this
    timeframe's own bar units."""
    n = len(c)
    st = np.zeros(n, int)
    last, cur = 0, 0
    for j in range(n):
        best = None
        for a in arrs_tf:
            if a.known <= j and l[j] <= a.top and h[j] >= a.bottom:
                dist = abs(c[j] - a.ce)
                if best is None or dist < best[0]:
                    best = (dist, 1 if a.kind == "bull" else -1)
        if best is not None:
            last = best[1]                                          # the last array touched sets which displacement counts; a touch of the other side does not erase the standing state
        if last and j >= 1:
            rng = h[j] - l[j]
            lo_ = max(0, j - nbar)
            mean = float((h[lo_:j] - l[lo_:j]).mean())
            if mean > 0 and rng >= mult * mean:
                if last > 0 and c[j] >= l[j] + 2.0 * rng / 3.0:
                    cur = 1
                elif last < 0 and c[j] <= l[j] + rng / 3.0:
                    cur = -1
        st[j] = cur
    return st


def hh_hl_series(h, l) -> np.ndarray:
    """Per bar j (the state after bar j completes): +1 when the last two known 3-bar pivot highs AND the last two pivot lows are rising (HH / HL), -1 when both pairs are falling (LH / LL), else 0."""
    n = len(h)
    ph, pl = L.pivots(h, l, 1)
    out = np.zeros(n, int)
    for j in range(n):
        a = [p.price for p in ph if p.known <= j]
        b = [p.price for p in pl if p.known <= j]
        if len(a) >= 2 and len(b) >= 2:
            if a[-1] > a[-2] and b[-1] > b[-2]:
                out[j] = 1
            elif a[-1] < a[-2] and b[-1] < b[-2]:
                out[j] = -1
    return out


def iof_state_series(o, h, l, c) -> np.ndarray:
    """bh1e.iof_state (item 43) after each bar: a close above the high of the last up-close candle is bullish, below the low of the last down-close candle bearish; holds until the opposite event."""
    n = len(c)
    out = np.zeros(n, int)
    up_hi = dn_lo = None
    st = 0
    for j in range(n):
        if up_hi is not None and c[j] > up_hi:
            st = 1
        elif dn_lo is not None and c[j] < dn_lo:
            st = -1
        if c[j] > o[j]:
            up_hi = h[j]
        elif c[j] < o[j]:
            dn_lo = l[j]
        out[j] = st
    return out


def breaker_cancel(o, h, l, c, j_end: int, g: int) -> bool:
    """X3-b10-cancel-condition (cc06_004 ~5:51; cc06_005 ~2:52): at the last completed bar `j_end` of the case's timeframe (daily for case B, weekly for C), for a bullish sequential (g = +1): a bar t made a
    new high above the latest known pivot high (a higher high) and a later bar closed below the pivot low that preceded it (the high was rejected and the market structure broke: a bearish breaker), with
    no close back above that high since [our interpretation of 'a bearish breaker forming']. g = -1 mirrors it with lower lows and bullish breakers."""
    ph, pl = L.pivots(h, l, 1)
    piv_hi, piv_lo = (ph, pl) if g > 0 else (pl, ph)               # the extreme side first
    ext = h if g > 0 else l
    far = l if g > 0 else h
    for t in range(j_end, max(2, j_end - 60), -1):
        ref = [p for p in piv_hi if p.known <= t - 1 and p.i < t]
        if not ref:
            continue
        broke = ext[t] > ref[-1].price if g > 0 else ext[t] < ref[-1].price
        if not broke:
            continue
        opp = [p for p in piv_lo if p.known <= t - 1 and p.i < t]
        if not opp:
            continue
        lvl = opp[-1].price
        q = next((x for x in range(t + 1, j_end + 1) if (c[x] < lvl if g > 0 else c[x] > lvl)), None)
        if q is None:
            continue
        back = any((c[x] > ext[t]) if g > 0 else (c[x] < ext[t]) for x in range(q + 1, j_end + 1))
        if not back:
            return True
    return False


def case_c_to_b(m_arrs, w_arrs, wo, wc, wh, wl, wlast, k: int, px: float, g: int) -> bool:
    """X3-b10-case-c-to-b-upgrade (cc06_004 ~17:29): price (the row's price) is inside a monthly array of the sequential's side (a bull array for g = +1) and a weekly OB of that side inside the monthly
    zone has been traded into by a completed weekly bar that closed up (down for g = -1): it reacted, so month and week agree."""
    kind = "bull" if g > 0 else "bear"
    for m in m_arrs:
        if m.kind != kind or m.known > k or not (m.bottom <= px <= m.top):
            continue
        for a in w_arrs:
            if a.typ != "ob" or a.kind != kind or a.known > k or a.bottom < m.bottom - 1e-9 or a.top > m.top + 1e-9:
                continue
            for j in range(len(wlast)):
                if wlast[j] >= k or wlast[j] < a.known - 1:
                    continue
                if wl[j] <= a.top and wh[j] >= a.bottom and ((wc[j] > wo[j]) if g > 0 else (wc[j] < wo[j])):
                    return True
    return False


def dcandle_levels(o, h, l, c, k: int, g: int) -> tuple:
    """X3-b10-case-c-to-b-upgrade: for a bullish case B (g = +1) the open and the high of every daily DOWN-close candle since the correction began (the sessions after the last known daily pivot high, up to the
    prior session k-1); the mirror uses the up-close candles' open and low. Levels, not zones."""
    ph, pl = L.pivots(h, l, 1)
    piv = [p for p in (ph if g > 0 else pl) if p.known <= k - 1]
    if not piv:
        return ()
    out = []
    for j in range(piv[-1].i + 1, k):
        if g > 0 and c[j] < o[j]:
            out += [float(o[j]), float(h[j])]
        elif g < 0 and c[j] > o[j]:
            out += [float(o[j]), float(l[j])]
    return tuple(out)


def needs_dsmt(p) -> bool:
    """The switches that read the daily index SMT map (backtest.run with a partner): season_qualified, mo_bias_gate, fall_low_bias, season_poised and the weekly / daily checklist composers."""
    return bool(p.season_qualified or p.mo_bias_gate or p.fall_low_bias or p.season_poised or p.htf_bias in ("week_check", "wd_check"))
