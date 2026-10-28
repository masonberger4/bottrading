"""Caption-gap pass, package bias_htf#6/7: the STUDY-ONLY items (research functions, no live branch, nothing here reads Params).

management_partials_trailing_exits.md items 13, 15, 31, 32, 33, 135-142 -> `swing_mgmt_study` (+ `four_h_trail`, `htf_array_ladder`, `opp_ob_ladder`, `donchian_stops`, `days_to_target_report`,
                                  `daily_limit_model`, `weekly_template_study`)
models_setups_entries.md items 96, 100, 133 (monthly OB), 155-162, 164-170 -> bh6t.py (`opening_price_model`, `daily_fvg_sellstop`, `monthly_ob_study`, `daily_candle_entries`,
                                  `position_checklist`, `hallmarks`, `swing_entries`)

Every function is a pure function of the bars it is given. A daily bar is used only after its session closes: management starts the session AFTER the entry, stop moves are made at a bar's close and act from
the next bar, and when a stop and a target are both inside one bar the stop is taken first (the conservative reading of a daily bar). All prices are handled in "side space" (a short is a long on negated
prices). Thresholds the sources never give are marked [our interpretation]. Wrapper names live in study.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L

NAN = float("nan")


def _ohlc(df) -> tuple:
    return tuple(df[k].values.astype(float) for k in ("open", "high", "low", "close"))


def _dates(df) -> list:
    return [pd.Timestamp(x).normalize().tz_localize(None) if getattr(pd.Timestamp(x), "tzinfo", None) is not None else pd.Timestamp(x).normalize() for x in df.index]


def _side_bars(df, s: int) -> tuple:
    o, h, l, c = _ohlc(df)
    if s > 0:
        return o, h, l, c
    return -o, -l, -h, -c                                  # (open, high, low, close) of the mirrored market


# --------------------------------------------------------------------------------------------------------------
# helpers: ladders, trails
# --------------------------------------------------------------------------------------------------------------

def four_h_trail(h4, side: int, entry: float, objective: float, start: int = 0, trail_from: float = 0.75, tick: float = 0.0) -> np.ndarray:
    """X5-swing-final-exit-4h-trail (cc06_008 ~00:17:10): the stop level per 4h bar (NaN until the trail starts). From the first bar whose progress (best price so far, as a share of |objective - entry|)
    reaches `trail_from`, the stop is one tick beyond the most recent CONFIRMED 3-bar 4h swing low (high for a short) formed since `start`, and it only ratchets in the trade direction. The value at bar j
    is known at j's close (used from bar j+1)."""
    o, hi, lo, c = _side_bars(h4, side)
    e, t = side * entry, side * objective
    dist = t - e
    n = len(hi)
    out = np.full(n, NAN)
    ph, pl = L.pivots(hi, lo, 1)
    best = -np.inf
    stop = -np.inf
    started = False
    for j in range(start, n):
        best = max(best, hi[j])
        if dist > 0 and (best - e) / dist >= trail_from:
            started = True
        if started:
            cand = [q.price for q in pl if q.known <= j and q.i >= start]
            if cand:
                stop = max(stop, cand[-1] - tick)
            if stop > -np.inf:
                out[j] = side * stop
    return out


def htf_array_ladder(entry: float, target: float, arrays: dict, fracs=(0.3, 0.25, 0.2), keep: float = 0.25) -> list:
    """X3-swing-htf-array-scaleout (cc06_003 ~00:23:00): the swing ladder. `arrays` = {"4h": [levels], "D": [...], "W": [...]} (the opposing premium arrays for a long, discount arrays for a short, as
    prices); rungs are the 4h, then daily, then weekly arrays between entry and the monthly `target`, in price order; sizes `fracs` (0.3 / 0.25 / 0.2, sum 0.75) so that `keep` (25 %) is left once the
    weekly array is reached and rides to the target (the last rung). Other rung counts share (1 - keep) equally [our interpretation]. Returns [(level, fraction of the original size)], target last."""
    s = 1 if target >= entry else -1
    lv = []
    for tf in ("4h", "D", "W"):
        for x in arrays.get(tf, ()):
            if (x - entry) * s > 0 and (target - x) * s > 0:
                lv.append((float(x), tf))
    lv.sort(key=lambda r: (r[0] - entry) * s)
    n = len(lv)
    if n == 3 and len(fracs) == 3 and abs(sum(fracs) - (1 - keep)) < 1e-9:
        fr = list(fracs)
    elif n:
        fr = [(1 - keep) / n] * n
    else:
        fr = []
    return [(x, f) for (x, _), f in zip(lv, fr)] + [(float(target), 1 - sum(fr))]


