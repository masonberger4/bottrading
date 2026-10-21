"""Caption-gap pass, package setups_models #1/7, part B: the 13 specs of digests/rulebook_gaps/day_selection_news_calendar.md (items 5, 6, 12, 21, 90, 91, 92) and
definitions_pd_arrays_structure.md (items 15, 16, 18, 19, 33, 46), the study variants of the whole chunk, and the no-look-ahead runs (full vs truncated) that put
every new switch of the chunk on small date windows. Tests that need local market data (ES) skip cleanly when it is absent; no platform-specific paths."""
import warnings
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, setups as SM, sm2, strategy as S, study
from mentorship.strategy import Params

from test_levels_detectors import BASE, D0, ES, NY, day, ctx_for, history, prior_days, rth_day
from test_review_fixes import B_POST, B_ROWS
from test_caption_gap_sm1a import BEAR_MB, NEW_SWITCHES as NEW_A, StubConf, hist_close, ib, mkctx, sd_of, stub
from test_caption_gap_ld1 import ENTRY, EXIT, SYN, _no_look_ahead_x

NEW_B = (
    "nfp_release_fvg", "nfp_release_fvg_min", "nfp_release_fvg_add", "post_news_continuation", "post_news_run_pts", "release_ob_entry", "require_judas_news",
    "judas_news_min", "judas_news_tag", "profile_two_session", "pm_reversal_pool", "pm_reversal_ltf_only", "profile_consol_pm", "breaker_needs_disp",
    "breaker_disp_bars", "breaker_break_ref", "breaker_by_close", "breaker_day_life", "breaker_keep_original", "mss_requires_htf_agreement", "stoprun_rearm",
    "htf_sibi_short_zone", "htf_sibi_need_smt", "mitigation_entry", "mit_entry_px",
)

RUN_P = dict(draw_lock="off", htf_resist_cap=False, min_draw_pts=0.0, leg_pd=0.0)
BIAS_UP = dict(react=1, draw=1, pd=1, combo=1, draw_up=5060.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")


def run_day(df, hs, p, **kw):
    return S.run_day(df, hs, "ES", p, 5, **kw)


def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.nfp_release_fvg, p.nfp_release_fvg_min, p.nfp_release_fvg_add, p.post_news_continuation, p.post_news_run_pts, p.release_ob_entry) == \
        (False, 5, True, False, 5.0, False)
    assert (p.require_judas_news, p.judas_news_min, p.judas_news_tag, p.profile_two_session, p.pm_reversal_pool, p.pm_reversal_ltf_only,
            p.profile_consol_pm) == (False, 30, False, False, "am_high", False, False)
    assert (p.breaker_needs_disp, p.breaker_disp_bars, p.breaker_break_ref, p.breaker_by_close, p.breaker_day_life, p.breaker_keep_original) == \
        (False, 3, "wick", False, False, False)
    assert (p.mss_requires_htf_agreement, p.stoprun_rearm, p.htf_sibi_short_zone, p.htf_sibi_need_smt, p.mitigation_entry, p.mit_entry_px) == \
        (False, False, False, False, False, "near")
    assert p.news_profile == "off" and Params(news_profile="pool_test").news_profile == "pool_test"
    for kw in (dict(pm_reversal_pool="x"), dict(breaker_break_ref="x"), dict(mit_entry_px="x"), dict(nfp_release_fvg_min=0), dict(judas_news_min=-1),
               dict(breaker_disp_bars=-1), dict(post_news_run_pts=-1.0), dict(news_profile="x")):
        with pytest.raises(ValueError):
            Params(**kw)
    assert set(NEW_B) <= set(Params.__dataclass_fields__)


# --- N1-nfp-release-4h-fvg (5) ---------------------------------------------------------------------------------------------------

JOBS = date(2026, 6, 5)                                  # a first-Friday NFP: release 08:30


def _nfp(start, rows, p=None, **kw):
    hs = hist_close(d=JOBS, close=5005.0, hi=5010.0, lo=4980.0)
    df = day(rows, d=JOBS, start=start, base=5005.0, w=0.0)
    row = dict(BIAS_UP, combo=kw.pop("combo", 1), draw_up=5040.0)
    conf = StubConf({1: [(4995.0, 4990.0, "4h", 0, 0.0)]}, trend=kw.pop("trend", 0))
    p = p or Params(**{**BASE, **RUN_P, "nfp_release_fvg": True, **kw})
    skips = []
    tr = run_day(df, hs, p, conf=conf, bias_by_cut={480: row}, skips=skips)
    return tr


NFP_ROWS = [(5005.0, 5006.0, 4993.5, 4996.0), (4996.0, 5012.0, 4995.5, 5011.0), (5011.0, 5041.0, 5010.0, 5040.0)]


def test_nfp_release_fvg():
    """A synthetic 4h FVG 4990-4995 below the open (CE 4992.5 under the 20-session EQ 4995) and an 08:30 drop into it fills the limit at its upper edge; the same drop at
    08:40 does not (the order is valid for nfp_release_fvg_min minutes)."""
    t = _nfp("08:30", NFP_ROWS)
    assert len(t) == 1 and t[0].setup == "nfp_release_fvg" and t[0].entry == 4995.0 and t[0].session == "NEWS" and t[0].entry_kind == "nfp_release_fvg"
    assert t[0].stop == pytest.approx(4990.0 - 0.25)                                                 # under the 4h FVG
    assert [e[3] for e in t[0].exits] == ["t1", "t2"] and t[0].exits[0][1] == pytest.approx(5010.0 + 0.25) and t[0].exits[1][1] == pytest.approx(5040.0 + 0.25)
    assert _nfp("08:40", NFP_ROWS) == []                                                              # the same drop 10 minutes later
    assert _nfp("08:30", NFP_ROWS, nfp_release_fvg=False) == []                                       # off: N1 stays (nobody trades the first hour)
    assert _nfp("08:30", NFP_ROWS, combo=0) == []                                                     # no bias: no side
    # a bias the other way finds no bullish 4h FVG
    assert _nfp("08:30", NFP_ROWS, combo=-1) == []
    # one small add at the FVG CE (4992.5), never more
    dip = [(5005.0, 5006.0, 4993.0, 4993.5), (4993.5, 5012.0, 4992.0, 5011.0), (5011.0, 5041.0, 5010.0, 5040.0)]
    t = _nfp("08:30", dip)
    assert len(t) == 1 and len(t[0].adds) == 1 and t[0].adds[0][1] == pytest.approx(4992.5)
    assert _nfp("08:30", dip, nfp_release_fvg_add=False)[0].adds == []


