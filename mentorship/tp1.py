"""Caption-gap pass (digests/rulebook_gaps/*.md), package targets_partials, chunk 1 of 4: the engine glue of its 33 specs -
bias_htf_intermarket.md 14, 34, 70, 137, 176, 183, 208; day_selection_news_calendar.md 1, 3, 8, 52, 76;
definitions_pd_arrays_structure.md 20, 22, 58, 103, 107, 114, 135, 144, 153, 163, 164, 165, 166, 171, 197, 198;
levels_liquidity_targets.md 4, 7 (already built), 8, 9, 11.

Same conventions as es1.py / es2.py / es3.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED
bar, an order armed on it fills from bar i+1), an object only from the bar that completes it. Every function sits behind a Params switch of the
"caption-gap pass, targets_partials #1/4" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's
counter dict (tests: proof that a switch's code path RAN).

Sections: 1 validation - 2 calendar (NFP week, eve of a release, the htf sources) - 3 raw level additions (hook A of strategy._finish_order) -
4 pool tweaks of strategy._targets - 5 caps and gates (hook B) - 6 order-level checks (resistance, eve, runner) - 7 helpers read from other
modules (OR gate, reuse, the dealing range, fulcrum SD, the lock filter, management)."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit

POOLK = ("pool", "pool_eq")
TF_NAME = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h", 240: "4h"}
SPEED_KINDS = ("bump", "speed")
OB_KIND_WORDS = ("ob",)                      # entry kinds holding an order block: ob_pre, ob_anchor, cisd_ob, recap_ob, release_ob, reaper_ob ...


def _S():
    from . import strategy as S
    return S


def _TP():
    from . import targets as TP
    return TP


def _BD():
    from . import bias_day as BD
    return BD


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__) and the inert-switch notes."""
    for name, ok in (("resist_def", ("off", "struct", "htf", "both")), ("eve_mode", ("off", "tag", "bnb")), ("skip_high_resistance", ("off", "tag", "skip")),
                     ("array_reuse", ("first_touch", "reuse", "tiebreak")), ("erl_range_update", ("off", "swing")), ("matrix_anchor", ("eq", "price"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    bad = [m for m in p.speed_bump_tfs if m not in TF_NAME]
    if bad:
        raise ValueError(f"speed_bump_tfs {bad}: expected minutes from {sorted(TF_NAME)}")
    if (p.resist_overlaps < 1 or p.hr_max_obstacles < 1 or p.vi_keep_days < 1 or p.reh_merge_pts < 0 or p.nfp_week_inside_pts < 0
            or not 0 < p.nfp_week_partial < 1 or not 0 < p.htf_runner_frac < 1 or not 0 < p.speed_frac < 1 or not 0 < p.stubby_frac < 1
            or p.eve_target_pts <= 0 or p.eve_risk_mult <= 0 or not (p.nfp_flat_by == 0 or 570 < p.nfp_flat_by <= 960)
            or not p.sd_fulcrum_ext or any(m <= 1.0 for m in p.sd_fulcrum_ext)):
        raise ValueError("targets_partials #1/4: resist_overlaps, hr_max_obstacles, vi_keep_days >= 1; reh_merge_pts, nfp_week_inside_pts >= 0; nfp_week_partial, htf_runner_frac, "
                         "speed_frac, stubby_frac in (0, 1); eve_target_pts, eve_risk_mult > 0; nfp_flat_by 0 or a minute in (570, 960]; sd_fulcrum_ext multiples > 1")
    inert = []
    if p.htf_range_runner and not p.matrix_tf_lower:
        inert.append("htf_range_runner needs matrix_tf_lower (the opposing array one timeframe lower is its level)")
    if (p.vi_void_level or p.vi_ob_levels or p.vi_quarters or p.vi_keep_traded or p.void_ce_rung) and not p.vi_arrays:
        inert.append("vi_void_level / vi_ob_levels / vi_quarters / vi_keep_traded / void_ce_rung read the HTF VI rows: they need vi_arrays=True")
    if p.sd_anchor == "fulcrum_week" and not p.sd_targets:
        inert.append("sd_anchor 'fulcrum_week' needs sd_targets=True")
    if inert:
        warnings.warn("inert switches (targets_partials #1/4): " + "; ".join(inert), stacklevel=4)


def any_on(p) -> bool:
    """True when a switch that acts inside strategy._finish_order is on (the state dict is built only then)."""
    return bool(p.nwog_revert_targets or p.dxy_rally_cap or p.resist_def != "off" or p.post_raid_cap or p.eq_first_rung or p.htf_range_runner
                or p.nfp_week_split or p.nfp_no_htf_targets or p.eve_mode != "off" or p.skip_high_resistance != "off" or p.vi_void_level
                or p.vi_ob_levels or p.vi_keep_traded or p.vi_return_tag or p.bpr_gate_htf or p.old_high_ladder or p.speed_bump_tfs
                or p.void_ce_rung or p.vi_quarters or p.lrlr_zone or p.leg_mt_target or p.rb_fallback or p.matrix_anchor == "price"
                or p.level_polarity or p.ob_location_cap or p.swing_grade_tag)


# --- 2. calendar and sources ------------------------------------------------------------------------------------------------------------------------

def nfp_week_on(p, day) -> bool:
    """N2-nfp-week-imprecise-targets (003 ~00:18:39): `day` lies in an NFP week (Monday-Friday, the jobs date may be shifted - calendar.nfp_date)
    or is an FOMC day."""
    if not p.nfp_week_split:
        return False
    from . import calendar as CAL
    return bool(CAL.nfp_date(day) is not None or CAL.fomc_info(day)["fomc"])


def split_fracs(p, day):
    """The ladder split of an NFP-week / FOMC day (strategy._split), or None."""
    if nfp_week_on(p, day):
        hit("nfp_week_split")
        return (float(p.nfp_week_partial), round(1.0 - float(p.nfp_week_partial), 10))
    return None


def is_jobs_day(day) -> bool:
    from claude_hf.daytypes import events
    return "jobs" in events(day)


def eve_tags(day) -> list:
    """N4-eve-of-high-impact (029 ~00:52:11; 042 ~00:39:05): the release tags of the NEXT trading day, 'pre_cpi' / 'pre_nfp' / 'pre_fomc'."""
    from claude_hf.daytypes import events
    from .calendar import next_trading_day
    ev = events(next_trading_day(day))
    return [nm for tag, nm in (("cpi", "pre_cpi"), ("jobs", "pre_nfp"), ("fomc", "pre_fomc")) if tag in ev]


def _tol(p) -> float:
    return 0.005 * p.es_pt


def near_any(v: float, vals, tol: float) -> bool:
    return any(abs(v - w) <= tol for w in vals)


def htf_values(ctx, sd, i: int, p, above: float, mode: str) -> list:
    """Side-space raw levels that come from HTF sources, read the way the target code reads them. mode 'array' = the daily / weekly / monthly
    confluence arrays (near edge, CE, far edge, the order-block anchors of conf.targets); 'nfp' adds the previous week's pool (N1: the weekly
    target), 'bpr' adds the daily wick CEs and the previous days' / week's highs (A11: PDH / PWH)."""
    out = []
    conf = getattr(ctx, "conf", None)
    TP = _TP()
    if conf is not None:
        now = TP.now_ts(ctx, i)
        tfs = ("D", "W", "M")
        for r in conf.opposing_ext(now, sd.x(above), sd.sign, tfs, (0, 1, 2, 3, 4), straddle=True):
            near, far = TP._zone_edges(sd, r)
            out += [near, (near + far) / 2, far]
        for v in conf.targets(now, sd.x(above), sd.sign, tfs, True):
            out.append(float(sd.x(v)))
    if mode in ("nfp", "bpr") and getattr(ctx, "pw", None) is not None:
        out.append(float(sd.x(ctx.pw[0] if sd.sign > 0 else ctx.pw[1])))
    if mode == "bpr":
        for w in [getattr(ctx, "wick", None)] + list(getattr(ctx, "wicks", []) or []) + list(getattr(ctx, "wick_wk", []) or []):
            if w:
                out.append(float(sd.x(w["upper"] if sd.sign > 0 else w["lower"])))
        for k in (("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")):
            if k in ctx.pd:
                out.append(float(sd.x(ctx.pd[k])))
    return out


# --- 3. raw level additions (hook A) ---------------------------------------------------------------------------------------------------------------

def _row(ctx, session, i):
    return _BD().row_for(ctx, session, i)


def _fin(v) -> bool:
    return v is not None and v == v and np.isfinite(v)


def _clear_path(ctx, sd, i: int, p, lo: float, hi: float) -> bool:
    """No FVG / VI (an opposing zone not yet traded through) lies between `lo` and `hi` (side space) - the intraday zones and the confluence rows."""
    h = sd.h
    for z in list(sd.opposing()) + list(sd.vis("bear")):
        if z.i <= i and lo < z.bottom < hi and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            return False
    conf = getattr(ctx, "conf", None)
    if conf is not None:
        TP = _TP()
        for r in conf.opposing_ext(TP.now_ts(ctx, i), sd.x(lo), sd.sign, ("5m", "15m", "30m", "1h", "4h", "D"), (0, 3)):
            if lo < TP._zone_edges(sd, r)[0] < hi:
                return False
    return True


def _support(ctx, sd, i: int, p, v: float, lv) -> bool:
    """B14 'never alone' (051 ~13:12): another draw factor within eq_tol_pts of the level `v` - a pool of the list (the gap's own levels are arrays, they
    do not count), an open opposing FVG edge / CE or a wick CE [our interpretation]."""
    tol = p.eq_tol_pts * p.es_pt
    if any(k in POOLK and abs(w - v) <= tol for w, k in lv):
        return True
    h = sd.h
    for z in sd.opposing():
        if z.i <= i and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom and (abs(z.bottom - v) <= tol or abs(z.mid - v) <= tol):
            return True
    for w in [getattr(ctx, "wick", None)] + list(getattr(ctx, "wicks", []) or []):
        if w and abs(sd.x(w["upper"] if sd.sign > 0 else w["lower"]) - v) <= tol:
            return True
    return False


def nwog_revert(ctx, sd, i: int, p, session: str, entry: float, lv: list):
    """BH-B14-consolidation-week-reversion (051 ~00:13:12): in a consolidation NWOG week (table column nwog_regime == 'cons') price is pulled back
    into the current NWOG: its near edge is the first rung; an entry already past it takes the nearest OLD NWOG's near edge instead. Only with another
    draw factor within eq_tol_pts (a pool / FVG / wick CE: never alone). Returns the raw rung or None."""
    row = _row(ctx, session, i)
    if not row or (row.get("nwog_regime") or "") != "cons":
        return None
    gaps = [(sd.x(a), sd.x(b)) for a, b, _ in sm2.gap_list(ctx, i)]
    gaps = [(min(a, b), max(a, b)) for a, b in gaps]
    if not gaps:
        return None
    cands = [gaps[-1][0]] if gaps[-1][0] > entry else sorted(g[0] for g in gaps[:-1] if g[0] > entry)[:1]
    for v in cands:
        if _support(ctx, sd, i, p, v, lv):
            return (float(v), "array")
    return None


def eq_rung(ctx, sd, i: int, p, session: str, entry: float) -> list:
    """X3-a21-rebalance-to-eq (cc05_015 ~00:04:03): from a discount of the 20-day range (pd20 columns) the first expected draw is its equilibrium."""
    row = _row(ctx, session, i)
    if not row:
        return []
    hi, lo = row.get("pd20_hi"), row.get("pd20_lo")
    if not (_fin(hi) and _fin(lo)) or hi <= lo:
        return []
    eq = float(sd.x((hi + lo) / 2))
    return [(eq, "eq20")] if eq > entry else []


def old_high_ladder(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """L10-A17-old-high-target-ladder (003 ~01:03:13; 030 ~01:04:30): a draw toward an old swing high with no FVG / VI on the way: T1 = the body edge
    of the swing candle (kind 'speed'), T2 = the upper-wick CE (kind 'array'), T3 = the high itself (the pool already in the list), T4 the next pool."""
    TP = _TP()
    out = []
    for v, k in lv:
        if k not in POOLK or v <= above:
            continue
        body = TP.body_edge(ctx, sd, i, v, p, False)
        if body is None or body >= v - 1e-9:
            continue
        if not _clear_path(ctx, sd, i, p, above, v):
            continue
        if body > above:
            out.append((float(body), "speed"))
        ce = (v + body) / 2
        if ce > above:
            out.append((float(ce), "array"))
    return out


def void_rungs(ctx, sd, i: int, p, above: float) -> list:
    """A10-void-levels-persistence (065 ~1:58:00; 077 ~2:24): the CE of every open liquidity void ahead - the intraday true price gaps (levels.voids) not
    yet traded and the daily / weekly VIs whose wicks also leave a gap (confluence rows keep them while alive: a void left untouched stays open a long time)."""
    out = []
    h = sd.h
    for z in sd._lazy("voids_bear", lambda: [z for z in L.voids(sd.h, sd.l) if z.kind == "bear" and z.top - z.bottom >= sd.min_gap]):
        if z.i <= i and z.bottom > above and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            out.append((float(z.mid), "array"))
    out += [(m, "array") for m in _vi_void_mids(ctx, sd, i, above)]
    return out


def _vi_rows(ctx, sd, i: int, above: float, tfs=("D", "W")) -> list:
    conf = getattr(ctx, "conf", None)
    if conf is None:
        return []
    return conf.opposing_ext(_TP().now_ts(ctx, i), sd.x(above), sd.sign, tfs, (3,))


def _vi_void_mids(ctx, sd, i: int, above: float) -> list:
    out = []
    for r in _vi_rows(ctx, sd, i, above):
        if _fin(r.get("vlo")) and _fin(r.get("vhi")):
            m = float(sd.x((r["vlo"] + r["vhi"]) / 2))
            if m > above:
                out.append(m)
    return out


def vi_ladder(ctx, sd, i: int, p, above: float, lv: list, lvt: list) -> tuple:
    """A10-vi-target-ladder (045 ~02:47:00; 061 ~01:55:50; 076): the HTF VI rungs beyond near edge / CE / far edge - the void midpoint (vi_void_level),
    the OB open + MT in place of the CE for a VI that is part of an order block (vi_ob_levels, 045), the edges of recently traded VIs
    (vi_keep_traded, 076). Returns (the new list, the added rungs)."""
    TP = _TP()
    out = list(lv)
    add = []
    tol = _tol(p)
    rows = _vi_rows(ctx, sd, i, above)
    if p.vi_void_level:
        for m in _vi_void_mids(ctx, sd, i, above):
            add.append((m, "array"))
        if add:
            lvt.append("vi_void")
    if p.vi_ob_levels:
        for r in rows:
            if _fin(r.get("obo")) and _fin(r.get("obm")):
                near, far = TP._zone_edges(sd, r)
                ce = (near + far) / 2
                out = [(v, k) for v, k in out if not (k == "array" and abs(v - ce) <= tol)]
                for v in (sd.x(r["obo"]), sd.x(r["obm"])):
                    if v > above:
                        add.append((float(v), "array"))
                lvt.append("vi_ob")
    if p.vi_keep_traded and getattr(ctx, "conf", None) is not None:
        now = float(TP.now_ts(ctx, i).value)
        span = p.vi_keep_days * 86400e9 * 7 / 5                        # sessions -> calendar ns [our interpretation]
        for r in ctx.conf.rows(("D", "W"), (3,)):
            if r["known"] <= now and np.isfinite(r["dead"]) and r["dead"] <= now and now - r["dead"] <= span:
                for v in (r["top"], r["bottom"]):
                    x = float(sd.x(v))
                    if x > above:
                        add.append((x, "array"))
                lvt.append("vi_kept")
    return out + add, add


def vi_return(ctx, sd, i: int, p, entry: float) -> bool:
    """A10-vi-target-ladder (077 ~00:04:08, test only): the entry sits at an edge of a daily / weekly VI that traded within the last 5 sessions."""
    conf = getattr(ctx, "conf", None)
    if conf is None:
        return False
    now = float(_TP().now_ts(ctx, i).value)
    span = 5 * 86400e9 * 7 / 5
    for r in conf.rows(("D", "W"), (3,)):
        if r["known"] <= now and np.isfinite(r["dead"]) and r["dead"] <= now and now - r["dead"] <= span:
            if any(abs(sd.x(v) - entry) <= 2 * p.es_pt for v in (r["top"], r["bottom"])):
                return True
    return False


def quarters(ctx, sd, i: int, p, above: float) -> list:
    """A9-vi-quarters (074 ~16:08): the 25 / 50 / 75 % levels of every opposing weekly VI as rungs (the 0 / 100 % edges are the VI's own rungs)."""
    out = []
    TP = _TP()
    for r in _vi_rows(ctx, sd, i, above, ("W",)):
        near, far = TP._zone_edges(sd, r)
        out += [(float(near + q * (far - near)), "array") for q in (0.25, 0.5, 0.75) if near + q * (far - near) > above]
    return out


def leg_mt(sd, p, sw: dict, above: float) -> list:
    """A10-one-sided-leg-levels (cc03_002 ~3:38; cc04_004 ~10:17): the body MT of the one-sided displacement leg into the sweep extreme - (the leg's
    first open + its last close) / 2 - is the primary fill target, before the leg start [our interpretation: a leg = >= 2 consecutive same-direction bars]."""
    ls = _TP().leg_start(sd, sw["ext_i"], 0)
    if ls is None:
        return []
    mt = (float(sd.o[ls[0]]) + float(sd.c[sw["ext_i"]])) / 2
    return [(mt, "array")] if mt > above else []


def rb_fallback(ctx, sd, i: int, p, above: float) -> list:
    """A22-rejection-block-fallback (cc05_014 ~22:54): after the mitigation block, breaker, void and FVG the next array is the opposing order block;
    with none in the range (a top of long-wick candles) the rejection block's body level is run and the old high is the final reference."""
    TP = _TP()
    S = _S()
    h = sd.h
    out = []
    for z in TP.rb_zones(sd, p):
        if not (z.i <= i and z.bottom > above and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom):
            continue
        has_ob = any(above < b < z.top for b, _ in S._EN.ob_target_levels(sd, i, above, p))
        conf = getattr(ctx, "conf", None)
        if not has_ob and conf is not None:
            has_ob = any(above < TP._zone_edges(sd, r)[0] < z.top
                         for r in conf.opposing_ext(TP.now_ts(ctx, i), sd.x(above), sd.sign, ("15m", "30m", "1h", "4h", "D"), (1,)))
        if not has_ob:
            out += [(float(z.bottom), "rb"), (float(z.top), "pool")]
    return out


def matrix_price(ctx, sd, i: int, p, entry: float, above: float) -> list:
    """A22-matrix-anchor-market-price (cc06_003 ~3:45; cc07_004 ~2:25): the reference is the current market price, not the leg high: the matrix blocks
    (matrix_targets) between price and `above` are the first unused arrays of the premium list. Exhausted (traded-through) arrays are skipped."""
    if not p.matrix_targets:
        return []
    TP = _TP()
    lo = max(float(entry), float(sd.c[i]))
    h = sd.h
    after = lambda z: h[z.i + 1:i + 1].max(initial=-np.inf)
    out = []
    if "breaker" in p.matrix_targets:
        for z in TP.matrix_breakers(sd, p):
            if z.i <= i and z.bottom > lo and after(z) < z.bottom:
                out += [(float(z.bottom), "array"), (float(z.mt if z.mt == z.mt else z.mid), "array")]
    if "mitigation" in p.matrix_targets:
        for z in sd.opp_mits():
            if z.i <= i and z.bottom > lo and (not (p.mit_body_respect or p.mit_mt_invalid) or L.mitigation_alive(sd.c, z, i, p.mit_mt_invalid)):
                out += [(float(z.bottom), "array"), (float(z.mid), "array")]
    if "rejection" in p.matrix_targets:
        for z in TP.rb_zones(sd, p):
            if z.i <= i and z.bottom > lo and after(z) < z.bottom:
                out.append((float(z.bottom), "rb"))
    return [(v, k) for v, k in out if lo < v <= above]


def polarity(ctx, sd, i: int, p, above: float) -> list:
    """A22-old-level-polarity (cc05_014 ~23:22; cc06_003 ~3:45; cc07_006 ~13:26): an old high / low counts as premium when above price and discount
    when below, whatever its original type - an old low above price (a broken low turned resistance) is a rung of a long, an old high below price
    (a broken high turned support) a rung of a short. Levels the day has already traded back to are spent."""
    keys = ("pdl1", "pdl2", "pdl3", "pml") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3", "pmh")
    out = []
    for k in keys:
        if k in ctx.pd:
            v = float(sd.x(ctx.pd[k]))
            if v > above and sd.h[ctx.start:i + 1].max(initial=-np.inf) < v:
                out.append((v, "pool"))
    return out


def lrlr_zone(ctx, sd, i: int, p):
    """L4-lrlr-bounds (cc01_007 ~12:03), bullish in side space: the low-resistance zone after a fast down leg that broke an old low L_b, a higher low
    and a close above a short-term high (the MSS up). Returns (mss_level, L_b) of the latest such zone known by bar i, or None.
      (1) from the pivot high H0 a fast one-directional leg to the leg low LL: no rally inside it larger than 38 % of the leg [our interpretation of
          'fast' = few retracements]
      (2) after LL a higher pivot low HL, then a close above the highest short-term high between LL and HL (bar m <= i)
      (3) L_b = the nearest confirmed old low above LL that the leg broke (formed before H0)"""
    ph = [q for q in sd.ph if q.known <= i]
    pl = [q for q in sd.pl if q.known <= i]
    for LL in reversed(pl[-8:]):
        hs = [q for q in ph if q.i < LL.i]
        if not hs:
            continue
        H0 = hs[-1]
        leg = H0.price - LL.price
        if leg <= 0 or LL.i - H0.i < 2:
            continue
        run_low, big = float(sd.l[H0.i]), 0.0
        for k in range(H0.i + 1, LL.i + 1):
            big = max(big, float(sd.h[k]) - run_low)
            run_low = min(run_low, float(sd.l[k]))
        if big > 0.38 * leg:
            continue
        old = [q.price for q in pl if q.i < H0.i and LL.price < q.price < H0.price]
        if not old:
            continue
        Lb = min(old)
        for HL in [q for q in pl if q.i > LL.i and q.price > LL.price]:
            sh = [q for q in ph if LL.i < q.i < HL.i + 1 and q.known <= i]
            if not sh:
                continue
            SH = max(sh, key=lambda q: q.price)
            m = next((m for m in range(HL.i + 1, i + 1) if sd.c[m] > SH.price), None)
            if m is not None and SH.price < Lb:
                return float(SH.price), float(Lb)
    return None


def lrlr_rungs(ctx, sd, i: int, p, entry: float, above: float):
    """(the untaken short-term highs inside the zone as rungs, L_b) when the entry sits inside the zone, else ([], None)."""
    z = lrlr_zone(ctx, sd, i, p)
    if z is None or not (z[0] <= entry < z[1]):
        return [], None
    TP = _TP()
    out = [(float(q.price), "swing") for q in TP._ph(sd) if q.known <= i and entry < q.price < z[1] and sd.h[q.i + 1:i + 1].max(initial=-np.inf) < q.price]
    return out, z[1]


def raw_post(ctx, sd, i: int, p, session: str, entry: float, risk: float, above: float, sw: dict, lv: list, lvt: list, st: dict) -> list:
    """Hook A of strategy._finish_order (the raw (level, kind) list in side space, before the exit prices): the NFP-day / NFP-week handling of the HTF
    rungs, then the rungs the chunk adds. `st` collects what the later stages need (one scalp rung, protected rungs)."""
    out = list(lv)
    tol = _tol(p)
    day = ctx.day
    if p.nfp_no_htf_targets and is_jobs_day(day):                       # N1-nfp-no-htf-hold (006 ~00:03:31): intraday liquidity only
        arr = htf_values(ctx, sd, i, p, above, "array")
        pw = [float(sd.x(ctx.pw[0] if sd.sign > 0 else ctx.pw[1]))] if getattr(ctx, "pw", None) is not None else []
        n0 = len(out)
        out = [(v, k) for v, k in out if not ((k not in POOLK and near_any(v, arr, tol)) or (k in POOLK and near_any(v, pw, tol)))]
        st["nfp_htf"] = True
        if len(out) < n0:
            lvt.append("nfp_no_htf")
            hit("nfp_no_htf_drop")
    if nfp_week_on(p, day):                                             # N2-nfp-week-imprecise-targets (003 ~00:18:39): limit just before the array edge
        lvt.append("nfp_week")
        arr = htf_values(ctx, sd, i, p, above, "array")
        sh = p.nfp_week_inside_pts * p.es_pt
        moved = [(v - sh if (k not in POOLK and near_any(v, arr, tol) and v - sh > entry) else v, k) for v, k in out]
        if moved != out:
            hit("nfp_week_inside")
        out = moved
    add = []
    hit("eval_raw_post")
    if p.nwog_revert_targets:
        hit("eval_nwog_revert")
        r = nwog_revert(ctx, sd, i, p, session, entry, out)
        if r is not None:
            add.append(r)
            st["revert"] = r
            lvt.append("nwog_revert")
    if p.eq_first_rung:
        hit("eval_eq_first")
        e = eq_rung(ctx, sd, i, p, session, entry)
        if e:
            add += e
            st.setdefault("lock_rungs", []).extend(e)
            lvt.append("eq_first")
    if p.old_high_ladder:
        hit("eval_old_high")
        o = old_high_ladder(ctx, sd, i, p, above, out)
        if o:
            add += o
            st.setdefault("lock_rungs", []).extend(o)
            lvt.append("old_high_ladder")
    if p.void_ce_rung:
        hit("eval_void_ce")
        v = void_rungs(ctx, sd, i, p, above)
        if v:
            add += v
            lvt.append("void_ce")
    if p.vi_void_level or p.vi_ob_levels or p.vi_keep_traded:
        hit("eval_vi_ladder")
        out, a = vi_ladder(ctx, sd, i, p, above, out, lvt)
        add += a
    if p.vi_quarters:
        hit("eval_vi_quarters")
        q = quarters(ctx, sd, i, p, above)
        if q:
            add += q
            lvt.append("vi_quarters")
    if p.leg_mt_target:
        hit("eval_leg_mt")
        m = leg_mt(sd, p, sw, above)
        if m:
            add += m
            lvt.append("leg_mt")
    if p.rb_fallback:
        hit("eval_rb_fallback")
        r = rb_fallback(ctx, sd, i, p, above)
        if r:
            add += r
            lvt.append("rb_fallback")
    if p.matrix_anchor == "price":
        hit("eval_matrix_price")
        m = matrix_price(ctx, sd, i, p, entry, above)
        if m:
            add += m
            lvt.append("matrix_price")
    if p.level_polarity:
        hit("eval_polarity")
        o = polarity(ctx, sd, i, p, above)
        if o:
            add += o
            lvt.append("polarity")
    if p.lrlr_zone:
        hit("eval_lrlr")
        rs, Lb = lrlr_rungs(ctx, sd, i, p, entry, above)
        if Lb is not None:
            add += rs
            st["lrlr_Lb"] = Lb
            st.setdefault("lock_rungs", []).extend(rs)
    if p.vi_return_tag and vi_return(ctx, sd, i, p, entry):
        lvt.append("vi_return")
    for name in ("nwog_revert", "eq_first", "old_high_ladder", "void_ce", "vi_quarters", "leg_mt", "rb_fallback", "matrix_price", "polarity"):
        if name in lvt:
            hit(name)
    if add:
        out = sorted(set(out) | {(float(v), k) for v, k in add if v > entry})
    return out


# --- 4. pool tweaks of strategy._targets ------------------------------------------------------------------------------------------------------------

def reh_merge(lv: list, p) -> list:
    """A3-reh-under-older-high (021 ~00:40:41): a relative equal high (kind pool_eq) within reh_merge_pts under an older, higher pool is one buy-side
    pool with it - the target is just beyond the older high (X2's pool buffer, _exit_px), not the REH. Returns the merged list."""
    if p.reh_merge_pts <= 0:
        return lv
    gap = p.reh_merge_pts * p.es_pt
    pools = [(v, k) for v, k in lv if k in POOLK]
    drop, up = set(), set()
    for v, k in pools:
        if k != "pool_eq":
            continue
        w = [x for x, _ in pools if 0 < x - v <= gap + 1e-9]
        if w:
            drop.add(v)
            up.add(max(w))
    if not drop:
        return lv
    hit("reh_merge")
    out = []
    for v, k in lv:
        if (v, k) in [(d, "pool_eq") for d in drop]:
            continue
        out.append((v, "pool_eq") if (k in POOLK and v in up) else (v, k))
    return out


def merged_sweep(levels: dict, p, sd) -> dict:
    """The sweep side of the REH merge (mark_levels / _sell_side consumers): of two sell-side pools within reh_merge_pts the one NEARER price (the REL
    above the older lower low, in side space the higher one) is dropped - sweeping it alone does not book the merged pool. `levels` {name: side-space price}."""
    if p is None or p.reh_merge_pts <= 0:
        return levels
    gap = p.reh_merge_pts * p.es_pt
    names = [k for k in levels if k.startswith("rel_eq")]
    drop = set()
    for k in names:
        for j, v in levels.items():
            if j != k and 0 < levels[k] - v <= gap + 1e-9:       # a lower (older) pool within the gap: the higher rel-eq one belongs to it
                drop.add(k)
    if drop:
        hit("reh_merge_sweep")
    return {k: v for k, v in levels.items() if k not in drop}


def stubby(ctx, sd, i: int, p, lv: list) -> list:
    """A23-stubby-wick-first-approach (028 ~15:24): the first approach to a day extreme whose wick is stubby (<= stubby_frac of the candle range) targets
    the wick's CE instead and expects a retrace; the extreme itself comes at a later approach. The candles are the last three regular sessions
    (pdh1-3 / pdl1-3); 'first approach' = today's bars have not come within eq_tol_pts of it [our interpretation]."""
    if not p.stubby_wick_ce or not getattr(ctx, "hist", None):
        return lv
    keys = ("pdh1", "pdh2", "pdh3") if sd.sign > 0 else ("pdl1", "pdl2", "pdl3")
    tol = p.eq_tol_pts * p.es_pt
    today_max = float(sd.h[ctx.start:i + 1].max(initial=-np.inf))
    rep = {}
    for n, k in enumerate(keys, 1):
        if k not in ctx.pd or n > len(ctx.hist):
            continue
        d = ctx.hist[-n]
        o_, c_ = float(d.open.iloc[0]), float(d.close.iloc[-1])
        hi, lo = float(d.high.max()), float(d.low.min())
        rng = hi - lo
        if rng <= 0:
            continue
        v = float(sd.x(ctx.pd[k]))
        body = max(o_, c_) if sd.sign > 0 else min(o_, c_)
        wick = abs((hi if sd.sign > 0 else lo) - body)
        if wick <= 0 or wick / rng > p.stubby_frac or today_max >= v - tol:
            continue
        rep[v] = float(sd.x((ctx.pd[k] + body) / 2))
    if not rep:
        return lv
    hit("stubby_wick_ce")
    return [(rep[v], "array") if (k in POOLK and v in rep) else (v, k) for v, k in lv]


def targets_post(ctx, sd, i: int, p, lv: list) -> list:
    """The pool tweaks at the end of strategy._targets (before the merge of levels within a point)."""
    if p.reh_merge_pts > 0:
        lv = reh_merge(lv, p)
    if p.stubby_wick_ce:
        lv = stubby(ctx, sd, i, p, lv)
    return lv


def or_ok(ctx, p, sd, i: int) -> bool:
    """T4-or-needs-bias-iof (cc10_010 ~00:11:25): the OR30 / OR60 highs and lows are used as levels together with a defined daily bias and the HTF
    institutional order flow; without both they are tags only [our interpretation]. True = the OR level may be used."""
    if not p.or_needs_bias:
        return True
    w = int(getattr(ctx, "cur_bias", 0) or 0)
    row = _row(ctx, getattr(ctx, "cur_session", "") or "AM", i) if w else None
    ok = bool(w and row and int(row.get("iof") or 0) == w)
    hit("or_needs_bias_pass" if ok else "or_needs_bias_block")
    return ok


# --- 5. caps and gates (hook B) --------------------------------------------------------------------------------------------------------------------

def speed_names(ctx, sd, p) -> tuple:
    """N-opposing-fvg-speed-bump (019 ~00:11:08; 089 ~00:04:52): the confluence timeframe names that are neither a cap, a bump rung nor a target for
    this order - only while the session bias agrees with its side."""
    if not p.speed_bump_tfs or int(getattr(ctx, "cur_bias", 0) or 0) != sd.sign:
        return ()
    return tuple(TF_NAME[m] for m in p.speed_bump_tfs)


def bpr_gate(ctx, sd, i: int, p, entry: float):
    """A11-bpr-clear-for-htf-targets (012 ~00:08:35): the nearest opposing BPR above the entry; (near edge, far edge, cleared). Cleared = a bar since the
    BPR formed CLOSED beyond its far edge and left an FVG with it (levels.fvgs, c1 = that bar - 1) [our interpretation of 'trade aggressively through']."""
    zs = [z for z in sd.bprs(p.bpr_max_gap_bars) if z.i <= i and z.bottom > entry]
    if not zs:
        return None
    z = min(zs, key=lambda z: z.bottom)
    cleared = False
    for k in range(z.i + 1, i + 1):
        if sd.c[k] > z.top and any(g.i - 2 == k - 1 and g.kind == "bull" for g in sd.gaps if g.i <= i):
            cleared = True
            break
    return float(z.bottom), float(z.top), cleared


def cap_gates(ctx, sd, i: int, p, session: str, entry: float, risk: float, above: float, lv: list, kinds: list, lvt: list, st: dict, tags: dict):
    """Hook B of strategy._finish_order (exit prices, side space): the gates that cut the ladder. Returns (lv, kinds, cap) - `cap` the highest allowed exit
    (None = no cap), which the caller merges into the owner #7 cap (a locked draw beyond it ends in front of it)."""
    caps = []
    eb = p.exit_before_pts * p.es_pt
    pairs = list(zip(lv, kinds))
    first_rung = next((v for v, k in pairs if k not in SPEED_KINDS and v - entry >= p.min_rr * risk), None)
    if p.dxy_rally_cap:                                              # BH-B19-DXY-falling-risk-on (032 ~00:32:11; 102 ~00:31:27)
        hit("eval_dxy")
        dx = int((getattr(ctx, "intermarket", None) or {}).get("dxy", 0) or 0)
        if first_rung is not None and dx and dx == sd.sign:
            caps.append(first_rung)
            lvt.append("dxy_cap")
            hit("dxy_rally_cap")
    if p.post_raid_cap:                                              # X3-a21-eq-after-raid (cc05_002 ~00:15:30)
        hit("eval_post_raid")
        row = _row(ctx, session, i)
        if row:
            clue = int(row.get("first_clue") or 0)
            tug = int(row.get("tug") or 0)
            rp, req = row.get("raid_px"), row.get("raid_eq")
            if (clue == -sd.sign or tug == -sd.sign) and _fin(rp) and _fin(req) and sd.c[i] <= sd.x(req):
                caps.append(float(sd.x(rp)) - eb)
                lvt.append("post_raid_cap")
                hit("post_raid_cap")
    if p.ob_location_cap and first_rung is not None and any(w in str(tags.get("entry_kind", "")) for w in OB_KIND_WORDS) and "breaker" not in str(tags.get("entry_kind", "")):
        hit("eval_ob_location")
        row = _row(ctx, session, i)
        if row and _fin(row.get("pd20_hi")) and _fin(row.get("pd20_lo")) and row["pd20_hi"] > row["pd20_lo"]:
            eq = float(sd.x((row["pd20_hi"] + row["pd20_lo"]) / 2))
            if entry > eq:                                           # A21-ob-strength-by-location (cc06_004 ~35:33): the wrong half of the range
                caps.append(first_rung)
                lvt.append("ob_loc_cap")
                hit("ob_location_cap")
    Lb = st.get("lrlr_Lb")
    if Lb is not None:                                               # L4-lrlr-bounds (cc01_007 ~12:03): at or above L_b it is high resistance
        c_ = Lb - eb
        if c_ - entry >= p.min_rr * risk:
            caps.append(c_)
            if not any(abs(v - c_) <= p.es_pt for v in lv):
                pairs.append((c_, "array"))
            lvt.append("lrlr_zone")
            hit("lrlr_zone")
    if p.bpr_gate_htf:
        hit("eval_bpr_gate")
        g = bpr_gate(ctx, sd, i, p, entry)
        if g is not None and not g[2]:
            htf = htf_values(ctx, sd, i, p, above, "bpr")
            tol = _tol(p)
            beyond = [(v, k) for v, k in pairs if v > g[1] and near_any(v, htf, tol)]
            if beyond:
                pairs = [x for x in pairs if x not in beyond]
                lvt.append("bpr_chop")
                hit("bpr_gate_htf")
                st["bpr_far"] = g[1]
                st["bpr_near"] = g[0]
    cap = min(caps) if caps else None
    if cap is not None:
        pairs = [(v, k) for v, k in pairs if v <= cap + 1e-9]
    pairs.sort()
    return [v for v, _ in pairs], [k for _, k in pairs], cap


def lock_adjust(ctx, sd, i: int, p, st: dict, tv: float, keep: list, entry: float):
    """The locked draw's raw side-space level `tv` against the chunk's gates: returns (new level or None for 'unchanged', skip reason or None).
    N1: on a jobs day an HTF-array draw is replaced by the last intraday rung (none: no trade); A11: a draw beyond an uncleared BPR ends in front of it."""
    tol = _tol(p)
    if st.get("nfp_htf"):
        if near_any(tv, htf_values(ctx, sd, i, p, entry, "array"), tol):
            hit("nfp_lock_htf")
            return (keep[-1][0] if keep else None), (None if keep else "x_nfp_htf_draw")
    if st.get("bpr_far") is not None and tv > st["bpr_far"] and near_any(tv, htf_values(ctx, sd, i, p, entry, "bpr"), tol):
        return st["bpr_near"] - p.exit_before_pts * p.es_pt, None
    return None, None


# --- 6. order-level checks and tails ----------------------------------------------------------------------------------------------------------------

def bars_m(ctx, sd, i: int, m: int):
    """Side-space m-minute bars made of the COMPLETED base bars up to bar i of the day frame: (high, low) arrays."""
    if ctx.tf == m:
        return np.asarray(sd.h[:i + 1]), np.asarray(sd.l[:i + 1])
    idx = ctx.idx[:i + 1]
    g = pd.Series(np.arange(i + 1), index=idx).groupby(idx.floor(f"{m}min"))
    first, last, st = g.min().values, g.max().values, g.min().index
    done = (idx[last] - st) >= pd.Timedelta(minutes=m - ctx.tf)
    hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])[done]
    ll = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])[done]
    return hh, ll


