"""Caption-gap pass, package bias_htf#2/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 83-86, 93, 95, 96, 104-106, 108, 109, 114, 116, 117, 122, 130-136, 138) - TABLE SIDE.

The daily / weekly / monthly columns and flip hooks these switches need. Everything here is a pure function of COMPLETED daily / weekly / monthly candles (sessions before the row's day) and of the
arrays `htf.table` already built (`Arr`: `known` = the first session index at which an array may be used); a value in the row of session k never reads session k or later. The engine side (side
gates, lock adjustments, scalps, sizes, tags) is `bh2e.py`. `bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b2"; `finish` runs at the end of `htf.table`
(after the flip column), `oneway_arrays` adds the E4 arrays before the row loop, `flip_cfg` is the block `htf._flip` reads for the pd3 switches. Thresholds the sources never give are marked
[our interpretation]; every rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  q_days / q_window / shift_due            (items 84, 134)   sessions since the last daily MSS; q_window = q_window_lo <= q_days <= q_window_hi; shift_due = q_days >= 126 with a one-way 126-session move
  last_break / eq_near / last_break_m / eq_near_m (108)       the direction of the most recent daily (monthly) pivot broken by a close; the prior close within eq_tie_frac of the 20-session (12-month) range EQ
  qshift / qs_form / qs_scalp / q_obj      (items 83, 131, 133, 132) the quarterly shift state (+1 / -1), its form ("consol" / "retrace"), the 20 scalp sessions of a consolidation form, the weekly array objective
  iof_w                                    (85)              the B6 score on completed weekly bars
  sibi_dir / sibi_top / sibi_bot           (86)              the nearest daily FVG formed after the last daily sweep (bear after a sell-side sweep = -1, bull after a buy-side sweep = +1)
  wk_q75                                   (96)              +1 / -1 after a daily close this week beyond the prior week's wick 75 % level
  consol_prior / raid_profile              (104, 114)        the strongest day since the previous range / the last N ranges' raid-then-exit profile (needs the drange columns)
  after_draw_d / after_draw_w / fast_draw / fast_next (105, 93) the reverse side after a daily / weekly array draw was hit; a fast weekly draw and the next weekly array beyond it
  eq20_body                                (106)             the EQ of the 20-session body range
  tier_regime / tier_ith                   (109)             -1 / +1 swing-tier regime and the defended intermediate-term high (low)
  bias_m / bias_w                          (116)             the monthly / weekly draw side
  raid_side60 / ipda_pause                 (130, 138)        the 60-session raid side; the side BLOCKED at a 60-day extreme (-1 = shorts)
  pd3_n                                    (95)              the number of supporting arrays closed through in the flip state (the first-array caution)
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import levels as L

HITS: Counter = Counter()
NAN = float("nan")
LB = 20                                               # sweeps older than this many sessions give no SIBI context (item 86) [our interpretation]


def hit(k: str) -> None:
    HITS[k] += 1


def sw(name: str) -> None:
    """Count one LIVE use of a switch (its code path ran with its input present in an executed run; the look-ahead coverage test requires one per switch)."""
    HITS["sw_" + name] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b2" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.q_days_tag or p.q_window_gate or p.shift_due_tag or p.q_window_size != 1.0:
        c["qd"] = [int(p.q_window_lo), int(p.q_window_hi)]
    if p.eq_tiebreak or p.ipda_draw_side:
        c["brk"] = [float(p.eq_tie_frac)]
    if p.qshift_bias or p.q_obj_lean or p.qshift_strong_consol or p.ipda_draw_side or p.mo_bias_gate:
        c["qs2"] = [float(p.qshift_strong_pct), int(p.q_obj_days), int(bool(p.ipda_draw_side)), int(bool(p.q_obj_lean or p.mo_bias_gate))]
        if p.qshift_broken == "leg":
            c["qs2"].append(1)                     # OA1029 Q236 / Q242: the broken swing = the low (high) that started the leg
        # (caption-gap MB-monthly-bias-routine, bias_htf#3/7: the quarterly objective's side is a component of mo_aligned)
    if p.iof_weekly_weight:
        c["iofw"] = [int(p.iof_w_weeks), int(p.iof_min)]
    if p.sibi_gate:
        c["sibi"] = 1
    if p.wk_q75_confirm:
        c["q75"] = 1
    if p.consol_dir == "prior_strongest":
        c["cd"] = 1
    if p.raid_profile_bias:
        c["rp"] = int(p.raid_profile_n)
    if p.htf_after_draw == "reverse":
        c["ad"] = 1
    if p.fast_draw_extend:
        c["fd"] = float(p.fast_draw_mult)
    if p.pd_two_level:
        c["eq20"] = int(p.pd_day_range)
    if p.tier_regime_gate or p.tug_required:
        c["tier"] = [p.tier_stl_mode]
    if p.htf_bias_tf != "D" or p.htf_rank_tf:
        c["btf"] = [int(bool(p.htf_bias_pools)), int(p.htf_bias_tf != "D"), int(bool(p.htf_rank_tf))]
    if p.flip_terminus:
        c["term"] = int(p.flip_max_days)
    if p.oneway_n:
        c["ow"] = int(p.oneway_n)
    if p.raid_side_gate:
        c["rs"] = float(p.raid_ratio)
    if p.ipda_extreme_pause:
        c["ipz"] = 1
    if p.first_clue_neutral:
        c["fcn"] = 1
    fl: dict = {}
    if p.pd3_result == "neutral" and "flip_pd3" in p.flip_triggers:   # OA1029: the neutral default only shapes the table when flip_pd3 runs
        fl["pd3n"] = float(p.pd3_disp_adr)
    if p.pd3_first_caution:
        fl["pd3log"] = 1
    if fl:
        c["fl"] = fl
    return c


def flip_cfg(b2: dict | None) -> dict:
    """The part of the "b2" block `htf._flip` reads (+ the pd3 log dict the table fills)."""
    fl = dict((b2 or {}).get("fl") or {})
    if fl.get("pd3log"):
        fl["pd3_log"] = {}
    return fl


# --------------------------------------------------------------------------------------------------------------
# swing structure helpers
# --------------------------------------------------------------------------------------------------------------

def pivot_levels(h, l) -> tuple:
    """For each session j the latest daily pivot high / low price (3-bar pivots) KNOWN before session j (known <= j-1); NaN when none."""
    D = len(h)
    ph, pl = L.pivots(h, l, 1)
    last_h = np.full(D, NAN)
    last_l = np.full(D, NAN)
    a = b = 0
    ch = cl = NAN
    for j in range(D):
        while a < len(ph) and ph[a].known <= j - 1:
            ch = ph[a].price
            a += 1
        while b < len(pl) and pl[b].known <= j - 1:
            cl = pl[b].price
            b += 1
        last_h[j], last_l[j] = ch, cl
    return last_h, last_l


def break_stream(h, l, c) -> tuple:
    """Per session j: (ev, mss, last_dir, last_mss) - ev[j] = +1 / -1 when session j CLOSED above the latest known pivot high / below the latest known pivot low that was not already broken
    (3-bar pivots, known before j); mss[j] = that break is in the opposite direction to the previous break (a market structure shift); last_dir[j] = the direction of the most recent break through j;
    last_mss[j] = the session of the most recent MSS through j (-1 none)."""
    D = len(c)
    ph, pl = L.pivots(h, l, 1)
    ev = np.zeros(D, int)
    mss = np.zeros(D, bool)
    last_dir = np.zeros(D, int)
    last_mss = np.full(D, -1)
    a = b = 0
    cur_h = cur_l = NAN
    bh = bl = True
    prev = 0
    lm = -1
    for j in range(D):
        while a < len(ph) and ph[a].known <= j - 1:
            cur_h, bh = ph[a].price, False
            a += 1
        while b < len(pl) and pl[b].known <= j - 1:
            cur_l, bl = pl[b].price, False
            b += 1
        up = (not bh) and cur_h == cur_h and c[j] > cur_h
        dn = (not bl) and cur_l == cur_l and c[j] < cur_l
        if up and dn:
            up, dn = (c[j] >= (cur_h + cur_l) / 2), (c[j] < (cur_h + cur_l) / 2)
        if up:
            ev[j], bh = 1, True
        elif dn:
            ev[j], bl = -1, True
        if ev[j]:
            if prev and ev[j] != prev:
                mss[j] = True
                lm = j
            prev = ev[j]
        last_dir[j] = prev
        last_mss[j] = lm
    return ev, mss, last_dir, last_mss


def _row_state(arr, ks, fill=0):
    """The value known before the row's session k = arr[k-1] (fill when k = 0)."""
    ks = np.asarray(ks)
    out = np.where(ks >= 1, np.asarray(arr)[np.maximum(ks - 1, 0)], fill)
    return out


