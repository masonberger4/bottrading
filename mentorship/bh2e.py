"""Caption-gap pass, package bias_htf#2/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 82-88, 90, 91, 93-96, 104-109, 114, 116, 117, 119, 121, 122, 130-136, 138, 139) - ENGINE SIDE.

The bar-loop part: side gates, the bias fallbacks, the draw-lock adjustments (at the lock and per bar), scalp / size / target hooks, order tags. The columns they read are built by `bh2.py` inside
`htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a completed hist session. Hooks (who calls them)
  bias_value_adjust bias_day.bias_value        htf_bias_tf (W / M), wk_q75_confirm, htf_after_draw "reverse", fast_draw_extend
  want_adjust       bias_day.want_at           qshift_bias, dsmt_bias, raid_profile_bias, eq_tiebreak (a neutral bias takes the structural reading)
  side_ok           daycontext.side_ok tail    raid_side_gate, ipda_extreme_pause, sibi_gate, consol_dir, inside_bisi_release (side), dxy_needs_rates lives in bh1e
  order_ok          daycontext.order_ok tail   pd_two_level, tier_regime_gate, consol_dir entries, range_no_bias, tags (soft_carry, iof_w, q_window, dsmt, rates, im_regime, ...)
  scalp_now         daycontext.scalp_now tail  sibi inside, pd3 caution, qshift consolidation, range_no_bias, decoupled   (scalp_cap: the single range target)
  size_mult         bias_day.size_mult         scalp_week_risk, soft_carry_risk, iof_w_risk
  targets_post      strategy._targets          tier_regime_gate trim, htf_rank_tf projection
  lock_cands / lock_post / lock_bar   strategy.mark_levels / _lock_step   fast_draw next array, soft carry, q_obj, tier regime, ipda side, PM reversal / wick CE 60m, reversal after target
  sloppy_release    strategy.run_day           inside_bisi_release
  extras_unblocked  manage.extras_blocked      allow_reversal_after_target: the PM Silver Bullet after a winning AM trade whose lock reversed
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

from collections import Counter

import numpy as np

from . import bh1e as B1
from . import levels as L

HITS: Counter = Counter()


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def _BD():
    return B1._BD()


_n, _f, _row = B1._n, B1._f, B1._row


def on(p) -> bool:
    """Any engine-side bias_htf#2/7 switch is on (the hooks return at once otherwise)."""
    return bool(p.bias_neutral == "scalp_week" or p.q_days_tag or p.q_window_gate or p.shift_due_tag or p.q_window_size != 1.0 or p.qshift_bias or p.q_obj_lean or p.qshift_strong_consol or p.iof_weekly_weight
                or p.sibi_gate or p.wick_ce_60m or p.sibi15_ce_cancel or p.allow_reversal_after_target or p.soft_carry or p.inside_bisi_release or p.fast_draw_extend or p.dxy_needs_rates
                or p.pd3_first_caution or p.wk_q75_confirm or p.consol_dir != "off" or p.htf_after_draw == "reverse" or p.pd_two_level or p.range_no_bias or p.eq_tiebreak
                or p.tier_regime_gate or p.raid_profile_bias or p.htf_bias_tf != "D" or p.htf_rank_tf or p.dsmt_bias or p.im_regime_tag or p.raid_side_gate or p.ipda_draw_side
                or p.ipda_extreme_pause or p.decoupled_scalp)


def want_on(p) -> bool:
    return bool(p.qshift_bias or p.dsmt_bias or p.raid_profile_bias or p.eq_tiebreak)


def lock_on(p) -> bool:
    return bool(p.wick_ce_60m or p.sibi15_ce_cancel or p.allow_reversal_after_target)


def targets_on(p) -> bool:
    return bool(p.tier_regime_gate or p.htf_rank_tf)


def _im(ctx) -> dict:
    return getattr(ctx, "intermarket", None) or {}


# --------------------------------------------------------------------------------------------------------------
# the bias reading (bias_day.bias_value)
# --------------------------------------------------------------------------------------------------------------

