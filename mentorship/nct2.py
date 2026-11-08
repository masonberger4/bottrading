"""Caption-gap pass, package news_calendar_times#1/1 (digests/rulebook_gaps/*.md, the 37 specs of the chunk; build_log.md).

Calendar rules (release counts, two-driver days, CPI / FOMC-minutes / post-FOMC day rules), per-bar gates (the AM search box, macro failure of any macro, the NFP both-pools sequence,
the lunch raid, the lunch-length-by-AM-speed, the PM array time, the chop wait ...), side filters (the pre-news coil, the news trend side, the FOMC move end ...), order tags and the study
helpers (news sequence, FOMC stage label, kill-zone release extreme). Everything reads only bars that have closed (index <= the caller's bar i); every value fixed ahead of time
(a release minute, a pre-release range) is computed from bars that ended before the minute it is used at; results derived from the whole-day arrays are used only when the index they
name is <= the caller's bar (the same pattern as newscal.first_run). Thresholds the sources never give are marked [our interpretation]. Every rule is a Params switch.

Pieces
  calendar_block2   cpi_from / fomc_minutes_mode / multi_release "skip" / two_driver_mode "skip" / post_fomc_am "skip"      (newscal.calendar_block tail)
  day_tags2         fomc_hv / pre_fomc_only / fomc_minutes / rel0_wildcard / rel1 / rel2plus                                  (newscal.day_tags tail)
  size_mult / adds_off   multi_release "half", pre_fomc_week_light / _mult                                                    (entries.size_mult, entries.adds_blocked)
  gate2             am_search_minutes, am_trend_end, lunch_by_speed, lunch_raid_wait, macro_fail_*, nfp_both_sides / nfp_macro_only, two_driver_mode "wait2",
                    fomc_whipsaw_skip, post_fomc_am "symmetry", pm_1400_disp, pre_entry_guard, chop_wait_bars                 (run_day, after newscal.gate)
  side2             pre_news_coil, nfp_both_sides side, news_trend_side, fomc_end, pre_fomc_week_smt                           (run_day, after newscal.side_filter)
  order_tags        study tags and order filters (pm_array_from, pm_1400_disp, chop displacement, pre_entry_guard pool, macro_trend_off ...)   (newscal.post_order tail)
  special           post_news_fade, pre_open_bnb                                                                              (run_day, like sm7.special7)
  speed_adjust      lunch_by_speed: the PM start of the day                                                                   (run_day)
  after_close       pre_draw_done_am, hard_day_one_trade                                                                      (strategy._after_close)
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

import numpy as np

from mentorship.calendar import events
from . import calendar as CAL
from . import newscal as NC

HITS: Counter = Counter()


def hit(k: str) -> None:
    """Executed-path counter (the look-ahead tests assert the switches act in their window)."""
    HITS[k] += 1


def _S():
    from . import strategy as S
    return S


AM_FAM = ("AM", "PRE9", "NEWS")                    # the NY AM family (not London / PRE7 / PRE8 / lunch)
PRE_WINS = ("PRE7", "PRE8", "PRE9", "NEWS")
HIGH_IMPACT = {"cpi", "jobs", "fomc"}
MACRO_SET = {"0950": ((590, 610),), "1050": ((650, 670),), "1150": ((710, 730),),
             "1330": ((790, 820), (810, 815), (819, 840)), "1450": ((890, 910),), "1515": ((915, 945),)}
NFP_MACROS = ((590, 610), (600, 660), (650, 670))       # N1-nfp-both-sides-macro: 09:50-10:10, the 10:00-11:00 SB, 10:50-11:10
MACRO_FAIL_AM = ((590, 610), (650, 670))
MACRO_FAIL_ALL = ((590, 610), (650, 670), (710, 730), (810, 815), (890, 910), (915, 945))


def _cache(ctx) -> dict:
    return ctx.__dict__.setdefault("_nct2", {})


def _adr(ctx):
    return _S().adr5((getattr(ctx, "hist", None) or [])[-5:])


# ---------------------------------------------------------------------------------------------------
# calendar-only helpers
# ---------------------------------------------------------------------------------------------------

def two_driver(day, p=None) -> bool:
    """N5-two-driver-session (100 ~01:10:53): 08:30 and 10:00 releases in the same NY AM (FOMC 14:00 excluded; 08:30 + 14:00 does not count)."""
    rt = NC.releases(day, p) if p is not None else CAL.release_times(day)
    return 510 in rt and 600 in rt


def rel_count(day, p) -> int:
    """N5-multi-release-count (cc08_006 ~00:07:04): the releases (the set the news gate waits for: high and, with the news_* switches, medium impact) between 08:30 and 11:00."""
    return sum(1 for r in NC.releases(day, p) if 510 <= r <= 660)


def rel_tag(day, p) -> str:
    n = rel_count(day, p)
    return "rel0_wildcard" if n == 0 else ("rel1" if n == 1 else "rel2plus")


def fomc_week_before(day, t: int) -> bool:
    """N3-fomc-week-mon-wed (094 ~00:01:48): `day` lies in an FOMC week (Mon-Fri) before the Wednesday 14:00 statement (day < F, or the FOMC day itself before 14:00)."""
    mon = day - timedelta(days=day.weekday())
    for k in range(5):
        x = mon + timedelta(days=k)
        if "fomc" in events(x):
            return day < x or (day == x and t < 840)
    return False


def hard_day(day) -> bool:
    """new-premarket-difficult-days (032 ~00:06:00): an 08:30-release day that is hard to read - FOMC later today or a high-impact event (CPI / jobs / FOMC) the next trading day."""
    if _S().news(day) != "0830":
        return False
    return "fomc" in events(day) or bool(events(CAL.next_trading_day(day)) & HIGH_IMPACT)


def calendar_block2(d, session: str, p, t: int = 0):
    """The day rules of this package that need only the date (called at the end of newscal.calendar_block; None = not blocked)."""
    tags = events(d)
    am_only = session in AM_FAM
    if p.cpi_from and "cpi" in tags and t < p.cpi_from:
        return "cpi_before_from"                         # N4-cpi-day-new-traders (030 ~00:07:13)
    if p.fomc_minutes_mode != "allow" and d in CAL.FOMC_MINUTES and not CAL.fomc_info(d)["fomc"]:
        if p.fomc_minutes_mode == "block" and session == "PM" and not (p.fomc_pm_from and t >= p.fomc_pm_from):
            return "fomc_minutes_pm"                     # N3-fomc-minutes (cc10_008 ~11:18): a 14:00 driver blocks the PM like an FOMC day
        if p.fomc_minutes_mode == "pm_only" and (am_only or session in ("PRE7", "PRE8")):
            return "fomc_minutes_am"                     # (082 ~00:04:18): no AM, the PM setups are allowed
    if am_only:
        if p.multi_release == "skip" and rel_count(d, p) >= 2:
            return "multi_release_skip"                  # N5-multi-release-count
        if p.two_driver_mode == "skip" and two_driver(d, p):
            return "two_driver_skip"                     # N5-two-driver-session
        if p.post_fomc_am == "skip" and CAL.fomc_info(d)["after"]:
            return "post_fomc_am"                        # N3-post-fomc-thu-fri
    return None


def day_tags2(d, p=None) -> list:
    """Tags added to the day's news tags (newscal.day_tags): fomc_hv (an FOMC day with an 08:30 / 10:00 release too), pre_fomc_only (the day before a lone-release FOMC day),
    fomc_minutes, and the release-count tag with multi_release on."""
    out = []
    fi = CAL.fomc_info(d)
    rt = CAL.release_times(d)
    if fi["fomc"] and (510 in rt or 600 in rt):
        out.append("fomc_hv")                            # N3 (cc10_008 ~2:56): FOMC + AM high-impact news = a high-volatility day, not a consolidation day
    if fi["eve"] and CAL.fomc_info(CAL.next_trading_day(d))["only"]:
        out.append("pre_fomc_only")
    if d in CAL.FOMC_MINUTES and not fi["fomc"]:
        out.append("fomc_minutes")
    if p is not None and p.multi_release != "off":
        out.append(rel_tag(d, p))
    return out


# ---------------------------------------------------------------------------------------------------
# risk and adds
# ---------------------------------------------------------------------------------------------------

def size_mult(ctx, sd, i: int, p, session: str, lvt: list) -> float:
    """entries.size_mult tail: multi_release "half" on a rel2plus day, pre_fomc_week_light from Monday of FOMC week to Wednesday 14:00."""
    m = 1.0
    if p.multi_release == "half" and rel_count(ctx.day, p) >= 2:
        m *= 0.5
        lvt.append("size_rel2plus")
        hit("multi_half")
    if p.pre_fomc_week_light and fomc_week_before(ctx.day, int(ctx.t[i])):
        m *= p.pre_fomc_week_mult
        lvt.append("size_pre_fomc_week")
        hit("fomc_week_light")
    return m


def adds_off(ctx, p, i: int) -> bool:
    """entries.adds_blocked tail: no pyramiding in FOMC week before the statement (pre_fomc_week_light)."""
    return bool(p.pre_fomc_week_light and fomc_week_before(ctx.day, int(ctx.t[i])))


# ---------------------------------------------------------------------------------------------------
# bar-derived helpers
# ---------------------------------------------------------------------------------------------------

def am_speed(ctx, p, i: int):
    """T8-lunch-length-am-speed (cc10_012 ~00:02:56): the 09:30-11:00 range / ADR5 from the bars that ended by 11:00 - known only once the bar before 11:00 has closed (i >= that bar);
    None before that or without ADR5."""
    c = _cache(ctx)
    S = _S()
    a, b = S._idx_at(ctx, 570), S._idx_at(ctx, 660)
    if i < b - 1 or b >= len(ctx.t):
        return None
    if "speed" in c:
        return c["speed"]
    adr = _adr(ctx)
    if b - a < 1 or not adr:
        return None
    v = float(ctx.h[a:b].max() - ctx.l[a:b].min()) / adr
    c["speed"] = v
    return v


def speed_class(ctx, p, i: int) -> str:
    v = am_speed(ctx, p, i)
    if v is None:
        return ""
    return "fast" if v >= p.am_fast_k else ("slow" if v < p.am_slow_k else "mid")


def speed_adjust(ctx, p, lock_t, state: dict, t: int, i: int) -> None:
    """lunch_by_speed: once the 11:00 range is known (t >= 11:00) set the PM start of the day (state["pm0"], and the PM lock minute): fast AM -> lunch_fast_pm, lethargic -> lunch_slow_pm."""
    if not p.lunch_by_speed or "pm0" in state or t < 660:
        return
    k = speed_class(ctx, p, i)
    if not k:
        return
    state["pm0"] = {"fast": p.lunch_fast_pm, "slow": p.lunch_slow_pm}.get(k, p.pm[0])
    if lock_t and "PM" in lock_t:
        lock_t["PM"] = state["pm0"]
    hit("speed_" + k)


def trend_day_nr(ctx, i: int) -> bool:
    """T7-no-macro-trending (025 ~00:59:10) [our interpretation]: a one-sided trending day = from 10:00 on, no bar has retraced to the running 50 % of the 09:30 session's range
    (up: no low at or under it; down: no high at or over it). False before 10:00 or while the first bar after it has not closed."""
    S = _S()
    a, b = S._idx_at(ctx, 570), S._idx_at(ctx, 600)
    if b >= len(ctx.t) or i < b or b - a < 1:
        return False
    hi, lo = float(ctx.h[a:b].max()), float(ctx.l[a:b].min())
    up = dn = True
    for k in range(b, i + 1):
        eq = (hi + lo) / 2
        if ctx.l[k] <= eq:
            up = False
        if ctx.h[k] >= eq:
            dn = False
        if not (up or dn):
            return False
        hi, lo = max(hi, float(ctx.h[k])), min(lo, float(ctx.l[k]))
    return True


def macro_wins_for(p) -> list:
    """T7 macro_gate_set: the (start, end) windows the macro_gate / macro_only tests use (() = every window of newscal.MACROS_T7)."""
    if not p.macro_gate_set:
        return list(NC.MACROS_T7)
    out = []
    for k in p.macro_gate_set:
        out += list(MACRO_SET[k])
    return out


# --- pre-news coil (BH-consolidation-near-highs-before-news) --------------------------------------

def coil_block(ctx, p, day, i: int) -> int:
    """075 ~01:37:16: -1 = shorts are blocked at bar i (weekly bias up, a tight overnight range at the week high going into the 08:30 release), +1 = longs blocked (the mirror), 0 = n/a.
    Tight = the overnight range < 0.5 x ADR5 with its high within 0.25 x ADR5 of the week-to-date high [our interpretation]. The overnight range is read AS OF bar i (00:00 .. i, capped
    at 08:30), from 07:00 on; the week and ADR figures come from completed sessions."""
    S = _S()
    t = int(ctx.t[i])
    if t < 420:
        return 0
    c = _cache(ctx)
    if "coil_static" not in c:
        adr = _adr(ctx)
        hist = getattr(ctx, "hist", None) or []
        st = None
        if adr and 510 in NC.releases(day, p):
            wb = S.weekly_bias(hist, day)
            if wb:
                iso = day.isocalendar()[:2]
                wk = [g for g in hist[-5:] if g.index[0].date().isocalendar()[:2] == iso] or hist[-5:]
                st = (wb, adr, max(float(g.high.max()) for g in wk), min(float(g.low.min()) for g in wk))
        c["coil_static"] = st
    st = c["coil_static"]
    if st is None:
        return 0
    wb, adr, wk_hi, wk_lo = st
    k_end = min(i + 1, S._idx_at(ctx, 510))
    if k_end <= ctx.start:
        return 0
    on_hi, on_lo = float(ctx.h[ctx.start:k_end].max()), float(ctx.l[ctx.start:k_end].min())
    if on_hi - on_lo >= 0.5 * adr:
        return 0
    if wb > 0 and on_hi >= wk_hi - 0.25 * adr:
        return -1
    if wb < 0 and on_lo <= wk_lo + 0.25 * adr:
        return 1
    return 0


def coil_mss_k(ctx, blocked_sign: int):
    """The first bar index of the post-release shift that lifts the coil block: for blocked shorts (-1) a close under the latest confirmed post-release swing low, for blocked
    longs (+1) a close over the latest confirmed post-release swing high [our interpretation of "a bearish shift"]. Derived from the whole-day arrays; use only when <= the caller's bar."""
    c = _cache(ctx)
    key = ("coil_k", blocked_sign)
    if key in c:
        return c[key]
    S = _S()
    kR = S._idx_at(ctx, 510)
    sd = ctx.sides_map[1]
    piv = sd.pl if blocked_sign < 0 else sd.ph
    out = None
    for k in range(kR + 1, len(ctx.t)):
        qs = [q for q in piv if q.i >= kR and q.known < k]
        if not qs:
            continue
        q = max(qs, key=lambda x: x.i)
        if (blocked_sign < 0 and ctx.c[k] < q.price) or (blocked_sign > 0 and ctx.c[k] > q.price):
            out = k
            break
    c[key] = out
    return out


