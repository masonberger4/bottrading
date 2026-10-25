"""Caption-gap pass (digests/rulebook_gaps/*.md), package management_exits, chunk 1 of 3: the engine glue of its 34 specs -
bias_htf_intermarket.md 13, 68, 79, 209; day_selection_news_calendar.md 11, 58; definitions_pd_arrays_structure.md 2, 17, 25, 30, 31, 40, 62, 63, 65, 83, 94, 106, 111, 196;
levels_liquidity_targets.md 3, 47, 57, 84; management_partials_trailing_exits.md 5, 6, 10, 11, 12, 14, 16, 17, 18, 19.

Same conventions as tp1.py .. tp4.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1),
an object only from the bar that completes it. Every function sits behind a Params switch of the "caption-gap pass, management_exits #1/3" block; interpretations the sources do not
pin down are marked [our interpretation]. `HITS` is sm2's counter dict (tests: proof that a switch's code path RAN).

Hooks (strategy.py): `on_fill` (after manage.init_pos), `manage` (the position loop, once per closed bar), `rung_hook` / `rung_taken` (the ladder loop), `am_exit_hold` (the 12:00 close),
`void_pending` / `void_fill_bar` (fvg_full_fill_void), `day_pick` / `day_level` (day_mode_auto), `thu_block` (thu_cap), `flat_0830` (hold_through_0830), `after_close`, `trail_ok`."""
from __future__ import annotations

import re

import numpy as np

from . import levels as L
from . import sm2
from types import SimpleNamespace

HITS = sm2.HITS
hit = sm2.hit


def _S():
    from . import strategy as S
    return S


def _MG():
    from . import manage as MG
    return MG


def _TP():
    from . import targets as TP
    return TP


# --- 1. validation ----------------------------------------------------------------------------------------------------------------------------------

BPR_LIMITS = ("mt_body_close_abort", "no_reentry", "ce_touch", "mt_warn_far_exit", "far_edge")
BE_MODES = ("partial", "vi_then_new_ssl", "through_opposing_fvg", "adr_frac")
SWITCHES = ("nwog_traverse_hold", "tick_match_hold", "heavy_gauge", "no_lunch_retrace_hold", "hold_through_0830", "thu_cap", "far_half_no_adds", "fvg_bpr_backstop", "vi_mid_exit",
            "rip_through", "fvg_full_fill_void", "refusal_breakaway", "iof_intraday_exit", "sd_time_roll", "hold_reached", "sd_body_hold", "best_case_limit", "be_cap_htf", "day_mode_auto",
            "event_eve_lock", "trail_confirm")


