"""Caption-gap pass, package bias_htf#7/7: defaults / validation / study variants / bx configuration, the TABLE-SIDE functions of bh7.py (range quadrant, flip turn, 1h sponsorship, array lost, breaker
regime, the IPDA true day, the raw front-month series) and the STUDY-ONLY functions (bh7s.py One Shot One Kill, swing re-entry, trend tired, frequency flags, the OSOK scale-in, the swing re-add, the daily
stop model, htf.swing_stop; stocks.py / stocks_watch.py) on hand-made books. Pure functions, no market data, nothing platform specific, no file written outside the repo."""
import inspect
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh2 as BH2, bh7 as BH7, bh7s as S7, bias_htf as BX, htf, study, stocks as ST, stocks_watch as SW
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr as harr  # noqa: E402

NY = "America/New_York"
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)

NEW_FIELDS = ("weekly_flip_follow", "pd_subrange", "pd_top_skip", "wr15_tag", "wr_lookback", "array_lost_flip", "london_breaker_bias", "london_confirm", "true_day", "late_obj_k", "cc_daytrade",
              "london_dir_gate", "london_dir_tag", "htf_series", "htf_monthly_series", "stocks_mode", "stock_piv_n", "stock_match_days", "stock_excl_2017", "stock_near_high_pct", "stock_ext_atr",
              "stock_rs_min", "stock_top_sectors")
KNOBS = {"pd_top_skip", "wr_lookback", "stock_piv_n", "stock_match_days", "stock_excl_2017", "stock_near_high_pct", "stock_ext_atr", "stock_rs_min", "stock_top_sectors", "late_obj_k"}
OFF = {"weekly_flip_follow": False, "pd_subrange": False, "wr15_tag": False, "array_lost_flip": False, "london_breaker_bias": False, "london_confirm": "off", "true_day": "session", "cc_daytrade": False,
       "london_dir_gate": False, "london_dir_tag": False, "htf_series": "adjusted", "htf_monthly_series": "adjusted", "stocks_mode": False, "late_obj_k": 1.0}


def T(s):
    return pd.Timestamp(s, tz=NY)


def daily(rows, start="2026-01-05"):
    idx = pd.date_range(start, periods=len(rows), freq="B")
    return pd.DataFrame([list(map(float, r)) for r in rows], columns=["open", "high", "low", "close"], index=idx)


# --- defaults, validation, configuration -------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert p.pd_top_skip is True and p.wr_lookback == 20 and p.stock_rs_min == 80.0 and p.stock_top_sectors == 2 and p.stock_near_high_pct == 0.05 and p.stock_ext_atr == 3.0
    assert p.sb_model is False and p.sb_use_bias == Params().sb_use_bias and p.want_all_engines == Params().want_all_engines
    for bad in (dict(london_confirm="x"), dict(true_day="x"), dict(htf_series="x"), dict(htf_monthly_series="contract"), dict(late_obj_k=0.0), dict(late_obj_k=1.5), dict(wr_lookback=1),
                dict(stock_rs_min=101.0), dict(stock_top_sectors=0), dict(stock_ext_atr=0.0)):
        with pytest.raises(ValueError):
            Params(**bad)
    Params(htf_bias="h1_sponsor")
    Params(htf_bias="breaker")
    assert BX is not None


def test_bx_configuration_is_empty_by_default_and_names_the_columns():
    assert Params().bx == ""
    assert BH7.bx_cfg(Params()) == {}
    c = BH7.bx_cfg(Params(htf_bias="h1_sponsor", pd_subrange=True, weekly_flip_follow=True, array_lost_flip=True, true_day="ipda", htf_series="raw"))
    assert c == dict(rq=60, ft=1, h1=1, al=1, td=1, hs="raw")
    assert BH7.bx_cfg(Params(htf_bias="breaker")) == dict(br=1)
    assert BH7.bx_cfg(Params(htf_monthly=True, htf_monthly_series="raw")) == dict(ms="raw")
    assert BH7.bx_cfg(Params(htf_monthly_series="raw")) == {}                     # the monthly arrays are off: nothing to draw on the raw series
    assert '"b7"' in Params(htf_bias="breaker").bx
    from mentorship import bias_day as BD
    assert BD.bias_col(Params(htf_bias="breaker")) == "brk_react" and BD.bias_col(Params(htf_bias="h1_sponsor")) == "h1_sponsor"


def test_study_variants_build_and_are_named_by_gap_id():
    from dataclasses import replace
    names = set(study._BH7_DECISIONS)
    gap_ids = ("new-after-of-shift-sell-any-premium-array", "A21-longs-above-eq-subrange-discount", "B6-intraweek-reversal-1h-confirmation", "B20-15m-williams-r-entry",
               "new-stopout-at-planned-array-next-day-flip", "new-london-breaker-precursor", "OT-htf-array-data-series", "new-london-confirm-after-daily-signal", "new-ipda-true-day",
               "new-ny-continues-london", "T13-po3-breaker-regime")
    for g in gap_ids:
        assert any(n.startswith(g) for n in names), g
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for n, kw in study._BH7_DECISIONS.items():
            p = replace(Params(), **kw)
            assert p.sb_model is False
            assert study.DECISIONS[n] == kw
    for f in ("osok_study", "swing_reentry_study", "trend_tired_study", "position_freq_study", "swing_frequency_study", "osok_scale_in", "swing_readd", "daily_stop_model", "stock_watchlist",
              "stock_sell_list", "stock_jan_study", "stock_mega", "osok_origin_report"):
        assert callable(getattr(study, f))


# --- table side ------------------------------------------------------------------------------------------------------------------------

def test_range_columns_and_quadrant():
    n = 30
    o = np.linspace(100, 130, n)
    c = o + 0.5
    ks = np.array([12, 29])
    r = BH7.range_columns(o, c, ks, 60)
    assert r["range_lo"][1] == pytest.approx(o[:29].min()) and r["range_hi"][1] == pytest.approx(c[:29].max())     # completed sessions only: k-n .. k-1
    assert r["range_q"][1] == 4                                                  # the prior close sits at the top of the range
    assert BH7.quadrant(104.0, 100.0, 120.0) == 1 and BH7.quadrant(111.0, 100.0, 120.0) == 3 and BH7.quadrant(125.0, 100.0, 120.0) == 4 and BH7.quadrant(90.0, 100.0, 120.0) == 1
    assert BH7.quadrant(1.0, 5.0, 5.0) == 0
    few = BH7.range_columns(o, c, np.array([5]), 60)
    assert few["range_q"][0] == 0 and few["range_lo"][0] != few["range_lo"][0]    # fewer than 10 sessions: no range


def test_flip_turn_column():
    d = dsess([(100, 101, 99, 100)] * 15)
    ks = np.arange(10)
    flip = np.array([0, 0, 0, 0, 0, 0, -1, -1, -1, 1])           # week 1: rows 0-4; week 2: rows 5-9 (flip turns -1 on row 6, +1 on row 9)
    out = BH7.flip_turn_column(flip, ks, d)
    assert list(out) == [0, 0, 0, 0, 0, 0, -1, -1, -1, 1]
    assert list(BH7.flip_turn_column(np.array([-1] * 10), ks, d)) == [0] * 10           # the state was already -1 at the week's open: it did not turn inside the week


def test_array_lost_columns():
    # bullish daily FVG [101, 103] (day 2's gap); day 6 opens at 108 and closes at 100.5 through it: the planned support is lost; the next lower array is a bullish FVG [91, 93]
    rows = [(100, 101, 99, 100.5), (100.5, 106, 100.5, 105), (105, 107, 103, 106), (106, 107, 105, 106.5), (106.5, 108, 105, 107), (107, 108.5, 106, 107.5), (108, 109, 100, 100.5), (100.5, 102, 99, 101)]
    d = daily(rows)
    arrs = [htf.Arr("bull", "fvg", "D", 103.0, 101.0, 102.0, 3), htf.Arr("bull", "fvg", "D", 93.0, 91.0, 92.0, 1)]
    ks = np.array([6, 7])
    r = BH7.array_lost_columns(d, arrs, ks)
    assert list(r["array_lost"]) == [0, 1]                                            # row 6 sees session 5 (still holding); row 7 sees session 6 close through the array
    assert r["array_lost_tgt"][1] == 93.0 and r["array_lost_tgt"][0] != r["array_lost_tgt"][0]
    rows2 = [(120 - a, 120 - c, 120 - b, 120 - dd) for a, b, c, dd in rows]
    r2 = BH7.array_lost_columns(daily(rows2), [htf.Arr("bear", "fvg", "D", 19.0, 17.0, 18.0, 3), htf.Arr("bear", "fvg", "D", 29.0, 27.0, 28.0, 1)], ks)
    assert list(r2["array_lost"]) == [0, -1] and r2["array_lost_tgt"][1] == 27.0                    # the mirror: the bottom of the next higher bearish array


