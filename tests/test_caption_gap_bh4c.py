"""Caption-gap pass, package bias_htf#4/7: the htf.table hooks on small synthetic futures frames (age tiers, weekly / monthly life, reach tolerance, event wicks, the new columns, the unchanged default
table, no look-ahead of the rows), per-path causal cases of the engine hooks, the no-look-ahead runs (full vs truncated; hand-made days, synthetic windows and ES windows, the latter skip without the
data) and the check that every new switch is set in at least one executed run (third file of tests/test_caption_gap_bh4.py)."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh4 as BH4, bh4e as E4, bias_day as BD, bias_htf as BX, htf, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, history, rth_day  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1c import fut_walk, fut_frame  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks, _same  # noqa: E402
from test_caption_gap_bh4 import NEW_FIELDS, KNOBS, build  # noqa: E402
from test_caption_gap_bh4b import _bars, _zigzag, _down_hist  # noqa: E402
from test_caption_gap_bh3b import cx as cx3, order  # noqa: E402

BASE_SESSION = (4000.0, 4002.0, 3997.0, 4000.0)
END = (4000.0, 4005.0, 3997.0, 3999.0)              # the last session closes down, so its overnight runs to the high first: the previous day's high is not an untaken pool then


def plan_frame(rows):
    return fut_frame(rows, start=date(2026, 1, 5), tf=5)


def last_row(p, rows):
    t = build(p, plan_frame(rows), min_gap_pts=50.0)                  # (no opening-gap draws: the synthetic sessions' tiny gaps would be nearer than anything)
    return t.iloc[-1], t


# --- item 29: the age tiers ------------------------------------------------------------------------------------------------------------

def _tier_plan():
    """A weekly bearish gap [4002, 4018] (weeks 1-3: 52 sessions old, unrebalanced - completed weekly bars never traded it) and a young DAILY bearish gap [4036, 4042] made by a spike inside the current week
    (age 2). The old weekly gap is nearer; the age tiers prefer the young one."""
    rows = [(4020.0, 4025.0, 4018.0, 4022.0)] * 5 + [(4005.0, 4015.0, 3990.0, 4000.0)] * 5 + [BASE_SESSION] * 55
    rows += [(4050.0, 4055.0, 4042.0, 4052.0), (4050.0, 4051.0, 3998.0, 4005.0), (4005.0, 4036.0, 4000.0, 4002.0), BASE_SESSION, END]
    return rows


def test_age_tiers_pick_the_younger_array_over_the_nearer_old_one():
    rows = _tier_plan()
    off, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo"), rows)
    on, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", array_age_tiers=True), rows)
    assert off.draw_up == pytest.approx(4002.0, abs=0.01) and off.draw_up_name == "W_fvg"          # the 52-session-old weekly gap is nearer
    assert on.draw_up == pytest.approx(4036.0, abs=0.01) and on.draw_up_name == "D_fvg"            # W20 first: the 2-session-old daily gap is the draw
    assert BH2.HITS["sw_array_age_tiers"] > 0


# --- items 113 / 184: the weekly / monthly life ----------------------------------------------------------------------------------------

def _weekly_plan(n_weeks=40):
    rows = [(4020.0, 4025.0, 4018.0, 4022.0)] * 5 + [(4005.0, 4015.0, 3990.0, 4000.0)] * 5 + [(4000.0, 4002.0, 3997.0, 4000.0)] * 5       # a weekly bearish gap [4002, 4018]
    return rows + [(4000.0, 4001.5, 3997.0, 4000.0)] * (5 * n_weeks - 1) + [END]


def test_weekly_array_lives_without_a_cap_when_asked():
    rows = _weekly_plan()
    off, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo"), rows)
    on, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", htf_lifetime_wm=0), rows)
    assert off.draw_up_name != "W_fvg"                                                         # 200 sessions old: past the 60-session look-back
    assert on.draw_up_name == "W_fvg" and on.draw_up >= 4002.0
    capped, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", htf_lifetime_wm=60), rows)
    assert capped.draw_up_name != "W_fvg"
    hist18, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", htf_history_months=18), rows)             # 18 x 21 = 378 sessions of life
    assert hist18.draw_up_name == "W_fvg"


# --- item 173: the reach tolerance ------------------------------------------------------------------------------------------------------

def test_reach_tolerance_counts_a_turn_short_of_the_level():
    rows = [(3980.0, 3990.0, 3975.0, 3985.0), (3985.0, 4030.0, 3984.0, 4025.0), (4025.0, 4040.0, 4000.0, 4035.0)] + [(4012.0, 4014.0, 4003.0, 4010.0)] * 20      # a bullish gap [3990, 4000]; the lows stay 3 above it
    off, _ = last_row(Params(**dict(FUT, es_pt=1.0), nwog_cfd_src="none", htf_bias="combo"), rows)
    on, _ = last_row(Params(**dict(FUT, es_pt=1.0), nwog_cfd_src="none", htf_bias="combo", htf_reach_tol_pts=4.0), rows)
    near, _ = last_row(Params(**dict(FUT, es_pt=1.0), nwog_cfd_src="none", htf_bias="combo", htf_reach_tol_pts=1.0), rows)
    assert on.react_score > off.react_score and near.react_score == off.react_score                # 3 points short counts at a tolerance of 4, not at 1


# --- item 139: the event wick -------------------------------------------------------------------------------------------------------------

def test_event_wick_is_not_a_swing_high():
    rows = [BASE_SESSION] * 29 + [END]
    rows[12] = (4000.0, 4100.0, 3997.0, 4001.0)
    off, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo"), rows)
    on, _ = last_row(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", event_wick_ignore=True), rows)
    assert off.draw_up == pytest.approx(4100.0) and off.draw_up_name == "D_swing_high"
    assert not (on.draw_up == on.draw_up and on.draw_up > 4050)                                    # without that wick there is no higher high


# --- the table with every table switch ---------------------------------------------------------------------------------------------------------

TABLE_A = dict(htf_bias="combo", range_day_mode="pm_only", ipda_mid_skip=True, htf_checklist=True, dbisi_lower_half=True, ce_line_bias=True, ifvg_bias=True, trapped_bpr_bias=True, program_tag=True,
               monthly_range=True, monthly_flow_gate=True, ob_ladder=True, matrix_tfs=("D", "W", "M"), htf_range_arrays=True, htf_eq_invalid=True, pd_grid=True, pd_range_break="two_close",
               failed_consol_break=True, nested_pd_bias=True, breaker_regime=True, htf_monthly_arrays=True, array_age_tiers=True, htf_lifetime_wm=0, event_wick_ignore=True, htf_ob_mitigation=True,
               origin_ob=True, htf_ob_to_mt=True, htf_reach_tol_pts=3.0, bias_cadence="weekly")
NEW_COLS = ("rng_day", "ipda60_hi", "ipda60_lo", "ipda_pos", "chk_q", "chk_react_up", "chk_react_dn", "chk_path_up", "chk_path_dn", "dz_dir", "dz_lo", "dz_hi", "dz_ce", "cel_kind", "cel_ce", "cel_top",
            "cel_bot", "ifvg_bias", "ifvg_top", "ifvg_bot", "trapped_bpr", "program", "mx_W_lo", "mx_W_hi", "mx_W_eq", "mx_W_prem", "mx_W_disc", "mx_M_eq", "m_rng_dir", "m_rng_lo", "m_rng_hi", "m_flow",
            "obl", "obl_dir", "htf_rng_lo", "htf_rng_hi", "htf_rng_dir", "htf_rng_eq", "eq_invalid", "grid_lo", "grid_hi", "grid_pos", "grid_k", "grid_q", "grid_half", "failed_break", "fb_target",
            "nested_bias", "brk_regime")


@pytest.fixture(scope="module")
def walk():
    return fut_walk("2024-09-02", "2026-03-27", seed=7, vol=0.9)


@pytest.fixture(scope="module")
def table_a(walk):
    BH2.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, **TABLE_A)
        return p, build(p, walk)


def test_table_builds_every_column(table_a):
    p, t = table_a
    assert not [c for c in NEW_COLS if c not in t.columns], [c for c in NEW_COLS if c not in t.columns]
    assert len(t) > 300
    for c in ("rng_day", "chk_react_up", "chk_react_dn", "eq_invalid", "grid_half"):
        assert t[c].isin([-1, 0, 1]).all(), c
    for c in ("chk_q", "dz_dir", "cel_kind", "ifvg_bias", "trapped_bpr", "program", "m_rng_dir", "m_flow", "obl_dir", "htf_rng_dir", "failed_break", "nested_bias", "brk_regime"):
        assert t[c].isin([-1, 0, 1]).all(), c
    assert (t.chk_path_up >= 0).all() and t.ipda_pos.dropna().between(0, 1).all() and t.grid_pos.dropna().between(0, 1).all() and t.grid_k.isin(range(-1, 8)).all()
    assert t.ifvg_bias.abs().sum() > 0 and t.brk_regime.abs().sum() > 0 and t.m_flow.abs().sum() > 0 and t.nested_bias.abs().sum() > 0 and t.program.abs().sum() > 0
    assert all(isinstance(v, tuple) for v in t.obl) and all(isinstance(v, tuple) for v in t.mx_W_prem) and t.obl.map(len).max() >= 1
    ok = t.dropna(subset=["mx_W_eq"])
    assert len(ok) > 100 and (ok.mx_W_lo < ok.mx_W_eq).all() and (ok.mx_W_eq < ok.mx_W_hi).all()
    assert all(all(x > e for x in pr) and all(x <= e for x in ds) for pr, ds, e in zip(ok.mx_W_prem, ok.mx_W_disc, ok.mx_W_eq))      # the arrays are split at the EQ
    g = t.dropna(subset=["grid_lo"])
    assert (g.grid_lo < g.grid_hi).all() and (g.ipda60_hi >= g.grid_hi - 1e-9).all()               # the body range sits inside the high-low range


def test_default_table_has_no_new_columns_and_is_unchanged_by_inert_switches(walk):
    p0 = Params(**FUT, nwog_cfd_src="none", htf_bias="combo")
    t0 = build(p0, walk)
    assert not [c for c in NEW_COLS if c in t0.columns] and "b4" not in BX.parse(p0.bx)
    p1 = Params(**FUT, nwog_cfd_src="none", htf_bias="combo", htf_checklist=True)                                      # a column switch changes no existing column
    t1 = build(p1, walk)
    base_cols = list(t0.columns)
    pd.testing.assert_frame_equal(t0[base_cols], t1[base_cols])


def test_cadence_freezes_the_weekly_columns_at_monday(walk):
    p = Params(**FUT, htf_bias="wk")
    q = Params(**FUT, htf_bias="wk", bias_cadence="weekly")
    t, f = build(p, walk), build(q, walk)
    wk = pd.Series([pd.Timestamp(x).to_period("W-FRI") for x in t.index], index=t.index)
    first = t.groupby(wk).wk_bias.transform("first")
    assert (f.wk_bias == first).all() and (t.wk_bias != first).any()                               # frozen at the first row of the week; the live column changes midweek
    assert (f.flip == t.flip).all() and (f.draw == t.draw).all()                                    # the daily columns are untouched
    assert BH2.HITS["sw_bias_cadence"] > 0


def test_htf_range_is_anchored_at_the_origin_body(table_a, walk):
    p, t = table_a
    d = htf.sessions(walk)
    w = htf.weeks(d)
    o, h, l, c = (w[k].values.astype(float) for k in ("open", "high", "low", "close"))
    pos = {x: k for k, x in enumerate(d.index)}
    wl = [pos[x] + 1 for x in w["last"]]
    origins = BH4.origin_arrays(o, h, l, c, "W", lambda i: wl[i])
    mo = htf.months(d)
    mlast = [pos[x] for x in mo["last"]]
    origins += BH4.origin_arrays(*(mo[k].values.astype(float) for k in ("open", "high", "low", "close")), "M", lambda i: mlast[i] + 1)
    r = t[t.htf_rng_dir == 1]
    assert len(r) > 5
    tops = {round(a.top, 6) for a in origins if a.kind == "bull"}
    assert all(round(v, 6) in tops for v in r.htf_rng_lo)                                          # the range low is the BODY top of a bullish origin block, never a wick
    assert (r.htf_rng_hi > r.htf_rng_lo).all()
    s = t[t.htf_rng_dir == -1]
    assert len(s) == 0 or (s.htf_rng_hi > s.htf_rng_lo).all()
    e = t[t.eq_invalid == 1]
    assert len(e) >= 1 and ((e.htf_rng_dir != 0)).all()


def test_monthly_columns_use_completed_months_only(table_a, walk):
    p, t = table_a
    d = htf.sessions(walk)
    mo, mh, ml, mc, mlast = BH4.BH3.tf_bars(d, "M")
    dates = list(t.index)
    k = len(dates) - 30
    day_ = pd.Timestamp(dates[k])
    n_done = int((d.index[mlast] < day_).sum())
    exp = BH4.monthly_range_at(mo, mh, ml, mc, n_done)
    row = t.iloc[k]
    assert (row.m_rng_dir, row.m_rng_lo, row.m_rng_hi) == exp or (exp[0] == 0 and row.m_rng_dir == 0)
    fl = BH4.monthly_flow_series(mo, mh, ml, mc)
    assert row.m_flow == (fl[n_done - 1] if n_done else 0)


def test_table_rows_do_not_look_ahead():
    """Row of session k built from the frame cut just before 09:30 of session k equals the full table's row (every new column); earlier rows are the same too."""
    df = fut_walk("2025-03-03", "2026-03-27", seed=11, vol=0.9)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p = Params(**FUT, **TABLE_A)
        full = build(p, df)
        cols = [c for c in NEW_COLS if c in full.columns] + ["draw", "draw_up", "draw_dn", "react_score", "pd", "flip"]
        dates = list(full.index)
        for pos in (len(dates) - 3, len(dates) // 2 + 4):
            d = dates[pos]
            cut = pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)
            part = build(p, df[df.index < cut])
            assert d in part.index
            for x in dates[:pos + 1]:
                a, b = full.loc[x, cols], part.loc[x, cols]
                bad = [c for c in cols if not _same(a[c], b[c]) and not (isinstance(a[c], tuple) and a[c] == b[c])]
                assert not bad, (str(x), bad, [(a[c], b[c]) for c in bad])


