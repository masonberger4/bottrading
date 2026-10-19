"""ICT's Silver Bullet as its own setup (mentorship/digests/silver_bullet.md; 044, 054, 057,
058, 059, 060, 065B, 090).

Per window (AM 10:00-11:00, PM 14:00-15:00; London 03:00-04:00 optional, futures only; the optional
15:00-16:00 (entries to 15:50), 07:00-08:30 (flat 08:29) and 15:15-15:45 windows are switches):
  draw    the nearest untaken liquidity/array beyond the entry (PDH/PDL, session H/L, opening
          range, NWOG/NDOG/ORG levels, HTF arrays - the bot's target list); it must offer at
          least `sb_room_pts` ES points of room (10 for new traders, 5 for experienced, 046) -
          a MINIMUM, not the goal (owner #2). sb_draw_first marks the 054 draw list and locks ONE
          draw before the window (M3.2); owner #9's session lock does the same without it.
  trigger displacement toward the draw: a close beyond the swing that led into the leg's
          extreme (MSS). A liquidity sweep is not required (tagged when present; sb_need_sweep).
  FVG     faces the trade, sits beyond the broken swing, still open, formed after the leg's
          extreme - it may come from the 09:30-10:00 (13:30-14:00) leg (058 ~44:37, 065B); with
          sb_fvg_in_window only from inside the window. Evolving SB (057): the newest such FVG
          price has not yet traded back into; sb_fvg_pick "first" / "any_in_leg" (093).
  entry   limit at the FVG's near edge (sb_entry "ce": 048 worst case), fills only inside the
          window; cancelled if the target trades first or at the window end. Extra entry arrays:
          IFVG (076), 5m order block (049), wick CE / VI / MT confluence (090).
  stop    below the FVG's first candle low and the order block mean threshold (090); sb_stop:
          057 "fvg2", 086 "entry_candle", "swing", 069 "fvg_ce".
  exit    at the draw (nearest untaken liquidity/array, exit_before applied); a fixed
          +sb_target_pts is a switch (sb_target_mode="fixed"); optional runner to the next
          draw. Capped by an unbroken opposing HTF FVG (owner #7); toward the session's locked
          draw only (owner #9). AM-window units close at 12:00 (owner #8). Flat at the close.
  count   one Silver Bullet per window (sb_max_per_window), independent of the bot's other setups.
Direction filters (all off by default): sb_draw_first + sb_day_dir (one way per day), displacement
size (sb_disp_*), ES/NQ/YM sync (sb_sync), spotty-day skip (sb_spotty), weekly profile (sb_weekly).
Every switch cites its rule id and source in strategy.Params ("silver_bullet package" block).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import levels as L

MSS_MODES = ("close", "wick")

_CHOICES = {
    "sb_mgmt": ("fixed", "ladder", "gap424", "layered057"),
    "sb_fvg_pick": ("evolving", "first", "any_in_leg"),
    "sb_day_dir": ("off", "lock", "first_trade"),
    "sb_day_dir_delivered": ("hold", "free"),
    "sb_weekly": ("off", "tag", "require"),
    "sb_weekly_neutral": ("allow", "skip"),
    "sb_sync": ("off", "tag", "require"),
    "sb_sync_mode": ("dir", "mss"),
    "sb_spotty": ("off", "tag", "skip"),
    "sb_sweep_alt": ("", "discount_array"),
    "sb_lrc_mode": ("tag", "wait", "skip"),
    "sb_premise": ("", "htf_array", "smt", "either"),
    "sb_nwog_expansion": ("", "tag", "require"),
    "sb_ifvg": ("", "add", "prefer"),
    "sb_ifvg_stop": ("candle", "breaker"),
    "sb_conf_mode": ("tag", "entry"),
    "sb_stop": ("fvg_ob", "090", "fvg2", "entry_candle", "swing", "fvg_ce"),   # "090" = "fvg_ob" (the rule_coverage name)
    "sb_wide": ("skip", "size"),
    "sb_room_mode": ("exit", "draw"),
    "sb_fail_mode": ("skip", "scalp"),
}
_SETS = {
    "sb_extra": ("pm2", "early"),
    "sb_entry_arrays": ("fvg", "ob", "confluence"),
    "sb_spotty_tests": ("no_disp", "no_fvg", "whipsaw", "no_draw"),
}


def check_params(p) -> None:
    """Params.__post_init__ hook (SB package): reject unknown values of the silver_bullet switches."""
    for name, ok in _CHOICES.items():
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    for name, ok in _SETS.items():
        bad = set(getattr(p, name)) - set(ok)
        if bad:
            raise ValueError(f"{name} {sorted(bad)}: expected from {ok}")
    if "fvg" not in p.sb_entry_arrays and not ({"ob", "confluence"} & set(p.sb_entry_arrays)) and not p.sb_ifvg:
        raise ValueError("sb_entry_arrays needs at least one entry array")
    if p.sb_max_per_window < 1:
        raise ValueError(f"sb_max_per_window {p.sb_max_per_window}: expected >= 1")
    if p.sb_cancel_ticks < 0 or p.sb_conf_min < 2 or p.sb_org_chop_bars < 1 or p.sb_cons_bars < 2:
        raise ValueError("sb_cancel_ticks >= 0, sb_conf_min >= 2, sb_org_chop_bars >= 1, sb_cons_bars >= 2 expected")
    if len(p.sb_gap424_fracs) < 2 or abs(sum(p.sb_gap424_fracs) - 1.0) > 1e-6:
        raise ValueError(f"sb_gap424_fracs {p.sb_gap424_fracs!r}: expected >= 2 fractions summing to 1")
    for name in ("sb_lh_window", "sb_0700_window", "sb_london_window", "sb_moc_window"):
        w = getattr(p, name)
        if len(w) != 2 or not 0 <= w[0] < w[1] <= 1440:
            raise ValueError(f"{name} {w!r}: expected (start_minute, end_minute)")


# --- windows ---------------------------------------------------------------------------------------------------------

@dataclass
class Win:
    name: str            # london / 0700 / am / pm / lh / moc
    session: str         # "AM" / "PM": the parent session (blocked(), owner #8, risk state)
    setup: str           # Trade.setup
    a: int               # first minute an entry may fill
    b: int               # first minute it may not
    leg_from: int        # the leg the FVG / displacement may come from starts here
    flat: int | None = None   # the window's own flat (07:00: 08:29)
    max_n: int = 1       # SB entries in the window
    classic: bool = True  # one of London / AM / PM (the 054 cascade)


def windows(p) -> list:
    """T6 / M3.1: the windows in use, in time order. [our interpretation] leg starts: London 02:00,
    07:00 window 06:00, last hour 14:30, 15:15 window 14:30."""
    w = []
    mx = p.sb_max_per_window
    if p.sb_london:
        w.append(Win("london", "AM", "sb_london", p.sb_london_window[0], p.sb_london_window[1], 120, max_n=mx))
    if p.sb_0700:
        w.append(Win("0700", "AM", "sb_0700", p.sb_0700_window[0], p.sb_0700_window[1], 360,
                     flat=p.sb_0700_flat, max_n=mx, classic=False))
    a_am = p.sb_early_start if "early" in p.sb_extra else p.sb_windows[0][0]
    w.append(Win("am", "AM", "sb_am", a_am, p.sb_windows[0][1], 570, max_n=mx))
    w.append(Win("pm", "PM", "sb_pm", p.sb_windows[1][0], p.sb_windows[1][1], 810,
                 max_n=max(mx, 2) if "pm2" in p.sb_extra else mx))
    if p.sb_last_hour:
        w.append(Win("lh", "PM", "sb_lh", p.sb_lh_window[0], p.sb_lh_window[1], 870, max_n=mx, classic=False))
    if p.sb_moc_extra and not p.sb_last_hour:          # (the 15:00-15:50 window already covers 15:15-15:45)
        w.append(Win("moc", "PM", "sb_moc", p.sb_moc_window[0], p.sb_moc_window[1], 870, max_n=1, classic=False))
    return sorted(w, key=lambda x: (x.a, x.b))


# --- day-level reads (known before the first window) -----------------------------------------------------------------

def weekly_profile(ctx, p, day) -> dict:
    """The weekly profile read (048 ~2:02:12: "a classic bullish weekly profile would be a Tuesday low of the week in
    London") [our interpretation]. From the completed sessions of this week: `side` +1 when the week's low is in on
    Monday / Tuesday and the last close is above the week's open (mirror -1); 0 otherwise or on Mondays. `early_up` /
    `early_dn` are 1 while it is Monday-Wednesday and the week's low (high) is not yet clearly in: within 0.5 x ADR5 of
    the last close (the supercharge test, gap 8). Uses completed days only."""
    from .strategy import adr5
    hist = getattr(ctx, "hist", [])
    iso = day.isocalendar()[:2]
    wk = [g for g in hist if g.index[0].date().isocalendar()[:2] == iso and g.index[0].date() < day]
    out = dict(side=0, early_up=0, early_dn=0, low_day=None, high_day=None)
    if not wk:
        return out
    lows = [float(g.low.min()) for g in wk]
    highs = [float(g.high.max()) for g in wk]
    ld, hd = int(np.argmin(lows)), int(np.argmax(highs))
    out["low_day"], out["high_day"] = wk[ld].index[0].weekday(), wk[hd].index[0].weekday()
    o0, c1 = float(wk[0].open.iloc[0]), float(wk[-1].close.iloc[-1])
    up = wk[ld].index[0].weekday() <= 1 and c1 > o0
    dn = wk[hd].index[0].weekday() <= 1 and c1 < o0
    if up and not dn:
        out["side"] = 1
    elif dn and not up:
        out["side"] = -1
    elif up and dn:
        out["side"] = 1 if (c1 - min(lows)) >= (max(highs) - c1) else -1
    adr = adr5(hist[-5:]) if len(hist) >= 5 else None
    if adr and day.weekday() <= 2:
        out["early_up"] = int((c1 - min(lows)) < 0.5 * adr)      # long: the week's low not yet clearly in
        out["early_dn"] = int((max(highs) - c1) < 0.5 * adr)     # short: the week's high not yet clearly in
    return out


def window_row(ctx, win):
    """The htf table row a window may read: its own lock-time cut (bias_by_cut), else the 09:30 row for windows that start
    the leg at or after 09:30; a pre-open window without a cut table reads nothing (the 09:30 row holds the overnight)."""
    row = getattr(ctx, "bias_by_cut", {}).get(win.leg_from)
    if row is None and win.leg_from >= 570:
        row = getattr(ctx, "bias_row", None)
    return row


def daily_ranging(ctx, p, row=None) -> bool:
    """Gap 8 [our interpretation]: the daily is ranging when the htf table's bias column is flat (0) or the last 3
    daily bodies all sit inside the 5-day range that preceded them."""
    hist = getattr(ctx, "hist", [])
    col = p.htf_bias if p.htf_bias != "off" else "combo"
    flat = True
    if row is not None:
        try:
            flat = int(row[col]) == 0
        except Exception:
            flat = True
    if len(hist) < 8:
        return flat
    prior, last = hist[-8:-3], hist[-3:]
    hi = max(float(g.high.max()) for g in prior)
    lo = min(float(g.low.min()) for g in prior)
    inside = all(lo <= min(float(g.open.iloc[0]), float(g.close.iloc[-1])) and
                 max(float(g.open.iloc[0]), float(g.close.iloc[-1])) <= hi for g in last)
    return flat or inside


def want_side(ctx, p, row=None) -> int | None:
    """M3.3: the main engine's `want` (htf_bias column of the window's htf row); None = no bias filter."""
    if p.htf_bias == "off":
        return None
    return 0 if row is None else int(row[p.htf_bias])


def ote_levels(ctx, sd) -> list:
    """L14g (054 ~04:02): a classic OTE as a draw [our interpretation]: the 62% retracement edge of the prior session's
    leg, in the direction price has to retrace (prior day down -> the premium OTE above, up -> the discount OTE below).
    Side space; the near edge of the 62-79% band."""
    hist = getattr(ctx, "hist", [])
    if not hist:
        return []
    g = hist[-1]
    o, c = float(g.open.iloc[0]), float(g.close.iloc[-1])
    hi, lo = float(g.high.max()), float(g.low.min())
    if hi <= lo:
        return []
    if c < o:                                            # a down leg retraces UP into the OTE
        v = lo + 0.62 * (hi - lo)
    else:
        v = hi - 0.62 * (hi - lo)
    return [sd.x(v)]


def spotty_day(ctx, p, win, a_idx: int, k0: int, tf: int) -> tuple:
    """045 ~31:22-36:27 "spotty" [our interpretation; filters.md: no measurable definition]. Read the bars from the
    leg start up to the window start (closed bars only): `no_disp` no energetic candle (range >= 2 x the mean range
    of the 20 bars before the region, body >= 60% of it); `no_fvg` no fair value gap of either direction formed in the
    region; `whipsaw` >= 60% of the close-to-close steps change direction; `no_draw` strategy._no_draw (B1).
    Spotty when >= sb_spotty_min of sb_spotty_tests hold. Returns (spotty, reasons)."""
    h, l, o, c = ctx.h, ctx.l, ctx.o, ctx.c
    a = min(a_idx, len(c))
    lo_i = max(k0, a - max(3, p.sb_spotty_bars // max(tf, 1)))
    if a - lo_i < 3:
        return False, ()
    rng = h[lo_i:a] - l[lo_i:a]
    pre = (h[max(0, lo_i - 20):lo_i] - l[max(0, lo_i - 20):lo_i])
    base = float(pre.mean()) if len(pre) else float(rng.mean())
    why = []
    if "no_disp" in p.sb_spotty_tests:
        body = np.abs(c[lo_i:a] - o[lo_i:a])
        if not ((rng >= 2.0 * base) & (body >= 0.6 * np.maximum(rng, 1e-12))).any():
            why.append("no_disp")
    if "no_fvg" in p.sb_spotty_tests:
        gp = [z for z in L.fvgs(h[lo_i - 2:a] if lo_i >= 2 else h[:a], l[lo_i - 2:a] if lo_i >= 2 else l[:a])
              if z.top - z.bottom >= p.min_fvg_pts * p.es_pt]
        if not gp:
            why.append("no_fvg")
    if "whipsaw" in p.sb_spotty_tests:
        d = np.sign(np.diff(c[lo_i:a]))
        d = d[d != 0]
        if len(d) >= 2 and float((d[1:] != d[:-1]).mean()) >= 0.6:
            why.append("whipsaw")
    if "no_draw" in p.sb_spotty_tests:
        from .strategy import _no_draw
        if _no_draw(ctx, p, win.session, min(a, len(c) - 1), getattr(ctx, "bias_by_cut", {})):
            why.append("no_draw")
    return len(why) >= p.sb_spotty_min, tuple(why)


def _partners(ctx) -> list:
    """ES/NQ/YM: the sister indices present on this day as (DayCtx, {sign: Side}, positions)."""
    out = []
    ps = getattr(ctx, "pside", None)
    if ps and ps[0] is not None:
        out.append(ps)
    p2 = getattr(ctx, "partner2", None)
    if p2 is not None:
        out.append(p2)
    return out


def _pj(ctx, pctx, ppos, k: int) -> int:
    """The sister's bar at (or just before) ctx's bar k, by time."""
    return int(ppos.index.searchsorted(ctx.idx[k], side="right")) - 1


def sync_state(ctx, sd, k0: int, li: int, i: int, p) -> tuple:
    """ES/NQ/YM in sync (045 ~1:01:43; 048 ~11:38; filters.md 1.4) [our interpretation]: each sister must have moved the
    same way over the displacement leg - its close at bar i above its close at the bar of our leg low - and, with
    sb_sync_mode "mss", also closed above its own last swing high before its leg low (it broke too). Returns
    (ok, n_in_sync, n_sisters): ok None when no sister is present (no data to judge)."""
    ps_list = _partners(ctx)
    n_in = n = 0
    for pctx, psides, ppos in ps_list:
        ps = psides[sd.sign]
        j0, jl, ji = _pj(ctx, pctx, ppos, k0), _pj(ctx, pctx, ppos, li), _pj(ctx, pctx, ppos, i)
        if min(j0, jl, ji) < pctx.start or ji <= jl:
            continue
        n += 1
        lj = j0 + int(np.argmin(ps.l[j0:ji + 1]))
        ok = ps.c[ji] > ps.c[jl] and lj < ji
        if ok and p.sb_sync_mode == "mss":
            refs = [q for q in ps.ph if q.i < lj and q.known <= ji]
            ok = bool(refs) and bool((ps.c[lj + 1:ji + 1] > refs[-1].price).any())
        n_in += int(ok)
    if n == 0:
        return None, 0, 0
    return n_in >= min(p.sb_sync_min, n), n_in, n


def cons_box(sd, a_idx: int, i: int, p):
    """Gap 21 (072 ~35:41) [our interpretation]: the latest consolidation box ending at or before bar i: sb_cons_bars
    consecutive closed bars (from the window start on) whose high-low range is <= sb_cons_pts ES pts. Returns
    (top, bottom, end_index, mean_body) or None."""
    n = p.sb_cons_bars
    best = None
    for e in range(max(a_idx, 0) + n - 1, i + 1):
        s = e - n + 1
        top, bot = float(sd.h[s:e + 1].max()), float(sd.l[s:e + 1].min())
        if top - bot <= p.sb_cons_pts * p.es_pt:
            best = (top, bot, e, float(np.abs(sd.c[s:e + 1] - sd.o[s:e + 1]).mean()))
    return best


# --- entry candidates and filters (arming) ---------------------------------------------------------------------------

def _bears(sd):
    """Bearish FVGs of the side (cached): the SIBIs against a long, in side space."""
    return sd._lazy("sb_bears", lambda: [z for z in L.fvgs(sd.h, sd.l, sd.o, sd.c, sd.c2_dir)
                                         if z.kind == "bear" and z.top - z.bottom >= sd.min_gap])


def _resample(ctx, sd, lo: int, hi: int, m: int):
    """Complete m-minute bars of side-space bars [lo, hi] (closed bars only, grouped by clock), as
    (o, h, l, c, first_index, last_index) arrays; a group counts only when its last base bar closes the m-minute slot."""
    tf = ctx.tf
    if m <= tf:
        return None
    n = hi - lo + 1
    if n < 1:
        return None
    key = [(int(ctx.idx[k].value // 1_000_000_000 // 60) // m) for k in range(lo, hi + 1)]
    groups, cur = [], []
    for k, g in zip(range(lo, hi + 1), key):
        if cur and g != cur[0][1]:
            groups.append(cur)
            cur = []
        cur.append((k, g))
    if cur:
        groups.append(cur)
    o, h, l, c, f, e = [], [], [], [], [], []
    for gr in groups:
        ks = [k for k, _ in gr]
        last_end = int(ctx.idx[ks[-1]].value // 1_000_000_000 // 60) + tf
        slot_end = (gr[0][1] + 1) * m
        if last_end < slot_end or len(ks) * tf < m:
            continue                                    # the slot is still open (or starts before `lo`)
        o.append(sd.o[ks[0]]); h.append(sd.h[ks].max()); l.append(sd.l[ks].min()); c.append(sd.c[ks[-1]])
        f.append(ks[0]); e.append(ks[-1])
    if not o:
        return None
    return (np.array(o), np.array(h), np.array(l), np.array(c), np.array(f), np.array(e))


def _sweep_levels(ctx, sd, i, p, session) -> dict:
    """Side-space sell-side levels a leg low may have swept: the prior day / overnight lows and the session pools."""
    out = {}
    pre = ctx.t[i] < 570                               # the overnight range / London pool are incomplete before 09:30 / 05:00
    for nm, v in ctx.pd.items():
        if pre and nm.startswith("pm"):
            continue
        if nm.startswith(("pdl", "pml")) and sd.sign > 0:
            out[nm] = sd.x(v)
        elif nm.startswith(("pdh", "pmh")) and sd.sign < 0:
            out[nm] = sd.x(v)
    out.update(_sell_side_known(ctx, sd, session, i, p))
    return out


def _sell_side_known(ctx, sd, session, i, p) -> dict:
    """strategy._sell_side without the levels a pre-09:30 bar cannot know (the premarket range, today's ORG, London before 05:00)."""
    from .strategy import _sell_side
    out = dict(_sell_side(ctx, sd, session, i, True, p))
    if ctx.t[i] < 570:
        out.pop("premarket", None)
    if ctx.t[i] < 300:
        out.pop("london", None)
    return out


def sweep_info(ctx, sd, li, i, p, session) -> tuple:
    """M3.5 (054; 055; 056; 058): the nearest level the leg low swept (`name`, depth in ES pts beyond it) - the last level
    taken [our interpretation]; ("none", None) when it swept nothing."""
    from .strategy import _thru, _tick
    lo = float(sd.l[li])
    best = None
    for nm, v in _sweep_levels(ctx, sd, i, p, session).items():
        if _thru(lo, v, _tick(p)) and (best is None or v - lo < best[1]):
            best = (nm, v - lo)
    return ("none", None) if best is None else (best[0], round(best[1] / p.es_pt, 4))


def _premise(ctx, sd, li, i, p, session) -> str:
    """Gap 13 (054 ~14:20 PM; 093 ~8:40) [our interpretation]: "htf_array" = the leg low traded into a valid HTF array
    of the trade's side (15m .. daily) and sits in the discount half of the range from the overnight start; "smt" = a
    swept level the sister index did NOT take (strategy._smt is True: the sister's higher low). Returns the premise
    that held ("htf_array" / "smt") or ""."""
    from .strategy import _smt, _thru, _tick
    mode = p.sb_premise
    if mode in ("htf_array", "either"):
        cf = getattr(ctx, "conf", None)
        if cf is not None:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            tfs = cf.at(now, sd.x(float(sd.l[li])), sd.sign)
            hi, lo = float(sd.h[ctx.start:li + 1].max()), float(sd.l[ctx.start:li + 1].min())
            if set(tfs) & {"15m", "30m", "1h", "4h", "D"} and sd.l[li] < (hi + lo) / 2:
                return "htf_array"
    if mode in ("smt", "either"):
        ps = getattr(ctx, "pside", None)
        if ps and ps[0] is not None:
            pctx, psides, ppos = ps
            for key, v in _sell_side_known(ctx, sd, session, i, p).items():
                if _thru(float(sd.l[li]), v, _tick(p)) and _smt(ctx, sd, i, key, v, session, pctx, psides, ppos, p) is True:
                    return "smt"
    return ""


def _discount_array(ctx, sd, k0, li, kb, g, p) -> bool:
    """Gap 5 (048 ~6:54, ~26:50, ~1:36:06): the discount array stands in for the Judas raid [our interpretation of
    each condition]: (1) a bias-side pool (the prior highs, the overnight high) traded before the leg low; (2) the leg
    low sits inside a bullish breaker, or inside an earlier bullish FVG of the frame (the week's initial FVG proxy);
    (3) it is in the discount half of the range from the overnight start to the high so far; (4) the opposing FVG the
    leg left (leg_sibi) was broken (close above its top) and the entry FVG sits above it."""
    h, l, o, c = sd.h, sd.l, sd.o, sd.c
    pre = ctx.t[min(li, len(ctx.t) - 1)] < 570
    pools = [sd.x(v) for nm, v in ctx.pd.items() if (nm.startswith(("pdh", "pmh")) and sd.sign > 0
                                                     or nm.startswith(("pdl", "pml")) and sd.sign < 0)
             and not (pre and nm.startswith("pm"))]
    if not pools or not any(h[ctx.start:li].max(initial=-np.inf) >= v - 1e-12 for v in pools):
        return False
    lo_i = float(l[li])
    bz = L.breaker_zone(o, h, l, c, k0, li, li, "bull")
    inside = bz is not None and bz.bottom <= lo_i <= bz.top
    if not inside:
        inside = any(z.kind == "bull" and z.i < k0 and z.bottom <= lo_i <= z.top for z in sd.gaps)
    if not inside:
        return False
    hi_, lo_ = float(h[ctx.start:li + 1].max()), float(l[ctx.start:li + 1].min())
    if not lo_i < (hi_ + lo_) / 2:
        return False
    sib = L.leg_sibi(h, l, o, c, max(k0, 2), li, sd.c2_dir)
    return bool(sib is not None and kb is not None and c[kb] > sib.top and g is not None and g.bottom >= sib.top)


def _nwog_react(ctx, sd, li, i, p) -> bool:
    """Gap 22 (054 ~5:17): the leg low reacted at (traded into or within eq_tol of) an NWOG known at bar i."""
    from .strategy import _nwogs
    x = sd.x(float(sd.l[li]))
    tol = p.eq_tol_pts * p.es_pt
    return any(min(a, b) - tol <= x <= max(a, b) + tol for a, b in _nwogs(ctx, i))


def _ifvg_cands(ctx, sd, k0, li, i, p, kb) -> list:
    """Gap 1 (076 ~23:03; 092 ~21:36; 044 ~38:17): an earlier same-day FVG that the in-window displacement closes
    through is an IFVG (A8) and its near edge an entry. Side space: a bearish gap formed before the leg low, not yet
    closed through at the low, closed above its top by a base-bar close in (li, i]. Base-timeframe gaps plus 5m gaps
    (built from complete 5m bars). Tag "ifvg_breaker" when it overlaps the bullish breaker of the leg (the Reaper case)."""
    h, l, o, c = sd.h, sd.l, sd.o, sd.c
    zs = []                                              # (top, bottom, formed index, source index)
    for z in _bears(sd):
        if ctx.start <= z.i < li:
            zs.append((z.top, z.bottom, z.i, z.src))
    r5 = _resample(ctx, sd, ctx.start, li, 5)
    if r5 is not None:
        o5, h5, l5, c5, f5, e5 = r5
        for z in L.fvgs(h5, l5, o5, c5, sd.c2_dir):
            if z.kind == "bear" and z.top - z.bottom >= sd.min_gap:
                zs.append((z.top, z.bottom, int(e5[z.i]), int(f5[z.i - 1])))
    bz = L.breaker_zone(o, h, l, c, k0, li, i, "bull") if li > k0 else None
    rp = L.reaper(o, h, l, c, k0, k0 + int(np.argmax(h[k0:li + 1])), li, sd.c2_dir) if (p.sb_ifvg_reaper and li > k0 + 2) else None
    out, seen = [], set()
    for top, bot, fi, src in zs:
        if (round(top, 6), round(bot, 6)) in seen:
            continue
        if c[fi + 1:li + 1].max(initial=-np.inf) > top:
            continue                                     # already closed through before the low
        hit = np.flatnonzero(c[li + 1:i + 1] > top)
        if not len(hit):
            continue
        ki = li + 1 + int(hit[0])
        seen.add((round(top, 6), round(bot, 6)))
        brk = bz is not None and bz.bottom < top and bz.top > bot
        out.append(dict(kind="ifvg_breaker" if brk else "ifvg", top=float(top), bottom=float(bot), i=ki, g=None,
                        first_low=float(l[li]), src=src, bz=bz if brk else None,
                        passes=L.ifvg_passes(h, l, top, bot, fi, ki)))
    if rp is not None and (round(rp.top, 6), round(rp.bottom, 6)) not in seen and rp.i <= i:
        out.append(dict(kind="ifvg_breaker", top=float(rp.top), bottom=float(rp.bottom), i=rp.i, g=rp,
                        first_low=float(l[li]), src=rp.src, bz=bz, passes="none", reaper=True))
    return out


def _ob_cand(ctx, sd, k0, a_idx, i, p, lock, want) -> dict | None:
    """Gap 9 (049 ~2:00): a 5m order block that formed before the window; price inside it when the window opens is a
    scalp entry toward a locked / HTF draw [our interpretation: the OB is the last down-close 5m candle at the
    start of the pre-window leg to its high]. Needs a locked draw on the trade's side (or the htf bias)."""
    if lock is not None:
        if lock["side"] != sd.sign:
            return None
    elif not want or want != sd.sign:
        return None
    hi_i = min(a_idx - 1, i)
    r5 = _resample(ctx, sd, k0, hi_i, 5)
    if r5 is None or len(r5[0]) < 3:
        r5 = None
        if ctx.tf >= 5 and hi_i - k0 >= 2:               # the base bars are already >= 5m
            r5 = (sd.o[k0:hi_i + 1], sd.h[k0:hi_i + 1], sd.l[k0:hi_i + 1], sd.c[k0:hi_i + 1],
                  np.arange(k0, hi_i + 1), np.arange(k0, hi_i + 1))
        if r5 is None:
            return None
    o5, h5, l5, c5, f5, e5 = r5
    lo5 = int(np.argmin(l5))
    if lo5 >= len(l5) - 1:
        return None
    hi5 = lo5 + int(np.argmax(h5[lo5:]))
    if hi5 <= lo5:
        return None
    ob = L.order_block_blend(o5, h5, l5, c5, max(0, lo5 - 3), min(lo5 + 1, hi5), "bull")
    if ob is None:
        return None
    return dict(kind="ob", top=float(ob.top), bottom=float(ob.bottom), i=max(a_idx - 1, 0), g=None,
                first_low=float(ob.bottom), mt=float(ob.mt) if ob.mt == ob.mt else float(ob.mid), ob=ob)


def _conf_levels(ctx, sd, k0, i, g, ob, p) -> tuple | None:
    """Gap 10 (090 ~1:45-2:01) [our interpretation]: where a wick CE (1m / 5m / 1h candles), a volume-imbalance edge and
    the order block mean threshold agree (>= sb_conf_min distinct kinds within sb_conf_tol_pts), below the FVG top.
    Returns (mean, kinds, mt) or None."""
    h, l, o, c = sd.h, sd.l, sd.o, sd.c
    tol = p.sb_conf_tol_pts * p.es_pt
    lv = []
    for k in range(k0, i + 1):
        lv.append((float(L.wick_ce(o, l, c, k)), "wick"))
    for m in (5, 60):
        r = _resample(ctx, sd, k0, i, m)
        if r is not None:
            o_, h_, l_, c_, f_, e_ = r
            lv += [(float(L.wick_ce(o_, l_, c_, k)), "wick") for k in range(len(o_))]
    for z in sd.vis("bull"):
        if k0 <= z.i <= i:
            lv += [(float(z.top), "vi"), (float(z.bottom), "vi")]
    mt = None
    if ob is not None and ob.mt == ob.mt:
        mt = float(ob.mt if p.mt_mode == "body" else ob.mid)
        lv.append((mt, "mt"))
    lv = sorted(x for x in lv if x[0] <= g.top)
    if mt is not None:                                 # the idea is "support where they agree with the MT" (090)
        grp = [x for x in lv if abs(x[0] - mt) <= tol]
        kinds = {k for _, k in grp}
        if len(kinds) >= p.sb_conf_min:
            return float(np.mean([x[0] for x in grp])), kinds, mt
        return None
    best = None
    for j, (v, _) in enumerate(lv):
        grp = [x for x in lv if v - 1e-12 <= x[0] <= v + tol]
        kinds = {k for _, k in grp}
        if len(kinds) >= p.sb_conf_min and (best is None or len(kinds) > len(best[1])):
            best = (float(np.mean([x[0] for x in grp])), kinds, mt)
    return best


def _gap424(ctx, sd, i, entry, p) -> list | None:
    """M3.11 / 057 ~3:30 (4 / 2 / 4 of 10 at the NWOG high / 75% / CE): the three exits of the nearest opposing gap
    ahead of the entry - NWOG, today's / recent ORGs, HTF arrays - near edge, the quarter of its depth (the 75% mark of the
    gap measured from its far edge), then its CE. Side space, exit prices (exit_before applied)."""
    from .strategy import _nwogs
    zs = []
    for a, b in _nwogs(ctx, i):
        x1, x2 = sd.x(a), sd.x(b)
        zs.append((min(x1, x2), max(x1, x2)))
    orgs = ctx.org[:-1] if (ctx.org_today and ctx.t[i] < 570) else ctx.org
    for a, b in orgs[-max(p.org_days, 1):] if p.org_days else ():
        x1, x2 = sd.x(a), sd.x(b)
        zs.append((min(x1, x2), max(x1, x2)))
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        for near, ce, far, tf, _ in cf.opposing(now, sd.x(entry), sd.sign, tuple(p.htf_targets), (0, 2)):
            x1, x2 = sd.x(near), sd.x(far)
            zs.append((min(x1, x2), max(x1, x2)))
    zs = [z for z in zs if z[0] > entry and z[1] - z[0] > 1e-9]
    if not zs:
        return None
    near, far = min(zs)
    ex = p.exit_before_pts * p.es_pt
    return [near - ex, near + 0.25 * (far - near) - ex, (near + far) / 2 - ex]


# --- arming ----------------------------------------------------------------------------------------------------------

def _arm(ctx, sd, i, k0, p, tol, lock=None, session="AM", win_a=None, prior=(), win=None, ds=None, rev=None):
    """The newest order of _arm_all (the evolving pick) - the single-order entry point kept for the unit tests."""
    os_ = _arm_all(ctx, sd, i, k0, p, tol, lock, session, win_a, prior, win, ds, rev)
    return max(os_, key=lambda o: o["fvg_i"]) if os_ else None


def _arm_all(ctx, sd, i, k0, p, tol, lock=None, session="AM", win_a=None, prior=(), win=None, ds=None, rev=None) -> list:
    """Orders (dicts, side space) for the closed bar i: the qualifying FVG / IFVG / OB entries of the leg from bar k0.
    rev = dict(origin=, bottom=, since=) arms the ONE opposite Silver Bullet of gap 15 (needs the run's origin broken)."""
    from .strategy import _f, _idx_at
    from .setups import disp_ok_sb
    l, h, c, o = sd.l, sd.h, sd.c, sd.o
    if i <= k0 + 2:
        return []
    a_idx = _idx_at(ctx, win_a) if win_a is not None else k0
    ext_pts = 0.0                                      # M3.10: an immediate rebalance in the window
    if p.sb_rebalance_ext and win_a is not None:       # -> expect more than 5 handles
        if immediate_rebalance(sd, a_idx, i, 0.25 * p.es_pt):
            ext_pts = p.sb_rebalance_ext
    li = k0 + int(np.argmin(l[k0:i + 1]))             # the leg's extreme since the leg start
    if li >= i:
        return []
    # --- the trigger: MSS (a close or, mss_mode "wick", a wick beyond the swing that led into the extreme)
    need_mss = p.sb_mss_required and p.sb_need_mss
    refs = [q for q in sd.ph if q.i < li and q.known <= i]
    ref, kb = None, None
    if refs:
        ref = refs[-1].price
        brk = (h if p.mss_mode == "wick" else c)[li + 1:i + 1] > ref
        if brk.any():
            kb = li + 1 + int(np.flatnonzero(brk)[0])
    mss_fail = False                                   # no (valid) MSS: only the 5m order block entry (049) can still arm
    if kb is None and need_mss:
        if "ob" not in p.sb_entry_arrays:
            return []
        mss_fail = True
    if kb is not None and (p.disp_mult or p.disp_body_mult or p.disp_through_pts or p.disp_follow or p.mss_disp):
        ok, kb2 = disp_ok_sb(sd, li, i, ref, p)        # setups_models A20 / M0.4 "also in SB"
        if not ok:
            if need_mss:
                if "ob" not in p.sb_entry_arrays:
                    return []
                mss_fail = True
            kb = None
        else:
            kb = kb2
    if kb is not None and (p.sb_disp_pts or p.sb_disp_leg_pts or p.sb_disp_range_mult):
        # direction filter "displacement size": the breaking candle's body / range and the run from the low
        body, rg = float(c[kb] - o[kb]), float(h[kb] - l[kb])
        base = (h[max(0, li - 20):li] - l[max(0, li - 20):li])
        if (body < p.sb_disp_pts * p.es_pt or float(c[kb] - l[li]) < p.sb_disp_leg_pts * p.es_pt
                or (p.sb_disp_range_mult and len(base) and rg < p.sb_disp_range_mult * float(base.mean()))):
            _f("sb_x_disp_size")
            return []
    tags = []
    if kb is None:
        tags.append("sb_no_mss")
    # --- sweep (M3.5), discount-array stand-in (gap 5), premise (gap 13), NWOG reaction (gap 22), sync
    sw_name, sw_depth = "none", None
    if p.sb_need_sweep or p.sb_sweep_max_pts:
        sw_name, sw_depth = sweep_info(ctx, sd, li, i, p, session)
    deferred_alt = False
    if p.sb_need_sweep and sw_name == "none":
        if p.sb_sweep_alt == "discount_array":
            deferred_alt = True                        # decided with the entry FVG (condition 4 needs it)
        else:
            _f("sb_x_need_sweep")
            return []
    if p.sb_sweep_max_pts and sw_depth is not None and sw_depth > p.sb_sweep_max_pts:
        _f("sb_x_sweep_depth")
        return []
    if p.sb_premise:
        pm = _premise(ctx, sd, li, i, p, session)
        if not pm:
            _f("sb_x_premise")
            return []
        tags.append("sb_premise_" + pm)
    if p.sb_nwog_expansion:
        if _nwog_react(ctx, sd, li, i, p):
            tags.append("sb_nwog_expansion")
        elif p.sb_nwog_expansion == "require":
            _f("sb_x_nwog")
            return []
    if p.sb_sync != "off":
        ok, n_in, n_s = sync_state(ctx, sd, k0, li, i, p)
        if ok is False:
            if p.sb_sync == "require":
                _f("sb_x_sync")
                return []
            tags.append(f"sb_unsync_{n_in}of{n_s}")
        elif ok is None:
            tags.append("sb_sync_na")
        else:
            tags.append(f"sb_sync_{n_in}of{n_s}")
    # --- entry candidates
    k_fvg = k0
    if p.sb_fvg_in_window and win_a is not None:
        k_fvg = max(k_fvg, a_idx)
    if p.sb_fvg_from:
        k_fvg = max(k_fvg, _idx_at(ctx, p.sb_fvg_from))
    pick = p.sb_fvg_pick if p.sb_evolve else "first"
    cands = []
    gaps = []
    if "fvg" in p.sb_entry_arrays and not mss_fail:
        brk_lv = -np.inf if ref is None else ref
        sib_top = -np.inf
        bears = []
        if p.sb_bpr_exclude:                           # gap 6 (048 ~1:34:40)
            sib = L.leg_sibi(h, l, o, c, max(k0, 2), li, sd.c2_dir)
            sib_top = sib.top if sib is not None else -np.inf
            bears = [z for z in _bears(sd) if k0 <= z.i <= i]
        for g in sd.gaps:
            if not (li <= g.i - 2 and g.i <= i and g.i - 2 >= k_fvg):
                continue
            if ref is not None and kb is not None and not g.top > ref:
                continue                               # beyond the level that needed breaking (048 ~1:34:31)
            if p.disp_fvg_after_break and kb is not None and g.i < kb:
                continue                               # A20: the gap left by the break
            if not c[g.i + 1:i + 1].min(initial=np.inf) >= g.bottom:
                continue                               # still open
            if pick == "evolving":
                if not l[g.i + 1:i + 1].min(initial=np.inf) > g.top:
                    continue                           # not yet traded back in
            elif not c[i] > g.top:
                continue                               # first / any_in_leg: a retrace is still to come
            if p.sb_bpr_exclude:
                lvl = max(brk_lv, sib_top)
                if not (g.bottom > lvl and kb is not None and g.i >= kb) or any(z.overlaps(g) for z in bears):
                    continue
            gaps.append(g)
        box = cons_box(sd, a_idx, i, p) if p.sb_cons_wait else None
        if box is not None:                            # gap 21 (072 ~35:41): FVGs inside the range do not count
            top_b, bot_b, e_b, mb = box
            gaps = [g for g in gaps if g.i - 1 > e_b and c[g.i - 1] > top_b
                    and abs(c[g.i - 1] - o[g.i - 1]) >= p.sb_cons_body_mult * max(mb, 1e-12)]
        big = None
        if p.sb_lrc_mult:
            def big(g):                                # gap 18 (057 ~2:16): a large-range candle next to the gap
                k = g.i - 2
                prev = h[max(0, k - 20):k] - l[max(0, k - 20):k]
                return bool(len(prev) and (h[k] - l[k]) >= p.sb_lrc_mult * float(prev.mean()))
        first_g = gaps[0] if gaps else None
        for g in gaps:
            tg = []
            if big is not None and big(g):
                if p.sb_lrc_mode == "skip" or (p.sb_lrc_mode == "wait" and g is first_g):
                    continue
                tg.append("sb_lrc")
            cands.append(dict(kind="fvg", top=g.top, bottom=g.bottom, i=g.i, g=g, first_low=float(l[g.i - 2]), tags=tg))
    if (p.sb_ifvg or p.sb_ifvg_reaper) and not mss_fail:
        ifs = _ifvg_cands(ctx, sd, k0, li, i, p, kb)
        ifs = [x for x in ifs if x["i"] >= k_fvg]
        if p.sb_ifvg == "prefer" and ifs:
            cands = []
        cands += ifs
    if "ob" in p.sb_entry_arrays and win_a is not None and i >= a_idx - 1:
        want = ds.want if ds is not None else None
        ob_c = _ob_cand(ctx, sd, k0, a_idx, i, p, lock, want)
        if ob_c is not None:
            cands.append(ob_c)
    if not cands:
        return []
    cands.sort(key=lambda x: (x["i"], x["kind"] != "fvg", x["top"]))
    if pick == "any_in_leg":
        sel = cands
    elif pick == "first":
        sel = cands[:1]
    else:
        sel = cands[-1:]
    out = []
    for cd in sel:
        if deferred_alt and not _discount_array(ctx, sd, k0, li, kb, cd.get("g"), p):
            _f("sb_x_need_sweep")
            continue
        o_ = _order(ctx, sd, i, k0, li, kb, cd, p, tol, lock, session, ext_pts, a_idx, prior, ds,
                    tags + cd.get("tags", []), sw_name, sw_depth, gaps, rev)
        if o_ is not None:
            out.append(o_)
    return out


def _order(ctx, sd, i, k0, li, kb, cd, p, tol, lock, session, ext_pts, a_idx, prior, ds, tags, sw_name, sw_depth,
           gaps, rev=None):
    """One order for the entry candidate `cd` (side space) or None."""
    from .strategy import (_targets, _eq_levels, _first_units, CF_SRC, _thru, _tick, POOL_KINDS, _htf_tag, _f,
                           _lots, _lv_finish_targets)
    from . import entries as _EN
    from . import targets as _TP
    from .setups import Params_like
    l, h, c, o = sd.l, sd.h, sd.c, sd.o
    g, kind = cd.get("g"), cd["kind"]
    lvt = list(tags)
    conf = None
    from .entries import entry_px                      # E2 / D11: the SB's own entry price mode
    entry = entry_px(sd, g, cd["top"], cd["bottom"], p, p.sb_entry)
    if p.sb_use_bias and p.use_bias:                    # M3.3: use_bias (T2 / D22 PO3) - discount of the AM / PM reference open
        from .strategy import _open_known
        ref_open = _open_known(ctx, "1330" if session == "PM" else p.bias_open, i)
        if ref_open is None and session != "PM":
            ref_open = _open_known(ctx, "midnight", i)
        if ref_open is not None and not (entry <= sd.x(ref_open) + p.eq_tol_pts * p.es_pt if p.po3_inclusive
                                         else entry < sd.x(ref_open) + p.mo_tol_pts * p.es_pt):
            _f("sb_x_wrong_side_of_open")
            return None
    fi = g.i - 2 if g is not None else i
    ob = L.order_block_blend(o, h, l, c, li - 3, fi, "bull")
    mt_ob = None if (ob is None or ob.mt != ob.mt) else float(ob.mt if p.mt_mode == "body" else ob.mid)
    if "confluence" in p.sb_entry_arrays and g is not None:
        conf = _conf_levels(ctx, sd, k0, i, g, ob, p)
        if conf is not None:
            lvt.append("sb_conf")
            if p.sb_conf_mode == "entry":
                entry = min(entry, conf[0] if conf[2] is None else max(conf[0], conf[2]))   # support at or above the MT
                kind = "conf"
    pad = p.pad
    stop_at_fill = False
    if kind == "ob":
        stop = cd["bottom"] - pad
    elif p.sb_stop == "fvg2" and g is not None:        # 057 ~6:41: 2 pts beyond the entry (about the evolved FVG's far edge)
        stop = min(entry - p.sb_stop_pts * p.es_pt, g.bottom - pad)
    elif p.sb_stop == "swing":                          # gap 19 (092 ~55:30): beyond the candle / swing that ran into the array
        stop = float(l[li]) - pad
    elif p.sb_stop == "fvg_ce" and g is not None:      # 069 ~13:46: just beyond the CE of the deeper of two FVGs
        deep = [z for z in gaps[-2:] if z.i <= g.i] or [g]
        stop = min(z.mid for z in deep) - pad
    elif p.sb_stop == "entry_candle" or kind in ("ifvg", "ifvg_breaker"):
        if kind in ("ifvg", "ifvg_breaker") and p.sb_ifvg_stop == "breaker" and cd.get("bz") is not None:
            stop = float(cd["bz"].bottom) - pad       # beyond the breaker zone (076 / 092)
        else:                                          # 086 ~11:35 / 076: below the entry candle (recomputed at the fill)
            stop = float(l[max(i - 2, 0):i + 1].min()) - pad
            stop_at_fill = True
    else:                                              # 090 ~2:14:00: below the FVG's first candle and the OB mean threshold
        stop = float(cd["first_low"])
        if mt_ob is not None:
            stop = min(stop, mt_ob)
        stop -= pad
    lvx = {}                                           # the main engine's stop modifiers (E6d, E6f, A4 mohawk)
    stop = _EN.refine_stop(ctx, sd, dict(ext_i=li), i, p, entry, stop, {}, lvx, lvt)
    risk = entry - stop
    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt):
        return None
    wide_cut = 1.0
    if p.sb_max_stop_pts and risk > p.sb_max_stop_pts * p.es_pt + 1e-12:   # gap 19 (057 ~2:54; 092 ~55:30)
        if p.sb_wide == "skip":
            _f("sb_x_wide_stop")
            return None
        wide_cut = p.sb_max_stop_pts * p.es_pt / risk
        lvt.append("sb_wide_sized")
    # --- the draw list
    eq_hi = _eq_levels(sd, i, tol, lows=False, p=p)
    pq = p if (p.pool_prev_week or not p.sb_pw_pools) else Params_like(p, pool_prev_week=True)   # L14g (054 ~04:02)
    lv = list(_targets(ctx, sd, i, entry, eq_hi, pq, None, li))
    if p.sb_htf_targets:                               # L14g: the main scan's conf / fvg target sources
        cf = getattr(ctx, "conf", None)
        extra = []
        if cf is not None and p.htf_targets:
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            extra += [(sd.x(v), "array") for v in cf.targets(now, sd.x(entry), sd.sign, tuple(p.htf_targets), p.htf_far_edge)]
        if p.fvg_targets:
            for z in sd.opposing():
                if z.i <= i and z.bottom > entry and h[z.i + 1:i + 1].max(initial=-np.inf) < z.bottom:
                    extra += [(z.bottom, "array"), (z.mid, "array")]
        extra += _lv_finish_targets(ctx, sd, i, entry, p, tuple(p.htf_targets))
        lv = sorted(set(lv) | set(extra))
    if p.sb_ote_draw:
        lv = sorted(set(lv) | {(v, "array") for v in ote_levels(ctx, sd) if v > entry})
    if p.sb_htf_targets or p.sb_ote_draw:              # merge levels within ~1 ES point like _targets
        mg = []
        for v, k_ in sorted(lv):
            if not mg or v - mg[-1][0] > p.es_pt:
                mg.append((v, k_))
        lv = mg
    dr = [(v, k_) for v, k_ in lv if v > entry]
    if lock is not None and lock["side"] == sd.sign and lock["target"] is not None:   # #9 / M3.2: the locked draw is a draw
        tv_ = sd.x(lock["target"])                      # even when the target list (pw_pools, OTE, fallback, London) lacks it
        if tv_ > entry and not any(abs(v - tv_) <= 1e-9 for v, _ in dr):
            dr = sorted(dr + [(tv_, "pool" if lock["kind"] == "pool" else "array")])
    if p.sb_draw_pools_only:                           # A2 (033 ~24:34): an imbalance is not liquidity
        dr = [(v, k_) for v, k_ in dr if k_ in POOL_KINDS]
    scalp_fail = None
    if p.sb_room_untaken and dr:                       # gap 3 (058 ~54:20): no room past a pool already swept today
        full = _targets(ctx, sd, i, entry, eq_hi, pq, None, None)
        gone = [v for v, k_ in full if k_ in POOL_KINDS and v > entry and v not in {x for x, _ in dr}]
        if gone:
            cut = min(gone)
            dr2 = [(v, k_) for v, k_ in dr if v < cut]
            if not dr2 or dr2 != dr:
                scalp_fail = "sb_room_untaken"
            dr = dr2
    if p.sb_org_chop and ctx.org_today and ctx.org and i >= a_idx and ctx.t[i] >= 570:   # gap 3: consolidating inside today's ORG
        pc_, op_ = ctx.org[-1]
        lo_o, hi_o = sd.x(pc_), sd.x(op_)
        lo_o, hi_o = min(lo_o, hi_o), max(lo_o, hi_o)
        seg = c[max(a_idx - p.sb_org_chop_bars, 0):a_idx + 1]
        if len(seg) and (seg >= lo_o - 1e-12).all() and (seg <= hi_o + 1e-12).all():
            scalp_fail = scalp_fail or "sb_org_chop"
            dr = [] if p.sb_fail_mode == "skip" else dr
    if scalp_fail and p.sb_fail_mode == "skip":
        _f("sb_x_" + scalp_fail[3:])
        return None
    if not dr:
        return None
    capped = False
    bm = []
    fracs424 = None
    raw_first, kind_first = dr[0]
    if scalp_fail:                                     # gap 3 (c): half size to the nearer untaken pool
        pools = [(v, k_) for v, k_ in dr if k_ in POOL_KINDS]
        if not pools:
            return None
        raw_first, kind_first = pools[0]
        t1 = raw_first + (p.pool_beyond_pts * p.es_pt if p.exit_mode == "split" else -p.exit_before_pts * p.es_pt)
        if t1 - entry < p.min_rr * risk * max(p.sb_min_rr, 1.0) or t1 - entry <= 0:
            return None
        t2, levels = None, [t1]
        lvt.append("sb_scalp")
        scalp_sb = True
    elif p.sb_simple:                                  # gap 20 (069 ~15:05): EQ of the leg, the first array beyond it, one exit
        hi_l, lo_l = float(h[k0:li + 1].max()), float(l[li])
        eq = (hi_l + lo_l) / 2
        if not entry <= eq + 1e-12:
            _f("sb_x_simple_premium")
            return None
        arr = [(v, k_) for v, k_ in dr if v > eq and k_ not in POOL_KINDS]
        if not arr:
            return None
        raw_first, kind_first = arr[0]
        t1 = raw_first - p.exit_before_pts * p.es_pt
        if t1 - entry < p.sb_room_pts * p.es_pt or t1 - entry < p.min_rr * risk * p.sb_min_rr:
            return None
        t2, levels = None, [t1]
        lvt.append("sb_simple")
        scalp_sb = True
    elif kind == "ob":                                 # 049: cover at the next short-term high beyond the entry
        piv = sorted(q.price for q in sd.ph if q.known <= i and q.price > entry + p.sb_ob_min_pts * p.es_pt)
        t1 = (piv[0] if piv else dr[0][0]) - p.exit_before_pts * p.es_pt
        if t1 - entry < p.sb_ob_min_pts * p.es_pt:
            return None
        t2, levels, raw_first, kind_first = None, [t1], t1, "array"
        lvt.append("sb_ob")
        scalp_sb = True
    elif p.sb_target_mode == "fixed":                  # the old list: +sb_target_pts first
        draws = [v for v, k_ in dr]
        draw = draws[0]
        room = draw - entry + (p.sb_room_overshoot_pts * p.es_pt if dr[0][1] in POOL_KINDS else 0.0)
        if room < max(p.sb_room_pts, ext_pts) * p.es_pt:
            return None                                # not enough room (the 10 / 5 framework)
        t1 = min(entry + max(p.sb_target_pts, ext_pts) * p.es_pt, draw - p.exit_before_pts * p.es_pt)
        if t1 - entry < p.min_rr * risk * p.sb_min_rr:
            return None
        t2 = draw if p.sb_runner and draw > t1 + p.es_pt else None
        levels = [t1] + [v for v in draws if v > t1 + p.es_pt][:2]
        scalp_sb = False
    else:                                              # owner #2: exit AT the draw levels
        ex = lambda v, k_: v + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and k_ in POOL_KINDS) \
            else v - p.exit_before_pts * p.es_pt
        pairs = sorted((ex(v, k_), v, k_) for v, k_ in dr)
        if lock is not None:                           # #9: only toward the locked draw, out at it
            tv = sd.x(lock["target"])
            T = tv + p.pool_beyond_pts * p.es_pt if (p.exit_mode == "split" and lock["kind"] == "pool") \
                else tv - p.exit_before_pts * p.es_pt
            pairs = [x for x in pairs if x[0] < T - p.es_pt] + [(T, tv, lock["kind"])]
        draws = [x[0] for x in pairs]
        rawmap = {x[0]: (x[1], x[2]) for x in pairs}
        cap_tfs, bump_tfs = _TP.resist_cfg(p)             # owner #7 REVISED: cap tfs / speed-bump tfs
        if cap_tfs and getattr(ctx, "conf", None) is not None:   # #7 cap
            now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
            r = ctx.conf.resistance(now, sd.x(entry), sd.sign, cap_tfs,
                                    tuple(CF_SRC[x] for x in p.htf_resist_src))
            if r is not None:
                capx = sd.x(r[0]) - p.htf_resist_buffer_pts * p.es_pt
                draws = [d for d in draws if d <= capx] or [capx]   # exit before the cap
                capped = True
                if capx - entry < max(p.min_rr * risk, p.sb_room_pts * p.es_pt):
                    return None
        if bump_tfs and getattr(ctx, "conf", None) is not None:      # #7 REVISED: a partial at the opposing HTF FVG
            bm = _TP.bump_levels(ctx, sd, i, p, entry, risk, bump_tfs, tuple(CF_SRC[x] for x in p.htf_resist_src), None)
            last_ = max(draws) if draws else None
            bm = [b for b in bm if last_ is not None and entry + p.sb_room_pts * p.es_pt <= b < last_ - p.es_pt]
            if bm:
                draws = sorted(set(draws) | set(bm))
                lvt.append("speed_bump")
        draws = [d for d in draws if d > entry + ext_pts * p.es_pt - 1e-9]   # M3.10: the extended draw
        if not draws:
            return None
        t1 = draws[0]
        raw_first, kind_first = rawmap.get(t1, (t1, "array"))
        ref_px = raw_first if p.sb_room_mode == "draw" else t1               # L15: room to the exit price or the raw draw
        room = ref_px - entry + (p.sb_room_overshoot_pts * p.es_pt if kind_first in POOL_KINDS else 0.0)   # gap 2 (059)
        if room < p.sb_room_pts * p.es_pt:
            return None                                # minimum room to the draw
        if t1 - entry < p.min_rr * risk * p.sb_min_rr:
            return None
        t2 = (draws[-1] if lock is not None else draws[1]) if (p.sb_runner and len(draws) > 1) else None
        nl_ = len(p.ladder_fracs) + len([b for b in bm if b in draws])      # a speed bump is an extra small rung
        levels = draws[:nl_] if lock is None else (
            draws[:nl_ - 1] + [draws[-1]] if len(draws) > nl_ else draws)
        scalp_sb = False
        if p.sb_mgmt in ("gap424", "layered057"):      # M3.11 (057): 4 / 2 / 4 at the NWOG high / 75% / CE
            g4 = _gap424(ctx, sd, i, entry, p)
            if g4 and g4[0] - entry >= p.sb_room_pts * p.es_pt and g4[0] - entry >= p.min_rr * risk * p.sb_min_rr:
                levels, t1, t2 = g4, g4[0], None
                fracs424 = tuple(p.sb_gap424_fracs)
                bm = []
                lvt.append("sb_gap424")
    # --- M3.11 / gap 8: the runner conditions (the weekly profile and the supercharge)
    sup = False
    if not scalp_sb:
        wk = ds.week if ds is not None else None
        aligned = wk is not None and wk["side"] == sd.sign
        if p.sb_runner_if_weekly and t2 is not None and not aligned:
            t2 = None                                  # the runner only with the weekly profile aligned (048 ~2:02:12)
            lvt.append("sb_no_runner")
        if p.sb_supercharge:
            early = wk is not None and wk.get("early_up" if sd.sign > 0 else "early_dn", 0)
            if early and aligned and not (ds.ranging if ds is not None else True):
                sup = True
                if t2 is None:                         # the HTF draw: the locked target, else the farthest draw
                    far = lock["target"] if (lock is not None and lock["side"] == sd.sign) else None
                    t2 = (sd.x(far) if far is not None else (levels[-1] if levels else t1))
                    if t2 <= t1 + p.es_pt:
                        t2 = None
                        sup = False
                if sup:
                    lvt.append("sb_supercharge")
            else:
                t2 = None                              # not supercharged: the full exit at the SB target (gap 8)
    chop = getattr(ctx, "chop", None)                # #10: sloppy reasons known at this close
    sl_set = {r for r in getattr(ctx, "sl_day", ()) if session == "PM" or not r.endswith(":PM")}
    if chop is not None and chop.active_before(i + 1):
        sl_set.add("chop")
    sl, scalp = "|".join(sorted(sl_set)), scalp_sb
    if p.sloppy_mode == "scalp" and sl_set:
        t1 = min(entry + p.sloppy_scalp_pts * p.es_pt, t1)   # scalp: one exit, no runner
        t2, levels, scalp = None, [t1], True
    rm = _EN.extras_risk_mult(ctx, p, ctx.idx[i], prior)      # E10 loss_halving / Ep08.12 after_loss_mult
    sw_ = dict(ext=float(l[li]), ext_i=li)
    rm *= _EN.size_mult(ctx, sd, sw_, i, p, session, entry, _htf_tag(ctx, sd, i, sw_["ext"], tol), sl, lvt)   # E9
    xcap = p.size_up_cap_pct * ctx.equity if (p.size_up_cap_pct and any(x.startswith("size_up_") for x in lvt)) else 0.0
    if scalp_fail:
        rm *= 0.5                                      # gap 3: half size
    shares = _EN.cap_initial(_first_units(p, ctx.equity, risk, entry, rm, xcap), p)    # E11
    if wide_cut < 1.0:
        shares = _lots(shares * wide_cut, p.lot)
    if shares < 1:
        return None
    lo_seg = l[k0:li + 1].min()
    swept = "none"
    for name, v in ctx.pd.items():                      # tag a sweep of a prior level
        if ctx.t[i] < 570 and name.startswith("pm"):
            continue                                    # (the overnight range is not complete before 09:30)
        lv_ = sd.x(v)
        if name.startswith(("pdl", "pml")) and sd.sign > 0 and _thru(lo_seg, lv_, _tick(p)):   # A2 tick
            swept = name
        if name.startswith(("pdh", "pmh")) and sd.sign < 0 and _thru(lo_seg, lv_, _tick(p)):
            swept = name
    if sw_name != "none" and swept == "none":
        swept = sw_name
    if sw_depth is None:
        sw_depth = None if (swept == "none" and not (p.sb_need_sweep or p.sb_sweep_max_pts)) else sweep_info(ctx, sd, li, i, p, session)[1]
    if p.sb_sweep_alt and p.sb_need_sweep and swept == "none":
        swept = "discount_array"
    if conf is not None and p.sb_conf_mode in ("tag", "entry") and conf[2] is not None:
        lvx["sb_conf_mt"] = (float(conf[2]), False)    # gap 10: a 1m close below the MT ends the idea (wicks allowed)
    ek = {"fvg": "fvg", "ifvg": "ifvg", "ifvg_breaker": "ifvg_breaker", "ob": "ob", "conf": "conf"}[kind]
    if kind == "fvg" and conf is not None:
        ek = "fvg"
    return dict(side=sd, i=i, fvg_i=cd["i"], entry=entry, stop=stop, t1=t1, t2=t2, shares=shares,
                swept=swept, levels=levels, capped=capped, scalp=scalp, sloppy=sl,
                lv_tags="|".join(dict.fromkeys(lvt)), lvx=lvx,
                draw_side=0 if lock is None else lock["side"],
                draw_px=None if lock is None else lock["target"],
                draw_name="" if lock is None else lock["name"],
                draw_kind="" if lock is None else lock["kind"], bumps=bm,
                kind=ek, zone=(cd["top"], cd["bottom"]), draw_raw=raw_first, draw_raw_kind=kind_first,
                stop_at_fill=stop_at_fill, rm=rm, xcap=xcap, sweep_depth=sw_depth, li=li, kb=kb, super=sup,
                fracs424=fracs424, wide_cut=wide_cut, market=bool(kind in ("ifvg", "ifvg_breaker") and p.sb_ifvg_market),
                cancel_below=(float(conf[2]) if (conf is not None and conf[2] is not None) else None),
                rev=rev is not None, imm=False)



