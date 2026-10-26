"""Caption-gap pass (digests/rulebook_gaps/*.md), package management_exits, chunk 3 of 3: the engine glue of its 33 specs -
management_partials_trailing_exits.md 109, 110, 111, 112, 116, 117, 119, 120, 123, 124, 127, 130, 131, 132; models_setups_entries.md 57, 65, 118, 128, 199;
session_day_week_stops_frequency.md 1, 5, 9, 10, 13, 15, 16, 17, 30; stops_sizing_scaling_in.md 41, 42; times_sessions_macros.md 8, 16, 25.

Same conventions as me1.py / me2.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an
object only from the bar that completes it, every function sits behind a Params switch of the "caption-gap pass, management_exits #3/3" block, interpretations the sources do not pin down are
marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN). The shared pieces are me2's (`partial_close`, `close_all`, `raise_to`).

Hooks (strategy.py): `on_fill` (after me2.on_fill), `manage` (the position loop, once per closed bar, after me2.manage), `rung_pre` / `rung_taken` (the ladder loop), `lh_all` (the last-hour
target), `am_skip` (the 12:00 AM close), `noon_exempt` (the pending-order noon guard), `pre_close` / `after_close` (`_after_close`), `bar` (once per bar, before the position loop), `order_block`
(`_finish_order`), `re_order` (`_scan`), `lost_side_holds` (the no-reversal lock), `risk_count` (`_risk_mult`), `eff_p` (the laggard's Params), `conflicted_day` (run_day).
manage.py carries abort_mode "half" (41), the offside flip request (42) and the ts_off flag of the time stop (109 / 120); sm7.py / es3.py / backtest.py / daycontext.py carry the small hooks
of 9, 128, 30."""
from __future__ import annotations

import numpy as np

from . import levels as L
from . import me1 as M1
from . import me2 as M2
from . import sm2

HITS = sm2.HITS
hit = sm2.hit
POOLS = ("pool", "pool_eq")
ABORT_REASONS = ("abort", "ce_close", "breaker_mt", "chop_close", "htf_stall", "time", "slow_ref", "lost_hi", "hh_low", "stall_reh")        # 130 (+ every "pd3*")
LH_ENTRY_KINDS = ("moc_run", "lh_ob")
BOOLS = ("implied_range", "vol_div_exit", "pm_two_stage", "london_tod_partials", "pre_hold_open", "session_fail_flatten", "late_week_flat", "open_reclaim_runner", "lh_pool_timing",
         "explosive_runner", "am_exit_trend_hold", "recover_trail", "abort_blocks_side", "reentry_breakaway", "ote_fail_ts", "offside_flip",
         "runner_stop_no_reentry", "am_idea_fail", "lc_second_swipe", "last_hour_target_done", "pd3_pm_window", "beginner_template")
NUMS = ("cc_day_exit", "am_runner_hold_to", "chop_scalp_pts", "stop_ack_sec")
STRS = ("scalp_mode", "recovery_exit", "reentry_mode")


def _S():
    from . import strategy as S
    return S


def _MG():
    from . import manage as MG
    return MG


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__)."""
    for name, ok in (("lost_side_scope", ("day", "session")), ("abort_mode", ("full", "half")), ("scalp_mode", ("", "fixed_1to1")), ("recovery_exit", ("", "new", "experienced")),
                     ("reentry_mode", ("", "cc_ob")), ("reentry_cc_entry", ("high", "open")), ("conflicted_mode", ("off", "skip", "one", "one_win")),
                     ("pm_after_am_win", ("off", "draw_open")), ("reentry_ob_stop", ("mt", "full"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if (not 0 <= p.pm_reset_t <= 1440 or p.reentry_count_max < 1 or not 0 <= p.lh_keep_frac < 1 or p.lh_late_ext_pts < 0 or not 0 < p.runner_frac_done <= 1 or p.chop_scalp_pts < 0
            or p.chop_scalp_max < 1 or p.chop_scalp_day_pts < 0 or p.beginner_target_pts <= 0 or not 0 <= p.late_flat_t <= 1440 or not 0 < p.abort_frac <= 1 or p.laggard_mult <= 0
            or p.vol_div_ratio <= 0 or p.am_runner_hold_to < 0 or p.explosive_frac <= 0 or p.explosive_until < 0 or not 0 < p.london_tod_frac <= 1 or p.cc_day_exit < 0
            or p.scalp_max_min < 1 or p.stop_ack_sec < 0):
        raise ValueError("management_exits #3/3: 0 <= pm_reset_t, late_flat_t <= 1440; reentry_count_max, chop_scalp_max, scalp_max_min >= 1; 0 <= lh_keep_frac < 1; "
                         "lh_late_ext_pts, chop_scalp_pts, chop_scalp_day_pts, am_runner_hold_to, explosive_until, cc_day_exit, stop_ack_sec >= 0; "
                         "0 < runner_frac_done, abort_frac, london_tod_frac <= 1; beginner_target_pts, laggard_mult, vol_div_ratio, explosive_frac > 0")


def apply_presets(p) -> None:
    """16 beginner_template (095 ~47:08): the preset over existing fields - one contract (fixed_units 1), one setup, a single exit at `beginner_target_pts` (t1_fixed_pts + t1_fixed_all),
    the stop at most 12 handles (max_stop_pts, kept when the user set one), trader_mode "new" with the day-positive / AM-or-PM stops (new_day_stops)."""
    if not p.beginner_template:
        return
    p.fixed_units = 1
    p.t1_fixed_pts = float(p.beginner_target_pts)
    p.t1_fixed_all = True
    if not p.max_stop_pts:
        p.max_stop_pts = 12.0
    p.trader_mode = "new"
    p.new_day_stops = True


def any_on(p) -> bool:
    """Does any mid-trade switch of the chunk need the per-position state (pos["me3"])?"""
    return bool(any(getattr(p, k) for k in BOOLS) or any(getattr(p, k) for k in NUMS) or any(getattr(p, k) for k in STRS) or p.laggard_mult != 1.0 or p.ladder_trail == "rolling_bpr"
                or p.abort_mode == "half" or p.chop_scalp_pts > 0 or p.conflicted_mode in ("one", "one_win") or p.pm_after_am_win != "off" or (p.new_day_stops and p.trader_mode == "new"))


def order_on(p) -> bool:
    """Does any order-stage block of the chunk apply (`order_block`)?"""
    return bool(p.abort_blocks_side or p.reentry_breakaway or p.cc_day_exit or p.pd3_pm_window or p.chop_scalp_pts > 0)


# --- 2. helpers ---------------------------------------------------------------------------------------------------------------------------------------

def _tag(tr, name: str) -> None:
    M1._tag(tr, name)


def _avg(pos) -> float:
    return pos["basis"] / pos["n"]


def _closed(pos) -> float:
    return (pos["n"] - pos["left"]) / max(pos["n"], 1)


def _fam(session: str) -> str:
    return "PM" if session == "PM" else "AM"


def _last_reason(tr) -> str:
    return str(tr.exits[-1][3]).split("+")[0] if getattr(tr, "exits", None) else ""


def is_cc(tr) -> bool:
    """123: a trade of the Core Content (2016) day-trader model - the model tags 'cc_*' (turtle-soup variants cc_limit / cc_1h_ob: entry_kind 'ts_cc_limit' ...)."""
    for s in (getattr(tr, "entry_kind", ""), getattr(tr, "setup", ""), getattr(tr, "swept", "")):
        if str(s).startswith(("cc_", "ts_cc_")):
            return True
    return any(x in ("cc_limit", "cc_1h_ob", "ts_cc_limit", "ts_cc_1h_ob") for x in str(getattr(tr, "lv_tags", "") or "").split("|"))        # (the tag 'cc_common' is an entry-location tag, not a model)


def open_net(pos, tr, sd, c: float, p) -> float:
    """The trade's net P&L if everything left were closed at `c`: the realized exits plus the open units at `c`, minus the round-trip costs of all units (side space, price x units)."""
    avg = _avg(pos)
    realized = sum((sd.sign * float(e[1]) - avg) * e[2] for e in tr.exits)
    return float(realized + (float(c) - avg) * pos["left"] - 2.0 * p.cost_per_share * pos["n"])


