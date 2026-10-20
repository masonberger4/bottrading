"""Package day_week_context: no look-ahead for EVERY new switch, one study.DECISIONS variant per run (so each switch alone
changes the trades it can change; merged sets let conflicting values overwrite each other and the blocking switches leave
nothing to compare). Full run vs runs truncated just after entries must give identical entries (tags included).

  5m    main engine, a window that suits the switch (August for the August switches, a futures roll week, the
        Christmas / New Year / MLK weeks, an FOMC / NFP / CPI stretch)
  1m    the same variants with Silver Bullet, Ma Deuce and the 07:00 / 09:00 pre-open models on, so every switch is also
        exercised in those engines (at least one trade must come out)
"""
import warnings
from pathlib import Path

import pytest

from mentorship import backtest as B, study
from mentorship.strategy import Params

from test_entries_stops import _no_look_ahead  # noqa: F401,E402  (shared helper; used through _check)

ES5 = Path("data/mentorship/ES_5min_db.csv").exists()
ES1 = Path("data/mentorship/ES_1min_db.csv").exists()

# windows (start, end) tried in order until the run has a trade
WIN = {
    "def": [("2024-01-22", "2024-02-16"), ("2023-11-27", "2023-12-15")],         # FOMC Jan 31, NFP Feb 2, CPI Feb 13, Fridays
    "aug": [("2023-08-07", "2023-08-25")],                                        # the August switches (Aug 15+ and the whole month)
    "roll": [("2024-03-04", "2024-03-22")],                                       # the March roll week (Mar 11-15) and FOMC Mar 20
    "hol": [("2023-12-15", "2024-01-19")],                                        # Christmas eve / day, last day, Jan 2 first day, NFP Jan 5, MLK
    "sd": [("2023-07-10", "2023-07-28")],                                         # July: the seek-and-destroy months
    "rare": [("2024-08-05", "2024-08-23")],                                       # trend_recipe="only": the one trade of 2024 (Aug 13)
    "wide": [("2023-09-05", "2023-11-10")],                                       # last resort for the "only" / very selective switches
}
LA_COLS = ["entry_time", "entry", "stop", "t1", "side", "day_tags"]


def _variants():
    names = list(study.DECISIONS)
    return names[names.index("B11_inside_week_tag"):names.index("X16_journal_tags_off") + 1]


def _kind(name: str) -> str:
    n = name.lower()
    if "august" in n:
        return "aug"
    if "roll" in n:
        return "roll"
    if any(k in n for k in ("holiday", "first_day", "year_first", "low_vol", "early_close", "last_day")):
        return "hol"
    if "sd_" in n:
        return "sd"
    return "def"


def _params(name, **extra):
    kw = dict(study.DECISIONS[name])
    kw.update(extra)
    return Params(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1, leg_pd=0, min_draw_pts=0, **kw)


_CACHE = {}


def _bars(tf, a, b):
    """The window's bars. The raw 1m / 5m frame is loaded once per process, every window of WIN is sliced out and the
    raw frame is dropped again (the 1m ES file is ~2.7M rows: several xdist workers holding it exhaust the memory)."""
    if tf not in _CACHE:
        raw = B.load("ES", tf, source="databento")
        wins = {(x, y) for v in WIN.values() for (x, y) in v}
        _CACHE[tf] = {(x, y): raw[(raw.index >= x) & (raw.index < y)].copy() for (x, y) in wins}
        del raw
    return _CACHE[tf][(a, b)]


def _check(name, tf, windows, p, need=None, max_cuts=4):
    """Full run vs truncated runs on the first window that gives a trade `need(row)` accepts (any trade when none does:
    a switch that blocks every Silver Bullet / Ma Deuce trade of the windows still has to give the same main-engine
    entries when truncated)."""
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
    _check(name, 5, WIN[_kind(name)] + WIN["def"] + WIN["wide"] + WIN["rare"], _params(name))


def _extra(row) -> bool:
    return str(row.get("setup", "")).startswith(("sb_", "ma_deuce", "pre"))


@pytest.mark.skipif(not ES1, reason="ES 1m data missing")
@pytest.mark.parametrize("name", _variants())
def test_no_look_ahead_each_variant_with_silver_bullet_and_ma_deuce_1m(name):
    p = _params(name, sb_model=True, ma_deuce=True, pre_0700=True, pre_0900=True)
    kind = _kind(name)
    wins = WIN[kind] if kind != "def" else [("2023-08-07", "2023-08-25")] + WIN["def"]
    _check(name, 1, wins + WIN["hol"] + WIN["wide"], p, need=_extra)