# --- per-path causal cases of the engine hooks --------------------------------------------------------------------------------------------

JUNK = [(500.0, 600.0, 400.0, 450.0)] * 12
CAUSAL = {}


def causal(*switches):
    def deco(fn):
        CAUSAL[fn.__name__] = (switches, fn)
        return fn
    return deco


def cx(p, rows, bias=None, im=None, hist=None, d=date(2026, 3, 10), start="09:30", **kw):
    ctx = mk(d, hist if hist is not None else history(d), p, rows=rows, bias_row=bias, start=start, **kw)
    ctx.intermarket = im or {}
    return ctx


def _p4(**kw):
    return Params(**BASE, htf_bias="combo", bias_neutral="both", **kw)


@causal("ce_line_bias")
def case_ce_line(poison, mp):
    p = _p4(ce_line_bias=True)
    rows = [(100.5, 101.5, 100.4, 101.2)] * 6 + (JUNK if poison else [(99.0, 99.1, 98.9, 99.0)] * 12)
    ctx = cx(p, rows, BR(cel_kind=1, cel_ce=100.0, cel_top=104.0, cel_bot=96.0))
    i = at(ctx, "09:55")                                                         # two complete 15m closes above the CE; everything after is junk in the poisoned run
    return (E4.cel_state(ctx, ctx.bias_row, i), E4.side_ok(ctx, p, 1, "AM", i), E4.side_ok(ctx, p, -1, "AM", i))


