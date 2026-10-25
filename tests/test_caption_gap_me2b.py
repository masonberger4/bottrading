"""Caption-gap pass, package management_exits #2/3, part B: the unit tests of the partial specs (management_partials_trailing_exits.md 36, 49, 50, 52, 53, 54, 55, 67, 68, 87, 108) - the harness of
test_caption_gap_me2a.py (hand-made one-minute books, the me2.py hooks called bar by bar). No platform-specific paths; nothing here needs market data."""
from datetime import date

import pandas as pd
import pytest

from mentorship import me1, me2
from mentorship.strategy import Params

from test_caption_gap_me1a import NY, flatrows, mkctx, mkpos, pk, reasons
from test_caption_gap_me2a import fill2, rung, step2


# --- X3-htf-target-bank-partial (36) -----------------------------------------------------------------------------------------------------------------

def test_htf_bank():
    rows = flatrows(2, 4100.0, 1.0) + [(4100, 4151, 4099, 4150), (4150, 4152, 4149, 4151)]
    ctx = mkctx(rows)
    p = pk(htf_bank=0.5, be_pad_pts=1.0)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4170.0,), n=6)
    fill2(ctx, sd, pos, tr, p, htf_draw=(4150.0, 4160.0))
    step2(ctx, sd, pos, tr, p, 1)
    assert pos["left"] == 6 and pos["stop"] == 4090.0                                       # not yet in the array
    step2(ctx, sd, pos, tr, p, 2)                                                           # a bar to 4151: 3 of the 6 units go, the stop to BE + pad, no adds
    assert reasons(tr) == ["htf_bank"] and pos["left"] == 3 and pos["stop"] == pytest.approx(4101.0) and pos["no_adds"]
    assert tr.exits[0][1] == 4150.0
    # a short setup armed inside that FVG later in the session is rejected (a long one, or one outside it, is not)
    short = ctx.sides_map[-1]
    assert me2.order_block(ctx, short, 3, p, "AM", short.x(4155.0)) == "x_htf_touch"
    assert me2.order_block(ctx, short, 3, p, "AM", short.x(4140.0)) is None
    assert me2.order_block(ctx, ctx.sides_map[1], 3, p, "AM", 4155.0) is None
    assert me2.order_block(ctx, short, 3, pk(), "AM", short.x(4155.0)) is None
    # a single banking only
    step2(ctx, sd, pos, tr, p, 3)
    assert reasons(tr) == ["htf_bank"]


# --- X3-running-down-equity-trigger (49) ---------------------------------------------------------------------------------------------------------------

def test_rde_partials():
    rows = [(4000, 4001, 3999, 4000), (4000, 4010, 3999.5, 4009), (4009, 4020, 4008, 4019), (4014, 4015, 4012, 4013), (4013, 4030, 4012.5, 4029), (4029, 4029.5, 4027, 4028), (4028, 4032, 4027.5, 4031),
            (4031, 4031.5, 4029, 4030), (4030, 4035, 4029.5, 4034), (4034, 4034.5, 4031, 4032), (4032, 4036, 4031.5, 4035.5)]
    ctx = mkctx(rows)
    p = pk(rde_partials=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4040.0,))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert pos["me2"]["rde_arm_i"] == 4 and not tr.exits                                    # armed at 4030 (0.75 of the way to 4040); the pivot high 4020 formed before arming
    step2(ctx, sd, pos, tr, p, 5, 7)
    assert not tr.exits
    step2(ctx, sd, pos, tr, p, 8)                                                           # the pivot high 4032 is exceeded: 20 % of the units at arming time at 4032.25
    assert reasons(tr) == ["rde"] and tr.exits[0][1] == pytest.approx(4032.25) and tr.exits[0][2] == 2
    step2(ctx, sd, pos, tr, p, 9, 10)                                                       # the pivot high 4035 is exceeded: the next 20 % at 4035.25
    assert reasons(tr) == ["rde", "rde"] and tr.exits[1][1] == pytest.approx(4035.25) and pos["left"] == 6
    pos2, tr2, sd2 = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4040.0,))
    fill2(ctx, sd2, pos2, tr2, pk())
    step2(ctx, sd2, pos2, tr2, pk(), 1, 10)
    assert not tr2.exits


