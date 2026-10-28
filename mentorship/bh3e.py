"""Caption-gap pass, package bias_htf#3/7 (digests/rulebook_gaps/bias_htf_intermarket.md items 147, 152, 154, 164, 167, 168, 172-174, 185, 186, 190, 195, 198, 200-203, 215, 216, 221, 222, 224-227 and
day_selection_news_calendar.md item 45) - ENGINE SIDE.

The bar-loop part: bias fallbacks and composers, side gates, per-order rules and tags, scalps, sizes, targets, the AM lock. The columns they read are built by `bh3.py` inside `htf.table`, the COT
states by `cot.py`, the intermarket values by `backtest.INTERMARKET` / the day maps. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a
completed hist session. Hooks (who calls them)
  bias_value_adjust bias_day.bias_value        pd_needs_iof, pause_on_hold
  want_override     bias_day.want_at           htf_bias 'week_check' / 'wd_check' composers, fall_low_bias
  side_ok           daycontext.side_ok tail    cot_gate, mo_bias_gate, profile_gate (trend), in_play_gate, bias_dh, iof_sponsor_gate (skip), chop_lean
  order_ok          daycontext.order_ok tail   iof_premium_wait, profile retrace, in_play room, stack_min, tags (cot, notes_dxy, stack, hallmarks, wpr_d, bond_lt, mw, q_dir, bias_dh, wk_struct ...)
  scalp_now         daycontext.scalp_now tail  tandem_scalp, swing_gate_runners, profile consol, chop_target_baseline
  size_mult         bias_day.size_mult         wk_struct_weight
  targets_post      strategy._targets          chop_target_baseline
  lock_post         strategy.mark_levels       ny_continue_london, the q_obj_dir fallback
  counter_kind      strategy.run_day           counter_range_extreme (finish_order: kind 'ctr')
  dcandle_rows      strategy._ts_arrays0       mwd_levels_entries
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np

from . import bh1e as B1
from . import bh2 as BH2
from . import bh2e as B2
from . import bh3 as BH3
from . import cot as COT

HITS = BH2.HITS                           # one counter for the table side and the engine side (the coverage test reads it)
sw = BH2.sw
_n, _f, _row = B1._n, B1._f, B1._row


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def _BD():
    return B1._BD()


def _im(ctx) -> dict:
    return getattr(ctx, "intermarket", None) or {}


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_bh3e", {})


def on(p) -> bool:
    """Any engine-side bias_htf#3/7 switch is on (the hooks return at once otherwise)."""
    return bool(p.cot_two_states or p.cot_gate != "off" or p.tandem_scalp or p.notes_dxy_tag or p.stack_tag or p.stack_min or p.swing_gate_runners or p.bond_lt_tag or p.wpr_daily_tag
                or p.hallmarks_tag or p.profile_gate or p.mw_bookkeeping or p.in_play_gate or p.bias_dh != "off" or p.iof_premium_wait or p.mo_bias_gate or p.q_dir_tag or p.wk_struct_weight
                or p.iof_sponsor_gate != "off" or p.chop_lean or p.chop_target_baseline or p.ny_continue_london or p.counter_range_extreme or p.mwd_levels_entries
                or p.htf_bias in ("week_check", "wd_check"))


def want_on(p) -> bool:
    return bool(p.htf_bias in ("week_check", "wd_check") or p.fall_low_bias)


def bias_on(p) -> bool:
    return bool(p.pd_needs_iof or p.pause_on_hold)


def targets_on(p) -> bool:
    return bool(p.chop_target_baseline)


def lock_on(p) -> bool:
    return bool(p.ny_continue_london or (p.q_obj_lean and p.q_dir_tag))


# --------------------------------------------------------------------------------------------------------------
# readings shared by the rules
# --------------------------------------------------------------------------------------------------------------

def cot_states(ctx, p) -> tuple:
    """(cot_program, cot_hedge) of the day from the CFTC legacy files (cot.load_dir(p.cot_market)), (0, 0) without data."""
    c = _c(ctx)
    if "cot" not in c:
        tbl = COT.load_dir(p.cot_market)
        c["cot"] = COT.states(tbl, ctx.day) if tbl is not None else (0, 0)
    return c["cot"]


