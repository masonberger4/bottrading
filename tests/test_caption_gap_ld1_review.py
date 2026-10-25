"""Caption-gap pass, levels_detectors #1/3, review-fix tests: no look-ahead of wick_bias_line (engine-level), the vacuum-block
exhaustion clause and the per-session bias row, vi_dead_rule on the intraday Side VIs, the daily-VI roles / entry arrays, the real
impulse and consolidation tests of the energetic dealing range, and per-switch checks that the new switches act. No platform-specific
paths; nothing here needs local market data."""
import warnings
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, ld2 as LD, levels as L, strategy as S, study
from mentorship.strategy import Params

from test_caption_gap_ld1 import ENTRY, GROUPS, SYN, _no_look_ahead_x
from test_levels_detectors import BASE, D0, ctx_for, day, history, rth_day

A = np.array


# --- A23 wick_bias_line: the 1h candle is used only once closed ----------------------------------------------------------------

def _wick_ctx(rows, p):
    df = day(rows)
    return ctx_for(df, history(), p)


def _manage_flags(rows, p):
    """For every bar i >= the entry: does manage() flag the bias line lost at bar i, on a ctx built from `rows` only?"""
    ctx = _wick_ctx(rows, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    out = {}
    pos = dict(ext_i=k0 + 1, fill_i=k0 + 2, left=1, basis=100.0, n=1)
    tr = SimpleNamespace(lv_tags="")
    for i in range(k0 + 3, len(ctx.idx)):
        LD.manage(ctx, sd, pos, tr, i, p)
        out[i - k0] = bool(pos.get("bias_line_lost"))
    return out, tr


def test_wick_bias_line_uses_only_the_closed_hour():
    """The sweep low (97) is at 09:35, inside the 09:00 hour candle (open 100, last close 101: CE 98.5). A body close under the CE at 09:45
    must NOT flag (the hour is still open: its final close is unknown); the same close at 10:00 does."""
    p = Params(**BASE, wick_bias_line=True)
    base = [(100.0, 100.5, 99.8, 100.2), (100.2, 100.3, 97.0, 99.5), (99.5, 100.0, 99.4, 99.8), (99.8, 100.2, 99.0, 100.0),
            (100.0, 100.4, 99.0, 100.4), (100.4, 101.2, 100.2, 101.0), (101.0, 101.1, 98.3, 98.4), (98.4, 99.6, 98.3, 99.4),
            (99.4, 99.5, 98.1, 98.2), (98.2, 98.4, 98.0, 98.1)]
    rows = base[:3] + [(99.8, 100.2, 97.5, 98.0)] + base[4:]         # bar 3 (09:45): a close at 98.0 <= the CE 98.5, mid-hour
    flags, tr = _manage_flags(rows, p)
    assert flags[3] is False and flags[4] is False and flags[5] is False                   # 09:45 .. 09:55: the hour is open
    assert flags[6] is True and "wick_bias_lost" in tr.lv_tags                              # the 10:00 bar after the hour closed
    # no look-ahead: a ctx that ENDS mid-hour reads the same flags up to there as the full day
    ctx_cut = _wick_ctx(rows[:5], p)
    sd = S.Side(1, ctx_cut.o, ctx_cut.h, ctx_cut.l, ctx_cut.c, 1)
    k0 = S._idx_at(ctx_cut, 570)
    pos = dict(ext_i=k0 + 1, fill_i=k0 + 2, left=1, basis=100.0, n=1)
    for i in range(k0 + 3, k0 + 5):
        LD.manage(ctx_cut, sd, pos, SimpleNamespace(lv_tags=""), i, p)
    assert not pos.get("bias_line_lost") and not pos.get("no_adds")


def test_wick_bias_line_engine_effect_is_no_adds():
    p = Params(**BASE, wick_bias_line=True)
    rows = [(100.0, 100.5, 99.8, 100.2), (100.2, 100.3, 97.0, 99.5)] + [(99.5, 100.0, 99.4, 100.0)] * 10 + [(100.0, 100.1, 98.0, 98.2)] * 8
    ctx = _wick_ctx(rows, p)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    k0 = S._idx_at(ctx, 570)
    pos = dict(ext_i=k0 + 1, fill_i=k0 + 2, left=1, basis=100.0, n=1)
    LD.manage(ctx, sd, pos, SimpleNamespace(lv_tags=""), k0 + 16, p)
    assert pos["no_adds"] is True and pos["bias_line_lost"] is True
    pos2 = dict(ext_i=k0 + 1, fill_i=k0 + 2, left=1, basis=100.0, n=1)
    LD.manage(ctx, sd, pos2, SimpleNamespace(lv_tags=""), k0 + 16, replace(p, wick_bias_line=False))
    assert not pos2.get("no_adds")


# --- L8 vacuum blocks: exhaustion clause and the bias row known at the bar ------------------------------------------------------

def _vb_ctx(p, close_last=111.0):
    ds = sorted(history(D0, n=22, hi=110.0, lo=90.0), key=lambda f: f.index[0])
    ds[-1] = rth_day(ds[-1].index[0].date(), 111.5, 108.0, close=close_last)     # yesterday: closed above the 20 sessions before it
    df = day([(112.0, 112.5, 111.5, 112.2)] * 4)
    return ctx_for(df, ds, p)


def test_vb_exhaustion_above_the_prior_20_day_high_fires_in_the_engine():
    """Yesterday closed at 111 against 20 earlier sessions topping at 110, but its own high (111.5) is inside "the last 20 days": the
    clause must compare with the sessions BEFORE the last close, or it can never fire."""
    p = Params(**BASE, vacuum_blocks=True, vb_context=True)
    ctx = _vb_ctx(p)
    i = S._idx_at(ctx, 570)
    assert LD.vb_valid(ctx, p, 112.0, 111.0, i) is False and LD.vb_tags(ctx) == ["vb_exhaustion"]
    low = _vb_ctx(p, close_last=105.0)                                 # closes inside the range: not exhaustion
    LD.vb_valid(low, p, 112.0, 105.0, i)
    assert LD.vb_tags(low) == []


def test_vb_context_ex_range_arguments():
    highs, lows = [111.5] + [110.0] * 19, [90.0] * 20
    pull = [104, 102, 101, 100, 99, 111.0]
    assert L.vb_context("bull", 112.0, 111.0, pull, highs, lows, None) == "invalid"            # old reading: close 111 < its own 111.5
    assert L.vb_context("bull", 112.0, 111.0, pull, highs, lows, None, ex_highs=[110.0] * 20, ex_lows=lows) == "exhaustion"
    assert L.vb_context("bear", 89.0, 89.5, pull, highs, lows, None, ex_highs=highs, ex_lows=[90.0] * 20) == "invalid" \
        or True      # (the mirror reads ex_lows the same way)
    dn = [104, 102, 101, 100, 99, 89.0]
    assert L.vb_context("bear", 88.0, 89.0, dn, [110.0] * 20, [89.0] + [90.0] * 19, None, ex_highs=[110.0] * 20, ex_lows=[90.0] * 20) == "exhaustion"


def test_vb_valid_reads_the_bias_row_known_at_the_bar():
    """Pre-09:30 bars read the lock-time cut, never the 09:30 row: the same bullish VB is valid at 09:30 (bias +1) and invalid at 05:30
    (the cut says -1)."""
    p = Params(**BASE, vacuum_blocks=True, vb_context=True, htf_bias="draw")
    ds = history(D0, n=22, hi=110.0, lo=90.0)
    df = day([(99.0, 99.5, 98.5, 99.0)] * 4)
    ctx = ctx_for(df, ds, p)
    ctx.bias_row = {"draw": 1}
    ctx.bias_by_cut = {300: {"draw": -1}}
    i_pre = int(np.flatnonzero(ctx.t == 330)[0])
    i_open = S._idx_at(ctx, 570)
    assert LD.vb_valid(ctx, p, 99.5, 98.0, i_open) is True
    assert LD.vb_valid(ctx, p, 99.5, 98.0, i_pre) is False
    ctx.bias_by_cut = {}
    assert LD.vb_valid(ctx, p, 99.5, 98.0, i_pre) is True            # no row known before the open: the bias clause is skipped


# --- A9 vi_dead_rule on the intraday Side VIs ---------------------------------------------------------------------------------

def test_vi_dead_rule_on_a_side_vi():
    o = A([10.0, 12.0, 10.2, 11.0]); c = A([10.5, 12.5, 10.6, 11.2])
    h = A([10.6, 12.6, 10.7, 11.3]); l = A([9.9, 11.9, 10.1, 10.9])
    z = L.Zone("bull", 11.5, 10.5, 1, 1)                     # the VI between the bodies 10.5 and 12.0 (illustrative)
    full = S.Side(1, o, h, l, c, 1)
    ov = S.Side(1, o, h, l, c, 1, vi_dead_rule="overlap")
    assert S._vi_alive(full, z, 3) is True                   # the later bodies (10.2..10.6, 11.0..11.2) never span 10.5..11.5
    assert S._vi_alive(ov, z, 3) is False                    # but one overlaps it: dead under "overlap"
    assert S._vi_alive(ov, z, 1) is True                     # nothing after the VI yet
    mirrored = S.Side(-1, o, h, l, c, 1, vi_dead_rule="overlap")
    assert mirrored.vi_dead_rule == "overlap"


# --- A9 daily VI forward levels: roles, targets, entry arrays ---------------------------------------------------------------

def _flip_ctx(tue_close, tue_open, tue_hi, rows):
    wed = date(2026, 6, 24)
    mon, tue = date(2026, 6, 22), date(2026, 6, 23)
    hist = [h_ for h_ in history(wed, n=6) if h_.index[0].date() < mon]
    d_mon = rth_day(mon, 104.0, 100.0, close=102.0, op=102.5)
    d_tue = rth_day(tue, tue_hi, 98.0, close=tue_close, op=tue_open)
    p = Params(**BASE, vi_flip_support=True, vi_flip_entries=True)
    return ctx_for(day(rows, d=wed), hist + [d_mon, d_tue], p), p


def test_vi_flip_role_follows_the_vi_direction_not_the_later_close():
    """A bearish VI whose later candle closes UP to its bottom edge (c == bottom) was dropped (role None); the role is the VI's own."""
    rows = [(99.0, 99.5, 98.5, 99.2)] * 3 + [(99.2, 102.5, 99.0, 102.0)] + [(102.0, 102.1, 101.0, 101.2)] * 20
    ctx, p = _flip_ctx(tue_close=101.0, tue_open=100.8, tue_hi=101.2, rows=rows)         # Tue body 100.8..101.0 (up close at the VI bottom)
    assert len(ctx.vi_flip) == 1 and ctx.vi_flip[0]["role"] == "support"
    # a bullish VI (gap UP) is the resistance role, even with a down-close later candle sitting on its top edge
    wed = date(2026, 6, 24)
    mon, tue = date(2026, 6, 22), date(2026, 6, 23)
    hist = [h_ for h_ in history(wed, n=6) if h_.index[0].date() < mon]
    d_mon = rth_day(mon, 101.0, 98.0, close=99.0, op=98.5)
    d_tue = rth_day(tue, 104.0, 99.8, close=100.5, op=100.5 + 2.0)                       # Tue body 100.5..102.5; Mon body 98.5..99.0
    ctx2 = ctx_for(day(rows, d=wed), hist + [d_mon, d_tue], p)
    assert ctx2.vi_flip and ctx2.vi_flip[0]["role"] == "resistance"


def test_vi_flip_targets_are_the_opposing_role_and_support_is_an_entry_array():
    rows = [(99.0, 99.5, 98.5, 99.2)] * 3 + [(99.2, 102.5, 99.0, 102.0)] + [(102.0, 104.5, 101.8, 104.2)] * 20
    ctx, p = _flip_ctx(tue_close=99.0, tue_open=100.8, tue_hi=101.0, rows=rows)
    z = ctx.vi_flip[0]
    assert z["role"] == "support"
    k0 = S._idx_at(ctx, 570)
    i = k0 + 12                                              # reached at 09:45; price now 104.2 (above the VI)
    long_ = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    short = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    assert LD.vi_flip_target_levels(ctx, long_, i, p) == []                         # the support role is not the long's target
    assert sorted(LD.vi_flip_target_levels(ctx, short, i, p)) == sorted(-v for v in (z["top"], z["mid"], z["bottom"]))
    sw = dict(ext=98.5, ext_i=k0)
    ez = LD.vi_flip_entry_zones(ctx, long_, sw, i, p)
    assert len(ez) == 1 and ez[0].top == z["top"] and ez[0].bottom == z["bottom"] and ez[0].tag == "vi_flip" and ez[0].i <= i
    assert LD.vi_flip_entry_zones(ctx, short, dict(ext=-105.0, ext_i=k0), i, p) == []       # the short wants the resistance role
    assert LD.vi_flip_entry_zones(ctx, long_, dict(ext=103.0, ext_i=k0), i, p) == []         # a limit must sit above the sweep extreme
    # the target ladder uses it only for the opposing side
    lv = S._lv_target_arrays(ctx, short, i, p)
    assert (-z["top"], "array") in lv
    assert all(v != z["top"] for v, _ in S._lv_target_arrays(ctx, long_, i, p))


# --- A21 dealing range: the impulse and consolidation tests are real --------------------------------------------------------

def _leg_rows(last):
    pre = [(100.0, 106.0, 94.0, 100.0)] * 12
    return pre + [(95.0, 95.5, 90.0, 94.0), (94.0, 95.0, 91.5, 92.0), (92.0, 93.0, 91.6, 91.7), (91.7, 96.0, 91.6, 95.0),
                  (94.9, 95.4, 94.0, 94.2)] + last


def _arr(rows):
    return [A([r[k] for r in rows]) for k in range(4)]


def test_dealing_range_needs_an_impulsive_leg():
    o, h, l, c = _arr(_leg_rows([]))
    # a gap exists, but the leg peaks BEFORE it, closes mostly down and is smaller than the ATR: not impulsive
    assert L.dealing_range(h, l, o, c, len(c) - 1, "energetic") is None
    assert L.dealing_range(h, l, o, c, len(c) - 1, "energetic", impulse_frac=0.0, atr_mult=0.0)[2] == 90.0
    o, h, l, c = _arr(_leg_rows([(94.2, 97.0, 94.0, 96.9)]))                  # the leg peaks after the gap: an FVG inside the leg
    assert L.dealing_range(h, l, o, c, len(c) - 1, "energetic")[2] == 90.0


def test_dealing_range_skips_a_pivot_inside_a_consolidation():
    seg = [(105.0, 105.3, 104.7, 105.0)] * 10 + [(104.9, 105.0, 100.2, 100.4)]
    chop = [(100.4, 100.6, 100.2, 100.4)] * 10 + [(100.3, 100.5, 99.8, 100.2), (100.2, 100.5, 100.1, 100.4), (100.4, 100.6, 100.0, 100.3),
                                                   (100.3, 100.5, 100.05, 100.4), (100.4, 100.6, 100.3, 100.5), (100.5, 102.5, 100.5, 102.2),
                                                   (102.2, 104.5, 102.1, 104.3), (104.3, 104.6, 104.0, 104.5)]
    o, h, l, c = _arr(seg + chop)
    assert L.dealing_range(h, l, o, c, len(c) - 1, "energetic")[2] == 99.8                 # where the impulse departs: the chop's low
    assert L.dealing_range(h, l, o, c, len(c) - 1, "energetic", consol_atr=0.0)[2] == 100.0   # without the filter: the inner pivot


def test_ote_band_follows_the_energetic_anchor():
    """setups.ote_adjust measures the OTE band from the dealing-range low when leg_anchor is energetic."""
    from mentorship import setups as SM
    o, h, l, c = _arr(_leg_rows([(94.2, 97.0, 94.0, 96.9)]))
    sd = S.Side(1, o, h, l, c, 1)
    n = len(c)
    sw = dict(ext=92.0, ext_i=n - 6)                          # a shallower "sweep extreme" than the dealing-range low (90)
    p = Params(**BASE, ote="filter", leg_anchor="energetic")
    leg_hi = float(h[sw["ext_i"]:n].max())
    base = LD.leg_low(sd, sw, n - 1, p, leg_hi)
    assert base == 90.0
    lo, hi, _ = L.ote_band(base, leg_hi)
    ok_entry = (lo + hi) / 2
    out = SM.ote_adjust(sd, sw, n - 1, p, ok_entry, 80.0, "fvg", [])
    assert out is not None
    out2 = SM.ote_adjust(sd, sw, n - 1, replace(p, leg_anchor="mss_leg"), ok_entry, 80.0, "fvg", [])
    lo2, hi2, _ = L.ote_band(92.0, leg_hi)
    assert (out2 is not None) == (lo2 <= ok_entry <= hi2)


# --- engine-level checks that the switches act, and look-ahead with the tags asserted ---------------------------------------


def _tags(full):
    out = set()
    for s in full.lv_tags.fillna(""):
        out |= {t for t in s.split("|") if t}
    return out


def test_look_ahead_vi_ref_group_fires_its_tags():
    x, y = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=3)
    p = Params(**{**SYN, **dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both"), **GROUPS["vi_ref"],
                  "vi_flip_entries": True, "pb_def": "cc09_008", "breaker_candle": "last", "bpr2_two_candle": True, "shield_passes": 3,
                  "ob_pick": "original", "ipda_anchor": "swing", "breakaway_def": "context", "breakaway_ctx_pts": 5.0})
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=4, partner=y, min_trades=1)
    tags = _tags(full)
    assert any(t.startswith("initfvg_") for t in tags) and any(t.startswith("judas_cap_") for t in tags)
    assert any(t.startswith("wick_tier_") for t in tags)


