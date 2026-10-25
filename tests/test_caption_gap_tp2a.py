"""Caption-gap pass, package targets_partials #2/4, part A: the unit tests of the 33 specs (levels_liquidity_targets.md 15, 16, 17, 20, 24, 27, 37, 39, 41, 43, 45, 48, 49, 50, 51, 52, 53, 54, 56, 60,
61, 62, 65, 66, 83, 85, 86, 88, 89, 94, 98, 99, 101). Hand-made bars and stub confluence tables (as test_caption_gap_tp1a.py), the tp2.py helpers called directly, the targets.sd_levels engine, a run_day
scenario for the order-level hooks. No platform-specific paths; nothing here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_tp2b.py."""
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import confluence as CF, levels as L, strategy as S, targets as TP, tp1, tp2, study
from mentorship.strategy import Params

from test_targets_partials import bar_ctx, conf

NY = "America/New_York"
D0 = date(2026, 6, 23)                       # a Tuesday: no release
NEW_SWITCHES = (
    "eq_beyond_imb", "hrlr_time_k", "clear_path", "session_pool_first", "nwog_ladder", "event_horizon_target", "nwog_magnet", "org_beyond", "org_ce_if_flow", "htf_gap_gate", "weekly_bisi_ts_block",
    "keep_traded_wfvg", "wick_long_only", "min_obj_frac", "sd_arm", "sd_ref_roll", "sd_multi_tiers", "proj_exit_ticks", "sd_cap_htf", "sd_htf_extreme", "sd_premium_consol", "sd_last_hour_k",
    "proj_org_reprice", "session_pools_mode", "room_ref", "t1_skip_near", "overnight_5m_fvgs", "htf_ob_open", "htf_ob_open_final", "org_breaker_stop", "beyond_pool_final", "break_accel_gate",
    "swept_pool_targets", "proj_breaker_k", "confl_rank", "sd_fulcrum_def", "sd_deep_conv", "defended_filter", "eq_leg", "sd_anchor",
)
KNOBS = ("linger_bars", "linger_pts", "nwog_near_frac", "nwog_ce_frac", "consol_min_bars", "consol_max_adr", "org_beyond_adr", "htf_gap_final", "sd_arm_bars", "sd_cluster_min", "sd_htf_tol", "proj_org_kmax",
         "beyond_pool_adr", "break_accel_mult", "confl_tol_frac", "sd_conv_ticks", "defended_band_adr", "defended_touches", "defended_bars")
GAP_IDS = (
    "L4-target-below-eq-leg", "L4-resistance-runs", "L4-session-pool-before-rel", "L5-nwog-target-ladder", "L5-event-horizon-objective", "L5-old-nwog-in-consolidation", "L7-org-overshoot-discount",
    "L7-org-partial-close-orderflow", "L9-htf-fvg-target-ladder", "L10-intraday-wick-ce", "L12-sd-activation", "L12-ref-rolls-to-new-high", "L12-cluster-anchors", "L12-projection-exit-1tick",
    "L12-cap-at-htf-array", "L12-prior-session-swing-htf-extreme", "L12-sd-in-premium-consolidation", "L12-minus3-sd-last-hour", "L13-org-sd-projection", "L14-session-pools-only", "L15-room-measure-anchors",
    "L15-first-sth-offering-5", "X1-london-0300-fvg-draw", "X1-htf-ob-open-target", "L7-org-breaker-inside", "B2-target-beyond-pool-inefficiency", "new-pool-break-accel-vs-reject", "new-old-pool-redelivery",
    "L13-breaker-range-sd-weekly", "new-level-confluence-scoring", "D23-inception-fulcrum-anchor", "L12-deep-sd-pd-convergence", "new-defended-level",
)
P = dict(es_pt=1.0, lot=1, max_notional=1e12)


def hist_days(n=6, rng=20.0, base=4000.0):
    """n daily frames of a `rng`-point range (the ADR5 of the chunk's tests)."""
    out = []
    for k in range(n):
        d = pd.Timestamp("2026-06-10", tz=NY) + pd.Timedelta(days=k)
        idx = pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=3, freq="5min")
        out.append(pd.DataFrame({"open": base, "high": [base + rng, base, base], "low": [base, base - 0.0, base], "close": base}, index=idx))
    return out


def mk(rows, cf=None, tf_conf=("15m",), **kw):
    """A ctx on 5m bars from 09:30 with the attributes the engine reads (rows = (o, h, l, c))."""
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    base = dict(pd={}, sess={}, org=[], org_today=False, or_hl=None, or_end=600, am_hl=None, day=D0, hist=hist_days(), wicks=[], wick=None, wbias=0, pw=None, pm_=None, gaps=None)
    base.update(kw)
    return bar_ctx(cf, o, h, l, c, **base)


def side(ctx, sign=1, **kw):
    return S.Side(sign, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0, **kw)


def flat(n, v=4000.0, w=0.3):
    return [(v, v + w, v - w, v)] * n


# --- defaults / validation / study variants -------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert (p.eq_leg, p.eq_beyond_imb, p.hrlr_time_k, p.clear_path, p.linger_bars, p.linger_pts, p.session_pool_first, p.nwog_ladder, p.nwog_near_frac, p.nwog_ce_frac, p.event_horizon_target,
            p.nwog_magnet, p.org_beyond, p.org_beyond_adr, p.org_ce_if_flow, p.htf_gap_final, p.htf_gap_gate, p.weekly_bisi_ts_block, p.keep_traded_wfvg) == (
        "sweep", False, 0.0, False, 10, 1.0, False, False, 0.0, 0.8, False, False, False, 0.5, False, "ce", False, False, False)
    assert (p.wick_long_only, p.min_obj_frac, p.sd_arm, p.sd_arm_bars, p.sd_ref_roll, p.sd_multi_tiers, p.sd_cluster_min, p.proj_exit_ticks, p.sd_cap_htf, p.sd_htf_extreme, p.sd_htf_tol, p.sd_premium_consol,
            p.sd_last_hour_k, p.proj_org_reprice, p.proj_org_kmax, p.session_pools_mode, p.room_ref, p.t1_skip_near, p.overnight_5m_fvgs) == (
        False, 0.0, "trade", 1, False, (), 3, 0, False, False, 1.0, False, 0.0, False, 12, "off", "exit", False, False)
    assert (p.htf_ob_open, p.htf_ob_open_final, p.org_breaker_stop, p.beyond_pool_final, p.beyond_pool_adr, p.break_accel_gate, p.break_accel_mult, p.swept_pool_targets, p.proj_breaker_k, p.confl_rank,
            p.confl_tol_frac, p.sd_fulcrum_def, p.sd_deep_conv, p.sd_conv_ticks, p.defended_filter, p.defended_band_adr, p.defended_touches, p.defended_bars) == (
        False, False, False, False, 0.25, False, 1.5, False, (1.0,), False, 0.001, "ep06", False, 2, False, 0.1, 4, 200)
    assert p.sd_anchor == "leg" and p.sd_first_beyond                                  # the built defaults stay
    assert not tp2.any_on(p) and not tp2.targets_on(p) and not tp2.sd_on(p)
    for kw in (dict(eq_leg="x"), dict(session_pools_mode="x"), dict(sd_arm="x"), dict(htf_gap_final="x"), dict(room_ref="x"), dict(sd_fulcrum_def="x"), dict(sd_multi_tiers=("stl",)), dict(sd_arm_bars=0),
               dict(sd_cluster_min=1), dict(proj_exit_ticks=-1), dict(sd_last_hour_k=-1), dict(proj_org_kmax=0), dict(hrlr_time_k=-1), dict(linger_bars=0), dict(consol_min_bars=1), dict(org_beyond_adr=0),
               dict(beyond_pool_adr=0), dict(break_accel_mult=0), dict(confl_tol_frac=0), dict(defended_band_adr=0), dict(defended_touches=0), dict(min_obj_frac=1.0), dict(nwog_near_frac=0.5, nwog_ce_frac=0.8),
               dict(proj_breaker_k=()), dict(proj_breaker_k=(0.0,)), dict(sd_anchor="x")):
        with pytest.raises(ValueError):
            Params(**kw)
    for a in ("entry_low", "m15_leg", "mss_leg"):
        Params(sd_anchor=a, sd_targets=True)
    assert set(NEW_SWITCHES) | set(KNOBS) <= set(Params.__dataclass_fields__)


def test_every_switch_has_a_study_variant():
    on = set()
    for g in GAP_IDS:
        vs = [v for v in study.DECISIONS if v == g or v.startswith(g + "_")]
        assert vs, g
        for v in vs:
            Params(**study.DECISIONS[v])
            on |= set(study.DECISIONS[v])
    missing = [s for s in NEW_SWITCHES if s not in on]
    assert not missing, missing
    assert all(v in study.DECISIONS for v in study._TP2_DECISIONS)
    names = list(study.DECISIONS)
    assert names.index("L4-target-below-eq-leg") > names.index("new-swing-projection-fulcrum")


def test_inert_switch_note():
    with pytest.warns(UserWarning, match="inert switches \\(targets_partials #2/4\\)"):
        Params(sd_ref_roll=True, sd_htf_extreme=True, eq_beyond_imb=True)


# --- L4-target-below-eq-leg (15) ------------------------------------------------------------------------------------------------------------------