@causal("dbisi_lower_half")
def case_dbisi(poison, mp):
    p = _p4(dbisi_lower_half=True)
    hours = [(100.0, 102.0, 100.0, 101.5), (101.5, 104.0, 101.5, 103.8), (103.8, 105.0, 103.0, 104.5), (104.5, 104.6, 101.0, 101.5)]       # the lower-half gap [102, 103] then a fill
    rows = [h_ for h_ in hours for _ in range(12)] + (JUNK if poison else [(101.5, 101.6, 101.4, 101.5)] * 12)
    rows = rows[:48] + rows[48:]
    ctx = cx(p, rows, BR(dz_dir=1, dz_lo=100.0, dz_hi=110.0, dz_ce=105.0), start="00:00")
    i = at(ctx, "03:55")
    return (E4.dbisi_lower_filled(ctx, ctx.bias_row, 1, i), E4.side_ok(ctx, p, 1, "AM", i))


@causal("salient_pd")
def case_salient(poison, mp):
    p = _p4(salient_pd=(60,))
    pts = [100, 110, 95, 112, 93, 108, 96, 111, 94]
    rows = [r for r in _zigzag(pts) for _ in range(12)] + (JUNK if poison else [(94.0, 94.1, 93.9, 94.0)] * 12)
    ctx = cx(p, rows, BR(), start="00:00")
    i = at(ctx, "08:55")
    return (E4.salient_eq(ctx, 60, i), E4.order_ok(ctx, ctx.sides_map[1], order(entry=104.0), "AM", i, p), E4.order_ok(ctx, ctx.sides_map[1], order(entry=101.0), "AM", i, p))


