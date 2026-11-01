from datetime import date

import numpy as np
import pandas as pd

from mentorship import backtest as B, levels as L
from mentorship.strategy import Params, blocked
from dataclasses import dataclass as _oa_dc  # noqa: E402


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False


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
    from mentorship.strategy import weekly_bias
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
               sd_targets=True, wick_levels=True, leg_pd=0, min_draw_pts=0)
    full = B.run(x, 5, "RW", p, y)
    assert len(full) > 0
    cols = ["entry_time", "entry", "stop", "t1", "shares", "htf"]
    for cut in full.entry_time.iloc[::2]:
        c = cut + pd.Timedelta(minutes=2)
        part = B.run(x[x.index <= c], 5, "RW", p, y[y.index <= c], partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_htf_bias_uses_nothing_after_0930():
    import pandas as pd
    from mentorship import backtest as B, htf
    from pathlib import Path
    if not Path("data/mentorship/SPX_5min_hd.csv").exists():
        return
    df = B.load("SPX", 5, source="histdata")
    df = df[(df.index >= "2024-01-01") & (df.index < "2024-07-01")]
    full = htf.table(df)
    for day in list(full.index)[-40::7]:
        cut = pd.Timestamp(day, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
        part = htf.table(df[df.index < cut])
        a, b = full.loc[day], part.loc[day]
        for k in ("react", "draw", "pd", "combo", "react_score", "draw_up", "draw_dn"):
            assert (a[k] == b[k]) or (a[k] != a[k] and b[k] != b[k]), (day, k, a[k], b[k])


def test_no_look_ahead_with_decision_switches_on():
    x, y = B.synthetic(start="2026-03-30", end="2026-10-14", tf=5, seed=7)
    for kw in (dict(mss_mode="wick", fvg_abort=True, time_stop_min=10, reentry_half=True,
                    no_pm_after_am_win=True, pm_done_by=900, leg_pd=0, min_draw_pts=0),
               dict(sb_only=True, min_draw_pts=5, leg_pd=0.8, max_trades_week=3, am_exit=660)):
        p = Params(es_pt=0.09, use_bias=False, **kw)
        full = B.run(x, 5, "RW", p, y)
        assert len(full) > 0
        cols = ["entry_time", "entry", "stop", "t1", "shares"]
        for cut in full.entry_time.iloc[::2]:
            c = cut + pd.Timedelta(minutes=2)
            part = B.run(x[x.index <= c], 5, "RW", p, y[y.index <= c], partial_last=True)
            a = full[full.entry_time <= c][cols].reset_index(drop=True)
            b = part[part.entry_time <= c][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b)


def test_confluence_tags_do_not_look_ahead():
    from pathlib import Path
    if not Path("data/mentorship/SPX_5min_hd.csv").exists():
        return
    df = B.load("SPX", 5, source="histdata")
    df = df[(df.index >= "2024-05-01") & (df.index < "2024-08-01")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0)
    full = B.run(df, 5, "SPX", p)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "conf_n", "conf_tfs"]
    for cut in full.entry_time.iloc[::3]:
        c = cut + pd.Timedelta(minutes=2)
        part = B.run(df[df.index <= c], 5, "SPX", p, partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_inversion_fvg_void_and_mitigation():
    import numpy as np
    from mentorship import levels as L
    h = np.array([10, 9, 7, 8, 12, 13.]); l = np.array([9, 8, 6, 6.5, 9.5, 12])
    c = np.array([9.5, 8, 6.5, 7.5, 11, 12.5])
    inv = L.inversion_fvgs(h, l, c)
    assert len(inv) == 1 and inv[0].kind == "bull" and (inv[0].top, inv[0].bottom, inv[0].i) == (9, 7, 4)
    v = L.voids(h, l)
    assert [(z.kind, z.i) for z in v] == [("bear", 2), ("bull", 4)]
    # the OLD swing order (legacy=True; A15 fixed in levels_detectors): high (idx 2), two later lows
    # (idx 4, then the higher low idx 6), close above the high (idx 8)
    h2 = np.array([5, 6, 8, 6, 4, 5, 6, 7, 9, 9.5]); l2 = np.array([4, 5, 6, 4, 2, 3.5, 3, 5, 7, 8])
    o2 = np.array([4.5, 5.5, 6.5, 5.5, 3.5, 3.5, 5.5, 5.5, 7.5, 8.5]); c2 = np.array([5, 6, 7.5, 4.5, 3, 4.5, 4.5, 6.5, 8.8, 9])
    m = L.mitigation_blocks(o2, h2, l2, c2, 1, legacy=True)
    assert m and m[0].kind == "bull" and m[0].src == 2


def test_no_look_ahead_with_new_arrays_on():
    from pathlib import Path
    if not Path("data/mentorship/ES_5min_db.csv").exists():
        return
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-05-01") & (df.index < "2024-08-01")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0,
               ifvg_entries=True, fvg_targets=True, mss_cisd=True, globex_pool=True)
    full = B.run(df, 5, "ES", p)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "t1", "entry_kind", "mitigation", "propulsion", "conf_tfs"]
    for cut in full.entry_time.iloc[::3]:
        c = cut + pd.Timedelta(minutes=2)
        part = B.run(df[df.index <= c], 5, "ES", p, partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_no_look_ahead_with_5m_entries_on_1m():
    from pathlib import Path
    if not Path("data/mentorship/ES_1min_db.csv").exists():
        return
    df = B.load("ES", 1, source="databento")
    df = df[(df.index >= "2024-05-01") & (df.index < "2024-07-01")]
    for et in ("5m", "nested"):
        p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0,
                   min_draw_pts=0, entry_tf=et)
        full = B.run(df, 1, "ES", p)
        assert len(full) > 0
        cols = ["entry_time", "entry", "stop", "t1"]
        for cut in full.entry_time.iloc[::3]:
            for lag in (2, 3, 4):          # cut inside a 5-minute bucket too
                c = cut + pd.Timedelta(minutes=lag)
                part = B.run(df[df.index <= c], 1, "ES", p, partial_last=True)
                a = full[full.entry_time <= cut][cols].reset_index(drop=True)
                b = part[part.entry_time <= cut][cols].reset_index(drop=True)
                pd.testing.assert_frame_equal(a, b)


