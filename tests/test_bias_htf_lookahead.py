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
# Selective switches whose default-window run has no trade (the full-suite run after setups_models#7/7 found them): the test pins what it needs to
# trade - PINS (extra Params the switch needs to be reachable at all; not a change of any default) and SEL_WIN (single months where the narrow switch fires).
PINS = {"M12-setup-selection-order": dict(htf_bias="react"),                    # turtle_soup="cc_limit" needs a bias side (ctx.cur_bias); SM_POST has draw_lock off
        "OT-one-state-tool-pairing_expansion_ob": dict(htf_bias="react"),       # the expansion state needs the bias side
        "M13-pattern1-full-sequence-ote-fvg": dict(ote_need_s=False)}           # ote_need_s + the FVG overlap together leave no order in these windows; the overlap rule alone is checked
SEL_WIN = {"OT-one-state-tool-pairing_expansion_ob": [("2023-09-01", "2023-10-01"), ("2024-10-01", "2024-10-16")],
           "M13-pattern1-full-sequence-ote-fvg": [("2023-07-01", "2023-08-01"), ("2023-06-01", "2023-07-01")],
           "new-clarity-filter-pass-if-arguing": [("2024-02-01", "2024-03-01"), ("2024-04-01", "2024-05-01")],
           "OT-M17-cc09_001-checklist_gate": [("2023-10-01", "2023-11-01")]}
# No trade in 7 years of quarterly windows even with the enabling switches: the check runs on the surrogate (the same state / trigger code computed without the filter).
ZERO_OK = {"OT-one-state-tool-pairing_retracement_void": dict(pairing="all", state_tag=True),
           "OT-one-state-tool-pairing_consolidation_eq": dict(pairing="all", state_tag=True),
           "M13-ote-needs-bias-trigger-structure": dict(ote_need_trigger=False),
           # caption-gap bias_htf#1/7: these gates leave no trade in the 2024 windows (the 15m / 60m order-flow state and the three-step minimum criteria reject nearly everything); the surrogate runs the
           # sibling code on the same 60m / 15m bars without the filter (bellwether_tf: swing breaks of tf_bars; bisi60_draw: the 60m FVG helpers); tests/test_caption_gap_bh1g.py checks the real paths with junk future bars
           # caption-gap bias_htf#2/7: a trade above the CE of the session's latest 15m FVG cancels nearly every lock on the 2023-24 windows; the surrogate keeps the 60m wick-CE cancel (tests/test_caption_gap_bh2c.py checks the 15m path)
           "A23-intraday-close-line-in-sand_15m": dict(sibi15_ce_cancel=False, wick_ce_60m=True),
           "BH-B6-intraday-iof_15": dict(iof_tf=0, bellwether_tf=15, htf_bias="combo"),
           "BH-B6-intraday-iof_60": dict(iof_tf=0, bellwether_tf=60, htf_bias="combo"),
           "BH-B4-HTF-bias-minimum-criteria": dict(min_criteria=False, bisi60_draw=True, htf_bias="combo")}
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
        wins = {(x, y) for v in WIN.values() for (x, y) in v} | {("2024-01-22", "2024-02-02")} | {w for v in SEL_WIN.values() for w in v}
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
    wins = SEL_WIN.get(name, []) + wins
    p = _params(name, **PINS.get(name, {}))
    if name in ZERO_OK:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if any(len(B.run(_bars(5, a, b), 5, "ES", p)) for a, b in WIN["def"] + WIN["wide"]):
                return _check(name, 5, wins, p)                 # (it does trade after all: the strict check)
        p = _params(name, **ZERO_OK[name])
    _check(name, 5, wins, p)


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