# --- NFP both-pools sequence (N1-nfp-both-sides-macro) -----------------------------------------

def nfp_sequence(ctx, p):
    """The post-release news range of the 08:30 jobs release: dict(first=+1 high taken first / -1 low first, both=bar where the second pool traded, allow=the side the second pool
    leaves open: long after the low run, short after the high run) from the bars after the range was made, 1 tick through each end; None while no range is made. The indexes are derived from
    the whole-day arrays: readers compare them with their own bar."""
    c = _cache(ctx)
    if "nfp_seq" in c:
        return c["nfp_seq"]
    d = getattr(ctx, "news_dr", {}).get(510)
    if not d or d.get("made") is None or d.get("hi") is None:
        return None
    made, tk = int(d["made"]), float(p.tick)
    up = np.flatnonzero(ctx.h[made + 1:] >= d["hi"] + tk - 1e-9)
    dn = np.flatnonzero(ctx.l[made + 1:] <= d["lo"] - tk + 1e-9)
    ku = made + 1 + int(up[0]) if len(up) else None
    kd = made + 1 + int(dn[0]) if len(dn) else None
    out = dict(made=made, ku=ku, kd=kd, first=0, both=None, allow=0)
    if ku is not None and (kd is None or ku <= kd):
        out["first"] = 1
    elif kd is not None:
        out["first"] = -1
    if ku is not None and kd is not None:
        out["both"] = max(ku, kd)
        out["allow"] = out["first"] if ku != kd else 0      # the pool taken second is the opposite one: first = high -> the low run then a long (+1); first = low -> a short (-1)
    c["nfp_seq"] = out
    return out


