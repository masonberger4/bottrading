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
            sb_pw_pools=False, sloppy_mode="off")


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


class SimpleNS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def history(d=D0, n=8, hi=108.0, lo=90.0, close=100.0, week=None, over=None):
    """n prior regular sessions (oldest first); `week` = {weekday: (o, h, l, c)} overrides this week's days, `over` =
    {date: (o, h, l, c)} any day."""
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
        if over and x in over:
            o, h, l, c = over[x]
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
    ctx = S.DayCtx(df, d, hist, 5, or_minutes=p.or_minutes)
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
    p = Params(sb_london=True, sb_0700=True, sb_last_hour=True)
    w = {x.name: x for x in sb_model.windows(p)}
    assert [x.name for x in sb_model.windows(p)] == ["london", "0700", "am", "pm", "lh"]
    w["moc"] = {x.name: x for x in sb_model.windows(Params(sb_moc_extra=True))}["moc"]
    assert [x.name for x in sb_model.windows(Params(sb_last_hour=True, sb_moc_extra=True))] == ["am", "pm", "lh"]   # lh covers moc
    assert (w["london"].a, w["london"].b) == (180, 240)
    assert (w["0700"].a, w["0700"].b, w["0700"].flat) == (420, 510, 509)          # T6: flat 08:29
    assert (w["lh"].a, w["lh"].b) == (900, 950)                                    # owner #1: entries to 15:50
    assert (w["moc"].a, w["moc"].b) == (915, 945)
    assert [x.name for x in sb_model.windows(Params())] == ["am", "pm"]
    q = {x.name: x for x in sb_model.windows(Params(sb_extra=("pm2", "early"), sb_max_per_window=1))}
    assert q["pm"].max_n == 2 and q["am"].a == 590 and q["am"].max_n == 1
    q = {x.name: x for x in sb_model.windows(Params(sb_extra=("early",), sb_early_start=585, sb_0700=True, sb_0700_window=(430, 500),
                                                   sb_moc_extra=True, sb_moc_window=(920, 940)))}
    assert q["am"].a == 585 and (q["0700"].a, q["0700"].b) == (430, 500) and (q["moc"].a, q["moc"].b) == (920, 940)


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


# --- T6 / M3.1 windows ------------------------------------------------------------------------------------------------

def test_t6_london_window_03_to_04():
    tr = one([("02:30", ROWS)], P(sb_london=True))
    assert len(tr) == 1 and (tr[0].setup, tr[0].sb_win, tr[0].session) == ("sb_london", "london", "AM")
    assert str(tr[0].entry_time)[11:16] == "03:15" and tr[0].exits[-1][3] == "t1"
    assert one([("02:30", ROWS)]) == []                                                       # off by default


def test_t6_0700_window_flat_at_0829():
    # the FVG fills at 07:15; the target is not reached, so the trade is flat before the 08:30 release
    tr = one([("06:30", ROWS[:10])], P(sb_0700=True))
    assert len(tr) == 1 and tr[0].setup == "sb_0700" and str(tr[0].entry_time)[11:16] == "07:15"
    assert tr[0].exits[-1][3] == "eod" and str(tr[0].exits[-1][0])[11:16] == "08:25"
    tr = one([("06:30", ROWS)], P(sb_0700=True))
    assert tr[0].exits[-1][3] == "t1"
    assert one([("06:30", ROWS)]) == []


def test_t6_last_hour_window_15_to_1550():
    tr = one([("14:30", ROWS)], P(sb_last_hour=True))
    assert len(tr) == 1 and (tr[0].setup, tr[0].sb_win, tr[0].session) == ("sb_lh", "lh", "PM")
    assert str(tr[0].entry_time)[11:16] == "15:15"
    assert one([("14:30", ROWS)]) == []                                                       # the PM window ends at 15:00
    # a fill at 15:55 is outside the 15:00-15:50 entries (owner #1): the same shape 40 minutes later is not taken
    assert one([("15:10", ROWS[:10])], P(sb_last_hour=True)) == []


def test_gap14_moc_window_only_while_the_pm_draw_is_not_delivered():
    tr = one([("14:45", ROWS)], P(sb_moc_extra=True))
    assert len(tr) == 1 and (tr[0].setup, tr[0].sb_win) == ("sb_moc", "moc") and str(tr[0].entry_time)[11:16] == "15:30"
    assert one([("14:45", ROWS)]) == []
    # a PM Silver Bullet that reached its target (13:30 block) shuts the extra window
    both = one([("13:30", ROWS), ("14:45", ROWS)], P(sb_moc_extra=True))
    assert [t.setup for t in both] == ["sb_pm"]


# --- M3 count: per window, per day, cascade ---------------------------------------------------------------------------

# the first entry (10:15) is stopped out at 10:20, a new low, MSS and FVG [102.5, 102.9] follow: a second entry fills 10:45
ROWS2 = ROWS[:10] + [(101.6, 101.7, 98.0, 98.2), (98.2, 98.5, 98.0, 98.4), (98.4, 102.5, 98.3, 102.4),
                     (102.4, 103.2, 102.2, 103.1), (103.1, 103.6, 102.9, 103.5), (103.5, 103.6, 102.8, 102.95),
                     (102.95, 108.7, 102.9, 108.6)]


def test_gap14_max_per_window_and_pm2():
    one1 = one([("09:30", ROWS2)])
    assert [(t.entry, t.exits[-1][3]) for t in one1] == [(101.7, "stop")]
    two = one([("09:30", ROWS2)], P(sb_max_per_window=2))
    assert [(t.entry, t.sb_n, t.exits[-1][3]) for t in two] == [(101.7, 1, "stop"), (102.9, 2, "t1")]
    assert [t.sb_win for t in two] == ["am", "am"]
    pm = one([("13:30", ROWS2)], P(sb_extra=("pm2",)))                                       # 056: PM "two chances"
    assert [t.sb_n for t in pm] == [1, 2]
    assert len(one([("13:30", ROWS2)])) == 1
    assert len(one([("09:30", ROWS2)], P(sb_extra=("pm2",)))) == 1                           # pm2 is PM only


def test_m3_one_per_day_and_cascade_over_the_windows():
    blocks = [("09:30", ROWS), ("13:30", ROWS)]
    assert [t.setup for t in one(blocks)] == ["sb_am", "sb_pm"]
    assert [t.setup for t in one(blocks, P(sb_one_per_day=True))] == ["sb_am"]
    assert [t.setup for t in one(blocks, P(sb_cascade=True))] == ["sb_am"]                    # 054 ~18:01 London, else AM, else PM
    lon = [("02:30", ROWS), ("09:30", ROWS)]
    assert [t.setup for t in one(lon, P(sb_london=True))] == ["sb_london", "sb_am"]
    assert [t.setup for t in one(lon, P(sb_london=True, sb_cascade=True))] == ["sb_london"]


def test_gap14_adds_on_a_return_into_the_filled_fvg():
    rows = ROWS[:10] + [(101.6, 104.0, 101.5, 103.9), (103.9, 104.0, 101.6, 102.0), (102.0, 108.6, 101.9, 108.5)]
    base = one([("09:30", rows)])
    assert len(base) == 1 and base[0].adds == []
    t = one([("09:30", rows)], P(sb_adds=True))[0]
    assert len(t.adds) == 1 and t.adds[0][1] == 101.7                                         # the add at the FVG top
    assert 0 < t.adds[0][2] <= t.shares // 2                                                  # decreasing size (E12)
    assert sum(e[2] for e in t.exits) == t.shares + t.adds[0][2]
    assert t.peak_risk_pct <= 0.013 + 1e-9                                                    # the 1.3% total cap


# --- direction: draw first, one way per day, bias ----------------------------------------------------------------------

def test_m32_draw_first_locks_one_draw_and_trades_only_toward_it():
    p = P(sb_draw_first=True)
    df = mk([("09:30", ROWS)])
    tr, locks, _ = run(df, history(), p)
    assert len(tr) == 1 and tr[0].draw_side == 1 and tr[0].draw_px == 108.0 and tr[0].t1 == 108.25
    lk = [x for x in locks if x["session"] == "AM"]
    assert lk and lk[0]["side"] == 1 and lk[0]["target"] == 108.0 and lk[0]["t_lock"] == 570       # locked before the window
    # the nearest draw is DOWN (PDL 94 is 6 away, PDH 120 is 20 away): the long Silver Bullet is not taken
    h2 = history(hi=120.0, lo=94.0)
    assert one([("09:30", ROWS)], p, hist=h2) == []
    assert len(one([("09:30", ROWS)], P(), hist=h2)) == 1                                       # without the lock it is
    assert one([("09:30", ROWS)], P(sb_draw_first=True), hist=history(hi=101.0, lo=97.0)) == []   # no draw >= 5 pts: neutral


