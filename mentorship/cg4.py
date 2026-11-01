"""DXY intraday management and SMT rules (dxy_intraday_spec_2026-10-31.md items 2, 3, 7, 8, 9, 10): the pool-run cap, the DXY SMT, the in-trade bank, the DXY unicorn, the DXY-target partial and the
non-confirmation exit. They read the 1-minute SPOT file (cg3 / dxy.py); without it every rule is "no information". Management runs on closed ES bars (like smt_bank): a DXY bar is used only once it
has closed. All switches default off. `fx_nonconf_exit` (EURUSD / GBPUSD) is not built: the pair data is not on the laptop.

Side space: sd.sign = +1 for a long order. For an ES order of direction sg the dollar CONFIRMS when it moves the other way: Y = -low (sg > 0: a falling dollar makes new Y highs) or high (sg < 0).
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import cg3 as C3
from . import dxy as DXY

HITS: Counter = Counter()
NY = DXY.NY
TFS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    from . import strategy
    return strategy


def _Y(b, sg: int):
    return (-b.low if sg > 0 else b.high).values


def _tf_bars(ctx, i: int, tf: int, from_min: int = 7 * 60):
    return C3._day_bars(ctx, i, tf, from_min)


def dxy_unconfirmed(ctx, sg: int, i: int, tf: int, t_from, from_min: int = 7 * 60) -> bool | None:
    """True when the dollar has NOT confirmed an ES move in direction sg at the closed ES bar i (037 ~32:37: "so far it hasn't made a higher high than the high it's already produced"): since `t_from` (the fill) its
    closed 5-minute closes have made no Y extreme beyond the last confirmed swing of its `tf`-minute bars that ended before the fill. Y = -close (sg > 0) or close (sg < 0). None = no data / no swing before the fill."""
    tfill = pd.Timestamp(t_from)
    b = _tf_bars(ctx, i, tf, from_min)
    b5 = _tf_bars(ctx, i, 5, from_min)
    if b is None or b5 is None:
        return None
    pre = b[b.end <= tfill]
    if len(pre) < 3:
        return None
    y = -pre.close.values if sg > 0 else pre.close.values
    sw = C3._swing_idx(y, True)
    if not sw:
        return None
    post = b5[b5.index >= tfill]
    if not len(post):
        return None
    yp = -post.close.values if sg > 0 else post.close.values
    return bool(yp.max() <= y[sw[-1]] + 1e-12)


def _es_new(sd, pos, i: int) -> bool:
    return bool(i > pos["fill_i"] and sd.h[i] > sd.h[pos["fill_i"]:i].max() + 1e-9)


def _sister_div(ctx, sd, pos, i: int) -> bool:
    """A sister index (NQ or YM) makes a new extreme in the trade's direction at bar i while ES does not (037 ~32:37: "the Dow has made a lower low where ES has not")."""
    from . import cg1 as C1
    if _es_new(sd, pos, i):
        return False
    pr = C1._partners(ctx, sd, pos, i)
    return any(bool(s_.h[j] > s_.h[jf:j].max() + 1e-9) for s_, j, jf in pr)


def _bank(S, sd, pos, tr, ts, c, p, frac: float, name: str) -> None:
    if frac <= 0:
        return
    q = min(pos["left"], max(p.lot, S._lots(pos["left"] * frac, p.lot)))
    if q <= 0:
        return
    tr.exits.append((ts, sd.x(c), q, name))
    pos["left"] -= q


def cap_next_rung(pos: dict) -> bool:
    """The ladder ends at its next rung, no runner (spec item 2): the rungs after the next one are dropped, T2 is pulled onto it."""
    k = pos.get("k", 0)
    lv = pos.get("levels")
    if not lv or len(lv) <= k + 1:
        return False
    pos["levels"] = list(lv[:k + 1])
    if pos.get("level_kinds") is not None:
        pos["level_kinds"] = list(pos["level_kinds"][:k + 1])
    if pos.get("t2") is not None and pos["t2"] > pos["levels"][-1]:
        pos["t2"] = pos["levels"][-1]
    pos["final_T"] = False
    pos["runner"] = False
    return True


