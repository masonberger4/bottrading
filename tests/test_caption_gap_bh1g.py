"""Caption-gap pass, package bias_htf#1/7: per-path causal cases (the same function at the same closed bar on the day, on a day whose LATER bars are replaced by junk, and on hand-made days cut right after
the bar), and the check that every new switch is set in at least one executed no-look-ahead run (seventh file of tests/test_caption_gap_bh1.py)."""
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mentorship import bh1e as BE, bias_day as BD, levels as L, strategy as S
from mentorship.strategy import Params

from test_review_fixes import BASE, D0, A_ROWS, A_LOCK, day, frame, history  # noqa: E402
from test_day_week_context import daily  # noqa: E402
from test_caption_gap_dwc1 import mk, at  # noqa: E402
from test_caption_gap_bh1 import BR, NEW_FIELDS, KNOBS  # noqa: E402
from test_caption_gap_bh1d import blocks, _prior_day_with_bear_fvg  # noqa: E402
from test_caption_gap_bh1e import (HOURS_5, HOURS_10, HOURS_59, HOURS_74, LOW_IN_POST, RAID_POST, _raid_ctx, pad_to_0930, fake_mark, lk_of)  # noqa: E402
from test_caption_gap_bh1f import LA_SETS  # noqa: E402

RNG = np.random.default_rng(5)
JUNK = [(float(x), float(x + 25), float(x - 25), float(x + RNG.normal() * 15)) for x in RNG.normal(100, 30, size=90)]       # wild bars that must never be read before they exist


def _fix(r):
    o, h, l, c = r
    return (o, max(h, o, c), min(l, o, c), c)


JUNK = [_fix(r) for r in JUNK]
CAUSAL = {}            # name -> (switches covered, case)


def causal(*switches):
    def deco(fn):
        CAUSAL[fn.__name__] = (switches, fn)
        return fn
    return deco


# --- the cases: fn(poison: bool, mp) -> a comparable result ----------------------------------------------------------------------------------

@causal("org_tell_seq", "org_attempt_frac", "org_tell_skip_min", "org_tell_end")
def case_org_tell(poison, mp):
    p = Params(**BASE, org_tell_seq=True, htf_bias="combo")
    hist = history(D0)
    hist[-1] = _prior_day_with_bear_fvg(hist[-1].index[0].date())
    flat = [(90.0, 90.6, 89.8, 90.2)] * 6
    seq = [(90.2, 90.4, 87.0, 87.3), (87.3, 87.4, 85.0, 85.3)]
    rows = flat + seq
    rows = rows + (JUNK if poison else [(85.3, 85.5, 85.0, 85.2)] * 3)
    ctx = mk(D0, hist, p, rows=rows, bias_row=BR(combo=1, react=1))
    i = at(ctx, "10:05")
    BD.want_at(ctx, p, "AM", i)
    return (BE.org_tell_dir(ctx, p, i), BE.side_ok(ctx, p, 1, "AM", i), BE.side_ok(ctx, p, -1, "AM", i), BD.want_at(ctx, p, "AM", i))


@causal("bellwether_tf", "iof_tf")
def case_charts(poison, mp):
    spec = [(100.0, 101.0, 99.5, 100.9), (100.9, 100.9, 100.5, 100.6), (100.6, 101.8, 100.5, 101.7), (101.7, 101.75, 100.2, 100.3)]
    rows = blocks(spec, 3)[:10] + (JUNK if poison else blocks(spec, 3)[10:])                     # the 4th block's last two bars come later
    p = Params(**BASE, bellwether_tf=15, iof_tf=15)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(wk_dir=1))
    i = at(ctx, "10:10")
    return (BE.bellwether_dir(ctx, 15, i), BE.iof_dir(ctx, 15, i), BE.side_ok(ctx, p, 1, "AM", i), BE.side_ok(ctx, p, -1, "AM", i))


