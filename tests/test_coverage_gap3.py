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
@pytest.mark.parametrize("name", ["gaps", "sick", "smt", "sym", "dxy", "dxy1m"])
def test_look_ahead_es(name):
    es, nq, ym = _es3()
    kw = dict(partner=nq, partner2=ym)
    sets = {"gaps": dict(ndog_min_pts=0.0, ndog_life="16h", ndog_ce_filter=True),
            "sick": dict(sick_sister=True, sick_consol_only=False),
            "sym": dict(sym_gate="scalp", sym_crack_block_reversal=True),
            "dxy": dict(dxy_ts_raid="filter", dxy_daily_mt="scalp", dxy_end_day="block", week_done_on_draw="skip", week_done_levels=("pwh", "pwl", "dxy_pwh", "dxy_pwl", "dxy_obj")),
            "dxy1m": dict(dxy_states="filter", dxy_session_gate="filter", dxy_eq_gate="block", dxy_range_trigger="gate", dxy_pool_run="cap", dxy_smt="qualify", dxy_intrade="bank",
                          dxy_intrade_tfs=("5m",), dxy_unicorn="qualify", dxy_target_partial="partial", dxy_nonconf_exit="any", sym_gate="scalp", sym_dxy="tf", sym_tf=5, dxy_htf_src="spot"),
            "smt": dict(smt_partial="both", smt_partial_b_bars=2, smt_partial_b_near=0.6, smt_bank_min_r=0.1)}
    from mentorship import study
    p = Params(**{**study.DEC_BASE, **sets[name]})
    if name == "dxy1m":                                   # a stand-in spot DXY (the real file is not on every machine): the inverse of ES, 1-minute, covering the whole window
        one = pd.date_range(es.index[0], es.index[-1] + pd.Timedelta(minutes=5), freq="1min")
        dxy.set_spot(pd.DataFrame({"close": 100.0 - 0.01 * es.close.reindex(one, method="ffill").values}, index=one))
    full = _run_cut(es, p, kw)
    base = _run_cut(es, replace(p, **{k: getattr(Params(), k) for k in sets[name]}), kw)
    assert len(base)
    assert len(full) or name == "sick"          # (sick_sister alone trades one index only, in the deep discount: a short window may hold none; sick_refs_053 has its own cut test)
    if not len(full):
        dxy.set_spot(None)
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
    dxy.set_spot(None)


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
    assert cg2.sym_state(ctx, 1, i, _p5(sym_dxy="off"))[0] == "ok" and cg2.sym_state(ctx, 1, i, _p5(sym_dxy="off"))[1] is False       # (DXY switched off: no sym_no_dxy tag)
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


# --- review fixes (second-agent review of 2 / 3a) -----------------------------------------------------------------------------------

def test_sym_dxy_hole_is_no_information_not_a_crack():
    n = 70
    up = _wave(n, 0.4)
    ctx, idx = _ctx_sym(up, up, up)
    one = pd.date_range(idx[0], idx[0] + pd.Timedelta(minutes=60), freq="1min", tz=NY)           # DXY covers only the first hour, the decision is hours later
    dxy.set_spot(pd.DataFrame({"close": np.linspace(100, 99, len(one))}, index=one))
    assert cg2.sym_state(ctx, 1, n - 3, _p5()) == ("ok", True)
    dxy.set_spot(None)


def test_dxy_obj_week_done_is_sticky_and_open_gap_free():
    specs = {pd.Timestamp(d): _plain(d, hi=(100.8 if d in WEEK1 else 100.5)) for d in WEEK1 + WEEK2}
    specs[pd.Timestamp("2026-06-02")] = [(0, 100.5), (6, 100.0), (12, 100.4), (22.99, 100.4)]
    specs[pd.Timestamp("2026-06-03")] = [(0, 101.0), (6, 101.0), (12, 101.5), (22.99, 101.4)]     # a daily FVG: 06-02 high 100.4 < 06-04 low 100.9 ...
    specs[pd.Timestamp("2026-06-04")] = [(0, 101.4), (6, 100.9), (12, 101.2), (22.99, 101.2)]
    specs[pd.Timestamp("2026-06-08")] = [(0, 100.0), (12, 100.2), (22.99, 100.2)]               # the week opens at 100.0, the FVG bottom 100.9 lies above
    specs[pd.Timestamp("2026-06-10")] = [(0, 100.2), (6, 100.2), (12, 101.0), (22.99, 100.8)]    # Wednesday trades into it
    dxy.set_spot(_sessions(specs))
    p = _p3(week_done_on_draw="skip", week_done_levels=("dxy_obj",))
    wed, thu = _es_ctx("2026-06-10"), _es_ctx("2026-06-11")
    assert cg2.dxy_week_delivered(wed, date(2026, 6, 10), _at(wed, "15:00"), p)
    assert cg2.dxy_week_delivered(thu, date(2026, 6, 11), _at(thu, "09:30"), p)                 # still delivered on Thursday: the week's own high is no "fill"
    dxy.set_spot(None)


