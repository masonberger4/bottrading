"""Package bias_htf, engine side (rule_coverage.md section 3 "bias_htf"; build_log.md).

The bias_htf switches that act on the bar loop. The daily columns they read are built by `bias_htf.py` inside `htf.table`
(bias_htf.bx_string(Params) names the ones in use); this module turns them into

  want_at(ctx, p, session, i)        the day's bias side for a session (htf_bias), read from the table row KNOWN at that bar:
                                     the 09:30 row from 09:30 on, before it the row cut at the latest lock time <= the bar
  plan(P, ctx, hist, p, bias)        day-level tags on the DayPlan (reporting; no decision reads them)
  side_ok / order_ok / gate / scalp_now / size_mult    the hooks daycontext.side_ok, order_ok, gate, scalp_now and
                                     entries.size_mult call, so all three engines (main, Silver Bullet, Ma Deuce) obey them
  ordered_side / ext_target / tf_lower_pref / cond_relock    the draw-lock helpers strategy.mark_levels / _lock_step call

Nothing here reads a bar after the one the caller passes (i = the last CLOSED bar); every daily value is a table column or an
intermarket value of a PRIOR session. Interpretations the sources do not pin down are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import bias_htf as BH

PRE_END = 570                                           # the 09:30 open: the ordinary bias table's cut

COL = {"ordered": "draw_ord", "nwog": "nwog_bias", "wk": "wk_bias", "ob_mt": "ob_mt", "draw_pd": "draw_pd"}


def bias_col(p) -> str:
    """The htf-table column Params.htf_bias reads."""
    if p.htf_bias == "candle":
        return "bc_" + p.bias_candle
    return COL.get(p.htf_bias, p.htf_bias)


def _i(v) -> int:
    try:
        return 0 if v is None or v != v else int(v)
    except Exception:
        return 0


def bias_value(row, p) -> int:
    """The htf_bias reading of a table row (0 = neutral / unknown)."""
    if row is None or p.htf_bias == "off":
        return 0
    v = _i(row.get(bias_col(p)))
    if p.objective_neutral in ("day", "both") and _i(row.get("obj_day")):
        return 0                                         # B9: the previous day's draw was delivered: neutral
    if p.objective_neutral in ("week", "both") and _i(row.get("obj_week")):
        return 0
    return v


def row_for(ctx, session: str, i: int):
    """The htf-table row known at closed bar i: the 09:30 table from 09:30 on; before it the table cut at the latest lock time
    that is not after the bar's start (a pre-open session must never read the 09:30 overnight range); None when there is none."""
    if ctx.t[i] >= PRE_END:
        return getattr(ctx, "bias_row", None)
    cuts = getattr(ctx, "bias_by_cut", None) or {}
    ok = [m for m in cuts if m <= ctx.t[i] and m < PRE_END]
    return cuts[max(ok)] if ok else None


def tue_open_ref(ctx, i: int, at: str = "0930") -> tuple:
    """Params.tue_open_ref: (monday_is_a_holiday, the Tuesday opening price) of the current week - `at` "0930" (indices: the 09:30 open) or "midnight" (FX,
    Params.tue_open_time: the 00:00 open). The open is known only once its bar has closed (today's `_open_known`; later in the week it is read from the
    completed Tuesday session's frame - the midnight bar only if the frame holds it), else None."""
    from datetime import timedelta
    from .calendar import is_trading_day
    from .strategy import _open_known
    d = ctx.day
    mon = d - timedelta(days=d.weekday())
    if is_trading_day(mon):
        return False, None
    tue = mon + timedelta(days=1)
    if d < tue:
        return True, None
    if d == tue:
        return True, _open_known(ctx, at, i)
    for x in reversed(getattr(ctx, "hist", [])):
        if x.index[0].date() == tue:
            m = x.index.hour * 60 + x.index.minute
            r = x[m >= 570] if at == "0930" else x[m == 0]
            return True, (float(r.open.iloc[0]) if len(r) else None)
    return True, None


def want_at(ctx, p, session: str, i: int) -> int:
    """B3 / M0.1 the bias side (htf_bias) a session may trade at closed bar i; 0 = neutral or unknown."""
    if p.htf_bias == "off":
        return 0
    row = row_for(ctx, session, i)
    c = ctx.__dict__.setdefault("_bh_want", {})
    k = (id(row) if row is not None else None)
    if k not in c:
        c[k] = bias_value(row, p)
    if p.carry_weekly_draw:
        from . import dwc3 as _D3                    # caption-gap N10-unmet-target-carries-to-monday: the carried draw's side when the table has none; neutral once it traded
        return _D3.want_override(ctx, p, c[k])
    return c[k]


# --------------------------------------------------------------------------------------------------------------
# the day's state
# --------------------------------------------------------------------------------------------------------------

class State:
    """What the table row (and the day's intermarket values) say for one session: a block reason for every session (`block`) or only
    before 09:30 (`block_pre`: "wait for 09:30"), blocked sides by reason, a scalp reason, tags."""
    __slots__ = ("block", "block_pre", "sides", "scalp", "tags")

    def __init__(self):
        self.block = None
        self.block_pre = None
        self.sides: dict = {}
        self.scalp = ""
        self.tags: set = set()


def _adr5(ctx, p):
    P = getattr(ctx, "dplan", None)
    return None if P is None else P.info.get("adr5_prev")