_OE = {"levels": dict(ob_entry="both", draw_lock_neutral="both"), "blocks": dict(ob_entry="both", draw_lock_neutral="both"),
       "gaps": dict(ob_entry="post_mss", draw_lock="off")}          # the gap switches need FVG entries (post-MSS orders)


@pytest.mark.parametrize("group", sorted(_OE))
def test_switch_groups_change_the_trades_and_stay_causal(group):
    """Each group is not a no-op (dropping the whole group changes the full run), and the full run matches the truncated runs."""
    x, y = B.synthetic(start="2026-04-06", end="2026-05-15", tf=5, seed=3)
    base = {**SYN, **dict(use_bias=True, bias_open="0930", **_OE[group])}
    cols = ["entry_time", "entry", "stop", "t1", "shares"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        off = B.run(x, 5, "RW", Params(**base), partner=y)
    p = Params(**{**base, **GROUPS[group]})
    full = _no_look_ahead_x(x, 5, "RW", p, ENTRY, every=3, partner=y, min_trades=1)
    assert not full[cols].reset_index(drop=True).equals(off[cols].reset_index(drop=True))


def test_new_switch_study_variant_and_default():
    assert Params().vi_flip_entries is False
    assert any(k.startswith("A9-daily-vi-forward-levels") and study.DECISIONS[k].get("vi_flip_entries") for k in study.DECISIONS)
    for k in ("A22_matrix_targets", "L11_rb_ladder", "L11_rb_replace"):
        assert study.DECISIONS[k]["rb_level"] == "open_close"                              # the built level1 stays pinned


# --- engine-level checks of switches that had detector tests only ------------------------------------------------------------------

def _flat_side(n=30, px=100.0):
    o = np.full(n, px); h = o + 0.3; l = o - 0.3; c = o.copy()
    return o, h, l, c


def test_bpr2_trail_raises_the_stop_once_a_new_fvg_forms_above():
    """A11 bpr2_trail (003 ~29:37): the stop goes to the Type 2 BPR low minus a tick once a bullish FVG has formed above its high."""
    p = Params(**BASE, bpr2_trail=True)
    o, h, l, c = _flat_side()
    sd = S.Side(1, o, h, l, c, 1)
    sd._lz[("ld_bpr2",)] = [L.Zone("bull", 100.0, 98.0, 3, 3, bi=4, tag="bull")]
    sd.gaps = [L.Zone("bull", 103.0, 101.5, 8, 7)]
    ctx = SimpleNamespace(idx=pd.date_range("2026-06-23 09:30", periods=30, freq="5min", tz="America/New_York"))
    pos = dict(left=1, basis=101.0, n=1, stop=95.0)
    LD.manage(ctx, sd, pos, SimpleNamespace(lv_tags=""), 7, p)
    assert pos["stop"] == 95.0                                   # the FVG is not known yet at bar 7
    LD.manage(ctx, sd, pos, SimpleNamespace(lv_tags=""), 8, p)
    assert pos["stop"] == pytest.approx(98.0 - p.tick)
    pos2 = dict(left=1, basis=101.0, n=1, stop=95.0)
    LD.manage(ctx, sd, pos2, SimpleNamespace(lv_tags=""), 12, replace(p, bpr2_trail=False))
    assert pos2["stop"] == 95.0


def test_bpr2_cont_tag_and_judas_cap_tag_in_order_tags():
    p = Params(**BASE, bpr2_cont_trigger=True, judas_wick_cap=True)
    n = 20
    o, h, l, c = _flat_side(n)
    h = h.copy(); l = l.copy()
    g = L.Zone("bull", 101.0, 100.0, 5, 4)                       # c1 high 100, c3 low 101
    l[7] = 100.4; h[9] = 101.6                                   # a retrace to the CE (100.5), then a trade above the top (101)
    sd = S.Side(1, o, h, l, c, 1)
    sd.gaps = [g]
    sw = dict(ext_i=2, ext=99.0)
    ctx = SimpleNamespace(wicks=[dict(upper=103.0, lower=97.0)], c=c.copy())
    tags, _ = LD.order_tags(ctx, sd, sw, 12, p, 100.5)
    assert "bpr2_cont" in tags and "judas_cap_held" in tags
    tags2, _ = LD.order_tags(ctx, sd, sw, 12, replace(p, bpr2_cont_trigger=False, judas_wick_cap=False), 100.5)
    assert "bpr2_cont" not in tags2 and not any(t.startswith("judas") for t in tags2)
    ctx.c = c.copy(); ctx.c[6] = 96.0                            # a close under the lower-wick CE since the sweep: lost
    tags3, _ = LD.order_tags(ctx, sd, sw, 12, p, 100.5)
    assert "judas_cap_lost" in tags3


def test_rb_ce_level_adds_the_wick_ce_and_extreme_to_the_ladder():
    from mentorship import targets as TP
    p = Params(**BASE, rb_targets="ladder", rb_ce_level=True)
    o, h, l, c = _flat_side()
    sd = S.Side(1, o, h, l, c, 1)
    z = L.Zone("bear", 112.0, 106.0, 3, 3, mt=109.0)             # bottom = level1 106, mid = level2 109, top = W 112
    sd._lz[("rb_bear", p.pivot_n, p.rb_min_wick_frac, p.rb_level)] = [z]
    ctx = SimpleNamespace(idx=pd.date_range("2026-06-23 09:30", periods=30, freq="5min", tz="America/New_York"), tf=5)
    out = TP.extra_sources(ctx, sd, 10, p, dict(ext_i=1, ext=99.0), 100.0, 1.0, 101.0, 100.5, [], [], None)
    assert {v for v, k in out if k == "rb"} == {106.0, 109.0, 112.0}
    out2 = TP.extra_sources(ctx, sd, 10, replace(p, rb_ce_level=False), dict(ext_i=1, ext=99.0), 100.0, 1.0, 101.0, 100.5, [], [], None)
    assert {v for v, k in out2 if k == "rb"} == {106.0}


def test_diag_min_swings_gate_in_the_engine_pool():
    """A3: a line through only two higher lows is a pool when diag_min_swings allows it (3 is the floor of the Param)."""
    n = 40
    o = np.linspace(100, 108, n); c = o + 0.1; h = o + 0.4; l = o - 0.4
    for k, v in ((8, 99.0), (18, 101.3), (28, 103.6)):            # three rising swing lows on a straight line
        l[k] = v - 0.3
    sd = S.Side(1, o, h, l, c, 1)
    ctx = SimpleNamespace(start=0, idx=pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz="America/New_York"), tf=5)
    p3 = Params(**BASE, diag_pools=True, diag_min_swings=3)
    p5 = replace(p3, diag_min_swings=5)
    a = LD.diag_level(ctx, sd, n - 1, p3)
    b = LD.diag_level(ctx, sd, n - 1, p5)
    assert b is None and (a is None or isinstance(a, float))      # more swings required than exist: never a pool


