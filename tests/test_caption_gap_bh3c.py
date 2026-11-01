"""Caption-gap pass, package bias_htf#3/7: the full htf.table on synthetic 24-hour futures frames (every table-side switch, the unchanged default table, no look-ahead of the rows), per-path causal cases of
the engine hooks, the no-look-ahead runs (full vs truncated; hand-made days, synthetic windows and ES windows, the latter skip without the data) and the check that every new switch is set in at least
one executed run (third file of tests/test_caption_gap_bh3.py)."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh3 as BH3, bh3e as E3, bias_day as BD, cot, htf, strategy as S
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029 Q92: these tests exercise other rules; the order-block narrative gate (default on) leaves them no trades
    ob_need_narrative: bool = False

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, history, rth_day  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import BR, dsess, arr, flip_of  # noqa: E402
from test_caption_gap_bh1c import fut_walk, fut_frame  # noqa: E402
from test_caption_gap_bh1e import pad_to_0930  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks, _same  # noqa: E402
from test_caption_gap_bh3 import NEW_FIELDS, KNOBS, tue_book  # noqa: E402
from test_caption_gap_bh3b import put_cot, hist_closes, counter_hist, london_rows, CHOP_ROWS  # noqa: E402

@pytest.fixture(autouse=True)
def _no_cot_files(monkeypatch):
    """Hermetic: no CFTC files are read from data/mentorship/cot unless a test puts a table in the cache."""
    monkeypatch.setitem(cot._CACHE, ("E-MINI S&P 500", str(cot.COT_DIR)), None)


FL = ("ob_mt", "wk_dc", "flip_pd3", "tue_fail")
TABLE_A = dict(wpr_daily_tag=True, profile_gate=True, mwd_tf_test=True, mwd_cancel_case=True, mwd_upgrade=True, retire_arrays=True, pause_on_hold=True, mw_bookkeeping=True, pd60_only_consol=True,
               pd_day_range=20, day_pd="20d", in_play_gate=True, iof_mode="score", mo_bias_gate=True, q_dir_tag=True, wk_struct_weight=True, q_obj_lean=True, htf_bias="flip", flip_triggers=FL)
NEW_COLS_A = ("wpr_d", "profile", "profile_dir", "wm_zones", "held_arrays", "held_pause", "mo_pd", "wk_pd", "wk_expand", "in_play", "iof_ob_bounce", "iof_gap_fill_rally", "iof_premium_broken", "iof_sum",
              "mo_bias", "q_dir", "q_obj_dir", "wk_control", "pd60_consol", "mwd_levels", "mwd", "mwd_case")
NEW_COLS_B = ("wk_pre_bias", "wk_obj")
NEW_COLS_C = ("wk_chk_tail", "wk_consol", "d_head", "d_tail", "iof_w", "profile")


# --- the table on a synthetic futures frame ------------------------------------------------------------------------------------------------

def build(p, df):
    return htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))


def test_table_builds_every_new_column_and_the_default_table_is_unchanged():
    df = fut_walk("2025-03-03", "2026-03-27", seed=7, vol=0.9)
    pa = Params(**FUT, **TABLE_A)
    ta = build(pa, df)
    assert not [c for c in NEW_COLS_A if c not in ta.columns], [c for c in NEW_COLS_A if c not in ta.columns]
    assert len(ta) > 200 and set(ta.flip.unique()) <= {-1, 0, 1}
    for c in ("wpr_d", "in_play", "mo_bias", "q_dir", "wk_control", "iof_ob_bounce", "iof_gap_fill_rally", "iof_premium_broken"):
        assert ta[c].isin([-1, 0, 1]).all(), c
    assert set(ta.profile.unique()) <= {"", "consol", "trend", "retrace"} and ta.held_arrays.max() >= 1 and ta.held_pause.sum() >= 1
    assert ta.wpr_d.abs().sum() > 0 and ta.in_play.abs().sum() > 0 and ta.iof_sum.abs().max() >= 2 and set(ta.iof.unique()) <= {-1, 0, 1} and ta.pd60_consol.isin([0, 1]).all()
    assert ta.mo_pd.dropna().between(0, 1).all() and ta.wk_pd.dropna().between(0, 1).all() and (ta.wk_expand >= 0).all()
    assert all(isinstance(z, tuple) for z in ta.wm_zones) and all(isinstance(z, tuple) for z in ta.mwd_levels)
    pb = Params(**FUT, htf_bias="week_pre")
    tb = build(pb, df)
    assert not [c for c in NEW_COLS_B if c not in tb.columns] and set(tb.wk_pre_bias.unique()) <= {-1, 0, 1} and tb.wk_pre_bias.abs().sum() > 0
    mon = tb[[pd.Timestamp(x).weekday() == 0 for x in tb.index]]
    wk_key = pd.Series([str(pd.Timestamp(x).isocalendar()[:2]) for x in tb.index], index=tb.index)
    assert (tb.wk_pre_bias.groupby(wk_key).nunique() <= 1).all()      # held for the whole week
    pc = Params(**FUT, htf_bias="wd_check")
    tc = build(pc, df)
    assert not [c for c in NEW_COLS_C if c not in tc.columns] and len(mon) > 20
    assert (tc.wk_chk_tail[tc.wk_consol == 1] == 0).all() and set(tc.d_tail.unique()) <= {-1, 0, 1}
    # the default table has none of them and an empty configuration
    base = htf.table(df, 1.0, **B.table_kw(Params(**FUT)))
    assert not [c for c in NEW_COLS_A + NEW_COLS_B + NEW_COLS_C if c in base.columns]
    assert Params(**FUT).bx == ""
    # the switches that only add columns leave the base reading alone
    q = Params(**FUT, wpr_daily_tag=True, profile_gate=True, mw_bookkeeping=True, in_play_gate=True, mo_bias_gate=True, q_dir_tag=True, wk_struct_weight=True, htf_bias="combo")
    t2 = htf.table(df, 1.0, **B.table_kw(q))
    assert np.array_equal(base.px.values, t2.px.values) and np.array_equal(base.draw.values, t2.draw.values) and np.array_equal(base.react.values, t2.react.values)
    assert BH3.HITS


def test_retire_arrays_expires_a_weekly_gap_traded_through():
    """A weekly bull FVG that the daily wicks traded through to its far edge inside the current week is still a draw by the completed-week balance rule (balance_tf 'own'); retire_arrays expires it."""
    wk = [(4000, 4012, 3995, 4010), (4010, 4060, 4005, 4055), (4055, 4075, 4050, 4070)]               # a weekly bull FVG 4012-4050 (bar 1 high 4012 vs bar 3 low 4050)
    daily = []
    for o, h, l, c in wk:
        daily += [(o, h, l, c)] * 5
    daily += [(4070, 4072, 4065, 4068), (4068, 4069, 4005, 4060), (4060, 4064, 4056, 4062), (4062, 4066, 4058, 4063), (4063, 4067, 4059, 4064)]
    df = fut_frame(daily, start=date(2026, 1, 5))
    p0, p1 = Params(**FUT), Params(**FUT, retire_arrays=True)
    t0 = htf.table(df, 1.0, **B.table_kw(p0))
    t1 = htf.table(df, 1.0, **B.table_kw(p1))
    x = pd.Timestamp("2026-01-27").date()                                                               # the Tuesday: the overnight session already traded down through the gap (low 4005 under its bottom 4012)
    names0 = (t0.loc[x, "draw_dn_name"], t0.loc[x, "draw_up_name"])
    names1 = (t1.loc[x, "draw_dn_name"], t1.loc[x, "draw_up_name"])
    assert "W_fvg" in names0 and "W_fvg" not in names1
    assert np.array_equal(t0.react.values, t1.react.values)                                              # only the draw changes


def test_pd60_only_consol():
    n = 90
    rng = np.random.default_rng(3)
    rangebound = [(5000, 5006, 4994, 5000 + float(5 * np.sin(2 * np.pi * q / 59.0))) for q in range(n)]
    trending = [(5000 + 8 * q, 5006 + 8 * q, 4994 + 8 * q, 5000 + 8 * q + 4) for q in range(n)]
    pr = Params(**FUT, htf_bias="pd", day_pd="20d", pd_day_range=60, pd60_only_consol=True, consol_ratio=0.25, pd_body_multiday=True)
    t_rb = htf.table(fut_frame(rangebound, date(2025, 11, 3)), 1.0, **B.table_kw(pr))
    t_tr = htf.table(fut_frame(trending, date(2025, 11, 3)), 1.0, **B.table_kw(pr))
    assert t_rb.pd60_consol.iloc[-1] == 1                                                               # range-bound 60 sessions: True
    assert t_tr.pd60_consol.iloc[-1] == 0 and (t_tr.pd[t_tr.pd60_consol == 0] == 0).all()               # a 60-session trend: False, and the premium / discount reading is unused
    off = Params(**FUT, htf_bias="pd", day_pd="20d", pd_day_range=60)
    t_off = htf.table(fut_frame(trending, date(2025, 11, 3)), 1.0, **B.table_kw(off))
    assert "pd60_consol" not in t_off.columns and (t_off.pd != 0).any()


def test_tue_fail_in_the_table_and_wk_pre_for_the_whole_week():
    df = fut_frame([(o, h, l, c) for o, h, l, c in tue_book().itertuples(index=False, name=None)], date(2024, 1, 1))
    p = Params(**FUT, htf_bias="flip", flip_triggers=("ob_mt", "tue_fail"), eq_tol_pts=0.5)
    t = htf.table(df, 1.0, flip_triggers=p.flip_triggers, **B.table_kw(p))
    days = list(pd.bdate_range("2024-01-01", periods=40).date)
    tue, wed, fri, nxt = days[31], days[32], days[34], days[35]
    assert t.loc[tue, "flip"] == 0 and t.loc[wed, "flip"] == -1 and t.loc[fri, "flip"] == -1 and t.loc[nxt, "flip"] == 0      # the failure swing of Tuesday flips Wed-Fri; the state returns the next week
    plain = htf.table(df, 1.0, flip_triggers=("ob_mt",), **B.table_kw(Params(**FUT)))
    assert plain.loc[wed, "flip"] != -1


def test_table_rows_do_not_look_ahead():
    """Row of session k built from the frame cut just before 09:30 of session k equals the full table's row (every new column); earlier rows are the same too."""
    df = fut_walk("2025-06-02", "2026-03-27", seed=11, vol=0.9)
    cols_all = []
    for p, cols in ((Params(**FUT, **TABLE_A), NEW_COLS_A + ("flip", "draw", "pd")), (Params(**FUT, htf_bias="week_pre"), NEW_COLS_B), (Params(**FUT, htf_bias="week_check"), NEW_COLS_C)):
        kw = dict(vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
        full = htf.table(df, p.es_pt, **kw)
        cols = [c for c in cols if c in full.columns]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4, len(dates) // 3):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part = htf.table(df[df.index < cut], p.es_pt, **kw)
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])
        cols_all += cols
    assert len(cols_all) > 25