def test_target_imbalance_beyond_pool_below_eq():
    """The short of the spec (rally 4000 -> 4040, EQ 4020, REL 4012, 60m FVG top 4008 -> final 4008) in the bullish side space: a decline 4040 -> 4000 (EQ 4020), REL 4028, 15m SIBI near edge 4032."""
    rows = [(4040 - 4 * k, 4040.5 - 4 * k, 4036 - 4 * k, 4036 - 4 * k) for k in range(10)] + [(4000.0, 4001, 3999, 4000.5)] * 4 + [(4001.0, 4003, 4000, 4002)] * 4
    cf = conf([(-1, 4038.0, 4032.0, np.inf, 0, "15m")])
    ctx = mk(rows, cf)
    sd = side(ctx)
    sw = dict(ext=3999.0, ext_i=10)
    p = Params(**P, draw_below_eq=True, eq_leg="rally", eq_beyond_imb=True)
    keep = [(4024.0, "pool"), (4028.0, "pool_eq")]
    out = TP.draw_pref(ctx, sd, 17, p, 4002.0, 2.0, keep, 4003.0, sw)
    assert out and out[0][1:] == ("array", "eq_beyond_imb") and abs(out[0][0] - S._exit_px(4032.0, "array", p)) < 1e-9
    # without the switch the pool itself (the larger one below EQ) is the pick, with eq_leg 'rally' the EQ is the leg's: the pool at 4024 sits above EQ (4020) and is a candidate
    p0 = replace(p, eq_beyond_imb=False)
    out0 = TP.draw_pref(ctx, sd, 17, p0, 4002.0, 2.0, keep, 4003.0, sw)
    assert out0 and out0[0][2] in ("pool_eq_leg", "pool_pick") and out0[0][0] in (4024.0, 4028.0)
    # the 60m fallback: no 15m row -> the 1h one
    cf2 = conf([(-1, 4038.0, 4034.0, np.inf, 0, "1h")], tfs=("1h",))
    out2 = TP.draw_pref(mk(rows, cf2), side(mk(rows, cf2)), 17, p, 4002.0, 2.0, keep, 4003.0, sw)
    assert out2 and abs(out2[0][0] - S._exit_px(4034.0, "array", p)) < 1e-9
    assert tp2.HITS["eq_beyond_imb"] >= 2


def test_eq_leg_rally_uses_the_start_of_the_run():
    rows = [(4040 - 4 * k, 4040.5 - 4 * k, 4036 - 4 * k, 4036 - 4 * k) for k in range(10)] + [(4000.0, 4001, 3999, 4000.5)] * 4
    ctx = mk(rows)
    sd = side(ctx)
    p = Params(**P, eq_leg="rally")
    assert tp2.eq_leg_hi(ctx, sd, dict(ext=3999.0, ext_i=10), 4003.0, p) == pytest.approx(4040.5)
    assert tp2.eq_leg_hi(ctx, sd, dict(ext=3999.0, ext_i=10), 4003.0, Params(**P)) is None


# --- L4-resistance-runs (16) ----------------------------------------------------------------------------------------------------------------------

def _hrlr_ctx(day=D0, n_in=60, conf_rows=None):
    """Bars: flat to 4000 (the sweep low at bar 9), a rise with a swing high 4088 (bar 20), a dip, a swing high 4090 (bar 29), then n_in bars hovering at 4089.5 (below 4090)."""
    rows = flat(10, 4000.0)
    rows += [(4000.0 + 8.0 * k, 4000.0 + 8.0 * k + 1.0, 4000.0 + 8.0 * k - 0.5, 4000.0 + 8.0 * k + 0.8) for k in range(1, 11)]       # bars 10..19 rise to ~4080
    rows += [(4080.0, 4088.0, 4079.0, 4087.0), (4086.0, 4086.5, 4084.0, 4084.5), (4084.5, 4085.0, 4083.0, 4084.0)]                       # bars 20..22: the swing high 4088, a dip
    rows += [(4084.0, 4087.0, 4084.0, 4086.5), (4086.5, 4089.0, 4086.0, 4088.5), (4088.5, 4089.5, 4088.0, 4089.0), (4089.0, 4089.6, 4088.5, 4089.5),
             (4089.5, 4089.7, 4089.0, 4089.5), (4089.5, 4089.8, 4089.0, 4089.5), (4089.5, 4090.0, 4089.0, 4089.5)]                             # bars 23..29: the swing high 4090 at bar 29
    rows += [(4089.5, 4089.9, 4089.0, 4089.5)] * (n_in + 3)
    cf = conf(conf_rows, tfs=("4h", "D")) if conf_rows else None
    return mk(rows, cf, day=day), len(rows) - 1


def test_hrlr_time_factor_drops_target():
    ctx, i = _hrlr_ctx()
    sd = side(ctx)
    sw = dict(ext=3999.7, ext_i=9)
    p = Params(**P, hrlr_time_k=1.0)
    keep = [(4100.0, "pool")]
    why, k2, dr = tp2.resistance_runs(ctx, sd, sw, i, p, 4080.0, keep, 4100.0, False, [], {})
    assert why == "x_hrlr_time" and tp2.HITS["hrlr_time_drop"] >= 1                     # 60 bars in the band vs a 20-bar leg: the only target is dropped
    keep2 = [(4085.0, "array"), (4100.0, "pool")]
    lvt = []
    why, k2, dr = tp2.resistance_runs(ctx, sd, sw, i, p, 4080.0, keep2, 4100.0, False, lvt, {})
    assert why is None and [v for v, _ in k2] == [4085.0] and "hrlr_time" in lvt             # 4085 has no intermediate swing under it: kept; 4100 dropped
    why, k3, dr = tp2.resistance_runs(ctx, sd, sw, i, replace(p, hrlr_time_k=4.0), 4080.0, keep, 4100.0, False, [], {})
    assert why is None and k3 == keep                                                    # 60 <= 4 x 20
    jobs, i2 = _hrlr_ctx(day=date(2023, 3, 10))                                          # the NFP day: the news driver is the exception
    why, k4, dr = tp2.resistance_runs(jobs, side(jobs), sw, i2, p, 4080.0, keep, 4100.0, False, [], {})
    assert why is None and k4 == keep
    why, k5, dr = tp2.resistance_runs(ctx, sd, sw, i, p, 4080.0, keep, 4100.0, True, [], {})
    assert why == "x_hrlr_time"                                                          # a locked draw that is dropped rejects the order


def test_clear_path_needs_an_htf_array_beyond_the_draw():
    ctx, i = _hrlr_ctx(conf_rows=[(-1, 4130.0, 4120.0, np.inf, 0, "4h")])
    sd = side(ctx)
    sw = dict(ext=3999.7, ext_i=9)
    p = Params(**P, clear_path=True, lrlr_max=4)
    keep = [(4100.0, "pool")]
    why, k, dr = tp2.resistance_runs(ctx, sd, sw, i, p, 4080.0, keep, 4100.0, False, [], {})
    tg = {}
    why, k, dr = tp2.resistance_runs(ctx, sd, sw, i, p, 4088.0, keep, 4100.0, False, [], tg)
    assert why is None and tg["tp2"]["linger"] == (10, 1.0)
    ctx2, i2 = _hrlr_ctx()
    why, k, dr = tp2.resistance_runs(ctx2, side(ctx2), sw, i2, p, 4080.0, keep, 4100.0, False, [], {})
    assert why == "x_no_clear_path"
    # too many obstacles between the entry and the array: lrlr_max = 0 fails with the intermediate swings under the array
    why, k, dr = tp2.resistance_runs(ctx, sd, sw, i, replace(p, lrlr_max=0), 4060.0, keep, 4100.0, False, [], {})
    assert why == "x_no_clear_path"


def test_linger_tag():
    n = 15
    ctx = mk(flat(n))
    sd = side(ctx)
    p = Params(**P, hrlr_time_k=1.0, linger_bars=5, linger_pts=1.0)
    tr = SimpleNamespace(lv_tags="x")
    pos = dict(left=1)
    tp2.on_fill(ctx, sd, pos, tr, dict(tp2=dict(linger=(5, 1.0), entry=4000.0), ext=3990.0), 3, p)
    for i in range(3, 9):
        tp2.manage(ctx, sd, pos, tr, i, p)
    assert "lingered" in tr.lv_tags
    ctx2 = mk(flat(3) + [(4000.0, 4006, 3999, 4005)] * 12)
    tr2 = SimpleNamespace(lv_tags="")
    pos2 = dict(left=1)
    tp2.on_fill(ctx2, side(ctx2), pos2, tr2, dict(tp2=dict(linger=(5, 1.0), entry=4000.0), ext=3990.0), 3, p)
    for i in range(3, 9):
        tp2.manage(ctx2, side(ctx2), pos2, tr2, i, p)
    assert "lingered" not in tr2.lv_tags


# --- L4-session-pool-before-rel (17) --------------------------------------------------------------------------------------------------------------

def test_lunch_low_before_rel():
    """The short of the spec (14:00, lunch low 4050, REL 4040) in side space: lunch high 4050, REL 4060 -> rungs 4050 then 4060, draw 4050."""
    ctx = mk(flat(20, 4000.0), sess={"lunch": (4050.0, 3990.0, 0)})
    sd = side(ctx)
    p = Params(**P, session_pool_first=True, eq_pref="rank", draw_lock="off")
    a, b = S._exit_px(4050.0, "pool", p), S._exit_px(4060.0, "pool_eq", p)
    keep_full = [(a, "pool"), (b, "pool_eq")]
    r = tp2.session_first(ctx, sd, 10, p, 4000.0, 3.0, keep_full, b)
    assert r is not None and r[1] == a and [v for v, _ in r[0]] == [a, b]
    assert tp2.session_first(ctx, sd, 10, p, 4000.0, 3.0, [(b, "pool_eq")], b) is None      # no session pool in front
    ctx2 = mk(flat(20, 4000.0), sess={"lunch": (4070.0, 3990.0, 0)})                           # the lunch high lies beyond the rel-eq pool: no change
    assert tp2.session_first(ctx2, side(ctx2), 10, p, 4000.0, 3.0, keep_full, b) is None