def _is_lh_trade(tr) -> bool:
    return getattr(tr, "setup", "") == "pm_last_hour" or str(getattr(tr, "entry_kind", "")) in LH_ENTRY_KINDS


def _htf_draw_touched(ctx, sd, pos, i: int) -> bool:
    """15: has the day's HTF draw (the session lock, else the trade's draw) been traded by bar i?"""
    lk = None
    if getattr(ctx, "lock", None):
        lk = ctx.lock.get(pos["trade"].session) or ctx.lock.get("AM")
    if lk is not None and lk.get("delivered"):
        return True
    draw = pos.get("draw")
    if draw is None and lk is not None and lk.get("target") is not None:
        draw = sd.x(lk["target"])
    if draw is None:
        return False
    return bool(float(sd.h[ctx.start:i + 1].max()) >= float(draw) - 1e-9)


# --- 3. fill ------------------------------------------------------------------------------------------------------------------------------------------

def laggard_flag(ctx, sd, i: int, p) -> bool:
    """111: the trade is taken in the index moving in SYMPATHY after the leader already reached its draw: the partner index has traded through its previous-day extreme in the trade direction
    (the draw level; PDH for a long, PDL for a short [our interpretation: the htf.table row of the partner is not part of run_day]) before this fill's bar while this index has not yet traded
    through its own. Only the partner's closed bars up to bar i-1 are read."""
    ps = getattr(ctx, "pside", None)
    if not ps or ps[0] is None:
        return False
    pctx, psides, ppos = ps
    key = "pdh1" if sd.sign > 0 else "pdl1"
    lv_p, lv_o = pctx.pd.get(key), ctx.pd.get(key)
    if lv_p is None or lv_o is None:
        return False
    psd = psides[sd.sign]
    k = ppos.get(ctx.idx[i])
    if k is None or i - 1 < ctx.start:
        return False
    k = int(k)
    own = float(sd.h[ctx.start:i].max()) if i > ctx.start else -np.inf                  # (side space)
    partner = float(psd.h[pctx.start:k].max()) if k > pctx.start else -np.inf
    return bool(partner >= float(psd.x(lv_p)) - 1e-9 and own < float(sd.x(lv_o)) - 1e-9)


def eff_p(pos, p):
    """111: the laggard position's Params - time_stop_min / time_stop_bars / meander_bars x laggard_mult (a loosened, not dropped, X9 / X8g window). Built once per position."""
    d = pos.get("me3")
    if not d or not d.get("laggard") or p.laggard_mult == 1.0:
        return p
    q = d.get("p_lag")
    if q is None:
        from dataclasses import replace
        m = p.laggard_mult
        q = d["p_lag"] = replace(p, time_stop_min=int(round(p.time_stop_min * m)), time_stop_bars=int(round(p.time_stop_bars * m)), meander_bars=int(round(p.meander_bars * m)))
    hit("laggard_params")
    return q


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p, fill: float, state=None, done=None) -> None:
    """Fill time (side space): the state the mid-trade hooks need. The order may carry explicit values in o["me3"] (tests, forced books)."""
    d = dict(o.get("me3") or {})
    d["fill_i"] = i
    d["hi"] = float(sd.h[i])
    d["rb_i"], d["rb_hi"] = i, float(sd.h[i])                       # 110: the running extreme since the fill
    pos["me3"] = d
    tk = p.tick
    # --- 109 the implied range: the sweep extreme .. the final level
    if p.implied_range and "ir" not in d and pos.get("levels"):
        lo, hi = float(pos["ext"]), float(pos["levels"][-1])
        if hi > lo:
            d["ir"] = (lo, hi)
    # --- 111 laggard
    if p.laggard_mult != 1.0 and "laggard" not in d:
        d["laggard"] = laggard_flag(ctx, sd, i, p)
        if d["laggard"]:
            tr.laggard = True
            _tag(tr, "laggard")
            hit("laggard")
    if p.chop_scalp_pts > 0 and o.get("scalp"):
        pos["scalp_chop"] = True                                                # 10: counted in after_close
    # --- 127 scalp mode: a single 1:1 rung, no BE / trail / adds, a time exit
    if p.scalp_mode == "fixed_1to1" and o.get("scalp"):
        avg = float(fill)
        risk = avg - float(pos["stop"])
        if risk > 0:
            lvl = avg + risk
            pos.update(levels=[lvl], level_kinds=["fixed"], fracs=(1.0,), t1=lvl, t2=None, final_T=False, runner=False, rungs=[], no_adds=True, no_trail=True, be_at=None, trade_mode="scalp")
            pos["add"] = None
            pos["exit_at"] = int(pos["fill_t"]) + int(p.scalp_max_min)
            _tag(tr, "scalp_1to1")
            hit("scalp_1to1")
    # --- 132 / 30 the re-entry after a loss
    r3_ = ((state or {}).get("re3") or {}).get(tr.session)
    re_ = bool(pos.get("reentry") or (r3_ and r3_.get("pending") and r3_.get("side") == tr.side))      # manage.init_pos: the X13b re-entry (re_ctx pending); the 65 / 118 contexts
    d["reentry"] = re_
    if re_ and state is not None:
        rec = (state.get("unrecovered") or {}).get(tr.session)
        if rec is None:
            rec = pos.get("re_loss")
        d["recover"] = None if rec is None else float(rec)
        if p.recovery_exit == "experienced" and not o.get("scalp"):
            risk = float(fill) - float(pos["stop"])
            if risk > 0:
                d["rec_r"] = float(risk)
                lvl = float(fill) + 3.0 * risk
                pos.update(levels=[lvl], level_kinds=["fixed"], fracs=(1.0,), t1=lvl, t2=None, final_T=False, runner=False)             # a single rung at +3R
                hit("recovery_rung")
    # --- 17 conflicted day: one entry
    if p.conflicted_mode == "one" and getattr(ctx, "conflicted", False) and done is not None:
        for k in list(done):
            done[k] = True
        hit("conflicted_one")
    # --- re-entry gating contexts of 65 / 118 are over once an order of their side fills
    if state is not None:
        for sess, r in (state.get("re3") or {}).items():
            if r.get("pending") and r.get("side") == tr.side and sess == tr.session:
                r["pending"] = False
    # --- 120 two-stage PM delivery (the PM profile is read at the fill; cc_profile caches it)
    if p.pm_two_stage and tr.session == "PM":
        from . import setups as ST
        prof = ST.cc_profile(ctx, i, p)
        d["two_stage"] = bool(prof and str(prof[0]).startswith("two_session"))
    # --- 25 / 124 / 123 flags
    d["fill_t"] = int(pos["fill_t"])


