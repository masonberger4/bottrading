"""Multi-timeframe PD-array confluence (Mase, 2026-10-17): conviction rises with the number
of timeframes whose PD arrays line up at a price, and with how high those timeframes are.
PD arrays are fractal, so the same detectors run on every timeframe from 1m to monthly.

Arrays per timeframe (bullish shown; bearish mirrors):
  FVG   3-candle gap; valid until a close below its bottom.
  OB    the last down-close candle(s), blended (levels.order_block_blend), within 3 bars
        before the displacement candle of a bullish FVG, if that candle closed above the
        block's high; valid until a close below its body mean threshold.
  gap   ICT's opening gaps (htf.opening_gaps): NDOG (17:00 close -> 18:00 reopen, Mon-Thu,
        > 1 handle) on the daily timeframe through the end of its week; NWOG (Friday close ->
        Sunday 18:00) on the weekly for 60 trading days. Gaps are never retired by a fill.
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

NY = "America/New_York"

TFS = ("1m", "5m", "15m", "30m", "1h", "4h", "D", "W", "M")
MINUTES = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}
LIFE = {"1m": "1D", "5m": "2D", "15m": "5D", "30m": "10D", "1h": "20D", "4h": "60D",
        "D": "90D", "W": "1100D", "M": "3700D"}   # D: ~60 trading days, as htf.py


def _structure(h, l, c) -> np.ndarray:
    """Market-structure state after each bar: +1 once a close is above the most recent
    confirmed swing high (3-candle pivot), -1 once a close is below the most recent swing low;
    the state holds until the opposite break."""
    ph, pl = L.pivots(h, l, 1)
    st = np.zeros(len(c))
    hi = lo = None
    a = b = 0
    s = 0
    for k in range(len(c)):
        while a < len(ph) and ph[a].known <= k:
            hi = ph[a].price; a += 1
        while b < len(pl) and pl[b].known <= k:
            lo = pl[b].price; b += 1
        if hi is not None and c[k] > hi:
            s = 1
        elif lo is not None and c[k] < lo:
            s = -1
        st[k] = s
    return st


SRC = {"fvg": 0, "ob": 1, "gap": 2, "vi": 3, "breaker": 4}   # array source codes (column `src`)


def _zones(o, h, l, c, end_times, gaps=None, max_bars=None, vi=False, breakers=False):
    """Arrays as columns: kind (+1 bull / -1 bear), top, bottom, inv (invalidation level),
    known (time the array can first be used), src (SRC code: FVG 0, OB 1, opening gap 2,
    volume imbalance 3, breaker 4), plus the bar index the invalidation scan starts from.
    `vi` adds volume imbalances (shared VI wiring; dies on a close beyond the far edge like an
    FVG); `breakers` adds breaker zones with inv = the breaker MT (owner #6, conf_breakers)."""
    rows = []
    for z in L.fvgs(h, l):
        s = 1 if z.kind == "bull" else -1
        rows.append((s, z.top, z.bottom, z.bottom if s > 0 else z.top, z.i, 0))
        ob = L.order_block_blend(o, h, l, c, z.i - 4, z.i - 2, z.kind)
        if ob is not None:
            disp = c[z.i - 1]
            if (s > 0 and disp > ob.top) or (s < 0 and disp < ob.bottom):
                rows.append((s, ob.top, ob.bottom, ob.mt, z.i, 1))
    if vi:
        for z in L.volume_imbalances(o, h, l, c):
            s = 1 if z.kind == "bull" else -1
            rows.append((s, z.top, z.bottom, z.bottom if s > 0 else z.top, z.i, 3))
    if breakers:
        for z in L.breakers(o, h, l, c, 1):
            s = 1 if z.kind == "bull" else -1
            rows.append((s, z.top, z.bottom, z.mt, z.i, 4))
    for s, top, bottom, k in gaps or ():
        rows.append((s, top, bottom, bottom if s > 0 else top, k, 2))
    if not rows:
        return None
    a = np.array(rows, dtype=float)
    kind, top, bottom, inv, i, src = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4].astype(int), a[:, 5]
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
    return dict(kind=kind, top=top, bottom=bottom, known=known, dead=dead, src=src)