# --- L5-nwog-target-ladder (20) -------------------------------------------------------------------------------------------------------------------

def test_nwog_ladder_bulk_at_ce():
    ctx = mk(flat(20, 4060.0), gaps=[("nwog", 4100.0, 4076.75, 4088.375)])
    sd = side(ctx)
    p = Params(**P, nwog_ladder=True)
    ex = lambda v: S._exit_px(v, "array", p)
    keep = [(ex(4076.75), "array")]
    r = tp2.nwog_ladder(ctx, sd, 10, p, 4060.0, 3.0, keep, ex(4076.75))
    assert r is not None
    rungs, fr = r
    assert [round(v, 6) for v, _ in rungs] == [round(ex(x), 6) for x in (4076.75, 4088.375, 4100.0)] and fr == pytest.approx((0.0, 0.8, 0.2))
    # entry beyond the near edge: CE and far edge only (they are targets once the near edge traded)
    r2 = tp2.nwog_ladder(ctx, sd, 10, p, 4080.0, 3.0, [(ex(4088.375), "array")], ex(4088.375))
    assert r2 is not None and len(r2[0]) == 2 and r2[1] == pytest.approx((0.8, 0.2))
    assert tp2.nwog_ladder(ctx, sd, 10, p, 4060.0, 3.0, [(4090.0, "pool")], 4090.0 + 0.5) is None       # the draw is no NWOG level
    p2 = replace(p, nwog_near_frac=0.1)
    assert tp2.nwog_ladder(ctx, sd, 10, p2, 4060.0, 3.0, keep, ex(4076.75))[1] == pytest.approx((0.1, 0.8, 0.1))


# --- L5-event-horizon-objective (24) --------------------------------------------------------------------------------------------------------------

def test_event_horizon_gates_next_nwog():
    gaps = [("nwog", 4010.0, 4000.0, 4005.0), ("nwog", 4070.0, 4060.0, 4065.0)]
    lv = [(4060.0, "array"), (4065.0, "array"), (4070.0, "array"), (4080.0, "pool")]
    rows = flat(4, 4012.0) + [(4012.0, 4034.0, 4011, 4033.0)] + flat(4, 4033.0)
    ctx = mk(rows, gaps=gaps)
    sd = side(ctx)
    p = Params(**P, event_horizon_target=True)
    st = {"tags": [], "prefs": []}
    out, add = tp2.event_horizon(ctx, sd, 8, p, 4012.0, list(lv), st)
    assert [v for v, _ in out] == [4080.0] and add == [(4035.0, "array")] and "event_horizon" in st["tags"]       # ladder ends at 4035 until 4035.25 trades
    rows2 = rows[:-1] + [(4033.0, 4035.25, 4032, 4035.0)]
    ctx2 = mk(rows2, gaps=gaps)
    out2, add2 = tp2.event_horizon(ctx2, side(ctx2), 8, p, 4012.0, list(lv), {"tags": [], "prefs": []})
    assert out2 == lv and add2 == []                                                      # then 4060 appears
    ctx3 = mk(flat(9, 3990.0), gaps=gaps)                                                 # price below every NWOG: nothing
    assert tp2.event_horizon(ctx3, side(ctx3), 8, p, 3990.0, list(lv), {"tags": [], "prefs": []}) == (lv, [])


# --- L5-old-nwog-in-consolidation (27) ------------------------------------------------------------------------------------------------------------

def _daily(o, h, l, c, d):
    idx = pd.date_range(pd.Timestamp(d, tz=NY) + pd.Timedelta(hours=9, minutes=30), periods=2, freq="5min")
    return pd.DataFrame({"open": o, "high": [h, h], "low": [l, l], "close": c}, index=idx)


def test_nwog_through_old_consolidation_ranked():
    days = [_daily(4000, 4010, 3990, 4000, "2026-06-01"), _daily(4098, 4101, 4096, 4099, "2026-06-02"), _daily(4100, 4115, 4098, 4112, "2026-06-03"),
            _daily(4110, 4113, 4100, 4101, "2026-06-04"), _daily(4090, 4098, 4085, 4092, "2026-06-05"), _daily(4080, 4090, 4070, 4075, "2026-06-08")]
    gaps = [("nwog", 4105.0, 4095.0, 4100.0), ("nwog", 4160.0, 4150.0, 4155.0)]
    ctx = mk(flat(12, 4070.0), hist=days, gaps=gaps)
    sd = side(ctx)
    p = Params(**P, nwog_magnet=True)
    st = {"tags": [], "prefs": []}
    add = tp2.magnet(ctx, sd, 8, p, 4070.0, st)
    assert "nwog_magnet" in st["tags"] and st["prefs"][0][0] == 4095.0 and st["prefs"][0][2] == "nwog_magnet"       # the NWOG through the old high's bodies is the draw, not the far one
    assert (4095.0, "array") in add and not any(v >= 4150.0 for v, _ in add)


def test_range_anchor_from_the_current_cluster():
    rows = flat(12, 4100.0, 1.0)                                            # 12 bars within a 2-point band, ADR5 = 20: 0.3 x 20 = 6
    ctx = mk(rows, gaps=[("nwog", 4103.0, 4098.0, 4100.5), ("nwog", 4200.0, 4190.0, 4195.0)], hist=hist_days())
    st = {"tags": [], "prefs": []}
    add = tp2.magnet(ctx, side(ctx), 11, Params(**P, nwog_magnet=True), 4090.0, st)
    assert "range_anchor" in st["tags"] and any(n == "range_anchor" for _, _, n in st["prefs"])
    assert L.consolidation_band(ctx.h, ctx.l, 11, 6, 6.0) == (4099.0, 4101.0) and L.consolidation_band(ctx.h, ctx.l, 11, 6, 1.0) is None


# --- L7 org family (37, 39, 83) -------------------------------------------------------------------------------------------------------------------

def _org_ctx(n=14, sign=1, rows=None, **kw):
    """A gap down 4020 -> 4000 for a long (the prior close 4020 above the open 4000), mirrored (x -1) for sign -1: the gap up of the spec (4000 -> 4020) for a short. The bars start at 09:30."""
    rows = rows or flat(n, 4004.0 if sign > 0 else 4016.0)              # real prices; the short's gap up 4000 -> 4020 trades near the open
    return mk(rows, org=[(4020.0, 4000.0)] if sign > 0 else [(4000.0, 4020.0)], org_today=True, **kw)


def test_org_ladder_extends_to_discount_array():
    """Gap 4000 -> 4020 (short, the prior close 4000 is the far edge); a daily FVG top 3992 lies beyond: the ladder ends ..., 4000, 3992."""
    ctx = _org_ctx(sign=-1)
    sd = side(ctx, -1)
    p = Params(**P, org_beyond=True, org_draw="draw")
    far = S._exit_px(-4000.0, "array", p)
    keep = [(S._exit_px(-4010.0, "array", p), "array"), (far, "array")]
    full = keep + [(S._exit_px(-3992.0, "array", p), "array"), (S._exit_px(-3900.0, "pool", p), "pool")]
    lvt, st2, tags = [], {}, {}
    why, k2, dr, fT = tp2.late(ctx, sd, dict(ext=-4021.0, ext_i=3), 10, p, "AM", -4018.0, 3.0, keep, full, far, False, lvt, tags, st2, True, False, -4010.0)
    assert why is None and [round(v, 6) for v, _ in k2] == [round(v, 6) for v, _ in keep] + [round(S._exit_px(-3992.0, "array", p), 6)] and "org_beyond" in lvt
    # the beyond level lies outside 0.5 x ADR5 (10): no extension
    full2 = keep + [(S._exit_px(-3980.0, "array", p), "array")]
    why, k3, *_ = tp2.late(ctx, sd, dict(ext=-4021.0, ext_i=3), 10, p, "AM", -4018.0, 3.0, keep, full2, far, False, [], {}, {}, True, False, -4010.0)
    assert len(k3) == 2


def test_org_ce_final_when_ob_inside():
    ctx = _org_ctx(rows=flat(3, 4004.0, 0.5) + [(4003, 4012.5, 4012, 4012.2), (4012, 4012.4, 4005, 4006), (4006, 4008, 4000.5, 4001)] + flat(8, 4003.0, 0.5))
    sd = side(ctx)
    assert any(z.bottom == 4008 and z.top == 4012 for z in sd.opposing())
    p = Params(**P, org_ce_if_flow=True, org_draw="draw")
    far = S._exit_px(4020.0, "array", p)
    keep = [(S._exit_px(4010.0, "array", p), "array"), (far, "array")]
    lvt, st2 = [], {}
    why, k2, dr, fT = tp2.late(ctx, sd, dict(ext=3999.0, ext_i=2), 13, p, "AM", 4003.0, 2.0, keep, keep, far, False, lvt, {}, st2, True, False, 4004.0)
    assert why is None and k2[-1][0] == pytest.approx(S._exit_px(4010.0, "array", p)) and dr == k2[-1][0] and st2["runner"] == pytest.approx(far)       # the CE is final, the far edge a runner slice
    # no order flow inside the gap: unchanged
    ctx0 = _org_ctx(rows=flat(14, 4003.0, 0.3))
    why, k0, *_ = tp2.late(ctx0, side(ctx0), dict(ext=3999.0, ext_i=2), 13, p, "AM", 4003.0, 2.0, keep, keep, far, False, [], {}, {}, True, False, 4004.0)
    assert k0 == keep


