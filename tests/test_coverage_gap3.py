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
@pytest.mark.parametrize("name", ["gaps", "sick", "smt"])
def test_look_ahead_es(name):
    es, nq, ym = _es3()
    kw = dict(partner=nq, partner2=ym)
    sets = {"gaps": dict(ndog_min_pts=0.0, ndog_life="16h", ndog_ce_filter=True),
            "sick": dict(sick_sister=True, sick_consol_only=False),
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