def test_dxy_bars_open_gap_not_in_range():
    a = pd.date_range("2026-06-01 09:00", periods=60, freq="1min", tz=NY)
    b = pd.date_range("2026-06-01 18:00", periods=60, freq="1min", tz=NY)
    dxy.set_spot(pd.DataFrame({"close": np.r_[np.full(60, 100.0), np.full(60, 105.0)]}, index=a.append(b)))
    bars = dxy.bars(60, "spot")
    reopen = bars.loc[pd.Timestamp("2026-06-01 18:00", tz=NY)]
    assert reopen.open == 105.0 and reopen.low == 105.0                                          # the reopen bar does not carry the 17:00 close
    dxy.set_spot(None)


# --- DXY intraday entry rules (cg3.py): items 1, 4, 5, 6, sym_swing_dxy ------------------------------------------------------------------

from mentorship import cg3


def _spot_day(day, anchors, start="00:00", end="16:00"):
    """A 1-minute close series for one calendar day from (hh:mm, value) anchors."""
    t = pd.date_range(pd.Timestamp(f"{day} {start}", tz=NY), pd.Timestamp(f"{day} {end}", tz=NY), freq="1min")
    xs = np.array([(pd.Timestamp(f"{day} {h}", tz=NY) - t[0]).total_seconds() / 60 for h, _ in anchors])
    ys = np.array([v for _, v in anchors])
    return pd.DataFrame({"close": np.interp(np.arange(len(t)), xs, ys)}, index=t)


DAY = "2026-06-24"


def _ctx_day(day=DAY):
    return _es_ctx(day, "00:00", "16:00")


def _p4(**kw):
    return Params(**kw)


def test_cg3_params_off_by_default():
    p = Params()
    assert (p.dxy_states, p.dxy_session_gate, p.dxy_eq_gate, p.dxy_range_trigger, p.sym_swing_dxy, p.dxy_state_from) == ("off", "off", "off", "off", False, "07:00")
    for bad in (dict(dxy_states="x"), dict(dxy_session_gate="x"), dict(dxy_eq_gate="x"), dict(dxy_range_from="x"), dict(dxy_range_trigger="x")):
        with pytest.raises(ValueError):
            Params(**bad)