# --- news sequence study (N6-both-pools-news, N6-news-pool-mapping) -----------------------------

def news_sequence(ctx, p, R: int, i: int):
    """064 ~00:30:16: at the bar before the release R mark the nearest untaken buy-side (pre_bsl) and sell-side (pre_ssl) pool - relative-equal levels first, else the nearest swing - and the
    nearest unfilled FVG; then, through bar i, which of them traded and when. dict(bsl, ssl, fvg, k_bsl, k_ssl, k_fvg, order) with order in none / bsl_first / ssl_first / both_same_bar /
    bsl_only / ssl_only. None when the release bar has not closed or no pool exists."""
    S = _S()
    kR = S._idx_at(ctx, R)
    if kR >= len(ctx.t) or kR <= ctx.start + 2 or i < kR:
        return None
    k0 = kR - 1
    px = float(ctx.c[k0])
    sd = ctx.sides_map[1]
    tol = p.eq_tol_pts * p.es_pt
    try:
        eqh = [v for v in S._eq_levels(sd, k0, tol, False, p) if v > px]
        eql = [-v for v in S._eq_levels(sd, k0, tol, True, p) if -v < px]
    except (ValueError, IndexError):                     # (no equal-level pools could be built from these bars; a signature / data bug now raises)
        eqh, eql = [], []
    sw_h = [q.price for q in sd.ph if q.known <= k0 and q.price > px and not (ctx.h[q.i + 1:k0 + 1] >= q.price).any()]
    sw_l = [q.price for q in sd.pl if q.known <= k0 and q.price < px and not (ctx.l[q.i + 1:k0 + 1] <= q.price).any()]
    bsl = min(eqh) if eqh else (min(sw_h) if sw_h else None)
    ssl = max(eql) if eql else (max(sw_l) if sw_l else None)
    fvg = None
    for g in sd.gaps:                                    # bullish (support) FVGs, raw prices; the bearish ones come from the mirrored side
        if g.i <= k0 and not (ctx.l[g.i + 1:k0 + 1] <= g.bottom).any() and g.top < px:
            if fvg is None or px - g.top < px - fvg[0]:
                fvg = (float(g.top), float(g.bottom))
    sd2 = ctx.sides_map[-1]
    for g in sd2.gaps:
        top, bot = -float(g.bottom), -float(g.top)       # mirrored back
        if g.i <= k0 and not (ctx.h[g.i + 1:k0 + 1] >= bot).any() and bot > px:
            if fvg is None or bot - px < abs(px - fvg[0]):
                fvg = (top, bot)
    if bsl is None and ssl is None:
        return None
    kb = ks = kf = None
    for k in range(kR, i + 1):
        if kb is None and bsl is not None and ctx.h[k] >= bsl:
            kb = k
        if ks is None and ssl is not None and ctx.l[k] <= ssl:
            ks = k
        if kf is None and fvg is not None and ctx.l[k] <= fvg[0] and ctx.h[k] >= fvg[1]:
            kf = k
    if kb is not None and ks is not None:
        order = "both_same_bar" if kb == ks else ("bsl_first" if kb < ks else "ssl_first")
    elif kb is not None:
        order = "bsl_only"
    elif ks is not None:
        order = "ssl_only"
    else:
        order = "none"
    return dict(bsl=bsl, ssl=ssl, fvg=fvg, k_bsl=kb, k_ssl=ks, k_fvg=kf, order=order,
                min_bsl=None if kb is None else int(ctx.t[kb]), min_ssl=None if ks is None else int(ctx.t[ks]))


def kz_release_extreme(ctx, p, i: int, bias: int):
    """cc09_008 ~00:01:46: True when the day's low (bullish bias) / high (bearish) so far was made within 60 minutes after a kill-zone release (07:00-10:00); None without a bias."""
    if not bias:
        return None
    S = _S()
    rs = [r for r in NC.releases(ctx.day, p) if 420 <= r <= 600]
    if not rs or i <= ctx.start:
        return False
    seg = ctx.l[ctx.start:i + 1] if bias > 0 else ctx.h[ctx.start:i + 1]
    k = ctx.start + int(np.argmin(seg) if bias > 0 else np.argmax(seg))
    te = int(ctx.t[k])
    return any(r <= te < r + 60 for r in rs)