# --- X3-020-runner-peel-singles (50) / X8-nwog-ce-pullback-hold (92) -------------------------------------------------------------------------------------

PEEL = [(4098, 4099, 4097, 4098), (4098, 4111, 4097.5, 4110.5), (4110.5, 4112, 4110, 4111.5), (4111.5, 4114, 4111, 4112), (4112, 4113, 4111.5, 4112.5), (4112.5, 4114.25, 4112, 4113),
        (4113, 4113.5, 4111.8, 4112.5), (4112.5, 4114.5, 4112.25, 4114), (4114, 4115, 4113.5, 4114.5), (4114.5, 4116, 4114, 4115.5), (4115.5, 4115.75, 4113.5, 4114), (4114, 4114.5, 4113, 4113.5)]


def test_peel_singles():
    ctx = mkctx(PEEL)
    p = pk(peel_singles=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4098.0, 4090.0, levels=(4120.0,), n=16)
    pos["left"] = 4                                                                       # 75 % closed
    fill2(ctx, sd, pos, tr, p, nwog=(4100.0, 4120.0))
    step2(ctx, sd, pos, tr, p, 6)
    assert not tr.exits
    step2(ctx, sd, pos, tr, p, 7)                                                         # a poke 1 tick over the relative equal highs (4114 / 4114.25) peels one lot
    assert reasons(tr) == ["peel"] and pos["left"] == 3 and tr.exits[0][1] == pytest.approx(4114.5)
    step2(ctx, sd, pos, tr, p, 8)                                                         # the next higher high peels one
    step2(ctx, sd, pos, tr, p, 9)                                                         # and the next
    assert reasons(tr) == ["peel"] * 3 and pos["left"] == 1
    step2(ctx, sd, pos, tr, p, 10)                                                        # one unit left: the stop under the latest 1m pivot low, no more peels
    assert pos["left"] == 1 and pos["me2"]["peel_end"] and pos["stop"] == pytest.approx(4111.55)
    assert pos["stop_log"][-1][0] == "peel_last"
    # below the CE nothing is peeled
    pos, tr, sd = mkpos(ctx, 1, 0, 4098.0, 4090.0, levels=(4120.0,), n=16)
    pos["left"] = 4
    fill2(ctx, sd, pos, tr, p, nwog=(4115.0, 4135.0))
    step2(ctx, sd, pos, tr, p, 6, 9)
    assert not tr.exits


def test_gap_q_hold():
    # NWOG 4100-4120 with the CE (4110) rung filled: a pullback to 4105.5 holds, a bar to 4104.75 closes the runners
    rows = [(4100, 4101, 4099, 4100), (4100, 4112, 4099.5, 4111), (4111, 4112, 4105.5, 4107), (4107, 4108, 4104.75, 4105)]
    ctx = mkctx(rows)
    p = pk(gap_q_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4110.0, 4125.0), fracs=(0.8, 0.2), kinds=["array", "pool"])
    fill2(ctx, sd, pos, tr, p, nwog=(4100.0, 4120.0))
    rung(ctx, sd, pos, tr, p, 0, 1)
    assert pos["me2"]["gap_q"] == 4105.0
    step2(ctx, sd, pos, tr, p, 2)
    assert pos["left"] == 2
    step2(ctx, sd, pos, tr, p, 3)
    assert reasons(tr) == ["t1", "gap_q"] and pos["left"] == 0 and tr.exits[-1][1] == 4105.0
    # a rung that is not at the NWOG CE sets nothing
    pos, tr, sd = mkpos(ctx, 1, 0, 4100.0, 4090.0, levels=(4104.0, 4125.0), fracs=(0.8, 0.2), kinds=["array", "pool"])
    fill2(ctx, sd, pos, tr, p, nwog=(4100.0, 4120.0))
    rung(ctx, sd, pos, tr, p, 0, 1)
    assert pos["me2"].get("gap_q") is None


