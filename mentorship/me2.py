"""Caption-gap pass (digests/rulebook_gaps/*.md), package management_exits, chunk 2 of 3: the engine glue of its 34 specs -
management_partials_trailing_exits.md 20, 21, 23, 24, 25, 26, 27, 28, 29, 36, 49, 50, 52, 53, 54, 55, 67, 68, 87, 90, 91, 92, 93, 94, 95, 96, 98, 99, 100, 102, 103, 104, 107, 108.

Same conventions as me1.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only from the
bar that completes it, every function sits behind a Params switch of the "caption-gap pass, management_exits #2/3" block, interpretations the sources do not pin down are marked
[our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Shared pieces (spec header "Shared pieces"): `partial_close` (a fraction of the units left, lot-rounded, at least 1 lot, all when fewer remain), `raise_to` (the one place of this chunk that
lifts the stop: never lowers, capped one tick under the close, refuses a level above `pos["stop_cap"]`, honours the trail locks, the wick gate and the freeze; logs `pos["stop_log"]`).

Hooks (strategy.py): `on_fill` (after me1.on_fill), `manage` (the position loop, once per closed bar, after me1.manage), `rung_taken` (the ladder loop), `after_close`, `trail_ok` (via
me1.trail_ok), `capv` (the stop-cap clamp of the inline trails), `order_block` (the order stage: the HTF-touch / reversal-watch / late-FVG entry blocks), `chop_close` (the Chop detector)."""
from __future__ import annotations

import numpy as np
from types import SimpleNamespace

from . import levels as L
from . import me1 as M1
from . import sm2

HITS = sm2.HITS
hit = sm2.hit
POOLS = ("pool", "pool_eq")
LADDER_TRAILS = ("candle_mt", "eq_pause", "rej_block", "071", "structure")
BOOLS = ("raise_on_vi", "raise_on_sth_break", "trail_swing_at_array", "trail_after_pool", "ob_stop_to_mt_after_run", "rde_partials", "peel_singles", "pm_macro_runner", "hh_low_hold",
         "marginal_ext_warn", "stall_exits", "wick_ce_close_test", "gap_q_hold", "ref_speed_check", "opp_tear_check", "edge_bump_add", "edge_bump_guard", "late_fvg_flip", "sister_breaker_hold",
         "stall_at_htf", "chop_close", "upclose_pair_guard", "urgency_runner", "pool_lock_day_done")
NUMS = ("pool_lock_pts", "ob_retests", "htf_bank", "adr_closed_min", "ote_leave_bars", "fulcrum_speed_bars", "breaker_far_partial", "small_fvg_linger", "depth_trail")
STRS = ("trail_wick_gate", "three_array_mode", "held_hi_action")


def _S():
    from . import strategy as S
    return S


def _MG():
    from . import manage as MG
    return MG


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__)."""
    for name, ok in (("trail_wick_gate", ("", "trade", "close")), ("three_array_mode", ("", "trade", "close", "into")), ("held_hi_action", ("", "tighten", "partial")),
                     ("after_chop_exit", ("end_session", "reentry_allowed"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if (p.pool_lock_pts < 0 or not 0 <= p.pool_lock_after <= 1 or p.ob_retests < 0 or not 0 <= p.htf_bank < 1 or not 0 < p.rde_arm <= 1 or not 0 < p.rde_frac <= 1
            or not 0 < p.hh_low_frac <= 1 or p.marginal_pts < 0 or p.marginal_n < 1 or p.stall_bars < 1 or not 0 <= p.adr_closed_min < 1 or p.ote_leave_bars < 0
            or not 0 < p.pd3_close_frac <= 1 or p.pd3_near_pts < 0 or p.speed_k <= 0 or p.ref_speed_bars < 1 or not 0 < p.speed_pare <= 1 or p.stall_at_htf_bars < 1
            or p.fulcrum_speed_bars < 0 or not 0 <= p.breaker_far_partial < 1 or p.small_fvg_linger < 0 or p.urgency_stop_pts < 0
            or not 0 <= p.depth_trail < 1):
        raise ValueError("management_exits #2/3: pool_lock_pts, ob_retests, marginal_pts, pd3_near_pts, ote_leave_bars, fulcrum_speed_bars, small_fvg_linger, urgency_stop_pts >= 0; "
                         "pool_lock_after in [0, 1]; htf_bank, adr_closed_min, breaker_far_partial in [0, 1); rde_arm, rde_frac, hh_low_frac, pd3_close_frac, speed_pare in (0, 1]; "
                         "marginal_n, stall_bars, ref_speed_bars, stall_at_htf_bars >= 1; speed_k > 0; depth_trail in [0, 1)")


def any_on(p) -> bool:
    """Does any mid-trade switch of the chunk need the per-position state (pos["me2"])?"""
    return bool(any(getattr(p, k) for k in BOOLS) or any(getattr(p, k) for k in NUMS) or any(getattr(p, k) for k in STRS) or p.ladder_trail in LADDER_TRAILS)


# --- 2. helpers ---------------------------------------------------------------------------------------------------------------------------------------

def _cs(ctx) -> dict:
    """The day's cross-trade state of the chunk (the HTF touch, the late FVG): ctx.me2_state."""
    st = ctx.__dict__.get("me2_state")
    if st is None:
        st = ctx.__dict__["me2_state"] = dict(htf_touch={}, late_fvg={})
    return st


def _closed(pos) -> float:
    """The share of the position's units closed so far (every exit, not only the ladder rungs)."""
    return (pos["n"] - pos["left"]) / max(pos["n"], 1)


def _avg(pos) -> float:
    return pos["basis"] / pos["n"]


def partial_close(pos, tr, sd, ts, px, frac, why, p, units=None) -> int:
    """Shared piece: close `frac` of the units left (lot-rounded, at least 1 lot, everything when fewer remain; manage.cut_qty); `units` closes that many lots instead. Returns the quantity."""
    MG = _MG()
    q = MG.cut_qty(pos["left"], frac, p) if units is None else min(pos["left"], max(p.lot, units))
    if q <= 0:
        return 0
    MG._exit(tr, sd, ts, px, q, why, pos)
    hit("pc_" + why)
    return q


def close_all(pos, tr, sd, ts, px, why) -> None:
    _MG()._exit(tr, sd, ts, px, pos["left"], why, pos)
    hit("pc_" + why)


def raise_to(pos, new: float, why: str, c: float, p, gate: bool = True, ignore_freeze: bool = False) -> bool:
    """Shared piece `raise_stop(pos, new, why)` of this chunk: tighten the stop (side space) - never lower, never on a day trade (X5c), capped one tick under the close (the level may not sit at or
    through it) [our interpretation of "refuses a level at or through the close": clamped as me1 does], refused above `stop_cap` (small_fvg_linger). `gate=True` marks a TRAIL: it also honours the
    trail locks (me1.trail_ok), the overhead-wick gate (trail_wick_gate) and the OB-open freeze; a BE-like lock passes gate=False. Appends (why, level) to pos["stop_log"]."""
    if pos.get("day_trade"):
        return False
    new = min(float(new), float(c) - p.tick)
    if new <= pos["stop"] + 1e-12:
        return False
    cap = pos.get("stop_cap")
    if cap is not None and new > cap + 1e-12:
        return False
    if gate:
        if pos.get("no_trail") or pos.get("wgate") is not None or (pos.get("me1") or {}).get("trail_block") or (pos.get("me2") or {}).get("block_pool"):
            return False                                                # (= me1.trail_ok without the freeze)
        if pos.get("freeze") and not ignore_freeze:
            return False
    pos["stop"] = new
    pos.setdefault("stop_log", []).append((why, new))
    hit("stop_" + why)
    return True


def capv(pos, v: float) -> float:
    """The stop-cap clamp of the inline trails (strategy.py): a trail level above `stop_cap` is refused (the stop stays)."""
    cap = pos.get("stop_cap")
    return pos["stop"] if (cap is not None and v > cap + 1e-12) else v


def _piv(sd, a: int, i: int):
    """(pivot highs, pivot lows) of the closed bars a..i with absolute indices, n = 1 (a bar needs one bar on each side: the last closed bar is never a pivot yet)."""
    a = max(a, 0)
    if i - a < 2:
        return [], []
    hs, ls = L.pivots(sd.h[a:i + 1], sd.l[a:i + 1], 1)
    return ([SimpleNamespace(i=q.i + a, price=q.price, known=q.known + a) for q in hs], [SimpleNamespace(i=q.i + a, price=q.price, known=q.known + a) for q in ls])


def _kinds(pos) -> list:
    return list(pos.get("level_kinds") or [])


def _tag(tr, name: str) -> None:
    M1._tag(tr, name)


def _htf_cf(ctx):
    return getattr(ctx, "conf", None)


def _bz_far(sd, tr):
    """The breaker zone's far edge in side space (its bottom; the mirror of a bearish breaker's BH), None for a trade with no breaker."""
    if tr.bz_top is None or tr.bz_bottom is None:
        return None
    return float(min(sd.x(tr.bz_top), sd.x(tr.bz_bottom)))


def _ob_candle(sd, pos, i: int, p=None, ob_only: bool = False):
    """The down-close candle of the entry OB: an OB entry's candle is the down-close one whose MT (body mean, or the range mean under mt_mode "range") is the order's MT (fvg_ce); an FVG
    entry's is the last down-close candle before the displacement (the gap's first candle) [our interpretation, #26 only: `ob_only` (#29 - the stop to the OB MT, an OB-entry rule) returns None
    for a non-OB entry]. None if none is found."""
    ek = str(pos.get("kind") or "")
    is_ob = ek.startswith("ob") or ek.startswith("arr_ob")
    if is_ob and pos.get("fvg_ce") is not None:
        for k in range(i - 1, max(i - 40, -1), -1):
            if sd.c[k] < sd.o[k] and (abs(_mt(sd, k, p) - pos["fvg_ce"]) <= 1e-9 if p is not None else sd.c[k] - 1e-9 <= pos["fvg_ce"] <= sd.o[k] + 1e-9):
                return k
        for k in range(i - 1, max(i - 40, -1), -1):                          # (the body holds the MT: the fallback when mt_mode differs from the one that built the order)
            if sd.c[k] < sd.o[k] and sd.c[k] - 1e-9 <= pos["fvg_ce"] <= sd.o[k] + 1e-9:
                return k
    if ob_only and not is_ob:
        return None
    g0 = next((g for g in sd.gaps if abs(float(g.bottom) - float(pos.get("fvg_bottom", np.nan))) < 1e-9 and g.i <= i), None)
    j0 = (g0.i - 2) if g0 is not None else i - 1
    for k in range(j0, max(j0 - 10, -1), -1):
        if sd.c[k] < sd.o[k]:
            return k
    return None


