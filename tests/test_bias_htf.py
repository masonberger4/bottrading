"""Package bias_htf (rule_coverage.md section 3, 45 items): unit tests for the table columns (bias_htf.py), the loaders and
the bar-level rules (bias_day.py) on synthetic frames, plus the engine scenarios (long AND mirrored short) through run_day.
The real-data no-look-ahead runs live in test_bias_htf_lookahead.py."""
import json
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bias_day as BD, bias_htf as BH, htf, levels as L, study, strategy as S
from mentorship.strategy import Params

from test_day_week_context import NORMAL, ctx_for  # noqa: E402
from test_review_fixes import A_LOCK, A_ROWS, BASE, K, day, history  # noqa: E402

ES = Path("data/mentorship/ES_5min_db.csv").exists()
P0 = Params(**BASE)
NAN = float("nan")


def ix(ctx, minute: int) -> int:
    return ctx.start + minute // 5


# --- Params ----------------------------------------------------------------------------------------------------------------

def test_defaults_are_the_old_behaviour_and_the_table_config_is_empty():
    p = Params()
    assert p.bx == "" and p.htf_bias == "off" and p.draw_lock_pick == "nearest" and p.bias_neutral == "skip"
    assert not BD.active(p)
    assert p.want_all_engines and p.bias_open == "midnight" and p.bias_open_src == "data"


def test_validation_and_umbrellas():
    for kw in (dict(htf_bias="x"), dict(pd_zone="x"), dict(neutral_gate=("x",)), dict(ote_band=(0.8, 0.6)), dict(iof_days=1),
               dict(weekly_open="x"), dict(bias_open="x"), dict(chop_mode="x"), dict(draw_first_skip=("x",)), dict(qshift_size=0)):
        with pytest.raises(ValueError):
            Params(**kw)
    p = Params(draw_first="session")                                   # L14 / L14a umbrella
    assert (p.draw_lock, p.draw_lock_pick, p.draw_ext_target, p.cond_draw) == ("session", "ordered", True, True)
    assert "htf" in p.target_hygiene
    q = Params(draw_first="session", draw_first_skip=("pick", "cond", "hygiene"))
    assert q.draw_lock_pick == "nearest" and not q.cond_draw and "htf" not in q.target_hygiene and q.draw_ext_target
    r = Params(intermarket_model=True, intermarket_model_skip=("bond_dir",))         # B19 umbrella
    assert (r.dxy_gate, r.bond_range, r.bond_dir, r.decoupled_mode) == ("block", "scalp", "off", "scalp")
    s = Params(cot_oi_model=True, cot_oi_model_skip=("oi_tag",))                         # B20 umbrella
    assert (s.cot_tag, s.oi_tag, s.wpr_tag) == ("tag", "off", "tag")


def test_bx_string_names_the_columns_the_switches_need():
    assert json.loads(Params(htf_bias="ordered").bx) == {"ord": 1}
    x = json.loads(Params(htf_bias="combo2", weekly_open="either", nwog_bias="filter", wpr_tag="tag", matrix_tf_lower=True).bx)
    assert {"iof", "wk", "wo", "nwog", "wpr", "rtf"} <= set(x)
    assert "pd20" in json.loads(Params(day_pd="20d").bx) and "obj" in json.loads(Params(objective_met_stop="day").bx)
    assert json.loads(Params(neutral_gate=("draw_delivered",)).bx).keys() >= {"obj", "wk"}


def test_every_new_switch_has_a_study_variant():
    names = list(study.DECISIONS)
    new = set(names[names.index("X16_journal_tags_off") + 1:])
    covered = {"ord": "B2_", "iof": "B6_", "pd20": "A21", "wk": "B5_", "obmt": "B7_", "obj": "B9_", "mwd": "B10_", "wo": "B13_",
               "nwog": "B14", "qs": "B22", "wpr": "B20.3", "bc": "M0.1", "dpd": "Ep03.12", "r5050": "B17", "onr": "Ep08.2"}
    for pre in covered.values():
        assert any(n.startswith(pre) for n in new), pre
    fields = ("want_all_engines", "draw_ext_target", "judas_required", "draw_first", "cond_draw", "matrix_tf_lower", "iof_days",
              "day_pd", "pd_zone", "ote_band", "weekly_gate", "news_topdown", "bellwether_15m", "how_rule", "objective_neutral",
              "objective_met_stop", "bias_persist", "next_array_on_fail", "mwd_nest", "weekly_open", "nwog_regime", "nwog_bias",
              "neutral_gate", "neutral_5050", "chop_mode", "decoupled_mode", "smt_both", "bias_candle", "no_narrative_scalp",
              "mmbm_zone", "intermarket_model", "dxy_gate", "bond_range", "bond_dir", "cot_oi_model", "cot_tag", "oi_tag",
              "wpr_tag", "qshift_tag", "qshift_size", "midnight_target", "midnight_confirm", "midnight_below_ok", "one_market",
              "bias_open_src")
    used = set()
    for n in new:
        used |= set(study.DECISIONS[n])
    for f in fields:
        if f == "want_all_engines":
            continue
        assert f in used or f in ("iof_days", "ote_band", "bias_candle", "day_pd") or f in str(used), f


# --- B2 the ordered draw -----------------------------------------------------------------------------------------------------

def test_ordered_draw_inefficiency_first_then_liquidity_by_pd_and_the_extent():
    up = [(5.0, "D_swing_high", 105.0), (8.0, "W_fvg", 108.0)]
    dn = [(3.0, "PDL", 97.0)]
    r = BH.ordered_draw(up, dn, pdb=-1)                  # the FVG up is an inefficiency: it beats the nearer pool below
    assert (r["draw_ord"], r["draw_ord_kind"], r["draw_ord_lvl"], r["draw_ord_name"]) == (1, "ineff", 108.0, "W_fvg")
    r = BH.ordered_draw([(5.0, "D_swing_high", 105.0)], [(3.0, "PDL", 97.0)], pdb=1)       # no inefficiency: discount -> buy-side
    assert (r["draw_ord"], r["draw_ord_kind"], r["draw_ord_lvl"]) == (1, "liq", 105.0)
    r = BH.ordered_draw([(5.0, "D_swing_high", 105.0)], [(3.0, "PDL", 97.0)], pdb=-1)      # premium -> sell-side
    assert (r["draw_ord"], r["draw_ord_lvl"]) == (-1, 97.0)
    r = BH.ordered_draw([(5.0, "D_swing_high", 105.0)], [(3.0, "PDL", 97.0)], pdb=0)       # no P/D: the nearer pool
    assert r["draw_ord"] == -1
    r = BH.ordered_draw([(3.0, "D_swing_high", 103.0)], [(3.0, "PDL", 97.0)], pdb=0)
    assert r["draw_ord"] == 0                                                             # a tie is neutral
    r = BH.ordered_draw([(2.0, "D_fvg", 102.0)], [(2.0, "D_fvg", 98.0)], pdb=1)
    assert r["draw_ord"] == 0                                                             # two equal inefficiencies
    # the extent: beyond the pool the nearest inefficiency sets how far the run goes
    r = BH.ordered_draw([(5.0, "PDH", 105.0)], [(30.0, "D_swing_low", 70.0)], pdb=1)
    assert r["draw_ord_kind"] == "liq" and r["draw_ext_lvl"] != r["draw_ext_lvl"]
    mirror = BH.ordered_draw([(30.0, "D_swing_high", 130.0)], [(5.0, "PDL", 95.0)], pdb=-1)
    assert mirror["draw_ord"] == -1 and mirror["draw_ord_lvl"] == 95.0


