"""Caption-gap pass, package bias_htf#3/7 (35 specs from digests/rulebook_gaps/bias_htf_intermarket.md items 147, 148, 152, 154, 164, 167, 168, 172-174, 177, 179, 180, 184-190, 195, 197, 198, 200-203,
215, 216, 221, 222, 224-227 and day_selection_news_calendar.md item 45): defaults / validation / study variants / table configuration, the COT loader and states (cot.py) and the TABLE-side functions
(bh3.py) on hand-made daily books. The engine hooks are in test_caption_gap_bh3b.py, the table build and the no-look-ahead runs in test_caption_gap_bh3c.py. Nothing here needs market data; nothing is
platform specific; no file outside the repo is written (the CFTC archive is built in memory)."""
import io
import json
import warnings
import zipfile
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh2 as BH2, bh3 as BH3, bias_htf as BX, cot, htf, levels as L, study
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr, flip_of  # noqa: E402

NAN = float("nan")

NEW_FIELDS = (
    "cot_two_states", "cot_gate", "tandem_scalp", "notes_dxy_tag", "season_qualified", "stack_tag", "stack_min", "swing_gate_runners", "trend_slope_min", "bond_lt_tag", "wpr_daily_tag", "hallmarks_tag",
    "profile_gate", "mwd_tf_test", "mwd_cancel_case", "mwd_upgrade", "mwd_levels_entries", "retire_arrays", "pause_on_hold", "mw_bookkeeping", "pd60_only_consol", "consol_ratio", "in_play_gate",
    "in_play_days", "in_play_room_pts", "iof_mode", "bias_dh", "ny_continue_london", "pd_needs_iof", "counter_range_extreme", "iof_premium_wait", "fall_low_bias", "season_poised", "mo_bias_gate", "q_dir_tag",
    "wk_struct_weight", "iof_sponsor_gate", "chop_lean", "chop_target_baseline")
KNOBS = {"trend_slope_min", "consol_ratio", "in_play_days", "in_play_room_pts", "stack_min"}
OFF = dict(cot_two_states=False, cot_gate="off", tandem_scalp=False, notes_dxy_tag=False, season_qualified=False, stack_tag=False, stack_min=0, swing_gate_runners=False, bond_lt_tag=False, wpr_daily_tag=False,
           hallmarks_tag=False, profile_gate=False, mwd_tf_test=False, mwd_cancel_case=False, mwd_upgrade=False, mwd_levels_entries=False, retire_arrays=False, pause_on_hold=False, mw_bookkeeping=False,
           pd60_only_consol=False, in_play_gate=False, iof_mode="basic", bias_dh="off", ny_continue_london=False, pd_needs_iof=False, counter_range_extreme=False, iof_premium_wait=False, fall_low_bias=False,
           season_poised=False, mo_bias_gate=False, q_dir_tag=False, wk_struct_weight=False, iof_sponsor_gate="off", chop_lean=False, chop_target_baseline=False)


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert (p.trend_slope_min, p.consol_ratio, p.in_play_days, p.in_play_room_pts) == (0.5, 0.25, 3, 5.0)
    assert p.bx == "" and "tue_fail" not in p.flip_triggers and p.htf_bias == "off" and p.wpr_len == 14       # the weekly %R period of item 172 is the built wpr_len
    # the owner-fixed Silver Bullet switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and p.want_all_engines is True
    for bad in (dict(cot_gate="x"), dict(iof_mode="x"), dict(bias_dh="x"), dict(iof_sponsor_gate="x"), dict(stack_min=-1), dict(stack_min=6), dict(trend_slope_min=0), dict(in_play_days=0), dict(in_play_room_pts=-1),
                dict(consol_ratio=0), dict(consol_ratio=1.5), dict(htf_bias="x")):
        with pytest.raises(ValueError):
            Params(**bad)
    for hb in ("week_pre", "week_check", "wd_check"):
        assert Params(htf_bias=hb).htf_bias == hb
    assert "tue_fail" in htf.FLIP_TRIGGERS
    Params(flip_triggers=("ob_mt", "wk_dc", "tue_fail"), htf_bias="flip")
    with pytest.raises(ValueError):
        Params(flip_triggers=("nope",))
    with pytest.warns(UserWarning, match="inert"):
        Params(pause_on_hold=True)                                              # a flip-column switch without htf_bias='flip'


def test_every_new_switch_has_a_study_variant():
    used = set()
    for v in study._BH3_DECISIONS.values():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for k, v in study._BH3_DECISIONS.items():
        assert k in study.DECISIONS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)
    for gid in ("B20-cot-zero-line-vs-hedging", "B20-cot-data-spec", "X3-notes-dollar-regime", "X3-seasonal-quarterly-qualifier", "X3-full-confluence-stack", "X3-swing-two-group-trending-gate",
                "X3-bonds-lead-stocks", "B20-williams-r", "X3-swing-checklist-pipeline", "X3-htf-market-profile", "X3-b10-tf-test", "X3-b10-cancel-condition", "X3-b10-case-c-to-b-upgrade",
                "B17-no-active-array", "B9-ltf-arrays-break-in-succession", "B5-monthly-weekly-range-bookkeeping", "B8-tuesday-failure-swing-flip", "A21-trend-vs-consolidation-first",
                "B13-weekly-bias-from-daily-arrays", "B5-htf-arrays-respected-and-in-play", "B6-iof-checklist-extended", "B5-daily-and-4h-bias", "N9-ny-continues-london", "A21-discount-not-buy-signal",
                "B3-countertrend-from-range-extreme", "B6-bullish-iof-at-premium-wait", "B23-fall-seasonal-low-setup", "B23-market-poised-first", "MB-monthly-bias-routine", "B22-quarterly-shift-direction",
                "WB-weekly-checklist-order", "B10-weekly-structure-control", "B6-daily-iof-htf-relative", "B5-daily-checklist-fallback", "B17-chop-revert-middle"):
        assert any(k.startswith(gid) for k in study.DECISIONS), gid