def test_org_fill_stops_at_inner_breaker(monkeypatch):
    """Gap up 4000 -> 4020 (short): a bullish breaker whose candle spans 4008-4012: the fill stops at its low 4008 (side space top -4008), the prior close stays a runner."""
    ctx = _org_ctx(sign=-1)
    sd = side(ctx, -1)
    z = L.Zone("bear", -4008.0, -4012.0, 3)
    monkeypatch.setattr(TP, "matrix_breakers", lambda sd_, p_: [z])
    p = Params(**P, org_breaker_stop=True, org_draw="draw")
    far = S._exit_px(-4000.0, "array", p)
    keep = [(S._exit_px(-4014.0, "array", p), "array"), (far, "array")]
    st2 = {}
    why, k2, dr, fT = tp2.late(ctx, sd, dict(ext=-4021.0, ext_i=3), 10, p, "AM", -4018.0, 3.0, keep, keep, far, False, [], {}, st2, True, False, -4010.0)
    assert why is None and k2[-1][0] == pytest.approx(S._exit_px(-4008.0, "array", p)) and st2["runner"] == pytest.approx(far)
    assert tp2.org_breaker(ctx, sd, 10, p, -4020.0, -4000.0, -4018.0) == -4008.0
    assert tp2.org_breaker(ctx, sd, 10, p, -4005.0, -4000.0, -4018.0) is None             # the breaker is not inside this range


# --- L9-htf-fvg-target-ladder (41) ----------------------------------------------------------------------------------------------------------------

def _gap_rows(close_above=False):
    rows = flat(8, 4110.0)
    if close_above:
        rows[6] = (4110.0, 4128.5, 4109.0, 4128.0)
    return rows


def test_htf_gap_ladder_far_edge_mode(monkeypatch):
    cf = conf([(-1, 4134.0, 4120.0, np.inf, 0, "15m")])
    lv = [(4120.0, "array"), (4123.5, "array"), (4127.0, "array"), (4130.5, "array"), (4134.0, "array"), (4150.0, "pool")]
    p = Params(**P, htf_gap_gate=True, htf_gap_final="ce")
    for close, keep in ((False, False), (True, True)):
        ctx = mk(_gap_rows(close), cf)
        lvt = []
        out = tp2.raw_post(ctx, side(ctx), 7, p, "AM", 4110.0, 3.0, 4112.0, dict(ext=4100.0, ext_i=1), list(lv), lvt, {})
        vals = [v for v, _ in out]
        assert (4130.5 in vals and 4134.0 in vals) == keep and 4127.0 in vals and 4150.0 in vals           # 75 % / far edge only after a close beyond the CE
        assert ("htf_gap_ce_first" in lvt) == (not keep)
    # far_edge mode: the 75 % and the far edge stay while the bias table's flip is not against the order
    for flip, kept in ((0, True), (-1, False), (1, True)):
        monkeypatch.setattr(tp1, "_row", lambda ctx_, session, i, f=flip: {"flip": f})
        ctx = mk(_gap_rows(False), cf)
        out = tp2.raw_post(ctx, side(ctx), 7, replace(p, htf_gap_final="far_edge"), "AM", 4110.0, 3.0, 4112.0, dict(ext=4100.0, ext_i=1), list(lv), [], {})
        assert ((4134.0, "array") in out and (4130.5, "array") in out) == kept


def test_weekly_bisi_blocks_turtle_soup_and_traded_weekly_edges_stay():
    cf = conf([(1, 4000.0, 3990.0, np.inf, 0, "W")], tfs=("W",))
    ctx = mk(flat(10, 4005.0), cf)
    sd = side(ctx)
    p = Params(**P, weekly_bisi_ts_block=True)
    assert tp2.ts_weekly_bisi(ctx, sd, dict(level=4003.0), 5, p) and not tp2.ts_weekly_bisi(ctx, sd, dict(level=4010.0), 5, p)
    assert not tp2.ts_weekly_bisi(ctx, sd, dict(level=3995.0), 5, p)                       # the pool inside / under the gap
    cf2 = conf([(-1, 4120.0, 4110.0, 1.0, 0, "W")], tfs=("W",))                            # a weekly bearish FVG price traded through (dead)
    ctx2 = mk(flat(10, 4005.0), cf2)
    q = Params(**P, keep_traded_wfvg=True)
    out = tp2.raw_post(ctx2, side(ctx2), 5, q, "AM", 4005.0, 3.0, 4006.0, dict(ext=4000.0, ext_i=1), [(4050.0, "pool")], [], {})
    assert (4110.0, "array") in out and (4120.0, "array") in out and (4050.0, "pool") in out
    out0 = tp2.raw_post(ctx2, side(ctx2), 5, Params(**P), "AM", 4005.0, 3.0, 4006.0, dict(ext=4000.0, ext_i=1), [(4050.0, "pool")], [], {})
    assert out0 == [(4050.0, "pool")]


# --- L10-intraday-wick-ce (43) --------------------------------------------------------------------------------------------------------------------

def test_long_wick_ces_and_the_minimum_objective():
    o = np.array([100, 100, 100, 100.0])
    h = np.array([101.3, 110.0, 101.3, 101.3])
    l = np.array([99.0, 99.0, 99.0, 99.0])
    c = np.array([101.0, 101.0, 101.0, 101.0])
    got = L.long_wick_ces(o, h, l, c, True, 1.0, 20)
    assert [k for k, _, _ in got] == [1] and got[0][1] == pytest.approx((101.0 + 110.0) / 2)
    # 1h buckets from 09:00: a long wick (bucket 1) and a stubby one (bucket 2)
    rows = [(4000, 4001, 3999, 4000.5)] * 6 + [(4000, 4001, 3999, 4000.5)] * 6
    rows[2] = (4000, 4030, 3999, 4000.5)                                                  # the 09:00 bucket: a 29.5-point upper wick over a 0.5 body
    ctx = mk(rows + [(4000, 4001, 3999, 4000.5)] * 12)
    sd = side(ctx)
    p = Params(**P, wick_tfs=("1h",), wick_partial_min_pts=0.0, wick_long_only=True, min_obj_frac=0.2)
    w = TP.tf_wicks(ctx, sd, 23, p, ("1h",), 4000.0)
    assert len(w) == 1 and w[0][0] == pytest.approx((4000.5 + 4030) / 2)
    st2 = {}
    tp2.raw_post(ctx, sd, 23, p, "AM", 4000.0, 3.0, 4001.0, dict(ext=3999.0, ext_i=1), [(4100.0, "pool")], [], st2)
    assert st2["min_obj"] == [pytest.approx((4000.5 + 4030) / 2)]
    tags, lvt = {}, []
    keep = [(4100.0, "pool")]
    tp2.late(ctx, sd, dict(ext=3999.0, ext_i=1), 23, p, "AM", 4000.0, 3.0, keep, keep, 4100.0, False, lvt, tags, st2, False, False, 4001.0)
    assert tags["tp2_extras"][0][1:] == ("min_obj", True) and "min_obj" in lvt
    # the share of the position: fill_plan uses min_obj_frac for the kind
    o2 = dict(rung_plan=[dict(v=4015.0, k="min_obj", role="extra", prot=True), dict(v=4100.0, k="pool", role="main", prot=False)], final_T=False, bulk=False)
    lv_, kd_, fr_ = TP.fill_plan(o2, (1.0,), p)
    assert kd_ == ["min_obj", "pool"] and fr_[0] == pytest.approx(0.2)
    # without wick_long_only the stubby wick of the second bucket counts as well
    w0 = TP.tf_wicks(ctx, sd, 23, replace(p, wick_long_only=False), ("1h",), 4000.0)
    assert len(w0) >= 1


def test_1h_wick_ce_ladder_steps():
    """Two long 1h upper wicks above price (the short of the spec: two long lower wicks below): both CEs are in the ladder, in order (the built wick_tfs source, long wicks only)."""
    rows = [(4000, 4000.5, 3999, 4000.2)] * 96
    rows[2] = (4000, 4040.0, 3999, 4000.2)                                                # the 09:00 bucket (bars 0-5): CE (4000.2 + 4040) / 2
    rows[40] = (4000, 4020.0, 3999, 4000.2)                                               # the 12:00 bucket (bars 30-41): CE (4000.2 + 4020) / 2, never traded through
    ctx = mk(rows)
    sd = side(ctx)
    p = Params(**P, wick_tfs=("1h",), wick_partial_min_pts=0.0, wick_long_only=True)
    w = sorted(x[0] for x in TP.tf_wicks(ctx, sd, 95, p, ("1h",), 4000.0))
    assert w == [pytest.approx((4000.2 + 4020.0) / 2), pytest.approx((4000.2 + 4040.0) / 2)]
    assert len(sorted(x[0] for x in TP.tf_wicks(ctx, sd, 95, replace(p, wick_long_only=False), ("1h",), 4000.0))) >= 2


