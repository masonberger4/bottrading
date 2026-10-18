"""Owner directives 2026-10-18 (#1-#14), the verified bugs M1.2 / M7.1 and the shared helpers.

Unit tests on synthetic bars, plus no-look-ahead tests (full run vs truncated runs) that cover
every new switch. The databento tests skip when the ES data is not on disk."""
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, levels as L, strategy as S
from mentorship.confluence import Confluence
from mentorship.strategy import Params

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)


def arr(*rows):
    a = np.array(rows, dtype=float)
    return a[:, 0], a[:, 1], a[:, 2], a[:, 3]


def frame(d, rows, tf=1, start="00:00"):
    """rows of (o, h, l, c) from `start` every tf minutes."""
    idx = pd.date_range(pd.Timestamp(f"{d} {start}", tz=NY), periods=len(rows), freq=f"{tf}min")
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3],
                         "volume": 1.0}, index=idx)


def flat_day(d, px=100.0, tf=1, end=975, w=0.2, start=0):
    n = (end - start) // tf
    return frame(d, [(px, px + w, px - w, px)] * n, tf, f"{start // 60:02d}:{start % 60:02d}")


def rth_day(d, hi, lo, close=None, tf=5):
    n = 390 // tf
    c = close if close is not None else (hi + lo) / 2
    rows = [(c, hi, lo, c)] + [(c, c + 0.1, c - 0.1, c)] * (n - 1)
    return frame(d, rows, tf, "09:30")


# --- #14 breaker zone helper / #6 breaker MT ----------------------------------------------

BRK = arr((10, 10.2, 9.8, 10.0), (10, 10.1, 9.5, 9.6), (9.6, 9.7, 9.0, 9.2),
          (9.2, 9.9, 9.1, 9.8), (9.8, 10.4, 9.7, 10.3),
          (10.3, 10.3, 9.6, 9.7), (9.7, 9.8, 9.2, 9.3), (9.3, 9.4, 8.6, 8.8),
          (8.8, 9.6, 8.7, 9.5), (9.5, 10.0, 9.4, 9.9), (9.9, 10.8, 9.8, 10.7))


def test_breaker_zone_range_body_and_mt():
    o, h, l, c = BRK
    z = L.breaker_zone(o, h, l, c, 2, 7, 10)                       # default: full range
    assert (z.top, z.bottom, z.src, z.i) == (10.4, 9.7, 4, 10) and z.mt == pytest.approx(10.05)
    b = L.breaker_zone(o, h, l, c, 2, 7, 10, mode="body")
    assert (b.top, b.bottom) == (10.3, 9.8) and b.mt == pytest.approx(10.05)
    assert L.breaker_zone(o, h, l, c, 2, 7, 10, mode="range", mt_mode="body").mt == pytest.approx(10.05)
    assert L.breaker_mt(o, h, l, c, 3, "range") == pytest.approx(9.5)
    assert L.breaker_mt(o, h, l, c, 3, "body") == pytest.approx(9.5)
    # a wick-only gap overlaps the range zone but not the body zone
    wick = L.Zone("bull", 10.35, 10.31, 11, 10)
    assert wick.overlaps(z) and not wick.overlaps(b)
    with pytest.raises(ValueError):
        L.breaker_zone(o, h, l, c, 2, 7, 10, mode="bogus")
    assert L.breaker_zone(o, h, l, c, 2, 7, 10, mode="leg") is not None      # D6 leg / last built
    assert Params().breaker_zone == "range"
    with pytest.raises(ValueError):
        Params(breaker_zone="bogus")
    assert Params(breaker_zone="last").breaker_zone == "last"