def stage_label(ctx, p, R: int, i: int):
    """N3-fomc-two-stage (021 ~00:39:02; 065B ~05:34:01) at R + 60 (FOMC 15:00; a jobs release 09:30): dict(label, d1, ext, pool, fvg, opp). leg 1 = R .. R + 25. A = the bar closed
    before R + 60 beyond the R open against leg 1; B = price touched the leg-1 FVG and then made a new leg-1 extreme; else "none". None until the bar before R + 60 has closed."""
    S = _S()
    k0, kl, kc = S._idx_at(ctx, R), S._idx_at(ctx, R + 25), S._idx_at(ctx, R + 60)
    if k0 >= len(ctx.t) or kl - 1 < k0 or kc - 1 > i or kc - 1 < kl:
        return None
    o0 = float(ctx.o[k0])
    d1 = int(np.sign(ctx.c[kl - 1] - o0))
    if d1 == 0:
        return None
    ext = float(ctx.h[k0:kl].max()) if d1 > 0 else float(ctx.l[k0:kl].min())
    rk = np.flatnonzero((ctx.t[ctx.start:] >= R - p.news_judas_ref_min) & (ctx.t[ctx.start:] < R)) + ctx.start
    pool = opp = None
    if len(rk):
        rh, rl = float(ctx.h[rk].max()), float(ctx.l[rk].min())
        pool, opp = (rh, rl) if d1 > 0 else (rl, rh)
    sd = ctx.sides_map[d1]
    fvg = None
    for g in sd.gaps:
        if k0 <= g.i < kl:
            fvg = (float(sd.x(g.top)), float(sd.x(g.bottom)))
    label = "none"
    if int(np.sign(ctx.c[kc - 1] - o0)) == -d1:
        label = "A"
    elif fvg is not None:
        touch = None
        for k in range(kl, kc):
            if (d1 > 0 and ctx.l[k] <= max(fvg)) or (d1 < 0 and ctx.h[k] >= min(fvg)):
                touch = k
                break
        if touch is not None and ((d1 > 0 and ctx.h[touch + 1:kc].max(initial=-np.inf) > ext) or (d1 < 0 and ctx.l[touch + 1:kc].min(initial=np.inf) < ext)):
            label = "B"
    return dict(label=label, d1=d1, ext=ext, pool=pool, fvg=fvg, opp=opp)


def fomc_move_dir(ctx, p, i: int) -> int:
    """N3-fomc-move-ends-1500 (cc08_002 ~00:09:56): direction of the 14:00 -> fomc_end FOMC move when it is at least fomc_end_min_pts, else 0; read once the bar ending at fomc_end has closed."""
    S = _S()
    k0, kE = S._idx_at(ctx, 840), S._idx_at(ctx, p.fomc_end)
    if kE >= len(ctx.t) or kE - 1 > i or kE - 1 < k0:
        return 0
    mv = float(ctx.c[kE - 1] - ctx.o[k0])
    return int(np.sign(mv)) if abs(mv) >= p.fomc_end_min_pts * p.es_pt else 0


def whip_flag(ctx, p, day) -> bool:
    """N3-fomc-whipsaw-skip-london (cc08_006 ~00:04:37): the previous session was an FOMC day whose 14:00-16:00 moves reached both above and below the 14:00 price by fomc_whip_frac x ADR5
    (the five sessions before the FOMC day), or whose day range exceeded 2 x ADR5. History bars only."""
    if p.fomc_whipsaw_skip == "off" or not CAL.fomc_info(day)["after"]:
        return False
    c = _cache(ctx)
    if "whip" in c:
        return c["whip"]
    hist = getattr(ctx, "hist", None) or []
    out = False
    if len(hist) >= 6:
        prev = hist[-1]
        m = prev.index.hour * 60 + prev.index.minute
        win = prev[(m >= 840) & (m < 960)]
        adr = _S().adr5(hist[-6:-1])
        if len(win) and adr:
            px = float(win.open.iloc[0])
            up, dn = float(win.high.max()) - px, px - float(win.low.min())
            out = bool(min(up, dn) >= p.fomc_whip_frac * adr or float(prev.high.max() - prev.low.min()) > 2 * adr)
    c["whip"] = out
    return out


def smt_same_side(ctx, i: int, sign: int, win: int = 12):
    """pre_fomc_week_smt: both indexes swept the same side at bar i - the last `win` bars took out the low (long) / high (short) of the `win` bars before. None without a partner."""
    pctx, psides, ppos = getattr(ctx, "pside", (None, None, None))
    if pctx is None:
        return None
    j = int(ppos.index.searchsorted(ctx.idx[i], side="right")) - 1
    if j < pctx.start + 2 * win or i < ctx.start + 2 * win:
        return False

    def swept(x, k):
        if sign > 0:
            return bool(x.l[k - win + 1:k + 1].min() < x.l[k - 2 * win + 1:k - win + 1].min())
        return bool(x.h[k - win + 1:k + 1].max() > x.h[k - 2 * win + 1:k - win + 1].max())
    return swept(ctx, i) and swept(pctx, j)


def symmetry_ok(ctx, p, i: int) -> bool:
    """N3-post-fomc-thu-fri (094 ~00:07:09) [our interpretation]: the AM after FOMC is open once both indexes broke the SAME side of the 09:30-09:45 range (and neither the other side) -
    the symmetry that returns. Blocked until then; with no partner the rule cannot be judged (open)."""
    pctx, psides, ppos = getattr(ctx, "pside", (None, None, None))
    if pctx is None:
        return True
    S = _S()
    ka, kb = S._idx_at(ctx, 570), S._idx_at(ctx, 585)
    pa, pb = S._idx_at(pctx, 570), S._idx_at(pctx, 585)
    if kb >= len(ctx.t) or i < kb:
        return False
    j = int(ppos.index.searchsorted(ctx.idx[i], side="right")) - 1
    if pb >= len(pctx.t) or j < pb or kb - ka < 1 or pb - pa < 1:
        return False

    def broke(x, a, b, k):
        return (bool(x.h[b:k + 1].max() > x.h[a:b].max()), bool(x.l[b:k + 1].min() < x.l[a:b].min()))
    u1, d1 = broke(ctx, ka, kb, i)
    u2, d2 = broke(pctx, pa, pb, j)
    return bool((u1 and u2 and not d1 and not d2) or (d1 and d2 and not u1 and not u2))


# --- lunch raid (T8-lunch-raid-target) ---------------------------------------------------------

def lunch_pools(ctx, p):
    """The lunch pool(s) L from the bars that ended by 11:50: the AM move d (09:30 open -> the last close before 11:50) is bullish -> L are lows (the profitable longs' trailed stops), bearish
    -> highs. Candidates (025 ~01:01:51; 064 ~01:46:02; 075 ~01:10:44): recent = the last confirmed swing against the move, am_low = the AM extreme made before 11:00, post_news = the first swing
    after the 08:30 release. lunch_raid selects one ("first_of" = all). Returns dict(d, pools={name: raw price}) or None."""
    if p.lunch_raid == "off":
        return None
    c = _cache(ctx)
    if ("lunch", p.lunch_raid) in c:
        return c[("lunch", p.lunch_raid)]
    S = _S()
    a, k660, k710 = S._idx_at(ctx, 570), S._idx_at(ctx, 660), S._idx_at(ctx, 710)
    if k710 >= len(ctx.t) or k710 - 1 < a:
        return None
    d = int(np.sign(ctx.c[k710 - 1] - ctx.o[a]))
    if d == 0:
        return None
    sd = ctx.sides_map[d]
    piv = [q for q in sd.pl if q.i >= a and q.known <= k710 - 1]
    pools = {}
    if piv:
        pools["recent"] = float(sd.x(piv[-1].price))
    if k660 > a:
        pools["am_low"] = float(sd.x(sd.l[a:k660].min()))
    k600, k690 = S._idx_at(ctx, 600), S._idx_at(ctx, 690)
    af = [q for q in sd.pl if k600 <= q.i and q.known <= min(k690, k710) - 1]
    if af:                                       # LUNCH-TARGET B: looking left from 11:30, the first swing (against the move) formed after 10:00
        pools["after_1000"] = float(sd.x(af[-1].price))
    k590, k610 = S._idx_at(ctx, 590), S._idx_at(ctx, 610)
    if k610 > k590 >= a:                         # LUNCH-TARGET C: the extreme made in the 09:50-10:10 macro
        pools["macro_0950"] = float(sd.x(sd.l[k590:k610].min()))
    if 510 in NC.releases(ctx.day, p):
        kR = S._idx_at(ctx, 510)
        pr = [q for q in sd.pl if q.i >= kR and q.known <= k710 - 1]
        if pr:
            pools["post_news"] = float(sd.x(pr[0].price))
    if p.lunch_raid != "first_of":
        pools = {k: v for k, v in pools.items() if k == p.lunch_raid}
    out = dict(d=d, pools=pools)
    c[("lunch", p.lunch_raid)] = out
    return out


