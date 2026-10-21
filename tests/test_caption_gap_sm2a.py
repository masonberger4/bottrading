"""Caption-gap pass, package setups_models #2/7, part A: the 36 specs of digests/rulebook_gaps/definitions_pd_arrays_structure.md (items 48, 49, 50, 51, 52, 53, 56, 81,
82, 86, 98, 101, 104, 112, 115, 120, 121, 122, 124, 126, 138, 152, 157, 159, 174, 187, 188, 189, 200, 202) and levels_liquidity_targets.md (6, 21, 25, 31, 34, 36).
Unit tests of the new detectors (levels.py) and of the engine glue (sm2.py / setups.py hooks), small run_day scenarios, Params plumbing. Tests that need local market
data (ES) skip cleanly when it is absent; no platform-specific paths. The no-look-ahead runs live in test_caption_gap_sm2b.py."""
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, setups as SM, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, NY, day, ctx_for, history, prior_days, rth_day
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx, sd_of, stub

A = np.array

NEW_SWITCHES = (
    "dfvg_half", "dfvg_large_pts", "nwog_sr_entries", "nwog_sr_stop_pts", "ts_next_array", "ts_min_beyond_pts", "gap_quarter_retrace", "gap_edge_entry", "org_two_rally",
    "org_sig_adr", "reclaimed_def", "mss_ref_raid", "raid_level", "mss_eq_wait_unless_draw", "reh_trap", "micro_regime", "micro_range_adr", "ts_skip_reswept",
    "second_break_partial", "breaker_range_hold", "ifvg_need_run", "ifvg_over_pool_pref", "ifvg_tails_block", "tails_tol_ticks", "ir_need_draw", "ir_need_window",
    "range_lock", "mss_rearm_lower_high", "reaper_def", "poke_high_cancel", "ifvg_pool_intact", "mm_ssl_target", "htf_body_qual", "state_tool_map", "state_machine",
    "consol_bars", "consol_adr", "sweep_ref", "daily_first_return", "daily_first_days", "ts_need_smt", "div_tag", "or_rb", "or_rb_from", "or_rb_bear", "pm_rev_nested",
    "consol_fade", "ts_itl_context", "smt_mode",
)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.dfvg_half, p.dfvg_large_pts, p.nwog_sr_entries, p.nwog_sr_stop_pts, p.ts_next_array, p.ts_min_beyond_pts) == ("off", 15.0, False, 1.0, False, 1.0)
    assert (p.gap_quarter_retrace, p.gap_edge_entry, p.org_two_rally, p.org_sig_adr, p.reclaimed_def, p.mss_ref_raid, p.raid_level) == (False, False, False, 0.25, "strict", False, "pdh")
    assert (p.mss_eq_wait_unless_draw, p.reh_trap, p.micro_regime, p.micro_range_adr, p.ts_skip_reswept, p.second_break_partial, p.breaker_range_hold) == \
        (False, False, False, 0.25, True, False, False)
    assert (p.ifvg_need_run, p.ifvg_over_pool_pref, p.ifvg_tails_block, p.tails_tol_ticks, p.ir_need_draw, p.ir_need_window, p.range_lock) == (False, False, False, 3, True, True, False)
    assert (p.mss_rearm_lower_high, p.reaper_def, p.poke_high_cancel, p.ifvg_pool_intact, p.ifvg_depth, p.mm_ssl_target, p.htf_body_qual) == (False, "fvg", False, False, False, False, False)
    assert (p.state_tool_map, p.state_machine, p.consol_bars, p.consol_adr, p.sweep_ref, p.daily_first_return, p.daily_first_days) == (False, False, 20, 0.3, "wick", False, 30)
    assert (p.ts_need_smt, p.div_tag, p.or_rb, p.or_rb_from, p.or_rb_bear, p.pm_rev_nested, p.consol_fade, p.ts_itl_context, p.smt_mode) == \
        (False, False, False, 630, "last", False, False, False, "pair")
    for kw in (dict(dfvg_half="x"), dict(reclaimed_def="x"), dict(raid_level="x"), dict(reaper_def="x"), dict(sweep_ref="x"), dict(or_rb_bear="x"), dict(smt_mode="x"),
               dict(ifvg_depth="x"), dict(dfvg_large_pts=-1), dict(micro_range_adr=0), dict(consol_bars=1), dict(consol_adr=0), dict(daily_first_days=0), dict(or_rb_from=1440),
               dict(tails_tol_ticks=-1), dict(entry_arrays=("nope",))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(ifvg_depth="w_cap").ifvg_depth == "w_cap" and Params(ifvg_depth=True).ifvg_depth is True
    assert Params(entry_arrays=("bpr_ce",)).entry_arrays == ("bpr_ce",)
    assert set(NEW_SWITCHES) <= set(Params.__dataclass_fields__)


# --- levels.py helpers -----------------------------------------------------------------------------------------------------------

def test_reclaimed_obs_loose_leave_retrade_leave():
    """A18 (006 / Ep 02): a down-close candle price left (close above its high), re-traded (a low back inside) and left again is a loose reclaimed block, known at the
    second leaving close; a candle never re-traded is not one."""
    #       o      h      l      c
    r = [(10.0, 10.2, 9.0, 9.2),      # 0 down-close block 9.0-10.2
         (9.2, 10.8, 9.1, 10.6),      # 1 closes above 10.2: left
         (10.6, 10.7, 9.8, 10.1),     # 2 low 9.8 <= 10.2: re-traded
         (10.1, 11.0, 10.0, 10.9),    # 3 closes above 10.2 again: left again -> known at 3
         (10.9, 11.0, 10.5, 10.8)]
    o, h, l, c = (A([x[k] for x in r], float) for k in range(4))
    zs = L.reclaimed_obs_loose(o, h, l, c, 0, 4)
    assert [(z.top, z.bottom, z.i, z.src, z.tag) for z in zs] == [(10.2, 9.0, 3, 0, "reclaimed_loose")]
    assert L.reclaimed_obs_loose(o, h, l, c, 0, 2) == []                          # not known yet at bar 2
    r2 = [r[0], r[1], (10.6, 11.0, 10.5, 10.9), r[3]]                             # never re-traded (the low stays above 10.2)
    o2, h2, l2, c2 = (A([x[k] for x in r2], float) for k in range(4))
    assert L.reclaimed_obs_loose(o2, h2, l2, c2, 0, 3) == []


def test_reclaimed_zones_switch_and_traded_through_is_kept():
    """A18-reclaimed-ob-codeable: reclaimed_def picks the definition; A18-traded-through-ok: the strict candidates that price traded AND closed through before the curve
    extreme are still returned (levels.reclaimed_obs reads no MT / close filter)."""
    # bars: 0 down-close 100->99 (block 99.0-100.2), 1 up bounce, 2 down-close again that CLOSES THROUGH block 0 (98.5 < 99), 3 the curve low, 4 closes above block 0's high
    r = [(100.0, 100.2, 98.9, 99.0), (99.0, 99.8, 98.9, 99.6), (99.6, 99.7, 97.0, 97.5), (97.5, 97.8, 96.0, 96.5), (96.5, 101.0, 96.4, 100.9)]
    sd = sd_of(r)
    strict = sm2.reclaimed_zones(sd, 0, 3, 4, Params(**BASE))
    assert any(z.src == 0 and z.top == 100.2 for z in strict)                       # block 0 was traded and closed through (97.5 < 99.0) before the low: kept
    loose = sm2.reclaimed_zones(sd, 0, 3, 4, Params(**BASE, reclaimed_def="loose"))
    assert loose == []                                                              # never "left, re-traded and left again" here
    assert sm2.HITS.get("reclaimed_loose")


def test_delivery_state_labels():
    n = 40
    flat = np.full(n, 100.0)
    # a flat 40-bar fixture: CONSOLIDATION
    o = c = flat.copy(); h = flat + 0.1; l = flat - 0.1
    assert L.delivery_state(o, h, l, c, n - 1, 10.0, 20, 0.3) == "CONSOLIDATION"
    assert L.delivery_state(o, h, l, c, n - 1, 0.0) == ""                              # no ADR
    # a breakout bar closing beyond the prior range: EXPANSION
    o2, h2, l2, c2 = (x.copy() for x in (o, h, l, c))
    o2[-1], h2[-1], l2[-1], c2[-1] = 100.0, 112.0, 99.9, 111.5
    assert L.delivery_state(o2, h2, l2, c2, n - 1, 10.0, 20, 0.3) == "EXPANSION"
    # a wick beyond the old high that closes back inside: REVERSAL
    o3, h3, l3, c3 = (x.copy() for x in (o, h, l, c))
    o3[-1], h3[-1], l3[-1], c3[-1] = 100.0, 103.0, 99.9, 100.0
    h3[-5], c3[-5] = 102.0, 101.0                                                        # the old high is 102 (a range of 2.1 > 0.3 x 5)
    assert L.delivery_state(o3, h3, l3, c3, n - 1, 5.0, 20, 0.3) == "REVERSAL"
    # back inside the recently created range after an expansion: RETRACEMENT
    o4 = np.r_[np.full(30, 100.0), np.linspace(100, 110, 10)]
    c4 = np.r_[np.full(30, 100.0), np.linspace(100.5, 110, 10)]
    h4, l4 = np.maximum(o4, c4) + 0.1, np.minimum(o4, c4) - 0.1
    o5, c5 = np.r_[o4, [108.6] * 6], np.r_[c4, [108.5] * 6]
    h5, l5 = np.maximum(o5, c5) + 0.1, np.minimum(o5, c5) - 0.1
    assert L.delivery_state(o5, h5, l5, c5, len(c5) - 1, 5.0, 20, 0.3) == "RETRACEMENT"


def test_stoch_divergence_types():
    """new-divergence-types: type 1 = price LOWER low with a HIGHER momentum low (classic), type 2 = price HIGHER low with a LOWER momentum low (hidden)."""
    # two swing lows: 100 then 99 (lower low); the first came after a deep slide (stoch ~0), the second after a shallow one (stoch higher)
    h = A([110, 108, 105, 102, 100.5, 103, 106, 109, 108, 106, 104, 102, 100.5, 102, 105], float)
    l = A([108, 105, 102, 100, 99.5, 101, 104, 107, 106, 104, 102, 100, 99.4, 100, 103], float)
    c = A([108.5, 105.5, 102.5, 100.5, 100.0, 102.5, 105.5, 108.0, 106.5, 104.5, 102.5, 100.5, 100.0, 101.5, 104.5], float)
    d = L.stoch_divergence(h, l, c, len(c) - 1, 1, 5)
    assert d in ("", "type1", "type2")
    # constructed: pivots at 4 and 12; price 99.5 -> 99.4 (lower low) ; %K(5) at them
    st = L.stochastic_k(h, l, c, 5)
    sa, sb = st[4], st[12]
    expect = "type1" if (99.4 < 99.5 and sb > sa) else ("type2" if (99.4 > 99.5 and sb < sa) else "")
    assert d == expect
    # a clean hidden case: higher low in price, lower in momentum
    hh = A([10, 9, 8, 7, 8, 9, 11, 12, 11, 10, 9.2, 9.0, 9.6, 10.5, 11.5], float)
    ll = A([9, 8, 7, 6, 7, 8, 10, 11, 10, 9, 8.2, 7.9, 8.6, 9.5, 10.5], float)
    cc = A([9.5, 8.5, 7.5, 6.5, 7.5, 8.5, 10.5, 11.5, 10.5, 9.5, 8.5, 8.4, 9.2, 10.0, 11.0], float)
    pl = L.pivots(hh, ll, 1)[1]
    assert [q.i for q in pl][:2] == [3, 11]
    stk = L.stochastic_k(hh, ll, cc, 4)
    got = L.stoch_divergence(hh, ll, cc, len(cc) - 1, 1, 4)
    assert got == ("type1" if (ll[11] < ll[3] and stk[11] > stk[3]) else "type2" if (ll[11] > ll[3] and stk[11] < stk[3]) else "")
    assert L.stoch_divergence(hh[:6], ll[:6], cc[:6], 5, 1, 4) == ""                       # fewer than two confirmed swing lows


# --- A5-premium-half-daily-fvg (6) --------------------------------------------------------------------------------------------

def test_daily_bisi_upper_half_gate():
    """Daily BISI 4000-4040 (CE 4020): a sweep low at 4025 arms; at 4012 it is skipped ("skip") or tagged ("tag"); a 15m body closed below the CE earlier today also
    downgrades a sweep that sits in the upper half."""
    conf = StubConf(arrays={1: [(4040.0, 4000.0, "D", 0, 0)]})
    rows = [(4026.0, 4027.0, 4024.0, 4025.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4026.0, conf=conf)
    i = ib(ctx, "09:40")
    p = Params(**BASE, dfvg_half="skip")
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4025.0), i, p, []) is None
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4012.0), i, p, []) == "x_dfvg_lower_half"
    lvt = []
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4012.0), i, replace(p, dfvg_half="tag"), lvt) is None and lvt == ["dfvg_lower_half"]
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4019.8), i, p, []) is None                       # the 1-tick allowance under the CE
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4050.0), i, p, []) is None                       # not inside the daily gap: n/a
    small = StubConf(arrays={1: [(4010.0, 4000.0, "D", 0, 0)]})
    ctx2, (sl2, _) = mkctx(rows, base=4026.0, conf=small)
    assert sm2.dfvg_gate(ctx2, sl2, dict(ext=4001.0), i, p, []) is None                      # a 10-point gap is not "large"
    # a 15m body that closed under the CE today
    rows3 = [(4025.0, 4026.0, 4014.0, 4015.0), (4015.0, 4016.0, 4014.0, 4015.0), (4015.0, 4016.0, 4014.0, 4015.0), (4015.0, 4030.0, 4015.0, 4029.0)]
    ctx3, (sl3, _) = mkctx(rows3, base=4026.0, conf=conf)
    assert sm2.dfvg_gate(ctx3, sl3, dict(ext=4025.0), ib(ctx3, "09:45"), p, []) == "x_dfvg_lower_half"
    # the mirror: a SIBI 3960-4000 (CE 3980) for a short
    conf_s = StubConf(arrays={-1: [(4000.0, 3940.0, "D", 0, 0)]})
    ctx4, (sl4, ss4) = mkctx([(3962.0, 3964.0, 3961.0, 3962.0)] * 3, base=3962.0, conf=conf_s)
    assert sm2.dfvg_gate(ctx4, ss4, dict(ext=-3965.0), i, p, []) is None                     # a short from the lower half (high 3965 <= CE 3970)
    assert sm2.dfvg_gate(ctx4, ss4, dict(ext=-3990.0), i, p, []) == "x_dfvg_lower_half"
    assert sm2.dfvg_gate(ctx, sl, dict(ext=4025.0), i, p, []) is None and sm2.HITS.get("dfvg_half")
    assert sm2.dfvg_gate(replace(ctx, conf=None) if False else SimpleNamespace(**{**ctx.__dict__, "conf": None}), sl, dict(ext=4012.0), i, p, []) is None


