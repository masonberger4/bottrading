"""Package entries_stops_sizing (rule_coverage.md section 3 "entries_stops_sizing"; build_log.md).

Entry prices, stop placement, order hygiene, sizing and the add rules of the E / D / A items,
called from strategy._scan_core / _finish_order / run_day. Everything here runs in SIDE SPACE
(bullish terms; shorts are the mirrored prices of strategy.Side), reads only bars that have closed
(index <= the caller's bar i) and every rule is a Params switch. Thresholds ICT never gives are
marked [our interpretation].

Pieces
  entry_px / ladder_rungs      E2 / D11  entry price modes: edge, ce, edge_1tick, iofed, ladder
  gap_stop                     E6 / E6b / E6c / Ep01.20 / M2.5  the new stop_mode values
  refine_stop                  A4 / A12 / E6d / E6f / Ep02.3   stop modifiers for every entry path
  ob_entry / ob_far            A12 / Ep03.9  the OB zone (range / sensitive) and its entry price
  size_mult                    E9  size-down / size-up rules
  risk_state_*                 E10  loss_halving (state carried across days by backtest.run)
  add_*                        E12 / E12b / E12c / E12e / E12f / Ep01.18 / Ep01.19 / Ep04.10 / owner #7
"""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from claude_hf.daytypes import events
from . import levels as L
from . import strategy as S


# --- entry price (E2 / D11) ---------------------------------------------------------------------

def ladder_rungs(top: float, bottom: float, p) -> list[float]:
    """E2 (030 ~15:46): "FVG high, then 75%, then CE" (bullish). Two rungs = edge + CE; more than
    three are spread evenly from the edge to the CE [our interpretation]."""
    mid = (top + bottom) / 2
    n = len(p.entry_ladder_fracs)
    if n == 2:
        return [top, mid]
    if n == 3:
        return [top, bottom + 0.75 * (top - bottom), mid]
    return [float(x) for x in np.linspace(top, mid, n)]


def entry_px(sd, g, top: float, bottom: float, p, mode: str | None = None) -> float:
    """The limit price inside the entry gap (side space). edge = the near edge; ce = 50%;
    edge_1tick = one tick inside the edge (001, 018, 042, 054, 057, 066 live fills); iofed (003
    ~30:30; 006 ~50:09; 010 ~47:38; 024 ~23:43) = the FVG-forming candle's high clipped into the
    gap - never beyond one tick inside the edge and never past the CE ("a shallow touch that does
    not reach CE"), or per iofed_ref "tick" / "q75"; ladder = the first rung (the edge; the other
    rungs are placed by the caller from ladder_rungs)."""
    mode = mode or p.entry
    tk = p.tick
    mid = (top + bottom) / 2
    if mode in ("edge", "ladder"):
        return top
    if mode == "ce":
        return mid
    if mode == "edge_1tick":
        return max(bottom, top - tk)
    if mode == "iofed":
        if p.iofed_ref == "tick":
            return max(bottom, top - tk)
        if p.iofed_ref == "q75":
            return bottom + 0.75 * (top - bottom)
        h2 = float(sd.h[g.src]) if (g is not None and getattr(g, "src", -1) >= 0) else top
        return float(max(bottom, min(top - tk, max(mid, h2))))
    raise ValueError(f"entry mode {mode!r}: expected one of {S.ENTRY_MODES}")


# --- stops (E6 / E6b / E6c / Ep01.20 / M2.5) ------------------------------------------------------