# --- X3-027-pm-runner-macro (52) -------------------------------------------------------------------------------------------------------------------

def test_pm_macro_runner():
    from mentorship import newscal
    t0 = 15 * 60 + 40
    rows = [(4000, 4001, 3999, 4000)] + [(4000, 4001, 3999.5, 4000.5)] * 4 + [(4000.5, 4012, 4000, 4011)] + [(4011, 4012, 4010, 4011.5)] * 4 + [(4011.5, 4021, 4011, 4020)] + [(4020, 4021, 4019, 4020)] * 4
    ctx = mkctx(rows, t0=t0)
    p = pk(pm_macro_runner=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4020.0, 4030.0), fracs=(1 / 3, 1 / 3, 1 / 3), n=3)
    tr.session = "PM"
    fill2(ctx, sd, pos, tr, p)
    assert pos["runner"] and len(pos["levels"]) == 2                                      # the last unit has no target
    rung(ctx, sd, pos, tr, p, 0, 5)
    assert pos["stop"] == pytest.approx(4001.0) and pos["left"] == 2                      # partial 1: the stop to +1 pt
    rung(ctx, sd, pos, tr, p, 1, 10, q=1)                                                 # the day-high rung closes 1
    assert pos["left"] == 1
    step2(ctx, sd, pos, tr, p, 11, 13)                                                    # the 15:49 bar is bar 9... bars here run 15:51 +: see below
    # the 15:45-15:50 macro is a T7 window with the switch only
    assert newscal.macro_wins(15 * 60 + 47) == [] and newscal.macro_wins(15 * 60 + 47, p) == ["1545"]
    assert newscal.macro_wins(15 * 60 + 30, pk()) == ["1515"]


def test_pm_macro_runner_closes_at_1550():
    t0 = 15 * 60 + 40
    rows = [(4000, 4001, 3999, 4000)] + [(4000, 4001, 3999.5, 4000.5)] * 13
    ctx = mkctx(rows, t0=t0)
    p = pk(pm_macro_runner=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4020.0, 4030.0), fracs=(1 / 3, 1 / 3, 1 / 3), n=3)
    tr.session = "PM"
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 8)                                                      # bars 15:41 .. 15:48 (closing 15:49): still open
    assert pos["left"] == 3
    step2(ctx, sd, pos, tr, p, 9)                                                         # the 15:49 bar closes at 15:50: out
    assert reasons(tr) == ["pm_macro_exit"] and pos["left"] == 0
    # an AM trade is untouched
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4020.0, 4030.0), fracs=(1 / 3, 1 / 3, 1 / 3), n=3)
    fill2(ctx, sd, pos, tr, p)
    assert not pos["runner"]


# --- X3-runner-swing-low-must-hold (53) ------------------------------------------------------------------------------------------------------------

HH = [(4090, 4091, 4089, 4090.5), (4090.5, 4100, 4089.5, 4099), (4099, 4099.5, 4098, 4098.5), (4098.5, 4101, 4098.2, 4100.5), (4100.5, 4104, 4100, 4103), (4103, 4103.5, 4100.5, 4101)]


@pytest.mark.parametrize("low,exits", [(4097.75, True), (4098.25, False)])
def test_hh_low_hold(low, exits):
    rows = HH + [(4101, 4102, low, 4101.5)]
    ctx = mkctx(rows)
    p = pk(hh_low_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4080.0, levels=(4140.0,), n=6)
    pos["t1_done"] = True                                                                # after the first partial
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 5)
    assert pos["me2"]["hh_low"] == 4098.0                                                  # the lowest low between the pivot highs 4100 and the bar that took it out
    step2(ctx, sd, pos, tr, p, 6)
    assert (reasons(tr) == ["hh_low"] and pos["left"] == 0) == exits
    if exits:
        assert tr.exits[0][1] == pytest.approx(4098.0)


def test_hh_low_hold_fraction():
    rows = HH + [(4101, 4102, 4097.0, 4101.5)]
    ctx = mkctx(rows)
    p = pk(hh_low_hold=True, hh_low_frac=0.5)
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4080.0, levels=(4140.0,), n=6)
    pos["t1_done"] = True
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert pos["left"] == 3
    # no partial taken yet: the rule is off
    pos, tr, sd = mkpos(ctx, 1, 0, 4090.0, 4080.0, levels=(4140.0,), n=6)
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 5)
    assert not pos["me2"].get("hh_low")