def _ladder_levels(ctx, sg: int, p):
    """All levels of the dollar's HTF ladder in the direction opposite to ES (sg < 0 -> up), from the completed daily bars before today (cg2._ladder_all); [] when none."""
    from . import cg2
    d = DXY.daily("spot")                                  # always the spot series: it is compared with spot bars (spec 0.3: never mix series)
    if d is None:
        return []
    day = pd.Timestamp(ctx.day)
    d = d[d.index < day]
    if len(d) < 5:
        return []
    return cg2._ladder_all(d, sg < 0, float(d.close.iloc[-1]), p.dxy_ladder)


def manage(ctx, sd, pos: dict, tr, i: int, ts, p) -> None:
    """dxy_pool_run (2), dxy_intrade (7), dxy_target_partial (9), dxy_nonconf_exit (10): run on each closed bar after the stop / ladder tests of the engine."""
    if not pos["left"] or i <= pos["fill_i"]:
        return
    S = _S()
    sg = sd.sign
    c = sd.c[i]
    basis = pos["basis"] / pos["n"]
    risk = abs(tr.entry - tr.stop)

    # ---- item 2: the DXY pool must keep going --------------------------------------------------------------------------------------------
    if p.dxy_pool_run != "off" and not pos.get("dxy_pool_done"):
        b = _tf_bars(ctx, i, 5)
        if b is not None and len(b) >= 4:
            tfill = ctx.idx[pos["fill_i"]]
            if "dxy_pool" not in pos:
                pre = b[b.end <= tfill + pd.Timedelta(minutes=ctx.tf)]
                pool = None
                if len(pre) >= 4:
                    px = float(pre.close.iloc[-1])                      # the dollar's pool: a long needs the dollar's sell-side (its swing lows below price) to be run
                    for j in C3._swing_idx(pre.close.values if sg > 0 else -pre.close.values, False)[::-1]:
                        lv = float(pre.close.iloc[j])
                        if (lv < px) if sg > 0 else (lv > px):
                            pool = lv
                            break
                pos["dxy_pool"] = pool
            pool = pos.get("dxy_pool")
            if pool is not None:
                post = b[b.index >= tfill]
                lo = post.low.values if sg > 0 else -post.high.values
                lv = pool if sg > 0 else -pool
                pierced = np.flatnonzero(lo < lv)
                if len(pierced):
                    k = int(pierced[0])
                    depth = lv - float(lo[k:].min())
                    cl = post.close.values if sg > 0 else -post.close.values
                    back = np.flatnonzero(cl[k:k + p.dxy_expand_bars + 1] > lv)
                    if depth >= p.dxy_expand_min - 1e-12 and not len(back) and len(post) > k + p.dxy_expand_bars:
                        pos["dxy_pool_done"] = True
                        hit("dxy_pool_confirmed")
                    elif depth < p.dxy_expand_min - 1e-12 and len(back):
                        pos["dxy_pool_done"] = True
                        hit("dxy_pool_failed")
                        if p.dxy_pool_run in ("cap", "hold_gate"):
                            if cap_next_rung(pos):
                                hit("dxy_pool_cap")

    # ---- items 7 and 10: the in-trade check and the non-confirmation exit (D3: staged) -------------------------------------------------------
    want7 = p.dxy_intrade != "off" and (sg < 0 or p.dxy_intrade_long)
    want10 = p.dxy_nonconf_exit != "off"
    unicorn_exit(ctx, sd, pos, tr, i, ts, p)
    if not pos["left"]:
        return
    if (want7 or want10) and risk > 0 and not pos.get("dxy_nc_done"):
        es_new = _es_new(sd, pos, i)
        sister = _sister_div(ctx, sd, pos, i)
        if es_new or sister:
            started = bool(tr.exits)
            if want10 and (started or p.dxy_nonconf_exit == "any") and es_new:
                if dxy_unconfirmed(ctx, sg, i, 5, ctx.idx[pos["fill_i"]]):
                    hit("dxy_nonconf_exit")
                    if p.dxy_nonconf_exit != "tag":
                        tr.exits.append((ts, sd.x(c), pos["left"], "dxy_nonconf"))
                        pos["left"] = 0
                        pos["dxy_nc_done"] = True
                        return
            if want7 and not started and not pos.get("dxy_banked") and (c - basis) / risk >= p.smt_bank_min_r:
                tfs = [TFS[t] for t in p.dxy_intrade_tfs]
                if all(dxy_unconfirmed(ctx, sg, i, t, ctx.idx[pos["fill_i"]]) for t in tfs):
                    hit("dxy_intrade")
                    if p.dxy_intrade == "bank":
                        _bank(S, sd, pos, tr, ts, c, p, p.dxy_intrade_sister_frac if sister else p.dxy_intrade_frac, "dxy_intrade")
                        pos["dxy_banked"] = True

    # ---- item 9: the DXY target ladder ----------------------------------------------------------------------------------------------------
    if p.dxy_target_partial != "off" and pos["left"] and (sg < 0 or p.dxy_intrade_long):
        b = _tf_bars(ctx, i, 5)
        if "dxy_ladder" not in pos and b is not None:
            pre = b[b.end <= ctx.idx[pos["fill_i"]]]
            px0 = float(pre.close.iloc[-1]) if len(pre) else None
            lv = _ladder_levels(ctx, sg, p) if px0 is not None else []
            pos["dxy_ladder"] = [v for v in lv if ((v > px0) if sg < 0 else (v < px0))]          # only the levels still ahead of the dollar at the fill
            pos["dxy_ladder_n"] = 0
        lv = pos.get("dxy_ladder")
        if lv and b is not None:
            post = b[b.index >= ctx.idx[pos["fill_i"]]]
            while len(post) and pos["dxy_ladder_n"] < len(lv) and pos["left"]:
                nxt = lv[pos["dxy_ladder_n"]]
                if not ((float(post.high.max()) >= nxt) if sg < 0 else (float(post.low.min()) <= nxt)):
                    break
                pos["dxy_ladder_n"] += 1
                hit("dxy_target_partial")
                if p.dxy_target_partial == "partial":
                    _bank(S, sd, pos, tr, ts, c, p, p.dxy_target_frac, "dxy_target")