def check_params(p) -> None:
    """Validation of the chunk's Params (strategy.Params.__post_init__)."""
    for name, ok in (("bpr_limit", BPR_LIMITS), ("breaker_mt_test", ("close", "trade")), ("ce_exit", ("close", "trade")), ("resistance_def", ("swings", "speed")),
                     ("exit_fill", ("touch", "limit_through", "touch_1tick")), ("be_mode", BE_MODES), ("runner_stop", ("", "leg_eq", "half_profit"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    if not (0 < p.heavy_scale < 1 and 0 < p.lunch_retr_max <= 1 and p.vi_mid_bars >= 1 and 0 < p.stall_partial <= 1 and p.resist_speed_bars >= 1 and p.run_through_bars >= 0
            and p.run_through_ticks >= 0 and p.hold_tf >= 1 and p.best_case_mult >= 0 and 0 < p.best_case_bulk <= 1 and p.exit_slip_ticks >= 0 and p.be_adr > 0
            and 0 < p.runner_eq_after <= 1 and 0 < p.day_mode_size <= 1 and 0 < p.pos_switch_frac < 1 and p.ifvg_fail_tf >= 0
            and p.iof_tol_bars >= 1 and p.iof_min_body_ticks >= 0 and p.rip_wick_mult >= 0):
        raise ValueError("management_exits #1/3: 0 < heavy_scale, best_case_bulk-share, stall_partial, day_mode_size <= 1 (heavy_scale < 1); 0 < lunch_retr_max, runner_eq_after <= 1; "
                         "vi_mid_bars, resist_speed_bars, hold_tf >= 1; run_through_bars, run_through_ticks, best_case_mult, exit_slip_ticks, ifvg_fail_tf >= 0; be_adr > 0; 0 < pos_switch_frac < 1")
    if len(p.sd_window) != 2 or not 0 <= p.sd_window[0] < p.sd_window[1] <= 1440:
        raise ValueError("sd_window: (start_minute, end_minute)")
    if p.sd_time_roll and p.sd_body_hold:
        raise ValueError("sd_time_roll and sd_body_hold both act on the SD rungs: set at most one of them")


def any_on(p) -> bool:
    """Does any mid-trade switch of the chunk need the per-position state (pos["me1"])?"""
    return bool(any(getattr(p, k) for k in SWITCHES) or p.bpr_limit != "mt_body_close_abort" or p.breaker_mt_test != "close" or p.ce_exit != "close" or p.run_through_bars
                or p.be_mode != "partial" or p.exit_mode2 == "full_pull" or p.runner_stop or p.resistance_def != "swings" or p.ifvg_fail_tf)


def eff_params(p):
    """The effective Params of a day: the breakeven modes that replace the first-partial rule switch `be_on` off (X4 / D14: "the be_on branches are skipped in this mode")."""
    if p.be_mode != "partial" or p.be_cap_htf:
        if p.be_on != "off":
            key = (p.be_mode, p.be_cap_htf, p.be_on)
            c = p.__dict__.get("_me1_eff")                       # built once per Params (not re-validated by replace() on every day)
            if c is None or c[0] != key:
                from dataclasses import replace
                c = (key, replace(p, be_on="off"))
                p.__dict__["_me1_eff"] = c
            return c[1]
    return p


def bemode(p) -> str:
    """X4-be-without-partials: the breakeven mode in force - `be_mode`, or the opposing-FVG breakeven for a full-pull trade (exit_mode2 == "full_pull": no partial exists to trigger the usual one)."""
    if p.be_mode == "partial" and p.exit_mode2 == "full_pull":
        return "through_opposing_fvg"
    return p.be_mode


# --- 2. helpers ---------------------------------------------------------------------------------------------------------------------------------------

def _tag(tr, name: str) -> None:
    """A tag set during the trade (Trade.mgmt_tags: not an entry column, so the order-time lv_tags stay what the no-look-ahead runs compare at the entry)."""
    if name not in (tr.mgmt_tags or "").split("|"):
        tr.mgmt_tags = "|".join(x for x in (tr.mgmt_tags, name) if x)


def _exit(pos, tr, sd, ts, px, reason, q=None) -> None:
    _MG()._exit(tr, sd, ts, px, pos["left"] if q is None else q, reason, pos)


def trail_ok(pos) -> bool:
    """False while a lock (runner_stop / event_eve_lock) or a confirmation rule (be_cap_htf, trail_confirm, refusal_breakaway) keeps the ladder_trail FVG trails off."""
    if pos.get("no_trail"):
        return False
    d = pos.get("me1")
    return not (d and d.get("trail_block"))


def opp_gaps(ctx, sd, upto: int) -> list:
    """The opposite-polarity gaps in side space (the other Side's bullish gaps, mirrored), known by bar `upto`: [SimpleNamespace(i, bottom, top, mid)]."""
    other = (getattr(ctx, "sides_map", None) or {}).get(-sd.sign)
    if other is None:
        return []
    return [SimpleNamespace(i=g.i, bottom=-float(g.top), top=-float(g.bottom), mid=-float(g.mid)) for g in other.gaps if g.i <= upto]


def wick_objs(ctx, sd, upto: int, p, back: int = 200) -> list:
    """A8-rip-through-ce-signature, 'large wick in the path' [our interpretation]: the upper wicks (side space) of the bars up to `upto` that are >= rip_wick_mult x the median range of the 20 bars
    before them, as gap-like objects (bottom = the body high, top = the high, mid = the wick CE)."""
    out = []
    for k in range(max(ctx.start, 1, upto - back), upto + 1):
        bh = max(float(sd.o[k]), float(sd.c[k]))
        w = float(sd.h[k]) - bh
        rng = sd.h[max(0, k - 20):k] - sd.l[max(0, k - 20):k]
        if w > 0 and len(rng) and w >= p.rip_wick_mult * float(np.median(rng)):
            out.append(SimpleNamespace(i=k, bottom=bh, top=float(sd.h[k]), mid=(bh + float(sd.h[k])) / 2.0))
    return out


def agg(ctx, sd, i: int, m: int, back: int = 90):
    """The completed m-minute candles (side space) ending at or before bar i, from the engine bars: [(open, high, low, close, end_bar)]; [] when the engine timeframe does not divide m."""
    tf = ctx.tf
    if m % tf:
        return []
    n = m // tf
    out = []
    for e in range(max(ctx.start, i - back), i + 1):
        if (ctx.t[e] + tf) % m:
            continue
        s = e - n + 1
        if s < ctx.start or ctx.t[s] % m:
            continue
        out.append((float(sd.o[s]), float(sd.h[s:e + 1].max()), float(sd.l[s:e + 1].min()), float(sd.c[e]), e))
    return out


def _closed_frac(pos, tr) -> float:
    q = sum(x[2] for x in tr.exits if re.fullmatch(r"t\d+", str(x[3])))
    return q / max(pos["n"], 1)


def _avg(pos) -> float:
    return pos["basis"] / pos["n"]


def _lv(pos) -> list:
    """The rungs the ladder loop walks (strategy: levels[:len(fracs)], the locked-draw variant ends on levels[-1])."""
    fr, lv = pos["fracs"], list(pos["levels"])
    if pos.get("final_T") and len(lv) > len(fr):
        return lv[:len(fr) - 1] + [lv[-1]]
    return lv[:len(fr)]


lv = _lv


def _collapse_to_last(pos, k: int, new_last=None) -> None:
    """The not yet taken rungs k.. are dropped: their whole share goes to the last rung (optionally replaced by `new_last`)."""
    lv, fr = _lv(pos), list(pos["fracs"])
    kd = list(pos.get("level_kinds") or [])
    n = len(lv)
    if k >= n or (n - k < 2 and new_last is None):
        return
    tot = sum(fr[k:])
    last_v = lv[n - 1] if new_last is None else float(new_last)
    last_k = (kd[n - 1] if len(kd) >= n else "array") if new_last is None else "array"
    pos["levels"] = lv[:k] + [last_v]
    pos["level_kinds"] = (kd[:k] + [last_k]) if len(kd) >= k else kd
    pos["fracs"] = tuple(fr[:k] + [tot])


def release_0830(day, p) -> bool:
    from .calendar import release_times
    return 510 in release_times(day, claims=p.news_claims)


def flat_0830(day, p) -> bool:
    """N5-hold-through-0830 (032 ~00:06:56; 040 ~00:01:03; 091 ~00:22:26): is an open pre-09:30 position closed at 08:29 on this day? `pre_flat_0830` on a day with a 08:30 release; the experienced
    `hold_through_0830` holds it - except on a jobs / CPI day (N1 / N4 strict), which stay excluded."""
    if not p.pre_flat_0830 or not release_0830(day, p):
        return False
    hit("eval_flat_0830")
    if not p.hold_through_0830:
        return True
    from claude_hf.daytypes import events
    return bool(events(day) & {"jobs", "cpi"})


def pre8_cut(day, p) -> int:
    """The fill cut (minute) of a PRE8 order: 08:30 (510) on a day with a 08:30 release under pre_flat_0830 (or am_from_0830) - whether or not a position is HELD through the release
    (hold_through_0830): nothing new opens on or after the 08:30 bar ('never open on the 08:30 bar itself') - else 09:30 (570)."""
    return 510 if (p.am_from_0830 or (p.pre_flat_0830 and release_0830(day, p))) else 570


def entry_cut_0825(day, p, session: str) -> int | None:
    """N5-hold-through-0830: 'no_entry_0825' - a pre-09:30 order does not fill from 08:25 on a day with a 08:30 release (505); None = no cut. The experienced `hold_through_0830` keeps the
    08:25-08:29 entries (a Ma Deuce short on the retrace into the inverted FVG) - except on a jobs / CPI day."""
    if not p.no_entry_0825 or session not in ("PRE7", "PRE8", "LON") or not p.pre_flat_0830 or not release_0830(day, p):
        return None
    if p.hold_through_0830:
        from claude_hf.daytypes import events
        if not (events(day) & {"jobs", "cpi"}):
            return None
    return 505


# --- 3. fill time ------------------------------------------------------------------------------------------------------------------------------------

def _htf_entry_hi(ctx, sd, i: int, price: float):
    """The top (side space) of the highest-timeframe (>= 60m) valid entry array that holds the fill price at bar i, from the Confluence object; None if the entry came from none."""
    cf = getattr(ctx, "conf", None)
    if cf is None or not hasattr(cf, "z"):
        return None
    now = float(ctx.idx[i].value)
    real = float(sd.x(price))
    best = None
    for tf in ("1h", "4h", "D", "W", "M"):
        z = cf.z.get(tf)
        if z is None:
            continue
        m = ((z["kind"] == sd.sign) & (z["known"] <= now) & (z["dead"] > now) & (now - z["known"] <= z["life"]) & (z["bottom"] - cf.tol <= real) & (real <= z["top"] + cf.tol))
        if m.any():
            a, b = z["top"][m], z["bottom"][m]
            hi = float(max(max(sd.x(float(x)), sd.x(float(y))) for x, y in zip(a, b)))
            best = hi
    return best


def _nwog_zone(ctx, sd, i: int):
    S = _S()
    zs = S._nwogs(ctx, i)
    if not zs:
        return None
    a, b = zs[-1]
    x, y = float(sd.x(a)), float(sd.x(b))
    return (min(x, y), max(x, y))


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p, fill: float) -> None:
    """Fill time (side space): the state the mid-trade hook needs."""
    S = _S()
    d = dict(o.get("me1") or {})
    d["fill_i"] = i
    d["no_adds0"] = bool(pos.get("no_adds"))
    tk = p.tick
    fi_ext = int(o.get("ext_i", i))
    pos["me1"] = d
    bm = bemode(p)
    if bm == "vi_then_new_ssl":
        vis = [z for z in sd.vis("bull") if z.i < i and z.i >= fi_ext and z.bottom >= fill - tk]
        if vis:
            z = min(vis, key=lambda z: z.bottom)
            d["vi"] = (float(z.bottom), float(z.top))
        if tr.bz_top is not None and tr.bz_bottom is not None:
            d["bz_far"] = float(min(sd.x(tr.bz_top), sd.x(tr.bz_bottom)))
    if bm == "through_opposing_fvg":
        T = float(pos["levels"][-1]) if pos.get("levels") else np.inf
        c_ = [g for g in opp_gaps(ctx, sd, i - 1) if g.bottom >= fill - tk and g.bottom < T]
        if c_:
            d["opp"] = min(c_, key=lambda g: g.bottom)
    if bm == "adr_frac":
        d["adr"] = S.adr5(list(getattr(ctx, "hist", None) or [])[-5:])
    if p.be_cap_htf:
        d["htf_hi"] = _htf_entry_hi(ctx, sd, i, fill)
        d["np"] = 0
        d["trail_block"] = False
    if p.trail_confirm and pos.get("kind") not in ("ob_pre", "ob_anchor", "turtle_soup"):
        g0 = next((g for g in sd.gaps if abs(float(g.bottom) - float(pos["fvg_bottom"])) < 1e-9 and g.i <= i), None)
        d["P"] = (float(pos["fvg_bottom"]), float(pos.get("fvg_top", pos["fvg_ce"] * 2 - pos["fvg_bottom"])), int(g0.i) if g0 is not None else fi_ext)
        d["P_ok"] = False
        d["trail_block"] = True
    if p.best_case_limit and pos.get("levels") and not pos.get("runner"):
        O = float(_lv(pos)[-1])
        d["best_fill"] = float(fill)
        d["best_case"] = O + p.best_case_mult * (O - fill)
        pos["best_case"] = d["best_case"]
    if p.heavy_gauge:
        arrs = []
        top_ent = float(pos["fvg_ce"]) * 2 - float(pos["fvg_bottom"]) if pos.get("fvg_ce") is not None and pos.get("fvg_bottom") is not None else float(fill)      # the entry gap's top (read explicitly: pos has no fvg_top)
        for g in sd.gaps:
            if g.i < i and g.top <= fill + 1e-9 and g.bottom > pos["stop"] and not (abs(g.bottom - pos["fvg_bottom"]) < 1e-9 and abs(g.top - top_ent) < 1e-9):
                arrs.append((float(g.bottom), float(g.top), float((g.top + g.bottom) / 2)))
        for z in sd.vis("bull"):
            if z.i < i and z.top <= fill + 1e-9 and z.bottom > pos["stop"]:
                arrs.append((float(z.bottom), float(z.top), float((z.top + z.bottom) / 2)))
        for z in sd.ifvgs():                                        # B6-untouched-premium-arrays-heavy: the IFVG (high / MT) counts like a gap
            if z.i < i and z.top <= fill + 1e-9 and z.bottom > pos["stop"]:
                arrs.append((float(z.bottom), float(z.top), float((z.top + z.bottom) / 2)))
        d["arrs"] = arrs
        d["heavy_touched"] = False
    if p.fvg_bpr_backstop and pos.get("kind") in ("fvg", "ifvg", "implied_fvg"):
        fb = float(pos["fvg_bottom"])
        for z in sd.bprs(p.bpr_max_gap_bars):
            if z.i < i and z.bottom - tk <= fb <= z.top + tk and z.bottom < fb:
                d["bpr_back"] = float(z.mid)
                pos["lvx"] = dict(pos.get("lvx") or {})
                pos["lvx"]["bpr_abort"] = (float(z.mid), False)         # the BPR midpoint body close (A11) replaces the FVG far-edge exits
                hit("fvg_bpr_backstop")
                break
    if p.nwog_traverse_hold:
        d["nwog"] = _nwog_zone(ctx, sd, i)
    if p.far_half_no_adds:
        d["far_block"] = False
    if p.vi_mid_exit and pos.get("kind") == "vi" and pos.get("leg"):
        ext, hi = pos["leg"]
        d["vi_mid"] = float(ext + 0.5 * (hi - ext))
    if p.rip_through:
        c_ = [g for g in opp_gaps(ctx, sd, i - 1) + (wick_objs(ctx, sd, i - 1, p) if p.rip_wick_mult > 0 else [])
              if g.bottom >= fill - tk and (not pos.get("levels") or g.bottom < pos["levels"][-1])]
        if c_:
            g = min(c_, key=lambda g: g.bottom)
            d["rip_gap"] = (float(g.bottom), float(g.top), float(g.mid))
            d["rip_n"] = 0
    if p.iof_intraday_exit:
        d["iof_open"] = None
    if p.refusal_breakaway:
        d["miss"] = 0
    d["lod_hold"] = False
    d["speed_on"] = p.resistance_def == "speed"
    pos["me1"] = d


# --- 4. the ladder loop hooks -------------------------------------------------------------------------------------------------------------------------

def rung_hit_off(p) -> float:
    """E1-manual-touch-exits: the price offset a rung needs to print to count as hit (exit_fill)."""
    if p.exit_fill == "limit_through":
        return p.tick
    if p.exit_fill == "touch_1tick":
        return -p.tick
    return 0.0


def rung_px(level: float, p) -> float:
    """The fill price of a rung hit under exit_fill (touch_1tick: the level minus exit_slip_ticks)."""
    if p.exit_fill == "touch_1tick":
        return level - p.exit_slip_ticks * p.tick
    return level


def rung_hook(ctx, sd, pos, tr, k: int, lv: list, h: float, c: float, i: int, ts, p, t: int, tf: int):
    """The rung k of the ladder loop is hit on this closed bar. Returns None (go on: take the partial), "skip" (the rung is passed, its share moved to the next one) or "break"."""
    d = pos.get("me1")
    if not d:
        return None
    kinds = pos.get("level_kinds") or []
    kind = kinds[k] if k < len(kinds) else ""
    last = k == len(lv) - 1
    if d.get("best_case") is not None and last and not pos.get("runner"):
        return _best_case(ctx, sd, pos, tr, k, lv, h, c, i, ts, p)
    if p.sd_time_roll and kind in _TP().SD_KINDS:
        a, b = p.sd_window
        end = t + tf
        if end <= a:
            if last:
                return None
            fr = list(pos["fracs"])
            fr[k + 1] += fr[k]
            fr[k] = 0.0
            pos["fracs"] = tuple(fr)
            hit("sd_roll")
            return "skip"
        if a < end <= b:
            hit("eval_sd_window")
            if c >= lv[k]:
                _exit(pos, tr, sd, ts, c, "sd_window")
                tr.final_hit = True
                _tag(tr, "sd_window")
                hit("sd_window_exit")
            return "break"
        return None
    if p.sd_body_hold and kind in _TP().SD_KINDS:
        sdh = d.setdefault("sdh", {})
        if k in sdh and sdh[k] == "released":
            return None
        nxt = k + 1 < len(lv) and h >= lv[k + 1]
        if nxt:
            sdh[k] = "released"
            return None
        if k not in sdh:
            sdh[k] = i
            hit("sd_body_hold")
        return "break"
    if p.heavy_gauge and k == 0 and not d.get("heavy_touched") and not d.get("heavy_tag") and d.get("arrs") and len(lv) > 1 and pos["fracs"][0] > 0:
        d["heavy_tag"] = True
        _tag(tr, "heavy")
        fr = list(pos["fracs"])
        fr[1] += fr[0]
        fr[0] = 0.0
        pos["fracs"] = tuple(fr)
        hit("heavy_t1_skip")
        return "skip"
    return None


def _best_case(ctx, sd, pos, tr, k: int, lv: list, h: float, c: float, i: int, ts, p):
    """X2-best-case-resting-limit (009 ~00:01:06; cc10_008 ~00:14:20): the last rung O is not a limit exit - the bulk goes when price prints BEYOND it, the rest rests at
    best_case = O + best_case_mult x (O - avg)."""
    MG = _MG()
    d = pos["me1"]
    O = float(lv[k])
    if not d.get("bc_hold"):
        d["best_case"] = O + p.best_case_mult * (O - d.get("best_fill", _avg(pos)))       # recomputed from the CURRENT last rung (a collapse / move of the rungs moves O)
        pos["best_case"] = d["best_case"]
    bc = d["best_case"]
    o = float(sd.o[i])
    if d.get("bc_hold"):
        if h >= bc:
            _exit(pos, tr, sd, ts, max(bc, o), "best_case")
            tr.final_hit = True
            hit("best_case_fill")
        return "break"
    if h <= O:
        return "break"
    hit("eval_best_case")
    q = MG.cut_qty(pos["left"], p.best_case_bulk, p)       # best_case_bulk of the units STILL LEFT (the spec's "65 % of the units" after earlier partials would swallow the remainder: 65 % of n > 50 % left) [our interpretation]
    _exit(pos, tr, sd, ts, max(O, o), "bulk_O", q)
    pos["t1_done"] = True
    pos["last_partial_i"] = i
    _tag(tr, "best_case")
    if not pos["left"]:
        tr.final_hit = True
        return "break"
    lo = max(0, i - 20)
    rng = (sd.h[lo:i] - sd.l[lo:i])
    mom = bool(c > O and len(rng) and (h - sd.l[i]) >= 1.5 * float(np.median(rng)))
    if mom:
        prev = float(lv[k - 1]) if k >= 1 else _avg(pos)
        MG.raise_stop(pos, min(prev, c - p.tick))
        d["bc_hold"] = True
        hit("best_case_hold")
        if h >= bc:
            _exit(pos, tr, sd, ts, max(bc, o), "best_case")
            tr.final_hit = True
    else:
        _exit(pos, tr, sd, ts, c, "bulk_O")
        tr.final_hit = True
        hit("best_case_weak")
    return "break"


def rung_taken(ctx, sd, pos, tr, k: int, level: float, i: int, p) -> None:
    """A ladder rung k was filled on bar i (units may remain; pos["k"] is already k + 1)."""
    d = pos.get("me1")
    if not d:
        return
    low = False
    if p.resistance_def == "speed" and not d.get("first_rung"):
        d["first_rung"] = i
        n = i - pos["fill_i"] + 1
        tr.resist_speed = "low" if n <= p.resist_speed_bars else "high"
        low = tr.resist_speed == "low"
        hit("resist_speed")
    if not pos["left"]:
        return
    if p.run_through_bars:
        d.setdefault("rt", []).append(dict(level=float(level), i0=i, state=None))
    if p.hold_reached:
        d["held_lvl"] = float(level)
        d["held_i"] = i
    if low and p.resistance_mode in ("low_full", "both"):
        _collapse_to_last(pos, pos["k"])                    # a low-resistance (fast) run is pulled in full: the share of the rungs left goes to the last one [our interpretation]
        hit("resist_speed_full")


def _am_leg(ctx, sd, i: int):
    """T9: the AM leg (side space) from the 09:30-12:00 bars up to bar i (the overnight bars are no part of it): (low, high, low bar, high bar) or None."""
    ks = [k for k in range(ctx.start, i + 1) if 570 <= ctx.t[k] < 720]
    if not ks:
        return None
    lo_i = min(ks, key=lambda k: sd.l[k])
    hi_i = max(ks, key=lambda k: sd.h[k])
    return float(sd.l[lo_i]), float(sd.h[hi_i]), lo_i, hi_i, ks[-1]


def lunch_ext(ctx, sd, i: int, p) -> bool:
    """T9-strong-am-no-lunch-retrace, second bullet (cc10_012 ~00:11:54): a new PM order in the AM direction after a strong AM rally (the 09:30-12:00 low -> high, the 12:00 close in the
    upper half), no lunch retracement (< lunch_retr_max) and a PM break of the lunch high [our interpretation: 'PM break of the lunch high' as the trigger] keeps the last-hour window: its
    time exit at 15:00 (pm_done_by) is lifted (the final targets run to the 15:50 flat)."""
    if not p.no_lunch_retrace_hold or ctx.t[i] + ctx.tf < 780:
        return False
    leg = _am_leg(ctx, sd, i)
    if leg is None:
        return False
    lo, hi, lo_i, hi_i, last_am = leg
    rng = hi - lo
    if rng <= 0 or lo_i >= hi_i or sd.c[last_am] < lo + 0.5 * rng:
        return False
    lunch = [k for k in range(ctx.start, i + 1) if 720 <= ctx.t[k] < 780]
    if not lunch:
        return False
    if (hi - float(min(sd.l[k] for k in lunch))) / rng >= p.lunch_retr_max:
        return False
    lh = float(max(sd.h[k] for k in lunch))
    ok = any(sd.h[k] > lh + 1e-9 for k in range(ctx.start, i + 1) if ctx.t[k] >= 780)
    if ok:
        hit("lunch_ext")
    return bool(ok)


def am_exit_hold(ctx, sd, pos, tr, i: int, ts, p, am_x: int, ev_flat: bool = False) -> bool:
    """T9-strong-am-no-lunch-retrace (cc10_012 ~00:11:54): at the 12:00 AM close (and after it) - True = the engine does NOT close now. A strong AM rally from the 09:30 low whose lunch
    (12:00-13:00) low retraces less than lunch_retr_max of the AM leg keeps the AM-direction position to 15:50 / its target, the stop at the lunch low; otherwise it closes at 13:00.
    `ev_flat` (the flat time came from an event, e.g. nfp_flat_by on a jobs day) = never held."""
    if not p.no_lunch_retrace_hold or tr.session in ("PM", "LUNCH") or ev_flat:
        return False
    hit("eval_am_hold")
    d = pos.setdefault("me1", {})
    t, tf = ctx.t[i], ctx.tf
    st = d.get("lunch")
    if st is None:
        leg = _am_leg(ctx, sd, i)
        if leg is not None:
            lo, hi, lo_i, hi_i, last_am = leg
            if hi - lo > 0 and lo_i < hi_i and sd.c[last_am] >= lo + 0.5 * (hi - lo):
                d["lunch"], d["am_lo"], d["am_hi"] = "wait", lo, hi
                hit("lunch_wait")
                return True
        d["lunch"] = "no"
        return False
    if st == "no":
        return False
    if st == "wait":
        if t + tf < 780:
            return True
        sel = [k for k in range(ctx.start, i + 1) if 720 <= ctx.t[k] < 780]
        leg = d["am_hi"] - d["am_lo"]
        low = float(min(sd.l[k] for k in sel)) if sel else float(sd.l[i])
        retr = (d["am_hi"] - low) / leg
        if retr < p.lunch_retr_max:
            d["lunch"] = "held"
            _MG().raise_stop(pos, min(low, float(sd.c[i]) - p.tick))
            _tag(tr, "lunch_hold")
            hit("lunch_hold")
            return True
        d["lunch"] = "no"
        return False
    if st == "held":
        if t + tf >= 950:
            _exit(pos, tr, sd, ts, sd.c[i], "lunch_hold_exit")
            return True
        return True
    return False


def void_pending(pending: dict, sd, i: int) -> bool:
    """A pending FVG order is void once a closed bar after the arming bar printed beyond the entry FVG's far edge (fvg_full_fill_void, 013 ~17:55)."""
    if pending.get("entry_kind") not in ("fvg", "ifvg", "implied_fvg") or pending.get("fvg_bottom") is None or i - 1 <= pending["i"]:
        return False
    ok = bool(sd.l[pending["i"] + 1:i].min(initial=np.inf) < pending["fvg_bottom"] - 1e-9)
    if ok:
        hit("fvg_void_pending")
    return ok


def void_fill_bar(pos, sd, i: int, fill: float):
    """The fill bar traded on through the entry FVG's far edge: the exit price (side space), else None."""
    if pos.get("kind") not in ("fvg", "ifvg", "implied_fvg") or sd.l[i] >= pos["fvg_bottom"] - 1e-9:
        return None
    hit("fvg_void_fill")
    return float(min(pos["fvg_bottom"], fill))


def mt_exit_px(p, pos, o: float, l: float, c: float):
    """A13-breaker-mt-trade-test: the exit price when the breaker MT is lost under `breaker_mt_test` ("close": a body close below it; "trade": a print below MT - mohawk), else None."""
    mt = pos["bz_mt"]
    if p.breaker_mt_test == "close":
        return float(c) if c < mt else None
    lim = mt - p.mohawk
    if l < lim - 1e-9:
        hit("breaker_mt_trade")
        return float(min(o, lim))
    return None


def after_close(pos, tr, done: dict, key: str) -> None:
    d = pos.get("me1")
    if d and d.get("side_done") and done is not None:
        done[key] = True
        hit("hold_reached_done")
    if d and d.get("speed_on") and "first_rung" not in d and not tr.resist_speed:
        tr.resist_speed = "high"


# --- 5. the order stage (strategy._finish_order) -----------------------------------------------------------------------------------------------------

def day_pick(ctx, sd, i: int, p, entry: float) -> bool:
    """X5-day-trade-stop-no-trail (064 ~01:45:14), selection: day mode only when the htf.table bias agrees and the day's range is 'expansion' [our interpretation]: today's range so
    far under 0.5 x ADR5 and the next HTF draw (nearest untouched D / W / M array) >= 0.75 x ADR5 away."""
    S = _S()
    hit("eval_day_pick")
    if S._BD.bias_value(getattr(ctx, "bias_row", None), p) != sd.sign:
        return False
    adr = S.adr5(list(getattr(ctx, "hist", None) or [])[-5:])
    if not adr:
        return False
    rng = float(sd.h[ctx.start:i + 1].max() - sd.l[ctx.start:i + 1].min())
    if rng >= 0.5 * adr:
        return False
    from . import tp3
    dr = tp3.htf_draw(ctx, sd, i, p, entry, {})
    ok = dr is not None and dr - entry >= 0.75 * adr
    if ok:
        hit("day_mode_pick")
    return bool(ok)


def day_level(ctx, sd, k830: int, i: int, p) -> float:
    """The day-mode stop level (side space): the lower of the 08:30 open and the 08:30 wick CE, and beyond the low of the pre-08:30 range when that low was swept before the fill."""
    o830 = float(sd.o[k830])
    b830 = min(o830, float(sd.c[k830]))
    ce = float(b830 - (b830 - sd.l[k830]) / 2)
    lvl = min(o830, ce)
    pre = [k for k in range(ctx.start, k830) if ctx.t[k] < 510]
    if pre:
        lo = float(min(sd.l[k] for k in pre))
        if k830 <= i and float(sd.l[k830:i + 1].min()) < lo:
            lvl = min(lvl, lo)
            hit("day_mode_swept_low")
    return lvl


def thu_block(ctx, sd, i: int, p, session: str):
    """N10-thursday-caps-week (cc08_001 ~00:21:59): a Thursday NY-morning (09:30-12:00) new weekly extreme into a daily PD array is a candidate weekly high / low: no further entries in
    the direction of the extreme that day. Returns the filter tag or None."""
    if not p.thu_cap or ctx.day.weekday() != 3 or ctx.t[i] < 570:
        return None                                                # from 09:30 for the rest of that Thursday session (the extreme itself must be a 09:30-12:00 one)
    hit("eval_thu_block")
    hist = [g for g in (getattr(ctx, "hist", None) or []) if g.index[0].date().isocalendar()[:2] == ctx.day.isocalendar()[:2]]
    if not hist:
        return None
    import pandas as pd
    prior = max(float(g.high.max()) for g in hist) if sd.sign > 0 else -min(float(g.low.min()) for g in hist)
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return None
    run = prior
    for k in range(ctx.start, i + 1):
        if 570 <= ctx.t[k] < 720 and sd.h[k] > run + 1e-9:
            real = float(sd.x(sd.h[k]))
            now = ctx.idx[k] + pd.Timedelta(minutes=ctx.tf)
            if "D" in cf.at(now, real, -sd.sign):
                hit("thu_week_ext")
                return "x_thu_week_ext"
        run = max(run, float(sd.h[k]))
    return None


def mark_tags(tags: dict, name: str, value=True) -> None:
    tags.setdefault("me1", {})[name] = value


# --- 6. mid-trade management --------------------------------------------------------------------------------------------------------------------------

def manage(ctx, sd, pos, tr, i: int, ts, p) -> None:
    """Mid-trade (bar i closed): the stop moves, exits and tags of the chunk. Called once per bar after the bar's stop / ladder tests; a stop moved here applies from the next bar."""
    d = pos.get("me1")
    if not d or not pos["left"] or i <= pos["fill_i"]:
        return
    MG = _MG()
    o, h, l, c = float(sd.o[i]), float(sd.h[i]), float(sd.l[i]), float(sd.c[i])
    t, tf = ctx.t[i], ctx.tf
    fi = pos["fill_i"]
    tk = p.tick
    avg = _avg(pos)
    # --- E1 run-through watch (levels_liquidity_targets 3): a tap and stall at a rung
    for w in d.get("rt", ()):
        if w["state"] is None:
            if float(sd.h[w["i0"]:i + 1].max()) >= w["level"] + p.run_through_ticks * tk - 1e-9:
                w["state"] = "cont"
            elif i - w["i0"] + 1 >= p.run_through_bars:
                w["state"], w["si"] = "stall", i
                pos["stall_at"] = w["level"]
                _tag(tr, "rt_stall")
                hit("rt_stall")
        elif w["state"] == "stall" and i > w["si"] and c < w["level"] and pos["left"]:
            _exit(pos, tr, sd, ts, c, "rt_stall_exit")
            hit("rt_stall_exit")
            return
    # --- X2 best-case resting limit: checked on every bar, also when the ladder loop does not run
    if d.get("bc_hold") and h >= d["best_case"] and pos["left"]:
        _exit(pos, tr, sd, ts, max(d["best_case"], o), "best_case")
        tr.final_hit = True
        hit("best_case_fill")
        return
    # --- L14 hold above the reached objective (57)
    if p.hold_reached and d.get("held_lvl") is not None:
        m = max(1, p.hold_tf // tf)
        if ((t + tf) % p.hold_tf == 0 or m == 1) and i - m + 1 > d["held_i"] and c < d["held_lvl"]:
            _exit(pos, tr, sd, ts, c, "hold_lost")
            d["side_done"] = True
            _tag(tr, "hold_lost")
            hit("hold_reached_exit")
            return
    # --- L12 SD rung deferred while the 5m bodies hold beyond it (84)
    if p.sd_body_hold and d.get("sdh"):
        m = max(1, p.hold_tf // tf)
        if (t + tf) % p.hold_tf == 0 or m == 1:
            for kk, v in list(d["sdh"].items()):
                if v == "released" or pos["k"] != kk:
                    continue
                lvl = float(pos["levels"][kk])
                if c < lvl:
                    fr = pos["fracs"]
                    last = kk == len(pos["levels"][:len(fr)]) - 1
                    q = pos["left"] if last else min(pos["left"], max(p.lot, MG._lots(pos["n"] * fr[kk], p)))
                    _exit(pos, tr, sd, ts, c, f"t{kk + 1}", q)
                    pos["k"] = kk + 1
                    d["sdh"][kk] = "released"
                    if pos["left"]:
                        pos["last_partial_i"] = i
                        if not pos["t1_done"]:
                            pos["t1_done"] = True
                            if p.be_on == "t1":
                                MG.be_move(pos, p)
                        pos["trail_now"] = True
                        d["trail_body"] = True
                        pos["away"] = lvl
                    hit("sd_body_release")
                    if not pos["left"]:
                        return
    # --- A11 bpr_limit (2)
    z = d.get("bpr")
    if z is not None and pos["left"]:
        bot, top, mid = z
        mode = p.bpr_limit
        if mode == "mt_warn_far_exit" and l <= mid and not d.get("bpr_warn"):
            d["bpr_warn"] = True
            _tag(tr, "bpr_warn")
        px = None
        if mode == "no_reentry" and l <= top:
            px = min(o, top)
        elif mode == "ce_touch" and l <= mid:
            px = min(o, mid)
        elif mode == "mt_warn_far_exit" and l <= bot:
            px = min(o, bot)
        elif mode == "far_edge" and l < bot - 1e-9:
            px = min(o, bot)
        if px is not None:
            _exit(pos, tr, sd, ts, px, "bpr_" + mode)
            hit("bpr_limit_exit")
            return
    # --- X9 entry FVG full fill (63): a print through the far edge voids the idea (before the first partial [our interpretation])
    if p.fvg_full_fill_void and pos.get("kind") in ("fvg", "ifvg", "implied_fvg") and not pos["t1_done"] and l < pos["fvg_bottom"] - 1e-9:
        _exit(pos, tr, sd, ts, min(o, pos["fvg_bottom"]), "fvg_void")
        hit("fvg_void_exit")
        return
    # --- A5 ce_exit trade (30)
    if p.ce_exit == "trade" and not pos["t1_done"] and (p.ce_hold or pos.get("ce_hold")) and l < pos["fvg_ce"] - 1e-9:
        _exit(pos, tr, sd, ts, min(o, pos["fvg_ce"]), "ce_trade")
        hit("ce_trade")
        return
    # --- A9 broken VI retrace to the midpoint (40)
    if d.get("vi_mid") is not None and pos["left"]:
        hit("eval_vi_mid")
        vm = d["vi_mid"]
        if d.get("vi_touch") is None:
            if l <= vm:
                d["vi_touch"] = i
                if c > vm:
                    d["vi_touch"] = -1
        if d.get("vi_touch") is not None and d["vi_touch"] >= 0:
            if c > vm:
                d["vi_touch"] = -1
            elif i - d["vi_touch"] >= p.vi_mid_bars:
                _exit(pos, tr, sd, ts, c, "vi_mid")
                hit("vi_mid_exit")
                return
    # --- A8 IFVG on 15m bodies (83)
    if d.get("ifvg15") is not None and not pos["t1_done"]:
        m = max(1, p.ifvg_fail_tf // tf)
        if ((t + tf) % p.ifvg_fail_tf == 0 or m == 1) and c < d["ifvg15"]:
            _exit(pos, tr, sd, ts, c, "ifvg_fail")
            hit("ifvg15_exit")
            return
    # --- B6 intraday IOF (111)
    if p.iof_intraday_exit:
        io = d.get("iof_open")
        if io is not None and c < io:
            _exit(pos, tr, sd, ts, c, "iof_fail")
            hit("iof_exit")
            return
        if c < o and (o - c) >= p.iof_min_body_ticks * tk - 1e-9:
            d["iof_open"] = o                                     # the newest down-close candle's open (the support the IOF needs)
            if p.iof_strict:
                d.setdefault("iof_sup", []).append([i, h, l, None])
        if p.iof_strict:
            for sup in list(d.get("iof_sup", ())):
                j, hj, lj, br = sup
                if i <= j:
                    continue
                if h > hj:
                    d["iof_sup"].remove(sup)                      # the support led to a new short-term high
                    continue
                if br is None and l < lj - 1e-9:
                    sup[3] = -1 if c >= lj else i                 # a short-term low taken: it must reverse right away
                if i - j >= p.iof_tol_bars or (sup[3] is not None and sup[3] >= 0 and i - sup[3] + 1 > p.iof_tol_bars):
                    _exit(pos, tr, sd, ts, c, "iof_fail")
                    hit("iof_strict_exit")
                    return
    # --- N10 Thursday cap (58)
    if p.thu_cap and ctx.day.weekday() == 3 and pos["fill_t"] < 570:
        hit("eval_thu_cap")
    if p.thu_cap and ctx.day.weekday() == 3 and pos["fill_t"] < 570 and t + tf >= 600:
        _tag(tr, "thu_cap")
        _exit(pos, tr, sd, ts, c, "thu_cap")
        hit("thu_cap_exit")
        return
    # --- breakeven modes (10, 11, 14, 12) and the stop locks (16, 18, 19)
    _be_modes(ctx, sd, pos, tr, d, i, p, o, h, l, c, avg)
    _be_cap(ctx, sd, pos, tr, d, i, p, c)
    _runner_lock(ctx, sd, pos, tr, d, i, p, c)
    _trail_confirm(ctx, sd, pos, tr, d, i, p, h, l)
    # --- tags / holds
    _expansion(ctx, sd, pos, tr, d, i, p)
    _heavy(ctx, sd, pos, tr, d, i, p, l, ts, c)
    _tick_match(ctx, sd, pos, tr, d, i, p)
    _strength(ctx, sd, pos, tr, d, i, p, h, l, c, ts)


def _be_modes(ctx, sd, pos, tr, d, i, p, o, h, l, c, avg) -> None:
    MG = _MG()
    mode = bemode(p)
    if mode == "partial":
        return
    hit("eval_be_" + mode)
    be = MG.be_stop(pos, p)
    fi = pos["fill_i"]
    if mode == "vi_then_new_ssl" and not d.get("ssl_done"):
        vi = d.get("vi")
        if vi is not None and not d.get("vi_done"):
            a = d.get("vi_arm")
            if a is not None and i == a + 1:
                if c > vi[1]:                                       # the bar after the print through the VI closes beyond it: the move holds
                    if d.get("bz_far") is not None:
                        MG.raise_stop(pos, min(d["bz_far"] - p.pad, c - p.tick))
                    d["vi_done"] = True
                    hit("be_vi")
                d["vi_arm"] = None
            if not d.get("vi_done") and h > vi[1]:
                d["vi_arm"] = i
        sw = [x for x in pos["side"].ph if x.known <= i - 1 and x.i > fi]
        if sw and h > sw[-1].price:
            MG.raise_stop(pos, min(be, c - p.tick) if be >= c else be)
            d["ssl_done"] = True
            hit("be_new_ssl")
    elif mode == "through_opposing_fvg" and not d.get("opp_done"):
        opp = d.get("opp")
        if opp is not None:
            if h > opp.top:
                MG.raise_stop(pos, min(be, c - p.tick))
                d["opp_done"] = True
                hit("be_opp_fvg")
        else:
            for g in sd.gaps:
                if g.i <= i and g.i - 2 > fi and g.bottom > avg:   # the fallback: the first same-direction FVG formed after the fill, entirely beyond the entry [our interpretation]
                    MG.raise_stop(pos, min(be, c - p.tick))
                    d["opp_done"] = True
                    hit("be_fallback_fvg")
                    break
    elif mode == "adr_frac" and not d.get("adr_done"):
        adr = d.get("adr")
        if adr and pos["best"] - avg >= p.be_adr * adr - 1e-9:
            MG.raise_stop(pos, min(avg, c - p.tick))                # the average entry itself (spec: avg), capped under the close
            d["adr_done"] = True
            hit("be_adr_frac")


def _be_cap(ctx, sd, pos, tr, d, i, p, c) -> None:
    """X4-be-plus-cap-htf (105 ~00:10:50, ~01:00:51): each raise happens only after a partial fills."""
    if not p.be_cap_htf:
        return
    hit("eval_be_cap")
    MG = _MG()
    n = sum(1 for x in tr.exits if re.fullmatch(r"t\d+", str(x[3])))
    hi = d.get("htf_hi")
    while d["np"] < n:
        d["np"] += 1
        k = d["np"]
        if k == 1:
            new = MG.be_stop(pos, p)
            if hi is not None:
                new = min(new, hi - p.pad)
            MG.raise_stop(pos, min(new, c - p.tick))
            pos["be_done"] = True
            d["p1_i"] = i
            d["trail_block"] = True
            hit("be_cap_1")
        elif k == 2:
            j0 = d.get("p1_i", pos["fill_i"])
            kk = j0 + int(np.argmax(sd.h[j0:i])) if i > j0 else i              # the highest bar between the partials (the bar of partial 2 itself only when both fill on one bar)
            MG.raise_stop(pos, min(L.upper_wick_ce(sd.o, sd.h, sd.c, kk) - p.tick, c - p.tick))
            d["trail_block"] = False
            hit("be_cap_2")
        elif hi is not None:
            MG.raise_stop(pos, min(hi, c - p.tick))
            hit("be_cap_3")


def _runner_lock(ctx, sd, pos, tr, d, i, p, c) -> None:
    """X5-runner-stop-half-open-profit (036 ~01:01:33; 065 ~02:56:01) and X5-event-tight-lock-020 (020 ~00:09:40): once the closed ladder fraction reaches the threshold."""
    if not (p.runner_stop or p.event_eve_lock) or (d.get("rs_done") and d.get("ev_done")):
        return
    hit("eval_runner_lock")
    MG = _MG()
    frac = _closed_frac(pos, tr)
    avg = _avg(pos)
    if p.runner_stop and not d.get("rs_done") and frac >= p.runner_eq_after - 1e-9:
        if p.runner_stop == "leg_eq":
            eq = (float(pos["ext"]) + float(pos["best"])) / 2.0
            new = max(avg, eq - p.tick)
        else:
            new = avg + 0.5 * (c - avg)
        MG.raise_stop(pos, min(new, c - p.tick))
        pos["no_trail"] = True
        d["rs_done"] = True
        hit("runner_lock_" + p.runner_stop)
    if p.event_eve_lock and not d.get("ev_done") and frac >= 0.75 - 1e-9:
        hit("eval_event_eve")
        if "ev" not in d:
            from claude_hf.daytypes import events
            from .calendar import next_trading_day
            d["ev"] = bool(events(next_trading_day(ctx.day)) & {"fomc", "cpi", "jobs"})
        if d["ev"]:
            gs = [g for g in sd.gaps if g.i <= i and g.i - 2 > pos["fill_i"] and g.top < c]
            if gs:
                g = max(gs, key=lambda g: g.i)
                MG.raise_stop(pos, min(float(g.top) + p.pad, c - p.tick))
                pos["no_trail"] = True
                d["ev_done"] = True
                _tag(tr, "event_lock")
                hit("event_eve_lock")


def _trail_confirm(ctx, sd, pos, tr, d, i, p, h, l) -> None:
    """X5-trail-after-protected-gap-confirmed (003 ~00:41:35; 062 ~00:39:12): the stop goes to the protected zone P only after (a) a new same-direction FVG beyond P or (b) a new extreme
    past the post-gap swing with part of P unfilled."""
    P = d.get("P")
    if not p.trail_confirm or P is None or d.get("P_ok"):
        return
    hit("eval_trail_confirm")
    MG = _MG()
    bot, top, gi = P
    if l < bot - 1e-9:
        d["P"] = None                                           # P filled completely: not a breakaway gap
        hit("trail_confirm_void")
        return
    ok = any(g.i <= i and g.i > gi and g.bottom > top for g in sd.gaps)
    if not ok and i - 1 >= gi and h > float(sd.h[gi:i].max()) and float(sd.l[gi:i + 1].min()) > bot:
        ok = True
    if ok:
        MG.raise_stop(pos, bot - p.pad)
        d["P_ok"] = True
        d["trail_block"] = False
        hit("trail_confirmed")


def _expansion(ctx, sd, pos, tr, d, i, p) -> None:
    """BH-B14-NWOG-traverse-large-range (026 ~01:32:09): price traded from one NWOG edge to the other this session = an expansion day: the whole position runs to the final rung."""
    z = d.get("nwog")
    if not p.nwog_traverse_hold or z is None or d.get("nwog_done"):
        return
    hit("eval_nwog")
    lo, hi = z
    st = ctx.start
    idx = np.flatnonzero(sd.l[st:i + 1] <= lo + 1e-9)
    if not len(idx):
        return
    j = st + int(idx[0])
    if float(sd.h[j:i + 1].max()) < hi - 1e-9:
        return
    d["nwog_done"] = True
    pos["expansion"] = True
    _tag(tr, "nwog_traverse")
    hit("nwog_traverse")
    if pos.get("runner"):
        return
    nxt = None
    if not pos.get("final_T") and pos.get("levels"):
        last = float(_lv(pos)[-1])
        c_ = [x.price for x in sd.ph if x.known <= i and x.price > last + p.tick]       # the next pool beyond the final rung: the nearest old swing high above it [our interpretation]
        nxt = min(c_) if c_ else None
    _collapse_to_last(pos, pos["k"], nxt)


def _heavy(ctx, sd, pos, tr, d, i, p, l, ts, c) -> None:
    """B6-untouched-premium-arrays-heavy (078 ~00:57:07 ...): a print past the CE of an opposing array between the entry and the stop = less heavy: a partial of heavy_scale (once)."""
    if not p.heavy_gauge or d.get("heavy_touched") or not d.get("arrs"):
        return
    hit("eval_heavy")
    hit_ce = [ce for _, _, ce in d["arrs"] if l <= ce + 1e-9]
    if hit_ce:
        d["heavy_touched"] = True
        q = _MG().cut_qty(pos["left"], p.heavy_scale, p)
        _tag(tr, "heavy_scale")
        hit("heavy_scale")
        _exit(pos, tr, sd, ts, min(float(sd.o[i]), max(hit_ce)), "heavy_scale", q)       # the partial goes at the CE touch (not the bar close)


def _tick_match(ctx, sd, pos, tr, d, i, p) -> None:
    """BH-micro-BPR-tick-match-LOD (055 ~00:15:51): on the 3m chart a later candle's low equals an earlier candle's high to the tick inside a BPR (after the entry), then a 3m close above the
    retrace high = the low of the day is in: hold (the X9 time stop is skipped) [our interpretation]."""
    if not p.tick_match_hold or d.get("lod_hold") or ctx.t[i] >= p.am[1]:
        return
    cs = agg(ctx, sd, i, 3, 60)
    if not cs or cs[-1][4] != i:
        return
    o3 = np.array([x[0] for x in cs]); h3 = np.array([x[1] for x in cs]); l3 = np.array([x[2] for x in cs]); c3 = np.array([x[3] for x in cs])
    j = len(cs) - 1
    hit("eval_tick_match")
    if d.get("tm_hi") is not None:
        if c3[j] > d["tm_hi"]:
            d["lod_hold"] = True
            _tag(pos["trade"], "lod_in")
            hit("lod_in")
        return
    if cs[j][4] <= pos["fill_i"]:
        return
    zones = [(float(z.bottom), float(z.top)) for z in L.balanced_ranges(h3, l3, 0, o3, c3)]
    k = L.tick_match_k(h3, l3, j, p.tick, 10, zones)
    if k is not None:
        d["tm_hi"] = float(h3[k:j + 1].max())
        hit("tick_match")


def _strength(ctx, sd, pos, tr, d, i, p, h, l, c, ts) -> None:
    """A5-partial-fill-strength-read (far_half_no_adds), A8-rip-through-ce-signature (rip_through), A6-breakaway-by-refusal (refusal_breakaway)."""
    MG = _MG()
    fi = pos["fill_i"]
    if p.far_half_no_adds:
        gs = [g for g in sd.gaps if g.i <= i and g.i - 2 > fi]
        blocked = False
        if gs:
            g = max(gs, key=lambda g: g.i)
            blocked = bool(sd.l[g.i + 1:i + 1].min(initial=np.inf) <= g.mid - 1e-9)      # the far half of the newest post-entry gap was traded into: no more adds
        if blocked != d.get("far_block"):
            d["far_block"] = blocked
            pos["no_adds"] = bool(d["no_adds0"] or blocked)
            if blocked:
                pos["add"] = None
                _tag(tr, "strength_read")
                hit("far_half_block")
    rg = d.get("rip_gap")
    if p.rip_through and rg is not None and not d.get("rip_done"):
        hit("eval_rip")
        bot, top, ce = rg
        if l <= ce <= h:
            d["rip_ce"] = True                                    # a candle traded THROUGH the CE (not a gap over it) before the far-edge print
        if h > top and d.get("rip_ce"):
            d["rip_done"] = True
            _tag(tr, "rip")
            hit("rip")
        elif abs(c - ce) <= p.es_pt:
            d["rip_n"] += 1
            if d["rip_n"] >= 3:
                d["rip_done"] = True
                _tag(tr, "stall")
                pos["no_adds"] = True
                pos["add"] = None
                hit("rip_stall")
                q = MG.cut_qty(pos["left"], p.stall_partial, p)
                _exit(pos, tr, sd, ts, c, "stall_partial", q)


def add_missed(pos, p, a=None) -> None:
    """A6-breakaway-by-refusal (090 ~2:03:43): an armed add TIMED OUT unfilled while price ran away from it - the best price since the fill is at least as far above the entry as the add
    sits below it [our interpretation: 'price runs without touching level 1 / level 2']. Cancels by a partial, a hold break, chop or a cut are no refusal (the caller passes only a pure
    time-out). Two missed adds = the most recent FVG is a breakaway gap: no trailing inside it [our interpretation: the ladder_trail FVG trails go off]. `a` None = count unconditionally."""
    d = pos.get("me1")
    if not p.refusal_breakaway or not d or d.get("refusal"):
        return
    hit("eval_add_expiry")
    if a is not None:
        avg = _avg(pos)
        if a.get("px") is None or pos["best"] - avg < max(avg - float(a["px"]), p.tick) - 1e-9:
            return
    d["miss"] = d.get("miss", 0) + 1
    hit("add_missed")
    if d["miss"] >= 2:
        d["refusal"] = True
        d["trail_block"] = True
        pos["breakaway_refusal"] = True
        _tag(pos["trade"], "breakaway_refusal")
        hit("breakaway_refusal")


# --- 7. helper for a position trade (levels_liquidity / definitions 196: spec only) -------------------------------------------------------------

def pos_trail(lows, highs, side: int, entry: float, objective: float, price: float, switch_frac: float = 0.5, long_n: int = 40, short_n: int = 20) -> float:
    """new-position-trade-grading-fib (cc05_018 ~16:20), SPEC ONLY (no multi-day position engine exists yet; deferred until the swing models, M17): the trail of a position trade from the
    daily bars: before `switch_frac` of the way from the entry to the objective the stop sits beyond the `long_n`-day extreme (40), afterwards beyond the `short_n`-day extreme (20).
    `lows` / `highs` = the daily lows / highs up to the last closed day; side +1 long (the stop under the lows), -1 short (over the highs)."""
    prog = (price - entry) / (objective - entry) if objective != entry else 0.0
    n = short_n if prog >= switch_frac else long_n
    return float(min(lows[-n:])) if side > 0 else float(max(highs[-n:]))