def test_breakers_use_the_helper_both_directions():
    o, h, l, c = BRK
    br = [z for z in L.breakers(o, h, l, c, 2) if z.kind == "bull"]
    assert br and br[0] == L.breaker_zone(o, h, l, c, 2, 7, 10)
    # bearish mirror: the same bars mirrored in price give a bearish breaker at the mirrored candle
    mo, mh, ml, mc = -o, -l, -h, -c
    bb = [z for z in L.breakers(mo, mh, ml, mc, 2) if z.kind == "bear"]
    assert bb and bb[0].src == 4 and (bb[0].top, bb[0].bottom) == (-9.7, -10.4)
    assert bb[0].mt == pytest.approx(-10.05)


def test_unicorn_sides_switch_validates():
    with pytest.raises(ValueError):
        Params(unicorn_sides="up")
    with pytest.raises(ValueError):
        replace(Params(), news_wait="sometimes")
    assert Params(unicorn_sides="short").unicorn_sides == "short"


# --- turtle soup core (M12) ---------------------------------------------------------------

def test_turtle_soup_core():
    l = np.array([10, 9.5, 9.0, 9.8, 9.9, 10.2])
    c = np.array([10.2, 9.7, 9.3, 10.1, 10.0, 10.4])
    assert L.turtle_soup(l, c, 9.4, 2, 3, 1.0, 3)           # 0.4 below, closed back above at 3
    assert not L.turtle_soup(l, c, 9.4, 2, 3, 0.3, 3)       # deeper than "a little"
    assert not L.turtle_soup(l, c, 9.4, 2, 2, 1.0, 3)       # no close back yet (bar 2 itself)
    assert not L.turtle_soup(l, c, 9.4, 2, 6 - 1 + 4, 1.0, 3)


# --- calendar helpers (shared: next_trading_day; #3, #4) ----------------------------------

def test_trading_day_helpers_and_release_times():
    assert C.last_trading_day_of_year(date(2022, 12, 30))
    assert not C.last_trading_day_of_year(date(2022, 12, 29))
    assert C.last_trading_day_of_year(date(2023, 12, 29))
    assert C.last_trading_day_of_year(date(2021, 12, 31))
    assert C.next_trading_day(date(2026, 7, 2)) == date(2026, 7, 6)      # 07-03 holiday + weekend
    assert C.next_trading_day(date(2025, 12, 24)) == date(2025, 12, 26)
    assert C.last_n_trading_days(2026, 2) == [date(2026, 12, 30), date(2026, 12, 31)]
    assert C.release_times(date(2026, 6, 1)) == [585, 600]               # PMI + ISM manufacturing
    assert C.release_times(date(2026, 6, 5))[0] == 510                  # NFP
    assert 840 in C.release_times(date(2026, 6, 17))                      # FOMC


# --- #3 year end (switch, off by default) -------------------------------------------------

def _days(start, n, step):
    out, d, px = [], pd.Timestamp(start), 100.0
    while len(out) < n:
        if C.is_trading_day(d.date()):
            out.append(rth_day(d.date(), px + 1, px - 1, px + step * 0.9))
            px += step
        d += pd.Timedelta(days=1)
    return out


def test_year_end_takes_side_from_december():
    day = date(2022, 12, 30)
    falling = _days("2022-11-20", 30, -1.0)
    falling = [x for x in falling if x.index[0].date() < day]
    assert S.december_dir(falling, day) == -1
    p = Params(year_end="december")
    tags, block = S.day_context(falling, day, p)
    assert "year_end_long" in tags and block["year_end"] == (-1,)        # squaring: no shorts
    tags, block = S.day_context(falling, day, replace(p, year_end_map="with"))
    assert "year_end_short" in tags and block["year_end"] == (1,)
    rising = [x for x in _days("2022-11-20", 30, 1.0) if x.index[0].date() < day]
    assert S.day_context(rising, day, p)[1]["year_end"] == (1,)          # Dec up -> squaring short
    flat = [x for x in _days("2022-11-20", 30, 0.0) if x.index[0].date() < day]
    tags, block = S.day_context(flat, day, p)
    assert "year_end" in tags and "year_end" not in block
    assert S.day_context(falling, day, replace(p, year_end="long"))[1]["year_end"] == (-1,)
    tags, block = S.day_context(falling, day, replace(p, year_end="tag"))
    assert "year_end_long" in tags and "year_end" not in block
    assert "year_end" not in S.day_context(falling, day, Params())[0]   # default off
    assert S.day_context(falling, date(2022, 12, 29), p)[1].get("year_end") is None
    late = [x for x in falling if x.index[0].date() >= date(2022, 12, 2)]
    assert S.december_dir(late, day) == 0                                # no session before Dec 1