def test_breaker_react_column():
    """Daily series with a bearish breaker retested and rejected: brk_react = -1 the next day; a bullish breaker rejected flips it to +1."""
    rows = [
        (100.0, 100.6, 99.6, 100.2), (100.2, 100.4, 99.2, 99.4), (99.4, 99.5, 98.5, 98.7), (98.7, 99.6, 98.9, 99.5), (99.5, 100.5, 99.4, 100.4), (100.4, 101.5, 100.3, 101.3),
        (101.3, 101.2, 100.2, 100.4), (100.4, 100.6, 99.6, 99.8), (99.8, 100.0, 97.8, 98.0), (98.0, 98.6, 97.9, 98.5), (98.5, 99.4, 98.4, 99.3), (99.3, 102.2, 99.2, 102.0),
        (102.0, 102.4, 101.8, 102.2), (102.2, 102.5, 101.9, 102.3), (102.3, 102.6, 102.0, 102.4),
        (102.4, 101.5, 100.0, 100.2),      # touches the bullish breaker [100.3, 101.5] and closes UNDER it: not a reaction away (the bullish zone is lost)
    ]
    d = daily(rows)
    ks = np.arange(len(rows))
    # a bullish breaker known at row 11; a daily touch of it that closes away (above its top) = a bullish reaction
    rows2 = rows[:12] + [(102.0, 102.4, 101.8, 102.2), (102.2, 102.5, 100.8, 102.3), (102.3, 103.0, 102.0, 102.9)]
    d2 = daily(rows2)
    r2 = BH7.breaker_react_column(d2, np.arange(len(rows2)))
    assert list(r2[:13]) == [0] * 13 and r2[14] == 1                                  # the touch at session 13 (low 100.8 <= 101.5, close 102.3 > 101.5) rules from row 14
    r1 = BH7.breaker_react_column(d, ks)
    assert set(r1) <= {0, 1, -1}
    mirror = [(200.0 - a, 200.0 - c, 200.0 - b, 200.0 - dd) for a, b, c, dd in rows2]
    r3 = BH7.breaker_react_column(daily(mirror), np.arange(len(rows2)))
    assert r3[14] == -1 and list(r3[:13]) == [0] * 13                                  # the bearish breaker retested and rejected: -1 the next day


def _frame5(day_, rows, start="00:00"):
    idx = pd.date_range(pd.Timestamp(f"{day_} {start}", tz=NY), periods=len(rows), freq="5min")
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3], "volume": 1.0}, index=idx)


def test_true_day_ohlc():
    """A day with a 15:30 high: with the IPDA true day (00:00-15:00) the daily high excludes it."""
    out = []
    for dd, spike in (("2026-03-09", None), ("2026-03-10", 186)):
        rows = [(100.0, 100.2, 99.8, 100.0)] * 195
        if spike is not None:
            rows[spike] = (100.0, 110.0, 99.9, 100.0)                                 # 15:30
        out.append(_frame5(dd, rows))
    df = pd.concat(out)
    full = htf.sessions(df)
    tru = BH7.sessions_true_day(df)
    assert float(full.high.iloc[1]) == 110.0
    assert float(tru.high.iloc[1]) == pytest.approx(100.2) and float(tru.low.iloc[1]) == pytest.approx(99.8)
    assert tru.open.iloc[1] == 100.0 and len(tru) == 2
    # the open is the first bar at / after 00:00, the close the last bar ending at / before 15:00 (14:55 start)
    rows = [(float(k), float(k) + 1.0, float(k) - 1.0, float(k) + 0.5) for k in range(195)]
    t2 = BH7.sessions_true_day(_frame5("2026-03-11", rows))
    assert t2.open.iloc[0] == 0.0 and t2.close.iloc[0] == 179.5


def test_true_day_in_the_table_changes_the_daily_candle():
    from test_caption_gap_bh1c import fut_walk
    df = fut_walk("2025-12-01", "2026-03-27", seed=3, vol=0.9)
    p0, p1 = Params(**FUT, htf_bias="combo"), Params(**FUT, htf_bias="combo", true_day="ipda")
    n0 = BH2.HITS["sw_true_day"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = htf.table(df, p0.es_pt, vi=p0.vi_arrays, flip_triggers=p0.flip_triggers, **__import__("mentorship.backtest", fromlist=["x"]).table_kw(p0))
        b = htf.table(df, p1.es_pt, vi=p1.vi_arrays, flip_triggers=p1.flip_triggers, **__import__("mentorship.backtest", fromlist=["x"]).table_kw(p1))
    assert len(a) and len(b) and BH2.HITS["sw_true_day"] > n0
    assert not a[["draw", "react"]].equals(b[["draw", "react"]]) or not a.px.equals(b.px) or len(a) != len(b)


# --- OT-htf-array-data-series -------------------------------------------------------------------------------------------------------------

def test_adj_before_reads_only_bars_before_the_cut():
    idx = pd.date_range(T("2026-03-09 00:00"), periods=60, freq="5min")
    adj = pd.Series([10.0] * 30 + [0.0] * 30, index=idx)                                # a roll at 02:30
    assert BH7.adj_before(adj, pd.Timestamp("2026-03-09"), idx.tz, cut_min=120, bm=5) == 10.0         # 02:00 cut: the last closed bar is 01:55
    assert BH7.adj_before(adj, pd.Timestamp("2026-03-09"), idx.tz, cut_min=150, bm=5) == 10.0         # 02:30 cut: bar 02:25 is the last closed (still the old contract)
    assert BH7.adj_before(adj, pd.Timestamp("2026-03-09"), idx.tz, cut_min=155, bm=5) == 0.0
    assert BH7.adj_before(None, pd.Timestamp("2026-03-09"), idx.tz) == 0.0


def test_htf_series_raw_maps_by_adj():
    """A synthetic series with a +10 roll: the raw table (the unadjusted series, roll gap in) mapped back by the adj agrees with the adjusted table on the rows before the roll and puts a level formed BEFORE
    the roll 10 pts lower after it; a level formed after the roll is identical."""
    from test_caption_gap_bh1c import fut_walk
    from mentorship import backtest as B
    df = fut_walk("2025-11-03", "2026-03-27", seed=5, vol=0.9)
    roll = pd.Timestamp("2026-02-02", tz=NY)
    adj = pd.Series(np.where(df.index < roll, 10.0, 0.0), index=df.index)
    raw = df.copy()
    for k in ("open", "high", "low", "close"):
        raw[k] = df[k] - adj
    p = Params(**FUT, htf_series="raw", htf_bias="combo")
    pa = Params(**FUT, htf_bias="combo")
    n0 = BH2.HITS["sw_htf_series_raw"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ta = htf.table(df, pa.es_pt, vi=pa.vi_arrays, flip_triggers=pa.flip_triggers, **B.table_kw(pa))
        tr = htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p, raw, adj))
    assert BH2.HITS["sw_htf_series_raw"] > n0 and "adj_map" in tr
    before = [x for x in ta.index if pd.Timestamp(x) < pd.Timestamp("2026-02-02")]
    assert len(before) > 20
    cols = [c for c in ("px", "draw_up", "draw_dn") if c in tr]
    for c in cols:
        a_, r_ = ta.loc[before, c].values.astype(float), tr.loc[before, c].values.astype(float)
        ok = np.isfinite(a_) & np.isfinite(r_)
        assert np.allclose(a_[ok], r_[ok]), c                                           # one uniform shift before the roll: mapped back it IS the adjusted level
    after = [x for x in ta.index if pd.Timestamp(x) >= pd.Timestamp("2026-02-09")]
    d_up = (ta.loc[after, "draw_up"].values.astype(float) - tr.loc[after, "draw_up"].values.astype(float))
    d_up = d_up[np.isfinite(d_up)]
    assert len(d_up) > 5
    assert (np.isclose(d_up, 10.0, atol=1e-6)).any(), "a level formed before the roll must sit 10 pts lower in the raw table"
    assert (np.isclose(d_up, 0.0, atol=1e-6)).any(), "a level formed after the roll must be identical"
    assert np.allclose(ta.loc[after, "px"].values.astype(float), tr.loc[after, "px"].values.astype(float))          # the observed price maps exactly
    # contract / missing raw
    with pytest.raises(NotImplementedError):
        htf.table(df, 1.0, bx=Params(**FUT, htf_series="contract", htf_bias="combo").bx)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t_fb = htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))                    # no raw frame given: the adjusted table
    assert t_fb.px.equals(ta.px)


def test_raw_series_warns_and_falls_back_without_meta():
    from mentorship import backtest as B
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        r, a = B.raw_series(Params(htf_series="raw"), "SPX", 5, None)
    assert r is None and a is None and any("adjusted frame" in str(x.message) for x in w)
    assert B.raw_series(Params(), "ES", 5, None) == (None, None)