@causal("ob_ladder", "swing_ignore_eq", "ifvg_edge_add", "htf_eq_invalid", "pd_need_array", "grade_confluence", "pd_grid", "swing_extreme_block", "htf_range_arrays", "monthly_range", "program_tag",
        "failed_consol_break", "matrix_tfs", "nested_pd_bias", "trapped_bpr_bias", "ifvg_bias", "monthly_flow_gate", "breaker_regime", "htf_checklist", "ipda_mid_skip", "range_day_mode",
        "dbisi_upper_and_discount")
def case_rows(poison, mp):
    p = _p4(ob_ladder=True, swing_ignore_eq=True, ifvg_edge_add=True, htf_eq_invalid=True, pd_grid=True, grade_confluence=True, swing_extreme_block=True, htf_range_arrays=True, monthly_range=True,
            program_tag=True, failed_consol_break=True, matrix_tfs=("D", "W"), nested_pd_bias=True, trapped_bpr_bias=True, ifvg_bias=True, monthly_flow_gate=True, breaker_regime=True,
            htf_checklist=True, ipda_mid_skip=True, range_day_mode="scalp", dbisi_upper_and_discount=True)
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    row = BR(obl=(104.0, 99.0), obl_dir=1, htf_rng_dir=1, htf_rng_lo=90.0, htf_rng_hi=130.0, ifvg_bias=1, ifvg_top=99.5, ifvg_bot=97.0, grid_lo=95.0, grid_hi=135.0, program=1, failed_break=-1,
             mx_W_eq=105.0, m_rng_dir=1, m_rng_lo=95.0, m_rng_hi=125.0, m_flow=1, brk_regime=1, chk_q=1, chk_react_up=1, chk_react_dn=0, chk_path_up=0, chk_path_dn=0, ipda_pos=0.2,
             rng_day=1, dz_dir=1, dz_ce=99.0, pd20_lo=90.0, pd20_hi=130.0, nested_bias=1, eq_invalid=0, combo=0)
    ctx = cx(p, rows, row, hist=_down_hist(date(2026, 3, 10)), lock={"AM": dict(side=1, target=110.0)})
    i = at(ctx, "09:40")
    sd = ctx.sides_map[1]
    o = order(entry=100.0)
    why = E4.order_ok(ctx, sd, o, "AM", i, p)
    pos = dict(fill_i=i - 2, stop=95.0)
    return (why, o["lv_tags"], E4.side_ok(ctx, p, 1, "AM", i), E4.scalp_now(ctx, p, "AM", i, 1), E4.ladder_rows(ctx, sd, i), E4.leg_pd_exempt(ctx, sd, 99.0, i, p), E4.ifvg_add_zone(ctx, sd, pos, i, p),
            BD.want_at(ctx, p, "AM", i), BD.want_at(cx(p, rows, dict(row, eq_invalid=1, combo=1), lock={"AM": dict(side=1, target=110.0)}), p, "AM", i))