def test_ordered_side_and_ext_target_in_the_lock_candidates():
    # items: (distance, level, kind, name, dir), nearest first
    up = [(5.0, 105.0, "array", "htf_D_fvg", 0), (9.0, 109.0, "pool", "pdh1", 1)]
    dn = [(3.0, 97.0, "pool", "pdl1", -1)]
    p = Params(draw_lock_pick="ordered")
    side, u, d = BD.ordered_side(up, dn, {"pd": -1}, p)
    assert side == 1 and u[0][3] == "htf_D_fvg"                    # the array beats the nearer pool
    mu = [(a, 300 - b, k, n, -dr) for a, b, k, n, dr in dn]          # the mirror: the array is below, the pool above
    side, u, d = BD.ordered_side([(3.0, 103.0, "pool", "pdh1", 1)], [(5.0, 95.0, "array", "htf_D_fvg", 0)], {"pd": 1}, p)
    assert side == -1 and d[0][3] == "htf_D_fvg"
    side, *_ = BD.ordered_side([(5.0, 105.0, "pool", "pdh1", 1)], [(3.0, 97.0, "pool", "pdl1", -1)], {"pd": 1}, p)
    assert side == 1                                                # no array: discount -> buy-side
    side, *_ = BD.ordered_side([(5.0, 105.0, "pool", "pdh1", 1)], [(3.0, 97.0, "pool", "pdl1", -1)], {"pd": -1}, p)
    assert side == -1
    side, *_ = BD.ordered_side([(5.0, 105.0, "pool", "pdh1", 1)], [(3.0, 97.0, "pool", "pdl1", -1)], None, p)
    assert side == -1                                               # no row: the nearer
    big = replace(p, draw_lock_pick="largest")
    side, *_ = BD.ordered_side(up, dn, {"pd": -1}, big)
    assert side == 1                                                # the bigger move (9 vs 3)
    ext = BD.ext_target([(5.0, 105.0, "pool", "pdh1", 1)], [(5.0, 105.0, "pool", "pdh1", 1), (8.0, 108.0, "array", "x", 0)])
    assert ext[1] == 108.0
    assert BD.ext_target([(5.0, 105.0, "array", "x", 0)], [(5.0, 105.0, "array", "x", 0), (8.0, 108.0, "array", "y", 0)]) is None


# --- B6 IOF -------------------------------------------------------------------------------------------------------------------

def _ohlc(rows):
    a = np.array(rows, float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def test_iof_score_candle_respect_and_pivot_raids():
    # bullish flow: a down-close candle retested and held, then an up-close candle run through, with a raided low that reverses
    o, h, l, c = _ohlc([(100, 101, 99, 99.5), (99.5, 102, 99.2, 101.5), (101.5, 103, 100.0, 102.8), (102.8, 104.5, 102.5, 104),
                        (104, 105, 101, 104.5), (104.5, 106, 103.5, 105.8), (105.8, 107, 105, 106.5)])
    s = BH.iof_score(o, h, l, c, 7, 10)
    assert s > 0
    # the mirror (price -> K - price) scores the opposite
    om, hm, lm, cm = K - o, K - l, K - h, K - c
    assert BH.iof_score(om, hm, lm, cm, 7, 10) == -s
    # a down-close candle closed through = bearish; an up-close candle held as resistance = bearish
    o2, h2, l2, c2 = _ohlc([(100, 101, 98, 98.5), (98.5, 99, 96, 96.5), (96.5, 97, 94, 94.5), (94.5, 95, 92, 92.5)])
    assert BH.iof_score(o2, h2, l2, c2, 4, 10) < 0
    assert BH.iof_score(o, h, l, c, 1, 10) == 0           # nothing completed after the first candle


# --- A21 premium / discount ----------------------------------------------------------------------------------------------------

def test_pd_state_zones_and_the_mirror():
    assert BH.pd_state(104.0, 120.0, 100.0, "half") == (1, 0.2)
    assert BH.pd_state(116.0, 120.0, 100.0, "half")[0] == -1
    assert BH.pd_state(110.0, 120.0, 100.0, "third")[0] == 0 and BH.pd_state(105.0, 120.0, 100.0, "third")[0] == 1
    assert BH.pd_state(115.0, 120.0, 100.0, "third")[0] == -1
    assert BH.pd_state(105.0, 120.0, 100.0, "deep")[0] == 1 and BH.pd_state(107.0, 120.0, 100.0, "deep")[0] == 0
    assert BH.pd_state(108.0, 120.0, 100.0, "ote")[0] == 0       # 40% of the range: above the 21-38% discount OTE band
    assert BH.pd_state(106.0, 120.0, 100.0, "ote")[0] == 1       # 30%: inside the discount OTE band
    assert BH.pd_state(114.0, 120.0, 100.0, "ote")[0] == -1      # 70%: the premium OTE band
    assert BH.pd_state(104.0, 120.0, 100.0, "ote")[0] == 0       # 20%: deeper than 79%
    assert BH.pd_state(110.0, 100.0, 100.0)[0] == 0              # no range
    with pytest.raises(ValueError):
        BH.pd_state(1, 2, 0, "nope")


# --- B10 MWD ---------------------------------------------------------------------------------------------------------------------

def test_mwd_case_logic():
    assert BH.mwd_case(1, 1, 1, 0, 0) == (1, "A")            # all three bullish, day not correcting: buy every daily discount array
    assert BH.mwd_case(1, 1, 1, 1, 0) == (1, "B")            # the day corrects inside a bullish week
    assert BH.mwd_case(1, 1, -1, 0, 0) == (1, "B")
    assert BH.mwd_case(1, -1, -1, 0, 0) == (1, "C")          # only the month is bullish
    assert BH.mwd_case(-1, -1, -1, 0, 0) == (-1, "A")        # the mirror
    assert BH.mwd_case(-1, 1, 1, 0, 0) == (-1, "C")
    assert BH.mwd_case(0, 1, 1, 0, 0) == (1, "A") and BH.mwd_case(0, 1, 0, 0, 0) == (1, "B")
    assert BH.mwd_case(0, 0, -1, 0, 0) == (-1, "D") and BH.mwd_case(0, 0, 0, 0, 0) == (0, "")


def test_tf_states_displacement_structure_break_and_correction():
    rows, px = [], 100.0
    for k in range(14):                                      # a quiet drift down in small candles
        rows.append((px, px + 0.6, px - 0.9, px - 0.6)); px -= 0.6
    rows.append((px, px + 6, px - 0.2, px + 5.5))            # a bullish displacement closing above the last swing high
    o, h, l, c = _ohlc(rows)
    st, cr = BH.tf_states(o, h, l, c, 1.0)
    assert st[-1] == 1 and st[-2] <= 0
    st_m, _ = BH.tf_states(K - o, K - l, K - h, K - c, 1.0)  # the mirror: a bearish displacement through the last swing low
    assert st_m[-1] == -1
    # a counter displacement only marks the state as correcting; it does not cancel it
    rows2 = rows + [(px + 5.5, px + 5.6, px + 1.0, px + 1.5)]
    o2, h2, l2, c2 = _ohlc(rows2)
    st2, cr2 = BH.tf_states(o2, h2, l2, c2, 1.0)
    assert st2[-1] == 1 and cr2[-1] == 1


# --- the table columns ----------------------------------------------------------------------------------------------------------

BX_ALL = json.dumps({"ord": 1, "iof": [10, 2], "pd20": [20, 1, "half", [0.62, 0.79], 0], "wk": 1, "obmt": 1, "obj": 1, "mwd": 1.0,
                     "wo": 2, "nwog": [0.5, 2, 10, "low"], "bc": 1, "dpd": 1, "qs": [0.03, 0.07, 63, 84], "wpr": 14, "r5050": 0.5,
                     "onr": 1, "rtf": 1}, sort_keys=True)


@pytest.fixture(scope="module")
def es5():
    if not ES:
        pytest.skip("ES 5m data missing")
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= "2023-03-01") & (df.index < "2024-03-01")]


