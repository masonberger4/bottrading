"""Caption-gap pass, package bias_htf#1/7: the full htf.table on synthetic 24-hour futures frames (every table-side switch, the unchanged default table, no look-ahead of the rows, the joint weekly ITH
end to end) and the no-look-ahead runs of the engine (sixth file of tests/test_caption_gap_bh1.py). The ES windows skip without the data."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, bh1 as BH, bh1e as BE, bias_day as BD, htf, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, history  # noqa: E402
from test_entries_stops import _no_look_ahead  # noqa: E402
from test_caption_gap_dwc1 import mk, at, COLS, FUT, ES  # noqa: E402
from test_caption_gap_bh1 import NEW_FIELDS, KNOBS, BR  # noqa: E402
from test_caption_gap_bh1c import fut_walk, fut_frame  # noqa: E402

FLIPS = ("ob_mt", "wk_dc", "wk_bisi", "inv3", "ob_low_touch", "wk_rb", "d_breaker")
TABLE_SWITCHES = dict(drange_scalp=True, neutral_lean=True, wk_po3=True, run_extreme_lean=True, pwh_giveback_draw=True, ceiling_ladder=True, wk_high_in_gate=True, b7_mode="mt_trade", wick_ce_draw=True,
                      stack_far=True, draw_order="inefficiency_first", b9_persist=True, b7_fresh_break=True, wk_bisi_ce_neutral=True, htf_bias="ordered", vi_arrays=True, flip_triggers=FLIPS, nwog_bias="tag",
                      nwog_ref="previous", nwog_bias_basis="close", htf_monthly=True, no_htf_top_pick=True, org_consol_case=True)
NEW_COLS = ("drange_in", "drange", "drange_hi", "drange_lo", "ob_guard", "ob_guard_sh", "wk_high_in", "wk_low_in", "lean", "ceiling", "ladder_dn", "floor", "ladder_up", "wk_po3", "run_hi_draw",
            "run_lo_draw", "pwh_giveback", "pwh_cand", "draw_mid_lvl")


def _same(a, b):
    return (a == b) or (isinstance(a, float) and isinstance(b, float) and a != a and b != b)


# --- the table on a synthetic futures frame ------------------------------------------------------------------------------------------------

def test_table_builds_every_new_column_and_the_default_table_is_unchanged():
    df = fut_walk("2025-10-06", "2026-04-17", seed=7, vol=0.9)
    p = Params(**FUT, **TABLE_SWITCHES)
    tb = htf.table(df, p.es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
    assert not [c for c in NEW_COLS if c not in tb.columns], [c for c in NEW_COLS if c not in tb.columns]
    assert set(tb.flip.unique()) <= {-1, 0, 1} and len(tb) > 100
    assert tb.drange_in.isin([0, 1]).all() and tb.drange.isin([-1, 0, 1]).all() and tb.lean.isin([-1, 0, 1]).all() and tb.wk_po3.isin([-1, 0, 1]).all()
    assert tb.draw.isin([-1, 0, 1]).all()
    # the default table has none of them (and no b1 key in the configuration)
    base = htf.table(df, 1.0, **B.table_kw(Params(**FUT)))
    assert not [c for c in NEW_COLS if c in base.columns]
    assert Params(**FUT).bx == ""
    # the new flip triggers leave the old columns alone (ob_low_touch builds the B17.3 objective columns first, so the flip column is computed after them)
    q = Params(**FUT, flip_triggers=FLIPS)
    t2 = htf.table(df, 1.0, flip_triggers=q.flip_triggers, **B.table_kw(q))
    assert set(base.columns) <= set(t2.columns) and "obj_day" in t2.columns
    assert np.array_equal(base.px.values, t2.px.values) and np.array_equal(base.draw.values, t2.draw.values)
    old = htf.table(df, 1.0, flip_triggers=("ob_mt", "wk_dc"), **B.table_kw(Params(**FUT)))
    assert len(old) == len(t2) and (old.flip.values != t2.flip.values).any()                      # the new triggers moved the state somewhere on this walk
    assert BH.HITS


def test_table_rows_do_not_look_ahead():
    """Row of session k built from the frame cut just before 09:30 of session k equals the full table's row (every new column); earlier rows are the same too."""
    df = fut_walk("2025-10-06", "2026-03-27", seed=11, vol=0.9)
    p = Params(**FUT, **TABLE_SWITCHES)
    kw = dict(vi=p.vi_arrays, flip_triggers=p.flip_triggers, **B.table_kw(p))
    full = htf.table(df, p.es_pt, **kw)
    cols = list(NEW_COLS) + ["flip", "draw", "draw_ord", "draw_ord_lvl", "nwog_bias", "react", "pd"]
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