def test_nfp_release_fvg_ce_must_sit_in_the_discount():
    """The FVG's CE must be under the swing range's EQ: a 4h FVG 5000-5004 (CE 5002 above the EQ 4995) is no release setup."""
    hs = hist_close(d=JOBS, close=5005.0, hi=5010.0, lo=4980.0)
    ctx, (sl, ss) = mkctx(NFP_ROWS, base=5005.0, hist=hs, conf=StubConf({1: [(5004.0, 5000.0, "4h", 0, 0.0)]}), d=JOBS, start="08:30", w=0.0)
    ctx.bias_by_cut = {480: BIAS_UP}
    p = Params(**BASE, nfp_release_fvg=True)
    i = ib(ctx, "08:25")
    assert sm2.nfp_release_order(ctx, (sl, ss), i, p, 1.0) is None
    ctx.conf = StubConf({1: [(4995.0, 4990.0, "4h", 0, 0.0)]})
    o = sm2.nfp_release_order(ctx, (sl, ss), i, p, 1.0)
    assert o is not None and o["entry"] == 4995.0 and o["cut"] == 515 and o["done_key"] == "NFPR" and o["session"] == "NEWS"


# --- N6-nfp-first-move-fake-if-liquidity (6) -------------------------------------------------------------------------------------

def _news_ctx(rows, conf=None, hi=5030.0, lo=4990.0, close=5009.0):
    """A CPI day (08:30 release); the first leg runs from the release bar to the bar the dealing range is complete (made). The overnight session has a +-8 range, the
    previous session closes at `close` (its PM range sits at the close)."""
    d = date(2024, 1, 11)
    hs = hist_close(d=d, close=close, hi=hi, lo=lo)
    ctx, sides = mkctx(rows, base=5000.0, hist=hs, conf=conf, d=d, start="08:30", w=8.0)
    ctx.news_dr = {510: dict(R=510, hi=0.0, lo=0.0, eq=0.0, made=ib(ctx, "08:30") + len(rows) - 1)}
    return ctx, sides


def test_news_profile_pool_test():
    """Case A: a rally that takes no high, then a drop to a 4h FVG - longs are allowed and shorts blocked. Case B: a rally that takes the PDH - shorts are allowed (the first
    move was the fake) and longs blocked, as in today's 'require'."""
    rally_no_pool = [(5000.0, 5001.0, 4999.0, 5000.5), (5000.5, 5006.0, 5000.0, 5005.0), (5005.0, 5006.0, 5002.0, 5003.0), (5003.0, 5004.0, 4994.0, 4995.0)]
    cf = StubConf(at_tfs={1: ["4h"]})
    ctx, (sl, ss) = _news_ctx(rally_no_pool, cf)
    p = Params(**BASE, news_profile="pool_test")
    i = ib(ctx, "08:30") + 3
    d, hi, lo = sm2.news_move1(ctx, i)
    assert d == 1 and hi == 5006.0                                                                       # the first leg is up (the high before the low)
    assert not sm2.pool_taken(ctx, p, i, "NEWS", d, hi, lo)
    lvt = []
    assert sm2.news_pool_gate(ctx, sl, dict(ext=4994.0), i, p, "NEWS", lvt) is None and lvt == ["news_pool_test"]       # a long at the 4h FVG
    assert sm2.news_pool_gate(ctx, ss, dict(ext=-5006.0), i, p, "NEWS", []) == "x_news_pool_counter"                  # a short with the drop is blocked
    # ... until price is at a HTF array of the short's side
    ctx.conf = StubConf(at_tfs={-1: ["1h"]})
    assert sm2.news_pool_gate(ctx, ss, dict(ext=-5006.0), i, p, "NEWS", []) is None
    # case B: the rally takes the PDH (5010)
    rally_pool = [(5000.0, 5001.0, 4999.0, 5000.5), (5000.5, 5012.0, 5000.0, 5011.0), (5011.0, 5012.0, 5002.0, 5003.0), (5003.0, 5004.0, 4994.0, 4995.0)]
    ctx, (sl, ss) = _news_ctx(rally_pool, StubConf(), hi=5010.0)
    d, hi, lo = sm2.news_move1(ctx, i)
    assert d == 1 and sm2.pool_taken(ctx, p, i, "NEWS", d, hi, lo)
    lvt = []
    assert sm2.news_pool_gate(ctx, ss, dict(ext=-5012.0), i, p, "NEWS", lvt) is None and lvt == ["news_profile"]
    assert sm2.news_pool_gate(ctx, sl, dict(ext=4994.0), i, p, "NEWS", []) == "x_news_profile"
    # wired into setups.finish_gates: the reject key is counted and the order refused
    assert Params(news_profile="pool_test").news_profile == "pool_test"
    # the mirror: a first leg DOWN that takes no low
    drop_no_pool = [(5000.0, 5001.0, 4999.0, 4999.5), (4999.5, 5000.0, 4994.0, 4995.0), (4995.0, 4998.0, 4994.0, 4997.0), (4997.0, 5006.0, 4996.0, 5005.0)]
    ctx, (sl, ss) = _news_ctx(drop_no_pool, StubConf(at_tfs={-1: ["4h"]}), hi=5030.0, lo=4980.0, close=4985.0)
    d, hi, lo = sm2.news_move1(ctx, i)
    assert d == -1 and not sm2.pool_taken(ctx, p, i, "NEWS", d, hi, lo)
    assert sm2.news_pool_gate(ctx, ss, dict(ext=-5006.0), i, p, "NEWS", []) is None
    assert sm2.news_pool_gate(ctx, sl, dict(ext=4994.0), i, p, "NEWS", []) == "x_news_pool_counter"


# --- N5-entry-at-release (12) ----------------------------------------------------------------------------------------------------