def active(p) -> bool:
    """Any bias_htf switch that gates or reshapes trades is on (the hooks return at once otherwise)."""
    return bool(
        p.htf_bias != "off" or p.weekly_gate != "off" or p.how_rule != "off" or p.nwog_regime != "off"
        or p.nwog_bias != "off" or p.weekly_open != "off" or p.objective_met_stop != "off" or p.neutral_gate
        or p.neutral_5050 != "off" or p.decoupled_mode != "off" or p.smt_both != "off" or p.chop_mode != "off"
        or p.dxy_gate != "off" or p.bond_range != "off" or p.bond_dir != "off" or p.cot_tag != "off" or p.oi_tag != "off"
        or p.wpr_tag != "off" or p.judas_required != "off" or p.bellwether_15m != "off" or p.news_topdown != "off"
        or p.no_narrative_scalp or p.mwd_nest != "off" or p.midnight_confirm != "off" or p.mmbm_zone != "off"
        or p.bias_neutral == "scalp")


_WARNED: set = set()


def _warn_once(key: str, msg: str) -> None:
    import warnings
    if key not in _WARNED:
        _WARNED.add(key)
        warnings.warn(msg, stacklevel=3)


def im_state(ctx, p) -> State:
    """The row-independent part (intermarket values of PRIOR sessions, COT / OI): cached per day."""
    c = ctx.__dict__.setdefault("_bh_cache", {})
    if "im" in c:
        return c["im"]
    S = State()
    day = ctx.day
    f = BH.im_flags(day, p)
    if p.dxy_gate != "off" and f.get("dxy_hi"):               # B19.1: the dollar closed above its 20-day high and rising
        S.tags.add("dxy_hi")
        if p.dxy_gate == "block":
            S.sides["dxy_gate"] = (1,)                        # no ES longs while the dollar rallies (031 ~7:54; 045 ~42:05)
    if p.bond_range != "off" and f.get("bond_range"):         # B19.3: bonds in a range -> all markets consolidate
        S.tags.add("bond_range")
        if p.bond_range == "scalp":
            S.scalp = S.scalp or "bond_range"
        elif p.bond_range == "skip":
            S.block = S.block or "bond_range"
    if p.bond_dir != "off" and f.get("bond_dir", 0):
        S.tags.add("bond_up" if f["bond_dir"] > 0 else "bond_dn")
        if p.bond_dir == "filter" and f["bond_dir"] < 0:
            S.sides["bond_dir"] = (1,)                        # falling bonds (rising yields) hold equity rallies back (061 ~1:05:42)
    dec = bool(f.get("decoupled"))
    if dec:
        S.tags.add("decoupled")
        if p.decoupled_mode == "scalp":
            S.scalp = S.scalp or "decoupled"
        elif p.decoupled_mode == "skip":
            S.block = S.block or "decoupled"
    if p.cot_tag != "off":
        tbl = BH.load_cot(p.cot_market)
        if tbl is None:
            _warn_once("cot", "cot_tag is on but there is no COT file in data/mentorship/cot: the tag is inert (B20.1)")
        st = BH.cot_state(day, tbl)
        if st:
            S.tags.add("cot_buy" if st > 0 else "cot_sell")
            if p.cot_tag == "filter":
                S.sides["cot"] = (-st,)
    if p.oi_tag != "off":
        oi = BH.load_oi()
        if oi is None:
            _warn_once("oi", "oi_tag is on but there is no open-interest file (data/mentorship/ES_oi.csv): the tag is inert (B20.2)")
        ch = BH.oi_change(oi, day, p.oi_days)
        if ch is not None and abs(ch) >= p.oi_pct:
            S.tags.add("oi_rise" if ch > 0 else "oi_drop")      # a plain change tag (the rule's "drop into HTF support" needs the array state: not built)
    c["im"] = S
    return S


def _chop(row, adr) -> str:
    """Ep08.2 / B17 premium_chop [our interpretation]: "stuck at a premium array or in chop": the 09:30 price sits inside a daily /
    weekly FVG / OB / VI (in_bull_arr / in_bear_arr) or the overnight range is narrower than chop_on_adr x ADR5."""
    if row is None:
        return ""
    why = []
    if _i(row.get("in_bear_arr")) or _i(row.get("in_bull_arr")):
        why.append("in_array")
    rng = row.get("on_range") if row.get("_use_on", True) else None          # caption-gap N8-overnight-not-precursor (cc10_009 ~00:00:55): n8_use_overnight False leaves the overnight range out
    if adr and rng == rng and rng is not None and rng < row.get("_chop_frac", 0.35) * adr:
        why.append("on_range")
    return "+".join(why)