# --- #12 risk ------------------------------------------------------------------------------

def test_risk_sizing_1_2_and_cap_1_3():
    p = Params(es_pt=1.0, lot=5, max_notional=1e12)
    assert S._first_units(p, 100_000.0, 10.0, 4000.0) == 120              # MES: 24 contracts
    assert S._first_units(replace(p, lot=50), 100_000.0, 10.0, 4000.0) == 100   # ES: 2 contracts
    assert S._first_units(Params(max_notional=1e9), 100_000.0, 1.0, 500.0) == 1200   # SPY
    assert S._first_units(replace(p, **{"risk_dollars": 1000.0, "max_total_risk": 2000.0}),
                          100_000.0, 10.0, 4000.0) == 100                 # legacy 1% preset
    assert S._first_units(p, 100_000.0, 10.0, 4000.0, 0.5) == 60          # re-entry half = 0.6%
    # an add that would lift open risk to 1.35% is shrunk to fit 1.3%
    pos = dict(basis=4000.0 * 120, stop=3990.0, n=120, add=None)
    tr = SimpleNamespace(shares=120, adds=[])
    S._arm_add(pos, tr, 4002.0, 7, replace(p, lot=1, adds=(0.5,)), 100_000.0)
    assert pos["add"] is not None and pos["add"]["q"] * 12.0 <= 1300 - 1200 + 1e-9
    pos2 = dict(pos, add=None, stop=3995.0)                               # at-risk 600: room 700
    S._arm_add(pos2, tr, 4002.0, 7, replace(p, lot=1, adds=(0.5,)), 100_000.0)
    assert pos2["add"]["q"] == 60
    pos3 = dict(pos, add=None, stop=4001.0)                               # stop above basis: clamp 0
    S._arm_add(pos3, tr, 4002.0, 7, replace(p, lot=1, adds=(0.5,)), 100_000.0)
    assert pos3["add"]["q"] == 60


# --- #7 resistance cap ------------------------------------------------------------------

def _conf(rows, t0):
    cf = Confluence.__new__(Confluence)
    a = np.array(rows, float)
    cf.z = {"15m": dict(kind=a[:, 0], top=a[:, 1], bottom=a[:, 2], known=np.full(len(a), float(t0.value)),
                        dead=a[:, 3], life=float(pd.Timedelta("5D").value), src=a[:, 4])}
    cf.st, cf.tol = {}, 0.25
    return cf


def test_resistance_cap_levels():
    t0 = pd.Timestamp("2024-03-01 09:00", tz=NY)
    now = t0 + pd.Timedelta(hours=1)
    cf = _conf([(-1, 5002, 4998, np.inf, 0)], t0)
    assert cf.resistance(now, 4990.0, 1, ("15m",))[:2] == (4998.0, "15m")           # (a)
    assert cf.resistance(now, 4999.0, 1, ("15m",))[0] == 4999.0                     # (f) straddle
    assert cf.resistance(now, 4999.0, 1, ("15m",), straddle=False) is None
    killed = _conf([(-1, 5002, 4998, float((t0 + pd.Timedelta(minutes=30)).value), 0)], t0)
    assert killed.resistance(now, 4990.0, 1, ("15m",)) is None                      # (c) dead before
    later = _conf([(-1, 5002, 4998, float((now + pd.Timedelta(minutes=30)).value), 0)], t0)
    assert later.resistance(now, 4990.0, 1, ("15m",)) is not None                   # dies later: caps
    short = _conf([(1, 4982, 4978, np.inf, 0)], t0)
    assert short.resistance(now, 4990.0, -1, ("15m",))[0] == 4982.0                 # (d) mirror
    ob = _conf([(-1, 5002, 4998, np.inf, 1)], t0)
    assert ob.resistance(now, 4990.0, 1, ("15m",)) is None                          # (g) OB only with src
    assert ob.resistance(now, 4990.0, 1, ("15m",), src=(0, 1)) is not None
    sup = _conf([(1, 4991, 4985, np.inf, 0)], t0)
    assert sup.support(now, 4990.0, 1, "15m")[:2] == (4991.0, 4985.0)


