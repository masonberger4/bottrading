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


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """sym_gate: "tag" tags the order sym_ok / sym_crack (+ sym_no_dxy); "skip" drops a crack; sym_crack_block_reversal drops an order against a confirmed (all-ok) trend."""
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