def resist_class(ctx, sd, i: int, p, session: str, entry: float, t1: float) -> str:
    """BH-L4-resistance-definitions (062 ~00:08:42; cc04_002 ~00:31:25): 'high' / 'low' resistance of a run, by the structure (>= resist_overlaps 5m swing
    pivots lying between the entry and T1: back-and-forth, overlapping swings) and / or the HTF draw (the order against the weekly state)."""
    if p.resist_def == "off":
        return ""
    high = False
    if p.resist_def in ("struct", "both"):
        hh, ll = bars_m(ctx, sd, i, 5)
        if len(hh) >= 3:
            ph, pl = L.pivots(hh, ll, 1)
            n = sum(1 for q in ph + pl if entry < q.price < t1)
            high = high or n >= p.resist_overlaps
    if p.resist_def in ("htf", "both"):
        row = _row(ctx, session, i)
        wk = int((row or {}).get("wk_bias") or 0)
        high = high or wk == -sd.sign
    return "high" if high else "low"


def hr_obstacles(ctx, sd, i: int, p, entry: float, draw: float) -> int:
    """new-skip-high-resistance (036 ~00:39:59): the opposing open FVGs plus the untaken swing pivots between the entry and the draw."""
    TP = _TP()
    n = 0
    h = sd.h
    for z in sd.opposing():
        if z.i <= i and entry < z.bottom < draw and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
            n += 1
    for q in TP._ph(sd):
        if q.known <= i and q.i >= ctx.start - 1 and entry < q.price < draw and h[q.i + 1:i + 1].max(initial=-np.inf) < q.price:
            n += 1
    return n


