"""Caption-gap pass, package bias_htf#4/7 (digests/rulebook_gaps/day_selection_news_calendar.md items 46, 51, 74, 75 and definitions_pd_arrays_structure.md items 27, 28, 29, 61, 80, 110, 113,
119, 139, 143, 145, 147, 148, 150, 160, 162, 168-170, 172, 173, 177-185) - TABLE SIDE.

The daily / weekly / monthly columns and the table-time array rules these switches need. Everything here is a pure function of COMPLETED sessions (the sessions before the row's day) and of the arrays
`htf.table` built (`Arr.known` = the first session index at which an array may be used): the row of session k never reads session k's high / low / close nor an incomplete week or month. The
engine side (side gates, per-order rules, tags, adds, the neutral-bias fallbacks) is `bh4e.py`. `bx_cfg(p)` is the JSON-able configuration `bias_htf.bx_string` stores under the key "b4"; `finish4`
runs at the end of `htf.table` (after bh3.finish3); `table_cfg` returns what the table's day loop itself reads (age tiers, the reach tolerance, the weekly / monthly array life, the origin OB, the
broken-OB mitigation arrays, the OB-to-MT life, the event-wick-free pivots). Thresholds the sources never give are marked [our interpretation]; every rule is a Params switch (off by default).

Columns (row of session k = the state after the completed session k-1)
  rng_day                         (46)        1 on a range-bound day: the last `range_day_n` daily closes sit inside the high-low of the session `range_day_n` + 1 back and the table draw is 0
  ipda60_hi / ipda60_lo / ipda_pos (51)       the 60-session high / low and the prior close's position in it (0..1)
  chk_q / chk_react_up / chk_react_dn / chk_path_up / chk_path_dn   (74)   the quarter's side (q_dir, else the price against the quarter open), a daily react within 3 sessions, the number of live
                                              opposing daily arrays between price and the draw
  dz_dir / dz_lo / dz_hi / dz_ce  (27, 28)    the daily FVG the price is inside (+1 a BISI, -1 a SIBI; the newest one) and its edges / CE
  cel_kind / cel_ce / cel_top / cel_bot (61)  the recent daily FVG whose CE price traded through and into which it came back (+1 a bullish gap traded below its CE, -1 a bearish one traded above)
  ifvg_bias / ifvg_top / ifvg_bot (80)        the side of the latest HTF inversion (a close beyond an FVG's far side) kept `ifvg_bias_days` sessions, and the inverted gap's edges
  trapped_bpr                     (119)       +1 / -1: the latest 15m balanced price range of a fast down-up (up-down) pair, not closed through
  program                         (160)       +1 / -1: `program_days` consecutive up (down) closes with higher highs (lower lows)
  mx_<W|M>_lo / _hi / _eq / _prem / _disc   (162)   the weekly / monthly dealing range (the latest confirmed swing high and low), its EQ and the live arrays of that timeframe split at it
  m_rng_dir / m_rng_lo / m_rng_hi (147)       the monthly D -> U dealing range
  m_flow                          (148)       the side most recently activated on the monthly bars
  obl / obl_dir                   (150)       the stepping order-block ladder (active level first)
  htf_rng_lo / htf_rng_hi / htf_rng_dir / htf_rng_eq   (168)  the weekly / monthly dealing range anchored at the origin order block
  eq_invalid                      (183)       1 when the last completed weekly close is beyond the EQ of htf_rng against its direction
  grid_lo / grid_hi / grid_pos / grid_k / grid_q / grid_half   (177, 180)   the 60-session body range (poke tolerant with pd_range_break) and the prior price's place in its eighths
  failed_break / fb_target        (181)       -1 / +1: a run beyond the consolidation's extreme, back inside and through the midpoint; the lowest (highest) body of the range
  nested_bias                     (182)       +1 / -1: the daily swing range's discount (premium) array held inside the 60-session range's premium (discount)
  brk_regime                      (185)       +1 / -1: the side of the most recent daily breaker
  (bias_cadence 'weekly' / 'weekly_midweek' freezes the weekly-timeframe columns (item 75))
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import bh2 as BH2
from . import bh3 as BH3

HITS = BH2.HITS
NAN = float("nan")
sw = BH2.sw


def hit(k: str) -> None:
    HITS[k] += 1


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_cfg(p) -> dict:
    """The "b4" part of Params.bx: only what the switches in use need ({} = nothing)."""
    c: dict = {}
    if p.range_day_mode != "off":
        c["rd"] = int(p.range_day_n)
    if p.ipda_mid_skip:
        c["mid"] = 1
    if p.htf_checklist:
        c["chk"] = 1
    if p.bias_cadence != "daily":
        c["cad"] = 2 if p.bias_cadence == "weekly_midweek" else 1
    if p.dbisi_lower_half or p.dbisi_upper_and_discount:
        c["dz"] = 1
    if p.array_age_tiers:
        c["tiers"] = 1
    if p.ce_line_bias:
        c["cel"] = 1
    if p.ifvg_bias or p.ifvg_edge_add:
        c["ifb"] = int(p.ifvg_bias_days)
    if p.htf_lifetime_wm >= 0 or p.htf_history_months > 0:
        c["wm"] = life_wm(p)
        if p.htf_lifetime_wm < 0:
            c["hm"] = 1                                   # the life comes from htf_history_months
    if p.trapped_bpr_bias:
        c["trap"] = int(p.bpr_max_gap_bars) or 8
    if p.event_wick_ignore:
        c["ew"] = float(p.event_wick_mult)
    if p.htf_ob_mitigation:
        c["mit"] = 1
    if p.origin_ob:
        c["oob"] = 1
    if p.monthly_range:
        c["mr"] = 1
    if p.monthly_flow_gate:
        c["mf"] = 1
    if p.ob_ladder:
        c["lad"] = [float(p.ob_disp_mult), 1 if p.ob_ladder_px == "high" else 0]
    if p.program_tag:
        c["prog"] = int(p.program_days)
    mx = [t for t in p.matrix_tfs if t in ("W", "M")]
    if mx:
        c["mx"] = mx
    if p.htf_range_arrays or p.swing_extreme_block or p.swing_ignore_eq or p.htf_eq_invalid:
        c["rng"] = 1
    if p.htf_eq_invalid:
        c["eqi"] = 1
    if p.htf_ob_to_mt:
        c["tomt"] = 1
    if p.htf_reach_tol_pts > 0:
        c["tol"] = float(p.htf_reach_tol_pts) * float(p.es_pt)
    if p.pd_grid or p.grade_confluence or p.pd_need_array or p.nested_pd_bias or p.pd_range_break != "off":
        c["grid"] = [int(p.pd_grid_days), 1 if p.pd_range_break == "two_close" else 0]
    if p.failed_consol_break:
        c["fb"] = int(p.pd_day_range)
        c["fbt"] = list(p.failed_consol_tfs)
    if p.nested_pd_bias:
        c["nest"] = 1
    if p.breaker_regime:
        c["brk"] = 1
    return c


def life_wm(p) -> int:
    """The life of the weekly / monthly arrays in sessions: htf_lifetime_wm (0 = no cap, N = sessions) when set, else htf_history_months x 21 [our interpretation: a month is 21 sessions]."""
    if p.htf_lifetime_wm >= 0:
        return int(p.htf_lifetime_wm)
    return int(p.htf_history_months) * 21 if p.htf_history_months > 0 else 0


def table_cfg(X: dict) -> dict:
    """The table-time part of the "b4" block (what the day loop reads), with defaults."""
    b = (X or {}).get("b4") or {}
    return {"tiers": bool(b.get("tiers")), "tol": float(b.get("tol", 0.0)), "wm": b.get("wm"), "oob": bool(b.get("oob")), "mit": bool(b.get("mit")), "tomt": bool(b.get("tomt")),
            "ew": b.get("ew"), "hm": bool(b.get("hm"))}


# --------------------------------------------------------------------------------------------------------------
# table-time helpers
# --------------------------------------------------------------------------------------------------------------

def event_wick_adjust(o, h, l, c, mult: float = 2.0, n: int = 20):
    """A4-event-wick-ignore (cc05_007 ~4:42: "without that Wick we have lower high"): the daily highs / lows with the wick of an extraordinary one-off candle replaced by its body extreme. [our interpretation]
    a wick (the part of the range beyond the body) longer than `mult` x the mean range of the `n` sessions before it (at least 5 are needed) is the event wick; a known event date list is not kept."""
    o, h, l, c = (np.asarray(x, float) for x in (o, h, l, c))
    h2, l2 = h.copy(), l.copy()
    rng = h - l
    for j in range(5, len(c)):
        avg = float(rng[max(0, j - n):j].mean())
        if avg <= 0:
            continue
        if h[j] - max(o[j], c[j]) > mult * avg:
            h2[j] = max(o[j], c[j])
        if min(o[j], c[j]) - l[j] > mult * avg:
            l2[j] = min(o[j], c[j])
    return h2, l2


def tier_of(age: int) -> int:
    """A5-pd-array-lookback-priority (015 ~4:35; cc07_004 ~3:50): W20 = tier 1 (age <= 20 sessions), W40 = tier 2, W60 = tier 3, older = 4 (ignored)."""
    return 1 if age <= 20 else 2 if age <= 40 else 3 if age <= 60 else 4


def tier_filter(draws, ages):
    """The draws (distance, name, level) of one side restricted to the lowest age tier that has any (W20 first, then W40, then W60). `ages` is parallel to `draws`; None = no age (kept in the lowest
    tier found)."""
    if not draws:
        return draws
    ts = []
    for x, a in zip(draws, ages):
        ts.append(1 if a is None else tier_of(int(a)))
    ok = [t for t in ts if t < 4]
    if not ok:
        return draws
    m = min(ok)
    if m == 1 and all(t == 1 for t in ts):
        return draws
    sw("array_age_tiers")
    return [x for x, t in zip(draws, ts) if t == m]


def body_origin(o, h, l, c, z_i: int, kind: str, window: int = 4):
    """A12-sponsorship-origin-ob (cc03_003 ~12:43): the BODY zone (open to close, the wick ignored) of the last opposite-close candle at the origin of a displacement that left a gap whose third candle is
    `z_i` - for a bullish gap the last down-close candle among the bars z_i-4 .. z_i-2 (bearish: up-close). Returns (top, bottom, mt, j) or None. The displacement candle (z_i-1) must close beyond the body's far
    side (like the standard order block)."""
    a, b = max(0, z_i - window), z_i - 2
    for j in range(b, a - 1, -1):
        if kind == "bull" and c[j] < o[j]:
            top, bot = float(o[j]), float(c[j])
            return (top, bot, (top + bot) / 2, j) if c[z_i - 1] > top else None
        if kind == "bear" and c[j] > o[j]:
            top, bot = float(c[j]), float(o[j])
            return (top, bot, (top + bot) / 2, j) if c[z_i - 1] < bot else None
    return None


def origin_arrays(o, h, l, c, tf: str, known_of, existing=()) -> list:
    """The body-zone origin order blocks (typ "ob", `Arr.origin` True, `Arr.src_i` = the origin candle) of the gaps of one timeframe, without the ones an existing block of the same zone already covers."""
    from .htf import Arr
    out = []
    seen = {(round(a.top, 6), round(a.bottom, 6), a.kind) for a in existing if a.typ == "ob" and a.tf == tf}
    for z in L.fvgs(h, l, o, c):
        r = body_origin(o, h, l, c, z.i, z.kind)
        if r is None:
            continue
        top, bot, mt, j = r
        key = (round(top, 6), round(bot, 6), z.kind)
        if key in seen:
            continue
        seen.add(key)
        a = Arr(z.kind, "ob", tf, top, bot, mt, known_of(z.i))
        a.origin = True
        a.src_i = j
        out.append(a)
    return out


def mitigation_arrays(arrs, d_close, ndays: int) -> list:
    """A15-htf-ob-as-mitigation (cc03_002 ~25:51): a weekly / monthly order block broken by a daily body close beyond its far side (below the low of a bullish one; [our interpretation] broken = a body close)
    acts afterwards as a daily mitigation block of the opposite side (resistance for a broken bullish block): an `ob` array of tf "D", usable from the session after the break. The usual order-block death
    (a close beyond its MT) applies to it."""
    from .htf import Arr
    out = []
    for a in arrs:
        if a.tf not in ("W", "M") or a.typ != "ob":
            continue
        for j in range(a.known, ndays):
            cl = d_close[j]
            if (a.kind == "bull" and cl < a.bottom) or (a.kind == "bear" and cl > a.top):
                if j + 1 < ndays:
                    m = Arr("bear" if a.kind == "bull" else "bull", "ob", "D", a.top, a.bottom, a.ce, j + 1)
                    m.mit = True
                    out.append(m)
                break
    return out


# --------------------------------------------------------------------------------------------------------------
# the book: daily / weekly arrays and the liveness test shared by the columns
# --------------------------------------------------------------------------------------------------------------

class Book:
    """The completed-bar views `finish4` shares: the daily book, the weekly book, the arrays and `alive(a, k)` = htf._arr_alive for the table's defaults."""

    def __init__(self, d, w, arrs, es_pt, cfg):
        self.d, self.w, self.arrs, self.es_pt, self.cfg = d, w, arrs, es_pt, cfg
        self.o, self.h, self.l, self.c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
        pos = {t: k for k, t in enumerate(d.index)}
        self.wl = [pos[t] + 1 for t in w["last"]]
        self.wo, self.wc = w.open.values.astype(float), w.close.values.astype(float)
        self.wh, self.wlow = w.high.values.astype(float), w.low.values.astype(float)
        self.arrs_all = list(arrs) + [a for a in BH3.month_arrays(d, arrs) if a not in arrs]       # + the monthly arrays when the table did not build them

    def alive(self, a, k: int, ol: float = 0.0, oh: float = 0.0, vi_body_death: bool = False) -> bool:
        from .htf import _arr_alive
        return _arr_alive(a, k, self.o, self.h, self.l, self.c, self.wo, self.wc, self.wl, vi_body_death, "full_span", bal="own")