def row_state(ctx, p, session: str, i: int) -> State:
    """The table-row part of the day's state at closed bar i, cached per row."""
    row = row_for(ctx, session, i)
    c = ctx.__dict__.setdefault("_bh_cache", {})
    k = ("row", id(row) if row is not None else None)
    if k in c:
        return c[k]
    S = State()
    if row is None:
        c[k] = S
        return S
    adr = _adr5(ctx, p)
    # B17.3 / B9: the objective of the day / week is met: stop (neutral is want_at)
    od, ow = _i(row.get("obj_day")), _i(row.get("obj_week"))
    if (p.objective_met_stop in ("day", "both") and od) or (p.objective_met_stop in ("week", "both") and ow):
        S.block = S.block or "objective_met"
    # B17 neutral_gate tests
    mode = p.neutral_gate_mode
    for test in p.neutral_gate:
        hit = ""
        pre = False
        if test == "fifty_fifty" and _i(row.get("fifty")):
            hit = "fifty_fifty"
        elif test == "premium_chop":
            hit = "premium_chop" if _chop(dict(row, _chop_frac=p.chop_on_adr, _use_on=p.n8_use_overnight), adr) else ""
            pre = True                                        # "stuck ... wait for 09:30" (010 ~14:05; Ep 08)
        elif test == "draw_delivered" and (od or ow):
            hit = "draw_delivered"
        elif test == "range_market":
            rr = getattr(getattr(ctx, "dplan", None), "info", {}).get("drr_ng")
            hit = "range_market" if rr else ""
        elif test == "decoupled" and "decoupled" in im_state(ctx, p).tags:
            hit = "decoupled"
        if not hit:
            continue
        S.tags.add("ng_" + hit)
        if mode == "skip":
            if pre:
                S.block_pre = S.block_pre or "ng_" + hit
            else:
                S.block = S.block or "ng_" + hit
        elif mode == "scalp":
            S.scalp = S.scalp or "ng_" + hit
    if p.neutral_5050 == "react" and _i(row.get("fifty")):       # B17.1: both sides have equal reaction weight
        S.tags.add("fifty_fifty")
        S.block = S.block or "fifty_fifty"
    # Ep08.2 chop_mode
    if p.chop_mode != "off":
        ch = _chop(dict(row, _chop_frac=p.chop_on_adr, _use_on=p.n8_use_overnight), adr)
        if ch and not p.chop_in_array:
            ch = "on_range" if "on_range" in ch else ""
        if ch:
            S.tags.add("chop_" + ch.replace("+", "_"))
            if p.chop_mode == "skip":
                S.block_pre = S.block_pre or "chop"           # wait for 09:30 to reveal direction (Ep 08)
            elif p.chop_mode == "skip_day":
                S.block = S.block or "chop"
            elif p.chop_mode == "scalp":
                S.scalp = S.scalp or "chop"
    # B5 weekly gate
    wk = _i(row.get("wk_bias"))
    if p.weekly_gate != "off" and wk:
        S.tags.add("wk_up" if wk > 0 else "wk_dn")
        if p.weekly_gate == "filter":
            S.sides["weekly_gate"] = (-wk,)                   # intraday dips in a bullish week are buys (064 ~1:44:34)
    # B7 high of the week in
    if p.how_rule != "off" and (_i(row.get("how_in")) or _i(row.get("low_in"))):
        hi_, lo_ = _i(row.get("how_in")), _i(row.get("low_in"))
        if hi_:
            S.tags.add("how_in")
        if lo_:
            S.tags.add("low_in")
        blocked = []
        if hi_ and p.how_rule in ("no_long", "both"):
            blocked.append(1)                                 # a close below 50% of the last down-close candle: high of the week
        if lo_ and p.how_rule in ("no_short", "both"):
            blocked.append(-1)                                # the mirror: a close above 50% of the last up-close candle: low of the week
        if blocked:
            S.sides["how"] = tuple(blocked)
    # B14 NWOG regime and bias
    rg = row.get("nwog_regime") or ""
    if p.nwog_regime != "off" and rg:
        S.tags.add("nwog_" + rg)
        if rg == "cons":
            if p.nwog_regime == "scalp":
                S.scalp = S.scalp or "nwog_cons"
            elif p.nwog_regime == "skip":
                S.block = S.block or "nwog_cons"
    nb = _i(row.get("nwog_bias"))
    if p.nwog_bias != "off" and nb:
        S.tags.add("nwog_up" if nb > 0 else "nwog_dn")
        if p.nwog_bias == "filter":
            S.sides["nwog_bias"] = (-nb,)
    # B20.3 weekly %R
    w = row.get("wpr")
    if p.wpr_tag != "off" and w is not None and w == w:
        ex = 1 if w <= -80 else (-1 if w >= -20 else 0)       # -80 ideal long, -20 ideal short (cc12_002 ~12:17)
        if ex:
            S.tags.add("wpr_long" if ex > 0 else "wpr_short")
            if p.wpr_tag == "filter":
                S.sides["wpr"] = (-ex,)
    # B22 quarterly shift
    if p.qshift_tag and row.get("qs_state") is not None:
        if row.get("qs_state"):
            S.tags.add("qs_" + str(row["qs_state"]))
        if _i(row.get("qs_due")):
            S.tags.add("qs_due")
    # M0.1 / Ep02.6: no narrative -> scalp (bias_neutral="scalp" is the same reading with the htf_bias column)
    if p.bias_neutral == "scalp" and p.htf_bias != "off":
        if want_at(ctx, p, session, i) == 0:
            S.scalp = S.scalp or "bias_neutral"
    if p.no_narrative_scalp:
        col = bias_col(p) if p.htf_bias != "off" else "combo"
        if _i(row.get(col)) == 0 and not (S.scalp):
            S.scalp = "no_narrative"                          # Ep02.6: no daily narrative -> intraday scalps, small targets
    c[k] = S
    return S