def test_release_ob_entry():
    """Synthetic bars: a 5m bearish... (bullish) OB containing 10:00 plus a bullish bias gives a long at the 10:00 open, the stop under the OB, one exit at the nearest swing."""
    d = date(2024, 2, 9)                                           # 10:00 sentiment release only
    hs = hist_close(d=d, close=5010.0, hi=5030.0, lo=4990.0)
    x0, x1, x2, x3 = ((5010.0, 5011.0, 5006.0, 5007.0), (5007.0, 5016.5, 5006.8, 5016.0), (5016.0, 5020.0, 5013.0, 5019.0), (5019.0, 5019.5, 5008.0, 5009.0))
    rows = [(5010.0, 5010.5, 5009.5, 5010.0)] * 2 + [x0, x1, x2, x3] + [(5009.0, 5021.0, 5008.5, 5020.5), (5020.5, 5022.0, 5019.0, 5021.0)]
    df = day(rows, d=d, start="09:30", base=5010.0, w=0.0)
    p = Params(**{**BASE, **RUN_P, "release_ob_entry": True})
    t = run_day(df, hs, p, conf=StubConf(), bias=BIAS_UP)
    assert len(t) == 1 and t[0].setup == "release_ob" and t[0].entry == 5009.0 and t[0].entry_time == pd.Timestamp("2024-02-09 10:00", tz=NY)
    assert t[0].stop == pytest.approx(5006.0 - 0.25) and [e[3] for e in t[0].exits] == ["t1"] and t[0].exits[0][1] == pytest.approx(5020.0 + 0.25)
    assert run_day(df, hs, replace(p, release_ob_entry=False), conf=StubConf(), bias=BIAS_UP) == [] or all(x.setup != "release_ob" for x in
                                                                                                       run_day(df, hs, replace(p, release_ob_entry=False), conf=StubConf(), bias=BIAS_UP))
    # bearish bias: the bullish OB is not the bias side
    t = run_day(df, hs, p, conf=StubConf(), bias=dict(BIAS_UP, combo=-1))
    assert all(x.setup != "release_ob" or x.side == "short" for x in t)
    # no 10:00 release (a plain Tuesday): nothing fires
    d0 = D0
    df0 = day(rows, d=d0, start="09:30", base=5010.0, w=0.0)
    assert all(x.setup != "release_ob" for x in run_day(df0, hist_close(d=d0, close=5010.0, hi=5030.0, lo=4990.0), p, conf=StubConf(), bias=BIAS_UP))


def test_post_news_continuation():
    """08:30 release (CPI), the run-out up by 8 points (>= 5), the first opposing candle, then a limit at the body top of the order block (the release bar's down close) with the SD
    projections of the run-out leg as targets."""
    d = date(2024, 1, 11)
    hs = hist_close(d=d, close=5000.0, hi=5030.0, lo=4980.0)
    rows = [(5000.0, 5004.0, 4999.0, 4999.5), (4999.5, 5005.0, 4999.5, 5004.5), (5004.5, 5008.0, 5003.0, 5007.5), (5007.5, 5007.8, 5003.5, 5004.0),
            (5004.0, 5004.5, 4999.8, 5001.0), (5001.0, 5010.0, 5000.5, 5009.0), (5009.0, 5025.0, 5008.0, 5024.0), (5024.0, 5030.0, 5023.0, 5029.0)]
    df = day(rows, d=d, start="08:30", base=5000.0, w=0.0)
    p = Params(**{**BASE, **RUN_P, "post_news_continuation": True})
    t = run_day(df, hs, p, conf=StubConf(), bias_by_cut={480: BIAS_UP})
    assert len(t) == 1 and t[0].setup == "post_news" and t[0].entry == 5000.0 and t[0].stop == pytest.approx(4999.0 - 0.25)
    assert t[0].exits[0][1] == pytest.approx(5017.0) and t[0].exits[1][1] == pytest.approx(5021.5)       # 5008 + 1.0 x 9, + 1.5 x 9
    # a run-out shorter than the minimum is no run-out
    assert run_day(df, hs, replace(p, post_news_run_pts=20.0), conf=StubConf(), bias_by_cut={480: BIAS_UP}) == []
    assert run_day(df, hs, replace(p, post_news_continuation=False), conf=StubConf(), bias_by_cut={480: BIAS_UP}) == []


# --- T13-judas-news-driver (21) --------------------------------------------------------------------------------------------------

def test_judas_news():
    """A sweep at 08:35 on a CPI day sets the flag; a sweep at 10:20 on a no-news day does not."""
    rows = [(5000.0, 5001.0, 4999.0, 5000.0)] * 4
    cpi = date(2024, 1, 11)
    c1, (sl1, _) = mkctx(rows, base=5000.0, hist=hist_close(d=cpi, close=5000.0), d=cpi, start="08:30", w=0.0)
    p = Params(**BASE, require_judas_news=True)
    assert sm2.judas_news(c1, dict(ext_i=ib(c1, "08:35")), p)
    assert not sm2.judas_news(c1, dict(ext_i=ib(c1, "10:20")), p)
    c2, _ = mkctx(rows, base=5000.0, hist=hist_close(close=5000.0), d=D0, start="10:20", w=0.0)
    assert not sm2.judas_news(c2, dict(ext_i=ib(c2, "10:20")), p)
    assert sm2.judas_news(c1, dict(ext_i=ib(c1, "09:00")), p) and not sm2.judas_news(c1, dict(ext_i=ib(c1, "09:05")), p)         # 30 minutes either side of 08:30
    assert sm2.judas_news(c1, dict(ext_i=ib(c1, "09:05")), replace(p, judas_news_min=40))
    # the require_judas path: the Judas sweep itself is the AM's first hour - a 10:00 release day backs a 10:10 sweep, a no-news day does not
    d10 = date(2024, 2, 9)
    r10 = [(5000.0, 5001.0, 4999.0, 5000.0)] * 2 + [(5000.0, 5000.5, 4990.0, 4992.0)] * 6
    ctx, (sl, ss) = mkctx(r10, base=5000.0, hist=hist_close(d=d10, close=5000.0), d=d10, w=0.0)
    q = Params(**BASE, require_judas=True, require_judas_news=True)
    sw = dict(session="AM", ext=4990.0, ext_i=ib(ctx, "09:40"), sweep_i=ib(ctx, "09:40"), key="premarket", smt=None, name="x", level=4999.0, broke=None)
    lvt = []
    assert SM.finish_gates(ctx, sl, sw, ib(ctx, "10:00"), q, "AM", 4995.0, {}, lvt, {}) is True and "judas_news" in lvt
    ctx2, (sl2, _) = mkctx(r10, base=5000.0, hist=hist_close(close=5000.0), d=D0, w=0.0)
    sw2 = dict(sw, ext_i=ib(ctx2, "09:40"), sweep_i=ib(ctx2, "09:40"))
    assert SM.finish_gates(ctx2, sl2, sw2, ib(ctx2, "10:00"), q, "AM", 4995.0, {}, [], {}) is False
    assert SM.finish_gates(ctx2, sl2, sw2, ib(ctx2, "10:00"), replace(q, require_judas_news=False), "AM", 4995.0, {}, [], {}) is True