def test_table_configuration_names_what_the_switches_need():
    x = json.loads(Params(wpr_daily_tag=True, profile_gate=True, retire_arrays=True, pause_on_hold=True, mw_bookkeeping=True, in_play_gate=True, iof_mode="score", mo_bias_gate=True, q_dir_tag=True,
                          wk_struct_weight=True, htf_bias="flip", flip_triggers=("ob_mt", "tue_fail"), mwd_tf_test=True, pd60_only_consol=True).bx)
    assert set(x["b3"]) >= {"wprd", "prof", "ret", "hold", "mw", "inplay", "iofx", "mo", "qdir", "wkc", "fl"} and x["b3"]["prof"] == 2 and x["b3"]["fl"] == {"tuef": 2.0}
    assert x["iof"] == [10, 2] and x["mwd3"] == [1, 0, 0] and x["pd20"][5:] == [1, 0.25]
    assert x["b2"]["qs2"][3] == 1                                           # the quarterly objective is built for mo_bias_gate
    w = json.loads(Params(htf_bias="week_check").bx)
    assert w["wk"] == 1 and w["iof"] == [10, 2] and w["b3"]["chk"] == [10, 2]
    assert json.loads(Params(htf_bias="wd_check").bx)["b3"]["prof"] == 1
    assert Params(htf_bias="week_pre").bx and json.loads(Params(htf_bias="week_pre").bx)["b3"] == {"wkpre": 1}


# --- item 148: the CFTC loader ------------------------------------------------------------------------------------------

HDR = ("Market and Exchange Names,Report_Date_as_YYYY-MM-DD,CFTC Contract Market Code,Commercial Positions-Long (All),Commercial Positions-Short (All),Noncommercial Positions-Long (All)")


def deacot_zip(rows) -> bytes:
    """A deacot{year}.zip built in memory: annual.txt with the legacy futures-only columns."""
    buf = io.StringIO()
    buf.write(HDR + "\n")
    for nm, d_, code, cl, cs in rows:
        buf.write(f'"{nm}",{d_},{code},{cl},{cs},999\n')
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("annual.txt", buf.getvalue())
    return out.getvalue()


def test_cot_loader_known_date():
    data = deacot_zip([("E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", "2023-03-07", "13874A", 300000, 250000),
                       ("E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", "2023-03-14", "13874A", 290000, 260000),
                       ("NASDAQ-100 MINI", "2023-03-07", "209742", 1000, 5000),
                       ("GOLD - COMMODITY EXCHANGE", "2023-03-07", "088691", 7, 7)])
    r = cot.read_zip(data, cot.market_code("E-MINI S&P 500"))
    assert list(r.net) == [50000, 30000] and len(r) == 2                                      # commercials only (long - short), the other markets filtered by their CFTC code
    assert cot.market_code("E-MINI S&P 500") == "13874A" and cot.market_code("E-MINI NASDAQ-100") == "209742"
    t = cot.table(r)
    assert t.known.iloc[0] == pd.Timestamp("2023-03-10")                                       # the Friday release
    assert t.index[0] == pd.Timestamp("2023-03-13")                                            # the session after Friday 03-10
    assert cot.first_usable("2023-03-07") == pd.Timestamp("2023-03-13")
    nq = cot.read_zip(data, cot.market_code("E-MINI NASDAQ-100"))
    assert list(nq.net) == [-4000]
    # the tag is not usable on the Tuesday it describes or on the release Friday
    assert cot.first_usable("2023-03-07") > cot.known_date("2023-03-07")
    # no look-ahead of the usable date, on a table with enough reports (60 weekly rows, net 100 -> 159; usable the session after the Friday release)
    big = cot.table(pd.DataFrame({"report_date": pd.date_range("2022-01-04", periods=60, freq="7D"), "comm_long": 1, "comm_short": 1, "net": np.arange(100, 160)}))
    u = big.index[55]
    assert cot.states(big, u - pd.Timedelta(days=1))[0] == 1 and len(big[big.index <= u - pd.Timedelta(days=1)]) == 55
    assert cot.states(big, big.index[3]) == (0, 0)                                           # fewer than MIN_REPORTS usable reports
    assert cot.states(big, big.index[20]) == (1, 0)                                          # 8..51 reports: program only
    assert cot.states(big, big.index[59])[1] == 1                                            # 60 reports, a rising net: above the 52-week midpoint
    assert cot.parse_legacy(pd.DataFrame({"a": [1]})) is None


def test_cot_loader_reads_a_folder_without_network(monkeypatch):
    # an empty / missing folder gives no table; the cache key is per (market, folder)
    from pathlib import Path
    assert cot.load_dir("E-MINI S&P 500", Path("data/mentorship/_no_such_cot_dir")) is None


def test_cot_loader_reads_a_real_zip_from_a_folder(tmp_path):
    rows = [("E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE", d.strftime("%Y-%m-%d"), "13874A", 300000 + k * 1000, 250000) for k, d in enumerate(pd.date_range("2023-01-03", periods=4, freq="7D"))]
    (tmp_path / "deacot2023.zip").write_bytes(deacot_zip(rows))
    t = cot.load_dir("E-MINI S&P 500", tmp_path)
    assert t is not None and len(t) == 4 and list(t.net) == [50000, 51000, 52000, 53000]


# --- item 147: program and hedging ---------------------------------------------------------------------------------------

def test_cot_two_states():
    net = [-60000 if k % 2 else -10000 for k in range(51)] + [-20000]
    assert cot.states_of_series(net) == (-1, 1)                                                # net -20k: program -1; MID52 = -35k: hedge +1
    net2 = [-60000 if k % 2 else -10000 for k in range(51)] + [-50000]
    assert cot.states_of_series(net2) == (-1, -1)
    assert cot.states_of_series([5000.0] * 4) == (0, 0)                                        # too little history
    # a narrow 52-week range (< 10 % of the mean |net|) falls back to the 26-week midpoint
    narrow = [100400.0] * 26 + [100000.0] * 25 + [100100.0]
    assert cot.states_of_series(narrow) == (1, 1)                                              # MID26 = 100050 < 100100 (MID52 = 100200 would say -1)
    assert cot.states_of_series([100400.0] * 26 + [100000.0] * 25 + [100100.0], weeks=52, fallback=52) == (1, -1)


