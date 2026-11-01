"""Coverage gap build (coverage_build_2026-10-31.md), packages 3b-3d: per-order filters and glue. Every switch defaults to the built behaviour.

  3b  ndog_ce_filter  order_ok   092 ~45:52: a short's entry at / above the current NDOG's CE, a long's at / below it
  3c  sick_refs / sick_consol_only  sick_refs_053, consol_day   053 ~3:47: the sick sister's two references and the consolidation-day gate
  3d  smt_partial  smt_partial   037 ~33:44 / 046 ~1:09:15: the SMT partials with NQ and YM (case a / case b)
Tags go into o["lv_tags"]; a failed rule returns a funnel key (x_cg_*).
"""
from __future__ import annotations

from collections import Counter

HITS: Counter = Counter()


def hit(k: str) -> None:
    HITS[k] += 1


def _tag(o: dict, t: str) -> None:
    o["lv_tags"] = "|".join(x for x in (o.get("lv_tags", ""), t) if x) if isinstance(o.get("lv_tags", ""), str) else list(o.get("lv_tags") or []) + [t]


def order_ok(ctx, sd, o: dict, session: str, i: int, p, trades=()):
    """A funnel key when the armed order `o` (side space) breaks a coverage-gap rule, else None."""
    from . import cg2 as _CG2, cg3 as _CG3
    why = _CG2.order_ok(ctx, sd, o, session, i, p, trades) or _CG3.order_ok(ctx, sd, o, session, i, p)
    if why is not None:
        return why
    if not p.ndog_ce_filter:
        return None
    gaps = getattr(ctx, "gaps", None)
    nd = [g for g in (gaps or []) if g[0] == "ndog"]
    if not nd:
        hit("ndog_ce_none")
        return None
    ce = float(nd[-1][3])                     # the latest NDOG in force (rows are in formation order)
    entry = float(sd.x(o["entry"]))
    ok = entry >= ce - 1e-9 if sd.sign < 0 else entry <= ce + 1e-9
    if not ok:
        hit("ndog_ce_fail")
        return "x_cg_ndog_ce"
    hit("ndog_ce_pass")
    _tag(o, "ndog_ce")
    return None


def _S():
    from . import strategy
    return strategy


def sick_refs_053(c_, s_, k: int, tk):
    """053 ~3:47, ICT's two references of the sick sister in side space s_, counted at bar index k (the count minute): the prior session's afternoon high (ctx.sess["prev_pm"], the high / low
    by the side) and the most recent overnight swing high (the latest 3-candle swing high among today's bars before k that was confirmed before k [our interpretation]). Returns
    (number broken, sorted unbroken levels): broken = a bar before k traded above the level (the swing: after its confirmation bars). None when neither reference exists."""
    S = _S()
    lv, broken, left = [], 0, []
    top = s_.h[c_.start:k].max() if k > c_.start else None
    if top is None:
        return None
    if "prev_pm" in c_.sess:
        hi, lo, _ = c_.sess["prev_pm"]
        v = s_.x(hi if s_.sign > 0 else lo)
        lv.append(v)
        if S._spent_up(top, v, tk):
            broken += 1
        else:
            left.append(v)
    h = s_.h
    sw = None
    for j in range(k - 4, c_.start, -1):                      # the latest swing high whose right 3 bars are < k (confirmed before the count)
        if h[j] > h[j - 1] and h[j] > h[j + 1] and h[j] > h[j + 2] and h[j] > h[j + 3]:
            sw = j
            break
    if sw is not None:
        v = float(h[sw])
        lv.append(v)
        if S._spent_up(h[sw + 1:k].max(), v, tk):
            broken += 1
        else:
            left.append(v)
    if not lv:
        return None
    return broken, sorted(left)


MEDIUM_HIGH_NEWS = {"fomc", "cpi", "jobs", "ppi", "pce", "retail_sales", "gdp"}      # medium / high impact releases [our interpretation]; ISM, sentiment and JOLTS are low impact


def partial_active(ctx, p) -> bool:
    """smt_partial replaces smt_bank / smt_bank_against_frac only when both sisters (NQ and YM) are present; otherwise the old banks stay."""
    ps = getattr(ctx, "pside", None)
    return p.smt_partial != "off" and ps is not None and ps[0] is not None and bool(getattr(ctx, "partner2", None))


