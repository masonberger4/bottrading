"""silver_bullet package (sb_model.py): the 12 rule_coverage items, the caption-verified gaps of
rulebook_gaps/silver_bullet.md and the direction filters (draw first / one way per day, displacement size,
ES/NQ/YM sync, spotty-day skip, weekly profile).

Synthetic days run through run_day (the real engine path, 5m bars, es_pt = 1.0), unit tests on sb_model._arm /
windows / the day reads, and look-ahead runs (full vs truncated) for every switch group. The databento tests skip
when the ES data is missing. The Silver Bullet itself stays OFF by default (sb_model=False)."""
import warnings
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mentorship import backtest as B, calendar as C, levels as L, sb_model, strategy as S
from mentorship.strategy import Params

NY = "America/New_York"
ES = Path("data/mentorship/ES_5min_db.csv").exists() and Path("data/mentorship/ES_1min_dbraw.csv").exists()
ES1 = Path("data/mentorship/ES_1min_db.csv").exists()
FUT = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.1)
D0 = date(2026, 6, 23)                      # a Tuesday: no release, no NFP / FOMC week

# engine settings that keep a hand-made day readable; the Silver Bullet alone, no lock / cap / wick levels
BASE = dict(es_pt=1.0, lot=1, max_notional=1e12, cost_per_share=0.0, use_bias=False, adds=(), ladder_by_day=False,
            session_close=975, slow_frac=0.0, draw_lock="off", htf_resist_cap=False, news_wait="off",
            min_draw_pts=0.0, leg_pd=0.0, wick_levels=False, org_days=0, am=(0, 0), pm=(0, 0), sb_model=True,
            sb_pw_pools=False)


def P(**kw):
    return Params(**{**BASE, **kw})


def frame(d, rows, tf=5, start="00:00"):
    idx = pd.date_range(pd.Timestamp(f"{d} {start}", tz=NY), periods=len(rows), freq=f"{tf}min")
    a = np.array(rows, float)
    return pd.DataFrame({"open": a[:, 0], "high": a[:, 1], "low": a[:, 2], "close": a[:, 3], "volume": 1.0}, index=idx)


def mk(blocks, d=D0, base=100.0, w=0.2, spike=False):
    """A 00:00-16:15 5m day: flat at `base` (+-w) until the first block, each block (HH:MM, rows) overwrites its
    bars, flat at the last close in between and after."""
    n = 975 // 5
    put = {}
    for start, rows in blocks:
        m0 = int(start[:2]) * 60 + int(start[3:])
        for j, r in enumerate(rows):
            put[m0 + 5 * j] = r
    first = min(put)
    out, last = [], base
    for k in range(n):
        m = 5 * k
        if m in put:
            out.append(put[m]); last = put[m][3]
        elif m < first:
            out.append((base, base + w, base - w, base))
        else:
            out.append((last, last + 0.1, last - 0.1, last))
    if spike:
        out[36] = (base, base + 2.5, base - 0.1, base)
    return frame(d, out)


def rth_day(d, o, h, l, c, tf=5):
    n = 390 // tf
    rows = [(o, o + 0.1, o - 0.1, o)] + [(o, h, l, c)] + [(c, c + 0.1, c - 0.1, c)] * (n - 2)
    return frame(d, rows, tf, "09:30")


def history(d=D0, n=8, hi=108.0, lo=90.0, close=100.0, week=None):
    """n prior regular sessions (oldest first); `week` = {weekday: (o, h, l, c)} overrides this week's days."""
    out, x = [], pd.Timestamp(d)
    while len(out) < n:
        x -= pd.Timedelta(days=1)
        if C.is_trading_day(x.date()):
            out.append(x.date())
    out = out[::-1]
    res = []
    for k, x in enumerate(out):
        o, h, l, c = close, hi, lo, close
        if week and x.weekday() in week and x.isocalendar()[:2] == d.isocalendar()[:2]:
            o, h, l, c = week[x.weekday()]
        res.append(rth_day(x, o, h, l, c))
    return res


def run(df, hist, p, partner=None, partner2=None, rows=None, **kw):
    locks, log, skips = [], [], []
    tr = S.run_day(df, hist, "ES", p, 5, partner=partner, partner2=partner2, locks=locks, log=log, skips=skips,
                   bias_by_cut=rows or {}, **kw)
    return tr, locks, skips