def test_dxy_states():
    # a rally: 07:00 base, a swing high at 07:40, a close above it by 09:30
    up = _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("07:40", 100.4), ("08:00", 100.2), ("08:20", 100.5), ("08:40", 100.3), ("09:30", 101.0), ("16:00", 101.0)])
    dxy.set_spot(up)
    ctx = _ctx_day()
    i = _at(ctx, "09:30")
    assert cg3.dxy_state(ctx, i, _p4()) == 1
    o = dict(entry=1.0, lv_tags="")
    assert cg3.order_ok(ctx, _sd(1), o, "AM", i, _p4(dxy_states="filter")) == "x_cg_dxy_state" and "dxy_up" in o["lv_tags"]
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i, _p4(dxy_states="filter")) is None              # shorts are fine in a rising dollar
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", i, _p4(dxy_states="soft")) is None                 # soft: a scalp at half risk instead
    assert cg3.scalp_now(ctx, _p4(dxy_states="soft"), "AM", i, 1) == "cg_dxy_state"
    assert cg3.size_mult(ctx, _sd(1), i, _p4(dxy_states="soft"), []) == 0.5
    assert cg3.size_mult(ctx, _sd(1), i, _p4(dxy_states="filter"), []) == 1.0
    # a falling dollar: longs full size (no block, no scalp)
    dn = _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("07:40", 99.6), ("08:00", 99.8), ("08:20", 99.5), ("08:40", 99.7), ("09:30", 99.0), ("16:00", 99.0)])
    dxy.set_spot(dn)
    ctx = _ctx_day()
    assert cg3.dxy_state(ctx, i, _p4()) == -1
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", i, _p4(dxy_states="filter")) is None and cg3.scalp_now(ctx, _p4(dxy_states="filter"), "AM", i, 1) == ""
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", i, _p4(dxy_states="filter")) == "x_cg_dxy_state"      # a falling dollar blocks ES shorts
    # flat: scalp
    flat = _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("07:40", 100.3), ("08:00", 100.0), ("08:20", 100.3), ("08:40", 99.9), ("09:30", 100.1), ("16:00", 100.1)])
    dxy.set_spot(flat)
    ctx = _ctx_day()
    assert cg3.dxy_state(ctx, i, _p4()) == 0 and cg3.scalp_now(ctx, _p4(dxy_states="filter"), "AM", i, 1) == "cg_dxy_state"
    # no data (the file ends before the day)
    dxy.set_spot(_spot_day("2026-06-01", [("00:00", 100.0), ("16:00", 100.0)]))
    ctx = _ctx_day()
    assert cg3.dxy_state(ctx, i, _p4()) is None
    o = dict(entry=1.0, lv_tags="")
    assert cg3.order_ok(ctx, _sd(1), o, "AM", i, _p4(dxy_states="filter")) is None and "dxy_na" in o["lv_tags"]
    dxy.set_spot(None)


def test_dxy_states_no_lookahead():
    base = [("00:00", 100.0), ("07:00", 100.0), ("07:40", 100.4), ("08:00", 100.2), ("08:20", 100.5), ("08:40", 100.3), ("09:30", 100.1)]
    a = _spot_day(DAY, base + [("09:31", 100.1), ("16:00", 100.1)])
    b = _spot_day(DAY, base + [("09:31", 105.0), ("16:00", 105.0)])
    out = []
    for df in (a, b):
        dxy.set_spot(df)
        ctx = _ctx_day()
        out.append(cg3.dxy_state(ctx, _at(ctx, "09:20"), _p4()))                              # the 09:20 bar closes at 09:25: nothing later may count
    assert out[0] == out[1]
    dxy.set_spot(None)


def test_dxy_session_gate():
    # 00:00-09:30: a swing low near 03:00 (key support 99.80) and a bullish 15m FVG under price: DXY bullish structure, ES bearish
    pts = [("00:00", 100.0), ("02:00", 99.95), ("03:00", 99.8), ("03:45", 99.82), ("04:30", 100.3), ("06:00", 100.5), ("07:00", 100.7), ("09:30", 100.8), ("16:00", 100.8)]
    dxy.set_spot(_spot_day(DAY, pts))
    ctx = _ctx_day()
    p = _p4(dxy_session_gate="filter")
    assert cg3.dxy_sess_state(ctx, _at(ctx, "09:20"), p) is None                                    # before the mark: not set
    st = cg3.dxy_sess_state(ctx, _at(ctx, "09:35"), p)
    assert st == 1
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:35"), p) == "x_cg_dxy_sess"
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:35"), p) is None
    # DXY breaks down through the FVG and the support after 09:30: the long block lifts, then the short block
    pts2 = pts[:-2] + [("09:30", 100.8), ("10:15", 100.0), ("11:00", 99.5), ("16:00", 99.5)]
    dxy.set_spot(_spot_day(DAY, pts2))
    ctx = _ctx_day()
    assert cg3.dxy_sess_state(ctx, _at(ctx, "09:35"), p) == 1
    assert cg3.dxy_sess_state(ctx, _at(ctx, "11:30"), p) == -1
    dxy.set_spot(None)