# --------------------------------------------------------------------------------------------------------------
# the DayPlan
# --------------------------------------------------------------------------------------------------------------

def plan(P, ctx, hist, p, dt) -> None:
    """Reporting tags and the facts later hooks need: the range_market reading (neutral_gate / B17.4) and the day's tags."""
    ctx.bh_on = active(p)
    if not ctx.bh_on and not (p.qshift_tag or p.qshift_size != 1.0):
        return
    if "range_market" in p.neutral_gate:
        from dataclasses import replace
        from . import daycontext as _DW
        tests = tuple(p.drr_tests) or ("range", "inside_bisi", "premium_run")
        q = replace(p, drr_tests=tests)
        P.info["drr_ng"] = _DW.range_regime(hist, q, getattr(ctx, "eth", None))
    S = im_state(ctx, p)
    P.tags |= {"bh_" + t for t in S.tags}
    row = getattr(ctx, "bias_row", None)
    if row is not None:
        rs = row_state(ctx, p, "AM", len(ctx.t) - 1 if len(ctx.t) else 0) if len(ctx.t) else State()
        P.tags |= {"bh_" + t for t in rs.tags}
        if p.htf_bias != "off":
            P.info["bias_val"] = bias_value(row, p)
        for k in ("mwd_case", "react_tf", "wk_dir"):
            if row.get(k) not in (None, ""):
                P.info[k] = row[k]
        if row.get("mwd_case"):
            P.tags.add("bh_mwd_" + str(row["mwd_case"]))


# --------------------------------------------------------------------------------------------------------------
# the hooks
# --------------------------------------------------------------------------------------------------------------

def lock_side(ctx, session: str) -> int:
    """The locked draw's side for a session (0 = none / neutral / lock off)."""
    lk = (getattr(ctx, "lock", None) or {}).get({"LUNCH": "AM", "PRE8": "MD"}.get(session, session))      # (Ma Deuce locks as "MD")
    return 0 if lk is None else int(lk["side"])


def gate(ctx, p, session: str, i: int, t: int):
    """A funnel key when the session may not arm at closed bar i for a bias_htf reason (a day-level block)."""
    if not getattr(ctx, "bh_on", False):
        return None
    S = row_state(ctx, p, session, i)
    im = im_state(ctx, p)
    for s_ in (S, im):
        if s_.block:
            return "x_bh_" + s_.block
        if s_.block_pre and t < PRE_END:
            return "x_bh_" + s_.block_pre
    if p.neutral_5050 == "armed" and fifty_blocked(ctx, session):
        return "x_bh_fifty_fifty"                         # B17.1: both sides armed in this window
    return None


def scalp_now(ctx, p, session: str, i: int | None):
    """The reason an order of `session` is a bias_htf scalp (one exit min(+5, T1), no adds), else ""."""
    if not getattr(ctx, "bh_on", False) or i is None:
        return ""
    S = row_state(ctx, p, session, i)
    r = S.scalp or im_state(ctx, p).scalp
    if r:
        return r
    if p.decoupled_mode == "scalp" or (p.neutral_gate_mode == "scalp" and "decoupled" in p.neutral_gate):
        from .entries import decoupled                    # B17.5 live: the partner moved the other way since the open
        if decoupled(ctx, i, p):
            return "decoupled" if p.decoupled_mode == "scalp" else "ng_decoupled"
    return ""


def side_ok(ctx, p, sign: int, session: str, i: int):
    """A funnel key when this side may not be traded at closed bar i for a bias_htf reason, else None."""
    if not getattr(ctx, "bh_on", False):
        return None
    if p.htf_bias != "off" and p.want_all_engines:
        w = want_at(ctx, p, session, i)               # B3: the Silver Bullet and Ma Deuce honour the bias side too
        if w != sign and (w or p.bias_neutral == "skip"):
            return "x_bh_want"
    S = row_state(ctx, p, session, i)
    for s_ in (S, im_state(ctx, p)):
        for why, signs in s_.sides.items():
            if sign in signs:
                return "x_bh_" + why
    row = row_for(ctx, session, i)
    # B13 weekly open: best longs below it early in the week, then buy each day while above it; until an opposing daily array
    if p.weekly_open != "off" and row is not None and not _i(row.get("wo_expired")):
        wd = _i(row.get("wk_dir"))
        if wd and sign == wd:
            ops = {"sun18": ("wo_sun",), "mon00": ("wo_mon",), "either": ("wo_sun", "wo_mon")}[p.weekly_open]
            vals = [float(row[k]) for k in ops if row.get(k) is not None and row[k] == row[k]]
            if p.tue_open_ref:                  # caption-gap L5-holiday-nwog (046 ~20:47-21:11): a holiday Monday - the week's reference is TUESDAY 09:30
                hol, tv = tue_open_ref(ctx, i, p.tue_open_time)
                if hol:
                    vals = [] if tv is None else [tv]      # (before Tuesday's 09:30 bar has closed the reference is unknown: no filter)
            if vals:
                early = ctx.day.weekday() < p.weekly_open_early_days
                px = float(ctx.c[i])
                below = [px < v for v in vals]
                above = [px > v for v in vals]
                ok = any(below if early else above) if wd > 0 else any(above if early else below)
                if not ok:
                    return "x_bh_weekly_open"
    # B5 news_topdown: on a release day the daily VI sets the side
    if p.news_topdown == "side" and row is not None:
        vs = _topdown_side(ctx, p, row)
        if vs and sign != vs:
            return "x_bh_news_topdown"
    # B17.5 decoupled (live): the partner moved the other way since the open
    if p.decoupled_mode == "skip" or (p.neutral_gate_mode == "skip" and "decoupled" in p.neutral_gate):
        from .entries import decoupled
        if decoupled(ctx, i, p):
            return "x_bh_decoupled"
    # B17.5 smt_both: SMT both ways at once with no bias = no trade
    if p.smt_both == "skip":
        b, s = smt_both_state(ctx, i)
        if b and s:
            w = want_at(ctx, p, session, i) if p.htf_bias != "off" else 0
            if not lock_side(ctx, session) and not w:
                return "x_bh_smt_both"
    # B5 bellwether_15m: the 15m chart must not deliver against the side
    if p.bellwether_15m == "filter":
        st = bellwether(ctx, i)
        if st and st != sign:
            return "x_bh_bellwether"
    # B3 judas_required: the first delivery goes against the bias
    if p.judas_required == "filter":
        b = lock_side(ctx, session) or (want_at(ctx, p, session, i) if p.htf_bias != "off" else 0)
        if b and sign == b and not judas_seen(ctx, p, session, i, b):
            return "x_bh_judas"
    # Ep06.6 midnight_confirm: the bias side must be confirmed by price on the right side of the midnight open
    if p.midnight_confirm == "filter":
        b = lock_side(ctx, session) or (want_at(ctx, p, session, i) if p.htf_bias != "off" else 0)
        if b and sign == b and not midnight_confirmed(ctx, b, i):
            return "x_bh_midnight_confirm"
    return None


