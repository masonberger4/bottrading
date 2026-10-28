"""Caption-gap pass, package bias_htf#1/7: the table columns (lean, weekly PO3, run extreme, PWH give-back, wick CE, stacked gaps, NWOG reference, joint weekly ITH), the futures-frame generators
and the table integration (third file of tests/test_caption_gap_bh1.py). No market data is read."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh1 as BH, bias_htf as BX, htf, levels as L
from mentorship.strategy import Params

from test_review_fixes import BASE  # noqa: E402
from test_caption_gap_bh1 import dsess, arr, K, mirror_book, mirror_arr, week_book, weekly_arrs, NAN  # noqa: E402

NY = "America/New_York"


# --- synthetic 24-hour futures frames (an evening reopen, so htf.table builds) ---------------------------------------------------------

def fut_frame(daily, start=date(2026, 1, 5), tf=5, seed=0, wick=0.0):
    """5m bars from each session's previous-day 18:00 to 16:10 (the ES frame shape) following the given session (open, high, low, close) rows: piecewise-linear closes through the waypoints
    open -> low -> high -> close (high first when the session closes down), the session extremes exact. `wick` adds random wicks (never beyond the session extremes)."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=len(daily))
    out = []
    for d_, (o, h, l, c) in zip(days, daily):
        t0 = pd.Timestamp(d_.date(), tz=NY) - pd.Timedelta(hours=6)                      # 18:00 the evening before
        t1 = pd.Timestamp(d_.date(), tz=NY) + pd.Timedelta(hours=16, minutes=15)
        idx = pd.date_range(t0, t1, freq=f"{tf}min", inclusive="left")
        idx = idx[~((idx.hour == 17) | ((idx.hour == 16) & (idx.minute >= 15)))]                 # the 17:00 break is not in the frame
        n = len(idx)
        way = [o, l, h, c] if c >= o else [o, h, l, c]
        pos = [0, n // 3, 2 * n // 3, n - 1]
        cl = np.interp(np.arange(n), pos, way)
        op = np.r_[o, cl[:-1]]
        hi, lo = np.maximum(op, cl), np.minimum(op, cl)
        if wick:
            hi = np.minimum(hi + rng.random(n) * wick, max(h, o, c))
            lo = np.maximum(lo - rng.random(n) * wick, min(l, o, c))
            hi = np.maximum(hi, np.maximum(op, cl))
            lo = np.minimum(lo, np.minimum(op, cl))
        out.append(pd.DataFrame({"open": op, "high": hi, "low": lo, "close": cl, "volume": 1.0}, index=idx))
    return pd.concat(out)


def fut_walk(start, end, seed=0, tf=5, price=4000.0, vol=0.45):
    """A random-walk 24-hour futures frame (the evening reopen to 16:10) for the no-look-ahead runs: U-shaped intraday volatility, wicks, drifting regimes."""
    rng = np.random.default_rng(seed)
    out, px = [], price
    for d_ in pd.bdate_range(start, end):
        t0 = pd.Timestamp(d_.date(), tz=NY) - pd.Timedelta(hours=6)
        t1 = pd.Timestamp(d_.date(), tz=NY) + pd.Timedelta(hours=16, minutes=15)
        idx = pd.date_range(t0, t1, freq=f"{tf}min", inclusive="left")
        idx = idx[~((idx.hour == 17) | ((idx.hour == 16) & (idx.minute >= 15)))]
        n = len(idx)
        m = (idx.hour * 60 + idx.minute).values
        scale = np.where((m >= 570) & (m < 660), 1.8, np.where((m >= 540) & (m < 570), 1.3, np.where((m >= 900) & (m < 960), 1.4, np.where(m < 360, 0.9, 1.0))))
        drift = rng.normal(0, 0.01) * np.ones(n)
        step = rng.normal(drift, vol * scale)
        cl = px + np.cumsum(step)
        op = np.r_[px, cl[:-1]]
        hi = np.maximum(op, cl) + np.abs(rng.normal(0, vol * 0.5 * scale))
        lo = np.minimum(op, cl) - np.abs(rng.normal(0, vol * 0.5 * scale))
        out.append(pd.DataFrame({"open": op, "high": hi, "low": lo, "close": cl, "volume": 1.0}, index=idx))
        px = float(cl[-1])
    return pd.concat(out)


def test_fut_frame_makes_the_expected_sessions():
    daily = [(4000, 4010, 3990, 4005), (4005, 4020, 3995, 4000), (4000, 4030, 3980, 4025)]
    df = fut_frame(daily)
    s = htf.sessions(df)
    assert list(s.itertuples(index=False, name=None)) == [(float(o), float(h), float(l), float(c)) for o, h, l, c in daily]
    assert htf.has_overnight(df)
    days = B.days(df, 5, False, 975)
    assert len(days) == 3 or len(days) == 4                         # the first calendar day's frame holds the evening only from the day before (cut off)


# --- item 6: the neutral lean -------------------------------------------------------------------------------------------------------

def test_neutral_lean_column():
    bear = arr("bear", "fvg", 4040, 4030, 1)                                 # a daily premium array 4030-4040
    book = [(4000, 4010, 3990, 4005), (4005, 4015, 3995, 4010), (4010, 4020, 4000, 4015), (4015, 4022, 4005, 4018), (4018, 4025, 4008, 4020), (4020, 4026, 4010, 4022),
            (4022, 4029, 4012, 4025), (4025, 4031, 4015, 4027)]                # highs 4029 / 4031 probe the array, the closes stay under 4040
    d = dsess(book)
    assert BH.lean_columns([8], [4028.0], d, [bear], 2, 5.0) == [-1]
    assert BH.lean_columns([8], [4000.0], d, [bear], 2, 5.0) == [0]            # price not at the array
    book2 = book[:6] + [(4022, 4029, 4012, 4025), (4025, 4045, 4015, 4042)]    # a daily close above the array: dead
    assert BH.lean_columns([8], [4028.0], dsess(book2), [bear], 2, 5.0) == [0]
    book3 = book[:6] + [(4022, 4015, 4012, 4013), (4013, 4031, 4005, 4027)]   # the session before probed nothing
    assert BH.lean_columns([8], [4028.0], dsess(book3), [bear], 2, 5.0) == [0]
    # the mirror at a discount array
    bull = mirror_arr(bear)
    assert BH.lean_columns([8], [K - 4028.0], dsess(mirror_book(book)), [bull], 2, 5.0) == [1]


# --- item 64: the weekly PO3 ---------------------------------------------------------------------------------------------------------

def test_wk_po3():
    fvg = arr("bull", "fvg", 4090, 4080, 1)
    pre = [(4090, 4100, 4085, 4098)] * 5                                       # week 1
    wk = [(4100, 4105, 4085, 4095), (4095, 4112, 4093, 4110), (4110, 4115, 4100, 4112), (4112, 4118, 4105, 4110), (4110, 4120, 4108, 4118)]    # Mon trades to 4085 (the FVG), Tue closes 4110 above the open 4100
    d = dsess(pre + wk, start=date(2026, 3, 9))                                # the week of Mar 9: no NFP
    r = BH.wk_po3_column([6, 7, 8], d, [fvg])
    assert r == [0, 1, 1]                                                      # Tue: the Monday close 4095 is still under the open; Wed: the Tuesday close is above it
    d_nfp = dsess(pre + wk, start=date(2026, 2, 23))                           # the week of Mar 2 holds NFP on Friday Mar 6: wk_po3 waits until Friday
    assert BH.wk_po3_column([6, 7, 8, 9], d_nfp, [fvg])[:3] == [0, 0, 0]
    assert BH.wk_po3_column([9], d_nfp, [fvg]) == [1]                          # Friday itself (the NFP day): the reading stands
    # the mirror
    dm = dsess(mirror_book(pre + wk), start=date(2026, 3, 9))
    assert BH.wk_po3_column([6, 7, 8], dm, [mirror_arr(fvg)]) == [0, -1, -1]
    # the engine blocks the other side and locks toward the weekly draw
    from mentorship.bh1e import side_ok, lock_post
    from test_caption_gap_dwc1 import mk, at
    from test_review_fixes import D0, history
    from test_caption_gap_bh1 import BR
    p = Params(**BASE, wk_po3=True)
    ctx = mk(D0, history(D0), p, rows=[], bias_row=BR(wk_po3=1))
    i = at(ctx, "10:00")
    assert side_ok(ctx, p, -1, "AM", i) == "x_bh1_wk_po3" and side_ok(ctx, p, 1, "AM", i) is None
    lock = dict(side=-1, target=95.0, kind="pool", name="pdl1", marked=[(95.0, "pool", "pdl1", -1), (110.0, "pool", "pdh1", 1)], delivered=False)
    out = lock_post(ctx, p, BR(wk_po3=1, wk_draw_up=120.0), 570, "AM", at(ctx, "09:30"), 100.0, lock, [])
    assert out["side"] == 1 and out["target"] == 120.0 and out["name"] == "wk_po3_draw"
    lock2 = dict(side=-1, target=95.0, kind="pool", name="pdl1", marked=[(95.0, "pool", "pdl1", -1), (110.0, "pool", "pdh1", 1)], delivered=False)
    assert lock_post(ctx, p, BR(wk_po3=1), 570, "AM", at(ctx, "09:30"), 100.0, lock2, [])["target"] == 110.0       # no weekly draw level: the nearest buy-side pool


# --- item 65: a run, then consolidation ---------------------------------------------------------------------------------------------------

def test_run_extreme_lean():
    book = [(4000, 4010, 3990, 4005), (4005, 4020, 3980, 4015), (4015, 4090, 3995, 4085), (4085, 4130, 4080, 4125), (4125, 4160, 4120, 4150), (4150, 4180, 4140, 4170),
            (4170, 4175, 4150, 4160), (4160, 4170, 4155, 4165), (4165, 4168, 4158, 4166)]
    d = dsess(book)
    a5 = pd.Series(d.high.values - d.low.values).rolling(5).mean().shift(1).values
    r = BH.run_columns([8], d, a5)
    assert r["run_hi_draw"] == [4180.0] and r["run_lo_draw"][0] != r["run_lo_draw"][0]       # a 200-pt leg, then 2 inside days: the run high is the minimum draw
    book2 = book[:7] + [(4160, 4200, 4155, 4190), (4190, 4195, 4185, 4192)]                    # the second day broke out: no draw
    d2 = dsess(book2)
    assert BH.run_columns([8], d2, pd.Series(d2.high.values - d2.low.values).rolling(5).mean().shift(1).values)["run_hi_draw"][0] != 4180.0
    book3 = book[:7]                                                                           # only one inside day yet
    d3 = dsess(book3)
    assert BH.run_columns([6], d3, pd.Series(d3.high.values - d3.low.values).rolling(5).mean().shift(1).values)["run_hi_draw"][0] != 4180.0
    dm = dsess(mirror_book(book))
    am = pd.Series(dm.high.values - dm.low.values).rolling(5).mean().shift(1).values
    rm = BH.run_columns([8], dm, am)
    assert rm["run_lo_draw"] == [K - 4180.0]
    # the engine: a neutral lock goes toward it until it is taken
    from mentorship.bh1e import lock_post
    from test_caption_gap_dwc1 import mk, at
    from test_review_fixes import D0, history
    from test_caption_gap_bh1 import BR
    p = Params(**BASE, run_extreme_lean=True)
    ctx = mk(D0, history(D0), p, rows=[], bias_row=BR(run_hi_draw=110.0))
    lock = dict(side=0, target=None, kind="", name="", marked=[], delivered=False)
    out = lock_post(ctx, p, BR(run_hi_draw=110.0), 570, "AM", at(ctx, "09:30"), 100.0, lock, [])
    assert out["side"] == 1 and out["target"] == 110.0 and "run_extreme" in out["bh1"]
    lock2 = dict(side=-1, target=90.0, kind="pool", name="pdl1", marked=[(90.0, "pool", "pdl1", -1)], delivered=False)
    assert lock_post(ctx, p, BR(run_hi_draw=110.0), 570, "AM", at(ctx, "09:30"), 100.0, lock2, [])["side"] == -1       # only a neutral lock leans


# --- item 66: the PWH run and give-back ------------------------------------------------------------------------------------------------

def test_pwh_giveback():
    w1 = [(4150, 4170, 4140, 4160)] * 5
    w2 = [(4160, 4175, 4150, 4165), (4165, 4180, 4160, 4175), (4175, 4180, 4125, 4130), (4130, 4140, 4100, 4130), (4130, 4150, 4120, 4140)]      # high 4180 above the PWH 4170, low 4100, the close 4130 under the midpoint 4140
    d = dsess(w1 + w2)
    bisi = arr("bull", "fvg", 4090, 4060, 3, tf="W", ce=4075)
    w = htf.weeks(d)
    r = BH.pwh_columns([8, 9], d, w, [bisi], 0.5)
    assert r["pwh_giveback"] == [1, 1]                                     # Thursday's row reads Mon-Wed: high 4180 > 4170, low 4125, the close 4130 < 4125 + 0.5 x 55
    assert r["pwh_cand"] == [4075.0, 4075.0]
    r0 = BH.pwh_columns([7], d, w, [bisi], 0.5)
    assert r0["pwh_giveback"] == [0]                                       # Wednesday: the prior close 4175 has not given anything back
    r2 = BH.pwh_columns([9], d, w, [bisi], 0.9)
    assert r2["pwh_giveback"] == [0]                                       # a 90 % threshold: not yet
    far = arr("bull", "fvg", 4300, 4290, 3, tf="W")
    assert BH.pwh_columns([9], d, w, [far], 0.5)["pwh_cand"][0] != BH.pwh_columns([9], d, w, [far], 0.5)["pwh_cand"][0]      # no weekly BISI under price: no candidate
    dm = dsess(mirror_book(w1 + w2))
    wm = htf.weeks(dm)
    assert BH.pwh_columns([9], dm, wm, [mirror_arr(bisi)], 0.5)["pwh_giveback"] == [-1]
    # the lock candidate
    from mentorship.bh1e import lock_cands
    p = Params(**BASE, pwh_giveback_draw=True)
    c = lock_cands(None, p, dict(pwh_giveback=1, pwh_cand=4075.0), 570, 0)
    assert c == [(4075.0, "array", "pwh_bisi_ce", 0, 0)]
    assert lock_cands(None, p, dict(pwh_giveback=0, pwh_cand=4075.0), 570, 0) == []


# --- items 46 / 47: the wick CE draw and the stacked gaps -----------------------------------------------------------------------------

def test_wick_ce_draw():
    # a weekly candle 3985 / 4000 / 3950 / 3970: lower wick 3950-3970 (the body low is 3970), CE 3960; later weeks stay above it
    wk = [(3985, 4000, 3950, 3970), (3975, 4010, 3975, 4000), (4000, 4040, 4000, 4030), (4030, 4080, 4030, 4070), (4070, 4120, 4070, 4110)]
    d = week_book(wk)
    w = htf.weeks(d)
    n = len(d)
    out = pd.DataFrame(dict(draw_ord=[0], draw_ord_kind=[""], pd=[-1], draw_ord_lvl=[NAN], draw_ord_name=[""], draw_ext_lvl=[NAN], draw_ext_name=[""]))
    BH.wick_columns(out, [n], [4115.0], d, w)
    r = out.iloc[0]
    assert (r.draw_ord, r.draw_ord_lvl, r.draw_ext_lvl, r.draw_ord_kind) == (-1, 3960.0, 3950.0, "wick")
    out2 = pd.DataFrame(dict(draw_ord=[-1], draw_ord_kind=["ineff"], pd=[-1], draw_ord_lvl=[4000.0], draw_ord_name=["D_fvg"], draw_ext_lvl=[NAN], draw_ext_name=[""]))
    BH.wick_columns(out2, [n], [4115.0], d, w)
    assert out2.iloc[0].draw_ord_lvl == 4000.0 and out2.iloc[0].draw_ord_kind == "ineff"             # an inefficiency decides: untouched
    wk_taken = wk[:1] + [(3975, 3980, 3955, 3957)] + wk[2:]                                             # a later week traded through the CE 3960: taken, no draw
    d2 = week_book(wk_taken)
    out3 = pd.DataFrame(dict(draw_ord=[0], draw_ord_kind=[""], pd=[-1], draw_ord_lvl=[NAN], draw_ord_name=[""], draw_ext_lvl=[NAN], draw_ext_name=[""]))
    BH.wick_columns(out3, [len(d2)], [4115.0], d2, htf.weeks(d2))
    assert out3.iloc[0].draw_ord_kind != "wick" or out3.iloc[0].draw_ord_lvl != 3960.0
    # the mirror: a bullish draw to the nearest upper wick's CE
    dm = week_book(mirror_book(wk))
    out4 = pd.DataFrame(dict(draw_ord=[0], draw_ord_kind=[""], pd=[1], draw_ord_lvl=[NAN], draw_ord_name=[""], draw_ext_lvl=[NAN], draw_ext_name=[""]))
    BH.wick_columns(out4, [len(dm)], [K - 4115.0], dm, htf.weeks(dm))
    assert (out4.iloc[0].draw_ord, out4.iloc[0].draw_ord_lvl, out4.iloc[0].draw_ext_lvl) == (1, K - 3960.0, K - 3950.0)
    # the lock candidates
    from mentorship.bh1e import lock_cands
    p = Params(**BASE, wick_ce_draw=True)
    c = lock_cands(None, p, dict(draw_ord_kind="wick", draw_ord_lvl=3960.0, draw_ext_lvl=3950.0), 570, 7)
    assert [x[2] for x in c] == ["wick_ce_draw", "wick_ext"]


def test_stack_far_draw():
    ex = dict(draw_ord=-1, draw_ord_kind="ineff", draw_ord_lvl=4430.0, draw_ord_name="D_fvg")
    BH.stack_far_post(ex, [], [(20.0, "D_fvg", 4430.0), (70.0, "D_fvg", 4380.0)])
    assert ex["draw_ord_lvl"] == 4380.0 and ex["draw_mid_lvl"] == 4430.0                          # price 4450: the farther gap's near edge, the nearer one's as the partial rung
    ex2 = dict(draw_ord=-1, draw_ord_kind="ineff", draw_ord_lvl=4430.0, draw_ord_name="D_fvg")
    BH.stack_far_post(ex2, [], [(20.0, "D_fvg", 4430.0), (40.0, "PDL", 4410.0), (70.0, "D_fvg", 4380.0)])
    assert ex2["draw_ord_lvl"] == 4430.0 and ex2["draw_mid_lvl"] != ex2["draw_mid_lvl"]            # another draw between them: no stack
    ex3 = dict(draw_ord=1, draw_ord_kind="ineff", draw_ord_lvl=4470.0, draw_ord_name="D_fvg")
    BH.stack_far_post(ex3, [(20.0, "D_fvg", 4470.0), (70.0, "D_fvg", 4520.0)], [])
    assert ex3["draw_ord_lvl"] == 4520.0 and ex3["draw_mid_lvl"] == 4470.0
    ex4 = dict(draw_ord=-1, draw_ord_kind="liq", draw_ord_lvl=4400.0, draw_ord_name="PDL")
    BH.stack_far_post(ex4, [], [(20.0, "D_fvg", 4430.0), (70.0, "D_fvg", 4380.0)])
    assert ex4["draw_ord_lvl"] == 4400.0                                                              # only an inefficiency pick is rewritten
    from mentorship.bh1e import targets_post
    from test_caption_gap_dwc1 import mk, at
    from test_review_fixes import D0, history
    from test_caption_gap_bh1 import BR
    import mentorship.strategy as S
    p = Params(**BASE, stack_far=True)
    ctx = mk(D0, history(D0), p, rows=[], bias_row=BR(draw_mid_lvl=4430.0, draw_ord=-1))
    ctx.cur_session = "AM"
    short_ = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1)
    lv = targets_post(ctx, short_, at(ctx, "10:00"), p, -4450.0, [(-4380.0, "array")])
    assert (-4430.0, "array") in lv                                                                    # the nearer gap's near edge is a rung (side space)