def _mt(sd, k: int, p) -> float:
    """The MT of candle k under mt_mode (D4): the body mean, or the full range (mt_mode "range")."""
    if p.mt_mode == "range":
        return float((sd.h[k] + sd.l[k]) / 2)
    return float((sd.o[k] + sd.c[k]) / 2)


def _htf_draw(ctx, sd, pos, fill: float, i: int, p):
    """(near, far) edges in side space of the nearest untouched daily / weekly / monthly opposing array above the fill (tp3.htf_draw with the far edge), None if none."""
    cf = _htf_cf(ctx)
    if cf is None:
        return None
    from . import tp3 as T3
    from . import targets as TP
    adr = T3._adr(ctx)
    reach = 3.0 * adr if adr else np.inf
    out, bias_out = None, None
    bl = _bias_draw_lvl(ctx, sd, i)
    for r in cf.opposing_ext(T3._now(ctx, i), sd.x(fill), sd.sign, ("D", "W", "M"), (0, 1, 2, 3)):
        near, far = T3._zone_edges(sd, r)
        ex = TP.extreme_since(ctx, i, r["known"] + 1.0, sd.sign > 0)
        if ex is not None and sd.x(ex) >= near:
            continue
        if near - fill > reach:
            continue
        if out is None or near < out[0]:
            out = (float(near), float(far))
        if bl is not None and near - 1e-9 <= bl <= far + 1e-9 and (bias_out is None or near < bias_out[0]):
            bias_out = (float(near), float(far))
    if bias_out is not None:
        hit("htf_bank_bias_draw")
        return bias_out                                            # the array the bias framed the trade with (htf.table draw_ord_lvl) wins; else the nearest untouched array [our interpretation]
    return out


def _bias_draw_lvl(ctx, sd, i: int):
    """Item 36: the bias draw level (htf.table row draw_ord_lvl, side space) when the ordered draw points the trade's way, else None. Read only through bias_row_known (the table is cut at 09:30)."""
    try:
        from .entries import bias_row_known
        row = bias_row_known(ctx, i)
        if row is None:
            return None
        if int(row.get("draw_ord", 0)) != sd.sign:
            return None
        v = float(row.get("draw_ord_lvl", np.nan))
        return float(sd.x(v)) if np.isfinite(v) else None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _opp_obs(ctx, sd, upto: int, p, fill: float) -> list:
    """Item 94: the opposing order blocks above `fill` (side space) known by bar `upto`, as dict(near, ce, far) with ce = the OB's MT: the confluence rows of source OB (15m and up) and the own-
    timeframe bullish OBs of the OTHER Side (blended order block of the gap's candles), mirrored."""
    from . import tp3 as T3
    out = []
    cf = _htf_cf(ctx)
    if cf is not None:
        for r in cf.opposing_ext(T3._now(ctx, upto), sd.x(fill), sd.sign, T3.HTF_ALL, (1,)):
            a, b = T3._zone_edges(sd, r)
            if b - a > 0:
                out.append(dict(near=float(a), ce=float((a + b) / 2), far=float(b)))
    other = (getattr(ctx, "sides_map", None) or {}).get(-sd.sign)
    if other is not None:
        for g in other.gaps:
            if g.i > upto:
                break
            if g.i < 4:
                continue
            ob = L.order_block_blend(other.o, other.h, other.l, other.c, g.i - 4, g.i - 2, "bull")
            if ob is not None and np.isfinite(ob.mt) and -float(ob.top) > fill and ob.top > ob.bottom:
                out.append(dict(near=-float(ob.top), ce=-float(ob.mt), far=-float(ob.bottom)))
    return out


def _pd3_arrays(sd, pos, i: int, p, fill: float, ctx=None) -> list:
    """X7a / item 90: the three nearest arrays against the trade under the fill and over the stop, known by bar i, nearest first, as SimpleNamespace(level, top, bottom, kind): `level` is the
    line a body close must stay over (a gap's / VI's bottom, an OB's / breaker's MT, a wick's CE), `top` / `bottom` its extent (an OB: the body; a wick: body edge .. wick extreme). The ENTRY
    array itself (the FVG / OB the order filled in) is not one of the three [our interpretation: arrays "against" the trade are the ones below the entry array]. With `ctx` the lower wicks of
    the last 200 bars that are >= rip_wick_mult x the median range (the mirror of me1.wick_objs: the other Side's upper wicks) count as wick-CE arrays (the 105 example)."""
    stop = pos["stop"]
    tk = p.tick
    ent_lv = [x for x in (pos.get("fvg_bottom"), pos.get("fvg_ce")) if x is not None]

    def _entry(level: float) -> bool:
        return any(abs(level - e) <= tk + 1e-9 for e in ent_lv) or (pos.get("fvg_top") is not None and level >= float(pos["fvg_top"]) - 1e-9)

    out = []
    for g in sd.gaps:
        if g.i <= i and stop < g.bottom < fill and not _entry(float(g.bottom)):
            out.append(SimpleNamespace(level=float(g.bottom), top=float(g.top), bottom=float(g.bottom), kind="fvg"))
    for z in sd.vis("bull"):
        if z.i <= i and stop < z.bottom < fill and not _entry(float(z.bottom)):
            out.append(SimpleNamespace(level=float(z.bottom), top=float(z.top), bottom=float(z.bottom), kind="vi"))
    other = (getattr(ctx, "sides_map", None) or {}).get(-sd.sign) if ctx is not None else None
    if other is not None:
        for w in M1.wick_objs(ctx, other, i, p):                  # the other Side's upper wicks = our lower wicks, mirrored (bottom/top swap)
            lvl, top_, bot_ = -float(w.mid), -float(w.bottom), -float(w.top)
            if stop < lvl < fill and not _entry(lvl):
                out.append(SimpleNamespace(level=lvl, top=top_, bottom=bot_, kind="wick"))
    for g in sd.gaps:
        if g.i > i:
            break
        if g.i < 4:
            continue
        ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, g.i - 4, g.i - 2, "bull")
        if ob is not None and sd.c[g.i - 1] > ob.top and np.isfinite(ob.mt) and stop < ob.mt < fill and not _entry(float(ob.mt)):
            out.append(SimpleNamespace(level=float(ob.mt), top=float(ob.top), bottom=float(ob.bottom), kind="ob"))
    for z in _S()._SM._breakers(sd, p):
        if z.i <= i:
            th = z.mt if np.isfinite(z.mt) else z.bottom
            if stop < th < fill and not _entry(float(th)):
                out.append(SimpleNamespace(level=float(th), top=float(z.top), bottom=float(z.bottom), kind="breaker"))
    out.sort(key=lambda a: -a.level)
    merged = []
    for a in out:
        if merged and abs(merged[-1].level - a.level) <= p.tick:
            continue
        merged.append(a)
    return merged[:3]


# --- 3. fill time ------------------------------------------------------------------------------------------------------------------------------------

