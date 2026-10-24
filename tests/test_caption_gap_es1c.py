"""Caption-gap pass, package entries_stops_sizing #1/3, review fixes: engine-level tests for the findings of the chunk's review (the failed propulsion block as an array, the CISD open-level wait, the nested
OTE ranges through the engine, the OB gates on the other OB arrays, mt_break on the pre-break OB, the body-leg OTE band, the OB-in-VI add, the 3m-only scan gap). Hand-made days through run_day; no
platform-specific paths and nothing here needs market data."""
from types import SimpleNamespace

import pandas as pd
import pytest

from mentorship import es1, setups as SM, sm2, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import NY
from test_review_fixes import A_ROWS, day, history
from test_caption_gap_sm1a import sd_of
from test_caption_gap_es1a import CISD_ROWS, D_ROWS, FVG_ROWS, c_run, one, _a_rows


# --- A16-propulsion-block-full: the failed block is an array of the flipped side -------------------------------------------------------------

def test_pb_flip_cand_and_array_cands_for_both_sides():
    p = Params(es_pt=1.0, prop_fail_flip=True)
    rows = [(100.0, 100.5, 99.5, 100.0)] * 4
    # a long failed on a block spanning real 98.0 .. 99.5: the short side gets it as a reclaimed resistance - the first edge the retrace reaches is the LOWER real edge (98.0)
    sd_s = sd_of(rows, sign=-1)
    ctx = SimpleNamespace(pb_flip=dict(sign=-1, lo=98.0, hi=99.5, i=1))
    assert es1.pb_flip_cand(ctx, sd_s, 3, p) == (pytest.approx(-98.0), pytest.approx(-99.5), "pb_flip")           # side space (mirrored): near edge -98, far edge -99.5
    assert es1.pb_flip_cand(ctx, sd_of(rows), 3, p) is None                                                       # the long side is not the flipped side
    assert es1.pb_flip_cand(SimpleNamespace(), sd_s, 3, p) is None and es1.pb_flip_cand(ctx, sd_s, 3, Params()) is None
    # a short failed: the long side gets the block, near edge = its top
    ctx2 = SimpleNamespace(pb_flip=dict(sign=1, lo=101.0, hi=102.0, i=1))
    assert es1.pb_flip_cand(ctx2, sd_of(rows), 3, p) == (pytest.approx(102.0), pytest.approx(101.0), "pb_flip")
    # setups.array_cands offers it (between the sweep extreme and the last close, side space)
    sd_l = sd_of([(103.0, 103.1, 102.9, 103.0)] * 4)
    out = SM.array_cands(ctx2, sd_l, dict(ext_i=0, ext=100.0), 3, p, None)
    assert out == [(pytest.approx(102.0), pytest.approx(101.0), "pb_flip")]
    sd_dn = sd_of([(100.0, 100.1, 99.9, 100.0)] * 4, sign=-1)                                                      # real 100: the block entry (real 98) is below - not a retrace UP into it
    assert SM.array_cands(ctx, sd_dn, dict(ext_i=0, ext=-103.0), 3, p, None) == []
    sd_dn2 = sd_of([(97.0, 97.1, 96.9, 97.0)] * 4, sign=-1)                                                        # real 97: the retrace up to the block's lower edge (98) is ahead
    assert SM.array_cands(ctx, sd_dn2, dict(ext_i=0, ext=-103.0), 3, p, None) == [(pytest.approx(-98.0), pytest.approx(-99.5), "pb_flip")]


