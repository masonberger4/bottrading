"""Caption-gap pass, package bias_htf#4/7, review round 1: the fixes (weekly cadence over every weekly column, the tiers outside PDH / PWH, the live-only htf range, the weekly / monthly failed break, the
matrix W / M targets, the first-touch kill vs htf_ob_to_mt, the ladder side fall-through, the BPR through levels.balanced_ranges, the approach-side reach tolerance, the paper history). No market data
is needed; no file outside the repo is written."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh4 as BH4, bh4e as E4, htf, levels as L, paper
from mentorship.strategy import Params

from test_review_fixes import BASE  # noqa: E402
from test_caption_gap_dwc1 import at, FUT  # noqa: E402
from test_caption_gap_bh1 import BR, dsess  # noqa: E402
from test_caption_gap_bh1c import fut_walk  # noqa: E402
from test_caption_gap_bh3b import cx  # noqa: E402
from test_caption_gap_bh4 import build  # noqa: E402
from test_caption_gap_bh4c import BASE_SESSION, END, last_row  # noqa: E402


def P(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


@pytest.fixture(scope="module")
def walk():
    return fut_walk("2024-09-02", "2026-03-27", seed=7, vol=0.9)


# --- item 29: PDH / PWH sit outside the age-tier test ------------------------------------------------------------------------------

def test_pdh_does_not_drop_a_nearer_old_array_from_the_tiers():
    rows = [(4020.0, 4025.0, 4018.0, 4022.0)] * 5 + [(4005.0, 4015.0, 3990.0, 4000.0)] * 5 + [BASE_SESSION] * 55
    rows += [(4000.0, 4010.0, 3997.0, 4000.0), END]                                    # PDH = 4010, farther than the old weekly gap's near edge (4002)
    off, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo"), rows)
    on, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", array_age_tiers=True), rows)
    assert off.draw_up == pytest.approx(4002.0) and off.draw_up_name == "W_fvg"
    assert on.draw_up == pytest.approx(4002.0) and on.draw_up_name == "W_fvg"          # the old array is the only array tier: it stays; the PDH no longer pushes it out


# --- item 168: the htf range anchors only on live arrays -------------------------------------------------------------------------

def test_htf_range_high_never_sits_on_a_dead_array(walk, monkeypatch):
    got = {}
    real = BH4.htf_range_columns

    def spy(bk, ks, px):
        got["bk"], got["ks"] = bk, ks
        got["out"] = real(bk, ks, px)
        return got["out"]
    monkeypatch.setattr(BH4, "htf_range_columns", spy)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        build(Params(**FUT, htf_bias="combo", htf_range_arrays=True, htf_monthly_arrays=True), walk)
    bk, ks, out = got["bk"], got["ks"], got["out"]
    bears = [a for a in bk.arrs_all if a.tf == "W" and a.kind == "bear" and a.typ in ("fvg", "ob", "vi")]
    piv_h = {p_.price for p_ in L.pivots(bk.wh, bk.wlow, 1)[0]}
    checked = bad = 0
    for r, k in enumerate(ks):
        if out["htf_rng_dir"][r] != 1:
            continue
        hi = out["htf_rng_hi"][r]
        done = [q for q in range(len(bk.wl)) if bk.wl[q] <= int(k)]
        match = [a for a in bears if a.bottom == hi and a.known <= int(k)]
        if not match or hi in piv_h:
            continue
        checked += 1
        alive = []
        for a in match:
            cl = bk.wc[[q for q in done if bk.wl[q] > a.known]]
            lvl = a.ce if a.typ == "ob" else a.top
            alive.append(not (len(cl) and cl.max() > lvl))
        bad += not any(alive)
    assert bad == 0


# --- item 181: the weekly / monthly failed break -----------------------------------------------------------------------------------

def test_failed_break_core_works_on_any_timeframe_bars():
    base = [(100.0, 112.0, 98.0, 105.0), (110.0, 112.0, 98.0, 105.0)] * 4
    a = np.array(base + [(105.0, 115.0, 104.0, 108.0), (108.0, 109.0, 100.5, 103.0), (103.0, 104.0, 100.2, 102.0)], float)
    fb = BH4.failed_break_columns(a[:, 0], a[:, 1], a[:, 2], a[:, 3], np.array([len(a)]), 8, look=4)
    assert fb["failed_break"].tolist() == [-1] and fb["fb_target"][0] == 100.0


def test_failed_break_tf_columns_merge_the_highest_timeframe(walk):
    d = htf.sessions(walk)
    bk = BH4.Book(d, htf.weeks(d), [], 1.0, {})
    ks = np.arange(80, len(d), 7)
    only_d = BH4.failed_break_tf_columns(bk, ks, 60, ("D",))
    assert set(only_d) == {"failed_break", "fb_target"}
    allt = BH4.failed_break_tf_columns(bk, ks, 60, ("D", "W", "M"))
    assert {"failed_break_W", "fb_target_W", "failed_break_M", "fb_target_M"} <= set(allt)
    for r in range(len(ks)):
        want = next((allt[f"failed_break_{t}"][r] for t in ("M", "W") if allt[f"failed_break_{t}"][r]), only_d["failed_break"][r])
        assert allt["failed_break"][r] == want


def test_failed_break_weekly_fixture_flags_bearish():
    """A synthetic weekly consolidation poked above and failed: weekly bars from a 5-session-per-week frame."""
    rows = []
    for _ in range(14):
        rows += [(100.0, 112.0, 98.0, 105.0)] * 4 + [(110.0, 112.0, 98.0, 105.0)]
    rows += [(105.0, 115.0, 104.0, 108.0)] * 5 + [(108.0, 109.0, 100.5, 103.0)] * 5 + [(103.0, 104.0, 100.2, 102.0)] * 5
    d = dsess(rows, date(2026, 1, 5))
    bk = BH4.Book(d, htf.weeks(d), [], 1.0, {})
    cols = BH4.failed_break_tf_columns(bk, np.array([len(d)]), 40, ("W",))
    assert cols["failed_break_W"].tolist() == [-1] and cols["fb_target_W"][0] == 100.0
    assert cols["failed_break"].tolist() == [-1]
    assert BH2.HITS["sw_failed_consol_tfs"] > 0


# --- item 162: the weekly / monthly premium arrays join the matrix targets --------------------------------------------------------

def test_matrix_wm_levels_feed_the_target_list():
    p = P(matrix_tfs=("D", "W", "M"), matrix_targets=("mitigation",))
    ctx = cx(p, bias=BR(mx_W_prem=(104.0, 108.0), mx_W_disc=(99.0,), mx_M_prem=(112.0,), mx_M_disc=()))
    i = at(ctx, "09:50")
    up, dn = ctx.sides_map[1], ctx.sides_map[-1]
    assert [v for v, _ in E4.matrix_wm_levels(ctx, up, i, p, 105.0)] == [108.0, 112.0]          # above 105 only
    assert [v for v, _ in E4.matrix_wm_levels(ctx, dn, i, p, -100.0)] == [-99.0]                # a short reads the discount list, in side space
    assert E4.matrix_wm_levels(ctx, up, i, P(matrix_tfs=("D",), matrix_targets=("mitigation",)), 105.0) == []
    assert E4.matrix_wm_levels(ctx, up, i, P(matrix_tfs=("D", "W")), 105.0) == []              # no matrix_targets: tags only
    assert E4.matrix_wm_levels(ctx, up, i, P(matrix_tfs=("D", "M"), matrix_targets=("mitigation",)), 105.0) == [(112.0, "array")]
    with pytest.warns(UserWarning, match="matrix_tfs"):
        P(matrix_tfs=("D", "W"))


# --- item 113 / 172: the first-touch kill does not cancel the MT test ---------------------------------------------------------------

def test_first_touch_kill_is_skipped_with_ob_to_mt(walk):
    base = dict(htf_bias="combo", htf_monthly_arrays=True, htf_lifetime_wm=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        BH2.HITS.clear()
        build(Params(**FUT, **base, htf_ob_to_mt=True), walk)
        killed_mt = BH2.HITS.get("sw_htf_lifetime_wm", 0)
    assert killed_mt == 0                      # with htf_ob_to_mt the own-timeframe MT close test decides: the first-touch kill never fires


# --- item 150: the ladder side falls through a 0 --------------------------------------------------------------------------------------

def test_ladder_dirs_fall_through_zero_columns():
    out = pd.DataFrame({"mwd": [0, 1, 0, -1], "bias_m": [1, 0, 0, 0], "wk_bias": [0, 0, -1, 0], "flip": [0, 0, 0, 1]})
    assert BH4._ladder_dirs(out) == [1, 1, -1, -1]
    assert BH4._ladder_dirs(pd.DataFrame({"x": [1, 2]})) == [0, 0]


# --- item 119: the trapped-trader BPR goes through levels.balanced_ranges -------------------------------------------------------------------

def test_bpr_list_uses_balanced_ranges_and_the_window():
    rng = np.random.default_rng(3)
    n = 400
    c = 100 + np.cumsum(rng.normal(0, 1, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 0.8, n)
    l = np.minimum(o, c) - rng.uniform(0, 0.8, n)
    full = [z for z in L.balanced_ranges(h, l, 0, o, c) if z.i - z.src <= 12]
    win = L.balanced_ranges(h, l, 12, o, c)
    assert [(z.kind, z.top, z.bottom, z.i, z.src) for z in win] == [(z.kind, z.top, z.bottom, z.i, z.src) for z in full]      # the windowed scan = the full scan restricted
    res = BH4.bpr_list(o, h, l, c, 12, large=0.0)
    assert len(res) > 0 and set(res) <= {(z.i, z.kind, z.top, z.bottom) for z in win}
    assert len(BH4.bpr_list(o, h, l, c, 12, large=50.0)) == 0


# --- item 173: the reach tolerance widens the approach side only ------------------------------------------------------------------------------

def test_htf_tag_reach_tolerance_is_one_sided():
    from mentorship import strategy as S
    ctx = type("C", (), {})()
    ctx.hzones = [(L.Zone("bull", 105.0, 100.0, 0), pd.Timestamp("2026-01-01", tz="UTC"), 0)]
    ctx.idx = pd.DatetimeIndex([pd.Timestamp("2026-03-02 10:00", tz="UTC")])
    ctx.tf = 5
    ctx.full_off = 0
    ctx.full_idx = pd.DatetimeIndex([pd.Timestamp("2026-03-02 10:00", tz="UTC")])
    ctx.full_c = np.array([103.0])
    ctx.htf_reach_tol = 3.0
    sd = type("S", (), {"sign": 1})()
    assert S._htf_tag(ctx, sd, 0, 107.5, 0.0) is True            # a turn 2.5 above the zone top (the approach side)
    assert S._htf_tag(ctx, sd, 0, 98.0, 0.0) is False            # 2 below the bottom: the far side is not widened


# --- item 184: the paper path asks for the same history --------------------------------------------------------------------------------------------

def test_paper_history_follows_the_history_switches():
    base = paper.history_days(5)
    assert paper.history_days(5, Params()) == base
    assert paper.history_days(5, Params(htf_history_months=18)) > base
    assert paper.short_history(61, Params(htf_history_months=18)) is not None
    assert paper.short_history(61, Params(pd_grid=True)) is None
    assert B.hist_days(Params(htf_history_months=18)) == 18 * 21 + 1


# --- item 170: every leg_pd premium test carries the waiver ------------------------------------------------------------------------------------------

def test_leg_pd_waiver_is_wired_into_all_three_tests():
    from pathlib import Path
    src = (Path(B.__file__).parent / "strategy.py").read_text(encoding="utf-8")
    assert src.count("p.swing_ignore_eq and _BH4E.leg_pd_exempt(") == 3         # the fill-time test, the arm-time test and the leg_pd_anchor='target' test