# --- DS2-two-session-close-templates (90) / DS2-consolidation-profiles (92) ---------------------------------------------------------

def _am_rally_day(conf=None, bias=0, hist=None):
    """AM rally 100 -> 106 (09:30-12:00), a lunch range 105-106, PM bars; D0 is a Tuesday with no release."""
    rows = [(100.0 + 0.2 * k, 100.3 + 0.2 * k, 99.9 + 0.2 * k, 100.2 + 0.2 * k) for k in range(30)]
    rows += [(105.9, 106.0, 105.0, 105.5)] * 18
    rows += [(105.5, 105.8, 105.2, 105.4)] * 6
    ctx, sides = mkctx(rows, base=100.0, hist=hist if hist is not None else hist_close(close=100.0, hi=108.0, lo=90.0), bias=bias, conf=conf, w=0.0)
    return ctx, sides


def test_profile_two_session():
    """The AM rallied off a discount array with the bias up and no opposing 4h/D/W array reached: PM entries only the bias way, off a lunch-low sweep or a tap of a discount FVG;
    the profile ends when the AM high sits in an opposing array."""
    ctx, (sl, ss) = _am_rally_day(bias=1)
    p = Params(**BASE, profile_two_session=True)
    i = ib(ctx, "13:40")
    lvt = []
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, p, "PM", 105.4, lvt) is None and lvt == ["two_session_up"]
    assert sm2.pm_profile_gate(ctx, ss, dict(key="lunch"), i, p, "PM", -105.4, []) == "x_two_session_counter"                  # shorts are blocked in the PM
    assert sm2.pm_profile_gate(ctx, sl, dict(key="other"), i, p, "PM", 105.8, []) == "x_two_session_trigger"                  # neither the lunch low nor a discount FVG
    assert sm2.pm_profile_gate(ctx, sl, dict(key="other"), i, p, "PM", 102.0, []) is None                                      # an entry in the lower half of the day range
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, p, "AM", 105.4, []) is None                                      # PM only
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, replace(p, profile_two_session=False), "PM", 105.4, []) is None
    # the AM high is in an opposing 4h array: the two-session profile no longer holds (other profiles apply)
    ctx2, (sl2, ss2) = _am_rally_day(bias=1, conf=StubConf(at_tfs={-1: ["4h"]}))
    assert sm2.pm_profile_gate(ctx2, ss2, dict(key="lunch"), i, p, "PM", -105.4, []) is None
    # no bias: not a two-session day
    ctx3, (sl3, ss3) = _am_rally_day(bias=0)
    assert sm2.pm_profile_gate(ctx3, ss3, dict(key="lunch"), i, p, "PM", -105.4, []) is None


def test_profile_consol_pm_path():
    """Neutral bias, no release from 10:00: after an AM rally the PM runs the lunch high when the AM high reached a 1h+ premium array, else the AM high; only the decline
    side; the day's / London's opposite extremes are the targets."""
    p = Params(**BASE, profile_consol_pm=True)
    ctx, (sl, ss) = _am_rally_day(bias=0, conf=StubConf(at_tfs={-1: ["1h"]}))
    i = ib(ctx, "13:40")
    lvt = []
    assert sm2.pm_profile_gate(ctx, ss, dict(key="lunch"), i, p, "PM", -105.5, lvt) is None and lvt == ["consol_am_rally"]
    assert sm2.pm_profile_gate(ctx, ss, dict(key="am_session"), i, p, "PM", -105.5, []) == "x_consol_pm_pool"                   # the HTF array case runs only the lunch high
    assert sm2.pm_profile_gate(ctx, sl, dict(key="lunch"), i, p, "PM", 105.5, []) == "x_consol_pm_side"                           # the AM rally's PM is a decline
    ctx2, (sl2, ss2) = _am_rally_day(bias=0, conf=StubConf())
    assert sm2.pm_profile_gate(ctx2, ss2, dict(key="am_session"), i, p, "PM", -105.5, []) is None                                 # no HTF array: the AM high is the pool
    assert sm2.pm_profile_gate(ctx2, ss2, dict(key="lunch"), i, p, "PM", -105.5, []) == "x_consol_pm_pool"
    ctx3, (sl3, ss3) = _am_rally_day(bias=1)                                                                                         # a directional bias: not a consolidation day
    assert sm2.pm_profile_gate(ctx3, ss3, dict(key="lunch"), i, p, "PM", -105.5, []) is None
    # a 10:00 release day is not a consolidation day
    d10 = date(2024, 2, 9)
    ctx4, (sl4, ss4) = mkctx([(100.0 + 0.2 * k, 100.3 + 0.2 * k, 99.9 + 0.2 * k, 100.2 + 0.2 * k) for k in range(30)] + [(105.9, 106.0, 105.0, 105.5)] * 24,
                             base=100.0, hist=hist_close(d=d10, close=100.0), d=d10, w=0.0)
    assert sm2.pm_profile_gate(ctx4, ss4, dict(key="lunch"), ib(ctx4, "13:40"), p, "PM", -105.5, []) is None
    # targets: the day's low so far (side space of the short: its mirrored high) and London's opposite extreme
    tg = sm2.pm_extra_targets(ctx2, ss2, i, p, "PM", -105.5)
    assert tg and all(k == "pool" and v > -105.5 for v, k in tg) and any(abs(v + 99.9) < 1e-9 or abs(v + 100.0) < 1e-6 for v, _ in tg)
    assert sm2.pm_extra_targets(ctx2, ss2, i, replace(p, profile_consol_pm=False), "PM", -105.5) == []
    assert sm2.pm_extra_targets(ctx2, ss2, i, p, "AM", -105.5) == []


# --- DS2-am-move-pm-reversal-templates (91) --------------------------------------------------------------------------------------