def rel_eq_rungs(h4: pd.DataFrame, side: int, entry: float, target: float, tol: float, frac: float = 0.25, max_total: float = 0.75) -> list:
    """M17-swing-horizon (cc06_004 ~00:30:09, cc06_005 ~00:21:27): the intermediate pools of a swing - the 4h relative equal highs (lows for a short) between the entry and the target, each a partial of
    `frac` of the original size (the rest is held to the HTF array; the partials never exceed `max_total` together) [our interpretation of the sizes]. `tol` = the equality tolerance. Returns
    [(level, fraction)] in price order, ready for the entries' `rungs`."""
    o, hi, lo, c = _side_bars(h4, side)
    ph, _ = L.pivots(hi, lo, 1)
    lv = sorted(x for x in L.equal_levels([q.price for q in ph], tol) if side * entry < x < side * target)
    out, tot = [], 0.0
    for x in lv:
        f = min(frac, max_total - tot)
        if f <= 1e-12:
            break
        out.append((float(side * x), float(f)))
        tot += f
    return out


def opp_ob_ladder(monthly: pd.DataFrame, entry: float, side: int, mt_mode: str = "body", eq_tol: float = 0.0) -> list:
    """X1-swing-opposing-ob-ladder (cc06_006 ~00:26:29): a swing short at a monthly premium array aims at (T1) the MT of the nearest monthly last down-close candle BELOW the entry - even if it was
    touched once - and (T2) that candle's low. The mirror (long) uses the nearest up-close candle above, its body MT then its high. `monthly` = monthly bars (open/high/low/close). `mt_mode` "body" =
    (open + close) / 2, "range" = (high + low) / 2. A neighbouring monthly low within `eq_tol` of T2 (relative equal lows) is reported as `eq_neighbor` (T2 stays the candle's low). Returns
    [(T1, "mt"), (T2, "low" | "high")] or []."""
    o, h, l, c = _ohlc(monthly)
    n = len(c)
    for j in range(n - 1, -1, -1):
        if side < 0 and c[j] < o[j] and max(o[j], c[j]) < entry:
            t1 = (o[j] + c[j]) / 2 if mt_mode == "body" else (h[j] + l[j]) / 2
            nb = [l[q] for q in (j - 1, j + 1) if 0 <= q < n and abs(l[q] - l[j]) <= eq_tol and eq_tol > 0]
            r = [(float(t1), "mt"), (float(l[j]), "low")]
            if nb:
                r.append((float(nb[0]), "eq_neighbor"))
            return r
        if side > 0 and c[j] > o[j] and min(o[j], c[j]) > entry:
            t1 = (o[j] + c[j]) / 2 if mt_mode == "body" else (h[j] + l[j]) / 2
            nb = [h[q] for q in (j - 1, j + 1) if 0 <= q < n and abs(h[q] - h[j]) <= eq_tol and eq_tol > 0]
            r = [(float(t1), "mt"), (float(h[j]), "high")]
            if nb:
                r.append((float(nb[0]), "eq_neighbor"))
            return r
    return []


