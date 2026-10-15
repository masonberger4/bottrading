from datetime import date

import numpy as np
import pandas as pd

from mentorship2023 import backtest as B, levels as L
from mentorship2023.strategy import Params, blocked


def arr(*rows):
    """rows of (open, high, low, close) -> o, h, l, c arrays"""
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_fvg_bull_and_bear_with_ce():
    o, h, l, c = arr((10, 11, 9.5, 10.8), (10.8, 13, 10.7, 12.9), (12.9, 14, 12, 13.5),
                     (13.5, 13.6, 11, 11.2), (11.2, 11.3, 9, 9.2), (9.2, 9.4, 8, 8.5))
    g = L.fvgs(h, l)
    bull = [z for z in g if z.kind == "bull"]
    bear = [z for z in g if z.kind == "bear"]
    assert bull[0] == L.Zone("bull", 12.0, 11.0, 2, 1)          # low[2] 12 > high[0] 11
    assert bull[0].mid == 11.5                                  # consequent encroachment
    assert bear and bear[0].kind == "bear" and bear[0].top > bear[0].bottom
    assert all(z.i >= 2 for z in g)


def test_no_fvg_when_wicks_overlap():
    o, h, l, c = arr((10, 11, 9, 10.5), (10.5, 11.5, 10, 11), (11, 12, 10.9, 11.8))
    assert L.fvgs(h, l) == []


def test_volume_imbalance_bodies_gap_wicks_overlap():
    o, h, l, c = arr((10, 10.6, 9.9, 10.5), (10.6, 11, 10.4, 10.9))
    vi = L.volume_imbalances(o, h, l, c)
    assert vi == [L.Zone("bull", 10.6, 10.5, 1, 1)]
    o, h, l, c = arr((10, 10.6, 9.9, 10.5), (10.7, 11, 10.65, 10.9))   # wicks don't overlap
    assert L.volume_imbalances(o, h, l, c) == []


def test_pivots_confirmed_n_bars_later():
    h = np.array([1, 2, 5, 3, 2, 4, 6, 3, 2], float)
    l = h - 1
    ph, pl = L.pivots(h, l, 2)
    assert [(p.i, p.price, p.known) for p in ph] == [(2, 5.0, 4), (6, 6.0, 8)]
    assert [(p.i, p.known) for p in pl] == [(4, 6)]


def test_order_block_mean_threshold():
    o, h, l, c = arr((10, 10.5, 9.8, 10.4), (10.4, 10.5, 9.6, 9.7), (9.7, 11, 9.7, 10.9))
    ob = L.order_block(o, h, l, c, 0, 1, "bull")     # last down-close candle
    assert ob.src == 1 and ob.mid == (10.5 + 9.6) / 2


def test_bullish_breaker():
    # swing low, swing high, lower low, then a body closes above the swing high
    o, h, l, c = arr(
        (10, 10.2, 9.8, 10.0), (10, 10.1, 9.5, 9.6), (9.6, 9.7, 9.0, 9.2),   # low at 2
        (9.2, 9.9, 9.1, 9.8), (9.8, 10.4, 9.7, 10.3),                        # up-close at 4 = high
        (10.3, 10.3, 9.6, 9.7), (9.7, 9.8, 9.2, 9.3), (9.3, 9.4, 8.6, 8.8),  # lower low at 7
        (8.8, 9.6, 8.7, 9.5), (9.5, 10.0, 9.4, 9.9), (9.9, 10.8, 9.8, 10.7))  # close > 10.4
    br = [z for z in L.breakers(o, h, l, c, 2) if z.kind == "bull"]
    assert br and br[0].src == 4 and br[0].i == 10
    assert (br[0].top, br[0].bottom) == (10.4, 9.7)


def test_relative_equal_levels():
    assert L.equal_levels([100.0, 100.03, 101.0, 102.0, 102.04, 102.05], 0.05) == [100.03, 102.05]
    assert L.equal_levels([1.0, 2.0], 0.05) == []