# --------------------------------------------------------------------------------------------------------------
# items 84 / 134: the time since the last daily MSS
# --------------------------------------------------------------------------------------------------------------

SHIFT_ONEWAY = 0.6                         # X3-shift-due-six-months [our interpretation]: a 126-session move is one-directional when its net change is >= 60 % of the closes' high-low range


def q_columns(h, l, c, ks, lo: int, hi: int) -> dict:
    """B22-timing-tool (cc05_001 ~35:25-37:51): q_days = sessions since the last daily MSS (-1 none), q_window = lo <= q_days <= hi [our interpretation: the last third of the 60-session cast];
    X3-shift-due-six-months (cc05_001 ~48:36): shift_due = q_days >= 126 and the 126-session net move is one-directional (the net change of the last 126 closes is >= SHIFT_ONEWAY of their high-low range)."""
    ev, mss, ld, lm = break_stream(h, l, c)
    last = _row_state(lm, ks, -1)
    ks_ = np.asarray(ks)
    qd = np.where(last >= 0, ks_ - last, -1)
    out = dict(q_days=qd, q_window=((qd >= lo) & (qd <= hi)).astype(int))
    due = np.zeros(len(ks_), int)
    for r, k in enumerate(ks_):
        if qd[r] >= 126 and k >= 127:
            seg = c[k - 127:k]                                                 # the last 126 closes' moves (k-127 .. k-1)
            rng = float(seg.max() - seg.min())
            if rng > 0 and abs(float(seg[-1] - seg[0])) >= SHIFT_ONEWAY * rng:   # one-directional: the net move covers most of the range [our interpretation]
                due[r] = 1
    out["shift_due"] = due
    return out


def break_columns(h, l, c, ks, frac: float, d=None) -> dict:
    """B3-eq-recent-structure-break (cc01_006 ~7:29; cc05_015 ~5:09): last_break = the direction (+1 / -1) of the most recent daily pivot broken by a close; eq_near = the prior close is within
    `frac` of the 20-session range (high-low) of that range's EQ [our interpretation of "at the EQ"]. The monthly pair (last_break_m / eq_near_m) uses completed monthly bars and the 12-month range."""
    ev, mss, ld, lm = break_stream(h, l, c)
    ks_ = np.asarray(ks)
    out = dict(last_break=_row_state(ld, ks_, 0))
    near = np.zeros(len(ks_), int)
    for r, k in enumerate(ks_):
        if k >= 20:
            hi_, lo_ = h[k - 20:k].max(), l[k - 20:k].min()
            if hi_ > lo_ and abs(c[k - 1] - (hi_ + lo_) / 2) <= frac * (hi_ - lo_):
                near[r] = 1
    out["eq_near"] = near
    if d is not None:
        from .htf import months
        m = months(d)
        lbm = np.zeros(len(ks_), int)
        nm = np.zeros(len(ks_), int)
        if len(m) >= 5:
            mh, ml, mc = (m[k].values.astype(float) for k in ("high", "low", "close"))
            _, _, mld, _ = break_stream(mh, ml, mc)
            pos = {t: q for q, t in enumerate(d.index)}
            mlast = np.array([pos[t] for t in m["last"]])
            for r, k in enumerate(ks_):
                n = int(np.searchsorted(mlast, k, side="left"))              # completed months: last session < k
                if n >= 1:
                    lbm[r] = mld[n - 1]
                if n >= 12:
                    hi_, lo_ = mh[n - 12:n].max(), ml[n - 12:n].min()
                    if hi_ > lo_ and abs(c[k - 1] - (hi_ + lo_) / 2) <= frac * (hi_ - lo_):
                        nm[r] = 1
        out["last_break_m"], out["eq_near_m"] = lbm, nm
    return out


# --------------------------------------------------------------------------------------------------------------
# items 131 / 133 / 132 / 83: the quarterly shift, its form and its objective
# --------------------------------------------------------------------------------------------------------------