def gap_stop(sd, g, sw, i, p, ob, mode: str):
    """The stop (side space) of the new stop_mode values, or None (mode not handled here / no
    data). `g` is the entry FVG (a plain bullish gap: g.i is its third candle, g.src the middle
    one), `ob` the blended OB before the break or None.
      fvg_c1_low   below candle 1's low (E6 "just beyond the FVG-forming candle", Ep 01)
      fvg_bodies   below the lowest body of the three FVG candles (E6b; 013 ~18:13; 090 ~2:14)
      fvg_open     below the open of the middle (displacement) candle (Ep01.20; 015 ~33:56)
      sweep        beyond the sweep extreme (E6c; cc05_005 ~11:06; cc02_002 ~6:34; 078 ~1:22:14)
      ob_mt_pure   the OB mean threshold minus ob_mt_pure_pad_pts (M2.5; no FVG-bottom min)"""
    pad = p.pad
    if mode == "sweep":
        return float(sw["ext"]) - pad
    if mode == "ob_mt_pure":
        if ob is None:
            return None
        mt = ob.mt if p.mt_mode == "body" else ob.mid
        return float(mt) - p.ob_mt_pure_pad_pts * p.es_pt
    if g is None or g.i - 2 < 0:
        return None
    if mode == "fvg_c1_low":
        return float(sd.l[g.i - 2]) - pad
    if mode == "fvg_bodies":
        return float(min(min(sd.o[k], sd.c[k]) for k in range(g.i - 2, g.i + 1))) - pad
    if mode == "fvg_open":
        return float(sd.o[g.i - 1]) - pad
    return None


def refine_stop(ctx, sd, sw, i, p, entry: float, stop: float, tags: dict, lvx: dict, lvt: list) -> float:
    """Stop modifiers applied to every entry path (_finish_order), in this order:
    A12 / Ep02.3 mt_close_stop, E6d stop_all_ineff, E6f nfp_stop_wide and ce_stop_pad_pts, A4 mohawk.
    Each only ever moves the stop further away (E7: a stop is never tightened by these)."""
    pad = p.pad
    mtc = tags.pop("mt_close", None)
    if p.mt_close_stop and mtc is not None:
        mt, far = mtc
        if abs(stop - (mt - pad)) < 1e-9 and far - pad < stop:
            stop = far - pad                       # hard stop at the OB far edge ...
            lvx["ob_mt_close"] = (float(mt), False)    # ... a body CLOSE below the MT exits (wicks may poke)
            lvt.append("mt_close")
    if p.stop_all_ineff:
        c = []
        e = sw["ext_i"]
        for g in sd.gaps:
            if e < g.i - 2 and g.i <= i and g.bottom < entry and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom:
                c.append(g.bottom)               # an open FVG under the entry since the sweep
        for z in sd.vis("bull"):
            if e < z.i <= i and z.bottom < entry and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom:
                c.append(z.bottom)               # an open VI under the entry
        if p.stop_ineff_wick and i > e:
            lows = sd.l[e + 1:i + 1]
            gb = min(c) if c else entry
            below = lows[lows < gb]              # an overshoot wick printed after the sweep extreme
            if len(below):
                c.append(float(below.min()))
        if c and min(c) - pad < stop:
            stop = min(c) - pad
            lvt.append("stop_ineff")
    if p.nfp_stop_wide and "jobs" in events(ctx.day):
        a = max(0, sw["ext_i"] - 3)
        body = float(np.minimum(sd.o[a:i + 1], sd.c[a:i + 1]).min())
        if body - pad < stop:
            stop = body - pad
            lvt.append("nfp_wide")
    if p.ce_stop_pad_pts and tags.get("ce_entry"):
        stop -= p.ce_stop_pad_pts * p.es_pt
    if p.mohawk_ticks:
        raw = stop                               # the level + pad: a body close beyond it exits
        stop -= p.mohawk
        lvx["mohawk"] = (float(raw), False)
    tags.pop("ce_entry", None)
    return stop


def ote_cancel_level(entry: float, ext: float, leg_hi: float, existing, p):
    """A21.3 ote_cancel: a closed bar through the 79% line of the leg cancels the order - set only for an
    entry in or under the OTE band (not for a shallower entry, review fix), and never loosening a
    cancel level that is already there (ob_cisd="cancel": the more protective = higher one wins)."""
    if not (p.ote_cancel and p.ote != "off"):
        return existing
    band = L.ote_band(ext, leg_hi)
    if entry > band[1] + p.tick:
        return existing
    return max(float(band[0]), float(existing)) if existing is not None else float(band[0])


def engage_ok(ctx, i: int, p) -> bool:
    """Ep08.17 (010 ~1:15:16): the session range since midnight is at least engage_range_pts."""
    if not p.engage_range_pts:
        return True
    a = ctx.start
    return float(ctx.h[a:i + 1].max() - ctx.l[a:i + 1].min()) >= p.engage_range_pts * p.es_pt - 1e-9