def test_m32_draw_first_works_for_the_short_side_too():
    h = history(close=200.0, hi=210.0, lo=192.0)                      # DOWN is nearer (8 vs 10)
    tr = one([("09:30", mirror(ROWS))], P(sb_draw_first=True), hist=h, base=200.0)
    assert len(tr) == 1 and tr[0].side == "short" and tr[0].draw_side == -1 and tr[0].draw_px == pytest.approx(192.0)


def test_l14g_pw_pools_ote_draw_and_htf_fallback():
    # the prior week's high 125 is the only pool above 101.7: PWH is a draw only with sb_pw_pools
    over = {date(2026, 6, 16): (100.0, 125.0, 92.0, 100.0)}
    h = history(hi=101.0, lo=92.0, over=over)
    assert one([("09:30", ROWS)], P(sb_pw_pools=False), hist=h) == []
    t = one([("09:30", ROWS)], P(sb_pw_pools=True), hist=h)
    assert len(t) == 1 and t[0].t1 == 125.25
    # a classic OTE of the prior session's down leg (116 -> 96): the 62% retracement 108.4 is a nearer array draw
    over = {date(2026, 6, 22): (108.5, 116.0, 96.0, 100.0)}
    h = history(hi=108.0, lo=90.0, over=over)
    assert one([("09:30", ROWS)], P(), hist=h)[0].t1 == 116.25
    ote = one([("09:30", ROWS)], P(sb_ote_draw=True), hist=h)
    assert ote[0].t1 == pytest.approx(108.4 - 0.5)
    sd1 = S.Side(1, np.ones(5), np.ones(5), np.ones(5), np.ones(5), 1)
    assert sb_model.ote_levels(SimpleNS(hist=h), sd1) == [pytest.approx(108.4)]
    # htf fallback: every near draw is inside draw_lock_min_pts (neutral) -> the previous week's range is used
    over = {date(2026, 6, 16): (100.0, 125.0, 70.0, 100.0)}
    h = history(hi=101.0, lo=97.0, over=over)
    assert one([("09:30", ROWS)], P(sb_draw_first=True), hist=h) == []
    t = one([("09:30", ROWS)], P(sb_draw_first=True, sb_htf_fallback=True), hist=h)
    assert len(t) == 1 and t[0].draw_px == 125.0 and t[0].draw_name == "pwh"


# a PM short around 108 (the mirror of ROWS about 210) after the AM long ran to 108.5
PM_SHORT = mirror(ROWS, 210.0)


def test_one_direction_per_day_sb_day_dir():
    blocks = [("09:30", ROWS), ("13:30", PM_SHORT)]
    assert [(t.setup, t.side) for t in one(blocks)] == [("sb_am", "long"), ("sb_pm", "short")]
    ft = one(blocks, P(sb_day_dir="first_trade"))
    assert [(t.setup, t.side) for t in ft] == [("sb_am", "long")]                   # the day is long: the PM short is not taken
    free = one(blocks, P(sb_day_dir="first_trade", sb_day_dir_delivered="free"))
    assert [(t.setup, t.side) for t in free] == [("sb_am", "long"), ("sb_pm", "short")]     # the AM draw printed: released
    lk = one(blocks, P(sb_day_dir="lock", sb_draw_first=True))                      # the AM lock (up) sets the day
    assert [(t.setup, t.side) for t in lk] == [("sb_am", "long")]
    lk = one(blocks, P(sb_day_dir="lock", sb_draw_first=True, sb_day_dir_delivered="free"))
    assert [(t.setup, t.side) for t in lk] == [("sb_am", "long"), ("sb_pm", "short")]
    assert [t.side for t in one(blocks, P(sb_draw_first=True))] == ["long", "short"]    # each window locks its own draw


def test_m33_use_bias_binds_the_sb_to_the_htf_and_weekly_bias():
    df = mk([("09:30", ROWS)])
    q = dict(htf_bias="combo", bias_neutral="both")
    down = dict(react=0, draw=0, pd=0, combo=-1)
    up = dict(react=0, draw=0, pd=0, combo=1)
    assert len(run(df, history(), P(**q), bias=down)[0]) == 1                        # the SB ignores the bias by default
    assert run(df, history(), P(sb_use_bias=True, **q), bias=down)[0] == []
    assert len(run(df, history(), P(sb_use_bias=True, **q), bias=up)[0]) == 1
    # a strong down Monday: weekly_bias -1 (favor shorts) keeps the Tuesday long out
    h = history(week={0: (110.0, 111.0, 80.0, 82.0)})
    assert S.weekly_bias(h, D0) == -1
    assert len(run(df, h, P(weekly_bias=True))[0]) == 1
    assert run(df, h, P(weekly_bias=True, sb_use_bias=True))[0] == []


def test_weekly_profile_alignment_048_2_02_12():
    aligned = history(week={0: (88.0, 108.0, 88.0, 100.0)})                         # Monday low in, closed up: bullish week
    against = history(week={0: (112.0, 112.0, 90.0, 100.0)})                        # Monday high in, closed down
    flat = history(week={0: (100.0, 108.0, 90.0, 100.0)})
    assert sb_model.weekly_profile(SimpleNS(hist=aligned), P(), D0)["side"] == 1
    assert sb_model.weekly_profile(SimpleNS(hist=against), P(), D0)["side"] == -1
    assert sb_model.weekly_profile(SimpleNS(hist=flat), P(), D0)["side"] == 0
    assert sb_model.weekly_profile(SimpleNS(hist=history()), P(), date(2026, 6, 22))["side"] == 0      # a Monday: no week yet
    req = P(sb_weekly="require")
    assert len(one(hist=aligned, p=req)) == 1
    assert one(hist=against, p=req) == []
    assert len(one(hist=against)) == 1
    t = one(hist=against, p=P(sb_weekly="tag"))
    assert len(t) == 1 and "sb_wk_against" in t[0].lv_tags
    t = one(hist=flat, p=req)
    assert len(t) == 1 and "sb_wk_neutral" in t[0].lv_tags
    assert one(hist=flat, p=P(sb_weekly="require", sb_weekly_neutral="skip")) == []


def test_m311_runner_only_with_the_weekly_profile_aligned():
    over = {date(2026, 6, 16): (100.0, 120.0, 92.0, 100.0)}
    q = dict(sb_runner=True, sb_pw_pools=True)
    a = history(over=over, week={0: (88.0, 108.0, 88.0, 100.0)})
    b = history(over=over, week={0: (112.0, 112.0, 90.0, 100.0)})
    assert one(hist=a, p=P(**q))[0].t2 == 120.25                                    # the runner to the next draw
    assert one(hist=b, p=P(**q))[0].t2 == 120.25                                    # (no weekly condition by default)
    assert one(hist=a, p=P(sb_runner_if_weekly=True, **q))[0].t2 == 120.25
    t = one(hist=b, p=P(sb_runner_if_weekly=True, **q))[0]
    assert t.t2 is None and "sb_no_runner" in t.lv_tags


def test_gap8_supercharge_keeps_one_lot_for_the_htf_draw_mon_to_wed():
    rows = ROWS[:11] + [(103.9, 114.6, 103.8, 114.5)]
    over = {date(2026, 6, 17): (112.0, 121.0, 111.0, 113.0), date(2026, 6, 18): (112.0, 114.0, 111.0, 113.0),
            date(2026, 6, 22): (97.5, 100.8, 97.0, 100.5)}                          # (June 19 is a holiday)
    h = history(over=over)
    bias = dict(react=0, draw=0, pd=0, combo=1)
    q = dict(sb_supercharge=True, htf_bias="combo", sb_use_bias=True)
    df = mk([("09:30", rows)])
    t = run(df, h, P(sb_runner=True, **q), bias=bias)[0][0]
    assert "sb_supercharge" in t.lv_tags and t.t2 == 121.25
    assert t.exits[0][3] == "t1" and t.exits[0][2] == t.shares - 1                   # all but one lot at the SB target
    assert t.exits[1][2] == 1 and t.exits[-1][3] in ("t2", "eod", "am_exit")                  # the lot rides on, the stop is not at BE
    # not supercharged (the daily is ranging: no bias row): the full exit at the SB target even with sb_runner
    t = run(df, h, P(sb_runner=True, sb_supercharge=True))[0][0]
    assert [e[3] for e in t.exits] == ["t1"] and t.t2 is None
    # a Thursday is outside Monday-Wednesday
    d4 = date(2026, 6, 25)
    h4 = history(d4, over={date(2026, 6, 18): (112.0, 121.0, 111.0, 113.0), date(2026, 6, 23): (97.5, 100.8, 97.0, 100.5),
                           date(2026, 6, 24): (97.5, 100.8, 97.0, 100.5), date(2026, 6, 22): (97.5, 100.8, 97.0, 100.5)})
    t = run(mk([("09:30", rows)], d4), h4, P(sb_runner=True, **q), bias=bias)
    assert all("sb_supercharge" not in x.lv_tags for x in t[0])


# --- ES / NQ / YM in sync, spotty days --------------------------------------------------------------------------------