class Confluence:
    def __init__(self, df: pd.DataFrame, base_minutes: int, es_pt: float = 1.0, vi: bool = False,
                 breakers: bool = False):
        self.tol = 0.25 * es_pt
        self.z = {}
        self.st = {}                   # tf -> (bar end times, structure state)
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
                       end.astype(float), max_bars=life_bars, vi=vi, breakers=breakers)
            self.st[tf] = (end.astype(float), _structure(b.high.values, b.low.values, b.close.values))
            if z:
                z["life"] = pd.Timedelta(LIFE[tf]).value
                self.z[tf] = z
        d = htf.sessions(df)
        # a session's end time: its last bar's close
        lab = (df.index + pd.Timedelta(hours=7)).normalize().tz_localize(None)
        last = pd.Series(df.index, index=df.index).groupby(lab).max()
        dend = pd.DatetimeIndex(last.reindex(d.index) + pd.Timedelta(minutes=base_minutes)).as_unit("ns").asi8.astype(float)
        # never before the session's scheduled 17:00 close, so a session still in progress at the
        # end of the data is not taken as complete
        close17 = pd.DatetimeIndex((d.index + pd.Timedelta(hours=17)).tz_localize(NY)).as_unit("ns").asi8.astype(float)
        dend = np.maximum(dend, close17)
        for tf, per in (("D", None), ("W", "W-FRI"), ("M", "M")):
            if per is None:
                b, ends = d, dend
            else:
                grp = d.index.to_period(per)
                g = d.groupby(grp)
                b = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                                  "close": g.close.last()})
                ends = pd.Series(dend, index=d.index).groupby(grp).max().values
            z = _zones(*(b[k].values.astype(float) for k in ("open", "high", "low", "close")),
                       np.asarray(ends, float), vi=vi, breakers=breakers)
            self.st[tf] = (np.asarray(ends, float), _structure(b.high.values, b.low.values, b.close.values))
            if z:
                z["life"] = np.full(len(z["kind"]), float(pd.Timedelta(LIFE[tf]).value))
                self.z[tf] = z
        # opening gaps as ICT defines them (htf.opening_gaps): NDOGs count on the daily
        # timeframe through the end of their week; NWOGs on the weekly for 60 trading days.
        # Neither is retired by a fill.
        og = htf.opening_gaps(df, es_pt)
        if len(og):
            known = pd.DatetimeIndex(og.known).as_unit("ns").asi8.astype(float)
            nd = (og.kind == "ndog").values
            week_end = pd.DatetimeIndex([(w.end_time + pd.Timedelta(hours=17)).tz_localize(NY)
                                         for w in og.week]).as_unit("ns").asi8.astype(float)
            # NWOGs stay in force for 60 trading days (~86 calendar days; 051 ~18:02, 065)
            nw_dead = known + float(pd.Timedelta(days=86).value)
            for tf, m, dead in (("D", nd, week_end), ("W", ~nd, nw_dead)):
                if not m.any():
                    continue
                add = dict(kind=np.where(og.up.values[m], 1.0, -1.0), top=og.high.values[m],
                           bottom=og.low.values[m], known=known[m], dead=np.asarray(dead)[m],
                           life=np.full(m.sum(), np.inf), src=np.full(m.sum(), 2.0))
                z = self.z.get(tf)
                self.z[tf] = add if z is None else {k: np.concatenate([z[k], add[k]]) for k in add}

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


