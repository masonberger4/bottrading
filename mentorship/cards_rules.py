"""Scorecard cards (mentorship/cards.py): the engine concepts the cards needed that the engine did not have yet (Mase 2026-11-08: build every card default).

Each function sits behind its Params switch; interpretations the card does not pin down are marked [our interpretation]. `HITS` counts the code paths that ran (tests)."""
from __future__ import annotations

import numpy as np

HITS: dict[str, int] = {}


def hit(k: str) -> None:
    HITS[k] = HITS.get(k, 0) + 1


# --- ATH-RULE -------------------------------------------------------------------------------------------------
def ath_map(ds: list) -> dict:
    """{date: the highest high of every day frame before it} (the first day has none). The history is what the run loaded, so the first
    days of a run see a lower "all-time" high than the market's [our interpretation]."""
    out, top = {}, None
    for g in ds:
        d = g.index[0].date()
        if top is not None:
            out[d] = top
        h = float(g.high.max())
        top = h if top is None else max(top, h)
    return out


def ath_block(ctx, sd, o: dict, p) -> str | None:
    """ATH-RULE: a funnel key for a short armed near the all-time high, else None. "no_top_pick" (A, "don't pick the top: daily bias stays long; shorts
    only intraday") blocks the setups that pick a high (turtle soup, three drives, reversal: bh1e._is_top_pick); "longs_only" (C) blocks every short."""
    ath = getattr(ctx, "ath", None)
    if sd.sign > 0 or ath is None:
        return None
    hit("eval_ath")
    if sd.x(o["entry"]) < ath * (1.0 - p.ath_near_frac) - 1e-9:
        return None
    if p.ath_rule == "longs_only":
        hit("ath_no_short")
        return "x_ath_no_short"
    if _top_pick(o):
        hit("ath_top_pick")
        return "x_ath_top_pick"
    return None


def _top_pick(o: dict) -> bool:
    """bh1e._is_top_pick with whole tags (its substring test also matched lc_reversal / td_reversal, S1 review)."""
    from . import sm7 as _SM7
    from .bh1e import TOP_KINDS
    tags = set(str(o.get("lv_tags") or "").split("|"))
    return bool(_SM7.is_ts_kind(o) or {"three_drives", "reversal"} & tags or str(o.get("entry_kind") or "") in TOP_KINDS)


# --- FPFVG-DEF / FVG-CARRY / RANGE-REGIME: per-day context built once over the loaded day frames (backtest.Prepared.cards) ----------------
def fpfvg_of(g):
    """FPFVG-DEF A: the day's first FVG on the engine bars whose middle candle opens 09:31-09:59 ("can't be the gap if it forms on the 9:30 candle")
    -> dict(sign, top, bottom, ts = the completing bar), else None. On 5m bars the first middle candle is 09:35 [our interpretation]."""
    t = g.index.hour * 60 + g.index.minute
    h, l = g.high.values, g.low.values
    for k in range(2, len(g)):
        m = t[k - 1]
        if m < 571 or t[k - 2] < 570:
            continue
        if m >= 600:
            break
        if l[k] > h[k - 2]:
            return dict(sign=1, top=float(l[k]), bottom=float(h[k - 2]), ts=g.index[k])
        if h[k] < l[k - 2]:
            return dict(sign=-1, top=float(l[k - 2]), bottom=float(h[k]), ts=g.index[k])
    return None


def _rth(g):
    t = g.index.hour * 60 + g.index.minute
    return g[(t >= 570) & (t < 960)]