def test_sync_es_nq_ym_in_sync_filter():
    df = mk([("09:30", ROWS)])
    same = (mk([("09:30", ROWS)]), history())
    mir = (mk([("09:30", mirror(ROWS, 200.0))], base=100.0), history())
    assert len(run(df, history(), P())[0]) == 1
    assert len(run(df, history(), P(sb_sync="require"), partner=same)[0]) == 1
    assert run(df, history(), P(sb_sync="require"), partner=mir)[0] == []
    t = run(df, history(), P(sb_sync="tag"), partner=mir)[0]
    assert len(t) == 1 and "sb_unsync_0of1" in t[0].lv_tags
    t = run(df, history(), P(sb_sync="tag"), partner=same)[0]
    assert "sb_sync_1of1" in t[0].lv_tags
    t = run(df, history(), P(sb_sync="require"))[0]                                   # no sister index: no data to judge
    assert len(t) == 1 and "sb_sync_na" in t[0].lv_tags
    # NQ in sync, YM out: 1 of 2 passes sb_sync_min=1 and fails sb_sync_min=2
    assert len(run(df, history(), P(sb_sync="require"), partner=same, partner2=mir)[0]) == 1
    assert run(df, history(), P(sb_sync="require", sb_sync_min=2), partner=same, partner2=mir)[0] == []
    # the weaker "dir" mode: the sister only has to close higher than at our low
    assert len(run(df, history(), P(sb_sync="require", sb_sync_mode="dir"), partner=same)[0]) == 1


# a choppy 09:30-10:00 (no displacement, no FVG, direction flips) before the structure at 10:00
SPOTTY = [(100.0, 100.4, 99.8, 100.2), (100.2, 100.5, 99.9, 100.0), (100.0, 100.4, 99.7, 100.3), (100.3, 100.5, 99.8, 99.8),
          (99.8, 100.2, 99.5, 100.2), (100.2, 100.4, 99.9, 100.1), (100.1, 101.2, 100.0, 101.1), (101.1, 101.6, 101.0, 101.5),
          (101.5, 102.2, 101.5, 102.1), (102.1, 102.2, 101.3, 101.4), (101.4, 108.6, 101.3, 108.5)]


def test_spotty_day_skip_045():
    base_ctx, base_sd = actx([("09:30", ROWS)], P())
    bad, why = sb_model.spotty_day(base_ctx, P(), sb_model.Win("am", "AM", "sb_am", 600, 660, 570), S._idx_at(base_ctx, 600),
                                   S._idx_at(base_ctx, 570), 5)
    assert not bad                                                                 # the base day has a displacement
    ctx, sd = actx([("09:30", SPOTTY)], P())
    bad, why = sb_model.spotty_day(ctx, P(), sb_model.Win("am", "AM", "sb_am", 600, 660, 570), S._idx_at(ctx, 600),
                                   S._idx_at(ctx, 570), 5)
    assert bad and {"no_disp", "no_fvg", "whipsaw"} == set(why)
    assert len(one([("09:30", SPOTTY)])) == 1
    assert one([("09:30", SPOTTY)], P(sb_spotty="skip")) == []
    t = one([("09:30", SPOTTY)], P(sb_spotty="tag"))
    assert len(t) == 1 and "sb_spotty_" in t[0].lv_tags
    assert len(one([("09:30", ROWS)], P(sb_spotty="skip"))) == 1                    # a normal day is untouched
    assert len(one([("09:30", SPOTTY)], P(sb_spotty="skip", sb_spotty_min=4, sb_spotty_tests=("no_disp", "no_fvg", "whipsaw", "no_draw")))) == 1


# --- entry price, cancel threshold, stop modes (E2, gap 17, M3.8, gap 19) ---------------------------------------------

def test_entry_mode_ce_is_the_048_worst_case():
    t = one(p=P(sb_entry="ce"))[0]
    assert t.entry == pytest.approx(101.55) and one()[0].entry == 101.7              # edge by default


# the market runs to 108.4 (beyond the 108 draw) at 10:15, THEN retraces into the FVG at 10:20 and runs again
CANCEL = ROWS[:9] + [(102.5, 108.4, 102.4, 108.3), (108.3, 108.4, 101.5, 101.7), (101.7, 108.6, 101.6, 108.5)]


def test_gap17_cancel_threshold_ticks_beyond_the_draw_057():
    assert one([("09:30", CANCEL)]) == []                                            # the exit price traded: cancelled (old)
    assert one([("09:30", CANCEL)], P(sb_cancel_ticks=1)) == []                      # 108.4 >= 108.0 + 1 tick x 0.25
    t = one([("09:30", CANCEL)], P(sb_cancel_ticks=3))
    assert len(t) == 1 and t[0].entry == 102.4 and t[0].exits[-1][3] == "t1"         # 108.4 < 108.75: a short run is wanted (evolved to the run candle's FVG)
    assert t[0].sb_pre_run_ticks == pytest.approx(1.6)                               # 0.4 pt beyond / 0.25
    t = one([("09:30", CANCEL)], P(sb_cancel_ticks=2))
    assert len(t) == 1                                                               # 108.4 < 108.5
    assert len(one([("09:30", CANCEL)], P(sb_cancel_sticky=False))) == 1             # (the old build re-armed the same draw)
    rows = CANCEL[:9] + [(102.5, 109.0, 102.4, 108.9)] + CANCEL[10:]                 # 109.0 >= 108.75: cancelled
    assert one([("09:30", rows)], P(sb_cancel_ticks=3)) == []


def test_gap19_stop_modes_swing_fvg2_fvg_ce_entry_candle_and_width():
    assert one()[0].stop == pytest.approx(98.95)                                     # 090: below the first FVG candle
    assert one(p=P(sb_stop="swing"))[0].stop == pytest.approx(98.25)                 # the leg low - 1 tick
    assert one(p=P(sb_stop="fvg2"))[0].stop == pytest.approx(99.7)                   # 057: 2 pts beyond the entry
    assert one(p=P(sb_stop="fvg2", sb_stop_pts=1.5))[0].stop == pytest.approx(100.2)
    o = arm([("09:30", ROWS)], P(sb_stop="fvg_ce", min_risk_pts=0.1))[0]
    assert o["stop"] == pytest.approx((99.4 + 101.0) / 2 - 0.25)                     # 069: beyond the CE of the deeper of two FVGs
    # width: 2.75 pts risk; sb_max_stop_pts=2 skips it, "size" cuts the size to the 2-pt budget (057 / 092)
    base = one()[0]
    assert one(p=P(sb_max_stop_pts=2.0, sb_wide="skip")) == []
    cut = one(p=P(sb_max_stop_pts=2.0, sb_wide="size"))[0]
    assert cut.shares == pytest.approx(base.shares * 2.0 / 2.75, abs=1.5) and "sb_wide_sized" in cut.lv_tags
    assert len(one(p=P(sb_max_stop_pts=4.0, sb_wide="skip"))) == 1
    # 086 ~11:35: below the entry candle, taken at the fill and sized there
    rows = ROWS[:9] + [(102.5, 102.6, 100.2, 101.6), (101.6, 104.0, 101.5, 103.9), (103.9, 108.6, 103.8, 108.5)]
    e = one([("09:30", rows)], P(sb_stop="entry_candle"))[0]
    assert e.stop == pytest.approx(99.95) and e.entry == 101.7
    assert e.shares == int(1200 / (101.7 - 99.95))                                   # sized at the real fill stop
    assert one([("09:30", ROWS)], P(sb_stop="entry_candle")) == []                   # the fill candle's stop is under 1 pt


def test_045_abort_after_a_body_closes_outside_the_fvg():
    rows = ROWS[:10] + [(101.6, 101.7, 101.0, 101.2), (101.2, 101.3, 100.6, 100.8), (100.8, 108.6, 100.7, 108.5)]
    assert one([("09:30", rows)])[0].exits[-1][3] == "t1"
    t = one([("09:30", rows)], P(sb_abort=True))[0]
    assert t.exits[0][3] == "sb_abort" and t.exits[0][1] == pytest.approx(101.0)


# --- L15 / gaps 2, 3, 5 ------------------------------------------------------------------------------------------------

def test_gap2_room_counts_the_overshoot_beyond_a_pool():
    p = dict(sb_room_pts=7.0)
    assert arm([("09:30", ROWS)], P(**p)) == []                                      # exit 108.25 - 101.7 = 6.55
    o = arm([("09:30", ROWS)], P(sb_room_overshoot_pts=3.0, **p))
    assert len(o) == 1 and o[0]["t1"] == pytest.approx(108.25)                       # the exit stays at the pool
    assert arm([("09:30", ROWS)], P(sb_room_mode="draw", **p)) == []                 # raw draw 108.0: 6.3
    assert len(arm([("09:30", ROWS)], P(sb_room_mode="draw", sb_room_overshoot_pts=3.0, **p))) == 1
    assert len(arm([("09:30", ROWS)], P(sb_room_mode="draw", sb_room_pts=6.0))) == 1