def test_opens_use_premarket_proxy_for_midnight():
    idx = pd.date_range("2026-06-01 04:00", "2026-06-01 15:55", freq="5min", tz="America/New_York")
    o = np.arange(len(idx), dtype=float)
    op = L.opens(idx, o)
    assert op["midnight"] == 0 and op["0930"] == (570 - 240) / 5 and op["1330"] == (810 - 240) / 5


def test_day_filter():
    assert blocked(date(2026, 9, 4), "AM") == "nfp_day"            # NFP Friday
    assert blocked(date(2026, 9, 3), "AM") == "nfp_week_thu_fri"
    assert blocked(date(2026, 9, 2), "PM") == "nfp_week_wed_pm"
    assert blocked(date(2026, 9, 2), "AM") is None
    assert blocked(date(2026, 9, 16), "PM") == "fomc_pm"
    assert blocked(date(2026, 9, 16), "AM") is None


def test_backtest_does_not_look_ahead():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(es_pt=0.09, use_bias=False)
    full = B.run(x, 5, "RW", p, y)
    assert len(full) > 0
    cols = ["entry_time", "entry", "stop", "t1", "shares"]
    for cut in full.entry_time.iloc[::3]:
        c = cut + pd.Timedelta(minutes=2)
        part = B.run(x[x.index <= c], 5, "RW", p, y[y.index <= c], partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_rejection_block_at_swing_high():
    o, h, l, c = arr((10, 10.5, 9.9, 10.4), (10.4, 10.9, 10.3, 10.8), (10.8, 12.0, 10.7, 10.9),
                     (10.9, 11.0, 10.2, 10.3), (10.3, 10.4, 9.8, 9.9))
    rb = [z for z in L.rejection_blocks(o, h, l, c, 2) if z.kind == "bear"]
    assert rb == [L.Zone("bear", 12.0, 10.9, 4, 2)]


def test_balanced_price_range():
    # up gap (bull FVG 11-12), then a down gap through the same prices (bear FVG)
    h = np.array([11, 13, 14, 13.5, 11.5, 10], float)
    l = np.array([10, 11, 12, 11.8, 10.5, 9], float)
    bpr = L.balanced_ranges(h, l)
    assert bpr and bpr[0].kind == "bear" and bpr[0].top <= 12 and bpr[0].bottom >= 11


def test_wick_midpoints_and_weekly_bias():
    assert L.wick_midpoints(10, 12, 8, 9) == {"upper": 11.0, "lower": 8.5}
    from mentorship2023.strategy import weekly_bias
    hist = []
    for k, d in enumerate(pd.bdate_range("2026-06-01", "2026-06-16")):
        idx = pd.date_range(d + pd.Timedelta(hours=9.5), periods=2, freq="195min", tz="America/New_York")
        o, hh, ll, cc = (100, 101, 99, 100.5) if d.day != 16 else (100, 100.5, 94, 94.5)
        hist.append(pd.DataFrame({"open": [o, cc], "high": [hh, hh], "low": [ll, ll], "close": [o, cc]}, idx))
    assert weekly_bias(hist, date(2026, 6, 17)) == -1     # strong down Tuesday
    assert weekly_bias(hist, date(2026, 6, 22)) == 0      # next week


def test_no_look_ahead_with_every_optional_rule_on():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=5)
    p = Params(es_pt=0.09, use_bias=False, trail=True, adds=(0.5, 0.33), weekly_bias=True,
               sd_targets=True, wick_levels=True)
    full = B.run(x, 5, "RW", p, y)
    assert len(full) > 0
    cols = ["entry_time", "entry", "stop", "t1", "shares", "htf"]
    for cut in full.entry_time.iloc[::2]:
        c = cut + pd.Timedelta(minutes=2)
        part = B.run(x[x.index <= c], 5, "RW", p, y[y.index <= c], partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