# --- X3-marginal-lower-lows-warning (54) -----------------------------------------------------------------------------------------------------------

MARG = [(4000, 4001, 3999, 4000), (4000, 4010, 3999.5, 4009), (4009, 4010.5, 4008, 4009.5), (4009.5, 4011, 4009, 4010), (4010, 4011.2, 4009, 4010.5), (4010.5, 4014.2, 4010, 4014)]


def test_marginal_ext():
    ctx = mkctx(MARG)
    p = pk(marginal_ext_warn=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0, 4040.0), fracs=(0.5, 0.5))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 2)
    assert not pos["no_adds"]                                                              # one poke 0.5 over the high, back inside
    step2(ctx, sd, pos, tr, p, 3)
    assert pos["no_adds"] and "marginal_ext" in tr.mgmt_tags and pos["left"] == 10        # two pokes block the adds
    # with the exit switch they close the rest
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0, 4040.0), fracs=(0.5, 0.5))
    pe = pk(marginal_ext_warn=True, marginal_exit=True)
    fill2(ctx, sd, pos, tr, pe)
    step2(ctx, sd, pos, tr, pe, 1, 3)
    assert reasons(tr) == ["marginal"] and pos["left"] == 0
    # a 3-pt smash through the high does not count (bar 5 breaks 4011.2 by 3): no more pokes
    smash = [MARG[0], MARG[1], (4009, 4013.5, 4008, 4013), (4013, 4017.5, 4012, 4017), (4017, 4021, 4016, 4020.5)]
    ctx2 = mkctx(smash)
    pos, tr, sd = mkpos(ctx2, 1, 0, 4000.0, 3990.0, levels=(4030.0, 4040.0), fracs=(0.5, 0.5))
    fill2(ctx2, sd, pos, tr, pe)
    step2(ctx2, sd, pos, tr, pe, 1, 4)
    assert pos["left"] == 10 and not pos["no_adds"]


# --- X3-runner-stall-exits (55) --------------------------------------------------------------------------------------------------------------------

def test_stall_exits():
    # a long with 2 of 10 units left: the high (4020) is made on bar 1, bar 2 is the last down-close candle (body 4017.5 - 4019), then 10 quiet up-close bars without a new high
    rows = [(4000, 4001, 3999, 4000), (4000, 4020, 3999.5, 4019), (4019, 4019.2, 4017, 4017.5)] + [(4019.2, 4019.8, 4019.1, 4019.7)] * 10 + [(4019.5, 4019.6, 4018.9, 4019.0)]
    ctx = mkctx(rows)
    p = pk(stall_exits=True, stall_bars=10)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 2
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 12)
    assert pos["left"] == 2 and not tr.exits                                                # ten bars without a new high: the stall is on, no bar traded back into the body yet
    assert pos["me2"]["stall_on"]
    step2(ctx, sd, pos, tr, p, 13)                                                          # a bar trading back into the body of the last down-close candle (low 4018.9 <= its open 4019)
    assert reasons(tr) == ["stall_rebal"] and pos["left"] == 1 and tr.exits[0][2] == 1
    # the unit goes once only
    ctx2 = mkctx(rows + [(4019.0, 4019.3, 4018.5, 4018.8)])
    step2(ctx2, ctx2.sides_map[1], pos, tr, p, 14)
    assert reasons(tr) == ["stall_rebal"]
    # not before 75 % is closed
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 6
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 13)
    assert pos["left"] == 6