# --- the locked draw of a window -------------------------------------------------------------------------------------

def _first_lock(ctx, p, win, ds):
    """M3.2 (054 ~04:02-06:50): mark up the 054 draw list and lock ONE draw before the window (at the leg start): PDH/PDL,
    the previous session H/L (London / prior PM for the AM; the AM and lunch for the PM), PWH/PWL (sb_pw_pools), NWOG /
    ORG arrays, the HTF table draws (mark_levels), plus the classic OTE (sb_ote_draw); with sb_htf_fallback, when every
    draw was raided (neutral), an HTF pool or array. The nearest draw >= draw_lock_min_pts away sets the side (owner #9)."""
    from .strategy import mark_levels, _spent_up, _thru, _tick, _idx_at
    from .setups import Params_like
    pq = p if (p.pool_prev_week or not p.sb_pw_pools) else Params_like(p, pool_prev_week=True)
    t_lock = win.leg_from
    row = getattr(ctx, "bias_by_cut", {}).get(t_lock)
    if row is None and t_lock >= 570:
        row = getattr(ctx, "bias_row", None)
    lock = mark_levels(ctx, row, t_lock, win.session, pq, ())
    S = ctx.start
    kl = S + int(np.searchsorted(ctx.t[S:] + ctx.tf, t_lock, side="right"))
    px, tk = lock["px"], _tick(p)
    mn = p.draw_lock_min_pts * p.es_pt
    marked = list(lock["marked"])
    have = {(round(v, 9), k) for v, k, *_ in marked}

    def intact(v, created):
        a = max(created, S)
        if a >= kl:
            return True
        return (not _spent_up(ctx.h[a:kl].max(), v, tk)) if v > px else (not _thru(ctx.l[a:kl].min(), v, tk))

    extra = []
    if win.name == "am":                                   # the previous session H/L: London and the prior PM
        for nm in ("london", "prev_pm"):
            if nm in ctx.sess:
                hi, lo, ready = ctx.sess[nm]
                extra += [(hi, "pool", nm + "_high", 1, _idx_at(ctx, ready) if ready else S),
                          (lo, "pool", nm + "_low", -1, _idx_at(ctx, ready) if ready else S)]
    if p.sb_ote_draw:
        for v in ote_levels(ctx, _Real):
            extra.append((v, "array", "ote", 0, S))
    for v, k, n, dr, cr in extra:
        if v == px or (v > px and dr < 0) or (v < px and dr > 0) or (round(v, 9), k) in have:
            continue
        if intact(v, cr):
            marked.append((v, k, n, dr))
            have.add((round(v, 9), k))
    if p.sb_htf_fallback and not any(abs(v - px) >= mn for v, *_ in marked):
        cf = getattr(ctx, "conf", None)
        now = pd.Timestamp(ctx.day, tz=ctx.idx.tz) + pd.Timedelta(minutes=t_lock)
        fb = []
        if ctx.pw is not None:
            fb += [(ctx.pw[0], "pool", "pwh", 1, S), (ctx.pw[1], "pool", "pwl", -1, S)]
        if ctx.pm_ is not None:
            fb += [(ctx.pm_[0], "pool", "pmonth_h", 1, S), (ctx.pm_[1], "pool", "pmonth_l", -1, S)]
        if cf is not None:
            for sgn in (1, -1):
                r = cf.opposing(now, px, sgn, ("1h", "4h", "D", "W"), (0,))
                if r:
                    fb.append((r[0][0], "array", "htf_fb", 0, S))
        for v, k, n, dr, cr in fb:
            if (v > px and dr < 0) or (v < px and dr > 0) or (round(v, 9), k) in have:
                continue
            if intact(v, cr):
                marked.append((v, k, n, dr))
                have.add((round(v, 9), k))
    marked.sort(key=lambda m: abs(m[0] - px))
    up = [m for m in marked if m[0] > px and abs(m[0] - px) >= mn]
    dn = [m for m in marked if m[0] < px and abs(m[0] - px) >= mn]
    side = 0
    if up and (not dn or up[0][0] - px < px - dn[0][0]):
        side = 1
    elif dn and (not up or px - dn[0][0] < up[0][0] - px):
        side = -1
    pick = (up if side > 0 else dn)[0] if side else None
    lock.update(side=side, target=pick[0] if pick else None, kind=pick[1] if pick else "",
                name=pick[2] if pick else "", marked=marked)
    return lock