def qshift_columns(h, l, c, arrs, ks, strong_pct: float = 0.10, obj_days: int = 84, ipda: bool = False, want_obj: bool = False, leg: bool = False) -> dict:
    """X3-b22-shift-trigger-quarter-bias (cc05_001 ~32:36; cc05_004 ~16:53; cc05_003 ~16:01): a new 60-session high made within the last 10 sessions and then a daily low under the last daily STL
    (levels.swing_tiers "stl", known before the session) = a bearish quarterly shift (qshift -1): it holds for 63 sessions or until a new 60-session high; the mirror (a new 60-session low, then a daily
    high above the last STH) is +1. X3-b21-draw-side-and-flip (cc05_003 ~1:24:00, `ipda`): a bullish daily MSS within 10 sessions of a 20-day-low raid that stopped short of the 40-day low is +1 too (mirror
    -1). X3-b22-shift-form-strong-trend (cc05_001 ~7:35): the shift is "consol" when the close is more than `strong_pct` beyond its 252-session mean on the OTHER side (a shift against a strong primary
    trend), else "retrace"; qs_scalp = 1 for the 20 sessions after a consolidation-form shift. B22-quarterly-shift (084 ~22:18, `want_obj`): q_obj = the near edge of the nearest weekly FVG in the
    shift's direction beyond the 60-session range (the weekly bull FVG below for a bearish shift), kept until it is traded, `obj_days` sessions pass or a new 60-session extreme cancels the shift."""
    D = len(c)
    new_hi = np.zeros(D, bool)
    new_lo = np.zeros(D, bool)
    for j in range(60, D):
        new_hi[j] = h[j] > h[j - 60:j].max()
        new_lo[j] = l[j] < l[j - 60:j].min()
    tiers = L.swing_tiers(h, l, 1)
    sth, stl = tiers["stl"]
    ev, mss, ld, lm = break_stream(h, l, c)
    wk = [a for a in arrs if a.tf == "W" and a.typ == "fvg"]
    st = np.zeros(D, int)
    form = [""] * D
    scalp = np.zeros(D, int)
    qobj = np.full(D, NAN)
    cur, at, fm = 0, -1, ""
    qo = None
    a_h = a_l = 0
    cs_h = cs_l = NAN
    for j in range(D):
        while a_h < len(sth) and sth[a_h].known <= j - 1:
            cs_h = sth[a_h].price
            a_h += 1
        while a_l < len(stl) and stl[a_l].known <= j - 1:
            cs_l = stl[a_l].price
            a_l += 1
        if cur != 0 and (j - at >= 63 or (cur < 0 and new_hi[j]) or (cur > 0 and new_lo[j])):
            if qo is not None and ((cur < 0 and new_hi[j]) or (cur > 0 and new_lo[j])):
                qo = None                                              # [our interpretation] a new 60-session extreme against the shift cancels its objective too
            cur, fm = 0, ""
        fire = 0
        if leg:                                                        # OA1029 Q236 / Q242 [our interpretation]: the swing low that STARTED the leg to the new 60-session high
            ref_l = ref_h = NAN                                        # = the lowest low of the 60 sessions before that high (the mirror for a new low); only sessions before j
            mh = np.flatnonzero(new_hi[max(0, j - 10):j])
            if len(mh):
                m_ = max(0, j - 10) + int(mh[-1])
                ref_l = float(l[max(0, m_ - 60):m_].min()) if m_ > 0 else NAN
            ml = np.flatnonzero(new_lo[max(0, j - 10):j])
            if len(ml):
                m_ = max(0, j - 10) + int(ml[-1])
                ref_h = float(h[max(0, m_ - 60):m_].max()) if m_ > 0 else NAN
        else:
            ref_l, ref_h = cs_l, cs_h                                  # literal: the latest daily STL / STH
        if ref_l == ref_l and new_hi[max(0, j - 10):j].any() and l[j] < ref_l:
            fire = -1
        if ref_h == ref_h and new_lo[max(0, j - 10):j].any() and h[j] > ref_h:
            fire = 1 if fire == 0 else 0
        if fire == 0 and ipda and ev[j] and mss[j] and j >= 41:
            if ev[j] > 0:                                              # a 20-day-low raid short of the 40-day low, then the bullish MSS
                raid = any(l[m] < l[m - 20:m].min() and l[m] > l[m - 40:m].min() for m in range(max(41, j - 10), j))
                fire = 1 if raid else 0
            else:
                raid = any(h[m] > h[m - 20:m].max() and h[m] < h[m - 40:m].max() for m in range(max(41, j - 10), j))
                fire = -1 if raid else 0
        if fire and fire != cur:
            cur, at = fire, j
            dev = (c[j] / c[j - 251:j + 1].mean() - 1.0) if j >= 251 else 0.0
            fm = "consol" if ((fire < 0 and dev > strong_pct) or (fire > 0 and dev < -strong_pct)) else "retrace"
            hit("qshift_" + fm)
            if want_obj:
                qo = None
                if fire < 0:
                    lo60 = l[max(0, j - 59):j + 1].min()
                    cs = [a for a in wk if a.kind == "bull" and a.known <= j + 1 and a.top < lo60 and c[a.known:j + 1].min(initial=np.inf) >= a.bottom]
                    if cs:
                        a = max(cs, key=lambda x: x.top)
                        qo = dict(level=float(a.top), side=-1, at=j)
                else:
                    hi60 = h[max(0, j - 59):j + 1].max()
                    cs = [a for a in wk if a.kind == "bear" and a.known <= j + 1 and a.bottom > hi60 and c[a.known:j + 1].max(initial=-np.inf) <= a.top]
                    if cs:
                        a = min(cs, key=lambda x: x.bottom)
                        qo = dict(level=float(a.bottom), side=1, at=j)
        if qo is not None and j > qo["at"]:
            if j - qo["at"] >= obj_days or (qo["side"] < 0 and l[j] <= qo["level"]) or (qo["side"] > 0 and h[j] >= qo["level"]):
                qo = None
        st[j] = cur
        form[j] = fm if cur else ""
        scalp[j] = int(bool(cur) and fm == "consol" and j - at < 20)
        qobj[j] = qo["level"] if qo is not None else NAN
    ks_ = np.asarray(ks)
    return dict(qshift=_row_state(st, ks_, 0), qs_form=np.array([form[k - 1] if k >= 1 else "" for k in ks_], dtype=object), qs_scalp=_row_state(scalp, ks_, 0),
                q_obj=_row_state(qobj, ks_, NAN).astype(float))


# --------------------------------------------------------------------------------------------------------------
# item 85: the weekly B6 score
# --------------------------------------------------------------------------------------------------------------

def iof_w_column(d, w, ks, weeks: int, mn: int) -> np.ndarray:
    """B6-weekly-iof (cc12_002 ~16:34): the candle-respect score of bias_htf.iof_score on the last `weeks` COMPLETED weekly bars (weeks whose last session is before the row's session); +1 / -1 at
    |score| >= mn, else 0."""
    from .bias_htf import iof_score
    pos = {t: q for q, t in enumerate(d.index)}
    wlast = np.array([pos[t] for t in w["last"]])
    wo, wh, wl, wc = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        kw = int(np.searchsorted(wlast, k, side="left"))
        if kw >= 3:
            s = iof_score(wo, wh, wl, wc, kw, weeks)
            out[r] = 1 if s >= mn else (-1 if s <= -mn else 0)
    return out


# --------------------------------------------------------------------------------------------------------------
# item 86: the daily SIBI / BISI after a daily sweep
# --------------------------------------------------------------------------------------------------------------

