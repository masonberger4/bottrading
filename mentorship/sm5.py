"""Caption-gap pass (digests/rulebook_gaps/*.md), package setups_models, chunk 5 of 7: the engine glue of its 36 specs from models_setups_entries.md (items 63, 64, 66, 68-70, 72, 75-81, 83, 84,
86-89, 91, 95, 98, 99, 101-112).

Same conventions as sm2.py / sm3.py / sm4.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an
object only from the bar that completes it, daily / weekly objects only after their session closes (everything reads `ctx.hist`, the COMPLETED prior sessions, plus today's bars through the bar
being judged). Every function sits behind a Params switch of the "caption-gap pass, setups_models #5/7" block; interpretations the sources do not pin down are marked [our interpretation].
`HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2, sm3, sm4

HITS = sm2.HITS
hit = sm2.hit

MIN1 = 1e-9


def _S():
    from . import strategy as S
    return S


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_sm5", {})


def _want(ctx) -> int:
    return sm2.want(ctx)


# the entry kinds that RAID a pool and enter before the MSS / without confirmation (item 69: the experienced-trader "turtle soup" style); every other kind waits for the displacement
RAID_KINDS = frozenset({"ob_pre", "turtle_soup", "ts_or60", "ts_cc_1h_ob", "ts_cc_limit", "ts_external", "htf_stab", "wick_ce", "smt_turtle", "smt_stop", "dagger_entry", "prev_pm_turtle",
                        "lh_old_low", "po3_rest"})            # (false_flag is a tag, not an entry kind: review fix)


def entry_style(entry_kind: str) -> str:
    """M12-new-trader-no-turtle-soup (065 ~03:01:01; 066 ~00:31:09): "raid" = an entry at the run of a pool before / without the MSS (turtle soup, the owner's pre-break OB); "confirmed" =
    the displacement, the swing taken and the FVG first (the 2022 model). A tag only (reports split the results by style); the owner question about the pre_break default is not part of the build."""
    return "raid" if entry_kind in RAID_KINDS else "confirmed"


# --- tiny helpers -----------------------------------------------------------------------------------------------------------------------------------

def _tol(p) -> float:
    return p.eq_tol_pts * p.es_pt


def _min_stop(p, entry: float, stop: float) -> float:
    return stop if entry - stop >= p.min_risk_pts * p.es_pt else entry - p.min_risk_pts * p.es_pt


def _prev_range_real(ctx):
    """(high, low, close) of the previous completed session, real prices, or None."""
    h = getattr(ctx, "hist", None)
    if not h:
        return None
    f = h[-1]
    return float(f.high.max()), float(f.low.min()), float(f.close.iloc[-1])


def _day_bars(hist: list):
    """The completed daily bars of `hist` as real (o, h, l, c) arrays (the prior sessions only)."""
    o = np.array([float(f.open.iloc[0]) for f in hist])
    h = np.array([float(f.high.max()) for f in hist])
    l = np.array([float(f.low.min()) for f in hist])
    c = np.array([float(f.close.iloc[-1]) for f in hist])
    return o, h, l, c


def daily_side(ctx, sd, p):
    """A Side over the COMPLETED daily bars (ctx.hist, newest last) in the trade's own side space - the daily mitigation blocks / IFVGs of items 98 / 105 are read from it. Cached per sign; the
    zones' `i` are indices into the hist list (a block known at the close of day i)."""
    S = _S()
    key = ("dside", sd.sign, len(ctx.hist))
    c = _c(ctx)
    if key not in c:
        o, h, l, cc = _day_bars(ctx.hist)
        c[key] = S.Side(sd.sign, o, h, l, cc, 1, mit_legacy=p.mit_legacy_order, mit_mt=p.mit_mt_invalid, bpr_def=p.bpr_def, pb_def=p.pb_def) if len(o) >= 4 else None
    return c[key]


# --- 63 M10-ifvg-fvg-signature-full -----------------------------------------------------------------------------------------------------------------

def ifvg_061_iofed(ctx, sd, sw, f, i: int, p, session: str, risk_mult: float):
    """M10-ifvg-fvg-signature-full (061 ~02:18:22): `ifvg_061_entry` "iofed" replaces the 061 market entry at the body close by a LIMIT at the lower FVG's top + 1 tick (the IOFED level
    "at it or just inside"; never deeper than the CE - [our interpretation: the cap]); a trade below the CE cancels the order and exits the position (`manage`: reason ifvg_ce); the stop stays under
    the FVG; the ladder's first rung is the nearest relative equal highs (`_targets` already carries them: the rel-eq pools are in its ladder)."""
    S = _S()
    tk = float(p.tick)
    entry = min(float(f.top) + tk, float(sd.c[i]) - tk)
    entry = max(entry, float(f.mid))
    if entry >= sd.c[i] - MIN1:
        return None
    stop = float(f.bottom) - p.pad
    tags = dict(unicorn=False, fvg_bottom=float(f.bottom), fvg_ce=float(f.mid), entry_kind="ifvg_061_iofed", mitigation=False, propulsion=False, no_leg_wait=True,
                cancel_low=float(f.mid), sm5=dict(kind="ifvg061", ce=float(f.mid)), lv_tags=["ifvg_061_iofed"])
    hit("ifvg_061_iofed")
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, sd.h[sw["ext_i"]:i + 1].max(), tags, skip_leg_pd=True)


# --- 64 new-false-bull-flag-short -------------------------------------------------------------------------------------------------------------------

def flag_info(ctx, sd, sw, i: int, p):
    """new-false-bull-flag-short (061 ~01:41:32; cc02_007 ~00:16:23): in side space a BEAR flag over the swept pool - a rapid one-sided drop (the flagpole) followed by a consolidation of at least
    `flag_min_bars` bars whose range is no wider than `flag_max_frac` x the pole (the pole origin high .. the flag's low), ending at the bar before the sweep extreme. The flag is the last
    `flag_min_bars` bars before the sweep (a longer flag qualifies through its last bars; a window that still holds pole bars is too wide and fails the range test). The pole origin is the highest
    high of the `6 x flag_min_bars` bars before the flag (the impulse that made the flag, not an older high - review fix). The flag is anchored on the FIRST sweep bar (`sweep_i`, like
    near_miss_tag): a multi-bar sweep moves `ext_i` to every new lower low, which would pull sweep bars into the flag window. Returns dict(s, low, high, origin_i, origin) or None."""
    e = int(sw.get("sweep_i", sw["ext_i"]))
    n = int(p.flag_min_bars)
    s = e - n
    o0 = max(0, s - 6 * n)
    if s - o0 < 2:
        return None
    top, low = float(sd.h[s:e].max()), float(sd.l[s:e].min())
    oi = o0 + int(np.argmax(sd.h[o0:s]))
    origin = float(sd.h[oi])
    pole = origin - low
    if pole <= 0 or origin <= top + MIN1 or (top - low) > p.flag_max_frac * pole + MIN1:
        return None
    return dict(s=s, low=low, high=top, origin_i=oi, origin=origin)


def false_flag_gate(ctx, sd, sw, i: int, p, lvt: list, tags: dict):
    """The context gate `false_flag` ("tag" / "require"): the swept pool is the bottom of a flag (flag_info) AND (the flag lies under the EQ of the previous day's range or of today's swing - side
    space: the real "above EQ" -, or inside a same-side HTF array: `_htf_tag`). Tagged `false_flag`; the first target rung = the flagpole origin (the real flagpole origin low). Returns a reject key or None."""
    S = _S()
    fl = flag_info(ctx, sd, sw, i, p)
    ok = False
    if fl is not None and abs(float(sw["level"]) - fl["low"]) <= max(_tol(p) * 2, 0.1 * (fl["high"] - fl["low"])):
        eqs = []                                                # the EQ of the previous session's range and of the last five sessions' range (the daily swing) [our interpretation]
        for k_ in (1, 5):
            hs_ = getattr(ctx, "hist", [])[-k_:]
            if hs_:
                eqs.append(float(sd.x((max(float(f.high.max()) for f in hs_) + min(float(f.low.min()) for f in hs_)) / 2)))
        below_eq = any(fl["low"] < eq for eq in eqs)
        in_htf = bool(S._htf_tag(ctx, sd, i, float(sw["ext"]), _tol(p)))
        ok = below_eq or in_htf
    hit("false_flag_eval")
    if ok:
        hit("false_flag")
        lvt.append("false_flag")
        tags.setdefault("extra5", []).append((fl["origin"], "pool"))
        return None
    return "x_false_flag" if p.false_flag == "require" else None


# --- 66 M9-news-judas-full-sequence -----------------------------------------------------------------------------------------------------------------

def news_two_sided_gate(ctx, sd, sw, i: int, p, session: str, lvt: list, lvx: dict):
    """M9-news-judas-full-sequence (064 ~01:10:05): on a release day, from the bar its post-release range completes (`_news_ranges`): once BOTH extremes of that range have been taken
    (a later bar traded beyond each), the trade side = the extreme taken SECOND (the high -> long); the order arms only after a bar traded back to the range CE or the release-time open (the
    nearer of the two - bodies stop there, wicks may pass [our interpretation]); then the normal MSS + OB / FVG path; a body close below the OB's mean threshold exits. Orders armed within
    240 minutes of the release. Returns a reject key or None (None also when no completed release range applies)."""
    S = _S()
    drs = getattr(ctx, "news_dr", None) or {}
    t = int(ctx.t[i])
    rs = [R for R, d in drs.items() if d.get("made") is not None and R <= t and d["made"] <= i and t - R <= 240]
    if not rs:
        return None
    R = max(rs)
    d = drs[R]
    made = int(d["made"])
    hi, lo = float(d["hi"]), float(d["lo"])
    hh, ll = ctx.h[made + 1:i + 1], ctx.l[made + 1:i + 1]
    k_hi = np.flatnonzero(hh > hi)
    k_lo = np.flatnonzero(ll < lo)
    hit("news_two_sided_eval")
    if not len(k_hi) or not len(k_lo):
        return "x_news_2s_wait"
    k_hi, k_lo = made + 1 + int(k_hi[0]), made + 1 + int(k_lo[0])
    side = 1 if k_hi > k_lo else -1
    if sd.sign != side:
        return "x_news_2s_side"
    second = max(k_hi, k_lo)
    eq = float(d["eq"])
    o_rel = {510: S._open_known(ctx, "0830", i)}.get(R)
    refs = [eq] + ([float(o_rel)] if o_rel is not None else [])
    ref = max(refs) if side > 0 else min(refs)
    back = (ctx.l[second + 1:i + 1] <= ref + MIN1).any() if side > 0 else (ctx.h[second + 1:i + 1] >= ref - MIN1).any()      # a bar AFTER the second extreme trades back to the CE / the open
    if not back:
        return "x_news_2s_pullback"
    ob = S._ob_at_low(sd, sw, i, p, ctx)
    if ob is not None:
        lvx["news_ob_mt"] = (float(ob["mt"]), False)
    lvt.append("news_two_sided")
    hit("news_two_sided")
    return None


# --- 68 new-15m-candle-po3-upper-half ---------------------------------------------------------------------------------------------------------------

