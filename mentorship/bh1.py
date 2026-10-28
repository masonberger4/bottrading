"""Caption-gap pass, package bias_htf#1/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 1, 4-10, 12, 15-18, 20-22, 24, 40, 41, 43-47, 57, 59, 64-66, 71, 73-75, 77, 78) - TABLE SIDE.

The daily / weekly columns and flip triggers these switches need. Everything here is a pure function of COMPLETED daily / weekly candles (sessions before the row's day) and of the arrays
`htf.table` already built (`Arr` objects: `known` = the first session index at which an array may be used), so a value in the row of session k never reads session k or later; the stateful
flip triggers are evaluated at each completed session's close and apply from the NEXT session (the same as `htf._flip`). The engine side (side gates, the draw lock, scalps, tags) is `bh1e.py`.
`bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b1"; `add_columns` runs at the end of `bias_htf.add_columns`; `flip_extra` is the block `htf._flip` calls
for the new triggers. Thresholds the sources never give are marked [our interpretation]; every rule is a Params switch (off by default).

Columns
  drange / drange_in / drange_hi / drange_lo    (item 1)  daily consolidation: drange_in 1 while the last `drange_n` closes stay inside the first of those days' range; drange +1 / -1 after a close (or wick) beyond it
  ob_guard / ob_guard_sh / wk_high_in / wk_low_in (item 4) the last daily bull (bear) OB's mean threshold, carried across weeks; the in-week "high (low) of the week is in" after a break of it (b7_mode)
  lean                                          (item 6)  +1 / -1 / 0: a neutral market's gun-to-head lean at a daily premium (discount) array probed repeatedly without a close through it
  ceiling / ladder_dn / floor / ladder_up        (item 9)  the nearest overhead (underfoot) daily imbalance and whether the lower (upper) arrays are still drawn in order
  wk_po3                                        (item 64) +1 / -1: the week's accumulation below (above) the weekly open into a daily array, then a daily close back across it
  run_hi_draw / run_lo_draw                      (item 65) the high (low) of a >= 2 x ADR5 leg followed by >= 2 inside days, while untaken
  pwh_giveback / pwh_cand                        (item 66) the week ran above the previous week's high and gave back > giveback_frac; the weekly BISI CE below as the candidate
  draw_ord* (wick CE) / draw_mid_lvl             (items 46, 47) see `wick_columns` / `stack_far_post`
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from . import levels as L

HITS: Counter = Counter()
NAN = float("nan")


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b1" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.drange_scalp or p.org_consol_case or p.raid_gap_guard or p.consol_dir != "off" or p.raid_profile_bias:     # (bias_htf#2/7: consol_dir and raid_profile_bias read the same range)
        c["dr"] = [int(p.drange_n), p.drange_break]       # (the ORG consolidation case and the raid gap guard read drange_in as their regime)
    if p.wk_high_in_gate or p.b7_mode != "mt_close":
        c["b7"] = p.b7_mode + ("+fresh" if p.b7_fresh_break else "")
    if p.neutral_lean:
        c["lean"] = [int(p.lean_n), float(p.lean_tol_pts)]
    if p.ceiling_ladder:
        c["ceil"] = 1
    if p.wk_po3:
        c["wpo3"] = 1
    if p.run_extreme_lean:
        c["run"] = 1
    if p.pwh_giveback_draw:
        c["pwg"] = float(p.giveback_frac)
    if p.wick_ce_draw:
        c["wick"] = 1
    if p.stack_far:
        c["stack"] = 1
    if p.draw_order == "inefficiency_first":
        c["ofirst"] = 1
    fl: dict = {}
    if p.wk_bisi_ce_neutral:
        fl["ce"] = 1
    if p.b9_persist:
        fl["persist"] = 1
    if p.b7_mode != "mt_close":
        fl["b7"] = p.b7_mode
    if fl:
        c["fl"] = fl
    return c


def needs_objective(p) -> bool:
    """ob_low_touch reads the B17.3 objective-met columns (obj_day / obj_week)."""
    return "ob_low_touch" in p.flip_triggers


# --------------------------------------------------------------------------------------------------------------
# small helpers on the arrays
# --------------------------------------------------------------------------------------------------------------

LB = 60                                              # the daily arrays' life in sessions (htf.table's own look-back): older ones are not live, so the row loops never look at them


def _daily(arrs, kind: str, typs=("fvg", "ob", "vi")) -> list:
    return [a for a in arrs if a.tf == "D" and a.typ in typs and a.kind == kind]


def _recent(arrs, k: int) -> list:
    """The arrays formed in the last LB sessions up to session k (arrs is sorted by `known`)."""
    return [a for a in arrs if k - LB <= a.known <= k]


def _alive_d(a, k: int, o, c) -> bool:
    """A daily array is alive at session k: no body of the sessions after its formation closed through its far side (the table's simple reading; an OB dies on its mean threshold)."""
    s = a.known
    if s >= k:
        return True
    if a.kind == "bull":
        lvl = a.ce if a.typ == "ob" else a.bottom
        return bool(c[s:k].min() >= lvl)
    lvl = a.ce if a.typ == "ob" else a.top
    return bool(c[s:k].max() <= lvl)


def _week_starts(d) -> np.ndarray:
    """For each session its week's first session position (calendar weeks ending Friday)."""
    wk = d.index.to_period("W-FRI")
    first = np.zeros(len(d), int)
    cur = 0
    for q in range(len(d)):
        if q == 0 or wk[q] != wk[q - 1]:
            cur = q
        first[q] = cur
    return first


# --------------------------------------------------------------------------------------------------------------
# item 1: the daily consolidation regime
# --------------------------------------------------------------------------------------------------------------

def drange_states(h, l, c, n: int, brk: str = "close", events: list | None = None) -> tuple:
    """BH-B17-daily-range-scalp-regime (002 ~00:06:57; 043 ~00:06:55): per completed session j the state AFTER it: (in_range, breakout, range_hi, range_lo). A range forms at session j when the closes of the last n
    sessions (j-n+1 .. j) all lie inside the high-low of the first of them; it is held until a session closes (brk "close") or trades (brk "wick") beyond it: breakout +1 / -1, kept until a NEW range forms [our
    interpretation: n = 5 sessions, close-vs-wick is the spec's test switch]. A session that breaks both ways is judged by its close against the range's middle.
    `events` (caption-gap bias_htf#2/7, items 104 / 114): a list that receives one dict per range formed - a (first session), f (formation session), hi, lo, b (breakout session or None), dir (+1 / -1 or 0)."""
    D = len(c)
    inn = np.zeros(D, int)
    out = np.zeros(D, int)
    rhi = np.full(D, NAN)
    rlo = np.full(D, NAN)
    rng = None
    state = 0
    brk_day = -1                                      # review round 1: the n sessions of a NEW range start after the breakout session (a wide earlier day cannot swallow the breakout close at once)
    for j in range(D):
        if rng is not None and state == 0:
            hi, lo = rng
            up = (h[j] > hi) if brk == "wick" else (c[j] > hi)
            dn = (l[j] < lo) if brk == "wick" else (c[j] < lo)
            if up and dn:
                up, dn = (c[j] >= (hi + lo) / 2), (c[j] < (hi + lo) / 2)
            if up:
                state = 1
                brk_day = j
            elif dn:
                state = -1
                brk_day = j
            if (up or dn) and events:
                events[-1]["b"], events[-1]["dir"] = j, state
        if (rng is None or state != 0) and j >= n - 1 and j - n + 1 > brk_day:
            a = j - n + 1
            seg = c[a:j + 1]
            if (seg <= h[a]).all() and (seg >= l[a]).all():
                rng = (float(h[a]), float(l[a]))
                state = 0
                if events is not None:
                    events.append(dict(a=a, f=j, hi=float(h[a]), lo=float(l[a]), b=None, dir=0))
        inn[j] = 1 if (rng is not None and state == 0) else 0
        out[j] = state if rng is not None else 0
        if rng is not None:
            rhi[j], rlo[j] = rng
    return inn, out, rhi, rlo


# --------------------------------------------------------------------------------------------------------------
# item 4: the last daily OB's mean threshold as a guard
# --------------------------------------------------------------------------------------------------------------

def b7_columns(ks, d, arrs, mode: str = "mt_close") -> dict:
    """BH-B7-last-daily-OB-guard (058 ~00:06:43; 072 ~00:17:12; 101 ~00:33:35). For the row of session k:
      ob_guard    the mean threshold of the last daily BULLISH OB known at k (kept across the week boundary - the level is NOT reset on Monday: 'my last line of defense'); ob_guard_sh the bearish mirror
      wk_high_in  1 when, in the current week's sessions before k, the guard of that day was broken FRESHLY (the previous close was still on the guard's side): mode "mt_close" a daily close below the MT (wicks
                  below it are allowed), "mt_trade" any trade below the MT, "ob_close" a close below the OB's low. It is 'the weekly high is likely in', for that week only (cleared at the next weekly open) - not a short signal. wk_low_in is the mirror."""
    fresh = mode.endswith("+fresh")                   # b7_fresh_break (review round 1): only a break whose previous close was still on the guard's side counts; the spec default (False) sets the flag after ANY close below the MT
    mode = mode.split("+")[0]
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    bulls = [a for a in arrs if a.typ == "ob" and a.tf == "D" and a.kind == "bull"]
    bears = [a for a in arrs if a.typ == "ob" and a.tf == "D" and a.kind == "bear"]
    first = _week_starts(d)
    import bisect
    kb, ke = [a.known for a in bulls], [a.known for a in bears]

    def last(lst, j):
        keys = kb if lst is bulls else ke
        n = bisect.bisect_right(keys, j)
        return lst[n - 1] if n else None
    g, gs, hi_in, lo_in = [], [], [], []
    for k in ks:
        k = int(k)
        a, b = last(bulls, k), last(bears, k)
        g.append(float(a.ce) if a is not None else NAN)
        gs.append(float(b.ce) if b is not None else NAN)
        hh = ll = 0
        for j in range(int(first[k]), k):
            ga, gb = last(bulls, j), last(bears, j)
            pc_ = c[j - 1] if j >= 1 else None          # fresh: the previous close was still on the guard's side (a market that is long below the OB has no guard to break)
            if ga is not None and (pc_ is not None or not fresh):
                pa_ = pc_ if fresh else float("inf")
                if (mode == "mt_close" and c[j] < ga.ce <= pa_) or (mode == "mt_trade" and l[j] < ga.ce <= pa_) or (mode == "ob_close" and c[j] < ga.bottom <= pa_):
                    hh = 1
            if gb is not None and (pc_ is not None or not fresh):
                pb_ = pc_ if fresh else float("-inf")
                if (mode == "mt_close" and c[j] > gb.ce >= pb_) or (mode == "mt_trade" and h[j] > gb.ce >= pb_) or (mode == "ob_close" and c[j] > gb.top >= pb_):
                    ll = 1
        hi_in.append(hh)
        lo_in.append(ll)
    return dict(ob_guard=g, ob_guard_sh=gs, wk_high_in=hi_in, wk_low_in=lo_in)


# --------------------------------------------------------------------------------------------------------------
# item 6: the neutral market's lean
# --------------------------------------------------------------------------------------------------------------

def lean_columns(ks, px, d, arrs, n: int, tol: float) -> list:
    """BH-B17-neutral-lean (010 ~00:36:36): lean -1 when the row's price sits inside or within `tol` (price units) of a live daily BEARISH array (FVG / OB / VI) and each of the last `n` completed sessions' highs
    probed it (reached within tol of its bottom) without a daily close above its top; +1 the mirror at a bullish array. The main bias decides whether the lean is used (engine: only when it is 0)."""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    bear = _daily(arrs, "bear")
    bull = _daily(arrs, "bull")
    out = []
    for k, x in zip(ks, px):
        k = int(k)
        lean = 0
        if k >= n:
            best = None
            for a in _recent(bear, k):
                if not _alive_d(a, k, o, c):
                    continue
                if not (a.bottom - tol <= x <= a.top + tol):
                    continue
                if all(h[j] >= a.bottom - tol and c[j] <= a.top for j in range(k - n, k)):
                    d_ = abs(x - (a.top + a.bottom) / 2)
                    if best is None or d_ < best[0]:
                        best = (d_, -1)
            for a in _recent(bull, k):
                if not _alive_d(a, k, o, c):
                    continue
                if not (a.bottom - tol <= x <= a.top + tol):
                    continue
                if all(l[j] <= a.top + tol and c[j] >= a.bottom for j in range(k - n, k)):
                    d_ = abs(x - (a.top + a.bottom) / 2)
                    if best is None or d_ < best[0]:
                        best = (d_, 1)
            lean = best[1] if best else 0
        out.append(lean)
    return out


# --------------------------------------------------------------------------------------------------------------
# item 9: the imbalance ceiling ladder
# --------------------------------------------------------------------------------------------------------------

def ceiling_columns(ks, d, arrs) -> dict:
    """BH-B1-imbalance-ceiling-ladder (011 ~00:00:24): ceiling = the top of the nearest live daily bear imbalance (VI / FVG; VIs need htf.table(vi=True)) above the prior close; ladder_dn = 1 while no daily BODY
    closes above it and it is not suspended: a session traded above an imbalance and a later session's low held at or above its top (two imbalances supporting) - the suspension lasts until a close back below that
    imbalance's bottom. floor / ladder_up are the mirror (bull imbalance below, bodies below it, a trade below and a later high holding at or below its bottom)."""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    D = len(d)
    bear = [a for a in arrs if a.tf == "D" and a.typ in ("vi", "fvg") and a.kind == "bear"]
    bull = [a for a in arrs if a.tf == "D" and a.typ in ("vi", "fvg") and a.kind == "bull"]

    def susp_bear(a, k) -> bool:           # traded above the top at j1, then a low >= top at j2 > j1, and no close back under the bottom since j2 (sessions before k)
        idx = np.flatnonzero(h[a.known:k] > a.top)
        if not len(idx):
            return False
        j1 = a.known + int(idx[0])
        idx2 = np.flatnonzero(l[j1 + 1:k] >= a.top)
        if not len(idx2):
            return False
        j2 = j1 + 1 + int(idx2[0])
        return not (c[j2:k] < a.bottom).any()

    def susp_bull(a, k) -> bool:
        idx = np.flatnonzero(l[a.known:k] < a.bottom)
        if not len(idx):
            return False
        j1 = a.known + int(idx[0])
        idx2 = np.flatnonzero(h[j1 + 1:k] <= a.bottom)
        if not len(idx2):
            return False
        j2 = j1 + 1 + int(idx2[0])
        return not (c[j2:k] > a.top).any()
    bo, bl = np.maximum(o, c), np.minimum(o, c)
    ce_, ld_, fl_, lu_ = [], [], [], []
    for k in ks:
        k = int(k)
        px = float(c[k - 1]) if k >= 1 else NAN
        cl, lad = NAN, 0
        rb = _recent(bear, k)
        cand = [a for a in rb if a.top > px and not (bo[a.known:k] > a.top).any()]
        if cand:
            a = min(cand, key=lambda x: x.bottom - px)
            cl = float(a.top)
            lad = 0 if any(susp_bear(b, k) for b in rb) else 1
        fl, lup = NAN, 0
        rl = _recent(bull, k)
        cand = [a for a in rl if a.bottom < px and not (bl[a.known:k] < a.bottom).any()]
        if cand:
            a = max(cand, key=lambda x: x.top)
            fl = float(a.bottom)
            lup = 0 if any(susp_bull(b, k) for b in rl) else 1
        ce_.append(cl)
        ld_.append(lad)
        fl_.append(fl)
        lu_.append(lup)
    return dict(ceiling=ce_, ladder_dn=ld_, floor=fl_, ladder_up=lu_)


# --------------------------------------------------------------------------------------------------------------
# item 64: the weekly PO3
# --------------------------------------------------------------------------------------------------------------

def _jobs_week(day) -> bool:
    """A week with an NFP release (claude_hf.daytypes 'jobs' event on any of its days)."""
    from datetime import timedelta
    from claude_hf.daytypes import events
    mon = day - timedelta(days=day.weekday())
    return any("jobs" in events(mon + timedelta(days=q)) for q in range(5))


def wk_po3_column(ks, d, arrs) -> list:
    """BH-B13-weekly-PO3 (066 ~00:08:51; 072 ~00:07:07; cc07_006 ~00:08:30): +1 from the session after this week (a) traded below the weekly open (the first session's open) into a daily bull array
    (the array lies at or below the open: sell stops / FVG / old high) and (b) afterwards closed back above the open; -1 the mirror; 0 when neither or both. On an NFP week it stays 0 until Friday [our
    interpretation of 072: the weekly extreme can form late on news weeks]."""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    first = _week_starts(d)
    bull = _daily(arrs, "bull")
    bear = _daily(arrs, "bear")
    dates = [t.date() for t in d.index]
    out = []
    for k in ks:
        k = int(k)
        k0 = int(first[k])
        wo = float(o[k0])
        up = dn = False
        bull_, bear_ = _recent(bull, k), _recent(bear, k)
        for j in range(k0, k):
            if not up and l[j] < wo and any(a.known <= j and a.top <= wo + 1e-9 and l[j] <= a.top for a in bull_):
                if (c[j:k] > wo).any():
                    up = True
            if not dn and h[j] > wo and any(a.known <= j and a.bottom >= wo - 1e-9 and h[j] >= a.bottom for a in bear_):
                if (c[j:k] < wo).any():
                    dn = True
        v = 1 if (up and not dn) else (-1 if (dn and not up) else 0)
        if v and dates[k].weekday() < 4 and _jobs_week(dates[k]):
            v = 0
        out.append(v)
    return out


# --------------------------------------------------------------------------------------------------------------
# item 65: a run, then consolidation: the run's extreme is the minimum draw
# --------------------------------------------------------------------------------------------------------------

def run_columns(ks, d, adr5, n_inside: int = 2, leg_mult: float = 2.0, window: int = 40) -> dict:
    """BH-consolidation-takes-run-high (046 ~00:09:16): run_hi_draw = the high of the latest confirmed daily swing high (within the last `window` sessions) whose leg (from the swing low before it) was >= 2 x ADR5
    and which the following sessions (>= 2, all of them) stayed inside - each trading within that high-day candle's range; the high is still untaken at the row's session [our interpretation: 'inside days' =
    inside the run-high candle]; run_lo_draw the mirror."""
    h = d.high.values.astype(float)
    l = d.low.values.astype(float)
    ph, pl = L.pivots(h, l, 1)
    import bisect
    ph_i, pl_i = [q.i for q in ph], [q.i for q in pl]

    def scan(piv, other, other_i, k, a5, up):
        for p_ in reversed([q for q in piv if k - window <= q.i and q.known <= k - 1]):
            m = bisect.bisect_left(other_i, p_.i)
            if not m:
                continue
            leg = (p_.price - other[m - 1].price) if up else (other[m - 1].price - p_.price)
            after = range(p_.i + 1, k)
            if leg >= leg_mult * a5 and len(after) >= n_inside and all(h[j] <= h[p_.i] and l[j] >= l[p_.i] for j in after):
                return float(p_.price)
        return NAN
    hi_out, lo_out = [], []
    for k in ks:
        k = int(k)
        a5 = adr5[k] if adr5[k] == adr5[k] else NAN
        if a5 == a5:
            hi_out.append(scan(ph, pl, pl_i, k, a5, True))
            lo_out.append(scan(pl, ph, ph_i, k, a5, False))
        else:
            hi_out.append(NAN)
            lo_out.append(NAN)
    return dict(run_hi_draw=hi_out, run_lo_draw=lo_out)


# --------------------------------------------------------------------------------------------------------------
# item 66: the previous week's high run, then a give-back
# --------------------------------------------------------------------------------------------------------------

def pwh_columns(ks, d, w, arrs, frac: float) -> dict:
    """BH-PWH-run-giveback-weekly-gap (047 ~00:01:31): pwh_giveback +1 when this week (sessions before the row) traded above the PREVIOUS week's high and the prior close gave back more than `frac` of the week's
    low-to-high (c < week_low + (1 - frac) x range); -1 the mirror (below the previous week's low, bounced more than frac). pwh_cand = the CE of the nearest live weekly BISI below the prior close (+1) / SIBI above (-1),
    the lock candidate. A full close into that gap flows into the flip trigger wk_bisi. A tag; the tenor of the draw is [our interpretation: 'much of' = 50 %]."""
    h = d.high.values.astype(float)
    l = d.low.values.astype(float)
    c = d.close.values.astype(float)
    first = _week_starts(d)
    wk = d.index.to_period("W-FRI")
    wh = w.high.values.astype(float)
    wlw = w.low.values.astype(float)
    wcl = w.close.values.astype(float)
    wper = {p_: q for q, p_ in enumerate(w.index)}
    pos = {t: q for q, t in enumerate(d.index)}
    wl_ = [pos[t] + 1 for t in w["last"]]                      # the session from which each weekly bar is usable
    wf = [a for a in arrs if a.tf == "W" and a.typ == "fvg"]
    g, cand = [], []
    for k in ks:
        k = int(k)
        k0 = int(first[k])
        v, cv = 0, NAN
        if k > k0:
            q = wper.get(wk[k])
            if q is not None and q >= 1:
                pwh_, pwl_ = float(wh[q - 1]), float(wlw[q - 1])
                hh, ll = float(h[k0:k].max()), float(l[k0:k].min())
                px = float(c[k - 1])
                rng = hh - ll
                if hh > pwh_ and rng > 0 and px < ll + (1 - frac) * rng:
                    v = 1
                elif ll < pwl_ and rng > 0 and px > hh - (1 - frac) * rng:
                    v = -1
                if v:
                    def alive(a):
                        done = [wcl[j] for j in range(len(wcl)) if a.known <= wl_[j] <= k0]         # completed weekly closes after its formation
                        if a.kind == "bull":
                            return all(x >= a.bottom for x in done)
                        return all(x <= a.top for x in done)
                    if v > 0:
                        cs = [a for a in wf if a.kind == "bull" and a.known <= k and a.top <= px and alive(a)]
                        cv = float(max(cs, key=lambda a: a.top).ce) if cs else NAN
                    else:
                        cs = [a for a in wf if a.kind == "bear" and a.known <= k and a.bottom >= px and alive(a)]
                        cv = float(min(cs, key=lambda a: a.bottom).ce) if cs else NAN
        g.append(v)
        cand.append(cv)
    return dict(pwh_giveback=g, pwh_cand=cand)


# --------------------------------------------------------------------------------------------------------------
# items 46 / 47: the draw when no inefficiency is left; the stacked gaps
# --------------------------------------------------------------------------------------------------------------

def wick_columns(out, ks, px, d, w) -> None:
    """BH-B2-wick-CE-draw (065A ~00:39:00): for a row whose ordered draw found no inefficiency (draw_ord_kind not 'ineff'), the draw in the bias direction is the CE of the nearest untaken WEEKLY (else
    DAILY) wick - below price for a bearish draw ((min(o, c) + l) / 2, extreme = the wick's low), above for a bullish one - the first objective; the wick's extreme is the full one (draw_ext_lvl). The bias
    direction is the ordered draw's side, else the P/D side. Rows of kind 'ineff' are untouched. Sets draw_ord / draw_ord_lvl / draw_ord_name / draw_ord_kind ('wick') and draw_ext_lvl / draw_ext_name."""
    if "draw_ord" not in out:
        return
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    wo, wh, wlw, wc = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    pos = {t: q for q, t in enumerate(d.index)}
    wlast = np.array([pos[t] for t in w["last"]])               # session position of each week's last session
    kinds = out.draw_ord_kind.values
    sides = out.draw_ord.values
    pds = out.pd.values if "pd" in out else np.zeros(len(out), int)
    for r, k in enumerate(ks):
        k = int(k)
        if kinds[r] == "ineff":
            continue
        s = int(sides[r]) or int(pds[r])
        if not s:
            continue
        x = float(px[r])
        got = None
        # weekly wicks first (completed weeks), then daily
        for tf in ("W", "D"):
            if tf == "W":
                idx = [q for q in range(len(wo)) if wlast[q] < k][-13:]
                oo, hh, ll, cc = wo, wh, wlw, wc
                after = lambda q: (float(l[wlast[q] + 1:k].min()) if wlast[q] + 1 < k else np.inf, float(h[wlast[q] + 1:k].max()) if wlast[q] + 1 < k else -np.inf)
            else:
                idx = list(range(max(0, k - 60), k))
                oo, hh, ll, cc = o, h, l, c
                after = lambda q: (float(l[q + 1:k].min()) if q + 1 < k else np.inf, float(h[q + 1:k].max()) if q + 1 < k else -np.inf)
            best = None
            for q in idx:
                if s < 0:
                    body = min(oo[q], cc[q])
                    if not ll[q] < body:
                        continue
                    ce = (body + ll[q]) / 2
                    if ce < x and after(q)[0] > ce:
                        if best is None or ce > best[0]:
                            best = (float(ce), float(ll[q]))
                else:
                    body = max(oo[q], cc[q])
                    if not hh[q] > body:
                        continue
                    ce = (body + hh[q]) / 2
                    if ce > x and after(q)[1] < ce:
                        if best is None or ce < best[0]:
                            best = (float(ce), float(hh[q]))
            if best is not None:
                got = (tf, best)
                break
        if got is None:
            continue
        tf, (ce, ext) = got
        for col, val in (("draw_ord", s), ("draw_ord_lvl", ce), ("draw_ord_name", tf + "_wick_ce"), ("draw_ord_kind", "wick"), ("draw_ext_lvl", ext), ("draw_ext_name", tf + "_wick")):
            out.iloc[r, out.columns.get_loc(col)] = val


def stack_far_post(ex: dict, draws_up: list, draws_dn: list) -> None:
    """BH-B2-two-HTF-FVGs-farther (069 ~00:01:59): two daily FVGs stacked in the bias direction with no other draw between their near edges: the draw is the FARTHER one's near edge (L9), the nearer gap's near
    edge is draw_mid_lvl (the engine's partial rung [our interpretation]). Acts on the ordered draw's pick when it is an inefficiency."""
    ex.setdefault("draw_mid_lvl", NAN)
    if ex.get("draw_ord_kind") != "ineff" or not ex.get("draw_ord"):
        return
    s = ex["draw_ord"]
    pool = sorted(draws_up if s > 0 else draws_dn)
    fv = [x for x in pool if x[1] == "D_fvg"]
    if len(fv) < 2:
        return
    a, b = fv[0], fv[1]
    if abs(a[2] - ex["draw_ord_lvl"]) > 1e-9:
        return
    lo_, hi_ = sorted((a[2], b[2]))
    if any(lo_ < x[2] < hi_ for x in pool if x is not a and x is not b):
        return
    ex["draw_mid_lvl"] = float(a[2])
    ex["draw_ord_lvl"] = float(b[2])
    ex["draw_ord_name"] = b[1]


# --------------------------------------------------------------------------------------------------------------
# the whole-table pass
# --------------------------------------------------------------------------------------------------------------

def add_columns(out, cfg: dict, d, w, arrs, ks, px, es_pt: float):
    """Add the b1 columns named in `cfg` to the table `out` (one row per trading day; `ks` = each row's session position, `px` the row prices)."""
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    if "dr" in cfg:
        n, brk = cfg["dr"]
        inn, st, rhi, rlo = drange_states(h, l, c, int(n), brk)
        prev = np.maximum(np.asarray(ks) - 1, 0)
        ok = np.asarray(ks) >= 1
        out["drange_in"] = np.where(ok, inn[prev], 0)
        out["drange"] = np.where(ok, st[prev], 0)
        out["drange_hi"] = np.where(ok, rhi[prev], NAN)
        out["drange_lo"] = np.where(ok, rlo[prev], NAN)
    if "b7" in cfg:
        for k_, v_ in b7_columns(ks, d, arrs, cfg["b7"]).items():
            out[k_] = v_
    if "lean" in cfg:
        out["lean"] = lean_columns(ks, px, d, arrs, int(cfg["lean"][0]), float(cfg["lean"][1]) * es_pt)
    if "ceil" in cfg:
        for k_, v_ in ceiling_columns(ks, d, arrs).items():
            out[k_] = v_
    if "wpo3" in cfg:
        out["wk_po3"] = wk_po3_column(ks, d, arrs)
    if "run" in cfg:
        import pandas as pd
        a5 = pd.Series(h - l).rolling(5).mean().shift(1).values
        for k_, v_ in run_columns(ks, d, a5).items():
            out[k_] = v_
    if "pwg" in cfg:
        for k_, v_ in pwh_columns(ks, d, w, arrs, float(cfg["pwg"])).items():
            out[k_] = v_
    if "wick" in cfg:
        wick_columns(out, ks, px, d, w)
    return out


# --------------------------------------------------------------------------------------------------------------
# the flip triggers (called from htf._flip once per completed session)
# --------------------------------------------------------------------------------------------------------------

class FlipState:
    """The per-run state of the new flip triggers (htf._flip creates one)."""

    def __init__(self, d, w, arrs, triggers, cfg):
        self.o, self.h, self.l, self.c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.cfg = cfg or {}
        self.tr = set(triggers)
        self.wk_of = d.index.to_period("W-FRI")
        self.piv_h, self.piv_l = L.pivots(self.h, self.l, 1)
        self.obs = [a for a in arrs if a.typ == "ob" and a.tf == "D"]
        self.fv_d = [a for a in arrs if a.typ == "fvg" and a.tf == "D"]
        self.fv_w = [a for a in arrs if a.typ == "fvg" and a.tf == "W"]
        self.wcl = {}                                              # session position of a week's last session -> (weekly bar row)
        pos = {t: q for q, t in enumerate(d.index)}
        self.wk_rows = {pos[r.last]: r for r in w.itertuples()}
        self.brk = {}
        if "d_breaker" in self.tr:
            for z in L.breakers(self.o, self.h, self.l, self.c, 1, "range"):
                self.brk.setdefault(z.i, []).append(z)
        self.inv = None
        self.pend = None                                           # item 78: the flip kept pending while the retracement persists
        self.rb = None
        self.db = None
        self.obj = self.cfg.get("obj")

    # --- helpers
    def _first(self, k: int) -> int:
        q = k
        while q > 0 and self.wk_of[q - 1] == self.wk_of[k]:
            q -= 1
        return q

    def _alive_w(self, a, k: int, last_week_pos: list) -> bool:
        """A weekly FVG is alive before the week that closes at session k: no completed weekly close after its formation closed through its far side."""
        cl = [self.wk_rows[q].close for q in last_week_pos if q < k and q + 1 >= a.known]
        if a.kind == "bull":
            return all(x >= a.bottom for x in cl)
        return all(x <= a.top for x in cl)

    def _persists(self, sign: int, F, k: int) -> bool:
        """B9 persistence at session k: the last daily swing low (high) known before k still holds and the breakaway FVG `F` is still partly open."""
        if F is None:
            return False
        if sign > 0:
            pl_ = [q for q in self.piv_l if q.known <= k - 1]
            return bool(pl_ and self.l[k] > pl_[-1].price and self.l[k] > F.bottom and _alive_d(F, k, self.o, self.c))
        ph_ = [q for q in self.piv_h if q.known <= k - 1]
        return bool(ph_ and self.h[k] < ph_[-1].price and self.h[k] < F.top and _alive_d(F, k, self.o, self.c))

    def step(self, k: int, state: int, prev_week, prev_state=None) -> int:
        """Apply the new triggers at the close of session k; returns the new state. `prev_week` = the last COMPLETED week's row before k (or None); `prev_state` = the state known before session k
        (htf._flip passes it: the older triggers may already have moved `state`; default = the state passed in)."""
        o, h, l, c = self.o, self.h, self.l, self.c
        tr = self.tr
        prev0 = state
        pst = prev0 if prev_state is None else prev_state
        # --- item 7: a weekly close into / through the nearest weekly BISI (SIBI)
        if "wk_bisi" in tr and k in self.wk_rows and prev_week is not None:
            wc_ = float(self.wk_rows[k].close)
            lastw = sorted(q for q in self.wk_rows if q < k)
            pc_ = float(prev_week.close)
            bulls = [a for a in self.fv_w if a.kind == "bull" and a.known <= k and a.top <= pc_ and self._alive_w(a, k, lastw)]
            bears = [a for a in self.fv_w if a.kind == "bear" and a.known <= k and a.bottom >= pc_ and self._alive_w(a, k, lastw)]
            if bulls:
                a = max(bulls, key=lambda x: x.top)
                if wc_ < a.bottom:
                    state = -1
                    hit("flip_wk_bisi")
                elif self.cfg.get("ce") and state > 0 and wc_ < a.ce:
                    state = 0
                    hit("flip_wk_bisi_ce")
            if bears and state == prev0:
                a = min(bears, key=lambda x: x.bottom)
                if wc_ > a.top:
                    state = 1
                    hit("flip_wk_bisi")
                elif self.cfg.get("ce") and state < 0 and wc_ > a.ce:
                    state = 0
                    hit("flip_wk_bisi_ce")
        # --- item 8: bias -> neutral (L taken and the opposing inefficiency F entered) -> opposite (a close through F, a held retest)
        if ("inv3" in tr or "inv3_lit" in tr) and k >= 1:
            lit = "inv3_lit" in tr                      # the spec's literal reading (review round 1): the opposing inefficiency F is the nearest daily BEAR FVG below a bullish state (BULL FVG above a bearish one); the default reads the supporting FVG
            if self.inv is not None and state != 0:
                self.inv = None
            if self.inv is None and state != 0:
                s = state
                if s > 0:
                    pl_ = [q for q in self.piv_l if q.known <= k - 1]
                    L_ = pl_[-1].price if pl_ else None
                    if L_ is not None and l[k] < L_:
                        cs = [a for a in self.fv_d if a.kind == ("bear" if lit else "bull") and a.known <= k and a.top < c[k - 1] and _alive_d(a, k, o, c)]
                        F = max(cs, key=lambda a: a.top) if cs else None
                        if F is not None and l[k] <= F.top:
                            state = 0
                            self.inv = dict(sign=1, F=F, stage=2 if c[k] < F.bottom else 1)
                            hit("flip_inv3_neutral")
                else:
                    ph_ = [q for q in self.piv_h if q.known <= k - 1]
                    L_ = ph_[-1].price if ph_ else None
                    if L_ is not None and h[k] > L_:
                        cs = [a for a in self.fv_d if a.kind == ("bull" if lit else "bear") and a.known <= k and a.bottom > c[k - 1] and _alive_d(a, k, o, c)]
                        F = min(cs, key=lambda a: a.bottom) if cs else None
                        if F is not None and h[k] >= F.bottom:
                            state = 0
                            self.inv = dict(sign=-1, F=F, stage=2 if c[k] > F.top else 1)
                            hit("flip_inv3_neutral")
            elif self.inv is not None:
                s, F = self.inv["sign"], self.inv["F"]
                if self.inv["stage"] == 1:
                    if (s > 0 and c[k] < F.bottom) or (s < 0 and c[k] > F.top):
                        self.inv["stage"] = 2
                else:
                    if (s > 0 and h[k] >= F.bottom and c[k] < F.bottom) or (s < 0 and l[k] <= F.top and c[k] > F.top):
                        state = -s
                        self.inv = None
                        hit("flip_inv3_flip")
        # --- item 17: after the objective is met a trade below the last bullish OB candle's low drops the bullish draw to neutral (no close needed)
        if "ob_low_touch" in tr and state != 0 and k >= 1 and (self.obj is None or self.obj[k]):
            if state > 0:
                bu = [a for a in self.obs if a.kind == "bull" and a.known <= k]
                if bu and l[k] < bu[-1].bottom:
                    state = 0
                    hit("flip_ob_low_touch")
            else:
                be = [a for a in self.obs if a.kind == "bear" and a.known <= k]
                if be and h[k] > be[-1].top:
                    state = 0
                    hit("flip_ob_low_touch")
        # --- item 73: an indecisive weekly candle at a weekly FVG: neutral until the rejection-block level / the week's low is traded
        if "wk_rb" in tr:
            if self.rb is not None and state == 0:
                hi_, lo_ = h[k] > self.rb["top"], l[k] < self.rb["low"]
                if hi_ and lo_:
                    hi_, lo_ = c[k] >= (self.rb["top"] + self.rb["low"]) / 2, c[k] < (self.rb["top"] + self.rb["low"]) / 2
                if hi_:
                    state = 1
                    self.rb = None
                    hit("flip_wk_rb")
                elif lo_:
                    state = -1
                    self.rb = None
                    hit("flip_wk_rb")
            if k in self.wk_rows:
                r = self.wk_rows[k]
                rng = float(r.high - r.low)
                if rng > 0 and abs(float(r.close - r.open)) < 0.3 * rng:
                    k0 = self._first(k)
                    if any(a.known <= k0 and a.bottom <= r.high and a.top >= r.low for a in self.fv_w):
                        state = 0
                        self.rb = dict(top=float(max(r.open, r.close)), low=float(r.low))
                        hit("flip_wk_rb_neutral")
        # --- item 75: a daily breaker (a close through the last swing) respected on its retest
        if "d_breaker" in tr:
            for z in self.brk.get(k, ()):
                self.db = dict(zone=z, stage=0)
            if self.db is not None and k > self.db["zone"].i:
                z = self.db["zone"]
                if z.kind == "bear":
                    if self.db["stage"] == 0:
                        if h[k] >= z.bottom:
                            if c[k] < z.bottom:
                                state = -1
                                self.db["stage"] = 1
                                hit("flip_d_breaker")
                            elif c[k] > z.top:
                                self.db = None
                    elif c[k] > z.top:
                        state = 0
                        self.db = None
                else:
                    if self.db["stage"] == 0:
                        if l[k] <= z.top:
                            if c[k] > z.top:
                                state = 1
                                self.db["stage"] = 1
                                hit("flip_d_breaker")
                            elif c[k] < z.bottom:
                                self.db = None
                    elif c[k] < z.bottom:
                        state = 0
                        self.db = None
        # --- item 78: a retracement inside a bullish (bearish) HTF is not a flip while the last daily swing low (high) holds and the lower (upper) breakaway FVG is still partly open.
        # The suppressed flip is kept pending (review round 1): it applies at the first later session where the persistence conditions fail - the swing low breaks or the FVG is traded through ("after the swing low breaks, the flip applies")
        if self.cfg.get("persist") and pst != 0 and k >= 1:
            if state == -pst:
                if pst > 0:
                    cs = [a for a in self.fv_d if a.kind == "bull" and a.known <= k and a.top < c[k - 1]]
                    F = max(cs, key=lambda a: a.top) if cs else None
                else:
                    cs = [a for a in self.fv_d if a.kind == "bear" and a.known <= k and a.bottom > c[k - 1]]
                    F = min(cs, key=lambda a: a.bottom) if cs else None
                if self._persists(pst, F, k):
                    state = pst
                    self.pend = dict(sign=pst, F=F)
                    hit("b9_persist")
                else:
                    self.pend = None
            elif self.pend is not None:
                if state == pst == self.pend["sign"] and not self._persists(pst, self.pend["F"], k):
                    state = -pst
                    hit("b9_persist_release")
                    self.pend = None
                elif state != pst or self.pend["sign"] != pst:
                    self.pend = None
        elif self.cfg.get("persist"):
            self.pend = None
        return state



# --------------------------------------------------------------------------------------------------------------
# item 77: the weekly ITH flag needs both indices
# --------------------------------------------------------------------------------------------------------------

def _week_flags(df) -> dict:
    """Per completed week of one instrument: {week period: (date of its last session, closed below the low of the last down-close week before it, closed above that week's high)}."""
    from . import htf
    d = htf.sessions(df)
    w = htf.weeks(d)
    out = {}
    last_dn = None                                   # (low, high) of the last down-close week
    for t, r in w.iterrows():
        below = bool(last_dn is not None and r.close < last_dn[0])
        above = bool(last_dn is not None and r.close > last_dn[1])
        out[t] = (r["last"].date(), below, above)
        if r.close < r.open:
            last_dn = (float(r.low), float(r.high))
    return out


def joint_from_flags(fa: dict, fb: dict) -> dict:
    """The joint state over the weeks (see wk_joint_map) from the per-instrument week flags {week period: (last session date, closed below, closed above)}."""
    st = False
    out = {}
    for per in sorted(fa):
        da, ba, ua = fa[per]
        _, bb, ub = fb.get(per, (None, False, False))
        if ba and bb:
            st = True
        elif ua or ub:
            st = False
        out[da] = st
    return out


def wk_joint_map(df_a, df_b) -> dict:
    """B8-weekly-ith-both-indices-close (077 ~00:09:44): {date of the first instrument's week-last session: the joint weekly-ITH state}. The state turns True when BOTH instruments' week closed below the low of
    their own last down-close week ('on a closing basis both S&P and NASDAQ'), and stays True until either instrument closes a week above the high of its last down-close week (the wk_dc +1 test) [our
    interpretation of 'a return to bullish']. htf._flip applies the wk_dc -1 flip only while it is True."""
    return joint_from_flags(_week_flags(df_a), _week_flags(df_b))