@causal("pd_need_array")
def case_need_array(poison, mp):
    from test_caption_gap_dwc1 import Conf
    p = _p4(pd_need_array=True)
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    out = []
    for tfs in (("D",), ()):
        ctx = cx(p, rows, BR(grid_lo=95.0, grid_hi=135.0), conf=Conf(at_tfs=tfs))
        i = at(ctx, "09:40")
        out.append(E4.order_ok(ctx, ctx.sides_map[1], order(entry=100.0), "AM", i, p))
    return out


@pytest.mark.parametrize("name", list(CAUSAL))
def test_bh4_paths_are_causal(name, monkeypatch):
    switches, case = CAUSAL[name]
    E4.HITS.clear()
    full = case(False, monkeypatch)
    poisoned = case(True, monkeypatch)
    assert full == poisoned, (name, full, poisoned)
    flat = full if isinstance(full, (list, tuple)) else [full]
    assert any(x for x in flat)                                                                  # a case that returns nothing proves nothing


# --- hand-made days cut right after a bar ----------------------------------------------------------------------------------------------------

def la_day4(p, bias=None, intermarket=None, hist=None, cuts=("09:55", "10:05", "10:30"), min_trades=1, lock_rows=None):
    df = day(A_ROWS, d=D0, start="09:50", spike=True)
    h = hist if hist is not None else history(D0)

    def run(frame_, live):
        return S.run_day(frame_, h, "ES", p, 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK if lock_rows is None else lock_rows, bias=bias, intermarket=intermarket, live=live)
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


