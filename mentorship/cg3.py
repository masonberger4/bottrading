"""DXY intraday entry rules (dxy_intraday_spec_2026-10-31.md items 1, 4, 5, 6, 11): the dollar's 5-minute state, the session gate, the 5m dealing-range EQ gate, the 09:15-09:30 range trigger and
the DXY leg of the swing-symmetry rule. They read the 1-minute SPOT file (data/dxy/spot_dxy_1m_close_2019-2025_NYtime.csv.gz; close only, `line` bars - high / low from the closes) and nothing else:
without it, or outside 2019-2025, every rule returns "no information" (no block, tag dxy_na). A DXY bar is used only once it has closed (dxy.closed); a swing is confirmed by its right-hand bar.
All switches default off. DXY is inverse: a falling dollar is the ES-long condition.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import dxy as DXY

HITS: Counter = Counter()
NY = DXY.NY


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    from . import strategy
    return strategy


def _t_end(ctx, i: int):
    return ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _day_bars(ctx, i: int, tf: int, from_min: int = 0):
    """Closed DXY spot bars of `tf` minutes of today's calendar day from `from_min` (minutes of day) to the closed ES bar i; None when the spot file does not cover the date."""
    b = DXY.closed(DXY.bars(tf, "spot"), _t_end(ctx, i))
    if b is None or not len(b):
        return None
    day = pd.Timestamp(ctx.day, tz=NY)
    lo = b.index.searchsorted(day + pd.Timedelta(minutes=from_min))
    b = b.iloc[lo:]
    if not len(b) or b.index[0] > day + pd.Timedelta(minutes=from_min + 3 * tf + 60):         # the file has nothing near the start of the window: no information
        return None
    return b


def _swing_idx(x: np.ndarray, high: bool) -> list:
    if high:
        return [j for j in range(1, len(x) - 1) if x[j] > x[j - 1] and x[j] > x[j + 1]]
    return [j for j in range(1, len(x) - 1) if x[j] < x[j - 1] and x[j] < x[j + 1]]


# ---- item 1: the three states (048 ~23:44; 022 ~4:25) ---------------------------------------------------------------------------------

def dxy_state(ctx, i: int, p) -> int | None:
    """+1 rallying, -1 falling, 0 consolidating / mixed on the DXY 5m bars from `dxy_state_from`: the last close is beyond the most recent confirmed swing high (low) and no close has broken the other
    swing since [our interpretation of "rally / consolidate / fall"]. None = no DXY data."""
    key = ("st", i)
    cache = ctx.__dict__.setdefault("_cg3_cache", {})
    if key in cache:
        return cache[key]
    b = _day_bars(ctx, i, 5, _hhmm(p.dxy_state_from))
    res = None
    if b is not None and len(b) >= 3:
        h, l, c = b.high.values, b.low.values, b.close.values
        sh, sl = _swing_idx(h, True), _swing_idx(l, False)
        res = 0
        if sh and c[-1] > h[sh[-1]] and not (sl and (c[sl[-1] + 1:] < l[sl[-1]]).any()):
            res = 1
        elif sl and c[-1] < l[sl[-1]] and not (sh and (c[sh[-1] + 1:] > h[sh[-1]]).any()):
            res = -1
    cache[key] = res
    return res


# ---- item 4: the session gate levels (031 ~7:54, ~15:17) -----------------------------------------------------------------------------