def lunch_raided(ctx, p, i: int) -> bool:
    """True when a lunch pool traded one tick through between 11:50 and bar i (bullish AM: a low; bearish: a high)."""
    lp = lunch_pools(ctx, p)
    if not lp or not lp["pools"]:
        return True                                      # nothing to wait for
    S = _S()
    k710 = S._idx_at(ctx, 710)
    if i < k710:
        return False
    tk = float(p.tick)
    for px in lp["pools"].values():
        if (lp["d"] > 0 and ctx.l[k710:i + 1].min() <= px - tk + 1e-9) or (lp["d"] < 0 and ctx.h[k710:i + 1].max() >= px + tk - 1e-9):
            return True
    return False


def guard_stop(pos, new: float) -> float:
    """lunch_trail_guard (manage.raise_stop): a trailed stop of an AM trade may not sit within eq_tol beyond a lunch pool (side space): it is moved to just beyond the zone."""
    for lp, tol in pos.get("lunch_guard") or ():
        if lp - tol - 1e-9 <= new <= lp + 1e-9:
            hit("trail_guard")
            return lp - tol - 1e-6
    return new


def set_guard(ctx, p, pos, tr, sd, i: int) -> None:
    """Attach the lunch pools (side space) to an open AM-family position from 11:50 (when the pool lies behind its direction)."""
    lp = lunch_pools(ctx, p)
    if not lp or lp["d"] != sd.sign or tr.session in ("PM", "LUNCH") or pos.get("lunch_guard"):
        return
    pos["lunch_guard"] = [(sd.sign * v, p.eq_tol_pts * p.es_pt) for v in lp["pools"].values()]


# ---------------------------------------------------------------------------------------------------
# per-bar gates (run_day, after newscal.gate)
# ---------------------------------------------------------------------------------------------------

def _am_filled(trades, pos) -> bool:
    """An AM-session position is open or was closed today (a pre-open window's trade is not an AM fill)."""
    if pos is not None:
        tr = pos.get("trade") if isinstance(pos, dict) else None
        if tr is None or tr.session == "AM":
            return True
    return any(tr.session == "AM" for tr in trades)


def macro_fail_key(ctx, p, session: str, i: int, t: int):
    """N9-macro-failure-any-macro (073 ~00:35:33): a macro window (macro_fail_windows) that ended with no new extreme toward the session's draw ends the session's entries (scope "session"),
    or the day's (scope "day"). Reuses daycontext._macro_test (the no-move proxy of N9.5). The two AM windows with the session scope are the macro_no_move switch's own business."""
    if p.macro_fail_windows == "am" and p.macro_fail_scope == "session":
        return None
    from . import daycontext as DW
    wins = MACRO_FAIL_ALL if p.macro_fail_windows == "all" else MACRO_FAIL_AM
    cache = DW._ctx_cache(ctx)
    here_pm = session in ("PM", "LUNCH")
    for (a, b) in wins:
        if t + ctx.tf < b:
            continue
        win_pm = a >= 700
        if p.macro_fail_scope == "session" and win_pm != here_pm:
            continue
        key = ("mfail", a, b)
        if not cache.get(key):                       # only a TRUE failure is cached: a False computed while the side was still unknown must be re-asked
            cache[key] = DW._macro_test(ctx, p, "PM" if win_pm else "AM", a, b, i) and not _macro_displaced(ctx, p, session, a, b, i)
        if cache[key]:
            hit("macro_fail")
            return "x_macro_fail"
    return None


def _macro_displaced(ctx, p, session: str, a: int, b: int, i: int) -> bool:
    """The displacement half of the N9 failure proxy [our interpretation]: some bar of the window has a body in the draw direction at least 1.5 x the mean body of the reference minutes before it."""
    lk = (getattr(ctx, "lock", None) or {}).get("PM" if session in ("PM", "LUNCH") else "AM")
    side = int(lk["side"]) if lk and lk.get("side") else 0
    if not side:
        from .entries import bias_row_known
        row = bias_row_known(ctx, i)
        try:
            side = int(row["draw"]) if row is not None else 0
        except (KeyError, TypeError, ValueError):
            side = 0
    if not side:
        return False
    t, S = ctx.t, ctx.start
    ref = np.flatnonzero((t[S:] >= a - p.macro_ref_min) & (t[S:] < a)) + S
    win = np.flatnonzero((t[S:] >= a) & (t[S:] < b)) + S
    if not len(ref) or not len(win):
        return False
    base = float(np.abs(ctx.c[ref] - ctx.o[ref]).mean())
    mv = side * (ctx.c[win] - ctx.o[win])
    return bool(base > 0 and (mv >= 1.5 * base).any())


def macro_fail_close(p, session: str, done: dict) -> None:
    """A failed macro ends the entries: the session's done keys (plain, Silver Bullet; Ma Deuce is a pre-08:00 setup that runs before any macro window, so it has no key to close), or every session's with scope "day"."""
    ks = ["AM", "PM", "LUNCH", "PRE7", "PRE9", "NEWS", "PRE8", "LON"] if p.macro_fail_scope == "day" else [session]
    for k in ks:
        done[k] = True
        done["SB_" + k] = True