# the 103 pool (the prior day's high) is swept by a spike at 10:00 before the low; the draw left is 108 (beyond the swept one)
UNTAKEN = [(100.0, 103.5, 99.9, 100.5), (100.5, 100.6, 99.9, 100.0), (100.0, 101.0, 99.9, 100.8), (100.8, 100.8, 99.6, 99.7),
           (99.7, 99.8, 98.9, 99.0), (99.0, 99.1, 98.5, 98.6), (98.6, 99.4, 98.55, 99.3), (99.3, 101.4, 99.2, 101.3),
           (101.3, 102.0, 101.0, 101.9), (101.9, 102.6, 101.7, 102.5), (102.5, 102.6, 101.5, 101.6), (101.6, 108.6, 101.5, 108.5)]


def test_gap3_room_never_counts_past_a_pool_already_swept():
    h = history(over={date(2026, 6, 22): (100.0, 103.0, 95.0, 100.0)})
    blocks = [("10:00", UNTAKEN)]
    assert len(one(blocks, hist=h)) == 1 and one(blocks, hist=h)[0].t1 == 108.25
    assert one(blocks, P(sb_room_untaken=True), hist=h) == []                        # 058 ~54:20: the 103 high is taken


# no gap-up: the day opens inside the ORG [100, 102] and stays in it until the structure at 10:20
ORG = [(102.0, 102.0, 101.2, 101.6), (101.6, 101.9, 101.3, 101.5), (101.5, 101.8, 101.2, 101.7), (101.7, 101.9, 101.4, 101.5),
       (101.5, 101.8, 101.3, 101.6), (101.6, 101.8, 101.3, 101.7), (101.7, 101.8, 100.2, 100.4), (100.4, 100.5, 99.4, 99.5),
       (99.5, 99.6, 98.5, 98.6), (98.6, 99.4, 98.55, 99.3), (99.3, 102.4, 99.2, 102.2), (102.2, 102.8, 102.0, 102.7),
       (102.7, 103.4, 102.7, 103.3), (103.3, 103.4, 102.6, 102.9), (102.9, 108.6, 102.8, 108.5)]


def test_gap3_org_chop_is_not_a_classic_sb_and_scalp_mode_takes_half_size():
    base = one([("09:30", ORG)])
    assert len(base) == 1 and base[0].entry == 102.7
    assert one([("09:30", ORG)], P(sb_org_chop=True)) == []
    sc = one([("09:30", ORG)], P(sb_org_chop=True, sb_fail_mode="scalp"))
    assert len(sc) == 1 and "sb_scalp" in sc[0].lv_tags and [e[3] for e in sc[0].exits] == ["t1"]
    assert sc[0].shares == pytest.approx(base[0].shares / 2, abs=2)


def test_m35_sweep_required_depth_and_the_discount_array_alternative():
    up = [(o + 1.5, h + 1.5, l + 1.5, c + 1.5) for o, h, l, c in ROWS]
    assert one([("09:30", up)], P(sb_pw_pools=False))[0].swept == "none"             # nothing swept: allowed by default
    assert one([("09:30", up)], P(sb_need_sweep=True)) == []
    t = one([("09:30", ROWS)], P(sb_need_sweep=True))[0]
    assert t.swept == "pml" and t.sb_sweep_depth == pytest.approx(1.3)               # the depth tag
    assert len(one([("09:30", ROWS)], P(sb_sweep_max_pts=1.5))) == 1
    assert one([("09:30", ROWS)], P(sb_sweep_max_pts=1.0)) == []                     # ran too deep through the level
    # gap 5 (048 ~1:36): a retrace into a discount array (an earlier bullish FVG holding the low) stands in for the raid
    pre = [(99.3, 99.9, 99.2, 99.8), (99.8, 100.6, 99.7, 100.5), (100.5, 100.9, 100.3, 100.8)]    # a bullish FVG [99.9, 100.3]
    blocks = [("08:00", pre), ("09:30", up)]
    assert one(blocks, P(sb_need_sweep=True)) == []
    t = one(blocks, P(sb_need_sweep=True, sb_sweep_alt="discount_array"))
    assert len(t) == 1 and t[0].swept == "discount_array"
    assert one([("09:30", up)], P(sb_need_sweep=True, sb_sweep_alt="discount_array")) == []   # no array holds that low


# --- gap 7: immediate rebalance, done for the AM ----------------------------------------------------------------------

IMM = ROWS[:7] + [(101.3, 102.0, 99.4, 101.9)] + ROWS[8:]            # 10:05 trades straight back to the 09:55 high 99.4


def test_gap7_immediate_rebalance_tag_and_am_done():
    assert sb_model.immediate_rebalance(actx([("09:30", IMM)], P())[1], S._idx_at(actx([("09:30", IMM)], P())[0], 600),
                                        S._idx_at(actx([("09:30", IMM)], P())[0], 615), 0.25)
    assert one([("09:30", IMM)])[0].imm_rebal is False
    assert one([("09:30", IMM)], P(sb_imm_tag=True))[0].imm_rebal is True
    assert one([("09:30", ROWS)], P(sb_imm_tag=True))[0].imm_rebal is False


def _mk_book(rows):
    cols = ["date", "symbol", "session", "setup", "entry_time", "exit_time", "exit_reason", "smt", "ext_px", "leg_hi_px"]
    return pd.DataFrame(rows, columns=cols)


def test_combine_sb_window_is_its_own_slot_one_market_and_am_done():
    d = D0
    t = lambda h, m: pd.Timestamp(f"{d} {h:02d}:{m:02d}", tz=NY)
    es = _mk_book([(d, "ES", "AM", "sb_london", t(3, 15), t(3, 30), "t1", False, np.nan, np.nan),
                   (d, "ES", "AM", "sb_am", t(10, 15), t(10, 40), "t1", False, np.nan, np.nan)])
    nq = _mk_book([(d, "NQ", "AM", "am_mm", t(9, 50), t(10, 5), "t1", False, np.nan, np.nan),
                   (d, "NQ", "AM", "sb_am", t(10, 20), t(10, 50), "t1", False, np.nan, np.nan)])
    both = B.combine(es, nq)
    # the London and AM Silver Bullets and the main engine's AM trade each own a slot (the old key (date, session) kept one)
    assert sorted(both.setup) == ["am_mm", "sb_am", "sb_london"]
    assert both[both.setup == "sb_am"].symbol.iloc[0] == "ES"                        # the first fill of that SB window
    # 046 ~55:21: don't switch markets - the NQ SB of a later window is dropped after an ES SB
    pm_nq = _mk_book([(d, "NQ", "PM", "sb_pm", t(14, 15), t(14, 40), "t1", False, np.nan, np.nan)])
    pm_es = _mk_book([(d, "ES", "PM", "sb_pm", t(14, 30), t(14, 50), "t1", False, np.nan, np.nan)])
    got = B.combine(es, pm_nq, pm_es, sb_one_market=True)
    assert set(got[got.setup.str.startswith("sb_")].symbol) == {"ES"}
    # 048 ~1:35: an AM Silver Bullet that reached its target ends the AM - the main engine's later AM trade goes
    late = _mk_book([(d, "ES", "AM", "am_mm", t(10, 55), t(11, 20), "stop", False, np.nan, np.nan)])
    kept = B.combine(es, late)
    assert "am_mm" in set(kept.setup)
    done = B.combine(es, late, sb_am_done=True)
    assert "am_mm" not in set(done.setup) and "sb_am" in set(done.setup)


class StubConf:
    """A minimal confluence stand-in: at() = the timeframes holding the price, targets() = HTF target levels (real prices)."""

    def __init__(self, tfs=("15m",), targets=()):
        self._tfs, self._targets = list(tfs), list(targets)

    def at(self, t, price, side, known_by=None):
        return list(self._tfs)

    def targets(self, t, beyond, side, tfs, far_edge=False):
        return [v for v in self._targets if (v > beyond if side > 0 else v < beyond)]

    def opposing(self, t, beyond, side, tfs, src=(0,), keep_dead=False):
        return []

    def resistance(self, *a, **k):
        return None


# --- M3.1 'early': fills from 09:50 ------------------------------------------------------------------------------------

EARLY2 = [(100.0, 100.9, 100.0, 100.8), (100.8, 100.8, 99.6, 99.7), (99.7, 99.8, 98.5, 98.6), (98.6, 101.2, 98.55, 101.1),
          (101.1, 101.5, 101.0, 101.4), (101.4, 101.5, 100.8, 101.0), (101.0, 104.0, 100.9, 103.9), (103.9, 108.6, 103.8, 108.5)]


def test_m31_early_extra_lets_the_09_50_macro_fill():
    assert one([("09:30", EARLY2)]) == []                                             # 09:55 is before the 10:00 window
    t = one([("09:30", EARLY2)], P(sb_extra=("early",)))
    assert len(t) == 1 and str(t[0].entry_time)[11:16] == "09:55" and t[0].entry == 101.0


# --- gap 1: the IFVG entry ------------------------------------------------------------------------------------------------