def bias_value_adjust(row, p, v: int, obj_day: int, obj_week: int) -> tuple:
    """(value, handled): the bias_htf#2/7 changes of the table bias reading. `handled` True = the caller returns the value as it is (the objective-met neutral already decided)."""
    if p.htf_bias_tf != "D":
        m, w_ = _n(row, "bias_m"), _n(row, "bias_w")
        v = (m or w_) if p.htf_bias_tf == "M" else w_                  # B5-monthly-first-hierarchy: the monthly draw, if unclear the weekly, if both unclear none (daily moves against it are retracements)
    if p.wk_q75_confirm and v and _n(row, "wk_q75") != v:
        v = 0                                                          # B8-weekly-wick-quadrant-gate: the bias counts only after a daily close beyond the wick's 75 % level in its direction
    if p.objective_neutral in ("day", "both") and obj_day:
        return (_n(row, "after_draw_d") if p.htf_after_draw == "reverse" else 0), True
    if p.objective_neutral in ("week", "both") and obj_week:
        if p.fast_draw_extend and _n(row, "fast_draw"):
            return v, True                                             # NEW-speed-into-weekly-draw: a fast run into the weekly draw keeps the bias (the next weekly array is the new draw)
        return (_n(row, "after_draw_w") if p.htf_after_draw == "reverse" else 0), True
    return v, False


def want_adjust(ctx, p, session: str, i: int, base: int) -> int:
    """bias_day.want_at tail: a neutral bias takes (in order) the quarterly shift, the daily SMT, the raid profile, the EQ tie-break."""
    if base or not want_on(p):
        return base
    row = _row(ctx, session, i)
    if row is None:
        return base
    if p.qshift_bias:
        v = _n(row, "qshift")
        if v and not (p.qshift_strong_consol and row.get("qs_form") == "consol"):
            hit("want_qshift")
            return v
    if p.dsmt_bias:
        v = int(_im(ctx).get("dsmt", 0) or 0)
        if v and (not p.q_window_gate or _n(row, "q_window")):
            hit("want_dsmt")
            return v
    if p.raid_profile_bias:
        v = _n(row, "raid_profile")
        if v:
            hit("want_raid_profile")
            return v
    if p.eq_tiebreak:
        if _n(row, "eq_near") and _n(row, "last_break"):
            hit("want_eq_tiebreak")
            return _n(row, "last_break")
        if _n(row, "eq_near_m") and _n(row, "last_break_m"):
            hit("want_eq_tiebreak_m")
            return _n(row, "last_break_m")
    return base


# --------------------------------------------------------------------------------------------------------------
# helpers on the bars
# --------------------------------------------------------------------------------------------------------------

def swing60(ctx, i: int):
    """The last 60m swing range at closed bar i: (high, low) of the most recent confirmed 3-candle pivot high and pivot low of the complete 60m bars (yesterday + today); None when either is missing."""
    b = B1.tf_complete(ctx, 60, i)
    if len(b["c"]) < 5:
        return None
    ph, pl = L.pivots(b["h"], b["l"], 1)
    if not ph or not pl:
        return None
    hi, lo = float(ph[-1].price), float(pl[-1].price)
    return (hi, lo) if hi > lo else None


def unbiased(ctx, p, session: str, i: int) -> bool:
    """No bias for the session: the bias reading is 0 (always so with htf_bias 'off') and the session lock has no side."""
    w = _BD().want_at(ctx, p, session, i) if p.htf_bias != "off" else 0
    lk = (getattr(ctx, "lock", None) or {}).get("AM" if session == "LUNCH" else session)
    return w == 0 and not (lk is not None and lk.get("side"))


