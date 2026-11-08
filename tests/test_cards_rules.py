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
    assert (p.depth_trail, p.ath_rule, p.fed_chair_skip_am, p.drange_scalp, p.neutral_5050, p.tgif_thu) == (0.75, "no_top_pick", True, True, "armed", True)
