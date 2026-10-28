"""Caption-gap pass, package bias_htf#6/7: the STUDY-ONLY models of models_setups_entries.md (items 96, 100, 133 monthly OB, 155-162, 164-170). Research functions, no live branch; they read daily /
4h / intraday frames and (optionally) `htf.table` columns and `htf` arrays, never Params. Same conventions as bh6s.py: a bar is used only after it closes, stop and target in one bar = stop first,
prices are handled in side space (a short is a long on negated prices), thresholds the sources never give are marked [our interpretation].

  opening_price_model        96   the Asian / midnight opening-price position model
  daily_fvg_sellstop        100   the daily FVG sell-stop at the next open
  monthly_ob_study          133   the monthly OB activation -> return -> target statistics (the `mob` column of bh6.py)
  daily_candle_entries      155-159  the daily-candle stop-at-open / limit-at-close models (needs the daily PD array, the MSS preference, both order types side by side)
  position_checklist        160   the eight position-trade steps, report only
  hallmarks                 170   the eight explosive-swing hallmarks, report only
  swing_entries             161, 162, 164-169  the 4h swing execution (location, no range turtle, impulse -> retrace sequence, 4h bounce confirmation, MWD sequential, framework defaults, dealing range
                                    premium / discount, monthly MT + 4h OB)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import levels as L
from . import bh3 as BH3
from . import bh6 as BH6
from .bh6s import NAN, _dates, _ohlc, _side_bars, r_distribution  # noqa: F401  (r_distribution is re-exported)


def _norm(x):
    t = pd.Timestamp(x)
    return (t.tz_localize(None) if t.tzinfo is not None else t).normalize()


# --------------------------------------------------------------------------------------------------------------
# new-opening-price-position-model (96)
# --------------------------------------------------------------------------------------------------------------

def _araw(ra, key: str, default=None):
    """An attribute of an array given either as an object (levels.Zone ...) or a dict; `default` when the array has no such field."""
    if isinstance(ra, dict):
        return ra.get(key, default)
    return getattr(ra, key, default)


def opening_price_model(df: pd.DataFrame, bias, draw=None, ref_min: int = 0, tick: float = 0.0, conservative: bool = False) -> pd.DataFrame:
    """new-opening-price-position-model (095 ~00:15:42), research: on each calendar day whose weekly bias (`bias`: date-indexed Series, +1 / -1) is set, take the opening price at minute `ref_min` (0 =
    the midnight open; the first bar at or after it), wait for the market to trade BELOW it first (above it for a short), then place a stop at the open: a bar trading back through it fills (at the open,
    or at that bar's open on a gap). Stop = the lowest low since the reference (the sub-open low) less `tick` [our interpretation: ICT says only a reasonable stop]; target = the weekly `draw`
    (date-indexed level Series; None = none), held to the target, the stop or the week's last bar. One trade per day. Returns one row per trade with r in initial-risk units. The fill bar is not managed intrabar (the stop is checked from the next bar): the column `entry_bar_stop_reached`
    flags a fill bar whose low also reached the stop, and `conservative=True` books that trade as stopped (-1R) [our interpretation of the unknown intrabar order]."""
    day = np.asarray([_norm(x) for x in df.index])
    mins = np.asarray([pd.Timestamp(x).hour * 60 + pd.Timestamp(x).minute for x in df.index])
    wk = np.asarray(pd.PeriodIndex(day, freq="W-FRI").astype(str))
    o, h, l, c = _ohlc(df)
    bsr = {_norm(k): int(v) for k, v in bias.items()}
    drw = None if draw is None else {_norm(k): float(v) for k, v in draw.items()}
    rows = []
    for d_ in sorted(set(day)):
        s = bsr.get(d_, 0)
        if not s:
            continue
        ix = np.flatnonzero((day == d_) & (mins >= ref_min))
        if not len(ix):
            continue
        hi, lo = (h, l) if s > 0 else (-l, -h)
        r0 = int(ix[0])
        opn = s * o[r0]
        sub = lo[r0]
        under, fill = False, None
        for q in ix[1:]:
            sub = min(sub, lo[q])
            if not under:
                under = lo[q] < opn
                continue
            if hi[q] >= opn:
                fill = (int(q), max(opn, s * o[q]))
                break
        if fill is None:
            continue
        q0, px = fill
        stop = sub - tick
        if px - stop <= 0:
            continue
        tgt = None if drw is None or d_ not in drw else s * drw[d_]
        r, why, qe = None, "week_end", q0
        eb = bool(lo[q0] <= stop)
        if eb and conservative:
            r, why = -1.0, "stop"
        for q in range(q0 + 1, len(c)) if r is None else ():
            if wk[q] != wk[q0]:
                break
            qe = q
            if lo[q] <= stop:
                r, why = -1.0, "stop"
                break
            if tgt is not None and hi[q] >= tgt:
                r, why = (tgt - px) / (px - stop), "target"
                break
        if r is None:
            r = (s * c[qe] - px) / (px - stop)
        rows.append(dict(date=d_, side=s, entry=s * px, stop=s * stop, r=float(r), reason=why, entry_bar_stop_reached=eb))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------------------------
# M17-daily-swing-sellstop-midnight (100)
# --------------------------------------------------------------------------------------------------------------

def daily_fvg_sellstop(df_daily: pd.DataFrame, bias, tbl: pd.DataFrame | None = None, near_adr: float = 0.5, tick: float = 0.0, p1_frac: float = 0.5, side: int = -1) -> pd.DataFrame:
    """M17-daily-swing-sellstop-midnight (098 ~00:22:11), parked research: on daily bars with the table bias -1 (`bias`: date-indexed Series of the bias for each session) and the PRIOR session having
    traded up into a daily bearish FVG (its high reached the gap's bottom, its close stayed below the gap's top), a sell stop sits at the session's open (the settlement open is acceptable; ICT: the
    midnight NY open) and fills when that session trades `tick` below it. Sessions that open farther below the gap than `near_adr` x ADR5 are skipped. Stop = the high of the candle that formed the
    FVG (its middle candle; the first candle's high when the middle one is not above the entry) [our interpretation]. Exits: `p1_frac` at the nearest daily low (the lowest low of the last 10
    sessions), the rest at the weekly target (`tbl.wk_draw_dn` of that row, else the lowest low of the last 40 sessions). Reports R. side=+1 mirrors (bullish FVG, buy stop)."""
    o, h, l, c = _side_bars(df_daily, side)                  # a short is a long on the mirrored market: a bearish gap is a bullish one below
    n = len(c)
    dd = _dates(df_daily)
    pos = {d_: k for k, d_ in enumerate(dd)}
    bsr = {_norm(k): int(v) for k, v in bias.items()}
    gaps = [(j, float(h[j - 2]), float(l[j]), j - 2, j - 1) for j in range(2, n) if l[j] > h[j - 2]]          # (formed, bottom, top, first, middle) in side space
    out = []
    for kf in range(4, n):
        if bsr.get(dd[kf], 0) != side:
            continue
        k = kf - 1                                           # the prior session
        cand = next((g for g in reversed(gaps) if g[0] < k and l[k] <= g[2] and c[k] >= g[1]), None)
        if cand is None:
            continue
        j, bot, top, c1, c2 = cand
        adr = float(np.mean(h[max(0, k - 4):k + 1] - l[max(0, k - 4):k + 1]))
        E = float(o[kf])
        if E > top + near_adr * adr:
            continue
        if not h[kf] > E + tick:
            continue                                         # the stop order never triggered
        stop = float(l[c2]) if l[c2] < E else float(l[c1])
        if stop >= E:
            continue
        R = E - stop
        hist = h[max(0, kf - 10):kf]
        t1 = float(hist.max()) if len(hist) and hist.max() > E else None
        tw = None
        if tbl is not None:
            for ix in tbl.index:
                if _norm(ix) == dd[kf]:
                    v = tbl.loc[ix].get("wk_draw_dn" if side < 0 else "wk_draw_up", NAN)
                    if v == v:
                        tw = float(v) * (-1.0 if side < 0 else 1.0)
        if tw is None or tw <= E:
            tw = float(h[max(0, kf - 40):kf].max())
        size, real, stp, why = 1.0, 0.0, stop, "open"
        for q in range(kf, n):
            if l[q] <= stp:
                real += size * (stp - E) / R
                why, size = "stop", 0.0
                break
            if size == 1.0 and t1 is not None and h[q] >= t1:
                real += p1_frac * (t1 - E) / R
                size -= p1_frac
                stp = max(stp, E)
            if tw > E and h[q] >= tw and size > 0:
                real += size * (tw - E) / R
                why, size = "target", 0.0
                break
        if size > 0:
            real += size * (c[-1] - E) / R
        out.append(dict(fill_i=kf, fvg_i=j, entry=side * E if side < 0 else E, stop=side * stop if side < 0 else stop, r=float(real), reason=why))
    return pd.DataFrame(out)


# --------------------------------------------------------------------------------------------------------------
# new-htf-regime-trigger-and-entry (133 models)
# --------------------------------------------------------------------------------------------------------------

def monthly_ob_study(df_daily: pd.DataFrame, tick: float = 0.0, max_wait: int = 60) -> pd.DataFrame:
    """new-htf-regime-trigger-and-entry (cc03_002 ~00:14:23, ~00:22:50): the daily-entry statistics of the monthly OB sequence. For each activation of the `mob` column (a session trades above the
    high of the last completed down-close monthly candle D = the candle is a bullish OB; mirror: below the low of the last up-close candle U): wait up to `max_wait` sessions for a return into the
    candle (a bar trading down to its open, the top of the body) and buy there (a limit; the fill is at the open on a gap); stop below D's low; target U's high (the old highs above it). The idea is
    void when the candle's low breaks first. Returns one row per activation: act_i, fill_i (-1 = never returned), days_to_return, r, reason. Bearish activations are the mirror."""
    o0, h0, l0, c0 = _ohlc(df_daily)
    mid = np.asarray(df_daily.index.to_period("M").astype(str))
    eps: list = []
    BH6.mob_state_after(o0, h0, l0, c0, mid, eps)
    rows = []
    for ep in eps:
        s = ep["side"]
        o, h, l, c = _side_bars(df_daily, s)
        ref = ep["D"] if s > 0 else ep["U"]
        opp = ep["U"] if s > 0 else ep["D"]
        if ref is None:
            continue
        ro, rh, rl, rc = ref
        lvl = s * ro                                           # the candle's open, in side space
        stop = (rl if s > 0 else -rh) - tick                   # beyond the candle's far extreme
        tgt = None
        if opp is not None:
            tgt = opp[1] if s > 0 else -opp[2]
        if tgt is None or tgt <= lvl:
            tgt = float(np.max(h[max(0, ep["j"] - 60):ep["j"] + 1]))
        j0 = ep["j"]
        fill = None
        for q in range(j0 + 1, min(len(c), j0 + 1 + max_wait)):
            if l[q] < stop:
                break                                         # the candle's far extreme broke first
            if l[q] <= lvl:
                fill = (q, min(lvl, o[q]))
                break
        if fill is None:
            rows.append(dict(act_i=j0, side=s, fill_i=-1, days_to_return=NAN, r=NAN, reason="no_return"))
            continue
        q0, px = fill
        risk = px - stop
        r, why = None, "open"
        for q in range(q0, len(c)):
            if l[q] <= stop:
                r, why = -1.0, "stop"
                break
            if tgt > px and h[q] >= tgt:
                r, why = (tgt - px) / risk, "target"
                break
        if r is None:
            r = (c[-1] - px) / risk
        rows.append(dict(act_i=j0, side=s, fill_i=q0, days_to_return=int(q0 - j0), r=float(r), reason=why))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------------------------