def on_fill(ctx, sd, pos, tr, o: dict, i: int, p, fill: float) -> None:
    """Fill time (side space): the state the mid-trade hooks need. The order may carry explicit values in o["me2"] (tests, forced books)."""
    S = _S()
    d = dict(o.get("me2") or {})
    d["fill_i"] = i
    d["hi"] = float(sd.h[i])
    d["nohi"] = 0
    pos["me2"] = d
    tk = p.tick
    kinds = _kinds(pos)
    lv = M1._lv(pos)
    # --- 21 trail_after_pool: nothing to wait for when the ladder holds no pool
    if p.trail_after_pool:
        pl = [v for v, k in zip(pos["levels"], kinds) if k in POOLS]
        d["pool_first"] = min(pl) if pl else None
        d["pool_hit"] = not pl
        leg = pos.get("leg")
        d["leg_eq"] = float(leg[0] + 0.5 * (leg[1] - leg[0])) if leg else None
        d["cut_i"] = None if (leg and sd.h[i] <= d["leg_eq"]) else i
        d["block_pool"] = False
    # --- 23 / 27 the short-term high above the entry, the breaker bottom, the nearest VI below
    if p.raise_on_vi and "vi" not in d:
        vis = [z for z in sd.vis("bull") if z.i < i and z.top <= fill + tk]
        if vis:
            z = max(vis, key=lambda z: z.top)
            d["vi"] = (float(z.bottom), float(z.top))
    if (p.raise_on_sth_break or p.ladder_trail == "structure") and "sth" not in d:
        hs = [q for q in sd.ph if q.known <= i - 1 and q.price > fill]
        d["sth"] = float(max(hs, key=lambda q: q.i).price) if hs else None
    if p.raise_on_sth_break and "bz_bot" not in d:
        bf = _bz_far(sd, tr)
        d["bz_bot"] = bf if bf is not None else float(pos.get("fvg_bottom", pos["stop"]))      # no breaker on the trade: the entry array's bottom [our interpretation]
    # --- 26 / 29 the entry OB
    if p.ob_retests or p.ob_stop_to_mt_after_run:
        k = _ob_candle(sd, pos, i, p)
        if "ob_open" not in d and k is not None:
            d["ob_open"] = float(sd.o[k])
        k29 = _ob_candle(sd, pos, i, p, ob_only=True) if p.ob_stop_to_mt_after_run else None
        if p.ob_stop_to_mt_after_run and "ob_mt" not in d and k29 is not None:
            k = k29
            body = abs(float(sd.o[k]) - float(sd.c[k]))
            d["ob_body"] = body
            d["ob_mt"] = _mt(sd, k, p)
            up = [q for q in range(k + 1, i + 1) if sd.c[q] > sd.o[q]]
            d["ob_valid_hi"] = float(sd.h[up[0]]) if up else None                  # the validating candle: the first up-close candle after the OB
        d["ob_n"] = 0
    # --- 28 the overhead wick gate
    if p.trail_wick_gate:
        _wick_gate(sd, pos, d, i, fill, p)
    # --- 36 the HTF draw
    if p.htf_bank and "htf_draw" not in d:
        d["htf_draw"] = _htf_draw(ctx, sd, pos, fill, i, p)
    # --- 50 / 92 the NWOG; the peel (50) is armed only when this NWOG is the trade's target gap (a ladder rung lies inside it) or once a rung at its CE has filled (rung_taken)
    if (p.peel_singles or p.gap_q_hold) and "nwog" not in d:
        d["nwog"] = M1._nwog_zone(ctx, sd, i)
    if p.peel_singles and "peel_armed" not in d:
        z_ = d.get("nwog")
        tol_ = max(tk, p.exit_before_pts * p.es_pt)
        d["peel_armed"] = bool(z_ is not None and any(z_[0] - tol_ <= v <= z_[1] + tol_ for v in pos["levels"]))
    # --- 52 a PM trade keeps its last unit as a runner to 15:50
    if p.pm_macro_runner and tr.session == "PM" and not pos.get("runner") and len(pos["fracs"]) >= 2:
        lv0 = pos["levels"][:-1] if (pos.get("final_T") and len(pos["levels"]) > 1) else pos["levels"]
        pos.update(runner=True, levels=list(lv0)[:max(1, len(pos["fracs"]) - 1)], final_T=False)
        d["pm_runner"] = True
    # --- 67 the 105 ladder: the wick-CE rung is a 10 % rung
    if p.wick_ce_close_test and kinds and kinds[0] in ("wick", "wick_ce") and len(pos["fracs"]) >= 2:
        fr = list(pos["fracs"])
        rest = sum(fr[1:])
        if rest > 0:
            pos["fracs"] = tuple([0.1] + [f * 0.9 / rest for f in fr[1:]])
            d["wick_w"] = None
            d["wick_rung"] = True
    # --- 87 the OTE band's 62 % line
    if p.ote_leave_bars and "ote62" not in d and (str(pos.get("kind") or "") in ("ote", "arr_ote") or d.get("ote_fill")):      # (review fix: an OTE limit placed through ote_adjust on the FVG path is an OTE entry too: the order's tags["me2"]["ote_fill"])
        leg = pos.get("leg") or (float(pos["ext"]), float(sd.h[int(o.get("ext_i", i)):i + 1].max()))        # the entry array "ote": the leg from the sweep extreme to the high made before the fill
        ext, hi = leg
        if hi > ext:
            d["ote62"] = float(hi - p.ote_band[0] * (hi - ext))
    # --- 90 the three arrays against the trade
    if p.three_array_mode and "pd3" not in d:
        d["pd3"] = _pd3_arrays(sd, pos, i - 1, p, fill, ctx)
    # --- 94 the opposing arrays on the way
    if p.opp_tear_check and "opp" not in d:
        from . import tp3 as T3
        fin = lv[-1] if lv else np.inf
        d["opp"] = [dict(near=g[0], ce=g[1], far=g[2]) for g in T3.gap_registry(ctx, sd, i, p, fill, {}) if g[0] < fin]
        d["opp"] += [r for r in _opp_obs(ctx, sd, i - 1, p, fill) if r["near"] < fin]         # (review fix: the opposing order blocks - their MT - are array rows too)
        d["opp"].sort(key=lambda r: r["near"])
        d["opp_done"] = set()
        d["opp_win"] = None
    # --- 95 the broken FVG edge
    if (p.edge_bump_add or p.edge_bump_guard) and "edge" not in d:
        # the opposing gap the entry leg broke through: a bar of the leg (from the sweep extreme on) traded over its far edge after it formed [review fix: "broke through in the entry leg", not "formed in it"]
        e_i = int(o.get("ext_i", i))
        gs = [g for g in M1.opp_gaps(ctx, sd, i - 1) if g.top <= fill + tk and g.i >= e_i - 40 and float(sd.h[max(g.i + 1, e_i):i].max(initial=-np.inf)) > g.top + 1e-9]
        d["edge"] = float(max(gs, key=lambda g: g.top).top) if gs else None
        d["bumps"] = 0
        d["bump_on"] = False
    # --- 102 the last two consecutive same-colour candles before the entry (down-close in side space: the mirror of the up-close pair of a short)
    if p.upclose_pair_guard and "pair_ref" not in d:
        d["pair_ref"] = None
        for k in range(i - 1, max(i - 40, 0), -1):
            if sd.c[k] < sd.o[k] and sd.c[k - 1] < sd.o[k - 1]:
                d["pair_ref"] = float(max(sd.o[k], sd.o[k - 1]))
                break
        d["pair_b"] = None
    # --- 103 the fulcrum pool and the -0.5 SD level: fulcrum-anchored trades only (item 66: Params.sd_anchor == "fulcrum"; with fulcrum_exit on, the trade must carry the fulcrum_ladder
    #     tag = tp4.fulcrum_ladder built its pool + beyond / -0.5 SD / -1 SD rungs; the "trail" mode has a single -1 SD rung and no pool: nothing to watch)
    if p.fulcrum_speed_bars and "fp_pool" not in d:
        scope = p.sd_anchor == "fulcrum" and (not p.fulcrum_exit or "fulcrum_ladder" in str(getattr(tr, "lv_tags", "") or ""))
        pl = [v for v, k in zip(pos["levels"], kinds) if k in POOLS] if scope else []
        sdl = [v for v, k in zip(pos["levels"], kinds) if k in ("sd_half", "sd")] if scope else []
        d["fp_pool"] = min(pl) if pl else None
        d["fp_sd"] = min([x for x in sdl if not pl or x > min(pl)], default=None)
        d["fp_b"] = None
    # --- 104 / 107
    if p.breaker_far_partial:
        d["bz_far"] = _bz_far(sd, tr)
    if p.small_fvg_linger:
        d["htf_hi"] = d.get("htf_hi", M1._htf_entry_hi(ctx, sd, i, fill))
        d["sf"] = None
    # --- 91 the 09:30 high and the highs that formed after it
    if p.held_hi_action:
        d["bh_done"] = False
    # --- 99 the week gate
    if p.stall_at_htf:
        d["htf_stall_on"] = None


# --- 4. the ladder loop hook --------------------------------------------------------------------------------------------------------------------------

def rung_taken(ctx, sd, pos, tr, k: int, level: float, i: int, p) -> None:
    """A ladder rung k was filled on bar i (units may remain; pos["k"] is already k + 1)."""
    d = pos.get("me2")
    if not d:
        return
    MG = _MG()
    kinds = _kinds(pos)
    kind = kinds[k] if k < len(kinds) else ""
    n = len(M1._lv(pos))
    c = float(sd.c[i])
    # 21: a filled pool rung is the pool run
    if p.trail_after_pool and kind in POOLS:
        d["pool_hit"] = True
    if not pos["left"]:
        return
    ts = ctx.idx[i]
    if p.pool_lock_pts > 0:
        hit("eval_pool_lock")
    # 20: the last pool-kind rung before the final one has run: the stop tight under it
    if p.pool_lock_pts > 0 and k < n - 1 and kind in POOLS and not any(x in POOLS for x in kinds[k + 1:n - 1]) and _closed(pos) >= p.pool_lock_after - 1e-9:
        pos["no_reentry"] = True                                       # (review fix: the spec sets these unconditionally - the raise itself may be refused by the clamp / the stop cap)
        pos["pool_locked"] = True
        _tag(tr, "pool_lock")
        hit("pool_lock")
        raise_to(pos, level - p.pool_lock_pts * p.es_pt, "pool_lock", c, p, gate=False)
    # 36: a planned rung that prints while price is at the HTF draw array banks too (the trigger "planned target prints while at that array")
    if p.htf_bank and d.get("htf_draw") and not d.get("htf_banked") and level >= d["htf_draw"][0] - 1e-9:
        _bank(ctx, sd, pos, tr, d, i, ts, p, float(sd.o[i]), c, _avg(pos), level)
        if not pos["left"]:
            return
    # 24: a non-final array rung: the stop under the latest 1m swing low
    if p.trail_swing_at_array and kind == "array" and k < n - 1:
        hit("eval_swing_at_array")
        _, lows = _piv(sd, max(ctx.start, pos["fill_i"] - 1), i)
        lows = [q for q in lows if q.i >= pos["fill_i"]]                      # (review fix: the latest pivot low SINCE the fill - a pre-fill retracement low is not one)
        if lows and raise_to(pos, lows[-1].price - p.tick, "swing_at_array", c, p):
            hit("swing_at_array")
    # 25 rej_block: after the last non-final rung, 1 tick beyond the wicks of the last 1-2 closed bars
    if p.ladder_trail in ("rej_block", "071") and p.mgmt in ("ladder", "unit") and k == n - 2:
        lo = float(min(sd.l[max(i - 1, 0)], sd.l[i]))
        if raise_to(pos, lo - p.tick, "rej_block", c, p):
            hit("trail_rej_block")
    # 52: the first partial of a PM runner trade: +1 pt (retried on the next bars while the close is still under avg + 1), and the next rung becomes the next untaken pool rung (the pool rungs
    #     carry pool_beyond_pts already: sd._exit_px(pool) = level + pool_beyond_pts) [our interpretation of "set the next rung to the next untaken pool + pool_beyond_pts"]
    if d.get("pm_runner") and not d.get("pm_first"):
        d["pm_first"] = True
        if raise_to(pos, _avg(pos) + 1.0 * p.es_pt, "pm_macro", c, p, gate=False):
            hit("pm_macro_first")
        if pos["stop"] < _avg(pos) + 1.0 * p.es_pt - 1e-9:
            d["pm_stop_pending"] = True                                # (the close was under avg + 1: the clamp kept the level under the close; the full +1 follows on a later bar)
        nxt = k + 1
        if nxt < len(pos["levels"]) and nxt < len(kinds) and kinds[nxt] not in POOLS:
            later = [pos["levels"][q] for q in range(nxt + 1, min(len(pos["levels"]), len(kinds))) if kinds[q] in POOLS]
            if later:
                pos["levels"][nxt] = float(min(later))
                pos["level_kinds"][nxt] = "pool"
                hit("pm_macro_retarget")
    # 67: the wick-CE rung filled: BE + pad, the 5m close test starts
    if d.get("wick_rung") and k == 0:
        d["wick_w"] = float(level)
        d["w5"] = []
        if not pos.get("day_trade"):
            MG.be_move(pos, p)
        hit("wick_ce_first")
    # 92: a rung at the NWOG CE: the lower quarter is the hold line (and, 50, arms the runner peel: "bulk partial at the NWOG CE")
    if (p.gap_q_hold or p.peel_singles) and d.get("nwog"):
        lo, hi = d["nwog"]
        ce = (lo + hi) / 2
        if abs(level - ce) <= max(p.tick, p.exit_before_pts * p.es_pt) + 1e-9:
            if p.peel_singles:
                d["peel_armed"] = True
            if p.gap_q_hold:
                d["gap_q"] = float(lo + 0.25 * (hi - lo))
                d["gap_ce_i"] = i
                hit("gap_q_set")
    # 108: T1 on an urgent leg (no down-close candle since the fill): most of the position is off, the runner keeps the farther target on a tight stop
    if p.urgency_runner and k == 0 and not d.get("urg") and n >= 2:
        hit("eval_urgency")
        if all(sd.c[q] >= sd.o[q] for q in range(pos["fill_i"] + 1, i + 1)):
            d["urg"] = True
            keep = max(p.lot, _S()._lots(pos["n"] * (p.runner_frac or 0.2), p.lot))
            # the spec: "the last rung keeps runner_frac (or 0.2)", the rest of the ladder unchanged - the rungs between T1 and the last one share what is left above the runner [review fix: no extra
            # bulk exit]; with only two rungs there is no rung to shrink and urgency_bulk (off) is the explicit alternative: the T1 bulk exit of the first build
            mid = list(range(k + 1, n - 1))
            if mid:
                share = max(0.0, (pos["left"] - keep) / max(pos["n"], 1))
                fr = list(pos["fracs"])
                tot = sum(fr[q] for q in mid) or 1.0
                for q in mid:
                    fr[q] = share * fr[q] / tot
                pos["fracs"] = tuple(fr)
            elif p.urgency_bulk and pos["left"] > keep:
                MG._exit(tr, sd, ts, level, pos["left"] - keep, "urgency_bulk", pos)
            raise_to(pos, c - p.urgency_stop_pts * p.es_pt, "urgency", c, p, gate=False)
            _tag(tr, "urgency")
            hit("urgency_runner")


