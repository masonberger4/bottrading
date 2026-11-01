"""Package targets_partials (build_log.md): the owner #7 REVISED speed bump, the ladder / partial planner,
target sources, SD engine, TGIF zone and the mid-trade partials.

Unit tests on hand-made bars / stub confluence tables, scenarios through run_day (the real engine path) and
no-look-ahead runs (full vs truncated, entries AND exits) covering every new switch. The ES tests skip when
the databento data is not on disk."""
import warnings
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, levels as L, strategy as S, study, targets as TP
from mentorship.confluence import Confluence
from mentorship.strategy import Params
from dataclasses import dataclass as _oa_dc


@_oa_dc
class Params(Params):   # OA1029: these tests were written for the pre-build engine and exercise other rules - every OA1029 default back at its old value
    __annotations__ = {k: object for k in __import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD}
    locals().update(__import__('mentorship.study', fromlist=['OA1029_OLD']).OA1029_OLD)

from test_review_fixes import A_LOCK, A_ROWS, BASE, D0, day, history, run  # noqa: E402
from test_entries_stops import _no_look_ahead, _syn  # noqa: E402

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0)
COLS = ["entry_time", "entry", "stop", "t1", "shares", "rungs", "lv_tags"]
T0 = pd.Timestamp("2026-06-23 02:00", tz=NY)
NOW = pd.Timestamp("2026-06-23 09:45", tz=NY)


def conf(rows, tfs=("15m",), t0=T0):
    """Stub confluence table: rows (kind, top, bottom, dead, src[, tf])."""
    cf = Confluence.__new__(Confluence)
    cf.z = {}
    for tf in tfs:
        a = np.array([r[:5] for r in rows if (r[5] if len(r) > 5 else tfs[0]) == tf], float)
        if len(a):
            cf.z[tf] = dict(kind=a[:, 0], top=a[:, 1], bottom=a[:, 2], known=np.full(len(a), float(t0.value)),
                            dead=a[:, 3], life=float(pd.Timedelta("5D").value), src=a[:, 4])
    cf.st, cf.tol = {}, 0.25
    return cf


def fake_ctx(cf, n=12, tf=5, **kw):
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq=f"{tf}min", tz=NY)
    return SimpleNamespace(conf=cf, idx=idx, tf=tf, **kw)


def side(sign=1, n=12, base=100.0):
    a = np.full(n, base)
    return S.Side(sign, a, a + 0.5, a - 0.5, a, 1, 0.0)


def flag_log():
    out = []
    return out, out.append


# --- defaults / validation / aliases ------------------------------------------------------------

def test_defaults_validation_and_aliases():
    p = Params()
    assert p.htf_resist_mode == "bump" and p.htf_resist_cap and p.htf_bump_max == 1          # owner #7 REVISED default
    assert p.mgmt == "ladder" and not p.run_down and p.capture_frac == 0.0
    for kw in (dict(htf_resist_mode="x"), dict(rb_targets="x"), dict(resistance_mode="x"), dict(sd_anchor="x"),
               dict(measuring_anchor="x"), dict(wick_read="x"), dict(mgmt="x"), dict(matrix_targets=("x",)),
               dict(target_hygiene=("x",)), dict(target_order=("x",)), dict(wick_partial_tfs=("2h",)),
               dict(sd_levels=(0.25,)), dict(sd_levels=(5.0,)), dict(capture_frac=0.1),
               dict(tgif_zone=True, tgif_cap=0.5, tgif_stand_down=0.4), dict(sd_close_window=(700, 600)),
               dict(partial_extra_frac=0.9), dict(htf_resist_cap_tfs=("2h",))):
        with pytest.raises(ValueError):
            Params(**kw)
    assert Params(sd_levels=(0.5, 1.0, 4.5)).sd_levels == (0.5, 1.0, 4.5)
    q = Params(wick_ce_partial=True, sd_neg05_first=True, rej_targets=True, proj_measuring=True, wick_week=True,
               wick_daily_src="eth")
    assert q.wick_partials and q.sd_half_partial and q.rb_targets == "ladder" and q.measuring_target
    assert q.wick_weekly and q.wick_session == "eth"
    for m in ("ladder", "t1t2", "unit"):
        Params(mgmt=m)


def test_study_has_a_variant_for_every_new_switch():
    new = {f.name for f in fields(Params)} & set(NEW_FIELDS)
    assert new == set(NEW_FIELDS)
    names = " ".join(str(v) for v in study.DECISIONS.values())
    for f in NEW_FIELDS:
        if f in KNOBS:
            continue
        assert f"'{f}'" in names, f
    ids = {k.split("_")[0] for k in study.DECISIONS}
    for rid in ("X3", "X3a", "X3b", "X3c", "X3d", "X3f", "X3g", "X3h", "A6", "A10", "A17", "A22", "A23", "L4", "L9",
                "L11", "L12", "L13", "L14d", "L16", "M8", "M14.2", "M14.4", "X1", "D23", "Ep01.21", "Ep03.5", "Ep03.19",
                "Ep03.22", "Ep04.11", "Ep04.12", "Ep06.4", "Ep07.1", "Ep08.9"):
        assert rid in ids, rid
    for k, v in study.DECISIONS.items():
        Params(**v)                                            # every variant is a valid parameter set


NEW_FIELDS = (
    "htf_resist_mode", "htf_resist_cap_tfs", "htf_bump_max", "htf_bump_frac", "htf_bump_below_min", "smt_bank_against_frac", "ladder_all_pools", "run_down", "ladder_max_levels",
    "partial_extra_frac", "partial_extra_cap", "wick_partials", "wick_ce_partial", "wick_partial_tfs",
    "wick_partial_longest", "wick_partial_protect", "wick_partial_min_pts", "sd_half_partial", "sd_neg05_first",
    "halfway_partial", "halfway_min_pts", "smt_bank", "smt_bank_frac", "smt_bank_min_r", "resistance_mode",
    "res_low_max", "res_high_min", "capture_frac", "measuring_gap", "measuring_band", "measuring_mid_frac",
    "measuring_target", "measuring_anchor", "measuring_pool_pts", "proj_measuring", "trail_breakaway", "proj_breaker",
    "proj_org_k", "proj_ext", "mm_targets", "mm_anchor", "matrix_targets", "breaker_first", "skip_exhausted",
    "fvg_over_ob", "fvg_remainder", "weekly_gap_ce_only", "rb_targets", "rej_targets", "pool_body_edge",
    "rb_min_wick_frac", "target_hygiene", "void_targets", "leg_start_target", "inter_swing_target", "target_ltf_obs",
    "keep_inner_levels", "inner_min_pts", "final_htf", "org_reprice", "adr_target", "adr_frac", "adr_early",
    "adr_early_frac", "sd_anchor", "sd_swings", "sd_cluster_ticks", "sd_roles", "sd_align", "sd_align_tol_pts",
    "sd_no_pool_fallback", "sd_close_hit", "sd_close_window", "tgif_zone", "tgif_zone_levels", "tgif_cap",
    "tgif_stand_down", "tgif_exits", "tgif_exit_fracs", "target_order", "ladder_fracs_bulk", "ladder_news_day",
    "clean_eq_pref", "close_draw", "pool_rank", "pool_rank_reach", "rel_tfs", "draw_below_eq", "lrlr_max",
    "pool_runner_pts", "wick_daily_src", "wick_week", "wick_tfs", "wick_read", "sb_split")
KNOBS = {"htf_resist_cap_tfs", "htf_bump_max", "htf_bump_frac", "partial_extra_frac", "partial_extra_cap", "wick_partial_longest", "wick_partial_protect",
         "wick_partial_min_pts", "halfway_min_pts", "smt_bank_frac", "smt_bank_min_r", "res_low_max", "res_high_min",
         "measuring_band", "adr_frac", "adr_early_frac", "sd_swings", "sd_align_tol_pts", "tgif_zone_levels", "tgif_cap",
         "tgif_stand_down", "tgif_exit_fracs", "ladder_fracs_bulk", "pool_rank_reach", "inner_min_pts",
         "sd_close_window", "rb_min_wick_frac", "wick_ce_partial", "sd_neg05_first", "rej_targets", "proj_measuring",
         "wick_week", "wick_daily_src", "measuring_mid_frac"}


# --- owner #7 REVISED: speed bump / cap / split ------------------------------------------------------

def test_resist_cfg_modes():
    assert TP.resist_cfg(Params()) == ((), ("15m", "30m", "1h", "4h", "D"))
    assert TP.resist_cfg(Params(htf_resist_mode="cap")) == (("15m", "30m", "1h", "4h", "D"), ())
    assert TP.resist_cfg(Params(htf_resist_mode="split")) == (("1h", "4h", "D"), ("15m", "30m"))
    assert TP.resist_cfg(Params(htf_resist_cap=False, htf_resist_mode="cap")) == ((), ())


ARR = [("array", "array")]


def _lv(*v):
    return list(v), ["array"] * len(v)


