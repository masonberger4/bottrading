"""Scorecard cards: the new engine concepts (mentorship/cards_rules.py and the card hooks in me2.py)."""
from types import SimpleNamespace

import pandas as pd

from mentorship import cards_rules as CR, me2
from mentorship.strategy import Params


def _day(d, hi):
    ix = pd.date_range(f"{d} 09:30", periods=3, freq="5min")
    return pd.DataFrame({"open": hi - 1, "high": [hi - 2, hi, hi - 1], "low": hi - 5, "close": hi - 1}, index=ix)


def test_ath_map_is_the_high_of_the_days_before():
    ds = [_day("2024-01-02", 100.0), _day("2024-01-03", 90.0), _day("2024-01-04", 120.0), _day("2024-01-05", 110.0)]
    m = CR.ath_map(ds)
    assert pd.Timestamp("2024-01-02").date() not in m
    assert [m[pd.Timestamp(d).date()] for d in ("2024-01-03", "2024-01-04", "2024-01-05")] == [100.0, 100.0, 120.0]


class _Short:
    sign = -1

    @staticmethod
    def x(v):
        return -v                      # side space of a short: mirrored prices


class _Long:
    sign = 1

    @staticmethod
    def x(v):
        return v


def test_ath_block_only_near_the_high_and_only_shorts():
    ctx = SimpleNamespace(ath=1000.0)
    p = Params(ath_rule="no_top_pick", ath_near_frac=0.02)
    ts = {"entry": -995.0, "lv_tags": "reversal"}               # a reversal short 0.5 % under the ATH
    assert CR.ath_block(ctx, _Short, ts, p) == "x_ath_top_pick"
    assert CR.ath_block(ctx, _Short, {"entry": -995.0, "lv_tags": ""}, p) is None      # a structure short stays
    assert CR.ath_block(ctx, _Short, {"entry": -900.0, "lv_tags": "reversal"}, p) is None   # 10 % under: not near
    assert CR.ath_block(ctx, _Long, {"entry": 995.0, "lv_tags": "reversal"}, p) is None
    assert CR.ath_block(ctx, _Short, {"entry": -995.0, "lv_tags": ""}, Params(ath_rule="longs_only")) == "x_ath_no_short"
    assert CR.ath_block(SimpleNamespace(ath=None), _Short, ts, p) is None


def test_depth_trail_arms_at_the_share_and_trails_under_each_bar_low():
    p = Params(depth_trail=0.75)
    pos = {"stop": 90.0, "levels": [110.0], "left": 2}
    d = {}
    lv = [110.0]
    me2._depth_trail(pos, d, 5, 104.0, 101.0, 103.0, p, lv, 100.0)       # 40 % of the way: not armed
    assert pos["stop"] == 90.0 and not d.get("depth_armed")
    me2._depth_trail(pos, d, 6, 108.0, 104.0, 107.0, p, lv, 100.0)       # 80 %: armed, stop under this bar's low
    assert d["depth_armed"] and pos["stop"] == 104.0 - p.tick
    me2._depth_trail(pos, d, 7, 107.5, 103.0, 106.0, p, lv, 100.0)       # a lower low never lowers the stop
    assert pos["stop"] == 104.0 - p.tick
    me2._depth_trail(pos, d, 8, 109.0, 106.0, 108.5, p, lv, 100.0)
    assert pos["stop"] == 106.0 - p.tick


def test_card_defaults_of_the_new_concepts():
    p = Params()
    assert (p.depth_trail, p.ath_rule, p.fed_chair_skip_am, p.neutral_5050, p.tgif_thu) == (0.75, "no_top_pick", True, "armed", True)


def _bars(d, rows, start="09:30"):
    ix = pd.date_range(f"{d} {start}", periods=len(rows), freq="1min")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=ix)


def test_fpfvg_needs_a_0931_middle_candle_and_lives_its_week():
    gap_on_0930 = [(100, 101, 99, 100.5), (101, 105, 100.8, 104), (104.5, 106, 103, 105)]       # middle 09:31, gap 101 -> 103
    g = _bars("2024-01-08", gap_on_0930)                       # a Monday
    z = CR.fpfvg_of(g)
    assert z["sign"] == 1 and (z["bottom"], z["top"]) == (101.0, 103.0) and z["ts"] == g.index[2]
    assert CR.fpfvg_of(_bars("2024-01-08", gap_on_0930, start="09:29")) is None              # c1 09:29 is not RTH: no 09:31 middle candle in 3 bars
    flat = [(104, 105, 103.5, 104)] * 3                       # above the gap: unfilled
    ds = [g, _bars("2024-01-09", flat), _bars("2024-01-15", flat)]
    m = CR.card_map(ds, Params(fpfvg_def="time", fvg_carry_days=0, range_regime="off"))
    d = [x.index[0].date() for x in ds]
    assert len(m[d[0]]["fpfvg"]) == 1 and len(m[d[1]]["fpfvg"]) == 1 and m[d[2]]["fpfvg"] == []   # the next week drops it (no carry)
    m = CR.card_map(ds, Params(fpfvg_def="time", fvg_carry_days=20, range_regime="off"))
    assert len(m[d[2]]["fpfvg"]) == 1                          # carried while unfilled
    filled = [(100, 101, 100.5, 100.8)] * 2 + [(100, 101, 100.9, 100.9)]
    ds2 = [g, _bars("2024-01-09", filled), _bars("2024-01-15", flat)]
    assert CR.card_map(ds2, Params(fpfvg_def="time", fvg_carry_days=20, range_regime="off"))[d[2]]["fpfvg"] == []   # a low through 101 filled it


def test_range_gate_blocks_breakouts_only_on_a_range_day():
    ctx = SimpleNamespace(cards={"rr": (110.0, 90.0, 105.0, 95.0, True)})
    p = Params(range_regime="fade")
    assert CR.range_gate(ctx, _Long, {"entry": 106.0}, p) == "x_range_breakout"
    assert CR.range_gate(ctx, _Long, {"entry": 100.0}, p) is None
    assert CR.range_gate(ctx, _Short, {"entry": -94.0}, p) == "x_range_breakout"
    assert CR.range_gate(SimpleNamespace(cards={"rr": (110.0, 90.0, 105.0, 95.0, False)}), _Long, {"entry": 106.0}, p) is None


def test_wick_priority_moves_the_limit_to_the_candle1_wick_ce():
    from mentorship.levels import Zone
    import numpy as np
    sd = SimpleNamespace(o=np.array([100.0, 101.0, 106.0, 107.0]), c=np.array([100.5, 101.0, 107.0, 108.0]),
                         h=np.array([101.0, 104.0, 108.0, 109.0]), l=np.array([99.0, 100.0, 105.0, 106.0]))

    g = Zone("bull", top=106.0, bottom=104.0, i=3)                     # candle 1 = bar 1: body top 101, wick to 104 (3 pts >= the 2-pt gap)
    p = Params(wick_priority=True, min_risk_pts=0.5)
    e, s = CR._wick_first(sd, g, 3, p, 104.0, 99.0)
    assert e == 102.5 and s == 101.0 - p.pad
    e, s = CR._wick_first(sd, Zone("bull", top=108.0, bottom=104.0, i=3), 3, p, 104.0, 99.0)   # a 4-pt gap outgrows the wick: unchanged
    assert (e, s) == (104.0, 99.0)
