"""Coverage gap 2 (package 2) and 3a: the symmetrical-market gate and the DXY daily / hourly rules (coverage_build_2026-10-31.md; dxy_intraday_spec_2026-10-31.md items 12-16).
Every switch defaults off. A DXY bar is used only once it has closed (dxy.closed); a swing is confirmed only by its right-hand bar.

  sym_gate   B17.5 (031 ~50:02; 045 ~2:50:01; 046 ~1:23:17; 048 ~13:02, ~41:01; 095 ~27:01; 098 ~55:06; 102 ~31:27): ES, NQ and YM post the same swing extreme and DXY the opposite one.
             scalp_now / size_mult / order_ok below.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import dxy as DXY

HITS: Counter = Counter()


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    from . import strategy
    return strategy


def _tfbars(c_, sg: int, t_end, tf: int, back: int = 600):
    """(bar starts, X) of the complete tf-minute bars of the DayCtx-like `c_` that closed at or before t_end; X = high (sg>0) or -low (sg<0), so a higher X is a new extreme in the trade's direction."""
    n = int(c_.idx.searchsorted(t_end, side="left"))            # base bars starting before t_end
    lo = max(0, n - back)
    idx = c_.idx[lo:n]
    if not len(idx):
        return None
    x = (c_.h if sg > 0 else -c_.l)[lo:n]
    s = pd.Series(x, index=idx)
    g = s.groupby(idx.floor(f"{tf}min")).max()
    starts = g.index
    ok = (starts + pd.Timedelta(minutes=tf)) <= t_end
    return starts[ok], g.values[ok]


def _swings(x: np.ndarray) -> list:
    """Indices of 3-candle swing highs of x, confirmed (the right-hand bar exists)."""
    return [j for j in range(1, len(x) - 1) if x[j] > x[j - 1] and x[j] > x[j + 1]]


def _ext_near(starts, x, t, span) -> float | None:
    """The highest x among the bars starting within [t - span, t + span]; None when there is none."""
    lo, hi = starts.searchsorted(t - span, side="left"), starts.searchsorted(t + span, side="right")
    return float(x[lo:hi].max()) if hi > lo else None


def sym_state(ctx, sg: int, i: int, p):
    """(state, no_dxy) of the symmetry at closed ES bar i for trade direction sg: "ok" = ES, NQ and YM each posted the new extreme of each of the last `sym_lookback` ES swing extremes (within `sym_win` bars)
    and DXY the opposite one; "crack" = ES posted them and a partner / DXY did not; "none" = ES has no such run of new extremes (a counter-trend or ranging moment: no information);
    "na" = NQ or YM missing. no_dxy = the DXY leg was not available (counted as off) and the state is the indices'."""
    ps, p2 = getattr(ctx, "pside", None), getattr(ctx, "partner2", None)
    if ps is None or ps[0] is None or not p2:
        return "na", True
    key = ("sym", sg, i)
    cache = ctx.__dict__.setdefault("_cg_cache", {})
    if key in cache:
        return cache[key]
    tf = p.sym_tf
    t_end = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    es = _tfbars(ctx, sg, t_end, tf)
    nq = _tfbars(ps[0], sg, t_end, tf)
    ym = _tfbars(p2[0], sg, t_end, tf)
    res = ("na", True)
    if es is not None and nq is not None and ym is not None:
        sws = _swings(es[1])
        L = p.sym_lookback
        if len(sws) >= L + 1:
            span = pd.Timedelta(minutes=tf * p.sym_win)
            ks = range(len(sws) - L, len(sws))
            pairs = [(es[0][sws[k]], es[0][sws[k - 1]]) for k in ks]
            if not all(es[1][sws[k]] > es[1][sws[k - 1]] for k in ks):
                res = ("none", True)
            else:
                def conf(b, sp=span):
                    for tn, tp in pairs:
                        a, bb = _ext_near(b[0], b[1], tn, sp), _ext_near(b[0], b[1], tp, sp)
                        if a is None or bb is None or not a > bb:
                            return False
                    return True
                ok_idx = conf(nq) and conf(ym)
                no_dxy, ok_dxy = True, True
                if p.sym_dxy != "off":
                    dtf = 60 if p.sym_dxy == "1h" else tf
                    db = DXY.closed(DXY.bars(dtf, "auto" if p.sym_dxy == "1h" else "spot"), t_end)
                    if db is not None and len(db) and db.index[0] <= pairs[0][1]:
                        y = (-db.low if sg > 0 else db.high).values
                        no_dxy = False
                        ok_dxy = conf((db.index, y), pd.Timedelta(minutes=dtf * (1 if p.sym_dxy == "1h" else p.sym_win)))
                res = (("ok" if (ok_idx and ok_dxy) else "crack"), no_dxy)
    cache[key] = res
    return res


