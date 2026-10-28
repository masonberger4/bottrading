"""Daily bias from higher-timeframe PD arrays (mentorship_rules.md B1-B3, B7, B14, L5-L6).

Mase's spec (2026-10-17): the daily bias comes from higher-timeframe draws on liquidity,
fair value gaps, order blocks and the daily/weekly opening gaps. A daily gap is the 17:00
close to the 18:00 open; a weekly gap is Friday's 17:00 close to Sunday's 18:00 open.

Data note: the HistData index CFDs stop at 16:14 and reopen at 18:00 (Sunday 18:00 after
the weekend), so the gaps here are 16:14 close -> 18:00 open; ES's 16:15-17:00 trade is
missing. A few weeks a year (US/EU daylight-saving mismatch) the feed runs an hour early;
labelling each bar with the date of (time + 7h) puts 17:00 and 18:00 reopens alike on the
next trading day.

Trading day D runs from the previous evening's reopen to D's close. The bias for D is
decided at 09:30 from completed daily/weekly bars before D plus D's overnight bars
(18:00-09:29); nothing at or after 09:30 of D is read.

Three readings, each -1 / 0 / +1:
  react  the last `react_days` completed days or tonight's overnight traded into a valid
         bullish HTF array (daily/weekly FVG, OB, NDOG/NWOG) and price now holds above its
         CE / mean threshold -> +1; bearish mirror; weekly arrays count double.
  draw   direction of the nearest HTF draw: the near edge of an open (not yet rebalanced)
         daily/weekly FVG or opening gap, or an untaken daily swing high/low, previous day
         or previous week high/low.
  pd     premium/discount of the daily dealing range (the nearest untaken daily swing high
         above and low below): below its 50% -> +1 (buy-side is the draw), above -> -1.
  combo  react, else pd.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import levels as L


@dataclass
class Arr:
    kind: str        # "bull" / "bear"
    typ: str         # "fvg", "ob", "ndog", "nwog"
    tf: str          # "D" or "W"
    top: float
    bottom: float
    ce: float        # consequent encroachment / mean threshold
    known: int       # index (in daily bars) of the first day it can be used
    ipda_w: int = 0  # caption-gap B21 (cc05_001 ~22:58): the IPDA window (20 / 40 / 60 sessions) of the row being built, by the age of `known`
                     # (set per day in table(); 0 = older than 60 sessions). Arr objects are shared across days, so read it only inside the loop.


def sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Daily OHLC per trading day (futures-style: evening reopen to the afternoon close)."""
    lab = (df.index + pd.Timedelta(hours=7)).date
    g = df.groupby(lab)
    d = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                      "close": g.close.last(), "n": g.close.size()})
    d.index = pd.to_datetime(d.index)
    return d[d.n >= 60].drop(columns="n")            # drop stub sessions (holiday fragments)


def months(d: pd.DataFrame) -> pd.DataFrame:
    """Monthly candles of the sessions `d` (the analogue of `weeks`): open / high / low / close and `last` = the month's last session label. A month the
    frame only partly covers at its start keeps the covered sessions (like the first week)."""
    m = d.groupby(d.index.to_period("M"))
    return pd.DataFrame({"open": m.open.first(), "high": m.high.max(), "low": m.low.min(),
                         "close": m.close.last(), "last": m.apply(lambda x: x.index[-1])})


def weeks(d: pd.DataFrame) -> pd.DataFrame:
    w = d.groupby(d.index.to_period("W-FRI"))
    out = pd.DataFrame({"open": w.open.first(), "high": w.high.max(), "low": w.low.min(),
                        "close": w.close.last(), "last": w.apply(lambda x: x.index[-1])})
    return out


def _arrays(o, h, l, c, tf: str, known_of, vi: bool = False, c2_dir: bool = False,
            vi_min_gap: float = 0.0, vi_wick_overlap: bool = True, vi_multi: bool = False,
            drill=None, spr: bool = False, void_rt: bool = False, rb: bool = False, rb_level: str = "close", upclose: bool = False) -> list[Arr]:
    """Daily / weekly arrays. levels_detectors: `c2_dir` (A5 fvg_c2_dir) keeps only FVGs whose
    middle candle closes their way; `vi_min_gap` (A9) drops narrower VIs; caption-gap A9 `vi_wick_overlap` /
    `vi_multi` (see levels.volume_imbalances).
    Caption-gap pass (levels_detectors #2/3):
      `drill`  A12-tf-relative-ob (079 ~15:06: "don't get thrown off that this is the down closed candle"): a callable j -> (o, h, l, c)
               arrays of the lower-timeframe bars INSIDE bar j (daily -> 1h). When the swing-extreme candle of an FVG's formation
               (the highest high of the three bars before the displacement for a bearish gap, the lowest low for a bullish one) has the
               WRONG colour for an order block, the block is the last opposite-colour LTF bar before the displacement - at or before the
               LTF bar holding the extreme - labelled at the HTF location: zone from its open to its extreme, mean threshold = its body
               midpoint [our interpretation of "(open, MT, high)"].
      `spr`    new-single-candle-daily-inefficiency (091 ~25:37): single-pass ranges as typ "spr" arrays (levels.single_pass_ranges);
               `Arr.ce` = the candle's CE; the 25 / 75% levels come from the candle (`Arr.q`)
      `void_rt` A12-void-up-down-ob (cc02_007 ~13:33): a one-sided rally followed at once by a one-sided drop through the same range
               = one OB (typ "ob", ce = 50%).
      `rb`     A17-rejection-block-short-protocol (035 ~23:08; levels_detectors #3/3 review): the CLOSE of the candle that made a swing high (low)
               (levels.rejection_blocks, `rb_level`, 3-candle pivots) as typ "rb" arrays - top = bottom = ce = that close, `src_i` = the swing
               candle. The bias table never counts them (they are levels, not reactions); `table(rb_closes=True)` lists the untaken ones as the
               columns rb_up / rb_dn and the engine (ld4.rb_build) reads the same arrays."""
    out = []
    if vi:                       # shared VI wiring (Ep02.8 / Ep03.3 / B1): daily/weekly volume
        for z in L.volume_imbalances(o, h, l, c, vi_min_gap, vi_wick_overlap, vi_multi):   # imbalances as arrays and draws
            a = Arr(z.kind, "vi", tf, z.top, z.bottom, z.mid, known_of(z.i))
            a.src_i = z.i                                     # its own-TF bar (A9 body death)
            out.append(a)
    for z in L.fvgs(h, l, o, c, c2_dir):
        if upclose and tf == "D":                           # caption-gap A5-htf-fvg-last-upclose-anchor (bias_htf#5/7; cc09_008 ~12:27): the last up-close candle's low is the upper reference of a bearish gap whose first candle closed down
            from . import bh5 as _bh5
            t5_, b5_ = _bh5.upclose_edges(o, h, l, c, z)
            if (t5_, b5_) != (z.top, z.bottom):
                _bh5.sw("dfvg_upclose_anchor")
                out.append(Arr(z.kind, "fvg", tf, t5_, b5_, (t5_ + b5_) / 2, known_of(z.i)))
            else:
                out.append(Arr(z.kind, "fvg", tf, z.top, z.bottom, z.mid, known_of(z.i)))
        else:
            out.append(Arr(z.kind, "fvg", tf, z.top, z.bottom, z.mid, known_of(z.i)))
        # order block: last opposite-close candle before the displacement candle
        kind = "bull" if z.kind == "bull" else "bear"
        ob = None
        if drill is not None:
            ob = _drilled_ob(o, h, l, c, z, kind, drill)
        if ob is None:
            ob = L.order_block_blend(o, h, l, c, z.i - 4, z.i - 2, kind)
        if ob is not None:
            disp = c[z.i - 1]
            if (kind == "bull" and disp > ob.top) or (kind == "bear" and disp < ob.bottom):
                out.append(Arr(kind, "ob", tf, ob.top, ob.bottom, ob.mt, known_of(z.i)))
    if void_rt:
        for z in L.void_round_trip_obs(o, h, l, c):
            out.append(Arr(z.kind, "ob", tf, z.top, z.bottom, z.mt, known_of(z.i)))
    if rb:
        for z in L.rejection_blocks(o, h, l, c, 1, 0.0, rb_level):
            lvl = float(z.levels[0])
            a = Arr(z.kind, "rb", tf, lvl, lvl, lvl, known_of(z.i))
            a.src_i = z.src
            out.append(a)
    if spr:
        for z in L.single_pass_ranges(o, h, l, c):
            a = Arr(z.kind, "spr", tf, z.top, z.bottom, z.mid, known_of(z.i))
            a.levels = z.levels
            a.src_i = z.src
            out.append(a)
    return out


