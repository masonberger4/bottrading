"""Caption-gap pass, package management_exits #1/3, part A: the unit and engine tests of the 34 specs (bias_htf_intermarket.md 13, 68, 79, 209; day_selection_news_calendar.md 11, 58;
definitions_pd_arrays_structure.md 2, 17, 25, 30, 31, 40, 62, 63, 65, 83, 94, 106, 111, 196; levels_liquidity_targets.md 3, 47, 57, 84; management_partials_trailing_exits.md 5, 6, 10, 11, 12, 14,
16, 17, 18, 19). Hand-made one-minute bar books with the me1.py hooks called bar by bar (the position dict and the Side are real, the context is a stub) and scenario C through run_day for the
ladder-loop and order-level hooks. No platform-specific paths; nothing here needs market data. The study variants and the no-look-ahead runs are in test_caption_gap_me1b.py."""
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from mentorship import levels as L, me1, strategy as S, study, targets as TP
from mentorship.strategy import Params

from test_review_fixes import BASE, day, history, run as rf_run
from test_caption_gap_es1a import C_ROWS, POST

NY = "America/New_York"
D0 = date(2026, 6, 23)                       # a Tuesday: no release
NEW_SWITCHES = (
    "nwog_traverse_hold", "tick_match_hold", "heavy_gauge", "no_lunch_retrace_hold", "hold_through_0830", "thu_cap", "far_half_no_adds", "fvg_bpr_backstop", "vi_mid_exit", "rip_through",
    "fvg_full_fill_void", "refusal_breakaway", "iof_intraday_exit", "sd_time_roll", "hold_reached", "sd_body_hold", "best_case_limit", "be_cap_htf", "day_mode_auto", "event_eve_lock", "trail_confirm",
)
KNOBS = ("heavy_scale", "lunch_retr_max", "vi_mid_bars", "stall_partial", "resist_speed_bars", "pos_switch_frac", "run_through_ticks", "sd_window", "hold_tf", "best_case_mult", "best_case_bulk",
         "exit_slip_ticks", "be_adr", "runner_eq_after", "day_mode_size")
MODES = ("bpr_limit", "breaker_mt_test", "ce_exit", "resistance_def", "ifvg_fail_tf", "run_through_bars", "exit_fill", "be_mode", "runner_stop", "no_entry_0825")
GAP_IDS = (
    "BH-B14-NWOG-traverse-large-range", "BH-micro-BPR-tick-match-LOD", "B6-untouched-premium-arrays-heavy", "T9-strong-am-no-lunch-retrace", "N5-hold-through-0830", "N10-thursday-caps-week",
    "A11-bpr-retrace-allowance", "A13-breaker-mt-trade-test", "A5-partial-fill-strength-read", "A5-quadrants-any-gap-ladder", "A5-reclaimed-fvg-full-revisit", "A9-broken-vi-retrace-midpoint",
    "A8-rip-through-ce-signature", "X9-entry-fvg-immediate-rejection", "L4-resistance-is-delivery-speed", "A8-ifvg-15m-body-failure", "A6-breakaway-by-refusal", "new-ignore-dojis", "B6-intraday-iof",
    "new-position-trade-grading-fib", "A2-quick-run-through", "L12-sd-step-to-time-window", "L14-hold-above-reached-objective", "L12-bodies-hold-sd-continuation", "X2-best-case-resting-limit",
    "E1-manual-touch-exits", "X4-be-vi-then-new-ssl", "X4-be-without-partials", "X4-be-plus-cap-htf", "D14-be-after-adr-fraction", "X5-runner-stop-half-open-profit", "X5-day-trade-stop-no-trail",
    "X5-event-tight-lock-020", "X5-trail-after-protected-gap-confirmed",
)
P1 = dict(es_pt=1.0, lot=1, max_notional=1e12, pivot_n=1)


def pk(**kw):
    return Params(**{**P1, **kw})


# --- a one-minute book with the stub context ---------------------------------------------------------------------------------------------------------------