def po3_15m_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-15m-candle-po3-upper-half (065 ~04:29:00): at each 15m open (the bar that opens a clock-aligned 15 minutes), with the last `po3_15m_n` closed 15m bars all up-close (bullish flow, [our
    interpretation]) and a same-side BPR / FVG below price still intact: a buy limit at the new 15m open - 1 tick. The order is valid while price stays above 50% of the prior 15m bar (a trade below
    cancels) and is cut at the 15m close; a base-bar body close below the BPR / FVG EQ exits; the target = the prior 15m high + its range; the stop under the BPR / FVG [our interpretation]."""
    S = _S()
    t = int(ctx.t[i])
    m = 15
    if ctx.tf > m or m % ctx.tf or t % m != 0 or t < 570 or session not in ("AM", "PM") or _want(ctx) not in (0, sd.sign):
        return None
    first, last, done, o, hh, ll, cc = sm4.buckets(ctx, sd, m)
    ok = np.flatnonzero(done & (last < i))              # the closed 15m bars before the one that opens now
    n = int(p.po3_15m_n)
    if len(ok) < n:
        return None
    last_n = ok[-n:]
    if not all(cc[j] > o[j] for j in last_n):
        return None
    prev = int(ok[-1])
    if int(last[prev]) != i - 1:
        return None                                      # the prior bucket must be the one right before this bar
    sent = sd.__dict__.setdefault("_po3_15_sent", set())
    if i in sent:
        return None
    zones = [(float(g.top), float(g.bottom), "fvg") for g in sd.gaps if g.i <= i and float(sd.c[g.i + 1:i + 1].min(initial=np.inf)) >= g.bottom - MIN1 and g.top < sd.o[i]]
    zones += [(float(z.top), float(z.bottom), "bpr") for z in sd.bprs() if z.i <= i and z.kind == "bull" and float(sd.c[z.i + 1:i + 1].min(initial=np.inf)) >= z.bottom - MIN1 and z.top < sd.o[i]]
    if not zones:
        return None
    top_z, bot_z, kind_z = max(zones, key=lambda z: z[0])
    entry = float(sd.o[i]) - float(p.tick)
    half = float((hh[prev] + ll[prev]) / 2)
    if entry <= half + MIN1 or entry - bot_z < p.min_risk_pts * p.es_pt:
        return None
    ce = (top_z + bot_z) / 2
    tgt = float(hh[prev] + (hh[prev] - ll[prev]))
    if tgt <= entry + MIN1:
        return None
    sent.add(i)
    hit("po3_15m")
    o_ = sm4._order(ctx, sd, i, p, session, risk_mult, "po3_15m", entry, bot_z - p.pad, level=float(sd.o[i]), ext=float(ll[prev]), ext_i=int(first[prev]), fvg_bottom=bot_z, fvg_ce=ce,
                    fixed=[(float(S._exit_px(tgt, "array", p)), "array")], cancel_low=half, cut=t + m, lvx={"po3_15m_ce": (float(ce), False)}, lv=("po3_15m",))
    return o_


# --- 70 M12-turtle-soup-prev-pm-low -----------------------------------------------------------------------------------------------------------------

def prev_pm_limit(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M12-turtle-soup-prev-pm-low (067 ~00:20:12): turtle_soup "prev_pm" - the weekly bias this way (`weekly_bias` / ctx.wbias) and price near the previous day's 13:30-16:00 range at 09:30: a
    resting limit 1 tick beyond the range's far low (side space: under it), once, armed on the first AM bar; the target = the range's other extreme (the previous PM high), the stop under the
    run (`ts_max_pts` under the level, as cc_limit) [our interpretation: the sweep extreme does not exist yet]. Experienced-only, default off."""
    S = _S()
    if session != "AM" or ctx.t[i] != 570 or "prev_pm" not in ctx.sess:
        return None
    wb = int(getattr(ctx, "wbias", 0) or 0)
    if wb != sd.sign:
        return None
    sent = sd.__dict__.setdefault("_ppm_sent", set())
    if ctx.day in sent:
        return None
    hi, lo, _ = ctx.sess["prev_pm"]
    lvl = float(sd.x(lo if sd.sign > 0 else hi))               # the pool beyond the range (side space: its low)
    lvl = float(S._SM6.prev_pm_body(ctx, sd, lvl, p))          # caption-gap E2-body-extreme-entry: ts_level_src "body" = the range's extreme body
    other = float(sd.x(hi if sd.sign > 0 else lo))
    px = float(sd.c[i])
    rng = other - lvl
    if rng <= 0 or not (lvl < px <= other + rng):
        return None                                           # not near the range
    entry = lvl - float(p.tick)
    if entry >= px - MIN1:
        return None
    stop = entry - p.ts_max_pts * p.es_pt - p.pad
    sent.add(ctx.day)
    hit("prev_pm_limit")
    sw = sm4._synth(S, session, "prev_pm_turtle", lvl, entry, i, None)
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=(entry + stop) / 2, entry_kind="prev_pm_turtle", mitigation=False, propulsion=False, no_leg_wait=True, no_expire=True, lv_tags=["prev_pm_turtle"])
    return S._finish_order(ctx, sd, i, p, session, sw, entry, stop, risk_mult, float(sd.h[i]), tags, skip_leg_pd=True, fixed=[(float(S._exit_px(other, "pool", p)), "pool")])


# --- 72 M7-second-dip-into-rejection-block ----------------------------------------------------------------------------------------------------------

def second_dip_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M7-second-dip-into-rejection-block (067 ~01:05:38): PM, the lunch low (12:00-13:30) swept (wick low L = the lowest low since the first trade under it, before the dip); RB = the lowest
    CLOSE of that swing (from the pivot high before L's bar to it); a later bar that trades under RB but holds above L (RB > low > L) arms the entry on a bullish lowest-timeframe PD array of that dip
    - an FVG / IFVG formed after L that no close went through, in the discount of the move since L (top at or under its EQ): a limit at the array's top, the stop under L (X8 exception: the
    M1.3 body-low cancel is replaced by L itself - the idea is stopped only when L is taken), the targets the lunch high then the ORG buy-side. Bearish = mirror (side space)."""
    S = _S()
    if session != "PM" or "lunch" not in ctx.sess or ctx.t[i] < 810 or _want(ctx) not in (0, sd.sign):
        return None
    k810 = S._idx_at(ctx, 810)
    if i <= k810 + 3:
        return None
    hi_r, lo_r, _ = ctx.sess["lunch"]
    lvl = float(sd.x(lo_r if sd.sign > 0 else hi_r))
    seg = np.flatnonzero(sd.l[k810:i] < lvl - MIN1)
    if not len(seg):
        return None
    k0 = k810 + int(seg[0])
    e = k0 + int(np.argmin(sd.l[k0:i]))
    L_ = float(sd.l[e])
    ph = [q for q in sd.ph if q.i < e and q.known <= i]            # known by the judged bar (review fix: `e + pivot_n` could be after i)
    a = ph[-1].i if ph else max(k0 - 5, 0)
    RB = float(sd.c[a:e + 1].min())
    j0 = next((j for j in range(e + 2, i + 1) if L_ + MIN1 < sd.l[j] < RB - MIN1 and (sd.c[e + 1:j] > RB).any()), None)
    if j0 is None:
        return None                                              # no later dip under RB that holds above L (after a bounce)
    top_since = float(sd.h[e:i + 1].max())
    eq = L_ + 0.5 * (top_since - L_)
    arrs = [(float(g.top), float(g.bottom), "fvg", g.i) for g in sd.gaps if g.i - 2 >= j0 and g.i <= i and sd.c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom - MIN1]
    arrs += [(float(z.top), float(z.bottom), "ifvg", z.i) for z in sd.ifvgs() if j0 < z.i <= i and sd.c[z.i + 1:i + 1].min(initial=np.inf) >= z.bottom - MIN1]
    arrs = [x for x in arrs if x[0] <= eq + MIN1 and x[1] > L_ and x[0] < sd.c[i]]
    sent = sd.__dict__.setdefault("_rb2_sent", set())
    arrs = [x for x in arrs if (e, round(x[0], 6)) not in sent]
    if not arrs:
        return None
    top, bot, kind, gi = max(arrs, key=lambda x: x[0])
    lun_hi = float(sd.x(hi_r if sd.sign > 0 else lo_r))
    fx = [(float(S._exit_px(lun_hi, "pool", p)), "pool")] if lun_hi > top else []
    if getattr(ctx, "org_today", False) and ctx.org:
        for v in (sd.x(ctx.org[-1][0]), sd.x(ctx.org[-1][1])):
            if v > max(top, lun_hi) + p.es_pt:
                fx.append((float(S._exit_px(float(v), "array", p)), "array"))
    if not fx:
        return None
    sent.add((e, round(top, 6)))
    hit("second_dip")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "second_dip", top, L_ - p.pad, level=lvl, ext=L_, ext_i=e, fvg_bottom=bot, fixed=sorted(set(fx)), body_low=L_, lv=("second_dip_" + kind,))


# --- 75 M8-org-repricing-full-conditions / 76 M0-all-nearby-pools-run-first -------------------------------------------------------------------------

def pool_levels(ctx, sd, i: int, names, pts: float, session: str, es_pt: float = 1.0):
    """The Judas-side pools of `names` (side space: the sell-side low of a long / the buy-side high of a short mirrored) that exist at bar i and lie at or beyond the session open within `pts`
    ES points of it: [(name, level, created bar)]. london = the 02:00-05:00 range (from 05:00), prev_ny = the previous regular session's extreme, lunch = the 12:00-13:30 range (from 13:30),
    prev_pm = the previous 13:30-16:00 range. Names this does not know are skipped."""
    S = _S()
    m0 = 810 if session == "PM" else 570
    k0 = S._idx_at(ctx, m0)
    if k0 > i or k0 >= len(ctx.t):
        return []
    open_s = float(sd.o[k0])
    out = []
    for nm in names:
        if nm == "london" and "london" in ctx.sess and S._idx_at(ctx, 300) <= i:
            hi, lo, _ = ctx.sess["london"]
            lv, cr = float(sd.x(lo if sd.sign > 0 else hi)), S._idx_at(ctx, 300)
        elif nm == "prev_pm" and "prev_pm" in ctx.sess:
            hi, lo, _ = ctx.sess["prev_pm"]
            lv, cr = float(sd.x(lo if sd.sign > 0 else hi)), ctx.start
        elif nm == "lunch" and "lunch" in ctx.sess and S._idx_at(ctx, 810) <= i:
            hi, lo, _ = ctx.sess["lunch"]
            lv, cr = float(sd.x(lo if sd.sign > 0 else hi)), S._idx_at(ctx, 810)
        elif nm == "prev_ny":
            pr = _prev_range_real(ctx)
            if pr is None:
                continue
            lv, cr = float(sd.x(pr[1] if sd.sign > 0 else pr[0])), ctx.start
        else:
            continue
        if lv <= open_s + MIN1 and open_s - lv <= pts * es_pt + MIN1:
            out.append((nm, lv, cr))
    return out


def pools_taken(ctx, sd, i: int, p, names, pts: float, session: str):
    """(listed, taken): how many of the Judas-side pools of `names` within `pts` ES points of the open exist, and how many of them the day's bars traded through by bar i."""
    ls = pool_levels(ctx, sd, i, names, pts, session, p.es_pt)
    taken = 0
    for nm, lv, cr in ls:
        a = max(cr, ctx.start)
        if float(sd.l[a:i + 1].min(initial=np.inf)) <= lv + MIN1:
            taken += 1
    return len(ls), taken


def all_pools_gate(ctx, sd, sw, i: int, p, session: str, lvt: list):
    """M0-all-nearby-pools-run-first (069 ~00:16:49): before a counter-Judas entry every listed pool of the Judas side (`all_pools_names`) within `all_pools_pts` of the open must have been run:
    "tag" (lv_tag all_pools) / "require" (the MSS after only the nearer pool is dropped). No listed pool nearby = nothing to wait for. Returns a reject key or None."""
    if session not in ("AM", "PM"):
        return None
    n, k = pools_taken(ctx, sd, i, p, p.all_pools_names, p.all_pools_pts, session)
    if not n:
        return None
    hit("all_pools_eval")
    if k == n:
        lvt.append("all_pools")
        hit("all_pools")
        return None
    return "x_all_pools" if p.all_pools_first == "require" else None