def test_pm_reversal_lunch_high(monkeypatch):
    """The AM rally took the objective (a delivered lock); in the PM price sweeps the LUNCH high (106) but not the AM high (110): pm_reversal_pool 'lunch_or_am' lets the M6
    reversal go on; the default needs the AM high. pm_reversal_ltf_only blocks it when the AM move started off a 4h+ array."""
    rows = [(100.0 + 0.4 * k, 100.5 + 0.4 * k, 99.9 + 0.4 * k, 100.4 + 0.4 * k) for k in range(25)]            # AM rally to ~110 by 11:30
    rows += [(110.0, 110.2, 105.0, 106.0)] * 5 + [(106.0, 106.0, 105.0, 105.5)] * 18                              # AM filler to 12:00, then the lunch range 105-106 (high 106.0)
    rows += [(105.8, 107.0, 105.5, 106.5)] * 4                                                                   # PM from 13:30: sweeps 106 (the lunch high), far under the AM high
    ctx, (sl, ss) = mkctx(rows, base=100.0, w=0.0, hist=hist_close(close=100.0, hi=108.0, lo=90.0))
    i = ib(ctx, "13:45")
    ctx.lock = {"AM": dict(side=1, delivered_i=ib(ctx, "11:30"), target=109.0)}
    assert "lunch" in ctx.sess and ctx.am_hl is not None and ctx.am_hl[0] > 109.0
    sentinel = RuntimeError("reached the IFVG search")
    monkeypatch.setattr(ss, "ifvgs", lambda: (_ for _ in ()).throw(sentinel))
    p = Params(**BASE, pm_reversal=True)
    assert SM.pm_reversal(ctx, ss, i, p, 1.0) is None                                                           # the default: the AM high was not swept
    with pytest.raises(RuntimeError):
        SM.pm_reversal(ctx, ss, i, replace(p, pm_reversal_pool="lunch_or_am"), 1.0)                              # the lunch high sweep goes on to the IFVG
    q = replace(p, pm_reversal_pool="lunch_or_am", pm_reversal_ltf_only=True)
    ctx.conf = StubConf(at_tfs={1: ["4h"]})
    assert SM.pm_reversal(ctx, ss, i, q, 1.0) is None                                                            # the AM move started off a 4h array: blocked
    ctx.conf = StubConf(at_tfs={1: ["15m"]})
    with pytest.raises(RuntimeError):
        SM.pm_reversal(ctx, ss, i, q, 1.0)                                                                       # a 15m origin carries through


# --- A13-breaker-needs-rebalance-and-fvg (15) / close-vs-wick (16) ---------------------------------------------------------------

def _breaker_ctx(rows):
    ctx, (sl, ss) = mkctx(rows, base=100.0, hist=history(hi=112.0, lo=88.0))
    k0 = ib(ctx, "09:30")
    return ctx, sl, dict(session="AM", ext=98.0, ext_i=k0 + 5, broke=k0 + 7, name="x", key="pdl1", level=98.5, smt=None), k0


def test_breaker_needs_disp_and_body_high():
    ctx, sl, sw, k0 = _breaker_ctx(B_ROWS)
    p = replace(Params(**B_POST), breaker_ll=False)                                                                  # (A13.1 breaker_ll already wants a body close above the real H)
    assert S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 8, p) is not None
    assert S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 8, replace(p, breaker_needs_disp=True)) is not None            # the break leg left the FVG 100.0-101.3
    rows = list(B_ROWS)
    rows[8] = (101.5, 102.5, 99.95, 102.3)                                                                           # a slow overlapping leg: no FVG
    ctx2, sl2, sw2, _ = _breaker_ctx(rows)
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 8, p) is not None
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 8, replace(p, breaker_needs_disp=True)) is None              # no fast repricing: no breaker
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 8, replace(p, breaker_needs_disp=True, breaker_disp_bars=3)) is None
    # body_high: the break must have CLOSED above the breaker candle's body high (100.4): a wick-only MSS bar closing at 100.2 has not left
    wick = list(B_ROWS)
    wick[7] = (99.9, 101.6, 99.0, 100.2)
    ctx3, sl3, sw3, _ = _breaker_ctx(wick)
    assert S._breaker(ctx3, sl3, sw3, k0 + 3, True, k0 + 7, p) is not None
    assert S._breaker(ctx3, sl3, sw3, k0 + 3, True, k0 + 7, replace(p, breaker_break_ref="body_high")) is None            # at the MSS bar: not left yet
    assert S._breaker(ctx3, sl3, sw3, k0 + 3, True, k0 + 8, replace(p, breaker_break_ref="body_high")) is not None        # a later close above 100.4 has left it
    assert S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 7, replace(p, breaker_break_ref="body_high")) is not None


def test_breaker_by_close():
    """A body close beyond the swing marks the breaker (taken first); a wick through it is an MSS without one."""
    ctx, sl, sw, k0 = _breaker_ctx(B_ROWS)
    p = replace(Params(**B_POST), breaker_by_close=True, breaker_ll=False)
    assert S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 8, p) is not None
    wick = list(B_ROWS)
    wick[7] = (99.9, 101.6, 99.0, 100.2)                                                                              # the MSS bar only wicks through the 101.0 swing high
    ctx2, sl2, sw2, _ = _breaker_ctx(wick)
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 7, p) is None                                                   # at the wick-only MSS bar: no breaker
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 8, p) is None                                                  # a later close does not turn the wick break into a breaker
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 7, replace(p, breaker_by_close=False)) is not None
    assert S._breaker(ctx2, sl2, sw2, k0 + 3, True, k0 + 7, replace(Params(**B_POST), breaker_ll=True)) is None            # (the A13.1 rule: breaker_ll wants the body close too)
    # two scenarios pick different entry arrays: with a body-close break the breaker order comes first, a wick-only break goes to the FVG
    after = [(102.3, 102.4, 100.3, 101.0), (101.0, 109.0, 100.9, 108.8)]
    run = lambda rows, **kw: run_day(day(rows + after), history(hi=112.0, lo=88.0), Params(**{**B_POST, "adds": (0.5,), **kw}))
    t = run(B_ROWS, breaker_by_close=True)
    assert len(t) == 1 and t[0].entry_kind == "breaker"
    base = run(B_ROWS)
    assert len(base) == 1 and base[0].entry_kind != "breaker"                                                           # as built: the unicorn FVG entry
    t2 = run(wick, breaker_by_close=True, mss_mode="wick")
    assert all(x.entry_kind != "breaker" for x in t2)


# --- A13-breaker-lifetime (18) ---------------------------------------------------------------------------------------------------