def sibi_columns(o, h, l, c, arrs, ks, px) -> dict:
    """NEW-daily-sibi-bias-gate (086 ~2:22, ~12:30): the latest daily sell-side sweep (a low under the latest known daily pivot low) within LB sessions gives the nearest alive daily BEAR FVG that
    formed after it (sibi_dir -1, sibi_top / sibi_bot); the latest buy-side sweep gives the nearest alive daily BULL FVG formed after it (+1). Both on the same session or none: 0. 'Nearest' = the
    smallest distance from the row's price to the zone, then the later one."""
    from .bh1 import _alive_d
    last_h, last_l = pivot_levels(h, l)
    with np.errstate(invalid="ignore"):
        sell = l < last_l
        buy = h > last_h
    fv = [a for a in arrs if a.tf == "D" and a.typ == "fvg"]
    n = len(ks)
    dr = np.zeros(n, int)
    top = np.full(n, NAN)
    bot = np.full(n, NAN)
    for r, k in enumerate(ks):
        lo_ = max(0, k - LB)
        js = next((j for j in range(k - 1, lo_ - 1, -1) if sell[j]), None)
        jb = next((j for j in range(k - 1, lo_ - 1, -1) if buy[j]), None)
        if js is None and jb is None:
            continue
        if js is not None and jb is not None:
            if js == jb:
                continue
            side = -1 if js > jb else 1
        else:
            side = -1 if js is not None else 1
        j = js if side < 0 else jb
        want = "bear" if side < 0 else "bull"
        cs = [a for a in fv if a.kind == want and j < a.known <= k and _alive_d(a, k, o, c)]
        if not cs:
            continue
        x = px[r]
        dist = lambda a: 0.0 if a.bottom <= x <= a.top else min(abs(x - a.top), abs(x - a.bottom))
        a = min(cs, key=lambda z: (dist(z), -z.known))
        dr[r], top[r], bot[r] = side, a.top, a.bottom
    return dict(sibi_dir=dr, sibi_top=top, sibi_bot=bot)


# --------------------------------------------------------------------------------------------------------------
# item 96: the prior weekly wick's 75 % quadrant
# --------------------------------------------------------------------------------------------------------------

def q75_column(d, w, ks, c) -> np.ndarray:
    """B8-weekly-wick-quadrant-gate (102 ~2:11:40; 103 ~0:02:32): +1 when a daily close of THIS week (a session before the row's) is above the prior completed week's upper wick 75 % level (body
    top + 0.75 x the upper wick), -1 when below its lower wick 75 % level (body bottom - 0.75 x the lower wick), 0 otherwise (the later close wins)."""
    pos = {t: q for q, t in enumerate(d.index)}
    wlast = np.array([pos[t] for t in w["last"]])
    wo, wh, wl, wc = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    wk = d.index.to_period("W-FRI")
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        k0 = k
        while k0 > 0 and wk[k0 - 1] == wk[k]:
            k0 -= 1
        n = int(np.searchsorted(wlast, k0, side="left"))             # weeks completed before this week started
        if n < 1 or k0 >= k:
            continue
        bt, bb = max(wo[n - 1], wc[n - 1]), min(wo[n - 1], wc[n - 1])
        up_lvl = bt + 0.75 * (wh[n - 1] - bt)
        dn_lvl = bb - 0.75 * (bb - wl[n - 1])
        v = 0
        for j in range(k0, k):
            if c[j] > up_lvl:
                v = 1
            elif c[j] < dn_lvl:
                v = -1
        out[r] = v
    return out


# --------------------------------------------------------------------------------------------------------------
# items 104 / 114: the daily ranges' leg and raid profile
# --------------------------------------------------------------------------------------------------------------

def range_events(h, l, c, n: int, brk: str = "close") -> list:
    from .bh1 import drange_states
    ev: list = []
    drange_states(h, l, c, n, brk, ev)
    return ev


def consol_prior_column(o, h, l, c, ks, events: list) -> np.ndarray:
    """N8-consolidation-breakout-direction (cc01_006 ~18:37): while the row sits in a daily range, the direction (+1 / -1) of the largest-range day between the PREVIOUS range's breakout and the current
    range's first session (the strongest prior move out of consolidation); the previous range's exit direction when there is no such day; 0 outside a range or without a previous range."""
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        j = k - 1
        cur = None
        for e in events:
            if e["f"] <= j and (e["b"] is None or e["b"] > j):
                cur = e
        if cur is None:
            continue
        prev = [e for e in events if e["b"] is not None and e["b"] < cur["a"]]
        if not prev:
            continue
        pe = prev[-1]
        seg = list(range(pe["b"], cur["a"]))
        if not seg:
            out[r] = pe["dir"]
            continue
        m = max(seg, key=lambda q: h[q] - l[q])
        s = int(np.sign(c[m] - o[m]))
        out[r] = s if s else pe["dir"]
    return out


def raid_profile_column(h, l, ks, events: list, n: int) -> np.ndarray:
    """B6-consolidation-raid-profile (cc02_008 ~14:28): +1 when the last `n` COMPLETED ranges (breakout session before the row) each raided the LOW first (a session between the range's formation and its
    breakout with a low under the range) and then exited up; -1 for the mirror (high raided first, exit down); 0 otherwise. A session raiding both sides first gives no profile."""
    prof = []
    for e in events:
        if e["b"] is None:
            prof.append((None, 0))
            continue
        first = 0
        for m in range(e["f"] + 1, e["b"] + 1):
            lo_hit, hi_hit = l[m] < e["lo"], h[m] > e["hi"]
            if lo_hit and hi_hit:
                first = 0
                break
            if lo_hit or hi_hit:
                first = -1 if lo_hit else 1                            # -1: the low was raided first
                break
        pf = 1 if (first == -1 and e["dir"] > 0) else (-1 if (first == 1 and e["dir"] < 0) else 0)
        prof.append((e["b"], pf))
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        done = [pf for b, pf in prof if b is not None and b <= k - 1]
        if len(done) >= n and all(x == 1 for x in done[-n:]):
            out[r] = 1
        elif len(done) >= n and all(x == -1 for x in done[-n:]):
            out[r] = -1
    return out


# --------------------------------------------------------------------------------------------------------------
# item 105 / 93: after the draw is hit
# --------------------------------------------------------------------------------------------------------------

def _htf_array_name(nm: str) -> bool:
    """A daily / weekly PD array draw ('D_fvg', 'W_fvg', '*_ob', '*_vi'), not a swing / previous-extreme pool."""
    return isinstance(nm, str) and nm.split("_", 1)[-1] in ("fvg", "ob", "vi") and nm[:1] in ("D", "W")


def _week_objective(out, r0: int, px) -> tuple:
    """The week's objective chosen at the week's first row r0: (side, level, name) of the nearest weekly-class draw, else None (the htf_bias B17.3 rule)."""
    if "wk_draw_up" not in out:
        return None
    a_, b_ = out.wk_draw_up.values[r0], out.wk_draw_dn.values[r0]
    cand = [(abs(x - px[r0]), s_, x) for s_, x in ((1, a_), (-1, b_)) if x == x]
    if not cand:
        return None
    _, s_, x = min(cand)
    nm = (out.wk_draw_up_n if s_ > 0 else out.wk_draw_dn_n).values[r0]
    return s_, float(x), nm


