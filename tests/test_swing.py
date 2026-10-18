"""Swing package: bar building, sparse-table queries, order-flow states, and a full-vs-truncated
no-look-ahead run of One Shot One Kill on synthetic CME-session data."""
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from swing import arrays as A, bars, bias, osok, synthetic

NY = "America/New_York"


@pytest.fixture(scope="module")
def df():
    return synthetic.bars("2021-01-03", "2022-03-31", seed=1)


@pytest.fixture(scope="module")
def frames(df):
    return bars.resample(df)


def test_4h_blocks_anchor_at_globex_open(frames):
    assert set(frames["4h"].start.dt.hour) == {18, 22, 2, 6, 10, 14}


def test_sunday_evening_belongs_to_monday(frames):
    d = frames["D"]
    assert (d.day.dt.weekday < 5).all()
    mon = d[d.day.dt.weekday == 0].iloc[0]
    assert mon.start.weekday() == 6 and mon.start.hour == 18


def test_weeks_run_sunday_to_friday(frames):
    w = frames["W"]
    assert (w.start.dt.weekday == 6).all()
    assert (w.end.dt.weekday == 4).iloc[:-1].all()


def test_sparse_matches_brute_force():
    rng = np.random.default_rng(3)
    lo = rng.normal(0, 1, 500).cumsum()
    hi = lo + rng.random(500)
    sp = A.Sparse(lo, hi)
    for _ in range(300):
        s, x = int(rng.integers(0, 520)), float(rng.normal(lo.mean(), 3))
        le = next((i for i in range(s, 500) if lo[i] <= x), 500)
        ge = next((i for i in range(s, 500) if hi[i] >= x), 500)
        assert sp.first_le(s, x) == le
        assert sp.first_ge(s, x) == ge


def test_bias_reads_a_displaced_uptrend():
    # three legs up, each leaving a bullish FVG and closing above the prior swing high
    rows = []
    p = 100.0
    for leg in range(3):
        for k in range(3):                      # pullback: 3 down candles
            rows.append((p, p + 0.5, p - 2, p - 1.5)); p -= 1.5
        for k in range(4):                      # displacement: gaps between candles
            rows.append((p, p + 4, p - 0.2, p + 3.8)); p += 3.8
    a = np.array(rows)
    f = pd.DataFrame(a, columns=["open", "high", "low", "close"])
    st = bias.states(f)
    assert st.dir.iloc[-1] == 1


def test_no_look_ahead(df, frames):
    p = osok.Params(fib_gate=False, cases=("A", "B", "C"))
    full = osok.run(frames, p)
    cut = pd.Timestamp("2021-12-15 12:00", tz=NY)
    part = osok.run(bars.resample(df[df.index < cut]), p)
    a = full[full.exit_time <= cut - pd.Timedelta(days=7)].reset_index(drop=True)
    b = part[part.exit_time <= cut - pd.Timedelta(days=7)].reset_index(drop=True)
    assert len(a) > 0
    pd.testing.assert_frame_equal(a, b)


def test_switches_run(frames):
    for kw in (dict(target="prev_week"), dict(order="limit"), dict(stop="array"),
               dict(scale_in=False), dict(ob_entry="open"), dict(cutoff=0.8)):
        t = osok.run(frames, osok.Params(**kw))
        assert isinstance(t, pd.DataFrame)


def test_swing_model_runs_and_has_no_look_ahead(df, frames):
    from swing import swing_model
    full = swing_model.run(frames)
    assert isinstance(full, pd.DataFrame)
    cut = pd.Timestamp("2021-12-15 12:00", tz=NY)
    part = swing_model.run(bars.resample(df[df.index < cut]))
    if len(full) and len(part):
        a = full[full.exit_time <= cut - pd.Timedelta(days=14)].reset_index(drop=True)
        b = part[part.exit_time <= cut - pd.Timedelta(days=14)].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