# --- per-path causal cases (the same function at the same closed bar on the day, on a day whose LATER bars are junk) ------------------------------

RNG = np.random.default_rng(5)
JUNK = [(float(x), float(x + 25), float(x - 25), float(x + RNG.normal() * 15)) for x in RNG.normal(100, 30, size=90)]
JUNK = [(o, max(h, o, c), min(l, o, c), c) for o, h, l, c in JUNK]
CAUSAL = {}


def causal(*switches):
    def deco(fn):
        CAUSAL[fn.__name__] = (switches, fn)
        return fn
    return deco


def cx(p, rows, bias=None, im=None, hist=None, d=date(2026, 3, 10), start="09:30"):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start)
    ctx.intermarket = im or {}
    return ctx


@causal("chop_lean", "chop_target_baseline")
def case_chop(poison, mp):
    p = Params(**BASE, htf_bias="combo", chop_lean=True, chop_target_baseline=True)
    rows = list(CHOP_ROWS) + (JUNK if poison else [(103.5, 104.0, 103.0, 103.5)] * 4)
    ctx = cx(p, rows, BR(), start="08:30")
    ctx.cur_sloppy = "chop"
    i = at(ctx, "09:15")                                                                          # the last real bar; everything after it is junk in the poisoned run
    sd = ctx.sides_map[-1]
    return (E3.chop_baseline(ctx, i), E3.side_ok(ctx, p, -1, "AM", i), E3.side_ok(ctx, p, 1, "AM", i), E3.scalp_now(ctx, p, "AM", i, -1),
            E3.targets_post(ctx, sd, i, p, sd.x(float(ctx.c[i])) - 20.0, [(sd.x(90.0), "pool")]))