def test_htf_monthly_known_next_day():
    """An 'M' array's `known` is the first session of the next month (also for the arrays drawn on the raw series)."""
    from test_caption_gap_bh1c import fut_walk
    df = fut_walk("2025-09-01", "2026-03-27", seed=9, vol=1.2)
    d = htf.sessions(df)
    pos = {t: k for k, t in enumerate(d.index)}
    mth = htf.months(d)
    arrs = BH7.monthly_raw_arrays(df, d, pos, lambda *a: htf._arrays(*a, False, False, 0.0, True, False), ())
    assert arrs and all(getattr(a, "rawk", False) and a.tf == "M" for a in arrs)
    firsts = {pos[t] + 1 for t in mth["last"]}
    assert {a.known for a in arrs} <= firsts
    k = min(a.known for a in arrs)
    assert d.index[k].month != d.index[k - 1].month                                    # the session it becomes known is the first of the next month
    sh = BH7.shifted(arrs[0], 10.0)
    assert sh.top == arrs[0].top + 10.0 and sh.bottom == arrs[0].bottom + 10.0 and sh.ce == arrs[0].ce + 10.0 and sh.known == arrs[0].known


def test_price_like_columns():
    t = pd.DataFrame({"px": [4000.0, 4010.0], "draw_up": [4050.0, 4060.0], "react_score": [1.5, 0.5], "n": [1, 2], "adr": [50.0, 52.0]})
    assert BH7.price_like_columns(t) == ["px", "draw_up"]


# --- B6-intraweek-reversal-1h-confirmation ---------------------------------------------------------------------------------------------

def _h1(rows):
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_h1_sponsorship_column():
    """+1 after a 1h close breaks the latest short-term swing high that preceded the low, kept while every later bullish 1h OB holds on a body-close basis at its MT; a failed OB turns it off; the
    bearish mirror."""
    rows = [(100, 101, 99.5, 100.5), (100.5, 102.5, 100.2, 102.0), (102.0, 102.2, 101.0, 101.2), (101.2, 101.4, 99.0, 99.2), (99.2, 99.6, 97.0, 97.4), (97.4, 98.4, 97.2, 98.2),
            (98.2, 98.6, 97.9, 98.4), (98.4, 103.0, 98.3, 102.8), (102.8, 103.4, 102.0, 102.2), (102.2, 105.0, 102.1, 104.8), (104.8, 105.0, 103.9, 104.2)]
    o, h, l, c = _h1(rows)
    # the low (97.0) is bar 4; the latest 3-bar swing high confirmed before it is bar 1 (102.5); bar 7 closes 102.8 above it
    assert BH7.sponsor_state(o, h, l, c, 4, 1, 6) == 0                                 # not yet broken
    assert BH7.sponsor_state(o, h, l, c, 4, 1, 7) == 1                                 # broken
    assert BH7.sponsor_state(o, h, l, c, 4, 1, 10) == 1                                # the down-close bar 8 (OB 102.0-102.4?) and bar 10 hold above the MT
    bad = [r for r in rows]
    bad[10] = (104.8, 105.0, 99.0, 99.5)                                               # a later body close under the MT of the OB formed by bars 8-9
    ob, hb, lb, cb = _h1(bad)
    assert BH7.sponsor_state(ob, hb, lb, cb, 4, 1, 10) == 0
    mo, mh, ml, mc = (200 - x for x in (o, l, h, c))                                   # the mirror: a high with a bearish break
    assert BH7.sponsor_state(mo, mh, ml, mc, 4, -1, 10) == 1


# --- OT-htf: tools per timeframe guard -----------------------------------------------------------------------------------------------------

def test_htf_weekly_ignores_time_of_day():
    """The weekly / monthly bias columns do not depend on the intraday session parameters (or_minutes, am, pm, london_kz_start): the table inputs are the same."""
    from test_caption_gap_bh1c import fut_walk
    from mentorship import backtest as B
    df = fut_walk("2025-11-03", "2026-02-27", seed=4, vol=0.9)
    base = dict(**FUT, htf_bias="wk", htf_monthly=True)
    pa = Params(**base)
    pb = Params(**base, or_minutes=60, am=(540, 700), pm=(840, 930), london_kz_start=60)
    assert B.table_kw(pa) == B.table_kw(pb) and pa.bx == pb.bx
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ta = htf.table(df, pa.es_pt, vi=pa.vi_arrays, flip_triggers=pa.flip_triggers, **B.table_kw(pa))
        tb = htf.table(df, pb.es_pt, vi=pb.vi_arrays, flip_triggers=pb.flip_triggers, **B.table_kw(pb))
    cols = [c for c in ta.columns if c.startswith("wk") or c in ("mob", "m_ctrl")] or ["wk_bias"]
    pd.testing.assert_frame_equal(ta[cols], tb[cols])
    assert "wk_bias" in ta


# --- One Shot One Kill ----------------------------------------------------------------------------------------------------------------------

def h1(rows, start="2026-03-02 09:00"):
    a = np.array(rows, float)
    idx = pd.date_range(T(start), periods=len(a), freq="60min")
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}, index=idx)


SHORT_ROWS = ([(100, 101, 99.5, 100.5), (100.5, 103, 100.2, 102.8), (102.8, 106, 102.5, 105.8), (105.8, 108.2, 107.0, 107.4), (107.4, 107.5, 105.8, 106.0), (106.0, 106.0, 104.5, 104.8),
               (105.0, 106.7, 104.8, 105.2)]
              + [(105.2 - 2.5 * k, 105.4 - 2.5 * k, 103.0 - 2.5 * k, 103.2 - 2.5 * k) for k in range(0, 6)])
ARR_OK = [S7.arr("W", "bear", 110.0, 105.0, T("2026-02-27 17:00")), S7.arr("D", "bull", 92.0, 90.0, T("2026-02-27 17:00")), S7.arr("W", "bull", 82.0, 80.0, T("2026-02-27 17:00"))]


def test_osok_1h_execution():
    """A bearish monthly frame: a 1h bearish FVG completes INSIDE a weekly premium array on Monday; the sell limit at its CE fills the next bar, the stop sits above the weekly array, the daily discount
    array is the target. The seven bars after the fill run down to it."""
    tr = S7.osok_core(h1(SHORT_ROWS), ARR_OK, -1)
    assert len(tr) == 1
    t = tr[0]
    assert t["side"] == -1 and t["entry"] == pytest.approx(106.5) and t["stop"] == pytest.approx(110.0) and t["target"] == pytest.approx(92.0)
    assert t["exit_reason"] == "target" and t["origin_tf"] == "W" and t["seq"] == 1 and t["htf"] == (105.0, 110.0)
    assert t["r"] == pytest.approx((106.5 - 92.0) / 3.5)
    # Mon-Wed only: the same bars on a Thursday arm nothing
    assert S7.osok_core(h1(SHORT_ROWS, "2026-03-05 09:00"), ARR_OK, -1) == []
    # the 1h FVG must sit inside a live HTF array
    far = [S7.arr("W", "bear", 125.0, 120.0, T("2026-02-27 17:00"))] + ARR_OK[1:]
    assert S7.osok_core(h1(SHORT_ROWS), far, -1) == []
    # an array that is not yet known is not used (no look-ahead)
    late = [S7.arr("W", "bear", 110.0, 105.0, T("2026-03-02 16:00"))] + ARR_OK[1:]
    assert S7.osok_core(h1(SHORT_ROWS), late, -1) == []
    # no target array: no trade
    assert S7.osok_core(h1(SHORT_ROWS), ARR_OK[:1], -1) == []
    # 1h arrays alone execute inside a kill zone (the first FVG candle starts 12:00 = outside; moved to 07:00 it is inside)
    only1h = S7.osok_core(h1(SHORT_ROWS, "2026-03-02 04:00"), ARR_OK[1:], -1, h1_alone=True)
    assert only1h and only1h[0]["origin_tf"] == "1h"
    assert S7.osok_core(h1(SHORT_ROWS, "2026-03-02 04:00"), ARR_OK[1:], -1, h1_alone=False) == []
    assert S7.osok_core(h1(SHORT_ROWS, "2026-03-02 09:00"), ARR_OK[1:], -1, h1_alone=True) == []                  # the FVG's first candle starts at 12:00: outside the kill zones
    # the bullish mirror
    mir = h1([(200 - a, 200 - c, 200 - b, 200 - d) for a, b, c, d in SHORT_ROWS])
    arrm = [S7.arr(a["tf"], "bull" if a["kind"] == "bear" else "bear", 200 - a["bottom"], 200 - a["top"], a["t_known"]) for a in ARR_OK]
    tm = S7.osok_core(mir, arrm, 1)
    assert len(tm) == 1 and tm[0]["side"] == 1 and tm[0]["entry"] == pytest.approx(93.5) and tm[0]["target"] == pytest.approx(108.0) and tm[0]["exit_reason"] == "target"


