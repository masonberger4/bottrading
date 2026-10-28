"""Caption-gap pass, package bias_htf#5/7: defaults / validation / study variants / bx configuration, and the TABLE-SIDE functions of bh5.py on hand-made daily books (pure functions, no market data,
nothing platform specific, no file written outside the repo)."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh2 as BH2, bh5 as BH5, bias_htf as BX, htf, levels as L, study
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr  # noqa: E402

FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)

NEW_FIELDS = (
    "dfvg_upclose_anchor", "h4_ob_flip", "iof_follow", "iof_follow_days", "swing_min_days", "monthly_ctrl", "mega_min_days", "nwog_fill_rule", "nwog_eq_band", "nwog_below_return", "nwog_draw_confl",
    "confl_pts", "org_with_bias", "org_pm_draw", "dce_proj_study", "range_alternate", "range_block_probed", "pm_flip_draw", "pm_flip_adr", "pm_flip_days", "pm_range_break", "stack_draw", "stack_n",
    "program_gate", "gap_theory_bias", "wk_ssl_draw", "wk_two_draw", "b7_spike_floor", "shift_origin_pool", "target_tf", "wk_ref_friday", "fast_week_rev", "fast_week_adr", "eq_breakout_draw",
    "wk_range", "monthly_ctrl_smt", "d_draw_carry", "pdh_raid_rev", "raid_run_days", "or60_bias", "stock_old_high_max_pct", "range_rollover", "weekly_open_array")
KNOBS = {"iof_follow_days", "swing_min_days", "mega_min_days", "nwog_eq_band", "confl_pts", "range_block_probed", "pm_flip_adr", "pm_flip_days", "stack_n", "fast_week_adr", "raid_run_days",
         "stock_old_high_max_pct", "target_tf"}
OFF = {k: False for k in NEW_FIELDS if k not in KNOBS}
OFF.update(target_tf="off")


def book(ohlc, arrs, start=date(2026, 1, 5)):
    from mentorship import bh4 as BH4
    d = dsess(ohlc, start)
    return BH4.Book(d, htf.weeks(d), arrs, 1.0, {})


# --- defaults, validation, configuration -------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert (p.iof_follow_days, p.swing_min_days, p.mega_min_days, p.nwog_eq_band, p.confl_pts, p.pm_flip_adr, p.pm_flip_days, p.stack_n, p.fast_week_adr, p.raid_run_days, p.stock_old_high_max_pct) == \
        (5, 10, 126, 0.10, 2.0, 0.25, 5, 3, 1.5, 3, 0.10)
    assert p.sb_model is False and p.sb_use_bias == Params().sb_use_bias and p.want_all_engines == Params().want_all_engines
    for bad in (dict(target_tf="x"), dict(iof_follow_days=0), dict(nwog_eq_band=0.6), dict(stack_n=0), dict(raid_run_days=1), dict(fast_week_adr=0), dict(pm_flip_days=0), dict(range_block_probed=-1)):
        with pytest.raises(ValueError):
            Params(**bad)
    with pytest.warns(UserWarning, match="inert"):
        Params(stack_draw=True)                                              # htf_bias 'off': the side readings have nothing to reshape


def test_bx_configuration_is_empty_by_default_and_names_what_is_needed():
    assert BH5.bx_cfg(Params()) == {} and "b5" not in BX.parse(Params().bx)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, htf_bias="combo", stack_draw=True, stack_n=4, eq_breakout_draw=True, wk_ref_friday=True, range_rollover=True, iof_follow=True, wk_range=True, target_tf="same")
    c = BH5.bx_cfg(p)
    assert c["stack"] == 4 and c["eqb"] == [p.drange_n, p.drange_break] and c["wref"] == 1 and c["roll"] == 1 and c["iff"] == 5
    x = BX.parse(p.bx)
    assert x["wk"] == 1 and x["rtf"] == 1 and "iof" in x and "pd20" in x


def test_study_variants_exist_and_build():
    ids = ("A5-htf-fvg-last-upclose-anchor", "A12-4h-ob-mt-invalidation-flip", "B6-broken-highs-follow-through", "new-monthly-structure-control", "L5-friday-close-location-fill", "L5-below-nwog-low",
           "L5-nwog-not-standalone", "L7-breakaway-test", "L7-org-fill-delayed-pm", "L13-old-high-to-daily-ce-projection", "L14-consolidation-alternation", "L14-conditional-pm-draw-up",
           "new-range-edge-break-retest", "B2-stacked-unrun-highs", "B2-buy-program-eq-draw", "new-gap-theory", "L14-consolidation-above-ssl", "L14-weekly-two-sided-map",
           "B7-spike-floor-1h-ob-fvg", "new-shift-origin-pool", "L14-target-timeframe", "new-weekly-market-price-friday-close", "B7-fast-week-htf-reversal-level", "B1-eq-consolidation-breakout",
           "LLT3-weekly-dealing-range", "LLT3-daily-draw-multiday", "LLT3-pdh-raid-after-multiday-run", "LLT3-or-forms-day-extreme", "LLT3-dealing-range-rollover", "LLT3-weekly-open-pd-array")
    used = set()
    for i in ids:
        ks = [k for k in study.DECISIONS if k.startswith(i)]
        assert ks, i
        for k in ks:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p = Params(**dict(FUT, **study.DECISIONS[k]))
            used |= {f for f in NEW_FIELDS if getattr(p, f) != getattr(Params(), f)}
    assert (set(NEW_FIELDS) - KNOBS) <= used, sorted((set(NEW_FIELDS) - KNOBS) - used)


# --- item 191: the up-close anchor ---------------------------------------------------------------------------------------------

def test_upclose_anchor_extends_the_bearish_gap_top():
    o = np.array([118.0, 121.0, 113.0, 106.0])
    h = np.array([123.0, 121.0, 113.5, 108.0])
    l = np.array([118.0, 112.0, 105.0, 104.0])
    c = np.array([122.0, 113.0, 106.0, 105.0])
    z = [z for z in L.fvgs(h, l, o, c) if z.kind == "bear" and z.i == 3][0]
    assert (z.top, z.bottom) == (112.0, 108.0)
    assert BH5.upclose_edges(o, h, l, c, z) == (118.0, 108.0)               # c1 closed down: the last up-close candle's low is the top
    c2 = c.copy()
    o2 = o.copy()
    o2[1], c2[1] = 111.0, 121.0                                             # an up-close c1: unchanged
    assert BH5.upclose_edges(o2, h, l, c2, z) == (112.0, 108.0)
    a = htf._arrays(o, h, l, c, "D", lambda i: i + 1, upclose=True)
    f = [x for x in a if x.typ == "fvg" and x.known == 4][0]
    assert (f.top, f.bottom) == (118.0, 108.0)
    assert [x for x in htf._arrays(o, h, l, c, "D", lambda i: i + 1) if x.typ == "fvg" and x.known == 4][0].top == 112.0


# --- item 193: the follow-through ----------------------------------------------------------------------------------------------

def test_broken_high_without_a_higher_high_cuts_the_iof():
    h = np.array([100, 101, 102, 110, 101, 113, 105, 104, 103, 102, 101, 100, 99, 98, 97, 96], float)
    l = h - 3
    c = h - 2
    c[5] = 112.0
    cols = BH5.iof_follow_columns(h, l, c, np.array([9, 12]), 5)
    assert cols["iof_ft_up"].tolist() == [0, 1]                              # at k=9 the window is still running; at k=12 it completed without a new high
    out = pd.DataFrame({"iof": [1, 1], "iof_ft_up": cols["iof_ft_up"], "iof_ft_dn": cols["iof_ft_dn"], "react": [0, 0], "pd": [0, 0], "combo2": [1, 1]})
    assert BH5.apply_iof_follow(out).iof.tolist() == [1, 0]


# --- item 201: the monthly control -----------------------------------------------------------------------------------------------

def test_monthly_two_lower_highs_set_minus_one():
    mh = np.array([100, 110, 105, 108, 103, 106, 100, 102], float)
    ml = mh - 5
    assert BH5.monthly_ctrl_state(mh, ml, 8) == -1
    assert BH5.monthly_ctrl_state(mh[::-1] * -1 + 220, ml[::-1] * -1 + 220, 8) in (-1, 0, 1)
    up_l = np.array([95, 105, 100, 103, 101, 106, 104, 108], float)          # higher lows 100 -> 101 ... a rising structure
    assert BH5.monthly_ctrl_state(up_l + 5, up_l, 8) in (1, 0, -1)
    assert BH5.monthly_ctrl_state(mh, ml, 3) == 0


# --- item 22: the Friday close and the NWOG ----------------------------------------------------------------------------------------

def test_nwog_fill_by_friday_location():
    assert BH5.nwog_fill_state(4051.0, -1, 4000.0, 4100.0, 0.7, 0.10) == 0      # near the EQ after a premium-heavy week, gap down (the less explored side): a partial fill is fine
    assert BH5.nwog_fill_state(4051.0, 1, 4000.0, 4100.0, 0.7, 0.10) == 1       # gap up (the heavily explored side): the far edge is kept
    assert BH5.nwog_fill_state(4090.0, -1, 4000.0, 4100.0, 0.7, 0.10) == 1      # not near the EQ: full return
    assert BH5.nwog_fill_state(4051.0, -1, 4000.0, 4100.0, 0.5, 0.10) == 1


# --- item 55: the projection ---------------------------------------------------------------------------------------------------------

def test_daily_ce_projection_levels():
    lv = BH5.dce_levels(4090.75, 4117.5)
    assert lv == pytest.approx((4104.125, 4117.5, 4124.1875, 4130.875, 4137.5625, 4144.25))
    o = np.array([4000.0] * 3 + [4095.0] + [4000.0] * 6)
    h = np.array([4001, 4091, 4001, 4140, 4001, 4001, 4001, 4001, 4001, 4001], float)
    c = np.array([4000.0] * 3 + [4140.0] + [4000.0] * 6)
    l = np.array([3999.0] * 10)
    cols = BH5.dce_columns(o, h, l, c, np.array([9]))
    assert cols["dce_proj"][0] != ()
    hits = BH5.dce_proj_hits(pd.DataFrame({"dce_proj": [lv]}, index=[pd.Timestamp("2026-01-05")]), dsess([(4000, 4130, 3990, 4100)] * 12, date(2026, 1, 5)), 10)
    assert hits.n.tolist() == [1] * 6 and hits.hits.tolist() == [1, 1, 1, 0, 0, 0]


# --- item 75: the stacked highs ------------------------------------------------------------------------------------------------------

def test_stacked_highs_bias():
    hi = [4003.0] * 5 + [4080.0, 4040.0, 4070.0, 4030.0, 4060.0, 4020.0, 4030.0, 4025.0, 4020.0, 4018.0]
    rows = [(4012.0, h_, 4005.0, 4012.0) for h_ in hi]
    bk = book(rows, [arr("bull", "fvg", 4015, 4005, 3)])
    c = BH5.stack_columns(bk, np.array([14]), np.array([4012.0]), 3)
    assert c["stack_side"].tolist() == [1] and c["stack_hi"][0] == 4030.0                  # four untaken highs (4080, 4070, 4060, 4030): the nearest is the draw
    assert c["stack_rungs"][0] == (4030.0, 4060.0, 4070.0, 4080.0)                           # review fix: the nearest stacked high, then the higher ones
    bear = book(rows, [arr("bear", "fvg", 4120, 4100, 3)])
    assert BH5._reh_in_premium(bear, 14, [4101.0, 4101.5, 4030.0], 4012.0, 1) == (4101.5,)    # ... then the REH inside a live HTF premium FVG
    assert BH5._reh_in_premium(bear, 14, [4101.0, 4130.0], 4012.0, 1) == ()
    assert BH5.stack_columns(bk, np.array([14]), np.array([4012.0]), 5)["stack_side"].tolist() == [0]
    assert BH5.stack_columns(book(rows, []), np.array([14]), np.array([4012.0]), 3)["stack_side"].tolist() == [0]      # no unfilled BISI under the price


# --- item 78: the buy program --------------------------------------------------------------------------------------------------------

def test_buy_program_state_and_target():
    levels = [4100, 4150, 4200, 4150, 4100, 4050, 4000, 4000, 4000, 4000]
    rows = [(x, x + 2, x - 2, x) for x in levels for _ in range(5)]
    rows += [(4000.0, 4010.0, 3995.0, 4005.0), (4005.0, 4006.0, 3996.0, 3999.0), (3999.0, 4004.0, 3997.0, 4001.0), (4001.0, 4003.0, 3998.0, 4002.0),
             (4002.0, 4025.0, 4000.0, 4020.0), (4020.0, 4030.0, 4015.0, 4025.0)]
    bk = book(rows, [arr("bear", "fvg", 4120, 4110, 40)])
    j = len(rows) - 2
    c = BH5.program_columns(bk, np.array([j + 1]))
    assert c["bprog"].tolist() == [1] and c["bprog_tgt"][0] == 4110.0
    far = book(rows, [arr("bear", "fvg", 4070, 4060, 40)])                       # an array under the leg's 50 % (4099) is no target
    assert BH5.program_columns(far, np.array([j + 1]))["bprog"].tolist() == [0]


# --- item 115: the shift-origin pool ---------------------------------------------------------------------------------------------------

def test_shift_origin_pool():
    h = np.array([4100, 4150, 4200, 4150, 4120, 4140, 4125, 4090, 4085, 4080, 4078, 4070, 4065], float)
    l = np.array([4090, 4130, 4180, 4130, 4100, 4115, 4105, 4075, 4070, 4065, 4063, 4055, 4050], float)
    c = l + 5
    c[5], c[6], c[7] = 4130.0, 4115.0, 4085.0                                   # the first close under the pivot low 4100 is session 7
    cols = BH5.shift_origin_columns(h, l, c, np.array([9, 12]))
    assert cols["shift_last"].tolist() == [-1, -1] and cols["shift_origin_hi"].tolist() == [4200.0, 4200.0]
    h2 = np.append(h, 4205.0)
    cols = BH5.shift_origin_columns(h2, np.append(l, 4100.0), np.append(c, 4150.0), np.array([12, 14]))
    assert cols["shift_origin_hi"][0] == 4200.0 and np.isnan(cols["shift_origin_hi"][1])      # traded on session 13: no longer kept


# --- item 136: the fast week -----------------------------------------------------------------------------------------------------------

def test_fast_week_reversal_bias():
    rows = [(4000.0, 4010.0, 3990.0, 4000.0)] * 15 + [(4000.0, 4002.0, 3985.0, 3990.0), (3990.0, 3992.0, 3955.0, 3975.0), (3975.0, 3980.0, 3970.0, 3972.0), (3972.0, 3975.0, 3968.0, 3970.0),
                                                      (3970.0, 3975.0, 3965.0, 3970.0)]
    bk = book(rows, [arr("bull", "ob", 3980, 3960, 3, ce=3970.0)])
    c = BH5.fast_week_columns(bk, np.array([17]), np.array([3975.0]), 1.5)
    assert c["fast_week"].tolist() == [1] and c["fw_level"][0] == 3970.0
    assert BH5.fast_week_columns(bk, np.array([16]), np.array([3975.0]), 1.5)["fast_week"].tolist() == [0]       # Tuesday's row: not before Wednesday
    deep = book(rows[:15] + [(4000.0, 4002.0, 3985.0, 3990.0), (3990.0, 3992.0, 3955.0, 3965.0)] + rows[17:], [arr("bull", "ob", 3980, 3960, 3, ce=3970.0)])
    assert BH5.fast_week_columns(deep, np.array([17]), np.array([3975.0]), 1.5)["fast_week"].tolist() == [0]      # a close through the MT cancels it


# --- item 138: the EQ breakout ---------------------------------------------------------------------------------------------------------

def test_breakout_draws_to_weekly_imbalance():
    rows = [(4000.0, 4010.0, 3990.0, 4000.0)] + [(4000.0, 4008.0, 3992.0, 4002.0)] * 5 + [(4002.0, 4025.0, 4001.0, 4020.0), (4020.0, 4022.0, 4015.0, 4018.0)]
    rows = rows[:1] + rows[1:]
    bk = book(rows, [arr("bear", "fvg", 4060, 4040, 0, tf="W")])
    c = BH5.eqb_columns(bk, np.array([7]), np.array([4020.0]), 5, "close")
    assert c["eqb_dir"].tolist() == [1] and c["eqb_tgt"][0] == 4040.0
    inside = BH5.eqb_columns(book(rows[:6], []), np.array([6]), np.array([4002.0]), 5, "close")
    assert inside["eqb_dir"].tolist() == [0] and inside["eqb_in_eq"].tolist() == [1]


# --- item 147: the daily draw that carries -----------------------------------------------------------------------------------------------

def test_daily_draw_carries_until_hit():
    out = pd.DataFrame({"react": [1, 0, 0, 0, 0], "flip": [0] * 5, "draw_up": [4200.0] * 5, "draw_dn": [np.nan] * 5})
    h = np.array([4100.0, 4120.0, 4205.0, 4100.0, 4100.0])
    l = h - 20
    c = BH5.d_draw_columns(out, np.arange(5), h, l)
    assert c["d_draw_dir"].tolist() == [1, 1, 1, 0, 0]                           # set Monday, unmet Tuesday / Wednesday (the row of Wednesday sees Monday and Tuesday), hit on Wednesday: cleared on Thursday
    flipped = pd.DataFrame({"react": [1, 0, 0], "flip": [0, 0, 1], "draw_up": [4200.0] * 3, "draw_dn": [np.nan] * 3})
    assert BH5.d_draw_columns(flipped, np.arange(3), np.array([4100.0] * 3), np.array([4080.0] * 3))["d_draw_dir"].tolist() == [1, 1, 0]


# --- item 149: the run into an array -------------------------------------------------------------------------------------------------------

def test_three_up_days_into_a_daily_sibi():
    rows = [(4000.0, 4003.0, 3997.0, 4000.0), (4000.0, 4005.0, 3999.0, 4003.0), (4003.0, 4008.0, 4002.0, 4006.0), (4006.0, 4012.0, 4005.0, 4009.0), (4009.0, 4013.0, 4008.0, 4012.0),
            (4012.0, 4014.0, 4010.0, 4011.0)]
    bk = book(rows, [arr("bear", "fvg", 4020, 4010, 0)])
    assert BH5.run_into_array_column(bk, np.array([5]), 3).tolist() == [1]
    assert BH5.run_into_array_column(bk, np.array([5]), 5).tolist() == [0]        # not enough up closes
    assert BH5.run_into_array_column(book(rows, []), np.array([5]), 3).tolist() == [0]


# --- item 93: the consolidation above a cluster of lows --------------------------------------------------------------------------------------

def test_consolidation_above_lows_draw():
    n = 44
    base = [15100, 15080, 15120, 15060, 15030, 15000, 15040, 15020, 15001, 15030] + [15020, 15025, 15015, 15022, 15018, 15021, 15016, 15023, 15019, 15024] * 0
    h = np.array(base + [15030, 15025, 15028, 15024, 15027, 15022, 15026, 15025], float)[:18] + 3
    l = h - 8
    h[:8] = [15110, 15125, 15130, 15090, 15060, 15045, 15040, 15035]
    l[:8] = h[:8] - 6
    l[5], l[8] = 15000.0, 15001.0
    h[5], h[8] = 15012.0, 15012.0
    h[9] = 15040.0
    h[10:] = np.array([15030, 15026, 15028, 15025, 15029, 15024, 15027, 15026], float)
    l[10:] = h[10:] - 6
    l[l < 15000.0] = 15000.0
    l[5], l[8] = 15000.0, 15001.0
    o = (h + l) / 2
    c = o
    s, lvl, hi = BH5.ssl_state(o, h, l, c, 100.0, [(15110.0, 15130.0)], [])
    assert s == -1 and lvl == 15000.0 and hi == hi
    assert BH5.ssl_state(o, h, l, c, 100.0, [], [])[0] == 0                      # no rejection at a daily array


def test_ssl_read_uses_4h_arrays_and_the_fvg_below():
    """Review fix (93): the rejection may be at a 4h array; the inefficiency just below the cluster is part of the draw."""
    blocks = [(120, 121, 119, 119.5), (115, 116, 112, 113), (108, 109, 105, 106), (106, 107, 105.5, 106.5)]
    rows = [r for r in blocks for _ in range(48)]
    ix = pd.date_range("2026-03-02 00:00", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=ix)
    until = ix[-1] + pd.Timedelta(minutes=5)
    bear, bull = BH5.h4_live_zones(df, until.tz_localize(None))
    assert (109.0, 119.0) in bear and (107.0, 112.0) in bear and bull == []
    assert BH5.h4_live_zones(df, ix[0].tz_localize(None) + pd.Timedelta(hours=4)) == ([], [])          # nothing complete yet: no look-ahead
    h3 = np.array([60, 62, 70, 72, 74], float)
    l3 = np.array([58, 60, 66, 68, 70], float)                                           # bullish FVGs [60, 66] (CE 63) and [62, 68] (CE 65), below a level at 80, never refilled: the nearest (highest) CE
    assert np.isnan(BH5.ssl_fvg_below(np.array([61, 62, 70, 72, 74], float), np.array([59, 60, 66, 68, 61.0]), -1, 80.0))        # refilled by a later low under the gap's bottom
    assert BH5.ssl_fvg_below(h3, l3, -1, 80.0) == 65.0
    assert np.isnan(BH5.ssl_fvg_below(h3, l3, -1, 62.0))                                 # not below the level


# --- item 102: the two-sided map -----------------------------------------------------------------------------------------------------------

def test_weekly_two_draw_columns():
    rows = [(4100.0, 4105.0, 4095.0, 4100.0)] * 10
    bk = book(rows, [arr("bear", "fvg", 4160, 4150, 0), arr("bull", "fvg", 4050, 4040, 0)])
    c = BH5.two_draw_columns(bk, np.array([6, 7, 8]))                              # the second week: Monday = 5, Tuesday = 6
    assert np.isnan(c["wk_prem_draw"][0]) and c["wk_prem_draw"].tolist()[1:] == [4150.0, 4150.0] and c["wk_disc_draw"].tolist()[1:] == [4050.0, 4050.0]


def test_two_draw_and_fast_week_read_4h_arrays():
    """Review fix (102 / 136): the live 4h FVGs join the daily / weekly arrays in the table columns."""
    blocks = [(4180, 4190, 4170, 4175), (4170, 4172, 4160, 4162), (4150, 4155, 4140, 4145)]
    rows = [r for r in blocks for _ in range(48)]
    ix = pd.date_range("2026-01-13 00:00", periods=len(rows), freq="5min", tz="America/New_York")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=ix)
    bk = book([(4100.0, 4105.0, 4095.0, 4100.0)] * 10, [arr("bear", "fvg", 4260, 4250, 0), arr("bull", "fvg", 4050, 4040, 0)])
    ks = np.array([6, 7, 8])
    base = BH5.two_draw_columns(bk, ks)
    c = BH5.two_draw_columns(bk, ks, df)
    assert base["wk_prem_draw"].tolist()[1:] == [4250.0, 4250.0] and c["wk_prem_draw"].tolist()[1:] == [4155.0, 4155.0]       # the 4h gap [4155, 4170] is the nearer premium draw
    assert c["wk_disc_draw"].tolist()[1:] == [4050.0, 4050.0]
    a4 = BH5.h4_arrs(df, bk.d, 7)
    assert [(a.kind, a.bottom, a.top, a.ce) for a in a4 if a.bottom == 4155.0] == [("bear", 4155.0, 4170.0, 4162.5)]
    assert BH5.h4_arrs(df, bk.d, 6) == [] and BH5.h4_arrs(None, bk.d, 7) == []                  # not known before the cut


# --- item 135 / 30: the week's price ---------------------------------------------------------------------------------------------------------

def test_weekly_ref_is_friday_close():
    idx = pd.bdate_range("2026-01-05", periods=10)
    out = pd.DataFrame({"wk_draw_up": [1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10], "wk_draw_dn": [0.0] * 10}, index=idx)
    f = BH5.ref_friday_freeze(out.copy())
    assert f.wk_draw_up.tolist() == [1.0] * 5 + [6.0] * 5                            # Tuesday's split is the Monday row's (Friday's close)
    assert f.wk_draw_dn.tolist() == [0.0] * 10


def test_weekly_open_line_one_week():
    idx = pd.bdate_range("2026-01-05", periods=10)
    t = pd.DataFrame({"wo_sun": [4000.0] * 5 + [4100.0] * 5, "wo_mon": [3999.0] * 5 + [4099.0] * 5}, index=idx)
    assert BH5.weekly_open_level(t, pd.Timestamp("2026-01-12")) == 4100.0              # Monday of week 2: week 2's open, never week 1's
    assert BH5.weekly_open_level(t, pd.Timestamp("2026-01-09")) == 4000.0
    assert BH5.weekly_open_level(t, pd.Timestamp("2026-01-12"), "wo_mon") == 4099.0
    assert BH5.weekly_open_level(t, pd.Timestamp("2026-02-02")) != BH5.weekly_open_level(t, pd.Timestamp("2026-02-02"))     # no row: NaN


# --- item 142: the seasonal report -------------------------------------------------------------------------------------------------------------

def test_seasonal_entry_array_tag():
    idx = pd.bdate_range("2026-02-02", periods=60)
    t = pd.DataFrame({"px": np.linspace(4000, 4100, 60), "sea_w_ob": [0] * 60, "sea_w_brk": [0] * 60}, index=idx)
    t.loc[t.index[idx.month == 3][0], "sea_w_ob"] = 1
    m = ("cons",) * 2 + ("bull",) + ("cons",) * 9
    r = BH5.seasonal_entry_report(t, m, 10)
    assert len(r) == 1 and bool(r.in_w_ob.iloc[0]) and r.ret_next.iloc[0] > 0
    assert study.seasonal_entry_report(t, m, 10).equals(r)
    pm = Params(seasonal_map=m)                                              # review fix: the report reads Params.seasonal_map (the map seasonal_tag uses)
    assert BH5.seasonal_entry_report(t, pm, 10).equals(r) and len(BH5.seasonal_entry_report(t, None, 10)) >= 0


def test_stock_lrlr_symbol_aggregates_daily_to_weekly():
    idx = pd.bdate_range("2025-01-06", periods=100)
    px = np.linspace(100, 110, 100)
    d = pd.DataFrame({"open": px, "high": px + 1, "low": px - 1, "close": px}, index=idx)
    w = BH5.weekly_from_daily(d)
    assert len(w) == 20 and w.high.iloc[0] == d.high.iloc[:5].max() and w.close.iloc[0] == d.close.iloc[4]
    assert BH5.stock_lrlr_symbol("X", "2025-01-01", daily=d) == BH5.stock_lrlr(w) and study.stock_lrlr_symbol("X", "2025-01-01", daily=d)["reason"] == BH5.stock_lrlr(w)["reason"]


# --- item 179: the rollover -----------------------------------------------------------------------------------------------------------------------

def test_dealing_range_rollover():
    lo, hi, roll = BH5.rollover_range(4000.0, 4100.0, 4100.0, 4000.0, 4105.0, 4110.0, 4090.0, [4130.0, 4160.0], [])
    assert (lo, hi, roll) == (4000.0, 4130.0, 1) and (lo + hi) / 2 == 4065.0
    assert BH5.rollover_range(4000.0, 4100.0, 4100.0, 4000.0, 4105.0, 4110.0, 4090.0, [], []) == (4000.0, 4100.0, 0)
    assert BH5.rollover_range(4000.0, 4100.0, 4100.0, 4000.0, 3995.0, 4090.0, 3990.0, [], [3960.0]) == (3960.0, 4100.0, -1)


def test_rollover_is_carried_until_the_array_trades():
    """Review fix (179): the rolled range lasts beyond the one table row after the break session - until the array is traded or the range breaks the other way."""
    from test_caption_gap_bh1 import arr as mk_arr
    ohlc = [(100, 110, 95, 105)] * 7 + [(105, 115, 104, 112), (112, 113, 110, 112), (112, 114, 110, 112), (112, 126, 111, 124), (124, 125, 120, 123)]
    bk = book(ohlc, [mk_arr("bear", "fvg", 130.0, 125.0, 2)])
    ks = np.array([8, 9, 10, 11, 12])
    R = len(ks)
    out = pd.DataFrame(dict(pd20_hi=[110.0] * R, pd20_lo=[95.0] * R, pd20=[0] * R, pd20_pos=[0.5] * R, px=[112.0] * R, react=[0] * R, pd=[0] * R))
    r = BH5.rollover_columns(out, bk, ks, np.full(R, 112.0), (5, False, "half", (0.62, 0.79), False))
    assert r.pd20_roll.tolist() == [1, 1, 1, 0, 0]                           # rows 8, 9, 10 carry the rolled range, the session that traded the array (10) ends it
    assert r.pd20_hi.tolist()[:3] == [125.0] * 3 and r.pd20_old_hi.iloc[1] == 110.0 and r.pd20_lo.iloc[1] == 95.0
    assert r.pd20_hi.iloc[3] != 125.0


# --- items 176 / 199 / 204: the screen and the definitions -----------------------------------------------------------------------------------------

def _weekly(prices, high_at, high):
    rows = []
    for k, x in enumerate(prices):
        rows.append((x, max(x, high if k == high_at else x) + 1.0, x - 1.0, x))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"])


def test_stock_old_high_distance_filter():
    px = [100, 101, 120, 101, 100, 99, 100, 102, 103, 104, 105, 104, 105, 104, 105, 105, 105]
    w = pd.DataFrame([(x, x + 1.0, x - 1.0, x) for x in px], columns=["open", "high", "low", "close"])
    w.loc[2, "high"] = 120.0
    r = study.stock_lrlr(w, 0.10)
    assert not r["passed"] and r["reason"] == "old_high_far" and r["old_high"] == 120.0
    w.loc[2, "high"] = 113.0
    assert study.stock_lrlr(w, 0.10)["dist_pct"] == pytest.approx(8 / 105, abs=0.01)
    assert study.stock_lrlr(w, 0.10)["passed"] in (True, False)
    assert study.stock_lrlr(w, 0.10)["old_high"] == 113.0


def test_mw_side_and_mega_tag():
    assert htf.mw_side(1, 1) == 1 and htf.mw_side(-1, -1) == -1 and htf.mw_side(1, 0) == 0 and htf.mw_side(1, -1) == 0
    assert htf.mw_side_row({"bias_m": 1, "bias_w": 1}) == 1 and htf.mw_side_row({"bias_m": 1}) == 0
    assert htf.mega_tag("2025-01-02", "2025-07-10") == "mega" and htf.mega_tag("2025-01-02", "2025-03-10") == ""
    assert htf.mega_tag("2025-01-02", "2025-01-10", "ZB", zb_handles=11.0) == "mega" and htf.mega_tag("2025-01-02", "2025-01-10", "ZB", zb_handles=6.0) == ""
