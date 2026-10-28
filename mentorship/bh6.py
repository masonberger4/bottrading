"""Caption-gap pass, package bias_htf#6/7 (digests/rulebook_gaps/management_partials_trailing_exits.md items 97, 134 and models_setups_entries.md items 129, 133) - TABLE SIDE.

The daily columns these switches need. Everything here is a pure function of COMPLETED sessions (the sessions before the row's day): the row of session k never reads session k's high / low / close nor an
incomplete week. The engine side (the side gate, the scenario re-lock, the factor tag) is `bh6e.py`; the study-only items of the package (swing management, daily-candle entries, ...) are `bh6s.py`.
`bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b6"; `finish6` runs at the end of `htf.table` (after bh5.finish5). Thresholds the sources never give are marked
[our interpretation]; every rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  both_pools / bp_dir / cont_cap   (X8-061-continuation-after-both-pools)  1 when the last session (or the last `bp_leg_days` sessions together) took both the prior high and the prior low; -1 / +1 = the
                                   leg's direction (down / up); the continuation cap = min(open of the last up-close daily candle before the down move, CE of the daily FVG that candle starts) for a down leg,
                                   max(open of the last down-close candle, CE of its FVG) for an up leg
  mob                              (new-htf-regime-trigger-and-entry)  +1 once a session trades above the high of the last completed down-close MONTHLY candle (the monthly bullish OB activates), kept until a session
                                   trades below that candle's low; -1 the mirror (a session trading below the low of the last up-close monthly candle, kept until a session trades above its high)
  wk_bias (rewritten)              (new-weekly-idea-persistence)  a Tue / Wed daily close beyond Monday's extreme against the weekly bias keeps the week's first reading until the table's stateful bias changes
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import bh2 as BH2

HITS = BH2.HITS
NAN = float("nan")
sw = BH2.sw


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b6" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.both_pools_gate:
        c["bp"] = int(p.bp_leg_days)
    if p.htf_bias == "mob" or p.factor_tag:
        c["mob"] = 1
    if p.weekly_persist:
        c["wp"] = 1
    if p.factor_tag:
        c["ft"] = 1
    return c


# --------------------------------------------------------------------------------------------------------------
# X8-061-continuation-after-both-pools
# --------------------------------------------------------------------------------------------------------------

def _leg_cap(o, h, l, c, k: int, direction: int):
    """The continuation cap for a leg in `direction` (-1 down, +1 up) seen at row k (sessions <= k-1): the open of the last candle of the opposite colour before the leg (an up-close candle for a down leg),
    together with the CE of the 3-candle FVG that candle starts when that gap is complete (candle j+2 <= k-1). Down leg: min of the two; up leg: max. NaN when there is no such candle in 30 sessions."""
    j = k - 1
    lo_j = max(-1, k - 31)
    while j > lo_j and ((c[j] < o[j]) if direction < 0 else (c[j] > o[j])):
        j -= 1                                           # walk back over the leg's own candles
    if j <= lo_j:
        return NAN
    # j is now the first opposite-colour (or doji) candle back from the leg's end: the order-block candle
    lvl = float(o[j])
    if j + 2 <= k - 1:
        if direction < 0 and l[j] > h[j + 2]:
            lvl = min(lvl, (float(l[j]) + float(h[j + 2])) / 2)
        elif direction > 0 and h[j] < l[j + 2]:
            lvl = max(lvl, (float(h[j]) + float(l[j + 2])) / 2)
    return lvl


def both_pools_columns(o, h, l, c, ks, leg: int) -> dict:
    """The columns both_pools / bp_dir / cont_cap per row (see the module doc). The window is the last m sessions (m = 1 .. leg, the smallest that works) against the session before it: their highest high is
    above that session's high AND their lowest low is below its low [our interpretation of 'that day or the leg took both the prior high and the prior low']."""
    n = len(ks)
    bp = np.zeros(n, int)
    bd = np.zeros(n, int)
    cap = np.full(n, NAN)
    for r, k in enumerate(ks):
        k = int(k)
        for m in range(1, int(leg) + 1):
            b = k - m - 1
            if b < 0:
                break
            if h[k - m:k].max() > h[b] and l[k - m:k].min() < l[b]:
                dr = -1 if c[k - 1] < c[b] else (1 if c[k - 1] > c[b] else 0)
                if dr:
                    bp[r], bd[r] = 1, dr
                    cap[r] = _leg_cap(o, h, l, c, k, dr)
                break
    return dict(both_pools=bp, bp_dir=bd, cont_cap=cap)


# --------------------------------------------------------------------------------------------------------------
# new-htf-regime-trigger-and-entry: the monthly OB activation column
# --------------------------------------------------------------------------------------------------------------