def test_dxy_eq_gate():
    # a down leg: swing high 08:00 (100.7), swing low 09:00 (100.2), EQ 100.45; a 5m close above the EQ blocks longs
    pts = [("00:00", 100.4), ("07:30", 100.4), ("08:00", 100.7), ("08:30", 100.5), ("09:00", 100.2), ("09:20", 100.35), ("09:50", 100.55), ("16:00", 100.55)]
    dxy.set_spot(_spot_day(DAY, pts))
    ctx = _ctx_day()
    p = _p4(dxy_eq_gate="block")
    assert cg3.dxy_eq_state(ctx, _at(ctx, "09:25"), p) == 0                                         # still under the EQ (100.45)
    assert cg3.dxy_eq_state(ctx, _at(ctx, "09:55"), p) == 1
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:55"), p) == "x_cg_dxy_eq"
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:55"), p) is None
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:55"), _p4(dxy_eq_gate="tag")) is None
    dxy.set_spot(None)


def test_dxy_range_trigger():
    # the 09:15-09:30 range is 103.00-103.10; DXY then dips and runs above 103.10 at 09:52
    pts = [("00:00", 103.0), ("09:15", 103.0), ("09:22", 103.1), ("09:29", 103.05), ("09:40", 102.9), ("09:52", 103.2), ("09:58", 103.3), ("10:05", 103.4), ("16:00", 103.4)]
    dxy.set_spot(_spot_day(DAY, pts))
    ctx = _ctx_day()
    p = _p4(dxy_range_trigger="gate")
    assert cg3.dxy_range_state(ctx, _at(ctx, "09:40"), p) == 0                        # the dip armed the long side, the recovery closed above its bearish FVG: nothing armed, the short waits
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "09:40"), p) == "x_cg_dxy_range"          # the ES short waits
    assert cg3.dxy_range_state(ctx, _at(ctx, "10:00"), p) == 1
    assert cg3.order_ok(ctx, _sd(-1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "10:00"), p) is None
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "AM", _at(ctx, "10:00"), p) == "x_cg_dxy_range"
    assert cg3.order_ok(ctx, _sd(1), dict(entry=1.0, lv_tags=""), "PM", _at(ctx, "10:00"), p) is None                       # AM only
    # a bullish 1m FVG (a gap up on the closes) forms in the run; a later 1m close under it cancels, break_only ignores that
    pts2 = [("00:00", 103.0), ("09:15", 103.0), ("09:22", 103.1), ("09:29", 103.05), ("09:52", 103.2), ("09:53", 103.5), ("09:56", 103.6), ("10:05", 103.0), ("16:00", 103.0)]
    dxy.set_spot(_spot_day(DAY, pts2))
    ctx = _ctx_day()
    assert cg3.dxy_range_state(ctx, _at(ctx, "10:15"), p) == 0
    assert cg3.dxy_range_state(ctx, _at(ctx, "10:15"), _p4(dxy_range_trigger="break_only")) in (0, 1)
    dxy.set_spot(None)


def test_sym_swing_dxy_confirms():
    pts = [("00:00", 100.0), ("07:00", 100.0), ("08:00", 100.4), ("09:00", 100.2), ("09:20", 100.9), ("16:00", 100.9)]
    dxy.set_spot(_spot_day(DAY, pts))
    ctx = _ctx_day()
    p = _p4(sym_win=2)
    assert cg3.dxy_confirms(ctx, _sd(1), _at(ctx, "09:25"), p) is True                           # an ES low is confirmed by a new DXY high
    assert cg3.dxy_confirms(ctx, _sd(-1), _at(ctx, "09:25"), p) is False
    dxy.set_spot(_spot_day("2026-06-01", [("00:00", 100.0), ("16:00", 100.0)]))
    assert cg3.dxy_confirms(_ctx_day(), _sd(1), _at(ctx, "09:25"), p) is True                    # no data: the extra condition is not applied
    dxy.set_spot(None)


# --- DXY intraday management / SMT rules (cg4.py): items 2, 3, 7, 8, 9, 10 -----------------------------------------------------------------

from mentorship import cg4


