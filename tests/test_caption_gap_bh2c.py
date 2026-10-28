"""Caption-gap pass, package bias_htf#2/7: the full htf.table on synthetic 24-hour futures frames (every table-side switch, the unchanged default table, no look-ahead of the rows), per-path causal
cases of the engine hooks, the no-look-ahead runs (full vs truncated; synthetic windows and ES windows, the latter skip without the data) and the check that every new switch is set in at least one
executed run (third file of tests/test_caption_gap_bh2.py)."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh2 as BH2, bh2e as B2, bias_day as BD, htf, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, history  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import BR  # noqa: E402
from test_caption_gap_bh1c import fut_walk  # noqa: E402
from test_caption_gap_bh1d import blocks  # noqa: E402
from test_caption_gap_bh1e import pad_to_0930, fake_mark, lk_of  # noqa: E402
from test_caption_gap_bh1f import LA, IM, _walks, _same  # noqa: E402
from test_caption_gap_bh2 import NEW_FIELDS, KNOBS  # noqa: E402

FL = ("ob_mt", "wk_dc", "flip_pd3")
NEW_COLS = ("q_days", "q_window", "shift_due", "last_break", "eq_near", "last_break_m", "eq_near_m", "qshift", "qs_form", "qs_scalp", "q_obj", "iof_w", "sibi_dir", "sibi_top", "sibi_bot", "wk_q75",
            "consol_prior", "raid_profile", "after_draw_d", "after_draw_w", "fast_draw", "fast_next", "eq20_body", "tier_regime", "tier_ith", "bias_m", "bias_w", "raid_side60", "ipda_pause", "pd3_n",
            "first_clue", "tug", "no_new_ground", "tug_spec", "rk_D_up", "rk_D_dn", "rk_W_up", "rk_W_dn", "rk_M_up", "rk_M_dn")
TABLE_SWITCHES = dict(q_days_tag=True, q_window_lo=5, q_window_hi=15, shift_due_tag=True, eq_tiebreak=True, qshift_bias=True, q_obj_lean=True, iof_weekly_weight=True, sibi_gate=True, wk_q75_confirm=True, consol_dir="prior_strongest",
                      raid_profile_bias=True, htf_after_draw="reverse", fast_draw_extend=True, objective_neutral="both", pd_two_level=True, tier_regime_gate=True, tug_required=True, htf_bias_tf="M",
                      raid_side_gate=True, ipda_extreme_pause=True, first_clue_neutral=True, pd3_result="neutral", pd3_first_caution=True, flip_terminus=True, flip_triggers=FL, htf_bias="flip",
                      ipda_draw_side=True, htf_bias_pools=True, tier_stl_mode="two_of_four", htf_rank_tf=True)


# --- the table on a synthetic futures frame ------------------------------------------------------------------------------------------------

def test_table_builds_every_new_column_and_the_default_table_is_unchanged():
    df = fut_walk("2025-03-03", "2026-03-27", seed=7, vol=0.9)
    p = Params(**FUT, **TABLE_SWITCHES)
    tb = htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
    assert not [c for c in NEW_COLS if c not in tb.columns], [c for c in NEW_COLS if c not in tb.columns]
    assert len(tb) > 200 and set(tb.flip.unique()) <= {-1, 0, 1}
    for c in ("qshift", "last_break", "eq_near", "sibi_dir", "wk_q75", "consol_prior", "raid_profile", "tier_regime", "bias_m", "bias_w", "raid_side60", "ipda_pause", "first_clue"):
        assert tb[c].isin([-1, 0, 1]).all(), c
    assert tb.q_days.min() >= -1 and set(tb.qs_form.unique()) <= {"", "consol", "retrace"}
    assert tb.q_window.sum() > 0 and tb.last_break.abs().sum() > 0 and (tb.pd3_n >= 0).all()           # the columns carry information on this walk
    base = htf.table(df, 1.0, **B.table_kw(Params(**FUT)))
    assert not [c for c in NEW_COLS if c in base.columns and c not in ("first_clue", "tug", "no_new_ground")]
    assert Params(**FUT).bx == ""
    # the new switches leave the base reading alone (no oneway array here)
    q = Params(**FUT, **{k: v for k, v in TABLE_SWITCHES.items() if k not in ("flip_terminus", "first_clue_neutral", "pd3_result", "flip_triggers", "htf_bias", "htf_bias_tf")})        # (the monthly arrays of htf_bias_tf "M" add their reaction weights)
    t2 = htf.table(df, 1.0, **B.table_kw(q))
    assert np.array_equal(base.px.values, t2.px.values) and np.array_equal(base.draw.values, t2.draw.values) and np.array_equal(base.react.values, t2.react.values)
    assert BH2.HITS
    # flip_terminus / pd3 neutral move only the flip column
    f0 = htf.table(df, 1.0, flip_triggers=FL, **B.table_kw(Params(**FUT)))
    f1 = htf.table(df, 1.0, flip_triggers=FL, **B.table_kw(Params(**FUT, flip_terminus=True, flip_triggers=FL)))
    assert (f0.flip.values != f1.flip.values).any() and np.array_equal(f0.draw.values, f1.draw.values)
    f2 = htf.table(df, 1.0, flip_triggers=FL, **B.table_kw(Params(**FUT, pd3_result="neutral", flip_triggers=FL)))
    assert len(f2) == len(f0)


def test_table_rows_do_not_look_ahead():
    """Row of session k built from the frame cut just before 09:30 of session k equals the full table's row (every new column); earlier rows are the same too."""
    df = fut_walk("2025-06-02", "2026-03-27", seed=11, vol=0.9)
    p = Params(**FUT, **TABLE_SWITCHES)
    kw = dict(vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
    full = htf.table(df, p.es_pt, **kw)
    cols = [c for c in list(NEW_COLS) + ["flip", "draw", "obj_day", "obj_week", "wk_draw_up"] if c in full.columns]
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


def test_oneway_arrays_do_not_look_ahead():
    df = fut_walk("2025-09-01", "2026-03-27", seed=5, vol=0.9)
    p = Params(**FUT, oneway_n=2)
    kw = B.table_kw(p)
    full = htf.table(df, 1.0, **kw)
    assert full.draw_up_name.eq("D_oneway").any() or full.draw_dn_name.eq("D_oneway").any()
    dates = list(full.index)
    for pos in (len(dates) - 2, len(dates) // 2):
        d = dates[pos]
        part = htf.table(df[df.index < pd.Timestamp(d, tz=B.NY) + pd.Timedelta(hours=9, minutes=30)], 1.0, **kw)
        for x in dates[:pos + 1]:
            for c in ("draw", "draw_up", "draw_dn", "draw_up_name", "react"):
                assert _same(full.loc[x, c], part.loc[x, c]), (str(x), c)


# --- per-path causal cases (the same function at the same closed bar on the day, on a day whose LATER bars are junk) ------------------------------

RNG = np.random.default_rng(5)
JUNK = [(float(x), float(x + 25), float(x - 25), float(x + RNG.normal() * 15)) for x in RNG.normal(100, 30, size=90)]


def _fix(r):
    o, h, l, c = r
    return (o, max(h, o, c), min(l, o, c), c)


JUNK = [_fix(r) for r in JUNK]
CAUSAL = {}


def causal(*switches):
    def deco(fn):
        CAUSAL[fn.__name__] = (switches, fn)
        return fn
    return deco


@causal("sibi_gate", "raid_side_gate", "ipda_extreme_pause", "consol_dir")
def case_gates(poison, mp):
    p = Params(**BASE, sibi_gate=True, raid_side_gate=True, ipda_extreme_pause=True, consol_dir="first_expansion")
    rows = [(107.0, 107.2, 106.8, 107.0)] * 3 + [(107.0, 111.5, 106.9, 111.2), (111.2, 112.5, 111.1, 112.0)] + (JUNK if poison else [(112.0, 112.5, 111.5, 112.0)] * 4)
    row = BR(sibi_dir=-1, sibi_top=110.0, sibi_bot=100.0, raid_side60=0, ipda_pause=0, drange_in=0, drange=1, drange_hi=110.0, drange_lo=100.0)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=row)
    i = at(ctx, "09:50")
    return (B2.side_ok(ctx, p, 1, "AM", i), B2.side_ok(ctx, p, -1, "AM", i), B2.scalp_now(ctx, p, "AM", i, 1), B2.sibi_state(ctx, p, row, i),
            B2.order_ok(ctx, ctx.sides_map[1], dict(entry=105.0, t1=108.0, lv_tags="", levels=[108.0]), "AM", i, p))


@causal("wick_ce_60m", "sibi15_ce_cancel")
def case_wick(poison, mp):
    p = Params(**BASE, wick_ce_60m=True, sibi15_ce_cancel=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    spec = [(100.0, 100.0, 100.0, 100.0)] * 9 + [(103.0, 104.3, 102.8, 104.2)]
    rows = blocks(spec, 12)[:119] + (JUNK if poison else [(104.2, 104.3, 103.0, 103.1)] * 3)
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    i = at(ctx, "09:50")
    r = B2.lock_bar(ctx, p, "AM", lk_of(-1, 90.0, marked), i, {"AM": False}, [])
    spec15 = [(100.0, 100.0, 100.0, 100.0)] * 36 + [(104.0, 104.2, 103.5, 103.6), (103.6, 103.7, 101.5, 101.8), (101.8, 102.0, 101.0, 101.6), (101.6, 103.0, 101.5, 102.5)]
    rows15 = blocks(spec15, 3)[:-1] + (JUNK if poison else [(102.5, 103.0, 102.4, 102.5)])
    c15 = mk(D0, history(D0), p, rows=rows15, start="00:00", bias_row=BR())
    r15 = B2.lock_bar(c15, p, "AM", lk_of(-1, 90.0, marked), at(c15, "09:50"), {"AM": False}, [])
    return (None if r is None else (r[0]["side"], r[1]), None if r15 is None else (r15[0]["side"], r15[1]), B2._wick60_cancel(ctx, p, lk_of(-1, 90.0, marked), i))


REV_ROWS = [(101.0, 102.0, 100.5, 101.5), (101.5, 102.0, 100.8, 101.0), (101.0, 101.2, 98.0, 98.5), (98.5, 100.5, 98.4, 100.0), (100.0, 102.5, 99.9, 102.0), (102.0, 104.0, 101.8, 103.5),
            (103.5, 103.6, 101.5, 102.0), (102.0, 102.5, 100.5, 101.0), (101.0, 101.3, 96.5, 97.0), (97.0, 98.5, 96.8, 98.0), (98.0, 99.5, 97.8, 99.0), (99.0, 105.0, 98.9, 104.8),
            (104.8, 105.0, 103.0, 104.0), (104.0, 104.5, 103.6, 104.2), (104.2, 104.8, 103.9, 104.6), (104.6, 105.0, 104.2, 104.9)]


@causal("allow_reversal_after_target")
def case_reversal(poison, mp):
    p = Params(**BASE, allow_reversal_after_target=True, pivot_n=2)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    rows = pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3, price=101.0) + REV_ROWS[:16] + (JUNK if poison else [(104.9, 105.0, 104.5, 104.8)] * 2)
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {}
    d8 = at(ctx, "09:30") + 8
    fake_mark(mp, marked, side=1, target=110.0)
    lk = lk_of(-1, 96.5, marked, delivered=True, delivered_i=d8)
    out = []
    for j in (13, 14, 15):
        r = B2.lock_bar(ctx, p, "AM", dict(lk), at(ctx, "09:30") + j, {"AM": True}, [], {})
        out.append(None if r is None else (r[0]["side"], r[0]["target"]))
    return out


@causal("soft_carry", "q_obj_lean", "tier_regime_gate", "ipda_draw_side")
def case_lock_post(poison, mp):
    from datetime import timedelta
    p = Params(**BASE, soft_carry=True, q_obj_lean=True, tier_regime_gate=True, ipda_draw_side=True)
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1), (95.0, "pool", "ipda20l", -1)]
    rows = pad_to_0930([(100.0, 100.1, 99.9, 100.0)] * 3) + (JUNK if poison else [(100.0, 100.5, 99.5, 100.2)] * 3)
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR(flip=1))
    ctx.prior_locks = [dict(day=D0 - timedelta(days=1), session="PM", side=1, target=110.0, kind="pool", name="pdh1", delivered=False, flip=1)]
    kl = S._idx_at(ctx, 570)
    a = B2.lock_post(ctx, p, BR(flip=1), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    b = B2.lock_post(ctx, p, BR(flip=1, tier_regime=-1, tier_ith=104.0), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    c = B2.lock_post(ctx, p, BR(flip=1, last_break=-1), 570, "AM", kl, 100.0, lk_of(1, 110.0, marked))
    d = B2.lock_post(ctx, p, BR(flip=1, q_obj=70.0), 570, "AM", kl, 100.0, lk_of(0, None, marked))
    return [(x["side"], x["target"], x.get("name")) for x in (a, b, c, d)]


@causal("range_no_bias", "iof_weekly_weight", "decoupled_scalp", "bias_neutral")
def case_order_rules(poison, mp):
    p = Params(**BASE, range_no_bias=True, iof_weekly_weight=True, decoupled_scalp=True)
    spec = [(100.0, 101.0, 99.0, 100.5), (100.5, 105.0, 100.0, 104.0), (104.0, 105.0, 101.0, 102.0), (102.0, 103.0, 100.0, 101.0), (101.0, 102.0, 95.0, 96.0), (96.0, 99.0, 95.5, 98.0),
            (98.0, 100.0, 97.0, 99.0), (99.0, 99.5, 98.0, 98.5), (98.5, 99.0, 98.0, 98.4)]
    rows = blocks(spec, 12)[:119] + (JUNK if poison else [(98.4, 98.6, 98.2, 98.4)] * 3)
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR(iof_w=1))
    ctx.intermarket = {"dxy": 1, "spx20": 1}
    i = at(ctx, "09:50")
    o = dict(entry=-101.0, t1=-96.0, lv_tags="", levels=[-96.0])
    why = B2.order_ok(ctx, ctx.sides_map[-1], o, "AM", i, p)
    lvt: list = []
    return (B2.swing60(ctx, i), why, o["lv_tags"], B2.scalp_now(ctx, p, "AM", i, -1), B2.scalp_cap(ctx, ctx.sides_map[-1], i, p, "bh2_range", -101.0, -96.0), B2.size_mult(ctx, ctx.sides_map[-1], i, p, lvt), lvt)


@causal("htf_bias_tf", "wk_q75_confirm", "qshift_bias", "dsmt_bias", "eq_tiebreak", "raid_profile_bias", "htf_after_draw", "fast_draw_extend")
def case_bias_readings(poison, mp):
    p = Params(**BASE, htf_bias="combo", htf_bias_tf="M", qshift_bias=True, dsmt_bias=True, eq_tiebreak=True, raid_profile_bias=True, wk_q75_confirm=True, htf_after_draw="reverse",
               fast_draw_extend=True, objective_neutral="both")
    rows = [(100.0, 100.3, 99.8, 100.1)] * 3 + (JUNK if poison else [(100.0, 100.3, 99.8, 100.1)] * 3)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(combo=0, bias_m=0, bias_w=0, qshift=-1, qs_form="retrace", eq_near=1, last_break=1, raid_profile=1))
    ctx.intermarket = {"dsmt": 1}
    i = at(ctx, "09:40")
    row2 = BR(combo=1, bias_m=1, wk_q75=1, obj_week=1, after_draw_w=-1, fast_draw=1)
    return (BD.want_at(ctx, p, "AM", i), BD.bias_value(row2, p), BD.bias_value(dict(row2, wk_q75=0), p), BD.bias_value(dict(row2, fast_draw=0), p))