# an earlier 5m-style SIBI [100.4, 100.8] (09:30-09:40) that the 10:00 displacement closes through; a deep retrace at 10:15
IFVG = [(101.1, 101.2, 100.8, 101.0), (101.0, 101.0, 100.3, 100.4), (100.4, 100.4, 99.7, 99.8), (99.8, 99.9, 99.0, 99.1),
        (99.1, 99.2, 98.5, 98.6), (98.6, 99.3, 98.55, 99.2), (99.2, 101.5, 99.1, 101.4), (101.4, 101.8, 101.1, 101.7),
        (102.0, 102.4, 101.9, 102.3), (102.3, 102.4, 99.5, 100.9), (100.9, 108.6, 100.8, 108.5)]
# the same with an up-close candle (09:45) overlapping the SIBI: a bullish breaker
IFVG_B = IFVG[:3] + [(99.8, 100.6, 99.6, 100.5), (100.5, 100.5, 99.0, 99.1), (99.1, 99.2, 98.5, 98.6), (98.6, 99.3, 98.55, 99.2),
                     (99.2, 101.5, 99.1, 101.4), (101.4, 101.8, 101.1, 101.7), (102.0, 102.4, 101.9, 102.3),
                     (102.3, 102.4, 99.5, 100.9), (100.9, 108.6, 100.8, 108.5)]


def test_gap1_ifvg_entry_at_the_near_edge_of_an_inverted_gap():
    assert one([("09:30", IFVG)])[0].entry == 101.9                                  # the new FVG [101.5, 101.9] by default
    q = dict(or_minutes=0)                                                              # (no opening-range pool: 101.2 would be the draw)
    t = one([("09:30", IFVG)], P(sb_ifvg="prefer", **q))
    assert len(t) == 1 and t[0].entry == 100.8 and t[0].entry_kind == "ifvg"          # the old SIBI's top (076 / 092)
    assert t[0].stop == pytest.approx(99.5 - 0.25)                                     # below the entry candle (076)
    t = one([("09:30", IFVG)], P(sb_ifvg="add", **q))
    assert t[0].entry == 101.9 and t[0].entry_kind == "fvg"                           # the later formation wins
    o = arm([("09:30", IFVG_B)], P(sb_ifvg="prefer", **q), at="10:10")                # overlapping a breaker: "SB on steroids"
    assert o[0]["kind"] == "ifvg_breaker" and o[0]["entry"] == 100.8
    o = arm([("09:30", IFVG)], P(sb_ifvg="prefer", **q), at="10:10")
    assert o[0]["kind"] == "ifvg"
    # with a breaker stop
    o = arm([("09:30", IFVG_B)], P(sb_ifvg="prefer", sb_ifvg_stop="breaker", **q), at="10:10")[0]
    assert o["stop"] == pytest.approx(99.6 - 0.25)                                     # the breaker candle's low - 1 tick


def test_gap1_ifvg_market_entry_076():
    t = one([("09:30", IFVG)], P(sb_ifvg="prefer", sb_ifvg_market=True, or_minutes=0))
    # the 10:15 bar is a down-close candle trading into the IFVG [100.4, 100.8]: bought at the next open (10:20), stop under that candle
    assert len(t) == 1 and t[0].entry_kind == "ifvg" and str(t[0].entry_time)[11:16] == "10:20"
    assert t[0].entry == pytest.approx(100.9) and t[0].stop == pytest.approx(99.5 - 0.25)


# --- gap 9: the 5m order block entry (049) --------------------------------------------------------------------------------

# a pre-window leg up from 98.0 (09:35) to 102.8 (09:50), a retrace into the bullish OB [98.0, 100.2] at 09:55
OBR = [(100.0, 100.2, 99.0, 99.2), (99.2, 99.3, 98.0, 98.2), (98.2, 100.5, 98.1, 100.4), (100.4, 102.0, 100.3, 101.8),
       (101.8, 102.8, 101.7, 102.6), (102.6, 102.7, 100.0, 100.3), (100.3, 100.4, 100.1, 100.35), (100.35, 103.0, 100.3, 102.9),
       (102.9, 103.0, 102.5, 102.6)]


def test_gap9_order_block_entry_needs_a_locked_draw_and_covers_at_the_next_high():
    p = P(sb_entry_arrays=("ob",), sb_draw_first=True)
    t = one([("09:30", OBR)], p)
    assert len(t) == 1 and t[0].entry_kind == "ob" and t[0].entry == 100.2 and "sb_ob" in t[0].lv_tags
    assert str(t[0].entry_time)[11:16] == "10:00"
    assert t[0].stop == pytest.approx(98.0 - 0.25) and t[0].exits[-1][1] == pytest.approx(102.8 - 0.5)
    assert one([("09:30", OBR)], P(sb_entry_arrays=("ob",))) == []                    # no locked / htf draw: no trade
    assert one([("09:30", OBR)], P(sb_draw_first=True)) == []                         # the FVG entry only: nothing here
    h = history(hi=120.0, lo=94.0)                                                     # a DOWN lock: no long OB (only the mirror)
    assert all(t.side == "short" for t in one([("09:30", OBR)], p, hist=h))


# --- gap 10: wick CE / VI / MT confluence (090) -----------------------------------------------------------------------------

def test_gap10_three_array_confluence_tags_or_moves_the_entry_and_a_close_below_the_mt_exits():
    p_tag = P(sb_entry_arrays=("fvg", "confluence"))
    o = arm([("09:30", ROWS)], p_tag)[0]
    assert "sb_conf" in o["lv_tags"] and o["entry"] == 101.7                           # tag mode keeps the FVG edge
    o = arm([("09:30", ROWS)], P(sb_entry_arrays=("fvg", "confluence"), sb_conf_mode="entry", min_risk_pts=0.5, or_minutes=0, sb_room_pts=0.2))[0]
    assert o["kind"] == "conf" and o["entry"] < 101.7 and o["cancel_below"] == pytest.approx(99.7)
    entry = float(o["entry"])
    assert entry >= 99.7 - 1e-9
    # run: the retrace to the confluence fills; a wick below the MT is allowed, a 1m close below ends the idea
    wick = ROWS[:9] + [(102.5, 102.6, entry - 0.1, entry + 0.2), (entry + 0.2, entry + 0.4, 99.5, 99.9), (99.9, 108.6, 99.8, 108.5)]
    t = one([("09:30", wick)], P(sb_entry_arrays=("fvg", "confluence"), sb_conf_mode="entry", min_risk_pts=0.5, or_minutes=0, sb_room_pts=0.2))
    assert len(t) == 1 and t[0].entry == pytest.approx(entry) and t[0].exits[-1][3] == "t1"
    close = ROWS[:9] + [(102.5, 102.6, entry - 0.1, entry + 0.2), (entry + 0.2, entry + 0.4, 99.5, 99.6), (99.6, 108.6, 99.5, 108.5)]
    t = one([("09:30", close)], P(sb_entry_arrays=("fvg", "confluence"), sb_conf_mode="entry", min_risk_pts=0.5, or_minutes=0, sb_room_pts=0.2))
    assert len(t) == 1 and t[0].exits[0][3] == "sb_conf_mt"


# --- gap 13: premise (HTF array / SMT) ---------------------------------------------------------------------------------------

def test_gap13_premise_htf_array_and_smt():
    df = mk([("09:30", ROWS)])
    q = dict(sb_premise="htf_array")
    assert len(run(df, history(), P(**q), conf=StubConf(("15m",)))[0]) == 1
    assert run(df, history(), P(**q), conf=StubConf(()))[0] == []                      # the low is in no HTF array
    assert run(df, history(), P(**q))[0] == []                                          # no HTF data: not provable
    assert len(run(df, history(), P())[0]) == 1
    up2 = mk([("09:30", [(o + 2.0, h + 2.0, l + 2.0, c + 2.0) for o, h, l, c in ROWS])])
    # SMT: the sister holds a higher low (no new low through its own premarket low) while ES takes the low
    t = run(df, history(), P(sb_premise="smt"), partner=(up2, history()))[0]
    assert len(t) == 1 and "sb_premise_smt" in t[0].lv_tags
    assert run(df, history(), P(sb_premise="smt"), partner=(mk([("09:30", ROWS)]), history()))[0] == []   # the sister also took it
    t = run(df, history(), P(sb_premise="either"), conf=StubConf(()), partner=(up2, history()))[0]
    assert len(t) == 1 and "sb_premise_smt" in t[0].lv_tags


# --- gap 22: NWOG expansion -----------------------------------------------------------------------------------------------------