def after_draw_columns(out: pd.DataFrame, px) -> dict:
    """B17-after-draw-retrace-or-reverse (cc01_002 ~18:49; cc07_007 ~23:55; cc10_013 ~6:27; cc03_002 ~10:14): after the day's (obj_day) / the week's (obj_week) draw was hit AT a daily / weekly array
    the reverse side is the opposite of the draw's side: after_draw_d / after_draw_w (0 when the draw was a swing / previous-extreme pool or nothing was hit). Needs the B17.3 columns."""
    n = len(out)
    ad = np.zeros(n, int)
    aw = np.zeros(n, int)
    if "obj_day" in out:
        for r in range(1, n):
            if out.obj_day.values[r]:
                side = int(out.draw.values[r - 1])
                nm = (out.draw_up_name if side > 0 else out.draw_dn_name).values[r - 1] if side else ""
                if side and _htf_array_name(nm):
                    ad[r] = -side
    if "obj_week" in out and "wk_draw_up" in out:
        wk = [pd.Timestamp(x).to_period("W-FRI") for x in out.index]
        first = {}
        for r in range(n):
            first.setdefault(wk[r], r)
        for r in range(n):
            if out.obj_week.values[r]:
                ob = _week_objective(out, first[wk[r]], px)
                if ob is not None and str(ob[2]).startswith("W_") and _htf_array_name(ob[2]):
                    aw[r] = -ob[0]
    return dict(after_draw_d=ad, after_draw_w=aw)


def fast_draw_columns(out: pd.DataFrame, d, w, arrs, ks, px, mult: float) -> dict:
    """NEW-speed-into-weekly-draw (095 ~8:01): the week's objective (obj_week = 1, the nearest weekly-class draw at the week's first row) was reached at >= `mult` x the speed of the previous leg
    [our interpretation: speed = the distance from the last CONFIRMED weekly pivot (low for an up draw) to the objective over the weeks since that pivot; the previous leg = the opposite pivot before
    it to this pivot over its weeks]. fast_draw = the objective's side, fast_next = the near edge of the nearest weekly FVG beyond the objective (NaN when none: the extension has no target, so the
    ordinary neutral applies)."""
    n = len(out)
    fd = np.zeros(n, int)
    fx = np.full(n, NAN)
    if "obj_week" not in out or "wk_draw_up" not in out:
        return dict(fast_draw=fd, fast_next=fx)
    wh, wl = w.high.values.astype(float), w.low.values.astype(float)
    ph, pl = L.pivots(wh, wl, 1)
    pos = {t: q for q, t in enumerate(d.index)}
    wlast = np.array([pos[t] for t in w["last"]])
    wk = [pd.Timestamp(x).to_period("W-FRI") for x in out.index]
    first = {}
    for r in range(n):
        first.setdefault(wk[r], r)
    wfv = [a for a in arrs if a.tf == "W" and a.typ == "fvg"]
    for r in range(n):
        if not out.obj_week.values[r]:
            continue
        ob = _week_objective(out, first[wk[r]], px)
        if ob is None:
            continue
        s_, lv, _ = ob
        k = ks[r]
        wi = int(np.searchsorted(wlast, k, side="left"))             # the weeks completed before the row; the current week is wi
        same, opp = (pl, ph) if s_ > 0 else (ph, pl)                  # an up draw runs from a pivot LOW; the previous leg came down from a pivot HIGH
        a1 = [q for q in same if q.known <= wi - 1]
        if not a1:
            continue
        p1 = a1[-1]
        a2 = [q for q in opp if q.i < p1.i and q.known <= wi - 1]
        if not a2:
            continue
        p0 = a2[-1]
        dist1, wks1 = abs(lv - p1.price), max(wi - p1.i, 1)
        dist0, wks0 = abs(p1.price - p0.price), max(p1.i - p0.i, 1)
        if dist0 <= 0 or (dist1 / wks1) < mult * (dist0 / wks0):
            continue
        if s_ > 0:
            cs = [a.bottom for a in wfv if a.known <= k and a.bottom > lv]
            nxt = min(cs) if cs else NAN
        else:
            cs = [a.top for a in wfv if a.known <= k and a.top < lv]
            nxt = max(cs) if cs else NAN
        if nxt == nxt:
            fd[r], fx[r] = s_, nxt
            hit("fast_draw")
    return dict(fast_draw=fd, fast_next=fx)


# --------------------------------------------------------------------------------------------------------------
# items 106 / 109 / 116 / 122 / 130 / 138
# --------------------------------------------------------------------------------------------------------------

def eq20_column(o, c, ks, n: int) -> np.ndarray:
    """A21-two-level-discount (cc01_004 ~30:18): the EQ of the BODY range (highest body top, lowest body bottom) of the last n completed sessions; NaN before n sessions."""
    top, bot = np.maximum(o, c), np.minimum(o, c)
    out = np.full(len(ks), NAN)
    for r, k in enumerate(ks):
        if k >= n:
            out[r] = (top[k - n:k].max() + bot[k - n:k].min()) / 2
    return out


def _stl_broken(seq, arr, k: int, mode: str, highs: bool) -> bool:
    """B6-hrlr-lrlr-structure-regime: the short-term lows (highs) being run - 'last2' (the spec): each of the last two was broken since it formed; 'two_of_four' [our interpretation]: two of the last four
    (the newest is rarely broken yet)."""
    def broken(q):
        seg = arr[q.i + 1:k]
        return (seg.max(initial=-np.inf) > q.price) if highs else (seg.min(initial=np.inf) < q.price)
    if mode == "last2":
        return all(broken(q) for q in seq[-2:])
    return sum(1 for q in seq[-4:] if broken(q)) >= 2


def tier_columns(h, l, ks, stl_mode: str = "last2") -> dict:
    """B6-hrlr-lrlr-structure-regime (cc01_007 ~19:48): tier_regime -1 when the last long-term high is unbroken, the last intermediate-term high is below the one before it and the last two short-term
    lows were broken (two of the last four: the high-resistance-rally regime); +1 for the mirror; 0 otherwise or once a session traded above the last ITH (below the last ITL). tier_ith = that defended ITH (ITL)."""
    t = L.swing_tiers(h, l, 1)
    sth, stl = t["stl"]
    ith, itl = t["itl"]
    lth, ltl = t["ltl"]
    n = len(ks)
    reg = np.zeros(n, int)
    lvl = np.full(n, NAN)

    def known(seq, k):
        return [q for q in seq if q.known <= k - 1]

    for r, k in enumerate(ks):
        if k < 6:
            continue
        bear = bull = False
        lh, ih, sl = known(lth, k), known(ith, k), known(stl, k)
        if lh and len(ih) >= 2 and len(sl) >= 2:
            ok = h[lh[-1].i + 1:k].max(initial=-np.inf) < lh[-1].price
            ok = ok and ih[-1].price < ih[-2].price and h[ih[-1].i + 1:k].max(initial=-np.inf) <= ih[-1].price
            ok = ok and _stl_broken(sl, l, k, stl_mode, False)
            bear = bool(ok)
        ll, il, sh = known(ltl, k), known(itl, k), known(sth, k)
        if ll and len(il) >= 2 and len(sh) >= 2:
            ok = l[ll[-1].i + 1:k].min(initial=np.inf) > ll[-1].price
            ok = ok and il[-1].price > il[-2].price and l[il[-1].i + 1:k].min(initial=np.inf) >= il[-1].price
            ok = ok and _stl_broken(sh, h, k, stl_mode, True)
            bull = bool(ok)
        if bear and not bull:
            reg[r], lvl[r] = -1, ih[-1].price
        elif bull and not bear:
            reg[r], lvl[r] = 1, il[-1].price
    return dict(tier_regime=reg, tier_ith=lvl)


