"""ICT's Venom model (2025 Lectures 22, 39, 43, 51, 62; scorecard cards PREMARKET-RANGE E and VENOM-STOP).

Bullish version (the bearish one is the mirror), on 5m candles ("framed with the five-minute candlestick", L39):
  frame   the 08:00-09:30 ET range (`venom_window`): its low is the sell side, its high the buy side (L51).
  context the day is predisposed one way: the AM session lock's side when the engine has one (a neutral lock = no Venom)
          [our interpretation of "needs trend context"; "several large range candles" has no threshold and is not built].
  signal  from 09:30 to `venom_until`: a SIBI (bearish FVG) whose middle candle trades down through the 08:00-09:30 low, at
          least `venom_min_under` candles after it, then a BISI (bullish FVG) whose middle candle closes back above the low
          ("you have to have a SIBI first and then a BISI leaving it or it's not a Venom", L39; "two fangs", L43 / L51).
          Known when the BISI's third candle closes.
  entry   limit at the open of the candle that completes the BISI, placed when it closes, or less (L43 "buying at this
          candlestick's open or less ... a power three type of entry", the limit sent "as soon as this candlestick closes"
          [our interpretation: that candle is the BISI's third]; VENOM-STOP B); venom_entry="close" = the displacement
          (BISI middle) candle's close or less (VENOM-STOP A, L39 "enter below the second candle closing price"). Rests until
          `venom_until` (+ the entry bar) or until the target trades first.
  stop    venom_stop="bpr_ce" (VENOM-STOP B, L43): just below the CE of the SIBI + BISI balanced price range (their overlap,
          else the span between the two gaps' anchors [our interpretation]); "pierce" (A, L39): below the candle that pierces
          back above the low (the BISI candle's low).
  target  the 08:00-09:30 high (the buy side; L39 exits "as it pokes above this high"), less exit_before_pts.
  exit    stop / target bar by bar; flat at `venom_flat` (12:00) [our interpretation: L51 frames the move into 10:00-10:30].
One Venom a day, its own book like the Silver Bullet and the NDOG scalp (no adds, no partials).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .cards_rules import hit

MIN1 = 1e-9
SIGNALS: list = []          # (day, side, entry, stop, target, risk) of every signal that reached the risk check (study / debugging)


def _bars5(ctx, a: int, b: int) -> pd.DataFrame:
    """The day's bars that start in [a, b) minutes, as 5m candles (a candle only once its last base bar is in)."""
    S = ctx.start
    t = np.asarray(ctx.t[S:])
    m = (t >= a) & (t < b)
    if not m.any():
        return pd.DataFrame(columns=["open", "high", "low", "close", "k_last"])
    ix = np.flatnonzero(m) + S
    df = pd.DataFrame({"open": np.asarray(ctx.o)[ix], "high": np.asarray(ctx.h)[ix], "low": np.asarray(ctx.l)[ix],
                       "close": np.asarray(ctx.c)[ix], "k": ix}, index=ctx.idx[ix])
    if ctx.tf >= 5:
        return df.rename(columns={"k": "k_last"})
    g = df.resample("5min", closed="left", label="left")         # (the day has closed: every candle is complete; k_last = the base bar it is known at)
    return g.agg({"open": "first", "high": "max", "low": "min", "close": "last", "k": "max"}).dropna().rename(columns={"k": "k_last"})


def find_signal(c5: pd.DataFrame, lo: float, hi: float, sgn: int, p) -> dict | None:
    """The first Venom on the 5m candles `c5` (09:30 on) for side `sgn` against the 08:00-09:30 low `lo` / high `hi`
    (sgn < 0: the mirror against the high). Returns the signal at the close of the BISI's third candle, or None."""
    o, h, l, c = (c5[x].values.astype(float) * sgn for x in ("open", "high", "low", "close"))
    if sgn < 0:
        h, l = l, h                                                # mirrored: high <-> low
        edge = -hi
    else:
        edge = lo
    n = len(c5)
    sibi = None
    for j in range(2, n):
        if sibi is None:
            # a SIBI: the bearish gap between candle j-2's low and candle j's high, its middle candle j-1 trading down through the low
            if h[j] < l[j - 2] - MIN1 and l[j - 1] < edge - MIN1 and h[j - 1] >= edge - MIN1 and c[j - 1] < o[j - 1]:
                sibi = dict(m=j - 1, top=float(l[j - 2]), bottom=float(h[j]))
            continue
        # a BISI after it: the bullish gap between candle j-2's high and candle j's low, its middle candle j-1 closing back above the low
        if (j - 1) - sibi["m"] - 1 < p.venom_min_under:
            continue
        if l[j] > h[j - 2] + MIN1 and c[j - 1] > edge + MIN1 and l[j - 1] < edge + MIN1 and c[j - 1] > o[j - 1]:
            return dict(sibi=sibi, bisi=dict(m=j - 1, bottom=float(h[j - 2]), top=float(l[j])), k=j,
                        k_open=float(o[j]), b_close=float(c[j - 1]), b_low=float(l[j - 1]), edge=float(edge))
        if c[j] < min(l[sibi["m"]], edge) - MIN1 and l[j] < l[sibi["m"]] - MIN1:
            sibi = None                                            # a new low under the SIBI candle: look for a newer SIBI [our interpretation]
            if h[j] < l[j - 2] - MIN1 and l[j - 1] < edge - MIN1 and c[j - 1] < o[j - 1]:
                sibi = dict(m=j - 1, top=float(l[j - 2]), bottom=float(h[j]))
    return None