def _hist_closes(ctx, n: int):
    hist = getattr(ctx, "hist", None) or []
    if len(hist) < n:
        return None
    return np.array([float(x.close.iloc[-1]) for x in hist[-n:]])


def own_trend_ratio(ctx, n: int = 20):
    """The instrument's own trend ratio (|regression slope| / mean |daily change| of the last n closes, completed sessions), None without history."""
    cl = _hist_closes(ctx, n + 1)
    if cl is None:
        return None
    mad = float(np.abs(np.diff(cl)).mean())
    return abs(BH3._slope(cl[-n:])) / mad if mad > 0 else None


def trend_ok(ctx, p):
    """X3-swing-two-group-trending-gate (cc06_007 ~9:14; cc06_008 ~5:31): True when at least one of {10Y yield, dollar} trends (the INTERMARKET trend ratios tr_tnx / tr_dxy above trend_slope_min) AND the
    instrument itself trends (the stocks / commodities group: commodities are not loaded, the instrument stands in); None when the data to tell is missing."""
    c = _c(ctx)
    if "trend_ok" not in c:
        im = _im(ctx)
        g1 = [im[k] for k in ("tr_tnx", "tr_dxy") if im.get(k) is not None and im[k] == im[k]]
        own = own_trend_ratio(ctx)
        if not g1 or own is None:
            c["trend_ok"] = None
        else:
            c["trend_ok"] = bool(any(x > p.trend_slope_min for x in g1) and own > p.trend_slope_min)
    return c["trend_ok"]


def rates_support(ctx, sign: int):
    """The 10Y yield's side supports `sign` (falling yields support longs): the 60-session slope side (tnx_slow) else the 20-day mean side (tnx); None without data."""
    im = _im(ctx)
    t = int(im.get("tnx_slow", 0) or 0) or int(im.get("tnx", 0) or 0)
    return None if not t else bool(t == -sign)


def dollar_support(ctx, sign: int):
    dx = int(_im(ctx).get("dxy", 0) or 0)
    return None if not dx else bool(dx == -sign)


def window_dir(day) -> int:
    """The primary seasonal window's direction (item 60: calendar.season_window), 0 outside every window."""
    from . import calendar as CAL
    w = CAL.season_window(day)
    return int(w[1]) if w else 0


def iof_4h(ctx, i: int) -> int:
    """item 43 iof_state on the complete 4h bars of the frame at closed bar i."""
    return B1.iof_dir(ctx, 240, i)


def _inst_trend(ctx) -> int:
    hist = getattr(ctx, "hist", None) or []
    if len(hist) >= 21:
        cl = [float(x.close.iloc[-1]) for x in hist[-21:]]
        return int(np.sign(cl[-1] - cl[0]))
    return int(_im(ctx).get("spx20", 0) or 0)


def harmony(ctx, p) -> int:
    """item 139 `im_harmony`: the instrument's 20-session trend when it is in harmony with the dollar (trend == -dxy; commodities when loaded), else 0 (decoupled or unknown)."""
    d_ = B2.decoupled(ctx, p)
    return _inst_trend(ctx) if d_ is False else 0


# --------------------------------------------------------------------------------------------------------------
# the bias reading (bias_day.bias_value / want_at)
# --------------------------------------------------------------------------------------------------------------

def bias_value_adjust(row, p, v: int) -> int:
    """pd_needs_iof (A21-discount-not-buy-signal): a P/D-sourced bias counts only when the daily iof agrees. pause_on_hold (B9-ltf-arrays-break-in-succession): the session after an opposing array held is 0."""
    if p.pd_needs_iof and v:
        src_pd = (p.htf_bias in ("pd", "pd20", "draw_pd")
                  or (p.htf_bias == "combo" and _n(row, "react") == 0)
                  or (p.htf_bias == "combo2" and _n(row, "react") == 0 and _n(row, "iof") == 0))
        if src_pd:
            sw("pd_needs_iof")
            if _n(row, "iof") != v:
                hit("pd_needs_iof_zero")
                v = 0
    if p.pause_on_hold and row is not None and "held_pause" in row:
        sw("pause_on_hold")
        if _n(row, "held_pause"):
            hit("pause_on_hold")
            v = 0
    return v