# --- 4. the position loop -----------------------------------------------------------------------------------------------------------------------------

def _pre_open_drift(ctx, sd, pos, i: int) -> bool:
    """25: risk_0930_sweep - the 5m closes of the last 20 minutes (550-570) all sit in the lower third of the post-entry range [our interpretation of "drift into the open"]."""
    fi = pos["fill_i"]
    lo, hi = float(sd.l[fi:i + 1].min()), float(sd.h[fi:i + 1].max())
    if hi <= lo:
        return False
    tf = ctx.tf
    ks = [k for k in range(fi + 1, i + 1) if 550 <= ctx.t[k] < 570 and (ctx.t[k] + tf) % 5 == 0]
    return bool(ks) and all(float(sd.c[k]) <= lo + (hi - lo) / 3.0 + 1e-9 for k in ks)


def _fails_in_family(trades, fam: str, p, skip=None) -> int:
    """13: the run of failed trades at the end of the family's closed trades (the X7c rule: a loss; with session_fail_mode "arrays" one that ended in a FAIL_REASONS exit)."""
    MG = _MG()
    run = 0
    closed = sorted((t for t in trades if t.exits and t is not skip and _fam(t.session) == fam), key=lambda t: t.exits[-1][0])
    for tr in closed:
        fail = MG._net(tr, p) < 0 and (p.session_fail_mode == "trades" or _last_reason(tr) in MG.FAIL_REASONS)
        run = run + 1 if fail else 0
    return run