HAND = (
    dict(range_day_mode="scalp", bias=BR(rng_day=1)),
    dict(ipda_mid_skip=True, bias=BR(combo=1, ipda_pos=0.2)),
    dict(htf_checklist=True, bias=BR(chk_q=1, chk_react_up=1, chk_react_dn=0, chk_path_up=0, chk_path_dn=0)),
    dict(dbisi_upper_and_discount=True, bias=BR(dz_dir=1, dz_ce=99.0, pd20_lo=90.0, pd20_hi=130.0)),
    dict(ce_line_bias=True, bias=BR(cel_kind=-1, cel_ce=95.0, cel_top=100.0, cel_bot=90.0)),
    dict(monthly_flow_gate=True, breaker_regime=True, bias=BR(m_flow=1, brk_regime=1)),
    dict(swing_extreme_block=True, htf_range_arrays=True, bias=BR(htf_rng_lo=90.0, htf_rng_hi=130.0, htf_rng_dir=1)),
    dict(pd_grid=True, grade_confluence=True, program_tag=True, matrix_tfs=("D", "W"), monthly_range=True, failed_consol_break=True,
         bias=BR(grid_lo=95.0, grid_hi=135.0, program=1, mx_W_eq=105.0, m_rng_dir=1, m_rng_lo=95.0, m_rng_hi=125.0, failed_break=1)),
    dict(ifvg_bias=True, nested_pd_bias=True, trapped_bpr_bias=True, htf_eq_invalid=True, bias=BR(combo=0, ifvg_bias=1, nested_bias=1, trapped_bpr=1, eq_invalid=0, htf_rng_dir=1)),
    dict(htf_eq_invalid=True, bias=BR(combo=1, eq_invalid=1, htf_rng_dir=-1)),
)


def test_look_ahead_hand_made_days():
    for kw in HAND:
        kw = dict(kw)
        bias = kw.pop("bias")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            la_day4(Params(**BASE, htf_bias="combo", bias_neutral="both", **kw), bias=bias, min_trades=1)


# --- the engine on synthetic and ES windows --------------------------------------------------------------------------------------------------