def _live_daily(bk: Book, k: int, lookback: int = 60, typs=("fvg", "ob", "vi")) -> list:
    return [a for a in bk.arrs if a.tf == "D" and a.typ in typs and k - lookback <= a.known - 1 and a.known <= k and bk.alive(a, k)]


# --------------------------------------------------------------------------------------------------------------
# items 46 / 51: the range day and the 60-session middle
# --------------------------------------------------------------------------------------------------------------

def range_day_column(h, l, c, ks, n: int) -> np.ndarray:
    """B17-range-day-sit-out-am (031 ~9:20, 032 ~28:53): 1 when the last `n` daily closes (sessions k-n .. k-1) sit inside the high-low of the session n + 1 back (k-n-1) [our interpretation of 'the ES daily
    is inside a multi-day range']."""
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        if k - n - 1 < 0:
            continue
        hi, lo = h[k - n - 1], l[k - n - 1]
        seg = c[k - n:k]
        out[r] = int(len(seg) == n and bool((seg <= hi).all() and (seg >= lo).all()))
    return out


def ipda_pos_columns(h, l, c, ks, n: int = 60) -> dict:
    """N8-middle-of-range (cc07_005 ~00:23:47): the 60-session high / low (sessions k-60 .. k-1) and the prior close's position in it."""
    hi, lo, pos = (np.full(len(ks), NAN) for _ in range(3))
    for r, k in enumerate(ks):
        if k < n:
            continue
        hi[r], lo[r] = h[k - n:k].max(), l[k - n:k].min()
        if hi[r] > lo[r]:
            pos[r] = (c[k - 1] - lo[r]) / (hi[r] - lo[r])
    return {"ipda60_hi": hi, "ipda60_lo": lo, "ipda_pos": pos}