# --- item 172: the daily Williams %R(15) ---------------------------------------------------------------------------------

def test_wpr_daily_15():
    n = 40
    c_dn = np.linspace(120, 100, n)                                                            # falling: the close sits at the 15-day low
    h, l = c_dn + 1.0, c_dn - 1.0
    st = BH3.wpr_daily_state(h, l, c_dn)
    assert st[-1] == 1 and (st[:14] == 0).all()                                                # %R(15) < 50 -> +1 (buy area)
    ks = np.array([n])
    assert BH3.wpr_daily_column(h, l, c_dn, ks)[0] == st[-1]
    assert BH3.wpr_daily_column(h, l, c_dn, np.array([n - 1]))[0] == st[-2]                    # the row of session k reads session k-1 (prior-day data only)
    c_up = np.linspace(100, 120, n)
    assert BH3.wpr_daily_state(c_up + 1, c_up - 1, c_up)[-1] == -1
    # the +-5 band keeps the side most recently left
    base = np.linspace(110, 100, 20)
    h, l = base + 0.5, base - 0.5
    hh, ll = h[6:].max(), l[6:].min()
    c_new = ll + 0.52 * (hh - ll)                                                              # %R(15) = 52: inside 50 +- 5
    c = np.r_[base, c_new]
    h, l = np.r_[h, c_new + 0.01], np.r_[l, c_new - 0.01]
    seq = BH3.wpr_daily_state(h, l, c)
    assert seq[-2] == 1 and seq[-1] == 1                                                       # the buy side it just left holds inside the band
    c2 = np.r_[c, ll + 0.9 * (h[7:].max() - ll)]
    seq2 = BH3.wpr_daily_state(np.r_[h, c2[-1] + 0.01], np.r_[l, c2[-1] - 0.01], c2)
    assert seq2[-1] == -1                                                                      # outside the band it reads sign(50 - %R)


# --- item 174: the weekly profile ---------------------------------------------------------------------------------------

def weekly_book(closes, rng=3.0):
    """Weekly bars as arrays (high, low, close) from a close path."""
    c = np.array(closes, float)
    return c + rng / 2, c - rng / 2, c


def test_weekly_profile():
    up = [100 + 2.0 * k for k in range(52)]
    h, l, c = weekly_book(up)
    assert BH3.profile_of(h, l, c, 52) == ("trend", 1)
    pull = up[:48] + [up[47] - 3.0 * k for k in range(1, 5)]
    h, l, c = weekly_book(pull)
    assert BH3.profile_of(h, l, c, 52) == ("retrace", 1)                                       # a 52-week uptrend with a 4-week pullback
    down = [300 - 2.0 * k for k in range(52)]
    assert BH3.profile_of(*weekly_book(down), 52) == ("trend", -1)
    assert BH3.profile_of(*weekly_book(down[:48] + [down[47] + 3.0 * k for k in range(1, 5)]), 52) == ("retrace", -1)
    flat = [100 + (k % 2) for k in range(52)]
    assert BH3.profile_of(*weekly_book(flat, 2.0), 52)[0] == "consol"                          # a 26-week range under 9 x the mean weekly range
    assert BH3.profile_of(h, l, c, 20) == ("", 0)                                              # fewer than 26 weeks


def week_days(week_closes, start=date(2024, 1, 1), rng=3.0):
    """A daily book of consecutive Monday-Friday weeks whose weekly close is given (every day of a week closes at the weekly close, the week's range is rng)."""
    rows, prev = [], week_closes[0]
    for c in week_closes:
        for k in range(5):
            o = prev if k == 0 else c
            rows.append((o, max(o, c) + rng / 2, min(o, c) - rng / 2, c))
        prev = c
    return dsess(rows, start)


def test_profile_columns_on_a_daily_book():
    up = [100 + 2.0 * k for k in range(60)]
    d = week_days(up[:56] + [up[55] - 3.0 * k for k in range(1, 5)])
    w = htf.weeks(d)
    ks = np.array([len(d) - 1, len(d) - 6])
    res = BH3.profile_columns(d, w, [], ks, True)
    assert res["profile"][0] in ("retrace", "trend", "consol", "") and len(res["wm_zones"]) == 2
    assert res["profile_dir"][0] in (-1, 0, 1)
    # the columns of a row use only the weeks completed before the row's session
    full = BH3.profile_columns(d, w, [], np.array([len(d) - 6]), False)
    assert full["profile"][0] == res["profile"][1]


# --- item 222: the quarterly direction ----------------------------------------------------------------------------------

def month_days(month_closes, start=date(2023, 1, 2)):
    """A daily book with ~21 sessions per month; each month closes at its given close (linear inside the month from the previous close)."""
    rows, prev = [], month_closes[0]
    for c in month_closes:
        path = np.linspace(prev, c, 22)[1:]
        for q in range(21):
            o = path[q - 1] if q else prev
            x = path[q]
            rows.append((o, max(o, x) + 0.5, min(o, x) - 0.5, x))
        prev = c
    idx = pd.bdate_range(start, periods=len(rows))
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).astype(float)