def compose_week(ctx, p, row) -> int:
    """WB-weekly-checklist-order (cc12_002 ~3:17): the first non-zero of, in ICT's order, (1) relative strength - the daily index SMT as the proxy, (2) the COT hedging state when the data is loaded,
    (3) sentiment (no data: skipped), (4) the market profile - 'consol' stops the cascade with 0, (5) the intermarket harmony (item 139), (6) the weekly iof, (7) the weekly draw (table: wk_chk_tail)."""
    if row is None:
        return 0
    im = _im(ctx)
    d_ = int(im.get("dsmt", 0) or 0)
    if d_:
        sw("week_check")
        return d_
    h_ = cot_states(ctx, p)[1]
    if h_:
        return h_
    if _n(row, "wk_consol"):
        sw("week_check")
        return 0
    hm = harmony(ctx, p)
    if hm:
        return hm
    return _n(row, "wk_chk_tail")


def compose_day(ctx, p, row) -> int:
    """B5-daily-checklist-fallback (cc12_003 ~13:20): the first non-zero of the daily iof, the daily SMT, the flip state (d_breaker / B8), the table draw (COT and OI are skipped until loaded; the expected weekly
    profile is context only)."""
    if row is None:
        return 0
    v = _n(row, "d_head")
    if v:
        return v
    v = int(_im(ctx).get("dsmt", 0) or 0)
    if v:
        return v
    return _n(row, "d_tail")


def checklist_want(ctx, p, row):
    """(want, daily_unconfirmed) of htf_bias 'week_check' (the weekly composer) and 'wd_check' (the weekly composer with the daily fallback)."""
    wk = compose_week(ctx, p, row)
    if p.htf_bias == "week_check":
        return wk, False
    d_ = compose_day(ctx, p, row)
    sw("wd_check")
    if wk == 0:
        return d_, False                                           # the weekly bias is unclear or neutral: the daily alone (never less than the daily)
    if d_ in (0, wk):
        return wk, d_ == 0
    return 0, False                                                # the daily contradicts the weekly: no bias


def want_override(ctx, p, session: str, i: int, v: int) -> int:
    """bias_day.want_at tail: the checklist composers replace the reading; fall_low_bias fills a neutral one."""
    if p.htf_bias in ("week_check", "wd_check"):
        row = _row(ctx, session, i)
        w_, unc = checklist_want(ctx, p, row)
        c = _c(ctx)
        c["daily_unconfirmed"] = bool(unc)
        if w_:
            hit("want_" + p.htf_bias)
        return w_
    if v == 0 and p.fall_low_bias:
        fl = int(_im(ctx).get("fall_low", 0) or 0)
        if fl:
            sw("fall_low_bias")
            hit("want_fall_low")
            return fl
    return v


# --------------------------------------------------------------------------------------------------------------
# the monthly bias alignment (item 221)
# --------------------------------------------------------------------------------------------------------------

def mo_aligned(ctx, p, row, mb: int) -> bool:
    """MB-monthly-bias-routine: the season window (item 60), the quarterly objective's side (item 83: q_obj, else q_obj_dir of item 222), the rates tag and the SMT / structure (dsmt, else the last daily
    structure break) ALL equal the monthly bias `mb`."""
    if window_dir(ctx.day) != mb:
        return False
    px = _f(row, "px")
    q = _f(row, "q_obj")
    if q != q:
        q = _f(row, "q_obj_dir")
    if q != q or px != px or int(np.sign(q - px)) != mb:
        return False
    if rates_support(ctx, mb) is not True:
        return False
    im = _im(ctx)
    return bool(int(im.get("dsmt", 0) or 0) == mb or _n(row, "last_break") == mb)


# --------------------------------------------------------------------------------------------------------------
# chop days (item 45)
# --------------------------------------------------------------------------------------------------------------

def chop_day(ctx) -> bool:
    """B17-chop-revert-middle (031 ~19:39): the day is a range / chop day - the B17.4 range-market reading (dplan drr_ng) or a sloppy chop test hit in the session."""
    P = getattr(ctx, "dplan", None)
    if P is not None and P.info.get("drr_ng"):
        return True
    return bool(getattr(ctx, "cur_sloppy", ""))


