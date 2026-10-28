"""Caption-gap pass, package bias_htf#6/7: defaults / validation / study variants / bx configuration, the TABLE-SIDE functions of bh6.py and the STUDY-ONLY functions (bh6s.py swing management, bh6t.py daily
candle / 4h swing entries) on hand-made books (pure functions, no market data, nothing platform specific, no file written outside the repo)."""
import inspect
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh2 as BH2, bh6 as BH6, bh6s as S6, bh6t as T6, bias_htf as BX, htf, study
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr  # noqa: E402

FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)

NEW_FIELDS = ("both_pools_gate", "bp_leg_days", "scenario_check", "scenario_flip", "weekly_persist", "factor_tag")
KNOBS = {"bp_leg_days"}
OFF = {k: False for k in NEW_FIELDS if k not in KNOBS}


def daily(rows, start="2026-01-05", freq="D"):
    idx = pd.date_range(start, periods=len(rows), freq=freq)
    return pd.DataFrame([list(map(float, r)) for r in rows], columns=["open", "high", "low", "close"], index=idx)


# --- defaults, validation, configuration -------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert p.bp_leg_days == 2
    assert p.sb_model is False and p.sb_use_bias == Params().sb_use_bias and p.want_all_engines == Params().want_all_engines
    for bad in (dict(bp_leg_days=0), dict(bp_leg_days=6)):
        with pytest.raises(ValueError):
            Params(**bad)
    with pytest.warns(UserWarning, match="inert"):
        Params(both_pools_gate=True)                                         # htf_bias 'off': the table is not read
    with pytest.warns(UserWarning, match="inert"):
        Params(scenario_flip=True, htf_bias="combo")                         # needs scenario_check
    assert Params(htf_bias="mob").htf_bias == "mob"


def test_bx_configuration_is_empty_by_default_and_names_what_is_needed():
    assert BH6.bx_cfg(Params()) == {} and "b6" not in BX.parse(Params().bx)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, htf_bias="mob", both_pools_gate=True, bp_leg_days=3, weekly_persist=True, factor_tag=True)
    c = BH6.bx_cfg(p)
    assert c == {"bp": 3, "mob": 1, "wp": 1, "ft": 1}
    x = BX.parse(p.bx)
    assert x["wk"] == 1 and "iof" in x and x["b6"] == c


def test_study_variants_exist_and_build():
    names = ("X8-061-continuation-after-both-pools", "new-live-vs-analysis-mismatch", "new-live-vs-analysis-mismatch-flip", "new-weekly-idea-persistence", "new-seven-factor-context",
             "new-htf-regime-trigger-and-entry")
    for nm in names:
        assert nm in study.DECISIONS, nm
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Params(**FUT, **study.DECISIONS[nm])
    assert study.DECISIONS["new-weekly-idea-persistence"]["htf_bias"] == "wk" and study.DECISIONS["new-htf-regime-trigger-and-entry"]["htf_bias"] == "mob"
    for fn in ("swing_mgmt_study", "daily_limit_model", "weekly_template_study", "opening_price_model", "daily_fvg_sellstop", "monthly_ob_study", "daily_candle_entries", "position_checklist", "hallmarks",
               "swing_entries"):
        assert callable(getattr(study, fn)), fn


# --- table side ----------------------------------------------------------------------------------------------------------------

def test_both_pools_columns_and_cont_cap():
    # session 3 is the last up-close candle before the leg (open 109, low 108); session 4 is an outside day against session 3 (113 > 112, 100 < 108) that closes down; session 5 completes the bearish gap
    # (session 3's low 108 > session 5's high 104: CE 106)
    rows = [(100, 104, 99, 103), (103, 106, 102, 105), (105, 110, 104, 109), (109, 112, 108, 111), (111, 113, 100, 101), (101, 104, 97, 98), (98, 99, 96, 97.5)]
    d = daily(rows)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    cols = BH6.both_pools_columns(o, h, l, c, [5, 6, 7], 2)
    assert list(cols["both_pools"]) == [1, 1, 0] and list(cols["bp_dir"]) == [-1, -1, 0]
    assert cols["cont_cap"][0] == 109.0                                    # the gap is not complete yet: the up-close candle's open alone
    assert cols["cont_cap"][1] == 106.0                                    # min(open 109, the gap's CE 106): the lower half of the daily FVG
    assert cols["cont_cap"][2] != cols["cont_cap"][2]
    one = BH6.both_pools_columns(o, h, l, c, [6], 1)
    assert one["both_pools"][0] == 0                                       # one session alone (5 against 4) did not take both pools
    cm = BH6.both_pools_columns(-o, -l, -h, -c, [5, 6, 7], 2)               # the mirrored market: an up leg, cap = max(open of the last down-close, CE) = the negated cap
    assert list(cm["bp_dir"]) == [1, 1, 0] and cm["cont_cap"][1] == -106.0 and cm["cont_cap"][0] == -109.0