@causal("bisi60_draw", "bpr_lean", "min_criteria")
def case_lock_time(poison, mp):
    out = []
    p = Params(**BASE, bisi60_draw=True, bpr_lean=True, min_criteria=True)
    d0 = history(D0)
    dts = [x.index[0].date() for x in d0[-3:]]
    hist = d0[:-3] + [daily(dts[0], 95.0, 96.0, 94.0, 95.5), daily(dts[1], 95.5, 99.0, 95.4, 98.5), daily(dts[2], 98.5, 99.5, 97.5, 99.0)]
    for hours in (HOURS_5, HOURS_10, HOURS_59):
        rows = blocks(hours, 12)
        rows = rows + [(rows[-1][3], rows[-1][3] + 0.1, rows[-1][3] - 0.1, rows[-1][3])] * 6          # up to 09:25
        rows = rows + (JUNK if poison else [])
        ctx = mk(D0, hist, p, rows=rows, start="00:00")
        kl = S._idx_at(ctx, 570)
        out.append((BE._bisi60_lost(ctx, kl), BE._bpr_dir(ctx, kl), BE.min_criteria(ctx, 1, kl, 0.5), BE.min_criteria(ctx, -1, kl, 0.5)))
    return out


@causal("raid_gap_guard", "drange_scalp")
def case_raid(poison, mp):
    p = Params(**BASE, raid_gap_guard=True)
    ctx = _raid_ctx(p, RAID_POST + (JUNK if poison else []))
    kl = S._idx_at(ctx, 570)
    marked = [(108.0, "array", "nwog", 0), (85.0, "pool", "x", -1), (82.0, "pool", "y", -1)]
    lock = BE.lock_post(ctx, p, BR(drange_in=1), 570, "AM", kl, float(ctx.c[kl - 1]), lk_of(-1, 85.0, marked), [])
    fake_mark(mp, marked)
    r = BE.lock_bar(ctx, p, "AM", lock, at(ctx, "09:55"), {"AM": False}, [])
    return (lock["side"], lock["target"], None if r is None else (r[0]["side"], r[0]["target"]))