def donchian_stops(lows, j: int, progress: float, trail_switch: float = 0.5, buffer: float = 0.0) -> float:
    """new-position-40-20-day-trail (cc05_018 ~00:05:52): the long stop at the close of day j - below the lowest low of the last 40 trading days (the trade day included), or of the last 20 once
    `progress` >= `trail_switch`, less a buffer. (The caller ratchets; shorts pass negated highs.)"""
    n = 20 if progress >= trail_switch else 40
    return float(np.min(lows[max(0, j - n + 1):j + 1])) - buffer


# --------------------------------------------------------------------------------------------------------------
# the replay
# --------------------------------------------------------------------------------------------------------------

DEFAULT_CFG = dict(swing_be_r=1.5, t1_r=1.0, swing_p1=0.25, swing_trail_from=0.75, trail_switch=0.5, pos_buffer_frac=0.04, readd_frac=0.5, tick=0.0, eq_buffer=0.0, eq_pullback_r=0.05,
                   swing_label_days=10, expect_days=30)


def _replay(bars: pd.DataFrame, daily_pos: dict, df_daily: pd.DataFrame, e: dict, mode: str, trail: str, ladder, readd: bool, confirm4h: bool, max_hold_days, cfg: dict) -> dict:
    """One trade. `bars` are the simulation bars (daily, or 4h when a 4h trail / confirmation is used); `e` the entry dict (see swing_mgmt_study)."""
    s = int(e["side"])
    o, hi, lo, c = _side_bars(bars, s)
    ts = list(bars.index)
    bdate = [pd.Timestamp(x).tz_localize(None).normalize() if getattr(pd.Timestamp(x), "tzinfo", None) is not None else pd.Timestamp(x).normalize() for x in ts]
    E, S0, T = s * float(e["entry"]), s * float(e["stop"]), s * float(e["target"])
    R = E - S0
    D = T - E
    i0 = int(e["i"])                                       # the entry session (daily position)
    origin = s * float(e.get("origin", e["entry"]))
    tick = cfg["tick"]
    size, avg, real = 1.0, E, 0.0
    stop = S0
    p1_done = False
    p1_size = 0.0
    events: list = []
    day_of = [daily_pos.get(d_, None) for d_ in bdate]
    start = next((j for j, k_ in enumerate(day_of) if k_ is not None and k_ > i0), len(ts))
    # rungs
    rungs: list = []
    if ladder is not None:
        rungs = [(s * float(x), float(f)) for x, f in (e.get("rungs") or ())]
    elif mode == "thirds":
        rungs = [(E + cfg["swing_p1"] * D, cfg["swing_p1"])]
    rungs = sorted(r_ for r_ in rungs if r_[0] < T - 1e-12)             # (a rung at the objective is the final exit itself)
    rung_done = [False] * len(rungs)
    opp = sorted(s * float(x) for x in (e.get("opp_arrays") or ())) if readd else []
    opp_done = [False] * len(opp)
    readd_wait = 0.0                                       # size waiting to be re-added
    half_j = None                                          # thirds: the bar that first reached 0.5 D
    thirds_readd = False
    readd_lv = NAN
    best = E
    t1 = E + cfg["t1_r"] * R if e.get("t1") is None else s * float(e["t1"])
    t1_hit = False
    third_hit = False
    hmid = NAN
    phase = 1
    eq = (E + T) / 2
    exceeded_eq = False
    exceeded_hmid = False
    pb_eq = False
    pb_hm = False
    run_hi = -np.inf
    # 4h trail pivots (side space)
    _ph, pl = L.pivots(hi, lo, 1) if trail in ("4h", "phased") or confirm4h or mode == "thirds" else ([], [])
    tr_stop = -np.inf
    # 4h arrays (confirm4h)
    zones = [(s * float(a[0]), s * float(a[1])) for a in (e.get("h4_arrays") or ())]
    zones = [(min(a, b), max(a, b)) for a, b in zones]
    z_touch = [None] * len(zones)                          # the highest high since the touch, or None
    z_thru = [False] * len(zones)
    z_failed = [False] * len(zones)
    leg_low = E
    exit_reason, exit_j = "open", None
    stop_path: list = []
    for j in range(start, len(ts)):
        kd = day_of[j]
        day_n = (kd - i0) if kd is not None else 0
        # 1. the stop (adverse first)
        if lo[j] <= stop:
            px = min(stop, o[j])
            real += size * (px - avg) / R
            exit_reason = "stop" if abs(stop - S0) < 1e-9 else ("be" if abs(stop - E) < 1e-9 else "trail")
            size, exit_j = 0.0, j
            events.append((ts[j], exit_reason, px))
            break
        leg_low = min(leg_low, lo[j])
        # 2. the 4h failure (the retrace measured on bars completed before this one)
        if confirm4h:
            for q, (zl, zh) in enumerate(zones):
                if z_touch[q] is not None and not z_failed[q] and not z_thru[q]:
                    thr = z_touch[q] - 0.5 * (z_touch[q] - leg_low)
                    if lo[j] <= thr:
                        cl = size / 2 if size > 0 else 0.0
                        px = min(thr, o[j])
                        real += cl * (px - avg) / R
                        size -= cl
                        z_failed[q] = True
                        events.append((ts[j], "4h_fail", px))
        # 3. the re-add (a limit below, placed after a partial)
        if readd and readd_wait > 0 and lo[j] <= readd_lv:
            px = min(readd_lv, o[j])
            avg = (avg * size + px * readd_wait) / (size + readd_wait)
            size += readd_wait
            events.append((ts[j], "readd", px))
            readd_wait = 0.0
        # 4. the favourable side: rungs, opposing arrays, the target
        for q, (lv, fr) in enumerate(rungs):
            if not rung_done[q] and hi[j] >= lv and size > 0:
                cl = min(size, fr)
                px = max(lv, o[j])
                real += cl * (px - avg) / R
                size -= cl
                rung_done[q] = True
                if mode == "thirds" and ladder is None:
                    p1_done, p1_size = True, cl
                events.append((ts[j], "partial", px))
        for q, lv in enumerate(opp):
            if not opp_done[q] and hi[j] >= lv and size > 0 and lv < T:
                cl = min(size, cfg["readd_frac"])
                px = max(lv, o[j])
                real += cl * (px - avg) / R
                size -= cl
                opp_done[q] = True
                readd_wait += cl
                rl = e.get("entry_open")
                readd_lv = s * float(rl) if rl is not None else E
                events.append((ts[j], "partial_opp", px))
        if hi[j] >= T and size > 0:
            px = max(T, o[j])
            real += size * (px - avg) / R
            size, exit_j, exit_reason = 0.0, j, "target"
            events.append((ts[j], "target", px))
            break
        # 5. bookkeeping at the close (acts from the next bar)
        best = max(best, hi[j])
        if confirm4h:
            for q, (zl, zh) in enumerate(zones):
                if z_thru[q]:
                    continue
                if hi[j] > zh:
                    z_thru[q] = True
                    z_touch[q] = None
                elif hi[j] >= zl:
                    z_touch[q] = hi[j] if z_touch[q] is None else max(z_touch[q], hi[j])
        if mode == "be_t1" and not readd:                  # (readd: the stop stays at the initial level until swing_be_r, whatever the BE mode)
            if hi[j] >= t1:
                t1_hit = True
                stop = max(stop, E)
        elif mode == "no_be" or (readd and mode == "be_t1"):
            if (best - E) / R >= cfg["swing_be_r"]:
                stop = max(stop, E)
        elif mode == "thirds":
            if hi[j] >= E + D / 3:
                third_hit = True
            if third_hit and p1_done:
                stop = max(stop, E)                        # BE only if the first partial was taken, never before
            if half_j is None and hi[j] >= E + 0.5 * D:
                half_j = j
            if half_j is not None and p1_done and not thirds_readd and size > 0:
                if any(q.known <= j and q.i > half_j for q in pl):          # the first retrace low (a confirmed 3-bar swing low) after 0.5 D: re-add the quarter at that bar's close
                    avg = (avg * size + c[j] * p1_size) / (size + p1_size)
                    size += p1_size
                    thirds_readd = True
                    events.append((ts[j], "readd", c[j]))
        if readd and (best - E) / R >= cfg["swing_be_r"]:
            stop = max(stop, E)
        if trail == "donchian":
            prog = (c[j] - origin) / (T - origin) if T != origin else 0.0
            dl = s * df_daily["low"].values.astype(float) if s > 0 else -df_daily["high"].values.astype(float)
            kk = daily_pos.get(bdate[j])
            if kk is not None:
                cand = donchian_stops(dl, kk, prog, cfg["trail_switch"], cfg["pos_buffer_frac"] * R)
                stop = max(stop, cand)
        elif trail == "4h":
            if dist_ok(D) and (best - E) / D >= cfg["swing_trail_from"]:
                cand = [q.price for q in pl if q.known <= j and q.i >= start]
                if cand:
                    tr_stop = max(tr_stop, cand[-1] - tick)
                    stop = max(stop, tr_stop)
        elif trail == "phased":
            cand = [q.price for q in pl if q.known <= j and q.i >= start]
            cand_stop = max(stop, (cand[-1] - tick)) if cand else stop
            if phase == 1:
                cap = eq - cfg["eq_buffer"]
                if exceeded_eq and lo[j] <= eq + cfg["eq_pullback_r"] * R:         # the pullback into EQ after price first exceeded it (earlier bars)
                    pb_eq, hmid, phase = True, run_hi, 2
                stop = max(stop, min(cand_stop, cap))
            elif phase == 2:
                cap = hmid - cfg["eq_buffer"]
                if exceeded_hmid and lo[j] <= hmid:                                # the retest of the high made near EQ, after it was exceeded
                    pb_hm, phase = True, 3
                stop = max(stop, min(cand_stop, cap))
            else:
                stop = max(stop, cand_stop)
            if hi[j] > eq:
                exceeded_eq = True
            if phase == 2 and hi[j] > hmid:
                exceeded_hmid = True
            run_hi = max(run_hi, hi[j])
        stop_path.append(stop)
        # 6. the horizon
        if max_hold_days is not None and kd is not None and day_n >= max_hold_days:
            real += size * (c[j] - avg) / R
            size, exit_j, exit_reason = 0.0, j, "horizon"
            events.append((ts[j], "horizon", c[j]))
            break
    if size > 0 and exit_j is None:
        last = len(ts) - 1
        if last >= start:
            real += size * (c[last] - avg) / R
            exit_j, exit_reason = last, "end"
            events.append((ts[last], "end", c[last]))
    kd_end = day_of[exit_j] if exit_j is not None else None
    held = int(kd_end - i0) if kd_end is not None else 0
    lab = "short_term" if held < cfg["swing_label_days"] else "swing"
    return dict(entry_i=i0, side=s, entry=float(e["entry"]), stop0=float(e["stop"]), target=float(e["target"]), r=float(real), reason=exit_reason, days_held=held, label=lab, p1_done=p1_done,
                max_progress=float((best - E) / D) if D > 0 else NAN, eq_pullback=pb_eq, hmid_retest=pb_hm, n_events=len(events), events=events, final_size=float(size), stop_path=[s * x for x in stop_path])