def test_gap22_nwog_expansion_tag_and_require():
    gap = history(n=24, over={date(2026, 6, 22): (94.0, 108.0, 90.0, 100.0)})         # Monday opens at 94 under Thursday's 100
    t = one(hist=gap, p=P(sb_nwog_expansion="tag"))
    assert len(t) == 1 and "sb_nwog_expansion" in t[0].lv_tags                         # the low 98.5 sits in the NWOG [94, 100]
    assert len(one(hist=gap, p=P(sb_nwog_expansion="require"))) == 1
    h0 = history(n=24)
    t = one(hist=h0, p=P(sb_nwog_expansion="tag"))
    assert len(t) == 1 and "sb_nwog_expansion" not in t[0].lv_tags                      # no gap near the low
    assert one(hist=h0, p=P(sb_nwog_expansion="require")) == []


# --- gap 15: ONE opposite SB after an HTF-array target -----------------------------------------------------------------------------

# the long runs to the OTE array draw (107.9) and sells off through the run's origin (98.5); a SIBI and a short entry follow
REV = ROWS[:11] + [(103.9, 108.6, 103.8, 108.5), (108.5, 108.6, 106.0, 106.2), (106.2, 106.3, 97.5, 97.8),
                   (97.8, 98.3, 97.0, 97.2), (97.2, 98.6, 97.1, 98.0), (98.0, 98.1, 96.0, 96.2)]
OTE_HIST = history(over={date(2026, 6, 22): (108.5, 116.0, 96.0, 100.0)})            # prior-day OTE array at 108.4


def test_gap15_reverse_after_an_htf_array_target():
    q = dict(sb_ote_draw=True, sb_room_pts=2.0, or_minutes=0)
    base = one([("09:30", REV)], P(**q), hist=OTE_HIST)
    assert [t.side for t in base] == ["long"] and base[0].exits[-1][3] == "t1"
    rv = one([("09:30", REV)], P(sb_reverse_after_target=True, **q), hist=OTE_HIST)
    assert [t.side for t in rv] == ["long", "short"] and "sb_reverse" in rv[1].lv_tags and rv[1].sb_n == 2
    assert rv[1].entry < 100.0
    # a plain pool as the target (no OTE, PDH 108) is not an HTF array: no reversal
    pool = one([("09:30", REV)], P(sb_reverse_after_target=True))
    assert [t.side for t in pool] == ["long"]


# --- gap 20: the simple EQ rule ---------------------------------------------------------------------------------------------------------

# a Judas drop from 106 to 98.5, a lower swing high 101.2, the MSS and an FVG [101.9, 102.2] in the DISCOUNT of the leg (EQ 102.25)
SIMPLE = [(105.0, 106.0, 104.8, 105.5), (105.5, 105.6, 101.8, 102.0), (101.0, 101.1, 99.6, 99.8), (99.8, 101.2, 99.7, 101.0),
          (101.0, 101.1, 98.6, 98.7), (98.7, 98.9, 98.5, 98.8), (98.8, 101.9, 98.7, 101.7), (101.7, 102.8, 101.6, 102.6),
          (102.6, 103.2, 102.2, 103.0), (103.0, 103.1, 102.1, 102.5), (102.5, 108.6, 102.4, 108.5)]


def test_gap20_simple_rule_enters_in_discount_and_exits_at_the_first_array_beyond_eq():
    q = dict(sb_ote_draw=True, sb_room_pts=4.0)
    base = one([("09:30", SIMPLE)], P(**q), hist=OTE_HIST)
    assert len(base) == 1 and base[0].entry == 102.2 and base[0].t1 == pytest.approx(106.25)   # the opening-range high 106
    t = one([("09:30", SIMPLE)], P(sb_simple=True, **q), hist=OTE_HIST)
    assert len(t) == 1 and "sb_simple" in t[0].lv_tags and [e[3] for e in t[0].exits] == ["t1"]
    assert t[0].t1 == pytest.approx(108.4 - 0.5)                                       # the OTE array beyond EQ, one exit
    assert one([("09:30", ROWS)], P(sb_simple=True, **q), hist=OTE_HIST) == []                # the ROWS FVG is in the premium


# --- M3.11: the 4 / 2 / 4 exits of 057, HTF target merge -------------------------------------------------------------------------------

def test_m311_gap424_exits_at_the_nwog_high_75pct_and_ce():
    h = history(n=24, over={date(2026, 6, 18): (100.0, 108.0, 91.0, 108.0), date(2026, 6, 22): (111.0, 111.0, 100.0, 100.5)})
    rows = ROWS[:11] + [(103.9, 109.6, 103.8, 109.5)]
    t = [x for x in one([("09:30", rows)], P(sb_mgmt="gap424", sb_draw_first=True), hist=h) if x.side == "long"][0]
    assert [e[3] for e in t.exits] == ["t1", "t2", "t3"] and "sb_gap424" in t.lv_tags
    assert [e[1] for e in t.exits] == pytest.approx([107.5, 108.25, 109.0])           # near edge - 0.5, 25% in, CE
    q = [e[2] / t.shares for e in t.exits]
    assert q[0] == pytest.approx(0.4, abs=0.01) and q[1] == pytest.approx(0.2, abs=0.01)
    assert one([("09:30", rows)], P(sb_mgmt="layered057", sb_draw_first=True), hist=h)[0].exits[0][1] == pytest.approx(107.5)


def test_l14g_htf_targets_merge_into_the_sb_draw_list():
    df = mk([("09:30", ROWS)])
    q = dict(sb_room_pts=2.0)
    base = run(df, history(), P(**q), conf=StubConf((), (105.0,)))[0][0]
    assert base.t1 == 108.25
    t = run(df, history(), P(sb_htf_targets=True, **q), conf=StubConf((), (105.0,)))[0][0]
    assert t.t1 == pytest.approx(104.5)                                                 # an HTF array 105 is the nearer draw


# --- knobs and the remaining switches ----------------------------------------------------------------------------------------

# a Reaper (076): a bullish FVG [100.2, 100.8] in the discount of the L1 -> H leg that price cut through on the way to the low
REAPER = [(100.0, 100.2, 99.0, 99.9), (99.9, 101.0, 99.8, 100.9), (100.9, 102.5, 100.8, 102.4), (102.4, 102.4, 100.0, 100.1),
          (100.1, 100.2, 98.5, 98.6), (98.6, 103.0, 98.55, 102.9), (102.9, 103.6, 102.8, 103.5), (103.5, 104.2, 103.3, 104.1),
          (104.1, 104.2, 100.5, 101.0), (101.0, 108.6, 100.9, 108.5)]


def test_gap1_ifvg_reaper_is_an_entry_candidate():
    q = dict(or_minutes=0, sb_room_pts=4.5)
    assert arm([("09:30", REAPER)], P(sb_ifvg="prefer", **q), at="10:05")[0]["kind"] == "fvg"        # no inverted gap: the FVG
    o = arm([("09:30", REAPER)], P(sb_ifvg="prefer", sb_ifvg_reaper=True, **q), at="10:05")[0]
    assert o["kind"] == "ifvg_breaker" and o["entry"] == 100.8
    o = arm([("09:30", REAPER)], P(sb_ifvg_reaper=True, **q), at="10:05")                            # the reaper alone arms it too
    assert any(x["kind"] == "ifvg_breaker" for x in o) or o[0]["kind"] == "fvg"


def test_knobs_windows_spotty_cons_ob_conf():
    assert [(w.a, w.b) for w in sb_model.windows(P(sb_london=True, sb_london_window=(190, 230)))][0] == (190, 230)
    assert one([("14:30", ROWS)], P(sb_last_hour=True, sb_lh_window=(900, 910))) == []                 # the 15:15 fill is outside
    assert len(one([("14:30", ROWS)], P(sb_last_hour=True, sb_lh_window=(900, 960)))) == 1
    t = one([("06:30", ROWS[:10])], P(sb_0700=True, sb_0700_flat=480))
    assert str(t[0].exits[-1][0])[11:16] == "07:55"
    # spotty: a 10-minute look-back sees too few bars to call the day spotty
    ctx_s, _ = actx([("09:30", SPOTTY)], P())
    win_s = sb_model.Win("am", "AM", "sb_am", 600, 660, 570)
    k0_s = S._idx_at(ctx_s, 570)
    assert not sb_model.spotty_day(ctx_s, P(), win_s, k0_s + 2, k0_s, 5)[0]                 # fewer than 3 bars: nothing to read
    assert sb_model.spotty_day(ctx_s, P(sb_spotty_bars=15), win_s, k0_s + 6, k0_s, 5)[0]       # the last 3 bars are choppy too
    assert one([("09:30", SPOTTY)], P(sb_spotty="skip", sb_spotty_bars=60)) == []
    # consolidation: a looser box (range 1.0 > 0.5) is no box, a stricter body test drops the displacement
    p = dict(sb_cons_bars=4, sb_mss_required=False, sb_room_pts=0.5, min_risk_pts=0.5, sb_cons_wait=True)
    assert arm([("09:30", CONS)], P(sb_cons_pts=0.5, **p), at="10:15") != []
    assert arm([("09:30", CONS)], P(sb_cons_pts=2.0, **p), at="10:15") == []
    assert arm([("09:30", CONS)], P(sb_cons_body_mult=10.0, **p), at="10:30") == []
    # order block / confluence thresholds
    ob = dict(sb_entry_arrays=("ob",), sb_draw_first=True)
    assert len(one([("09:30", OBR)], P(sb_ob_min_pts=2.0, **ob))) == 1
    assert one([("09:30", OBR)], P(sb_ob_min_pts=10.0, **ob)) == []
    cf = dict(sb_entry_arrays=("fvg", "confluence"))
    assert "sb_conf" in arm([("09:30", ROWS)], P(**cf))[0]["lv_tags"]
    assert "sb_conf" not in arm([("09:30", ROWS)], P(sb_conf_min=3, **cf))[0]["lv_tags"]
    assert "sb_conf" not in arm([("09:30", ROWS)], P(sb_conf_tol_pts=0.01, **cf))[0]["lv_tags"]
    # the ORG look-back and the reserved seasonal switch change nothing here
    assert len(one([("09:30", ORG)], P(sb_org_chop_bars=2))) == 1
    assert one([("09:30", ROWS)], P(sb_supercharge_seasonal=True))[0].entry == one([("09:30", ROWS)])[0].entry
    # the 4 / 2 / 4 split is a switch
    h = history(n=24, over={date(2026, 6, 18): (100.0, 108.0, 91.0, 108.0), date(2026, 6, 22): (111.0, 111.0, 100.0, 100.5)})
    rows = ROWS[:11] + [(103.9, 109.6, 103.8, 109.5)]
    t = one([("09:30", rows)], P(sb_mgmt="gap424", sb_draw_first=True, sb_gap424_fracs=(0.5, 0.25, 0.25)), hist=h)[0]
    assert t.exits[0][2] / t.shares == pytest.approx(0.5, abs=0.01)


