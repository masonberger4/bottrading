"""Caption-gap pass, package bias_htf#7/7 - the PARKED stock watch-list screens (M17; other.md items 21, 22, 24). Research functions on daily bars; not wired into `run_day` (`Params.stock_intraday` keeps
individual stocks out of the intraday engine). Every function raises unless `Params.stocks_mode` is on.

Data: daily OHLC frames with a DatetimeIndex (e.g. `alpaca_data.bars(sym, 1440, start)`); the index is DIA (or YM daily). A daily bar is used only when its date is <= `asof` (closed bars), a weekly
bar only when its Friday label is <= `asof`. Thresholds the sources never give are marked [our interpretation].

  smt_screen   (OT-stocks-smt-weekly-screen)      the Dow-vs-stock lower-low / higher-low screen -> "keep" / "discard" / "none"
  weekly_up    (OT-stocks-smt-weekly-screen)      two rising weekly pivots and the last down-close week's low not closed below
  watchlist    (21 + 22 + 24)                     exclusions -> leaders -> smt_screen -> select; only in / within ~21 trading days before a buy window
  select       (OT-stocks-exclusions-selection)   2-4 names at / just below the old weekly highs, not extended
  rs_rank / leaders (OT-stocks-rs-leadership)     the price-only stock leg of the L of CAN SLIM; sector / group legs behind the hooks sector_of / group_of
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L

DOW30 = ("AAPL", "AMGN", "AMZN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM", "MRK",
         "MSFT", "NKE", "NVDA", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT")
EXCLUDE = ("VZ", "KO", "GE")                # the 'safe' stocks ICT avoids (cc10_016 ~3:01)
EXCLUDE_2017 = ("MSFT", "INTC")             # dropped in 2017 as 'not exciting' - his opinion at the time
BUY_MONTHS = (10, 11, 12, 1, 2, 3, 4, 5)   # Feb-May and Oct-Jan
LEAD_DAYS = 30                              # ~21 trading days before a window opens


def need_mode(p) -> None:
    """The stock modules are parked (M17): they run only with Params.stocks_mode."""
    if p is None or not getattr(p, "stocks_mode", False):
        raise RuntimeError("stocks.py is parked (M17): set Params.stocks_mode=True")


def _closed(df: pd.DataFrame, asof) -> pd.DataFrame:
    """The daily bars with a date <= asof (closed bars only)."""
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return df[idx.normalize() <= _naive(asof).normalize()]


def _naive(t) -> pd.Timestamp:
    t = pd.Timestamp(t)
    return t.tz_localize(None) if t.tzinfo is not None else t


def weekly_closed(daily: pd.DataFrame, asof) -> pd.DataFrame:
    """Weekly bars (W-FRI) of the closed daily bars whose Friday label is <= asof."""
    d = _closed(daily, asof)
    if not len(d):
        return d
    d = d.set_index(pd.DatetimeIndex(d.index).tz_localize(None)) if d.index.tz is not None else d
    w = d.resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return w[w.index <= _naive(asof).normalize()]


def in_buy_window(asof) -> bool:
    """asof is inside a buy window (Feb-May, Oct-Jan) or within ~21 trading days (30 calendar days) before one opens (the study month before)."""
    t = _naive(asof).normalize()
    if t.month in BUY_MONTHS:
        return True
    return 0 <= (pd.Timestamp(year=t.year, month=10, day=1) - t).days <= LEAD_DAYS


def _win_low(l: np.ndarray, k: int, m: int) -> float:
    return float(l[max(0, k - m):k + m + 1].min())


def _win_high(h: np.ndarray, k: int, m: int) -> float:
    return float(h[max(0, k - m):k + m + 1].max())


# --------------------------------------------------------------------------------------------------------------
# OT-stocks-smt-weekly-screen
# --------------------------------------------------------------------------------------------------------------

def smt_screen(stock_d: pd.DataFrame, index_d: pd.DataFrame, asof, p, lookback: int = 60) -> str:
    """The Dow-vs-stock screen on closed daily bars (cc10_016 ~1:49-4:24; cc11_003 ~23:35). Over the last `lookback` common bars: the index's last two pivot lows (`levels.pivots`, p.stock_piv_n); when the
    second is LOWER and the stock's lowest low in the same window (+/- p.stock_match_days) is HIGHER than its own low around the first, the stock is kept. Then, when the index's next pivot low fails to make
    a lower low (a failure swing), the stock must have made a higher high at the same juncture (its highest high in the window around that pivot above its last pivot high before the window) or it is
    discarded. Returns "keep", "discard" or "none" (no index lower low / the stock made lower lows too)."""
    need_mode(p)
    s = _closed(stock_d, asof)
    x = _closed(index_d, asof)
    idx = s.index.intersection(x.index)[-lookback:]
    if len(idx) < 10:
        return "none"
    s, x = s.loc[idx], x.loc[idx]
    n, m = int(p.stock_piv_n), int(p.stock_match_days)
    ih, il = x.high.values.astype(float), x.low.values.astype(float)
    sh, sl = s.high.values.astype(float), s.low.values.astype(float)
    _, pl = L.pivots(ih, il, n)
    if len(pl) < 2:
        return "none"
    # the last pair of consecutive index pivot lows where the later one is lower (the index's lower low)
    pair = None
    for q in range(len(pl) - 1, 0, -1):
        if pl[q].price < pl[q - 1].price:
            pair = (pl[q - 1], pl[q], q)
            break
    if pair is None:
        return "none"
    a, b, qb = pair
    if not _win_low(sl, b.i, m) > _win_low(sl, a.i, m):
        return "none"
    later = pl[qb + 1:]
    if later and later[0].price >= b.price:                      # the index's next pivot low fails to make a lower low
        c = later[0]
        ph, _ = L.pivots(sh, sl, n)
        prev = [q.price for q in ph if q.i < max(0, c.i - m) and q.known < len(sh)]
        if prev and not _win_high(sh, c.i, m) > prev[-1]:
            return "discard"
    return "keep"


def weekly_up(stock_d: pd.DataFrame, asof) -> bool:
    """On the closed weekly bars: the last two weekly pivot highs and the last two weekly pivot lows rise, and the low of the last down-close week has not been closed below (cc10_016 ~10:03-11:00) [our
    interpretation: 'trending up on the weekly' = two rising weekly pivots; 'down-close weeks holding as support' = no later weekly close under the last down-close week's low]."""
    w = weekly_closed(stock_d, asof)
    if len(w) < 6:
        return False
    h, l, c, o = (w[k].values.astype(float) for k in ("high", "low", "close", "open"))
    ph, pl = L.pivots(h, l, 1)
    if len(ph) < 2 or len(pl) < 2 or not (ph[-1].price > ph[-2].price and pl[-1].price > pl[-2].price):
        return False
    down = [k for k in range(len(c)) if c[k] < o[k]]
    if down:
        k = down[-1]
        if len(c) > k + 1 and c[k + 1:].min() < l[k]:
            return False
    return True


# --------------------------------------------------------------------------------------------------------------
# OT-stocks-exclusions-selection
# --------------------------------------------------------------------------------------------------------------

def excluded(p) -> tuple:
    return EXCLUDE + (EXCLUDE_2017 if p.stock_excl_2017 else ())


def atr20(d: pd.DataFrame) -> float:
    """The mean true range of the last 20 daily bars."""
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    if len(c) < 2:
        return float("nan")
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    return float(tr[-20:].mean())


def near_high_info(d: pd.DataFrame, asof, p) -> dict:
    """near_high (the close within p.stock_near_high_pct below the highest weekly high of the last 52 weeks, or at / above it), the distance (fraction under the old high, 0 at / above), and extended (the close
    more than p.stock_ext_atr x the 20-day ATR above the last weekly pivot low)."""
    w = weekly_closed(d, asof)
    dd = _closed(d, asof)
    if len(w) < 8 or not len(dd):
        return dict(near_high=False, dist=float("nan"), extended=False)
    px = float(dd.close.iloc[-1])
    old = float(w.high.values[-52:].max())
    dist = max(0.0, (old - px) / old) if old > 0 else float("nan")
    _, pl = L.pivots(w.high.values.astype(float), w.low.values.astype(float), 1)
    low_p = float(pl[-1].price) if pl else float(w.low.values.min())
    a = atr20(dd)
    ext = bool(a == a and a > 0 and (px - low_p) > p.stock_ext_atr * a)
    return dict(near_high=bool(dist == dist and dist <= p.stock_near_high_pct), dist=dist, extended=ext)


def select(kept, universe: dict, asof, p, n_max: int = 4, opt_cost=None, fund_ok=None) -> list:
    """From the screened survivors pick up to `n_max` (2-4): near the old weekly high and not extended, closest to the old high first. Excluded symbols are never returned. Fewer than two survivors = none
    ('at least 2 when available, else none'). The hooks opt_cost(sym) (option affordability) and fund_ok(sym) (quarterly sales / profit increases) return None without the data and are then ignored; a
    False from fund_ok drops the name."""
    need_mode(p)
    bad = set(excluded(p))
    rows = []
    for s in kept:
        if s in bad or s not in universe:
            continue
        info = near_high_info(universe[s], asof, p)
        if not info["near_high"] or info["extended"]:
            continue
        if fund_ok is not None and fund_ok(s) is False:
            continue
        rows.append((info["dist"], s))
    rows.sort()
    out = [s for _, s in rows][:n_max]
    return out if len(out) >= 2 else []


# --------------------------------------------------------------------------------------------------------------
# OT-stocks-rs-leadership
# --------------------------------------------------------------------------------------------------------------

def rs_rank(stocks: dict, index_d: pd.DataFrame, asof, n: int = 63) -> dict:
    """Each stock's n-day % change minus the index's, ranked to a 0-100 percentile across the universe (best = 100; closed bars to asof). Stocks with fewer than n+1 bars are left out."""
    ix = _closed(index_d, asof).close.values.astype(float)
    if len(ix) <= n:
        return {}
    bench = ix[-1] / ix[-1 - n] - 1.0
    rel = {}
    for s, d in stocks.items():
        c = _closed(d, asof).close.values.astype(float)
        if len(c) > n and c[-1 - n] > 0:
            rel[s] = c[-1] / c[-1 - n] - 1.0 - bench
    if not rel:
        return {}
    order = sorted(rel, key=lambda k: rel[k])
    den = max(1, len(order) - 1)
    return {s: 100.0 * k / den for k, s in enumerate(order)}


def leaders(stocks: dict, index_d: pd.DataFrame, asof, p, index_flip=None, sector_of=None, group_of=None, n: int = 63) -> list:
    """The price-only leadership filter (L of CAN SLIM, cc11_003 ~14:03; cc10_018 ~16:02): runs only when the market precondition is bullish (the index's table `flip` > 0, else `weekly_up(index_d)`);
    keeps the stocks with rs_rank >= p.stock_rs_min whose close is above the midpoint of their last 60-day range (leaving a discount). Hooks sector_of(sym) / group_of(sym) return None (the sector and
    group legs need IBD data); when they answer, the sectors (then the groups of the kept sectors) are ranked by the mean member rs_rank and only the top p.stock_top_sectors of each are kept first."""
    need_mode(p)
    bull = (index_flip > 0) if index_flip is not None else weekly_up(index_d, asof)
    if not bull:
        return []
    rk = rs_rank(stocks, index_d, asof, n)
    pool = [s for s in rk]
    if sector_of is not None and any(sector_of(s) is not None for s in pool):
        pool = _top_groups(pool, rk, sector_of, p.stock_top_sectors)
    if group_of is not None and any(group_of(s) is not None for s in pool):
        pool = _top_groups(pool, rk, group_of, p.stock_top_sectors)
    out = []
    for s in pool:
        if rk[s] < p.stock_rs_min:
            continue
        d = _closed(stocks[s], asof)
        h, l, c = d.high.values[-60:].astype(float), d.low.values[-60:].astype(float), d.close.values.astype(float)
        if len(c) and c[-1] > (h.max() + l.min()) / 2.0:
            out.append(s)
    return sorted(out, key=lambda s: -rk[s])


def _top_groups(pool: list, rk: dict, key_of, n_top: int) -> list:
    groups: dict = {}
    for s in pool:
        g = key_of(s)
        if g is not None:
            groups.setdefault(g, []).append(s)
    ranked = sorted(groups, key=lambda g: -float(np.mean([rk[s] for s in groups[g]])))[:n_top]
    return [s for g in ranked for s in groups[g]]


# --------------------------------------------------------------------------------------------------------------
# the watch list
# --------------------------------------------------------------------------------------------------------------

def watchlist(asof, universe: dict, index_d: pd.DataFrame, p, n_max: int = 4, index_flip=None, sector_of=None, group_of=None, use_leaders: bool = True, opt_cost=None, fund_ok=None) -> dict:
    """The buy watch list at `asof`: {} outside the buy windows. Order (item 24): exclusions -> leaders -> smt_screen -> select. Returns dict(kept=the screened symbols, weekly-uptrend names first,
    picks=select()). Empty lists in July (no window)."""
    need_mode(p)
    if not in_buy_window(asof):
        return dict(kept=[], picks=[])
    bad = set(excluded(p))
    pool = {s: d for s, d in universe.items() if s not in bad}
    if use_leaders:
        lead = leaders(pool, index_d, asof, p, index_flip, sector_of, group_of)
        pool = {s: pool[s] for s in lead}
    kept = [s for s, d in pool.items() if smt_screen(d, index_d, asof, p) == "keep"]
    kept.sort(key=lambda s: (not weekly_up(pool[s], asof), s))
    return dict(kept=kept, picks=select(kept, pool, asof, p, n_max, opt_cost, fund_ok))