def test_prop_fail_flip_overrides_only_side_and_keeps_the_array():
    done, state = {"AM": True}, {"only_side": {"AM": 1}}
    trd = SimpleNamespace(exits=[("t", 99.0, 10, "prop_mt")], side="long", session="AM")
    es1.after_close(None, dict(fill_i=7, es1=dict(prop_zone=(98.0, 99.5))), trd, done, "AM", state, Params(prop_fail_flip=True))
    assert done["AM"] is False and state["only_side"]["AM"] == -1
    assert state["pb_flip"]["AM"] == dict(sign=-1, lo=98.0, hi=99.5, i=7)
    # a short that failed flips to the long side
    d2, s2 = {"PM": True}, {}
    trs = SimpleNamespace(exits=[("t", 101.0, 10, "prop_wick")], side="short", session="PM")
    es1.after_close(None, dict(fill_i=2, es1=dict(prop_zone=(101.0, 102.0))), trs, d2, "PM", s2, Params(prop_fail_flip=True))
    assert s2["only_side"]["PM"] == 1 and s2["pb_flip"]["PM"]["sign"] == 1
    # an exit for another reason does nothing
    d3, s3 = {"AM": True}, {}
    es1.after_close(None, dict(fill_i=7), SimpleNamespace(exits=[("t", 99.0, 10, "stop")], side="long", session="AM"), d3, "AM", s3, Params(prop_fail_flip=True))
    assert d3["AM"] is True and not s3


def test_prop_zone_real_is_low_high_for_both_sides():
    rows = [(100.0, 100.4, 99.6, 99.8), (99.8, 100.6, 99.7, 100.5), (100.5, 101.5, 100.4, 101.4), (101.4, 101.6, 101.0, 101.2)]
    for sign in (1, -1):
        sd = sd_of(rows, sign=sign)
        z = es1.prop_zone_real(sd, dict(ext_i=0, ext=float(sd.l[0])), 1e9, 3, Params(prop_zone="range"))
        assert z is None or z[0] <= z[1]


# --- A12-cisd-open-buy-level: the CISD is not consumed by a bar that closes back under the open -------------------------------------------

def test_cisd_open_waits_for_a_close_above_the_open():
    kw = dict(cisd_ob_entries=True, ob_entry="pre_break", min_risk_pts=0.5, cisd_ob_px="open")
    rows = list(CISD_ROWS)
    rows[4] = (99.7, 100.7, 99.6, 100.3)                                                    # the CISD bar (high 100.7 >= open 100.4 + 1 tick) closes UNDER the open
    rows[5] = (100.3, 100.6, 100.1, 100.5)                                                  # the next bar closes above it
    s0 = dict(sm2.HITS)
    tr = c_run(rows, **kw)
    assert len(tr) == 1 and tr[0].entry_kind == "cisd_ob" and tr[0].entry == pytest.approx(100.4) and tr[0].stop == pytest.approx(98.35)
    assert tr[0].entry_time.hour == 10 and tr[0].entry_time.minute == 0                      # armed on the bar that closed above the open, filled from the next one
    assert sm2.HITS.get("cisd_open_wait", 0) > s0.get("cisd_open_wait", 0)
    # a body close under the run low in between voids the setup (no order)
    void = list(rows)
    void[5] = (100.3, 100.4, 98.0, 98.2)
    assert c_run(void, **kw) == []
    # the bar that closes above the open at once (the built fixture) still arms at once
    assert c_run(CISD_ROWS, **kw)[0].entry_time.minute == 55


def test_cisd_add_waits_for_a_close_above_the_run_open():
    sd = sd_of([(100.0, 100.1, 99.9, 100.0), (100.4, 100.5, 100.0, 100.1), (100.1, 100.2, 99.6, 99.8), (99.8, 100.8, 99.7, 100.3), (100.3, 100.9, 100.2, 100.5)])
    p = Params(es_pt=1.0)
    pos = dict(fill_i=0)
    armed = []
    es1.cisd_add(sd, pos, None, 3, p, lambda px, fl: armed.append((px, fl)))                 # bar 3: high 100.8 >= run open 100.4 + tick, but it closes at 100.3 <= 100.4: kept, not armed
    assert armed == [] and 1 in pos["es1"]["cisd_wait"] and 1 not in pos["es1"]["cisd_used"]
    es1.cisd_add(sd, pos, None, 4, p, lambda px, fl: armed.append((px, fl)))                 # bar 4 closes above the open: the add at 100.4, floor = the run low
    assert armed == [(pytest.approx(100.4), pytest.approx(99.6))] and 1 in pos["es1"]["cisd_used"]
    es1.cisd_add(sd, pos, None, 4, p, lambda px, fl: armed.append((px, fl)))                 # used once
    assert len(armed) == 1


# --- M13-nested-ranges through the engine ---------------------------------------------------------------------------------------------------