def sibi_state(ctx, p, row, i: int):
    """NEW-daily-sibi-bias-gate (086 ~2:22, ~12:30): (allowed side, scalp) from the nearest daily FVG formed after the last sweep - sibi_dir -1 (a bear FVG after a sell-side sweep): a close under its CE =
    only shorts; inside it above the CE, or above its high without a holding bar = only longs, as scalps; above its high with a bar whose low holds above it = longs toward the buy-side pool (no scalp).
    sibi_dir +1 (a BISI after a buy-side sweep) mirrors it. None without a zone."""
    if row is None:
        return None
    d_ = _n(row, "sibi_dir")
    top, bot = _f(row, "sibi_top"), _f(row, "sibi_bot")
    if not d_ or top != top or bot != bot:
        return None
    ce = (top + bot) / 2
    px = float(ctx.c[i])
    a = ctx.start
    if d_ < 0:
        if px < ce:
            return (-1, False)
        held = bool(px > top and any(ctx.c[j] > top and ctx.l[j + 1] > top for j in range(a, i)))
        return (1, not held)
    if px > ce:
        return (1, False)
    held = bool(px < bot and any(ctx.c[j] < bot and ctx.h[j + 1] < bot for j in range(a, i)))
    return (-1, not held)


def decoupled(ctx, p):
    """B19-four-asset-risk-map (cc10_019 ~6:41): None when the legs are missing, else True when the instrument's 20-session trend is NOT in harmony with the dollar (trend == -dxy) and, when a commodity
    leg is loaded (ctx.intermarket['crb']), with commodities (trend == crb)."""
    im = _im(ctx)
    dx = int(im.get("dxy", 0) or 0)
    hist = getattr(ctx, "hist", None) or []
    tr = 0
    if len(hist) >= 21:
        cl = [float(x.close.iloc[-1]) for x in hist[-21:]]
        tr = int(np.sign(cl[-1] - cl[0]))
    if not tr:
        tr = int(im.get("spx20", 0) or 0)
    if not dx or not tr:
        return None
    ok = tr == -dx
    crb = int(im.get("crb", 0) or 0)
    if crb:
        ok = ok and tr == crb
    return not ok


def season_side(day) -> int:
    """The seasonal direction of the day: the first calendar window (calendar.SEASON_WINDOWS priority order) the date falls in, else the intramonth map (calendar.season_dir); 0 = none."""
    from . import calendar as CAL
    for _nm, dr, a, b in CAL.SEASON_WINDOWS:
        if CAL._in_window(day, a, b):
            return int(dr)
    return int(CAL.season_dir(day))


def season(day) -> str:
    """B18-htf-daily-smt (cc03_005 ~19:41; cc10_016): 'trend' in the seasonally bullish windows (Feb-Apr, Oct-Jan), 'short' between spring and fall (May-Sep) [our interpretation of Feb-May / May-Aug]."""
    m = day.month
    return "short" if 5 <= m <= 9 else "trend"


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#2/7 reason, else None."""
    if not on(p) or i is None:
        return None
    row = _row(ctx, session, i)
    if row is not None:
        if p.raid_side_gate:
            v = _n(row, "raid_side60")
            if v and sign == -v:
                return "x_bh2_raid_side"
        if p.ipda_extreme_pause:
            v = _n(row, "ipda_pause")
            if v and sign == v:
                return "x_bh2_ipda_pause"
        if p.sibi_gate:
            st = sibi_state(ctx, p, row, i)
            if st is not None and sign != st[0]:
                return "x_bh2_sibi"
        if p.consol_dir == "first_expansion":
            if _n(row, "drange_in"):
                return "x_bh2_consol_wait"
            br = _n(row, "drange")
            if br and sign != br:
                return "x_bh2_consol_side"
        elif p.consol_dir == "prior_strongest" and _n(row, "drange_in"):
            pr = _n(row, "consol_prior")
            if pr and sign != pr:
                return "x_bh2_consol_prior"
    if p.inside_bisi_release:
        s_ = getattr(ctx, "inside_side", 0)
        if s_ and sign != s_:
            return "x_bh2_inside_release"
    return None


# --------------------------------------------------------------------------------------------------------------
# scalps and sizes
# --------------------------------------------------------------------------------------------------------------

def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """The bias_htf#2/7 reason an order of `session` is a scalp (one exit, no adds), else ''."""
    if not on(p) or i is None:
        return ""
    row = _row(ctx, session, i)
    if p.sibi_gate and sign and row is not None:
        st = sibi_state(ctx, p, row, i)
        if st is not None and st[1] and sign == st[0]:
            return "bh2_sibi"
    if p.pd3_first_caution and sign and row is not None and 1 <= _n(row, "pd3_n") <= 2 and _n(row, "flip") == sign:
        return "bh2_pd3"
    if p.qshift_strong_consol and row is not None and _n(row, "qs_scalp"):
        return "bh2_qshift_consol"
    if p.range_no_bias and sign and unbiased(ctx, p, session, i) and swing60(ctx, i) is not None:
        return "bh2_range"
    if p.decoupled_scalp and decoupled(ctx, p):
        return "bh2_decoupled"
    return ""