# --- 5. mid-trade management --------------------------------------------------------------------------------------------------------------------------

def _wick_gate(sd, pos, d, i: int, ref: float, p) -> None:
    """28: pos["wgate"] = the CE of the upper wick of the highest bar (up to 60 bars back) that sits above price and whose upper wick is >= 25 % of its range [our interpretation of 'blocks the path'];
    None if there is none."""
    best, bh = None, -np.inf
    for k in range(max(0, i - 60), i + 1):
        rng = float(sd.h[k] - sd.l[k])
        if rng <= 0:
            continue
        top = float(max(sd.o[k], sd.c[k]))
        wick = float(sd.h[k]) - top
        ce = (top + float(sd.h[k])) / 2
        if wick >= 0.25 * rng and ce > ref + 1e-9 and sd.h[k] > bh:
            best, bh = ce, float(sd.h[k])
    pos["wgate"] = best
    d["wg_stop"] = pos["stop"]
    if best is not None:
        hit("wick_gate_set")


def _bank(ctx, sd, pos, tr, d, i, ts, p, o, c, avg, px) -> None:
    """36: the HTF draw bank - htf_bank of the units left at `px`, the stop to BE + be_pad_pts, no adds, the session's counter-setup block (order_block)."""
    d["htf_banked"] = True
    near, far = d["htf_draw"]
    partial_close(pos, tr, sd, ts, px, p.htf_bank, "htf_bank", p)
    raise_to(pos, avg + p.be_pad_pts * p.es_pt, "htf_bank", c, p, gate=False)
    pos["no_adds"] = True
    pos["add"] = None
    a_, b_ = sorted((float(sd.x(near)), float(sd.x(far))))
    _cs(ctx)["htf_touch"][sd.sign] = (a_, b_, i)
    _tag(tr, "htf_bank")
    hit("htf_bank")


def manage(ctx, sd, pos, tr, i: int, ts, p, pctx=None, psides=None, ppos=None) -> None:
    """Mid-trade (bar i closed): the stop moves, exits and tags of the chunk. Called once per bar after me1.manage; a stop moved here applies from the next bar."""
    d = pos.get("me2")
    if not d or not pos["left"] or i <= pos["fill_i"]:
        return
    o, h, l, c = float(sd.o[i]), float(sd.h[i]), float(sd.l[i]), float(sd.c[i])
    t, tf = int(ctx.t[i]), ctx.tf
    tk = p.tick
    avg = _avg(pos)
    newhi = h > d["hi"] + 1e-9
    lv = M1._lv(pos)

    # --- 28 overhead-wick gate: opens when a bar trades (or closes) through the CE; a stop move since the last bar re-reads the next overhead wick
    if p.trail_wick_gate:
        if pos.get("wgate") is not None:
            if (c if p.trail_wick_gate == "close" else h) > pos["wgate"] + 1e-9:
                pos["wgate"] = None
                hit("wick_gate_open")
        if pos.get("wgate") is None and pos["stop"] > d.get("wg_stop", pos["stop"]) + 1e-12:
            _wick_gate(sd, pos, d, i, c, p)
    # --- 21 pool-hit
    if p.trail_after_pool:
        if not d["pool_hit"] and d.get("pool_first") is not None and h >= d["pool_first"]:
            d["pool_hit"] = True
        if d.get("cut_i") is None and d.get("leg_eq") is not None and h > d["leg_eq"]:
            d["cut_i"] = i
        d["block_pool"] = bool((not d["pool_hit"]) and d.get("cut_i") is not None)
        if d["block_pool"]:
            hit("eval_trail_after_pool")

    # ---------------- exits first
    # 90 three arrays against the trade
    if p.three_array_mode and d.get("pd3") and len(d["pd3"]) >= 3:
        if _three_arrays(ctx, sd, pos, tr, d, i, ts, p, o, l, c):
            return
    # 104 the breaker's far edge
    if p.breaker_far_partial and d.get("bz_far") is not None and not d.get("bz_far_done"):
        hit("eval_bz_far")
    if p.breaker_far_partial and d.get("bz_far") is not None and not d.get("bz_far_done") and l < d["bz_far"] - 1e-9:
        d["bz_far_done"] = True
        partial_close(pos, tr, sd, ts, min(o, d["bz_far"]), p.breaker_far_partial, "bz_far", p)
        pos["no_adds"] = True
        pos["add"] = None
        _tag(tr, "bz_far")
        hit("bz_far")
        if not pos["left"]:
            return
    # 53 the swing low between two rising highs must hold
    if p.hh_low_hold and (pos["t1_done"] or _closed(pos) > 0):
        hit("eval_hh_low")
        _hh_low(sd, pos, tr, d, i, ts, p, o, h, l)
        if not pos["left"]:
            return
    # 98 the sister index's breaker
    if p.sister_breaker_hold:
        _sister(ctx, sd, pos, tr, d, i, p, pctx, psides, ppos)
    # 36 the HTF draw bank
    if p.htf_bank and d.get("htf_draw") and not d.get("htf_banked"):
        hit("eval_htf_bank")
    if p.htf_bank and d.get("htf_draw") and not d.get("htf_banked") and h >= d["htf_draw"][0]:
        _bank(ctx, sd, pos, tr, d, i, ts, p, o, c, avg, d["htf_draw"][0] if o < d["htf_draw"][0] else o)
        if not pos["left"]:
            return
    # 99 a profitable trade that stops delivering inside an HTF array in a fast intraweek move
    if p.stall_at_htf and _stall_htf(ctx, sd, pos, tr, d, i, ts, p, c, avg):
        return
    # 55 runner stall exits
    if p.stall_exits and _stall_exits(ctx, sd, pos, tr, d, i, ts, p, o, h, l, c):
        return
    # 54 marginal new extremes
    if p.marginal_ext_warn and _marginal(ctx, sd, pos, tr, d, i, ts, p, h, c):
        return
    # 96 the late-day FVG flip
    if p.late_fvg_flip and _late_fvg(ctx, sd, pos, tr, d, i, ts, p, c, t):
        return
    # 91 the broken session highs
    if p.held_hi_action and _held_hi(ctx, sd, pos, tr, d, i, ts, p, c, l, h, t):
        return
    # 92 the NWOG lower quarter
    if p.gap_q_hold and d.get("gap_q") is not None:
        hit("eval_gap_q")
    if p.gap_q_hold and d.get("gap_q") is not None and i > d["gap_ce_i"] and l < d["gap_q"] - 1e-9:
        close_all(pos, tr, sd, ts, min(o, d["gap_q"]), "gap_q")
        hit("gap_q_exit")
        return
    # 93 the in-trade speed check at the next reference
    if p.ref_speed_check and _ref_speed(ctx, sd, pos, tr, d, i, ts, p, h, l, c, lv):
        return
    # 94 the opposing arrays' tear-through
    if p.opp_tear_check:
        _opp_tear(sd, pos, tr, d, i, h, l)
    # 95 the broken FVG edge
    if (p.edge_bump_add or p.edge_bump_guard) and d.get("edge") is not None:
        _edge_bump(ctx, sd, pos, tr, d, i, p, l)
    # 102 the pair guard
    if p.upclose_pair_guard and d.get("pair_ref") is not None:
        _pair(sd, pos, tr, d, i, h)
    # 103 the speed after the fulcrum break
    if p.fulcrum_speed_bars and d.get("fp_pool") is not None and d.get("fp_sd") is not None and _fulcrum(sd, pos, tr, d, i, ts, p, h, l, c):
        return
    # 107 the small 5m FVG linger
    if p.small_fvg_linger and pos["t1_done"]:
        _small_fvg(ctx, sd, pos, tr, d, i, p)
    # 87 the OTE band must be left quickly
    if p.ote_leave_bars and d.get("ote62") is not None and not d.get("ote_done"):
        hit("eval_ote")
        n_post = i - pos["fill_i"]
        if any(sd.c[q] > d["ote62"] for q in range(pos["fill_i"] + 1, i + 1)):
            d["ote_done"] = True
        elif n_post >= p.ote_leave_bars:
            d["ote_done"] = True
            partial_close(pos, tr, sd, ts, c, 0.5, "ote_slow", p)
            _tag(tr, "ote_slow")
            hit("ote_slow")
            if not pos["left"]:
                return
    # 68 the ADR5 projection from the day's low: at least adr_closed_min closed
    if p.adr_closed_min > 0 and not d.get("adr_done") and not pos.get("day_trade"):
        adr = _S().adr5(list(getattr(ctx, "hist", None) or [])[-5:])
        if adr:
            # [our interpretation, review fix] the day's low = the low of the Side's bars since the array start (the whole trading day, Asia / London / pre-open included); a projection already exceeded before the
            # fill tops the closed share up on the first managed bar (the trade is in while price is beyond ADR5 from the day's low)
            lo_ = float(sd.l[:i + 1].min())
            if h >= lo_ + adr:
                d["adr_done"] = True
                hit("eval_adr_closed")
                if _closed(pos) < p.adr_closed_min - 1e-9:
                    want = int(round(p.adr_closed_min * pos["n"])) - (pos["n"] - pos["left"])
                    if want > 0:
                        px_ = max(o, lo_ + adr)
                        partial_close(pos, tr, sd, ts, px_, 0, "adr_true_up", p, units=want)
                        hit("adr_true_up")
                        if not pos["left"]:
                            return
    # 49 running down equity: one tranche above each short-term high once armed
    if p.rde_partials and _rde(sd, pos, tr, d, i, ts, p, o, h, lv, avg):
        return
    # EXIT-DEPTH B (scorecard card, Mase 2026-11-08): from depth_trail of the way to the final rung the stop trails one tick under each closed bar's low
    if p.depth_trail:
        _depth_trail(pos, d, i, h, l, c, p, lv, avg)
    # 50 / 92 the runner peel
    if p.peel_singles and _peel(ctx, sd, pos, tr, d, i, ts, p, o, h, l, c, avg):
        return
    # 52 the +1 pt stop of the first partial, retried while the close sat under avg + 1
    if d.get("pm_stop_pending"):
        raise_to(pos, avg + 1.0 * p.es_pt, "pm_macro", c, p, gate=False)
        if pos["stop"] >= avg + 1.0 * p.es_pt - 1e-9:
            d["pm_stop_pending"] = False
            hit("pm_macro_first")
    # 52 a PM runner is closed at 15:50
    if d.get("pm_runner") and t + tf >= 950:
        close_all(pos, tr, sd, ts, c, "pm_macro_exit")
        hit("pm_macro_exit")
        return
    # 67 the 5m close test around the wick CE
    if d.get("wick_w") is not None and (t + tf) % 5 == 0:
        w5 = d["w5"]
        W = d["wick_w"]
        if not d.get("fund_done"):
            if c > W:
                w5.append(1)
            elif w5 and w5[-1] == 1:
                d["fund_done"] = True
                partial_close(pos, tr, sd, ts, c, 0, "fund", p, units=_S()._lots(pos["n"] * 0.3 + 1e-9, p.lot))      # 30 % of the position (3 of 10 units)
                hit("wick_ce_fund")
                if not pos["left"]:
                    return
            else:
                w5.append(0)

    # ---------------- stop raisers
    _raisers(ctx, sd, pos, tr, d, i, p, o, h, l, c, newhi, avg, tf)

    # ---- bookkeeping (after everything read the running state)
    if newhi:
        d["hi"] = h
        d["nohi"] = 0
    else:
        d["nohi"] += 1