# --------------------------------------------------------------------------------------------------------------
# item 74: the buy-day checklist
# --------------------------------------------------------------------------------------------------------------

def quarter_open_sign(d, o, ks, px) -> np.ndarray:
    """DS2-buy-day-checklist (a): the sign of (price - the open of the quarter's first session) [our interpretation of the quarter's expectation]."""
    q = d.index.to_period("Q")
    first = {}
    for k, p_ in enumerate(q):
        first.setdefault(p_, k)
    return np.array([int(np.sign(px[r] - o[first[q[k]]])) for r, k in enumerate(ks)])


def checklist_columns(bk: Book, out, ks, px) -> dict:
    """DS2-buy-day-checklist (cc08_007 ~00:06:40): chk_q (the quarter side: q_dir when the table has it and it is non-zero, else the price against the quarter open), chk_react_up / _dn (a react of that
    side within the last 3 table rows), chk_path_up / _dn (the number of live opposing daily arrays - bearish for the way up - whose near edge lies between price and the table's draw level)."""
    R = len(ks)
    q = quarter_open_sign(bk.d, bk.o, ks, px)
    if "q_dir" in out:
        qd = out.q_dir.values.astype(int)
        q = np.where(qd != 0, qd, q)
    react = out.react.values.astype(int)
    ru = np.array([int((react[max(0, r - 2):r + 1] == 1).any()) for r in range(R)])
    rd = np.array([int((react[max(0, r - 2):r + 1] == -1).any()) for r in range(R)])
    pu, pdn = np.zeros(R, int), np.zeros(R, int)
    du, dd = out.draw_up.values.astype(float), out.draw_dn.values.astype(float)
    for r, k in enumerate(ks):
        live = _live_daily(bk, int(k))
        if du[r] == du[r]:
            pu[r] = sum(1 for a in live if a.kind == "bear" and px[r] < a.bottom < du[r])
        if dd[r] == dd[r]:
            pdn[r] = sum(1 for a in live if a.kind == "bull" and dd[r] < a.top < px[r])
    return {"chk_q": q, "chk_react_up": ru, "chk_react_dn": rd, "chk_path_up": pu, "chk_path_dn": pdn}


# --------------------------------------------------------------------------------------------------------------
# item 75: the weekly cadence
# --------------------------------------------------------------------------------------------------------------

FROZEN = ("wk_bias", "wk_draw_up", "wk_draw_dn", "wk_draw_up_n", "wk_draw_dn_n", "bias_w", "bias_m", "mo_bias", "wk_pre_bias", "wk_control", "react_wk", "q_dir", "q_obj_dir", "wk_chk_tail", "wk_consol",
          "mo_pd", "wk_pd", "wk_expand", "htf_rng_lo", "htf_rng_hi", "htf_rng_dir", "htf_rng_eq", "eq_invalid", "m_rng_dir", "m_rng_lo", "m_rng_hi", "m_flow", "mx_W_lo", "mx_W_hi", "mx_W_eq", "mx_W_prem",
          "mx_W_disc", "mx_M_lo", "mx_M_hi", "mx_M_eq", "mx_M_prem", "mx_M_disc",
          # review fix (item 75): every other weekly / monthly-derived column of the table (the B10 weekly-first bias and its parts, the weekly direction / PO3 / q75 / IOF)
          "mwd", "mwd_m", "mwd_w", "mwd_case", "mwd_zones", "mwd_levels", "wk_dir", "wk_po3", "wk_po3_draw", "wk_q75", "wk_q75_confirm", "iof_w", "wo_sun", "wo_mon", "wo_expired", "wpr", "obj_week",
          "wk_bisi", "wk_dc", "wk_rb", "wk_high_in", "wk_high_in_trim", "wk_low_in", "wk_struct_agree", "wk_struct_disagree", "wk_struct_weight", "mo_aligned", "mo_unaligned", "mo_bias_block", "mo_bias_gate")


def cadence_freeze(out: pd.DataFrame, mode: int) -> pd.DataFrame:
    """new-perspective-cadence (cc02_006 ~00:48:38: "the big picture perspective you usually have that at the beginning of the week"): the weekly-timeframe columns of every table row of a week hold the
    values of the week's FIRST row (the Monday open). Mode 2 ('weekly_midweek'): one refresh at the first row of Wednesday or later when the daily `flip` column changed since the week's first row. The daily
    columns are recomputed daily as before."""
    cols = [c_ for c_ in FROZEN if c_ in out.columns]
    if not cols or not len(out):
        return out
    idx = [pd.Timestamp(x) for x in out.index]
    wk = [x.to_period("W-FRI") for x in idx]
    flip = out.flip.values if "flip" in out else np.zeros(len(out), int)
    vals = {c_: list(out[c_].values) for c_ in cols}
    r0 = 0
    sw("bias_cadence")
    for r in range(len(out)):
        if r == 0 or wk[r] != wk[r - 1]:
            r0, rw = r, None
        src = r0
        if mode == 2:
            # review fix: the one refresh is at the FIRST row of Wednesday (not a later day), NaN-safe comparison
            fl_r, fl_0 = flip[r], flip[r0]
            changed = (fl_r != fl_0) and not (fl_r != fl_r and fl_0 != fl_0)
            if rw is None and idx[r].weekday() == 2 and wk[r] == wk[r0] and r > r0 and changed:
                rw = r
                hit("cadence_refresh")
            if rw is not None:
                src = rw
        for c_ in cols:
            vals[c_][r] = vals[c_][src]
    for c_ in cols:
        out[c_] = vals[c_]
    return out


# --------------------------------------------------------------------------------------------------------------
# items 27 / 28 / 61 / 80: the daily FVG Z, the CE line, the inversion bias
# --------------------------------------------------------------------------------------------------------------

