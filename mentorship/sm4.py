"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models, chunk 4 of 7: the engine glue of its 36 specs from models_setups_entries.md (items 11-17, 19-23, 26, 28, 31-37,
39, 40, 43, 47-50, 53-56, 58-60, 62).

Same conventions as sm2.py / sm3.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object
only from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar being
judged). Every function sits behind a Params switch of the "caption-gap pass, setups_models #4/7" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS` is
sm2's counter dict (tests: proof that a switch's code path RAN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2, sm3

HITS = sm2.HITS
hit = sm2.hit

MIN1 = 1e-9


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm4", {})


def _want(ctx) -> int:
    return sm2.want(ctx)


def _synth(S, session: str, name: str, level: float, ext: float, ext_i: int, broke):
    return dict(session=session, name=name, level=float(level), key=name, ext=float(ext), ext_i=int(ext_i), broke=broke, sweep_i=int(ext_i), smt=None, smt2=None,
                **{S._SM.SYNTH: True})


def _order(ctx, sd, i: int, p, session: str, risk_mult: float, name: str, entry: float, stop: float, *, level=None, ext=None, ext_i=None, broke=None, leg_hi=None, fixed=None,
           fvg_bottom=None, fvg_ce=None, lv=(), **tags):
    """The common tail of this chunk's non-sweep setups: a synthetic sweep object + the engine's order tail (`_finish_order`, skip_leg_pd, no PO3 open filter unless synth_po3)."""
    S = _S()
    ext_i = int(i if ext_i is None else ext_i)
    ext = float(sd.l[ext_i]) if ext is None else float(ext)
    sw = _synth(S, session, name, entry if level is None else level, ext, ext_i, i if broke is None else broke)
    t = dict(unicorn=False, fvg_bottom=float(stop if fvg_bottom is None else fvg_bottom), fvg_ce=float(entry if fvg_ce is None else fvg_ce), entry_kind=name, mitigation=False,
             propulsion=False, no_leg_wait=True, skip_po3=not p.synth_po3, lv_tags=[name, *lv])
    t.update(tags)
    lh = float(sd.h[min(ext_i, i):i + 1].max()) if leg_hi is None else float(leg_hi)
    return S._finish_order(ctx, sd, i, p, session, sw, float(entry), float(stop), risk_mult, lh, t, skip_leg_pd=True, fixed=fixed)


def conf_arrays(ctx, sd, i: int, tfs, src=(0,), known_at_start: bool = True) -> list:
    """The same-side Confluence arrays (default FVGs) of the given timeframes valid at bar i's close, in side space [(top, bottom, tf)]; known_at_start: only those complete before the day's
    first bar (the daily / weekly ones are known after their session closes)."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return []
    kb = ctx.idx[ctx.start] if known_at_start else None
    out = []
    for top, bot, tf, sc, kn in cf.valid(sm2.now_ts(ctx, i), sd.sign, tfs, src, kb):
        a, b = sd.x(top), sd.x(bot)
        out.append((max(a, b), min(a, b), tf))
    return out


def is_fvg_zone(z) -> bool:
    return z.mt != z.mt


def _tf_fvgs(ctx, sd, m: int) -> list:
    """The bullish (side space) FVGs of the m-minute bars built from the day's bars (empty when m cannot be built from the base bars)."""
    if m == ctx.tf:
        return [z for z in sd.gaps if is_fvg_zone(z)]                   # the base bars ARE the m-minute bars
    if m < ctx.tf or m % ctx.tf:
        return []
    return [z for z in sd.zones_tf(ctx.idx, ctx.tf, m) if is_fvg_zone(z)]


def _alive(sd, z, i: int) -> bool:
    """A zone no bar closed through (below its bottom) since it formed, through bar i."""
    return bool(sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1)


# --- 11 new-falling-dagger-upper-half-buy ---------------------------------------------------------------------------------------------------------

def dagger_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-falling-dagger-upper-half-buy (012 ~00:20:06; experienced-only, off): a bullish daily FVG (Confluence, complete before today), the bias this way, price trading back into its UPPER
    half (above the CE): a pre-MSS buy limit into the falling move - at the daily CE (`dagger_level` "ce") or the highest 15m / 60m bullish FVG low between the CE and the daily FVG top ("ltf").
    The lower-half imbalances (the hourly FVGs there) are expected to stay open: skipped once price filled one today. Stop just under the CE [our interpretation: stop_buffer, floored at
    min_risk_pts]; a bar trading under the CE before the fill cancels the order (`cancel_low`)."""
    if _want(ctx) != sd.sign or i < ctx.start + 3:
        return None
    px = float(sd.c[i])
    sent = sd.__dict__.setdefault("_dag_sent", set())
    tol = p.eq_tol_pts * p.es_pt
    for top, bot, tf in conf_arrays(ctx, sd, i, ("D",)):
        key = (round(top, 6), round(bot, 6))
        ce = (top + bot) / 2
        if key in sent or not (ce < px <= top + MIN1):
            continue
        z60 = _tf_fvgs(ctx, sd, 60) + _tf_fvgs(ctx, sd, 15)
        lower = [z for z in z60 if z.top <= ce + tol and z.bottom >= bot - tol and z.i <= i]
        if any(float(sd.l[z.i + 1:i + 1].min(initial=np.inf)) <= z.bottom + MIN1 for z in lower):
            hit("dagger_lower_filled")
            continue
        entry = ce
        if p.dagger_level == "ltf":
            ups = [z.bottom for z in z60 if ce + MIN1 <= z.bottom <= top and z.i <= i and _alive(sd, z, i) and z.bottom < px]
            if ups:
                entry = float(max(ups))
        if entry >= px - MIN1:
            continue
        stop = ce - max(p.stop_buffer, p.min_risk_pts * p.es_pt)
        sent.add(key)
        hit("dagger")
        return _order(ctx, sd, i, p, session, risk_mult, "dagger_entry", entry, stop, level=ce, fvg_bottom=ce, cancel_low=float(ce), lv=("dagger",))
    return None


# --- 12 M12-0930-htf-fvg-stab-no-mss --------------------------------------------------------------------------------------------------------------

def big_event_day(ctx, session: str, p, t: int = 0) -> bool:
    """Review fix (#12 / #43): a Fed-chair / FOMC / other big-event day, from the calendar itself (the engine's `blocked()` rules are switches that default off): the FOMC day or its tag, a Fed-chair
    testimony / speech day, the jobs day, a CPI day - or a day `strategy.blocked` already flags."""
    S = _S()
    from mentorship.calendar import events
    from . import calendar as CAL
    d = ctx.day
    if events(d) & {"fomc", "jobs", "cpi"} or CAL.fomc_info(d)["fomc"] or d in CAL.FED_CHAIR or d in CAL.FED_CHAIR_EXTRA:
        return True
    r = S.blocked(d, session, p, t)
    return r is not None and not r.startswith("nfp_week") and r != "monday"        # (the NFP-week Thursday / Friday and Monday rules are not events)


def stab_order(ctx, sd, sw, i: int, p, session: str, risk_mult: float):
    """M12-0930-htf-fvg-stab-no-mss (015 ~00:16:57; 038 ~00:21:57): turtle_soup="htf_stab" - an HTF (`stab_tfs`) bullish FVG lying beyond a pool of relatively equal lows; the run of the pool
    arms a limit at the FVG's near edge (no MSS, no SMT, whatever the touching candle is), stop beyond its far edge, the target the session lock / the normal ladder. Not on a Fed-chair / FOMC
    day; a run that stops short of the FVG fills nothing (the order simply rests; N9 depth is the existing sweep-depth rule)."""
    S = _S()
    if not str(sw.get("key", "")).startswith("rel_eq"):
        return None
    if big_event_day(ctx, session, p, int(ctx.t[i])):
        hit("stab_fomc")
        return None
    if sd.c[i] < sw["ext"]:
        return None
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    tfs = tuple(f"{m}m" if m < 60 else "1h" for m in p.stab_tfs)
    arrs = [a for a in S._ts_arrays(ctx, sd, i, kb, tfs, (0,)) if a[0] < sw["level"] - MIN1 and sd.c[i] >= a[1] - MIN1]
    if not arrs:
        return None
    top, bot, _ = max(arrs)
    sw["ts_sent"] = True
    hit("htf_stab")
    stop = bot - p.pad
    if top - stop < p.min_risk_pts * p.es_pt:
        stop = top - p.min_risk_pts * p.es_pt
    tags = dict(unicorn=False, fvg_bottom=bot, fvg_ce=(top + bot) / 2, entry_kind="htf_stab", mitigation=False, propulsion=False, lv_tags=["htf_stab"])
    return S._finish_order(ctx, sd, i, p, session, sw, top, stop, risk_mult, float(sd.h[sw["ext_i"]:i + 1].max()), tags, skip_leg_pd=True)


# --- 14 new-po3-midnight-open-resting-order -------------------------------------------------------------------------------------------------------

def po3_rest_order(ctx, sides, i: int, p, risk_mult: float):
    """new-po3-midnight-open-resting-order (013 ~00:09:46): at the 00:00 bar's close, with the bias of the night before (the Confluence daily / 4h structure: the htf.table has no row before the
    first lock) nonzero: a resting limit just under (over) the midnight open M, the minimum size, no adds, no breakeven / trail (`day_trade`); target 1 = the day's high already formed at the fill
    (`on_fill`), target 2 = the HTF objective; the stop under the nearest old low under the limit [our interpretation]."""
    S = _S()
    if ctx.t[i] != 0 or i != ctx.start or "midnight" not in ctx.opens:
        return None
    b = sm2.bias_at(ctx, p, "AM", i, use_want=False)
    if not b:
        return None
    sd = sides[0] if b > 0 else sides[1]
    M = float(sd.x(ctx.opens["midnight"]))
    entry = M - p.po3_rest_off_pts * p.es_pt
    lows = [sd.x(ctx.pd[k]) for k in (("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")) if k in ctx.pd]
    if "prev_pm" in ctx.sess:
        hi, lo, _ = ctx.sess["prev_pm"]
        lows.append(sd.x(lo if sd.sign > 0 else hi))
    lows = [float(v) for v in lows if v < entry - MIN1]
    if not lows:
        return None
    stop = max(lows) - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = entry - p.min_risk_pts * p.es_pt
    obj = sm3.htf_level_beyond(ctx, sd, i, p, entry, "AM", entry)
    if obj is None:
        return None
    hit("po3_rest")
    o = _order(ctx, sd, i, p, "PO3R", risk_mult, "po3_rest", entry, stop, level=M, fvg_bottom=stop, fixed=[(S._exit_px(obj, "array", p), "array")], day_trade=(p.po3_rest_mgmt == "none"), no_expire=True,
               sm4=dict(kind="po3_rest", obj=float(S._exit_px(obj, "array", p))), done_key="PO3R", lv=("po3_rest",))
    if o is None:
        return None
    n = max(int(p.lot), 1)
    o.update(shares=n, plan_shares=n, no_adds=True)
    return o


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    """Fill-time rewrite of the levels the order could not know when it was armed: po3_rest - target 1 = the day's high formed before the fill, target 2 = the HTF objective."""
    st = o.get("sm4")
    if not st:
        return
    pos["sm4"] = dict(st)
    if st.get("kind") == "po3_rest":
        fill = float(pos["basis"] / pos["n"])
        t1 = float(sd.h[ctx.start:i].max()) if i > ctx.start else None
        lv = []
        if t1 is not None and t1 > fill + p.tick:
            lv.append((t1, "pool"))
        lv.append((st["obj"], "array"))
        lv = [(v, k) for v, k in lv if v > fill + MIN1]
        if not lv:
            return
        pos["levels"], pos["level_kinds"] = [v for v, _ in lv], [k for _, k in lv]
        pos["fracs"] = (0.5, 0.5) if len(lv) > 1 else (1.0,)
        pos["t1"], pos["t2"] = pos["levels"][0], (pos["levels"][1] if len(lv) > 1 else None)
        pos["final_T"] = False
        tr.t1 = float(sd.x(pos["t1"]))
        tr.t2 = None if pos["t2"] is None else float(sd.x(pos["t2"]))
        hit("po3_rest_fill")


# --- 15 M5-lasthour-first-unit-at-old-low ---------------------------------------------------------------------------------------------------------

def lh_slot_now(ctx, i: int, p, session: str) -> bool:
    S = _S()
    return session == "PM" and p.last_hour[0] <= ctx.t[i] < S._SM.lh_window(p)[1]


def lh_old_low_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M5-lasthour-first-unit-at-old-low (013 ~00:26:58): the last hour (15:00-15:50), bias this way: unit 1 = a limit at the nearest untaken sell-side pool under the close (the sell-side pools
    of `_sell_side`), filled on a 1-tick trade-through, no MSS first; stop `lh_old_low_stop_pts` under the pool [our interpretation: ICT gives none]. After the fill the first bullish FVG of the
    rally arms an add of `lh_add2_mult` x the unit on a down-close bar into it (`manage`); later adds follow the E12 half sizes."""
    S = _S()
    if not lh_slot_now(ctx, i, p, session) or _want(ctx) != sd.sign:
        return None
    tk = S._tick(p)
    lv = S._sell_side(ctx, sd, session, i, True, p)
    px = float(sd.c[i])
    cand = [(v, k) for k, v in lv.items() if v < px - MIN1 and S._level_intact(ctx, sd.l, i, k, v, session, tk)]
    if not cand:
        return None
    v, k = max(cand)
    sent = sd.__dict__.setdefault("_lhol_sent", set())
    if round(float(v), 6) in sent:
        return None
    stop = float(v) - p.lh_old_low_stop_pts * p.es_pt
    sent.add(round(float(v), 6))
    hit("lh_old_low")
    return _order(ctx, sd, i, p, session, risk_mult, "lh_old_low", float(v), stop, level=v, fvg_bottom=stop, through=float(p.tick), sm4=dict(kind="lh_old_low", add2=None), lv=("lh_old_low",))


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this package tagged (pos["sm4"]): lh_old_low (the same-size second unit), pm_old_high_fvg (the add at the first retrace candle's open),
    pm_rev_partial (the gap fully re-traded)."""
    st = pos.get("sm4")
    if not st or i <= pos["fill_i"] or not pos["left"]:
        return
    S = _S()
    k = st.get("kind")
    if k in ("lh_old_low", "lh_array") and pos["add"] is None and st.get("add2") is None and (k == "lh_old_low" or p.lh_array_iofed):
        new = [g for g in sd.gaps if g.i <= i and g.i - 2 > pos["fill_i"]]
        if new:
            g = new[0]                                           # review fix: the FIRST gap formed after the fill (lh_old_low 013; lh_array_short the next SIBI - the IOFED add)
            if sd.c[g.i + 1:i + 1].min(initial=np.inf) < g.bottom - MIN1:
                return
            if sd.c[i] < sd.o[i] and sd.l[i] <= g.top and g.top > pos["stop"]:
                q = S._lots(pos["plan_shares"] * p.lh_add2_mult, p.lot)
                S._arm_add(pos, tr, float(g.top), i, p, ctx.equity, floor=float(g.bottom), size=q)
                st["add2"] = int(g.i)
                hit("lh_add2" if k == "lh_old_low" else "lh_array_iofed")
    elif k == "pm_old_high" and pos["add"] is None and not st.get("added"):
        g = st["gap"]
        if sd.c[i] < sd.o[i] and sd.l[i] <= g[0] and float(sd.o[i]) > pos["stop"]:
            q = S._lots(pos["plan_shares"] * p.adds[0], p.lot) if p.adds else 0
            if q >= 1:
                S._arm_add(pos, tr, float(sd.o[i]), i, p, ctx.equity, floor=float(g[1]), size=q)
                st["added"] = True
                hit("pm_old_high_add")
    elif k == "pm_rev_partial":                                  # M6 (015 ~00:33:56): the reversal's gap must stay partly open - a trade through its far edge is the gap fully re-traded
        far = st["far"]
        if sd.l[i] <= far + MIN1 and not st.get("done"):
            st["done"] = True
            sm3._part(sd, pos, tr, ts, float(min(sd.o[i], far)), 1.0, "gap_refill", p, all_=True)
            hit("pm_rev_refill")


def after_close(pos, tr, done: dict) -> None:
    """pm_old_high_fvg: the target fill arms the M6 reversal (done["PM_REV_ARMED"], read by setups.pm_reversal)."""
    st = pos.get("sm4")
    if st and st.get("kind") == "pm_old_high" and tr.final_hit and done is not None:
        done["PM_REV_ARMED"] = True
        hit("pm_rev_armed")


# --- 16 M6-pm-continuation-long-at-old-high -------------------------------------------------------------------------------------------------------

def pm_old_high_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M6-pm-continuation-long-at-old-high (015 ~00:31:57): PM, bias this way, the HTF objective above not yet traded to, price has just traded above an intraday old high (the AM / lunch /
    London / prior-PM high, within the last `pm_old_high_bars` bars) and a bullish FVG whose range spans that high's price formed since: a buy limit at the FVG's top (candle-3 low), the first
    down-close retrace candle's open is the add, stop under the FVG, the single target = the HTF objective. The target fill arms the M6 reversal (`after_close`)."""
    S = _S()
    if session != "PM" or ctx.t[i] < 780 or _want(ctx) != sd.sign:
        return None
    if S._SM.htf_done(ctx, sd, i):
        return None
    highs = []                                                  # the buy-side extremes of the day so far, side space (the real high for a long, the mirrored low for a short)
    if ctx.am_hl:
        highs.append(float(sd.x(ctx.am_hl[0] if sd.sign > 0 else ctx.am_hl[1])))
    for nm in ("lunch", "london", "prev_pm"):
        if nm in ctx.sess:
            hi, lo, _ = ctx.sess[nm]
            highs.append(float(sd.x(hi if sd.sign > 0 else lo)))
    if not highs:
        return None
    sent = sd.__dict__.setdefault("_pmoh_sent", set())
    n = max(int(p.pm_old_high_bars), 1)
    a = max(S._idx_at(ctx, 810), i - n + 1)
    for g in reversed([g for g in sd.gaps if g.i <= i and g.i - 2 >= a - 2 and g.i not in sent]):
        H = next((h_ for h_ in sorted(highs, reverse=True) if g.bottom < h_ < g.top and float(sd.h[a:i + 1].max()) > h_), None)
        if H is None or sd.c[g.i + 1:i + 1].min(initial=np.inf) < g.bottom - MIN1:
            continue
        entry = float(g.top)
        if entry >= sd.c[i] - MIN1:
            continue
        obj = sm3.htf_level_beyond(ctx, sd, i, p, entry, session, entry)
        if obj is None:
            continue
        sent.add(g.i)
        hit("pm_old_high")
        x = float(S._exit_px(obj, "array", p))
        return _order(ctx, sd, i, p, session, risk_mult, "pm_old_high_fvg", entry, float(g.bottom) - p.pad, level=H, fvg_bottom=float(g.bottom), fvg_ce=float(g.mid), fixed=[(x, "array")],
                      sm4=dict(kind="pm_old_high", gap=(float(g.top), float(g.bottom)), added=False), lv=("pm_old_high_fvg",))
    return None


# --- 17 M6-ifvg-must-stay-partly-open (the helpers; the order itself is setups.pm_reversal) -------------------------------------------------------------

def lunch_eq_highs(ctx, sd, i: int, p, lo_m: int = 720, hi_m: int = 780) -> list:
    """The relatively equal highs (side space) of the swings formed in the [lo_m, hi_m) bars (the 12:00-13:00 lunch rel-eq pools, mirrored: for a long the rel-eq highs, for a short the lows)
    still untraded above bar i: clusters of >= 2 pivot highs within eq_tol_pts [our interpretation]."""
    S = _S()
    tol = p.eq_tol_pts * p.es_pt
    q = [x for x in sd.ph if x.known <= i and lo_m <= ctx.t[x.i] < hi_m]
    if len(q) < 2:
        return []
    out = []
    for lv in L.equal_levels([x.price for x in q], tol):
        if float(sd.h[S._idx_at(ctx, hi_m):i + 1].max(initial=-np.inf)) < lv:
            out.append(float(lv))
    return out


def pm_rev_extra_targets(ctx, sd, i: int, p, entry: float) -> list:
    """pm_rev_partial: the lunch rel-eq pools join the ladder after the old daily level (015 ~00:33:56: targets in order - nearest intraday liquidity, the old daily high, the 12:00-13:00
    relative equal lows, then the next HTF FVG): [(level, kind)] above the entry (side space), plus the nearest 1h / 4h opposing array's near edge ([our interpretation] of "the next HTF FVG")."""
    out = [(v, "pool") for v in lunch_eq_highs(ctx, sd, i, p) if v > entry + MIN1]
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        for near, ce, far, tf, src in cf.opposing(sm2.now_ts(ctx, i), sd.x(entry), sd.sign, ("1h", "4h"), (0,))[:1]:
            out.append((float(sd.x(near)), "array"))
    return out


# --- 19 new-pm-retracement-short-after-draw-delivered ------------------------------------------------------------------------------------------------

def delivered_bar(ctx, b: int, i: int):
    """The first bar by which the day's objective in the real direction b (+1 up / -1 down) was delivered: the session lock's delivered_i, else the first bar the htf.table draw traded; None."""
    best = None
    for lk in getattr(ctx, "lock", {}).values():
        if lk.get("side") == b and lk.get("delivered_i") is not None and lk["delivered_i"] <= i:
            best = lk["delivered_i"] if best is None else min(best, lk["delivered_i"])
    if best is not None:
        return int(best)
    row = getattr(ctx, "bias_row", None) or {}
    v = row.get("draw_up" if b > 0 else "draw_dn")
    if v is not None and v == v:
        seg = ctx.h[ctx.start:i + 1] if b > 0 else ctx.l[ctx.start:i + 1]
        hitm = np.flatnonzero(seg >= float(v)) if b > 0 else np.flatnonzero(seg <= float(v))
        if len(hitm):
            return ctx.start + int(hitm[0])
    return None


def mss_gap(sd, g, a: int) -> bool:
    """A gap (side space) whose middle candle closed above a swing high confirmed after bar `a` (the break of a short-term high = the MSS the displacement made)."""
    hs = [q for q in sd.ph if q.i >= a and q.known <= g.src]
    if not hs:
        return False
    q = hs[-1]
    return bool(sd.c[g.src] > q.price and sd.c[q.i + 1:g.src].max(initial=-np.inf) <= q.price)


def pm_after_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-pm-retracement-short-after-draw-delivered (019 ~00:20:53; 060 ~01:09:30): the day's predefined objective (the opposite real direction) has been delivered; then (a) a body close beyond
    a 5m FVG that served as AM support (the other Side's 5m bullish FVG formed before 12:00; flipped to resistance) and a 1m BPR / FVG forming at or beyond it, or (b) a displacement that
    breaks a short-term swing and leaves a gap (SIBI): a limit at the BPR / gap's near edge, filled 13:20-15:00 (800-900), stop beyond it, at least `pm_after_room_pts` to the next gap / void
    beyond the entry; targets: the lunch relative equal pools, the nearest void, the AM-origin extreme. Side space (a short = the mirrored long)."""
    S = _S()
    t = int(ctx.t[i])
    if session != "PM" or not (800 <= t < 900):
        return None
    b = -sd.sign
    di = delivered_bar(ctx, b, i)
    if di is None:
        return None
    sent = sd.__dict__.setdefault("_pma_sent", set())
    tol = p.eq_tol_pts * p.es_pt
    other = sm2.other_side(ctx, sd, p)
    cand = []                                                  # (entry, bottom, key, tag)
    for z in [z for z in _tf_fvgs(ctx, other, 5) if ctx.t[z.i] < 720]:
        k = next((k for k in range(max(di, z.i + 1), i + 1) if other.c[k] < z.bottom - MIN1), None)
        if k is None:
            continue
        for g in list(sd.gaps) + [x for x in sd.bprs() if x.kind == "bull"]:
            if g.i > k and g.i <= i and g.bottom >= sd.x(z.top) - tol and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1 and ("a", g.i, g.src) not in sent:
                cand.append((float(g.top), float(g.bottom), ("a", g.i, g.src), "pm_after_flip"))
    if not cand:
        for g in sd.gaps:
            if di <= g.i <= i and ("b", g.i, g.src) not in sent and mss_gap(sd, g, max(ctx.start, di - 3)) and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1:
                cand.append((float(g.top), float(g.bottom), ("b", g.i, g.src), "pm_after_sibi"))
    if not cand:
        return None
    entry, bot, key, tag = max(cand, key=lambda x: x[2][1])                  # the newest gap / BPR
    if entry >= sd.c[i] - MIN1:
        return None
    opp = [z for z in sd.opposing() if z.i <= i and z.bottom > entry + MIN1 and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
    void = min((z.bottom for z in opp), default=None)
    if void is not None and void - entry < p.pm_after_room_pts * p.es_pt:
        hit("pm_after_room")
        return None
    a0 = S._idx_at(ctx, 570)
    orig = float(sd.x(ctx.l[a0:i + 1].min()) if sd.sign < 0 else sd.x(ctx.h[a0:i + 1].max()))
    lv = [(v, "pool") for v in lunch_eq_highs(ctx, sd, i, p, 720, 810) if v > entry + MIN1]
    if void is not None:
        lv.append((float(void), "array"))
    if orig > entry + MIN1:
        lv.append((orig, "pool"))
    if not lv:
        return None
    fixed = sorted({(float(S._exit_px(v, k, p)), k) for v, k in lv})
    sent.add(key)
    hit("pm_after_draw")
    return _order(ctx, sd, i, p, session, risk_mult, "pm_after_draw", entry, bot - p.pad, level=entry, fvg_bottom=bot, fixed=fixed, done_key="PMA", lv=(tag,))


# --- 20 M1-ob-entry-after-mss ------------------------------------------------------------------------------------------------------------------------

def ob_post_cand(ctx, sd, sw, i: int, p):
    """M1-ob-entry-after-mss (020 ~00:06:14): after the MSS (sw["broke"]) the first down-close candle of the ensuing pullback is the OB: the limit at `ob_entry_px` of that candle (A12: its
    sensitive range), the order cancelled by a body close under its MT. (entry, bottom, "ob_post") or None; the candle's MT is kept in sw["_ob_post_mt"]."""
    S = _S()
    b = sw.get("broke")
    if b is None:
        return None
    ks = [k for k in range(int(b) + 1, i + 1) if sd.c[k] < sd.o[k]]
    if not ks:
        return None
    k = ks[0]
    mt = float((sd.o[k] + sd.c[k]) / 2)
    if sd.c[k + 1:i + 1].min(initial=np.inf) < mt - MIN1:
        return None                                              # a body closed through the MT: invalid
    ob = dict(j=k, k=k, body_top=float(sd.o[k]), body_low=float(sd.c[k]), mt=mt, hi=float(sd.h[k]), lo=float(sd.l[k]))
    sw["_ob_post_mt"] = mt
    sw["_ob_post_k"] = k                                         # caption-gap setups_models #6/7 review fix: ob_below_open / eq_fresh_ob judge THIS candle
    return (float(S._EN.ob_entry_price(ob, sd, p, i)), float(sd.c[k]), "ob_post")


# --- 21 B5-multi-tf-fvg-scan -------------------------------------------------------------------------------------------------------------------------

def m2_eq(sd, sw, i: int) -> float:
    """The displacement leg's equilibrium in side space: the sweep extreme .. the highest high since."""
    return float(sw["ext"] + 0.5 * (float(sd.h[sw["ext_i"]:i + 1].max()) - sw["ext"]))


def leg_tf_gaps(ctx, sd, sw, gaps: list, i: int, p):
    """B5-multi-tf-fvg-scan (022 ~00:43:05; 055 ~00:11:46): with `leg_tfs` set and no 1m gap of the leg at or under the leg EQ (side space: the discount; real short: at or above EQ), look for one
    on each timeframe of `leg_tfs` (highest first - the tuple is sorted; the bars of the leg, `sd.zones_tf`) and take the first timeframe that has one; where a higher-TF gap holds a narrower gap of a LATER (lower)
    timeframe of the tuple the narrower gap's edges are used (the more sensitive level). Returns (gaps, [added zones])."""
    eq = m2_eq(sd, sw, i)
    if any(g.top <= eq + MIN1 for g in gaps):
        return gaps, []
    hit("leg_tf_eval")
    e = sw["ext_i"]
    tfs = sorted({int(m) for m in p.leg_tfs}, reverse=True)       # review fix: the order of the tuple does not matter - the highest timeframe first, a narrower gap of a lower one inside it refines it
    for n, m in enumerate(tfs):
        zs = [z for z in _tf_fvgs(ctx, sd, m) if z.i <= i and z.src > e and z.top <= eq + MIN1 and _alive(sd, z, i)]
        if not zs:
            continue
        z = zs[-1]
        for m2 in tfs[n + 1:]:
            inner = [y for y in _tf_fvgs(ctx, sd, m2) if y.i <= i and y.src > e and y.top <= z.top + MIN1 and y.bottom >= z.bottom - MIN1 and _alive(sd, y, i)]
            if inner:
                z, m = inner[-1], m2
        sw["leg_tf"] = int(m)
        hit("leg_tf")
        return sorted(list(gaps) + [z], key=lambda g: g.i), [z]
    return gaps, []


# --- 22 M2-leg-eq-after-low-prints / 26 M2-implied-range-eq-gate -------------------------------------------------------------------------------------

def m2_discount_gaps(sd, sw, gaps: list, i: int) -> list:
    """M2-leg-eq-after-low-prints (022 ~00:47:17): the candidate gaps are re-filtered on every new extreme of the leg - only those at or under the CURRENT EQ (side space: the discount)."""
    eq = m2_eq(sd, sw, i)
    out = [g for g in gaps if g.top <= eq + MIN1]
    if len(out) < len(gaps):
        hit("m2_live_eq_drop")
    return out


def m2_order_dead(sd, o: dict, k: int) -> bool:
    """A pending m2_live_eq order whose gap top lies above the leg EQ of bar k (the leg has re-anchored): cancelled."""
    e = o["ext_i"]
    eq = o["ext"] + 0.5 * (float(sd.h[e:k + 1].max()) - o["ext"])
    return bool(o.get("zone_top", o["entry"]) > eq + MIN1)


def runup_pick(ctx, sd, sw, pick: list, i: int, p):
    """M2-pyramid-runup-leg-eq (022 ~01:03:28): m2_anchor "runup" - the EQ from the swing the run into the swept pool started from (side space: the last pivot high before the sweep extreme)
    to the sweep extreme; a VI at or under that EQ in the displacement first, else the FVG there. None = nothing qualifies (the leg-EQ pick stands)."""
    hs = [q for q in sd.ph if q.i < sw["ext_i"] and q.known <= i]
    if not hs:
        return None
    eq = float(sw["ext"] + 0.5 * (hs[-1].price - sw["ext"]))
    vis = [z for z in sd.vis("bull") if sw["ext_i"] <= z.i <= i and z.top <= eq + MIN1]
    if vis:
        hit("m2_runup_vi")
        return vis[-1]
    fv = [g for g in pick if g.top <= eq + MIN1]
    if fv:
        hit("m2_runup_fvg")
        return fv[-1]
    return None


def implied_eq(ctx, sd, sw, i: int, p, session: str):
    """M2-implied-range-eq-gate (025 ~00:46:41; 060 ~01:24:16): the implied range = the suspect extreme H (the sweep extreme) .. the session lock's target (else the htf.table draw), side space; its
    EQ, or None when there is no objective to span (the gate is n/a then)."""
    lk = getattr(ctx, "cur_lock", None)
    D = None
    if lk is not None and lk.get("side") == sd.sign:
        D = float(sd.x(lk["target"]))
    else:
        r = sm3.row_draw(ctx, sd, i, session)
        if r is not None:
            D = float(r[0])
    if D is None or D <= sw["ext"] + MIN1:
        return None
    return float((sw["ext"] + D) / 2)


def implied_gate(ctx, sd, sw, gaps: list, i: int, p, session: str):
    """The gate: H is valid only after price traded from premium into discount (side space: a high at or over the EQ after the sweep extreme); until then the order is not armed ("wait");
    then only the gaps at or under EQ are entries. Returns ("wait", gaps) / (eq, gaps) / (None, gaps) when there is no objective."""
    eq = implied_eq(ctx, sd, sw, i, p, session)
    if eq is None:
        return None, gaps
    hit("implied_eval")
    if not (sd.h[sw["ext_i"] + 1:i + 1] >= eq - MIN1).any():
        if sd.l[sw["ext_i"] + 1:i + 1].min(initial=np.inf) < float(sw["ext"]) - MIN1:
            hit("implied_h_traded")
            return "dead", gaps                           # review fix: H traded first (our interpretation, 025) - the suspect extreme was taken before any premium-to-discount trade: cancelled
        return "wait", gaps
    hit("implied_range")
    return eq, [g for g in gaps if g.top <= eq + MIN1]


# --- 28 M7-pm-short-after-lunch-run-of-am-stops ------------------------------------------------------------------------------------------------------

def am_last_pool(ctx, sd, i: int, p):
    """M7-pm-short-after-lunch-run-of-am-stops (025 ~01:05:57): the PM pool `am_last_high` = the last AM swing extreme before 12:00 (side space: the last pivot LOW of the AM bars still untraded at
    noon) when the AM moved this side's way (the real direction of the trade: a bearish AM for a short) - the trailed AM stops. None when there is none."""
    S = _S()
    k0, k1 = S._idx_at(ctx, 570), S._idx_at(ctx, 720)
    if i < k1 or k1 <= k0 + 2 or not sd.c[k1 - 1] > sd.o[k0]:
        return None
    qs = [q for q in sd.pl if k0 <= q.i < k1 and q.known <= k1 and float(sd.l[q.i + 1:k1].min(initial=np.inf)) > q.price]
    return float(qs[-1].price) if qs else None


def am_stops_fixed(ctx, sd, i: int, p, entry: float):
    """pm_am_stops targets: the relatively equal pools between the entry and the AM origin are the first rungs, the AM session's far extreme (the AM low for a short) the final one."""
    S = _S()
    if not ctx.am_hl:
        return None
    tgt = float(sd.x(ctx.am_hl[1] if sd.sign < 0 else ctx.am_hl[0]))
    if tgt <= entry + MIN1:
        return None
    eq = [v for v in S._eq_levels(sd, i, p.eq_tol_pts * p.es_pt, lows=False, p=p) if entry + MIN1 < v < tgt - MIN1]
    fx = [(float(S._exit_px(v, "pool", p)), "pool") for v in sorted(eq)] + [(float(S._exit_px(tgt, "pool", p)), "pool")]
    hit("pm_am_stops_targets")
    return fx


# --- time-frame buckets of a Side -----------------------------------------------------------------------------------------------------------------------

def buckets(ctx, sd, m: int):
    """Clock-aligned m-minute buckets of the day frame in side space: (first, last, done, o, h, l, c) arrays; a bucket is `done` only once its last base bar is in (never a partial bucket)."""
    key_ = f"_bk4_{m}"
    hc = sd.__dict__.get(key_)
    if hc is None:
        key = ctx.idx.floor(f"{m}min")
        b = pd.Series(np.arange(len(key)), index=key).groupby(level=0)
        first, last = b.min().values, b.max().values
        done = np.asarray((ctx.idx[last] - b.min().index) >= pd.Timedelta(minutes=m - ctx.tf))
        o = np.array([sd.o[a] for a in first])
        c = np.array([sd.c[z] for z in last])
        hh = np.array([sd.h[a:z + 1].max() for a, z in zip(first, last)])
        ll = np.array([sd.l[a:z + 1].min() for a, z in zip(first, last)])
        hc = sd.__dict__[key_] = (first, last, done, o, hh, ll, c)
    return hc


# --- 31 M5-lasthour-short-sequence ----------------------------------------------------------------------------------------------------------------------

def lh_array_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M5-lasthour-short-sequence (026 ~01:35:33; 047 ~00:09:56), side space (a short = the mirrored long): (1) a bullish VI / FVG under the price, marked before 15:00 (alive at 15:00); (2) from
    15:00 a candle's low respects it (low into the array, close not through it) = the rejection bar R, a trade under R's low invalidates; (3) early confirmation (tag): the next bar makes no lower
    low and stays off the array, then its high is taken; (4) the MSS: a swing high formed after R pierced by one tick (no close needed); (5) the entry: the VI the displacement left (limit at its
    top - as soon as price trades back into it, even on an up-close candle), else the CE of the latest gap of the leg; stop under R's low; target the draw (the normal ladder). 15:00-15:50."""
    S = _S()
    if not lh_slot_now(ctx, i, p, session) or _want(ctx) not in ((sd.sign,) if p.lh_array_need_draw else (0, sd.sign)):
        return None
    k900 = S._idx_at(ctx, p.last_hour[0])
    if k900 > i or k900 < 1:
        return None
    sent = sd.__dict__.setdefault("_lharr_sent", set())
    tk = float(p.tick)
    hit("lh_array_eval")
    arrays = [(z.top, z.bottom, ("vi", z.i)) for z in sd.vis("bull") if z.i < k900] + [(g.top, g.bottom, ("fvg", g.i)) for g in sd.gaps if g.i < k900]
    arrays = [a for a in arrays if sd.c[a[2][1] + 1:k900].min(initial=np.inf) >= a[1] - MIN1 and a[0] <= sd.c[k900 - 1] + MIN1]
    for top, bot, key in sorted(arrays, key=lambda a: -a[0]):
        r = next((j for j in range(k900, i) if sd.l[j] <= top + MIN1 and sd.c[j] >= bot - MIN1 and sd.l[k900:j].min(initial=np.inf) >= bot - MIN1), None)
        if r is None or (key, r) in sent or sd.l[r + 1:i + 1].min(initial=np.inf) < sd.l[r] - MIN1:
            continue
        qs = [q for q in sd.ph if q.i > r and q.known <= i]
        mss = next((q for q in qs if sd.h[q.known:i + 1].max(initial=-np.inf) >= q.price + tk - MIN1), None)
        if mss is None:
            continue
        early = bool(r + 2 <= i and sd.l[r + 1] >= sd.l[r] - MIN1 and sd.l[r + 1] > top and sd.h[r + 2:i + 1].max(initial=-np.inf) > sd.h[r + 1])
        vis = [z for z in sd.vis("bull") if r < z.i <= i and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
        if vis:
            entry, bot2, kind = float(vis[-1].top), float(vis[-1].bottom), "vi"
        else:
            gs = [g for g in sd.gaps if r < g.i <= i and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1]
            if not gs:
                continue
            entry, bot2, kind = float(gs[-1].mid), float(gs[-1].bottom), "sibi_ce"
        if entry >= sd.c[i] - MIN1:
            continue
        sent.add((key, r))
        hit("lh_array_short")
        stop = float(sd.l[r]) - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            stop = entry - p.min_risk_pts * p.es_pt
        fx = None
        if p.lh_array_target == "sd3":                                # [026] the -3 SD projection of the MSS leg (R's extreme .. the leg extreme), side space: above the leg high
            leg_hi = float(sd.h[r:i + 1].max())
            tgt = leg_hi + p.lh_array_sd_k * (leg_hi - float(sd.l[r]))
            if tgt > entry + MIN1:
                fx = [(float(S._exit_px(tgt, "array", p)), "array")]
                hit("lh_array_sd")
        return _order(ctx, sd, i, p, session, risk_mult, "lh_array_short", entry, stop, level=top, ext=float(sd.l[r]), ext_i=r, fvg_bottom=bot2, fixed=fx, sm4=dict(kind="lh_array", add2=None),
                      lv=("lh_array_" + kind,) + (("lh_early_conf",) if early else ()))
    return None


# --- 32 B16-nwog-gapup-return-then-mss ------------------------------------------------------------------------------------------------------------------

def nwog_fill_gate(ctx, sd, sw, i: int, p, lvt: list):
    """B16-nwog-gapup-return-then-mss (028 ~01:22:36): in a gap-up week (this week's NWOG: Friday's close below the Sunday open - the all-hours open when the data has it, else the first RTH
    open) a LONG needs that price has traded back to the NWOG low (the Friday close) since the week began and that the sweep extreme sits within `nwog_fill_tol_pts` of it - a touch with no
    MSS afterwards is no entry (the MSS / FVG path follows as usual). Returns a reject key or None; real longs only (a gap down needs no return: a half-gap fail is breakaway weakness)."""
    S = _S()
    if sd.sign < 0:
        return None
    hist = getattr(ctx, "hist", [])
    lv = S._DW._week_objective_levels(ctx, hist, ctx.day, p, getattr(ctx, "eth", None))
    nw = lv.get("_nwog")
    if nw is None or not nw[1] > nw[0]:
        return None                                               # no NWOG known, or a gap down
    a = float(nw[0])
    rng = S._DW.week_range_so_far(ctx, hist, ctx.day, p, getattr(ctx, "eth", None), i)
    lows = [] if rng is None else [float(rng[1])]
    eve = getattr(ctx, "eve", None)
    if eve is not None and ctx.day.weekday() == 0:
        lows.append(float(eve[2]))                                # the Sunday evening of a Monday
    if not lows:
        return None
    hit("nwog_fill_eval")
    tol = p.nwog_fill_tol_pts * p.es_pt
    if min(lows) > a + 0.25 * p.es_pt or abs(float(sw["ext"]) - a) > tol:
        return "x_nwog_fill"
    lvt.append("nwog_fill")
    hit("nwog_fill")
    return None


# --- 33 M11-wick-ce-fade-short / 43 new-sweep-wick-ce-failure-swing-long ----------------------------------------------------------------------------------

def wick_ce_entry(ctx, sd, sw, i: int, p, session: str, risk_mult: float, ref: float):
    """M11 wick CE entries beyond the built close-confirmed long (`wick_ce_entries`), both sides (side space):
    `wick_ce_tf` 0 (the sweep candle itself): "close" = the built behaviour (limit at the CE once the next candle closed above it, target 0.5 pt before the high); "intrabar" (028 ~00:18:38) = armed on
    the sweep candle's close with no confirmation: a limit just beyond the CE (1 tick), the stop `wick_ce_pad_pts` beyond the CE; "retrace" = no order here - the sweep candle's wick CE is the entry
    of the no-FVG fallback (`array_cands`).
    `wick_ce_tf` 5 / 15 / 60 (084 ~00:30:43; 038 ~00:50:59; 080 ~00:05:45): the CE of the sweep candle on that timeframe once it has closed; the order is placed when a later bar retraces to
    within one tick of the CE (price bounced off it first) while the sweep low is intact: a limit at the CE, stop under the sweep low, cancelled by a trade under it; not on an FOMC day; the sweep
    must have taken a pool (`wick_ce_need_pool`: a pre-marked array premise is no sweep)."""
    S = _S()
    e = sw["ext_i"]
    tk = float(p.tick)
    if p.wick_ce_tf:
        if sw.get("wce_sent") or (p.wick_ce_need_pool and sw.get("key") == "htf_array"):
            return None
        if big_event_day(ctx, session, p, int(ctx.t[i])):
            return None
        first, last, done, o, hh, ll, c = buckets(ctx, sd, p.wick_ce_tf)
        j = int(np.searchsorted(first, e, side="right") - 1)
        if j < 0 or not done[j] or last[j] >= i:
            return None
        ce = float((min(o[j], c[j]) + ll[j]) / 2)
        low = float(ll[j])
        seg_lo = sd.l[last[j] + 1:i + 1]
        if seg_lo.min(initial=np.inf) <= low + MIN1:
            return None                                              # the sweep low was traded back: no failure swing
        if not (sd.c[last[j] + 1:i].max(initial=-np.inf) > ce + MIN1 and sd.l[i] <= ce + tk + MIN1):
            return None
        sw["wce_sent"] = True
        hit("wick_ce_tf")
        entry = ce
        stop = low - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            stop = entry - p.min_risk_pts * p.es_pt
        tags = dict(unicorn=False, fvg_bottom=low, fvg_ce=ce, entry_kind="wick_ce", mitigation=False, propulsion=False, no_leg_wait=True, cancel_low=low, lv_tags=[f"wick_ce_{p.wick_ce_tf}m"])
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[e:i + 1].max()), tags, skip_leg_pd=True)
    if p.wick_ce_mode == "intrabar" and not sw.get("wce_sent") and i == e:
        sw["wce_sent"] = True
        ce = L.wick_ce(sd.o, sd.l, sd.c, e)
        entry = float(ce + tk)
        if not sd.c[e] > entry + MIN1:
            return None
        if p.wick_ce_precursor and not (e >= 1 and sd.c[e - 1] > sd.o[e - 1]):
            return None                                              # review fix, 028 ~00:18:38: the wick follows a precursor that closed WITH the trade (a down-close for the short; side space: an up-close)
        hit("wick_ce_intrabar")
        stop = float(ce - p.wick_ce_pad_pts * p.es_pt)
        tags = dict(unicorn=False, fvg_bottom=sw["ext"], fvg_ce=ce, entry_kind="wick_ce", mitigation=False, propulsion=False, no_leg_wait=True, lv_tags=["wick_ce_intrabar"])
        return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[e:i + 1].max()), tags, skip_leg_pd=True)
    return None


# --- 34 M5-lasthour-shallowest-unused-array -------------------------------------------------------------------------------------------------------------

def unused_cands(ctx, sd, sw, i: int, p, bz, cs: list) -> list:
    """M5-lasthour-shallowest-unused-array (030 ~00:21:36): entry_pick "shallowest_unused" - drop every candidate array price has already traded back into between its creation and the MSS
    bar (its top reached by a low); the caller then takes the most sensitive (highest) one left. An array with no creation bar (the OTE band, a prior ORG) stays."""
    S = _S()
    e = sw["ext_i"]
    mss = int(sw["broke"]) if sw.get("broke") is not None else i
    made = {}
    ob = S._ob_at_low(sd, sw, i, p, ctx)
    if ob is not None:
        made["ob"] = ob["k"]
    vs = [z for z in sd.vis("bull") if e <= z.i <= i]
    if vs:
        made["vi"] = vs[-1].i
    if bz is not None:
        made["breaker"] = int(getattr(bz, "i", e))
    made["wick_ce"] = e
    made["ob_post"] = e
    out = []
    for x in cs:
        k = made.get(x[2])
        if k is not None and sd.l[k + 1:min(mss, i) + 1].min(initial=np.inf) <= x[0] + MIN1:
            hit("unused_drop")
            continue
        out.append(x)
    return out


# --- 37 A12-entry-array-at-key-level --------------------------------------------------------------------------------------------------------------------

def key_levels(ctx, sd, i: int, p, session: str) -> list:
    """The predefined key levels (side space): the NWOG / NDOG edges and CEs, the ORG edges, and the session pools of `_sell_side` (the old lows / the PM / London / AM ranges)."""
    S = _S()
    out = []
    for hi, lo, ce in sm2.gap_list(ctx, i, ("nwog", "nwog_rth", "ndog")):
        out += [float(sd.x(hi)), float(sd.x(lo)), float(sd.x(ce))]
    for a, b in (ctx.org[:-1] if (ctx.t[i] < 570 and getattr(ctx, "org_today", False)) else ctx.org)[-5:]:
        out += [float(sd.x(a)), float(sd.x(b))]
    out += [float(v) for v in S._sell_side(ctx, sd, session, i, True, p).values()]       # (review fix: no blanket except - a real error must surface)
    return out


def ob_key_gate(ctx, sd, sw, i: int, p, session: str, lvt: list):
    """A12-entry-array-at-key-level (032 ~00:21:34): the OB candle (the last opposite candle before the displacement; the sweep extreme when there is none) must have its extreme within `ob_key_ticks`
    of a predefined key level. Tag `ob_at_key`; "require" drops the others (`x_ob_key`)."""
    S = _S()
    ob = S._ob_at_low(sd, sw, i, p, ctx)
    x = float(ob["lo"]) if ob is not None else float(sw["ext"])
    tol = p.ob_key_ticks * p.tick
    hit("ob_at_key_eval")
    near = any(abs(x - v) <= tol + MIN1 for v in key_levels(ctx, sd, i, p, session))
    if near:
        lvt.append("ob_at_key")
        hit("ob_at_key")
        return None
    return "x_ob_key" if p.ob_at_key == "require" else None


# --- 35 new-nwog-edge-to-ce-cookie-cutter / 36 M8-short-after-reprice-to-prior-close -------------------------------------------------------------------

def nwog_ce_for_key(ctx, sd, i: int, key: str):
    """The CE (side space) of the stored NWOG behind a `gap_<kind><j>` sweep key, or None."""
    S = _S()
    gl = ctx.gaps if getattr(ctx, "gaps", None) is not None else [("monday", max(a, b), min(a, b), (a + b) / 2) for a, b in S._nwogs(ctx, i)]
    for j, (kind, hi, lo, ce) in enumerate(gl):
        if key == f"gap_{kind}{j}" and kind in ("nwog", "nwog_rth", "monday"):
            return float(sd.x(ce))
    return None


def nwog_edge_adjust(ctx, sd, sw, i: int, p, entry: float, tags: dict):
    """nwog_edge_ce: a sweep of an NWOG edge (the far edge, side space) targets that NWOG's CE - `exit_before_pts` (take profit just before the CE), at least 5 ES pts of room; not on a choppy
    day (`Chop.active_before`). Returns "x_nwog_edge_..." (a reject key) or None; sets tags["fixed4"]."""
    k = str(sw.get("key", ""))
    if not k.startswith("gap_"):
        return None
    ce = nwog_ce_for_key(ctx, sd, i, k)
    if ce is None:
        return None
    chop = getattr(ctx, "chop", None)
    if chop is not None and chop.active_before(i):
        return "x_nwog_edge_chop"
    tgt = ce - p.exit_before_pts * p.es_pt
    if tgt - entry < 5.0 * p.es_pt:
        return "x_nwog_edge_room"
    tags["fixed4"] = [(float(tgt), "array")]
    hit("nwog_edge_ce")
    return None


def org_reverse_adjust(ctx, sd, sw, i: int, p, entry: float, tags: dict):
    """org_fill_reverse (030 ~01:47:48): a sweep of the ORG's prior-close edge (the pool `org_close`: price repriced up to it) targets the session extreme (side space: the day's highest high so far,
    the session low of a bearish day), entries only before 12:00. Returns a reject key or None; sets tags["fixed4"] when the session extreme gives room."""
    S = _S()
    if sw.get("key") != "org_close":
        return None
    if ctx.t[i] >= 720:
        return "x_org_fill_late"
    a0 = S._idx_at(ctx, 570)
    ext = float(sd.h[a0:i + 1].max())
    hit("org_fill_reverse")
    if ext - entry >= p.min_rr * max(entry - sw["ext"], 1e-9):
        tags["fixed4"] = [(float(S._exit_px(ext, "pool", p)), "pool")]
    return None


# --- 39 M4-breaker-needs-fvg-inside / 40 A13-breaker-inversion-against -------------------------------------------------------------------------------------

def breaker_low_guard(sd, tags: dict, lvx: dict) -> None:
    """breaker_low_invalidate (032 ~00:42:02): a breaker / unicorn order is cancelled before the fill, and exited after it, by a body close beyond the breaker candle's far extreme (not its MT)."""
    bb = sm3.breaker_bounds(sd, tags) if sm3.is_breaker_entry(tags) else None
    if bb is None:
        return
    low = float(bb[1])
    lvx["breaker_low"] = (low, False)
    tags["cancel_close"] = low          # review fix: the far extreme REPLACES the MT-based cancel (the MT rule is the one this switch relaxes), not only raises it
    hit("breaker_low")


def _own_breakers(ctx, sd, i: int, p):
    """The latest bullish breaker (side space) of this Side formed in the current session, as (zone, formed bar, inverted bar or None, retrace-confirm bar or None)."""
    S = _S()
    ss = S._sess_start(ctx, i)
    if ss is None:
        return None
    key = ("brk", sd.sign, p.pivot_n)
    c = _c(ctx)
    if key not in c:
        c[key] = [z for z in L.breakers(sd.o, sd.h, sd.l, sd.c, p.pivot_n) if z.kind == "bull"]
    zs = [z for z in c[key] if ss <= z.i <= i]
    if not zs:
        return None
    z = max(zs, key=lambda z: z.i)
    inv = next((k for k in range(z.i + 1, i + 1) if sd.c[k] < z.bottom - MIN1), None)
    conf = None
    if inv is not None:
        r = next((k for k in range(inv + 1, i + 1) if sd.h[k] >= z.bottom - MIN1), None)
        if r is not None:
            conf = next((k for k in range(r + 1, i + 1) if sd.c[k] < z.bottom - MIN1), None)
    return z, z.i, inv, conf


def breaker_counter_gate(ctx, sd, i: int, p, session: str):
    """A13-breaker-inversion-against (033 ~00:49:43; 048 ~01:54:11): while a bullish breaker holds on a body-close basis (this session) no short is taken - an FVG above price alone does not qualify
    one; a body close below the breaker inverts it: longs are blocked for the session (and no automatic reversal: the counter side stands aside too) until price retraces into the zone and a bar
    closes back below it (the retrace that rejects as resistance), after which the counter side may trade. Mirror for the other Side. Returns a reject key or None."""
    other = sm2.other_side(ctx, sd, p)
    own = _own_breakers(ctx, sd, i, p)
    if own is not None and own[2] is not None:
        hit("breaker_inverted")
        return "x_breaker_inverted"                                   # this side's own breaker was inverted: no more of this direction this session
    ob = _own_breakers(ctx, other, i, p)
    if ob is None:
        return None
    if ob[2] is None:
        hit("breaker_counter")
        return "x_breaker_counter"                                    # the other side's breaker holds: no counter-trend trade
    if ob[3] is None:
        hit("breaker_counter_wait")
        return "x_breaker_counter"                                    # inverted, but not yet retraced and rejected
    return None


# --- 53 new-short-top-of-htf-discount-fvg ----------------------------------------------------------------------------------------------------------------

def top_short_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-short-top-of-htf-discount-fvg (050 ~00:51:08), side space (the short = the mirrored long): the bias this way, the near edge of an opposing daily FVG (a bullish daily FVG for a short = its top) already
    traded today, price back at that edge and a 5m breaker of this Side (the bearish breaker for a short) whose zone touches it: a limit at the zone's near edge, stop beyond it; the target
    just beyond the nearest swing inside the daily FVG (1 pt), never past its far edge; out by 12:00 (`exit_at`)."""
    S = _S()
    if _want(ctx) != sd.sign or ctx.t[i] >= 720:
        return None
    other = sm2.other_side(ctx, sd, p)
    _, last, done, o5, h5, l5, c5 = buckets(ctx, sd, 5)
    ok5 = np.flatnonzero(done & (last <= i))
    if len(ok5) < 6:
        return None
    n5 = len(ok5)
    brs = [z for z in L.breakers(o5[:n5], h5[:n5], l5[:n5], c5[:n5], 2) if z.kind == "bull"]
    if not brs:
        return None
    tol = p.eq_tol_pts * p.es_pt
    sent = sd.__dict__.setdefault("_top_sent", set())
    for top_r, bot_r, tf in conf_arrays(ctx, other, i, ("D",)):
        e_sd = float(sd.x(top_r))                                     # the near edge of the daily FVG in this Side's space (its far edge: sd.x(bot_r), above it)
        far = float(sd.x(bot_r))
        if not sd.h[ctx.start:i + 1].max() >= e_sd - MIN1:
            continue
        hit("top_short_eval")
        for z in sorted(brs, key=lambda z: -z.i):
            kz = int(last[z.i])
            if kz > i or not (z.bottom - tol <= e_sd <= z.top + tol) or (round(e_sd, 6), z.i) in sent:
                continue
            if sd.c[kz + 1:i + 1].min(initial=np.inf) < z.bottom - MIN1:
                continue
            entry = float(z.top)
            if entry >= sd.c[i] - MIN1:
                continue
            piv = [q.price for q in sd.ph if q.known <= i and entry < q.price <= far and q.i >= ctx.start]
            if not piv:
                continue
            tgt = min(min(piv) + 1.0 * p.es_pt, far - p.tick)
            if tgt - entry < p.min_rr * max(entry - (z.bottom - p.pad), 1e-9):
                continue
            sent.add((round(e_sd, 6), z.i))
            hit("htf_fvg_top_short")
            return _order(ctx, sd, i, p, session, risk_mult, "htf_fvg_top_short", entry, float(z.bottom) - p.pad, level=e_sd, fvg_bottom=float(z.bottom), fixed=[(float(tgt), "array")], exit_at=720,
                          lv=("htf_fvg_top_short",))
    return None


# --- 47 M16-sick-sister-ob-open-entry / 56 M16-sick-sister-discount-confluence --------------------------------------------------------------------------

def sick_refs(ctx, sd, i: int, p, session: str):
    """The sick-sister reference count of `setups.sick_sister` as a keyed table: (me, partners) where each is {key: (value in the instrument's own side space, taken)} at the session start (09:30 AM /
    13:30 PM) and the partner list covers the sister indices; None when the data or the session start is missing."""
    S = _S()
    sisters = []
    ps = getattr(ctx, "pside", None)
    if ps is not None and ps[0] is not None:
        sisters.append((ps[0], ps[1][sd.sign], ps[2]))
    if getattr(ctx, "partner2", None):
        sisters.append((ctx.partner2[0], ctx.partner2[1][sd.sign], ctx.partner2[2]))
    if not sisters:
        return None
    m0 = 810 if session == "PM" else 570
    tk = S._tick(p)

    def refs(c_, s_):
        k = S._idx_at(c_, m0)
        if k <= c_.start or k > len(c_.t):
            return None
        hk = "pdh" if s_.sign > 0 else "pdl"
        lv = {kk: s_.x(v) for kk, v in c_.pd.items() if kk.startswith(hk)}
        ok = "pmh" if s_.sign > 0 else "pml"
        if ok in c_.pd:
            lv[ok] = s_.x(c_.pd[ok])
        for nm in ("london", "prev_pm"):
            if nm in c_.sess:
                hi, lo, _ = c_.sess[nm]
                lv[nm] = s_.x(hi if s_.sign > 0 else lo)
        top = s_.h[c_.start:k].max()
        return {kk: (float(v), bool(S._spent_up(top, v, tk))) for kk, v in lv.items()}

    me = refs(ctx, sd)
    if me is None or S._idx_at(ctx, m0) > i:
        return None
    others = [refs(c_, s_) for c_, s_, _ in sisters]
    others = [x for x in others if x is not None]
    if not others:
        return None
    n_me = sum(1 for v in me.values() if v[1])
    if not n_me < min(sum(1 for v in o.values() if v[1]) for o in others):
        return None
    return me, others


def sick_ob_open_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M16-sick-sister-ob-open-entry (045 ~01:41:00): the leader has made the higher high (the partner index traded a reference high this one has not): the first down-close bar of this (the
    laggard) index arms a buy limit at that bar's open - no return to the OB is needed; stop under the bar's low, target the matching old high (the nearest reference the partner took and this one
    has not). One order per session."""
    S = _S()
    if session not in ("AM", "PM"):
        return None
    sent = sd.__dict__.setdefault("_sickob_sent", set())
    if session in sent or not sd.c[i] < sd.o[i]:
        return None
    r = sick_refs(ctx, sd, i, p, session)
    if r is None:
        return None
    me, others = r
    todays = float(sd.h[ctx.start:i + 1].max())
    match = [v[0] for kk, v in me.items() if not v[1] and v[0] > sd.c[i] and any(kk in o and o[kk][1] for o in others) and todays < v[0] + MIN1]
    if not match:
        return None
    entry = float(sd.o[i])
    stop = float(sd.l[i]) - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = entry - p.min_risk_pts * p.es_pt
    sent.add(session)
    hit("sick_ob_open")
    return _order(ctx, sd, i, p, session, risk_mult, "sick_ob_open", entry, stop, level=min(match), ext=float(sd.l[i]), ext_i=i, fvg_bottom=float(sd.l[i]),
                  fixed=[(float(S._exit_px(min(match), "pool", p)), "pool")], lv=("sick_ob_open",))


def sick_ote_stack_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M16-sick-sister-discount-confluence (053 ~00:05:17, ~00:10:51): consolidation only (no locked draw / a neutral bias); the sick sister: the leg from the day's swing low to the high it failed to
    exceed; price below EQ and the entry zone = where the 62-79% OTE band overlaps a bullish OB (consecutive down-close candles) AND a bullish FVG; up to `sick_units` resting limits spread over the
    overlap (the entry ladder rungs); no buying above EQ or on a rally; target the buy-side it failed to take (the matching old high)."""
    S = _S()
    if session not in ("AM", "PM") or getattr(ctx, "cur_bias", 0):
        return None
    r = sick_refs(ctx, sd, i, p, session)
    if r is None:
        return None
    hit("sick_ote_eval")
    me, others = r
    m0 = 810 if session == "PM" else 570
    a = S._idx_at(ctx, m0)
    hi_i = a + int(np.argmax(sd.h[a:i + 1])) if i >= a else None
    if hi_i is None or hi_i <= ctx.start + 2:
        return None
    H = float(sd.h[hi_i])
    lo_i = ctx.start + int(np.argmin(sd.l[ctx.start:hi_i + 1]))
    lowS = float(sd.l[lo_i])
    if H - lowS < p.min_risk_pts * p.es_pt * 2 or not sd.c[i] < (H + lowS) / 2:
        return None
    if sd.c[i] > sd.c[i - 1] and sd.c[i - 1] > sd.c[max(i - 2, 0)]:
        return None                                                  # rallying: no buy
    lo_b, hi_b, _ = L.ote_band(lowS, H)
    sent = sd.__dict__.setdefault("_sickote_sent", set())
    for g in reversed([g for g in sd.gaps if lo_i < g.i <= i and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1]):
        ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, max(g.src - 4, 0), g.src, "bull")
        if ob is None:
            continue
        top, bot = min(hi_b, g.top, ob.top), max(lo_b, g.bottom, ob.bottom)
        if top <= bot + MIN1 or top >= sd.c[i] - MIN1 or (g.i, round(top, 4)) in sent:
            continue
        match = [v[0] for kk, v in me.items() if not v[1] and v[0] > top and any(kk in o and o[kk][1] for o in others)] or [v[0] for kk, v in me.items() if not v[1] and v[0] > top]
        if not match:
            continue
        n = max(1, min(int(p.sick_units), len(p.entry_ladder_fracs)))
        lad = [float(top - (top - bot) * k / max(n - 1, 1)) for k in range(n)] if n > 1 else [float(top)]
        sent.add((g.i, round(top, 4)))
        hit("sick_ote_stack")
        tags = dict(ladder=lad) if n > 1 else {}
        return _order(ctx, sd, i, p, session, risk_mult, "sick_ote_stack", float(top), float(bot) - p.pad, level=H, ext=lowS, ext_i=lo_i, fvg_bottom=float(bot),
                      fixed=[(float(S._exit_px(min(match), "pool", p)), "pool")], lv=("sick_ote_stack",), **tags)
    return None


# --- 48 new-lunch-macro-long-nwog ------------------------------------------------------------------------------------------------------------------------

def lunch_nwog_order(ctx, sd, i: int, p, risk_mult: float):
    """new-lunch-macro-long-nwog (046 ~02:07:16; experimental, in conflict with T8): 11:40-12:10, a down AM (side space: the AM net move against the side), price inside [the NWOG low, the NWOG CE]
    (the old NWOG whose CE lies above the low), nothing traded under the NWOG low today: a limit at the CE (the zone's first touch from above) with the stop under the NWOG low, the target the
    buy-side above the NWOG high / the next FVG (the normal ladder). This branch alone bypasses the T8 lunch block (run_day arms it)."""
    S = _S()
    t = int(ctx.t[i])
    if sd.sign < 0 or not (700 <= t < 730):
        return None                                           # review fix: the spec is long-only (no mirrored short)
    k0 = S._idx_at(ctx, 570)
    if i <= k0 + 2 or not sd.c[i] < sd.o[k0]:
        return None
    sent = sd.__dict__.setdefault("_lnw_sent", set())
    for hi, lo, ce in sm2.gap_list(ctx, i, ("nwog", "nwog_rth")):
        lo_s, ce_s = min(float(sd.x(hi)), float(sd.x(lo))), float(sd.x(ce))
        if (round(lo_s, 6)) in sent or not (lo_s <= sd.c[i] <= ce_s + MIN1) or sd.l[ctx.start:i + 1].min() < lo_s - MIN1:
            continue
        entry = ce_s
        if p.lunch_nwog_entry == "ob":                        # [046 "or a down-close OB there"] the latest down-close candle whose body lies inside the zone: a limit at its body top
            ob = [k for k in range(k0, i + 1) if sd.c[k] < sd.o[k] and lo_s - MIN1 <= sd.c[k] and sd.o[k] <= ce_s + MIN1]
            if ob:
                entry = float(sd.o[ob[-1]])
                hit("lunch_nwog_ob")
        if entry >= sd.c[i] - MIN1:
            entry = float(min(sd.c[i] - p.tick, ce_s))
        stop = lo_s - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(round(lo_s, 6))
        hit("lunch_nwog_long")
        return _order(ctx, sd, i, p, "LUNCH", risk_mult, "lunch_nwog_long", entry, stop, level=lo_s, fvg_bottom=lo_s, exit_at=810, lv=("lunch_nwog_long",))
    return None


# --- 49 A8-symmetry-skip-ifvg-confirmation / 50 A8-ifvg-5m-to-1m-handoff ------------------------------------------------------------------------------------

def symmetric(ctx, sd, i: int, p) -> bool:
    """The indices agree (no SMT): the partner Side made the same higher high within the last `smt_window` ... bars - [our interpretation, no YM intraday data] ES and NQ both printed a higher high
    inside the window: both Sides' highest high of the last `ifvg_sym_bars` bars is a high of the day so far."""
    ps = getattr(ctx, "pside", None)
    if ps is None or ps[0] is None:
        return False
    n = max(int(p.ifvg_sym_bars), 1)
    a = max(ctx.start, i - n + 1)
    mine = float(sd.h[a:i + 1].max()) >= float(sd.h[ctx.start:i + 1].max()) - MIN1

    def _agrees(book) -> bool | None:
        pctx, psides, ppos = book
        j = int(ppos.index.searchsorted(ctx.idx[i], side="right") - 1)
        if j < pctx.start:
            return None
        psd = psides[sd.sign]
        pa = max(pctx.start, j - n + 1)
        return float(psd.h[pa:j + 1].max()) >= float(psd.h[pctx.start:j + 1].max()) - MIN1

    theirs = _agrees(ps)
    if theirs is None:
        return False
    if theirs and p.ifvg_sym_ym and getattr(ctx, "partner2", None):     # OA1029 Q55: with the YM book loaded, all three indices must agree
        hit("ifvg_sym_ym")
        theirs = bool(_agrees(ctx.partner2))
    if mine and theirs:
        hit("ifvg_sym_eval")
    return bool(mine and theirs)


def sym_zones(ctx, sd, sw, i: int, p) -> list:
    """The opposing (bearish, side space) FVGs of the leg a symmetric market may buy inside directly: formed after the sweep extreme, not closed through, the market already at or into them."""
    out = []
    for z in sd.opposing():
        if z.kind == "bear" and z.i <= i and z.src > sw["ext_i"] and z.bottom < sd.c[i] and sd.c[z.i + 1:i + 1].max(initial=-np.inf) <= z.top:
            out.append(L.Zone("bull", z.top, z.bottom, z.i, z.src))
    return out


def ifvg_tf_zones(ctx, sd, sw, i: int, p) -> list:
    """A8-ifvg-5m-to-1m-handoff (048 ~00:21:30): ifvg_tf = 5 - the reference gaps are the 5m bearish FVGs (side space). Ideal: a 5m candle CLOSES above the gap and a later 5m candle trades back into it
    and holds -> the inversion (known at that candle's last base bar). If a 5m candle only trades above it (no close), the check runs on the base bars: a body close above the gap, a NEW bar opening above
    and trading back into it (the zone is known there), the hold = no close back below the gap's bottom after the close above. Zones as bullish Zones."""
    m = int(p.ifvg_tf)
    if m < ctx.tf or m % ctx.tf:
        return []
    first, last, done, o, hh, ll, c = buckets(ctx, sd, m)
    n = int(np.flatnonzero(done & (last <= i))[-1]) + 1 if (done & (last <= i)).any() else 0
    if n < 3:
        return []
    out = []
    for z in L.fvgs(hh[:n], ll[:n], o[:n], c[:n], sd.c2_dir):
        if z.kind != "bear" or z.top - z.bottom < sd.min_gap or int(first[z.src]) <= sw["ext_i"] - 1:
            continue
        top, bot = float(z.top), float(z.bottom)
        k = next((q for q in range(z.i + 1, n) if hh[q] > top + MIN1), None)
        if k is None:
            continue
        if c[k] > top + MIN1:                                         # ideal: a 5m close above, then a 5m candle back into it that holds
            r = next((q for q in range(k + 1, n) if ll[q] <= top + MIN1), None)
            if r is not None and c[k + 1:r + 1].min(initial=np.inf) >= bot - MIN1 and c[r] >= bot - MIN1:
                out.append(L.Zone("bull", top, bot, int(last[r]), int(first[z.src])))
                hit("ifvg_5m")
            continue
        b1 = next((q for q in range(int(first[k]), min(int(last[k]), i) + 1) if sd.c[q] > top + MIN1), None)
        if b1 is None:
            b1 = next((q for q in range(int(last[k]) + 1, i + 1) if sd.c[q] > top + MIN1), None)
        if b1 is None:
            continue
        b2 = next((q for q in range(b1 + 1, i + 1) if sd.o[q] > top and sd.l[q] <= top + MIN1), None)
        if b2 is None or sd.c[b1:b2 + 1].min() < bot - MIN1:
            continue
        out.append(L.Zone("bull", top, bot, int(b2), int(first[z.src])))
        hit("ifvg_1m_handoff")
    return out


# --- 55 M16-trending-divergence-continuation -------------------------------------------------------------------------------------------------------------

def trend_day(ctx, sd, i: int, p) -> bool:
    """M16-trending-divergence-continuation (053 ~00:08:20): a trending day for this Side = the bias equals the locked draw's side (both this way), the session's FIRST market-structure break
    went this way, and no opposing HTF premium array (a 1h / 4h / daily array the other way, ahead) has been reached by today's extreme. [our proxy: no MSS against the trend, no premium array reached]."""
    S = _S()
    lk = getattr(ctx, "cur_lock", None)
    if not (_want(ctx) == sd.sign and lk is not None and lk.get("side") == sd.sign):
        return False
    hit("trend_eval")
    a = S._idx_at(ctx, 810 if getattr(ctx, "cur_session", "") == "PM" else 570)
    if a >= i:
        return False
    first = 0
    other = sm2.other_side(ctx, sd, p)
    for k in range(a + 1, i + 1):
        up = [q for q in sd.ph if q.known <= k - 1 and q.i >= ctx.start and sd.c[k] > q.price and sd.c[k - 1] <= q.price]
        dn = [q for q in other.ph if q.known <= k - 1 and q.i >= ctx.start and other.c[k] > q.price and other.c[k - 1] <= q.price]
        if up or dn:
            first = 1 if up and not dn else -1 if dn and not up else 0
            break
    if first != 1:
        return False
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        day_hi = float(sd.h[ctx.start:i + 1].max())
        for near, ce, far, tf, src in cf.opposing(sm2.now_ts(ctx, i), float(sd.x(float(sd.c[a]))), sd.sign, ("1h", "4h", "D"), (0,)):
            if sd.x(near) <= day_hi + MIN1:
                return False                                          # a premium array of the opposing kind was reached
    hit("trend_day")
    return True


# --- 59 M4-complete-model-breaker-ote-ob ------------------------------------------------------------------------------------------------------------------

def complete_model_tag(ctx, sd, sw, i: int, p, tags: dict, lvt: list):
    """M4-complete-model-breaker-ote-ob (056 ~00:12:24): a breaker entry (a breaker / unicorn order) is a `complete_model` when (a) the breaker comes from a parent swing (the reference swing high is an
    ITL / LTL high, `levels.swing_tiers`), (b) its zone lies within 62-79% of the leg (overlaps the OTE band of the leg from the sweep extreme to the leg high) and (c) a down-close candle (the
    short-term OB) from before the displacement sits inside the zone. Returns True when tagged."""
    bb = sm3.breaker_bounds(sd, tags) if sm3.is_breaker_entry(tags) else None
    if bb is None:
        return False
    hit("complete_eval")
    top, bot = float(bb[0]), float(bb[1])
    ref_i = sw.get("ref_i")
    tiers = sd.tiers()
    parent = ref_i is not None and any(q.i == ref_i and q.known <= i for q in tiers["itl"][0] + tiers["ltl"][0])
    leg_hi = float(sd.h[sw["ext_i"]:i + 1].max())
    lo_b, hi_b, _ = L.ote_band(float(sw["ext"]), leg_hi)
    in_ote = bot <= hi_b + MIN1 and top >= lo_b - MIN1
    e = sw["ext_i"]
    ob = any(sd.c[k] < sd.o[k] and bot - MIN1 <= min(sd.o[k], sd.c[k]) and max(sd.o[k], sd.c[k]) <= top + MIN1 for k in range(max(ctx.start, e - 12), e + 1))
    ok = bool(parent and in_ote and ob)
    if ok:
        lvt.append("complete_model")
        hit("complete_model")
    return ok


# --- 60 M5-lasthour-reversal-into-org ----------------------------------------------------------------------------------------------------------------------

def org_fill_ctx(ctx, sd, i: int, p):
    """M5-lasthour-reversal-into-org (059 ~00:24:09): today's ORG is unfilled (the day's extreme never reached its far edge, the prior close) and the session's objective the other way is
    delivered; (near edge, CE, far edge) in this Side's space when the ORG lies ABOVE the open in side space (the Side that trades toward it), else None."""
    if not (getattr(ctx, "org_today", False) and ctx.org):
        return None
    pc, op = ctx.org[-1]
    pcx, opx = float(sd.x(pc)), float(sd.x(op))
    if not pcx > opx + MIN1:
        return None
    S = _S()
    k0 = S._idx_at(ctx, 570)
    if float(sd.h[k0:i + 1].max()) >= pcx - MIN1:
        return None
    if not S._SM.htf_done_sign(ctx, -sd.sign, i):
        return None
    hit("lh_org_ctx")
    return opx, (opx + pcx) / 2, pcx


def lh_org_open(ctx, i: int, p) -> bool:
    """The side-agnostic form of `org_fill_ctx` (run_day: the LH slot may trade on although the session's draw is delivered)."""
    sm = getattr(ctx, "sides_map", None) or {}
    return any(org_fill_ctx(ctx, sd, i, p) is not None for sd in sm.values())


def lh_org_adjust(ctx, sd, sw, i: int, p, session: str, entry: float, tags: dict):
    """lh_org_fill: in the last hour with an unfilled ORG ahead the targets are [the ORG's near edge, its CE, the prior close] (above the entry, side space) and nothing else."""
    if session != "PM" or not lh_slot_now(ctx, i, p, session):
        return None
    r = org_fill_ctx(ctx, sd, i, p)
    if r is None:
        return None
    S = _S()
    lv = [(float(S._exit_px(v, "array", p)), "array") for v in r if v > entry + MIN1]
    if not lv:
        return "x_lh_org_room"
    tags["fixed4"] = lv
    hit("lh_org_fill")
    return None


# --- 62 D15-one-clean-gap-instrument -------------------------------------------------------------------------------------------------------------------

def gap_count(sd, sw, i: int) -> int:
    """D15-one-clean-gap-instrument (061 ~01:49:01): the number of same-side FVGs of the leg between the leg EQ and the leg extreme (side space: from the sweep extreme up to the EQ) - one clean
    obvious gap vs a muddy area of several small ones. `backtest.combine` smt_pick "clean" keeps the fill whose count is 1."""
    eq = m2_eq(sd, sw, i)
    e = sw["ext_i"]
    return int(sum(1 for g in sd.gaps if g.i - 2 >= e and g.i <= i and g.top <= eq + MIN1 and g.bottom >= sw["ext"] - MIN1))


# --- the order gate (strategy._finish_order, after order_gate3) ------------------------------------------------------------------------------------------

def any_gate4(p) -> bool:
    return bool(p.po3_ideal != "off" or p.nwog_fill_long or p.ob_at_key != "off" or p.complete_model != "off" or p.breaker_low_invalidate or p.breaker_block_counter
                or p.three_drives_htf or p.nwog_edge_ce or p.org_fill_reverse or p.lh_org_fill or p.pm_am_stops or p.smt_pick == "clean" or p.implied_range_gate
                or p.m2_live_eq)


def order_gate4(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #4/7 at order completion. Returns a reject key or None."""
    S = _S()
    synth = bool(sw.get(S._SM.SYNTH))
    if p.po3_ideal != "off" and not synth and sw.get("key") != "htf_array":
        mo = S._open_known(ctx, "midnight", i)
        if mo is not None:
            ideal = bool(ctx.t[sw["ext_i"]] >= 510 and sw["ext"] < sd.x(mo) - MIN1 and sw["level"] < sd.x(mo) - MIN1)
            hit("po3_ideal_eval")
            if ideal:
                lvt.append("po3_ideal")
                hit("po3_ideal")
            elif p.po3_ideal == "require":
                return "x_po3_ideal"
    if p.nwog_fill_long and not synth:
        r = nwog_fill_gate(ctx, sd, sw, i, p, lvt)
        if r:
            return r
    if p.ob_at_key != "off" and not synth:
        r = ob_key_gate(ctx, sd, sw, i, p, session, lvt)
        if r:
            return r
    if p.complete_model != "off" and not synth:
        ok = complete_model_tag(ctx, sd, sw, i, p, tags, lvt)
        if not ok and p.complete_model == "require" and sm3.is_breaker_entry(tags):
            return "x_complete_model"
    if p.breaker_low_invalidate:
        breaker_low_guard(sd, tags, lvx)
    if p.breaker_block_counter and not synth:
        r = breaker_counter_gate(ctx, sd, i, p, session)
        if r:
            return r
    if p.three_drives_htf and not synth:
        td = L.three_drives(sd.pl, sw["ext"], sw["ext_i"], i, max(0, ctx.start - 1), sw["level"] if p.td_same_level else None, p.td_level_pts * p.es_pt)     # (setups_models #5/7: td_same_level)
        if td:
            hit("td_htf_eval")
            ok = _want(ctx) == sd.sign or S._SM.htf_done_sign(ctx, -sd.sign, i)
            if ok:
                lvt.append("td_reversal")
            else:
                tags["single_exit"] = True
                tags["no_adds"] = True
                lvt.append("td_scalp")
                hit("td_scalp")
    if p.nwog_edge_ce and not synth:
        r = nwog_edge_adjust(ctx, sd, sw, i, p, entry, tags)
        if r:
            return r
    if p.org_fill_reverse and not synth:
        r = org_reverse_adjust(ctx, sd, sw, i, p, entry, tags)
        if r:
            return r
    if p.lh_org_fill:
        r = lh_org_adjust(ctx, sd, sw, i, p, session, entry, tags)
        if r:
            return r
    if p.pm_am_stops and sw.get("key") == "am_last_high":
        fx = am_stops_fixed(ctx, sd, i, p, entry)
        if fx:
            tags["fixed4"] = fx
    if p.smt_pick == "clean" and not synth:
        tags["gap_count"] = gap_count(sd, sw, i)
        hit("gap_count")
    return None


def entry_adjust(sw, entry: float, top: float, bottom: float, p) -> float:
    """pm_am_stops: the entry of a sweep of the trailed AM stops is the FVG's CE (the source enters at the CE of the post-run range)."""
    if p.pm_am_stops and sw.get("key") == "am_last_high":
        hit("pm_am_stops_ce")
        return float((top + bottom) / 2)
    return entry


def pools4(ctx, sd, i: int, p, session: str, out: dict) -> None:
    """Sell-side pools of this chunk (strategy._sell_side): the last AM swing extreme as the PM pool am_last_high (pm_am_stops)."""
    if p.pm_am_stops and session == "PM":
        v = am_last_pool(ctx, sd, i, p)
        if v is not None:
            out["am_last_high"] = v


def created(ctx, key: str):
    """The bar from which a pool of this chunk exists, else None."""
    if key == "am_last_high":
        return _S()._idx_at(ctx, 720)
    return None


# --- the non-sweep setups (strategy._scan) ---------------------------------------------------------------------------------------------------------------

def any_extra4(p) -> bool:
    return bool(p.dagger_entry or p.lh_old_low_entry or p.pm_old_high_fvg or p.pm_after_draw or p.lh_array_short or p.htf_fvg_top_short or p.sick_entry != "discount")


def extra4(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried when the sweep machine has nothing (strategy._scan)."""
    if p.dagger_entry:
        o = dagger_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.lh_old_low_entry:
        o = lh_old_low_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.lh_array_short:
        o = lh_array_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.pm_old_high_fvg:
        o = pm_old_high_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.pm_after_draw:
        o = pm_after_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.htf_fvg_top_short:
        o = top_short_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.sick_entry == "ob_open":
        o = sick_ob_open_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.sick_entry == "ote_stack":
        o = sick_ote_stack_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


def any_special4(p) -> bool:
    return bool(p.po3_resting or p.lunch_nwog_long)


def special4(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float, done: dict):
    """The setups that run outside the session windows (run_day, like the release setups): the 00:00 resting PO3 order and the experimental lunch-macro NWOG long. Armed on the bar that has
    just closed; each fires at most once a day."""
    if pos is not None or pending is not None or state.get("day_done"):
        return None
    S = _S()
    sent = state.setdefault("sm4_sent", set())
    t = int(ctx.t[i])
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_lock_any, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, None, "", False, 0
        if p.po3_resting and "po3r" not in sent and i == ctx.start and t == 0 and not done.get("PO3R"):
            sent.add("po3r")
            ctx.cur_session = "AM"
            if not (p.day_filter and S.blocked(ctx.day, "AM", p, t)):
                out = po3_rest_order(ctx, sides, i, p, risk_mult)
        if out is None and p.lunch_nwog_long and "lnw" not in sent and 700 <= t < 730 and not done.get("LNW"):
            ctx.cur_session = "LUNCH"
            if not (p.day_filter and S.blocked(ctx.day, "LUNCH", p, t)):
                for sd in sides:
                    ctx.cur_bias = sd.sign
                    out = lunch_nwog_order(ctx, sd, i, p, risk_mult)
                    if out is not None:
                        out["done_key"] = "LNW"
                        sent.add("lnw")
                        break
    finally:
        for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session"):
            if k in saved:
                setattr(ctx, k, saved[k])
            else:
                ctx.__dict__.pop(k, None)
    return out


def room_ok(sd, entry: float, i: int, p) -> bool:
    """The 10-handle room rule (019 ~00:20:53): the nearest untraded gap / void beyond the entry (side space) is at least `pm_after_room_pts` ES pts away; nothing in the way is room enough."""
    opp = [z for z in sd.opposing() if z.i <= i and z.bottom > entry + MIN1 and sd.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
    return (not opp) or (min(z.bottom for z in opp) - entry >= p.pm_after_room_pts * p.es_pt - MIN1)


# --- 54 new-ndog-asian-scalp -----------------------------------------------------------------------------------------------------------------------------

def post_evening(df: pd.DataFrame, d) -> pd.DataFrame:
    """backtest: the bars from 16:00 of day d to midnight (the 17:00 close, the 18:00 reopen and the Asian evening); empty when the data has none."""
    a = pd.Timestamp(d, tz=df.index.tz) + pd.Timedelta(hours=16)
    b = pd.Timestamp(d, tz=df.index.tz) + pd.Timedelta(days=1)
    return df[(df.index >= a) & (df.index < b)]


def ndog_scalp(ctx, ev: pd.DataFrame, p, day, symbol: str, btag: dict) -> list:
    """new-ndog-asian-scalp (052 ~00:08:18): the 18:00 open below the 17:00 close (a gap down) of more than one handle and the NDOG high (the 17:00 close) not yet traded: once price trades at the
    NDOG low (the 18:00 open) and consolidates there, the first 5m bar that closes back above the NDOG low (no 5m close below it before) is a market long (filled at the next open); stop under the
    post-open low; target the NDOG high - exit_before_pts; flat at 24:00. The gap up is the mirror (a short). ICT gives no trigger or stop [our interpretation]. One trade a day, no adds.
    `ev` = the day's bars from 16:00 to midnight; only bars that closed are used, bar by bar."""
    S = _S()
    if ev is None or not len(ev):
        return []
    if p.day_filter and S.blocked(day, "ASIA", p, 1080):
        return []                                                 # review fix: a blocked day (NFP / FOMC / CPI rules) has no evening scalp either
    tt = ev.index.hour * 60 + ev.index.minute
    pre, ev18 = ev[tt < 1020], ev[tt >= 1080]
    if not len(pre) or not len(ev18):
        return []
    c17, o18 = float(pre.close.iloc[-1]), float(ev18.open.iloc[0])
    gap = o18 - c17
    if abs(gap) <= 1.0 * p.es_pt:
        return []
    hit("ndog_eval")
    sgn = 1 if gap < 0 else -1                                    # a gap down -> a long (to the NDOG high); a gap up -> a short
    m = 5
    rows = ev18.resample(f"{m}min", closed="left", label="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    last_base = ev18.index[-1]
    edge = o18                                                    # the NDOG low (gap down) / high (gap up): the 18:00 open
    tgt_px = c17 - sgn * p.exit_before_pts * p.es_pt              # the NDOG high (low) less the exit distance
    touched = False
    trig = None
    low_since = None
    for k, (ts5, r) in enumerate(rows.iterrows()):
        end = ts5 + pd.Timedelta(minutes=m)
        if end > last_base + pd.Timedelta(minutes=ctx.tf):
            break                                                 # a bucket counts only once its last base bar is in
        o_, h_, l_, c_ = (float(r.open), float(r.high), float(r.low), float(r.close))
        low_since = l_ if low_since is None else (min(low_since, l_) if sgn > 0 else max(low_since, h_))
        if sgn > 0:
            if h_ >= c17:
                return []                                         # the NDOG high was traded first: no scalp
            if c_ < edge - MIN1:
                touched = False                                   # a body close under the low: not holding it
                continue
            if touched and c_ > edge + MIN1 and k > 0:
                trig = (k, ts5, end)
                break
            touched = bool(l_ <= edge + 0.25 * p.es_pt)
        else:
            if l_ <= c17:
                return []
            if c_ > edge + MIN1:
                touched = False
                continue
            if touched and c_ < edge - MIN1 and k > 0:
                trig = (k, ts5, end)
                break
            touched = bool(h_ >= edge - 0.25 * p.es_pt)
    if trig is None:
        return []
    k, ts5, end = trig
    after = ev18[ev18.index >= end]
    if not len(after):
        return []
    fill_t = after.index[0]
    fill = float(after.open.iloc[0])
    pre_b = ev18[ev18.index < end]
    stop = (float(pre_b.low.min()) - p.pad) if sgn > 0 else (float(pre_b.high.max()) + p.pad)
    risk = (fill - stop) * sgn
    tgt = tgt_px
    if risk < p.min_risk_pts * p.es_pt or risk > p.max_risk_pts * p.es_pt or (tgt - fill) * sgn < p.min_rr * risk:
        return []
    eq = ctx.equity or 0.0
    shares = S._EN.cap_initial(S._first_units(p, eq, risk, fill, 1.0, 0.0), p) if eq else 0
    if shares < 1:
        return []
    tr = S.Trade(day, symbol, "ASIA", "ndog_scalp", "long" if sgn > 0 else "short", "ndog", False, None, ts5, fill_t, fill, stop, tgt, None, shares, day_type=S.day_type(day), news=S.news(day),
                 weekday=day.weekday(), lv_tags="ndog_scalp", entry_kind="ndog_scalp", **btag)
    tr.entry_risk_pct = round(shares * risk / eq, 5) if eq else None
    tr.peak_risk_pct = tr.entry_risk_pct
    exit_ = None
    for ts, r in after.iterrows():
        o_, h_, l_, c_ = (float(r.open), float(r.high), float(r.low), float(r.close))
        if (sgn > 0 and o_ <= stop) or (sgn < 0 and o_ >= stop):
            exit_ = (ts, o_, shares, "stop_gap")
        elif (sgn > 0 and l_ <= stop) or (sgn < 0 and h_ >= stop):
            exit_ = (ts, stop, shares, "stop")
        elif (sgn > 0 and h_ >= tgt) or (sgn < 0 and l_ <= tgt):
            exit_ = (ts, tgt, shares, "t1")
            tr.final_hit = True
        if exit_ is not None:
            break
    if exit_ is None:
        ts = after.index[-1]
        exit_ = (ts, float(after.close.iloc[-1]), shares, "asia_end")
    tr.exits.append(exit_)
    hit("ndog_scalp")
    return [tr]