# M17-daily-stop-entry-at-open-with-roll / -limit-at-close / -needs-daily-pd-array / -after-mss / E1-stop-vs-limit-ob-tradeoff (155-159)
# --------------------------------------------------------------------------------------------------------------

def _arr_side(a, s: int) -> tuple:
    """(kind in side space "disc"/"prem", bottom, top, tf, known) of a htf.Arr-like object or dict, mirrored for s < 0."""
    g = (lambda k: a[k]) if isinstance(a, dict) else (lambda k: getattr(a, k))
    kind, top, bot = g("kind"), float(g("top")), float(g("bottom"))
    if s > 0:
        return ("disc" if kind == "bull" else "prem"), bot, top, g("tf"), int(g("known"))
    return ("disc" if kind == "bear" else "prem"), -top, -bot, g("tf"), int(g("known"))


def _mss_since(h, l, c, ref: int, j: int) -> bool:
    """A close (at a session <= j) above the last confirmed 3-bar swing high formed since `ref`, side space."""
    ph, _ = L.pivots(h[:j + 1], l[:j + 1], 1)
    for q in ph:
        if q.i >= ref and q.known <= j and any(c[x] > q.price for x in range(q.known, j + 1)):
            return True
    return False


def daily_candle_entries(df_daily: pd.DataFrame, target, side: int = 1, mode: str = "stop_open", bias=None, arrays=None, need_array: bool = False, need_mss: bool = False, tick: float = 0.0,
                         mss_lookback: int = 20, modes=None) -> pd.DataFrame:
    """M17 daily-candle entries (cc05_016 ~00:00:36, cc05_017 ~00:00:41, ~00:04:48, ~00:01:25, cc05_018 ~00:04:48), research. Long (side=1; side=-1 mirrors): `target` = the monthly / weekly PD array above
    that draws price (a date-indexed Series of its level, or a scalar). A daily candle that CLOSES down arms an order for the next sessions: mode "stop_open" = a buy stop at that candle's OPEN (a later
    down-close candle moves it to its own open; it fills when a bar trades through it, at the bar's open on a gap), "limit_close" = a buy limit at its CLOSE (replaced by each new qualifying
    candle's close [our interpretation]; it fills when a bar trades `tick` below it). Both stop the arming once the target is touched. The stop is deferred to trade management; the study uses
    the signal candle's low less `tick` [our interpretation]. `bias` (date-indexed +1 / -1) must equal `side` at the order's session. need_array: the FIRST entry needs the down candle to trade into a
    daily PD array of the trade side (`arrays`: htf.Arr or dicts with kind / top / bottom / tf / known = daily position); later entries in the trend toward the target do not. need_mss: a daily
    close above the last daily swing high formed since the latest array touch (else since the lowest low of the last `mss_lookback` sessions). `modes` (a tuple) runs several order types side by side
    (item 159) with a `mode` column. Returns one row per armed order: mode, arm_i, fill_i (-1 = never filled), price, entry, stop, target, r, reason."""
    modes = tuple(modes) if modes else (mode,)
    if len(modes) > 1:
        return pd.concat([daily_candle_entries(df_daily, target, side, m, bias, arrays, need_array, need_mss, tick, mss_lookback) for m in modes], ignore_index=True)
    o, h, l, c = _side_bars(df_daily, side)
    n = len(c)
    dd = _dates(df_daily)
    tg = None if not isinstance(target, pd.Series) else {_norm(k): float(v) for k, v in target.items()}
    bs = None if bias is None else {_norm(k): int(v) for k, v in bias.items()}
    disc = [_arr_side(a, side) for a in (arrays or ())]
    disc = [a for a in disc if a[0] == "disc"]
    rows: list = []
    order = None                                           # dict
    pos: list = []
    flag = not need_array                                  # the first-entry array requirement was met
    last_touch = None
    for j in range(n):
        # fills on bar j
        if order is not None and j > order["arm_i"]:
            fb = (h[j] >= order["price"]) if mode == "stop_open" else (l[j] <= order["price"] - tick)
            if fb:
                px = max(order["price"], o[j]) if mode == "stop_open" else min(order["price"], o[j])
                order.update(fill_i=j, entry=px)
                pos.append(order)
                order = None
        for q in pos:
            if q["reason"] is not None or q["fill_i"] > j:
                continue
            risk = q["entry"] - q["stop"]
            if risk <= 0:
                q["reason"], q["r"] = "bad_risk", NAN
            elif l[j] <= q["stop"]:
                q["reason"], q["r"] = "stop", -1.0
            elif h[j] >= q["target"]:
                q["reason"], q["r"] = "target", (q["target"] - q["entry"]) / risk
        tl = None
        if tg is not None:
            tl = tg.get(dd[min(j + 1, n - 1)], tg.get(dd[j]))
        elif target is not None and not isinstance(target, pd.Series):
            tl = float(target)
        if tl is not None:
            tl = side * tl if side < 0 else tl
        # array touches (daily arrays of the trade side) by bar j
        touch = [a for a in disc if a[4] <= j and l[j] <= a[2] and h[j] >= a[1]]
        if touch:
            last_touch = j
        if tl is not None and h[j] >= tl:
            order = None                                   # the HTF target was reached: arming stops, the move is over
            flag = not need_array
            continue
        if tl is None or c[j] >= o[j]:
            continue
        if bs is not None and bs.get(dd[min(j + 1, n - 1)], bs.get(dd[j], 0)) != side:
            continue
        if need_array and not flag:
            if touch:
                flag = True
            else:
                continue
        if need_mss:
            ref = last_touch if last_touch is not None else int(np.argmin(l[max(0, j - mss_lookback):j + 1])) + max(0, j - mss_lookback)
            if not _mss_since(h, l, c, ref, j):
                continue
        price = float(o[j]) if mode == "stop_open" else float(c[j])
        if order is not None:
            order["reason"] = "replaced"
            rows.append(order)
        order = dict(mode=mode, arm_i=j, fill_i=-1, price=price, entry=NAN, stop=float(l[j]) - tick, target=float(tl), r=NAN, reason=None)
    for q in pos:
        if q["reason"] is None:
            q["reason"] = "open"
            q["r"] = (c[-1] - q["entry"]) / (q["entry"] - q["stop"]) if q["entry"] > q["stop"] else NAN
    if order is not None:
        order["reason"] = "unfilled"
        rows.append(order)
    out = pd.DataFrame(rows + pos)
    if len(out):
        out.loc[out.fill_i < 0, "reason"] = out.loc[out.fill_i < 0, "reason"].fillna("unfilled")
        if side < 0:
            for k in ("price", "entry", "stop", "target"):
                out[k] = -out[k]
        out = out.sort_values(["arm_i"]).reset_index(drop=True)
    return out