def scalp_cap(ctx, sd, i: int, p, dws: str, entry: float, first: float):
    """The scalp's target (side space) for the bias_htf#2/7 reasons, or None (the caller's default)."""
    if dws == "bh2_range":
        rng = swing60(ctx, i)
        if rng is None:
            return None
        tick = 0.25 * p.es_pt
        t = sd.x(rng[0] + tick) if sd.sign > 0 else sd.x(rng[1] - tick)          # B3-range-trading-without-bias: just beyond the opposite internal swing extreme
        return t if t > entry else None
    return None


def size_mult(ctx, sd, i: int, p, lvt: list, session: str = "") -> float:
    """scalp_week_risk (a neutral week), soft_carry_risk (the carried soft bias), iof_w_risk (an order against the weekly order flow)."""
    if not on(p):
        return 1.0
    m = 1.0
    session = session or getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    row = _row(ctx, session, i)
    if p.bias_neutral == "scalp_week" and p.htf_bias != "off" and _BD().want_at(ctx, p, session, i) == 0:
        lvt.append("size_scalp_week")
        m *= p.scalp_week_risk
    lk = (getattr(ctx, "lock", None) or {}).get("AM" if session == "LUNCH" else session)
    if p.soft_carry and lk is not None and lk.get("side") == sd.sign and "soft_carry" in (lk.get("bh2") or ()):
        lvt.append("size_soft_carry")
        m *= p.soft_carry_risk
    if p.iof_weekly_weight and row is not None:
        v = _n(row, "iof_w")
        if v and v == -sd.sign:
            lvt.append("size_iof_w")
            m *= p.iof_w_risk
    if p.q_window_size != 1.0 and row is not None and _n(row, "q_window"):
        bias = _BD().want_at(ctx, p, session, i) if p.htf_bias != "off" else int((lk or {}).get("side") or 0)
        if bias == sd.sign and season_side(ctx.day) == sd.sign:           # B22-timing-tool: the time window, the bias and the seasonal direction agree: a candidate mega trade
            lvt.append("size_q_window")
            m *= p.q_window_size
    return m