def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """The day-context scalp reason: not symmetrical (a crack) with sym_gate "hold" / "scalp" = high resistance: T1 only, no adds."""
    why = scalp_now_dxy(ctx, p, session, i, sign)
    if why:
        return why
    if p.sym_gate not in ("hold", "scalp") or i is None or not sign:
        return ""
    st, _ = sym_state(ctx, sign, i, p)
    if st == "crack":
        hit("sym_scalp")
        return "cg_sym_crack"
    return ""


def size_mult(ctx, sd, i: int, p, lvt: list) -> float:
    if p.sym_gate == "scalp" and sym_state(ctx, sd.sign, i, p)[0] == "crack":
        lvt.append("size_sym_crack")
        return p.sym_scalp_risk
    return 1.0


def order_ok(ctx, sd, o: dict, session: str, i: int, p, trades=()):
    """sym_gate: "tag" tags the order sym_ok / sym_crack (+ sym_no_dxy); "skip" drops a crack; sym_crack_block_reversal drops an order against a confirmed (all-ok) trend."""
    why = order_ok_dxy(ctx, sd, o, session, i, p, trades)
    if why is not None:
        return why
    if p.sym_gate == "off" and not p.sym_crack_block_reversal:
        return None
    S = _S()
    tags = []
    st, no_dxy = sym_state(ctx, sd.sign, i, p)
    if p.sym_gate != "off":
        if st in ("ok", "crack"):
            tags.append("sym_" + st)
            if no_dxy:
                tags.append("sym_no_dxy")
        if p.sym_gate == "skip" and st == "crack":
            hit("sym_skip")
            return "x_cg_sym_crack"
    if p.sym_crack_block_reversal and sym_state(ctx, -sd.sign, i, p)[0] == "ok":
        hit("sym_block_reversal")
        return "x_cg_sym_trend"
    for t in tags:
        S._CG1._tag(o, t)
    return None


# --------------------------------------------------------------------------------------------------------------------------------------
# 3a: DXY daily / hourly rules (spec items 13-16). One DXY series per comparison: `dxy_htf_src` "dx" (Databento DX 1h, 2019-2026; the default, it also covers 2026) / "spot".
# --------------------------------------------------------------------------------------------------------------------------------------

def _t_end(ctx, i: int):
    return ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)


def _hourly_today(ctx, i: int, p):
    """(closed DXY 1h bars of today's session (18:00 the evening before to the closed bar i), closed daily sessions before today); None when DXY has no data for the date."""
    src = p.dxy_htf_src
    h = DXY.closed(DXY.bars(60, src), _t_end(ctx, i))
    dly = DXY.daily(src)
    if h is None or dly is None or not len(h):
        return None
    day = pd.Timestamp(ctx.day)
    lab = DXY.session_label(h.index)
    ht = h[lab == day]
    d = dly[dly.index < day]
    if not len(ht) or len(d) < 5 or (day - d.index[-1]).days > 6:
        return None
    return ht, d


def _daily_swing_levels(d: pd.DataFrame, kind: str, lookback: int) -> list:
    """Old untaken 3-candle daily swing lows (kind "low") / highs ("high") among the last `lookback` completed sessions: [(session date, level)]."""
    d = d.iloc[-lookback:]
    x = d.low.values if kind == "low" else d.high.values
    out = []
    for j in range(1, len(x) - 1):
        if kind == "low" and x[j] < x[j - 1] and x[j] < x[j + 1] and x[j + 1:].min() > x[j]:
            out.append((d.index[j], float(x[j])))
        if kind == "high" and x[j] > x[j - 1] and x[j] > x[j + 1] and x[j + 1:].max() < x[j]:
            out.append((d.index[j], float(x[j])))
    return out


def dxy_ts_state(ctx, i: int, p) -> int:
    """Item 13 (030 ~39:00, ~1:37:28): +1 = DXY pierced an old daily low and closed back above it within `dxy_ts_back` 1h bars (a DXY turtle soup: the dollar goes up, an ES buy-side run is a raid); -1 = the mirror
    at an old daily high. The latest completed pattern at the closed bar i wins; 0 = none / no DXY data."""
    key = ("ts", i)
    cache = ctx.__dict__.setdefault("_cg_cache", {})
    if key in cache:
        return cache[key]
    res = 0
    got = _hourly_today(ctx, i, p)
    if got is not None:
        ht, d = got
        best = None
        for kind, sgn in (("low", 1), ("high", -1)):
            for _, lv in _daily_swing_levels(d, kind, p.dxy_ts_lookback):
                lo, hi, cl = ht.low.values, ht.high.values, ht.close.values
                pierced = np.flatnonzero(lo < lv) if kind == "low" else np.flatnonzero(hi > lv)
                if not len(pierced):
                    continue
                k = int(pierced[0])
                for m in range(k, min(len(ht), k + p.dxy_ts_back + 1)):
                    if (cl[m] > lv) if kind == "low" else (cl[m] < lv):
                        e = ht.end.iloc[m]
                        if best is None or e > best[0]:
                            best = (e, sgn)
                        break
        res = best[1] if best else 0
    cache[key] = res
    return res


