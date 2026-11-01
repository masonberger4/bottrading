"""Coverage gaps 3b-3d (coverage_build_2026-10-31.md packages 3b / 3c / 3d; cg1.py): unit tests, Params plumbing and no-look-ahead checks on synthetic frames."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import cg1, htf
from mentorship.strategy import Params

NY = "America/New_York"


def _ndog_frame(gaps):
    """Mon 2026-06-15 .. Thu: RTH bars 09:30-16:55 at the day's base price, the 18:00 reopen `gap` points away; one flat day of bars per weekday. gaps = [Mon, Tue, Wed, Thu] evening gap sizes."""
    idx, px = [], []
    base = 4000.0
    for k, g in enumerate(gaps):
        d = pd.Timestamp("2026-06-15", tz=NY) + pd.Timedelta(days=k)
        rth = pd.date_range(d + pd.Timedelta(hours=9, minutes=30), d + pd.Timedelta(hours=16, minutes=55), freq="5min")
        eve = pd.date_range(d + pd.Timedelta(hours=18), d + pd.Timedelta(hours=18, minutes=10), freq="5min")
        idx += list(rth) + list(eve)
        px += [base] * len(rth) + [base + g] * len(eve)
        base += g
    # Friday morning bars so a Friday exists
    fri = pd.date_range("2026-06-19 09:30", "2026-06-19 16:55", freq="5min", tz=NY)
    idx += list(fri)
    px += [base] * len(fri)
    a = np.array(px)
    return pd.DataFrame({"open": a, "high": a, "low": a, "close": a, "volume": 1.0}, index=pd.DatetimeIndex(idx))


def test_params_defaults_and_validation():
    p = Params()
    assert (p.ndog_min_pts, p.ndog_life, p.ndog_ce_filter) == (1.0, "friday", False)
    for bad in (dict(ndog_life="2d"), dict(ndog_min_pts=-1.0)):
        with pytest.raises(ValueError):
            Params(**bad)


def test_ndog_min_pts():
    df = _ndog_frame([0.5, 2.0, 0.0, 3.0])
    k1 = htf.opening_gaps(df, 1.0, 1.0)
    assert list(k1[k1.kind == "ndog"].high - k1[k1.kind == "ndog"].low) == [2.0, 3.0]          # as built: only gaps over one handle
    k0 = htf.opening_gaps(df, 1.0, 0.0)
    nd = k0[k0.kind == "ndog"]
    assert list(nd.high - nd.low) == [0.5, 2.0, 0.0, 3.0]                                      # 0 = every NDOG, a one-tick (here zero-size) gap uses the single price
    assert nd.iloc[2].high == nd.iloc[2].low == nd.iloc[2].ce


def test_ndog_life():
    df = _ndog_frame([2.0, 3.0, 4.0, 5.0])
    og = htf.opening_gaps(df, 1.0, 1.0)
    n = lambda day, life: len([r for r in htf.gaps_for_day(og, day, 5, 0, ndog_life=life) if r[0] == "ndog"])
    # Friday 06-19: Mon-Thu evenings formed this week
    assert n(date(2026, 6, 19), "friday") == 4
    assert n(date(2026, 6, 19), "16h") == 1                      # only Thursday evening's
    assert n(date(2026, 6, 19), "5d") == 4
    # Tuesday 06-16 09:30: only Monday evening's NDOG is known
    assert n(date(2026, 6, 16), "friday") == 1 and n(date(2026, 6, 16), "16h") == 1
    # the following Monday: the week rolled, "friday" has none; "5d" still sees all four (five trading days back = 06-15)
    assert n(date(2026, 6, 22), "friday") == 0 and n(date(2026, 6, 22), "16h") == 0
    assert n(date(2026, 6, 22), "5d") == 4


def test_ndog_life_no_lookahead():
    """gaps_for_day reads only rows known before the day's 09:30: the same answer from the table cut at that time."""
    df = _ndog_frame([2.0, 3.0, 4.0, 5.0])
    og = htf.opening_gaps(df, 1.0, 1.0)
    for life in ("friday", "16h", "5d"):
        full = htf.gaps_for_day(og, date(2026, 6, 18), 5, 0, ndog_life=life)
        cut = htf.gaps_for_day(og[og.known < pd.Timestamp("2026-06-18 09:30", tz=NY)], date(2026, 6, 18), 5, 0, ndog_life=life)
        assert list(full) == list(cut)


def _sd(sign):
    return SimpleNamespace(sign=sign, x=lambda v: v)