def dist_ok(d: float) -> bool:
    return d > 0


def swing_mgmt_study(df_daily: pd.DataFrame, entries: list, mode: str = "be_t1", trail: str = "none", ladder=None, readd: bool = False, confirm4h: bool = False,
                     max_hold_days=None, df_4h: pd.DataFrame | None = None, **kw) -> pd.DataFrame:
    """X4-be-by-timeframe / X4-swing-stop-thirds-partial-quarter / X5-swing-final-exit-4h-trail / X5-swing-eq-stop-runs / new-position-40-20-day-trail / new-htf-partial-and-readd /
    new-position-hold-horizon / M17-swing-horizon / B6-swing-in-trade-confirmation / X3-swing-htf-array-scaleout / X1-swing-opposing-ob-ladder (cc06_008, cc05_018, 098, ...): replays swing /
    position entries on daily bars (4h bars for the 4h trail and the 4h confirmation) with pluggable management. `entries` = dicts {i: daily position of the entry session, side, entry, stop, target
    [, origin, t1, rungs [(level, fraction)], opp_arrays [levels], entry_open, h4_arrays [(lo, hi)]]}; management starts on the session after the entry.
      mode    "be_t1"  BE as soon as the first target `t1` (default 1R) is touched | "no_be"  the initial stop until the position is `swing_be_r` (1.5R) in profit, then BE | "thirds"  a partial
              `swing_p1` (25 %) at 0.25 D (D = |objective - entry|), the stop frozen until D/3 and then BE only if that partial was taken
      trail   "none" | "4h" (from `swing_trail_from` of D, one tick under the last confirmed 4h swing low, ratchet only) | "phased" (the stop stays under EQ until the first pullback to EQ, then under the
              high made near EQ until its retest, then the 4h trail) | "donchian" (below the lowest low of the last 40 sessions, the last 20 from `trail_switch` of the way; no BE)
      ladder  None | any value: use the entries' `rungs` (see htf_array_ladder / opp_ob_ladder)
      readd   at each opposing array (`opp_arrays`) close `readd_frac`, re-add the same size at `entry_open` (default the entry); BE only from `swing_be_r`
      confirm4h  close half when a 4h array above holds (touched, not traded through) and the price retraces more than 50 % of the leg from the lowest low to the touch high
      max_hold_days  close at the close of that trading day (swing mode 22, position 63); the result's label is "short_term" below `swing_label_days` (10) days held
    Returns one row per trade: r (in initial-risk units, size weighted), reason, days_held, label, ... The 4h modes need `df_4h`."""
    cfg = dict(DEFAULT_CFG)
    cfg.update(kw)
    if mode not in ("be_t1", "no_be", "thirds"):
        raise ValueError(f"mode {mode!r}")
    if trail not in ("none", "4h", "phased", "donchian"):
        raise ValueError(f"trail {trail!r}")
    dd = _dates(df_daily)
    daily_pos = {d_: k for k, d_ in enumerate(dd)}
    use4 = trail in ("4h", "phased") or confirm4h
    if use4 and df_4h is None:
        raise ValueError("the 4h trail / phased trail / 4h confirmation need df_4h")
    bars = df_4h if use4 else df_daily
    rows = [_replay(bars, daily_pos, df_daily, e, mode, trail, ladder, readd, confirm4h, max_hold_days, cfg) for e in entries]
    return pd.DataFrame(rows)