# ---- item 3: the DXY SMT ---------------------------------------------------------------------------------------------------------------------

def dxy_smt(ctx, sd, i: int, sw: dict, p) -> bool | None:
    """True when the dollar did NOT confirm ES's new extreme (031 ~48:51, 032 ~34:21, 035 ~1:06:35): ES swept to a new low (sd.sign > 0; a new high for sd.sign < 0) and DXY's twin extreme (its high around
    the new low, the low around the new high; the best of the bars within `dxy_smt_win` ES bars of each ES swing bar) is not beyond its twin at the previous ES swing. None = no data / no prior swing."""
    if sw is None or sw.get("ext_i") is None:
        return None
    sg = sd.sign
    j1 = int(sw["ext_i"])
    x = sd.l                                       # side space: the swept extreme is a low for a long AND for a short (sd.l = -high of the real series)
    hist = [j for j in range(max(ctx.start + 1, j1 - 120), j1 - 1) if x[j] < x[j - 1] and x[j] < x[j + 1] and x[j] > x[j1]]      # the previous swing low that ES took out
    if not hist:
        return None
    j0 = hist[-1]
    tf = 1 if p.dxy_smt_tf == "1m" else 5
    b = C3._day_bars(ctx, i, tf, 0)
    if b is None:
        return None
    span = pd.Timedelta(minutes=ctx.tf * p.dxy_smt_win)
    y = (b.high if sg > 0 else -b.low).values

    def near(j):
        t = ctx.idx[j]
        lo, hi = b.index.searchsorted(t - span, side="left"), b.index.searchsorted(t + pd.Timedelta(minutes=ctx.tf), side="left")      # the same trailing window for both swings
        return float(y[lo:hi].max()) if hi > lo else None

    a, bb = near(j1), near(j0)
    if a is None or bb is None:
        return None
    return bool(a <= bb + 1e-9)


# ---- item 8: the DXY unicorn -----------------------------------------------------------------------------------------------------------------

