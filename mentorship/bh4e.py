"""Caption-gap pass, package bias_htf#4/7 (digests/rulebook_gaps/day_selection_news_calendar.md items 46, 51, 74 and definitions_pd_arrays_structure.md items 27, 28, 61, 80, 110, 119, 147, 148, 150, 160,
162, 168-170, 177-179, 181-183, 185) - ENGINE SIDE.

The bar-loop part: side gates, per-order rules and tags, scalps, the neutral-bias fallbacks, the ladder entry level, the leg_pd waiver, the IFVG add. The columns they read are built by `bh4.py` inside
`htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a completed hist session. Hooks (who calls them)
  side_ok          daycontext.side_ok tail     range_day_mode (pm_only), ipda_mid_skip, htf_checklist, dbisi_lower_half, ce_line_bias, monthly_flow_gate, breaker_regime
  order_ok         daycontext.order_ok tail    dbisi_upper_and_discount, salient_pd, swing_extreme_block, pd_need_array, tags (program, grid, grade_confluence, htf range, matrix, monthly range, failed break)
  scalp_now        daycontext.scalp_now tail   range_day_mode (scalp)
  want_adjust      bias_day.want_at            trapped_bpr_bias, failed_consol_break, nested_pd_bias, ifvg_bias (a neutral bias takes them), htf_eq_invalid (the bias turns neutral)
  range_day        newscal.carry_lock          range_day_mode pm_only: the PM carries the AM draw
  ladder_rows      strategy._ts_arrays0        ob_ladder
  leg_pd_exempt    strategy (leg_pd tests)     swing_ignore_eq
  ifvg_add_zone    entries.more_add_arrays     ifvg_edge_add
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np

from . import levels as L
from . import bh1e as B1
from . import bh2 as BH2
from . import bh4 as BH4

HITS = BH2.HITS
sw = BH2.sw
_n, _f, _row = B1._n, B1._f, B1._row


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def _BD():
    return B1._BD()


def on(p) -> bool:
    """Any engine-side bias_htf#4/7 switch is on (the hooks return at once otherwise)."""
    return bool(p.range_day_mode != "off" or p.ipda_mid_skip or p.htf_checklist or p.dbisi_lower_half or p.dbisi_upper_and_discount or p.ce_line_bias or p.monthly_flow_gate or p.breaker_regime
                or p.salient_pd or p.swing_extreme_block or p.pd_need_array or p.program_tag or p.pd_grid or p.grade_confluence or p.htf_range_arrays or p.matrix_tfs != ("D",) or p.monthly_range
                or p.failed_consol_break)


def want_on(p) -> bool:
    return bool(p.trapped_bpr_bias or p.failed_consol_break or p.nested_pd_bias or p.ifvg_bias or p.htf_eq_invalid)


def _sess_row(ctx, i: int):
    return _row(ctx, "AM" if ctx.t[i] < 810 else "PM", i)


# --------------------------------------------------------------------------------------------------------------
# readings shared by the rules
# --------------------------------------------------------------------------------------------------------------

def range_day(ctx) -> bool:
    """The day is range-bound (table rng_day at the 09:30 row)."""
    row = getattr(ctx, "bias_row", None)
    return bool(row is not None and _n(row, "rng_day"))


def dbisi_lower_filled(ctx, row, sign: int, i: int) -> bool:
    """A5-ltf-fvgs-inside-daily-bisi (012 ~19:16: "the ones in the lower half they are likely to stay open"): the price is inside a daily FVG of the order's side (a BISI for a long) and a 1h / 15m FVG of
    that side lying inside its LOWER half (below the CE; the upper half for a short) has been filled by a body close through it since it formed. Upper-half fills are acceptable and never count."""
    if row is None or _n(row, "dz_dir") != sign:
        return False
    zlo, zhi, zce = _f(row, "dz_lo"), _f(row, "dz_hi"), _f(row, "dz_ce")
    if zlo != zlo or zhi != zhi or zce != zce:
        return False
    kind = "bull" if sign > 0 else "bear"
    for m in (60, 15):
        b = B1.tf_complete(ctx, m, i)
        if len(b["c"]) < 3:
            continue
        for z in L.fvgs(b["h"], b["l"], b["o"], b["c"]):
            if z.kind != kind:
                continue
            lower = (z.bottom >= zlo and z.top <= zce) if sign > 0 else (z.top <= zhi and z.bottom >= zce)
            if not lower:
                continue
            later = b["c"][z.i + 1:]
            if len(later) and ((sign > 0 and later.min() < z.bottom) or (sign < 0 and later.max() > z.top)):
                return True
    return False