# --- order blocks (A12 / Ep03.9 / Ep08.5) -----------------------------------------------------------

def ob_entry_price(ob: dict, sd, p) -> float:
    """The limit price at a bullish OB dict from strategy._ob_at_low (body_top, body_low, mt, hi, lo, j, k).
    ob_entry_px: body_top (the highest open) / mt / range_top (= "high") / open (Ep03.9: the open of
    the FIRST candle of the series). ob_zone overrides it: "range" = the full range's high;
    "sensitive" (A12 012 ~5:13; 055 ~1:44; 061 ~26:10) = high down to the open - at the open when
    the upper wick is stubby (<= ob_stub_frac of the series range), else at the upper wick's CE."""
    if p.ob_zone == "range":
        return float(ob["hi"])
    if p.ob_zone == "sensitive":
        rng = max(ob["hi"] - ob["lo"], 1e-12)
        wick = ob["hi"] - ob["body_top"]
        return float(ob["body_top"] if wick <= p.ob_stub_frac * rng else (ob["hi"] + ob["body_top"]) / 2)
    px = p.ob_entry_px
    if px == "open":
        return float(sd.o[ob["j"]])
    return float({"body_top": ob["body_top"], "mt": ob["mt"], "range_top": ob["hi"], "high": ob["hi"]}[px])


def ob_blend(sd, sw, i):
    """The blended bullish OB (levels.order_block_blend) before the structure break, as the FVG
    path uses it: the last down-close candle(s) in [ext-3, broke-1]."""
    if sw.get("broke") is None:
        return None
    return L.order_block_blend(sd.o, sd.h, sd.l, sd.c, sw["ext_i"] - 3, sw["broke"] - 1, "bull")


def ob_quality_ok(sd, sw, ob, i, p) -> bool:
    """A12 ob_disp_mult (022 ~13:12; 064 ~50:06; cc04_003 ~26:51): the move away from the OB (its
    top to the highest high since) is at least ob_disp_mult x the OB body."""
    if not p.ob_disp_mult or ob is None:
        return True
    body = float(max(sd.o[ob.src], sd.c[ob.src]) - min(sd.o[ob.src], sd.c[ob.src]))
    body = max(body, float(ob.top - ob.bottom) * 0.1)          # a doji OB keeps a floor [our interpretation]
    move = float(sd.h[ob.src + 1:i + 1].max() - ob.top) if i > ob.src else 0.0
    return move >= p.ob_disp_mult * body


def ob_cisd_ok(sd, ob, i, p) -> bool:
    """A12 (075 ~1:16:40; 078 ~53:53) 2023 validation: after the OB a bar CLOSED through the open
    of its last down candle (the OB's highest open)."""
    if ob is None:
        return False
    k = ob.src
    while k + 1 < len(sd.c) and k + 1 <= i and sd.c[k + 1] < sd.o[k + 1]:
        k += 1
    top = float(max(sd.o[ob.src:k + 1]))
    return bool((sd.c[k + 1:i + 1] > top).any())


def opposing_obs(sd, i: int, p):
    """A12 / ob_targets_1m: bearish order blocks (side space; zone top/bottom, mt) of this session's
    bars known by bar i: each bearish FVG's last up-close candle(s) before it (the way propulsion
    blocks find bullish ones). Cached on the Side."""
    def build():
        out = []
        for z in sd.opposing():
            if z.src < 0 or z.top - z.bottom <= 0:
                continue
            # a SIBI mirrored into side space: bearish gap above price. Its OB = the up-close run
            # right before the gap (side space)
            ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, z.i - 4, z.i - 2, "bear")
            if ob is not None:
                out.append(L.Zone("bear", ob.top, ob.bottom, z.i, ob.src, ob.mt))
        return out
    return [z for z in sd._lazy("opp_obs", build) if z.i <= i]


