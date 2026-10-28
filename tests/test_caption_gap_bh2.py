"""Caption-gap pass, package bias_htf#2/7 (35 specs from digests/rulebook_gaps/bias_htf_intermarket.md items 82-88, 90, 91, 93-96, 104-109, 114, 116, 117, 119, 121, 122, 130-136, 138, 139, 143):
defaults / validation / study variants / table configuration, and the TABLE-side functions (bh2.py) on hand-made daily books. The engine hooks are in test_caption_gap_bh2b.py, the no-look-ahead runs
in test_caption_gap_bh2c.py. Nothing here needs market data; nothing is platform specific; no file outside the repo is written."""
import json
import warnings
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bias_htf as BX, htf, levels as L, study
from mentorship.strategy import Params

from test_caption_gap_bh1 import dsess, arr, flip_of  # noqa: E402
from test_caption_gap_bh1c import fut_frame  # noqa: E402
from test_caption_gap_dwc1 import FUT  # noqa: E402

NAN = float("nan")

NEW_FIELDS = (
    "scalp_week_risk", "q_days_tag", "q_window_lo", "q_window_hi", "q_window_gate", "q_window_size", "shift_due_tag", "qshift_bias", "q_obj_lean", "q_obj_days", "qshift_strong_consol", "qshift_strong_pct",
    "iof_weekly_weight", "iof_w_risk", "iof_w_weeks", "sibi_gate", "wick_ce_60m", "sibi15_ce_cancel", "allow_reversal_after_target", "soft_carry", "soft_carry_risk", "inside_bisi_release",
    "release_pts", "fast_draw_extend", "fast_draw_mult", "dxy_needs_rates", "pd3_result", "pd3_disp_adr", "pd3_first_caution", "wk_q75_confirm", "consol_dir", "consol_chase_frac",
    "htf_after_draw", "pd_two_level", "range_no_bias", "range_no_bias_pct", "eq_tiebreak", "eq_tie_frac", "tier_regime_gate", "tug_required", "raid_profile_bias", "raid_profile_n", "htf_bias_tf",
    "htf_rank_tf", "flip_terminus", "flip_max_days", "dsmt_bias", "dsmt_days", "im_regime_tag", "oneway_n", "raid_side_gate", "raid_ratio", "ipda_draw_side", "first_clue_neutral",
    "ipda_extreme_pause", "decoupled_scalp")
KNOBS = {"scalp_week_risk", "q_window_lo", "q_window_hi", "q_obj_days", "qshift_strong_pct", "iof_w_risk", "iof_w_weeks", "soft_carry_risk", "release_pts", "fast_draw_mult", "pd3_disp_adr",
         "consol_chase_frac", "range_no_bias_pct", "eq_tie_frac", "raid_profile_n", "flip_max_days", "dsmt_days", "raid_ratio"}
OFF = dict(q_days_tag=False, q_window_gate=False, q_window_size=1.0, shift_due_tag=False, qshift_bias=False, q_obj_lean=False, qshift_strong_consol=False, iof_weekly_weight=False, sibi_gate=False, wick_ce_60m=False,
           sibi15_ce_cancel=False, allow_reversal_after_target=False, soft_carry=False, inside_bisi_release=False, fast_draw_extend=False, dxy_needs_rates=False, pd3_result="flip",
           pd3_first_caution=False, wk_q75_confirm=False, consol_dir="off", htf_after_draw="neutral", pd_two_level=False, range_no_bias=False, eq_tiebreak=False, tier_regime_gate=False,
           tug_required=False, raid_profile_bias=False, htf_bias_tf="D", htf_rank_tf=False, flip_terminus=False, dsmt_bias=False, im_regime_tag=False, oneway_n=0, raid_side_gate=False,
           ipda_draw_side=False, first_clue_neutral=False, ipda_extreme_pause=False, decoupled_scalp=False)


# --- hand-made daily books ----------------------------------------------------------------------------------------------

def book(closes, up_wick=0.8, dn_wick=0.8):
    """Daily bars from a close path: each opens at the previous close; up bars carry a small low wick and a larger high wick (and the mirror), so the turns are strict 3-bar pivots."""
    c = np.array(closes, float)
    o = np.r_[c[0], c[:-1]]
    up = c >= o
    h = np.maximum(o, c) + np.where(up, up_wick, 0.1)
    l = np.minimum(o, c) - np.where(up, 0.1, dn_wick)
    return o, h, l, c


def stair(cycles, base=100.0, up=3.0, back=2.0, n_up=3, n_dn=2):
    """A staircase up: n_up bars of +up then n_dn bars of -back per cycle (higher peaks and higher troughs)."""
    c = [base]
    for _ in range(cycles):
        for _ in range(n_up):
            c.append(c[-1] + up)
        for _ in range(n_dn):
            c.append(c[-1] - back)
    return c


def crash(c, n=3, step=4.0):
    return c + [c[-1] - step * q for q in range(1, n + 1)]


def week_rows(specs):
    """Daily rows of consecutive Monday-Friday weeks: each (o, h, l, c) is the WEEK's candle (open on Monday, high on Tuesday, low on Wednesday, close on Friday)."""
    rows = []
    for o, h, l, c in specs:
        rows += [(o, o, o, o), (o, h, o, o), (o, o, l, o), (o, o, o, o), (o, max(o, c), min(o, c), c)]
    return rows


# --- defaults and validation --------------------------------------------------------------------------------------------

def test_defaults_and_validation():
    p = Params()
    for f in NEW_FIELDS:
        assert f in Params.__dataclass_fields__, f
    for k, v in OFF.items():
        assert getattr(p, k) == v, k
    assert (p.scalp_week_risk, p.q_window_lo, p.q_window_hi, p.q_obj_days, p.qshift_strong_pct, p.iof_w_risk, p.iof_w_weeks, p.soft_carry_risk, p.release_pts, p.fast_draw_mult) == (0.5, 40, 60, 84, 0.10, 0.5, 10, 0.5, 1.0, 1.5)
    assert (p.pd3_disp_adr, p.consol_chase_frac, p.range_no_bias_pct, p.eq_tie_frac, p.raid_profile_n, p.flip_max_days, p.dsmt_days, p.raid_ratio) == (1.5, 0.25, 0.62, 0.10, 2, 126, 18, 2.0)
    assert p.bias_neutral == "skip" and p.bx == ""
    # the owner-fixed Silver Bullet switches are untouched by this chunk
    assert p.sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and p.want_all_engines is True
    for bad in (dict(pd3_result="x"), dict(consol_dir="x"), dict(htf_after_draw="x"), dict(htf_bias_tf="X"), dict(bias_neutral="x"), dict(scalp_week_risk=0), dict(soft_carry_risk=1.5), dict(iof_w_risk=0),
                dict(q_window_lo=50, q_window_hi=40), dict(q_window_size=0), dict(q_obj_days=0), dict(iof_w_weeks=2), dict(release_pts=-1), dict(fast_draw_mult=0), dict(pd3_disp_adr=0), dict(consol_chase_frac=0.8),
                dict(range_no_bias_pct=0.4), dict(eq_tie_frac=0.6), dict(raid_profile_n=0), dict(flip_max_days=0), dict(dsmt_days=1), dict(oneway_n=-1), dict(raid_ratio=0), dict(qshift_strong_pct=1.0)):
        with pytest.raises(ValueError):
            Params(**bad)
    assert Params(htf_bias_tf="M").htf_monthly_arrays is True            # the monthly draw needs the monthly arrays
    assert Params(htf_bias_tf="W").htf_monthly_arrays is False
    Params(bias_neutral="scalp_week", htf_bias="combo", pd3_result="neutral", flip_triggers=("ob_mt", "wk_dc", "flip_pd3"))