def bpr_ce(sig: dict) -> float:
    """The CE of the SIBI + BISI balanced price range (mirrored prices): their overlap when they overlap, else the span between them."""
    s, b = sig["sibi"], sig["bisi"]
    lo_, hi_ = max(s["bottom"], b["bottom"]), min(s["top"], b["top"])
    if hi_ <= lo_:
        lo_, hi_ = min(s["bottom"], b["bottom"]), max(s["top"], b["top"])
    return (lo_ + hi_) / 2


def run_venom(ctx, p, day, symbol: str, btag: dict) -> list:
    """The day's Venom trade (at most one)."""
    from . import strategy as S
    if p.day_filter and S.blocked(day, "AM", p, p.venom_window[1]):
        return []                                                  # (the NFP / FOMC / CPI day rules block the AM Venom too)
    a, b = p.venom_window
    w = _bars5(ctx, a, b)
    if not len(w):
        return []
    lo, hi = float(w.low.min()), float(w.high.max())
    if hi - lo < 2 * p.es_pt:
        return []
    c5 = _bars5(ctx, b, p.venom_until)
    if len(c5) < 5:
        return []
    hit("venom_eval")
    best = None
    for sgn in (1, -1):
        sig = find_signal(c5, lo, hi, sgn, p)
        if sig is not None and (best is None or sig["k"] < best[1]["k"]):
            best = (sgn, sig)
    if best is None:
        return []
    sgn, sig = best
    k_sig = int(c5.k_last.iloc[sig["k"]])                          # the base bar the signal is known at (its close)
    from .sb_model import _lock_at
    lock = _lock_at(ctx, "AM", k_sig)
    if lock is not None and lock.get("side", 0) != sgn:
        hit("venom_x_lock")
        return []
    hit("venom_signal")
    x = lambda v: v * sgn                                          # mirrored <-> real price
    entry_m = sig["k_open"] if p.venom_entry == "open" else sig["b_close"]
    stop_m = (bpr_ce(sig) if p.venom_stop == "bpr_ce" else sig["b_low"]) - p.pad
    tgt_m = (hi if sgn > 0 else -lo) - p.exit_before_pts * p.es_pt
    risk = entry_m - stop_m
    SIGNALS.append((day, sgn, x(entry_m), x(stop_m), x(tgt_m), round(risk, 2)))
    if risk < p.min_risk_pts * p.es_pt or risk > p.max_risk_pts * p.es_pt or tgt_m - entry_m < p.min_rr * risk:
        hit("venom_x_risk")
        return []
    eq = ctx.equity or 0.0
    shares = S._EN.cap_initial(S._first_units(p, eq, risk, x(entry_m), 1.0, 0.0), p) if eq else 0
    if shares < 1:
        return []
    T = np.asarray(ctx.t)
    n = len(T)
    fill_i = None
    for i in range(k_sig + 1, n):
        if T[i] >= p.venom_until:
            break
        hm, lm = (ctx.h[i] * sgn, ctx.l[i] * sgn) if sgn > 0 else (ctx.l[i] * sgn, ctx.h[i] * sgn)
        if hm >= tgt_m:
            hit("venom_x_target_first")
            return []                                              # the target traded before the fill: cancelled
        if lm <= entry_m + MIN1:
            fill_i = i
            break
    if fill_i is None:
        return []
    om = ctx.o[fill_i] * sgn
    fill = min(om, entry_m)                                        # a limit: at the open when the bar opens through it
    armed = pd.Timestamp(ctx.idx[k_sig])
    tr = S.Trade(day, symbol, "AM", "venom", "long" if sgn > 0 else "short", "venom_range", False, None, armed, pd.Timestamp(ctx.idx[fill_i]),
                 x(fill), x(stop_m), x(tgt_m), None, shares, day_type=S.day_type(day), news=S.news(day), weekday=day.weekday(),
                 lv_tags="venom|venom_stop_" + p.venom_stop, entry_kind="venom", **btag)
    tr.entry_risk_pct = round(shares * (fill - stop_m) / eq, 5) if eq else None
    tr.peak_risk_pct = tr.entry_risk_pct
    exit_ = None
    for i in range(fill_i, n):
        if T[i] >= p.venom_flat:
            exit_ = (pd.Timestamp(ctx.idx[i]), float(ctx.o[i]), shares, "venom_time")
            break
        om_ = ctx.o[i] * sgn
        hm, lm = (ctx.h[i] * sgn, ctx.l[i] * sgn) if sgn > 0 else (ctx.l[i] * sgn, ctx.h[i] * sgn)
        if i > fill_i and om_ <= stop_m:
            exit_ = (pd.Timestamp(ctx.idx[i]), x(om_), shares, "stop_gap")
        elif lm <= stop_m:
            exit_ = (pd.Timestamp(ctx.idx[i]), x(stop_m), shares, "stop")
        elif hm >= tgt_m:
            exit_ = (pd.Timestamp(ctx.idx[i]), x(tgt_m), shares, "t1")
            tr.final_hit = True
        if exit_ is not None:
            break
    if exit_ is None:
        exit_ = (pd.Timestamp(ctx.idx[-1]), float(ctx.c[-1]), shares, "eod")
    tr.exits.append(exit_)
    hit("venom")
    return [tr]