def ob_target_levels(sd, i: int, above: float, p) -> list:
    """ob_targets_1m (A12; cc01_004 ~36:31: opposing OBs are targets and profit spots): the near edge
    and the MT of the opposing OBs above `above` that price has not traded into since they formed.
    opp_ob_mt (065A ~1:39: once price trades through an OB's MT its other half is not revisited): an
    OB whose lower half was traded (high >= near edge) but not yet its MT keeps the MT as a target;
    once the MT itself traded the OB is spent."""
    out = []
    for z in opposing_obs(sd, i, p):
        hi_since = sd.h[z.i + 1:i + 1].max(initial=-np.inf)
        mt = float(z.mt if z.mt == z.mt else z.mid)
        if hi_since < z.bottom:
            out += [(float(z.bottom), "array"), (mt, "array")]
        elif p.opp_ob_mt and hi_since < mt:
            out.append((mt, "array"))
    return [(v, k) for v, k in out if v > above]


# --- sizing (E9 / E10 / E11 / Ep08.12) ------------------------------------------------------------

def _next_day_events(day) -> set:
    from .calendar import next_trading_day
    try:
        return events(next_trading_day(day))
    except Exception:
        return set()


def bias_row_known(ctx, i) -> object:
    """The day's htf table row (ctx.bias_row) only for bars at or after 09:30: that table is cut at the
    09:30 open, so a pre-open order (PRE7 / PRE9 / Ma Deuce / London) reading it would use bars that
    have not printed yet (the B3 pre-open look-ahead; found by the SB / Ma Deuce look-ahead test)."""
    row = getattr(ctx, "bias_row", None)
    if row is None or i is None:
        return row
    return row if ctx.t[i] >= 570 else None


def low_probability(ctx, sd, p, htf_tag, sloppy: str, i=None) -> bool:
    """E9 / E12f "low-probability setup" [our interpretation], any of low_prob_tests:
    against_bias (the htf table's draw column opposes the side), no_htf (no HTF array at the sweep),
    sloppy (a sloppy-day reason is active)."""
    for t in p.low_prob_tests:
        if t == "against_bias":
            row = bias_row_known(ctx, i)
            if row is not None:
                try:
                    if int(row["draw"]) == -sd.sign:
                        return True
                except Exception:
                    pass
        elif t == "no_htf" and not htf_tag:
            return True
        elif t == "sloppy" and sloppy:
            return True
    return False


def decoupled(ctx, i: int, p) -> bool:
    """E9 / E12f (045 ~1:01:43; 079) "cracked ES/NQ correlation" [our interpretation]: the day's
    move since the 09:30 open has the opposite sign on the partner instrument and both exceed
    0.1% (known bars only)."""
    ps = getattr(ctx, "pside", None)
    if not ps or ps[0] is None:
        return False
    pctx, _, ppos = ps
    t = ctx.idx[i]
    try:
        j = int(ppos.index.get_indexer([t])[0])
    except Exception:
        return False
    if j < 0:
        return False
    k0 = next((k for k in range(ctx.start, i + 1) if ctx.t[k] >= 570), None)
    kp = next((k for k in range(pctx.start, j + 1) if pctx.t[k] >= 570), None)
    if k0 is None or kp is None:
        return False
    a = ctx.c[i] / ctx.o[k0] - 1
    b = pctx.c[j] / pctx.o[kp] - 1
    return bool(a * b < 0 and abs(a) > 0.001 and abs(b) > 0.001)