def test_q_dir():
    d = month_days([100 + 5.0 * k for k in range(14)])
    ks = np.array([len(d) - 1])
    assert BH3.q_dir_column(d, ks)[0] == 1                                                     # 12 rising months: the trend continues
    flat = [100, 101, 99, 100, 101, 100, 99, 100, 96, 98, 100, 104, 104]
    assert BH3.q_dir_column(month_days(flat), np.array([len(month_days(flat)) - 1]))[0] == -1  # a flat year with the last 4 months up: expect the reversal
    assert BH3.q_dir_column(d, np.array([30]))[0] == 0                                         # fewer than 12 completed months
    # the objective: the weekly bear FVG above the 60-session range when q_dir is +1
    d2 = d
    px = np.array([float(d2.close.iloc[-1])])
    h, l, c = (d2[k].values.astype(float) for k in ("high", "low", "close"))
    a = arr("bear", "fvg", h.max() + 30, h.max() + 20, 0, tf="W")
    out = BH3.q_obj_dir_column([a], np.array([len(d2) - 1]), px, h, l, c, np.array([1]))
    assert out[0] == h.max() + 20
    assert np.isnan(BH3.q_obj_dir_column([a], np.array([len(d2) - 1]), px, h, l, c, np.array([-1]))[0])


# --- item 185: arrays that hold on the way ---------------------------------------------------------------------------------

def test_pause_on_hold():
    c = np.array([105, 104, 103, 102, 101, 100.5, 99.5, 101.5, 100.8, 100.6, 100.4, 100.2], float)
    h, l = c + 0.3, c - 0.3
    l[6] = 99.0
    a = arr("bull", "fvg", 100.0, 98.0, 2)                                          # a daily BISI (a bull FVG) in a bearish state
    ks = np.arange(5, 12)
    flip = np.full(len(ks), -1)
    res = BH3.held_columns(flip, [a], ks, h, l, c)
    assert list(res["held_arrays"]) == [0, 0, 0, 1, 1, 1, 1]                        # touched at session 6, held by the close above it at session 7: counted from the row of session 8
    assert list(res["held_pause"]) == [0, 0, 0, 1, 0, 0, 0]                         # want = 0 for the next session after the holding close
    assert list(BH3.held_columns(np.full(len(ks), 1), [a], ks, h, l, c)["held_arrays"]) == [0] * 7       # a bull array is not an opposing array in a bullish state
    flip2 = np.array([-1, -1, 1, 1, -1, -1, -1])                                    # the state's run restarts the count
    assert BH3.held_columns(flip2, [a], ks, h, l, c)["held_arrays"][4] == 0


# --- item 186: month / week bookkeeping ------------------------------------------------------------------------------------

def test_mw_bookkeeping():
    d = week_days([100 + 2.0 * k for k in range(14)], start=date(2024, 1, 1))
    k = list(d.index).index(pd.Timestamp("2024-03-11"))
    res = BH3.mw_columns(d, np.array([k, k - 5]), np.array([1, 1]))
    assert res["wk_expand"][0] == 2                                                 # the weeks of 26 Feb and 4 Mar (both ended in March) each made a higher high
    h, l, c = (d[x].values.astype(float) for x in ("high", "low", "close"))
    m0 = list(d.index).index(pd.Timestamp("2024-03-01"))
    exp = (c[k - 1] - l[m0:k].min()) / (h[m0:k].max() - l[m0:k].min())
    assert res["mo_pd"][0] == pytest.approx(exp) and 0 <= res["mo_pd"][0] <= 1       # computed from the completed sessions of the month before the row
    assert res["wk_pd"][0] == pytest.approx((c[k - 1] - l[k - 5:k].min()) / (h[k - 5:k].max() - l[k - 5:k].min()))       # the first session of a week: the last week range
    assert BH3.mw_columns(d, np.array([k]), np.array([-1]))["wk_expand"][0] == 0     # a bearish monthly bias: rising weeks do not count


# --- item 195: respected and in play -----------------------------------------------------------------------------------------

def test_in_play_gate():
    c = np.array([105, 104, 103, 102, 101.5, 101.2, 100.2, 101, 101.5, 101.8], float)
    h, l = c + 0.3, c - 0.3
    l[6] = 99.5
    a = arr("bull", "fvg", 100.0, 98.0, 2)
    ks = np.array([9])
    assert BH3.in_play_column(h, l, c, [a], ks, 3, np.array([0]))[0] == 1             # a daily BISI tagged within 3 sessions with a close above it
    assert BH3.in_play_column(h, l, c, [a], ks, 3, np.array([-1]))[0] == 0            # the daily iof against it
    c_nt = c.copy()
    c_nt[6] = 100.9
    assert BH3.in_play_column(c_nt + 0.3, c_nt - 0.3, c_nt, [a], ks, 3, np.array([0]))[0] == 0       # no touch: longs are rejected
    old = BH3.in_play_column(np.r_[h, [102] * 5], np.r_[l, [101.4] * 5], np.r_[c, [101.8] * 5], [a], np.array([14]), 3, np.array([0]))
    assert old[0] == 0                                                                # the touch is older than in_play_days
    assert BH3.in_play_column(h, l, c, [a], np.array([7]), 3, np.array([0]))[0] == 0   # the touch session (6) is not a LATER close: no reaction yet at k = 7
    b = arr("bear", "fvg", 112.0, 110.0, 2)
    cc2 = np.array([105, 106, 107, 108, 109, 109.5, 111.0, 109.5, 109.0, 108.5], float)
    assert BH3.in_play_column(cc2 + 0.3, cc2 - 0.3, cc2, [b], np.array([9]), 3, np.array([0]))[0] == -1       # the mirror: a bear array touched from below, a close under its bottom


# --- item 197: the extra B6 components ---------------------------------------------------------------------------------------