@pytest.fixture(scope="module")
def tables(es5):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return htf.table(es5, 1.0, vi=True), htf.table(es5, 1.0, vi=True, bx=BX_ALL)


def test_table_without_bx_is_unchanged_and_extra_columns_do_not_touch_the_old_ones(tables):
    base, full = tables
    assert list(base.columns) == ["px", "react", "react_score", "draw", "pd", "combo", "draw_up", "draw_up_name", "draw_dn",
                                  "draw_dn_name", "vi_up", "vi_dn", "flip"]
    assert full[base.columns].fillna(-9).equals(base.fillna(-9))
    for col in ("draw_ord", "draw_ord_lvl", "iof", "iof_score", "pd20", "wk_bias", "ob_mt", "ob_mt_lvl", "how_in", "obj_day", "obj_week",
                "mwd", "mwd_case", "mwd_zones", "wo_sun", "wo_mon", "wk_dir", "wo_expired", "nwog_regime", "nwog_bias", "bc_D", "bc_W",
                "draw_pd", "qs_state", "qs_due", "wpr", "fifty", "on_range", "in_bull_arr", "react_tf"):
        assert col in full.columns, col


def test_table_column_values_are_sane(tables):
    _, t = tables
    assert set(t.draw_ord.unique()) <= {-1, 0, 1} and set(t.iof.unique()) <= {-1, 0, 1} and set(t.mwd.unique()) <= {-1, 0, 1}
    assert set(t.mwd_case.unique()) <= {"", "A", "B", "C", "D"}
    assert set(t.nwog_regime.unique()) <= {"", "cons", "trend"} and set(t.nwog_bias.unique()) <= {-1, 0, 1}
    assert t.wpr.dropna().between(-100, 0).all()
    q = t.dropna(subset=["pd20_pos"])
    assert ((q.pd20_pos > 0.5) == (q.pd20 < 0)).all()                       # above the middle of the body range = premium (a breakout reads > 1)
    d = t.dropna(subset=["draw_ord_lvl"])
    assert ((d.draw_ord > 0) == (d.draw_ord_lvl > d.px)).all()            # the ordered draw's level is on its side of price
    # the weekly open is constant within a week; Monday's Sunday-18:00 open is the first session open
    wk = pd.Series(pd.to_datetime(t.index)).dt.to_period("W-FRI").values
    assert (t.groupby(wk).wo_sun.nunique() == 1).all()
    assert (t.groupby(wk).wk_dir.nunique() == 1).all()
    # reactions are weights: the signed score is up minus down
    assert np.allclose(t.react_score, t.react_up - t.react_dn)
    # a candle's open is the reference: bc_D's level lies on the side of its own sign relative to the session open
    assert ((t.bc_D != 0) | t.bc_D_lvl.isna()).all()


def test_table_does_not_look_ahead(es5):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for cut_min in (570, 810):
            full = htf.table(es5, 1.0, vi=True, bx=BX_ALL, cut_min=cut_min)
            for cut in (pd.Timestamp("2023-09-12 11:00", tz="America/New_York"), pd.Timestamp("2024-01-18 15:00", tz="America/New_York")):
                part = htf.table(es5[es5.index < cut], 1.0, vi=True, bx=BX_ALL, cut_min=cut_min)
                day_ = cut.date()
                a = full[full.index < day_].drop(columns=["mwd_zones"])
                b = part[part.index < day_].drop(columns=["mwd_zones"])
                pd.testing.assert_frame_equal(a.reset_index(), b.reset_index(), check_exact=False, rtol=1e-9)
                assert [x for x in full.mwd_zones[full.index < day_]] == [x for x in part.mwd_zones[part.index < day_]]


def test_persistence_keeps_the_standing_sign_until_confirmed(monkeypatch):
    monkeypatch.setattr(htf, "_flip", lambda *a, **k: {})
    idx = pd.date_range("2024-01-02", periods=10, freq="D")
    ks = np.arange(10)
    d = pd.DataFrame(index=idx)
    raw = [1, 1, -1, 1, -1, -1, -1, 0, 1, -1]
    out = pd.DataFrame({"react": raw, "draw": raw, "pd": raw, "combo": raw}, index=idx.date)
    got = BH._persist(out.copy(), 2, ks, d, None, [])
    assert list(got.react) == [1, 1, 1, 1, 1, -1, -1, 0, -1, -1] or list(got.react)[:3] == [1, 1, 1]
    assert list(got.react0) == raw                            # the plain reading is kept
    # a single contrary day inside the trend is a retracement; two in a row flip it
    assert got.react.iloc[2] == 1 and got.react.iloc[5] == -1
    # n = 1: the old behaviour
    same = BH._persist(out.copy(), 1, ks, d, None, [])
    assert list(same.react) == raw


def test_cot_oi_loaders(tmp_path, monkeypatch):
    rep = pd.date_range("2023-01-03", periods=60, freq="7D")
    net_long = np.r_[np.linspace(100, 300, 30), np.linspace(300, 120, 30)]
    pd.DataFrame({"Market and Exchange Names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
                  "As of Date in Form YYYY-MM-DD": rep.strftime("%Y-%m-%d"),
                  "Commercial Positions-Long (All)": net_long + 1000, "Commercial Positions-Short (All)": 1000}).to_csv(tmp_path / "a.csv", index=False)
    pd.DataFrame({"Market and Exchange Names": "GOLD", "As of Date in Form YYYY-MM-DD": rep.strftime("%Y-%m-%d"),
                  "Commercial Positions-Long (All)": 1, "Commercial Positions-Short (All)": 5}).to_csv(tmp_path / "b.csv", index=False)
    BH._COT.clear()
    t = BH.load_cot("E-MINI S&P 500", tmp_path)
    assert len(t) == 60 and (t.net.values == pytest.approx(net_long))
    # usable from the Monday after the Friday release: the report of Tuesday 2023-01-03 is usable on 2023-01-09
    assert t.index[0] == pd.Timestamp("2023-01-09")
    assert BH.cot_state(date(2023, 1, 6), t) == 0              # not usable yet / too little history
    # report 40 (net 2xx falling): after the peak the net is above the 52-week midpoint until it falls under (100+300)/2 = 200
    late = t.index[45]
    assert BH.cot_state(late, t) in (-1, 1)
    assert BH.cot_state(t.index[29], t) == 1                  # near the peak: above the midpoint
    assert BH.cot_state(t.index[59], t) == -1 and BH.load_cot("E-MINI S&P 500", tmp_path / "none") is None
    # open interest: roll-summed (two contracts per day), a 20% drop over 10 sessions
    days = pd.bdate_range("2024-01-02", periods=30)
    rows = [(f"{d.date()}T14:00:00Z", 9, q, "ESH4") for d, q in zip(days, np.linspace(1000, 800, 30))]
    rows += [(f"{d.date()}T14:00:00Z", 9, 500, "ESM4") for d in days]
    rows += [(f"{days[0].date()}T14:00:00Z", 1, 99999, "ESH4")]      # another stat type: ignored
    f = tmp_path / "oi.csv"
    pd.DataFrame(rows, columns=["ts_event", "stat_type", "quantity", "symbol"]).to_csv(f, index=False)
    oi = BH.load_oi(f)
    assert oi.iloc[0] == 1500 and len(oi) == 30
    ch = BH.oi_change(oi, days[29].date(), 10)
    assert ch == pytest.approx(oi.iloc[28] / oi.iloc[18] - 1) and ch < 0
    assert BH.oi_change(oi, days[3].date(), 10) is None and BH.oi_change(None, days[3].date()) is None