def cel_state(ctx, row, i: int) -> int:
    """A8-ce-line-bearish-read (030 ~1:38:43): the lean of the CE line at closed bar i - for a bullish gap whose CE was traded through: -1 (bearish) while the price is under the CE, +1 once TWO 15m closes
    since 09:30 sit above it ('holds as support with a rally'; [our interpretation]) until a close falls back under it; a bearish gap mirrors it. 0 without a line."""
    kind = _n(row, "cel_kind") if row is not None else 0
    if not kind:
        return 0
    ce = _f(row, "cel_ce")
    b = B1.tf_complete(ctx, 15, i)
    cl = b["c"][b["first"] >= ctx.start] if len(b["c"]) else np.array([])
    st, cnt = -kind, 0
    for x in cl:
        back = x > ce if kind > 0 else x < ce
        if back:
            cnt += 1
            if cnt >= 2:
                st = kind
        else:
            cnt, st = 0, -kind
    return st


def path_obstructed(ctx, sign: int, session: str, i: int) -> bool:
    """DS2-buy-day-checklist (c): with the confluence table, an opposing daily / 4h array whose near edge lies between the close and the session's locked draw (the 4h part the daily table cannot see)."""
    cf = getattr(ctx, "conf", None)
    lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in ("PM", "LUNCH") else "AM")
    if cf is None or not hasattr(cf, "opposing") or not lk or lk.get("target") is None or not lk.get("side"):
        return False
    import pandas as pd
    px = float(ctx.c[i])
    tgt = float(lk["target"])
    if (tgt - px) * sign <= 0:
        return False
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    r = cf.opposing(now, px, sign, ("D", "4h"), (0,))
    if not r:
        return False
    near = float(r[0][0])
    return (near - px) * sign > 0 and (tgt - near) * sign > 1e-9


def salient_eq(ctx, m: int, i: int):
    """A21-salient-dealing-ranges (061 ~1:38:11: "all the ranges that are Salient"): the EQ of the latest intermediate-term run of the timeframe `m` (minutes; 1440 = the completed daily sessions): the
    last intermediate-term high and low of levels.swing_tiers [our interpretation of 'intermediate run']. None when the pair does not exist."""
    if m == 1440:
        hist = getattr(ctx, "hist", None) or []
        if len(hist) < 5:
            return None
        h = np.array([float(x.high.max()) for x in hist])
        l = np.array([float(x.low.min()) for x in hist])
    else:
        b = B1.tf_complete(ctx, m, i)
        if len(b["c"]) < 5:
            return None
        h, l = b["h"], b["l"]
    t = L.swing_tiers(h, l, 1)["itl"]
    if not t[0] or not t[1]:
        return None
    return (t[0][-1].price + t[1][-1].price) / 2


def entry_in_htf_array(ctx, sd, o: dict, i: int, p) -> bool:
    """The order's entry lies inside a daily / 4h / HTF array of its side (the confluence table's at(); without it the session's HTF zones)."""
    S = _S()
    entry_raw = sd.x(o["entry"])
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        import pandas as pd
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        return bool(cf.at(now, entry_raw, sd.sign))
    return bool(S._htf_tag(ctx, sd, i, o["entry"], p.eq_tol_pts * p.es_pt))


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#4/7 reason, else None."""
    if not on(p) or i is None:
        return None
    if p.range_day_mode == "pm_only" and ctx.t[i] < 810 and range_day(ctx):
        sw("range_day_mode")
        return "x_bh4_range_day"
    row = _row(ctx, session, i)
    if row is None:
        return None
    if p.ipda_mid_skip and "ipda_pos" in row:
        pos = _f(row, "ipda_pos")
        if pos == pos:
            sw("ipda_mid_skip")
            if p.ipda_mid_lo <= pos <= p.ipda_mid_hi:
                lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in ("PM", "LUNCH") else "AM")
                if _BD().want_at(ctx, p, session, i) == 0 or not (lk and lk.get("side")):
                    hit("ipda_mid_skip")
                    return "x_bh4_ipda_mid"
            elif (pos < p.ipda_mid_lo and sign < 0) or (pos > p.ipda_mid_hi and sign > 0):
                return "x_bh4_ipda_quadrant"
    if p.htf_checklist and "chk_q" in row:
        sw("htf_checklist")
        q = _n(row, "chk_q")
        ok = (q > 0 and _n(row, "chk_react_up") and _n(row, "chk_path_up") == 0) if sign > 0 else (q < 0 and _n(row, "chk_react_dn") and _n(row, "chk_path_dn") == 0)
        if ok and path_obstructed(ctx, sign, session, i):
            ok = False
        if not ok:
            return "x_bh4_htf_checklist"
    if p.dbisi_lower_half and "dz_dir" in row:
        sw("dbisi_lower_half")
        if dbisi_lower_filled(ctx, row, sign, i):
            return "x_bh4_dbisi_lower_filled"
    if p.ce_line_bias and "cel_kind" in row:
        st = cel_state(ctx, row, i)
        if st:
            sw("ce_line_bias")
            if sign == -st:
                return "x_bh4_ce_line"
    if p.monthly_flow_gate and "m_flow" in row:
        fl = _n(row, "m_flow")
        if fl:
            sw("monthly_flow_gate")
            if sign == -fl:
                return "x_bh4_monthly_flow"
    if p.breaker_regime and "brk_regime" in row:
        rg = _n(row, "brk_regime")
        if rg:
            sw("breaker_regime")
            if sign == -rg:
                return "x_bh4_breaker_regime"
    return None