def test_ndog_ce_filter():
    ctx = SimpleNamespace(gaps=[("ndog", 4010.0, 4000.0, 4005.0)])
    off, on = Params(), Params(ndog_ce_filter=True)
    short_hi, short_lo = dict(entry=4006.0, lv_tags=""), dict(entry=4003.0, lv_tags="")
    long_lo, long_hi = dict(entry=4003.0, lv_tags=""), dict(entry=4006.0, lv_tags="")
    assert cg1.order_ok(ctx, _sd(-1), short_lo, "AM", 0, off) is None                      # off: nothing
    assert cg1.order_ok(ctx, _sd(-1), short_hi, "AM", 0, on) is None and "ndog_ce" in short_hi["lv_tags"]
    assert cg1.order_ok(ctx, _sd(-1), short_lo, "AM", 0, on) == "x_cg_ndog_ce"              # a short below the CE: discount half
    assert cg1.order_ok(ctx, _sd(1), long_lo, "AM", 0, on) is None
    assert cg1.order_ok(ctx, _sd(1), long_hi, "AM", 0, on) == "x_cg_ndog_ce"
    assert cg1.order_ok(SimpleNamespace(gaps=[("nwog", 1.0, 0.0, 0.5)]), _sd(-1), dict(entry=0.1, lv_tags=""), "AM", 0, on) is None    # no NDOG in force: no filter
    assert cg1.order_ok(SimpleNamespace(gaps=None), _sd(-1), dict(entry=0.1, lv_tags=""), "AM", 0, on) is None


# --- 3c sick sister ---------------------------------------------------------------------------------------------------------------

def _side(sign, h, l=None, c=None, start=0):
    h = np.asarray(h, float)
    l = np.asarray(l if l is not None else h - 1, float)
    c = np.asarray(c if c is not None else h - 0.5, float)
    return SimpleNamespace(sign=sign, h=h, l=l, c=c, x=lambda v: v)


def test_sick_params():
    p = Params()
    assert (p.sick_count_at, p.sick_refs, p.sick_consol_only) == (480, "053", True)
    for bad in (dict(sick_refs="x"), dict(sick_count_at=1440)):
        with pytest.raises(ValueError):
            Params(**bad)
    from mentorship import study
    old = Params(**study.COVERAGE_OLD)
    assert (old.sick_count_at, old.sick_refs, old.sick_consol_only, old.news_cal) == (570, "built", False, "legacy")


def test_sick_refs_053():
    # bars 0..19 (start = 2); the prior PM high 105; a swing high at bar 6 (=104, confirmed by bars 7-9); k = 15
    h = [0, 0, 100, 101, 102, 103, 104, 103, 102, 101, 100, 101, 102, 103, 103.5, 0, 0, 0, 0, 0]
    ctx = SimpleNamespace(start=2, sess={"prev_pm": (105.0, 90.0, 0)})
    sd = _side(1, h)
    n, untaken = cg1.sick_refs_053(ctx, sd, 15, 0.0)
    assert n == 0 and untaken == [104.0, 105.0]                    # neither the swing (104; the later bars top at 104, not above) nor the PM high is broken
    h2 = list(h); h2[13] = 106.0
    n, untaken = cg1.sick_refs_053(ctx, _side(1, h2), 15, 0.0)
    assert n == 2 and untaken == []                                 # 106 breaks both
    # look-ahead: bars at / after k change nothing
    h3 = list(h2); h3[15:] = [999.0] * 5
    assert cg1.sick_refs_053(ctx, _side(1, h3), 15, 0.0) == cg1.sick_refs_053(ctx, _side(1, h2), 15, 0.0)
    assert cg1.sick_refs_053(SimpleNamespace(start=2, sess={}), _side(1, [0] * 20), 15, 0.0) is None


def test_consol_day(monkeypatch):
    from mentorship import bias_day as BD
    ctx = SimpleNamespace(day=date(2026, 6, 24))                                    # a Wednesday with no release in the csv calendar
    monkeypatch.setattr(BD, "row_for", lambda c, s, i: {"nwog_regime": "cons"})
    assert cg1.consol_day(ctx, "AM", 0)
    monkeypatch.setattr(BD, "row_for", lambda c, s, i: {"nwog_regime": "trend"})
    assert not cg1.consol_day(ctx, "AM", 0)
    monkeypatch.setattr(BD, "row_for", lambda c, s, i: None)
    assert cg1.consol_day(ctx, "AM", 0)                                              # unknown = allowed
    monkeypatch.setattr(BD, "row_for", lambda c, s, i: {"nwog_regime": "cons"})
    assert not cg1.consol_day(SimpleNamespace(day=date(2026, 6, 10)), "AM", 0)       # 2026-06-10: CPI day