def days_to_target_report(res: pd.DataFrame, expect_days: int = 30) -> dict:
    """new-position-hold-horizon (cc05_007 ~00:06:55): the distribution of days-to-target of a study result against the ~30-day expectation (half the 63-day horizon)."""
    hit = res[res.reason == "target"]
    return dict(n=int(len(res)), n_target=int(len(hit)), median_days=float(hit.days_held.median()) if len(hit) else NAN, expect_days=expect_days,
                share_within_expect=float((hit.days_held <= expect_days).mean()) if len(hit) else NAN, n_horizon=int((res.reason == "horizon").sum()))


# --------------------------------------------------------------------------------------------------------------
# M17-daily-limit-repeat-to-weekly
# --------------------------------------------------------------------------------------------------------------

def daily_limit_model(df_daily: pd.DataFrame, weekly_arrays: list, bias=None, quick_bars: int = 2, tick: float = 0.0, side: int = 1) -> pd.DataFrame:
    """M17-daily-limit-repeat-to-weekly (cc05_017 ~00:09:16): while the monthly / weekly bias is bullish (`bias`: a date-indexed Series of +1 / -1, or None = always) and a weekly bearish array above
    (`weekly_arrays` = [(bottom, top, known_pos)], known_pos = the first daily position it may be used) is untouched, each completed down-close daily candle arms a buy limit at its close (it
    replaces an unfilled earlier one [our interpretation: the order lifetime is unstated]; it fills when a later bar trades `tick` through it). Every fill is its own position: target = the nearest
    array's bottom, stop below the week's low so far (the signal candle's week), "suspect" when no close above the fill price within `quick_bars` sessions. Arming stops once the array is touched.
    side=-1 mirrors (up-close candle, sell limit, a weekly bullish array below). Returns one row per fill: arm_i, fill_i, limit, stop, target, suspect, exit, r (prices in the market's own units)."""
    o, h, l, c = _side_bars(df_daily, side)
    n = len(c)
    dd = _dates(df_daily)
    wk = np.asarray(pd.PeriodIndex(dd, freq="W-FRI").astype(str))
    live = [((float(a[0]) if side > 0 else -float(a[1])), int(a[2])) for a in weekly_arrays]
    bsr = None if bias is None else {pd.Timestamp(k).normalize(): int(v) for k, v in bias.items()}
    order = None                                           # (limit, arm_i, stop, target)
    pos: list = []
    for j in range(n):
        if order is not None and j > order[1] and l[j] <= order[0] - tick:
            pos.append(dict(arm_i=order[1], fill_i=j, limit=order[0], fill=min(order[0], o[j]), stop=order[2], target=order[3], exit=None, r=None, up=False, suspect=None))
            order = None
        for q in pos:
            if q["exit"] is not None:
                continue
            risk = q["fill"] - q["stop"]
            if l[j] <= q["stop"]:
                q["exit"], q["r"] = "stop", -1.0
            elif h[j] >= q["target"]:
                q["exit"], q["r"] = "target", (q["target"] - q["fill"]) / risk
            elif j > q["fill_i"] and j - q["fill_i"] <= quick_bars and c[j] > q["fill"]:
                q["up"] = True
            if q["exit"] is None and j - q["fill_i"] >= quick_bars and q["suspect"] is None:
                q["suspect"] = not q["up"]
        known = [a for a in live if a[1] <= j]
        hit = [a for a in known if h[j] >= a[0]]
        if hit:
            live = [a for a in live if a not in hit]
            order = None                                   # the array was touched: arming stops
            continue
        if not known:
            continue
        tgt = min(a[0] for a in known)
        okb = True if bsr is None else bsr.get(dd[min(j + 1, n - 1)], bsr.get(dd[j], 0)) == side
        if c[j] < o[j] and okb:
            wl = float(np.min(l[[q for q in range(j + 1) if wk[q] == wk[j]]]))
            order = (float(c[j]), j, wl - tick, float(tgt))
    rows = []
    for q in pos:
        if q["exit"] is None:
            q["exit"] = "open"
            q["r"] = (c[-1] - q["fill"]) / (q["fill"] - q["stop"])
        if q["suspect"] is None:
            q["suspect"] = not q["up"]
        q.pop("up")
        rows.append(q)
    out = pd.DataFrame(rows)
    if side < 0 and len(out):
        for k in ("limit", "fill", "stop", "target"):
            out[k] = -out[k]
    return out