def test_apply_resist_bump_cap_and_split_long():
    # long 4990, risk 4, a bearish 15m FVG 4998-5002 between price and a pool at 5010 (spec test a)
    cf = conf([(-1, 5002.0, 4998.0, np.inf, 0)])
    sd, ctx = side(), fake_ctx(cf)
    log, flag = flag_log()
    lv, kd = [5010.25], ["pool"]
    r = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0), 4990.0, 4.0, lv, kd, flag)           # default = bump
    assert r["lv"] == [4997.5, 5010.25] and r["kinds"] == ["bump", "pool"] and r["capx"] is None and r["bumps"] == [4997.5]
    r = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0, htf_resist_mode="cap"), 4990.0, 4.0, lv, kd, flag)
    assert r["lv"] == [4997.5] and r["capx"] == 4997.5 and r["resist"][1] == "15m"          # exit before it, nothing beyond
    r = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0, htf_resist_mode="split"), 4990.0, 4.0, lv, kd, flag)
    assert r["kinds"] == ["bump", "pool"] and r["capx"] is None                              # 15m bumps in the split
    cf4 = conf([(-1, 5002.0, 4998.0, np.inf, 0, "4h")], tfs=("4h",))
    r = TP.apply_resist(fake_ctx(cf4), sd, 5, Params(es_pt=1.0, htf_resist_mode="split"), 4990.0, 4.0, lv, kd, flag)
    assert r["lv"] == [4997.5] and r["capx"] == 4997.5                                       # 4h caps in the split
    # the cap skips the trade when the room is short (spec test b); a bump simply is not a partial point
    near = conf([(-1, 4996.0, 4992.0, np.inf, 0)])
    assert TP.apply_resist(fake_ctx(near), sd, 5, Params(es_pt=1.0, htf_resist_mode="cap"), 4990.0, 4.0, lv, kd, flag) is None
    assert "x_htf_resist" in log
    r = TP.apply_resist(fake_ctx(near), sd, 5, Params(es_pt=1.0, htf_bump_below_min=False), 4990.0, 4.0, lv, kd, flag)
    assert r["bumps"] == [] and r["lv"] == [5010.25]                                         # 1.5 pt < 1R: dropped by the switch
    r = TP.apply_resist(fake_ctx(near), sd, 5, Params(es_pt=1.0), 4990.0, 4.0, lv, kd, flag)
    assert r["bumps"] == [4991.5]                                                            # default: a small protected partial (extra path)
    # master off: byte-identical
    off = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0, htf_resist_cap=False), 4990.0, 4.0, lv, kd, flag)
    assert off["lv"] == lv and off["kinds"] == kd and off["bumps"] == []


def test_apply_resist_mirror_existing_rung_and_behind_the_trade():
    # short 5000 (side space = mirrored): a bullish 15m FVG 4982-4986 below price, a pool at 4970 below
    cf = conf([(1, 4986.0, 4982.0, np.inf, 0)])
    sd = side(-1)
    ctx = fake_ctx(cf)
    entry = -5000.0
    lv, kd = [sd.x(4969.75)], ["pool"]
    r = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0), entry, 4.0, lv, kd, lambda n: None)
    assert [sd.x(v) for v in r["bumps"]] == [4986.5] and r["kinds"] == ["bump", "pool"]
    # an existing array rung at the FVG edge becomes the bump (no duplicate rung)
    lv2, kd2 = [sd.x(4986.5), sd.x(4969.75)], ["array", "pool"]
    r = TP.apply_resist(ctx, sd, 5, Params(es_pt=1.0), entry, 4.0, lv2, kd2, lambda n: None)
    assert r["kinds"] == ["bump", "pool"] and len(r["lv"]) == 2
    # an FVG BEHIND the trade (a bullish zone under a long, bearish over a short) is never a target or a bump
    behind = conf([(1, 4988.0, 4984.0, np.inf, 0)])
    r = TP.apply_resist(fake_ctx(behind), side(), 5, Params(es_pt=1.0), 4990.0, 4.0, [5010.0], ["pool"], lambda n: None)
    assert r["bumps"] == [] and r["lv"] == [5010.0]
    # a killed FVG (dead before the signal close) never counts; htf_bump_max limits the count
    dead = conf([(-1, 5002.0, 4998.0, float((NOW - pd.Timedelta(minutes=30)).value), 0)])
    assert TP.apply_resist(fake_ctx(dead), side(), 5, Params(es_pt=1.0), 4990.0, 4.0, [5010.0], ["pool"],
                           lambda n: None)["bumps"] == []
    two = conf([(-1, 5002.0, 4998.0, np.inf, 0), (-1, 5006.0, 5004.0, np.inf, 0), (-1, 5009.0, 5008.0, np.inf, 0)])
    r = TP.apply_resist(fake_ctx(two), side(), 5, Params(es_pt=1.0, htf_bump_max=1), 4990.0, 4.0, [5020.0], ["pool"],
                        lambda n: None)
    assert r["bumps"] == [4997.5]
    r = TP.apply_resist(fake_ctx(two), side(), 5, Params(es_pt=1.0), 4990.0, 4.0, [5020.0], ["pool"], lambda n: None)
    assert r["bumps"] == [4997.5]                                                            # default htf_bump_max = 1
    r = TP.apply_resist(fake_ctx(two), side(), 5, Params(es_pt=1.0, htf_bump_max=2), 4990.0, 4.0, [5020.0], ["pool"], lambda n: None)
    assert r["bumps"] == [4997.5, 5003.5]


def test_bump_straddling_array_uses_ce_or_far_edge():
    cf = conf([(-1, 5002.0, 4996.0, np.inf, 0)])                     # the entry 4999 sits inside 4996-5002
    r = TP.bump_levels(fake_ctx(cf), side(), 5, Params(es_pt=1.0), 4999.0, 1.0, ("15m",), (0,))
    assert r == [5001.5]                                             # CE 4999 is not above the entry -> the far edge - 0.5
    cf2 = conf([(-1, 5006.0, 4992.0, np.inf, 0)])                    # CE 4999 > entry 4995: the bump sits at the CE - 0.5
    assert TP.bump_levels(fake_ctx(cf2), side(), 5, Params(es_pt=1.0), 4995.0, 1.0, ("15m",), (0,)) == [4998.5]


# --- L9 / A22 / L14d HTF array levels ---------------------------------------------------------------

def bar_ctx(cf, o, h, l, c, hist=None, **kw):
    n = len(o)
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz=NY)
    return SimpleNamespace(conf=cf, idx=idx, tf=5, start=0, o=np.array(o, float), h=np.array(h, float),
                           l=np.array(l, float), c=np.array(c, float), t=(idx.hour * 60 + idx.minute).values,
                           hist=hist or [], **kw)


def test_htf_levels_filters():
    n = 12
    flat = np.full(n, 100.0)
    ctx = bar_ctx(conf([(-1, 5002.0, 4998.0, np.inf, 0), (-1, 5001.0, 4997.0, np.inf, 1)]), flat, flat + .5, flat - .5, flat)
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    p = Params(es_pt=1.0)
    lv = TP.htf_levels(ctx, sd, 5, 4990.0, p, ("15m",))
    assert sorted(v for v, _ in lv) == [4997.0, 4998.0, 4999.0, 5000.0]                # OB and FVG both: near edge + CE
    lv = TP.htf_levels(ctx, sd, 5, 4990.0, Params(es_pt=1.0, fvg_over_ob=True), ("15m",))
    assert sorted(v for v, _ in lv) == [4998.0, 5000.0]                                # the overlapping OB is dropped
    # a weekly gap keeps its CE only
    w = conf([(-1, 5010.0, 5000.0, np.inf, 2, "W")], tfs=("W",))
    ctxw = bar_ctx(w, flat, flat + .5, flat - .5, flat)
    sdw = S.Side(1, ctxw.o, ctxw.h, ctxw.l, ctxw.c, 1, 0.0)
    assert len(TP.htf_levels(ctxw, sdw, 5, 4990.0, p, ("W",))) == 2
    assert [v for v, _ in TP.htf_levels(ctxw, sdw, 5, 4990.0, Params(es_pt=1.0, weekly_gap_ce_only=True), ("W",))] == [5005.0]


def test_htf_levels_exhausted_and_remainder():
    # price traded 5000 -> 5001 into a bearish FVG 4998-5002 after it formed: exhausted / a remainder
    n = 12
    h = np.full(n, 4990.5); l = np.full(n, 4989.5); o = np.full(n, 4990.0)
    h[3] = 5001.0
    ctx = bar_ctx(conf([(-1, 5002.0, 4998.0, np.inf, 0)], t0=T0), o, h, l, o.copy())
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert len(TP.htf_levels(ctx, sd, 8, 4992.0, Params(es_pt=1.0), ("15m",))) == 2              # default: still listed
    assert TP.htf_levels(ctx, sd, 8, 4992.0, Params(es_pt=1.0, skip_exhausted=True), ("15m",)) == []
    assert TP.htf_levels(ctx, sd, 8, 4992.0, Params(es_pt=1.0, target_hygiene=("htf",)), ("15m",)) == []
    rem = TP.htf_levels(ctx, sd, 8, 4992.0, Params(es_pt=1.0, fvg_remainder=True), ("15m",))
    assert [v for v, _ in rem] == [5001.0, 5001.5, 5002.0]                                      # traded extreme, CE, far edge
    # untouched: nothing changes
    h2 = np.full(n, 4990.5)
    ctx2 = bar_ctx(conf([(-1, 5002.0, 4998.0, np.inf, 0)]), o, h2, l, o.copy())
    sd2 = S.Side(1, ctx2.o, ctx2.h, ctx2.l, ctx2.c, 1, 0.0)
    assert len(TP.htf_levels(ctx2, sd2, 8, 4992.0, Params(es_pt=1.0, skip_exhausted=True), ("15m",))) == 2


# --- A6 / Ep03.5 measuring gap, A10 leg start, A17 rejection blocks ----------------------------------