def org_reprice_gate(ctx, sd, sw, i: int, p, session: str, entry: float, tags: dict):
    """M8-org-repricing-full-conditions (069 ~00:14:49): an order whose ladder starts at the ORG (targets.refine tagged it `org_reprice`) is REJECTED unless ALL hold - the Judas ran beyond the
    midnight open and took both the London and the prior-day NY pools (item 76's helper, no distance limit); a same-side premium array sits at the sweep (`_htf_tag`); it is armed 10:00-11:00 (fill
    by 11:00: tags cut 660); the ORG lies between the entry and the htf.table draw ([our interpretation], the owner-side filter). Returns a reject key or None."""
    S = _S()
    t = int(ctx.t[i])
    if session != "AM" or not (600 <= t < 660):
        return "x_org_reprice_time"
    mo = S._open_known(ctx, "midnight", i)
    if mo is None or not float(sw["ext"]) < float(sd.x(mo)):
        return "x_org_reprice_midnight"
    n, k = pools_taken(ctx, sd, i, p, ("london", "prev_ny"), 1e9, session)
    if n < 2 or k < n:
        return "x_org_reprice_pools"
    if not S._htf_tag(ctx, sd, i, float(sw["ext"]), _tol(p)):
        return "x_org_reprice_array"
    if not (getattr(ctx, "org_today", False) and ctx.org):
        return "x_org_reprice_org"                                # review fix: no ORG today - nothing to price toward
    a, b = ctx.org[-1]
    near = float(min(sd.x(a), sd.x(b)))
    dr = sm3.row_draw(ctx, sd, i, session)
    if dr is None or not (entry < near < float(dr[0])):
        return "x_org_reprice_draw"
    tags["cut"] = 660
    hit("org_reprice_full")
    return None


# --- 77 M7-lunch-reprice-org-ce-moc -----------------------------------------------------------------------------------------------------------------

def lunch_org_order(ctx, sd, i: int, p, risk_mult: float):
    """M7-lunch-reprice-org-ce-moc (069 ~00:20:38; research, in conflict with T8): 12:00-13:30 on a day whose AM-locked HTF draw (this side) is still undelivered, today's ORG lying on the far
    side (side space: below the open): a limit at max(ORG CE, lunch relative equal highs + 1 tick) - real; side space min(CE, lunch rel-eq lows - 1 tick) - the nearest of them under the close;
    the stop beyond the ORG's far edge [our interpretation: ICT gives none]; the single target the locked draw; held to the MOC (flat at the close / at the lock). Session PM for the order's
    window rules, done key LOCS."""
    S = _S()
    t = int(ctx.t[i])
    lk = ctx.lock.get("AM") if getattr(ctx, "lock", None) else None
    if not (720 <= t < 810) or lk is None or lk.get("side") != sd.sign or lk.get("delivered") or not (getattr(ctx, "org_today", False) and ctx.org):
        return None
    pc, op = ctx.org[-1]
    pcx, opx = float(sd.x(pc)), float(sd.x(op))
    if not pcx < opx - MIN1:
        return None                                              # the ORG must lie where this side's retrace goes (its far edge under the open in side space)
    ce = (pcx + opx) / 2
    k12 = S._idx_at(ctx, 720)
    tol = _tol(p)
    qs = [q for q in sd.pl if k12 <= q.i and q.known <= i]
    reh = [v for v in L.equal_levels([q.price for q in qs], tol)] if len(qs) >= 2 else []
    reh = [v for v in reh if sd.l[k12:i + 1].min() >= v - MIN1 and v < sd.c[i]]
    entry = float(min(ce, max(reh) - float(p.tick))) if reh else float(ce)
    if entry >= sd.c[i] - MIN1:
        return None
    sent = sd.__dict__.setdefault("_locs_sent", set())
    if ctx.day in sent:
        return None
    stop = float(min(pcx, entry) - p.pad)
    stop = _min_stop(p, entry, stop)
    tv = float(sd.x(lk["target"]))
    if tv <= entry + MIN1:
        return None
    sent.add(ctx.day)
    hit("lunch_org_ce_short")
    return sm4._order(ctx, sd, i, p, "PM", risk_mult, "lunch_org_ce_short", entry, stop, level=ce, fvg_bottom=pcx, fixed=[(float(S._exit_px(tv, lk["kind"], p)), lk["kind"])],
                      exit_at=960, done_key="LOCS", no_expire=True, lv=("lunch_org_ce_short",))


# --- 79 M4-1m-last-upclose-finetune -----------------------------------------------------------------------------------------------------------------

def breaker_zone_tf(ctx, sd, a0: int, to: int, i: int, p):
    """M4-1m-last-upclose-finetune (070 ~00:55:41): `breaker_tf` m > the base timeframe - the breaker zone is built on the m-minute bars (the 5m leg) of the day: the same breaker_zone helper on the
    COMPLETED m-minute buckets, mapped back to base-bar indices (known at bar i). None = no zone (the base-bar zone stands)."""
    m = int(p.breaker_tf)
    if m <= ctx.tf or m % ctx.tf:
        return None
    first, last, done, o, hh, ll, cc = sm4.buckets(ctx, sd, m)
    ok = np.flatnonzero(done & (last <= i))
    if len(ok) < 3:
        return None
    nb = int(ok[-1]) + 1
    bi = lambda k: max(0, int(np.searchsorted(first[:nb], max(k, 0), side="right") - 1))
    z = L.breaker_zone(o[:nb], hh[:nb], ll[:nb], cc[:nb], bi(a0), bi(to), nb - 1, "bull", p.breaker_zone, p.breaker_mt_mode, p.breaker_candle, p.breaker_body_swing)
    if z is None:
        return None
    hit("breaker_zone_tf")
    return L.Zone("bull", z.top, z.bottom, i, int(first[min(z.src, nb - 1)]), z.mt, levels=z.levels)


def breaker_last_1m(ctx, sd, sw, bz, i: int, p):
    """M4-1m-last-upclose-finetune: `breaker_pref` "last_1m" - inside the (m-minute) breaker zone the entry block is the LAST up-close base bar before the run to the lower low (the sweep extreme),
    treated as an order block: a limit at its MT (`mt_mode`: body mean / range mid), filled only on a print 1 tick through (E3). Returns (entry, bottom) or None (the zone top stands)."""
    e = int(sw["ext_i"])
    tol = _tol(p)
    ks = [k for k in range(max(ctx.start, e - 120), e) if sd.c[k] > sd.o[k] and sd.l[k] >= bz.bottom - tol and sd.h[k] <= bz.top + tol]
    if not ks:
        return None
    k = ks[-1]
    from .es1 import candle_mt
    mt = float((sd.o[k] + sd.c[k]) / 2) if p.mt_mode == "body" else candle_mt(p, sd.o[k], sd.h[k], sd.l[k], sd.c[k])
    if mt >= sd.c[i] - MIN1:
        return None
    hit("breaker_last_1m")
    return mt, float(sd.l[k])


# --- 80 M4-two-pool-breaker-near-miss ---------------------------------------------------------------------------------------------------------------

def near_miss_tag(ctx, sd, sw, i: int, p, lvt: list) -> None:
    """M4-two-pool-breaker-near-miss (070 ~00:41:22): before the sweep bar, a swing low formed within `near_miss_pts` ES points ABOVE the swept pool after a bounce of at least that size (the
    price came close to the pool without taking it, bounced, then dropped through) [our interpretation of "at least as large"]: tag `near_miss`."""
    v = float(sw["level"])
    pts = p.near_miss_pts * p.es_pt
    sw_i = int(sw.get("sweep_i", sw["ext_i"]))
    for q in sd.pl:
        if q.i >= sw_i or q.known > sw_i or not (v + MIN1 < q.price <= v + pts + MIN1):
            continue
        if float(sd.h[q.i:sw_i].max(initial=-np.inf)) - q.price >= pts - MIN1:
            lvt.append("near_miss")
            hit("near_miss")
            return


# --- 81 M4-unfinished-high-keep-ab-leg --------------------------------------------------------------------------------------------------------------

def ab_anchor(ctx, sd, A: float, B: float, i: int, p, session: str):
    """M4-unfinished-high-keep-ab-leg (070 ~00:52:42): `ab_anchor_lock` - once an advanced-breaker order of this side FILLED (`on_fill`), its A-B leg stays the projection anchor while the session's
    locked target (the HTF draw beyond B) is still untaken: a newer swing high below that target does not re-anchor. Returns (A, B)."""
    st = sd.__dict__.get("_ab5")
    if st is None or st["day"] != ctx.day or st["session"] != session:
        return A, B
    if not st["filled"] or bool(_S()._SM.htf_done(ctx, sd, i)):
        return A, B
    hit("ab_anchor_kept")
    return st["A"], st["B"]


def ab_note(ctx, sd, A: float, B: float, session: str) -> dict:
    """The A-B leg the order was built from (kept per side and session; `filled` flips at the fill): the order's sm5 tag."""
    st = sd.__dict__.get("_ab5")
    if st is None or st["day"] != ctx.day or st["session"] != session or not st["filled"]:
        st = sd.__dict__["_ab5"] = dict(day=ctx.day, session=session, A=float(A), B=float(B), filled=False)
    return dict(kind="ab_anchor")


# --- 83 M11-cisd-ob-stop-skip-rearm -----------------------------------------------------------------------------------------------------------------

def cisd_htf_ok(ctx, sd, sw, i: int, p) -> bool:
    """M11-cisd-ob-stop-skip-rearm (075 ~01:19:43), context: the sweep extreme sits in a same-side HTF array (`_htf_tag`) - the CISD OB is taken only there."""
    S = _S()
    ok = bool(S._htf_tag(ctx, sd, i, float(sw["ext"]), _tol(p)))
    hit("cisd_htf_ok" if ok else "cisd_htf_no")
    return ok


def cisd_floor(sw, e: int, ob_bottom: float, sd, i: int, p) -> int:
    """`cisd_rearm`: once a bar traded below the CISD OB's low (the setup is void), the next CISD must come AFTER that bar: returns the last bar the search must start after (e by default)."""
    f = int(sw.get("cisd_floor", e))
    if p.cisd_rearm:
        k = np.flatnonzero(sd.l[e + 1:i + 1] < ob_bottom - MIN1)
        if len(k):
            f = max(f, e + 1 + int(k[-1]))
    return f


# --- 84 M10-ifvg-footholds-buy-program --------------------------------------------------------------------------------------------------------------

def ifvg_hunt_ok(ctx, sd, i: int, p, tags: dict) -> bool:
    """M10-ifvg-footholds-buy-program (075 ~01:29:33): an IFVG entry arms only after a short-term low (a pivot low under the price) was run since the IFVG formed while no body has closed below the
    IFVG's CE (the stop hunt first, expected near the equilibrium; bodies respect the CE). `tags` = the order's tags (zone top / bottom / CE / bar)."""
    zi = tags.get("fvg_i")
    ce = tags.get("fvg_ce")
    if zi is None or ce is None:
        return True
    zi = int(zi)
    if float(sd.c[zi + 1:i + 1].min(initial=np.inf)) < float(ce) - MIN1:
        return False
    for q in sd.pl:
        if q.known > i or q.price >= sd.c[i]:
            continue
        a = max(q.known, zi + 1)
        if a <= i and float(sd.l[a:i + 1].min()) < q.price - MIN1:
            hit("ifvg_hunt")
            return True
    return False


def ifvg_target_levels(ctx, sd, sw, i: int, p, above: float) -> list:
    """M10-ifvg-footholds-buy-program, targets part: after the CISD / MSS (sw["broke"] set) the bearish FVGs of the prior down leg that are still open (no high went into them since) are buy-side
    delivery targets first - near edge and CE: [(level, "array")] above `above` (side space)."""
    if sw.get("broke") is None:
        return []
    e = int(sw["ext_i"])
    out = []
    for z in sd.opposing():
        if z.kind != "bear" or z.i > e + 1 or z.i < max(ctx.start - 1, 0) or z.bottom <= above:
            continue
        if float(sd.h[z.i + 1:i + 1].max(initial=-np.inf)) >= z.bottom:
            continue
        out += [(float(z.bottom), "array"), (float(z.mid), "array")]
    if out:
        hit("ifvg_targets")
    return out


# --- 86 A4-bodies-hold-prev-day-50 ------------------------------------------------------------------------------------------------------------------