def _three_arrays(ctx, sd, pos, tr, d, i, ts, p, o, l, c) -> bool:
    """90 X7-three-array-exit-trigger: A1 may be traded through, A2 is a warning, A3 decides by `three_array_mode` ("trade" low under A3's far edge = close all, "close" a close under the A3 level =
    pd3_close_frac once, "into" a low into A3's body top = close all). A3 sitting within pd3_near_pts of A2 (078): the trigger moves to A2. A sister-index breaker breach (item 98, pos["warn"]) counts
    as one array already broken: with A1 and A2 broken it completes the three in "trade" mode. The near-A2 exception (078) is "close everything when price reaches A2": a low into A2's top
    exits in every mode."""
    a1, a2, a3 = d["pd3"][:3]
    if l <= a2.top + 1e-9 and not d.get("pd3_warned"):
        d["pd3_warned"] = True
        _tag(tr, "pd3_warn")
    trig = a3
    hit("eval_pd3_mode")
    mode = p.three_array_mode
    if p.pd3_near_pts > 0 and abs(a3.level - a2.level) <= p.pd3_near_pts * p.es_pt + 1e-9:
        hit("pd3_near")
        if l <= a2.top + 1e-9:
            close_all(pos, tr, sd, ts, min(o, a2.top), "pd3_near")
            hit("pd3_near_exit")
            return True
        return False
    if mode == "trade":
        broken_sis = pos.get("sis_warn", 0) >= 1 and l < a1.bottom - 1e-9 and l < a2.bottom - 1e-9
        if l < trig.bottom - 1e-9 or broken_sis:
            close_all(pos, tr, sd, ts, min(o, trig.bottom) if l < trig.bottom - 1e-9 else c, "pd3_trade")
            hit("pd3_trade")
            return True
    elif mode == "close":
        if not d.get("pd3_close_done") and c < trig.level - 1e-9:
            d["pd3_close_done"] = True
            partial_close(pos, tr, sd, ts, c, p.pd3_close_frac, "pd3_close", p)
            hit("pd3_close")
            return not pos["left"]
    elif mode == "into":
        if l <= trig.top + 1e-9:
            close_all(pos, tr, sd, ts, min(o, trig.top), "pd3_into")
            hit("pd3_into")
            return True
    return False


def _hh_low(sd, pos, tr, d, i, ts, p, o, h, l) -> None:
    """53 X3-runner-swing-low-must-hold: after the first partial, a bar that exceeds the latest 1m pivot high H1 (a new high taking out the previous one) records the lowest low between H1 and
    that bar; a later trade under it closes `hh_low_frac` of the rest."""
    hl = d.get("hh_low")
    if hl is not None and l < hl - 1e-9:
        d["hh_low"] = None
        partial_close(pos, tr, sd, ts, min(o, hl), p.hh_low_frac, "hh_low", p)
        _tag(tr, "hh_low")
        hit("hh_low_exit")
        return
    highs, _ = _piv(sd, max(pos["fill_i"] - 1, 0), i - 1)
    highs = [q for q in highs if q.i >= pos["fill_i"] and q.known <= i - 1]
    if highs:
        h1 = highs[-1]
        if h > h1.price + 1e-9 and d.get("hh_h1") != h1.i:
            d["hh_h1"] = h1.i
            d["hh_low"] = float(sd.l[h1.i + 1:i].min()) if i - 1 > h1.i else float(sd.l[i])      # the swing low between the two highs (the bars after H1 up to the one before the break)
            hit("hh_low_set")


def _sister(ctx, sd, pos, tr, d, i, p, pctx, psides, ppos) -> None:
    """98 X8-sister-index-breaker-hold: the sister's bullish breaker of the same leg (known at the fill); a sister CLOSE under its bottom is one array against the trade (pos["warn"] += 1, once per
    breach); with no sister data the switch is a no-op."""
    if psides is None or pctx is None or ppos is None:
        return
    try:
        ps = psides[sd.sign]
        if "sis" not in d:
            jf = ppos.index.searchsorted(ctx.idx[pos["fill_i"]], side="right") - 1
            je = ppos.index.searchsorted(ctx.idx[pos.get("ext_i", pos["fill_i"])], side="right") - 1
            z = L.breaker_zone(ps.o, ps.h, ps.l, ps.c, max(pctx.start, je - 40), max(je, 0), jf, kind="bull") if jf >= pctx.start else None
            d["sis"] = None if z is None else (float(min(z.top, z.bottom)), float(max(z.top, z.bottom)))
            d["sis_below"] = False
        if d["sis"] is None:
            return
        j = ppos.index.searchsorted(ctx.idx[i], side="right") - 1
        if j < pctx.start:
            return
        hit("eval_sister")
        if ps.c[j] < d["sis"][0] - 1e-9:
            if not d["sis_below"]:
                d["sis_below"] = True
                pos["warn"] = pos.get("warn", 0) + 1
                pos["sis_warn"] = pos.get("sis_warn", 0) + 1          # (review fix: the three-array trigger reads this counter only - #94's opposing-array warn is no sister breach)
                _tag(tr, "sister_breaker")
                hit("sister_breaker_warn")
        else:
            d["sis_below"] = False
    except KeyError:                                                    # (the partner has no Side of this direction: no-op)
        return


def _week_range_ok(ctx, i: int) -> bool:
    """99: the week's range so far (the completed days of the ISO week plus today's bars, real prices) >= 1.5 x ADR5, on a Monday / Tuesday."""
    if ctx.day.weekday() > 1:
        return False
    adr = _S().adr5(list(getattr(ctx, "hist", None) or [])[-5:])
    if not adr:
        return False
    wk = ctx.day.isocalendar()[:2]
    his, los = [float(np.max(ctx.h[:i + 1]))], [float(np.min(ctx.l[:i + 1]))]
    for g in getattr(ctx, "hist", None) or []:
        if g.index[0].date().isocalendar()[:2] == wk:
            his.append(float(g.high.max()))
            los.append(float(g.low.min()))
    return (max(his) - min(los)) >= 1.5 * adr


def _stall_htf(ctx, sd, pos, tr, d, i, ts, p, c, avg) -> bool:
    """99 X8-profitable-stall-exit: in a fast intraweek move (week range >= 1.5 x ADR5, Monday / Tuesday) a trade in profit inside a daily / weekly / monthly array that makes no new extreme for
    stall_at_htf_bars bars is closed at the close (the weekly reversal_watch flag is backtest.week_state)."""
    if pos.get("stall_off"):
        return False                                                    # (caption-gap X11-two-stage-pm-delivery: suspended until 15:00 on a two-session PM)
    if not d.get("htf_stall_on"):
        d["htf_stall_on"] = _week_range_ok(ctx, i)
    if not d["htf_stall_on"]:
        return False
    hit("eval_stall_htf_week")
    if c <= avg or d["nohi"] < p.stall_at_htf_bars:
        return False
    cf = _htf_cf(ctx)
    if cf is None:
        return False
    import pandas as pd
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    hit("eval_stall_htf")
    if not (set(cf.at(now, float(sd.x(c)), -sd.sign)) & {"D", "W", "M"}):
        return False
    close_all(pos, tr, sd, ts, c, "htf_stall")
    _tag(tr, "htf_stall")
    hit("htf_stall_exit")
    return True