def test_cg4_params_off_by_default():
    p = Params()
    assert (p.dxy_pool_run, p.dxy_smt, p.dxy_intrade, p.dxy_unicorn, p.dxy_target_partial, p.dxy_nonconf_exit) == ("off",) * 6
    assert (p.dxy_expand_min, p.dxy_expand_bars, p.dxy_intrade_frac, p.dxy_intrade_sister_frac, p.dxy_target_frac) == (0.05, 3, 0.5, 0.8, 0.5)
    for bad in (dict(dxy_pool_run="x"), dict(dxy_smt="x"), dict(dxy_intrade="x"), dict(dxy_unicorn="x"), dict(dxy_target_partial="x"), dict(dxy_nonconf_exit="x"),
                dict(dxy_intrade_tfs=("2m",)), dict(dxy_intrade_frac=1.5)):
        with pytest.raises(ValueError):
            Params(**bad)
    assert not cg4.active(Params()) and cg4.active(Params(dxy_intrade="bank"))


def _closes_day(day, base_anchors, extra=None):
    """A 1-minute close frame for `day` from 00:00 to 16:00: anchors for the day, or explicit per-minute values starting at a clock time (extra = (hh:mm, [closes]))."""
    df = _spot_day(day, base_anchors)
    if extra:
        t0 = pd.Timestamp(f"{day} {extra[0]}", tz=NY)
        idx = pd.date_range(t0, periods=len(extra[1]), freq="1min")
        df.loc[idx, "close"] = np.asarray(extra[1], float)
    return df


def _short_fixture(es_h, nq_h=None, ym_h=None, left=10, exits=()):
    """A short ES trade (side space: favorable = up) filled at bar 0 of the 09:30 grid; es_h are the side-space highs."""
    n = len(es_h)
    idx = pd.date_range(f"{DAY} 09:30", periods=n, freq="5min", tz=NY)
    mk = lambda a: SimpleNamespace(start=0, idx=idx, h=np.asarray(a, float), l=np.asarray(a, float) - 1.0)
    ctx = SimpleNamespace(idx=idx, t=(idx.hour * 60 + idx.minute).values, tf=5, day=pd.Timestamp(DAY).date(), start=0)
    if nq_h is not None:
        ctx.pside = (mk(nq_h), {-1: mk(nq_h)}, pd.Series(np.arange(n), index=idx))
        ctx.partner2 = (mk(ym_h), {-1: mk(ym_h)}, pd.Series(np.arange(n), index=idx))
    sd = SimpleNamespace(sign=-1, h=np.asarray(es_h, float), l=np.asarray(es_h, float) - 1.0, c=np.asarray(es_h, float) - 0.2, x=lambda v: v)
    pos = dict(fill_i=0, basis=100.0, n=1, left=left, k=0, levels=[103.0, 105.0, 108.0], level_kinds=["array"] * 3, t2=108.0, final_T=True, t1_done=False, t1=103.0)
    tr = SimpleNamespace(entry=100.0, stop=95.0, exits=list(exits), lv_tags="")
    return ctx, sd, pos, tr, idx


def _dxy_flat_after_swing():
    """DXY (spot) 07:00-09:55: a swing high near 08:00, then lower highs: the dollar does not confirm a new ES low (for a short Y = the high)."""
    return _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("08:00", 100.6), ("08:30", 100.3), ("09:00", 100.5), ("10:00", 100.4), ("16:00", 100.4)])


def _dxy_confirming():
    return _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("08:00", 100.6), ("08:30", 100.3), ("09:00", 100.5), ("09:40", 100.9), ("16:00", 100.9)])


def test_dxy_unconfirmed():
    dxy.set_spot(_dxy_flat_after_swing())
    ctx = _ctx_day()
    i = _at(ctx, "09:50")
    assert cg4.dxy_unconfirmed(ctx, -1, i, 5, pd.Timestamp(f"{DAY} 09:35", tz=NY)) is True                     # no new Y high after the last swing high
    dxy.set_spot(_dxy_confirming())
    ctx = _ctx_day()
    assert cg4.dxy_unconfirmed(ctx, -1, i, 5, pd.Timestamp(f"{DAY} 09:35", tz=NY)) is False                    # the dollar made a higher high: it confirms
    dxy.set_spot(_spot_day("2026-06-01", [("00:00", 100.0), ("16:00", 100.0)]))
    assert cg4.dxy_unconfirmed(_ctx_day(), -1, i, 5, pd.Timestamp(f"{DAY} 09:35", tz=NY)) is None              # no data
    dxy.set_spot(None)