def test_osok_weekly_to_daily_target():
    """The target is the nearest UNTOUCHED daily opposing array (172: 'W' picks the weekly one)."""
    near = [S7.arr("D", "bull", 92.0, 90.0, T("2026-02-27 17:00")), S7.arr("D", "bull", 82.0, 80.0, T("2026-02-27 17:00"))]
    tr = S7.osok_core(h1(SHORT_ROWS), ARR_OK[:1] + near, -1)
    assert tr and tr[0]["target"] == pytest.approx(92.0)
    tr2 = S7.osok_core(h1(SHORT_ROWS), ARR_OK[:1] + near[1:], -1)
    assert tr2 and tr2[0]["target"] == pytest.approx(82.0)
    # a daily array price already traded into before the setup is not an untouched objective
    touched = h1([(98, 99, 91.0, 98.5)] + SHORT_ROWS[1:], "2026-03-02 09:00")
    assert S7.osok_core(touched, ARR_OK[:2], -1) == []
    tw = S7.osok_core(h1(SHORT_ROWS), ARR_OK, -1, target_tf="W")
    assert tw and tw[0]["target"] == pytest.approx(82.0) and tw[0]["exit_reason"] == "week_end"          # the weekly objective is not reached inside the data: flat by the week's last bar


def test_osok_missed_monthly_only_sets_the_direction():
    """173: when the price already left the monthly origin array, the monthly array sets the direction only - entries use W / D / 4h arrays."""
    mon = [S7.arr("M", "bear", 110.0, 105.0, T("2026-02-27 17:00"))] + ARR_OK[1:]
    live = S7.osok_core(h1(SHORT_ROWS), mon, lambda t: (-1, False))
    assert live and live[0]["origin_tf"] == "M"
    missed = S7.osok_core(h1(SHORT_ROWS), mon, lambda t: (-1, True))
    assert missed == []
    with_w = S7.osok_core(h1(SHORT_ROWS), mon + [S7.arr("W", "bear", 110.0, 105.0, T("2026-02-27 17:00"))], lambda t: (-1, True))
    assert with_w and with_w[0]["origin_tf"] == "W"
    assert S7.osok_core(h1(SHORT_ROWS), ARR_OK, lambda t: 0) == []                       # no frame direction: nothing


def test_osok_origin_tag():
    """A weekly-origin leg with two signals before the target counts 2 for 'W'."""
    legW = ("W", 105.0, 110.0)
    trades = [dict(origin_tf="W", leg=legW, exit_reason="stop"), dict(origin_tf="W", leg=legW, exit_reason="target"), dict(origin_tf="4h", leg=("4h", 1.0, 2.0), exit_reason="target"),
              dict(origin_tf="W", leg=legW, exit_reason="stop")]
    rep = S7.origin_report(trades)
    assert rep["W"]["per_leg"] == [2, 1] and rep["W"]["signals"] == 3 and rep["W"]["legs"] == 2
    assert rep["4h"]["per_leg"] == [1] and rep["4h"]["mean_per_leg"] == 1.0 and rep["M"]["legs"] == 0 and rep["M"]["mean_per_leg"] != rep["M"]["mean_per_leg"]
    assert rep["W"]["mean_per_leg"] == 1.5
    assert study.osok_origin_report(trades)["W"]["signals"] == 3
    # the engine's own sequence counter: a stopped trade then a target trade from the same origin array -> seq 1, 2
    rows = SHORT_ROWS[:6] + [(105.0, 106.7, 104.8, 105.2), (105.2, 111.0, 105.0, 110.5)]                   # the stop at 110 is hit after the fill
    s1 = S7.osok_core(h1(rows), ARR_OK, -1)
    assert s1 and s1[0]["exit_reason"] == "stop" and s1[0]["seq"] == 1


def test_osok_smoke():
    from test_caption_gap_bh1c import fut_walk
    df = fut_walk("2025-10-06", "2026-02-27", seed=3, vol=1.5)
    arrays = S7.build_arrays(df)
    assert {"D", "W", "M", "4h"} >= {a["tf"] for a in arrays} and any(a["tf"] == "4h" for a in arrays) and any(a["tf"] == "W" for a in arrays)
    assert all(isinstance(a["t_known"], pd.Timestamp) for a in arrays)
    f = S7.monthly_direction(arrays, df)
    assert f(T("2025-10-20 10:00")) == (0, False)                                        # no completed month yet
    d, m = f(T("2026-02-20 10:00"))
    assert d in (-1, 0, 1) and isinstance(m, bool)
    tr = study.osok_study(df, direction=-1, min_rr=0.5)
    assert isinstance(tr, list)
    for t in tr:
        assert t["side"] == -1 and t["t_out"] >= t["t_in"] and t["origin_tf"] in ("M", "W", "D", "4h", "1h")
        assert t["exit_reason"] in ("stop", "target", "week_end") and t["stop"] > t["entry"]


# --- X13 swing re-entry / trend tired --------------------------------------------------------------------------------------------------

def h4(rows, start="2026-03-02 00:00"):
    a = np.array(rows, float)
    idx = pd.date_range(T(start), periods=len(a), freq="4h")
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3]}, index=idx)


K0 = T("2026-02-27 17:00")
ARR_RE = [S7.arr("4h", "bull", 102.0, 100.0, K0), S7.arr("4h", "bull", 98.0, 96.0, K0), S7.arr("D", "bull", 92.0, 90.0, K0), S7.arr("D", "bear", 122.0, 120.0, K0)]


def test_swing_reentry_cascade():
    """A failed 4H array long picks the next lower 4H array, and with none falls to the daily array; the failed array is never reused."""
    pick = S7.pick_reentry(ARR_RE, [ARR_RE[0]], 100.0, T("2026-03-03 00:00"))
    assert pick is ARR_RE[1]
    pick2 = S7.pick_reentry(ARR_RE, [ARR_RE[0], ARR_RE[1]], 96.0, T("2026-03-03 00:00"))
    assert pick2 is ARR_RE[2]                                                          # no lower 4h array: the daily one
    mw = ARR_RE + [S7.arr("W", "bull", 89.0, 85.0, K0), S7.arr("M", "bull", 84.0, 70.0, K0)]
    assert S7.pick_reentry(mw, ARR_RE[:3], 90.0, T("2026-03-03 00:00"))["tf"] == "W"          # then weekly, then monthly
    assert S7.pick_reentry(mw[:3], ARR_RE[:3], 90.0, T("2026-03-03 00:00")) is None
    assert S7.pick_reentry(ARR_RE, [], 100.0, T("2026-02-20 00:00")) is None            # nothing known yet
    # the whole cascade on 4h bars: attempt 0 stops, attempt 1 (half size, the lower array) reaches the daily bearish array above
    rows = ([(106, 107, 105, 106)] * 3 + [(106, 106.5, 100.8, 101.2), (101.2, 103, 100.4, 102), (102, 102.5, 99.5, 99.8), (99.8, 100, 97.5, 98.2), (98.2, 98.5, 96.8, 97.6)]
            + [(97.6 + 3 * k, 99 + 3 * k, 97 + 3 * k, 98.5 + 3 * k) for k in range(0, 9)])
    res = S7.swing_reentry_study(h4(rows), ARR_RE, min_rr=3.0)
    assert [r["attempt"] for r in res] == [0, 1] and res[0]["exit_reason"] == "stop" and res[1]["exit_reason"] == "target"
    assert res[0]["array"] is not res[1]["array"] and res[1]["size"] == 0.5 and res[1]["pnl_r"] == pytest.approx(0.5 * res[1]["r"])
    assert res[0]["array"]["top"] == 102.0 and res[1]["array"]["top"] == 98.0
    rep = S7.reentry_report(res)
    assert rep[0]["n"] == 1 and rep[0]["hit_rate"] == 0.0 and rep[1]["hit_rate"] == 1.0 and rep[1]["recovered"] == 1.0 and rep[0]["recovered"] == 0.0
    # reentry_max=0 stops after the first failure
    one = S7.swing_reentry_study(h4(rows), ARR_RE, reentry_max=0, min_rr=3.0)
    assert len(one) == 1 and one[0]["exit_reason"] == "stop"
    # a bearish bias trades nothing
    assert S7.swing_reentry_study(h4(rows), ARR_RE, bias=-1) == []
    # the void: a 4h body close under the far edge of the weekly array under the entry ends the sequence (the original reasons are gone)
    rows_v = rows[:6] + [(99.8, 100, 93.0, 94.0)] + rows[7:]
    voided = S7.swing_reentry_study(h4(rows_v), ARR_RE + [S7.arr("W", "bull", 96.5, 95.0, K0)], min_rr=3.0)
    assert len(voided) == 1 and voided[0]["exit_reason"] == "stop"
    kept = S7.swing_reentry_study(h4(rows_v), ARR_RE + [S7.arr("W", "bull", 96.5, 95.0, K0)], min_rr=3.0, void="none")
    assert len(kept) >= 1
    assert study.swing_reentry_study(h4(rows), ARR_RE, min_rr=3.0)[0]["attempt"] == 0


