"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models, chunk 7 of 7: the engine glue of its 34 specs - models_setups_entries.md items 200-202, 204, 213, 214, 216-219, 228, 229;
other.md items 2, 3, 12, 13, 15; session_day_week_stops_frequency.md items 2, 3, 4, 7, 8; stops_sizing_scaling_in.md items 16, 43, 46, 47; times_sessions_macros.md items 2, 3, 7, 9, 10, 12, 31, 54.

Same conventions as sm2.py ... sm6.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only
from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar being judged).
Every function sits behind a Params switch of the "caption-gap pass, setups_models #7/7" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS` is sm2's counter
dict (tests: proof that a switch's code path RAN).
"""
from __future__ import annotations

import re
from dataclasses import replace

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2, sm3, sm4, sm5, sm6

HITS = sm2.HITS
hit = sm2.hit
_counted = sm6._counted
_dh = sm6._dh

MIN1 = 1e-9

NDX_SYMS = frozenset({"NQ", "NDX", "QQQ", "MNQ"})
TS_ENTRY_KINDS = ("turtle_soup", "ts_or60", "ts_cc_1h_ob", "ts_cc_limit", "ts_external", "smt_turtle", "prev_pm_turtle", "htf_stab")


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm7", {})


def _want(ctx) -> int:
    return sm2.want(ctx)


def _tol(p) -> float:
    return p.eq_tol_pts * p.es_pt


def _tfs(ctx, sd, m: int):
    """The m-minute bars of the day frame in side space (sm6.tf_groups) or None."""
    return sm6.tf_groups(ctx, sd, m)


def _done_groups(ctx, sd, i: int, m: int):
    """(g, ks): the m-minute bar arrays of today and the group indices that are complete at bar i (and start today)."""
    g = _tfs(ctx, sd, m)
    if g is None:
        return None, np.array([], int)
    first, last, done, *_ = g
    ks = np.flatnonzero(done & (last <= i) & (first >= ctx.start))
    return g, ks


def bias_now(ctx, p, session: str, i: int) -> int:
    """The htf_bias side known at closed bar i (0 = neutral / off)."""
    if p.htf_bias == "off":
        return 0
    return int(_S()._BD.want_at(ctx, p, session, i))


def sess_label(t: int, p) -> str:
    """The session label of a special (window-less) order: the AM family before the AM exit (12:00), the lunch session after it."""
    return "AM" if t < (p.am_exit or 720) else "LUNCH"


# --- OT-D15-default-instrument: the NQ overshoot tolerance ---------------------------------------------------------------------------------------------

def nq_params(p, symbol: str):
    """OT-D15-default-instrument (028 ~00:23:58): NQ / NDX / QQQ over-deliver past levels - the run's sweep_ticks (sweep, intact, SMT, seen filter, SB tag) and mohawk_ticks (stop tolerance) are
    multiplied by `nq_overshoot_mult` on those symbols. Applied once per day by run_day (one replaced Params); other symbols and mult 1.0 keep `p`."""
    m = float(p.nq_overshoot_mult)
    if m == 1.0 or str(symbol).upper() not in NDX_SYMS:
        return p
    hit("nq_overshoot")
    return replace(p, sweep_ticks=p.sweep_ticks * m, mohawk_ticks=p.mohawk_ticks * m, nq_overshoot_mult=1.0)


# --- T3-london-close-counter-trend-scalp / new-london-close-scalp-large-range ------------------------------------------------------------------------

def lc_window(p) -> tuple:
    return tuple(p.lc_fs_win if p.lc_mode == "failure_swing" else p.london_close)


def lc_day(ctx, i: int, p):
    """The London-close precondition from closed bars: (day direction, high, low, adr5) or None. failure_swing (cc09_006 ~00:23:58): London (00:00-05:00) and NY (07:00-10:00) moved the same way and
    the day range (00:00 -> now) >= lc_adr_mult x ADR5; mss (cc09_005 ~00:12:05): the range >= lc_adr_k x ADR5 and the move is one-sided (the day's open lies within lc_oneside of the range from the
    opposite extreme [our interpretation])."""
    S = _S()
    k5, k7, k10 = S._idx_at(ctx, 300), S._idx_at(ctx, 420), S._idx_at(ctx, 600)
    if k10 >= len(ctx.t) or i < k10 - 1 or k5 <= ctx.start + 1 or k7 >= k10:
        return None
    adr = S.adr5(getattr(ctx, "hist", None) or [])
    if not adr:
        return None
    hi, lo = float(ctx.h[ctx.start:i + 1].max()), float(ctx.l[ctx.start:i + 1].min())
    rng = hi - lo
    ln = np.sign(ctx.c[k5 - 1] - ctx.o[ctx.start])
    ny = np.sign(ctx.c[k10 - 1] - ctx.o[k7])
    if p.lc_mode == "failure_swing":
        if not ln or ln != ny or rng < p.lc_adr_mult * adr - MIN1:
            return None
        return int(ln), hi, lo, float(adr)
    if rng < p.lc_adr_k * adr - MIN1 or rng <= 0:
        return None
    op = float(ctx.o[ctx.start])
    d = 1 if (hi - op) > (op - lo) else -1
    if d > 0 and not (op - lo) <= p.lc_oneside * rng + MIN1:
        return None
    if d < 0 and not (hi - op) <= p.lc_oneside * rng + MIN1:
        return None
    return d, hi, lo, float(adr)


@_counted
def lc_order(ctx, sd, i: int, p, risk_mult: float):
    """The London-close counter-trend scalp (`lc_scalp`), side space of the TRADE (against the day's move, so the day is a decline in it with its low LOD). `failure_swing` (200: "a high, a pullback, a
    lower / equal rally"): on the 5m bars a pivot low b (confirmed by the next 5m bar) at or above the day low LOD - tol after a rally of at least 2 x tol; a limit at the open of the last
    down-close 5m candle (side space) up to b (the bearish OB of the real short), stop LOD - lc_stop_pts, single target LOD + lc_retrace x the day range (ICT no longer trades it: it often fails;
    index points are [our interpretation]). `mss` (54): the day's extreme LOD is followed by the normal MSS (a close above the last short-term high before it) and the first FVG of that break:
    a limit at its near edge, stop LOD - pad, the single target entry + lc_retrace_mss x the day range, out by the AM exit (exit_at). Own done key LC. (lc_retrace / lc_retrace_mss are two switches: the two sources give 25 % and 20 %.)"""
    S = _S()
    lo_w, hi_w = lc_window(p)
    t = int(ctx.t[i])
    if not (lo_w <= t < hi_w):
        return None
    dd = lc_day(ctx, i, p)
    if dd is None or sd.sign != -dd[0]:
        return None
    d, hi, lo, adr = dd
    rng = hi - lo
    tol = _tol(p)
    lod = float(sd.l[ctx.start:i + 1].min())
    session = sess_label(t, p)
    sent = sd.__dict__.setdefault("_lc_sent", set())
    if p.lc_mode == "failure_swing":
        g, ks = _done_groups(ctx, sd, i, 5)
        if g is None or len(ks) < 5:
            return None
        first, last, done, o5, h5, l5, c5 = g
        a0, n = int(ks[0]), int(ks[-1]) + 1
        a = a0 + int(np.argmin(l5[a0:n]))
        b = n - 2
        if b <= a + 1 or l5[b] > l5[b - 1] + MIN1 or l5[b] > l5[b + 1] + MIN1 or l5[b] < l5[a] - tol:
            return None
        if float(h5[a:b + 1].max()) - float(l5[b]) < 2 * tol or (a, b) in sent:
            return None
        k = next((q for q in range(b, a, -1) if c5[q] < o5[q]), None)
        if k is None:
            return None
        entry = float(o5[k])
        stop = lod - p.lc_stop_pts * p.es_pt                                 # the DAY extreme (HOD of the real day) + the buffer, as specified
        tgt = float(l5[a]) + p.lc_retrace * rng
        if not (stop < entry < sd.c[i]) or tgt <= entry or entry - stop < p.min_risk_pts * p.es_pt:
            return None
        sent.add((a, b))
        _dh("lc_scalp")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "lc_scalp", entry, stop, level=entry, ext=float(l5[a]), ext_i=int(first[a]), broke=i,
                          fixed=[(float(S._exit_px(tgt, "pool", p)), "pool")], lv=("lc_scalp",), done_key="LC", cut_at=int(hi_w), no_adds=True)
    # mss mode
    e = ctx.start + int(np.argmin(sd.l[ctx.start:i + 1]))
    if e >= i - 1 or ("e", e) in sent:
        return None
    sw = sm4._synth(S, session, "lc_scalp", lod, lod, e, None)
    rr = S._mss_ref(ctx, sd, sw, i, p)
    if rr is None:
        return None
    ref = float(rr[1])
    b = next((q for q in range(e + 1, i + 1) if sd.c[q] > ref), None)
    if b is None:
        return None
    zs = [z for z in sd.gaps if z.i <= i and z.i - 2 >= e and z.i >= b - 1 and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1 and ("g", z.i) not in sent]
    if not zs:
        return None
    z = zs[0]
    entry, stop = float(z.top), lod - p.pad
    tgt = entry + p.lc_retrace_mss * rng
    if not (stop < entry < sd.c[i]) or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    sent.add(("e", e))
    sent.add(("g", z.i))
    _dh("lc_scalp")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "lc_scalp", entry, stop, level=entry, ext=lod, ext_i=e, broke=b, fvg_bottom=float(z.bottom), fvg_ce=float(z.mid),
                      fixed=[(float(S._exit_px(tgt, "pool", p)), "pool")], lv=("lc_scalp", "lc_mss"), done_key="LC", cut_at=int(hi_w), no_adds=True,
                      exit_at=(int(p.am_exit) if p.am_exit else None))          # mss: out by the AM exit (a forced time exit, not only the order cut)


# --- E5-missed-entry-5m-retrace ---------------------------------------------------------------------------------------------------------------------

def note_sweep(ctx, sd, sw, ref: float, i: int) -> None:
    """`missed_5m`: remember the live sweep (by reference: its `broke` is set later) and the MSS reference swing it needs to break."""
    _c(ctx).setdefault("m5", {})[sd.sign] = (sw, float(ref))


@_counted
def missed_order(ctx, sd, i: int, p, session: str, risk_mult: float, extra=None):
    """E5-missed-entry-5m-retrace (cc09_006 ~00:17:03; cc09_007 ~00:21:11): the session's sweep fired and broke its MSS reference, NO order of the session filled (and none rests) and price left (the
    close more than missed_leave_pts above the broken reference): ONE more order, a limit at the near edge of the first 5m same-side FVG (else 5m OB) formed by the move (after the sweep extreme, still
    alive), ignoring po3_inclusive / the open-side gate (the synthetic order skips the PO3 filter). Stop under the zone; target the ADR5 extreme (the sweep extreme + ADR5) or the first 60m / 4h opposing array above the entry
    (Confluence), whichever is nearer; only inside a kill zone (missed_kz_ok); with the ADR5 extreme as the target 80 % leave there and the rest runs [our interpretation of 'leave a runner': a quarter
    of an ADR5 further] ONLY when the ADR5 extreme is hit before 10:00 (manage: runner_before) - hit later, the rest goes out with it."""
    S = _S()
    st = _c(ctx).get("m5", {}).get(sd.sign)
    if st is None or getattr(ctx, "pend_now", None) is not None or getattr(ctx, "done_ref", {}).get(session):
        return None
    sw, ref = st
    if sw.get("broke") is None or sw.get("session") != session or sw.get("_m5_sent") or sw["ext_i"] >= i:
        return None
    if not missed_kz_ok(ctx, int(ctx.t[i]), p):
        return None
    if not sd.c[i] > ref + p.missed_leave_pts * p.es_pt:
        return None
    adr = S.adr5(getattr(ctx, "hist", None) or [])
    if not adr:
        return None
    zs = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 5) if z.i <= i and z.src > sw["ext_i"] - 1 and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1 and z.top < sd.c[i]]
    if not zs:
        return None
    fv = [z for z in zs if z.mt != z.mt]
    z = min(fv or zs, key=lambda z_: z_.i)                       # the FIRST same-side 5m zone formed by the move (FVG before OB)
    entry, stop = float(z.top), float(z.bottom) - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        return None
    tgt = float(sw["ext"]) + adr
    tgt2, cand = tgt, [tgt]
    cf = getattr(ctx, "conf", None)
    if cf is not None:                                           # review fix: the first 60m / 4h premium (opposing) array above the entry, from the Confluence object (real prices -> side space)
        for near, ce, far, tf_, src in cf.opposing(sm2.now_ts(ctx, i), sd.x(entry), sd.sign, ("1h", "4h"), (0,))[:1]:
            v = float(sd.x(near))
            if v > entry + p.min_rr * (entry - stop):
                cand.append(v)
                hit("missed_htf_target")
    tgt2 = min(cand)
    tags = {}
    fixed = [(float(S._exit_px(tgt2, "pool", p)), "pool")]
    sm7 = {}
    if tgt2 >= tgt - MIN1:                                       # the ADR5 extreme is the target: 80 % there, a quarter-ADR5 runner [our interpretation of 'leave a runner'] - kept only when it is hit before 10:00 (manage)
        fixed = [(fixed[0][0], "pool"), (float(S._exit_px(tgt + 0.25 * adr, "pool", p)), "pool")]
        tags["fracs"] = (0.8, 0.2)
        sm7["runner_before"] = 600
    sw["_m5_sent"] = True
    if session == "LON":
        hit("missed_5m_lon")
    _dh("missed_5m")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "missed_5m", entry, stop, level=entry, ext=float(sw["ext"]), ext_i=int(sw["ext_i"]), broke=i,
                      fvg_bottom=float(z.bottom), fvg_ce=float(z.mid), fixed=fixed, lv=("missed_5m",), **({"sm7": sm7} if sm7 else {}), **tags, **(extra or {}))


def missed_kz_ok(ctx, t: int, p) -> bool:
    """missed_5m runs inside a kill zone only (cc09_006 ~00:17:03): the NY kill zone `missed_kz` (default the futures NY zone 08:20-11:00, as ny_kz_futures), and with `missed_lon` the London lunch
    05:00-07:00 when London was quiet early and active late [our interpretation: the first half (02:00-03:30) range <= missed_lon_ratio x the second half (03:30-05:00) range]."""
    if any(a <= t < b for a, b in p.missed_kz):
        return True
    if p.missed_lon and 300 <= t < 420:
        S = _S()
        k2, k35, k5 = S._idx_at(ctx, 120), S._idx_at(ctx, 210), S._idx_at(ctx, 300)
        if k5 - k35 < 2 or k35 - k2 < 2 or k5 >= len(ctx.t):
            return False
        r1 = float(ctx.h[k2:k35].max() - ctx.l[k2:k35].min())
        r2 = float(ctx.h[k35:k5].max() - ctx.l[k35:k5].min())
        if r2 > 0 and r1 <= p.missed_lon_ratio * r2 + MIN1:
            hit("missed_lon")
            return True
    return False


# --- resting-limit pullbacks: or_ref (213), am_array_open (214), lh_ob_pullback (T10) --------------------------------------------------------------------

def _near(p) -> float:
    return p.or_ref_near_pts * p.es_pt


def or_ref_arrays(ctx, sd, i: int, p) -> list:
    """new-or-reference-arrays-reused (cc10_010 ~00:07:38), recorded once the OR60 (09:30-10:30) is complete, side space: `pre` = the last down-close candle (side space) of today's bars before 09:30
    (the real bearish OB 'just before 09:30' for a short), `rb` = the rejection block (longs: the lowest-close down-close candle inside the OR; shorts: the last up-close candle, i.e. the last
    side-space down-close candle), `ob` = the last down-close candle inside the OR. [{name, k, top (the body top), low (the candle low), or_lo}]"""
    S = _S()
    k5, k6 = S._idx_at(ctx, 570), S._idx_at(ctx, 630)
    if k6 >= len(ctx.t) or i < k6 - 1:
        return []
    c = _c(ctx).setdefault("orr", {})
    if sd.sign not in c:
        arr = []
        dn = [k for k in range(k5, k6) if sd.c[k] < sd.o[k]]
        or_lo = float(sd.l[k5:k6].min())
        pre = [k for k in range(ctx.start, k5) if sd.c[k] < sd.o[k]]
        if pre:
            arr.append(("pre", pre[-1]))
        if dn:
            arr.append(("ob", dn[-1]))
            rb = min(dn, key=lambda k: sd.c[k]) if sd.sign > 0 else dn[-1]
            if rb != dn[-1]:
                arr.append(("rb", rb))
        c[sd.sign] = [dict(name=n_, k=int(k), top=float(sd.o[k]), low=float(sd.l[k]), or_lo=or_lo) for n_, k in arr]
    return c[sd.sign]


@_counted
def or_ref_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """entry_arrays "or_ref" (cc10_010 ~00:07:38): after 10:30 a RETURN to an OR60 reference array in the bias direction (the bar's low within or_ref_near_pts of its body top, the close still above it)
    arms a limit at the body top; stop beyond the OR extreme / the candle low; the engine's ladder is the target [our interpretation: ICT gives none]. The array is reusable - at most or_ref_reuse
    returns, each after price left it by twice the near distance - until a body closes through its low."""
    if "or_ref" not in p.entry_arrays or _want(ctx) != sd.sign or session not in ("AM", "PM"):
        return None
    S = _S()
    k6 = S._idx_at(ctx, 630)
    use = _c(ctx).setdefault("orr_use", {})
    near = _near(p)
    for a in or_ref_arrays(ctx, sd, i, p):
        if sd.c[a["k"] + 1:i + 1].min(initial=np.inf) < a["low"] - MIN1:
            continue                                            # review fix: a body closed through the array at any time since its candle (inside the OR too), not only after 10:30
        key = (sd.sign, a["name"])
        n_, last = use.get(key, (0, None))
        if n_ >= p.or_ref_reuse or not (sd.c[i] > a["top"] + MIN1 and sd.l[i] <= a["top"] + near + MIN1):
            continue
        if last is not None and float(sd.h[last + 1:i + 1].max(initial=-np.inf)) < a["top"] + 2 * near:
            continue
        entry, stop = a["top"], min(a["low"], a["or_lo"]) - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        use[key] = (n_ + 1, i)
        _dh("or_ref")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "or_ref", entry, stop, level=entry, ext=float(a["low"]), ext_i=a["k"], broke=i, lv=("or_ref", "or_ref_" + a["name"]))
    return None


@_counted
def am_open_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-am-trend-definition-and-start (cc10_011 ~00:01:08), side space: 09:30-10:30, the bias this way, a first touch of a pre-09:30 same-side array - a London (02:00-05:00) 5m / 15m FVG still
    alive or the last down-close candle (side space) before 09:30 - arms a limit at its near edge (the top / the body top) without an MSS: the AM swing starts at the array. Stop under the array
    (the candle low), the engine's ladder = the buy-side by noon [our interpretation]. One AM trade (the session slot)."""
    if not p.am_array_open or session != "AM" or _want(ctx) != sd.sign:
        return None
    S = _S()
    k5, k6, kl0, kl1 = S._idx_at(ctx, 570), S._idx_at(ctx, 630), S._idx_at(ctx, 120), S._idx_at(ctx, 300)
    if not (k5 <= i < k6):
        return None
    sent = sd.__dict__.setdefault("_amo_sent", set())
    near = _near(p)
    arrs = []
    for m in (5, 15):
        for z in sd.zones_tf(ctx.idx, ctx.tf, m):
            if z.mt != z.mt and kl0 <= z.src < kl1 and z.i < k5:
                arrs.append((float(z.top), float(z.bottom), "london_fvg%d" % m, z.i))
    pre = [k for k in range(ctx.start, k5) if sd.c[k] < sd.o[k]]
    if pre:
        arrs.append((float(sd.o[pre[-1]]), float(sd.l[pre[-1]]), "pre_ob", pre[-1]))
    for top, bot, name, k in arrs:
        key = (name, round(top, 4))
        if key in sent or sd.c[k + 1:i + 1].min(initial=np.inf) < bot - MIN1:
            continue                                    # review fix: a body closed through the array at any time since it formed kills it (not only since 09:30)
        t0 = k + 1 if name.startswith("london") else k5
        if sd.l[t0:i].min(initial=np.inf) <= top + MIN1 or not (sd.c[i] > top + MIN1 and sd.l[i] <= top + near + MIN1):
            continue                                    # a FIRST touch only: nothing traded into the array since it formed (the London FVG; the last pre-09:30 candle: since 09:30) before this approach
        entry, stop = top, bot - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(key)
        _dh("am_array_open")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "am_open", entry, stop, level=entry, ext=bot, ext_i=int(k), broke=i, fvg_bottom=bot, lv=("am_open", name))
    return None


@_counted
def lh_ob_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """T10-lasthour-ob-pullback (012 ~00:14:52), side space: the last hour (p.last_hour, 15:00-15:50), the bias this way, the HTF objective of this side not done: after the PM high the last
    down-close candle before it is the OB; a pullback toward it (the bar's low within or_ref_near_pts of its open, the close above) arms a limit at its OPEN, stop under its low; the target is the engine's
    ladder (the nearest untaken buy-side pools / the daily draw). No sweep needed (unlike M5). Once per OB; a single example - tagged lh_ob, not a core rule."""
    S = _S()
    t = int(ctx.t[i])
    if not p.lh_ob_pullback or session != "PM" or not (p.last_hour[0] <= t < p.last_hour[1]) or _want(ctx) != sd.sign or S._SM.htf_done(ctx, sd, i):
        return None
    k810 = S._idx_at(ctx, 810)
    if k810 >= i:
        return None
    e = k810 + int(np.argmax(sd.h[k810:i + 1]))
    q = next((k for k in range(e, max(ctx.start, e - 36) - 1, -1) if sd.c[k] < sd.o[k]), None)
    if q is None:
        return None
    sent = sd.__dict__.setdefault("_lhob_sent", set())
    entry, stop = float(sd.o[q]), float(sd.l[q]) - p.pad
    if q in sent or not (sd.c[i] > entry + MIN1 and sd.l[i] <= entry + _near(p) + MIN1) or entry - stop < p.min_risk_pts * p.es_pt:
        return None
    if sd.c[q + 1:i + 1].min(initial=np.inf) < stop:
        return None
    sent.add(q)
    _dh("lh_ob_pullback")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "lh_ob", entry, stop, level=entry, ext=float(sd.l[q]), ext_i=int(q), broke=i, lv=("lh_ob",))


# --- T7-0950-reversal-or-continuation ---------------------------------------------------------------------------------------------------------------

def rev_pool_run(ctx, sd, i: int, p):
    """Branch A of the 09:50-10:10 macro (043 ~00:05:31; 073 ~00:25:56), side space: a pool of this side (OR20, the London / previous-PM lows, relative equal lows known before the window) traded one tick
    through inside 09:50-10:10 AND a premium FVG of the reversal was rebalanced (REAL prices: after a buy-side run a bearish FVG above the real 09:30-now EQ, after a sell-side run a bullish FVG below it; a body closed inside it and the next
    bar left it the reversal way [our interpretation]). Returns {ext, i (the run bar), pool, tgt (the 09:30-09:50 extreme, side space)} or None; cached per bar."""
    S = _S()
    k0, k1 = S._idx_at(ctx, 590), S._idx_at(ctx, 610)
    if k0 >= len(ctx.t) or i < k0:
        return None
    cc = _c(ctx).setdefault("m0950", {})
    key = (sd.sign, i)
    if key in cc:
        return cc[key]
    res = None
    tk = S._tick(p)
    pools = []
    if ctx.or20 is not None:
        pools.append(("or20", float(sd.x(ctx.or20[1] if sd.sign > 0 else ctx.or20[0]))))
    for nm in ("london", "prev_pm"):
        v = ctx.sess.get(nm)
        if v is not None:
            pools.append((nm, float(sd.x(v[1] if sd.sign > 0 else v[0]))))
    pools += [("rel_eq", float(v)) for v in S._eq_levels(sd, k0 - 1, _tol(p), lows=True, p=p)]
    hi_k = min(i, k1 - 1)
    for nm, v in pools:
        if nm != "or20" and sd.l[ctx.start:k0].min(initial=np.inf) < v - MIN1:
            continue
        run = next((k for k in range(k0, hi_k + 1) if sd.l[k] < v - tk + MIN1), None)
        if run is None:
            continue
        a = S._idx_at(ctx, 570)
        # review fix (times#2): premium / discount in REAL prices. A buy-side run (side space of the short reversal: a taken LOW) pairs with a REAL bearish FVG above the real 09:30-now EQ
        # (rebalanced = a body closed in it, the next bar left it the reversal way); a sell-side run with a real bullish FVG below it. In side space both mirror to the same test: a side-space
        # BULLISH gap (sd.gaps) whose CE lies at or under the side-space EQ of the 09:30-now range.
        eq = (float(sd.h[a:i + 1].max()) + float(sd.l[a:i + 1].min())) / 2
        for z in sd.gaps:
            if z.i <= i and z.i >= a and (z.top + z.bottom) / 2 <= eq + MIN1:
                q = next((q for q in range(z.i + 1, i) if z.bottom - MIN1 <= sd.c[q] <= z.top + MIN1 and sd.c[q + 1] > z.top + MIN1), None)
                if q is not None:
                    res = dict(ext=float(sd.l[run:i + 1].min()), i=int(run), pool=nm, tgt=float(sd.h[a:k0].max()))      # tgt: the 09:30-09:50 extreme the reversal runs toward (side space)
                    break
        if res is not None:
            break
    cc[key] = res
    return res


def counter_kind7(ctx, sd, i: int, p, w_: int) -> str:
    """The counter-bias reason of this chunk that lets a side be scanned against the bias `w_`: "m0950" (the 09:50 reversal macro on an NFP / jobs day, branch rev / both - 073 ~00:25:56), "lod" (X14
    allow_opposite_after_target: a counter short into a predefined low-of-day level), "" (none)."""
    S = _S()
    if p.m0950_branch in ("rev", "both") and sd.sign != w_ and "jobs" in S.events(ctx.day) and rev_pool_run(ctx, sd, i, p) is not None:
        hit("m0950_rev")
        return "m0950"
    if p.allow_opposite_after_target in ("lod", "both") and sd.sign != w_ and lod_level(ctx, sd, i, p) is not None:
        return "lod"
    return ""


@_counted
def m0950_cont_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """Branch B (015 ~00:27:13): 09:50-10:10, no opposing pool run, price consolidates and leaves an FVG in the bias direction (formed inside the window): a limit at its near edge (top) as a
    continuation entry, stop under the gap [our interpretation]; the engine's ladder = the next draw."""
    if p.m0950_branch not in ("cont", "both") or session != "AM" or _want(ctx) != sd.sign:
        return None
    S = _S()
    k0, k1 = S._idx_at(ctx, 590), S._idx_at(ctx, 610)
    if not (k0 <= i < k1 + 1):
        return None
    other = getattr(ctx, "sides_map", {}).get(-sd.sign)
    if other is not None and rev_pool_run(ctx, other, i, p) is not None:
        return None
    sent = sd.__dict__.setdefault("_m0950_sent", set())
    for g in sd.gaps:
        if g.i <= i and k0 <= g.i < k1 and g.i not in sent and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1 and g.top < sd.c[i]:
            entry, stop = float(g.top), float(g.bottom) - p.pad
            if entry - stop < p.min_risk_pts * p.es_pt:
                continue
            sent.add(g.i)
            _dh("m0950_cont")
            return sm4._order(ctx, sd, i, p, session, risk_mult, "m0950_cont", entry, stop, level=entry, ext=float(g.bottom), ext_i=int(g.src), broke=i, fvg_bottom=float(g.bottom),
                              fvg_ce=float(g.mid), lv=("m0950_cont",))
    return None


# --- T7-1050-macro-setup ------------------------------------------------------------------------------------------------------------------------------

@_counted
def m1050_order(ctx, sd, i: int, p, risk_mult: float):
    """T7-1050-macro-setup (022 ~03:09:01, ~03:10:40), any day type, side space: 10:50-11:10 - a short-term low (STL pivot formed today) swept one tick inside the window, then an MSS (a close above the
    short-term high that preceded the sweep) inside the window: a limit at the near edge (top) of the FIRST VI / FVG of the break, stop under the sweep extreme - pad; the target = the nearest
    untapped pool (the engine's ladder). Cancelled at 11:10 (m1050_cut). Own done key M1050. The macro extreme is stored as protected (protect_macro_ext)."""
    S = _S()
    k0, k1, k5 = S._idx_at(ctx, 650), S._idx_at(ctx, 670), S._idx_at(ctx, 570)
    if not p.m1050 or k0 >= len(ctx.t) or not (k0 <= i < k1 + 1) or int(ctx.t[i]) >= 670 + ctx.tf:
        return None
    tk = S._tick(p)
    sent = sd.__dict__.setdefault("_m1050_sent", set())
    for q in reversed([q for q in sd.pl if k5 <= q.i < k0 + 1 and q.known <= i and q.i not in sent]):
        k = next((k for k in range(k0, i + 1) if k > q.known and sd.l[k] <= q.price - tk + MIN1 and sd.l[q.known:k].min(initial=np.inf) > q.price - tk), None)
        if k is None:
            continue
        hs = [h for h in sd.ph if h.i < k and h.known <= i]
        if not hs:
            continue
        ref = float(hs[-1].price)
        b = next((x for x in range(k, i + 1) if sd.c[x] > ref and int(ctx.t[x]) < 670), None)
        if b is None:
            continue
        ext_i = k + int(np.argmin(sd.l[k:b + 1]))
        ext = float(sd.l[ext_i])
        zs = [z for z in sd.gaps + [z for z in sd.vis("bull")] if ext_i <= z.i <= i and z.i - 2 >= ext_i - 1 and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1 and z.top < sd.c[i] + MIN1]
        if not zs:
            continue
        z = min(zs, key=lambda z_: z_.i)
        entry, stop = float(z.top), ext - p.pad
        if p.stop_mode == "ob_mt":
            ob = S._ob_at_low(sd, dict(ext=ext, ext_i=ext_i), i, p, ctx)
            if ob is not None and ob["mt"] < entry - p.min_risk_pts * p.es_pt:
                stop = min(stop, float(ob["mt"]) - p.pad)
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(q.i)
        _c(ctx).setdefault("protected", {})[sd.sign] = ext
        _dh("m1050")
        kw = dict(cut_at=670 if p.m1050_cut else int(p.am_exit or 720))        # cancelled at 11:10 (m1050_cut) - else it lives to the AM exit (the usual order lifetime applies)
        return sm4._order(ctx, sd, i, p, "AM", risk_mult, "m1050", entry, stop, level=entry, ext=ext, ext_i=ext_i, broke=b, fvg_bottom=float(z.bottom), fvg_ce=float((z.top + z.bottom) / 2),
                          lv=("m1050",), done_key="M1050", **kw)
    return None


def protected_stop(ctx, sd, entry: float, stop: float, p) -> float:
    """protect_macro_ext: a later same-side stop sits just beyond the stored macro extreme (the protected level of the day)."""
    pr = _c(ctx).get("protected", {}).get(sd.sign)
    if pr is None or not p.protect_macro_ext or not entry > pr:
        return stop
    if stop > pr - p.pad:
        hit("protect_macro_ext")
        return pr - p.pad
    return stop


# --- T7-lasthour-after-target / T10-lasthour-consolidation-direction ------------------------------------------------------------------------------------

def lh_after(ctx, i: int, p):
    """T7-lasthour-after-target (059 ~00:23:13): the last hour after a day whose objective was delivered before noon. All of: the AM direction (09:30 -> 12:00) delivered its objective before 12:00 (a
    session lock of that side delivered / the htf-table draw that way traded); an MSS AGAINST the AM move formed after 12:00 (the reversal side closed above the first short-term high that formed
    after the AM extreme); an opposite-side inefficiency is still unfilled - today's ORG ahead of the open (its far edge never reached) or an untouched opposing FVG. Returns {sign (the reversal
    side), levels (real prices of the reversal side's targets: the ORG near edge / CE / far edge, else the FVG near edge / CE)} or None; the LH slot then does NOT skip (lh_htf_done_skip / lock
    delivered) and trades the reversal direction only."""
    S = _S()
    t = int(ctx.t[i])
    if not p.lh_after_target or not (p.last_hour[0] <= t < p.last_hour[1]):
        return None
    k5, k720 = S._idx_at(ctx, 570), S._idx_at(ctx, 720)
    if k720 >= len(ctx.t) or i < k720 + 2 or k5 >= k720:
        return None
    d = int(np.sign(ctx.c[k720 - 1] - ctx.o[k5]))
    if not d:
        return None
    done = any(lk.get("side") == d and lk.get("delivered_i") is not None and lk["delivered_i"] < k720 for lk in getattr(ctx, "lock", {}).values()) or S._SM.htf_done_sign(ctx, d, k720 - 1)
    if not done:
        return None
    sm = getattr(ctx, "sides_map", None) or {}
    sdr = sm.get(-d)
    if sdr is None:
        return None
    e = k5 + int(np.argmin(sdr.l[k5:k720]))
    qs = [q for q in sdr.ph if q.i > e and q.known <= i]
    if not qs:
        return None
    q = qs[0]
    j = next((x for x in range(max(k720, q.known), i + 1) if sdr.c[x] > q.price), None)
    if j is None:
        return None
    lv = None
    if getattr(ctx, "org_today", False) and ctx.org:
        pc, op = ctx.org[-1]
        pcx, opx = float(sdr.x(pc)), float(sdr.x(op))
        if pcx > opx + MIN1 and float(sdr.h[k5:i + 1].max()) < pcx - MIN1:
            lv = [opx, (opx + pcx) / 2, pcx]
    if lv is None:
        zs = [z for z in sdr.opposing() if z.i <= i and z.i < k720 and z.bottom > sdr.c[i] and sdr.h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom]
        if zs:
            z = min(zs, key=lambda z_: z_.bottom)
            lv = [float(z.bottom), float(z.mid)]
    if lv is None:
        return None
    hit("lh_after_target")
    return dict(sign=-d, levels=[float(x) for x in lv])


def lh_after_open(ctx, i: int, p) -> bool:
    """run_day: the LH slot may trade on although the session's draw is delivered (like lh_org_open)."""
    return p.lh_after_target and lh_after(ctx, i, p) is not None


def lh_after_pass(ctx, sd, i: int, p) -> bool:
    """setups.finish_gates: the htf_done skip of the last hour does not apply to the reversal side of lh_after_target."""
    if not p.lh_after_target:
        return False
    r = lh_after(ctx, i, p)
    return r is not None and r["sign"] == sd.sign


def moc_block(ctx, sd, i: int, p):
    """T10-lasthour-consolidation-direction (032 ~00:59:56), 15:00-16:00 orders. `moc_range_dir`: a range-bound day (an inside day / big-previous-day / chop) whose previous-day boundary was tested 2+
    times (pivots within 2 x eq_tol of it, no body close beyond it) trapped the traders on that side: only the other direction trades the close (a boundary tested twice from below = shorts, from above =
    longs [our interpretation of 'tried repeatedly']). `moc_no_chase_hod`: a big bull day (range >= ADR5, close in the top quarter) whose HOD printed before 15:00 on a non-trend day: no new longs (the
    bear mirror blocks shorts). Returns a reject key or None."""
    S = _S()
    t = int(ctx.t[i])
    if not (p.last_hour[0] <= t < 960) or not (p.moc_range_dir or p.moc_no_chase_hod):
        return None
    sm = getattr(ctx, "sides_map", None) or {}
    bull = sm.get(1)
    hist = getattr(ctx, "hist", None) or []
    k5 = S._idx_at(ctx, 570)
    if p.moc_range_dir and bull is not None and hist and k5 < i:
        dtags = set(str(getattr(ctx, "day_tags", "")).split("|"))
        chop = getattr(ctx, "chop", None)
        if "inside_day" in dtags or "big_prev" in dtags or (chop is not None and chop.on):
            pdh, pdl = float(hist[-1].high.max()), float(hist[-1].low.min())
            tol2 = 2 * _tol(p)
            up_ok = float(ctx.c[k5:i + 1].max()) <= pdh + MIN1
            dn_ok = float(ctx.c[k5:i + 1].min()) >= pdl - MIN1
            n_up = sum(1 for q in bull.ph if q.i >= k5 and q.known <= i and q.price >= pdh - tol2) if up_ok else 0
            n_dn = sum(1 for q in bull.pl if q.i >= k5 and q.known <= i and q.price <= pdl + tol2) if dn_ok else 0
            hit("moc_range_eval")
            allow = 1 if (n_dn >= 2 and n_up < 2) else -1 if (n_up >= 2 and n_dn < 2) else 0
            if allow:
                hit("moc_range_dir")
                if sd.sign != allow:
                    return "x_moc_range_dir"
    if p.moc_no_chase_hod and k5 < i:
        adr = S.adr5(hist)
        hi, lo = float(ctx.h[ctx.start:i + 1].max()), float(ctx.l[ctx.start:i + 1].min())
        if adr and hi - lo >= adr - MIN1 and hi > lo:
            ihi, ilo = ctx.start + int(np.argmax(ctx.h[ctx.start:i + 1])), ctx.start + int(np.argmin(ctx.l[ctx.start:i + 1]))
            top_q = ctx.c[i] >= lo + 0.75 * (hi - lo) - MIN1
            bot_q = ctx.c[i] <= lo + 0.25 * (hi - lo) + MIN1
            hit("moc_no_chase")
            if sd.sign > 0 and top_q and ctx.t[ihi] < 900 and not sm4.trend_day(ctx, sd, i, p):
                return "x_moc_no_chase_hod"
            if sd.sign < 0 and bot_q and ctx.t[ilo] < 900 and not sm4.trend_day(ctx, sd, i, p):
                return "x_moc_no_chase_lod"
    return None


# --- T7-lunch-macro-htf-program / T8-lunch-entries-switch (the helper of item 13) --------------------------------------------------------------------

def _lunch_ctx(ctx, sd, i: int, p):
    """(late-AM sell-side taken between 11:00 and 11:50, the REH / buy-side resting above) in side space, or None. The pool: a short-term low (STL pivot formed after 09:30, known before 11:00)
    traded one tick through inside 660-710; the REH: the nearest untouched relative equal highs above the close, else the AM high (09:30-11:00) when untouched."""
    S = _S()
    k5, k660, k710 = S._idx_at(ctx, 570), S._idx_at(ctx, 660), S._idx_at(ctx, 710)
    if k710 >= len(ctx.t) or i < k710 - 1 or k660 <= k5:
        return None
    tk = S._tick(p)
    pools = [q for q in sd.pl if k5 <= q.i < k660 and q.known < k660]
    took = [q for q in pools if sd.l[k660:min(i, k710 - 1) + 1].min(initial=np.inf) <= q.price - tk + MIN1 and sd.l[q.known:k660].min(initial=np.inf) > q.price - tk]
    if not took:
        return None
    px = float(sd.c[i])
    cand = [float(v) for v in S._eq_levels(sd, i, _tol(p), lows=False, p=p) if v > px]
    am_hi = float(sd.h[k5:k660].max())
    if am_hi > px and sd.h[k660:i + 1].max(initial=-np.inf) < am_hi:
        cand.append(am_hi)
    if not cand:
        return None
    return took[-1], min(cand)


def lunch_program(ctx, sd, i: int, p, session: str, entry: float, tags: dict):
    """lunch_htf_program (070 ~00:31:06): inside the lunch macro (11:50-12:10, to 12:30 with lunch_macro_win) and after a late-AM pullback that took a sell-side pool with the REH above: expect the run
    into that buy-side. HTF program (the bias) this way: the setup is a long with the first rung just above the REH (REH + exit_before_pts) and the runner to the HTF draw (the htf-table draw); the
    bias the other way: no long, a short only after the REH traded one tick through (the raid) - the normal model then forms the MSS down. Returns a reject key or None."""
    S = _S()
    t = int(ctx.t[i])
    if not p.lunch_htf_program or not (p.lunch_macro_win[0] <= t < p.lunch_macro_win[1] + 20):
        return None
    w = bias_now(ctx, p, "AM", i)
    if not w:
        return None                                              # the rule reads the HTF program: neutral = silent
    r = _lunch_ctx(ctx, sd, i, p)
    if r is not None:
        reh = r[1]
        hit("lunch_program")
        if w != sd.sign:
            return "x_lunch_program_against"                     # the HTF program is the other way: no entry that runs the buy-side
        if not p.lunch_long_win[0] <= t < p.lunch_long_win[1]:
            return "x_lunch_program_window"                      # review fix: the program's long is armed 710-730 (the macro itself), not in its 12:10-12:30 extension
        first = reh + p.exit_before_pts * p.es_pt
        lv = [(float(S._exit_px(first, "pool", p)), "pool")]
        row = getattr(ctx, "bias_row", None) or {}
        dv = row.get("draw_up" if sd.sign > 0 else "draw_dn")
        if dv is not None and dv == dv:
            dx = float(sd.x(float(dv)))
            if dx > first + p.es_pt:
                lv.append((dx, "array"))
        if lv[0][0] > entry + MIN1:
            tags["fixed4"] = lv
            if len(lv) > 1:
                tags["fracs"] = (0.5, 0.5)
        return None
    other = (getattr(ctx, "sides_map", None) or {}).get(-sd.sign)
    r2 = _lunch_ctx(ctx, other, i, p) if other is not None else None
    if r2 is not None:                                           # this side is the counter: it waits for the raid of the REH, then the normal model's MSS
        hit("lunch_program_raid")
        if not float(other.h[S._idx_at(ctx, 660):i + 1].max()) >= r2[1] + S._tick(p) - MIN1:
            return "x_lunch_program_raid_first"
    return None


@_counted
def lunch_macro_order(ctx, sd, i: int, p, risk_mult: float):
    """T8-lunch-entries-switch (046 ~00:32:10; 080 ~00:12:39; 081 ~00:15:28), side space, in the lunch-macro window (lunch_macro_win, 11:50-12:30). Case A (the AM move this way, the continuation
    from a retrace): a 5m / 15m FVG formed after 11:00, still alive, the close above its top: a limit at its near edge (top), stop under the gap and any overshoot wick of its candles. Case B (the
    AM draw unfinished, buy-side still above): the sell-side run under a short-term low of the late AM into the low of an untouched 15m FVG: a limit at that low, stop under it. One rung only
    (lunch_first_rung_only: a single exit at the nearest pool). The full LUNCH session of the spec (5m / 15m arrays only) belongs to the news_calendar_times owner."""
    S = _S()
    t = int(ctx.t[i])
    if not p.lunch_macro_entry or not (p.lunch_macro_win[0] <= t < p.lunch_macro_win[1]):
        return None
    k5, k660, k710 = S._idx_at(ctx, 570), S._idx_at(ctx, 660), S._idx_at(ctx, 710)
    if k710 >= len(ctx.t) or i < k710 - 1:
        return None
    sent = sd.__dict__.setdefault("_lm_sent", set())
    near = _near(p)
    am_move = float(sd.c[k710 - 1] - sd.o[k5])
    tags = dict(single_exit=True) if p.lunch_first_rung_only else {}
    zs = []
    for m in (5, 15):
        zs += [z for z in sd.zones_tf(ctx.idx, ctx.tf, m) if z.mt != z.mt and z.i <= i and z.src >= k660 and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
    if am_move > 0:                                               # case A
        for z in sorted(zs, key=lambda z_: -z_.i):
            key = ("a", z.i, round(float(z.top), 4))
            if key in sent or not (sd.c[i] > z.top + MIN1 and sd.l[i] <= z.top + near + MIN1):
                continue
            wick = float(sd.l[max(ctx.start, z.src - 1):z.src + 2].min())
            entry, stop = float(z.top), min(float(z.bottom), wick) - p.pad
            if entry - stop < p.min_risk_pts * p.es_pt:
                continue
            sent.add(key)
            _dh("lunch_macro")
            return sm4._order(ctx, sd, i, p, "LUNCH", risk_mult, "lunch_macro", entry, stop, level=entry, ext=float(z.bottom), ext_i=int(z.src), broke=i, fvg_bottom=float(z.bottom),
                              fvg_ce=float(z.mid), lv=("lunch_macro", "lunch_a"), done_key="LUNCHM", cut_at=int(p.lunch_macro_win[1]), **tags)
    if S._SM.htf_done(ctx, sd, i):
        return None
    q15 = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 15) if z.mt != z.mt and z.i <= i and z.i < k710 and sd.l[z.i + 1:i + 1].min(initial=np.inf) > z.bottom + MIN1]
    lows = [q for q in sd.pl if k5 <= q.i < k710 and q.known <= i and sd.l[max(q.known, k660):i + 1].min(initial=np.inf) < q.price - S._tick(p)]
    if lows and q15:                                              # case B
        z = min(q15, key=lambda z_: abs(float(z_.bottom) - float(sd.c[i])))
        key = ("b", z.i, round(float(z.bottom), 4))
        entry = float(z.bottom)
        stop = entry - max(p.pad, p.min_risk_pts * p.es_pt)
        if key not in sent and entry < sd.c[i] - MIN1:
            sent.add(key)
            _dh("lunch_macro")
            return sm4._order(ctx, sd, i, p, "LUNCH", risk_mult, "lunch_macro", entry, stop, level=entry, ext=entry, ext_i=int(z.src), broke=i, fvg_bottom=entry, fvg_ce=float(z.mid),
                              lv=("lunch_macro", "lunch_b"), done_key="LUNCHM", cut_at=int(p.lunch_macro_win[1]), **tags)
    return None


# --- OT-M17-cc09_003-ny-expansion --------------------------------------------------------------------------------------------------------------------

@_counted
def nyx_order(ctx, sd, i: int, p, risk_mult: float, n_done: int):
    """OT-M17-cc09_003-ny-expansion (cc09_003 ~00:17:37, setup 2 ~11:10-12:30), side space (a long; shorts mirror): at nyx_start, from closed bars - the low of 00:00 -> nyx_start was made in the London
    window (02:00-05:00) and the ADR5 projection from the day's high so far (high - ADR5) has not been traded. Window nyx_start -> 10:00: a 5m bar that trades sweep_ticks under a 5m short-term low
    (pivot n=1) formed after nyx_start and CLOSES back above it (the L.turtle_soup test, max depth nyx_stop_pct x price) is bought at that close; stop = entry - nyx_stop_pct x price;
    target = min(entry + nyx_target_pct x price, the ADR5 projection from the day's low). Several a day up to nyx_max (one at a time); entry_kind nyx_ts, setup NYX."""
    S = _S()
    t = int(ctx.t[i])
    if not p.nyx_model or not (p.nyx_start <= t < 600) or n_done >= p.nyx_max:
        return None
    k0, k300, k120 = S._idx_at(ctx, p.nyx_start), S._idx_at(ctx, 300), S._idx_at(ctx, 120)
    if k0 >= len(ctx.t) or i < k0 or k120 >= k300 or k0 <= ctx.start + 1:
        return None
    adr = S.adr5(getattr(ctx, "hist", None) or [])
    if not adr:
        return None
    lo0 = float(sd.l[ctx.start:k0].min())
    j0 = ctx.start + int(np.argmin(sd.l[ctx.start:k0]))
    hi0 = float(sd.h[ctx.start:k0].max())
    if not (k120 <= j0 < k300) or lo0 <= hi0 - adr + MIN1:
        return None
    g, ks = _done_groups(ctx, sd, i, 5)
    if g is None or len(ks) < 3:
        return None
    first, last, done, o5, h5, l5, c5 = g
    n = int(ks[-1]) + 1
    kk = int(ks[-1])
    a0 = next((int(q) for q in ks if first[q] >= k0), None)
    if a0 is None or kk - a0 < 2:
        return None
    ph, pl = L.pivots(h5[a0:n], l5[a0:n], 1)
    sent = sd.__dict__.setdefault("_nyx_sent", set())
    price = float(c5[kk])
    depth = p.nyx_stop_pct * price
    tk = S._tick(p)
    for q in reversed(pl):
        lvl = float(q.price)
        qi = a0 + q.i
        if qi >= kk - 1 or qi in sent:
            continue
        took = [e for e in range(qi + 1, kk + 1) if l5[e] <= lvl - tk + MIN1]
        if not took or took[0] < kk - 1:
            continue                                                    # the pool was already taken before the sweeping bar / not taken now
        e = took[0]
        ok = L.turtle_soup(l5, c5, lvl, e, kk, depth, 1) if e < kk else bool(c5[kk] > lvl and lvl - l5[kk] <= depth)
        if not ok:
            continue
        entry = float(c5[kk])
        stop = entry - depth
        lo_day = float(min(lo0, sd.l[ctx.start:i + 1].min()))
        tgt = min(entry + p.nyx_target_pct * price, lo_day + adr)
        if not (tgt > entry) or entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(qi)
        _dh("nyx")
        return sm4._order(ctx, sd, i, p, "AM", risk_mult, "nyx_ts", entry, stop, level=lvl, ext=float(l5[kk]), ext_i=int(first[kk]), broke=i, market=True,
                          fixed=[(float(S._exit_px(tgt, "pool", p)), "pool")], lv=("nyx_ts",), done_key=("AM" if p.nyx_counts_session else "NYX"), setup="NYX", single_exit=True, no_adds=True)
    return None


# --- X14-opposite-second-trade-after-win: the low-of-day level ---------------------------------------------------------------------------------------

def lod_level(ctx, sd, i: int, p):
    """X14 allow_opposite_after_target lod (093 ~00:14:52), for the COUNTER-bias side `sd`: the predefined low-of-day level the bias side would raid = a prior daily wick CE (wick_days) of the bias
    side below the market that has an intraday discount array (15m / 1h / 4h, Confluence) within lod_conf_pts of it, untouched today. Returns the level in SD's side space (above its entry) or None."""
    w = _want(ctx)
    sm = getattr(ctx, "sides_map", None) or {}
    sb = sm.get(w) if w else None
    if sb is None or sd.sign == w:
        return None
    S = _S()
    px = float(ctx.c[i])
    arrs = sm4.conf_arrays(ctx, sb, i, ("15m", "1h", "4h"), (0, 1, 3), known_at_start=False)
    tol2 = p.lod_conf_pts * p.es_pt
    best = None
    for v in S._wick_ces(ctx, sb, True):
        real = float(sb.x(v))
        if (w > 0 and not real < px) or (w < 0 and not real > px):
            continue
        if (w > 0 and float(ctx.l[ctx.start:i + 1].min()) < real) or (w < 0 and float(ctx.h[ctx.start:i + 1].max()) > real):
            continue                                              # traded through today
        if not any(bot - tol2 <= float(v) <= top + tol2 for top, bot, tf in arrs):
            continue
        if best is None or abs(real - px) < abs(best - px):
            best = real
    return None if best is None else float(sd.x(best))


# --- the order gate (strategy._finish_order, after order_gate6) ----------------------------------------------------------------------------------------

def any_gate7(p) -> bool:
    return bool(p.lc_rev_need_htf or p.htf_converge or p.two_session_smt or p.pm_nest_reversal or p.profile_consol or p.cc09_gate != "off" or p.m0950_branch != "off"
                or p.moc_range_dir or p.moc_no_chase_hod or p.lunch_htf_program or p.lh_after_target or p.allow_opposite_after_target in ("split", "both")
                or p.reverse_after_failure in ("at_stop", "all"))


def _trades(ctx) -> list:
    return list((getattr(ctx, "risk_view", None) or {}).get("trades", []))


def _am_trade(ctx):
    """The first closed AM trade of the day (the profile templates compare the PM with it), or None."""
    for tr in _trades(ctx):
        if tr.session == "AM":
            return tr
    return None


def _nested_all(ctx, sd, sw, i: int, tfs, tol: float) -> bool:
    """The sweep extreme lies inside an open same-side array of EVERY timeframe in `tfs` (setups._nested with a parameter)."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return False
    now = sm2.now_ts(ctx, i)
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    xr = sd.x(sw["ext"])
    for tf_ in tfs:
        if not any(min(t_, b_) - tol <= xr <= max(t_, b_) + tol for t_, b_, *_ in cf.valid(now, sd.sign, (tf_,), (0,), kb)):
            return False
    return True


def cc09_checks(ctx, sd, sw, i: int, p, entry: float) -> dict:
    """OT-M17-cc09_001-checklist (cc09_001 ~00:01:26, conditions ~1:00-7:00), side space (a long; shorts mirror): the day-trade checklist as {name: bool}. (1) iof: the daily order flow this way - the
    htf-table `iof` column, else its `flip`, else the D / 4h structure of the Confluence object; (2) react: the table's `react` this way; (3) room: the distance from the entry to the nearest opposing
    D / 4h array >= cc09_room_pts (below cc09_scalp_pts the trade is a cc09_scalp; no array = room); (4) open: the day's extreme since 00:00 traded beyond the midnight open (or the overnight low) in the Judas
    direction; (5) m15: the sweep extreme in a same-side 15m array (tag only); (6) depart: the leg from the sweep extreme reaches the MSS within cc09_depart_bars bars; (7) wpr15: the 10-period
    Williams %R on the 15m bars <= -80 at the order (tag only: short-term sentiment most bearish)."""
    S = _S()
    row = getattr(ctx, "bias_row", None) or {}
    cf = getattr(ctx, "conf", None)
    now = sm2.now_ts(ctx, i)
    out = {}

    def num(k):
        v = row.get(k)
        return None if v is None or v != v else int(v)

    iof = num("iof")
    if iof is None:
        iof = num("flip")
    if iof is not None and iof != 0:
        out["iof"] = iof == sd.sign
    else:
        out["iof"] = cf is not None and any(cf.trend(now, tf_) == sd.sign for tf_ in ("D", "4h"))
    r_ = num("react")
    out["react"] = r_ == sd.sign
    room = None
    if cf is not None:
        ent_r = float(sd.x(entry))
        opp = cf.opposing(now, ent_r, sd.sign, ("4h", "D"), (0,))
        if opp:
            room = abs(float(opp[0][0]) - ent_r)
    out["room"] = room is None or room >= p.cc09_room_pts * p.es_pt
    out["scalp"] = room is not None and room < p.cc09_scalp_pts * p.es_pt
    mo = S._open_known(ctx, "midnight", i)
    pre = ctx.pd.get("pml" if sd.sign > 0 else "pmh") if int(ctx.t[i]) >= 570 else None      # the overnight range is complete at 09:30
    lo_s = float(sd.l[ctx.start:i + 1].min())
    out["open"] = bool((mo is not None and lo_s < float(sd.x(mo)) - MIN1) or (pre is not None and lo_s < float(sd.x(pre)) - MIN1))
    kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
    arrs = S._ts_arrays(ctx, sd, i, kb, ("15m",)) if (cf is not None or getattr(ctx, "hzones", None)) else []
    out["m15"] = any(b_ - _tol(p) <= sw["ext"] <= t_ + _tol(p) for t_, b_, _ in arrs)
    br = sw.get("broke")
    out["depart"] = br is None or (int(br) - int(sw["ext_i"])) <= p.cc09_depart_bars
    g, ks = _done_groups(ctx, sd, i, 15)
    if g is not None and len(ks) >= 10:
        _, _, _, _, h15, l15, c15 = g
        w = ks[-10:]
        hh, ll = float(h15[w].max()), float(l15[w].min())
        r15 = -100.0 * (hh - float(c15[w[-1]])) / (hh - ll) if hh > ll else -50.0
        out["wpr15"] = r15 <= -80.0
    else:
        out["wpr15"] = False
    return out


def order_gate7(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #7/7 at order completion (strategy._finish_order, after order_gate6). Returns a reject key or None."""
    S = _S()
    synth = bool(sw.get(S._SM.SYNTH))
    tol = _tol(p)
    t = int(ctx.t[i])
    st7 = getattr(ctx, "state7", None) or {}
    # M17 lc_rev_need_htf: a 10:00-12:00 reversal needs a same-side, not-yet-met HTF array at the sweep
    if p.lc_rev_need_htf and not synth and session == "AM" and 600 <= int(ctx.t[sw["ext_i"]]) < 720:
        hit("lc_rev_need_htf")
        kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
        arrs = [a for a in S._ts_arrays(ctx, sd, i, kb) if a[1] - tol <= sw["ext"] <= a[0] + tol]
        sweep_i = int(sw.get("sweep_i", sw["ext_i"]))
        fresh = [a for a in arrs if sd.l[ctx.start:sweep_i].min(initial=np.inf) > a[0] + MIN1]
        if not fresh:
            return "x_lc_rev_no_htf" if not arrs else "x_lc_rev_met"
        lvt.append("lc_rev_htf")
    # B12 htf_converge: the 15m array holding the sweep extreme overlaps a 60m / 4h / D same-side array
    if p.htf_converge and not synth and getattr(ctx, "conf", None) is not None:
        kb = ctx.idx[sw["ext_i"]] + pd.Timedelta(minutes=ctx.tf)
        a15 = [a for a in S._ts_arrays(ctx, sd, i, kb, ("15m",)) if a[1] - tol <= sw["ext"] <= a[0] + tol]
        hi_ = S._ts_arrays(ctx, sd, i, kb, ("1h", "4h", "D"))
        hit("htf_converge_eval")
        if any(b_ <= th and t_ >= bh for t_, b_, _ in a15 for th, bh, _ in hi_):
            lvt.append("htf_converge")
            hit("htf_converge")
    # T13 two_session_smt: an AM trade with SMT that reached its target -> the PM takes the same side only, with SMT, and holds to the close
    if p.two_session_smt and session == "PM":
        am = _am_trade(ctx)
        if am is not None:
            hit("two_session_smt_eval")
        if am is not None and am.smt is True and am.final_hit:
            hit("two_session_smt")
            if (am.side == "long") != (sd.sign > 0):
                return "x_two_session_smt_side"
            if not synth and not (sw.get("smt") is True or sw.get("smt2") is True):
                return "x_two_session_smt_no_smt"
            lvt.append("two_session_smt")
            tags["sm7"] = dict(tags.get("sm7") or {}, hold_pm=True)
    # T13 pm_nest_reversal: a PM trade against the AM leg needs the sweep extreme nested; the target is the AM entry array when it is HTF
    am_ = _am_trade(ctx) if session == "PM" and (p.pm_nest_reversal or p.profile_consol) else None
    if p.pm_nest_reversal and session == "PM" and not synth:
        k810 = S._idx_at(ctx, 810)
        d, ah, al = sm2.am_leg(ctx, k810) if k810 < len(ctx.t) else (0, None, None)
        if d and sd.sign == -d:
            hit("pm_nest_reversal")
            if not _nested_all(ctx, sd, sw, i, p.pm_nest_tfs, tol):
                return "x_pm_nest"
            lvt.append("pm_nest")
            if am_ is not None:
                cf = getattr(ctx, "conf", None)
                e_am = float(am_.entry)
                htf_am = cf is not None and any(tf_ in ("4h", "D", "W") for tf_ in cf.at(sm2.now_ts(ctx, k810 - 1), e_am, d))
                if htf_am:
                    # review fix: the target is the NEAR EDGE of the AM entry's HTF array (the top of a long's array / the bottom of a short's), not the AM entry price inside it. (An AM trade still open at the PM
                    # cannot meet a PM order: the engine holds one position at a time, so only closed AM trades are read.)
                    edge = e_am
                    for t_, b_, *_r in cf.valid(sm2.now_ts(ctx, k810 - 1), d, ("4h", "D", "W"), (0, 1, 3), None):
                        if min(t_, b_) - tol <= e_am <= max(t_, b_) + tol:
                            edge = max(t_, b_) if d > 0 else min(t_, b_)
                            break
                    tags["fixed4"] = [(float(S._exit_px(sd.x(edge), "array", p)), "array")]
                    tags["single_exit"] = True
                    lvt.append("pm_nest_htf_target")
                else:
                    tags["extra5"] = list(tags.get("extra5") or []) + [(float(sd.x(al if d > 0 else ah)), "pool")]
                    lvt.append("pm_nest_ladder")
    # T13 profile_consol: AM and PM trades on opposite sides: the PM trade is out at 14:00 + consol_exit_min with a target at the 15m / 60m array
    if p.profile_consol and session == "PM" and am_ is not None and (am_.side == "long") != (sd.sign > 0):
        hit("profile_consol")
        tags["exit_at"] = 840 + p.consol_exit_min
        cf = getattr(ctx, "conf", None)
        if cf is not None and "fixed4" not in tags:
            opp = cf.opposing(sm2.now_ts(ctx, i), float(sd.x(entry)), sd.sign, ("15m", "1h"), (0,))
            if opp:
                tags["fixed4"] = [(float(S._exit_px(sd.x(opp[0][0]), "array", p)), "array")]
        lvt.append("profile_consol")
    # M17 cc09 checklist
    if p.cc09_gate != "off" and not synth:
        ck = cc09_checks(ctx, sd, sw, i, p, entry)
        hit("cc09_eval")
        bad = [k for k in ("iof", "react", "room", "open", "depart") if not ck[k]]
        if ck["scalp"]:
            lvt.append("cc09_scalp")
        if p.cc09_gate == "gate" and bad:
            return "x_cc09_" + bad[0]
        tags["cc09"] = "|".join(bad + [k for k in ("m15", "wpr15") if not ck[k]])
    # T7 09:50 macro: tag every AM trade
    if p.m0950_branch != "off" and session == "AM" and not synth:
        rv = rev_pool_run(ctx, sd, i, p)
        lvt.append("m0950_rev" if rv is not None else "m0950_start")
        if rv is not None and p.m0950_branch in ("rev", "both") and "fixed4" not in tags and rv["tgt"] > entry + MIN1:
            tags["fixed4"] = [(float(S._exit_px(rv["tgt"], "pool", p)), "pool")]            # (A) the reversal runs toward the 09:30-09:50 extreme = the draw flips to the opposite pool
            tags["single_exit"] = True
            hit("m0950_rev_target")
    if p.m0950_branch != "off" and session == "AM" and str(tags.get("entry_kind")) == "m0950_cont":
        lvt.append("m0950_cont_tag")
    # T10 range-day MOC direction / big-day no chase
    if session == "PM":
        rj = moc_block(ctx, sd, i, p)
        if rj:
            return rj
    # T7 lunch htf program
    if session == "LUNCH" or (p.lunch_macro_win[0] <= t < p.lunch_macro_win[1] + 20):
        rj = lunch_program(ctx, sd, i, p, session, entry, tags)
        if rj:
            return rj
    # T7 last hour after the target
    if p.lh_after_target and session == "PM" and p.last_hour[0] <= t < p.last_hour[1]:
        r = lh_after(ctx, i, p)
        if r is not None:
            if sd.sign != r["sign"]:
                return "x_lh_after_side"
            lv = [(float(S._exit_px(v, "array", p)), "array") for v in r["levels"] if v > entry + MIN1]
            if not lv:
                return "x_lh_after_room"
            tags["fixed4"] = lv
            lvt.append("lh_after_target")
    # X14 split: a PM trade against the AM after a noon reversal only when the AM did not deliver the bulk of the range
    sp = st7.get("split_pm")
    if sp and session == "PM":
        adr = S.adr5(getattr(ctx, "hist", None) or [])
        k5, k720 = S._idx_at(ctx, 570), S._idx_at(ctx, 720)
        am_rng = float(ctx.h[k5:k720].max() - ctx.l[k5:k720].min()) if k720 > k5 else 0.0
        hit("split_pm")
        if adr and am_rng >= p.skip_pm_adr_k * adr:
            return "x_split_am_range"
        br = sw.get("broke")
        if br is None or ctx.t[int(br)] < 720:
            return "x_split_no_pm_mss"
        lvt.append("split_pm")
    return None


def stop_adjust7(ctx, sd, sw, i: int, p, entry: float, stop: float, tags: dict, session: str) -> float:
    """protect_macro_ext (the stored macro extreme) and london_ext_guard (an AM short's stop never beyond the London high; the long mirror: a London low) applied to the stop before the risk check."""
    if p.protect_macro_ext and not str(tags.get("entry_kind")) == "m1050":
        stop = protected_stop(ctx, sd, entry, stop, p)
    if p.london_ext_guard and session == "AM":
        ext = london_extreme(ctx, sd, i, p)
        if ext is not None and ext[0] == "stop":
            lim = ext[1] - p.pad
            if stop < lim and lim < entry - p.min_risk_pts * p.es_pt:
                hit("london_ext_stop")
                stop = lim
    return stop


def london_extreme(ctx, sd, i: int, p):
    """new-ny-runs-london-extreme-news (065 ~03:07:01): on a day with no scheduled release a London (02:00-05:00) leg that made the day's high and broke down (the extreme before the opposite
    one, London closing under its open) is expected to hold: ("long_cap", London high) for a bullish side (no target above it) and ("stop", cap in this side's space) for the bearish side (a stop
    never beyond the London high); the bullish London mirror likewise. Returns None on a news day / without a London leg."""
    S = _S()
    from .calendar import release_times
    lon = ctx.sess.get("london")
    if lon is None or release_times(ctx.day):
        return None
    a, b = S._idx_at(ctx, 120), S._idx_at(ctx, 300)
    if b - a < 3 or i < b - 1:
        return None                                              # the London leg is complete at 05:00 (no look-ahead for an earlier bar)
    ih, il = a + int(np.argmax(ctx.h[a:b])), a + int(np.argmin(ctx.l[a:b]))
    d = -1 if (ih < il and ctx.c[b - 1] < ctx.o[a]) else 1 if (il < ih and ctx.c[b - 1] > ctx.o[a]) else 0
    if not d:
        return None
    ext_real = float(lon[0] if d < 0 else lon[1])          # the London high of a down leg / the London low of an up leg
    if sd.sign == d:
        return ("stop", float(sd.x(ext_real)))             # trading WITH the London leg: its stop is capped at the London extreme
    return ("long_cap", float(sd.x(ext_real)))             # trading against it: no target beyond the London extreme


def late7(ctx, sd, sw, i: int, p, order: dict, tags: dict, session: str):
    """The end of _finish_order: london_ext_guard's target check, the pairing state stamp, the order flags the position loop reads. Returns a reject key or None."""
    S = _S()
    if p.london_ext_guard and session == "AM":
        ex = london_extreme(ctx, sd, i, p)
        if ex is not None and ex[0] == "long_cap":
            hit("london_ext_guard")
            if max(order["levels"]) > ex[1] + MIN1:
                return "x_london_ext_target"
    if p.pairing != "all" or p.state_tag:
        order["state"] = session_state(ctx, sd, i, p)
        if p.state_tag:
            hit("state_tag")
    sm = dict(order.get("sm7") or {})
    if p.reverse_after_failure in ("at_stop", "all"):
        sm["at_stop"] = True
    if p.reentry_ts and not sw.get(S._SM.SYNTH):
        sm["ts_pivot"] = ts_pivot_ok(ctx, sd, sw, i, p)
    if sm:
        order["sm7"] = sm
    return None


# --- OT-one-state-tool-pairing -----------------------------------------------------------------------------------------------------------------------

def session_state(ctx, sd, i: int, p) -> str:
    """The market condition of the session, from data known at the session start (OT-one-state-tool-pairing, cc01_001 ~00:19:34; [our interpretation] the four names): "consolidation" = the
    htf-table daily-range regime column `drange` == 0 when present, else the engine's Chop; "expansion" = the previous day's range > ADR5 and its close in the top (bottom) quarter in the bias
    direction; "retracement" = a bias set, the close inside the previous day's range and on the discount side of its 50 % (side space); "reversal" = everything else."""
    S = _S()
    hist = getattr(ctx, "hist", None) or []
    row = getattr(ctx, "bias_row", None) or {}
    dr = row.get("drange")
    if dr is not None and dr == dr:
        if int(dr) == 0:
            return "consolidation"
    else:
        chop = getattr(ctx, "chop", None)
        if chop is not None and chop.on:
            return "consolidation"
    w = _want(ctx)
    if hist and w:
        hi, lo, cl = float(hist[-1].high.max()), float(hist[-1].low.min()), float(hist[-1].close.iloc[-1])
        adr = S.adr5(hist[:-1] if len(hist) > 5 else hist)
        if adr and hi - lo > adr and ((w > 0 and cl >= lo + 0.75 * (hi - lo)) or (w < 0 and cl <= lo + 0.25 * (hi - lo))):
            return "expansion"
        px = float(ctx.c[i])
        if lo <= px <= hi and ((w > 0 and px < (hi + lo) / 2) or (w < 0 and px > (hi + lo) / 2)):
            return "retracement"
    return "reversal"


PAIR_VOID = ("fvg", "ifvg", "implied_fvg", "vi", "void")


def pairing_ok(ctx, sd, i: int, p, o: dict) -> bool:
    """OT-one-state-tool-pairing: the end of _scan - an order passes only when the session state AND the entry kind belong to the chosen pairing ("all" = everything). expansion_ob: expansion + the
    OB entries (ob_pre / ob_anchor / arr_ob*); retracement_void: retracement + an FVG / IFVG / VI / void entry in the leg's discount; reversal_pool: reversal + a sweep-driven entry (the swept pool
    is not the entry's own name); consolidation_eq: consolidation + an entry within eq_tol_pts of the session range EQ (since 09:30)."""
    if p.pairing == "all":
        return True
    st = o.get("state") or session_state(ctx, sd, i, p)
    kind = str(o.get("entry_kind") or "")
    if p.pairing == "expansion_ob":
        ok = st == "expansion" and (kind.startswith("ob") or kind.startswith("arr_ob"))
    elif p.pairing == "retracement_void":
        leg = o.get("leg")
        disc = True if not leg else o["entry"] < leg[0] + 0.5 * (leg[1] - leg[0]) + MIN1
        ok = st == "retracement" and kind in PAIR_VOID and disc
    elif p.pairing == "reversal_pool":
        sw_name = str(o.get("swept") or "")
        ok = st == "reversal" and sw_name not in ("", kind)
    else:
        S = _S()
        k5 = S._idx_at(ctx, 570)
        if k5 > i:
            return False
        eq = (float(sd.h[k5:i + 1].max()) + float(sd.l[k5:i + 1].min())) / 2
        ok = st == "consolidation" and abs(o["entry"] - eq) <= _tol(p)
    if ok:
        hit("pairing_" + p.pairing)
    return ok


# --- M12-ts-stop-midpoint / M13 OTE full sequence ----------------------------------------------------------------------------------------------------

def array_src(ctx, sd, i: int, arr) -> int:
    """The Confluence source code (0 FVG, 1 OB, 3 VI) of the array `arr` = (top, bottom, ...) in side space, 0 when it cannot be matched (the hzones fallback holds FVGs only)."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return 0
    from .strategy import TS_TFS
    for top, bot, tf, src, kn in cf.valid(sm2.now_ts(ctx, i), sd.sign, TS_TFS, (0, 1, 3), None):
        a, b = sd.x(top), sd.x(bot)
        if abs(max(a, b) - float(arr[0])) < 1e-6 and abs(min(a, b) - float(arr[1])) < 1e-6:
            return int(src)
    return 0


def mid_stop(ctx, sd, i: int, arr, p) -> float:
    """M12-ts-stop-midpoint (022 ~02:48:40): the turtle-soup stop by the entry array's kind - a VI: below its bottom; an FVG: below its CE; an OB: below its MT (the zone midpoint) - minus one tick."""
    top, bot = float(arr[0]), float(arr[1])
    src = array_src(ctx, sd, i, arr)
    lv = bot if src == 3 else (top + bot) / 2
    hit("ts_stop_mid")
    return lv - p.tick


def ote_overlap(sd, sw, i: int, p, lo: float, hi: float, sweet: float, entry: float):
    """M13-pattern1-full-sequence-ote-fvg (cc12_004 ~00:26:47, ~00:57:31): with ote="limit" the limit stays at the 70.5 % sweet spot only where it lies inside an alive FVG of the leg (formed after the
    sweep extreme); otherwise it goes to the FVG edge nearest the sweet spot that lies inside the 62-79 % band; no FVG overlapping the band = None (no entry: the pattern needs the overlap)."""
    zs = [g for g in sd.gaps if g.i <= i and g.i - 2 >= sw["ext_i"] - 1 and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1 and g.bottom <= hi + MIN1 and g.top >= lo - MIN1]
    if not zs:
        return None
    if any(g.bottom - MIN1 <= sweet <= g.top + MIN1 for g in zs):
        hit("ote_overlap_sweet")
        return sweet
    edges = [e for g in zs for e in (float(g.top), float(g.bottom)) if lo - MIN1 <= e <= hi + MIN1]
    if not edges:
        return None
    hit("ote_overlap_edge")
    return min(edges, key=lambda e: abs(e - sweet))


def ote_s_ok(sd, sw, i: int, p) -> bool:
    """M13 ote_need_s: a short-term low S (a pivot low above the leg low, formed after it) was taken - a later bar traded one tick under it - before the order."""
    tk = _S()._tick(p)
    for q in sd.pl:
        if q.i > sw["ext_i"] and q.price > sw["ext"] + MIN1 and q.known <= i and sd.l[q.known:i + 1].min(initial=np.inf) <= q.price - tk + MIN1:
            hit("ote_s")
            return True
    return False


def ts_pivot_ok(ctx, sd, sw, i: int, p) -> bool:
    """X13-reentry-turtle-soup: the swept level is a 3-bar (pivot n=1) swing extreme formed inside the session range (since 09:30), side space."""
    S = _S()
    lvl = sw.get("level")
    if lvl is None:
        return False
    k5 = S._idx_at(ctx, 570)
    n1l = L.pivots(sd.h, sd.l, 1)[1]
    return any(q.i >= k5 and abs(q.price - float(lvl)) <= 1e-6 + _tol(p) * 0.0 for q in n1l)


# --- X14 / X13 re-entries, reversals, opposite trades (engine state: state["re7"][session]) -------------------------------------------------------------

REV_VARIANTS = {"inversion", "at_stop", "prop_fail", "sick_sister"}


def any_after7(p) -> bool:
    return bool(p.reentry_after_win or p.breakaway_chase or p.reentry_after_trail_win or p.reverse_after_failure != "off" or p.reentry_ts or p.allow_opposite_after_target != "off"
                or p.reentry_idea_gate or p.reentry_trigger != "new_array")


def _sgn(tr) -> int:
    return 1 if tr.side == "long" else -1


def after_close(ctx, pos, tr, lost, net: float, done: dict, key: str, state: dict, i, p, reopened: bool, no_same: bool = False) -> bool:
    """The re-entry / reversal state machine at a trade's close (strategy._after_close). Returns True when it re-opened the trade's session slot. Kinds (state["re7"][session], a dict with
    kind / side / pending / exit_i ...):
      "win"        X14 reentry_after_win (049 ~00:02:38; 050 ~00:49:44): a target exit short of the draw, the draw untouched -> one more same-direction entry at a NEW PD array formed after the exit;
      "trail_win"  X13 reentry_after_trail_win (085 ~00:27:16; 056; 022): a trailed stop hit in profit, the draw untouched -> a limit at the defended IFVG CE / the breaker retest (re_order);
      "reverse"    X13 reverse_after_failure (045; 094; 102; cc04_008): after a loss, the opposite side once, at reverse_risk_mult;
      "ts_re"      X13 reentry_ts (cc01_005 ~00:12:36): after a stop-out the same direction again, only by a turtle soup of an old 3-bar swing extreme (reentry_ts_ok);
      "lod"        X14 allow_opposite_after_target (093): the counter short reached the predefined low-of-day level -> the slot re-opens once for the bias side.
    `no_same` (caption-gap E6-new-trader-wide-stops, review fix): a tight-stop loss of a new trader - the SAME-direction paths (ts_re) are skipped; the reversal (opposite side) is unaffected."""
    if ctx is None or i is None:
        return False
    sess = tr.session
    sd = pos["side"]
    re7 = state.setdefault("re7", {})
    last = tr.exits[-1] if tr.exits else None
    reason = str(last[3]) if last else ""
    sgn = _sgn(tr)
    if p.allow_opposite_after_target != "off":
        hit("opposite_eval")
    draw = pos.get("draw")
    fill_i = pos["fill_i"]
    untouched = draw is not None and float(sd.h[fill_i:i + 1].max()) < float(draw) - MIN1
    basis = pos["basis"] / max(pos["n"], 1)
    sm = pos.get("sm7") or {}
    if lost is None and "lod_short" in (tr.lv_tags or "") and (tr.final_hit or reason.startswith("t")) and not state.get("lod_done"):
        state["lod_done"] = True                                         # X14 lod: the counter short reached the level; once, the bias side next
        done[key] = False
        state.setdefault("only_side", {})[sess] = -sgn
        hit("opposite_lod")
        return True
    if reopened:
        return False
    net_pos = lost is None and net > 0
    if net_pos and (p.reentry_after_win or p.breakaway_chase):
        hit("reentry_win_eval")
    if net_pos and p.reentry_after_trail_win:
        hit("trail_win_eval")
    if lost is not None and p.reverse_after_failure != "off":
        hit("reverse_eval")
    if lost is not None and p.reentry_ts:
        hit("ts_re_eval")
    if state.get("no_win_reentry"):
        net_pos = False                                      # caption-gap N3-021-citation-misread (021 ~00:44:08): a runner stopped after the bulk was banked ends the move - no win / trail-win re-entry
        hit("runner_stop_no_reentry")
    if (p.reentry_after_win or p.breakaway_chase) and net_pos and re.fullmatch(r"t\d+", reason) and not tr.final_hit and untouched and state.setdefault("win_n", {}).get(sess, 0) < p.reentry_win_max:
        state["win_n"][sess] = state["win_n"].get(sess, 0) + 1
        re7[sess] = dict(kind="win", side=tr.side, exit_i=i, fill_i=fill_i, draw=float(draw), key=key, pending=True, ext=float(pos["ext"]))
        done[key] = False
        hit("reentry_after_win")
        return True
    if (p.reentry_after_trail_win and net_pos and reason in ("stop", "be", "stop_gap") and sd.x(last[1]) > basis + MIN1 and untouched
            and state.setdefault("trail_n", {}).get(sess, 0) < p.trail_reentry_max):
        ref = pos.get("trail_ref") or (float(pos["fvg_bottom"]), float(pos.get("fvg_top") if pos.get("fvg_top") is not None else 2 * pos["fvg_ce"] - pos["fvg_bottom"]), int(fill_i))
        state["trail_n"][sess] = state["trail_n"].get(sess, 0) + 1
        re7[sess] = dict(kind="trail_win", side=tr.side, exit_i=i, fill_i=fill_i, draw=float(draw), key=key, pending=True, ref=(float(ref[0]), float(ref[1])), ref_i=int(ref[2]))
        done[key] = False
        hit("reentry_after_trail_win")
        return True
    if lost is not None and p.reverse_after_failure != "off" and not state.setdefault("rev7_n", {}).get(sess):
        vs = REV_VARIANTS if p.reverse_after_failure == "all" else {p.reverse_after_failure}
        risk_usd = tr.shares * abs(tr.entry - tr.stop)
        var = None
        if "at_stop" in vs and reason == "offside_rev":
            var = "at_stop"
        elif "inversion" in vs and reason in ("stop", "stop_gap") and float(sd.c[fill_i + 1:i + 1].min(initial=np.inf)) < float(pos["fvg_bottom"]) - MIN1:
            var = "inversion"
        elif "prop_fail" in vs and ("prop" in str(tr.entry_kind) or tr.propulsion) and prop_mt_lost(pos, sd, fill_i, i):
            var = "prop_fail"
        elif "sick_sister" in vs and risk_usd > 0 and -net <= 0.5 * risk_usd + 1e-9:
            var = "sick_sister"
        if var is not None:
            zt = pos.get("fvg_top") if pos.get("fvg_top") is not None else 2 * pos["fvg_ce"] - pos["fvg_bottom"]
            adv = float(sd.x(sd.h[fill_i:i + 1].max())) if sgn > 0 else float(sd.x(sd.l[fill_i:i + 1].min()))          # real prices: the adverse leg extreme of the reversal
            re7[sess] = dict(kind="reverse", variant=var, side="short" if sgn > 0 else "long", exit_i=i, fill_i=fill_i, key=key, pending=True, stop_i=i,
                             zone=(float(sd.x(pos["fvg_bottom"])), float(sd.x(zt))), ext=float(sd.x(pos["ext"])), old_stop=float(sd.x(pos["stop"])), adv_ext=adv)
            state["rev7_n"][sess] = 1
            done[key] = False
            state.setdefault("only_side", {})[sess] = -sgn
            hit("reverse_" + var)
            return True
    if lost is not None and p.reentry_ts and not no_same and state.setdefault("ts_re_n", {}).get(sess, 0) < p.reentry_max and reason in ("stop", "stop_gap"):
        state["ts_re_n"][sess] = state["ts_re_n"].get(sess, 0) + 1
        re7[sess] = dict(kind="ts_re", side=tr.side, exit_i=i, fill_i=fill_i, key=key, pending=True)
        done[key] = False
        hit("reentry_ts")
        return True
    return False


def prop_mt_lost(pos, sd, fill_i: int, i: int) -> bool:
    """X13 prop_fail (cc04_008 ~5:15): the propulsion block failed = a BODY closed through its MT after the fill. The MT is the trade's `prop_mt` exit level (lvx, set with prop_mt_exit); a trade that
    carries none (prop_mt_exit off) cannot be checked and counts as failed [our interpretation: the reversal then follows any loss of a propulsion entry, as the first build did]."""
    ent = (pos.get("lvx") or {}).get("prop_mt")
    if not ent:
        return True
    hit("prop_fail_mt_eval")
    return bool(float(sd.c[fill_i + 1:i + 1].min(initial=np.inf)) < float(ent[0]) - MIN1)


def rc_extra(pos, tr, i: int, p) -> dict:
    """Extra fields of the X13b loss re-entry context (manage.reentry_open's dict) the idea-intact gate reads: the entry zone (side space), the leg origin, the stop price, the draw."""
    sd = pos["side"]
    zt = pos.get("fvg_top") if pos.get("fvg_top") is not None else 2 * pos["fvg_ce"] - pos["fvg_bottom"]
    return dict(z=(float(pos["fvg_bottom"]), float(zt)), ext=float(pos["ext"]), draw=None if pos.get("draw") is None else float(pos["draw"]), low_stop=float(sd.l[pos["fill_i"]:i + 1].min()),
                stop_px=float(pos["stop"]), exit_i=int(i))


def risk_mult7(state, session: str, p, m: float) -> float:
    """_risk_mult for this chunk: the loss re-entry risk (reentry_risk_mult replaces the hard 0.5 of X13), the reversal's reverse_risk_mult, the turtle-soup re-entry's reentry_mult."""
    r7 = state.get("re7", {}).get(session)
    if r7 is not None and r7.get("pending"):
        if r7["kind"] == "reverse":
            return m * p.reverse_risk_mult
        if r7["kind"] == "ts_re":
            return m * p.reentry_mult
    return m


def reentry_idea_ok(ctx, sd, i: int, p, o: dict, rc: dict) -> bool:
    """X13-reentry-after-loss-conditions (060 ~01:22:23; cc02_005 ~00:03:34; 104 ~00:45:43), the idea is intact when: (a) the draw is untouched since the fill; (b) no opposing MSS (a close under the
    stop-out low) and no close beyond the leg's origin swing since the stop; (c) a NEW PD array formed after the stop - and the re-entry is a limit at that array, never a market chase.
    [our interpretation of (b)]. With reentry_trigger "sibi_return" the order must be the return order of re_order."""
    hit("reentry_idea_eval")
    if o.get("market"):
        return False
    z = rc.get("z")
    if z is None:
        return True
    fill_i, stop_i = rc.get("fill_i", 0), rc.get("stop_i", 0)
    if rc.get("draw") is not None and float(sd.h[fill_i:i + 1].max()) >= float(rc["draw"]) - MIN1:
        return False
    if float(sd.c[stop_i + 1:i + 1].min(initial=np.inf)) < rc["low_stop"] - MIN1 or float(sd.c[stop_i:i + 1].min(initial=np.inf)) < rc["ext"] - MIN1:
        return False
    if p.reentry_trigger == "sibi_return":
        return (o.get("sm7") or {}).get("kind") == "sibi_return"
    return int(o.get("fvg_i", o["i"])) > stop_i


def loss_reentry_ok(ctx, sd, i: int, p, o: dict, rc: dict) -> bool:
    """X13b gate of an order while the loss re-entry context is pending (run_day): the idea-intact test when reentry_idea_gate is on OR the trigger is sibi_return (review fix: the sibi return order
    carries ext_i == stop_i and could never pass the old restored-sweep test, so the trigger alone was dead), else the old restored-sweep / FVG test."""
    if p.reentry_stop == "ob_low":
        return (o.get("sm7") or {}).get("kind") == "ob_low"              # caption-gap E6-attempt-based-stop: the re-entry order IS the new OB (es3.ob_low_order)
    if p.reentry_idea_gate or p.reentry_trigger == "sibi_return":
        return reentry_idea_ok(ctx, sd, i, p, o, rc)
    return _S()._MG.reentry_order_ok(o, sd, rc, p)


def reentry_ok(ctx, sd, i: int, p, o: dict, r7: dict) -> bool:
    """The order gate of the re7 kinds (run_day, after _scan): same side / opposite side, a NEW array after the exit, the turtle-soup form, the sister condition."""
    kind = r7["kind"]
    sm = o.get("sm7") or {}
    if kind in ("win", "trail_win", "ts_re") and ("long" if sd.sign > 0 else "short") != r7["side"]:
        return False
    if kind in ("win", "trail_win") and o.get("market"):
        return False                                                      # review fix: the re-entry arms through a LIMIT order only (a market chase never qualifies)
    if kind == "win":
        if int(o.get("fvg_i", o["i"])) <= r7["exit_i"]:
            return False
        if p.reentry_need_sister and not sister_delivered(ctx, sd, i, r7):
            return False
        return True
    if kind == "trail_win":
        return sm.get("kind") == "trail_win"
    if kind == "ts_re":
        k = str(o.get("entry_kind") or "")
        if not is_ts_kind(o) or not sm.get("ts_pivot"):
            return False
        S = _S()
        k5 = S._idx_at(ctx, 570)
        eq = (float(sd.h[k5:i + 1].max()) + float(sd.l[k5:i + 1].min())) / 2
        return float(o["entry"]) < eq + MIN1                              # side space: the discount of the range = the real premium for a short
    if kind == "reverse":
        v = r7["variant"]
        if v in ("inversion", "at_stop"):
            return sm.get("kind") == "rev_" + v
        if v == "prop_fail":
            return o.get("broke") is not None and int(o.get("fvg_i", o["i"])) > r7["stop_i"]
        return True
    return True


def sister_delivered(ctx, sd, i: int, r7: dict) -> bool:
    """reentry_need_sister [our interpretation]: the sister index traded beyond its own extreme of the bars before the first entry (the same draw kind: its session low for a short) after the fill."""
    ps = getattr(ctx, "pside", None)
    if not ps or ps[0] is None:
        return False
    pctx, psides, ppos = ps
    j = int(ppos.index.searchsorted(ctx.idx[i], side="right") - 1)
    j0 = int(ppos.index.searchsorted(ctx.idx[r7["fill_i"]], side="right") - 1)
    if j <= j0 or j0 <= pctx.start:
        return False
    psd = psides[sd.sign]
    return bool(float(psd.h[j0 + 1:j + 1].max()) > float(psd.h[pctx.start:j0 + 1].max()) + MIN1)


def held(pos) -> bool:
    """T13 two_session_smt: the PM trade is held to the close - the PM time exits (pm_done_by, pm_consol_exit) skip a position that carries hold_pm."""
    return bool((pos.get("sm7") or {}).get("hold_pm"))


def fill_note(state: dict, o: dict) -> None:
    """run_day: the re-entry / reversal order filled - the slot's re7 context is no longer pending."""
    r7 = state.get("re7", {}).get(o.get("session"))
    if r7 is not None and r7.get("pending"):
        r7["pending"] = False
        hit("re7_fill_" + str(r7["kind"]))                       # the OUTCOME counter: the re-entry / reversal order filled (win / trail_win / reverse / ts_re)


# --- the re-entry orders (non-sweep) ---------------------------------------------------------------------------------------------------------------

def any_re_orders(ctx, p) -> bool:
    r7 = getattr(ctx, "re7", None)
    if r7 is not None and r7.get("pending") and (r7["kind"] in ("trail_win", "reverse") or (r7["kind"] == "win" and p.breakaway_chase)):
        return True
    rc = getattr(ctx, "re_ctx_now", None)
    return bool(rc and rc.get("pending") and p.reentry_trigger == "sibi_return")


@_counted
def re_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The limit / stop orders of the re-entry kinds, side space of the order's side:
    trail_win - a limit at the CE of the defended IFVG (`trail_reentry_entry` "ifvg_ce", stop under its low) or at the retest of the last up-close candle that price traded above (the 022 breaker,
        stop at the CE of the FVG beneath it); the draw untouched, the structure never broken by a body close, not a high-resistance day (sloppy / chop [our interpretation]); target = the original draw.
    reverse inversion (102) - the failed array inverted (a body closed through it, nothing back over its CE): a limit at its near edge on the return, stop beyond its CE + pad;
    reverse at_stop (094) - a stop order at the old stop price in the opposite direction, stop beyond the adverse leg extreme.
    X13b loss + reentry_trigger sibi_return (104) - after the market traded one tick beyond the entry zone's far edge, a limit at that edge on the return; stop under the lowest low since the stop (or
    the CE of its wick with reentry_stop "wick_ce")."""
    S = _S()
    sidename = "long" if sd.sign > 0 else "short"
    rc = getattr(ctx, "re_ctx_now", None)
    if rc and rc.get("pending") and p.reentry_trigger == "sibi_return" and rc.get("side") == sidename and rc.get("z") is not None and not rc.get("armed"):
        bot, top = rc["z"]
        si = rc["stop_i"]
        if float(sd.h[si:i + 1].max()) >= top + float(p.tick) - MIN1 and sd.c[i] > top + MIN1:
            k = si + int(np.argmin(sd.l[si:i + 1]))
            stop = ((float(sd.l[k]) + float(min(sd.o[k], sd.c[k]))) / 2 if p.reentry_stop == "wick_ce" else float(sd.l[si:i + 1].min())) - p.pad
            entry = float(top)
            if stop < entry and entry - stop >= p.min_risk_pts * p.es_pt:
                _dh("sibi_return")
                o = sm4._order(ctx, sd, i, p, session, risk_mult, "sibi_return", entry, stop, level=entry, ext=float(bot), ext_i=int(si), broke=i, fvg_bottom=float(bot),
                               lv=("sibi_return",), sm7=dict(kind="sibi_return"))
                if o is not None:
                    rc["armed"] = True                                    # review fix: armed only once the order passed its gates (a rejected one may be tried again)
                return o
    r7 = getattr(ctx, "re7", None)
    if r7 is None or not r7.get("pending") or r7.get("side") != sidename and r7["kind"] == "trail_win" or r7.get("armed"):
        return None
    kind = r7["kind"]
    hit("re_order_eval")
    if kind == "win":
        return chase_order(ctx, sd, i, p, session, risk_mult, r7) if (p.breakaway_chase and r7["side"] == sidename) else None
    if kind == "trail_win":
        if getattr(ctx, "cur_sloppy", "") or (getattr(ctx, "chop", None) is not None and ctx.chop.on):
            return None
        bot, top = r7["ref"]
        fi, ei = r7["fill_i"], r7["exit_i"]
        if float(sd.c[fi + 1:i + 1].min(initial=np.inf)) < bot - MIN1 or float(sd.h[fi:i + 1].max()) >= r7["draw"] - MIN1:
            r7["dead"] = True
            return None
        if p.trail_reentry_entry == "ifvg_ce":
            entry, stop = (top + bot) / 2, bot - p.pad
        else:
            cand = [k for k in range(fi, ei + 1) if sd.c[k] > sd.o[k] and float(sd.h[k + 1:i + 1].max(initial=-np.inf)) > sd.h[k]]
            if not cand:
                return None
            k = cand[-1]
            entry = float(max(sd.o[k], sd.c[k]))
            gaps = [g for g in sd.gaps if g.i <= i and g.top <= entry + MIN1]
            stop = (float(max(gaps, key=lambda g: g.top).mid) if gaps else float(sd.l[k])) - p.pad
        if not (stop < entry < sd.c[i]) or entry - stop < p.min_risk_pts * p.es_pt or r7["draw"] <= entry:
            return None
        _dh("trail_reentry")
        o = sm4._order(ctx, sd, i, p, session, risk_mult, "trail_reentry", entry, stop, level=entry, ext=float(stop + p.pad), ext_i=int(ei), broke=i, fvg_bottom=float(bot),
                       fvg_ce=float((top + bot) / 2), fixed=[(float(S._exit_px(r7["draw"], "pool", p)), "pool")], lv=("trail_reentry",), sm7=dict(kind="trail_win"))
        if o is not None:
            r7["armed"] = True
        return o
    if kind == "reverse" and r7["side"] == sidename:
        v = r7["variant"]
        if v == "inversion":
            a_, b_ = r7["zone"]                                       # the failed array, REAL prices
            zb, zt = min(float(sd.x(a_)), float(sd.x(b_))), max(float(sd.x(a_)), float(sd.x(b_)))      # ... in this (opposite) side's space
            ce = (zb + zt) / 2
            inv = float(sd.c[r7["fill_i"] + 1:i + 1].max(initial=-np.inf)) > zt + MIN1               # a body closed through it
            back = float(sd.c[r7["exit_i"]:i + 1].min(initial=np.inf)) < ce - MIN1                  # ... and did not come back over its CE (A8: the inversion holds)
            entry, stop = zt, ce - p.pad
            if not inv or back or not (entry < sd.c[i]) or not (stop < entry) or entry - stop < p.min_risk_pts * p.es_pt:
                return None
            _dh("reverse_inversion")
            o = sm4._order(ctx, sd, i, p, session, risk_mult, "rev_inversion", entry, stop, level=entry, ext=zb, ext_i=int(r7["exit_i"]), broke=i, fvg_bottom=zb, fvg_ce=ce,
                           lv=("rev_inversion",), sm7=dict(kind="rev_inversion"))
            if o is not None:
                r7["armed"] = True
            return o
        if v == "at_stop":
            entry = float(sd.x(r7["old_stop"]))
            stop = float(sd.x(r7["adv_ext"])) - p.pad
            if not (entry > sd.c[i] + MIN1) or not (stop < entry) or entry - stop < p.min_risk_pts * p.es_pt:
                return None
            _dh("reverse_at_stop")
            o = sm4._order(ctx, sd, i, p, session, risk_mult, "rev_at_stop", entry, stop, level=entry, ext=stop + p.pad, ext_i=int(r7["exit_i"]), broke=i, stop_entry=True,
                           lv=("rev_at_stop",), sm7=dict(kind="rev_at_stop"))
            if o is not None:
                r7["armed"] = True
            return o
    return None


def chase_pick(sd, i: int, p, r7: dict):
    """The pure pick of the chase (E5-breakaway-gap-chase): (gap, entry, stop) or None. Reads only bars <= i (gaps complete by i, pivots known by i)."""
    draw = r7.get("draw")
    if draw is None:
        return None
    fi, ei = int(r7["fill_i"]), int(r7["exit_i"])
    if float(sd.h[fi:i + 1].max()) >= float(draw) - MIN1:
        return None
    g = None
    for z in sorted((z for z in sd.gaps if ei < z.i - 2 and z.i <= i), key=lambda z: z.i):
        if any(q.known <= z.i - 1 and q.i < z.i - 2 and sd.c[z.i - 1] > q.price + MIN1 for q in sd.ph):
            g = z
            break
    if g is None or sd.c[g.i + 1:i + 1].min(initial=np.inf) < g.bottom - MIN1:
        return None
    entry, stop = float(g.top), float(g.bottom) - p.pad
    if not (stop < entry < sd.c[i]) or entry - stop < p.min_risk_pts * p.es_pt or float(draw) <= entry:
        return None
    return g, entry, stop


def chase_order(ctx, sd, i: int, p, session: str, risk_mult: float, r7: dict):
    """E5-breakaway-gap-chase (049 ~00:05:01), review fix - the standalone chase path: after a closed winner (the X14 win state, the draw still untouched) the FIRST same-direction FVG formed after the exit by a
    displacement that closed beyond a short-term high (the breakaway gap) is picked DIRECTLY - no fresh sweep / MSS, whatever the normal fvg_pick would choose [our interpretation of "breakaway-tagged":
    the gap's middle candle closes over a pivot high confirmed before it]. A limit at its near edge (top), the stop under its bottom, the target the original draw; unfilled after breakaway_chase_bars bars
    it becomes a market order at the next open (strategy.run_day -> es2.convert_pending, which drops it if the stop was pierced). Armed once per win."""
    if r7.get("armed"):
        return None
    if r7.get("draw") is not None and float(sd.h[int(r7["fill_i"]):i + 1].max()) >= float(r7["draw"]) - MIN1:
        r7["dead"] = True
        return None
    pk = chase_pick(sd, i, p, r7)
    if pk is None:
        return None
    g, entry, stop = pk
    S = _S()
    _dh("breakaway_chase_direct")
    o = sm4._order(ctx, sd, i, p, session, risk_mult, "breakaway_chase", entry, stop, level=entry, ext=float(stop + p.pad), ext_i=int(r7["exit_i"]), broke=i, fvg_bottom=float(g.bottom), fvg_ce=float(g.mid),
                   fixed=[(float(S._exit_px(r7["draw"], "pool", p)), "pool")], lv=("breakaway_chase",), fvg_i=int(g.i), chase_bars=int(p.breakaway_chase_bars), sm7=dict(kind="win_chase"))
    if o is not None:
        r7["armed"] = True
        hit("breakaway_chase_direct")
    return o


# --- the position loop ------------------------------------------------------------------------------------------------------------------------------

def on_fill(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    st = dict(o.get("sm7") or {})
    if st.get("kind") == "ba":
        st["ref_hi"] = float(sd.h[ctx.start:o["i"] + 1].max())
    pos["sm7"] = st


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this chunk tagged (pos["sm7"]):
    at_stop (094 ~00:03:05) - the open trade offside by >= offside_frac x (entry -> stop) with a body closed beyond its entry gap [our interpretation of 'bodies': ONE body close under the gap]: out at that
    close (exit reason offside_rev - it is a reversal trigger, so it is named apart from a plain offside exit), the reversal order follows;
    breakaway re-entry (062 ~00:37:28) - once price leaves to a new extreme beyond the order's high and the gap is still partly open, the stop drops to the gap (just under its bottom + a tick)."""
    S = _S()
    st = pos.get("sm7")
    if not st or not pos["left"] or i <= pos["fill_i"]:
        return
    if st.get("at_stop") and not st.get("done") and not pos.get("t1_done"):
        basis = pos["basis"] / max(pos["n"], 1)
        risk = basis - pos.get("stop0", pos["stop"])
        c = float(sd.c[i])
        if risk > 0 and basis - c >= p.offside_frac * risk - MIN1 and c < pos["fvg_bottom"] - MIN1:
            st["done"] = True
            tr.exits.append((ts, sd.x(c), pos["left"], "offside_rev"))
            pos["left"] = 0
            hit("offside_rev")
            return
    if st.get("runner_before") and pos.get("t1_done") and pos["left"] and tr.exits:
        # missed_5m: the quarter-ADR5 runner is left only when the ADR5 extreme was hit before 10:00; hit later, the rest leaves with the first rung at its price
        mt0 = tr.exits[0][0]
        if mt0.hour * 60 + mt0.minute >= st["runner_before"]:
            tr.exits.append((ts, tr.exits[0][1], pos["left"], "no_runner"))
            pos["left"] = 0
            hit("missed_no_runner")
            return
    if st.get("kind") == "ba" and not st.get("dropped"):
        gb = st["gap_bottom"]
        if sd.h[i] > st["ref_hi"] + MIN1 and float(sd.l[pos["fill_i"] + 1:i + 1].min(initial=np.inf)) > gb + MIN1:
            st["dropped"] = True
            new = gb - p.tick
            if new > pos["stop"] and new < sd.c[i]:
                S._MG.raise_stop(pos, new, trail=True)
                hit("breakaway_stop_drop")


# --- E6-breakaway-gap-stop ---------------------------------------------------------------------------------------------------------------------------

def n_mss(sd, sw, i: int) -> int:
    """The number of same-direction market-structure shifts since the sweep: the first (sw["broke"]) plus every later close above a short-term high formed after it (side space)."""
    if sw.get("broke") is None:
        return 0
    n, lvl_i = 1, int(sw["broke"])
    for q in sd.ph:
        if q.i > lvl_i and q.known <= i:
            j = next((x for x in range(q.known, i + 1) if sd.c[x] > q.price), None)
            if j is not None:
                n += 1
                lvl_i = j
    return n


def breakaway_order(ctx, sd, sw, ba, i: int, p, session: str, risk_mult: float):
    """E6-breakaway-gap-stop (062 ~00:37:28): a missed 2022-model entry (no fill in the session, nothing resting) after TWO same-direction MSSs: a retrace bar that enters the breakaway FVG (the first
    gap after the MSS, still partly open) arms a limit at its near edge (top); the stop = that retrace bar's low - 1 tick (the two MSSs justify not fearing a return into it); once price leaves to
    a new high beyond the order's, the stop drops to just under the gap (manage). A full fill of the gap cancels (cancel_low = its bottom): then it is no breakaway gap."""
    S = _S()
    if ba is None or sw.get("broke") is None or getattr(ctx, "pend_now", None) is not None or getattr(ctx, "done_ref", {}).get(session):
        return None
    hit("breakaway_eval")
    if n_mss(sd, sw, i) < 2 or sw.get("_ba_sent") or ba.i > i:
        return None
    if float(sd.l[ba.i + 1:i + 1].min(initial=np.inf)) <= ba.bottom + MIN1 or not (sd.l[i] <= ba.top + MIN1 and sd.c[i] > ba.top + MIN1):
        return None
    entry, stop = float(ba.top), float(sd.l[i]) - p.tick
    if entry - stop < p.min_risk_pts * p.es_pt:
        return None
    sw["_ba_sent"] = True
    tags = dict(unicorn=False, fvg_bottom=float(ba.bottom), fvg_ce=float(ba.mid), zone_top=float(ba.top), fvg_i=int(ba.i), entry_kind="breakaway_re", mitigation=False, propulsion=False,
                no_leg_wait=True, cancel_low=float(ba.bottom), lv_tags=["breakaway_re"], sm7=dict(kind="ba", gap_bottom=float(ba.bottom)))
    o = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[sw["ext_i"]:i + 1].max()), tags, skip_leg_pd=True)
    if o is not None:
        hit("breakaway_reentry")
    return o


# --- E12-070-rung-order / M4-pattern3-breaker-half-size-add-ltf --------------------------------------------------------------------------------------

def adv_ladder(ctx, sd, sw, i: int, p, A: float, B: float, stop: float):
    """E12-070-rung-order (070 ~00:58:44): the advanced breaker's A-B leg (side space, A the swing low, B the high) filled by up to three resting limits - rung 1 the CE of a 5m FVG inside the leg,
    rung 2 the CE of the 1m IFVG, rung 3 the low end (bottom) of that IFVG - sized adv_rung_fracs (renormalised over the rungs found); only rungs under the close and over the stop. Returns
    (prices descending, fracs) or None when fewer than two rungs exist (the single MT limit stays)."""
    rungs = []                                                       # (price, index into adv_rung_fracs): 0 = the 5m FVG CE, 1 = the IFVG CE, 2 = the IFVG bottom
    z5 = [z for z in sd.zones_tf(ctx.idx, ctx.tf, 5) if z.mt != z.mt and z.i <= i and z.bottom >= A - MIN1 and z.top <= B + MIN1 and z.i >= sw["ext_i"]
          and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
    if z5:
        rungs.append((float(max(z5, key=lambda z: z.i).mid), 0))
    ifz = [z for z in sd.ifvgs() if z.i <= i and z.bottom >= A - MIN1 and z.top <= B + MIN1 and z.i >= sw["ext_i"] and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
    if ifz:
        z = max(ifz, key=lambda z_: z_.i)
        rungs += [(float(z.mid), 1), (float(z.bottom), 2)]
    rungs = sorted({(round(v, 6), k) for v, k in rungs if stop + MIN1 < v < sd.c[i] - MIN1}, reverse=True)
    out = []
    for v, k in rungs:                                               # prices descending; rungs closer than a quarter point merge into the higher one
        if not out or out[-1][0] - v >= 0.25 * p.es_pt - MIN1:
            out.append((v, k))
    if len(out) < 2:
        return None
    fr = [p.adv_rung_fracs[k] for _, k in out]                       # review fix: each rung keeps ITS type's weight (a missing 5m rung does not hand its weight to the IFVG CE), renormalised over the rungs found
    s_ = sum(fr)
    hit("adv_rungs")
    return [v for v, _ in out], tuple(f / s_ for f in fr)


def breaker_add(ctx, sd, pos, tr, i: int, p, z) -> None:
    """M4-pattern3-breaker-half-size-add-ltf (cc12_004 ~00:36:02): the breaker add of a turtle-soup trade is ts_breaker_add_mult (spec 0.5; None = the standard add fraction, unchanged) x the initial units; with ts_breaker_ltf the add limit is the 1m
    FVG (or the down-close candle's body top) INSIDE the breaker zone nearest its top (the lower-timeframe refinement), else the zone top."""
    S = _S()
    hit("ts_breaker_add_eval")
    px = float(z.top)
    if p.ts_breaker_ltf:
        c1 = [float(g.top) for g in sd.gaps if g.i <= i and g.i > pos["fill_i"] and g.bottom >= z.bottom - MIN1 and g.top <= z.top + MIN1]
        c1 += [float(sd.o[k]) for k in range(max(z.src, pos["fill_i"] + 1), i + 1) if sd.c[k] < sd.o[k] and z.bottom - MIN1 <= min(sd.o[k], sd.c[k]) and max(sd.o[k], sd.c[k]) <= z.top + MIN1]
        if c1:
            px = max(c1)
            hit("ts_breaker_ltf")
    if not S._SM.add_ok(sd, pos, px, i, p):
        return
    if p.ts_breaker_add_mult is None:                                # unset: the standard add fraction (adds), byte-identical to the build before this pass
        hit("ts_breaker_add")
        S._arm_add(pos, tr, px, i, p, ctx.equity)
        return
    base = pos.get("plan_shares") or tr.shares
    size = S._lots(base * p.ts_breaker_add_mult, p.lot)
    if size >= max(p.lot, 1):
        hit("ts_breaker_add")
        S._arm_add(pos, tr, px, i, p, ctx.equity, size=size)


# --- dispatchers (strategy._scan / run_day) -------------------------------------------------------------------------------------------------------------

def any_extra7(p) -> bool:
    return bool("or_ref" in p.entry_arrays or p.am_array_open or p.lh_ob_pullback or p.m0950_branch in ("cont", "both") or p.missed_5m)


def extra7(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried when the sweep machine has nothing (strategy._scan)."""
    if "or_ref" in p.entry_arrays:
        o = or_ref_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.am_array_open:
        o = am_open_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.lh_ob_pullback:
        o = lh_ob_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.m0950_branch in ("cont", "both"):
        o = m0950_cont_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.missed_5m:
        o = missed_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


def any_special7(p) -> bool:
    return bool(p.lc_scalp or p.m1050 or p.lunch_macro_entry or p.nyx_model or (p.missed_5m and p.missed_lon))


def special7(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float, done: dict):
    """The setups of this chunk that run outside the session windows (run_day, like sm4.special4): the London-close scalp, the 10:50 macro model, the lunch-macro entry, the NY expansion turtle soup.
    Armed on the bar that has just closed; each has its own done key. The day filter (`blocked`, skip_news) applies to each; the NY expansion, the 10:50 macro and the lunch macro also pass through
    the htf_bias gate (a side against the bias is not tried; neutral / off = both). The session_veto helper of other.md#10 is not built (the same checks - blocked(), skip_news - are applied here)."""
    if pos is not None or pending is not None or state.get("day_done"):
        return None
    S = _S()
    t = int(ctx.t[i])
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_lock_any, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, None, "", False, 0
        n_nyx = sum(1 for tr in _trades(ctx) if tr.entry_kind == "nyx_ts")
        jobs = (
            ("LC", p.lc_scalp and lc_window(p)[0] <= t < lc_window(p)[1], lambda sd: lc_order(ctx, sd, i, p, risk_mult)),
            ("M1050", p.m1050 and 650 <= t < 670, lambda sd: m1050_order(ctx, sd, i, p, risk_mult)),
            ("LUNCHM", p.lunch_macro_entry and p.lunch_macro_win[0] <= t < p.lunch_macro_win[1], lambda sd: lunch_macro_order(ctx, sd, i, p, risk_mult)),
            ("NYX", p.nyx_model and p.nyx_start <= t < 600, lambda sd: nyx_order(ctx, sd, i, p, risk_mult, n_nyx)),
            # E5 London lunch: the engine scans no session between 05:00 and 07:00, so the London sweep's missed-entry retrace runs here (the sweep is a LON one, the order is cut at 07:00)
            ("MISSLON", p.missed_5m and p.missed_lon and 300 <= t < 420, lambda sd: missed_order(ctx, sd, i, p, "LON", risk_mult, extra=dict(cut_at=420, done_key="MISSLON"))),
        )
        for key, on, fn in jobs:
            if not on or done.get(key) or (key == "NYX" and p.nyx_counts_session and done.get("AM")):
                continue
            ses = sess_label(t, p) if key in ("LC", "NYX") else ("LUNCH" if key == "LUNCHM" else ("LON" if key == "MISSLON" else "AM"))
            ctx.cur_session = ses
            if (p.day_filter and S.blocked(ctx.day, ses, p, t)) or (p.skip_news and S.news(ctx.day) != "none"):
                continue
            for sd in sides:
                w_ = bias_now(ctx, p, "AM", i) if key != "LC" else 0       # the London-close scalp is counter-trend on purpose (no bias gate)
                ctx.cur_bias = w_
                if w_ and w_ != sd.sign:
                    hit("special7_bias_skip")                                # review fix: NYX / 10:50 / lunch macro pass through use_bias (htf_bias) like every setup: the other side is not tried
                    continue
                out = fn(sd)
                if out is not None:
                    if key == "NYX" and not p.nyx_counts_session:
                        out["done_key"] = "NYX_x"
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


# --- small glue --------------------------------------------------------------------------------------------------------------------------------------

def trade_fields(o: dict) -> dict:
    """The Trade fields of this chunk carried by an order dict (strategy._make_trade)."""
    return {k: o[k] for k in ("cc09", "state") if k in o}


def is_ts_kind(o: dict) -> bool:
    return str(o.get("entry_kind") or "") in TS_ENTRY_KINDS


def any_late7(p) -> bool:
    return bool(p.london_ext_guard or p.pairing != "all" or p.state_tag or p.reverse_after_failure in ("at_stop", "all") or p.reentry_ts)