def card_map(ds: list, p) -> dict:
    """{date: dict(fpfvg=[active FPFVGs], rr=(range high, range low, PDH, PDL, range-bound))}. An FPFVG is active through the rest of its ISO week
    (FPFVG-DEF A, filled or not) and, while unfilled (a later RTH low through a bullish one's bottom / high through a bearish one's top), for fvg_carry_days trading
    days (FVG-CARRY A). Today's own FPFVG is listed with its ts (usable after that bar). The history is what the run loaded [our interpretation]."""
    out, live, hist = {}, [], []
    for g in ds:
        d = g.index[0].date()
        r = _rth(g)
        row = dict(fpfvg=[], rr=None)
        if p.fpfvg_def != "off":
            wk = d.isocalendar()[:2]
            live = [z for z in live if z["wk"] == wk or (not z["filled"] and z["age"] < p.fvg_carry_days)]     # (S2 review: the week's FPFVG stays all week, filled or not)
            row["fpfvg"] = [dict(z) for z in live]
            z = fpfvg_of(g)
            if z is not None:
                z.update(wk=wk, age=0, filled=False, day=d)
                row["fpfvg"].append(dict(z))
            for y in live:
                y["age"] += 1
                y["filled"] = bool(len(r)) and bool(r.low.min() <= y["bottom"] if y["sign"] > 0 else r.high.max() >= y["top"])
            if z is not None:
                after = r[r.index > z["ts"]]
                z["filled"] = bool(len(after)) and bool(after.low.min() <= z["bottom"] if z["sign"] > 0 else after.high.max() >= z["top"])
                live.append(z)
        if p.range_regime != "off" and len(hist) >= p.range_regime_days:
            w = hist[-p.range_regime_days:]
            hi, lo = max(x[0] for x in w), min(x[1] for x in w)
            older = w[:-5]
            fresh = max(x[0] for x in w[-5:]) > max(x[0] for x in older) or min(x[1] for x in w[-5:]) < min(x[1] for x in older)
            pos = (w[-1][2] - lo) / (hi - lo) if hi > lo else 0.5
            row["rr"] = (hi, lo, w[-1][0], w[-1][1], bool(not fresh and 0.2 <= pos <= 0.8))
        if len(r):
            hist.append((float(r.high.max()), float(r.low.min()), float(r.close.iloc[-1])))
        out[d] = row
    return out


def _lines(ctx, p, i: int, fps: list, sd=None, sw=None) -> list:
    """The grade lines (raw prices) [our interpretation]: the octants of the setup's dealing range (the sweep extreme .. the swing high the run into it
    began from, "OB below the dealing range lower quadrant"), today's ORG quadrants (k/4, -4..6 ORG heights: the gap and two heights either side)
    once the 09:30 bar has closed (an ORG at least grade_min_pts tall) and the octants of each active FPFVG."""
    from . import bh5e as _BH5E
    out = []
    if sw is not None and sw.get("ref_px") is not None and sw["ref_px"] > sw["ext"]:
        a, b = sw["ext"], sw["ref_px"]
        out += [float(sd.x(a + k * (b - a) / 8)) for k in range(9)]
    og = _BH5E.org_now(ctx, p, i)
    qmin = max(p.grade_min_pts, 20 * p.org_handle if p.org_size == "q20" else 0.0) * p.es_pt     # ORG-SIZE C: quadrants only on a gap of 20+ handles
    if og is not None and abs(og[1] - og[0]) >= qmin:
        a, b = min(og), max(og)
        out += [a + k * (b - a) / 4 for k in range(-8, 13)]
    for z in fps:
        out += [z["bottom"] + k * (z["top"] - z["bottom"]) / 8 for k in range(9)]
    return out


def active_fpfvgs(ctx, i: int) -> list:
    """The FPFVGs known at bar i (today's only after its completing bar)."""
    ts = ctx.idx[i]
    return [z for z in ((getattr(ctx, "cards", None) or {}).get("fpfvg") or ()) if ts > z["ts"]]


FVG_KINDS = ("fvg",)
def is_ob_kind(kind: str) -> bool:
    """ob_pre, ob_anchor, cisd_ob, release_ob, recap_ob, reaper_ob, ts_cc_1h_ob, arr_ob, arr_ob_post, arr_cons_ob_open, ... (S2 review: every OB kind)."""
    return "ob" in kind.split("_")


