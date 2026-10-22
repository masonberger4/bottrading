"""Package management_exits (rule_coverage.md section 3 "management_exits"; build_log.md).

Mid-trade management, session / day / week stops and the add rules of the X4-X16 / D14 / D18 / M2.6 /
Ep03-Ep07 items, called from strategy.run_day (the position loop, `_after_close`, the scan guards) and
from sb_model / pre_open (the day-level stops, the time stop and the breakeven rule). Everything runs in
SIDE SPACE (bullish terms; a short is the mirrored prices of strategy.Side), reads only bars that have
closed (index <= the caller's bar i) and every rule is a Params switch. Thresholds ICT never gives are
marked [our interpretation].

Exits decided on a closed bar are market-on-close exits at that bar's close (like ce_close / htf_heavy /
lvx exits); a limit-type exit (the objective, the re-entry target) fills at its price once the bar's high
reaches it. They use no data past that close [documented].

Pieces
  be_stop / be_modes        X4 / D14 / Ep03.15   breakeven level with a pad; after_mss / stall / pool modes
  trail_extra               X5 / X5a / Ep03.10 / Ep03.20  measuring-gap and first-FVG trails
  init_pos                  the per-position data fixed at the fill (arrays, leg MT, offside level, ...)
  exits                     X6 .. X12 / D18 / Ep07.5 / X10b-c / X11c  the mid-trade exits (one call per bar)
  time_stop_frac            X9 / X9a / X9d  shared by the main engine, the Silver Bullet and Ma Deuce
  stops_from                X7c / X12 / X13a / X14b / X14d / Ep04.13  session and day stops from closed trades
  reentry_*                 X13b / D18  the gate and the sizing of a re-entry
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from claude_hf.daytypes import events
from . import levels as L
from . import strategy as S

POOL_KINDS = ("pool", "pool_eq")
# exits that mean "the idea failed" (X7c session_fail_mode="arrays")
FAIL_REASONS = {"stop", "stop_gap", "abort", "pd3", "ce_close", "breaker_mt", "body_low", "first_fvg_fail",
                "leg_mt", "ir_eq", "offside", "meander", "far_edge", "prop_mt", "q_close", "wick_inv", "bpr_abort",
                "po3_hold", "release_open", "breakaway_ce"}


def _lots(x: float, p) -> int:
    return S._lots(x, p.lot)


def cut_qty(left: int, frac: float, p) -> int:
    """Units to take off `left` for a fraction `frac`; a remainder under the minimum size is closed too
    (X9d "at minimum size, close")."""
    if frac >= 1.0:
        return left
    q = min(left, max(p.lot, _lots(left * frac, p)))
    if left - q < max(p.lot, 1):
        return left
    return q


def _exit(tr, sd, ts, px, q, reason, pos):
    tr.exits.append((ts, sd.x(px), q, reason))
    pos["left"] -= q


# --- breakeven (X4 / D14 / Ep03.15) ----------------------------------------------------------------------

def be_stop(pos_or_entry, p, n=None) -> float:
    """X4: the breakeven stop (side space) = average entry + be_pad_pts + (be_cost_pad) the round-trip cost per
    unit (105 ~10:41 "BE + commissions + a little"). `pos_or_entry` is a position dict (basis / n) or a price."""
    px = pos_or_entry["basis"] / pos_or_entry["n"] if isinstance(pos_or_entry, dict) else float(pos_or_entry)
    return px + p.be_pad_pts * p.es_pt + (2.0 * p.cost_per_share if p.be_cost_pad else 0.0)


def raise_stop(pos, new: float) -> None:
    """The ONE place a trail / lock / tighten lifts a position's stop (side space, never down). A day trade (X5c
    trade_type="day", 064 ~1:38:44) keeps its initial stop: no trail, no breakeven, nothing raises it."""
    if pos.get("day_trade"):
        return
    pos["stop"] = max(pos["stop"], new)


def be_move(pos, p) -> None:
    """Move the stop to breakeven (never down, never on a day trade: X5c)."""
    if pos.get("day_trade"):
        return
    pos["stop"] = max(pos["stop"], be_stop(pos, p))


def be_modes(sd, pos, tr, i: int, p, mode=None) -> None:
    """D14 / Ep03.15 be_on modes that are not tied to the first partial (called once per bar, after the bar's
    stop and ladder tests; a move applies from the next bar):
      after_mss  (003 ~40:15, 042) a close above the leg high (the short-term high the shift took) after the fill
      stall      (009 ~09:46) be_stall_bars closed bars in a row without a new high once the trade was at least
                 be_stall_min_r in profit [our interpretation of "when price stalls"]
      pool       (Ep03.15, Ep 03 "breakeven after buy-side is run") the high reaches the first liquidity pool of the
                 ladder - the pool levels are carried from the fill whatever rungs were taken; no pool in the ladder:
                 the default (expansion) rule"""
    mode = mode or p.be_on
    if mode not in ("after_mss", "stall", "pool") or pos.get("be_done") or pos.get("day_trade") or not pos["left"]:
        return
    h, c = sd.h[i], sd.c[i]
    if i <= pos["fill_i"]:
        return
    if mode == "after_mss":
        leg = pos.get("leg")
        if leg and c > leg[1]:
            be_move(pos, p)
            pos["be_done"] = True
    elif mode == "stall":
        best = pos.get("stall_best", -np.inf)
        if h > best + 1e-9:
            pos["stall_best"], pos["stall_n"] = float(h), 0
        else:
            pos["stall_n"] = pos.get("stall_n", 0) + 1
        risk = abs(tr.entry - tr.stop)
        basis = pos["basis"] / pos["n"]
        if risk > 0 and pos["stall_best"] - basis >= p.be_stall_min_r * risk and pos["stall_n"] >= p.be_stall_bars:
            be_move(pos, p)
            pos["be_done"] = True
    elif mode == "pool":
        pools = pos.get("pool_levels")
        if pools:
            if h >= min(pools):
                be_move(pos, p)
                pos["be_done"] = True
        elif pos["t1_done"] and pos["last_partial_i"] < i and c > pos["levels"][0]:
            be_move(pos, p)                       # no pool in the ladder: the expansion rule
            pos["be_done"] = True


# --- trailing (X5 / X5a / Ep03.10 / Ep03.20) ----------------------------------------------------------------

def first_fvg(sd, ext_i: int, i: int):
    """The first FVG made after the sweep extreme and known by bar i (the shift's gap)."""
    return next((g for g in sd.gaps if g.i - 2 >= ext_i and g.i <= i), None)


def trail_extra(sd, pos, i: int, p) -> None:
    """Trail variants decided on bar i's close (applies from bar i+1):
      trail_first_fvg   Ep03.10 / X5 (003 ~42:40; 062 ~37:02): the stop goes under the FIRST FVG after the shift once
                        a close is above its top and no body has closed below its bottom (it still "holds")
      ladder_trail "measuring"  Ep03.20 / X5a (003 ~1:05:10): after trail_after rounds of partials the stop goes under
                        the measuring gap (the FVG in the middle of the leg, targets.measuring_gap) once price is above it
      ladder_trail "breakaway"  X5a (003 ~42:40; 062 ~37:02): the same rounds gate, the stop under the breakaway gap
                        (targets.breakaway_gap: the shift's FVG while price has not retraced past its half)"""
    if pos.get("day_trade") or not pos["left"]:
        return
    c = sd.c[i]
    if p.trail_first_fvg:
        g = first_fvg(sd, pos["ext_i"], i)
        if g is not None and c > g.top and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom:
            from . import ld3 as _L3                         # caption-gap A6 trail_skip_common
            if _L3.trail_ok(sd, pos, g, i, p):
                raise_stop(pos, g.bottom - p.trail_pad)
    if p.mgmt in ("ladder", "unit") and p.ladder_trail == "breakaway" and pos["k"] >= p.trail_after:
        from . import targets as _TP
        g = _TP.breakaway_gap(sd, pos["ext_i"], i, p)       # A6: the shift's gap while price has not retraced past its half (bk_depth / bk_state)
        if g is not None and c > g.top:
            raise_stop(pos, g.bottom - p.trail_pad)
    if p.mgmt in ("ladder", "unit") and p.ladder_trail == "measuring" and pos["k"] >= p.trail_after:
        from . import targets as _TP
        leg = pos.get("leg")
        hi = leg[1] if leg else float(sd.h[pos["ext_i"]:i + 1].max())
        hi = max(hi, float(sd.h[pos["ext_i"]:i + 1].max()))
        g = _TP.measuring_gap(sd, dict(ext=pos["ext"], ext_i=pos["ext_i"]), i, hi, p)
        if g is not None and c > g.top:
            raise_stop(pos, g.bottom - p.trail_pad)


# --- per-position data fixed at the fill ----------------------------------------------------------------------

def _arrays(sd, pos, known: int, p, ref: float, stop: float, kinds) -> list:
    """X7a: the PD arrays under `ref` and over the stop, known by bar `known`, as (level a body must close below,
    kind): FVG bottoms, VI bottoms, order-block MTs, breaker MTs. Nearest (highest) first, duplicates merged."""
    out = []
    tk = p.tick
    if "fvg" in kinds:
        for g in sd.gaps:
            if g.i <= known and stop < g.bottom < ref:
                out.append((float(g.bottom), "fvg"))
    if "vi" in kinds:
        for z in sd.vis("bull"):
            if z.i <= known and stop < z.bottom < ref:
                out.append((float(z.bottom), "vi"))
    if "ob" in kinds:
        for g in sd.gaps:
            if g.i > known:
                break
            if g.i < 4:
                continue
            ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, g.i - 4, g.i - 2, "bull")
            if ob is not None and sd.c[g.i - 1] > ob.top and np.isfinite(ob.mt) and stop < ob.mt < ref:
                out.append((float(ob.mt), "ob"))
    if "breaker" in kinds:
        for z in S._SM._breakers(sd, p):
            if z.i <= known:
                th = z.mt if np.isfinite(z.mt) else z.bottom
                if stop < th < ref:
                    out.append((float(th), "breaker"))
        if pos.get("bz_mt") is not None and stop < pos["bz_mt"] < ref:
            out.append((float(pos["bz_mt"]), "breaker"))
    ek = str(pos.get("kind") or "")
    if ek.startswith("ob"):
        if "ob" in kinds and stop < pos["fvg_ce"] < ref:
            out.append((float(pos["fvg_ce"]), "ob"))                 # the entry array is an order block: its MT
    elif ek != "breaker" and "fvg" in kinds and stop < pos["fvg_bottom"] < ref:
        out.append((float(pos["fvg_bottom"]), "fvg"))                # the entry array (an FVG / unicorn / other zone)
    out.sort(key=lambda x: -x[0])
    merged = []
    for lv, kd in out:
        if merged and abs(merged[-1][0] - lv) <= tk:
            continue
        merged.append((lv, kd))
    return merged