# --- item 12: the NWOG that holds the bias state ---------------------------------------------------------------------------------------------

def test_nwog_flip_edge():
    d = dsess([(4100, 4110, 4090, 4095)] * 4 + [(4095, 4100, 4085, 4090), (4090, 4108, 4085, 4105), (4105, 4120, 4100, 4112), (4112, 4115, 4105, 4110), (4110, 4120, 4105, 4115), (4115, 4120, 4110, 4118)])
    wk = d.index.to_period("W-FRI")
    og = pd.DataFrame(dict(kind=["nwog", "nwog"], high=[4110.0, 4210.0], low=[4100.0, 4200.0], ce=[4105.0, 4205.0], up=[True, True], known=[0, 0], week=[wk[0], wk[5]]))
    ks = np.array([5, 6, 7])
    px = np.array([9999.0, 9999.0, 9999.0])
    res = {}
    for ref in ("current", "previous"):
        for rec in ("low", "high"):
            out = pd.DataFrame(index=[d.index[k].date() for k in ks], data=dict(px=px))
            r = BX._nwog(out, [1.0, 2, 0.0, rec, "near", ref, "close"], d, og, ks, px, 1.0)
            res[(ref, rec)] = list(r.nwog_bias)
    assert res[("previous", "high")] == [-1, -1, 1]                       # the closes 4090 / 4105 / 4112 against last week's NWOG 4100-4110: bearish until back above the HIGH, a close at 4105 does not flip
    assert res[("previous", "low")] == [-1, 0, 1]                         # ... under the LOW edge the 4105 close ends it (058)
    assert res[("current", "high")] == [-1, -1, -1]                       # this week's NWOG sits at 4200-4210: all three closes are under it
    out = pd.DataFrame(index=[d.index[k].date() for k in ks], data=dict(px=px))
    r = BX._nwog(out, [1.0, 2, 0.0, "high", "near"], d, og, ks, np.array([4090.0, 4105.0, 4112.0]), 1.0)             # the built defaults: this week's NWOG (4200-4210) on the 09:30 price
    assert list(r.nwog_bias) == [-1, -1, -1]