@causal("ny_continue_london", "q_dir_tag")
def case_london(poison, mp):
    p = Params(**BASE, htf_bias="combo", ny_continue_london=True, q_obj_lean=True, q_dir_tag=True)
    rows = london_rows() + (JUNK if poison else [(100.0, 100.4, 99.6, 100.0)] * 4)
    ctx = cx(p, rows, BR(iof=-1), start="00:00")
    kl = S._idx_at(ctx, 570)
    lock = dict(side=0, target=None, kind="", name="", marked=[])
    a = E3.lock_post(ctx, p, BR(iof=-1), 570, "AM", kl, 100.0, dict(lock))
    b = E3.lock_post(ctx, p, BR(q_obj=float("nan"), q_obj_dir=112.0), 570, "AM", kl, 100.0, dict(lock))
    return [(x["side"], x["target"], x["name"]) for x in (a, b)]


@causal("counter_range_extreme")
def case_counter(poison, mp):
    from types import SimpleNamespace
    p = Params(**BASE, htf_bias="combo", counter_range_extreme=True, pd_body_multiday=False)
    rows = [(100.0, 100.2, 99.0, 99.2), (99.2, 99.3, 90.0, 90.5), (90.5, 90.6, 87.0, 87.6), (87.6, 88.4, 87.4, 88.0)] + (JUNK if poison else [(88.0, 88.2, 87.8, 88.0)] * 4)
    ctx = cx(p, rows, BR(), hist=counter_hist(date(2026, 3, 10)))
    ctx.conf = SimpleNamespace(opposing=lambda now, beyond, side, tfs, src: [(95.0, 0, 0, "D", 0)])
    i = at(ctx, "09:45")
    return (E3.counter_kind(ctx, ctx.sides_map[1], i, p, -1, "AM"), E3.ctr_target(ctx, ctx.sides_map[1], i, p))