def _leg_candle(sd, ext_i: int, end: int):
    """X8b: the up-close candle that started the leg = the first up-close candle at or after the sweep extreme
    (bars < end). None until one has closed."""
    for k in range(ext_i, end):
        if sd.c[k] > sd.o[k]:
            return k
    return None


def init_pos(ctx, sd, pos, tr, o: dict, i: int, p, state=None) -> None:
    """Called when the pending order fills on bar i (side space): store what the exits need, fixed at the fill."""
    fill_px = pos["basis"] / pos["n"]
    kinds = pos.get("level_kinds") or []
    pos["day_trade"] = bool(o.get("day_trade"))
    pos["pool_levels"] = [v for v, k in zip(pos["levels"], kinds) if k in POOL_KINDS]
    zt = pos.get("zone_top")
    pos["fvg_top"] = float(zt) if zt is not None else 2 * pos["fvg_ce"] - pos["fvg_bottom"]
    pos["smt_tag"] = tr.smt is True
    pos["done_key"] = o.get("done_key", o["session"])
    pos["stop0"] = float(pos["stop"])
    pos["fill_px"] = float(fill_px)
    if pos.get("leg"):
        ext, hi = pos["leg"]
        # M2.6: the leg the ADD rules measure (add_cutoff / add_cut / add_in_pd / add_leg_cut) is FIXED at the fill; it is
        # its own field, so the other leg readers (be_on after_mss, leg MT, IR EQ, time stop leg_high) never see it
        pos["leg_fill"] = ((ext, max(float(hi), float(sd.h[o["ext_i"]:i + 1].max()))) if p.add_leg_at_fill
                           else (ext, hi))
    if p.pd3_exit and not p.pd3_legacy:
        pos["pd3"] = _arrays(sd, pos, i - 1, p, fill_px, pos["stop0"], p.pd3_list)[:p.pd3_n]    # the NEAREST pd3_n, fixed
        pos["pd3_broken"] = set()
        if not p.pd3_dynamic:                       # audit tag: how many arrays the fixed list holds ("pd3_short" = fewer
            add_ = [f"pd3_n{len(pos['pd3'])}"] + (["pd3_short"] if len(pos["pd3"]) < p.pd3_n else [])   # than pd3_n: never fires)
            tr.lv_tags = "|".join(x for x in [tr.lv_tags] + add_ if x)
    if p.pd3_half:
        three = []
        for kd in ("vi", "fvg", "ob"):
            a = [x for x in _arrays(sd, pos, i - 1, p, fill_px, pos["stop0"], (kd,)) if x[1] == kd]
            three.append(a[0][0] if a else None)
        pos["pd3_half_lv"] = None if None in three else min(three)
    if p.ir_eq_exit and tr.imm_rebal and pos.get("leg"):
        ext, hi = pos["leg"]
        eq = ext + 0.5 * (hi - ext)
        pos["ir_eq"] = float(eq) if fill_px > eq else None          # only an entry above the range EQ can lose it
    if p.offside_exit:
        cands = [k for k in range(max(0, o["ext_i"] - 12), i) if sd.c[k] > sd.o[k] and sd.o[k] > fill_px]
        if cands:
            k = min(cands, key=lambda k: sd.o[k])                   # the nearest up-close candle above the entry
            lvl = float(sd.o[k]) if p.offside_level == "open" else float((sd.h[k] + max(sd.o[k], sd.c[k])) / 2)
            pos["offside"] = lvl
    re = (state or {}).get("re_ctx", {}).get(tr.session) if state else None
    pos["reentry"] = bool(re and re.get("pending"))
    if pos["reentry"]:
        re["pending"] = False
        tr.reentry = True
        pos["re_loss"] = re.get("loss", 0.0)
    tr.slow_chop = bool((state or {}).get("fill_slow_chop", False))