def array_gate(ctx, sd, sw: dict, i: int, p, entry: float, stop: float, tags: dict):
    """FVG-VALID B / OB-VALID B / WICK-PRIORITY B at the head of strategy._finish_order (side space) -> (entry, stop, funnel key or None).
    FVG-VALID B: "either first presentation, and if not first presented, always anchored to an octant or a quadrant" - the first FVG of the leg after
    the sweep, or one overlapping an active FPFVG of its side, or one whose gap holds a grade line (S2 review: the middle candle's whole range passed
    nearly every gap). OB-VALID B: the OB zone (body low .. entry / zone top) holds a grade line. FPFVG-DEF / FVG-CARRY act through these two gates
    (and the fvg_on_fpfvg / grade lines); the FPFVG is not an entry or target array of its own [our interpretation]."""
    kind = str(tags.get("entry_kind") or "")
    if kind in FVG_KINDS and tags.get("fvg_i") is not None:
        fi = int(tags["fvg_i"])
        g = next((z for z in sd.gaps if z.i == fi), None)
        if g is None:
            hit("fvg_gap_unknown")             # (S2 review: an FVG entry whose gap is not in sd.gaps skips both rules)
            return entry, stop, None
        if p.wick_priority:
            e0 = entry
            entry, stop = _wick_first(sd, g, i, p, entry, stop)
            if entry != e0:                    # (S2 review) the order's zone is now the wick: CE holds, aborts, adds and the ladder read it
                k = g.i - 2
                bt = float(max(sd.o[k], sd.c[k]))
                tags.update(fvg_bottom=bt, fvg_ce=float(entry), zone_top=float(sd.h[k]), ce_hold=False, wick_first=float(stop))
                tags.pop("ladder", None)
                tags.pop("ladder_fracs", None)
        if p.fvg_valid != "any":
            hit("eval_fvg_valid")
            first = min((z.i for z in sd.gaps if z.i - 2 >= sw["ext_i"] and z.i <= i), default=None) == fi
            fps = active_fpfvgs(ctx, i)
            lo, hi = sorted((sd.x(g.bottom), sd.x(g.top)))
            on_fp = any(z["sign"] == sd.sign and z["bottom"] <= hi and lo <= z["top"] for z in fps)
            if first or on_fp:
                hit("fvg_first" if first else "fvg_on_fpfvg")
                return entry, stop, None
            if not any(lo <= v <= hi for v in _lines(ctx, p, i, fps, sd, sw)):
                hit("fvg_not_valid")
                return entry, stop, "x_fvg_not_valid"
            hit("fvg_grade")
    elif is_ob_kind(kind) and p.ob_valid != "any" and tags.get("fvg_bottom") is not None:
        hit("eval_ob_valid")
        top = tags.get("zone_top")
        top = entry if top is None else max(entry, float(top))
        lo, hi = sorted((sd.x(float(tags["fvg_bottom"])), sd.x(float(top))))
        if not any(lo <= v <= hi for v in _lines(ctx, p, i, active_fpfvgs(ctx, i), sd, sw)):
            hit("ob_not_valid")
            return entry, stop, "x_ob_not_valid"
        hit("ob_grade")
    return entry, stop, None


def _wick_first(sd, g, i: int, p, entry: float, stop: float):
    """WICK-PRIORITY B: candle 1's wick next to the gap (its upper wick under a bullish FVG, side space) at least as tall as the FVG is the salient PD
    array: the limit at the wick's CE and the stop a pad beyond the wick (under candle 1's body) [our interpretation]. Kept only while the limit is
    under the market and the risk is at least min_risk_pts."""
    k = g.i - 2
    if k < 0:
        return entry, stop
    bt = max(sd.o[k], sd.c[k])
    wk = sd.h[k] - bt
    if wk <= 0 or wk < (g.top - g.bottom) - 1e-12:
        return entry, stop
    ce = (sd.h[k] + bt) / 2
    st = bt - p.pad
    if ce >= sd.c[i] or ce - st < p.min_risk_pts * p.es_pt:
        return entry, stop
    hit("wick_priority")
    return float(ce), float(st)


def range_gate(ctx, sd, o: dict, p) -> str | None:
    """RANGE-REGIME A: on a range-bound day ("never trade outside the range", "I'm not teaching buy a breakout") no long entry above the PDH and
    no short below the PDL; the turtle soups back into the range stay. None = allowed."""
    rr = (getattr(ctx, "cards", None) or {}).get("rr")
    if rr is None or not rr[4]:
        return None
    hit("eval_range_regime")
    _, _, pdh, pdl, _ = rr
    e = sd.x(o["entry"])
    if (sd.sign > 0 and e > pdh) or (sd.sign < 0 and e < pdl):            # (the PDH / PDL sit inside the multi-week range, so they are the tighter edge)
        hit("range_breakout")
        return "x_range_breakout"
    return None