@causal("stack_tag", "hallmarks_tag", "swing_gate_runners", "profile_gate", "bias_dh", "iof_premium_wait", "mwd_levels_entries")
def case_orders(poison, mp):
    up = hist_closes(date(2026, 3, 10), [100 + q for q in range(24)])
    p = Params(**BASE, htf_bias="combo", stack_tag=True, stack_min=1, hallmarks_tag=True, swing_gate_runners=True, profile_gate=True, bias_dh="tag", iof_premium_wait=True, mwd_upgrade=True, mwd_levels_entries=True)
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    row = BR(iof=1, draw_up=110.0, profile="retrace", profile_dir=1, wm_zones=((90.0, 120.0, 1),), px=95.0, pd20_lo=90.0, pd20_hi=110.0, mwd=1, mwd_levels=(99.0, 98.0), flip=1)
    ctx = cx(p, rows, row, im={"tr_tnx": 0.8, "tnx": -1, "dxy": -1}, hist=up)
    i = at(ctx, "09:40")
    o = dict(entry=100.0, t1=108.0, lv_tags="", levels=[108.0], ext=99.0)
    why = E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p)
    return (why, o["lv_tags"], E3.scalp_now(ctx, p, "AM", i, 1), E3.dcandle_rows(ctx, ctx.sides_map[1], i), E3.trend_ok(ctx, p))


@causal("htf_bias", "fall_low_bias", "iof_sponsor_gate", "pd_needs_iof", "pause_on_hold")
def case_composers(poison, mp):
    p = Params(**BASE, htf_bias="wd_check", fall_low_bias=True, iof_sponsor_gate="tag")
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    ctx = cx(p, rows, BR(wk_consol=0, wk_chk_tail=1, d_head=0, d_tail=0, iof=0), im={"dsmt": 0})
    i = at(ctx, "09:40")
    pp = Params(**BASE, htf_bias="pd", pd_needs_iof=True)
    return (BD.want_at(ctx, p, "AM", i), E3.side_ok(ctx, p, 1, "AM", i), BD.bias_value(BR(pd=1, iof=-1), pp), BD.bias_value(BR(flip=-1, held_pause=1), Params(**BASE, htf_bias="flip", pause_on_hold=True)))