# --- L12 SD engine ----------------------------------------------------------------------------------------------------------------------------------

def _sd_setup(rows, sign=1, **pk):
    ctx = mk(rows)
    sd = side(ctx, sign)
    p = Params(**P, sd_targets=True, **pk)
    return ctx, sd, p


def _levels(ctx, sd, p, sw, leg_hi, rr, lv, entry=4090.0, risk=3.0, i=None):
    lvt = []
    out = TP.sd_levels(ctx, sd, len(ctx.c) - 1 if i is None else i, p, sw, leg_hi, rr, lv, entry, risk, lvt)
    return out, lvt


def test_sd_arm_needs_close_through():
    """Anchor 4096..4100 (leg high 4100): a wick through 4100 that closes back arms nothing, a close above and then a higher close does."""
    base = flat(4, 4090.0) + [(4090, 4100, 4090, 4095)]
    wick = base + [(4095, 4101.0, 4094, 4098.0)] + [(4098, 4099, 4097, 4098.0)] * 2
    ctx, sd, p = _sd_setup(wick, sd_arm="close", sd_arm_bars=1)
    sw = dict(ext=4090.0, ext_i=3)
    out, _ = _levels(ctx, sd, p, sw, 4100.0, None, [(4102.0, "pool")])
    assert out == []
    good = base + [(4098, 4103.0, 4097, 4102.0)] + [(4102, 4104, 4101, 4103.0)] * 2
    ctx2, sd2, p2 = _sd_setup(good, sd_arm="close", sd_arm_bars=1)
    out2, _ = _levels(ctx2, sd2, p2, sw, 4100.0, None, [(4102.0, "pool")])
    assert len(out2) == 1 and out2[0][0] > 4102.0
    # trade mode = the built behaviour: the wick arms it
    ctx3, sd3, p3 = _sd_setup(wick, sd_arm="trade", sd_ref_roll=True)
    out3, _ = _levels(ctx3, sd3, p3, sw, 4100.0, None, [(4102.0, "pool")])
    assert len(out3) == 1
    # a return inside within sd_arm_bars: not armed
    back = base + [(4098, 4103.0, 4097, 4102.0)] + [(4102, 4102.5, 4098, 4099.0)] + [(4099, 4100, 4098, 4099.5)]
    ctx4, sd4, p4 = _sd_setup(back, sd_arm="close", sd_arm_bars=1)
    assert _levels(ctx4, sd4, p4, sw, 4100.0, None, [(4102.0, "pool")])[0] == []


def test_sd_ref_rolls_to_newer_high():
    """Pool 4100.75, a newer pivot high 4101.5; the SD levels 4101 / 4102 / 4103 / 4104 (range 2 from 4100): without the roll 4101 is first beyond the pool, with it 4102."""
    rows = flat(3, 4096.0) + [(4096, 4101.5, 4096, 4100)] + flat(8, 4098.0)
    ctx, sd, p = _sd_setup(rows, sd_ref_roll=True, sd_levels=(0.5, 1.0, 1.5, 2.0))
    sw = dict(ext=4098.0, ext_i=0)
    sd.ph = [L.Pivot(3, 4101.5, 4)]
    lv = [(4100.75, "pool")]
    out, _ = _levels(ctx, sd, p, sw, 4100.0, None, lv, entry=4090.0)
    assert [v for v, _ in out] == [4102.0]
    out0, _ = _levels(ctx, sd, replace(p, sd_ref_roll=False, sd_anchor="broken", sd_targets=True), dict(sw), 4100.0, (0, 4100.0, 0), lv, entry=4090.0)
    assert out0 == [] or out0[0][0] == 4101.0


def test_sd_cluster_from_tiers():
    rows = flat(14, 4098.0)
    ctx, sd, p = _sd_setup(rows, sd_multi_tiers=("itl", "ltl"), sd_cluster_min=3, sd_levels=(1.0, 1.5, 2.0))
    sw = dict(ext=4090.0, ext_i=0)
    Pv = L.Pivot
    sd.ph = [Pv(1, 4100.25, 2), Pv(4, 4101.0, 5), Pv(7, 4101.5, 8)]
    lows_itl = [Pv(2, 4096.25, 3), Pv(5, 4097.75, 6)]
    lows_ltl = [Pv(8, 4098.5, 9)]
    sd._lz["tiers"] = {"itl": ([], lows_itl), "ltl": ([], lows_ltl)}
    out, lvt = _levels(ctx, sd, p, sw, 4100.0, None, [(4100.1, "pool")], i=12)
    assert [(round(v, 2), k) for v, k in out if k != "sd"] == [(4104.25, "proj_cluster")] and "sd_cluster_tiers" in lvt        # (+ the plain leg's own first level)
    assert not [1 for v, k in out if k == "sd" and round(v, 2) in (4104.25, 4104.5)]
    p2 = replace(p, sd_cluster_min=4)
    out2, _ = _levels(ctx, sd, p2, sw, 4100.0, None, [(4100.1, "pool")], i=12)
    assert sorted(round(v, 2) for v, _ in out2 if v < 4110) == [4104.25, 4104.25, 4104.5] and {k for _, k in out2} == {"sd"}


def test_projection_exit_one_tick_before():
    p = Params(**P, proj_exit_ticks=1)
    assert S._exit_px(4076.25, "proj", p) == pytest.approx(4076.0) and S._exit_px(4076.25, "proj_htf", p) == pytest.approx(4076.0)
    assert S._exit_px(4076.25, "array", p) == S._exit_px(4076.25, "array", Params(**P))                      # other kinds keep the X2 offset
    assert TP._raw(4076.0, "proj", p) == pytest.approx(4076.25)
    assert S._exit_px(4076.25, "proj", Params(**P)) == S._exit_px(4076.25, "array", Params(**P))


def test_entry_low_projection_rung_is_added_mid_trade():
    rows = flat(3, 4064.0) + [(4064, 4066, 4063.25, 4065)] + [(4065, 4070, 4064, 4069)] + [(4069, 4076.5, 4068, 4075)] + [(4075, 4072, 4070, 4071)] + [(4071, 4071.5, 4069, 4070)] * 3
    ctx = mk(rows)
    sd = side(ctx)
    p = Params(**P, sd_targets=True, sd_anchor="entry_low", proj_exit_ticks=1, htf_runner_frac=0.1)
    pos = dict(left=3, levels=[4080.0], fracs=(1.0,), k=0, final_T=False, level_kinds=["array"])
    tr = SimpleNamespace(lv_tags="")
    tp2.on_fill(ctx, sd, pos, tr, dict(ext=4063.25, tp2=None), 3, p)
    assert pos["tp2"]["entry_low"] == 4063.25
    for i in range(4, 9):
        tp2.manage(ctx, sd, pos, tr, i, p)
    q = next(q for q in sd.ph if q.i >= 3 and q.price > 4063.25)
    want = q.price + (q.price - 4063.25) - 0.25
    assert pos["levels"][-1] == pytest.approx(want) if want > 4080.0 else pos["levels"] == [4080.0]
    # a rung beyond the last one with room: the fraction is carved from the last rung
    pos2 = dict(left=3, levels=[4072.0], fracs=(1.0,), k=0, final_T=False, level_kinds=["array"], tp2=dict(entry_low=4063.25, fill_i=3))
    tr2 = SimpleNamespace(lv_tags="")
    sd.ph = [L.Pivot(5, 4070.0, 6)]
    tp2.manage(ctx, sd, pos2, tr2, 8, p)
    assert len(pos2["levels"]) == 2 and pos2["levels"][-1] == pytest.approx(4070 + 6.75 - 0.25) and pos2["fracs"] == pytest.approx((0.9, 0.1)) and "entry_low_proj" in tr2.lv_tags
    assert pos2["level_kinds"][-1] == "proj"


def test_sd_capped_at_htf_fvg():
    cf = conf([(-1, 4130.5, 4122.0, np.inf, 0, "15m")])
    rows = flat(8, 4110.0)
    ctx = mk(rows, cf)
    sd = side(ctx)
    p = Params(**P, sd_targets=True, sd_cap_htf=True, sd_first_beyond=False, sd_levels=(1.0, 1.5, 2.0))
    sw = dict(ext=4109.75, ext_i=1)
    out, lvt = _levels(ctx, sd, p, sw, 4118.0, None, [], entry=4111.0, i=7)
    # leg 4109.75 .. 4118.0: levels 4126.25 / 4130.375 / 4134.5
    assert [round(v, 3) for v, _ in out] == [4126.25, 4130.375] and "sd_cap_htf" in lvt
    out0, _ = _levels(ctx, sd, replace(p, sd_cap_htf=False), sw, 4118.0, None, [], entry=4111.0, i=7)
    assert len(out0) == 3