# --- #13 round handles in the real contract's prices ---------------------------------------

def test_round_levels_map_real_to_engine():
    l = np.array([4520.0, 4506.0, 4512.0]); h = l + 3
    sd = S.Side(1, l + 1, h, l, l + 2, np.array([0]) if False else 1)
    ctx = SimpleNamespace(start=0, adj=np.full(3, 600.0), round_step=50.0, round_from="midnight")
    # real low so far 3906 -> nearest untaken round below = 3900 -> engine 4500
    assert S._round_levels(ctx, sd, 2, False) == [4500.0]
    # targets above the real high 3923 (4523-600): 3950, 4000 -> engine 4550, 4600
    assert S._round_levels(ctx, sd, 2, True, 2) == [4550.0, 4600.0]
    sh = S.Side(-1, l + 1, h, l, l + 2, 1)
    assert S._round_levels(ctx, sh, 2, False) == [-4550.0]                 # short: above the high


# --- #4 news dealing range ----------------------------------------------------------------

def _news_day(d, R):
    df = flat_day(d, 100.0, 1, 975)
    k = R
    pat = [(100, 101, 100, 100.8), (100.8, 103, 101, 102.5), (102.5, 102, 100.5, 101),
           (101, 101, 99, 99.5), (99.5, 101.5, 100, 101)]
    for j, row in enumerate(pat):
        df.iloc[k + j] = list(row) + [1.0]
    return df


def test_news_dealing_range_made_and_jobs_floor():
    d = date(2026, 6, 1)                                     # PMI 09:45 + ISM 10:00
    df = _news_day(d, 600)
    hist = [rth_day(date(2026, 5, 29), 104, 96)]
    ctx = S.DayCtx(df, d, hist, 1)
    ctx.tf = 1
    dr = S._news_ranges(ctx, d, Params())
    m = dr[600]["made"]
    assert ctx.t[m] == 604 and (dr[600]["hi"], dr[600]["lo"]) == (103.0, 99.0)
    assert S._news_gate(SimpleNamespace(news_dr=dr), Params(), 570, 660)["R"] == 600
    fx = S._news_ranges(ctx, d, Params(news_wait="fixed"))
    assert ctx.t[fx[600]["made"]] == 630
    assert S._news_ranges(ctx, d, Params(news_wait="off")) == {}
    # truncation: before the range completes nothing is "made" yet; afterwards identical
    cut = S.DayCtx(df[df.index < pd.Timestamp(f"{d} 10:03", tz=NY)], d, hist, 1)
    assert S._news_ranges(cut, d, Params())[600]["made"] is None
    cut2 = S.DayCtx(df[df.index <= pd.Timestamp(f"{d} 10:06", tz=NY)], d, hist, 1)
    assert S._news_ranges(cut2, d, Params())[600] == dr[600]
    # jobs day: the range is complete no earlier than R + 30 (Ep04 ~8:23)
    j = date(2026, 6, 5)
    jctx = S.DayCtx(_news_day(j, 510), j, [rth_day(date(2026, 6, 4), 104, 96)], 1)
    jd = S._news_ranges(jctx, j, Params())[510]
    assert jctx.t[jd["made"]] >= 540
    # no range by R + 90: None (no entries after R)
    nctx = S.DayCtx(flat_day(d, 100.0, 1, 975), d, hist, 1)
    assert S._news_ranges(nctx, d, Params())[600]["made"] is None


