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


def _zones(o, h, l, c, end_times, gaps=None, max_bars=None, vi=False, breakers=False, c2_dir=False,
           vi_min_gap=0.0, vi_body_death=False, vi_wick_overlap=True, vi_multi=False, vi_dead_rule="full_span", void_rt=False):
    """Arrays as columns: kind (+1 bull / -1 bear), top, bottom, inv (invalidation level),
    known (time the array can first be used), src (SRC code: FVG 0, OB 1, opening gap 2,
    volume imbalance 3, breaker 4), plus the bar index the invalidation scan starts from.
    `vi` adds volume imbalances (shared VI wiring; dies on a close beyond the far edge like an
    FVG); `breakers` adds breaker zones with inv = the breaker MT (owner #6, conf_breakers).
    levels_detectors: `c2_dir` (A5) keeps FVGs whose middle candle closes their way; `vi_min_gap`
    (A9) drops narrow VIs; `vi_body_death` (A9 / Ep03.3) kills a VI when a later body of its
    timeframe spans it (instead of a close beyond its far edge); caption-gap A9: `vi_wick_overlap` / `vi_multi` (the VI
    definition) and `vi_dead_rule` ("full_span" / "overlap": which body kills a VI).
    Caption-gap A12-void-up-down-ob (cc02_007 ~13:33; `void_rt`, 4h and higher only - the caller decides): a one-sided rally followed at once by a
    one-sided drop through the same range is ONE order block (levels.void_round_trip_obs), invalidated like any OB at its MT."""
    rows = []
    vi_dead = {}
    for z in L.fvgs(h, l, o, c, c2_dir):
        s = 1 if z.kind == "bull" else -1
        rows.append((s, z.top, z.bottom, z.bottom if s > 0 else z.top, z.i, 0))
        ob = L.order_block_blend(o, h, l, c, z.i - 4, z.i - 2, z.kind)
        if ob is not None:
            disp = c[z.i - 1]
            if (s > 0 and disp > ob.top) or (s < 0 and disp < ob.bottom):
                rows.append((s, ob.top, ob.bottom, ob.mt, z.i, 1))
    if void_rt:
        for z in L.void_round_trip_obs(o, h, l, c):
            rows.append((1 if z.kind == "bull" else -1, z.top, z.bottom, z.mt, z.i, 1))
    if vi:
        for z in L.volume_imbalances(o, h, l, c, vi_min_gap, vi_wick_overlap, vi_multi):
            s = 1 if z.kind == "bull" else -1
            if vi_body_death:
                vi_dead[len(rows)] = L.vi_body_dead(o, c, z, end=None if max_bars is None else z.i + max_bars,
                                                    rule=vi_dead_rule)
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
        if j in vi_dead:                                  # A9 body death rule
            if vi_dead[j] is not None:
                dead[j] = end_times[vi_dead[j]]
            continue
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
                 breakers: bool = False, c2_dir: bool = False, vi_min_gap: float = 0.0,
                 vi_body_death: bool = False, vi_wick_overlap: bool = True, vi_multi: bool = False,
                 vi_dead_rule: str = "full_span", ipda_first20: bool = False, nwog_cfd_src: str = "auto",
                 void_rt_ob: bool = False, tf_lookback: dict | None = None):
        # caption-gap new-lookback-per-tf-topdown: tf_lookback {tf: trading days} replaces the array LIFE of that timeframe (calendar days = x 7 / 5)
        life = dict(LIFE)
        for k_, n_ in (tf_lookback or {}).items():
            if k_ in life:
                life[k_] = f"{max(1, round(int(n_) * 7 / 5))}D"
        zk = dict(c2_dir=c2_dir, vi_min_gap=vi_min_gap, vi_body_death=vi_body_death, vi_wick_overlap=vi_wick_overlap,
                  vi_multi=vi_multi, vi_dead_rule=vi_dead_rule)
        self.first20 = ipda_first20            # caption-gap B21: only the freshest IPDA window of daily arrays (see _ipda_mask)
        self.dends = np.array([])
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
            life_bars = int(pd.Timedelta(life[tf]).total_seconds() // 60 // m)
            z = _zones(*(b[k].values.astype(float) for k in ("open", "high", "low", "close")),
                       end.astype(float), max_bars=life_bars, vi=vi, breakers=breakers,
                       void_rt=void_rt_ob and m >= 240, **zk)
            self.st[tf] = (end.astype(float), _structure(b.high.values, b.low.values, b.close.values))
            if z:
                z["life"] = pd.Timedelta(life[tf]).value
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
        self.dends = np.sort(dend)
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
                       np.asarray(ends, float), vi=vi, breakers=breakers, void_rt=void_rt_ob, **zk)
            self.st[tf] = (np.asarray(ends, float), _structure(b.high.values, b.low.values, b.close.values))
            if z:
                z["life"] = np.full(len(z["kind"]), float(pd.Timedelta(life[tf]).value))
                self.z[tf] = z
        # opening gaps as ICT defines them (htf.opening_gaps): NDOGs count on the daily
        # timeframe through the end of their week; NWOGs on the weekly for 60 trading days.
        # Neither is retired by a fill.
        og = htf.opening_gaps(df, es_pt, 1.0, nwog_cfd_src)
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

    def windowed(self, since: dict):
        """A cheap copy of this object (the array tables are shared) whose queries keep only the FVG / OB / VI / breaker arrays of the timeframes in
        `since` ({tf: ns}) that were KNOWN at or after that time - the B21 `ipda_arrays` window (caption-gap levels_detectors #3/3 review: every
        merge of the engine - the main scan, the Silver Bullet, entries.py, targets.htf_levels - reads the same limited arrays). Opening gaps
        are never limited."""
        import copy
        c = copy.copy(self)
        c.window = dict(since)
        return c

    window = None

    def _ipda_mask(self, tf: str, z: dict, now: float) -> np.ndarray:
        """Caption-gap B21 (cc05_001 ~22:58; cc07_005 ~14:17: "for day trading you're going to operate in those last 20 days"): with
        ipda_arrays_first20 the DAILY FVG / OB / VI rows are limited to the 20 sessions after they formed until every one of
        them is traded through (dead), then 40, then 60 sessions - the age counts closed trading sessions since `known` (Sunday
        sessions are not in htf.sessions). Other timeframes and the opening gaps are untouched.
        With `windowed` (ipda_arrays) the arrays of a listed timeframe must also have been known at or after the window start."""
        n = len(z["kind"])
        ok = np.ones(n, bool)
        w = self.window
        if w and tf in w:
            ok = ~(np.isin(z["src"], [0, 1, 3, 4]) & (z["known"] < w[tf]))
        if not getattr(self, "first20", False) or tf != "D" or not len(getattr(self, "dends", ())):
            return ok
        sel = np.isin(z["src"], [0, 1, 3])
        age = np.searchsorted(self.dends, now, side="right") - np.searchsorted(self.dends, z["known"], side="right") + 1
        alive = sel & (z["known"] <= now) & (z["dead"] > now)
        win = 60
        for w_ in (20, 40, 60):
            if (alive & (age <= w_)).any():
                win = w_
                break
        return ok & (~sel | (age <= win))

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
            m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
            if m.any():
                out.append(tf)
        return out