def test_intermarket_flags_use_prior_sessions_only(monkeypatch):
    days = pd.bdate_range("2023-01-02", periods=120)
    rng = np.random.default_rng(1)
    def mk(c, spread=0.5):
        return pd.DataFrame({"open": c, "high": c + spread, "low": c - spread, "close": c}, index=days)
    dxy = 100 + np.cumsum(rng.normal(0, 0.2, 120))
    dxy[-1] += 10                                              # the LAST row is a new high - must not be seen from its own day
    tnx = 3 + np.cumsum(rng.normal(0, 0.02, 120))
    spx = 4000 * np.cumprod(1 + rng.normal(0, 0.01, 120))
    ndx = spx * 3 * np.cumprod(1 + rng.normal(0, 0.002, 120))
    monkeypatch.setattr(BH, "_IMD", {"DXY": mk(dxy), "TNX": mk(tnx, 0.02), "GSPC": mk(spx, 5), "NDX": mk(ndx, 5)})
    p = Params()
    last = days[-1].date()
    assert BH.im_flags(last, p)["dxy_hi"] is False             # day D's own close (the spike) is not read
    nxt = (days[-1] + pd.Timedelta(days=1)).date()
    BH._IMD["_flags"] = {}
    assert BH.im_flags(nxt, p)["dxy_hi"] is True               # the next day sees it: a close above the 20-day high and rising
    f = BH.im_flags(last, p)
    assert set(f) >= {"bond_range", "bond_dir", "decoupled", "dec_corr"} and f["bond_dir"] in (-1, 0, 1)
    # an opposite-sign prior day makes the indices decoupled
    sp2, nd2 = spx.copy(), ndx.copy()
    sp2[-2], nd2[-2] = sp2[-3] * 1.02, nd2[-3] * 0.98
    BH._IMD.update({"GSPC": mk(sp2, 5), "NDX": mk(nd2, 5), "_flags": {}})
    assert BH.im_flags(days[-1].date(), p)["decoupled"] is True


def test_map_midnight_scales_by_the_prior_close_ratio():
    d0, d1 = date(2024, 3, 4), date(2024, 3, 5)
    ref_idx = pd.date_range("2024-03-04 00:00", "2024-03-05 16:00", freq="30min", tz="America/New_York")
    ref = pd.DataFrame({"open": np.where(ref_idx.date == d0, 5000.0, 5100.0), "close": np.where(ref_idx.date == d0, 5000.0, 5100.0)}, index=ref_idx)
    ix_ = pd.date_range("2024-03-04 09:30", "2024-03-04 16:00", freq="30min", tz="America/New_York").append(
        pd.date_range("2024-03-05 04:00", "2024-03-05 16:00", freq="30min", tz="America/New_York"))
    df = pd.DataFrame({"close": 500.0, "open": 500.0}, index=ix_)
    m = L.map_midnight(ref, df)
    assert d0 not in m and m[d1] == pytest.approx(5100.0 * 500.0 / 5000.0)


def test_combine_trend_pick_and_one_market():
    mk = lambda sym, t, smt, tags, rel=1.0: dict(symbol=sym, date=date(2024, 3, 4), session="AM", entry_time=pd.Timestamp(t), smt=smt,
                                                 day_tags=tags, dw_tags="", ext_px=100.0, leg_hi_px=100.0 + rel)
    a = pd.DataFrame([mk("ES", "2024-03-04 09:40", False, "")])               # the leader (its SMT did not show the sister stronger)
    b = pd.DataFrame([mk("NQ", "2024-03-04 09:45", True, "")])                # the laggard
    assert list(B.combine(a, b, pick="trend").symbol) == ["ES"]               # trend day: the leader
    a2, b2 = a.assign(day_tags="inside_day"), b.assign(day_tags="inside_day")
    assert list(B.combine(a2, b2, pick="trend").symbol) == ["NQ"]             # consolidation day: the laggard
    assert B.consolidation_day(dict(day_tags="", dw_tags="bh_nwog_cons")) and not B.consolidation_day(dict(day_tags="x", dw_tags=""))
    with pytest.raises(ValueError):
        B.combine(a, b, pick="x")
    # one_market: the day's later trades of the other instrument are dropped
    c = pd.DataFrame([dict(mk("ES", "2024-03-04 09:40", False, ""), session="AM"), dict(mk("NQ", "2024-03-04 14:00", False, ""), session="PM")])
    assert list(B.combine(c).symbol) == ["ES", "NQ"]
    assert list(B.combine(c, one_market=True).symbol) == ["ES"]


# --- the bar-level rules (bias_day.py): long AND mirrored short ----------------------------------------------------------------

FLAT = (100.0, 100.1, 99.9, 100.0)
I = lambda m: 78 + m // 5                                      # bar index of minute m in these hand-made frames (ctx.start = 78)
MON_WED = date(2026, 6, 24)                                  # a Wednesday (the weekly-open "later in the week" side)


def bctx(rows=None, p=None, row=None, d=NORMAL, cuts=None, lock=None, **kw):
    """A one-day ctx with the bias_htf state: `row` = the 09:30 table row, `cuts` = {minute: row} for the pre-09:30 rows."""
    p = p or P0
    ctx = ctx_for(rows or [FLAT] * 12, d=d, p=p, **kw)
    ctx.bias_row = row
    ctx.bias_by_cut = cuts or {}
    ctx.lock = lock or {}
    ctx.lock_t = {"AM": 570, "PM": 810, "PRE7": 420, "PRE9": 540}
    BD.plan(ctx.dplan, ctx, ctx.hist, p, set())
    return ctx


def DW_side_ok(ctx, p, sign, session, i):
    from mentorship import daycontext as DW
    return DW.side_ok(ctx, p, sign, session, i)


def test_row_for_and_want_at_never_read_the_0930_row_before_0930():
    p = Params(**BASE, htf_bias="draw")
    row = dict(draw=1, px=100)
    pre = dict(draw=-1, px=100)
    ctx = bctx(row=row, p=p, cuts={420: pre})
    # the engine frame starts at 00:00 (day() builds 00:00-16:15): bar index = minute // 5
    assert BD.row_for(ctx, "PRE7", I(420)) is pre                      # 07:00 reads the 07:00 cut
    assert BD.row_for(ctx, "AM", I(570)) is row                       # 09:30 reads the 09:30 table
    assert BD.row_for(ctx, "PRE7", I(300)) is None                     # 05:00: no cut yet
    assert BD.want_at(ctx, p, "PRE7", I(420)) == -1 and BD.want_at(ctx, p, "AM", I(570)) == 1 and BD.want_at(ctx, p, "PRE7", I(300)) == 0
    assert BD.want_at(ctx, P0, "AM", I(570)) == 0                     # htf_bias off


@pytest.mark.parametrize("sgn", [1, -1])
def test_side_ok_bias_side_in_every_engine_and_neutral_modes(sgn):
    p = Params(**BASE, htf_bias="draw")
    ctx = bctx(row=dict(draw=sgn, px=100), p=p)
    i = I(600)
    assert BD.side_ok(ctx, p, sgn, "AM", i) is None and BD.side_ok(ctx, p, -sgn, "AM", i) == "x_bh_want"
    assert DW_side_ok(ctx, p, -sgn, "AM", i) == "x_bh_want"        # daycontext.side_ok calls it (all engines)
    off = replace(p, want_all_engines=False)
    assert BD.side_ok(ctx, off, -sgn, "AM", i) is None             # the main engine keeps its own gate
    neutral = bctx(row=dict(draw=0, px=100), p=p)
    assert BD.side_ok(neutral, p, 1, "AM", i) == "x_bh_want" and BD.side_ok(neutral, p, -1, "AM", i) == "x_bh_want"
    both = replace(p, bias_neutral="both")
    assert BD.side_ok(neutral, both, 1, "AM", i) is None and BD.side_ok(neutral, both, -1, "AM", i) is None


