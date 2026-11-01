"""Caption-gap pass, package bias_htf#6/7: the ENGINE hooks (bh6e.py) on hand-made days built with the real DayCtx and DayPlan (the both-pools side gate, the scenario re-lock, the seven-factor tag), the
table with every new column, the no-look-ahead runs (full vs truncated; synthetic windows, hand-made days; ES windows skip without the data) and the check that every new switch is live in an executed run
(second file of tests/test_caption_gap_bh6.py). Nothing here needs market data except the ES windows; no file outside the repo is written."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh6 as BH6, bh6e as E6, bias_day as BD, htf
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, history  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks  # noqa: E402
from test_caption_gap_bh3b import order  # noqa: E402

D1 = date(2026, 3, 10)                          # a Tuesday


def p6(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


def mkd(p, rows, bias=None, hist=None, d=D1, base=100.0, start="09:30", **kw):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start, base=base, **kw)
    ctx.intermarket = {}
    return ctx


# --- X8-061-continuation-after-both-pools ---------------------------------------------------------------------------------------

def test_both_pools_gate():
    """The test is on the price the order is armed at (spec: 1.0845 rejected, 1.0835 allowed with the cap at 1.0840)."""
    p = p6(both_pools_gate=True)
    bias = BR(combo=0, both_pools=1, bp_dir=-1, cont_cap=100.5)
    flat = [(100.2, 100.4, 100.0, 100.2)] * 12
    ctx = mkd(p, flat, bias)
    i = at(ctx, "09:50")
    sd, su = ctx.sides_map[-1], ctx.sides_map[1]
    assert E6.side_ok(ctx, p, -1, "AM", i) is None                           # the side itself stays open; the armed price decides
    assert E6.order_ok(ctx, sd, dict(order(), entry=100.45), "AM", i, p) is None            # a short armed under the cap: allowed
    assert E6.order_ok(ctx, sd, dict(order(), entry=100.55), "AM", i, p) == "x_bh6_both_pools"       # armed above the cap: rejected although the market is below it
    assert E6.order_ok(ctx, su, dict(order(), entry=100.9), "AM", i, p) is None            # the gate only reads the continuation side
    above = mkd(p, [(101.0, 101.2, 100.8, 101.0)] * 12, bias, base=101.0)
    ia = at(above, "09:50")
    assert E6.order_ok(above, above.sides_map[-1], dict(order(), entry=100.4), "AM", ia, p) is None       # a retrace-into-the-OB short with the market closed above the cap: allowed
    assert E6.order_ok(above, above.sides_map[-1], dict(order(), entry=101.0), "AM", ia, p) == "x_bh6_both_pools"
    up = mkd(p, [(99.0, 99.2, 98.8, 99.0)] * 12, BR(combo=0, both_pools=1, bp_dir=1, cont_cap=99.5), base=99.0)
    iu = at(up, "09:50")
    assert E6.order_ok(up, up.sides_map[1], dict(order(), entry=99.0), "AM", iu, p) == "x_bh6_both_pools"       # the mirror: a long armed below the cap
    assert E6.order_ok(up, up.sides_map[1], dict(order(), entry=99.6), "AM", iu, p) is None
    quiet = mkd(p, flat, BR(combo=0, both_pools=0, bp_dir=0, cont_cap=100.5))
    assert E6.order_ok(quiet, quiet.sides_map[-1], dict(order(), entry=101.0), "AM", at(quiet, "09:50"), p) is None        # not a both-pools day
    nocap = mkd(p, flat, BR(combo=0, both_pools=1, bp_dir=-1, cont_cap=float("nan")))
    assert E6.order_ok(nocap, nocap.sides_map[-1], dict(order(), entry=101.0), "AM", at(nocap, "09:50"), p) is None        # nothing to measure against: inert
    off = Params(**BASE, htf_bias="combo", bias_neutral="both")
    assert E6.order_ok(ctx, sd, dict(order(), entry=100.55), "AM", i, off) is None
    from mentorship import daycontext as DW
    assert DW.order_ok(ctx, sd, dict(order(), entry=100.55), "AM", i, p) == "x_bh6_both_pools"       # wired through the order_ok chain


# --- new-live-vs-analysis-mismatch -----------------------------------------------------------------------------------------------

def _lock(**kw):
    return dict(dict(side=-1, target=90.0, kind="pool", name="PDL", delivered=False, delivered_t=None, delivered_i=None, marked=[], session="AM", t_lock=570, px=100.0, traded=False, day=D1), **kw)


DIVE = [(100.0, 100.1, 99.9, 100.0)] * 3 + [(100.0, 100.1, 92.0, 92.5), (92.5, 92.6, 88.0, 88.5)] + [(88.5, 88.6, 88.4, 88.5)] * 8


def test_scenario_check():
    p = p6(scenario_check=True)
    ctx = mkd(p, DIVE, BR(combo=-1))
    i = at(ctx, "09:50")
    lk = _lock()
    ctx.lock = {"AM": lk}
    assert E6.scenario_broken(ctx, p, lk, i)                                 # the PDL (the draw) was run first: a close under 90 and a bearish gap, the PDH raid never came
    assert not E6.scenario_broken(ctx, p, lk, at(ctx, "09:45"))              # the closing bar is not there yet (92.5 is above the pool)
    done: dict = {}
    r = E6.lock_bar(ctx, p, "AM", lk, i, done, [], None)
    assert r is not None and r[1] is True and r[0]["side"] == 0 and done == {"AM": True} and r[0]["scn_done"]     # stand aside: pending cancelled, the session ends
    assert E6.lock_bar(ctx, p, "AM", dict(lk, scn_done=True), i, {}, [], None) is None                     # once per lock
    flip = p6(scenario_check=True, scenario_flip=True)
    ctx2 = mkd(flip, DIVE, BR(combo=-1))
    ctx2.lock = {"AM": lk}
    done2: dict = {}
    r2 = E6.lock_bar(ctx2, flip, "AM", _lock(), i, done2, [], None)
    assert r2 is not None and r2[0]["side"] == 1 and done2 == {}               # the bias of the rest of the session flips to the other side (new setups only)
    assert E6.lock_bar(ctx, p6(), "AM", lk, i, {}, [], None) is None            # switch off
    # the raid came first: the scenario is on track
    raid = [(100.0, 100.1, 99.9, 100.0), (100.0, 109.0, 99.9, 100.0), (100.0, 100.1, 99.9, 100.0)] + DIVE[3:]
    ctx3 = mkd(p, raid, BR(combo=-1))
    assert not E6.scenario_broken(ctx3, p, _lock(), at(ctx3, "09:50"))
    # a fill already happened, or the draw was delivered: nothing to cancel
    assert not E6.scenario_broken(ctx, p, _lock(traded=True), i) and not E6.scenario_broken(ctx, p, _lock(delivered=True), i)
    # a close beyond the pool without a gap is not displacement
    slow = [(100.0, 100.1, 99.9, 100.0)] * 2 + [(100.0, 100.0, 94.0, 94.5), (94.5, 96.0, 92.0, 93.0), (93.0, 94.5, 88.0, 88.5)] + [(88.5, 88.6, 88.4, 88.5)] * 8
    ctx4 = mkd(p, slow, BR(combo=-1))
    assert not E6.scenario_broken(ctx4, p, _lock(), at(ctx4, "09:50"))
    # the long side mirror: the PDH (108) is the draw, the PDL (90) the raid
    up_rows = [(100.0, 100.1, 99.9, 100.0)] * 3 + [(100.0, 108.0, 99.9, 107.5), (107.5, 111.0, 107.4, 110.8)] + [(110.8, 110.9, 110.7, 110.8)] * 8
    ctx5 = mkd(p, up_rows, BR(combo=1))
    assert E6.scenario_broken(ctx5, p, _lock(side=1, target=108.0), at(ctx5, "09:50"))


# --- new-seven-factor-context ------------------------------------------------------------------------------------------------------

def test_factor_count_tag():
    p = p6(factor_tag=True)
    row = BR(combo=1, iof=1, flip=0, wk_bias=1, mob=1, m_ctrl=0)
    ctx = mkd(p, [(100.0, 100.2, 99.8, 100.0)] * 14, row)
    i = at(ctx, "09:50")
    sd = ctx.sides_map[1]
    o = dict(order(), smt=True, htf=True)
    assert E6.order_ok(ctx, sd, o, "AM", i, p) is None                        # a label, never a rejection
    assert "f7_b2m2s3" in o["lv_tags"] and "f7_high" in o["lv_tags"]
    o2 = dict(order(), smt=False, htf=True)
    E6.order_ok(ctx, sd, o2, "AM", i, p)
    assert "f7_b2m2s2" in o2["lv_tags"] and "f7_high" not in o2["lv_tags"]
    o3 = dict(order(tags="smt_laggard"), smt=True, htf=True)
    E6.order_ok(ctx, sd, o3, "AM", i, p)
    assert "f7_b2m2s2" in o3["lv_tags"]                                       # a laggard SMT is no factor for the order
    late = mkd(p, [(100.0, 100.2, 99.8, 100.0)] * 90, row)
    o4 = dict(order(), smt=True, htf=True)
    E6.order_ok(late, late.sides_map[1], o4, "AM", at(late, "12:30"), p)
    assert "f7_b2m2s2" in o4["lv_tags"] and "f7_high" not in o4["lv_tags"]    # outside the 09:30-11:00 / 13:30-15:00 windows
    bear = mkd(p, [(100.0, 100.2, 99.8, 100.0)] * 14, BR(combo=-1, iof=-1, flip=-1, wk_bias=-1, mob=0, m_ctrl=-1))
    o5 = dict(order(), smt=False, htf=False)
    E6.order_ok(bear, bear.sides_map[-1], o5, "AM", at(bear, "09:50"), p)
    assert "f7_b2m3s1" in o5["lv_tags"]
    off = Params(**BASE, htf_bias="combo", bias_neutral="both")
    o6 = dict(order())
    E6.order_ok(ctx, sd, o6, "AM", i, off)
    assert "f7" not in o6["lv_tags"]
    from mentorship import daycontext as DW
    o7 = dict(order(), smt=True, htf=True)
    DW.order_ok(ctx, sd, o7, "AM", i, p)
    assert "f7_b2m2s3" in o7.get("lv_tags", "")                               # wired through the order_ok chain


# --- the table -----------------------------------------------------------------------------------------------------------------------

TABLE_A = dict(htf_bias="mob", both_pools_gate=True, weekly_persist=True, factor_tag=True)
NEW_COLS = ("both_pools", "bp_dir", "cont_cap", "mob", "m_ctrl")


@pytest.fixture(scope="module")
def walk():
    from test_caption_gap_bh1c import fut_walk
    return fut_walk("2024-09-02", "2026-03-27", seed=7, vol=0.9)


def _build(p, df):
    return htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))


def test_table_builds_every_column_and_default_is_unchanged(walk):
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _build(Params(**FUT, **TABLE_A), walk)
        t0 = _build(Params(**FUT, htf_bias="combo2"), walk)
        t1 = _build(Params(**FUT, htf_bias="combo2", both_pools_gate=True), walk)
        t2 = _build(Params(**FUT, htf_bias="mob"), walk)
    assert not [c for c in NEW_COLS if c not in t.columns], [c for c in NEW_COLS if c not in t.columns]
    assert not [c for c in NEW_COLS if c in t0.columns]
    base_cols = list(t0.columns)
    pd.testing.assert_frame_equal(t0[base_cols], t1[base_cols])               # a column switch changes no existing column
    assert t.both_pools.isin([0, 1]).all() and t.bp_dir.isin([-1, 0, 1]).all() and t.mob.isin([-1, 0, 1]).all() and t.m_ctrl.isin([-1, 0, 1]).all()
    assert t.both_pools.sum() > 0 and t.mob.abs().sum() > 0, "the synthetic walk shows no both-pools day / monthly OB activation"
    assert (t.both_pools == (t.bp_dir != 0).astype(int)).all()
    live = t[t.both_pools == 1]
    assert live.cont_cap.notna().mean() > 0.5
    assert (t2.mob == t.mob).all() and BH2.HITS["sw_both_pools_gate"] > 0 and BH2.HITS["sw_mob"] > 0
    # a Params with the mob bias reads the column as the want
    assert BD.bias_col(Params(**FUT, htf_bias="mob")) == "mob"
    assert (t.wk_bias.isin([-1, 0, 1])).all()


def test_table_rows_do_not_look_ahead():
    from test_caption_gap_bh1c import fut_walk
    from test_caption_gap_bh1f import _same
    df = fut_walk("2025-03-03", "2026-03-27", seed=11, vol=0.9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, **TABLE_A)
        full = _build(p, df)
        cols = list(NEW_COLS) + ["wk_bias", "draw", "pd", "flip", "iof"]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part = _build(p, df[df.index < cut])
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])


def test_weekly_persist_on_a_real_table(walk):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = _build(Params(**FUT, htf_bias="wk"), walk)
        b = _build(Params(**FUT, htf_bias="wk", weekly_persist=True), walk)
    assert list(a.index) == list(b.index)
    diff = a.wk_bias != b.wk_bias
    # the persisted reading differs from the plain one only on a Tue-Fri row, never on a week's first row
    wk = pd.Series([pd.Timestamp(x).to_period("W-FRI") for x in a.index], index=a.index)
    first = wk != wk.shift(1)
    assert not (diff & first).any()
    assert (b.wk_bias.isin([-1, 0, 1])).all()
    other = [c for c in a.columns if c != "wk_bias"]
    pd.testing.assert_frame_equal(a[other], b[other])                         # nothing else moves


# --- the engine on synthetic and ES windows ----------------------------------------------------------------------------------------------------------------------

LA_SETS = {   # name -> switches (the draw lock stays on); each leaves trades on its windows
    "gates": dict(htf_bias="combo", bias_neutral="both", both_pools_gate=True, factor_tag=True, weekly_persist=True),
    "scenario": dict(htf_bias="combo", bias_neutral="both", scenario_check=True),
    "scenario_flip": dict(htf_bias="combo", bias_neutral="both", scenario_check=True, scenario_flip=True),
    "mob": dict(htf_bias="mob", bias_neutral="both"),
}


LA_HITS = {"gates": ("both_pools_gate", "factor_tag", "weekly_persist"), "scenario": ("scenario_check",), "scenario_flip": ("scenario_check", "scenario_flip"), "mob": ("mob",)}


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh6(name):
    x, y = _walks()
    p = Params(**dict(LA, **LA_SETS[name]))
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    for k in LA_HITS[name]:
        assert BH2.HITS["sw_" + k] > 0, f"{name}: {k} never acted in the full run"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM, exits=True, min_trades=1)


ES_WIN = {"gates": ("2023-03-06", "2023-03-24"), "scenario": ("2023-03-06", "2023-03-24"), "scenario_flip": ("2023-03-06", "2023-03-24"), "mob": ("2023-03-06", "2023-03-24")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(ES_WIN))
def test_look_ahead_es_bh6(name):
    es = B.load("ES", 5, source="databento")
    a, b = ES_WIN[name]
    df = es[(es.index >= pd.Timestamp(a, tz=B.NY)) & (es.index < pd.Timestamp(b, tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**dict(LA, **LA_SETS[name]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta, intermarket=IM))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 2), meta=meta, intermarket=IM, exits=True, min_trades=1)


def test_look_ahead_hand_made_day():
    from test_caption_gap_bh4c import la_day4
    for kw, bias in ((dict(both_pools_gate=True), BR(combo=1, both_pools=1, bp_dir=-1, cont_cap=90.0)), (dict(factor_tag=True), BR(combo=1, wk_bias=1, mob=1, iof=1)),
                     (dict(scenario_check=True), BR(combo=1))):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            la_day4(p6(**kw), bias=bias, min_trades=1)


def test_scenario_poison_is_causal():
    """The scenario test reads only bars <= i: poisoning every later bar leaves the answer unchanged."""
    p = p6(scenario_check=True)
    junk = [(500.0, 600.0, 1.0, 550.0)] * 8
    a = mkd(p, DIVE[:5] + junk, BR(combo=-1))
    b = mkd(p, DIVE[:5] + DIVE[5:], BR(combo=-1))
    i = at(a, "09:50")
    assert E6.scenario_broken(a, p, _lock(), i) == E6.scenario_broken(b, p, _lock(), i) is True


# --- every new switch is LIVE in an executed run ----------------------------------------------------------------------------------------------------------------

def test_every_switch_is_covered(walk):
    """Execution, not names: a `sw_<switch>` count in bh2.HITS (written by bh6.sw / bh6e.sw where the switch acts) must exist for every non-knob switch after the table with every table switch, the
    hand-made days and the per-path cases."""
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _build(Params(**FUT, **TABLE_A), walk)
        test_both_pools_gate()
        test_scenario_check()
        test_factor_count_tag()
        from test_caption_gap_bh6 import test_persist_week_keeps_the_weekly_idea, NEW_FIELDS, KNOBS
        test_persist_week_keeps_the_weekly_idea()
    live = {k[3:] for k in BH2.HITS if k.startswith("sw_")}
    missing = sorted(set(NEW_FIELDS) - KNOBS - live)
    assert not missing, f"never live in an executed run: {missing}"
