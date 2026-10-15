import random

import numpy as np
import pandas as pd
import pytest

from claude_hf import features, strategy as S
from claude_hf.evolve import Search


def panel(days=12, minutes=5, n=8, seed=0):
    rng = np.random.default_rng(seed)
    per = 390 // minutes
    idx = pd.DatetimeIndex(np.concatenate([
        pd.date_range(pd.Timestamp(d, tz="America/New_York") + pd.Timedelta(minutes=570),
                      periods=per, freq=f"{minutes}min")
        for d in pd.bdate_range("2026-03-02", periods=days)]))
    c = 100 * np.exp(np.cumsum(rng.normal(0, 1e-3, (len(idx), n)), axis=0))
    o = np.vstack([c[:1], c[:-1]]) * (1 + rng.normal(0, 2e-4, c.shape))
    h, l = np.maximum(o, c) * 1.0005, np.minimum(o, c) * 0.9995
    cols = [f"S{i}" for i in range(n)]
    mk = lambda a: pd.DataFrame(a, idx, cols)
    return {"open": mk(o), "high": mk(h), "low": mk(l), "close": mk(c),
            "volume": mk(rng.integers(1000, 5000, c.shape).astype(float))}


def test_features_never_look_ahead():
    p = panel()
    f1 = features.build(p)
    cut = 5 * 78 + 40
    q = {k: v.copy() for k, v in p.items()}
    for v in q.values():
        v.iloc[cut + 1:] *= 1.37            # rewrite the future
    f2 = features.build(q)
    for name in ("vwap", "orb", "volshock", "dayret", "gap"):
        assert np.allclose(getattr(f1, name)[:cut + 1], getattr(f2, name)[:cut + 1]), name
    for k in features.LOOKBACKS:
        assert np.allclose(f1.idio[k][:cut + 1], f2.idio[k][:cut + 1])


def test_flipping_weights_flips_gross_pnl():
    f = features.build(panel())
    g = S.random_genome(random.Random(3))
    g.update({"A.mode": 0, "A.slots": 4, "A.threshold": 0.0},
             **{k: 1 for k in g if k.startswith("r.")})
    h = dict(g, **{f"A.{w}": -g[f"A.{w}"] for w in S.WEIGHTS})
    a = S.backtest(g, f, range(f.days), cost_bps=-S.SEC_FEE_BPS / 2)   # zero total cost
    b = S.backtest(h, f, range(f.days), cost_bps=-S.SEC_FEE_BPS / 2)
    assert a["trades"] == b["trades"] > 0
    assert np.allclose(a["daily"], -b["daily"])


def test_positions_close_before_the_session_ends():
    f = features.build(panel())
    g = S.playbook(S.random_genome(random.Random(1)), "A")
    g.update(start=300, length=90, hold=S.HOLDS.index(60))
    bars = S.decision_bars(g, f)
    assert len(bars) and (bars + S.hold_bars(g, 5) <= f.bars_per_day - 1).all()


def test_search_runs_and_logs(tmp_path):
    f = features.build(panel(days=20))
    s = Search(f, seed=1, batch=6, out=tmp_path)
    s.run(generations=5, init=20, quiet=True)
    r = s.report()
    assert set(r) >= {"train", "val", "test", "genome"}
    assert len((tmp_path / "generations.jsonl").read_text().splitlines()) == 6


def test_day_types():
    from datetime import date
    from claude_hf.daytypes import day_type, expiration
    assert day_type(date(2026, 9, 16)) == "fomc"
    assert day_type(date(2026, 10, 14)) == "cpi"
    assert expiration(2026, 6) == date(2026, 6, 18)          # Juneteenth moves quad witching
    assert day_type(date(2026, 9, 18)) == "quad_witching"
    assert day_type(date(2026, 8, 21)) == "opex"
    assert day_type(date(2026, 9, 30)) == "quarter_end"
    assert day_type(date(2026, 9, 1)) == "month_start"
    assert day_type(date(2026, 9, 10)) == "roll_week"
    assert day_type(date(2026, 8, 18)) == "tue"


def test_skipped_days_are_flat():
    f = features.build(panel())
    g = S.random_genome(random.Random(4))
    g.update({k: 0 for k in g if k.startswith("r.")})
    st = S.backtest(g, f, range(f.days))
    assert st["trades"] == 0 and not st["daily"].any()