def test_bias_value_columns_and_objective_neutral():
    row = dict(draw_ord=-1, iof=1, bc_D=1, bc_W=-1, nwog_bias=1, wk_bias=-1, ob_mt=1, mwd=-1, draw_pd=1, pd20=-1, combo2=1, obj_day=1, obj_week=0)
    for mode, want in (("ordered", -1), ("iof", 1), ("nwog", 1), ("wk", -1), ("ob_mt", 1), ("mwd", -1), ("draw_pd", 1), ("pd20", -1),
                       ("combo2", 1)):
        assert BD.bias_value(row, Params(**BASE, htf_bias=mode)) == want
    assert BD.bias_value(row, Params(**BASE, htf_bias="candle", bias_candle="D")) == 1
    assert BD.bias_value(row, Params(**BASE, htf_bias="candle", bias_candle="W")) == -1
    assert BD.bias_value(row, Params(**BASE, htf_bias="iof", objective_neutral="day")) == 0        # yesterday's draw delivered: neutral
    assert BD.bias_value(row, Params(**BASE, htf_bias="iof", objective_neutral="week")) == 1
    assert BD.bias_value(dict(row, obj_week=1), Params(**BASE, htf_bias="iof", objective_neutral="week")) == 0
    assert BD.bias_value(None, Params(**BASE, htf_bias="iof")) == 0


def test_objective_met_stop_and_neutral_gate_modes():
    ctx = lambda p, row: bctx(row=row, p=p)
    i = I(600)
    p = Params(**BASE, objective_met_stop="day")
    c = ctx(p, dict(obj_day=1, obj_week=0))
    assert BD.gate(c, p, "AM", i, 600) == "x_bh_objective_met" and BD.gate(c, p, "PM", I(840), 840) == "x_bh_objective_met"
    assert BD.gate(ctx(p, dict(obj_day=0, obj_week=1)), p, "AM", i, 600) is None
    q = replace(p, objective_met_stop="week")
    assert BD.gate(ctx(q, dict(obj_day=0, obj_week=1)), q, "AM", i, 600) == "x_bh_objective_met"
    # neutral_gate: tag leaves everything alone, skip blocks, scalp reshapes the exits
    tag = Params(**BASE, neutral_gate=("fifty_fifty",), neutral_gate_mode="tag")
    c = ctx(tag, dict(fifty=1))
    assert BD.gate(c, tag, "AM", i, 600) is None and BD.scalp_now(c, tag, "AM", i) == ""
    assert "bh_ng_fifty_fifty" in c.dplan.tags
    skip = replace(tag, neutral_gate_mode="skip")
    assert BD.gate(ctx(skip, dict(fifty=1)), skip, "AM", i, 600) == "x_bh_ng_fifty_fifty"
    assert BD.gate(ctx(skip, dict(fifty=0)), skip, "AM", i, 600) is None
    sc = replace(tag, neutral_gate_mode="scalp")
    c = ctx(sc, dict(fifty=1))
    assert BD.gate(c, sc, "AM", i, 600) is None and BD.scalp_now(c, sc, "AM", i) == "ng_fifty_fifty"
    dd = Params(**BASE, neutral_gate=("draw_delivered",), neutral_gate_mode="skip")
    assert BD.gate(ctx(dd, dict(obj_day=0, obj_week=1)), dd, "AM", i, 600) == "x_bh_ng_draw_delivered"
    rf = Params(**BASE, neutral_5050="react")
    assert BD.gate(ctx(rf, dict(fifty=1)), rf, "AM", i, 600) == "x_bh_fifty_fifty"


def test_premium_chop_and_chop_mode_wait_for_0930():
    # the ADR5 of history() is 18; the overnight range 4 is narrower than 0.35 x 18
    p = Params(**BASE, chop_mode="skip")
    row = dict(on_range=4.0, in_bull_arr=0, in_bear_arr=0)
    c = bctx(row=row, p=p, cuts={420: row})
    assert BD.gate(c, p, "PRE7", I(420), 420) == "x_bh_chop"                         # before 09:30: wait
    assert BD.gate(c, p, "AM", I(600), 600) is None                                 # from 09:30 the AM trades
    assert BD.gate(bctx(row=dict(on_range=40.0, in_bull_arr=0, in_bear_arr=0), p=p), p, "AM", I(600), 600) is None
    arr = dict(on_range=40.0, in_bull_arr=0, in_bear_arr=1)                       # stuck inside a bearish (premium) HTF array
    c2 = bctx(row=arr, p=p, cuts={420: arr})
    assert BD.gate(c2, p, "PRE7", I(420), 420) == "x_bh_chop"
    noarr = replace(p, chop_in_array=False)
    assert BD.gate(bctx(row=arr, p=noarr, cuts={420: arr}), noarr, "PRE7", I(420), 420) is None
    day_ = replace(p, chop_mode="skip_day")
    assert BD.gate(bctx(row=row, p=day_), day_, "AM", I(600), 600) == "x_bh_chop"
    sc = replace(p, chop_mode="scalp")
    c3 = bctx(row=row, p=sc)
    assert BD.scalp_now(c3, sc, "AM", I(600)) == "chop" and BD.gate(c3, sc, "AM", I(600), 600) is None
    pc = Params(**BASE, neutral_gate=("premium_chop",), neutral_gate_mode="skip")
    c4 = bctx(row=row, p=pc, cuts={420: row})
    assert BD.gate(c4, pc, "PRE7", I(420), 420) == "x_bh_ng_premium_chop" and BD.gate(c4, pc, "AM", I(600), 600) is None


@pytest.mark.parametrize("sgn", [1, -1])
def test_side_filters_from_the_row(sgn):
    i = I(600)
    # weekly gate: no side against the weekly bias; how_in: no longs; nwog_bias / wpr: the opposite sides
    p = Params(**BASE, weekly_gate="filter")
    c = bctx(row=dict(wk_bias=sgn), p=p)
    assert BD.side_ok(c, p, sgn, "AM", i) is None and BD.side_ok(c, p, -sgn, "AM", i) == "x_bh_weekly_gate"
    t = replace(p, weekly_gate="tag")
    assert BD.side_ok(bctx(row=dict(wk_bias=sgn), p=t), t, -sgn, "AM", i) is None
    h = Params(**BASE, how_rule="no_long")
    c = bctx(row=dict(how_in=1), p=h)
    assert BD.side_ok(c, h, 1, "AM", i) == "x_bh_how" and BD.side_ok(c, h, -1, "AM", i) is None
    n = Params(**BASE, nwog_bias="filter")
    c = bctx(row=dict(nwog_bias=sgn), p=n)
    assert BD.side_ok(c, n, -sgn, "AM", i) == "x_bh_nwog_bias" and BD.side_ok(c, n, sgn, "AM", i) is None
    w = Params(**BASE, wpr_tag="filter")
    c = bctx(row=dict(wpr=-90.0), p=w)                               # oversold: ideal longs -> no shorts
    assert BD.side_ok(c, w, -1, "AM", i) == "x_bh_wpr" and BD.side_ok(c, w, 1, "AM", i) is None
    c = bctx(row=dict(wpr=-10.0), p=w)
    assert BD.side_ok(c, w, 1, "AM", i) == "x_bh_wpr" and BD.side_ok(c, w, -1, "AM", i) is None
    c = bctx(row=dict(wpr=-50.0), p=w)
    assert BD.side_ok(c, w, 1, "AM", i) is None and BD.side_ok(c, w, -1, "AM", i) is None


def test_nwog_regime_modes():
    cons = dict(nwog_regime="cons")
    for mode, key in (("scalp", "scalp"), ("skip", "gate"), ("tag", None)):
        p = Params(**BASE, nwog_regime=mode)
        c = bctx(row=cons, p=p)
        assert (BD.scalp_now(c, p, "AM", I(600)) == "nwog_cons") == (key == "scalp")
        assert (BD.gate(c, p, "AM", I(600), 600) == "x_bh_nwog_cons") == (key == "gate")
        assert "bh_nwog_cons" in c.dplan.tags
    p = Params(**BASE, nwog_regime="skip")
    t = bctx(row=dict(nwog_regime="trend"), p=p)
    assert BD.gate(t, p, "AM", I(600), 600) is None and "bh_nwog_trend" in t.dplan.tags