LA_SETS = {   # name -> switches (the draw lock stays on); each leaves trades on its windows
    "gates": dict(htf_bias="combo", bias_neutral="both", range_day_mode="pm_only", ipda_mid_skip=True, htf_checklist=True, dbisi_lower_half=True, dbisi_upper_and_discount=True, ce_line_bias=True,
                  monthly_flow_gate=True, breaker_regime=True),
    "orders": dict(htf_bias="combo", bias_neutral="both", salient_pd=(60, 15), swing_extreme_block=True, htf_range_arrays=True, pd_grid=True, grade_confluence=True, pd_need_array=True, program_tag=True,
                   matrix_tfs=("D", "W", "M"), monthly_range=True, failed_consol_break=True),
    "bias": dict(htf_bias="combo", bias_neutral="both", trapped_bpr_bias=True, nested_pd_bias=True, ifvg_bias=True, ifvg_edge_add=True, htf_eq_invalid=True, ob_ladder=True, swing_ignore_eq=True,
                 htf_range_arrays=True, leg_pd=0.5),
    "table": dict(htf_bias="combo", bias_neutral="both", range_day_mode="scalp", array_age_tiers=True, bias_cadence="weekly_midweek", origin_ob=True, htf_ob_mitigation=True, htf_ob_to_mt=True,
                  htf_reach_tol_pts=3.0, event_wick_ignore=True, htf_lifetime_wm=0, pd_range_break="two_close", htf_monthly_arrays=True),
}


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh4(name):
    x, y = _walks()
    p = Params(**dict(LA, **LA_SETS[name]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM, exits=True, min_trades=1)


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run and executed-path counters ran."""
    E4.HITS.clear()
    x, y = _walks()
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    fired = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, kw in LA_SETS.items():
            keep = {k: v for k, v in kw.items() if k in ("htf_bias", "bias_neutral", "leg_pd")}
            base = B.run(x, 5, "ES", Params(**dict(LA, **keep)), partner=y, intermarket=IM)
            t = B.run(x, 5, "ES", Params(**dict(LA, **kw)), partner=y, intermarket=IM)
            fired[name] = not (len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True))))
    fired.pop("table")                                                        # (the table-time switches reshape single table columns: their effect is asserted on the table itself above; here they only ride along in the no-look-ahead run)
    assert all(fired.values()), fired
    assert E4.HITS


ES_WIN = {"gates": ("2022-09-12", "2022-10-07"), "orders": ("2022-09-12", "2022-10-07"), "bias": ("2023-03-06", "2023-03-31"), "table": ("2023-03-06", "2023-03-31")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_es_bh4(name):
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


# --- every new switch is LIVE in an executed run -----------------------------------------------------------------------------------------------

def test_every_switch_is_covered(monkeypatch, walk):
    """Execution, not names: the code path of every new switch must have run with its input present (a `sw_<switch>` count in bh2.HITS, written by bh4.sw / bh4e.sw where the switch acts) in the runs
    below - the table with every table switch, the full-engine runs of the synthetic sets (each leaves >= 1 trade), the hand-made days (each trades), and the per-path causal cases."""
    E4.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        build(Params(**FUT, **TABLE_A), walk)
        build(Params(**FUT, nwog_cfd_src="none", htf_bias="combo", htf_history_months=18, htf_monthly_arrays=True), walk)
        x, y = _walks()
        for name, kw in LA_SETS.items():
            tr = B.run(x, 5, "ES", Params(**dict(LA, **kw)), partner=y, intermarket=IM)
            assert len(tr) >= 1, name
        for kw in HAND:
            kw = dict(kw)
            bias = kw.pop("bias")
            la_day4(Params(**BASE, htf_bias="combo", bias_neutral="both", **kw), bias=bias, min_trades=1)
    for sw_, case in CAUSAL.values():
        case(False, monkeypatch)
    live = {k[3:] for k in E4.HITS if k.startswith("sw_")}
    missing = sorted(set(NEW_FIELDS) - set(KNOBS) - live)
    assert not missing, f"never live in an executed run: {missing}"