def test_measuring_gap_anchors_and_pool_requirement():
    o, h, l, c = [np.array(x, float) for x in zip(*[
        (100, 100.5, 99.5, 100), (100, 100.2, 95.0, 95.4),              # 1: the sweep extreme 95.0
        (95.4, 100.5, 95.3, 100.2), (100.2, 104.0, 100.0, 103.8),       # 2-3: displacement
        (103.8, 109.0, 103.0, 108.8),                                    # 4: candle after
        (108.8, 112.0, 107.0, 111.8), (111.8, 112.5, 111.5, 112.2)])]   # 5-6
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    g = TP.measuring_gap(sd, dict(ext=95.0, ext_i=1), 6, 112.5, Params(es_pt=1.0))
    assert g is not None and (g.bottom, g.top) == (104.0, 107.0)        # near the middle of the 95-112.5 leg
    assert TP.measuring_level(g, 95.0, "far") == 107.0 + (107.0 - 95.0)
    assert TP.measuring_level(g, 95.0, "near") == 104.0 + 9.0
    assert TP.measuring_level(g, 95.0, "ce") == 105.5 + 10.5
    assert TP.measuring_level(g, 95.0, "dup") == 104.0 + 12.0
    # a body closed through the gap: not a measuring gap any more
    c2 = c.copy(); c2[6] = 103.0
    sd2 = S.Side(1, o, h, l, c2, 1, 0.0)
    g2 = TP.measuring_gap(sd2, dict(ext=95.0, ext_i=1), 6, 112.5, Params(es_pt=1.0))
    assert g2 is None or g2.bottom != 104.0
    # the target needs a pool within measuring_pool_pts (062: -1 SD lines up with an old pool)
    p = Params(es_pt=1.0, measuring_gap=True, measuring_target=True)
    ctx = bar_ctx(None, o, h, l, c)
    ctx.org = []
    lvt = []
    sw = dict(ext=95.0, ext_i=1)
    out = TP.extra_sources(ctx, sd, 6, p, sw, 100.0, 4.0, 112.5, 112.5, [(119.2, "pool")], lvt, None)
    assert (119.0, "array") in out and "measuring_target" in lvt
    out = TP.extra_sources(ctx, sd, 6, p, sw, 100.0, 4.0, 112.5, 112.5, [(130.0, "pool")], [], None)
    assert out == []                                                      # no pool near the projection: dropped
    out = TP.extra_sources(ctx, sd, 6, Params(es_pt=1.0, measuring_gap=True), sw, 100.0, 4.0, 112.5, 112.5, [], lvt, None)
    assert out == []                                                      # tag only without measuring_target


def test_extra_sources_mm_projection_org_ext_and_leg_start():
    o, h, l, c = [np.array(x, float) for x in zip(*[
        (110, 110.5, 109.0, 109.2), (109.2, 109.4, 107.0, 107.2), (107.2, 107.3, 104.0, 104.2),
        (104.2, 104.3, 100.0, 100.4), (100.4, 104.0, 100.2, 103.8), (103.8, 108.0, 103.6, 107.9),
        (107.9, 108.6, 107.5, 108.4)])]
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    ctx = bar_ctx(None, o, h, l, c)
    ctx.org, ctx.org_today = [(102.0, 104.0)], False
    sw = dict(ext=100.0, ext_i=3)
    ls = TP.leg_start(sd, 3, 0)
    assert ls == (0, 110.5)                                               # the one-sided run of down-close candles
    assert TP.leg_start(sd, 1, 0) is None                                 # fewer than two candles: no leg
    rr = (0, 108.5, True)                                                 # the broken MSS swing
    p = Params(es_pt=1.0, mm_targets=True, mm_anchor="ref", leg_start_target=True)
    out = dict((round(v, 2), k) for v, k in TP.extra_sources(ctx, sd, 6, p, sw, 103.0, 3.0, 108.6, 108.6, [], [], rr))
    assert 117.0 in out                                                   # ref + (ref - ext) = 108.5 + 8.5
    assert 110.5 in out                                                   # the leg start fill target
    p2 = Params(es_pt=1.0, mm_targets=True, mm_anchor="leg")
    assert (round(108.6 + 8.6, 2), "array") in [(round(v, 2), k) for v, k in
                                               TP.extra_sources(ctx, sd, 6, p2, sw, 103.0, 3.0, 108.6, 108.6, [], [], None)]
    p3 = Params(es_pt=1.0, proj_org_k=(1, 2))                             # ORG multiples beyond the far edge
    out3 = [round(v, 2) for v, k in TP.extra_sources(ctx, sd, 6, p3, sw, 103.0, 3.0, 104.0, 104.0, [], [], None)]
    assert out3 == [106.0, 108.0]


def test_rejection_blocks_fix_window_and_wick_test():
    o, h, l, c = [np.array(x, float) for x in zip(*[
        (10, 10.5, 9.9, 10.4), (10.4, 10.9, 10.3, 10.8), (10.8, 12.0, 10.7, 10.9), (10.9, 11.0, 10.2, 10.3),
        (10.3, 10.4, 9.8, 9.9)])]
    assert [z for z in L.rejection_blocks(o, h, l, c, 2) if z.kind == "bear"] == [L.Zone("bear", 12.0, 10.9, 4, 2)]
    # a short wick at the pivot is not a rejection block once the wick test is on
    o2, h2, l2, c2 = o.copy(), h.copy(), l.copy(), c.copy()
    h2[2], o2[2], c2[2], l2[2] = 11.2, 10.2, 10.98, 10.1
    assert [z for z in L.rejection_blocks(o2, h2, l2, c2, 2) if z.kind == "bear"]
    assert not [z for z in L.rejection_blocks(o2, h2, l2, c2, 2, 0.5) if z.kind == "bear"]
    # n = 2 reads +-2 candles (the old fixed +-1 window missed a higher body two candles away)
    o3, h3, l3, c3 = o.copy(), h.copy(), l.copy(), c.copy()
    o3[0], c3[0], h3[0] = 11.2, 11.5, 11.6
    z = [z for z in L.rejection_blocks(o3, h3, l3, c3, 2) if z.kind == "bear"][0]
    assert z.bottom == 11.5
    z1 = [z for z in L.rejection_blocks(o3, h3, l3, c3, 1) if z.kind == "bear"]
    assert not z1 or z1[0].bottom == 10.9                                 # pivot_n = 1: the window stays +-1


def test_pool_body_edge_and_rejection_replace():
    o = np.array([100, 100, 100, 100.5, 100, 100, 100, 100.0]); c = np.array([100, 100, 100, 101, 100, 100, 100, 100.0])
    h = np.array([100.5, 100.5, 100.5, 105.0, 100.5, 100.5, 100.5, 100.5]); l = o - 0.5
    ctx = bar_ctx(None, o, h, l, c)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    p = Params(es_pt=1.0, pool_body_edge=True)
    assert TP.body_edge(ctx, sd, 7, 105.0, p, need_wick=False) == 101.0
    assert TP.body_edge(ctx, sd, 7, 105.0, p, need_wick=True) == 101.0         # wick 4.0 of a 5.5 range
    assert TP.body_edge(ctx, sd, 7, 100.5, Params(es_pt=1.0, rb_min_wick_frac=0.6), need_wick=True) is None          # a tiny wick: not a rejection block
    sw = dict(ext_i=2, ext=99.0)
    assert TP.refine(ctx, sd, 7, p, [(105.0, "pool")], sw, 100.0, 100.5, []) == [(101.0, "rb")]
    p2 = Params(es_pt=1.0, rb_targets="replace", rb_min_wick_frac=0.6)
    assert TP.refine(ctx, sd, 7, p2, [(105.0, "pool"), (100.5, "pool")], sw, 100.0, 100.0, []) == [(100.5, "pool"), (101.0, "rb")]
    assert TP.refine(ctx, sd, 7, Params(es_pt=1.0), [(105.0, "pool")], sw, 100.0, 100.5, []) == [(105.0, "pool")]


# --- L12 / D23 / Ep06.4 SD engine -------------------------------------------------------------------

SDB = [(110, 110.5, 109.0, 109.2), (109.2, 109.4, 107.0, 107.2), (107.2, 107.3, 104.0, 104.2),
       (104.2, 104.3, 100.0, 100.4), (100.4, 104.0, 100.2, 103.8), (103.8, 108.0, 103.6, 107.9),
       (107.9, 112.0, 107.5, 111.5), (111.5, 111.8, 110.0, 110.5), (110.5, 113.0, 110.2, 112.6)]


def _sd_setup(rows=SDB):
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = bar_ctx(None, o, h, l, c)
    ctx.sess = {}
    return ctx, S.Side(1, o, h, l, c, 1, 0.0)


def test_sd_anchors_ranges():
    ctx, sd = _sd_setup()
    sw = dict(ext=100.0, ext_i=3)
    rr = (0, 108.0, True)
    r = lambda a, **kw: {n: (lo, hi) for n, lo, hi in TP.sd_ranges(ctx, sd, 8, Params(es_pt=1.0, sd_anchor=a, **kw), sw, 112.0, rr)}
    assert r("leg") == {"leg": (100.0, 112.0)} and r("sweep_leg") == r("leg")
    assert r("broken") == {"broken": (100.0, 108.0)}
    assert r("downleg") == {"downleg": (100.0, 110.5)}
    f = r("fulcrum")                                                      # first swing high after the extreme, closed through
    assert list(f) == ["fulcrum"] and f["fulcrum"][1] == 112.0
    assert set(r("multi")) >= {"leg", "broken", "downleg"}
    assert TP.sd_ranges(ctx, sd, 8, Params(es_pt=1.0, sd_anchor="london"), sw, 112.0, rr) == []       # no London range
    ctx.sess = {"london": (111.0, 106.0, 5)}
    ctx.t = np.arange(len(ctx.t)) + 10
    assert [x[0] for x in TP.sd_ranges(ctx, sd, 8, Params(es_pt=1.0, sd_anchor="manip"), sw, 112.0, rr)] == ["london"]
    assert TP.sd_ranges(ctx, sd, 4, Params(es_pt=1.0, sd_anchor="broken"), sw, 104.0, rr) == []      # not yet traded through