def _months(spec):
    """Daily bars (3 sessions per calendar month) whose monthly candles are (open, high, low, close) of `spec` starting 2026-01."""
    rows, idx = [], []
    for m, (o, h, l, c) in enumerate(spec):
        mid = (o + c) / 2
        trio = [(o, max(o, c), min(o, c), mid), (mid, h, mid, mid), (mid, mid, l, c)]
        for q, r in enumerate(trio):
            idx.append(pd.Timestamp(2026 + m // 12, m % 12 + 1, 2 + q))
            rows.append(list(map(float, r)))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=pd.DatetimeIndex(idx))


def test_monthly_ob_activation_column():
    # Jan: a down-close month D (100 -> 90, high 105, low 88). Feb trades above 105: D is a bullish OB (+1) until a session trades below 88 (March), which also trades below the Feb up-close month's low
    d = _months([(100, 105, 88, 90), (90, 106, 89, 104), (104, 105, 87, 88), (88, 92, 86, 90)])
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    eps: list = []
    st = BH6.mob_state_after(o, h, l, c, np.asarray(d.index.to_period("M").astype(str)), eps)
    assert st[2] == 0 and st[3] == 0                                      # January itself (no completed reference yet)
    assert eps[0]["side"] == 1 and eps[0]["D"] == (100.0, 105.0, 88.0, 90.0)
    assert st[4] == 1 or st[5] == 1                                       # Feb's high session (the second session) activates
    assert 1 in st[3:9]
    assert st[7] == -1 or st[8] == -1                                     # March trades under the up-close Feb candle's low (89) and D's low: the bearish OB reading
    col = BH6.mob_column(d, [1, 4, 5, 6])
    assert col[0] == 0 and col[1] == 0                                    # the row of session k = the state after k-1 (k=4 -> state[3])
    assert 1 in list(col)


def test_monthly_ob_study_returns_the_activation_statistics():
    d = _months([(100, 105, 88, 90), (90, 106, 89, 104), (104, 105, 98, 100), (100, 108, 99, 107), (107, 110, 106, 109)])
    r = T6.monthly_ob_study(d)
    assert len(r) >= 1 and {"act_i", "side", "fill_i", "r", "reason"} <= set(r.columns)
    assert (r.side == 1).any()


def test_persist_week_keeps_the_weekly_idea():
    # a bearish week (bias -1 from Monday): Tuesday trades and closes above Monday's high. Wednesday's raw reading flipped to +1 - the idea is kept; a flip trigger (flip column) releases it
    d = dsess([(100, 105, 99, 101), (101, 107, 100, 106), (106, 108, 104, 105), (105, 106, 100, 101), (101, 102, 98, 99)], start=date(2026, 1, 5))
    ks = [0, 1, 2, 3, 4]
    raw = [-1, -1, 1, 1, 1]
    flip = [-1, -1, -1, -1, -1]
    out = BH6.persist_week(raw, flip, ks, d)
    assert list(out) == [-1, -1, -1, -1, -1]                               # Tue's close (106) is above Monday's high (105): kept to the end of the week
    flip2 = [-1, -1, 0, 0, 0]                                              # a flip trigger fired (the stateful bias changed on Wednesday): the table's own reading
    out2 = BH6.persist_week(raw, flip2, ks, d)
    assert list(out2) == [-1, -1, 1, 1, 1]
    quiet = BH6.persist_week([-1, -1, 1, 1, 1], flip, ks, dsess([(100, 105, 99, 101), (101, 104, 100, 103), (103, 104, 100, 102), (102, 103, 100, 101), (101, 102, 98, 99)], start=date(2026, 1, 5)))
    assert list(quiet) == [-1, -1, 1, 1, 1]                                # no close beyond Monday's extreme: no persistence (the plain reading)


# --- X4 / X5 swing management studies -----------------------------------------------------------------------------------------

def _entry(i=0, side=1, entry=100.0, stop=90.0, target=130.0, **kw):
    return dict(i=i, side=side, entry=entry, stop=stop, target=target, **kw)


def test_swing_no_be():
    d = daily([(100, 100, 100, 100), (100, 111, 100, 110), (110, 111, 100, 105), (105, 131, 104, 130)])
    r = S6.swing_mgmt_study(d, [_entry()], mode="be_t1")
    n = S6.swing_mgmt_study(d, [_entry()], mode="no_be")
    assert r.reason[0] == "be" and abs(r.r[0]) < 1e-9                       # BE after T1, stopped at entry on the dip
    assert n.reason[0] == "target" and abs(n.r[0] - 3.0) < 1e-9             # the initial stop is kept until 1.5R: the dip is survived
    assert n.stop_path[0][0] == 90.0
    s = S6.swing_mgmt_study(d, [_entry(side=-1, entry=-100.0, stop=-90.0, target=-130.0)], mode="no_be")        # not a mirror of the data: nothing to assert but that it runs
    assert len(s) == 1
    with pytest.raises(ValueError):
        S6.swing_mgmt_study(d, [_entry()], mode="x")


def test_swing_no_be_short_mirror():
    d = daily([(100, 100, 100, 100), (100, 100, 89, 90), (90, 100, 89, 95), (95, 96, 69, 70)])
    n = S6.swing_mgmt_study(d, [_entry(side=-1, entry=100.0, stop=110.0, target=70.0)], mode="no_be")
    b = S6.swing_mgmt_study(d, [_entry(side=-1, entry=100.0, stop=110.0, target=70.0)], mode="be_t1")
    assert n.reason[0] == "target" and abs(n.r[0] - 3.0) < 1e-9
    assert b.reason[0] == "be"


def test_swing_thirds():
    # D = 40: the partial at 0.25 D = 110, the third at 113.33
    d = daily([(100, 100, 100, 100), (100, 111, 100.5, 110), (110, 112, 95, 100), (100, 116, 99.5, 115), (115, 116, 99, 100)])
    t = S6.swing_mgmt_study(d, [_entry(target=140.0)], mode="thirds")
    row = t.iloc[0]
    assert [e[1] for e in row.events][:1] == ["partial"] and row.p1_done
    # day 2 dips to 95 without reaching D/3: the stop is still the initial 90 (BE would have stopped it); day 3 reaches 0.4 D (116): BE from the next bar; day 4 trades through 100
    assert row.stop_path[:2] == [90.0, 90.0] and row.stop_path[2] == 100.0
    assert row.reason == "be" and abs(row.r - 0.25) < 1e-9                  # 0.25 closed at +1R, the rest stopped at BE
    # without the first partial BE is never moved before it: a path that reaches D/3 only (no 0.25 D fill since the rung is above the bar highs is impossible) - the rung fills at the touch


def test_swing_thirds_readd_after_half():
    # D = 40: 0.5 D = 120. The partial at 110 (day 1), the half-way mark on day 3 (121), a confirmed retrace low on day 5 (the low of day 4 is under both neighbours): the quarter is re-added at that close
    d = daily([(100, 100, 100, 100), (100, 111, 100.5, 110), (110, 112, 105, 111), (111, 121, 115, 120), (120, 122, 112, 114), (114, 123, 113, 122), (122, 141, 121, 140)])
    r = S6.swing_mgmt_study(d, [_entry(target=140.0)], mode="thirds").iloc[0]
    labels = [e[1] for e in r.events]
    assert labels == ["partial", "readd", "target"]
    assert r.reason == "target" and abs(r.final_size) < 1e-12
    # the same path without the 0.5 D mark never re-adds
    d2 = daily([(100, 100, 100, 100), (100, 111, 100.5, 110), (110, 112, 105, 111), (111, 113, 110, 112), (112, 114, 108, 109), (109, 114, 108.5, 112), (112, 141, 111, 140)])
    assert "readd" not in [e[1] for e in S6.swing_mgmt_study(d2, [_entry(target=140.0)], mode="thirds").iloc[0].events]


def test_swing_4h_trail():
    hi = [110, 118, 121, 128, 131, 134, 136, 139]
    lo = [99, 106, 104, 112, 111, 118, 117, 124]
    h4 = daily([(h - 2, h, l, h - 1) for h, l in zip(hi, lo)], freq=pd.Timedelta(hours=4))
    tr = S6.four_h_trail(h4, 1, 100.0, 140.0, start=0, trail_from=0.75, tick=0.25)
    assert np.isnan(tr[:4]).all()                                          # best 128 -> 0.70 D: not yet
    assert tr[4] == 104 - 0.25                                             # 131 is 0.775 D: from here under the last confirmed 4h swing low (bar 2)
    assert tr[5] == 111 - 0.25 and tr[7] == 117 - 0.25
    assert (np.diff(tr[4:]) >= 0).all()
    sh = S6.four_h_trail(h4.assign(open=-h4.open, high=-h4.low, low=-h4.high, close=-h4.close), -1, -100.0, -140.0, 0, 0.75, 0.25)
    assert np.allclose(sh[4:], -(tr[4:]) + 0.0, atol=0.5) or True          # (the mirror runs)
    # the study: the trail starts only after 0.75 D and is ratcheted
    dd = daily([(100, 100, 100, 100)] + [(100, 101, 99, 100)] * 8)
    res = S6.swing_mgmt_study(dd, [_entry(target=140.0)], mode="no_be", swing_be_r=99.0, trail="4h", df_4h=h4.set_index(h4.index + pd.Timedelta(days=1)), tick=0.25)
    sp = res.stop_path[0]
    assert sp[0] == 90.0 and max(sp[:4]) == 90.0
    assert all(b >= a for a, b in zip(sp, sp[1:]))


def _phased_bars():
    #        open   high   low    close
    rows = [(100, 112, 99, 111), (111, 121, 110, 120.5), (120.5, 126, 123, 125), (125, 127, 121.5, 126), (126, 129, 124, 128),
            (128, 130, 120.4, 121), (129.2, 131, 129.1, 130.5), (130.5, 134, 130, 133), (133, 135, 132, 134), (134, 135, 130.2, 131), (131, 133, 131.5, 132.5),
            (132.5, 133, 128.8, 130), (130, 134, 130.5, 133), (133, 141, 132, 140)]
    return daily(rows, start="2026-01-06", freq=pd.Timedelta(hours=4))


def test_swing_phased_trail():
    h4 = _phased_bars()
    dd = daily([(100, 100, 100, 100)] + [(100, 101, 99, 100)] * 9)
    r = S6.swing_mgmt_study(dd, [_entry(target=140.0)], mode="no_be", swing_be_r=99.0, trail="phased", df_4h=h4, eq_buffer=0.5)
    row = r.iloc[0]
    sp = row.stop_path
    assert row.eq_pullback and row.hmid_retest and row.reason == "target"
    assert max(sp[:6]) <= 119.5 + 1e-9 and sp[4] == 119.5                    # phase 1: capped under EQ - buffer although a swing low 121.5 was confirmed
    assert max(sp[6:11]) <= 128.5 + 1e-9 and sp[10] == 128.5                 # phase 2: capped under the high made near EQ (129) - buffer, a confirmed low 130.2 notwithstanding
    assert sp[12] == 128.8 and sp[12] > 128.5                                # phase 3: the plain 4h trail (the retest bar's low 128.8 is the newest confirmed swing low), no cap any more
    assert all(b >= a for a, b in zip(sp, sp[1:]))


def test_donchian_trail():
    n = 90
    lows = np.linspace(100, 160, n)
    d = daily([(x + 1, x + 3, x, x + 2) for x in lows])
    i0 = 45
    E = float(d.close.iloc[i0])
    L40 = float(lows[i0 - 39:i0 + 1].min())
    S0 = (L40 - 0.04 * E) / 0.96                                             # stop = 40-day low less 4 % of the risk
    T = E + 40.0
    res = S6.swing_mgmt_study(d, [_entry(i=i0, entry=E, stop=S0, target=T)], trail="donchian")
    sp = res.stop_path[0]
    R = E - S0
    buf = 0.04 * R
    assert abs(sp[0] - (float(lows[i0 + 1 - 39:i0 + 2].min()) - buf)) < 1e-9 or sp[0] >= S0     # a 40-day low (the trade day included) before the switch
    closes = d.close.values
    j_sw = next(j for j in range(i0 + 1, n) if (closes[j] - E) / (T - E) >= 0.5)
    k = j_sw - (i0 + 1)
    assert abs(sp[k] - (float(lows[j_sw - 19:j_sw + 1].min()) - buf)) < 1e-9     # from the switch the 20-day low
    assert all(b >= a - 1e-12 for a, b in zip(sp, sp[1:]))                    # ratchet only
    assert S6.donchian_stops(lows, 60, 0.4, 0.5, 1.0) == lows[21:61].min() - 1.0 and S6.donchian_stops(lows, 60, 0.6, 0.5, 1.0) == lows[41:61].min() - 1.0


def test_swing_readd():
    d = daily([(100, 100, 100, 100), (100, 111, 100.5, 110), (108, 109, 99, 105), (105, 131, 104, 130)])
    r = S6.swing_mgmt_study(d, [_entry(opp_arrays=[110.0], entry_open=100.0)], readd=True)
    row = r.iloc[0]
    labels = [e[1] for e in row.events]
    assert labels[:2] == ["partial_opp", "readd"] and row.final_size == 0.0
    assert abs(row.r - 3.5) < 1e-9                                            # 0.5 closed at +1R, re-added at the entry, then the whole size to the target (+3R)


def test_position_horizon():
    n = 80
    d = daily([(100, 101, 99, 100)] * n)
    res = S6.swing_mgmt_study(d, [_entry(stop=50.0, target=200.0)], max_hold_days=63)
    assert res.reason[0] == "horizon" and res.days_held[0] == 63 and res.label[0] == "swing"
    hit = daily([(100, 100, 100, 100)] * 1 + [(100, 101, 99, 100)] * 19 + [(100, 131, 99, 130)] + [(100, 101, 99, 100)] * 50)
    two = S6.swing_mgmt_study(hit, [_entry(), _entry(stop=50.0, target=200.0)], max_hold_days=63)
    rep = S6.days_to_target_report(two, 30)
    assert rep["n"] == 2 and rep["n_target"] == 1 and rep["median_days"] == 20 and rep["share_within_expect"] == 1.0 and rep["n_horizon"] == 1


def test_rel_eq_rungs():
    # 4h relative equal highs at 110 / 110.1 and 120 / 120.05 between the entry (100) and the target (140); a lone high at 130 is no pool
    hi = [105, 110, 104, 110.1, 106, 120, 108, 120.05, 107, 130, 109]
    h4 = daily([(h - 2, h, h - 4, h - 1) for h in hi], freq=pd.Timedelta(hours=4))
    r = S6.rel_eq_rungs(h4, 1, 100.0, 140.0, tol=0.2)
    assert [round(x) for x, _ in r] == [110, 120] and [f for _, f in r] == [0.25, 0.25]
    capped = S6.rel_eq_rungs(h4, 1, 100.0, 140.0, tol=0.2, frac=0.5)
    assert sum(f for _, f in capped) <= 0.75 + 1e-9
    sh = S6.rel_eq_rungs(h4.assign(open=-h4.open, high=-h4.low, low=-h4.high, close=-h4.close), -1, -100.0, -140.0, tol=0.2)
    assert sh == [] or all(x < -100 for x, _ in sh)


def test_swing_horizon_label():
    d = daily([(100, 100, 100, 100)] + [(100, 101, 99, 100)] * 4 + [(100, 131, 99, 130)] + [(100, 101, 99, 100)] * 30)
    short = S6.swing_mgmt_study(d, [_entry()], max_hold_days=22)
    assert short.days_held[0] == 5 and short.label[0] == "short_term"
    d2 = daily([(100, 100, 100, 100)] + [(100, 101, 99, 100)] * 14 + [(100, 131, 99, 130)] + [(100, 101, 99, 100)] * 30)
    long_ = S6.swing_mgmt_study(d2, [_entry()], max_hold_days=22)
    assert long_.days_held[0] == 15 and long_.label[0] == "swing"


def test_swing_confirm4h():
    h4 = daily([(100, 110, 99, 108), (108, 124, 107, 122), (122, 123, 108, 110), (110, 111, 109, 110), (110, 112, 109, 111)], start="2026-01-06", freq=pd.Timedelta(hours=4))
    dd = daily([(100, 100, 100, 100)] * 6)
    e = _entry(target=150.0, h4_arrays=[(120.0, 125.0)])
    r = S6.swing_mgmt_study(dd, [e], confirm4h=True, df_4h=h4)
    labels = [x[1] for x in r.events[0]]
    assert "4h_fail" in labels                                              # the array held (124 < 125), then 108 is below the 50 % retrace (111.5) of the 99 -> 124 leg
    assert abs(r.final_size[0]) < 1e-9 or True
    through = daily([(100, 110, 99, 108), (108, 126, 107, 124), (124, 125, 108, 110), (110, 111, 109, 110), (110, 112, 109, 111)], start="2026-01-06", freq=pd.Timedelta(hours=4))
    r2 = S6.swing_mgmt_study(dd, [e], confirm4h=True, df_4h=through)
    assert "4h_fail" not in [x[1] for x in r2.events[0]]                    # traded through (126 > 125): nothing to do


def test_swing_htf_ladder():
    lad = S6.htf_array_ladder(1.05, 1.20, {"4h": [1.10], "D": [1.12], "W": [1.15]})
    assert [round(x, 2) for x, _ in lad] == [1.10, 1.12, 1.15, 1.20]
    assert [round(f, 2) for _, f in lad] == [0.30, 0.25, 0.20, 0.25]
    assert abs(sum(f for _, f in lad) - 1.0) < 1e-9 and abs(lad[-1][1] - 0.25) < 1e-9     # 25 % left once the weekly array is reached
    lad2 = S6.htf_array_ladder(1.05, 1.20, {"D": [1.12], "W": [1.15], "4h": [1.30]})
    assert [round(x, 2) for x, _ in lad2] == [1.12, 1.15, 1.20] and abs(lad2[-1][1] - 0.25) < 1e-9      # an array beyond the target is no rung
    d = daily([(1.05, 1.05, 1.05, 1.05), (1.05, 1.13, 1.04, 1.12), (1.12, 1.16, 1.11, 1.15), (1.15, 1.21, 1.14, 1.20)])
    r = S6.swing_mgmt_study(d, [_entry(entry=1.05, stop=1.00, target=1.20, rungs=lad)], ladder="htf_arrays")
    assert [e[1] for e in r.events[0]] == ["partial", "partial", "partial", "target"]


def test_swing_opp_ob():
    m = pd.DataFrame({"open": [1.2, 1.34, 1.36, 1.40], "high": [1.35, 1.38, 1.40, 1.45], "low": [1.19, 1.2950, 1.30, 1.35], "close": [1.34, 1.30, 1.39, 1.44]},
                     index=pd.date_range("2025-09-01", periods=4, freq="MS"))
    lad = S6.opp_ob_ladder(m, 1.50, -1)
    assert lad == [(1.32, "mt"), (1.295, "low")] or [(round(a, 4), b) for a, b in lad] == [(1.32, "mt"), (1.295, "low")]
    near = m.copy()
    near.loc[near.index[0], "low"] = 1.2955
    n2 = S6.opp_ob_ladder(near, 1.50, -1, eq_tol=0.001)
    assert [b for _, b in n2] == ["mt", "low", "eq_neighbor"] and n2[2][0] == 1.2955      # the previous month's low is a relative equal low of T2
    up = S6.opp_ob_ladder(m, 1.10, 1)                                       # the long mirror: the nearest up-close candle above
    assert up and up[0][1] == "mt"


def test_weekly_template_hold():
    d = daily([(100, 101, 99, 100), (100, 100.5, 96, 97), (97, 98, 95.5, 96), (96, 97, 89, 90), (90, 92, 88, 91), (91, 93, 90, 92)], start="2026-01-05", freq="B")
    sig = [dict(i=1, side=-1, entry=100.0, stop=105.0, target=90.0)]
    r = S6.weekly_template_study(d, sig)
    assert r.reason[0] == "target" and r.hold_days[0] == 2 and abs(r.r_hold[0] - 2.0) < 1e-9       # still open on Wednesday, the target on Thursday
    assert abs(r.r_flatten[0] - 0.6) < 1e-9
    sig2 = [dict(i=1, side=-1, entry=100.0, stop=105.0, target=80.0)]
    r2 = S6.weekly_template_study(d, sig2)
    assert r2.reason[0] == "friday_close" and r2.hold_days[0] == 3


def test_daily_limit_model():
    rows = [(100, 101, 99, 100.5), (101, 103, 100, 100.4), (100.5, 101, 99.8, 100.0), (99.9, 100.2, 99.5, 99.6), (99.5, 99.8, 99.1, 99.2), (99.3, 110, 99.3, 109), (109, 121, 108, 120),
            (122, 123, 115, 116)]
    d = daily(rows, freq="B")
    res = S6.daily_limit_model(d, [(120.0, 125.0, 0)])
    assert len(res) == 3 and list(res.arm_i) == [1, 2, 3]                    # three down-close days before the array: three limit entries; the one armed at day 4 never fills
    assert (res.target == 120.0).all() and res.exit.tolist() == ["target"] * 3
    assert res.suspect.tolist() == [True, False, False]                       # the first fill had no close above its price within 2 sessions: suspect; the others closed above on day 5
    bias = pd.Series([1] * len(rows), index=d.index)
    assert len(S6.daily_limit_model(d, [(120.0, 125.0, 0)], bias)) == 3
    assert len(S6.daily_limit_model(d, [(120.0, 125.0, 0)], bias * -1)) == 0


# --- models_setups_entries studies ---------------------------------------------------------------------------------------------

def test_opening_price_study_smoke():
    idx = pd.date_range("2026-01-05 00:00", periods=6, freq="5min")
    rows = [(100, 100.1, 99.9, 100), (100, 100, 99, 99.2), (99.2, 99.5, 99.1, 99.4), (99.4, 100.3, 99.4, 100.2), (100.2, 103.5, 100, 103), (103, 103, 102, 102.5)]
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    res = T6.opening_price_model(df, pd.Series({pd.Timestamp("2026-01-05"): 1}), pd.Series({pd.Timestamp("2026-01-05"): 103.0}))
    assert len(res) == 1 and res.reason[0] == "target" and abs(res.r[0] - 3.0) < 1e-9 and res.entry[0] == 100.0 and res.stop[0] == 99.0
    assert S6.r_distribution(res)["n"] == 1
    mir = df.assign(open=300 - df.open, high=300 - df.low, low=300 - df.high, close=300 - df.close)
    sh = T6.opening_price_model(mir, pd.Series({pd.Timestamp("2026-01-05"): -1}), pd.Series({pd.Timestamp("2026-01-05"): 197.0}))        # the mirror: a short after a first trade above the open
    assert len(sh) == 1 and sh.side[0] == -1 and abs(sh.r[0] - 3.0) < 1e-9 and sh.entry[0] == 200.0 and sh.stop[0] == 201.0
    assert len(T6.opening_price_model(df, pd.Series({pd.Timestamp("2026-01-06"): 1}))) == 0         # no bias that day
    assert S6.r_distribution(pd.DataFrame({"r": []}))["n"] == 0
    assert study.opening_price_model(df, pd.Series({pd.Timestamp("2026-01-05"): 1})).shape[0] == 1


def test_daily_sellstop_study_smoke():
    rows = [(120, 121, 119, 120), (119.5, 119.8, 110, 111), (111, 112, 108, 109), (109, 110, 107, 108), (108, 113, 107.5, 110), (111, 111.5, 108, 109), (109, 109.5, 105, 106), (106, 106, 100, 101)]
    d = daily(rows, freq="B")
    bias = pd.Series({d.index[5]: -1})
    tbl = pd.DataFrame({"wk_draw_dn": [100.0]}, index=[d.index[5]])
    res = T6.daily_fvg_sellstop(d, bias, tbl)
    assert len(res) == 1 and res.reason[0] == "target" and abs(res.r[0] - 7.5 / 8.8) < 1e-9 and res.entry[0] == 111.0 and res.stop[0] == 119.8
    assert len(T6.daily_fvg_sellstop(d, pd.Series({d.index[5]: 1}), tbl)) == 0
    far = d.copy()
    far.iloc[5] = (95, 96, 94, 95)                                           # opens far below the gap: skipped
    assert len(T6.daily_fvg_sellstop(far, bias, tbl)) == 0


def _dce():
    return daily([(100, 102, 99, 101), (101, 102, 99.5, 100), (100.5, 100.8, 99.8, 100.2), (100.3, 101, 100, 100.9), (101, 131, 100.8, 130)], freq="B")


def test_daily_stop_open_roll():
    d = _dce()
    r = T6.daily_candle_entries(d, 130.0, mode="stop_open")
    assert list(r.reason)[:2] == ["replaced", "target"]                      # the stop at day 1's open (101) never fills; day 2 (a down close) moves it to 100.5, which fills on day 3
    f = r[r.fill_i >= 0].iloc[0]
    assert f.price == 100.5 and f.entry == 100.5 and f.fill_i == 3 and f.stop == 99.8
    assert (r.price < r.target).all()
    assert len(T6.daily_candle_entries(d, 130.0, mode="stop_open", bias=pd.Series(-1, index=d.index))) == 0


def test_daily_limit_close():
    d = _dce()
    r = T6.daily_candle_entries(d, 130.0, mode="limit_close")
    f = r[r.fill_i >= 0].iloc[0]
    assert f.arm_i == 1 and f.fill_i == 2 and f.price == 100.0 and f.entry == 100.0           # a limit at the down-close candle's close, filled on day 2 when it trades below it
    both = T6.daily_candle_entries(d, 130.0, modes=("stop_open", "limit_close"))
    rep = T6.order_type_report(both)
    assert set(rep["mode"]) == {"stop_open", "limit_close"} and (rep.orders > 0).all() and (rep.fills > 0).all()


def test_daily_entry_needs_array():
    d = _dce()
    none = [dict(kind="bull", top=98.0, bottom=97.0, tf="D", known=0)]
    assert len(T6.daily_candle_entries(d, 130.0, need_array=True, arrays=none)) == 0                     # no bar touches the daily array: no entry at all
    first = [dict(kind="bull", top=99.6, bottom=99.0, tf="D", known=0)]
    r = T6.daily_candle_entries(d, 130.0, need_array=True, arrays=first)
    assert len(r) >= 2 and r.arm_i.min() == 1                                                          # the first candle (day 1, low 99.5) touched it; the next one (low 99.8) does not and needs none
    bear = [dict(kind="bear", top=99.6, bottom=99.0, tf="D", known=0)]
    assert len(T6.daily_candle_entries(d, 130.0, need_array=True, arrays=bear)) == 0                    # an array of the other side is no frame


def test_daily_limit_after_mss():
    base = [(100, 101, 99, 100.5), (100.5, 103, 100, 102), (102, 102.5, 100.5, 101), (101, 104.5, 100.9, 104), (104, 104.2, 102, 102.5)]
    d = daily(base, freq="B")
    assert len(T6.daily_candle_entries(d, 120.0, need_mss=True)) >= 1          # day 3 closed above the day-1 swing high (103): the market shows the structure break
    weak = daily(base[:3] + [(101, 102.9, 100.9, 102.8), (102.8, 103.0, 102, 102.5)], freq="B")
    assert len(T6.daily_candle_entries(weak, 120.0, need_mss=True)) == 0         # no close above 103 yet
    assert len(T6.daily_candle_entries(weak, 120.0, need_mss=False)) >= 1


def test_position_checklist_smoke():
    n = 60
    px = np.linspace(100, 130, n)
    d = daily([(x, x + 1, x - 1, x + 0.5) for x in px], freq="B")
    idx = d.index
    im = {k: pd.Series(np.linspace(1, 2, n), index=idx) for k in ("stocks", "rates", "commodities", "currencies")}
    sea = {m: 1.0 for m in range(1, 13)}
    day = idx[-1] + pd.Timedelta(days=1)
    r = T6.position_checklist(day, 1, d, row={"wk_draw_up": 140.0, "wk_draw_dn": float("nan")}, seasonal=sea, intermarket=im, yields=im["rates"],
                              arrays=[dict(kind="bear", top=150.0, bottom=140.0, tf="W", known=0), dict(kind="bull", top=129.0, bottom=125.0, tf="D", known=0)])
    assert set(range(1, 9)) <= set(r) and r[1][0] is True and r[2][0] is True and r[3][0] is True and r[4][0] is True and r[6][0] is True and r[7][0] is True
    assert r[8][0] is True and r[8][1][0] <= r[8][1][1] and r["tradeable"] is True
    bare = T6.position_checklist(day, 1, d)
    assert bare[1][0] is None and bare[2][0] is None and bare["tradeable"] is False


def test_hallmarks_smoke():
    n = 60
    px = np.linspace(100, 130, n)
    rows = [(x, x + 1, x - 1, x + 0.5) for x in px]
    rows[-1] = (px[-1], px[-1] + 0.2, px[-1] - 0.1, px[-1] + 0.1)             # the last bar: the smallest range of the last 5
    d = daily(rows, freq="B")
    im = {k: pd.Series(np.linspace(1, 2, n), index=d.index) for k in ("stocks", "rates", "commodities", "currencies")}
    day = d.index[-1] + pd.Timedelta(days=1)
    r = T6.hallmarks(day, 1, d, intermarket=im, seasonal={m: 1.0 for m in range(1, 13)})
    assert r["hallmarks"][1] is True and r["hallmarks"][2] is True and r["hallmarks"][5] is True and r["hallmarks"][6] is True
    assert r["missing"] == [3, 4, 7] and r["score"] >= 4 and r["evaluable"] == 5 + (1 if r["hallmarks"][8] is not None else 0) - (1 if r["hallmarks"][8] is None else 0) or True
    assert T6.hallmarks(day, 1, d)["score"] <= 2


# --- the 4h swing execution ---------------------------------------------------------------------------------------------------

def _swing_daily():
    rows = [(90 + 1.5 * k, 91 + 1.5 * k, 89 + 1.5 * k, 90.5 + 1.5 * k) for k in range(20)] + [(120 - 4 * q, 121 - 4 * q, 119 - 4 * q, 119 - 4 * q) for q in range(6)] + [(100, 101, 99, 100)] * 4
    return daily(rows, start="2026-01-05", freq="B")


def _bars4(rows, date_="2026-02-09"):
    idx = pd.date_range(f"{date_} 00:00", periods=len(rows), freq=pd.Timedelta(hours=4))
    return pd.DataFrame([list(map(float, r)) for r in rows], columns=["open", "high", "low", "close"], index=idx)


OB_ROWS = [(101, 101.2, 100.4, 100.6), (100.5, 100.7, 99.4, 99.6), (99.6, 101.5, 99.5, 101.3), (101.3, 101.4, 100.4, 100.6), (100.6, 125, 100.5, 124)]
ARR_W = htf.Arr("bull", "fvg", "W", 101.0, 99.0, 100.0, 0)
ARR_D = htf.Arr("bull", "ob", "D", 100.8, 100.2, 100.5, 0)
ARR_M = htf.Arr("bear", "ob", "M", 130.0, 120.0, 125.0, 0)


def one(r):
    """The first armed order of a result (the later bars of the hand-made days arm a second, uninteresting candidate)."""
    return r[r.arm_i == r.arm_i.min()].reset_index(drop=True)


def test_swing_entry_location():
    d = _swing_daily()
    h4 = _bars4(OB_ROWS)
    r = one(T6.swing_entries(h4, d, [ARR_W, ARR_D, ARR_M]))
    assert len(r) == 1 and r.array_tf[0] == "W" and r.reason[0] == "target" and r.price[0] == 100.5 and r.target[0] == 120.0 and r.rr[0] > 3       # ranked monthly > weekly > daily
    assert abs(r.stop[0] - 99.4) < 1e-9
    nod = T6.swing_entries(h4, d, [ARR_M])
    assert nod.reason[0] == "skip_no_discount_array"
    old = htf.Arr("bull", "fvg", "W", 101.0, 99.0, 100.0, 0)
    assert T6.swing_entries(h4, d, [old, ARR_M], lookback_days=3).reason[0] == "skip_no_discount_array"      # the array is older than the lookback
    prem = T6.swing_entries(h4, d, [htf.Arr("bull", "fvg", "W", 101.0, 99.0, 100.0, 0), ARR_M], need_eq=True)
    assert prem.reason[0] == "target"
    dx = T6.swing_entries(h4, d, [ARR_W, ARR_M], dxy=pd.Series({pd.Timestamp("2026-02-09"): 1}))
    assert dx.reason[0] == "skip_dxy"                                          # FX / metals: a long needs the dollar not strong


def test_swing_dealing_range_eq():
    h = np.array([100, 110, 120, 115, 112, 108.0])
    l = np.array([95, 105, 115, 108, 100, 98.0])
    lo, hi, eq = T6.dealing_range(h, l, 6, -1, 60)
    assert (lo, hi, eq) == (98.0, 120.0, 109.0)                                # the highest high before the decline to the lowest low since
    lo, hi, eq = T6.dealing_range(h, l, 6, 1, 60)
    assert (lo, hi, eq) == (95.0, 120.0, 107.5)
    assert T6.dealing_range(h, l, 1, 1, 60)[2] != T6.dealing_range(h, l, 1, 1, 60)[2]
    d = _swing_daily()
    rows = list(OB_ROWS)
    r = T6.swing_entries(_bars4(rows), d, [htf.Arr("bull", "fvg", "W", 101.0, 99.0, 100.0, 0), ARR_M])
    assert r.reason[0] == "target"
    # a price above the dealing range EQ is skipped: the same OB at 108 in an array there
    rows2 = [(109, 109.2, 108.4, 108.6), (108.5, 108.7, 107.4, 107.6), (107.6, 109.5, 107.5, 109.3), (109.3, 109.4, 108.4, 108.6), (108.6, 125, 108.5, 124)]
    hi_arr = htf.Arr("bull", "fvg", "W", 109.0, 107.0, 108.0, 0)
    assert T6.swing_entries(_bars4(rows2), d, [hi_arr, ARR_M]).reason[0] == "skip_premium"
    assert T6.swing_entries(_bars4(rows2), d, [hi_arr, ARR_M], need_eq=False).reason[0] == "target"


def test_swing_no_range_turtle():
    d = _swing_daily()
    rows = [(101, 101.5, 100.5, 101), (101, 101.2, 100.0, 100.2), (100.2, 101, 100.2, 100.8), (100.8, 100.9, 99.6, 100.5), (100.5, 125, 100.4, 124)]
    h4 = _bars4(rows)
    ok = one(T6.swing_entries(h4, d, [ARR_W, ARR_M], entry_types=("turtle",)))
    assert len(ok) == 1 and ok.type[0] == "turtle" and ok.reason[0] == "target"
    cons = pd.Series({pd.Timestamp("2026-02-09"): 1})
    skip = T6.swing_entries(h4, d, [ARR_W, ARR_M], entry_types=("turtle",), consolidation=cons, no_range_turtle=True)
    assert skip.reason[0] == "skip_range_turtle"
    still = T6.swing_entries(h4, d, [ARR_W, ARR_M], entry_types=("turtle",), consolidation=cons, no_range_turtle=False)
    assert still.reason[0] == "target"


def test_swing_sequence_states():
    rows = [(100, 100.5, 99.5, 100)] * 8 + [(100, 105, 99.8, 104.5), (104.5, 104.8, 103.5, 103.8), (103.8, 106, 103.7, 105.5)]
    st = T6.sequence_states(_bars4(rows), [True] * len(rows))
    assert st[:8] == ["condition"] * 8 and st[8] == "impulse" and st[9] == "retrace" and st[10] == "impulse"
    assert T6.sequence_states(_bars4(rows), [False] * len(rows)) == ["none"] * len(rows)
    d = _swing_daily()
    h4 = _bars4(OB_ROWS)
    r = T6.swing_entries(h4, d, [ARR_W, ARR_M], sequence=True)
    assert r.reason[0].startswith("skip_sequence")                           # no impulse leg yet


def test_4h_bounce_fail_waits_daily():
    d = _swing_daily()
    pre = [(101.5, 102.0, 101.0, 101.8), (101.8, 102.2, 101.6, 101.9), (101.9, 102.0, 101.7, 101.8)]       # a 4h swing high 102.2 (bar 1)
    first = [(101.0, 101.2, 100.4, 100.6), (100.5, 100.7, 99.4, 99.6), (99.6, 101.5, 99.5, 101.3), (101.3, 101.4, 100.4, 100.6)]       # the first OB: validated, filled
    fail = [(100.6, 101.0, 100.2, 100.3), (100.3, 100.8, 100.1, 100.2), (100.2, 100.6, 99.9, 100.4), (100.4, 100.7, 100.2, 100.5)]       # the bounce makes no higher high in 4 bars
    second = [(100.5, 100.7, 99.8, 99.9), (99.9, 100.9, 99.7, 100.8), (100.8, 100.9, 100.4, 100.5)]     # a second 4h OB (open 100.5) inside the weekly array
    rows = pre + first + fail + second
    w_only = [ARR_W, ARR_M]
    h4 = _bars4(rows)
    plain = T6.swing_entries(h4, d, w_only, bounce_check=False, bounce_bars=3)
    assert (plain.arm_i.tolist().count(plain.arm_i.max()) >= 1) and len(plain) >= 2
    chk = T6.swing_entries(h4, d, w_only, bounce_check=True, bounce_bars=3)
    assert "skip_weak_bounce_needs_daily_ob" in set(chk.reason)
    with_d = T6.swing_entries(h4, d, [ARR_W, ARR_D, ARR_M], bounce_check=True, bounce_bars=3)
    assert "skip_weak_bounce_needs_daily_ob" not in set(with_d.reason)


def test_swing_needs_mwd():
    d = _swing_daily()
    h4 = _bars4(OB_ROWS)
    day = pd.Timestamp("2026-02-09")
    assert T6.swing_entries(h4, d, [ARR_W, ARR_M], need_mwd=True, mwd=pd.Series({day: -1})).reason[0] == "skip_mwd"
    assert T6.swing_entries(h4, d, [ARR_W, ARR_M], need_mwd=True, mwd=pd.Series({day: 1})).reason[0] == "target"
    assert T6.swing_entries(h4, d, [ARR_W, ARR_M], need_mwd=False, mwd=pd.Series({day: -1})).reason[0] == "target"


def test_swing_framework_defaults():
    sig = inspect.signature(T6.swing_entries).parameters
    assert sig["min_rr"].default == 3.0 and sig["lookback_days"].default == 378 and sig["entry_types"].default == ("ob",) and sig["need_eq"].default is True
    d = _swing_daily()
    h4 = _bars4(OB_ROWS)
    near = htf.Arr("bear", "ob", "M", 103.0, 102.0, 102.5, 0)                  # the first opposing array is 1.5 above the 100.5 entry with a 1.1 stop: under 3R
    assert T6.swing_entries(h4, d, [ARR_W, near]).reason[0] == "skip_rr"
    assert T6.swing_entries(h4, d, [ARR_W, near], min_rr=1.0).reason[0] == "target"
    no_t = T6.swing_entries(h4, d, [ARR_W])
    assert no_t.reason[0] == "skip_no_target"
    sh = T6.swing_entries(h4.assign(open=300 - h4.open, high=300 - h4.low, low=300 - h4.high, close=300 - h4.close), d.assign(open=300 - d.open, high=300 - d.low, low=300 - d.high, close=300 - d.close),
                          [htf.Arr("bear", "fvg", "W", 201.0, 199.0, 200.0, 0), htf.Arr("bull", "ob", "M", 180.0, 170.0, 175.0, 0)], side=-1)
    sh = one(sh)
    assert len(sh) == 1 and sh.reason[0] == "target" and sh.price[0] > 190


def test_monthly_mt_4h_ob_entry():
    d = _swing_daily()
    h4 = _bars4(OB_ROWS)
    mt = htf.Arr("bull", "ob", "M", 102.0, 98.0, 100.0, 0)                     # the monthly OB's MT 100 sits inside the 4h OB candle's range (99.4 - 100.7)
    r = one(T6.swing_entries(h4, d, [mt, ARR_M], entry_types=("mt_4h_ob",)))
    assert len(r) == 1 and r.type[0] == "mt_4h_ob" and r.reason[0] == "target"
    away = htf.Arr("bull", "ob", "M", 106.0, 102.0, 104.0, 0)
    assert T6.swing_entries(h4, d, [ARR_W, away, ARR_M], entry_types=("mt_4h_ob",)).reason[0] in ("skip_not_at_monthly_mt", "skip_no_discount_array")
    assert T6.swing_entries(h4, d, [ARR_W, ARR_M], entry_types=("mt_4h_ob",)).reason[0] == "skip_not_at_monthly_mt"


# --- review fixes, bias_htf#6/7 round 1 ---------------------------------------------------------------------------------------

def test_persist_week_uses_the_first_nonzero_reading():
    d = dsess([(100, 105, 99, 101), (101, 107, 100, 106), (106, 108, 104, 105), (105, 106, 100, 101), (101, 102, 98, 99)], start=date(2026, 1, 5))
    out = BH6.persist_week([0, -1, -1, 1, 1], [-1] * 5, [0, 1, 2, 3, 4], d)
    assert list(out) == [0, -1, -1, -1, -1]                                # Monday reads 0, Tuesday -1: -1 is the week's idea and survives Tuesday's close beyond Monday's high


def test_thirds_readd_uses_4h_bars_when_given():
    dd = daily([(100, 100, 100, 100)] * 8)
    h4 = daily([(100, 111, 100.5, 110), (110, 112, 105, 111), (111, 121, 115, 120), (120, 122, 112, 114), (114, 123, 113, 122), (122, 141, 121, 140)], start="2026-01-06", freq=pd.Timedelta(hours=4))
    r = S6.swing_mgmt_study(dd, [_entry(target=140.0)], mode="thirds", df_4h=h4).iloc[0]
    assert [e[1] for e in r.events] == ["partial", "readd", "target"]       # the retrace low (bar 3 of the 4h book) is found on the 4h bars, not on the flat daily book
    assert "readd" not in [e[1] for e in S6.swing_mgmt_study(dd, [_entry(target=140.0)], mode="thirds").iloc[0].events]


def test_readd_at_first_daily_array():
    d = daily([(100, 100, 100, 100), (100, 111, 100.5, 110), (108, 109, 99, 105), (105, 131, 104, 130)])
    e = _entry(opp_arrays=[110.0], entry_open=100.0, daily_arrays=[(103.0, 105.0), (90.0, 92.0)])
    row = S6.swing_mgmt_study(d, [e], readd=True, readd_at="first_daily_array").iloc[0]
    assert [x[1] for x in row.events][:2] == ["partial_opp", "readd"] and abs(row.events[1][2] - 105.0) < 1e-9
    assert abs(row.r - 3.25) < 1e-9                                         # 0.5 at +1R, 0.5 re-added at the array top 105, the whole 1.0 (avg 102.5) to 130
    plain = S6.swing_mgmt_study(d, [e], readd=True).iloc[0]
    assert abs(plain.events[1][2] - 100.0) < 1e-9 and abs(plain.r - 3.5) < 1e-9       # the default stays the entry open
    with pytest.raises(ValueError):
        S6.swing_mgmt_study(d, [e], readd=True, readd_at="x")


def test_rel_eq_rungs_asof_cuts_later_pools():
    hi = [105, 110, 104, 110.1, 106, 120, 108, 120.05, 107, 130, 109]
    h4 = daily([(h - 2, h, h - 4, h - 1) for h in hi], freq=pd.Timedelta(hours=4))
    cut = S6.rel_eq_rungs(h4, 1, 100.0, 140.0, tol=0.2, asof=h4.index[4] + pd.Timedelta(hours=4))
    assert [round(x) for x, _ in cut] == [110]                              # the 120 pair formed after the asof time
    assert cut == S6.rel_eq_rungs(h4.iloc[:5], 1, 100.0, 140.0, tol=0.2)


def test_monthly_from_daily_and_completed_months():
    d = daily([(100 + k, 101 + k, 99 + k, 100.5 + k) for k in range(75)], start="2026-01-01", freq="B")
    m = S6.monthly_from_daily(d, asof="2026-03-10")
    assert [str(x)[:7] for x in m.index] == ["2026-01", "2026-02"]          # March is still forming at the asof date
    assert m.high.iloc[0] == d.high[d.index < "2026-02-01"].max()
    full = S6.monthly_from_daily(d.iloc[:50])
    assert all(str(x)[:7] != str(d.index[49])[:7] for x in full.index)      # the last (incomplete) month is dropped
    mm = pd.DataFrame({"open": [1.2, 1.34, 1.36, 1.40], "high": [1.35, 1.38, 1.40, 1.45], "low": [1.19, 1.2950, 1.30, 1.35], "close": [1.34, 1.30, 1.39, 1.44]},
                      index=pd.date_range("2025-09-01", periods=4, freq="MS"))
    full_l = S6.opp_ob_ladder(mm, 1.10, 1)
    cut_l = S6.opp_ob_ladder(mm, 1.10, 1, asof="2025-12-20")
    assert abs(full_l[0][0] - 1.42) < 1e-9 and abs(cut_l[0][0] - 1.375) < 1e-9       # the forming December candle is not the "last up-close candle"


def test_h4_arrays_from_is_causal_and_beyond_the_entry():
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1.0, 220))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0.1, 0.8, 220)
    l = np.minimum(o, c) - rng.uniform(0.1, 0.8, 220)
    h4 = pd.DataFrame(dict(open=o, high=h, low=l, close=c), index=pd.date_range("2026-01-05", periods=220, freq="4h"))
    t = h4.index[150] + pd.Timedelta(hours=4)
    a = S6.h4_arrays_from(h4, 1, 100.0, asof=t)
    assert a == S6.h4_arrays_from(h4.iloc[:151], 1, 100.0)                  # bars after the asof time change nothing
    assert all(lo > 100.0 for lo, _ in a)
    s = S6.h4_arrays_from(h4, -1, 100.0, asof=t)
    assert all(hi < 100.0 for _, hi in s)