def pd50_gate(ctx, sd, sw, i: int, p, tags: dict):
    """A4-bodies-hold-prev-day-50 (076 ~00:22:29): for an order whose sweep extreme lies INSIDE the previous day's range, no body may have closed on the wrong side of the previous day's 50% between
    the sweep extreme and now (base bars, or the completed `pd50_tf`-minute bars; wicks may pierce it); a body close past it = a failed confirmation (the order is dropped), and a pending order is
    cancelled by such a close (`cancel_close`, base-bar frame only). Returns a reject key or None."""
    pr = _prev_range_real(ctx)
    if pr is None:
        return None
    lo_s, hi_s = sorted((float(sd.x(pr[1])), float(sd.x(pr[0]))))
    if not (lo_s <= float(sw["ext"]) <= hi_s):
        return None
    mid = float(sd.x((pr[0] + pr[1]) / 2))
    e = int(sw["ext_i"])
    hit("pd50_eval")
    m = int(p.pd50_tf)
    if m > ctx.tf and m % ctx.tf == 0:
        first, last, done, o, hh, ll, cc = sm4.buckets(ctx, sd, m)
        ok = np.flatnonzero(done & (last <= i) & (first >= e))
        closes = cc[ok]
    else:
        closes = sd.c[e:i + 1]
    if len(closes) and float(closes.min()) < mid - MIN1:
        hit("pd50_fail")
        return "x_pd50_bodies"
    if m <= ctx.tf:
        tags["cancel_close"] = max(float(tags.get("cancel_close", -np.inf)), mid)
    elif m % ctx.tf == 0:
        tags["cancel_close_tf"] = (float(mid), m)               # review fix: a pending order is cancelled by a completed `pd50_tf` bar closing under the 50% (tf_close_cancel)
    hit("pd50_hold")
    return None


def tf_close_cancel(ctx, sd, pending: dict, j: int) -> bool:
    """True when a COMPLETED `m`-minute bar (its last base bar <= j, started after the order was armed) closed under the level of `pending["cancel_close_tf"]` = (level, m)."""
    lvl, m = pending["cancel_close_tf"]
    first, last, done, o, hh, ll, cc = sm4.buckets(ctx, sd, int(m))
    ok = np.flatnonzero(done & (last <= j) & (first > int(pending["i"])))
    if len(ok) and float(cc[ok].min()) < lvl - MIN1:
        hit("pd50_pending_cancel")
        return True
    return False


# --- 87 new-overshoot-ltf-fvg-into-htf-level --------------------------------------------------------------------------------------------------------

def overshoot_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """new-overshoot-ltf-fvg-into-htf-level (078 ~01:22:24), side space (the short = the mirrored long): a 60m FVG (the SIBI of the real short) whose near edge lies within `overshoot_pts` ES points
    of an OLDER same-side daily FVG's near edge (the 60m FVG sits just short of the daily level, price overshoots into it): a limit one tick beyond the 60m FVG's near edge (filled when price
    trades through it), the stop beyond the swing that formed the leg - the last swing low (side space) before the 60m FVG's displacement - never beyond the FVG / daily level; invalid
    when that swing is taken (`cancel_low`); the targets the normal ladder (the next pool). One order per 60m FVG."""
    S = _S()
    if _want(ctx) not in (0, sd.sign):
        return None
    sent = sd.__dict__.setdefault("_ovs_sent", set())
    daily = sm4.conf_arrays(ctx, sd, i, ("D",))
    if not daily:
        return None
    tol, pts = _tol(p), p.overshoot_pts * p.es_pt
    for z in sorted(sm4._tf_fvgs(ctx, sd, 60), key=lambda z: -z.i):
        if z.i > i or z.i in sent or not sm4._alive(sd, z, i):
            continue
        near = float(z.bottom)                                  # the 60m FVG's edge toward the daily level (side space: the real top / the mirrored bottom)
        d_ok = [d for d in daily if 0 <= near - float(d[0]) <= pts + MIN1]    # the daily FVG (top, bottom) sits just under the 60m gap
        if not d_ok:
            continue
        entry = near - float(p.tick)
        if entry >= sd.c[i] - MIN1:
            continue
        sw_lows = [q for q in sd.pl if q.known <= z.src + 1 and q.i < z.src]
        if not sw_lows:
            continue
        q = sw_lows[-1]
        stop = float(q.price) - p.pad
        if entry - stop < p.min_risk_pts * p.es_pt:
            continue
        sent.add(z.i)
        hit("htf_overshoot")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "htf_overshoot", entry, stop, level=near, ext=float(q.price), ext_i=int(q.i), fvg_bottom=float(z.bottom),
                          cancel_low=float(q.price), lv=("htf_overshoot",))
    return None


# --- 88 new-open-returns-into-bearish-ob / 89 B5-ltf-at-htf-array -----------------------------------------------------------------------------------

def open_ob_note(ctx, sd, sw, i: int, p, session: str, tags: dict) -> None:
    """new-open-returns-into-bearish-ob (081 ~00:11:34): note on the order that the entry OB formed BEFORE the session open (09:30, or 13:30 for the PM) - the fill tag `open_into_ob` is set at the
    fill if it comes within `open_ob_min` minutes of that open (`on_fill`)."""
    S = _S()
    m0 = 810 if session == "PM" else 570
    ob = S._ob_at_low(sd, sw, i, p, ctx)
    if ob is None or (ctx.idx[ob["k"]].date() == ctx.day and int(ctx.t[ob["k"]]) >= m0):
        return                                                  # no OB, or it formed after the open
    st = tags.setdefault("sm5", {})
    st["open_ob"] = int(m0)
    hit("open_ob_note")


def htf_arrays(ctx, sd, i: int, p) -> list:
    """The same-side 15m / 60m arrays at bar i, side space [(top, bottom)]: the Confluence object's FVG / OB / VI of those timeframes (when present) and the day's own 15m / 60m FVGs that no
    close went through."""
    out = [(a, b) for a, b, _ in sm4.conf_arrays(ctx, sd, i, ("15m", "1h"), (0, 1, 3), known_at_start=False)]
    for m in (15, 60):
        out += [(float(z.top), float(z.bottom)) for z in sm4._tf_fvgs(ctx, sd, m) if z.i <= i and sm4._alive(sd, z, i)]
    return out


def htf_entry_gate(ctx, sd, i: int, p, entry: float, lvt: list):
    """B5-ltf-at-htf-array (082 ~00:06:22): `htf_entry_array` tag / require - the entry (limit) lies inside a same-side 15m / 60m array (FVG / OB / VI, +- the equal tolerance)."""
    tol = _tol(p)
    hit("htf_entry_eval")
    if any(b - tol <= entry <= a + tol for a, b in htf_arrays(ctx, sd, i, p)):
        lvt.append("htf_entry_array")
        hit("htf_entry_array")
        return None
    return "x_htf_entry_array" if p.htf_entry_array == "require" else None


def htf_cands(ctx, sd, sw, i: int, p) -> list:
    """entry_arrays "htf" (B5): the near edge (top, side space) of each same-side 15m / 60m array between the sweep extreme and the close: [(top, bottom, "htf")]."""
    out = [(a, b, "htf") for a, b in htf_arrays(ctx, sd, i, p) if float(sw["ext"]) < a < float(sd.c[i])]
    if out:
        hit("htf_cands")
    return out


# --- 104 M13-max-depth-79 ---------------------------------------------------------------------------------------------------------------------------

def depth_filter(sd, sw, gaps: list, i: int, p) -> list:
    """M13-max-depth-79 (102 ~01:00:33): after the MSS an FVG is no entry when reaching it needs a very deep retracement of the displacement leg ("harmonic territory"): the gap's NEAR edge (its top,
    side space) lies deeper than `max_retrace` of the leg - the sweep extreme .. the highest high since (0.79 = the OTE upper bound [our interpretation of ICT's unnamed cap]). Combined with the
    M2 at-or-above-50% rule the valid gaps sit between 50% and the cap."""
    ext = float(sw["ext"])
    leg_hi = float(sd.h[int(sw["ext_i"]):i + 1].max())
    rng = leg_hi - ext
    if rng <= 0:
        return gaps
    out = [g for g in gaps if (leg_hi - float(g.top)) / rng <= p.max_retrace + MIN1]
    if len(out) < len(gaps):
        hit("max_retrace_drop")
    return out


# --- 98 A15-mitigation-block-entry (entry_arrays "mitigation") / 99 A15-stair-step-mitigation -------------------------------------------------------

def _mit_zones(ctx, sd, i: int, p):
    """The alive bullish mitigation blocks (side space) of the execution TF (today's bars) or, with `mit_entry_tf` "D", of the completed daily bars; [(zone, gaps)] with the gaps of the same bar
    set for the adjacent-FVG stop."""
    out = []
    if p.mit_entry_tf == "D":
        dsd = daily_side(ctx, sd, p)
        if dsd is None:
            return out
        n = len(dsd.c) - 1
        for z in dsd.mitigations():
            if L.mitigation_alive(dsd.c, z, n, p.mit_mt_invalid):
                out.append((z, dsd.gaps))
        return out
    for z in sd.mitigations():
        if ctx.start <= z.i <= i and L.mitigation_alive(sd.c, z, i, p.mit_mt_invalid):
            out.append((z, sd.gaps))
    return out


def mit_cand(ctx, sd, sw, i: int, p):
    """A15-mitigation-block-entry (098 ~00:45:55), entry_arrays "mitigation": the alive mitigation block (execution TF, or daily with `mit_entry_tf` "D") the retrace has reached: a limit at its
    near edge (side space: its top) - only while the price sits on the open's wrong side (real: above the day's opening price for a short = the high part of a bearish PO3; side space: under the
    midnight open's mirror); the stop beyond the block's MT and the adjacent FVG's far edge (the 3-PD-array shield: MB MT, OB MT, the FVG's high). Returns (entry, stop reference, "mitigation") or None."""
    S = _S()
    mo = S._open_known(ctx, "midnight", i)
    if mo is None or not float(sd.c[i]) < float(sd.x(mo)):         # an unknown midnight open rejects (review fix: it used to let the entry through unfiltered)
        return None
    tol = _tol(p)
    best = None
    for z, gaps in _mit_zones(ctx, sd, i, p):
        mt = float(z.mt) if z.mt == z.mt else float((z.top + z.bottom) / 2)
        adj = [float(g.bottom) for g in gaps if g.bottom <= z.top + tol and g.top >= z.bottom - tol]
        ref = min([mt] + adj)
        top_ = float(z.top)
        if p.mit_entries and z.src >= 0:
            top_ = min(top_, float(max(sd.o[z.src], sd.c[z.src])))     # caption-gap E6-mitigation-block-stop (cc04_004 ~00:14:00): the limit at the mitigation candle's BODY edge (side space: the body top) ...
            ref = float(z.bottom)                                       # ... and the stop beyond the candle's far extreme (+ the pad)
            _S()._ES3.hit("mit_entries")
        if best is None or top_ > best[0]:
            best = (top_, float(ref), "mitigation")
    if best is not None:
        hit("mit_entry_array")
    return best


def stair_blocks(ctx, sd, i: int, p) -> list:
    """A15-stair-step-mitigation (cc04_004 ~00:11:52): each swing high (side space) the price has CLOSED above is broken; the last up-close candle at (or just before) it is a new mitigation block - its
    whole range is usable. Returns [dict(top, bottom, j, broke)] in swing order, today's blocks only."""
    out = []
    for q in sd.ph:
        if q.known > i or q.i < ctx.start:
            continue
        br = np.flatnonzero(sd.c[q.known:i + 1] > q.price)
        if not len(br):
            continue
        ks = [k for k in range(max(ctx.start, q.i - 5), q.i + 1) if sd.c[k] > sd.o[k]]
        if not ks:
            continue
        j = ks[-1]
        out.append(dict(top=float(sd.h[j]), bottom=float(sd.l[j]), j=j, broke=int(q.known + br[0])))
    return out