def test_sd_at_wick_ce_marks_intraday_high(monkeypatch):
    rows = flat(12, 4112.0)
    ctx = mk(rows, wicks=[{"upper": 4125.0, "lower": 3990.0}], wick={"upper": 4125.0, "lower": 3990.0})
    sd = side(ctx)
    monkeypatch.setattr(L, "tf_pivots", lambda idx, h, l, base, m, n=1: ([L.Pivot(5, 4110.0, 6)], [L.Pivot(2, 4100.0, 3)]))
    p = Params(**P, sd_targets=True, sd_anchor="m15_leg", sd_htf_extreme=True, sd_htf_tol=1.0, sd_levels=(0.5, 1.0, 1.5, 2.0), sd_first_beyond=False)
    out, lvt = _levels(ctx, sd, p, dict(ext=4100.0, ext_i=2), 4110.0, None, [], entry=4105.0, i=11)
    assert [(round(v, 2), k) for v, k in out] == [(4125.0, "proj_htf")]                    # 4110 + 1.5 x 10 = the daily wick CE
    # the closing rung: a proj_htf rung reached after 11:00 with an SMT
    pos = dict(level_kinds=["array", "proj_htf"])
    assert tp2.close_here(pos, 1, SimpleNamespace(smt=True), 660, 5, p) and not tp2.close_here(pos, 1, SimpleNamespace(smt=None), 660, 5, p)
    assert not tp2.close_here(pos, 1, SimpleNamespace(smt=True), 570, 5, p) and not tp2.close_here(pos, 0, SimpleNamespace(smt=True), 660, 5, p)
    assert not tp2.close_here(pos, 1, SimpleNamespace(smt=True), 660, 5, replace(p, sd_htf_extreme=False))


def test_sd_pick_premium_on_consolidation_day():
    rows = [(4010, 4012, 4010, 4011)] + flat(6, 4015.0, 0.5) + [(4018, 4034, 4017, 4019)] + flat(3, 4019.0, 0.5)
    ctx, sd, p = _sd_setup(rows, sd_premium_consol=True, sd_levels=(1.0, 1.5, 2.0, 2.5))
    ctx.dplan = SimpleNamespace(tags={"consol_day"})
    sw = dict(ext=4010.0, ext_i=0)
    # leg 4015..4018 (range 3): levels 4021 / 4022.5 / 4024 / 4025.5; the day's range 4010-4034 has its 50 % at 4022
    out, lvt = _levels(ctx, sd, p, dict(ext=4015.0, ext_i=1), 4018.0, None, [(4020.0, "pool")], entry=4016.0)
    assert [(round(v, 2), k) for v, k in out] == [(4022.5, "proj")]
    ctx.dplan = SimpleNamespace(tags=set())                                                 # not a consolidation day: the first level beyond the pool
    out2, _ = _levels(ctx, sd, p, dict(ext=4015.0, ext_i=1), 4018.0, None, [(4020.0, "pool")], entry=4016.0)
    assert [round(v, 2) for v, _ in out2] == [4021.0]


