"""Caption-gap pass, package bias_htf#6/7 (digests/rulebook_gaps/management_partials_trailing_exits.md items 97, 133 and models_setups_entries.md item 129) - ENGINE SIDE.

The bar-loop part: the side gate of the both-pools continuation filter, the scenario re-lock of the live-vs-analysis check, the seven-factor order tag. The columns they read are built by `bh6.py` inside
`htf.table`. Nothing here reads a bar after the closed bar `i` the caller passes; every daily value is a table column.
Hooks (who calls them)
  side_ok     daycontext.side_ok tail      both_pools_gate (X8-061-continuation-after-both-pools)
  order_ok    daycontext.order_ok tail     factor_tag (new-seven-factor-context): adds lv_tags f7_b<n>m<n>s<n> [+ f7_high]
  lock_bar    strategy._lock_step          scenario_check / scenario_flip (new-live-vs-analysis-mismatch)
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations


from . import bh1e as B1
from . import bh2 as BH2

HITS = BH2.HITS
sw = BH2.sw
_n, _f, _row = B1._n, B1._f, B1._row


def hit(k: str) -> None:
    HITS[k] += 1


def _S():
    return B1._S()


def on(p) -> bool:
    return bool(p.both_pools_gate or p.factor_tag)


def lock_on(p) -> bool:
    return bool(p.scenario_check)


# --------------------------------------------------------------------------------------------------------------
# X8-061-continuation-after-both-pools: the side gate
# --------------------------------------------------------------------------------------------------------------

def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf#6/7 reason, else None."""
    if not p.both_pools_gate or i is None:
        return None
    row = _row(ctx, session, i)
    if row is None or "bp_dir" not in row or not _n(row, "both_pools"):
        return None
    cap = _f(row, "cont_cap")
    if cap != cap:
        return None                                          # no order-block candle / FVG to measure against: the filter is inert
    dr = _n(row, "bp_dir")
    # The test is on the price the order is armed at (order_ok -> _cap_order): a short limit armed above the cap is rejected, one armed at / below it (a retrace into the OB) is allowed even when the market
    # last closed above the cap. [our interpretation] "if it trades above either one, stand aside" = the armed price is the thing tested, so there is no session latch; the side stays open here.
    return None


def _cap_order(ctx, sd, o: dict, session: str, i: int, p):
    """X8-061: the order-level test - a short armed ABOVE the cap (a long BELOW it for an up leg) is rejected, one armed at or inside the cap is allowed whatever the market does."""
    row = _row(ctx, session, i)
    if row is None or "bp_dir" not in row or not _n(row, "both_pools"):
        return None
    cap = _f(row, "cont_cap")
    if cap != cap or o.get("entry") is None:
        return None
    dr = _n(row, "bp_dir")
    e = float(o["entry"])
    if (dr < 0 and sd.sign < 0 and e > cap) or (dr > 0 and sd.sign > 0 and e < cap):
        sw("both_pools_gate")
        return "x_bh6_both_pools"
    return None


# --------------------------------------------------------------------------------------------------------------
# new-seven-factor-context: the order tag
# --------------------------------------------------------------------------------------------------------------

def factor_counts(ctx, p, row, sign: int, o: dict, i: int) -> tuple:
    """(big-picture, intermediate, short-term) agreeing-factor counts for an order in direction `sign`: big picture = the weekly bias, the monthly OB activation, the monthly structure control; intermediate =
    the daily reaction / P-D reading, the daily IOF, the stateful B8 bias; short term = (time of day) the order is armed inside 09:30-11:00 / 13:30-15:00, (SMT) the order carries an SMT tag that is not a
    laggard / against tag, (array) the order's entry array is an HTF array. The factor list is [our interpretation] (the slide of cc02_006 is not in the captions)."""
    big = sum(1 for k in ("wk_bias", "mob", "m_ctrl") if _n(row, k) == sign)
    mid = sum(1 for k in ("combo", "iof", "flip") if _n(row, k) == sign)
    t = int(ctx.t[i])
    tags = str(o.get("lv_tags", "") or "")
    tod = 1 if (570 <= t < 660 or 810 <= t < 900) else 0
    smt = 1 if (o.get("smt") and "smt_laggard" not in tags and "smt_bias_against" not in tags) else 0
    arr = 1 if o.get("htf") else 0
    return big, mid, (tod, smt, arr)


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """Adds the f7 tag to the armed order; never rejects (a context label, ICT: 'this is not execution')."""
    if p.both_pools_gate and i is not None:
        why = _cap_order(ctx, sd, o, session, i, p)
        if why is not None:
            return why
    if not p.factor_tag:
        return None
    row = _row(ctx, session, i)
    if row is None:
        return None
    big, mid, sh = factor_counts(ctx, p, row, sd.sign, o, i)
    sw("factor_tag")
    tags = [f"f7_b{big}m{mid}s{sum(sh)}"]
    if big >= 2 and mid >= 2 and all(sh):
        tags.append("f7_high")
    o["lv_tags"] = "|".join(dict.fromkeys(x for x in (o.get("lv_tags", ""), *tags) if x))
    return None