def order_type_report(res: pd.DataFrame) -> pd.DataFrame:
    """E1-stop-vs-limit-ob-tradeoff (cc05_018 ~00:04:48): the orders of daily_candle_entries(modes=...) per order type - orders armed, fill rate, mean R and win rate of the fills."""
    g = []
    for m, x in res.groupby("mode"):
        f = x[x.fill_i >= 0]
        g.append(dict(mode=m, orders=int(len(x)), fills=int(len(f)), fill_rate=float(len(f) / len(x)) if len(x) else NAN, mean_r=float(f.r.mean()) if len(f) else NAN,
                      win_rate=float((f.r > 0).mean()) if len(f) else NAN))
    return pd.DataFrame(g)


# --------------------------------------------------------------------------------------------------------------
# M17-position-trade-checklist (160) and new-eight-hallmark-swing-checklist (170)
# --------------------------------------------------------------------------------------------------------------

def _trend_sign(sr: pd.Series, n: int = 20) -> int:
    v = sr.dropna().values.astype(float)
    if len(v) <= n:
        return 0
    return int(np.sign(v[-1] - v[-1 - n]))


def _efficiency(sr: pd.Series, n: int = 20) -> float:
    v = sr.dropna().values.astype(float)[-(n + 1):]
    if len(v) < n + 1:
        return NAN
    tot = float(np.abs(np.diff(v)).sum())
    return abs(float(v[-1] - v[0])) / tot if tot > 0 else 0.0


