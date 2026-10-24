"""Caption-gap pass (digests/rulebook_gaps/*.md), package entries_stops_sizing, chunk 2 of 3: the engine glue of its 35 specs - definitions_pd_arrays_structure.md items 146, 151, 154, 155, 186, 190;
levels_liquidity_targets.md items 10, 90, 120; management_partials_trailing_exits.md items 105, 129; models_setups_entries.md items 6, 7, 18, 24, 27, 29, 30, 38, 44, 45, 52, 73, 82, 92, 124, 141;
stops_sizing_scaling_in.md items 1, 2, 3, 4, 6, 8, 9, 10.

Same conventions as es1.py / sm2.py ... sm7.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an
object only from the bar that completes it. Every function sits behind a Params switch of the "caption-gap pass, entries_stops_sizing #2/3" block; interpretations the sources do not pin down are
marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Sections: 1 add sizes / ladders / locations (E12) - 2 order blocks (A12) - 3 entry gaps and prices (E1 / E2 / A5) - 4 stops (A11 / E6 / A13) - 5 order gate (tags, multipliers) - 6 position hooks.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit
MIN1 = 1e-9

ENTRY_MODES_ES2 = ("far_on_breaker", "auto2")


def _S():
    from . import strategy as S
    return S


def _tol(p) -> float:
    return p.eq_tol_pts * p.es_pt


def _es(o: dict | None) -> dict:
    return (o or {}).get("es2") or {}


def tag(tags: dict, **kw) -> None:
    """Merge keys into the order's `es2` dict (the chunk's own state, read at the fill)."""
    d = dict(tags.get("es2") or {})
    d.update(kw)
    tags["es2"] = d


def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__)."""
    for name, ok in (("add_sizes", ("decreasing", "equal_or_less", "equal_013")), ("add_ladder", ("", "631", "6421", "6321", "067")),
                     ("gap_risk", ("off", "widen", "skip")), ("ifvg_stop", ("ce", "far")),
                     ("add_after_partial", ("", "inv_fvg", "high_vol")), ("add_day_mode", ("eq_cutoff", "trend_day")),
                     ("add_low_end_size", ("smallest", "ladder"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if p.entry not in _S().ENTRY_MODES + ENTRY_MODES_ES2:
        raise ValueError(f"entry {p.entry!r}: expected one of {_S().ENTRY_MODES + ENTRY_MODES_ES2}")
    if p.entry_order not in ("limit", "stop_cc", "market_on_touch"):
        raise ValueError(f"entry_order {p.entry_order!r}: expected 'limit', 'stop_cc' or 'market_on_touch'")
    if p.ob_arm not in ("leave", "touch", "intrabar_htf"):
        raise ValueError(f"ob_arm {p.ob_arm!r}: expected 'leave', 'touch' or 'intrabar_htf'")
    if len(p.ob_grade_mult) != 2 or any(m <= 0 for m in p.ob_grade_mult):
        raise ValueError(f"ob_grade_mult {p.ob_grade_mult!r}: expected two multipliers > 0 (A, B)")
    for t_ in tuple(p.ob_session_windows) + tuple(p.close_prox_windows):
        if len(t_) != 2 or not (0 <= int(t_[0]) < int(t_[1]) <= 1440):
            raise ValueError(f"window {t_!r}: expected (start_minute, end_minute) pairs inside the day")
    if (p.ob_grade_tol < 0 or p.rb_ctx_mult <= 0 or p.entry_fvg_min_tf < 1 or p.bpr_adj_pts < 0 or p.bz_higher_pts < 0 or p.vi_add_early_pts < 0 or p.wick_ce_lookback < 1
            or p.breakaway_chase_bars < 1 or p.iofed_gap_bars < 0 or p.iofed_gap_pts < 0 or p.entry_offset_ticks < 0 or p.add_max_n < 1 or p.add_hv_mult <= 0
            or p.trend_day_adr <= 0 or p.gap_risk_near_pts < 0):
        raise ValueError("entries_stops_sizing #2/3: ob_grade_tol, bpr_adj_pts, bz_higher_pts, vi_add_early_pts, iofed_gap_*, entry_offset_ticks, gap_risk_near_pts >= 0; rb_ctx_mult, add_hv_mult, "
                         "trend_day_adr > 0; entry_fvg_min_tf, wick_ce_lookback, breakaway_chase_bars, add_max_n >= 1")


# --- 1. add sizes / ladders / locations (E12) -----------------------------------------------------------------------------------------------------

LADDERS = {"631": (0.5, 0.17), "6421": (0.67, 0.33, 0.17), "6321": (0.5, 0.33, 0.17), "067": (0.625, 0.625, 0.25, 0.625, 0.625)}


def sizing_on(p) -> bool:
    return bool(p.add_ladder or p.add_sizes != "decreasing")


def add_size_fracs(p) -> tuple:
    """E12 / stops_sizing 1-3: the add fractions of the first unit. `add_ladder` wins (631 = 6/3/1, 6421 = 6/4/2/1, 6321 = 6/3/2/1 = the built `adds`, 067 = 8 then 5/5/2/5/5); else add_sizes
    ("equal_or_less": add_max_n adds of the first unit's size, the 1.3 % cap in _arm_add still shrinks them; "equal_013": the 013 variant 10 / 10 / 5 / 5 = adds 1.0, 0.5, 0.5); else p.adds."""
    if p.add_ladder:
        return LADDERS[p.add_ladder]
    if p.add_sizes == "equal_or_less":
        return (1.0,) * max(1, int(p.add_max_n))
    if p.add_sizes == "equal_013":
        return (1.0, 0.5, 0.5)
    return tuple(p.adds)


def apply_sizing(p):
    """run_day: the size switches replace Params.adds for the whole day (adds=() stays off: a size switch never turns the pyramid on)."""
    if not sizing_on(p) or not p.adds:
        return p
    hit("add_sizes")
    return replace(p, adds=add_size_fracs(p))


def add_loc_on(p) -> bool:
    return bool(p.add_far_edge or p.add_wick_retouch or p.add_htf_fvg_edge or p.add_on_ifvg or p.ifvg_ob_add or p.vi_add_early_pts > 0 or p.vi_ob_add)


def add_locations(ctx, sd, pos, tr, i: int, p, arm) -> None:
    """The new add locations of E12 (stops_sizing 1 / 3, models 6 / 7 / 73): at most one add armed on bar i's close; `arm(px, floor=None)` is the caller's arming function (True if armed).
      add_far_edge     001 ~39:05: a limit at the entry FVG's far edge (+ 1 tick, so an exact-tick wick tag fills) while no body has closed under it since the fill
      add_wick_retouch 096 ~9:30: a limit at the wick extreme of the prior retrace (the lowest low since the fill), once per level
      add_htf_fvg_edge 002 ~8:24: a limit at the near edge of the nearest 30m FVG under the price (ctx.conf 30m rows), once per array
      add_on_ifvg      067 ~1:18: an IFVG formed after the fill, a limit at its near edge, once per IFVG
      ifvg_ob_add      067 ~1:19: on an IFVG entry, one add where the IFVG overlaps a reclaimed OB (the overlap's middle)
      vi_add_early_pts 009 ~8:03: a down candle heading to an intact VI under the price - a limit VI top + vi_add_early_pts, filled only on a down bar
      vi_ob_add        009 ~11:15: the down-close candle whose low trades into an intact VI above the entry is a bullish OB - a limit at its MT once a later bar closes above its open"""
    S = _S()
    f = pos["fill_i"]
    c, l, tk = sd.c, sd.l, p.tick
    if p.vi_ob_add and not pos["t1_done"]:
        _vi_ob_add(sd, pos, tr, i, p, arm)
        if pos["add"] is not None:
            return
    if p.vi_add_early_pts > 0:
        _vi_early(sd, pos, i, p, arm)
        if pos["add"] is not None:
            return
    if p.add_on_ifvg:
        used = pos.setdefault("es2_ifvg_used", set())
        zs = [z for z in sd.ifvgs() if f < z.i <= i and z.i not in used and z.bottom > pos["stop"] and z.top < c[i]]
        if zs:
            z = max(zs, key=lambda z: z.top)
            used.add(z.i)
            if arm(float(z.top), floor=float(z.bottom)):
                hit("add_on_ifvg")
                return
    if p.ifvg_ob_add and pos.get("kind") == "ifvg" and not pos.get("es2_ifvg_ob_used"):
        r = _ifvg_ob_overlap(sd, pos, i, p)
        if r is not None:
            pos["es2_ifvg_ob_used"] = True
            if arm(float(r[0]), floor=float(r[1])):
                hit("ifvg_ob_add")
                return
    if p.add_far_edge and not pos.get("es2_far_used"):
        b = float(pos["fvg_bottom"])
        if i > f and b > pos["stop"] and b + tk < c[i] and c[f + 1:i + 1].min(initial=np.inf) >= b - MIN1:
            if arm(b + tk, floor=b):
                pos["es2_far_used"] = True
                hit("add_far_edge")
                return
    if p.add_wick_retouch and i > f:
        wl = float(l[f:i + 1].min())
        used = pos.setdefault("es2_wr_used", set())
        key = round(wl, 6)
        if key not in used and wl > pos["stop"] and wl + 2 * tk < c[i] and l[i] > wl + MIN1:
            used.add(key)
            if arm(wl + tk, floor=wl):
                hit("add_wick_retouch")
                return
    if p.add_htf_fvg_edge and not pos.get("es2_htf_used") and getattr(ctx, "conf", None) is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        zs = []
        for top, bot, tf_, src, known in ctx.conf.valid(now, sd.sign, ("30m",), src=(0,)):
            t_, b_ = (sd.x(top), sd.x(bot)) if sd.sign > 0 else (sd.x(bot), sd.x(top))
            if pos["stop"] < t_ < c[i]:
                zs.append((float(t_), float(b_)))
        if zs:
            t_, b_ = max(zs)
            if arm(t_, floor=b_):
                pos["es2_htf_used"] = True
                hit("add_htf_fvg_edge")


def _ifvg_ob_overlap(sd, pos, i: int, p):
    """models 73: the overlap of the entry IFVG (pos zone: fvg_bottom .. zone_top) and a reclaimed OB (levels.reclaimed_obs via sm2.reclaimed_zones) - (middle, bottom), or None."""
    top = pos.get("zone_top")
    if top is None:
        return None
    bot = float(pos["fvg_bottom"])
    hs = [q for q in sd.ph if q.i < pos["ext_i"] and q.known <= i]
    a = hs[-1].i if hs else max(0, pos["ext_i"] - 30)
    best = None
    for z in sm2.reclaimed_zones(sd, a, pos["ext_i"], i, p):
        lo, hi = max(bot, float(z.bottom)), min(float(top), float(z.top))
        if hi - lo > MIN1 and lo > pos["stop"] and hi < sd.c[i]:
            best = (hi, lo) if best is None or hi > best[0] else best
    if best is None:
        return None
    return ((best[0] + best[1]) / 2, best[1])


def _vi_early(sd, pos, i: int, p, arm) -> None:
    """models 7 (009 ~8:03): "while the candle is going down I buy it ... it may or may not touch the volume imbalance again". The last closed bar is a down candle and an intact VI formed after the fill
    lies under the price: a limit `vi_add_early_pts` above the VI top (a touch of the VI is not required), filled only on a down bar (the bar opens above the limit and trades down into it)."""
    f = pos["fill_i"]
    if not (sd.c[i] < sd.o[i]):
        return
    used = pos.setdefault("es2_vie_used", set())
    best = None
    for z in sd.vis("bull"):
        if z.i <= f + 1 or z.i > i or z.i in used or z.bottom <= pos["stop"]:
            continue
        if sd.c[z.i + 1:i + 1].min(initial=np.inf) < z.bottom:
            continue                                                          # a body closed under it: no longer intact
        px = float(z.top) + p.vi_add_early_pts * p.es_pt
        if px < sd.c[i] and (best is None or px > best[0]):
            best = (px, float(z.bottom), z.i)
    if best is not None:
        used.add(best[2])
        if arm(best[0], floor=best[1]):
            pos["add"]["down_only"] = True
            hit("vi_add_early")


def _vi_ob_add(sd, pos, tr, i: int, p, arm) -> None:
    """models 6 (009 ~11:15, ~13:35): after the first long, with an intact VI formed after the fill ABOVE the entry, the down-close candle whose low trades into the VI (without a body close under its bottom)
    is a bullish order block - a buy limit at that candle's MT (body mean), armed once a later bar has closed above its open [our interpretation: the block is validated, so its MT lies under the market].
    Cancelled on a body close under the VI bottom (a["hold_es2"])."""
    f = pos["fill_i"]
    basis = pos["basis"] / max(pos["n"], 1)
    used = pos.setdefault("es2_viob_used", set())
    c, o, l = sd.c, sd.o, sd.l
    for z in sd.vis("bull"):
        if z.i <= f + 1 or z.i >= i or z.bottom <= basis:
            continue
        if c[z.i + 1:i + 1].min(initial=np.inf) < z.bottom - MIN1:
            continue
        for k in range(z.i + 1, i):
            if k in used or not c[k] < o[k] or not l[k] <= z.top + MIN1 or l[k] < z.bottom - MIN1:
                continue
            mt = float((o[k] + c[k]) / 2)
            if c[k + 1:i + 1].max(initial=-np.inf) > o[k] and mt < c[i] and mt > pos["stop"]:
                used.add(k)
                if arm(mt, floor=float(z.bottom)):
                    pos["add"]["hold_es2"] = float(z.bottom)
                    hit("vi_ob_add")
                    return


def vi_ob_cand(sd, sw, i: int, p):
    """models 6, standalone (vi_ob_entry): after the MSS, the same pattern as an entry array - (entry, bottom, "vi_ob"): the MT of a down-close pullback candle (formed after the VI) that traded into an
    intact VI of the displacement leg, a later bar closing above its open; the stop under the VI bottom (setups.array_order: bottom - pad)."""
    c, o, l = sd.c, sd.o, sd.l
    best = None
    for z in sd.vis("bull"):
        if z.i <= sw["ext_i"] + 1 or z.i >= i or c[z.i + 1:i + 1].min(initial=np.inf) < z.bottom - MIN1:
            continue
        for k in range(z.i + 1, i):
            if not c[k] < o[k] or not l[k] <= z.top + MIN1 or l[k] < z.bottom - MIN1:
                continue
            mt = float((o[k] + c[k]) / 2)
            if c[k + 1:i + 1].max(initial=-np.inf) > o[k] and mt < c[i] and mt > z.bottom:
                if best is None or mt > best[0]:
                    best = (mt, float(z.bottom), "vi_ob")
    if best is not None:
        hit("vi_ob_cand")
    return best


# post-partial adds (stops_sizing 6) ------------------------------------------------------------------------------------------------------------

def _median_range(ctx, n: int = 20):
    h = getattr(ctx, "hist", None) or []
    r = [float(x.high.max() - x.low.min()) for x in h[-n:]]
    return float(np.median(r)) if r else None


def post_partial_add(ctx, sd, pos, tr, i: int, p, arm_sized) -> None:
    """stops_sizing 6: after the first partial one small add (add_after_partial), once per trade (pos["post_partial_adds"]):
      "inv_fvg"  071 ~15:58: an opposing FVG (side space: a bear gap) that price closed through after the fill; a limit at its near edge (its top) on the retrace - size min(smallest earlier unit, partial units)
      "high_vol" 092 ~1:30: any new same-side FVG while ADR5 > add_hv_mult x the median of the last 20 daily ranges - the units taken as partials come back [our interpretation of high volatility]
    The trailed stop must hold (the limit must lie above it); `arm_sized(px, size, floor)` applies add_ok and the 1.3 % cap shrink."""
    S = _S()
    if pos.get("post_partial_adds", 0) >= 1 or pos["add"] is not None or not pos["t1_done"] or pos["left"] <= 0:
        return
    f = pos["fill_i"]
    part = int(sum(q for *_, q, r in tr.exits if str(r).startswith("t")))
    if part < 1:
        return
    earlier = [tr.shares] + [q for _, _, q in tr.adds[pos.get("rung_fills", 0):]]
    if p.add_after_partial == "inv_fvg":
        cands = []
        for g in sd.opposing():
            if g.i > i or g.i <= f - 3:
                continue
            if sd.c[max(f + 1, g.i + 1):i + 1].max(initial=-np.inf) > g.top and sd.c[i] > g.top + p.tick:
                cands.append(g)
        if not cands:
            return
        g = max(cands, key=lambda g: g.top)
        px, size, fl = float(g.top), min(min(earlier), part), float(g.bottom)
    else:
        a5 = S.adr5(getattr(ctx, "hist", [])[-5:])
        med = _median_range(ctx)
        if not a5 or not med or not a5 > p.add_hv_mult * med:
            return
        new = [g for g in sd.gaps if g.i == i and g.i - 2 > f]
        if not new:
            return
        g = new[-1]
        px, size, fl = float(S._EN.add_px(g, p)), part, float(g.bottom)
    if not (pos["stop"] < px < sd.c[i]):
        return
    pos["post_partial_adds"] = pos.get("post_partial_adds", 0) + 1
    if arm_sized(px, int(size), fl):
        pos["add"]["post_partial"] = True
        hit("add_after_partial_" + p.add_after_partial)


# add gates (stops_sizing 8 / 9) ------------------------------------------------------------------------------------------------------------------

def form_eq_ok(sd, pos, px: float, form, p) -> bool:
    """stops_sizing 8 (025 ~48:05; 092 ~1:16:43): an add array must have FORMED at or beyond the EQ of the implied range H .. T on H's side. Side space: H = the sweep extreme (the leg's low), T = the locked draw
    (pos["draw"], else the last ladder level); `form` = the array's formation price (an FVG: its edge nearer H = its bottom; an OB: its body bottom), default the add price [our interpretation]. An array formed on
    the T side of EQ is only a calibration check: rejected as an add and counted on the trade (pos["es2_cal"])."""
    if not p.add_form_eq:
        return True
    leg = pos.get("leg")
    t_ = pos.get("draw")
    if t_ is None and pos.get("levels"):
        t_ = pos["levels"][-1]
    if not leg or t_ is None:
        return True
    h_ = float(leg[0])
    if not t_ > h_:
        return True
    eq = (h_ + float(t_)) / 2
    fp = float(px if form is None else form)
    if fp > eq + MIN1:
        pos["es2_cal"] = pos.get("es2_cal", 0) + 1
        hit("add_form_eq_cal")
        return False
    return True


def trend_day_update(ctx, sd, pos, i: int, p) -> None:
    """stops_sizing 9 (038 ~1:15:27): add_day_mode "trend_day" - a clean trending day lets adds continue until the far extreme of the daily range. Classifier [our interpretation]: no FOMC / CPI / jobs release
    today, and price >= trend_day_adr x ADR5 away from the 09:30 open (in the trade's direction) without having traded back through the open. Sets pos["td_ok"] (the add cuts are waived) and
    pos["td_block"] (price within 0.1 x ADR5 of the previous day's extreme in the trade's direction: no more adds)."""
    S = _S()
    pos["td_ok"] = pos["td_block"] = False
    if S.events(ctx.day) & {"fomc", "cpi", "jobs"}:
        return
    o930 = S._open_known(ctx, "0930", i)
    a5 = S.adr5(getattr(ctx, "hist", [])[-5:])
    if o930 is None or not a5:
        return
    open_s = float(sd.x(o930))
    k0 = S._idx_at(ctx, 570)
    if not sd.c[i] - open_s >= p.trend_day_adr * a5 or sd.l[k0:i + 1].min() < open_s - MIN1:
        return
    pos["td_ok"] = True
    hs = getattr(ctx, "hist", None) or []
    if hs:
        far = float(sd.x(hs[-1].high.max() if sd.sign > 0 else hs[-1].low.min()))
        if sd.c[i] >= far - 0.1 * a5:
            pos["td_block"] = True
            hit("trend_day_far")
    hit("trend_day_adds")


# --- 2. order blocks (A12) ------------------------------------------------------------------------------------------------------------------------

SESSION_LOW_KEYS = ("london", "prev_london", "prev_pm", "am_session", "lunch", "overnight")


def ob_session_ok(ctx, sd, sw, ob: dict, p) -> bool:
    """definitions 146 (cc03_003 ~41:41: "every order block that we refer to here is linked to a london session or a new york session"): the OB candle lies in a London (02:00-05:00) or New York
    (07:00-11:00 ET) window [our interpretation: ob_session_windows], or the setup is a run below a prior London / NY session low (the sweep key)."""
    if not p.ob_session_filter:
        return True
    t = int(ctx.t[int(ob["k"])])
    ok = any(a <= t < b for a, b in p.ob_session_windows) or str(sw.get("key", "")) in SESSION_LOW_KEYS
    hit("ob_session_ok" if ok else "ob_session_skip")
    return ok


def ob_mt_dead(sd, ob_k: int, mt: float, i: int) -> bool:
    """definitions 190 (cc09_008 ~14:37: "it's already worked on both sides of that"): after the OB's last candle `ob_k` price has traded on BOTH sides of its MT - a bar entirely above it (the OB was left)
    and later a bar trading under it (the retest), or a bar entirely under it and later a bar trading over it - the MT is no level any more (the stop falls back to the OB low). A fresh OB that has only been
    left upward is alive."""
    if i <= ob_k:
        return False
    lows, highs = sd.l[ob_k + 1:i + 1], sd.h[ob_k + 1:i + 1]
    up = np.flatnonzero(lows > mt + MIN1)
    if len(up) and bool((lows[up[0] + 1:] < mt - MIN1).any()):
        return True
    dn = np.flatnonzero(highs < mt - MIN1)
    return bool(len(dn) and (highs[dn[0] + 1:] > mt + MIN1).any())


def ob_swept_entry(sd, ob: dict, p) -> float | None:
    """definitions 120 (cc04_003 ~32:47): the OB candle was itself a run on sell stops (its low under the latest confirmed pivot low before it) - a shallower retrace is expected: buy at the candle's body MT
    (open + close) / 2 instead of the open. None = not swept (the caller keeps its price)."""
    if not p.ob_mt_if_swept:
        return None
    k = int(ob["k"])
    prior = [q for q in sd.pl if q.known < k and q.i < k]
    if not prior:
        return None
    q = max(prior, key=lambda q: q.i)
    if sd.l[k] < q.price - MIN1:
        hit("ob_mt_if_swept")
        return float((sd.o[k] + sd.c[k]) / 2)
    return None


def ob_grade_tags(ob: dict) -> dict:
    """definitions 151: the OB's MT and body height, stored with the order for the fill-time grade."""
    return dict(ob_mt=float(ob["mt"]), ob_body=float(max(ob["body_top"] - ob["body_low"], 1e-9)))


def ob_grade(st: dict, low: float, close: float, p) -> str:
    """definitions 151 (cc04_003 ~9:59 / ~10:35 / ~24:21: "the best order blocks will not see price trade down below the midway point"): A = the retest low at or above the MT; B = slightly under it (at most
    ob_grade_tol x the body height) with no body close under it; X = a body close under the MT or the tolerance exceeded."""
    mt, body = st["ob_mt"], st["ob_body"]
    if low >= mt - MIN1:
        return "A"
    if close >= mt - MIN1 and mt - low <= p.ob_grade_tol * body + MIN1:
        return "B"
    return "X"


# --- 3. entry gaps and prices (E1 / E2 / A5) ------------------------------------------------------------------------------------------------------

def min_tf_gaps(ctx, sd, sw, i: int, p) -> list | None:
    """definitions 186 (cc12_004 ~5:00: "15 minute minimum, the best is to get it down until five minute"): entry_fvg_min_tf = m > the base bar size: the entry FVGs are those of the m-minute bars built from
    the base bars (formed after the sweep, complete by bar i, not closed through). None = the switch does not apply (m <= the base bars or not a multiple of them)."""
    m = int(p.entry_fvg_min_tf)
    if m <= ctx.tf or m % ctx.tf:
        return None
    from . import sm4
    hit("entry_fvg_min_tf")
    return [z for z in sm4._tf_fvgs(ctx, sd, m) if z.i <= i and z.src > sw["ext_i"] and sm4._alive(sd, z, i)]


def vi_first_pick(ctx, sd, sw, i: int, p):
    """models 27 (025 ~00:49:04; 026 ~01:36:42): after the MSS, a VI of the displacement leg at or beyond the leg EQ on the entry side (side space: its top at or under EQ + eq_tol) is the entry zone
    (the highest one: nearest the market); None = no such VI, the FVG pick stands. EQ = the sweep extreme .. the leg high."""
    S = _S()
    e = sw["ext_i"]
    eq = (float(sw["ext"]) + float(sd.h[e:i + 1].max())) / 2
    best = None
    for z in sd.vis("bull"):
        if not (e < z.i <= i) or z.top > eq + _tol(p):
            continue
        if p.vi_body_death and not S._vi_alive(sd, z, i):
            continue
        if best is None or z.top > best.top:
            best = z
    if best is not None:
        hit("vi_first")
    return best


def close_prox_pick(ctx, sd, sw, gaps: list, i: int, p, session: str):
    """models 24 (022 ~03:08:33: "close proximity entries - you don't need a breaker"): inside a macro window (close_prox_windows, default 10:50-11:10) and with a session lock (a draw named), after the MSS the
    pick is the VI / FVG created by the shift that lies NEAREST the market (the highest top under the close), the limit at its near edge; the leg-EQ (M2) filter is not applied. None = not active."""
    if not any(a <= int(ctx.t[i]) < b for a, b in p.close_prox_windows):
        return None
    lk = getattr(ctx, "cur_lock", None)
    if lk is None or not lk.get("side"):
        return None
    cands = [g for g in gaps if g.top < sd.c[i]]
    cands += [z for z in sd.vis("bull") if sw["ext_i"] < z.i <= i and z.top < sd.c[i]]
    if not cands:
        return None
    hit("close_proximity")
    return max(cands, key=lambda z: (z.top, z.i))


def wick_ce_refine(ctx, sd, sw, g, top: float, bottom: float, i: int, p) -> float | None:
    """models 29 (025 ~01:08:00: "extend it through this fair value gap and you'll get the very tick high"): the wicks (upper or lower) of the last wick_ce_lookback bars before the leg (the same day) whose
    CE lies inside the gap [bottom, top]: the limit = the highest such CE + 1 tick (market side, so a tick-exact touch fills under E3), clipped to the gap top. None = none."""
    a = max(ctx.start, int(sw.get("ref_i", sw["ext_i"])) - p.wick_ce_lookback)
    b = int(sw.get("ref_i", sw["ext_i"]))
    if b <= a:
        return None
    o, h, l, c = sd.o[a:b], sd.h[a:b], sd.l[a:b], sd.c[a:b]
    bt, bb = np.maximum(o, c), np.minimum(o, c)
    ces = np.concatenate([(bt + h) / 2, (bb + l) / 2])
    ok = ces[(ces >= bottom - MIN1) & (ces <= top + MIN1)]
    if not len(ok):
        return None
    hit("wick_ce_refine")
    return float(min(float(ok.max()) + p.tick, top))


def second_gap_near(sd, g, i: int, p) -> bool:
    """models 82 (074 ~00:36:02: "that's what makes this an institutional referential"): another same-side gap of the move within iofed_gap_bars bars of the picked gap and iofed_gap_pts beyond its far side
    (side space: above the picked gap's top) - then only an IOFED touch of the near edge is expected."""
    for z in sd.gaps:
        if z is g or z.i > i or abs(z.i - g.i) > p.iofed_gap_bars:
            continue
        d = float(z.bottom) - float(g.top)
        if -MIN1 <= d <= p.iofed_gap_pts * p.es_pt + MIN1:
            return True
    return False


def far_on_breaker_stop(ctx, sd, sw, g, bz, coarse: bool, i: int, p):
    """models 18 (018 ~00:00:09: "if I can touch the bottom end down here I'm gonna buy that"): a 5m gap that overlaps the breaker zone or a same-side VI (formed after the sweep) is entered at its FAR edge
    + 1 tick; the stop under the bottom of the overlapped breaker / VI. Returns (entry, stop) or None."""
    five = ctx.tf == 5 or coarse
    if not five or g.mt == g.mt:
        return None
    lows = []
    if bz is not None and g.overlaps(bz):
        lows.append(float(bz.bottom))
    for z in sd.vis("bull"):
        if sw["ext_i"] <= z.i <= i and g.overlaps(z):
            lows.append(float(z.bottom))
    if not lows:
        return None
    hit("far_on_breaker")
    return float(g.bottom) + p.tick, min(lows) - p.pad


def fri_shallow_pick(ctx, sd, sw, gaps: list, i: int, p):
    """management 129 (070 ~00:47:11: "it's really close to that June 16th high anyway so we don't want to see any deep retracements"): on a Friday with the price closer to the HTF draw than the A-B leg is
    tall (draw proxy: the session's locked draw; leg: the sweep extreme .. the highest high since), the first FVG of the leg is entered at its near edge - no deep retrace, no breaker MT. None = not active."""
    if ctx.day.weekday() != 4:
        return None
    lk = getattr(ctx, "cur_lock", None)
    if lk is None or not lk.get("side"):
        return None
    leg = float(sd.h[sw["ext_i"]:i + 1].max() - sw["ext"])
    draw = float(sd.x(lk["target"]))
    if leg <= 0 or not 0 < draw - float(sd.c[i]) < leg:
        return None
    g = min(gaps, key=lambda z: z.i, default=None)
    if g is not None:
        hit("fri_shallow")
    return g


def convert_pending(o: dict, sd, i: int) -> dict:
    """models 92 (089 ~00:04:20: "here's the market trade up into the fair value gap here I marketed in") / models 52 (049 ~00:05:01): at the start of bar i (bars through i-1 are closed) a pending order that
    (a) is a market_on_touch order (`mot`) and whose level the bar BEFORE touched (no trade through needed) or (b) is a breakaway-chase order unfilled for more than `chase_bars` bars becomes a MARKET
    order: it fills at bar i's open."""
    if o.get("market") or i - 1 <= o["i"]:
        return o
    if o.get("mot") and sd.l[i - 1] <= o["entry"] + 1e-12:
        hit("mot_market")
        return dict(o, market=True)
    if o.get("chase_bars") is not None and i - o["i"] > o["chase_bars"]:
        hit("chase_market")
        return dict(o, market=True)
    return o


def wick_redelivery(sd, i: int) -> bool:
    """models 30 (026 ~01:57:39: "it doesn't need to close with an up candle if it was a recent down closed candle"): the fill bar trades across the full range of the most recent opposite-colour candle (side
    space: down through the low of the last up-close candle) - the redelivery counts whatever the colour of the fill bar."""
    for k in range(i - 1, max(-1, i - 60), -1):
        if sd.c[k] > sd.o[k]:
            return bool(sd.l[i] <= sd.l[k] + MIN1)
    return False


# --- 4. stops (A11 / E6 / A13 / E6d) ---------------------------------------------------------------------------------------------------------------

def bpr_stop(sd, g, i: int, p) -> float | None:
    """levels 10 (026 ~00:59:14: "what's the midpoint ... for that balanced price range"): a BPR directly beyond the entry gap's far edge (its near edge within bpr_adj_pts of the gap's far edge) caps the
    expected overshoot at the BPR's MT: the stop = BPR MT - pad (side space). None = no such BPR."""
    best = None
    for z in sd.bprs(p.bpr_max_gap_bars):
        if z.i > i:
            continue
        d = float(g.bottom) - float(z.top)
        if -MIN1 <= d <= p.bpr_adj_pts * p.es_pt + MIN1:
            if best is None or z.top > best.top:
                best = z
    if best is None:
        return None
    hit("stop_bpr_mt")
    return float(best.mid) - p.pad


def wick_ce_of(sd, g, p):
    """levels 90 (075 ~01:04:11: "it's likely to go into this consequent encroachment not just filled in that gap"): the entry FVG's first candle has a long lower wick (wick >= body): (wick CE, wick low)."""
    k = g.i - 2
    if k < 0:
        return None
    bb = float(min(sd.o[k], sd.c[k]))
    body = abs(float(sd.c[k]) - float(sd.o[k]))
    wick = bb - float(sd.l[k])
    if wick <= MIN1 or wick < body - MIN1:
        return None
    return (bb + float(sd.l[k])) / 2, float(sd.l[k])


def higher_array(ctx, sd, bz, i: int, p):
    """management 105 (081 ~00:14:11: "give it permission ... to trade just outside"): a same-polarity OB / FVG within bz_higher_pts beyond the breaker's far edge (side space: its top within that distance
    under the breaker bottom): its far edge (bottom) is the stop level / the abort level of the breaker trade. Intraday FVGs and the Confluence HTF arrays count; None = none."""
    S = _S()
    lo, hi = float(bz.bottom) - p.bz_higher_pts * p.es_pt, float(bz.bottom) + MIN1
    best = None
    for g in sd.gaps:
        if g.i <= i and lo - MIN1 <= g.top <= hi and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1:
            if best is None or g.top > best[0]:
                best = (float(g.top), float(g.bottom))
    if getattr(ctx, "conf", None) is not None:
        kb = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        for top, bot, _ in S._ts_arrays(ctx, sd, i, kb):
            if lo - MIN1 <= top <= hi and (best is None or top > best[0]):
                best = (float(top), float(bot))
    if best is None:
        return None
    hit("bz_higher_array")
    return best[1]


def gap_risk_adjust(ctx, sd, sw, i: int, p, entry: float, stop: float):
    """definitions 154 (cc04_002 ~1:41: "liquidity voids will fill in and this is associated with gap risk"): in a CONSOLIDATION (delivery state: no displacement beyond the range) an unfilled FVG between the
    entry and the stop - or within gap_risk_near_pts under the stop - will likely fill: "widen" puts the stop under it, "skip" drops the order. Returns the stop, or None (skip)."""
    if p.gap_risk == "off" or sm2.state_at(ctx, i, p) != "CONSOLIDATION":
        return stop
    near = p.gap_risk_near_pts * p.es_pt
    low = None
    for g in sd.gaps:
        if g.i > i or g.top >= entry - MIN1:
            continue                                       # the entry gap itself (or one above the entry) is not a risk gap
        if sd.l[g.i + 1:i + 1].min(initial=np.inf) <= g.bottom + MIN1:
            continue                                       # already filled
        if g.top >= stop - near - MIN1 and g.bottom < entry:
            low = g.bottom if low is None else min(low, g.bottom)
    if low is None:
        return stop
    hit("gap_risk_" + p.gap_risk)
    if p.gap_risk == "skip":
        return None
    return min(stop, low - p.pad)


# --- 5. the order gate (tags / multipliers) ---------------------------------------------------------------------------------------------------------

def any_gate_es2(p) -> bool:
    return bool(p.rb_ctx_mult != 1.0)


def order_gate_es2(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, cf, htf, lvt: list, tags: dict):
    """The multipliers of the chunk: definitions 155 (cc04_006 ~5:14: "the ideal setups are found in major to intermediate term downtrends") - a rejection-block entry is graded lower (half size by default
    [our interpretation]) unless the bias is this way AND the swing sits at an HTF array. Returns a reject key or None."""
    S = _S()
    mult = 1.0
    if p.rb_ctx_mult != 1.0 and S._LD4.is_rb_key(sw.get("key")):
        at_htf = bool(htf or (cf is not None and S._htf_array(cf, p)))
        if not (getattr(ctx, "cur_bias", 0) == sd.sign and at_htf):
            mult *= p.rb_ctx_mult
            lvt.append("rb_ctx_lower")
            hit("rb_ctx_lower")
        else:
            lvt.append("rb_ctx_ideal")
    if mult != 1.0:
        tags["es2_mult"] = float(tags.get("es2_mult", 1.0)) * mult
    return None


# --- 6. position hooks ---------------------------------------------------------------------------------------------------------------------------------

def rescale(pos, tr, fill: float, mult: float, p) -> int:
    """Scale the just-filled position by `mult` (the OB grade), in whole lots; returns the new size."""
    S = _S()
    q0 = pos["n"]
    q = max(max(p.lot, 1), S._lots(q0 * mult, p.lot))
    if q == q0:
        return q0
    pos["n"] = pos["left"] = q
    pos["basis"] = fill * q
    pos["plan_shares"] = max(q, int(round((pos.get("plan_shares") or q0) * q / q0)))
    tr.shares = q
    return q


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p, fill: float) -> None:
    """Fill-time hooks of the chunk's orders (pos["es2"]): the OB grade (151), the FVG-then-OB add (38), the zone-ladder add base (4)."""
    S = _S()
    st = dict(o.get("es2") or {})
    pos["es2"] = st
    if st.get("ob_mt") is not None and p.ob_grade_mult != (1.0, 1.0):
        gr = ob_grade(st, float(sd.l[i]), float(sd.c[i]), p)
        tr.lv_tags = "|".join(x for x in (tr.lv_tags, "ob_grade_" + gr) if x)
        hit("ob_grade_" + gr)
        if gr in ("A", "B"):
            m = p.ob_grade_mult[0 if gr == "A" else 1]
            if m != 1.0:
                q0 = pos["n"]
                if rescale(pos, tr, fill, m, p) != q0:
                    tr.entry_risk_pct = round(pos["n"] * (fill - o["stop"]) / ctx.equity, 5) if ctx.equity else tr.entry_risk_pct
                    tr.peak_risk_pct = tr.entry_risk_pct
    if st.get("then_ob") is not None:
        px, fl = st["then_ob"]
        if pos["stop"] < px < fill - MIN1 and S._SM.add_ok(sd, pos, px, i, p):
            S._arm_add(pos, tr, px, i, p, ctx.equity, floor=fl)
            if pos["add"] is not None:
                hit("fvg_then_ob_add")
    if st.get("add_base") is not None:
        pos["add_base"] = int(st["add_base"])
