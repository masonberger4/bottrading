"""Package setups_models (rule_coverage.md section 3 "setups_models"; build_log.md).

The new setup branches and the sweep / MSS rules of the models digest, called from
strategy._scan_core / _finish_order / run_day. Everything here runs in SIDE SPACE (bullish terms;
shorts are the mirrored prices of strategy.Side), reads only bars that have closed (index <= the
caller's bar i) and every rule is a Params switch, off by default. Thresholds ICT never gives are
marked [our interpretation]; [CC] = Core Content only.

Order flags these helpers may set (strategy.run_day honours them):
  market      fill at the next bar's open (an "enter at once" rule)
  stop_entry  a buy stop (side space): fills once a bar trades up to the entry
  through     a limit that needs `through` price units beyond it to fill (M4.3 "1 tick through")
  cancel_low  a closed bar trading below it cancels the pending order (M11b OB low, M1.3 body low)
  exit_at     time exit (minutes; M16.1 11:00)
  runner      the last ladder fraction is held to the close (Ep04.3 po3_runner)
  po3_open    (side space) after a close above it, a close back below exits (T13 po3_hold)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from claude_hf.daytypes import events
from . import levels as L
from . import strategy as S

SYNTH = "synthetic"          # sw flag: a setup that did not come from the sell-side sweep machine


def lh_on(p, name: str) -> bool:
    """Ep01.13 last_hour_setup turns on the own slot, unengaged draw and HTF-done skip."""
    return bool(getattr(p, name)) or p.last_hour_setup


def _tf(ctx):
    return pd.Timedelta(minutes=ctx.tf)


def _ob_body(o, c, z, end: int) -> tuple[float, float]:
    """Body top / low of a blended bullish OB zone (order_block_blend: src = first candle)."""
    j = z.src
    k = j
    while k + 1 <= end and c[k + 1] < o[k + 1]:
        k += 1
    return float(np.max(o[j:k + 1])), float(np.min(c[j:k + 1]))


def ob_low(sd, e: int, outside=None):
    """Review fix (A20 / M0.4 / M2.3): the order block AT the sweep low - the last down-close
    candle(s) in [e-3, e] (order_block_blend limited to the sweep extreme), never a pullback
    candle of the up-leg after the low. (zone, body top, body low) or None."""
    ob = L.order_block_blend(sd.o, sd.h, sd.l, sd.c, e - 3, e, "bull", outside=outside)     # (caption-gap A12 ob_outside_fvg: candles inside the shaded zone are ignored)
    if ob is None:
        return None
    top, low = _ob_body(sd.o, sd.c, ob, e)
    return ob, top, low


# --- pools (hooked into strategy._sell_side) ----------------------------------------------------

def extra_pools(ctx, sd, session, i, p, out: dict) -> None:
    """M16.1 "l0500": the 05:00-09:30 low (side space), an AM pool from 09:30 (cc10_011 ~8:01).
    M7.3 "pm_judas_array": in the PM, the top of the nearest same-side HTF array wholly beyond the
    13:30 open (complete by bar i-1) - a raid into it is the PM Judas without a pool."""
    if p.smt_entry and session == "AM" and ctx.t[i] >= 570:
        k5, k9 = S._idx_at(ctx, 300), S._idx_at(ctx, 570)
        if ctx.start <= k5 < k9 <= i:
            out["l0500"] = float(sd.l[k5:k9].min())
    if p.pm_judas_array and session == "PM" and i - 1 >= S._idx_at(ctx, 810):
        o13 = S._open_known(ctx, "1330", i - 1)
        if o13 is not None:
            ref = sd.x(o13)
            kb = ctx.idx[i - 1] + _tf(ctx)
            tops = [a for a, b, _ in S._ts_arrays(ctx, sd, i - 1, kb) if a < ref]
            if p.pm_lunch_fvg_array:             # caption-gap M7-pm-1330-judas-full (010 ~57:47): the 5m FVGs formed in the lunch hour are arrays too
                tops += S._SM3.lunch_fvg_tops(ctx, sd, i - 1, ref)
            if tops:
                out["pm_judas_array"] = float(max(tops))


# --- MSS reference (A19 parent, Ep08.4 origin, Ep07.6 SIBI, Ep08.16 higher-tf swing) -------------

def _tf_pivots(ctx, sd, m: int):
    key = ("tfp", m)
    if key not in sd._lz:
        sd._lz[key] = L.tf_pivots(ctx.idx, sd.h, sd.l, ctx.tf, m, sd.n)
    return sd._lz[key]


def mss_ref(ctx, sd, sw, i, p):
    """(ref_i, ref, real_pivot) from the setups_models reference rules, or None (the caller falls
    back to the A1 tier chain with mss_ref "stl"). Ep08.4 "origin" = leg_origin (anchored at the
    sweep extreme, review fix); "origin_max" = the first build's rule, kept as a value."""
    e = sw["ext_i"]
    if p.mss_ref_raid:                       # caption-gap A19-mss-when-raid-missing (010 ~41:31): the reference depends on whether the expected raid level was taken
        r_ = S._SM2.raid_ref(ctx, sd, sw, i, p)
        if r_ is not None:
            return r_
    m_tf = p.mss_ref_tf
    if p.micro_regime and ctx.tf < 5 and S._SM2.micro_active(ctx, sd, i, p):
        m_tf = 5                             # caption-gap N-micro-structure-regime (024 ~10:08): inside a small consolidation read the structure on the 5m chart
    if p.mss_ref_sibi:                       # Ep07.6 / M1: the small SIBI high the leg left
        hs = [q for q in sd.ph if q.i < e and q.known <= i]
        a = hs[-1].i if hs else max(0, e - 30)
        z = L.leg_sibi(sd.h, sd.l, sd.o, sd.c, a, e, sd.c2_dir)
        if z is not None:
            return z.src, z.top, True
    if m_tf and m_tf > ctx.tf:    # Ep08.16: the 5m swing (equal highs -> the higher)
        hs = [q for q in _tf_pivots(ctx, sd, m_tf)[0] if q.i < e and q.known <= i]
        if hs:
            q = hs[-1]
            if len(hs) > 1 and abs(hs[-2].price - q.price) <= p.eq_tol_pts * p.es_pt and hs[-2].price > q.price:
                q = hs[-2]
            return q.i, q.price, True
    if p.mss_ref in ("parent", "origin", "origin_max"):
        refs = [q for q in sd.ph if q.i < e and q.known <= i]
        if p.mss_ref == "parent":            # A19 [our interpretation]: walk back over lower highs
            if refs:
                k = len(refs) - 1
                while k - 1 >= 0 and refs[k - 1].price > refs[k].price:
                    k -= 1
                return refs[k].i, refs[k].price, True
        elif p.mss_ref == "origin":          # Ep08.4 (review fix: anchored at ext_i)
            q = leg_origin(sd, e, i)
            if q is not None:
                return q.i, q.price, True
        else:                                # "origin_max" (the first build): the highest swing high
            a = S._level_created(ctx, sw["key"], sw["session"]) if not sw.get(SYNTH) else ctx.start
            rr = [q for q in refs if q.i >= min(a, e - 1)]    # between the swept level's creation
            if rr:                                          # and the extreme [our interpretation]
                q = max(rr, key=lambda q: (q.price, q.i))
                return q.i, q.price, True
    return None


def leg_origin(sd, e: int, i: int):
    """Ep08.4 "the swing that originated the leg into the sweep extreme" [our interpretation of
    the walk-back]: from the last swing high before ext_i (known by bar i) walk back to earlier
    swing highs as long as the leg from that high down to ext_i stays one leg - no close above
    the high after it, and the swing lows after it (known by bar i) form a staircase of lower lows
    (no higher swing low intervened). The furthest such high is the origin. None if none."""
    hs = [q for q in sd.ph if q.i < e and q.known <= i]
    ls = [q for q in sd.pl if q.i < e and q.known <= i]
    best = None
    for q in reversed(hs):
        if sd.c[q.i + 1:e + 1].max(initial=-np.inf) >= q.price:
            break                                  # a close above it: the leg started later
        lows = [x.price for x in ls if x.i > q.i]
        if any(b > a for a, b in zip(lows, lows[1:])):
            break                                  # a higher swing low intervened
        best = q
    return best


def parent_high(sd, e: int, i: int):
    """Ep05.8: the parent swing high before bar e (start of the staircase of lower highs)."""
    refs = [q for q in sd.ph if q.i < e and q.known <= i]
    if not refs:
        return None
    k = len(refs) - 1
    while k - 1 >= 0 and refs[k - 1].price > refs[k].price:
        k -= 1
    return refs[k]


# --- break gates (A20, M0.4, M1.3, Ep07.6, A19.2, Ep01.22) -----------------------------------------

def drop_before_break(ctx, sd, sw, i, p) -> bool:
    """Timing rules while waiting for the MSS: True = drop the sweep. Ep07.6 mss_max_bars; M1.3
    speed_check (the leg's last SIBI closed above within speed_bars of the extreme)."""
    e = sw["ext_i"]
    if p.mss_max_bars and i - e > p.mss_max_bars:
        S._f("x_mss_slow")
        return True
    if p.speed_check:
        if sw.get("sibi_e") != e:
            hs = [q for q in sd.ph if q.i < e and q.known <= i]
            a = hs[-1].i if hs else max(0, e - 30)
            sw["sibi"], sw["sibi_e"] = L.leg_sibi(sd.h, sd.l, sd.o, sd.c, a, e, sd.c2_dir), e
        z = sw["sibi"]
        if z is not None:
            hit = np.flatnonzero(sd.c[e + 1:i + 1] > z.top)
            if (len(hit) and hit[0] + 1 > p.speed_bars) or (not len(hit) and i - e >= p.speed_bars):
                S._f("x_speed")
                return True
    return False


def break_ok(ctx, sd, sw, i, p, ref, lv: dict, tol: float, tk: float) -> bool:
    """Extra tests on the breaking candle i (side space). A20 disp_mult / disp_through_pts, M0.4
    disp_body_mult, Ep07.6 mss_disp, A19.2 mss_eq_wait, Ep01.22 clean_leg / clean_body."""
    o, h, l, c = sd.o, sd.h, sd.l, sd.c
    if p.disp_through_pts and c[i] - ref < p.disp_through_pts * p.es_pt - 1e-12:
        S._f("x_disp_through")
        return False
    if p.disp_mult or p.disp_body_mult:
        r = ob_low(sd, sw["ext_i"], S._LD4.disp_fvg_zone(sd, sw, i) if p.ob_outside_fvg else None)          # review fix: the OB at the sweep low, not the last
        if r is not None:                    # down-close candle before the break
            _, top, low = r
            body = top - low
            if body > 0:
                if p.disp_mult and c[i] - top < p.disp_mult * body:
                    S._f("x_disp_mult")
                    return False
                if p.disp_body_mult and abs(c[i] - o[i]) < p.disp_body_mult * body:
                    S._f("x_disp_body")
                    return False
    if p.mss_disp:
        a = max(0, i - 10)
        rng = h[a:i] - l[a:i]
        if len(rng) and h[i] - l[i] < p.mss_disp * float(rng.mean()):
            S._f("x_mss_disp")
            return False
    if sw.get("raid_disp") and not S._SM2.disp_break(ctx, sd, i):
        S._f("x_raid_no_disp")               # caption-gap A19-mss-when-raid-missing: with mss_ref_raid only a displacement break is an MSS (case B stresses it: the raid level untaken)
        return False
    if p.mss_eq_wait and not S._SM2.eq_wait_waived(ctx, sd, p):     # A19.2: the lower of relative equal lows still standing (caption-gap A19-mss-no-rel-sweep-with-htf-draw: waived with a locked draw its way)
        for k, v in lv.items():
            if v < sw["level"] - 1e-12 and sw["level"] - v <= tol and not S._thru(sw["ext"], v, tk):
                S._f("x_mss_eq_wait")
                return False
    if p.clean_leg >= 0 or p.clean_body:
        ks = np.arange(sw["ext_i"] + 1, i + 1)
        dn = ks[c[ks] < o[ks]]
        up = ks[c[ks] > o[ks]]
        if p.clean_leg >= 0 and len(dn) > p.clean_leg:
            S._f("x_clean_leg")
            return False
        if p.clean_body and len(dn) and len(up):
            if float((o[dn] - c[dn]).max()) > p.clean_body * float((c[up] - o[up]).mean()):
                S._f("x_clean_body")
                return False
    return True