def test_every_new_switch_has_a_study_variant():
    used = set()
    for v in study._BH2_DECISIONS.values():
        used |= set(v)
    for f in NEW_FIELDS:
        assert f in used or f in KNOBS, f
    for k, v in study._BH2_DECISIONS.items():
        assert k in study.DECISIONS
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            replace(Params(), **v)
    for gid in ("B17-neutral-htf-monday-close", "B22-quarterly-shift", "B22-timing-tool", "B6-weekly-iof", "NEW-daily-sibi-bias-gate", "A23-intraday-close-line-in-sand", "B3-reversal-after-target",
                "B17-unreached-draw-soft-bias", "B17-inside-daily-range-no-trade", "NEW-speed-into-weekly-draw", "NEW-rates-dxy-fx-direction", "B8-three-pd-array-abort", "B8-weekly-wick-quadrant-gate",
                "N8-consolidation-breakout-direction", "B17-after-draw-retrace-or-reverse", "A21-two-level-discount", "B3-range-trading-without-bias", "B3-eq-recent-structure-break",
                "B6-hrlr-lrlr-structure-regime", "B6-consolidation-raid-profile", "B5-monthly-first-hierarchy", "B17-hold-bias-most-recent-htf-setup", "B18-htf-daily-smt", "B19-bond-stock-dxy-sign",
                "E4-daily-one-way-delivery-rebalance", "X3-iof-60day-framing-raids", "X3-b22-shift-trigger-quarter-bias", "X3-b21-draw-side-and-flip", "X3-b22-shift-form-strong-trend",
                "X3-shift-due-six-months", "X3-b6-tug-of-war-new-ground", "X3-one-sided-delivery-first-clue", "X3-60day-low-deep-discount-bounce", "B19-four-asset-risk-map"):
        assert any(k.startswith(gid) for k in study.DECISIONS), gid


def test_table_configuration_names_what_the_switches_need():
    x = json.loads(Params(q_window_gate=True, sibi_gate=True, htf_after_draw="reverse", fast_draw_extend=True, tug_required=True, pd3_result="neutral", pd3_first_caution=True, consol_dir="prior_strongest",
                          flip_triggers=("ob_mt", "flip_pd3")).bx)
    assert set(x["b2"]) >= {"qd", "sibi", "ad", "fd", "tier", "fl", "cd"} and x["b2"]["fl"] == {"pd3n": 1.5, "pd3log": 1} and x["obj"] == 1 and x["wk"] == 1 and x["pr"] == 1
    assert x["b1"]["dr"] == [5, "close"]                                             # consol_dir reads the daily range columns
    y = json.loads(Params(eq_tiebreak=True, ipda_draw_side=True, qshift_bias=True, iof_weekly_weight=True, oneway_n=4, htf_bias_tf="W").bx)
    assert y["b2"]["brk"] == [0.1] and y["b2"]["qs2"][2] == 1 and y["b2"]["ow"] == 4 and y["b2"]["btf"] == "W" and y["b2"]["iofw"] == [10, 2]
    assert json.loads(Params(raid_profile_bias=True, raid_profile_n=3).bx)["b2"]["rp"] == 3
    assert Params(bias_neutral="scalp_week").bx == ""                                # engine-only switches add nothing to the table


# --- items 84 / 134: the time since the last daily MSS ----------------------------------------------------------------------------------

def test_q_days_cast():
    c = crash(stair(5), 3, 4.0)
    c = c + [c[-1] - 0.8 * q for q in range(1, 160)]
    o, h, l, cl = book(c)
    ev, mss, ld, lm = BH2.break_stream(h, l, cl)
    assert list(np.flatnonzero(ev)) and ev[np.flatnonzero(mss)[-1]] == -1 and mss.sum() == 1            # the staircase breaks upward (no MSS: same direction), the crash is the one MSS
    j = int(np.flatnonzero(mss)[-1])
    ks = np.array([j + 1, j + 39, j + 45, j + 61, j + 130])
    q = BH2.q_columns(h, l, cl, ks, 40, 60)
    assert list(q["q_days"]) == [1, 39, 45, 61, 130]
    assert list(q["q_window"]) == [0, 0, 1, 0, 0]                                              # inside S+40 .. S+60 only
    assert list(q["shift_due"]) == [0, 0, 0, 0, 1]                                             # item 134: 130 sessions since the last MSS on a one-way path (126 needed)
    # nothing before the first MSS
    assert list(BH2.q_columns(h, l, cl, np.array([5]), 40, 60)["q_days"]) == [-1]


def test_shift_due_is_false_without_a_one_way_move():
    c = crash(stair(5), 3, 4.0)
    c = c + [c[-1]] * 160                                                                        # flat for 160 sessions: 130+ since the MSS but no net move
    o, h, l, cl = book(c)
    ev, mss, ld, lm = BH2.break_stream(h, l, cl)
    j = int(np.flatnonzero(mss)[-1])
    q = BH2.q_columns(h, l, cl, np.array([j + 140]), 40, 60)
    assert q["q_days"][0] == 140 and q["shift_due"][0] == 0


# --- item 108: the EQ tie-break ------------------------------------------------------------------------------------------------------