def size_mult(ctx, sd, sw, i, p, session, entry, htf_tag, sloppy: str, lvt: list) -> float:
    """E9 size rules (022 ~1:38:24; 029 ~5:22; 042 ~3:50; 045 ~1:01:43; 079; 090 ~35:02; 094; 103
    ~32:44): each active size-down rule multiplies the risk by size_down; the test-only size-ups
    (092 ~9:44; 102 ~1:23:50) by size_up (the 1.3% total cap still binds in _first_units)."""
    m = 1.0
    day = ctx.day
    for r in p.size_rules:
        on = False
        if r == "news_eve":                      # the day before CPI / NFP / FOMC
            on = bool(_next_day_events(day) & {"cpi", "jobs", "fomc"})
        elif r == "fomc_week":
            mon = day - timedelta(days=day.weekday())
            on = any("fomc" in events(mon + timedelta(days=k)) for k in range(5))
        elif r == "august":
            on = day.month == 8
        elif r == "against_macro":
            row = bias_row_known(ctx, i)
            if row is not None:
                try:
                    on = int(row["react"]) == -sd.sign or int(row["draw"]) == -sd.sign
                except Exception:
                    on = False
        elif r == "decoupled":
            on = decoupled(ctx, i, p)
        elif r == "low_prob":
            on = low_probability(ctx, sd, p, htf_tag, sloppy, i)
        if on:
            m *= p.size_down
            lvt.append("size_" + r)
    for r in p.size_up_rules:
        on = False
        if r == "bpr":
            on = any(z.i <= i and z.bottom <= entry and z.top >= sw["ext"] for z in sd.bprs(p.bpr_max_gap_bars))
        elif r == "htf_target" and getattr(ctx, "conf", None) is not None:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            near = ctx.conf.targets(now, sd.x(entry), sd.sign, p.htf_targets, False)
            on = any(0 < sd.sign * (sd.sign * sd.x(v) - sd.sign * sd.x(entry)) <= p.htf_target_pts * p.es_pt
                     for v in near) if near else False
        if on:
            m *= p.size_up
            lvt.append("size_up_" + r)
    return m


def contracts(shares: float, p) -> float:
    return shares / max(p.units_per_contract or p.lot, 1)


def cap_initial(shares: int, p) -> int:
    """E11 max_contracts_initial (Ep08; 010 ~49:51; 076 ~27:54: ~6 contracts initial)."""
    if p.max_contracts_initial:
        per = max(p.units_per_contract or p.lot, 1)
        shares = min(shares, p.max_contracts_initial * per)
        shares = S._lots(shares, p.lot)
    return int(shares)


def cap_add(q: int, held: int, p) -> int:
    """E11 max_contracts_total (10-16 by pyramiding): an add shrinks to the contracts left."""
    if p.max_contracts_total:
        per = max(p.units_per_contract or p.lot, 1)
        q = min(q, max(0, p.max_contracts_total * per - held))
        q = S._lots(q, p.lot)
    return int(q)


# --- risk state (E10 loss_halving) ------------------------------------------------------------------

def new_risk_state() -> dict:
    return dict(m=1.0, deficit=0.0, peak=0.0)


def risk_state_update(rs: dict, net: float, p) -> None:
    """E10 (061 ~2:26:40; cc02_005 ~5:20-15:44; cc06_003 ~23:24): after a loss halve the risk (down to
    halving_floor); a win reduces the drawdown, and once winback_frac of the peak drawdown is won
    back the size steps back to full. Never raised to recover."""
    if net < 0:
        rs["deficit"] += -net
        rs["peak"] = max(rs["peak"], rs["deficit"])
        rs["m"] = max(p.halving_floor, rs["m"] * 0.5)
    else:
        rs["deficit"] = max(0.0, rs["deficit"] - net)
        if rs["peak"] <= 0 or rs["deficit"] <= rs["peak"] * (1 - p.winback_frac) + 1e-9:
            rs["m"], rs["deficit"], rs["peak"] = 1.0, 0.0, 0.0


# --- adds -------------------------------------------------------------------------------------------

def add_px(g, p) -> float:
    """E12 add_points: where in a new FVG g an add rests (side space)."""
    if p.add_points == "ce":
        return (g.top + g.bottom) / 2
    if p.add_points == "q75":
        return g.bottom + 0.75 * (g.top - g.bottom)
    return g.top


def adds_blocked(ctx, sd, pos, i, p) -> bool:
    """E12f / Ep08.12: no pyramiding on a jobs (NFP) day, none when ES and the partner are
    decoupled, none on low-probability setups, none after a loss that day (after_loss_adds False /
    no_max_after_loss)."""
    if (p.nfp_no_adds or p.no_adds_nfp) and "jobs" in events(ctx.day):
        return True
    if p.decoupled_no_adds and decoupled(ctx, i, p):
        return True
    if p.low_prob_no_adds and pos.get("low_prob"):
        return True
    return False