def _tf_cands(arrs, tf: str, k: int, px: float, h, l) -> list:
    """The unrebalanced FVGs of timeframe `tf` at row k as (distance, side, level), with the htf.table rule (a bull FVG below the price is a draw down to min(top, the lowest low since); above it, a draw
    up to its bottom; bear mirrored)."""
    out = []
    for a in arrs:
        if a.tf != tf or a.typ != "fvg" or a.known > k:
            continue
        if a.kind == "bull":
            if l[a.known:k].min(initial=np.inf) <= a.bottom:
                continue
            near = min(a.top, l[a.known:k].min(initial=np.inf))
            if near < px:
                out.append((px - near, -1, float(near)))
            elif a.bottom > px:
                out.append((a.bottom - px, 1, float(a.bottom)))
        else:
            if h[a.known:k].max(initial=-np.inf) >= a.top:
                continue
            near = max(a.bottom, h[a.known:k].max(initial=-np.inf))
            if near > px:
                out.append((near - px, 1, float(near)))
            elif a.top < px:
                out.append((px - a.top, -1, float(a.top)))
    return out


def _tf_draw(arrs, tf: str, k: int, px: float, h, l):
    """(distance, side) of the nearest unrebalanced FVG of timeframe `tf` at row k, None when there is none."""
    c = _tf_cands(arrs, tf, k, px, h, l)
    if not c:
        return None
    d_, s_, _ = min(c, key=lambda x: x[0])
    return d_, s_


def btf_columns(arrs, ks, px, h, l, c, d=None, pools: bool = False, bias: bool = True, rank: bool = False) -> dict:
    """B5-monthly-first-hierarchy (cc04_003 ~14:07; cc04_002 ~29:38): bias_m / bias_w = the side of the nearest draw of the monthly / weekly timeframe - the nearest unrebalanced FVG of that
    timeframe (the literal spec: bias = sign(monthly draw - price) from the monthly arrays; htf_bias_tf 'M' takes the monthly side, else the weekly, else none). With `pools` (htf_bias_pools,
    [our interpretation], owner question) the previous completed month's (week's) high above / low below the price are draws too, like htf.table's PWH / PWL: an FVG-only reading is one-sided in a
    trend. With `rank` (htf_rank_tf) also the columns rk_<tf>_up / rk_<tf>_dn (tf D, W, M): the level of the nearest unrebalanced FVG of that timeframe above / below the price (NaN when none)."""
    from .htf import months, weeks
    pl_ = {}
    if pools and d is not None:
        pos = {t: q for q, t in enumerate(d.index)}
        for tf, bars in (("M", months(d)), ("W", weeks(d))):
            if len(bars):
                pl_[tf] = (np.array([pos[t] for t in bars["last"]]), bars.high.values.astype(float), bars.low.values.astype(float))
    n = len(ks)
    bm = np.zeros(n, int)
    bw = np.zeros(n, int)
    if bias:
        for r, k in enumerate(ks):
            for tf, out in (("M", bm), ("W", bw)):
                best = _tf_draw(arrs, tf, k, float(px[r]), h, l)
                if tf in pl_:
                    last, ph_, pll = pl_[tf]
                    q = int(np.searchsorted(last, k, side="left"))              # completed bars before the row
                    if q >= 1:
                        x = float(px[r])
                        if ph_[q - 1] > x and (best is None or ph_[q - 1] - x < best[0]):
                            best = (ph_[q - 1] - x, 1)
                        if pll[q - 1] < x and (best is None or x - pll[q - 1] < best[0]):
                            best = (x - pll[q - 1], -1)
                out[r] = best[1] if best else 0
    res = dict(bias_m=bm, bias_w=bw)
    if rank:
        for tf in ("D", "W", "M"):
            up = np.full(n, NAN)
            dn = np.full(n, NAN)
            for r, k in enumerate(ks):
                cs = _tf_cands(arrs, tf, k, float(px[r]), h, l)
                u = [x for x in cs if x[1] > 0]
                v = [x for x in cs if x[1] < 0]
                if u:
                    up[r] = min(u, key=lambda x: x[0])[2]
                if v:
                    dn[r] = min(v, key=lambda x: x[0])[2]
            res[f"rk_{tf}_up"], res[f"rk_{tf}_dn"] = up, dn
    return res


def oneway_arrays(o, h, l, c, n: int) -> list:
    """E4-daily-one-way-delivery-rebalance (cc03_007 ~23:41): an up-close day U followed by >= n consecutive down-close days: U's range is the rebalance draw (a 'bear' array, typ 'oneway', known the
    session after the n-th down day); the mirror (a down-close day then >= n up-close days) is a 'bull' array. A draw only - htf.table gives it no reaction weight."""
    from .htf import Arr
    out = []
    D = len(c)
    for u in range(D - n):
        if c[u] > o[u]:
            if all(c[u + q] < o[u + q] for q in range(1, n + 1)):
                out.append(Arr("bear", "oneway", "D", float(h[u]), float(l[u]), float((h[u] + l[u]) / 2), u + n + 1))
                sw("oneway_n")
        elif c[u] < o[u]:
            if all(c[u + q] > o[u + q] for q in range(1, n + 1)):
                out.append(Arr("bull", "oneway", "D", float(h[u]), float(l[u]), float((h[u] + l[u]) / 2), u + n + 1))
                sw("oneway_n")
    return out


def raid_side_column(h, l, ks, ratio: float) -> np.ndarray:
    """X3-iof-60day-framing-raids (cc05_001 ~26:08; cc05_004 ~23:59): over the last 60 completed sessions the highs that took a prior 20-session high against the lows that took a prior 20-session
    low: +1 when highs >= ratio x lows and highs >= 2 (bullish IOF: no shorts), -1 for the mirror, else 0 [the ratio is the bot's parameter]."""
    out = np.zeros(len(ks), int)
    D = len(h)
    nh = np.zeros(D, int)
    nl = np.zeros(D, int)
    for j in range(20, D):
        nh[j] = int(h[j] > h[j - 20:j].max())
        nl[j] = int(l[j] < l[j - 20:j].min())
    for r, k in enumerate(ks):
        a = max(20, k - 60)
        hi_n, lo_n = int(nh[a:k].sum()), int(nl[a:k].sum())
        if hi_n >= 2 and hi_n >= ratio * lo_n:
            out[r] = 1
        elif lo_n >= 2 and lo_n >= ratio * hi_n:
            out[r] = -1
    return out