# --------------------------------------------------------------------------------------------------------------
# the per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#4/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p):
        return None
    row = _row(ctx, session, i)
    sign = sd.sign
    entry_raw = sd.x(o["entry"])
    tags: list = []
    if p.dbisi_upper_and_discount and row is not None and _n(row, "dz_dir") == sign:
        ce = _f(row, "dz_ce")
        lo, hi = _f(row, "pd20_lo"), _f(row, "pd20_hi")
        if lo != lo or hi != hi:
            from . import bh3e as _B3
            lo, hi = _B3._range20(ctx, p)
        if ce == ce:
            sw("dbisi_upper_and_discount")
            eq = (lo + hi) / 2 if (lo == lo and hi == hi and hi > lo) else None
            upper = entry_raw >= ce - 1e-9 if sign > 0 else entry_raw <= ce + 1e-9
            disc = True if eq is None else (entry_raw < eq if sign > 0 else entry_raw > eq)
            if not (upper and disc):
                return "x_bh4_dbisi_location"
    if p.salient_pd:
        for m in p.salient_pd:
            eq = salient_eq(ctx, int(m), i)
            if eq is not None:
                sw("salient_pd")
                if (sign > 0 and entry_raw > eq) or (sign < 0 and entry_raw < eq):
                    return "x_bh4_salient_pd"
    if row is not None and "htf_rng_lo" in row:
        lo, hi = _f(row, "htf_rng_lo"), _f(row, "htf_rng_hi")
        if lo == lo and hi == hi and hi > lo:
            pos = (entry_raw - lo) / (hi - lo)
            if p.swing_extreme_block:
                sw("swing_extreme_block")
                if (sign > 0 and pos >= p.swing_block_long - 1e-12) or (sign < 0 and pos <= p.swing_block_short + 1e-12):
                    return "x_bh4_swing_extreme"
            if p.htf_range_arrays:
                sw("htf_range_arrays")
                tags.append(f"htfrng_{pos:.2f}")
    if row is not None and "grid_lo" in row and (p.pd_grid or p.grade_confluence or p.pd_need_array):
        glo, ghi = _f(row, "grid_lo"), _f(row, "grid_hi")
        pos, ek, q, half = BH4.grid_position(entry_raw, glo, ghi)
        if ek >= 0:
            if p.pd_grid:
                sw("pd_grid")
                tags.append(f"grid_q{q}_{'disc' if half > 0 else 'prem'}_k{ek}")
            if p.grade_confluence and ((sign > 0 and half > 0) or (sign < 0 and half < 0)) and BH4.near_grid_line(entry_raw, glo, ghi):
                sw("grade_confluence")
                tags.append("grade_confluence")
            if p.pd_need_array:
                sw("pd_need_array")
                disc_band = (ek % 2 == 0) if sign > 0 else (ek % 2 == 1)            # [our interpretation] the discount (premium for a short) of its own quadrant
                if not (disc_band and entry_in_htf_array(ctx, sd, o, i, p)):
                    return "x_bh4_pd_need_array"
    if p.program_tag and row is not None and "program" in row:
        v = _n(row, "program")
        if v:
            sw("program_tag")
            tags.append("program_agree" if v == sign else "program_oppose")
    if p.matrix_tfs != ("D",) and row is not None:
        for tf in ("W", "M"):
            eq = _f(row, f"mx_{tf}_eq")
            if tf in p.matrix_tfs and eq == eq:
                sw("matrix_tfs")
                tags.append(f"mx_{tf}_{'disc' if entry_raw < eq else 'prem'}")
    if p.monthly_range and row is not None and "m_rng_dir" in row:
        d_ = _n(row, "m_rng_dir")
        lo, hi = _f(row, "m_rng_lo"), _f(row, "m_rng_hi")
        if d_ and lo == lo and hi == hi:
            sw("monthly_range")
            tags.append("mrng_in" if lo <= entry_raw <= hi else "mrng_out")
    if p.failed_consol_break and row is not None and "failed_break" in row and _n(row, "failed_break"):
        sw("failed_consol_break")
        tags.append("failed_break_agree" if _n(row, "failed_break") == sign else "failed_break_oppose")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """The reason an order is a scalp for bias_htf#4/7 (range_day_mode 'scalp'), else ''."""
    if p.range_day_mode == "scalp" and range_day(ctx):
        sw("range_day_mode")
        return "bh4_range_day"
    return ""