@causal("cot_gate", "cot_two_states")
def case_cot(poison, mp):
    put_cot(mp, [-60000 if k % 2 else -10000 for k in range(59)] + [-20000])
    p = Params(**BASE, htf_bias="combo", cot_gate="hedge_iof", cot_two_states=True)
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    ctx = cx(p, rows, BR(iof=1))
    i = at(ctx, "09:40")
    o = dict(entry=100.0, t1=108.0, lv_tags="", levels=[108.0], ext=99.0)
    return (E3.side_ok(ctx, p, 1, "AM", i), E3.side_ok(ctx, p, -1, "AM", i), E3.order_ok(ctx, ctx.sides_map[1], o, "AM", i, p), o["lv_tags"])


@causal("season_qualified", "season_poised")
def case_season(poison, mp):
    from mentorship import dwc1
    p = Params(**BASE, htf_bias="combo", season_windows="tag", season_qualified=True, season_poised=True, season_gate=True)
    h = history(date(2026, 3, 10), n=60)
    out = []
    for im in ({"dsmt": 1, "poised": 1}, {"dsmt": 0, "poised": -1}, {"notes_dxy": "opposed", "poised": 1}):
        ctx = cx(p, [(100.0, 100.3, 99.8, 100.1)] * 3, BR(), im=im, hist=h)
        info = dwc1.season_info(ctx, date(2026, 3, 10), p, h, 10.0)
        out.append((info["prim"], info["wdir"], info["qualified"]))
    return out


@pytest.mark.parametrize("name", list(CAUSAL))
def test_bh3_paths_are_causal(name, monkeypatch):
    switches, case = CAUSAL[name]
    E3.HITS.clear()
    full = case(False, monkeypatch)
    poisoned = case(True, monkeypatch)
    assert full == poisoned, (name, full, poisoned)
    flat = full if isinstance(full, (list, tuple)) else [full]
    assert any(x for x in flat)                                                                 # a case that returns nothing proves nothing


# --- hand-made days cut right after a bar ----------------------------------------------------------------------------------------------------

def la_day3(p, bias=None, intermarket=None, hist=None, cuts=("09:55", "10:05", "10:30"), min_trades=1):
    df = day(A_ROWS, d=D0, start="09:50", spike=True)
    h = hist if hist is not None else history(D0)

    def run(frame_, live):
        return S.run_day(frame_, h, "ES", p, 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK, bias=bias, intermarket=intermarket, live=live)
    full = run(df, False)
    assert len(full) >= min_trades, "no trade - the hand-made day must produce one"
    cols = lambda tr: (str(tr.entry_time), round(tr.entry, 6), round(tr.stop, 6), tr.shares, tr.session, tr.lv_tags)
    for cut in cuts:
        c = pd.Timestamp(f"{D0} {cut}", tz="America/New_York")
        part = run(df[df.index <= c], True)
        assert [cols(t) for t in full if t.entry_time <= c] == [cols(t) for t in part if t.entry_time <= c], cut
        xa = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in full for e in t.exits if e[0] <= c]
        xb = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in part for e in t.exits if e[0] <= c]
        assert xa == xb, cut
    return full


def trending_hist(d=D0, n=24):
    """24 prior sessions with the A_ROWS hist range (108 / 90, so the draws are unchanged) and trending closes."""
    from mentorship import calendar as C
    out, x = [], pd.Timestamp(d)
    while len(out) < n:
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    return [rth_day(x, 108.0, 90.0, float(c)) for c, x in zip(np.linspace(96.0, 100.0, n), out[::-1])]          # ... ending at the usual 100 close