def _stall_exits(ctx, sd, pos, tr, d, i, ts, p, o, h, l, c) -> bool:
    """55 X3-runner-stall-exits: active once >= 75 % is closed and stall_bars bars passed without a new high. (a) a trade back into the body of the most recent down-close candle = 1 unit off
    (once); (b) a poke above a relative equal high of the last 30 bars followed by a close back below it closes the rest (side space, as the spec's test)."""
    if pos.get("stall_off"):
        return False                                                    # (caption-gap X11-two-stage-pm-delivery)
    hit("eval_stall_exits")
    if not (_closed(pos) >= 0.75 - 1e-9 and d["nohi"] >= p.stall_bars and h <= d["hi"] + 1e-9):
        d["stall_on"] = False                                           # (review fix: evaluated on every bar - a new extreme resets the stall counter and switches the exits off again)
        return False
    if not d.get("stall_on"):
        d["stall_on"] = True
        hit("stall_on")
    if not d.get("rebal_done"):
        for k in range(i - 1, max(i - 30, pos["fill_i"] - 1), -1):
            if sd.c[k] < sd.o[k]:
                if l <= float(sd.o[k]) + 1e-9:
                    d["rebal_done"] = True
                    partial_close(pos, tr, sd, ts, c, 0, "stall_rebal", p, units=p.lot)
                    hit("stall_rebal")
                break
        if not pos["left"]:
            return True
    a = max(0, i - 30)
    highs, lows_ = _piv(sd, a, i - 1)
    if len(highs) >= 2:
        for lvl in L.equal_levels([q.price for q in highs], p.eq_tol_pts * p.es_pt):
            if h > lvl + 1e-9:
                d["reh_poke"] = max(d.get("reh_poke") or -np.inf, lvl)
    if d.get("reh_poke") is not None and c < d["reh_poke"] - 1e-9:
        close_all(pos, tr, sd, ts, c, "stall_reh")
        hit("stall_reh")
        return True
    if p.stall_reh_against and len(lows_) >= 2:                          # the 'against the trade' reading of (b): a poke under a relative equal LOW (side space) followed by a close back above it
        for lvl in L.equal_levels([q.price for q in lows_], p.eq_tol_pts * p.es_pt):
            if l < lvl - 1e-9:
                d["rel_poke"] = min(d.get("rel_poke") or np.inf, lvl)
        if d.get("rel_poke") is not None and c > d["rel_poke"] + 1e-9:
            close_all(pos, tr, sd, ts, c, "stall_rel")
            hit("stall_rel")
            return True
    return False


def _marginal(ctx, sd, pos, tr, d, i, ts, p, h, c) -> bool:
    """54 X3-marginal-lower-lows-warning: a bar making a new session extreme by less than marginal_pts that closes back inside it counts; marginal_n of them before the final rung = no adds (and,
    with marginal_exit, the rest closed)."""
    ext = float(sd.h[ctx.start:i].max()) if i > ctx.start else float(sd.h[i])
    hit("eval_marginal")
    if h > ext + 1e-9 and (h - ext) < p.marginal_pts * p.es_pt - 1e-9 and c <= ext + 1e-9 and pos["k"] < len(M1._lv(pos)):
        d["marg_n"] = d.get("marg_n", 0) + 1
        hit("marginal_bar")
        if d["marg_n"] >= p.marginal_n and not d.get("marg_done"):
            d["marg_done"] = True
            pos["no_adds"] = True
            pos["add"] = None
            _tag(tr, "marginal_ext")
            hit("marginal_ext")
            if p.marginal_exit:
                close_all(pos, tr, sd, ts, c, "marginal")
                return True
    return False


def _late_fvg(ctx, sd, pos, tr, d, i, ts, p, c, t) -> bool:
    """96 X8-late-day-fvg-lost-hod-in: from last_hour[0] the latest bearish gap formed after the session high; a close above its top = support, a later close under its bottom closes the runner
    (the high of day is in). New entries in the trade direction are blocked while price is under the gap (order_block)."""
    if t < p.last_hour[0]:
        return False
    hi_i = ctx.start + int(np.argmax(sd.h[ctx.start:i + 1])) if i >= ctx.start else i
    gs = [g for g in M1.opp_gaps(ctx, sd, i) if g.i > hi_i]
    if not gs:
        return False
    g = max(gs, key=lambda g: g.i)
    if d.get("lf_g") != g.i:
        d["lf_g"], d["lf_sup"] = g.i, False
    _cs(ctx)["late_fvg"][sd.sign] = (float(g.bottom), float(g.top), i)
    hit("eval_late_fvg")
    if c > g.top + 1e-9:
        d["lf_sup"] = True
    elif d["lf_sup"] and c < g.bottom - 1e-9:
        close_all(pos, tr, sd, ts, c, "hod_in")
        _tag(tr, "hod_in")
        hit("hod_in_exit")
        return True
    return False


def _held_hi(ctx, sd, pos, tr, d, i, ts, p, c, l, h, t) -> bool:
    """91 X8-hold-above-broken-session-highs: the candidates are the 09:30 bar's high and the pivot highs confirmed since 09:30; a candidate counts once a LATER closed bar traded above it (broken).
    BH = the highest broken candidate (the higher of the 09:30 high and the 09:53 swing high of 009). A 1m close under BH on a bar after the one that broke it triggers held_hi_action
    ("tighten": the stop under the bar's low; "partial": half the rest), once [our interpretation: ICT states the warning, not the response]."""
    if d["bh_done"]:
        return False
    k0 = next((q for q in range(ctx.start, i + 1) if ctx.t[q] == 570), None)
    if k0 is None or k0 >= i:
        return False
    highs, _ = _piv(sd, k0 - 1, i - 1)
    cand = [(float(sd.h[k0]), k0)] + [(q.price, q.i) for q in highs if q.i >= k0 and q.known <= i - 1]
    bh, bj = None, None
    for v, k in cand:
        seg = sd.h[k + 1:i]                                          # the closed bars after the candidate, before this one
        if len(seg) and float(seg.max()) > v + 1e-9:
            j = k + 1 + int(np.argmax(seg > v + 1e-9))
            if bh is None or v > bh:
                bh, bj = v, j
    if bh is None:
        return False
    d["bh"] = bh
    hit("eval_held_hi")
    if c < bh - 1e-9:
        d["bh_done"] = True
        hit("held_hi_lost")
        _tag(tr, "lost_hi")
        if p.held_hi_action == "tighten":
            raise_to(pos, l - p.pad, "lost_hi", c, p, gate=False)
        else:
            partial_close(pos, tr, sd, ts, c, 0.5, "lost_hi", p)
            return not pos["left"]
    return False


def _ref_speed(ctx, sd, pos, tr, d, i, ts, p, h, l, c, lv) -> bool:
    """93 X8-fast-through-next-reference: ref = the nearest unhit rung or bearish VI above. 'ok' when the bar that trades beyond it or the next leaves a gap over ref, or its range >= speed_k x the
    median of the last 20 ranges; 'fail' when a close comes back under ref within ref_speed_bars bars, or after coming within 1 pt of ref three bars close lower without touching it. A fail pares
    speed_pare before T1 and closes the rest after T1 (slow_ref)."""
    rs = d.get("rs")
    if rs is None:
        failed = d.setdefault("rs_failed", [])                      # a reference that failed is not judged again (the high never passed it: it would be picked on the next bar)
        cands = [v for v in lv[pos["k"]:] if v > d["hi"] + 1e-9]
        for z in sd.vis("bear"):
            if z.i <= i - 1 and z.bottom > d["hi"] + 1e-9:
                cands.append(float(z.bottom))
        cands = [v for v in cands if all(abs(v - f_) > 1e-9 for f_ in failed)]
        if not cands:
            return False
        rs = d["rs"] = dict(ref=min(cands), b=None, near=None, nc=0)
    ref = rs["ref"]
    hit("eval_ref_speed")
    fail = False
    if rs["b"] is None:
        if h >= ref - 1e-9 and h > ref + 1e-9:
            rs["b"] = i
        elif h >= ref - p.es_pt and h < ref - 1e-9:
            if rs["near"] is None:
                rs["near"], rs["nc"] = i, 0
            elif c < float(sd.c[i - 1]):
                rs["nc"] += 1
            else:
                rs["nc"] = 0
            if rs["nc"] >= 3:
                fail = True
        elif rs["near"] is not None:
            rs["nc"] = rs["nc"] + 1 if c < float(sd.c[i - 1]) else 0         # (review fix: the lower-close run resets on a non-lower close in this branch too)
            if rs["nc"] >= 3:
                fail = True
    if rs["b"] is not None and not fail:
        b = rs["b"]
        lo20 = max(0, b - 20)
        med = float(np.median(sd.h[lo20:b] - sd.l[lo20:b])) if b > lo20 else 0.0
        ok = (sd.h[b] - sd.l[b]) >= p.speed_k * med > 0
        if not ok and i >= 2 and (i == b or i == b + 1):
            ok = bool(sd.l[i] > sd.h[i - 2] and sd.h[i - 1] > ref)
        if ok:
            d["rs"] = None
            d["hi_ref"] = ref
            hit("ref_speed_ok")
            return False
        if c < ref - 1e-9 and i - b < p.ref_speed_bars:
            fail = True
        elif i - b >= p.ref_speed_bars:
            d["rs"] = None
            hit("ref_speed_ok")
            return False
    if fail:
        d.setdefault("rs_failed", []).append(float(ref))
        d["rs"] = None
        hit("ref_speed_fail")
        _tag(tr, "slow_ref")
        if pos["t1_done"]:
            close_all(pos, tr, sd, ts, c, "slow_ref")
            return True
        partial_close(pos, tr, sd, ts, c, p.speed_pare, "slow_ref_pare", p)
        return not pos["left"]
    return False


def _opp_tear(sd, pos, tr, d, i, h, l) -> None:
    """94 X8-opposing-array-torn-through: touching an opposing array (near edge) opens a window of the touch bar and the next one: confirmed when a high reaches its MT / CE with no low under the
    touch bar's low first; otherwise no adds and a warn count."""
    hit("eval_opp_tear")
    w = d.get("opp_win")
    if w is not None:
        # the window is the touch bar T and the next bar T+1 (review fix): the touch bar itself confirms when its high reaches the MT / CE (below); on T+1 a high at the CE with no low under the
        # touch bar's low confirms, anything else - including a bar that undercuts the touch low (the order inside the bar is unknown) - is the tear-through warning. There is no T+2.
        a = d["opp"][w["k"]]
        d["opp_win"] = None
        if h >= a["ce"] - 1e-9 and l >= w["lo"] - 1e-9:
            hit("opp_tear_ok")
        else:
            pos["no_adds"] = True
            pos["add"] = None
            pos["warn"] = pos.get("warn", 0) + 1
            hit("opp_tear_warn")
            _tag(tr, "opp_tear_warn")
        return
    for k, a in enumerate(d["opp"]):
        if k in d["opp_done"] or h < a["near"] - 1e-9:
            continue
        d["opp_done"].add(k)
        if h >= a["ce"] - 1e-9:
            hit("opp_tear_ok")
        else:
            d["opp_win"] = dict(k=k, i=i + 1, lo=float(l))
        return