def _topdown_side(ctx, p, row) -> int:
    """B5 news_topdown (Ep 02 ~0:56-2:29; 003): on a release day the top-down chain starts at the daily volume imbalance - the nearer of
    the table's vi_up / vi_dn is the draw (0 on a day without a release or without a VI; needs vi_arrays)."""
    from . import newscal as _NC
    if not _NC.releases(ctx.day, p):
        return 0
    vu, vd, px = row.get("vi_up"), row.get("vi_dn"), row.get("px")
    if vu is None or vd is None or px is None:
        return 0
    a, b = (abs(vu - px) if vu == vu else None), (abs(px - vd) if vd == vd else None)
    if a is None and b is None:
        return 0
    return 1 if (b is None or (a is not None and a < b)) else -1


def order_ok(ctx, sd, o: dict, session: str, i: int, p):
    """A funnel key when the armed order `o` breaks a bias_htf per-order rule (side-space prices), else None. Also adds the order
    tags (lv_tags)."""
    if not getattr(ctx, "bh_on", False):
        return None
    tags = []
    row = row_for(ctx, session, i)
    # B10 mwd_nest: with the day correcting inside a bullish week (case B) or month (case C) buy only inside those arrays
    if p.mwd_nest != "off" and row is not None and row.get("mwd_case") in ("B", "C") and _i(row.get("mwd")) == sd.sign:
        real = sd.x(o["entry"])
        tol = p.eq_tol_pts * p.es_pt
        inside = any(b - tol <= real <= t + tol for b, t in (row.get("mwd_zones") or []))
        tags.append(f"mwd_{row['mwd_case']}_{'nested' if inside else 'free'}")
        if p.mwd_nest == "filter" and not inside:
            return "x_bh_mwd_nest"
    # Ep03.12 mmbm_zone: the buy model buys a discount of [sweep low .. draw]
    if p.mmbm_zone != "off":
        draw = o.get("draw")
        if draw is None and o.get("levels"):
            draw = o["levels"][-1]
        if draw is not None and draw > o["ext"]:
            eq = (o["ext"] + draw) / 2
            disc = o["entry"] <= eq
            tags.append("mmbm_discount" if disc else "mmbm_premium")
            if p.mmbm_zone == "filter" and not disc:
                return "x_bh_mmbm_zone"
    if p.news_topdown == "tag" and row is not None:
        vs = _topdown_side(ctx, p, row)
        if vs:
            tags.append("topdown_agree" if vs == sd.sign else "topdown_against")
    if p.decoupled_mode == "tag" or (p.neutral_gate_mode == "tag" and "decoupled" in p.neutral_gate):
        from .entries import decoupled
        if decoupled(ctx, i, p):
            tags.append("decoupled_live")
    if p.smt_both == "tag":
        b_, s_ = smt_both_state(ctx, i)
        if b_ and s_:
            tags.append("smt_both")
    if p.judas_required == "tag":
        b = lock_side(ctx, session) or (want_at(ctx, p, session, i) if p.htf_bias != "off" else 0)
        if b and sd.sign == b:
            tags.append("judas_seen" if judas_seen(ctx, p, session, i, b) else "judas_pending")
    if p.bellwether_15m == "tag":
        st = bellwether(ctx, i)
        if st:
            tags.append("bell15_agree" if st == sd.sign else "bell15_against")
    if p.midnight_confirm == "tag":
        b = sd.sign
        tags.append("midnight_confirmed" if midnight_confirmed(ctx, b, i) else "midnight_unconfirmed")
    if p.neutral_5050 == "armed":
        # B17.1: both sides can be framed in the same window = 50/50 = no trade. The first side is registered only once its order
        # is really armed (register_armed, called by the engine); the other side's order then cancels the pending first one and
        # blocks the rest of the window (strategy cancels `pending`; fifty_blocked gates later bars)
        if -sd.sign in (getattr(ctx, "_bh_armed", None) or {}).get(session, ()):
            ctx.__dict__.setdefault("_bh_fifty", set()).add(session)
            return "x_bh_fifty_fifty"
    if tags:
        o["lv_tags"] = "|".join(x for x in (o.get("lv_tags", ""), *tags) if x)
    return None