def mkctx(rows, t0=570, tf=1, d=D0, **kw):
    """rows = (o, h, l, c) real prices; bars from minute `t0` of day d. Both Sides are built (pivot_n 1) and registered in sides_map."""
    o, h, l, c = [np.array(x, float) for x in zip(*rows)]
    idx = pd.date_range(pd.Timestamp(f"{d} 00:00", tz=NY) + pd.Timedelta(minutes=t0), periods=len(rows), freq=f"{tf}min")
    t = np.array([x.hour * 60 + x.minute for x in idx])
    ctx = SimpleNamespace(o=o, h=h, l=l, c=c, t=t, idx=idx, tf=tf, start=0, day=d, hist=[], conf=None, nwog=[], nwog_today=False, bias_row=None)
    ctx.sides_map = {1: S.Side(1, o, h, l, c, 1, 0.0), -1: S.Side(-1, o, h, l, c, 1, 0.0)}
    ctx.__dict__.update(kw)
    return ctx


def mkpos(ctx, sign, fill_i, entry, stop, levels=(), fracs=(), kinds=None, n=10, **kw):
    """A position dict + a stub trade in SIDE space (entry / stop / levels given in REAL prices; sign -1 mirrors them)."""
    sd = ctx.sides_map[sign]
    x = sd.x
    fr = tuple(fracs) or ((1.0,) if len(levels) <= 1 else tuple(1.0 / len(levels) for _ in levels))
    tr = SimpleNamespace(exits=[], adds=[], lv_tags="", mgmt_tags="", session="AM", bz_top=None, bz_bottom=None, final_hit=False, resist_speed="", entry=entry, entry_time=ctx.idx[fill_i], side="long" if sign > 0 else "short")
    pos = dict(trade=tr, side=sd, stop=x(stop), left=n, n=n, basis=x(entry) * n, k=0, levels=[x(v) for v in levels], fracs=fr, level_kinds=list(kinds or ["pool"] * len(levels)), t1_done=False,
               last_partial_i=fill_i, fill_i=fill_i, fill_t=int(ctx.t[fill_i]), best=x(entry), ext=x(kw.pop("ext", entry - 5)), ext_i=max(0, fill_i - 2), fvg_bottom=x(entry) - 1.0, fvg_ce=x(entry) - 0.5,
               fvg_top=x(entry), kind="fvg", leg=None, runner=False, final_T=False, lvx={}, add=None, no_adds=False, ce_hold=False, be_done=False, away=None, draw=None, day_trade=False, rungs=[])
    pos.update(kw)
    return pos, tr, sd


def fill(ctx, sd, pos, tr, p, me1_data=None, **o):
    """me1.on_fill for the stub position (the order `o` carries ext_i and, optionally, the order-stage me1 data)."""
    o = dict(ext_i=pos["ext_i"], **o)
    if me1_data:
        o["me1"] = me1_data
    me1.on_fill(ctx, sd, pos, tr, o, pos["fill_i"], p, pos["basis"] / pos["n"])


def step(ctx, sd, pos, tr, p, i0, i1=None):
    """me1.manage for bars i0 .. i1 (inclusive); stops when the position is flat."""
    for i in range(i0, (i0 if i1 is None else i1) + 1):
        if not pos["left"]:
            break
        pos["best"] = max(pos["best"], float(sd.h[i]))
        me1.manage(ctx, sd, pos, tr, i, ctx.idx[i], p)


def reasons(tr):
    return [e[3] for e in tr.exits]


def flatrows(n, v=4000.0, w=0.3):
    return [(v, v + w, v - w, v)] * n


# --- defaults / validation / study variants ----------------------------------------------------------------------------------------------------------