def _edge_bump(ctx, sd, pos, tr, d, i, p, l) -> None:
    """95 X8-broken-fvg-edge-bump-once: bars whose low comes within a tick of the broken gap's edge E: bump 1 may arm an add (edge_bump_add), bump 2 = no more adds and the ladder frozen
    (edge_bump_guard)."""
    hit("eval_edge_bump")
    if l <= d["edge"] + p.tick + 1e-9:
        if not d["bump_on"]:
            d["bump_on"] = True
            d["bumps"] += 1
            if d["bumps"] == 1 and p.edge_bump_add:
                d["edge_add_armed"] = True
                hit("edge_bump_add")
                S = _S()
                t_ = int(ctx.t[i])
                # the add goes through the engine's add rules (setups.add_ok: cut-off, PD gate, breaker gate; the day-state gates of the loop: adds_blocked, the add cut, late_cutoff) [review fix]
                if (p.adds and pos["add"] is None and not pos.get("no_adds") and not pos["t1_done"] and S._nadds(pos, tr) < len(p.adds)
                        and not S._EN.adds_blocked(ctx, sd, pos, i, p) and not S._EN.add_cut_passed(sd, pos, i, p) and not (p.late_cutoff and t_ >= p.late_cutoff)
                        and S._SM.add_ok(sd, pos, d["edge"], i, p)):
                    S._arm_add(pos, tr, d["edge"], i, p, getattr(ctx, "equity", None))
            elif d["bumps"] >= 2 and p.edge_bump_guard:
                pos["no_adds"] = True
                pos["add"] = None
                pos["levels_frozen"] = True
                _tag(tr, "edge_bump2")
                hit("edge_bump_guard")
    else:
        d["bump_on"] = False


def _pair(sd, pos, tr, d, i, h) -> None:
    """102 X9-071-move-away-from-up-close-pair: after a bar trades through the pair's reference open, the break bar or one of the next two must make a new extreme, else no adds."""
    ref = d["pair_ref"]
    hit("eval_pair")
    if d["pair_b"] is None:
        if h > ref + 1e-9:
            d["pair_b"] = i
            d["pair_hi"] = float(h)
        return
    b = d["pair_b"]
    if i > b and i <= b + 2:
        if h > d["pair_hi"] + 1e-9:
            d["pair_b"] = -1
            d["pair_ref"] = None
        elif i == b + 2:
            pos["no_adds"] = True
            pos["add"] = None
            _tag(tr, "pair_stall")
            hit("pair_stall")
            d["pair_ref"] = None


def _fulcrum(sd, pos, tr, d, i, ts, p, h, l, c) -> bool:
    """103 X9-speed-after-fulcrum-break: from the bar that breaks the fulcrum pool, -0.5 SD must print within fulcrum_speed_bars bars without a close back under the broken level, else the first
    rung's share is closed at the close (fulcrum_slow) and the stop goes under the break bar's low."""
    hit("eval_fulcrum_speed")                                           # (not "eval_fulcrum": that is tp4.fulcrum_ladder's counter)
    if d["fp_b"] is None:
        if h > d["fp_pool"] + 1e-9:
            d["fp_b"] = i
            d["fp_blow"] = float(l)
            if h >= d["fp_sd"] - 1e-9:
                d["fp_pool"] = None
        return False
    b = d["fp_b"]
    if h >= d["fp_sd"] - 1e-9:
        d["fp_pool"] = None
        hit("fulcrum_fast")
        return False
    if c < d["fp_pool"] - 1e-9 or i - b >= p.fulcrum_speed_bars:
        d["fp_pool"] = None
        q = max(p.lot, _S()._lots(pos["n"] * (pos["fracs"][0] if pos.get("fracs") else 0.5), p.lot))
        partial_close(pos, tr, sd, ts, c, 0, "fulcrum_slow", p, units=q)
        raise_to(pos, d["fp_blow"] - p.pad, "fulcrum_slow", c, p, gate=False)
        _tag(tr, "fulcrum_slow")
        hit("fulcrum_slow")
        return not pos["left"]
    return False


def _small_fvg(ctx, sd, pos, tr, d, i, p) -> None:
    """107 new-small-fvg-last-line: after T1 the latest 5m bullish gap price retraces into; more than small_fvg_linger 5m bars inside it, or a 5m close under it = no adds and the stop capped at the
    HTF entry array's high (stop_cap)."""
    from . import tp3 as T3
    t, tf = int(ctx.t[i]), ctx.tf
    if (t + tf) % 5 or d.get("sf_done"):
        return
    hit("eval_small_fvg")
    a5 = T3.tf_arrays(ctx, sd, i, 5)
    if a5 is None:
        return
    o5, h5, l5, c5, last = a5
    if len(c5) < 3 or last[-1] != i:
        return
    k = len(c5) - 1
    sf = d["sf"]
    if sf is None:
        for q in range(k, 1, -1):
            if l5[q] > h5[q - 2] and last[q] > pos["fill_i"]:
                g = (float(h5[q - 2]), float(l5[q]), q)
                if q < k and l5[k] <= g[1] + 1e-9:
                    sf = d["sf"] = dict(bot=g[0], top=g[1], n=0)
                break
    if sf is None:
        return
    if c5[k] < sf["bot"] - 1e-9:
        trig = True
    elif c5[k] > sf["top"] + 1e-9:
        d["sf"] = None
        return
    else:
        sf["n"] += 1
        trig = sf["n"] > p.small_fvg_linger
    if trig:
        d["sf_done"] = True
        pos["no_adds"] = True
        pos["add"] = None
        if d.get("htf_hi") is not None:
            pos["stop_cap"] = float(d["htf_hi"])
        _tag(tr, "small_fvg_linger")
        hit("small_fvg_linger")


def _rde(sd, pos, tr, d, i, ts, p, o, h, lv, avg) -> bool:
    """49 X3-running-down-equity-trigger: armed when (h - avg) / (final - avg) >= rde_arm; each confirmed 1m pivot high formed after arming that a later bar exceeds takes rde_frac of the units at
    arming time at pivot + tick."""
    fin = lv[-1] if lv else None
    if fin is None or fin <= avg:
        return False
    hit("eval_rde")
    if d.get("rde_arm_i") is None:
        if (h - avg) / (fin - avg) >= p.rde_arm - 1e-12:
            d["rde_arm_i"], d["rde_units"], d["rde_done"] = i, pos["left"], set()
            hit("rde_armed")
        return False
    highs, _ = _piv(sd, d["rde_arm_i"], i - 1)
    for q in highs:
        if q.i > d["rde_arm_i"] and q.i not in d["rde_done"] and q.known <= i - 1 and h >= q.price + p.tick - 1e-9:
            d["rde_done"].add(q.i)
            units = max(p.lot, _S()._lots(d["rde_units"] * p.rde_frac, p.lot))
            partial_close(pos, tr, sd, ts, max(q.price + p.tick, o), 0, "rde", p, units=units)
            hit("rde_partial")
            if not pos["left"]:
                return True
    return False


def _depth_trail(pos, d, i, h, l, c, p, lv, avg) -> None:
    """EXIT-DEPTH B: "close or trail tight from 75% of the projection; don't demand the exact target" - armed once a bar's high reaches depth_trail of the way from the
    average fill to the final rung; from then on every closed bar raises the stop to one tick under its low [our interpretation: "trail tight" = the engine bar's low (1m or 5m); only the trail half of
    "close or trail" is built]. A trail: refused while a trail lock / wick gate / freeze holds (raise_to gate=True); a bar that exits earlier in manage skips it."""
    fin = lv[-1] if lv else None
    if fin is None or fin <= avg:
        return
    hit("eval_depth_trail")
    if not d.get("depth_armed"):
        if (h - avg) / (fin - avg) < p.depth_trail - 1e-12:
            return
        d["depth_armed"] = True
        hit("depth_trail_armed")
    if raise_to(pos, l - p.tick, "depth_trail", c, p):
        hit("depth_trail_raise")


def _peel(ctx, sd, pos, tr, d, i, ts, p, o, h, l, c, avg) -> bool:
    """50 X3-020-runner-peel-singles: after >= 75 % is closed and while price is above the target NWOG's CE: one lot per bar at most when a bar trades 1 tick above a relative equal high inside the
    gap, or makes a higher high than the bar before; one lot halfway from the first peel's price to the gap top. With one unit left the stop goes under the latest 1m pivot low and the peeling
    stops."""
    z = d.get("nwog")
    if z is None or d.get("peel_end") or not d.get("peel_armed") or _closed(pos) < 0.75 - 1e-9:
        return False
    lo, hi = z
    ce = (lo + hi) / 2
    hit("eval_peel")
    if c <= ce:
        return False
    if pos["left"] <= p.lot:
        _, lows = _piv(sd, max(ctx.start, pos["fill_i"] - 3), i)
        if lows:
            raise_to(pos, lows[-1].price - p.tick, "peel_last", c, p, gate=False)       # (review fix: the final unit's roll is the spec's own stop move, not a trail the wick gate may block)
        d["peel_end"] = True
        hit("peel_last")
        return False
    px = None
    highs, _ = _piv(sd, max(ctx.start, pos["fill_i"] - 3), i - 1)
    rehs = L.equal_levels([q.price for q in highs if lo - 1e-9 <= q.price <= hi + 1e-9], p.eq_tol_pts * p.es_pt)          # the relative equal highs inside the gap
    peeled = d.setdefault("reh_peeled", set())
    for lvl in rehs:
        if lvl not in peeled and h >= lvl + p.tick - 1e-9:
            peeled.add(lvl)
            px = max(lvl + p.tick, o)
            break
    reh_ready = (not rehs) or bool(peeled)                  # the sequence of 020: the REH poke first, then each higher high (no REH inside the gap: straight to the higher highs)
    if px is None and reh_ready and h >= float(sd.h[i - 1]) + p.tick - 1e-9:
        px = max(float(sd.h[i - 1]) + p.tick, o)
    if px is not None:
        d["peel_n"] = d.get("peel_n", 0) + 1
        if d.get("peel_mid") is None:
            d["peel_mid"] = (c + hi) / 2
        partial_close(pos, tr, sd, ts, px, 0, "peel", p, units=p.lot)
        hit("peel")
        return not pos["left"]
    pm = d.get("peel_mid")
    if pm is not None and not d.get("peel_mid_done") and h >= pm - 1e-9:
        d["peel_mid_done"] = True
        partial_close(pos, tr, sd, ts, max(pm, o), 0, "peel_mid", p, units=p.lot)
        hit("peel_mid")
        return not pos["left"]
    return False