def mit_stair_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A15-stair-step-mitigation: with the bias this way, the HTF target untaken and no position: a limit (`mb_order` "limit": at the block's near edge) or a stop (`mb_order` "stop": one tick beyond
    the block's top, armed while price is inside / under it) at the NEWEST broken-swing block whose bodies were never violated (no close under its bottom); the stop beyond the block's far edge; the
    first retrace only; the target = the next swing / the HTF draw (the normal ladder). The adds of later blocks are `manage`."""
    S = _S()
    if _want(ctx) != sd.sign or S._SM.htf_done(ctx, sd, i):
        return None
    sent = sd.__dict__.setdefault("_stair_sent", set())
    bl = [b for b in stair_blocks(ctx, sd, i, p) if b["j"] not in sent and float(sd.c[b["broke"] + 1:i + 1].min(initial=np.inf)) >= b["bottom"] - MIN1]
    if not bl:
        return None
    b = bl[-1]
    px = float(sd.c[i])
    if p.mb_order == "stop":
        entry = b["top"] + float(p.tick)
        if px >= entry - MIN1 or px > b["top"] + MIN1:
            return None
        extra = dict(stop_entry=True)
    else:
        entry = b["top"]
        if px <= entry + MIN1:
            return None
        extra = {}
    stop = b["bottom"] - p.pad
    if entry - stop < p.min_risk_pts * p.es_pt:
        stop = entry - p.min_risk_pts * p.es_pt
    sent.add(b["j"])
    hit("mit_stair")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "mit_stair", entry, stop, level=b["top"], ext=b["bottom"], ext_i=b["j"], fvg_bottom=b["bottom"], no_expire=True, cancel_close=b["bottom"],
                      sm5=dict(kind="mit_stair", j=int(b["j"])), lv=("mit_stair",), **extra)


# --- 101 new-next-day-or-reh-short -------------------------------------------------------------------------------------------------------------------

def prev_reh_levels(ctx, sd, i: int, p) -> list:
    """new-next-day-or-reh-short (099 ~00:52:08), real terms for a SHORT (the long is its mirror, the code runs in side space): the prior day drove down into the lower half of an HTF bullish
    FVG (its close inside the lower half), the overnight did not trade below the prior day's low; then the relatively equal HIGHS of the prior day's rally on the 15m bars (still untraded
    overnight) are the AM pools. Returns the pools' levels in side space (rel-eq lows for the side's own space) - empty when the context fails."""
    S = _S()
    key = ("reh", sd.sign, ctx.day)
    c = _c(ctx)
    if key in c:
        return c[key]
    out = []
    pr = _prev_range_real(ctx)
    pmk = "pml" if sd.sign < 0 else "pmh"
    pdk = "pdl1" if sd.sign < 0 else "pdh1"
    if pr is not None and pmk in ctx.pd and pdk in ctx.pd and float(sd.x(ctx.pd[pmk])) < float(sd.x(ctx.pd[pdk])) - MIN1:
        other = sm2.other_side(ctx, sd, p)
        pcx = float(other.x(pr[2]))
        ok = any(b - MIN1 <= pcx <= (a + b) / 2 + MIN1 for a, b, _ in sm4.conf_arrays(ctx, other, i, ("D",)))
        if ok:
            hb = S.htf_bars(ctx.hist[-1], 15)
            hx, lx = (hb.high.values, hb.low.values) if sd.sign > 0 else (-hb.low.values, -hb.high.values)
            if len(hx) >= 5:
                _, pls = L.pivots(hx, lx, 2)
                lv = L.equal_levels([q.price for q in pls], _tol(p)) if len(pls) >= 2 else []
                out = [float(v) for v in lv if float(sd.l[ctx.start:i + 1].min()) > v]
    c[key] = out
    if out:
        hit("prev_reh_pools")
    return out


def pools5(ctx, sd, i: int, p, session: str, out: dict) -> None:
    """Sell-side pools of this chunk (strategy._sell_side): the prior day's 15m relative equal highs as AM pools (`prev_reh_plan`), from 09:30."""
    if p.prev_reh_plan and session == "AM" and ctx.t[i] >= 570:
        for k, v in enumerate(prev_reh_levels(ctx, sd, i, p)):
            out[f"prev_reh{k}"] = v


def created(ctx, key: str):
    """The bar from which a pool of this chunk exists, else None."""
    if key.startswith("prev_reh"):
        return _S()._idx_at(ctx, 570)
    return None


def reh_target(ctx, sd, sw, i: int, p, entry: float, tags: dict) -> None:
    """The short target of `prev_reh_plan`: the swing low (real; side space the last pivot HIGH) that formed just before the REH sweep."""
    S = _S()
    if not str(sw.get("key", "")).startswith("prev_reh"):
        return
    hs = [q for q in sd.ph if q.i < sw["ext_i"] and q.known <= i and q.i >= ctx.start - 1]
    if hs and hs[-1].price > entry + MIN1:
        tags["fixed4"] = [(float(S._exit_px(hs[-1].price, "pool", p)), "pool")]
        hit("prev_reh_target")


# --- 102 M2-skip-filter ------------------------------------------------------------------------------------------------------------------------------

def stop_zone_gate(ctx, sd, sw, i: int, p, session: str, entry: float, stop: float):
    """M2-skip-filter (100 ~01:07:20): drop the order when an unraided same-side pool lies between the entry and the stop (side space: a sell-side level under the entry above the stop). Two
    cases (review fix - the first one is the real "unraided" case): (a) a pool in the stop zone BEYOND the sweep extreme (stop < v < ext) that no bar has traded since it formed - the stop would
    sit past a pool the market has not yet run; (b) a level between the extreme and the entry that the sweep's first bar did not take, probed by >= 2 wicks BEFORE the sweep (the sweep bar's
    own wick does not count) with no body close beyond it - a squeeze can run it first. The swept pool itself is excluded. Returns a reject key or None."""
    S = _S()
    tol = _tol(p)
    ext = float(sw["ext"])
    sw_i = int(sw.get("sweep_i", sw["ext_i"]))
    lv = S._sell_side(ctx, sd, session, i, True, p)
    cands = [(v, ctx.start) for v in lv.values()]
    cands += [(float(q.price), int(q.i)) for q in sd.pl if q.known <= i and ctx.start <= q.i < sw_i]
    for v, a in cands:
        v = float(v)
        if not (stop + MIN1 < v < entry - MIN1) or abs(v - float(sw["level"])) <= tol:
            continue
        if v < ext - tol:                                                       # (a) beyond the sweep extreme: raided only if a bar since then went through it
            seg_l = sd.l[a + 1:i + 1]
            if not len(seg_l) or float(seg_l.min()) > v:
                hit("stop_zone_pool")
                return "x_stop_zone_pool"
            continue
        if v <= ext + tol or v >= float(sd.l[sw_i]) - MIN1:                    # (b) inside the sweep's own range: the sweep bar took it
            continue
        pre_l, pre_c = sd.l[a + 1:sw_i], sd.c[a + 1:sw_i]
        if len(pre_c) and float(pre_c.min()) < v - MIN1:
            continue
        if int((pre_l <= v + tol).sum()) >= 2:
            hit("stop_zone_pool")
            return "x_stop_zone_pool"
    return None


# --- 95 M2-three-drives-breaker-fallback -------------------------------------------------------------------------------------------------------------

def td_note(ctx, sd, sw, i: int, p, tags: dict) -> None:
    """M2-three-drives-breaker-fallback (093 ~00:11:14): on a three-drives order (same level when `td_same_level`) with `td_fallback`, remember the sweep so the breaker fallback can arm when the
    FVG order expires unfilled (td_fallback_order)."""
    if sw.get("ref_i") is None:
        return
    sd.__dict__["_td_fb"] = dict(sw=dict(sw), ref_i=int(sw["ref_i"]), armed=int(i), day=ctx.day, done=False)
    hit("td_note")