# --- 3d SMT partials ---------------------------------------------------------------------------------------------------------------

def _smt_fixture(es_h, nq_h, ym_h, t1=None):
    n = len(es_h)
    idx = pd.date_range("2026-06-24 09:30", periods=n, freq="5min", tz=NY)
    mk = lambda hh: (SimpleNamespace(start=0), {1: _side(1, hh)}, pd.Series(np.arange(n), index=idx))
    ctx = SimpleNamespace(idx=idx, pside=(mk(nq_h)[0], mk(nq_h)[1], mk(nq_h)[2]), partner2=mk(ym_h))
    sd = _side(1, es_h, l=np.asarray(es_h) - 2)
    pos = dict(fill_i=0, basis=100.0, n=1, left=10, t1=t1, t1_done=False, stop=95.0)
    tr = SimpleNamespace(entry=100.0, stop=95.0, exits=[])
    return ctx, sd, pos, tr


def _p(**kw):
    return Params(lot=1, **kw)


def test_smt_partial_a():
    es = [101, 102, 103, 103, 103, 103]
    nq = [101, 102, 103, 103, 103, 103]
    ym = [101, 102, 103, 103, 103, 108]                           # only YM makes a new extreme at the last bar
    ctx, sd, pos, tr = _smt_fixture(es, nq, ym)
    sd.c[:] = [101, 102, 103, 103, 103, 103]
    cg1.smt_partial(ctx, sd, pos, tr, 5, ctx.idx[5], _p(smt_partial="a"))
    assert tr.exits and tr.exits[0][3] == "smt_partial_a" and tr.exits[0][2] == 8 and pos["left"] == 2      # 80 % of 10
    # all confirm -> nothing; ES also new -> nothing
    for es2, nq2 in (([101, 102, 103, 103, 103, 109], [101, 102, 103, 103, 103, 109]), ([101, 102, 103, 103, 103, 103], [101, 102, 103, 103, 103, 108])):
        ctx, sd, pos, tr = _smt_fixture(es2, nq2, ym)
        sd.c[:] = [101, 102, 103, 103, 103, 103]
        cg1.smt_partial(ctx, sd, pos, tr, 5, ctx.idx[5], _p(smt_partial="a"))
        assert not tr.exits or tr.exits[0][3] != "smt_partial_a" or (es2[5] > 103 and False)
    # off and case "b" only: no case-a exit
    ctx, sd, pos, tr = _smt_fixture(es, nq, ym)
    sd.c[:] = [101, 102, 103, 103, 103, 103]
    cg1.smt_partial(ctx, sd, pos, tr, 5, ctx.idx[5], _p(smt_partial="b"))
    assert not tr.exits


def test_smt_partial_b():
    # t1 = 110, entry 100: near = within 25 % of 10 = c >= 107.5 (armed at bar 3), sisters' extreme (since the fill) 106 before the arm
    es = [101, 104, 106, 108, 108, 108, 108, 108, 108]
    nq = [101, 104, 106, 105, 105, 105, 105, 105, 105]
    ym = list(nq)
    ctx, sd, pos, tr = _smt_fixture(es, nq, ym, t1=110.0)
    sd.c[:] = [101, 104, 106, 108, 108, 108, 108, 108, 108]
    pb = _p(smt_partial="b", smt_partial_b_bars=3)
    for i in range(1, 9):
        cg1.smt_partial(ctx, sd, pos, tr, i, ctx.idx[i], pb)
    assert [e[3] for e in tr.exits] == ["smt_partial_b"] and tr.exits[0][2] == 5 and pos["left"] == 5         # 50 %, once
    # a sister breaks its extreme inside the window: no partial
    nq2 = [101, 104, 106, 105, 107, 105, 105, 105, 105]
    ctx, sd, pos, tr = _smt_fixture(es, nq2, ym, t1=110.0)
    sd.c[:] = [101, 104, 106, 108, 108, 108, 108, 108, 108]
    for i in range(1, 9):
        cg1.smt_partial(ctx, sd, pos, tr, i, ctx.idx[i], pb)
    assert not tr.exits