# --------------------------------------------------------------------------------------------------------------
# per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#2/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p):
        return None
    tags: list = []
    row = _row(ctx, session, i)
    entry_raw = sd.x(o["entry"])
    if row is not None:
        # item 106: the two-level discount
        if p.pd_two_level:
            eq = _f(row, "eq20_body")
            if eq == eq:
                if not (entry_raw <= eq if sd.sign > 0 else entry_raw >= eq):
                    return "x_bh2_pd_two_level"
                tags.append("htf_discount")
        # item 109 / 135: the structural regime
        if p.tier_regime_gate:
            reg = _n(row, "tier_regime")
            if reg == -sd.sign and (not p.tug_required or _n(row, "tug") == reg):
                ith = _f(row, "tier_ith")
                if ith == ith and o["t1"] > sd.x(ith) + 1e-9:
                    return "x_bh2_tier_regime"
                tags.append("tier_regime")
        # item 104: where inside / after the range an entry may sit
        if p.consol_dir != "off":
            hi, lo = _f(row, "drange_hi"), _f(row, "drange_lo")
            if hi == hi and lo == lo and hi > lo:
                eq = (hi + lo) / 2
                if p.consol_dir == "first_expansion" and _n(row, "drange") and not _n(row, "drange_in"):
                    ok = entry_raw <= eq + p.consol_chase_frac * (hi - lo) if sd.sign > 0 else entry_raw >= eq - p.consol_chase_frac * (hi - lo)
                    if not ok:
                        return "x_bh2_consol_chase"
                    tags.append("consol_first_expansion")
                elif p.consol_dir == "prior_strongest" and _n(row, "drange_in"):
                    if not (entry_raw <= eq if sd.sign > 0 else entry_raw >= eq):
                        return "x_bh2_consol_discount"
                    tags.append("consol_prior_strongest")
        # tags
        if p.iof_weekly_weight:
            v = _n(row, "iof_w")
            if v:
                tags.append("iof_w_agree" if v == sd.sign else "iof_w_oppose")
        if p.q_days_tag or p.q_window_gate or p.shift_due_tag:
            if _n(row, "q_window"):
                tags.append("q_window")
            if p.shift_due_tag and _n(row, "shift_due"):
                tags.append("shift_due")
        if p.qshift_strong_consol or p.qshift_bias or p.q_obj_lean:
            if _n(row, "qshift") and row.get("qs_form"):
                tags.append("qshift_" + str(row.get("qs_form")))
        if p.htf_after_draw == "reverse" or p.fast_draw_extend or p.objective_neutral != "off":
            if _n(row, "obj_day") or _n(row, "obj_week"):
                rev = p.htf_after_draw == "reverse" and (_n(row, "after_draw_d") or _n(row, "after_draw_w"))
                tags.append("after_draw_reverse" if rev else "after_draw_neutral")
            if p.fast_draw_extend and _n(row, "fast_draw"):
                tags.append("fast_draw")
        if p.sibi_gate:
            st = sibi_state(ctx, p, row, i)
            if st is not None:
                tags.append("sibi_" + ("short" if st[0] < 0 else "long") + ("_scalp" if st[1] else ""))
    if p.range_no_bias and unbiased(ctx, p, session, i):
        rng = swing60(ctx, i)
        if rng is not None:
            hi, lo = rng
            pos = lo + p.range_no_bias_pct * (hi - lo)
            neg = lo + (1 - p.range_no_bias_pct) * (hi - lo)
            if not (entry_raw >= pos if sd.sign < 0 else entry_raw <= neg):
                return "x_bh2_range_loc"
            tags.append("range_no_bias")
    lk = (getattr(ctx, "lock", None) or {}).get("AM" if session == "LUNCH" else session)
    if lk is not None and lk.get("bh2") and lk.get("side") == sd.sign:
        tags += [t for t in lk["bh2"] if t != "soft_carry"]
        if "soft_carry" in lk["bh2"]:
            tags.append("soft_carry")
            o["no_adds"] = True                                            # B17-unreached-draw-soft-bias: a soft bias is not pyramided
    im = _im(ctx)
    if p.dsmt_bias:
        v = int(im.get("dsmt", 0) or 0)
        if v and v == sd.sign:
            tags.append("dsmt_" + season(ctx.day))
    if p.dxy_needs_rates or p.im_regime_tag:
        ra = int(im.get("rates_dxy_agree", 0) or 0)
        if ra:
            tags.append("rates_agree" if ra > 0 else "rates_diverge")
    if p.im_regime_tag and im.get("im_regime"):
        tags.append("im_" + str(im["im_regime"]))
    if p.decoupled_scalp:
        d_ = decoupled(ctx, p)
        if d_:
            tags.append("decoupled")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


# --------------------------------------------------------------------------------------------------------------
# targets
# --------------------------------------------------------------------------------------------------------------

