"""Caption-gap pass, package bias_htf#1/7 (digests/rulebook_gaps/bias_htf_intermarket.md) - ENGINE SIDE.

The bar-loop part of the 35 specs: side gates, the draw-lock adjustments (at the lock and per bar), the scalp / size / target hooks, the order tags. The daily / weekly columns and the flip triggers
they read are built by `bh1.py` inside `htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column or a completed hist session.
Hooks (who calls them)
  side_ok          daycontext.side_ok tail        drange side gate, bellwether_tf, iof_tf, org_gap_filter, org_tell_seq, wk_po3, dxy_filter (sets the per-side flags the later hooks read)
  order_ok         daycontext.order_ok tail       no_htf_top_pick, counter-trend MSS, min_criteria bodies, tags
  scalp_now        daycontext.scalp_now tail      drange_scalp, neutral_lean, org_consol_case, dxy soft  (scalp_cap: the cap distance / level)
  size_mult        bias_day.size_mult             dxy_filter "soft": dxy_soft_risk
  want_adjust      bias_day.want_at               neutral_lean, org_tell_seq: the bias side
  targets_post     strategy._targets              wk_high_in_gate, stack_far (draw_mid_lvl rung)
  lock_cands / lock_post / tiebreak   strategy.mark_levels   the lock candidates and the lock adjustments at the lock time
  lock_bar         strategy._lock_step            per-bar lock changes: invalidation touch, 60m BISI hold, raid gap guard, 50/50 re-lock, low-in re-lock, counter-trend reopen
  counter_kind     strategy.run_day               allow_counter_trend: the counter-bias trade after the delivered draw
  after_close      strategy._after_close          drange_scalp: the day's points / wins
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from . import levels as L

HITS: Counter = Counter()
INVAL_FILE = Path("data/mentorship/inval_levels.csv")        # BH-B8-pre-stated-invalidation-price: date, session, price


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    from . import strategy as S
    return S


def _BD():
    from . import bias_day as BD
    return BD


def _c(ctx) -> dict:
    return ctx.__dict__.setdefault("_bh1e", {})


def on(p) -> bool:
    """Any engine-side bias_htf#1/7 switch is on (the hooks return at once otherwise)."""
    return bool(p.drange_scalp or p.wk_high_in_gate or p.bisi60_draw or p.neutral_lean or p.ceiling_ladder or p.bpr_lean or p.raid_gap_guard or p.inval_src != "off"
                or p.bellwether_tf or p.org_gap_filter or p.org_tell_seq or p.org_consol_case or p.dxy_filter != "off" or p.low_in_relock or p.fifty_rel or p.iof_tf
                or p.allow_counter_trend or p.draw_order == "nearest_tb" or p.stack_far or p.no_htf_top_pick or p.min_criteria or p.wk_po3 or p.run_extreme_lean
                or p.pwh_giveback_draw or p.bisi60_hold != "off" or p.wick_ce_draw)


def lock_on(p) -> bool:
    """The per-bar lock hook has work."""
    return bool(p.inval_src != "off" or p.bisi60_hold != "off" or p.raid_gap_guard or p.fifty_rel or p.low_in_relock or p.allow_counter_trend)


def _row(ctx, session: str, i: int):
    return _BD().row_for(ctx, session, i)


def _n(row, key: str, default: int = 0) -> int:
    if row is None:
        return default
    v = row.get(key)
    try:
        return default if v is None or v != v else int(v)
    except Exception:
        return default


def _f(row, key: str) -> float:
    if row is None:
        return float("nan")
    v = row.get(key)
    try:
        return float("nan") if v is None else float(v)
    except Exception:
        return float("nan")


def _state(ctx) -> dict:
    return getattr(ctx, "state7", None) or {}


# --------------------------------------------------------------------------------------------------------------
# per-side flags (side_ok sets them; scalp_now / size_mult / order_ok read them)
# --------------------------------------------------------------------------------------------------------------

def _set_flags(ctx, sign: int, i: int) -> set:
    fl: set = set()
    ctx.__dict__.setdefault("_bh1_fl", {})[sign] = (i, fl)
    return fl


def flags(ctx, sign: int, i) -> set:
    r = getattr(ctx, "_bh1_fl", {}).get(sign)
    return r[1] if (r is not None and r[0] == i) else set()


# --------------------------------------------------------------------------------------------------------------
# bars of a coarser timeframe from the engine frame (closed bars only)
# --------------------------------------------------------------------------------------------------------------