@pytest.mark.parametrize("sgn", [1, -1])
def test_weekly_open_filter_early_below_then_above(sgn):
    p = Params(**BASE, weekly_open="either")
    wo = 100.0
    row = dict(wk_dir=sgn, wo_sun=wo, wo_mon=wo + 3.0 * sgn, wo_expired=0)
    # the rows are 5m bars from 09:30: price on the "cheap" side of the open (below it for a long) and on the "dear" side
    cheap = [(wo - 1.0 * sgn, wo - 0.5 * sgn if sgn > 0 else wo - 1.5 * sgn, wo - 1.5 * sgn if sgn > 0 else wo - 0.5 * sgn, wo - 1.0 * sgn)] * 8
    dear = [(wo + 1.0 * sgn, wo + 1.5 * sgn if sgn > 0 else wo + 0.5 * sgn, wo + 0.5 * sgn if sgn > 0 else wo + 1.5 * sgn, wo + 1.0 * sgn)] * 8
    i = I(590)
    late = dict(d=MON_WED)
    c = bctx(rows=cheap, p=p, row=row)
    assert BD.side_ok(c, p, sgn, "AM", i) is None                               # Tuesday: longs below the open are the best
    c = bctx(rows=dear, p=p, row=dict(row, wo_mon=wo + 6.0 * sgn))
    assert BD.side_ok(c, p, sgn, "AM", i) is None                               # "either": below the Monday open is enough
    c = bctx(rows=dear, p=p, row=dict(row, wo_mon=wo))
    assert BD.side_ok(c, p, sgn, "AM", i) == "x_bh_weekly_open"                 # above both opens early in the week
    assert BD.side_ok(c, p, -sgn, "AM", i) is None                              # the counter side is not this rule's business
    c = bctx(rows=dear, p=p, row=row, **late)
    assert BD.side_ok(c, p, sgn, "AM", i) is None                               # Wednesday: buy each day while above it
    c = bctx(rows=cheap, p=p, row=dict(row, wo_mon=wo), **late)
    assert BD.side_ok(c, p, sgn, "AM", i) == "x_bh_weekly_open"
    c = bctx(rows=cheap, p=p, row=dict(row, wo_mon=wo, wo_expired=1), **late)
    assert BD.side_ok(c, p, sgn, "AM", i) is None                               # expired at an opposing daily array
    s18 = replace(p, weekly_open="sun18")
    c = bctx(rows=dear, p=s18, row=dict(row, wo_mon=wo + 99 * sgn))
    assert BD.side_ok(c, s18, sgn, "AM", i) == "x_bh_weekly_open"               # only the Sunday open counts


@pytest.mark.parametrize("sgn", [1, -1])
def test_judas_required_waits_for_the_run_against_the_bias(sgn):
    p = Params(**BASE, judas_required="filter", judas_min_pts=2.0)
    if sgn > 0:
        rows = [(100, 100.2, 99.5, 99.7), (99.7, 99.8, 97.4, 97.6)] + [(97.6, 99.6, 97.5, 99.5)] * 6
    else:
        rows = [(100, 100.5, 99.8, 100.3), (100.3, 102.7, 100.2, 102.6)] + [(102.6, 102.7, 100.6, 100.7)] * 6
    lock = {"AM": dict(side=sgn, delivered=False, target=110 if sgn > 0 else 90)}
    c = bctx(rows=rows, p=p, row=dict(draw=sgn), lock=lock)
    k0 = I(570)
    assert BD.side_ok(c, p, sgn, "AM", k0) == "x_bh_judas"                       # the first bar: only 0.5 against the bias
    assert BD.judas_seen(c, p, "AM", k0 + 1, sgn) is True                         # the second bar ran 2.6 against it
    assert BD.side_ok(c, p, sgn, "AM", k0 + 1) is None
    assert BD.side_ok(c, p, -sgn, "AM", k0) is None                               # (the lock gate stops the other side elsewhere)
    t = replace(p, judas_required="tag")
    assert BD.side_ok(c, t, sgn, "AM", k0) is None
    o = dict(entry=1, ext=0, lv_tags="")
    BD.order_ok(c, SimpleNamespace(sign=sgn, x=lambda v: v), o, "AM", k0, t)
    assert "judas_pending" in o["lv_tags"]


@pytest.mark.parametrize("sgn", [1, -1])
def test_order_ok_mwd_nest_mmbm_zone_and_tags(sgn):
    X = lambda v: v if sgn > 0 else K - v
    sd = SimpleNamespace(sign=sgn, x=X)
    # side space: entry 101, sweep extreme 98, draw 110 -> the discount half is entry <= 104
    p = Params(**BASE, mwd_nest="filter", mmbm_zone="filter")
    zones = [(X(99.0), X(102.0))] if sgn > 0 else [(X(102.0), X(99.0))]
    row = dict(mwd=sgn, mwd_case="B", mwd_zones=zones)
    c = bctx(row=row, p=p)
    o = dict(entry=101.0, ext=98.0, draw=110.0, lv_tags="")
    assert BD.order_ok(c, sd, o, "AM", I(600), p) is None and "mwd_B_nested" in o["lv_tags"] and "mmbm_discount" in o["lv_tags"]
    far = dict(entry=105.0, ext=98.0, draw=110.0, lv_tags="")
    assert BD.order_ok(c, sd, far, "AM", I(600), p) == "x_bh_mwd_nest"
    only_zone = replace(p, mwd_nest="off")
    far2 = dict(entry=105.0, ext=98.0, draw=110.0, lv_tags="")
    assert BD.order_ok(bctx(row=row, p=only_zone), sd, far2, "AM", I(600), only_zone) == "x_bh_mmbm_zone"
    tag = replace(p, mwd_nest="tag", mmbm_zone="tag")
    far3 = dict(entry=105.0, ext=98.0, draw=110.0, lv_tags="")
    assert BD.order_ok(bctx(row=row, p=tag), sd, far3, "AM", I(600), tag) is None
    assert "mwd_B_free" in far3["lv_tags"] and "mmbm_premium" in far3["lv_tags"]
    a = dict(row, mwd_case="A")                                    # case A: no nesting required
    near = dict(entry=105.0, ext=98.0, draw=110.0, lv_tags="")
    q = Params(**BASE, mwd_nest="filter")
    assert BD.order_ok(bctx(row=a, p=q), sd, near, "AM", I(600), q) is None
    # 50/50: both sides armed in one window -> the second arming is refused and the window is gated
    f = Params(**BASE, neutral_5050="armed")
    c = bctx(row={}, p=f)
    assert BD.order_ok(c, sd, dict(entry=1, ext=0, lv_tags=""), "AM", I(600), f) is None
    assert BD.order_ok(c, SimpleNamespace(sign=-sgn, x=X), dict(entry=1, ext=0, lv_tags=""), "AM", I(600), f) == "x_bh_fifty_fifty"
    assert BD.gate(c, f, "AM", I(605), 605) == "x_bh_fifty_fifty" and BD.gate(c, f, "PM", I(840), 840) is None