def test_sd_levels_first_beyond_roles_cluster_align_and_fallback():
    ctx, sd = _sd_setup()
    sw = dict(ext=100.0, ext_i=3)
    rr = (0, 108.0, True)
    pool = [(114.0, "pool")]
    p = Params(es_pt=1.0, sd_targets=True, sd_anchor="broken", sd_levels=(0.5, 1.0, 1.5, 2.0))
    out = TP.sd_levels(ctx, sd, 8, p, sw, 112.0, rr, pool, 103.0, 3.0, [])
    assert out == [(116.0, "sd")]                                      # the first level beyond the pool 114: 108 + 1 x 8
    no_pool = TP.sd_levels(ctx, sd, 8, p, sw, 112.0, rr, [], 103.0, 3.0, [])
    assert no_pool == []                                                  # no pool: nothing (the first build)
    fb = TP.sd_levels(ctx, sd, 8, Params(**{**p.__dict__, "sd_no_pool_fallback": True}), sw, 112.0, rr, [], 103.0, 3.0, [])
    assert fb == [(112.0, "sd")]                                       # the first level paying 1R (108 + 0.5 x 8 = 112)
    pr = Params(**{**p.__dict__, "sd_roles": True, "sd_first_beyond": False})
    kinds = {round(v, 1): k for v, k in TP.sd_levels(ctx, sd, 8, pr, sw, 112.0, rr, pool, 103.0, 3.0, [])}
    assert kinds == {112.0: "sd_half", 116.0: "sd_mm", 120.0: "sd", 124.0: "sd_ext"}
    al = Params(**{**p.__dict__, "sd_first_beyond": False, "sd_align": True, "sd_align_tol_pts": 1.0})
    got = TP.sd_levels(ctx, sd, 8, al, sw, 112.0, rr, [(116.5, "pool")], 103.0, 3.0, [])
    assert [round(v, 1) for v, _ in got] == [116.0]                       # only the level next to a pool / array
    # clusters: two anchors landing within N ticks -> one sd_cluster level at the mean
    multi = Params(es_pt=1.0, sd_targets=True, sd_anchor="multi", sd_levels=(1.0,), sd_first_beyond=False,
                   sd_cluster_ticks=400)
    tags = []
    cl = TP.sd_levels(ctx, sd, 8, multi, sw, 112.0, rr, [], 103.0, 3.0, tags)
    assert cl and all(k == "sd_cluster" for _, k in cl) and "sd_cluster" in tags
    assert TP.sd_active(Params(sd_targets=True, sd_roles=True)) and not TP.sd_active(Params(sd_targets=True))
    assert not TP.sd_active(Params(sd_anchor="broken"))


def test_sd_old_block_matches_new_engine_for_the_leg_anchor():
    ctx, sd = _sd_setup()
    sw = dict(ext=100.0, ext_i=3)
    p = Params(es_pt=1.0, sd_targets=True, sd_levels=(1.0, 1.5, 2.0), sd_first_beyond=False)
    old = S._targets(ctx_for_targets(sd), sd, 8, 112.0, [], p, (100.0, 112.0), 3)
    sdv = [v for v, k in old if v > 114 and k == "sd"]
    assert sdv                                                            # the first build still produces SD levels


def ctx_for_targets(sd):
    n = len(sd.h)
    idx = pd.date_range("2026-06-23 09:30", periods=n, freq="5min", tz=NY)
    c = SimpleNamespace(idx=idx, t=(idx.hour * 60 + idx.minute).values, tf=5, start=0, pd={}, pre_at={}, sess={},
                        or_hl=None, or_end=600, am_hl=None, pw=None, pm_=None, org=[], org_today=False, nwog=[],
                        gaps=None, wick={"upper": 90.0, "lower": 90.0}, start_=0, hist=[], news_dr={}, ipda={},
                        round_step=0.0, adj=None, vac=[], opens={})
    c.o, c.h, c.l, c.c = sd.o, sd.h, sd.l, sd.c
    return c


# --- the rung plan --------------------------------------------------------------------------------

def _plan(keep, p=None, entry=100.0, risk=2.0, extras=(), tg=None, final_T=False, eq_raw=(), lvt=None, sdx=None, ctx=None):
    p = p or Params(es_pt=1.0)
    sd = sdx or side()
    ctx = ctx or fake_ctx(None)
    return TP.plan(ctx, sd, 5, p, entry, risk, entry, keep, final_T, list(extras), tg, list(eq_raw),
                   [] if lvt is None else lvt)


def _order(rp, **kw):
    return dict(rung_plan=rp["rungs"], fracs_fixed=rp["fracs_fixed"], run_local=rp["run_local"],
                final_T=rp["final_T"], bulk=False, **kw)


def test_plan_inert_by_default_and_bump_promotion():
    keep = [(102.0, "array"), (104.0, "pool"), (106.0, "pool")]
    assert _plan(keep) is None                                            # no switch, no bump: the old ladder runs
    p = Params(es_pt=1.0)
    four = [(102.0, "bump"), (103.5, "array"), (104.5, "pool"), (106.0, "pool")]
    rp = _plan(four)
    lv, kd, fr = TP.fill_plan(_order(rp), p.ladder_fracs, p)
    # 3 main slots (50/25/25): the bump is a small protected extra, the mains keep their 3 slots and the last one
    assert lv == [102.0, 103.5, 104.5, 106.0] and kd[0] == "bump"
    assert abs(sum(fr) - 1.0) < 1e-9 and len(lv) == len(fr) == len(kd)
    slow = TP.fill_plan(_order(rp), p.ladder_fracs_slow, p)
    assert len(slow[0]) <= 3 and abs(sum(slow[2]) - 1.0) < 1e-9


def test_plan_run_down_all_pools_and_unit():
    keep = [(101.5, "array"), (102.5, "pool"), (103.5, "pool"), (104.5, "pool"), (105.5, "pool")]
    p = Params(es_pt=1.0, run_down=True)
    rp = _plan(keep, p)
    lv, kd, fr = TP.fill_plan(_order(rp), p.ladder_fracs, p)
    assert len(lv) == 5 and fr[0] == 0.5 and all(abs(f - 0.125) < 1e-9 for f in fr[1:])          # first keeps ladder_fracs[0]
    p2 = Params(es_pt=1.0, ladder_all_pools=True)
    lv, kd, fr = TP.fill_plan(_order(_plan(keep, p2)), p2.ladder_fracs, p2)
    assert kd == ["pool"] * 4 or kd[0] == "pool"                          # only pools (+ the first array is not a pool)
    p3 = Params(es_pt=1.0, ladder_max_levels=4)
    lv, kd, fr = TP.fill_plan(_order(_plan(keep, p3)), p3.ladder_fracs, p3)
    assert len(lv) == 4 and abs(fr[0] - 0.5) < 1e-9
    p4 = Params(es_pt=1.0, mgmt="unit")
    lv, kd, fr = TP.fill_plan(_order(_plan(keep, p4)), p4.ladder_fracs, p4)
    assert fr == [1 / 3] * 3                                              # one equal unit per rung (3 slots)
    p5 = Params(es_pt=1.0, run_down=True, mgmt="unit")
    assert TP.fill_plan(_order(_plan(keep, p5)), p5.ladder_fracs, p5)[2] == [0.2] * 5


def test_plan_extras_halfway_inner_and_shares():
    keep = [(104.0, "pool"), (110.0, "pool")]
    p = Params(es_pt=1.0, halfway_partial=True)
    lt = []
    rp = _plan(keep, p, extras=[(101.5, "sd_half", True), (102.8, "wick_ce", True), (112.0, "inner", False),
                                (104.5, "inner", False)], lvt=lt)
    vs = [(r["v"], r["role"]) for r in rp["rungs"]]
    assert (112.0, "extra") not in vs                                     # beyond the last main: dropped
    assert (104.5, "extra") not in vs and (104.0, "main") in vs           # within 1 pt of a main rung: dropped
    assert (107.0, "extra") in vs                                         # halfway between the first two mains
    assert {"sd_half", "wick_partial", "halfway"} <= set(lt)
    lv, kd, fr = TP.fill_plan(_order(rp), p.ladder_fracs, p)
    extras = [f for f, k in zip(fr, kd) if k in ("sd_half", "wick_ce", "halfway")]
    assert extras == [0.15] * 3 or all(abs(f - 0.2) < 1e-9 for f in extras) or abs(sum(extras) - 0.6) < 1e-9
    assert abs(sum(fr) - 1.0) < 1e-9 and lv == sorted(lv)
    # too close to the entry: not a partial
    rp = _plan(keep, Params(es_pt=1.0, sd_half_partial=True), extras=[(100.5, "sd_half", True)])
    assert all(r["role"] == "main" for r in rp["rungs"])
    # the extras share is capped: three extras of 0.25 -> at most partial_extra_cap in total
    p2 = Params(es_pt=1.0, halfway_partial=True, partial_extra_cap=0.45)
    rp = _plan(keep, p2, extras=[(102.0, "sd_half", True), (103.0, "wick_ce", True)])
    fr = TP.fill_plan(_order(rp), p2.ladder_fracs, p2)[2]
    ex = [f for f, r in zip(fr, rp["rungs"]) if r["role"] == "extra"]
    assert abs(sum(ex) - 0.45) < 1e-9