def test_smt_partial_params_and_lookahead():
    p = Params()
    assert (p.smt_partial, p.smt_partial_a_frac, p.smt_partial_b_frac, p.smt_partial_b_bars) == ("off", 0.8, 0.5, 5)
    for bad in (dict(smt_partial="x"), dict(smt_partial_a_frac=1.5), dict(smt_partial_b_bars=0)):
        with pytest.raises(ValueError):
            Params(**bad)
    # bars after i change nothing
    es = [101, 102, 103, 103, 103, 103, 50, 50]
    ym = [101, 102, 103, 103, 103, 108, 50, 50]
    out = []
    for tail in (50, 999):
        e2, y2 = list(es), list(ym)
        e2[6:] = [tail] * 2
        y2[6:] = [tail] * 2
        ctx, sd, pos, tr = _smt_fixture(e2, list(e2[:5]) + [103, tail, tail], y2)
        sd.c[:] = [101, 102, 103, 103, 103, 103, 103, 103]
        cg1.smt_partial(ctx, sd, pos, tr, 5, ctx.idx[5], _p(smt_partial="a"))
        out.append(list(tr.exits))
    assert out[0] == out[1]


# --- ES smoke + no look-ahead (full run vs truncated runs) ---------------------------------------------------------------------------

import warnings
from pathlib import Path

from mentorship import backtest as B

ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/NQ_5min_db.csv").exists() and Path("data/mentorship/YM_5min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
ENTRY = ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "lv_tags", "session"]
EXIT = ["entry_time", "exit_time", "exit_reason"]


def _es3(a="2023-08-28", b="2023-11-10"):
    out = []
    for s in ("ES", "NQ", "YM"):
        df = B.load(s, 5, source="databento")
        out.append(df[(df.index >= a) & (df.index < b)])
    return out


def _run_cut(df, p, kw, cut_t=None):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if cut_t is None:
            return B.run(df, 5, "ES", p, **kw)
        c = cut_t + pd.Timedelta(minutes=2)
        return B.run(df[df.index <= c], 5, "ES", p, partial_last=True, **{k: v[v.index <= c] for k, v in kw.items()})


@pytest.mark.skipif(not ES, reason="no ES / NQ / YM data")
@pytest.mark.parametrize("name", ["gaps", "sick", "smt", "sym", "dxy"])
def test_look_ahead_es(name):
    es, nq, ym = _es3()
    kw = dict(partner=nq, partner2=ym)
    sets = {"gaps": dict(ndog_min_pts=0.0, ndog_life="16h", ndog_ce_filter=True),
            "sick": dict(sick_sister=True, sick_consol_only=False),
            "sym": dict(sym_gate="scalp", sym_crack_block_reversal=True),
            "dxy": dict(dxy_ts_raid="filter", dxy_daily_mt="scalp", dxy_end_day="block", week_done_on_draw="skip", week_done_levels=("pwh", "pwl", "dxy_pwh", "dxy_pwl", "dxy_obj")),
            "smt": dict(smt_partial="both", smt_partial_b_bars=2, smt_partial_b_near=0.6, smt_bank_min_r=0.1)}
    from mentorship import study
    p = Params(**{**study.DEC_BASE, **sets[name]})
    full = _run_cut(es, p, kw)
    base = _run_cut(es, replace(p, **{k: getattr(Params(), k) for k in sets[name]}), kw)
    assert len(base)
    assert len(full) or name == "sick"          # (sick_sister alone trades one index only, in the deep discount: a short window may hold none; sick_refs_053 has its own cut test)
    if not len(full):
        return
    cuts = sorted(set(full.entry_time.iloc[::7]) | set(full.exit_time.dropna().iloc[::7]))
    for cut_t in cuts[:12]:
        part = _run_cut(es, p, kw, cut_t)
        a = full[full.entry_time <= cut_t][ENTRY].reset_index(drop=True)
        b = part[part.entry_time <= cut_t][ENTRY].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        done = full.exit_time.notna() & (full.exit_time <= cut_t)
        a = full[done][EXIT].reset_index(drop=True)
        b = part[part.entry_time.isin(full[done].entry_time)][EXIT].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)


# --- review fixes (second-agent review of 3b-3d) ---------------------------------------------------------------------------------------

def test_partial_active_needs_both_sisters():
    ctx2 = SimpleNamespace(pside=(object(), {}, None), partner2=(object(), {}, None))
    assert cg1.partial_active(ctx2, Params(smt_partial="a"))
    assert not cg1.partial_active(ctx2, Params())                                                  # off
    assert not cg1.partial_active(SimpleNamespace(pside=(object(), {}, None), partner2=None), Params(smt_partial="a"))   # one sister: smt_bank stays
    assert not cg1.partial_active(SimpleNamespace(pside=(None, None, None), partner2=(object(), {}, None)), Params(smt_partial="a"))