def _seasonal_side(seasonal: dict | None, day, months_ahead: int = 3) -> int:
    if not seasonal:
        return 0
    m = pd.Timestamp(day).month
    vals = [float(seasonal.get((m - 1 + k) % 12 + 1, 0.0)) for k in range(1, months_ahead + 1)]
    return int(np.sign(sum(vals)))


def donchian_levels(df_daily: pd.DataFrame, j: int, side: int = 1) -> tuple:
    """The 40- and 20-session extremes (lowest low for a long, highest high for a short) ending at session j inclusive."""
    if side > 0:
        x = df_daily["low"].values.astype(float)
        return float(x[max(0, j - 39):j + 1].min()), float(x[max(0, j - 19):j + 1].min())
    x = df_daily["high"].values.astype(float)
    return float(x[max(0, j - 39):j + 1].max()), float(x[max(0, j - 19):j + 1].max())


def position_checklist(day, side: int, df_daily: pd.DataFrame, row: dict | None = None, seasonal: dict | None = None, intermarket: dict | None = None, yields: pd.Series | None = None,
                       arrays=None, expect: dict | None = None) -> dict:
    """M17-position-trade-checklist (cc05_018 ~00:02:49), report only: which of the eight steps hold for a position trade in direction `side` on `day` with the data we have. Each step is
    (True | False | None, detail); None = no data. 1 seasonal tendency of the next 3 months (`seasonal` = {month: +1 / -1}); 2 intermarket confirmation from >= 3 of the 4 asset classes
    (`intermarket` = {stocks, rates, commodities, currencies: daily close Series}, `expect` = the trend sign that supports a long per class, default +1; 20-session net move); 3 yields confirm
    (`yields` Series: rising yields support a long currency [our interpretation]); 4 monthly / weekly PD arrays map the path (`row`: an htf.table row, or `arrays` with tf M / W in the trade
    direction); 5 the daily quarterly-shift / intermediate swing: the table's `qs_due` when built; 6 a daily PD array frames the entry (`arrays` with tf D of the trade side); 7 stop-or-limit,
    risk <= 1 %: always (a choice); 8 the 40 -> 20-day trail levels from df_daily. 'tradeable' = a seasonal needs technical alignment (steps 4 or 6) [B23]."""
    d = pd.Timestamp(day)
    dd = _dates(df_daily)
    j = max((k for k, x in enumerate(dd) if x < _norm(d)), default=None)
    out: dict = {}
    sea = _seasonal_side(seasonal, d)
    out[1] = (None if not seasonal else sea == side, f"seasonal {sea:+d}")
    if intermarket:
        ex = expect or {}
        agree = {k: _trend_sign(v[v.index < d]) == side * int(ex.get(k, 1)) for k, v in intermarket.items()}
        out[2] = (sum(agree.values()) >= 3, agree)
    else:
        out[2] = (None, "no data")
    if yields is not None:
        yt = _trend_sign(yields[yields.index < d])
        out[3] = (yt == side, f"yields {yt:+d}")
    else:
        out[3] = (None, "no data")
    arr = [_arr_side(a, side) for a in (arrays or ())]
    rowv = None
    if row is not None:
        up, dn = row.get("wk_draw_up", NAN), row.get("wk_draw_dn", NAN)
        v = up if side > 0 else dn
        rowv = (v == v) if v is not None else None
    mw = [a for a in arr if a[0] == "prem" and a[3] in ("M", "W")]
    out[4] = ((bool(mw) or bool(rowv)) if (arrays is not None or row is not None) else None, f"{len(mw)} M/W premium arrays")
    qs = None if row is None else row.get("qs_due", None)
    out[5] = (None if qs is None else bool(qs), "qs_due")
    dd_arr = [a for a in arr if a[0] == "disc" and a[3] == "D"]
    out[6] = (bool(dd_arr) if arrays is not None else None, f"{len(dd_arr)} daily arrays")
    out[7] = (True, "stop or limit, risk <= 1 %")
    if j is not None and j >= 19:
        l40, l20 = donchian_levels(df_daily, j, side)
        out[8] = (True, (l40, l20))
    else:
        out[8] = (None, "no data")
    tech = bool(out[4][0]) or bool(out[6][0])
    out["tradeable"] = bool(out[1][0]) and tech if out[1][0] is not None else tech
    return out