def manage(ctx, sd, pos, tr, i: int, ts, p, state=None, done=None, trades=None) -> None:
    """Mid-trade (bar i closed): the exits, partials and stop moves of the chunk. Called once per bar after me2.manage; a stop moved here applies from the next bar. Sets pos["ts_off"] (the X9
    time stop is suspended: 109 inside the middle half of the implied range, 120 until the second PM stage) and pos["stall_off"] (the stall exits of #55 / #99 are suspended: 120)."""
    d = pos.get("me3")
    if not d or not pos["left"] or i <= pos["fill_i"]:
        return
    o, h, l, c = float(sd.o[i]), float(sd.h[i]), float(sd.l[i]), float(sd.c[i])
    t, tf = int(ctx.t[i]), ctx.tf
    tk = p.tick
    avg = _avg(pos)
    newhi = h > d["hi"] + 1e-9
    ts_off = stall_off = False

    # --- 109 implied range: no time exit in the middle half; the top-quarter raid halves the position
    ir = d.get("ir")
    if ir:
        lo, hi = ir
        r = hi - lo
        hit("eval_implied_range")
        ts_off = lo + 0.25 * r <= c <= lo + 0.75 * r
        top = lo + 0.75 * r
        if d.get("ir_top") and not d.get("ir_raid"):
            hit("eval_ir_top_raid")
            fi = pos["fill_i"]
            _, pls = M2._piv(sd, fi, i - 1)
            lows = [q for q in pls if q.known <= i - 1 and q.price >= top - 1e-9]
            trig = float(lows[-1].price) if lows else None
            if trig is not None and l < trig - 1e-9:
                d["ir_raid"] = True
            else:
                obs = [k for k in range(fi + 1, i) if sd.c[k] < sd.o[k] and float(sd.c[k + 1:i].max(initial=-np.inf)) > sd.h[k]]      # a bullish OB: a down-close candle a later close went over
                if obs:
                    body_lo = float(min(sd.o[obs[-1]], sd.c[obs[-1]]))
                    if l < body_lo - 1e-9:
                        d["ir_raid"] = True
            if d.get("ir_raid"):
                px = min(o, trig) if (trig is not None and l < trig - 1e-9) else min(o, body_lo)
                M2.partial_close(pos, tr, sd, ts, px, 0.5, "ir_top_raid", p)
                _tag(tr, "ir_top_raid")
                hit("ir_top_raid")
                if not pos["left"]:
                    return
        if h >= top:
            d["ir_top"] = True

    # --- 120 two-stage PM delivery: the time stop and the stall exits wait until 15:00 while the far (non-pool) rung is unhit and the close holds above the entry array's far edge
    if p.pm_two_stage and d.get("two_stage") and t + tf < 900:
        lvl = M1._lv(pos)
        kinds = list(pos.get("level_kinds") or [])
        if lvl and pos["k"] < len(lvl) and (not kinds or kinds[min(len(lvl), len(kinds)) - 1] not in POOLS) and c > float(pos["fvg_bottom"]):
            ts_off = stall_off = True
            hit("two_stage_hold")
    pos["ts_off"] = ts_off
    pos["stall_off"] = stall_off

    # --- 123 CC day-trader model: flat by cc_day_exit
    if p.cc_day_exit and is_cc(tr) and t + tf >= p.cc_day_exit:
        M2.close_all(pos, tr, sd, ts, c, "cc_" + f"{p.cc_day_exit // 60:02d}{p.cc_day_exit % 60:02d}")
        hit("cc_day_exit")
        return
    # --- 127 the scalp's max hold is the order's exit_at (the ladder loop's time_exit)
    # --- 124 London time-of-day partials (bar-time convention: t = the bar's OPEN minute, so a partial fires on the first bar opening at or after the clock time, at that bar's close; the 04:55 and 06:55 checks are independent)
    if p.london_tod_partials and tr.session == "LON":
        hit("eval_london_tod")
        ft = d["fill_t"]
        if ft < 295 and t >= 295 and not d.get("lon_0500"):
            d["lon_0500"] = True
            M2.partial_close(pos, tr, sd, ts, c, p.london_tod_frac, "lon_0500", p)
            hit("lon_0500")
        if ft < 415 and t >= 415 and not d.get("lon_0700") and pos["left"]:
            d["lon_0700"] = True
            M2.partial_close(pos, tr, sd, ts, c, p.london_tod_frac, "lon_0700", p)
            hit("lon_0700")
        if pos["left"] and ft < 660 and 600 <= t < 660 and newhi and not d.get("lon_1000"):
            d["lon_1000"] = True
            M2.partial_close(pos, tr, sd, ts, c, p.london_tod_frac, "lon_1000", p)
            hit("lon_1000")
        if not pos["left"]:
            return
    # --- 25 a funded pre-09:30 position may be held through the open; an unfunded one with the drift flag is closed
    if p.pre_hold_open and tr.session in ("PRE7", "PRE9", "NEWS") and t + tf >= 570 and not d.get("pre_open_done"):
        d["pre_open_done"] = True
        funded = pos["t1_done"] or _closed(pos) > 0
        flag = _pre_open_drift(ctx, sd, pos, i)
        hit("eval_pre_hold_open")
        if flag:
            _tag(tr, "risk_0930_sweep")
        if flag and not funded:
            M2.close_all(pos, tr, sd, ts, c, "pre_open_unfunded")
            hit("pre_open_unfunded")
            return
    # --- 13 the third failed array of the session: flatten at the close, no more entries of the family
    if p.session_fail_flatten and trades is not None and state is not None and done is not None:
        fam = _fam(tr.session)
        need = p.session_stop_after_fails or 3
        hit("eval_session_fail")
        if c < float(pos["fvg_bottom"]) - 1e-9 and _fails_in_family(trades, fam, p, skip=tr) + 1 >= need:
            M2.close_all(pos, tr, sd, ts, c, "pd3_session")
            st = state.setdefault("stops", {"day": None})
            st.setdefault(fam, "pd3_session")
            for k in list(done):
                if _MG().key_fam(k) == fam:
                    done[k] = True
            done["SB_" + tr.session] = True
            if fam == "AM" and p.pd3_pm_window:
                state["pm_window"] = (825, 870)
            hit("session_fail_flatten")
            return
    # --- 30 late in the week / session: a recovery re-entry that brings the week back to flat is closed there; otherwise the stop trails to the break-even-week price
    if p.late_week_flat and d.get("reentry") and trades is not None and state is not None and done is not None:
        MG = _MG()
        wk = float((getattr(ctx, "week", None) or {}).get("net", 0.0))
        day_closed = float(sum(MG._net(x, p) for x in trades))
        tot = wk + day_closed + open_net(pos, tr, sd, c, p)
        hit("eval_late_week_flat")
        late = ctx.day.weekday() in (3, 4) or t + tf >= p.late_flat_t
        if tot >= 0 and late:
            M2.close_all(pos, tr, sd, ts, c, "flat_week")
            for k in list(done):
                done[k] = True
            state["day_done"] = True
            hit("flat_week")
            return
        if p.recover_trail and tot > 0 and pos["left"] > 0:
            M2.raise_to(pos, c - tot / pos["left"], "week_trail", c, p, gate=False)
            hit("week_trail")
    # --- 132 the recovery exit of a re-entry after a loss
    if p.recovery_exit and d.get("reentry"):
        hit("eval_recovery")
        if p.recovery_exit == "new" and d.get("recover") is not None and open_net(pos, tr, sd, c, p) >= d["recover"] - 1e-9:
            M2.close_all(pos, tr, sd, ts, c, "recovered")
            if done is not None:
                done[pos.get("done_key", tr.session)] = True
                done[tr.session] = True
            hit("recovered")
            return
        if p.recovery_exit == "experienced" and d.get("rec_r"):
            lvl2 = avg + 2.0 * d["rec_r"]
            if h >= lvl2 - 1e-9:
                M2.raise_to(pos, lvl2 - tk, "recovery_lock", c, p, gate=False)
    # --- 112 volume divergence at a new session extreme (bonds-sourced; a test switch)
    if p.vol_div_exit and not d.get("vol_div"):
        v = getattr(ctx, "v", None)
        if v is None:
            hit("vol_div_no_volume")
        else:
            hit("eval_vol_div")
            k0 = ctx.start
            if i > k0 and h > float(sd.h[k0:i].max()) + 1e-9:
                kp = k0 + int(np.argmax(sd.h[k0:i]))
                draw = pos.get("draw")
                untouched = draw is not None and float(sd.h[pos["fill_i"]:i + 1].max()) < float(draw) - 1e-9
                if v[i] == v[i] and v[kp] == v[kp] and v[i] < p.vol_div_ratio * v[kp] and not (p.no_collapse_htf and untouched):
                    d["vol_div"] = True
                    M2.partial_close(pos, tr, sd, ts, c, 0.5, "vol_div", p)
                    _tag(tr, "vol_div")
                    hit("vol_div")
                    if not pos["left"]:
                        return
    # --- 110 the rolling BPR ceiling: each new extreme (side space: high) after a retrace raises the stop under the retrace
    if p.ladder_trail == "rolling_bpr" and not pos.get("day_trade"):
        if h > d["rb_hi"] + 1e-9:
            ks = range(d["rb_i"] + 1, i)
            if len(ks) >= 1:
                lows = [float(sd.l[k]) for k in ks]
                kmin = d["rb_i"] + 1 + int(np.argmin(lows))
                lw = min(lows)
                d["bpr_mt"] = float((min(sd.o[kmin], sd.c[kmin]) + max(sd.o[i], sd.c[i])) / 2.0)      # the body MT of the new balance range [retrace low, new high] (report)
                hit("eval_rolling_bpr")
                if M2.raise_to(pos, lw - tk, "bpr_roll", c, p):
                    _tag(tr, "bpr_roll")
                    hit("bpr_roll")
            d["rb_i"], d["rb_hi"] = i, h
    # --- 57 reclaim of the 09:30 open: the expansion confirmation keeps the runner
    if p.open_reclaim_runner and not d.get("expanding"):
        k570 = _S()._idx_at(ctx, 570)
        if k570 <= i and ctx.t[k570] == 570:
            o930 = float(sd.o[k570])
            lows = sd.l[k570:i + 1]
            kl = k570 + int(np.argmin(lows))
            hit("eval_open_reclaim")
            if float(sd.l[kl]) < o930 - 1e-9 and any(float(sd.c[k]) > o930 + 1e-9 for k in range(kl, i + 1)) and c > o930 + 1e-9:
                d["expanding"] = True
                pos["expanding"] = True
                lvl = M1._lv(pos)
                if not pos.get("runner") and len(pos["fracs"]) >= 2 and pos["k"] < len(pos["fracs"]) - 1:
                    pos["runner"] = True                                     # the last fraction has no target (like po3_runner)
                    pos.update(levels=list(pos["levels"])[:max(1, len(pos["fracs"]) - 1)], final_T=False)
                _tag(tr, "open_reclaim")
                hit("open_reclaim")
    d["hi"] = max(d["hi"], h)


# --- 5. the ladder loop -------------------------------------------------------------------------------------------------------------------------------

def lh_all(pos, t: int, p) -> bool:
    """119: from 15:00 on a fill of ANY rung closes everything left at that rung's price (X11: a target hit in the last hour = done)."""
    on = bool(p.last_hour_target_done and t >= p.last_hour[0])
    if on:
        hit("eval_lh_target")
    return on