def test_trend_tired_flag():
    """Signal list win, loss, loss -> flag set after the second loss; a win in between resets the count."""
    sig = [dict(date=pd.Timestamp("2026-01-05"), win=True), dict(date=pd.Timestamp("2026-01-20"), win=False), dict(date=pd.Timestamp("2026-02-03"), win=False),
           dict(date=pd.Timestamp("2026-02-17"), win=True), dict(date=pd.Timestamp("2026-03-03"), win=False), dict(date=pd.Timestamp("2026-03-17"), win=True), dict(date=pd.Timestamp("2026-04-01"), win=False)]
    r = S7.trend_tired(sig)
    assert r["flags"] == [pd.Timestamp("2026-02-03")] and len(r["kept"]) == 7 and r["skipped"] == []
    assert S7.trend_tired(sig[:2])["flags"] == []
    assert S7.trend_tired(sig, tired_n=1)["flags"] == [sig[1]["date"], sig[2]["date"], sig[4]["date"], sig[6]["date"]]
    flip = pd.Series([1, 1, -1], index=pd.to_datetime(["2026-01-01", "2026-02-10", "2026-03-10"]))
    p = S7.trend_tired(sig, tired_pause=True, flip=flip)
    assert [s["date"] for s in p["skipped"]] == [pd.Timestamp("2026-02-17"), pd.Timestamp("2026-03-03")]          # paused until the flip column changes (on 03-10)
    assert [s["date"] for s in p["kept"]][-2:] == [pd.Timestamp("2026-03-17"), pd.Timestamp("2026-04-01")]
    closes = pd.Series(np.linspace(100, 160, 80), index=pd.bdate_range("2026-01-01", periods=80))
    c = S7.trend_tired(sig, closes=closes)
    assert c["fwd20"] > 0 and c["base20"] > 0 and c["fwd40"] > 0
    assert study.trend_tired_study(sig)["flags"] == r["flags"]


def test_position_freq_flag():
    """A synthetic signal list with 2 in one quarter keeps only the first and raises the flag at 5/yr."""
    sig = ["2026-01-10", "2026-02-20", "2026-04-15", "2026-07-01", "2026-10-05"]
    r = S7.position_freq(sig)
    assert [t.strftime("%m-%d") for t in r["kept"]] == ["01-10", "04-15", "07-01", "10-05"]
    assert r["per_year"] == {2026: 5} and r["over_year"] == [2026] and r["over_quarter"] == [(2026, 1)] and r["flag"] is True
    ok = S7.position_freq(["2026-01-10", "2026-04-15"])
    assert ok["flag"] is False and len(ok["kept"]) == 2
    many = S7.position_freq(sig, pos_max_per_quarter=2, pos_flag_per_year=6)
    assert len(many["kept"]) == 5 and many["flag"] is False
    assert study.position_freq_study(sig)["flag"] is True


def test_swing_one_open():
    """Overlapping swing signals: the second is dropped while the first is open."""
    sig = [dict(entry="2026-01-05", exit="2026-01-20"), dict(entry="2026-01-12", exit="2026-01-30"), dict(entry="2026-02-02", exit="2026-02-10")]
    r = S7.swing_frequency(sig)
    assert len(r["kept"]) == 2 and len(r["dropped"]) == 1 and r["dropped"][0]["entry"] == "2026-01-12" and r["per_year"] == {2026: 2} and r["flag"] is False
    both = S7.swing_frequency(sig, swing_one_open=False)
    assert len(both["kept"]) == 3 and both["dropped"] == []
    flag = S7.swing_frequency([dict(entry=f"2026-{m:02d}-02", exit=f"2026-{m:02d}-03") for m in range(1, 13)] * 2, swing_one_open=False, swing_flag_per_year=12)
    assert flag["flag"] is True and flag["over_year"] == [2026]
    assert study.swing_frequency_study(sig)["kept"] == r["kept"]


# --- stops_sizing_scaling_in -------------------------------------------------------------------------------------------------------------------

def test_swing_stop_helper():
    """Daily pivots at 4000 and 4030, entry 4050: daily_swing -> 4030 - pad."""
    rows = [(4040, 4050, 4020, 4045), (4045, 4060, 4000.0, 4010), (4010, 4040, 4015, 4035), (4035, 4070, 4040, 4065), (4065, 4080, 4060, 4075), (4075, 4090, 4030.0, 4080), (4080, 4100, 4045, 4095),
            (4095, 4110, 4090, 4100), (4100, 4120, 4075, 4115)]
    d = daily(rows)
    assert htf.swing_stop(d, 8, 1, "daily_swing", pad=2.0) == pytest.approx(4030.0 - 2.0)
    assert htf.swing_stop(d, 4, 1, "daily_swing") == pytest.approx(4000.0)           # only the bars before the entry bar: the 4030 pivot does not exist yet
    # the pivot at bar 5 is confirmed by bar 6: with entry bar 6 it is not usable, with bar 7 it is
    assert htf.swing_stop(d, 6, 1, "daily_swing") == pytest.approx(4000.0) and htf.swing_stop(d, 7, 1, "daily_swing") == pytest.approx(4030.0)
    m = daily([(10 - r_[0] % 10, 10 - r_[2] % 10, 10 - r_[1] % 10, 0) for r_ in rows])
    assert htf.swing_stop(daily([(200 - a, 200 - c, 200 - b, 200 - dd) for a, b, c, dd in rows]), 8, -1, "daily_swing", pad=1.0) == pytest.approx(200 - 4030.0 + 1.0)
    assert m is not None
    # the 4h sell-side behind the entry level
    base = pd.date_range(T("2026-01-05 00:00"), periods=20, freq="4h")
    lows = [4040, 4030, 4020, 4035, 4048, 4060, 4046, 4050, 4062, 4065, 4055, 4058, 4070, 4075, 4068, 4072, 4080, 4085, 4078, 4082]
    h4d = pd.DataFrame({"open": lows, "high": [x + 5 for x in lows], "low": lows, "close": [x + 2 for x in lows]}, index=base)
    daily2 = daily([(4000, 4100, 3990, 4050)] * 30, start="2026-01-05")
    s = htf.swing_stop(daily2, 5, 1, "ssl_behind", h4=h4d, entry=4050.0, pad=1.0, asof=pd.Timestamp("2026-01-09"))
    assert s == pytest.approx(4046 - 1.0)
    assert np.isnan(htf.swing_stop(daily2, 5, 1, "ssl_behind", h4=None, entry=4050.0))
    with pytest.raises(ValueError):
        htf.swing_stop(daily2, 5, 1, "nope")


def _week_book():
    """Prior sessions with a daily pivot high at 108 and a bearish weekly array [105, 110]; then the bearish week Mon-Fri."""
    pre = [(100, 104, 99, 103), (103, 106, 102, 105), (105, 108.0, 104, 106), (106, 107, 103, 104), (104, 105, 101, 102), (102, 103, 100, 101), (101, 104, 100, 103), (103, 104, 102, 103), (103, 104, 102.5, 103.5), (103.5, 104, 102.6, 103.8)]
    wk = [(104.0, 106.0, 103.0, 104.5), (105.0, 107.0, 103.5, 106.0), (106.0, 106.5, 101.0, 102.0), (102.0, 103.0, 96.5, 97.0), (97.0, 98.0, 95.0, 96.0)]
    return daily(pre + wk, start="2026-01-05")


def test_osok_scale_in_study():
    """Monday piece filled at 0.25, Wednesday higher high adds 0.75, average price above Monday's (a bearish week sells higher)."""
    d = _week_book()
    mon = d.index[10]
    k0 = T("2026-01-02 17:00")
    arrays = [S7.arr("W", "bear", 110.0, 105.0, k0), S7.arr("D", "bull", 97.0, 95.0, k0)]
    rows = S7.osok_scale_in(d, arrays, {mon: -1}, first_frac=0.25)
    assert len(rows) == 1
    r = rows[0]
    assert r["n_fills"] == 2 and r["first_entry"] == pytest.approx(105.0) and r["size"] == pytest.approx(1.0)
    assert r["avg_entry"] == pytest.approx(0.25 * 105.0 + 0.75 * 106.0) and r["avg_entry"] > r["first_entry"]            # Tuesday made the higher high: the add at Monday's high
    assert r["stop"] == pytest.approx(108.0) and r["exit"] == pytest.approx(97.0) and r["exit_reason"] == "target"
    assert r["pts_build"] == pytest.approx(r["avg_entry"] - 97.0) and r["pts_full"] == pytest.approx(105.0 - 97.0) and r["pts_build"] > r["pts_full"]
    assert S7.osok_scale_in(d, arrays, {mon: 1}, first_frac=0.25) == []                  # the week is not bearish
    assert S7.osok_scale_in(d, [S7.arr("W", "bear", 120.0, 115.0, k0)], {mon: -1}) == []     # Monday never traded into the array
    assert study.osok_scale_in(d, arrays, lambda t: -1)[0]["n_fills"] == 2
    # no higher high Tue / Wed: the add is the open above Monday's close
    d2 = d.copy()
    d2.loc[d2.index[11], ["open", "high"]] = [106.2, 105.9]
    d2.loc[d2.index[12], ["high"]] = 105.5
    r2 = S7.osok_scale_in(d2, arrays, {mon: -1})
    assert r2 and r2[0]["n_fills"] == 2 and r2[0]["avg_entry"] > 105.0
    # the small piece stays alone when neither day makes a higher high nor opens above Monday's close
    d3 = d.copy()
    d3.loc[d3.index[11], ["open", "high", "low", "close"]] = [103.0, 105.5, 100.0, 101.0]
    d3.loc[d3.index[12], ["open", "high", "low", "close"]] = [101.0, 104.0, 99.0, 100.0]
    r3 = S7.osok_scale_in(d3, arrays, {mon: -1})
    assert r3 and r3[0]["n_fills"] == 1 and r3[0]["size"] == pytest.approx(0.25)


