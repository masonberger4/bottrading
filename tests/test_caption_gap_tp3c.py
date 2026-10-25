"""Caption-gap pass, package targets_partials #3/4, part C (review fixes): the unit tests of the fixes to the 33 specs of the chunk - the double-top pair scan over earlier sessions and its draw lock,
the leg-end void fill, the weekly-beyond 'untaken' test, the ADR zone convergence and final precedence, the consolidation / PM time exits, the wide-OR lock, the launch-array record and the
'arm' tag, the no-collapse cap, the sweep-gate reach, the extension anchors, and the SHORT side (mirrored bars through side space) of the helpers that had only long-side tests.
Hand-made bars and stub confluence tables (as test_caption_gap_tp3a.py); nothing here needs market data and no platform-specific paths."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, sm2, strategy as S, targets as TP, tp3
from mentorship.strategy import Params

from test_targets_partials import conf
from test_caption_gap_tp2a import D0, flat, hist_days, mk, side
from test_caption_gap_tp3a import NY, _leg_rows, _mm_ctx, _walk, _day_rows, pk

HITS = sm2.HITS


def mirror(rows):
    """The mirror image of OHLC rows (o, h, l, c) -> (-o, -l, -h, -c): a short book whose side space (sign -1) is the long book."""
    return [(-o, -l, -h, -c) for o, h, l, c in rows]


def ctx_rows(ctx):
    return list(zip(ctx.o, ctx.h, ctx.l, ctx.c))


# --- 126: the double-top pairs over earlier sessions, the 4h scan, the draw lock ----------------------------------------------------------------------

def _session(day, peaks, hours=(10, 11, 12, 13, 14), base_off=5.0):
    """One regular session of 5m bars with a 1h swing high per hour: hour `hours[k]` has its high at `peaks[k]` on the sixth bar, low `peaks[k] - base_off`."""
    idx, o, h, l, c = [], [], [], [], []
    for hr, pk_ in zip(hours, peaks):
        base = pk_ - base_off
        for m in range(12):
            idx.append(pd.Timestamp(f"{day} {hr:02d}:{5 * m:02d}", tz=NY))
            top = pk_ if m == 5 else base + 1.0
            o.append(base), h.append(top), l.append(base), c.append(base)
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c}, index=pd.DatetimeIndex(idx))


def _dt_ctx(today_rows, day=D0, peaks=(4090.0, 4100.0, 4085.0, 4099.75, 4082.0)):
    older = _session("2026-06-18", peaks)
    prev = hist_days(n=1)[0]
    return mk(today_rows, day=day, hist=[older, prev])


def test_double_top_from_an_earlier_session():
    ctx = _dt_ctx(flat(12, 4040.0))
    p = pk(dt_proj=True)
    out = tp3.dt_scan(ctx, 1, 11, p)
    assert [x[:2] for x in out] == [(4100.0, 4120.0)] and not out[0][2] and not out[0][3]
    sd = side(ctx)
    st = {}
    lv = tp3.dt_levels(ctx, sd, 11, p, 4050.0, st)
    assert (4120.0, "proj") in lv and (4100.0, "pool_eq") in lv and not st.get("dt_reached")
    # reached TODAY: the gate; reached in an earlier session only: the target is retired, the side is not done
    today = flat(11, 4040.0) + [(4040.0, 4121.0, 4039.0, 4120.0)]
    ctx_t = _dt_ctx(today)
    st_t = {}
    assert tp3.dt_levels(ctx_t, side(ctx_t), 11, p, 4050.0, st_t) == [] and st_t["dt_reached"]
    old = _session("2026-06-19", (4121.0, 4110.0))
    ctx_o = mk(flat(12, 4040.0), hist=[_session("2026-06-18", (4090.0, 4100.0, 4085.0, 4099.75, 4082.0)), old, hist_days(n=1)[0]])
    st_o = {}
    assert tp3.dt_levels(ctx_o, side(ctx_o), 11, p, 4050.0, st_o) == [] and not st_o.get("dt_reached")
    assert HITS["eval_dt"] >= 1 and HITS["dt_proj"] >= 1


def _day_session(day, am_hi, pm_hi, base=4000.0):
    """09:30 - 15:55 of 5m bars: one spike to am_hi in the 08:00 4-hour bucket (09:30 - 11:55), one to pm_hi in the 12:00 bucket."""
    idx = pd.date_range(f"{day} 09:30", f"{day} 15:55", freq="5min", tz=NY)
    h = np.full(len(idx), base + 1.0)
    h[10] = am_hi
    h[40] = pm_hi
    return pd.DataFrame({"open": base, "high": h, "low": base, "close": base}, index=idx)


def test_double_top_groups_by_equal_clusters_and_scans_4h():
    # three equal peaks on the 1h scale: every neighbouring pair of the cluster is a double top
    older = _session("2026-06-18", (4090.0, 4100.0, 4080.0, 4099.75, 4070.0, 4100.0, 4060.0), hours=(8, 9, 10, 11, 12, 13, 14))
    ctx = mk(flat(12, 4040.0), hist=[older, hist_days(n=1)[0]])
    out = tp3.dt_scan(ctx, 1, 11, pk(dt_proj=True))
    assert len(out) == 2 and {round(x[0], 2) for x in out} == {4100.0} and all(x[5] == 60 for x in out)
    # a peak outside eq_tol is no pair
    older2 = _session("2026-06-18", (4090.0, 4100.0, 4080.0, 4130.0, 4070.0, 4150.0, 4060.0), hours=(8, 9, 10, 11, 12, 13, 14))
    ctx2 = mk(flat(12, 4040.0), hist=[older2, hist_days(n=1)[0]])
    assert tp3.dt_scan(ctx2, 1, 11, pk(dt_proj=True)) == []
    # the 4h scan: the NY-session 4-hour candles (08:00 and 12:00 buckets) of three earlier sessions: highs 4080, 4100 | 4060, 4099.75 | 4050 -> a 4h double top; R = 4100 - 4000
    h4 = [_day_session("2026-06-16", 4080.0, 4100.0), _day_session("2026-06-17", 4060.0, 4099.75), _day_session("2026-06-18", 4050.0, 4040.0), hist_days(n=1)[0]]
    ctx4 = mk(flat(12, 4040.0), hist=h4)
    o4 = [x for x in tp3.dt_scan(ctx4, 1, 11, pk(dt_proj=True)) if x[5] == 240]
    assert o4 and o4[0][:2] == (4100.0, 4200.0)


def test_double_bottom_is_the_mirror():
    ctx = _dt_ctx(flat(12, 4040.0))
    ctx_s = mk(mirror(flat(12, 4040.0)), hist=[pd.DataFrame({"open": -x.open, "high": -x.low, "low": -x.high, "close": -x.close}, index=x.index) for x in ctx.hist])
    a = tp3.dt_scan(ctx, 1, 11, pk(dt_proj=True))
    b = tp3.dt_scan(ctx_s, -1, 11, pk(dt_proj=True))
    assert a == b and a


def test_double_top_projection_locks_the_nearest_sell_side_pool():
    today = flat(11, 4040.0) + [(4040.0, 4121.0, 4039.0, 4120.0)]
    ctx = _dt_ctx(today)
    p = pk(dt_proj=True)
    lk = dict(side=1, target=4150.0, kind="pool", name="pdh1", px=4040.0, delivered=False,
              marked=[(4150.0, "pool", "pdh1", 1), (4030.0, "pool", "pdl1", -1), (4000.0, "pool", "pdl2", -1), (4130.0, "array", "x", 0)])
    spent = []
    nl = tp3.dt_relock(ctx, p, lk, 11, spent)
    assert nl is not None and nl["side"] == -1 and nl["target"] == 4030.0 and nl["name"] == "pdl1" and nl["dt_used"] and spent == [4150.0]
    assert tp3.dt_relock(ctx, p, nl, 11, spent) is None                         # once
    assert tp3.dt_relock(ctx, pk(), lk, 11, []) is None                         # switch off
    ctx_n = _dt_ctx(flat(12, 4040.0))
    assert tp3.dt_relock(ctx_n, p, lk, 11, []) is None                          # the projection has not traded
    # a short lock is not moved by a TOP's projection
    assert tp3.dt_relock(ctx, p, dict(lk, side=-1, target=4000.0), 11, []) is None


# --- 107: a fill inside the bar that confirms the leg ---------------------------------------------------------------------------------------------------

def test_void_filled_in_the_confirming_bar_is_no_target():
    rows = _leg_rows()
    ctx = mk(rows)
    p = pk(void_legs=True)
    assert tp3.void_levels(ctx, side(ctx), 14, p, 4060.0, {}) == [(4085.0, "array"), (4100.0, "array")]
    rows2 = list(rows)
    rows2[12] = (4072.0, 4101.0, 4071.0, 4073.0)                                 # the bar right after the leg already filled the void
    ctx2 = mk(rows2)
    assert tp3.void_levels(ctx2, side(ctx2), 14, p, 4060.0, {}) == []


def test_void_short_side():
    rows = mirror(_leg_rows())                                                   # a bullish one-sided leg: a short's void
    ctx = mk(rows)
    out = tp3.void_levels(ctx, side(ctx, -1), 14, pk(void_legs=True), -4060.0, {})
    assert out == [(4085.0, "array"), (4100.0, "array")]


# --- 109 / 178 / 110 short side ---------------------------------------------------------------------------------------------------------------------

def test_measured_moves_short_side():
    base = _mm_ctx()
    ctx_s = mk(mirror(ctx_rows(base)))
    sd = side(ctx_s, -1)
    p = pk(mm_targets=True, mm_anchor="reanchor")
    assert tp3.mm_levels(ctx_s, sd, 14, p, dict(ext=4010.0, ext_i=11), 4022.0, 4013.0, 4013.0) == [(4040.0, "proj")]
    p2 = pk(mm_targets=True, mm_anchor="impulse")
    assert tp3.mm_levels(ctx_s, sd, 14, p2, dict(ext=4000.0, ext_i=3), 4020.0, 4010.0, 4005.0) == [(4030.0, "proj")]


def test_ob_order_short_side():
    rows = [(4100.0, 4102.0, 4098.0, 4101.0), (4101.0, 4104.0, 4100.0, 4103.0), (4103.0, 4107.0, 4102.0, 4106.0), (4106.0, 4109.0, 4105.0, 4108.0),
            (4111.0, 4116.0, 4110.0, 4115.0), (4114.0, 4114.5, 4108.0, 4109.0), (4109.0, 4111.0, 4104.0, 4105.0), (4105.0, 4107.0, 4101.0, 4102.0), (4102.0, 4104.0, 4099.0, 4100.0)]
    ctx = mk(mirror(rows), conf([(1, -4130.0, -4135.0, np.inf, 1, "1h")], tfs=("1h",)))
    out = tp3.ob_order_levels(ctx, side(ctx, -1), 8, pk(ob_target_order=True), 4100.0, dict(entry_kind="ob_pre"))
    assert [(v, k) for v, k in out][:2] == [(4110.0, "array"), (4116.25, "exact")]


# --- 119: untaken weekly / monthly pools and the weekly pivot ---------------------------------------------------------------------------------------

def _week_frame(day, hi, lo=4000.0):
    idx = pd.date_range(f"{day} 09:30", periods=3, freq="5min", tz=NY)
    return pd.DataFrame({"open": [4050.0] * 3, "high": [hi, 4050.0, 4050.0], "low": [lo] * 3, "close": [4050.0] * 3}, index=idx)


def test_weekly_beyond_untaken_this_week():
    p = pk(weekly_beyond_mode="tag")
    keep = [(4100.25, "pool")]
    plain = [_week_frame("2026-06-08", 4060.0), _week_frame("2026-06-22", 4060.0)]                  # Monday 2026-06-22 is in D0's week (D0 = 2026-06-23)
    ctx = mk(flat(12), pw=(4140.0, 4000.0), pm_=(4300.0, 3900.0), hist=plain)
    assert tp3.weekly_beyond(ctx, side(ctx), 8, p, 4090.0, keep) == (True, True)
    taken = [_week_frame("2026-06-08", 4060.0), _week_frame("2026-06-22", 4141.0)]                  # the PWH was traded on Monday
    ctx_t = mk(flat(12), pw=(4140.0, 4000.0), pm_=(4300.0, 3900.0), hist=taken)
    assert tp3.weekly_beyond(ctx_t, side(ctx_t), 8, p, 4090.0, keep) == (False, True)
    # the monthly high is taken by an earlier session of this month
    taken_m = [_week_frame("2026-06-02", 4301.0), _week_frame("2026-06-22", 4060.0)]
    ctx_m = mk(flat(12), pw=(4140.0, 4000.0), pm_=(4300.0, 3900.0), hist=taken_m)
    assert tp3.weekly_beyond(ctx_m, side(ctx_m), 8, p, 4090.0, keep) == (True, False)


def test_weekly_beyond_weekly_pivot():
    wk = [_week_frame("2026-05-26", 4120.0), _week_frame("2026-06-02", 4180.0), _week_frame("2026-06-09", 4130.0), _week_frame("2026-06-16", 4100.0), _week_frame("2026-06-22", 4060.0)]
    ctx = mk(flat(12), pw=None, pm_=None, hist=wk)
    p = pk(weekly_beyond_mode="tag")
    h0 = HITS.get("weekly_pivot", 0)
    assert tp3.weekly_beyond(ctx, side(ctx), 8, p, 4090.0, [(4100.25, "pool")])[0] is True and HITS["weekly_pivot"] > h0       # the 4180 swing high of the week of 06-02 is untaken
    wk[3] = _week_frame("2026-06-16", 4190.0)                                          # a later week traded above it: not untaken
    ctx2 = mk(flat(12), pw=None, pm_=None, hist=wk)
    assert tp3.weekly_beyond(ctx2, side(ctx2), 8, p, 4090.0, [(4100.25, "pool")])[0] is False


def test_weekly_beyond_short_side():
    ctx = mk(mirror(flat(12)), pw=(-4000.0, -4140.0), pm_=(-3900.0, -4300.0), hist=[_week_frame("2026-06-22", 4060.0)])
    assert tp3.weekly_beyond(ctx, side(ctx, -1), 8, pk(weekly_beyond_mode="tag"), 4090.0, [(4100.25, "pool")]) == (True, True)


# --- 134: the extension anchors, short side, the 100% swing ------------------------------------------------------------------------------------------

def test_cc_extension_short_side_and_symmetrical_swing():
    rows = _walk([4050, 4054, 4060, 4056, 4046, 4041, 4040.5, 4046, 4052, 4058], 0.3)
    rows[2] = (4056.0, 4060.0, 4055.0, 4059.0)
    rows[3] = (4059.0, 4059.5, 4054.0, 4056.0)
    cf = conf([(-1, 4068.0, 4064.0, np.inf, 0, "15m")], tfs=("15m",))
    ctx = mk(rows, cf)
    p = pk(proj_ext_anchor="stop_run", sd_htf_tol=1.0)
    sw = dict(ext=4040.0, ext_i=6)
    long_out = tp3.ext_levels(ctx, side(ctx), 9, p, sw, 4045.0)
    cf_s = conf([(1, -4064.0, -4068.0, np.inf, 0, "15m")], tfs=("15m",))
    ctx_s = mk(mirror(rows), cf_s)
    assert [(round(v, 2), k) for v, k in tp3.ext_levels(ctx_s, side(ctx_s, -1), 9, p, sw, 4045.0)] == [(round(v, 2), k) for v, k in long_out] == [(4065.4, "proj")]
    # the 100% symmetrical swing: 4040 + 1.0 x 20 = 4060 inside an array there
    cf2 = conf([(-1, 4062.0, 4058.0, np.inf, 0, "15m")], tfs=("15m",))
    ctx2 = mk(rows, cf2)
    assert tp3.ext_levels(ctx2, side(ctx2), 9, p, sw, 4045.0) == []
    out = tp3.ext_levels(ctx2, side(ctx2), 9, replace(p, proj_ext_sym=True), sw, 4045.0)
    assert [(round(v, 2), k) for v, k in out] == [(4060.0, "proj")]


# --- 156 / 159: the ADR convergence zone, the precedence of the finals -----------------------------------------------------------------------------

def _adr_ctx(cf, last_high=4041.0, **kw):
    rows = [(4010.0, 4012.0, 4000.0, 4008.0)] + [(4008.0, 4015.0, 4006.0, 4012.0)] * 5 + [(4012.0, last_high, 4010.0, 4030.0)] * 2
    kw.setdefault("opens", {})
    return mk(rows, cf, hist=hist_days(n=6, rng=40.0), **kw)


def test_adr_convergence_accepts_a_projection_inside_the_zone():
    cf = conf([(-1, 4044.0, 4038.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf)
    p = pk(adr_conv_target=True)
    st = {}
    out = tp3.raw_post(ctx, side(ctx), 7, p, "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, [(4020.0, "pool"), (4042.0, "sd"), (4065.0, "array")], [], {}, st)
    assert st["adr_final"] == 4042.0 and (4042.0, "proj_htf") in out and st["adr_zone"] == (4038.0, 4044.0)         # ADR high 4040 sits in the zone; the SD level at 4042 is in it too
    st2 = {}
    tp3.raw_post(ctx, side(ctx), 7, p, "AM", 4020.0, 4.0, 4015.0, dict(ext=4001.0, ext_i=0), 4030.0, [(4020.0, "pool"), (4047.0, "sd")], [], {}, st2)
    assert "adr_final" not in st2                                                    # 4047 is outside the zone by more than the tolerance


def test_adr_rungs_need_adr_target():
    cf = conf([(-1, 4055.0, 4051.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf, last_high=4041.0)
    sd = side(ctx)
    assert tp3.adr_levels(ctx, sd, 7, pk(adr_t2_htf=True, adr_ext=True), 4020.0, 4020.0, {}) == []
    assert tp3.adr_levels(ctx, sd, 7, pk(adr_t2_htf=True, adr_ext=True, adr_target=True, adr_frac=1.0), 4020.0, 4020.0, {})


def test_finals_have_an_explicit_precedence():
    cf = conf([(-1, 4044.0, 4038.0, np.inf, 0, "1h")], tfs=("1h",))
    ctx = _adr_ctx(cf)
    sd = side(ctx)
    p = pk(adr_conv_target=True, grades60=True)
    keep = [(4025.0, "pool"), (4039.75, "sd"), (4064.5, "array")]
    st = dict(adr_final=4040.0, void_final=4064.5, grades=[4060.0], grade_through=True)
    lvt = []
    why, k2, draw, _ = tp3.late(p=p, ctx=ctx, sd=sd, sw=dict(ext=4001.0, ext_i=0), i=7, session="AM", entry=4020.0, risk=4.0, keep=keep, keep_full=[], draw=4064.5, final_T=False, lvt=lvt, tags={},
                                st=st, locked=False, fixed=None)
    assert why is None and "adr_conv_final" in lvt and "void_final" not in lvt and "grade_final" not in lvt and k2[-1][1] == "proj_htf"


# --- 169 / 170 / 172 / 175 --------------------------------------------------------------------------------------------------------------------------

def test_consol_trade_is_out_at_eleven():
    from test_caption_gap_tp3a import _overnight_rows, mk_at
    rows = _overnight_rows()
    dplan = SimpleNamespace(tags=("consol_day",), info={})
    ctx = mk_at(rows, start="2026-06-23 04:00", dplan=dplan, sess={"london": (4015.0, 3998.0, 300)})
    keep = [(4009.0, "array"), (4030.25, "pool")]
    tags = {}
    why, k2, draw, _ = tp3.late(p=pk(consol_overnight_targets=True), ctx=ctx, sd=side(ctx), sw=dict(ext=4004.0, ext_i=60), i=len(rows) - 1, session="AM", entry=4006.0, risk=1.0, keep=keep, keep_full=keep,
                                draw=4030.25, final_T=False, lvt=[], tags=tags, st={}, locked=False, fixed=None)
    assert why is None and tags["exit_at"] == 660 and tags["single_exit"]


def test_wide_or_end_is_the_session_lock(monkeypatch):
    from test_caption_gap_tp3a import _or_rows
    rows = _or_rows() + [(4006.0, 4009.0, 4003.0, 4007.0)] * 4
    ctx = mk(rows, hist=hist_days(n=20, rng=12.0))
    p = pk(wide_or_draw=True, htf_bias="draw")
    lk = dict(side=-1, target=3990.0, kind="pool", name="pdl1", px=4005.0, delivered=False, marked=[])
    i = 13
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: 1)
    nl = tp3.wide_or_relock(ctx, p, lk, i, "AM")
    assert nl is not None and nl["side"] == 1 and nl["target"] == 4040.0 and nl["name"] == "wide_or_end" and nl["wo_used"]
    assert tp3.wide_or_relock(ctx, p, nl, i, "AM") is None                         # once
    assert tp3.wide_or_relock(ctx, pk(wide_or_draw=True), lk, i, "AM") is None     # htf_bias off: inert
    assert tp3.wide_or_relock(ctx, p, lk, 9, "AM") is None                         # the OR60 is not complete
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: -1)
    nl2 = tp3.wide_or_relock(ctx, p, lk, i, "AM")
    assert nl2 is not None and nl2["side"] == -1 and nl2["target"] == 4000.0         # a bearish bias: the OR60 LOW (4000) replaces the 3990 pool
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: 0)
    assert tp3.wide_or_relock(ctx, p, lk, i, "AM") is None
    # the OR end already taken after 10:30: no lock
    rows3 = rows[:12] + [(4006.0, 4041.0, 4005.0, 4020.0)] + rows[13:]
    ctx3 = mk(rows3, hist=hist_days(n=20, rng=12.0))
    monkeypatch.setattr(S._BD, "want_at", lambda ctx_, p_, session, i_: 1)
    assert tp3.wide_or_relock(ctx3, p, lk, i, "AM") is None


def test_wide_or_short_side():
    from test_caption_gap_tp3a import _or_rows
    hist = hist_days(n=20, rng=12.0)
    ctx = mk(_or_rows(), hist=hist)
    ctx_s = mk(mirror(_or_rows()), hist=[pd.DataFrame({"open": -x.open, "high": -x.low, "low": -x.high, "close": -x.close}, index=x.index) for x in hist])
    p = pk(wide_or_draw=True, htf_bias="draw")
    a, b = tp3.or_wide(ctx, side(ctx), 11, p), tp3.or_wide(ctx_s, side(ctx_s, -1), 11, p)
    assert a == b == (4040.0, 4000.0)


def test_launch_array_is_recorded_once_and_pm_trades_arm_there():
    from test_caption_gap_tp3a import _launch_ctx
    ctx = _launch_ctx("D")
    p = pk(pm_launch_filter=True)
    i = len(ctx.c) - 1
    sd_long = side(ctx)                                          # a PM LONG after an AM rally launched from the bullish daily array 3995-4005
    assert tp3.launch_arm(ctx, sd_long, i, p, 4001.0) is True
    assert tp3.launch_arm(ctx, sd_long, i, p, 4030.0) is False   # outside the array
    assert 1 in ctx._tp3_launch                                  # recorded once (the call is at or after 13:30)
    ctx._tp3_launch[1] = None                                    # the cache is what later calls read
    assert tp3.launch_arm(ctx, sd_long, i, p, 4001.0) is False
    ctx15 = _launch_ctx("15m")
    assert tp3.launch_arm(ctx15, side(ctx15), i, p, 4001.0) is False      # only 4h / D / W arrays are supports


def test_hold_to_obj_is_exempt_from_the_pm_time_exit():
    pos = {}
    tp3.on_fill(None, None, pos, None, {"tp3_hold": True}, 0, pk())
    assert pos["tp3"]["hold_obj"] and not pos["tp3"]["speed"]
    pos2 = {}
    tp3.on_fill(None, None, pos2, None, {"tp3_speed": True}, 0, pk())
    assert pos2["tp3"]["speed"] and not pos2["tp3"]["hold_obj"]
    p = pk(session_obj_tf=True)
    ctx = mk(flat(12), conf([(-1, 4050.0, 4045.0, np.inf, 0, "1h")], tfs=("1h",)))
    ctx.cur_lock = {"name": "obj_1h"}
    keep = [(4020.0, "pool")]
    tags = {}
    r = tp3.pm_gate_targets(ctx, side(ctx), dict(ext=3990.0, ext_i=1), 8, p, "PM", 4000.0, 2.0, keep, keep, 4020.0, True, [], tags)
    assert r is not None and tags["tp3_hold"] and tags["exit_at"] == 945


# --- 38 / 37 ------------------------------------------------------------------------------------------------------------------------------------------

def test_no_collapse_caps_the_last_rung_at_the_draw():
    cf = conf([(-1, 4130.0, 4140.0, np.inf, 0, "D")], tfs=("D",))
    ctx = mk(flat(12), cf)
    sd = side(ctx)
    p = pk(no_collapse_htf=True, no_collapse_keep=0.2)
    keep = [(4110.0, "array"), (4125.0, "pool"), (4160.0, "array")]
    h0 = HITS.get("no_collapse_cap", 0)
    r = tp3.no_collapse(ctx, sd, 8, p, 4090.0, keep, None, {})
    assert r is not None
    k2, fr = r
    hx = S._exit_px(4130.0, "array", p)
    assert k2[-1] == (hx, "array") and [v for v, _ in k2] == [4110.0, 4125.0, hx] and fr[-1] >= 0.2 - 1e-9 and sum(fr) == pytest.approx(1.0) and HITS["no_collapse_cap"] > h0


def test_sweep_gate_reach():
    # a daily bearish array 4130-4140 above the swept pool 4000; ADR5 = 20: 3 x ADR5 = 60 -> out of reach, nothing blocks the reversal
    cf = conf([(-1, 4140.0, 4130.0, np.inf, 0, "D")], tfs=("D",))
    ctx = mk(flat(12), cf)
    sd = side(ctx, -1)
    p = pk(pool_milestone=0.5, htf_bias="draw")
    assert tp3.sweep_gate(ctx, sd, dict(ext=-4000.0, level=-4000.0), 8, p, "AM", want=1) is None
    cf2 = conf([(-1, 4050.0, 4040.0, np.inf, 0, "D")], tfs=("D",))
    ctx2 = mk(flat(12), cf2)
    assert tp3.sweep_gate(ctx2, side(ctx2, -1), dict(ext=-4000.0, level=-4000.0), 8, p, "AM", want=1) == "x_htf_untraded"


# --- 35: the speed exception, one step per bar -------------------------------------------------------------------------------------------------------

def test_speed_state_pays_when_not_both_bars_are_big():
    n = 30
    o = np.full(n, 4100.0)
    h, l, c = o + 0.5, o - 0.5, o.copy()
    h[28], l[28], c[28] = 4112.0, 4099.0, 4111.0
    sd = S.Side(1, o, h, l, c, 1, 0.0)                      # the touch bar is big, the next one quiet
    pos = dict(fracs=(0.5, 0.5), level_kinds=["pool", "pool"], tp3=dict(speed=True), k=0)
    p = pk(exit_mode2="pay_first", speed_skip=True)
    assert tp3.speed_hold(pos, 0, 28, sd, p) and tp3.speed_state(pos, 0, [4110.0, 4120.0], 29, sd, p) == "pay"
    assert pos["fracs"] == (0.5, 0.5) and pos["tp3"]["pend"] is None


def test_hold_runner_exit_time_and_frozen_stop():
    p = pk(exit_mode2="hold_runner")
    ctx = mk(flat(12))
    kw = dict(ctx=ctx, sd=side(ctx), sw=dict(ext=4096.0, ext_i=2), i=8, session="AM", entry=4100.0, risk=2.0, keep=[(4110.25, "pool"), (4120.25, "pool")], keep_full=[], draw=4110.25, final_T=False, lvt=[],
              st={}, locked=False, fixed=None)
    tags = {}
    tp3.late(p=p, tags=tags, **kw)
    assert tags["exit_at"] == 900 and tags["day_trade"]
    tags = {"exit_at": 840}
    tp3.late(p=p, tags=tags, **kw)
    assert tags["exit_at"] == 840                                      # an earlier exit is kept
    from mentorship import manage as MG
    pos = dict(day_trade=True, stop=4096.0, basis=4100.0, n=1)
    MG.be_move(pos, p)
    assert pos["stop"] == 4096.0                                       # the be_at move goes through be_move: a day trade never moves its stop