HAND = (
    dict(cot_two_states=True, cot_gate="hedge_iof", htf_bias="combo", bias_neutral="both", bias=BR(iof=1), cot=True),
    dict(tandem_scalp=True, notes_dxy_tag=True, bond_lt_tag=True, htf_bias="combo", bias_neutral="both", intermarket={"notes_dxy": "tandem", "bond_lt": 1}, bias=BR()),
    dict(stack_tag=True, stack_min=1, htf_bias="combo", bias_neutral="both", intermarket={"tnx": -1, "dxy": -1}, bias=BR(flip=1)),
    dict(swing_gate_runners=True, hallmarks_tag=True, htf_bias="combo", bias_neutral="both", intermarket={"tr_tnx": 0.1, "tr_dxy": 0.1}, hist=True, bias=BR(iof=1, draw_up=110.0)),
    dict(wpr_daily_tag=True, mw_bookkeeping=True, q_dir_tag=True, htf_bias="combo", bias_neutral="both", bias=BR(wpr_d=1, mo_pd=0.4, wk_pd=0.5, wk_expand=1, q_dir=1)),
    dict(profile_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(profile="consol", profile_dir=0)),
    dict(profile_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(profile="trend", profile_dir=1)),
    dict(profile_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(profile="retrace", profile_dir=1, wm_zones=((90.0, 101.0, 1),))),
    dict(in_play_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(in_play=1)),
    dict(bias_dh="tag", htf_bias="combo", bias_neutral="both", bias=BR(iof=1)),
    dict(iof_premium_wait=True, htf_bias="combo", bias_neutral="both", bias=BR(iof=1, px=95.0, pd20_lo=90.0, pd20_hi=110.0)),
    dict(mo_bias_gate=True, wk_struct_weight=True, htf_bias="combo", bias_neutral="both", bias=BR(mo_bias=1, wk_control=1, px=100.0)),
    dict(htf_bias="week_check", iof_sponsor_gate="tag", bias_neutral="both", bias=BR(wk_consol=0, wk_chk_tail=1, iof=1)),
    dict(htf_bias="wd_check", bias_neutral="both", bias=BR(wk_consol=0, wk_chk_tail=1, d_head=0, d_tail=0)),
    dict(htf_bias="week_pre", bias_neutral="both", bias=BR(wk_pre_bias=1)),
    dict(htf_bias="pd", pd_needs_iof=True, bias_neutral="both", bias=BR(pd=1, iof=1)),
    dict(htf_bias="flip", pause_on_hold=True, bias_neutral="both", bias=BR(flip=1, held_pause=0)),
    dict(htf_bias="combo", fall_low_bias=True, bias_neutral="both", intermarket={"fall_low": 1}, bias=BR(combo=0)),
    dict(htf_bias="combo", ny_continue_london=True, bias_neutral="both", bias=BR(iof=1)),
    dict(htf_bias="combo", chop_lean=True, bias_neutral="both", chop=95.0, bias=BR()),                                     # a chop day whose baseline lies under the price: longs only
    dict(htf_bias="combo", chop_target_baseline=True, bias_neutral="both", chop=101.5, bias=BR()),                         # ... a baseline above the entry: the long is the counter-move, a single-target scalp with the baseline rung
    dict(htf_bias="combo", season_windows="tag", season_qualified=True, season_poised=True, bias_neutral="both", intermarket={"dsmt": 1, "poised": -1}, bias=BR()),
)


def test_look_ahead_hand_made_days(monkeypatch):
    for kw in HAND:
        kw = dict(kw)
        bias, im = kw.pop("bias", None), kw.pop("intermarket", None)
        hist = trending_hist() if kw.pop("hist", False) else None
        with monkeypatch.context() as mp:
            if kw.pop("cot", False):
                put_cot(mp, [-60000 if k % 2 else -10000 for k in range(59)] + [-20000], last_report=date(2026, 6, 16))
            cb = kw.pop("chop", None)
            if cb is not None:
                mp.setattr(E3, "chop_day", lambda ctx: True)
                mp.setattr(E3, "chop_baseline", lambda ctx, i, cb=cb: cb)
            la_day3(Params(**BASE, **kw), bias=bias, intermarket=im, hist=hist, min_trades=1)


# --- the engine on synthetic and ES windows -------------------------------------------------------------------------------------------------------

def im3(i, d, v):
    return dict(v, rates_dxy_agree=1, spx20=1, tnx_slow=-1 if i % 3 else 1, notes_dxy="tandem" if i % 2 else "opposed", tr_tnx=0.8 if i % 4 else 0.1, tr_dxy=0.1, bond_lt=1, fall_low=1 if i % 5 == 0 else 0,
                poised=1 if i % 2 else -1)


