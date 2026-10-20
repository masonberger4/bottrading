"""Review fixes of the caption-gap pass, package levels_detectors #2/3: unit tests and look-ahead (prefix invariance) tests of the
corrected / added detectors. No platform-specific paths; tests needing local market data skip cleanly."""
import warnings
from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, htf, levels as L, strategy as S, study
from mentorship.strategy import Params

from test_caption_gap_ld2 import _STOPRUN, _bk_bars, daily_df, mk

A = np.array


# --- #93 bk_state: a qualified gap that is LATER fully filled is dead --------------------------------------------------------

def test_bk_state_qualified_then_filled_is_dead():
    o, h, l, c = _bk_bars(101.0)                                   # gap [100, 110] at bar 2, retrace bar 3, qualified bar 4
    z = L.fvgs(h, l)[0]
    ext = lambda a, v: np.concatenate([a, A(v, float)])
    h2, l2 = ext(h, [118.0, 117.0, 116.0, 116.0]), ext(l, [112.0, 111.0, 99.0, 100.0])   # bar 7 low 99 < far edge 100
    for i in (4, 5, 6):
        assert L.bk_state(h2, l2, z, i, "any_open") == ("qualified", 4)
    for i in (7, 8):
        assert L.bk_state(h2, l2, z, i, "any_open") == ("dead", 7)
    # ce mode: a later trade at / below the CE (105) also kills it
    o3, h3, l3, c3 = _bk_bars(106.0)
    assert L.bk_state(h3, l3, z, 4, "ce") == ("qualified", 4)
    assert L.bk_state(ext(h3, [118.0]), ext(l3, [104.0]), z, 5, "ce") == ("dead", 5)


# --- #142 stop-run mitigation block with an intermediate pivot high --------------------------------------------------------------

def test_mitigation_stoprun_intermediate_pivot_high():
    rows = _STOPRUN[:7] + [(9.4, 10.5, 9.3, 10.0), (10.0, 10.2, 9.5, 9.8), (9.8, 12.6, 9.7, 12.4)]
    o, h, l, c = mk(rows)
    ph, _ = L.pivots(h, l, 1)
    assert any(p.i == 7 and p.known <= 8 for p in ph)              # the intermediate pivot high formed during the rally back to U
    z = L.mitigation_blocks(o, h, l, c, 1, variant="stoprun")
    assert [(m.top, m.bottom, m.src, m.i) for m in z] == [(12.0, 11.8, 3, 9)]
    # without the intermediate pivot the same block is found at the same break
    z0 = L.mitigation_blocks(*mk(_STOPRUN), 1, variant="stoprun")
    assert [(m.top, m.bottom, m.src) for m in z0] == [(12.0, 11.8, 3)]
    # prefix invariance: the zones known by bar k of a truncated run equal those of the full run
    full = L.mitigation_blocks(o, h, l, c, 1, variant="stoprun")
    for k in range(3, len(rows)):
        part = L.mitigation_blocks(o[:k + 1], h[:k + 1], l[:k + 1], c[:k + 1], 1, variant="stoprun")
        assert [(m.top, m.bottom, m.src, m.i) for m in part] == [(m.top, m.bottom, m.src, m.i) for m in full if m.i <= k]


# --- #68 nwog_cfd_src: monday_0930 on a frame with Sunday bars, per-weekend fall-back ----------------------------------------

def _two_weeks():
    ohlc = [(100 + 2 * k, 104 + 2 * k, 98 + 2 * k, 102 + 2 * k) for k in range(10)]
    return daily_df(ohlc, first=date(2026, 3, 2), tf=15)