def _raisers(ctx, sd, pos, tr, d, i, p, o, h, l, c, newhi, avg, tf) -> None:
    """The stop moves of the chunk: 23 (VI reaction, short-term-high break), 25 (trail anchors), 26 (OB-open retests), 27 (structure trail), 29 (OB MT after the run)."""
    # 23 raise_on_vi: a bar whose low enters the VI and closes above its top
    if p.raise_on_vi and d.get("vi") and not d.get("vi_done"):
        hit("eval_raise_on_vi")
        vb, vt = d["vi"]
        if l <= vt + 1e-9 and c > vt + 1e-9:
            d["vi_done"] = True
            if raise_to(pos, vb - p.tick, "vi_react", c, p):
                hit("raise_on_vi")
    # 23 raise_on_sth_break
    if p.raise_on_sth_break and d.get("sth") is not None and not d.get("sth_done"):
        hit("eval_sth_break")
        if d.get("sth_b") is None and h > d["sth"] + 1e-9:
            d["sth_b"] = i
        if d.get("sth_b") is not None:
            ok = True
            if p.raise_need_5m_fvg:
                ok = _fvg5_since(ctx, sd, i, d["sth_b"], d["sth"])
            if ok:
                d["sth_done"] = True
                if raise_to(pos, d["bz_bot"] - p.tick, "sth_break", c, p):
                    hit("raise_on_sth_break")
    lt = p.ladder_trail if p.mgmt in ("ladder", "unit") else ""        # (review fix: the ladder_trail modes act on the ladder positions only - with mgmt "t1_t2" they are inert like the other ladder_trail values)
    # 25 the trail anchors
    if lt in ("candle_mt", "071") and newhi and not pos.get("day_trade"):
        for k in range(i - 1, max(pos["fill_i"] - 1, 0), -1):
            if sd.c[k] < sd.o[k]:
                if raise_to(pos, _mt(sd, k, p) - p.tick, "candle_mt", c, p):
                    hit("trail_candle_mt")
                break
    if lt in ("eq_pause", "071") and not pos.get("day_trade"):
        _, lows = _piv(sd, max(ctx.start, pos["fill_i"] - 1), i - 1)
        lows = [q for q in lows if q.i >= pos["fill_i"] and pos["stop"] < q.price < c]
        if len(lows) >= 2:
            cl = L.equal_clusters([q.price for q in lows], p.eq_tol_pts * p.es_pt)
            if cl:
                best = max(cl, key=lambda ix: max(lows[q].price for q in ix))
                if raise_to(pos, min(lows[q].price for q in best) - p.tick, "eq_pause", c, p):
                    hit("trail_eq_pause")
    # 26 OB-open retests
    if p.ob_retests and d.get("ob_open") is not None and not d.get("ob_done") and i - 1 > pos["fill_i"]:
        hit("eval_ob_retests")
        oo = d["ob_open"]
        j = i - 1
        if sd.l[j] <= oo + p.tick + 1e-9 and sd.l[j] >= oo - p.tick - 1e-9 and h > sd.h[j] + 1e-9:
            d["ob_n"] += 1
            hit("ob_retest")
            if d["ob_n"] >= p.ob_retests:
                d["ob_done"] = True
                if raise_to(pos, oo - p.tick, "ob_open", c, p, ignore_freeze=True):
                    pos["freeze"] = True
                    hit("ob_open_raise")
    # 27 structure trail
    if lt == "structure" and not pos.get("day_trade"):
        hit("eval_structure")
        _structure(sd, pos, tr, d, i, p, h, c)
    # 29 stop to the OB MT after the run
    if p.ob_stop_to_mt_after_run and d.get("ob_mt") is not None and not d.get("obmt_done"):
        hit("eval_ob_mt")
        run = (d["hi"] if not newhi else h) - avg >= 2.0 * d["ob_body"] - 1e-9 and d["ob_body"] > 0
        if not run and d.get("ob_valid_hi") is not None:
            highs, _ = _piv(sd, pos["fill_i"] - 1, i - 1)
            run = any(q.price > d["ob_valid_hi"] + 1e-9 and q.known <= i - 1 for q in highs)
        if run:
            d["obmt_done"] = True
            if raise_to(pos, d["ob_mt"] - p.pad, "ob_mt_run", c, p):
                hit("ob_stop_to_mt")


def _fvg5_since(ctx, sd, i: int, b: int, sth: float) -> bool:
    """23: a 5m bullish gap formed in the break of the short-term high - completed at or after bar b, its middle candle having traded through `sth` (setup_minutes aggregation, 5m)."""
    from . import tp3 as T3
    a5 = T3.tf_arrays(ctx, sd, i, 5)
    if a5 is None:
        return False
    o5, h5, l5, c5, last = a5
    for q in range(2, len(c5)):
        if l5[q] > h5[q - 2] and last[q] >= b and h5[q - 1] > sth + 1e-9:
            return True
    return False


def _structure(sd, pos, tr, d, i, p, h, c) -> None:
    """27 X5-structure-trail-and-cap: step 1 - the high clears the short-term high formed before the entry: the stop under the retracement's low, frozen. Then each new 1m pivot low L above the stop
    and a later bar exceeding the pivot high that followed L lifts it under min(L, L's wick CE), or under the gap bottom when that level lies inside a gap formed by the break bar."""
    if d.get("st_phase") is None:
        if d.get("sth") is None:
            return
        if h > d["sth"] + 1e-9:
            rl = pos.get("retr_low")
            if rl is None or not np.isfinite(rl):
                rl = float(sd.l[pos["fill_i"]:i + 1].min())
            raise_to(pos, rl - p.tick, "structure", c, p, ignore_freeze=True)
            pos["freeze"] = True
            d["st_phase"] = i
            hit("structure_step1")
        return
    highs, lows = _piv(sd, d["st_phase"], i - 1)
    for L_ in lows:
        if L_.i <= d["st_phase"] or L_.price <= pos["stop"] + 1e-9 or L_.i in d.setdefault("st_used", set()):
            continue
        hs = [q for q in highs if q.i > L_.i and q.known <= i - 1]
        if not hs:
            continue
        if h > hs[0].price + 1e-9:
            d["st_used"].add(L_.i)
            ce = float(L.wick_ce(sd.o, sd.l, sd.c, L_.i))
            lvl = min(L_.price, ce)
            for g in sd.gaps:
                if g.i == i and g.bottom <= lvl <= g.top:
                    lvl = float(g.bottom)
            if raise_to(pos, lvl - p.tick, "structure", c, p, ignore_freeze=True):
                d["st_phase"] = i
                hit("structure_step")


# --- 6. hooks of the position loop / the order stage ------------------------------------------------------------------------------------------------

def after_close(pos, tr, done: dict, key: str, state, p) -> None:
    """20: a stop exit after the pool lock blocks the re-entry of that session; a final-rung fill ends the day with pool_lock_day_done. 100: after_chop_exit."""
    d = pos.get("me2")
    if not d or done is None:
        return
    last = tr.exits[-1][3] if tr.exits else ""
    if pos.get("no_reentry") and last in ("stop", "stop_gap", "be"):
        done[key] = True
        hit("pool_lock_no_reentry")
    if p.pool_lock_day_done and pos.get("pool_locked") and tr.final_hit:
        done["AM"] = done["PM"] = True
        hit("pool_lock_day_done")
    if d.get("chop_closed"):
        if p.after_chop_exit == "end_session":
            done[key] = True
            hit("chop_end_session")
        elif state is not None:
            g_, c_ = tr.pnl(p.cost_per_share)
            if not (p.reentry_half and g_ - c_ < 0):                  # (review fix: after a chop-close LOSS the engine's own reentry_half block follows and sets this flag itself - setting it here would suppress it)
                state.setdefault("reentered", {})[tr.session] = True
            hit("chop_reentry_allowed")


def chop_close(pos, tr, sd, ts, c, chop, p, fill_i: int) -> bool:
    """100 X9-lethargic-or-choppy-trade: the intraday Chop detector turned on while the position was open -> everything closes at the close (after_chop_exit then decides the session)."""
    d = pos.get("me2")
    if not (p.chop_close and d and pos["left"]):
        return False
    if chop.on:
        hit("eval_chop_on")
    if chop.on and chop.on_at is not None and chop.on_at >= fill_i:
        close_all(pos, tr, sd, ts, c, "chop_close")
        d["chop_closed"] = True
        _tag(tr, "chop_close")
        hit("chop_close")
        return True
    return False


def order_block(ctx, sd, i: int, p, session: str, entry: float):
    """The entry blocks of the chunk (returns a filter tag or None): 36 a counter-direction setup whose entry lies inside the HTF array an open trade banked at; 99 the weekly reversal_watch
    direction; 96 an entry in the direction of a trade whose late-day gap price is still under."""
    st = ctx.__dict__.get("me2_state")
    real = float(sd.x(entry))
    if p.htf_bank and st:
        for dr, (a, b, _) in st["htf_touch"].items():
            if dr != sd.sign and a - 1e-9 <= real <= b + 1e-9:
                hit("htf_touch_block")
                return "x_htf_touch"
    if p.stall_at_htf:
        rw = (getattr(ctx, "week", None) or {}).get("reversal_watch") or ()
        if ("long" if sd.sign > 0 else "short") in rw:
            hit("reversal_watch_block")
            return "x_reversal_watch"
    if p.late_fvg_flip and st:
        lf = st["late_fvg"].get(sd.sign)
        if lf is not None and float(sd.c[i]) < lf[1] - 1e-9:
            hit("late_fvg_block")
            return "x_late_fvg"
    return None


def week_watch(rows: list, d) -> list:
    """99: the directions blocked for the rest of the week: a trade that exited 'htf_stall' on a day of this week, with no new same-direction trade the next weekday (the stall's 'next session'),
    blocks that direction from the day after that session on."""
    import datetime as _dt
    wk = d.isocalendar()[:2]
    out = set()
    for r in rows:
        if r["date"].isocalendar()[:2] != wk or r["date"] >= d or "htf_stall" not in str(r.get("exit_reason", "")):
            continue
        nxt = r["date"] + _dt.timedelta(days=1)
        while nxt.weekday() > 4:
            nxt += _dt.timedelta(days=1)
        if d <= nxt:
            continue
        if not any(q["side"] == r["side"] and r["date"] < q["date"] <= nxt for q in rows):
            out.add(r["side"])
    return sorted(out)