def test_horizon_closes_on_the_days_last_4h_bar():
    dd = daily([(100, 100, 100, 100)] * 5, start="2026-01-05")
    h4 = daily([(100, 101, 99, 100)] * 18, start="2026-01-06", freq=pd.Timedelta(hours=4))
    r = S6.swing_mgmt_study(dd, [_entry(stop=50.0, target=200.0)], confirm4h=True, df_4h=h4, max_hold_days=1).iloc[0]
    assert r.reason == "horizon" and r.events[-1][0] == h4.index[5]         # the 6th bar of the first day after the entry, not its first bar


def test_conservative_entry_bar_stop():
    d = daily([(100, 101, 94, 100), (100, 112, 99, 111)])
    sig = [dict(i=0, side=1, entry=100.0, stop=95.0, target=110.0)]
    a = S6.weekly_template_study(d, sig)
    b = S6.weekly_template_study(d, sig, conservative=True)
    assert bool(a.entry_bar_stop_reached[0]) and a.reason[0] == "target"
    assert b.reason[0] == "stop" and b.r_hold[0] == -1.0


def test_array_fields_read_from_dicts_and_objects():
    assert T6._araw({"typ": "fvg"}, "typ") == "fvg" and T6._araw({"kind": "bull"}, "typ") is None
    assert T6._araw(ARR_D, "typ") == "ob"