def test_stall_exits_reh():
    # relative equal highs 4015.0 / 4015.25 inside the range; a poke over them (4016) that closes back under (4014.5) closes the last unit
    rows = [(4000, 4001, 3999, 4000), (4000, 4020, 3999.5, 4019), (4013, 4013.2, 4012, 4012.5), (4012.5, 4015.0, 4012, 4013), (4013, 4013.5, 4012.2, 4013.2), (4013.2, 4015.25, 4012.6, 4013.6),
            (4013.6, 4014.0, 4012.8, 4013.4), (4013.4, 4016.0, 4013, 4014.5)]
    ctx = mkctx(rows)
    p = pk(stall_exits=True, stall_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 2
    fill2(ctx, sd, pos, tr, p)
    pos["me2"]["rebal_done"] = True
    step2(ctx, sd, pos, tr, p, 1, 6)
    assert pos["left"] == 2 and pos["me2"]["stall_on"]
    step2(ctx, sd, pos, tr, p, 7)
    assert reasons(tr) == ["stall_reh"] and pos["left"] == 0
    # not before 75 % is closed
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4030.0,), n=10)
    pos["left"] = 6
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 7)
    assert pos["left"] == 6


# --- X3-nfp-wick-ce-ladder-close-test (67) -------------------------------------------------------------------------------------------------------

def _wick_book(closes):
    rows = [(4096, 4097, 4095, 4096)]
    for c in closes:
        rows.append((c, c + 0.5, c - 0.5, c))
    return rows


@pytest.mark.parametrize("closes,fund", [((4100.5, 4099.5), True), ((4100.5, 4101.0, 4100.8), False), ((4099, 4098.5), False)])
def test_wick_ce_close_test(closes, fund):
    # 10 units: the W (4100) rung fill closes 1, BE + pad follows; a 5m close above W then a 5m close at or under it closes 3
    rows = _wick_book((4100.2,) + closes)
    ctx = mkctx(rows, tf=5)
    p = pk(wick_ce_close_test=True, be_pad_pts=0.5)
    pos, tr, sd = mkpos(ctx, 1, 0, 4096.0, 4090.0, levels=(4100.0, 4110.0, 4120.0), fracs=(0.5, 0.3, 0.2), kinds=["wick", "pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    assert pos["fracs"][0] == pytest.approx(0.1) and sum(pos["fracs"]) == pytest.approx(1.0)
    rung(ctx, sd, pos, tr, p, 0, 1)
    assert pos["left"] == 9 and pos["stop"] == pytest.approx(4096.5)                       # the 10 % rung and BE + pad
    step2(ctx, sd, pos, tr, p, 2, len(rows) - 1)
    assert ("fund" in reasons(tr)) == fund
    if fund:
        assert pos["left"] == 6 and tr.exits[-1][2] == 3


# --- L16-adr5-60-80-closed (68) ----------------------------------------------------------------------------------------------------------------------

def _hist5(rng=40.0):
    return [pd.DataFrame({"high": [4040.0], "low": [4040.0 - rng]}, index=pd.DatetimeIndex([pd.Timestamp(f"2026-06-{10 + k} 09:30", tz=NY)])) for k in range(5)]


def test_adr_closed_min():
    rows = [(4000, 4001, 4000, 4000.5)] + [(4000.5, 4010, 4000.2, 4009)] * 3
    t13 = [(4020, 4041, 4019, 4040)]
    ctx = mkctx(rows + t13, hist=_hist5())
    p = pk(adr_closed_min=0.7)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.5, 3990.0, levels=(4060.0,))
    pos["left"] = 7                                                                        # 30 % closed so far
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 3)
    assert pos["left"] == 7                                                                # before the projection (4000 + 40) is reached nothing happens
    step2(ctx, sd, pos, tr, p, 4)
    assert pos["left"] == 3 and reasons(tr) == ["adr_true_up"]                             # enough off to reach 70 % closed, once
    # already 80 % closed: nothing more
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.5, 3990.0, levels=(4060.0,))
    pos["left"] = 2
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 4)
    assert pos["left"] == 2 and not tr.exits


# --- M13-ote-leave-discount-fast (87) ----------------------------------------------------------------------------------------------------------------