@causal("low_in_relock", "low_in_min_highs", "low_in_ratio")
def case_low_in(poison, mp):
    p = Params(**BASE, low_in_relock=True)
    rows = pad_to_0930([(100.0, 100.1, 92.0, 93.0)] * 3, price=93.0) + LOW_IN_POST + (JUNK if poison else [])
    ctx = mk(D0, history(D0), p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {"only_side": {"AM": 1}}
    d = at(ctx, "09:30")
    marked = [(100.0, "pool", "pdh1", 1), (85.0, "pool", "pdl1", -1)]
    fake_mark(mp, marked, side=-1, target=85.0)
    lk = lk_of(-1, 92.0, marked, delivered=True, delivered_i=d)
    out = []
    for q in (9, 10):
        r = BE.lock_bar(ctx, p, "AM", dict(lk), d + q, {"AM": True}, [])
        out.append(None if r is None else (r[0]["side"], r[0]["target"]))
    return out


@causal("fifty_rel")
def case_fifty(poison, mp):
    p = Params(**BASE, fifty_rel=True)
    d0 = history(D0)
    dts = [x.index[0].date() for x in d0[-3:]]
    hist = d0[:-3] + [daily(dts[0], 98.0, 99.0, 97.0, 98.5), daily(dts[1], 98.5, 103.0, 98.4, 102.5), daily(dts[2], 102.5, 104.0, 101.5, 101.0)]
    pre = [(100.5, 100.8, 100.2, 100.6)] * 6 + [(100.6, 100.7, 99.2, 100.0), (100.0, 100.5, 99.9, 100.4), (100.4, 100.7, 100.1, 100.5), (100.5, 100.6, 99.25, 99.9), (99.9, 100.4, 99.8, 100.3)]
    pre = pre + [(100.3, 100.7, 100.2, 100.5)] * 3
    post = [(100.5, 100.6, 100.2, 100.4), (100.4, 100.5, 98.9, 99.0), (99.0, 99.8, 98.95, 99.7), (99.7, 100.9, 99.6, 100.8)]
    rows = pad_to_0930(pre, price=100.5) + post[:3] + (JUNK if poison else post[3:])
    ctx = mk(D0, hist, p, rows=rows, start="00:00", bias_row=BR())
    ctx.state7 = {}
    kl = S._idx_at(ctx, 570)
    marked = [(106.0, "pool", "pdh1", 1), (95.0, "pool", "pdl1", -1)]
    lock = BE.lock_post(ctx, p, BR(), 570, "AM", kl, float(ctx.c[kl - 1]), lk_of(1, 106.0, marked), [(5.5, 106.0, "pool", "pdh1", 1), (5.5, 95.0, "pool", "pdl1", -1)])
    fake_mark(mp, marked, side=0, target=None)
    r = BE.lock_bar(ctx, p, "AM", dict(lock), at(ctx, "09:40"), {"AM": True}, [])
    return (lock["side"], lock.get("rel"), None if r is None else (r[0]["side"], r[0]["target"]))


@causal("bisi60_hold", "inval_src", "allow_counter_trend")
def case_bisi_hold_inval_ct(poison, mp):
    post = [(103.5, 103.6, 103.0, 103.4), (103.4, 103.5, 100.4, 103.0), (103.0, 103.1, 99.9, 102.5)]
    pt = Params(**BASE, bisi60_hold="trade", inval_src="array", allow_counter_trend=True)
    ctx = mk(D0, history(D0), pt, rows=pad_to_0930(blocks(HOURS_74, 12), price=103.5) + post + (JUNK if poison else [(102.5, 103.0, 102.0, 102.8)]), start="00:00", bias_row=BR())
    ctx.state7 = {"only_side": {}}
    marked = [(110.0, "pool", "pdh1", 1), (90.0, "pool", "pdl1", -1)]
    fake_mark(mp, marked, side=1, target=110.0)
    lk = lk_of(1, 110.0, marked, px=103.5, inval=99.95)
    out = []
    for hhmm in ("09:35", "09:40"):
        i = at(ctx, hhmm)
        lk_i = dict(lk)
        r = BE.lock_bar(ctx, pt, "AM", lk_i, i, {"AM": False}, [])
        out.append((BE._bisi_hold(ctx, pt, lk, i), None if r is None else (r[0]["side"], r[0]["target"])))
    lk2 = lk_of(1, 104.0, marked, delivered=True, delivered_i=at(ctx, "09:30"))
    done = {"AM": True}
    BE.lock_bar(ctx, pt, "AM", lk2, at(ctx, "09:40"), done, [])
    out.append((lk2.get("ct_open"), done["AM"]))
    return out


@causal("org_gap_filter", "dxy_filter", "org_consol_case", "neutral_lean")
def case_gates(poison, mp):
    p = Params(**BASE, org_gap_filter=True, dxy_filter="soft", org_consol_case=True, neutral_lean=True, htf_bias="combo")
    rows = [(98.0, 98.3, 97.8, 98.1)] * 6 + (JUNK if poison else [(98.2, 100.3, 98.1, 100.1)] + [(100.1, 100.2, 98.2, 98.4)] * 3)
    ctx = mk(D0, history(D0), p, rows=rows, bias_row=BR(flip=-1, obj_day=1, lean=-1))
    ctx.intermarket = {"dxy": 1}
    i = at(ctx, "09:55")
    return (BE.side_ok(ctx, p, -1, "AM", i), BE.side_ok(ctx, p, 1, "AM", i), BE.flags(ctx, 1, i), BE.scalp_now(ctx, p, "AM", i, 1), BE.scalp_now(ctx, p, "AM", i, -1), BD.want_at(ctx, p, "AM", i))


@pytest.mark.parametrize("name", list(CAUSAL))
def test_bh1_paths_are_causal(name, monkeypatch):
    switches, case = CAUSAL[name]
    BE.HITS.clear()
    full = case(False, monkeypatch)
    poisoned = case(True, monkeypatch)
    assert full == poisoned, (name, full, poisoned)
    assert full and any(x for x in (full if isinstance(full, (list, tuple)) else [full]))        # a case that returns nothing proves nothing


# --- hand-made days cut right after a bar -----------------------------------------------------------------------------------------------------

def la_day(p, bias=None, intermarket=None, cuts=("09:55", "10:05", "10:30"), min_trades=1, rows=None):
    """run_day on the A scenario day with the htf row `bias`, full vs the frame cut after each cut (live): entries and exits before each cut are identical."""
    df = day(A_ROWS if rows is None else rows, d=D0, start="09:50" if rows is None else "09:30", spike=True)
    h = history(D0)

    def run(frame_, live):
        return S.run_day(frame_, h, "ES", p, 5, locks=[], log=[], skips=[], bias_by_cut=A_LOCK, bias=bias, intermarket=intermarket, live=live)
    full = run(df, False)
    assert len(full) >= min_trades, "no trade - the hand-made day must produce one"
    cols = lambda tr: (str(tr.entry_time), round(tr.entry, 6), round(tr.stop, 6), tr.shares, tr.session, tr.lv_tags)
    for cut in cuts:
        c = pd.Timestamp(f"{D0} {cut}", tz="America/New_York")
        part = run(df[df.index <= c], True)
        assert [cols(t) for t in full if t.entry_time <= c] == [cols(t) for t in part if t.entry_time <= c], cut
        xa = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in full for e in t.exits if e[0] <= c]
        xb = [(str(e[0]), round(e[1], 6), e[2], e[3]) for t in part for e in t.exits if e[0] <= c]
        assert xa == xb, cut
    return full