def test_swing_readd():
    """4h synthetic leg: partial 0.25 at the first array, new FVG after it -> re-add 0.25 with the stop unchanged."""
    rows = [(100, 101, 99.5, 100.5), (100.5, 100.8, 99.8, 100.2),                         # bar 1 (the order's bar), fill needs low <= 100
            (100.2, 101.0, 99.9, 100.6),                                                   # bar 2: fills at 100
            (100.6, 104.5, 100.5, 104.2),                                                  # bar 3: reaches the partial level 104
            (104.2, 104.4, 100.9, 103.2), (103.2, 103.6, 102.8, 103.4), (103.4, 106.0, 103.3, 105.8),     # a bullish FVG: bar 6 low 103.3 > bar 4 high 104.4? no - built below
            (105.8, 106.2, 104.5, 105.0), (105.0, 106.0, 103.5, 105.5), (105.5, 112.0, 105.0, 111.5)]
    # make a clean bullish FVG on bars 4-6: bar 6 low (104.9) above bar 4 high (104.4)
    rows[6] = (104.4, 107.0, 104.9, 106.8)
    rows[7] = (106.8, 106.9, 105.0, 105.3)                                                 # retrace into the FVG [104.4, 104.9] CE 104.65? bar 7 low 105.0 does not reach it
    rows[8] = (105.3, 105.6, 104.5, 105.0)                                                 # bar 8 low 104.5 <= CE 104.65: the re-add fills
    rows[9] = (105.0, 112.0, 104.9, 111.5)
    e = dict(time=h4(rows).index[1], side=1, entry=100.0, stop=98.0, target=110.0, partial_level=104.0)
    r = S7.swing_readd(h4(rows), [e], readd_mult=1.0)[0]
    assert r["fill_bar"] == 2 and r["partial_bar"] == 3 and r["readd_bar"] == 8 and r["readd_qty"] == pytest.approx(0.25)
    assert r["stop_final"] == 98.0 and r["exit_reason"] == "target" and r["r_total"] > 0
    r2 = S7.swing_readd(h4(rows), [e], readd_mult=1.33)[0]
    assert r2["readd_qty"] == pytest.approx(0.25 * 1.33)
    rb = S7.swing_readd(h4(rows), [e], readd_stop="be")[0]
    assert rb["stop_final"] == pytest.approx(100.0)                                         # breakeven after the first profit
    half = S7.swing_readd(h4(rows), [e], readd_gate="half_obj")[0]
    assert half["readd_bar"] == 8                                                          # the objective's half (105) was reached on bar 6 before the array formed? see below
    none = S7.swing_readd(h4(rows[:6]), [e])[0]
    assert none["readd_bar"] is None and none["readd_qty"] == 0.0
    sh = [(200 - a, 200 - c, 200 - b, 200 - dd) for a, b, c, dd in rows]
    es = dict(time=h4(sh).index[1], side=-1, entry=100.0, stop=102.0, target=90.0, partial_level=96.0)
    rs = S7.swing_readd(h4(sh), [es])[0]
    assert rs["readd_bar"] == 8 and rs["side"] == -1 and rs["stop_final"] == 102.0
    assert study.swing_readd(h4(rows), [e])[0]["readd_bar"] == 8


def test_daily_stop_model():
    """Two down-close candles, the second's open triggers; partial, retrace to that open re-adds the same quantity."""
    k0 = T("2026-01-02 17:00")
    arrays = [S7.arr("W", "bear", 130.0, 125.0, k0), S7.arr("D", "bear", 110.0, 108.0, k0)]
    rows = [(96, 98, 94, 97), (97, 99, 90.0, 98), (98, 100, 97, 99.5), (99.5, 101, 98.5, 100.5), (100.5, 101.0, 99.0, 99.5),      # bars 0-4: a pivot low 90 at bar 1; bar 4 down-close
            (99.5, 100.2, 98.0, 98.8),                                                                                            # bar 5 down-close (opens 99.5, below bar 4's open 100.5)
            (98.8, 101.0, 98.6, 100.8),                                                                                           # bar 6: high >= the trigger open 99.5: fills at max(open, 99.5) = 99.5
            (100.8, 108.5, 100.5, 108.2),                                                                                         # bar 7: the first opposing daily array (108): the partial
            (108.2, 108.4, 99.2, 100.0),                                                                                          # bar 8: retraces to the trigger open 99.5: the partial quantity goes back
            (100.0, 101.0, 99.6, 100.8), (100.8, 126.0, 100.5, 125.5), (125.5, 126, 125, 125.5)]
    d = daily(rows)
    out = S7.daily_stop_model(d, arrays, max_units=1)
    assert len(out) == 1
    t = out[0]
    kinds = [f[3] for f in t["fills"]]
    assert kinds == ["entry", "partial", "readd"]
    assert t["fills"][0][2] == pytest.approx(99.5) and t["fills"][1][1] == pytest.approx(-0.5) and t["fills"][2][1] == pytest.approx(0.5) and t["fills"][2][2] == pytest.approx(99.5)
    assert t["exit_reason"] == "target" and t["exit"] == pytest.approx(125.0) and t["draw"] == 125.0 and t["pts"] > 0
    assert t["stop"] == pytest.approx(90.0)                                                # htf.swing_stop: the daily pivot low
    half = S7.daily_stop_model(d, arrays, first_frac=0.5, max_units=1)
    assert half[0]["fills"][0][1] == 0.5
    assert S7.daily_stop_model(d, [S7.arr("W", "bear", 130.0, 125.0, T("2026-03-01 17:00"))]) == []        # the draw is not known yet
    # the EQ gate: a close above the HTF EQ blocks the entry
    near = [S7.arr("W", "bear", 105.0, 103.0, k0)]
    assert S7.daily_stop_model(d, near, dsm_eq_gate=True) == []                           # the close is above the EQ of the range (pivot low .. the draw): no entry
    assert len(S7.daily_stop_model(d, near, dsm_eq_gate=False)) >= 1
    assert study.daily_stop_model(d, arrays, max_units=1)[0]["fills"][0][3] == "entry"


# --- stocks ----------------------------------------------------------------------------------------------------------------------------------------

def zz(points, n=None, start="2025-10-01", spread=0.4):
    """Daily bars following the control points (day index, price) linearly (a pivot at each interior control point); high / low = price +- spread."""
    n = n or points[-1][0] + 1
    xs = np.arange(n)
    px = np.interp(xs, [p_[0] for p_ in points], [p_[1] for p_ in points])
    idx = pd.bdate_range(start, periods=n)
    return pd.DataFrame({"open": px, "high": px + spread, "low": px - spread, "close": px}, index=idx)


P_ON = Params(stocks_mode=True)
IDX = zz([(0, 110), (18, 100), (30, 108), (42, 95), (54, 107), (66, 96.0), (74, 104)])                  # lower low at day 42, then a failure swing (96 >= 95) at day 66
S_KEEP = zz([(0, 60), (18, 50), (30, 58), (42, 52), (54, 60), (66, 54), (74, 66)])                    # higher low at 42 (52 > 50), a higher high at the failure (it rallies over its last pivot high 60)
S_LL = zz([(0, 60), (18, 50), (30, 58), (42, 48), (54, 56), (66, 50), (74, 58)])                      # a lower low at 42
S_NOHH = zz([(0, 60), (18, 50), (30, 58), (42, 52), (54, 60), (66, 54), (74, 57)])                    # keeps the higher low but no higher high at the failure