def consol_day(ctx, session: str, i: int) -> bool:
    """sick_consol_only: no medium / high impact news today (the calendar) and a consolidation NWOG regime (the table column nwog_regime); an absent column is unknown and allowed (hit sick_cons_unknown)."""
    S = _S()
    from . import bias_day as BD, calendar as CAL
    if CAL.events(ctx.day) & MEDIUM_HIGH_NEWS:
        hit("sick_news_day")
        return False
    row = BD.row_for(ctx, session, i)
    reg = (row.get("nwog_regime") if row else None)
    if not reg:
        hit("sick_cons_unknown")
        return True
    if reg != "cons":
        hit("sick_not_cons")
        return False
    return True


def _partners(ctx, sd, pos, i: int):
    """[(partner Side, j (its bar of the closed ES bar i), jf (its bar of the fill))] for NQ (ctx.pside) and YM (ctx.partner2) that are aligned with the trade; [] unless both exist."""
    out = []
    ps = getattr(ctx, "pside", None)
    if ps is not None and ps[0] is not None and ps[1] is not None:
        out.append((ps[0], ps[1][sd.sign], ps[2]))
    p2 = getattr(ctx, "partner2", None)
    if p2:
        out.append((p2[0], p2[1][sd.sign], p2[2]))
    res = []
    for c_, s_, pp in out:
        j = pp.index.searchsorted(ctx.idx[i], side="right") - 1
        jf = pp.index.searchsorted(ctx.idx[pos["fill_i"]], side="right") - 1
        if jf < c_.start or j <= jf:
            return []
        res.append((s_, int(j), int(jf)))
    return res


def _bank(S, sd, pos, tr, ts, c, p, frac: float, name: str) -> None:
    if frac <= 0:
        return
    q = min(pos["left"], max(p.lot, S._lots(pos["left"] * frac, p.lot)))
    if q <= 0:
        return
    tr.exits.append((ts, sd.x(c), q, name))
    pos["left"] -= q


def smt_partial(ctx, sd, pos: dict, tr, i: int, ts, p) -> None:
    """3d: see Params.smt_partial. Market-on-close partials at the deciding bar's close (like smt_bank), side space = the trade's direction. Reads bars up to i only."""
    S = _S()
    if i <= pos["fill_i"] or not pos["left"]:
        return
    pr = _partners(ctx, sd, pos, i)
    if len(pr) < 2:                                       # both sisters are needed (NQ and YM)
        return
    c = sd.c[i]
    basis = pos["basis"] / pos["n"]
    risk_s = abs(tr.entry - tr.stop)
    if risk_s <= 0:
        return
    eps = 1e-9
    fi = pos["fill_i"]
    if p.smt_partial in ("a", "both") and not pos.get("smt_pa") and (c - basis) / risk_s >= p.smt_bank_min_r:
        es_new = sd.h[i] > sd.h[fi:i].max() + eps
        new = [s_.h[j] > s_.h[jf:j].max() + eps for s_, j, jf in pr]
        if not es_new and sum(new) == 1:                  # a sister makes the new extreme, ES and the other fail
            hit("smt_partial_a")
            _bank(S, sd, pos, tr, ts, c, p, p.smt_partial_a_frac, "smt_partial_a")
            pos["smt_pa"] = True
            if pos["left"]:                               # trail the rest under the latest confirmed short-term swing low (side space)
                for k in range(i - 1, fi, -1):
                    if sd.l[k] < sd.l[k - 1] and sd.l[k] < sd.l[k + 1]:
                        from . import manage as _MG
                        if sd.l[k] - S._tick(p) < c:
                            _MG.raise_stop(pos, sd.l[k] - S._tick(p), trail=True)
                        break
    if p.smt_partial in ("b", "both") and not pos.get("smt_pb_done"):
        st = pos.get("smt_pb")
        if pos.get("t1_done"):                              # the target was hit first: nothing left to warn about
            pos["smt_pb_done"] = True
        elif st is None:
            t1 = pos.get("t1")
            if t1 is not None and t1 - c <= p.smt_partial_b_near * max(t1 - basis, 1e-9):    # near the target: arm
                st = pos["smt_pb"] = dict(armed=i, hs=[float(s_.h[jf:j].max()) for s_, j, jf in pr])
        else:
            if any(s_.h[j] > h0 + eps for (s_, j, jf), h0 in zip(pr, st["hs"])):   # a sister broke its earlier extreme: it confirms
                pos["smt_pb_done"] = True
                hit("smt_partial_b_confirmed")
            elif i - st["armed"] >= p.smt_partial_b_bars:
                hit("smt_partial_b")
                _bank(S, sd, pos, tr, ts, c, p, p.smt_partial_b_frac, "smt_partial_b")
                pos["smt_pb_done"] = True