def test_intermarket_switches_through_the_flags(monkeypatch):
    flags = dict(dxy_hi=True, bond_range=True, bond_dir=-1, decoupled=True)
    monkeypatch.setattr(BH, "im_flags", lambda day, p: flags)
    i = I(600)
    p = Params(**BASE, dxy_gate="block")
    c = bctx(row={}, p=p)
    assert BD.side_ok(c, p, 1, "AM", i) == "x_bh_dxy_gate" and BD.side_ok(c, p, -1, "AM", i) is None and "bh_dxy_hi" in c.dplan.tags
    t = Params(**BASE, dxy_gate="tag")
    assert BD.side_ok(bctx(row={}, p=t), t, 1, "AM", i) is None
    b = Params(**BASE, bond_dir="filter")
    assert BD.side_ok(bctx(row={}, p=b), b, 1, "AM", i) == "x_bh_bond_dir"
    flags["bond_dir"] = 1
    assert BD.side_ok(bctx(row={}, p=b), b, 1, "AM", i) is None
    for mode, kind in (("scalp", "scalp"), ("skip", "gate"), ("tag", None)):
        q = Params(**BASE, bond_range=mode)
        c = bctx(row={}, p=q)
        assert (BD.scalp_now(c, q, "AM", i) == "bond_range") == (kind == "scalp")
        assert (BD.gate(c, q, "AM", i, 600) == "x_bh_bond_range") == (kind == "gate")
        r = Params(**BASE, decoupled_mode=mode)
        c = bctx(row={}, p=r)
        assert (BD.scalp_now(c, r, "AM", i) == "decoupled") == (kind == "scalp")
        assert (BD.gate(c, r, "AM", i, 600) == "x_bh_decoupled") == (kind == "gate")
    flags.update(dxy_hi=False, bond_range=False, decoupled=False)
    c = bctx(row={}, p=p)
    assert BD.side_ok(c, p, 1, "AM", i) is None
    u = Params(**BASE, intermarket_model=True)                      # the umbrella turns the lot on
    flags.update(dxy_hi=True)
    c = bctx(row={}, p=u)
    assert BD.side_ok(c, u, 1, "AM", i) == "x_bh_dxy_gate"


def test_cot_tag_and_the_qshift_size(monkeypatch):
    monkeypatch.setattr(BH, "load_cot", lambda market="": object())
    monkeypatch.setattr(BH, "cot_state", lambda day, t, weeks=52: 1)
    p = Params(**BASE, cot_tag="filter")
    c = bctx(row={}, p=p)
    assert BD.side_ok(c, p, -1, "AM", I(600)) == "x_bh_cot" and BD.side_ok(c, p, 1, "AM", I(600)) is None
    assert "bh_cot_buy" in c.dplan.tags
    q = Params(**BASE, qshift_size=0.5)
    c = bctx(row=dict(qs_due=1, qs_trend=1), p=q)
    lvt = []
    sd = lambda s: SimpleNamespace(sign=s)
    assert BD.size_mult(c, sd(-1), I(600), q, lvt) == 0.5 and lvt == ["size_qshift"]          # against the 252-session trend
    assert BD.size_mult(c, sd(1), I(600), q, []) == 1.0
    assert BD.size_mult(bctx(row=dict(qs_due=0, qs_trend=1), p=q), sd(-1), I(600), q, []) == 1.0
    assert BD.size_mult(bctx(row=dict(qs_due=1, qs_trend=-1), p=q), sd(1), I(600), q, []) == 0.5      # the mirror
    assert BD.size_mult(bctx(row=dict(qs_due=1, qs_trend=1), p=q), sd(-1), I(540), q, []) == 1.0      # before 09:30: the row is not known


def test_bellwether_midnight_and_open_helpers():
    # 15m bellwether: the last completed 15m close against the midpoint of the last four 15m bars
    up = [(100 + 0.4 * k, 100.6 + 0.4 * k, 99.9 + 0.4 * k, 100.5 + 0.4 * k) for k in range(24)]
    c = bctx(rows=up, p=P0)
    k0 = I(570)
    assert BD.bellwether(c, k0 + 11) == 1                                                  # rising: above the midpoint
    assert BD.bellwether(c, c.start + 8) == 0                                              # 00:40: fewer than four complete 15m bars
    c = bctx(rows=[(200 - r[0], 200 - r[2], 200 - r[1], 200 - r[3]) for r in up], p=P0)
    assert BD.bellwether(c, k0 + 11) == -1
    p = Params(**BASE, bellwether_15m="filter")
    c = bctx(rows=up, p=p)
    assert BD.side_ok(c, p, -1, "AM", k0 + 11) == "x_bh_bellwether" and BD.side_ok(c, p, 1, "AM", k0 + 11) is None
    # the midnight open: bias confirmed once price sits beyond it in the bias direction
    ctx = bctx(rows=[FLAT] * 3, p=P0)
    ctx.opens = dict(midnight=99.0, **{"0830": 99.5, "0930": 100.0})
    ctx.c = np.full(len(ctx.c), 100.0)
    i = I(600)
    assert BD.midnight_confirmed(ctx, 1, i) is True and BD.midnight_confirmed(ctx, -1, i) is False
    q = Params(**BASE, midnight_confirm="filter")
    BD.plan(ctx.dplan, ctx, ctx.hist, q, set())
    ctx.lock = {"AM": dict(side=-1)}
    assert BD.side_ok(ctx, q, -1, "AM", i) == "x_bh_midnight_confirm"
    ctx.lock = {"AM": dict(side=1)}
    assert BD.side_ok(ctx, q, 1, "AM", i) is None
    a = Params(**BASE, bias_open="all")
    assert BD.reference_opens(ctx, a, "AM", i) == [99.0, 99.5, 100.0]
    ctx.opens["1330"] = 100.0
    assert BD.reference_opens(ctx, a, "PM", i) == []                                          # the 13:30 open has not printed yet
    assert BD.reference_opens(ctx, P0, "AM", i) == [99.0]
    assert BD.reference_opens(ctx, a, "AM", I(450)) == [99.0]                                    # 07:30: the 08:30 / 09:30 opens are not in
    s = Params(**BASE, bias_open_src="es_map")
    BD.apply_open_src(ctx, s, {"ext_midnight": 98.0})
    assert ctx.opens["midnight"] == 98.0
    BD.apply_open_src(ctx, Params(**BASE, bias_open_src="spy"), None)
    assert "midnight" in ctx.opens


def test_smt_both_needs_a_partner_and_both_directions():
    ctx = bctx(rows=[FLAT] * 3, p=P0)
    assert BD.smt_both_state(ctx, I(600)) == (False, False)                                    # no partner
    p = Params(**BASE, smt_both="skip")
    assert BD.side_ok(ctx, p, 1, "AM", I(600)) is None