def td_fallback_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The fallback: the FVG order of a three-drives top expired unfilled (`pending_minutes` since it was armed, no position - the engine only scans while flat) - the breaker of the three-drives top
    (`_breaker` on the remembered sweep), where it overlaps an IFVG (`sd.ifvgs`), arms a breaker order (`_breaker_order`). Once."""
    S = _S()
    st = sd.__dict__.get("_td_fb")
    if st is None or st["done"] or st["day"] != ctx.day or sd.sweep is not None:
        return None
    if i - st["armed"] <= max(1, p.pending_minutes // ctx.tf):
        return None
    st["done"] = True
    sw = st["sw"]
    bz = S._breaker(ctx, sd, sw, st["ref_i"], True, i, p)
    if bz is None or bz.top >= sd.c[i]:
        return None
    if not any(z.bottom < bz.top and z.top > bz.bottom and z.i <= i for z in sd.ifvgs()):
        return None
    hit("td_fallback")
    sw["bz_sent"] = False
    return S._breaker_order(ctx, sd, sw, bz, i, p, session, risk_mult)


# --- 103 A14-unicorn-standalone -----------------------------------------------------------------------------------------------------------------------

def unicorn_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """A14-unicorn-standalone (101 ~01:24:37; "this setup alone is a model in and of itself"), side space, on `unicorn_tf`-minute bars (the day's completed buckets, base bars when equal): price
    retraces into a same-side array (a Confluence 15m / 1h / 4h / daily array, or the upper quadrant of an NWOG - the mirrored lower quadrant for shorts) forming a swing low S; a later bar
    closes above the swing high H before S (the MSS), leaving a bullish breaker (the breaker_zone of that leg) and an FVG that overlaps it: a limit at the overlap's top, the stop under the lower
    of the two, the single target = the nearest swing high above the entry, full exit there and the idea is done (`done` UNI). No pool sweep and no 09:30 requirement (owner #5 / #11: needs
    ob_entry "post_mss" or "both" for the engine's own unicorn to coexist: the setup trades only then, unless `unicorn_independent` (owner choice) lets it run under the pre-break default).
    A body close under the breaker / FVG bottom before the fill cancels the order (cancel_close)."""
    S = _S()
    if ctx.done_ref.get("UNI") or _want(ctx) not in (0, sd.sign):
        return None
    if p.ob_entry == "pre_break" and not p.unicorn_independent:
        return None
    m = int(p.unicorn_tf)
    if m == ctx.tf:
        n = i + 1
        first = last = np.arange(n)
        o, hh, ll, cc = sd.o[:n], sd.h[:n], sd.l[:n], sd.c[:n]
    elif m > ctx.tf and m % ctx.tf == 0:
        first, last, done, o_, h_, l_, c_ = sm4.buckets(ctx, sd, m)
        ok = np.flatnonzero(done & (last <= i))
        if len(ok) < 8:
            return None
        n = int(ok[-1]) + 1
        o, hh, ll, cc = o_[:n], h_[:n], l_[:n], c_[:n]
    else:
        return None
    if n < 8:
        return None
    ph, pl = L.pivots(hh, ll, 1)
    sent = sd.__dict__.setdefault("_uni_sent", set())
    arrs = [(a, b) for a, b, _ in sm4.conf_arrays(ctx, sd, i, ("15m", "1h", "4h", "D"), (0, 1, 3), known_at_start=False)]
    for hi, lo, ce in sm2.gap_list(ctx, i, ("nwog", "nwog_rth")):
        t_, b_ = max(float(sd.x(hi)), float(sd.x(lo))), min(float(sd.x(hi)), float(sd.x(lo)))
        arrs.append((t_, b_ + 0.75 * (t_ - b_)))
    tol = _tol(p)
    for Sv in reversed([q for q in pl if q.known <= n - 1]):
        if int(first[Sv.i]) in sent or Sv.i < 3:
            continue
        if not any(b - tol <= Sv.price <= a + tol for a, b in arrs):
            continue
        Hs = [q for q in ph if q.i < Sv.i and q.known <= Sv.i]
        if not Hs:
            continue
        H = Hs[-1]
        brk = np.flatnonzero(cc[Sv.i + 1:n] > H.price)
        if not len(brk):
            continue
        kb = Sv.i + 1 + int(brk[0])
        L1s = [q for q in pl if q.i < H.i and q.known <= H.i + 1]
        a0 = L1s[-1].i if L1s else max(0, H.i - 3)
        bz = L.breaker_zone(o, hh, ll, cc, a0, Sv.i, kb, "bull", p.breaker_zone, p.breaker_mt_mode, p.breaker_candle, p.breaker_body_swing)
        if bz is None:
            continue
        gs = [g for g in L.fvgs(hh, ll, o, cc, sd.c2_dir) if g.kind == "bull" and g.src >= Sv.i and g.bottom < bz.top and g.top > bz.bottom]
        gs = [g for g in gs if float(cc[g.i + 1:n].min(initial=np.inf)) >= g.bottom - MIN1]
        if not gs:
            continue
        g = gs[-1]
        entry, bottom = float(min(g.top, bz.top)), float(min(g.bottom, bz.bottom))
        if entry >= float(sd.c[i]) - MIN1:
            continue
        tg = [q.price for q in ph if q.known <= n - 1 and q.price > entry + MIN1]
        if not tg:
            continue
        sent.add(int(first[Sv.i]))
        hit("unicorn_standalone")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "unicorn_standalone", entry, bottom - p.pad, level=entry, ext=float(Sv.price), ext_i=int(first[Sv.i]), fvg_bottom=bottom,
                          fvg_ce=float((g.top + g.bottom) / 2), fixed=[(float(S._exit_px(min(tg), "pool", p)), "pool")], single_exit=True, no_adds=True, done_key="UNI", cancel_close=bottom, lv=("unicorn_standalone",))
    return None


# --- 105 M10-ifvg-open-dependent ----------------------------------------------------------------------------------------------------------------------

def ifvg_open_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M10-ifvg-open-dependent (102 ~02:21:33), side space (a short = the mirrored long under a daily IFVG): at the 09:30 bar (the Sunday open vs the Friday close on a Monday when the data has
    it) compare the open with the previous close - when the session opens AWAY from the daily IFVG by more than `ifvg_gap_pts` ES points (a gap lower for the short) a resting limit at the IFVG is
    allowed: at its near edge, the stop per M10 (CE minus `ifvg_stop_pts` (3.5 default) beyond; the far edge when the IFVG had no prior pass and `ifvg_depth` is on); otherwise (an unchanged
    open) nothing is pre-placed - only the LTF MSS + FVG path after price trades into the IFVG [the engine's own path]. Once a day, 09:30 bar."""
    S = _S()
    if session != "AM" or int(ctx.t[i]) != 570 or _want(ctx) != sd.sign:
        return None
    pr = _prev_range_real(ctx)
    if pr is None:
        return None
    sent = sd.__dict__.setdefault("_ifo_sent", set())
    if ctx.day in sent:
        return None
    ref_open = float(ctx.o[i])
    prev_close = float(pr[2])
    if ctx.day.weekday() == 0:
        so = S._open_known(ctx, "sunday", i)
        if so is not None:
            ref_open = float(so)                                 # [our interpretation] a Monday compares the Sunday 18:00 open with the Friday close
    gap = float(sd.x(ref_open) - sd.x(prev_close))
    if gap <= p.ifvg_gap_pts * p.es_pt + MIN1:
        hit("ifvg_open_unchanged")
        return None
    dsd = daily_side(ctx, sd, p)
    if dsd is None:
        return None
    n = len(dsd.c) - 1
    zs = [z for z in dsd.ifvgs() if z.i <= n and float(dsd.c[z.i + 1:n + 1].min(initial=np.inf)) >= z.bottom - MIN1 and z.top < sd.c[i]]
    if not zs:
        return None
    z = max(zs, key=lambda z: z.top)
    entry = float(z.top)
    ce = float((z.top + z.bottom) / 2)
    far = False
    if p.ifvg_depth:
        far = L.ifvg_passes(dsd.h, dsd.l, z.top, z.bottom, z.src + 1, z.i) == "none"           # the gap had only the one pass (the inversion): the far edge is the stop
    stop = (float(z.bottom) if far else ce - (p.ifvg_stop_pts or 3.5) * p.es_pt) - p.pad
    stop = _min_stop(p, entry, stop)
    sent.add(ctx.day)
    hit("ifvg_open_limit")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "ifvg_open", entry, stop, level=entry, ext=float(z.bottom), ext_i=i, fvg_bottom=float(z.bottom), fvg_ce=ce, no_expire=True, lv=("ifvg_open",))


# --- 106 M0-htf-array-not-reached ---------------------------------------------------------------------------------------------------------------------

def array_fb_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M0-htf-array-not-reached (103 ~00:29:15), side space: with the session lock on this side and the planned 1h / 4h array (a same-side array under the price) NOT reached today - price
    stalls above it - a 15m bullish breaker lying above that array and under the locked draw, formed and alive, arms a breaker order: a limit at its top (adds inside the breaker candle are
    the normal adds), the stop under its bottom. Once per breaker. [our interpretation: an FVG as the alternative entry is the engine's own path.]"""
    S = _S()
    lk = getattr(ctx, "cur_lock", None)
    if lk is None or lk.get("side") != sd.sign or lk.get("delivered"):
        return None
    px = float(sd.c[i])
    day_low = float(sd.l[ctx.start:i + 1].min())
    planned = [a for a, b, _ in sm4.conf_arrays(ctx, sd, i, ("1h", "4h"), (0, 1, 3)) if a < px and day_low > a]
    if not planned:
        return None
    top_pl = max(planned)
    tv = float(sd.x(lk["target"]))
    first, last, done, o, hh, ll, cc = sm4.buckets(ctx, sd, 15)
    ok = np.flatnonzero(done & (last <= i))
    if len(ok) < 6:
        return None
    n = int(ok[-1]) + 1
    sent = sd.__dict__.setdefault("_afb_sent", set())
    for z in sorted([z for z in L.breakers(o[:n], hh[:n], ll[:n], cc[:n], 2) if z.kind == "bull"], key=lambda z: -z.i):
        kz = int(last[z.i])
        if kz > i or z.i in sent or not (z.bottom > top_pl and z.top < tv) or float(sd.c[kz + 1:i + 1].min(initial=np.inf)) < z.bottom - MIN1:
            continue
        entry = float(z.top)
        if entry >= px - MIN1:
            continue
        sent.add(z.i)
        hit("array_fallback_breaker")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "array_fb_breaker", entry, float(z.bottom) - p.pad, level=entry, ext=float(z.bottom), ext_i=int(first[z.src]), fvg_bottom=float(z.bottom),
                          fvg_ce=float(z.mt) if z.mt == z.mt else float((z.top + z.bottom) / 2), lv=("array_fb_breaker",))
    return None


# --- the MM model (107 / 108 / 109 / 110) -------------------------------------------------------------------------------------------------------------

def need_note(p) -> bool:
    return bool(p.mm_oc_entry or p.mm_stages or p.mm_lowrisk or p.mm_accum_bars or p.reclaimed_ladder or p.td_fallback)


def note_sweep(sd, sw) -> None:
    """Remember the day's latest sweep (the dict the machine keeps updating) for the MM model / reclaimed-ladder setups, which outlive the sweep that was consumed by their first order."""
    sd.__dict__["_mm5"] = sw


def _mm(sd, ctx, session: str):
    m = sd.__dict__.get("_mm5")
    if m is None or m.get("session") != session or m.get("broke") is None or m["ext_i"] < ctx.start - 1:
        return None
    return m


def orig_consolidation(sd, m, i: int, p):
    """M1-original-consolidation-entry (104 ~00:32:10): the original consolidation of the MM model = the area of the parent swing high before the sell-side leg: (U, low, mid) in side space -
    the smooth-edge upper bound U of `levels.smooth_edge_range` (else the parent swing high itself) and the lowest low of the bars that touched it (the consolidation proper, not the leg that
    left it); mid = their midpoint. None without a parent swing."""
    S = _S()
    q = S._SM.parent_high(sd, m["ext_i"], i)
    if q is None:
        return None
    a, b = max(0, q.i - 30), min(q.i + 30, m["ext_i"], i)
    tol = p.orig_consol_tol_pts * p.es_pt
    r = L.smooth_edge_range(sd.o, sd.h, sd.l, sd.c, tol, p.orig_consol_touches, a, b)
    if r is not None:
        U = float(r[0])
        tops = np.maximum(sd.o[a:b + 1], sd.c[a:b + 1])
        touch = np.flatnonzero((np.abs(tops - U) <= tol) | (np.abs(sd.h[a:b + 1] - U) <= tol))
        lo_i, hi_i = a + int(touch.min()), a + int(touch.max())
        low = float(sd.l[lo_i:hi_i + 1].min())
    else:
        U = float(q.price)
        low = float(sd.l[max(0, q.i - 3):q.i + 4].min())
    if not U > low:
        return None
    return U, low, (U + low) / 2


def accum_ok(ctx, sd, m, i: int, p) -> bool:
    """The accumulation test of M1-consolidate-at-discount-array as a GATE (`mm_accum_gate`): some discount array of the move after the MSS (an FVG whose top is at or under the leg's EQ, no body
    close under it) holds the last `mm_accum_bars` closed bars' closes inside it with a total range under `mm_accum_frac` x its height. Without `mm_accum_bars` the gate is open."""
    n = int(p.mm_accum_bars)
    if n <= 0:
        return True
    hit("mm_accum_gate_eval")
    e = int(m["ext_i"])
    if i - e < n + 2:
        return False
    eq = sm4.m2_eq(sd, m, i)
    seg = slice(i - n + 1, i + 1)
    for g in [g for g in sd.gaps if g.i - 2 > e and g.i <= i and g.top <= eq + MIN1]:
        if float(sd.c[g.i + 1:i + 1].min(initial=np.inf)) < g.bottom - MIN1 or i - n + 1 <= g.i:
            continue
        cl = sd.c[seg]
        if ((cl >= g.bottom - MIN1) & (cl <= g.top + MIN1)).all() and float(sd.h[seg].max() - sd.l[seg].min()) < p.mm_accum_frac * float(g.top - g.bottom) - MIN1:
            hit("mm_accum_gate_open")
            return True
    return False


def mm_oc_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M1-original-consolidation-entry (104 ~00:32:10): once a body closed above the original consolidation's high (wicks do not count) after the sweep, a limit at that high - the first return only;
    the stop under the consolidation's midpoint [our interpretation]. If price never returns, the next stage entries (`mm_stages`) are the entries."""
    m = _mm(sd, ctx, session)
    if m is None or (p.mm_accum_gate and not accum_ok(ctx, sd, m, i, p)):
        return None
    oc = orig_consolidation(sd, m, i, p)
    if oc is None:
        return None
    U, low, mid = oc
    e = int(m["ext_i"])
    ks = np.flatnonzero(sd.c[e + 1:i + 1] > U)
    if not len(ks):
        return None
    kb = e + 1 + int(ks[0])
    sent = sd.__dict__.setdefault("_mmoc_sent", set())
    if (e, kb) in sent or float(sd.l[kb + 1:i + 1].min(initial=np.inf)) <= U + MIN1 or U >= sd.c[i] - MIN1:
        return None
    stop = _min_stop(p, U, mid - p.pad)
    sent.add((e, kb))
    hit("mm_oc_entry")
    return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_oc_entry", U, stop, level=U, ext=float(m["ext"]), ext_i=e, fvg_bottom=low, no_expire=True, cancel_close=low, sm5=dict(kind="mm"), lv=("mm_oc_entry",))


def mm_accum_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M1-consolidate-at-discount-array (104 ~00:23:42): after the shift and the retrace into a discount array (an FVG of the move after the MSS whose top is at or under the leg's EQ), the
    thesis stays only if price goes sideways inside it: `mm_accum_bars` consecutive closed bars with their closes inside the array and a total range under `mm_accum_frac` x the array's height arm a
    limit at the array's CE (never above the close); a body close below the array's low cancels (cancel_close) / invalidates. Once per array."""
    m = _mm(sd, ctx, session)
    if m is None:
        return None
    e = int(m["ext_i"])
    n = int(p.mm_accum_bars)
    if i - e < n + 2:
        return None
    eq = sm4.m2_eq(sd, m, i)
    sent = sd.__dict__.setdefault("_mmacc_sent", set())
    for g in reversed([g for g in sd.gaps if g.i - 2 > e and g.i <= i and g.top <= eq + MIN1]):
        if g.i in sent or float(sd.c[g.i + 1:i + 1].min(initial=np.inf)) < g.bottom - MIN1:
            continue
        seg = slice(i - n + 1, i + 1)
        if i - n + 1 <= g.i:
            continue
        cl = sd.c[seg]
        if not ((cl >= g.bottom - MIN1) & (cl <= g.top + MIN1)).all():
            continue
        if float(sd.h[seg].max() - sd.l[seg].min()) >= p.mm_accum_frac * float(g.top - g.bottom) - MIN1:
            continue
        entry = float(min((g.top + g.bottom) / 2, sd.c[i] - p.tick))
        sent.add(g.i)
        hit("mm_accum")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_accum", entry, float(g.bottom) - p.pad, level=float(g.top), ext=float(m["ext"]), ext_i=e, fvg_bottom=float(g.bottom),
                          cancel_close=float(g.bottom), no_expire=True, sm5=dict(kind="mm"), lv=("mm_accum",))
    return None


def mm_stage_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M1-accumulation-stages (104 ~00:36:46), flat: the first stage entry of the MM model = the bullish breaker's order (1st-stage accumulation: `_breaker_order` on the sweep's breaker), else
    the CE of the newest alive FVG formed since the MSS (the BISI retraced only to its CE: the next stage). Valid while the HTF target above is not delivered. One per object."""
    S = _S()
    m = _mm(sd, ctx, session)
    if m is None or S._SM.htf_done(ctx, sd, i) or m.get("ref_i") is None or (p.mm_accum_gate and not accum_ok(ctx, sd, m, i, p)):
        return None
    if not m.get("bz_sent"):
        bz = S._breaker(ctx, sd, m, int(m["ref_i"]), True, i, p)
        if bz is not None and bz.top < sd.c[i] - MIN1:
            hit("mm_stage_breaker")
            return S._breaker_order(ctx, sd, m, bz, i, p, session, risk_mult)
    if p.mm_stage2:                                             # stage 2 (redistribution) - the OB retrace; a missed one is never chased
        o = stage2_order(ctx, sd, m, i, p, session, risk_mult)
        if o is not None:
            return o
    sent = sd.__dict__.setdefault("_mmst_sent", set())
    for g in reversed([g for g in sd.gaps if g.i - 2 > m["broke"] and g.i <= i and g.i not in sent]):
        if float(sd.c[g.i + 1:i + 1].min(initial=np.inf)) < g.bottom - MIN1 or g.mid >= sd.c[i] - MIN1:
            continue
        sent.add(g.i)
        hit("mm_stage_bisi")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_stage_bisi", float(g.mid), float(g.bottom) - p.pad, level=float(g.top), ext=float(m["ext"]), ext_i=int(m["ext_i"]),
                          fvg_bottom=float(g.bottom), fvg_ce=float(g.mid), sm5=dict(kind="mm"), lv=("mm_stage_bisi",))
    return None


def stage2_order(ctx, sd, m, i: int, p, session: str, risk_mult: float):
    """M1-distribution-stages-lowrisk-short (104 ~00:49:45), `mm_stage2`, side space: the stage-2 (re)distribution / reaccumulation entry = a retrace into an order block of the move after the MSS
    (a down-close candle the next bar closed above: a limit at its mean threshold, the body midpoint) or into the BODY of a reclaimed block on the other side of the curve (a limit at the body's
    near edge, the reclaimed_obs of the left leg); the stop under the block. "This leg is expected to be the fastest; if it is missed, do not chase": a block whose entry price has already been
    traded since it formed is never armed (price came back to it and left without us). Each block once. [our interpretation: the OB definition and the missed-leg test.]"""
    sent = sd.__dict__.setdefault("_mmst2_sent", set())
    cands = []
    for k in range(int(m["broke"]) + 1, i - 1):
        if sd.c[k] < sd.o[k] and sd.c[k + 1] > sd.h[k]:
            cands.append(("ob_mt", k, float((sd.o[k] + sd.c[k]) / 2), float(sd.l[k]), k + 1))
    for z in reclaim_blocks(ctx, sd, m, i, p):
        k = int(z.src)
        cands.append(("ob_body", k, float(max(sd.o[k], sd.c[k])), float(z.bottom), int(z.i)))
    for kind, k, entry, bottom, known in sorted(cands, key=lambda c: -c[4]):
        if (kind, k) in sent or known >= i:
            continue
        if float(sd.l[known + 1:i + 1].min(initial=np.inf)) <= entry + MIN1:
            continue                                            # traded already: the leg was missed (or it is the idea of a later stage) - do not chase
        if float(sd.c[known:i + 1].min(initial=np.inf)) < bottom - MIN1 or entry >= sd.c[i] - MIN1:
            continue
        sent.add((kind, k))
        hit("mm_stage2")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_stage2", entry, _min_stop(p, entry, bottom - p.pad), level=entry, ext=float(m["ext"]), ext_i=int(m["ext_i"]),
                          fvg_bottom=bottom, cancel_close=bottom, sm5=dict(kind="mm"), lv=("mm_stage2", kind))
    return None