def eve_one(sd, p, entry: float, lv: list, kinds: list):
    """N4-eve-of-high-impact (042 ~00:39:05), 'bnb': ONE scalp exit at min(entry + eve_target_pts, the first pool), slightly inside the level (029 ~00:52:11:
    price stops one tick short). Returns (exit price, kind) or None when it lies at / under the entry."""
    eb = p.exit_before_pts * p.es_pt
    pool = next((v for v, k in zip(lv, kinds) if k in POOLK and v > entry), None)
    t = entry + p.eve_target_pts * p.es_pt - eb
    if pool is not None:
        t = min(t, pool)
    return (float(t), "array") if t > entry + p.tick else None


def late(ctx, sd, i: int, p, session: str, entry: float, risk: float, tags: dict, lvt: list, lv: list, kinds: list, draw: float, st: dict, risk_mult: float,
         grade_range=None):
    """The order-level checks after the ladder (strategy._finish_order): returns (reject reason or None, risk multiplier, the one-exit rung or None)."""
    one = None
    rm = risk_mult
    day = ctx.day
    if p.eve_mode != "off":
        et = eve_tags(day)
        if et:
            lvt += et + ["high_resistance"]                   # the eve is a high-resistance day (029 ~00:52:11; 042 ~00:39:05)
            rm *= p.eve_risk_mult
            hit("eve_" + p.eve_mode)
            if p.eve_mode == "bnb":
                one = eve_one(sd, p, entry, lv, kinds)
                if one is None:
                    return "x_eve_room", rm, None
                lvt.append("eve_bnb")
                tags["eve_bnb"] = True
    if one is None and st.get("revert") is not None:
        ex = _S()._exit_px(st["revert"][0], "array", p)
        if ex - entry >= p.min_rr * risk:
            one = (float(ex), "array")
            lvt.append("scalp_nwog")
            hit("nwog_revert_scalp")
    if p.resist_def != "off":
        rc = resist_class(ctx, sd, i, p, session, entry, lv[0] if lv else entry)
        if rc:
            tags["resist"] = rc
            if rc == "high":
                lvt.append("high_resist")
                hit("resist_high")
                if p.resist_filter:
                    return "x_high_resistance", rm, None
    if p.skip_high_resistance != "off":
        n = hr_obstacles(ctx, sd, i, p, entry, draw)
        if n >= p.hr_max_obstacles:
            lvt.append("high_res")
            hit("high_res")
            if p.skip_high_resistance == "skip":
                return "x_high_res", rm, None
            tags.setdefault("fracs", tuple(p.ladder_fracs_slow))
    if p.swing_grade_tag:
        g = swing_grade(entry, grade_range)
        if g:
            tags["swing_grade"] = g
            hit("swing_grade")
    return None, rm, one