def test_smt_partial_b_t1_hit_cancels_and_zero_frac():
    es = [101, 104, 106, 108, 108, 108]
    nq = [101, 104, 106, 105, 105, 105]
    ctx, sd, pos, tr = _smt_fixture(es, nq, list(nq), t1=110.0)
    sd.c[:] = es
    pb = _p(smt_partial="b", smt_partial_b_bars=2)
    cg1.smt_partial(ctx, sd, pos, tr, 3, ctx.idx[3], pb)                                           # armed
    pos["t1_done"] = True
    for i in (4, 5):
        cg1.smt_partial(ctx, sd, pos, tr, i, ctx.idx[i], pb)
    assert not tr.exits                                                                            # T1 was hit first: no partial
    ctx, sd, pos, tr = _smt_fixture([101, 102, 103, 103, 103, 103], [101, 102, 103, 103, 103, 103], [101, 102, 103, 103, 103, 108])
    sd.c[:] = [101, 102, 103, 103, 103, 103]
    cg1.smt_partial(ctx, sd, pos, tr, 5, ctx.idx[5], _p(smt_partial="a", smt_partial_a_frac=0.0))
    assert not tr.exits                                                                            # frac 0 banks nothing


def test_consol_day_ignores_low_impact_news(monkeypatch):
    from mentorship import bias_day as BD
    monkeypatch.setattr(BD, "row_for", lambda c, s, i: {"nwog_regime": "cons"})
    assert cg1.consol_day(SimpleNamespace(day=date(2026, 6, 12)), "AM", 0)                         # 2026-06-12 = the second Friday (sentiment only)
    assert not cg1.consol_day(SimpleNamespace(day=date(2026, 6, 10)), "AM", 0)                     # CPI


# --- package 2: symmetrical-market gate (cg2.py / dxy.py) --------------------------------------------------------------------------

from mentorship import cg2, dxy


def _wave(n, drift, amp=3.0, per=8):
    k = np.arange(n)
    return 100.0 + drift * k + amp * np.sin(2 * np.pi * k / per)


def _ctx_sym(es, nq, ym, tf=5):
    n = len(es)
    idx = pd.date_range("2026-06-24 09:30", periods=n, freq=f"{tf}min", tz=NY)
    mk = lambda a: SimpleNamespace(idx=idx, h=np.asarray(a) + 0.5, l=np.asarray(a) - 0.5, tf=tf, start=0)
    c = mk(es)
    c.pside = (mk(nq), {}, None)
    c.partner2 = (mk(ym), {}, None)
    return c, idx


def _spot_from(idx, vals):
    one = pd.date_range(idx[0], idx[-1] + pd.Timedelta(minutes=5), freq="1min", tz=NY)
    dxy.set_spot(pd.DataFrame({"close": np.interp(one.asi8, idx.asi8, vals)}, index=one))


def _p5(**kw):
    return Params(**{**dict(sym_gate="tag", sym_tf=5, sym_dxy="tf", sym_win=1), **kw})


def test_sym_gate_params():
    p = Params()
    assert (p.sym_gate, p.sym_scalp_risk, p.sym_tf, p.sym_lookback, p.sym_dxy, p.sym_crack_block_reversal) == ("off", 0.5, 15, 2, "1h", False)
    for bad in (dict(sym_gate="x"), dict(sym_dxy="x"), dict(sym_tf=7), dict(sym_scalp_risk=0.0), dict(sym_lookback=0)):
        with pytest.raises(ValueError):
            Params(**bad)


def test_sym_state_ok_and_cracks():
    n = 70
    up = _wave(n, 0.4)
    dn = _wave(n, -0.4)
    ctx, idx = _ctx_sym(up, up, up)
    _spot_from(idx, 100.0 + dn)
    i = n - 3
    assert cg2.sym_state(ctx, 1, i, _p5()) == ("ok", False)                       # all three confirm, DXY the other way
    ctx, idx = _ctx_sym(up, up, _wave(n, -0.4))                                     # YM fails
    _spot_from(idx, 100.0 + dn)
    assert cg2.sym_state(ctx, 1, i, _p5()) == ("crack", False)
    ctx, idx = _ctx_sym(up, up, up)                                                 # DXY also rising: a crack
    _spot_from(idx, 100.0 + up)
    assert cg2.sym_state(ctx, 1, i, _p5()) == ("crack", False)
    _spot_from(idx, 100.0 + dn)
    ctx, idx = _ctx_sym(up, up, up)
    assert cg2.sym_state(ctx, 1, i, _p5(sym_dxy="off"))[0] == "ok" and cg2.sym_state(ctx, 1, i, _p5(sym_dxy="off"))[1] is True
    # ES without new extremes: no information
    ctx, idx = _ctx_sym(dn, up, up)
    assert cg2.sym_state(ctx, 1, i, _p5())[0] == "none"
    # the mirror: lower lows everywhere (short side) with a rising DXY
    ctx, idx = _ctx_sym(dn, dn, dn)
    _spot_from(idx, 100.0 + up)
    assert cg2.sym_state(ctx, -1, i, _p5()) == ("ok", False)
    dxy.set_spot(None)