# --- #9 draw lock ----------------------------------------------------------------------------

def test_mark_levels_nearest_and_no_look_ahead():
    d = date(2026, 6, 9)
    hist = [rth_day(date(2026, 6, 5), 104, 94), rth_day(date(2026, 6, 8), 106, 93)]
    df = flat_day(d, 100.0, 5, 975)
    ctx = S.DayCtx(df, d, hist, 5)
    p = Params(es_pt=1.0)
    lk = S.mark_levels(ctx, None, 570, "AM", p)
    assert lk["side"] == 1 and lk["target"] == 106.0 and lk["name"] == "pdh1"
    row = dict(draw_dn=94.5, draw_dn_name="D_swing_low", draw_up=float("nan"), draw_up_name="")
    lk2 = S.mark_levels(ctx, row, 570, "AM", p)
    assert lk2["side"] == -1 and lk2["target"] == 94.5 and lk2["kind"] == "pool"
    assert S.mark_levels(ctx, None, 570, "AM", p, spent=[106.0])["side"] == -1      # L14e spent
    # bars after the lock time do not change it
    df2 = df.copy()
    late = df2.index >= pd.Timestamp(f"{d} 09:30", tz=NY)
    df2.loc[late, ["high", "close"]] = 120.0
    assert S.mark_levels(S.DayCtx(df2, d, hist, 5), None, 570, "AM", p)["target"] == 106.0
    # a level traded through before the lock is dropped (L14d)
    df3 = df.copy()
    df3.iloc[20, 1] = 106.5                     # overnight high 106.5 takes out the PDH 106
    lk3 = S.mark_levels(S.DayCtx(df3, d, hist, 5), None, 570, "AM", p)
    assert (lk3["target"], lk3["name"]) == (106.5, "pmh") and 106.0 not in [v for v, *_ in lk3["marked"]]
    # neutral when nothing is at least draw_lock_min_pts away
    assert S.mark_levels(ctx, None, 570, "AM", replace(p, draw_lock_min_pts=50))["side"] == 0


# --- #10 chop (tag only by default) --------------------------------------------------------