def test_plan_resistance_capture_runner_order_tgif_and_final_htf():
    sd = side()
    keep = [(102.0, "array"), (104.0, "pool"), (110.0, "pool")]
    # X3f: a low-resistance run is one full pull at the draw
    lt = []
    rp = _plan(keep, Params(es_pt=1.0, resistance_mode="low_full", res_low_max=5), lvt=lt)
    lv, kd, fr = TP.fill_plan(_order(rp), (0.5, 0.25, 0.25), Params(es_pt=1.0))
    assert lv == [110.0] and fr == [1.0] and "res_low" in lt
    # a high-resistance run runs down equity (obstacles >= res_high_min): res_high_min 0 forces it
    rp = _plan(keep + [(111.0, "pool")], Params(es_pt=1.0, resistance_mode="high_run", res_high_min=0))
    assert rp["run_local"] is True
    # X3h: the last rung sits at capture_frac of the run (entry 100 -> 110 at 85% = 108.5); rungs beyond are dropped
    rp = _plan(keep, Params(es_pt=1.0, capture_frac=0.85))
    assert rp["rungs"][-1]["v"] == pytest.approx(108.5)
    # L4 pool_runner_pts: a runner rung beyond the last pool
    rp = _plan(keep, Params(es_pt=1.0, pool_runner_pts=5.0))
    assert rp["rungs"][-1]["v"] == 115.0 and rp["rungs"][-1]["k"] == "runner"
    # Ep04.12 target order: eq pool, then a daily (non-eq) pool, then the VI rung; the bulk fractions sit on the first
    k2 = [(101.0, "array"), (103.0, "pool"), (105.0, "pool"), (108.0, "vi"), (109.0, "array")]
    p = Params(es_pt=1.0, target_order=("eq", "daily", "vi"))
    rp = _plan(k2, p, eq_raw=[102.75])
    assert [r["v"] for r in rp["rungs"]] == [103.0, 105.0, 108.0]
    o = _order(rp)
    o["bulk"] = True
    assert TP.fill_plan(o, p.ladder_fracs, p)[2] == [0.8, 0.1, 0.1]
    # M14.2 / M14.4 TGIF: only the zone levels; with tgif_exits the 25/25/50 split
    tg = dict(levels=[101.0, 102.5, 103.5, 104.5, 105.5], retrace=0.0, stand_down=False)
    pt = Params(es_pt=1.0, tgif_zone=True, tgif_exits=True)
    rp = _plan(keep, pt, tg=tg)
    lv, kd, fr = TP.fill_plan(_order(rp), pt.ladder_fracs, pt)
    assert lv == [102.5, 103.5, 104.5] and fr == [0.25, 0.25, 0.5] and set(kd) == {"exact"}
    assert _plan(keep, Params(es_pt=1.0, tgif_zone=True), tg=dict(levels=[100.5], retrace=0, stand_down=False)) == "skip"
    # Ep03.22 final_htf: the last rung is the nearest 4h / D / W array near edge
    cf = conf([(-1, 118.0, 112.0, np.inf, 0, "4h")], tfs=("4h",))
    rp = TP.plan(fake_ctx(cf), sd, 5, Params(es_pt=1.0, final_htf=True), 100.0, 2.0, 100.0, keep, False, [], None, [], [])
    assert rp["rungs"][-1]["v"] == 111.5 and [r["v"] for r in rp["rungs"]][:2] == [102.0, 104.0]
    # sd_roles: the bulk goes to the -1 SD rung, the smallest piece to the extended one
    ks = [(102.0, "sd_half"), (104.0, "sd_mm"), (106.0, "sd_ext")]
    ps = Params(es_pt=1.0, sd_roles=True)
    fr = TP.fill_plan(_order(_plan(ks, ps)), ps.ladder_fracs, ps)[2]
    assert fr[1] == max(fr) and fr[2] == min(fr)
    # pool_runner / capture / etc leave the plan inert when nothing is set
    assert _plan(keep, Params(es_pt=1.0, pool_runner_pts=0.0)) is None


def test_inner_extras_keep_levels_under_min_rr():
    p = Params(es_pt=1.0, keep_inner_levels=True, min_rr=1.0, inner_min_pts=1.0)
    out = TP.inner_extras(p, 100.0, 4.0, [100.5, 101.5, 103.0, 104.5], ["array"] * 4)
    assert [v for v, k, pr in out] == [101.5, 103.0]
    assert TP.inner_extras(Params(es_pt=1.0), 100.0, 4.0, [101.5], ["array"]) == []


# --- mid-trade partials ---------------------------------------------------------------------------

def test_rung_hit_close_based_sd():
    pos = dict(level_kinds=["pool", "sd_mm"])
    p = Params(es_pt=1.0, sd_close_hit=True, sd_close_window=(600, 720))
    assert TP.rung_hit(pos, 0, 105.0, 106.0, 104.0, 610, 5, p, 0.0) == (True, 105.0)       # a pool: the high
    assert TP.rung_hit(pos, 1, 105.0, 106.0, 104.0, 610, 5, p, 0.0) == (False, 104.0)      # an SD rung needs a close
    assert TP.rung_hit(pos, 1, 105.0, 106.0, 105.5, 610, 5, p, 0.0) == (True, 105.5)       # filled at the close
    assert TP.rung_hit(pos, 1, 105.0, 106.0, 104.0, 540, 5, p, 0.0) == (True, 105.0)       # outside the window: the high
    off = Params(es_pt=1.0)
    assert TP.rung_hit(pos, 1, 105.0, 105.0, 100.0, 610, 5, off, 0.25) == (False, 105.0)    # exit_fill_through still applies


class _Tr:
    def __init__(self, entry=100.0, stop=98.0):
        self.entry, self.stop, self.exits = entry, stop, []


def _pos(**kw):
    d = dict(basis=100.0 * 10, n=10, left=10, fill_i=0, stop=98.0, ext_i=0, best=100.0, level_kinds=[])
    d.update(kw)
    return d


def test_manage_adr_early_wick_read_and_trail_breakaway():
    n = 12
    o = np.full(n, 100.0); h = np.full(n, 100.5); l = np.full(n, 99.5); c = np.full(n, 100.0)
    h[4], c[4] = 112.0, 111.0
    ctx = bar_ctx(None, o, h, l, c)
    ctx.hist = [pd.DataFrame({"open": [100.0], "high": [110.0], "low": [100.0], "close": [105.0]},
                             index=pd.DatetimeIndex(["2026-06-22 09:30"], tz=NY)) for _ in range(5)]
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    ts = ctx.idx[4]
    tr, pos = _Tr(), _pos()
    TP.manage(ctx, sd, pos, tr, 4, ts, Params(es_pt=1.0, adr_early=True, lot=1), None, None, None)
    assert [e[3] for e in tr.exits] == ["adr_early"] and tr.exits[0][2] == 8 and pos["left"] == 2   # 80% off, a runner stays
    TP.manage(ctx, sd, pos, tr, 4, ts, Params(es_pt=1.0, adr_early=True, lot=1), None, None, None)
    assert len(tr.exits) == 1                                              # once
    # the ADR is not reached: nothing
    tr2, pos2 = _Tr(), _pos()
    TP.manage(ctx, sd, pos2, tr2, 2, ctx.idx[2], Params(es_pt=1.0, adr_early=True, lot=1), None, None, None)
    assert tr2.exits == []
    # wick_read: the bar after the wick-CE rung closes back through the CE -> the rest is out
    pos3, tr3 = _pos(wick_chk=(3, 105.0)), _Tr()
    c2 = c.copy(); c2[4] = 104.0
    sd3 = S.Side(1, o, h, l, c2, 1, 0.0)
    TP.manage(ctx, sd3, pos3, tr3, 4, ts, Params(es_pt=1.0, wick_read="exit"), None, None, None)
    assert tr3.exits[0][3] == "wick_revisit" and pos3["left"] == 0
    pos4, tr4 = _pos(wick_chk=(3, 105.0)), _Tr()
    TP.manage(ctx, sd, pos4, tr4, 4, ts, Params(es_pt=1.0, wick_read="exit"), None, None, None)       # continuation
    assert tr4.exits == [] and pos4["wick_chk"] is None
    # trail_breakaway: stop under the breakaway gap once a close is above it; not once it was retraced past its half
    ob = np.array([100, 100, 100, 101, 104, 104.5, 105, 105, 105, 105, 105, 105.0])
    hb = np.array([100.5, 100.5, 102.0, 102, 106, 105, 105.5, 105.5, 105.5, 105.5, 105.5, 105.5])
    lb = np.array([99.5, 99.5, 99.5, 100.2, 103.5, 104, 104.5, 104.5, 104.5, 104.5, 104.5, 104.5])
    cb = ob.copy(); cb[4] = 105.5; cb[5] = 105.0
    sdb = S.Side(1, ob, hb, lb, cb, 1, 0.0)
    assert sdb.gaps and (sdb.gaps[0].bottom, sdb.gaps[0].top) == (102.0, 103.5)
    pos5, tr5 = _pos(ext_i=0), _Tr()
    TP.manage(ctx, sdb, pos5, tr5, 6, ctx.idx[6], Params(es_pt=1.0, trail_breakaway=True), None, None, None)
    assert pos5["stop"] == pytest.approx(102.0 - Params(es_pt=1.0).trail_pad)
    assert TP.breakaway_gap(sdb, 0, 6) is not None
    lb2 = lb.copy(); lb2[5] = 102.5                                            # a retrace to the gap's half (102.75)
    assert TP.breakaway_gap(S.Side(1, ob, hb, lb2, cb, 1, 0.0), 0, 6) is None