def chop_baseline(ctx, i: int):
    """The baseline of a chop day: the midpoint of the range since 08:30 through the closed bar i, (max(high) + min(low)) / 2; None before 08:30 / without bars."""
    j0 = _S()._idx_at(ctx, 510)
    if j0 > i or j0 >= len(ctx.t):
        return None
    hi, lo = float(ctx.h[j0:i + 1].max()), float(ctx.l[j0:i + 1].min())
    return (hi + lo) / 2


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#3/7 reason, else None."""
    if not on(p) or i is None:
        return None
    row = _row(ctx, session, i)
    io = _n(row, "iof") if row is not None else 0
    if p.cot_gate == "hedge_iof":
        prog, hedge = cot_states(ctx, p)
        if prog or hedge:
            sw("cot_gate")
            if not (hedge == sign and io == sign):
                return "x_bh3_cot_gate"
    if row is not None:
        if p.mo_bias_gate:
            mb = _n(row, "mo_bias")
            if mb:
                sw("mo_bias_gate")
                if sign == -mb and mo_aligned(ctx, p, row, mb):
                    hit("mo_bias_block")
                    return "x_bh3_mo_bias"
        if p.profile_gate and row.get("profile"):
            sw("profile_gate")
            if row.get("profile") == "trend" and _n(row, "profile_dir") == -sign:
                return "x_bh3_profile_trend"
        if p.in_play_gate:
            sw("in_play_gate")
            if _n(row, "in_play") != sign:
                return "x_bh3_in_play"
        if p.iof_sponsor_gate == "skip":
            wb = compose_week(ctx, p, row) or _n(row, "flip")
            if wb:
                sw("iof_sponsor_gate")
                if io != wb:
                    return "x_bh3_iof_sponsor"
    if p.bias_dh in ("both", "either"):
        st = dh_state(ctx, row, sign, i)
        sw("bias_dh")
        if (p.bias_dh == "both" and st != "both") or (p.bias_dh == "either" and st not in ("both", "daily_only", "4h_only")):
            return "x_bh3_bias_dh"
    if p.chop_lean and chop_day(ctx):
        base = chop_baseline(ctx, i)
        if base is not None:
            sw("chop_lean")
            px = float(ctx.c[i])
            if px != base and sign != (1 if px > base else -1):
                return "x_bh3_chop_lean"
    return None


def dh_state(ctx, row, sign: int, i: int) -> str:
    """B5-daily-and-4h-bias: 'both' (the daily iof and the 4h iof agree with the side), 'daily_only' / '4h_only' (one agrees, the other is flat), 'conflict' (one agrees, the other opposes), 'none'."""
    d_ = _n(row, "iof") if row is not None else 0
    h_ = iof_4h(ctx, i)
    ad, ah = d_ == sign, h_ == sign
    opp = d_ == -sign or h_ == -sign
    if ad and ah:
        return "both"
    if (ad or ah) and opp:
        return "conflict"
    if ad:
        return "daily_only"
    if ah:
        return "4h_only"
    return "none"


# --------------------------------------------------------------------------------------------------------------
# scalps and sizes
# --------------------------------------------------------------------------------------------------------------

def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """The bias_htf#3/7 reason an order of `session` is a scalp (one exit, no adds), else ''."""
    if not on(p) or i is None:
        return ""
    if p.tandem_scalp and _im(ctx).get("notes_dxy") == "tandem":
        sw("tandem_scalp")
        return "bh3_tandem"
    if p.swing_gate_runners:
        t_ = trend_ok(ctx, p)
        if t_ is not None:
            sw("swing_gate_runners")
            if t_ is False:
                return "bh3_notrend"
    if p.profile_gate:
        row = _row(ctx, session, i)
        if row is not None and row.get("profile") == "consol":
            sw("profile_gate")
            return "bh3_profile_consol"
    if p.chop_target_baseline and sign and chop_day(ctx):
        base = chop_baseline(ctx, i)
        if base is not None and (base < float(ctx.c[i])) == (sign < 0) and base != float(ctx.c[i]):
            sw("chop_target_baseline")
            return "bh3_chop_baseline"
    return ""