def gate2(ctx, p, day, session: str, t: int, i: int, wb: int, trades, done: dict, state: dict, pos, pending):
    """(funnel key | None, cancel_pending) at bar i of `session`. The key skips this bar's scan; cancel_pending drops the armed order too (it must not fill into the rule)."""
    S = _S()
    tags = events(day)
    am_ = session == "AM"
    # new-am-search-timebox-60min (042 ~00:05:55): one hour of looking from 09:30, then cut bait
    if p.am_search_minutes and am_ and t >= 570 + p.am_search_minutes and not done.get("AM") and not _am_filled(trades, pos):
        done["AM"] = True
        if p.am_search_sb == "include":
            done["SB_AM"] = True
        hit("am_search")
        return None, bool(pending is not None and pending.get("session") not in ("PM", "LUNCH"))
    # T5-am-session-to-noon: no new AM entries after am_trend_end
    if p.am_trend_end and am_ and t >= p.am_trend_end:
        hit("am_trend_end")
        return "x_am_trend_end", True
    # T8-lunch-length-am-speed
    if p.lunch_by_speed and session in AM_FAM and t >= 660 and speed_class(ctx, p, i) == "slow":
        return "x_lunch_slow_am", True
    # T8-lunch-raid-target: no PM entry before the lunch pool was run
    if p.lunch_raid_wait and p.lunch_raid != "off" and session == "PM" and t < p.lunch_raid_by and not lunch_raided(ctx, p, i):
        hit("lunch_raid_wait")
        return "x_lunch_raid_wait", False
    # N9-macro-failure-any-macro
    why = macro_fail_key(ctx, p, session, i, t)
    if why:
        macro_fail_close(p, session, done)
        return why, True
    # N1-nfp-both-sides-macro (073 ~00:13:15; ~00:26:38)
    if (p.nfp_both_sides or p.nfp_macro_only) and "jobs" in tags and session in AM_FAM + ("LUNCH",):
        if p.nfp_macro_only and not any(a <= t < b for a, b in NFP_MACROS):
            return "x_nfp_macro_only", False
        if p.nfp_both_sides:
            sq = nfp_sequence(ctx, p)
            if sq is None or sq["both"] is None or sq["both"] > i or int(ctx.t[sq["both"]]) >= 670:
                hit("nfp_both_wait")
                return "x_nfp_both_sides", False
    # N5-two-driver-session: wait for the 10:00 dealing range
    if p.two_driver_mode == "wait2" and two_driver(day, p) and session != "PM" and t >= 510:
        d = getattr(ctx, "news_dr", {}).get(600)
        if d is None or d["made"] is None or i < d["made"]:
            hit("two_driver_wait")
            return "x_two_driver_wait", False
    # N3-fomc-whipsaw-skip-london
    if p.fomc_whipsaw_skip != "off" and whip_flag(ctx, p, day):
        if session == "LON" or (p.fomc_whipsaw_skip == "am" and session in AM_FAM):
            hit("fomc_whip_skip")
            return "x_fomc_whipsaw", True
    # N3-post-fomc-thu-fri
    if p.post_fomc_am == "symmetry" and session in AM_FAM and CAL.fomc_info(day)["after"] and not symmetry_ok(ctx, p, i):
        hit("post_fomc_symmetry_wait")
        return "x_post_fomc_symmetry", False
    # T9-pm-start-time: PM setups between 13:30 and 14:00 are skipped
    if p.pm_1400_disp and session == "PM" and 810 <= t < 840:
        return "x_pm_1400", False
    # T4-no-early-entry-conditions: a pending 10:00+ release disables the pre-open windows
    if p.pre_entry_guard and session in PRE_WINS and any(r >= 600 for r in NC.releases(day, p)):
        hit("pre_guard_release")
        return "x_pre_entry_guard", False
    # new-10min-wait-choppy (027 ~00:25:03)
    if p.chop_wait_bars and pos is None and pending is None:
        ch = getattr(ctx, "chop", None)
        if ch is not None and ch.on_at is not None and not ch.released and ch.on_at <= i < ch.on_at + p.chop_wait_bars:
            hit("chop_wait")
            return "x_chop_wait", False
    return None, False


# ---------------------------------------------------------------------------------------------------
# side filters
# ---------------------------------------------------------------------------------------------------

def side2(ctx, p, day, session: str, sign: int, i: int, t: int):
    """A funnel key when side `sign` is closed at bar i, else None."""
    if p.pre_news_coil:
        b = coil_block(ctx, p, day, i)
        if b and sign == b:
            k = coil_mss_k(ctx, b)
            if k is None or k > i:
                hit("pre_news_coil")
                return "x_pre_news_coil"
    if p.nfp_both_sides and "jobs" in events(day) and session in AM_FAM + ("LUNCH",):
        sq = nfp_sequence(ctx, p)
        if sq is not None and sq["both"] is not None and sq["both"] <= i and sq["allow"] and sign != sq["allow"]:
            return "x_nfp_side"
    if p.news_trend_side:
        why = _trend_side(ctx, p, session, sign, i)
        if why:
            return why
    if p.fomc_end and session in ("PM", "LUNCH") and CAL.fomc_info(day)["fomc"] and t >= p.fomc_end:
        d = fomc_move_dir(ctx, p, i)
        if d and sign == d:
            hit("fomc_end")
            return "x_fomc_end"
    if p.pre_fomc_week_smt and p.pre_fomc_week_light and fomc_week_before(day, t):
        ok = smt_same_side(ctx, i, sign)
        if ok is False:
            return "x_pre_fomc_week_smt"
    return None


def _trend_side(ctx, p, session, sign, i):
    """N6-news-runs-trailed-stops (065 ~04:11:02): after the release's dealing range is made only the daily-bias side trades, and only when the range's counter-trend extreme swept a pool
    (a confirmed, untaken swing before the release lay inside it)."""
    drv = getattr(ctx, "cur_news", None)
    if drv is None or drv.get("made") is None or i < drv["made"] or session == "PM":
        return None
    from . import entries as EN
    row = EN.bias_row_known(ctx, i)
    if row is None:
        return None
    try:
        b = int(row["draw"]) or int(row["react"])
    except (KeyError, TypeError, ValueError):
        return None
    if not b:
        return None
    if sign != b:
        return "x_news_trend_side"
    S = _S()
    kR = S._idx_at(ctx, drv["R"])
    sd = ctx.sides_map[1]
    if b > 0:
        swept = any(q.known <= kR and q.i < kR and q.price > drv["lo"] and not (ctx.l[q.i + 1:kR] <= q.price).any() for q in sd.pl)
    else:
        swept = any(q.known <= kR and q.i < kR and q.price < drv["hi"] and not (ctx.h[q.i + 1:kR] >= q.price).any() for q in sd.ph)
    if not swept:
        return "x_news_trend_noswept"
    hit("news_trend_side")
    return None


# ---------------------------------------------------------------------------------------------------
# order tags and filters (newscal.post_order tail)
# ---------------------------------------------------------------------------------------------------

def order_tags(ctx, sd, i: int, p, session: str, o_: dict):
    tags, why = _order_tags(ctx, sd, i, p, session, o_)
    for x in tags:
        hit("tag_" + x.split("=")[0])
    if why:
        hit("rej_" + why)
    return tags, why