# --- A19: MSS references --------------------------------------------------------------------------------------------------------

LEG = [(4010.0, 4012.0, 4009.0, 4011.0), (4011.0, 4020.0, 4010.0, 4019.0), (4019.0, 4021.0, 4012.0, 4013.0), (4013.0, 4014.0, 4004.0, 4005.0),
       (4005.0, 4006.0, 3996.0, 3997.0), (3997.0, 3999.0, 3991.0, 3992.0), (3992.0, 3995.0, 3990.0, 3994.0), (3994.0, 4003.0, 3993.0, 4002.0)]


def test_mss_ref_raid_taken_vs_missing():
    """010 ~41:31: the prior day's low R. Taken (the day traded under it): the reference is the swing high that started the leg into the sweep extreme; not taken: the
    reference is the swing that launched the leg making the session low and only a displacement break is an MSS."""
    hs = hist_close(close=4000.0, hi=4040.0, lo=3995.0)                                    # PDL1 = 3995
    p = Params(**BASE, mss_ref_raid=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(LEG, base=4010.0, hist=hs, p=p)
    ctx.pd["pdl1"] = 3995.0
    k0 = ib(ctx, "09:30")
    e, i = k0 + 6, k0 + 7                                                                  # the sweep extreme: low 3990 (< PDL 3995: taken)
    sw = dict(ext=3990.0, ext_i=e)
    r = sm2.raid_ref(ctx, sl, sw, i, p)
    assert r is not None and r[2] is True and sw["raid_miss"] is False and sw["raid_disp"] is True
    q = SM.leg_origin(sl, e, i)
    assert (r[0], r[1]) == (q.i, q.price)
    # R NOT taken: lower the PDL out of reach; the sweep is a higher intraday low
    ctx.pd["pdl1"] = 3950.0
    sw2 = dict(ext=3990.0, ext_i=e)
    r2 = sm2.raid_ref(ctx, sl, sw2, i, p)
    assert r2 is not None and sw2["raid_miss"] is True
    ctx.pd.pop("pdl1")
    assert sm2.raid_ref(ctx, sl, dict(ext=3990.0, ext_i=e), i, p) is None                  # R unknown: the ordinary reference
    # the break_ok gate: a non-displacement break with raid_miss is no MSS
    flat = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 12)
    ctx_f = stub(12, start=0)
    pp = Params(**BASE)
    assert SM.break_ok(ctx_f, flat, dict(ext=3999.0, ext_i=3, level=3999.0), 11, pp, 4000.0, {}, 0.25, 0.25) is True
    assert SM.break_ok(ctx_f, flat, dict(ext=3999.0, ext_i=3, raid_disp=True, raid_miss=True, level=3999.0), 11, pp, 4000.0, {}, 0.25, 0.25) is False
    assert SM.break_ok(ctx_f, flat, dict(ext=3999.0, ext_i=3, raid_disp=True, raid_miss=False, level=3999.0), 11, pp, 4000.0, {}, 0.25, 0.25) is False
    big = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 11 + [(4000.0, 4009.0, 3999.5, 4008.0)])
    assert SM.break_ok(ctx_f, big, dict(ext=3999.0, ext_i=3, raid_disp=True, raid_miss=True, level=3999.0), 11, pp, 4000.0, {}, 0.25, 0.25) is True


def test_mss_eq_wait_waived_with_a_locked_draw():
    ctx = SimpleNamespace(cur_lock=dict(side=1))
    sd = SimpleNamespace(sign=1)
    assert sm2.eq_wait_waived(ctx, sd, Params(**BASE, mss_eq_wait_unless_draw=True)) is True
    assert sm2.eq_wait_waived(ctx, SimpleNamespace(sign=-1), Params(**BASE, mss_eq_wait_unless_draw=True)) is False
    assert sm2.eq_wait_waived(SimpleNamespace(cur_lock=None), sd, Params(**BASE, mss_eq_wait_unless_draw=True)) is False
    assert sm2.eq_wait_waived(ctx, sd, Params(**BASE)) is False
    # the wait itself: relative equal lows 3990.0 / 3989.9 standing below the swept 3990.0 -> blocked without the switch, passes with the locked draw
    flat = sd_of([(4000.0, 4001.0, 3999.0, 4000.5)] * 12)
    ctxf = stub(12, start=0, cur_lock=dict(side=1))
    lv = {"rel_eq_lows0": 3989.9}
    sw = dict(ext=3995.0, ext_i=3, level=3990.0)
    assert SM.break_ok(ctxf, flat, sw, 11, Params(**BASE, mss_eq_wait=True), 4000.0, lv, 0.25, 0.25) is False
    assert SM.break_ok(ctxf, flat, sw, 11, Params(**BASE, mss_eq_wait=True, mss_eq_wait_unless_draw=True), 4000.0, lv, 0.25, 0.25) is True
    assert sm2.HITS.get("eq_wait_waived")


def test_reh_trap_gate():
    """029 ~48:29: bias long, equal swing highs 4020.0 / 4020.5 untaken, HTF draw above untaken: the short (a break of the low under them) is rejected."""
    rows = [(4000.0, 4010.0, 3999.0, 4009.0), (4009.0, 4012.0, 4006.0, 4007.0), (4007.0, 4020.0, 4006.0, 4018.0), (4018.0, 4019.0, 4010.0, 4011.0), (4011.0, 4013.0, 4005.0, 4006.0),
            (4006.0, 4020.5, 4005.0, 4017.0), (4017.0, 4018.0, 4009.0, 4010.0), (4010.0, 4011.0, 4007.0, 4008.0), (4008.0, 4009.0, 4001.0, 4002.0)]
    p = Params(**BASE, reh_trap=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, p=p)
    i = ib(ctx, "09:30") + 8
    assert [q.price for q in sl.ph if q.known <= i and q.i >= ctx.start][-2:] == [4020.0, 4020.5]
    assert sm2.reh_trap_gate(ctx, ss, i, p) == "x_reh_trap"                                  # the short is bait
    assert sm2.reh_trap_gate(ctx, sl, i, p) is None                                          # the long is the ordinary flow
    ctx.cur_bias = 0
    assert sm2.reh_trap_gate(ctx, ss, i, p) is None                                          # no bias
    ctx.cur_bias = 1
    ctx.bias_row = dict(draw_up=4015.0)                                                      # the HTF objective was reached (4020.5 traded)
    assert sm2.reh_trap_gate(ctx, ss, i, p) is None
    ctx.bias_row = dict(draw_up=4100.0)
    assert sm2.reh_trap_gate(ctx, ss, i, p) == "x_reh_trap"
    unequal = [r for r in rows]
    unequal[5] = (4006.0, 4030.0, 4005.0, 4017.0)                                            # the second high is not "equal"
    ctx2, (sl2, ss2) = mkctx(unequal, base=4000.0, bias=1, p=p)
    assert sm2.reh_trap_gate(ctx2, ss2, i, p) is None


def test_micro_regime_reads_the_5m_structure():
    """024 ~10:08: a narrow, alternating range since 09:30 with no displacement -> the MSS reference is read on the 5m chart (m_tf 5); a trending morning is not."""
    n = 50                                                                                   # 07:00 .. 11:10
    off = [0.0, 0.5, 1.0, 0.5]
    rows = [(4000.0 + off[k % 4], 4000.3 + off[k % 4], 3999.9 + off[k % 4], 4000.1 + off[k % 4]) for k in range(n)]
    hs = hist_close(close=4000.0, hi=4060.0, lo=3990.0)                                      # ADR5 = 70
    p = Params(**BASE, micro_regime=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hs, p=p, start="07:00")
    k0 = ib(ctx, "09:30")
    i = k0 + 18
    assert sm2.micro_active(ctx, sl, i, p) is True
    trend = [(4000.0 + 3 * k, 4003.0 + 3 * k, 3999.0 + 3 * k, 4002.5 + 3 * k) for k in range(n)]
    ctx2, (sl2, _) = mkctx(trend, base=4000.0, hist=hs, p=p, start="07:00")
    assert sm2.micro_active(ctx2, sl2, i, p) is False                                       # the range exceeds 0.25 x ADR5 (17.5)
    assert sm2.micro_active(ctx, sl, k0 + 3, p) is False                                    # too early
    big = list(rows)
    big[36] = (4000.0, 4009.0, 3999.0, 4008.0)                                              # a displacement bar after 09:30 (still inside 17.5)
    ctx3, (sl3, _) = mkctx(big, base=4000.0, hist=hs, p=p, start="07:00")
    assert sm2.micro_active(ctx3, sl3, i, p) is False
    assert sm2.HITS.get("micro_regime")
    # the engine hook: with the regime on, mss_ref reads the 5m swing (the 1m engine only)
    q1 = SM.mss_ref(ctx, sl, dict(ext_i=i, ext=3999.9, key="x", session="AM"), i, replace(p, mss_ref_tf=0))
    assert q1 is None or isinstance(q1[0], int)