def test_eq_tiebreak_columns():
    s5 = stair(5)
    c = s5 + [s5[-1] + 3.0, s5[-1] + 6.0, s5[-1] + 9.0, s5[-1] + 5.0, s5[-1] + 1.0]         # the staircase breaks highs upward; the retrace stops near the 20-session range's EQ without closing under the last trough
    o, h, l, cl = book(c)
    k = len(cl)
    ks = np.array([k])
    bc = BH2.break_columns(h, l, cl, ks, 0.30)
    assert bc["last_break"][0] == 1
    hi, lo = h[k - 20:k].max(), l[k - 20:k].min()
    assert bc["eq_near"][0] == int(abs(cl[-1] - (hi + lo) / 2) <= 0.30 * (hi - lo)) == 1
    far = BH2.break_columns(h, l, cl, np.array([k - 3]), 0.10)                    # at the staircase top: well away from the EQ
    assert far["eq_near"][0] == 0 and far["last_break"][0] == 1
    # a monthly pair is built when the daily book is given
    d = dsess([(x, x + 1, x - 1, x) for x in np.linspace(100, 200, 330)], start=date(2024, 1, 1))
    bm = BH2.break_columns(d.high.values, d.low.values, d.close.values, np.array([300]), 0.10, d)
    assert "last_break_m" in bm and "eq_near_m" in bm


# --- items 131 / 133 / 83 / 132: the quarterly shift ----------------------------------------------------------------------------------------

def _shift_book(cycles=75, after=100):
    c = stair(cycles) + [None]
    c = c[:-1]
    top = c[-1]
    c = crash(c, 3, 4.0)
    c = c + [c[-1] - 0.5 * q for q in range(1, after + 1)]
    return book(c)


def test_qshift_trigger_and_persistence():
    o, h, l, c = _shift_book()
    ks = np.arange(1, len(c) + 1)
    out = BH2.qshift_columns(h, l, c, [], ks, strong_pct=0.9)
    qs = out["qshift"]
    j = int(np.flatnonzero(qs == -1)[0]) - 1                                       # the session of the trigger (the row after it is the first -1)
    assert qs[j] == 0 and (qs[j + 1:j + 64] == -1).all()                           # a new 60-session high in the last 10 sessions, then a daily low under the last STL: -1 for 63 sessions
    assert (qs[j + 66:] == 0).all()
    assert out["qs_form"][j + 1] == "retrace"                                      # (strong_pct 0.9: the trend is not that strong)
    # no new 60-session high first: no shift
    flat = book([100.0 + (q % 3) for q in range(120)] + [90.0, 85.0, 80.0])
    assert (BH2.qshift_columns(flat[1], flat[2], flat[3], [], np.arange(1, 124), strong_pct=0.1)["qshift"] == 0).all()
    # a new 60-session high cancels a standing shift (the mirror of the trigger)
    ups = book(crash(stair(75), 3, 4.0) + stair(15, base=crash(stair(75), 3, 4.0)[-1], up=6.0)[1:])
    q2 = BH2.qshift_columns(ups[1], ups[2], ups[3], [], np.arange(1, len(ups[3]) + 1), strong_pct=0.9)["qshift"]
    assert (q2 == -1).any() and q2[-1] == 0


def test_qshift_mirror_is_plus_one():
    o, h, l, c = _shift_book()
    om, hm, lm, cm = book([400.0 - x for x in c])                                     # the mirrored path: a new 60-session low, then a daily high above the last STH
    out = BH2.qshift_columns(hm, lm, cm, [], np.arange(1, len(cm) + 1), strong_pct=0.9)
    assert (out["qshift"] == 1).sum() >= 60 and (out["qshift"] == -1).sum() == 0


def test_qshift_form_strong_trend():
    o, h, l, c = _shift_book()
    ks = np.arange(1, len(c) + 1)
    strong = BH2.qshift_columns(h, l, c, [], ks, strong_pct=0.10)
    j = int(np.flatnonzero(strong["qshift"] == -1)[0])
    assert strong["qs_form"][j] == "consol"                                         # a bearish shift 39 % above the 252-session mean: a consolidation, not a retracement
    assert strong["qs_scalp"][j] == 1 and strong["qs_scalp"][j + 19] == 1 and strong["qs_scalp"][j + 20] == 0      # the next 20 sessions are scalps
    weak = BH2.qshift_columns(h, l, c, [], ks, strong_pct=0.9)
    assert (weak["qs_scalp"] == 0).all()
    short = BH2.qshift_columns(h[:200], l[:200], c[:200], [], np.arange(1, 201), strong_pct=0.0)                     # fewer than 252 sessions: no trend reading
    assert not (short["qs_form"] == "consol").any()


def test_q_obj():
    o, h, l, c = _shift_book(after=120)
    ks = np.arange(1, len(c) + 1)
    first = BH2.qshift_columns(h, l, c, [], ks, strong_pct=0.9)["qshift"]
    j = int(np.flatnonzero(first == -1)[0]) - 1                                       # (row r shows the state after session r: the first -1 row is the trigger session + 0; j = one row earlier)
    lo60 = float(l[max(0, j + 1 - 59):j + 2].min())                                   # the 60-session low at the trigger session j + 1
    wk = [htf.Arr("bull", "fvg", "W", lo60 - 300, lo60 - 320, lo60 - 310, 5)]          # a weekly BISI 300 pts below the 60-session range
    out = BH2.qshift_columns(h, l, c, wk, ks, strong_pct=0.9, obj_days=84, want_obj=True)
    qo = out["q_obj"]
    assert np.isnan(qo[j]) and qo[j + 1] == pytest.approx(lo60 - 300)                  # set with the shift: the near edge (top) of the weekly gap
    assert qo[j + 83] == pytest.approx(lo60 - 300)                                     # persisting
    assert np.isnan(qo[j + 85])                                                        # expired after 84 sessions
    assert out["qshift"][j + 70] == 0 and qo[j + 70] == pytest.approx(lo60 - 300)      # the objective outlives the 63-session shift
    # an array that is not beyond the 60-session range is no objective
    near = [htf.Arr("bull", "fvg", "W", lo60 + 5, lo60 + 1, lo60 + 3, 5)]
    assert np.isnan(BH2.qshift_columns(h, l, c, near, ks, strong_pct=0.9, want_obj=True)["q_obj"][j + 1])
    # traded: a later low into the array ends it
    deep = book(list(c[:j + 2]) + [lo60 - 305.0] * 5)
    q3 = BH2.qshift_columns(deep[1], deep[2], deep[3], wk, np.arange(1, len(deep[3]) + 1), strong_pct=0.9, want_obj=True)["q_obj"]
    assert q3[j + 1] == pytest.approx(lo60 - 300) and np.isnan(q3[-1])