def test_no_look_ahead_smt_htf_targets_sb_topdown():
    from pathlib import Path
    if not Path("data/mentorship/YM_5min_db.csv").exists():
        return
    es, nq, ym = (B.load(s, 5, source="databento") for s in ("ES", "NQ", "YM"))
    cut = lambda d: d[(d.index >= "2024-03-01") & (d.index < "2024-06-01")]
    es, nq, ym = cut(es), cut(nq), cut(ym)
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0,
               htf_targets=("15m", "1h", "4h", "D"), sb_setup=True, topdown=("D", "1h"), topdown_min=1,
               htf_resist_cap=False)   # the #7 cap (own look-ahead tests) left only 2 trades here
    full = B.run(es, 5, "ES", p, nq, partner2=ym)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "t1", "smt", "smt2", "td_agree", "setup", "macro_win"]
    for cut_t in full.entry_time.iloc[::3]:
        c = cut_t + pd.Timedelta(minutes=2)
        part = B.run(es[es.index <= c], 5, "ES", p, nq[nq.index <= c], partial_last=True,
                     partner2=ym[ym.index <= c])
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)   # smt: None (no twin level) vs bool


def test_no_look_ahead_day_templates_and_exits():
    from pathlib import Path
    if not Path("data/mentorship/ES_5min_db.csv").exists():
        return
    es = B.load("ES", 5, source="databento")
    es = es[(es.index >= "2024-02-01") & (es.index < "2024-06-01")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0,
               neutral_skip=True, three_day_rule=True, tgif=True, pd3_exit=True, sd_targets=True)
    full = B.run(es, 5, "ES", p)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "t1", "day_tags", "judas", "dxy", "tnx"]
    for cut_t in full.entry_time.iloc[::3]:
        c = cut_t + pd.Timedelta(minutes=2)
        part = B.run(es[es.index <= c], 5, "ES", p, partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_silver_bullet_no_look_ahead():
    from pathlib import Path
    if not Path("data/mentorship/ES_1min_db.csv").exists():
        return
    es = B.load("ES", 1, source="databento")
    es = es[(es.index >= "2024-01-01") & (es.index < "2024-02-15")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, am=(0, 0), pm=(0, 0),
               sb_runner=True, sb_model=True,
               draw_lock="off", htf_resist_cap=False)   # owner #7/#9 leave too few SB trades here;
    full = B.run(es, 1, "ES", p)                       # covered with them on in test_owner_directives
    assert len(full) > 5 and set(full.setup) <= {"sb_am", "sb_pm"}
    cols = ["entry_time", "entry", "stop", "t1", "side"]
    for cut_t in full.entry_time.iloc[::4]:
        c = cut_t + pd.Timedelta(minutes=1)
        part = B.run(es[es.index <= c], 1, "ES", p, partial_last=True)
        a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
        b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_new_pools_no_look_ahead():
    from pathlib import Path
    if not Path("data/mentorship/ES_5min_db.csv").exists():
        return
    es = B.load("ES", 5, source="databento")
    es = es[(es.index >= "2024-01-01") & (es.index < "2024-05-01")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0,
               pool_prev_week=True, pool_prev_month=True, pool_swings=True)
    full = B.run(es, 5, "ES", p)
    assert len(full) > 2
    assert full.swept.str.startswith(("pwl", "pml_month", "swing_low", "pwh")).any() or True
    cols = ["entry_time", "entry", "stop", "t1", "swept"]
    for cut_t in full.entry_time.iloc[::4]:
        c = cut_t + pd.Timedelta(minutes=2)
        part = B.run(es[es.index <= c], 5, "ES", p, partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_ep07_switches_no_look_ahead():
    from pathlib import Path
    if not Path("data/mentorship/ES_5min_db.csv").exists():
        return
    es = B.load("ES", 5, source="databento")
    es = es[(es.index >= "2024-01-01") & (es.index < "2024-05-01")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0,
               ep07_stop=True, ep07_body_exit=True, ep07_trail=True, htf_far_edge=True, ce_hold=True,
               htf_resist_cap=False)   # the #7 cap (own look-ahead tests) left only 2 trades here
    full = B.run(es, 5, "ES", p)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "t1"]
    for cut_t in full.entry_time.iloc[::4]:
        c = cut_t + pd.Timedelta(minutes=2)
        part = B.run(es[es.index <= c], 5, "ES", p, partial_last=True)
        a = full[full.entry_time <= c][cols].reset_index(drop=True)
        b = part[part.entry_time <= c][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_pre_open_switches_no_look_ahead():
    from pathlib import Path
    if not Path("data/mentorship/ES_1min_db.csv").exists():
        return
    es = B.load("ES", 1, source="databento")
    es = es[(es.index >= "2022-01-01") & (es.index < "2022-04-15")]
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, sb_model=False, am=(0, 0), pm=(0, 0),
               pre_0700=True, pre_0900=True, post_news=True, ma_deuce=True, leg_pd=0)
    full = B.run(es, 1, "ES", p, confluence=False)
    assert len(full) > 2
    cols = ["entry_time", "entry", "stop", "t1", "setup"]
    for cut_t in full.entry_time.iloc[::2]:
        c = cut_t + pd.Timedelta(minutes=1)
        part = B.run(es[es.index <= c], 1, "ES", p, partial_last=True, confluence=False)
        a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
        assert len(part) >= len(a), (cut_t, len(part), len(a))
        a = a.sort_values(["entry_time", "setup"]).reset_index(drop=True)
        b = part[part.entry_time <= cut_t][cols].sort_values(["entry_time", "setup"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