def register_armed(ctx, p, session: str, sign: int) -> None:
    """B17.1 neutral_5050="armed": remember that an order of `sign` was armed in this window (called when the engine arms it)."""
    if p.neutral_5050 == "armed":
        ctx.__dict__.setdefault("_bh_armed", {}).setdefault(session, set()).add(sign)


def fifty_blocked(ctx, session: str) -> bool:
    """B17.1 neutral_5050="armed": both sides were framed in this window - stand aside for the rest of it."""
    return session in (getattr(ctx, "_bh_fifty", None) or ())


def size_mult(ctx, sd, i: int, p, lvt) -> float:
    """B22 qshift_size: the risk multiplier against the 252-session trend while a quarterly shift is due [our interpretation]."""
    if p.qshift_size == 1.0:
        return 1.0
    row = row_for(ctx, "", i)                        # (review fix) the cut row before 09:30 too: the quarterly columns are daily
    if row is None or not _i(row.get("qs_due")):
        return 1.0
    tr = _i(row.get("qs_trend"))
    if tr and sd.sign != tr:
        lvt.append("size_qshift")
        return p.qshift_size
    return 1.0


# --------------------------------------------------------------------------------------------------------------
# bar-level reads
# --------------------------------------------------------------------------------------------------------------

def _start_idx(ctx, session: str, i: int) -> int:
    """The first bar of the session's window (its lock time)."""
    lt = (getattr(ctx, "lock_t", None) or {}).get("AM" if session == "LUNCH" else session)
    if lt is None:
        lt = {"PM": 810, "PRE7": 420, "PRE8": 480, "PRE9": 540, "NEWS": 540, "LON": getattr(ctx, "lon_start", 120)}.get(session, 570)
    k = ctx.start + int(np.searchsorted(ctx.t[ctx.start:], lt))
    return min(k, i)


def judas_seen(ctx, p, session: str, i: int, b: int) -> bool:
    """B3 / M0 step 3 (068 ~16:30; 082 ~8:02): since the session opened (its first bar's open) price has been delivered AGAINST
    the bias side `b` by at least judas_min_pts - a long waits for a run below the open, a short for a run above it. Closed bars
    only (through i)."""
    k = _start_idx(ctx, session, i)
    if k > i:
        return False
    ref = float(ctx.o[k])
    need = p.judas_min_pts * p.es_pt
    return bool((ref - float(ctx.l[k:i + 1].min()) >= need) if b > 0 else (float(ctx.h[k:i + 1].max()) - ref >= need))


def midnight_confirmed(ctx, b: int, i: int) -> bool:
    """Ep06.6 (Ep 06 ~0:51): "the midnight opening price is the reference: if bearish, look for price below it". The bias side b is
    confirmed once the last closed bar sits beyond the midnight open in its direction (bullish: above, bearish: below)."""
    from .strategy import _open_known
    m = _open_known(ctx, "midnight", i)
    if m is None:
        return True                                  # no midnight open yet: nothing to confirm against
    return bool(ctx.c[i] > m) if b > 0 else bool(ctx.c[i] < m)