def mob_state_after(o, h, l, c, month_id, episodes: list | None = None) -> np.ndarray:
    """State after each session j (+1 / -1 / 0). References are COMPLETED months only (the last down-close month D, the last up-close month U); the activation is tested on every session after the
    reference completes and the same candle activates only once until a newer one forms. `episodes` (a list) receives one dict per activation: j, side, D and U as (open, high, low, close)."""
    n = len(h)
    out = np.zeros(n, int)
    state, inv, act_ref = 0, NAN, None
    cur = None
    cm_o = cm_h = cm_l = cm_c = NAN
    dref = uref = None
    for j in range(n):
        m = month_id[j]
        if m != cur:
            if cur is not None:                           # the month just completed becomes a reference candle
                if cm_c < cm_o:
                    dref = (cm_o, cm_h, cm_l, cm_c)
                elif cm_c > cm_o:
                    uref = (cm_o, cm_h, cm_l, cm_c)
            cur, cm_o, cm_h, cm_l = m, float(o[j]), float(h[j]), float(l[j])
        else:
            cm_h, cm_l = max(cm_h, float(h[j])), min(cm_l, float(l[j]))
        cm_c = float(c[j])
        if state == 1 and l[j] < inv:
            state = 0
        elif state == -1 and h[j] > inv:
            state = 0
        up = dref is not None and h[j] > dref[1] and act_ref != ("d", dref)
        dn = uref is not None and l[j] < uref[2] and act_ref != ("u", uref)
        if up and dn:
            up, dn = (c[j] >= o[j]), (c[j] < o[j])
        if up and state != 1:
            state, inv, act_ref = 1, dref[2], ("d", dref)
            if episodes is not None:
                episodes.append(dict(j=j, side=1, D=dref, U=uref))
        elif dn and state != -1:
            state, inv, act_ref = -1, uref[1], ("u", uref)
            if episodes is not None:
                episodes.append(dict(j=j, side=-1, D=dref, U=uref))
        out[j] = state
    return out


def mob_column(d, ks) -> np.ndarray:
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    st = mob_state_after(o, h, l, c, np.asarray(d.index.to_period("M").astype(str)))
    return np.array([st[int(k) - 1] if int(k) >= 1 else 0 for k in ks], int)


# --------------------------------------------------------------------------------------------------------------
# new-weekly-idea-persistence
# --------------------------------------------------------------------------------------------------------------

def persist_week(wk_bias, flip, ks, d) -> np.ndarray:
    """The weekly bias per row with the idea kept: per week the first nonzero reading v0 (of the rows so far; the extreme is that of the week's first session - Monday, or the first session of a
    holiday week [our interpretation]) holds on the later rows as long as (a) a Tuesday / Wednesday daily close (completed before the row) lay
    beyond Monday's extreme AGAINST v0 - the case the plain reading would turn - and (b) the table's stateful bias `flip` has not changed since the week's first row (only a close-based flip trigger does).
    Without (a) the row keeps the table's own reading."""
    wk = np.asarray(wk_bias, int).copy()
    wk_in = wk.copy()                                        # the plain readings (the loop below overwrites wk)
    fl = np.asarray(flip, int) if flip is not None else np.zeros(len(wk), int)
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    wd = d.index.weekday
    wid = np.asarray(d.index.to_period("W-FRI").astype(str))
    r0 = 0
    for r in range(len(wk)):
        k = int(ks[r])
        if r > 0 and wid[k] == wid[int(ks[r - 1])]:
            pass
        else:
            r0 = r
        if r == r0:
            continue
        v0 = next((int(x) for x in wk_in[r0:r + 1] if x), 0)       # the week's FIRST NONZERO reading (Monday reads 0, Tuesday -1: -1 is the idea)
        if not v0:
            continue
        k0 = int(ks[r0])
        mon_hi, mon_lo = h[k0], l[k0]
        beyond = False
        for q in range(k0 + 1, k):
            if wid[q] != wid[k0]:
                break
            if wd[q] in (1, 2) and ((v0 < 0 and c[q] > mon_hi) or (v0 > 0 and c[q] < mon_lo)):
                beyond = True
        if beyond and fl[r] == fl[r0]:
            if wk[r] != v0:
                sw("weekly_persist")
            wk[r] = v0
    return wk


# --------------------------------------------------------------------------------------------------------------
# finish6
# --------------------------------------------------------------------------------------------------------------

def finish6(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, df=None) -> pd.DataFrame:
    """Add the b6 columns named in `cfg` to the table `out` (one row per trading day)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    if "bp" in cfg:
        for k_, v_ in both_pools_columns(o, h, l, c, ks, int(cfg["bp"])).items():
            out[k_] = v_
        sw("both_pools_gate")
    if "mob" in cfg:
        out["mob"] = mob_column(d, ks)
        sw("mob")
    if "ft" in cfg and "m_ctrl" not in out:
        from . import bh5 as BH5
        out["m_ctrl"] = BH5.monthly_ctrl_column(d, ks)
    if "wp" in cfg and "wk_bias" in out:
        out["wk_bias"] = persist_week(out.wk_bias.values, out.flip.values if "flip" in out else None, ks, d)
    return out