def test_tf_lower_pref_and_cond_relock_and_untraded_arrays():
    conf = SimpleNamespace(opposing=lambda now, px, sgn, tfs, src: [(103.0 if sgn > 0 else 97.0, 104.0, 105.0, tfs[0], 0)])
    ctx = bctx(rows=[FLAT] * 3, p=P0)
    ctx.conf = conf
    now = pd.Timestamp("2026-06-23 09:30", tz="America/New_York")
    assert BD.tf_lower_pref(ctx, dict(react=1, react_tf="W"), 100.0, now, 0) == (103.0, "array", "tf_lower_D", 0, 0)
    assert BD.tf_lower_pref(ctx, dict(react=-1, react_tf="D"), 100.0, now, 0) == (97.0, "array", "tf_lower_4h", 0, 0)
    assert BD.tf_lower_pref(ctx, dict(react=0, react_tf=""), 100.0, now, 0) is None and BD.tf_lower_pref(ctx, None, 100.0, now, 0) is None
    # cond_draw: a close 0.25 x ADR5 (18) = 4.5 under the lock price fails an upper draw; the other side's nearest marked level is the new draw
    p = Params(**BASE, cond_draw=True)
    lk = dict(side=1, px=100.0, target=108.0, delivered=False, kind="pool", name="pdh1",
              marked=[(108.0, "pool", "pdh1", 1), (88.0, "pool", "pdl1", -1), (84.0, "pool", "pdl2", -1)])
    ctx.c = np.full(len(ctx.c), 100.0)
    ctx.c[ctx.start + 40] = 95.0
    spent = []
    assert BD.cond_relock(ctx, p, lk, ctx.start + 30, spent) is None                                       # not failed yet
    nl = BD.cond_relock(ctx, p, lk, ctx.start + 40, spent)
    assert nl["side"] == -1 and nl["target"] == 88.0 and nl["cond_used"] and spent == [108.0] and lk["side"] == 1
    assert BD.cond_relock(ctx, p, nl, ctx.start + 40, spent) is None                                      # once
    lk2 = dict(lk, side=-1, target=92.0, marked=[(112.0, "pool", "pdh1", 1), (92.0, "pool", "pdl1", -1)])
    ctx.c[ctx.start + 41] = 105.0
    nl2 = BD.cond_relock(ctx, p, lk2, ctx.start + 41, [])
    assert nl2["side"] == 1 and nl2["target"] == 112.0                                         # the mirror
    assert BD.cond_relock(ctx, p, dict(lk, delivered=True), ctx.start + 40, []) is None
    # untraded arrays: an array price already traded into since it formed is not a draw
    rows = [dict(top=108.0, bottom=106.0, tf="D", src=0, known=0.0, dead=1e30), dict(top=112.0, bottom=110.0, tf="D", src=2, known=0.0, dead=1e30)]
    ctx.conf = SimpleNamespace(opposing_ext=lambda now, px, sgn, tfs, src: rows)
    import mentorship.targets as TP
    orig = TP.extreme_since
    TP.extreme_since = lambda ctx_, i, t_ns, up: 107.0
    try:
        out = BD.untraded_arrays(ctx, 5, now, 100.0, 1, ("D",), (0, 2))
    finally:
        TP.extreme_since = orig
    assert [r[3:] for r in out] == [("D", 2)]                                                  # the traded FVG is gone, the gap stays


def test_neutral_gate_range_market_through_the_plan():
    flat = history()                                             # eight identical 90-108 sessions: a range
    p = Params(**BASE, neutral_gate=("range_market",), neutral_gate_mode="scalp")
    ctx = ctx_for(A_ROWS, d=NORMAL, p=p, hist=flat)
    ctx.bias_row, ctx.bias_by_cut, ctx.lock = {}, {}, {}
    BD.plan(ctx.dplan, ctx, flat, p, set())
    assert ctx.dplan.info["drr_ng"] == ["range"]
    assert BD.scalp_now(ctx, p, "AM", I(600)) == "ng_range_market"
    from test_review_fixes import rth_day
    trend = [rth_day(x.index[0].date(), 100 + 8 * (k + 1), 100 + 8 * k, 100 + 8 * k + 7) for k, x in enumerate(history())]
    ctx = ctx_for(A_ROWS, d=NORMAL, p=p, hist=trend)
    ctx.bias_row, ctx.bias_by_cut, ctx.lock = {}, {}, {}
    BD.plan(ctx.dplan, ctx, trend, p, set())
    assert ctx.dplan.info["drr_ng"] == []


# --- the lock (run_day) --------------------------------------------------------------------------------------------------------

def _go(rows=A_ROWS, bias_by_cut=None, bias=None, d=NORMAL, hist=None, **kw):
    p = Params(**{**BASE, **kw})
    locks, log, skips = [], [], []
    tr = S.run_day(day(rows, d=d, spike=True), hist or history(d), "ES", p, 5, locks=locks, log=log, skips=skips,
                   bias_by_cut=bias_by_cut if bias_by_cut is not None else A_LOCK, bias=bias)
    return tr, locks, skips


def test_ordered_lock_picks_the_inefficiency_first_and_the_mirror_picks_the_down_side():
    cut = {570: dict(draw_up=107.0, draw_up_name="D_fvg", draw_dn=94.0, draw_dn_name="D_swing_low", pd=-1)}
    near = _go(bias_by_cut=cut, draw_lock_pick="nearest")[1]
    assert near and near[0]["side"] == -1                              # the nearer level (94, six away; the FVG is seven) wins the old pick
    ordd = _go(bias_by_cut=cut, draw_lock_pick="ordered")[1]
    assert ordd[0]["side"] == 1 and ordd[0]["name"] == "htf_D_fvg"      # the FVG up is an inefficiency: it comes first
    cut2 = {570: dict(draw_up=106.0, draw_up_name="D_swing_high", draw_dn=93.0, draw_dn_name="D_fvg", pd=1)}
    assert _go(bias_by_cut=cut2, draw_lock_pick="nearest")[1][0]["side"] == 1
    assert _go(bias_by_cut=cut2, draw_lock_pick="ordered")[1][0]["side"] == -1        # the mirror
    ext = _go(bias_by_cut=cut, draw_lock_pick="ordered", draw_ext_target=True)[1]
    assert "ext_from" in ext[0] and ext[0]["side"] == 1


def test_htf_bias_ordered_end_to_end_gates_the_bar_loop():
    row = dict(draw_ord=-1, draw=-1, react=0, pd=0, combo=0, px=100.0)
    assert len(_go()[0]) == 1                                           # the A scenario: a long order to the locked draw (104)
    tr, locks, sk = _go(bias=row, htf_bias="ordered")
    assert tr == []                                                     # the long scenario is refused: the bias is down
    tr2, *_ = _go(bias=dict(row, draw_ord=1), htf_bias="ordered")
    assert len(tr2) == 1 and tr2[0].side == "long"
    tr3, *_ = _go(bias=dict(row, draw_ord=0), htf_bias="ordered")
    assert tr3 == []                                                    # neutral + bias_neutral="skip"
    tr4, *_ = _go(bias=dict(row, draw_ord=0), htf_bias="ordered", bias_neutral="both")
    assert len(tr4) == 1 and len(tr4[0].exits) > 1
    tr5, *_ = _go(bias=dict(row, draw_ord=0), htf_bias="ordered", bias_neutral="scalp")
    assert len(tr5) == 1 and len(tr5[0].exits) == 1                     # the neutral day is scalped: one exit, no runner
    tr6, *_ = _go(bias=dict(row, draw_ord=0, draw=0, combo=0), no_narrative_scalp=True)
    assert len(tr6) == 1 and len(tr6[0].exits) == 1                     # Ep02.6: no narrative -> scalp (htf_bias off)


def test_objective_met_stop_and_neutral_gate_through_run_day():
    row = dict(obj_day=1, obj_week=0, px=100.0, react=0, draw=0, pd=0)
    tr, locks, sk = _go(bias=row, objective_met_stop="day")
    assert tr == []
    assert len(_go(bias=dict(row, obj_day=0), objective_met_stop="day")[0]) == 1
    tr2 = _go(bias=dict(row, fifty=1), neutral_gate=("fifty_fifty",), neutral_gate_mode="scalp")[0]
    assert len(tr2) == 1 and len(tr2[0].exits) == 1 and "bh_ng_fifty_fifty" in tr2[0].dw_tags
    tr3 = _go(bias=dict(row, fifty=1), neutral_gate=("fifty_fifty",), neutral_gate_mode="skip")[0]
    assert tr3 == []


def test_cond_draw_in_run_day_relocks_once_the_draw_fails():
    # price turns down from the lock: the long draw fails and the lock switches to the down side (or stays when nothing marked)
    rows = [(100.0, 100.1, 99.5, 99.6), (99.6, 99.7, 94.0, 94.2)] + [(94.2, 94.4, 93.8, 94.0)] * 10
    tr, locks, sk = _go(rows=rows, cond_draw=True)
    assert locks
    assert locks[0]["side"] in (1, -1, 0)


def test_study_variants_build():
    names = list(study.DECISIONS)
    for nm in names[names.index("X16_journal_tags_off") + 1:]:
        q = replace(Params(), **study.DECISIONS[nm])
        assert isinstance(q.bx, str)