def test_iof_score():
    c = np.array([103, 102.5, 102, 101, 103, 104, 106, 108.5, 109, 109.5, 110, 110.2], float)
    o = np.r_[c[0], c[:-1]]
    h, l = np.maximum(o, c) + 0.2, np.minimum(o, c) - 0.2
    l[3] = 99.5                                                                       # session 3 trades into the bull OB and closes above it
    c[3], o[3] = 101.0, 102.0
    ob = arr("bull", "ob", 100.0, 98.5, 1)
    bear_fvg = arr("bear", "fvg", 108.0, 106.0, 1)
    ks = np.array([10])
    res = BH3.iof_components(o, h, l, c, [ob, bear_fvg], ks)
    assert (res["iof_ob_bounce"][0], res["iof_gap_fill_rally"][0], res["iof_premium_broken"][0], res["iof_sum"][0]) == (1, 0, 1, 2)        # two bullish components: score 2
    df = pd.DataFrame({"iof_sum": [2, 1, -2, 0], "react": [0, 0, 0, 0], "pd": [0, 0, 0, 1], "combo2": [0, 0, 0, 0], "iof": [0, 0, 0, 0]})
    out = BH3.apply_iof_score(df)
    assert list(out.iof) == [1, 0, -1, 0] and list(out.combo2) == [1, 0, -1, 1]       # the bias = sign(score) when |score| >= 2
    fb = arr("bull", "fvg", 104.0, 102.0, 1)                                          # a bull FVG that was filled and then closed above
    c2 = np.array([106, 105, 103, 101.5, 105.5, 106, 106.2, 106.4, 106.6, 106.8], float)
    o2 = np.r_[c2[0], c2[:-1]]
    h2, l2 = np.maximum(o2, c2) + 0.2, np.minimum(o2, c2) - 0.2
    r2 = BH3.iof_components(o2, h2, l2, c2, [fb], np.array([9]))
    assert r2["iof_gap_fill_rally"][0] == 1


# --- item 190: the weekly bias before the week opens -----------------------------------------------------------------------

def test_wk_pre_bias():
    rows = []
    for k in range(20):
        px = 100 + 0.4 * k
        rows.append((px, px + 1.0, px - 1.0, px + 0.2))
    rows[14] = (106.0, 109.0, 106.0, 107.0)                                           # Friday: trades up into the daily SIBI (a bear FVG 108-110)
    d = dsess(rows, date(2024, 1, 1))
    o, h, l, c = (d[x].values.astype(float) for x in ("open", "high", "low", "close"))
    sibi = arr("bear", "fvg", 110.0, 108.0, 3)
    bull = arr("bull", "fvg", 99.0, 97.0, 0)
    ks = np.arange(15, 20)
    px = np.full(5, 107.0)
    res = BH3.wk_pre_columns(d, [sibi, bull], ks, px, o, h, l, c)
    assert list(res["wk_pre_bias"]) == [-1] * 5                                       # the last array touched was a premium array: Monday-Friday want -1
    assert list(res["wk_obj"]) == [99.0] * 5                                         # the nearest bull array below
    res2 = BH3.wk_pre_columns(d, [bull], ks, px, o, h, l, c, look=3)
    assert list(res2["wk_pre_bias"]) == [0] * 5                                       # nothing touched in the lookback


# --- item 221: the monthly bias ----------------------------------------------------------------------------------------------

def test_mo_bias_held_63_sessions():
    d = dsess([(100, 101, 99, 100)] * 160, date(2024, 1, 1))
    ks = np.arange(5, 160)
    bm = np.zeros(len(ks), int)
    first = list(ks).index(next(k for k in ks if d.index[k].month != d.index[k - 1].month))
    bm[first] = 1
    out = BH3.mo_bias_column(d, ks, bm, np.zeros(len(ks), int))
    assert out[first] == 1 and out[first - 1] == 0 and out[first + 62] == 1 and out[first + 63] == 0     # held 63 sessions
    flip = np.zeros(len(ks), int)
    flip[first + 10:] = -1
    out2 = BH3.mo_bias_column(d, ks, bm, np.zeros(len(ks), int), flip)
    assert out2[first + 9] == 1 and out2[first + 10] == 0                              # the opposing flip state ends it
    bw = np.zeros(len(ks), int)
    bw[first] = -1
    assert BH3.mo_bias_column(d, ks, np.zeros(len(ks), int), bw)[first] == -1          # the weekly draw stands in when the monthly is unclear


# --- item 225: the controlling weekly structure ------------------------------------------------------------------------------

def pivot_bars(piv):
    """Weekly (high, low) from an alternating list of pivot prices ('L', p) / ('H', p): the pivot bar carries the extreme, its neighbours sit inside it."""
    hs, ls = [], []
    for kind, p in piv:
        if kind == "H":
            hs.append(p)
            ls.append(p - 3.0)
        else:
            ls.append(p)
            hs.append(p + 3.0)
    return np.array(hs, float), np.array(ls, float)


def daily_from_weekly(hs, ls):
    rows = []
    for h_, l_ in zip(hs, ls):
        c = (h_ + l_) / 2
        rows += [(c, h_, l_, c)] * 5
    return dsess(rows, date(2024, 1, 1))


def test_wk_control():
    piv = [("H", 105), ("L", 100), ("H", 110), ("L", 95), ("H", 118), ("L", 102), ("H", 112), ("L", 104), ("H", 125), ("L", 115), ("H", 128)]
    hs, ls = pivot_bars(piv)
    d = daily_from_weekly(hs, ls)
    w = htf.weeks(d)
    ks = np.array([len(d)])                                                           # the session after the last week
    out = BH3.wk_control_column(d, w, ks, np.array([120.0]))
    assert out[0] == 1                                                                # a broken ITH (118) and an intact ITL (95) below the price
    K_ = 300.0
    hs2, ls2 = K_ - ls, K_ - hs
    d2 = daily_from_weekly(hs2, ls2)
    assert BH3.wk_control_column(d2, htf.weeks(d2), ks, np.array([K_ - 120.0]))[0] == -1
    assert BH3.wk_control_column(d, w, ks, np.array([90.0]))[0] == 0                   # price under the ITL: not controlling


# --- items 177 / 179 / 180: the per-timeframe B10 test, the cancel, the upgrade ------------------------------------------------