def dxy_sess_state(ctx, i: int, p) -> int | None:
    """+1 = the bearish-ES case holds (DXY above its 00:00-09:30 key support and the bullish 15m FVG beneath it): ES longs blocked; 0 once DXY closed (15m body) below the FVG's low; -1 = DXY
    displaced through the support after that (ES decisively bullish): ES shorts blocked. The mirror case (DXY under its key resistance and a bearish FVG above) gives -1 -> 0 -> +1. None = not set (before
    09:30, no array, no DXY data)."""
    key = ("sess", i)
    cache = ctx.__dict__.setdefault("_cg3_cache", {})
    if key in cache:
        return cache[key]
    res = None
    tf = 15
    mark = pd.Timestamp(ctx.day, tz=NY) + pd.Timedelta(hours=9, minutes=30)
    if _t_end(ctx, i) > mark:
        b = _day_bars(ctx, i, tf, 0)
        if b is not None:
            pre, post = b[b.end <= mark], b[b.end > mark]
            if len(pre) >= 3:
                h, l, c = pre.high.values, pre.low.values, pre.close.values
                px = c[-1]
                cases = []
                sl = _swing_idx(l, False)
                if sl:
                    s_ = float(l[sl[-1]])
                    for j in range(len(pre) - 1, 1, -1):               # the nearest unfilled bullish FVG below price
                        if h[j - 2] < l[j] and h[j - 2] < px and (j + 1 >= len(pre) or float(l[j + 1:].min()) > h[j - 2]):
                            cases.append((px - float(l[j]), 1, s_, float(h[j - 2])))
                            break
                sh = _swing_idx(h, True)
                if sh:
                    r_ = float(h[sh[-1]])
                    for j in range(len(pre) - 1, 1, -1):               # the nearest unfilled bearish FVG above price
                        if l[j - 2] > h[j] and l[j - 2] > px and (j + 1 >= len(pre) or float(h[j + 1:].max()) < l[j - 2]):
                            cases.append((float(h[j]) - px, -1, r_, float(l[j - 2])))
                            break
                if cases:
                    _, sg, lvl, arr = min(cases)
                    cc = post.close.values
                    st = sg
                    broke = False
                    for v in cc:
                        if sg > 0:
                            if not broke and v < arr:
                                broke, st = True, 0
                            elif broke and v < lvl:
                                st = -1
                        else:
                            if not broke and v > arr:
                                broke, st = True, 0
                            elif broke and v > lvl:
                                st = 1
                    res = st
    cache[key] = res
    return res


# ---- item 5: the 5m dealing-range EQ (045 ~42:00) --------------------------------------------------------------------------------------

def dxy_eq_state(ctx, i: int, p) -> int | None:
    """+1 = DXY closed above the EQ of its down-leg range (no ES longs); -1 = DXY closed below the EQ of its up-leg range (no ES shorts); 0 otherwise. The range = the latest 5m swing high and the swing
    low after it (a down leg), or the mirror; `dxy_range_from` "0830" / "0930" = the range from that time to now instead of the swings. None = no data."""
    key = ("eq", i)
    cache = ctx.__dict__.setdefault("_cg3_cache", {})
    if key in cache:
        return cache[key]
    res = None
    frm = {"swings": 0, "0830": 510, "0930": 570}[p.dxy_range_from]
    b = _day_bars(ctx, i, 5, frm)
    if b is not None and len(b) >= 4:
        h, l, c = b.high.values, b.low.values, b.close.values
        if p.dxy_range_from == "swings":
            sh, sl = _swing_idx(h, True), _swing_idx(l, False)
            if sh and sl:
                down = sl[-1] > sh[-1]
                top, bot = float(h[sh[-1]]), float(l[sl[-1]])
                if top > bot:
                    eq = (top + bot) / 2
                    res = 1 if (down and c[-1] > eq) else (-1 if (not down and c[-1] < eq) else 0)
        else:
            top, bot = float(h.max()), float(l.min())
            down = int(np.argmin(l)) > int(np.argmax(h))
            eq = (top + bot) / 2
            res = 1 if (down and c[-1] > eq) else (-1 if (not down and c[-1] < eq) else 0)
    cache[key] = res
    return res


# ---- item 6: the 09:15-09:30 range trigger (042 ~19:00, ~23:30, ~41:41) ------------------------------------------------------------------

def dxy_range_state(ctx, i: int, p) -> int | None:
    """+1 = an ES short may fill (DXY traded above its 09:15-09:30 range high after 09:30 and has not closed a 1m body under its nearest bullish 1m FVG since); -1 = an ES long may fill (the mirror);
    0 = neither. `dxy_range_trigger="break_only"` ignores the FVG hold. None = no data. (1m `line` bars have no volume imbalances, only FVGs.)"""
    key = ("rng", i)
    cache = ctx.__dict__.setdefault("_cg3_cache", {})
    if key in cache:
        return cache[key]
    res = None
    a0, a1 = (_hhmm(x) for x in p.dxy_range_win)
    b = _day_bars(ctx, i, 1, a0)
    if b is not None:
        day0 = pd.Timestamp(ctx.day, tz=NY)
        rng = b[(b.index >= day0 + pd.Timedelta(minutes=a0)) & (b.end <= day0 + pd.Timedelta(minutes=a1))]
        post = b[b.index >= day0 + pd.Timedelta(minutes=a1)]
        if len(rng) >= 5:
            hi, lo = float(rng.high.max()), float(rng.low.min())
            sup_dn = sup_up = None
            up_armed = dn_armed = False
            dead_up = dead_dn = False                       # a cancelled side re-arms only after DXY has come back inside the range (a NEW run beyond it)
            h, l, c = post.high.values, post.low.values, post.close.values
            for k in range(len(post)):
                if c[k] <= hi:
                    dead_up = False
                if c[k] >= lo:
                    dead_dn = False
                if c[k] > hi and not dead_up:
                    if not up_armed:
                        sup_up = None
                    up_armed, dn_armed = True, False
                elif c[k] < lo and not dead_dn:
                    if not dn_armed:
                        sup_dn = None
                    dn_armed, up_armed = True, False
                if k >= 2 and l[k] > h[k - 2] and up_armed:
                    sup_up = float(h[k - 2])
                if k >= 2 and h[k] < l[k - 2] and dn_armed:
                    sup_dn = float(l[k - 2])
                if p.dxy_range_trigger != "break_only":
                    if up_armed and sup_up is not None and c[k] < sup_up:
                        up_armed, sup_up, dead_up = False, None, True
                    if dn_armed and sup_dn is not None and c[k] > sup_dn:
                        dn_armed, sup_dn, dead_dn = False, None, True
            res = 1 if up_armed else (-1 if dn_armed else 0)
    cache[key] = res
    return res


