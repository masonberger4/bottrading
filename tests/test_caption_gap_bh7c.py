"""Caption-gap pass, package bias_htf#7/7 review fixes: the no-look-ahead (full vs truncated data) checks of the STUDY functions of bh7s.py and the parked stock screens (stocks.py / stocks_watch.py).

A study row that closed before the cut must be identical when the data after the cut is removed; an entry made before the cut must be identical too. The windows are small synthetic futures walks (no market
data), the cuts are session / 4h-bar boundaries so that no partial candle enters the truncated run. Nothing here writes a file."""
import warnings

import numpy as np
import pandas as pd
import pytest

from mentorship import bh7s as S7, htf, stocks as ST, stocks_watch as SW, study
from mentorship.strategy import Params, htf_bars

from test_caption_gap_bh1c import fut_walk  # noqa: E402

NY = "America/New_York"


@pytest.fixture(scope="module")
def walk():
    return fut_walk("2025-03-03", "2026-02-27", seed=3, vol=1.5)


@pytest.fixture(scope="module")
def short_walk():
    return fut_walk("2025-10-06", "2026-02-27", seed=3, vol=1.5)


def _cut_after(df, ts):
    """The next Friday-session close (17:00 NY) at or after `ts`: a boundary at which no session / week / month candle is partial."""
    t = pd.Timestamp(ts).tz_convert(NY)
    d = t.normalize() + pd.Timedelta(hours=17)
    while d.weekday() != 4 or d < t:
        d += pd.Timedelta(days=1)
    return d


def _same(a, b):
    return (a == b) or (isinstance(a, float) and isinstance(b, float) and a != a and b != b) or (isinstance(a, float) and isinstance(b, float) and abs(a - b) < 1e-9)