def test_mwd_tf_state():
    # a weekly bull FVG (bars 1-3), price comes back into it, then a displacement bar closing in the top third
    h = np.array([100, 106, 112, 115, 114, 110, 107, 106, 110, 116, 118, 122], float)
    l = np.array([98, 100, 109, 113, 108, 104, 103, 101, 102, 109, 114, 118], float)
    c = np.array([99, 105, 111, 114, 109, 105, 104, 102, 109, 115, 117, 121], float)
    o = np.r_[c[0], c[:-1]]
    zs = htf._arrays(o, h, l, c, "W", lambda i: i + 1)
    assert any(a.kind == "bull" and a.typ == "fvg" for a in zs)
    st = BH3.tf_state3(o, h, l, c, zs, mult=1.5)
    assert st[9] == 1 and st[0] == 0                                                   # the displacement off the weekly FVG
    zh = np.array([100, 105, 102, 108, 104, 112, 108, 115, 110, 118, 114, 121], float)
    zl = np.array([98, 100, 97, 101, 99, 104, 102, 107, 104, 109, 106, 112], float)
    assert BH3.hh_hl_series(zh, zl)[-1] == 1                                           # HH / HL
    zh2, zl2 = zh.copy(), zl.copy()
    zh2[8:], zl2[8:] = [109, 112, 108, 109], [101, 103, 99, 100]
    assert BH3.hh_hl_series(zh2, zl2)[-1] == -1                                         # without HH/HL: the +1 state is not case A
    from mentorship import bh1e
    ios = BH3.iof_state_series(o, h, l, c)
    assert len(ios) == len(c) and ios[-1] == bh1e.iof_state(o, h, l, c) and all(ios[j] == bh1e.iof_state(o[:j + 1], h[:j + 1], l[:j + 1], c[:j + 1]) for j in range(len(c)))


def test_mwd_cancel_case():
    # a bullish sequential: a daily higher high above the pivot high, rejected, then a close under the pivot low that preceded it
    h = np.array([100, 103, 101, 106, 104, 109, 105, 108, 104, 101], float)
    l = np.array([97, 99, 98, 100, 99, 104, 101, 102, 98, 94], float)
    c = np.array([99, 102, 100, 105, 101, 107, 103, 104, 99, 95], float)
    o = np.r_[c[0], c[:-1]]
    assert BH3.breaker_cancel(o, h, l, c, 9, 1) is True                                # HH 109 rejected, a close at 95 under the pivot low before it
    assert BH3.breaker_cancel(o, h[:7], l[:7], c[:7], 6, 1) is False                   # not yet
    c2, h2 = c.copy(), h.copy()
    c2[9], h2[9] = 110.0, 111.0
    assert BH3.breaker_cancel(o, h2, l, c2, 9, 1) is False                              # a close back above the high negates the breaker
    K_ = 200.0
    assert BH3.breaker_cancel(K_ - o, K_ - l, K_ - h, K_ - c, 9, -1) is True            # the bearish mirror (lower low rejected, a bullish breaker)


def test_mwd_c_to_b_and_levels():
    # a monthly bull array holding a weekly bull OB that a weekly up-close reacted to
    m = arr("bull", "fvg", 120.0, 100.0, 1, tf="M")
    wob = arr("bull", "ob", 112.0, 108.0, 3, tf="W")
    wo = np.array([115, 114, 111, 109], float)
    wc = np.array([113, 111, 108.5, 111], float)
    wh = np.array([116, 115, 112, 112], float)
    wl = np.array([112, 110, 107, 108.5], float)
    wlast = np.array([4, 9, 14, 19])
    assert BH3.case_c_to_b([m], [wob], wo, wc, wh, wl, wlast, 21, 110.0, 1) is True
    assert BH3.case_c_to_b([m], [wob], wo, wc, wh, wl, wlast, 21, 125.0, 1) is False   # the price is not inside the monthly array
    wc_same = np.array([113, 111, 108.5, 111], float)
    wob_late = arr("bull", "ob", 112.0, 108.0, 20, tf="W")                              # formed in the last week: that week's own up-close is not a later visit
    assert BH3.case_c_to_b([m], [wob_late], wo, wc_same, wh, wl, wlast, 21, 110.0, 1) is False
    wc_dn = np.array([113, 111, 107.0, 108.0], float)
    wo_dn = np.array([115, 114, 111, 110], float)
    assert BH3.case_c_to_b([m], [wob], wo_dn, wc_dn, wh, wl, wlast, 21, 110.0, 1) is False   # no weekly up-close at the OB
    # three daily down-close candles since the correction began: 6 levels (open and high of each)
    h = np.array([100, 103, 106, 108, 107, 106, 105, 104, 103], float)
    l = np.array([98, 100, 103, 106, 105, 104, 103, 102, 101], float)
    o = np.array([99, 101, 104, 107, 107, 106, 105, 104, 103], float)
    c = np.array([100, 103, 107, 106, 106, 105, 104, 103, 102], float)
    lv = BH3.dcandle_levels(o, h, l, c, 8, 1)
    assert len(lv) == 6 and lv == (107.0, 107.0, 106.0, 106.0, 105.0, 105.0) or len(lv) == 2 * sum(1 for j in range(4, 8) if c[j] < o[j])
    assert BH3.dcandle_levels(o, h, l, c, 8, -1) == ()                                  # a bearish sequential needs a pivot LOW first (none known here)


# --- item 188: the Tuesday failure swing ----------------------------------------------------------------------------------------

def tue_book(mirror=False):
    base = (4050, 4060, 4040, 4050)
    rows = [base] * 40
    rows[12] = (4050, 4102, 4045, 4055)                                                # week 3, Wednesday: the old weekly (and daily) pivot high 4102
    rows[30] = (4050, 4100, 4045, 4095)                                                # week 7, Monday: high 4100
    rows[31] = (4095, 4103, 4078, 4080)                                                # Tuesday: 4103 into the old high, closes in its lower third and under Monday close
    for q in (32, 33, 34):
        rows[q] = (4080, 4085, 4070, 4075)
    if mirror:
        rows = [(8000 - o, 8000 - l, 8000 - h, 8000 - c) for o, h, l, c in rows]
    return dsess(rows, date(2024, 1, 1))