def targets_post(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """tier_regime_gate: in the high-resistance regime no counter-side target above the defended ITH (below the ITL); htf_rank_tf: the weekly / monthly draw levels of the table row join the rungs and
    replace a daily rung at the same level (the higher timeframe ranks first)."""
    session = getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    row = _row(ctx, session, i)
    if row is None:
        return lv
    if p.tier_regime_gate:
        reg = _n(row, "tier_regime")
        if reg == -sd.sign and (not p.tug_required or _n(row, "tug") == reg):
            ith = _f(row, "tier_ith")
            if ith == ith:
                x = sd.x(ith)
                kept = [(v, k) for v, k in lv if v <= x + 1e-9]
                if len(kept) != len(lv):
                    hit("tier_trim")
                lv = kept
    if p.htf_rank_tf:
        tol = p.eq_tol_pts * p.es_pt
        add = []
        for key, nkey in (("draw_up", "draw_up_name"), ("draw_dn", "draw_dn_name")):
            v, nm = _f(row, key), str(row.get(nkey) or "")
            if v == v and nm[:2] in ("W_", "M_") and sd.x(v) > above:
                add.append(sd.x(v))
        for x in add:
            lv = [(a, k) for a, k in lv if abs(a - x) > tol] + [(x, "array")]
            hit("rank_tf_rung")
        lv = sorted(lv, key=lambda t: t[0])
    return lv


# --------------------------------------------------------------------------------------------------------------
# the draw lock: candidates and the adjustments at the lock time
# --------------------------------------------------------------------------------------------------------------

def lock_cands(ctx, p, row, t_lock: int, start: int) -> list:
    """NEW-speed-into-weekly-draw: the next weekly array beyond a fast weekly draw is a lock candidate."""
    out = []
    if row is not None and p.fast_draw_extend and _n(row, "fast_draw"):
        v = _f(row, "fast_next")
        if v == v:
            out.append((v, "array", "fast_draw_next", 0, start))
    return out


def _carry(ctx, p, row, kl: int, px: float, mn: float):
    """B17-unreached-draw-soft-bias (087 ~0:30): the previous trading day's last lock with a side that was not delivered, unless the flip state changed, its target traded overnight, or the opposing pool (the
    prior day's low for a long carry, high for a short) was taken overnight. Returns (side, target, kind) or None."""
    prior = getattr(ctx, "prior_locks", None) or []
    days = sorted({lk["day"] for lk in prior if lk.get("day") is not None and lk["day"] < ctx.day})
    if not days or (ctx.day - days[-1]).days > 5:
        return None
    ls = [lk for lk in prior if lk.get("day") == days[-1] and lk.get("side") and not lk.get("failed") and lk.get("target") is not None]
    if not ls:
        return None
    lk = ls[-1]
    if lk.get("delivered"):
        return None
    side, tgt = int(lk["side"]), float(lk["target"])
    if lk.get("flip") is not None and int(lk["flip"]) != _n(row, "flip"):
        return None
    if (tgt - px) * side < mn:
        return None
    a = ctx.start
    if kl > a:
        if (side > 0 and ctx.h[a:kl].max() >= tgt) or (side < 0 and ctx.l[a:kl].min() <= tgt):
            return None
        opp = ctx.pd.get("pdl1" if side > 0 else "pdh1")
        if opp is not None and ((side > 0 and ctx.l[a:kl].min() < opp) or (side < 0 and ctx.h[a:kl].max() > opp)):
            return None
    return side, tgt, lk.get("kind") or "pool"


def lock_post(ctx, p, row, t_lock: int, session: str, kl: int, px: float, lock: dict) -> dict:
    """mark_levels tail (after bh1e.lock_post): fast / PM reversal, ipda side, tier regime, quarterly objective, soft carry."""
    if not on(p) or B1._c(ctx).get("no_post"):
        return lock
    mn = p.draw_lock_min_pts * p.es_pt
    if p.soft_carry:
        lock["flip"] = _n(row, "flip")
    # item 132: the next 20 / 40 / 60-day extreme on the side of the last daily MSS
    if p.ipda_draw_side and row is not None:
        s_ = _n(row, "last_break")
        if s_:
            cs = [m for m in lock.get("marked", ()) if str(m[2]).startswith("ipda") and ((m[0] > px) if s_ > 0 else (m[0] < px)) and abs(m[0] - px) >= mn]
            if cs:
                v, k_, n_, d_ = min(cs, key=lambda m: abs(m[0] - px))
                lock.update(side=s_, target=v, kind=k_, name=n_)
                lock.setdefault("bh2", []).append("ipda_draw_side")
                hit("lock_ipda_side")
    # item 105: a PM draw may reverse an AM draw hit at a 4h / daily array
    if p.htf_after_draw == "reverse" and t_lock >= 810:
        am = (getattr(ctx, "lock", None) or {}).get("AM")
        nm = str((am or {}).get("name") or "")
        if am is not None and am.get("delivered") and am.get("side") and (nm.startswith("htf") or "htf_4h" in nm or "htf_D" in nm):
            if B1._force(lock, -int(am["side"]), px, mn, "after_draw_pm", kinds=None):
                lock.setdefault("bh2", []).append("after_draw_reverse")
    if row is not None and lock["side"] == 0:
        # item 109 / 135
        if p.tier_regime_gate:
            reg = _n(row, "tier_regime")
            if reg and (not p.tug_required or _n(row, "tug") == reg):
                if B1._force(lock, reg, px, mn, "tier_regime"):
                    lock.setdefault("bh2", []).append("tier_regime")
        # item 83
        if lock["side"] == 0 and p.q_obj_lean:
            q = _f(row, "q_obj")
            if q == q and abs(q - px) >= mn:
                lock.update(side=1 if q > px else -1, target=q, kind="array", name="q_obj")
                lock.setdefault("bh2", []).append("q_obj")
                hit("lock_q_obj")
        # item 90
        if lock["side"] == 0 and p.soft_carry:
            c = _carry(ctx, p, row, kl, px, mn)
            if c is not None:
                lock.update(side=c[0], target=c[1], kind=c[2], name="soft_carry")
                lock.setdefault("bh2", []).append("soft_carry")
                hit("lock_soft_carry")
    return lock


# --------------------------------------------------------------------------------------------------------------
# the per-bar lock changes
# --------------------------------------------------------------------------------------------------------------

def _wick60_cancel(ctx, p, lk: dict, i: int) -> str:
    """A23-intraday-close-line-in-sand: '' / the reason the locked side is cancelled at closed bar i - a completed 60m bar closed beyond the prior day's wick CE (090 ~19:57), or a trade beyond the CE of
    the session's latest 15m FVG against the lock (092 ~2:10:25)."""
    side = lk["side"]
    S = _S()
    kl = S._idx_at(ctx, lk.get("t_lock", 570))
    if p.wick_ce_60m:
        w = getattr(ctx, "wick", None)
        if w is not None:
            ce = float(w["upper"] if side < 0 else w["lower"])
            b = B1.tf_complete(ctx, 60, i)
            cl = b["c"][b["last"] >= kl]
            if len(cl) and ((cl.max() > ce) if side < 0 else (cl.min() < ce)):
                return "wick_ce_60m"
    if p.sibi15_ce_cancel:
        b = B1.tf_complete(ctx, 15, i)
        keep = b["first"] >= ctx.start
        if keep.sum() >= 3:
            o, h, l, c = (b[k][keep] for k in ("o", "h", "l", "c"))
            zs = [z for z in L.fvgs(h, l, o, c) if z.kind == ("bear" if side < 0 else "bull")]
            if zs:
                z = zs[-1]
                ce = (z.top + z.bottom) / 2
                a = int(b["last"][keep][z.i])
                seg_h, seg_l = ctx.h[a + 1:i + 1], ctx.l[a + 1:i + 1]
                if len(seg_h) and ((seg_h.max() > ce) if side < 0 else (seg_l.min() < ce)):
                    return "sibi15_ce"
    return ""


def _reversal_ok(ctx, p, lk: dict, i: int) -> bool:
    """B3-reversal-after-target (086 ~10:26): after the draw was reached, a bar that wicked into a breaker of the opposite colour (bullish after a delivered sell-side draw) and the next 3 bars' bodies
    stayed beyond the wick's extreme. [our interpretation: the breaker is one of today's closed-bar breakers (levels.breaker_zone via levels.breakers) formed before the wick bar]"""
    side, di = lk["side"], lk["delivered_i"]
    a = ctx.start
    if i - 3 < di:
        return False
    zs = L.breakers(ctx.o[a:i + 1], ctx.h[a:i + 1], ctx.l[a:i + 1], ctx.c[a:i + 1], p.pivot_n, p.breaker_zone)
    zs = [z for z in zs if z.kind == ("bull" if side < 0 else "bear")]
    for j in range(di, i - 2):
        for z in zs:
            if a + z.i >= j:
                continue
            if side < 0 and ctx.l[j] <= z.top:
                bodies = np.minimum(ctx.o[j + 1:j + 4], ctx.c[j + 1:j + 4])
                if len(bodies) == 3 and bodies.min() > ctx.l[j]:
                    return True
            if side > 0 and ctx.h[j] >= z.bottom:
                bodies = np.maximum(ctx.o[j + 1:j + 4], ctx.c[j + 1:j + 4])
                if len(bodies) == 3 and bodies.max() < ctx.h[j]:
                    return True
    return False


def lock_bar(ctx, p, s_: str, lk: dict, i: int, done: dict, spent, state=None):
    """_lock_step hook (after bh1e.lock_bar), once per bar and session lock: returns (new_lock, cancel_pending) when the lock changes, else None."""
    side = lk.get("side", 0)
    if not side:
        return None
    # item 88: the reversal after the target
    if p.allow_reversal_after_target and lk.get("delivered") and not lk.get("rev_done") and lk.get("delivered_i") is not None:
        st_day = ((state or {}).get("stops") or {}).get("day")
        blocked = bool(state is not None and (state.get("day_done") and st_day != "win"))
        if not blocked and _reversal_ok(ctx, p, lk, i):
            nl = B1._relock(ctx, p, s_, lk, i, spent, -side, "reversal_after_target")
            nl["rev_done"] = True
            nl["rev_after_target"] = True
            nl.setdefault("bh2", []).append("reversal_after_target")
            if nl["side"]:
                done[s_] = False
            hit("reversal_after_target")
            return nl, True
    if lk.get("delivered"):
        return None
    # item 87: the 60m close beyond the wick CE / a trade beyond the 15m FVG's CE cancels the idea
    if (p.wick_ce_60m or p.sibi15_ce_cancel) and not lk.get("w60_done"):
        why = _wick60_cancel(ctx, p, lk, i)
        if why:
            nl = dict(lk)
            B1._neutral(nl, why)
            nl["w60_done"] = True
            hit("lock_" + why)
            return nl, True
    return None


# --------------------------------------------------------------------------------------------------------------
# the inside-BISI release, the PM Silver Bullet after a reversal
# --------------------------------------------------------------------------------------------------------------

def inside_zone(hist):
    """The daily FVG (top, bottom) that yesterday's whole range sat inside (the strategy._inside_daily_fvg zone), or None."""
    S = _S()
    if len(hist) < 4:
        return None
    o, h, l, c = S._daily(hist)
    k = len(h) - 1
    for z in L.fvgs(h[:k], l[:k]):
        after = c[z.i + 1:k]
        if z.kind == "bull" and len(after) and after.min() < z.bottom:
            continue
        if z.kind == "bear" and len(after) and after.max() > z.top:
            continue
        if z.bottom <= l[k] and h[k] <= z.top:
            return float(z.top), float(z.bottom)
    return None


def sloppy_release(ctx, p, sl_now: set, i: int) -> set:
    """B17-inside-daily-range-no-trade (091 ~6:20): from the first bar that trades release_pts beyond the daily FVG's high or low the inside_bisi stand-aside is lifted, and only that side may trade."""
    z = getattr(ctx, "inside_zone", None)
    if z is None or "inside_bisi" not in sl_now:
        return sl_now
    if not getattr(ctx, "inside_side", 0):
        top, bot = z
        rel = p.release_pts * p.es_pt
        a = ctx.start
        for j in range(a, i + 1):
            u, d_ = ctx.h[j] > top + rel, ctx.l[j] < bot - rel
            if u and d_:
                u, d_ = ctx.c[j] >= (top + bot) / 2, ctx.c[j] < (top + bot) / 2
            if u or d_:
                ctx.inside_side = 1 if u else -1
                hit("inside_release")
                break
    if getattr(ctx, "inside_side", 0):
        return sl_now - {"inside_bisi"}
    return sl_now


def extras_unblocked(ctx, p, session: str, day_reason) -> bool:
    """B3-reversal-after-target: the AM winner ended the day (no_trade_after_win) - the PM family may still trade once an AM lock was reversed after its target."""
    if not p.allow_reversal_after_target or day_reason != "win" or session not in ("PM", "SB_PM", "LH", "PMR"):
        return False
    return any(lk.get("rev_after_target") for lk in (getattr(ctx, "lock", None) or {}).values())
