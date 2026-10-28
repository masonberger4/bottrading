"""Caption-gap pass, package bias_htf#7/7: the STUDY-ONLY items (research functions, no live branch, nothing here reads Params).

models_setups_entries.md items 171-174 + session_day_week_stops_frequency.md item 26     -> `osok_core` / `osok` / `origin_report` (One Shot One Kill: weekly holding on 1h execution)
session_day_week_stops_frequency.md items 6, 38                                           -> `pick_reentry` / `swing_reentry_study` / `reentry_report`, `trend_tired`
session_day_week_stops_frequency.md items 24, 25                                          -> `position_freq`, `swing_frequency`
stops_sizing_scaling_in.md items 5, 7, 22 (item 66's helper is `htf.swing_stop`)           -> `osok_scale_in`, `swing_readd`, `daily_stop_model`

Every function is a pure function of the bars it is given. A bar is used only after it closes: orders are armed at a bar's close and fill from the NEXT bar; when a stop and a target are both inside one bar the
stop is taken first; arrays are used only from their `t_known` (the end of the bar that completes them). All prices are handled in "side space" (a short is a long on negated prices). Thresholds the sources
never give are marked [our interpretation]. Wrapper names live in study.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import htf
from . import levels as L

NAN = float("nan")
KILL_ZONES = ((120, 300), (420, 600))            # London 02:00-05:00 and New York 07:00-10:00 (minutes of the NY day)
HTF_ORDER = ("M", "W", "D", "4h")                # the container preference: the higher timeframe is the origin


# --------------------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------------------

def _naive_idx(idx) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize(None) if idx.tz is not None else idx


def arr(tf: str, kind: str, top: float, bottom: float, t_known, ce: float | None = None, typ: str = "fvg") -> dict:
    """An array record: timeframe, kind ("bull" / "bear"), edges, CE and the time from which it can be used."""
    return dict(tf=tf, kind=kind, top=float(top), bottom=float(bottom), ce=float((top + bottom) / 2.0 if ce is None else ce), t_known=pd.Timestamp(t_known), typ=typ)


def side_arr(a: dict, d: int) -> dict:
    """The array in side space (d = +1 unchanged; -1 negated: kind flipped, top / bottom swapped)."""
    if d > 0:
        return a
    return dict(a, kind="bear" if a["kind"] == "bull" else "bull", top=-a["bottom"], bottom=-a["top"], ce=-a["ce"])


def side_bars(df: pd.DataFrame, d: int) -> tuple:
    o, h, l, c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
    return (o, h, l, c) if d > 0 else (-o, -l, -h, -c)


def _cmp_ts(a, b) -> bool:
    """a <= b for timestamps that may be tz-aware or naive (compared as wall-clock)."""
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    a = a.tz_localize(None) if a.tzinfo is not None else a
    b = b.tz_localize(None) if b.tzinfo is not None else b
    return a <= b


def _wk(ts) -> str:
    """The trading-week id of a timestamp (a session belongs to the day its time + 7h falls on)."""
    t = pd.Timestamp(ts)
    t = t.tz_localize(None) if t.tzinfo is not None else t
    return str((t + pd.Timedelta(hours=7)).to_period("W-FRI"))


def _label_wd(ts) -> int:
    t = pd.Timestamp(ts)
    t = t.tz_localize(None) if t.tzinfo is not None else t
    return int((t + pd.Timedelta(hours=7)).weekday())


# --------------------------------------------------------------------------------------------------------------
# M17-osok-*: One Shot One Kill
# --------------------------------------------------------------------------------------------------------------

def build_arrays(df: pd.DataFrame) -> list:
    """The D / W / M arrays (from the sessions of the minute frame `df`) and the 4h arrays as array records: an array is usable from the end of the bar that completes it (a session's 17:00, the week's / month's
    last session 17:00, the 4h bar's end). FVGs and order blocks (htf._arrays)."""
    from .strategy import htf_bars
    tz = df.index.tz
    d = htf.sessions(df)
    w = htf.weeks(d)
    m = htf.months(d)
    pos = {t: k for k, t in enumerate(d.index)}

    def tk(label):
        return pd.Timestamp(label).normalize().tz_localize(tz) + pd.Timedelta(hours=17)
    out = []
    for tf, fr, kn in (("D", d, lambda i: i + 1), ("W", w, lambda i, _w=[pos[t] + 1 for t in w["last"]]: _w[i]), ("M", m, lambda i, _m=[pos[t] + 1 for t in m["last"]]: _m[i])):
        o, h, l, c = (fr[k].values.astype(float) for k in ("open", "high", "low", "close"))
        for a in htf._arrays(o, h, l, c, tf, kn):
            if a.known - 1 < len(d):
                out.append(arr(tf, a.kind, a.top, a.bottom, tk(d.index[a.known - 1]), a.ce, a.typ))
    b4 = htf_bars(df, 240)
    o, h, l, c = (b4[k].values.astype(float) for k in ("open", "high", "low", "close"))
    for a in htf._arrays(o, h, l, c, "4h", lambda i: i + 1):
        out.append(arr("4h", a.kind, a.top, a.bottom, b4["end"].iloc[a.known - 1], a.ce, a.typ))
    return out


def monthly_direction(arrays: list, df: pd.DataFrame):
    """(callable t -> (dir, missed)) the monthly frame of One Shot One Kill (cc07_001 ~00:01:14 / ~00:17:35). At time t, from the last COMPLETED monthly candle and the most recent monthly array known at t:
    inside / beyond a bearish array (the close at or under its top) = -1, a bullish one (the close at or over its bottom) = +1; missed = the close already left the array's far side (under a bearish
    array's bottom / over a bullish one's top): the array no longer trades, only the direction stays; with no array the candle's colour. [our interpretation]"""
    d = htf.sessions(df)
    m = htf.months(d)
    tz = df.index.tz
    ends = [pd.Timestamp(t).normalize().tz_localize(tz) + pd.Timedelta(hours=17) for t in m["last"]]
    mo, mc = m["open"].values.astype(float), m["close"].values.astype(float)
    ma = sorted((a for a in arrays if a["tf"] == "M"), key=lambda a: a["t_known"])

    def f(t):
        k = sum(1 for e in ends if _cmp_ts(e, t)) - 1
        if k < 0:
            return 0, False
        known = [a for a in ma if _cmp_ts(a["t_known"], t)]
        c = mc[k]
        if known:
            a = known[-1]
            if a["kind"] == "bear":
                return (-1, c < a["bottom"]) if c <= a["top"] or c < a["bottom"] else (int(np.sign(c - mo[k])), False)
            return (1, c > a["top"]) if c >= a["bottom"] or c > a["top"] else (int(np.sign(c - mo[k])), False)
        return int(np.sign(c - mo[k])), False
    return f


def _dir_at(direction, t) -> tuple:
    if callable(direction):
        r = direction(t)
        return (int(r[0]), bool(r[1])) if isinstance(r, tuple) else (int(r), False)
    return int(direction), False


def osok_core(h1: pd.DataFrame, arrays: list, direction, target_tf: str = "D", min_rr: float = 1.0, pad: float = 0.0, days: tuple = (0, 1, 2), h1_alone: bool = False,
              kill_zones: tuple = KILL_ZONES, flat_week_end: bool = True, max_wait_bars: int = 24) -> list:
    """One Shot One Kill on 1h bars (cc07_001 ~00:16:17 / ~00:22:41; cc07_006 ~00:20:04). `h1` = the 1h bars (tz-aware start index; open / high / low / close), `arrays` = array records of the weekly, daily,
    4h (and monthly) frames, `direction` = +1 / -1 or a callable t -> (dir, missed_monthly) (see `monthly_direction`).
    A bearish frame (a bullish one mirrors it): a 1h bearish FVG completes INSIDE a live premium array of the weekly / daily / 4h (/ monthly unless the monthly array was missed - then it only sets the
    direction) -> a sell limit at the 1h FVG's CE, stop above the 1h FVG and the HTF array's top (+pad), target = the nearest UNTOUCHED opposing array of `target_tf` ("D": the daily discount array of item
    174; "W": the weekly one of item 172). Orders are armed only on Mon-Wed sessions (`days`), fill only on Mon-Wed, are cancelled at the week's end and never use bars below 1h. `h1_alone`: a 1h FVG with no
    HTF array may be executed inside a kill zone (origin tf "1h"). Positions are flat by the week's last 1h bar. Returns trade dicts: side, entry/exit time and price, stop, target, exit_reason, origin_tf,
    htf (the container's edges), leg_id and seq (the number of the signal inside the leg of the same origin array: a leg ends when a trade reaches its target)."""
    n = len(h1)
    if n < 6:
        return []
    ts = list(h1.index)
    ends = [t + pd.Timedelta(minutes=60) for t in ts]
    wk = [_wk(t) for t in ts]
    fv = {}
    for d in (1, -1):
        O, H, Lw, C = side_bars(h1, d)
        fv[d] = [z for z in L.fvgs(H, Lw) if z.kind == "bull"]
    trades = []
    pend = None
    pos = None
    legs: dict = {}
    for j in range(n):
        d_here, missed = _dir_at(direction, ends[j])
        # ---- the open position / the pending order, on bar j (they were created at an earlier bar)
        if pos is not None:
            d = pos["d"]
            O, H, Lw, C = (x[j] for x in side_bars(h1, d))
            last_bar = (j + 1 >= n) or wk[j + 1] != wk[j]
            ex = None
            if Lw <= pos["stop"]:
                ex = (min(pos["stop"], O), "stop")
            elif H >= pos["target"]:
                ex = (O if O >= pos["target"] else pos["target"], "target")
            elif flat_week_end and last_bar:
                ex = (C, "week_end")
            if ex is not None:
                trades.append(_close_trade(pos, ts[j], ex, legs))
                pos = None
        elif pend is not None:
            d = pend["d"]
            O, H, Lw, C = (x[j] for x in side_bars(h1, d))
            if wk[j] != pend["wk"] or _label_wd(ts[j]) not in days or j - pend["armed"] > max_wait_bars or C < pend["stop"]:
                pend = None
            elif Lw <= pend["entry"]:
                fill = min(pend["entry"], O)
                pos = dict(pend, fill=fill, t_in=ts[j])
                pend = None
                if Lw <= pos["stop"]:                                  # the fill bar also reaches the stop: booked stopped (conservative)
                    trades.append(_close_trade(pos, ts[j], (min(pos["stop"], O), "stop"), legs))
                    pos = None
        # ---- a new setup completing at bar j
        if pos is None and pend is None and d_here and _label_wd(ts[j]) in days and wk[j] == _wk(ends[j] - pd.Timedelta(minutes=1)):
            s = _setup(h1, j, d_here, missed, arrays, fv[d_here], target_tf, min_rr, pad, ends, h1_alone, kill_zones, ts)
            if s is not None:
                s.update(d=d_here, armed=j, wk=wk[j], t_armed=ends[j])
                pend = s
    return trades


def _close_trade(pos: dict, t_out, ex: tuple, legs: dict) -> dict:
    d = pos["d"]
    key = pos["leg_key"]
    seq = legs.get(key, 0) + 1
    legs[key] = 0 if ex[1] == "target" else seq
    return dict(side=d, t_in=pos["t_in"], t_out=pd.Timestamp(t_out), entry=d * pos["fill"], exit=d * ex[0], stop=d * pos["stop"], target=d * pos["target"], exit_reason=ex[1],
                r=(ex[0] - pos["fill"]) / (pos["fill"] - pos["stop"]), origin_tf=pos["origin_tf"], htf=pos["htf"], seq=seq, leg=key)


def _setup(h1, j, d, missed, arrays, fvs, target_tf, min_rr, pad, ends, h1_alone, kill_zones, ts):
    zs = [z for z in fvs if z.i == j]
    if not zs:
        return None
    O, H, Lw, C = side_bars(h1, d)
    te = ends[j]
    z = zs[-1]
    sarr = [side_arr(a, d) for a in arrays if _cmp_ts(a["t_known"], te)]
    cont = []
    for a in sarr:
        if a["kind"] != "bull" or a["tf"] not in HTF_ORDER or (a["tf"] == "M" and missed):
            continue
        if not (z.top >= a["bottom"] - 1e-9 and z.bottom <= a["top"] + 1e-9):
            continue
        since = [q for q in range(j + 1) if _cmp_ts(a["t_known"], ends[q])]
        if since and C[since[0]:j + 1].min() < a["bottom"]:                # closed through its far edge: dead
            continue
        cont.append(a)
    origin = None
    if cont:
        cont.sort(key=lambda a: HTF_ORDER.index(a["tf"]))
        origin = cont[0]
        origin_tf = origin["tf"]
        htf_edges = tuple(sorted((origin["bottom"] * d, origin["top"] * d)))
        stop = min(z.bottom, origin["bottom"]) - pad
    elif h1_alone:
        m = int(pd.Timestamp(ts[z.i - 2 if z.i >= 2 else 0]).hour * 60 + pd.Timestamp(ts[z.i - 2 if z.i >= 2 else 0]).minute)
        if not any(a <= m < b for a, b in kill_zones):
            return None
        origin_tf = "1h"
        htf_edges = None
        stop = z.bottom - pad
    else:
        return None
    entry = float((z.top + z.bottom) / 2.0)
    tg = []
    for a in sarr:
        if a["kind"] == "bear" and a["tf"] == target_tf and a["bottom"] > entry:
            q0 = next((q for q in range(j + 1) if _cmp_ts(a["t_known"], ends[q])), None)
            if q0 is not None and H[q0:j + 1].max() < a["bottom"]:        # untouched
                tg.append(a["bottom"])
    if not tg or entry <= stop:
        return None
    target = min(tg)
    if (target - entry) / (entry - stop) < min_rr:
        return None
    key = (origin_tf, round(htf_edges[0], 6), round(htf_edges[1], 6)) if htf_edges else ("1h", round(float(z.bottom) * d, 6), round(float(z.top) * d, 6))
    return dict(entry=entry, stop=stop, target=target, origin_tf=origin_tf, htf=htf_edges, leg_key=key)


def osok(df: pd.DataFrame, direction=None, **kw) -> list:
    """`osok_core` on a minute frame: the arrays of `build_arrays`, the 1h bars of the frame and (when `direction` is None) the monthly frame of `monthly_direction`."""
    arrays = build_arrays(df)
    g = df.groupby(df.index.floor("60min"))
    h1 = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    return osok_core(h1, arrays, direction if direction is not None else monthly_direction(arrays, df), **kw)


def origin_report(trades: list, origin_tfs: tuple = ("M", "W", "D", "4h")) -> dict:
    """new-frequency-by-origin-tf (cc07_001 ~00:18:29): per origin timeframe, the legs (an origin array's consecutive signals up to the trade that reaches the target) and the signals before the target: {tf: dict(
    signals, legs, per_leg=[signals of each leg], mean_per_leg)}. A leg still open at the end counts with the signals so far."""
    out = {tf: dict(signals=0, legs=0, per_leg=[]) for tf in origin_tfs}
    cur: dict = {}
    for t in trades:
        tf = t["origin_tf"]
        if tf not in out:
            continue
        out[tf]["signals"] += 1
        cur[t["leg"]] = cur.get(t["leg"], 0) + 1
        if t["exit_reason"] == "target":
            out[tf]["per_leg"].append(cur.pop(t["leg"]))
            out[tf]["legs"] += 1
    for k, n in cur.items():
        out[k[0]]["per_leg"].append(n)
        out[k[0]]["legs"] += 1
    for tf, v in out.items():
        v["mean_per_leg"] = float(np.mean(v["per_leg"])) if v["per_leg"] else NAN
    return out


# --------------------------------------------------------------------------------------------------------------
# X13-swing-reentry-next-htf-array
# --------------------------------------------------------------------------------------------------------------

def pick_reentry(arrays: list, failed: list, below: float, te, closes_since=None) -> dict | None:
    """The next entry array after a swing long was stopped at `failed` (a list of failed array records; none is ever reused): the next LOWER untested 4h bullish array whose top is under `below` (the failed
    array's bottom); when the 4h has none, the nearest daily, then weekly, then monthly bullish array under `below`. Usable arrays are those known at `te`. 'Untested' (4h only) = `closes_since` (a
    callable array -> lowest low since it was known, or None for 'unknown') shows no trade into it; omitted = every 4h array counts as untested."""
    def key(a):
        return (a["tf"], round(a["top"], 6), round(a["bottom"], 6))
    bad = {key(a) for a in failed}
    pool = [a for a in arrays if a["kind"] == "bull" and _cmp_ts(a["t_known"], te) and key(a) not in bad and a["top"] < below]
    for tf in ("4h", "D", "W", "M"):
        c = [a for a in pool if a["tf"] == tf]
        if tf == "4h" and closes_since is not None:
            c = [a for a in c if (closes_since(a) is None or closes_since(a) > a["top"])]
        if c:
            return max(c, key=lambda a: a["top"])
    return None


def swing_reentry_study(h4: pd.DataFrame, arrays: list, bias: int = 1, reentry_max: int | None = None, void: str = "mw_far_edge", min_rr: float = 3.0, pad: float = 0.0, max_wait_bars: int = 18,
                        side: int = 1) -> list:
    """A swing long at a 4h discount array under a bullish M / W bias, with the re-entry cascade of cc06_003 / cc06_008 (a bearish bias / short mirrors it; `side`). The entry limit sits at the array's CE,
    the stop under its bottom (-pad), the target is the nearest opposing array above (any timeframe, known, not closed through) with at least `min_rr`. On a stop the original reasons are re-checked
    (the void test below), the failed array is never reused and the next order sits at `pick_reentry`'s array with HALF the previous size (size 0.5 ** failures). `reentry_max` (1 / 2 / 3 / None)
    caps the failures a sequence may take; `void="mw_far_edge"` ends a sequence when a 4h body closes beyond the far edge of the monthly / weekly array under the entry [our interpretation of the
    invalidation threshold]. Rows: seq, attempt, size, entry / exit, exit_reason, r (per unit risk), pnl_r (= size * r)."""
    O, H, Lw, C = side_bars(h4, side)
    n = len(C)
    ends = [t + pd.Timedelta(hours=4) for t in h4.index]
    sarr = [side_arr(a, side) for a in arrays]
    rows = []
    seq = 0
    j = 0
    while j < n - 2:
        # ---- start a sequence: the nearest untested 4h bullish array under the close
        cand = [a for a in sarr if a["tf"] == "4h" and a["kind"] == "bull" and _cmp_ts(a["t_known"], ends[j]) and a["top"] < C[j] and _untested(a, Lw, ends, j)]
        if bias <= 0 or not cand:
            j += 1
            continue
        cur = max(cand, key=lambda a: a["top"])
        seq += 1
        failed: list = []
        attempt = 0
        j0 = j
        while cur is not None:
            r = _swing_attempt(O, H, Lw, C, ends, sarr, cur, j0, min_rr, pad, max_wait_bars, void)
            if r is None:
                break
            r.update(seq=seq, attempt=attempt, size=0.5 ** attempt)
            r["pnl_r"] = r["size"] * r["r"]
            rows.append(r)
            j0 = r["j_out"]
            if r["exit_reason"] != "stop":
                break
            failed.append(cur)
            attempt += 1
            if reentry_max is not None and attempt > reentry_max:
                break
            cur = pick_reentry(sarr, failed, cur["bottom"], ends[j0])
            if cur is None:
                break
        j = max(j0 + 1, j + 1)
    return rows


def _untested(a: dict, Lw, ends, j: int) -> bool:
    """No bar since the array became known has traded into it (the lowest low since is above its top)."""
    q0 = next((q for q in range(j + 1) if _cmp_ts(a["t_known"], ends[q])), None)
    return q0 is None or q0 + 1 > j or float(Lw[q0 + 1:j + 1].min()) > a["top"]


def _swing_attempt(O, H, Lw, C, ends, sarr, a, j0, min_rr, pad, max_wait, void):
    n = len(C)
    entry, stop = a["ce"], a["bottom"] - pad
    opp = [b["bottom"] for b in sarr if b["kind"] == "bear" and _cmp_ts(b["t_known"], ends[min(j0, n - 1)]) and b["bottom"] > entry]
    if not opp or entry <= stop:
        return None
    target = min(opp)
    if (target - entry) / (entry - stop) < min_rr:
        return None
    mw = [b for b in sarr if b["tf"] in ("M", "W") and b["kind"] == "bull" and b["top"] < entry and _cmp_ts(b["t_known"], ends[min(j0, n - 1)])]
    layer = max(mw, key=lambda b: b["top"]) if mw else None
    fill = None
    for j in range(j0 + 1, n):
        if layer is not None and void == "mw_far_edge" and min(O[j], C[j]) < layer["bottom"]:
            return None if fill is None else dict(j_in=fill[0], j_out=j, entry=entry, exit=C[j], stop=stop, target=target, exit_reason="void", r=(C[j] - entry) / (entry - stop), array=a)
        if fill is None:
            if j - j0 > max_wait:
                return None
            if Lw[j] <= entry:
                fill = (j, min(entry, O[j]))
            else:
                continue
        px = fill[1]
        if Lw[j] <= stop:
            return dict(j_in=fill[0], j_out=j, entry=px, exit=min(stop, O[j]), stop=stop, target=target, exit_reason="stop", r=(min(stop, O[j]) - px) / (px - stop), array=a)
        if H[j] >= target and j > fill[0]:
            return dict(j_in=fill[0], j_out=j, entry=px, exit=target, stop=stop, target=target, exit_reason="target", r=(target - px) / (px - stop), array=a)
    if fill is None:
        return None
    return dict(j_in=fill[0], j_out=n - 1, entry=fill[1], exit=C[-1], stop=stop, target=target, exit_reason="open", r=(C[-1] - fill[1]) / (fill[1] - stop), array=a)


def reentry_report(rows: list) -> dict:
    """Hit rates and the recovery fraction by attempt number: {attempt: dict(n, hit_rate, mean_r, recovered)} where recovered = the share of sequences whose cumulative pnl_r after that attempt is >= 0."""
    out: dict = {}
    by_seq: dict = {}
    for r in rows:
        by_seq.setdefault(r["seq"], []).append(r)
    for a in sorted({r["attempt"] for r in rows}):
        rs = [r for r in rows if r["attempt"] == a]
        cum = [sum(x["pnl_r"] for x in v if x["attempt"] <= a) for v in by_seq.values() if any(x["attempt"] == a for x in v)]
        out[a] = dict(n=len(rs), hit_rate=float(np.mean([r["exit_reason"] == "target" for r in rs])), mean_r=float(np.mean([r["r"] for r in rs])),
                      recovered=float(np.mean([c >= 0 for c in cum])) if cum else NAN)
    return out


# --------------------------------------------------------------------------------------------------------------
# X13-two-failed-trend-signals
# --------------------------------------------------------------------------------------------------------------

def trend_tired(signals: list, tired_n: int = 2, tired_pause: bool = False, flip=None, closes=None, side: int = 1) -> dict:
    """Swing mode (cc06_001 ~00:09:01): signals = dicts with `date`, `win` (bool; True = target, False = stopped) in time order. After `tired_n` consecutive stop-outs `trend_tired` is set (a win in between
    resets the count). `tired_pause` (our interpretation, a switch to test) skips the with-trend signals that follow until the table's `flip` column (a Series date -> state) changes from its value at
    the moment the flag was set. With `closes` (a Series date -> close) reports the forward 20 / 40-day return in the trend direction after each flag against the baseline of every signal date. Returns
    dict(flags=[dates], kept=[signals], skipped=[signals], fwd20, fwd40, base20, base40)."""
    n_loss = 0
    flags, kept, skipped = [], [], []
    paused_at = None
    for s in signals:
        d = s["date"]
        if paused_at is not None:
            if flip is not None and _flip_at(flip, d) != paused_at[1]:
                paused_at = None
            else:
                skipped.append(s)
                continue
        kept.append(s)
        if s["win"]:
            n_loss = 0
        else:
            n_loss += 1
            if n_loss >= tired_n:
                flags.append(d)
                n_loss = 0
                if tired_pause:
                    paused_at = (d, _flip_at(flip, d) if flip is not None else None)
    out = dict(flags=flags, kept=kept, skipped=skipped, fwd20=NAN, fwd40=NAN, base20=NAN, base40=NAN)
    if closes is not None and len(closes):
        c = closes.sort_index()
        idx = _naive_idx(c.index)

        def fwd(t, h):
            k = int(idx.searchsorted(_naive_idx([t])[0]))
            return side * (float(c.iloc[k + h]) / float(c.iloc[k]) - 1.0) if k + h < len(c) and k < len(c) else NAN
        for h in (20, 40):
            f = [fwd(d, h) for d in flags]
            b = [fwd(s["date"], h) for s in signals]
            out[f"fwd{h}"] = float(np.nanmean(f)) if f and not np.all(np.isnan(f)) else NAN
            out[f"base{h}"] = float(np.nanmean(b)) if b and not np.all(np.isnan(b)) else NAN
    return out


def _flip_at(flip, d):
    s = flip.sort_index()
    idx = _naive_idx(s.index)
    k = int(idx.searchsorted(_naive_idx([d])[0], side="right")) - 1
    return None if k < 0 else s.iloc[k]


# --------------------------------------------------------------------------------------------------------------
# X15-position-trade-frequency / X15-swing-frequency
# --------------------------------------------------------------------------------------------------------------

def position_freq(signals: list, pos_max_per_quarter: int = 1, pos_flag_per_year: int = 4) -> dict:
    """Position model frequency (cc05_013 ~00:24:19: 'two, if I'm lucky three position trade setups a year'): `signals` = dates or dicts with `date`. At most `pos_max_per_quarter` per calendar quarter are
    kept (the first ones); the raw counts per year and per quarter are reported and a parameter set is flagged over-firing when a year holds more than `pos_flag_per_year` raw signals or any quarter more than
    `pos_max_per_quarter`. Returns dict(kept, per_year, per_quarter, over_year, over_quarter, flag)."""
    ds = sorted(pd.Timestamp(s["date"] if isinstance(s, dict) else s) for s in signals)
    per_y: dict = {}
    per_q: dict = {}
    kept = []
    for t in ds:
        q = (t.year, (t.month - 1) // 3 + 1)
        per_y[t.year] = per_y.get(t.year, 0) + 1
        per_q[q] = per_q.get(q, 0) + 1
        if per_q[q] <= pos_max_per_quarter:
            kept.append(t)
    oy = sorted(y for y, v in per_y.items() if v > pos_flag_per_year)
    oq = sorted(q for q, v in per_q.items() if v > pos_max_per_quarter)
    return dict(kept=kept, per_year=per_y, per_quarter=per_q, over_year=oy, over_quarter=oq, flag=bool(oy or oq))


def swing_frequency(signals: list, swing_one_open: bool = True, swing_flag_per_year: int = 12) -> dict:
    """Swing frequency (cc06_006 ~00:14:25: 'one to two swing trades per every four to six weeks'): `signals` = dicts with `entry` and `exit` (dates), in time order. With `swing_one_open` the second of
    two overlapping signals is dropped while the first is open. Reports the kept signals per year and per 28-day block, and flags a year over `swing_flag_per_year` (our interpretation of the over-firing line).
    Returns dict(kept, dropped, per_year, per_block, over_year, flag)."""
    kept, dropped = [], []
    open_until = None
    for s in sorted(signals, key=lambda x: pd.Timestamp(x["entry"])):
        t0, t1 = pd.Timestamp(s["entry"]), pd.Timestamp(s["exit"])
        if swing_one_open and open_until is not None and t0 <= open_until:
            dropped.append(s)
            continue
        kept.append(s)
        open_until = t1 if open_until is None else max(open_until, t1)
    per_y: dict = {}
    per_b: dict = {}
    if kept:
        base = pd.Timestamp(kept[0]["entry"])
        for s in kept:
            t = pd.Timestamp(s["entry"])
            per_y[t.year] = per_y.get(t.year, 0) + 1
            b = (t - base).days // 28
            per_b[b] = per_b.get(b, 0) + 1
    over = sorted(y for y, v in per_y.items() if v > swing_flag_per_year)
    return dict(kept=kept, dropped=dropped, per_year=per_y, per_block=per_b, over_year=over, flag=bool(over))


# --------------------------------------------------------------------------------------------------------------
# E12-start-small-build: the weekly OSOK scale-in
# --------------------------------------------------------------------------------------------------------------

def osok_scale_in(daily: pd.DataFrame, arrays: list, bias, first_frac: float = 0.25, pad: float = 0.0, target_tf: str = "D", stop_mode: str = "daily_swing", side: int = -1) -> list:
    """Weekly OSOK built small-first (cc07_008 ~00:29:33; `side=-1` is the bearish week that sells into premium, `side=+1` the bullish mirror), on daily bars. `bias` = {Monday date: -1 / +1}, a callable
    Monday -> bias or an int (the weekly bias of the table): a week trades only when it equals `side`. Monday: when its range trades into a known, live array of the week's origin type in `arrays` (a premium
    array for a sell; the daily approximation of 'price trades into it' = the high reaches the array's bottom), `first_frac` of the planned size is filled at max(open, the array's bottom) (a sell). The rest is
    added at the first of Tuesday / Wednesday that makes a HIGHER HIGH than Monday's (at max(open, Monday's high), a stop order through it); when neither does, at the open of the first of them that opens
    above Monday's close (the next intraday premium retrace, daily approximation); otherwise the small piece stays alone. Stop = `htf.swing_stop` (above the latest daily pivot high before Monday; the
    array's top when that lies under the entry); target = the nearest UNTOUCHED opposing array of `target_tf` beyond the entry, else the week's last close; the stop is taken first inside a bar.
    Rows (one per week traded): week, n_fills, first_entry, avg_entry, size, stop, exit, exit_reason, pts_build and pts_full (the whole size at the Monday fill) in real points of profit."""
    o, h, l, c = (daily[k].values.astype(float) for k in ("open", "high", "low", "close"))
    idx = _naive_idx(daily.index)
    wid = np.asarray(idx.to_period("W-FRI").astype(str))
    sgn = 1 if side > 0 else -1
    so, sh, sl, sc = (o, h, l, c) if side > 0 else (-o, -l, -h, -c)              # side space: the trade is a long
    sdaily = pd.DataFrame(dict(open=so, high=sh, low=sl, close=sc), index=daily.index)
    entry_kind = "bull" if side > 0 else "bear"
    rows = []
    k, n = 0, len(daily)
    while k < n:
        w0 = k
        while k < n and wid[k] == wid[w0]:
            k += 1
        wk = list(range(w0, k))
        mon = wk[0]
        b = bias(idx[mon]) if callable(bias) else (bias.get(idx[mon]) if hasattr(bias, "get") else bias)
        if b != side:
            continue
        known = [a for a in arrays if _cmp_ts(a["t_known"], idx[mon])]
        ent = [side_arr(a, side) for a in known if a["kind"] == entry_kind and a["tf"] in ("M", "W", "D")]
        hit = [a for a in ent if sl[mon] <= a["top"] and sh[mon] >= a["bottom"]]
        if not hit:
            continue
        a = max(hit, key=lambda x: x["top"])
        first = float(min(so[mon], a["top"]))
        sp = htf.swing_stop(sdaily, mon, 1, stop_mode, pad=pad)
        stop = float(sp) if sp == sp and sp < first else float(a["bottom"] - pad)
        tgts = []
        for x in (side_arr(b_, side) for b_ in known if b_["tf"] == target_tf and b_["kind"] != entry_kind):
            q0 = next((q for q in range(mon + 1) if _cmp_ts(x["t_known"], idx[q] + pd.Timedelta(hours=17))), None)
            if x["bottom"] > first and (q0 is None or q0 >= mon or float(sh[q0:mon].max()) < x["bottom"]):
                tgts.append(x["bottom"])
        target = min(tgts) if tgts else None
        # the add: a higher high than Monday's (side space: a lower low) on Tue / Wed, else the next day's open beyond Monday's close
        add = None
        for q in wk[1:3]:
            if sl[q] < sl[mon]:
                add = (q, float(min(so[q], sl[mon])))
                break
        if add is None:
            for q in wk[1:3]:
                if so[q] < sc[mon]:
                    add = (q, float(so[q]))
                    break
        fills = [(first_frac, first)]
        exit_px, why = float(sc[wk[-1]]), "week_end"
        for q in wk:
            if add is not None and q == add[0]:
                fills.append((1.0 - first_frac, add[1]))
            if sl[q] <= stop:
                exit_px, why = float(min(stop, so[q])) if q != mon else float(stop), "stop"
                break
            if target is not None and q != mon and sh[q] >= target:
                exit_px, why = float(target), "target"
                break
        size = sum(f for f, _ in fills)
        avg = sum(f * p_ for f, p_ in fills) / size
        rows.append(dict(week=idx[mon], n_fills=len(fills), first_entry=sgn * first, avg_entry=sgn * avg, size=size, stop=sgn * stop, exit=sgn * exit_px, exit_reason=why,
                         pts_build=size * (exit_px - avg), pts_full=1.0 * (exit_px - first), first_frac=first_frac))
    return rows


# --------------------------------------------------------------------------------------------------------------
# E12-readd-after-partials-swing
# --------------------------------------------------------------------------------------------------------------

def swing_readd(h4: pd.DataFrame, entries: list, readd_mult: float = 1.0, readd_gate: str = "any", readd_stop: str = "orig", partial_frac: float = 0.25, pad: float = 0.0) -> list:
    """Swing / position re-add after a partial (098 ~00:25:13; cc04_003 ~00:30:31; cc05_013 ~00:19:55; cc06_008 ~00:17:00), on 4h bars. `entries` = dicts with `time` (the 4h bar start at whose close the order
    is armed), `side` (+1 / -1), `entry` (the limit), `stop`, `target` and `partial_level` (the first opposing HTF array). The order fills from the next bar; a partial of `partial_frac` of the position is
    taken at `partial_level`; the re-add of partial_frac x `readd_mult` (test 1.33) is a limit at the CE of the FIRST same-side 4h FVG (confirmed on its third candle's close) or order block (a down-close
    bar whose next bar closes above its high; known at that next bar) formed AFTER the partial. `readd_gate="half_obj"` (cc06_008: after price reached 50 % of the objective) additionally needs the high to
    have reached entry + 0.5 x (target - entry) before the array forms. `readd_stop`: "orig" = the original stop (098), "be" = breakeven after the first profit (cc06_008). The stop is taken first inside a
    bar. One row per entry: fill / partial / re-add bars, the re-add quantity, exit, exit_reason, r_total (R of the original risk, all lots)."""
    rows = []
    for e in entries:
        s = 1 if e.get("side", 1) >= 0 else -1
        O, H, Lw, C = side_bars(h4, s)
        n = len(C)
        t_idx = _naive_idx(h4.index)
        j0 = int(t_idx.searchsorted(_naive_idx([e["time"]])[0]))
        entry, stop0, target, plevel = s * e["entry"], s * e["stop"], s * e["target"], s * e["partial_level"]
        risk = entry - stop0
        if risk <= 0:
            continue
        fv = [z for z in L.fvgs(H, Lw) if z.kind == "bull"]
        fill = next((j for j in range(j0 + 1, n) if Lw[j] <= entry), None)
        if fill is None:
            continue
        lots = [(1.0, min(entry, O[fill]))]
        realized = 0.0
        stop = stop0
        partial = half = readd = order = None
        why, exit_px = "open", float(C[-1])
        for j in range(fill, n):
            if Lw[j] <= stop:
                why, exit_px = "stop", float(min(stop, O[j]))
                break
            if j > fill and H[j] >= target:
                why, exit_px = "target", float(O[j] if O[j] > target else target)
                break
            if half is None and H[j] >= entry + 0.5 * (target - entry):
                half = j
            if partial is None and j > fill and H[j] >= plevel:
                qty = sum(q for q, _ in lots)
                avg = sum(q * p for q, p in lots) / qty
                realized += partial_frac * (plevel - avg)
                lots = [(q * (1.0 - partial_frac / qty), p) for q, p in lots]
                partial = j
                if readd_stop == "be":
                    stop = max(stop, avg)
            if partial is not None and readd is None and order is None:
                cands = [(z.i, float((z.top + z.bottom) / 2.0)) for z in fv if partial < z.i <= j]
                cands += [(q + 1, float((H[q] + Lw[q]) / 2.0)) for q in range(partial + 1, j) if C[q] < O[q] and C[q + 1] > H[q]]
                cands = [cd for cd in cands if readd_gate != "half_obj" or (half is not None and half <= cd[0])]
                if cands:
                    order = min(cands)
            elif order is not None and readd is None and j > order[0] and Lw[j] <= order[1]:
                lots.append((partial_frac * readd_mult, float(min(order[1], O[j]))))
                readd = (j, partial_frac * readd_mult)
        qty = sum(q for q, _ in lots)
        avg = sum(q * p for q, p in lots) / qty if qty else 0.0
        realized += qty * (exit_px - avg)
        rows.append(dict(time=e["time"], side=s, fill_bar=fill, partial_bar=partial, readd_bar=None if readd is None else readd[0], readd_qty=0.0 if readd is None else readd[1],
                         exit=s * exit_px, exit_reason=why, stop_final=s * stop, r_total=realized / risk))
    return rows


# --------------------------------------------------------------------------------------------------------------
# E12-daily-downclose-add-stops
# --------------------------------------------------------------------------------------------------------------

def daily_stop_model(daily: pd.DataFrame, arrays: list, first_frac: float = 1.0, dsm_partial: float = 0.5, dsm_eq_gate: bool = True, pad: float = 0.0, stop_mode: str = "daily_swing",
                     side: int = 1, max_units: int = 3, swing_lookback: int = 60) -> list:
    """The daily stop-entry model (cc05_016 ~00:03:14; the long side, `side=-1` mirrors it): with a monthly / weekly array as the draw (the nearest known opposing M / W array beyond price - its near
    edge), a BUY STOP sits at the open of the latest closed down-close daily candle and is rolled to the latest down-close candle each day until filled (it fills at max(open, the stop)). Entries are
    allowed while the last close is at or under the HTF EQ (the midpoint of the latest daily pivot low and the draw; `dsm_eq_gate`) and the draw has not been reached. `first_frac` is the first fill's
    size (0.5 = the `daily_stop_half` variant of item 5: start at half and add at the prior trigger-candle opens); a new down-close candle forming while the position is open and price is still under the
    EQ places a further buy stop at its open for `first_frac` (up to `max_units` fills). Stop = `htf.swing_stop` (the latest daily pivot low before the fill; the trigger candle's low when none lies under
    the fill) less pad. `dsm_partial` of the position is taken at the first opposing known daily array above the entry; if price then retraces to the trigger open, the partial quantity is put back there.
    Everything is out at the draw (target) or the stop (the stop first inside a bar). Rows: fills [(day, qty, price, kind)], exit, exit_reason, pts (profit in points per 1.0 size), stop, draw."""
    o, h, l, c = (daily[k].values.astype(float) for k in ("open", "high", "low", "close"))
    s = 1 if side >= 0 else -1
    so, sh, sl, sc = (o, h, l, c) if s > 0 else (-o, -l, -h, -c)
    sd_ = pd.DataFrame(dict(open=so, high=sh, low=sl, close=sc), index=daily.index)
    idx = _naive_idx(daily.index)
    n = len(daily)
    opp_kind = "bear" if s > 0 else "bull"
    known = [side_arr(a, s) for a in arrays]
    rows = []
    j = 6
    while j < n - 1:
        t_day = idx[j]
        mw = [a for a in known if a["tf"] in ("M", "W") and a["kind"] == opp_kind and _cmp_ts(a["t_known"], t_day) and a["bottom"] > sc[j - 1]]
        if not mw:
            j += 1
            continue
        draw = min(a["bottom"] for a in mw)
        _, pl = L.pivots(sh[max(0, j - swing_lookback):j], sl[max(0, j - swing_lookback):j], 1)
        eq = (pl[-1].price + draw) / 2.0 if pl else None
        if dsm_eq_gate and (eq is None or sc[j - 1] > eq):
            j += 1
            continue
        dn = [q for q in range(j) if sc[q] < so[q]]
        if not dn or sh[j] < so[dn[-1]]:
            j += 1
            continue
        trig = float(so[dn[-1]])
        fill_px = float(max(so[j], trig))
        if fill_px >= draw:                                   # a buy stop at or beyond the draw is no entry toward it
            j += 1
            continue
        sp = htf.swing_stop(sd_, j, 1, stop_mode, pad=pad)
        stop = float(sp) if sp == sp and sp < fill_px else float(sl[dn[-1]] - pad)
        qty, cost = first_frac, first_frac * fill_px
        fills = [(idx[j], first_frac, fill_px, "entry")]
        trig_open = trig
        opp = [a["bottom"] for a in known if a["tf"] == "D" and a["kind"] == opp_kind and _cmp_ts(a["t_known"], t_day) and a["bottom"] > fill_px]
        p1 = min(opp) if opp else None
        realized, part_q, partial_done = 0.0, 0.0, False
        why, exit_px, jx = "open", float(sc[n - 1]), n - 1
        if sl[j] <= stop:
            why, exit_px, jx = "stop", float(min(stop, so[j])), j
        else:
            for q in range(j + 1, n):
                if sl[q] <= stop:
                    why, exit_px, jx = "stop", float(min(stop, so[q])), q
                    break
                if sh[q] >= draw:
                    why, exit_px, jx = "target", float(draw), q
                    break
                if part_q > 0 and sl[q] <= trig_open:                 # the retrace to the trigger open: the partial quantity goes back on there
                    px = float(min(trig_open, so[q]))
                    qty += part_q
                    cost += part_q * px
                    fills.append((idx[q], part_q, px, "readd"))
                    part_q = 0.0
                if p1 is not None and not partial_done and sh[q] >= p1:
                    part_q = dsm_partial * qty
                    avg = cost / qty
                    realized += part_q * (p1 - avg)
                    qty -= part_q
                    cost -= part_q * avg
                    fills.append((idx[q], -part_q, float(p1), "partial"))
                    partial_done = True
                if sc[q] < so[q] and (not dsm_eq_gate or eq is None or sc[q] <= eq) and sh[q] < draw and q + 1 < n and sum(1 for f in fills if f[3] in ("entry", "add")) < max_units:
                    nxt = float(so[q])
                    if sh[q + 1] >= nxt and sl[q + 1] > stop:                    # a further buy stop at the new down-close candle's open
                        px = float(max(so[q + 1], nxt))
                        qty += first_frac
                        cost += first_frac * px
                        fills.append((idx[q + 1], first_frac, px, "add"))
                        trig_open = nxt
        avg = cost / qty if qty else 0.0
        realized += qty * (exit_px - avg)
        rows.append(dict(day=idx[j], fills=[(d_, q_, s * p_, k_) for d_, q_, p_, k_ in fills], exit=s * exit_px, exit_reason=why, pts=realized, stop=s * stop, draw=s * draw))
        j = max(jx + 1, j + 1)
    return rows