def mm_stage_add(ctx, sd, pos, tr, i: int, p, st: dict) -> None:
    """M1-accumulation-stages, after the first MM fill: arm the add at the next stage - the (not yet used) bullish breaker's top, then the CE of each later FVG (reaccumulation) - with the E12
    sizes; none once the HTF target is delivered or the add is not above the stop."""
    S = _S()
    if pos["add"] is not None or S._nadds(pos, tr) >= len(p.adds) or S._SM.htf_done(ctx, sd, i):
        return
    m = st.get("sw")
    if m is None or m.get("broke") is None:                     # (an mm_lowrisk fill may carry a remembered sweep that has not broken yet: no stage ladder then)
        return
    if not st.get("bz") and m.get("ref_i") is not None:
        bz = S._breaker(ctx, sd, m, int(m["ref_i"]), True, i, p)
        if bz is not None and pos["stop"] < bz.top < sd.c[i] - MIN1:
            st["bz"] = True
            S._arm_add(pos, tr, float(bz.top), i, p, ctx.equity, floor=float(bz.bottom))
            hit("mm_stage_add_breaker")
            return
    used = st.setdefault("gaps", set())
    for g in reversed([g for g in sd.gaps if g.i - 2 > pos["fill_i"] and g.i <= i and g.i not in used]):
        if float(sd.c[g.i + 1:i + 1].min(initial=np.inf)) < g.bottom - MIN1 or not pos["stop"] < g.mid < sd.c[i] - MIN1:
            continue
        used.add(g.i)
        S._arm_add(pos, tr, float(g.mid), i, p, ctx.equity, floor=float(g.bottom), g=g)
        hit("mm_stage_add_bisi")
        return


def mm_lowrisk_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """M1-distribution-stages-lowrisk-short (104 ~00:45:30), side space: a 60m FVG (the 60m SIBI of the real short) whose bottom was wicked UNDER while the bodies stayed inside it (closes at or
    above its bottom), then an LTF MSS (a close above the swing high before the wick); a limit at the FVG's CE, the stop under the wick extreme; `mm_oc_frac` of the position comes off at the
    original consolidation (fracs; the rest to the next HTF level). One per FVG. The wick pattern does not need a remembered same-side sweep (review fix: only the original-consolidation
    partial reads the sweep, and is skipped without one). `mm_lowrisk_reentry` ("extreme" / "wick_ce"): after the first order's stop was run (a later bar traded under it) and price is back
    above the FVG's near edge, ONE re-entry limit at that edge ("a later touch of the FVG low"), the stop under the new extreme ("extreme": the highest high of the real short) or under the
    wick candle's CE ("wick_ce": the midpoint of the extreme bar's low and its body low) [our interpretation of "the highest high or the CE of the higher wick"]."""
    S = _S()
    m = _mm(sd, ctx, session)
    sent = sd.__dict__.setdefault("_mmlr_sent", set())
    first = sd.__dict__.setdefault("_mmlr_first", {})
    if p.mm_lowrisk_reentry:
        o = lowrisk_reentry(ctx, sd, i, p, session, risk_mult, first)
        if o is not None:
            return o
    for z in sorted(sm4._tf_fvgs(ctx, sd, 60), key=lambda z: -z.i):
        if z.i >= i or z.i in sent or z.mid >= sd.c[i] - MIN1:
            continue
        seg_l, seg_o, seg_c = sd.l[z.i + 1:i + 1], sd.o[z.i + 1:i + 1], sd.c[z.i + 1:i + 1]
        wk = np.flatnonzero(seg_l < z.bottom - MIN1)
        if not len(wk) or float(np.minimum(seg_o, seg_c).min()) < z.bottom - MIN1:
            continue                                            # no wick under it, or a body went under (not "bodies inside")
        k = z.i + 1 + int(wk[0])
        low = float(sd.l[k:i + 1].min())
        hs = [q for q in sd.ph if q.i < k and q.known <= k]
        if not hs or not (sd.c[k:i + 1] > hs[-1].price).any():
            continue                                            # the LTF MSS has not happened
        oc = orig_consolidation(sd, m, i, p) if m is not None else None
        fx, tags = None, {}
        if oc is not None and oc[0] > z.mid:
            fx = [(float(S._exit_px(oc[0], "pool", p)), "pool")]
            nxt = sm3.htf_level_beyond(ctx, sd, i, p, float(z.mid), session, oc[0])
            if nxt is not None:
                fx.append((float(S._exit_px(nxt, "array", p)), "array"))
                tags["fracs"] = (float(p.mm_oc_frac), 1.0 - float(p.mm_oc_frac))
        sent.add(z.i)
        stop1 = low - p.pad
        first[z.i] = dict(k=int(k), stop=float(stop1), top=float(z.top), bottom=float(z.bottom), placed=int(i), done=False)
        hit("mm_lowrisk")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_lowrisk", float(z.mid), stop1, level=float(z.top), ext=low, ext_i=int(k), fvg_bottom=float(z.bottom), fvg_ce=float(z.mid),
                          fixed=fx, sm5=dict(kind="mm", lowrisk=True), lv=("mm_lowrisk",), **tags)
    return None


def lowrisk_reentry(ctx, sd, i: int, p, session: str, risk_mult: float, first: dict):
    """The re-entry of `mm_lowrisk_reentry` (see mm_lowrisk_order): once per first order."""
    for zi, f in first.items():
        if f["done"] or i <= f["placed"] + 1:
            continue
        k = int(f["k"])
        run = np.flatnonzero(sd.l[f["placed"] + 1:i + 1] < f["stop"] - MIN1)
        if not len(run):
            continue                                            # the first order's stop was not run: no re-entry
        entry = float(f["top"])
        if entry >= sd.c[i] - MIN1 or sd.c[i] <= f["stop"]:
            continue
        seg = slice(k, i + 1)
        j = k + int(np.argmin(sd.l[seg]))
        low = float(sd.l[j])
        if p.mm_lowrisk_reentry == "wick_ce":
            stop = (low + float(min(sd.o[j], sd.c[j]))) / 2 - p.pad
        else:
            stop = low - p.pad
        stop = _min_stop(p, entry, stop)
        f["done"] = True
        hit("mm_lowrisk_reentry")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "mm_lowrisk_re", entry, stop, level=entry, ext=low, ext_i=int(j), fvg_bottom=float(f["bottom"]), fvg_ce=entry,
                          sm5=dict(kind="mm", lowrisk=True), lv=("mm_lowrisk_re",))
    return None


# --- 111 A18-curve-arrays-reverse-ladder -------------------------------------------------------------------------------------------------------------