def test_new_switch_defaults_and_validation():
    p = Params()
    assert all(getattr(p, k) is False for k in NEW_SWITCHES), "behaviour switches default off"
    assert (p.heavy_scale, p.lunch_retr_max, p.no_entry_0825, p.bpr_limit, p.breaker_mt_test, p.ce_exit, p.vi_mid_bars, p.stall_partial, p.resistance_def, p.resist_speed_bars, p.ifvg_fail_tf,
            p.pos_switch_frac, p.run_through_bars, p.run_through_ticks, p.sd_window, p.hold_tf, p.best_case_mult, p.best_case_bulk, p.exit_fill, p.exit_slip_ticks, p.be_mode, p.be_adr, p.runner_stop,
            p.runner_eq_after, p.day_mode_size) == (0.33, 0.3, True, "mt_body_close_abort", "close", "close", 2, 0.5, "swings", 3, 0, 0.5, 0, 2.0, (600, 720), 5, 1.0, 0.65, "touch", 1, "partial", 0.4, "",
                                                    0.75, 0.5)
    assert not me1.any_on(p) and me1.eff_params(p) is p
    for kw in (dict(bpr_limit="x"), dict(breaker_mt_test="x"), dict(ce_exit="x"), dict(resistance_def="x"), dict(exit_fill="x"), dict(be_mode="x"), dict(runner_stop="x"), dict(heavy_scale=1.0),
               dict(lunch_retr_max=0), dict(vi_mid_bars=0), dict(stall_partial=0), dict(resist_speed_bars=0), dict(run_through_bars=-1), dict(hold_tf=0), dict(best_case_bulk=1.5), dict(be_adr=0),
               dict(runner_eq_after=0), dict(day_mode_size=0), dict(pos_switch_frac=1.0), dict(sd_window=(720, 600)), dict(sd_time_roll=True, sd_body_hold=True)):
        with pytest.raises(ValueError):
            Params(**kw)
    assert me1.eff_params(Params(be_mode="adr_frac")).be_on == "off" and me1.eff_params(Params(be_cap_htf=True)).be_on == "off"
    # the Silver Bullet bias switches are untouched by this chunk
    assert Params().sb_model is False and "sb_use_bias" in Params.__dataclass_fields__ and "want_all_engines" in Params.__dataclass_fields__
    assert "speed_bars" in Params.__dataclass_fields__ and "resist_speed_bars" in Params.__dataclass_fields__


# --- BH-B14-NWOG-traverse-large-range (13) ---------------------------------------------------------------------------------------------------------------

def test_nwog_traverse_hold():
    rows = [(4105, 4106, 4104, 4105), (4105, 4130, 4105, 4106), (4106, 4107, 4099.5, 4101), (4101, 4103, 4100.5, 4102), (4102, 4104, 4101.5, 4103), (4103, 4111, 4102.5, 4110.5), (4110, 4112, 4109, 4111)]
    ctx = mkctx(rows, nwog=[(4100.0, 4110.0)])
    for flag in (False, True):
        p = pk(nwog_traverse_hold=flag)
        pos, tr, sd = mkpos(ctx, 1, 3, 4102.0, 4098.0, levels=(4105.0, 4120.0), fracs=(0.5, 0.5))
        fill(ctx, sd, pos, tr, p)
        step(ctx, sd, pos, tr, p, 4, 6)
        if flag:
            assert pos.get("expansion") and "nwog_traverse" in tr.mgmt_tags
            assert pos["levels"] == [4130.0] and pos["fracs"] == (1.0,)            # no T1 partial: the whole position runs to the next pool (the 4130 swing high)
        else:
            assert not pos.get("expansion") and pos["levels"] == [4105.0, 4120.0]


def test_nwog_traverse_short_and_locked_draw():
    # a short through the NWOG top-to-bottom: the mirror; under a locked draw the final target stays
    rows = [(4105, 4106, 4104, 4105), (4105, 4106, 4101, 4104), (4104, 4111, 4103, 4110), (4110, 4110.5, 4108, 4109), (4109, 4110, 4107, 4108), (4108, 4109, 4098, 4099), (4099, 4100, 4090, 4091)]
    ctx = mkctx(rows, nwog=[(4100.0, 4110.0)])
    p = pk(nwog_traverse_hold=True)
    pos, tr, sd = mkpos(ctx, -1, 3, 4108.0, 4113.0, levels=(4104.0, 4095.0), fracs=(0.5, 0.5), final_T=True)
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 4, 6)
    assert pos.get("expansion") and pos["fracs"] == (1.0,) and pos["levels"] == [sd.x(4095.0)]        # the locked draw (owner #9) is the one exact target


# --- BH-micro-BPR-tick-match-LOD (68) --------------------------------------------------------------------------------------------------------------------