def tf_bars(ctx, m: int) -> dict:
    """The clock-aligned m-minute bars of the frame (previous session + today): o h l c, first / last base index, and `full` = the bar ends on an m-minute boundary. A bar is COMPLETE at base bar i
    when last <= i and full (see `tf_complete`) - a group's aggregate then only contains base bars <= i."""
    c = _c(ctx)
    key = ("tf", m)
    if key not in c:
        idx = ctx.idx
        dkey = idx.year.values.astype(np.int64) * 400 + idx.dayofyear.values
        g = dkey * 100000 + (ctx.t // m)
        starts = np.flatnonzero(np.r_[True, g[1:] != g[:-1]])
        ends = np.r_[starts[1:], len(g)] - 1
        c[key] = dict(o=ctx.o[starts], h=np.maximum.reduceat(ctx.h, starts), l=np.minimum.reduceat(ctx.l, starts), c=ctx.c[ends], first=starts, last=ends,
                      full=((ctx.t[ends] + ctx.tf) % m == 0))
    return c[key]


def tf_complete(ctx, m: int, i: int) -> dict:
    """The complete m-minute bars at closed base bar i (arrays o h l c first last)."""
    b = tf_bars(ctx, m)
    n = int(np.searchsorted(b["last"], i, side="right"))
    keep = np.flatnonzero(b["full"][:n])
    return {k: v[keep] for k, v in b.items() if k != "full"}


def iof_state(o, h, l, c) -> int:
    """BH-B6-intraday-iof (028 ~00:21:27; 085 ~00:10:28; 099 ~00:15:03; OHLC only): the order flow of the bars given. Walk the bars: a close above the high of the LAST up-close candle is a bullish event
    (+1 - a down-close candle that held as support, an up-close one run through), a close below the low of the last down-close candle a bearish event (-1); the state is the last event and holds until
    the opposite one ('it ends when price trades and holds above the last up-close candle'). 0 before any event. The linger / close thresholds are our parameters (none: closes decide)."""
    up_hi = dn_lo = None
    st = 0
    for j in range(len(c)):
        if up_hi is not None and c[j] > up_hi:
            st = 1
        elif dn_lo is not None and c[j] < dn_lo:
            st = -1
        if c[j] > o[j]:
            up_hi = h[j]
        elif c[j] < o[j]:
            dn_lo = l[j]
    return st


def iof_dir(ctx, m: int, i: int) -> int:
    b = tf_complete(ctx, m, i)
    return iof_state(b["o"], b["h"], b["l"], b["c"]) if len(b["c"]) else 0


def swing_break_dir(o, h, l, c) -> int:
    """BH-B5-bellwether: the direction of the last swing break on the bars given: the latest close above the last confirmed 3-candle pivot high (+1) or below the last pivot low (-1)."""
    ph, pl = L.pivots(h, l, 1)
    hi = lo = None
    a = b = 0
    st = 0
    for j in range(len(c)):
        if hi is not None and c[j] > hi:
            st = 1
        elif lo is not None and c[j] < lo:
            st = -1
        while a < len(ph) and ph[a].known <= j:
            hi = ph[a].price
            a += 1
        while b < len(pl) and pl[b].known <= j:
            lo = pl[b].price
            b += 1
    return st


def bellwether_dir(ctx, m: int, i: int) -> int:
    b = tf_complete(ctx, m, i)
    return swing_break_dir(b["o"], b["h"], b["l"], b["c"]) if len(b["c"]) >= 3 else 0


# --------------------------------------------------------------------------------------------------------------
# the daily arrays of the completed sessions (hist)
# --------------------------------------------------------------------------------------------------------------

def daily_arrays(ctx) -> list:
    """Alive daily FVGs of the completed history sessions (regular-session candles): SimpleNamespace(kind, top, bottom, ce, i). Alive = no later close through the far side."""
    c = _c(ctx)
    if "darr" not in c:
        hist = getattr(ctx, "hist", None) or []
        out = []
        if len(hist) >= 3:
            o = np.array([float(x.open.iloc[0]) for x in hist])
            h = np.array([float(x.high.max()) for x in hist])
            l = np.array([float(x.low.min()) for x in hist])
            cl = np.array([float(x.close.iloc[-1]) for x in hist])
            for z in L.fvgs(h, l, o, cl):
                later = cl[z.i + 1:]
                if z.kind == "bull" and (not len(later) or later.min() >= z.bottom):
                    out.append(SimpleNamespace(kind="bull", top=float(z.top), bottom=float(z.bottom), ce=float(z.mid), i=z.i))
                elif z.kind == "bear" and (not len(later) or later.max() <= z.top):
                    out.append(SimpleNamespace(kind="bear", top=float(z.top), bottom=float(z.bottom), ce=float(z.mid), i=z.i))
        c["darr"] = out
    return c["darr"]


# --------------------------------------------------------------------------------------------------------------
# the ORG tell with its sequence (item 21)
# --------------------------------------------------------------------------------------------------------------

def org_tell_dir(ctx, p, i: int) -> int:
    """BH-B15-ORG-tell-details (030 ~01:29:44), judged at org_tell_end (10:00): the gap down (up) made no meaningful attempt back toward the prior close in 09:30 + org_tell_skip_min .. 10:00 (the high
    stayed under op + org_attempt_frac x the gap), AND a displacement bar has closed below the CE and then below the low of the prior session's last bear-side (bull for a gap up) FVG under the open.
    Returns -1 / +1 (very bearish / bullish) from the bar that completes the sequence (not before the window is over), else 0. [our interpretation: 'with speed' = the displacement test with
    displacement_mult (1.0 when it is 0); the FVG is the latest one of the prior session on the way down (the gap-down case needs one below the open)]."""
    if not (getattr(ctx, "org_today", False) and getattr(ctx, "org", None)):
        return 0
    S = _S()
    k0 = S._idx_at(ctx, 570)
    ka = S._idx_at(ctx, 570 + p.org_tell_skip_min)
    kend = S._idx_at(ctx, p.org_tell_end)
    if i < kend - 1 or ka >= kend:
        return 0
    c = _c(ctx)
    key = ("orgtell", i)
    if key in c:
        return c[key]
    pc, op = ctx.org[-1]
    gap = pc - op
    out = 0
    if abs(gap) >= 0.25 * p.es_pt:
        sgn = -1 if gap > 0 else 1
        win_ext = float(ctx.h[ka:kend].max()) if gap > 0 else float(ctx.l[ka:kend].min())
        attempt = (win_ext - op) if gap > 0 else (op - win_ext)
        if attempt < p.org_attempt_frac * abs(gap):
            hist = getattr(ctx, "hist", None) or []
            if hist:
                pr = hist[-1]
                zs = [z for z in L.fvgs(pr.high.values.astype(float), pr.low.values.astype(float), pr.open.values.astype(float), pr.close.values.astype(float))
                      if z.kind == ("bear" if gap > 0 else "bull") and ((z.top < op) if gap > 0 else (z.bottom > op))]
                if zs:
                    z = zs[-1]
                    mult = p.displacement_mult or 1.0
                    thru = False
                    for j in range(ka, i + 1):
                        if (gap > 0 and ctx.c[j] < z.mid) or (gap < 0 and ctx.c[j] > z.mid):
                            thru = True
                        beyond = (ctx.c[j] < z.bottom) if gap > 0 else (ctx.c[j] > z.top)
                        if thru and beyond:
                            prev = np.abs(ctx.c[max(0, j - 10):j] - ctx.o[max(0, j - 10):j])
                            body = abs(ctx.c[j] - ctx.o[j])
                            if len(prev) == 0 or body >= mult * float(prev.mean()):
                                out = sgn
                                break
    c[key] = out
    return out


# --------------------------------------------------------------------------------------------------------------
# neutral lean (item 6)
# --------------------------------------------------------------------------------------------------------------

def _lean_raided(ctx, lean: int, i: int) -> bool:
    """A raid of the prior day's high (lean short) / low (lean long), or of the Tuesday extreme on a later day of the week, through bar i [our interpretation: 'a nearby key level' is not read]."""
    if lean == 0:
        return False
    levels = []
    k = "pdh1" if lean < 0 else "pdl1"
    if k in ctx.pd:
        levels.append(ctx.pd[k])
    hist = getattr(ctx, "hist", None) or []
    d = ctx.day
    if d.weekday() >= 2:
        for x in hist:
            xd = x.index[0].date()
            if xd.weekday() == 1 and xd.isocalendar()[:2] == d.isocalendar()[:2]:
                levels.append(float(x.high.max()) if lean < 0 else float(x.low.min()))
    if not levels:
        return False
    if lean < 0:
        return bool(ctx.h[ctx.start:i + 1].max() > min(levels))
    return bool(ctx.l[ctx.start:i + 1].min() < max(levels))


def want_adjust(ctx, p, session: str, i: int, base: int) -> int:
    """bias_day.want_at tail: BH-B17-neutral-lean (a neutral bias takes the table's lean) and BH-B15-ORG-tell-details (a confirmed tell is the AM bias)."""
    if p.org_tell_seq and ctx.t[i] < 720:
        t_ = org_tell_dir(ctx, p, i)
        if t_:
            hit("org_tell_want")
            return t_
    if p.neutral_lean and base == 0:
        ln = _n(_row(ctx, session, i), "lean")
        if ln:
            hit("lean_want")
            return ln
    return base


# --------------------------------------------------------------------------------------------------------------
# the side gate
# --------------------------------------------------------------------------------------------------------------

def _bias_known(ctx, p, session: str, i: int, row) -> bool:
    if p.htf_bias != "off" and _BD().want_at(ctx, p, session, i):
        return True
    return bool(_n(row, "wk_dir") or _n(row, "wk_bias") or getattr(ctx, "wbias", 0))


def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#1/7 reason, else None. Sets the per-side flags (counter_dxy ...)."""
    if not on(p) or i is None:
        return None
    fl = _set_flags(ctx, sign, i)
    row = _row(ctx, session, i)
    st = _state(ctx)
    # item 24: the dollar
    if p.dxy_filter != "off":
        dx = int((getattr(ctx, "intermarket", None) or {}).get("dxy", 0) or 0)
        if dx and ((sign > 0 and dx > 0) or (sign < 0 and dx < 0)):
            if p.dxy_filter == "hard":
                return "x_bh1_dxy"
            fl.add("counter_dxy")
        elif dx:
            fl.add("dxy_ok")
    # item 1: the daily consolidation regime
    if p.drange_scalp and row is not None:
        if _n(row, "drange_in"):
            if st.get("bh1_dr_done"):
                return "x_bh1_drange_done"
            s_ = st.get("bh1_dr_side")
            if s_ and sign != s_:
                return "x_bh1_drange_side"
        else:
            br = _n(row, "drange")
            if br and sign != br:
                return "x_bh1_drange_break"
    # item 64: the weekly PO3
    if p.wk_po3 and row is not None:
        v = _n(row, "wk_po3")
        if v and sign == -v:
            return "x_bh1_wk_po3"
    # item 18: the bellwether chart
    if p.bellwether_tf:
        m = p.bellwether_tf
        if m == 15 and not _bias_known(ctx, p, session, i, row):
            m = 60
        sd_ = bellwether_dir(ctx, m, i)
        if sd_ and sd_ != sign:
            return "x_bh1_bellwether"
    # item 43: the intraday order flow
    if p.iof_tf:
        sd_ = iof_dir(ctx, p.iof_tf, i)
        if sd_ and sd_ != sign:
            return "x_bh1_iof"
    S = _S()
    # item 20: a gap with the bias against it needs a reason
    if p.org_gap_filter and getattr(ctx, "org_today", False) and getattr(ctx, "org", None) and i >= S._idx_at(ctx, 570):
        pc, op = ctx.org[-1]
        if abs(op - pc) >= 0.25 * p.es_pt:
            blocked = -1 if op < pc else 1
            if sign == blocked:
                dx = int((getattr(ctx, "intermarket", None) or {}).get("dxy", 0) or 0)
                ok_a = _n(row, "flip") == blocked and dx == -blocked
                if not ok_a and S._org_break(ctx, p, i) is not True:
                    return "x_bh1_org_gap"
                hit("org_gap_exception")
    # item 21: the confirmed ORG tell (the AM rest)
    if p.org_tell_seq and ctx.t[i] < 720:
        t_ = org_tell_dir(ctx, p, i)
        if t_ and sign != t_:
            return "x_bh1_org_tell"
    return None


# --------------------------------------------------------------------------------------------------------------
# scalps and sizes
# --------------------------------------------------------------------------------------------------------------

def _org_filled(ctx, i: int) -> bool:
    """Today's ORG filled through bar i: price reached the prior RTH close (the gap's far edge)."""
    if not (getattr(ctx, "org_today", False) and getattr(ctx, "org", None)):
        return False
    S = _S()
    k0 = S._idx_at(ctx, 570)
    if i < k0:
        return False
    pc, op = ctx.org[-1]
    if pc == op:
        return False
    return bool(ctx.h[k0:i + 1].max() >= pc) if pc > op else bool(ctx.l[k0:i + 1].min() <= pc)


def _consolidating(row) -> bool:
    return bool(_n(row, "obj_day") or _n(row, "obj_week") or _n(row, "drange_in") or (row is not None and row.get("nwog_regime") == "cons"))


def scalp_now(ctx, p, session: str, i, sign: int = 0) -> str:
    """The bias_htf#1/7 reason an order of `session` is a scalp (one exit, no adds), else ''."""
    if not on(p) or i is None:
        return ""
    row = _row(ctx, session, i)
    if p.drange_scalp and _n(row, "drange_in"):
        return "bh1_drange"
    if p.neutral_lean and row is not None and sign:
        base = _BD().bias_value(row, p) if p.htf_bias != "off" else 0
        ln = _n(row, "lean")
        if p.htf_bias != "off" and base == 0 and ln == sign and not _lean_raided(ctx, ln, i):
            return "bh1_lean"
    if p.org_consol_case and sign and _consolidating(row) and _org_filled(ctx, i):
        return "bh1_org_consol"
    if p.dxy_filter == "soft" and sign and "counter_dxy" in flags(ctx, sign, i):
        return "bh1_counter_dxy"
    return ""


def scalp_cap(ctx, sd, i: int, p, dws: str, entry: float, first: float):
    """The scalp's target (side space) for the bias_htf#1/7 reasons, or None (the caller's default min(+sloppy_scalp_pts, T1))."""
    if dws == "bh1_drange":
        return min(entry + p.drange_t1_pts * p.es_pt, first)
    if dws == "bh1_org_consol":
        pc, op = ctx.org[-1]
        far = max(sd.x(pc), sd.x(op))
        ce = sd.x((pc + op) / 2)
        cap = far if far > entry else (ce if ce > entry else first)
        return min(first, cap)
    return None


def size_mult(ctx, sd, i: int, p, lvt: list) -> float:
    """BH-B19-DXY-soft-filter-for-indices: a counter-dollar index order trades at dxy_soft_risk x the risk (dxy_filter 'soft')."""
    if p.dxy_filter == "soft" and "counter_dxy" in flags(ctx, sd.sign, i):
        lvt.append("size_counter_dxy")
        return p.dxy_soft_risk
    return 1.0


# --------------------------------------------------------------------------------------------------------------
# per-order rules and tags
# --------------------------------------------------------------------------------------------------------------

TOP_KINDS = ("pm_reversal", "cc_failure_swing", "hs_fade", "reaper", "reaper_ob")


def _is_top_pick(o: dict) -> bool:
    """A turtle-soup / three-drives / reversal entry (the setups that pick a high or a low)."""
    from . import sm7 as _SM7
    tags = str(o.get("lv_tags") or "")
    return bool(_SM7.is_ts_kind(o) or "three_drives" in tags or "reversal" in tags or str(o.get("entry_kind") or "") in TOP_KINDS)


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` (side space) breaks a bias_htf#1/7 rule, else None. Adds tags to o['lv_tags']."""
    if not on(p):
        return None
    tags: list = []
    row = _row(ctx, session, i)
    # item 57: no HTF top / bottom picking
    if p.no_htf_top_pick and row is not None and _is_top_pick(o):
        fl = _n(row, "flip")
        met = bool(_n(row, "obj_day") or _n(row, "obj_week"))
        if fl == -sd.sign and not met:
            return "x_bh1_top_pick"
    # item 44: the counter-trend trade needs a MSS after the raid
    if "counter_trend" in str(o.get("lv_tags") or ""):
        lk = ctx.lock.get(session) if getattr(ctx, "lock", None) else None
        di = (lk or {}).get("delivered_i")
        if di is not None and (o.get("broke") is None or o["broke"] <= di):
            return "x_bh1_ct_mss"
        tags.append("counter_trend")
    # item 59: the bodies after the minimum criteria stay beyond the array MT
    lk = (getattr(ctx, "lock", None) or {}).get(session)
    if lk is not None and lk.get("mc") and lk["side"] == sd.sign:
        mc = lk["mc"]
        k3 = mc.get("k3")
        if k3 is not None and i > k3:
            bodies = np.minimum(ctx.o[k3 + 1:i + 1], ctx.c[k3 + 1:i + 1]) if sd.sign > 0 else np.maximum(ctx.o[k3 + 1:i + 1], ctx.c[k3 + 1:i + 1])
            if len(bodies) and ((bodies.min() < mc["mt"]) if sd.sign > 0 else (bodies.max() > mc["mt"])):
                return "x_bh1_min_criteria"
        tags.append("min_criteria")
    # tags from the lock and the flags
    if lk is not None and lk.get("bh1") and lk["side"] == sd.sign:
        tags += [t for t in lk["bh1"]]
    fl = flags(ctx, sd.sign, i)
    if p.dxy_filter in ("tag", "soft") and fl:
        tags += [t for t in ("counter_dxy", "dxy_ok") if t in fl]
    if p.pwh_giveback_draw and _n(row, "pwh_giveback"):
        tags.append("pwh_giveback")
    if p.org_consol_case and _consolidating(row) and _org_filled(ctx, i):
        tags.append("org_consol")
    if p.neutral_lean and row is not None and p.htf_bias != "off" and _BD().bias_value(row, p) == 0 and _n(row, "lean") == sd.sign:
        tags.append("neutral_lean")
    if tags:
        o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


# --------------------------------------------------------------------------------------------------------------
# targets (strategy._targets)
# --------------------------------------------------------------------------------------------------------------

def targets_on(p) -> bool:
    return bool(p.wk_high_in_gate or p.stack_far or p.org_tell_seq)


def org_tell_ladder(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """BH-B15-ORG-tell-details (030 ~01:29:44): after a confirmed ORG tell in the trade's direction the targets are the discount arrays in timeframe order - the nearest untraded 15m array, then the 1h, then the
    daily one - as rungs (their CE). [our interpretation: each timeframe contributes its nearest array beyond the previous rung, so a higher-timeframe array lying NEARER than the lower one's is out of the order and is skipped]."""
    cf = getattr(ctx, "conf", None)
    if cf is None or org_tell_dir(ctx, p, i) != sd.sign:
        return lv
    import pandas as pd
    from . import bias_day as BD
    now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=int(ctx.t[i] + ctx.tf))
    px = float(ctx.c[i])
    last = above
    add = []
    for tf in ("15m", "1h", "D"):
        rows = BD.untraded_arrays(ctx, i, now, px, sd.sign, (tf,), (0,), p.array_reuse != "first_touch")
        ces = sorted(sd.x(r[1]) for r in rows if sd.x(r[1]) > above)
        nxt = next((v for v in ces if v > last), None)        # the nearest array of this timeframe beyond the previous rung
        if nxt is not None:
            add.append((nxt, "array"))
            last = nxt
    if add:
        hit("org_tell_ladder")
    return list(lv) + add




def _week_extreme(ctx, sign: int, i: int):
    """The current week's high (sign > 0) / low so far through bar i: the completed sessions of this ISO week plus today's bars."""
    d = ctx.day
    wk = d.isocalendar()[:2]
    hist = getattr(ctx, "hist", None) or []
    vals = [float(x.high.max()) if sign > 0 else float(x.low.min()) for x in hist if x.index[0].date().isocalendar()[:2] == wk and x.index[0].date() < d]
    vals.append(float(ctx.h[ctx.start:i + 1].max()) if sign > 0 else float(ctx.l[ctx.start:i + 1].min()))
    return max(vals) if sign > 0 else min(vals)


def targets_post(ctx, sd, i: int, p, above: float, lv: list) -> list:
    """BH-B7-last-daily-OB-guard (wk_high_in_gate): the week's high is in - no long target above it (mirror: the week's low); BH-B2-two-HTF-FVGs-farther: the nearer stacked gap's near edge is a partial rung."""
    if p.org_tell_seq:
        lv = org_tell_ladder(ctx, sd, i, p, above, lv)
    session = getattr(ctx, "cur_session", "") or ("PM" if ctx.t[i] >= 810 else "AM")
    row = _row(ctx, session, i)
    if row is None:
        return lv
    if p.wk_high_in_gate:
        flag = _n(row, "wk_high_in") if sd.sign > 0 else _n(row, "wk_low_in")
        if flag:
            ext = sd.x(_week_extreme(ctx, sd.sign, i))
            kept = [(v, k) for v, k in lv if v <= ext + 1e-9]
            if len(kept) != len(lv):
                hit("wk_high_in_trim")
            lv = kept
    if p.stack_far:
        mid = _f(row, "draw_mid_lvl")
        if mid == mid and _n(row, "draw_ord") == sd.sign and sd.x(mid) > above:
            lv = list(lv) + [(sd.x(mid), "array")]
            hit("stack_far_rung")
    return lv


# --------------------------------------------------------------------------------------------------------------
# the draw lock: candidates, the pick tie-break, the adjustments at the lock time
# --------------------------------------------------------------------------------------------------------------

def lock_cands(ctx, p, row, t_lock: int, start: int) -> list:
    """Extra lock candidates (v, kind, name, dir, created): the weekly BISI CE after a PWH run-and-give-back, the wick CE draw / its extreme."""
    out = []
    if row is None:
        return out
    if p.pwh_giveback_draw and _n(row, "pwh_giveback"):
        v = _f(row, "pwh_cand")
        if v == v:
            out.append((v, "array", "pwh_bisi_ce", 0, start))
    if p.wick_ce_draw and row.get("draw_ord_kind") == "wick":
        v, e = _f(row, "draw_ord_lvl"), _f(row, "draw_ext_lvl")
        if v == v:
            out.append((v, "array", "wick_ce_draw", 0, start))
        if e == e:
            out.append((e, "array", "wick_ext", 0, start))
    return out


def arrays_between(ctx, p, now, px: float, sgn: int, v: float) -> int:
    """BH-B2-draw-by-proximity: the opposing HTF arrays (bear FVG / OB above the price for sgn > 0, bull below for sgn < 0; 15m, 1h, 4h, D) known at `now` whose near edge lies strictly between the price
    and the level `v` - the resistance in the path of the draw [our interpretation: "least resistance in the path" = fewest opposing arrays in between]."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return 0
    n = 0
    for r in cf.opposing_ext(now, px, sgn, ("15m", "1h", "4h", "D"), (0, 1)):
        near = r["bottom"] if sgn > 0 else r["top"]
        if (px < near < v) if sgn > 0 else (v < near < px):
            n += 1
    return n


def tiebreak(up: list, dn: list, mk: list, cands: list, between=None) -> int:
    """BH-B2-draw-by-proximity (draw_order 'nearest_tb'): two candidates within eq_tol of the same distance - the one with fewer opposing arrays between the price and it wins, then the one that formed later.
    Items are (distance, level, kind, name, dir); `mk` = all marked items, `cands` = (v, kind, name, dir, created); `between(sgn, item)` = the number of opposing arrays in the path (default: none counted)."""
    cr = {(round(v, 9), k): c_ for v, k, n, d_, c_ in cands}
    a, b = up[0], dn[0]
    na = between(1, a) if between else 0
    nb = between(-1, b) if between else 0
    if na != nb:
        return 1 if na < nb else -1
    ca, cb = cr.get((round(a[1], 9), a[2]), 0), cr.get((round(b[1], 9), b[2]), 0)
    if ca != cb:
        return 1 if ca > cb else -1
    hit("tiebreak_tie")
    return 1 if a[0] <= b[0] else -1


def _nearest(lock: dict, px: float, side: int, mn: float, kinds=("pool",)):
    """The nearest marked level on `side` of px at least mn away (kind in kinds, or any when kinds is None): (v, kind, name, dir) or None."""
    best = None
    for v, k, n, dr in lock.get("marked", ()):
        if kinds is not None and k not in kinds:
            continue
        if (side > 0 and v <= px) or (side < 0 and v >= px) or abs(v - px) < mn:
            continue
        if best is None or abs(v - px) < abs(best[0] - px):
            best = (v, k, n, dr)
    return best


def _force(lock: dict, side: int, px: float, mn: float, tag: str, kinds=("pool",)) -> bool:
    """Set the lock to `side` toward the nearest marked level there; False when there is none (the lock is left as it was)."""
    nr = _nearest(lock, px, side, mn, kinds)
    if nr is None:
        return False
    lock.update(side=side, target=nr[0], kind=nr[1], name=nr[2])
    lock.setdefault("bh1", []).append(tag)
    hit("lock_" + tag)
    return True


def _neutral(lock: dict, tag: str) -> None:
    lock.update(side=0, target=None, kind="", name="")
    lock.setdefault("bh1", []).append(tag)
    hit("lock_" + tag)


def _bisi60_lost(ctx, kl: int) -> int:
    """BH-A8-60m-BISI-loss-draw: +1 / -1 = the lean (a 60m close below the nearest discount BISI under the swing's 50 % -> -1; above the nearest premium SIBI over it -> +1), 0 none."""
    b = tf_complete(ctx, 60, kl - 1)
    if len(b["c"]) < 5:
        return 0
    o, h, l, c = (b[k][-30:] for k in ("o", "h", "l", "c"))
    lo, hi = float(l[-24:].min()), float(h[-24:].max())
    eq = (lo + hi) / 2
    got = []
    zs = L.fvgs(h, l, o, c)
    bulls = [z for z in zs if z.kind == "bull" and z.top < eq]
    bears = [z for z in zs if z.kind == "bear" and z.bottom > eq]
    if bulls:                                       # the NEAREST discount BISI under the 50 % (the highest one), its loss only (review round 1)
        z = max(bulls, key=lambda x: x.top)
        j = next((q for q in range(z.i + 1, len(c)) if c[q] < z.bottom), None)
        if j is not None:
            got.append((j, -1, z.top))
    if bears:
        z = min(bears, key=lambda x: x.bottom)
        j = next((q for q in range(z.i + 1, len(c)) if c[q] > z.top), None)
        if j is not None:
            got.append((j, 1, -z.bottom))
    if not got:
        return 0
    sides = {g[1] for g in got}
    if len(sides) > 1:
        return max(got)[1]                          # both: the later loss
    return got[0][1]


def _bpr_dir(ctx, kl: int) -> int:
    """BH-A11-BPR-lean: a 1h BPR of the last 24 hours in a down-up-down sequence (-1) / up-down-up (+1): a bear FVG, then a bull FVG overlapping it, then a close under the overlap's bottom (mirror: above its top)."""
    b = tf_complete(ctx, 60, kl - 1)
    if len(b["c"]) < 5:
        return 0
    o, h, l, c = (b[k][-24:] for k in ("o", "h", "l", "c"))
    zs = L.fvgs(h, l, o, c)
    last = (0, 0)
    for zb in zs:
        for zu in zs:
            if zb.kind == "bear" and zu.kind == "bull" and zu.i > zb.i and zu.bottom < zb.top and zu.top > zb.bottom:
                ov_b = max(zb.bottom, zu.bottom)
                j = next((q for q in range(zu.i + 1, len(c)) if c[q] < ov_b), None)
                if j is not None and (j, -1) > last:
                    last = (j, -1)
            if zb.kind == "bull" and zu.kind == "bear" and zu.i > zb.i and zu.bottom < zb.top and zu.top > zb.bottom:      # the mirror: up (bull FVG), down (bear FVG overlapping it), up (a close above the overlap)
                ov_t = min(zb.top, zu.top)
                j = next((q for q in range(zu.i + 1, len(c)) if c[q] > ov_t), None)
                if j is not None and (j, 1) > last:
                    last = (j, 1)
    return last[1]


def min_criteria(ctx, sign: int, kl: int, tol: float = 0.5):
    """BH-B4-HTF-bias-minimum-criteria (075 ~00:34:50): the three steps in order on the 60m bars up to the lock - (1) price traded into a daily array of the side, (2) a 60m relative-equal-low (high; two
    pivot lows within `tol`) was swept, (3) a later 60m high above the most recent 60m pivot high before the sweep (the MSS; no close needed). Returns (ok, the array's MT, base bar index of the step-3 bar)."""
    b = tf_complete(ctx, 60, kl - 1)
    n = len(b["c"])
    if n < 8:
        return False, None, None
    s = 1 if sign > 0 else -1
    if s > 0:
        o, h, l, c = (b[k][-72:] for k in ("o", "h", "l", "c"))
    else:
        o, h, l, c = -b["o"][-72:], -b["l"][-72:], -b["h"][-72:], -b["c"][-72:]
    last_idx = b["last"][-72:]
    arrs = [a for a in daily_arrays(ctx) if a.kind == ("bull" if s > 0 else "bear")]
    if not arrs:
        return False, None, None
    top = lambda a: a.top if s > 0 else -a.bottom
    bot = lambda a: a.bottom if s > 0 else -a.top
    k1, arr = None, None
    for j in range(len(c)):
        hit_ = [a for a in arrs if l[j] <= top(a) and h[j] >= bot(a)]
        if hit_:
            k1, arr = j, hit_[0]
            break
    if k1 is None:
        return False, None, None
    ph, pl = L.pivots(h, l, 1)
    k2 = None
    for j in range(k1, len(c)):
        rels = [q.price for q in pl if q.known <= j - 1]
        lv = [min(x, y) for a_, x in enumerate(rels) for y in rels[a_ + 1:] if abs(x - y) <= tol]
        if lv and l[j] < min(lv) - 1e-9:
            k2 = j
            break
    if k2 is None:
        return False, None, None
    prior_h = [q.price for q in ph if q.i < k2 and q.known <= k2]
    if not prior_h:
        return False, None, None
    ref = prior_h[-1]
    k3 = next((j for j in range(k2 + 1, len(c)) if h[j] > ref), None)
    if k3 is None:
        return False, None, None
    return True, float((arr.top + arr.bottom) / 2), int(last_idx[k3])


def _fifty(ctx, p, kl: int, px: float, lock: dict, mk: list):
    """BH-B17-REL-REH-both-intact: price inside an alive daily FVG, the nearest REL below and a buy-side pool above both untaken (or the mirror: REH above, a sell-side pool below). Returns (rel, reh) levels
    or None when the test fails."""
    S = _S()
    inside = any(a.bottom <= px <= a.top for a in daily_arrays(ctx))
    if not inside:
        return None
    sd = ctx.sides_map[1] if getattr(ctx, "sides_map", None) else None
    if sd is None:
        return None
    tol = p.eq_tol_pts * p.es_pt
    i = kl - 1
    rel = [v for v in S._eq_levels(sd, i, tol, True, p) if v < px]
    reh = [v for v in S._eq_levels(sd, i, tol, False, p) if v > px]
    up_pool = any(m_[1] > px and m_[2] == "pool" for m_ in mk)
    dn_pool = any(m_[1] < px and m_[2] == "pool" for m_ in mk)
    rel_v, reh_v = (max(rel) if rel else None), (min(reh) if reh else None)
    if (rel_v is not None and up_pool) or (reh_v is not None and dn_pool):
        return rel_v, reh_v
    return None


def _inval_level(ctx, p, session: str, side: int, px: float):
    """The pre-stated invalidation price of a lock (item 16): 'array' = the far edge of the nearest daily array beyond the lock price on the lock's side (bearish lock: a bear array above, top;
    bullish: a bull array below, bottom) [our interpretation]; 'manual' = data/mentorship/inval_levels.csv (date, session, price)."""
    if p.inval_src == "manual":
        if not INVAL_FILE.exists() and "inval_missing" not in HITS:
            import warnings
            warnings.warn(f"inval_src='manual': {INVAL_FILE} is missing (header: date,session,price; one row per pre-stated invalidation price) - no manual invalidation is applied", stacklevel=2)
            hit("inval_missing")
        try:
            import csv
            if INVAL_FILE.exists():
                with open(INVAL_FILE, newline="") as fh:
                    for r in csv.DictReader(fh):
                        if r.get("date") == str(ctx.day) and (r.get("session") or "").upper() in ("", session.upper()):
                            return float(r["price"])
        except Exception:
            return None
        return None
    cs = [a for a in daily_arrays(ctx) if a.kind == ("bear" if side < 0 else "bull") and ((a.bottom >= px) if side < 0 else (a.top <= px))]
    if not cs:
        return None
    if side < 0:
        return float(min(cs, key=lambda a: a.bottom - px).top)
    return float(max(cs, key=lambda a: a.top).bottom)


def lock_post(ctx, p, row, t_lock: int, session: str, kl: int, px: float, lock: dict, mk: list) -> dict:
    """mark_levels tail: the bias_htf#1/7 adjustments of the freshly built lock (in order: ceiling ladder, weekly PO3, 60m BISI loss, BPR lean, raid gap guard, minimum criteria, 50/50, run extreme, inval)."""
    if not on(p) or _c(ctx).get("no_post"):
        return lock
    mn = p.draw_lock_min_pts * p.es_pt
    S = _S()
    state_side = 0
    if row is not None:
        state_side = _BD().bias_value(row, p) if p.htf_bias != "off" else _n(row, "flip")
        if not state_side:
            state_side = _n(row, "flip")
    # item 9
    if p.ceiling_ladder and row is not None:
        ld, lu = _n(row, "ladder_dn"), _n(row, "ladder_up")
        if ld and not lu:
            _force(lock, -1, px, mn, "ceiling_ladder", kinds=None)
        elif lu and not ld:
            _force(lock, 1, px, mn, "floor_ladder", kinds=None)
    # item 64
    if p.wk_po3 and row is not None:
        v = _n(row, "wk_po3")
        if v:
            wd = _f(row, "wk_draw_up" if v > 0 else "wk_draw_dn")
            if wd == wd and ((wd > px) if v > 0 else (wd < px)) and abs(wd - px) >= mn:
                lock.update(side=v, target=wd, kind="array", name="wk_po3_draw")
                lock.setdefault("bh1", []).append("wk_po3")
                hit("lock_wk_po3")
            else:
                _force(lock, v, px, mn, "wk_po3")
    # item 5
    if p.bisi60_draw:
        lean = _bisi60_lost(ctx, kl)
        if lean:
            _force(lock, lean, px, mn, "bisi60_lost")
    # item 10
    if p.bpr_lean:
        d_ = _bpr_dir(ctx, kl)
        if d_ and d_ == state_side:
            _force(lock, d_, px, mn, "bpr_lean")
    # item 15
    if p.raid_gap_guard and getattr(ctx, "hist", None):
        _raid_lock(ctx, p, row, kl, px, lock, mn)
    # item 59
    if p.min_criteria and lock["side"]:
        ok, mt, k3 = min_criteria(ctx, lock["side"], kl, p.eq_tol_pts * p.es_pt)
        if ok:
            lock["mc"] = dict(mt=mt, k3=k3)
            lock.setdefault("bh1", []).append("min_criteria")
        else:
            _neutral(lock, "min_criteria_fail")
    # item 41
    if p.fifty_rel:
        f5 = _fifty(ctx, p, kl, px, lock, mk)
        if f5 is not None:
            lock["rel"], lock["reh"] = f5
            lock["fifty"] = True
            _neutral(lock, "fifty_rel")
    # item 65
    if p.run_extreme_lean and lock["side"] == 0 and row is not None and not lock.get("fifty"):
        hv, lv = _f(row, "run_hi_draw"), _f(row, "run_lo_draw")
        c_ = [(abs(hv - px), 1, hv) for hv in [hv] if hv == hv and hv > px + mn] + [(abs(px - lv), -1, lv) for lv in [lv] if lv == lv and lv < px - mn]
        if c_:
            _, sg, v = min(c_)
            lock.update(side=sg, target=v, kind="pool", name="run_extreme")
            lock.setdefault("bh1", []).append("run_extreme")
            lock["marked"] = list(lock.get("marked", ())) + [(v, "pool", "run_extreme", sg)]
            hit("lock_run_extreme")
    # item 16
    if p.inval_src != "off" and lock["side"]:
        lv = _inval_level(ctx, p, session, lock["side"], px)
        if lv is not None:
            lock["inval"] = lv
    return lock


def _raid_lock(ctx, p, row, kl: int, px: float, lock: dict, mn: float) -> None:
    """BH-B14-protective-gap-and-low: after a sell-side raid under a consolidation (the prior session's low taken since the session start while the market was ranging) stay long toward the current
    NWOG's near edge; mirror for a buy-side raid. The gap guard (lock_bar) flips it."""
    S = _S()
    hist = ctx.hist
    adr = None
    P = getattr(ctx, "dplan", None)
    if P is not None:
        adr = P.info.get("adr5_prev")
    pr = hist[-1]
    rng = float(pr.high.max() - pr.low.min())
    consol = bool(_n(row, "drange_in") or (row is not None and row.get("nwog_regime") == "cons") or (adr and rng < 0.6 * adr))
    if not consol or kl - 1 < ctx.start:
        return
    nw = S._nwogs(ctx, kl - 1)
    if not nw:
        return
    a, b = nw[-1]
    lo, hi = min(a, b), max(a, b)
    sl = float(ctx.l[ctx.start:kl].min())
    sh = float(ctx.h[ctx.start:kl].max())
    if sl < float(pr.low.min()) and lo > px and lo - px >= mn:
        lock.update(side=1, target=float(lo), kind="array", name="raid_nwog")
        lock["rg"] = dict(side=1, raid=sl, raid_i=ctx.start + int(np.argmin(ctx.l[ctx.start:kl])))
        lock.setdefault("bh1", []).append("raid_gap")
        hit("lock_raid_gap")
    elif sh > float(pr.high.max()) and hi < px and px - hi >= mn:
        lock.update(side=-1, target=float(hi), kind="array", name="raid_nwog")
        lock["rg"] = dict(side=-1, raid=sh, raid_i=ctx.start + int(np.argmax(ctx.h[ctx.start:kl])))
        lock.setdefault("bh1", []).append("raid_gap")
        hit("lock_raid_gap")


# --------------------------------------------------------------------------------------------------------------
# the per-bar lock changes
# --------------------------------------------------------------------------------------------------------------

def _relock(ctx, p, s_: str, lk: dict, i: int, spent, side: int, tag: str, kinds=("pool",)):
    """A new lock for session s_ from bar i+1 forced to `side` (the nearest marked pool there); a lock with side 0 when nothing is there. Returns the new lock."""
    S = _S()
    _c(ctx)["no_post"] = True
    try:
        nl = S.mark_levels(ctx, None, int(ctx.t[i] + ctx.tf), "PM" if s_ == "LH" else s_, p, spent)
    finally:
        _c(ctx)["no_post"] = False
    nl["session"] = s_
    px = float(ctx.c[i])
    mn = p.draw_lock_min_pts * p.es_pt
    if side == 0 or not _force(nl, side, px, mn, tag, kinds):
        if side != 0:
            nl2 = dict(lk, marked=nl.get("marked", lk.get("marked", ())))
            if not _force(nl2, side, px, mn, tag, kinds):
                _neutral(nl, tag + "_none")
            else:
                nl = dict(nl, **{k: nl2[k] for k in ("side", "target", "kind", "name", "bh1")})
        else:
            _neutral(nl, tag)
    nl.update(delivered=False, delivered_t=None, delivered_i=None, traded=lk.get("traded", False))
    nl.setdefault("bh1", []).append(tag)
    return nl


def _pivot_highs_taken(ctx, a: int, i: int, high: bool = True) -> int:
    """Short-term pivot highs (lows) formed after bar a that a later bar (through i) traded beyond."""
    if i - a < 3:
        return 0
    h, l = ctx.h[:i + 1], ctx.l[:i + 1]
    ph, pl = L.pivots(h, l, 1)
    n = 0
    for q in (ph if high else pl):
        if q.i <= a or q.known > i:
            continue
        later = h[q.known:i + 1] if high else l[q.known:i + 1]
        if len(later) and ((later.max() > q.price) if high else (later.min() < q.price)):
            n += 1
    return n


def _new_extremes(ctx, a: int, i: int, low: bool = True) -> int:
    """New session lows (highs) printed by the bars after a (through i): bars that undercut (exceed) the session extreme before them."""
    n = 0
    for j in range(a + 1, i + 1):
        if low and ctx.l[j] < ctx.l[ctx.start:j].min():
            n += 1
        if (not low) and ctx.h[j] > ctx.h[ctx.start:j].max():
            n += 1
    return n


def lock_bar(ctx, p, s_: str, lk: dict, i: int, done: dict, spent, state=None):
    """_lock_step hook, once per bar and session lock: returns (new_lock, cancel_pending) when the lock changes, else None."""
    st = _state(ctx)
    side = lk.get("side", 0)
    closed_ = False                                   # review round 1: a session or day ended by a stop / target switch (eve_bnb, day_target_pts, drange, loss stops) is not reopened
    if state is not None:
        from . import manage as _M
        closed_ = bool(state.get("day_done")) or _M.blocked_now(state, s_)
    # item 44: the delivered draw reopens the session for one counter-bias trade
    if p.allow_counter_trend and lk.get("delivered") and side and not closed_ and not lk.get("ct_open") and not lk.get("ct_done"):
        lk["ct_open"] = True
        done[s_] = False
        st.setdefault("only_side", {})[s_] = -side
        hit("ct_open")
    # item 40: the morning low is in
    if p.low_in_relock and lk.get("delivered") and side and not closed_ and not lk.get("low_in_done") and lk.get("delivered_i") is not None and i > lk["delivered_i"]:
        a = lk["delivered_i"]
        hi_n = _pivot_highs_taken(ctx, a, i, high=(side < 0))
        lo_n = _new_extremes(ctx, a, i, low=(side < 0))
        if hi_n >= p.low_in_min_highs and hi_n >= p.low_in_ratio * lo_n:
            nl = _relock(ctx, p, s_, lk, i, spent, -side, "low_in")
            nl["low_in_done"] = True
            if nl["side"]:
                done[s_] = False
                st.get("only_side", {}).pop(s_, None)
            return nl, True
    if lk.get("delivered") and side:
        return None
    # item 16: the pre-stated invalidation price
    if p.inval_src != "off" and lk.get("inval") is not None and side and not lk.get("inval_touch"):
        v = lk["inval"]
        if (side < 0 and ctx.h[i] >= v) or (side > 0 and ctx.l[i] <= v):
            nl = _relock(ctx, p, s_, lk, i, spent, -side, "inval_touch")
            nl["inval_touch"] = True
            nl["inval"] = None
            return nl, True
    # item 74: the latest 60m BISI of the locked side holds
    if p.bisi60_hold != "off" and side and not lk.get("bisi_dead"):
        r = _bisi_hold(ctx, p, lk, i)
        if r == "dead":
            nl = dict(lk)
            _neutral(nl, "bisi60_dead")
            nl["bisi_dead"] = True
            return nl, True
        if r == "weak" and not lk.get("weak"):
            lk["weak"] = True
            lk.setdefault("bh1", []).append("bias_weak")
            hit("bias_weak")
    # item 15: the raid-gap guard
    if p.raid_gap_guard and lk.get("rg") and side == lk["rg"]["side"] and not lk.get("rg_done"):
        rg = lk["rg"]
        s = rg["side"]
        zs = [z for z in L.fvgs(ctx.h[:i + 1], ctx.l[:i + 1]) if z.kind == ("bear" if s > 0 else "bull") and z.i - 2 > rg["raid_i"] and z.i <= i]
        if zs:
            z = zs[0]
            later = ctx.h[z.i + 1:i + 1] if s > 0 else ctx.l[z.i + 1:i + 1]
            filled = bool(len(later) and ((later.max() >= z.top) if s > 0 else (later.min() <= z.bottom)))
            taken = (ctx.l[i] < rg["raid"]) if s > 0 else (ctx.h[i] > rg["raid"])
            if filled:
                lk["rg_done"] = True
            elif taken:
                nl = _relock(ctx, p, s_, lk, i, spent, -s, "raid_gap_flip")
                nl["rg_done"] = True
                return nl, True
    # item 41: the 50/50 lock waits for a sweep and an MSS
    if p.fifty_rel and lk.get("fifty") and side == 0 and not lk.get("fifty_done"):
        r = _fifty_resolve(ctx, p, lk, i)
        if r:
            nl = _relock(ctx, p, s_, lk, i, spent, r, "fifty_resolved")
            nl["fifty_done"] = True
            nl["fifty"] = False
            if nl["side"]:
                done[s_] = False
            return nl, True
    return None


def _bisi_hold(ctx, p, lk: dict, i: int) -> str:
    """BH-B8-1h-BISI-CE-hold (072 ~13:53, ~15:19): '' / 'weak' (traded / closed through the latest 60m BISI's CE) / 'dead' (through its low). Mirror for a -1 lock (the latest 60m SIBI)."""
    s = lk["side"]
    b = tf_complete(ctx, 60, i)
    if len(b["c"]) < 3:
        return ""
    o, h, l, c = ((b[k] for k in ("o", "h", "l", "c")) if s > 0 else (-b["o"], -b["l"], -b["h"], -b["c"]))
    zs = [z for z in L.fvgs(h, l, o, c) if z.kind == "bull" and z.bottom < (lk["px"] if s > 0 else -lk["px"])]
    if not zs:
        return ""
    z = zs[-1]
    ce = (z.top + z.bottom) / 2
    j0 = int(b["last"][z.i])
    if p.bisi60_hold == "trade":
        seg = ctx.l[j0 + 1:i + 1] if s > 0 else -ctx.h[j0 + 1:i + 1]
        lo = float(seg.min()) if len(seg) else np.inf
    else:
        seg = c[z.i + 1:]
        lo = float(seg.min()) if len(seg) else np.inf
    if lo < z.bottom:
        return "dead"
    if lo < ce:
        return "weak"
    return ""


def _fifty_resolve(ctx, p, lk: dict, i: int) -> int:
    """After a 50/50 lock: the REL swept then an MSS up (a close above the last short-term high before the sweep) -> +1; the REH swept then an MSS down -> -1; else 0."""
    S = _S()
    t0 = lk.get("t_lock", 0)
    a = max(ctx.start, S._idx_at(ctx, t0) - 1)
    for side, lvl in ((1, lk.get("rel")), (-1, lk.get("reh"))):
        if lvl is None or i <= a:
            continue
        j = next((q for q in range(a, i + 1) if ((ctx.l[q] < lvl - 1e-9) if side > 0 else (ctx.h[q] > lvl + 1e-9))), None)
        if j is None:
            continue
        ph, pl = L.pivots(ctx.h[:i + 1], ctx.l[:i + 1], 1)
        pv = [q.price for q in (ph if side > 0 else pl) if q.i < j and q.known <= j]
        if not pv:
            continue
        ref = pv[-1]
        if any((ctx.c[q] > ref) if side > 0 else (ctx.c[q] < ref) for q in range(j + 1, i + 1)):
            return side
    return 0


# --------------------------------------------------------------------------------------------------------------
# the counter-trend trade, drange accounting
# --------------------------------------------------------------------------------------------------------------

def counter_kind(ctx, sd, i: int, p, w_: int, session: str) -> str:
    """BH-B3-counter-bias-modes (095 ~11:56; 030 ~25:11): 'ct' when the session's locked draw was delivered (ct_open) and this side is the opposite of the delivered draw (the bias side)."""
    if not p.allow_counter_trend:
        return ""
    lk = (getattr(ctx, "lock", None) or {}).get("AM" if session == "LUNCH" else session)
    if lk is not None and lk.get("ct_open") and lk.get("side") and sd.sign == -lk["side"]:
        return "ct"
    return ""


def after_close(ctx, tr, done: dict, state: dict, p, net: float) -> None:
    """BH-B17-daily-range-scalp-regime: count the day's points and wins; after one win trade only the opposite pool; stop for the day at drange_day_pts or two wins (range days only)."""
    if not p.drange_scalp:
        return
    row = getattr(ctx, "bias_row", None)
    if row is None or not _n(row, "drange_in"):
        return
    units = max(tr.shares + sum(q for *_, q in tr.adds), 1)
    state["bh1_pts"] = state.get("bh1_pts", 0.0) + net / units / p.es_pt
    if net > 0:
        state["bh1_wins"] = state.get("bh1_wins", 0) + 1
        state["bh1_dr_side"] = -(1 if tr.side == "long" else -1)
    if state.get("bh1_pts", 0.0) >= p.drange_day_pts or state.get("bh1_wins", 0) >= 2:
        for k in list(done):
            done[k] = True
        state["day_done"] = True
        state["bh1_dr_done"] = True
        hit("drange_day_done")