def rung_pre(ctx, sd, pos, tr, k: int, lv_, i: int, p, t: int):
    """8 lh_pool_timing: BEFORE the pool rung of a last-hour trade fills. At or after 15:50 the rung keeps a runner (lh_keep_frac of the units) with a new final rung lh_late_ext_pts beyond the
    pool, held to the flatten. Returns "reload" when the ladder was changed (the loop re-reads the rungs), else None."""
    d = pos.get("me3")
    if p.lh_pool_timing and d and _is_lh_trade(tr):
        hit("eval_lh_late")
    if not (p.lh_pool_timing and d and _is_lh_trade(tr)) or t < 950 or d.get("lh_ext"):
        return None
    kinds = list(pos.get("level_kinds") or [])
    if k >= len(kinds) or kinds[k] not in POOLS:
        return None
    fr = list(pos["fracs"])
    if k != len(fr) - 1:
        return None
    keep = max(float(p.lh_keep_frac), 0.0)
    if keep <= 0:
        return None
    d["lh_ext"] = True
    share = max(0.0, 1.0 - sum(fr[:k]) - keep)
    lv = list(pos["levels"])[:k + 1] + [float(lv_[k]) + p.lh_late_ext_pts * p.es_pt]
    pos.update(levels=lv, fracs=tuple(fr[:k] + [share, keep]), level_kinds=kinds[:k + 1] + ["lh_ext"], final_T=False, runner=False)
    hit("lh_late_runner")
    return "reload"


def rung_taken(ctx, sd, pos, tr, k: int, level: float, i: int, p) -> None:
    """A ladder rung k was filled on bar i (units may remain; pos["k"] is already k + 1): 8 the early pool take (before 15:50 nearly everything off, the stop to breakeven), 57 the breakeven
    waits for the next rung while the day is expanding."""
    d = pos.get("me3")
    if not d or not pos["left"]:
        return
    kinds = list(pos.get("level_kinds") or [])
    kind = kinds[k] if k < len(kinds) else ""
    t = int(ctx.t[i])
    MG = _MG()
    if p.lh_pool_timing and _is_lh_trade(tr) and kind in POOLS and t < 950:
        keep_u = max(p.lot, int(round(pos["n"] * p.lh_keep_frac / max(p.lot, 1))) * p.lot)
        extra = pos["left"] - keep_u
        hit("eval_lh_pool_timing")
        if extra > 0:
            M2.partial_close(pos, tr, sd, ctx.idx[i], level, 0.0, "lh_early", p, units=extra)
            MG.raise_stop(pos, MG.be_stop(pos, p))
            _tag(tr, "lh_early")
            hit("lh_early")
    if p.open_reclaim_runner and d.get("expanding") and pos["left"]:
        if k == 0 and not pos["t1_done"]:
            pos["t1_done"] = True                                              # the first partial is made, the breakeven move waits (the ladder loop skips its be_on branch)
            d["be_wait"] = True
            hit("reclaim_be_wait")
        elif k >= 1 and d.get("be_wait"):
            d["be_wait"] = False
            if p.be_on == "t1":
                MG.be_move(pos, p)


# --- 6. the 12:00 AM close / the noon guard -------------------------------------------------------------------------------------------------------------

def am_on(p) -> bool:
    return bool(p.day_mode_no_am_exit or p.am_runner_hold_to or p.explosive_runner or p.am_exit_trend_hold)


def _explosive(ctx, sd, pos, i: int, p) -> bool:
    """117: an explosive day - the range of the bars closed by 10:00 >= ADR5, or by 11:00 >= explosive_frac x ADR5 - and the session extreme in the trade direction was made within the last 15 bars.
    (The two-session profile branch of the spec is not available at 12:00: setups.cc_profile classifies at 13:30.)"""
    S = _S()
    adr = S.adr5(list(getattr(ctx, "hist", None) or [])[-5:])
    if not adr:
        return False
    k10, k11 = S._idx_at(ctx, 600), S._idx_at(ctx, 660)
    a = ctx.start

    def rng(k):
        return float(sd.h[a:k].max() - sd.l[a:k].min()) if k > a else 0.0
    ok = rng(k10) >= adr - 1e-9 or rng(k11) >= p.explosive_frac * adr - 1e-9
    if not ok:
        from . import setups as ST                                  # 117 T13 profile "two_session": the AM leg's profile (classified from the bars closed by 12:00) trends in the trade direction
        prof = ST.cc_profile(ctx, i, p, at=720)
        if not (prof and str(prof[0]).startswith("two_session") and int(prof[1]) == int(sd.sign)):
            return False
        hit("explosive_two_session")
    kx = a + int(np.argmax(sd.h[a:i + 1]))
    return bool(i - kx <= 15)


def _trend_hold(ctx, sd, pos, tr, i: int, p) -> bool:
    """T8-16: a trending day (sm4.trend_day: the bias and the session lock agree, the first MSS went this way, no opposing HTF array reached) with the open position in that direction."""
    from . import sm4
    save = {k: getattr(ctx, k, None) for k in ("cur_lock", "cur_bias", "cur_session")}
    try:
        lk = ctx.lock.get(tr.session) if getattr(ctx, "lock", None) else None
        ctx.cur_lock = lk if (lk is not None and lk.get("side") == sd.sign) else None
        ctx.cur_session = tr.session
        return bool(sm4.trend_day(ctx, sd, i, p))
    finally:
        for k, v in save.items():
            setattr(ctx, k, v)


def am_skip(ctx, sd, pos, tr, i: int, ts, p, am_x: int) -> bool:
    """True = the engine does NOT close the position at the 12:00 AM exit this bar. 116 day mode (no am_exit) and the am_runner_hold_to runner (>= 85 % off at 12:00: at most 2 lots kept on
    the current stop, closed at am_runner_hold_to); 117 the explosive day runner (kept to explosive_until); T8-16 the trend-day hold (kept to the session close). The decision is made at the first
    12:00 bar and kept."""
    d = pos.get("me3")
    if d is None:
        d = pos["me3"] = {"fill_i": pos["fill_i"], "hi": float(sd.h[i]), "rb_i": i, "rb_hi": float(sd.h[i]), "fill_t": int(pos["fill_t"])}
    t, tf = int(ctx.t[i]), ctx.tf
    c = float(sd.c[i])
    hold = d.get("am_hold")
    if hold == "runner":
        if t + tf >= p.am_runner_hold_to:
            M2.close_all(pos, tr, sd, ts, c, "am_runner_hold")
            hit("am_runner_hold_exit")
        return True
    if hold == "explosive":
        if t + tf >= p.explosive_until:
            M2.close_all(pos, tr, sd, ts, c, "explosive_exit")
            hit("explosive_exit")
        return True
    if hold in ("day", "trend"):
        return True
    if hold == "no":
        return False
    if p.day_mode_no_am_exit and (pos.get("day_trade") or pos.get("trade_mode") == "day"):
        d["am_hold"] = "day"
        hit("day_mode_no_am_exit")
        return True
    if p.am_runner_hold_to and tr.session not in ("PM", "LUNCH"):
        hit("eval_am_runner_hold")
    if p.am_runner_hold_to and tr.session not in ("PM", "LUNCH") and _closed(pos) >= 0.85 - 1e-9:
        d["am_hold"] = "runner"
        keep = 2 * p.lot
        extra = pos["left"] - keep
        if extra > 0:
            M2.partial_close(pos, tr, sd, ts, c, 0.0, "am_exit", p, units=extra)
        _tag(tr, "am_runner")
        hit("am_runner_hold")
        return True
    if p.explosive_runner:
        hit("eval_explosive")
    if p.explosive_runner and _explosive(ctx, sd, pos, i, p):
        d["am_hold"] = "explosive"
        _tag(tr, "explosive_runner")
        hit("explosive_runner")
        return True
    if p.am_exit_trend_hold:
        hit("eval_trend_hold")
    if p.am_exit_trend_hold and _trend_hold(ctx, sd, pos, tr, i, p):
        d["am_hold"] = "trend"
        _tag(tr, "trend_hold")
        hit("trend_hold")
        return True
    d["am_hold"] = "no"
    return False