# The base long Silver Bullet (side +1): a down leg at 09:30-09:55 to 98.5, a displacement at 10:00 closing above the swing
# high 100.9 (MSS) and leaving a 1m-style FVG 101.4-101.7 at 10:10, the retrace to 101.5 at 10:15, then a run into the PDH.
ROWS = [(100.0, 100.6, 99.9, 100.5), (100.5, 100.9, 100.3, 100.8), (100.8, 100.8, 99.6, 99.7), (99.7, 99.8, 98.9, 99.0),
        (99.0, 99.1, 98.5, 98.6), (98.6, 99.4, 98.55, 99.3), (99.3, 101.4, 99.2, 101.3), (101.3, 102.0, 101.0, 101.9),
        (101.9, 102.6, 101.7, 102.5), (102.5, 102.6, 101.5, 101.6), (101.6, 104.0, 101.5, 103.9), (103.9, 108.6, 103.8, 108.5)]


def one(blocks=None, p=None, hist=None, base=100.0, **kw):
    df = mk(blocks or [("09:30", ROWS)], base=base)
    tr, locks, skips = run(df, hist or history(), p or P(), **kw)
    return tr


def minute(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:])


def actx(blocks, p, hist=None, d=D0, sign=1, base=100.0):
    """A DayCtx and the side (+1 / -1) for direct sb_model._arm_all calls."""
    df = mk(blocks, d, base=base)
    hist = hist or history(d)
    ctx = S.DayCtx(df, d, hist, 5)
    S._setup_news(ctx, d, p)
    ctx.equity, ctx.conf, ctx.hist = p.account_equity, None, hist
    sd = S.Side(sign, ctx.o, ctx.h, ctx.l, ctx.c, p.pivot_n, p.min_fvg_pts * p.es_pt)
    return ctx, sd


def arm(blocks, p, at="10:10", lock=None, ds=None, hist=None, sign=1, base=100.0, win_a=600, k0_at="09:30", **kw):
    """Orders (list) armed on the closed bar starting `at`."""
    ctx, sd = actx(blocks, p, hist, sign=sign, base=base)
    i, k0 = S._idx_at(ctx, minute(at)), S._idx_at(ctx, minute(k0_at))
    return sb_model._arm_all(ctx, sd, i, k0, p, 0.5, lock, "AM", win_a, (), None, ds, **kw)


def shifted(rows, bars):
    """The same bars `bars` 5m steps later (flat prelude at the first open)."""
    o = rows[0][0]
    return [(o, o + 0.1, o - 0.1, o)] * bars + list(rows)


def mirror(rows, k=300.0):
    return [(k - o, k - l, k - h, k - c) for o, h, l, c in rows]


# --- defaults and validation -----------------------------------------------------------------------------------------

def test_silver_bullet_is_off_by_default_and_switches_default_to_the_old_behaviour():
    p = Params()
    assert p.sb_model is False
    old = dict(sb_last_hour=False, sb_0700=False, sb_extra=(), sb_moc_extra=False, sb_one_per_day=False,
               sb_cascade=False, sb_one_market=False, sb_max_per_window=1, sb_adds=False, sb_am_done=False,
               sb_draw_first=False, sb_ote_draw=False, sb_htf_fallback=False, sb_htf_targets=False, sb_use_bias=False,
               sb_day_dir="off", sb_weekly="off", sb_sync="off", sb_spotty="off", sb_disp_pts=0.0, sb_disp_leg_pts=0.0,
               sb_disp_range_mult=0.0, sb_mss_required=True, sb_need_mss=True, sb_fvg_in_window=False, sb_fvg_from=0,
               sb_evolve=True, sb_fvg_pick="evolving", sb_need_sweep=False, sb_sweep_max_pts=0.0, sb_sweep_alt="",
               sb_bpr_exclude=False, sb_cons_wait=False, sb_lrc_mult=0.0, sb_premise="", sb_nwog_expansion="",
               sb_entry_arrays=("fvg",), sb_ifvg="", sb_reverse_after_target=False, sb_cancel_ticks=0, sb_simple=False,
               sb_stop="fvg_ob", sb_max_stop_pts=0.0, sb_abort=False, sb_room_mode="exit", sb_room_overshoot_pts=0.0,
               sb_room_untaken=False, sb_org_chop=False, sb_imm_tag=False, sb_runner_if_weekly=False,
               sb_supercharge=False, sb_mgmt="fixed", sb_entry="edge")
    for k, v in old.items():
        assert getattr(p, k) == v, k
    assert p.sb_pw_pools is True                       # the spec's one default change (054 draw list has PWH / PWL)