def add_range(pos, p):
    """The range the E12e / D12 add cut measures: (low, high) in side space = the sweep extreme and
    the locked draw (add_cut_ref="range") or the leg high ("leg"); None when unknown."""
    leg = S._SM.add_leg(pos)                    # M2.6: fixed at the fill
    if not leg:
        return None
    ext, hi = leg
    if p.add_cut_ref == "range" and pos.get("draw") is not None:
        hi = pos["draw"]
    return (ext, hi) if hi > ext else None


def add_cut_passed(sd, pos, i, p) -> bool:
    """E12e (022 ~49:26; 025 ~47:56; 045 ~1:51:09; 058 ~43:12; 092 ~1:15:24) / D12 add_cutoff: True
    once the position's progress (the highest high since the fill) passed the cut: EQ of the range
    (add_cut "eq"), 75% of the leg (add_cut "leg75"), or 1 - add_cutoff of the range (the "25% line":
    add_cutoff 0.25 = 75% covered)."""
    if not (p.add_cut or p.add_cutoff):
        return False
    r = add_range(pos, p) if p.add_cut != "leg75" else (S._SM.add_leg(pos) or None)
    if r is None:
        return False
    lo, hi = r
    prog = (float(sd.h[pos["fill_i"]:i + 1].max()) - lo) / (hi - lo)
    fr = []
    if p.add_cut == "eq":
        fr.append(0.5)
    if p.add_cut == "leg75":
        fr.append(0.75)
    if p.add_cutoff:                    # add_cutoff_read: "covered" (1 - cutoff) or "progress" (cutoff itself)
        fr.append(p.add_cutoff if p.add_cutoff_read == "progress" else 1.0 - p.add_cutoff)
    return bool(prog >= min(fr) - 1e-12)


def htf_add_zones(ctx, sd, pos, i, p) -> list:
    """Owner #7 (revised): the HTF FVG BEHIND the trade - one price already traded through - is
    support (resistance for a short) and an ADD zone, never a target. Same-side arrays on
    add_htf_tfs valid at bar i's close, in side space, whose top lies between the stop and the
    close. Returns [(top, bottom, tf)] nearest the price first."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return []
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    out = []
    for top, bot, tf, src, known in cf.valid(now, sd.sign, p.add_htf_tfs, src=(0,)):
        t_, b_ = (sd.x(top), sd.x(bot)) if sd.sign > 0 else (sd.x(bot), sd.x(top))
        if pos["stop"] < t_ < sd.c[i]:
            out.append((float(t_), float(b_), tf))
    return sorted(out, reverse=True)


def more_add_arrays(ctx, sd, pos, tr, i, p, arm) -> bool:
    """E12b add_arrays vi / ifvg / ob / breaker and the owner #7 htf_fvg: arm at most one add on
    bar i's close at the array's top. `arm(px, **kw)` is the caller's arming function. True if armed."""
    ar = set(p.add_arrays)
    if "vi" in ar:
        vs = [z for z in sd.vis("bull") if z.i == i and z.i > pos["fill_i"] + 1]
        if vs and arm(vs[-1].top, floor=vs[-1].bottom):
            return True
    if "ifvg" in ar:
        zs = [z for z in sd.ifvgs() if z.i == i and z.i > pos["fill_i"] + 1 and z.bottom > pos["stop"]]
        if zs and arm(zs[-1].top, floor=zs[-1].bottom):
            return True
    if "ob" in ar and not p.ob_adds:
        S._ob_add(sd, pos, tr, i, p, ctx.equity)
        if pos["add"] is not None:
            return True
    if "breaker" in ar and pos.get("bz_side") and not pos.get("bz_add2"):
        top, bot = pos["bz_side"]
        if i > pos["fill_i"] and sd.c[i] > top and top > pos["stop"]:
            pos["bz_add2"] = True
            if arm(top, floor=bot):
                return True
    if "htf_fvg" in ar and not pos.get("htf_add_used"):
        zs = htf_add_zones(ctx, sd, pos, i, p)
        avg = pos["basis"] / pos["n"]
        zs = [z for z in zs if avg <= z[0] + p.tick]         # filled in / under it: price traded up through it
        if zs:
            top, bot, tf = zs[0]
            # review fix: the one shot is spent only when an add is really ARMED. A failed arm (no risk room
            # under the 1.3% cap, add_ok false) leaves it for a later bar, e.g. after a trail has freed risk.
            if arm(top, floor=bot, extra=p.htf_add_extra_risk_pct):
                pos["htf_add_used"] = True
                return True
    return False