def swing_grade(entry: float, rng) -> int:
    """new-swing-grades (cc07_003 ~17:26): the grade of the entry in the swing sweep extreme (origin) .. leg high (terminus) - the intraday use of the tag."""
    if not rng:
        return 0
    return L.swing_grade_of(entry, float(rng[0]), float(rng[1]))


def runner(ctx, sd, i: int, p, session: str, entry: float, levels: list) -> float | None:
    """L14-monthly-to-weekly-range (cc07_001 ~00:09:47): the matrix_tf_lower draw (the opposing array one timeframe below the one price reacted from)
    beyond the session ladder: the level a small final slice is held to (side-space exit price) or None."""
    if not p.htf_range_runner or getattr(ctx, "conf", None) is None:
        return None
    hit("eval_runner")
    row = _row(ctx, session, i)
    TP = _TP()
    now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=int(ctx.t[i]) + ctx.tf)
    r = _BD().tf_lower_pref(ctx, row, float(sd.x(sd.c[i])), now, ctx.start)
    if r is None:
        return None
    v = float(_S()._exit_px(float(sd.x(r[0])), "array", p))          # the exit price: one buffer before the array's near edge
    if (levels and v <= max(levels) + p.es_pt) or v <= entry:
        return None
    hit("htf_range_runner")
    return v