# --- PREMARKET-RANGE --------------------------------------------------------------------------------------------
def premarket_range(ctx, df, p, tags: set) -> None:
    """PREMARKET-RANGE A: the pre-market pools ctx.pd pmh / pml are the high / low of today's bars that start in pm_window (07:00-09:00, to 08:30 on an
    08:30-release day with pm_news_cut) instead of the whole overnight to 09:30. No bar in the window = no pre-market pools."""
    if p.pm_window is None:
        return
    from .strategy import NEWS_0830
    a, b = p.pm_window
    if p.pm_news_cut and tags & NEWS_0830:
        b = min(b, 510)
    tt = df.index.hour * 60 + df.index.minute
    w = df[(tt >= a) & (tt < b)]
    if len(w):
        hit("pm_window")
        ctx.pd["pmh"], ctx.pd["pml"] = float(w.high.max()), float(w.low.min())
    else:
        ctx.pd.pop("pmh", None)
        ctx.pd.pop("pml", None)
    tw = tt[(tt >= a) & (tt < b)]
    for m in list(getattr(ctx, "pre_at", {})):          # (S3 review) the pre-09:30 sessions: the window as known at their start (bars starting before m, as DayCtx.pre_at)
        q = w[np.asarray(tw < m)]
        if len(q):
            ctx.pre_at[m] = (float(q.high.max()), float(q.low.min()))
        else:
            del ctx.pre_at[m]


# --- ORG-SIZE / ORG-AFTER-CE / ORG-CE-WINDOW: the ORG play --------------------------------------------------------
def org_play(ctx, p, i: int):
    """Today's ORG as the AM draw at bar i (bars before i are closed) -> (price, name) or None.
    ORG-SIZE picks by the gap's size in NQ handles (org_handle ES points each): B "20-75 handles likes the odds of trading to mid-gap, 75-120 gray,
    over 120 ... up to about a quarter ... then gap and go" -> < 20 and 75-120 none [our interpretation], > 120 the near quadrant (25 %); D / E none under
    30 / 40 handles; C the CE only under 20 handles. ORG-AFTER-CE: "continue" = the far edge (the prior close, full gap closure), "done" = the CE.
    ORG-CE-WINDOW: from org_ce_by on, the draw stays only if the CE (the near quadrant for an extreme gap) traded 09:30 .. org_ce_by."""
    if p.org_size == "off" or not (getattr(ctx, "org_today", False) and ctx.org):
        return None
    pc, op = ctx.org[-1]
    if pc == op:
        return None
    k0 = int(ctx.start + np.searchsorted(ctx.t[ctx.start:], 570))
    if i < k0:
        return None
    hnd = abs(pc - op) / (p.org_handle * p.es_pt)
    ce, q1 = (pc + op) / 2, op + 0.25 * (pc - op)
    m = p.org_size
    if (m == "buckets" and (hnd < 20 or 75 <= hnd < 120)) or (m == "min30" and hnd < 30) or (m == "min40" and hnd < 40):
        hit("org_size_none")
        return None
    if m == "buckets" and hnd >= 120:
        out, gate = (q1, "org_play_q1"), q1
    elif (m == "q20" and hnd < 20) or p.org_after_ce == "done":
        out, gate = (ce, "org_play_ce"), ce
    else:
        out, gate = (pc, "org_play_far"), ce
    if p.org_ce_by and ctx.t[i] >= p.org_ce_by:
        kb = int(ctx.start + np.searchsorted(ctx.t[ctx.start:], p.org_ce_by))
        hi, lo = ctx.h[k0:min(i, kb)], ctx.l[k0:min(i, kb)]
        if not len(hi) or not (hi.max() >= gate if pc > op else lo.min() <= gate):
            hit("org_ce_late")
            return None
    hit(out[1])
    return out


# --- OVERNIGHT-HOLD ---------------------------------------------------------------------------------------------
def _daily_ces(ds: list, k: int, look: int = 60) -> list:
    """The CEs of the daily FVGs (RTH bars of the day frames ds[k-look .. k]) that no later day through day k has traded back to."""
    rows = [(float(r.high.max()), float(r.low.min())) for r in (_rth(g) for g in ds[max(0, k - look):k + 1]) if len(r)]
    out = []
    for j in range(2, len(rows)):
        h0, l0 = rows[j - 2]
        h2, l2 = rows[j]
        if l2 > h0:
            ce = (l2 + h0) / 2
        elif h2 < l0:
            ce = (h2 + l0) / 2
        else:
            continue
        later = rows[j + 1:]
        if not any(lo <= ce <= hi for hi, lo in later):
            out.append(ce)
    return out