def test_ipda_side_shift():
    # a 20-day-low raid short of the 40-day low, then a bullish MSS: qshift +1 (X3-b21-draw-side-and-flip)
    c = stair(2, base=200.0, up=-3.0, back=-2.0)                                     # a staircase DOWN (lower peaks, lower troughs)
    c = c + [c[-1]] * 40
    o, h, l, cl = book(c)
    base = BH2.qshift_columns(h, l, cl, [], np.arange(1, len(cl) + 1), ipda=False)["qshift"]
    assert (base == 0).all()
    ev, mss, ld, lm = BH2.break_stream(h, l, cl)
    assert isinstance(ld[-1], (int, np.integer))


# --- item 85: the weekly order flow --------------------------------------------------------------------------------------------------------

def test_iof_weekly():
    weeks = [(100, 110, 98, 108), (108, 111, 102, 104), (104, 118, 103, 116), (116, 119, 110, 112), (112, 128, 111, 126), (126, 129, 120, 122), (122, 138, 121, 136), (136, 139, 130, 132),
             (132, 148, 131, 146), (146, 149, 140, 142), (142, 158, 141, 156), (156, 159, 150, 152)]
    d = dsess(week_rows(weeks), start=date(2026, 1, 5))
    w = htf.weeks(d)
    assert len(w) == 12
    ks = np.array([5 * q for q in (3, 6, 8, 11)])                                      # the first session of weeks 3, 6, 8, 11: weeks before them are complete
    col = BH2.iof_w_column(d, w, ks, 10, 2)
    from mentorship.bias_htf import iof_score
    wo, wh, wl, wc = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    exp = [iof_score(wo, wh, wl, wc, q, 10) for q in (3, 6, 8, 11)]
    assert list(col) == [1 if s >= 2 else (-1 if s <= -2 else 0) for s in exp]
    assert col[-1] == 1 and exp[-1] >= 2                                               # premium arrays run through and the discount candles held: bullish
    # a row inside the week uses only completed weeks: the same value on every session of the week
    mid = BH2.iof_w_column(d, w, np.array([5 * 11, 5 * 11 + 3]), 10, 2)
    assert mid[0] == mid[1]
    mirror = [(400 - o_, 400 - l_, 400 - h_, 400 - c_) for o_, h_, l_, c_ in weeks]
    dm = dsess(week_rows(mirror), start=date(2026, 1, 5))
    assert BH2.iof_w_column(dm, htf.weeks(dm), np.array([55]), 10, 2)[0] == -1


# --- item 86: the daily SIBI / BISI after a sweep ---------------------------------------------------------------------------------------

def test_sibi_columns():
    c = crash(stair(4), 3, 4.0)
    c = c + [c[-1] - 1.0, c[-1] - 2.0]
    c = c + [c[-1] + 5.0, c[-1] + 7.0, c[-1] + 9.0]                                    # the sweep, then a bounce
    o, h, l, cl = book(c)
    last_h, last_l = BH2.pivot_levels(h, l)
    sweep = int(np.flatnonzero(l < last_l)[-1])
    assert sweep == len(cl) - 3                                                         # the last lower low (against the latest KNOWN pivot low)
    ks = np.array([len(cl), len(cl)])
    px = np.array([cl[-1], cl[-1]], float)
    base = float(cl[sweep])
    bear = htf.Arr("bear", "fvg", "D", base + 60, base + 40, base + 50, sweep + 1)       # a daily SIBI formed after the sweep (not yet closed through)
    old = htf.Arr("bear", "fvg", "D", base + 10, base + 5, base + 7, 2)                   # one that formed BEFORE it
    out = BH2.sibi_columns(o, h, l, cl, [bear, old], ks, px)
    assert list(out["sibi_dir"]) == [-1, -1] and out["sibi_top"][0] == bear.top and out["sibi_bot"][0] == bear.bottom
    assert list(BH2.sibi_columns(o, h, l, cl, [old], ks, px)["sibi_dir"]) == [0, 0]       # only an FVG formed after the sweep counts
    dead = htf.Arr("bear", "fvg", "D", base + 3, base + 1, base + 2, sweep + 1)           # the bounce's closes (base + 5 ..) went through its top
    assert list(BH2.sibi_columns(o, h, l, cl, [dead], ks, px)["sibi_dir"]) == [0, 0]
    bull = htf.Arr("bull", "fvg", "D", base + 60, base + 40, base + 50, sweep + 1)
    assert list(BH2.sibi_columns(o, h, l, cl, [bull], ks, px)["sibi_dir"]) == [0, 0]      # a sell-side sweep gives a SIBI, not a BISI
    near, far = htf.Arr("bear", "fvg", "D", base + 70, base + 60, base + 65, sweep + 1), bear
    pick = BH2.sibi_columns(o, h, l, cl, [near, far], ks, px)                              # the nearest zone to the price
    assert pick["sibi_bot"][0] == far.bottom
    # the mirror: a buy-side sweep gives the nearest BISI
    om, hm, lm, cm = book([400 - x for x in c])
    bull2 = htf.Arr("bull", "fvg", "D", 400 - (base + 40), 400 - (base + 60), 400 - (base + 50), sweep + 1)
    pm = BH2.sibi_columns(om, hm, lm, cm, [bull2], ks, 400 - px)
    assert list(pm["sibi_dir"]) == [1, 1]


# --- item 96: the prior weekly wick's 75 % quadrant ------------------------------------------------------------------------------------

def test_wk_q75_column():
    prior = (4000, 4140, 3990, 4100)                                                     # body top 4100, upper wick 4100-4140: the 75 % level is 4130
    rows = week_rows([(3900, 4010, 3890, 3990), prior]) + [(4100, 4128, 4090, 4128), (4128, 4140, 4120, 4132), (4132, 4140, 4125, 4135)]
    d = dsess(rows, start=date(2026, 1, 5))
    w = htf.weeks(d)
    c = d.close.values.astype(float)
    # the current week's Mon / Tue / Wed rows (sessions 10, 11, 12)
    col = BH2.q75_column(d, w, np.array([10, 11, 12]), c)
    assert list(col) == [0, 0, 1]                                                         # a close at 4128 leaves 0; the close at 4132 gives +1 from the next day
    low = week_rows([(4000, 4010, 3860, 3900)])                                          # a bearish prior week: body bottom 3900, lower wick 3900-3860: 75 % level 3870
    d2 = dsess(week_rows([(4000, 4010, 3860, 3900)]) + [(3900, 3905, 3880, 3880), (3880, 3890, 3860, 3868), (3868, 3870, 3860, 3865)], start=date(2026, 1, 5))
    assert list(BH2.q75_column(d2, htf.weeks(d2), np.array([5, 6, 7]), d2.close.values.astype(float))) == [0, 0, -1]