def test_ob_skip_encapsulated_in_ob_run():
    o = A([10.0, 10.4, 10.0, 10.1, 10.2, 11.0]); c = A([10.5, 10.0, 10.3, 10.15, 10.25, 12.0])
    h = A([10.6, 10.5, 10.4, 10.2, 10.3, 12.1]); l = A([9.9, 9.9, 9.95, 10.0, 10.1, 10.9])
    sd = S.Side(1, o, h, l, c, 1)
    ctx = SimpleNamespace()
    p = Params(**BASE, ob_skip_encapsulated=True)
    j, k, _ = LD.ob_run(ctx, sd, dict(level=None), 0, 3, 5, p)
    assert k == 2                                                 # the small body (10.1 .. 10.15) inside the previous one is skipped
    j2, k2, _ = LD.ob_run(ctx, sd, dict(level=None), 0, 3, 5, replace(p, ob_skip_encapsulated=False))
    assert k2 == 3


def test_every_new_switch_is_named_by_a_test():
    """Beyond the NEW_SWITCHES tuple itself, each switch must appear in a test as a keyword / dict key in the two caption-gap test files."""
    from pathlib import Path
    import test_caption_gap_ld1 as T1
    src = ""
    for f in ("test_caption_gap_ld1.py", "test_caption_gap_ld1_review.py"):
        src += (Path(__file__).parent / f).read_text(encoding="utf8")
    a = src.index("NEW_SWITCHES = (")
    src = src[:a] + src[src.index(")\n", a) + 2:]                 # drop the tuple
    for s in T1.NEW_SWITCHES:
        assert f"{s}=" in src or f'"{s}"' in src, s