# --------------------------------------------------------------------------------------------------------------
# new-live-vs-analysis-mismatch: the scenario re-lock
# --------------------------------------------------------------------------------------------------------------

def _pools(ctx, side: int, target: float, px0: float) -> list:
    """The draw-side pools between the price at the lock and the draw: the previous-day extremes of that side that lie on the way (the draw itself included)."""
    keys = ("pdl1", "pdl2", "pdl3") if side < 0 else ("pdh1", "pdh2", "pdh3")
    out = [float(ctx.pd[k]) for k in keys if k in ctx.pd]
    out.append(float(target))
    if side < 0:
        return [x for x in out if x < px0 and x >= target - 1e-9]
    return [x for x in out if x > px0 and x <= target + 1e-9]


def scenario_broken(ctx, p, lk: dict, i: int) -> bool:
    """True when, before any fill and before the raid-side pool of the locked scenario was taken, the draw-side pool was run at a bar since the lock with a close beyond it and a same-direction FVG (a
    3-bar gap whose third bar is that bar or one of the next two) [our interpretation of 'with displacement and a body close beyond it']."""
    side = int(lk.get("side", 0))
    if not side or lk.get("traded") or lk.get("delivered") or lk.get("scn_done") or lk.get("target") is None:
        return False
    raid_key = "pdh1" if side < 0 else "pdl1"                # the other side's previous-day pool is where the raid is expected
    if raid_key not in ctx.pd:
        return False
    raid = float(ctx.pd[raid_key])
    tl = int(lk.get("t_lock", 0))
    S = _S()
    j0 = max(S._idx_at(ctx, tl), ctx.start + 2)
    if j0 > i:
        return False
    px0 = float(ctx.o[j0])
    pools = _pools(ctx, side, float(lk["target"]), px0)
    if not pools:
        return False
    h, l, c = ctx.h, ctx.l, ctx.c
    for jb in range(j0, i + 1):
        if (side < 0 and h[ctx.start:jb + 1].max() >= raid) or (side > 0 and l[ctx.start:jb + 1].min() <= raid):
            return False                                     # the raid came first: the scenario is on track
        if not any((c[jb] < x) if side < 0 else (c[jb] > x) for x in pools):
            continue
        for jg in range(jb, min(i, jb + 2) + 1):
            if jg - 2 < ctx.start:
                continue
            if (side < 0 and h[jg] < l[jg - 2]) or (side > 0 and l[jg] > h[jg - 2]):
                if (side < 0 and h[ctx.start:jg + 1].max() >= raid) or (side > 0 and l[ctx.start:jg + 1].min() <= raid):
                    return False
                return True
    return False


def lock_bar(ctx, p, s_: str, lk: dict, i: int, done: dict, spent, state=None):
    """_lock_step hook, once per bar and session lock: scenario_check re-locks (once per session) to neutral - the session ends (done[s_]) - or, with scenario_flip, to the other side. Returns
    (new_lock, cancel_pending) or None."""
    if not p.scenario_check or not scenario_broken(ctx, p, lk, i):
        return None
    side = int(lk["side"])
    if p.scenario_flip:
        nl = B1._relock(ctx, p, s_, lk, i, spent, -side, "scenario_flip")
    else:
        nl = B1._relock(ctx, p, s_, lk, i, spent, 0, "scenario")
        done[s_] = True
    nl["scn_done"] = True
    sw("scenario_check")
    if p.scenario_flip:
        sw("scenario_flip")
    hit("scenario_flip" if p.scenario_flip else "scenario_aside")
    return nl, True