def hallmarks(day, side: int, df_daily: pd.DataFrame, intermarket: dict | None = None, seasonal: dict | None = None, expect: dict | None = None, trend_er: float = 0.3) -> dict:
    """new-eight-hallmark-swing-checklist (cc06_007 ~00:20:56), report only: the eight hallmarks of an explosive swing for direction `side` on `day`. Scored with what the data allows: 1 trending profile
    (>= 2 of the 4 asset classes with a 20-session efficiency ratio >= `trend_er`, one of stocks / commodities and one of currencies / rates), 2 intermarket confluence (>= 3 of 4 trend signs support
    the direction), 5 seasonal tendency, 6 volatility contraction (the last completed daily bar is an inside bar or has the smallest range of the last 5 - no direction), 8 Williams %R(15) on the
    daily bars (the buy / sell area). 3 COT, 4 open interest and 7 news headlines are missing (None). `score` = the hallmarks that hold, `evaluable` = those with data. Any threshold is [our interpretation]."""
    d = pd.Timestamp(day)
    dd = _dates(df_daily)
    j = max((k for k, x in enumerate(dd) if x < _norm(d)), default=None)
    res: dict = {i: None for i in range(1, 9)}
    if intermarket:
        er = {k: _efficiency(v[v.index < d]) for k, v in intermarket.items()}
        tr = {k for k, x in er.items() if x == x and x >= trend_er}
        res[1] = len(tr) >= 2 and bool(tr & {"stocks", "commodities"}) and bool(tr & {"currencies", "rates"})
        ex = expect or {}
        res[2] = sum(1 for k, v in intermarket.items() if _trend_sign(v[v.index < d]) == side * int(ex.get(k, 1))) >= 3
    if seasonal:
        res[5] = _seasonal_side(seasonal, d) == side
    if j is not None and j >= 5:
        h, l, c = (df_daily[k].values.astype(float) for k in ("high", "low", "close"))
        rng = h - l
        inside = h[j] <= h[j - 1] and l[j] >= l[j - 1]
        res[6] = bool(inside or rng[j] <= rng[j - 4:j + 1].min() + 1e-12)
        if j >= 14:
            res[8] = int(BH3.wpr_daily_state(h[:j + 1], l[:j + 1], c[:j + 1], 15)[-1]) == side
    ev = [k for k, v in res.items() if v is not None]
    return dict(hallmarks=res, score=int(sum(1 for k in ev if res[k])), evaluable=len(ev), missing=[k for k, v in res.items() if v is None])