def test_chop_on_and_release():
    d = date(2026, 6, 10)
    hist = [rth_day(x.date(), 105, 95) for x in pd.bdate_range("2026-06-03", "2026-06-09")]
    rows = []
    for k in range(975 // 5):
        px = 100.6 if (k // 3) % 2 else 99.4                # crosses the midnight open often
        rows.append((px, px + 0.2, px - 0.2, px))
    rows[0] = (100.0, 100.2, 99.2, 99.4)
    rows[60] = (100.6, 104.5, 100.5, 104.4)                 # 05:00: breaks out by > 0.25 x ADR5
    df = frame(d, rows, 5)
    ctx = S.DayCtx(df, d, hist, 5)
    ch = S.Chop(ctx, hist, Params())
    on = [ch.update(i) for i in range(ctx.start, len(ctx.t))]
    k_on = ch.on_at
    assert k_on is not None and ctx.t[k_on] >= 120
    assert not ch.on and ch.released and not ch.state[ctx.start + 60]
    assert ch.state[ctx.start + 59] and not ch.active_before(ctx.start + 61)
    assert ch.active_before(k_on + 1) and not ch.active_before(k_on)


# --- #1 session close ------------------------------------------------------------------

def test_session_close_resolution_and_rth_history():
    fut = pd.concat([flat_day(date(2026, 6, 9), 100.0, 5, 975), frame(date(2026, 6, 9), [(100, 100.2, 99.8, 100)] * 60, 5, "18:00")])
    assert S.resolve_session_close(Params(), fut, "ES").session_close == 975
    assert S.resolve_session_close(Params(), fut, "SPY").session_close == 960
    assert S.resolve_session_close(Params(session_close=960), fut, "ES").session_close == 960
    assert S._eff_flat(Params()) == 960 and S._eff_flat(Params(session_close=975)) == 975
    assert S._eff_flat(Params(session_close=975, flatten=960)) == 960
    day = flat_day(date(2026, 6, 9), 100.0, 5, 975)
    assert (B.rth(day).index.hour * 60 + B.rth(day).index.minute).max() == 955
    ds = B.days(day, 5, close=975)
    assert (ds[0].index[-1].hour * 60 + ds[0].index[-1].minute) == 970


# --- htf table cut and the flip column (no look-ahead) -----------------------------------

@pytest.mark.skipif(not ES, reason="no ES data")
def test_htf_table_cut_and_flip_no_look_ahead():
    from mentorship import htf
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-01-01") & (df.index < "2024-05-01")]
    full = htf.table(df, cut_min=810)
    assert "flip" in full.columns and set(full.flip.unique()) <= {-1, 0, 1}
    for day in list(full.index)[-30::6]:
        cut = pd.Timestamp(day, tz=B.NY) + pd.Timedelta(hours=13, minutes=30)
        part = htf.table(df[df.index < cut], cut_min=810)
        for k in ("px", "draw_up", "draw_dn", "flip", "react"):
            a, b = full.loc[day][k], part.loc[day][k]
            assert a == b or (a != a and b != b), (day, k, a, b)
    base = htf.table(df)
    assert base.drop(columns="flip").equals(htf.table(df, cut_min=570).drop(columns="flip"))


# --- full runs: behaviour + no look-ahead -------------------------------------------------

def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, **kw):
    full = B.run(df, tf, sym, p, meta=meta, **kw)
    assert len(full) > 0, "no trades - the test window must produce some"
    for cut_t in full.entry_time.iloc[::every]:
        c = cut_t + pd.Timedelta(minutes=lag)
        pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
        part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
        a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
        b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
    return full


def test_synthetic_switches_no_look_ahead():
    x, y = B.synthetic(start="2026-06-01", end="2026-07-31", tf=5, seed=3)
    p = Params(es_pt=0.09, use_bias=False, last_hour_strict=True, t1_fixed_pts=5.0, day_target_pts=5.0,
               news_wait="fixed", unicorn_sides="long", breaker_mt_mode="body", breaker_mt_exit_after_t1=True,
               am_exit_mode="tighten", draw_lock_neutral="both", draw_lock_levels="live", draw_relock=True,
               draw_lock_min_pts=2.0, sloppy_mode="scalp", ob_entry="both", ob_entry_px="mt", ob_arm="touch",
               ob_stop="ext", risk_basis="equity", seen_from_created=False, pm_off_lunch=True,
               displacement_mult=0.5, turtle_soup="2023", year_end="december", min_draw_pts=0, leg_pd=0)
    _no_look_ahead(x, 5, "RW", p, ["entry_time", "entry", "stop", "t1", "shares", "entry_kind", "sloppy",
                                   "draw_px", "lh_sweet"], every=2, partner=y)


def test_synthetic_turtle_and_pm_judas_no_look_ahead():
    x, y = B.synthetic(start="2026-06-01", end="2026-08-14", tf=5, seed=11)
    p = Params(es_pt=0.09, use_bias=False, turtle_soup="2023", ts_max_pts=8.0, ob_entry="post_mss",
               draw_lock="off", pm_judas_1330=True, t1_fixed_pts=4.0, t1_fixed_all=True,
               sloppy_mode="stand_aside", ob_entry_cancel_on_mss=True, min_draw_pts=0, leg_pd=0)
    full = _no_look_ahead(x, 5, "RW", p, ["entry_time", "entry", "stop", "t1", "entry_kind"], every=2)
    assert full.t2.isna().all()                                             # t1_fixed_all


@pytest.mark.skipif(not ES, reason="no ES data")
def test_owner_defaults_es_no_look_ahead():
    """Every owner default at once on ES 5m with the databento meta (front-month frame, round
    pools, lock tables, cap, news range, OB entry, breaker MT, 1.2% risk, 16:15 close)."""
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2023-03-15") & (df.index < "2023-07-01")]
    meta = B.load_meta("ES", 5)
    full = _no_look_ahead(df, 5, "ES", Params(**FUT), ["entry_time", "entry", "stop", "t1", "shares",
                                                       "draw_px", "capped", "adj", "entry_kind"],
                          meta=meta)
    assert (full.entry_risk_pct <= 0.0121).all() and (full.peak_risk_pct <= 0.0131).all()
    assert (full.adj > 0).all()                                                       # 2023: shifted


@pytest.mark.skipif(not ES, reason="no ES data")
def test_owner_switches_es_no_look_ahead_and_behaviour():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-01-01") & (df.index < "2024-04-01")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=True, htf_resist_live=True, htf_resist_src=("fvg", "ob"),
               htf_targets_30m=True, runner_htf_exit="30m", draw_lock="off", ob_entry="post_mss",
               vi_arrays=True, news_range_pd=False, unicorn_sides="both", price_frame="front_month")
    full = _no_look_ahead(df, 5, "ES", p, ["entry_time", "entry", "stop", "t1", "unicorn_side", "capped",
                                           "resist_tf", "bz_mt"], every=3, meta=meta)
    uni = full[full.unicorn]
    assert set(uni[uni.side == "long"].unicorn_side) <= {"bull"}
    assert set(uni[uni.side == "short"].unicorn_side) <= {"bear"}
    # the breaker MT entry floor: a unicorn long never enters below the breaker MT
    lb = uni[(uni.side == "long") & uni.bz_mt.notna()]
    assert (lb.entry >= lb.bz_mt - 1e-9).all()
    sb = uni[(uni.side == "short") & uni.bz_mt.notna()]
    assert (sb.entry <= sb.bz_mt + 1e-9).all()
    # AM-family units are closed at 12:00 (owner #8)
    am = full[full.session != "PM"]
    et = pd.to_datetime(am.exit_time.astype(str).str[:19])
    assert ((et.dt.hour * 60 + et.dt.minute) <= 715).all()
    # last-hour label (owner #1): pm_last_hour = armed 15:00-15:50; lh_sweet = 15:15-15:45
    pmlh = full[full.setup == "pm_last_hour"]
    at = pd.to_datetime(pmlh.armed.astype(str).str[:19])
    m = at.dt.hour * 60 + at.dt.minute
    assert ((m >= 900) & (m < 950)).all() and (pmlh.lh_sweet == ((m >= 915) & (m < 945))).all()