@pytest.mark.parametrize("kw", [dict(sb_mgmt="x"), dict(sb_fvg_pick="x"), dict(sb_day_dir="x"), dict(sb_weekly="x"),
                                dict(sb_sync="x"), dict(sb_spotty="x"), dict(sb_stop="x"), dict(sb_wide="x"),
                                dict(sb_premise="x"), dict(sb_ifvg="x"), dict(sb_extra=("x",)),
                                dict(sb_entry_arrays=("x",)), dict(sb_spotty_tests=("x",)), dict(sb_max_per_window=0),
                                dict(sb_gap424_fracs=(0.5, 0.2)), dict(sb_lh_window=(950, 900)),
                                dict(sb_room_mode="x"), dict(sb_lrc_mode="x"), dict(sb_nwog_expansion="x")])
def test_params_reject_bad_silver_bullet_values(kw):
    with pytest.raises(ValueError):
        Params(**kw)


def test_windows_list_t6_and_m31():
    p = Params(sb_london=True, sb_0700=True, sb_last_hour=True, sb_moc_extra=True)
    w = {x.name: x for x in sb_model.windows(p)}
    assert [x.name for x in sb_model.windows(p)] == ["london", "0700", "am", "pm", "lh", "moc"]
    assert (w["london"].a, w["london"].b) == (180, 240)
    assert (w["0700"].a, w["0700"].b, w["0700"].flat) == (420, 510, 509)          # T6: flat 08:29
    assert (w["lh"].a, w["lh"].b) == (900, 950)                                    # owner #1: entries to 15:50
    assert (w["moc"].a, w["moc"].b) == (915, 945)
    assert [x.name for x in sb_model.windows(Params())] == ["am", "pm"]
    q = {x.name: x for x in sb_model.windows(Params(sb_extra=("pm2", "early"), sb_max_per_window=1))}
    assert q["pm"].max_n == 2 and q["am"].a == 590 and q["am"].max_n == 1


# --- the base setup (M3) ---------------------------------------------------------------------------------------------

def test_base_long_silver_bullet_fills_at_the_fvg_edge_and_exits_at_the_draw():
    tr = one()
    assert len(tr) == 1
    t = tr[0]
    assert (t.setup, t.side, t.session, t.entry_kind, t.sb_win, t.sb_n) == ("sb_am", "long", "AM", "fvg", "am", 1)
    assert str(t.entry_time)[11:16] == "10:15" and t.entry == 101.7                  # limit at the FVG near edge
    assert t.stop == pytest.approx(98.95)                                            # below the FVG's first candle (090) - pad
    assert [(e[3], e[1]) for e in t.exits] == [("t1", 108.25)]                       # AT the draw, not +5 (owner #2)
    assert t.swept == "pml"


def test_look_ahead_free_full_vs_truncated_base_day():
    df = mk([("09:30", ROWS)])
    full = run(df, history(), P())[0]
    cut = df[df.index <= pd.Timestamp(f"{D0} 10:20", tz=NY)]
    part = run(cut, history(), P(), live=True)[0]
    assert len(full) == len(part) == 1
    for k in ("entry", "stop", "t1"):
        assert getattr(full[0], k) == getattr(part[0], k)


def test_mirror_short_is_the_same_trade():
    tr = one([("09:30", mirror(ROWS))], hist=history(close=200.0, hi=210.0, lo=192.0), p=P(), base=200.0)
    assert len(tr) == 1 and tr[0].side == "short"
    assert tr[0].entry == pytest.approx(300 - 101.7) and tr[0].stop == pytest.approx(300 - 98.95)


# --- M3 umbrella / M3.3: the trigger ---------------------------------------------------------------------------------

def test_sb_mss_not_required_arms_on_displacement_and_fvg_alone():
    # swing high 102.2; the displacement never closes above it, but leaves an FVG 100.8-101.1 (044 ~0:50: displacement + FVG)
    rows = [ROWS[0], (100.5, 102.2, 100.3, 100.8)] + ROWS[2:6] + [
        (99.3, 100.8, 99.2, 100.7), (100.7, 101.4, 100.5, 101.2), (101.2, 101.5, 101.1, 101.3),
        (101.3, 101.4, 100.8, 101.0), (101.0, 104.0, 100.7, 103.9), (103.9, 108.6, 103.8, 108.5)]
    assert arm([("09:30", rows)], P(sb_room_pts=1.0), at="10:10") == []    # (the opening-range high 102.2 is the draw)
    for kw in (dict(sb_mss_required=False), dict(sb_need_mss=False)):
        o = arm([("09:30", rows)], P(sb_room_pts=1.0, **kw), at="10:10")
        assert len(o) == 1 and "sb_no_mss" in o[0]["lv_tags"] and o[0]["entry"] == 101.1
    # a run-level fill: the long order fills at 10:15 when the direction is fixed (here the side lock of sb_draw_first)
    tr = one([("09:30", rows)], P(sb_mss_required=False, sb_draw_first=True, sb_room_pts=1.0))
    assert [t.side for t in tr] == ["long"] and tr[0].entry == 101.1