def test_wk_dc_joint_end_to_end():
    daily_a = [(4000, 4010, 3930, 3950)] * 1 + [(3950, 4000, 3940, 3990), (3990, 4080, 3985, 4075), (4110, 4120, 4040, 4100), (4100, 4105, 3900, 3910)]
    # five weeks of constant sessions: every day of a week repeats the same weekly-like shape
    def weekly_frame(weeks, scale=1.0):
        rows = []
        for o, h, l, c in weeks:
            rows += [(o, o, o, o), (o, h, o, o), (o, o, l, o), (o, o, o, o), (o, max(o, c), min(o, c), c)]
        rows.append((c, c + 1, c - 1, c))                                        # the Monday after the last week: its row shows the state the last close made
        return fut_frame(rows, start=date(2026, 1, 5))
    es = weekly_frame(daily_a)
    nq_dn = weekly_frame([(a * 3, b * 3, c * 3, d * 3) for a, b, c, d in daily_a])
    nq_up = weekly_frame([(a * 3, b * 3, c * 3, d * 3) for a, b, c, d in daily_a[:4]] + [(4100 * 3, 4110 * 3, 4090 * 3, 4105 * 3)])
    j_dn = BH.wk_joint_map(es, nq_dn)
    j_up = BH.wk_joint_map(es, nq_up)
    last = max(j_dn)
    assert j_dn[last] is True and j_up[last] is False                  # both indices closed the week under their last down-close week's low / only ES did
    # htf.table: the wk_dc -1 flip needs the flag
    p = Params(**FUT, htf_bias="flip", wk_dc_joint=True)
    on = htf.table(es, 1.0, flip_triggers=("wk_dc",), wk_joint=j_dn)
    off = htf.table(es, 1.0, flip_triggers=("wk_dc",), wk_joint=j_up)
    plain = htf.table(es, 1.0, flip_triggers=("wk_dc",))
    assert on.flip.iloc[-1] == plain.flip.iloc[-1] == -1 and off.flip.iloc[-1] != -1


# --- the engine: no look-ahead, full vs truncated -----------------------------------------------------------------------------------------

LA = dict(FUT, htf_resist_cap=False, leg_pd=0, min_draw_pts=0, use_bias=False)
LA_SETS = {   # name -> switches (the draw lock stays on: most of these act on it); each leaves trades on its windows
    "lock": dict(bisi60_draw=True, bpr_lean=True, raid_gap_guard=True, drange_scalp=True, inval_src="array", low_in_relock=True, fifty_rel=True, allow_counter_trend=True, draw_order="nearest_tb",
                 run_extreme_lean=True, pwh_giveback_draw=True, bisi60_hold="trade", ceiling_ladder=True, wk_po3=True, htf_monthly=True),
    "gates": dict(org_gap_filter=True, org_tell_seq=True, dxy_filter="soft", bellwether_tf=15, org_consol_case=True, drange_scalp=True),
    "flip": dict(htf_bias="flip", bias_neutral="both", flip_triggers=FLIPS + ("inv3_lit",), b9_persist=True, b7_fresh_break=True, wk_bisi_ce_neutral=True, b7_mode="mt_trade", wk_high_in_gate=True, no_htf_top_pick=True,
                 neutral_lean=True, nwog_bias="tag", nwog_ref="previous", nwog_bias_basis="close", objective_neutral="week"),
    "ordered": dict(htf_bias="ordered", bias_neutral="both", draw_lock_pick="ordered", wick_ce_draw=True, stack_far=True, iof_tf=60, draw_order="inefficiency_first"),
}
IM = {d.date(): {"dxy": (1 if k % 3 else -1), "tnx": 0} for k, d in enumerate(pd.bdate_range("2021-01-01", "2026-12-30"))}      # +1 / -1 prior-day dollar values (the real INTERMARKET file is not needed)
WIN = ("2026-02-02", "2026-03-06")


def _walks(seed=2):
    return (fut_walk(*WIN, seed=seed, vol=0.7), fut_walk(*WIN, seed=seed + 20, vol=0.7, price=17000.0))


@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_synthetic_bh1(name):
    x, y = _walks()
    p = Params(**LA, **LA_SETS[name])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(x, 5, "ES", p, partner=y, intermarket=IM)
    assert len(full) >= 1, f"{name}: the switches leave no trade in the synthetic window"
    _no_look_ahead(x, 5, "ES", p, COLS, every=max(1, len(full) // 2), partner=y, intermarket=IM, exits=True, min_trades=1)


def test_look_ahead_sets_fire_something():
    """The sets change the engine on their windows (not inert): the trades differ from the switches-off run and executed-path counters ran."""
    BE.HITS.clear()
    BH.HITS.clear()
    x, y = _walks()
    CMP = ["entry_time", "entry", "shares", "session", "lv_tags", "net", "stop"]
    fired = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, kw in LA_SETS.items():
            base = B.run(x, 5, "ES", Params(**LA, **{k: v for k, v in kw.items() if k in ("htf_bias", "draw_lock_pick", "bias_neutral")}), partner=y, intermarket=IM)
            t = B.run(x, 5, "ES", Params(**LA, **kw), partner=y, intermarket=IM)
            fired[name] = not (len(t) == len(base) and (not len(t) or t[CMP].reset_index(drop=True).equals(base[CMP].reset_index(drop=True))))
    assert all(fired.values()), fired
    assert BE.HITS and BH.HITS                                                        # (counters of the executed paths: lock hooks, flips)


# --- ES windows (skipped without the data) --------------------------------------------------------------------------------------------------

ES_WIN = {"lock": ("2022-09-12", "2022-10-07"), "gates": ("2022-09-12", "2022-10-07"), "flip": ("2022-09-12", "2022-10-07"), "ordered": ("2023-03-06", "2023-03-31")}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(LA_SETS))
def test_look_ahead_es_bh1(name):
    es = B.load("ES", 5, source="databento")
    a, b = ES_WIN[name]
    df = es[(es.index >= pd.Timestamp(a, tz=B.NY)) & (es.index < pd.Timestamp(b, tz=B.NY))]
    if not len(df):
        pytest.skip("the ES file does not cover the window")
    meta = B.load_meta("ES", 5)
    p = Params(**LA, **LA_SETS[name])
    BE.HITS.clear()
    BH.HITS.clear()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        n = len(B.run(df, 5, "ES", p, meta=meta, intermarket=IM))
    if n < 1:
        pytest.skip("no trades in the window with this data file")
    _no_look_ahead(df, 5, "ES", p, COLS, every=max(1, n // 2), meta=meta, intermarket=IM, exits=True, min_trades=1)