def disp_ok_sb(sd, li: int, i: int, ref: float, p) -> tuple[bool, int | None]:
    """A20 "also in SB": the Silver Bullet's MSS (a close beyond ref after the leg extreme li) with
    disp_through_pts / disp_mult / disp_body_mult / mss_disp and disp_follow (the next candle
    closes above it, by bar i). Review fix: every breaking close after li is tried in turn and
    the first one that passes is the MSS (a weak first break no longer rejects a later candle
    that breaks with displacement). Returns (ok, breaking bar: the passing one, else the first)."""
    c = sd.c
    thr = ref + p.disp_through_pts * p.es_pt
    hit = np.flatnonzero(c[li + 1:i + 1] > (thr if p.disp_through_pts else ref))
    if not len(hit):
        return False, None
    sw = dict(ext_i=li, ext=float(sd.l[li]), level=-np.inf)
    q = Params_like(p, mss_eq_wait=False, clean_leg=-1, clean_body=0.0, disp_through_pts=0.0)
    for h_ in hit:
        k = li + 1 + int(h_)
        if not break_ok(None, sd, sw, k, q, ref, {}, 0.0, 0.0):
            continue
        if p.disp_follow and (k + 1 > i or not c[k + 1] > c[k]):
            continue
        return True, k
    return False, li + 1 + int(hit[0])


class Params_like:
    """A light read-only view of Params with a few fields overridden (no __post_init__)."""

    def __init__(self, p, **kw):
        self._p, self._kw = p, kw

    def __getattr__(self, k):
        return self._kw[k] if k in self._kw else getattr(self._p, k)


# --- Ep04.7 / A19.4 on side --------------------------------------------------------------------