def _targets_impl(self, t: pd.Timestamp, beyond: float, side: int, tfs, far_edge: bool = False, min_known: dict | None = None) -> list[float]:
    """Opposing PD arrays (FVGs, order blocks, opening gaps) still valid at time t on the
    given timeframes, beyond `beyond` in the trade's direction: their near edge and CE.
    For a long (side +1): bearish arrays above; for a short: bullish arrays below.
    Caption-gap B21 ipda_arrays (levels_detectors #3/3): `min_known` {tf: ns} keeps only the arrays of that timeframe known at or after the time."""
    now = float(t.value)
    out = []
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == -side) & (z["known"] <= now) & (z["dead"] > now)
             & (now - z["known"] <= z["life"]))
        m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
        if min_known and tf in min_known:
            m &= z["known"] >= min_known[tf]
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
        m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
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
    m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
    m &= (z["bottom"] <= price) if side > 0 else (z["top"] >= price)
    if not m.any():
        return None
    key = z["top"][m] if side > 0 else -z["bottom"][m]       # nearest behind the price
    k = int(np.argmax(key))
    return float(z["top"][m][k]), float(z["bottom"][m][k]), float(z["dead"][m][k])


Confluence.support = _support_impl


def _valid_impl(self, t: pd.Timestamp, side: int, tfs, src=(0, 1, 3), known_by: pd.Timestamp | None = None):
    """Every same-side array (side +1: bullish) valid at time t on `tfs` with a source in `src`,
    complete by `known_by` (default t): [(top, bottom, tf, src, known_ns)], real prices. Used by
    the turtle-soup variants (M12.1 / M12.3 / M12.4) to find the PD array at a sweep."""
    now = float(t.value)
    kb = now if known_by is None else float(known_by.value)
    out = []
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == side) & (z["known"] <= kb) & (z["dead"] > now)
             & (now - z["known"] <= z["life"]) & np.isin(z["src"], list(src)))
        m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
        for k in np.flatnonzero(m):
            out.append((float(z["top"][k]), float(z["bottom"][k]), tf, int(z["src"][k]), float(z["known"][k])))
    return out