def test_nwog_monday_0930_on_sunday_bar_frame():
    df = _two_weeks()
    assert any(ix.weekday() == 6 for ix in df.index)
    auto = htf.opening_gaps(df, 1.0, 1.0, "auto")
    mon = htf.opening_gaps(df, 1.0, 1.0, "monday_0930")
    nw_auto, nw_mon = auto[auto.kind == "nwog"], mon[mon.kind == "nwog"]
    assert len(nw_auto) == 1 and len(nw_mon) == 1 and mon.attrs["nwog_unavailable"] == []
    assert nw_mon.known.iloc[0].weekday() == 0 and (nw_mon.known.iloc[0].hour, nw_mon.known.iloc[0].minute) == (9, 45)   # known when the 09:30 bar closes
    assert nw_mon.close_before.iloc[0] == nw_auto.close_before.iloc[0]
    assert nw_mon.open_after.iloc[0] != nw_auto.open_after.iloc[0] or nw_mon.known.iloc[0] > nw_auto.known.iloc[0]


def test_nwog_sunday_else_monday_per_weekend_fallback():
    df = _two_weeks()
    base = htf.opening_gaps(df, 1.0, 1.0, "sunday_else_monday")
    auto = htf.opening_gaps(df, 1.0, 1.0, "auto")
    assert base[base.kind == "nwog"].known.tolist() == auto[auto.kind == "nwog"].known.tolist()          # Sunday bars present: unchanged
    mon_only = htf.opening_gaps(df, 1.0, 1.0, "monday_0930")
    # drop the Sunday-evening bars: auto flags the weekend unavailable and has no NWOG, the fall-back builds the Monday one
    nos = df[df.index.weekday != 6]
    assert htf.opening_gaps(nos, 1.0, 1.0, "auto").attrs["nwog_unavailable"]
    fb = htf.opening_gaps(nos, 1.0, 1.0, "sunday_else_monday")
    mm = htf.opening_gaps(nos, 1.0, 1.0, "monday_0930")
    assert [r for r in fb.kind if r == "nwog"] == ["nwog"] and fb[fb.kind == "nwog"].known.tolist() == mm[mm.kind == "nwog"].known.tolist()
    assert fb.attrs["nwog_unavailable"] == []
    assert mon_only[mon_only.kind == "nwog"].known.tolist() == mm[mm.kind == "nwog"].known.tolist()


# --- #18 nwog_redelivery selectivity ------------------------------------------------------------------------------------------

def test_nwog_redelivery_review_selectivity():
    from test_caption_gap_ld2 import _nwog_bars
    o, h, l, c = _nwog_bars()
    assert L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25) == (6, 98.4, None)
    # a gap shorter than 2 x pts: every FVG would be "at the edge" - not a candidate
    assert L.nwog_redelivery(o, h, l, c, 0, 99.5, 100.0, 0.25) is None
    # bound in time: the sequence completes at bar 6, a window ending at bar 5 does not see it
    assert L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25, end=5) is None
    # a later full redelivery to the far edge un-rebalances it
    ext = lambda a, v: np.concatenate([a, A(v, float)])
    h2, l2, c2, o2 = ext(h, [100.2]), ext(l, [97.0]), ext(c, [100.0]), ext(o, [97.5])
    assert L.nwog_redelivery(o2, h2, l2, c2, 0, 98.0, 100.0, 0.25, until_end=7) == (6, 98.4, 7)
    assert L.nwog_redelivery(o2, h2, l2, c2, 0, 98.0, 100.0, 0.25, until_end=6) == (6, 98.4, None)
    # an FVG elsewhere on the exit leg first: the leg is not lone, the CE failure is abandoned
    rows = [(98.0, 98.4, 97.8, 98.2), (98.2, 100.1, 98.1, 99.9), (99.9, 99.95, 97.9, 98.0), (98.0, 99.2, 97.95, 98.7),
            (98.7, 98.8, 98.6, 98.65), (98.6, 98.6, 97.9, 98.0), (98.0, 98.4, 97.0, 97.2)]       # bar 6 high 98.4 < low[4] 98.6: FVG [98.4, 98.6], 0.4 from the edge... within 1 pt
    ro, rh, rl, rc = mk(rows)
    assert L.nwog_redelivery(ro, rh, rl, rc, 0, 98.0, 100.0, 0.25, pts=0.2) is None
    # the leg must close outside the gap: an exit FVG at the edge whose bar closes far inside is not an exit
    # (prefix invariance: the result at `end` equals a run on the truncated arrays)
    for e in range(0, 7):
        full = L.nwog_redelivery(o, h, l, c, 0, 98.0, 100.0, 0.25, end=e)
        part = L.nwog_redelivery(o[:e + 1], h[:e + 1], l[:e + 1], c[:e + 1], 0, 98.0, 100.0, 0.25)
        assert full == part