def bellwether(ctx, i: int) -> int:
    """B5 (013 ~2:36; 065B ~05:01): the 15m bellwether read [our interpretation]: the last COMPLETED 15m bar's close against the
    midpoint of the range of the last four completed 15m bars: above = +1 (delivering up), below = -1, 0 without four bars."""
    c = ctx.__dict__.setdefault("_bh_b15", {})
    if "g" not in c:
        t = ctx.t
        g = (t // 15).astype(int)
        c["g"] = g
        c["last"] = np.r_[g[1:] != g[:-1], True]            # the last base bar of each 15-minute bucket (the bucket is complete after it)
    g, last = c["g"], c["last"]
    # complete buckets up to i: bucket b is complete if its last bar index <= i and the bar ends on a 15-minute boundary
    ends = np.flatnonzero(last[:i + 1] & (((ctx.t[:i + 1] + ctx.tf) % 15) == 0))
    ends = ends[ends >= ctx.start]
    if len(ends) < 4:
        return 0
    bars = []
    for e in ends[-4:]:
        a = e
        while a - 1 >= ctx.start and g[a - 1] == g[e]:
            a -= 1
        bars.append((float(ctx.h[a:e + 1].max()), float(ctx.l[a:e + 1].min()), float(ctx.c[e])))
    mid = (max(b[0] for b in bars) + min(b[1] for b in bars)) / 2
    return 1 if bars[-1][2] > mid else (-1 if bars[-1][2] < mid else 0)


def smt_both_state(ctx, i: int) -> tuple:
    """B17.5 (090 ~41:00-43:00): the SMT divergences at the previous day's high AND low in the overnight range, as in
    manage.smt_bias but both reported: (bull, bear). Bars closed before 09:30 only; cached once the overnight is complete."""
    cached = getattr(ctx, "_bh_smt2", None)
    if cached is not None:
        return cached
    from .strategy import _idx_at
    ps = getattr(ctx, "pside", None)
    pc = ps[0] if ps else None
    hist, phist = getattr(ctx, "hist", None), getattr(pc, "hist", None) if pc is not None else None
    if pc is None or not hist or not phist:
        return (False, False)
    k = _idx_at(ctx, 570)
    end = min(k, i + 1)
    if end <= ctx.start + 1:
        return (False, False)
    last = ctx.idx[end - 1]
    pend = int(pc.idx.searchsorted(last, side="right"))
    if pend <= pc.start + 1:
        return (False, False)
    lo_o, hi_o = ctx.l[ctx.start:end], ctx.h[ctx.start:end]
    lo_p, hi_p = pc.l[pc.start:pend], pc.h[pc.start:pend]
    pdl, pdh = float(hist[-1].low.min()), float(hist[-1].high.max())
    qdl, qdh = float(phist[-1].low.min()), float(phist[-1].high.max())
    out = (bool(lo_o.min() < pdl and lo_p.min() >= qdl), bool(hi_o.max() > pdh and hi_p.max() <= qdh))
    if end >= k:
        ctx._bh_smt2 = out
    return out


# --------------------------------------------------------------------------------------------------------------
# the draw lock (strategy.mark_levels / _lock_step)
# --------------------------------------------------------------------------------------------------------------

def ordered_side(up: list, dn: list, row, p) -> tuple:
    """B2 / B3 draw_lock_pick="ordered" | "largest": choose the locked side from the marked candidates (items are
    (distance, level, kind, name, dir), nearest first; kind "array" = an inefficiency, "pool" = liquidity). ORDERED: inefficiency
    first - the nearer of the nearest array each side; none: liquidity by premium / discount (the row's `pd`: discount -> the
    buy-side above, premium -> the sell-side below; pd 0 or no pool that side -> the nearest); a tie is neutral. LARGEST (068 ~16:30
    "the day's largest move"): the side whose ordered candidate is the farther [our interpretation]. Returns (side, up, dn) with the
    chosen candidate first in its list."""
    def first(lst):
        arr = [x for x in lst if x[2] == "array"]
        return (arr[0], "ineff") if arr else ((lst[0], "liq") if lst else (None, ""))

    (ua, uk), (da, dk) = first(up), first(dn)
    if p.draw_lock_pick == "largest":
        if ua and da:
            side = 1 if ua[0] > da[0] else (-1 if da[0] > ua[0] else 0)
        else:
            side = 1 if ua else (-1 if da else 0)
    else:
        arr_u = [x for x in up if x[2] == "array"]
        arr_d = [x for x in dn if x[2] == "array"]
        if arr_u or arr_d:
            if arr_u and arr_d:
                side = 1 if arr_u[0][0] < arr_d[0][0] else (-1 if arr_d[0][0] < arr_u[0][0] else 0)
            else:
                side = 1 if arr_u else -1
        else:
            pdv = _i(row.get("pd")) if row else 0
            if pdv > 0 and up:
                side = 1
            elif pdv < 0 and dn:
                side = -1
            elif up and dn:
                side = 1 if up[0][0] < dn[0][0] else (-1 if dn[0][0] < up[0][0] else 0)
            else:
                side = 1 if up else (-1 if dn else 0)
    if side > 0:
        up = [ua] + [x for x in up if x is not ua]
    elif side < 0:
        dn = [da] + [x for x in dn if x is not da]
    return side, up, dn


def ext_target(pick: list, mk_side: list, extra: list = ()):
    """B2 (104 ~16:18) draw_ext_target: when the locked draw is a liquidity pool, the nearest inefficiency (array) beyond it on the
    same side sets how far the run goes - it becomes the target and the pool a rung (lock["ext_from"], which _targets adds to
    the ladder). `pick` = the chosen candidate list (first = the pool), `mk_side` = ALL marked candidates that side, nearest
    first, `extra` = further arrays that side that are not marked draws (the untraded HTF arrays beyond the pool, built by
    mark_levels). Items are (distance, level, kind, name, dir). Returns the extended candidate or None."""
    c0 = pick[0]
    if c0[2] != "pool":
        return None
    beyond = [x for x in list(mk_side) + list(extra) if x[2] == "array" and x[0] > c0[0] + 1e-9]
    return min(beyond, key=lambda x: x[0]) if beyond else None


def tf_lower_pref(ctx, row, px: float, now, S: int):
    """L14c (cc06_003 ~0:50; cc07_001 ~9:29) matrix_tf_lower: once price has reacted from one side's arrays on timeframe X (the
    table's react / react_tf), the draw is the opposing array one timeframe lower: W -> D, D -> 4h. Returns
    (level, "array", name, 0, S) or None."""
    if not row or getattr(ctx, "conf", None) is None:
        return None
    rs, tf = _i(row.get("react")), row.get("react_tf")
    if not rs or tf not in ("W", "D"):
        return None
    lower = {"W": "D", "D": "4h"}[tf]
    r = ctx.conf.opposing(now, px, 1 if rs > 0 else -1, (lower,), (0, 1, 2, 3))
    if not r:
        return None
    return (float(r[0][0]), "array", f"tf_lower_{lower}", 0, S)


def cond_relock(ctx, p, lk: dict, i: int, spent: list):
    """L14e (080 ~16:58) cond_draw: "if price fails to reach the upper pool, switch to the lower; once taken the low draw is spent".
    Failure [our interpretation] = the draw has NOT been reached and the OTHER side's nearest marked level (at least
    draw_lock_min_pts from the lock price) has been taken first, by a bar of this session after the lock: the market delivered
    the opposite side, the first move went against the bias (a retrace alone is NOT a failure - that is the Judas swing, B3). The
    taken level is spent and the lock switches ONCE to the next marked level beyond it on that side (none: no relock). Returns the
    new lock dict or None."""
    if lk.get("cond_used") or not lk["side"] or lk["delivered"]:
        return None
    mn = p.draw_lock_min_pts * p.es_pt
    other = -lk["side"]
    lv = sorted((abs(v - lk["px"]), v, kd, nm, dr) for v, kd, nm, dr in lk["marked"]
                if ((v < lk["px"] - mn) if other < 0 else (v > lk["px"] + mn)) and abs(v - lk["target"]) > 1e-9)
    if not lv:
        return None
    first = lv[0]
    taken = ctx.l[i] <= first[1] if other < 0 else ctx.h[i] >= first[1]
    if not taken:
        return None
    nxt = [x for x in lv[1:] if (x[1] < first[1] if other < 0 else x[1] > first[1])]
    if not nxt:
        return None
    d, v, kd, nm, dr = nxt[0]
    nl = dict(lk)
    nl.update(side=other, target=v, kind=kd, name=nm, cond_used=True, cond_failed=lk["target"], delivered=False,
              delivered_t=None, delivered_i=None)
    spent += [lk["target"], first[1]]
    return nl


def untraded_arrays(ctx, i: int, now, px: float, sgn: int, tfs, src, reuse: bool = False) -> list:
    """L14 / L14d conf-target hygiene for the lock: `conf.opposing` rows [(near, ce, far, tf, src)] minus the arrays price has already
    traded into since they formed (through the last closed bar i) - an exhausted array is not a draw (028 ~54:55; cc07_004 ~4:00).
    Gaps are never retired by a fill (039): src 2 rows are kept. Caption-gap A22-array-reuse (`reuse`, Params.array_reuse != "first_touch"; 061 ~2:11:51):
    a traded-into array stays a draw until a bar closed through its CE (tp1.untouched)."""
    from . import targets as _TP
    from . import tp1 as _T1
    out = []
    for r in ctx.conf.opposing_ext(now, px, sgn, tfs, src):
        if r["src"] != 2:
            ext = _TP.extreme_since(ctx, i, r["known"], sgn > 0)
            near = r["bottom"] if sgn > 0 else r["top"]
            if ext is not None and ((ext >= near) if sgn > 0 else (ext <= near)):
                if not (reuse and _T1.untouched(ctx, sgn, i, r)):
                    continue
                _T1.hit("array_reuse_draw")
        top, bot = r["top"], r["bottom"]
        n, f = (bot, top) if sgn > 0 else (top, bot)
        out.append((n, (top + bot) / 2, f, r["tf"], r["src"]))
    return out


# --------------------------------------------------------------------------------------------------------------
# D22 / Ep08.3 / Ep06.6 the opening prices
# --------------------------------------------------------------------------------------------------------------

def apply_open_src(ctx, p, intermarket) -> None:
    """D22 bias_open_src: "spy" re-reads the midnight open as the 04:00 stand-in even from a frame with bars from midnight;
    "es_map" takes the futures midnight open mapped to this instrument (backtest.prepare(ref_df=...) -> intermarket
    ["ext_midnight"]; it prints at 00:00, long before any bar the engine trades)."""
    if p.bias_open_src == "spy":
        from . import levels as L
        ctx.opens = L.opens(ctx.idx, ctx.o, "spy")
    elif p.bias_open_src == "es_map":
        m = (intermarket or {}).get("ext_midnight")
        if m is not None and m == m:
            ctx.opens["midnight"] = float(m)


def reference_opens(ctx, p, session: str, i: int) -> list:
    """T2 / D22 / Ep08.3: the opening prices the AM (PM: the 13:30) entry is judged against - bias_open, or with "all" every one of
    midnight, 08:30 and 09:30 that has printed (an open counts only once its own bar has closed: strategy._open_known)."""
    from .strategy import _open_known
    if session == "PM":
        names = ["1330"]
    elif p.bias_open == "all":
        names = ["midnight", "0830", "0930"]
    else:
        names = [p.bias_open]
    out = []
    for nm in names:
        v = _open_known(ctx, nm, i)
        if v is None and nm == p.bias_open and session != "PM":     # a pre-09:30 window reads the midnight open until it prints
            v = _open_known(ctx, "midnight", i)
        if v is not None:
            out.append(v)
    return out


def below_ok(ctx, p, sd, session: str, i: int) -> bool:
    """Ep06.6 midnight_below_ok: the bias side (locked draw, else htf_bias) is confirmed by price beyond the midnight open."""
    b = lock_side(ctx, session) or (want_at(ctx, p, session, i) if p.htf_bias != "off" else 0)
    return bool(b == sd.sign and midnight_confirmed(ctx, b, i))