IM3 = {d: im3(i, d, v) for i, (d, v) in enumerate(IM.items())}
LA_SETS = {   # name -> switches (the draw lock stays on: most of these act on it); each leaves trades on its windows
    "tags": dict(htf_bias="combo", bias_neutral="both", cot_two_states=True, tandem_scalp=True, notes_dxy_tag=True, stack_tag=True, bond_lt_tag=True, hallmarks_tag=True, swing_gate_runners=True, bias_dh="tag"),
    "composers": dict(htf_bias="wd_check", bias_neutral="both", dsmt_bias=True, iof_sponsor_gate="tag", season_windows="tag", season_qualified=True, season_poised=True),
    "lock": dict(htf_bias="combo", bias_neutral="both", ny_continue_london=True, iof_premium_wait=True, counter_range_extreme=True, fall_low_bias=True, q_obj_lean=True, q_dir_tag=True),
    "flip": dict(htf_bias="flip", bias_neutral="both", flip_triggers=FL, pause_on_hold=True, retire_arrays=True, mw_bookkeeping=True, wpr_daily_tag=True),
    "pd": dict(htf_bias="pd", day_pd="20d", bias_neutral="both", pd_needs_iof=True, pd60_only_consol=True, iof_mode="score", chop_lean=True, chop_target_baseline=True, sloppy_tests=("chop",), sloppy_mode="scalp"),
    "pre": dict(htf_bias="week_pre", bias_neutral="both", mwd_tf_test=True, mwd_cancel_case=True, mwd_upgrade=True, mwd_levels_entries=True, in_play_gate=True, wk_struct_weight=True, profile_gate=True, mo_bias_gate=True),
}


def _cot_ctx(mp):
    put_cot(mp, [-60000 if k % 2 else -10000 for k in range(59)] + [-20000], last_report=date(2026, 1, 27))


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh3(name, monkeypatch):
    x, y = _walks()
    p = Params(**LA, **LA_SETS[name])
    _cot_ctx(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM3)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM3, exits=True, min_trades=1)