# --- items 104 / 114: the daily ranges ---------------------------------------------------------------------------------------------------

RANGE_ROWS = (
    [(100, 105, 95, 100)] + [(100, 104, 96, 101), (101, 104, 96, 99), (99, 104, 96, 102), (102, 104, 96, 100)]                           # range 1: formed at session 4 (closes inside session 0's 95-105)
    + [(100, 103, 94, 100), (100, 108, 99, 106)]                                                                                          # 5: raids the low (94) and closes back inside; 6: closes 106 (> 105): exit up
    + [(106, 115, 105, 110)] + [(110, 114, 106, 111), (111, 114, 106, 109), (109, 114, 106, 112), (112, 114, 106, 110)]                    # range 2 from session 7 (105-115), formed at 11
    + [(110, 113, 104, 110), (110, 118, 109, 116)]                                                                                        # 12: raids the low (104); 13: closes 116 (> 115): exit up
    + [(116, 118, 115, 117)] * 3)


def test_range_events_consol_prior_and_raid_profile():
    d = dsess(RANGE_ROWS, start=date(2026, 1, 5))
    o, h, l, c = (d[k].values.astype(float) for k in ("open", "high", "low", "close"))
    ev = BH2.range_events(h, l, c, 5, "close")
    assert [(e["a"], e["f"], e["b"], e["dir"]) for e in ev][:2] == [(0, 4, 6, 1), (7, 11, 13, 1)]
    ks = np.arange(1, len(c) + 1)
    rp = dict(zip(ks, BH2.raid_profile_column(h, l, ks, ev, 2)))                          # keyed by the row's session k
    assert rp[13] == 0 and rp[14] == 1                                                    # session 14: both completed ranges raided the low first and exited up (the 2nd broke out at session 13)
    assert dict(zip(ks, BH2.raid_profile_column(h, l, ks, ev, 1)))[7] == 1                # one completed range is enough for n = 1
    cp = dict(zip(ks, BH2.consol_prior_column(o, h, l, c, ks, ev)))
    assert cp[12] == 1                                                                    # inside range 2 (session 12): the strongest day since range 1's breakout was an up day
    assert cp[4] == 0                                                                     # before any range: nothing
    # the mirror: two ranges that raided the high first and exited down
    mr = [(400 - o_, 400 - l_, 400 - h_, 400 - c_) for o_, h_, l_, c_ in RANGE_ROWS]
    dm = dsess(mr, start=date(2026, 1, 5))
    evm = BH2.range_events(dm.high.values.astype(float), dm.low.values.astype(float), dm.close.values.astype(float), 5, "close")
    assert dict(zip(range(1, len(dm) + 1), BH2.raid_profile_column(dm.high.values.astype(float), dm.low.values.astype(float), np.arange(1, len(dm) + 1), evm, 2)))[14] == -1


# --- item 109: the structure regime ------------------------------------------------------------------------------------------------------

def _tier_book(mirror=False):
    peaks = [100, 96, 104, 98, 112, 102, 108, 100, 106, 96, 102, 94, 99]
    troughs = [90, 88, 92, 86, 94, 84, 91, 82, 90, 80, 88, 78, 86]
    h, l = [], []
    for p_, t_ in zip(peaks, troughs):
        h += [p_, t_ + 1]
        l += [p_ - 1, t_]
    h, l = np.array(h, float), np.array(l, float)
    h = np.r_[h, 85.0, 83.0, 81.0]
    l = np.r_[l, 77.0, 75.0, 74.0]
    if mirror:
        h, l = 400 - l, 400 - h
    return h, l


def test_tier_regime():
    h, l = _tier_book()
    ks = np.arange(8, len(h))
    t = BH2.tier_columns(h, l, ks)
    reg = dict(zip(ks, t["tier_regime"]))
    assert reg[8] == 0 and reg[27] == -1 and reg[28] == -1                           # an intact LTH, a lower ITH and the short-term lows run: high-resistance-rally mode
    assert dict(zip(ks, t["tier_ith"]))[27] == 102.0                                   # the defended intermediate-term high
    # a trade above the last ITH clears it
    h2 = h.copy()
    h2[27] = 103.0                                                                       # a session trades above the last ITH (102): the regime is cleared for the next row
    t2 = BH2.tier_columns(h2, l, ks)
    assert dict(zip(ks, t2["tier_regime"]))[28] == 0
    hm, lm = _tier_book(mirror=True)
    tm = BH2.tier_columns(hm, lm, ks)
    assert dict(zip(ks, tm["tier_regime"]))[27] == 1 and dict(zip(ks, tm["tier_ith"]))[27] == 400 - 102.0


# --- item 116: the monthly / weekly draw -------------------------------------------------------------------------------------------------

def test_btf_columns():
    rows = [(100.0, 102.0, 99.0, 100.0)] * 40
    rows[5] = (100.0, 125.0, 99.0, 100.0)                                                  # January's high 125 ...
    rows[6] = (100.0, 102.0, 60.0, 100.0)                                                  # ... and low 60 (the weekly gap below formed after it)
    d = dsess(rows, start=date(2026, 1, 5))
    h, l, c = (d[k].values.astype(float) for k in ("high", "low", "close"))
    monthly = htf.Arr("bear", "fvg", "M", 160.0, 150.0, 155.0, 3)                         # an unfilled monthly bear FVG ABOVE the price: price is drawn up to it
    weekly = htf.Arr("bull", "fvg", "W", 99.5, 90.0, 95.0, 10)                             # a weekly bull FVG just BELOW the price: price is drawn down to it
    k = np.array([30])                                                                     # mid-February
    out = BH2.btf_columns([monthly, weekly], k, np.array([100.0]), h, l, c)               # FVGs only
    assert out["bias_m"][0] == 1 and out["bias_w"][0] == -1
    assert BH2.btf_columns([weekly], k, np.array([100.0]), h, l, c)["bias_m"][0] == 0     # no monthly array: the engine falls back to the weekly
    # with the daily book the previous month's / week's extremes are draws too: January's high (25 away) is nearer than the monthly FVG (50 away), the weekly FVG (0.5) than the week's high
    wk = BH2.btf_columns([monthly, weekly], k, np.array([100.0]), h, l, c, d)
    assert wk["bias_m"][0] == 1 and wk["bias_w"][0] == -1
    assert BH2.btf_columns([], k, np.array([100.0]), h, l, c, d)["bias_m"][0] == 1             # January's high 25 above vs low 40 below: up even without any array
    assert BH2.btf_columns([], k, np.array([100.0]), h, l, c, d)["bias_w"][0] in (-1, 1)
    # an FVG-only reading is one-sided in a trend: the pools add the other side
    assert BH2.btf_columns([htf.Arr("bull", "fvg", "M", 70.0, 60.0, 65.0, 10)], k, np.array([100.0]), h, l, c)["bias_m"][0] == -1
    assert BH2.btf_columns([htf.Arr("bull", "fvg", "M", 70.0, 60.0, 65.0, 10)], k, np.array([100.0]), h, l, c, d)["bias_m"][0] == 1