class _RealSide:
    """sign +1 view: ote_levels() on real prices."""
    sign = 1

    @staticmethod
    def x(v):
        return v


_Real = _RealSide()


def _day_state(ctx, p, day) -> SimpleNamespace:
    """Per-day reads shared by the windows (all from data known before the first window)."""
    ds = SimpleNamespace(want=None, day_side=0, delivered=False, spot={}, week=None, ranging=True)
    if p.sb_weekly != "off" or p.sb_runner_if_weekly or p.sb_supercharge:
        ds.week = weekly_profile(ctx, p, day)
    return ds


def _hit_target(tr, before=None) -> bool:
    """The trade reached a target rung (t1, t2, ...), not just a stop / exit; `before` (a timestamp) = by then."""
    import re
    return any(re.fullmatch(r"t\d+", e[3]) and (before is None or e[0] < before) for e in tr.exits)


def _moc_ok(ctx, out, a_idx: int) -> bool:
    """Gap 14 (056 ~15:00 "the final market on close macro"): the extra 15:15-15:45 entry only while the PM draw is
    not delivered (before the window opens) and no PM Silver Bullet has hit its target (by then)."""
    pm = getattr(ctx, "lock", {}).get("PM")
    if pm is not None and pm.get("delivered_i") is not None and pm["delivered_i"] < a_idx:
        return False
    t0 = ctx.idx[a_idx] if a_idx < len(ctx.idx) else None
    return not any(t.setup in ("sb_pm", "sb_lh") and _hit_target(t, t0) for t in out)