def test_look_ahead_sets_fire_something(monkeypatch):
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run and executed-path counters ran."""
    E3.HITS.clear()
    x, y = _walks()
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    fired = {}
    _cot_ctx(monkeypatch)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, kw in LA_SETS.items():
            keep = {k: v for k, v in kw.items() if k in ("htf_bias", "bias_neutral", "flip_triggers", "sloppy_tests", "sloppy_mode", "day_pd", "season_windows", "dsmt_bias")}
            if keep.get("htf_bias") in ("wd_check", "week_pre"):
                keep["htf_bias"] = "combo"
            base = B.run(x, 5, "ES", Params(**LA, **keep), partner=y, intermarket=IM3)
            t = B.run(x, 5, "ES", Params(**LA, **kw), partner=y, intermarket=IM3)
            fired[name] = not (len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True))))
    assert all(fired.values()), fired
    assert E3.HITS


ES_WIN = {"tags": ("2022-09-12", "2022-10-07"), "composers": ("2022-09-12", "2022-10-07"), "lock": ("2022-09-12", "2022-10-07"), "flip": ("2022-09-12", "2022-10-07"),
          "pd": ("2023-03-06", "2023-03-31"), "pre": ("2023-03-06", "2023-03-31")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_es_bh3(name, monkeypatch):
    es = B.load("ES", 5, source="databento")
    a, b = ES_WIN[name]
    df = es[(es.index >= pd.Timestamp(a, tz=B.NY)) & (es.index < pd.Timestamp(b, tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**LA, **LA_SETS[name])
    put_cot(monkeypatch, [-60000 if k % 2 else -10000 for k in range(59)] + [-20000], last_report=pd.Timestamp(a).date())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta, intermarket=IM3))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 2), meta=meta, intermarket=IM3, exits=True, min_trades=1)


# --- every new switch is LIVE in an executed run ---------------------------------------------------------------------------------------------

ALIAS = {"cot_gate": "cot_gate", "cot_two_states": "cot_two_states"}


def test_every_switch_is_covered(monkeypatch):
    """Execution, not names: the code path of every new switch must have run with its input present (a `sw_<switch>` count in bh2.HITS, written by bh3.sw / bh3e.sw where the switch acts) in the runs below -
    the table builds with every table switch, the flip trigger on its hand-made book, the full-engine runs of the synthetic sets (each leaves >= 1 trade), the hand-made days (each trades), and the per-path
    causal cases. Coverage by name alone (a switch listed in a dict whose run never reached it) fails here."""
    E3.HITS.clear()
    df = fut_walk("2025-03-03", "2026-03-27", seed=7, vol=0.9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        build(Params(**FUT, **TABLE_A), df)
        build(Params(**FUT, htf_bias="week_pre"), df)
        build(Params(**FUT, htf_bias="wd_check"), df)
        flip_of(tue_book(), [], ("tue_fail",), {"tue_tol": 2.0})
        _cot_ctx(monkeypatch)
        x, y = _walks()
        for name, kw in LA_SETS.items():
            tr = B.run(x, 5, "ES", Params(**LA, **kw), partner=y, intermarket=IM3)
            assert len(tr) >= 1, name
        for kw in HAND:
            kw = dict(kw)
            bias, im = kw.pop("bias", None), kw.pop("intermarket", None)
            hist = trending_hist() if kw.pop("hist", False) else None
            with monkeypatch.context() as mp:
                if kw.pop("cot", False):
                    put_cot(mp, [-60000 if k % 2 else -10000 for k in range(59)] + [-20000], last_report=date(2026, 6, 16))
                cb = kw.pop("chop", None)
                if cb is not None:
                    mp.setattr(E3, "chop_day", lambda ctx: True)
                    mp.setattr(E3, "chop_baseline", lambda ctx, i, cb=cb: cb)
                la_day3(Params(**BASE, **kw), bias=bias, intermarket=im, hist=hist, min_trades=1)
    for sw_, case in CAUSAL.values():
        case(False, monkeypatch)
    live = {k[3:] for k in E3.HITS if k.startswith("sw_")}
    for hb in ("week_check", "wd_check", "week_pre"):
        if hb in live:
            live.add("htf_bias")
    missing = sorted((set(NEW_FIELDS) | set()) - set(KNOBS) - live - {"stack_min"} | ({"stack_min"} - live))
    assert not missing, f"never live in an executed run: {missing}"


# --- items 177 / 179 / 180: the glue in bias_htf._mwd (the sequential is forced so every branch runs on a short walk) ------------------------------------

def test_mwd_glue(monkeypatch):
    from mentorship import bias_htf as BX
    df = fut_walk("2025-09-01", "2026-03-27", seed=3, vol=0.9)

    def table(**kw):
        p = Params(**FUT, htf_bias="mwd", **kw)
        return build(p, df)
    monkeypatch.setattr(BX, "mwd_case", lambda *a: (1, "A"))
    base = table()
    assert set(base.mwd_case.unique()) == {"A"} and "mwd_levels" not in base.columns
    t_ok = table(mwd_tf_test=True)
    assert set(t_ok.mwd_case.unique()) <= {"A", "B"} and "B" in set(t_ok.mwd_case.unique())          # case A needs HH/HL and the iof of every timeframe in play: otherwise B
    monkeypatch.setattr(BH3, "hh_hl_series", lambda h, l: np.ones(len(h), int))
    monkeypatch.setattr(BH3, "iof_state_series", lambda o, h, l, c: np.ones(len(c), int))
    assert set(table(mwd_tf_test=True).mwd_case.unique()) == {"A"}                                      # with HH/HL and the iof agreeing everywhere case A stands
    monkeypatch.setattr(BX, "mwd_case", lambda *a: (1, "C"))
    monkeypatch.setattr(BH3, "breaker_cancel", lambda *a: True)
    t_c = table(mwd_cancel_case=True)
    assert (t_c.mwd == 0).all() and (t_c.mwd_case == "").all()                                          # the cancel sets mwd to 0 (no sequential), not -1
    monkeypatch.setattr(BX, "mwd_case", lambda *a: (1, "B"))
    assert (table(mwd_cancel_case=True).mwd == 0).all()
    monkeypatch.setattr(BH3, "breaker_cancel", lambda *a: False)
    assert (table(mwd_cancel_case=True).mwd == 1).all()
    monkeypatch.setattr(BX, "mwd_case", lambda *a: (1, "C"))
    monkeypatch.setattr(BH3, "case_c_to_b", lambda *a: True)
    t_u = table(mwd_upgrade=True)
    assert set(t_u.mwd_case.unique()) == {"B"} and all(isinstance(v, tuple) for v in t_u.mwd_levels) and sum(len(v) for v in t_u.mwd_levels) > 0       # case C -> B, the daily down-candle levels exported
    assert all(len(v) % 2 == 0 for v in t_u.mwd_levels)
    monkeypatch.setattr(BH3, "case_c_to_b", lambda *a: False)
    assert set(table(mwd_upgrade=True).mwd_case.unique()) == {"C"}