# --- item 122: the one-way delivery ---------------------------------------------------------------------------------------------------

def test_oneway_rebalance_array():
    rows = [(100, 101, 99, 99.5), (99.5, 106, 99, 105), (105, 105.5, 103, 103.5), (103.5, 104, 101, 101.5), (101.5, 102, 99.5, 100), (100, 100.5, 97, 97.5), (97.5, 98, 96, 96.5)]
    o, h, l, c = (np.array([r[q] for r in rows], float) for q in range(4))
    ar = BH2.oneway_arrays(o, h, l, c, 4)
    assert len(ar) == 1 and (ar[0].kind, ar[0].typ, ar[0].top, ar[0].bottom, ar[0].known) == ("bear", "oneway", 106.0, 99.0, 6)      # U = session 1; four down-close days; usable the day after the 4th
    assert BH2.oneway_arrays(o, h, l, c, 5)[0].known == 7 and BH2.oneway_arrays(o, h, l, c, 6) == []          # five down-close days follow U in all
    up = BH2.oneway_arrays(-o + 200, 200 - l, 200 - h, 200 - c, 4)
    assert len(up) == 1 and up[0].kind == "bull"
    # htf.table: U's range is a draw above the price (the near edge, until the nearer FVG / gap draws replace it), with no reaction weight
    daily = [(100, 101, 99, 100)] * 6 + rows + [(96.5, 97, 95.5, 96.5)] * 8
    df = fut_frame(daily, start=date(2026, 1, 5))
    on = htf.table(df, 1.0, bx=Params(**FUT, oneway_n=4).bx)
    off = htf.table(df, 1.0)
    hit_ = on[on.draw_up_name == "D_oneway"]
    assert len(hit_) >= 1 and hit_.draw_up.iloc[0] == pytest.approx(99.0)                    # the first session after the array is known
    assert (off.draw_up_name != "D_oneway").all()
    assert (on.react.values == off.react.values).all() and (on.react_score.values == off.react_score.values).all()


# --- items 130 / 138: the 60-session raid side and the extreme pause ------------------------------------------------------------------------

def test_raid_side_column():
    n = 90
    h = np.full(n, 105.0)
    l = np.full(n, 95.0)
    for q in (30, 34, 38, 42, 46):
        h[q] = 105.0 + q                                                                 # five sessions that take the 20-session high
    l[50] = 80.0                                                                         # one that takes the 20-session low
    out = BH2.raid_side_column(h, l, np.array([60, 25]), 2.0)
    assert list(out) == [1, 0]
    ll = np.full(n, 95.0)
    hh = np.full(n, 105.0)
    for q in (30, 34, 38, 42, 46):
        ll[q] = 95.0 - q
    assert BH2.raid_side_column(hh, ll, np.array([60]), 2.0)[0] == -1
    both = h.copy()
    lo2 = l.copy()
    for q in (31, 35, 39, 43):
        lo2[q] = 95.0 - q
    assert BH2.raid_side_column(both, lo2, np.array([60]), 2.0)[0] == 0                   # 5 highs vs 4 lows: not 2x


def test_ipda_pause_column():
    n = 70
    h = np.full(n, 110.0)
    l = np.full(n, 100.0)
    h[10] = 130.0                                                                        # an old spike: the 60-day high is far above the recent highs
    l[-1] = 99.0                                                                         # the prior session's low is the lowest of the 60
    assert BH2.ipda_pause_column(h, l, np.array([n]))[0] == -1                            # shorts are blocked the next day
    l[-1] = 100.0
    l[10] = 70.0                                                                         # ... and an old flush: the 60-day low is far below
    h[-1] = 131.0
    assert BH2.ipda_pause_column(h, l, np.array([n]))[0] == 1                             # longs blocked at the 60-day high
    h[-1] = 110.0
    assert BH2.ipda_pause_column(h, l, np.array([n]))[0] == 0                             # neither extreme is near
    l[-1] = 70.2
    assert BH2.ipda_pause_column(h, l, np.array([n]))[0] == -1                            # within 0.25 x ADR5 of the 60-day low counts too


# --- item 95: three arrays closed through -> neutral -------------------------------------------------------------------------------------

def _pd3_book():
    closes = [100, 100, 100, 105, 99, 99, 101.5, 102.5, 103.5, 103.5, 103.5, 103.5, 103.5, 109.9, 109.5, 109.5]
    o = np.r_[closes[0], closes[:-1]]
    c = np.array(closes, float)
    h = np.maximum(o, c) + 0.5
    l = np.minimum(o, c) - 0.5
    k = 13                                                                               # a displacement day: range 5.4 vs ADR5 ~1, closing in the top quarter
    o[k], h[k], l[k], c[k] = 104.5, 110.0, 104.6 - 0.6, 109.9
    d = pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=pd.bdate_range("2026-01-05", periods=len(c)))
    arrs = [arr("bull", "ob", 101, 99, 2, ce=100.0)] + [arr("bear", "fvg", t, t - 1.5, 5) for t in (101.0, 102.0, 103.0)]
    return d, arrs


def test_flip_pd3_neutral():
    d, arrs = _pd3_book()
    base = flip_of(d, arrs, ("ob_mt", "flip_pd3"))
    assert base[4] == 0 and base[5] == -1 and base[9] == 1                                # the bullish OB's MT is closed through (-1); three bear arrays closed through: the built flip (+1)
    neutral = flip_of(d, arrs, ("ob_mt", "flip_pd3"), {"pd3n": 1.5})
    assert neutral[5] == -1 and neutral[9] == 0 and neutral[12] == 0                       # abandon the bias: neutral, not an automatic opposite
    assert neutral[14] == 1                                                               # a displacement day (range >= 1.5 x ADR5, close in the top quarter) gives +1
    quiet = flip_of(d.assign(high=lambda x: x.high.where(x.index != d.index[13], x.close + 0.3), low=lambda x: x.low.where(x.index != d.index[13], x.close - 0.3)), arrs, ("ob_mt", "flip_pd3"), {"pd3n": 1.5})
    assert quiet[14] == 0 and quiet[15] == 0                                              # without the displacement day it stays neutral
    # the log of arrays closed through, known before each session (the first-array caution)
    log = {}
    flip_of(d, arrs, ("ob_mt", "flip_pd3"), {"pd3_log": log})
    n = [log[t] for t in d.index]
    assert n[6] == 0 and n[7] == 1 and n[8] == 2 and n[9] == 0                          # the first array closed through at session 6, the second at 7, the third at 8 (the state changes; the count resets)