def test_nwog_flip_edge_params():
    import json
    # review round 1: the spec parameters - nwog_flip_edge (default "high") and the daily-close basis (default "close"); the first-pass nwog_bias_reclaim stays as an override
    p = Params(nwog_bias="tag")
    assert (p.nwog_flip_edge, p.nwog_ref, p.nwog_bias_basis, p.nwog_bias_reclaim) == ("high", "current", "close", "")
    assert json.loads(p.bx)["nwog"][3] == "high" and json.loads(p.bx)["nwog"][5:] == ["current", "close"]
    assert json.loads(Params(nwog_bias="tag", nwog_flip_edge="low", nwog_bias_basis="px").bx)["nwog"][3] == "low"
    assert json.loads(Params(nwog_bias="tag", nwog_flip_edge="low", nwog_bias_reclaim="ce").bx)["nwog"][3] == "ce"          # the explicit override wins
    with pytest.raises(ValueError):
        Params(nwog_flip_edge="ce")
    # the spec test: NWOG 4100-4110, a bearish state; a close at 4105 flips under "low" but not "high"; a close at 4112 flips under both
    d = dsess([(4100, 4110, 4090, 4095), (4095, 4100, 4085, 4090), (4090, 4108, 4085, 4105), (4105, 4120, 4100, 4112), (4112, 4115, 4105, 4110)])
    wk = d.index.to_period("W-FRI")
    og = pd.DataFrame(dict(kind=["nwog"], high=[4110.0], low=[4100.0], ce=[4105.0], up=[True], known=[0], week=[wk[0]]))
    ks = np.array([2, 3, 4])                                                # the table rows read the previous session's close: 4090 (bearish), 4105, 4112
    px = np.array([9999.0] * 3)
    for edge, want in (("high", [-1, -1, 1]), ("low", [-1, 0, 1])):
        cfg = json.loads(Params(nwog_bias="tag", nwog_flip_edge=edge).bx)["nwog"]
        out = pd.DataFrame(index=[d.index[k].date() for k in ks], data=dict(px=px))
        assert list(BX._nwog(out, cfg, d, og, ks, px, 1.0).nwog_bias) == want, edge