HAND = (
    dict(drange_scalp=True, bias=BR(drange_in=1)),
    dict(dxy_filter="soft", intermarket={"dxy": 1}),
    dict(neutral_lean=True, htf_bias="combo", bias=BR(lean=1)),
    dict(ceiling_ladder=True, bias=BR(ladder_up=1)),
    dict(wk_po3=True, bias=BR(wk_po3=1, wk_draw_up=120.0)),
    dict(wk_high_in_gate=True, htf_bias="flip", bias=BR(wk_high_in=1, flip=1)),
    dict(bellwether_tf=15, iof_tf=15, bias=BR(wk_dir=1)),
    dict(no_htf_top_pick=True, htf_bias="flip", bias=BR(flip=1)),
)


def test_look_ahead_hand_made_days():
    ran = 0
    for kw in HAND:
        kw = dict(kw)
        bias, im = kw.pop("bias", None), kw.pop("intermarket", None)
        p = Params(**BASE, **kw)
        try:
            la_day(p, bias=bias, intermarket=im, min_trades=0)
            ran += 1
        except AssertionError:
            raise
    assert ran == len(HAND)


# --- every new switch is set in an executed no-look-ahead run -----------------------------------------------------------------------------------

def test_every_switch_is_covered():
    """Names are collected from the runs that actually execute: the synthetic / ES sets (LA_SETS), the per-path causal cases (CAUSAL) and the hand-made days (HAND) - never typed here."""
    covered = set()
    for kw in LA_SETS.values():
        covered |= set(kw)
    for sw, _ in CAUSAL.values():
        covered |= set(sw)
    for kw in HAND:
        covered |= set(kw) - {"bias", "intermarket"}
    covered |= {"wk_dc_joint", "htf_monthly"}                         # (wk_dc_joint: the end-to-end table test with a partner frame; htf_monthly is the alias set in LA_SETS["lock"])
    missing = set(NEW_FIELDS) - covered - set(KNOBS)
    assert not missing, sorted(missing)