def size_mult(ctx, sd, i: int, p, lvt: list, session: str = "") -> float:
    """wk_struct_weight (B10-weekly-structure-control): half risk when the order does not agree with both the controlling weekly structure and the monthly bias."""
    if not p.wk_struct_weight:
        return 1.0
    session = session or getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    row = _row(ctx, session, i)
    if row is None or "wk_control" not in row:
        return 1.0
    sw("wk_struct_weight")
    if _n(row, "wk_control") == sd.sign == _n(row, "mo_bias"):
        return 1.0
    lvt.append("size_wk_struct")
    return 0.5


# --------------------------------------------------------------------------------------------------------------
# per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

def stack_count(ctx, p, sign: int, row, i: int) -> int:
    """X3-full-confluence-stack (cc05_011 ~30:51): the number of agreeing factors - the seasonal window (item 60), the flip state, kill-zone timing (the AM / PM entry windows), the rates tag (falling
    yields for a long) and the dollar (its inverse)."""
    n = 0
    n += window_dir(ctx.day) == sign
    n += row is not None and _n(row, "flip") == sign
    t = int(ctx.t[i])
    n += bool(p.am[0] <= t < p.am[1] or p.pm[0] <= t < p.pm[1])
    n += rates_support(ctx, sign) is True
    n += dollar_support(ctx, sign) is True
    return int(n)


def hallmark_count(ctx, p, sign: int, row, i: int) -> int:
    """X3-swing-checklist-pipeline (cc06_002 ~0:45): the count of {trend_ok, the daily iof, rates, the seasonal window, an opposing array (a table draw on the order's side)} in agreement; the COT hedging state (item 147) joins it when the CFTC files are loaded."""
    n = 0
    n += trend_ok(ctx, p) is True
    n += row is not None and _n(row, "iof") == sign
    n += rates_support(ctx, sign) is True
    n += window_dir(ctx.day) == sign
    if row is not None:
        d_ = _f(row, "draw_up" if sign > 0 else "draw_dn")
        n += d_ == d_
    prog, hedge = cot_states(ctx, p)
    if prog or hedge:                                          # COT joins the count once its data is loaded (item 148: cot.py); without the files the count is the five computable hallmarks
        n += hedge == sign
    return int(n)


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#3/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p):
        return None
    tags: list = []
    row = _row(ctx, session, i)
    sign = sd.sign
    entry_raw = sd.x(o["entry"])
    im = _im(ctx)
    if p.iof_premium_wait and row is not None and _n(row, "iof") == sign and "px" in row:
        lo, hi = _f(row, "pd20_lo"), _f(row, "pd20_hi")
        if lo != lo or hi != hi:
            lo, hi = _range20(ctx, p)
        px = _f(row, "px")
        if lo == lo and hi > lo and px == px:
            pos = (px - lo) / (hi - lo) if sign > 0 else (hi - px) / (hi - lo)
            sw("iof_premium_wait")
            if pos > 0.75:
                if not sweep_in_htf_array(ctx, sd, o, i, p):
                    return "x_iof_premium_wait"
                tags.append("iof_premium_wait_ok")
    if p.profile_gate and row is not None and row.get("profile"):
        sw("profile_gate")
        tags.append("profile_" + str(row.get("profile")))
        if row.get("profile") == "retrace" and _n(row, "profile_dir") == sign:
            zs = row.get("wm_zones") or ()
            if not any(d_ == sign and b <= entry_raw <= t for b, t, d_ in zs):
                return "x_bh3_profile_retrace"
            tags.append("profile_in_array")
    if p.in_play_gate and row is not None:
        room = array_room(ctx, sd, i, entry_raw)
        sw("in_play_gate")
        if room is not None and room < p.in_play_room_pts * p.es_pt - 1e-9:
            return "x_bh3_in_play_room"
        tags.append("in_play")
    if p.stack_tag or p.stack_min:
        n = stack_count(ctx, p, sign, row, i)
        if p.stack_min:
            sw("stack_min")
        if p.stack_min and n < p.stack_min:
            return "x_bh3_stack"
        sw("stack_tag")
        tags.append(f"stack_{n}")
    if p.hallmarks_tag:
        sw("hallmarks_tag")
        tags.append(f"hallmarks_{hallmark_count(ctx, p, sign, row, i)}")
    if p.cot_two_states or p.cot_gate != "off":
        prog, hedge = cot_states(ctx, p)
        if prog or hedge:
            sw("cot_two_states")
            tags += [f"cot_program_{prog:+d}", f"cot_hedge_{hedge:+d}"]
    if (p.notes_dxy_tag or p.tandem_scalp) and im.get("notes_dxy"):
        sw("notes_dxy_tag")
        tags.append("notes_" + str(im["notes_dxy"]))
    if p.bond_lt_tag and im.get("bond_lt"):
        sw("bond_lt_tag")
        tags.append(f"bond_lt_{int(im['bond_lt']):+d}")
    if p.wpr_daily_tag and row is not None and "wpr_d" in row:
        sw("wpr_daily_tag")
        v = _n(row, "wpr_d")
        if v:
            tags.append(f"wprd_{v:+d}")
    if p.mw_bookkeeping and row is not None and "mo_pd" in row:
        sw("mw_bookkeeping")
        for k_, nm in (("mo_pd", "mo_pd"), ("wk_pd", "wk_pd")):
            v = _f(row, k_)
            if v == v:
                tags.append(f"{nm}_{v:.2f}")
        tags.append(f"wk_expand_{_n(row, 'wk_expand')}")
    if p.q_dir_tag and row is not None and "q_dir" in row:
        sw("q_dir_tag")
        v = _n(row, "q_dir")
        if v:
            tags.append("q_dir_agree" if v == sign else "q_dir_oppose")
    if p.bias_dh != "off":
        sw("bias_dh")
        tags.append("bias_dh_" + dh_state(ctx, row, sign, i))
    if p.iof_sponsor_gate != "off" and row is not None:
        wb = compose_week(ctx, p, row) or _n(row, "flip")
        if wb:
            sw("iof_sponsor_gate")
            tags.append("iof_sponsor" if _n(row, "iof") == wb else "iof_no_sponsor")
    if p.wk_struct_weight and row is not None and "wk_control" in row:
        sw("wk_struct_weight")
        tags.append("wk_struct_agree" if _n(row, "wk_control") == sign == _n(row, "mo_bias") else "wk_struct_disagree")
    if p.mo_bias_gate and row is not None and _n(row, "mo_bias"):
        tags.append("mo_aligned" if mo_aligned(ctx, p, row, _n(row, "mo_bias")) else "mo_unaligned")
    if p.htf_bias == "wd_check" and _c(ctx).get("daily_unconfirmed"):
        tags.append("daily_unconfirmed")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