def _entered_before(ctx, out, a_idx: int, setups=None) -> bool:
    """A Silver Bullet (of `setups`) was filled before the bar `a_idx` - what a later window may know."""
    t0 = ctx.idx[a_idx] if a_idx < len(ctx.idx) else None
    return any((setups is None or t.setup in setups) and (t0 is None or t.entry_time < t0) for t in out)


# --- the window loop -------------------------------------------------------------------------------------------------

def run_sb(ctx, sides, p, day, symbol, blocked, btag: dict) -> list:
    from .strategy import _news_gate, _eff_flat, _idx_at
    out = []
    ds = _day_state(ctx, p, day)
    stand = p.sloppy_mode == "stand_aside"
    for win in windows(p):
        if p.day_filter and blocked(day, win.session, p, win.a):
            continue
        if stand and win.session == "PM" and "nfp_week:PM" in getattr(ctx, "sl_day", ()):
            continue                                  # #10 stand aside (off by default)
        if p.sb_one_per_day and _entered_before(ctx, out, _idx_at(ctx, win.a)):
            continue                                  # M3 / 047 ~08:00: one Silver Bullet a day
        if p.sb_cascade and win.classic and _entered_before(ctx, out, _idx_at(ctx, win.a), ("sb_london", "sb_am", "sb_pm")):
            continue                                  # M3.9 / 054 ~18:01: London, else AM, else PM
        if win.name == "moc" and not _moc_ok(ctx, out, _idx_at(ctx, win.a)):
            continue
        drv = _news_gate(ctx, p, win.a, win.b)        # #4: wait for the news dealing range
        made = 0
        if drv is not None:
            if drv["made"] is None:
                continue
            made = drv["made"]
        _run_window(ctx, sides, p, day, symbol, btag, win, ds, out, made, _eff_flat(p))
    return out