@pytest.mark.skipif(not ES, reason="no ES data")
def test_futures_flatten_at_1615_and_switch():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-01-01") & (df.index < "2024-07-01")]
    kw = dict(**FUT, htf_resist_cap=False, draw_lock="off", news_wait="off", am=(0, 0), pm=(900, 950))
    a = B.run(df, 5, "ES", Params(**kw), confluence=False)
    eod = a[a.exit_reason.str.endswith("eod")]
    assert len(eod) and (eod.exit_time.astype(str).str[11:16] == "16:10").all()
    b = B.run(df, 5, "ES", Params(**kw, flatten=960), confluence=False)
    eod = b[b.exit_reason.str.endswith("eod")]
    assert len(eod) and (eod.exit_time.astype(str).str[11:16] == "15:55").all()


@pytest.mark.skipif(not ES, reason="no ES data")
def test_front_month_prices_inside_the_raw_contract_range():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2022-12-01") & (df.index < "2023-02-01")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, htf_resist_cap=False, draw_lock="off")
    t = B.run(df, 5, "ES", p, meta=meta)
    old = B.run(df, 5, "ES", replace(p, price_frame="back_adjusted", round_pools=False))
    assert len(t) and len(old)
    parts = []
    for ch in pd.read_csv("data/mentorship/ES_1min_dbraw.csv", index_col=0, chunksize=500_000):
        ch = ch[ch.index.str.startswith(("2022-12", "2023-01"))]
        if len(ch):
            parts.append(ch)
    raw = pd.concat(parts)
    raw.index = pd.to_datetime(raw.index, utc=True).tz_convert(B.NY)
    for r in t.itertuples():
        d = raw[raw.index.date == r.date]
        assert d.low.min() - 1e-6 <= r.entry <= d.high.max() + 1e-6, (r.date, r.entry)
    # without round pools the front-month frame only relabels prices: same trades, same P&L
    t2 = B.run(df, 5, "ES", replace(p, round_pools=False), meta=meta)
    pd.testing.assert_series_equal(t2.net, old.net)
    pd.testing.assert_series_equal((t2.entry + t2.adj).round(6), old.entry.round(6), check_names=False)