def _drilled_ob(o, h, l, c, z, kind: str, drill):
    """levels.Zone of the lower-timeframe order block inside a wrong-coloured swing-extreme candle (see `_arrays`), or None. The extreme
    candle is searched among the bars z.i-4 .. z.i-2 (the three before the displacement candle z.i-1), like the standard OB window."""
    a = max(0, z.i - 4)
    rng = range(a, z.i - 1)
    if not len(rng):
        return None
    e = max(rng, key=lambda k: h[k]) if kind == "bear" else min(rng, key=lambda k: l[k])
    wrong = (c[e] <= o[e]) if kind == "bear" else (c[e] >= o[e])        # an OB needs an up-close (bearish) / down-close (bullish) candle
    if not wrong:
        return None
    sub = drill(e)
    if sub is None:
        return None
    so, sh, sl, sc = sub
    if not len(sc):
        return None
    m = int(np.argmax(sh)) if kind == "bear" else int(np.argmin(sl))
    for q in range(m, -1, -1):
        if (kind == "bear" and sc[q] > so[q]) or (kind == "bull" and sc[q] < so[q]):
            top, bot = (float(sh[q]), float(so[q])) if kind == "bear" else (float(so[q]), float(sl[q]))
            return L.Zone(kind, top, bot, z.i, e, float((so[q] + sc[q]) / 2))
    return None


