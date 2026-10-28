"""Caption-gap pass, package bias_htf#5/7 (digests/rulebook_gaps/definitions_pd_arrays_structure.md items 191, 193, 201 and levels_liquidity_targets.md items 22, 55, 75, 78, 93, 102, 103, 115, 135, 136, 138,
142, 147, 149, 179 (+ the helpers of 192, 199, 204, 30)) - TABLE SIDE.

The daily / weekly columns these switches need. Everything here is a pure function of COMPLETED sessions (the sessions before the row's day) and of the arrays `htf.table` built (`Arr.known` = the first
session index at which an array may be used): the row of session k never reads session k's high / low / close nor an incomplete week or month. The engine side (side gates, per-order rules, the draw prefs,
the intraday states) is `bh5e.py`. `bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b5"; `finish5` runs at the end of `htf.table` (after bh4.finish4); `table_cfg` returns
what the table's day loop itself reads (the up-close FVG anchor). Thresholds the sources never give are marked [our interpretation]; every rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  iof_ft_up / iof_ft_dn      (193)   1 when the latest broken daily high (low) got no higher high (lower low) within `iof_follow_days` sessions - the daily `iof` is cut to 0 on that side
  m_ctrl                     (201)   -1 / +1: two successive lower monthly pivot highs (higher lows) = a long-term high (low) is in control
  nwog_gap / nwog_fill       (22)    the week's NWOG direction (+1 up / -1 down / 0) and +1 = full fill of Friday's close expected, 0 = a partial fill is fine; the same for every row of the week
  dce_proj / dce_proj_dn     (55)    the daily A-B projection levels (tuples), upward from an untaken pivot high / downward from an untaken pivot low
  stack_side / stack_hi      (75)    +1 / -1 and the nearest stacked untaken daily high (low)
  bprog / bprog_tgt          (78)    the buy (+1) / sell (-1) program state and its target array edge
  wk_ssl / wk_ssl_lvl / wk_ssl_hi / wk_ssl_fri / wk_ssl_fvg   (93)  -1 / +1, the cluster level, the latest 15m short-term high (low) and Friday's high (low) - the same for every row of the week
  wk_prem_draw / wk_disc_draw   (102)  the nearest unfilled W / D inefficiency above / below Tuesday's close (rows from Wednesday)
  b7sf_guard / b7sf_guard_sh (103)   the MT of the last daily bullish (bearish) OB known at the row
  shift_origin_hi / shift_origin_lo / shift_last   (115)   the untaken swing high (low) the last bearish (bullish) daily MSS started from, and the side of the most recent MSS
  fast_week / fw_level / fw_tgt   (136)  +1 / -1 (the reversal side after a fast bearish / bullish week), the first array touched (its MT) and the nearest opposing array
  eqb_dir / eqb_in_eq / eqb_tgt   (138)  the daily consolidation breakout side, 1 inside the range within 10 % of its EQ, the nearest untouched W / M imbalance in the breakout direction
  d_draw / d_draw_dir        (147)   the carried daily draw and its direction
  run_arr                    (149)   +1 / -1: raid_run_days up (down) closes with the last high (low) in a live daily premium (discount) array
  pd20_hi / pd20_lo / pd20 / pd20_pos / pd20_old_hi / pd20_old_lo / pd20_roll   (179)  the rolled dealing range
  sea_w_ob / sea_w_brk       (142)   price inside a weekly bullish (bearish) OB / above a broken weekly pivot high (below a broken pivot low) - the seasonal-entry report
  (wk_ref_friday freezes the weekly premium / discount split columns at the week's first row, item 135)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import bh2 as BH2
from . import bh3 as BH3
from . import bh4 as BH4

HITS = BH2.HITS
NAN = float("nan")
sw = BH2.sw


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b5" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.dfvg_upclose_anchor:
        c["upc"] = 1
    if p.iof_follow:
        c["iff"] = int(p.iof_follow_days)
    if p.monthly_ctrl:
        c["mctrl"] = 1
    if p.nwog_fill_rule:
        c["nfill"] = float(p.nwog_eq_band)
    if p.dce_proj_study:
        c["dce"] = 1
    if p.stack_draw:
        c["stack"] = int(p.stack_n)
    if p.program_gate:
        c["bprog"] = 1
    if p.shift_origin_pool:
        c["sorg"] = 1
    if p.fast_week_rev:
        c["fw"] = float(p.fast_week_adr)
    if p.eq_breakout_draw:
        c["eqb"] = [int(p.drange_n), p.drange_break]
    if p.d_draw_carry:
        c["ddraw"] = 1
    if p.pdh_raid_rev:
        c["runarr"] = int(p.raid_run_days)
    if p.wk_ssl_draw:
        c["ssl"] = 1
    if p.wk_two_draw:
        c["two"] = 1
    if p.b7_spike_floor:
        c["b7sf"] = 1
    if p.seasonal_tag:
        c["sea"] = 1
    if p.range_rollover:
        c["roll"] = 1
    if p.wk_ref_friday:
        c["wref"] = 1
    return c


def table_cfg(X: dict) -> dict:
    """The table-time part of the "b5" block (what the day loop reads), with defaults."""
    b = (X or {}).get("b5") or {}
    return {"upc": bool(b.get("upc"))}


def needs_columns(p) -> bool:
    """Any table switch of this package is on."""
    return bool(bx_cfg(p))


# --------------------------------------------------------------------------------------------------------------
# item 191: the daily FVG's up-close anchor
# --------------------------------------------------------------------------------------------------------------

def upclose_edges(o, h, l, c, z, back: int = 5) -> tuple:
    """A5-htf-fvg-last-upclose-anchor (cc09_008 ~12:27: "we want to see the last up close"): the (top, bottom) of the daily FVG `z` (levels.Zone, `z.i` = the third candle). A bearish gap whose first candle
    (z.i - 2) closed DOWN takes its upper reference from the low of the last UP-close candle before the down move (walked back at most `back` bars [our interpretation of 'the last up close']); a lower
    low than the gap's own top never shrinks it. A bullish gap whose first candle closed up mirrors it with the high of the last down-close candle. The gap's other edge is unchanged."""
    c1 = z.i - 2
    top, bot = float(z.top), float(z.bottom)
    if z.kind == "bear":
        if c[c1] < o[c1]:
            for j in range(c1 - 1, max(-1, c1 - 1 - back), -1):
                if c[j] > o[j]:
                    top = max(top, float(l[j]))
                    break
    else:
        if c[c1] > o[c1]:
            for j in range(c1 - 1, max(-1, c1 - 1 - back), -1):
                if c[j] < o[j]:
                    bot = min(bot, float(h[j]))
                    break
    return top, bot


# --------------------------------------------------------------------------------------------------------------
# item 193: the IOF follow-through test
# --------------------------------------------------------------------------------------------------------------

def iof_follow_columns(h, l, c, ks, days: int) -> dict:
    """B6-broken-highs-follow-through (cc06_002 ~5:05: "are the swing highs breaking and seeing higher highs"): the daily IOF is bullish when (a) the down-close candles hold AND (b) broken swing highs are
    followed by higher highs. Test (b): the latest swing high (1-bar pivot) a daily CLOSE broke - the break session j - needs a session within the next `days` sessions that trades above the high of j;
    verdict 'failed' (iof_ft_up = 1) once the window has completed without one (a window still running is no verdict). iof_ft_dn is the mirror for broken swing lows [our interpretation: the time limit]."""
    ph, pl = L.pivots(h, l, 1)
    R = len(ks)
    up, dn = np.zeros(R, int), np.zeros(R, int)

    def events(piv, high: bool):
        ev = []
        for q in piv:
            for j in range(q.i + 2, len(c)):
                if (c[j] > q.price) if high else (c[j] < q.price):
                    ev.append(j)
                    break
        return sorted(set(ev))

    for arr, piv, high in ((up, ph, True), (dn, pl, False)):
        ev = events(piv, high)
        for r, k in enumerate(ks):
            k = int(k)
            js = [j for j in ev if j <= k - 1]
            if not js:
                continue
            j = js[-1]
            seg_end = min(j + days, k - 1)
            seg = (h[j + 1:seg_end + 1] > h[j]) if high else (l[j + 1:seg_end + 1] < l[j])
            if len(seg) and seg.any():
                continue
            if j + days <= k - 1:
                arr[r] = 1
    return {"iof_ft_up": up, "iof_ft_dn": dn}


def apply_iof_follow(out: pd.DataFrame) -> pd.DataFrame:
    """The daily iof column after the follow-through test: a bullish iof with iof_ft_up, a bearish one with iof_ft_dn, drops to 0; combo2 follows (react, then iof, then the P/D reading)."""
    if "iof" not in out or "iof_ft_up" not in out:
        return out
    io = out.iof.values.astype(int)
    new = np.where((io > 0) & (out.iof_ft_up.values == 1), 0, np.where((io < 0) & (out.iof_ft_dn.values == 1), 0, io))
    if (new != io).any():
        hit("iof_follow_cut")
    out["iof"] = new
    if "combo2" in out and "react" in out and "pd" in out:
        out["combo2"] = [int(r) if r else (int(i) if i else int(p_)) for r, i, p_ in zip(out.react, out.iof, out.pd)]
    sw("iof_follow")
    return out


# --------------------------------------------------------------------------------------------------------------
# item 201: the monthly structure control
# --------------------------------------------------------------------------------------------------------------

def monthly_ctrl_state(mh, ml, m: int) -> int:
    """new-monthly-structure-control (cc12_001 ~23:53: "we've probably made an intermediate term or long-term high"): from the first `m` completed monthly bars (levels.swing_tiers 'stl' = 1-bar swing
    pivots): two successive LOWER monthly pivot highs (after the higher highs) = a long-term high is in control (-1); two successive HIGHER pivot lows = a long-term low is in control (+1); when both hold
    the more recent pivot decides. 0 otherwise [our interpretation: the HH before the first LH is not required]."""
    if m < 5:
        return 0
    ph, pl = L.swing_tiers(mh[:m], ml[:m], 1)["stl"]
    lh = len(ph) >= 3 and ph[-1].price < ph[-2].price < ph[-3].price
    hl = len(pl) >= 3 and pl[-1].price > pl[-2].price > pl[-3].price
    if lh and hl:
        return -1 if ph[-1].i > pl[-1].i else 1
    return -1 if lh else (1 if hl else 0)


def monthly_smt_map(df_a, df_b, months: int = 3) -> dict:
    """new-monthly-structure-control (cc12_001 ~23:53, 'confirm with SMT'; FX: DXY, indices: SPX / NDX / DJI - here the two index frames): {session date: +1 / -1 / 0} known before that session, from the COMPLETED
    monthly bars of both frames. For a completed month j (j >= 1): exactly one index makes a higher monthly high than month j-1 while the other does not = -1 (a long-term high); exactly one makes a lower
    monthly low = +1 (a long-term low); both or neither = no event. The latest event inside the last `months` completed months counts [our interpretation of the window]."""
    from .htf import sessions
    a, b = sessions(df_a), sessions(df_b)
    idx = a.index.intersection(b.index)
    a, b = a.loc[idx], b.loc[idx]
    if not len(idx):
        return {}
    pa = a.groupby(a.index.to_period("M")).agg(h=("high", "max"), l=("low", "min"))
    pb = b.groupby(b.index.to_period("M")).agg(h=("high", "max"), l=("low", "min"))
    ev = {}
    for j in range(1, len(pa)):
        ua, ub = pa.h.iloc[j] > pa.h.iloc[j - 1], pb.h.iloc[j] > pb.h.iloc[j - 1]
        da, db = pa.l.iloc[j] < pa.l.iloc[j - 1], pb.l.iloc[j] < pb.l.iloc[j - 1]
        e = (-1 if ua != ub else 0) + (1 if da != db else 0)
        ev[pa.index[j]] = e if e in (-1, 1) else 0                           # both kinds in one month cancel
    per = list(pa.index)
    out = {}
    for t in idx:
        m = t.to_period("M")
        done = [q for q in per if q < m]                                      # completed months only
        val = 0
        for q in reversed(done[-months:]):
            if ev.get(q, 0):
                val = ev[q]
                break
        out[t.date()] = val
    return out


def monthly_ctrl_column(d, ks) -> np.ndarray:
    mo, mh, ml, mc, mlast = BH3.tf_bars(d, "M")
    out = np.zeros(len(ks), int)
    if len(mc) < 5:
        return out
    mm = np.searchsorted(mlast, np.asarray(ks) - 1, side="right")
    cache = {}
    for r, m in enumerate(mm):
        m = int(m)
        if m not in cache:
            cache[m] = monthly_ctrl_state(mh, ml, m)
        out[r] = cache[m]
    return out


# --------------------------------------------------------------------------------------------------------------
# item 22: the Friday-close location and the NWOG fill
# --------------------------------------------------------------------------------------------------------------

def nwog_fill_state(fri_close: float, gap_sign: int, lo: float, hi: float, share_above: float, band: float) -> int:
    """L5-friday-close-location-fill (028 ~1:09:54: 'a full return back to Friday's close'): +1 = Friday's close is expected to be filled fully, 0 = a partial fill is fine. Friday closed NEAR the EQ of
    the 20-session body range (within +-band of the range) after a week that spent more time on one side of the EQ (`share_above` = the share of the week's 1h closes above it): a gap toward the LESS explored
    side need not fill (0), a gap toward the heavily explored side fills (+1). Not near the EQ (or an even week): +1 [our interpretation: the gap leaves price extended]."""
    if not (hi > lo) or gap_sign == 0:
        return 1
    pos = (fri_close - lo) / (hi - lo)
    if abs(pos - 0.5) > band:
        return 1
    if share_above == 0.5:
        return 1
    explored = 1 if share_above > 0.5 else -1
    return 1 if gap_sign == explored else 0


def nwog_fill_columns(d, df, ks, band: float = 0.10) -> dict:
    """The week's NWOG (Friday's close to the Sunday-18:00 first print = the open of the week's first session) and `nwog_fill_state` for every row of the week, from data up to Friday's close and the
    Sunday open only. The time spent is counted on the 1h closes of the sessions of the ended week (the daily closes without a frame)."""
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    R = len(ks)
    gap, fill = np.zeros(R, int), np.ones(R, int)
    wk = d.index.to_period("W-FRI")
    first = {}
    for k in range(len(d)):
        first.setdefault(wk[k], k)
    one_h = None
    if df is not None and len(df):
        one_h = df.close.resample("1h").last().dropna()
    cache = {}
    for r, k in enumerate(ks):
        k = int(k)
        k0 = first[wk[k]]
        if k0 < 20:
            continue
        if k0 not in cache:
            g = float(o[k0] - c[k0 - 1])
            gs = int(np.sign(g)) if abs(g) > 0 else 0
            bh_, bl_ = np.maximum(o, c)[k0 - 20:k0], np.minimum(o, c)[k0 - 20:k0]
            lo, hi = float(bl_.min()), float(bh_.max())
            eq = (lo + hi) / 2
            share = NAN
            if one_h is not None:
                wprev = first.get(wk[k0 - 1], k0 - 5)
                a_ = d.index[wprev] - pd.Timedelta(hours=6)
                b_ = d.index[k0] - pd.Timedelta(hours=6)
                ix = one_h.index.tz_localize(None) if one_h.index.tz is not None else one_h.index
                seg = one_h[(ix >= a_) & (ix < b_)]
                if len(seg):
                    share = float((seg.values > eq).mean())
            if share != share:
                sub = c[first.get(wk[k0 - 1], k0 - 5):k0]
                share = float((sub > eq).mean()) if len(sub) else 0.5
            cache[k0] = (gs, nwog_fill_state(float(c[k0 - 1]), gs, lo, hi, share, band))
        gap[r], fill[r] = cache[k0]
    return {"nwog_gap": gap, "nwog_fill": fill}


# --------------------------------------------------------------------------------------------------------------
# item 55: the old-high to daily-CE projection
# --------------------------------------------------------------------------------------------------------------

def dce_levels(a: float, b: float) -> tuple:
    """L13-old-high-to-daily-ce-projection (019 ~2:35, '25 percent 50 75 in terminus'): the midpoint of A-B, then B, then B + k(B - A) for k = 0.25, 0.5, 0.75, 1.0 (the terminus). Mirror when B < A (the
    formula is the same on signed distances)."""
    d = b - a
    return tuple(float(x) for x in (a + d / 2, b, b + 0.25 * d, b + 0.5 * d, b + 0.75 * d, b + d))


def dce_columns(o, h, l, c, ks, look: int = 60) -> dict:
    """A = the latest daily pivot high (1-bar pivot) that has a LATER candle with a higher body CE ((open + close) / 2), A untaken until that candle; B = the nearest such CE - 'the next higher daily candle' -
    [our interpretation]. dce_proj = the levels upward; dce_proj_dn the mirror from an untaken pivot low and the nearest LOWER body CE. Empty tuples when there is no pair."""
    ph, pl = L.pivots(h, l, 1)
    ce = (o + c) / 2
    R = len(ks)
    up, dn = [()] * R, [()] * R
    for r, k in enumerate(ks):
        k = int(k)
        a = max(0, k - look)
        for q in reversed(ph):
            if q.known > k - 1 or q.i < a:
                continue
            cands = [ce[b] for b in range(q.i + 1, k) if ce[b] > q.price and h[q.i + 1:b].max(initial=-np.inf) < q.price]       # B = a later candle whose body CE is above A, A untaken until that candle [our interpretation]
            if cands:
                up[r] = dce_levels(float(q.price), float(min(cands)))
                break
        for q in reversed(pl):
            if q.known > k - 1 or q.i < a:
                continue
            cands = [ce[b] for b in range(q.i + 1, k) if ce[b] < q.price and l[q.i + 1:b].min(initial=np.inf) > q.price]
            if cands:
                dn[r] = dce_levels(float(q.price), float(max(cands)))
                break
    return {"dce_proj": up, "dce_proj_dn": dn}


# --------------------------------------------------------------------------------------------------------------
# item 75: the stacked unrun highs
# --------------------------------------------------------------------------------------------------------------

def stack_columns(bk, ks, px, n: int, look: int = 20) -> dict:
    """B2-stacked-unrun-highs (055 ~4:19: 'they're stacking that up'): stack_side +1 when at least `n` daily pivot highs (1-bar pivots) formed in the last `look` sessions are still untaken (no later high
    above - untaken highs are a descending staircase by construction) and above the price, AND the price sits in or above an unfilled weekly / daily BISI (alive in the table's sense) that no daily close
    broke below its CE since it formed; stack_hi = the nearest stacked high. -1 / the nearest stacked low for the mirror (untaken pivot lows below, a SIBI, no close above its CE). [our interpretation of
    'since the last daily low': the last `look` sessions]."""
    h, l, c = bk.h, bk.l, bk.c
    ph, pl = L.pivots(h, l, 1)
    R = len(ks)
    side, lvl = np.zeros(R, int), np.full(R, NAN)
    rungs = [()] * R
    for r, k in enumerate(ks):
        k = int(k)
        x = float(px[r])
        if k < 8 or x != x:
            continue
        a = max(0, k - look)
        hi_ = [q.price for q in ph if q.known <= k - 1 and q.i >= a and q.price > x and h[q.i + 1:k].max(initial=-np.inf) < q.price]
        lo_ = [q.price for q in pl if q.known <= k - 1 and q.i >= a and q.price < x and l[q.i + 1:k].min(initial=np.inf) > q.price]
        up_ok = dn_ok = False
        for arr in bk.arrs:
            if arr.tf not in ("D", "W") or arr.typ != "fvg" or arr.known > k or not bk.alive(arr, k):
                continue
            seg = c[arr.known:k]
            if arr.kind == "bull" and x >= arr.bottom and (not len(seg) or seg.min() >= arr.ce):
                up_ok = True
            if arr.kind == "bear" and x <= arr.top and (not len(seg) or seg.max() <= arr.ce):
                dn_ok = True
        s = 1 if (len(hi_) >= n and up_ok) else 0
        t = -1 if (len(lo_) >= n and dn_ok) else 0
        if s and not t:
            side[r], lvl[r] = 1, min(hi_)
            rungs[r] = tuple(sorted(hi_)) + _reh_in_premium(bk, k, hi_, x, 1)
        elif t and not s:
            side[r], lvl[r] = -1, max(lo_)
            rungs[r] = tuple(sorted(lo_, reverse=True)) + _reh_in_premium(bk, k, lo_, x, -1)
    return {"stack_side": side, "stack_hi": lvl, "stack_rungs": rungs}


def _reh_in_premium(bk, k: int, lv: list, x: float, side: int) -> tuple:
    """Item 75, the last rung: 'any REH sitting inside an HTF premium VI/FVG' - the relative equal highs (equal_levels of the stacked pivot highs, tolerance 0.05 % of the price [our interpretation]) that lie
    inside a live weekly / daily bearish FVG / VI above the price (mirror: relative equal lows inside a bullish one below), beyond the stacked highs; ascending (descending) order."""
    if len(lv) < 2:
        return ()
    eq = L.equal_levels(np.asarray(lv, float), 0.0005 * abs(x)) if side > 0 else [-q for q in L.equal_levels(-np.asarray(lv, float), 0.0005 * abs(x))]
    out = []
    for v in eq:
        for arr in bk.arrs:
            if arr.tf not in ("D", "W") or arr.typ not in ("fvg", "vi") or arr.known > k or not bk.alive(arr, k):
                continue
            if arr.kind == ("bear" if side > 0 else "bull") and arr.bottom <= v <= arr.top and (v - x) * side > 0:
                out.append(float(v))
                break
    return tuple(sorted(set(out), reverse=side < 0))


# --------------------------------------------------------------------------------------------------------------
# item 78: the buy / sell program
# --------------------------------------------------------------------------------------------------------------

def program_columns(bk, ks) -> dict:
    """B2-buy-program-eq-draw (061 ~45:42: 'we're looking for the first first equilibrium or higher PD array'): state after each completed session j - bprog +1 (BUY_PROGRAM) set by a daily CLOSE above the last
    daily short-term high (a fresh break of the latest 1-bar pivot high no close had broken before) while the weekly leg is bearish (the latest completed weekly pivot high P and the lowest weekly low since it,
    leg low L < P) and the close is still below P; its target = the nearest unmitigated weekly / daily array (FVG, VI, OB - alive in the table's sense, incl. inversions through their kind) whose near
    edge lies at or above the leg's 50 % AND above the close. The state ends when a daily high reaches the target. bprog_tgt = that near edge. -1 / below for the SELL_PROGRAM (bullish weekly leg, a close
    below the last daily short-term low, an array with its near edge at or below the leg's 50 % and below the close)."""
    h, l, c = bk.h, bk.l, bk.c
    D = len(c)
    ph, pl = L.pivots(h, l, 1)
    wh, wlow = bk.wh, bk.wlow
    wl = np.asarray(bk.wl)
    st = np.zeros(D, int)
    tg = np.full(D, NAN)
    cur, tgt, inval = 0, NAN, NAN
    used_h, used_l = set(), set()
    wcache = {}

    def weekly(j):
        nw = int(np.searchsorted(wl, j + 1, side="right"))              # weeks completed by session j (last session position <= j)
        if nw not in wcache:
            wph, wpl = L.pivots(wh[:nw], wlow[:nw], 1) if nw >= 3 else ([], [])
            leg = None
            if wph:
                P = wph[-1]
                lo_ = float(wlow[P.i:nw].min())
                if lo_ < P.price:
                    leg = (-1, float(P.price), lo_)                    # a bearish leg: high P -> low
            lleg = None
            if wpl:
                Q = wpl[-1]
                hi_ = float(wh[Q.i:nw].max())
                if hi_ > Q.price:
                    lleg = (1, hi_, float(Q.price))                    # a bullish leg: low Q -> high
            wcache[nw] = (leg, lleg)
        return wcache[nw]

    for j in range(D):
        if cur != 0:
            if (cur > 0 and (h[j] >= tgt or c[j] < inval)) or (cur < 0 and (l[j] <= tgt or c[j] > inval)):
                cur, tgt, inval = 0, NAN, NAN                       # the target traded (the hit: neutral) - or the leg's extreme closed through (the program failed) [our interpretation]
        if cur == 0 and j >= 3:
            leg, lleg = weekly(j)
            if leg is not None:
                _, P, lo_ = leg
                q = next((q for q in reversed(ph) if q.known <= j - 1 and q.i not in used_h), None)
                if q is not None and c[j] > q.price >= 0 and c[j - 1] <= q.price and c[j] < P:
                    used_h.add(q.i)
                    eq = (P + lo_) / 2
                    best = None
                    for a in bk.arrs:
                        if a.tf not in ("D", "W") or a.typ not in ("fvg", "ob", "vi") or a.known > j + 1 or not bk.alive(a, j + 1):
                            continue
                        if a.bottom >= eq - 1e-9 and a.bottom > c[j] and (best is None or a.bottom < best):
                            best = float(a.bottom)
                    if best is not None:
                        cur, tgt, inval = 1, best, lo_
            if cur == 0 and lleg is not None:
                _, Hh, Qp = lleg
                q = next((q for q in reversed(pl) if q.known <= j - 1 and q.i not in used_l), None)
                if q is not None and c[j] < q.price and c[j - 1] >= q.price and c[j] > Qp:
                    used_l.add(q.i)
                    eq = (Hh + Qp) / 2
                    best = None
                    for a in bk.arrs:
                        if a.tf not in ("D", "W") or a.typ not in ("fvg", "ob", "vi") or a.known > j + 1 or not bk.alive(a, j + 1):
                            continue
                        if a.top <= eq + 1e-9 and a.top < c[j] and (best is None or a.top > best):
                            best = float(a.top)
                    if best is not None:
                        cur, tgt, inval = -1, best, Hh
        st[j], tg[j] = cur, tgt
    ks_ = np.asarray(ks)
    prev = np.maximum(ks_ - 1, 0)
    ok = ks_ >= 1
    return {"bprog": np.where(ok, st[prev], 0), "bprog_tgt": np.where(ok, tg[prev], NAN)}


# --------------------------------------------------------------------------------------------------------------
# item 115: the shift-origin pool
# --------------------------------------------------------------------------------------------------------------

def shift_origin_columns(h, l, c, ks) -> dict:
    """new-shift-origin-pool (cc05_002 ~7:58: 'your eyes need to go right to the high it just came from'): on a bearish daily MSS (a close below the latest 1-bar pivot low that no close had broken) the
    pivot high the down-leg started from (the latest pivot high before that low) is a buy-side pool, kept until a later high trades above it; a bullish MSS stores the swing low the up-leg came from. The
    row of session k shows the most recent still-untaken origin (shift_origin_hi / _lo) and shift_last = the side of the most recent MSS (+1 bullish)."""
    ph, pl = L.pivots(h, l, 1)
    D = len(c)
    ev = []                                              # (j, side, origin pivot)
    used_l, used_h = set(), set()
    for j in range(2, D):
        q = next((q for q in reversed(pl) if q.known <= j - 1 and q.i not in used_l and not (c[q.i + 1:j] < q.price).any()), None)
        if q is not None and c[j] < q.price:
            used_l.add(q.i)
            o_ = next((x for x in reversed(ph) if x.i < q.i), None)
            if o_ is not None:
                ev.append((j, -1, o_))
        q = next((q for q in reversed(ph) if q.known <= j - 1 and q.i not in used_h and not (c[q.i + 1:j] > q.price).any()), None)
        if q is not None and c[j] > q.price:
            used_h.add(q.i)
            o_ = next((x for x in reversed(pl) if x.i < q.i), None)
            if o_ is not None:
                ev.append((j, 1, o_))
    R = len(ks)
    hi, lo, last = np.full(R, NAN), np.full(R, NAN), np.zeros(R, int)
    for r, k in enumerate(ks):
        k = int(k)
        seen = [e for e in ev if e[0] <= k - 1]
        if seen:
            last[r] = seen[-1][1]
        for j, s, o_ in reversed(seen):
            if s < 0 and hi[r] != hi[r] and h[o_.i + 1:k].max(initial=-np.inf) < o_.price:
                hi[r] = o_.price
            if s > 0 and lo[r] != lo[r] and l[o_.i + 1:k].min(initial=np.inf) > o_.price:
                lo[r] = o_.price
            if hi[r] == hi[r] and lo[r] == lo[r]:
                break
    return {"shift_origin_hi": hi, "shift_origin_lo": lo, "shift_last": last}


# --------------------------------------------------------------------------------------------------------------
# item 136: the fast week
# --------------------------------------------------------------------------------------------------------------

def fast_week_columns(bk, ks, px, mult: float, df=None) -> dict:
    """B7-fast-week-htf-reversal-level (cc07_007 ~13:57): from the first row of Wednesday on (the week's sessions before the row: Monday and Tuesday at least), when the range of those sessions is at least
    `mult` x ADR5 (the mean daily range of the five sessions before the week) and the move reached a live daily / weekly array opposite to it (a bullish array for a drop; the array lay below the week's
    open and the week's extreme traded into it), the FIRST array touched (the one nearest the open) is the reversal level fw_level (its MT / CE) as long as no daily close of the week went through that MT.
    fast_week = the reversal side (+1 after a fast DOWN week, -1 after a fast UP week); fw_tgt = the nearest live opposing array edge beyond the price. With the intraday frame `df` the live 4h FVGs join the daily / weekly arrays ('the HTF level': 4h included, review fix)."""
    d = bk.d
    o, h, l, c = bk.o, bk.h, bk.l, bk.c
    wk = d.index.to_period("W-FRI")
    first = {}
    for k in range(len(d)):
        first.setdefault(wk[k], k)
    R = len(ks)
    fw, lvl, tgt = np.zeros(R, int), np.full(R, NAN), np.full(R, NAN)
    for r, k in enumerate(ks):
        k = int(k)
        k0 = first[wk[k]]
        if k - k0 < 2 or k0 < 5:
            continue
        adr = float((h[k0 - 5:k0] - l[k0 - 5:k0]).mean())
        wh_, wl_ = float(h[k0:k].max()), float(l[k0:k].min())
        if not adr > 0 or wh_ - wl_ < mult * adr:
            continue
        mv = float(c[k - 1] - o[k0])
        if mv == 0:
            continue
        down = mv < 0
        best = None
        pool0 = [a for a in bk.arrs if a.tf in ("D", "W") and a.typ in ("fvg", "ob") and a.known <= k0 and bk.alive(a, k0)] + h4_arrs(df, d, k0)
        for a in pool0:
            if down and a.kind == "bull" and a.top <= o[k0] and wl_ <= a.top and (best is None or a.top > best.top):
                best = a
            if (not down) and a.kind == "bear" and a.bottom >= o[k0] and wh_ >= a.bottom and (best is None or a.bottom < best.bottom):
                best = a
        if best is None:
            continue
        seg = c[k0:k]
        if (down and seg.min() < best.ce) or ((not down) and seg.max() > best.ce):
            continue
        fw[r], lvl[r] = (1 if down else -1), float(best.ce)
        x = float(px[r])
        cands = [a for a in bk.arrs if a.tf in ("D", "W") and a.typ in ("fvg", "ob", "vi") and a.known <= k and bk.alive(a, k)] + h4_arrs(df, d, k)
        if down:
            ups = [a.bottom for a in cands if a.kind == "bear" and a.bottom > x]
            tgt[r] = min(ups) if ups else NAN
        else:
            dns = [a.top for a in cands if a.kind == "bull" and a.top < x]
            tgt[r] = max(dns) if dns else NAN
    return {"fast_week": fw, "fw_level": lvl, "fw_tgt": tgt}


# --------------------------------------------------------------------------------------------------------------
# item 138: the EQ consolidation breakout
# --------------------------------------------------------------------------------------------------------------

def eqb_columns(bk, ks, px, n: int, brk: str) -> dict:
    """B1-eq-consolidation-breakout (cc06_002 ~7:55: 'if price is at equilibrium ... move to an imbalance'): uses the daily consolidation regime (bh1.drange_states over the last `n` closes). eqb_dir = the
    breakout side (a close beyond the range; +1 / -1) at the row; eqb_in_eq = 1 while the range holds and the prior close is within 10 % of the range of its EQ; eqb_tgt = the nearest untouched weekly /
    monthly imbalance (FVG, VI) in the breakout direction (a bearish one above / a bullish one below the price, no daily bar traded into it since it formed)."""
    from . import bh1 as BH1
    h, l, c = bk.h, bk.l, bk.c
    inn, st, rhi, rlo = BH1.drange_states(h, l, c, int(n), brk)
    R = len(ks)
    ks_ = np.asarray(ks)
    d_dir, in_eq, tgt = np.zeros(R, int), np.zeros(R, int), np.full(R, NAN)
    for r, k in enumerate(ks_):
        k = int(k)
        if k < 1:
            continue
        s, inside = int(st[k - 1]), int(inn[k - 1])
        d_dir[r] = s
        if inside and rhi[k - 1] == rhi[k - 1] and rhi[k - 1] > rlo[k - 1]:
            eq = (rhi[k - 1] + rlo[k - 1]) / 2
            in_eq[r] = int(abs(c[k - 1] - eq) <= 0.10 * (rhi[k - 1] - rlo[k - 1]))
        if s:
            x = float(px[r])
            best = None
            for a in bk.arrs_all:
                if a.tf not in ("W", "M") or a.typ not in ("fvg", "vi") or a.known > k or not bk.alive(a, k):
                    continue
                if s > 0 and a.kind == "bear" and a.bottom > x and h[a.known:k].max(initial=-np.inf) < a.bottom and (best is None or a.bottom < best):
                    best = float(a.bottom)
                if s < 0 and a.kind == "bull" and a.top < x and l[a.known:k].min(initial=np.inf) > a.top and (best is None or a.top > best):
                    best = float(a.top)
            tgt[r] = best if best is not None else NAN
    return {"eqb_dir": d_dir, "eqb_in_eq": in_eq, "eqb_tgt": tgt}


# --------------------------------------------------------------------------------------------------------------
# item 147: the daily draw that carries across days
# --------------------------------------------------------------------------------------------------------------

def d_draw_columns(out, ks, h, l) -> dict:
    """new-daily-draw-multiday (cc08_006 ~22:03: 'it can take several days'): when a daily bar reacts at a daily array (the table's `react`) and no draw is carried, the table's draw level on that side (draw_up
    for a react up, draw_dn for a react down) is carried: d_draw / d_draw_dir on every following row until a session traded it (the sessions from the setting one up to the row's previous one) or the daily
    `flip` state differs from the one at the setting row. A new reaction sets a new draw only after the old one ended."""
    R = len(out)
    lvl, dr = np.full(R, NAN), np.zeros(R, int)
    react = out.react.values.astype(float) if "react" in out else np.zeros(R)
    flip = out.flip.values if "flip" in out else np.zeros(R)
    du = out.draw_up.values.astype(float) if "draw_up" in out else np.full(R, NAN)
    dd = out.draw_dn.values.astype(float) if "draw_dn" in out else np.full(R, NAN)
    cur_l, cur_d, k_set, f_set = NAN, 0, -1, 0
    for r in range(R):
        k = int(ks[r])
        if cur_d:
            traded = (h[k_set:k].max(initial=-np.inf) >= cur_l) if cur_d > 0 else (l[k_set:k].min(initial=np.inf) <= cur_l)
            fl_chg = (flip[r] != f_set) and not (flip[r] != flip[r] and f_set != f_set)
            if traded or fl_chg:
                cur_l, cur_d = NAN, 0
        if not cur_d and react[r] != 0:
            v = du[r] if react[r] > 0 else dd[r]
            if v == v:
                cur_l, cur_d, k_set, f_set = float(v), (1 if react[r] > 0 else -1), k, flip[r]
        lvl[r], dr[r] = cur_l, cur_d
    return {"d_draw": lvl, "d_draw_dir": dr}


# --------------------------------------------------------------------------------------------------------------
# item 149: the multi-day run into a daily array
# --------------------------------------------------------------------------------------------------------------

def run_into_array_column(bk, ks, n: int) -> np.ndarray:
    """L2-pdh-raid-after-multiday-run (cc08_007 ~5:05: 'I'll look for a buy stop run there and then go short the next day'): +1 when the last `n` completed sessions all closed above their previous close and the
    last session's high reached a live daily premium array (a bearish FVG / OB / VI: its bottom <= the high, the close not above its top); -1 for n down closes and a low in a live discount array."""
    h, l, c = bk.h, bk.l, bk.c
    R = len(ks)
    out = np.zeros(R, int)
    for r, k in enumerate(ks):
        k = int(k)
        if k < n + 1:
            continue
        seg = np.diff(c[k - n - 1:k])
        up, dn = bool((seg > 0).all()), bool((seg < 0).all())
        if not (up or dn):
            continue
        for a in bk.arrs:
            if a.tf != "D" or a.typ not in ("fvg", "ob", "vi") or a.known > k - 1 or not bk.alive(a, k - 1):
                continue
            if up and a.kind == "bear" and a.bottom <= h[k - 1] and c[k - 1] <= a.top:
                out[r] = 1
                break
            if dn and a.kind == "bull" and a.top >= l[k - 1] and c[k - 1] >= a.bottom:
                out[r] = -1
                break
    return out


# --------------------------------------------------------------------------------------------------------------
# item 93: the week's consolidation above a relative-equal-low cluster
# --------------------------------------------------------------------------------------------------------------

def _bars15(df, until: pd.Timestamp, n_bars: int = 96):
    """The last `n_bars` COMPLETE 15m bars of `df` that closed by `until` (a naive timestamp in the frame's own wall clock): o h l c arrays. Empty arrays when there are none."""
    ix = df.index
    cut = until.tz_localize(ix.tz) if ix.tz is not None and until.tzinfo is None else until
    pos = int(ix.searchsorted(cut, side="left"))
    seg = df.iloc[max(0, pos - n_bars * 15):pos]
    if not len(seg):
        return np.array([]), np.array([]), np.array([]), np.array([])
    r = seg.resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    r = r.iloc[-n_bars:]
    return tuple(r[k].values.astype(float) for k in ("open", "high", "low", "close"))


def ssl_state(o15, h15, l15, c15, adr: float, bear_arr, bull_arr, eq_tol_frac: float = 0.05, n_cons: int = 8) -> tuple:
    """L14-consolidation-above-ssl (077 ~14:58): from the 15m bars before the week's open - (side, cluster level, latest 15m short-term high, ) or (0, nan, nan). Bearish (-1): the last `n_cons` 15m bars
    overlap inside 0.3 x ADR5 [the consolidation], a cluster of at least two 15m pivot lows within `eq_tol_frac` x ADR5 of each other (the relative equal lows) lies below the consolidation's low and within
    0.5 x ADR5 of it [our interpretation of 'directly above'], and the window's high was a rejection at a live daily bearish array in `bear_arr` (its bottom <= that high <= its top + 0.1 x ADR5, the
    consolidation's high below the array's bottom). The latest 15m pivot high is the level whose acceptance cancels it. +1 is the mirror (cluster of highs, rejection at a bullish array)."""
    n = len(c15)
    if n < n_cons + 6 or not adr > 0:
        return 0, NAN, NAN
    cl, ch = float(l15[-n_cons:].min()), float(h15[-n_cons:].max())
    if ch - cl > 0.3 * adr:
        return 0, NAN, NAN
    body_h, body_l = h15[:-n_cons], l15[:-n_cons]
    ph, pl = L.pivots(h15, l15, 1)
    tol = eq_tol_frac * adr
    # bearish: lows cluster below
    lows = sorted(q.price for q in pl if q.i < n - n_cons and q.price < cl and cl - q.price <= 0.5 * adr)
    for i in range(len(lows) - 1):
        grp = [x for x in lows if abs(x - lows[i]) <= tol]
        if len(grp) >= 2:
            top_h = float(h15.max())
            rej = any(a[0] <= top_h <= a[1] + 0.1 * adr and ch < a[0] for a in bear_arr)
            if rej:
                hi_p = [q.price for q in ph if q.known <= n - 1]
                return -1, float(min(grp)), float(hi_p[-1]) if hi_p else float(ch)
            break
    highs = sorted((q.price for q in ph if q.i < n - n_cons and q.price > ch and q.price - ch <= 0.5 * adr), reverse=True)
    for i in range(len(highs) - 1):
        grp = [x for x in highs if abs(x - highs[i]) <= tol]
        if len(grp) >= 2:
            low_l = float(l15.min())
            rej = any(a[1] >= low_l >= a[0] - 0.1 * adr and cl > a[1] for a in bull_arr)
            if rej:
                lo_p = [q.price for q in pl if q.known <= n - 1]
                return 1, float(max(grp)), float(lo_p[-1]) if lo_p else float(cl)
            break
    return 0, NAN, NAN


def h4_live_zones(df, until: pd.Timestamp, days: int = 60) -> tuple:
    """The live 4h FVGs of the last `days` calendar days that closed by `until` (the frame's wall clock): ([(bottom, top)] bearish, [(bottom, top)] bullish); live = not filled through the far edge by a later bar.
    4h bars floor at 00:00 of the frame's clock [our interpretation]. ((), ()) without bars."""
    ix = df.index
    cut = until.tz_localize(ix.tz) if ix.tz is not None and until.tzinfo is None else until
    seg = df[(ix < cut) & (ix >= cut - pd.Timedelta(days=days))]
    if len(seg) < 3:
        return [], []
    g = seg.groupby(seg.index.floor("240min"))
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    b = b[(b.index + pd.Timedelta(minutes=240)) <= cut]
    if len(b) < 3:
        return [], []
    o_, h_, l_, c_ = (b[k].values.astype(float) for k in ("open", "high", "low", "close"))
    bear, bull = [], []
    for z in L.fvgs(h_, l_, o_, c_):
        if z.kind == "bear" and h_[z.i + 1:].max(initial=-np.inf) < z.top:
            bear.append((float(z.bottom), float(z.top)))
        elif z.kind == "bull" and l_[z.i + 1:].min(initial=np.inf) > z.bottom:
            bull.append((float(z.bottom), float(z.top)))
    return bear, bull


def h4_arrs(df, d, k: int) -> list:
    """The live 4h FVGs known at the open of session `k` of the daily book `d` as array-like rows (kind, top, bottom, ce, tf '4h', typ 'fvg'): the table-side 4h arrays (review fix, items 102 / 136). Empty without a frame."""
    if df is None or not len(df) or k < 0 or k >= len(d):
        return []
    from types import SimpleNamespace as NS
    bear, bull = h4_live_zones(df, d.index[k] - pd.Timedelta(hours=6))
    return [NS(kind="bear", top=t, bottom=b, ce=(t + b) / 2, tf="4h", typ="fvg") for b, t in bear] + [NS(kind="bull", top=t, bottom=b, ce=(t + b) / 2, tf="4h", typ="fvg") for b, t in bull]


def ssl_fvg_below(h15, l15, s: int, lvl: float) -> float:
    """Item 93, 'plus the inefficiency just below it': the CE of the nearest still-unfilled 15m FVG beyond the cluster level (below an SSL read, above a BSL read), NaN without one."""
    best = NAN
    for z in L.fvgs(h15, l15):
        later_l, later_h = l15[z.i + 1:].min(initial=np.inf), h15[z.i + 1:].max(initial=-np.inf)
        if s < 0 and z.top < lvl and later_l > z.bottom:
            ce = (z.top + z.bottom) / 2
            best = ce if best != best or ce > best else best
        elif s > 0 and z.bottom > lvl and later_h < z.top:
            ce = (z.top + z.bottom) / 2
            best = ce if best != best or ce < best else best
    return float(best)


def wk_ssl_columns(bk, df, ks) -> dict:
    """The weekly state of `ssl_state` for every row of a week, computed once from the 15m bars before the week's first session (Friday's close / the Sunday open) and the daily arrays alive there."""
    d = bk.d
    wk = d.index.to_period("W-FRI")
    first = {}
    for k in range(len(d)):
        first.setdefault(wk[k], k)
    R = len(ks)
    side, lvl, hi, fri, fvg = np.zeros(R, int), np.full(R, NAN), np.full(R, NAN), np.full(R, NAN), np.full(R, NAN)
    if df is None or not len(df):
        return {"wk_ssl": side, "wk_ssl_lvl": lvl, "wk_ssl_hi": hi, "wk_ssl_fri": fri, "wk_ssl_fvg": fvg}
    cache = {}
    for r, k in enumerate(ks):
        k = int(k)
        k0 = first[wk[k]]
        if k0 < 6:
            continue
        if k0 not in cache:
            until = d.index[k0] - pd.Timedelta(hours=6)                 # the session label is the date of the evening's +7h shift: the Sunday 18:00 open is label - 6h
            o15, h15, l15, c15 = _bars15(df, until)
            adr = float((bk.h[k0 - 5:k0] - bk.l[k0 - 5:k0]).mean())
            live = [a for a in bk.arrs if a.tf == "D" and a.typ in ("fvg", "ob", "vi") and a.known <= k0 and bk.alive(a, k0)]
            bear = [(float(a.bottom), float(a.top)) for a in live if a.kind == "bear"]
            bull = [(float(a.bottom), float(a.top)) for a in live if a.kind == "bull"]
            b4, u4 = h4_live_zones(df, until)                          # review fix (93): the rejection may be at a 4h array too ('a D/4h array')
            s, lv, hh = ssl_state(o15, h15, l15, c15, adr, bear + b4, bull + u4)
            cache[k0] = (s, lv, hh, float(bk.h[k0 - 1]) if s < 0 else float(bk.l[k0 - 1]), ssl_fvg_below(h15, l15, s, lv) if s else NAN)
        side[r], lvl[r], hi[r], fri[r], fvg[r] = cache[k0]
    return {"wk_ssl": side, "wk_ssl_lvl": lvl, "wk_ssl_hi": hi, "wk_ssl_fri": fri, "wk_ssl_fvg": fvg}


# --------------------------------------------------------------------------------------------------------------
# item 102: the weekly two-sided map
# --------------------------------------------------------------------------------------------------------------

def two_draw_columns(bk, ks, df=None) -> dict:
    """L14-weekly-two-sided-map (099 ~34:25: 'premium up here discount down here'): from the first row of Wednesday on, the premium draw = the nearest unfilled weekly / daily inefficiency (FVG, VI) above
    TUESDAY's close (its near edge) and the discount draw = the nearest below (its near edge), judged on the arrays alive at Wednesday's open (daily / weekly, and the live 4h FVGs with the intraday frame). NaN on Monday / Tuesday rows and without one."""
    d = bk.d
    wk = d.index.to_period("W-FRI")
    first = {}
    for k in range(len(d)):
        first.setdefault(wk[k], k)
    R = len(ks)
    prem, disc = np.full(R, NAN), np.full(R, NAN)
    cache = {}
    for r, k in enumerate(ks):
        k = int(k)
        k0 = first[wk[k]]
        if k - k0 < 2:
            continue
        kt = k0 + 1                                                    # Tuesday's session (the second session of the week)
        if kt not in cache:
            x = float(bk.c[kt])
            kw = kt + 1
            h4 = h4_arrs(df, d, kw)                                      # review fix: 'daily/4h unfilled arrays'
            ups = [a.bottom for a in bk.arrs if a.tf in ("D", "W") and a.typ in ("fvg", "vi") and a.known <= kw and a.kind == "bear" and a.bottom > x and bk.alive(a, kw)] + [a.bottom for a in h4 if a.kind == "bear" and a.bottom > x]
            dns = [a.top for a in bk.arrs if a.tf in ("D", "W") and a.typ in ("fvg", "vi") and a.known <= kw and a.kind == "bull" and a.top < x and bk.alive(a, kw)] + [a.top for a in h4 if a.kind == "bull" and a.top < x]
            cache[kt] = (float(min(ups)) if ups else NAN, float(max(dns)) if dns else NAN)
        prem[r], disc[r] = cache[kt]
    return {"wk_prem_draw": prem, "wk_disc_draw": disc}


# --------------------------------------------------------------------------------------------------------------
# item 135: the weekly market price = Friday's close
# --------------------------------------------------------------------------------------------------------------

WK_PD_COLS = ("wk_draw_up", "wk_draw_dn", "wk_draw_up_n", "wk_draw_dn_n", "wk_pd", "mo_pd")


def ref_friday_freeze(out: pd.DataFrame) -> pd.DataFrame:
    """new-weekly-market-price-friday-close (cc07_004 ~8:49: 'market price is defined as Friday's close'): the weekly premium / discount split columns of every row of a week hold the values of the week's FIRST
    row, whose price (px) is the previous Friday's close - so the whole week is split at that one price."""
    cols = [c_ for c_ in WK_PD_COLS if c_ in out.columns]
    if not cols or not len(out):
        return out
    idx = [pd.Timestamp(x) for x in out.index]
    wk = [x.to_period("W-FRI") for x in idx]
    vals = {c_: list(out[c_].values) for c_ in cols}
    r0 = 0
    for r in range(len(out)):
        if r == 0 or wk[r] != wk[r - 1]:
            r0 = r
        for c_ in cols:
            vals[c_][r] = vals[c_][r0]
    for c_ in cols:
        out[c_] = vals[c_]
    sw("wk_ref_friday")
    return out


def weekly_open_level(table: pd.DataFrame, day, which: str = "wo_sun") -> float:
    """B13-weekly-open-line-lifetime (051 ~3:27: 'that price I will extend throughout the entirety of this trading week'): the weekly-open line (wo_sun = the Sunday 18:00 first print, wo_mon = the 00:00 open of the
    week's first session's calendar day) of the week containing `day`: the CURRENT week's value, never a prior week's (NaN for a day without a row). The line ends with that trading week (Friday's close)."""
    ts = pd.Timestamp(day).normalize()
    if ts not in table.index and ts.date() not in [pd.Timestamp(x).date() for x in table.index]:
        return NAN
    row = table.loc[ts] if ts in table.index else table.loc[[x for x in table.index if pd.Timestamp(x).date() == ts.date()][0]]
    v = row.get(which)
    return NAN if v is None else float(v)


# --------------------------------------------------------------------------------------------------------------
# item 142: the seasonal entry-array report
# --------------------------------------------------------------------------------------------------------------

def sea_columns(bk, ks, px) -> dict:
    """B23-seasonal-entry-arrays (cc05_011 ~24:21: 'a bearish candle which is a bullish order block'): report columns - sea_w_ob +1 when the price sits inside a live weekly bullish order block (-1 inside a bearish
    one); sea_w_brk +1 when the price is above the latest weekly pivot high that a later weekly CLOSE broke (old resistance turned support), -1 below the latest broken pivot low."""
    R = len(ks)
    ob, brk = np.zeros(R, int), np.zeros(R, int)
    wh, wlow, wc = bk.wh, bk.wlow, bk.wc
    wl = np.asarray(bk.wl)
    wph, wpl = L.pivots(wh, wlow, 1) if len(wh) >= 3 else ([], [])

    def broken(piv, high: bool, nw: int):
        best = None
        for q in piv:
            if q.known > nw - 1:
                continue
            for j in range(q.i + 2, nw):
                if (wc[j] > q.price) if high else (wc[j] < q.price):
                    if best is None or j > best[0]:
                        best = (j, q.price)
                    break
        return best[1] if best else None

    for r, k in enumerate(ks):
        k = int(k)
        x = float(px[r])
        nw = int(np.searchsorted(wl, k, side="right"))                 # weeks completed before session k (their last session position + 1 <= k)
        for a in bk.arrs:
            if a.tf == "W" and a.typ == "ob" and a.known <= k and a.bottom <= x <= a.top and bk.alive(a, k):
                ob[r] = 1 if a.kind == "bull" else -1
                break
        bh_, bl_ = broken(wph, True, nw), broken(wpl, False, nw)
        if bh_ is not None and x > bh_:
            brk[r] = 1
        elif bl_ is not None and x < bl_:
            brk[r] = -1
    return {"sea_w_ob": ob, "sea_w_brk": brk}


# --------------------------------------------------------------------------------------------------------------
# item 179: the dealing range rollover
# --------------------------------------------------------------------------------------------------------------

def rollover_range(lo: float, hi: float, old_hi: float, old_lo: float, x: float, h_last: float, l_last: float, prem: list, disc: list) -> tuple:
    """L14-dealing-range-rollover (cc12_002 ~22:26: 'once this range has been broken ... this range is no longer valid'): the range [lo, hi] after a break. When the last completed session traded beyond the
    OLD range high (`old_hi`, the high of the sessions before it): the range is retired, the new HIGH is the nearest unmitigated premium array edge above the price (`prem`: near edges, bottoms of the live
    bearish arrays above `x`) - the old high and the EQ stay as discount levels; mirror below the old low with `disc` (tops of the live bullish arrays below `x`). Returns (lo, hi, roll) with roll +1 / -1 / 0;
    without an array on that side the range is unchanged (roll 0)."""
    if h_last > old_hi and prem:
        return lo, float(min(prem)), 1
    if l_last < old_lo and disc:
        return float(max(disc)), hi, -1
    return lo, hi, 0


def rollover_columns(out: pd.DataFrame, bk, ks, px, pdcfg) -> pd.DataFrame:
    """Applies `rollover_range` to the table's N-session range (pd20_hi / pd20_lo; the sessions k-n .. k-1, bodies or wicks as the table's) and recomputes pd20 / pd20_pos with the table's own P/D
    reading, plus pd (and combo) when the range replaced them (day_pd '20d'). pd20_old_hi / pd20_old_lo keep the retired extreme as a level, pd20_roll the side of the roll."""
    from .bias_htf import pd_state
    if "pd20_hi" not in out:
        return out
    n, bodies, zone, ote, repl = pdcfg[:5]
    o, h, l, c = bk.o, bk.h, bk.l, bk.c
    R = len(out)
    rh, rl = out.pd20_hi.values.astype(float).copy(), out.pd20_lo.values.astype(float).copy()
    st, ps = out.pd20.values.copy(), out.pd20_pos.values.astype(float).copy()
    oh, ol, rr = np.full(R, NAN), np.full(R, NAN), np.zeros(R, int)
    top_, bot_ = (np.maximum(o, c), np.minimum(o, c)) if bodies else (h, l)
    carry = None                                       # review fix: the rolled range lasts until its array is traded or the range breaks the other way [our interpretation of 'no longer valid']
    for r, k in enumerate(ks):
        k = int(k)
        if rh[r] != rh[r] or k - n < 0:
            continue
        x = float(px[r])
        roll = 0
        if carry is not None:
            k0 = carry["k0"]
            seg_hi = float(top_[k0:k].max()) if k > k0 else -np.inf
            seg_lo = float(bot_[k0:k].min()) if k > k0 else np.inf
            if (carry["roll"] > 0 and (seg_hi >= carry["hi"] or seg_lo < carry["lo"])) or (carry["roll"] < 0 and (seg_lo <= carry["lo"] or seg_hi > carry["hi"])):
                carry = None                           # the array was traded (or the range broke the other way): the table's own range returns
            else:
                nl_, nh_, roll = carry["lo"], carry["hi"], carry["roll"]
                oh[r], ol[r] = (carry["old"] if roll > 0 else NAN), (carry["old"] if roll < 0 else NAN)
        if carry is None:
            a = k - n
            hh = (np.maximum(o, c)[a:k - 1].max() if bodies else h[a:k - 1].max()) if k - 1 > a else rh[r]
            ll = (np.minimum(o, c)[a:k - 1].min() if bodies else l[a:k - 1].min()) if k - 1 > a else rl[r]
            live = [x_ for x_ in bk.arrs if x_.tf in ("D", "W") and x_.typ in ("fvg", "ob", "vi") and x_.known <= k and bk.alive(x_, k)]
            top_last = max(o[k - 1], c[k - 1]) if bodies else h[k - 1]
            bot_last = min(o[k - 1], c[k - 1]) if bodies else l[k - 1]
            prem = [x_.bottom for x_ in live if x_.kind == "bear" and x_.bottom > max(x, hh, top_last)]       # beyond the broken high and the price; an array the last session already entered is traded, not ahead
            disc = [x_.top for x_ in live if x_.kind == "bull" and x_.top < min(x, ll, bot_last)]
            lo2, hi2, roll = rollover_range(ll, hh, hh, ll, x, top_last, bot_last, prem, disc)
            if roll > 0:
                nl_, nh_ = ll, hi2
                carry = dict(roll=1, hi=float(hi2), lo=float(ll), old=float(hh), k0=k)
            elif roll < 0:
                nl_, nh_ = lo2, hh
                carry = dict(roll=-1, hi=float(hh), lo=float(lo2), old=float(ll), k0=k)
            else:
                continue
            oh[r], ol[r] = (hh if roll > 0 else NAN), (ll if roll < 0 else NAN)
        rr[r] = roll
        rh[r], rl[r] = nh_, nl_
        s_, p_ = pd_state(x, float(nh_), float(nl_), zone, tuple(ote))
        st[r], ps[r] = s_, p_
        hit("range_rollover")
    out["pd20_hi"], out["pd20_lo"], out["pd20"], out["pd20_pos"] = rh, rl, st, ps
    out["pd20_old_hi"], out["pd20_old_lo"], out["pd20_roll"] = oh, ol, rr
    if repl and "react" in out:
        out["pd"] = st
        out["combo"] = [int(r_) if r_ else int(p_) for r_, p_ in zip(out.react, out.pd)]
    sw("range_rollover")
    return out


# --------------------------------------------------------------------------------------------------------------
# the table hook
# --------------------------------------------------------------------------------------------------------------

def finish5(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, df=None) -> pd.DataFrame:
    """Add the b5 columns named in `cfg` to the table `out` (one row per trading day)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    px = out.px.values.astype(float)
    bk = BH4.Book(d, w, arrs, es_pt, cfg)
    if "iff" in cfg:
        for k_, v_ in iof_follow_columns(h, l, c, ks, int(cfg["iff"])).items():
            out[k_] = v_
        out = apply_iof_follow(out)
    if "mctrl" in cfg:
        out["m_ctrl"] = monthly_ctrl_column(d, ks)
        sw("monthly_ctrl")
    if "nfill" in cfg:
        for k_, v_ in nwog_fill_columns(d, df, ks, float(cfg["nfill"])).items():
            out[k_] = v_
        sw("nwog_fill_rule")
    if "dce" in cfg:
        for k_, v_ in dce_columns(o, h, l, c, ks).items():
            out[k_] = v_
        sw("dce_proj_study")
    if "stack" in cfg:
        for k_, v_ in stack_columns(bk, ks, px, int(cfg["stack"])).items():
            out[k_] = v_
        sw("stack_draw")
    if "bprog" in cfg:
        for k_, v_ in program_columns(bk, ks).items():
            out[k_] = v_
        sw("program_gate")
    if "sorg" in cfg:
        for k_, v_ in shift_origin_columns(h, l, c, ks).items():
            out[k_] = v_
        sw("shift_origin_pool")
    if "fw" in cfg:
        for k_, v_ in fast_week_columns(bk, ks, px, float(cfg["fw"]), df).items():
            out[k_] = v_
        sw("fast_week_rev")
    if "eqb" in cfg:
        n_, brk_ = cfg["eqb"]
        for k_, v_ in eqb_columns(bk, ks, px, int(n_), brk_).items():
            out[k_] = v_
        sw("eq_breakout_draw")
    if "ddraw" in cfg:
        for k_, v_ in d_draw_columns(out, ks, h, l).items():
            out[k_] = v_
        sw("d_draw_carry")
    if "runarr" in cfg:
        out["run_arr"] = run_into_array_column(bk, ks, int(cfg["runarr"]))
        sw("pdh_raid_rev")
    if "ssl" in cfg:
        for k_, v_ in wk_ssl_columns(bk, df, ks).items():
            out[k_] = v_
        sw("wk_ssl_draw")
    if "two" in cfg:
        for k_, v_ in two_draw_columns(bk, ks, df).items():
            out[k_] = v_
        sw("wk_two_draw")
    if "b7sf" in cfg:
        from . import bh1 as BH1
        g = BH1.b7_columns(ks, d, arrs, "mt_close")
        out["b7sf_guard"], out["b7sf_guard_sh"] = g["ob_guard"], g["ob_guard_sh"]
        sw("b7_spike_floor")
    if "sea" in cfg:
        for k_, v_ in sea_columns(bk, ks, px).items():
            out[k_] = v_
    if "roll" in cfg and cfg.get("_pd20"):
        out = rollover_columns(out, bk, ks, px, cfg["_pd20"])
    if "wref" in cfg:
        out = ref_friday_freeze(out)
    return out


# --------------------------------------------------------------------------------------------------------------
# the reports and screens (study.py wraps them)
# --------------------------------------------------------------------------------------------------------------

def dce_proj_hits(table: pd.DataFrame, d: pd.DataFrame, within: int = 10) -> pd.DataFrame:
    """L13-old-high-to-daily-ce-projection (019 ~2:35), research: for each projection level (0 = the A-B midpoint, 1 = B, 2..5 = B + k(B-A), k = .25 ... 1.0) of the table's dce_proj (upward) and dce_proj_dn
    columns, how often a session within the next `within` sessions traded to it. `d` = the daily book (htf.sessions). Columns: level, n, hits, rate."""
    rows = {k: [0, 0] for k in range(6)}
    pos = {pd.Timestamp(t).date(): k for k, t in enumerate(d.index)}
    h, l = d.high.values.astype(float), d.low.values.astype(float)
    for col, up in (("dce_proj", True), ("dce_proj_dn", False)):
        if col not in table:
            continue
        for day_, lv in zip(table.index, table[col]):
            k = pos.get(pd.Timestamp(day_).date())
            if k is None or not lv:
                continue
            seg_h, seg_l = h[k:k + within], l[k:k + within]
            if len(seg_h) < within:
                continue
            for j, x in enumerate(lv):
                rows[j][0] += 1
                rows[j][1] += int((seg_h.max() >= x) if up else (seg_l.min() <= x))
    return pd.DataFrame([dict(level=j, n=n, hits=hh, rate=(hh / n if n else NAN)) for j, (n, hh) in rows.items()])


def stock_lrlr(weekly: pd.DataFrame, max_pct: float = 0.10, ext_atr: float = 2.0, atr_n: int = 14) -> dict:
    """LLT3-stock-low-resistance-distance (cc10_016 ~12:49: 'you're going to see some lethargic price action'): the weekly-chart screen of a stock candidate (`weekly` = open / high / low / close of weekly
    bars, e.g. the Alpaca daily data aggregated). Pass = (a) a CLEAN old high (the lowest still-untaken 2-bar weekly pivot high above the last close) lies within `max_pct` of the price, (b) the last close has not
    already blown through the latest intermediate-term high of levels.swing_tiers (weak structure) and (c) the price is not extended - more than `ext_atr` weekly ATRs above the last weekly pivot low
    [our interpretation]. Returns dict(passed, old_high, dist_pct, broken_mid, extension, reason)."""
    o, h, l, c = (weekly[k].values.astype(float) for k in ("open", "high", "low", "close"))
    px = float(c[-1])
    ph, pl = L.pivots(h, l, 2)
    olds = [q.price for q in ph if q.price > px and h[q.i + 1:].max(initial=-np.inf) < q.price]
    old = float(min(olds)) if olds else NAN
    dist = (old - px) / px if old == old else NAN
    ith = L.swing_tiers(h, l, 1)["itl"][0]
    broken = bool(ith and px > ith[-1].price)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr = float(tr[-atr_n:].mean()) if len(tr) else NAN
    low_p = float(pl[-1].price) if pl else float(l.min())
    ext = (px - low_p) / atr if atr and atr == atr else NAN
    reason = ""
    if not dist == dist:
        reason = "no_old_high"
    elif dist > max_pct:
        reason = "old_high_far"
    elif broken:
        reason = "broke_intermediate_high"
    elif ext == ext and ext > ext_atr:
        reason = "extended"
    return dict(passed=reason == "", old_high=old, dist_pct=dist, broken_mid=broken, extension=ext, reason=reason)


def weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Weekly bars (open / high / low / close, W-FRI) from a daily frame (e.g. the Alpaca daily bars): the aggregator stock_lrlr needs."""
    return daily.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def stock_lrlr_symbol(symbol: str, start: str, end: str | None = None, max_pct: float = 0.10, ext_atr: float = 2.0, daily: pd.DataFrame | None = None) -> dict:
    """`stock_lrlr` for a symbol: the Alpaca daily bars (`daily` when given, else alpaca_data.bars(symbol, 1440, start, end)) aggregated to weekly bars (review fix, 176)."""
    if daily is None:
        from . import alpaca_data
        daily = alpaca_data.bars(symbol, 1440, start, end)
    return stock_lrlr(weekly_from_daily(daily), max_pct, ext_atr)


def seasonal_entry_report(table: pd.DataFrame, seasonal_map=None, ahead: int = 20) -> pd.DataFrame:
    """B23-seasonal-entry-arrays (cc05_011 ~24:21), report only: the first table row of every month whose seasonal reading (`seasonal_map`, January first) is 'bull' after a month that was not = a bullish window
    start (`seasonal_map` None = Params.seasonal_map, the map daycontext.seasonal / seasonal_tag reads; a Params object is taken for its seasonal_map); whether the price sits inside a weekly bullish OB (`in_w_ob`) or above a broken weekly pivot high (`above_broken_high`), and the return of the next `ahead` rows (px to px)."""
    if seasonal_map is None:
        from .strategy import Params
        seasonal_map = Params().seasonal_map
    elif hasattr(seasonal_map, "seasonal_map"):
        seasonal_map = seasonal_map.seasonal_map
    rows = []
    idx = [pd.Timestamp(x) for x in table.index]
    px = table.px.values.astype(float)
    for r, t in enumerate(idx):
        if r > 0 and idx[r - 1].month == t.month:
            continue
        if seasonal_map[t.month - 1] != "bull" or seasonal_map[(t.month - 2) % 12] == "bull":
            continue
        ret = (px[r + ahead] / px[r] - 1.0) if r + ahead < len(px) and px[r] else NAN
        rows.append(dict(date=t, in_w_ob=bool(table.sea_w_ob.values[r] > 0) if "sea_w_ob" in table else False,
                         above_broken_high=bool(table.sea_w_brk.values[r] > 0) if "sea_w_brk" in table else False, ret_next=ret))
    return pd.DataFrame(rows, columns=["date", "in_w_ob", "above_broken_high", "ret_next"])