def lo_ok(low: float, limit: float, tick: float) -> bool:
    return low <= limit - tick


# --------------------------------------------------------------------------------------------------------------
# T11-weekly-template-hold
# --------------------------------------------------------------------------------------------------------------

def weekly_template_study(df_daily: pd.DataFrame, signals: list) -> pd.DataFrame:
    """T11-weekly-template-hold (cc07_003 ~00:13:14), weekly-template mode only: a Tuesday / Wednesday entry at the weekly extreme (`signals` = [{i: daily position of the entry session, side, entry,
    stop, target}]) is held across days until the target, the stop, or Friday's close [weekend flattening is our assumption]. The entry session is not managed (no intraday data); the trade is managed
    from the next session. Reports the hold time, the outcome and the same-day flatten (the entry session's close) for comparison."""
    o, h, l, c = _ohlc(df_daily)
    dd = _dates(df_daily)
    wk = np.asarray(pd.PeriodIndex(dd, freq="W-FRI").astype(str))
    rows = []
    for e in signals:
        i0, s = int(e["i"]), int(e["side"])
        E, S0, T = float(e["entry"]), float(e["stop"]), float(e["target"])
        R = abs(E - S0)
        flat = s * (c[i0] - E) / R
        reason, r, jx = "friday_close", None, i0
        for j in range(i0 + 1, len(c)):
            if wk[j] != wk[i0]:
                break
            jx = j
            stop_hit = (l[j] <= S0) if s > 0 else (h[j] >= S0)
            tgt_hit = (h[j] >= T) if s > 0 else (l[j] <= T)
            if stop_hit:
                reason, r = "stop", -1.0
                break
            if tgt_hit:
                reason, r = "target", s * (T - E) / R
                break
        if r is None:
            r = s * (c[jx] - E) / R
        rows.append(dict(entry_i=i0, side=s, hold_days=int(jx - i0), reason=reason, r_hold=float(r), r_flatten=float(flat)))
    return pd.DataFrame(rows)


