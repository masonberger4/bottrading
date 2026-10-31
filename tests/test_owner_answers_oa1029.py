"""Owner answers 2026-10-29 (OA1029): the new defaults, the old value of each kept as a switch value
(study.OA1029_OLD, merged into PRE_OWNER / CURRENT) and one study variant per item."""
import json
import warnings

from mentorship import study
from mentorship.strategy import Params
from mentorship.study import OA1029_OLD

NEW = dict(bk_depth="any_open", bk_bpr_ce=True, ob_need_narrative=True, add_ladder="631", htf_gap_final="far_edge",
           hold_through_0830=True, objective_done_pm="reversal_only", tgif_window="off", pd3_result="neutral",
           org_with_bias=True, htf_monthly_series="raw", htf_bias_pools=True, release_ob_entry=True,
           tgif_exits="066", dagger_level="ltf", ifvg_stop="by_tf", lc_retry_until=720,
           htf_resist_tfs=("5m", "15m", "30m", "1h", "4h", "D"), cisd_ob_px="open",
           ifvg_targets_after="cisd", qshift_broken="leg",
           ifvg_sym_ym=True, dxy_filter="tag")


def test_new_defaults():
    p = Params()
    for k, v in NEW.items():
        assert getattr(p, k) == v, k
    assert not p.tgif and p.no_entry_0825 and not p.htf_gap_gate          # the parents the build list keeps as they were
    assert not p.nfp_release_fvg and not p.post_news_continuation         # N1 / N5a stay off (D2 / Q19: only N5b)


def test_old_values_are_switch_values_and_study_variants():
    assert set(OA1029_OLD) == set(NEW)
    for k, v in OA1029_OLD.items():
        assert v != NEW[k], k
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert getattr(Params(**{k: v}), k) == v, k                   # the old value is still accepted
        assert study.DECISIONS[f"OA1029_{k}_old"] == {k: v}
        assert study.PRE_OWNER[k] == v and study.CURRENT[k] == v, k


def test_plain_params_has_no_inert_warning_and_an_empty_table_config():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        p = Params()
    assert not [x for x in w if "inert" in str(x.message)]
    assert p.bx == ""
    # pd3_result="neutral" shapes the table only when the flip_pd3 trigger runs
    assert json.loads(Params(flip_triggers=("ob_mt", "flip_pd3")).bx)["b2"]["fl"] == {"pd3n": 1.5}


def test_q98_ifvg_stop_by_timeframe():
    from types import SimpleNamespace
    from mentorship import setups as SM
    g = SimpleNamespace(top=10.0, bottom=8.0)
    p = Params(es_pt=1.0)
    assert SM.ifvg_stop(None, g, 10.0, 7.5, p, tf=5)[1] == 8.0 - p.pad            # under 1h: beyond the whole IFVG
    assert SM.ifvg_stop(None, g, 10.0, 7.5, p, tf=1440)[1] == 9.0 - 3.0 - p.pad   # daily: CE + 3 pts
    assert SM.ifvg_stop(None, g, 10.0, 7.5, Params(es_pt=1.0, ifvg_stop_pts=2.0), tf=1440)[1] == 9.0 - 2.0 - p.pad
    assert SM.ifvg_stop(None, g, 10.0, 7.5, p, tf=60)[1] == 7.5                   # 1h-4h: CE as built (no pts set)
    assert SM.ifvg_stop(None, g, 10.0, 7.5, Params(es_pt=1.0, ifvg_stop="ce"), tf=5)[1] == 7.5     # the old value


def test_q23_london_close_retry_window():
    from types import SimpleNamespace
    from mentorship import strategy as S
    p = Params()
    live = SimpleNamespace(lc_retry=dict(session="AM"))
    assert S._lc_retry_end(live, p, 660) == 720                                    # the retry slot runs to 12:00
    assert S._lc_retry_end(SimpleNamespace(lc_retry=None), p, 660) == 660         # other AM setups keep am[1]
    assert S._lc_retry_end(SimpleNamespace(lc_retry=dict(session="PM")), p, 660) == 660
    assert S._lc_retry_end(live, Params(lc_retry_until=0), 660) == 660            # the old value


# --- no look-ahead: every new OA1029 code path, truncated runs agree with the full run (as test_caption_gap_sm2b._la) -----------------------
import numpy as np
import pytest

from test_caption_gap_sm2b import ENTRY, ES_NB, TAG_COLS, _check_ran, _es_tf, _la
from test_levels_detectors import ES

LA_CASES = {
    # Q90: the CISD open buy level with the discount check; Q71: IFVG targets after the real A12 CISD; Q98: the by-timeframe IFVG stop; D4: 5m speed bumps
    "cisd_open": (("2024-02-19", "2024-03-11"), 5, dict(cisd_ob_entries=True, ob_need_narrative=False), ("cisd_open",)),
    "ifvg": (("2023-10-02", "2023-10-23"), 5, dict(ifvg_entries=True, ifvg_targets=True, ob_entry="post_mss", ob_need_narrative=False), ("ifvg_targets_cisd",)),
    "bumps": (("2024-05-13", "2024-06-03"), 5, dict(htf_resist_cap=True, ob_need_narrative=False), ()),
}


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("case", sorted(LA_CASES))
def test_look_ahead_oa1029(case):
    (a, b), tf, kw, need = LA_CASES[case]
    df, meta = _es_tf(tf, a, b)
    p = Params(**{**ES_NB, **kw})
    full, added = _la(df, tf, "ES", p, ENTRY + ["draw_px"] + TAG_COLS, every=4, meta=meta)
    _check_ran(case, full, added, need)


def test_q236_qshift_leg_column_uses_only_past_sessions():
    from mentorship import bh2
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1.0, 400))
    h, l = c + rng.uniform(0.2, 1.5, 400), c - rng.uniform(0.2, 1.5, 400)
    full = bh2.qshift_columns(h, l, c, [], np.arange(len(c)), leg=True)
    key = next(k for k in full if np.asarray(full[k]).dtype.kind in "if")
    for cut in (150, 260, 399):
        part = bh2.qshift_columns(h[:cut + 1], l[:cut + 1], c[:cut + 1], [], np.arange(cut + 1), leg=True)
        assert np.array_equal(np.asarray(full[key])[:cut + 1], np.asarray(part[key]), equal_nan=True), (key, cut)


def test_q236_leg_reference_differs_from_literal():
    from mentorship import bh2
    rng = np.random.default_rng(7)
    c = 100 + np.cumsum(rng.normal(0, 1.0, 400))
    h, l = c + rng.uniform(0.2, 1.5, 400), c - rng.uniform(0.2, 1.5, 400)
    a = bh2.qshift_columns(h, l, c, [], np.arange(400), leg=True)
    b = bh2.qshift_columns(h, l, c, [], np.arange(400))
    assert any(not np.array_equal(np.asarray(a[k]), np.asarray(b[k])) for k in a if np.asarray(a[k]).dtype.kind in "if")   # the switch changes the column