@pytest.mark.skipif(not ES, reason="no ES data")
def test_sb_ma_deuce_pre_open_with_lock_no_look_ahead():
    es = B.load("ES", 1, source="databento")
    es = es[(es.index >= "2024-01-02") & (es.index < "2024-02-10")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), sb_model=True, sb_london=True, sb_runner=True,
               ma_deuce=True, pre_0700=True, pre_0900=True, post_news=True, htf_resist_cap=True,
               conf_breakers=False, sb_mgmt="ladder")
    full = _no_look_ahead(es, 1, "ES", p, ["entry_time", "entry", "stop", "t1", "setup", "draw_px"],
                          every=3, lag=1, confluence=True)
    sbam = full[full.setup.isin(["sb_am", "sb_london", "ma_deuce"])]
    et = pd.to_datetime(sbam.exit_time.astype(str).str[:19])
    assert ((et.dt.hour * 60 + et.dt.minute) <= 719).all()                  # owner #8 extras


@pytest.mark.skipif(not ES, reason="no ES data")
def test_conf_breakers_and_sloppy_stand_aside_no_look_ahead():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-02-01") & (df.index < "2024-03-20")]
    p = Params(**FUT, conf_breakers=True, sloppy_mode="stand_aside", htf_resist_cap=False,
               draw_lock="off", news_wait="range", year_end="december", htf_bias="flip", bias_neutral="both")
    _no_look_ahead(df, 5, "ES", p, ["entry_time", "entry", "stop", "t1", "sloppy"], every=2)


def test_day_target_stops_the_day():
    x, y = B.synthetic(start="2026-06-01", end="2026-08-31", tf=5, seed=4)
    base = Params(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0, draw_lock="off", ob_entry="post_mss",
                  adds=())
    t = B.run(x, 5, "RW", replace(base, day_target_pts=0.5))
    for d, g in t.groupby("date"):
        g = g.sort_values("entry_time")
        pts = (g.net / (g.shares) / 0.09).cumsum().values
        hit = np.flatnonzero(pts >= 0.5)
        assert not len(hit) or hit[0] == len(g) - 1


@pytest.mark.skipif(not ES, reason="no ES data")
def test_pre_owner_switches_reproduce_the_old_engine():
    """Golden regression: every owner default switched back (study.PRE_OWNER) gives exactly the
    engine of commit 833350f (numbers recorded from that commit on this window, SB and Ma Deuce
    on): 23 trades, net 4693.52."""
    from mentorship.study import PRE_OWNER
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2024-01-01") & (df.index < "2024-04-01")]
    p = replace(Params(**FUT, leg_pd=0, min_draw_pts=0, sb_model=True, ma_deuce=True), **PRE_OWNER)
    t = B.run(df, 5, "ES", p)
    assert len(t) == 23 and round(t.net.sum(), 2) == 4693.52
    assert list(t.entry_time.astype(str).str[:16])[:3] == ["2024-01-09 10:25", "2024-01-10 15:30", "2024-01-11 10:00"]