# --------------------------------------------------------------------------------------------------------------
# the bias fallbacks
# --------------------------------------------------------------------------------------------------------------

def want_adjust(ctx, p, session: str, i: int, v: int) -> int:
    """The htf_bias value after the bias_htf#4/7 readings: a weekly close beyond the htf range's EQ against its direction turns that direction neutral (htf_eq_invalid); a NEUTRAL bias takes, in order,
    the nested-range bias, the trapped-trader BPR, the failed consolidation break and the IFVG bias."""
    row = _row(ctx, session, i)
    if row is None:
        return v
    if v and p.htf_eq_invalid and _n(row, "eq_invalid") and _n(row, "htf_rng_dir") == v:
        sw("htf_eq_invalid")
        return 0
    if v:
        return v
    for flag, col, name in ((p.nested_pd_bias, "nested_bias", "nested_pd_bias"), (p.trapped_bpr_bias, "trapped_bpr", "trapped_bpr_bias"), (p.failed_consol_break, "failed_break", "failed_consol_break"),
                            (p.ifvg_bias, "ifvg_bias", "ifvg_bias")):
        if flag and col in row:
            x = _n(row, col)
            if x:
                sw(name)
                return x
    return v


# --------------------------------------------------------------------------------------------------------------
# the ladder, the leg_pd waiver, the IFVG add
# --------------------------------------------------------------------------------------------------------------

def ladder_rows(ctx, sd, i: int) -> list:
    """A12-stepping-ob: the ladder's highest level at or under the price (above it for a short) as a zero-height entry array of the order's side (side space top, bottom, known)."""
    row = _sess_row(ctx, i)
    if row is None or "obl" not in row or _n(row, "obl_dir") != sd.sign:
        return []
    kn = ctx.idx[ctx.start]
    px = float(sd.x(ctx.c[i]))
    for v in row.get("obl") or ():
        x = float(sd.x(v))
        if x <= px:
            sw("ob_ladder")
            return [(x, x, kn)]
    return []


def leg_pd_exempt(ctx, sd, entry: float, i: int, p) -> bool:
    """A21-swing-discount-exception (cc05_017 ~10:19; cc06_003 ~17:18): with the htf range's direction intact (htf_rng_dir = the side) the leg_pd premium test is waived for an entry below the close of the
    last down-close daily candle, or inside an HTF array of the side between the range low and its high; the cap stays (a long at or above swing_block_long of the range is never waived)."""
    row = _sess_row(ctx, i)
    if row is None or _n(row, "htf_rng_dir") != sd.sign:
        return False
    lo, hi = _f(row, "htf_rng_lo"), _f(row, "htf_rng_hi")
    if not (lo == lo and hi == hi and hi > lo):
        return False
    raw = float(sd.x(entry))
    pos = (raw - lo) / (hi - lo)
    if (sd.sign > 0 and pos >= p.swing_block_long) or (sd.sign < 0 and pos <= p.swing_block_short):
        return False
    hist = getattr(ctx, "hist", None) or []
    ok = False
    for x in reversed(hist):                                          # (a) the last down-close (up-close) daily candle
        o_, c_ = float(x.open.iloc[0]), float(x.close.iloc[-1])
        if (sd.sign > 0 and c_ < o_) or (sd.sign < 0 and c_ > o_):
            ok = raw < c_ if sd.sign > 0 else raw > c_
            break
    if not ok and lo <= raw <= hi:                                    # (b) a bullish (bearish) array inside the range
        ok = entry_in_htf_array(ctx, sd, {"entry": entry}, i, p)
    if ok:
        sw("swing_ignore_eq")
    return bool(ok)


def ifvg_add_zone(ctx, sd, pos: dict, i: int, p):
    """A8-ifvg-bias-without-retest (070 ~13:02): the add zone (top, floor) of the HTF IFVG of the position's side once a closed body has held at or beyond its edge - the bar's lowest body price at or
    above the zone top (below it for a short; wicks may poke) and the close beyond it. None otherwise."""
    row = _sess_row(ctx, i)
    if row is None or _n(row, "ifvg_bias") != sd.sign or i <= pos.get("fill_i", i):
        return None
    top, bot = _f(row, "ifvg_top"), _f(row, "ifvg_bot")
    if top != top or bot != bot:
        return None
    a, b = float(sd.x(top)), float(sd.x(bot))
    zt, zb = max(a, b), min(a, b)
    tk = float(p.tick)
    if min(sd.o[i], sd.c[i]) >= zt - tk and sd.c[i] > zt and zt > pos["stop"]:
        sw("ifvg_edge_add")
        return zt, zb
    return None