def dz_columns(bk: Book, ks, px) -> dict:
    """A5-ltf-fvgs-inside-daily-bisi (012 ~19:16) / A21-htf-fvg-upper-half-and-discount (012 ~18:29): the daily FVG Z the price is inside - the NEWEST live one (dz_dir +1 a BISI, -1 a SIBI) with its edges
    and CE."""
    R = len(ks)
    dz = np.zeros(R, int)
    lo, hi, ce = (np.full(R, NAN) for _ in range(3))
    for r, k in enumerate(ks):
        best = None
        for a in _live_daily(bk, int(k), typs=("fvg",)):
            if a.bottom <= px[r] <= a.top and (best is None or a.known >= best.known):
                best = a
        if best is not None:
            dz[r] = 1 if best.kind == "bull" else -1
            lo[r], hi[r], ce[r] = best.bottom, best.top, best.ce
    return {"dz_dir": dz, "dz_lo": lo, "dz_hi": hi, "dz_ce": ce}


def cel_columns(bk: Book, ks, px, on_h, on_l, recent: int = 3) -> dict:
    """A8-ce-line-bearish-read (030 ~1:38:43: "as long as we remain below"): the most recent daily FVG (formed within `recent` sessions, still open) whose CE the market traded through after the gap formed
    (a bullish gap: a low under its CE in the sessions since or tonight; a bearish gap: a high over it) and whose price is back at or inside the gap (bullish: price at or under its top). [our
    interpretation] the 'speed' of the move through the CE is not measured."""
    R = len(ks)
    kind = np.zeros(R, int)
    ce, top, bot = (np.full(R, NAN) for _ in range(3))
    for r, k in enumerate(ks):
        k = int(k)
        best = None
        for a in _live_daily(bk, k, typs=("fvg",)):
            if k - a.known > recent:
                continue
            if a.kind == "bull":
                seen = np.nanmin([bk.l[a.known:k].min() if a.known < k else np.inf, on_l[r] if on_l[r] == on_l[r] else np.inf])
                ok = seen < a.ce and px[r] <= a.top
            else:
                seen = np.nanmax([bk.h[a.known:k].max() if a.known < k else -np.inf, on_h[r] if on_h[r] == on_h[r] else -np.inf])
                ok = seen > a.ce and px[r] >= a.bottom
            if ok and (best is None or a.known >= best.known):
                best = a
        if best is not None:
            kind[r] = 1 if best.kind == "bull" else -1
            ce[r], top[r], bot[r] = best.ce, best.top, best.bottom
    return {"cel_kind": kind, "cel_ce": ce, "cel_top": top, "cel_bot": bot}


def ifvg_columns(bk: Book, ks, days: int) -> dict:
    """A8-ifvg-bias-without-retest (072 ~9:18: "it doesn't need to come back down and touch it again"): once a daily candle closes beyond the far side of an FVG (below a bullish gap's bottom, above a bearish
    gap's top; a weekly gap by a completed weekly close) it is an IFVG for bias at once: ifvg_bias = -1 for the former bullish gap, +1 for the former bearish one, from the next session, the latest inversion wins,
    kept `days` sessions and ended by a close back through the inverted gap's other side (above a bullish gap's top)."""
    R = len(ks)
    bias = np.zeros(R, int)
    top, bot = np.full(R, NAN), np.full(R, NAN)
    ev = []                                              # (session of the closing break, side, top, bottom, array)
    for a in bk.arrs:
        if a.typ != "fvg" or a.tf not in ("D", "W"):
            continue
        if a.tf == "D":
            for j in range(a.known, len(bk.c)):
                if (a.kind == "bull" and bk.c[j] < a.bottom) or (a.kind == "bear" and bk.c[j] > a.top):
                    ev.append((j, -1 if a.kind == "bull" else 1, a.top, a.bottom, a.kind))
                    break
        else:
            for q in range(len(bk.wl)):
                if bk.wl[q] > a.known and ((a.kind == "bull" and bk.wc[q] < a.bottom) or (a.kind == "bear" and bk.wc[q] > a.top)):
                    ev.append((bk.wl[q] - 1, -1 if a.kind == "bull" else 1, a.top, a.bottom, a.kind))
                    break
    ev.sort(key=lambda e: e[0])
    for r, k in enumerate(ks):
        k = int(k)
        cur = [e for e in ev if e[0] <= k - 1 and k - 1 - e[0] < days]
        if not cur:
            continue
        j, side, tp, bt, kind = cur[-1]
        later = bk.c[j + 1:k]
        if len(later) and ((kind == "bull" and later.max() > tp) or (kind == "bear" and later.min() < bt)):
            continue                                       # closed back through the inverted gap: the inversion is spent
        bias[r], top[r], bot[r] = side, tp, bt
    return {"ifvg_bias": bias, "ifvg_top": top, "ifvg_bot": bot}


# --------------------------------------------------------------------------------------------------------------
# item 119: the trapped-trader BPR on 15m
# --------------------------------------------------------------------------------------------------------------

def bpr_list(o, h, l, c, max_gap: int, large: float = 1.5, n_avg: int = 20) -> list:
    """A11-trapped-trader-bpr (104 ~26:09): (bar index known, kind, top, bottom) of the balanced price ranges (levels.balanced_ranges, max_gap_bars=`max_gap`) whose BOTH gaps come from a LARGE-range candle
    [our interpretation: a large range = at least `large` x the mean range of the 20 bars before it]."""
    rng = h - l

    def big(gi: int) -> bool:
        m = gi - 1
        if m < 5:
            return False
        return bool(rng[m] >= large * rng[max(0, m - n_avg):m].mean())
    return [(z.i, z.kind, z.top, z.bottom) for z in L.balanced_ranges(h, l, int(max_gap), o, c) if big(z.i) and big(z.src)]


