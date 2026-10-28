"""Caption-gap pass, package bias_htf#7/7 - the PARKED stock research studies (M17; models_setups_entries.md items 220, 221, 222, 224, 225). Daily bars of the Dow 30 stocks and DIA / SPY / QQQ; reports only,
nothing here trades or is wired into `run_day`. Every function raises unless `Params.stocks_mode` is on. Selection reads closed daily bars up to the date given; the forward returns REPORTED beside a pick read
the bars after it (research output, never used to select).

  jan_smt     (M17-stock-jan-fvg-refill-entry)    stocks with a higher January low while the Dow made a lower low
  gap_refill  (M17-stock-jan-fvg-refill-entry)    January up-gaps / voids refilled in February + forward 1-3 month returns
  sell_list   (M17-stock-sell-watchlist-smt, new-stock-short-prefer-rally-into-premium)  weekly lower high vs a DIA higher high, bearish weekly flow, a rally into a weekly premium array
  base_ok     (new-stock-no-gapped-away-or-overextended)  >= 15 daily bars within 15 % in the last 60 bars; no unfilled up-gap above it with the price > 10 % over the base high
  mega        (new-stock-mega-trade-process-and-filters)  the steps the data allows; fundamentals / IBD lists are reported as unavailable
Thresholds the sources never give are marked [our interpretation].
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import htf
from . import levels as L
from .stocks import EXCLUDE, _closed, _naive, need_mode, weekly_closed

FWD = (21, 42, 63)                    # trading days: about 1, 2 and 3 months
UNAVAILABLE = ("fundamental screen", "IBD 50 / sector leaders", "SmartSelect composite", "option Greeks / strikes")


def _month(d: pd.DataFrame, year: int, month: int) -> pd.DataFrame:
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return d[(idx.year == year) & (idx.month == month)]


def _fwd(d: pd.DataFrame, t, ns=FWD) -> list:
    """Forward returns (fraction) from the close of the bar at / after `t` to the close `ns` bars later (NaN beyond the data). Research reporting only."""
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    k = int(idx.searchsorted(_naive(t).normalize()))
    c = d.close.values.astype(float)
    return [float(c[k + n] / c[k] - 1.0) if k + n < len(c) and k < len(c) else float("nan") for n in ns]


# --------------------------------------------------------------------------------------------------------------
# M17-stock-jan-fvg-refill-entry
# --------------------------------------------------------------------------------------------------------------

def jan_smt(year: int, stocks: dict, dia: pd.DataFrame, p) -> list:
    """The stocks whose January low is HIGHER than their previous December's low while the Dow (DIA) made a LOWER January low than its December low (the January stock-vs-Dow SMT, cc10_016 ~7:07). [our
    interpretation: 'a lower low' = the January low against the December low; the pivot form is `stocks.smt_screen`.] Known at the end of January."""
    need_mode(p)
    dj, dd = _month(dia, year, 1), _month(dia, year - 1, 12)
    if not len(dj) or not len(dd) or not dj.low.min() < dd.low.min():
        return []
    out = []
    for s, d in stocks.items():
        j, c = _month(d, year, 1), _month(d, year - 1, 12)
        if len(j) and len(c) and j.low.min() > c.low.min():
            out.append(s)
    return out


def gap_refill(stock_d: pd.DataFrame, year: int, p) -> list:
    """January up-gaps (a bar's low above the previous bar's high) and bullish daily voids (3-candle FVGs whose third bar is a January bar) are discount arrays; the first February session whose low trades
    back into one refills it. One row per array: kind, zone, refill date, February trading-day number and the forward 1 / 2 / 3 month returns from the refill close (reported)."""
    need_mode(p)
    d = stock_d
    idx = pd.DatetimeIndex(d.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    h, l = d.high.values.astype(float), d.low.values.astype(float)
    jan = [k for k in range(1, len(d)) if idx[k].year == year and idx[k].month == 1]
    zones = [("gap", float(l[k]), float(h[k - 1])) for k in jan if l[k] > h[k - 1]]
    for z in L.fvgs(h, l):
        if z.kind == "bull" and idx[z.i].year == year and idx[z.i].month == 1:
            zones.append(("fvg", float(z.top), float(z.bottom)))
    feb = [k for k in range(len(d)) if idx[k].year == year and idx[k].month == 2]
    out = []
    for kind, top, bot in zones:
        hit = next((n for n, k in enumerate(feb) if l[k] <= top), None)
        if hit is None:
            continue
        k = feb[hit]
        out.append(dict(kind=kind, top=top, bottom=bot, refill=idx[k], feb_day=hit + 1, **dict(zip(("fwd1m", "fwd2m", "fwd3m"), _fwd(d, idx[k])))))
    return out


# --------------------------------------------------------------------------------------------------------------
# M17-stock-sell-watchlist-smt / new-stock-short-prefer-rally-into-premium
# --------------------------------------------------------------------------------------------------------------

def sell_window(asof) -> bool:
    """January, or May 1 - Aug 1 (cc10_017 ~1:40)."""
    t = _naive(asof)
    return t.month == 1 or t.month in (5, 6, 7)


def weekly_flow(w: pd.DataFrame) -> int:
    """The weekly order flow of a weekly frame: -1 when the last weekly pivot high is lower than the one before AND the last close is under the midpoint of the last 13 weeks' range; +1 the mirror; else 0
    [our interpretation of 'weekly order flow already bearish']."""
    if len(w) < 8:
        return 0
    h, l, c = (w[k].values.astype(float) for k in ("high", "low", "close"))
    ph, pl = L.pivots(h, l, 1)
    mid = (h[-13:].max() + l[-13:].min()) / 2.0
    if len(ph) >= 2 and ph[-1].price < ph[-2].price and c[-1] < mid:
        return -1
    if len(pl) >= 2 and pl[-1].price > pl[-2].price and c[-1] > mid:
        return 1
    return 0


def rally_into_premium(w: pd.DataFrame, weeks: int = 13) -> bool:
    """An up-close weekly bar within the last `weeks` weeks traded into a live weekly bearish array (FVG / OB drawn on the weekly bars known before that week; not closed through): the counter-trend 'Judas'
    rally into premium of item 222."""
    if len(w) < 8:
        return False
    o, h, l, c = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    arrs = [a for a in htf._arrays(o, h, l, c, "W", lambda i: i + 1) if a.kind == "bear" and a.typ in ("fvg", "ob")]
    for k in range(max(1, len(c) - weeks), len(c)):
        if c[k] <= o[k]:
            continue
        for a in arrs:
            if a.known <= k and h[k] >= a.bottom and not (c[a.known:k].size and c[a.known:k].max() > (a.ce if a.typ == "ob" else a.top)):
                return True
    return False


def sell_list(asof, stocks: dict, dia: pd.DataFrame, p, need_rally: bool = True, match_weeks: int = 4, window_weeks: int = 26) -> list:
    """The sell watch list at `asof` (cc10_017 ~1:40): in the sell window only; the Dow's last weekly pivot high is HIGHER than the one before; a stock qualifies when its last weekly pivot high (within
    `match_weeks` of the Dow's) is LOWER than its previous one, its weekly flow is bearish, defensives (VZ, GE, KO) are excluded and (item 222, need_rally) an up-close weekly bar in the last 13 weeks
    traded into a weekly premium array. One row per stock: symbol, forward 1 / 2 / 3 month returns (reported; a short profits from negative numbers). The signal holds only while the Dow keeps making higher
    highs, so a Dow lower high returns []."""
    need_mode(p)
    if not sell_window(asof):
        return []
    wd = weekly_closed(dia, asof).iloc[-window_weeks:]
    if len(wd) < 8:
        return []
    phd, _ = L.pivots(wd.high.values.astype(float), wd.low.values.astype(float), 1)
    if len(phd) < 2 or not phd[-1].price > phd[-2].price:
        return []
    out = []
    for s, d in stocks.items():
        if s in EXCLUDE:
            continue
        w = weekly_closed(d, asof).iloc[-window_weeks:]
        if len(w) < 8:
            continue
        ph, _ = L.pivots(w.high.values.astype(float), w.low.values.astype(float), 1)
        if len(ph) < 2 or not ph[-1].price < ph[-2].price:
            continue
        # the stock's lower high sits at the Dow's higher high (within match_weeks)
        if abs((w.index[ph[-1].i] - wd.index[phd[-1].i]).days) > 7 * match_weeks:
            continue
        if weekly_flow(w) >= 0:
            continue
        if need_rally and not rally_into_premium(w):
            continue
        out.append(dict(symbol=s, **dict(zip(("fwd1m", "fwd2m", "fwd3m"), _fwd(d, asof)))))
    return out


# --------------------------------------------------------------------------------------------------------------
# new-stock-no-gapped-away-or-overextended
# --------------------------------------------------------------------------------------------------------------

def find_base(h: np.ndarray, l: np.ndarray, min_bars: int = 15, max_range: float = 0.15):
    """The most recent base in the arrays (indices into them): the latest window of >= min_bars bars whose (highest high - lowest low) / lowest low <= max_range, extended back as far as it holds.
    (start, end, base_low, base_high) or None."""
    n = len(h)
    for e in range(n - 1, min_bars - 2, -1):
        s = e
        lo, hi = float(l[e]), float(h[e])
        while s - 1 >= 0 and (max(hi, float(h[s - 1])) - min(lo, float(l[s - 1]))) / min(lo, float(l[s - 1])) <= max_range:
            s -= 1
            lo, hi = min(lo, float(l[s])), max(hi, float(h[s]))
        if e - s + 1 >= min_bars:
            return s, e, lo, hi
    return None


def base_ok(stock_d: pd.DataFrame, asof, p, min_bars: int = 15, max_range: float = 0.15, ext: float = 0.10, window: int = 60) -> dict:
    """Reject a stock that has gapped away from its base or is extended with no base (cc11_003 ~32:27, ~43:37): a base = >= 15 daily bars with a range <= 15 % inside the last 60 closed bars; reject an
    UNFILLED up-gap (a bar's low above the previous high, never traded back down to it) that opened above the base while the close is more than 10 % above the base high; with NO base reject when the close
    is more than 10 % above the window's low (extended trend, turtle-soup risk). Inside or just breaking out of a base, or a small gap followed by sideways movement, is accepted [thresholds ours].
    Returns dict(ok, reason, base)."""
    need_mode(p)
    d = _closed(stock_d, asof).iloc[-window:]
    if len(d) < min_bars:
        return dict(ok=False, reason="no_data", base=None)
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    px = float(c[-1])
    b = find_base(h, l, min_bars, max_range)
    if b is None:
        return dict(ok=not px > (1.0 + ext) * float(l.min()), reason="no_base_extended" if px > (1.0 + ext) * float(l.min()) else "", base=None)
    s, e, lo, hi = b
    for k in range(e + 1, len(d)):
        if l[k] > h[k - 1] and l[k] > hi and l[k:].min() > h[k - 1] and px > (1.0 + ext) * hi:
            return dict(ok=False, reason="gapped_away", base=(lo, hi, e - s + 1))
    return dict(ok=True, reason="", base=(lo, hi, e - s + 1))


# --------------------------------------------------------------------------------------------------------------
# new-stock-mega-trade-process-and-filters
# --------------------------------------------------------------------------------------------------------------

def last_two_lows(d: pd.DataFrame, n: int, lookback: int):
    """The last two pivot lows (index, price) of the last `lookback` bars, or None."""
    x = d.iloc[-lookback:]
    _, pl = L.pivots(x.high.values.astype(float), x.low.values.astype(float), n)
    return None if len(pl) < 2 else ((x.index[pl[-2].i], pl[-2].price), (x.index[pl[-1].i], pl[-1].price))


def three_index_smt(indices: dict, asof, p, lookback: int = 60):
    """The daily three-index SMT (cc11_003 ~28:37): of the averages in `indices` ({name: daily frame}) at least two made a LOWER pivot low (their last pivot low under the one before) while one held a HIGHER
    one. Returns (name of the holder, date of the latest lower low) or None."""
    lower, holder = [], []
    for k, d in indices.items():
        r = last_two_lows(_closed(d, asof), p.stock_piv_n, lookback)
        if r is None:
            return None
        (lower if r[1][1] < r[0][1] else holder if r[1][1] > r[0][1] else lower).append((k, r[1][0]))
    if len(lower) >= 2 and len(holder) == 1:
        return holder[0][0], max(t for _, t in lower)
    return None


def mega(asof, stocks: dict, indices: dict, p, min_price: float = 20.0, lookback: int = 60) -> dict:
    """The mega-trade screen as far as the data goes: the three-index daily SMT (two averages lower, one higher), then the stocks whose swing low around the SMT date (+/- p.stock_match_days) is HIGHER than
    their prior swing low (a lower low = reject), that pass `base_ok` (basing, not gapped away or extended) and trade above `min_price`. Fundamentals, the IBD lists, the SmartSelect composite and the option
    Greeks are reported as unavailable. Returns dict(smt, picks, unavailable)."""
    need_mode(p)
    smt = three_index_smt(indices, asof, p, lookback)
    if smt is None:
        return dict(smt=None, picks=[], unavailable=list(UNAVAILABLE))
    holder, when = smt
    picks = []
    for s, d in stocks.items():
        if s in EXCLUDE:
            continue
        x = _closed(d, asof)
        if not len(x) or float(x.close.iloc[-1]) <= min_price:
            continue
        r = last_two_lows(x, p.stock_piv_n, lookback)
        if r is None or not r[1][1] > r[0][1]:
            continue
        if abs((_naive(r[1][0]).normalize() - _naive(when).normalize()).days) > max(1, p.stock_match_days) * 2:
            continue
        if base_ok(d, asof, p)["ok"]:
            picks.append(s)
    return dict(smt=(holder, when), picks=picks, unavailable=list(UNAVAILABLE))