# --- item 77: the joint weekly ITH ------------------------------------------------------------------------------------------------------

def test_wk_dc_joint():
    per = pd.period_range("2026-03-02", periods=4, freq="W-FRI")
    days = [date(2026, 3, 6), date(2026, 3, 13), date(2026, 3, 20), date(2026, 3, 27)]
    # ES closes below its last down-close week's low on week 2 and NQ does not: no joint flag; both on week 3: joint; NQ returns bullish on week 4: it ends
    es = {per[i]: (days[i], i in (1, 2), i == 3) for i in range(4)}
    nq = {per[i]: (days[i], i == 2, i == 3) for i in range(4)}
    j = BH.joint_from_flags(es, nq)
    assert j == {days[0]: False, days[1]: False, days[2]: True, days[3]: False}
    only_es = BH.joint_from_flags(es, {per[i]: (days[i], False, False) for i in range(4)})
    assert not any(v for k, v in only_es.items() if k != days[3]) or only_es[days[2]] is False
    # htf._flip applies the wk_dc -1 flip only while the joint flag holds
    book = [(4000, 4010, 3930, 3950), (3950, 4000, 3940, 3990), (3990, 4080, 3985, 4075), (4075, 4120, 4040, 4100), (4100, 4105, 3900, 3910)]
    d = week_book(book)
    d = pd.concat([d, dsess([(3910, 3911, 3909, 3910)], start=date(2026, 4, 6))])
    w = htf.weeks(d)
    arrs = []
    last_day = [t.date() for t in d.index][-2]                                                     # the 5th week's last session
    base = htf._flip(d, w, arrs, ("wk_dc",), None)
    assert base[d.index[-1]] == -1
    cfg_off = {"wk_joint": {last_day: False}}
    cfg_on = {"wk_joint": {last_day: True}}
    assert htf._flip(d, w, arrs, ("wk_dc",), cfg_off)[d.index[-1]] == 1                           # ES alone: the bullish state stays
    assert htf._flip(d, w, arrs, ("wk_dc",), cfg_on)[d.index[-1]] == -1
    p = Params(**BASE, wk_dc_joint=True)
    assert p.wk_dc_joint