NEST = [(100.0, 100.1, 99.4, 99.5), (99.5, 99.6, 98.0, 98.1), (98.1, 99.9, 99.2, 99.8), (99.8, 100.0, 99.0, 99.1), (99.1, 100.6, 99.1, 100.5), (100.5, 102.0, 100.4, 101.9),
        (101.9, 102.0, 100.6, 100.8), (100.8, 101.0, 98.9, 99.0), (99.0, 108.0, 98.95, 107.9)]


def test_ote_nested_children_and_the_parent_through_the_engine():
    # parent L = 98.0 (the sweep extreme), H = 102.0; a child low 99.0 (bar 3) that held; the OTE sweet spot is H - 0.705 x (H - L)
    assert es1.ote_children(sd_of(NEST), dict(ext_i=1, ext=98.0), 5) == [99.0]
    par = c_run(NEST, ote="limit")
    assert len(par) == 1 and par[0].entry == pytest.approx(102.0 - 0.705 * (102.0 - 98.0))                    # the parent's sweet spot 99.18
    nest = c_run(NEST, ote="limit", ote_nested=True)
    assert len(nest) == 1 and nest[0].entry == pytest.approx(102.0 - 0.705 * (102.0 - 99.0))                  # the child's sweet spot 99.885 (the higher, nearest one under the market)
    # the child is traded under (bar 4 prints 98.9, a new 3-candle low): the old child (99.0) is dropped, the NEW child is the base
    rows = NEST[:4] + [(99.1, 100.6, 98.9, 100.5)] + NEST[5:]
    assert es1.ote_children(sd_of(rows), dict(ext_i=1, ext=98.0), 5) == [98.9]
    t2 = c_run(rows, ote="limit", ote_nested=True)
    assert len(t2) == 1 and t2[0].entry == pytest.approx(102.0 - 0.705 * (102.0 - 98.9))
    # the parent's lower third (98 .. 99.33) holds only the parent sweet spot: parent_third rejects the child's 99.81 limit, accepts the parent's 99.18
    assert c_run(rows, ote="limit", ote_nested=True, ote_parent_third=True) == []
    ok = c_run(NEST, ote="limit", ote_parent_third=True)
    assert len(ok) == 1 and ok[0].entry == pytest.approx(99.18)
    # no live child at all: the nested run is the parent run
    assert c_run(D_ROWS, ote="limit", ote_nested=True)[0].entry == pytest.approx(c_run(D_ROWS, ote="limit")[0].entry)


# --- A21-intraday-fib-bodies: the OTE band reads the body leg too ---------------------------------------------------------------------------

def test_leg_fib_body_moves_the_ote_band():
    w = c_run(D_ROWS, ote="limit")
    b = c_run(D_ROWS, ote="limit", leg_fib="body")
    lo, hi = es1.body_leg(sd_of(D_ROWS), dict(ext_i=1), 5)
    assert (lo, hi) == (pytest.approx(98.7), pytest.approx(101.6))
    assert w[0].entry == pytest.approx(99.544) and b[0].entry == pytest.approx(101.6 - 0.705 * (101.6 - 98.7))   # the 70.5 % point of the BODY leg


# --- OB gates on the other OB arrays; mt_break on the pre-break OB ----------------------------------------------------------------------------

def test_ob_gate_applies_to_the_cisd_ob():
    kw = dict(cisd_ob_entries=True, ob_entry="pre_break", min_risk_pts=0.5)
    assert len(c_run(CISD_ROWS, **kw)) == 1
    s0 = dict(sm2.HITS)
    c_run(CISD_ROWS, ob_need_fvg=True, **kw)
    assert sm2.HITS.get("ob_potential", 0) > s0.get("ob_potential", 0)                         # the CISD OB candle is judged against the signature gate (a potential OB until an FVG printed)