def test_osok_does_not_look_ahead(short_walk):
    walk = short_walk
    """osok on the minute frame: every trade entered before the cut equals the truncated run's, and every trade closed (stop / target) before the cut too."""
    for kw in (dict(direction=-1, min_rr=0.5), dict(direction=1, min_rr=0.5), dict(min_rr=0.5, h1_types=("fvg", "ob")), dict(direction=-1, min_rr=0.5, inside="within")):
        full = S7.osok(walk, **kw)
        assert len(full) >= 2, kw
        for tr in (full[len(full) // 3], full[2 * len(full) // 3]):
            cut = _cut_after(walk, tr["t_out"])
            part = S7.osok(walk[walk.index < cut], **kw)
            a = [t for t in full if t["t_in"] < cut]
            b = [t for t in part if t["t_in"] < cut]
            assert len(a) == len(b), (kw, str(cut))
            for x, y in zip(a, b):
                for k in ("side", "t_in", "entry", "stop", "target", "origin_tf", "h1_type", "second_entry"):
                    assert _same(x[k], y[k]), (kw, k, x[k], y[k])
                if x["exit_reason"] in ("stop", "target") and x["t_out"] < cut:
                    assert (x["t_out"], x["exit"], x["exit_reason"]) == (y["t_out"], y["exit"], y["exit_reason"]), kw


def test_swing_reentry_does_not_look_ahead(short_walk):
    walk = short_walk
    arrays = S7.build_arrays(walk)
    h4 = htf_bars(walk, 240)
    full = S7.swing_reentry_study(h4, arrays, min_rr=1.0)
    assert len(full) >= 5
    done = [r for r in full if r["exit_reason"] != "open"]
    for r in (done[len(done) // 3], done[2 * len(done) // 3]):
        cut = _cut_after(walk, h4["end"].iloc[min(r["j_out"] + 3, len(h4) - 1)])
        wc = walk[walk.index < cut]
        h4c = htf_bars(wc, 240)
        part = S7.swing_reentry_study(h4c, S7.build_arrays(wc), min_rr=1.0)
        keys = ("seq", "attempt", "j_in", "j_out", "entry", "exit", "exit_reason", "size")
        a = [tuple(x[k] for k in keys) for x in full if x["exit_reason"] != "open" and x["j_out"] < len(h4c) - 1]
        b = [tuple(x[k] for k in keys) for x in part if x["exit_reason"] != "open" and x["j_out"] < len(h4c) - 1]
        assert a == b and len(a) >= 1


def test_scale_in_and_daily_stop_do_not_look_ahead(walk):
    daily = htf.sessions(walk)
    arrays = S7.build_arrays(walk)
    full_s = S7.osok_scale_in(daily, arrays, -1, first_frac=0.25, side=-1)
    full_d = S7.daily_stop_model(daily, arrays)
    assert len(full_s) >= 5 and len(full_d) >= 3
    for k in (len(full_s) // 3, 2 * len(full_s) // 3):
        cut = _cut_after(walk, pd.Timestamp(full_s[k]["week"]).tz_localize(NY) + pd.Timedelta(days=9))
        wc = walk[walk.index < cut]
        dc, ac = htf.sessions(wc), S7.build_arrays(wc)
        a = [r for r in full_s if pd.Timestamp(r["week"]) + pd.Timedelta(days=4) < cut.tz_localize(None)]
        b = [r for r in S7.osok_scale_in(dc, ac, -1, first_frac=0.25, side=-1) if pd.Timestamp(r["week"]) + pd.Timedelta(days=4) < cut.tz_localize(None)]
        assert len(a) == len(b) >= 1
        for x, y in zip(a, b):
            for key in ("week", "n_fills", "first_entry", "avg_entry", "size", "stop", "exit", "exit_reason"):
                assert _same(x[key], y[key]), (key, x[key], y[key])
    for r in (full_d[len(full_d) // 3], full_d[2 * len(full_d) // 3]):
        cut = _cut_after(walk, pd.Timestamp(r["fills"][0][0]).tz_localize(NY) + pd.Timedelta(days=9))
        wc = walk[walk.index < cut]
        part = S7.daily_stop_model(htf.sessions(wc), S7.build_arrays(wc))
        lim = cut.tz_localize(None) - pd.Timedelta(days=2)               # (the model never evaluates a frame's last session)
        a = [x for x in full_d if pd.Timestamp(x["fills"][0][0]) < lim and x["exit_reason"] in ("stop", "target")]
        b = [x for x in part if pd.Timestamp(x["fills"][0][0]) < lim and x["exit_reason"] in ("stop", "target")]
        assert a and [(x["fills"], x["exit"], x["exit_reason"], x["stop"], x["draw"]) for x in a if pd.Timestamp(x["fills"][-1][0]) < lim] == \
            [(x["fills"], x["exit"], x["exit_reason"], x["stop"], x["draw"]) for x in b if pd.Timestamp(x["fills"][-1][0]) < lim]


def test_swing_readd_does_not_look_ahead(walk):
    """swing_readd reads 4h bars after the order's own bar only; entries given before the cut give the same rows on the truncated bars once the trade closed."""
    h4 = htf_bars(walk, 240)
    o, hi, lo, cl = (h4[k].values.astype(float) for k in ("open", "high", "low", "close"))
    entries = []
    for j in range(40, len(h4) - 80, 90):
        px = float(cl[j])
        entries.append(dict(time=h4.index[j], side=1, entry=px - 1.0, stop=px - 12.0, target=px + 30.0, partial_level=px + 6.0))
    full = S7.swing_readd(h4, entries)
    assert len(full) >= 4
    cut_n = len(h4) // 2
    part = S7.swing_readd(h4.iloc[:cut_n], [e for e in entries if h4.index.get_loc(e["time"]) < cut_n - 1])
    done = [(i, r) for i, r in enumerate(part) if r.get("exit_reason") not in (None, "open")]
    for i, r in done:
        for k in r:
            assert _same(r[k], full[i][k]) or isinstance(r[k], (list, tuple, dict)), (k, r[k], full[i][k])


# --- the parked stock screens ------------------------------------------------------------------------------------------------------------------------

def _path(points, n, start="2025-06-02"):
    xs = np.arange(n)
    px = np.interp(xs, [p_[0] for p_ in points], [p_[1] for p_ in points])
    return pd.DataFrame({"open": px, "high": px + 0.4, "low": px - 0.4, "close": px}, index=pd.bdate_range(start, periods=n))


def test_stock_screens_do_not_look_ahead():
    """smt_screen / leaders / watchlist / sell_list answer from bars <= asof: removing every bar after asof changes nothing (the forward returns of sell_list are reporting only and are not compared)."""
    p = Params(stocks_mode=True, stock_rs_min=0.0)
    n = 260
    idx_full = _path([(0, 100), (60, 120), (90, 108), (130, 126), (160, 114), (200, 130), (259, 118)], n)
    stocks = {"A": _path([(0, 50), (60, 66), (90, 60), (130, 72), (160, 66), (200, 76), (259, 70)], n),
              "B": _path([(0, 50), (60, 60), (90, 54), (130, 58), (160, 52), (200, 55), (259, 48)], n),
              "C": _path([(0, 80), (60, 70), (90, 76), (130, 66), (160, 72), (200, 62), (259, 58)], n)}
    dates = [idx_full.index[k] for k in (150, 180, 215, 240)]
    for asof in dates:
        cut = lambda d: d[d.index <= asof]  # noqa: E731
        ic = cut(idx_full)
        sc = {s: cut(d) for s, d in stocks.items()}
        for s in stocks:
            assert ST.smt_screen(stocks[s], idx_full, asof, p) == ST.smt_screen(sc[s], ic, asof, p)
            assert ST.weekly_up(stocks[s], asof, p) == ST.weekly_up(sc[s], asof, p)
        assert ST.rs_rank(stocks, idx_full, asof, n=40, p=p) == ST.rs_rank(sc, ic, asof, n=40, p=p)
        assert ST.leaders(stocks, idx_full, asof, p, n=40) == ST.leaders(sc, ic, asof, p, n=40)
        assert ST.watchlist(asof, stocks, idx_full, p) == ST.watchlist(asof, sc, ic, p)
        for need_rally in (False, True):
            a = [r["symbol"] for r in SW.sell_list(asof, stocks, idx_full, p, need_rally=need_rally, need_poised=False)]
            b = [r["symbol"] for r in SW.sell_list(asof, sc, ic, p, need_rally=need_rally, need_poised=False)]
            assert a == b
        assert SW.index_poised(idx_full, asof) == SW.index_poised(ic, asof)
        for s in stocks:
            assert SW.base_ok(stocks[s], asof, p) == SW.base_ok(sc[s], asof, p)