# --- the new switches never fire by themselves --------------------------------------------------------------------------------

NEW_FIELDS = (
    "sb_last_hour", "sb_lh_window", "sb_0700", "sb_0700_window", "sb_0700_flat", "sb_london_window", "sb_extra", "sb_early_start",
    "sb_moc_extra", "sb_moc_window", "sb_one_per_day", "sb_cascade", "sb_one_market", "sb_max_per_window", "sb_adds",
    "sb_am_done", "sb_draw_first", "sb_pw_pools", "sb_ote_draw", "sb_htf_fallback", "sb_htf_targets", "sb_use_bias",
    "sb_day_dir", "sb_day_dir_delivered", "sb_weekly", "sb_weekly_neutral", "sb_sync", "sb_sync_mode", "sb_sync_min",
    "sb_spotty", "sb_spotty_tests", "sb_spotty_min", "sb_spotty_bars", "sb_disp_pts", "sb_disp_leg_pts",
    "sb_disp_range_mult", "sb_mss_required", "sb_need_mss", "sb_fvg_in_window", "sb_fvg_from", "sb_evolve", "sb_fvg_pick",
    "sb_need_sweep", "sb_sweep_max_pts", "sb_sweep_alt", "sb_bpr_exclude", "sb_cons_wait", "sb_cons_bars", "sb_cons_pts",
    "sb_cons_body_mult", "sb_lrc_mult", "sb_lrc_mode", "sb_premise", "sb_nwog_expansion", "sb_entry_arrays", "sb_ifvg",
    "sb_ifvg_reaper", "sb_ifvg_stop", "sb_ifvg_market", "sb_ob_min_pts", "sb_conf_min", "sb_conf_tol_pts", "sb_conf_mode",
    "sb_reverse_after_target", "sb_cancel_ticks", "sb_cancel_sticky", "sb_simple", "sb_stop", "sb_stop_pts", "sb_max_stop_pts",
    "sb_wide", "sb_abort", "sb_room_mode", "sb_room_overshoot_pts", "sb_room_untaken", "sb_org_chop", "sb_org_chop_bars",
    "sb_fail_mode", "sb_imm_tag", "sb_runner_if_weekly", "sb_supercharge", "sb_supercharge_seasonal", "sb_gap424_fracs")


def test_every_new_switch_is_a_params_field_and_has_a_test_that_names_it():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(Params)}
    assert set(NEW_FIELDS) <= fields
    src = Path(__file__).read_text(encoding="utf-8")
    cut = src.index("NEW_FIELDS = (")
    body = src[:cut] + src[src.index("def test_every_new_switch"):]
    missing = [f for f in NEW_FIELDS if f not in body]
    assert not missing, f"no test names {missing}"


# --- no look-ahead: a run on the full data and on data cut just after each fill must agree on every trade up to that fill ---

def _no_look_ahead(df, tf, sym, p, cols, every=1, meta=None, lag=2, min_trades=1, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = B.run(df, tf, sym, p, meta=meta, **kw)
        assert len(full) >= min_trades, "no trades - the test window must produce some"
        for cut_t in full.entry_time.iloc[::every]:
            c = cut_t + pd.Timedelta(minutes=lag)
            pk = {k: (v[v.index <= c] if isinstance(v, pd.DataFrame) else v) for k, v in kw.items()}
            part = B.run(df[df.index <= c], tf, sym, p, partial_last=True, meta=meta, **pk)
            a = full[full.entry_time <= cut_t][cols].reset_index(drop=True)
            b = part[part.entry_time <= cut_t][cols].reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b)
    return full


SBCOLS = ["entry_time", "entry", "stop", "t1", "t2", "shares", "setup", "entry_kind", "swept", "draw_px", "lv_tags", "sb_win", "sb_n"]
SYN = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0, sb_model=True, am=(0, 0), pm=(0, 0), draw_lock="off",
           htf_resist_cap=False, sloppy_mode="off", sb_room_pts=1.0)
MIN_TRADES = {"windows_draw": 3, "count_pick": 5, "filters": 1, "entries_exits": 5, "runner_simple": 5}
SYN_GROUPS = {
    "windows_draw": dict(sb_london=True, sb_0700=True, sb_last_hour=True, sb_moc_extra=True, sb_draw_first=True,
                         sb_ote_draw=True, sb_htf_fallback=True, sb_day_dir="first_trade", sb_day_dir_delivered="free"),
    "count_pick": dict(sb_max_per_window=2, sb_extra=("pm2", "early"), sb_fvg_pick="any_in_leg", sb_adds=True,
                       sb_cancel_ticks=2, sb_one_per_day=False),
    "filters": dict(sb_sync="require", sb_spotty="skip", sb_weekly="require", sb_weekly_neutral="allow", sb_disp_pts=0.2,
                    sb_cons_wait=True, sb_cons_bars=3, sb_need_sweep=True, sb_sweep_alt="discount_array",
                    sb_nwog_expansion="tag", sb_bpr_exclude=True, sb_lrc_mult=1.5, sb_lrc_mode="wait"),
    "entries_exits": dict(sb_ifvg="add", sb_ifvg_reaper=True, sb_ifvg_market=True, sb_entry_arrays=("fvg", "ob", "confluence"),
                          sb_conf_mode="entry", sb_stop="entry_candle", sb_abort=True, sb_mgmt="gap424", sb_room_untaken=True,
                          sb_org_chop=True, sb_fail_mode="scalp", sb_room_overshoot_pts=3.0, sb_imm_tag=True),
    "runner_simple": dict(sb_runner=True, sb_runner_if_weekly=True, sb_supercharge=True, sb_reverse_after_target=True,
                          sb_ote_draw=True, sb_htf_targets=True, sb_use_bias=True, sb_simple=False, sb_stop="fvg2"),
}


@pytest.mark.parametrize("group", list(SYN_GROUPS))
def test_look_ahead_synthetic_silver_bullet_switch_groups(group):
    x, y = B.synthetic(start="2026-06-01", end="2026-08-15", tf=5, seed=3)
    p = Params(**SYN, **SYN_GROUPS[group])
    full = _no_look_ahead(x, 5, "RW", p, SBCOLS, every=3, partner=y, min_trades=MIN_TRADES[group])
    assert set(full.sb_win) <= {"london", "0700", "am", "pm", "lh", "moc"}


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_5m_silver_bullet_switches():
    df = B.load("ES", 5, source="databento")
    df = df[(df.index >= "2023-04-03") & (df.index < "2023-06-02")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), sb_model=True, draw_lock="off", htf_resist_cap=False, sloppy_mode="off",
               sb_last_hour=True, sb_max_per_window=2, sb_fvg_pick="any_in_leg", sb_adds=True, sb_draw_first=True,
               sb_day_dir="first_trade", sb_day_dir_delivered="free", sb_disp_pts=0.5, sb_ote_draw=True, sb_weekly="tag",
               sb_stop="fvg2", sb_cancel_ticks=3, sb_ifvg="add", sb_mgmt="gap424")
    full = _no_look_ahead(df, 5, "ES", p, SBCOLS, every=1, min_trades=3)
    assert set(full.sb_win) <= {"am", "pm", "lh"}