def _range20(ctx, p) -> tuple:
    """The pd_day_range-session range of the completed history (bodies when pd_body_multiday): (low, high) or (nan, nan)."""
    hist = getattr(ctx, "hist", None) or []
    n = int(p.pd_day_range)
    if len(hist) < n:
        return float("nan"), float("nan")
    seg = hist[-n:]
    if p.pd_body_multiday:
        hi = max(max(float(x.open.iloc[0]), float(x.close.iloc[-1])) for x in seg)
        lo = min(min(float(x.open.iloc[0]), float(x.close.iloc[-1])) for x in seg)
    else:
        hi, lo = max(float(x.high.max()) for x in seg), min(float(x.low.min()) for x in seg)
    return lo, hi


def sweep_in_htf_array(ctx, sd, o: dict, i: int, p) -> bool:
    """The order's sweep extreme (the low of a long's sweep) sits inside a daily / 4h array of the order's side (conf.at; without the confluence table the session's HTF zones)."""
    S = _S()
    ext = sd.x(o.get("ext", o["entry"]))
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        import pandas as pd
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        tfs = cf.at(now, ext, sd.sign)
        return bool("D" in tfs or "4h" in tfs)
    return bool(S._htf_tag(ctx, sd, i, o.get("ext", o["entry"]), p.eq_tol_pts * p.es_pt))