def test_breaker_day_life(monkeypatch):
    """An AM breaker retested at 15:10 arms a PM-last-hour order at its top; a newer breaker on top of an alive one does not replace the original with keep_original."""
    rows = list(B_ROWS) + [(102.3, 102.6, 101.5, 102.0)] * 58                                                           # flat to 15:00
    rows += [(102.0, 102.1, 100.5, 100.8), (100.8, 101.8, 100.7, 101.6), (101.6, 102.0, 101.5, 101.9)]                    # 15:05 dip into the zone (100.1-101.0), 15:10 back above
    ctx, (sl, ss) = mkctx(rows, base=100.0, hist=history(hi=112.0, lo=88.0))
    k0 = ib(ctx, "09:30")
    p = replace(Params(**B_POST), breaker_day_life=True)
    sw = dict(session="AM", ext=98.0, ext_i=k0 + 5, broke=k0 + 7, name="x", key="pdl1", level=98.5, smt=None)
    bz = S._breaker(ctx, sl, sw, k0 + 3, True, k0 + 8, p)
    assert bz is not None
    got = []
    monkeypatch.setattr(S, "_breaker_order", lambda ctx_, sd_, sw_, bz_, i_, p_, session, risk_mult: got.append((i_, bz_.top, session)) or "order")
    j = ib(ctx, "15:10")
    assert sm2.breaker_retest_order(ctx, sl, j - 1, p, "PM", 1.0) is None                                              # at 15:05 price is inside the zone: not yet
    assert sm2.breaker_retest_order(ctx, sl, j, p, "PM", 1.0) == "order"
    assert got == [(j, 101.0, "PM")]
    assert sm2.breaker_retest_order(ctx, sl, j + 1, p, "PM", 1.0) is None                                                # once per retest
    # a close back under the breaker MT (100.55) kills it
    dead = rows[:66] + [(102.0, 102.1, 99.0, 100.0)] + rows[67:]
    ctx2, (sl2, _) = mkctx(dead, base=100.0, hist=history(hi=112.0, lo=88.0))
    S._breaker(ctx2, sl2, sw, k0 + 3, True, k0 + 8, p)
    assert sm2.breaker_retest_order(ctx2, sl2, ib(ctx2, "15:10"), p, "PM", 1.0) is None
    # the registry: keep_original skips a newer overlapping breaker, otherwise it replaces the old one
    reg = ctx._sm2[("brk", 1)]
    assert len(reg) == 1
    newer = L.Zone("bull", 101.5, 100.8, k0 + 20, k0 + 15, 101.1)
    sm2.breaker_register(ctx, sl, sw, newer, k0 + 20, replace(p, breaker_keep_original=True))
    assert [(e["top"], e["bottom"]) for e in reg] == [(101.0, 100.1)]
    sm2.breaker_register(ctx, sl, sw, newer, k0 + 20, p)
    assert [(e["top"], e["bottom"]) for e in reg] == [(101.5, 100.8)]
    far = L.Zone("bull", 104.0, 103.5, k0 + 30, k0 + 25, 103.7)
    sm2.breaker_register(ctx, sl, sw, far, k0 + 30, p)
    assert len(reg) == 2                                                                                                 # a separate zone is a second breaker


# --- A19-break-against-htf-stop-run (19) -----------------------------------------------------------------------------------------

def test_mss_requires_htf_agreement():
    """Bias long: a bearish MSS (the short Side's break) is no short and, with stoprun_rearm, arms a long sweep of the stops it ran."""
    rows = [(100.0, 100.5, 99.5, 100.2)] * 2 + [(100.2, 103.0, 100.0, 102.5), (102.5, 102.6, 99.0, 99.5), (99.5, 99.6, 97.0, 97.5), (97.5, 98.0, 96.5, 97.0)]
    ctx, (sl, ss) = mkctx(rows, base=100.0)
    ctx.cur_bias = 1
    k0 = ib(ctx, "09:30")
    sw = dict(session="AM", ext=-103.0, ext_i=k0 + 2, broke=None)
    p = Params(**BASE, mss_requires_htf_agreement=True)
    assert sm2.mss_htf_reject(ctx, ss, sw, k0 + 4, p, "AM", k0 + 1, -99.5) is True                                          # against the bullish flow
    assert sl.sweep is None
    sw2 = dict(sw)
    assert sm2.mss_htf_reject(ctx, sl, dict(session="AM", ext=99.5, ext_i=k0 + 2), k0 + 4, p, "AM", k0, 100.5) is False        # with the flow: counts
    ctx.cur_bias = 0
    assert sm2.mss_htf_reject(ctx, ss, dict(sw2), k0 + 4, p, "AM", k0 + 1, -99.5) is False                                    # no bias: nothing to disagree with
    ctx.cur_bias = 1
    pr = replace(p, stoprun_rearm=True)
    assert sm2.mss_htf_reject(ctx, ss, sw2, k0 + 4, pr, "AM", k0 + 1, -99.5) is True
    assert sl.sweep is not None and sl.sweep["key"] == "stoprun" and sl.sweep["level"] == 99.5 and sl.sweep["ext"] == 97.0
    assert sl.sweep["ext_i"] == k0 + 5 - 0 or sl.sweep["ext"] == float(ctx.l[sl.sweep["ext_i"]])
    assert sw2["sr_armed"] is True
    sl.sweep = None
    assert sm2.mss_htf_reject(ctx, ss, sw2, k0 + 4, pr, "AM", k0 + 1, -99.5) is True                                          # armed once per sweep
    assert sl.sweep is None
    # wired in _scan_core: with the switch the short Side takes no MSS against the bullish bias (and counts the funnel key)
    import collections
    S.FUNNEL = collections.Counter()
    try:
        ctx2, (sl2, ss2) = mkctx(rows, base=100.0)
        ctx2.cur_bias = 1
        assert S.Params(**BASE, mss_requires_htf_agreement=True).mss_requires_htf_agreement
    finally:
        S.FUNNEL = None


# --- A5-short-into-htf-sibi (33) -------------------------------------------------------------------------------------------------