def test_manage_smt_bank():
    n = 12
    o = np.full(n, 100.0); c = np.full(n, 100.0)
    h = np.array([100.5, 100.5, 101, 101.5, 102.0, 103.0, 103.0, 103, 103, 103, 103, 103.0]); l = np.full(n, 99.5)
    c[5] = 102.8
    ctx = bar_ctx(None, o, h, l, c)
    ctx.pd = {}
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    hp = np.array([100.5, 100.5, 101, 101.5, 102.0, 101.9, 103.0, 103, 103, 103, 103, 103.0])     # the sister fails at bar 5
    pctx = SimpleNamespace(start=0)
    ps = {1: S.Side(1, o, hp, l, c, 1, 0.0)}
    ppos = pd.Series(np.arange(n), index=ctx.idx)
    p = Params(es_pt=1.0, smt_bank=True, lot=1)
    pos, tr = _pos(fill_i=1), _Tr()
    TP.manage(ctx, sd, pos, tr, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert [e[3] for e in tr.exits] == ["smt_bank"] and tr.exits[0][2] == 5 and pos["left"] == 5 and pos["smt_banked"]
    TP.manage(ctx, sd, pos, tr, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert len(tr.exits) == 1                                                  # once per trade
    # the sister confirms: no bank
    ps2 = {1: S.Side(1, o, np.maximum(hp, h), l, c, 1, 0.0)}
    pos2, tr2 = _pos(fill_i=1), _Tr()
    TP.manage(ctx, sd, pos2, tr2, 5, ctx.idx[5], p, pctx, ps2, ppos)
    assert tr2.exits == []
    # less than smt_bank_min_r in profit: no bank
    pos3, tr3 = _pos(fill_i=1), _Tr(stop=90.0)
    TP.manage(ctx, sd, pos3, tr3, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert tr3.exits == []


def test_capture_ratio():
    sd = S.Side(1, np.zeros(3), np.ones(3), np.zeros(3), np.zeros(3), 1, 0.0)
    tr = SimpleNamespace(exits=[(None, 104.0, 5, "t1"), (None, 108.0, 5, "t2")])
    pos = dict(side=sd, basis=1000.0, n=10, best=110.0)
    assert TP.capture_ratio(pos, tr) == pytest.approx((106.0 - 100.0) / 10.0, abs=1e-4)
    assert TP.capture_ratio(dict(pos, best=100.0), tr) is None
    sh = S.Side(-1, np.zeros(3), np.ones(3), np.zeros(3), np.zeros(3), 1, 0.0)
    trs = SimpleNamespace(exits=[(None, 96.0, 10, "t1")])
    assert TP.capture_ratio(dict(side=sh, basis=-1000.0, n=10, best=-90.0), trs) == pytest.approx(0.4, abs=1e-4)


# --- sources that read the day frame ----------------------------------------------------------------

def test_tf_wicks_and_partial_extras():
    # 15 five-minute bars = three 15m candles; the first has a long upper wick, price has not revisited it
    rows = [(100, 100.5, 99.8, 100.2), (100.2, 106.0, 100.1, 100.4), (100.4, 100.6, 100.0, 100.3)] + \
           [(100.3, 100.9, 100.1, 100.6), (100.6, 101.0, 100.4, 100.5), (100.5, 100.8, 100.3, 100.4)] + \
           [(100.4, 100.7, 100.2, 100.5)] * 3
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = bar_ctx(None, o, h, l, c)
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    p = Params(es_pt=1.0, wick_partials=True, wick_partial_tfs=("15m",), wick_partial_min_pts=2.0)
    w = TP.tf_wicks(ctx, sd, 8, p, ("15m",), 101.0)
    assert len(w) == 1 and w[0][0] == pytest.approx((100.3 + 106.0) / 2) and w[0][2] == "15m"
    ex = TP.partial_extras(ctx, sd, 8, p, dict(ext=99.8, ext_i=0), 101.0, 101.0, 110.0, None, [])
    assert ex == [(pytest.approx(103.15 - 0.5), "wick_ce", True)]
    # outside the path (the last rung is lower than the wick CE): not used
    assert TP.partial_extras(ctx, sd, 8, p, dict(ext=99.8, ext_i=0), 101.0, 101.0, 102.0, None, []) == []
    # two wicks: the longest only
    h2 = h.copy(); h2[4] = 102.8
    sd2 = S.Side(1, o, h2, l, c, 1, 0.0)
    ctx2 = bar_ctx(None, o, h2, l, c)
    w2 = TP.tf_wicks(ctx2, sd2, 8, p, ("15m",), 101.0)
    assert len(w2) == 2
    ex2 = TP.partial_extras(ctx2, sd2, 8, p, dict(ext=99.8, ext_i=0), 101.0, 101.0, 110.0, None, [])
    assert len(ex2) == 1 and ex2[0][0] == pytest.approx(103.15 - 0.5)
    both = Params(es_pt=1.0, wick_partials=True, wick_partial_tfs=("15m",), wick_partial_longest=False)
    assert len(TP.partial_extras(ctx2, sd2, 8, both, dict(ext=99.8, ext_i=0), 101.0, 101.0, 110.0, None, [])) == 2
    # sd_half: the -0.5 SD of the leg is a protected first partial
    ph = Params(es_pt=1.0, sd_half_partial=True)
    ex3 = TP.partial_extras(ctx, sd, 8, ph, dict(ext=99.8, ext_i=0), 101.0, 101.0, 110.0, None, [])
    assert ex3 == [(pytest.approx(101.0 + 0.5 * (101.0 - 99.8) - 0.5), "sd_half", True)]


def test_close_pools_rel_pools_and_draw_pref():
    d = pd.Timestamp("2026-06-22", tz=NY)
    def sess(dt, hi, lo, cl):
        idx = pd.date_range(dt + pd.Timedelta(hours=9.5), periods=3, freq="5min")
        return pd.DataFrame({"open": [cl] * 3, "high": [hi] * 3, "low": [lo] * 3, "close": [cl] * 3}, index=idx)
    hist = [sess(pd.Timestamp("2026-06-1%d" % k, tz=NY), 110.0, 100.0, 104.0 + k) for k in range(5, 9)]
    o = np.full(10, 101.0); h = o + 0.5; l = o - 0.5; c = o.copy()
    ctx = bar_ctx(None, o, h, l, c, hist=hist)
    ctx.day = pd.Timestamp("2026-06-23").date()
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    pools = TP.close_pools(ctx, sd, 9, Params(es_pt=1.0), 101.5)
    vals = sorted(v for v, _ in pools)
    assert vals and all(v > 101.5 for v in vals)
    # a close price re-traded since: realized, not a draw
    h2 = h.copy(); h2[5] = 109.5
    ctx2 = bar_ctx(None, o, h2, l, c, hist=hist); ctx2.day = ctx.day
    assert not [v for v, _ in TP.close_pools(ctx2, S.Side(1, o, h2, l, c, 1, 0.0), 9, Params(es_pt=1.0), 101.5) if v < 109.5]
    # draw_pref: pool_rank prefers the larger (daily) pool, lrlr / clean_eq return preferences among pools
    sw = dict(ext=99.0, ext_i=2)
    ctx3 = bar_ctx(None, o, h, l, c)
    ctx3.pd = {"pdh1": 108.0}
    keep = [(104.25, "pool"), (108.25, "pool")]
    pr = TP.draw_pref(ctx3, sd, 9, Params(es_pt=1.0, pool_rank=True, pool_rank_reach=5.0), 101.0, 2.0, keep, 102.0, sw)
    assert pr and pr[0][0] == 108.25 and pr[0][2] == "pool_rank"
    pr = TP.draw_pref(ctx3, sd, 9, Params(es_pt=1.0, pool_rank=True, pool_rank_reach=1.0), 101.0, 2.0, keep, 102.0, sw)
    assert pr[0][0] == 104.25                                              # out of reach: the nearest stays
    assert TP.draw_pref(ctx3, sd, 9, Params(es_pt=1.0), 101.0, 2.0, keep, 102.0, sw) == []
    # the lock-time ranking (real prices): the daily high outranks a nearer overnight high
    lst = [(2.0, 103.0, "pool", "overnight_high", 1), (6.0, 107.0, "pool", "pdh1", 1)]
    assert TP.lock_rank(ctx3, Params(es_pt=1.0, pool_rank=True), lst, 101.0, True)[0][3] == "pdh1"
    assert TP.lock_rank(ctx3, Params(es_pt=1.0), lst, 101.0, True) == lst


# --- scenarios through run_day (the real engine path) -----------------------------------------------

LOCK108 = {570: dict(draw_up=108.0, draw_up_name="D_fvg", draw_dn=float("nan"), draw_dn_name="")}
BEARISH_15M = conf([(-1, 106.0, 105.0, np.inf, 0)], t0=pd.Timestamp("2026-06-23 02:00", tz=NY))


def scen(label=None, **kw):
    p = Params(**{**BASE, **kw})
    tr, locks, log, _ = run(day(A_ROWS, spike=True), history(), p, LOCK108, conf=BEARISH_15M)
    return tr


def exits(t):
    return [(e[3], round(e[1], 3), e[2]) for e in t.exits]


def test_scenario_speed_bump_partial_then_the_draw():
    tr = scen()
    assert len(tr) == 1
    t = tr[0]
    # a partial at the opposing 15m FVG (105 - 0.5), the rest rides to the locked draw 108 - 0.5
    assert [e[:2] for e in exits(t)] == [("t1", 102.75), ("t2", 104.5), ("t3", 107.5)]
    assert "speed_bump" in t.lv_tags and not t.capped
    assert t.rungs == "102.75:pool:0.38|104.50:bump:0.25|107.50:array:0.38"        # the bump is a small extra
    assert t.capture is not None and 0.3 < t.capture <= 1.0


def test_scenario_cap_mode_is_the_first_build_and_off_switch_is_inert():
    tr = scen(htf_resist_mode="cap", min_draw_pts=0.0)
    t = tr[0]
    assert [e[:2] for e in exits(t)] == [("t1", 102.75), ("t2", 104.5)] and t.capped and t.lock_capped   # nothing beyond the FVG
    assert scen(htf_resist_mode="cap") == []                                 # 4.5 pts of room < the 5-pt minimum
    off = scen(htf_resist_cap=False)[0]
    assert [e[:2] for e in exits(off)] == [("t1", 102.75), ("t2", 107.5)] or off.rungs == ""
    assert off.rungs == "" and "speed_bump" not in off.lv_tags                # no plan, the old ladder
    sp = scen(htf_resist_mode="split")[0]                                    # 15m: speed bump in the split
    assert "speed_bump" in sp.lv_tags


def test_scenario_extra_partials_and_capture():
    t = scen(sd_half_partial=True)[0]
    assert t.rungs.startswith("101.45:sd_half:0.25")                         # -0.5 SD of the 98.5-100.5-ish leg, exempt from min_rr
    assert sum(float(x.split(":")[2]) for x in t.rungs.split("|")) == pytest.approx(1.0, abs=0.02)
    assert len(t.exits) == 4 and "sd_half" in t.lv_tags
    c = scen(capture_frac=0.85)[0]
    assert c.rungs.endswith("106.38:array:0.38") and "capture" in c.lv_tags       # 100 + 0.85 x 7.5
    h = scen(halfway_partial=True, halfway_min_pts=1.0)[0]
    assert "halfway" not in h.rungs                                        # the speed bump already sits at the middle (within 1 pt)
    u = scen(mgmt="unit")[0]
    assert [round(float(x.split(":")[2]), 2) for x in u.rungs.split("|")] == [0.38, 0.25, 0.38]     # bump extra + two equal mains
    keep_bump = scen(resistance_mode="low_full", res_low_max=9)[0]
    assert "bump" in keep_bump.rungs                                        # low_full yields to the #7 speed bump
    lo = scen(resistance_mode="low_full", res_low_max=9, htf_resist_cap=False)[0]
    assert lo.rungs == "107.50:array:1.00" and len(lo.exits) == 1
    rd = scen(run_down=True, ladder_all_pools=True)[0]
    assert len(rd.exits) == 3


def test_scenario_sd_close_hit_and_wick_read_flags_are_inert_without_their_rungs():
    a = scen()[0]
    b = scen(sd_close_hit=True, wick_read="exit", trail_breakaway=False)[0]
    assert exits(a) == exits(b)


# --- no look-ahead (full run vs runs truncated after each entry / exit) ---------------------------------------

SETS = {
    "ladder": dict(run_down=True, ladder_all_pools=True, ladder_max_levels=5, halfway_partial=True, keep_inner_levels=True,
                   capture_frac=0.85, resistance_mode="both", res_low_max=1, res_high_min=2, pool_runner_pts=3.0,
                   mgmt="unit", partial_extra_frac=0.15),
    "wick_sd": dict(wick_partials=True, wick_partial_tfs=("D", "15m", "1h"), wick_partial_min_pts=0.5,
                    sd_targets=True, sd_anchor="multi", sd_roles=True, sd_half_partial=True, sd_cluster_ticks=8,
                    sd_align=True, sd_no_pool_fallback=True, sd_close_hit=True, sd_close_window=(570, 720), sd_levels=(0.5, 1.0, 1.5)),
    "sd_anchors": dict(sd_targets=True, sd_anchor="downleg", sd_no_pool_fallback=True, draw_lock="off", wick_tfs=("15m", "1h"),
                       wick_read="exit"),
    "projections": dict(draw_lock="off", measuring_gap=True, measuring_target=True, measuring_pool_pts=0.0, mm_targets=True,
                        mm_anchor="ref", proj_breaker=True, proj_org_k=(1, 2), proj_ext=(1.27, 1.62), void_targets=True,
                        leg_start_target=True, inter_swing_target=True, adr_target=True, target_ltf_obs=True),
    "blocks": dict(draw_lock="off", matrix_targets=("breaker", "mitigation", "rejection"), breaker_first=True,
                   rb_targets="ladder", rej_targets=True, pool_body_edge=True, rb_min_wick_frac=0.3,
                   target_hygiene=("arrays", "htf", "wick"), skip_exhausted=True, fvg_over_ob=True, fvg_remainder=True,
                   weekly_gap_ce_only=True),
    "draw_prefs": dict(draw_lock="off", pool_rank=True, rel_tfs=(15, 60), draw_below_eq=True, lrlr_max=2,
                       clean_eq_pref=True, eq_pref="rank", close_draw=True, target_order=("eq", "daily", "vi"),
                       final_htf=True, org_reprice=True, tgif=True, tgif_zone=True, tgif_exits=True),
    "mid_trade": dict(adr_early=True, adr_early_frac=0.8, wick_read="exit", trail_breakaway=True, smt_bank=True,
                      smt_bank_min_r=0.0, wick_days=3),
}


def _syn_set(start="2026-04-06", end="2026-05-15", seed=3):
    return B.synthetic(start=start, end=end, tf=5, seed=seed)


@pytest.mark.parametrize("name", list(SETS))
def test_look_ahead_synthetic(name):
    x, y = _syn_set()
    p = Params(**SYN, **SETS[name])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = _no_look_ahead(x, 5, "RW", p, COLS, every=3, partner=y, exits=True, min_trades=1)
    assert len(full) >= 1


def test_look_ahead_synthetic_sb_split_and_news_day():
    x, y = _syn_set(seed=5)
    p = Params(**SYN, sb_model=True, sb_split=True, ladder_news_day=True, draw_lock="off", htf_resist_cap=False)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _no_look_ahead(x, 5, "RW", p, ["entry_time", "entry", "stop", "t1", "shares"], every=2, partner=y, exits=True, min_trades=1)


def test_synthetic_switches_fire():
    """The planner actually changes the engine on the synthetic window (not inert)."""
    x, y = _syn_set("2026-06-01", "2026-07-31", 5)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        run_ = lambda **kw: B.run(x, 5, "RW", Params(**SYN, **kw), y)
        base = run_()
        assert len(base)
        rd = run_(run_down=True, ladder_all_pools=True, ladder_max_levels=5)
        assert rd.rungs.str.len().sum() > 0 and rd.rungs.str.count(r"\|").max() >= 1
        un = run_(mgmt="unit")
        assert un.rungs.str.contains("0.33|0.50").any()
        assert run_(capture_frac=0.5).lv_tags.str.contains("capture").any()
        assert run_(sd_half_partial=True).lv_tags.str.contains("sd_half").any()
        assert run_(resistance_mode="low_full", res_low_max=99).lv_tags.str.contains("res_low").any()


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name,kw", [
    ("default_bump", dict()),
    ("cap_split", dict(htf_resist_mode="split", htf_bump_max=1)),
    ("htf_filters", dict(draw_lock="off", skip_exhausted=True, fvg_over_ob=True, htf_resist_src=("fvg", "ob"),
                          fvg_remainder=True, weekly_gap_ce_only=True, target_hygiene=("htf", "arrays"),
                          final_htf=True, htf_targets_30m=True)),
    ("planner", dict(draw_lock="off", run_down=True, wick_partials=True, wick_partial_tfs=("D", "1h", "4h"),
                     sd_half_partial=True, halfway_partial=True, keep_inner_levels=True, capture_frac=0.9,
                     rel_tfs=(60,), pool_rank=True, close_draw=True, adr_early=True, wick_read="exit",
                     trail_breakaway=True)),
])
def test_look_ahead_es_speed_bump_and_planner(name, kw):
    es = B.load("ES", 5, source="databento")
    df = es[(es.index >= "2024-01-08") & (es.index < "2024-02-09")]
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, **kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = _no_look_ahead(df, 5, "ES", p, COLS, every=3, meta=meta, exits=True, min_trades=2)
    if name == "default_bump":
        assert full.lv_tags.str.contains("speed_bump").any()


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_tgif_and_partner_switches():
    es = B.load("ES", 5, source="databento")
    nq = B.load("NQ", 5, source="databento")
    cut = lambda d: d[(d.index >= "2024-01-08") & (d.index < "2024-02-09")]
    df, pa = cut(es), cut(nq)
    meta = B.load_meta("ES", 5)
    p = Params(**FUT, draw_lock="off", tgif=True, tgif_zone=True, tgif_exits=True, smt_bank=True, smt_bank_min_r=0.0,
               org_reprice=True, adr_target=True, proj_ext=(1.27,), proj_org_k=(1,))
    _no_look_ahead(df, 5, "ES", p, COLS, every=3, meta=meta, exits=True, min_trades=1, partner=pa)


# --- review fixes (2026-10-18): bump share, old fractions, SD kinds, wick_ce, target_order, X3g 80% ---------------

def test_main_fractions_keep_the_old_remainder_rule():
    base = (0.5, 0.25, 0.25)
    assert TP._ext_fracs(base, 3, False) == [0.5, 0.25, 0.25]
    assert TP._ext_fracs(base, 2, False) == [0.5, 0.5]                    # the old engine: the last rung takes the remainder
    assert TP._ext_fracs(base, 1, False) == [1.0]
    assert TP._ext_fracs((0.8, 0.2), 2, False) == pytest.approx([0.8, 0.2])
    assert TP._ext_fracs(base, 4, False) == pytest.approx([0.5, 1 / 6, 1 / 6, 1 / 6])


def test_speed_bump_is_a_small_extra_and_the_draw_keeps_the_majority():
    p = Params(es_pt=1.0)
    keep = [(101.5, "bump"), (104.0, "pool"), (106.0, "array")]
    lv, kd, fr = TP.fill_plan(_order(_plan(keep)), p.ladder_fracs, p)
    assert kd == ["bump", "pool", "array"] and abs(sum(fr) - 1.0) < 1e-9
    assert fr[0] == pytest.approx(p.htf_bump_frac) and fr[0] < max(fr[1:])
    assert fr[1] + fr[2] > 0.7                                            # most of the position stays for the draw side
    two = TP.fill_plan(_order(_plan([(101.5, "bump"), (106.0, "array")])), p.ladder_fracs, p)
    assert two[2] == pytest.approx([0.25, 0.75])                          # draw rung holds the majority
    big = Params(es_pt=1.0, htf_bump_frac=0.5, partial_extra_cap=0.4)
    assert TP.fill_plan(_order(_plan(keep, big)), big.ladder_fracs, big)[2][0] == pytest.approx(0.4)    # capped
    assert TP.bump_fracs([101.5, 104.0, 106.0], [101.5], p.ladder_fracs, p) == pytest.approx([0.25, 0.375, 0.375])
    assert TP.bump_fracs([104.0, 106.0], [], p.ladder_fracs, p) == list(p.ladder_fracs)


def test_sd_levels_carry_an_sd_kind_so_the_close_rule_acts():
    assert "sd" in TP.SD_KINDS
    pos = dict(level_kinds=["sd"])
    p = Params(es_pt=1.0, sd_close_hit=True)
    assert TP.rung_hit(pos, 0, 105.0, 106.0, 104.0, 610, 5, p, 0.0) == (False, 104.0)      # a wick above is not a hit
    assert TP.rung_hit(pos, 0, 105.0, 106.0, 105.5, 610, 5, p, 0.0) == (True, 105.5)


def test_target_order_keeps_the_locked_draw_last_and_low_full_yields_to_extras():
    keep = [(102.0, "vi"), (104.0, "pool_eq"), (106.0, "array")]
    p = Params(es_pt=1.0, target_order=("vi", "eq"))
    rp = _plan(keep, p, final_T=True, risk=1.0)
    assert [r["v"] for r in rp["rungs"]][-1] == 106.0                    # the draw is still the last rung
    rp2 = _plan(keep, p, final_T=False, risk=1.0)
    assert [r["v"] for r in rp2["rungs"]] == [102.0, 104.0]
    lo = Params(es_pt=1.0, resistance_mode="low_full", res_low_max=99)
    rp3 = _plan([(101.5, "bump"), (106.0, "array")], lo)
    assert any(r["k"] == "bump" for r in rp3["rungs"]) and rp3["fracs_fixed"] is None        # the bump is not removed


def test_capture_is_clipped_and_needs_a_real_run():
    sd = S.Side(1, np.zeros(3), np.ones(3), np.zeros(3), np.zeros(3), 1, 0.0)
    pos = dict(side=sd, basis=1000.0, n=10, best=101.0)
    tr = SimpleNamespace(entry=100.0, stop=98.0, exits=[(None, 90.0, 10, "stop")])
    assert TP.capture_ratio(pos, tr) is None                              # best - entry < 1R: no metric
    pos2 = dict(pos, best=110.0)
    assert TP.capture_ratio(pos2, tr) == 0.0                              # a loser reads 0, not -1
    tr2 = SimpleNamespace(entry=100.0, stop=98.0, exits=[(None, 120.0, 10, "t1")])
    assert TP.capture_ratio(pos2, tr2) == 1.0


def test_manage_smt_bank_against_the_trade():
    n = 12
    o = np.full(n, 100.0); c = np.full(n, 100.0)
    h = np.full(n, 100.5); l = np.full(n, 99.5)
    c[5] = 102.0; h[5] = 102.2
    ctx = bar_ctx(None, o, h, l, c)
    ctx.pd = {}
    sd = S.Side(1, o, h, l, c, 1, 0.0)
    lp = l.copy(); lp[5] = 98.9                                           # the sister prints a new low, we hold ours
    pctx = SimpleNamespace(start=0)
    ps = {1: S.Side(1, o, h, lp, c, 1, 0.0)}
    ppos = pd.Series(np.arange(n), index=ctx.idx)
    p = Params(es_pt=1.0, smt_bank_against_frac=0.8, lot=1)
    pos, tr = _pos(fill_i=1), _Tr()
    TP.manage(ctx, sd, pos, tr, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert [e[3] for e in tr.exits] == ["smt_bank2"] and tr.exits[0][2] == 8 and pos["left"] == 2
    TP.manage(ctx, sd, pos, tr, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert len(tr.exits) == 1
    same = {1: S.Side(1, o, h, l, c, 1, 0.0)}                            # the sister holds: nothing
    pos2, tr2 = _pos(fill_i=1), _Tr()
    TP.manage(ctx, sd, pos2, tr2, 5, ctx.idx[5], p, pctx, same, ppos)
    assert tr2.exits == []
    pos3, tr3 = _pos(fill_i=1), _Tr()                                    # we broke our own low too: not a divergence
    TP.manage(ctx, S.Side(1, o, h, lp, c, 1, 0.0), pos3, tr3, 5, ctx.idx[5], p, pctx, ps, ppos)
    assert tr3.exits == []


def test_look_ahead_synthetic_bump_extras_and_smt_against():
    x, y = _syn_set(seed=4)
    p = Params(**SYN, smt_bank_against_frac=0.8, smt_bank_min_r=0.0, htf_bump_max=2, htf_bump_frac=0.3)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _no_look_ahead(x, 5, "RW", p, COLS, every=3, partner=y, exits=True, min_trades=1)


@pytest.mark.skipif(not ES, reason="no ES data")
class TestEsReviewFixes:
    def _es(self, a="2024-01-08", b="2024-02-09"):
        es = B.load("ES", 5, source="databento")
        nq = B.load("NQ", 5, source="databento")
        cut = lambda d: d[(d.index >= a) & (d.index < b)]
        return cut(es), cut(nq), B.load_meta("ES", 5)

    def _run(self, window=(), **kw):
        df, pa, meta = self._es(*window)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return B.run(df, 5, "ES", Params(**FUT, **kw), pa, meta=meta)

    def test_default_bump_leaves_the_draw_the_majority(self):
        t = self._run()
        b = t[t.rungs.str.contains("bump")]
        assert len(b)
        for rg in b.rungs:
            sh = [(x.split(":")[1], float(x.split(":")[2])) for x in rg.split("|")]
            assert sum(s for k, s in sh if k != "bump") > sum(s for k, s in sh if k == "bump")
            assert sum(1 for k, _ in sh if k == "bump") <= 1

    def test_sd_close_hit_changes_exits(self):
        kw = dict(draw_lock="off", sd_targets=True, sd_anchor="broken", sd_first_beyond=False, sd_levels=(0.5, 1.0, 1.5, 2.0))
        win = ("2024-06-03", "2024-06-25")                 # holds a trade whose SD rung (kind "sd") is only reached by a wick
        a, b = self._run(window=win, **kw), self._run(window=win, sd_close_hit=True, **kw)
        assert a.rungs.str.contains(":sd:").any()
        assert len(a) == len(b) and (a.net.round(2).tolist() != b.net.round(2).tolist())

    def test_sb_and_ma_deuce_speed_bump_paths(self):
        df, pa, meta = self._es()
        for kw in (dict(sb_model=True), dict(ma_deuce=True)):
            p = Params(**FUT, **kw)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                full = _no_look_ahead(df, 5, "ES", p, ["entry_time", "entry", "stop", "t1", "shares"], every=3, meta=meta,
                                      exits=True, min_trades=1)
            assert len(full) >= 1 and full.lv_tags.str.contains("speed_bump").any(), kw


# --- each of these switches changes real trades (not inert), one at a time -------------------------------------

FIRES = {
    "wick_tfs": dict(wick_tfs=("1h", "4h")),
    "org_reprice": dict(org_reprice=True),
    "smt_bank": dict(smt_bank=True, smt_bank_min_r=0.0),
    "smt_against80": dict(smt_bank_against_frac=0.8, smt_bank_min_r=0.0),
    "trail_breakaway": dict(trail_breakaway=True),
    "measuring": dict(measuring_gap=True, measuring_target=True, measuring_pool_pts=0.0),
    "wick_read": dict(wick_tfs=("1h", "4h"), wick_read="exit"),
}


@pytest.fixture(scope="module")
def es_fire_base():
    es = B.load("ES", 5, source="databento")
    nq = B.load("NQ", 5, source="databento")
    cut = lambda d: d[(d.index >= "2024-01-08") & (d.index < "2024-03-15")]
    df, pa, meta = cut(es), cut(nq), B.load_meta("ES", 5)

    def run(**kw):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return B.run(df, 5, "ES", Params(**FUT, draw_lock="off", **kw), pa, meta=meta)
    return run, run()


_sig = lambda t: (t.rungs.tolist(), t.lv_tags.tolist(), t.exit_reason.tolist(), t.net.round(1).tolist())


@pytest.mark.skipif(not ES, reason="no ES data")
@pytest.mark.parametrize("name", list(FIRES))
def test_switch_changes_real_trades(name, es_fire_base):
    run, base = es_fire_base
    assert len(base) >= 10
    assert _sig(run(**FIRES[name])) != _sig(base), name