def test_ote_leave():
    # the leg 4000 -> 4100: the OTE band is 4021 .. 4038 (62 % line 4038); an OTE fill followed by 3 bars still inside it cuts half
    inside = [(4030, 4036, 4028, 4034)] * 3
    ctx = mkctx([(4030, 4031, 4025, 4030)] + inside)
    p = pk(ote_leave_bars=3)
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4015.0, levels=(4100.0,), kind="ote", leg=(4000.0, 4100.0))
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"]["ote62"] == pytest.approx(4038.0)
    step2(ctx, sd, pos, tr, p, 1, 2)
    assert pos["left"] == 10
    step2(ctx, sd, pos, tr, p, 3)
    assert reasons(tr) == ["ote_slow"] and pos["left"] == 5
    # a close above the 62 % line on bar 2, then a pullback to the leg EQ (4050): nothing exits
    ok = [(4030, 4036, 4028, 4034), (4034, 4045, 4033, 4041), (4041, 4044, 4033, 4036), (4036, 4052, 4035, 4050.5), (4050.5, 4051, 4049, 4050)]
    ctx = mkctx([(4030, 4031, 4025, 4030)] + ok)
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4015.0, levels=(4100.0,), kind="ote", leg=(4000.0, 4100.0))
    fill2(ctx, sd, pos, tr, p)
    step2(ctx, sd, pos, tr, p, 1, 5)
    assert pos["left"] == 10 and not tr.exits
    # a non-OTE entry is not judged
    pos, tr, sd = mkpos(ctx, 1, 0, 4030.0, 4015.0, levels=(4100.0,), kind="fvg", leg=(4000.0, 4100.0))
    fill2(ctx, sd, pos, tr, p)
    assert pos["me2"].get("ote62") is None


# --- new-no-down-close-urgency (108) -------------------------------------------------------------------------------------------------------------

def test_urgency_runner():
    up = [(4000, 4001, 3999, 4000.5), (4000.5, 4004, 4000, 4003), (4003, 4007, 4002.5, 4006), (4006, 4012, 4005.5, 4011)]
    ctx = mkctx(up)
    p = pk(urgency_runner=True)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4030.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 3)                                                       # an all up-close leg to T1: the stop 1 pt under the close; the ladder is otherwise unchanged (no bulk exit)
    assert pos["left"] == 5 and reasons(tr) == ["t1"] and pos["stop"] == pytest.approx(4010.0)
    assert "urgency" in tr.mgmt_tags
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4030.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    pb = pk(urgency_runner=True, urgency_bulk=True)                                       # the explicit alternative: the T1 bulk exit, a 20 % runner
    fill2(ctx, sd, pos, tr, pb)
    rung(ctx, sd, pos, tr, pb, 0, 3)
    assert pos["left"] == 2 and reasons(tr) == ["t1", "urgency_bulk"]
    # three rungs: the rung between T1 and the last shrinks so the LAST rung keeps runner_frac (0.2 of 10 = 2 units)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4020.0, 4030.0), fracs=(0.4, 0.4, 0.2), kinds=["pool", "pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 3)
    assert pos["left"] == 6 and pos["fracs"][1] == pytest.approx(0.4) and reasons(tr) == ["t1"]     # 6 left - 2 runner = 4 for the middle rung = 0.4 of 10
    # one down-close bar in the leg: the ladder is unchanged
    dn = [(4000, 4001, 3999, 4000.5), (4000.5, 4004, 4000, 4003), (4003, 4004, 4000.5, 4001), (4001, 4012, 4000.8, 4011)]
    ctx = mkctx(dn)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4030.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    fill2(ctx, sd, pos, tr, p)
    rung(ctx, sd, pos, tr, p, 0, 3)
    assert pos["left"] == 5 and pos["stop"] == 3990.0 and reasons(tr) == ["t1"]
    # runner_frac sets the runner share
    ctx = mkctx(up)
    pos, tr, sd = mkpos(ctx, 1, 0, 4000.0, 3990.0, levels=(4010.0, 4030.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    pr = pk(urgency_runner=True, urgency_bulk=True, runner_frac=0.3, urgency_stop_pts=2.0)
    fill2(ctx, sd, pos, tr, pr)
    rung(ctx, sd, pos, tr, pr, 0, 3)
    assert pos["left"] == 3 and pos["stop"] == pytest.approx(4009.0)