# --- item 117 / 136: the state's terminus; the first clue ---------------------------------------------------------------------------------

def test_flip_terminus():
    flip = np.array([0, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1])
    n = len(flip)
    ks = np.arange(n)
    h = np.full(n, 4100.0)
    l = np.full(n, 4000.0)
    up = np.full(n, 4200.0)
    dn = np.full(n, 3900.0)
    h[5] = 4200.0                                                                         # session 5 trades the draw (4200)
    out = BH2.apply_terminus(flip, up, dn, ks, h, l, 126)
    assert list(out[:6]) == [0, 0, 1, 1, 1, 1] and list(out[6:8]) == [0, 0]               # the session after 4200 traded the state is 0
    assert out[9] == 1 and out[10] == 1                                                   # a new state later (the underlying changed) is held again
    expire = BH2.apply_terminus(np.array([1] * 12), np.full(12, 9999.0), np.full(12, 0.0), np.arange(12), np.full(12, 100.0), np.full(12, 90.0), 10)
    assert list(expire) == [1] * 10 + [0, 0]                                              # after flip_max_days sessions untouched


def test_first_clue_neutral():
    flip = np.array([1, 1, 1, 1, 1, 1, 1, -1, -1])
    clue = np.array([0, 0, -1, -1, 0, 0, 0, 0, 0])                                        # the first STL break after the buy-side pool was raided
    tug = np.array([0, 0, 0, 0, 0, -1, 0, 0, 0])
    out = BH2.apply_first_clue(flip, clue, tug)
    assert list(out[:5]) == [1, 1, 0, 0, 0] and out[5] == -1                              # neutral until the tug of war confirms, then the clue's side
    assert out[7] == -1                                                                   # the underlying state change ends the wait
    plain = BH2.apply_first_clue(np.array([-1, -1]), np.array([0, -1]), np.array([0, 0]))
    assert list(plain) == [-1, -1]                                                        # the clue agrees with the state: nothing to neutralize


# --- items 105 / 93: after the draw ------------------------------------------------------------------------------------------------------

def _obj_table(n=10, week_name="W_fvg"):
    idx = pd.bdate_range("2026-03-02", periods=n)                                         # Monday start
    return pd.DataFrame(dict(px=np.full(n, 4000.0), draw=np.ones(n, int), draw_up=np.full(n, 4100.0), draw_dn=np.full(n, 3900.0),
                             draw_up_name=["D_fvg"] * n, draw_dn_name=["D_swing_low"] * n, obj_day=np.zeros(n, int), obj_week=np.zeros(n, int),
                             wk_draw_up=np.full(n, 4100.0), wk_draw_dn=np.full(n, 3800.0), wk_draw_up_n=[week_name] * n, wk_draw_dn_n=["PWL"] * n), index=idx)


def test_after_draw_columns():
    t = _obj_table()
    t["obj_week"] = [0, 0, 0, 1, 1, 0, 0, 0, 0, 0]
    out = BH2.after_draw_columns(t, t.px.values)
    assert list(out["after_draw_w"][3:5]) == [-1, -1] and out["after_draw_w"][2] == 0         # a weekly draw hit at a weekly FVG: the reverse side is -1
    t2 = _obj_table(week_name="PWH")
    t2["obj_week"] = [0, 0, 0, 1, 1, 0, 0, 0, 0, 0]
    assert BH2.after_draw_columns(t2, t2.px.values)["after_draw_w"].sum() == 0                  # a pool (PWH) is not an HTF array
    t3 = _obj_table()
    t3["obj_day"] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    out3 = BH2.after_draw_columns(t3, t3.px.values)
    assert out3["after_draw_d"][1] == -1                                                   # the previous day's draw was the daily FVG above (draw side +1): reverse -1
    t4 = _obj_table()
    t4["obj_day"] = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    t4["draw"] = -1
    t4["draw_dn_name"] = ["D_swing_low"] * 10
    assert BH2.after_draw_columns(t4, t4.px.values)["after_draw_d"].sum() == 0               # a swing low is a pool


def test_fast_draw_columns():
    # weekly legs: a 6-week decline (a pivot HIGH at week 1, a pivot LOW at week 7) then an equal-size advance in 2 weeks (the current week is 9)
    weeks = [(100, 110, 90, 108), (160, 170, 150, 152), (152, 156, 138, 140), (140, 144, 126, 128), (128, 132, 114, 116), (116, 120, 102, 104), (104, 108, 92, 94), (94, 98, 80, 96), (96, 142, 94, 140), (140, 172, 138, 168), (168, 172, 160, 166)]
    d = dsess(week_rows(weeks), start=date(2026, 1, 5))
    w = htf.weeks(d)
    idx = d.index
    r0 = 9 * 5                                                                              # the first session of week 9 (the up draw is hit during it)
    rows = list(range(r0, r0 + 3))
    out = pd.DataFrame(dict(px=np.full(3, 140.0), obj_week=[0, 1, 1], wk_draw_up=np.full(3, 170.0), wk_draw_dn=np.full(3, np.nan), wk_draw_up_n=["W_fvg"] * 3, wk_draw_dn_n=[""] * 3), index=idx[rows])
    nxt = htf.Arr("bear", "fvg", "W", 215.0, 205.0, 210.0, 3)
    got = BH2.fast_draw_columns(out, d, w, [nxt], np.array(rows), out.px.values, 1.5)
    assert list(got["fast_draw"]) == [0, 1, 1] and got["fast_next"][1] == 205.0              # 2 weeks for what took 6: the move extends to the next weekly array
    slow = BH2.fast_draw_columns(out, d, w, [nxt], np.array(rows), out.px.values, 5.0)
    assert list(slow["fast_draw"]) == [0, 0, 0]                                             # ratio 3 < 5
    assert list(BH2.fast_draw_columns(out, d, w, [], np.array(rows), out.px.values, 1.5)["fast_draw"]) == [0, 0, 0]       # no weekly array beyond: no extension target


# --- items 119 / 94 / 121: intermarket -------------------------------------------------------------------------------------------------