# ---- item 11 (extend): the DXY leg of sym_swing_ts ---------------------------------------------------------------------------------------

def dxy_confirms(ctx, sd, i: int, p) -> bool:
    """`sym_swing_dxy`: DXY made the opposite session extreme (for an ES low: a new DXY high; for an ES high: a new low) within the last `sym_win` 5m bars of the closed bar i, from 07:00 (the pre-open
    swings). No DXY data = the extra condition is not applied (True)."""
    b = _day_bars(ctx, i, 5, 7 * 60)
    if b is None or len(b) < p.sym_win + 3:
        return True
    w = p.sym_win + 1
    if sd.sign > 0:              # ES made a low -> DXY a high
        return bool(b.high.values[-w:].max() > b.high.values[:-w].max())
    return bool(b.low.values[-w:].min() < b.low.values[:-w].min())


# ---- hooks ---------------------------------------------------------------------------------------------------------------------------------

def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """Entry gates of items 1, 4, 5, 6 (funnel keys x_cg_dxy_*; tags dxy_* / dxy_na)."""
    if p.dxy_states == p.dxy_session_gate == p.dxy_eq_gate == p.dxy_range_trigger == "off":
        return None
    S = _S()
    tag = lambda t: S._CG1._tag(o, t)
    sg = sd.sign
    if p.dxy_states != "off":
        st = dxy_state(ctx, i, p)
        if st is None:
            tag("dxy_na")
        else:
            tag({1: "dxy_up", -1: "dxy_dn", 0: "dxy_flat"}[st])
            if p.dxy_states in ("filter", "soft") and st == sg:                  # a rallying dollar: no ES longs (a falling one: no shorts); soft = a half-risk scalp instead (scalp_now / size_mult)
                if p.dxy_states == "filter":
                    hit("dxy_state_block")
                    return "x_cg_dxy_state"
    if p.dxy_session_gate != "off":
        st = dxy_sess_state(ctx, i, p)
        if st:
            tag("dxy_sess_" + ("up" if st > 0 else "dn"))
            if p.dxy_session_gate in ("filter", "bias") and st == sg:
                hit("dxy_sess_block")
                return "x_cg_dxy_sess"
    if p.dxy_eq_gate != "off":
        st = dxy_eq_state(ctx, i, p)
        if st:
            tag("dxy_eq_up" if st > 0 else "dxy_eq_dn")
            if p.dxy_eq_gate in ("block", "block_short_model") and st == sg:
                hit("dxy_eq_block")
                return "x_cg_dxy_eq"
    if p.dxy_range_trigger != "off" and session == "AM":
        st = dxy_range_state(ctx, i, p)
        if st is not None:
            tag("dxy_rng_ok" if st == -sg else "dxy_rng_wait")
            if p.dxy_range_trigger in ("gate", "break_only") and st != -sg:         # an ES short (sg < 0) needs st == +1; a long st == -1
                hit("dxy_range_wait")
                return "x_cg_dxy_range"
    return None


def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """dxy_states: a consolidating dollar (0) = longs / shorts only as small intraday scalps; "soft": a rally (for longs) is a half-risk scalp too."""
    if p.dxy_states in ("filter", "soft") and i is not None and sign:
        st = dxy_state(ctx, i, p)
        if st == 0 or (p.dxy_states == "soft" and st == sign):
            hit("dxy_state_scalp")
            return "cg_dxy_state"
    return ""


def size_mult(ctx, sd, i: int, p, lvt: list) -> float:
    if p.dxy_states == "soft" and dxy_state(ctx, i, p) == sd.sign:
        lvt.append("size_dxy_soft")
        return 0.5
    return 1.0