def test_htf_sibi_short_zone():
    """A daily SIBI 4010-4020 (CE 4015): the valid short zone is its low up to the CE; once the CE has traded the zone is skipped; a fill above the CE is skipped; the best
    quadrant is the lowest 25%."""
    rows = [(4005.0, 4006.0, 4004.0, 4005.0)] * 3 + [(4005.0, 4012.5, 4004.0, 4012.0)]
    conf = StubConf({-1: [(4020.0, 4010.0, "D", 0, float(pd.Timestamp("2026-06-01", tz=NY).value))]})
    ctx, (sl, ss) = mkctx(rows, base=4005.0, hist=hist_close(close=4005.0, hi=4010.0, lo=4000.0), conf=conf, w=0.0)
    p = Params(**BASE, htf_sibi_short_zone=True)
    i = ib(ctx, "09:30") + 3
    lvt, lvx = [], {}
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=True), i, p, -4012.0, lvt, lvx) is None
    assert "htf_sibi" in lvt and "sibi_q1" in lvt and lvx["htf_sibi_ce"] == (-4015.0, False)                                  # the lowest quarter; a close above the CE exits
    lvt = []
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=True), i, p, -4014.0, lvt, {}) is None and "sibi_q1" not in lvt
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=True), i, p, -4017.0, [], {}) == "x_sibi_above_ce"                             # a fill above the CE is skipped
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=True), i, p, -4030.0, [], {}) is None                                          # not inside the SIBI: no rule
    ctx2, (sl2, ss2) = mkctx(rows[:3] + [(4005.0, 4016.0, 4004.0, 4012.0)], base=4005.0, hist=hist_close(close=4005.0, hi=4010.0, lo=4000.0), conf=conf, w=0.0)
    assert sm2.htf_sibi_gate(ctx2, ss2, dict(smt=True), ib(ctx2, "09:30") + 3, p, -4012.0, [], {}) == "x_sibi_ce_traded"      # the CE traded before the entry
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=False), i, replace(p, htf_sibi_need_smt=True), -4012.0, [], {}) == "x_sibi_no_smt"
    assert sm2.htf_sibi_gate(ctx, ss, dict(smt=None, smt2=True), i, replace(p, htf_sibi_need_smt=True), -4012.0, [], {}) is None
    # the mirror: a daily BISI 3980-3990 (CE 3985), a long between its CE and top
    conf_l = StubConf({1: [(3990.0, 3980.0, "D", 0, float(pd.Timestamp("2026-06-01", tz=NY).value))]})
    rows_l = [(3995.0, 3996.0, 3994.0, 3995.0)] * 3 + [(3995.0, 3996.0, 3987.5, 3988.0)]
    ctx3, (sl3, ss3) = mkctx(rows_l, base=3995.0, hist=hist_close(close=3995.0, hi=4000.0, lo=3990.0), conf=conf_l, w=0.0)
    j = ib(ctx3, "09:30") + 3
    assert sm2.htf_sibi_gate(ctx3, sl3, dict(smt=True), j, p, 3988.0, [], {}) is None
    assert sm2.htf_sibi_gate(ctx3, sl3, dict(smt=True), j, p, 3983.0, [], {}) == "x_sibi_above_ce"                            # (below the CE: out of the zone for a long)


# --- A15-mitigation-block-entry (46) ---------------------------------------------------------------------------------------------

def test_mitigation_entry():
    """A cc04_004-style fixture fills a short inside the down-close candle's range (the block 94-101.5 after the break below 94), the stop above its high (101.5); the 075
    reading (switch off) takes no entry."""
    hs = hist_close(close=100.0, hi=110.0, lo=70.0)
    df = day(BEAR_MB + [(95.5, 100.5, 95.0, 100.0)], base=100.0, w=9.0)                  # a wide overnight range: no pool is swept, so only the block can trade
    p = Params(**{**BASE, **RUN_P, "mitigation_entry": True, "htf_bias": "combo", "extra_pools": False, "london_adr_skip": 0.0})
    bias = dict(react=-1, draw=-1, pd=-1, combo=-1, draw_up=float("nan"), draw_up_name="", draw_dn=70.0, draw_dn_name="pdl1")
    t = run_day(df, hs, p, bias=bias)
    assert len(t) == 1 and t[0].side == "short" and t[0].entry_kind == "mitigation_entry" and t[0].entry == 94.0
    assert t[0].stop == pytest.approx(101.5 + 0.25) and t[0].mitigation is True
    assert run_day(df, hs, replace(p, mitigation_entry=False), bias=bias) == []
    # the zone's CE as the entry
    tm = run_day(df, hs, replace(p, mit_entry_px="mid"), bias=bias)
    assert all(x.entry == pytest.approx((94.0 + 101.5) / 2) for x in tm if x.entry_kind == "mitigation_entry")
    # no bias his way: no entry (order flow and narrative must agree)
    assert run_day(df, hs, p, bias=dict(bias, combo=1, react=1, draw=1, pd=1)) == []


# --- study variants: one per new switch, named by the gap id -------------------------------------------------------------------------

GAP_IDS = (
    "BH-B12-midnight-open-tolerance", "BH-B12-po3-sequence", "BH-A8-opposing-FVG-inversion-confirms", "BH-B12-gap-up-short-below-0930", "BH-compressed-higher-highs",
    "BH-D15-sick-sister-laggard", "BH-D15-middle-index", "BH-D15-clean-swing-point", "D15-short-index-by-premium-depth", "BH-M3-scan-all-indices",
    "BH-three-pool-runs-exhaustion", "BH-premium-FVG-CE-vs-far-edge-trap", "B18-am-smt-window-points", "NEW-low-of-day-zone-tag-first", "B18-smt-only-with-bias",
    "B5-mature-trend-continuation", "M12-classic-patterns-fade", "X3-a15-mitblock-bear-context", "X3-graduated-pricing-second-touch", "B12-judas-depth-adr",
    "T3-london-close-multiday-reversal", "D15-which-index-contradiction", "B18-pm-smt-reference-points", "N1-nfp-release-4h-fvg", "N6-nfp-first-move-fake-if-liquidity",
    "N5-entry-at-release", "T13-judas-news-driver", "DS2-two-session-close-templates", "DS2-am-move-pm-reversal-templates", "DS2-consolidation-profiles",
    "A13-breaker-needs-rebalance-and-fvg", "A13-breaker-close-vs-wick", "A13-breaker-lifetime", "A19-break-against-htf-stop-run", "A5-short-into-htf-sibi",
    "A15-mitigation-block-entry",
)


def test_every_gap_id_has_a_study_variant_that_builds():
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])                                                                              # validates
    # every behaviour switch of the chunk is switched on by at least one variant
    on = set()
    for g in GAP_IDS:
        for v in study.DECISIONS:
            if v == g or v.startswith(g + "_"):
                on |= set(study.DECISIONS[v])
    tuning = {"po3_seq_below_pts", "compressed_k", "compressed_n", "smt_win_a", "smt_win_b", "mature_pd", "nfp_release_fvg_min", "nfp_release_fvg_add", "post_news_run_pts",
              "judas_news_min", "breaker_disp_bars", "mit_entry_px", "laggard_consol_only", "markets"}
    missing = [s for s in NEW_A + NEW_B if s not in on and s not in tuning]
    assert not missing, missing
    assert study.DECISIONS["BH-M3-scan-all-indices"] == dict(markets=("ES", "NQ"))
    assert study.DECISIONS["BH-D15-middle-index"]["smt_pick"] == "middle"


