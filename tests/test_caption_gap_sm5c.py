"""Caption-gap pass, package setups_models #5/7, review-fix round (chunk 5/7): unit tests of the review fixes and of the switches built after the review (mm_lowrisk_reentry, mm_stage2,
mm_accum_gate, unicorn_independent) plus direct truncation (look-ahead) checks of the paths the data windows of test_caption_gap_sm5b.py cannot reach. No local data needed here."""
from dataclasses import replace

import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, sm2, sm3, sm4, sm5, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE
from test_caption_gap_sm1a import StubConf, hist_close, ib, mkctx
from test_caption_gap_sm4a import cap  # noqa: F401
from test_caption_gap_sm5a import _flag_rows, _reh_hist, _mm_ctx, _dip_rows, REC_ROWS


def test_review_switch_defaults_and_validation():
    p = Params()
    assert (p.mm_lowrisk_reentry, p.mm_stage2, p.mm_accum_gate, p.unicorn_independent) == ("", False, False, False)
    with pytest.raises(ValueError):
        Params(mm_lowrisk_reentry="x")
    for v in ("extreme", "wick_ce"):
        assert Params(mm_lowrisk_reentry=v).mm_lowrisk_reentry == v


# --- 64: the flag is anchored on the first sweep bar ---------------------------------------------------------------------------------------------