def on_side_wait(ctx, sd, sw, i, p, wait: int):
    """Ep04.7 mss_on_side="require": after the first MSS (sw["broke"]) wait for a higher low, a
    second close above the high before it, and an FVG from that leg, with the first leg's FVG still
    open. Returns "wait", "drop" or None (ready: sw["leg2_from"] / sw["broke2"] / sw["f1"] set).
    Review fix: once ready, the first leg's FVG must still be open (no close below its bottom) on
    every later bar up to the arming bar - else the sweep is dropped; the caller measures the
    no-FVG timeout from the SECOND break (sw["broke2"])."""
    c, l, h = sd.c, sd.l, sd.h
    if sw.get("leg2_from") is not None:
        f1 = sw.get("f1")
        if f1 is not None and c[f1.i + 1:i + 1].min(initial=np.inf) < f1.bottom:
            return "drop"                      # the first leg's FVG closed through before arming
        return None
    b1, e = sw["broke"], sw["ext_i"]
    f1 = next((g for g in sd.gaps if g.i - 2 >= e and g.i <= i), None)
    if f1 is None:
        return "drop" if i - b1 >= wait else "wait"
    if c[f1.i + 1:i + 1].min(initial=np.inf) < f1.bottom:
        return "drop"                          # the first leg's FVG closed through
    if i - b1 > max(wait, p.pending_minutes // max(ctx.tf, 1)):
        return "drop"
    hl = next((q for q in sd.pl if q.i >= b1 and q.known <= i and q.price > sw["ext"]), None)
    if hl is None:
        return "wait"
    hh = h[e:hl.i].max(initial=-np.inf)
    brk = np.flatnonzero(c[hl.i + 1:i + 1] > hh)
    if not len(brk):
        return "wait"
    sw["broke2"] = hl.i + 1 + int(brk[0])
    sw["leg2_from"] = hl.i
    sw["f1"] = f1
    sw["on_side"] = True
    return None


def on_side_since(sd, o: dict, i: int) -> bool:
    """A19.4 tag: a second MSS (higher low, then a close above the high before it) between the
    first MSS and bar i-1 (closed bars before the fill), each leg leaving an FVG that is still
    open (no close below its bottom) through bar i-1 (review fix: the FVG part of "two MSSs each
    leaving an open FVG", 006 ~49:16). The first MSS bar is the order's own, or (owner #11 OB
    order armed before the break) the one its sweep printed later."""
    b1, e = o.get("broke"), o["ext_i"]
    if b1 is None:
        b1 = (o.get("sw_ref") or {}).get("broke")
    if b1 is None:
        return False
    hl = next((q for q in sd.pl if q.i >= b1 and q.known <= i - 1 and q.price > o["ext"]), None)
    if hl is None:
        return False
    hh = sd.h[e:hl.i].max(initial=-np.inf)
    k2 = np.flatnonzero(sd.c[hl.i + 1:i] > hh)
    if not len(k2):
        return False
    b2 = hl.i + 1 + int(k2[0])
    is_open = lambda g: sd.c[g.i + 1:i].min(initial=np.inf) >= g.bottom
    leg1 = any(g.i - 2 >= e and g.i <= hl.i and is_open(g) for g in sd.gaps)
    leg2 = any(g.i - 2 >= hl.i and g.i <= max(b2, i - 1) and is_open(g) for g in sd.gaps if g.i <= i - 1)
    return bool(leg1 and leg2)


# --- gap filters / picks / stops -----------------------------------------------------------------

def pick_2022(ctx, sd, sw, pick: list, i: int, p):
    """M2 / M2.3 FVG choice (022 ~55:00; 042 ~47:20; 082 ~5:31): (1) a gap aligned with a VI and
    the OB (a VI within one bar of its middle candle, the OB touching the gap), (2) else the first
    gap in the leg's discount (top at or below the leg EQ), (3) else the deeper of the last two."""
    o, h, l, c = sd.o, sd.h, sd.l, sd.c
    e = sw["ext_i"]
    if p.m2_anchor == "runup":                       # caption-gap M2-pyramid-runup-leg-eq (022 ~01:03:28): the EQ of the run into the swept pool - a VI first, else the FVG
        r_ = S._SM4.runup_pick(ctx, sd, sw, pick, i, p)
        if r_ is not None:
            return r_
    leg_hi = h[e:i + 1].max()
    eq = sw["ext"] + 0.5 * (leg_hi - sw["ext"])
    vis = [z for z in sd.vis("bull") if z.i <= i]
    r = ob_low(sd, e, S._LD4.disp_fvg_zone(sd, sw, i) if p.ob_outside_fvg else None)       # review fix: the OB at the sweep low (not a pullback candle)
    ob = None if r is None else r[0]
    tk = 0.25 * p.es_pt
    a = [g for g in pick if any(abs(z.i - g.src) <= 1 for z in vis)
         and ob is not None and ob.top >= g.bottom - tk and ob.bottom <= g.top]
    if a:
        return a[-1]
    d = [g for g in pick if g.top <= eq]
    if d:
        return d[0]
    return min(pick[-2:], key=lambda g: g.top) if len(pick) >= 2 else pick[-1]


def ifvg_filter(ctx, sd, sw, gaps, i, p):
    """A8 ifvg_hold (no close back below the IFVG top since the inversion) and ifvg_after_htf
    (only once the sweep reached an HTF array) on the inversion zones of `gaps`."""
    native = set(id(g) for g in sd.gaps) | set(id(z) for z in sd._lz.get("implied", []))   # A24.1
    out = []
    htf = None
    sym = bool(p.ifvg_symmetry_skip and S._SM4.symmetric(ctx, sd, i, p))     # caption-gap A8-symmetry-skip-ifvg-confirmation: the indices agree - the inversion steps are skipped
    for g in gaps:
        if id(g) in native or sym:
            out.append(g)
            continue
        if p.ifvg_hold and (sd.c[g.i + 1:i + 1] < g.top).any():
            continue
        if p.ifvg_after_htf:
            if htf is None:
                htf = bool(S._htf_tag(ctx, sd, i, sw["ext"], p.eq_tol_pts * p.es_pt))
            if not htf:
                continue
        out.append(g)
    return out


def ifvg_stop(sd, g, entry: float, stop: float, p, i: int | None = None):
    """M10 / A8 entry and stop for an inversion FVG: ifvg_entry "ce"; ifvg_depth (no prior pass ->
    the far edge, else the CE); ifvg_stop_pts beyond the CE."""
    ce = (g.top + g.bottom) / 2
    if p.ifvg_entry == "ce":
        entry = ce
    elif p.ifvg_entry == "quadrant":         # caption-gap A8-ifvg-narrative-liquidity-run (078 ~51:00): long entries at H, the upper quadrant or the CE
        entry = g.q(0.75)
        S._SM2.hit("ifvg_quadrant")
    if p.ifvg_depth == "w_cap":              # caption-gap A8-ifvg-depth-tolerances (102 ~1:11:04): cases a / b / c with the W cap; None = the retrace went too deep
        r_ = S._SM2.ifvg_w_cap(sd, g, entry, stop, i, p)
        if r_ is None:
            return None
        entry, stop = r_
    elif p.ifvg_depth:
        orig = g.src + 1                     # the original gap's third candle
        ps = L.ifvg_passes(sd.h, sd.l, g.top, g.bottom, orig, g.i)
        stop = (g.bottom if ps == "none" else ce) - p.pad
    if p.ifvg_stop_pts:
        stop = ce - p.ifvg_stop_pts * p.es_pt - p.pad
    if p.ifvg_stop == "far":                 # caption-gap M10-ifvg-stop-below-whole-ifvg (067 ~01:19:07): "my stop loss is below the inversion fair value gap" - the whole IFVG, never tightened inside it
        stop = g.bottom - p.pad
        S._ES2.hit("ifvg_stop_far")
    if stop >= entry:
        stop = g.bottom - p.pad
    return entry, stop


def ifvg_061(ctx, sd, sw, i, p, session, risk_mult):
    """M10 061 signature (061 ~2:15:00): an inversion FVG (after the sweep) with a normal bullish
    FVG below it; a body close at that FVG's high / CE (bar i, after the inversion) triggers a
    market entry; stop below the lower FVG."""
    c = sd.c
    tol = p.eq_tol_pts * p.es_pt
    for z in reversed([z for z in sd.ifvgs() if sw["ext_i"] < z.i < i]):
        lows = [g for g in sd.gaps if g.i <= i and g.top <= z.bottom + tol and g.i - 2 >= sw["ext_i"] - 3
                and c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom]
        if not lows:
            continue
        f = max(lows, key=lambda g: g.top)
        if not (f.mid <= c[i] <= f.top + tol and min(sd.o[i], c[i]) >= f.mid - 1e-12):
            continue
        stop = f.bottom - p.pad
        if p.ifvg_061_entry == "iofed":       # caption-gap M10-ifvg-fvg-signature-full (061 ~02:18:22): the IOFED limit instead of the market entry
            return S._SM5.ifvg_061_iofed(ctx, sd, sw, f, i, p, session, risk_mult)
        tags = dict(unicorn=False, fvg_bottom=f.bottom, fvg_ce=f.mid, entry_kind="ifvg_061", mitigation=False,
                    propulsion=False, market=True, no_leg_wait=True)
        return S._finish_order(ctx, sd, i, p, session, sw, float(c[i]), stop, risk_mult,
                               sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)
    return None


# --- OTE (M13) -----------------------------------------------------------------------------------

def ote_adjust(sd, sw, i, p, entry, stop, kind, lvt):
    """M13 ote filter / limit, leg_pd_strict, ote_leg_stop, ote_stack_tag. Returns (entry, stop)
    or None (rejected)."""
    e = sw["ext_i"]
    leg_hi = float(sd.h[e:i + 1].max())
    base = S._LD.leg_low(sd, sw, i, p, leg_hi)       # caption-gap A21 leg_anchor: the dealing range's low ("mss_leg" = the sweep extreme)
    if p.leg_fib == "body":                          # review fix (A21-intraday-fib-bodies, 058 ~41:48): the OTE band / leg_pd_strict read the same body leg as leg_pd (the lowest min(o, c) .. highest max(o, c) since the sweep extreme)
        b_lo, b_hi = S._ES1.body_leg(sd, sw, i)
        leg_hi = b_hi
        if p.leg_anchor != "energetic":
            base = b_lo
    if p.ote_gate_4th and p.ote != "off" and not S._ES1.ote_gate_ok(sd, sw, i, p):
        S._f("x_ote_gate")                           # caption-gap M13-swing-confirm-gate: the far extreme is not yet a 3-candle swing confirmed by the 4th candle - earlier dips are ignored
        sw["_ote_wait"] = True                       # (the caller keeps the sweep alive: the same gap is judged again on the next bar)
        return None
    lo, hi, sweet = L.ote_band(base, leg_hi)
    if p.ote_nested and p.ote != "off":              # caption-gap M13-nested-ranges: the parent swing and its live child legs; the band is the one that holds the entry (limit: the nearest sweet spot under the market)
        if p.ote == "filter":
            b_ = S._ES1.ote_band_for(sd, sw, i, p, entry, base, leg_hi)
            if b_ is None:
                S._f("x_ote")
                return None
            base = b_
        else:
            bs_ = [(L.ote_band(b_, leg_hi)[2], b_) for b_ in S._ES1.ote_children(sd, sw, i) + [base]]
            bs_ = [t_ for t_ in bs_ if t_[0] < sd.c[i]]
            if bs_ and max(bs_)[1] != base:
                S._ES1.hit("ote_child")
                base = max(bs_)[1]
        lo, hi, sweet = L.ote_band(base, leg_hi)
    if p.ote == "limit":
        if p.ote_need_trigger and not S._SM6.ote_trigger_ok(sd, sw, i, hi):
            S._f("x_ote_no_trigger")                 # caption-gap M13-ote-needs-bias-trigger-structure: OTE is context, not an entry - wait for an LTF MSS inside the band
            return None
        if sweet < sd.c[i]:
            entry = sweet
        if p.ote_fvg_overlap:                        # caption-gap M13-pattern1-full-sequence-ote-fvg: the 70.5 % limit only where it overlaps an FVG of the leg, else the FVG edge nearest it
            e7 = S._SM7.ote_overlap(sd, sw, i, p, lo, hi, sweet, entry)
            if e7 is None:
                S._f("x_ote_no_fvg_overlap")
                return None
            entry = e7 if e7 < sd.c[i] else entry
    elif p.ote == "filter" and not (lo - 1e-12 <= entry <= hi + 1e-12):
        S._f("x_ote")
        return None
    if p.ote_need_s and not S._SM7.ote_s_ok(sd, sw, i, p):
        S._f("x_ote_no_s")                           # caption-gap M13-pattern1-full-sequence-ote-fvg: no short-term low S taken before the order = the lower-probability version
        return None
    if p.ote_parent_third and not S._ES1.parent_third_ok(sd, sw, i, p, entry, leg_hi, base):
        S._f("x_ote_parent_third")                   # caption-gap M13-nested-ranges (cc01_006 ~13:16): not in the lower third of the parent swing and under the EQ of the small range
        return None
    if p.leg_pd_strict and not entry < base + 0.5 * (leg_hi - base) - 0.25 * p.es_pt + 1e-12:
        S._f("x_leg_pd_strict")
        return None
    if p.ote_leg_stop:
        stop = sw["ext"] - p.pad
    if stop >= entry - p.min_risk_pts * p.es_pt:
        stop = min(stop, sw["ext"] - p.pad)
    # review fix: any swept sell-side pool of the sweep machine counts as the "swept low" (PDL,
    # London, overnight, swing / rel-eq lows ...), not only swing_low / rel_eq keys; synthetic never
    if p.ote_stack_tag and lo <= entry <= hi and kind in ("fvg", "ifvg") and S._ob_at_low(sd, sw, i) is not None \
            and not sw.get(SYNTH):
        lvt.append("ote_stack")
    return entry, stop


# --- entry arrays (M0.5 / M5.2 / A18), reaper (A24.2), breakers (M4.1 / M4.3 / M4.5) --------------

def array_cands(ctx, sd, sw, i, p, bz) -> list:
    """M0.5 [our interpretation of "enter on any PD array"]: (entry, bottom, kind) of each listed
    array after the MSS that sits between the sweep extreme and the last close."""
    ea = set(p.entry_arrays) | ({"reclaimed_ob"} if p.reclaimed_ob else set()) |         ({"ob"} if "ob" in p.irl_entries else set())            # L14b: the OB is an allowed IRL entry
    e, ext = sw["ext_i"], sw["ext"]
    out = []
    if "ob" in ea:
        ob = S._ob_at_low(sd, sw, i, p, ctx)
        if ob is not None and S._ES1.ob_gate_on(p) and not S._ES1.ob_gate(ctx, sd, sw, ob, i, p):
            ob = None                                         # review fix (A12-ob-requires-signatures / narrative): the array "ob" is a potential OB until the gates pass
        if ob is not None:
            sw_e = S._ES2.ob_swept_entry(sd, ob, p)           # caption-gap A12-mt-retrace-after-stop-run: a swept OB candle is bought at its body MT
            out.append((sw_e if sw_e is not None else ob["body_top"], ob["body_low"], "ob"))
            sw["_es2_ob"] = ob
    if p.cons_ob_open or "cons_ob_open" in ea:       # caption-gap A12: the open of the last candle before a 1h consolidation is support
        for v, kd in S._LD.cons_ob_levels(ctx, sd, i, p):
            if kd == ("bull" if sd.sign > 0 else "bear"):
                out.append((v, v, "cons_ob_open"))
    if "breaker" in ea and bz is not None:
        out.append((bz.top, bz.bottom, "breaker"))
    if "ote" in ea and (not p.ote_gate_4th or S._ES1.ote_gate_ok(sd, sw, i, p)):     # review fix (M13-swing-confirm-gate): the OTE array waits for the 4th candle too
        out.append((L.ote_band(ext, float(sd.h[e:i + 1].max()))[2], ext, "ote"))
    if "broken_wick_ce" in ea and sw.get("broke") is not None and sw.get("ref_i") is not None:     # caption-gap A23-broken-wick-ce-inversion (043 ~10:45; 044 ~46:41): the swing the MSS broke - the CE of its wick is now support
        r_ = S._ES1.broken_wick_cand(sd, sw, i, p)
        if r_ is not None:
            out.append(r_)
    if p.wick_ce_mode == "retrace" and sw.get("_nofvg") and "wick_ce" not in ea:
        S._SM2.hit("wick_ce_retrace")
    if "wick_ce" in ea or (p.wick_ce_mode == "retrace" and sw.get("_nofvg")):     # caption-gap M11-wick-ce-fade-short (042 ~00:33:56): after an MSS that left no FVG the sweep candle's wick CE is the entry
        out.append((L.wick_ce(sd.o, sd.l, sd.c, e), ext, "wick_ce"))
    if "ob_post" in ea and sw.get("broke") is not None:      # caption-gap M1-ob-entry-after-mss (020 ~00:06:14): the first down-close candle of the pullback after the MSS
        r = S._SM4.ob_post_cand(ctx, sd, sw, i, p)
        if r is not None and S._ES1.ob_gate_on(p) and not S._ES1.ob_gate(ctx, sd, sw, dict(k=int(sw["_ob_post_k"]), body_top=r[0], body_low=r[1]), i, p):
            r = None                                          # review fix (A12-ob-requires-signatures / narrative): the post-MSS OB candle needs the same signatures / narrative
        if r is not None:
            S._SM2.hit("ob_post")
            out.append(r)
    if "htf" in ea:                                          # caption-gap B5-ltf-at-htf-array (082 ~00:06:22): the 15m / 60m arrays carried onto the execution chart
        out += S._SM5.htf_cands(ctx, sd, sw, i, p)
    if "mitigation" in ea:                                   # caption-gap A15-mitigation-block-entry (098 ~00:45:55)
        r_ = S._SM5.mit_cand(ctx, sd, sw, i, p)
        if r_ is not None:
            out.append(r_)
    if p.prop_fail_flip:                                     # caption-gap A16-propulsion-block-full: the failed propulsion block, a reclaimed array of the flipped side
        r_ = S._ES1.pb_flip_cand(ctx, sd, i, p)
        if r_ is not None:
            out.append(r_)
    out += S._SM6.arr_cands6(ctx, sd, sw, i, p, ea)           # caption-gap setups_models #6/7: ob_secondary / propulsion / last_offer arrays, the ote "ob62" body stall
    if "vi_ob" in ea:                                      # caption-gap E12-second-stage-ob-at-MT (009 ~00:11:15): the down-close candle that traded into an intact VI of the leg, standalone
        r_ = S._ES2.vi_ob_cand(sd, sw, i, p)
        if r_ is not None:
            out.append(r_)
    if "vi" in ea:
        vs = [z for z in sd.vis("bull") if e <= z.i <= i and not (p.vi_breakaway and S._LD3.vi_is_breakaway(sd, sw, z, i))]   # A9 vi_breakaway
        if vs:
            out.append((vs[-1].top, vs[-1].bottom, "vi"))
    if "reclaimed_ob" in ea:
        hs = [q for q in sd.ph if q.i < e and q.known <= i]
        a = hs[-1].i if hs else max(0, e - 30)
        rs = S._SM2.reclaimed_zones(sd, a, e, i, p)          # caption-gap A18-reclaimed-ob-codeable: strict (cc04_007) / loose (006)
        if rs:
            z = max(rs, key=lambda z: z.top)
            out.append((z.top, z.bottom, "reclaimed_ob"))
    if p.org_entry_array:                                  # caption-gap L7-org-later-day-entry-array (080 ~13:20; 092 ~1:59:32): the unfilled part of a prior ORG, never alone
        out += S._SM3.org_cands(ctx, sd, sw, i, p, out)
    return [x for x in out if ext < x[0] < sd.c[i]]


def array_order(ctx, sd, sw, i, p, session, risk_mult, fvg_entry, bz):
    """The highest array entry (the first the retrace reaches) when it beats the FVG entry (or
    there is no FVG). Stop below the array (OB MT rule kept), else below the sweep extreme."""
    cs = [x for x in array_cands(ctx, sd, sw, i, p, bz) if fvg_entry is None or x[0] > fvg_entry]
    if cs and p.entry_pick == "shallowest_unused":
        cs = S._SM4.unused_cands(ctx, sd, sw, i, p, bz, cs)        # caption-gap M5-lasthour-shallowest-unused-array (030 ~00:21:36): arrays price already traded back into are dropped
    if not cs:
        return None
    entry, bottom, kind = S._SM6.pick_array(cs, p) if p.entry_arrays_order else max(cs)       # caption-gap A15-mitigation-block-sell-entry: entry_arrays_order
    stop = bottom - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = sw["ext"] - p.pad
    tags = dict(unicorn=False, fvg_bottom=bottom, fvg_ce=(entry + bottom) / 2, entry_kind="arr_" + kind,
                mitigation=False, propulsion=False)
    if kind == "ob" and p.ob_grade_mult != (1.0, 1.0) and sw.get("_es2_ob") is not None:
        S._ES2.tag(tags, **S._ES2.ob_grade_tags(sw["_es2_ob"]))     # caption-gap A12-mt-grading
    S._SM6.array_tags(sw, kind, tags)                  # caption-gap A12-secondary-ob / A16-propulsion-entries: a body close under the candle's MT cancels
    if kind == "ob_post" and sw.get("_ob_post_mt") is not None:
        tags["cancel_close"] = float(sw["_ob_post_mt"])           # a body close under the candle's MT invalidates (A12)
    if kind == "broken_wick_ce":
        tags["cancel_close"] = float(sw["_bwc_edge"])             # caption-gap A23-broken-wick-ce-inversion: a body close beyond the wick's body edge voids the inversion level
    if kind == "reclaimed_ob" and p.reclaimed_def != "strict":
        tags["lv_tags"] = ["reclaimed_" + p.reclaimed_def]         # caption-gap A18-reclaimed-ob-codeable: which definition was used (the strict default stays untagged, as built)
    o_ = S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult,
                         sd.h[sw["ext_i"]:i + 1].max(), tags, pctx_free=True)
    if o_ is not None:
        S._SM6.chosen(sw, kind, entry)                # caption-gap setups_models #6/7 review fix: the counters of the new array kinds count an order that was built
    return o_