# --------------------------------------------------------------------------------------------------------------
# the 4h swing execution (161, 162, 164-169)
# --------------------------------------------------------------------------------------------------------------

def dealing_range(h, l, k: int, side: int, lookback: int = 60) -> tuple:
    """A21-swing-short-premium-of-major-range (cc06_005 ~00:11:36): the dealing range of a 4h swing entry at session k (sessions < k only). Short: the highest high of the last `lookback` sessions to
    the lowest low since it; long: the lowest low to the highest high since it. Returns (low, high, eq); eq = NaN when the range is degenerate (the extreme is the last session)."""
    a = max(0, k - lookback)
    if k - a < 2:
        return NAN, NAN, NAN
    hh, ll = h[a:k], l[a:k]
    if side < 0:
        q = int(np.argmax(hh))
        lo = float(ll[q:].min())
        hi = float(hh[q])
    else:
        q = int(np.argmin(ll))
        hi = float(hh[q:].max())
        lo = float(ll[q])
    if hi <= lo:
        return NAN, NAN, NAN
    return lo, hi, (lo + hi) / 2


def sequence_states(df_4h: pd.DataFrame, bias_ok, disp_mult: float = 1.5, side: int = 1) -> list:
    """M17-swing-sequence-condition-impulse-retrace (cc06_003 ~00:14:18): the state per 4h bar - "none" (no HTF condition), "condition" (the HTF bias agrees, no impulse yet), "impulse" (a displacement bar
    - range >= `disp_mult` x the mean range of the 20 bars before it, closing with the trade - made the leg away from its origin, the lowest low of the 10 bars before it), "retrace" (the first bar
    closing against the trade after the impulse high, until the leg's high is exceeded again, which is a new impulse). `bias_ok` = a list of bool per bar (the condition)."""
    o, h, l, c = _side_bars(df_4h, side)
    rng = h - l
    st = []
    cur = "none"
    leg_hi = NAN
    for j in range(len(c)):
        if not bias_ok[j]:
            cur = "none"
            leg_hi = NAN
            st.append(cur)
            continue
        if cur == "none":
            cur = "condition"
        mean = rng[max(0, j - 20):j].mean() if j >= 5 else NAN
        if mean == mean and rng[j] >= disp_mult * mean and c[j] > o[j] and cur in ("condition", "retrace"):
            cur = "impulse"
            leg_hi = h[j]
        elif cur == "impulse":
            if h[j] > leg_hi:
                leg_hi = h[j]
            elif c[j] < o[j]:
                cur = "retrace"
        elif cur == "retrace" and h[j] > leg_hi:
            cur = "impulse"
            leg_hi = h[j]
        st.append(cur)
    return st