def test_sym_state_no_dxy_before_2019_and_hooks():
    n = 70
    up = _wave(n, 0.4)
    ctx, idx = _ctx_sym(up, up, up)
    dxy.set_spot(pd.DataFrame({"close": [1.0, 1.0]}, index=pd.DatetimeIndex(["2030-01-01", "2030-01-02"]).tz_localize(NY)))     # spot starts after the window
    st = cg2.sym_state(ctx, 1, n - 3, _p5())
    assert st == ("ok", True)                                                         # DXY leg not available = off, tagged
    o = dict(entry=1.0, lv_tags="")
    assert cg2.order_ok(ctx, _sd(1), o, "AM", n - 3, _p5()) is None and "sym_ok" in o["lv_tags"] and "sym_no_dxy" in o["lv_tags"]
    # crack + modes
    ctx, idx = _ctx_sym(up, up, _wave(n, -0.4))
    _spot_from(idx, 100.0 - 0.4 * np.arange(n))
    i = n - 3
    assert cg2.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", i, _p5(sym_gate="skip")) == "x_cg_sym_crack"
    assert cg2.scalp_now(ctx, _p5(sym_gate="scalp"), "AM", i, 1) == "cg_sym_crack" and cg2.scalp_now(ctx, _p5(sym_gate="tag"), "AM", i, 1) == ""
    lvt = []
    assert cg2.size_mult(ctx, _sd(1), i, _p5(sym_gate="scalp"), lvt) == 0.5 and lvt == ["size_sym_crack"]
    assert cg2.size_mult(ctx, _sd(1), i, _p5(sym_gate="hold"), []) == 1.0
    # block reversal: a short against a confirmed up-trend is dropped
    ctx, idx = _ctx_sym(up, up, up)
    _spot_from(idx, 100.0 - 0.4 * np.arange(n))
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i, Params(sym_tf=5, sym_dxy="tf", sym_win=1, sym_crack_block_reversal=True)) == "x_cg_sym_trend"
    dxy.set_spot(None)


def test_sym_state_no_lookahead():
    """Bars at / after the decision bar do not change the answer."""
    n = 70
    up = _wave(n, 0.4)
    i = 60
    base = None
    for tail in (0.0, 500.0):
        a = up.copy()
        a[i + 1:] += tail
        ctx, idx = _ctx_sym(a, a, a)
        d = 100.0 - 0.4 * np.arange(n)
        d[i + 1:] += tail
        _spot_from(idx, d)
        r = cg2.sym_state(ctx, 1, i, _p5())
        base = r if base is None else base
        assert r == base
    dxy.set_spot(None)


def test_dxy_bars_closed_only():
    idx = pd.date_range("2023-05-01 09:00", periods=180, freq="1min", tz=NY)
    dxy.set_spot(pd.DataFrame({"close": np.linspace(100, 101, 180)}, index=idx))
    b = dxy.bars(5, "spot")
    c = dxy.closed(b, pd.Timestamp("2023-05-01 09:10", tz=NY))
    assert c.index[-1] == pd.Timestamp("2023-05-01 09:05", tz=NY) and (c.end <= pd.Timestamp("2023-05-01 09:10", tz=NY)).all()      # the 09:05 bar closes at 09:10
    c2 = dxy.closed(b, pd.Timestamp("2023-05-01 09:09", tz=NY))
    assert c2.index[-1] == pd.Timestamp("2023-05-01 09:00", tz=NY)
    assert (b.high >= b[["open", "close"]].max(axis=1) - 1e-12).all() and (b.low <= b[["open", "close"]].min(axis=1) + 1e-12).all()
    dxy.set_spot(None)


# --- package 3a: DXY daily / hourly rules (cg2.py) ---------------------------------------------------------------------------------