def test_flag_multi_bar_sweep_and_bounded_pole():
    """review: a sweep that lasts two bars moves ext_i to the new low; the flag window must still end at the FIRST sweep bar (sweep_i), the pole origin is the impulse's high (6 x flag_min_bars back)."""
    rows = _flag_rows() + [(3993.5, 3994.0, 3984.0, 3985.0)]                 # a second sweep bar, a lower low
    p = Params(**BASE, false_flag="tag")
    ctx, (sl, ss) = mkctx(rows, base=4050.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30") + len(rows) - 2
    sw = dict(session="AM", key="pdl1", name="pdl1", level=3990.0, ext=3984.0, ext_i=e + 1, broke=None, sweep_i=e, smt=None, smt2=None)
    fl = sm5.flag_info(ctx, sl, sw, e + 1, p)
    assert fl is not None and fl["low"] == pytest.approx(3990.0) and fl["high"] == pytest.approx(3998.0)
    bad = sm5.flag_info(ctx, sl, dict(sw, sweep_i=e + 1), e + 1, p)               # anchored on the lowest-low bar instead (the old behaviour): the sweep bar pollutes the window
    assert bad is None or bad["low"] < fl["low"]
    lvt = []
    assert sm5.false_flag_gate(ctx, sl, sw, e + 1, p, lvt, {}) is None and lvt == ["false_flag"]
    # an old high far before the impulse does not lengthen the pole
    old = [(4300.0, 4300.5, 4299.0, 4299.5)] + [(4050.0, 4051.0, 4049.0, 4050.0)] * 40
    ctx2, (sl2, _) = mkctx(old + _flag_rows(), base=4050.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e2 = ib(ctx2, "09:30") + len(old) + len(_flag_rows()) - 1
    sw2 = dict(sw, ext_i=e2, sweep_i=e2, ext=3988.0)
    fl2 = sm5.flag_info(ctx2, sl2, sw2, e2, p)
    assert fl2 is not None and fl2["origin"] == pytest.approx(4051.0)


# --- 110: low-risk short without a prior sweep, the re-entry, stage 2 ----------------------------------------------------------------------------------

LR_ROWS = [(4004.0, 4005.0, 4000.5, 4002.0), (4002.0, 4010.0, 4001.0, 4009.0), (4009.0, 4012.0, 4008.0, 4009.5), (4009.5, 4010.0, 3998.0, 4001.0), (4001.0, 4014.0, 4000.5, 4013.0),
           (4013.0, 4013.5, 3995.0, 3996.5), (3996.5, 4014.0, 3996.0, 4012.0)]


def _lr(monkeypatch, rows=LR_ROWS):
    ctx, (sl, ss) = mkctx(rows, base=4004.0, hist=hist_close(close=4004.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    z = L.Zone("bull", 4010.0, 4000.0, k0 + 1, k0)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: [z] if m == 60 else [])
    return ctx, sl, k0


def test_mm_lowrisk_needs_no_prior_sweep_and_is_mm_kind(cap, monkeypatch):
    ctx, sl, k0 = _lr(monkeypatch)
    p = Params(**BASE, mm_lowrisk=True)
    assert sl.__dict__.get("_mm5") is None
    assert sm5.mm_lowrisk_order(ctx, sl, k0 + 4, p, "AM", 1.0) is not None                  # no remembered same-side sweep needed (review fix)
    assert cap["entry"] == pytest.approx(4005.0) and cap["stop"] == pytest.approx(3998.0 - p.pad)
    assert cap["tags"]["sm5"]["kind"] == "mm" and cap["tags"]["sm5"]["lowrisk"] is True and cap["fixed"] is None     # no original consolidation without a sweep: no partial


def test_mm_lowrisk_reentry(cap, monkeypatch):
    ctx, sl, k0 = _lr(monkeypatch)
    p = Params(**BASE, mm_lowrisk=True)
    assert sm5.mm_lowrisk_order(ctx, sl, k0 + 4, p, "AM", 1.0) is not None
    i = k0 + 6
    assert sm5.mm_lowrisk_order(ctx, sl, i, p, "AM", 1.0) is None                          # off by default
    pe = replace(p, mm_lowrisk_reentry="extreme")
    assert sm5.mm_lowrisk_order(ctx, sl, k0 + 5, pe, "AM", 1.0) is None                    # the stop was run at bar 5 but the close is still under the edge
    assert sm5.mm_lowrisk_order(ctx, sl, i, pe, "AM", 1.0) is not None
    assert cap["tags"]["entry_kind"] == "mm_lowrisk_re" and cap["entry"] == pytest.approx(4010.0) and cap["stop"] == pytest.approx(3995.0 - p.pad)
    assert sm5.mm_lowrisk_order(ctx, sl, i, pe, "AM", 1.0) is None                         # one re-entry only
    ctx2, sl2, _ = _lr(monkeypatch)
    assert sm5.mm_lowrisk_order(ctx2, sl2, k0 + 4, p, "AM", 1.0) is not None
    assert sm5.mm_lowrisk_order(ctx2, sl2, i, replace(p, mm_lowrisk_reentry="wick_ce"), "AM", 1.0) is not None
    assert cap["stop"] == pytest.approx((3995.0 + 3996.5) / 2 - p.pad)                     # the wick candle's CE
    # no stop-out: no re-entry
    calm = LR_ROWS[:5] + [(4013.0, 4013.5, 4003.0, 4004.0), (4004.0, 4014.0, 4003.5, 4012.0)]
    ctx3, sl3, _ = _lr(monkeypatch, calm)
    assert sm5.mm_lowrisk_order(ctx3, sl3, k0 + 4, p, "AM", 1.0) is not None
    assert sm5.mm_lowrisk_order(ctx3, sl3, i, pe, "AM", 1.0) is None


ST2_ROWS = [(4003.0, 4004.0, 3999.0, 4003.5), (4003.5, 4012.0, 4003.0, 4011.0), (4011.0, 4012.0, 4006.0, 4007.0), (4007.0, 4015.0, 4006.5, 4014.0), (4014.0, 4016.0, 4012.0, 4013.0)]


def test_mm_stage2_ob_mt_and_no_chase(cap):
    """The stage-2 entry = the OB of the move after the MSS (a down-close candle the next bar closed above): a limit at its body midpoint; a leg that already traded it is never chased."""
    ctx, (sl, ss) = mkctx(ST2_ROWS, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0, broke=k0 + 1, sweep_i=k0, ref_i=k0 - 1, bz_sent=True, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    p = Params(**BASE, mm_stages=True, mm_stage2=True)
    i = k0 + 4
    assert sm5.mm_stage_order(ctx, sl, i, replace(p, mm_stage2=False), "AM", 1.0) is None            # no stage-2 switch and no BISI after the MSS: nothing
    assert sm5.mm_stage_order(ctx, sl, i, p, "AM", 1.0) is not None
    assert cap["tags"]["entry_kind"] == "mm_stage2" and cap["entry"] == pytest.approx(4009.0) and cap["stop"] == pytest.approx(4006.0 - p.pad) and cap["tags"]["cancel_close"] == pytest.approx(4006.0)
    assert cap["tags"]["sm5"]["kind"] == "mm"
    assert sm5.stage2_order(ctx, sl, sw, i, p, "AM", 1.0) is None                          # once per block
    missed = ST2_ROWS[:4] + [(4014.0, 4016.0, 4008.0, 4013.0)]                              # price came back to 4009 and left without us
    ctx2, (sl2, _) = mkctx(missed, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    assert sm5.stage2_order(ctx2, sl2, dict(sw), i, p, "AM", 1.0) is None


# --- 108: the accumulation gate ------------------------------------------------------------------------------------------------------------------------

def test_mm_accum_gate_blocks_oc_and_stages(cap):
    ctx, (sl, ss), k0, sw = _mm_ctx()
    p = Params(**BASE, mm_oc_entry=True, mm_accum_bars=3)
    assert sm5.mm_oc_order(ctx, sl, k0 + 8, p, "AM", 1.0) is not None                      # the gate switch is off: unchanged
    assert cap["tags"]["cancel_close"] == pytest.approx(4016.0)                            # the OC order cancels on a body close under the consolidation low
    sl.__dict__.pop("_mmoc_sent")
    pg = replace(p, mm_accum_gate=True)
    assert not sm5.accum_ok(ctx, sl, sw, k0 + 8, pg)
    assert sm5.mm_oc_order(ctx, sl, k0 + 8, pg, "AM", 1.0) is None                         # no sideways accumulation inside a discount array: not armed
    assert sm5.accum_ok(ctx, sl, sw, k0 + 8, replace(pg, mm_accum_bars=0))                 # the gate is open without the test


def test_accum_ok_true_when_array_holds():
    rows = [(4003.0, 4004.0, 3999.0, 3999.5), (3999.5, 4002.0, 3999.2, 4001.5), (4001.5, 4008.0, 4001.0, 4007.0), (4007.0, 4010.0, 4004.0, 4009.0), (4004.0, 4004.0, 4002.5, 4003.8),
            (4003.8, 4004.0, 4002.8, 4003.2), (4003.2, 4003.9, 4002.6, 4003.6)]
    ctx, (sl, ss) = mkctx(rows, base=4003.0, hist=hist_close(close=4003.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0, broke=k0 + 2, sweep_i=k0, smt=None, smt2=None)
    p = Params(**BASE, mm_accum_bars=3, mm_accum_gate=True)
    assert sm5.accum_ok(ctx, sl, sw, k0 + 6, p)
    assert not sm5.accum_ok(ctx, sl, sw, k0 + 6, replace(p, mm_accum_bars=4))


# --- 99 / 111 / 107: pending ladder orders cancel on a body close through the block, the ladder kill persists ----------------------------------------

def test_ladder_orders_carry_cancel_close_and_the_kill_persists(cap):
    ctx, (sl, ss) = mkctx(REC_ROWS, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=4000.0, ext=3999.0, ext_i=k0 + 8, broke=k0 + 9, sweep_i=k0 + 8, smt=None, smt2=None)
    sl.__dict__["_mm5"] = sw
    p = Params(**BASE, reclaimed_ladder=True)
    i = k0 + 9
    assert sm5.reclaim_order(ctx, sl, i, p, "AM", 1.0) is not None and cap["tags"]["cancel_close"] == pytest.approx(4008.0)
    # a block violated later: the whole ladder is dead for good
    bad = REC_ROWS[:9] + [(4005.0, 4022.0, 4004.0, 4021.0)] + [(4021.0, 4022.0, 4000.0, 4001.0)]
    ctx2, (sl2, _) = mkctx(bad, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    sl2.__dict__["_mm5"] = dict(sw)
    assert sm5.reclaim_order(ctx2, sl2, k0 + 10, p, "AM", 1.0) is None
    assert sl2.__dict__["_rcl_dead"] == {k0 + 8}
    assert sm5.reclaim_order(ctx2, sl2, k0 + 10, p, "AM", 1.0) is None


def test_mit_stair_order_cancel_close(cap):
    rows = [(4000.0, 4004.0, 3999.0, 4003.0), (4003.0, 4008.0, 4002.0, 4005.0), (4005.0, 4006.0, 4001.0, 4002.0), (4002.0, 4003.0, 4000.0, 4001.0), (4001.0, 4012.0, 4000.5, 4011.0),
            (4011.0, 4012.0, 4009.0, 4010.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    k0 = ib(ctx, "09:30")
    assert sm5.mit_stair_order(ctx, sl, k0 + 5, Params(**BASE, mit_stair=True), "AM", 1.0) is not None
    assert cap["tags"]["cancel_close"] == pytest.approx(4002.0)


# --- 98: unknown midnight open rejects -----------------------------------------------------------------------------------------------------------------

def test_mit_cand_rejects_without_the_open(monkeypatch):
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3999.0, 4000.0)] * 3, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    monkeypatch.setattr(S, "_open_known", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(sm5, "_mit_zones", lambda *a, **k: calls.append(1) or [])
    assert sm5.mit_cand(ctx, sl, dict(), ib(ctx, "09:30") + 2, Params(**BASE)) is None and not calls


# --- 72: the pivot filter uses the judged bar -----------------------------------------------------------------------------------------------------------

def test_second_dip_ignores_pivots_unknown_at_i(cap):
    p = Params(**{**BASE, "pivot_n": 9}, rb_second_dip=True)
    ctx, (sl, ss) = mkctx(_dip_rows(), base=4100.0, start="13:30", hist=hist_close(close=4100.0, hi=4130.0, lo=3900.0))
    ctx.sess["lunch"] = (4100.0, 4090.0, 810)
    i = ib(ctx, "13:30") + 8
    ref = sm5.second_dip_order(ctx, sl, i, p, "PM", 1.0)
    ref_cap = dict(cap)
    sl.__dict__.pop("_rb2_sent", None)
    sl.ph = list(sl.ph) + [L.Pivot(ib(ctx, "13:30") + 1, 4120.0, i + 1)]            # a swing high that only becomes known AFTER bar i
    out = sm5.second_dip_order(ctx, sl, i, p, "PM", 1.0)
    assert (ref is None) == (out is None) and (ref is None or cap["stop"] == ref_cap["stop"])


# --- 83: the stale too-wide-stop flag ------------------------------------------------------------------------------------------------------------------

def test_finish_order_clears_a_stale_wide_stop_flag():
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3999.0, 4000.0)] * 4, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    p = Params(**BASE)
    i = ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="x", name="x", level=3999.0, ext=3998.0, ext_i=i - 1, broke=None, sweep_i=i - 1, _wide_stop=True)
    out = S._finish_order(ctx, sl, i, p, "AM", sw, 4000.0, 3999.9999, 1.0, 4001.0, dict())       # risk under the minimum: x_risk_too_small, no wide-stop on this call
    assert out is None and "_wide_stop" not in sw


# --- 69 / 70 tags --------------------------------------------------------------------------------------------------------------------------------------

def test_prev_pm_turtle_kind_families_and_raid_kinds():
    assert "prev_pm_turtle" in SM.TS_KINDS and "prev_pm_turtle" in sm2.STATE_TOOLS["REVERSAL"]
    assert "false_flag" not in sm5.RAID_KINDS and sm5.entry_style("prev_pm_turtle") == "raid" and sm5.entry_style("fvg") == "confirmed"


def test_ts_linger_does_not_treat_prev_pm_as_a_turtle_variant():
    ctx, (sl, ss) = mkctx([(4000.0, 4001.0, 3990.0, 3991.0)] * 6, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", key="pdl1", level=3999.0, ext=3990.0, ext_i=e, sweep_i=e, broke=None)
    i = e + 5
    p = Params(**BASE, ts_linger_bars=2, turtle_soup="prev_pm")
    assert sm3.sweep_step(ctx, sl, dict(sw), i, p) != "drop"                          # five closes under the level: only a real turtle variant is cancelled by lingering
    assert sm3.sweep_step(ctx, sl, dict(sw), i, replace(p, turtle_soup="2023")) == "drop"


# --- 75: no ORG today ----------------------------------------------------------------------------------------------------------------------------------

def test_org_reprice_gate_without_org_today(monkeypatch):
    p = Params(**BASE, org_reprice=True, org_reprice_full=True)
    ctx, (sl, ss) = mkctx([(4003.0, 4004.0, 3990.0, 3992.0)] * 3, base=4005.0, start="10:00", hist=hist_close(close=4005.0, hi=4130.0, lo=3900.0))
    ctx.org, ctx.org_today = [(4020.0, 4000.0)], False
    sw = dict(session="AM", key="pdl1", level=3995.0, ext=3990.0, ext_i=ib(ctx, "10:00"), broke=None, sweep_i=ib(ctx, "10:00"))
    monkeypatch.setattr(sm5, "pools_taken", lambda *a, **k: (2, 2))
    monkeypatch.setattr(S, "_htf_tag", lambda *a, **k: True)
    assert sm5.org_reprice_gate(ctx, sl, sw, ib(ctx, "10:00") + 2, p, "AM", 3995.0, {}) == "x_org_reprice_org"
    ctx.org, ctx.org_today = [], True
    assert sm5.org_reprice_gate(ctx, sl, sw, ib(ctx, "10:00") + 2, p, "AM", 3995.0, {}) == "x_org_reprice_org"


# --- 86: pd50_tf pending cancel on completed higher-timeframe bars --------------------------------------------------------------------------------------

def test_pd50_tf_pending_cancel():
    rows = [(4010.0, 4011.0, 4009.0, 4010.0)] * 6 + [(4010.0, 4010.5, 3995.0, 3996.0)] * 6
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4000.0, hi=4020.0, lo=3980.0))
    e = ib(ctx, "09:30")
    pend = dict(i=e + 1, cancel_close_tf=(4000.0, 15))
    assert sm5.tf_close_cancel(ctx, sl, pend, e + 5) is False                              # the 15m bars (3 x 5m) that completed so far closed at 4010
    assert sm5.tf_close_cancel(ctx, sl, pend, e + 11) is True                              # a completed 15m bar closed under 4000
    p = Params(**BASE, pd50_bodies=True, pd50_tf=15)
    tags = {}
    assert sm5.pd50_gate(ctx, sl, dict(ext=4005.0, ext_i=e), e + 2, p, tags) is None
    assert tags.get("cancel_close_tf") == (4000.0, 15) and "cancel_close" not in tags


# --- 78: the dual-deal split is a post-hoc allocation --------------------------------------------------------------------------------------------------

def test_dual_deal_rows_are_labelled_posthoc():
    def book(sym):
        return pd.DataFrame(dict(date=[pd.Timestamp("2026-06-23").date()], session=["AM"], side=["long"], symbol=[sym], entry_time=[pd.Timestamp("2026-06-23 10:00")], gross=[50.0], costs=[1.0],
                                 net=[49.0], setup=[""], smt=[False]))
    out = B.combine(book("ES"), book("NQ"), dual_deal="split")
    assert set(out.dual_alloc.dropna()) == {"posthoc"} and "POST-HOC" in B.combine.__doc__


# --- the new study variants ----------------------------------------------------------------------------------------------------------------------------

def test_review_study_variants_build():
    D = study.DECISIONS
    for k in ("M1-distribution-stages-lowrisk-short_reentry", "M1-consolidate-at-discount-array_gate", "A14-unicorn-standalone_independent"):
        Params(**D[k])
    assert D["M1-distribution-stages-lowrisk-short_reentry"]["mm_lowrisk_reentry"] == "wick_ce" and D["M1-distribution-stages-lowrisk-short_reentry"]["mm_stage2"] is True
    assert D["M1-consolidate-at-discount-array_gate"]["mm_accum_gate"] is True and D["A14-unicorn-standalone_independent"]["unicorn_independent"] is True


# --- direct truncation (look-ahead) checks ----------------------------------------------------------------------------------------------------------------

def _trunc_equal(rows, fn, cuts, **kw):
    """fn(ctx, side, i) evaluated on the full day and on the day truncated after bar i must agree."""
    for c in cuts:
        full_ctx, (fs, _) = mkctx(rows, **kw)
        part_ctx, (ps, _) = mkctx(rows[:c + 1], **kw)
        a, b = fn(full_ctx, fs, ib(full_ctx, "09:30") + c), fn(part_ctx, ps, ib(part_ctx, "09:30") + c)
        assert a == b, (c, a, b)


def test_ifvg_hunt_ok_truncation():
    rows = [(110.0, 111.0, 109.0, 110.0), (110.0, 112.0, 109.5, 111.0), (111.0, 113.0, 110.0, 112.0), (112.0, 114.0, 111.0, 113.0), (113.0, 114.0, 106.0, 107.0), (107.0, 112.0, 107.0, 111.0),
            (111.0, 113.0, 110.0, 112.0), (112.0, 112.5, 105.5, 106.0), (106.0, 110.0, 106.0, 109.0), (109.0, 111.0, 108.0, 110.0)]
    p = Params(**BASE, ifvg_need_hunt=True)
    for ce in (100.0, 104.0, 108.0):
        _trunc_equal(rows, lambda c, s, i: sm5.ifvg_hunt_ok(c, s, i, p, dict(fvg_i=3, fvg_ce=ce)), range(5, len(rows)), base=110.0)


def test_prev_reh_levels_truncation():
    conf = StubConf(arrays={1: [(4012.0, 3990.0, "D", 0, 0)]})
    rows = [(4003.0, 4004.0, 4002.0, 4003.0)] * 3 + [(4003.0, 4004.0, 3997.0, 3998.0)] * 3 + [(3998.0, 4010.0, 3997.0, 4009.0)]
    p = Params(**BASE, prev_reh_plan=True)

    def fn(c, s, i):
        c.pd["pml"] = 3996.0
        return sm5.prev_reh_levels(c, s, i, p)
    _trunc_equal(rows, fn, range(0, len(rows)), base=4003.0, hist=_reh_hist(), conf=conf)


def test_ab_anchor_truncation():
    rows = [(4010.0, 4020.0, 4008.0, 4015.0), (4015.0, 4016.0, 4005.0, 4006.0), (4006.0, 4007.0, 4000.0, 4001.0), (4001.0, 4012.0, 3999.0, 4011.0), (4011.0, 4013.0, 4009.0, 4012.0)]
    p = Params(**BASE, adv_breaker=True, ab_anchor_lock=True)

    def fn(c, s, i):
        c.cur_session = "AM"
        s.__dict__["_ab5"] = dict(day=c.day, session="AM", A=4000.0, B=4020.0, filled=True)
        return sm5.ab_anchor(c, s, 4000.0, 4012.0, i, p, "AM")
    _trunc_equal(rows, fn, range(1, len(rows)), base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
