"""Package bias_htf, table side (rule_coverage.md section 3 "bias_htf", 45 items; build_log.md).

Everything here is a pure function of COMPLETED daily / weekly / monthly candles (sessions before the row's day) and of the
overnight bars that closed by the table's cut minute (09:30 for the ordinary bias table, each lock time for the draw-lock
tables). `htf.table(..., bx=...)` calls `row_extras` inside its day loop (the lists of live draws are needed there) and
`add_columns` after it (the columns that run over the whole table: IOF, P/D of the 20-day range, MWD, weekly open, NWOG,
objective met, persistence, quarterly shift, weekly %R). `bx` is a JSON string built from Params by `bx_string(p)`;
the empty string adds nothing (the table is then byte for byte the old one).

Columns (all per trading day, known at the table's cut):
  B2    draw_ord / draw_ord_lvl / draw_ord_kind / draw_ord_name   the ordered draw (inefficiency first, then P/D liquidity)
        draw_ext_lvl / draw_ext_name    the nearest inefficiency beyond a liquidity draw (how far the run goes, 104 ~16:18)
  B6    iof / iof_score           institutional order flow on the daily (candle respect + pivot raids)
  A21   pd20 / pd20_pos           premium / discount of the N-session range (bodies or wicks, half / third / ote / deep)
  B5    wk_bias                   the weekly reading (reaction from weekly arrays, else the weekly close flip)
  B7    ob_mt / ob_mt_lvl / how_in / low_in   daily OB mean-threshold state; "high of the week in" (close below 50% of the last
                                        down-close candle) and its mirror "low of the week in" (close above 50% of the last up-close)
  B9    obj_day / obj_week        the previous day's / this week's draw already delivered
  B10   mwd / mwd_case / mwd_zones    month-week-day sequence
  B13   wo_sun / wo_mon / wk_dir / wo_expired     weekly opens, the week's direction, expired at an opposing daily array
  B14   nwog_regime / nwog_returns / nwog_conv / nwog_bias
  M0.1  bc_D / bc_W               nearest unreached draw from the candle's open
  Ep03.12 draw_pd                 draw and premium / discount agree
  B22   qs_state / qs_due / qs_trend
  B20.3 wpr                       weekly Williams %R
  B17.1 react_up / react_dn / fifty     both sides' reaction weights
  Ep08.2 on_range / in_bull_arr / in_bear_arr    overnight range and "stuck inside an HTF array"
  A21   pd20_hi / pd20_lo         the N-session range itself (caption-gap X3-a21-rebalance-to-eq: its EQ is the first draw from a discount / premium)
  B6    first_clue / tug / raid_px / raid_eq   caption-gap X3-a21-eq-after-raid (cc05_002 ~13:28-16:12; built here for targets_partials #1/4 post_raid_cap, the
        owner package bias_htf items 135 / 136 reuse them): the post-raid flip reading, see `post_raid`
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import levels as L

INEFF = ("fvg", "ndog", "nwog", "vi")                  # inefficiency draws (B1): gaps and imbalances


# --------------------------------------------------------------------------------------------------------------
# the table configuration
# --------------------------------------------------------------------------------------------------------------

def bx_string(p) -> str:
    """The htf.table bias_htf configuration implied by Params `p` ("" = nothing extra). Only the columns the switches in
    use need are built; every column is also needed by the study variants that name it, hence the explicit lists."""
    x = {}
    hb = p.htf_bias
    if hb == "ordered" or p.draw_lock_pick in ("ordered", "largest") or p.draw_ext_target or p.draw_first != "off":
        x["ord"] = 1
    from . import bh3                                      # caption-gap pass bias_htf#3/7 (bh3.py)
    if hb in ("iof", "combo2") or p.or_needs_bias or bh3.needs_iof(p):         # (caption-gap T4-or-needs-bias-iof reads the iof column; bias_htf#3/7: cot_gate, hallmarks, bias_dh, ... read it too)
        x["iof"] = [p.iof_days, p.iof_min]
    pd20_on = (hb == "pd20" or p.day_pd == "20d" or p.pd_zone != "half" or "premium_chop" in p.neutral_gate
               or p.cond_pd_tags or p.eq_first_rung or p.ob_location_cap or p.pd60_only_consol)
    if pd20_on:
        x["pd20"] = [p.pd_day_range, int(p.pd_body_multiday), p.pd_zone, list(p.ote_band), int(p.day_pd == "20d"), int(p.pd60_only_consol), float(p.consol_ratio)]
    if p.resist_def in ("htf", "both"):                  # caption-gap L4-resistance-definitions: the weekly state
        x["wk"] = 1
    if hb == "wk" or p.weekly_gate != "off" or p.weekly_open != "off" or p.objective_neutral in ("week", "both")             or p.objective_met_stop in ("week", "both") or "draw_delivered" in p.neutral_gate or hb in ("week_check", "wd_check"):
        x["wk"] = 1
    if hb == "ob_mt" or p.how_rule != "off":
        x["obmt"] = 1
    if p.objective_neutral != "off" or p.objective_met_stop != "off" or "draw_delivered" in p.neutral_gate:
        x["obj"] = 1
    if p.bias_persist:
        x["persist"] = p.bias_persist
    if p.next_array_on_fail:
        x["nof"] = p.nof_days
    if hb == "mwd" or p.mwd_nest != "off" or p.mwd_tf_test or p.mwd_cancel_case or p.mwd_upgrade:
        x["mwd"] = p.mwd_disp_mult
        if p.mwd_tf_test or p.mwd_cancel_case or p.mwd_upgrade:
            x["mwd3"] = [int(p.mwd_tf_test), int(p.mwd_cancel_case), int(p.mwd_upgrade)]       # caption-gap bias_htf#3/7: the per-timeframe test, the case-specific cancel, the case C -> B upgrade
    if p.weekly_open != "off":
        x["wo"] = p.weekly_open_early_days
        x["woa"] = p.weekly_open_array_days
    if hb == "nwog" or p.nwog_regime != "off" or p.nwog_bias != "off" or p.nwog_sr_entries or p.nwog_revert_targets:     # (caption-gap L5-nwog-sr-levels: the regime column is read by nwog_sr_entries)
        x["nwog"] = [p.nwog_leave_adr, p.nwog_returns_cons, p.nwog_converge_pts, p.nwog_bias_reclaim or p.nwog_flip_edge, p.nwog_converge_mode, p.nwog_ref, p.nwog_bias_basis]       # caption-gap BH-B14-NWOG-flip-edge: the reclaim edge, which week's NWOG and the daily-close reclaim basis
    if hb == "candle" or p.bias_candle_tag:
        x["bc"] = "midnight" if p.bias_candle_open == "midnight" else 1
    if hb == "draw_pd":
        x["dpd"] = 1
    if p.qshift_tag or p.qshift_size != 1.0:
        x["qs"] = [p.qs_turn_pct, p.qs_cons_pct, p.qs_due_lo, p.qs_due_hi]
    if p.wpr_tag != "off":
        x["wpr"] = p.wpr_len
    if "fifty_fifty" in p.neutral_gate or p.neutral_5050 == "react":
        x["r5050"] = p.fifty_react_ratio
    if (p.chop_mode != "off" or "premium_chop" in p.neutral_gate) and True:
        x["onr"] = 1
    if p.matrix_tf_lower or p.react_tf_tag:
        x["rtf"] = 1
    if p.deep_run_mult != 1.0:                 # caption-gap E9-deep-discount-reduced (099 ~00:28:59): the weekly deep_run column
        x["deep"] = p.deep_run_weeks
    if p.post_raid_cap:                        # caption-gap X3-a21-eq-after-raid (cc05_002 ~00:15:30): the post-raid columns
        x["pr"] = 1
    from . import bh1                          # caption-gap pass bias_htf#1/7 (bh1.py): the columns / flip configuration of its 35 items
    b1 = bh1.bx_cfg(p)
    if b1:
        x["b1"] = b1
    if bh1.needs_objective(p) or p.org_consol_case or p.no_htf_top_pick:
        x["obj"] = 1                           # the B17.3 objective-met columns (ob_low_touch, the ORG consolidation case, the top-picking ban read them)
    if p.org_consol_case and "nwog" not in x:
        x["nwog"] = [p.nwog_leave_adr, p.nwog_returns_cons, p.nwog_converge_pts, p.nwog_bias_reclaim or p.nwog_flip_edge, p.nwog_converge_mode, p.nwog_ref, p.nwog_bias_basis]      # (the consolidation regime tag)
    if p.wk_po3 and "wk" not in x:
        x["wk"] = 1                            # the weekly draw levels (wk_draw_up / wk_draw_dn) the weekly-PO3 lock aims at
    if p.draw_order == "nearest_tb":
        x["tb"] = p.eq_tol_pts                   # caption-gap BH-B2-draw-by-proximity: the table's draw column breaks near-ties by the opposing arrays in the path
    if p.wick_ce_draw or p.stack_far or p.draw_order == "inefficiency_first":
        x["ord"] = 1                           # (the ordered draw columns the wick CE / stacked gaps / inefficiency-first order rewrite)
    from . import bh2                          # caption-gap pass bias_htf#2/7 (bh2.py): the columns / flip configuration of its items
    b2 = bh2.bx_cfg(p)
    if b2:
        x["b2"] = b2
    if p.bias_neutral == "scalp_week":
        x["wk"] = 1                            # B17-neutral-htf-monday-close: the weekly draw columns (a week without a weekly draw is a scalp week)
    if p.htf_after_draw == "reverse" or p.fast_draw_extend:
        x["obj"] = 1                           # the B17.3 objective-met columns and the weekly draw levels (after_draw_* / fast_draw read them)
        x["wk"] = 1
    if p.tug_required or p.first_clue_neutral:
        x["pr"] = 1                            # the post-raid first_clue / tug columns (items 135 / 136)
    b3 = bh3.bx_cfg(p)                         # caption-gap pass bias_htf#3/7 (bh3.py): the columns / flip configuration of its items
    if b3:
        x["b3"] = b3

    return json.dumps(x, sort_keys=True, separators=(",", ":")) if x else ""


def parse(bx: str) -> dict:
    return json.loads(bx) if bx else {}


# --------------------------------------------------------------------------------------------------------------
# B2: the draw search order
# --------------------------------------------------------------------------------------------------------------

def _is_ineff(name: str) -> bool:
    return name.split("_", 1)[-1] in INEFF


def ordered_draw(draws_up: list, draws_dn: list, pdb: int) -> dict:
    """B2 (065A ~50:00; 104 ~16:18): the draw search order. (1) INEFFICIENCY FIRST - the nearest unrebalanced FVG / VI / opening
    gap on either side sets the direction; (2) none: LIQUIDITY by premium / discount - from discount (pdb = +1) the buy-side
    above a short-term high, from premium (pdb = -1) the sell-side below an old low (pdb = 0: the nearest pool);
    (3) EXTENT: beyond a liquidity draw the nearest inefficiency in the same direction sets how far the run goes
    (draw_ext_lvl). Items are (distance, name, level); a tie between the two sides is neutral.
    Returns draw_ord (+1 / -1 / 0), draw_ord_lvl, draw_ord_kind ("ineff" / "liq" / ""), draw_ord_name, draw_ext_lvl / name."""
    nan = float("nan")
    out = dict(draw_ord=0, draw_ord_lvl=nan, draw_ord_kind="", draw_ord_name="", draw_ext_lvl=nan, draw_ext_name="")
    iu = [x for x in draws_up if _is_ineff(x[1])]
    idn = [x for x in draws_dn if _is_ineff(x[1])]
    pick = None
    if iu or idn:
        a = min(iu) if iu else None
        b = min(idn) if idn else None
        if a and b:
            if a[0] == b[0]:
                return out
            pick = (1, a, "ineff") if a[0] < b[0] else (-1, b, "ineff")
        else:
            pick = (1, a, "ineff") if a else (-1, b, "ineff")
    else:
        lu = [x for x in draws_up if not _is_ineff(x[1])]
        ld = [x for x in draws_dn if not _is_ineff(x[1])]
        if pdb > 0 and lu:
            pick = (1, min(lu), "liq")
        elif pdb < 0 and ld:
            pick = (-1, min(ld), "liq")
        elif lu or ld:
            a = min(lu) if lu else None
            b = min(ld) if ld else None
            if a and b:
                if a[0] == b[0]:
                    return out
                pick = (1, a, "liq") if a[0] < b[0] else (-1, b, "liq")
            else:
                pick = (1, a, "liq") if a else (-1, b, "liq")
    if pick is None:
        return out
    sd, it, kind = pick
    out.update(draw_ord=sd, draw_ord_lvl=float(it[2]), draw_ord_kind=kind, draw_ord_name=it[1])
    if kind == "liq":                                   # (3) the extent: the nearest inefficiency beyond the pool
        pool = draws_up if sd > 0 else draws_dn
        beyond = [x for x in pool if _is_ineff(x[1]) and ((x[2] > it[2]) if sd > 0 else (x[2] < it[2]))]
        if beyond:
            e = min(beyond, key=lambda x: abs(x[2] - it[2]))
            out.update(draw_ext_lvl=float(e[2]), draw_ext_name=e[1])
    return out


# --------------------------------------------------------------------------------------------------------------
# B6: institutional order flow on the daily
# --------------------------------------------------------------------------------------------------------------

def iof_score(o, h, l, c, k: int, n: int) -> int:
    """B6 (cc12_003 ~11:41; 075 ~1:21:40; 099 ~14:56; 102 ~1:42:05): the candle-respect score of the n completed sessions before
    session k [our interpretation of "respect"]. Bullish points: a down-close candle (a bullish OB) that price came back to and
    that held (no later close below its low), an up-close candle that later closes were run through (a close above its high),
    and a pivot low that was raided and reversed at once (the raid bar or the next one closed back above it). Bearish points are
    the mirror: an up-close candle that held as resistance, a down-close candle closed through, a pivot high raided and
    rejected at once. A level that is neither retested nor closed through scores nothing."""
    lo = max(0, k - n)
    s = 0
    for j in range(lo, k - 1):
        later = slice(j + 1, k)
        if c[j] < o[j]:                                              # down-close: bullish OB
            if (c[later] < l[j]).any():
                s -= 1                                               # closed through: support failed
            elif (l[later] <= h[j]).any():
                s += 1                                               # retested and held
        elif c[j] > o[j]:                                            # up-close: bearish OB
            if (c[later] > h[j]).any():
                s += 1                                               # run through: bullish
            elif (h[later] >= l[j]).any():
                s -= 1                                               # retested and held as resistance
    ph, pl = L.pivots(h[:k], l[:k], 1)
    for pv in pl:
        if pv.i < lo or pv.known >= k:
            continue
        m = next((q for q in range(pv.i + 1, k) if l[q] < pv.price), None)
        if m is None:
            continue
        back = c[m] > pv.price or (m + 1 < k and c[m + 1] > pv.price)
        s += 1 if back else -1                                       # raided and reversed at once / raided and left behind
    for pv in ph:
        if pv.i < lo or pv.known >= k:
            continue
        m = next((q for q in range(pv.i + 1, k) if h[q] > pv.price), None)
        if m is None:
            continue
        back = c[m] < pv.price or (m + 1 < k and c[m + 1] < pv.price)
        s += -1 if back else 1
    return s


# --------------------------------------------------------------------------------------------------------------
# A21: premium / discount of the multi-day range
# --------------------------------------------------------------------------------------------------------------

def pd_state(px: float, hi: float, lo: float, zone: str = "half", ote=(0.62, 0.79)) -> tuple:
    """A21 / A21.2 (cc01_004 ~23:59; cc01_006 ~2:07; cc06_004 ~31:39): +1 discount (the buy-side is the draw), -1 premium, 0
    outside the zone, and the position of `px` in the range (0 = low, 1 = high). Zones: "half" below / above the 50% EQ;
    "third" the lower / upper third; "deep" the 0.3 / 0.7 lines (0.2-0.3 deep discount, 0.8-0.9 deep premium); "ote" the
    62-79% retracement band (ote_band) from the extreme: a bullish range retraced to [1 - 0.79, 1 - 0.62] of its height."""
    r = hi - lo
    if not r > 0:
        return 0, float("nan")
    pos = (px - lo) / r
    if zone == "half":
        st = 1 if pos < 0.5 else (-1 if pos > 0.5 else 0)
    elif zone == "third":
        st = 1 if pos <= 1 / 3 else (-1 if pos >= 2 / 3 else 0)
    elif zone == "deep":
        st = 1 if pos <= 0.3 else (-1 if pos >= 0.7 else 0)
    elif zone == "ote":
        a, b = ote
        st = 1 if 1 - b <= pos <= 1 - a else (-1 if a <= pos <= b else 0)
    else:
        raise ValueError(f"pd zone {zone!r}")
    return st, float(pos)


# --------------------------------------------------------------------------------------------------------------
# B10: month / week / day displacement states
# --------------------------------------------------------------------------------------------------------------

def tf_states(o, h, l, c, disp_mult: float = 1.0):
    """B10 (cc06_004 ~1:02-14:47; cc06_005 ~0:46) per bar j (state after bar j completes) [our interpretation]: a timeframe is bullish
    (+1) once a DISPLACEMENT candle - an up-close with a body of at least disp_mult x the mean body of the last 10 bars - closes above
    the last confirmed swing high (the previous bar's high while there is no swing yet): the buying has been induced and the structure
    broken; the bearish mirror (-1). A displacement AGAINST the standing state that does not break the structure only marks it
    correcting (`corr`) - a correction never cancels the bias; the opposite structure break with a displacement (a breaker) is what turns it.
    Returns (state, corr) arrays."""
    n = len(c)
    st = np.zeros(n, int)
    corr = np.zeros(n, int)
    ph, pl = L.pivots(h, l, 1)
    s, cr = 0, 0
    a = b = 0
    last_h = last_l = None
    for j in range(n):
        while a < len(ph) and ph[a].known <= j - 1:
            last_h = ph[a].price
            a += 1
        while b < len(pl) and pl[b].known <= j - 1:
            last_l = pl[b].price
            b += 1
        if j >= 1:
            lo_ = max(0, j - 10)
            avg = float(np.mean(np.abs(c[lo_:j] - o[lo_:j])))
            big = avg > 0 and abs(c[j] - o[j]) >= disp_mult * avg
            ref_h = last_h if last_h is not None else h[j - 1]
            ref_l = last_l if last_l is not None else l[j - 1]
            if big and c[j] > o[j] and c[j] > ref_h:
                s, cr = 1, 0
            elif big and c[j] < o[j] and c[j] < ref_l:
                s, cr = -1, 0
            elif big and s > 0:
                cr = 1 if c[j] < o[j] else 0                 # a counter displacement: correcting; a with-trend one renews
            elif big and s < 0:
                cr = 1 if c[j] > o[j] else 0
        st[j], corr[j] = s, cr
    return st, corr


def mwd_case(sm: int, sw: int, sd: int, cd: int, cw: int) -> tuple:
    """B10 cases from the three states (+ their `corr` flags): returns (direction, case). The highest timeframe with a state
    gives the direction (the monthly drives); case A all three agree and neither week nor day is correcting (buy every daily / 4h
    discount array), B month + week agree (the week clean) and the day corrects or has no state (daily arrays only inside weekly
    arrays), C only the month: the week disagrees, has no state, or is itself correcting (arrays of the month only). With no monthly state the weekly stands in for it (cases A / B), then the daily alone ("D")."""
    top = sm or sw or sd
    if not top:
        return 0, ""
    g = 1 if top > 0 else -1
    wm, ww, dd = sm * g, sw * g, sd * g
    d_ok = dd > 0 and not cd
    w_ok = ww > 0 and not cw                                         # a correcting week is not a clean week (week + day correcting: C)
    if sm:
        if w_ok and d_ok:
            return g, "A"
        if w_ok:
            return g, "B"
        return g, "C"
    if sw:
        return (g, "A" if d_ok else "B") if not cw else (g, "C")
    return g, "D"


# --------------------------------------------------------------------------------------------------------------
# the day loop hook and the whole-table pass
# --------------------------------------------------------------------------------------------------------------

def row_extras(X: dict, px, oh, ol, d_open, wk_open, draws_up, draws_dn, pdb, ru, rd, rw_up, rw_dn, live, es_in):
    """The per-day values that need the lists htf.table builds inside its day loop."""
    nan = float("nan")
    ex = {}
    if "ord" in X:
        ex.update(ordered_draw(draws_up, draws_dn, pdb))
    if "r5050" in X or "rtf" in X:
        ex["react_up"], ex["react_dn"] = ru, rd
        side = 1 if ru > rd else (-1 if rd > ru else 0)
        wk_n = rw_up if side > 0 else (rw_dn if side < 0 else 0)
        ex["react_tf"] = "" if not side else ("W" if wk_n else "D")
        ex["react_wk"] = rw_up - rw_dn
    if "wk" in X:
        ex["react_wk"] = rw_up - rw_dn
        wk_up = [x for x in draws_up if x[1].startswith("W_") or x[1] in ("PWH", "PWL")]
        wk_dn = [x for x in draws_dn if x[1].startswith("W_") or x[1] in ("PWH", "PWL")]
        ex["wk_draw_up"] = min(wk_up)[2] if wk_up else nan
        ex["wk_draw_dn"] = min(wk_dn)[2] if wk_dn else nan
        ex["wk_draw_up_n"] = min(wk_up)[1] if wk_up else ""
        ex["wk_draw_dn_n"] = min(wk_dn)[1] if wk_dn else ""
    if "bc" in X:
        for tag, ref, cls in (("D", d_open, None), ("W", wk_open, "W")):
            ups = [x for x in draws_up if x[2] > max(ref, oh) - 0 and (cls is None or x[1].startswith("W_") or x[1] in ("PWH", "PWL"))]
            dns = [x for x in draws_dn if x[2] < min(ref, ol) + 0 and (cls is None or x[1].startswith("W_") or x[1] in ("PWH", "PWL"))]
            if cls == "W" and not ups and not dns:
                ups = [x for x in draws_up if x[2] > max(ref, oh)]
                dns = [x for x in draws_dn if x[2] < min(ref, ol)]
            a = min(ups, key=lambda x: x[2] - ref) if ups else None
            b = min(dns, key=lambda x: ref - x[2]) if dns else None
            if a and b:
                da, db = a[2] - ref, ref - b[2]
                sd_ = 0 if da == db else (1 if da < db else -1)
                lv = a[2] if sd_ > 0 else (b[2] if sd_ < 0 else nan)
            elif a or b:
                sd_ = 1 if a else -1
                lv = (a or b)[2]
            else:
                sd_, lv = 0, nan
            ex[f"bc_{tag}"], ex[f"bc_{tag}_lvl"] = sd_, float(lv)
    if "ord" in X and "b1" in X:
        from . import bh1
        c1 = X["b1"]
        if c1.get("stack"):
            bh1.stack_far_post(ex, draws_up, draws_dn)
        if c1.get("ofirst") and ex.get("draw_ord"):
            ex["draw"] = ex["draw_ord"]            # caption-gap BH-B2-draw-by-proximity: draw_order 'inefficiency_first' - the table's draw is the ordered pick
    if "onr" in X:
        ex["on_range"] = float(oh - ol)
        bull = bear = 0
        for a in live:
            if a.typ in ("fvg", "ob", "vi") and a.bottom <= px <= a.top:
                bull += a.kind == "bull"
                bear += a.kind == "bear"
        ex["in_bull_arr"], ex["in_bear_arr"] = int(bull), int(bear)
    return ex


def week_open_mon(df: pd.DataFrame, d: pd.DataFrame) -> dict:
    """{session position: open of the first bar of that session's calendar date}: the Monday 00:00 open of B13 (for a week that
    starts later, the first calendar day's 00:00 open)."""
    lab = pd.to_datetime((df.index + pd.Timedelta(hours=7)).date)
    cal = pd.to_datetime(df.index.date)
    m = np.asarray(cal == lab)
    sub = df[m]
    first = sub.groupby(lab[m]).open.first()
    return {t: float(first.get(t, np.nan)) for t in d.index}


def add_columns(out: pd.DataFrame, X: dict, d: pd.DataFrame, w: pd.DataFrame, arrs: list, og: pd.DataFrame, on: pd.DataFrame,
                df: pd.DataFrame, es_pt: float, vi: bool) -> pd.DataFrame:
    """Whole-table columns (see the module docstring). `out` has one row per trading day (index = date)."""
    if not len(out):
        return out
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    kpos = {t.date(): k for k, t in enumerate(d.index)}
    ks = np.array([kpos[x] for x in out.index])
    px = out.px.values.astype(float)
    nan = float("nan")
    # --- A21 P/D of the N-session range
    if "pd20" in X:
        n, bodies, zone, ote, repl = X["pd20"][:5]
        only_consol, c_ratio = (X["pd20"][5], X["pd20"][6]) if len(X["pd20"]) > 6 else (0, 0.25)
        st, ps, rh, rl, cons = [], [], [], [], []
        for k, x in zip(ks, px):
            if k < n:
                st.append(0)
                ps.append(nan)
                rh.append(nan)
                rl.append(nan)
                cons.append(0)
                continue
            hh = np.maximum(o, c)[k - n:k].max() if bodies else h[k - n:k].max()
            ll = np.minimum(o, c)[k - n:k].min() if bodies else l[k - n:k].min()
            s_, p_ = pd_state(float(x), float(hh), float(ll), zone, tuple(ote))
            cs_ = int(abs(float(c[k - 1] - c[k - n])) < c_ratio * float(hh - ll)) if hh > ll else 0      # caption-gap A21-trend-vs-consolidation-first: the net move of the n sessions is small against the body range
            cons.append(cs_)
            if only_consol and not cs_:
                s_ = 0                                       # pd60_only_consol: a trending range gives no premium / discount reading
                from . import bh3 as _bh3
                _bh3.sw("pd60_only_consol")
            st.append(s_)
            ps.append(p_)
            rh.append(float(hh))
            rl.append(float(ll))
        out["pd20"], out["pd20_pos"] = st, ps
        if only_consol:
            out["pd60_consol"] = cons
        out["pd20_hi"], out["pd20_lo"] = rh, rl            # caption-gap X3-a21-rebalance-to-eq: the range (its EQ = the first draw)
        if repl:
            out["pd"] = st
            out["combo"] = [int(r) if r else int(p_) for r, p_ in zip(out.react, out.pd)]
            if "draw_ord" in out:                         # (review fix) the B2 liquidity pick follows the replaced P/D too
                for r_ in np.flatnonzero((out.draw_ord_kind.values == "liq") | (out.draw_ord_kind.values == "")):
                    pdv = int(out.pd.values[r_])
                    du, dd_ = out.draw_up.values[r_], out.draw_dn.values[r_]
                    nu, nd_ = out.draw_up_name.values[r_], out.draw_dn_name.values[r_]
                    if out.draw_ord_kind.values[r_] == "" and not (du == du or dd_ == dd_):
                        continue
                    if _is_ineff(str(nu)) or _is_ineff(str(nd_)):
                        continue                          # an inefficiency decides, P/D is not consulted
                    px_ = out.px.values[r_]
                    if pdv > 0 and du == du:
                        sd_ = 1
                    elif pdv < 0 and dd_ == dd_:
                        sd_ = -1
                    elif du == du and dd_ == dd_:
                        sd_ = 0 if abs(du - px_) == abs(px_ - dd_) else (1 if abs(du - px_) < abs(px_ - dd_) else -1)
                    else:
                        sd_ = 1 if du == du else (-1 if dd_ == dd_ else 0)
                    out.iloc[r_, out.columns.get_loc("draw_ord")] = sd_
                    out.iloc[r_, out.columns.get_loc("draw_ord_lvl")] = (du if sd_ > 0 else dd_) if sd_ else nan
                    out.iloc[r_, out.columns.get_loc("draw_ord_name")] = (nu if sd_ > 0 else nd_) if sd_ else ""
                    out.iloc[r_, out.columns.get_loc("draw_ord_kind")] = "liq" if sd_ else ""
    # --- B6 IOF
    if "iof" in X:
        n, mn = X["iof"]
        sc = np.array([iof_score(o, h, l, c, int(k), n) for k in ks])
        out["iof_score"] = sc
        out["iof"] = np.where(sc >= mn, 1, np.where(sc <= -mn, -1, 0))
        out["combo2"] = [int(r) if r else (int(i) if i else int(p_)) for r, i, p_ in zip(out.react, out.iof, out.pd)]
    # --- B5 weekly bias
    wkstate = None
    if "wk" in X or "wo" in X:
        from .htf import _flip
        fl = _flip(d, w, arrs, ("wk_dc",))
        wkstate = np.array([fl.get(d.index[k], 0) for k in ks])
        rw = out.react_wk.values if "react_wk" in out else np.zeros(len(out))
        out["wk_bias"] = np.where(rw > 0, 1, np.where(rw < 0, -1, wkstate))
    # --- B7 ob_mt state, how_in
    if "obmt" in X:
        from .htf import _flip
        fl = _flip(d, w, arrs, ("ob_mt",))
        out["ob_mt"] = [fl.get(d.index[k], 0) for k in ks]
        obs = [a for a in arrs if a.typ == "ob" and a.tf == "D"]
        lv = []
        for k, s_ in zip(ks, out.ob_mt.values):
            side = "bull" if s_ >= 0 else "bear"
            cand = [a for a in obs if a.known <= k and a.kind == side]
            lv.append(float(cand[-1].ce) if cand else nan)
        out["ob_mt_lvl"] = lv
        wk_of = d.index.to_period("W-FRI")
        how, low = [], []
        for k in ks:
            hit = lo_hit = False
            k0 = next(q for q in range(k, -1, -1) if q == 0 or wk_of[q - 1] != wk_of[k])      # the week's first session
            prior_hi = h[max(0, k0 - 5):k0].max() if k0 > 0 else np.inf
            prior_lo = l[max(0, k0 - 5):k0].min() if k0 > 0 else -np.inf
            for j in range(k - 1, k0 - 1, -1):
                m = next((q for q in range(j - 1, -1, -1) if c[q] < o[q]), None)
                # [our interpretation] the "rally week" precondition (the week's high so far above the last five sessions' highs; not in the
                # rule's words), then a close below 50% of the last down-close candle
                if m is not None and h[k0:j + 1].max() > prior_hi and c[j] < (h[m] + l[m]) / 2:
                    hit = True
                    break
            for j in range(k - 1, k0 - 1, -1):                    # the mirror: low of the week in (a decline week, then a close above 50% of the last up-close)
                m = next((q for q in range(j - 1, -1, -1) if c[q] > o[q]), None)
                if m is not None and l[k0:j + 1].min() < prior_lo and c[j] > (h[m] + l[m]) / 2:
                    lo_hit = True
                    break
            how.append(int(hit))
            low.append(int(lo_hit))
        out["how_in"] = how
        out["low_in"] = low
    # --- B9 objective met
    if "obj" in X:
        dr = out.draw.values
        up, dn = out.draw_up.values, out.draw_dn.values
        od = np.zeros(len(out), int)
        for r in range(1, len(out)):
            if ks[r] != ks[r - 1] + 1:
                continue
            side = dr[r - 1]
            lv = up[r - 1] if side > 0 else dn[r - 1]
            if not side or lv != lv:
                continue
            kk = ks[r - 1]
            oh_ = float(on.at[pd.Timestamp(out.index[r]), "high"]) if pd.Timestamp(out.index[r]) in on.index else -np.inf
            ol_ = float(on.at[pd.Timestamp(out.index[r]), "low"]) if pd.Timestamp(out.index[r]) in on.index else np.inf
            reached = max(h[kk], oh_) >= lv if side > 0 else min(l[kk], ol_) <= lv
            od[r] = int(reached)
        out["obj_day"] = od
        # the week's objective: the nearest weekly-class draw at the week's first row, delivered since
        wk_of = [pd.Timestamp(x).to_period("W-FRI") for x in out.index]
        wobj, ow = {}, np.zeros(len(out), int)
        wk_u = out.wk_draw_up.values if "wk_draw_up" in out else None
        wk_d = out.wk_draw_dn.values if "wk_draw_dn" in out else None
        for r in range(len(out)):
            wk = wk_of[r]
            if wk not in wobj:
                if wk_u is not None:
                    a_, b_ = wk_u[r], wk_d[r]
                    cand = [(abs(x - px[r]), s_, x) for s_, x in ((1, a_), (-1, b_)) if x == x]
                    wobj[wk] = (min(cand)[1], min(cand)[2], r) if cand else None
                else:
                    wobj[wk] = None
            ob = wobj[wk]
            if ob is None or r == ob[2]:
                continue
            s_, lv, r0 = ob
            seg = slice(ks[r0], ks[r])
            oh_ = float(on.at[pd.Timestamp(out.index[r]), "high"]) if pd.Timestamp(out.index[r]) in on.index else -np.inf
            ol_ = float(on.at[pd.Timestamp(out.index[r]), "low"]) if pd.Timestamp(out.index[r]) in on.index else np.inf
            hit = (max(h[seg].max(initial=-np.inf), oh_) >= lv) if s_ > 0 else (min(l[seg].min(initial=np.inf), ol_) <= lv)
            ow[r] = int(hit)
        out["obj_week"] = ow
    # --- B10 MWD
    if "mwd" in X:
        out = _mwd(out, X["mwd"], d, w, arrs, ks, px, X.get("mwd3"))
    # --- B13 weekly open
    if "wo" in X:
        out = _weekly_open(out, X["wo"], d, w, arrs, ks, df, on, X.get("woa", 60))
    # --- B14 NWOG
    if "nwog" in X:
        out = _nwog(out, X["nwog"], d, og, ks, px, es_pt)
    # --- Ep03.12 draw_pd
    if "dpd" in X:
        dr = out.draw.values
        if vi and "vi_up" in out:
            vu, vd = out.vi_up.values, out.vi_dn.values
            vs = np.where(vu == vu, np.where(vd == vd, np.where(np.abs(vu - px) < np.abs(px - vd), 1, -1), 1),
                          np.where(vd == vd, -1, 0))
            dr = np.where(vs != 0, vs, dr)
        out["draw_pd"] = np.where((dr > 0) & (out.pd.values > 0), 1, np.where((dr < 0) & (out.pd.values < 0), -1, 0))
    # --- B17.1 fifty-fifty
    if "r5050" in X:
        ru, rd = out.react_up.values, out.react_dn.values
        mn, mx = np.minimum(ru, rd), np.maximum(ru, rd)
        out["fifty"] = ((mx > 0) & (mn >= X["r5050"] * mx)).astype(int)
    # --- B22 quarterly shift
    if "qs" in X:
        out = _qshift(out, X["qs"], d, ks)
    # --- B20.3 weekly %R
    if "wpr" in X:
        n = int(X["wpr"])
        wh, wl, wc = w.high.values.astype(float), w.low.values.astype(float), w.close.values.astype(float)
        wlast = np.array([kpos.get(t.date(), -1) for t in w["last"]])
        vals = []
        for k in ks:
            done = np.flatnonzero(wlast < k)
            if len(done) < n:
                vals.append(nan)
                continue
            seg = done[-n:]
            hh, ll = wh[seg].max(), wl[seg].min()
            vals.append(float(-100.0 * (hh - wc[done[-1]]) / (hh - ll)) if hh > ll else nan)
        out["wpr"] = vals
    # --- E9-deep-discount-reduced (099 ~00:28:59): +1 = a deep PREMIUM after n straight higher weekly closes (the latest completed close in the top quarter of the last-13-week range), -1 = deep DISCOUNT
    # after n straight lower closes (bottom quarter), 0 otherwise. Completed weeks only [our interpretation of "3-4 weeks of steady one-direction"; fewer than 13 weeks: the range of those available]
    if "deep" in X:
        from . import es3 as _ES3
        wh, wl, wc = w.high.values.astype(float), w.low.values.astype(float), w.close.values.astype(float)
        wlast = np.array([kpos.get(t.date(), -1) for t in w["last"]])
        out["deep_run"] = _ES3.deep_run_column(wh, wl, wc, wlast, ks, int(X["deep"]))
    # --- caption-gap X3-a21-eq-after-raid / X3-b6-tug-of-war-new-ground / X3-one-sided-delivery-first-clue (cc05_002 ~13:28-16:12)
    if "pr" in X:
        out = post_raid(out, o, h, l, c, ks)
    # --- B9 next array on fail (react through the next weekly array) and persistence
    if "nof" in X:
        out = _next_array(out, X["nof"], d, arrs, ks, px, on, o, h, l, c)
    if "persist" in X:
        out = _persist(out, int(X["persist"]), ks, d, w, arrs)
    if "b1" in X:                                         # caption-gap pass bias_htf#1/7 (bh1.py)
        from . import bh1
        out = bh1.add_columns(out, X["b1"], d, w, arrs, ks, px, es_pt)
    return out


# --------------------------------------------------------------------------------------------------------------
# X3: the post-raid reading (first clue / tug of war)
# --------------------------------------------------------------------------------------------------------------

PR_N, PR_RUN, PR_WIN = 20, 5, 40


def _pr_dir(h, l, c, ks) -> tuple:
    """The BEARISH reading of the post-raid state for the rows at daily index `ks` (the sessions before each: index k-1 is the last completed one);
    the bullish reading runs the same code on the mirrored bars. Returns (first_clue, tug, raid_px, raid_eq, no_new_ground) arrays (first_clue, tug, no_new_ground 0 / 1).
      raid       the latest completed session j (within the last 10) that took the highest high of the PR_N (20) sessions before it and closed back
                 below that high - the raid of the buy-side pool with a rejection [our interpretation of "raid and strong rejection"]
      first_clue cc05_002 ~13:28: no short-term low (3-bar pivot) broke in the PR_RUN sessions up to the raid, and one breaks after it
      tug        cc05_002 ~16:12: the last two short-term-high raids (a high through the latest confirmed STH) each closed back below it within one
                 session (no new ground) and the intermediate-term highs step lower (levels.swing_tiers)
      raid_px    the raided high (the later STH of the tug when there is no 20-session raid); raid_eq the EQ of the range [lowest low of the
                 20 sessions before it .. that high]"""
    nan = float("nan")
    n = len(h)
    ph, pl = L.pivots(h, l, 1)
    ref_lo = np.full(n, nan)
    ref_hi = np.full(n, nan)
    a = b = 0
    cur_l = cur_h = nan
    for m in range(n):
        while a < len(pl) and pl[a].known <= m - 1:
            cur_l = pl[a].price
            a += 1
        while b < len(ph) and ph[b].known <= m - 1:
            cur_h = ph[b].price
            b += 1
        ref_lo[m], ref_hi[m] = cur_l, cur_h
    with np.errstate(invalid="ignore"):
        broke = l < ref_lo
        raided = h > ref_hi
    ith = list(L.swing_tiers(h, l, 1)["itl"][0]) if n > 4 else []        # the intermediate-term highs (the tier dict holds (highs, lows))
    clue = np.zeros(len(ks), int)
    tug = np.zeros(len(ks), int)
    ngr = np.zeros(len(ks), int)
    rpx = np.full(len(ks), nan)
    req = np.full(len(ks), nan)
    for r, k in enumerate(ks):
        last = k - 1
        if last < PR_N + 2:
            continue
        j_raid = None
        hr = nan
        for j in range(last, max(last - 10, PR_N) - 1, -1):
            hh = h[j - PR_N:j].max()
            if h[j] > hh and c[j] < hh:
                j_raid, hr = j, float(hh)
                break
        if j_raid is not None:
            rpx[r] = hr
            req[r] = (hr + float(l[j_raid - PR_N:j_raid + 1].min())) / 2
            if (not broke[max(0, j_raid - PR_RUN + 1):j_raid + 1].any()) and broke[j_raid + 1:last + 1].any():
                clue[r] = 1
        ev = [m for m in range(max(1, last - PR_WIN), last + 1) if raided[m]]
        if len(ev) >= 2:
            def failed(m):
                return c[m] < ref_hi[m] or (m + 1 <= last and c[m + 1] < ref_hi[m])
            known_ith = [q.price for q in ith if q.known <= last]
            if failed(ev[-1]) and failed(ev[-2]):
                ngr[r] = 1                                              # X3-b6-tug-of-war-new-ground (item 135): the last two STH raids each closed back below (no new ground), alone
            if failed(ev[-1]) and failed(ev[-2]) and len(known_ith) >= 2 and known_ith[-1] < known_ith[-2]:
                tug[r] = 1
                if rpx[r] != rpx[r]:
                    rpx[r] = float(ref_hi[ev[-1]])
                    req[r] = (rpx[r] + float(l[max(0, last - PR_N):last + 1].min())) / 2
    return clue, tug, rpx, req, ngr


def post_raid(out: pd.DataFrame, o, h, l, c, ks) -> pd.DataFrame:
    """Columns first_clue / tug (+1 buy-side flip, -1 sell-side flip, 0 none) and raid_px / raid_eq (the raided extreme and the EQ of its range)
    for every row; a row where both readings fire is 0. Needs only completed sessions (see `_pr_dir`)."""
    nan = float("nan")
    h, l, c = np.asarray(h, float), np.asarray(l, float), np.asarray(c, float)
    cb, tb, pb, eb, nb = _pr_dir(h, l, c, ks)
    cu, tu, pu, eu, nu = _pr_dir(-l, -h, -c, ks)
    cb_, cu_, tb_, tu_ = cb.astype(bool), cu.astype(bool), tb.astype(bool), tu.astype(bool)
    fc = np.where(cb_ & ~cu_, -1, np.where(cu_ & ~cb_, 1, 0))
    tg = np.where(tb_ & ~tu_, -1, np.where(tu_ & ~tb_, 1, 0))
    use_bear = (fc < 0) | (tg < 0)
    use_bull = (fc > 0) | (tg > 0)
    out["first_clue"], out["tug"] = fc, tg
    out["no_new_ground"] = np.where(nb.astype(bool) & ~nu.astype(bool), -1, np.where(nu.astype(bool) & ~nb.astype(bool), 1, 0))      # the 'no new ground' part alone: tug of item 135 = this AND tier_regime (bh2.finish: tug_spec)
    out["raid_px"] = np.where(use_bear, pb, np.where(use_bull, -pu, nan))
    out["raid_eq"] = np.where(use_bear, eb, np.where(use_bull, -eu, nan))
    return out


# --------------------------------------------------------------------------------------------------------------
# helpers of add_columns
# --------------------------------------------------------------------------------------------------------------

def _valid(a, c, k):
    """An array (htf.Arr) still intact at session k: no close since it was known went through it."""
    cl = c[a.known:k]
    if not len(cl):
        return True
    if a.kind == "bull":
        lvl = a.ce if a.typ == "ob" else a.bottom
        return not cl.min() < lvl
    lvl = a.ce if a.typ == "ob" else a.top
    return not cl.max() > lvl


def _tf_bars(d: pd.DataFrame, rule: str):
    """Completed bars of a timeframe: arrays o, h, l, c and `last` = the session position that completes each bar."""
    g = d.groupby(d.index.to_period(rule))
    pos = {t: k for k, t in enumerate(d.index)}
    last = np.array([pos[x.index[-1]] for _, x in g])
    return (g.open.first().values.astype(float), g.high.max().values.astype(float), g.low.min().values.astype(float),
            g.close.last().values.astype(float), last)


def _mwd(out, disp, d, w, arrs, ks, px, x3=None):
    """B10 month / week / day states and cases (see tf_states / mwd_case). Caption-gap pass bias_htf#3/7 (`x3` = [tf_test, cancel, upgrade], bh3.py): X3-b10-tf-test - the timeframe states come from
    the displacement-after-an-array-touch test and case A needs HH/HL and the timeframe's iof on every timeframe in play (else it is case B); X3-b10-cancel-condition - case B is cancelled (mwd 0) by a
    daily bearish breaker formed after a new daily high, case C by the weekly one (mirror for a bearish sequential); X3-b10-case-c-to-b-upgrade - case C becomes B inside a monthly array holding a weekly
    OB that reacted, and in case B the open and high of every daily down-close candle since the correction began are exported (mwd_levels)."""
    from .htf import _arrays
    from . import bh3 as _b3
    x3 = x3 or [0, 0, 0]
    D = tuple(d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    sdh, cdh = tf_states(*D, disp)
    wo, wh, wl, wc, wlast = _tf_bars(d, "W-FRI")
    mo, mh, ml, mc, mlast = _tf_bars(d, "M")
    sw_, cw_ = tf_states(wo, wh, wl, wc, disp)
    sm_, cm_ = tf_states(mo, mh, ml, mc, disp)
    # arrays of the weekly / monthly timeframe: usable from the session after the bar's last session
    w_arrs = [a for a in arrs if a.tf == "W" and a.typ in ("fvg", "ob")]
    m_arrs = _arrays(mo, mh, ml, mc, "M", lambda i: int(mlast[i]) + 1)
    a_ok = None
    if x3[0]:                                                       # X3-b10-tf-test: the per-timeframe test replaces the states; HH/HL and iof state for case A
        _b3.sw("mwd_tf_test")
        sdh = _b3.tf_state3(*D, _arrays(*D, "D", lambda i: i + 1))
        sw_ = _b3.tf_state3(wo, wh, wl, wc, _arrays(wo, wh, wl, wc, "W", lambda i: i + 1))
        sm_ = _b3.tf_state3(mo, mh, ml, mc, _arrays(mo, mh, ml, mc, "M", lambda i: i + 1))
        a_ok = {tf: (_b3.hh_hl_series(b[1], b[2]), _b3.iof_state_series(*b)) for tf, b in (("D", D), ("W", (wo, wh, wl, wc)), ("M", (mo, mh, ml, mc)))}
    res_dir, res_case, res_zones, mw, ww, dw, lv = [], [], [], [], [], [], []
    for r_, k in enumerate(ks):
        iw = np.flatnonzero(wlast < k)
        im = np.flatnonzero(mlast < k)
        s_w = int(sw_[iw[-1]]) if len(iw) else 0
        c_w = int(cw_[iw[-1]]) if len(iw) else 0
        s_m = int(sm_[im[-1]]) if len(im) else 0
        s_d = int(sdh[k - 1]) if k >= 1 else 0
        c_d = int(cdh[k - 1]) if k >= 1 else 0
        g, case = mwd_case(s_m, s_w, s_d, c_d, c_w)
        if x3[0] and g and case == "A":                             # X3-b10-tf-test: case A also needs HH/HL and the timeframe's iof on the side of every timeframe in play
            need = [("M", im[-1] if len(im) else -1, s_m), ("W", iw[-1] if len(iw) else -1, s_w), ("D", k - 1, s_d)]
            for tf, j, s_ in need:
                if s_ and (j < 0 or a_ok[tf][0][j] != g or a_ok[tf][1][j] != g):
                    case = "B"
                    _b3.hit("mwd_not_case_a")
                    break
        if x3[1] and g:
            _b3.sw("mwd_cancel_case")                                # (live: a sequential exists whose case-specific breaker is tested)
        if x3[1] and g and case in ("B", "C"):                      # X3-b10-cancel-condition: the case-specific timeframe's bearish (bullish) breaker cancels the sequential
            if case == "B" and k >= 1 and _b3.breaker_cancel(*D, k - 1, g):
                g, case = 0, ""
                _b3.hit("mwd_cancel_B")
            elif case == "C" and len(iw) and _b3.breaker_cancel(wo, wh, wl, wc, int(iw[-1]), g):
                g, case = 0, ""
                _b3.hit("mwd_cancel_C")
        if x3[2] and g:
            _b3.sw("mwd_upgrade")                                    # (live: a sequential exists whose case C may be upgraded)
        if x3[2] and g and case == "C" and _b3.case_c_to_b(m_arrs, w_arrs, wo, wc, wh, wl, wlast, k, float(px[r_]), g):
            case = "B"                                              # X3-b10-case-c-to-b-upgrade: the monthly array holds a weekly OB that reacted: month and week agree
            _b3.hit("mwd_c_to_b")
        zones = []
        if g and case in ("B", "C"):
            src = w_arrs if case == "B" else m_arrs
            cl = (wc, wlast) if case == "B" else (mc, mlast)
            for a in src:
                if a.kind != ("bull" if g > 0 else "bear") or a.known > k:
                    continue
                # intact: no weekly / monthly close since it was known went through it
                done = np.flatnonzero((cl[1] < k) & (cl[1] >= a.known))        # (the bar that completed the array is not a test of it)
                cs = cl[0][done]
                lvl = a.ce if a.typ == "ob" else (a.bottom if g > 0 else a.top)
                if len(cs) and ((cs.min() < lvl) if g > 0 else (cs.max() > lvl)):
                    continue
                zones.append((float(a.bottom), float(a.top)))
        res_dir.append(g)
        res_case.append(case)
        res_zones.append(zones)
        mw.append(s_m)
        ww.append(s_w)
        dw.append(s_d)
        lv.append(_b3.dcandle_levels(*D, int(k), g) if (x3[2] and g and case == "B") else ())
    out["mwd"], out["mwd_case"], out["mwd_zones"] = res_dir, res_case, res_zones
    out["mwd_m"], out["mwd_w"], out["mwd_d"] = mw, ww, dw
    if x3[2]:
        arr_ = np.empty(len(lv), dtype=object)
        for i_, v_ in enumerate(lv):
            arr_[i_] = tuple(v_)
        out["mwd_levels"] = arr_
    return out


def _weekly_open(out, early_days, d, w, arrs, ks, df, on=None, max_age: int = 60):
    """B13 (048 ~1:00:10; cc08_001 ~22:58-29:03; cc12_003 ~19:03): the week's opens and direction. wo_sun = the Sunday 18:00 open
    (the first bar of the week's first session), wo_mon = the 00:00 open of that session's calendar day. wk_dir = the weekly bias
    (else the daily combo bias at the week's first row). wo_expired: the week so far reached a daily array opposing wk_dir
    (a bearish FVG / OB / VI above the week's open for a bullish week) - the filter is valid only until then. The row's own overnight
    range (the bars closed by the table's cut) counts too, so the expiry is seen on the morning the array is hit, not a session later;
    arrays older than `max_age` sessions at the week's open are ignored [our interpretation: the table's 60-session lookback, Param
    weekly_open_array_days]."""
    mon = week_open_mon(df, d)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    wk_of = d.index.to_period("W-FRI")
    first_k = {}
    for k in range(len(d)):
        first_k.setdefault(wk_of[k], k)
    nan = float("nan")
    ws, wm, wd, we = [], [], [], []
    wdir_cache = {}
    for r, k in enumerate(ks):
        wk = wk_of[k]
        k0 = first_k[wk]
        ws.append(float(o[k0]))
        wm.append(float(mon.get(d.index[k0], nan)))
        if wk not in wdir_cache:
            v = int(out.wk_bias.values[r]) if "wk_bias" in out else 0
            wdir_cache[wk] = v if v else int(out.combo.values[r])
        wdir = wdir_cache[wk]
        wd.append(wdir)
        exp = 0
        if wdir and k > k0:
            seg_h, seg_l = h[k0:k].max(), l[k0:k].min()
            day_ = pd.Timestamp(out.index[r])
            if on is not None and day_ in on.index:
                seg_h, seg_l = max(seg_h, float(on.at[day_, "high"])), min(seg_l, float(on.at[day_, "low"]))
            for a in arrs:
                if a.tf != "D" or a.typ not in ("fvg", "ob", "vi") or a.known > k0 or a.kind != ("bear" if wdir > 0 else "bull"):
                    continue
                if not _valid(a, c, k0) or k0 - a.known > max_age:
                    continue
                if wdir > 0 and a.bottom > o[k0] and seg_h >= a.bottom:
                    exp = 1
                    break
                if wdir < 0 and a.top < o[k0] and seg_l <= a.top:
                    exp = 1
                    break
        we.append(exp)
    out["wo_sun"], out["wo_mon"], out["wk_dir"], out["wo_expired"] = ws, wm, wd, we
    return out


def _nwog(out, cfg, d, og, ks, px, es_pt):
    """B14 / B14.1-3 from the NWOGs of the opening-gap table `og` (kind "nwog": high, low, ce, up, known, week)."""
    leave_adr, ret_cons, conv_pts, reclaim = cfg[:4]
    conv_mode = cfg[4] if len(cfg) > 4 else "near"
    ref = cfg[5] if len(cfg) > 5 else "current"           # caption-gap BH-B14-NWOG-flip-edge: "previous" = last week's NWOG decides the bias state (030), "current" this week's (046 / 060)
    basis = cfg[6] if len(cfg) > 6 else "px"              # ... "close" = the state moves on the previous DAILY close (a reclaim is a daily close beyond the edge), "px" = the row's 09:30 price (built)
    nan = float("nan")
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    wk_of = d.index.to_period("W-FRI")
    nw = og[og.kind == "nwog"].reset_index(drop=True) if len(og) else og
    cur = {}                                           # week -> index into nw of that week's NWOG
    for j, r in enumerate(nw.itertuples()):
        cur[r.week] = j
    reg, rets, conv, bias = [], [], [], []
    state, state_j = 0, -1
    adr5 = pd.Series(h - l).rolling(5).mean().shift(1).values
    for r, k in enumerate(ks):
        wk = wk_of[k]
        j = cur.get(wk)
        if j is None:
            reg.append("")
            rets.append(0)
            conv.append(0)
            bias.append(0)
            state, state_j = 0, -1
            continue
        jb = j - 1 if (ref == "previous" and j >= 1) else j      # the NWOG that holds the bias state (the regime columns stay on this week's gap)
        gb = nw.iloc[jb]
        g = nw.iloc[j]
        # returns: sessions of this week before k that came back into the gap after a session fully outside it
        k0 = next(q for q in range(len(d)) if wk_of[q] == wk)
        n_ret, prev_out, maxdist = 0, False, 0.0
        for q in range(k0, k):
            inside = l[q] <= g.high and h[q] >= g.low
            if q > k0 and inside and prev_out:
                n_ret += 1
            far = max(h[q] - g.high, g.low - l[q], 0.0)
            maxdist = max(maxdist, far)
            prev_out = not inside
        # convergence: this NWOG within conv_pts of the previous one, or three in a row each closer than the last
        cv = 0
        if j >= 1:
            d1 = abs(g.ce - nw.iloc[j - 1].ce)
            if conv_mode == "near" and conv_pts and d1 <= conv_pts * es_pt:
                cv = 1
            if j >= 2:
                d2 = abs(nw.iloc[j - 1].ce - nw.iloc[j - 2].ce)
                if d1 < d2 and (conv_mode == "shrink" or (conv_pts and d1 <= 2 * conv_pts * es_pt)):
                    cv = 1                    # "shrink": the distance falls across three gaps in a row, whatever its size
        a5 = adr5[k0] if adr5[k0] == adr5[k0] else nan
        if cv or n_ret >= ret_cons:
            rg = "cons"
        elif k > k0 and a5 == a5 and maxdist >= leave_adr * a5 and n_ret <= 1:
            rg = "trend"
        else:
            rg = ""
        # B14.3 hold-until-reclaim
        if state_j != jb:
            state, state_j = 0, jb
        hi, lo, ce = float(gb.high), float(gb.low), float(gb.ce)
        x = float(c[k - 1]) if (basis == "close" and k >= 1) else float(px[r])
        if x > hi:
            state = 1
        elif x < lo:
            state = -1
        else:
            if state > 0:
                lvl = {"low": hi, "ce": ce, "high": lo}[reclaim]     # bullish ends below the high (literal) ... the low (widest hold)
                if x < lvl:
                    state = 0
            elif state < 0:
                lvl = {"low": lo, "ce": ce, "high": hi}[reclaim]     # bearish ends back above the low (058 ~53:46)
                if x > lvl:
                    state = 0
        reg.append(rg)
        rets.append(n_ret)
        conv.append(cv)
        bias.append(state)
    out["nwog_regime"], out["nwog_returns"], out["nwog_conv"], out["nwog_bias"] = reg, rets, conv, bias
    return out


def _qshift(out, cfg, d, ks):
    """B22 (cc05_001 ~5:05-7:26; cc12_001 ~18:43): a major turn or consolidation every 3-4 months. At each session the last 60
    completed sessions' net change against the 60 before: a TURN when the sign changes and the move is at least turn_pct, a
    CONSOLIDATION when their whole range is under cons_pct of the price [our interpretation]; qs_due = the session count since the
    last shift began is inside [due_lo, due_hi] (3-4 months); qs_trend = the 252-session trend sign."""
    turn_pct, cons_pct, lo_d, hi_d = cfg
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    n = len(d)
    state = [""] * (n + 1)
    for k in range(121, n + 1):
        now = c[k - 1] / c[k - 61] - 1
        prev = c[k - 61] / c[k - 121] - 1
        rng = (h[k - 61:k].max() - l[k - 61:k].min()) / c[k - 1]
        if np.sign(now) != np.sign(prev) and abs(now) >= turn_pct:
            state[k] = "turn"
        elif rng < cons_pct:
            state[k] = "cons"
    since, last = {}, None
    cur = None
    for k in range(n + 1):
        if state[k] and (k == 0 or not state[k - 1]):
            cur = k
        since[k] = cur
    st, due, tr = [], [], []
    for k in ks:
        st.append(state[k])
        age = None if since[k] is None else k - since[k]
        due.append(int(age is not None and lo_d <= age <= hi_d))
        tr.append(int(np.sign(c[k - 1] - c[k - 253])) if k >= 253 else 0)
    out["qs_state"], out["qs_due"], out["qs_trend"] = st, due, tr
    return out


def _next_array(out, days, d, arrs, ks, px, on, o, h, l, c):
    """B9 (cc05_015 ~18:45-19:31): a failed daily array is a re-buy at the next weekly array, not a bias change. When the react
    reading is 0 and a bullish daily FVG / OB closed through within the last `days` sessions, a still-intact bullish WEEKLY array
    below it that price traded into since and now holds above its CE gives react +1 (the bearish mirror). react / combo follow; the
    plain reading stays in react0."""
    rc = out.react.values.copy()
    out["react0"] = rc.copy()
    daily = [a for a in arrs if a.tf == "D" and a.typ in ("fvg", "ob")]
    weekly = [a for a in arrs if a.tf == "W" and a.typ in ("fvg", "ob")]
    for r, k in enumerate(ks):
        if rc[r] != 0:
            continue
        for g in (1, -1):
            kind = "bull" if g > 0 else "bear"
            # failed within the window: intact before it, closed through by now
            failed = [a for a in daily if a.kind == kind and a.known <= k and k - a.known <= 60
                      and _valid(a, c, max(a.known, k - days)) and not _valid(a, c, k)]
            if not failed:
                continue
            far = min(a.bottom for a in failed) if g > 0 else max(a.top for a in failed)
            for a in weekly:
                if a.kind != kind or a.known > k or not _valid(a, c, k):
                    continue
                if (g > 0 and a.top <= far) or (g < 0 and a.bottom >= far):
                    lo = max(a.known, k - days - 1)
                    if lo >= k:
                        continue
                    touched = (l[lo:k].min() <= a.top) if g > 0 else (h[lo:k].max() >= a.bottom)
                    if touched and ((px[r] > a.ce) if g > 0 else (px[r] < a.ce)):
                        rc[r] = g
                        break
            if rc[r]:
                break
    out["react"] = rc
    out["combo"] = [int(r_) if r_ else int(p_) for r_, p_ in zip(rc, out.pd.values)]
    if "combo2" in out:                                   # (review fix) combo2 follows the new react too
        out["combo2"] = [int(r) if r else (int(i) if i else int(p_)) for r, i, p_ in zip(rc, out.iof, out.pd)]
    return out


def _persist(out, n, ks, d, w, arrs):
    """B9 (cc05_003 ~1:34:51): two down days inside an uptrend are a retracement, not a flip. For each reading column the new
    non-zero sign opposite to the standing one is accepted only after it has shown for `n` sessions in a row, or when the close-
    based flip column (ob_mt, wk_dc, ...) already agrees with it; until then the standing sign holds. 0 readings stay 0. The
    plain readings are kept as <col>0."""
    from .htf import _flip
    fl = _flip(d, w, arrs, ("ob_mt", "wk_dc"))
    flip = np.array([fl.get(d.index[k], 0) for k in ks])
    for col in ("react", "draw", "pd", "combo", "combo2", "draw_ord", "iof"):
        if col not in out:
            continue
        raw = out[col].values.astype(int)
        if col + "0" not in out:
            out[col + "0"] = raw.copy()
        res, stand, cnt = raw.copy(), 0, 0
        for i, v in enumerate(raw):
            if v == 0:
                cnt = 0                                   # (review fix) "in a row": a neutral reading breaks the run
                continue
            if stand == 0 or v == stand:
                stand, cnt = v, 0
                continue
            cnt += 1
            if cnt >= n or flip[i] == v:
                stand, cnt = v, 0
            else:
                res[i] = stand
        out[col] = res
        if col == "draw_ord" and "draw_ord_lvl" in out:   # (review fix) the held side's level, so the sign and the level agree
            for i in np.flatnonzero(res != raw):
                up_ = res[i] > 0
                src_l = out["draw_up"] if up_ else out["draw_dn"]
                src_n = out["draw_up_name"] if up_ else out["draw_dn_name"]
                out.iloc[i, out.columns.get_loc("draw_ord_lvl")] = src_l.iloc[i]
                out.iloc[i, out.columns.get_loc("draw_ord_name")] = src_n.iloc[i]
                out.iloc[i, out.columns.get_loc("draw_ord_kind")] = "held"
    return out


# --------------------------------------------------------------------------------------------------------------
# B20: COT / open interest loaders (files are optional; no file = no tag)
# --------------------------------------------------------------------------------------------------------------

COT_DIR = Path("data/mentorship/cot")
OI_FILE = Path("data/mentorship/ES_oi.csv")
_COT: dict = {}


def load_cot(market: str = "E-MINI S&P 500", folder: Path | None = None) -> pd.DataFrame | None:
    """B20.1 (cc10_001 ~8:48; cc12_003 ~4:25): the CFTC commitments of traders for one market, from CSV / TXT files in
    data/mentorship/cot (the legacy 'futures only' report: 'Market and Exchange Names', 'As of Date in Form YYYY-MM-DD',
    'Commercial Positions-Long (All)', 'Commercial Positions-Short (All)'; names are matched case-insensitively and any
    'long' / 'short' commercial column pair is accepted). Returns a frame indexed by the first session on which the report is
    USABLE - the report date is a Tuesday, released Friday 15:30, so it is usable from the next session after the release
    (Monday) - with the commercial net position, or None when there is no file."""
    folder = folder or COT_DIR
    key = (market, str(folder))
    if key in _COT:
        return _COT[key]
    parts = []
    if folder.exists():
        for f in sorted(list(folder.glob("*.csv")) + list(folder.glob("*.txt"))):
            try:
                x = pd.read_csv(f, low_memory=False)
            except Exception:
                continue
            cols = {c.strip().lower(): c for c in x.columns}
            nm = next((cols[c] for c in cols if c.startswith("market and exchange") or c in ("market_and_exchange_names",)), None)
            dt = next((cols[c] for c in cols if "as of date" in c and "yyyy-mm-dd" in c or c in ("report_date_as_yyyy-mm-dd",)), None)
            lg = next((cols[c] for c in cols if c.startswith("commercial positions-long") or c == "comm_positions_long_all"), None)
            sh = next((cols[c] for c in cols if c.startswith("commercial positions-short") or c == "comm_positions_short_all"), None)
            if None in (dt, lg, sh):
                continue
            if nm is not None:
                x = x[x[nm].astype(str).str.upper().str.contains(market.upper(), regex=False)]
            if not len(x):
                continue
            parts.append(pd.DataFrame({"rep": pd.to_datetime(x[dt]), "net": pd.to_numeric(x[lg], errors="coerce")
                                       - pd.to_numeric(x[sh], errors="coerce")}))
    try:                                                           # caption-gap B20-cot-data-spec (bias_htf#3/7): the CFTC legacy futures-only annual archives (deacot{year}.zip, cot.py) feed the same tag
        from . import cot as _cot
        z = _cot.load_reports(market, folder)
        if z is not None:
            parts.append(pd.DataFrame({"rep": pd.to_datetime(z.report_date), "net": z.net}))
    except Exception:
        pass
    if not parts:
        _COT[key] = None
        return None
    t = pd.concat(parts).dropna().drop_duplicates("rep").sort_values("rep")
    t["usable"] = t.rep + pd.Timedelta(days=6)                     # Tue report -> Friday release -> usable Monday
    _COT[key] = t.set_index("usable")[["rep", "net"]]
    return _COT[key]


def cot_state(day, tbl: pd.DataFrame | None, weeks: int = 52) -> int:
    """B20.1: +1 when the latest report usable at `day` has the commercial net above the midpoint of its trailing 52-week
    high-low range (a buying / hedging program), -1 below, 0 without data or history."""
    if tbl is None or not len(tbl):
        return 0
    t = tbl[tbl.index <= pd.Timestamp(day)]
    if len(t) < 8:
        return 0
    t = t.iloc[-weeks:]
    hi, lo = float(t.net.max()), float(t.net.min())
    if hi <= lo:
        return 0
    mid = (hi + lo) / 2
    return 1 if t.net.iloc[-1] > mid else (-1 if t.net.iloc[-1] < mid else 0)


OI_ROOTS = {"ES": "ES", "MES": "ES", "SPX": "ES", "SPY": "ES", "SP": "ES", "NQ": "NQ", "MNQ": "NQ", "NDX": "NQ", "QQQ": "NQ", "NASDAQ": "NQ"}
OI_READS: list = []                       # every open-interest file load_oi opened (the own-market check in load_oi_for reads it)


def oi_root(symbol) -> str:
    """B20-oi-own-market-only (cc10_003 ~39:38): the open-interest file root of the market a symbol trades: ES / MES / SPX / SPY -> ES, NQ / MNQ / NDX / QQQ -> NQ (an index or ETF stands for the futures
    market it follows, so the SPX-signals-traded-as-SPY runs keep their S&P tag); any other symbol is its own root (its own file, no file = no tag); no symbol is the S&P (the original single file)."""
    if not symbol:
        return "ES"
    s = "".join(ch for ch in str(symbol).upper() if ch.isalpha())
    return OI_ROOTS.get(s, s or "ES")


def oi_path(symbol) -> Path:
    r = oi_root(symbol)
    return OI_FILE if r == "ES" else OI_FILE.with_name(f"{r}_oi.csv")


def load_oi_for(symbol) -> pd.Series | None:
    """The roll-summed open interest of the traded market ONLY (data/mentorship/<ROOT>_oi.csv); never another market's series (open interest 'is not something that can be shared'). None without that file."""
    path = oi_path(symbol)
    n0 = len(OI_READS)
    out = load_oi(path)
    opened = {Path(x).name for x in OI_READS[n0:]}
    want = {path.name}
    if opened - want:                                 # a real check: nothing but the own-market file was opened
        raise AssertionError(f"oi lookup for {symbol!r} opened {sorted(opened - want)}: only {sorted(want)} is allowed")
    return out


def load_oi(path: Path | None = None) -> pd.Series | None:
    """B20.2 (cc05_003 ~58:26; cc12_003 ~10:42): daily open interest of the futures, ROLL-SUMMED (all listed contracts of the
    day added, so the roll does not read as a change). File: a CSV with a date column (ts_event / date) and 'quantity' (the
    Databento statistics feed, stat_type 9 = open interest; other stat types are ignored) or an 'open_interest' column, one row
    per contract per day. Returns a Series indexed by the session date, or None without a file."""
    path = path or OI_FILE
    if not path.exists():
        return None
    OI_READS.append(str(path))
    x = pd.read_csv(path)
    cols = {c.lower(): c for c in x.columns}
    dc = next((cols[c] for c in ("ts_event", "date", "ts_recv") if c in cols), None)
    qc = next((cols[c] for c in ("quantity", "open_interest", "oi") if c in cols), None)
    if dc is None or qc is None:
        return None
    if "stat_type" in cols:
        x = x[x[cols["stat_type"]] == 9]
    ts = pd.to_datetime(x[dc], utc=True).dt.tz_convert("America/New_York")
    s = pd.Series(pd.to_numeric(x[qc], errors="coerce").values, index=ts.dt.tz_localize(None).dt.normalize()).dropna()
    return s.groupby(level=0).sum().sort_index()


def oi_change(oi: pd.Series | None, day, days: int = 10) -> float | None:
    """The % change of the roll-summed open interest over the `days` sessions before `day` (data of the prior session on)."""
    if oi is None or not len(oi):
        return None
    s = oi[oi.index < pd.Timestamp(day)]
    if len(s) <= days:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - days] - 1)


# --------------------------------------------------------------------------------------------------------------
# B19 / B17.5: intermarket values of PRIOR sessions from the free daily data (data/mentorship/yahoo)
# --------------------------------------------------------------------------------------------------------------

YAHOO = Path("data/mentorship/yahoo")
_IMD: dict = {}


def _daily(name: str) -> pd.DataFrame | None:
    if name in _IMD:
        return _IMD[name]
    f = YAHOO / f"{name}_1d.csv"
    out = None
    if f.exists():
        s = pd.read_csv(f)
        s.columns = [c.lower() for c in s.columns]
        s["date"] = pd.to_datetime(s["date"].astype(str).str[:10])
        for k in ("open", "high", "low", "close"):
            s[k] = pd.to_numeric(s[k], errors="coerce")
        out = s.dropna(subset=["close"]).set_index("date").sort_index()
    _IMD[name] = out
    return out


def im_flags(day, p) -> dict:
    """The intermarket flags for trading day `day`, from sessions BEFORE it only (the daily files are indexed by session date;
    `day`'s own row is never read):
      dxy_hi      B19.1 (031 ~7:54; 036 ~59:00; 045 ~42:05): the dollar's prior close is above the highest high of the p.dxy_gate_days
                  sessions before it and above the close before that (a new range high and rising)
      bond_range  B19.3 (061 ~1:05:42; cc10_008 ~8:47): the 10-year yield's closes of the last p.bond_range_days sessions span
                  less than p.bond_range_frac of the span of the last 60 sessions (bonds in a range: all markets consolidate)
      bond_dir    B19.3 / B57: -1 when yields rose over the last p.bond_range_days sessions (bonds falling: bearish for stocks),
                  +1 when they fell
      decoupled   B17.5 (045 ~1:01:43; 046 ~1:06; 090 ~41:00): the S&P 500 and the Nasdaq 100 are out of step - the correlation of
                  their daily returns over the last p.decouple_days sessions is under p.decouple_corr, or the prior session's
                  returns have opposite signs and both exceed 0.2% [our interpretation]"""
    key = (str(day), p.dxy_gate_days, p.bond_range_days, p.bond_range_frac, p.decouple_days, p.decouple_corr)
    c = _IMD.setdefault("_flags", {})
    if key in c:
        return c[key]
    out = {}
    ts = pd.Timestamp(day)
    x = _daily("DXY")
    if x is not None:
        x = x[x.index < ts]
        n = p.dxy_gate_days
        if len(x) > n + 2:
            hi = float(x.high.iloc[-1 - n:-1].max())
            out["dxy_hi"] = bool(x.close.iloc[-1] > hi and x.close.iloc[-1] > x.close.iloc[-2])
    x = _daily("TNX")
    if x is not None:
        x = x[x.index < ts]
        n = p.bond_range_days
        if len(x) >= 60:
            span_n = float(x.close.iloc[-n:].max() - x.close.iloc[-n:].min())
            span_60 = float(x.close.iloc[-60:].max() - x.close.iloc[-60:].min())
            out["bond_range"] = bool(span_60 > 0 and span_n < p.bond_range_frac * span_60)
            ch = float(x.close.iloc[-1] - x.close.iloc[-1 - n])
            out["bond_dir"] = -1 if ch > 0 else (1 if ch < 0 else 0)
    a, b = _daily("GSPC"), _daily("NDX")
    if a is not None and b is not None:
        r = pd.concat([a.close[a.index < ts].pct_change(), b.close[b.index < ts].pct_change()], axis=1, keys=["a", "b"]).dropna()
        n = p.decouple_days
        if len(r) >= n:
            w = r.iloc[-n:]
            corr = float(w.a.corr(w.b)) if w.a.std() > 0 and w.b.std() > 0 else 1.0
            last = r.iloc[-1]
            opp = bool(last.a * last.b < 0 and abs(last.a) > 0.002 and abs(last.b) > 0.002)
            out["decoupled"] = bool(corr < p.decouple_corr or opp)
            out["dec_corr"] = corr
    if len(c) > 5000:
        c.clear()
    c[key] = out
    return out