def runner_rung(lv: list, kd: list, fr: list, level: float, p):
    """Fill time: the session ladder keeps (1 - htf_runner_frac) of the position, the runner rung (kind 'htf_runner') the rest."""
    f = float(p.htf_runner_frac)
    n = len(lv)
    base = list(fr) if len(fr) == n else _TP()._ext_fracs(tuple(fr), n, False)        # the old ladder's shares over the rungs it has (the last takes the rest)
    s = sum(base) or 1.0
    return list(lv) + [level], list(kd) + ["htf_runner"], [x / s * (1.0 - f) for x in base] + [f]


def trade_fields(o: dict) -> dict:
    """The Trade fields of this chunk carried by an order dict (strategy._make_trade)."""
    return {k: o[k] for k in ("resist", "swing_grade") if k in o}


# --- 7. helpers read from other modules -------------------------------------------------------------------------------------------------------------

def hrlr_filter(ctx, p, up: list, dn: list, kl: int, t_lock: int):
    """L4-hrlr-news-exception (cc01_007 ~00:08:34): a draw that is a high-resistance run (more obstacles between the lock price and it than lrlr_max allows -
    res_high_min when lrlr_max is off) is a locked draw only on a jobs / FOMC day and only after its release; otherwise the next candidate of the list is
    the draw (the nearest intermediate pool). Lists are the lock's (distance, level, kind, name, dir), nearest first, real prices."""
    from claude_hf.daytypes import events
    sm = getattr(ctx, "sides_map", None)
    if not p.hrlr_news_only or not sm:
        return up, dn
    TP = _TP()
    hit("eval_hrlr")
    ev = events(ctx.day)
    rel = [r for tag, r in (("jobs", 510), ("fomc", 840)) if tag in ev]
    after = bool(rel) and t_lock > min(rel)
    if after:
        return up, dn
    px = float(ctx.c[kl - 1])
    lim = p.lrlr_max if p.lrlr_max >= 0 else p.res_high_min - 1
    out = []
    for lst, sign in ((up, 1), (dn, -1)):
        sd = sm[sign]
        keep = []
        for x in lst:
            n = TP.resistance_count(ctx, sd, kl - 1, p, float(sd.x(px)), float(sd.x(x[1])))
            if n > lim:
                hit("hrlr_news_drop")
                continue
            keep.append(x)
        out.append(keep)
    return out[0], out[1]