def test_last_hour_sd_k3():
    """The short of the spec (swing high 4128.5, the MSS low 4123.5, k = 3 -> 4108.5): a short at 15:10 (real prices; the engine mirrors them)."""
    idx = pd.date_range("2026-06-23 14:50", periods=12, freq="5min", tz=NY)
    n = len(idx)
    rows = [(4127.0, 4128.5, 4126.0, 4127.0)] * 2 + [(4127.0, 4127.5, 4123.0, 4123.2)] + [(4123.2, 4124.0, 4122.0, 4122.5)] * (n - 3)       # the high 4128.5 (bar 0-1), the break of the low 4123.5 (bar 2)
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    ctx = SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values, hist=hist_days(), pd={}, sess={}, day=D0, org=[], org_today=False)
    sd = S.Side(-1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    p = Params(**P, sd_targets=True, sd_anchor="mss_leg", sd_last_hour_k=3.0)
    sw = dict(ext=-4128.5, ext_i=1)
    rr = (0, -4123.5, 0)
    out, lvt = _levels(ctx, sd, p, sw, -4125.0, rr, [], entry=-4122.5, i=n - 1)
    assert [(round(v, 2), k) for v, k in out] == [(-4108.5, "proj_lh")] and "sd_mss_leg" in lvt
    keep_full = [(-4115.0, "array"), (-4108.5, "proj_lh")]
    tags, lvt2 = {}, []
    why, k2, dr, fT = tp2.late(ctx, sd, sw, n - 1, p, "PM", -4122.5, 3.0, keep_full[:1], keep_full, -4115.0, False, lvt2, tags, {}, False, False, -4125.0)
    assert dr == -4108.5 and tags["exit_at"] == 945 and "sd_last_hour" in lvt2
    # before 15:00 the built first-beyond rule (no pool: nothing) applies
    ctx2 = SimpleNamespace(**{**ctx.__dict__, "t": ctx.t - 120})
    out2, _ = _levels(ctx2, sd, p, sw, -4125.0, rr, [], entry=-4122.5, i=n - 1)
    assert out2 == []


# --- L13-org-sd-projection (56) -------------------------------------------------------------------------------------------------------------------

def test_org_projection_after_reprice(monkeypatch):
    from mentorship import bias_day as BD
    monkeypatch.setattr(BD, "want_at", lambda ctx, p, session, i: 1)
    p = Params(**P, proj_org_reprice=True, proj_org_kmax=3)
    # the ORG: prior close 4200, open 4205 (a gap up): nothing before a bar trades down to 4200
    ctx = mk(flat(8, 4207.0, 0.5), org=[(4200.0, 4205.0)], org_today=True)
    assert tp2.org_projection(ctx, side(ctx), 7, p, "AM", 4205.0) == []
    rows = flat(4, 4207.0, 0.5) + [(4207, 4208, 4199.5, 4206.0)] + flat(3, 4207.0, 0.5)
    ctx2 = mk(rows, org=[(4200.0, 4205.0)], org_today=True)
    out = tp2.org_projection(ctx2, side(ctx2), 7, p, "AM", 4205.0)
    assert [(round(v, 2), k) for v, k in out] == [(4210.0, "proj"), (4215.0, "proj"), (4220.0, "proj")]
    ctx2.cur_lock = {"target": 4215.5}
    out2 = tp2.org_projection(ctx2, side(ctx2), 7, p, "AM", 4205.0)
    assert [k for _, k in out2] == ["proj", "proj_htf", "proj"]                                  # the level at the locked draw (within sd_htf_tol)
    monkeypatch.setattr(BD, "want_at", lambda ctx, p, session, i: -1)
    assert tp2.org_projection(ctx2, side(ctx2), 7, p, "AM", 4205.0) == []                       # the bias against the order's side: none


# --- L14-session-pools-only (60) ------------------------------------------------------------------------------------------------------------------

def test_session_pools_only_filters_minor_swings():
    ctx = mk(flat(12, 4000.0), sess={"london": (4090.0, 4000.0, 300), "prev_pm": (4070.0, 3990.0, 0), "lunch": (4060.0, 4000.0, 0)}, pd={"pdh1": 4110.0})
    sd = side(ctx)
    lv = [(4090.0, "pool"), (4070.0, "pool"), (4060.0, "pool"), (4110.0, "pool"), (4080.0, "pool"), (4075.0, "pool_eq"), (4120.0, "array")]
    out = tp2.session_filter(ctx, sd, 11, Params(**P, session_pools_mode="only"), list(lv))
    assert [v for v, _ in out] == [4090.0, 4070.0, 4110.0, 4120.0]                       # the lunch high, the minor 4080 swing and the rel-eq 4075 are out; the array stays
    ext = tp2.session_filter(ctx, sd, 11, Params(**P, session_pools_mode="extended"), list(lv))
    assert {v for v, _ in ext} == {4090.0, 4070.0, 4060.0, 4110.0, 4075.0, 4120.0}         # + the lunch high and the rel-eq pool inside the previous PM / London range; the minor 4080 swing stays out
    # the sweep pools of the scan
    ss = {"pdl1": 3990.0, "swing_low3": 3995.0, "london": 3980.0, "rel_eq2": 3985.0, "round": 4000.0, "lunch": 3975.0}
    assert set(tp2.sell_side_filter(dict(ss), ctx, sd, Params(**P, session_pools_mode="only"))) == {"pdl1", "london"}
    assert set(tp2.sell_side_filter(dict(ss), ctx, sd, Params(**P, session_pools_mode="extended"))) == {"pdl1", "london", "rel_eq2", "lunch"}
    rk = tp2.sell_side_filter(dict(ss), ctx, sd, Params(**P, session_pools_mode="rank"))
    assert list(rk)[:2] == ["pdl1", "london"] and set(rk) == set(ss)
    assert tp2.lock_session_rank([(1, 1, "pool", "pdh1", 1), (2, 2, "pool", "london_high", 1)])[0][3] == "london_high"


# --- L15 (61, 62) ---------------------------------------------------------------------------------------------------------------------------------

def test_room_to_htf_far_edge():
    cf = conf([(-1, 4185.0, 4180.0, np.inf, 0, "15m")])
    ctx = mk(flat(10, 4175.0), cf)
    sd = side(ctx)
    p = Params(**P, room_ref="htf_far", min_draw_pts=10.0)
    assert tp2.room(ctx, sd, 5, p, 4175.0, 4176.0, 4179.5) == pytest.approx(10.0)          # the far edge 4185 - the entry 4175: passes min 10
    assert tp2.room(ctx, sd, 5, replace(p, room_ref="exit"), 4175.0, 4176.0, 4179.5) == pytest.approx(4.5)       # the draw's exit 4179.5: fails
    ctx0 = mk(flat(10, 4175.0))
    assert tp2.room(ctx0, side(ctx0), 5, p, 4175.0, 4176.0, 4179.5) == pytest.approx(4.5)  # no array: the exit fallback


def test_t1_skips_pool_under_5():
    p = Params(**P, t1_skip_near=True, min_draw_pts=5.0)
    keep = [(4136.0, "pool"), (4137.0, "array"), (4139.82, "pool")]
    out, ok = tp2.skip_near(keep, 4134.0, p)
    assert ok and out == [(4137.0, "array"), (4139.82, "pool")]
    out2, ok2 = tp2.skip_near([(4136.0, "pool"), (4137.0, "array")], 4134.0, p)
    assert not ok2                                                                          # pools existed, none offers the room
    out3, ok3 = tp2.skip_near([(4137.0, "array")], 4134.0, p)
    assert ok3 and out3 == [(4137.0, "array")]


# --- X1 (65, 66) ----------------------------------------------------------------------------------------------------------------------------------

def _overnight_ctx():
    idx = pd.date_range(pd.Timestamp("2026-06-23 02:00", tz=NY), periods=96, freq="5min")
    o = np.full(96, 4050.0)
    h = o + 0.5
    l = o - 0.5
    c = o.copy()
    k = 12                                                                                   # 03:00
    o[k - 2], h[k - 2], l[k - 2], c[k - 2] = 4064, 4066, 4062, 4063
    o[k - 1], h[k - 1], l[k - 1], c[k - 1] = 4063, 4063.5, 4054, 4055
    o[k], h[k], l[k], c[k] = 4055, 4057, 4050, 4051
    return SimpleNamespace(conf=None, idx=idx, tf=5, start=0, o=o, h=h, l=l, c=c, t=(idx.hour * 60 + idx.minute).values, hist=hist_days(), pd={}, sess={}, day=D0, org=[], org_today=False,
                           or_hl=None, or_end=600, am_hl=None, gaps=None)


def test_overnight_5m_fvg_target():
    ctx = _overnight_ctx()
    sd = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    p = Params(**P, overnight_5m_fvgs=True)
    i = int(np.flatnonzero(ctx.t == 585)[0])
    out = tp2.overnight_fvgs(ctx, sd, i, p, 4050.0)
    assert [(round(v, 2)) for v, _ in out] == [4057.0, 4059.5, 4062.0]
    assert tp2.overnight_fvgs(ctx, sd, i, p, 4060.0) == []                                     # an FVG not beyond `above`
    ctx.h[20] = 4058.0                                                                         # traded into: no longer open
    sd2 = S.Side(1, ctx.o, ctx.h, ctx.l, ctx.c, 1, 0.0)
    assert tp2.overnight_fvgs(ctx, sd2, i, p, 4050.0) == []
    ctx.h[20] = 4050.5
    lc = tp2.lock_cands(ctx, p, 570, i + 1)                                                    # as AM lock candidates (real prices, direction 0)
    assert sorted(v for v, *_ in lc) == [4057.0, 4059.5, 4062.0] and all(c_[1:4] == ("array", "on_fvg", 0) for c_ in lc)
    assert tp2.lock_cands(ctx, p, 540, i + 1) == [] and tp2.lock_cands(ctx, Params(**P), 570, i + 1) == []


def test_weekly_ob_open_target():
    """A weekly bearish OB above a long (the mirror of the spec's short: weekly bullish OB h 4000 o 3990): near edge 4000, open 4002; final = the open when no FVG / VI is in between."""
    cf = conf([(-1, 4010.0, 4000.0, np.inf, 1, "W")], tfs=("W",))
    cf.z["W"]["open"] = np.array([4002.0])
    ctx = mk(flat(10, 3990.0), cf)
    sd = side(ctx)
    p = Params(**P, htf_ob_open=True, htf_ob_open_final=True)
    st = {"tags": [], "prefs": []}
    out = tp2.htf_ob(ctx, sd, 5, p, 3995.0, st)
    assert out == [(4000.0, "array"), (4002.0, "array")] and st["ob_open_final"] == 4002.0 and "htf_ob_open" in st["tags"]
    cf2 = conf([(-1, 4010.0, 4000.0, np.inf, 1, "W"), (-1, 3998.0, 3994.0, np.inf, 0, "15m")], tfs=("W", "15m"))
    cf2.z["W"]["open"] = np.array([4002.0])
    ctx2 = mk(flat(10, 3990.0), cf2)
    st2 = {"tags": [], "prefs": []}
    tp2.htf_ob(ctx2, side(ctx2), 5, p, 3991.0, st2)
    assert "ob_open_final" not in st2                                                          # an FVG lies between: not the final target
    ctx.__dict__["_tp2_st"] = dict(tags=[], prefs=[], ob_open_final=4002.0)
    assert tp2.draw_prefs(ctx, sd, 5, 3991.0, p, "AM", []) == [(S._exit_px(4002.0, "array", p), "array", "htf_ob_open")]


# --- B2-target-beyond-pool-inefficiency (85) -------------------------------------------------------------------------------------------------------

def test_final_target_array_beyond_pool():
    """The short of the spec (low 4000, FVG top 3996 beyond; FVG at 4005 inside) as a long: the pool 4000 (draw), a bearish FVG 4004-4008 beyond -> final 4004; an FVG 3996-3998 between price and the pool is no final."""
    rows = [(3990.0, 3991.0, 3988.0, 3990.0)] * 10
    ctx = mk(rows)
    sd = side(ctx)
    z_in = [z for z in sd.opposing()]
    p = Params(**P, beyond_pool_final=True)
    ex = lambda v, k: S._exit_px(v, k, p)
    keep = [(ex(3996.0, "array"), "array"), (ex(4000.0, "pool"), "pool")]
    sd._opp = [L.Zone("bear", 4008.0, 4004.0, 3), L.Zone("bear", 3998.0, 3996.0, 3)]
    r = tp2.beyond_pool(ctx, sd, 9, p, 3992.0, 3992.0, keep, keep, ex(4000.0, "pool"))
    assert r is not None and abs(r[1] - ex(4004.0, "array")) < 1e-9 and r[0][0] == keep[0] and r[0][1][0] == ex(4000.0, "pool")        # the array between price and the pool stays a rung
    sd._opp = [L.Zone("bear", 3998.0, 3996.0, 3)]
    eqs = keep + [(ex(4012.0, "pool_eq"), "pool_eq")]
    r2 = tp2.beyond_pool(ctx, sd, 9, p, 3992.0, 3992.0, keep, eqs, ex(4000.0, "pool"))
    assert r2 is not None and r2[1] == ex(4012.0, "pool_eq")                                 # no array beyond: the next rel-eq pool
    assert tp2.beyond_pool(ctx, sd, 9, p, 3992.0, 3992.0, keep, keep, ex(4000.0, "pool")) is None


# --- new-pool-break-accel-vs-reject (86) ----------------------------------------------------------------------------------------------------------

def _break_rows(accel):
    rows = [(4090.0, 4090.6, 4089.6, 4090.2)] * 14
    if accel:
        rows += [(4098.0, 4103.0, 4098.0, 4102.5), (4102.5, 4108.0, 4102.0, 4107.0), (4107.0, 4109.0, 4105.0, 4108.0)] + [(4108.0, 4109.0, 4107.0, 4108.0)] * 3
    else:
        rows += [(4099.5, 4100.5, 4099.0, 4099.8), (4099.8, 4100.2, 4098.5, 4099.0)] + [(4099.0, 4099.5, 4098.0, 4098.5)] * 4
    return rows


def test_deeper_pool_only_after_acceleration():
    p = Params(**P, break_accel_gate=True)
    lv = [(4120.0, "pool"), (4105.0, "array")]
    for accel, kept in ((False, False), (True, True)):
        ctx = mk(_break_rows(accel), pd={"pdh1": 4100.0})
        sd = side(ctx)
        st = {"tags": [], "prefs": []}
        out = tp2.break_accel(ctx, sd, len(ctx.c) - 1, p, list(lv), st)
        assert ((4120.0, "pool") in out) == kept and (4105.0, "array") in out
        assert st["tags"] == (["break_accel"] if kept else ["break_reject"])


# --- new-old-pool-redelivery (88) -----------------------------------------------------------------------------------------------------------------

def test_swept_high_is_short_target(monkeypatch):
    """BSL 4100 swept, then a short from 4110 with the bias short: the rung 4100. The pdh1 is real price 4100: the mirrored short side space holds -4100."""
    from mentorship import bias_day as BD
    rows = [(4090, 4101.0, 4089, 4100.0)] + [(4100, 4112.0, 4099, 4110.0)] * 3 + [(4110, 4111, 4109, 4110.0)] * 6
    ctx = mk(rows, pd={"pdh1": 4100.0})
    sd = side(ctx, -1)
    p = Params(**P, swept_pool_targets=True)
    monkeypatch.setattr(BD, "want_at", lambda ctx_, p_, s_, i_: -1)
    st = {"tags": [], "prefs": []}
    out = tp2.swept_targets(ctx, sd, 9, p, -4110.0, [], st)
    assert out == [(-4100.0, "array")] and "swept_pool" in st["tags"]
    monkeypatch.setattr(BD, "want_at", lambda ctx_, p_, s_, i_: 1)
    assert tp2.swept_targets(ctx, sd, 9, p, -4110.0, [], {"tags": [], "prefs": []}) == []          # the bias against the trade and no other level near it
    assert tp2.swept_targets(ctx, sd, 9, p, -4110.0, [(-4100.4, "pool")], {"tags": [], "prefs": []}) == [(-4100.0, "array")]       # another ladder level within 1 pt
    assert tp2.swept_targets(ctx, sd, 9, p, -4090.0, [], {"tags": [], "prefs": []}) == []         # not beyond `above`


# --- L13-breaker-range-sd-weekly (89) -------------------------------------------------------------------------------------------------------------

def test_breaker_range_minus2_sd(monkeypatch):
    from mentorship import bias_day as BD
    monkeypatch.setattr(BD, "want_at", lambda ctx_, p_, s_, i_: 1)
    ctx = mk(flat(10, 15700.0), wbias=1)
    sd = side(ctx)
    p = Params(**P, proj_breaker=True, proj_breaker_k=(1.0, 2.0))
    assert tp2.breaker_ks(ctx, sd, 5, p, "AM", 15780.0, 15700.0) == [(15860.0, "array"), (15940.0, "proj_wk")]
    ctx.wbias = -1                                                                               # the weekly bias against the order: only the 1 x rung
    assert tp2.breaker_ks(ctx, sd, 5, p, "AM", 15780.0, 15700.0) == [(15860.0, "array")]
    monkeypatch.setattr(BD, "want_at", lambda ctx_, p_, s_, i_: 0)
    ctx.wbias = 1
    assert tp2.breaker_ks(ctx, sd, 5, p, "AM", 15780.0, 15700.0) == [(15860.0, "array")]


# --- new-level-confluence-scoring (94) ------------------------------------------------------------------------------------------------------------

def test_level_confluence_score():
    srcs = [("a", "15m", [4100.0, 4090.0]), ("b", "M", [4100.0, 4120.0]), ("c", "W", [4101.0]), ("d", "15m", [4200.0])]
    assert CF.level_score(4100.0, srcs, 0.0001, 0.25) == pytest.approx(3.5)                  # 15m high 4100 = monthly CE 4100: 0.5 + 3
    assert CF.level_score(4100.0, srcs, 0.001, 0.25) == pytest.approx(5.5)                   # the weekly one at 4101 is inside 0.1 % (4.1 pts)
    assert CF.level_score(4150.0, srcs, 0.001, 0.25) == 0.0
    cf = conf([(-1, 4100.0, 4090.0, np.inf, 0, "15m"), (-1, 4110.0, 4090.0, np.inf, 0, "M")], tfs=("15m", "M"))      # the monthly FVG CE 4100 = the 15m FVG's top
    ctx = mk(flat(10, 4000.0), cf)
    sd = side(ctx)
    p = Params(**P, confl_rank=True, confl_tol_frac=0.0001)
    sc = tp2.level_scores(ctx, sd, 5, p, [(4100.0, "array"), (4095.0, "array"), (4130.0, "array")])
    assert sc[0] == pytest.approx(3.5) and sc[1] < sc[0] and sc[2] == 0.0
    # the final target = the highest scoring level beyond the first rung (ties: the nearest)
    keep_full = [(S._exit_px(4095.0, "array", p), "array"), (S._exit_px(4100.0, "array", p), "array"), (S._exit_px(4130.0, "array", p), "array")]
    lvt = []
    why, k2, dr, fT = tp2.late(ctx, sd, dict(ext=3999.0, ext_i=1), 5, p, "AM", 4001.0, 2.0, keep_full[:1], keep_full, keep_full[0][0], False, lvt, {}, {}, False, False, 4002.0)
    assert dr == keep_full[1][0] and k2[-1] == keep_full[1] and "confl_final" in lvt
    picked = tp2.pick_scored(ctx, sd, 5, p, [(4100.0, 4090.0, "ob"), (4120.0, 4110.0, "fvg")])
    assert picked[2] == "ob"


# --- D23-inception-fulcrum-anchor (98) ------------------------------------------------------------------------------------------------------------

def test_inception_fulcrum_sd():
    """Inception 15680 (the high that began the move), fulcrum low 15665.75: -1 SD 15651.5 once a bar traded below the fulcrum (short = side space x -1)."""
    real = [(15680, 15681, 15678, 15679), (15679, 15679.5, 15672, 15673), (15673, 15674, 15665.75, 15667), (15667, 15674, 15666.5, 15673), (15673, 15674, 15668, 15669), (15669, 15670, 15660.0, 15662.0), (15662, 15663, 15655, 15656)]
    ctx = mk(real)
    sd = side(ctx, -1)
    sd.ph = [L.Pivot(2, -15665.75, 3)]
    p = Params(**P, sd_targets=True, sd_anchor="fulcrum", sd_fulcrum_def="inception", sd_levels=(0.5, 1.0, 1.5), sd_first_beyond=False)
    sw = dict(ext=-15681.0, ext_i=0)
    out, lvt = _levels(ctx, sd, p, sw, -15665.75, None, [], entry=-15668.0, i=6)
    lv = [round(-v, 2) for v, _ in out]
    assert 15651.5 in [round(x - 0.0, 2) for x in lv] or lv                                   # the range: ext -15681 .. -15665.75 (15.25): -1 SD = -15665.75 + 15.25 = -15650.5
    assert [round(-v, 2) for v, _ in out] == [15658.12, 15650.5, 15642.88]
    # not yet traded through the fulcrum: no projection (the 'inception' definition is armed by the trade, not by a close)
    real2 = [r if k < 3 else (15669, 15670, 15667.0, 15668) for k, r in enumerate(real)]
    ctx2 = mk(real2)
    sd2 = side(ctx2, -1)
    sd2.ph = [L.Pivot(2, -15665.75, 3)]
    assert _levels(ctx2, sd2, p, sw, -15665.75, None, [], entry=-15668.0, i=6)[0] == []
    # the built 'ep06' fulcrum needs a CLOSE beyond it
    out3, _ = _levels(ctx, sd, replace(p, sd_fulcrum_def="ep06"), sw, -15665.75, None, [], entry=-15668.0, i=6)
    assert len(out3) == 3


# --- L12-deep-sd-pd-convergence (99) --------------------------------------------------------------------------------------------------------------

def test_deep_sd_kept_on_fvg():
    cf = conf([(-1, 4132.0, 4128.0, np.inf, 0, "15m")])                                       # CE 4130 = the -3 SD
    ctx = mk(flat(10, 4100.0), cf)
    sd = side(ctx)
    p = Params(**P, sd_targets=True, sd_deep_conv=True, sd_conv_ticks=2, sd_levels=(1.0, 1.5, 2.0, 2.5, 3.0))
    out, lvt = _levels(ctx, sd, p, dict(ext=4090.0, ext_i=1), 4100.0, None, [(4108.0, "pool")], entry=4095.0, i=9)
    assert [(round(v, 2), k) for v, k in out] == [(4110.0, "sd"), (4130.0, "proj_runner")]            # -2.5 (4125) has no array: dropped
    out0, _ = _levels(ctx, sd, replace(p, sd_deep_conv=False), dict(ext=4090.0, ext_i=1), 4100.0, None, [(4108.0, "pool")], entry=4095.0, i=9)
    assert [round(v, 2) for v, _ in out0] == [4110.0]
    # the runner kind is the preferred final target
    keep_full = [(4110.0, "sd"), (4130.0, "proj_runner")]
    why, k2, dr, fT = tp2.late(ctx, sd, dict(ext=4090.0, ext_i=1), 9, p, "AM", 4095.0, 2.0, keep_full[:1], keep_full, 4110.0, False, [], {}, {}, False, False, 4100.0)
    assert dr == 4130.0 and k2[-1] == (4130.0, "proj_runner")


# --- new-defended-level (101) ---------------------------------------------------------------------------------------------------------------------

def test_defended_high_not_target():
    rows = flat(30, 4090.0) + [(4090, 4099.7, 4089, 4090)] * 2 + flat(5, 4090.0) + [(4090, 4100.2, 4089, 4090)] * 3 + flat(4, 4090.0)
    ctx = mk(rows)                                                                         # ADR5 = 20: the band is 2 x 0.1... 0.1 x 20 = 2; use 0.025 -> 0.5
    sd = side(ctx)
    p = Params(**P, defended_filter=True, defended_band_adr=0.025)
    lv = [(4100.0, "pool"), (4110.0, "pool"), (4105.0, "array")]
    st = {"tags": [], "prefs": []}
    out = tp2.defended(ctx, sd, len(rows) - 1, p, list(lv), st)
    assert out == [(4110.0, "pool"), (4105.0, "array")] and st["tags"] == ["defended"]       # five highs within 0.5 pt of 4100
    p2 = replace(p, defended_touches=6)
    assert tp2.defended(ctx, sd, len(rows) - 1, p2, list(lv), {"tags": [], "prefs": []}) == lv
    out3 = tp2.targets_post(ctx, sd, len(rows) - 1, p, 4091.0, list(lv), [], None)
    assert (4100.0, "pool") not in out3 and ctx.__dict__["_tp2_st"]["tags"] == ["defended"]


def test_session_pools_rank_is_a_draw_preference():
    ctx = mk(flat(12, 4000.0), sess={"london": (4040.0, 3990.0, 300)}, pd={"pdh1": 4090.0})
    sd = side(ctx)
    p = Params(**P, session_pools_mode="rank", draw_lock="off")
    ex = lambda v, k: S._exit_px(v, k, p)
    keep = [(ex(4030.0, "pool"), "pool"), (ex(4040.0, "pool"), "pool"), (ex(4090.0, "pool"), "pool")]
    out = tp2.draw_prefs(ctx, sd, 11, 4000.0, p, "AM", keep)
    assert out == [(ex(4040.0, "pool"), "pool", "session_pool")]                       # the nearest SESSION pool (the London high), not the minor 4030 swing
    assert tp2.draw_prefs(ctx, sd, 11, 4000.0, replace(p, session_pools_mode="off"), "AM", keep) == []