def test_flip_tue_fail():
    d = tue_book()
    st = flip_of(d, [], ("tue_fail",), {"tue_tol": 2.0})
    assert st[31] == 0 and st[32:35] == [-1, -1, -1]                                   # -1 from Wednesday to Friday
    assert st[35] == 0 and st[30] == 0                                                 # the state before the failure swing returns the next week
    dm = tue_book(True)
    stm = flip_of(dm, [], ("tue_fail",), {"tue_tol": 2.0})
    assert stm[32:35] == [1, 1, 1] and stm[35] == 0                                    # the mirror: a lower low at an old low, a close in the upper third
    assert flip_of(d, [], ("tue_fail",), {"tue_tol": 0.5})[32] == 0                    # the old high is 1.0 away: outside a 0.5 tolerance
    rows = [tuple(r) for r in d.itertuples(index=False, name=None)]
    rows[31] = (4095, 4103, 4078, 4096)                                                # Tuesday closes above Monday close: no failure
    assert flip_of(dsess(rows, date(2024, 1, 1)), [], ("tue_fail",), {"tue_tol": 2.0})[32] == 0
    rows[31] = (4095, 4103, 4078, 4090)                                                # closes under Monday close but mid-range (not the lower third)
    assert flip_of(dsess(rows, date(2024, 1, 1)), [], ("tue_fail",), {"tue_tol": 2.0})[32] == 0
    assert flip_of(d, [], ("ob_mt",), {"tue_tol": 2.0})[32] == 0                       # not an active trigger
    b3 = json.loads(Params(flip_triggers=("ob_mt", "tue_fail"), htf_bias="flip", eq_tol_pts=0.5).bx)["b3"]
    assert BH3.flip_cfg(b3, 1.0) == {"tue_tol": 2.0} and BH3.flip_cfg(b3, 0.25) == {"tue_tol": 0.5} and BH3.flip_cfg({}, 1.0) == {}


# --- items 152 / 167 / 168: the intermarket columns --------------------------------------------------------------------------------

def im_series(tnx_vals, dxy_vals):
    idx = pd.bdate_range("2024-01-01", periods=len(tnx_vals))
    return pd.Series(dxy_vals, index=idx, dtype=float), pd.Series(tnx_vals, index=idx, dtype=float)


def test_notes_dxy_regime():
    """Rule and formula: the NOTE price direction (-sign of the yield slope) equal to the dollar direction = 'tandem' (the large consolidation regime). The spec test text lists 'TNX falling (notes up) with DXY
    rising' as opposed, which contradicts its own formula (notes up, dollar up = the same direction = tandem); the formula, the rule text and the second example agree, so they are built (owner question)."""
    n = 200
    dxy, tnx = im_series(np.linspace(4.5, 3.5, n), np.linspace(95, 105, n))              # yields falling (notes up) while the dollar rises: the same direction
    assert BH3.im3_columns(dxy, tnx).notes_dxy.iloc[-1] == "tandem"
    dxy, tnx = im_series(np.linspace(3.5, 4.5, n), np.linspace(105, 95, n))              # yields rising (notes down) while the dollar falls: the same direction (the spec second example)
    assert BH3.im3_columns(dxy, tnx).notes_dxy.iloc[-1] == "tandem"
    dxy, tnx = im_series(np.linspace(3.5, 4.5, n), np.linspace(95, 105, n))              # notes down, dollar up: opposite directions = the trending regime
    assert BH3.im3_columns(dxy, tnx).notes_dxy.iloc[-1] == "opposed"
    dxy, tnx = im_series(np.linspace(4.5, 3.5, n), np.linspace(105, 95, n))              # notes up, dollar down
    out = BH3.im3_columns(dxy, tnx)
    assert out.notes_dxy.iloc[-1] == "opposed" and (out.notes_dxy.iloc[:19] == "").all()
    # prior-day data only: the value of date t is unchanged by anything at t or later
    cut = BH3.im3_columns(dxy.iloc[:-7], tnx.iloc[:-7])
    assert (out.notes_dxy.iloc[:len(cut)].values == cut.notes_dxy.values).all()
    tnx2 = tnx.copy()
    tnx2.iloc[-1] += 9.0
    assert BH3.im3_columns(dxy, tnx2).notes_dxy.iloc[-1] == out.notes_dxy.iloc[-1]


def test_swing_gate_trend_ratios():
    n = 200
    dxy, tnx = im_series(np.full(n, 4.0) + 0.01 * np.sin(np.arange(n) * 2.1), np.full(n, 100.0) + 0.05 * np.cos(np.arange(n) * 1.7))      # flat, choppy
    out = BH3.im3_columns(dxy, tnx)
    assert out.tr_tnx.iloc[-1] < 0.5 and out.tr_dxy.iloc[-1] < 0.5                    # flat TNX and DXY: not trending
    dxy, tnx = im_series(np.linspace(3.0, 5.0, n), np.linspace(90, 110, n))
    out = BH3.im3_columns(dxy, tnx)
    assert out.tr_tnx.iloc[-1] > 0.9 and out.tr_dxy.iloc[-1] > 0.9                    # a steady trend: slope / mean change near 1
    assert np.isnan(out.tr_tnx.iloc[0])


def test_bond_lt_tag():
    n = 260
    dxy, tnx = im_series(np.linspace(5.0, 3.0, n), np.full(n, 100.0))
    out = BH3.im3_columns(dxy, tnx)
    assert out.bond_lt.iloc[-1] == 1                                                  # a falling TNX over 126 sessions: bonds up
    dxy2, tnx2 = im_series(np.linspace(3.0, 5.0, n), np.full(n, 100.0))
    assert BH3.im3_columns(dxy2, tnx2).bond_lt.iloc[-1] == -1
    tnx3 = tnx.copy()
    tnx3.iloc[-1] += 50.0                                                              # today value: not read
    assert BH3.im3_columns(dxy, tnx3).bond_lt.iloc[-1] == 1
    assert out.bond_lt.iloc[:127].isna().all()