def untouched(ctx, sign: int, i: int, r: dict) -> bool:
    """A22-array-reuse: is the opposing HTF array row `r` (real prices) still unspent for a target? 'first_touch': the old rule (price never traded into
    it since it formed); 'reuse' / 'tiebreak': spent only when a bar CLOSED through its CE since it formed (the narrative is intact until a body
    closes through the MT / CE or the bias flips; the bias part lives in the htf table). `sign` = the trade's side (+1: the array is resistance above)."""
    ce = (r["top"] + r["bottom"]) / 2
    ns = _TP()._ns(ctx)[:i + 1]
    m = ns >= r["known"]
    if not m.any():
        return True
    c = ctx.c[:i + 1][m]
    return not ((c > ce).any() if sign > 0 else (c < ce).any())


def fulcrum_week(ctx, sd, i: int, p=None):
    """new-swing-projection-fulcrum (cc07_003 ~27:33), side space: the consolidation midweek rally. The fulcrum = the week's highest high made on Monday or
    Tuesday, where the retracement starts; the low = the lowest low after it (the discount array hit Tue / Wed). Returns (low, high) or None.
    Needs the regular-session history of the week (ctx.hist) plus today's bars up to bar i."""
    d0 = ctx.day
    mon = d0 - pd.Timedelta(days=d0.weekday()).to_pytimedelta()
    days = [(x.index[0].date(), x) for x in getattr(ctx, "hist", []) if x.index[0].date() >= mon and x.index[0].date() < d0]
    hs, ls, ds = [], [], []
    for d, fr in days:
        hh, ll = (fr.high.values, fr.low.values) if sd.sign > 0 else (-fr.low.values, -fr.high.values)
        hs += list(hh.astype(float))
        ls += list(ll.astype(float))
        ds += [d.weekday()] * len(hh)
    hs += list(sd.h[ctx.start:i + 1])
    ls += list(sd.l[ctx.start:i + 1])
    ds += [d0.weekday()] * (i + 1 - ctx.start)
    if len(hs) < 3:
        return None
    hs, ls, ds = np.asarray(hs), np.asarray(ls), np.asarray(ds)
    k = int(np.argmax(hs))
    if ds[k] > 1 or k >= len(hs) - 1:
        return None
    lo = float(ls[k + 1:].min())
    return (lo, float(hs[k])) if hs[k] > lo else None