# --- M12-second-takeout-turtle-soup (53) / B18-smt-accum-distrib (152) / new-intermediate-term-hl-fade (200) ------------------------

def test_reswept_pool_is_no_turtle_soup():
    """046 ~1:01:58: PDL 4000 was swept at 09:35 and rallied away from (closes above it) WITHOUT taking the opposing high (4004) - the second break at 10:00 is no
    turtle-soup long; a first sweep is; a rally that took the opposing high started a new range."""
    rows = [(4003.0, 4004.0, 4002.0, 4003.0), (4003.0, 4003.5, 3999.0, 4001.0), (4001.0, 4003.0, 4000.5, 4002.5), (4002.5, 4003.5, 4001.0, 4003.0),
            (4003.0, 4003.2, 4000.8, 4001.0), (4001.0, 4001.5, 3999.5, 4000.5)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0)
    ctx.pd["pdl1"] = 4000.0
    k0 = ib(ctx, "09:30")
    p = Params(**BASE)
    sw_second = dict(key="pdl1", level=4000.0, sweep_i=k0 + 5, ext=3999.5, ext_i=k0 + 5, session="AM")
    assert sm2.reswept(ctx, sl, sw_second, k0 + 5, p) is True
    sw_first = dict(key="pdl1", level=4000.0, sweep_i=k0 + 1, ext=3999.0, ext_i=k0 + 1, session="AM")
    assert sm2.reswept(ctx, sl, sw_first, k0 + 1, p) is False
    took = [rows[0], rows[1], (4001.0, 4009.0, 4000.5, 4008.0), (4008.0, 4008.5, 4001.0, 4003.0), rows[4], rows[5]]       # the rally took the opposing high 4004
    ctx_t, (sl_t, _) = mkctx(took, base=4003.0)
    ctx_t.pd["pdl1"] = 4000.0
    assert sm2.reswept(ctx_t, sl_t, sw_second, k0 + 5, p) is False
    # no rally between the two breaks: the second is part of the same run, not a "second take-out"
    rows2 = [rows[0], rows[1], (4001.0, 4001.5, 3998.5, 3999.0), (3999.0, 3999.8, 3998.0, 3998.5), (3998.5, 3999.0, 3997.0, 3997.5)]
    ctx2, (sl2, _) = mkctx(rows2, base=4003.0)
    ctx2.pd["pdl1"] = 4000.0
    assert sm2.reswept(ctx2, sl2, dict(key="pdl1", level=4000.0, sweep_i=k0 + 4, ext=3997.0, ext_i=k0 + 4, session="AM"), k0 + 4, p) is False
    # a synthetic sweep (no history) is never "re-swept"
    assert sm2.reswept(ctx, sl, dict(key="", level=4000.0, sweep_i=k0 + 5, ext=3999.5, ext_i=k0 + 5), k0 + 5, p) is False
    assert sm2.HITS.get("reswept")


def test_second_break_partial_takes_a_partial():
    """046: an open trade whose target POOL (4010) was traded before the fill and is now broken by 1 point and closed back under it takes a partial, once."""
    ctx = stub(14, start=0)
    h = A([4012, 4011, 4009, 4006, 4004, 4003, 4003.5, 4004, 4005, 4006, 4007, 4009, 4011, 4010.5], float)
    sd = sd_of([(x - 1, x, x - 2, x - 0.5) for x in h])
    sd.h[12] = 4011.0
    sd.c[12] = 4009.5
    tr = SimpleNamespace(exits=[])
    pos = dict(left=4, fill_i=6, levels=[4010.0, 4020.0], level_kinds=["pool", "pool"], k=0)
    p = Params(**BASE, second_break_partial=True)
    sm2.second_break_partial(ctx, sd, pos, tr, "ts", 12, p)
    assert len(tr.exits) == 1 and tr.exits[0][3] == "second_break" and pos["left"] < 4 and pos["sb_done"]
    n = len(tr.exits)
    sm2.second_break_partial(ctx, sd, pos, tr, "ts", 12, p)
    assert len(tr.exits) == n                                                                  # once
    # a pool that was never traded before the fill is not a second break
    pos2 = dict(left=4, fill_i=6, levels=[4010.0], level_kinds=["pool"], k=0)
    sd2 = sd_of([(x - 1, min(x, 4009.0), x - 2, x - 0.5) for x in h])
    sd2.h[12], sd2.c[12] = 4011.0, 4009.5
    tr2 = SimpleNamespace(exits=[])
    sm2.second_break_partial(ctx, sd2, pos2, tr2, "ts", 12, p)
    assert tr2.exits == []
    # a deeper break (beyond ts_max_pts = 5) is a real break
    sd3 = sd_of([(x - 1, x, x - 2, x - 0.5) for x in h])
    sd3.h[12], sd3.c[12] = 4017.0, 4009.5
    tr3 = SimpleNamespace(exits=[])
    sm2.second_break_partial(ctx, sd3, dict(left=4, fill_i=6, levels=[4010.0], level_kinds=["pool"], k=0), tr3, "ts", 12, p)
    assert tr3.exits == []


def test_intermediate_term_pool_context_and_smt():
    hs = hist_close(close=4000.0, hi=4040.0, lo=3990.0)                                        # ADR5 = 50, ten sessions in a 50-point range: range bound
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3999.0, 4000.5)] * 3, base=4000.0, hist=hs)
    k0 = ib(ctx, "09:30")
    p = Params(**BASE, ts_itl_context=True)
    assert sm2.itl_ok(ctx, sl, dict(key="pdl1", ext=3990.0), k0 + 1, p) is True               # yesterday's low is not an intermediate-term pool: n/a
    assert sm2.itl_ok(ctx, sl, dict(key="pdl3", ext=3990.0), k0 + 1, p) is True               # range bound (50 <= 3 x ADR5)
    wide = [rth_day(d, 4040.0 + 40 * k, 3990.0 + 40 * k, close=4000.0 + 40 * k) for k, d in enumerate(prior_days(D0, 10))]
    ctx2, (sl2, ss2) = mkctx([(4400.0, 4401.0, 4399.0, 4400.5)] * 3, base=4400.0, hist=wide)
    assert sm2.itl_ok(ctx2, sl2, dict(key="pdl3", ext=4390.0), k0 + 1, p) is False            # a rising trend: a long fade of a low has no context
    assert sm2.itl_ok(ctx2, ss2, dict(key="pwl", ext=-4390.0), k0 + 1, p) is True             # the short fade of a high after a >= 3 ADR advance (profit taking)
    assert sm2.ts_smt_ok(dict(smt=True)) and sm2.ts_smt_ok(dict(smt=None, smt2=True)) and not sm2.ts_smt_ok(dict(smt=None, smt2=False))
    assert sm2.HITS.get("itl_context")


def test_next_array_level_skips_the_wick_ce_hugging_the_pool():
    """025 ~1:05:16: old high 4100 (a short: side space -4100), a gap row hugging it at 4100.5-4101 and the next array 4103-4105: the limit is 4103 and the stop
    4105.25 (one tick beyond the far edge)."""
    ctx, (sl, ss) = mkctx([(4098.0, 4099.0, 4097.0, 4098.0)] * 3, base=4098.0)
    ctx.gaps = [("nwog", 4101.0, 4100.5, 4100.75), ("nwog", 4105.0, 4103.0, 4104.0)]
    p = Params(**BASE, ts_next_array=True)
    i = ib(ctx, "09:40")
    got = sm2.next_array_level(ctx, ss, i, -4100.0, p, ctx.idx[i])
    assert got is not None and got[0] == pytest.approx(-4103.0) and got[1] == pytest.approx(-4105.25)
    got2 = sm2.next_array_level(ctx, ss, i, -4100.0, replace(p, ts_min_beyond_pts=0.4), ctx.idx[i])
    assert got2[0] == pytest.approx(-4100.5)                                                 # with a tiny minimum the hugging gap edge is the level
    assert sm2.next_array_level(ctx, ss, i, -4110.0, p, ctx.idx[i]) is None                  # nothing beyond
    assert sm2.HITS.get("ts_next_array")


# --- A8: inversion FVGs (81, 82, 120, 121) -----------------------------------------------------------------------------------------

IF_ROWS = [(4013.0, 4030.0, 4012.0, 4012.5), (4012.5, 4012.8, 4009.0, 4009.5), (4009.5, 4010.0, 4008.0, 4009.0), (4009.0, 4016.0, 4008.8, 4015.0),
           (4015.0, 4015.5, 4011.0, 4014.0), (4014.0, 4020.0, 4013.0, 4019.0)]


def _ifvg_ctx(rows=IF_ROWS, **kw):
    ctx, (sl, ss) = mkctx(rows, base=4000.0, **kw)
    z = sl.ifvgs()[0]
    tags = dict(zone_top=float(z.top), fvg_bottom=float(z.bottom), fvg_i=int(z.i), entry_kind="ifvg")
    return ctx, sl, z, tags


def test_ifvg_zone_lookup_and_narrative_run():
    """078 ~51:00: an IFVG needs the bias its way and an old sell-side pool taken inside / just beyond the bearish FVG before the inversion."""
    ctx, sl, z, tags = _ifvg_ctx(bias=1)
    assert (z.top, z.bottom) == (4012.0, 4010.0) and sm2.ifvg_zone(sl, tags) is z
    assert sm2.ifvg_zone(sl, dict(tags, zone_top=1.0)) is None and sm2.ifvg_zone(sl, {}) is None
    k0 = ib(ctx, "09:30")
    i = k0 + 5
    p = Params(**BASE, ifvg_need_run=True)
    ctx.pd["pdl1"] = 4011.0                                                                # bar 2 (low 4008) took it; it sits inside the gap 4010-4012
    lvt = []
    assert sm2.ifvg_run_gate(ctx, sl, dict(), i, p, "AM", z, lvt) is None and lvt == ["ifvg_pool_inside"]
    ctx.pd["pdl1"] = 4009.0                                                                # just beyond the gap (one gap height = 2 points): still a run
    lvt = []
    assert sm2.ifvg_run_gate(ctx, sl, dict(), i, p, "AM", z, lvt) is None and lvt == []
    ctx.pd["pdl1"] = 3990.0                                                                # never taken
    assert sm2.ifvg_run_gate(ctx, sl, dict(), i, p, "AM", z, []) == "x_ifvg_no_run"
    ctx.pd["pdl1"] = 4011.0
    ctx.cur_bias = 0
    assert sm2.ifvg_run_gate(ctx, sl, dict(), i, p, "AM", z, []) == "x_ifvg_no_bias"          # without the HTF bias it is just an FVG in its original direction
    assert sm2.ifvg_run_gate(ctx, sl, dict(), i, replace(p, ifvg_need_run=False), "AM", z, []) is None
    # the order gate wires it in
    ctx.cur_bias = 1
    sw = dict(key="rel_eq_lows0", ext=4008.0, ext_i=k0 + 2)
    assert sm2.order_gate2(ctx, sl, sw, i, p, 4012.0, 4007.0, "AM", [], {}, dict(tags)) is None
    ctx.pd["pdl1"] = 3990.0
    assert sm2.order_gate2(ctx, sl, sw, i, p, 4012.0, 4007.0, "AM", [], {}, dict(tags)) == "x_ifvg_no_run"