# --- item 71: weekly FVGs on the weekly bars, monthly known the session after ------------------------------------------------------------------

def test_weekly_fvg_on_weekly_bars():
    # every day spans 25 points and the range climbs 10 a day: no daily 3-candle gap, yet week 1's high is below week 3's low
    rows = []
    for k in range(15):
        lo = 3990 + 10 * k
        rows.append((lo + 5, lo + 25, lo, lo + 20))
    d = dsess(rows)
    dh, dl = d.high.values.astype(float), d.low.values.astype(float)
    assert not L.fvgs(dh, dl)                                              # no daily FVG at all
    arrs = weekly_arrs(d)
    fv = [a for a in arrs if a.tf == "W" and a.typ == "fvg"]
    assert fv and fv[0].kind == "bull" and fv[0].bottom == float(d.high.values[4]) and fv[0].top == float(d.low.values[10])


def test_monthly_arrays_known_next_month():
    # three months of sessions (Jan, Feb, Mar 2026): a monthly gap between January's high and March's low
    idx = pd.bdate_range("2026-01-01", "2026-03-31")
    n = len(idx)
    mo = np.array([t.month for t in idx])
    base = np.where(mo == 1, 4000.0, np.where(mo == 2, 4100.0, 4300.0))
    d = pd.DataFrame(dict(open=base, high=base + 20, low=base - 20, close=base + 5), index=idx)
    mth = htf.months(d)
    assert len(mth) == 3
    pos = {t: k for k, t in enumerate(d.index)}
    ml = [pos[t] + 1 for t in mth["last"]]
    arrs = htf._arrays(*(mth[k].values.astype(float) for k in ("open", "high", "low", "close")), "M", lambda i: ml[i], False)
    fv = [a for a in arrs if a.typ == "fvg"]
    assert len(fv) == 1 and fv[0].kind == "bull"
    assert fv[0].known == ml[2] == n                                      # usable from the session AFTER March's last session (index n = past the book: the completing month is not used inside it)
    p = Params(**BASE, htf_monthly=True)
    assert B.table_kw(p)["monthly_arrays"] is True