def _l1(sd, ref_i, i):
    l1 = [q for q in sd.pl if q.i < ref_i and q.known <= i]
    return l1[-1] if l1 else None


def reaper_order(ctx, sd, sw, i, p, session, risk_mult, ref_i, real_ref, wait: int):
    """A24.2 Reaper: the FVG in the discount half of the breaker's impulse leg L1 -> H that price
    cut through on the way to the lower low. After the MSS: a limit at its top, stop below it, out
    on a body close below its CE (bodies stay above); reaper_confirm = only after a reaction candle
    (a wick into it, a close at or above its CE) -> market entry. "wait" while confirming."""
    if p.reaper_def == "ob_overlap":         # caption-gap A24-reaper-definition option B (081 ~11:49): the breaker zone (lowest-close down candle) coincides with an order block
        if sw.get("reaper_ob_sent"):
            return None
        bz = S._breaker(ctx, sd, sw, ref_i, real_ref, i, p)
        ob = S._ob_at_low(sd, sw, i, p, ctx)
        if bz is None or ob is None or not (ob["body_low"] < bz.top and ob["body_top"] > bz.bottom) or bz.top >= sd.c[i]:
            return None
        sw["reaper_ob_sent"] = True
        S._SM2.hit("reaper_ob")
        tags = dict(unicorn=False, fvg_bottom=bz.bottom, fvg_ce=bz.mt, entry_kind="reaper_ob", mitigation=False, propulsion=False, no_leg_wait=True,
                    lv_tags=["reaper_ob"])
        stop = bz.bottom - p.pad
        if bz.top - stop < p.min_risk_pts * p.es_pt:
            stop = sw["ext"] - p.pad
        return S._finish_order(ctx, sd, i, p, session, sw, bz.top, stop, risk_mult, sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)
    q = _l1(sd, ref_i, i)
    if q is None or not real_ref or not sw["ext"] < q.price:
        return None
    if sw.get("reaper_e") != sw["ext_i"]:
        sw["reaper"] = L.reaper(sd.o, sd.h, sd.l, sd.c, q.i, ref_i, sw["ext_i"], sd.c2_dir)
        sw["reaper_e"] = sw["ext_i"]
    z = sw["reaper"]
    if z is None or sw.get("reaper_dead"):
        return None
    market = False
    entry = z.top
    if p.reaper_confirm:
        # review fix: the reaction candle (a wick into the Reaper, a close at or above its CE -
        # the textbook confirmation closes between the CE and the top) is tested BEFORE any
        # "price above the top" check; while the Reaper stands unconfirmed the sweep waits
        # ("wait", the ordinary FVG path does not consume it)
        b = sw["broke"]
        if i > b and sd.l[i] <= z.top and sd.c[i] >= z.mid:
            market, entry = True, float(sd.c[i])
        elif i > b and sd.c[i] < z.mid:
            sw["reaper_dead"] = True           # a body close below its CE: the Reaper failed -
            return None                        # the ordinary FVG path may still use the sweep
        else:
            return "drop" if i - b > max(wait, p.pending_minutes // max(ctx.tf, 1)) else "wait"
    elif z.top >= sd.c[i]:
        return None
    tags = dict(unicorn=False, fvg_bottom=z.bottom, fvg_ce=z.mid, entry_kind="reaper", mitigation=False,
                propulsion=False, market=market, no_leg_wait=True, lvx={"reaper_ce": (z.mid, True)})
    return S._finish_order(ctx, sd, i, p, session, sw, entry, z.bottom - p.pad, risk_mult,
                           sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


def adv_breaker_order(ctx, sd, sw, i, p, session, risk_mult, ref_i, ref, real_ref):
    """M4.3 advanced breaker (070 ~34:59-1:08:31): A = the swing low L1, B = the high H (the MSS
    reference); limit at the A-B leg MT that needs 1 tick through to fill, stop beyond L2 (the
    sweep extreme), target B + 1x(B - A). The A-B pre-break / bias-on-side entry is not built."""
    q = _l1(sd, ref_i, i)
    if q is None or not real_ref or not sw["ext"] < q.price:
        return None
    A, B = q.price, ref
    note5 = None
    if p.ab_anchor_lock:             # caption-gap M4-unfinished-high-keep-ab-leg (070 ~00:52:42): a filled order's A-B leg stays the anchor while the locked target is untaken
        ses_ = getattr(ctx, "cur_session", "") or session
        A, B = S._SM5.ab_anchor(ctx, sd, A, B, i, p, ses_)
        note5 = S._SM5.ab_note(ctx, sd, A, B, ses_)
    mt = (A + B) / 2
    tk = 0.25 * p.es_pt
    tgt = B + (B - A)
    fixed = [(S._exit_px(tgt, "array", p), "array")]
    tags = dict(unicorn=False, fvg_bottom=A, fvg_ce=mt, entry_kind="adv_breaker", mitigation=False,
                propulsion=False, through=tk, no_leg_wait=True)
    if note5 is not None:
        tags["sm5"] = note5
    if p.adv_rungs:                      # caption-gap E12-070-rung-order (070 ~00:58:44): 5m FVG CE, 1m IFVG CE, the IFVG's low end - three resting limits (sizes adv_rung_fracs)
        lad7 = S._SM7.adv_ladder(ctx, sd, sw, i, p, A, B, sw["ext"] - p.pad)
        if lad7 is not None:
            return S._finish_order(ctx, sd, i, p, session, sw, lad7[0][0], sw["ext"] - p.pad, risk_mult, sd.h[sw["ext_i"]:i + 1].max(),
                                   dict(tags, ladder=list(lad7[0]), ladder_fracs=lad7[1]), skip_leg_pd=True, fixed=fixed)
    return S._finish_order(ctx, sd, i, p, session, sw, mt, sw["ext"] - p.pad, risk_mult,
                           sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


def adv_breaker_pre(ctx, sd, sw, i, p, session, risk_mult, ref_i, ref, real_ref):
    """M4.3 advanced breaker, the "bias on side" entry (070 ~34:59-1:08:31: "with bias on side you
    may buy inside the A-B leg or on the sell-side run without waiting for the break and retest")
    [our interpretation of the trigger]: bias on side = the locked draw / htf bias this way
    (ctx.cur_bias); A = the swing low L1 before the reference high B. After the run below A (the
    sweep extreme L2 < A), the FIRST close back above A - price back inside the A-B leg, B not yet
    broken - enters at market (next open); stop beyond L2; target B + 1x(B - A). Once per sweep
    extreme."""
    if getattr(ctx, "cur_bias", 0) != sd.sign or i <= sw["ext_i"]:
        return None
    q = _l1(sd, ref_i, i)
    if q is None or not real_ref or not sw["ext"] < q.price:
        return None
    k = np.flatnonzero(sd.c[sw["ext_i"] + 1:i + 1] > q.price)
    if not len(k) or sw["ext_i"] + 1 + int(k[0]) != i or not sd.c[i] < ref:
        return None
    sw["adv_pre_sent"] = True
    A, B = q.price, ref
    fixed = [(S._exit_px(B + (B - A), "array", p), "array")]
    tags = dict(unicorn=False, fvg_bottom=A, fvg_ce=(A + B) / 2, entry_kind="adv_breaker_pre", mitigation=False,
                propulsion=False, market=True, no_leg_wait=True)
    return S._finish_order(ctx, sd, i, p, session, sw, float(sd.c[i]), sw["ext"] - p.pad, risk_mult,
                           sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


def cc_breaker_order(ctx, sd, sw, i, p, session, risk_mult, ref):
    """M4.5 breaker swing (cc05_005) [CC]: the drive took the low into the key level, then broke
    the in-between high: buy the retest of that breaking point (the reference high), stop below
    the new low."""
    tags = dict(unicorn=False, fvg_bottom=sw["ext"], fvg_ce=(ref + sw["ext"]) / 2, entry_kind="cc_breaker_swing",
                mitigation=False, propulsion=False, no_leg_wait=True)
    entry = S._SM6.near_ob_entry(sd, sw, i, ref, p) if p.cc_near_ob else ref      # caption-gap M4-retest-nearer-ob-or-none: OCO with the break leg's nearer OB
    if p.breaker_iofed and entry + p.tick < sd.c[i]:
        entry += p.tick                                # caption-gap E2-iofed-breaker-exact-match (043 ~00:16:21): 1 tick inside the level, so an exact match fills
        S._ES2.hit("breaker_iofed")
    return S._finish_order(ctx, sd, i, p, session, sw, entry, sw["ext"] - p.pad, risk_mult,
                           sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


def cc_failure_order(ctx, sd, i, p, session, risk_mult):
    """M4.5 failure swing (cc05_005) [CC]: a higher low B that failed to reach an intact sell-side
    pool (within cc_fail_pts above it), then the first close above the swing high H before B (the
    breaking point; both drawn before price arrives): buy the retest of H, stop below B."""
    ss = S._sess_start(ctx, i)
    if ss is None:
        return None
    tk = S._tick(p)
    lv = S._sell_side(ctx, sd, session, i, p.extra_pools, p)
    used = sd.__dict__.setdefault("_ccf", set())
    nne = p.fs_def == "no_new_extreme"       # caption-gap M4: the earlier swing reached / traded through K, so K need not be intact
    for k, v in sorted(lv.items(), key=lambda kv: -kv[1]):
        if v >= sd.c[i] or (not nne and not S._level_intact(ctx, sd.l, i + 1, k, v, session, tk)):
            continue
        r = L.failure_swing(sd.ph, sd.pl, v, p.cc_fail_pts * p.es_pt, i, ss, p.fs_def)
        if r is None:
            continue
        B, H = r
        if B.i in used or not sd.c[i] > H.price:
            continue
        if p.fs_sweep_close and nne:                  # caption-gap M4-immediate-response-swept-extreme (cc05_005 ~14:40; management#88 daily clause): the bar of the sweep (the earlier swing low L1
            prior = [q for q in sd.pl if q.i < H.i and q.known <= i and q.i >= ss]      # that traded through K) must CLOSE back above K - no lingering under it [our interpretation of "closes back above L1"]
            if not prior or not sd.c[prior[-1].i] > v:
                continue
            S._SM2.hit("fs_sweep_close")
        # review fix: the swing low B is confirmed only pivot_n bars after it prints, and the
        # break of H often comes inside those bars - arm on the first bar where BOTH are known
        # (B confirmed and a close above H since B), not only when the first close above H is
        # itself the current bar (which made the setup unreachable after a fast break)
        kk = np.flatnonzero(sd.c[B.i:i + 1] > H.price)
        if not len(kk) or i != max(B.i + int(kk[0]), B.known):
            continue
        used.add(B.i)
        sw = dict(session=session, name="cc_failure", level=v, key=k, ext=B.price, ext_i=B.i, broke=i,
                  sweep_i=B.i, smt=None, smt2=None, **{SYNTH: True})
        tags = dict(unicorn=False, fvg_bottom=B.price, fvg_ce=(H.price + B.price) / 2,
                    entry_kind="cc_failure_swing", mitigation=False, propulsion=False, no_leg_wait=True)
        return S._finish_order(ctx, sd, i, p, session, sw, H.price, B.price - p.pad, risk_mult,
                               sd.h[B.i:i + 1].max(), tags, skip_leg_pd=True)
    return None


# --- pre-break entries (M16.1 SMT, M11b CISD OB, M11c wick CE) -------------------------------------

def pre_break(ctx, sd, sw, i, p, session, risk_mult, ref):
    """Entries that do not wait for the body MSS. Each fires once per sweep extreme."""
    if p.smt_entry and not sw.get("smt_sent"):
        o_ = _smt_order(ctx, sd, sw, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    if p.cisd_ob_entries and (not sw.get("cisd_sent") or p.cisd_rearm):
        o_ = _cisd_ob(ctx, sd, sw, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    if p.wick_ce_entries and (p.wick_ce_tf or p.wick_ce_mode == "intrabar"):
        o_ = S._SM4.wick_ce_entry(ctx, sd, sw, i, p, session, risk_mult, ref)         # caption-gap M11-wick-ce-fade-short / new-sweep-wick-ce-failure-swing-long
        if o_ is not None:
            return o_
    elif p.wick_ce_entries and not sw.get("wce_sent") and i == sw["ext_i"] + 1:
        sw["wce_sent"] = True
        e = sw["ext_i"]
        ce = L.wick_ce(sd.o, sd.l, sd.c, e)
        if sd.c[i] > ce:
            tgt = ref - 0.5 * p.es_pt                    # "TP ~0.5 pt before the high" (100 ~38:13)
            tags = dict(unicorn=False, fvg_bottom=sw["ext"], fvg_ce=ce, entry_kind="wick_ce", mitigation=False,
                        propulsion=False, no_leg_wait=True)
            return S._finish_order(ctx, sd, i, p, session, sw, ce, sw["ext"] - p.pad, risk_mult,
                                   sd.h[e:i + 1].max(), tags, skip_leg_pd=True, fixed=[(tgt, "array")])
    return None


def _smt_order(ctx, sd, sw, i, p, session, risk_mult):
    """M16.1 CC AM SMT (cc10_011 ~8:01-18:36; cc10_014 ~1:15) [CC]: the sweep of the 05:00-09:30 low
    (or London / the overnight low) the sister index did not confirm (sw["smt"] True), on the
    allowed symbols; a buy STOP above the high of the last down-close candle since the low, or
    (smt_turtle) a turtle-soup limit at the swept level; stop below the low; out at smt_exit."""
    if session != "AM" or sw.get("smt") is not True or sw["key"] not in ("l0500", "london", "premarket"):
        return None
    if str(getattr(ctx, "symbol", "")).upper() not in {s.upper() for s in p.smt_entry_syms}:
        return None
    e = sw["ext_i"]
    o, h, l, c = sd.o, sd.h, sd.l, sd.c
    stop = sw["ext"] - p.pad
    if p.smt_turtle:
        if not L.turtle_soup(l, c, sw["level"], e, i, p.ts_max_pts * p.es_pt, p.ts_back_bars):
            return None
        entry, kind, extra = sw["level"], "smt_turtle", {}
    else:
        dn = [k for k in range(e, i + 1) if c[k] < o[k]]
        if not dn:
            return None
        entry = float(h[dn[-1]]) + 0.25 * p.es_pt
        if entry <= c[i]:
            return None
        kind, extra = "smt_stop", {"stop_entry": True}
    sw["smt_sent"] = True
    # review fix: the [CC] 2017 model has no PO3 open filter - with it the buy stop above the
    # down-close candle was rejected on most ES days (x_wrong_side_of_open, 2023)
    tags = dict(unicorn=False, fvg_bottom=sw["ext"], fvg_ce=(entry + sw["ext"]) / 2, entry_kind=kind,
                mitigation=False, propulsion=False, exit_at=p.smt_exit, no_leg_wait=True,
                skip_po3=not p.synth_po3, **extra)
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, max(h[e:i + 1].max(), entry),
                           tags, skip_leg_pd=True)


def _cisd_ob(ctx, sd, sw, i, p, session, risk_mult):
    """M11b CISD OB (075 ~1:16:40): the down-close series into the low; the first trade above its
    open (wick CISD) validates it; limit at min(EQ of the post-CISD range, OB top); a trade below
    the OB low cancels; stop below the OB low."""
    o, h, l, c = sd.o, sd.h, sd.l, sd.c
    e = sw["ext_i"]
    if i <= e:
        return None
    ob = L.order_block_blend(o, h, l, c, e - 5, e, "bull")
    if ob is None:
        return None
    if S._ES1.ob_gate_on(p) and not S._ES1.ob_gate(ctx, sd, sw, dict(k=int(ob.src), body_top=float(ob.top), body_low=float(ob.bottom)), i, p):
        return None                                 # review fix (A12-ob-requires-signatures / narrative): the CISD OB is a potential OB until the gates pass
    if p.cisd_need_htf and not S._SM5.cisd_htf_ok(ctx, sd, sw, i, p):
        return None                                 # caption-gap M11-cisd-ob-stop-skip-rearm: the sweep must sit in a same-side HTF array
    top, _ = _ob_body(o, c, ob, e)
    open_mode = p.cisd_ob_px == "open"
    if open_mode:
        top = float(o[ob.src])                       # caption-gap A12-cisd-open-buy-level (032 ~53:04): open_ref = the open of the first (highest) candle of the down-close run
    fl = S._SM5.cisd_floor(sw, e, ob.bottom, sd, i, p)       # caption-gap M11-cisd-ob-stop-skip-rearm: a trade under the OB low voids the setup; the next CISD must come after it
    if sw.get("cisd_sent") and not fl > sw.get("cisd_floor", e):
        return None
    if fl > sw.get("cisd_floor", e):
        S._SM2.hit("cisd_rearm")
    sw["cisd_floor"] = fl
    hit = np.flatnonzero(h[fl + 1:i + 1] >= top + p.tick - 1e-9) if open_mode else np.flatnonzero(h[fl + 1:i + 1] > top)       # (open mode: CISD = high >= open_ref + 1 tick)
    if not len(hit):
        return None
    first_ = fl + 1 + int(hit[0])
    if first_ != i and not (open_mode and first_ < i and sw.get("cisd_open_wait") == fl):
        return None                                 # arm on the CISD bar itself, once (open mode: or on a later bar while the wait below holds)
    rng_hi = float(h[e:i + 1].max())
    entry = top if open_mode else min((sw["ext"] + rng_hi) / 2, ob.top)
    if open_mode and entry >= c[i]:
        sw["cisd_open_wait"] = fl                   # review fix (A12-cisd-open-buy-level): the CISD bar closed back at / under the open - the buy limit would sit above the market; the CISD is NOT consumed, the order is armed on the first later bar that closes above the open (a body close under the run low voids it, floor)
        S._ES1.hit("cisd_open_wait")
        return None
    sw["cisd_sent"] = True
    sw["cisd_open_wait"] = None
    if entry >= c[i]:
        return None
    tags = dict(unicorn=False, fvg_bottom=ob.bottom, fvg_ce=ob.mid, entry_kind="cisd_ob", mitigation=False,
                propulsion=False, cancel_low=ob.bottom, no_leg_wait=True)
    if open_mode:                                   # a buy limit at open_ref (a 1-tick print through fills, E3); valid while no BODY closes under the run low
        tags.pop("cancel_low")
        tags.update(cancel_close=float(ob.bottom), through=float(p.tick), lvx={"cisd_run_low": (float(ob.bottom), False)})
        S._ES1.hit("cisd_open")
    if p.cisd_adds:
        tags["es1"] = {"cisd": True}                # each later CISD run's open is an add (strategy run_day -> es1.cisd_add)
    return S._finish_order(ctx, sd, i, p, session, sw, entry, ob.bottom - p.pad, risk_mult, rng_hi,
                           tags, skip_leg_pd=True)


# --- non-sweep setups (called from strategy._scan) ------------------------------------------------

def extra_setups(ctx, sd, i, p, session, risk_mult):
    if p.pm_ep01:
        o_ = pm_ep01(ctx, sd, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    if p.moc_run:
        o_ = moc_run(ctx, sd, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    if p.ir_entries:
        o_ = ir_entry(ctx, sd, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    if p.cc_swings in ("failure", "both"):
        o_ = cc_failure_order(ctx, sd, i, p, session, risk_mult)
        if o_ is not None:
            return o_
    return None


def ir_entry(ctx, sd, i, p, session, risk_mult):
    """M11a (099 ~3:46; 100 ~44:54, ~1:37:18): with a bias this way (the locked draw, else
    htf_bias), an immediate rebalance (A7 detector) completed at bar i -> enter at once (market),
    stop below the rebalancing candle [our interpretation of "very tight"]; out on a close below
    the EQ of the displacement candle (the range)."""
    info = sd.ir_info(0.25 * p.es_pt).get(i)
    if info is None or (getattr(ctx, "cur_bias", 0) != sd.sign and p.ir_need_draw):       # (caption-gap A7-immediate-rebalance-gates: ir_need_draw False = no bias needed)
        return None
    if not S._SM2.ir_gates_ok(ctx, sd, i, p, session):      # caption-gap A7-immediate-rebalance-gates: the draw was known beforehand and it prints in a volatility window
        return None
    bound, d = info                       # review fix #85: the rebalanced level and the displacement candle of THIS definition (open_space: older / d+2)
    eq = (sd.l[d] + sd.h[d]) / 2
    if not sd.c[i] > eq:
        return None
    sw = dict(session=session, name="ir", level=float(bound), key="ir", ext=float(sd.l[i]), ext_i=i,
              broke=i, sweep_i=i, smt=None, smt2=None, **{SYNTH: True})
    tags = dict(unicorn=False, fvg_bottom=float(sd.l[i]), fvg_ce=eq, entry_kind="ir", mitigation=False,
                propulsion=False, market=True, no_leg_wait=True, imm_rebal=True, lvx={"ir_eq": (eq, False)},
                skip_po3=not p.synth_po3)
    if p.ir_def != "a7":                  # caption-gap A7: "fast delivery expected" (the level is a PD array on its timeframe)
        tags["lv_tags"] = ["ir_fast_" + p.ir_def]
    return S._finish_order(ctx, sd, i, p, session, sw, float(sd.c[i]), float(sd.l[i]) - p.pad,
                           risk_mult, float(sd.h[i]), tags, skip_leg_pd=True)


def htf_done(ctx, sd, i) -> bool:
    """M5 / Ep01.13 / T10 "HTF objective done" [our interpretation]: a session lock on this side
    delivered by bar i, or the htf table's draw this way (draw_up / draw_dn) traded today."""
    return htf_done_sign(ctx, sd.sign, i)


def htf_done_sign(ctx, sign: int, i: int) -> bool:
    """htf_done for a direction (+1 up / -1 down) in real prices (M6 needs the OTHER side's)."""
    for lk in getattr(ctx, "lock", {}).values():
        if lk.get("side") == sign and lk.get("delivered_i") is not None and lk["delivered_i"] <= i:
            return True
    row = getattr(ctx, "bias_row", None) or {}
    v = row.get("draw_up" if sign > 0 else "draw_dn")
    if v is not None and v == v:
        v = float(v)
        return bool(ctx.h[ctx.start:i + 1].max() >= v if sign > 0 else ctx.l[ctx.start:i + 1].min() <= v)
    return False


def lh_window(p) -> tuple:
    """Owner #1: last-hour entries 15:00-15:50 (p.last_hour); 15:15-15:45 (last_hour_sweet) only
    under the last_hour_strict switch (review fix: M5 / M5.1 no longer re-introduce the sweet spot
    as the window, owner_directive_specs #1: 'M5 and proposed change 23: drop no entries after
    15:45')."""
    return tuple(p.last_hour_sweet) if p.last_hour_strict else tuple(p.last_hour)


def _htf_fvgs(ctx, sd, i, k_known, tf_):
    """Same-side FVGs on timeframe tf_ (confluence rows, source FVG), known by bar k_known's
    start, alive at bar i's close: [(top, bottom)] in side space."""
    conf = getattr(ctx, "conf", None)
    if conf is None or k_known >= len(ctx.t):
        return []
    now = ctx.idx[i] + _tf(ctx)
    out = []
    for top, bot, _, _, _ in conf.valid(now, sd.sign, (tf_,), (0,), ctx.idx[k_known]):
        a, b = sd.x(top), sd.x(bot)
        out.append((max(a, b), min(a, b)))
    return out


def _h4_ce(ctx, sd, i, k900):
    """Ep01.16: (ce, top, bottom) of the nearest same-side 4h FVG below the close, known by 15:00."""
    arr = [a for a in _htf_fvgs(ctx, sd, i, k900, "4h") if a[1] <= sd.c[i]]
    if not arr:
        return None
    t_, b_ = max(arr)
    return (t_ + b_) / 2, t_, b_


def pm_ep01(ctx, sd, i, p, session, risk_mult):
    """M5.1 Ep 01 last hour (001 ~39:03-45:20): a 1h FVG nested in a 4h FVG (same side, both known
    by 15:00, the 4h one below price); from the window start price trades into the 1h FVG and
    bodies refuse to close below its low; then a fast candle leaves a breakaway FVG -> buy its top
    (limit), stop below the FVG candle's open; one exit at the draw. Review fixes: the window is
    owner #1's 15:00-15:50 (lh_window; the sweet spot only with last_hour_strict), every nested
    1h/4h pair is tried (nearest 1h first) instead of only the nearest 4h FVG, and the 4h CE hold
    (Ep01.16, 001 ~30:48) is the separate pm_4h_ce switch on THAT pair's 4h FVG [our
    interpretation: "the four hour range ... that middle point, we're above it"]."""
    t = ctx.t[i]
    wa, wb = lh_window(p)
    if session != "PM" or not (wa <= t < wb):
        return None
    k900, ka = S._idx_at(ctx, p.last_hour[0]), S._idx_at(ctx, wa)
    if ka > i or k900 > i:
        return None
    h4s = [z for z in _htf_fvgs(ctx, sd, i, k900, "4h") if z[1] <= sd.c[i]]
    h1s = _htf_fvgs(ctx, sd, i, k900, "1h")
    pairs = sorted(((z1, z4) for z1 in h1s for z4 in h4s if z1[1] < z4[0] and z1[0] > z4[1]),
                   key=lambda zz: (-zz[0][0], -zz[1][0]))
    used = sd.__dict__.setdefault("_ep01", set())
    for (top1, bot1), (top4, bot4) in pairs:
        if p.pm_4h_ce and (sd.c[k900:i + 1] <= (top4 + bot4) / 2).any():
            continue                                   # Ep01.16: bodies hold above the 4h CE
        touch = np.flatnonzero(sd.l[ka:i + 1] <= top1)
        if not len(touch) or (sd.c[ka:i + 1] < bot1).any():
            continue                                   # into the 1h FVG, bodies refuse its low
        kt = ka + int(touch[0])
        gs = [g for g in sd.gaps if g.i - 2 >= kt and g.i <= i and g.i not in used
              and sd.l[g.i + 1:i + 1].min(initial=np.inf) > g.top]
        if not gs:
            continue
        g = gs[-1]
        used.add(g.i)
        e = kt + int(np.argmin(sd.l[kt:g.i + 1]))
        sw = dict(session=session, name="pm_ep01", level=bot1, key="pm_ep01", ext=float(sd.l[e]), ext_i=e,
                  broke=g.i, sweep_i=kt, smt=None, smt2=None, **{SYNTH: True})
        tags = dict(unicorn=False, fvg_bottom=g.bottom, fvg_ce=g.mid, entry_kind="pm_ep01", mitigation=False,
                    propulsion=False, single_exit=True, cut=wb, skip_po3=not p.synth_po3, no_leg_wait=True)
        return S._finish_order(ctx, sd, i, p, session, sw, g.top, float(sd.o[g.src]) - p.pad, risk_mult,
                               sd.h[e:i + 1].max(), tags, skip_leg_pd=True)
    return None


def ep01_manage(ctx, sd, pos, tr, i, p, can_add: bool) -> None:
    """M5.1 pm_ep01_adds (001 ~37:45-45:02) [our interpretation of the order]: the Ep 01 sequence
    instead of the generic adds / trail, one pending add at a time (p.adds fractions, #12 cap):
    (1) add in the entry FVG (a limit at its CE, armed on the first close after the fill above
    it); (2) add in the breakaway gap (the first new FVG after the fill, a limit at its top) -
    once it fills the stop goes just below that gap's candle bodies ("stop just below the candle
    bodies", ~42:19); (3) add on a breaker (the first bullish breaker formed after the fill, a
    limit at its top). Trail ("then trailed up", ~37:45): every new FVG after the fill lifts the
    stop to just below its candle bodies (kept below the close)."""
    st = pos.setdefault("ep01_stage", 0)
    new = [g for g in sd.gaps if g.i == i and g.i - 2 > pos["fill_i"]]
    for g in new:                                      # the trail under each new gap's bodies
        b = min(min(sd.o[k], sd.c[k]) for k in range(g.i - 2, g.i + 1)) - p.trail_pad
        if b < sd.c[i] and pos.get("ep01_trail_ok"):
            S._MG.raise_stop(pos, b)                       # X5c: never on a day trade
    if not (can_add and pos["add"] is None and S._nadds(pos, tr) < len(p.adds)):
        return
    if st == 0 and i > pos["fill_i"] and sd.c[i] > pos["fvg_ce"] > pos["stop"]:
        pos["ep01_stage"] = 1
        S._arm_add(pos, tr, pos["fvg_ce"], i, p, ctx.equity)
        return
    if st <= 1 and new:
        g = new[-1]
        pos["ep01_stage"] = 2
        pos["ep01_trail_ok"] = True                    # trailing starts with the breakaway gap
        if g.top > pos["stop"] and add_ok(sd, pos, g.top, i, p):
            S._arm_add(pos, tr, g.top, i, p, ctx.equity)
            if pos["add"] is not None:
                pos["add"]["stop_to"] = min(min(sd.o[k], sd.c[k]) for k in range(g.i - 2, g.i + 1)) - p.trail_pad
        return
    if st == 2:
        zs = [z for z in _breakers(sd, p) if z.i == i and z.i > pos["fill_i"] and z.top > pos["stop"]
              and z.top < sd.c[i]]
        if zs:
            pos["ep01_stage"] = 3
            S._arm_add(pos, tr, zs[-1].top, i, p, ctx.equity)


def moc_run(ctx, sd, i, p, session, risk_mult):
    """T10 (032 ~1:01:00) [our interpretation of the bar mechanics]: no PM / last-hour trade by
    15:40, the HTF objective not done, a bias this way (lock side / htf_bias) -> at the 15:40 bar's
    close enter at market toward the nearest liquidity untouched today, target capped at
    moc_cap_pts and at least min_draw_pts away; stop below the low since 15:10."""
    t = ctx.t[i]
    d = getattr(ctx, "done_ref", {})
    if session != "PM" or not (940 <= t < 945) or d.get("PM") or d.get("LH") or d.get("MOC"):
        return None
    if getattr(ctx, "cur_bias", 0) != sd.sign or htf_done(ctx, sd, i):
        return None
    entry = float(sd.c[i])
    stop = float(sd.l[S._idx_at(ctx, 910):i + 1].min()) - p.pad
    tol = p.eq_tol_pts * p.es_pt
    eq_hi = S._eq_levels(sd, i, tol, lows=False, p=p)
    today = float(sd.h[ctx.start:i + 1].max())
    lv = [v for v, k in S._targets(ctx, sd, i, entry, eq_hi, p, None, i) if k in S.POOL_KINDS and v > today]
    if not lv:
        return None
    x = min(S._exit_px(lv[0], "pool", p), entry + p.moc_cap_pts * p.es_pt)
    sw = dict(session=session, name="moc", level=entry, key="moc", ext=stop + p.pad, ext_i=i, broke=i,
              sweep_i=i, smt=None, smt2=None, **{SYNTH: True})
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=entry, entry_kind="moc_run", mitigation=False,
                propulsion=False, market=True, no_leg_wait=True, done_key="MOC", skip_po3=not p.synth_po3)
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, entry, tags, skip_leg_pd=True,
                           fixed=[(x, "pool")])


def pm_reversal(ctx, sd, i, p, risk_mult):
    """M6 PM reversal (015 ~31:57-36:20): the day's objective done the OTHER way (a lock on the
    opposite side delivered by bar i), the AM extreme on that side taken in the PM, then price
    trades back through the 1m FVG left at the extreme (an IFVG, side space: support); the first
    return into it is the entry (limit at its near edge / CE), stop beyond it; targets: the old
    daily level that was run and the lunch extreme on this side. In side space throughout."""
    t = ctx.t[i]
    if not (p.pm[0] <= t < p.pm[1]) or not ctx.am_hl:
        return None
    b = -sd.sign
    locks = [lk for lk in getattr(ctx, "lock", {}).values() if lk.get("side")]
    armed_ = bool(getattr(ctx, "done_ref", {}).get("PM_REV_ARMED"))      # caption-gap M6-pm-continuation-long-at-old-high: the continuation long's target fill arms the reversal
    if armed_:
        pass
    elif locks:
        if not any(lk.get("side") == b and lk.get("delivered_i") is not None and lk["delivered_i"] <= i
                   for lk in locks):
            return None
    elif not htf_done_sign(ctx, b, i):
        return None                  # review fix: no lock (draw_lock off / neutral) -> the htf table's
                                     # draw the other way traded today is the "objective met"
    k_pm = S._idx_at(ctx, 810)
    if p.pm_rev_nested and not S._SM2.nested_at_am(ctx, sd, i, p):
        S._f("x_pm_reversal_not_nested")     # caption-gap A22-htf-definition-nested-arrays (cc10_013): the AM move stopped at an un-nested 15 / 60m array - continuation, not a fade
        return None
    am_x = sd.x(ctx.am_hl[1] if sd.sign > 0 else ctx.am_hl[0])
    if p.pm_reversal_pool == "lunch_or_am" and "lunch" in ctx.sess:
        # caption-gap DS2-am-move-pm-reversal-templates (cc10_013 ~6:36): a sweep of the LUNCH extreme (a failure swing vs the AM extreme) also counts
        lx = sd.x(ctx.sess["lunch"][1] if sd.sign > 0 else ctx.sess["lunch"][0])
        am_x = max(am_x, lx)
        S._SM2.hit("pm_reversal_lunch")
    if p.pm_reversal_ltf_only:
        # ... the reversal carries through only when the AM move started off a 60m / 15m array: a 4h+ origin (the AM extreme's array) blocks it
        cf = getattr(ctx, "conf", None)
        if cf is not None:
            S._SM2.hit("pm_reversal_ltf")
            org = float(ctx.am_hl[1] if sd.sign < 0 else ctx.am_hl[0])       # real price of the AM move's origin (its low for an AM rally = b > 0)
            if any(t_ in ("4h", "D", "W", "M") for t_ in cf.at(ctx.idx[k_pm], org, b)):
                S._f("x_pm_reversal_htf_origin")
                return None
    seg = sd.l[k_pm:i + 1]
    if not len(seg) or seg.min() >= am_x:
        return None
    e = k_pm + int(np.argmin(seg))
    used = sd.__dict__.setdefault("_pmr", set())
    # the IFVG is the 1m FVG left AT the extreme: formed within 10 bars before it [our interpretation]
    zs = [z for z in sd.ifvgs() if e < z.i <= i and z.src + 1 >= max(k_pm, e - 10) and z.i not in used
          and sd.l[z.i + 1:i + 1].min(initial=np.inf) > z.top]
    if not zs:
        return None
    z = zs[-1]
    used.add(z.i)
    entry = z.mid if p.ifvg_entry == "ce" else z.top
    if entry >= sd.c[i]:
        return None
    pk = ("pdl1", "pdl2", "pdl3") if sd.sign > 0 else ("pdh1", "pdh2", "pdh3")
    lv = [sd.x(ctx.pd[k]) for k in pk if k in ctx.pd]
    if "lunch" in ctx.sess:
        lv.append(sd.x(ctx.sess["lunch"][0] if sd.sign > 0 else ctx.sess["lunch"][1]))
    fixed = sorted({(S._exit_px(v, "pool", p), "pool") for v in lv if v > entry})
    if p.pm_rev_partial:                                  # caption-gap M6-ifvg-must-stay-partly-open (015 ~00:33:56): the lunch relative equal lows join the ladder after the old daily level
        fixed = sorted(set(fixed) | {(S._exit_px(v, k, p), k) for v, k in S._SM4.pm_rev_extra_targets(ctx, sd, i, p, entry)})
    if not fixed:
        return None
    sw = dict(session="PM", name="pm_reversal", level=am_x, key="pm_reversal", ext=float(sd.l[e]), ext_i=e,
              broke=z.i, sweep_i=e, smt=None, smt2=None, **{SYNTH: True})
    tags = dict(unicorn=False, fvg_bottom=z.bottom, fvg_ce=z.mid, entry_kind="pm_reversal", mitigation=False,
                propulsion=False, done_key="PMR", no_leg_wait=True)
    stop = z.bottom - p.pad
    if p.pm_rev_partial:                                  # the gap must stay partly open: a body close past its far edge before the fill cancels the order, a trade through it afterwards exits
        S._SM2.hit("pm_rev_partial")
        stop = z.bottom - p.tick
        tags["cancel_close"] = float(z.bottom)
        tags["sm4"] = dict(kind="pm_rev_partial", far=float(z.bottom))
    return S._finish_order(ctx, sd, i, p, "PM", sw, entry, stop, risk_mult,
                           sd.h[e:i + 1].max(), tags, skip_leg_pd=True, fixed=fixed)


# --- _finish_order gates, targets and draws -----------------------------------------------------

def _news_first_leg(ctx, i) -> int:
    """N6: real direction of the first leg after the release driving this window (or the latest
    complete range today): -1 when its low formed before its high."""
    drv = getattr(ctx, "cur_news", None)
    if drv is None or drv.get("made") is None:
        ds = [d for d in getattr(ctx, "news_dr", {}).values() if d["made"] is not None and d["made"] <= i]
        drv = max(ds, key=lambda d: d["R"]) if ds else None
    if drv is None:
        return 0
    kR = S._idx_at(ctx, drv["R"])
    m = drv["made"]
    if m < kR:
        return 0
    ih = kR + int(np.argmax(ctx.h[kR:m + 1]))
    il = kR + int(np.argmin(ctx.l[kR:m + 1]))
    return -1 if il < ih else (1 if ih < il else 0)


def _candle_side(ctx, i, p) -> int:
    """M0 candle_draw_bias [our interpretation]: the daily (weekly) candle reaches for the nearer
    untaken prior extreme from the midnight open; once one is taken today the other is the draw."""
    if p.candle_draw_bias == "daily":
        hs = getattr(ctx, "hist", None)
        if not hs:
            return 0
        hi, lo = float(hs[-1].high.max()), float(hs[-1].low.min())
    else:
        if ctx.pw is None:
            return 0
        hi, lo = ctx.pw
    ref = S._open_known(ctx, "midnight", i)
    if ref is None or i <= ctx.start:
        return 0
    hh, ll = ctx.h[ctx.start:i].max(), ctx.l[ctx.start:i].min()
    up, dn = hh > hi, ll < lo
    if up and not dn:
        return -1
    if dn and not up:
        return 1
    if up and dn:
        return 0
    return 1 if hi - ref < ref - lo else (-1 if ref - lo < hi - ref else 0)


def _discount_array(ctx, sd, sw, tol, p=None) -> bool:
    """M1: the sweep extreme sits in a same-side 1m BISI (open by closes until the extreme) or a
    5m OB known by the extreme's bar."""
    e, x = sw["ext_i"], sw["ext"]
    types = p.mm_turn_types if p is not None else ("ob", "fvg")       # caption-gap M1-turning-level-types (cc04_007 ~1:04)
    if "fvg" in types:
        for g in sd.gaps:
            if g.i > e:
                break
            if g.bottom - tol <= x <= g.top + tol and sd.c[g.i + 1:e].min(initial=np.inf) >= g.bottom:
                return True
    if "ob" in types:
        for z in sd.zones_tf(ctx.idx, ctx.tf, max(5, ctx.tf)):
            if z.mt == z.mt and z.i <= e and z.bottom - tol <= x <= z.top + tol:
                return True
    if types and set(types) & {"old_high", "old_low", "void"}:
        if S._SM3.turn_level_ok(ctx, sd, sw, tol, p):
            S._SM2.hit("mm_turn_type")
            return True
    return False


def _htf_draw(ctx, sd, entry) -> bool:
    row = getattr(ctx, "bias_row", None) or {}
    v = row.get("draw_up" if sd.sign > 0 else "draw_dn")
    return v is not None and v == v and sd.x(float(v)) > entry


def _nested(ctx, sd, sw, i, p, tol) -> bool:
    conf = getattr(ctx, "conf", None)
    if conf is None:
        return False
    now = ctx.idx[i] + _tf(ctx)
    kb = ctx.idx[sw["ext_i"]] + _tf(ctx)
    xr = sd.x(sw["ext"])
    for tf_ in p.nest_tfs:
        ok = any(min(t_, b_) - tol <= xr <= max(t_, b_) + tol
                 for t_, b_, *_ in conf.valid(now, sd.sign, (tf_,), (0,), kb))
        if not ok:
            return False
    return True


CC_PROFILES = {1: ("two_session_up", "am_rally_pm_reversal", "cons_am_rally_pm_decline"),
               -1: ("two_session_down", "am_decline_pm_reversal", "cons_am_decline_pm_rally")}


def cc_profile(ctx, i, p):
    """T13 [CC] six index day profiles (cc10_013 ~1:21-15:43; cc10_014) classified at 13:30 from
    bars closed by then [our interpretation of the classification - the source reads them off an
    HTF array map]: the AM leg (09:30-12:00) = +1 when its low came before its high and it closed
    above its open (AM rally), -1 the mirror, else unclear; then
      - consolidation (5 / 6): no release after 10:00 and the AM range < 0.5 x ADR5;
      - AM rally (decline) into a 4h / daily premium (discount) array = an opposing 4h / D FVG at
        the AM extreme, known by 13:30 -> PM reversal (3 / 4);
      - else the two-session trend profile (1 / 2);
      - NFP days: "seek_destroy" (the exception).
    Returns (name, PM direction: +1 / -1 / 0) or None before 13:30; cached on ctx."""
    k810 = S._idx_at(ctx, 810)
    if i < k810 or k810 >= len(ctx.t):
        return None
    if getattr(ctx, "_cc_prof", None) is not None:
        return ctx._cc_prof
    if "jobs" in events(ctx.day):
        ctx._cc_prof = ("seek_destroy", 0)
        return ctx._cc_prof
    a, b = S._idx_at(ctx, 570), S._idx_at(ctx, 720)
    b = min(b, k810)
    if b - a < 2:
        ctx._cc_prof = ("unclear", 0)
        return ctx._cc_prof
    h, l, o, c = ctx.h[a:b], ctx.l[a:b], ctx.o[a:b], ctx.c[a:b]
    ih, il = int(np.argmax(h)), int(np.argmin(l))
    d = 1 if (il < ih and c[-1] > o[0]) else -1 if (ih < il and c[-1] < o[0]) else 0
    if d == 0:
        ctx._cc_prof = ("unclear", 0)
        return ctx._cc_prof
    from .calendar import release_times
    adr = S.adr5(getattr(ctx, "hist", [])[-5:])
    cons = (not any(R >= 600 for R in release_times(ctx.day)) and adr is not None
            and float(h.max() - l.min()) < 0.5 * adr)
    at_arr = False
    conf = getattr(ctx, "conf", None)
    if conf is not None:
        now = ctx.idx[k810 - 1] + _tf(ctx)
        x = float(h.max()) if d > 0 else float(l.min())
        at_arr = any(tf_ in ("4h", "D") for tf_ in conf.at(now, x, -d))   # the opposing array (real price)
    name = CC_PROFILES[d][2 if cons else 1 if at_arr else 0]
    ctx._cc_prof = (name, d if name.startswith("two_session") else -d)
    return ctx._cc_prof


def finish_gates(ctx, sd, sw, i, p, session, entry, tags: dict, lvt: list, lvx: dict) -> bool:
    """setups_models filters on every entry path (False = reject) and their tags."""
    tol = p.eq_tol_pts * p.es_pt
    synth = bool(sw.get(SYNTH))
    t = ctx.t[i]
    if p.require_judas and not S._judas(ctx, sd, sw, session, p.judas_window):
        S._f("x_require_judas")
        return False
    if p.require_judas_news or p.judas_news_tag:      # caption-gap T13-judas-news-driver (cc01_002 ~15:16): the Judas is triggered by a news driver
        jn = S._SM2.judas_news(ctx, sw, p)
        if jn:
            lvt.append("judas_news")
        elif p.require_judas_news and p.require_judas:
            S._f("x_require_judas_news")
            return False
    if p.po3_require_bias and getattr(ctx, "cur_bias", 0) != sd.sign:
        S._f("x_po3_bias")
        return False
    if p.nfp_sd != "off" and "jobs" in events(ctx.day):
        if p.nfp_sd == "skip":
            S._f("x_nfp_sd")
            return False
        lvt.append("nfp_sd")
    if p.news_profile == "pool_test":                 # caption-gap N6-nfp-first-move-fake-if-liquidity (105 ~7:58): the first move is the fake only if it ran a pool
        why = S._SM2.news_pool_gate(ctx, sd, sw, i, p, session, lvt)
        if why:
            S._f(why)
            return False
    elif p.news_profile != "off":
        fl = _news_first_leg(ctx, i)
        if fl == -sd.sign:
            lvt.append("news_profile")
        elif fl and p.news_profile == "require":
            S._f("x_news_profile")
            return False
    if p.candle_draw_bias != "off":
        cs = _candle_side(ctx, i, p)
        if cs and cs != sd.sign:
            S._f("x_candle_draw")
            return False
    if session == "AM" and (p.am_htf_draw or p.am_discount_array or p.mm_context != "off"):
        hd = _htf_draw(ctx, sd, entry)
        da = _discount_array(ctx, sd, sw, tol, p)
        if (p.am_htf_draw and not hd) or (p.am_discount_array and not da) or \
                (p.mm_context == "require" and not (hd and da)):
            S._f("x_mm_context")
            return False
        if hd and da:
            lvt.append("mm_ctx")
    if p.nest_tfs and not _nested(ctx, sd, sw, i, p, tol):
        S._f("x_nest_tfs")
        return False
    if p.three_drives != "off":
        td = L.three_drives(sd.pl, sw["ext"], sw["ext_i"], i, max(0, ctx.start - 1), sw["level"] if p.td_same_level else None, p.td_level_pts * p.es_pt)     # (caption-gap M2-three-drives-breaker-fallback: td_same_level)
        if td:
            lvt.append("three_drives")
        elif p.three_drives == "require":
            S._f("x_three_drives")
            return False
    lh = session == "PM" and p.last_hour[0] <= t < p.last_hour[1]
    ep01 = sw.get("key") == "pm_ep01"
    if lh and not synth:
        # M5 (review fix, owner #1): the last-hour sweep and the entry inside the owner's window
        # (15:00-15:50; the 15:15-15:45 sweet spot only with last_hour_strict)
        wa, wb = lh_window(p)
        if p.pm_last_hour_model and not (wa <= ctx.t[sw["sweep_i"]] < wb and t < wb):
            S._f("x_lh_window")
            return False
    if lh and p.lh_start_by and (not synth or ep01) and ctx.t[sw["ext_i"]] > p.lh_start_by:
        S._f("x_lh_start_by")                 # Ep01.17: the move started by 15:25 (also pm_ep01)
        return False
    if lh and (p.pm_last_hour_model or lh_on(p, "lh_htf_done_skip")) and htf_done(ctx, sd, i) and not S._SM7.lh_after_pass(ctx, sd, i, p):
        S._f("x_lh_htf_done")
        return False
    if lh and p.pm_4h_ce and not ep01:        # pm_ep01 tests its own nested pair's 4h CE
        k900 = S._idx_at(ctx, p.last_hour[0])
        h4 = _h4_ce(ctx, sd, i, k900)
        if h4 is None or (sd.c[k900:i + 1] <= h4[0]).any():
            S._f("x_pm_4h_ce")                # review fix: no 4h FVG below price = no hold either
            return False
    if session == "PM" and not synth and (p.pm_lunch_target or p.pm_lunch_org):
        if sw.get("key") != "lunch":
            S._f("x_pm_lunch")
            return False
        if p.pm_lunch_org:
            if not (getattr(ctx, "org_today", False) and ctx.org):
                return False
            a, b = sd.x(ctx.org[-1][0]), sd.x(ctx.org[-1][1])
            if not (min(a, b) - tol <= sw["ext"] <= max(a, b) + tol):
                S._f("x_pm_lunch_org")
                return False
    if p.profile_tags and getattr(ctx, "conf", None) is not None:
        now = ctx.idx[i] + _tf(ctx)
        d_, h4_ = ctx.conf.trend(now, "D"), ctx.conf.trend(now, "4h")
        prof = ("up_close" if d_ == 1 and h4_ == 1 else "down_close" if d_ == -1 and h4_ == -1
                else "consolidation" if d_ == 0 and h4_ == 0 else "reversal")
        lvt.append("profile_" + prof)
    if p.cc_profile != "off" and session == "PM":     # T13 CC day profiles
        pr = cc_profile(ctx, i, p)
        if pr is not None:
            lvt.append("cc_" + pr[0])
            if p.cc_profile == "gate":
                if pr[1] != sd.sign:
                    S._f("x_cc_profile")
                    return False
                if pr[0].startswith("cons"):           # cc10_014 ~13:17: out by ~14:00
                    tags["exit_at"] = 840
    if p.po3_hold:
        ref = S._open_known(ctx, "1330" if session == "PM" else "midnight", i)
        if ref is not None:
            tags["po3_open"] = sd.x(ref)
    return True


def sick_sister(ctx, sd, i, p, session, entry):
    """M16.2 sick sister (053 ~1:56-7:57) [our interpretation of the count]: at the session start
    (09:30 AM / 13:30 PM) count the reference highs (side space: PDH 1-3, the overnight high =
    ctx.pd "pmh" (midnight -> 09:30, from the 18:00 reopen with globex_pool), London and prior-PM
    highs) each index has traded through since midnight; the index with strictly fewer than every
    sister is the sick one - trade it only, only in the day's DEEP discount (review fix: below
    sick_depth of the range midnight -> bar i, 0.25 by default [our interpretation of "deep"];
    0.5 = the EQ, the first build), targets = its untaken references. None = reject."""
    sisters = []
    ps = getattr(ctx, "pside", None)
    if ps is not None and ps[0] is not None:
        sisters.append((ps[0], ps[1][sd.sign]))
    if getattr(ctx, "partner2", None):
        sisters.append((ctx.partner2[0], ctx.partner2[1][sd.sign]))
    if not sisters:
        return None
    m0 = 810 if session == "PM" else 570

    def refs(c_, s_):
        k = S._idx_at(c_, m0)
        if k <= c_.start or k > len(c_.t):
            return None
        tk = S._tick(p)
        hk = "pdh" if s_.sign > 0 else "pdl"
        lv = [s_.x(v) for kk, v in c_.pd.items() if kk.startswith(hk)]
        ok = "pmh" if s_.sign > 0 else "pml"
        if ok in c_.pd:
            lv.append(s_.x(c_.pd[ok]))
        for nm in ("london", "prev_pm"):
            if nm in c_.sess:
                hi, lo, _ = c_.sess[nm]
                lv.append(s_.x(hi if s_.sign > 0 else lo))
        top = s_.h[c_.start:k].max()
        taken = [v for v in lv if S._spent_up(top, v, tk)]
        return len(taken), sorted(v for v in lv if v not in taken)

    me = refs(ctx, sd)
    if me is None or S._idx_at(ctx, m0) > i:
        return None
    others = [refs(c_, s_) for c_, s_ in sisters]
    others = [x[0] for x in others if x is not None]
    if not others or not me[0] < min(others):
        S._f("x_not_sick_sister")
        return None
    lo_, hi_ = sd.l[ctx.start:i + 1].min(), sd.h[ctx.start:i + 1].max()
    if not entry < lo_ + p.sick_depth * (hi_ - lo_) and not (p.smt_trend_ignore and S._SM4.trend_day(ctx, sd, i, p)):    # (caption-gap M16-trending-divergence-continuation: a trending day needs no deep discount)
        S._f("x_sick_not_discount")
        return None
    tg = [v for v in me[1] if v > entry]
    if not tg:
        return None
    if p.ss_ladder:                          # caption-gap M16-sick-sister-exit-ladder (053 ~6:21): T1 just above the nearer high, T2 the midpoint, the farther high no rung
        S._SM2.hit("ss_ladder")
        return S._SM3.ss_ladder(tg, p)
    return [(S._exit_px(v, "array", p), "array") for v in tg]


def more_targets(ctx, sd, i, above, p) -> list:
    """M1.1 daily_vi_targets (opposing daily VIs: near edge, CE); N6 news_ce_target (the news
    range CE once both of its sides were taken after it formed)."""
    out = []
    conf = getattr(ctx, "conf", None)
    if p.daily_vi_targets and conf is not None:
        now = ctx.idx[i] + _tf(ctx)
        for near, ce, far, tf_, _ in conf.opposing(now, sd.x(above), sd.sign, ("D",), (3,)):
            kd = "vi" if p.target_order else "array"             # Ep04.12: only the daily VI rungs are told apart
            out += [(sd.x(near), kd), (sd.x(ce), kd)]
    if p.news_ce_target:
        for d in getattr(ctx, "news_dr", {}).values():
            m = d["made"]
            if m is None or m >= i:
                continue
            if ctx.h[m + 1:i + 1].max() > d["hi"] and ctx.l[m + 1:i + 1].min() < d["lo"]:
                out.append((sd.x(d["eq"]), "array"))
    return [(float(v), k) for v, k in out if v > above]


def draw_prefs(ctx, sd, sw, i, p, session, entry, risk, keep) -> list:
    """Draw overrides on the no-lock path: [(exit price, kind, name)]. M2 m2_target, Ep05.8
    mmxm_ctx, M7 pm_lunch_target."""
    out = []
    if p.m2_target:
        eqd = (sd.l[ctx.start:i + 1].min() + sd.h[ctx.start:i + 1].max()) / 2
        pools = [(v, k) for v, k in keep if k in S.POOL_KINDS and v > eqd]
        eqp = [x for x in pools if x[1] == "pool_eq"]
        if eqp or pools:
            v, k = (eqp or pools)[0]
            out.append((v, k, "m2"))
    if p.mmxm_ctx:
        q = leg_origin(sd, sw["ext_i"], i) if p.mm_ssl_target else None
        if q is not None:
            S._SM2.hit("mm_ssl")      # caption-gap A2-delivery-vs-liquidity (104 ~11:24): the far end of the delivery leg that engineered the pool (the origin of the decline into a long's sweep)
        if q is None:
            q = parent_high(sd, sw["ext_i"], i)
        else:
            q = type(q)(q.i, float(sd.h[q.i:sw["ext_i"] + 1].max()), q.known)
        if q is not None and q.price > entry:
            px_ = q.price
            if p.orig_consol:             # caption-gap M1-original-consolidation (104 ~27:53): the smooth-edge level of the original consolidation
                u_ = S._LD3.orig_consol_level(sd, q, sw["ext_i"], i, p)
                if u_ is not None and u_ > entry:
                    px_ = u_
            out.append((S._exit_px(px_, "pool", p), "pool", "mmxm"))
    if p.pm_lunch_target and session == "PM" and sw.get("key") == "lunch" and "lunch" in ctx.sess:
        lu = sd.x(ctx.sess["lunch"][0] if sd.sign > 0 else ctx.sess["lunch"][1])
        if lu > entry:
            out.append((S._exit_px(lu, "pool", p), "pool", "lunch"))
    return out


def unengaged_ok(ctx, sd, i, p, session, draw) -> bool:
    """Ep01.13 lh_unengaged: a last-hour draw must lie beyond today's high so far (untouched)."""
    if not (lh_on(p, "lh_unengaged") and session == "PM" and p.last_hour[0] <= ctx.t[i] < p.last_hour[1]):
        return True
    return bool(draw > sd.h[ctx.start:i + 1].max() + S._tick(p))


# --- adds (M2 add_leg_cut, Ep05.4, M4, M12.2, M4.4) ------------------------------------------------

def add_leg(pos):
    """The leg the add rules measure (M2.6): fixed at the fill (`leg_fill`), else the position's leg."""
    return pos.get("leg_fill") or pos.get("leg")


def add_pd_ok(pos, px, p) -> bool:
    """M2.6 add_in_pd (022 ~49:26; 058 ~43:12): pyramid only on the entry side of the leg's EQ (add_pd_level). Checked in
    `add_ok` AND in `strategy._arm_add`, so every add path (FVG, Ep04.10 low end, retest, Ep01 CE add, down-close) honours it."""
    ie = (pos.get("sm4") or {}).get("implied_eq")
    if ie is not None and px > ie + 1e-9:
        return False                              # caption-gap M2-implied-range-eq-gate (025 ~00:46:41): entries and adds only on the entry side of the implied range's EQ
    leg = add_leg(pos)
    if not (p.add_in_pd and leg):
        return True
    ext, hi = leg
    return px <= ext + p.add_pd_level * (hi - ext) + 1e-9


def add_ok(sd, pos, px, i, p, form=None) -> bool:
    if pos.get("td_block"):
        return False                              # caption-gap E12-trend-day-adds: price is at the far daily extreme
    if not S._ES2.form_eq_ok(sd, pos, px, form, p):
        return False                              # caption-gap E12-add-cutoff-definition (092 ~01:16:43): the add array formed on the draw side of the implied range EQ
    leg = add_leg(pos)
    if p.add_leg_cut and leg and not pos.get("td_ok"):
        ext, hi = leg
        lg = hi - ext
        if px > ext + 0.5 * lg or sd.h[pos["fill_i"]:i + 1].max() > ext + 0.75 * lg:
            return False
    if leg and (pos.get("sm4") or {}).get("implied_eq") is not None and sd.h[pos["fill_i"] + 1:i + 1].max(initial=-np.inf) > leg[1] + 1e-9:
        S._SM2.hit("implied_add_cut")
        return False                              # review fix, M2-implied-range-eq-gate (025 ~00:46:41): adds only while no new structural extreme beyond the post-MSS leg printed (side space: no swing high over the leg high)
    if not add_pd_ok(pos, px, p):
        return False
    if p.adds_in_breaker and pos.get("bz_side"):
        top, bot = pos["bz_side"]
        if not (bot - 1e-12 <= px <= top + 1e-12):
            return False
    if p.breaker_need_bias_draw and pos.get("bz_side") and not (pos.get("sm3") or {}).get("bd_ok", True):
        return False                              # caption-gap M4-accumulate-in-breaker-needs-bias-draw (007 ~21:34): no add inside the breaker without the bias + a named draw
    return True


def _breakers(sd, p):
    return sd._lazy(("brk", p.breaker_zone), lambda: [z for z in L.breakers(sd.o, sd.h, sd.l, sd.c, sd.n,
                                                                             p.breaker_zone) if z.kind == "bull"])


TS_KINDS = ("turtle_soup", "ts_or60", "ts_cc_1h_ob", "ts_cc_limit", "ts_external", "smt_turtle", "prev_pm_turtle")


def more_adds(ctx, sd, pos, tr, i, p) -> None:
    """Arm at most one add on bar i's close (pos["add"] must be free; the caller checked the
    common add conditions)."""
    arm = lambda px: S._arm_add(pos, tr, px, i, p, ctx.equity) if add_ok(sd, pos, px, i, p) else None
    if p.add_on_vi:
        vs = [z for z in sd.vis("bull") if z.i == i and z.i > pos["fill_i"] + 1]
        if vs:
            arm(vs[-1].top)
            if pos["add"] is not None:
                return
    if (p.breaker_retest_add or p.add_on == "breaker") and pos.get("bz_side") and not pos.get("bz_add"):
        top = pos["bz_side"][0]
        if i > pos["fill_i"] and sd.c[i] > top and top > pos["stop"]:
            pos["bz_add"] = True
            arm(top)
            if pos["add"] is not None:
                return
    if p.two_chance and pos.get("kind") in TS_KINDS and pos["add"] is None:
        S._SM6.two_chance_add(ctx, sd, pos, tr, i, p)              # caption-gap M4-two-chance-aggressive-vs-mss-retest: chance 2 is an add after a filled soup
        if pos["add"] is not None:
            return
    if (p.ts_adds_breakers or p.ts_breaker_pyramid) and pos.get("kind") in TS_KINDS:
        if p.ts_breaker_pyramid and not p.ts_adds_breakers and pos.get("ts_pyr"):
            return
        zs = [z for z in _breakers(sd, p) if z.i == i and z.i > pos["fill_i"] and z.bottom > pos["stop"]
              and z.top < sd.c[i]]
        if zs:
            pos["ts_pyr"] = True
            S._SM7.breaker_add(ctx, sd, pos, tr, i, p, zs[-1])          # caption-gap M4-pattern3-breaker-half-size-add-ltf: half the initial units, refined on the 1m