def noon_exempt(pending: dict, p) -> bool:
    """116: the pending-order noon guard (no AM-family fills into 12:00) does not apply to a day-mode order."""
    return bool(p.day_mode_no_am_exit and (pending.get("day_trade") or pending.get("trade_mode") == "day"))


# --- 7. closes ----------------------------------------------------------------------------------------------------------------------------------------

def pre_close(pos, tr, state, p, i) -> bool:
    """130 / 9 (before the re-entry blocks of `_after_close`): True = no loss re-entry. 130: an abort-set exit abandons the direction for the leg (`blocked_side` until a new structure shift in the
    same direction forms after the close); 9: a runner stopped after >= runner_frac_done of the units were banked (tag `runner_stop`)."""
    reason = _last_reason(tr)
    out = False
    if p.abort_blocks_side and (reason in ABORT_REASONS or reason.startswith("pd3")):
        state.setdefault("blocked_side", {})[tr.session] = dict(side=tr.side, i=int(i if i is not None else pos["fill_i"]))
        _tag(tr, "abort_blocks_side")
        hit("abort_blocks_side")
        out = True
    n_all = sum(e[2] for e in tr.exits)
    last_q = tr.exits[-1][2] if tr.exits else 0
    if runner_stop_on(p) and reason in ("stop", "stop_gap", "be") and n_all > 0 and (n_all - last_q) / n_all >= p.runner_frac_done - 1e-9:
        pos["runner_stop"] = True
        _tag(tr, "runner_stop")
        state["no_win_reentry"] = True                                       # sm7: the win / trail-win re-entries refuse this kind
        hit("runner_stop")
        out = True
    return out


def runner_stop_on(p) -> bool:
    """9: the runner_stop refusal ("the re-entry switches of items 2-3 refuse that kind") applies automatically whenever a win / trail-win re-entry switch is on; runner_stop_no_reentry also turns it on alone
    (and adds the final-rung session end)."""
    return bool(p.runner_stop_no_reentry or p.reentry_after_win or p.reentry_after_trail_win or p.breakaway_chase)


def more_reentries(state, session: str, p) -> bool:
    """5: one more same-direction re-entry while the session's count is under reentry_count_max."""
    n = state.get("reentered", {}).get(session)
    return bool(n) and p.reentry_count_max > 1 and int(n) < p.reentry_count_max


def count_reentry(state, session: str, p) -> None:
    """5: the session's re-entry count (True while reentry_count_max is 1: the old flag)."""
    if p.reentry_count_max > 1:
        state["reentered"][session] = int(state["reentered"].get(session) or 0) + 1
        hit("reentry_count")
    else:
        state["reentered"][session] = True


def risk_count(state, session: str, p, m: float) -> float:
    """5: the risk of the n-th re-entry = reentry_risk_mult ** n (2 % -> 1 % -> 0.5 %) when the risk is not the losing trade's own (reentry_risk 'loss' already halves each attempt)."""
    n = state.get("reentered", {}).get(session)
    if p.reentry_count_max > 1 and n and n is not True and p.reentry_risk != "loss":
        return float(p.reentry_risk_mult ** int(n))
    return m


def lost_side_holds(state, session: str, t: int, p) -> bool:
    """1: does the no-reversal lock (reverse_after_loss off) still bar the opposite side? lost_side_scope "session": it holds for the session of the loss and, for an AM loss, until the PM reset
    time (pm_reset_t, 13:30 by default); then either direction is allowed."""
    lf = state.get("lost_fam")
    if lf == _fam(session):
        return True
    return bool(p.lost_side_scope == "session" and lf == "AM" and session == "PM" and t < p.pm_reset_t)