# --- Silver Bullet / Ma Deuce: the same breakeven modes and invalidation exits (X4 / D14 / X6-X9c) -----------------------

def extras_be_mode(p) -> str:
    """The breakeven mode of the Silver Bullet / Ma Deuce: `extras_be_on` "t1" (the first build: the stop goes to
    breakeven the moment the first target / rung is taken - the default, so nothing changes) or "follow" (the main
    engine's `be_on`: t1 / expansion / after_mss / stall / pool / off)."""
    return "t1" if p.extras_be_on == "t1" else p.be_on


def extras_t1(pos, p) -> None:
    """The first target / rung was taken in the Silver Bullet / Ma Deuce: breakeven now when the mode is "t1"."""
    pos["t1_done"] = True
    if extras_be_mode(p) == "t1":
        be_move(pos, p)
        pos["be_done"] = True


def extras_be_bar(sd, pos, tr, i: int, p) -> None:
    """The other breakeven modes, once per closed bar, after the bar's exits (a move applies from the next bar):
    expansion (a close above the first target after the bar that took it), after_mss / stall / pool (`be_modes`).
    "t1" / "off" do nothing here."""
    mode = extras_be_mode(p)
    if not pos["left"] or pos.get("be_done") or mode in ("t1", "off"):
        return
    if mode == "expansion":
        if pos["t1_done"] and pos["last_partial_i"] < i and sd.c[i] > (pos["levels"][0] if pos["levels"] else pos["t1"]):
            be_move(pos, p)
            pos["be_done"] = True
        return
    be_modes(sd, pos, tr, i, p, mode)


