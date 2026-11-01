"""Caption-gap review fixes, package setups_models #4/7 (chunk 4/7): complete_model look-ahead guard, lh_array_short -3 SD target / IOFED add / draw requirement, implied-range cancel and add cut,
leg_tfs ordering, big-event skip, lunch NWOG OB entry and long-only, NDOG blocked days. Data-free; no platform-specific paths."""
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, setups as SM, sm2, sm4, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_levels_detectors import BASE
from test_caption_gap_sm1a import hist_close, ib, mkctx, sd_of
from test_caption_gap_sm4a import LH_ROWS, cap  # noqa: F401  (cap: the order recorder fixture)


def test_complete_model_parent_swing_must_be_known():
    """Review fix: the parent-swing test honours `Pivot.known` - a swing high that is an ITL / LTL only because of a LATER swing (known after bar i) is no parent swing at bar i."""
    rows = [(4010.0, 4011.0, 4000.0, 4006.0), (4006.0, 4009.0, 3999.5, 4007.5), (4007.5, 4020.0, 4007.0, 4019.0), (4019.0, 4020.5, 4015.0, 4018.0)]
    ctx, (sl, ss) = mkctx(rows, base=4010.0, hist=hist_close(close=4010.0, hi=4130.0, lo=3900.0))
    e, i = ib(ctx, "09:30") + 1, ib(ctx, "09:30") + 3
    sw = dict(session="AM", key="pdl1", ext=3999.5, ext_i=e, level=4000.0, broke=i, ref_i=ib(ctx, "09:30") + 2)
    tags = dict(entry_kind="breaker", bz_side=(4012.0, 4004.0))
    p = Params(**BASE, complete_model="tag")
    sl._lz["tiers"] = {"stl": ([], []), "itl": ([L.Pivot(sw["ref_i"], 4020.0, i)], []), "ltl": ([], [])}
    assert sm4.complete_model_tag(ctx, sl, sw, i, p, dict(tags), []) is True
    sl._lz["tiers"] = {"stl": ([], []), "itl": ([L.Pivot(sw["ref_i"], 4020.0, i + 5)], []), "ltl": ([], [])}
    assert sm4.complete_model_tag(ctx, sl, sw, i, p, dict(tags), []) is False


def test_lh_array_sd3_target_iofed_and_draw(cap, monkeypatch):
    """Review fix (026 ~01:35:33): lh_array_target "sd3" = the single target is the -3 SD projection of the MSS leg (R's low 4102.5 .. the leg high 4110.5: 4110.5 + 3 x 8); the ladder stays the
    default; lh_array_need_draw requires the draw set this way; lh_array_iofed arms the add at the FIRST gap formed after the fill, on a down-close bar trading into it."""
    hist = hist_close(close=4100.0, hi=4130.0, lo=3900.0)
    p = Params(**BASE, lh_array_short=True, lh_array_target="sd3")
    ctx, (sl, ss) = mkctx(LH_ROWS, base=4100.0, start="14:30", hist=hist)
    i = ib(ctx, "14:30") + len(LH_ROWS) - 1
    assert sm4.lh_array_order(ctx, sl, i, p, "PM", 1.0) is not None
    tgt = 4110.5 + 3.0 * (4110.5 - 4102.5)
    assert cap["fixed"] == [(pytest.approx(S._exit_px(tgt, "array", p)), "array")] and cap["tags"]["sm4"]["kind"] == "lh_array"
    sl.__dict__.pop("_lharr_sent")
    assert sm4.lh_array_order(ctx, sl, i, replace(p, lh_array_target="ladder"), "PM", 1.0) is not None and cap["fixed"] is None
    sl.__dict__.pop("_lharr_sent")
    assert sm4.lh_array_order(ctx, sl, i, replace(p, lh_array_need_draw=True), "PM", 1.0) is None            # no draw set (neutral)
    ctx.cur_bias = 1
    assert sm4.lh_array_order(ctx, sl, i, replace(p, lh_array_need_draw=True), "PM", 1.0) is not None
    # the IOFED add
    r2 = [(4091.0, 4091.5, 4090.0, 4091.0), (4092.0, 4093.0, 4091.0, 4092.5), (4092.5, 4097.0, 4092.4, 4096.5), (4096.5, 4099.0, 4095.5, 4098.0), (4098.0, 4098.5, 4094.0, 4095.0)]
    sd = sd_of(r2)
    armed = []
    monkeypatch.setattr(S, "_arm_add", lambda pos, tr, px, i_, p_, eq, **k: armed.append((px, k.get("size"))))
    pos = dict(fill_i=0, left=10, add=None, stop=4087.0, plan_shares=10, sm4=dict(kind="lh_array", add2=None))
    sm4.manage(ctx, sd, pos, SimpleNamespace(), 4, None, p)
    assert armed == []                                                                                        # off by default
    sm4.manage(ctx, sd, pos, SimpleNamespace(), 4, None, replace(p, lh_array_iofed=True))
    assert armed == [(4095.5, 10)] and pos["sm4"]["add2"] == 3