def _order_tags(ctx, sd, i: int, p, session: str, o_: dict):
    """(tags list, reject key | None) for an order armed at bar i."""
    S = _S()
    t = int(ctx.t[i])
    day = ctx.day
    tags = []
    if p.two_driver_mode != "off" and two_driver(day, p):
        tags.append("two_driver")
        k600 = S._idx_at(ctx, 600)
        if k600 < len(ctx.t) and i >= k600 - 1:
            eq = (float(ctx.h[ctx.start:k600].max()) + float(ctx.l[ctx.start:k600].min())) / 2
            tags.append(f"eq_two_driver={eq:.2f}")
    if p.multi_release != "off":
        r = rel_tag(day, p)
        tags.append(r)
        if r == "rel0_wildcard":
            tags.append("no_news_wildcard")
    if p.news_seq_study:
        rs = [r for r in NC.releases(day, p) if r <= t]
        if rs:
            q = news_sequence(ctx, p, max(rs), i)
            if q is not None:
                tags.append("news_seq_" + q["order"])
    if p.kz_release_tag:
        from . import entries as EN
        row = EN.bias_row_known(ctx, i)
        try:
            b = int(row["draw"]) or int(row["react"]) if row is not None else 0
        except (KeyError, TypeError, ValueError):
            b = 0
        if kz_release_extreme(ctx, p, i, b):
            tags.append("kz_release_extreme")
    if p.news_sweep_min and o_.get("ext_i") is not None:
        te = int(ctx.t[int(o_["ext_i"])])
        if any(r <= te < r + p.news_sweep_min for r in NC.releases(day, p)):
            tags.append("news_sweep")
    if p.fomc_stage_study:
        for R, ok in ((840, CAL.fomc_info(day)["fomc"]), (510, "jobs" in events(day))):
            if ok:
                sl = stage_label(ctx, p, R, i)
                if sl is not None:
                    tags.append(f"stage_{sl['label']}_{R}")
    if p.lunch_by_speed:
        k = speed_class(ctx, p, i)
        if k:
            tags.append("am_speed_" + k)
    if p.lunch_raid != "off" and session == "PM" and lunch_raided(ctx, p, i):
        tags.append("lunch_raided")
    if session == "PM":
        idx = o_.get("fvg_i")
        idx = idx if idx is not None else (o_.get("broke") if o_.get("broke") is not None else o_.get("ext_i"))
        if p.pm_array_from and idx is not None and int(ctx.t[int(idx)]) < p.pm_array_from:
            return tags, "x_pm_array_from"
        if p.pm_1400_disp and t >= 840:
            if not _mss_displaced(ctx, sd, o_, p):
                return tags, "x_pm_1400_disp"
            tags.append("pm_1400")
    if p.chop_wait_bars:
        ch = getattr(ctx, "chop", None)
        if ch is not None and ch.on_at is not None and ch.on:
            if not _mss_displaced(ctx, sd, o_, p):
                return tags, "x_chop_disp"
    if p.pre_entry_guard and session in PRE_WINS and _pool_beyond_stop(ctx, sd, o_, i, p):
        return tags, "x_pre_entry_pool"
    if p.macro_trend_off and (p.macro_gate or p.macro_only != "off") and trend_day_nr(ctx, i):
        tags.append("trend_day")
    return tags, None


def _mss_displaced(ctx, sd, o_, p) -> bool:
    """The MSS candle body is at least displacement_mult (1.5 when that switch is off [our interpretation]) x the mean body of the ten bars before it (M1.2)."""
    k = o_.get("broke")
    if k is None:
        return True
    k = int(k)
    mult = p.displacement_mult or 1.5
    body = abs(float(sd.c[k] - sd.o[k]))
    prev = np.abs(sd.c[max(0, k - 10):k] - sd.o[max(0, k - 10):k])
    return bool(len(prev) == 0 or body >= mult * float(prev.mean()))


def _pool_beyond_stop(ctx, sd, o_, i: int, p) -> bool:
    """T4-no-early-entry-conditions (100 ~01:26:48): an untaken swing pool (side space, the sell side for a long) beyond the stop and within one risk distance of it [our interpretation of "close"]."""
    entry, stop = float(o_["entry"]), float(o_["stop"])
    risk = entry - stop
    if risk <= 0:
        return False
    for q in sd.pl:
        if q.known <= i and stop - risk <= q.price < stop and not (sd.l[q.i + 1:i + 1] <= q.price).any():
            return True
    return False


# ---------------------------------------------------------------------------------------------------
# after a close (strategy._after_close)
# ---------------------------------------------------------------------------------------------------

def after_close(ctx, tr, done: dict, p, day) -> None:
    """pre_draw_done_am: a pre-09:30 trade that delivered the session draw ends the AM; hard_day_one_trade: a PRE7 target fill on a hard day ends AM and PM."""
    if tr.session not in PRE_WINS + ("LON",) or not tr.exits:
        return
    ex = tr.exits[-1]
    if p.pre_draw_done_am and ctx is not None:
        lk = (getattr(ctx, "lock", None) or {}).get(tr.session)
        if lk is not None and lk.get("delivered") and (ex[0].hour * 60 + ex[0].minute) < 570:
            done["AM"] = True
            hit("pre_draw_done_am")
    tgt = str(ex[3]) in ("t1", "t2", "t3", "target") or str(ex[3]).startswith("tp")
    if p.hard_day_one_trade and tgt and tr.session == "PRE7" and hard_day(day):
        for k in ("AM", "PM", "SB_AM", "SB_PM"):
            done[k] = True
        hit("hard_day_done")


# ---------------------------------------------------------------------------------------------------
# setups: post_news_fade, pre_open_bnb
# ---------------------------------------------------------------------------------------------------

def any_special(p) -> bool:
    return bool(p.post_news_fade or p.pre_open_bnb)


def _htf_hit(ctx, sd, i: int, price_side: float, tfs) -> bool:
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return False
    import pandas as pd
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    return any(x in tfs for x in cf.at(now, float(sd.x(price_side)), sd.sign))


def fade_order(ctx, sd, i: int, p, risk_mult: float):
    """N5-pre0930-entries (050 ~00:34:08), side space (a long off a downward spike; shorts mirror): after the 08:30 release the spike low (bars 08:30 .. i) went into a 15m / 1h array of this
    side, a volume imbalance of this side formed after it and is alive, and the last 3+ bars made no new extreme: a limit at the VI near edge, stop one tick beyond its far edge. [our
    interpretation: any 15m / 1h array of this side stands for the HTF OB.]"""
    S = _S()
    kR = S._idx_at(ctx, 510)
    if kR >= len(ctx.t) or i < kR + 4:
        return None
    seg = sd.l[kR:i + 1]
    j = kR + int(np.argmin(seg))
    if i - j < 3 or not _htf_hit(ctx, sd, j, float(sd.l[j]), ("15m", "1h")):
        return None
    sent = sd.__dict__.setdefault("_pnf_sent", set())
    for z in sorted(sd.vis("bull"), key=lambda z_: -z_.i):
        if z.i <= j or z.i > i or sd.c[z.i + 1:i + 1].min(initial=np.inf) < z.bottom:
            continue
        key = (z.i, round(float(z.top), 4))
        entry = float(z.top)
        if key in sent or entry >= sd.c[i]:
            continue
        stop = float(z.bottom) - S._tick(p)
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(key)
        hit("post_news_fade")
        from . import sm4
        return sm4._order(ctx, sd, i, p, "NEWS", risk_mult, "post_news_fade", entry, stop, level=entry, ext=float(sd.l[j]), ext_i=j, broke=i, fvg_bottom=float(z.bottom),
                          lv=("post_news_fade",), done_key="PNF", cut_at=570, exit_at=569)
    return None


def bnb_order(ctx, sd, i: int, p, risk_mult: float):
    """N5-soft-bias-pre-open (007 ~14:35, experienced; side space; shorts run the same code on mirrored prices) in 08:00-09:00: a sweep of a pre-market relative-low (a confirmed swing low made since 00:00) into an HTF discount
    array (daily / 4h / 1h of this side), a bullish order block formed after the sweep that no close has broken: a limit at the block top, stop under its MT, target the nearest untaken short-term
    high; flat by 09:29. [our interpretation: the 1m OB is built on the base bars.]"""
    from . import levels as L
    S = _S()
    a = ctx.start
    seg = sd.l[a:i + 1]
    j = a + int(np.argmin(seg))
    tk = S._tick(p)
    pre = [q for q in sd.pl if q.known <= j and q.i < j and sd.l[q.i + 1:j].min(initial=np.inf) > q.price and sd.l[j] < q.price - tk]
    if not pre or i - j < 2 or not _htf_hit(ctx, sd, j, float(sd.l[j]), ("1h", "4h", "D")):
        return None
    z = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, j, i, "bull")
    if z is None or z.src < j:
        return None
    k_ob = max(q for q in range(z.src, i + 1) if sd.c[q] < sd.o[q])          # the block's last down-close candle: the block "holds" while no close after it is under the MT
    if (sd.c[k_ob + 1:i + 1] < z.mt).any() or i - k_ob < 1:
        return None
    sent = sd.__dict__.setdefault("_bnb_sent", set())
    if (z.src, round(float(z.top), 4)) in sent:
        return None
    entry, stop = float(z.top), float(z.mt) - S._tick(p)
    if entry >= sd.c[i] or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    hs = [q.price for q in sd.ph if q.known <= i and q.price > entry and not (sd.h[q.i + 1:i + 1] >= q.price).any()]
    if not hs:
        return None
    sent.add((z.src, round(float(z.top), 4)))
    hit("pre_open_bnb")
    from . import sm4
    return sm4._order(ctx, sd, i, p, "PRE8", risk_mult, "pre_open_bnb", entry, stop, level=entry, ext=float(sd.l[j]), ext_i=j, broke=i, fvg_bottom=float(z.bottom),
                      fvg_ce=float(z.mt), lv=("pre_open_bnb",), done_key="BNB", cut_at=570, exit_at=569, fixed=[(float(min(hs)) - S._tick(p), "pool")])