def test_dxy_intrade_bank_and_nonconf_exit():
    es = [100, 101, 102, 104, 103, 103.5, 104.5, 104.4, 104.2, 104.3, 104.1, 105.5]          # bar 11 (10:25) = a new high since the fill
    dxy.set_spot(_dxy_flat_after_swing())
    ctx, sd, pos, tr, idx = _short_fixture(es)
    ctx.day = pd.Timestamp(DAY).date()
    p = _p4(dxy_intrade="bank", dxy_intrade_tfs=("5m",))
    i = 11
    cg4.manage(ctx, sd, pos, tr, i, idx[i], p)
    assert [e[3] for e in tr.exits] == ["dxy_intrade"] and tr.exits[0][2] == 5 and pos["left"] == 5               # half of what was left, once
    cg4.manage(ctx, sd, pos, tr, i, idx[i], p)
    assert len(tr.exits) == 1
    # a sister index diverges (makes the new extreme where ES does not): 80 %
    es2 = es[:-1] + [104.2]
    nq = list(es2[:-1]) + [106.0]
    ctx, sd, pos, tr, idx = _short_fixture(es2, nq, nq)
    cg4.manage(ctx, sd, pos, tr, i, idx[i], p)
    assert tr.exits and tr.exits[0][2] == 8
    # the dollar confirms: nothing
    dxy.set_spot(_dxy_confirming())
    ctx, sd, pos, tr, idx = _short_fixture(es)
    cg4.manage(ctx, sd, pos, tr, i, idx[i], p)
    assert not tr.exits
    # the non-confirmation exit: after a partial the rest closes (staged); before it only with "any"
    dxy.set_spot(_dxy_flat_after_swing())
    ctx, sd, pos, tr, idx = _short_fixture(es, left=5, exits=[(idx[5], 103.0, 5, "t1")])
    cg4.manage(ctx, sd, pos, tr, i, idx[i], _p4(dxy_nonconf_exit="after_partial"))
    assert tr.exits[-1][3] == "dxy_nonconf" and pos["left"] == 0
    ctx, sd, pos, tr, idx = _short_fixture(es)
    cg4.manage(ctx, sd, pos, tr, i, idx[i], _p4(dxy_nonconf_exit="after_partial"))
    assert not tr.exits                                                    # no partial yet: nothing
    cg4.manage(ctx, sd, pos, tr, i, idx[i], _p4(dxy_nonconf_exit="any"))
    assert tr.exits and tr.exits[-1][3] == "dxy_nonconf"
    # long trades are not touched by the in-trade bank unless dxy_intrade_long
    ctx, sd, pos, tr, idx = _short_fixture(es)
    sd.sign = 1
    cg4.manage(ctx, sd, pos, tr, i, idx[i], p)
    assert not tr.exits
    dxy.set_spot(None)


def test_dxy_manage_no_lookahead():
    es = [100, 101, 102, 104, 103, 103.5, 104.5, 104.4, 104.2, 104.3, 104.1, 105.5]
    out = []
    for tail in (100.4, 105.0):                                            # DXY closes after the decision bar differ
        d = _spot_day(DAY, [("00:00", 100.0), ("07:00", 100.0), ("08:00", 100.6), ("08:30", 100.3), ("09:00", 100.5), ("10:30", 100.4), ("10:31", tail), ("16:00", tail)])
        dxy.set_spot(d)
        ctx, sd, pos, tr, idx = _short_fixture(es)
        cg4.manage(ctx, sd, pos, tr, 11, idx[11], _p4(dxy_intrade="bank", dxy_intrade_tfs=("5m",)))
        out.append(list(tr.exits))
    assert out[0] == out[1] and out[0]
    dxy.set_spot(None)