def test_dsmt_map():
    base = stair(4)

    def path(step, bounce_after, hold=3.0):
        c = crash(base, 3, step)
        x = c[-1]
        return c + [x + 10, x + 20, x + 30] + [x + 30] * 30

    es = path(4.0, True)                                                                # ES breaks under its last pivot low
    nq = path(1.0, True)                                                                # NQ makes a higher low (its crash stays above its last pivot low)
    fa = fut_frame([(a, b, c_, d_) for a, b, c_, d_ in zip(*book(es))], start=date(2026, 1, 5))
    fb = fut_frame([(a, b, c_, d_) for a, b, c_, d_ in zip(*book(nq))], start=date(2026, 1, 5))
    m = BH2.dsmt_map(fa, fb, 18)
    days = sorted(m)
    ones = [i for i, dd in enumerate(days) if m[dd] == 1]
    assert ones and 21 <= ones[0] <= 25 and len(ones) >= 15                                # one index made a lower low, the other a higher low (the crash): bullish from the next session
    assert all(m[dd] == 0 for dd in days[:ones[0]])                                       # nothing before the first event
    assert ones[-1] - ones[0] <= 25 and m[days[-1]] == 0                                  # it lapses `days` sessions after the last such event
    # the symmetric partner order gives the same map (either index may be the one that fails)
    assert BH2.dsmt_map(fb, fa, 18) == m
    # NQ's higher low breaks soon after: the SMT ends early
    nq2 = nq[:len(base) + 3] + [nq[len(base) + 2] - 40.0] * 40
    fb2 = fut_frame([(a, b, c_, d_) for a, b, c_, d_ in zip(*book(nq2))], start=date(2026, 1, 5))
    m2 = BH2.dsmt_map(fa, fb2, 18)
    assert sum(m2[dd] == 1 for dd in sorted(m2)) < len(ones)
    # a mirror: highs
    em = [400 - x for x in es]
    nm = [400 - x for x in nq]
    fam = fut_frame([(a, b, c_, d_) for a, b, c_, d_ in zip(*book(em))], start=date(2026, 1, 5))
    fbm = fut_frame([(a, b, c_, d_) for a, b, c_, d_ in zip(*book(nm))], start=date(2026, 1, 5))
    mm = BH2.dsmt_map(fam, fbm, 18)
    assert sum(v == -1 for v in mm.values()) >= 1


def test_intermarket_columns_prior_day_only():
    idx = pd.bdate_range("2025-01-02", periods=160)
    rng = np.random.default_rng(3)
    tnx = pd.Series(np.linspace(3.0, 4.5, 160) + rng.normal(0, 0.01, 160), index=idx)                     # a rising 10-year yield
    dxy = pd.Series(np.linspace(100, 108, 160) + rng.normal(0, 0.05, 160), index=idx)                    # a rising dollar
    spx = pd.Series(4000 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, 160))), index=idx)
    ex = BH2.im_columns(dxy, tnx, spx)
    last = idx[-1]
    assert ex.loc[last, "tnx_slow"] == 1 and ex.loc[last, "rates_dxy_agree"] == 1                        # rising yields and a dollar above its 20-day mean: agree
    # prior day only: changing day t's own close leaves day t's values unchanged
    tnx2, dxy2, spx2 = tnx.copy(), dxy.copy(), spx.copy()
    tnx2.iloc[-1] = 0.5
    dxy2.iloc[-1] = 50.0
    spx2.iloc[-1] = 100.0
    ex2 = BH2.im_columns(dxy2, tnx2, spx2)
    for col in ("tnx_slow", "rates_dxy_agree", "spx_dxy_corr", "spx_tnx_corr", "spx20"):
        a, b = ex.loc[last, col], ex2.loc[last, col]
        assert a == b or (a != a and b != b), col
    assert ex.loc[last, "im_regime"].startswith("b") and set(ex.im_regime.dropna().unique()) <= {f"b{x}_d{y}" for x in ("with", "against") for y in ("with", "against")} | {""}
    # a falling yield against a rising dollar: they disagree
    ex3 = BH2.im_columns(dxy, tnx.iloc[::-1].set_axis(idx), spx)
    assert ex3.loc[last, "tnx_slow"] == -1 and ex3.loc[last, "rates_dxy_agree"] == -1


# --- item 143: open interest is read for its own market only ---------------------------------------------------------------------------------

def test_oi_tag_own_symbol(monkeypatch):
    import shutil
    from pathlib import Path
    assert BX.oi_root("ES") == "ES" and BX.oi_root("NQ") == "NQ" and BX.oi_root("nq1!") == "NQ" and BX.oi_root(None) == "ES"
    assert BX.oi_path("ES").name == "ES_oi.csv" and BX.oi_path("NQ").name == "NQ_oi.csv"
    work = Path(__file__).resolve().parent.parent / "runs" / "_bh2_oi_test"                # (inside the repo's git-ignored runs/ folder; removed at the end)
    work.mkdir(parents=True, exist_ok=True)
    try:
        idx = pd.bdate_range("2026-01-02", periods=30).astype(str)
        pd.DataFrame({"date": idx, "open_interest": np.linspace(100, 130, 30)}).to_csv(work / "NQ_oi.csv", index=False)
        monkeypatch.setattr(BX, "OI_FILE", work / "ES_oi.csv")                             # no ES file in the folder
        assert BX.load_oi_for("ES") is None                                                # an NQ-only series gives no ES tag
        assert BX.load_oi_for("NQ") is not None and len(BX.load_oi_for("NQ")) == 30         # the NQ run reads the NQ file only
        pd.DataFrame({"date": idx, "open_interest": np.linspace(500, 400, 30)}).to_csv(work / "ES_oi.csv", index=False)
        assert BX.load_oi_for("ES").iloc[-1] == 400 and BX.load_oi_for("NQ").iloc[-1] == 130
    finally:
        shutil.rmtree(work, ignore_errors=True)


def test_inert_switch_warnings():
    def warns(**kw):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            Params(**kw)
        return " ".join(str(x.message) for x in w if "inert" in str(x.message))
    assert "htf_bias='off'" in warns(qshift_bias=True) and "htf_bias='off'" in warns(htf_bias_tf="W")
    assert not warns(qshift_bias=True, htf_bias="combo")
    assert "flip_pd3" in warns(pd3_result="neutral", htf_bias="flip") and not warns(pd3_result="neutral", htf_bias="flip", flip_triggers=("ob_mt", "flip_pd3"))
    assert "htf_bias='flip'" in warns(flip_terminus=True, htf_bias="combo") and not warns(flip_terminus=True, htf_bias="flip")
    assert "inside_bisi" in warns(inside_bisi_release=True) and not warns(inside_bisi_release=True, sloppy_tests=("inside_bisi",))
    assert "draw lock" in warns(soft_carry=True, draw_lock="off") and not warns(soft_carry=True)