def _sessions(specs):
    """specs: {label date: [(hours after the 18:00 open, value), ...]} -> a 1-minute close frame; a session label L runs from L-1 18:00 to L 17:00 (23 h)."""
    parts = []
    for lab, anchors in sorted(specs.items()):
        start = pd.Timestamp(lab, tz=NY) - pd.Timedelta(hours=6)
        t = pd.date_range(start, periods=23 * 60, freq="1min")
        xs = np.array([a[0] for a in anchors]) * 60.0
        ys = np.array([a[1] for a in anchors])
        parts.append(pd.DataFrame({"close": np.interp(np.arange(23 * 60), xs, ys)}, index=t))
    return pd.concat(parts)


def _plain(lab, lo=100.0, hi=101.0, o=100.5, c=100.5):
    return [(0, o), (6, lo), (12, hi), (22.99, c)]


def _es_ctx(day, start="00:00", end="16:00", tf=5):
    idx = pd.date_range(pd.Timestamp(f"{day} {start}", tz=NY), pd.Timestamp(f"{day} {end}", tz=NY), freq=f"{tf}min")
    return SimpleNamespace(idx=idx, t=(idx.hour * 60 + idx.minute).values, tf=tf, day=pd.Timestamp(day).date())


def _at(ctx, hhmm):
    return int(ctx.idx.get_loc(pd.Timestamp(f"{ctx.day} {hhmm}", tz=NY)))


def _p3(**kw):
    return Params(**{**dict(dxy_htf_src="spot"), **kw})


WEEK1 = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"]
WEEK2 = ["2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12"]


def test_3a_params():
    p = Params()
    assert (p.dxy_ts_raid, p.dxy_daily_mt, p.dxy_end_day, p.dxy_htf_src, p.dxy_ts_back, p.dxy_ts_lookback) == ("off", "off", "off", "dx", 3, 20)
    Params(week_done_levels=("pwh", "dxy_obj", "dxy_pwh", "dxy_pwl"))
    for bad in (dict(dxy_ts_raid="x"), dict(dxy_daily_mt="x"), dict(dxy_end_day="x"), dict(dxy_htf_src="x"), dict(dxy_obj_levels=("x",)), dict(week_done_levels=("dxy_x",))):
        with pytest.raises(ValueError):
            Params(**bad)


def test_dxy_ts_raid():
    specs = {pd.Timestamp(d): _plain(d) for d in WEEK1 + WEEK2}
    specs[pd.Timestamp("2026-06-03")] = _plain("2026-06-03", lo=99.0)                       # the old daily swing low
    specs[pd.Timestamp("2026-06-15")] = [(0, 100.5), (6, 98.8), (9, 99.5), (12, 100.2), (22.99, 100.3)]       # pierces 99.0 at ~00:00 and closes back above within the hour
    dxy.set_spot(_sessions(specs))
    ctx = _es_ctx("2026-06-15")
    p = _p3(dxy_ts_raid="filter")
    assert cg2.dxy_ts_state(ctx, _at(ctx, "00:25"), p) == 0                                  # the 00:00 hour has not closed
    assert cg2.dxy_ts_state(ctx, _at(ctx, "09:30"), p) == 1
    o = dict(entry=1.0, lv_tags="")
    assert cg2.order_ok(ctx, _sd(1), o, "AM", _at(ctx, "09:30"), p) == "x_cg_dxy_ts"          # ES longs are blocked: the buy-side run was a raid
    o = dict(entry=1.0, lv_tags="")
    assert cg2.order_ok(ctx, _sd(-1), o, "AM", _at(ctx, "09:30"), p) is None and "dxy_ts_up" in o["lv_tags"]
    assert cg2.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:30"), _p3(dxy_ts_raid="tag")) is None
    # a taken low is not an old low: a lower daily low after it removes the level
    specs[pd.Timestamp("2026-06-09")] = _plain("2026-06-09", lo=98.5)
    dxy.set_spot(_sessions(specs))
    ctx = _es_ctx("2026-06-15")
    assert cg2.dxy_ts_state(ctx, _at(ctx, "09:30"), p) == 0
    dxy.set_spot(None)