def trapped_column(df, d, ks, cut_min: int, max_gap: int) -> np.ndarray:
    """The latest trapped-trader BPR (15m, completed by the table's cut) of the previous session or tonight, not closed through by a later 15m close: +1 for a bullish one (a down candle's SIBI, then an up
    candle's overlapping BISI: trapped shorts below, draws above), -1 for the mirror."""
    R = len(ks)
    res = np.zeros(R, int)
    if df is None or not len(df):
        return res
    g = df.groupby(df.index.floor("15min"))
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(), "n": g.close.size()})
    bm = max(1, int(np.diff(df.index.values[:50]).astype("timedelta64[m]").astype(int).min())) if len(df) > 2 else 1
    b = b[b.n >= 15 // bm]
    if len(b) < 20:
        return res
    t = b.index
    lab = pd.to_datetime((t + pd.Timedelta(hours=7)).date)
    tmin = t.hour * 60 + t.minute
    lpos = {x: q for q, x in enumerate(d.index)}
    sp = np.array([lpos.get(x, -1) for x in lab])
    o_, h_, l_, c_ = (b[k].values.astype(float) for k in ("open", "high", "low", "close"))
    bprs = bpr_list(o_, h_, l_, c_, max_gap)
    if not bprs:
        return res
    before = (tmin + 15 <= cut_min) | (tmin >= 17 * 60)        # bars completed by the cut on their own session date (the evening is the previous calendar day)
    spm = np.maximum.accumulate(sp)
    by_sess: dict = {}
    for (i, kd, tp, bt) in bprs:
        by_sess.setdefault(int(sp[i]), []).append((i, kd, tp, bt))
    for r, k in enumerate(ks):
        k = int(k)
        ok = [x for s_ in (k - 1, k) for x in by_sess.get(s_, []) if sp[x[0]] < k or before[x[0]]]
        if not ok:
            continue
        i, kd, tp, bt = max(ok, key=lambda x: x[0])
        end = int(np.searchsorted(spm, k, side="right"))
        later = [q for q in range(i + 1, end) if (sp[q] == k and before[q]) or sp[q] == k - 1]
        cl = c_[later] if later else np.array([])
        if len(cl) and ((kd == "bull" and cl.min() < bt) or (kd == "bear" and cl.max() > tp)):
            continue
        res[r] = 1 if kd == "bull" else -1
    return res


# --------------------------------------------------------------------------------------------------------------
# item 160: the program
# --------------------------------------------------------------------------------------------------------------

def program_column(o, h, l, c, ks, days: int) -> np.ndarray:
    """new-buy-program (cc05_001 ~9:01): +1 when the last `days` completed sessions all closed up with a higher high than the session before; -1 the mirror [our interpretation: >= 3 consecutive up closes with a
    higher high]."""
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        if k - days - 1 < 0:
            continue
        sl = slice(k - days, k)
        up = (c[sl] > o[sl]).all() and (h[k - days:k] > h[k - days - 1:k - 1]).all()
        dn = (c[sl] < o[sl]).all() and (l[k - days:k] < l[k - days - 1:k - 1]).all()
        out[r] = 1 if up else (-1 if dn else 0)
    return out


# --------------------------------------------------------------------------------------------------------------
# items 147 / 148 / 162: monthly and weekly books
# --------------------------------------------------------------------------------------------------------------

def monthly_range_at(o, h, l, c, m: int) -> tuple:
    """new-monthly-dealing-range (cc03_004 ~8:15): over the first `m` completed monthly bars, the (dir, lo, hi) of the dealing range. The last bar's colour picks the side: a down-close bar is the most recent
    down candle D (bullish): search left for the nearest up-close candle U with high[U] > high[D]; the range is low[D] .. high[U] [our interpretation of the edge prices]. An up-close last bar mirrors it
    (range high[U'] down to low[D'] of the nearest down-close candle with low[D'] < low[U']). (0, nan, nan) when there is none."""
    if m < 2:
        return 0, NAN, NAN
    j = m - 1
    if c[j] < o[j]:
        for q in range(j - 1, -1, -1):
            if c[q] > o[q] and h[q] > h[j]:
                return 1, float(l[j]), float(h[q])
    elif c[j] > o[j]:
        for q in range(j - 1, -1, -1):
            if c[q] < o[q] and l[q] < l[j]:
                return -1, float(l[q]), float(h[j])
    return 0, NAN, NAN


def monthly_flow_series(o, h, l, c) -> np.ndarray:
    """A12-bearish-activation (cc03_004 ~14:23): per monthly bar j the side most recently activated by bar j or before: bullish when a down-close candle's high was violated (a later high above it), bearish
    when an up-close candle's low was violated (a later low under it); each candle activates once, the later event wins, both at once: the violating bar's own colour decides. 0 before any."""
    n = len(c)
    flow = np.zeros(n, int)
    done = set()
    cur = 0
    for j in range(1, n):
        bull = [i for i in range(j) if i not in done and c[i] < o[i] and h[j] > h[i]]
        bear = [i for i in range(j) if i not in done and c[i] > o[i] and l[j] < l[i]]
        done.update(bull)
        done.update(bear)
        if bull and bear:
            cur = 1 if c[j] >= o[j] else -1
        elif bull:
            cur = 1
        elif bear:
            cur = -1
        flow[j] = cur
    return flow


def swing_range_at(h, l, m: int, n: int = 1) -> tuple:
    """The (lo, hi) of the latest confirmed swing low and swing high of the first `m` bars (3-bar pivots confirmed by a later bar), or (nan, nan)."""
    if m < 4:
        return NAN, NAN
    ph, pl = L.pivots(h[:m], l[:m], n)
    if not ph or not pl:
        return NAN, NAN
    return float(pl[-1].price), float(ph[-1].price)


def tf_arrays_alive(bk: Book, tf: str, m: int, bars) -> list:
    """The arrays of timeframe `tf` that no completed bar of that timeframe (the first `m` bars) closed through (FVG / VI: beyond the far side; OB: beyond the MT)."""
    o_, h_, l_, c_, last = bars
    out = []
    if m < 1:
        return out
    for a in bk.arrs_all:
        if a.tf != tf or a.typ not in ("fvg", "ob", "vi") or a.known > last[m - 1] + 1:
            continue
        cl = c_[[q for q in range(m) if last[q] >= a.known]]
        if a.kind == "bull":
            lvl = a.ce if a.typ == "ob" else a.bottom
            dead = len(cl) and cl.min() < lvl
        else:
            lvl = a.ce if a.typ == "ob" else a.top
            dead = len(cl) and cl.max() > lvl
        if not dead:
            out.append(a)
    return out


def matrix_columns(bk: Book, ks, tfs) -> dict:
    """A22-matrix-range-tf (cc05_014 ~6:31, ~17:49: "nothing below a daily chart"): the weekly / monthly dealing range (the latest confirmed swing low and high of that timeframe's completed bars), its EQ,
    and the live arrays of the timeframe split at the EQ - mx_<tf>_prem (the CEs above it, ascending) and mx_<tf>_disc (below, descending). Recomputed on every new swing (the range of the latest
    pivots) [our interpretation of 'recompute on a new range']."""
    cols = {}
    for tf in tfs:
        if tf == "W":
            bars = (bk.wo, bk.wh, bk.wlow, bk.wc, np.array(bk.wl) - 1)
        else:
            mo, mh, ml, mc, mlast = BH3.tf_bars(bk.d, "M")
            bars = (mo, mh, ml, mc, mlast)
        o_, h_, l_, c_, last = bars
        R = len(ks)
        lo, hi, eq = (np.full(R, NAN) for _ in range(3))
        prem, disc = [()] * R, [()] * R
        mm = np.searchsorted(last, np.asarray(ks) - 1, side="right")
        for r in range(R):
            m = int(mm[r])
            a_, b_ = swing_range_at(h_, l_, m)
            if a_ != a_ or b_ <= a_:
                continue
            lo[r], hi[r], eq[r] = a_, b_, (a_ + b_) / 2
            live = tf_arrays_alive(bk, tf, m, bars)
            prem[r] = tuple(sorted(x.ce for x in live if x.ce > eq[r]))
            disc[r] = tuple(sorted((x.ce for x in live if x.ce <= eq[r]), reverse=True))
        cols[f"mx_{tf}_lo"], cols[f"mx_{tf}_hi"], cols[f"mx_{tf}_eq"] = lo, hi, eq
        cols[f"mx_{tf}_prem"], cols[f"mx_{tf}_disc"] = prem, disc
    return cols


# --------------------------------------------------------------------------------------------------------------
# item 150: the stepping order-block ladder
# --------------------------------------------------------------------------------------------------------------

def ladder_at(o, h, l, c, k: int, direction: int, mult: float, px_high: int, span: int = 60) -> tuple:
    """A12-stepping-ob (cc04_003 ~28:30; cc05_003 ~1:06:00; cc06_004 ~18:06): from the HTF swing low (the lowest low of the last `span` sessions) the daily down-close candles followed by a higher high (and,
    when `mult` > 0, a run of at least mult x the candle's body above its open), each storing its entry level (its open; with px_high its high) and its MT; one whose MT a later close broke is dropped. The
    active block is the HIGHEST level, the older ones follow as fallbacks. Returns the levels, active first (descending for a long); () when there is none. direction -1 mirrors it (an up-close candle
    followed by a lower low from the swing high; the entry level is its open, or its low with px_high)."""
    a = max(0, k - span)
    if direction > 0:
        s = a + int(np.argmin(l[a:k]))
    else:
        s = a + int(np.argmax(h[a:k]))
    lv = []
    for j in range(s + 1 if direction > 0 else s + 1, k):
        body = abs(c[j] - o[j])
        if direction > 0 and c[j] < o[j]:
            if h[j + 1:k].size == 0 or h[j + 1:k].max() <= h[j]:
                continue
            if mult > 0 and h[j + 1:k].max() - o[j] < mult * body:
                continue
            mt = (o[j] + c[j]) / 2
            if c[j + 1:k].size and c[j + 1:k].min() < mt:
                continue
            lv.append(float(h[j] if px_high else o[j]))
        elif direction < 0 and c[j] > o[j]:
            if l[j + 1:k].size == 0 or l[j + 1:k].min() >= l[j]:
                continue
            if mult > 0 and o[j] - l[j + 1:k].min() < mult * body:
                continue
            mt = (o[j] + c[j]) / 2
            if c[j + 1:k].size and c[j + 1:k].max() > mt:
                continue
            lv.append(float(l[j] if px_high else o[j]))
    lv = sorted(set(lv), reverse=direction > 0)
    if direction < 0:
        lv = sorted(set(lv))
    return tuple(lv)


# --------------------------------------------------------------------------------------------------------------
# items 168 / 183: the HTF dealing range anchored at the arrays
# --------------------------------------------------------------------------------------------------------------

def htf_range_columns(bk: Book, ks, px) -> dict:
    """A21-htf-range-anchored-at-arrays (cc05_015 ~9:05; cc06_008 ~24:56): the weekly / monthly dealing range. Low (bullish): the BODY-based reference price of the newest live bullish point-of-origin block
    (the open of the last down-close candle before the displacement that left the gap - its body top, not the wick low); high: the nearest weekly / monthly bearish array (its near edge) or the next weekly
    swing high above the low. The bearish range mirrors it (high = the origin block's body bottom, low = the nearest bullish array's top or weekly swing low below it). The newest origin block of either side
    decides [our interpretation of 'the anchor array choice']. EQ = the midpoint."""
    R = len(ks)
    lo, hi, eq = (np.full(R, NAN) for _ in range(3))
    dr = np.zeros(R, int)
    w_o = [bk.wo, bk.wh, bk.wlow, bk.wc]
    origs = origin_arrays(*w_o, "W", lambda i: bk.wl[i])
    mo, mh, ml, mc, mlast = BH3.tf_bars(bk.d, "M")
    if len(mc) >= 3:
        origs += origin_arrays(mo, mh, ml, mc, "M", lambda i: int(mlast[i]) + 1)
    ph, pl = L.pivots(bk.wh, bk.wlow, 1)
    wbars = (bk.wo, bk.wh, bk.wlow, bk.wc, np.array(bk.wl) - 1)
    mbars = (mo, mh, ml, mc, mlast)
    mm_all = np.searchsorted(mlast, np.asarray(ks) - 1, side="right") if len(mc) else np.zeros(R, int)
    live_cache = {}

    def live_other(tf, m, bars):
        # review fix (item 168): the range anchors only on arrays no completed bar of their OWN timeframe closed through (tf_arrays_alive)
        if (tf, m) not in live_cache:
            live_cache[(tf, m)] = tf_arrays_alive(bk, tf, m, bars)
        return live_cache[(tf, m)]
    for r, k in enumerate(ks):
        k = int(k)
        cand = []
        for a in origs:
            if a.known > k:
                continue
            if a.tf == "W":
                cl = bk.wc[[q for q in range(len(bk.wl)) if a.known < bk.wl[q] <= k]]
            else:
                cl = mc[[q for q in range(len(mc)) if a.known < mlast[q] + 1 <= k]]
            lvl = a.ce
            if len(cl) and ((a.kind == "bull" and cl.min() < lvl) or (a.kind == "bear" and cl.max() > lvl)):
                continue
            cand.append(a)
        if not cand:
            continue
        a = max(cand, key=lambda x: x.known)
        done_w = [q for q in range(len(bk.wl)) if bk.wl[q] <= k]
        wm = len(done_w)
        htf_other = live_other("W", wm, wbars) + live_other("M", int(mm_all[r]), mbars)
        if a.kind == "bull":
            base = a.top
            ups = [x.bottom for x in htf_other if x.kind == "bear" and x.known <= k and x.bottom > base]
            ups += [p_.price for p_ in ph if p_.known < wm and p_.price > base and not (wm > p_.i + 1 and bk.wh[p_.i + 1:wm].max() >= p_.price)]
            if not ups:
                continue
            lo[r], hi[r], dr[r] = base, min(ups), 1
        else:
            base = a.bottom
            dns = [x.top for x in htf_other if x.kind == "bull" and x.known <= k and x.top < base]
            dns += [p_.price for p_ in pl if p_.known < wm and p_.price < base and not (wm > p_.i + 1 and bk.wlow[p_.i + 1:wm].min() <= p_.price)]
            if not dns:
                continue
            lo[r], hi[r], dr[r] = max(dns), base, -1
        eq[r] = (lo[r] + hi[r]) / 2
    return {"htf_rng_lo": lo, "htf_rng_hi": hi, "htf_rng_dir": dr, "htf_rng_eq": eq}


def eq_invalid_column(bk: Book, ks, rng: dict) -> np.ndarray:
    """A21-htf-eq-not-violated (cc12_002 ~26:38: "we just don't want to see it violated"): 1 when the last completed weekly close is beyond the EQ of htf_rng against its direction (below it for a bullish
    range) [our interpretation: violated = a weekly body close beyond EQ]."""
    R = len(ks)
    out = np.zeros(R, int)
    for r, k in enumerate(ks):
        dr = rng["htf_rng_dir"][r]
        eq = rng["htf_rng_eq"][r]
        if not dr or eq != eq:
            continue
        q = [i for i in range(len(bk.wl)) if bk.wl[i] <= k]
        if not q:
            continue
        cw = bk.wc[q[-1]]
        out[r] = int((dr > 0 and cw < eq) or (dr < 0 and cw > eq))
    return out


# --------------------------------------------------------------------------------------------------------------
# items 177 / 180 / 181 / 182: the 60-session body range, its eighths, the failed break, the nested ranges
# --------------------------------------------------------------------------------------------------------------

def body_range(o, h, l, c, ks, n: int, two_close: bool = False) -> tuple:
    """A21-60day-body-range (cc07_005 ~4:16) / A21-range-excursion-tolerance (cc07_005 ~15:37): the (lo, hi) per table row of the `n` sessions before it, BODIES (the open-close extremes). With `two_close`
    a session whose close was beyond the range of the n sessions before it and whose NEXT session closed back inside it is a poke and is left out - the range is broken only when a daily body closes beyond
    the extreme and the next day does not close back inside (the last completed session is pending: kept)."""
    bh_, bl_ = np.maximum(o, c), np.minimum(o, c)
    ref_hi = pd.Series(bh_).rolling(n).max().shift(1).values
    ref_lo = pd.Series(bl_).rolling(n).min().shift(1).values
    R = len(ks)
    lo, hi = np.full(R, NAN), np.full(R, NAN)
    for r, k in enumerate(ks):
        k = int(k)
        if k < n:
            continue
        idx = np.arange(k - n, k)
        if two_close:
            keep = []
            for j in idx:
                if j - n >= 0 and ref_hi[j] == ref_hi[j]:
                    beyond = c[j] > ref_hi[j] or c[j] < ref_lo[j]
                    if beyond and j + 1 <= k - 1 and ref_lo[j] <= c[j + 1] <= ref_hi[j]:
                        hit("pd_range_poke")
                        continue
                keep.append(j)
            if keep:
                idx = np.array(keep)
        hi[r], lo[r] = bh_[idx].max(), bl_[idx].min()
    return lo, hi


def grid_position(price: float, lo: float, hi: float) -> tuple:
    """A21-quadrant-grid (cc07_005 ~12:10: "we divide it in half then we divide those halves into halves"): the place of a price in [lo, hi] as (pos 0..1 clipped, eighth 0..7, quadrant 1..4, half) with half
    +1 for the discount half (below the 4/8 line), -1 for the premium half."""
    if not (hi > lo) or price != price:
        return NAN, -1, 0, 0
    pos = min(1.0, max(0.0, (price - lo) / (hi - lo)))
    k = min(7, int(pos * 8))
    return pos, k, k // 2 + 1, 1 if pos < 0.5 else -1


def grid_columns(lo, hi, px) -> dict:
    n = len(px)
    pos, ek, q, half = np.full(n, NAN), np.full(n, -1), np.zeros(n, int), np.zeros(n, int)
    for r in range(n):
        pos[r], ek[r], q[r], half[r] = grid_position(float(px[r]), float(lo[r]), float(hi[r]))
    return {"grid_lo": lo, "grid_hi": hi, "grid_pos": pos, "grid_k": ek, "grid_q": q, "grid_half": half}


def near_grid_line(price: float, lo: float, hi: float, tol_frac: float = 0.10) -> bool:
    """new-pd-array-at-quadrant-level (cc07_006 ~6:03): the price lies within `tol_frac` of a grid spacing (range / 8) of one of the k/8 lines, k = 0..8 [our interpretation: 10 % of the grade spacing]."""
    if not (hi > lo) or price != price:
        return False
    sp = (hi - lo) / 8
    k = round((price - lo) / sp)
    return 0 <= k <= 8 and abs(price - (lo + k * sp)) <= tol_frac * sp + 1e-12


def failed_break_columns(o, h, l, c, ks, n: int, ratio: float = 0.25, look: int = 10) -> dict:
    """new-monthly-failed-consolidation-break (cc12_001 ~45:46): a consolidation (the net move of the reference window under `ratio` of its body range) whose extreme a bar ran beyond within the last
    `look` bars, then closed back inside, then a bar closed through the midpoint, with the last close below it: -1 (bullish mirror +1), the target the lowest (highest) body of the range - ended
    once a later low (high) traded to it. `ks` = the number of completed bars per table row (the daily book: the session index)."""
    R = len(ks)
    fb, tgt = np.zeros(R, int), np.full(R, NAN)
    bh_, bl_ = np.maximum(o, c), np.minimum(o, c)
    for r, k in enumerate(ks):
        k = int(k)
        for s in range(k - 1, max(n, k - look) - 1, -1):
            a = s - n
            if a < 0:
                break
            hi_, lo_ = bh_[a:s].max(), bl_[a:s].min()
            if not hi_ > lo_ or abs(c[s - 1] - c[a]) >= ratio * (hi_ - lo_):
                continue
            mid = (hi_ + lo_) / 2
            if h[s] > hi_ and k - 1 > s and bool((c[s + 1:k] < mid).any()) and c[k - 1] < mid:
                if not (l[s + 1:k].min() <= lo_):
                    fb[r], tgt[r] = -1, lo_
                break
            if l[s] < lo_ and k - 1 > s and bool((c[s + 1:k] > mid).any()) and c[k - 1] > mid:
                if not (h[s + 1:k].max() >= hi_):
                    fb[r], tgt[r] = 1, hi_
                break
    return {"failed_break": fb, "fb_target": tgt}


def failed_break_tf_columns(bk: Book, ks, n_days: int, tfs) -> dict:
    """Review fix (item 181): the failed break on the WEEKLY / MONTHLY consolidations too (cc12_001 ~45:46 shows it on the DXY monthly). Window [our interpretation]: weekly = n_days / 5 bars (12 for the
    60-session range), monthly = 6 bars; the break must be within the last 4 bars of that timeframe. The merged `failed_break` / `fb_target` take the highest timeframe that has one (M, then W, then D);
    failed_break_<tf> / fb_target_<tf> keep each. Weekly / monthly bars are used only once complete (the number of weeks / months ended before the session)."""
    o, h, l, c = bk.o, bk.h, bk.l, bk.c
    ks = np.asarray(ks, int)
    res = {"D": failed_break_columns(o, h, l, c, ks, int(n_days))} if "D" in tfs else {}
    if "W" in tfs:
        wm = np.array([sum(1 for q in bk.wl if q <= int(k)) for k in ks])
        res["W"] = failed_break_columns(bk.wo, bk.wh, bk.wlow, bk.wc, wm, max(4, int(n_days) // 5), look=4)
    if "M" in tfs:
        mo, mh, ml, mc, mlast = BH3.tf_bars(bk.d, "M")
        if len(mc):
            mm = np.searchsorted(mlast, ks - 1, side="right")
            res["M"] = failed_break_columns(mo, mh, ml, mc, mm, 6, look=4)
    R = len(ks)
    fb, tgt = np.zeros(R, int), np.full(R, NAN)
    out = {}
    for tf in ("D", "W", "M"):                       # lowest priority first: a higher timeframe overwrites
        if tf not in res:
            continue
        f_, t_ = res[tf]["failed_break"], res[tf]["fb_target"]
        if tf != "D":
            out[f"failed_break_{tf}"], out[f"fb_target_{tf}"] = f_, t_
            if f_.any():
                sw("failed_consol_tfs")
        m_ = f_ != 0
        fb = np.where(m_, f_, fb)
        tgt = np.where(m_, t_, tgt)
    out["failed_break"], out["fb_target"] = fb, tgt
    return out


def nested_column(bk: Book, ks, px, big_lo, big_hi, on_h, on_l) -> np.ndarray:
    """A21-nested-ranges (cc07_007 ~16:59: "a willingness to not move out of a premium market"): +1 when the price sits in the PREMIUM half of the 60-session body range (above its EQ), a live daily bullish
    array in the DISCOUNT of the smaller (latest daily swing) range was traded into within the last 3 sessions or tonight, no close fell below its MT and the price is above it; -1 the mirror. The smaller
    range = the latest confirmed daily swing low / high of the last 20 sessions."""
    R = len(ks)
    out = np.zeros(R, int)
    for r, k in enumerate(ks):
        k = int(k)
        if big_lo[r] != big_lo[r] or k < 8:
            continue
        a = max(0, k - 20)
        slo, shi = swing_range_at(bk.h[a:k], bk.l[a:k], k - a)
        if slo != slo or shi <= slo:
            continue
        eq_s, eq_b = (slo + shi) / 2, (big_lo[r] + big_hi[r]) / 2
        live = _live_daily(bk, k, 20, typs=("fvg", "ob"))
        v = 0
        if px[r] > eq_b:
            for x in live:
                if x.kind == "bull" and x.ce < eq_s and min(bk.l[max(0, k - 3):k].min(), on_l[r] if on_l[r] == on_l[r] else np.inf) <= x.top and bk.c[k - 1] > x.ce and px[r] > x.ce:
                    v = 1
        if px[r] < eq_b:
            for x in live:
                if x.kind == "bear" and x.ce > eq_s and max(bk.h[max(0, k - 3):k].max(), on_h[r] if on_h[r] == on_h[r] else -np.inf) >= x.bottom and bk.c[k - 1] < x.ce and px[r] < x.ce:
                    v = -1 if v == 0 else 0
        out[r] = v
    return out


def breaker_regime_column(o, h, l, c, ks) -> np.ndarray:
    """A13-daily-breaker-regime (cc12_003 ~22:54): the side of the most recent daily breaker known by the close of the previous session (levels.breakers on the daily bars; +1 a bullish one), held until the
    opposite one forms."""
    zs = sorted(L.breakers(o, h, l, c, 2), key=lambda z: z.i)
    out = np.zeros(len(ks), int)
    for r, k in enumerate(ks):
        cur = 0
        for z in zs:
            if z.i <= k - 1:
                cur = 1 if z.kind == "bull" else -1
        out[r] = cur
    return out


# --------------------------------------------------------------------------------------------------------------
# the table hook
# --------------------------------------------------------------------------------------------------------------

def finish4(out: pd.DataFrame, cfg: dict, d, w, arrs, es_pt: float, df=None) -> pd.DataFrame:
    """Add the b4 columns named in `cfg` to the table `out` (one row per trading day)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    px = out.px.values.astype(float)
    bk = Book(d, w, arrs, es_pt, cfg)
    if "rd" in cfg:
        col = range_day_column(h, l, c, ks, int(cfg["rd"]))
        out["rng_day"] = np.where(out.draw.values == 0, col, 0)
        sw("range_day_mode")
    if "mid" in cfg:
        for k_, v_ in ipda_pos_columns(h, l, c, ks).items():
            out[k_] = v_
        sw("ipda_mid_skip")
    if "chk" in cfg:
        for k_, v_ in checklist_columns(bk, out, ks, px).items():
            out[k_] = v_
        sw("htf_checklist")
    if "dz" in cfg:
        for k_, v_ in dz_columns(bk, ks, px).items():
            out[k_] = v_
        sw("dbisi_lower_half")
    if "cel" in cfg:
        ol_, oh_ = _overnight_extremes(df, d, ks, int(cfg.get("_cut", 570)))
        for k_, v_ in cel_columns(bk, ks, px, oh_, ol_).items():
            out[k_] = v_
        sw("ce_line_bias")
    if "ifb" in cfg:
        for k_, v_ in ifvg_columns(bk, ks, int(cfg["ifb"])).items():
            out[k_] = v_
        sw("ifvg_bias")
    if "trap" in cfg:
        out["trapped_bpr"] = trapped_column(df, d, ks, int(cfg.get("_cut", 570)), int(cfg["trap"]))
        sw("trapped_bpr_bias")
    if "prog" in cfg:
        out["program"] = program_column(o, h, l, c, ks, int(cfg["prog"]))
        sw("program_tag")
    if "mx" in cfg:
        for k_, v_ in matrix_columns(bk, ks, cfg["mx"]).items():
            out[k_] = v_
        sw("matrix_tfs")
    if "mr" in cfg or "mf" in cfg:
        mo, mh, ml, mc, mlast = BH3.tf_bars(d, "M")
        mm = np.searchsorted(mlast, ks - 1, side="right")
        if "mr" in cfg:
            res = [monthly_range_at(mo, mh, ml, mc, int(m)) for m in mm]
            out["m_rng_dir"], out["m_rng_lo"], out["m_rng_hi"] = [r_[0] for r_ in res], [r_[1] for r_ in res], [r_[2] for r_ in res]
            sw("monthly_range")
        if "mf" in cfg:
            fl = monthly_flow_series(mo, mh, ml, mc) if len(mc) else np.zeros(0, int)
            out["m_flow"] = [int(fl[m - 1]) if m >= 1 else 0 for m in mm]
            sw("monthly_flow_gate")
    if "lad" in cfg:
        mult, pxh = cfg["lad"]
        dirs = _ladder_dirs(out)
        lv = [ladder_at(o, h, l, c, int(k), int(dr), float(mult), int(pxh)) if dr else () for k, dr in zip(ks, dirs)]
        out["obl"], out["obl_dir"] = lv, dirs
        sw("ob_ladder")
    rng = None
    if "rng" in cfg:
        rng = htf_range_columns(bk, ks, px)
        for k_, v_ in rng.items():
            out[k_] = v_
        sw("htf_range_arrays")
        if "eqi" in cfg:
            out["eq_invalid"] = eq_invalid_column(bk, ks, rng)
            sw("htf_eq_invalid")
    big = None
    if "grid" in cfg:
        gdays, tc = cfg["grid"]
        glo, ghi = body_range(o, h, l, c, ks, int(gdays), bool(tc))
        big = (glo, ghi)
        for k_, v_ in grid_columns(glo, ghi, px).items():
            out[k_] = v_
        sw("pd_grid")
        if tc:
            sw("pd_range_break")
    if "fb" in cfg:
        for k_, v_ in failed_break_tf_columns(bk, ks, int(cfg["fb"]), tuple(cfg.get("fbt", ("D",)))).items():
            out[k_] = v_
        sw("failed_consol_break")
    if "nest" in cfg and big is not None:
        ol_, oh_ = _overnight_extremes(df, d, ks, int(cfg.get("_cut", 570)))
        out["nested_bias"] = nested_column(bk, ks, px, big[0], big[1], oh_, ol_)
        sw("nested_pd_bias")
    if "brk" in cfg:
        out["brk_regime"] = breaker_regime_column(o, h, l, c, ks)
        sw("breaker_regime")
    if "cad" in cfg:
        out = cadence_freeze(out, int(cfg["cad"]))
    return out


def _ladder_dirs(out) -> list:
    """The side of the B10 sequential (the `mwd` column), else the monthly / weekly bias, else the flip state: the side the ladder is kept for (0 = none). Review fix: per row, the first of these columns
    that is non-zero (a 0 falls through to the next column)."""
    cols = [out[c_].values for c_ in ("mwd", "bias_m", "wk_bias", "flip") if c_ in out]
    res = []
    for r in range(len(out)):
        v_ = 0
        for col in cols:
            v = col[r]
            if v == v and v != 0:
                v_ = int(np.sign(v))
                break
        res.append(v_)
    return res


def _overnight_extremes(df, d, ks, cut_min: int) -> tuple:
    """(low, high) of the bars of session k that closed by `cut_min` (the overnight to the table's cut): the same bars htf.table's `on` frame uses."""
    n = len(ks)
    lo, hi = np.full(n, NAN), np.full(n, NAN)
    if df is None or not len(df):
        return lo, hi
    from .htf import bar_minutes
    lab = pd.to_datetime((df.index + pd.Timedelta(hours=7)).date)
    tmin = df.index.hour * 60 + df.index.minute
    keep = ((tmin < 17 * 60) & (tmin + bar_minutes(df) <= cut_min)) | (tmin >= 17 * 60)
    g = df[keep].groupby(lab[keep])
    mx, mn = g.high.max(), g.low.min()
    for r, k in enumerate(ks):
        t = d.index[int(k)]
        if t in mx.index:
            hi[r], lo[r] = float(mx[t]), float(mn[t])
    return lo, hi