def _targets_impl(self, t: pd.Timestamp, beyond: float, side: int, tfs, far_edge: bool = False) -> list[float]:
    """Opposing PD arrays (FVGs, order blocks, opening gaps) still valid at time t on the
    given timeframes, beyond `beyond` in the trade's direction: their near edge and CE.
    For a long (side +1): bearish arrays above; for a short: bullish arrays below."""
    now = float(t.value)
    out = []
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == -side) & (z["known"] <= now) & (z["dead"] > now)
             & (now - z["known"] <= z["life"]))
        if side > 0:
            m &= z["bottom"] > beyond
            near = z["bottom"][m]
        else:
            m &= z["top"] < beyond
            near = z["top"][m]
        ce = (z["top"][m] + z["bottom"][m]) / 2
        out += list(near) + list(ce)
        if far_edge:
            out += list(z["top"][m] if side > 0 else z["bottom"][m])
    return out


Confluence.targets = _targets_impl


def _trend_impl(self, t: pd.Timestamp, tf: str) -> int:
    """Structure state of timeframe tf from the last bar closed by time t (0 if unknown)."""
    e = self.st.get(tf)
    if e is None:
        return 0
    k = int(np.searchsorted(e[0], float(t.value), side="right")) - 1
    return int(e[1][k]) if k >= 0 else 0


Confluence.trend = _trend_impl


def _resistance_impl(self, t: pd.Timestamp, price: float, side: int, tfs, src=(0,), straddle: bool = True):
    """Owner directive #7 (Ep 02): the nearest unbroken OPPOSING array in the trade's way.
    Long (side +1): bearish arrays with top > price, still valid at t (known <= t, not dead by
    t, within life), source in `src`; level = max(bottom, price) (a straddling array gives
    level = price); the lowest such level over all rows wins. Short mirrors (bullish arrays
    below, level = min(top, price), highest wins). Real prices. Returns
    (level, tf, top, bottom) or None. straddle=False ignores arrays the price is inside."""
    now = float(t.value)
    best = None
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == -side) & (z["known"] <= now) & (z["dead"] > now)
             & (now - z["known"] <= z["life"]) & np.isin(z["src"], list(src)))
        if side > 0:
            m &= (z["top"] > price) if straddle else (z["bottom"] > price)
            lv = np.maximum(z["bottom"][m], price)
        else:
            m &= (z["bottom"] < price) if straddle else (z["top"] < price)
            lv = np.minimum(z["top"][m], price)
        if not m.any():
            continue
        k = int(np.argmin(lv) if side > 0 else np.argmax(lv))
        cand = (float(lv[k]), tf, float(z["top"][m][k]), float(z["bottom"][m][k]))
        if best is None or (cand[0] < best[0] if side > 0 else cand[0] > best[0]):
            best = cand
    return best


Confluence.resistance = _resistance_impl


def _support_impl(self, t: pd.Timestamp, price: float, side: int, tf: str, src=(0,)):
    """Ep 02 30m "heavy" line (runner_htf_exit): the same-side array on `tf` containing
    `price` or nearest behind it (below for a long), valid at t. Returns (top, bottom, dead)
    with `dead` the time of the first close beyond its far edge (inf while alive), or None."""
    now = float(t.value)
    z = self.z.get(tf)
    if z is None:
        return None
    m = ((z["kind"] == side) & (z["known"] <= now) & (z["dead"] > now)
         & (now - z["known"] <= z["life"]) & np.isin(z["src"], list(src)))
    m &= (z["bottom"] <= price) if side > 0 else (z["top"] >= price)
    if not m.any():
        return None
    key = z["top"][m] if side > 0 else -z["bottom"][m]       # nearest behind the price
    k = int(np.argmax(key))
    return float(z["top"][m][k]), float(z["bottom"][m][k]), float(z["dead"][m][k])


Confluence.support = _support_impl


def score(tfs: list[str]) -> tuple[int, int]:
    """(number of aligned timeframes, index of the highest one in TFS; -1 if none)."""
    return len(tfs), max((TFS.index(t) for t in tfs), default=-1)