def reclaim_blocks(ctx, sd, m, i: int, p) -> list:
    """A18-curve-arrays-reverse-ladder (104 ~00:52:18; cc04_007 ~00:04:46): the reclaimed blocks of the curve's left leg (the down-close candles of the sell-side leg, each followed by a bounce of
    >= `reclaim_bounce_bars` up-close bars, reclaimed by a close above their high after the low) ordered from the lowest up: the ladder of adds. Sell curve = the side-space mirror."""
    e = int(m["ext_i"])
    lo = max(ctx.start, e - 60)
    a = lo + int(np.argmax(sd.h[lo:e])) if e > lo else max(0, e - 30)      # the left leg starts at the highest high before the low (the curve's divider is the low) [our interpretation]
    nb = int(p.reclaim_bounce_bars)
    out = []
    for z in L.reclaimed_obs(sd.o, sd.h, sd.l, sd.c, a, e, i):
        k = int(z.src)
        if all(k + j <= e and sd.c[k + j] > sd.o[k + j] for j in range(1, nb + 1)):
            out.append(z)
    return sorted(out, key=lambda z: z.top)


def reclaim_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The flat entry of the ladder: the lowest unused reclaimed block price has passed (a close above its top) and is now back above, no close under its bottom since it formed: a limit at its
    top (near edge), the stop under its bottom. Each block once."""
    m = _mm(sd, ctx, session)
    if m is None:
        return None
    sent = sd.__dict__.setdefault("_rcl_sent", set())
    dead = sd.__dict__.setdefault("_rcl_dead", set())
    if int(m["ext_i"]) in dead:
        return None                                             # the ladder was killed (persistent: review fix)
    for z in reclaim_blocks(ctx, sd, m, i, p):
        if (m["ext_i"], z.src) in sent:
            continue
        if float(sd.c[z.i + 1:i + 1].min(initial=np.inf)) < z.bottom - MIN1:
            sent.add((m["ext_i"], z.src))
            dead.add(int(m["ext_i"]))
            break                                               # a body close back through a block cancels the rest of the ladder
        if z.top >= sd.c[i] - MIN1:
            continue
        sent.add((m["ext_i"], z.src))
        hit("reclaim_ladder")
        return sm4._order(ctx, sd, i, p, session, risk_mult, "reclaim_ladder", float(z.top), float(z.bottom) - p.pad, level=float(z.top), ext=float(m["ext"]), ext_i=int(m["ext_i"]),
                          fvg_bottom=float(z.bottom), no_expire=True, cancel_close=float(z.bottom), sm5=dict(kind="reclaim"), lv=("reclaim_ladder",))
    return None


def reclaim_add(ctx, sd, pos, tr, i: int, p, st: dict) -> None:
    """The ladder after the first fill: each recorded block in turn (lowest first) is the next pyramid add - a limit at its top once price has passed it (a close above) - each once; a body close
    back through a block kills the rest."""
    S = _S()
    m = st.get("sw")
    if m is None or st.get("dead") or pos["add"] is not None or S._nadds(pos, tr) >= len(p.adds):
        return
    used = st.setdefault("used", set())
    for z in reclaim_blocks(ctx, sd, m, i, p):
        if z.src in used:
            continue
        if float(sd.c[z.i + 1:i + 1].min(initial=np.inf)) < z.bottom - MIN1:
            st["dead"] = True
            return
        if z.top < sd.c[i] - MIN1 and z.top > pos["stop"]:
            used.add(z.src)
            S._arm_add(pos, tr, float(z.top), i, p, ctx.equity, floor=float(z.bottom))
            hit("reclaim_add")
            return


# --- the dispatchers (strategy._scan / run_day / _finish_order hooks) --------------------------------------------------------------------------------------

def any_gate5(p) -> bool:
    return bool(p.false_flag != "off" or p.news_two_sided or p.all_pools_first != "off" or p.near_miss_pts > 0 or p.pd50_bodies or p.open_ob_min > 0 or p.htf_entry_array != "off"
                or p.stop_zone_pool or p.ifvg_need_hunt or p.td_fallback or p.prev_reh_plan or p.mm_oc_entry or p.mm_stages or p.reclaimed_ladder or p.mm_lowrisk)


def order_gate5(ctx, sd, sw, i: int, p, entry: float, stop: float, session: str, lvt: list, lvx: dict, tags: dict):
    """Gates / tags of setups_models #5/7 at order completion (strategy._finish_order, after order_gate4). Returns a reject key or None."""
    S = _S()
    synth = bool(sw.get(S._SM.SYNTH))
    if p.news_two_sided and not synth:
        r = news_two_sided_gate(ctx, sd, sw, i, p, session, lvt, lvx)
        if r:
            return r
    if p.false_flag != "off" and not synth:
        r = false_flag_gate(ctx, sd, sw, i, p, lvt, tags)
        if r:
            return r
    if p.all_pools_first != "off" and not synth:
        r = all_pools_gate(ctx, sd, sw, i, p, session, lvt)
        if r:
            return r
    if p.near_miss_pts > 0 and not synth:
        near_miss_tag(ctx, sd, sw, i, p, lvt)
    if p.pd50_bodies and not synth:
        r = pd50_gate(ctx, sd, sw, i, p, tags)
        if r:
            return r
    if p.ifvg_need_hunt and tags.get("entry_kind") == "ifvg" and not ifvg_hunt_ok(ctx, sd, i, p, tags):
        return "x_ifvg_hunt"
    if p.htf_entry_array != "off":
        r = htf_entry_gate(ctx, sd, i, p, entry, lvt)
        if r:
            return r
    if p.stop_zone_pool and not synth:
        r = stop_zone_gate(ctx, sd, sw, i, p, session, entry, stop)
        if r:
            return r
    if p.open_ob_min > 0 and not synth:
        open_ob_note(ctx, sd, sw, i, p, session, tags)
    if p.td_fallback and not synth and L.three_drives(sd.pl, sw["ext"], sw["ext_i"], i, max(0, ctx.start - 1), sw["level"] if p.td_same_level else None, p.td_level_pts * p.es_pt):
        td_note(ctx, sd, sw, i, p, tags)
    if p.prev_reh_plan and not synth:
        reh_target(ctx, sd, sw, i, p, entry, tags)
    if (p.mm_stages or p.reclaimed_ladder) and not synth and sd.__dict__.get("_mm5") is sw:
        st = tags.setdefault("sm5", {})
        st.setdefault("kind", "mm" if p.mm_stages else "reclaim")
    return None


def any_extra5(p) -> bool:
    return bool(p.po3_15m or p.rb_second_dip or p.htf_overshoot_short or p.td_fallback or p.mit_stair or p.unicorn_standalone or p.ifvg_open_mode or p.array_fallback_breaker or p.mm_oc_entry
                or p.mm_accum_bars > 0 or p.mm_stages or p.mm_lowrisk or p.reclaimed_ladder)


def extra5(ctx, sd, i: int, p, session: str, risk_mult: float):
    """The non-sweep setups of this chunk, tried when the sweep machine has nothing (strategy._scan; each decides itself whether a live sweep matters)."""
    flat = sd.sweep is None
    if p.po3_15m:
        o = po3_15m_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.unicorn_standalone:
        o = unicorn_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.ifvg_open_mode:
        o = ifvg_open_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.array_fallback_breaker:
        o = array_fb_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.htf_overshoot_short:
        o = overshoot_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.rb_second_dip:
        o = second_dip_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.mit_stair:
        o = mit_stair_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if flat and p.td_fallback:
        o = td_fallback_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.mm_oc_entry:
        o = mm_oc_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.mm_accum_bars > 0:
        o = mm_accum_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.mm_stages:
        o = mm_stage_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.mm_lowrisk:
        o = mm_lowrisk_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    if p.reclaimed_ladder:
        o = reclaim_order(ctx, sd, i, p, session, risk_mult)
        if o is not None:
            return o
    return None


def any_special5(p) -> bool:
    return bool(p.lunch_org_ce_short)


def special5(ctx, sides, i: int, p, state: dict, pos, pending, risk_mult: float, done: dict):
    """The setups that run outside the session windows (run_day, like special4): the lunch-hour ORG-CE short (12:00-13:30)."""
    if pos is not None or pending is not None or state.get("day_done"):
        return None
    S = _S()
    t = int(ctx.t[i])
    if not (720 <= t < 810) or done.get("LOCS") or "locs" in state.setdefault("sm5_sent", set()):
        return None
    saved = {k: ctx.__dict__[k] for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session") if k in ctx.__dict__}
    out = None
    try:
        ctx.cur_lock, ctx.cur_lock_any, ctx.cur_news, ctx.cur_sloppy, ctx.cur_no_draw, ctx.cur_bias = None, None, None, "", False, 0
        ctx.cur_session = "PM"
        if not (p.day_filter and S.blocked(ctx.day, "PM", p, t)):
            for sd in sides:
                ctx.cur_bias = sd.sign
                out = lunch_org_order(ctx, sd, i, p, risk_mult)
                if out is not None:
                    state["sm5_sent"].add("locs")
                    break
    finally:
        for k in ("cur_lock", "cur_lock_any", "cur_bias", "cur_news", "cur_sloppy", "cur_no_draw", "cur_session"):
            if k in saved:
                setattr(ctx, k, saved[k])
            else:
                ctx.__dict__.pop(k, None)
    return out


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p) -> None:
    """Fill-time work: the `open_into_ob` tag, the A-B anchor lock's filled flag, the MM / reclaimed-ladder sweep reference."""
    st = o.get("sm5")
    if not st:
        return
    pos["sm5"] = dict(st)
    if st.get("open_ob") is not None:
        d = int(ctx.t[i]) - int(st["open_ob"])
        if 0 <= d <= p.open_ob_min:
            tr.lv_tags = "|".join(x for x in (tr.lv_tags, "open_into_ob") if x)
            hit("open_into_ob")
    if st.get("kind") == "ab_anchor":
        ab = sd.__dict__.get("_ab5")
        if ab is not None:
            ab["filled"] = True
    if st.get("kind") in ("mm", "reclaim"):
        pos["sm5"]["sw"] = sd.__dict__.get("_mm5")


def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Per-bar management of the positions this package tagged (pos["sm5"]): the ifvg_061 IOFED exit below the CE, the stair-step adds, the MM stage adds, the reclaimed-block ladder adds."""
    st = pos.get("sm5")
    if not st or i <= pos["fill_i"] or not pos["left"]:
        return
    S = _S()
    k = st.get("kind")
    if k == "ifvg061":
        ce = st["ce"]
        if sd.l[i] < ce - MIN1 and not st.get("done"):
            st["done"] = True
            sm3._part(sd, pos, tr, ts, float(min(sd.o[i], ce)), 1.0, "ifvg_ce", p, all_=True)
            hit("ifvg061_ce_exit")
    elif k == "mit_stair" and pos["add"] is None and not S._SM.htf_done(ctx, sd, i) and S._nadds(pos, tr) < len(p.adds):
        used = st.setdefault("used", {st.get("j")})
        for b in stair_blocks(ctx, sd, i, p):
            if b["j"] in used or b["j"] <= st.get("j", -1) or float(sd.c[b["broke"] + 1:i + 1].min(initial=np.inf)) < b["bottom"] - MIN1:
                continue
            if b["top"] < sd.c[i] and b["top"] > pos["stop"]:
                used.add(b["j"])
                S._arm_add(pos, tr, float(b["top"]), i, p, ctx.equity, floor=float(b["bottom"]))
                hit("mit_stair_add")
                break
    elif k == "mm" and p.mm_stages:
        mm_stage_add(ctx, sd, pos, tr, i, p, st)
    elif k == "reclaim" and p.reclaimed_ladder:
        reclaim_add(ctx, sd, pos, tr, i, p, st)


def after_close(pos, tr, done: dict, state: dict, p) -> None:
    """M1-one-segment (104 ~00:09:27): `mm_flip` - after an MM trade reached its last ladder level the session may reverse into the MM leg of the other side (the opposite side only, the lock no
    longer gates it); off by default: the session is done for the side (the built behaviour)."""
    st = pos.get("sm5")
    if not (p.mm_flip and st and st.get("kind") == "mm" and tr.final_hit and done is not None):
        return
    key = pos.get("done_key", tr.session)
    if state.setdefault("mm_flipped", {}).get(tr.session):
        return
    state["mm_flipped"][tr.session] = True
    done[key] = False
    state.setdefault("only_side", {})[tr.session] = -1 if tr.side == "long" else 1
    state.setdefault("mm_flip", {})[tr.session] = True
    hit("mm_flip")
