"""Scorecard cards (mentorship/cards.py): the engine concepts the cards needed that the engine did not have yet (Mase 2026-11-08: build every card default).

Each function sits behind its Params switch; interpretations the card does not pin down are marked [our interpretation]. `HITS` counts the code paths that ran (tests)."""
from __future__ import annotations

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
    (FPFVG-DEF A) and, while unfilled (a later RTH low through a bullish one's bottom / high through a bearish one's top), for fvg_carry_days trading
    days (FVG-CARRY A). Today's own FPFVG is listed with its ts (usable after that bar). The history is what the run loaded [our interpretation]."""
    out, live, hist = {}, [], []
    for g in ds:
        d = g.index[0].date()
        r = _rth(g)
        row = dict(fpfvg=[], rr=None)
        if p.fpfvg_def != "off":
            wk = d.isocalendar()[:2]
            live = [z for z in live if not z["filled"] and (z["wk"] == wk or z["age"] < p.fvg_carry_days)]
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
    began from, "OB below the dealing range lower quadrant"), today's ORG octants k = -16..24 once the 09:30 bar has closed (an ORG at least
    grade_min_pts tall) and the octants of each active FPFVG."""
    from . import bh5e as _BH5E
    out = []
    if sw is not None and sw.get("ref_px") is not None and sw["ref_px"] > sw["ext"]:
        a, b = sw["ext"], sw["ref_px"]
        out += [float(sd.x(a + k * (b - a) / 8)) for k in range(9)]
    og = _BH5E.org_now(ctx, p, i)
    if og is not None and abs(og[1] - og[0]) >= p.grade_min_pts * p.es_pt:
        a, b = min(og), max(og)
        out += [a + k * (b - a) / 8 for k in range(-16, 25)]
    for z in fps:
        out += [z["bottom"] + k * (z["top"] - z["bottom"]) / 8 for k in range(9)]
    return out


def active_fpfvgs(ctx, i: int) -> list:
    """The FPFVGs known at bar i (today's only after its completing bar)."""
    ts = ctx.idx[i]
    return [z for z in ((getattr(ctx, "cards", None) or {}).get("fpfvg") or ()) if ts > z["ts"]]


FVG_KINDS = ("fvg",)
OB_KINDS = ("ob_pre", "ob_anchor", "cisd_ob", "release_ob", "recap_ob", "reaper_ob", "ts_cc_1h_ob")


def array_gate(ctx, sd, sw: dict, i: int, p, entry: float, stop: float, tags: dict):
    """FVG-VALID B / OB-VALID B / WICK-PRIORITY B at the head of strategy._finish_order (side space) -> (entry, stop, funnel key or None).
    FVG-VALID B: "either first presentation, and if not first presented, always anchored to an octant or a quadrant" - the first FVG of the leg after
    the sweep, or one overlapping an active FPFVG of its side, or one whose middle candle touches a grade line. OB-VALID B: the OB zone on a grade line."""
    kind = str(tags.get("entry_kind") or "")
    if kind in FVG_KINDS and tags.get("fvg_i") is not None:
        fi = int(tags["fvg_i"])
        g = next((z for z in sd.gaps if z.i == fi), None)
        if g is None:
            return entry, stop, None
        if p.wick_priority:
            entry, stop = _wick_first(sd, g, i, p, entry, stop)
        if p.fvg_valid != "any":
            hit("eval_fvg_valid")
            first = min((z.i for z in sd.gaps if z.i - 2 >= sw["ext_i"] and z.i <= i), default=None) == fi
            fps = active_fpfvgs(ctx, i)
            lo, hi = sorted((sd.x(g.bottom), sd.x(g.top)))
            on_fp = any(z["sign"] == sd.sign and z["bottom"] <= hi and lo <= z["top"] for z in fps)
            if first or on_fp:
                hit("fvg_first" if first else "fvg_on_fpfvg")
                return entry, stop, None
            m = fi - 1
            mlo, mhi = sorted((sd.x(sd.l[m]), sd.x(sd.h[m])))
            if not any(mlo <= v <= mhi for v in _lines(ctx, p, i, fps, sd, sw)):
                hit("fvg_not_valid")
                return entry, stop, "x_fvg_not_valid"
            hit("fvg_grade")
    elif kind in OB_KINDS and p.ob_valid != "any" and tags.get("fvg_bottom") is not None:
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
    """RANGE-REGIME A: on a range-bound day ("never trade outside the range", "I'm not teaching buy a breakout") no long entry above the PDH or the
    multi-week range high and no short below the PDL or the range low; the turtle soups back into the range stay. None = allowed."""
    rr = (getattr(ctx, "cards", None) or {}).get("rr")
    if rr is None or not rr[4]:
        return None
    hit("eval_range_regime")
    hi, lo, pdh, pdl, _ = rr
    e = sd.x(o["entry"])
    if (sd.sign > 0 and e > min(pdh, hi)) or (sd.sign < 0 and e < max(pdl, lo)):
        hit("range_breakout")
        return "x_range_breakout"
    return None


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