def after_close(ctx, pos, tr, done, key, state, p, i, lost, net, reopened: bool) -> bool:
    """After the trade closed (`_after_close`, after the generic re-entry block): the day / session stops of 9, 10, 15, 17, 8; the re-entry state of 132; the re-entry arms of 65 / 118; the
    London-close second swipe of 199. Returns True when it re-opened the session."""
    sd = pos["side"]
    reason = _last_reason(tr)
    sess = tr.session
    fam = _fam(sess)
    xm = tr.exits[-1][0].hour * 60 + tr.exits[-1][0].minute if tr.exits else 0
    # --- 132 the unrecovered loss
    if net < 0:
        state.setdefault("unrecovered", {})[sess] = float(-net)
    # --- 9 the final rung filled: the session and its Silver Bullet key are done
    if p.runner_stop_no_reentry and tr.final_hit and done is not None:
        done[key] = True
        done["SB_" + sess] = True
        hit("final_done")
    # --- 8 the MOC target hit before 15:45 ends the last-hour slot
    if p.lh_pool_timing and _is_lh_trade(tr) and tr.final_hit and xm < 945 and done is not None:
        done["LH"] = True
        hit("lh_done")
    # --- 10 chop scalps: the count and the day's points
    if p.chop_scalp_pts > 0 and pos.get("scalp_chop") and done is not None:
        state["chop_scalps"] = state.get("chop_scalps", 0) + 1
        units = tr.shares + sum(q for *_, q in tr.adds)
        state["chop_pts"] = state.get("chop_pts", 0.0) + net / max(units, 1) / p.es_pt
        if state["chop_scalps"] >= p.chop_scalp_max or state["chop_pts"] >= p.chop_scalp_day_pts:
            for k in list(done):
                done[k] = True
            state["day_done"] = True
            hit("chop_scalp_done")
    # --- 15 new trader: stop once the day is positive; AM or PM, not both; the experienced draw_open PM
    if p.new_day_stops and p.trader_mode == "new" and done is not None:
        if state.get("day_net", 0.0) > 0:
            for k in list(done):
                done[k] = True
            state["day_done"] = True
            hit("new_day_positive")
        elif fam == "AM":
            done["PM"] = True
            hit("new_am_or_pm")
    if p.pm_after_am_win == "draw_open" and fam == "AM" and lost is None and net > 0 and done is not None and not (p.new_day_stops and p.trader_mode == "new"):
        touched_ = bool(_htf_draw_touched(ctx, sd, pos, i)) if ctx is not None and i is not None else True
        # the draw rule may re-open a PM that only no_pm_after_am_win closed - never one a stop / the day cap closed in this same close
        done["PM"] = True if (touched_ or _MG().blocked_now(state, "PM") or state.get("day_done")) else False
        hit("pm_after_am_win")
    # --- 17 conflicted day: one entry, done after a win
    if p.conflicted_mode == "one_win" and getattr(ctx, "conflicted", False) and net > 0 and done is not None:
        for k in list(done):
            done[k] = True
        state["day_done"] = True
        hit("conflicted_one_win")
    # --- re-entry arms (the generic reentry_half block ran before: `reopened` / state["reentered"])
    if lost is not None and done is not None and ctx is not None and i is not None and reason in ("stop", "stop_gap"):
        fi = pos["fill_i"]
        avg = _avg(pos)
        arm = None
        if p.reentry_breakaway and "breakaway" in (tr.lv_tags or ""):
            hit("eval_breakaway_arm")
        if p.reentry_breakaway and "breakaway" in (tr.lv_tags or "") and float(sd.l[fi:i + 1].min()) <= float(pos["fvg_bottom"]) + 1e-9:
            lvl = _htf_level_below(ctx, sd, pos, i, avg, p)                                         # 65: the gap filled completely - it was not a breakaway
            arm = dict(kind="breakaway", side=tr.side, stop_i=int(i), lvl=lvl, a_i=(int(i) if lvl is None else None), pending=True)
            hit("breakaway_fill_arm")
        elif p.ote_fail_ts and ("ote" in str(tr.entry_kind) or "ote" in (tr.lv_tags or "")):
            lo = _run_low(sd, pos, i, avg)                                                          # 118: the prior low the OTE stop-out ran
            if lo is not None:
                arm = dict(kind="ote_ts", side=tr.side, stop_i=int(i), lvl=float(lo), pending=True)
                hit("ote_stop_arm")
        if arm is not None:
            state.setdefault("re3", {})[sess] = arm
            done[key] = False
            if not state["reentered"].get(sess):
                count_reentry(state, sess, p)
            reopened = True
    # --- 199 the London-close second swipe (T3 lc_reentry machinery, widened to any stopped AM trade whose sweep extreme sat in an HTF array)
    if (p.lc_second_swipe and ctx is not None and lost is not None and not reopened and not state.get("lc_done") and fam == "AM" and done is not None
            and reason in ("stop", "stop_gap") and 600 <= xm < 720):
        arr = _lc_register(ctx, sd, pos, i, p)
        if arr is not None or getattr(ctx, "conf", None) is None:
            sm2.lc_reopen(ctx, tr, done, key, state)
            state.setdefault("reentered", {})[sess] = True                                           # risk x0.5 (the first trade lost)
            hit("lc_second_swipe")
            reopened = True
    return reopened


def _lc_register(ctx, sd, pos, i: int, p):
    """199: the HTF array holding the first trade's sweep extreme, recorded so that lc_reopen binds the retry to it (sm2.lc_array)."""
    sw = dict(ext=float(pos["ext"]), ext_i=int(pos["ext_i"]))
    arr = sm2.lc_array(ctx, sd, sw, i, p)
    if arr is not None:
        sm2._c(ctx).setdefault("lc_arr", {})[round(float(sd.x(sw["ext"])), 6)] = arr
    return arr


def _htf_level_below(ctx, sd, pos, i: int, avg: float, p):
    """65: the HTF level / prior FVG the retrace must reach before the re-entry (side space, below the entry): the top of the nearest same-side HTF array (D / 4h / 1h) under the entry, else the
    top of the nearest earlier gap under the filled one; None = nothing to wait for."""
    from . import sm4
    try:
        arrs = sm4.conf_arrays(ctx, sd, i, ("D", "4h", "1h"), known_at_start=False)
    except (AttributeError, KeyError, TypeError):                                                  # only the "no confluence object / array table" case of a stub or short context
        arrs = []
    cand = [float(a[0]) for a in arrs if float(a[0]) < float(pos["fvg_bottom"]) - p.tick]
    if cand:
        return max(cand)
    prior = [float(g.top) for g in sd.gaps if g.i <= pos["fill_i"] - 3 and float(g.top) < float(pos["fvg_bottom"]) - p.tick]
    return max(prior) if prior else None


def _run_low(sd, pos, i: int, avg: float):
    """118: the prior low the stopped OTE entry ran - the latest confirmed 1m pivot low (known at the fill) under the entry that the trade's low went under."""
    fi = pos["fill_i"]
    _, pls = M2._piv(sd, max(fi - 60, 0), fi - 1)
    lo_t = float(sd.l[fi:i + 1].min())
    c = [q for q in pls if q.known <= fi and q.price < avg - 1e-9 and lo_t < q.price - 1e-9]
    return max(c, key=lambda q: q.i).price if c else None


# --- 8. the once-per-bar hook ---------------------------------------------------------------------------------------------------------------------------

def bar(ctx, i: int, p, state, done, trades, pos, want: int = 0):
    """Called once per bar before the position loop. 1 am_idea_fail (the AM idea fails when price runs the opposite pool with displacement before any AM fill: the AM is done, a pending AM order
    is cancelled; the lost-side lock never applies); 65 the stage-(a) update of the breakaway re-entry (price reached the HTF level). Returns "cancel_am" or None."""
    out = None
    if p.am_idea_fail and want and not done.get("AM") and pos is None:
        t = int(ctx.t[i])
        k570 = _S()._idx_at(ctx, 570)
        if 570 <= t < (p.am_exit or 720) and i > k570 and not any(_fam(x.session) == "AM" for x in trades):
            sd = ctx.sides_map[want]
            opp = ctx.sides_map[-want]
            lev = float(opp.h[k570:i].max())                                                        # the AM session extreme on the opposite side (side space of the OPPOSITE Side: its highs)
            pm = ctx.pd.get("pml" if want > 0 else "pmh")
            if pm is not None:
                lev = min(lev, float(opp.x(pm)))                                                    # ... or the pre-market one: the nearer of the two
            if lev is not None:
                hit("eval_am_idea_fail")
                body = abs(float(opp.c[i]) - float(opp.o[i]))
                prev = np.abs(opp.c[max(0, i - 20):i] - opp.o[max(0, i - 20):i])
                mult = p.displacement_mult or 1.5
                if float(opp.h[i]) >= lev + p.tick - 1e-9 and opp.c[i] > opp.o[i] and (len(prev) == 0 or body >= mult * float(prev.mean())):
                    state["idea_fail"] = "no_fill_run"
                    done["AM"] = True
                    hit("am_idea_fail")
                    out = "cancel_am"
    for sess, r in (state.get("re3") or {}).items():
        if r.get("pending") and r.get("kind") == "breakaway" and r.get("a_i") is None and r.get("lvl") is not None:
            sd = ctx.sides_map[1 if r["side"] == "long" else -1]
            if float(sd.l[i]) <= r["lvl"] + 1e-9 and i > r["stop_i"]:
                r["a_i"] = int(i)
                hit("breakaway_wait_done")
    return out