# --- extra entry zones (Ep07.2 vi_entries, L14b irl_entries void) ------------------------------------

def extra_entry_zones(sd, sw, i, p) -> list:
    """Volume imbalances (vi_entries; Ep07.2, 009 ~13:46, 022) and liquidity voids (irl_entries
    "void"; L14b) formed AFTER the sweep extreme, as entry zones next to the FVGs: a limit at the
    zone top. A VI / void is made by two candles, so the index offset against an FVG (third
    candle) is one bar: both candles must come after the extreme (z.i - 1 > ext_i)."""
    e = sw["ext_i"]
    out = []
    if p.vi_entries:
        for z in sd.vis("bull"):
            if z.i <= i and z.i - 1 > e and (not p.vi_body_death or S._vi_alive(sd, z, i)):
                out.append(z)
    if "void" in p.irl_entries:
        vz = sd._lazy("voids_bull", lambda: [z for z in L.voids(sd.h, sd.l) if z.kind == "bull"
                                              and z.top - z.bottom >= sd.min_gap])
        out += [z for z in vz if z.i <= i and z.i - 1 > e]
    return sorted(out, key=lambda z: z.i)


def pd_high(sd, sw, i, leg_hi: float, p) -> float:
    """L14b erl_range_swings: the upper end of the dealing range for the P/D tests (leg_pd,
    leg_pd_min, add cuts) = the highest swing high CONFIRMED by bar i since the sweep extreme
    (external to external); falls back to the leg high."""
    if not p.erl_range_swings:
        return leg_hi
    hs = [q.price for q in sd.ph if q.i > sw["ext_i"] and q.known <= i]
    return float(max(hs)) if hs else leg_hi


def leg_depth_tags(entry: float, ext: float, hi: float) -> list:
    """A21.3 leg_depth_tag: the entry's retracement of the leg (hi -> ext): leg_shallow < 62%,
    leg_ote 62-79%, leg_deep > 79%, plus the third of the leg it sits in (1 = top third)."""
    leg = hi - ext
    if leg <= 0:
        return []
    r = (hi - entry) / leg
    k = "leg_deep" if r > L.OTE_HI else "leg_ote" if r >= L.OTE_LO else "leg_shallow"
    return [k, f"leg_third_{min(3, max(1, int(r * 3) + 1))}"]


def retest_add(sd, pos, tr, i, p, arm) -> None:
    """Ep01.18 add_on "retest": once price has LEFT the entry gap (a close add_retest_away_pts above
    its top) an add rests at the gap top for its retest [our interpretation of "add on the retest"].
    One shot per trade; the pyramid count and add_ok still apply."""
    if pos.get("retest_used") or pos["t1_done"] or S._nadds(pos, tr) >= len(p.adds):
        return
    top = pos.get("zone_top")          # the entry zone's top stored with the order (review fix: the old
    if top is None:                    # 2 * CE - bottom is wrong for OB / breaker / unicorn entries)
        top = 2 * pos["fvg_ce"] - pos["fvg_bottom"]
    if sd.c[i] >= top + p.add_retest_away_pts * p.es_pt and top > pos["stop"] and S._SM.add_ok(sd, pos, top, i, p):
        pos["retest_used"] = True
        arm(top)