def dxy_mt_state(ctx, i: int, p) -> str:
    """Item 14 (031 ~11:20-12:30): "chop" = DXY trades inside an old daily order-block candle on the wrong side of its mean threshold (a bearish OB above price: inside and below the MT; a bullish OB below price:
    inside and above the MT) = choppy ES; "expand" = through the MT (fast ES expansion); "" = none. The candle: the most recent daily up-close candle of the last `dxy_mt_lookback` sessions followed by a daily close
    below its low (bearish OB; the mirror down-close candle for a bullish one) whose range holds the last closed 1h close [our interpretation of ICT's old daily candle]."""
    key = ("mt", i)
    cache = ctx.__dict__.setdefault("_cg_cache", {})
    if key in cache:
        return cache[key]
    res = ""
    got = _hourly_today(ctx, i, p)
    if got is not None:
        ht, d = got
        px = float(ht.close.iloc[-1])
        dd = d.iloc[-p.dxy_mt_lookback:]
        o, h_, l_, c = (dd[k].values for k in ("open", "high", "low", "close"))
        for j in range(len(dd) - 2, -1, -1):
            nxt = c[j + 1]
            for bearish in (True, False):
                if bearish and not (c[j] > o[j] and nxt < l_[j]):
                    continue
                if not bearish and not (c[j] < o[j] and nxt > h_[j]):
                    continue
                if not (l_[j] <= px <= h_[j]):
                    continue
                mt = (o[j] + c[j]) / 2 if p.dxy_mt_mode == "body" else (h_[j] + l_[j]) / 2
                res = ("chop" if px < mt else "expand") if bearish else ("chop" if px > mt else "expand")
                break
            if res:
                break
    cache[key] = res
    return res


def dxy_week_delivered(ctx, d, i: int, p) -> bool:
    """Item 15 (038 ~3:57-6:08): the DXY weekly objective is delivered at the closed bar i: the week's DXY high / low so far (the 18:00 Sunday reopen on, closed 1h bars) reached `dxy_pwh` / `dxy_pwl` (the prior week's
    DXY high / low) or `dxy_obj` (the nearest unfilled daily FVG of the last 40 sessions beyond the week's open, in the direction the week has moved [our interpretation of the volume imbalance above the relative equal highs])."""
    names = [n for n in p.week_done_levels if n.startswith("dxy_")]
    if not names:
        return False
    key = ("wk", i)
    cache = ctx.__dict__.setdefault("_cg_cache", {})
    if key in cache:
        return cache[key]
    res = False
    src = p.dxy_htf_src
    dly = DXY.daily(src)
    h = DXY.closed(DXY.bars(60, src), _t_end(ctx, i))
    if dly is not None and h is not None and len(h):
        day = pd.Timestamp(d)
        mon = day - pd.Timedelta(days=day.weekday())
        lab = DXY.session_label(h.index)
        wk = h[lab >= mon]
        prior = dly[(dly.index >= mon - pd.Timedelta(days=7)) & (dly.index < mon)]
        done = dly[dly.index < day]
        if len(wk) and len(prior) >= 3 and len(done) >= 5:
            hi, lo = float(wk.high.max()), float(wk.low.min())
            open_ = float(wk.open.iloc[0])
            up = float(wk.close.iloc[-1]) >= open_
            if "dxy_pwh" in names and hi >= float(prior.high.max()):
                res = True
            if "dxy_pwl" in names and lo <= float(prior.low.min()):
                res = True
            if "dxy_obj" in names and not res:
                x = done.iloc[-40:]
                for j in range(len(x) - 1, 1, -1):          # newest first: a bullish FVG (x[j-2].high < x[j].low) above the open for an up week, the bearish mirror below
                    a, b = x.iloc[j - 2], x.iloc[j]
                    if up and a.high < b.low and b.low > open_ and (j + 1 >= len(x) or float(x.high.iloc[j + 1:].max()) < b.low):         # an unfilled gap above the week's open
                        res = hi >= b.low
                        break
                    if not up and a.low > b.high and b.high < open_ and (j + 1 >= len(x) or float(x.low.iloc[j + 1:].min()) > b.high):
                        res = lo <= b.high
                        break
    cache[key] = res
    return res


