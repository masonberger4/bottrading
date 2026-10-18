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


def sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Daily OHLC per trading day (futures-style: evening reopen to the afternoon close)."""
    lab = (df.index + pd.Timedelta(hours=7)).date
    g = df.groupby(lab)
    d = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                      "close": g.close.last(), "n": g.close.size()})
    d.index = pd.to_datetime(d.index)
    return d[d.n >= 60].drop(columns="n")            # drop stub sessions (holiday fragments)


def weeks(d: pd.DataFrame) -> pd.DataFrame:
    w = d.groupby(d.index.to_period("W-FRI"))
    out = pd.DataFrame({"open": w.open.first(), "high": w.high.max(), "low": w.low.min(),
                        "close": w.close.last(), "last": w.apply(lambda x: x.index[-1])})
    return out


def _arrays(o, h, l, c, tf: str, known_of, vi: bool = False, c2_dir: bool = False,
            vi_min_gap: float = 0.0) -> list[Arr]:
    """Daily / weekly arrays. levels_detectors: `c2_dir` (A5 fvg_c2_dir) keeps only FVGs whose
    middle candle closes their way; `vi_min_gap` (A9) drops narrower VIs."""
    out = []
    if vi:                       # shared VI wiring (Ep02.8 / Ep03.3 / B1): daily/weekly volume
        for z in L.volume_imbalances(o, h, l, c, vi_min_gap):   # imbalances as arrays and draws
            a = Arr(z.kind, "vi", tf, z.top, z.bottom, z.mid, known_of(z.i))
            a.src_i = z.i                                     # its own-TF bar (A9 body death)
            out.append(a)
    for z in L.fvgs(h, l, o, c, c2_dir):
        out.append(Arr(z.kind, "fvg", tf, z.top, z.bottom, z.mid, known_of(z.i)))
        # order block: last opposite-close candle before the displacement candle
        kind = "bull" if z.kind == "bull" else "bear"
        ob = L.order_block_blend(o, h, l, c, z.i - 4, z.i - 2, kind)
        if ob is not None:
            disp = c[z.i - 1]
            if (kind == "bull" and disp > ob.top) or (kind == "bear" and disp < ob.bottom):
                out.append(Arr(kind, "ob", tf, ob.top, ob.bottom, ob.mt, known_of(z.i)))
    return out


def bar_minutes(df: pd.DataFrame) -> int:
    if len(df) < 2:
        return 1
    d = pd.Series(df.index[1:] - df.index[:-1])
    return max(1, int(d[d > pd.Timedelta(0)].min().total_seconds() // 60))


def table(df: pd.DataFrame, es_pt: float = 1.0, react_days: int = 2, lookback: int = 60,
          min_gap_pts: float = 1.0, cut_min: int = 570, vi: bool = False,
          flip_triggers: tuple = ("ob_mt", "wk_dc"), c2_dir: bool = False, vi_min_gap: float = 0.0,
          vi_body_death: bool = False) -> pd.DataFrame:
    """One row per trading day: react / draw / pd / combo bias and the draw levels.
    `cut_min`: the row describes the market as known at that minute of the day - the overnight
    high/low/last use only bars that have CLOSED by cut_min (bar start + bar length <= cut_min).
    The default 570 (09:30) gives the original table; the draw lock (owner #9) builds one table
    per session lock time (13:30 for the PM, ...). `vi` adds daily/weekly volume imbalances as
    arrays/draws (shared VI wiring). `flip` is the stateful bias column (B8; shared): see _flip.
    levels_detectors: `c2_dir` / `vi_min_gap` (see _arrays); `vi_body_death` (A9 / Ep03.3): a VI
    dies once a later body of its own timeframe spans it (not on a close beyond its far edge).
    With `vi`, the columns vi_up / vi_dn hold the nearest live VI draw each way (vi_news_draw)."""
    d = sessions(df)
    D = len(d)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    arrs = _arrays(o, h, l, c, "D", lambda i: i + 1, vi, c2_dir, vi_min_gap)
    # weekly arrays become usable the day after the week's last session
    w = weeks(d)
    pos = {t: k for k, t in enumerate(d.index)}
    wl = [pos[t] + 1 for t in w["last"]]
    wo, wc = w.open.values.astype(float), w.close.values.astype(float)
    arrs += _arrays(*(w[k].values.astype(float) for k in ("open", "high", "low", "close")), "W",
                    lambda i: wl[i], vi, c2_dir, vi_min_gap)
    # opening gaps (ICT 039/051/052): NWOG Fri close -> Sun 18:00, NDOG 17:00 -> 18:00 Mon-Thu
    pos_of = {t: k for k, t in enumerate(d.index)}
    for r in opening_gaps(df, es_pt, min_gap_pts).itertuples():
        k = pos_of.get((r.known + pd.Timedelta(hours=7)).normalize().tz_localize(None))
        if k is None:
            continue
        arrs.append(Arr("bull" if r.up else "bear", r.kind, "W" if r.kind == "nwog" else "D",
                        r.high, r.low, r.ce, k))
    arrs.sort(key=lambda a: a.known)
    piv_h, piv_l = L.pivots(h, l, 1)

    # overnight (reopen to 09:29) of each trading day
    lab = pd.to_datetime((df.index + pd.Timedelta(hours=7)).date)
    tmin = df.index.hour * 60 + df.index.minute
    bm = bar_minutes(df)
    keep = ((tmin < 17 * 60) & (tmin + bm <= cut_min)) | (tmin >= 17 * 60)
    pre = df[keep]
    plab = lab[keep]
    g = pre.groupby(plab)
    on = pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "last": g.close.last()})

    rows = []
    for k in range(5, D):
        day = d.index[k]
        if day not in on.index:
            continue
        px = float(on.at[day, "last"])
        oh, ol = float(on.at[day, "high"]), float(on.at[day, "low"])
        lo_k = max(0, k - lookback)
        live = [a for a in arrs if lo_k <= a.known - 1 and a.known <= k and a.typ != "nwog"]
        live += [a for a in arrs if a.typ == "nwog" and k - lookback <= a.known <= k]   # 60 days (051)
        # NDOGs live through the week they form in (Mon-Fri)
        wk = day.to_period("W-FRI")
        live = [a for a in live if a.typ != "ndog" or d.index[a.known].to_period("W-FRI") == wk]
        react = 0.0
        draws_up, draws_dn = [], []
        for a in live:
            s = a.known
            cl, hi_after, lo_after = c[s:k], h[s:k], l[s:k]
            lo_after = np.append(lo_after, ol); hi_after = np.append(hi_after, oh)
            gap = a.typ in ("ndog", "nwog")              # gaps are never retired by a fill (039)
            if a.typ == "vi" and vi_body_death:          # A9: a later own-TF body spans it
                if a.tf == "D":
                    ob_, cb_ = o[s:k], c[s:k]
                else:                                    # weekly bodies completed before day k
                    done_w = [j for j in range(len(wl)) if a.known < wl[j] <= k]   # later weeks only
                    ob_, cb_ = wo[done_w], wc[done_w]
                if len(cb_) and ((np.minimum(ob_, cb_) <= a.bottom) & (np.maximum(ob_, cb_) >= a.top)).any():
                    continue
            elif a.kind == "bull" and not gap:
                lvl = a.ce if a.typ == "ob" else a.bottom
                if len(cl) and cl.min() < lvl:
                    continue                                   # closed through: invalid
            elif not gap:
                lvl = a.ce if a.typ == "ob" else a.top
                if len(cl) and cl.max() > lvl:
                    continue
            wt = 2.0 if a.tf == "W" else 1.0
            # reaction in the last react_days completed days or tonight
            rl = np.append(l[max(s, k - react_days):k], ol)
            rh = np.append(h[max(s, k - react_days):k], oh)
            if a.kind == "bull" and rl.min() <= a.top and px > a.ce:
                react += wt
            if a.kind == "bear" and rh.max() >= a.bottom and px < a.ce:
                react -= wt
            # draw: the unrebalanced part of the inefficiency (FVGs and gaps only)
            if a.typ in ("fvg", "ndog", "nwog", "vi"):
                if a.kind == "bull":
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
        hh = np.append(h[:k], oh); ll = np.append(l[:k], ol)
        up_sw = [p for p in piv_h if p.known < k and p.i >= lo_k and hh[p.i + 1:].max() < p.price]
        dn_sw = [p for p in piv_l if p.known < k and p.i >= lo_k and ll[p.i + 1:].min() > p.price]
        for p in up_sw:
            draws_up.append((p.price - px, "D_swing_high", p.price))
        for p in dn_sw:
            draws_dn.append((px - p.price, "D_swing_low", p.price))
        if h[k - 1] > max(px, oh):
            draws_up.append((h[k - 1] - px, "PDH", h[k - 1]))
        if l[k - 1] < min(px, ol):
            draws_dn.append((px - l[k - 1], "PDL", l[k - 1]))
        pw = [t for t in w.index if w.at[t, "last"] < day][-1:] if len(w) else []
        if pw:
            pwh, pwl = float(w.at[pw[0], "high"]), float(w.at[pw[0], "low"])
            if pwh > max(px, oh):
                draws_up.append((pwh - px, "PWH", pwh))
            if pwl < min(px, ol):
                draws_dn.append((px - pwl, "PWL", pwl))
        up = min(draws_up) if draws_up else None
        dn = min(draws_dn) if draws_dn else None
        vu = min((x for x in draws_up if x[1].endswith("_vi")), default=None)   # vi_news_draw
        vd = min((x for x in draws_dn if x[1].endswith("_vi")), default=None)
        if up and dn:
            draw = 1 if up[0] < dn[0] else -1
        else:
            draw = 1 if up else (-1 if dn else 0)
        # premium / discount of the dealing range between the nearest untaken swings
        rh_ = min((p.price for p in up_sw), default=None)
        rl_ = max((p.price for p in dn_sw), default=None)
        pdb = 0
        if rh_ is not None and rl_ is not None and rh_ > rl_:
            pdb = 1 if px < (rh_ + rl_) / 2 else -1
        rb = int(np.sign(react))
        rows.append(dict(date=day.date(), px=px, react=rb, react_score=react, draw=draw, pd=pdb,
                         combo=rb if rb else pdb,
                         draw_up=up[2] if up else np.nan, draw_up_name=up[1] if up else "",
                         draw_dn=dn[2] if dn else np.nan, draw_dn_name=dn[1] if dn else "",
                         vi_up=vu[2] if vu else np.nan, vi_dn=vd[2] if vd else np.nan))
    cols = ["date", "px", "react", "react_score", "draw", "pd", "combo", "draw_up", "draw_up_name",
            "draw_dn", "draw_dn_name"] + (["vi_up", "vi_dn"] if vi else [])
    out = pd.DataFrame(rows, columns=cols).set_index("date")
    if flip_triggers and len(out):
        fl = _flip(d, w, arrs, flip_triggers)
        out["flip"] = [fl.get(pd.Timestamp(x), 0) for x in out.index]
    return out


FLIP_TRIGGERS = ("ob_mt", "wk_dc", "flip_pd3", "flip_close_above", "flip_thu_wopen")


def _flip(d: pd.DataFrame, w: pd.DataFrame, arrs: list, triggers: tuple) -> dict:
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
    for k in range(len(d)):
        out[d.index[k]] = state                     # known before session k
        prev = state
        if "ob_mt" in triggers and k >= 1:
            bull = [a for a in obs if a.kind == "bull" and a.known <= k]
            bear = [a for a in obs if a.kind == "bear" and a.known <= k]
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
        if "wk_dc" in triggers and k in wk_last:
            r = wk_last[k]
            if last_dn_week is not None and r.close > last_dn_week:
                state = 1
            elif last_up_week is not None and r.close < last_up_week:
                state = -1
            if r.close < r.open:
                last_dn_week = r.high
            elif r.close > r.open:
                last_up_week = r.low
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


def opening_gaps(df: pd.DataFrame, es_pt: float = 1.0, ndog_min_pts: float = 1.0) -> pd.DataFrame:
    """ICT's opening gaps from bars that include the evening reopen (videos 039, 051, 052):
      NWOG  Friday's last price before the weekend close -> Sunday's first price at the 18:00
            reopen. Levels: high, low, CE. No minimum size; never retired by a fill.
      NDOG  a weekday's last price before the 17:00 close -> the 18:00 reopen (Mon-Thu
            evenings). Only gaps > ~1 ES handle count; they live through the end of that week.
    One row per gap: kind, high, low, ce, known (the reopen time), week (W-FRI period of the
    trading day the reopen starts)."""
    t = df.index
    gap = t.to_series().diff() > pd.Timedelta(minutes=45)
    m = t.hour * 60 + t.minute
    reopen = gap.values & (m >= 17 * 60) & (m < 19 * 60)     # evening reopen after the break
    rows = []
    for k in np.flatnonzero(reopen):
        if k == 0:
            continue
        a, b = float(df.close.iloc[k - 1]), float(df.open.iloc[k])
        weekend = (t[k] - t[k - 1]) > pd.Timedelta(hours=30)
        if not weekend and abs(b - a) <= ndog_min_pts * es_pt:
            continue
        pm = t[k - 1].hour * 60 + t[k - 1].minute
        if not weekend and not (960 <= pm < 1020):
            continue                                  # holiday early close: not a 17:00 close
        day = (t[k] + pd.Timedelta(hours=7)).normalize().tz_localize(None)
        rows.append(dict(kind="nwog" if weekend else "ndog", high=max(a, b), low=min(a, b),
                         ce=(a + b) / 2, up=b > a, known=t[k], week=day.to_period("W-FRI")))
    return pd.DataFrame(rows)


def gaps_for_day(g: pd.DataFrame, day, nwog_keep: int = 5, nwog_days: int = 0, skip_holiday: bool = False,
                 trading_days: bool = False) -> list[tuple[str, float, float, float]]:
    """Gaps in force at 09:30 of `day`: NWOGs (the last `nwog_keep`, or with `nwog_days` > 0
    every NWOG from the last that many trading days - ICT's 60-day maximum, 051 ~18:02,
    "60 market days", 065) and this week's NDOGs. Returns (kind, high, low, ce).
    levels_detectors L5: `trading_days` counts nwog_days in real trading days (calendar module)
    instead of the old calendar estimate; `skip_holiday` (046 ~16:01; 048 ~2:54) drops the NWOG
    of a holiday-shortened week (fewer than 5 trading days) - the nearest normal ones remain."""
    if g is None or not len(g):
        return []
    cut = pd.Timestamp(day, tz=NY_TZ) + pd.Timedelta(hours=9, minutes=30)
    k = g[g.known < cut]
    wk = pd.Timestamp(day).to_period("W-FRI")
    nw = k[k.kind == "nwog"]
    if skip_holiday and len(nw):
        from .calendar import is_trading_day
        full = [sum(is_trading_day((w.start_time + pd.Timedelta(days=j)).date()) for j in range(7)) >= 5
                for w in nw.week]
        nw = nw[np.asarray(full, bool)]
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
    nd = k[(k.kind == "ndog") & (k.week == wk)]
    return [(r.kind, r.high, r.low, r.ce) for r in pd.concat([nw, nd]).itertuples()]


NY_TZ = "America/New_York"