def low_end_add(sd, pos, tr, i, p, arm) -> None:
    """E12c (006 ~51:52; "if price closes into the FVG instead of rejecting it, add once more at its
    low end"; 006: size = the smallest earlier add) / E12 add_fvg_low_end / Ep04.10 add_fvg_low: a
    BODY close inside the last add's FVG (else the entry FVG) with no close below its bottom since
    -> one add at its bottom + 1 tick. Gates: no partial taken, the units so far in open profit,
    risk room left (the arm function shrinks to the cap). Once per trade."""
    if pos.get("low_end_used") or pos["t1_done"]:
        return
    g = pos.get("last_add_g")
    if g is None:
        g = (2 * pos["fvg_ce"] - pos["fvg_bottom"], pos["fvg_bottom"], pos["fill_i"])
    top, bot, since = g
    c = sd.c[i]
    if not (bot < c <= top) or sd.c[since + 1:i + 1].min(initial=np.inf) < bot:
        return
    if not c > pos["basis"] / pos["n"]:
        return                                             # the earlier units are not in open profit
    px = bot + p.tick
    if px <= pos["stop"] or px >= c:
        return
    sizes = [q for _, _, q in tr.adds[pos.get("rung_fills", 0):]]
    size = min(sizes) if sizes else S._lots(tr.shares * p.adds[-1], p.lot)
    pos["low_end_used"] = True
    arm(px, size)


def prop_block(sd, sw, g_top: float, i: int, p):
    """A16 (cc04_008 ~0:30-5:40; 027 ~11:31): the highest propulsion block known by bar i, formed
    after the sweep extreme, that overlaps or lies under the entry gap's top. Returns (top, mt) with
    the block zone from prop_zone ("range" = its high-low, "body" = open-close) and the body
    midpoint as its MT, or None."""
    pz = [z for z in sd.propulsions() if z.i <= i and z.i > sw["ext_i"] and z.bottom <= g_top and z.top >= sw["ext"]]
    if not pz:
        return None
    z = max(pz, key=lambda z: z.top)
    top = z.top if p.prop_zone == "range" else float(max(sd.o[z.src], sd.c[z.src]))
    return float(top), float(z.mt)


# --- Silver Bullet / Ma Deuce: the same risk, stop and sizing hooks as the main engine --------------------------
# (review fix, entries_stops_sizing). sb_model.run_sb and pre_open.run_ma_deuce run after the bar loop of
# strategy.run_day, so they read the day's CLOSED trades as of their order time (never a later loss) from
# ctx.risk_view = {rs0: the E10 state at the start of the day, trades: the day's closed trades so far}.
# The main loop cannot see the extras' trades (they are produced later); the carried E10 state is replayed in
# exit-time order over all of the day's trades at the end of run_day (replay_risk_state).

def _net(tr, p) -> float:
    gross, costs = tr.pnl(p.cost_per_share)
    return gross - costs


def _closed_before(trades, ts):
    """Trades whose last exit bar is at or before the bar `ts`, in exit-time order."""
    done = [t for t in trades if t.exits and t.exits[-1][0] <= ts]
    return sorted(done, key=lambda t: t.exits[-1][0])


def extras_risk_mult(ctx, p, ts, extra=()) -> float:
    """E10 loss_halving state and Ep08.12 after_loss_mult for an order armed on the bar `ts` (Silver Bullet,
    Ma Deuce): replays the closed trades (the day's main-loop trades + `extra`, the extras' own) that exited
    at or before that bar onto the day's starting E10 state."""
    view = getattr(ctx, "risk_view", None)
    if view is None:
        return 1.0
    rs = None if view["rs0"] is None else dict(view["rs0"])
    loss = False
    for tr in _closed_before(list(view["trades"]) + list(extra), ts):
        net = _net(tr, p)
        loss = loss or net < 0
        if p.loss_halving and rs is not None:
            risk_state_update(rs, net, p)
    m = rs["m"] if (p.loss_halving and rs is not None) else 1.0
    return m * (p.after_loss_mult if loss else 1.0)


def replay_risk_state(rs: dict, rs0: dict | None, trades, p) -> None:
    """End of run_day: recompute the carried E10 state from the day's starting state over ALL of its trades
    (main loop + Silver Bullet + Ma Deuce) in exit-time order, and write it into `rs` in place."""
    if rs0 is None:
        return
    new = dict(rs0)
    for tr in sorted((t for t in trades if t.exits), key=lambda t: t.exits[-1][0]):
        risk_state_update(new, _net(tr, p), p)
    rs.update(new)