def test_tick_match():
    h = np.array([4000.0, 4001.25, 4000.5, 4000.0]); l = np.array([3999.0, 4000.2, 3999.5, 4001.25])
    assert L.tick_match(h, l, 3, 0.25, 5) and L.tick_match_k(h, l, 3, 0.25, 5) == 1
    l2 = l.copy(); l2[3] = 4001.0                                          # one tick short: 4001.00 vs 4001.25 is no match
    assert not L.tick_match(h, l2, 3, 0.25, 5) and not L.tick_match(h, l, 3, 0.25, 1)
    assert L.tick_match(h, l, 3, 0.25, 5, zones=[(4000.0, 4002.0)]) and not L.tick_match(h, l, 3, 0.25, 5, zones=[(3990.0, 4000.5)])


def test_tick_match_hold_marks_lod_in(monkeypatch):
    # nine 1m bars = three 3m candles after the fill: candle 2's low equals candle 1's high (4001.25) inside a (stubbed) BPR; then a 3m close above the retrace high holds the trade
    c0 = [(4000, 4000.5, 3999.5, 4000)] * 3
    c1 = [(4000, 4001.25, 4000, 4001)] * 3                                 # candle 1: high 4001.25
    c2 = [(4001, 4001.0, 4001.25, 4001.5)]                                 # placeholder, replaced below
    c2 = [(4001, 4001.6, 4001.25, 4001.4), (4001.4, 4001.6, 4001.25, 4001.3), (4001.3, 4001.6, 4001.25, 4001.4)]     # candle 2: low 4001.25 (the tick match), high 4001.6
    c3 = [(4001.4, 4002.5, 4001.3, 4002.2)] * 3                             # candle 3 closes above the retrace high (4001.6)
    ctx = mkctx(c0 + c1 + c2 + c3)
    monkeypatch.setattr(L, "balanced_ranges", lambda *a, **k: [SimpleNamespace(bottom=4000.0, top=4003.0)])
    p = pk(tick_match_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3995.0, levels=(4010.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 2, 11)
    assert "lod_in" in tr.mgmt_tags and pos["me1"]["lod_hold"]
    p0 = pk(tick_match_hold=False)
    pos, tr, sd = mkpos(ctx, 1, 1, 4000.0, 3995.0, levels=(4010.0,))
    fill(ctx, sd, pos, tr, p0)
    step(ctx, sd, pos, tr, p0, 2, 11)
    assert "lod_in" not in tr.mgmt_tags


# --- B6-untouched-premium-arrays-heavy (79) --------------------------------------------------------------------------------------------------------------

def _siby_rows():
    """Real prices: a bearish FVG (SIBI) 4020-4030 formed above, then a drop to ~4010 (the short's entry area)."""
    rows = [(4033, 4034, 4030, 4031), (4031, 4031, 4021, 4022), (4022, 4020, 4015, 4016), (4016, 4017, 4010, 4011), (4011, 4012, 4009, 4010), (4010, 4011, 4008, 4009)]
    return rows


def test_heavy_gauge():
    rows = _siby_rows() + [(4009, 4010, 4005, 4006), (4006, 4026, 4005, 4007), (4007, 4008, 4000, 4001)]       # bar 7 wicks up to 4026 (past the SIBI's CE 4025)
    ctx = mkctx(rows)
    p = pk(heavy_gauge=True)
    pos, tr, sd = mkpos(ctx, -1, 5, 4009.0, 4040.0, levels=(3990.0,), fracs=(1.0,))
    fill(ctx, sd, pos, tr, p)
    assert pos["me1"]["arrs"] and abs(pos["me1"]["arrs"][0][2] - sd.x(4025.0)) < 1e-9
    step(ctx, sd, pos, tr, p, 6, 8)
    assert "heavy_scale" in reasons(tr) and tr.exits[0][2] == 3 and "heavy_scale" in tr.mgmt_tags         # 33 % of 10 units
    # no touch until the first rung: the T1 share is held and the trade is tagged 'heavy'
    rows2 = _siby_rows() + [(4009, 4010, 4005, 4006), (4006, 4012, 4005, 4007)]
    ctx2 = mkctx(rows2)
    pos, tr, sd = mkpos(ctx2, -1, 5, 4009.0, 4040.0, levels=(4000.0, 3990.0), fracs=(0.5, 0.5), kinds=["pool", "pool"])
    fill(ctx2, sd, pos, tr, p)
    d = pos["me1"]
    assert not d["heavy_touched"]
    assert me1.rung_hook(ctx2, sd, pos, tr, 0, pos["levels"], 0.0, 0.0, 6, ctx2.idx[6], p, 576, 1) == "skip" and "heavy" in tr.mgmt_tags and pos["fracs"] == (0.0, 1.0)


# --- T9-strong-am-no-lunch-retrace (209) -----------------------------------------------------------------------------------------------------------------

def test_no_lunch_retrace_hold():
    # the day's low 4000 at 09:30, the AM high 4040 by 11:59; lunch 12:00-13:00 low 4032 (20 % of the leg); the position is still open at 13:01 with the stop at 4032
    n = 13 * 60 + 5 - 570
    rows = []
    for k in range(n):
        m = 570 + k
        if m < 720:
            v = 4000 + 40 * (k / (720 - 570))
            rows.append((v, v + 0.5, v - 0.5, v))
        else:
            v = 4036
            rows.append((v, v + 0.5, 4032.0 if m == 750 else v - 0.5, v))
    ctx = mkctx(rows)
    p = pk(no_lunch_retrace_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 2, 4001.0, 3995.0, levels=(4100.0,))
    pos["fill_t"] = 572
    fill(ctx, sd, pos, tr, p)
    for i in range(3, len(rows)):
        t = int(ctx.t[i])
        if t + 1 >= 720:                                    # the engine's am_exit gate
            assert me1.am_exit_hold(ctx, sd, pos, tr, i, ctx.idx[i], p, 720) is True
            assert pos["me1"]["lunch"] == ("wait" if t + 1 < 780 else "held") and pos["left"] == 10
    assert pos["stop"] == pytest.approx(4032.0) and "lunch_hold" in tr.mgmt_tags
    # still held at 15:50: the position leaves at the close of the 15:49 bar (the engine's 15:50 exit)
    rows2 = rows + [(4036, 4036.5, 4035.5, 4036)] * (950 - 780)
    ctx2 = mkctx(rows2)
    pos2, tr2, sd2 = mkpos(ctx2, 1, 2, 4001.0, 3995.0, levels=(4100.0,))
    fill(ctx2, sd2, pos2, tr2, p)
    for i in range(3, len(rows2)):
        if ctx2.t[i] + 1 >= 720:
            me1.am_exit_hold(ctx2, sd2, pos2, tr2, i, ctx2.idx[i], p, 720)
        if not pos2["left"]:
            break
    assert reasons(tr2) == ["lunch_hold_exit"] and ctx2.t[i] + 1 == 950


def test_no_lunch_retrace_hold_closes_when_the_lunch_retraces():
    n = 12 * 60 + 65 - 570
    rows = []
    for k in range(n):
        m = 570 + k
        v = 4000 + 40 * (k / 150) if m < 720 else (4020 if m == 750 else 4036)
        rows.append((v, v + 0.5, v - 0.5, v))
    ctx = mkctx(rows)
    p = pk(no_lunch_retrace_hold=True)
    pos, tr, sd = mkpos(ctx, 1, 2, 4001.0, 3995.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    ii = [i for i in range(3, len(rows)) if ctx.t[i] + 1 >= 720]
    out = [me1.am_exit_hold(ctx, sd, pos, tr, i, ctx.idx[i], p, 720) for i in ii]
    first_false = ii[out.index(False)]
    assert ctx.t[first_false] + 1 == 780 and all(out[:out.index(False)]) and pos["me1"]["lunch"] == "no"      # a 50 % lunch retrace: the 13:00 close (the engine closes when this returns False)
    # a weak AM (no rally from the low) does not wait at all
    rows2 = [(4000, 4000.5, 3999.5, 4000)] * 200
    ctx2 = mkctx(rows2)
    pos2, tr2, sd2 = mkpos(ctx2, 1, 2, 4000.0, 3995.0, levels=(4100.0,))
    fill(ctx2, sd2, pos2, tr2, p)
    assert me1.am_exit_hold(ctx2, sd2, pos2, tr2, 190, ctx2.idx[190], p, 720) is False


# --- N5-hold-through-0830 (11) ----------------------------------------------------------------------------------------------------------------------------

def test_flat_before_0830():
    from claude_hf.daytypes import events
    from mentorship import calendar as C
    ppi = next(d for d in (date(2023, 5, 11), date(2023, 6, 14), date(2023, 7, 14)) if "ppi" in events(d))
    cpi = next(d for d in (date(2023, 5, 10), date(2023, 6, 13), date(2023, 7, 12)) if "cpi" in events(d))
    p = pk()
    assert me1.release_0830(ppi, p) and me1.flat_0830(ppi, p) and me1.flat_0830(cpi, p) and not me1.flat_0830(D0, p)
    q = pk(hold_through_0830=True)
    assert not me1.flat_0830(ppi, q) and me1.flat_0830(cpi, q)                          # jobs and CPI days stay excluded from the hold
    assert me1.entry_cut_0825(ppi, p, "PRE8") == 505 and me1.entry_cut_0825(ppi, q, "PRE8") is None and me1.entry_cut_0825(cpi, q, "PRE8") == 505
    assert me1.entry_cut_0825(ppi, pk(no_entry_0825=False), "PRE8") is None and me1.entry_cut_0825(ppi, p, "AM") is None and me1.entry_cut_0825(D0, p, "PRE8") is None
    # jobless claims: a Thursday 08:30 release, only with news_claims (the rule-based calendar already has them)
    thu = date(2023, 6, 15)
    assert 510 in C.release_times(thu, claims=True) and not me1.release_0830(thu, p) and me1.release_0830(thu, pk(news_claims=True))


# --- N10-thursday-caps-week (58) --------------------------------------------------------------------------------------------------------------------------

def test_thu_cap():
    thu = date(2026, 6, 25)
    assert thu.weekday() == 3
    rows = [(4000, 4001, 3999, 4000)] * 40
    ctx = mkctx(rows, t0=540, d=thu)          # 09:00 .. 09:39
    p = pk(thu_cap=True)
    pos, tr, sd = mkpos(ctx, 1, 2, 4000.0, 3990.0, levels=(4100.0,))
    pos["fill_t"] = 542                       # entered before 09:30
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 3, 39)
    assert pos["left"] == 10                  # 10:00 is not reached in the book
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 80, t0=540, d=thu)           # to 10:19
    pos, tr, sd = mkpos(ctx, 1, 2, 4000.0, 3990.0, levels=(4100.0,))
    pos["fill_t"] = 542
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 3, 79)
    assert reasons(tr) == ["thu_cap"] and ctx.t[[i for i in range(80) if ctx.idx[i] == tr.exits[0][0]][0]] == 599 and "thu_cap" in tr.mgmt_tags
    # a Wednesday, or a position entered after 09:30, is not capped
    wed = date(2026, 6, 24)
    ctx = mkctx([(4000, 4001, 3999, 4000)] * 80, t0=540, d=wed)
    pos, tr, sd = mkpos(ctx, 1, 2, 4000.0, 3990.0, levels=(4100.0,))
    fill(ctx, sd, pos, tr, p)
    step(ctx, sd, pos, tr, p, 3, 79)
    assert pos["left"] == 10


