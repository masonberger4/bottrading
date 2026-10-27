"""Caption-gap pass, package bias_htf#1/7: the flip triggers and the daily / weekly columns (bh1.py) on hand-made books (second file of tests/test_caption_gap_bh1.py)."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1 as BH, bh1e as BE, htf, levels as L
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, history  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import (dsess, arr, flip_of, K, mirror_book, mirror_arr, BR, week_book, weekly_arrs)  # noqa: E402


# --- item 8: bias -> neutral -> opposite through an inversion ---------------------------------------------------------------------

INV3_BOOK = [(3950, 3960, 3940, 3955), (3955, 3975, 3950, 3970), (3970, 3990, 3976, 3988), (3988, 4040, 3995, 4035), (4035, 4070, 4030, 4065), (4065, 4075, 4000, 4060),
             (4060, 4090, 4020, 4085), (4085, 4100, 4040, 4095), (4095, 4096, 3970, 3985), (3985, 3990, 3950, 3955), (3955, 3965, 3945, 3950), (3950, 3960, 3940, 3945)]


def step_states(book, arrs, triggers, cfg=None, start_state=1):
    """The state after each session when FlipState starts in `start_state` (the unit-level view of htf._flip's new triggers)."""
    d = dsess(book)
    w = htf.weeks(d)
    fs = BH.FlipState(d, w, arrs, triggers, cfg or {})
    out, state, last_week = [], start_state, None
    for k in range(len(d)):
        state = fs.step(k, state, last_week)
        out.append(state)
        if k in fs.wk_rows:
            last_week = fs.wk_rows[k]
    return out


def test_flip_inv3():
    F = arr("bull", "fvg", 3976, 3960, 3)                                # the supporting daily imbalance under the swing low 4000
    pl = L.pivots(*(np.array([r[i] for r in INV3_BOOK], float) for i in (1, 2)), 1)[1]
    assert any(q.price == 4000.0 and q.known == 6 for q in pl)          # the guarding swing low
    st = step_states(INV3_BOOK, [F], ("inv3",))
    assert st[:8] == [1] * 8 and st[8] == 0 and st[9] == 0 and st[10] == -1 and st[11] == -1       # +1 -> 0 (low 3970 under 4000 and into F) -> a close under F (3955) -> a held retest (3965 high, 3950 close): -1
    d = dsess(INV3_BOOK)
    fl = flip_of(d, [F], ("wk_dc", "inv3"))                              # applied from the NEXT session through htf._flip (no look-ahead)
    assert fl[8] == fl[7]                                                # the table never shows a state on the session that made it
    book2 = INV3_BOOK[:10] + [(3955, 3975, 3945, 3972)]                  # the retest day closes back above F's bottom
    assert step_states(book2, [F], ("inv3",))[10] == 0
    mb = mirror_book(INV3_BOOK)
    st_m = step_states(mb, [mirror_arr(F)], ("inv3",), start_state=-1)
    assert st_m[:8] == [-1] * 8 and st_m[8] == 0 and st_m[10] == 1


# --- item 9: the ceiling ladder ---------------------------------------------------------------------------------------------------

def test_ceiling_ladder():
    book = [(4000, 4010, 3990, 4005)] * 2 + [(4005, 4020, 3995, 4010), (4010, 4030, 4000, 4020), (4020, 4040, 4010, 4030), (4030, 4048, 4020, 4040), (4040, 4055, 4030, 4049),
                                           (4049, 4062, 4053, 4060), (4060, 4070, 4056, 4066)]
    vi = arr("bear", "vi", 4052, 4050, 1)                                 # the overhead imbalance 4050-4052
    d = dsess(book)
    r = BH.ceiling_columns([3, 4, 5, 7, 8], d, [vi])
    assert r["ceiling"][:3] == [4052.0] * 3 and r["ladder_dn"][:3] == [1, 1, 1]                          # closes stay under it: the lower arrays are drawn in order
    # session 6 traded to 4055 (above) with a close at 4049; session 7 (low 4053) held above it as support: the ladder is suspended (and no body is left under it)
    assert r["ladder_dn"][3] == 1 and r["ladder_dn"][4] == 0                                             # (row 7 still sees only the trade above; row 8 sees the held low 4053)
    fv = arr("bear", "fvg", 4090, 4080, 1)
    r2 = BH.ceiling_columns([8], d, [vi, fv])
    assert r2["ceiling"] == [4090.0] and r2["ladder_dn"] == [0]                                          # a second imbalance above: still suspended (two imbalances supporting)
    dm = dsess(mirror_book(book))                                                                        # the mirror: a floor and ladder_up
    rm = BH.ceiling_columns([3, 4, 5, 7, 8], dm, [mirror_arr(vi)])
    assert rm["floor"][:3] == [K - 4052.0] * 3 and rm["ladder_up"][:3] == [1, 1, 1] and rm["ladder_up"][3] == 1 and rm["ladder_up"][4] == 0
    # the engine: the lock follows the ladder
    p = Params(**BASE, ceiling_ladder=True)
    lock = dict(side=1, target=105.0, kind="pool", name="pdh1", marked=[(105.0, "pool", "pdh1", 1), (93.0, "array", "htf_D_fvg", 0), (90.0, "pool", "pdl1", -1)], delivered=False)
    ctx = mk(D0, history(D0), p, rows=[], bias_row=BR(ladder_dn=1, ladder_up=0))
    out = BE.lock_post(ctx, p, BR(ladder_dn=1, ladder_up=0), 570, "AM", at(ctx, "09:30"), 100.0, dict(lock), [])
    assert out["side"] == -1 and out["target"] == 93.0 and "ceiling_ladder" in out["bh1"]               # the nearest lower array first (L14 ladder), then the sell-side
    out2 = BE.lock_post(ctx, p, BR(ladder_dn=0, ladder_up=0), 570, "AM", at(ctx, "09:30"), 100.0, dict(lock), [])
    assert out2["side"] == 1


# --- item 17: the OB low traded through, objective met ---------------------------------------------------------------------------

def test_flip_ob_low_touch():
    ob = arr("bull", "ob", 4020, 4000, 0, ce=4010)                        # the last bullish OB candle: low 4000
    book = [(4005, 4030, 4005, 4025), (4025, 4040, 4015, 4035), (4035, 4045, 4020, 4040), (4040, 4042, 3999.75, 4010), (4010, 4020, 4000.0, 4015)]
    obj = np.ones(5, int)
    st = step_states(book, [ob], ("ob_low_touch",), {"obj": obj})
    assert st == [1, 1, 1, 0, 0]                                         # a low of 3999.75 with a close at 4010: neutral (not bearish) from the next session
    st2 = step_states(book[:3] + [(4040, 4042, 4000.0, 4010)], [ob], ("ob_low_touch",), {"obj": obj})
    assert st2[3] == 1                                                   # a low AT the OB low is not a trade below it
    assert step_states(book, [ob], ("ob_low_touch",), {"obj": np.zeros(5, int)})[3] == 1             # the objective is not met: no change
    assert step_states(book, [ob], ("ob_low_touch",), {})[3] == 0         # no objective columns: any state
    assert BH.needs_objective(Params(flip_triggers=("ob_mt", "ob_low_touch")))       # the table builds the B17.3 columns first
    dm = mirror_book(book)
    assert step_states(dm, [mirror_arr(ob)], ("ob_low_touch",), {"obj": obj}, start_state=-1) == [-1, -1, -1, 0, 0]


# --- item 73: the indecisive weekly candle at a weekly FVG ---------------------------------------------------------------------------

def test_flip_wk_rb():
    wfvg = arr("bull", "fvg", 4040, 4020, 0, tf="W")
    rows = [(4000, 4000, 4000, 4000), (4000, 4050, 4000, 4000), (4000, 4000, 3990, 4000), (4000, 4000, 4000, 4000), (4000, 4005, 4000, 4005)]      # a week 4000 / 4050 / 3990 / 4005: body 5 of 60
    nxt = [(4004, 4006, 3998, 4002)]
    st = step_states(rows + nxt, [wfvg], ("wk_rb",))
    assert st[:4] == [1, 1, 1, 1] and st[4] == 0                          # the Friday close of the indecisive week: neutral
    assert st[5] == 1                                                     # Monday high 4006 > the body top 4005: bullish resumption
    assert step_states(rows + [(4004, 4004, 3989, 3995)], [wfvg], ("wk_rb",))[5] == -1           # a trade below the week's low 3990: bearish
    assert step_states(rows + [(4003, 4005, 3995, 4000)], [wfvg], ("wk_rb",))[5] == 0            # inside the range: still neutral
    rows2 = [(4000, 4000, 4000, 4000), (4000, 4050, 4000, 4000), (4000, 4000, 3990, 4000), (4000, 4000, 4000, 4000), (4000, 4040, 3990, 4040)]   # a decisive week (body 40 of 60)
    assert step_states(rows2, [wfvg], ("wk_rb",))[4] == 1
    far = arr("bull", "fvg", 4300, 4280, 0, tf="W")                       # no weekly FVG under the week: no trigger
    assert step_states(rows, [far], ("wk_rb",))[4] == 1
    assert step_states(mirror_book(rows) + mirror_book(nxt), [mirror_arr(wfvg)], ("wk_rb",), start_state=-1)[4] == 0


# --- item 75: the daily breaker ----------------------------------------------------------------------------------------------------

DB_BOOK = [(4060, 4080, 4050, 4075), (4075, 4100, 4070, 4095), (4095, 4098, 4060, 4065), (4065, 4085, 4050, 4080), (4080, 4110, 4062, 4105), (4105, 4125, 4095, 4120),
           (4120, 4122, 4040, 4045), (4045, 4070, 4040, 4055), (4055, 4105, 4050, 4100)]


def test_flip_d_breaker():
    d = dsess(DB_BOOK)
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    zs = L.breakers(o, h, l, c, 1, "range")
    z = [q for q in zs if q.kind == "bear"][0]
    assert (z.bottom, z.top, z.i) == (4060.0, 4098.0, 6)                  # the down-close candle 4060-4098 after the sweep above 4100 and the close 4045 under the swing low 4050
    st = step_states(DB_BOOK, [], ("d_breaker",), start_state=0)
    assert st[:7] == [0] * 7 and st[7] == -1 and st[8] == 0               # the retest day (high 4070 into the zone, close 4055 under it): -1; a close above the zone top 4098: neutral
    no_retest = DB_BOOK[:7] + [(4045, 4055, 4040, 4050)] + DB_BOOK[8:]    # never traded into the zone: no state
    assert step_states(no_retest, [], ("d_breaker",), start_state=0)[7] == 0
    st_m = step_states(mirror_book(DB_BOOK), [], ("d_breaker",), start_state=0)
    assert st_m[7] == 1 and st_m[8] == 0


# --- item 78: a retracement inside a bullish HTF is not a flip -------------------------------------------------------------------------

def test_b9_persist():
    # sessions 0-3 rally through a bearish OB's MT (3990) -> +1; a swing low 4005 (session 5); a bull FVG 3995-4010 below; the bull OB (MT 4030) is closed through on session 8
    base = [(3975, 3985, 3970, 3980), (3980, 3992, 3975, 3985), (3985, 4000, 3984, 3995), (3995, 4030, 3994, 4025), (4025, 4040, 4015, 4035), (4035, 4045, 4005, 4040),
            (4040, 4060, 4025, 4055), (4055, 4065, 4045, 4060)]
    bear = arr("bear", "ob", 4000, 3980, 0, ce=3990)
    bull = arr("bull", "ob", 4040, 4020, 0, ce=4030)
    fvg = arr("bull", "fvg", 4010, 3995, 3)

    def run(low, cfg):
        d = dsess(base + [(4060, 4062, low, 4025), (4025, 4030, 4020, 4026)])
        return htf._flip(d, htf.weeks(d), [bear, bull, fvg], ("ob_mt",), cfg)[list(d.index)[9]]
    assert run(4015, None) == -1 and run(4015, {"persist": 1}) == 1        # the swing low 4005 and the lower FVG hold: no flip
    assert run(4000, {"persist": 1}) == -1                                 # the low 4000 breaks the swing low 4005: the flip applies
    assert run(3990, {"persist": 1}) == -1                                 # (and the FVG is fully traded through)
    dm = dsess(mirror_book(base + [(4060, 4062, 4015, 4025), (4025, 4030, 4020, 4026)]))
    ar = [mirror_arr(bear), mirror_arr(bull), mirror_arr(fvg)]
    assert htf._flip(dm, htf.weeks(dm), ar, ("ob_mt",), None)[list(dm.index)[9]] == 1 and htf._flip(dm, htf.weeks(dm), ar, ("ob_mt",), {"persist": 1})[list(dm.index)[9]] == -1