def test_stock_smt_screen():
    asof = IDX.index[74]
    assert ST.smt_screen(S_KEEP, IDX, asof, P_ON) == "keep"
    assert ST.smt_screen(S_LL, IDX, asof, P_ON) == "none"                                # the stock also makes lower lows: not kept
    assert ST.smt_screen(S_NOHH, IDX, asof, P_ON) == "discard"                           # the index's failure swing with no stock higher high
    early = IDX.index[58]
    assert ST.smt_screen(S_NOHH, IDX, early, P_ON) == "keep"                             # before the failure swing exists the stock is simply kept
    assert ST.smt_screen(S_KEEP, IDX, IDX.index[8], P_ON) == "none"                      # too little data
    with pytest.raises(RuntimeError):
        ST.smt_screen(S_KEEP, IDX, asof, Params())                                       # parked: stocks_mode is off
    # the windows: July is no buy window, February and the study month before October are
    assert ST.in_buy_window("2026-02-10") and ST.in_buy_window("2026-10-15") and ST.in_buy_window("2026-01-05") and ST.in_buy_window("2026-09-10")
    assert not ST.in_buy_window("2026-07-15") and not ST.in_buy_window("2026-06-01") and not ST.in_buy_window("2026-08-20")
    wl = ST.watchlist("2026-07-15", {"AAA": S_KEEP}, IDX, P_ON, use_leaders=False)
    assert wl == dict(kept=[], picks=[])


def test_stock_weekly_up():
    up = zz([(0, 50), (10, 56), (14, 53), (24, 62), (28, 58), (40, 70), (44, 66), (60, 78)], spread=0.3)
    assert ST.weekly_up(up, up.index[-1])
    down = zz([(0, 80), (10, 70), (14, 74), (24, 64), (28, 68), (40, 55), (44, 58), (60, 48)], spread=0.3)
    assert not ST.weekly_up(down, down.index[-1])
    assert not ST.weekly_up(up.iloc[:10], up.index[9])
    assert len(ST.weekly_closed(up, up.index[12])) <= len(ST.weekly_closed(up, up.index[40]))             # closed weeks only


def _uni():
    """Eight stocks that are well-behaved weekly uptrends; `near` ones sit just under their old weekly high."""
    base = [(0, 50), (20, 56), (26, 53), (50, 64), (58, 60), (80, 72), (86, 70)]
    return base


def test_stock_select():
    asof = pd.Timestamp("2026-02-27")
    idx = pd.bdate_range(end=asof, periods=140)

    def stock(top, last, base_low=None):
        """A stock whose highest weekly high is `top`, ending at `last`, with a base low (the last weekly pivot low) `base_low` ~1.5 under the end."""
        bl = last - 1.5 if base_low is None else base_low
        pts = [(0, top - 40), (60, top), (110, bl), (125, bl + 1.0), (139, last)]
        px = np.interp(np.arange(140), [p_[0] for p_ in pts], [p_[1] for p_ in pts])
        return pd.DataFrame({"open": px, "high": px + 0.5, "low": px - 0.5, "close": px}, index=idx)
    uni = {"VZ": stock(100, 98.0), "NEAR1": stock(100, 98.0), "NEAR2": stock(100, 99.0), "FAR": stock(100, 80.0), "EXT": stock(100, 98.0, base_low=80.0), "NEAR3": stock(100, 97.0)}
    kept = list(uni)
    out = ST.select(kept, uni, asof, P_ON)
    assert "VZ" not in out and "FAR" not in out and "EXT" not in out and len(out) >= 2 and set(out) <= {"NEAR1", "NEAR2", "NEAR3"}
    assert out[0] == "NEAR2"                                                              # closest to the old high first
    assert ST.near_high_info(uni["EXT"], asof, P_ON)["extended"] is True and ST.near_high_info(uni["EXT"], asof, P_ON)["near_high"] is True
    info = ST.near_high_info(uni["FAR"], asof, P_ON)
    assert not info["near_high"] and info["dist"] == pytest.approx(0.2, abs=0.01)
    assert ST.near_high_info(uni["NEAR1"], asof, P_ON)["near_high"]
    assert ST.near_high_info(uni["NEAR1"], asof, P_ON)["extended"] is False
    # more than four survivors -> four
    many = {f"S{k}": stock(100, 98.0) for k in range(7)}
    assert len(ST.select(list(many), many, asof, P_ON)) == 4
    assert len(ST.select(list(many), many, asof, P_ON, n_max=2)) == 2
    # fewer than two survivors: none
    assert ST.select(["NEAR1", "FAR"], uni, asof, P_ON) == []
    assert ST.select(["NEAR1", "NEAR2"], uni, asof, P_ON, fund_ok=lambda s: s != "NEAR1") == []
    # the 2017 list
    assert "MSFT" in ST.excluded(Params(stocks_mode=True, stock_excl_2017=True)) and "MSFT" not in ST.excluded(P_ON) and set(ST.EXCLUDE) <= set(ST.excluded(P_ON))
    with pytest.raises(RuntimeError):
        ST.select(kept, uni, asof, Params())


def test_stock_rs_leaders():
    asof = pd.Timestamp("2026-02-27")
    idx = pd.bdate_range(end=asof, periods=80)

    def ser(ret):
        c = np.linspace(100.0, 100.0 * (1 + ret), 80)
        c[:17] = 100.0
        c = np.interp(np.arange(80), [0, 16, 79], [100.0, 100.0, 100.0 * (1 + ret)])
        return pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c}, index=idx)
    stocks = {"UP": ser(0.20), "MID": ser(0.05), "DN": ser(-0.05)}
    index = ser(0.03)
    rk = ST.rs_rank(stocks, index, asof, n=63)
    assert rk["UP"] == 100.0 and rk["MID"] == 50.0 and rk["DN"] == 0.0
    lead = ST.leaders(stocks, index, asof, P_ON, index_flip=1)
    assert lead == ["UP"]
    assert ST.leaders(stocks, index, asof, P_ON, index_flip=-1) == []                    # a bearish index: nothing
    assert ST.leaders(stocks, index, asof, P_ON, index_flip=0) == []
    assert ST.leaders(stocks, index, asof, P_ON, index_flip=1, sector_of=lambda s: None) == ["UP"]       # sector hooks None: the step is skipped
    sec = {"UP": "tech", "MID": "tech", "DN": "util"}
    assert ST.leaders(stocks, index, asof, Params(stocks_mode=True, stock_top_sectors=1), index_flip=1, sector_of=sec.get) == ["UP"]
    assert ST.leaders(stocks, index, asof, Params(stocks_mode=True, stock_top_sectors=1, stock_rs_min=0.0), index_flip=1, sector_of=sec.get) == ["UP", "MID"]       # util is not a top sector
    # a stock below the 50 % of its 60-day range is no leader even with the best RS
    spike = ser(0.20)
    c = np.interp(np.arange(80), [0, 16, 60, 79], [100.0, 100.0, 160.0, 120.0])
    spike = pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c}, index=idx)         # the same +20 % but far under the midpoint of its 60-day range
    assert ST.leaders({"A": ser(0.20), "B": spike}, index, asof, Params(stocks_mode=True, stock_rs_min=0.0), index_flip=1) == ["A"]
    assert ST.rs_rank({}, index, asof) == {}


def test_stock_watchlist_order_and_ranking():
    """exclusions -> leaders -> smt_screen -> select; the kept names are ranked weekly-uptrend first."""
    asof = IDX.index[74]
    uni = {"VZ": S_KEEP, "AAA": S_KEEP, "BBB": S_LL}
    wl = ST.watchlist(asof, uni, IDX, P_ON, use_leaders=False)
    assert wl["kept"] == ["AAA"] and "VZ" not in wl["kept"]
    wl2 = ST.watchlist(asof, uni, IDX, P_ON, use_leaders=True, index_flip=1)
    assert isinstance(wl2["picks"], list)


# --- stocks_watch ----------------------------------------------------------------------------------------------------------------------------------

def _years():
    idx = pd.bdate_range("2025-11-03", "2026-05-29")
    return idx


def test_stock_jan_smt_synthetic():
    idx = _years()
    n = len(idx)

    def build(dec_low, jan_low):
        px = np.full(n, 100.0)
        s = pd.Series(px, index=idx)
        s[(idx.month == 12)] = 100.0
        s[(idx.month == 1)] = 100.0
        df = pd.DataFrame({"open": s.values, "high": s.values + 1, "low": s.values - 1, "close": s.values}, index=idx)
        df.loc[idx[(idx.month == 12) & (idx.day == 15)], "low"] = dec_low
        df.loc[idx[(idx.month == 1) & (idx.day == 15)], "low"] = jan_low
        return df
    dia = build(98.0, 96.0)                                                              # the Dow made a lower January low
    stocks = {"HL": build(90.0, 92.0), "LL": build(90.0, 88.0)}
    assert SW.jan_smt(2026, stocks, dia, P_ON) == ["HL"]
    assert SW.jan_smt(2026, stocks, build(98.0, 99.0), P_ON) == []                       # the Dow did not make a lower low
    with pytest.raises(RuntimeError):
        SW.jan_smt(2026, stocks, dia, Params())