# --- 9. the order stage -------------------------------------------------------------------------------------------------------------------------------

def order_block(ctx, sd, sw, i: int, p, session: str, entry: float, tags: dict, state=None):
    """The entry blocks of the chunk (a filter tag or None): 130 a same-direction setup on the leg an abort closed, until a new structure shift (MSS bar after the close); 65 the breakaway re-entry
    waits for the HTF level, then a new MSS + gap; 123 no CC order from cc_day_exit on; 13 the PM entry window after three failed AM arrays; 10 chop scalps only at a gap retrace."""
    t = int(ctx.t[i])
    state = state if state is not None else getattr(ctx, "state7", None) or {}
    sidename = "long" if sd.sign > 0 else "short"
    if p.abort_blocks_side:
        b = (state.get("blocked_side") or {}).get(session)
        if b is not None and b["side"] == sidename:
            brk = sw.get("broke")
            if brk is None:
                brk = sw.get("ext_i")                                  # a setup without an MSS bar: the bar of its sweep extreme dates the structure (a new leg formed after the close lifts the block)
            if brk is None or int(brk) <= int(b["i"]):
                hit("abort_block_order")
                return "x_abort_blocks_side"
            b["i"] = -1                                                # a new structure shift formed after the close: the block lifts
    if p.reentry_breakaway:
        r = (state.get("re3") or {}).get(session)
        if r is not None and r.get("pending") and r.get("kind") == "breakaway" and r["side"] == sidename:
            if r.get("a_i") is None:
                hit("breakaway_wait_block")
                return "x_reentry_breakaway_wait"
            brk = sw.get("broke")
            if brk is None or int(brk) <= int(r["a_i"]) or not any(r["a_i"] < g.i <= i for g in sd.gaps):
                hit("breakaway_mss_block")
                return "x_reentry_breakaway_mss"
    if p.chop_scalp_pts > 0 and p.sloppy_mode == "scalp" and getattr(ctx, "cur_sloppy", "") and str(tags.get("entry_kind", "fvg")) != "fvg":
        hit("chop_scalp_not_fvg")
        return "x_chop_scalp_not_fvg"                               # 10: chop scalps only at a 1m FVG retrace
    if p.cc_day_exit and t >= p.cc_day_exit and str(tags.get("entry_kind", "")).startswith(("cc_", "ts_cc_")):
        hit("cc_day_exit_block")
        return "x_cc_day_exit"
    if p.pd3_pm_window and session == "PM":
        hit("eval_pm_window")
        win = state.get("pm_window")
        if win is not None and not (win[0] <= t < win[1]):
            hit("pm_window_block")
            return "x_pd3_pm_window"
    return None


def any_re_orders(ctx, p) -> bool:
    r = getattr(ctx, "re3_now", None)
    return bool(r and r.get("pending") and r.get("kind") == "ote_ts" and p.ote_fail_ts)


def re_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """118: the turtle-soup long at the low the OTE stop-out ran (side space): once price has traded under that low by at most ts_max_pts and a candle closed back above it within ts_back_bars,
    a limit at the old low, the stop under the false-break extreme, the nearest old high as the (standard) target; half risk (the X13 re-entry)."""
    from . import sm4
    r = getattr(ctx, "re3_now", None)
    if not r or not r.get("pending") or r.get("kind") != "ote_ts" or r.get("armed"):
        return None
    if r["side"] != ("long" if sd.sign > 0 else "short"):
        return None
    lvl = float(r["lvl"])
    si = int(r["stop_i"])
    idx = np.flatnonzero(sd.l[max(si - 5, 0):i + 1] < lvl - 1e-9)
    if not len(idx):
        return None
    hit("eval_ote_ts")
    ext_i = max(si - 5, 0) + int(idx[np.argmin(sd.l[max(si - 5, 0):i + 1][idx])])
    if not L.turtle_soup(sd.l, sd.c, lvl, ext_i, i, p.ts_max_pts * p.es_pt, p.ts_back_bars):
        return None
    entry, stop = lvl, float(sd.l[ext_i]) - p.pad
    if not (stop < entry < sd.c[i]) or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    o = sm4._order(ctx, sd, i, p, session, risk_mult, "ote_ts", entry, stop, level=entry, ext=float(sd.l[ext_i]), ext_i=int(ext_i), broke=i, lv=("ote_ts",))
    if o is not None:
        r["armed"] = True
        hit("ote_ts_order")
    return o


def flip_order(ctx, state, i: int, p, risk_mult: float):
    """42: the offside flip - a market order on the opposite side at the next open after the offside close: the closed units, the stop under the reaction candles' bodies / the CE of their lower
    wick, the target the nearest buy-side pool (the engine's standard target list). Returns the order or None."""
    from . import sm4
    req = state.pop("flip_req", None)
    if not req:
        return None
    hit("eval_offside_flip")
    S = _S()
    sg = -req["sign"]
    sd = ctx.sides_map[sg]
    a = int(req["arm_i"])
    seg = range(a, i + 1)
    body_lo = min(min(float(sd.o[k]), float(sd.c[k])) for k in seg)
    kmin = min(seg, key=lambda k: sd.l[k])
    wick_ce = (float(sd.l[kmin]) + min(float(sd.o[kmin]), float(sd.c[kmin]))) / 2.0
    stop = min(body_lo, wick_ce) - p.pad
    entry = float(sd.c[i])
    if not stop < entry or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    session = req["session"]
    ctx.cur_session, ctx.cur_lock, ctx.cur_lock_any, ctx.cur_bias, ctx.counter_now, ctx.curve_now = session, None, None, 0, False, ""       # (outside the sides loop: no stale lock / bias of the last scanned side)
    o = sm4._order(ctx, sd, i, p, session, risk_mult, "offside_flip", entry, stop, level=entry, ext=float(sd.l[kmin]), ext_i=int(kmin), broke=i, lv=("offside_flip",), market=True)
    if o is None:
        return None
    n = int(req["n"])
    o["shares"] = n
    o["plan_shares"] = n
    o["offside_flip"] = True
    hit("offside_flip")
    return o


def conflicted_day(hist, bias, p) -> bool:
    """17: the HTF narrative is conflicted - both sides valid (the B17.1 neutral_5050 reading of the htf.table row) or yesterday's whole range inside one open daily FVG (B17.4 inside_bisi)."""
    S = _S()
    if bias is not None and hasattr(bias, "get"):
        v = bias.get("fifty")
        if v is not None and v == v and int(v):
            return True
    return bool(S._inside_daily_fvg(hist))