def ipda_pause_column(h, l, ks) -> np.ndarray:
    """X3-60day-low-deep-discount-bounce (cc05_004 ~24:29): the side BLOCKED for the session - -1 (no shorts) when the prior session's low is within 0.25 x ADR5 of (or under) the lowest low of the last
    60 sessions, +1 (no longs) when the prior high is that close to the 60-session high; 0 otherwise or when both."""
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        if k < 6:
            continue
        adr = float((h[k - 5:k] - l[k - 5:k]).mean())
        lo60, hi60 = l[max(0, k - 60):k].min(), h[max(0, k - 60):k].max()
        a = l[k - 1] <= lo60 + 0.25 * adr
        b = h[k - 1] >= hi60 - 0.25 * adr
        out[r] = -1 if (a and not b) else (1 if (b and not a) else 0)
    return out


# --------------------------------------------------------------------------------------------------------------
# post-flip columns
# --------------------------------------------------------------------------------------------------------------

def apply_terminus(flip, draw_up, draw_dn, ks, h, l, max_days: int) -> np.ndarray:
    """B17-hold-bias-most-recent-htf-setup (cc03_001 ~21:17; cc05_002 ~22:06): the flip state ends (0) once the draw it was set with has traded (the nearest draw on its side in the first row of the state:
    draw_up for +1, draw_dn for -1) - a session after the start with a high at / above (low at / below) it - or after `max_days` sessions; it comes back when the underlying state changes."""
    flip = np.asarray(flip).astype(int)
    out = flip.copy()
    r0 = None
    tgt = NAN
    for r in range(len(flip)):
        if r == 0 or flip[r] != flip[r - 1]:
            r0 = r if flip[r] != 0 else None
            tgt = NAN
            if r0 is not None:
                tgt = float(draw_up[r] if flip[r] > 0 else draw_dn[r])
        if r0 is None:
            continue
        k0, k = ks[r0], ks[r]
        done = (k - k0 >= max_days)
        if tgt == tgt and k > k0:
            seg_h, seg_l = h[k0:k], l[k0:k]
            done = done or (bool(seg_h.max() >= tgt) if flip[r] > 0 else bool(seg_l.min() <= tgt))
        if done:
            out[r] = 0
            hit("flip_terminus")
            sw("flip_terminus")
    return out


def apply_after_draw_flip(flip, ad, aw) -> np.ndarray:
    """B17-after-draw-retrace-or-reverse (cc01_002 ~18:49; cc07_007 ~23:55): under htf_after_draw='reverse' the flip state becomes the OPPOSITE side (instead of 0) from the session the day's / week's draw was
    hit at an HTF array (after_draw_d, else after_draw_w) and stays so until the underlying flip state changes (a new trigger)."""
    flip = np.asarray(flip).astype(int)
    out = flip.copy()
    cur, base = 0, None
    for r in range(len(flip)):
        if cur and flip[r] != base:
            cur = 0
        rev = int(ad[r]) or int(aw[r])
        if rev:
            cur, base = rev, int(flip[r])
        if cur:
            out[r] = cur
    return out


def apply_first_clue(flip, clue, tug) -> np.ndarray:
    """X3-one-sided-delivery-first-clue (cc05_002 ~13:28): the first clue (first_clue = s: the first daily STL break after the HTF buy-side pool was raided; s = -1 for the sell-side flip) while the
    state is still the opposite one (-s) turns it neutral; it stays neutral until the tug of war confirms (tug == s), then the state is s; a change of the underlying state ends the wait."""
    flip = np.asarray(flip).astype(int)
    out = flip.copy()
    pend = None
    for r in range(len(flip)):
        if pend is not None and (flip[r] != pend["under"] or r == 0):
            pend = None
        if pend is None and clue[r] != 0 and flip[r] == -int(clue[r]):
            pend = dict(sign=int(clue[r]), under=int(flip[r]))
            hit("first_clue_neutral")
            sw("first_clue_neutral")
        if pend is not None:
            out[r] = pend["sign"] if tug[r] == pend["sign"] else 0
    return out


# --------------------------------------------------------------------------------------------------------------
# the whole-table pass (htf.table, after the flip column)
# --------------------------------------------------------------------------------------------------------------