@pytest.mark.parametrize("name", list(CAUSAL))
def test_bh2_paths_are_causal(name, monkeypatch):
    switches, case = CAUSAL[name]
    B2.HITS.clear()
    full = case(False, monkeypatch)
    poisoned = case(True, monkeypatch)
    assert full == poisoned, (name, full, poisoned)
    flat = full if isinstance(full, (list, tuple)) else [full]
    assert any(x for x in flat)                                                                 # a case that returns nothing proves nothing


# --- hand-made days cut right after a bar ----------------------------------------------------------------------------------------------------

def la_day(p, bias=None, intermarket=None, cuts=("09:55", "10:05", "10:30"), min_trades=1):
    df = day(A_ROWS, d=D0, start="09:50", spike=True)
    h = history(D0)

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


def _patch_inside(mp):
    """The hand-made day is an inside_bisi stand-aside day by fiat (as in test_inside_bisi_release): its zone top 99 is beaten by the flat overnight highs, so the release lifts the stand-aside."""
    mp.setattr(S, "sloppy_day", lambda hist, day_, p_, open_px=None: {"inside_bisi"})
    mp.setattr(B2, "inside_zone", lambda hist: (99.0, 90.0))


HAND = (
    dict(raid_side_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(raid_side60=1)),                  # buy stops taken over the last 60 sessions: no shorts - the hand-made long day still trades
    dict(ipda_extreme_pause=True, htf_bias="combo", bias_neutral="both", bias=BR(ipda_pause=-1)),
    dict(sibi_gate=True, htf_bias="combo", bias_neutral="both", bias=BR(sibi_dir=1, sibi_top=90.0, sibi_bot=80.0)),
    dict(pd_two_level=True, htf_bias="combo", bias_neutral="both", bias=BR(eq20_body=500.0)),
    dict(consol_dir="prior_strongest", htf_bias="combo", bias_neutral="both", bias=BR(drange_in=1, consol_prior=1, drange_hi=300.0, drange_lo=50.0)),
    dict(tier_regime_gate=True, tug_required=True, htf_bias="combo", bias_neutral="both", bias=BR(tier_regime=-1, tug_spec=-1, tier_ith=120.0)),
    dict(iof_weekly_weight=True, htf_bias="combo", bias_neutral="both", bias=BR(iof_w=-1)),
    dict(htf_bias="combo", bias_neutral="scalp_week", bias=BR(combo=0)),
    dict(decoupled_scalp=True, htf_bias="combo", bias_neutral="both", intermarket={"dxy": 1, "spx20": 1}, bias=BR()),
    dict(dxy_needs_rates=True, dxy_filter="soft", htf_bias="combo", bias_neutral="both", intermarket={"dxy": 1, "rates_dxy_agree": 1}, bias=BR()),
    dict(im_regime_tag=True, htf_bias="combo", bias_neutral="both", intermarket={"im_regime": "bwith_dwith"}, bias=BR()),
    dict(dsmt_bias=True, htf_bias="combo", intermarket={"dsmt": 1}, bias=BR(combo=0)),
    dict(htf_bias="combo", htf_bias_tf="W", bias=BR(combo=-1, bias_w=1)),
    dict(htf_bias="flip", wk_q75_confirm=True, bias=BR(flip=1, wk_q75=1)),
    dict(htf_bias="combo", htf_after_draw="reverse", objective_neutral="both", bias=BR(combo=-1, obj_day=1, after_draw_d=1)),
    dict(htf_bias="combo", fast_draw_extend=True, objective_neutral="week", bias=BR(combo=1, obj_week=1, fast_draw=1, fast_next=300.0)),
    dict(htf_bias="combo", qshift_bias=True, qshift_strong_consol=True, bias=BR(combo=0, qshift=1, qs_form="retrace", qs_scalp=0)),
    dict(htf_bias="combo", eq_tiebreak=True, bias=BR(combo=0, eq_near=1, last_break=1)),
    dict(htf_bias="combo", raid_profile_bias=True, bias=BR(combo=0, raid_profile=1)),
    dict(htf_bias="flip", pd3_first_caution=True, pd3_result="neutral", flip_triggers=FL, bias=BR(flip=1, pd3_n=1)),
    dict(htf_bias="combo", bias_neutral="both", q_days_tag=True, shift_due_tag=True, q_window_gate=True, bias=BR(q_window=1, shift_due=1)),
    dict(htf_bias="combo", bias_neutral="both", q_window_size=1.5, bias=BR(q_window=1)),
    dict(htf_bias="combo", bias_neutral="both", range_no_bias=True, bias=BR()),
    dict(htf_bias="combo", bias_neutral="both", oneway_n=3, htf_rank_tf=True, bias=BR(draw_up=106.0, draw_up_name="W_fvg")),
    dict(htf_bias="flip", flip_terminus=True, first_clue_neutral=True, bias=BR(flip=1)),
    dict(htf_bias="combo", bias_neutral="both", inside_bisi_release=True, sloppy_tests=("inside_bisi",), patch_inside=True, bias=BR(combo=0)),
    dict(htf_bias="combo", bias_neutral="both", q_obj_lean=True, ipda_draw_side=True, bias=BR(combo=0, q_obj=130.0, last_break=1)),
)