def extras_init(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    """Silver Bullet / Ma Deuce: give the position dict the fields `exits` / `be_modes` / `init_pos` read (side space),
    from the order `o`: zone_bottom / zone_top / zone_ce (the entry FVG / inverted FVG), ext / ext_i (the sweep or leg
    extreme), leg_hi, level_kinds, draw (side space), session. [our interpretation] The SB's "sweep" is the leg
    extreme before its MSS; Ma Deuce's is the inverted FVG."""
    pos.setdefault("basis", pos["entry"] * pos["n"])
    pos.update(fvg_bottom=o["zone_bottom"], fvg_ce=o["zone_ce"], zone_top=o["zone_top"], ext=o["ext"],
               ext_i=o["ext_i"], kind="fvg", level_kinds=o.get("level_kinds") or [], draw=o.get("draw"),
               last_partial_i=-1, leg=(o["ext"], o["leg_hi"]), stall_n=0)
    init_pos(ctx, sd, pos, tr, dict(o, session=o["session"]), i, p, None)


# --- time stop (X9 / X9a / X9d) -------------------------------------------------------------------------------

def time_stop_frac(p, st: dict, *, nbars: int, elapsed: float, best: float, basis: float, leg_hi=None,
                   zone_top=None) -> float:
    """X9 time stops: returns the share of what is left to cut now (0 = nothing). `st` holds {"done": bool}.
    Due after time_stop_bars candles (the fill candle is the first) or time_stop_min minutes; the trade must have
    delivered by then (time_stop_ref: pts of progress, the leg high, or the entry array's far edge)."""
    if st.get("done") or not (p.time_stop_min or p.time_stop_bars):
        return 0.0
    due = nbars >= p.time_stop_bars if p.time_stop_bars else elapsed >= p.time_stop_min
    if not due:
        return 0.0
    ref = p.time_stop_ref
    if ref == "leg_high" and leg_hi is not None:
        ok = best >= leg_hi - 1e-9
    elif ref == "array_far" and zone_top is not None:
        ok = best >= zone_top - 1e-9
    else:
        ok = best - basis >= p.time_stop_pts * p.es_pt
    if ok:
        st["done"] = True                          # delivered in time: the rule is spent
        return 0.0
    st["done"] = True
    return p.time_stop_frac


# --- the mid-trade exits ----------------------------------------------------------------------------------------

def exits(ctx, sd, pos, tr, i: int, ts, p, state, extras: bool = False) -> None:
    """All new mid-trade exits for bar i (after the bar's stop / ladder / legacy exit tests). Each is a market-on-close
    exit at bar i's close unless noted. Order: first-FVG fail, abort, three arrays, half off, leg MT, IR EQ, offside,
    meander, far edge, time stop, SMT hold / AM bulk, PM consolidation, objective, re-entry target / lock, up-close take profit.
    extras=True (Silver Bullet / Ma Deuce, `invalidations_extras`): only the invalidation exits (first-FVG fail, abort,
    three arrays, half off, leg MT, IR EQ, offside, meander, far edge) and the PM consolidation exit - the time stop,
    the AM bulk and the AM close run inline in those engines (same helpers), the draw is their last rung and there is
    no re-entry / up-close add there."""
    if not pos["left"]:
        return
    o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
    t, tf = ctx.t[i], ctx.tf
    fi = pos["fill_i"]
    basis = pos["basis"] / pos["n"]
    tk = p.tick
    later = i > fi and (not extras or p.invalidations_extras)      # the invalidation exits (X6-X9c) below need `later`
    held = False
    if p.smt_hold_until and tr.session != "PM" and pos.get("smt_tag") and pos["fill_t"] < p.smt_hold_until:
        held = t + tf < p.smt_hold_until                        # X10c: no soft exits while an AM SMT trade is held
        if not held and p.smt_hold_exit and not pos.get("smt_hold_done"):
            pos["smt_hold_done"] = True
            _exit(tr, sd, ts, c, pos["left"], "smt_hold", pos)
            return
    # --- Ep03.10 first FVG fail
    if p.first_fvg_fail and later and (not pos["t1_done"] or p.first_fvg_fail_after_t1):
        g = first_fvg(sd, pos["ext_i"], i - 1)
        if g is not None and c < g.bottom and i > g.i:
            _exit(tr, sd, ts, c, pos["left"], "first_fvg_fail", pos)
            return
    # --- X6 abort (rule mode)
    if p.fvg_abort and p.fvg_abort_mode == "rule" and later and not held:
        if _abort(ctx, sd, pos, tr, i, ts, p):
            return
    # --- X7a three arrays / X7b half off
    if p.pd3_exit and not p.pd3_legacy and later:
        arrs = pos.get("pd3")
        if p.pd3_dynamic:
            arrs = _arrays(sd, pos, i, p, pos["fill_px"], pos["stop0"], p.pd3_list)[:p.pd3_n]
        if arrs is not None:
            key = lambda lv: int(round(lv / tk))
            for lv, _ in arrs:
                if c < lv:
                    pos["pd3_broken"].add(key(lv))
            nb = sum(1 for lv, _ in arrs if key(lv) in pos["pd3_broken"])
            if nb >= 2 and not pos.get("pd3_warned"):
                pos["pd3_warned"] = True
                tr.lv_tags = "|".join(x for x in (tr.lv_tags, "pd3_warn") if x)       # the second array is a warning
            if len(arrs) >= p.pd3_n and nb >= p.pd3_n:
                _exit(tr, sd, ts, c, pos["left"], "pd3", pos)
                return
    if p.pd3_half and later and not pos.get("pd3_half_done") and pos.get("pd3_half_lv") is not None and c < pos["pd3_half_lv"]:
        pos["pd3_half_done"] = True
        q = cut_qty(pos["left"], p.pd3_half_frac, p)
        _exit(tr, sd, ts, c, q, "pd3_half", pos)
        if not pos["left"]:
            return
    # --- X8b leg MT
    if p.leg_mt_exit and later:
        k = pos.get("leg_k")
        if k is None:
            k = _leg_candle(sd, pos["ext_i"], i)
            if k is not None:
                pos["leg_k"] = k
                pos["leg_mt"] = float((sd.o[k] + sd.c[k]) / 2 if p.mt_mode == "body" else (sd.h[k] + sd.l[k]) / 2)
        if k is not None and i > k and c < pos["leg_mt"]:
            _exit(tr, sd, ts, c, pos["left"], "leg_mt", pos)
            return
    # --- X8c immediate-rebalance EQ
    if pos.get("ir_eq") is not None and later:
        eq = pos["ir_eq"]
        if p.ir_eq_wick and l < eq - 1e-9:
            _exit(tr, sd, ts, min(o, eq), pos["left"], "ir_eq", pos)             # a limit-type exit at the EQ
            return
        if not p.ir_eq_wick and c < eq:
            _exit(tr, sd, ts, c, pos["left"], "ir_eq", pos)
            return
    # --- X8e offside
    if pos.get("offside") is not None and later and not pos.get("off_ok"):
        lv = pos["offside"]
        if c >= lv:
            pos["off_ok"] = True                                                  # smashed through: the test passed
        elif h >= lv:
            pos["off_arm"] = True                                                 # reached it, bodies respected it
        elif pos.get("off_arm") and c < basis:
            _exit(tr, sd, ts, c, pos["left"], "offside", pos)
            return
    # --- X8g meander
    if p.meander_bars and later and not pos["t1_done"] and not held:
        if c > pos["fvg_top"]:
            pos["meander_n"] = 0
        elif pos["fvg_bottom"] <= c <= pos["fvg_top"]:
            pos["meander_n"] = pos.get("meander_n", 0) + 1
            if pos["meander_n"] >= p.meander_bars:
                _exit(tr, sd, ts, c, pos["left"], "meander", pos)
                return
        else:
            pos["meander_n"] = 0
    # --- X9c far edge
    if p.far_edge_min and later and not pos["t1_done"] and not pos.get("fe_done") and not held:
        if pos.get("fe_t") is None and l <= pos["fvg_bottom"] + tk:
            pos["fe_t"] = t
        if pos.get("fe_t") is not None:
            if c >= pos["fvg_ce"]:
                pos["fe_done"] = True                                             # moved back to the CE in time
            elif (t + tf) - pos["fe_t"] >= p.far_edge_min:
                pos["fe_done"] = True
                _exit(tr, sd, ts, c, cut_qty(pos["left"], p.far_edge_frac, p), "far_edge", pos)
                if not pos["left"]:
                    return
    # --- X9 time stop
    if (p.time_stop_min or p.time_stop_bars) and not pos["t1_done"] and not held and not extras:
        frac = time_stop_frac(p, pos.setdefault("ts", {}), nbars=i - fi + 1, elapsed=(t + tf) - pos["fill_t"],
                              best=pos["best"], basis=basis,
                              leg_hi=pos["leg"][1] if pos.get("leg") else None, zone_top=pos["fvg_top"])
        if frac > 0:
            q = cut_qty(pos["left"], frac, p)
            _exit(tr, sd, ts, c, q, "time" if q >= pos["left"] else "time_cut", pos)
            if not pos["left"]:
                return
    # --- X10b AM bulk
    if (p.am_bulk_t and tr.session != "PM" and not held and not pos.get("bulk_done") and not extras
            and pos["fill_t"] < p.am_bulk_t and t + tf >= p.am_bulk_t):
        pos["bulk_done"] = True
        _exit(tr, sd, ts, c, cut_qty(pos["left"], p.am_bulk_frac, p), "am_bulk", pos)
        if not pos["left"]:
            return
    # --- X11c PM consolidation exit
    if p.pm_consol_exit and tr.session == "PM" and t + tf >= p.pm_consol_exit and consol_day(ctx, i, p) and not S._SM7.held(pos):
        _exit(tr, sd, ts, c, pos["left"], "pm_consol", pos)
        return
    if extras:
        return
    xt = p.exit_fill_through * tk
    # --- X12 objective
    if p.obj_stop:
        ob = objective(pos, p)
        if ob is not None and h >= ob + xt:
            _exit(tr, sd, ts, ob, pos["left"], "objective", pos)
            return
    # --- D18 re-entry target / lock
    if pos.get("reentry") and (p.reentry_target_r or p.reentry_lock_r):
        R = tr.entry - tr.stop if sd.sign > 0 else tr.stop - tr.entry
        if R > 0:
            if p.reentry_target_r and h >= basis + p.reentry_target_r * R + xt:
                _exit(tr, sd, ts, basis + p.reentry_target_r * R, pos["left"], "re_target", pos)
                return
            if p.reentry_lock_r and not pos.get("re_locked") and pos["best"] >= basis + p.reentry_lock_r * R:
                done_ = sum((sd.sign * e[1] - basis) * e[2] for e in tr.exits)
                s_ = basis + (pos.get("re_loss", 0.0) - done_) / max(pos["left"], 1)
                s_ = min(s_, pos["best"] - tk, c - tk)          # under the price: never a stop above the market
                raise_stop(pos, s_)
                pos["re_locked"] = True                                           # the prior loss stays repaid
    # --- Ep07.5 up-close take profit on the add units
    if p.tp_upclose:
        units = pos.setdefault("add_units", [])
        seen = pos.get("tp_seen", pos.get("rung_fills", 0))
        for ta, pxa, qa in tr.adds[seen:]:
            units.append([sd.sign * pxa, qa])
        pos["tp_seen"] = len(tr.adds)
        if c > o:
            for u in list(units):
                if c > u[0] + tk and pos["left"]:
                    q = min(u[1], pos["left"])
                    _exit(tr, sd, ts, c, q, "tp_upclose", pos)
                    units.remove(u)


def _abort(ctx, sd, pos, tr, i: int, ts, p) -> bool:
    """X6 (045 ~1:19:58) rule mode. A 5-minute candle (fvg_abort_tf; engine bars are grouped) whose CLOSE is beyond the
    entry FVG's far edge (bottom) arms the abort at that candle's low (fvg_abort_body: the whole body beyond the edge);
    the NEXT candle trading below the armed low confirms it (exit at the armed low, or the open on a gap) - and only the
    next candle: if it does not, the arm is cleared. Returns True when the position was closed."""
    tf = ctx.tf
    m = max(1, p.fvg_abort_tf // tf)                           # engine bars per 5-minute candle
    t = ctx.t[i]
    c, l = sd.c[i], sd.l[i]
    arm = pos.get("abort_arm")                                 # (armed candle end bar, armed low)
    if arm is not None and i > arm[0]:
        if l < arm[1] - 1e-9:
            _exit(tr, sd, ts, min(sd.o[i], arm[1]), pos["left"], "abort", pos)
            pos["abort_arm"] = None
            return True
        if i >= arm[0] + m:                                   # the next candle is over without confirming
            pos["abort_arm"] = None
    if (t + tf) % p.fvg_abort_tf == 0 or m == 1:               # the bar closes a 5-minute candle
        j0 = i - m + 1
        if j0 > pos["fill_i"] and pos.get("abort_arm") is None:
            cc = sd.c[i]
            beyond = (max(sd.o[j0], cc) < pos["fvg_bottom"]) if p.fvg_abort_body else (cc < pos["fvg_bottom"])
            if beyond:
                pos["abort_arm"] = (i, float(sd.l[j0:i + 1].min()))
    return False


def objective(pos, p):
    """X12: the session objective (side space). "draw" = the locked draw (the order's draw, else the last ladder level);
    "htf_ce" = the last array rung of the ladder (an HTF array's CE / near edge), the draw if there is none."""
    lv = pos.get("levels") or []
    if p.obj_source == "htf_ce":
        kinds = pos.get("level_kinds") or []
        arr = [v for v, k in zip(lv, kinds) if k in ("array", "vi", "gap")]
        if arr:
            return float(arr[-1])
    if pos.get("draw") is not None:
        return float(pos["draw"])
    return float(lv[-1]) if lv else None


def consol_day(ctx, i: int, p) -> bool:
    """X11c: the PM is a consolidation-profile day (setups.cc_profile, read from bars closed by 13:30)."""
    k = S._idx_at(ctx, 810)                # the explicit 13:30 index (the first bar at or after 13:30, even when 13:30 is
    if k >= len(ctx.t) or i < k:           # missing) - the same for the main engine and the Silver Bullet; None before it
        return False
    r = S._SM.cc_profile(ctx, k, p)
    return bool(r) and str(r[0]).startswith("cons")


# --- adds -----------------------------------------------------------------------------------------------------

def downclose_add(sd, pos, tr, i: int, p, arm) -> bool:
    """Ep07.5 add_mode "downclose" (Ep 07 "market efficiency paradigm": buy down-close candles): a closed down-close
    candle after the fill whose low holds above the stop and the entry array's bottom arms an add at its close (the add
    rests at the candle's close and fills if price trades down to it again) [our interpretation]. Once per candle."""
    if i <= pos["fill_i"] + 1 or not sd.c[i] < sd.o[i]:
        return False
    if sd.l[i] < pos["stop"] or sd.l[i] < pos["fvg_bottom"] or sd.c[i] <= pos["basis"] / pos["n"]:
        return False
    return bool(arm(float(sd.c[i])))


# --- session / day stops (X7c / X12 / X13a / X14b / X14d / Ep04.13) ------------------------------------------------

def _net(tr, p) -> float:
    gross, costs = tr.pnl(p.cost_per_share)
    return gross - costs


def mark_day_stop(tr, p) -> None:
    """X12 / Ep04.13: a trade that took its objective / its final level (before done_target_before) ends the day (read by
    `stops_from`, so the main loop, the Silver Bullet and Ma Deuce agree)."""
    if not tr.exits:
        return
    xm = tr.exits[-1][0].hour * 60 + tr.exits[-1][0].minute
    if p.obj_stop and (tr.exits[-1][3] == "objective" or tr.final_hit):
        tr.stop_day = "obj_stop"
    elif p.done_if_target and tr.final_hit and xm < p.done_target_before:
        tr.stop_day = "done_target"


def fam(session: str) -> str:
    """AM family (AM, pre-open, news, London, Ma Deuce) or PM."""
    return "PM" if session == "PM" else "AM"


def any_stop_switch(p, day=None) -> bool:
    """Any session / day stop in force. fomc_no_reentry (N3 / N3.5) counts only on an FOMC day (day=None: assume so)."""
    return bool(p.session_stop_after_fails or p.loss_ends_morning or p.no_trade_after_win or p.chop_one_win
                or p.obj_stop or p.done_if_target
                or (p.fomc_day_stop and (day is None or "fomc" in events(day))))


def stops_from(p, trades, ts=None) -> tuple:
    """(day reason | None, {family: reason}) from the CLOSED trades (exit at or before `ts`; all when None), in exit
    order. The main loop, Silver Bullet and Ma Deuce all read this, so the three agree [one source of truth]:
      no_trade_after_win  X14d (095 ~47:08) any winner on the day ends the day
      chop_one_win        X14b (031 ~9:20) a winner of a trade filled on a chop / slow day ends the day
      stop_day            X12 / Ep04.13 the trade itself ended the day (objective hit, final level before the cut-off)
      loss_ends_morning   X13a (001 ~46:57-48:43) an AM-family loss ends the AM family
      session_stop_after_fails  X7c (044 ~1:52:49) N failed trades in a row in a session end that session
      fomc_no_reentry  N3 / N3.5 (021 ~43:56) a loss on an FOMC day ends the day (every session, every model)"""
    closed = sorted((t for t in trades if t.exits and (ts is None or t.exits[-1][0] <= ts)),
                    key=lambda t: t.exits[-1][0])
    day, sess = None, {}
    for tr in closed:
        net = _net(tr, p)
        if p.no_trade_after_win and net > 0:
            day = day or "win"
        if p.chop_one_win and net > 0 and tr.slow_chop:
            day = day or "chop_win"
        if tr.stop_day:
            day = day or tr.stop_day
        if p.loss_ends_morning and net < 0 and fam(tr.session) == "AM":
            sess["AM"] = "loss_ends_morning"
        if p.fomc_day_stop and net < 0 and "fomc" in events(tr.date):
            day = day or "fomc_loss"
    n = p.session_stop_after_fails
    if n:
        for f in ("AM", "PM"):
            run = 0
            for tr in (t for t in closed if fam(t.session) == f):
                fail = _net(tr, p) < 0 and (p.session_fail_mode == "trades"
                                            or tr.exits[-1][3].split("+")[0] in FAIL_REASONS)
                run = run + 1 if fail else 0
            if run >= n:
                sess[f] = "fails"
    return day, sess


def extras_blocked(ctx, p, session: str, ts, extra=()) -> bool:
    """Silver Bullet / Ma Deuce / pre-open: no new order for `session` armed at bar `ts` once the day or the session is
    stopped by the closed trades before it (the main loop's trades + `extra`, the extras' own)."""
    if not any_stop_switch(p, getattr(ctx, "day", None)):
        return False
    view = getattr(ctx, "risk_view", None)
    base = list(view["trades"]) if view else []
    extra = list(extra)
    seen = {id(t) for t in base}
    day, sess = stops_from(p, base + [t for t in extra if id(t) not in seen], ts)
    return bool(day) or fam(session) in sess


def key_fam(k: str) -> str:
    """The family of a done-flag key: PM (PM, LH, PMR, SB_PM) or the morning (AM, PRE7, PRE9, NEWS, SB_AM, ...)."""
    return "PM" if k in ("PM", "LH", "PMR", "SB_PM") else "AM"


def apply_stops(trades, p, done: dict, state: dict, ts=None) -> None:
    """After a close in the main loop (and, with `state["ext"]`, once per bar): recompute the stops from the closed trades
    and enforce them on the done flags (idempotent: a re-entry that re-opened a flag cannot re-open a stopped session or
    day). `state["ext"]` = the Silver Bullet / Ma Deuce trades of the previous pass of run_day's fixed point
    (strategy.run_day): they count as of their exit time `ts`, so the stops are two-way (an SB win ends the main
    engine's day, an SB fail counts toward the session fails) without the main loop ever seeing a later trade."""
    if not any_stop_switch(p, state.get("day")):
        return
    ext = state.get("ext") or []
    if ext and ts is None:
        ts = max((t.exits[-1][0] for t in trades if t.exits), default=None)
        if ts is None:
            return
    day, sess = stops_from(p, list(trades) + list(ext), ts if ext else None)
    st = state.setdefault("stops", {"day": None})
    if day and not st.get("day"):
        st["day"] = day
        state["day_done"] = True
    for f, why in sess.items():
        st.setdefault(f, why)
    for k in list(done):
        if st.get("day") or key_fam(k) in st:
            done[k] = True


def sync_ext(trades, p, done: dict, state: dict, ts) -> None:
    """Bar start in the main loop: the extras' trades closed at or before `ts` (previous pass) may have stopped the
    session / the day (X7c / X12 / X13a / X14b / X14d)."""
    if state.get("ext") and any_stop_switch(p, state.get("day")):
        apply_stops(trades, p, done, state, ts=ts)


def blocked_now(state: dict, session: str) -> bool:
    st = state.get("stops")
    if not st:
        return False
    return bool(st.get("day")) or fam(session) in st


# --- re-entry (X13b / D18) -------------------------------------------------------------------------------------------

def reentry_open(ctx, pos, tr, i: int, p, state, lost_net: float) -> dict | None:
    """After a loss: the context of a same-side re-entry (X13b / D18), or None when it is not allowed. With
    reentry_gate: not on an FOMC day (reentry_fomc_ok), the locked draw not delivered and the original trade's last
    level not traded since its fill ("the idea is intact") [our interpretation]; the new order has to be on the same
    side with a restored sweep and an FVG made after the stop (reentry_order_ok)."""
    if p.reentry_stop_only and not (tr.exits and tr.exits[-1][3].split("+")[0] in ("stop", "stop_gap")):
        return None                              # D18 "re-entry after a stop-out": a time stop / abort / eod loss is not one
    if p.reentry_gate:
        if "fomc" in events(ctx.day) and not p.reentry_fomc_ok:
            return None
        sd = pos["side"]
        lv = pos.get("levels") or []
        tgt = pos["draw"] if pos.get("draw") is not None else (lv[-1] if lv else None)
        if tgt is not None and sd.h[pos["fill_i"]:i + 1].max() >= tgt:
            return None
        lk = ctx.lock.get(tr.session) if getattr(ctx, "lock", None) else None
        if lk is not None and lk.get("delivered"):
            return None
    eq = ctx.equity or 0.0
    ratio = 1.0
    if p.reentry_risk == "loss" and tr.entry_risk_pct and eq:
        bud = S._risk_budget(p, eq)
        ratio = (tr.entry_risk_pct * eq) / bud if bud else 1.0
    return dict(side=tr.side, stop_i=i, fill_i=pos["fill_i"], pending=True, loss=max(0.0, -lost_net), ratio=ratio,
                key=pos.get("done_key", tr.session))


def reentry_order_ok(o_: dict, sd, rc: dict, p) -> bool:
    """X13b: a re-entry order is the same side with a RESTORED sweep (its extreme made after the stop-out) and an FVG
    formed after the stop (the order's FVG bar, else its arming bar)."""
    if not p.reentry_gate:
        return True
    if ("long" if sd.sign > 0 else "short") != rc["side"]:
        return False
    if o_["ext_i"] <= rc["stop_i"]:
        return False
    return o_.get("fvg_i", o_["i"]) > rc["stop_i"]      # the order's FVG bar (`fvg_i`, FVG entries), else its arming bar


# --- fades (T11) ------------------------------------------------------------------------------------------------------

def is_fade(ctx, sd, lk, i: int) -> bool:
    """T11: an entry against the day's direction = against the locked draw's side, else against the 09:30 open."""
    if lk is not None and lk.get("side"):
        return sd.sign != lk["side"]
    k = S._idx_at(ctx, 570)
    if k >= len(ctx.t) or k > i:
        return False
    d = np.sign(ctx.c[i] - ctx.o[k])
    return bool(d) and sd.sign != d


# --- B18.3 SMT as a bias input ------------------------------------------------------------------------------------------

def smt_bias(ctx, i: int, p) -> int:
    """B18.3 smt_bias (B18 "Uses: bias"; 022; 065B ~05:04): the SMT divergence at the previous day's high / low in the
    overnight range, read once the 09:30 bar has closed [our interpretation]. Our index took the previous RTH low while the
    sister index did not (it held above its own previous low) -> +1 (bullish); the mirror at the high -> -1; both -> the one
    that came later; no partner -> 0. Uses bars closed before 09:30 only; cached from the first decision bar after it."""
    cached = getattr(ctx, "_smt_bias", None)
    if cached is not None:
        return cached
    ps = getattr(ctx, "pside", None)
    pc = ps[0] if ps else None
    hist, phist = getattr(ctx, "hist", None), getattr(pc, "hist", None) if pc is not None else None
    if pc is None or not hist or not phist:
        return 0
    k = S._idx_at(ctx, 570)
    end = min(k, i + 1)
    if end <= ctx.start + 1:
        return 0
    last = ctx.idx[end - 1]
    pend = int(pc.idx.searchsorted(last, side="right"))
    if pend <= pc.start + 1:
        return 0
    lo_o, hi_o = ctx.l[ctx.start:end], ctx.h[ctx.start:end]
    lo_p, hi_p = pc.l[pc.start:pend], pc.h[pc.start:pend]
    pdl, pdh = float(hist[-1].low.min()), float(hist[-1].high.max())
    qdl, qdh = float(phist[-1].low.min()), float(phist[-1].high.max())
    bull = lo_o.min() < pdl and lo_p.min() >= qdl
    bear = hi_o.max() > pdh and hi_p.max() <= qdh
    out = 0
    if bull and bear:
        out = 1 if int(np.argmin(lo_o)) > int(np.argmax(hi_o)) else -1
    elif bull:
        out = 1
    elif bear:
        out = -1
    if end >= k:
        ctx._smt_bias = out                     # final once the overnight range is complete
    return out