def bar_minutes(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 1
    d = pd.Series(df.index[1:] - df.index[:-1])
    return max(1, int(d[d > pd.Timedelta(0)].min().total_seconds() // 60))


def _arr_alive(a: Arr, k: int, o, h, l, c, wo, wc, wl, vi_body_death: bool, vi_rule: str = "full_span",
               ol: float = 0.0, oh: float = 0.0, open_only: bool = False, bal: str = "legacy", lcl=None, to_mt: bool = False, mon=None) -> bool:
    """Is array `a` still valid on day k (the table's inline test): a VI under `vi_body_death` dies once a later own-TF body spans
    it (rule "full_span") or overlaps it ("overlap"); other arrays die on a close through the far side / the OB mean threshold;
    opening gaps are never retired by a fill (039). open_only (caption-gap B21 window pick): also not fully rebalanced - the draw
    is still open (the unrebalanced part of an FVG / VI).
    Caption-gap A11-htf-gap-own-tf (`bal` = Params.balance_tf; 061 ~40:20 "on the weekly time frame it's inefficient still"; 078
    ~1:13:50): which closes retire an FVG / OB. "legacy" = as first built (a weekly array is judged on the DAILY closes after its
    week); "own" = only closes of its own timeframe (a weekly array: completed weekly closes, so daily back-and-forth inside it is
    ignored); "next_lower" = the next lower timeframe (a daily array: the 4h closes `lcl[j]` of each session j; a weekly array: the
    daily closes)."""
    s = a.known
    cl = c[s:k]
    if a.tf == "W" and bal == "own":
        cl = wc[[j for j in range(len(wl)) if a.known < wl[j] <= k]]
    elif a.tf == "D" and bal == "next_lower" and lcl is not None:
        parts = [lcl[j] for j in range(s, k) if j < len(lcl) and len(lcl[j])]
        cl = np.concatenate(parts) if parts else np.array([])
    if to_mt and a.typ == "ob" and a.tf in ("W", "M"):       # caption-gap A12-htf-ob-trade-through-to-mt (bias_htf#4/7; cc06_005 ~30:28): a weekly / monthly block dies only on a close of ITS OWN timeframe beyond the MT
        if a.tf == "W":
            cl = wc[[j for j in range(len(wl)) if a.known < wl[j] <= k]]
        elif mon is not None:
            cl = mon[1][[j for j in range(len(mon[0])) if a.known < mon[0][j] <= k]]
    gap = a.typ in ("ndog", "nwog")
    if a.typ == "vi" and vi_body_death:
        if a.tf == "D":
            ob_, cb_ = o[s:k], c[s:k]
        else:                                    # weekly bodies completed before day k
            done_w = [j for j in range(len(wl)) if a.known < wl[j] <= k]   # later weeks only
            ob_, cb_ = wo[done_w], wc[done_w]
        if len(cb_):
            lo_b, hi_b = np.minimum(ob_, cb_), np.maximum(ob_, cb_)
            dead = ((lo_b < a.top) & (hi_b > a.bottom)) if vi_rule == "overlap" else ((lo_b <= a.bottom) & (hi_b >= a.top))
            if dead.any():
                return False
    elif a.kind == "bull" and not gap:
        lvl = a.ce if a.typ == "ob" else a.bottom
        if len(cl) and cl.min() < lvl:
            return False                                   # closed through: invalid
    elif not gap:
        lvl = a.ce if a.typ == "ob" else a.top
        if len(cl) and cl.max() > lvl:
            return False
    if open_only and a.typ in ("fvg", "vi"):
        if a.kind == "bull" and np.append(l[s:k], ol).min() <= a.bottom:
            return False
        if a.kind == "bear" and np.append(h[s:k], oh).max() >= a.top:
            return False
    return True


def spr_target(a: Arr, seen: float, px: float):
    """new-single-candle-daily-inefficiency (091 ~25:37): the draw of a live single-pass range `a` for price `px` - "needs sell-side delivery": the CE first,
    then the lower quadrant (the 25% level), then the candle low (the extreme case); mirrored for a down candle. `seen` = the lowest low (highest high)
    since it formed; a level already traded is skipped, a range traded all the way through is no draw. None when nothing is left on the price's side."""
    lv = tuple(getattr(a, "levels", ()) or ())
    ladder = (a.ce,) + ((lv[1], lv[0]) if len(lv) >= 2 else ())
    if a.kind == "bull":
        if seen <= a.bottom:
            return None
        return next((t for t in ladder if seen > t and t < px), None)
    if seen >= a.top:
        return None
    return next((t for t in ladder if seen < t and t > px), None)


def _ltf_provider(df: pd.DataFrame, d: pd.DataFrame, m: int):
    """A12-tf-relative-ob: a callable j -> (o, h, l, c) arrays of the m-minute bars inside session j of the daily frame `d`
    (sessions(df): futures-style, labelled by (time + 7h).date)."""
    lab = (df.index + pd.Timedelta(hours=7)).date
    g = df.groupby([lab, df.index.floor(f"{m}min")])
    b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    by = {}
    for (day, _), r in b.iterrows():
        by.setdefault(pd.Timestamp(day), []).append((r.open, r.high, r.low, r.close))
    dates = list(d.index)
    cache = {}

    def get(j: int):
        if j in cache:
            return cache[j]
        rows = by.get(pd.Timestamp(dates[j]))
        cache[j] = None if not rows else tuple(np.array(x, float) for x in zip(*rows))
        return cache[j]
    return get


def _ltf_closes(df: pd.DataFrame, d: pd.DataFrame, m: int) -> list:
    """balance_tf "next_lower": for each session of `d`, the closes of its m-minute bars."""
    prov = _ltf_provider(df, d, m)
    out = []
    for j in range(len(d)):
        r = prov(j)
        out.append(np.array([]) if r is None else r[3])
    return out


def table(df: pd.DataFrame, es_pt: float = 1.0, react_days: int = 2, lookback: int = 60,
          min_gap_pts: float = 1.0, cut_min: int = 570, vi: bool = False,
          flip_triggers: tuple = ("ob_mt", "wk_dc"), c2_dir: bool = False, vi_min_gap: float = 0.0,
          vi_body_death: bool = False, bx: str = "", vi_wick_overlap: bool = True, vi_multi: bool = False,
          vi_dead_rule: str = "full_span", vi_two_sided: bool = False, ipda_first20: bool = False,
          nwog_cfd_src: str = "auto", single_pass_draw: bool = False, void_rt_ob: bool = False, htf_ob_ltf_drill: bool = False,
          balance_tf: str = "own", tf_lookback: dict | None = None, monthly_arrays: bool = False, rb_closes: bool = False,
          ipda_window: str | None = None, ob_reach: str = "wick", wk_joint: dict | None = None) -> pd.DataFrame:
    """One row per trading day: react / draw / pd / combo bias and the draw levels.
    Caption-gap A12-ob-reached-body (cc03_002 ~8:33; `ob_reach`): "body" = an order block counts as reached only when a BODY of the last `react_days` COMPLETED sessions enters it
    (min(open, close) <= its top; max(open, close) >= its bottom for a bearish block) - a wick through the whole block does not; "wick" (built) uses the lows / highs and tonight's range.
    `cut_min`: the row describes the market as known at that minute of the day - the overnight
    high/low/last use only bars that have CLOSED by cut_min (bar start + bar length <= cut_min).
    The default 570 (09:30) gives the original table; the draw lock (owner #9) builds one table
    per session lock time (13:30 for the PM, ...). `vi` adds daily/weekly volume imbalances as
    arrays/draws (shared VI wiring). `flip` is the stateful bias column (B8; shared): see _flip.
    levels_detectors: `c2_dir` / `vi_min_gap` (see _arrays); `vi_body_death` (A9 / Ep03.3): a VI
    dies once a later body of its own timeframe spans it (not on a close beyond its far edge).
    With `vi`, the columns vi_up / vi_dn hold the nearest live VI draw each way (vi_news_draw).
    bias_htf: `bx` (bias_htf.bx_string(Params)) names the extra columns to build (ordered draw, IOF, P/D of the 20-session range,
    MWD, weekly open, NWOG regime, ...); "" gives the table above unchanged.
    Caption-gap pass (levels_detectors #1/3): `vi_wick_overlap` / `vi_multi` (A9 definition), `vi_dead_rule` ("full_span" /
    "overlap": the body death rule of a VI), `vi_two_sided` (A9: an open VI stays a draw from either side until a body kills
    it - wicks never retire it, 077), `ipda_first20` (B21 / cc05_007: the daily FVG / OB / VI arrays of the last 20 sessions
    are the only ones used until all of them are traded through, then 40, then 60 - Arr.ipda_w by the age of `known`).
    Caption-gap pass (levels_detectors #2/3): `nwog_cfd_src` (L5-cfd-nwog-mapping, see opening_gaps), `single_pass_draw` (a daily
    single-pass range is a draw: its CE below / above price until a later low / high trades through it), `void_rt_ob` (a one-sided
    rally + drop = one OB), `htf_ob_ltf_drill` (a wrong-coloured swing-extreme candle takes its OB from the 1h bars inside it), `balance_tf`
    ("legacy" / "own" / "next_lower": which closes retire an array, see _arr_alive).
    Caption-gap pass (levels_detectors #3/3 review): `monthly_arrays` (L3-htf-pd-arrays-intraday, cc05_015 ~19:55: monthly PD arrays beside the daily and
    weekly ones; usable from the session after the month's last session, react weight 3 [our interpretation: higher timeframe counts more]),
    `rb_closes` (A17: the untaken rejection-block closes of the daily swing candles as the columns rb_up / rb_dn - the nearest above / below the
    price; they never enter the bias), `ipda_window` (B21-reference-points-in-windows, Params.ipda_arrays: the IPDA anchor - "rolling" / "month" /
    "current_month" / "swing" - whose 60-session window limits the daily arrays and swing draws of each row to those formed inside the 60 sessions
    ending at the anchor, `levels.ipda_end_index`; None = the lookback alone).
    Caption-gap pass (bias_htf#1/7): `wk_joint` (B8-weekly-ith-both-indices-close; bh1.wk_joint_map) = {date of a week's last session: the joint ES + NQ weekly-ITH state}: the wk_dc -1 flip applies only while it is True."""
    from . import bias_htf as BH
    X = BH.parse(bx)
    from . import bh4 as BH4                         # caption-gap pass bias_htf#4/7 (bh4.py): table-time rules (age tiers, reach tolerance, weekly / monthly life, origin OB, mitigation, OB to MT, event wicks)
    tc = BH4.table_cfg(X)
    from . import bh5 as BH5                         # caption-gap pass bias_htf#5/7 (bh5.py): the up-close FVG anchor at table time, the columns after bh4.finish4
    tc5 = BH5.table_cfg(X)
    d = sessions(df)
    D = len(d)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    h_pv, l_pv = BH4.event_wick_adjust(o, h, l, c, float(tc["ew"])) if tc["ew"] else (h, l)       # A4-event-wick-ignore: the swing pivots (and 'untaken' tests) use the body extreme of an event candle
    if tc["ew"]:
        BH4.sw("event_wick_ignore")
    if tc["hm"]:
        BH4.sw("htf_history_months")
    drill = _ltf_provider(df, d, 60) if htf_ob_ltf_drill else None
    lcl = _ltf_closes(df, d, 240) if balance_tf == "next_lower" else None
    arrs = _arrays(o, h, l, c, "D", lambda i: i + 1, vi, c2_dir, vi_min_gap, vi_wick_overlap, vi_multi,
                   drill=drill, spr=single_pass_draw, void_rt=void_rt_ob, rb=rb_closes, upclose=tc5["upc"])
    # weekly arrays become usable the day after the week's last session
    w = weeks(d)
    pos = {t: k for k, t in enumerate(d.index)}
    wl = [pos[t] + 1 for t in w["last"]]
    wo, wc = w.open.values.astype(float), w.close.values.astype(float)
    wh_, wlow_ = w.high.values.astype(float), w.low.values.astype(float)
    arrs += _arrays(*(w[k].values.astype(float) for k in ("open", "high", "low", "close")), "W",
                    lambda i: wl[i], vi, c2_dir, vi_min_gap, vi_wick_overlap, vi_multi, void_rt=void_rt_ob)
    if monthly_arrays:
        mth = months(d)
        ml_ = [pos[t] + 1 for t in mth["last"]]
        arrs += _arrays(*(mth[k].values.astype(float) for k in ("open", "high", "low", "close")), "M",
                        lambda i: ml_[i], vi, c2_dir, vi_min_gap, vi_wick_overlap, vi_multi, void_rt=void_rt_ob)
    mon_ = None
    if tc["tomt"]:                                   # A12-htf-ob-trade-through-to-mt: the monthly completions and closes (an own-timeframe close test for a monthly block)
        mth_ = months(d)
        mon_ = ([pos[t] + 1 for t in mth_["last"]], mth_["close"].values.astype(float))
    if tc["oob"]:                                    # A12-sponsorship-origin-ob (cc03_003 ~12:43): the body zone of the origin candle of each daily displacement
        arrs += BH4.origin_arrays(o, h, l, c, "D", lambda i: i + 1, existing=arrs)
        BH4.sw("origin_ob")
    # opening gaps (ICT 039/051/052): NWOG Fri close -> Sun 18:00, NDOG 17:00 -> 18:00 Mon-Thu
    pos_of = {t: k for k, t in enumerate(d.index)}
    og_df = opening_gaps(df, es_pt, min_gap_pts, nwog_cfd_src)
    for r in og_df.itertuples():
        k = pos_of.get((r.known + pd.Timedelta(hours=7)).normalize().tz_localize(None))
        if k is None:
            continue
        arrs.append(Arr("bull" if r.up else "bear", r.kind, "W" if r.kind == "nwog" else "D",
                        r.high, r.low, r.ce, k))
    b2 = X.get("b2") or {}
    b3 = X.get("b3") or {}                           # caption-gap pass bias_htf#3/7 (bh3.py)
    retire = bool(b3.get("ret"))                     # caption-gap B17-no-active-array: arrays traded to their far edge by any wick are expired draws
    if b2.get("ow"):                                 # caption-gap E4-daily-one-way-delivery-rebalance (bias_htf#2/7): the one-way-delivery range as a draw
        from . import bh2
        arrs += bh2.oneway_arrays(o, h, l, c, int(b2["ow"]))
    if tc["mit"]:                                    # A15-htf-ob-as-mitigation (cc03_002 ~25:51): a broken weekly / monthly block is a daily mitigation block afterwards
        arrs += BH4.mitigation_arrays(arrs, c, D)
        BH4.sw("htf_ob_mitigation")
    arrs.sort(key=lambda a: a.known)
    piv_h, piv_l = L.pivots(h_pv, l_pv, 1)

    # overnight (reopen to 09:29) of each trading day
    lab = pd.to_datetime((df.index + pd.Timedelta(hours=7)).date)
    tmin = df.index.hour * 60 + df.index.minute
    bm = bar_minutes(df)
    keep = ((tmin < 17 * 60) & (tmin + bm <= cut_min)) | (tmin >= 17 * 60)
    pre = df[keep]
    plab = lab[keep]
    g = pre.groupby(plab)
    on = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "last": g.close.last()})

    mid_open = BH.week_open_mon(df, d) if X.get("bc") == "midnight" else None     # M0.1 bias_candle_open="midnight": the 00:00 opens
    # caption-gap new-lookback-per-tf-topdown (cc01_003 ~13:38: "your daily chart needs to show 12 months"): tf_lookback["D"] = the daily arrays' life in sessions
    lb_d = int((tf_lookback or {}).get("D") or lookback)
    dates_ = [t_.date() for t_ in d.index]
    rows = []
    wk_first = {}                                    # W-FRI period -> first session position (bias_htf: the week's open)
    for k_, t_ in enumerate(d.index):
        wk_first.setdefault(t_.to_period("W-FRI"), k_)
    for k in range(5, D):
        day = d.index[k]
        if day not in on.index:
            continue
        px = float(on.at[day, "last"])
        oh, ol = float(on.at[day, "high"]), float(on.at[day, "low"])
        lo_k = max(0, k - lb_d)
        if ipda_window:                                  # B21 ipda_arrays: only arrays / swings formed inside the 60-session window ending at the anchor
            lo_k = max(lo_k, L.ipda_end_index(dates_[:k], dates_[k], ipda_window, h[:k], l[:k], c[:k]) - 60)
        wm_ = tc["wm"]                               # A5-A10-htf-lifetime / B5-htf-lookback-9-18-months: the weekly / monthly arrays live wm_ sessions (0 = no cap) instead of the daily look-back
        lo_wm = (0 if not wm_ else max(0, k - int(wm_))) if wm_ is not None else lo_k
        live = [a for a in arrs if (lo_wm if (wm_ is not None and a.tf in ("W", "M")) else lo_k) <= a.known - 1 and a.known <= k and a.typ != "nwog"]
        live += [a for a in arrs if a.typ == "nwog" and k - lookback <= a.known <= k]   # 60 days (051)
        # NDOGs live through the week they form in (Mon-Fri)
        wk = day.to_period("W-FRI")
        live = [a for a in live if a.typ != "ndog" or d.index[a.known].to_period("W-FRI") == wk]
        rb_live = [a for a in live if a.typ == "rb"]             # A17 rejection-block closes: levels only (columns rb_up / rb_dn), never the bias
        live = [a for a in live if a.typ != "rb"]
        react = 0.0
        ru = rd = rw_up = rw_dn = 0.0
        draws_up, draws_dn = [], []
        au_, ad_, prev_age = [], [], None      # A5-pd-array-lookback-priority: the age (sessions) of every draw, parallel to the lists
        win = 60
        if ipda_first20:                                 # B21: the first window that still has an open daily array
            for cand_ in (20, 40, 60):
                if any((k - a.known + 1) <= cand_ and _arr_alive(a, k, o, h, l, c, wo, wc, wl, vi_body_death, vi_dead_rule, ol, oh, True, balance_tf, lcl)
                       for a in live if a.tf == "D" and a.typ in ("fvg", "ob", "vi")):
                    win = cand_
                    break
        for a in live:
            if tc["tiers"]:
                au_ += [prev_age] * (len(draws_up) - len(au_))
                ad_ += [prev_age] * (len(draws_dn) - len(ad_))
            s = a.known
            age_ = k - a.known + 1
            prev_age = min(age_, 60) if (a.tf in ("W", "M") and wm_ is not None) else age_      # item 113: a weekly / monthly array past the daily window keeps tier 3
            if wm_ is not None and a.tf in ("W", "M") and a.typ == "ob" and s < k and not tc["tomt"]:        # (review fix: with htf_ob_to_mt a trade through the open is not a failure - the own-timeframe MT close test decides) A5-A10-htf-lifetime (cc03_001 ~28:41): a weekly / monthly block is valid until first traded back into (its reaction window is kept)
                tch = np.flatnonzero((l[s:k] <= a.top) if a.kind == "bull" else (h[s:k] >= a.bottom))
                if len(tch) and k > s + int(tch[0]) + react_days:
                    BH4.sw("htf_lifetime_wm")
                    continue
            a.ipda_w = 20 if age_ <= 20 else 40 if age_ <= 40 else 60 if age_ <= 60 else 0
            if ipda_first20 and a.tf == "D" and a.typ in ("fvg", "ob", "vi") and (a.ipda_w == 0 or a.ipda_w > win):
                continue
            cl, hi_after, lo_after = c[s:k], h[s:k], l[s:k]
            lo_after = np.append(lo_after, ol); hi_after = np.append(hi_after, oh)
            if balance_tf == "own" and a.tf == "W" and not retire:      # A11-htf-gap-own-tf: only completed weekly bars balance a weekly gap (caption-gap B17-no-active-array retire_arrays: any daily wick that traded to the far edge expires it)
                dw_ = [j for j in range(len(wl)) if a.known < wl[j] <= k]
                hi_after = wh_[dw_] if dw_ else np.array([-np.inf])
                lo_after = wlow_[dw_] if dw_ else np.array([np.inf])
            elif retire and a.tf == "W" and ((a.kind == "bull" and lo_after.min() <= a.bottom) or (a.kind == "bear" and hi_after.max() >= a.top)):
                from . import bh3 as _bh3
                _bh3.sw("retire_arrays")
            gap = a.typ in ("ndog", "nwog")              # gaps are never retired by a fill (039)
            if a.typ == "spr":                           # 091: a single-pass range is a draw until a later low / high trades through it
                seen = np.append(l[s:k], ol).min() if a.kind == "bull" else np.append(h[s:k], oh).max()
                t_ = spr_target(a, float(seen), px)
                if t_ is not None:
                    (draws_dn if a.kind == "bull" else draws_up).append((abs(px - t_), f"{a.tf}_spr", t_))
                continue
            if not _arr_alive(a, k, o, h, l, c, wo, wc, wl, vi_body_death, vi_dead_rule, bal=balance_tf, lcl=lcl, to_mt=tc["tomt"], mon=mon_):
                continue
            if tc["tomt"] and a.typ == "ob" and a.tf in ("W", "M"):
                BH4.sw("htf_ob_to_mt")
            wt = 2.0 if a.tf == "W" else 3.0 if a.tf == "M" else 1.0
            if a.typ == "oneway":                        # caption-gap E4-daily-one-way-delivery-rebalance: a draw only, no reaction weight
                if a.kind == "bear":
                    hs_ = hi_after.max()
                    if hs_ < a.top:
                        near = max(a.bottom, hs_)
                        if near > px:
                            draws_up.append((near - px, f"{a.tf}_{a.typ}", near))
                else:
                    ls_ = lo_after.min()
                    if ls_ > a.bottom:
                        near = min(a.top, ls_)
                        if near < px:
                            draws_dn.append((px - near, f"{a.tf}_{a.typ}", near))
                continue
            # reaction in the last react_days completed days or tonight
            rl = np.append(l[max(s, k - react_days):k], ol)
            rh = np.append(h[max(s, k - react_days):k], oh)
            if ob_reach == "body" and a.typ == "ob":
                bl_, bh_ = np.minimum(o, c)[max(s, k - react_days):k], np.maximum(o, c)[max(s, k - react_days):k]
                rl, rh = (bl_ if len(bl_) else np.array([np.inf])), (bh_ if len(bh_) else np.array([-np.inf]))
            tol_ = tc["tol"]                             # caption-gap new-layered-orders-before-level (cc06_006 ~10:17): a reversal within tol_ short of an HTF level counts as the touch
            if tol_ and a.kind == "bull" and a.top < rl.min() <= a.top + tol_ and px > a.ce:
                BH4.sw("htf_reach_tol_pts")
            if tol_ and a.kind == "bear" and a.bottom > rh.max() >= a.bottom - tol_ and px < a.ce:
                BH4.sw("htf_reach_tol_pts")
            if a.kind == "bull" and rl.min() <= a.top + tol_ and px > a.ce:
                react += wt
                ru += wt
                rw_up += a.tf == "W"
            if a.kind == "bear" and rh.max() >= a.bottom - tol_ and px < a.ce:
                react -= wt
                rd += wt
                rw_dn += a.tf == "W"
            # draw: the unrebalanced part of the inefficiency (FVGs and gaps only)
            if a.typ in ("fvg", "ndog", "nwog", "vi"):
                if a.typ == "vi" and vi_two_sided:           # caption-gap A9: open until a body kills it; wicks never retire it (077)
                    if retire and ((a.top < px and lo_after.min() <= a.bottom) or (a.bottom > px and hi_after.max() >= a.top)):
                        from . import bh3 as _bh3
                        _bh3.sw("retire_arrays")
                        continue                             # caption-gap B17-no-active-array (retire_arrays): traded to its far edge = expired
                    if a.top < px:
                        draws_dn.append((px - a.top, f"{a.tf}_{a.typ}", a.top))
                    elif a.bottom > px:
                        draws_up.append((a.bottom - px, f"{a.tf}_{a.typ}", a.bottom))
                elif a.kind == "bull":
                    low_seen = lo_after.min()
                    if low_seen > a.bottom:                  # not fully rebalanced
                        near = min(a.top, low_seen)
                        if near < px:
                            draws_dn.append((px - near, f"{a.tf}_{a.typ}", near))
                        elif a.bottom > px:
                            draws_up.append((a.bottom - px, f"{a.tf}_{a.typ}", a.bottom))
                else:
                    high_seen = hi_after.max()
                    if high_seen < a.top:
                        near = max(a.bottom, high_seen)
                        if near > px:
                            draws_up.append((near - px, f"{a.tf}_{a.typ}", near))
                        elif a.top < px:
                            draws_dn.append((px - a.top, f"{a.tf}_{a.typ}", a.top))
        # liquidity: untaken daily swing highs/lows, previous day and week extremes
        if tc["tiers"]:
            au_ += [prev_age] * (len(draws_up) - len(au_))
            ad_ += [prev_age] * (len(draws_dn) - len(ad_))
        hh = np.append(h_pv[:k], oh); ll = np.append(l_pv[:k], ol)
        up_sw = [p for p in piv_h if p.known < k and p.i >= lo_k and hh[p.i + 1:].max() < p.price]
        dn_sw = [p for p in piv_l if p.known < k and p.i >= lo_k and ll[p.i + 1:].min() > p.price]
        for p in up_sw:
            draws_up.append((p.price - px, "D_swing_high", p.price))
            au_.append(k - p.i)
        for p in dn_sw:
            draws_dn.append((px - p.price, "D_swing_low", p.price))
            ad_.append(k - p.i)
        if tc["tiers"]:                              # review fix (A5-pd-array-lookback-priority): only the arrays and the swing pools are tiered by their own age; PDH / PDL / PWH / PWL sit outside the tier test
            draws_up = BH4.tier_filter(draws_up, au_)
            draws_dn = BH4.tier_filter(draws_dn, ad_)
        if h[k - 1] > max(px, oh):
            draws_up.append((h[k - 1] - px, "PDH", h[k - 1]))
            au_.append(1)
        if l[k - 1] < min(px, ol):
            draws_dn.append((px - l[k - 1], "PDL", l[k - 1]))
            ad_.append(1)
        pw = [t for t in w.index if w.at[t, "last"] < day][-1:] if len(w) else []
        if pw:
            pwh, pwl = float(w.at[pw[0], "high"]), float(w.at[pw[0], "low"])
            if pwh > max(px, oh):
                draws_up.append((pwh - px, "PWH", pwh))
                au_.append(5)
            if pwl < min(px, ol):
                draws_dn.append((px - pwl, "PWL", pwl))
                ad_.append(5)
        up = min(draws_up) if draws_up else None
        dn = min(draws_dn) if draws_dn else None
        vu = min((x for x in draws_up if x[1].endswith("_vi")), default=None)   # vi_news_draw
        vd = min((x for x in draws_dn if x[1].endswith("_vi")), default=None)
        if up and dn:
            draw = 1 if up[0] < dn[0] else -1
            if "tb" in X and abs(up[0] - dn[0]) <= X["tb"] * es_pt:       # caption-gap BH-B2-draw-by-proximity (draw_order 'nearest_tb'): a near-tie goes to the draw with fewer opposing arrays in its path
                nu = sum(1 for a in live if a.typ in ("fvg", "ob", "vi") and a.kind == "bear" and px < a.bottom < up[2])
                nd = sum(1 for a in live if a.typ in ("fvg", "ob", "vi") and a.kind == "bull" and dn[2] < a.top < px)
                if nu != nd:
                    draw = 1 if nu < nd else -1
        else:
            draw = 1 if up else (-1 if dn else 0)
        # premium / discount of the dealing range between the nearest untaken swings
        rh_ = min((p.price for p in up_sw), default=None)
        rl_ = max((p.price for p in dn_sw), default=None)
        pdb = 0
        if rh_ is not None and rl_ is not None and rh_ > rl_:
            pdb = 1 if px < (rh_ + rl_) / 2 else -1
            if "pd20" in X and X["pd20"][2] != "half":          # A21 pd_zone: the swing range's zone (third / deep / ote)
                pdb = BH.pd_state(px, rh_, rl_, X["pd20"][2], tuple(X["pd20"][3]))[0]
        rb = int(np.sign(react))
        row = dict(date=day.date(), px=px, react=rb, react_score=react, draw=draw, pd=pdb,
                   combo=rb if rb else pdb,
                   draw_up=up[2] if up else np.nan, draw_up_name=up[1] if up else "",
                   draw_dn=dn[2] if dn else np.nan, draw_dn_name=dn[1] if dn else "",
                   vi_up=vu[2] if vu else np.nan, vi_dn=vd[2] if vd else np.nan)
        if rb_closes:
            rbu, rbd = [], []
            for a in rb_live:                          # untaken: no later session's wick (nor tonight's) traded through the close
                if a.kind == "bear" and np.append(h[a.src_i + 1:k], oh).max() < a.ce and a.ce > px:
                    rbu.append(a.ce)
                elif a.kind == "bull" and np.append(l[a.src_i + 1:k], ol).min() > a.ce and a.ce < px:
                    rbd.append(a.ce)
            row["rb_up"], row["rb_dn"] = (min(rbu) if rbu else np.nan), (max(rbd) if rbd else np.nan)
        if X:
            wk0 = wk_first.get(wk)
            d_open_ = float(o[k])
            w_open_ = float(o[wk0]) if wk0 is not None else float(o[k])
            if mid_open is not None:                  # the 00:00 open of the day / of the week's first session (the Sunday 18:00 open is the default)
                m_ = mid_open.get(day, float("nan"))
                d_open_ = m_ if m_ == m_ else d_open_
                m_ = mid_open.get(d.index[wk0], float("nan")) if wk0 is not None else float("nan")
                w_open_ = m_ if m_ == m_ else w_open_
            row.update(BH.row_extras(X, px, oh, ol, d_open_, w_open_,
                                     draws_up, draws_dn, pdb, ru, rd, rw_up, rw_dn, live, es_pt))
        rows.append(row)
    cols = ["date", "px", "react", "react_score", "draw", "pd", "combo", "draw_up", "draw_up_name",
            "draw_dn", "draw_dn_name"] + (["vi_up", "vi_dn"] if vi else []) + (["rb_up", "rb_dn"] if rb_closes else [])
    if X:
        cols += [k_ for k_ in (rows[0] if rows else {}) if k_ not in cols]
    out = pd.DataFrame(rows, columns=cols or None).set_index("date")
    b1 = X.get("b1") or {}
    pd3_log = None
    fl_b2 = {}
    if b2:
        from . import bh2
        fl_b2 = bh2.flip_cfg(b2)                     # caption-gap bias_htf#2/7: flip_pd3 neutral result / first-array caution log
        pd3_log = fl_b2.get("pd3_log")
    fl_b3 = {}
    if b3:
        from . import bh3
        fl_b3 = bh3.flip_cfg(b3, es_pt)              # caption-gap bias_htf#3/7: the tue_fail tolerance
    defer = bool(flip_triggers and "ob_low_touch" in flip_triggers and X)          # caption-gap BH-B9-HTF-OB-low-trade-through: the objective-met columns come from add_columns
    if flip_triggers and len(out) and not defer:
        fl = _flip(d, w, arrs, flip_triggers, dict(b1.get("fl") or {}, **fl_b2, **fl_b3, **({"wk_joint": wk_joint} if wk_joint is not None else {})))
        out["flip"] = [fl.get(pd.Timestamp(x), 0) for x in out.index]
    if X and len(out):
        out = BH.add_columns(out, X, d, w, arrs, og_df, on, df, es_pt, vi)
    if defer and len(out):
        cfg_ = dict(b1.get("fl") or {}, **fl_b2, **fl_b3)
        if wk_joint is not None:
            cfg_["wk_joint"] = wk_joint
        if "obj_day" in out or "obj_week" in out:
            pos_k = {t_.date(): q for q, t_ in enumerate(d.index)}
            om = np.zeros(len(d), int)
            for x_, a_, b_ in zip(out.index, out.obj_day.values if "obj_day" in out else np.zeros(len(out), int), out.obj_week.values if "obj_week" in out else np.zeros(len(out), int)):
                om[pos_k[x_]] = int(bool(a_) or bool(b_))
            cfg_["obj"] = om
        fl = _flip(d, w, arrs, flip_triggers, cfg_)
        out["flip"] = [fl.get(pd.Timestamp(x), 0) for x in out.index]
    if b2 and len(out):
        from . import bh2
        out = bh2.finish(out, b2, d, w, arrs, es_pt, b1.get("dr"), pd3_log)       # caption-gap bias_htf#2/7 (bh2.py): the columns after the flip
    if b3 and len(out):
        from . import bh3
        out = bh3.finish3(out, b3, d, w, arrs, es_pt, df)                           # caption-gap bias_htf#3/7 (bh3.py): the columns after bh2.finish
    b4 = dict(X.get("b4") or {})
    if b4 and len(out):
        b4["_cut"] = int(cut_min)
        out = BH4.finish4(out, b4, d, w, arrs, es_pt, df)                            # caption-gap bias_htf#4/7 (bh4.py): the columns after bh3.finish3
    b5 = dict(X.get("b5") or {})
    if b5 and len(out):
        if X.get("pd20"):
            b5["_pd20"] = X["pd20"]
        out = BH5.finish5(out, b5, d, w, arrs, es_pt, df)                            # caption-gap bias_htf#5/7 (bh5.py): the columns after bh4.finish4
    return out


FLIP_TRIGGERS = ("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen",
                 "wk_bisi", "inv3", "ob_low_touch", "wk_rb", "d_breaker", "inv3_lit",       # (caption-gap bias_htf#1/7, bh1.py: the five before the last)
                 "tue_fail")                                                                 # (caption-gap bias_htf#3/7, bh3.TueFail: B8-tuesday-failure-swing-flip)


def _flip(d: pd.DataFrame, w: pd.DataFrame, arrs: list, triggers: tuple, cfg: dict | None = None) -> dict:
    """Stateful bias column (B8; shared helper for B8a-f, B9, B13, B17.3). The state persists
    from day to day and changes only on a trigger, evaluated at each completed session's close
    and applied from the NEXT session (no look-ahead). Triggers:
      ob_mt   (B7/B8a) a daily close through the mean threshold of the most recent bullish daily
              OB (from above -> -1) or bearish daily OB (from below -> +1)
      wk_dc   (B8c) a week closing above the high of the last down-close week (+1) or below the
              low of the last up-close week (-1)
      flip_pd3  (B8b; 098 ~47:00, 078 ~1:02:38) bodies closing through THREE supporting daily /
              weekly PD arrays (FVG bottom / OB MT for a bullish state) since the state began ->
              the other side [our interpretation: distinct arrays, each counted once]
      flip_close_above  (B8d; 077 ~10:53, 098 ~67:30, 102 ~6:45, 103 ~2:29) in a bearish state a
              daily close above the last Friday's high, the prior session's upper-wick CE or the
              last completed week's upper-wick upper quadrant -> neutral (rule_coverage B8d: the
              result is set to neutral); mirrored for a bullish state [our interpretation: any one]
      flip_thu_wopen  (B8e; cc08_001 ~24:20) a Thursday body close back across the week's
              opening price against the state -> the other side
    Caption-gap pass (bias_htf#1/7, bh1.FlipState; `cfg` = the "fl" block of Params.bx plus an optional "obj" array of the B17.3 objective-met flags per session):
      wk_bisi       (BH-weekly-BISI-CE-and-full-close, 011 ~5:06; 047 ~2:05) a weekly close below the low of the nearest weekly bull FVG under the previous weekly close -> -1 (above the
                    top of the nearest weekly bear FVG above it -> +1); with cfg "ce" a weekly close below its CE (above, for the bear one) turns a bullish (bearish) state neutral
      inv3_lit      the same sequence with the spec's literal inefficiency: the nearest daily BEAR FVG below a bullish state (BULL FVG above a bearish one) instead of the supporting FVG
      inv3          (BH-B8-draw-flip-via-inversion, 011 ~0:49; 063 ~2:57) bias -> neutral when the guarding daily swing low is taken and price trades into the nearest daily bull FVG under it
                    (the opposing inefficiency) -> the opposite bias after a daily close through that FVG and a later day that trades back into it and closes below it again
      ob_low_touch  (BH-B9-HTF-OB-low-trade-through, 062 ~22:39) objective met: a daily trade (no close needed) below the last bullish daily OB candle's low -> neutral (not bearish)
      wk_rb         (BH-weekly-rejection-block-range-proof, 070 ~1:01) an indecisive weekly candle (body < 30 % of its range) that traded into a weekly FVG -> neutral until a daily high above its
                    body top (+1) or a daily low below its low (-1)
      d_breaker     (BH-B8-daily-breaker-bias, 035 ~51:30) a daily bearish (bullish) breaker, once a later day trades into it and closes below (above) it -> -1 (+1); a close above its top
                    (below its bottom) -> neutral
    cfg "persist" (BH-B9-retrace-above-swing-low, 077 ~11:02) suppresses a flip to the opposite state while the daily low (high) stays above (below) the last daily pivot low (high) and the
    nearest bull (bear) daily FVG is still partly open; cfg "b7" ('mt_trade' / 'ob_close') changes the level the ob_mt trigger tests (BH-B7-last-daily-OB-guard).
    stop_flip (B8f) is intraday and lives in the engine (Params.stop_flip), not in this column.
    Returns {session date: state known before that session}."""
    if "stop_flip" in triggers:
        raise ValueError("stop_flip (B8f) is an intraday engine switch: Params.stop_flip, not a flip trigger")
    bad = set(triggers) - set(FLIP_TRIGGERS)
    if bad:
        raise ValueError(f"flip triggers {sorted(bad)}: expected from {FLIP_TRIGGERS}")
    o = d.open.values.astype(float)
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    obs = [a for a in arrs if a.typ == "ob" and a.tf == "D"]
    pd_arrs = [a for a in arrs if a.typ in ("fvg", "ob") and a.tf in ("D", "W")]
    wk_last = {}                                   # session index -> its week's row (last session)
    pos = {t: k for k, t in enumerate(d.index)}
    for r in w.itertuples():
        wk_last[pos[r.last]] = r
    wk_of = d.index.to_period("W-FRI")
    wk_open = {}
    for k in range(len(d)):
        wk_open.setdefault(wk_of[k], o[k])
    state, out = 0, {}
    last_dn_week = last_up_week = None
    last_week = None                               # the last COMPLETED week's row
    last_fri = None                                # index of the last completed Friday session
    broken: set = set()                            # flip_pd3: arrays closed through in this state
    cfg = cfg or {}
    joint = cfg.get("wk_joint")
    b7 = cfg.get("b7", "mt_close")
    new_tr = bool(set(triggers) & {"wk_bisi", "inv3", "inv3_lit", "ob_low_touch", "wk_rb", "d_breaker"}) or bool(cfg.get("persist"))
    fs = None
    if new_tr:
        from . import bh1
        fs = bh1.FlipState(d, w, arrs, triggers, cfg)
    tf_obj, tf_hold = None, None                   # caption-gap B8-tuesday-failure-swing-flip
    if "tue_fail" in triggers and cfg.get("tue_tol") is not None:
        from . import bh3
        tf_obj = bh3.TueFail(d, w, cfg["tue_tol"])
    pd3n = cfg.get("pd3n")                         # caption-gap B8-three-pd-array-abort: the displacement multiple (None = flip_pd3 flips as built)
    pd3_log = cfg.get("pd3_log")                   # {date: arrays closed through in the state, known before the session} (the first-array caution)
    pd3_pend, pd3_set = 0, -1
    for k in range(len(d)):
        out[d.index[k]] = state                     # known before session k
        if pd3_log is not None:
            pd3_log[d.index[k]] = len(broken)
        prev = state
        if "ob_mt" in triggers and k >= 1:
            bull = [a for a in obs if a.kind == "bull" and a.known <= k]
            bear = [a for a in obs if a.kind == "bear" and a.known <= k]
            if b7 == "mt_trade":                    # caption-gap BH-B7-last-daily-OB-guard: any trade through the MT (a wick) counts
                if bull and l[k] < bull[-1].ce <= c[k - 1]:
                    state = -1
                if bear and h[k] > bear[-1].ce >= c[k - 1]:
                    state = 1
            elif b7 == "ob_close":                  # ... or a close through the OB's far side
                if bull and c[k] < bull[-1].bottom <= c[k - 1]:
                    state = -1
                if bear and c[k] > bear[-1].top >= c[k - 1]:
                    state = 1
            else:
                if bull and c[k] < bull[-1].ce <= c[k - 1]:
                    state = -1
                if bear and c[k] > bear[-1].ce >= c[k - 1]:
                    state = 1
        if "flip_pd3" in triggers and state != 0 and k >= 1:
            for j, a in enumerate(pd_arrs):
                if j in broken or a.known > k or a.kind != ("bull" if state > 0 else "bear"):
                    continue
                lvl = a.ce if a.typ == "ob" else (a.bottom if state > 0 else a.top)
                was = c[a.known:k]
                intact = (was.min(initial=np.inf) >= lvl) if state > 0 else (was.max(initial=-np.inf) <= lvl)
                if intact and (c[k] < lvl if state > 0 else c[k] > lvl):
                    broken.add(j)
            if len(broken) >= 3:
                if pd3n:                           # caption-gap B8-three-pd-array-abort (bias_htf#2/7): abandon the bias (neutral); the opposite state only after a displacement day
                    pd3_pend, pd3_set = -state, k
                    state = 0
                    from . import bh2 as _bh2
                    _bh2.sw("pd3_result")
                else:
                    state = -state
        if "flip_close_above" in triggers and state != 0 and k >= 1:
            ub = max(o[k - 1], c[k - 1])
            lb = min(o[k - 1], c[k - 1])
            if state < 0:
                lv = [ub + (h[k - 1] - ub) / 2]
                if last_fri is not None:
                    lv.append(h[last_fri])
                if last_week is not None:
                    wb = max(last_week.open, last_week.close)
                    lv.append(last_week.high - 0.25 * (last_week.high - wb))
                if any(c[k] > x for x in lv):
                    state = 0
            else:
                lv = [lb - (lb - l[k - 1]) / 2]
                if last_fri is not None:
                    lv.append(l[last_fri])
                if last_week is not None:
                    wb = min(last_week.open, last_week.close)
                    lv.append(last_week.low + 0.25 * (wb - last_week.low))
                if any(c[k] < x for x in lv):
                    state = 0
        if "flip_thu_wopen" in triggers and d.index[k].weekday() == 3 and state != 0:
            wo = wk_open[wk_of[k]]
            if state > 0 and c[k] < wo < o[k]:
                state = -1
            elif state < 0 and c[k] > wo > o[k]:
                state = 1
        if tf_obj is not None:                       # caption-gap B8-tuesday-failure-swing-flip (bias_htf#3/7): the failure swing at Tuesday's close flips the state for Wed-Fri
            if d.index[k].weekday() == 1 and k >= 1 and d.index[k - 1].weekday() == 0 and wk_of[k - 1] == wk_of[k]:
                v_ = tf_obj.step(k)
                if v_ and v_ != state:
                    tf_hold = (state, v_, wk_of[k])
                    state = v_
                    from . import bh3 as _bh3
                    _bh3.sw("tue_fail")
            if tf_hold is not None and (k + 1 >= len(d) or wk_of[k + 1] != tf_hold[2]):
                if state == tf_hold[1]:
                    state = tf_hold[0]               # the week is over: the state before the failure swing returns [our interpretation of 'for the rest of the week']
                tf_hold = None
        if "wk_dc" in triggers and k in wk_last:
            r = wk_last[k]
            if last_dn_week is not None and r.close > last_dn_week:
                state = 1
            elif last_up_week is not None and r.close < last_up_week:
                if joint is None or joint.get(d.index[k].date(), False):
                    state = -1                       # (caption-gap B8-weekly-ith-both-indices-close: with wk_dc_joint only while ES and NQ both closed below)
            if r.close < r.open:
                last_dn_week = r.high
            elif r.close > r.open:
                last_up_week = r.low
        if pd3_pend and k > pd3_set:                 # B8-three-pd-array-abort: a displacement day in the new direction ends the neutral wait
            if state != 0:
                pd3_pend = 0
            elif k >= 5:
                adr_ = float((h[k - 5:k] - l[k - 5:k]).mean())
                rng_ = float(h[k] - l[k])
                if adr_ > 0 and rng_ >= float(pd3n) * adr_ and ((pd3_pend > 0 and c[k] >= l[k] + 0.75 * rng_) or (pd3_pend < 0 and c[k] <= l[k] + 0.25 * rng_)):
                    state = pd3_pend
                    pd3_pend = 0
        if fs is not None:
            state = fs.step(k, state, last_week, prev)       # caption-gap bias_htf#1/7: the five new triggers and the B9 persistence
        if k in wk_last:
            last_week = wk_last[k]
        if d.index[k].weekday() == 4:
            last_fri = k
        if state != prev:
            broken = set()
    return out


def has_overnight(df: pd.DataFrame) -> bool:
    t = df.index.hour
    return bool(((t >= 18) | (t < 4)).mean() > 0.1)


NWOG_SRCS = ("auto", "sunday_bars", "monday_0930", "sunday_else_monday", "none")


GAP_VIEWS = ("auto", "both")


def opening_gaps(df: pd.DataFrame, es_pt: float = 1.0, ndog_min_pts: float = 1.0, nwog_src: str = "auto",
                 gap_views: str = "auto", rth_close: int = 960) -> pd.DataFrame:
    """ICT's opening gaps from bars that include the evening reopen (videos 039, 051, 052):
      NWOG  Friday's last price before the weekend close -> Sunday's first price at the 18:00
            reopen. Levels: high, low, CE. No minimum size; never retired by a fill.
      NDOG  a weekday's last price before the 17:00 close -> the 18:00 reopen (Mon-Thu
            evenings). Only gaps > ~1 ES handle count; they live through the end of that week.
    One row per gap: kind, high, low, ce, known (the reopen time), week (W-FRI period of the
    trading day the reopen starts).
    Caption-gap L5-cfd-nwog-mapping (036 ~1:32:40: "it's not going to be perfect"; `nwog_src` = Params.nwog_cfd_src): an SPX / NDX CFD's NWOG is
    the CFD close of the bar at the futures' Friday close time and the CFD open of the first bar at or after Sunday 18:00 (futures data
    preferred). "sunday_bars" = exactly that: a weekend whose first bar is NOT a Sunday-evening bar is left out and FLAGGED unavailable
    (`result.attrs["nwog_unavailable"]` = the dates of the first bar after each such weekend; the NWOG is NaN / missing, never guessed);
    "monday_0930" = the L5 variant of video 039: Friday's last close -> the open of the Monday 09:30 bar (known when that bar closes);
    "sunday_else_monday" = the PER-WEEKEND fall-back (review fix #68): a weekend that has a Sunday-evening reopen bar uses it, one that
    does not uses the Monday 09:30 variant (the Monday is the first date after the break that is not the Sunday; no bar at 09:30-12:00 that
    day = unavailable, flagged); "none" = no NWOG rows; "auto" = the built behaviour = "sunday_bars" (the fall-back to the Monday variant is an explicit choice, never
    silent: a frame without Sunday bars - SPY extended hours - would otherwise grow NWOGs it never had).
    Caption-gap L5-rth-and-eth-gap-views (levels_detectors #3/3; 019 ~4:31: "you use regular trading hours and electronic trading hours"):
    `gap_views` = "both" (Params.gap_views) also keeps the RTH-bar view of the weekend gap - kind "nwog_rth": the last RTH close of the Friday
    (the last bar starting before `rth_close`, minute of day) -> the open of the Monday 09:30 bar (known when that bar closes), next to
    the ETH "nwog" with no de-duplication ("auto" = the ETH rows only, as before). The Monday is the first date after the break that is not
    the Sunday evening; no 09:30-12:00 bar that day = no row."""
    if nwog_src not in NWOG_SRCS:
        raise ValueError(f"nwog_cfd_src {nwog_src!r}: expected one of {NWOG_SRCS}")
    if gap_views not in GAP_VIEWS:
        raise ValueError(f"gap_views {gap_views!r}: expected one of {GAP_VIEWS}")
    t = df.index
    gap = t.to_series().diff() > pd.Timedelta(minutes=45)
    m = t.hour * 60 + t.minute
    reopen = gap.values & (m >= 17 * 60) & (m < 19 * 60)     # evening reopen after the break
    weekend_brk = np.flatnonzero((t[1:] - t[:-1]) > pd.Timedelta(hours=30)) + 1 if len(t) > 1 else np.array([], int)
    sunday = {int(k) for k in weekend_brk if t[k].weekday() == 6 and 17 * 60 <= m[k] < 19 * 60}
    src = "sunday_bars" if nwog_src == "auto" else nwog_src
    mon_wk = {int(k) for k in weekend_brk if int(k) not in sunday} if src == "sunday_else_monday" else None
    rows = []
    unavailable = []
    for k in np.flatnonzero(reopen):
        if k == 0:
            continue
        a, b = float(df.close.iloc[k - 1]), float(df.open.iloc[k])
        weekend = (t[k] - t[k - 1]) > pd.Timedelta(hours=30)
        if weekend and src not in ("sunday_bars", "sunday_else_monday"):
            continue
        if not weekend and abs(b - a) <= ndog_min_pts * es_pt:
            continue
        pm = t[k - 1].hour * 60 + t[k - 1].minute
        if not weekend and not (960 <= pm < 1020):
            continue                                  # holiday early close: not a 17:00 close
        day = (t[k] + pd.Timedelta(hours=7)).normalize().tz_localize(None)
        rows.append(dict(kind="nwog" if weekend else "ndog", high=max(a, b), low=min(a, b),
                         ce=(a + b) / 2, up=b > a, known=t[k], week=day.to_period("W-FRI"),
                         # caption-gap L5 (051 ~5:38): nwog_high = max(Friday close, Sunday open), nwog_low = min; gap_dir = "down" when
                         # the Friday close is above the Sunday open, else "up". a = the last print before the break (Friday's close)
                         dir="down" if a > b else "up", close_before=a, open_after=b))
    if src == "sunday_bars":
        unavailable = [t[int(k)] for k in weekend_brk if int(k) not in sunday]
    if src in ("monday_0930", "sunday_else_monday"):
        bm = bar_minutes(df)
        for k in (weekend_brk if src == "monday_0930" else sorted(mon_wk)):
            k = int(k)
            d0 = t[k].normalize()
            if t[k].weekday() == 6:                    # review fix #68: skip the Sunday-evening bars - the 09:30 bar is the MONDAY's
                d0 = d0 + pd.DateOffset(days=1)         # (calendar day: a Sunday DST change would shift an absolute 24 h)
            j = int(t.searchsorted(d0.replace(hour=9, minute=30)))
            if j >= len(t) or t[j].normalize() != d0 or t[j].hour * 60 + t[j].minute >= 12 * 60:
                unavailable.append(t[k])
                continue
            a, b = float(df.close.iloc[k - 1]), float(df.open.iloc[j])
            day = (t[j] + pd.Timedelta(hours=7)).normalize().tz_localize(None)
            rows.append(dict(kind="nwog", high=max(a, b), low=min(a, b), ce=(a + b) / 2, up=b > a,
                             known=t[j] + pd.Timedelta(minutes=bm), week=day.to_period("W-FRI"),
                             dir="down" if a > b else "up", close_before=a, open_after=b))
        rows.sort(key=lambda r: r["known"])
    if gap_views == "both":
        bm = bar_minutes(df)
        for k in weekend_brk:
            k = int(k)
            fri = t[k - 1].normalize()
            fm = (t.hour * 60 + t.minute)[:k]
            fk = np.flatnonzero((t[:k].normalize() == fri) & (fm >= 570) & (fm < rth_close))
            if not len(fk):
                continue
            a = float(df.close.iloc[int(fk[-1])])
            d0 = t[k].normalize()
            if t[k].weekday() == 6:
                d0 = d0 + pd.DateOffset(days=1)
            j = int(t.searchsorted(d0.replace(hour=9, minute=30)))
            if j >= len(t) or t[j].normalize() != d0 or t[j].hour * 60 + t[j].minute >= 12 * 60:
                continue
            b = float(df.open.iloc[j])
            day = (t[j] + pd.Timedelta(hours=7)).normalize().tz_localize(None)
            rows.append(dict(kind="nwog_rth", high=max(a, b), low=min(a, b), ce=(a + b) / 2, up=b > a,
                             known=t[j] + pd.Timedelta(minutes=bm), week=day.to_period("W-FRI"),
                             dir="down" if a > b else "up", close_before=a, open_after=b))
        rows.sort(key=lambda r: r["known"])
    out = pd.DataFrame(rows)
    out.attrs["nwog_unavailable"] = unavailable
    return out


def nwog_rebalanced(df: pd.DataFrame, og: pd.DataFrame, tick: float, pts: float = 1.0, sessions_max: int = 5, life_sessions: int = 60) -> dict:
    """Caption-gap L5-partial-redelivery (019 ~16:36; Params.nwog_rebalanced): for each NWOG of `og` the time at which it became REBALANCED
    by the both-way redelivery sequence (levels.nwog_redelivery: far edge reached, back through the gap, a return that only reaches the CE
    and fails, an exit leg that leaves a lone FVG at the gap edge). The sequence is causal, so the state at time T needs only the bars up
    to T. Returns {(round(high, 6), round(low, 6)): (known_time, near_edge, exit_edge, until_time)} - known_time = the close of the bar that
    completes the sequence; near_edge = the gap edge on the Sunday-open side; exit_edge = the exit FVG's near edge; until_time = the
    close of the bar that later reached the far edge again (a full redelivery un-rebalances the gap), or None. Review fix #18: the
    sequence must complete within `sessions_max` sessions (the first trading week) of the Sunday open [our interpretation]; the gap
    must be taller than 2 x `pts`; the exit FVG must be the lone FVG of the leg (levels.nwog_redelivery)."""
    if og is None or not len(og):
        return {}
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    bm = bar_minutes(df)
    per_day = max(1, 24 * 60 // bm)
    out = {}
    for r in og[og.kind == "nwog"].itertuples():
        k0 = int(df.index.searchsorted(r.known))
        end = min(len(df) - 1, k0 + sessions_max * per_day)
        res = L.nwog_redelivery(o, h, l, c, k0, float(r.open_after), float(r.close_before), tick, pts, end,
                                min(len(df) - 1, k0 + life_sessions * per_day))
        if res is not None:
            k, edge, u = res
            out[(round(float(r.high), 6), round(float(r.low), 6))] = (
                df.index[k] + pd.Timedelta(minutes=bm), float(r.open_after), float(edge),
                None if u is None else df.index[u] + pd.Timedelta(minutes=bm))
    return out


class GapList(list):
    """gaps_for_day result that also carries `reb`: {(high, low): (known_time, near_edge, exit_edge, until_time)} of the rebalanced NWOGs (see nwog_rebalanced)."""
    reb = None


def gaps_for_day(g: pd.DataFrame, day, nwog_keep: int = 5, nwog_days: int = 0, skip_holiday: bool = False,
                 trading_days: bool = False, with_dir: bool = False, reb: dict | None = None,
                 holiday_pick: str = "all", ref_px: float | None = None) -> list[tuple]:
    """Gaps in force at 09:30 of `day`: NWOGs (the last `nwog_keep`, or with `nwog_days` > 0
    every NWOG from the last that many trading days - ICT's 60-day maximum, 051 ~18:02,
    "60 market days", 065) and this week's NDOGs. Returns (kind, high, low, ce).
    levels_detectors L5: `trading_days` counts nwog_days in real trading days (calendar module)
    instead of the old calendar estimate; `skip_holiday` (046 ~16:01; 048 ~2:54) drops the NWOG
    of a holiday-shortened week (fewer than 5 trading days) - the nearest normal ones remain.
    Caption-gap L5-holiday-nwog (levels_detectors #3/3; 046 ~16:34: "if I don't have it then I don't use it"): with `skip_holiday` and
    `holiday_pick` = "closest" (Params.nwog_holiday_pick), when THIS week's NWOG was dropped as a holiday week only the single remaining
    NWOG (within the nwog_days / nwog_keep selection) closest to the reference price `ref_px` (the day's open) stays - the distance from
    the price to the gap's range, then to its CE; none when there is no other. "all" (default) keeps every normal NWOG. Caption-gap
    L5-rth-and-eth-gap-views: the "nwog_rth" rows of opening_gaps(gap_views="both") are selected like the NWOGs (same rules, own list)."""
    if g is None or not len(g):
        return []
    cut = pd.Timestamp(day, tz=NY_TZ) + pd.Timedelta(hours=9, minutes=30)
    k = g[g.known < cut]
    wk = pd.Timestamp(day).to_period("W-FRI")
    skipped_now = [False]

    def pick(nw, nwog_days=nwog_days):
        if skip_holiday and len(nw):
            from .calendar import is_trading_day
            full = np.asarray([sum(is_trading_day((w.start_time + pd.Timedelta(days=j)).date()) for j in range(7)) >= 5
                               for w in nw.week], bool)
            skipped_now[0] = skipped_now[0] or bool((~full & (nw.week.values == wk)).any())
            nw = nw[full]
        if nwog_days:
            if trading_days:
                from .calendar import prev_trading_day
                d0 = day
                for _ in range(nwog_days):
                    d0 = prev_trading_day(d0)
                # formed at or after the start of the earliest counted session (its 18:00 reopen)
                nw = nw[nw.known >= pd.Timestamp(d0, tz=NY_TZ) - pd.Timedelta(hours=6)]
            else:
                nw = nw[nw.known >= cut - pd.Timedelta(days=round(nwog_days * 7 / 5) + 2)]
        else:
            nw = nw.tail(nwog_keep)
        return nw

    nw = pick(k[k.kind == "nwog"])
    nr = pick(k[k.kind == "nwog_rth"]) if (k.kind == "nwog_rth").any() else k.iloc[:0]
    if holiday_pick == "closest" and skipped_now[0] and ref_px is not None:
        def dist(r):
            d_rng = 0.0 if r.low <= ref_px <= r.high else min(abs(ref_px - r.low), abs(ref_px - r.high))
            return (d_rng, abs(ref_px - r.ce))
        # the closest NORMAL NWOG "formed within the last 60 days" (046 ~16:23): the candidates are the 60 trading days (nwog_days when set), not nwog_keep
        d60 = nwog_days or 60
        nw = pick(k[k.kind == "nwog"], d60)
        nr = pick(k[k.kind == "nwog_rth"], d60) if (k.kind == "nwog_rth").any() else k.iloc[:0]
        both = pd.concat([nw, nr])                       # ONE NWOG: the ETH and RTH rows of the closest weekend (levels_detectors #3/3 review)
        if len(both):
            best = min(both.itertuples(), key=dist)
            nw, nr = nw[(nw.week.values == best.week)], nr[(nr.week.values == best.week)]
    nd = k[(k.kind == "ndog") & (k.week == wk)]
    sel = pd.concat([nw, nr, nd])
    if with_dir:                      # caption-gap L5: (kind, high, low, ce, dir) - the labels as a tag, "up" / "down"
        return [(r.kind, r.high, r.low, r.ce, r.dir) for r in sel.itertuples()]
    rows = [(r.kind, r.high, r.low, r.ce) for r in sel.itertuples()]
    if reb is None:
        return rows
    out = GapList(rows)               # caption-gap L5-partial-redelivery: the rebalanced-NWOG table rides along (list equality unchanged)
    out.reb = reb
    return out


NY_TZ = "America/New_York"


# --- Caption-gap pass bias_htf#5/7 helpers (no table effect) -----------------------------------------------------------------------------------------

def mw_side(m: int, w: int) -> int:
    """M17-swing-trade-definition (cc06_001 ~0:50: 'trade durations of two weeks or longer in time'): the M/W side gate of the future swing engine - +1 only when the monthly AND the weekly bias are both bullish,
    -1 only when both are bearish, else 0 (no swing trade). The table's `bias_m` / `bias_w` columns are the inputs (`mw_side_row`)."""
    m, w = int(m or 0), int(w or 0)
    return 1 if (m > 0 and w > 0) else (-1 if (m < 0 and w < 0) else 0)


def mw_side_row(row) -> int:
    def g(k):
        try:
            v = row.get(k)
            return 0 if v is None or v != v else int(v)
        except Exception:
            return 0
    return mw_side(g("bias_m"), g("bias_w"))


def mega_tag(entry_day, exit_day, symbol: str = "", min_days: int = 126, zb_handles: float | None = None) -> str:
    """new-mega-trade-definition (cc11_003 ~0:37, cc11_004 ~43:02: 'six to nine months or more in the stock market'): "mega" when a position entered at a quarterly-shift / seasonal low was held at least
    `min_days` trading days (Params.mega_min_days; stocks: 6-9+ months) - or, for the bonds (ZB), when the move is at least 10 handles (about $10,000 per contract; `zb_handles`, a tag only) - else "".
    The hold counts the weekdays from entry to exit (holidays are not removed) [our interpretation]; a classifier for a future stock / position engine."""
    if str(symbol).upper().startswith("ZB") and zb_handles is not None:
        return "mega" if abs(float(zb_handles)) >= 10.0 else ""
    a, b = pd.Timestamp(entry_day).normalize(), pd.Timestamp(exit_day).normalize()
    n = int(np.busday_count(a.date(), b.date()))
    return "mega" if n >= int(min_days) else ""