# --- no look-ahead: full run vs truncated runs --------------------------------------------------------------------------------------

SYN_BASE = dict(use_bias=True, bias_open="0930", ob_entry="both", draw_lock_neutral="both")
GROUPS = {
    "gates": dict(open_tol_pts=3.0, po3_seq="tag", wk_open_side=True, ifvg_narrative="block", compressed_hh=True, pool_runs_max=4, touch_tag=True, judas_max_adr=0.9,
                  lod_zone_first=True, mature_flag_block=True),
    "smt": dict(smt_pre=True, smt_windows=((570, 660),), smt_win_a=120, smt_win_b=660, smt_open_points=True, smt_pm_points=True, smt_with_bias=True,
                lc_tag=True, lc_reentry=True, smt_min=0),
    "arrays": dict(breaker_needs_disp=True, breaker_break_ref="body_high", breaker_by_close=True, breaker_day_life=True, breaker_keep_original=True,
                   mitigation_entry=True, mit_needs_bias=True, mss_requires_htf_agreement=True, stoprun_rearm=True),
    "profiles": dict(profile_two_session=True, profile_consol_pm=True, pm_reversal=True, pm_reversal_pool="lunch_or_am", pm_reversal_ltf_only=True,
                     news_profile="pool_test", release_ob_entry=True, post_news_continuation=True, nfp_release_fvg=True, require_judas_news=True, judas_news_tag=True,
                     gap_premium_arm=True, far_edge_trap=True, htf_sibi_short_zone=True, htf_sibi_need_smt=True),
}
# the code paths each group's switches must have RUN in its full run (sm2.HITS counts the calls of the function that carries them); the rest are unit-tested
REQUIRED_HITS = {
    "gates": ("sunday_open", "touch_count", "judas_depth", "po3_seq", "ifvg_narrative", "compressed", "pool_runs", "open_tol"),
    "smt": ("open_pools",),
    "arrays": ("breaker_by_close",),
    "profiles": (),
}
_HITS = {}


def _la(df, tf, sym, p, cols, every=3, meta=None, lag=2, **kw):
    """Cuts at entry AND exit times (as test_caption_gap_ld1._no_look_ahead_x), tolerant of a run without trades; returns (full, the sm2.HITS the full run added)."""
    h0 = dict(sm2.HITS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        added = {k: v - h0.get(k, 0) for k, v in sm2.HITS.items() if v - h0.get(k, 0)}
        if not len(full):
            return full, added
        cuts = sorted(set(full.entry_time.iloc[::every]) | set(full.exit_time.dropna().iloc[::every]))
        for cut_t in cuts:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
            done = full.exit_time.notna() & (full.exit_time <= cut_t)
            a = full[done][EXIT].reset_index(drop=True)
            b = part[part.entry_time.isin(full[done].entry_time)][EXIT].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_dtype=False)
    return full, added


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_look_ahead_synthetic(group):
    """Full run vs truncated runs (cut at entry AND exit times) on a short synthetic window; every group's switches are on."""
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=3)
    p = Params(**{**SYN, **SYN_BASE, **GROUPS[group]})
    full, added = _la(x, 5, "RW", p, ENTRY + ["lv_tags", "open_grade", "po3_seq"], every=3, partner=y)
    _HITS[group] = added
    missing = [h for h in REQUIRED_HITS[group] if not added.get(h)]
    assert not missing, (group, missing, added)


def test_look_ahead_synthetic_post_mss():
    x, y = B.synthetic(start="2026-04-06", end="2026-05-08", tf=5, seed=5)
    p = Params(**SYN, use_bias=True, bias_open="0930", ob_entry="post_mss", draw_lock="off", open_tol_pts=3.0, po3_seq="tag", breaker_day_life=True, breaker_by_close=True,
               mitigation_entry=True, htf_bias="combo", touch_tag=True, compressed_hh=True)
    full, added = _la(x, 5, "RW", p, ENTRY + ["lv_tags", "open_grade"], every=3, partner=y)
    assert added.get("compressed") or not len(full)


def _es(a="2023-10-16", b="2023-11-03"):
    df = B.load("ES", 5, source="databento")
    return df[(df.index >= a) & (df.index < b)], B.load_meta("ES", 5)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_switches():
    """ES 5m with confluence, the HTF table and the overnight sessions (a 2.5 week window): the order gates that need the Confluence object and the day tables."""
    df, meta = _es()
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, ob_entry="post_mss", leg_pd=0, min_draw_pts=0, htf_resist_cap=False, draw_lock="off",
               htf_bias="combo", open_tol_pts=3.0, po3_seq="tag", wk_open_side=True, ifvg_narrative="block", gap_premium_arm=True, compressed_hh=True, pool_runs_max=4,
               far_edge_trap=True, mature_flag_block=True, touch_tag=True, judas_max_adr=0.9, lc_tag=True, lc_reentry=True, htf_sibi_short_zone=True, htf_sibi_need_smt=True,
               breaker_by_close=True, breaker_day_life=True, mitigation_entry=True, mss_requires_htf_agreement=True, profile_two_session=True, profile_consol_pm=True,
               lod_zone_first=True, smt_open_points=True, smt_pre=True, smt_windows=((570, 660),), smt_pm_points=True, nfp_release_fvg=True, release_ob_entry=True,
               post_news_continuation=True, news_profile="pool_test", pm_reversal=True, pm_reversal_pool="lunch_or_am", require_judas_news=True, judas_news_tag=True)
    full, added = _la(df, 5, "ES", p, ENTRY + ["draw_px", "lv_tags"], every=6, meta=meta)
    assert added                                                                                              # the new code ran


def test_every_new_switch_is_in_a_look_ahead_run():
    """Every behaviour switch of this chunk is on in one of the no-look-ahead runs (the synthetic groups or the ES run)."""
    src = open(__file__, encoding="utf-8").read()
    cover = str(GROUPS) + src[src.index("def test_look_ahead_synthetic_post_mss"):src.index("def test_every_new_switch_is_in_a_look_ahead_run")]
    assert "lod_zone_first" in cover
    tuning = {"po3_seq_below_pts", "compressed_k", "compressed_n", "mature_pd", "nfp_release_fvg_min", "nfp_release_fvg_add", "post_news_run_pts", "judas_news_min",
              "breaker_disp_bars", "mit_entry_px", "laggard_consol_only", "markets"}
    for s_ in NEW_A + NEW_B:
        if s_ in tuning:
            continue
        assert s_ in cover, s_
