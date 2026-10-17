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


def _arrays(o, h, l, c, tf: str, known_of) -> list[Arr]:
    out = []
    for z in L.fvgs(h, l):
        out.append(Arr(z.kind, "fvg", tf, z.top, z.bottom, z.mid, known_of(z.i)))
        # order block: last opposite-close candle before the displacement candle
        kind = "bull" if z.kind == "bull" else "bear"
        ob = L.order_block(o, h, l, c, z.i - 4, z.i - 2, kind)
        if ob is not None:
            k = ob.src
            disp = c[z.i - 1]
            if (kind == "bull" and disp > h[k]) or (kind == "bear" and disp < l[k]):
                out.append(Arr(kind, "ob", tf, h[k], l[k], (o[k] + c[k]) / 2, known_of(z.i)))
    return out


def table(df: pd.DataFrame, es_pt: float = 1.0, react_days: int = 2, lookback: int = 60,
          min_gap_pts: float = 1.0) -> pd.DataFrame:
    """One row per trading day: react / draw / pd / combo bias and the draw levels."""
    d = sessions(df)
    D = len(d)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    arrs = _arrays(o, h, l, c, "D", lambda i: i + 1)
    # weekly arrays become usable the day after the week's last session
    w = weeks(d)
    pos = {t: k for k, t in enumerate(d.index)}
    wl = [pos[t] + 1 for t in w["last"]]
    arrs += _arrays(*(w[k].values.astype(float) for k in ("open", "high", "low", "close")), "W",
                    lambda i: wl[i])
    # opening gaps: prior session close -> this session's first print
    for k in range(1, D):
        a, b = c[k - 1], o[k]
        if abs(b - a) < min_gap_pts * es_pt:
            continue
        weekend = (d.index[k] - d.index[k - 1]).days >= 3 or d.index[k].weekday() < d.index[k - 1].weekday()
        typ = "nwog" if weekend else "ndog"
        kind = "bull" if b > a else "bear"
        arrs.append(Arr(kind, typ, "W" if weekend else "D", max(a, b), min(a, b), (a + b) / 2, k))
    arrs.sort(key=lambda a: a.known)
    piv_h, piv_l = L.pivots(h, l, 1)

    # overnight (reopen to 09:29) of each trading day
    lab = pd.to_datetime((df.index + pd.Timedelta(hours=7)).date)
    tmin = df.index.hour * 60 + df.index.minute
    pre = df[(tmin < 570) | (tmin >= 17 * 60)]
    plab = lab[(tmin < 570) | (tmin >= 17 * 60)]
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
        live = [a for a in arrs if lo_k <= a.known - 1 and a.known <= k]
        if any(a.typ == "nwog" for a in live):         # keep the last 5 weekly gaps only
            nw = [a for a in live if a.typ == "nwog"][-5:]
            live = [a for a in live if a.typ != "nwog"] + nw
        # NDOGs live through the week they form in (Mon-Fri)
        wk = day.to_period("W-FRI")
        live = [a for a in live if a.typ != "ndog" or d.index[a.known].to_period("W-FRI") == wk]
        react = 0.0
        draws_up, draws_dn = [], []
        for a in live:
            s = a.known
            cl, hi_after, lo_after = c[s:k], h[s:k], l[s:k]
            lo_after = np.append(lo_after, ol); hi_after = np.append(hi_after, oh)
            if a.kind == "bull":
                lvl = a.ce if a.typ == "ob" else a.bottom
                if len(cl) and cl.min() < lvl:
                    continue                                   # closed through: invalid
            else:
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
            if a.typ in ("fvg", "ndog", "nwog"):
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
                         draw_dn=dn[2] if dn else np.nan, draw_dn_name=dn[1] if dn else ""))
    return pd.DataFrame(rows).set_index("date")


def has_overnight(df: pd.DataFrame) -> bool:
    t = df.index.hour
    return bool(((t >= 18) | (t < 4)).mean() > 0.1)