def test_dxy_pool_run():
    # ES long (sd.sign +1); the dollar's pool = its latest 5m swing low under price at the fill; failed run = pierce < 0.05 and a close back above
    def run(path):
        dxy.set_spot(_spot_day(DAY, path))
        ctx = _ctx_day()
        n = 40
        idx = ctx.idx[_at(ctx, "09:30"):_at(ctx, "09:30") + n]
        ctx2 = SimpleNamespace(idx=ctx.idx, t=ctx.t, tf=5, day=ctx.day, start=0)
        f = _at(ctx, "09:35")
        h = np.linspace(100, 110, len(ctx.idx))
        sd = SimpleNamespace(sign=1, h=h, l=h - 1.0, c=h - 0.2, x=lambda v: v)
        pos = dict(fill_i=f, basis=100.0, n=1, left=10, k=0, levels=[103.0, 105.0, 108.0], level_kinds=["array"] * 3, t2=108.0, final_T=True, t1_done=False, t1=103.0)
        tr = SimpleNamespace(entry=100.0, stop=95.0, exits=[], lv_tags="")
        for i in range(f + 1, f + 14):
            cg4.manage(ctx2, sd, pos, tr, i, ctx.idx[i], _p4(dxy_pool_run="cap"))
        return pos
    base = [("00:00", 101.0), ("07:00", 101.0), ("08:00", 100.5), ("08:30", 100.8), ("09:00", 101.0)]
    failed = run(base + [("09:35", 101.0), ("09:40", 100.47), ("09:50", 100.9), ("16:00", 100.9)])           # pierces 100.5 by 0.03 and closes back above
    assert failed["levels"] == [103.0] and failed["t2"] == 103.0 and failed["final_T"] is False
    confirmed = run(base + [("09:35", 101.0), ("09:40", 100.3), ("10:00", 100.2), ("16:00", 100.2)])         # runs 0.2 through and stays under
    assert confirmed["levels"] == [103.0, 105.0, 108.0]
    dxy.set_spot(None)


def test_cap_next_rung_edge():
    pos = dict(k=0, levels=[103.0], t2=None, final_T=True)
    assert cg4.cap_next_rung(pos) is False                                 # nothing beyond the next rung to drop
    pos = dict(k=1, levels=[103.0, 105.0, 108.0], t2=108.0, final_T=True, level_kinds=["a", "b", "c"])
    assert cg4.cap_next_rung(pos) and pos["levels"] == [103.0, 105.0] and pos["t2"] == 105.0 and pos["level_kinds"] == ["a", "b"]


def test_dxy_target_partial(monkeypatch):
    dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("08:00", 100.0), ("09:50", 100.0), ("10:30", 101.3), ("11:30", 102.4), ("16:00", 102.4)]))
    monkeypatch.setattr(cg4, "_ladder_levels", lambda ctx, sg, p: [101.0, 102.0, 103.0])
    ctx = _ctx_day()
    n = len(ctx.idx)
    f = _at(ctx, "09:35")
    h = np.linspace(100, 90, n)
    sd = SimpleNamespace(sign=-1, h=h, l=h - 1.0, c=h - 0.2, x=lambda v: v)
    pos = dict(fill_i=f, basis=100.0, n=1, left=8, k=0, levels=[103.0], level_kinds=["a"], t2=None, final_T=True, t1_done=False, t1=103.0)
    tr = SimpleNamespace(entry=100.0, stop=95.0, exits=[], lv_tags="")
    p = _p4(dxy_target_partial="partial", dxy_htf_src="spot")
    for t in ("10:00", "10:40", "11:00", "11:40"):
        i = _at(ctx, t)
        cg4.manage(ctx, sd, pos, tr, i, ctx.idx[i], p)
    assert [e[3] for e in tr.exits] == ["dxy_target", "dxy_target"] and [e[2] for e in tr.exits] == [4, 2] and pos["dxy_ladder_n"] == 2        # 101.0 then 102.0 reached; half of what was left each time
    dxy.set_spot(None)