def _window_lock(ctx, p, win, ds):
    """(lock, lazy_key): lock is None (no draw lock), a dict, or "lazy" (marked at the leg start inside the loop);
    lock False = skip the window."""
    if p.sb_draw_first:
        return "lazy", "SB_" + win.name                # M3.2: its own pre-window lock
    if p.draw_lock != "session":
        return None, None
    if win.name == "london":                           # [our interpretation; OWNER TO CONFIRM] London
        return "lazy", "LON"                           # precedes every session lock: its own lock at
    if win.name == "0700":                             # 02:00 (the leg start), with the htf table cut there
        return "lazy", "SB7"
    key = "LH" if win.name in ("lh", "moc") and "LH" in ctx.lock else win.session
    lock = getattr(ctx, "lock", {}).get(key)
    if lock is None:
        return False, None
    if lock["side"] == 0 and p.draw_lock_neutral == "skip":
        return False, None
    return lock, None


def _run_window(ctx, sides, p, day, symbol, btag, win, ds, out, made, flat):
    from .strategy import (Trade, _lots, news, day_type, _stamp_frame, mark_levels, _split, _f, _idx_at, POOL_KINDS)
    from . import entries as _EN
    tol = p.eq_tol_pts * p.es_pt
    chop = getattr(ctx, "chop", None)
    stand = p.sloppy_mode == "stand_aside"
    session, setup, a, b, leg_from = win.session, win.setup, win.a, win.b, win.leg_from
    lock, lazy_key = _window_lock(ctx, p, win, ds)
    if lock is False:
        return
    flat_w = win.flat if win.flat else flat
    idx = [k for k in range(ctx.start, len(ctx.t)) if leg_from <= ctx.t[k] < flat_w]
    if not idx:
        return
    k0 = idx[0]
    a_idx = _idx_at(ctx, a)
    row_w = window_row(ctx, win)                      # the window's own bias row (no overnight look-ahead before 09:30)
    ds.want = want_side(ctx, p, row_w)
    if p.sb_supercharge:
        ds.ranging = daily_ranging(ctx, p, row_w)
    if isinstance(lock, dict) and p.sb_day_dir == "lock" and ds.day_side == 0 and lock["side"]:
        ds.day_side = lock["side"]
    pend: dict = {}
    dead_draws: set = set()                           # M3.5 / 057 ~3:35: a cancelled draw stays cancelled (sb_cancel_sticky)
    pos = None
    n_done = 0
    rev_state = None
    rev_used = False
    spot_tag = ""
    tk_sb = 0.25 * p.es_pt
    for i in idx:
        t = ctx.t[i]
        ts = ctx.idx[i]
        if lock == "lazy" and t >= leg_from:          # locked before the leg it trades from
            if p.sb_draw_first:
                lock = _first_lock(ctx, p, win, ds)
            else:
                lock = mark_levels(ctx, getattr(ctx, "bias_by_cut", {}).get(leg_from), leg_from,
                                   "LON" if win.name == "london" else "AM", p, ())
            lock["window"] = win.name
            ctx.lock[lazy_key] = lock
            if p.sb_day_dir == "lock" and ds.day_side == 0 and lock["side"]:
                ds.day_side = lock["side"]
            if lock["side"] == 0 and p.draw_lock_neutral == "skip":
                break
        delivered_now = False                         # #9: the own lock's delivery (the AM / PM ones: run_day)
        if lazy_key and isinstance(lock, dict) and lock["side"] and not lock["delivered"]:
            if (ctx.h[i] >= lock["target"]) if lock["side"] > 0 else (ctx.l[i] <= lock["target"]):
                lock.update(delivered=True, delivered_t=ts, delivered_i=i)
                delivered_now = True
        if isinstance(lock, dict) and lock.get("delivered_i") is not None and lock["delivered_i"] <= i:
            ds.delivered = True                       # (the run_day locks carry the whole day's flag: only bars up to i)
        if pos is not None:                           # manage the open trade
            sd = pos["side"]
            o, h, l, c = sd.o[i], sd.h[i], sd.l[i], sd.c[i]
            tr = pos["trade"]
            _manage(ctx, p, win, pos, tr, sd, i, t, ts, o, h, l, c, flat_w, session)
            if pos["left"] and p.sb_adds and not pos["t1_done"]:
                _sb_adds(ctx, p, pos, tr, sd, i, ts, o, l, c)
            if pos["left"] and ctx.equity:
                r_now = max(0.0, (pos["entry"] - pos["stop"]) * pos["left"]) / ctx.equity
                tr.peak_risk_pct = round(max(tr.peak_risk_pct or 0.0, r_now), 5)
            if not pos["left"]:
                out.append(tr)
                n_done += 1
                hit = _hit_target(tr)
                was_rev = bool(pos.get("rev"))
                if hit:
                    ds.delivered = True
                if p.sb_reverse_after_target and hit and not rev_used and rev_state is None \
                        and not pos.get("rev") and pos["draw_raw_kind"] not in POOL_KINDS:
                    rev_state = dict(sd1=sd, origin1=float(sd.l[pos["li"]]), bottom1=float(pos["zone"][1]),
                                     since=pos["fill_i"], k0=pos["li"], sign=-sd.sign)
                pos = None
                pend = {}
                if rev_state is not None and not rev_used:
                    continue
                if hit or was_rev or n_done >= win.max_n:
                    break                              # one Silver Bullet per window (sb_max_per_window); target traded
                continue
            continue
        chopped = stand and chop is not None and chop.active_before(i)
        if pend and (chopped or i < made):
            pend = {}
        if pend and session == "AM" and p.am_exit and p.am_exit_extras and t + ctx.tf >= p.am_exit:
            pend = {}                                 # #8 guard
        if pend:                                      # working limit orders
            filled = None
            for key in list(pend):
                o_ = pend[key]
                sd = o_["side"]
                o_["maxh"] = max(o_.get("maxh", -np.inf), float(sd.h[i]))
                if t >= b:
                    del pend[key]                     # window over: cancel
                    continue
                if t < a and sd.l[i] < o_["entry"] and not o_["market"]:
                    del pend[key]                     # traded into before the window: not valid
                    continue
                if o_["cancel_below"] is not None and i - 1 >= o_["i"] and sd.c[i - 1] < o_["cancel_below"]:
                    del pend[key]                     # gap 10: a close below the MT cancels the confluence idea
                    continue
                if p.sb_cancel_ticks:                 # gap 17 (057 ~4:18): a 1-2 tick run beyond the draw is wanted
                    gone = sd.h[i] >= o_["draw_raw"] + p.sb_cancel_ticks * tk_sb and sd.l[i] >= o_["entry"]
                else:
                    gone = sd.h[i] >= o_["t1"] and sd.l[i] >= o_["entry"]
                if gone and not o_["market"]:
                    del pend[key]                     # target traded before the fill
                    dead_draws.add((sd.sign, round(float(o_["draw_raw"]), 6)))
                    continue
                ft_ = p.fill_through * p.tick         # E3: ticks the limit must print through to fill
                if o_["market"]:                      # 076: a down-close candle trades into the IFVG -> buy the next open
                    if i - 1 >= o_["i"]:
                        pb = i - 1
                        if sd.c[pb] < o_["zone"][1]:
                            del pend[key]         # a close through the IFVG: it failed
                            continue
                        if sd.c[pb] < sd.o[pb] and sd.l[pb] <= o_["zone"][0] and a <= t < b:
                            filled = (key, sd.o[i], o_)
                            break
                    continue
                if a <= t < b and (sd.l[i] <= o_["entry"] - ft_ + 1e-12 if ft_ else sd.l[i] < o_["entry"]):
                    cand = (key, min(o_["entry"], sd.o[i]), o_)
                    if filled is None or cand[1] > filled[1]:
                        filled = cand                 # several limits (any_in_leg): the nearest hit first
            if filled is not None:
                key, fill, o_ = filled
                sd = o_["side"]
                stop, shares = o_["stop"], o_["shares"]
                if o_["stop_at_fill"] or o_["market"]:   # 086 ~11:35 / 076: below the entry candle; size at the real fill
                    if o_["stop_at_fill"]:               # the entry candle: the fill bar, or the signal bar of a market buy
                        stop = float(sd.l[i - 1 if o_["market"] else i]) - p.pad
                    risk = fill - stop
                    if not (p.min_risk_pts * p.es_pt <= risk <= p.max_risk_pts * p.es_pt) or fill >= o_["t1"]:
                        del pend[key]
                        continue
                    shares = _EN.cap_initial(_first_units_sb(p, ctx.equity, risk, fill, o_), p)
                    if o_["wide_cut"] < 1.0:
                        shares = _lots(shares * o_["wide_cut"], p.lot)
                    if shares < 1:
                        del pend[key]
                        continue
                n_ = n_done + 1
                tags = o_["lv_tags"]
                tr = Trade(day, symbol, session, setup, "long" if sd.sign > 0 else "short",
                           o_["swept"], False, None, ctx.idx[o_["i"]], ts, sd.x(fill), sd.x(stop),
                           sd.x(o_["t1"]), None if o_["t2"] is None else sd.x(o_["t2"]), shares,
                           day_type=day_type(day), news=news(day), sb=True, weekday=day.weekday(),
                           lv_tags="|".join(x for x in (tags, spot_tag, "sb_reverse" if o_["rev"] else "") if x),
                           capped=o_["capped"], draw_side=o_["draw_side"], draw_px=o_["draw_px"],
                           draw_name=o_["draw_name"], draw_kind=o_["draw_kind"], sloppy=o_["sloppy"],
                           entry_kind=o_["kind"], sb_win=win.name, sb_n=n_, sb_sweep_depth=o_["sweep_depth"],
                           sb_pre_run_ticks=(round(max(o_["maxh"] - o_["draw_raw"], 0.0) / tk_sb, 2)
                                             if p.sb_cancel_ticks else None),
                           imm_rebal=bool(p.sb_imm_tag and immediate_rebalance(sd, a_idx, i, tk_sb)),
                           **btag)
                tr.entry_risk_pct = tr.peak_risk_pct = (round(shares * (fill - stop) / ctx.equity, 5)
                                                        if ctx.equity else None)
                _stamp_frame(ctx, tr, i)
                if o_["fracs424"]:
                    fracs = tuple(o_["fracs424"])
                elif o_["scalp"]:
                    fracs = (1.0,)
                else:
                    fracs = _bump_fr(o_, p, _split(p, ctx, getattr(ctx, "hist", []), day, i, t) if p.sb_split else p.ladder_fracs)
                pos = dict(trade=tr, side=sd, stop=stop, t1=o_["t1"], t2=o_["t2"], left=shares, entry=fill,
                           t1_done=False, n=shares, levels=o_["levels"], k=0, away=None, fill_i=i,
                           lvx=o_.get("lvx") or {}, fracs=fracs, zone=o_["zone"], li=o_["li"], rev=o_["rev"],
                           super=o_["super"], draw_raw_kind=o_["draw_raw_kind"], n0=shares, moved=False,
                           add_pend=None, adds_done=0)
                pend = {}
                if o_["rev"]:
                    rev_used, rev_state = True, None       # gap 15: ONE opposite Silver Bullet per window
                if p.sb_day_dir == "first_trade" and ds.day_side == 0:
                    ds.day_side = sd.sign
                if sd.l[i] <= pos["stop"]:
                    tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "stop")); pos["left"] = 0
                    out.append(tr)
                    pos = None
                    n_done += 1
                    if n_done >= win.max_n:
                        break
                    continue
                continue
        if delivered_now:
            pend = {}                                 # #9: delivered on this bar's close - done
        if t >= b:
            if not pend:
                break
            continue
        if i < made or chopped:
            continue
        lk = lock if isinstance(lock, dict) else None
        if lk is not None and lk.get("delivered_i") is not None and i >= lk["delivered_i"] and rev_state is None:
            continue                                  # #9: the session's draw is delivered
        if rev_state is not None:
            lk = None                                 # gap 15: the counter-draw trade ignores the lock's side
        if p.sb_spotty != "off":
            if i < a_idx - 1:
                continue                              # the spotty read needs the bars before the window
            if "r" not in ds.spot.get(win.name, ""):
                bad, why = spotty_day(ctx, p, win, a_idx, k0, ctx.tf)
                ds.spot[win.name] = "r" + ("S:" + "+".join(why) if bad else "")
                if bad:
                    _f("sb_x_spotty")
            st_ = ds.spot[win.name]
            if len(st_) > 1:
                if p.sb_spotty == "skip":
                    break
                spot_tag = "sb_spotty_" + st_[3:]
        # (re)arm on the closed bar: newest qualifying FVG (evolving SB) / the first / every one in the leg
        cand = []
        for sd in sides:
            if rev_state is not None and sd.sign != rev_state["sign"]:
                continue
            if sd.sign in getattr(ctx, "block_side", {}).get("year_end", ()):
                continue
            if lk is not None and lk["side"] and sd.sign != lk["side"]:
                continue
            if (ds.day_side and sd.sign != ds.day_side and rev_state is None
                    and not (p.sb_day_dir_delivered == "free" and ds.delivered)):
                continue                              # one direction per day (gap 15's counter trade is the exception)
            if p.sb_use_bias:                         # M3.3: the engine's bias filters
                if (ds.want and ds.want != sd.sign) or (p.weekly_bias and ctx.wbias == -sd.sign):
                    continue
            wk_tag = ""
            if p.sb_weekly != "off" and ds.week is not None:
                ws = ds.week["side"]
                if ws and ws != sd.sign and p.sb_weekly == "require" or (not ws and p.sb_weekly == "require"
                                                                          and p.sb_weekly_neutral == "skip"):
                    continue
                wk_tag = "sb_wk_aligned" if ws == sd.sign else ("sb_wk_neutral" if not ws else "sb_wk_against")
            rv = None
            if rev_state is not None:
                rv = dict(origin=rev_state["origin1"], since=rev_state["since"])
                if not (rev_state["sd1"].c[rev_state["since"]:i + 1].min(initial=np.inf) < rev_state["origin1"]
                        and rev_state["sd1"].c[rev_state["since"]:i + 1].min(initial=np.inf) < rev_state["bottom1"]):
                    continue                          # no MSS beyond the first run's origin (and its FVG) yet
            kk0 = rev_state["k0"] if rev_state is not None else k0
            lk_sd = lk if (lk is not None and lk["side"] == sd.sign) else None
            os_ = _arm_all(ctx, sd, i, kk0, p, tol, lk_sd, session, a, out, win, ds, None)
            if p.sb_cancel_sticky and dead_draws:
                os_ = [x for x in os_ if (sd.sign, round(float(x["draw_raw"]), 6)) not in dead_draws]
            for o_ in os_:
                if wk_tag:
                    o_["lv_tags"] = "|".join(x for x in (o_["lv_tags"], wk_tag) if x)
                if rv is not None:
                    o_["rev"] = True
                cand.append(o_)
        if cand:
            mode = p.sb_fvg_pick if p.sb_evolve else "first"
            if mode == "any_in_leg":
                for o_ in cand:
                    key = (o_["side"].sign, o_["kind"], o_["fvg_i"])
                    if key not in pend:
                        pend[key] = o_
            else:
                best = max(cand, key=lambda x: x["fvg_i"]) if mode == "evolving" else min(cand, key=lambda x: x["fvg_i"])
                key = (best["side"].sign, best["kind"], best["fvg_i"])
                if mode == "evolving":
                    if not pend or key not in pend:
                        pend = {key: best}            # evolving: the limit moves to the newest FVG
                elif not pend:
                    pend = {key: best}                # first: the oldest, never moved
    if pos is not None:                               # data ended
        out.append(pos["trade"])
    elif not out or out[-1].setup != setup:
        if p.sb_imm_tag and any(immediate_rebalance(sd, a_idx, len(ctx.t) - 1, tk_sb) for sd in sides if sd.sign > 0):
            _f("sb_runaway")                          # gap 7 (048 ~1:31): an immediate rebalance, no SB fill