def _ladder_first(d: pd.DataFrame, up: bool, px: float, names, lookback: int = 60):
    """Item 9 / 16 ladder (035 ~24:19): the first level of the dollar's HTF target ladder in its direction `up`, from the completed daily bars: "rb" = the close of the nearest old swing-high candle above price
    (the rejection block; below price for `up` False), "rb_ce" = the CE of its wick, "wick" = its extreme, "fvg" = the near edge of the nearest unfilled daily FVG beyond price. None when none exists.
    ("wk_ob_open" - the weekly bearish OB's opening price of 059 - needs the weekly arrays of the dollar and is not built.)"""
    lv = []
    kind = "high" if up else "low"
    for _, ext in sorted(_daily_swing_levels(d, kind, lookback), key=lambda t: t[0], reverse=True):
        if (ext > px) if up else (ext < px):
            row = d.loc[d.index[d[kind] == ext][0]]
            rb = float(row.close)
            cand = {"rb": rb, "rb_ce": (rb + ext) / 2, "wick": float(ext)}
            lv = [cand[n] for n in names if n in cand and ((cand[n] > px) if up else (cand[n] < px))]
            break
    if "fvg" in names:
        x = d.iloc[-40:]
        for j in range(len(x) - 1, 1, -1):
            a, b = x.iloc[j - 2], x.iloc[j]
            if up and a.high < b.low and b.low > px and (j + 1 >= len(x) or float(x.high.iloc[j + 1:].max()) < b.low):
                lv.append(float(b.low))
                break
            if not up and a.low > b.high and b.high < px and (j + 1 >= len(x) or float(x.low.iloc[j + 1:].min()) > b.high):
                lv.append(float(b.high))
                break
    if not lv:
        return None
    return min(lv) if up else max(lv)


def dxy_end_day_block(ctx, sd, i: int, p, trades) -> bool:
    """Item 16 (059 ~23:01): an earlier trade of today in this direction hit its final target (ES reached its target pool) and, within `dxy_end_win` 5-minute bars of that exit [our interpretation of "at the same
    time": the DXY 1h bar holding it, plus that margin], DXY reached the first level of its HTF ladder in the opposite direction (`dxy_obj_levels`): the day's move is done. Blocks further orders in that direction
    until 15:00 ("block", the last-hour model stays free) or to the close ("block_day")."""
    if not trades:
        return False
    t_now = int(ctx.t[i])
    if p.dxy_end_day == "block" and t_now >= 900:
        return False
    got = _hourly_today(ctx, i, p)
    if got is None:
        return False
    ht, d = got
    margin = pd.Timedelta(minutes=5 * p.dxy_end_win)
    for tr in trades:
        if not (tr.exits and tr.final_hit) or (1 if tr.side == "long" else -1) != sd.sign:
            continue
        tx = tr.exits[-1][0]
        if tx > ctx.idx[i]:
            continue
        up = sd.sign < 0                                         # ES short -> the dollar goes up
        lvl = _ladder_first(d, up, float(ht.open.iloc[0]), p.dxy_obj_levels)
        if lvl is None:
            continue
        hit_ = ht[(ht.high >= lvl)] if up else ht[(ht.low <= lvl)]
        if not len(hit_):
            continue
        b0 = hit_.iloc[0]
        if b0.name - margin <= tx <= b0.end + margin:
            return True
    return False


def order_ok_dxy(ctx, sd, o: dict, session: str, i: int, p, trades=()):
    """3a order filters: dxy_ts_raid (item 13), dxy_daily_mt (14), dxy_end_day (16)."""
    S = _S()
    if p.dxy_ts_raid != "off":
        st = dxy_ts_state(ctx, i, p)
        if st:
            S._CG1._tag(o, "dxy_ts_up" if st > 0 else "dxy_ts_dn")
            if p.dxy_ts_raid in ("filter", "prefer") and st == sd.sign:
                hit("dxy_ts_block")
                return "x_cg_dxy_ts"                                  # DXY turtle soup up -> the ES buy-side run was a raid: no longs (down -> no shorts)
    if p.dxy_daily_mt != "off":
        st = dxy_mt_state(ctx, i, p)
        if st:
            S._CG1._tag(o, "dxy_mt_" + st)
            if p.dxy_daily_mt == "skip" and st == "chop":
                hit("dxy_mt_skip")
                return "x_cg_dxy_mt"
    if p.dxy_end_day != "off" and dxy_end_day_block(ctx, sd, i, p, trades):
        S._CG1._tag(o, "dxy_end_day")
        if p.dxy_end_day != "tag":
            hit("dxy_end_day_block")
            return "x_cg_dxy_end_day"
    return None


def scalp_now_dxy(ctx, p, session: str, i, sign: int = 0) -> str:
    if p.dxy_daily_mt == "scalp" and i is not None and dxy_mt_state(ctx, i, p) == "chop":
        hit("dxy_mt_scalp")
        return "cg_dxy_mt"
    return ""