def test_ob_gate_applies_to_the_array_ob():
    ctx = SimpleNamespace(tf=5)
    for rows, signed in ((A_ROWS, False), (FVG_ROWS, True)):                                       # the OB candle (bar 1) has no FVG signature in A_ROWS, an FVG starting on it in FVG_ROWS
        sd = sd_of(rows)
        sw = dict(ext_i=1, ext=float(sd.l[1]))
        ob = S._ob_at_low(sd, sw, 7, Params(), None)
        assert ob is not None and es1.ob_fvg_ok(sd, int(ob["k"]), 7) is signed
        got = SM.array_cands(ctx, sd, dict(sw), 7, Params(entry_arrays=("ob",)), None)
        assert any(k == "ob" for _, _, k in got)
        gated = SM.array_cands(ctx, sd, dict(sw), 7, Params(entry_arrays=("ob",), ob_need_fvg=True), None)
        assert any(k == "ob" for _, _, k in gated) is signed


def test_mt_break_governs_the_pre_break_ob_with_a_sweep_stop():
    hist = history()
    df = day(_a_rows(), spike=True)
    k = dict(min_risk_pts=0.5, ob_stop="ext")                                                       # the stop would sit at the sweep extreme: mt_break moves it to the OB MT / far edge
    base = one(df, hist, **k)
    assert len(base) == 1 and base[0].stop < 99.0 and "mt_close" not in base[0].lv_tags
    tr = one(df, hist, mt_break="trade", **k)
    assert len(tr) == 1 and tr[0].stop == pytest.approx(99.15)                                       # any trade under the MT stops (the same level as the ob_stop "mt" run)
    wn = one(df, hist, mt_break="warn", **k)
    assert len(wn) == 1 and "mt_warn" in wn[0].lv_tags and wn[0].mt_warn


# --- A5-ob-in-vi-over-newer-fvg: the sweep precedes the fill -------------------------------------------------------------------------------

def test_ob_in_vi_add_needs_the_sweep_before_the_fill():
    rows = [(100.0, 100.2, 99.9, 100.1), (99.6, 99.9, 99.5, 99.8), (100.2, 100.8, 99.7, 100.6), (100.9, 101.0, 100.1, 100.3), (100.3, 101.2, 100.2, 101.0)]
    sd = sd_of(rows)
    p = Params(es_pt=1.0)
    assert es1.ob_in_vi_add(sd, dict(fill_i=0, ext_i=-1), 4, p) is not None
    assert es1.ob_in_vi_add(sd, dict(fill_i=0, ext_i=0), 4, p) is None                               # the "sweep" is not before the first fill
    assert es1.ob_in_vi_add(sd, dict(fill_i=0, ext_i=3), 4, p) is None


# --- new-multi-tf-scan: a gap visible only on the 3m chart ----------------------------------------------------------------------------------

def test_scan_tfs_finds_a_gap_only_the_3m_chart_shows():
    rows = [(99.0, 99.4, 98.9, 99.3), (99.3, 99.6, 99.2, 99.5), (99.5, 99.8, 99.4, 99.7), (99.7, 100.2, 99.6, 100.1), (100.1, 100.6, 100.0, 100.5), (100.5, 101.0, 100.4, 100.9),
            (100.9, 101.3, 100.8, 101.2), (101.2, 101.6, 101.1, 101.5), (101.5, 102.0, 101.4, 101.9)]
    sd = sd_of(rows)
    idx = pd.date_range("2026-06-23 09:30", periods=9, freq="1min", tz=NY)
    ctx = SimpleNamespace(idx=idx, tf=1)
    sw = dict(ext_i=-1, ext=98.0)
    zs = es1.scan_gaps(ctx, sd, sw, 8, Params(es_pt=1.0, scan_tfs=(1, 3)))
    assert [(round(float(z.bottom), 2), round(float(z.top), 2)) for z in zs] == [(99.8, 100.8)] and sw["_scan_tf"][id(zs[0])] == 3
    assert (99.8, 100.8) not in [(round(float(g.bottom), 2), round(float(g.top), 2)) for g in sd.gaps]       # not a 1m gap
    assert es1.scan_gaps(ctx, sd, dict(ext_i=-1, ext=98.0), 8, Params(es_pt=1.0)) == []
    assert es1.scan_gaps(ctx, sd, dict(ext_i=-1, ext=98.0), 7, Params(es_pt=1.0, scan_tfs=(1, 3))) == []    # the third 3m candle has not closed yet