def dxy_unicorn(ctx, sd, i: int, p) -> dict | None:
    """037 ~44:40-47:41: for an ES long, a DXY 1m bearish breaker (swing high 1, a swing low, a higher swing high 2 that takes the buy-side, then a body close below the swing low; zone = the swing-low candle's
    range) with a bearish 1m FVG that formed inside the zone, DXY trading up into the overlap and no 1m close above the FVG's high yet. Returns {"fvg_high": .., "fvg_low": .., "killed": bool} (the mirror for shorts)
    or None. Needs real 1m highs / lows to be exact: with the `line` bars of the spot file it is an approximation."""
    sg = sd.sign
    b = C3._day_bars(ctx, i, 1, 0)
    if b is None or len(b) < 12:
        return None
    h, l, o, c = (b[k].values for k in ("high", "low", "open", "close"))
    if sg < 0:                                             # the mirror: flip the series
        h, l, o, c = -l, -h, -o, -c
    sh, sl = C3._swing_idx(c, True), C3._swing_idx(c, False)
    for jl in sl[::-1]:
        hi_before = [j for j in sh if j < jl]
        hi_after = [j for j in sh if j > jl]
        if not hi_before or not hi_after:
            continue
        j1, j2 = hi_before[-1], hi_after[0]
        if not c[j2] > c[j1]:
            continue
        brk = [k for k in range(j2, len(c)) if c[k] < l[jl]]            # a body close below the swing low
        if not brk:
            continue
        kb = brk[0]
        z_hi, z_lo = float(h[jl]), float(l[jl])                          # the swing-low candle's range = the breaker zone
        for k in range(kb + 1, len(c)):                                  # a bearish FVG formed inside the zone after the break
            if k >= 2 and l[k - 2] > h[k] and l[k - 2] <= z_hi and h[k] >= z_lo:                   # the gap lies inside the zone
                f_hi, f_lo = float(l[k - 2]), float(h[k])
                killed = bool((c[k + 1:] > f_hi).any()) if k + 1 < len(c) else False
                return dict(fvg_high=f_hi if sg > 0 else -f_lo, fvg_low=f_lo if sg > 0 else -f_hi, killed=killed)
    return None


def unicorn_ok(ctx, sd, i: int, p) -> bool | None:
    u = dxy_unicorn(ctx, sd, i, p)
    if u is None:
        return None
    return not u["killed"]


def active(p) -> bool:
    return bool(p.dxy_pool_run != "off" or p.dxy_intrade != "off" or p.dxy_nonconf_exit != "off" or p.dxy_target_partial != "off" or (p.dxy_unicorn != "off" and p.dxy_unicorn_exit))


def entry_extra(ctx, sd, sw, i: int, p, lvt: list):
    """(extra SMT count, funnel key or None) of the DXY SMT (item 3) and the DXY unicorn (item 8) at an armed entry: "qualify" counts as one more confirmation next to the index SMT, "need" also drops the order
    without it. ("no_press" - blocking continuation entries until a confirmed new extreme - is not built.)"""
    extra = 0
    if p.dxy_smt != "off":
        v = dxy_smt(ctx, sd, i, sw, p)
        if v is True:
            lvt.append("smt_dxy")
            if p.dxy_smt != "tag":
                extra += 1
        elif v is False and p.dxy_smt == "need":                    # (None = no DXY data / no swing: no information, the entry is not blocked)
            hit("dxy_smt_need_fail")
            return extra, "x_no_dxy_smt"
    if p.dxy_unicorn != "off":
        ok = unicorn_ok(ctx, sd, i, p)
        if ok:
            lvt.append("dxy_unicorn")
            if p.dxy_unicorn != "tag":
                extra += 1
        elif p.dxy_unicorn == "need" and (ok is False or C3._day_bars(ctx, i, 1, 0) is not None):      # (no DXY data = no information; DXY data but no unicorn = the entry is blocked)
            hit("dxy_unicorn_need_fail")
            return extra, "x_no_dxy_unicorn"
    return extra, None


def unicorn_exit(ctx, sd, pos: dict, tr, i: int, ts, p) -> None:
    """dxy_unicorn_exit (qualify / need, not tag): a filled ES long qualified by the DXY unicorn closes when a DXY 1m body closes above the FVG's high that was in force at the fill (the vault, 037 ~49:48)."""
    if not (p.dxy_unicorn in ("qualify", "need") and p.dxy_unicorn_exit and pos["left"] and "dxy_unicorn" in str(getattr(tr, "lv_tags", ""))):
        return
    if "dxy_uni_fvg" not in pos:
        u = dxy_unicorn(ctx, sd, pos["fill_i"], p)
        pos["dxy_uni_fvg"] = None if u is None else (u["fvg_high"], u["fvg_low"])
    f = pos["dxy_uni_fvg"]
    if f is None:
        return
    b = C3._day_bars(ctx, i, 1, 0)
    if b is None:
        return
    c = b[b.index >= ctx.idx[pos["fill_i"]]].close.values
    if len(c) and ((c > f[0]).any() if sd.sign > 0 else (c < f[1]).any()):          # a long: a 1m close above the bearish FVG high; the short mirror: below the bullish FVG low
        hit("dxy_unicorn_exit")
        tr.exits.append((ts, sd.x(sd.c[i]), pos["left"], "dxy_unicorn"))
        pos["left"] = 0