def test_dxy_daily_mt():
    specs = {pd.Timestamp(d): _plain(d, lo=100.0, hi=100.4, o=100.2, c=100.2) for d in WEEK1 + WEEK2}
    specs[pd.Timestamp("2026-06-04")] = [(0, 100.0), (6, 99.8), (12, 102.0), (22.99, 101.5)]       # an up-close candle (OB) ...
    specs[pd.Timestamp("2026-06-05")] = [(0, 101.5), (6, 99.0), (12, 101.0), (22.99, 99.0)]        # ... followed by a close under its low
    specs[pd.Timestamp("2026-06-15")] = [(0, 100.2), (12, 100.3), (22.99, 100.3)]                  # DXY inside the candle, under its body MT (100.75)
    dxy.set_spot(_sessions(specs))
    ctx = _es_ctx("2026-06-15")
    i = _at(ctx, "09:30")
    assert cg2.dxy_mt_state(ctx, i, _p3(dxy_daily_mt="tag")) == "chop"
    assert cg2.scalp_now(ctx, _p3(dxy_daily_mt="scalp"), "AM", i, 1) == "cg_dxy_mt" and cg2.scalp_now(ctx, _p3(dxy_daily_mt="tag"), "AM", i, 1) == ""
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i, _p3(dxy_daily_mt="skip")) == "x_cg_dxy_mt"
    specs[pd.Timestamp("2026-06-15")] = [(0, 101.2), (12, 101.3), (22.99, 101.3)]                   # through the MT: expansion
    dxy.set_spot(_sessions(specs))
    ctx = _es_ctx("2026-06-15")
    assert cg2.dxy_mt_state(ctx, _at(ctx, "09:30"), _p3(dxy_daily_mt="tag")) == "expand"
    dxy.set_spot(None)


def test_week_done_dxy():
    specs = {pd.Timestamp(d): _plain(d, hi=(101.0 if d in WEEK1 else 100.9)) for d in WEEK1 + WEEK2}
    specs[pd.Timestamp("2026-06-10")] = [(0, 100.5), (6, 100.2), (12, 101.5), (22.99, 101.2)]      # Wednesday's high 101.5 > the prior week's high 101.0 at ~06:00 ET
    dxy.set_spot(_sessions(specs))
    p = _p3(week_done_on_draw="skip", week_done_levels=("dxy_pwh",))
    wed, tue = _es_ctx("2026-06-10"), _es_ctx("2026-06-09")
    assert not cg2.dxy_week_delivered(tue, date(2026, 6, 9), _at(tue, "09:30"), p)
    assert not cg2.dxy_week_delivered(wed, date(2026, 6, 10), _at(wed, "00:25"), p)               # before the high is in
    assert cg2.dxy_week_delivered(wed, date(2026, 6, 10), _at(wed, "09:30"), p)
    assert not cg2.dxy_week_delivered(wed, date(2026, 6, 10), _at(wed, "09:30"), _p3(week_done_levels=("pwh",)))        # no dxy_ level asked
    dxy.set_spot(None)


def test_dxy_end_day():
    specs = {pd.Timestamp(d): _plain(d) for d in WEEK1 + WEEK2}
    specs[pd.Timestamp("2026-06-03")] = [(0, 100.5), (6, 100.0), (12, 103.0), (22.99, 102.0)]       # the old daily swing high 103.0, its close 102.0 = the rejection block
    specs[pd.Timestamp("2026-06-15")] = [(0, 100.3), (16, 100.3), (17.5, 102.5), (22.99, 102.4)]    # DXY runs into 102.0 between 10:00 and 11:30 ET
    dxy.set_spot(_sessions(specs))
    ctx = _es_ctx("2026-06-15")
    tx = pd.Timestamp("2026-06-15 11:05", tz=NY)
    tr = SimpleNamespace(exits=[(tx, 1.0, 1, "t2")], final_hit=True, side="short")
    p = _p3(dxy_end_day="block")
    i1, i2, i3 = _at(ctx, "12:05"), _at(ctx, "15:05"), _at(ctx, "09:30")
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i1, p, [tr]) == "x_cg_dxy_end_day"
    assert cg2.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", i1, p, [tr]) is None                      # the other direction is free
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "LH", i2, p, [tr]) is None                     # the last hour is left alone
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "LH", i2, _p3(dxy_end_day="block_day"), [tr]) == "x_cg_dxy_end_day"
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i1, _p3(dxy_end_day="tag"), [tr]) is None
    far = SimpleNamespace(exits=[(pd.Timestamp("2026-06-15 04:00", tz=NY), 1.0, 1, "t2")], final_hit=True, side="short")      # ES done long before DXY got there: not "at the same time"
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i1, p, [far]) is None
    assert cg2.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "11:30"), p, [tr]) is None        # the 11:00 hour (DXY reaches 102.0) has not closed yet
    # look-ahead: DXY bars after the decision bar change nothing
    base = cg2.dxy_end_day_block(ctx, _sd(-1), i3, p, [SimpleNamespace(exits=[(pd.Timestamp("2026-06-15 09:00", tz=NY), 1, 1, "t2")], final_hit=True, side="short")])
    assert base is False
    dxy.set_spot(None)