def test_implied_h_traded_first_cancels_and_add_cut():
    """Review fix (025 ~00:46:41): while the order waits for the premium-to-discount trade, a trade beyond H (the sweep extreme) first cancels it ("dead"); adds stop once a new extreme beyond the
    post-MSS leg printed after the fill (side space: a high over the leg high)."""
    p = Params(**BASE, implied_range_gate=True)
    rows = [(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4004.0, 3995.0, 3996.0), (3996.0, 3999.0, 3994.0, 3998.0)]
    ctx, (sl, ss) = mkctx(rows, base=4001.0, hist=hist_close(close=4001.0, hi=4130.0, lo=3900.0))
    ctx.cur_lock = dict(side=1, target=4040.0, kind="pool", name="pdh1", marked=[])
    e = ib(ctx, "09:30")
    sw = dict(session="AM", ext=4000.0, ext_i=e, key="x", broke=e + 1)
    assert sm4.implied_gate(ctx, sl, sw, [], e + 2, p, "AM")[0] == "dead"
    sd = sd_of([(4001.0, 4003.0, 4000.0, 4002.0), (4002.0, 4010.0, 4001.0, 4009.0), (4009.0, 4012.0, 4008.0, 4011.0), (4011.0, 4034.0, 4010.0, 4033.0)])
    q = replace(p, add_leg_cut=False, add_in_pd=False)
    pos = dict(fill_i=1, leg=(4000.0, 4030.0), left=5, sm4=dict(kind="implied", implied_eq=4020.0))
    assert SM.add_ok(sd, dict(pos, leg=(4000.0, 4035.0)), 4012.0, 3, q) is True
    assert SM.add_ok(sd, pos, 4012.0, 3, q) is False                                                         # a high over the leg high printed after the fill


