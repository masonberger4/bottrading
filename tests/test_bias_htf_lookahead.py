"""Package bias_htf: no look-ahead for EVERY new switch. Full run vs runs truncated just after entries must give identical
entries (tags included).

  5m   one study.DECISIONS variant per run (so each switch alone changes the trades it can change), main engine, on a short
       window (a wider / longer one as the fallback for the selective switches and the long-history columns)
  1m   the switches grouped into compatible sets with the Silver Bullet, Ma Deuce and the 07:00 / 09:00 pre-open models on, so
       every shared hook (daycontext.side_ok / gate / order_ok / scalp_now) is also exercised in those engines

The columns themselves (htf.table, all of them, cut at 09:30 and 13:30) are covered in test_bias_htf.py."""
import warnings
from pathlib import Path

import pytest

from mentorship import backtest as B, study
from mentorship.strategy import Params

from test_entries_stops import _no_look_ahead  # noqa: F401,E402  (shared helper; used through _check)

ES5 = Path("data/mentorship/ES_5min_db.csv").exists()
ES1 = Path("data/mentorship/ES_1min_db.csv").exists()

WIN = {
    "def": [("2024-01-22", "2024-02-16"), ("2023-11-27", "2023-12-15")],
    "wide": [("2023-09-05", "2023-11-10")],
    "long": [("2023-06-01", "2024-01-31")],            # wpr (14 weeks), the monthly MWD state, the quarterly shift
    "rare": [("2024-08-19", "2024-09-13"), ("2024-02-26", "2024-03-25")],      # B9 objective_neutral='both' after the caption-gap levels pass: 0 trades in
}                                                      # the other windows, 2 in the first (2024-08-26 / 09-09); T13 require_judas_news (a Judas sweep within 30 minutes
                                                       # of a scheduled release AND a full setup): 1 trade in the second, none in the common windows
RARE = ("B9_objective_neutral", "T13-judas-news-driver_require")
LONG_HISTORY = ("wpr", "qshift", "mwd", "B22", "B20.3", "B10")
LA_COLS = ["entry_time", "entry", "stop", "t1", "side", "day_tags", "dw_tags"]


def _variants():
    names = list(study.DECISIONS)
    return [n for n in names[names.index("X16_journal_tags_off") + 1:] if n not in study.SB_VARIANTS]   # (merge: the SB variants are tested in test_silver_bullet.py)


def _params(name, **extra):
    kw = dict(study.DECISIONS[name])
    kw.update(extra)
    return Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, **kw)


_CACHE = {}


def _bars(tf, a, b):
    """The window's bars. The raw frame is loaded once per process, every window is sliced out and the raw frame is dropped again
    (the 1m ES file is ~2.7M rows: several xdist workers holding it exhaust the memory)."""
    if tf not in _CACHE:
        raw = B.load("ES", tf, source="databento")
        wins = {(x, y) for v in WIN.values() for (x, y) in v} | {("2024-01-22", "2024-02-02")}
        _CACHE[tf] = {(x, y): raw[(raw.index >= x) & (raw.index < y)].copy() for (x, y) in wins}
        del raw
    return _CACHE[tf][(a, b)]