def test_look_ahead_hand_made_days(monkeypatch):
    for kw in HAND:
        kw = dict(kw)
        bias, im = kw.pop("bias", None), kw.pop("intermarket", None)
        with monkeypatch.context() as mp:
            if kw.pop("patch_inside", False):
                _patch_inside(mp)
            la_day(Params(**BASE, **kw), bias=bias, intermarket=im, min_trades=1)


# --- the engine on synthetic and ES windows -------------------------------------------------------------------------------------------------------

LA_SETS = {   # name -> switches (the draw lock stays on: most of these act on it); each leaves trades on its windows
    "lock_a": dict(htf_bias="combo", bias_neutral="both", soft_carry=True, q_obj_lean=True, qshift_bias=True, tier_regime_gate=True, ipda_draw_side=True, ipda_next=True,
                   htf_after_draw="reverse", objective_neutral="both", fast_draw_extend=True),
    "lock_b": dict(htf_bias="combo", bias_neutral="both", wick_ce_60m=True, allow_reversal_after_target=True, no_trade_after_win=True),
    "lock_c": dict(htf_bias="combo", bias_neutral="both", sibi15_ce_cancel=True),
    "gates": dict(htf_bias="combo", bias_neutral="both", sibi_gate=True, raid_side_gate=True, ipda_extreme_pause=True, consol_dir="prior_strongest", range_no_bias=True, pd_two_level=True,
                  eq_tiebreak=True, raid_profile_bias=True, oneway_n=3, htf_bias_tf="W"),
    "flip": dict(htf_bias="flip", bias_neutral="both", flip_triggers=FL, pd3_result="neutral", pd3_first_caution=True, flip_terminus=True, first_clue_neutral=True, wk_q75_confirm=True,
                 iof_weekly_weight=True, q_days_tag=True, shift_due_tag=True, qshift_strong_consol=True, tug_required=True, tier_regime_gate=True),
    "misc": dict(htf_bias="combo", bias_neutral="scalp_week", decoupled_scalp=True, dsmt_bias=True, q_window_gate=True, dxy_needs_rates=True, dxy_filter="soft", im_regime_tag=True,
                 inside_bisi_release=True, sloppy_tests=("inside_bisi",), htf_rank_tf=True, consol_dir="first_expansion", htf_bias_tf="M"),
}
IM2 = {d: dict(v, rates_dxy_agree=1, spx20=1, im_regime="bwith_dwith") for d, v in IM.items()}


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh2(name):
    x, y = _walks()
    p = Params(**LA, **LA_SETS[name])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM2)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM2, exits=True, min_trades=1)


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run and executed-path counters ran."""
    B2.HITS.clear()
    BH2.HITS.clear()
    x, y = _walks()
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    fired = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, kw in LA_SETS.items():
            keep = {k: v for k, v in kw.items() if k in ("htf_bias", "bias_neutral", "flip_triggers", "sloppy_tests", "dxy_filter", "no_trade_after_win", "ipda_next", "objective_neutral")}
            base = B.run(x, 5, "ES", Params(**LA, **keep), partner=y, intermarket=IM2)
            t = B.run(x, 5, "ES", Params(**LA, **kw), partner=y, intermarket=IM2)
            fired[name] = not (len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True))))
    assert all(fired.values()), fired
    assert B2.HITS and BH2.HITS


ES_WIN = {"lock_a": ("2022-09-12", "2022-10-07"), "lock_b": ("2022-09-12", "2022-10-07"), "lock_c": ("2022-09-12", "2022-10-07"), "gates": ("2022-09-12", "2022-10-07"),
          "flip": ("2022-09-12", "2022-10-07"), "misc": ("2023-03-06", "2023-03-31")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_es_bh2(name):
    es = B.load("ES", 5, source="databento")
    a, b = ES_WIN[name]
    df = es[(es.index >= pd.Timestamp(a, tz=B.NY)) & (es.index < pd.Timestamp(b, tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**LA, **LA_SETS[name])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta, intermarket=IM2))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 2), meta=meta, intermarket=IM2, exits=True, min_trades=1)


# --- every new switch is LIVE in an executed run ---------------------------------------------------------------------------------------------

def test_every_switch_is_covered(monkeypatch):
    """Execution, not names: the code path of every new switch must have run with its input present (a `sw_<switch>` count in bh2.HITS, written by bh2.sw / bh2e.sw where the switch acts) in
    the runs below - the full-engine runs of the synthetic sets (each leaves >= 1 trade), the hand-made days (each trades, min_trades=1), the per-path causal cases and the table build with
    every table switch. Coverage by name alone (a switch listed in a dict whose run never reached it) fails here."""
    B2.HITS.clear()
    BH2.HITS.clear()
    covered = set(TABLE_SWITCHES) | set()
    df = fut_walk("2025-03-03", "2026-03-27", seed=7, vol=0.9)
    p = Params(**FUT, **TABLE_SWITCHES)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
        htf.table(df, 1.0, **B.table_kw(Params(**FUT, oneway_n=2)))
        x, y = _walks()
        for name, kw in LA_SETS.items():
            tr = B.run(x, 5, "ES", Params(**LA, **kw), partner=y, intermarket=IM2)
            assert len(tr) >= 1, name                                                           # an executed run: it trades
        for kw in HAND:
            kw = dict(kw)
            bias, im = kw.pop("bias", None), kw.pop("intermarket", None)
            with monkeypatch.context() as mp:
                if kw.pop("patch_inside", False):
                    _patch_inside(mp)
                la_day(Params(**BASE, **kw), bias=bias, intermarket=im, min_trades=1)
    for sw_, case in CAUSAL.values():
        case(False, monkeypatch)
    live = {k[3:] for k in B2.HITS if k.startswith("sw_")}
    live.add("bias_neutral" if "scalp_week" in live else "")
    missing = sorted((set(NEW_FIELDS) | {"bias_neutral"}) - set(KNOBS) - live)
    assert not missing, f"never live in an executed run: {missing}"