def test_stock_gap_refill():
    idx = pd.bdate_range("2025-12-15", "2026-06-30")
    n = len(idx)
    c = np.linspace(100, 130, n)
    df = pd.DataFrame({"open": c, "high": c + 0.5, "low": c - 0.5, "close": c}, index=idx)
    gap_day = int(np.flatnonzero(idx == pd.Timestamp("2026-01-12"))[0])
    df.iloc[gap_day:, :] += 5.0                                                          # a January up-gap: the low of 01-12 is above the high of 01-09
    feb2 = int(np.flatnonzero(idx == pd.Timestamp("2026-02-03"))[0])
    df.iloc[feb2, df.columns.get_loc("low")] = float(df.high.iloc[gap_day - 1]) - 0.2    # the second trading day of February trades back into the gap
    rows = SW.gap_refill(df, 2026, P_ON)
    gaps = [r for r in rows if r["kind"] == "gap"]
    assert gaps and gaps[0]["feb_day"] == 2 and gaps[0]["refill"] == pd.Timestamp("2026-02-03")
    assert gaps[0]["fwd1m"] == pytest.approx(float(df.close.iloc[feb2 + 21] / df.close.iloc[feb2] - 1.0))
    none = SW.gap_refill(df.iloc[:gap_day + 5], 2026, P_ON)
    assert none == []                                                                   # no February data: no refill


def test_stock_sell_smt_synthetic():
    asof = pd.Timestamp("2026-06-26")
    idx = pd.bdate_range(end=asof, periods=200)

    def path(points):
        xs = np.arange(200)
        px = np.interp(xs, [p_[0] for p_ in points], [p_[1] for p_ in points])
        return pd.DataFrame({"open": px, "high": px + 0.4, "low": px - 0.4, "close": px}, index=idx)
    dia = path([(0, 100), (120, 120), (140, 112), (170, 126), (199, 120)])              # higher weekly highs at ~120 and ~126
    weak = path([(0, 60), (120, 80), (140, 70), (170, 76), (185, 66), (199, 60)])        # a lower weekly high (76 < 80) while the Dow makes a higher high
    drift = path([(0, 90), (199, 50)])                                                  # drifts lower steadily: no rally into premium
    strong = path([(0, 60), (120, 80), (140, 70), (170, 90), (199, 88)])                # a higher high too
    out = SW.sell_list(asof, {"WEAK": weak, "DRIFT": drift, "STRONG": strong, "VZ": weak}, dia, P_ON, need_rally=False)
    names = [r["symbol"] for r in out]
    assert "WEAK" in names and "STRONG" not in names and "VZ" not in names
    assert SW.sell_list(pd.Timestamp("2026-09-18"), {"WEAK": weak}, dia, P_ON, need_rally=False) == []     # outside January / May-July
    assert SW.sell_list(asof, {"WEAK": weak}, path([(0, 100), (120, 130), (140, 120), (170, 118), (199, 110)]), P_ON, need_rally=False) == []      # the Dow made a lower high: the signal is gone
    nm = [r["symbol"] for r in SW.sell_list(asof, {"DRIFT": drift, "WEAK": weak}, dia, P_ON, need_rally=True)]
    assert "DRIFT" not in nm                                                             # the steady drift has no up-close weekly bar into a premium array


def test_stock_short_needs_rally():
    idx = pd.bdate_range("2025-06-02", periods=130)
    px = np.interp(np.arange(130), [0, 40, 55, 70, 129], [100, 130, 108, 125, 90.0])
    wk = pd.DataFrame({"open": px, "high": px + 0.4, "low": px - 0.4, "close": px}, index=idx).resample("W-FRI").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    steady = pd.DataFrame({"open": np.linspace(130, 80, 26), "high": np.linspace(130.5, 80.5, 26), "low": np.linspace(129.5, 79.5, 26), "close": np.linspace(129.0, 79.0, 26)}, index=wk.index[:26])
    assert SW.rally_into_premium(steady) is False
    rows = [(130, 131, 126, 127), (127, 128, 121, 122), (122, 123, 117, 118), (118, 119, 112, 113), (113, 114, 108, 109), (109, 110, 104, 105), (105, 106, 100, 101), (101, 124, 100, 123), (123, 123, 115, 116)]
    wkly = pd.DataFrame(rows, dtype=float, columns=["open", "high", "low", "close"], index=pd.date_range("2026-01-02", periods=len(rows), freq="W-FRI"))
    assert SW.rally_into_premium(wkly) is True                                          # an up-close week traded up into the weekly bearish FVG [123, 126]
    no_up = wkly.copy()
    no_up.loc[no_up.index[7], ["open", "close"]] = [123.5, 101.0]                         # the same wick but a down-close week: no Judas rally
    assert SW.rally_into_premium(no_up) is False
    assert SW.weekly_flow(steady) in (-1, 0)
    assert SW.weekly_flow(steady.iloc[:3]) == 0


def test_stock_base_filter():
    asof = pd.Timestamp("2026-03-27")
    idx = pd.bdate_range(end=asof, periods=70)

    def mk_(points, spread=0.3):
        px = np.interp(np.arange(70), [p_[0] for p_ in points], [p_[1] for p_ in points])
        return pd.DataFrame({"open": px, "high": px + spread, "low": px - spread, "close": px}, index=idx)
    base = mk_([(0, 80), (10, 100), (20, 100.5), (45, 101), (69, 102)])                    # a base of 50+ bars within 5 %
    assert SW.base_ok(base, asof, P_ON)["ok"] and SW.base_ok(base, asof, P_ON)["base"][2] >= 15
    brk = mk_([(0, 80), (10, 100), (20, 100.5), (55, 101), (69, 106)])                     # just breaking out of the base (6 % over): accepted
    assert SW.base_ok(brk, asof, P_ON)["ok"]
    gapped = mk_([(0, 80), (10, 100), (20, 100.5), (55, 101), (56, 118), (69, 120)])       # gapped away: price > 1.1 x the base high, the gap unfilled
    r = SW.base_ok(gapped, asof, P_ON)
    assert not r["ok"] and r["reason"] == "gapped_away"
    run = mk_([(0, 60), (69, 130)], spread=1.5)                                           # a straight run: no multi-week base, extended
    r2 = SW.base_ok(run, asof, P_ON)
    assert not r2["ok"] and r2["reason"] == "no_base_extended" and r2["base"] is None
    flat_gap = mk_([(0, 80), (10, 100), (20, 100.5), (55, 101), (56, 103.5), (69, 104)])    # a small gap followed by sideways movement is fine
    assert SW.base_ok(flat_gap, asof, P_ON)["ok"]
    assert SW.base_ok(base.iloc[:5], asof, P_ON)["reason"] == "no_data"
    assert SW.find_base(np.array([2.0, 3, 4]), np.array([1.0, 2, 3])) is None


def test_stock_mega_higher_low_filter():
    asof = pd.Timestamp("2026-03-27")
    idx = pd.bdate_range(end=asof, periods=90)

    def path(points, spread=0.3):
        px = np.interp(np.arange(90), [p_[0] for p_ in points], [p_[1] for p_ in points])
        return pd.DataFrame({"open": px, "high": px + spread, "low": px - spread, "close": px}, index=idx)
    lower = [(0, 110), (40, 100), (55, 108), (75, 95), (89, 99)]
    hold = [(0, 110), (40, 100), (55, 108), (75, 101), (89, 104)]
    indices = {"DIA": path(lower), "SPY": path([(0, 110), (40, 100), (55, 108), (75, 94), (89, 98)]), "QQQ": path(hold)}
    good = path([(0, 70), (40, 60), (55, 66), (75, 62), (89, 66)])                          # a higher swing low (62 > 60), basing
    bad = path([(0, 70), (40, 60), (55, 66), (75, 57), (89, 63)])                           # a lower low: rejected
    cheap = path([(0, 14), (40, 12), (55, 14), (75, 12.5), (89, 14)])                      # below $20
    out = SW.mega(asof, {"GOOD": good, "BAD": bad, "CHEAP": cheap, "VZ": good}, indices, P_ON)
    assert out["smt"] is not None and out["smt"][0] == "QQQ"                                # the Nasdaq held a higher low while the Dow and SPX made lower lows
    assert out["picks"] == ["GOOD"] and "fundamental screen" in out["unavailable"]
    none = SW.mega(asof, {"GOOD": good}, {k: indices["DIA"] for k in ("DIA", "SPY", "QQQ")}, P_ON)
    assert none["smt"] is None and none["picks"] == []
    assert SW.three_index_smt(indices, asof, P_ON)[0] == "QQQ"
    with pytest.raises(RuntimeError):
        SW.mega(asof, {}, indices, Params())


# --- hygiene -----------------------------------------------------------------------------------------------------------------------------------------

def test_new_modules_are_platform_neutral():
    for m in (BH7, S7, ST, SW):
        src = inspect.getsource(m)
        for bad in ("C:\\", "os.getcwd", "tempfile", "/tmp", "subprocess"):
            assert bad not in src, (m.__name__, bad)
    assert date(2026, 1, 1)