def test_htf_nwog_rebalanced_window_and_until():
    from test_caption_gap_ld2 import _nwog_bars, NY
    fri = pd.date_range("2026-06-19 16:45", periods=2, freq="5min", tz=NY)
    sun = pd.date_range("2026-06-21 18:00", periods=8, freq="5min", tz=NY)
    o, h, l, c = _nwog_bars()
    rows = [(100.5, 100.6, 100.1, 100.2), (100.2, 100.3, 99.9, 100.0)] + list(zip(o, h, l, c)) + [(97.5, 100.3, 97.4, 100.1)]
    a = np.array(rows, float)
    df = pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3], "volume": 1.0}, index=fri.append(sun))
    og = htf.opening_gaps(df)
    reb = htf.nwog_rebalanced(df, og, 0.25)
    when, near, exit_, until = reb[(100.0, 98.0)]
    assert exit_ == 98.4 and until == df.index[-1] + pd.Timedelta(minutes=5) and when < until
    assert htf.nwog_rebalanced(df, og, 0.25, sessions_max=0) == {}                      # the sequence needs bars after the open


# --- prefix invariance of every new detector (no look-ahead): the answer known at bar n-1 does not use later bars --------------------

def _walk(seed, n=260):
    """A seeded OHLC path with trending legs, big candles and gaps (so the displacement / void / FVG detectors fire)."""
    rng = np.random.default_rng(seed)
    drift = np.repeat(rng.normal(0, 1.2, n // 13 + 1), 13)[:n]
    cl = 100 + np.cumsum(drift + rng.normal(0, 0.8, n))
    op = np.concatenate([[100.0], cl[:-1]]) + rng.normal(0, 0.5, n) * (rng.random(n) < 0.35) * 2
    hi = np.maximum(op, cl) + np.abs(rng.normal(0, 0.5, n))
    lo = np.minimum(op, cl) - np.abs(rng.normal(0, 0.5, n))
    return op, hi, lo, cl


def _zkey(z):
    return (z.kind, round(float(z.top), 9), round(float(z.bottom), 9), int(z.i), int(z.src))


ZONE_DETECTORS = {
    "mit_a15": lambda o, h, l, c: L.mitigation_blocks(o, h, l, c, 1),
    "mit_stoprun": lambda o, h, l, c: L.mitigation_blocks(o, h, l, c, 1, variant="stoprun"),
    "mit_legacy": lambda o, h, l, c: L.mitigation_blocks(o, h, l, c, 1, legacy=True),
    "common_gaps_cc": lambda o, h, l, c: L.common_gaps_cc(o, h, l, c),
    "single_pass_ranges": lambda o, h, l, c: L.single_pass_ranges(o, h, l, c, 1.2),
    "balanced_bodies": lambda o, h, l, c: L.balanced_bodies(o, h, l, c, 3, 0.3, 1.2),
    "void_round_trip": lambda o, h, l, c: L.void_round_trip_obs(o, h, l, c, 2),
    "fvgs": lambda o, h, l, c: L.fvgs(h, l),
}


@pytest.mark.parametrize("name", sorted(ZONE_DETECTORS))
def test_zone_detectors_prefix_invariant(name):
    det = ZONE_DETECTORS[name]
    hits = 0
    for seed in range(6):
        o, h, l, c = _walk(seed)
        full = [_zkey(z) for z in det(o, h, l, c)]
        hits += len(full)
        for n in range(30, len(c), 17):
            part = [_zkey(z) for z in det(o[:n], h[:n], l[:n], c[:n])]
            assert part == [k for k in full if k[3] <= n - 1], (name, seed, n)
    assert hits > 0 or name in ("void_round_trip",), name        # the walk must exercise the detector


def test_void_round_trip_prefix_on_designed_bars():
    from test_caption_gap_ld2 import _void_rt_bars
    o, h, l, c = _void_rt_bars()
    full = [_zkey(z) for z in L.void_round_trip_obs(o, h, l, c)]
    assert full
    for n in range(3, len(c) + 1):
        part = [_zkey(z) for z in L.void_round_trip_obs(o[:n], h[:n], l[:n], c[:n])]
        assert part == [k for k in full if k[3] <= n - 1]


@pytest.mark.parametrize("mode", L.IR_DEFS)
def test_immediate_rebalances_prefix_invariant(mode):
    hits = 0
    for seed in range(6):
        o, h, l, c = _walk(seed)
        full = L.immediate_rebalances(o, h, l, c, 0.25, mode, body_mult=1.0)
        hits += len(full)
        for n in range(30, len(c), 17):
            part = L.immediate_rebalances(o[:n], h[:n], l[:n], c[:n], 0.25, mode, body_mult=1.0)
            assert part == [k for k in full if k[0] <= n - 1], (mode, seed, n)
    assert hits > 0, mode


def test_impulse_legs_prefix_invariant():
    hits = 0
    for seed in range(6):
        o, h, l, c = _walk(seed)
        full = L.impulse_legs(h, l, o, c, 1)
        hits += len(full)
        for n in range(40, len(c), 19):
            part = L.impulse_legs(h[:n], l[:n], o[:n], c[:n], 1)
            assert part == [g for g in full if g[5] <= n - 1], (seed, n)
    assert hits > 0


def test_engineered_pools_prefix_invariant():
    hits = 0
    for seed in range(8):
        o, h, l, c = _walk(seed)
        ph, pl = L.pivots(h, l, 2)
        for n in range(40, len(c), 23):
            phn, pln = L.pivots(h[:n], l[:n], 2)
            a = L.engineered_pools(ph, pl, n - 1, 4.0, h)
            b = L.engineered_pools(phn, pln, n - 1, 4.0, h[:n])
            assert a == b, (seed, n)
            hits += len(a)
    assert hits > 0


def test_bk_state_and_ob_anchor_state_prefix_invariant():
    for seed in range(5):
        o, h, l, c = _walk(seed)
        for z in L.fvgs(h, l)[:25]:
            if z.kind != "bull":
                continue
            for depth in ("ce", "any_open"):
                for i in range(z.i, min(len(c), z.i + 60), 7):
                    a = L.bk_state(h, l, z, i, depth)
                    b = L.bk_state(h[:i + 1], l[:i + 1], z, i, depth)
                    assert a == b
        for j in range(5, 120, 11):
            k = j + 2
            for i in (k + 2, k + 6, k + 12):
                assert L.ob_anchor_state(o, h, l, c, j, k, i) == L.ob_anchor_state(o[:i + 1], h[:i + 1], l[:i + 1], c[:i + 1], j, k, i)


def test_nwog_redelivery_prefix_random():
    """(Random walks rarely complete the four-step sequence; the designed bars of test_nwog_redelivery_review_selectivity do.)"""
    for seed in range(40):
        o, h, l, c = _walk(seed, 160)
        near, far = float(o[0]), float(o[0]) + (4.0 if seed % 2 else -4.0)
        full = L.nwog_redelivery(o, h, l, c, 0, near, far, 0.25, 1.0)
        for n in range(10, len(c), 9):
            part = L.nwog_redelivery(o[:n], h[:n], l[:n], c[:n], 0, near, far, 0.25, 1.0)
            if part is not None:
                assert full is not None and full[:2] == part[:2], (seed, n)      # a completed sequence never changes
            if full is not None and full[0] <= n - 1:
                assert part is not None and part[:2] == full[:2]


# --- #85 immediate_rebalances_ex: the bound level and the displacement candle of each definition -----------------------------------

def test_immediate_rebalances_ex_bound_and_displacement():
    from test_caption_gap_ld2 import _IR_DAILY
    o, h, l, c = mk(_IR_DAILY)
    assert L.immediate_rebalances_ex(o, h, l, c, 0.25, "open_space") == [(3, "bull", 100.0, 2)]
    assert [(k, kd) for k, kd, *_ in L.immediate_rebalances_ex(o, h, l, c, 0.25, "open_space")] == L.immediate_rebalances(o, h, l, c, 0.25, "open_space")
    # retrace on d+2: candle d+1 stays above the bound, the displacement candle is d = k-2 (not k-1), the level is the older bounding high
    rows = _IR_DAILY[:3] + [(111.5, 112.0, 108.5, 110.8), (110.0, 111.0, 100.2, 106.0)]
    ex = L.immediate_rebalances_ex(*mk(rows), 0.25, "open_space")
    assert ex == [(4, "bull", 100.0, 2)]
    sd = S.Side(1, *mk(rows), 1, ir_cfg=("open_space", 2.0, 1.5))
    assert sd.ir_info(0.25) == {4: (100.0, 2)} and sd.irs(0.25) == [4]
    # a7 geometry unchanged: bound = the candle two back, d = k-1
    r7 = [(100, 101, 99, 100.5), (100.5, 105, 100, 104.5), (104, 106, 101.0, 105)]
    assert L.immediate_rebalances_ex(*mk(r7), 0.25) == [(2, "bull", 101.0, 1)]


# --- engine-level trace look-ahead: the per-bar pools / targets of a truncated run equal those of the full run ------------------

def _trace_run(df, p, sym="ES", tf=5, meta=None, **kw):
    """B.run with S._targets and S._sell_side recorded: {(kind, day, sign, bar index, scalar args): normalised output, bar open time}.
    Compares what the engine SAW at each closed bar, whether or not a trade followed (so every switch that changes a pool / target is
    covered, not only those that change an entry)."""
    rec = {}
    o_t, o_s = S._targets, S._sell_side
    scal = lambda a: tuple(round(x, 6) if isinstance(x, float) else x for x in a if isinstance(x, (int, float, str, type(None), bool)))

    def wt(ctx, sd, i, *a, **k):
        out = o_t(ctx, sd, i, *a, **k)
        rec[("t", str(ctx.day), int(sd.sign), int(i)) + scal(a) + scal(tuple(k.values()))] = (
            ctx.idx[i], tuple((round(float(v), 6), kd) for v, kd in out))
        return out

    def ws(ctx, sd, session, i=None, *a, **k):
        out = o_s(ctx, sd, session, i, *a, **k)
        if i is not None:
            rec[("s", str(ctx.day), int(sd.sign), int(i), session)] = (ctx.idx[i], tuple(sorted((kk, round(float(v), 6)) for kk, v in out.items())))
        return out

    S._targets, S._sell_side = wt, ws
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tr = B.run(df, tf, sym, p, meta=meta, **kw)
    finally:
        S._targets, S._sell_side = o_t, o_s
    return tr, rec


def _trace_check(df, p, rf, cuts, meta=None):
    """Truncated runs at `cuts`: every (bar, args) the engine saw before the cut equals what the full run saw there."""
    compared = 0
    for cut in cuts:
        part, rp = _trace_run(df[df.index <= cut], p, meta=meta, partial_last=True)
        for key, (t, val) in rp.items():
            if t < cut and key in rf:
                assert rf[key][1] == val, (key, cut)
                compared += 1
    return compared


# --- the bias table: each HTF array switch changes it on real data and none of them looks ahead ----------------------------------

from test_levels_detectors import ES                                                            # noqa: E402

TABLE_SW = {
    "balance_tf_legacy": (dict(balance_tf="legacy"), "2023-05-01", "2023-08-01", True),
    "balance_tf_next_lower": (dict(balance_tf="next_lower"), "2023-05-01", "2023-08-01", True),
    "htf_ob_ltf_drill": (dict(htf_ob_ltf_drill=True), "2023-05-01", "2023-08-01", True),
    "nwog_monday_0930": (dict(nwog_cfd_src="monday_0930"), "2023-05-01", "2023-08-01", True),
    "nwog_sunday_else_monday": (dict(nwog_cfd_src="sunday_else_monday"), "2023-05-01", "2023-08-01", False),     # ES has the Sunday bars: = auto
    "single_pass_draw": (dict(single_pass_draw=True), "2020-01-01", "2020-07-01", True),
    "void_rt_ob": (dict(void_rt_ob=True), "2023-05-01", "2023-08-01", False),                                      # no round trip printed on these bars
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", sorted(TABLE_SW))
def test_table_switch_changes_table_and_does_not_look_ahead(name):
    kw, a, b, must_differ = TABLE_SW[name]
    raw = B.load("ES", 5, source="databento")
    df = raw[(raw.index >= a) & (raw.index < b)]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base = htf.table(df, 1.0)
        full = htf.table(df, 1.0, **kw)
        differs = bool((base.fillna(-9e9).astype(str) != full.fillna(-9e9).astype(str)).any(axis=1).any())
        if must_differ:
            assert differs, f"{name}: the window must exercise the switch"
        days = sorted(full.index)
        for cut_day in (days[len(days) // 3], days[2 * len(days) // 3]):
            cut = pd.Timestamp(cut_day, tz="America/New_York") + pd.Timedelta(hours=11)
            part = htf.table(df[df.index < cut], 1.0, **kw)
            x = full[full.index < cut_day].reset_index()
            y = part[part.index < cut_day].reset_index()
            pd.testing.assert_frame_equal(x, y, check_exact=False, rtol=1e-9)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_nwog_rebalanced_on_es_is_selective_and_causal():
    raw = B.load("ES", 5, source="databento")
    df = raw[(raw.index >= "2023-01-01") & (raw.index < "2023-07-01")]
    og = htf.opening_gaps(df, 1.0)
    reb = htf.nwog_rebalanced(df, og, 0.25)
    n = int((og.kind == "nwog").sum())
    assert n >= 20 and 0 < len(reb) < 0.6 * n                                   # a minority of the weekends (the review found >50% before the fixes)
    for r in reb.values():
        assert r[0] > df.index[0] and (r[3] is None or r[3] > r[0])
    for cut in (df.index[len(df) // 3], df.index[2 * len(df) // 3]):
        d2 = df[df.index < cut]
        part = htf.nwog_rebalanced(d2, htf.opening_gaps(d2, 1.0), 0.25)
        for k, v in reb.items():
            if v[0] <= cut:                                                      # completed before the cut: the truncated run has it
                assert k in part and part[k][:3] == v[:3], (k, cut)
                assert part[k][3] == (v[3] if v[3] is not None and v[3] <= cut else None)
        for k, v in part.items():                                                # ... and nothing the full run does not have
            assert k in reb and reb[k][:3] == v[:3]


# --- every switch of the package: changes the engine at least once on real ES bars, and the engine does not look ahead -------------

from test_caption_gap_ld1 import ENTRY, _no_look_ahead_x                                        # noqa: E402
from test_caption_gap_ld2 import NEW_SWITCHES                                                   # noqa: E402

W1, W2, W3, W4, W5 = (("2023-10-16", "2023-10-30"), ("2022-03-07", "2022-03-21"), ("2025-02-03", "2025-02-17"),
                      ("2019-05-06", "2019-05-20"), ("2021-09-13", "2021-09-27"))
# study variant -> (mode, window, evidence): "A" = no bias filter, draw_lock off; "T" = htf_bias combo; evidence "trades" = the entries /
# stops / targets / tags differ from the same run without the switch, "trace" = the pools / targets the engine saw differ
PINS = {
    "A2-which-old-high": ("A", W1, "trace"),
    "A2-round-number-pool_confluence": ("A", W1, "trades"),
    "A2-round-number-pool_tag_only": ("A", W1, "trades"),
    "A3-engineered-liquidity": ("A", W1, "trace"),
    "L1-rth-session-pools": ("A", W1, "trades"),
    "L3-midnight-session-opening-ranges": ("A", W1, "trades"),
    "L5-partial-redelivery": ("A", ("2023-02-13", "2023-03-20"), "trace"),
    "L5-cfd-nwog-mapping_monday_0930": ("A", W1, "trace"),
    "A2-open-float": ("A", W1, "trace"),
    "A7-immediate-rebalance-definition_open_space": ("A", W1, "trades"),
    "A7-immediate-rebalance-definition_zero_width": ("A", W2, "trades"),
    "A5-twice-traded-not-fvg": ("A", W1, "trades"),                                              # (also the ob_anchor_rule switch of A12-open-vs-wick-gap-criterion)
    "A12-tf-relative-ob": ("T", W5, "trades"),
    "A6-breakaway-depth-qualification": ("A", W1, "trades"),
    "A9-vi-breakaway": ("A", W1, "trades"),
    "A6-gap-hierarchy-common": ("A", W1, "trades"),
    "A5-vi-extended-ce": ("A", W4, "trades"),
    "A11-balanced-range-body-filled": ("A", W2, "trades"),
    "M1-original-consolidation": ("A", W3, "trades"),
    "A21-consolidation-range-def": ("A", W1, "trace"),
    "A3-clean-high": ("A", W4, "trades"),
    "A15-stoprun-variant": ("A", W3, "trades"),
    "M4-failure-swing-no-new-extreme": ("A", W2, "trades"),
    "B21-data-range-fv-eq": ("A", W2, "trades"),
}
TABLE_ONLY = {"A11-htf-gap-own-tf_legacy", "A11-htf-gap-own-tf_next_lower", "A12-void-up-down-ob", "new-single-candle-daily-inefficiency",
              "L5-cfd-nwog-mapping_sunday_else_monday",            # = auto on ES (Sunday bars): the table tests and the unit test cover it
              "A12-open-vs-wick-gap-criterion"}                    # same switch as A5-twice-traded-not-fvg (no ES window changes with the bare variant)


def test_every_ld2_variant_is_pinned_or_table_only():
    assert set(PINS) | TABLE_ONLY == set(study._LD2_DECISIONS)


def _engine_params(mode, kw):
    ex = {"A": dict(use_bias=False, draw_lock="off"), "T": dict(htf_bias="combo", draw_lock="off")}[mode]
    return Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, **{**ex, **kw})


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", sorted(PINS))
def test_variant_changes_the_engine_and_does_not_look_ahead(name):
    mode, (a, b), ev = PINS[name]
    kw = dict(study.DECISIONS[name])
    comp = {k: v for k, v in kw.items() if k not in NEW_SWITCHES}
    if name == "A5-vi-extended-ce":
        comp["fvg_vi_extend_ce"] = False                                                         # (the switch's default is already True)
    raw = B.load("ES", 5, source="databento")
    df = raw[(raw.index >= a) & (raw.index < b)]
    meta = B.load_meta("ES", 5)
    p, q = _engine_params(mode, kw), _engine_params(mode, comp)
    full, rf = _trace_run(df, p, meta=meta)
    base, rb = _trace_run(df, q, meta=meta)
    cols = ENTRY + ["exit_reason"]
    trades_differ = len(full) != len(base) or (len(full) > 0 and not full[cols].reset_index(drop=True).equals(base[cols].reset_index(drop=True)))
    values_differ = any(k in rb and rb[k][1] != v[1] for k, v in rf.items()) or bool(set(rf) ^ set(rb))
    assert (trades_differ if ev == "trades" else values_differ), f"{name}: the window must exercise the switch ({ev})"
    # what the engine saw at every closed bar before a cut is what it sees in the full run
    cuts = [df.index[len(df) // 2], df.index[(3 * len(df)) // 4]]
    assert _trace_check(df, p, rf, cuts, meta) > 0
    # entries / exits (tags included) of runs truncated at entries and exits
    if len(full):
        _no_look_ahead_x(df, 5, "ES", p, ENTRY, every=max(1, len(full) // 2), meta=meta, min_trades=1)