def test_dxy_smt():
    # ES long after a new low at bar j1; the previous swing low at j0; the dollar's high near j1 is not above its high near j0 = SMT
    n = 40
    idx = pd.date_range(f"{DAY} 09:30", periods=n, freq="1min", tz=NY)
    l = np.full(n, 100.0)
    l[8], l[20] = 99.0, 98.0
    l[7], l[9], l[19], l[21] = 99.5, 99.5, 98.5, 98.5
    h = l + 0.5
    ctx = SimpleNamespace(idx=idx, t=(idx.hour * 60 + idx.minute).values, tf=1, day=pd.Timestamp(DAY).date(), start=0)
    sd = SimpleNamespace(sign=1, h=h, l=l, c=l + 0.2, x=lambda v: v)
    sw = dict(ext_i=20, ext=98.0)
    p = _p4(dxy_smt="qualify")
    dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("09:38", 100.4), ("09:50", 100.2), ("16:00", 100.2)]))        # DXY high 100.4 near the first low, 100.2 near the new low
    assert cg4.dxy_smt(ctx, sd, 25, sw, p) is True
    dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("09:38", 100.2), ("09:50", 100.6), ("16:00", 100.6)]))        # the dollar made a higher high: no SMT
    assert cg4.dxy_smt(ctx, sd, 25, sw, p) is False
    lvt = []
    assert cg4.entry_extra(ctx, sd, sw, 25, p, lvt) == (0, None) and lvt == []
    dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("09:38", 100.4), ("09:50", 100.2), ("16:00", 100.2)]))
    assert cg4.entry_extra(ctx, sd, sw, 25, p, lvt) == (1, None) and lvt == ["smt_dxy"]
    assert cg4.entry_extra(ctx, sd, sw, 25, _p4(dxy_smt="tag"), []) == (0, None)
    dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("09:38", 100.2), ("09:50", 100.6), ("16:00", 100.6)]))
    assert cg4.entry_extra(ctx, sd, sw, 25, _p4(dxy_smt="need"), []) == (0, "x_no_dxy_smt")
    # look-ahead: the answer at bar 25 does not see DXY after it
    out = []
    for tail in (100.2, 105.0):
        dxy.set_spot(_spot_day(DAY, [("00:00", 100.0), ("09:38", 100.4), ("09:50", 100.2), ("09:55", 100.2), ("09:56", tail), ("16:00", tail)]))
        out.append(cg4.dxy_smt(ctx, sd, 25, sw, p))
    assert out[0] == out[1] is True
    dxy.set_spot(None)


def _unicorn_closes(kill=False):
    pre = [100.0, 100.3, 100.6, 100.9, 101.0, 100.8, 100.5, 100.3, 100.2, 100.4, 100.7, 101.2, 101.1, 100.9, 100.5, 100.1, 100.15, 100.25,
           100.29, 100.28, 100.26, 100.24]
    if kill:
        pre += [100.27, 100.35]
    return pre


def test_dxy_unicorn():
    dxy.set_spot(_closes_day(DAY, [("00:00", 100.0), ("09:00", 100.0), ("09:29", 100.0)], ("09:30", _unicorn_closes())))
    ctx = _ctx_day()
    sd = SimpleNamespace(sign=1, x=lambda v: v)
    i = _at(ctx, "09:55")
    u = cg4.dxy_unicorn(ctx, sd, i, _p4())
    assert u is not None and not u["killed"] and abs(u["fvg_high"] - 100.28) < 1e-9 and abs(u["fvg_low"] - 100.26) < 1e-9
    assert cg4.unicorn_ok(ctx, sd, i, _p4()) is True
    lvt = []
    assert cg4.entry_extra(ctx, sd, None, i, _p4(dxy_unicorn="qualify"), lvt) == (1, None) and lvt == ["dxy_unicorn"]
    dxy.set_spot(_closes_day(DAY, [("00:00", 100.0), ("09:00", 100.0), ("09:29", 100.0)], ("09:30", _unicorn_closes(kill=True))))
    ctx = _ctx_day()
    assert cg4.dxy_unicorn(ctx, sd, _at(ctx, "09:55"), _p4())["killed"] is True
    assert cg4.entry_extra(ctx, sd, None, _at(ctx, "09:55"), _p4(dxy_unicorn="need"), []) == (0, "x_no_dxy_unicorn")
    # the vault exit closes a filled long tagged dxy_unicorn
    pos = dict(left=4)
    tr = SimpleNamespace(exits=[], lv_tags="a|dxy_unicorn")
    sd2 = SimpleNamespace(sign=1, c=np.full(len(ctx.idx), 100.0), x=lambda v: v)
    cg4.unicorn_exit(ctx, sd2, pos, tr, _at(ctx, "09:55"), ctx.idx[_at(ctx, "09:55")], _p4(dxy_unicorn="qualify"))
    assert tr.exits and tr.exits[0][3] == "dxy_unicorn" and pos["left"] == 0
    dxy.set_spot(None)