def _first_units_sb(p, eq, risk, entry, o_):
    from .strategy import _first_units
    return _first_units(p, eq, risk, entry, o_["rm"], o_["xcap"])


def _manage(ctx, p, win, pos, tr, sd, i, t, ts, o, h, l, c, flat_w, session):
    """One bar of the open trade (side space): stops, targets (fixed / ladder / 4-2-4), the mohawk exits, the 045 abort,
    owner #8's 12:00 close and the flat."""
    from .strategy import _lots
    if o <= pos["stop"]:
        tr.exits.append((ts, sd.x(o), pos["left"], "stop_gap")); pos["left"] = 0
    elif l <= pos["stop"]:
        tr.exits.append((ts, sd.x(pos["stop"]), pos["left"], "be" if pos["t1_done"] else "stop"))
        pos["left"] = 0
    elif p.sb_abort and i - 1 >= pos["fill_i"] and sd.c[i - 1] < pos["zone"][1] and l <= sd.l[i - 1]:
        px = min(o, float(sd.l[i - 1]))                # 045 ~1:19:58: a body closed outside the FVG, the next candle exceeds it
        tr.exits.append((ts, sd.x(px), pos["left"], "sb_abort")); pos["left"] = 0
    elif p.sb_mgmt in ("ladder", "gap424", "layered057"):   # scale out through the draw levels
        lv_, fr = pos["levels"], pos["fracs"]
        while pos["k"] < len(lv_) and pos["left"] and h >= lv_[pos["k"]] + p.exit_fill_through * p.tick:
            k = pos["k"]
            q = pos["left"] if k == len(lv_) - 1 else min(pos["left"], max(p.lot, _lots(pos["n"] * fr[min(k, len(fr) - 1)], p.lot)))
            tr.exits.append((ts, sd.x(lv_[k]), q, f"t{k + 1}")); pos["left"] -= q
            pos["k"] += 1
            if not pos["t1_done"]:
                pos["t1_done"] = True
                pos["stop"] = max(pos["stop"], pos["entry"])
            pos["away"] = lv_[k]
        if pos["left"] and pos["away"] is not None and c >= pos["away"] + p.away_pts * p.es_pt:
            pos["stop"] = max(pos["stop"], pos["away"] - p.trail_pad)
            pos["away"] = None
    else:
        if not pos["t1_done"] and h >= pos["t1"] + p.exit_fill_through * p.tick:
            if pos.get("super"):                       # gap 8: all but one lot at the SB target, the stop stays
                q = max(p.lot, pos["left"] - p.lot)
            else:
                q = pos["left"] if pos["t2"] is None else max(p.lot, _lots(pos["left"] * 0.8, p.lot))
            q = min(q, pos["left"])
            tr.exits.append((ts, sd.x(pos["t1"]), q, "t1")); pos["left"] -= q
            pos["t1_done"] = True
            if not pos.get("super"):
                pos["stop"] = max(pos["stop"], pos["entry"])
        if pos["left"] and pos["t2"] is not None and pos["t1_done"] and h >= pos["t2"] + p.exit_fill_through * p.tick:
            tr.exits.append((ts, sd.x(pos["t2"]), pos["left"], "t2")); pos["left"] = 0
    if pos["left"] and pos["lvx"] and i > pos["fill_i"]:
        for nm_, (lvl_, pre_t1) in pos["lvx"].items():       # A4 mohawk: a body close beyond the raw
            if (not pre_t1 or not pos["t1_done"]) and c < lvl_:   # level exits (as in run_day)
                tr.exits.append((ts, sd.x(c), pos["left"], nm_)); pos["left"] = 0
                break
    if (pos["left"] and session == "AM" and p.am_exit and p.am_exit_extras
            and t + ctx.tf >= p.am_exit):              # owner #8: close (not tighten) at 12:00
        if p.am_exit_mode == "close":
            tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
        elif not pos.get("am_tightened"):
            new = max(pos["stop"], pos["entry"], l - p.trail_pad)
            pos["am_tightened"] = True
            if new >= c:
                tr.exits.append((ts, sd.x(c), pos["left"], "am_exit")); pos["left"] = 0
            else:
                pos["stop"] = new
    if pos["left"] and t + ctx.tf >= flat_w:
        tr.exits.append((ts, sd.x(c), pos["left"], "eod")); pos["left"] = 0