def test_sb_mss_mode_wick_counts_a_wick_through_the_swing():
    # D2: mss_mode "wick" - a wick to 101.0 (above the swing high 100.9) at 10:00 is the break (a close break comes at 10:05)
    rows = ROWS[:6] + [(99.3, 101.0, 99.2, 100.7), (100.7, 101.6, 100.5, 101.5), (101.5, 102.4, 101.5, 102.3),
                       (102.3, 102.4, 101.4, 101.6), (101.6, 104.0, 101.4, 103.9), (103.9, 108.6, 103.8, 108.5)]
    ctx, sd = actx([("09:30", rows)], P())
    c_ = arm([("09:30", rows)], P(mss_mode="close"), at="10:10")[0]
    w_ = arm([("09:30", rows)], P(mss_mode="wick"), at="10:10")[0]
    assert c_["entry"] == w_["entry"] == 101.5
    assert S._idx_at(ctx, 605) == c_["kb"] and S._idx_at(ctx, 600) == w_["kb"]


# --- D2 / gap 16: which FVG, where it may form ------------------------------------------------------------------------

# the FVG forms BEFORE 10:00 (the 09:30-10:00 leg, 058 ~44:37; 065B ~5:15) and fills at 10:00
EARLY = [(100.0, 100.9, 100.0, 100.8), (100.8, 100.8, 99.6, 99.7), (99.7, 99.8, 98.9, 99.0), (99.0, 99.1, 98.5, 98.6),
         (98.6, 101.2, 98.55, 101.1), (101.1, 101.5, 101.0, 101.4), (101.4, 101.5, 100.8, 101.0),
         (101.0, 104.0, 100.9, 103.9), (103.9, 108.6, 103.8, 108.5)]
# three FVGs in the leg up: [99.1, 101.0] 09:55, [101.2, 101.5] 10:00, [101.5, 103.0] 10:05; a retrace to 102.4 at 10:10
THREE = EARLY[:6] + [(101.5, 103.5, 101.5, 103.4), (103.4, 103.9, 103.0, 103.8), (103.8, 103.9, 102.4, 102.6),
                     (102.6, 108.7, 102.5, 108.6)]


def test_d2_fvg_may_come_from_the_0930_leg_and_sb_fvg_in_window_restricts_it():
    tr = one([("09:30", EARLY)])
    assert len(tr) == 1 and str(tr[0].entry_time)[11:16] == "10:00" and tr[0].entry == 101.0    # formed 09:55, filled 10:00
    assert one([("09:30", EARLY)], P(sb_fvg_in_window=True)) == []                           # 044 / 047 / 054 early wording
    assert len(one([("09:30", EARLY)], P(sb_fvg_from=585))) == 1                              # FVG candle 1 at 09:45
    assert one([("09:30", EARLY)], P(sb_fvg_from=590)) == []


def test_gap16_fvg_pick_evolving_first_any_in_leg():
    e = one([("09:30", THREE)])
    assert len(e) == 1 and e[0].entry == 103.0                                                # evolving: the newest FVG
    assert one([("09:30", THREE)], P(sb_fvg_pick="first")) == []                              # the oldest (101.0), never reached
    assert one([("09:30", THREE)], P(sb_evolve=False)) == []                                  # D2 sb_evolve off = first
    a = one([("09:30", THREE)], P(sb_fvg_pick="any_in_leg"))
    assert len(a) == 1 and a[0].entry == 103.0                                                # the nearest limit hit first
    # deeper retrace to 101.0: first fills the 100.9? no - 101.0 stays above it; any_in_leg fills the highest limit hit
    rows = THREE[:7] + [(103.4, 103.9, 103.0, 103.8), (103.8, 103.9, 101.3, 101.6), (101.6, 108.7, 101.5, 108.6)]
    a = one([("09:30", rows)], P(sb_fvg_pick="any_in_leg"))
    assert [t.entry for t in a] == [103.0]
    f = arm([("09:30", THREE)], P(sb_fvg_pick="first", sb_room_pts=0.5), at="10:05")
    assert [o["entry"] for o in f] == [101.0]
    f = arm([("09:30", THREE)], P(sb_fvg_pick="any_in_leg", sb_room_pts=0.5), at="10:05")
    assert sorted(o["entry"] for o in f) == [101.0, 101.5, 103.0]