def test_leg_tfs_order_does_not_matter(monkeypatch):
    """Review fix (022 ~00:43:05): leg_tfs (5, 15) and (15, 5) are the same scan - the highest timeframe first, a narrower gap of a lower one inside it refines it."""
    rows = [(4000.0, 4001.0, 3990.0, 4000.0)] * 3 + [(4000.0, 4020.0, 3999.0, 4019.0)] * 3 + [(4019.0, 4025.0, 4005.0, 4024.0)] * 3
    ctx, (sl, ss) = mkctx(rows, base=4000.0, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    e = ib(ctx, "09:30")
    sw = dict(session="AM", ext=3990.0, ext_i=e, key="x", broke=e + 3)
    z15, inner = L.Zone("bull", 4005.0, 4000.0, e + 8, e + 3), L.Zone("bull", 4004.0, 4002.0, e + 7, e + 5)
    monkeypatch.setattr(sm4, "_tf_fvgs", lambda ctx_, sd_, m: {15: [z15], 5: [inner]}.get(m, []))
    for tfs in ((5, 15), (15, 5)):
        g, added = sm4.leg_tf_gaps(ctx, sl, dict(sw), [], e + 8, Params(**BASE, leg_tfs=tfs))
        assert added == [inner], tfs


def test_big_event_day_uses_the_calendar():
    """Review fix (#12 / #43): a Fed-chair / FOMC / jobs / CPI day (the calendar itself, not a switch) is skipped; an ordinary day is not."""
    from mentorship import calendar as CAL
    from claude_hf.daytypes import events
    p = Params(**BASE)
    chair = sorted(CAL.FED_CHAIR)[-1]
    assert sm4.big_event_day(SimpleNamespace(day=chair), "AM", p, 600) is True
    days = [date(2023, 3, 7) + timedelta(days=k) for k in range(200)]
    quiet = [d for d in days if d.weekday() == 1 and not events(d) and not sm4.big_event_day(SimpleNamespace(day=d), "AM", p, 600)]
    assert quiet


def test_lunch_nwog_ob_entry_and_long_only(cap, monkeypatch):
    """Review fix (046 ~02:07:16): lunch_nwog_entry "ob" = a limit at the body top of a down-close OB inside [NWOG low, NWOG CE] (else the CE); the setup is long-only (no mirrored short)."""
    p = Params(**BASE, lunch_nwog_long=True)
    rows = [(4020.0, 4021.0, 4012.0, 4013.0)] * 60 + [(4013.0, 4014.0, 4006.0, 4007.0), (4007.0, 4008.0, 4004.5, 4006.0), (4004.9, 4005.0, 4001.0, 4002.0), (4002.0, 4005.0, 4001.5, 4004.95)]
    ctx, (sl, ss) = mkctx(rows, base=4020.0, hist=hist_close(close=4020.0, hi=4130.0, lo=3900.0))
    monkeypatch.setattr(sm2, "gap_list", lambda c, i, kinds: [(4010.0, 4000.0, 4005.0)])
    i = ib(ctx, "09:30") + len(rows) - 1
    t = np.array(ctx.t, copy=True)
    t[i] = 710
    ctx.t = t
    assert sm4.lunch_nwog_order(ctx, ss, i, p, 1.0) is None                                                  # the mirrored short is not built
    assert sm4.lunch_nwog_order(ctx, sl, i, p, 1.0) is not None
    assert cap["entry"] == pytest.approx(4004.7)                                                              # the CE sits at / over the close: one tick under the market
    sl.__dict__.pop("_lnw_sent")
    assert sm4.lunch_nwog_order(ctx, sl, i, replace(p, lunch_nwog_entry="ob"), 1.0) is not None
    assert cap["entry"] == pytest.approx(4004.9)                                                              # the body top of the last down-close candle inside the zone


def test_ndog_scalp_skips_a_blocked_day():
    """Review fix (052 ~00:08:18): a blocked day (the jobs day here) has no evening scalp when day_filter is on."""
    from claude_hf.daytypes import events
    d = next(x for x in (date(2023, 1, 6) + timedelta(days=7 * k) for k in range(60)) if "jobs" in events(x))
    p = Params(**BASE, ndog_scalp=True, asia_session=True, day_filter=True)
    ev = pd.DataFrame({"open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]}, index=pd.DatetimeIndex(["2023-01-06 17:00"], tz="America/New_York"))
    assert sm4.ndog_scalp(SimpleNamespace(tf=5), ev, p, d, "ES", {}) == []


def test_trend_day_sees_this_sides_lock_at_the_smt_filter(monkeypatch):
    """Review fix (053 ~00:08:20): at the smt_bias filter site `trend_day` is called with THIS side's lock / bias already set (not the previous side's leftovers): on a real run_day every call at a
    moment the lock exists has cur_lock None or the lock of the side being judged, and cur_bias equal to the lock's side whenever the lock names one."""
    import warnings
    from mentorship import backtest as B
    from test_caption_gap_ld1 import SYN
    from test_caption_gap_sm2b import SYN_BASE
    seen = []
    real = sm4.trend_day

    def spy(ctx, sd, i, p):
        lk = getattr(ctx, "cur_lock", None)
        any_ = getattr(ctx, "cur_lock_any", None)
        seen.append((sd.sign, None if lk is None else lk["side"], None if any_ is None else any_["side"], ctx.cur_bias))
        return real(ctx, sd, i, p)
    monkeypatch.setattr(sm4, "trend_day", spy)
    x, y = B.synthetic(start="2026-04-06", end="2026-04-24", tf=5, seed=4)
    p = Params(**{**SYN, **SYN_BASE, "smt_trend_ignore": True, "smt_bias": "filter", "sick_sister": True})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        B.run(x, 5, "RW", p, partner=y)
    assert seen
    for sign, lock_side, any_side, bias in seen:
        assert lock_side is None or lock_side == sign
        if any_side:
            assert bias == any_side                                                                          # the bias follows the session lock of this bar