def _sb_adds(ctx, p, pos, tr, sd, i, ts, o, l, c):
    """Gap 14 (080 ~17:20-17:50; 063 ~28:37): while the draw is untaken and before the first partial, a return into the
    filled FVG (price left it by add_retest_away_pts, no close through its far edge) and a new same-side FVG each add
    half the first size at their near edge (decreasing size, E12) [our interpretation], at most one add per source;
    the add shares the stop and the exits."""
    from .strategy import _total_cap, _lots
    from . import entries as _EN
    top, bot = pos["zone"]
    ap = pos.get("add_pend")
    if ap is not None and l <= ap["px"] and i > ap["i"]:           # a resting add limit fills
        px = min(ap["px"], o)
        per = px - pos["stop"]
        q = max(p.lot, _lots(pos["n0"] * 0.5, p.lot))
        q = _EN.cap_add(q, pos["n"], p)
        if per > 0 and ctx.equity:
            room = _total_cap(p, ctx.equity) - max(0.0, (pos["entry"] - pos["stop"]) * pos["left"])
            q = min(q, _lots(room / per, p.lot))
        if q >= max(p.lot, 1) and per > 0:
            tr.adds.append((ts, sd.x(px), q))
            pos["left"] += q; pos["n"] += q
            pos["adds_done"] += 1
        pos["add_pend"] = None
        return
    if pos["adds_done"] >= 2 or ap is not None:
        return
    if not pos["moved"] and c >= top + p.add_retest_away_pts * p.es_pt:
        pos["moved"] = True
    if pos["moved"] and not pos.get("fvg_add") and sd.c[pos["fill_i"]:i + 1].min() >= bot:
        pos["add_pend"] = dict(px=top, i=i)                        # a return into the filled FVG
        pos["fvg_add"] = True
        return
    for g in sd.gaps:                                              # a new FVG on the next leg (IOFED add)
        if g.i == i and g.i - 2 > pos["fill_i"] and g.bottom > pos["stop"] and not pos.get("new_add"):
            pos["add_pend"] = dict(px=g.top, i=i)
            pos["new_add"] = True
            return


def _bump_fr(o: dict, p, base):
    """Owner #7 revised: ladder shares of an armed order; a speed-bump rung takes the small htf_bump_frac share, the
    other rungs split the rest like the old ladder (targets.bump_fracs)."""
    from . import targets as _TP
    if o.get("bumps") and len(o["levels"]) > 1:
        return tuple(_TP.bump_fracs(o["levels"], o["bumps"], tuple(base), p))
    return base


def immediate_rebalance(sd, a: int, i: int, tick: float) -> bool:
    """A7 immediate rebalance (048 ~39:02; 060 ~7:20) [our interpretation of the bar test], side
    space: an up-close displacement candle k-1 whose NEXT candle k trades straight back to the
    high of the candle before it, h[k-2], within one tick and leaves no gap (an FVG is the deferred
    rebalance). Candles k in [a, i], closed bars only."""
    for k in range(max(a, 2), i + 1):
        if sd.c[k - 1] > sd.o[k - 1] and abs(sd.l[k] - sd.h[k - 2]) <= tick and sd.l[k] <= sd.h[k - 2] + 1e-12:
            return True
    return False