def osok_hold(tr, ds: list, k: int, p) -> None:
    """OVERNIGHT-HOLD B (OSOK, "hold ... overnight to a daily FVG CE"): a trade the session close flattened ("eod") keeps its remaining lots past the
    close when an untraded daily FVG CE lies ahead of the close; the later day frames (ds[k+1 ..], the engine's bars only: the 16:00-04:00 hours are
    not in them) are walked until the CE (exit there), the stop (the initial stop, break-even once a partial was taken [our interpretation]; the stop
    first when one bar holds both) or osok_days sessions (exit at that day's last close). The adds after midnight are not built. The exposure of the
    held lots is not counted against later trades [our interpretation]. Edits tr.exits in place."""
    if not tr.exits or tr.exits[-1][3] != "eod" or k + 1 >= len(ds):
        return
    ts0, px0, q, _ = tr.exits[-1]
    s = 1 if tr.side == "long" else -1
    ahead = [c for c in _daily_ces(ds, k) if s * (c - px0) > 0]
    if not ahead:
        hit("osok_none")
        return
    ce = min(ahead, key=lambda c: abs(c - px0))
    stop = tr.entry if len(tr.exits) > 1 else tr.stop
    if s * (px0 - stop) <= 0:
        return
    hit("osok_hold")
    for g in ds[k + 1:k + 1 + p.osok_days]:
        g = g[g.index > ts0]
        for ts, hi, lo in zip(g.index, g.high.values, g.low.values):
            if (lo <= stop) if s > 0 else (hi >= stop):
                tr.exits[-1] = (ts, float(stop), q, "osok_stop")
                hit("osok_stop")
                return
            if (hi >= ce) if s > 0 else (lo <= ce):
                tr.exits[-1] = (ts, float(ce), q, "osok_ce")
                hit("osok_ce")
                return
        if len(g):
            last = (g.index[-1], float(g.close.iloc[-1]))
    if "last" in locals():
        tr.exits[-1] = (last[0], last[1], q, "osok_time")
        hit("osok_time")


def check_params(p) -> None:
    """Validation (strategy.Params.__post_init__)."""
    if p.ath_rule not in ("off", "no_top_pick", "longs_only"):
        raise ValueError(f"ath_rule {p.ath_rule!r}: expected off / no_top_pick / longs_only")
    if not 0 <= p.ath_near_frac < 1:
        raise ValueError("ath_near_frac in [0, 1)")
    if p.fpfvg_def not in ("off", "time") or p.fvg_valid not in ("any", "first_or_grade") or p.ob_valid not in ("any", "grade"):
        raise ValueError("fpfvg_def off / time; fvg_valid any / first_or_grade; ob_valid any / grade")
    if p.wick_pick not in ("reach", "longest") or p.range_regime not in ("off", "fade"):
        raise ValueError("wick_pick reach / longest; range_regime off / fade")
    if p.fvg_carry_days < 0 or p.range_regime_days < 6 or p.grade_min_pts < 0:
        raise ValueError("fvg_carry_days >= 0, range_regime_days >= 6, grade_min_pts >= 0")
    if p.pm_window is not None and not (len(p.pm_window) == 2 and 0 <= p.pm_window[0] < p.pm_window[1] <= 570):
        raise ValueError("pm_window None or (start, end) minutes with 0 <= start < end <= 570")
    if p.org_size not in ("off", "same", "buckets", "q20", "min30", "min40") or p.org_after_ce not in ("continue", "done"):
        raise ValueError("org_size off / same / buckets / q20 / min30 / min40; org_after_ce continue / done")
    if p.org_handle <= 0 or not (p.org_ce_by == 0 or 571 <= p.org_ce_by <= 960):
        raise ValueError("org_handle > 0; org_ce_by 0 or 571..960")
    if p.overnight_hold not in ("off", "osok") or p.osok_days < 1:
        raise ValueError("overnight_hold off / osok; osok_days >= 1")