def array_room(ctx, sd, i: int, entry_raw: float):
    """The distance from the entry to the nearest opposing daily / 4h array (its near edge, real price); None when there is none (or no confluence table)."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    import pandas as pd
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    r = cf.opposing(now, entry_raw, sd.sign, ("D", "4h"), (0,))
    return abs(r[0][0] - entry_raw) if r else None


# --------------------------------------------------------------------------------------------------------------
# targets
# --------------------------------------------------------------------------------------------------------------

def targets_post(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """chop_target_baseline (B17-chop-revert-middle): on a chop day an order against the lean (the baseline lies in its direction) gets the baseline as a target rung."""
    if not p.chop_target_baseline or not chop_day(ctx):
        return lv
    base = chop_baseline(ctx, i)
    if base is None:
        return lv
    x = sd.x(base)
    if x > above + 1e-9 and (not lv or x < lv[0][0]):
        sw("chop_target_baseline")
        hit("chop_baseline_rung")
        return [(x, "pool")] + list(lv)
    return lv


# --------------------------------------------------------------------------------------------------------------
# the AM lock (item 200) and the quarterly direction fallback (item 222)
# --------------------------------------------------------------------------------------------------------------

def _touched_since_midnight(ctx, p, kl: int, sign: int) -> bool:
    """A daily / 4h array of the `sign` side (bull for +1) was touched by a bar of today before the lock bar kl."""
    cf = getattr(ctx, "conf", None)
    a = ctx.start
    if cf is None or kl <= a:
        return False
    import pandas as pd
    now = ctx.idx[kl - 1] + pd.Timedelta(minutes=ctx.tf)
    zs = cf.valid(now, sign, ("D", "4h"), (0, 1, 3))
    lo, hi = float(ctx.l[a:kl].min()), float(ctx.h[a:kl].max())
    return any(lo <= top and hi >= bot for top, bot, *_ in zs)


def lock_post(ctx, p, row, t_lock: int, session: str, kl: int, px: float, lock: dict) -> dict:
    """mark_levels tail (after bh2e.lock_post): ny_continue_london and the q_obj_dir fallback of q_obj_lean."""
    if not on(p):
        return lock
    mn = p.draw_lock_min_pts * p.es_pt
    if p.ny_continue_london and session == "AM" and row is not None and kl > ctx.start:
        io = _n(row, "iof")
        a = ctx.start
        adr = _S().adr5(getattr(ctx, "hist", [])[-5:])
        if io and adr:
            sw("ny_continue_london")
            hod, lod = float(ctx.h[a:kl].max()), float(ctx.l[a:kl].min())
            if io < 0:
                j = a + int(np.argmax(ctx.h[a:kl]))
                tgt = hod - adr
                ok = 120 <= ctx.t[j] < 300 and lod > tgt and px - tgt >= mn and not _touched_since_midnight(ctx, p, kl, 1)          # the day high (so far) was set in London; the ADR5 low not yet reached; no bull array touched
                side = -1
            else:
                j = a + int(np.argmin(ctx.l[a:kl]))
                tgt = lod + adr
                ok = 120 <= ctx.t[j] < 300 and hod < tgt and tgt - px >= mn and not _touched_since_midnight(ctx, p, kl, -1)
                side = 1
            if ok:
                cur_t = lock.get("target")
                keep = lock.get("side") == side and cur_t is not None and ((cur_t < tgt) if side < 0 else (cur_t > tgt))     # an existing farther target of the same side stays
                if not keep:
                    lock.update(side=side, target=float(tgt), kind="array", name="adr5")
                lock.setdefault("bh3", []).append("ny_continue_london")
                hit("lock_ny_continue_london")
    if p.q_obj_lean and p.q_dir_tag and row is not None and lock.get("side") == 0:
        q = _f(row, "q_obj")
        qd = _f(row, "q_obj_dir")
        if q != q and qd == qd and abs(qd - px) >= mn:
            lock.update(side=1 if qd > px else -1, target=qd, kind="array", name="q_obj_dir")
            lock.setdefault("bh3", []).append("q_obj_dir")
            sw("q_dir_tag")
            hit("lock_q_obj_dir")
    return lock


# --------------------------------------------------------------------------------------------------------------
# the counter-trend exception at a range extreme (item 202)
# --------------------------------------------------------------------------------------------------------------

def _pivot_swept(ctx, sd, i: int) -> bool:
    """Today's bars through the closed bar i have taken the latest known daily pivot low (high for a short) of the completed history (a sweep of an old low)."""
    hist = getattr(ctx, "hist", None) or []
    if len(hist) < 4:
        return False
    h = np.array([float(x.high.max()) for x in hist])
    l = np.array([float(x.low.min()) for x in hist])
    from . import levels as L
    ph, pl = L.pivots(h, l, 1)
    a = ctx.start
    if sd.sign > 0:
        piv = [q.price for q in pl if q.known <= len(hist) - 1]
        return bool(piv and float(ctx.l[a:i + 1].min()) < piv[-1])
    piv = [q.price for q in ph if q.known <= len(hist) - 1]
    return bool(piv and float(ctx.h[a:i + 1].max()) > piv[-1])