@pytest.mark.skipif(not ES, reason="no ES data")
def test_look_ahead_es_5m_locked_silver_bullet_with_sync_and_spotty():
    df = B.load("ES", 5, source="databento")
    nq = B.load("NQ", 5, source="databento") if Path("data/mentorship/NQ_5min_db.csv").exists() else None
    df = df[(df.index >= "2023-04-03") & (df.index < "2023-06-02")]
    kw = {}
    if nq is not None:
        kw["partner"] = nq[(nq.index >= "2023-04-03") & (nq.index < "2023-06-02")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), sb_model=True, sloppy_mode="off", sb_sync="tag", sb_spotty="tag",
               sb_premise="either", sb_nwog_expansion="tag", sb_need_sweep=False, sb_use_bias=False, sb_stop="entry_candle",
               sb_room_mode="draw", sb_room_overshoot_pts=2.0)
    _no_look_ahead(df, 5, "ES", p, SBCOLS, every=1, min_trades=1, **kw)


@pytest.mark.skipif(not ES1, reason="no ES 1m data")
def test_look_ahead_es_1m_silver_bullet_london_0700_and_last_hour():
    es = B.load("ES", 1, source="databento")
    es = es[(es.index >= "2024-01-02") & (es.index < "2024-02-02")]
    p = Params(**FUT, am=(0, 0), pm=(0, 0), sb_model=True, sloppy_mode="off", sb_london=True, sb_0700=True, sb_last_hour=True,
               sb_moc_extra=True, sb_draw_first=True, sb_max_per_window=2, sb_ifvg="add", sb_entry_arrays=("fvg", "ob", "confluence"),
               sb_conf_mode="tag", sb_stop="swing", sb_abort=True, sb_cons_wait=True)
    full = _no_look_ahead(es, 1, "ES", p, SBCOLS, every=2, lag=1, min_trades=2)
    assert set(full.sb_win) & {"london", "0700", "am", "pm", "lh", "moc"}


# --- the previous build is reproduced when the two behaviour changes are switched back ----------------------------------------

def _sig(t):
    import hashlib
    rows = [(str(r.entry_time), round(float(r.entry), 4), round(float(r.stop), 4), round(float(r.t1), 4), r.setup)
            for r in t.itertuples()]
    return hashlib.sha1(repr(rows).encode()).hexdigest()[:16], len(rows)


def test_defaults_reproduce_the_pre_package_build_when_pw_pools_and_cancel_sticky_are_off():
    """Signatures recorded from the build before this package (synthetic seed 3, 2026-06-01..08-15): sb_pw_pools (PWH / PWL are
    draws) and sb_cancel_sticky (a cancelled draw is not re-armed) are the only two default changes; with both off the
    Silver Bullet trades are the same."""
    x, y = B.synthetic(start="2026-06-01", end="2026-08-15", tf=5, seed=3)
    old = dict(es_pt=0.09, use_bias=False, min_draw_pts=0, leg_pd=0, sb_model=True, am=(0, 0), pm=(0, 0),
               sb_pw_pools=False, sb_cancel_sticky=False)
    cases = {"def": (dict(draw_lock="off", htf_resist_cap=False), ("743d211d83708eb2", 10)),
             "lock": ({}, ("8855c2c14eb38adf", 3)),
             "fixed": (dict(sb_target_mode="fixed", sb_runner=True, draw_lock="off"), ("eef1d92e092f06d5", 10)),
             "dp": (dict(sb_draw_pools_only=True, draw_lock="off", sb_entry="edge_1tick", sb_room_pts=2.0), ("069ae00e9a56ee52", 12))}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, (kw, want) in cases.items():
            t = B.run(x, 5, "RW", Params(**old, **kw), partner=y)
            assert _sig(t) == want, name


def test_study_silver_bullet_variants_build():
    from mentorship import study
    names = [k for k, v in study.DECISIONS.items() if set(v) & set(NEW_FIELDS)]
    assert len(names) >= 70
    for k in names:
        replace(Params(**study.DEC_BASE), **study.DECISIONS[k])
    used = set()
    for k in names:
        used |= {a for a in study.DECISIONS[k] if a.startswith("sb_")}
    assert set(NEW_FIELDS) - used - {"sb_pw_pools"} <= {"sb_lh_window", "sb_0700_window", "sb_0700_flat", "sb_london_window",
        "sb_early_start", "sb_moc_window", "sb_conf_min", "sb_conf_tol_pts", "sb_cons_bars", "sb_cons_pts", "sb_cons_body_mult",
        "sb_org_chop_bars", "sb_spotty_bars", "sb_spotty_min", "sb_spotty_tests", "sb_sync_min", "sb_ob_min_pts",
        "sb_stop_pts", "sb_gap424_fracs", "sb_supercharge_seasonal"}


def test_m33_use_bias_po3_entry_must_be_in_the_discount_of_the_reference_open():
    # the reference open is the midnight open 100.0: a long entry at 101.7 is in the premium, one at 98.7 in the discount
    down = [(o - 3.0, h - 3.0, l - 3.0, c - 3.0) for o, h, l, c in ROWS]
    p = dict(sb_use_bias=True, use_bias=True, sb_room_pts=1.0)
    assert one([("09:30", ROWS)], P(**p)) == []                                     # 101.7 > the open: wrong side
    assert len(one([("09:30", ROWS)], P(sb_use_bias=True, use_bias=False, sb_room_pts=1.0))) == 1     # the engine switch off: no test
    assert len(one([("09:30", ROWS)], P(use_bias=True))) == 1                       # the SB ignores it unless sb_use_bias
    t = one([("09:30", down)], P(**p))
    assert len(t) == 1 and t[0].entry == pytest.approx(98.7)
    assert one([("09:30", ROWS)], P(sb_use_bias=True, use_bias=True, mo_tol_pts=2.0)) != []      # Ep04.6 tolerance


def test_m38_sb_stop_090_is_the_default_alias():
    assert one(p=P(sb_stop="090"))[0].stop == one()[0].stop == pytest.approx(98.95)


# --- side-space mirroring: every long rule gives the short by mirroring ---------------------------------------------------

MIRROR_CASES = {
    "base": (ROWS, {}),
    "stop_swing": (ROWS, dict(sb_stop="swing")),
    "stop_fvg2": (ROWS, dict(sb_stop="fvg2")),
    "entry_ce": (ROWS, dict(sb_entry="ce")),
    "entry_candle": (ROWS[:9] + [(102.5, 102.6, 100.2, 101.6), (101.6, 104.0, 101.5, 103.9), (103.9, 108.6, 103.8, 108.5)],
                     dict(sb_stop="entry_candle")),
    "wide_size": (ROWS, dict(sb_max_stop_pts=2.0, sb_wide="size")),
    "pick_any": (THREE, dict(sb_fvg_pick="any_in_leg")),
    "bpr_exclude": (THREE, dict(sb_bpr_exclude=True)),
    "early": (EARLY, {}),
    "cancel_ticks": (CANCEL, dict(sb_cancel_ticks=3)),
    "adds": (ROWS[:10] + [(101.6, 104.0, 101.5, 103.9), (103.9, 104.0, 101.6, 102.0), (102.0, 108.6, 101.9, 108.5)],
             dict(sb_adds=True)),
    "abort": (ROWS[:10] + [(101.6, 101.7, 101.0, 101.2), (101.2, 101.3, 100.6, 100.8), (100.8, 108.6, 100.7, 108.5)],
              dict(sb_abort=True)),
    "two_entries": (ROWS2, dict(sb_max_per_window=2)),
    "ifvg_prefer": (IFVG, dict(sb_ifvg="prefer", or_minutes=0)),
    "ifvg_market": (IFVG, dict(sb_ifvg="prefer", sb_ifvg_market=True, or_minutes=0)),
    "cons": (CONS, dict(sb_cons_wait=True, sb_cons_bars=4)),
    "spotty_tag": (SPOTTY, dict(sb_spotty="tag")),
    "sweep_depth": (ROWS, dict(sb_need_sweep=True)),
    "ob": (OBR, dict(sb_entry_arrays=("ob",), sb_draw_first=True)),
    "untaken": (None, None),
}


@pytest.mark.parametrize("name", [k for k, v in MIRROR_CASES.items() if v[0] is not None])
def test_mirror_invariance_of_the_new_behaviours(name):
    rows, kw = MIRROR_CASES[name]
    long_t = one([("09:30", rows)], P(**kw))
    short_t = one([("09:30", mirror(rows))], P(**kw), hist=history(close=200.0, hi=210.0, lo=192.0), base=200.0)
    assert len(long_t) == len(short_t) >= 1, name
    for a, b in zip(long_t, short_t):
        assert (a.side, b.side) == ("long", "short")
        for f in ("entry", "stop", "t1"):
            assert getattr(a, f) + getattr(b, f) == pytest.approx(300.0, abs=1e-6), (name, f)
        assert a.shares == b.shares and a.entry_kind == b.entry_kind and a.lv_tags == b.lv_tags, name
        assert [e[3] for e in a.exits] == [e[3] for e in b.exits], name
        assert len(a.adds) == len(b.adds)