def test_thu_week_extreme_blocks_entries():
    thu = date(2026, 6, 25)
    # the week's prior days reach 4050; Thursday 09:30-10:00 makes a new high 4060 inside a daily bearish array 4055-4065
    rows = [(4040, 4041, 4039, 4040)] * 5 + [(4040, 4060, 4040, 4059)] + [(4059, 4059.5, 4058, 4058.5)] * 3
    prev = pd.DataFrame({"open": 4000.0, "high": 4050.0, "low": 3990.0, "close": 4040.0}, index=pd.date_range(f"2026-06-23 09:30", periods=3, freq="5min", tz=NY))
    ctx = mkctx(rows, t0=570, d=thu, hist=[prev])

    class Conf:
        def at(self, t, price, side):
            return ["D"] if (side == -1 and 4055 <= price <= 4065) else []
    ctx.conf = Conf()
    p = pk(thu_cap=True)
    sd_long, sd_short = ctx.sides_map[1], ctx.sides_map[-1]
    assert me1.thu_block(ctx, sd_long, 8, p, "AM") == "x_thu_week_ext"                 # no further long (the direction of the extreme)
    assert me1.thu_block(ctx, sd_short, 8, p, "AM") is None
    assert me1.thu_block(ctx, sd_long, 8, pk(), "AM") is None
    ctx.conf = SimpleNamespace(at=lambda t, price, side: [])
    assert me1.thu_block(ctx, sd_long, 8, p, "AM") is None                              # not into a daily array
