"""Caption-gap pass, package bias_htf#4/7 (35 specs from digests/rulebook_gaps): defaults / validation / study variants / table configuration, and the TABLE-SIDE functions of bh4.py on hand-made daily books
and 15m frames (the htf.table hooks on small synthetic frames). The engine hooks are in test_caption_gap_bh4b.py, the table build with every switch, the no-look-ahead cuts and the executed-path coverage
in test_caption_gap_bh4c.py. Nothing here needs market data; nothing is platform specific; no file outside the repo is written."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh4 as BH4, bias_htf as BX, htf, levels as L, study
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr  # noqa: E402
from test_caption_gap_bh1c import fut_frame, fut_walk  # noqa: E402

FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)

NEW_FIELDS = (
    "range_day_mode", "range_day_n", "ipda_mid_skip", "ipda_mid_lo", "ipda_mid_hi", "htf_checklist", "bias_cadence", "dbisi_lower_half", "dbisi_upper_and_discount", "array_age_tiers", "ce_line_bias",
    "ifvg_bias", "ifvg_edge_add", "ifvg_bias_days", "salient_pd", "htf_lifetime_wm", "htf_history_months", "trapped_bpr_bias", "event_wick_ignore", "event_wick_mult", "htf_ob_mitigation", "origin_ob",
    "monthly_range", "monthly_flow_gate", "ob_ladder", "ob_ladder_px", "program_tag", "program_days", "matrix_tfs", "htf_range_arrays", "swing_extreme_block", "swing_block_long", "swing_block_short",
    "swing_ignore_eq", "htf_ob_to_mt", "htf_reach_tol_pts", "pd_grid", "pd_grid_days", "grade_confluence", "pd_need_array", "pd_range_break", "failed_consol_break", "failed_consol_tfs", "nested_pd_bias", "htf_eq_invalid",
    "breaker_regime")
KNOBS = {"failed_consol_tfs", "range_day_n", "ipda_mid_lo", "ipda_mid_hi", "ifvg_bias_days", "event_wick_mult", "program_days", "swing_block_long", "swing_block_short", "pd_grid_days", "ob_ladder_px"}
OFF = {"range_day_mode": "off", "ipda_mid_skip": False, "htf_checklist": False, "bias_cadence": "daily", "dbisi_lower_half": False, "dbisi_upper_and_discount": False, "array_age_tiers": False,
       "ce_line_bias": False, "ifvg_bias": False, "ifvg_edge_add": False, "salient_pd": (), "htf_lifetime_wm": -1, "htf_history_months": 0, "trapped_bpr_bias": False, "event_wick_ignore": False,
       "htf_ob_mitigation": False, "origin_ob": False, "monthly_range": False, "monthly_flow_gate": False, "ob_ladder": False, "program_tag": False, "matrix_tfs": ("D",), "htf_range_arrays": False,
       "swing_extreme_block": False, "swing_ignore_eq": False, "htf_ob_to_mt": False, "htf_reach_tol_pts": 0.0, "pd_grid": False, "grade_confluence": False, "pd_need_array": False,
       "pd_range_break": "off", "failed_consol_break": False, "failed_consol_tfs": ("D",), "nested_pd_bias": False, "htf_eq_invalid": False, "breaker_regime": False}


def build(p, df, **kw):
    return htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p), **kw)


# --- defaults, validation, configuration -------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert (p.range_day_n, p.ipda_mid_lo, p.ipda_mid_hi, p.ifvg_bias_days, p.event_wick_mult, p.program_days, p.swing_block_long, p.swing_block_short, p.pd_grid_days) == (5, 0.375, 0.625, 20, 2.0, 3, 0.8, 0.3, 60)
    assert p.ob_ladder_px == "open" and p.sb_model is False                      # the Silver Bullet stays off
    assert p.sb_use_bias == Params().sb_use_bias and p.want_all_engines == Params().want_all_engines
    for bad in (dict(range_day_mode="x"), dict(bias_cadence="monthly"), dict(ob_ladder_px="mid"), dict(pd_range_break="one_close"), dict(matrix_tfs=("H",)), dict(salient_pd=(30,)),
                dict(range_day_n=1), dict(ipda_mid_lo=0.7, ipda_mid_hi=0.6), dict(htf_lifetime_wm=-2), dict(swing_block_short=0.9), dict(pd_grid_days=4), dict(program_days=1)):
        with pytest.raises(ValueError):
            Params(**bad)
    assert Params(htf_history_months=18).htf_monthly_arrays is True              # B5-htf-lookback-9-18-months: the monthly arrays exist from that far back
    with pytest.warns(UserWarning, match="inert"):
        Params(trapped_bpr_bias=True)                                            # htf_bias 'off': the fallbacks have nothing to reshape


def test_bx_configuration_is_empty_by_default_and_names_what_is_needed():
    assert BH4.bx_cfg(Params()) == {} and "b4" not in BX.parse(Params().bx)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        c = BH4.bx_cfg(Params(**FUT, range_day_mode="pm_only", htf_checklist=True, bias_cadence="weekly_midweek", htf_lifetime_wm=0, matrix_tfs=("D", "W", "M"), ob_ladder=True, pd_range_break="two_close",
                              htf_reach_tol_pts=3.0, event_wick_ignore=True, htf_eq_invalid=True, htf_history_months=18))
    assert c["rd"] == 5 and c["chk"] == 1 and c["cad"] == 2 and c["wm"] == 0
    assert c["mx"] == ["W", "M"] and c["grid"] == [60, 1] and c["tol"] == 3.0 and c["ew"] == 2.0 and c["rng"] == 1 and c["eqi"] == 1 and c["lad"] == [0.0, 0]
    assert BH4.life_wm(Params(htf_lifetime_wm=0, htf_history_months=18)) == 0 and BH4.life_wm(Params(htf_history_months=18)) == 378 and BH4.life_wm(Params(htf_lifetime_wm=100)) == 100
    assert B.hist_days(Params(htf_history_months=18)) >= 18 * 21 + 1 and B.hist_days(Params()) == 61           # the history the engine hands run_day


def test_study_variants_exist_and_build():
    names = [k for k in study.DECISIONS if k.startswith(("B17-range-day-sit-out-am", "N8-middle-of-range", "DS2-buy-day-checklist", "new-perspective-cadence", "A5-ltf-fvgs-inside-daily-bisi",
                                                           "A21-htf-fvg-upper-half-and-discount", "A5-pd-array-lookback-priority", "A8-ce-line-bearish-read", "A8-ifvg-bias-without-retest",
                                                           "A21-salient-dealing-ranges", "A5-A10-htf-lifetime", "A11-trapped-trader-bpr", "A4-event-wick-ignore", "A15-htf-ob-as-mitigation",
                                                           "A12-sponsorship-origin-ob", "new-monthly-dealing-range", "A12-bearish-activation", "A12-stepping-ob", "new-buy-program",
                                                           "A22-matrix-range-tf", "A21-htf-range-anchored-at-arrays", "A21-swing-no-new-longs-80-90", "A21-swing-discount-exception",
                                                           "A12-htf-ob-trade-through-to-mt", "new-layered-orders-before-level", "A21-quadrant-grid", "new-pd-array-at-quadrant-level",
                                                           "A21-range-position-needs-array", "A21-range-excursion-tolerance", "new-monthly-failed-consolidation-break", "A21-nested-ranges",
                                                           "A21-htf-eq-not-violated", "B5-htf-lookback-9-18-months", "A13-daily-breaker-regime"))]
    assert len(names) >= 34, len(names)
    used = set()
    for k in names:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p = Params(**dict(FUT, **study.DECISIONS[k]))
        used |= {f for f in NEW_FIELDS if getattr(p, f) != getattr(Params(), f)}
    assert (set(NEW_FIELDS) - KNOBS - {"ob_ladder_px"}) <= used, sorted((set(NEW_FIELDS) - KNOBS) - used)


# --- items 46 / 51: the range day and the 60-session middle -----------------------------------------------------------------------------

def test_range_day_column():
    h = np.array([110.0] + [105.0] * 9)
    l = np.array([90.0] + [95.0] * 9)
    c = np.array([100.0, 101, 99, 100, 100.5, 99.5, 130, 100, 100, 100])
    col = BH4.range_day_column(h, l, c, np.array([6, 7, 8]), 5)
    assert col.tolist() == [1, 0, 0]                                     # k=6: closes 1..5 inside the high-low of session 0; k=7 includes the close 130? no, 7 uses sessions 2..6 (130 is outside) and the ref is session 1


def test_ipda_pos_columns():
    h = np.linspace(100, 160, 70) + 1
    l = np.linspace(100, 160, 70) - 1
    c = np.linspace(100, 160, 70)
    cols = BH4.ipda_pos_columns(h, l, c, np.array([10, 60, 69]))
    assert np.isnan(cols["ipda_pos"][0]) and cols["ipda_pos"][1] == pytest.approx((c[59] - l[0:60].min()) / (h[0:60].max() - l[0:60].min()))
    assert 0.9 < cols["ipda_pos"][2] < 1.0 and cols["ipda60_hi"][2] == h[9:69].max()


# --- item 74: the buy-day checklist ---------------------------------------------------------------------------------------------------

def book(ohlc, arrs, start=date(2026, 1, 5)):
    d = dsess(ohlc, start)
    return BH4.Book(d, htf.weeks(d), arrs, 1.0, {})


def test_checklist_columns():
    base = [(4000.0, 4003.0, 3997.0, 4001.0)] * 70
    bk = book(base, [arr("bear", "fvg", 4030, 4020, 60), arr("bear", "fvg", 4012, 4008, 62)])
    ks = np.array([64, 66])
    out = pd.DataFrame({"react": [1, 0], "draw_up": [4020.0, 4020.0], "draw_dn": [np.nan, np.nan], "q_dir": [0, 0]}, index=[bk.d.index[64].date(), bk.d.index[66].date()])
    cols = BH4.checklist_columns(bk, out, ks, np.array([4001.0, 4001.0]))
    assert cols["chk_q"].tolist() == [1, 1]                                  # the price above the quarter open (4000)
    assert cols["chk_react_up"].tolist() == [1, 1] and cols["chk_react_dn"].tolist() == [0, 0]      # the react +1 at row 0 stays within 3 rows
    assert cols["chk_path_up"].tolist() == [1, 1]                            # the 4008-4012 bear FVG sits between the price and the 4020 draw (the draw itself is the near edge of the other gap)
    out2 = out.assign(q_dir=[-1, -1])
    assert BH4.checklist_columns(bk, out2, ks, np.array([4001.0, 4001.0]))["chk_q"].tolist() == [-1, -1]      # the quarterly shift column wins when set


# --- item 75: the weekly cadence ---------------------------------------------------------------------------------------------------------

def test_bias_cadence_freeze():
    idx = [d_.date() for d_ in pd.bdate_range("2026-03-02", periods=10)]
    out = pd.DataFrame({"wk_bias": [1, 1, -1, -1, -1, 0, 0, 1, 1, 1], "flip": [0, 0, 0, 1, 1, 0, 0, 0, 0, 0], "draw": 0}, index=idx)
    weekly = BH4.cadence_freeze(out.copy(), 1)
    assert weekly.wk_bias.tolist() == [1] * 5 + [0] * 5                      # Monday's value for the whole week
    assert weekly.flip.tolist() == out.flip.tolist()                         # the daily columns are not frozen
    mid = BH4.cadence_freeze(out.copy(), 2)
    assert mid.wk_bias.tolist() == [1] * 5 + [0] * 5                                  # the flip changed on THURSDAY only: no refresh (the one refresh is at the first row of Wednesday); week 2 holds Monday's
    out2 = out.copy()
    out2["flip"] = [0, 0, 1, 1, 1, 0, 0, 0, 0, 0]
    mid2 = BH4.cadence_freeze(out2, 2)
    assert mid2.wk_bias.tolist()[:5] == [1, 1, -1, -1, -1]                   # the daily flip changed by Wednesday: one refresh at the Wednesday open
    assert mid2.wk_bias.tolist()[5:] == [0] * 5
    out3 = out.copy()
    out3["flip"] = [np.nan] * 10
    assert BH4.cadence_freeze(out3, 2).wk_bias.tolist()[:5] == [1] * 5       # NaN against NaN is not a change


def test_cadence_freezes_every_weekly_column():
    """Review fix: every weekly / monthly-derived table column the bias modules build is in FROZEN (a new wk_ / mo_ / mwd weekly column must be added there or exempted here)."""
    import re
    from pathlib import Path
    root = Path(BH4.__file__).parent
    names = set()
    for f in ("bias_htf.py", "bh1.py", "bh2.py", "bh3.py"):
        names |= set(re.findall(r'out\["((?:wk|mo|mwd)_[a-z0-9_]+|iof_w)"\]', (root / f).read_text(encoding="utf-8")))
    exempt = {"mwd_d", "mo_aligned", "mo_unaligned", "mo_bias_block", "mo_bias_gate"}        # the daily part of the sequential; names that are not table columns
    missing = sorted(n for n in names - exempt if n not in BH4.FROZEN)
    assert not missing, missing
    out = pd.DataFrame({c_: [1, 2, 3, 4, 5, 6] for c_ in ("mwd", "mwd_m", "wk_dir", "wk_po3", "wk_q75", "iof_w", "mwd_d")}, index=[d_.date() for d_ in pd.bdate_range("2026-03-02", periods=6)])
    fz = BH4.cadence_freeze(out, 1)
    for c_ in ("mwd", "mwd_m", "wk_dir", "wk_po3", "wk_q75", "iof_w"):
        assert fz[c_].tolist() == [1] * 5 + [6], c_
    assert fz.mwd_d.tolist() == [1, 2, 3, 4, 5, 6]


# --- items 27 / 28 / 61 / 80: the daily FVG Z, the CE line, the inversion bias -------------------------------------------------------------

def test_dz_columns_pick_the_newest_gap_the_price_is_inside():
    base = [(4000.0, 4003.0, 3997.0, 4001.0)] * 40
    bk = book(base, [arr("bull", "fvg", 4010, 3990, 20), arr("bull", "fvg", 4005, 3999, 30), arr("bear", "fvg", 4040, 4030, 25)])
    cols = BH4.dz_columns(bk, np.array([35]), np.array([4001.0]))
    assert cols["dz_dir"].tolist() == [1] and cols["dz_lo"][0] == 3999 and cols["dz_hi"][0] == 4005 and cols["dz_ce"][0] == 4002
    assert BH4.dz_columns(bk, np.array([35]), np.array([4035.0]))["dz_dir"].tolist() == [-1]
    assert BH4.dz_columns(bk, np.array([35]), np.array([4100.0]))["dz_dir"].tolist() == [0]


def test_cel_columns_need_a_traded_through_ce_and_a_price_back_in_the_gap():
    base = [(4000.0, 4003.0, 3997.0, 4001.0)] * 40
    ohlc = list(base)
    ohlc[36] = (4000.0, 4003.0, 3992.0, 4001.0)                            # the session after the gap's formation trades under its CE 3995
    bk = book(ohlc, [arr("bull", "fvg", 4000, 3990, 35, ce=3995)])
    cols = BH4.cel_columns(bk, np.array([38]), np.array([3998.0]), np.array([4001.0]), np.array([3996.0]))
    assert cols["cel_kind"].tolist() == [1] and cols["cel_ce"][0] == 3995
    assert BH4.cel_columns(bk, np.array([38]), np.array([4010.0]), np.array([4012.0]), np.array([3996.0]))["cel_kind"].tolist() == [0]      # the price is back above the whole gap
    bk2 = book(base, [arr("bull", "fvg", 4000, 3990, 35, ce=3995)])
    assert BH4.cel_columns(bk2, np.array([38]), np.array([3998.0]), np.array([4001.0]), np.array([3996.0]))["cel_kind"].tolist() == [0]       # the CE was never traded through


def test_ifvg_columns_close_beyond_marks_the_next_session():
    ohlc = [(4000.0, 4003.0, 3997.0, 4001.0)] * 30 + [(4000.0, 4001.0, 3980.0, 3985.0)] + [(3986.0, 3990.0, 3980.0, 3985.0)] * 9      # session 30 closes under the bullish gap's bottom 3990
    bk = book(ohlc, [arr("bull", "fvg", 4000, 3990, 25)])
    cols = BH4.ifvg_columns(bk, np.array([30, 31, 33, 39]), 5)
    assert cols["ifvg_bias"].tolist() == [0, -1, -1, 0]                      # known the session after the close, kept 5 sessions
    assert cols["ifvg_top"][1] == 4000 and cols["ifvg_bot"][1] == 3990
    ohlc2 = list(ohlc)
    ohlc2[32] = (3990.0, 4010.0, 3989.0, 4005.0)                           # a close back above the inverted gap's top: spent
    assert BH4.ifvg_columns(book(ohlc2, [arr("bull", "fvg", 4000, 3990, 25)]), np.array([31, 33]), 5)["ifvg_bias"].tolist() == [-1, 0]
    bear = [(4000.0, 4003.0, 3997.0, 4001.0)] * 40
    bear[30] = (4000.0, 4021.0, 3999.0, 4020.0)
    assert BH4.ifvg_columns(book(bear, [arr("bear", "fvg", 4010, 4005, 25)]), np.array([31]), 5)["ifvg_bias"].tolist() == [1]      # the mirror


# --- item 119: the trapped-trader BPR on 15m ----------------------------------------------------------------------------------------

def _bpr_bars():
    base = [(100.5, 101.0, 100.0, 100.5)] * 26
    bars = base + [(100.5, 100.6, 95.0, 95.2), (95.2, 99.5, 95.0, 99.0), (99.0, 99.4, 98.8, 99.2), (99.2, 104.0, 99.1, 103.9), (103.9, 104.5, 100.5, 104.0)]
    a = np.array(bars, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_bpr_list_large_down_then_up_pair_is_bullish():
    o, h, l, c = _bpr_bars()
    got = BH4.bpr_list(o, h, l, c, 8)
    assert got == [(30, "bull", 100.0, 99.5)]
    assert BH4.bpr_list(o, h, l, c, 2) == []                               # more than max_gap bars apart
    assert BH4.bpr_list(o, h * 0 + 100.9, l * 0 + 99.0, c, 8) == []        # no large-range candles


def test_trapped_column_on_a_15m_frame():
    df = fut_frame([(4000.0, 4000.5, 3999.5, 4000.0)] * 30, seed=1)
    d = htf.sessions(df)
    k = 20
    day_ = d.index[k]
    idx = pd.date_range(pd.Timestamp(day_.date(), tz=B.NY) - pd.Timedelta(hours=2), periods=31 * 3, freq="5min")        # 22:00 the evening before ...
    o, h, l, c = _bpr_bars()
    # the frame in 15m bars of three identical 5m bars: shift the pattern to the 4000 level
    sh = 3900.0
    vals = np.vstack([o, h, l, c]).T + sh
    for q, (oo, hh, ll, cc) in enumerate(vals):
        for r in range(3):
            t = idx[q * 3 + r]
            df.loc[t, ["open", "high", "low", "close"]] = [oo, hh, ll, cc]
    got = BH4.trapped_column(df, htf.sessions(df), np.array([k, k + 1, k + 4]), 570, 8)
    assert got.tolist()[0] == 1 and got.tolist()[1] == 1 and got.tolist()[2] == 0         # known in the session after, gone three sessions later


# --- item 160: the program ---------------------------------------------------------------------------------------------------------

def test_program_column():
    o = np.array([100.0, 101, 102, 103, 104, 104, 103, 102, 101, 100])
    c = np.array([101.0, 102, 103, 104, 105, 103, 102, 101, 100, 99])
    h = np.array([101.5, 102.5, 103.5, 104.5, 105.5, 104.5, 103.5, 102.5, 101.5, 100.5])
    l = np.array([99.5, 100.5, 101.5, 102.5, 103.5, 102.5, 101.5, 100.5, 99.5, 98.5])
    col = BH4.program_column(o, h, l, c, np.array([4, 6, 9]), 3)
    assert col.tolist() == [1, 0, -1]                                         # k=4: sessions 1..3 up with higher highs; k=9: sessions 6..8 down with lower lows


# --- items 147 / 148: monthly range and flow -----------------------------------------------------------------------------------------

def test_monthly_range_picks_d_and_u():
    o = np.array([100.0, 110, 120, 118, 114])
    h = np.array([112.0, 125, 130, 121, 116])
    l = np.array([98.0, 108, 117, 112, 110])
    c = np.array([110.0, 122, 128, 114, 111])
    # the last completed bar (index 4) is down-close: D = 4 (high 116); the nearest older up-close candle with a high above 116 is bar 2 (130)
    assert BH4.monthly_range_at(o, h, l, c, 5) == (1, 110.0, 130.0)
    assert BH4.monthly_range_at(o, h, l, c, 1)[0] == 0                       # fewer than two completed months
    up = BH4.monthly_range_at(np.array([100.0, 90, 95]), np.array([101.0, 100, 99]), np.array([85.0, 80, 90]), np.array([88.0, 92, 98]), 3)
    assert up[0] == -1 and up[1] == 85.0 and up[2] == 99.0                    # the mirror: the last bar up-close; the nearest down-close candle with a lower low is bar 0


def test_monthly_flow_series_a_bearish_up_candle_activation():
    o = np.array([100.0, 104, 103, 98])
    h = np.array([105.0, 106, 104, 100])
    l = np.array([99.0, 103, 100, 95])
    c = np.array([104.0, 105, 101, 96])            # bar0 up, bar1 up, bar2 down (high 104), bar3 down
    fl = BH4.monthly_flow_series(o, h, l, c)
    # bar 2 violates the low of up-candle 1? l[2]=100 < l[1]=103 and < l[0]=99? no: bar0's low 99 not violated; bar1's low 103 violated -> bearish activation
    assert fl.tolist()[2] == -1
    # a down candle whose high is later exceeded activates the bullish side
    o2, h2, l2, c2 = np.array([105.0, 100, 101]), np.array([106.0, 101, 108]), np.array([99.0, 98, 100]), np.array([100.0, 99, 107])
    assert BH4.monthly_flow_series(o2, h2, l2, c2).tolist()[2] == 1


# --- item 150: the ladder ------------------------------------------------------------------------------------------------------------------

def test_ladder_steps_up_after_a_new_high():
    o = np.array([105.0, 104, 103, 104, 105, 108, 107, 110, 113, 112, 115])
    c = np.array([104.0, 103, 104, 105, 108, 107, 110, 113, 112, 115, 116])
    h = np.array([106.0, 105, 105, 106, 109, 109, 111, 114, 114, 116, 117])
    l = np.array([103.0, 102, 102, 103, 104, 106, 106, 109, 111, 111, 114])
    assert BH4.ladder_at(o, h, l, c, 8, 1, 0.0, 0) == (108.0,)                  # the down-close candle 5 (after the swing low, followed by a higher high)
    assert BH4.ladder_at(o, h, l, c, 10, 1, 0.0, 0) == (113.0, 108.0)            # after the next higher high the new down candle 8 is the active block (the highest), the older one a fallback
    assert BH4.ladder_at(o, h, l, c, 10, 1, 0.0, 1) == (114.0, 109.0)           # the entry level is the candle's high with px 'high'
    assert BH4.ladder_at(o, h, l, c, 10, 1, 5.0, 0) == (108.0,)                  # a displacement of 5x the body drops candle 8 (3 points above its open)
    c2 = c.copy()
    c2[9] = 112.0                                                                # a close under candle 8's MT 112.5 drops it
    assert BH4.ladder_at(o, h, l, c2, 10, 1, 0.0, 0) == (108.0,)
    assert BH4.ladder_at(o, h, l, c, 3, 1, 0.0, 0) == ()                         # nothing yet
    # the bearish mirror: mirrored prices give the mirrored ladder (lowest = active)
    K = 1000.0
    assert BH4.ladder_at(K - o, K - l, K - h, K - c, 10, -1, 0.0, 0) == (K - 113.0, K - 108.0)


# --- items 176 / 177 / 178 / 180: the body range, its eighths, the poke tolerance ----------------------------------------------------------

def test_grid_position_and_near_line():
    assert BH4.grid_position(30.0, 0.0, 100.0) == (0.3, 2, 2, 1)             # quadrant 2 (1-based), the discount half
    assert BH4.grid_position(75.0, 0.0, 100.0)[2:] == (4, -1) and BH4.grid_position(125.0, 0.0, 100.0)[1] == 7
    assert BH4.grid_position(10.0, 5.0, 5.0)[1] == -1
    assert BH4.near_grid_line(37.5 + 0.5, 0.0, 100.0) and not BH4.near_grid_line(37.5 + 3.0, 0.0, 100.0)      # 10 % of the 12.5 spacing = 1.25
    assert BH4.near_grid_line(50.0 + 1.2, 0.0, 100.0)


def test_body_range_two_close_ignores_a_one_day_poke_only():
    n = 10
    o = np.array([100.0] * 40)
    c = np.array([100.0, 104] * 20)
    h, l = np.maximum(o, c) + 1, np.minimum(o, c) - 1
    bh_ = np.maximum(o, c)
    ks = np.array([30, 32])
    lo0, hi0 = BH4.body_range(o, h, l, c, ks, n)
    assert hi0.tolist() == [104.0, 104.0] and lo0.tolist() == [100.0, 100.0]
    c2 = c.copy()
    c2[28] = 110.0                                                           # one close far beyond the range ...
    lo1, hi1 = BH4.body_range(o, h, l, c2, ks, n)
    lo2, hi2 = BH4.body_range(o, h, l, c2, ks, n, True)
    assert hi1[0] == 110.0 and hi2[0] == 104.0                               # ... a poke (the next close is back inside) is ignored with two_close
    c3 = c2.copy()
    c3[29] = 111.0                                                           # the next day does not close back inside: the range is broken and includes the new highs
    assert BH4.body_range(o, h, l, c3, ks, n, True)[1][0] == 111.0


# --- item 181: the failed consolidation break --------------------------------------------------------------------------------------------

def test_failed_break_bearish_and_target():
    n = 10
    base = [(100.0, 112.0, 98.0, 105.0), (110.0, 112.0, 98.0, 105.0)] * 7                 # bodies 100-110, closes 105: a consolidation
    ohlc = base + [(105.0, 115.0, 104.0, 108.0), (108.0, 109.0, 100.5, 103.0), (103.0, 104.0, 100.2, 102.0)]       # a run to 115, back, through the midpoint 105
    a = np.array(ohlc, float)
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    cols = BH4.failed_break_columns(o, h, l, c, np.array([len(c)]), n)
    assert cols["failed_break"].tolist() == [-1] and cols["fb_target"][0] == 100.0           # the lowest body of the range
    l2 = l.copy()
    l2[-1] = 99.0                                                              # the lowest body was traded to: the signal is spent
    assert BH4.failed_break_columns(o, h, l2, c, np.array([len(c)]), n)["failed_break"].tolist() == [0]
    assert BH4.failed_break_columns(o[:14], h[:14], l[:14], c[:14], np.array([14]), n)["failed_break"].tolist() == [0]
    K = 1000.0
    m = BH4.failed_break_columns(K - o, K - l, K - h, K - c, np.array([len(c)]), n)         # the mirror: a run under the range, back, over the midpoint
    assert m["failed_break"].tolist() == [1] and m["fb_target"][0] == K - 100.0


# --- item 185: the breaker regime ---------------------------------------------------------------------------------------------------------

def test_breaker_regime_follows_the_latest_breaker_without_looking_ahead():
    df = fut_walk("2025-01-06", "2025-09-30", seed=3, vol=0.9)
    d = htf.sessions(df)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    ks = np.arange(10, len(d))
    reg = BH4.breaker_regime_column(o, h, l, c, ks)
    zs = sorted(L.breakers(o, h, l, c, 2), key=lambda z: z.i)
    assert zs and set(reg.tolist()) <= {-1, 0, 1} and len(set(reg.tolist())) >= 2
    k = int(ks[-1])
    last = [z for z in zs if z.i <= k - 1][-1]
    assert reg[-1] == (1 if last.kind == "bull" else -1)
    cut = BH4.breaker_regime_column(o[:k], h[:k], l[:k], c[:k], ks[-3:])           # the same answer from the data through k-1 only
    assert cut.tolist() == reg[-3:].tolist()


# --- items 29 / 139 / 143 / 145 / 172: the table-time helpers --------------------------------------------------------------------------

def test_tier_filter_prefers_the_nearest_age_tier():
    draws = [(40.0, "D_fvg", 4040.0), (3.0, "D_fvg", 4003.0), (10.0, "D_swing_high", 4010.0)]
    got = BH4.tier_filter(draws, [15, 45, 70])
    assert got == [draws[0]]                                                     # the 15-day array is the draw although the 45-day one is nearer
    assert BH4.tier_filter(draws, [45, 30, 70]) == [draws[1]]                    # no W20 draw: W40 next (the 30-day array)
    assert BH4.tier_filter(draws, [70, 80, 90]) == draws                         # all older than 60: unchanged
    assert BH4.tier_filter([], []) == [] and BH4.tier_filter(draws[:1], [None]) == draws[:1]
    assert BH4.tier_of(20) == 1 and BH4.tier_of(21) == 2 and BH4.tier_of(60) == 3 and BH4.tier_of(61) == 4


def test_event_wick_adjust_uses_the_body_extreme_of_a_spike_day():
    n = 30
    o = np.full(n, 100.0)
    c = np.full(n, 100.5)
    h = np.full(n, 101.0)
    l = np.full(n, 99.5)
    h[25] = 140.0                                                                # one-off event wick (40 vs a mean range of 1.5)
    h2, l2 = BH4.event_wick_adjust(o, h, l, c, 2.0)
    assert h2[25] == 100.5 and (h2[:25] == 101.0).all() and (l2 == 99.5).all()
    ph, _ = L.pivots(h, l, 1)
    ph2, _ = L.pivots(h2, l2, 1)
    assert any(p.price == 140.0 for p in ph) and not any(p.price > 105 for p in ph2)       # without the wick there is no higher high


def test_body_origin_is_the_body_not_the_wick():
    # a down-close candle (open 104, close 101, wick low 95) then a displacement up leaving a bullish gap
    o = np.array([104.0, 101.0, 102.0, 112.0, 115.0])
    h = np.array([105.0, 103.0, 109.0, 118.0, 120.0])
    l = np.array([95.0, 100.0, 101.0, 110.0, 114.0])
    c = np.array([101.0, 102.0, 108.0, 117.0, 119.0])
    g = L.fvgs(h, l, o, c)
    assert g and g[0].kind == "bull"
    top, bot, mt, j = BH4.body_origin(o, h, l, c, g[0].i, "bull")
    assert (top, bot, mt, j) == (104.0, 101.0, 102.5, 0)                       # open to close of the last down-close candle; the 95 wick is ignored
    arrs = BH4.origin_arrays(o, h, l, c, "D", lambda i: i + 1)
    assert arrs and arrs[0].origin and arrs[0].top == 104.0 and arrs[0].bottom == 101.0 and arrs[0].known == g[0].i + 1
    assert BH4.origin_arrays(o, h, l, c, "D", lambda i: i + 1, existing=arrs) == []          # the same zone is not added twice


def test_mitigation_arrays_a_broken_bull_ob_becomes_a_daily_bear_ob():
    close = np.array([100.0, 100, 100, 100, 100, 94, 95, 96, 97, 98])
    ob = htf.Arr("bull", "ob", "W", 99.0, 96.0, 97.5, 2)
    got = BH4.mitigation_arrays([ob, htf.Arr("bull", "fvg", "W", 99, 96, 97.5, 2)], close, len(close))
    assert len(got) == 1 and got[0].kind == "bear" and got[0].tf == "D" and got[0].typ == "ob" and got[0].known == 6 and got[0].ce == 97.5 and got[0].mit
    assert BH4.mitigation_arrays([htf.Arr("bear", "ob", "W", 105.0, 102.0, 103.5, 2)], close, len(close)) == []      # not broken (no close above its top)


def test_ob_to_mt_keeps_a_weekly_block_alive_after_a_daily_close_through_the_open():
    d = dsess([(100.0, 101.0, 99.0, 100.0)] * 20)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    c = c.copy()
    c[12] = 97.0                                                                # a daily close under the weekly OB's MT 98
    w = htf.weeks(d)
    pos = {t: k for k, t in enumerate(d.index)}
    wl = [pos[t] + 1 for t in w["last"]]
    a = htf.Arr("bull", "ob", "W", 99.0, 96.0, 98.0, 5)
    args = (a, 15, o, h, l, c, w.open.values.astype(float), w.close.values.astype(float), wl, False)
    assert htf._arr_alive(*args, bal="legacy") is False                         # the old rule: daily closes retire it
    assert htf._arr_alive(*args, bal="legacy", to_mt=True) is True              # the weekly closes decide (they closed at 100)


# --- item 182: the nested ranges -----------------------------------------------------------------------------------------------------------

def test_nested_column_discount_array_held_inside_the_larger_premium():
    ohlc = [(4000.0, 4003.0, 3997.0, 4001.0)] * 60
    ohlc[30] = (4000.0, 4012.0, 3999.0, 4010.0)                            # the 60-session body range 4000-4010: EQ 4005
    ohlc[45] = (4000.0, 4003.0, 3990.0, 4001.0)                            # the small (20-session) swing range: low 3990 ...
    ohlc[52] = (4001.0, 4020.0, 3999.0, 4002.0)                            # ... high 4020: EQ 4005
    ohlc[58] = (4001.0, 4003.0, 4002.0, 4003.0)                            # a session whose low (4002) is above the array's CE: it traded into the array (top 4004) and held
    bull = arr("bull", "fvg", 4004, 3996, 50, ce=4000)                       # a daily bullish array in the discount of the small range (CE 4000 < EQ 4005)
    bk = book(ohlc, [bull])
    big = (np.array([4000.0]), np.array([4010.0]))
    nan1 = np.array([np.nan])
    assert BH4.nested_column(bk, np.array([60]), np.array([4012.0]), *big, nan1, nan1).tolist() == [1]          # price above the 60-session EQ, the array held: bullish
    assert BH4.nested_column(bk, np.array([60]), np.array([4002.0]), *big, nan1, nan1).tolist() == [0]          # price back in the larger discount: not nested
    bk2 = book(ohlc[:59] + [(4001.0, 4003.0, 3990.0, 3992.0)], [bull])                                          # a close under the array's CE 4000: it did not hold
    assert BH4.nested_column(bk2, np.array([60]), np.array([4012.0]), *big, nan1, nan1).tolist() == [0]
    bear = arr("bear", "fvg", 4010, 4006, 50, ce=4008)                       # the mirror: price in the larger DISCOUNT, a bearish array in the premium of the small range
    ohlc3 = [(4000.0, 4003.0, 3997.0, 3999.0)] * 60
    ohlc3[30] = (4010.0, 4011.0, 3999.0, 4000.0)
    ohlc3[45] = (4000.0, 4020.0, 3997.0, 3999.0)
    ohlc3[52] = (3999.0, 4001.0, 3980.0, 3998.0)
    ohlc3[58] = (3999.0, 4010.0, 3996.0, 3997.0)
    bk3 = book(ohlc3, [arr("bear", "fvg", 4012, 4008, 50, ce=4010)])
    assert BH4.nested_column(bk3, np.array([60]), np.array([3988.0]), np.array([3996.0]), np.array([4010.0]), nan1, nan1).tolist() == [-1]