Confluence.valid = _valid_impl


def _opposing_impl(self, t: pd.Timestamp, beyond: float, side: int, tfs, src=(0,), keep_dead: bool = False):
    """levels_detectors (A5 htf_ce_draw / fvg_keep_filled, A9 vi_htf_draw, Ep08.1 daily_fvg_exact):
    opposing arrays on `tfs` with a source in `src`, wholly beyond `beyond` in the trade's direction
    (long: bearish arrays with bottom > beyond), valid at t. keep_dead=True (A5 "reuse after
    fills", 015 / 051) ignores the invalidation close but keeps the life limit (D ~60 sessions).
    Returns [(near, ce, far, tf, src)], real prices, nearest first."""
    now = float(t.value)
    out = []
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == -side) & (z["known"] <= now) & (now - z["known"] <= z["life"])
             & np.isin(z["src"], list(src)))
        m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
        if not keep_dead:
            m &= z["dead"] > now
        m &= (z["bottom"] > beyond) if side > 0 else (z["top"] < beyond)
        for k in np.flatnonzero(m):
            top, bot = float(z["top"][k]), float(z["bottom"][k])
            near, far = (bot, top) if side > 0 else (top, bot)
            out.append((near, (top + bot) / 2, far, tf, int(z["src"][k])))
    out.sort(key=lambda r: r[0] * side)
    return out


Confluence.opposing = _opposing_impl


def _opposing_ext_impl(self, t: pd.Timestamp, beyond: float, side: int, tfs, src=(0,), straddle: bool = False):
    """targets_partials (L9 / A22 / L14d): like `opposing`, but every row keeps its identity - a dict
    (top, bottom, tf, src, known_ns, dead_ns) in real prices - so the caller can test overlaps
    (fvg_over_ob), how far price has traded into the array since it formed (skip_exhausted, hygiene)
    and the unvisited remainder (fvg_remainder). Valid at t (known <= t, not dead, within life).
    Long: bearish arrays with bottom > beyond (straddle=True: top > beyond). Nearest first."""
    now = float(t.value)
    out = []
    for tf in tfs:
        z = self.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == -side) & (z["known"] <= now) & (z["dead"] > now) & (now - z["known"] <= z["life"])
             & np.isin(z["src"], list(src)))
        m &= self._ipda_mask(tf, z, now)      # caption-gap B21 ipda_arrays_first20
        if side > 0:
            m &= (z["top"] > beyond) if straddle else (z["bottom"] > beyond)
        else:
            m &= (z["bottom"] < beyond) if straddle else (z["top"] < beyond)
        for k in np.flatnonzero(m):
            out.append(dict(top=float(z["top"][k]), bottom=float(z["bottom"][k]), tf=tf, src=int(z["src"][k]),
                            known=float(z["known"][k]), dead=float(z["dead"][k])))
    out.sort(key=lambda r: (r["bottom"] if side > 0 else -r["top"]))
    return out


Confluence.opposing_ext = _opposing_ext_impl


def score(tfs: list[str]) -> tuple[int, int]:
    """(number of aligned timeframes, index of the highest one in TFS; -1 if none)."""
    return len(tfs), max((TFS.index(t) for t in tfs), default=-1)