def test_gap6_bpr_exclude_drops_fvgs_below_the_break_level():
    # the leg down left a SIBI [99.1, 99.6]; the first bullish FVG [99.1, 101.0] reaches below the swing high 100.9 it must clear
    f = arm([("09:30", THREE)], P(sb_fvg_pick="first", sb_bpr_exclude=True, sb_room_pts=0.5), at="10:05")
    assert [o["entry"] for o in f] == [101.5]                                                  # the next one above the break
    f = arm([("09:30", THREE)], P(sb_fvg_pick="any_in_leg", sb_bpr_exclude=True, sb_room_pts=0.5), at="10:05")
    assert sorted(o["entry"] for o in f) == [101.5, 103.0]


def test_gap18_large_range_candle_flag_tag_skip_wait():
    # the candle before the displacement (09:50, range 2.65) is >= 2 x the mean range: the 10:00 FVG [101.2, 101.5] is flagged
    f = arm([("09:30", THREE)], P(sb_lrc_mult=2.0, sb_lrc_mode="tag", sb_room_pts=0.5), at="10:00")
    assert len(f) == 1 and f[0]["entry"] == 101.5 and "sb_lrc" in f[0]["lv_tags"]
    f = arm([("09:30", THREE)], P(sb_lrc_mult=2.0, sb_lrc_mode="skip", sb_room_pts=0.5), at="10:00")
    assert [o["entry"] for o in f] == [101.0]                                                  # the unflagged older FVG instead
    f = arm([("09:30", THREE)], P(sb_lrc_mult=2.0, sb_lrc_mode="wait", sb_room_pts=0.5), at="10:00")
    assert len(f) == 1 and f[0]["entry"] == 101.5                                              # not the first FVG: armed
    f = arm([("09:30", EARLY)], P(sb_lrc_mult=1.1, sb_lrc_mode="wait"), at="09:55")
    assert f == []                                                                             # the first FVG is flagged: wait
    assert arm([("09:30", EARLY)], P(sb_lrc_mult=1.1, sb_lrc_mode="tag"), at="09:55")[0]["lv_tags"].count("sb_lrc") == 1


# consolidation 10:00-10:15 (range 1.0, a 0.3 FVG inside it), then a displacement out at 10:20 leaving [102.5, 102.9]
CONS = ROWS[:6] + [(99.3, 99.7, 99.2, 99.6), (99.6, 99.65, 99.5, 99.7), (99.7, 99.8, 99.4, 99.5),
                   (99.5, 100.2, 99.95, 100.1), (100.1, 102.5, 100.0, 102.4), (102.4, 103.4, 102.2, 103.2),
                   (103.2, 103.6, 102.9, 103.5), (103.5, 103.6, 102.7, 102.8), (102.8, 108.7, 102.6, 108.6)]


def test_gap21_wait_for_displacement_out_of_the_consolidation():
    p = dict(sb_cons_bars=4, sb_mss_required=False, sb_room_pts=0.5, min_risk_pts=0.5)
    f = arm([("09:30", CONS)], P(**p), at="10:15")
    assert [o["entry"] for o in f] == [99.95]                                                  # the FVG inside the range
    assert arm([("09:30", CONS)], P(sb_cons_wait=True, **p), at="10:15") == []                 # does not count (072 ~35:41)
    f = arm([("09:30", CONS)], P(sb_cons_wait=True, sb_cons_bars=4), at="10:30")
    assert [o["entry"] for o in f] == [102.9]                                                  # the displacement's FVG
    tr = one([("09:30", CONS)], P(sb_cons_wait=True, sb_cons_bars=4, sb_draw_first=True))
    assert len(tr) == 1 and tr[0].entry == 102.9


def test_displacement_size_filter():
    assert len(arm([("09:30", ROWS)], P(sb_disp_pts=1.5))) == 1                                # MSS candle body 2.0
    assert arm([("09:30", ROWS)], P(sb_disp_pts=2.5)) == []
    assert len(arm([("09:30", ROWS)], P(sb_disp_leg_pts=2.5))) == 1                            # 98.5 -> 101.3 close = 2.8
    assert arm([("09:30", ROWS)], P(sb_disp_leg_pts=3.0)) == []
    assert len(arm([("09:30", ROWS)], P(sb_disp_range_mult=3.0))) == 1                         # range 2.2 vs ~0.5 before
    assert arm([("09:30", ROWS)], P(sb_disp_range_mult=8.0)) == []