def finish(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, drange: tuple | None = None, pd3_log: dict | None = None) -> pd.DataFrame:
    """Add the b2 columns named in `cfg` to the table `out` (one row per trading day). `drange` = (n, brk) of the daily-range configuration when the ranges are needed."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    px = out.px.values.astype(float)
    if "qd" in cfg:
        for k_, v_ in q_columns(h, l, c, ks, *cfg["qd"]).items():
            out[k_] = v_
    if "brk" in cfg:
        for k_, v_ in break_columns(h, l, c, ks, cfg["brk"][0], d).items():
            out[k_] = v_
    if "qs2" in cfg:
        sp, od, ip, wo, *lg = cfg["qs2"]
        for k_, v_ in qshift_columns(h, l, c, arrs, ks, sp, od, bool(ip), bool(wo), bool(lg and lg[0])).items():
            out[k_] = v_
    if "iofw" in cfg:
        out["iof_w"] = iof_w_column(d, w, ks, *cfg["iofw"])
    if "sibi" in cfg:
        for k_, v_ in sibi_columns(o, h, l, c, arrs, ks, px).items():
            out[k_] = v_
    if "q75" in cfg:
        out["wk_q75"] = q75_column(d, w, ks, c)
    if drange is not None and (cfg.get("cd") or cfg.get("rp")):
        ev = range_events(h, l, c, int(drange[0]), drange[1])
        if cfg.get("cd"):
            out["consol_prior"] = consol_prior_column(o, h, l, c, ks, ev)
        if cfg.get("rp"):
            out["raid_profile"] = raid_profile_column(h, l, ks, ev, int(cfg["rp"]))
    if "ad" in cfg:
        for k_, v_ in after_draw_columns(out, px).items():
            out[k_] = v_
    if "fd" in cfg:
        for k_, v_ in fast_draw_columns(out, d, w, arrs, ks, px, cfg["fd"]).items():
            out[k_] = v_
    if "eq20" in cfg:
        out["eq20_body"] = eq20_column(o, c, ks, int(cfg["eq20"]))
    if "tier" in cfg:
        if str(cfg["tier"][0]) != "last2":
            sw("tier_stl_mode")
        for k_, v_ in tier_columns(h, l, ks, str(cfg["tier"][0])).items():
            out[k_] = v_
    if "tier" in cfg and "no_new_ground" in out:                 # X3-b6-tug-of-war-new-ground (item 135): tug = no_new_ground AND the same-side tier_regime (the spec's definition; `tug` keeps the older post-raid reading)
        ng, rg = out.no_new_ground.values, out.tier_regime.values
        out["tug_spec"] = np.where((ng == rg) & (rg != 0), rg, 0)
    if "btf" in cfg:
        if cfg["btf"][0]:
            sw("htf_bias_pools")
        for k_, v_ in btf_columns(arrs, ks, px, h, l, c, d, bool(cfg["btf"][0]), bool(cfg["btf"][1]), bool(cfg["btf"][2])).items():
            out[k_] = v_
    if "rs" in cfg:
        out["raid_side60"] = raid_side_column(h, l, ks, cfg["rs"])
    if "ipz" in cfg:
        out["ipda_pause"] = ipda_pause_column(h, l, ks)
    if pd3_log is not None:
        out["pd3_n"] = [int(pd3_log.get(pd.Timestamp(x), 0)) for x in out.index]
    if "flip" in out:
        if "term" in cfg:
            out["flip"] = apply_terminus(out.flip.values, out.draw_up.values, out.draw_dn.values, ks, h, l, int(cfg["term"]))
        if "fcn" in cfg and "first_clue" in out:
            out["flip"] = apply_first_clue(out.flip.values, out.first_clue.values, out.tug.values)
        if "ad" in cfg and "after_draw_d" in out:
            out["flip"] = apply_after_draw_flip(out.flip.values, out.after_draw_d.values, out.after_draw_w.values)
    return out


# --------------------------------------------------------------------------------------------------------------
# intermarket (backtest.INTERMARKET) and the daily SMT map (backtest.run)
# --------------------------------------------------------------------------------------------------------------

def _slope(y) -> float:
    return float(np.polyfit(np.arange(len(y)), y, 1)[0])


def im_columns(dxy: pd.Series | None, tnx: pd.Series | None, spx: pd.Series | None) -> pd.DataFrame:
    """NEW-rates-dxy-fx-direction (095 ~14:49; cc03_006 ~5:35) and B19-bond-stock-dxy-sign (cc10_019 ~2:37; cc10_009 ~14:33; cc05_009 ~8:31): the extra INTERMARKET columns, every value for date t built from
    the closes up to t-1 only (shift(1)).
      tnx_slow          sign of the 60-session regression slope of the 10-year yield (rising yields +1)
      rates_dxy_agree   +1 when tnx_slow equals the dollar's side (the prior close vs its 20-day mean, as INTERMARKET["dxy"]), -1 when they differ, 0 unknown
      spx_dxy_corr / spx_tnx_corr   the 20-session correlation of the S&P's daily returns with the dollar's and with the BOND PRICE proxy (the yield's return inverted)
      spx20             sign of the S&P's 20-session change (the instrument's trend, for the four-asset map)
      im_regime         'b<with|against>_d<with|against>': the bond proxy / the dollar move with or against stocks, from the correlation signs"""
    cols: dict = {}
    if tnx is not None and len(tnx) > 62:
        cols["tnx_slow"] = np.sign(tnx.rolling(60).apply(_slope, raw=True).shift(1))
    if dxy is not None and "tnx_slow" in cols:
        ds = np.sign(dxy - dxy.rolling(20).mean()).shift(1).reindex(cols["tnx_slow"].index).ffill()
        both = (ds.fillna(0) != 0) & (cols["tnx_slow"].fillna(0) != 0)
        cols["rates_dxy_agree"] = pd.Series(np.where(both, np.where(ds == cols["tnx_slow"], 1, -1), 0), index=ds.index)
    if spx is not None and len(spx) > 22:
        r = spx.pct_change()
        cols["spx20"] = np.sign(spx.shift(1) - spx.shift(21))
        if dxy is not None:
            j = pd.concat([r, dxy.pct_change()], axis=1, keys=["a", "b"]).dropna()
            cols["spx_dxy_corr"] = j.a.rolling(20).corr(j.b).shift(1)
        if tnx is not None:
            j = pd.concat([r, -tnx.pct_change()], axis=1, keys=["a", "b"]).dropna()
            cols["spx_tnx_corr"] = j.a.rolling(20).corr(j.b).shift(1)
    if not cols:
        return pd.DataFrame()
    out = pd.concat(cols, axis=1)
    if "spx_dxy_corr" in out and "spx_tnx_corr" in out:
        def reg(row):
            a, b = row.spx_tnx_corr, row.spx_dxy_corr
            if a != a or b != b:
                return ""
            return f"b{'with' if a > 0 else 'against'}_d{'with' if b > 0 else 'against'}"
        out["im_regime"] = out.apply(reg, axis=1)
    return out


def dsmt_map(df_a, df_b, days: int = 18, ew=None) -> dict:
    """B18-htf-daily-smt (cc03_005 ~19:41; cc04_001 ~11:04; cc11_003 ~23:40): {date: +1 / -1 / 0} of the daily SMT between two indices, known before that session. +1 = within the last `days` sessions
    one index's low went under its latest known daily pivot low while the other's did not (the failing index's higher low holds: no later session of it traded under it); -1 = the same with highs (one
    index takes its latest pivot high, the other fails to; valid while the failing index's high holds); the later event wins. Whole-session lows / highs only ('if it is not obvious, it is not there')."""
    from .htf import sessions
    a, b = sessions(df_a), sessions(df_b)
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    ha, la = a.high.values.astype(float), a.low.values.astype(float)
    hb, lb = b.high.values.astype(float), b.low.values.astype(float)
    if ew:                                            # caption-gap A4-event-wick-ignore (bias_htf#4/7; cc05_007 ~4:42): the wick of a one-off event candle is ignored - its body extreme counts
        from . import bh4
        ha, la = bh4.event_wick_adjust(a.open.values, ha, la, a.close.values, float(ew))
        hb, lb = bh4.event_wick_adjust(b.open.values, hb, lb, b.close.values, float(ew))
        sw("event_wick_ignore")
    lha, lla = pivot_levels(ha, la)
    lhb, llb = pivot_levels(hb, lb)
    D = len(idx)
    ev = []                                           # (session, side, the instrument that failed, its extreme at that session)
    with np.errstate(invalid="ignore"):
        for j in range(D):
            na, nb = la[j] < lla[j], lb[j] < llb[j]
            if na != nb and (lla[j] == lla[j]) and (llb[j] == llb[j]):
                ev.append((j, 1, "b" if na else "a", float(lb[j] if na else la[j])))
            ua, ub = ha[j] > lha[j], hb[j] > lhb[j]
            if ua != ub and (lha[j] == lha[j]) and (lhb[j] == lhb[j]):
                ev.append((j, -1, "b" if ua else "a", float(hb[j] if ua else ha[j])))
    out = {}
    for k in range(D):
        val = 0
        for j, side, who, ext in reversed(ev):
            if j > k - 1:
                continue
            if k - j > days:
                break
            lo_, hi_ = (lb, hb) if who == "b" else (la, ha)
            seg = slice(j + 1, k)
            holds = (lo_[seg].min(initial=np.inf) >= ext) if side > 0 else (hi_[seg].max(initial=-np.inf) <= ext)
            if holds:
                val = side
                break
        out[idx[k].date()] = val
    return out