def fulcrum_levels(ctx, sd, i: int, p, entry: float) -> list:
    """The fulcrum_week projections (side space): low + m x (high - low) for the sd_fulcrum_ext multiples (1.27 / 1.68 / 2.0 = the 100 % symmetrical
    swing), kept only where they overlap an opposing array on a lower timeframe when sd_need_array is on."""
    f = fulcrum_week(ctx, sd, i, p)
    if f is None:
        return []
    lo, hi = f
    out = [lo + m * (hi - lo) for m in p.sd_fulcrum_ext]
    out = [v for v in out if v > entry]
    if p.sd_need_array and out:
        conf = getattr(ctx, "conf", None)
        keep = []
        tol = p.sd_align_tol_pts * p.es_pt
        if conf is not None:
            TP = _TP()
            rows = conf.opposing_ext(TP.now_ts(ctx, i), sd.x(entry), sd.sign, ("15m", "30m", "1h", "4h"), (0, 1, 3), straddle=True)
            zones = [TP._zone_edges(sd, r) for r in rows]
            keep = [v for v in out if any(a - tol <= v <= b + tol for a, b in zones)]
        out = keep
    if out:
        hit("sd_fulcrum_week")
    return out


def current_range(sd, i: int, floor: int = 0):
    """L14-dealing-range-redefine (cc04_002 ~5:59): the rolling dealing range (low, high) in side space as known at bar i. It starts as the first
    confirmed swing pair after `floor`; whenever a confirmed swing high exceeds range_high the range is redefined: range_high = the new swing high,
    range_low = the lowest confirmed swing low between the old range high's bar and the new one (the swing low that started the leg)."""
    ph = [q for q in sd.ph if q.known <= i and q.i >= floor]
    pl = [q for q in sd.pl if q.known <= i and q.i >= floor]
    if not ph or not pl:
        return None
    hi_q = ph[0]
    lows0 = [q for q in pl if q.i < hi_q.i]
    lo = min(lows0, key=lambda q: q.price).price if lows0 else min(q.price for q in pl)
    prev_i = hi_q.i
    for q in ph[1:]:
        if q.price > hi_q.price:
            ls = [x for x in pl if prev_i < x.i < q.i]
            if ls:
                lo = min(x.price for x in ls)
            hi_q, prev_i = q, q.i
    return float(lo), float(hi_q.price)


def htf_entry(tr) -> bool:
    """A22-array-reuse: the trade's entry array is a weekly / monthly array (the X9 time stop does not apply)."""
    return any(t in ("W", "M") for t in str(getattr(tr, "conf_tfs", "") or "").split("|"))