def swing_entries(df_4h: pd.DataFrame, df_daily: pd.DataFrame, arrays: list, side: int = 1, bias=None, mwd=None, consolidation=None, dxy=None, need_mwd: bool = False,
                  no_range_turtle: bool = False, need_eq: bool = True, sequence: bool = False, bounce_check: bool = False, bounce_bars: int = 12, entry_types=("ob",), disp_mult: float = 1.5,
                  lookback_days: int = 378, min_rr: float = 3.0, range_lookback: int = 60, tick: float = 0.0, mt_ob_tf: str = "M", wait_bars: int = 30) -> pd.DataFrame:
    """The 4h swing execution of the M17 / B10 swing lessons (cc06_001 ~00:17:36, ~00:19:14, cc06_003 ~00:14:18, cc06_004 ~00:21:34, ~00:38:37, cc06_005 ~00:11:01, ~00:11:36, cc06_006 ~00:23:25), research.
    Long (side=1; side=-1 mirrors every price). Framework defaults (167): 4h execution; `arrays` = htf.Arr-like objects (kind / top / bottom / ce / tf M, W or D / known = the daily position of the first
    session they may be used) not older than `lookback_days` (18 months); a 4h bullish OB (a down-close 4h candle that a later bar trades above) is a buy limit at its OPEN with the stop `tick` beyond
    its low; the target is the first opposing M / W array above (its bottom); orders below `min_rr` reward:risk are skipped.
      entry_types  "ob" (the 4h OB), "turtle" (a 4h sweep of the last confirmed swing low that closes back above it; market entry at the close), "mt_4h_ob" (169: the OB candle's range holds the
                   mean threshold of a monthly (`mt_ob_tf`) bearish OB array of the opposite side - the 4h up-close candle that runs above the monthly MT, mirrored)
      location (161)  the order price lies inside a M / W / D discount array of the trade side (ranked M > W > D, `array_tf`); with `dxy` (date-indexed Series, +1 = dollar strength) a long needs
                   dxy <= 0 (FX / metals only: the index bot omits it)
      need_eq (168)   the order price lies on the discount side of the daily dealing range (dealing_range)
      need_mwd (166)  the table's mwd direction (`mwd`, date-indexed) equals `side` on the order's day
      no_range_turtle (162)  a turtle entry is skipped where `consolidation` (date-indexed 0 / 1) is 1
      sequence (164)  entries only in the "retrace" state of sequence_states (`bias` the condition, date-indexed +1 / -1)
      bounce_check (165)  after a fill, if no 4h swing high above the previous one forms within `bounce_bars`, the next entry must sit in a daily bullish OB array until one does
    Returns one row per order: type, arm_i, fill_i (-1 = not filled within `wait_bars`), price, stop, target, rr, array_tf, state, r, reason."""
    o, h, l, c = _side_bars(df_4h, side)
    do, dh, dl, dc = _side_bars(df_daily, side)
    n = len(c)
    dd = _dates(df_daily)
    dpos = {d_: k for k, d_ in enumerate(dd)}
    bdate = [_norm(x) for x in df_4h.index]
    kday = [dpos.get(d_) for d_ in bdate]
    arr = [_arr_side(a, side) for a in arrays]
    rank = {"M": 3, "W": 2, "D": 1}
    ar_raw = list(arrays)
    bs = None if bias is None else {_norm(k): int(v) for k, v in bias.items()}
    mw = None if mwd is None else {_norm(k): int(v) for k, v in mwd.items()}
    cons = None if consolidation is None else {_norm(k): int(v) for k, v in consolidation.items()}
    dx = None if dxy is None else {_norm(k): int(v) for k, v in dxy.items()}
    cond = [bool(bs is None or bs.get(bdate[j], 0) == side) for j in range(n)]
    states = sequence_states(df_4h, cond, disp_mult, side) if sequence else ["none"] * n
    ph, pl = L.pivots(h, l, 1)
    orders: list = []
    seen: set = set()
    weak = False
    weak_ref = NAN
    pending_conf = None                                    # (deadline bar, prior swing high) after a fill
    rows = []
    last_dn = None                                         # the last down-close bar (the OB candidate)
    for j in range(n):
        k = kday[j]
        if k is None:
            continue
        # fills of standing orders on bar j
        for od in orders:
            if od["fill_i"] < 0 and od["reason"] is None and j > od["arm_i"]:
                if j - od["arm_i"] > wait_bars:
                    od["reason"] = "unfilled"
                elif od["type"] == "turtle" or l[j] <= od["price"]:
                    od["fill_i"], od["entry"] = j, (float(o[j]) if od["type"] == "turtle" else min(od["price"], o[j]))
                    if bounce_check:
                        sh = [q.price for q in ph if q.known <= j - 1]
                        pending_conf = (j + bounce_bars, sh[-1] if sh else h[j])
            if od["fill_i"] >= 0 and od["reason"] is None and od["fill_i"] <= j:
                risk = od["entry"] - od["stop"]
                if risk <= 0:
                    od["reason"] = "bad_risk"
                elif l[j] <= od["stop"]:
                    od["reason"], od["r"] = "stop", -1.0
                elif h[j] >= od["target"]:
                    od["reason"], od["r"] = "target", (od["target"] - od["entry"]) / risk
        if bounce_check:
            if pending_conf is not None:
                if h[j] > pending_conf[1]:
                    weak, pending_conf = False, None
                elif j >= pending_conf[0]:
                    weak, weak_ref, pending_conf = True, pending_conf[1], None
            elif weak and h[j] > weak_ref:
                weak = False                                 # a higher 4h high finally formed: the 4h level is confirmed again
        # the entry candidates armed on the closed bar j
        cands = []
        if "ob" in entry_types or "mt_4h_ob" in entry_types:
            # a bullish OB: the last down-close bar before j that bar j trades above (validated now)
            if last_dn is not None and h[j] > h[last_dn] and last_dn not in seen:
                seen.add(last_dn)
                cands.append(("ob" if "ob" in entry_types else "mt_4h_ob", float(o[last_dn]), float(l[last_dn]) - tick, last_dn))
                if "mt_4h_ob" in entry_types and "ob" in entry_types:
                    cands.append(("mt_4h_ob", float(o[last_dn]), float(l[last_dn]) - tick, last_dn))
        if "turtle" in entry_types:
            sl = [q for q in pl if q.known <= j - 1]
            if sl and l[j] < sl[-1].price and c[j] > sl[-1].price:
                cands.append(("turtle", float(c[j]), float(l[j]) - tick, j))
        if c[j] < o[j]:
            last_dn = j
        for typ, price, stop, src in cands:
            live = [a for a, ra in zip(arr, ar_raw) if a[4] <= k and k - a[4] <= lookback_days]
            ins = [a for a in live if a[0] == "disc" and a[1] <= price <= a[2]]
            tfs = sorted({a[3] for a in ins}, key=lambda t: -rank.get(t, 0))
            od = dict(type=typ, arm_i=j, fill_i=-1, price=price, entry=NAN, stop=stop, target=NAN, rr=NAN, array_tf=tfs[0] if tfs else "", state=states[j], r=NAN, reason=None)
            why = None
            if not ins:
                why = "no_discount_array"
            elif need_mwd and mw is not None and mw.get(bdate[j], 0) != side:
                why = "mwd"
            elif typ == "turtle" and no_range_turtle and cons is not None and cons.get(bdate[j], 0):
                why = "range_turtle"
            elif sequence and states[j] != "retrace":
                why = "sequence_" + states[j]
            elif dx is not None and dx.get(bdate[j], 0) * side > 0:
                why = "dxy"
            elif need_eq:
                lo_, hi_, eq_ = dealing_range(dh, dl, k, 1, range_lookback)
                if eq_ == eq_ and price > eq_:
                    why = "premium"
            if why is None and bounce_check and weak:
                if not any(a[0] == "disc" and a[3] == "D" and a[1] <= price <= a[2] and _araw(ar_raw[arr.index(a)], "typ") == "ob" for a in ins):
                    why = "weak_bounce_needs_daily_ob"
            if why is None and typ == "mt_4h_ob":
                mt_ok = False
                for a, ra in zip(arr, ar_raw):
                    if a[3] == mt_ob_tf and a[0] == "disc" and a[4] <= k and _araw(ra, "typ") == "ob":          # an array with no typ is not an order block
                        ce_raw = _araw(ra, "ce", NAN)
                        ce = (a[1] + a[2]) / 2 if ce_raw is None or ce_raw != ce_raw else (side * float(ce_raw))
                        if l[src] <= ce <= h[src]:
                            mt_ok = True
                if not mt_ok:
                    why = "not_at_monthly_mt"
            tg = [a[1] for a, ra in zip(arr, ar_raw) if a[0] == "prem" and a[3] in ("M", "W") and a[4] <= k and k - a[4] <= lookback_days and a[1] > price]
            if why is None and not tg:
                why = "no_target"
            if why is None:
                od["target"] = min(tg)
                risk = price - stop
                od["rr"] = (od["target"] - price) / risk if risk > 0 else NAN
                if not (od["rr"] == od["rr"] and od["rr"] >= min_rr):
                    why = "rr"
            if why is not None:
                od["reason"] = "skip_" + why
                od["target"] = od["target"] if od["target"] == od["target"] else NAN
                rows.append(od)
                continue
            orders.append(od)
    for od in orders:
        if od["reason"] is None:
            if od["fill_i"] < 0:
                od["reason"] = "unfilled"
            else:
                od["reason"] = "open"
                od["r"] = (c[-1] - od["entry"]) / (od["entry"] - od["stop"]) if od["entry"] > od["stop"] else NAN
    out = pd.DataFrame(rows + orders)
    if len(out):
        out = out.sort_values("arm_i", kind="stable").reset_index(drop=True)
        if side < 0:
            for k in ("price", "entry", "stop", "target"):
                out[k] = -out[k]
    return out