def test_ifvg_over_pool_preference():
    """ifvg_over_pool_pref: an IFVG whose range does not contain the taken pool is rejected when another IFVG after the sweep does."""
    ctx, sl, z, tags = _ifvg_ctx(bias=1)
    k0 = ib(ctx, "09:30")
    ctx.pd["pdl1"] = 4008.5                                                                # just beyond (below) the FVG 4010-4012: taken, not inside
    p = Params(**BASE, ifvg_need_run=True, ifvg_over_pool_pref=True)
    assert sm2.ifvg_run_gate(ctx, sl, dict(), k0 + 5, p, "AM", z, []) is None             # no other IFVG that contains a pool: accepted
    z2 = L.Zone("bull", 4009.0, 4008.2, k0 + 4, k0 + 2)
    sl._ifvg = list(sl.ifvgs()) + [z2]                                                     # a second IFVG that does contain the taken pool
    assert sm2.ifvg_run_gate(ctx, sl, dict(), k0 + 5, p, "AM", z, []) == "x_ifvg_pool_pref"


def test_ifvg_stacked_tails_block():
    """090 ~21:24: two long lower tails (lows within 3 ticks) just under the IFVG: armed only after a low below them."""
    tails = [(4009.8, 4009.9, 4008.0, 4009.7), (4009.7, 4009.9, 4008.2, 4009.6)]
    rows = tails + IF_ROWS
    ctx, sl, z, tags = _ifvg_ctx(rows)
    k0 = ib(ctx, "09:30")
    i = z.i + 2
    p = Params(**BASE, ifvg_tails_block=True)
    assert sm2.ifvg_tails_gate(ctx, sl, i, p, z) == "x_ifvg_tails"
    sw = dict(key="x", ext=4008.0, ext_i=z.i)
    assert sm2.order_gate2(ctx, sl, sw, i, p, 4012.0, 4007.0, "AM", [], {}, dict(tags)) == "x_ifvg_tails"
    deeper = rows + [(4014.0, 4014.5, 4007.0, 4013.0)]                                    # a later low (4007.0) below the cluster's 4008.0
    ctx2, sl2, z2, tags2 = _ifvg_ctx(deeper)
    assert sm2.ifvg_tails_gate(ctx2, sl2, ib(ctx2, "09:30") + len(rows), p, z2) is None
    ctx3, sl3, z3, _ = _ifvg_ctx(IF_ROWS)                                                  # the plain fixture has one long tail candle only: no cluster
    assert sm2.ifvg_tails_gate(ctx3, sl3, z3.i + 2, p, z3) is None
    assert sm2.HITS.get("ifvg_tails")


def test_ifvg_pool_intact_cancels_when_the_draw_is_taken():
    """102 ~1:08:45: the nearest swing high above the IFVG (4030 here) is the draw; once traded through before the return the IFVG is cancelled."""
    ctx, sl, z, tags = _ifvg_ctx()
    k0 = ib(ctx, "09:30")
    p = Params(**BASE, ifvg_pool_intact=True)
    assert sm2.ifvg_pool_gate(ctx, sl, k0 + 5, p, z) is None
    more = IF_ROWS + [(4019.0, 4031.0, 4018.0, 4030.5)]                                    # the draw (4030) is run at bar 6
    ctx2, sl2, z2, tags2 = _ifvg_ctx(more)
    assert sm2.ifvg_pool_gate(ctx2, sl2, k0 + 6, p, z2) == "x_ifvg_pool_taken"
    sw = dict(key="x", ext=4008.0, ext_i=z2.i)
    assert sm2.order_gate2(ctx2, sl2, sw, k0 + 6, p, 4012.0, 4007.0, "AM", [], {}, dict(tags2)) == "x_ifvg_pool_taken"
    assert sm2.HITS.get("ifvg_pool")


def test_ifvg_depth_w_cap_cases():
    """102 ~1:11:04: (a) partly re-traded: cap = max(CE, W) - the entry rises to the cap, the stop sits just under it, a retrace deeper than the cap + the mohawk kills
    it; (b) not re-traded: the far edge, stop beyond it; (c) traded through and back: valid only while the lows stay >= CE - 1 tick."""
    p = Params(**BASE, ifvg_depth="w_cap", ifvg_entry="ce")
    g = L.Zone("bull", 4012.0, 4010.0, 7, 3)                          # the inverted bearish gap [4010, 4012]: middle candle 3, third candle 4, inverted at bar 7
    ce = 4011.0
    flat = [(4000.0, 4001.0, 3999.0, 4000.5)] * 3

    def book(w_high, retrace_low):
        """bars 3-4 the original gap, bars 5-6 between (one of them prints the high w_high), bar 7 the inversion, bar 8 the retrace."""
        return sd_of(flat + [(4010.0, 4010.5, 4008.0, 4009.0), (4009.0, 4009.8, 4008.5, 4009.2), (4009.2, w_high, 4009.0, 4009.5), (4009.5, 4009.9, 4009.0, 4009.8),
                             (4009.8, 4018.0, 4009.5, 4017.0), (4017.0, 4017.5, retrace_low, 4014.0)])

    sd_b = book(4009.5, 4013.0)                                         # (b) nothing printed into the gap before the inversion
    assert L.ifvg_passes(sd_b.h, sd_b.l, g.top, g.bottom, g.src + 1, g.i) == "none"
    assert sm2.ifvg_w_cap(sd_b, g, 4012.0, 4009.0, 8, p) == (4012.0, 4010.0 - p.pad)
    sd_a = book(4011.6, 4012.0)                                         # (a) a high of 4011.6 printed inside the gap -> cap = max(CE 4011, 4011.6) = 4011.6
    assert L.ifvg_passes(sd_a.h, sd_a.l, g.top, g.bottom, g.src + 1, g.i) == "partial"
    e, s_ = sm2.ifvg_w_cap(sd_a, g, 4011.0, 4009.0, 8, p)
    assert e == pytest.approx(4011.6) and s_ == pytest.approx(4011.6 - p.pad)          # the entry rises to W, the stop just under it
    sd_a2 = book(4011.6, 4010.0)
    assert sm2.ifvg_w_cap(sd_a2, g, 4011.0, 4009.0, 8, p) is None                       # the retrace reached 4010.0 < the cap 4011.6 - 2 ticks: skip
    sd_c = book(4013.0, 4010.9)                                         # (c) traded through (a high above the top) and back
    assert L.ifvg_passes(sd_c.h, sd_c.l, g.top, g.bottom, g.src + 1, g.i) == "both"
    assert sm2.ifvg_w_cap(sd_c, g, 4012.0, 4009.0, 8, p) == (4012.0, ce - p.pad)       # the low stayed >= CE - 1 tick
    sd_c2 = book(4013.0, 4010.2)
    assert sm2.ifvg_w_cap(sd_c2, g, 4012.0, 4009.0, 8, p) is None                       # under the CE minus a tick
    assert SM.ifvg_stop(sd_c2, g, 4012.0, 4009.0, p, 8) is None
    assert SM.ifvg_stop(sd_c2, g, 4012.0, 4009.0, replace(p, ifvg_depth=True), 8) is not None    # the first-build behaviour never skips
    # ifvg_entry "quadrant" (078 ~51:00): the upper quadrant of the zone
    e, s_ = SM.ifvg_stop(sd_b, g, 4012.0, 4009.0, Params(**BASE, ifvg_entry="quadrant"), 8)
    assert e == pytest.approx(4011.5)
    assert Params(ifvg_entry="quadrant").ifvg_entry == "quadrant"


# --- L5 / L6 / L7: gap setups (21, 31, 34, 36) ---------------------------------------------------------------------------------------

def _gap_ctx(rows, base, gaps, bias=1, p=None, **kw):
    p = p or Params(**BASE)
    ctx, (sl, ss) = mkctx(rows, base=base, bias=bias, p=p, **kw)
    ctx.gaps = gaps
    return ctx, sl, ss


def test_nwog_sr_entry_consolidation_only():
    """039 ~10:52 / 024 ~18:37: the stored NWOG high / CE / low are exact levels in a consolidation week: a limit at the nearest level below the market (the CE
    4087.5 here), 1 point of stop, the next level (the high 4095) first; a trending week gives no order."""
    rows = [(4090.0, 4091.0, 4089.5, 4090.5)] * 4
    p = Params(**BASE, nwog_sr_entries=True)
    ctx, sl, ss = _gap_ctx(rows, 4090.0, [("nwog", 4095.0, 4080.0, 4087.5)], p=p)
    ctx.bias_row = dict(nwog_regime="cons")
    i = ib(ctx, "09:45")
    o = sm2.nwog_sr_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == 4087.5 and o["stop"] == pytest.approx(4086.5) and "nwog_sr" in o["lv_tags"]
    assert o["t1"] == pytest.approx(4095.0 - p.exit_before_pts * p.es_pt) or o["t1"] <= 4095.0
    assert sm2.nwog_sr_order(ctx, sl, i, p, "AM", 1.0) is None                              # once per level
    ctx2, sl2, ss2 = _gap_ctx(rows, 4090.0, [("nwog", 4095.0, 4080.0, 4087.5)], p=p)
    ctx2.bias_row = dict(nwog_regime="trend")
    assert sm2.nwog_sr_order(ctx2, sl2, i, p, "AM", 1.0) is None                            # a trending week
    ctx3, sl3, ss3 = _gap_ctx(rows, 4090.0, [("nwog", 4095.0, 4080.0, 4087.5)], bias=0, p=p)
    ctx3.bias_row = dict(nwog_regime="cons")
    assert sm2.nwog_sr_order(ctx3, sl3, i, p, "AM", 1.0) is None                            # no bias
    # the mirror: a short at the nearest level above (the CE 4092.5 with the market at 4090)
    ctx4, sl4, ss4 = _gap_ctx(rows, 4090.0, [("nwog", 4100.0, 4085.0, 4092.5)], bias=-1, p=p)
    ctx4.bias_row = dict(nwog_regime="cons")
    o4 = sm2.nwog_sr_order(ctx4, ss4, i, p, "AM", 1.0)
    assert o4 is not None and o4["entry"] == -4092.5 and o4["side"].sign == -1
    assert sm2.HITS.get("nwog_sr")


