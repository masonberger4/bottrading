"""Multi-timeframe PD-array confluence (Mase, 2026-10-17): conviction rises with the number
of timeframes whose PD arrays line up at a price, and with how high those timeframes are.
PD arrays are fractal, so the same detectors run on every timeframe from 1m to monthly.

Arrays per timeframe (bullish shown; bearish mirrors):
  FVG   3-candle gap; valid until a close below its bottom.
  OB    last down-close candle (within 3 bars) before the displacement candle of a bullish
        FVG, if that candle closed above the OB's high; valid until a close below its mean
        threshold (body midpoint).
  gap   daily: 16:14 close -> 18:00 reopen (NDOG); weekly: Friday close -> Sunday reopen
        (NWOG); valid until a close below the gap's bottom. (Daily and weekly only.)
Each array is usable from the close of the bar that completes it and for a limited life
(LIFE). "Aligned at price P" = P within the array (plus a small tolerance).

Intraday bars are clock-aligned (4h from midnight). Daily bars are futures-style sessions
(evening reopen to the afternoon close, see htf.sessions); weekly and monthly come from
those sessions. A daily/weekly/monthly array is known after its last session closes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import htf
from . import levels as L

TFS = ("1m", "5m", "15m", "30m", "1h", "4h", "D", "W", "M")
MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}
LIFE = {"1m": "1D", "5m": "2D", "15m": "5D", "30m": "10D", "1h": "20D", "4h": "60D",
        "D": "365D", "W": "1100D", "M": "3700D"}


def _zones(o, h, l, c, end_times, gaps=None, max_bars=None):
    """Arrays as columns: kind (+1 bull / -1 bear), top, bottom, inv (invalidation level),
    known (time the array can first be used), plus the bar index the invalidation scan
    starts from."""
    rows = []
    for z in L.fvgs(h, l):
        s = 1 if z.kind == "bull" else -1
        rows.append((s, z.top, z.bottom, z.bottom if s > 0 else z.top, z.i))
        ob = L.order_block(o, h, l, c, z.i - 4, z.i - 2, z.kind)
        if ob is not None:
            k = ob.src
            disp = c[z.i - 1]
            if (s > 0 and disp > h[k]) or (s < 0 and disp < l[k]):
                rows.append((s, h[k], l[k], (o[k] + c[k]) / 2, z.i))
    for s, top, bottom, k in gaps or ():
        rows.append((s, top, bottom, bottom if s > 0 else top, k))
    if not rows:
        return None
    a = np.array(rows, dtype=float)
    kind, top, bottom, inv, i = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4].astype(int)
    # first later close beyond the invalidation level
    dead = np.full(len(a), np.inf)
    n = len(c)
    for j in range(len(a)):
        seg = c[i[j] + 1:] if max_bars is None else c[i[j] + 1:i[j] + 1 + max_bars]
        if not len(seg):
            continue
        hit = np.flatnonzero(seg < inv[j]) if kind[j] > 0 else np.flatnonzero(seg > inv[j])
        if len(hit):
            dead[j] = end_times[i[j] + 1 + hit[0]]
    known = end_times[i]
    return dict(kind=kind, top=top, bottom=bottom, known=known, dead=dead)


class Confluence:
    def __init__(self, df: pd.DataFrame, base_minutes: int, es_pt: float = 1.0):
        self.tol = 0.25 * es_pt
        self.z = {}
        for tf, m in MINUTES.items():
            if m < base_minutes:
                continue
            if m == base_minutes:
                b = df
            else:
                g = df.groupby(df.index.floor(f"{m}min"))
                b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                                  "close": g.close.last()})
            end = (b.index + pd.Timedelta(minutes=m)).as_unit("ns").asi8
            life_bars = int(pd.Timedelta(LIFE[tf]).total_seconds() // 60 // m)
            z = _zones(*(b[k].values.astype(float) for k in ("open", "high", "low", "close")),
                       end.astype(float), max_bars=life_bars)
            if z:
                z["life"] = pd.Timedelta(LIFE[tf]).value
                self.z[tf] = z
        d = htf.sessions(df)
        # a session's end time: its last bar's close
        lab = (df.index + pd.Timedelta(hours=7)).normalize().tz_localize(None)
        last = pd.Series(df.index, index=df.index).groupby(lab).max()
        dend = pd.DatetimeIndex(last.reindex(d.index) + pd.Timedelta(minutes=base_minutes)).as_unit("ns").asi8.astype(float)
        gaps = []
        for k in range(1, len(d)):
            a, b = d.close.iloc[k - 1], d.open.iloc[k]
            if abs(b - a) >= 1.0 * es_pt:
                gaps.append((1 if b > a else -1, max(a, b), min(a, b), k - 1))  # known at prior close... see below
        # a gap is known at the reopen, i.e. before session k closes: use session k-1's end
        for tf, per in (("D", None), ("W", "W-FRI"), ("M", "M")):
            if per is None:
                b, ends, gp = d, dend, gaps
            else:
                grp = d.index.to_period(per)
                g = d.groupby(grp)
                b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                                  "close": g.close.last()})
                ends = pd.Series(dend, index=d.index).groupby(grp).max().values
                gp = None
                if tf == "W":                         # NWOGs: the gap opening each week
                    first = pd.Series(np.arange(len(d)), index=d.index).groupby(grp).min().values
                    gp = []
                    wk_of = {f: w for w, f in enumerate(first)}
                    for s, top, bottom, k in gaps:
                        w = wk_of.get(k + 1)
                        if w is not None and w > 0:
                            gp.append((s, top, bottom, w - 1))
            z = _zones(*(b[k].values.astype(float) for k in ("open", "high", "low", "close")),
                       np.asarray(ends, float), gp)
            if z:
                z["life"] = pd.Timedelta(LIFE[tf]).value
                self.z[tf] = z

    def at(self, t: pd.Timestamp, price: float, side: int, known_by: pd.Timestamp | None = None) -> list[str]:
        """Timeframes with a valid array of the trade's side containing `price` at time t,
        counting only arrays already complete by `known_by` (default t)."""
        now = float(t.value)
        kb = now if known_by is None else float(known_by.value)
        out = []
        for tf in TFS:
            z = self.z.get(tf)
            if z is None:
                continue
            m = ((z["kind"] == side) & (z["known"] <= kb) & (z["dead"] > now)
                 & (now - z["known"] <= z["life"])
                 & (z["bottom"] - self.tol <= price) & (price <= z["top"] + self.tol))
            if m.any():
                out.append(tf)
        return out


def score(tfs: list[str]) -> tuple[int, int]:
    """(number of aligned timeframes, index of the highest one in TFS; -1 if none)."""
    return len(tfs), max((TFS.index(t) for t in tfs), default=-1)