def weekly_template_signals(df_daily: pd.DataFrame, table: pd.DataFrame, rr: float = 2.0) -> list:
    """The Tuesday / Wednesday weekly-extreme entries of the weekly template: in a week whose first table row reads weekly bias v (`wk_bias`), on a Tuesday or Wednesday row the previous session made
    the week's extreme AGAINST v so far (the high of a bearish week); entry = that row's session open, stop = the extreme, target = the table's weekly draw (`wk_draw_dn` / `wk_draw_up`) else `rr` R.
    [our interpretation of 'the weekly extreme']"""
    o, h, l, c = _ohlc(df_daily)
    dd = _dates(df_daily)
    wk = np.asarray(pd.PeriodIndex(dd, freq="W-FRI").astype(str))
    pos = {d_: k for k, d_ in enumerate(dd)}
    out = []
    first: dict = {}
    for ix, row in table.iterrows():
        k = pos.get(pd.Timestamp(ix).normalize())
        if k is None or k < 1:
            continue
        first.setdefault(wk[k], int(row.get("wk_bias", 0) or 0))
        v = first[wk[k]]
        if not v or dd[k].weekday() not in (1, 2) or wk[k - 1] != wk[k]:
            continue
        wi = [q for q in range(k) if wk[q] == wk[k]]
        if v < 0 and h[k - 1] >= max(h[q] for q in wi):
            ext, side = float(h[k - 1]), -1
        elif v > 0 and l[k - 1] <= min(l[q] for q in wi):
            ext, side = float(l[k - 1]), 1
        else:
            continue
        E = float(o[k])
        R = abs(ext - E)
        if R <= 0:
            continue
        dr = row.get("wk_draw_dn" if side < 0 else "wk_draw_up", NAN)
        T = float(dr) if dr == dr and ((E - float(dr)) * side > 0) else E + side * rr * R
        out.append(dict(i=k - 0, side=side, entry=E, stop=ext, target=T))
    return out


def r_distribution(res: pd.DataFrame) -> dict:
    """The R distribution of a study result (the 'report the R distribution' of items 96 / 100 / 155): count, win rate, mean, median and the quartiles of `r`."""
    if not len(res):
        return dict(n=0, win_rate=NAN, mean_r=NAN, median_r=NAN, q25=NAN, q75=NAN)
    r = res.r.astype(float).dropna()
    if not len(r):
        return dict(n=0, win_rate=NAN, mean_r=NAN, median_r=NAN, q25=NAN, q75=NAN)
    return dict(n=int(len(r)), win_rate=float((r > 0).mean()), mean_r=float(r.mean()), median_r=float(r.median()), q25=float(r.quantile(0.25)), q75=float(r.quantile(0.75)))