def _check(name, tf, windows, p, need=None, max_cuts=3):
    fallback = None
    for a, b in windows:
        df = _bars(tf, a, b)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            full = B.run(df, tf, "ES", p)
        if not len(full):
            continue
        if need is None or full.apply(need, axis=1).any():
            fallback = (df, full)
            break
        fallback = fallback or (df, full)
    if fallback is None:
        pytest.fail(f"{name}: no window gave a trade ({windows})")
    df, full = fallback
    every = max(1, len(full) // max_cuts)
    _no_look_ahead(df, tf, "ES", p, LA_COLS, every=every, min_trades=1, lag=1 if tf == 1 else 2)
    return len(full)


@pytest.mark.skipif(not ES5, reason="ES 5m data missing")
@pytest.mark.parametrize("name", _variants())
def test_no_look_ahead_each_variant_5m(name):
    wins = (WIN["long"] if any(k in name for k in LONG_HISTORY) else []) + WIN["def"] + WIN["wide"] + WIN["long"]
    wins += WIN["rare"] if any(k in name for k in RARE) else []
    _check(name, 5, wins, _params(name))


GROUPS = {
    # tags and tag-mode filters: the trades equal the plain run, every tag path is computed
    "tags": dict(weekly_gate="tag", nwog_bias="tag", how_rule="tag", bellwether_15m="tag", judas_required="tag", midnight_confirm="tag",
                 mwd_nest="tag", mmbm_zone="tag", cot_oi_model=True, qshift_tag=True, dxy_gate="tag", bond_dir="tag", bond_range="tag",
                 decoupled_mode="tag", neutral_gate=("fifty_fifty", "premium_chop", "draw_delivered", "range_market", "decoupled"),
                 smt_both="tag", news_topdown="tag", nwog_regime="tag", vi_arrays=True),
    # scalp modes: the exits change in every engine
    "scalp": dict(chop_mode="scalp", nwog_regime="scalp", bias_neutral="scalp", htf_bias="combo2", no_narrative_scalp=True,
                  neutral_gate=("fifty_fifty", "range_market"), neutral_gate_mode="scalp", bond_range="scalp", decoupled_mode="scalp"),
    # side and bias filters
    "bias": dict(htf_bias="ordered", want_all_engines=True, weekly_open="either", bias_neutral="both", bias_persist=2,
                 next_array_on_fail=True, objective_neutral="day"),
    # the draw lock family
    "lock": dict(draw_first="session", matrix_tf_lower=True, judas_required="filter", day_pd="20d", pd_zone="third", vi_arrays=True),
    # stand-asides
    "stop": dict(objective_met_stop="day", chop_mode="skip", neutral_gate=("fifty_fifty", "premium_chop"), neutral_gate_mode="skip",
                 neutral_5050="armed", bias_open="all", bias_open_src="spy", midnight_target=True, wpr_tag="filter", cot_tag="filter",
                 qshift_size=0.5),
}


@pytest.mark.skipif(not ES1, reason="ES 1m data missing")
@pytest.mark.parametrize("group", list(GROUPS))
def test_no_look_ahead_grouped_switches_with_silver_bullet_and_ma_deuce_1m(group):
    p = Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0,
               sb_model=True, ma_deuce=True, pre_0700=True, pre_0900=True, **GROUPS[group])
    extra = lambda r: str(r.get("setup", "")).startswith(("sb_", "ma_deuce", "pre"))
    _check(group, 1, [("2024-01-22", "2024-02-02")] + WIN["def"], p, need=extra)


@pytest.mark.skipif(not ES5, reason="ES 5m data missing")
@pytest.mark.parametrize("tf", [5])
def test_no_look_ahead_es_map_midnight_through_backtest_run(tf):
    """D22 bias_open_src="es_map" through B.run(ref_df=...): the futures midnight open (00:00, +2 pts on every day so it differs from the frame's
    own) is mapped with the PRIOR session's close ratio; truncating both frames just after an entry leaves the entries unchanged."""
    from test_entries_stops import _no_look_ahead as nla
    p = _params("D22_bias_open_src_es_map")
    for a, b in WIN["def"] + WIN["wide"]:
        df = _bars(tf, a, b)
        ref = df.copy()
        mid = (ref.index.hour == 0) & (ref.index.minute == 0)
        ref.loc[mid, "open"] = ref.loc[mid, "open"] + 2.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            plain = B.run(df, tf, "ES", p, ref_df=ref)
        if len(plain):
            nla(df, tf, "ES", p, LA_COLS, every=max(1, len(plain) // 3), min_trades=1, lag=2, ref_df=ref)
            return
    pytest.fail("no window gave a trade")