def special(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float, done: dict):
    """The two setups of this package that run outside the session windows (like sm7.special7): the post-news fade (08:30-09:30) and the pre-open buy-and-... (08:00-09:00)."""
    if pos is not None or pending is not None or state.get("day_done"):
        return None
    S = _S()
    t = int(ctx.t[i])
    jobs = (("PNF", p.post_news_fade and 510 <= t < 570 and 510 in NC.releases(ctx.day, p), fade_order, "NEWS"),
            ("BNB", p.pre_open_bnb and 480 <= t < 540, bnb_order, "PRE8"))
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_lock_any, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, None, "", False, 0
        for key, on, fn, ses in jobs:
            if not on or done.get(key):
                continue
            ctx.cur_session = ses
            if (p.day_filter and S.blocked(ctx.day, ses, p, t)) or (p.skip_news and S.news(ctx.day) != "none" and key != "PNF"):
                continue
            for sd in sides:
                out = fn(ctx, sd, i, p, risk_mult)
                if out is not None:
                    break
            if out is not None:
                break
    finally:
        for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session"):
            if k in saved:
                setattr(ctx, k, saved[k])
            else:
                ctx.__dict__.pop(k, None)
    return out


# ---------------------------------------------------------------------------------------------------
# management: the event-eve noon half-close (X10-pre-nfp-noon-exit)
# ---------------------------------------------------------------------------------------------------

def event_eve_noon(ctx, sd, pos, tr, i: int, ts, p, day, t: int, tf: int, c: float) -> bool:
    """X10-pre-nfp-noon-exit (050 ~00:52:31): at the first bar from 11:50, the day before a jobs / CPI / FOMC day, with at least two targets hit and price within 25 % of the daily array's
    height of its FAR edge (the array being traded into): close half of what is left, keep the rest under the existing stop. Once per position. `c` is the close in side space."""
    if pos.get("eve_noon_done") or t < 710:
        return False
    pos["eve_noon_done"] = True
    if not (events(CAL.next_trading_day(day)) & HIGH_IMPACT) or pos["k"] < 2 or pos["left"] <= 0:
        return False
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return False
    import pandas as pd
    from . import me2
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    real = float(sd.x(c))
    s = sd.sign
    # arrays known at `now` (no beyond-price cut: the array price is inside or next to qualifies); near / far in real prices
    cand = [(near, far) for near, far in cf.arrays_any(now, s, ("D",)) if abs(far - near) > 0 and s * (far - real) >= 0]
    if not cand:
        return False
    near, far = min(cand, key=lambda x: abs(x[0] - real))
    height = abs(far - near)
    if s * (far - real) > 0.25 * height + 1e-9:
        return False
    if me2.partial_close(pos, tr, sd, ts, c, 0.5, "eve_noon", p) > 0:
        hit("eve_noon")
        return True
    return False


# ---------------------------------------------------------------------------------------------------
# study: the pre-event pool map (N6-news-pool-mapping)
# ---------------------------------------------------------------------------------------------------

def _pivots_tf(ctx, k_end: int, m: int):
    """Confirmed (n = 1) swing highs / lows of the m-minute bars built from the day's bars [start .. k_end] (a bar is complete only when its last base bar is in): lists of (price, bar_index_of_the_swing_bar's_last_base_bar)."""
    from . import levels as L
    if m == ctx.tf:
        ph, pl = L.pivots(ctx.h[ctx.start:k_end + 1], ctx.l[ctx.start:k_end + 1], 1)
        return [(q.price, ctx.start + q.i) for q in ph if ctx.start + q.known <= k_end], [(q.price, ctx.start + q.i) for q in pl if ctx.start + q.known <= k_end]
    per = m // ctx.tf
    n = (k_end + 1 - ctx.start) // per
    hs, ls, last = [], [], []
    for b in range(n):
        a = ctx.start + b * per
        hs.append(float(ctx.h[a:a + per].max()))
        ls.append(float(ctx.l[a:a + per].min()))
        last.append(a + per - 1)
    ph, pl = L.pivots(np.array(hs), np.array(ls), 1)
    return [(q.price, last[q.i]) for q in ph if q.known < n], [(q.price, last[q.i]) for q in pl if q.known < n]


def pool_study(ctx, p, R: int, i: int):
    """037 ~00:11:55 (a study exercise, never a trade): one minute before the release R mark the untaken 5m / 15m swing highs and lows within 1 x ADR5 of price (the buy-side pools above, the
    sell-side below); after R log which side's NEAREST pool the event move took first and whether the other was taken later (through bar i). dict(highs, lows, first = +1 / -1 / 0 (same bar
    or none), k_first, other = bool, k_other). None when the bar before R has not closed or no ADR5."""
    S = _S()
    kR = S._idx_at(ctx, R)
    adr = _adr(ctx)
    if kR >= len(ctx.t) or kR <= ctx.start + 3 or i < kR or not adr:
        return None
    k0 = kR - 1
    px = float(ctx.c[k0])
    highs, lows = [], []
    for m in (5, 15):
        if m % ctx.tf:
            continue
        ph, pl = _pivots_tf(ctx, k0, m)
        highs += [v for v, kk in ph if px < v <= px + adr and not (ctx.h[kk + 1:k0 + 1] >= v).any()]
        lows += [v for v, kk in pl if px - adr <= v < px and not (ctx.l[kk + 1:k0 + 1] <= v).any()]
    if not highs and not lows:
        return None
    hi, lo = (min(highs) if highs else None), (max(lows) if lows else None)
    kh = next((k for k in range(kR, i + 1) if hi is not None and ctx.h[k] >= hi), None)
    kl = next((k for k in range(kR, i + 1) if lo is not None and ctx.l[k] <= lo), None)
    if kh is not None and (kl is None or kh < kl):
        first, kf, other, ko = 1, kh, kl is not None, kl
    elif kl is not None and (kh is None or kl < kh):
        first, kf, other, ko = -1, kl, kh is not None, kh
    else:
        first, kf, other, ko = 0, kh, kh is not None, kl
    return dict(highs=sorted(set(highs)), lows=sorted(set(lows), reverse=True), near_high=hi, near_low=lo, first=first, k_first=kf, other=other, k_other=ko)