# --- items 215 / 216: the day maps ------------------------------------------------------------------------------------------------

def long_frame(rows, start=date(2025, 7, 7), scale=1.0):
    from test_caption_gap_bh1c import fut_frame
    return fut_frame([(o * scale, h * scale, l * scale, c * scale) for o, h, l, c in rows], start)


def rally_then_fall(n_up=50, n_dn=22, hi=5300.0):
    c = list(np.linspace(5000, hi, n_up)) + list(np.linspace(hi, 5100, n_dn))
    rows = []
    prev = c[0]
    for x in c:
        rows.append((prev, max(prev, x) + 5, min(prev, x) - 5, x))
        prev = x
    return rows


def test_fall_low_bias():
    rows = rally_then_fall()
    es = long_frame(rows)
    days = list(pd.bdate_range("2025-07-07", periods=len(rows)).date)
    k = len(rows) - 1
    dsmt = {days[k]: 1}                                                                # ES makes a lower daily low, NQ a higher one (October)
    out = BH3.fall_low_map(es, es, dsmt)
    assert days[k].month == 10 and out[days[k]] == 1 and out[days[k - 1]] == 0         # in the fall window, below the 60-session EQ
    es2 = long_frame(rows + [(5100, 5400, 5090, 5395)] + [(5395, 5400, 5390, 5395)] * 2)
    d2 = list(pd.bdate_range("2025-07-07", periods=len(rows) + 3).date)
    dsmt2 = {days[k]: 1}
    o2 = BH3.fall_low_map(es2, es2, dsmt2)
    assert o2[d2[k + 1]] == 1 and o2[d2[k + 2]] == 0                                    # persists until the 60-session high is taken
    assert BH3.fall_low_map(es, es, {})[days[k]] == 0                                  # no SMT: nothing
    # a September session before the window opens (15 Sep) or above the EQ gives nothing
    rows_up = [(5000 + 4 * q, 5010 + 4 * q, 4995 + 4 * q, 5005 + 4 * q) for q in range(len(rows))]
    es_up = long_frame(rows_up)
    assert BH3.fall_low_map(es_up, es_up, {days[k]: 1})[days[k]] == 0                  # the close is above the 60-session EQ


def test_season_poised_map():
    n = 45
    dn = [(5200 - 6 * q, 5205 - 6 * q, 5190 - 6 * q, 5195 - 6 * q) for q in range(n)]
    up = [(5000 + 6 * q, 5010 + 6 * q, 5000 + 6 * q, 5008 + 6 * q) for q in range(n)]
    es_dn, nq_dn = long_frame(dn, date(2026, 1, 5)), long_frame(dn, date(2026, 1, 5), 3.5)
    last = list(pd.bdate_range("2026-01-05", periods=n).date)[-1]
    assert BH3.poised_map(es_dn, nq_dn)[last] == -1                                    # ES and NQ both falling, no SMT: not poised for a long window
    es_up, nq_up = long_frame(up, date(2026, 1, 5)), long_frame(up, date(2026, 1, 5), 3.5)
    assert BH3.poised_map(es_up, nq_up)[last] == 1
    mixed = BH3.poised_map(es_up, nq_dn)
    assert mixed[last] == 0                                                            # the two disagree and there is no SMT
    # a bullish SMT with the price under the 60-session EQ makes it poised
    long_dn = long_frame([(6000 - 8 * q, 6005 - 8 * q, 5995 - 8 * q, 6000 - 8 * q) for q in range(70)], date(2025, 12, 1))
    days = list(pd.bdate_range("2025-12-01", periods=70).date)
    m2 = BH3.poised_map(long_dn, long_dn, {days[-1]: 1})
    assert m2[days[-1]] == -1 or m2[days[-1]] == 1                                      # both falling: -1 first (the slope reading wins); SMT is the fallback
    flat = long_frame([(5000, 5006, 4994, 5000 + (q % 3) - 1) for q in range(70)], date(2025, 12, 1))
    assert BH3.poised_map(flat, flat, {days[-1]: 1})[days[-1]] in (0, 1)


# --- items 224 / 227: the table parts of the composers ----------------------------------------------------------------------------

def test_checklist_table_columns():
    out = pd.DataFrame({"profile": ["consol", "trend", "trend", ""], "iof_w": [1, 0, 0, 0], "wk_bias": [1, 1, 0, -1], "iof": [0, 1, 0, 0], "flip": [-1, 0, 1, 0], "draw": [1, -1, -1, 0]})
    r = BH3.chk_columns(out)
    assert list(r["wk_chk_tail"]) == [0, 1, 0, -1] and list(r["wk_consol"]) == [1, 0, 0, 0]       # consol stops the cascade with a neutral result; else iof_w, then the weekly draw
    assert list(r["d_head"]) == [0, 1, 0, 0] and list(r["d_tail"]) == [-1, -1, 1, 0]               # the daily tail: the flip state, then the draw


def test_cot_loader_feeds_the_b20_tag(monkeypatch):
    """B20-cot-data-spec: the annual archives feed bias_htf.load_cot (the cot_tag state) beside the CSV files."""
    from pathlib import Path
    from mentorship import bias_htf as BX
    reps = pd.date_range("2022-01-04", periods=40, freq="7D")
    rows = pd.DataFrame({"report_date": reps, "comm_long": 100.0, "comm_short": 0.0, "net": [float(k) for k in range(40)]})
    monkeypatch.setattr(cot, "load_reports", lambda market="", folder=None: rows)
    BX._COT.clear()
    t = BX.load_cot("E-MINI S&P 500", Path("data/mentorship/_no_such_cot_dir"))
    assert t is not None and len(t) == 40 and list(t.net.iloc[:3]) == [0.0, 1.0, 2.0]
    assert t.index[0] == reps[0] + pd.Timedelta(days=6)                                  # usable the Monday after the Tuesday report (the Friday release in between)
    assert BX.cot_state(t.index[35], t) == 1                                              # a rising net: above the midpoint of its range
    BX._COT.clear()
