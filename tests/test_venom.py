"""The Venom model (mentorship/venom.py) and the CONTRACT B default (the raw-table cache key in study._bias_cache)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import cards, venom as V
from mentorship.strategy import Params

NY = "America/New_York"
LO, HI = 100.0, 110.0           # the 08:00-09:30 range


def c5(rows, start="2026-06-23 09:30"):
    idx = pd.date_range(start, periods=len(rows), freq="5min", tz=NY)
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["k_last"] = np.arange(len(rows))
    return df


# 09:30 on: a drift down to the low, a SIBI through it, one candle under, a BISI back above it
LONG = [
    (103.0, 103.5, 102.0, 102.2),
    (102.2, 102.4, 101.0, 101.2),       # j-2 of the SIBI: low 101.0
    (101.2, 101.3, 98.5, 98.8),         # SIBI middle: trades down through 100, closes down
    (98.8, 99.4, 98.0, 98.4),           # j of the SIBI: high 99.4 < 101.0 (the gap 99.4-101.0)
    (98.4, 98.9, 97.8, 98.6),           # under the low
    (98.6, 101.6, 98.5, 101.4),         # BISI middle: from under the low, closes back above it, up close
    (101.4, 102.6, 99.6, 102.4),        # j of the BISI: low 99.6 > the j-2 high 98.9 (the gap 98.9-99.6)
    (102.4, 103.0, 101.9, 102.8),
]


def mirror(rows, ax=210.0):
    return [(ax - o, ax - l, ax - h, ax - c) for o, h, l, c in rows]


def test_find_signal_long_and_its_mirror():
    p = Params(es_pt=1.0)
    s = V.find_signal(c5(LONG), LO, HI, 1, p)
    assert s is not None and s["sibi"]["m"] == 2 and s["bisi"]["m"] == 5 and s["k"] == 6
    assert s["sibi"]["top"] == 101.0 and s["sibi"]["bottom"] == 99.4 and s["bisi"]["bottom"] == 98.9 and s["bisi"]["top"] == 99.6
    assert s["k_open"] == 101.4 and s["b_close"] == 101.4 and s["b_low"] == 98.5
    # the BPR: the two gaps overlap 99.4 .. 99.6 -> CE 99.5
    assert V.bpr_ce(s) == pytest.approx(99.5)
    assert V.find_signal(c5(LONG), LO, HI, -1, p) is None
    # the bearish mirror against the 08:00-09:30 high (210 - 100 = 110): same candles, mirrored prices
    m = V.find_signal(c5(mirror(LONG)), LO, HI, -1, p)
    assert m is not None and m["k"] == 6 and m["k_open"] == pytest.approx(-(210.0 - 101.4)) and V.bpr_ce(m) == pytest.approx(-(210.0 - 99.5))


def test_find_signal_needs_the_sibi_first_and_min_under():
    p = Params(es_pt=1.0)
    no_sibi = [(103.0, 103.5, 102.0, 102.2), (102.2, 102.4, 100.5, 100.8), (100.8, 101.0, 99.5, 100.6), (100.6, 102.0, 100.4, 101.8), (101.8, 103.0, 101.5, 102.8)]   # one wick through the low, no sell-side gap through it
    assert V.find_signal(c5(no_sibi), LO, HI, 1, p) is None
    assert V.find_signal(c5(LONG), LO, HI, 1, Params(es_pt=1.0, venom_min_under=2))["bisi"]["m"] == 5    # two candles between the fangs
    assert V.find_signal(c5(LONG), LO, HI, 1, Params(es_pt=1.0, venom_min_under=3))["bisi"]["m"] == 6    # three: the next BISI (candle 6 also pierces back above the low)
    assert V.find_signal(c5(LONG), LO, HI, 1, Params(es_pt=1.0, venom_min_under=4)) is None


def _ctx(rows_pre, rows, eq=100_000.0):
    """A bare day context: 5m bars from 08:00 (the window), then `rows` from 09:30 to 12:00 (flat filler after them)."""
    allr = rows_pre + rows
    allr += [allr[-1][3:] * 4] * (30 - len(rows))
    idx = pd.date_range("2026-06-23 08:00", periods=len(allr), freq="5min", tz=NY)
    a = np.array(allr, float)
    return SimpleNamespace(start=0, t=np.asarray(idx.hour * 60 + idx.minute), idx=idx, o=a[:, 0], h=a[:, 1], l=a[:, 2], c=a[:, 3],
                           tf=5, equity=eq, lock={})


PRE = [(105.0, 110.0, 104.0, 105.0)] + [(105.0, 106.0, 100.0, 103.0)] + [(103.0, 104.0, 102.5, 103.0)] * 16      # 08:00-09:30: high 110, low 100


def test_run_venom_bpr_ce_stop_fills_and_reaches_the_buy_side(monkeypatch):
    from mentorship import strategy as S
    monkeypatch.setattr(S, "blocked", lambda *a, **k: None)
    rows = LONG + [(102.8, 103.0, 101.2, 101.6), (101.6, 106.0, 101.5, 105.8), (105.8, 110.5, 105.5, 110.2)]   # back to the 101.4 limit, then up through 110
    p = Params(es_pt=1.0, lot=1, cost_per_share=0.0)
    tr = V.run_venom(_ctx(PRE, rows), p, pd.Timestamp("2026-06-23").date(), "ES", {})
    assert len(tr) == 1
    t = tr[0]
    assert t.setup == "venom" and t.side == "long" and t.entry == pytest.approx(101.4) and t.stop == pytest.approx(99.5 - p.pad)
    assert t.t1 == pytest.approx(110.0 - p.exit_before_pts) and t.exits[0][3] == "t1" and t.entry_time.strftime("%H:%M") == "10:10"
    # VENOM-STOP A: below the pierce candle, entry at the displacement close or less
    ta = V.run_venom(_ctx(PRE, rows), Params(es_pt=1.0, lot=1, venom_stop="pierce", venom_entry="close"), pd.Timestamp("2026-06-23").date(), "ES", {})
    assert len(ta) == 1 and ta[0].stop == pytest.approx(98.5 - p.pad) and ta[0].entry == pytest.approx(101.4)


def test_run_venom_respects_the_am_lock_and_the_target_first(monkeypatch):
    from mentorship import strategy as S
    monkeypatch.setattr(S, "blocked", lambda *a, **k: None)
    p = Params(es_pt=1.0, lot=1)
    d = pd.Timestamp("2026-06-23").date()
    rows = LONG + [(102.8, 103.0, 101.2, 101.6), (101.6, 106.0, 101.5, 105.8), (105.8, 110.5, 105.5, 110.2)]
    ctx = _ctx(PRE, rows)
    ctx.lock = {"AM": dict(side=-1)}
    assert V.run_venom(ctx, p, d, "ES", {}) == []                         # the session lock points down: no long Venom
    ctx.lock = {"AM": dict(side=0)}
    assert V.run_venom(ctx, p, d, "ES", {}) == []                         # a neutral day: no Venom
    up = LONG + [(102.8, 110.5, 102.6, 110.2)]                            # the buy side trades before the limit fills: cancelled
    assert V.run_venom(_ctx(PRE, up), p, d, "ES", {}) == []


def test_cards_contract_b_and_venom_stop_b_are_the_defaults():
    p = Params()
    assert p.htf_series == "raw" and p.venom_model and p.venom_stop == "bpr_ce" and p.venom_entry == "open"
    assert ("CONTRACT", "B") not in cards.NOT_BUILT and ("VENOM-STOP", "B") not in cards.NOT_BUILT
    v = cards.variants()
    assert v["SC-CONTRACT-A"]["htf_series"] == "adjusted" and v["SC-VENOM-STOP-A"] == dict(venom_stop="pierce", venom_entry="close")
    with pytest.raises(ValueError):
        Params(venom_stop="wide")


def test_raw_table_cache_key(tmp_path, monkeypatch):
    """study._bias_cache: a raw-series table is kept on disk under a key of the raw file's last bar and the adj, and read back as it was built."""
    from mentorship import study, backtest as B, htf
    idx = pd.date_range("2026-01-02 09:30", periods=3, freq="5min", tz=NY)
    raw = pd.DataFrame(dict(open=1.0, high=2.0, low=0.5, close=1.5, volume=1.0), index=idx)
    meta = pd.DataFrame(dict(adj=[0.0, 0.0, 0.0]), index=idx)
    built = []

    def fake_table(df, **kw):
        built.append(kw.get("raw") is not None)
        return pd.DataFrame({"px": [1.0], "lst": [[1.0, 2.0]]}, index=[pd.Timestamp("2026-01-02")])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(study, "SRC", "databento")
    monkeypatch.setattr(study, "SYMS", ("ES", "NQ", "YM"))
    monkeypatch.setattr(study, "_BX_TABLES", {})
    monkeypatch.setattr(B, "load_meta", lambda *a, **k: meta)
    monkeypatch.setattr(B, "load_raw", lambda *a, **k: raw)
    monkeypatch.setattr(B, "load", lambda *a, **k: raw)
    monkeypatch.setattr(htf, "table", fake_table)
    kw = B.table_kw(Params())
    assert '"hs":"raw"' in kw["bx"]
    t1 = study._bias_cache(5, kw=kw)
    pk = list((tmp_path / "runs" / "mentorship").glob("*_raw*.pkl"))
    assert built == [True] and len(pk) == 1 and t1.lst.iloc[0] == [1.0, 2.0]
    monkeypatch.setattr(study, "_BX_TABLES", {})                         # a new process: read from disk, not rebuilt
    t2 = study._bias_cache(5, kw=kw)
    assert built == [True] and t2.lst.iloc[0] == [1.0, 2.0]