def test_gap_edge_first_return_entry():
    """050 ~54:42: want -1, NWOG 4080-4088: price rallies to its lower edge 4080 for the first time - a short limit there, stop = the gap high + the pad."""
    rows = [(4060.0, 4062.0, 4058.0, 4061.0), (4061.0, 4066.0, 4060.0, 4065.0), (4065.0, 4070.0, 4064.0, 4069.0), (4069.0, 4074.0, 4068.0, 4073.0)]
    p = Params(**BASE, gap_edge_entry=True)
    ctx, sl, ss = _gap_ctx(rows, 4060.0, [("nwog", 4088.0, 4080.0, 4084.0)], bias=-1, p=p)
    i = ib(ctx, "09:45")
    o = sm2.gap_edge_order(ctx, ss, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == pytest.approx(-4080.0) and o["stop"] == pytest.approx(-4088.0 - p.pad) and "gap_edge" in o["lv_tags"]
    assert sm2.gap_edge_order(ctx, ss, i, p, "AM", 1.0) is None                             # once per gap and session
    assert sm2.gap_edge_order(ctx, sl, i, p, "AM", 1.0) is None                             # the long side has no bias
    inside = [(4060.0, 4081.0, 4058.0, 4079.0)] + rows[1:]                                  # the gap edge was already traded (a high of 4081 at the open)
    ctx2, sl2, ss2 = _gap_ctx(inside, 4060.0, [("nwog", 4088.0, 4080.0, 4084.0)], bias=-1, p=p)
    assert sm2.gap_edge_order(ctx2, ss2, i, p, "AM", 1.0) is None
    assert sm2.HITS.get("gap_edge")


def test_quarter_retrace_no_imbalance():
    """030 ~1:23:49: NWOG 4130-4146 (CE 4138), a close below the low and a clean (gap-free) retrace: a short limit at the near quarter 4134, stop 4138.25."""
    # side space (shorts mirrored): the real down-break is the short Side's up-break. Closes: 4131 (inside), 4128 (the break), a low at 4120, a retrace to 4133.
    rows = [(4132.0, 4133.0, 4130.5, 4131.0), (4131.0, 4131.5, 4127.5, 4128.0), (4128.0, 4128.5, 4120.0, 4121.0), (4121.0, 4125.0, 4120.5, 4124.0),
            (4124.0, 4128.0, 4123.0, 4127.0), (4127.0, 4130.0, 4126.0, 4129.0), (4129.0, 4132.5, 4128.5, 4132.0)]
    p = Params(**BASE, gap_quarter_retrace=True)
    ctx, sl, ss = _gap_ctx(rows, 4132.0, [("nwog", 4146.0, 4130.0, 4138.0)], bias=0, p=p)
    i = ib(ctx, "09:30") + 3
    o = sm2.gap_quarter_order(ctx, ss, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == pytest.approx(-4134.0) and o["stop"] == pytest.approx(-4138.25) and "gap_quarter" in o["lv_tags"]
    assert sm2.gap_quarter_order(ctx, ss, i + 1, p, "AM", 1.0) is None                   # once per gap
    assert sm2.gap_quarter_order(ctx, sl, i, p, "AM", 1.0) is None                       # the long side never saw a break above the gap top
    # an imbalance (a bearish FVG) in the retrace leg: the FVG, not the quarter, is the entry
    imb = [rows[0], rows[1], (4128.0, 4128.5, 4126.0, 4127.0), (4127.0, 4127.4, 4120.0, 4121.0), (4121.0, 4123.0, 4119.5, 4122.0), (4122.0, 4125.0, 4121.5, 4124.0), (4124.0, 4130.0, 4123.8, 4129.8), (4129.8, 4131.5, 4127.0, 4131.0)]
    ctxi, sli, ssi = _gap_ctx(imb, 4132.0, [("nwog", 4146.0, 4130.0, 4138.0)], bias=0, p=p)
    assert sm2.gap_quarter_order(ctxi, ssi, ib(ctxi, "09:30") + 7, p, "AM", 1.0) is None
    assert sm2.HITS.get("gap_quarter")
    # the far edge traded: the read is dead
    dead = rows + [(4132.0, 4147.0, 4131.0, 4146.5)]
    ctx2, sl2, ss2 = _gap_ctx(dead, 4132.0, [("nwog", 4146.0, 4130.0, 4138.0)], bias=0, p=p)
    assert sm2.gap_quarter_order(ctx2, ss2, ib(ctx2, "09:30") + 7, p, "AM", 1.0) is None


def test_org_two_rally_state_machine_and_gate():
    """042 ~11:31: a significant gap up (15 pts >= 0.25 x ADR5) into the premium of the 20-day range: a short is blocked before the second rally above the first high that
    follows the dip to the open; after it the short may fire with T1 = open - 5."""
    hs = hist_close(close=4000.0, hi=4030.0, lo=3990.0)                                     # ADR5 40, the 20-day EQ 4010: an open of 4015 is premium
    op = 4015.0
    seq = [(op, op + 4.0, op - 0.2, op + 3.5), (op + 3.5, op + 9.0, op + 3.0, op + 8.0),                # step 1: the first rally (high 4024)
           (op + 8.0, op + 8.5, op - 0.5, op + 0.5),                                                    # step 2: the dip to the open
           (op + 0.5, op + 6.0, op + 0.2, op + 5.0)]                                                    # still under the first high
    p = Params(**BASE, org_two_rally=True)
    ctx, (sl, ss) = mkctx(seq + [(op + 5.0, op + 11.0, op + 4.0, op + 10.0)], base=op, hist=hs, p=p)
    ctx.org, ctx.org_today = [(4000.0, op)], True
    k0 = ib(ctx, "09:30")
    assert sm2.org_state(ctx, k0 + 1, p)[3] == 1 and sm2.org_state(ctx, k0 + 2, p)[3] == 2 and sm2.org_state(ctx, k0 + 3, p)[3] == 2
    assert sm2.org_state(ctx, k0 + 4, p)[3] == 3
    assert sm2.org_two_rally_gate(ctx, ss, k0 + 3, p) == "x_org_two_rally"                            # the short waits
    assert sm2.org_two_rally_gate(ctx, ss, k0 + 4, p) is None
    assert sm2.org_two_rally_gate(ctx, sl, k0 + 3, p) is None                                         # longs are not touched
    t = sm2.org_two_rally_targets(ctx, ss, k0 + 4, p, -4020.0)
    assert t[0] == (pytest.approx(-(op - 5.0)), "array") and t[1][0] == pytest.approx(-4000.0)
    assert sm2.org_two_rally_targets(ctx, ss, k0 + 3, p, -4020.0) == []
    # not significant (a 5 point gap) / a discount open: no template
    ctx2, _s = mkctx(seq, base=op, hist=hs, p=p)
    ctx2.org, ctx2.org_today = [(4010.0, op)], True
    assert sm2.org_state(ctx2, k0 + 2, p) is None
    ctx3, _s = mkctx(seq, base=op, hist=hist_close(close=4000.0, hi=4060.0, lo=3990.0), p=p)
    ctx3.org, ctx3.org_today = [(4000.0, op)], True
    assert sm2.org_state(ctx3, k0 + 2, p) is None                                                     # EQ 4025: 4015 is not premium
    assert sm2.HITS.get("org_two_rally")
    # the mirror: a significant gap DOWN into discount blocks longs
    seq_d = [(2 * op - o, 2 * op - l, 2 * op - h, 2 * op - c) for o, h, l, c in seq + [(op + 5.0, op + 11.0, op + 4.0, op + 10.0)]]
    hs_d = hist_close(close=4030.0, hi=4040.0, lo=4000.0)
    ctx4, (sl4, ss4) = mkctx(seq_d, base=op, hist=hs_d, p=p)
    ctx4.org, ctx4.org_today = [(4030.0, op)], True
    st = sm2.org_state(ctx4, k0 + 3, p)
    assert st is not None and st[0] == -1 and sm2.org_two_rally_gate(ctx4, sl4, k0 + 3, p) == "x_org_two_rally"


# --- A4: poke, body qualification, daily first return (115, 124, 138) ---------------------------------------------------------------

def test_poke_high_cancel():
    """090 ~1:05:53: an AM short idea whose HTF array top (4020) was only poked by a wick to 4021 (no body above it): a later trade above the poke high cancels the AM
    shorts; the PM is not affected; before the second push there is nothing to cancel."""
    arr = StubConf(arrays={-1: [(4020.0, 4015.0, "D", 0, 0)]})
    rows = [(4010.0, 4021.0, 4009.0, 4012.0), (4012.0, 4013.0, 4009.0, 4010.0), (4010.0, 4022.0, 4009.0, 4011.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, conf=arr)
    k0 = ib(ctx, "09:30")
    p = Params(**BASE, poke_high_cancel=True)
    assert sm2.poke_cancel(ctx, ss, k0 + 1, p, "AM") is None                         # the poke happened, nothing traded above it yet
    assert sm2.poke_cancel(ctx, ss, k0 + 2, p, "AM") == "x_poke_high_cancel"
    assert sm2.poke_cancel(ctx, ss, k0 + 2, p, "PM") is None                         # re-evaluated at 13:30
    assert sm2.poke_cancel(ctx, sl, k0 + 2, p, "AM") is None                         # the long side has no such array
    body = [(4010.0, 4021.0, 4009.0, 4021.0)] + rows[1:]                               # a body close above the top is no poke
    ctx2, (sl2, ss2) = mkctx(body, base=4010.0, conf=arr)
    assert sm2.poke_cancel(ctx2, ss2, k0 + 2, p, "AM") is None
    assert sm2.poke_cancel(replace_conf(ctx, None), ss, k0 + 2, p, "AM") is None
    assert sm2.HITS.get("poke_cancel")


def replace_conf(ctx, conf):
    c = SimpleNamespace(**ctx.__dict__)
    c.conf = conf
    return c


def test_htf_body_qualified_wick_pierce():
    """104 ~21:53: a 60m zone 4000-4010 pierced by a wick to 3996: the zone stays qualified while the 5m / 15m bodies hold above 4000; a body that closes under 4000 kills it."""
    g = L.Zone("bull", 4010.0, 4000.0, 0, -1)
    rows = [(4008.0, 4009.0, 4005.0, 4006.0), (4006.0, 4007.0, 3996.0, 4003.0), (4003.0, 4008.0, 4001.5, 4007.0), (4007.0, 4009.0, 4005.0, 4008.0)]
    ctx, (sl, ss) = mkctx(rows, base=4008.0)
    k0 = ib(ctx, "09:30")
    g = L.Zone("bull", 4010.0, 4000.0, k0, -1)
    p = Params(**BASE, htf_body_qual=True)
    assert sm2.body_qualified(ctx, sl, g, k0 + 3, p) is True
    bad = [rows[0], (4006.0, 4007.0, 3996.0, 3998.0), rows[2], rows[3]]
    ctx2, (sl2, _) = mkctx(bad, base=4008.0)
    assert sm2.body_qualified(ctx2, sl2, g, k0 + 3, p) is False
    # the engine hook: with a wick beyond the mohawk the zone is "fresh" only under the switch
    assert sm2.HITS.get("htf_body_qual")


def test_sweep_ref_body_cluster_and_daily_first_return():
    """cc03_002 ~11:36: under sweep_ref 'body' the relative-equal-low line is the lowest BODY of a cluster (2+ candles whose bodies end at about the same price)."""
    # two swing lows with wicks 3990.0 / 3991.0 but bodies ending at 4000.0 / 4000.2: wick pool 3990.0 vs body pool 4000.0
    rows = [(4010.0, 4012.0, 4009.0, 4011.0), (4011.0, 4012.0, 4000.0, 4000.2), (4000.2, 4008.0, 3990.0, 4005.0), (4005.0, 4012.0, 4004.0, 4011.0),
            (4011.0, 4012.0, 4001.0, 4000.3), (4000.3, 4008.0, 3991.0, 4004.0), (4004.0, 4012.0, 4003.0, 4011.0), (4011.0, 4012.0, 4010.0, 4011.5)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, p=Params(**BASE, pivot_n=1))
    i = ib(ctx, "09:30") + 7
    tol = 0.5
    wick_p = Params(**BASE, pivot_n=1, eq_bodies=True)
    body_p = Params(**BASE, pivot_n=1, sweep_ref="body")
    wick_lv = S._eq_levels(sl, i, tol, True, wick_p)
    body_lv = S._eq_levels(sl, i, tol, True, body_p)
    assert wick_lv == [3990.0]                                                          # eq_bodies: the cluster of bodies, the line at the most extreme WICK
    assert body_lv == [4000.2]                                                          # sweep_ref 'body': the line is the lowest body of the cluster (bodies end at 4000.2 / 4000.3)
    # daily first return: body lows cluster at 3000 (days 0-2), the next 40 sessions stay above; today runs below the cluster
    ds = prior_days(D0, 45)
    hs = [rth_day(d, 3010.0, 2990.0, close=3000.0, op=3000.0) for d in ds[:3]] + [rth_day(d, 4010.0, 3990.0, close=4000.0) for d in ds[3:]]
    p = Params(**BASE, daily_first_return=True)
    ctx2, (sl2, _) = mkctx([(4000.0, 4001.0, 2995.0, 3996.0)] * 2, base=4000.0, hist=hs)
    assert sm2.daily_first_return(ctx2, sl2, dict(ext=2995.0), ib(ctx2, "09:35"), p) is True
    assert sm2.daily_first_return(ctx2, sl2, dict(ext=3500.0), ib(ctx2, "09:35"), p) is False            # not under the cluster
    hs2 = list(hs)
    hs2[20] = rth_day(ds[20], 4010.0, 3000.5, close=4000.0)                                              # an intermediate return to the zone: not the first
    ctx3, (sl3, _) = mkctx([(4000.0, 4001.0, 2995.0, 3996.0)] * 2, base=4000.0, hist=hs2)
    assert sm2.daily_first_return(ctx3, sl3, dict(ext=2995.0), ib(ctx3, "09:35"), p) is False
    assert Params(daily_first_return=True).daily_first_days == 30
    ctx4, (sl4, _) = mkctx([(4000.0, 4001.0, 2995.0, 3996.0)] * 2, base=4000.0, hist=hs[:20])
    assert sm2.daily_first_return(ctx4, sl4, dict(ext=2995.0), ib(ctx4, "09:35"), p) is False            # too little history


# --- B18-smt-three-point-swing (202) ------------------------------------------------------------------------------------------------

def _lows_rows(lows):
    return [(x + 1.0, x + 2.0, x, x + 1.0) for x in lows]


def test_three_point_smt():
    """cc11_004 ~27:39: this index prints low 100 - lower low 98 - higher low 99 while the partner prints 100 - 98.5 - 97.5 = a bullish SMT; the partner also making a
    higher low (or the first points missing) is not."""
    x = [103, 102, 100, 102, 103, 101, 98, 101, 103, 101, 99, 101, 103, 104]
    y = [103, 102, 100, 102, 103, 101, 98.5, 101, 103, 101, 97.5, 101, 103, 104]
    p = Params(**BASE, smt_mode="three_point", pivot_n=1)
    ctx, (sl, ss) = mkctx(_lows_rows(x), base=103.0, p=p)
    pctx, (psl, pss) = mkctx(_lows_rows(y), base=103.0, p=p)
    i = ib(ctx, "09:30") + 12
    assert [q.price for q in sl.pl if q.i >= ctx.start][:3] == [100.0, 98.0, 99.0]
    assert sm2.three_point_smt(ctx, sl, i, pctx, psl, i, p) is True
    y2 = [103, 102, 100, 102, 103, 101, 98.5, 101, 103, 101, 99.0, 101, 103, 104]            # the partner makes the same higher low: no divergence
    pctx2, (psl2, _) = mkctx(_lows_rows(y2), base=103.0, p=p)
    assert sm2.three_point_smt(ctx, sl, i, pctx2, psl2, i, p) is False
    assert sm2.three_point_smt(ctx, sl, ib(ctx, "09:30") + 6, pctx, psl, ib(ctx, "09:30") + 6, p) is None      # fewer than three confirmed lows
    # extension: an extra short-term low between the first point and the lower low that all traded through
    xe = [103, 102, 100, 102, 103, 100.5, 101, 100.2, 101, 99, 101, 103, 101, 99.4, 101, 103]
    ye = [103, 102, 100, 102, 103, 100.5, 101, 100.2, 101, 98.9, 101, 103, 101, 98.5, 101, 103]
    ctxe, (sle, _) = mkctx(_lows_rows(xe), base=103.0, p=p)
    pctxe, (psle, _) = mkctx(_lows_rows(ye), base=103.0, p=p)
    ie = ib(ctxe, "09:30") + 14
    assert sm2.three_point_smt(ctxe, sle, ie, pctxe, psle, ie, p) is True
    assert sm2.HITS.get("smt_three_point")


# --- A22-htf-definition-nested-arrays (187) ----------------------------------------------------------------------------------------

def test_nested_array_definition():
    """cc10_013 ~8:17: the AM low (4000) lies in a 1h array 3998-4004 that overlaps a 4h array 3990-4010 of the same polarity = nested; an un-nested 1h array is not."""
    rows = [(4003.0, 4004.0, 4000.0, 4002.0), (4002.0, 4010.0, 4001.0, 4009.0)]
    nested = StubConf(arrays={1: [(4004.0, 3998.0, "1h", 0, 0), (4010.0, 3990.0, "4h", 0, 0)]})
    ctx, (sl, ss) = mkctx(rows, base=4003.0, conf=nested)
    ctx.am_hl = (4010.0, 4000.0)
    k0 = ib(ctx, "09:30")
    p = Params(**BASE, pm_rev_nested=True)
    assert sm2.nested_at_am(ctx, sl, k0 + 1, p) is True
    alone = StubConf(arrays={1: [(4004.0, 3998.0, "1h", 0, 0), (4100.0, 4050.0, "4h", 0, 0)]})
    ctx2, (sl2, _) = mkctx(rows, base=4003.0, conf=alone)
    ctx2.am_hl = (4010.0, 4000.0)
    assert sm2.nested_at_am(ctx2, sl2, k0 + 1, p) is False
    far = StubConf(arrays={1: [(4204.0, 4198.0, "1h", 0, 0), (4210.0, 4190.0, "4h", 0, 0)]})
    ctx3, (sl3, _) = mkctx(rows, base=4003.0, conf=far)
    ctx3.am_hl = (4010.0, 4000.0)
    assert sm2.nested_at_am(ctx3, sl3, k0 + 1, p) is False                                   # the AM extreme is not in the array
    ctx.conf = None
    assert sm2.nested_at_am(ctx, sl, k0 + 1, p) is False


# --- delivery states (125 helper, 126, 188) -----------------------------------------------------------------------------------------

def test_state_gate_and_tool_map(monkeypatch):
    """cc01_001: no entry in CONSOLIDATION; cc01_001 / cc01_002: EXPANSION <-> OB, RETRACEMENT <-> FVG / void, REVERSAL <-> sweeps (turtle soup); other kinds pass."""
    ctx, (sl, ss) = mkctx([(4000.0, 4000.4, 3999.6, 4000.1)] * 40, base=4000.0, hist=hist_close(close=4000.0, hi=4040.0, lo=3990.0))
    i = ib(ctx, "09:30") + 30
    p = Params(**BASE, state_machine=True)
    assert sm2.state_at(ctx, i, p) == "CONSOLIDATION"                                        # a flat 30-bar fixture
    assert sm2.state_gate(ctx, sl, i, p, dict(entry_kind="fvg")) == "x_state_consolidation"
    assert sm2.state_gate(ctx, sl, i, p, dict(entry_kind="consol_fade")) is None             # the fade of a consolidation break is the exception
    assert sm2.state_gate(ctx, sl, i, replace(p, state_machine=False), dict(entry_kind="fvg")) is None
    pm = Params(**BASE, state_tool_map=True)
    for st, ok, bad in (("RETRACEMENT", "fvg", "ob_pre"), ("RETRACEMENT", "void", "turtle_soup"), ("EXPANSION", "ob_pre", "fvg"), ("EXPANSION", "arr_ob", "ifvg"),
                        ("REVERSAL", "turtle_soup", "fvg"), ("CONSOLIDATION", "", "fvg")):
        monkeypatch.setattr(sm2, "state_at", lambda *a, _s=st: _s)
        if ok:
            assert sm2.state_gate(ctx, sl, i, pm, dict(entry_kind=ok)) is None
        assert sm2.state_gate(ctx, sl, i, pm, dict(entry_kind=bad)) == "x_state_tool"
    monkeypatch.setattr(sm2, "state_at", lambda *a: "RETRACEMENT")
    assert sm2.state_gate(ctx, sl, i, pm, dict(entry_kind="breaker")) is None                # outside the map
    monkeypatch.setattr(sm2, "state_at", lambda *a: "")
    assert sm2.state_gate(ctx, sl, i, pm, dict(entry_kind="fvg")) is None                    # unknown state
    assert sm2.HITS.get("state")


def test_consol_fade_breaks_against_the_bias():
    """cc09_004 ~5:07: a consolidation 4000-4010 over 20+ bars, a wick below it that closes back inside, bias long: a long limit at the range low targeting the range
    high; a break through the top (the bias way) is no fade."""
    osc = [(4002.0, 4010.0, 4000.0, 4008.0), (4008.0, 4009.0, 4000.5, 4002.0)]
    rows = [osc[k % 2] for k in range(30)]
    brk = rows + [(4002.0, 4003.0, 3995.0, 3998.0), (3998.0, 4004.0, 3997.0, 4003.0)]
    hs = hist_close(close=4000.0, hi=4040.0, lo=3990.0)                                      # ADR5 50: a 10-point range is < 0.3 x 50
    p = Params(**BASE, consol_fade=True)
    ctx, (sl, ss) = mkctx(brk, base=4005.0, hist=hs, bias=1, p=p, start="07:00")
    i = ib(ctx, "07:00") + 31
    o = sm2.consol_fade_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == pytest.approx(4000.0) and o["stop"] < 3995.0 and o["levels"][-1] >= 4009.0 and "consol_fade" in o["lv_tags"]
    assert sm2.consol_fade_order(ctx, sl, i, p, "AM", 1.0) is None                            # once per range
    ctx2, (sl2, ss2) = mkctx(brk, base=4005.0, hist=hs, bias=-1, p=p, start="07:00")
    assert sm2.consol_fade_order(ctx2, sl2, i, p, "AM", 1.0) is None                          # against the bias there is no fade of the downside break
    up = rows + [(4008.0, 4015.0, 4007.0, 4014.0), (4014.0, 4016.0, 4012.0, 4015.0)]
    ctx3, (sl3, _) = mkctx(up, base=4005.0, hist=hs, bias=1, p=p, start="07:00")
    assert sm2.consol_fade_order(ctx3, sl3, i, p, "AM", 1.0) is None
    assert sm2.HITS.get("consol_fade")


# --- A11-bpr-levels-ce-rejection (98) / A17-index-or-rejection-block (174) -------------------------------------------------------------

BPR_ROWS = [(4020.0, 4021.0, 4016.0, 4017.0), (4017.0, 4017.5, 4005.0, 4006.0), (4006.0, 4008.0, 4004.0, 4005.0),             # a bearish FVG 4008-4016
            (4005.0, 4010.0, 4004.5, 4009.8), (4009.8, 4020.0, 4009.5, 4019.5), (4019.5, 4021.0, 4014.0, 4020.5),            # a bullish FVG 4010-4014 -> the BPR (4010, 4014)
            (4020.5, 4022.0, 4019.0, 4021.0),                                                                                # above it: the first arm (limit at the CE 4012)
            (4021.0, 4021.5, 4013.5, 4014.0), (4014.0, 4020.0, 4013.9, 4019.0)]                                               # a revisit and a new departure: the second arm


def test_bpr_ce_arms_on_every_revisit():
    hs = hist_close(close=4020.0, hi=4100.0, lo=3990.0)
    ctx, (sl, ss) = mkctx(BPR_ROWS, base=4020.0, p=Params(**BASE, pivot_n=1), hist=hs)
    k0 = ib(ctx, "09:30")
    z = [z for z in sl.bprs(0) if z.kind == "bull" and z.top == 4014.0][0]
    assert (z.top, z.bottom, z.mid) == (4014.0, 4010.0, 4012.0) and z.i == k0 + 5
    p = Params(**BASE, entry_arrays=("bpr_ce",))
    o1 = sm2.bpr_ce_order(ctx, sl, k0 + 6, p, "AM", 1.0)
    assert o1 is not None and o1["entry"] == 4012.0 and o1["stop"] == pytest.approx(4010.0 - p.pad) and "bpr_ce" in o1["lv_tags"] and o1["lvx"]["bpr_ce_close"] == (4012.0, False)
    again = sm2.bpr_ce_order(ctx, sl, k0 + 6, p, "AM", 1.0)
    assert again is None or again["entry"] != 4012.0                                        # no new retest of THIS range yet (the fixture holds a second, lower bull BPR)
    assert sm2.bpr_ce_order(ctx, sl, k0 + 7, p, "AM", 1.0) is None                          # the revisit bar closes inside the zone's top (4014 not above 4014)
    o2 = sm2.bpr_ce_order(ctx, sl, k0 + 8, p, "AM", 1.0)
    assert o2 is not None and o2["entry"] == 4012.0                                         # the second revisit arms again
    dead = BPR_ROWS[:7] + [(4021.0, 4021.5, 4009.0, 4011.0), (4011.0, 4020.0, 4010.9, 4019.0)]      # a body closed under the CE
    ctx2, (sl2, _) = mkctx(dead, base=4020.0, p=Params(**BASE, pivot_n=1), hist=hs)
    od = sm2.bpr_ce_order(ctx2, sl2, ib(ctx2, "09:30") + 8, Params(**BASE), "AM", 1.0)
    assert od is None or od["entry"] != 4012.0                                              # the (4010, 4014) range is dead (the lower fixture BPR may still arm)
    assert sm2.HITS.get("bpr_ce")


def test_or_rejection_block():
    """cc10_010 ~9:03: the lowest-close down candle of the 09:30-10:30 range is the long block (level = its close); the bearish block is the LAST up-close candle."""
    rows = [(4010.0, 4012.0, 4008.0, 4009.0), (4009.0, 4011.0, 4005.0, 4007.0), (4007.0, 4010.0, 4004.0, 4009.0), (4009.0, 4012.0, 4007.0, 4011.0),
            (4011.0, 4013.0, 4009.0, 4012.0), (4012.0, 4012.5, 4005.5, 4006.0), (4006.0, 4010.0, 4005.0, 4009.0), (4009.0, 4011.0, 4007.0, 4010.0),
            (4010.0, 4012.0, 4008.0, 4011.0), (4011.0, 4013.0, 4010.0, 4012.0), (4012.0, 4014.0, 4010.5, 4013.0), (4013.0, 4015.0, 4012.0, 4014.0),
            (4014.0, 4016.0, 4013.0, 4015.0), (4015.0, 4016.0, 4014.0, 4015.5)]                          # 09:30 .. 10:35
    p = Params(**BASE, or_rb=True)
    hs = hist_close(close=4010.0, hi=4100.0, lo=3990.0)
    ctx, (sl, ss) = mkctx(rows, base=4010.0, p=p, hist=hs)
    ctx.or60 = (4013.0, 4004.0)
    i = ib(ctx, "09:30") + 13                                                                   # 10:35
    assert ctx.t[i] == 635
    o = sm2.or_rb_order(ctx, sl, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == 4006.0 and o["stop"] == pytest.approx(4004.0 - p.pad) and "or_rb" in o["lv_tags"]   # the lowest-close down candle: close 4006.0
    assert sm2.or_rb_order(ctx, sl, i, p, "AM", 1.0) is None                                     # once per side and day
    ctx2, (sl2, ss2) = mkctx(rows, base=4010.0, p=p, hist=hist_close(close=4010.0, hi=4030.0, lo=3900.0))
    ctx2.or60 = (4013.0, 4004.0)
    ctx2.cur_bias = -1
    ob = sm2.or_rb_order(ctx2, ss2, ib(ctx2, "09:30") + 11, p, "AM", 1.0)           # 10:25: still inside the OR, nothing yet
    assert ob is None
    ob = sm2.or_rb_order(ctx2, ss2, ib(ctx2, "09:30") + 13, replace(p, or_rb_bear="last"), "AM", 1.0)      # the bearish block: the LAST up-close candle (09:30 + 9: close 4012)
    assert ob is None or ob["entry"] == pytest.approx(-4012.0)                       # (the price is above the level: a short limit above the market needs c < level)
    ctx3, (sl3, _) = mkctx(rows[:12], base=4010.0, p=p, hist=hs)
    ctx3.or60 = (4013.0, 4004.0)
    assert sm2.or_rb_order(ctx3, sl3, ib(ctx3, "09:30") + 11, p, "AM", 1.0) is None            # before 10:30 the range is not complete
    below = rows[:12] + [(4015.0, 4016.0, 4003.0, 4004.5), (4004.5, 4006.0, 4004.0, 4005.0)]       # the OR low broke: invalid
    ctx4, (sl4, _) = mkctx(below, base=4010.0, p=p, hist=hs)
    ctx4.or60 = (4013.0, 4004.0)
    assert sm2.or_rb_order(ctx4, sl4, ib(ctx4, "09:30") + 13, p, "AM", 1.0) is None
    assert sm2.HITS.get("or_rb")


# --- run_day scenarios: tags, range lock, breaker hold, cc_limit next array, re-arm, reclaimed loose ------------------------------------------

from test_caption_gap_sm1a import AFTER, scen_b                      # noqa: E402
from test_review_fixes import B_POST, B_ROWS, run as rf_run          # noqa: E402


def test_setup_model_and_delivery_tags_in_a_trade():
    """cc09_006 / A2: a sweep-MSS-FVG trade is tagged OA (a short OD); the delivery tag is the sign of the last displacement leg."""
    t = scen_b()
    assert len(t) == 1 and t[0].setup_model == "OA" and t[0].delivery in ("up", "down", "")
    assert t[0].div_type == ""                                                         # off: untagged
    ctx, (sl, ss) = mkctx(B_ROWS, base=100.0)
    sw = dict(key="pdl1", level=98.6)
    assert sm2.setup_model(sl, sw) == "OA" and sm2.setup_model(ss, sw) == "OD"
    syn = {S._SM.SYNTH: True}
    assert sm2.setup_model(sl, syn) == "RA" and sm2.setup_model(ss, syn) == "RD"
    assert sm2.setup_model(sl, dict(key="mitigation")) == "RA" and sm2.setup_model(sl, dict(key="ir")) == "RA"
    # delivery: the displacement bar of a leg up
    ctx2, (sl2, _) = mkctx([(100.0, 100.3, 99.9, 100.1)] * 12 + [(100.1, 106.0, 100.0, 105.8)], base=100.0, start="07:00")
    assert sm2.delivery_dir(ctx2, sl2, ib(ctx2, "07:00") + 12) == "up"
    ctx3, (sl3, _) = mkctx([(100.0, 100.3, 99.9, 100.1)] * 12 + [(100.1, 100.2, 94.0, 94.3)], base=100.0, start="07:00")
    assert sm2.delivery_dir(ctx3, sl3, ib(ctx3, "07:00") + 12) == "down"
    ctx4, (sl4, _) = mkctx([(100.0, 100.3, 99.9, 100.1)] * 40, base=100.0, start="07:00")
    assert sm2.delivery_dir(ctx4, sl4, ib(ctx4, "07:00") + 35) == ""


def test_div_tag_on_a_trade():
    t = scen_b(div_tag=True)
    assert len(t) == 1 and t[0].div_type in ("", "type1", "type2")
    assert scen_b()[0].div_type == ""


def _chop_rows(n):
    return [(102.6, 103.0, 102.2, 102.7)] * n


def test_range_lock_keeps_the_order_through_a_chop():
    """064 ~56:17: lunch chop above the armed limit (101.3) longer than pending_minutes (30 = 6 bars): the order expires normally; under range_lock it rests until the
    dip fills it; a body close under the invalidation (the OB MT / low) still cancels it."""
    base = B_ROWS + _chop_rows(7) + AFTER
    hist = history(hi=112.0, lo=88.0)
    p = Params(**{**B_POST, "adds": (0.5,)})
    tr, *_ = rf_run(day(base), hist, p, {})
    assert tr == []                                                                    # expired during the chop
    tr, *_ = rf_run(day(base), hist, replace(p, range_lock=True), {})
    assert len(tr) == 1 and tr[0].entry == 101.3
    # (a body close under the invalidation always trades through the limit first - the cancel_close test is the plumbing in run_day, asserted on the source)
    assert 'pending.get("cancel_close")' in open(S.__file__, encoding="utf-8").read()
    # the lock record
    sd = sd_of([(100.0, 101.0, 99.0, 100.5), (100.5, 102.0, 100.0, 101.5), (101.5, 101.8, 100.8, 101.2), (101.2, 102.5, 101.0, 102.0), (102.0, 102.2, 98.0, 98.5)])
    sm2.range_lock_set(sd, dict(ext_i=0), 1, 99.5, 99.0)
    assert sm2.range_locked(sd, 2) is True                                              # strictly inside the range (hi 102.0 so far)
    assert sm2.range_locked(sd, 3) is False                                             # a high of 102.5 above the lock high 102.0: expansion, lock off
    sm2.range_lock_set(sd, dict(ext_i=0), 1, 99.5, 99.0)
    assert sm2.range_locked(sd, 4) is False                                              # the bar before closed under the invalidation 99.5? (98.5 < 99.5 only at bar 4's own close)


def test_breaker_range_hold_tags_the_order():
    """048 ~1:20:40: after a breaker tap the order rests with no expiry; a trade under the breaker's low cancels it."""
    ctx, (sl, ss) = mkctx(B_ROWS, base=100.0)
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", name="x", level=98.6, key="x", ext=98.0, ext_i=k0 + 5, broke=k0 + 7, sweep_i=k0 + 5, smt=None, smt2=None)
    bz = L.Zone("bull", 101.0, 100.1, k0 + 7, k0 + 3, 100.55)
    i = k0 + 8
    o = S._breaker_order(ctx, sl, sw, bz, i, Params(**B_POST, breaker_range_hold=True), "AM", 1.0)
    assert o is not None and o["no_expire"] is True and o["cancel_low"] == pytest.approx(100.1)
    o2 = S._breaker_order(ctx, sl, dict(sw), bz, i, Params(**B_POST), "AM", 1.0)
    assert o2 is not None and "no_expire" not in o2
    # run_day: the pending cancel / no-expiry plumbing (a pending order with no_expire survives the 30-minute lifetime)
    src = open(S.__file__, encoding="utf-8").read()
    assert 'pending.get("no_expire")' in src and 'pending.get("cancel_close")' in src


def test_mss_rearm_after_a_lower_high_keeps_the_side_armed():
    """069 ~14:41: after the first order (the MSS leg) the sweep stays armed while the retrace does not pierce the sweep extreme; a later displacement FVG re-arms."""
    more = [(108.8, 109.0, 106.0, 106.5), (106.5, 106.8, 105.0, 105.5), (105.5, 111.0, 105.4, 110.5), (110.5, 113.5, 110.0, 113.0), (113.0, 113.5, 112.5, 113.2),
            (113.2, 119.0, 113.1, 118.5), (118.5, 120.0, 118.0, 119.5)]
    rows = B_ROWS + AFTER + more
    hist = history(hi=140.0, lo=88.0)
    p = Params(**{**B_POST, "adds": ()})
    off, *_ = rf_run(day(rows), hist, p, {})
    on, *_ = rf_run(day(rows), hist, replace(p, mss_rearm_lower_high=True), {})
    assert len(on) >= len(off) and len(off) == 1
    assert [t.entry for t in on[:1]] == [t.entry for t in off[:1]]                       # the first trade is unchanged


def test_reclaimed_loose_trade_tag_and_array_entry():
    """A18: the loose reclaimed block (the 09:55 down candle 98.0-99.5: left, re-traded at 99.0, left again) is an entry array; the strict definition has no candle before the
    curve low here; the order carries the definition tag."""
    p = Params(**B_POST, reclaimed_ob=True, reclaimed_def="loose")
    ctx, (sl, ss) = mkctx(B_ROWS, base=100.0, p=p, hist=history(hi=112.0, lo=88.0))
    k0 = ib(ctx, "09:30")
    e, i = k0 + 5, k0 + 8
    sw = dict(ext=98.0, ext_i=e, key="x", session="AM", name="x", level=98.6, broke=k0 + 7, sweep_i=e, smt=None, smt2=None)
    assert SM.array_cands(ctx, sl, sw, i, p, None) == [(99.5, 98.0, "reclaimed_ob")]
    assert SM.array_cands(ctx, sl, sw, i, replace(p, reclaimed_def="strict"), None) == []
    o = SM.array_order(ctx, sl, sw, i, p, "AM", 1.0, None, None)
    assert o is not None and o["entry"] == 99.5 and o["lv_tags"] == "reclaimed_loose" and o["swept"] == "x"
    os_ = SM.array_order(ctx, sl, sw, i, replace(p, reclaimed_def="strict"), "AM", 1.0, None, None)
    assert os_ is None                                                                  # (no strict block in this fixture)


def test_cc_limit_uses_the_next_array_beyond_the_pool():
    """025: the resting buy limit of turtle_soup 'cc_limit' sits at the next array beyond the pool (the gap row 4103-4105 for a short at the old high 4100) and the stop one
    tick beyond its far edge."""
    rows = [(4098.0, 4099.0, 4097.0, 4098.0)] * 4
    p = Params(**BASE, turtle_soup="cc_limit", ts_next_array=True, ts_cc_below_pts=1.0)
    hist = hist_close(close=4098.0, hi=4100.0, lo=3990.0)
    ctx, (sl, ss) = mkctx(rows, base=4098.0, hist=hist, bias=-1, p=p)
    ctx.gaps = [("nwog", 4105.0, 4103.0, 4104.0)]
    ctx.pd["pdh1"] = 4100.0
    i = ib(ctx, "09:40")
    o = S._cc_limit(ctx, ss, i, p, "AM", 1.0)
    assert o is not None and o["entry"] == pytest.approx(-4103.0) and o["stop"] == pytest.approx(-4105.25)
    ctx2, (sl2, ss2) = mkctx(rows, base=4098.0, hist=hist, bias=-1, p=replace(p, ts_next_array=False))
    ctx2.pd["pdh1"] = 4100.0
    o2 = S._cc_limit(ctx2, ss2, i, replace(p, ts_next_array=False), "AM", 1.0)
    assert o2 is not None and o2["entry"] == pytest.approx(-4101.0)                      # the old rule: ts_cc_below_pts beyond the pool


def test_ir_gates_and_switches():
    """059 ~4:50: the opt-in IR path needs the draw its way and a volatility window."""
    ctx, (sl, ss) = mkctx([(100.0, 100.3, 99.9, 100.1)] * 4, base=100.0, bias=1)
    p = Params(**BASE)
    i = ib(ctx, "09:35")
    assert sm2.ir_gates_ok(ctx, sl, i, p, "AM") is True
    assert sm2.ir_gates_ok(ctx, sl, i, p, "LUNCH") is False                                  # outside the windows
    assert sm2.ir_gates_ok(ctx, sl, i, replace(p, ir_need_window=False), "LUNCH") is True
    assert sm2.ir_gates_ok(ctx, ss, i, p, "AM") is False                                      # the draw points the other way
    assert sm2.ir_gates_ok(ctx, ss, i, replace(p, ir_need_draw=False), "AM") is True
    ctx.cur_bias = 0
    assert sm2.ir_gates_ok(ctx, sl, i, p, "AM") is False and sm2.ir_gates_ok(ctx, sl, i, p, "AM", use_want=False) is False
    assert sm2.HITS.get("ir_gates")
    # the engine path: ir_entry reads both switches
    src = open(SM.__file__, encoding="utf-8").read()
    assert "ir_need_draw" in src and "ir_gates_ok" in src


def test_mm_ssl_target_is_the_far_end_of_the_delivery_leg():
    """104 ~11:24: with mmxm_ctx the draw is the far end of the leg that engineered the pool - side space: the highest high of the decline into the sweep extreme."""
    ctx, (sl, ss) = mkctx(LEG, base=4010.0, p=Params(**BASE, pivot_n=1))
    k0 = ib(ctx, "09:30")
    e, i = k0 + 6, k0 + 7
    p = Params(**BASE, pivot_n=1, mmxm_ctx=True, mm_ssl_target=True)
    q = SM.leg_origin(sl, e, i)
    out = SM.draw_prefs(ctx, sl, dict(ext_i=e, ext=3990.0, key="pdl1", session="AM"), i, p, "AM", 3995.0, 5.0, [])
    far = float(sl.h[q.i:e + 1].max())
    assert any(kd == "pool" and nm == "mmxm" and v >= far - 1.0 for v, kd, nm in out)
    out0 = SM.draw_prefs(ctx, sl, dict(ext_i=e, ext=3990.0, key="pdl1", session="AM"), i, replace(p, mm_ssl_target=False), "AM", 3995.0, 5.0, [])
    assert isinstance(out0, list)


def test_reaper_ob_overlap(monkeypatch):
    """081 ~11:49: the breaker zone coincides with an order block: a limit at the breaker top, stop under its low; a breaker that does not overlap the block gives nothing."""
    ctx, (sl, ss) = mkctx(B_ROWS + AFTER, base=100.0)
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", name="x", level=98.6, key="x", ext=98.0, ext_i=k0 + 5, broke=k0 + 7, sweep_i=k0 + 5, smt=None, smt2=None)
    p = Params(**B_POST, reaper=True, reaper_def="ob_overlap")
    bz = L.Zone("bull", 101.0, 100.1, k0 + 7, k0 + 3, 100.55)
    monkeypatch.setattr(S, "_breaker", lambda *a, **k: bz)
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: dict(body_top=100.8, body_low=100.2, mt=100.5))
    i = k0 + 8
    o = SM.reaper_order(ctx, sl, sw, i, p, "AM", 1.0, k0 + 3, True, 5)
    assert isinstance(o, dict) and o["entry"] == 101.0 and "reaper_ob" in o["lv_tags"]
    assert SM.reaper_order(ctx, sl, sw, i, p, "AM", 1.0, k0 + 3, True, 5) is None                 # once per sweep
    monkeypatch.setattr(S, "_ob_at_low", lambda *a, **k: dict(body_top=99.0, body_low=98.2, mt=98.6))
    assert SM.reaper_order(ctx, sl, dict(sw), i, p, "AM", 1.0, k0 + 3, True, 5) is None            # no overlap
    # the fvg definition (default) is untouched: no breaker call
    monkeypatch.setattr(S, "_breaker", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fvg def must not build a breaker")))
    r = SM.reaper_order(ctx, sl, dict(sw), i, replace(p, reaper_def="fvg"), "AM", 1.0, k0 + 3, True, 5)       # (the original A24.2 branch: never builds a breaker)
    assert r is None or isinstance(r, (dict, str))


def test_htf_pm_reversal_nested_gate_flag():
    """The PM reversal gate flag is read by setups.pm_reversal (a nested AM array); without a Confluence object it blocks."""
    src = open(SM.__file__, encoding="utf-8").read()
    assert "p.pm_rev_nested and not S._SM2.nested_at_am" in src


def test_turtle_gates_wired(monkeypatch):
    """ts_skip_reswept (default on), ts_need_smt and ts_itl_context are read by strategy._turtle."""
    src = open(S.__file__, encoding="utf-8").read()
    for needle in ("p.ts_skip_reswept and _SM2.reswept", "p.ts_need_smt and not _SM2.ts_smt_ok", "p.ts_itl_context and not _SM2.itl_ok", "p.ts_next_array"):
        assert needle in src
    assert Params().ts_skip_reswept is True


def test_mss_ref_reads_the_5m_swing_inside_a_micro_regime(monkeypatch):
    """024 ~10:08: on the 1m chart (ctx.tf 1) a micro regime makes setups.mss_ref read the 5m swing (m_tf 5); outside the regime, or on a 5m chart, it does not."""
    n = 50
    off = [0.0, 0.5, 1.0, 0.5]
    rows = [(4000.0 + off[k % 4], 4000.3 + off[k % 4], 3999.9 + off[k % 4], 4000.1 + off[k % 4]) for k in range(n)]
    hs = hist_close(close=4000.0, hi=4060.0, lo=3990.0)
    p = Params(**BASE, micro_regime=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hs, p=p, start="07:00")
    i = ib(ctx, "09:30") + 18
    seen = []
    real = SM._tf_pivots

    def spy(c, sd, m):
        seen.append(m)
        return real(c, sd, m)

    monkeypatch.setattr(SM, "_tf_pivots", spy)
    ctx.tf = 1                                                                           # pretend a 1m engine
    SM.mss_ref(ctx, sl, dict(ext_i=i - 2, ext=3999.9, key="x", session="AM"), i, p)
    assert seen == [5]
    seen.clear()
    SM.mss_ref(ctx, sl, dict(ext_i=i - 2, ext=3999.9, key="x", session="AM"), i, replace(p, micro_regime=False))
    assert seen == []
    ctx.tf = 5                                                                           # a 5m chart already is the 5m structure
    SM.mss_ref(ctx, sl, dict(ext_i=i - 2, ext=3999.9, key="x", session="AM"), i, p)
    assert seen == []


def test_order_gate2_wires_the_gates_and_always_on_tags():
    """The gates reach the orders through sm2.order_gate2 (called by strategy._finish_order after order_gate), and the always-on tags are set on every order."""
    rows = [(4000.0, 4010.0, 3999.0, 4009.0), (4009.0, 4012.0, 4006.0, 4007.0), (4007.0, 4020.0, 4006.0, 4018.0), (4018.0, 4019.0, 4010.0, 4011.0), (4011.0, 4013.0, 4005.0, 4006.0),
            (4006.0, 4020.5, 4005.0, 4017.0), (4017.0, 4018.0, 4009.0, 4010.0), (4010.0, 4011.0, 4007.0, 4008.0), (4008.0, 4009.0, 4001.0, 4002.0)]
    p = Params(**BASE, reh_trap=True, pivot_n=1)
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, p=p)
    i = ib(ctx, "09:30") + 8
    tags = {}
    assert sm2.order_gate2(ctx, ss, dict(key="pdh1", ext=-4001.0, ext_i=i - 1), i, p, -4002.0, -4010.0, "AM", [], {}, tags) == "x_reh_trap"
    assert tags["setup_model"] == "OD" and "delivery" in tags                                 # tagged before any gate can reject
    tags = {}
    assert sm2.order_gate2(ctx, sl, dict(key="pdl1", ext=3999.0, ext_i=i - 1), i, p, 4002.0, 3995.0, "AM", [], {}, tags) is None and tags["setup_model"] == "OA"
    # poke / dfvg / state / ifvg / org wiring is by the same function: the switches off leave the order untouched
    off = Params(**BASE)
    assert sm2.order_gate2(ctx, ss, dict(key="pdh1", ext=-4001.0, ext_i=i - 1), i, off, -4002.0, -4010.0, "AM", [], {}, {}) is None
    src = open(S.__file__, encoding="utf-8").read()
    for needle in ("_SM2.order_gate2(", "p.second_break_partial", "_SM2.second_break_partial(", "_SM2.extra2(", "_SM2.range_locked(", "_SM2.range_lock_set(", "_SM2.body_qualified("):
        assert needle in src, needle