def counter_kind(ctx, sd, i: int, p, w_: int, session: str) -> str:
    """B3-countertrend-from-range-extreme (cc09_008 ~16:57): 'ctr' when this side is against the bias `w_` and price sits in the bottom (top, for a short) 25 % of the pd_day_range range after the sweep took
    a daily pivot low (high); finish_order then gives it a single target (the nearest opposing array inside the range), no adds, half risk."""
    if not p.counter_range_extreme or not w_ or w_ == sd.sign:
        return ""
    lo, hi = _range20(ctx, p)
    if lo != lo or hi <= lo:
        return ""
    sw("counter_range_extreme")
    px = float(ctx.c[i])
    pos = (px - lo) / (hi - lo) if sd.sign > 0 else (hi - px) / (hi - lo)
    if pos <= 0.25 and _pivot_swept(ctx, sd, i):
        return "ctr"
    return ""


def ctr_target(ctx, sd, i: int, p):
    """The single target of a 'ctr' order (side space): the near edge of the nearest opposing daily / 4h array that lies inside the range, else None (no trade)."""
    cf = getattr(ctx, "conf", None)
    lo, hi = _range20(ctx, p)
    if cf is None or lo != lo:
        return None
    import pandas as pd
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    px = float(ctx.c[i])
    r = cf.opposing(now, px, sd.sign, ("D", "4h"), (0,))
    for near, _ce, _far, _tf, _src in r:
        if lo <= near <= hi:
            return float(sd.x(near))
    return None


# --------------------------------------------------------------------------------------------------------------
# mwd_levels as entry arrays (item 180)
# --------------------------------------------------------------------------------------------------------------

def dcandle_rows(ctx, sd, i: int, p=None) -> list:
    """The case-B daily down-close candles' open / high (mwd_levels of the table row) as zero-height arrays of the order's side (side space top, bottom, known): levels, not zones. Only the levels below the
    price for a long (above for a short) are entries."""
    row = _row(ctx, "AM" if ctx.t[i] < 810 else "PM", i)
    if row is None or "mwd_levels" not in row or _n(row, "mwd") != sd.sign:
        return []
    out = []
    px = float(sd.x(ctx.c[i]))
    kn = ctx.idx[ctx.start]
    for v in row.get("mwd_levels") or ():
        x = float(sd.x(v))
        if x <= px:
            out.append((x, x, kn))
    if out:
        sw("mwd_levels_entries")
    return out


# --------------------------------------------------------------------------------------------------------------
# the seasonal qualifiers (dwc1.season_info)
# --------------------------------------------------------------------------------------------------------------

def season_qualified(ctx, wdir: int) -> bool:
    """X3-seasonal-quarterly-qualifier (cc05_007 ~8:04, ~8:22, ~9:04): a window is qualified by any ONE of the three qualifiers; only the index-relevant proxies exist - the daily index SMT (item 119 dsmt) in the
    window's direction, or the notes / dollar regime 'opposed' (item 152: notes moving against the dollar = the trending regime) [our interpretation: 'opposed' qualifies the window whatever its direction]."""
    im = _im(ctx)
    sw("season_qualified")
    return bool(wdir and (int(im.get("dsmt", 0) or 0) == wdir or im.get("notes_dxy") == "opposed"))


def window_poised(ctx, wdir: int):
    """B23-market-poised-first (cc10_016 ~1:51; cc11_003 ~4:37): True / False whether the market is poised in the window's direction (backtest.poised_map: both indices' 20-session slopes agree, or the daily SMT
    with the price on the discount side of the 60-session EQ); None when the map is missing (no partner frame)."""
    im = _im(ctx)
    if "poised" not in im:
        return None
    sw("season_poised")
    return bool(int(im.get("poised", 0) or 0) == wdir)
