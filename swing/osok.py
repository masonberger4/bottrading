"""One Shot One Kill (Month 7, cc07_001-008): the default swing model (spec section 5).

One trade per week. Bias from the monthly/weekly order flow (MWD sequential, cases A/B/C);
entries on 1h bars inside the London / NY kill zones, Monday to Wednesday, at weekly / daily /
4h discount arrays (premium for shorts); target = the opposing PD array one timeframe below the
framing array, converging with a 1.27 / 1.68 / 100% projection of the early-week swing; partials
on the way; Million Dollar management (cc06_008 ~16:20); flat by Friday 16:00 ET.

Bars are closed-candle only: a decision at 1h bar k uses bars whose `end` <= start of bar k;
orders placed then can fill inside bar k. Inside one bar the stop is assumed to fill before any
target (conservative).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

import numpy as np
import pandas as pd

from mentorship import calendar as C
from mentorship import levels as L

from . import bias as Bi
from .arrays import ORDER, ORDER_SLIDE, STOP_TYPES, TF_RANK, Book

RANK_TF = {v: k for k, v in TF_RANK.items()}
LOWER = {"M": "W", "W": "D", "D": "4h"}          # target one timeframe below (cc07_003 ~00:02:40)
WEIGHT = {"1h": 1, "4h": 2, "D": 3, "W": 4, "M": 5}


@dataclass(frozen=True)
class Params:
    cutoff: float = 0.5               # no longs above this fraction of the 60-day body range (spec 12.2)
    kill_zones: tuple = (2, 3, 4, 8, 9, 10)   # 1h bars starting at these ET hours (London, NY) [our interp]
    entry_days: str = "mon_wed"       # "mon_wed" | "any" (Mon-Fri)
    order: str = "by_array"           # "by_array" (cc06_008) | "limit" (2023 E1)
    ob_entry: str = "high"            # "high" (fair) | "open" (conservative)
    mt: str = "range"                 # multi-candle OB mean threshold: "range" (2023) | "body" (CC)
    matrix_order: str = "spoken"      # "spoken" | "slide"
    stop: str = "swing"               # "swing" (beyond the sweep / swing low) | "array"
    target: str = "ict"               # "ict" (opposing array one TF lower) | "prev_week"
    fib_gate: bool = True             # target must converge with 1.27 / 1.68 / 1.0 projection
    fib_tol: float = 0.25             # x ADR5 [our interpretation]
    min_rr: float = 1.0               # objective at least this many R away [our interpretation]
    target_tfs: tuple = ()            # () = one timeframe below the framing array; else these (swing: W, M)
    min_stop_adr: float = 0.25        # stop at least this x ADR5 from entry [our interpretation]
    partials: tuple = (0.5, 0.25, 0.25)   # first array, second array, objective
    be_third: bool = True             # breakeven after the first partial AND price at 1/3 (spec 7)
    trail_at: float = 0.75            # trail under the latest 4h swing low from 75% of the objective
    scale_in: bool = True             # half first, add half if the next day fails to extend (cc07_008 ~29:33)
    skip_seek_destroy: bool = True
    cases: tuple = ("A", "B", "C")
    tfs: tuple = ("4h", "D", "W", "M")    # entry-array timeframes
    friday_exit_hour: int = 16
    tick: float = 0.25
    cost_pts: float = 0.3             # per side per unit: 1 tick slippage + commission [our interpretation]
    risk_usd: float = 1000.0


@dataclass
class Trade:
    side: int
    week: int
    entry_time: pd.Timestamp
    array: str
    case: str
    frame_tf: str
    lots: list = field(default_factory=list)          # [price, units ($ per point)]
    stop: float = 0.0
    risk_pts: float = 0.0
    objective: float = 0.0
    levels: list = field(default_factory=list)        # [(price, fraction)]
    exits: list = field(default_factory=list)         # [(time, price, units, reason)]
    partial_done: bool = False
    conviction: int = 0
    tags: dict = field(default_factory=dict)

    @property
    def units(self) -> float:
        return sum(u for _, u in self.lots) - sum(x[2] for x in self.exits)


class Prepared:
    def __init__(self, frames: dict, p: Params):
        self.f = frames
        self.p = p
        self.book = Book(frames, p.tfs, p.mt, p.ob_entry, p.tick)
        self.st = {tf: Bi.states(frames[tf]) for tf in ("4h", "D", "W", "M")}
        h1, d = frames["1h"], frames["D"]
        self.h1 = h1
        self.o, self.h, self.l, self.c = (h1[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        self.hour = pd.DatetimeIndex(h1.start).hour.to_numpy()
        self.wd = pd.DatetimeIndex(h1.day).weekday.to_numpy()        # session weekday
        self.h1_highs, self.h1_lows = L.pivots(self.h, self.l, n=1)
        f4 = frames["4h"]
        self.h4hi, self.l4 = L.pivots(f4.high.to_numpy(float), f4.low.to_numpy(float), n=1)
        dh, dl = d.high.to_numpy(float), d.low.to_numpy(float)
        self.adr5 = pd.Series(dh - dl).rolling(5).mean().to_numpy()
        body_hi = np.maximum(d.open, d.close).to_numpy(float)
        body_lo = np.minimum(d.open, d.close).to_numpy(float)
        self.r60_hi = pd.Series(body_hi).rolling(60, min_periods=20).max().to_numpy()
        self.r60_lo = pd.Series(body_lo).rolling(60, min_periods=20).min().to_numpy()
        self.order = ORDER_SLIDE if p.matrix_order == "slide" else ORDER


def _day_idx(pr: Prepared, t: pd.Timestamp) -> int:
    """Index of the last daily bar closed by t."""
    return int(pr.f["D"].end.searchsorted(t, side="right")) - 1


def _nested(pr: Prepared, j: int, k: int, tf: str, bull: bool) -> bool:
    """Array j sits at or inside an alive array of timeframe `tf` on the same side (cc06_004 ~4:01)."""
    b = pr.book
    m = b.alive(k) & (b.tf == TF_RANK[tf]) & (b.bull == bull)
    if not m.any():
        return False
    return bool(((b.bottom[m] <= b.top[j]) & (b.top[m] >= b.bottom[j])).any())


def _conviction(pr: Prepared, k: int, level: float) -> int:
    b = pr.book
    m = b.alive(k) & (b.bottom <= level) & (b.top >= level)
    return int(sum(WEIGHT[RANK_TF[r]] for r in b.tf[m]))


def _sweep_stop(pr: Prepared, k: int, below: float, side: int) -> float | None:
    """Nearest known 1h swing low below `below` (high above, shorts), 1 tick beyond."""
    p = pr.p
    best = None
    if side > 0:
        for q in pr.h1_lows:
            if q.known < k and q.price < below and (best is None or q.price > best):
                best = q.price
        return None if best is None else best - p.tick
    for q in pr.h1_highs:
        if q.known < k and q.price > below and (best is None or q.price < best):
            best = q.price
    return None if best is None else best + p.tick


def _targets(pr: Prepared, k: int, entry: float, stop: float, side: int, frame_tf: str,
             week: int, fulcrum: float | None, swing_ext: float | None):
    """Objective and partial levels. Long: premium arrays (bear kind) and old highs above."""
    p, b = pr.p, pr.book
    risk = abs(entry - stop)
    want_bull = side < 0
    m = b.fresh(k) & (b.bull == want_bull)
    near = np.where(b.bull, b.top, b.bottom)
    ahead = (near - entry) * side > p.min_rr * risk
    if p.target == "prev_week":
        w = pr.f["W"]
        if week < 1:
            return None
        lvl = float(w.high.iloc[week - 1] if side > 0 else w.low.iloc[week - 1])
        if (lvl - entry) * side <= p.min_rr * risk:
            return None
        obj = lvl
    else:
        if p.target_tfs:
            cand = m & ahead & np.isin(b.tf, [TF_RANK[x] for x in p.target_tfs])
        else:
            cand = m & ahead & (b.tf == TF_RANK[LOWER[frame_tf]])
        if not cand.any():
            return None
        idx = np.flatnonzero(cand)
        prices = near[idx]
        if p.fib_gate:
            if fulcrum is None or swing_ext is None:
                return None
            rng = abs(fulcrum - swing_ext)
            proj = [fulcrum + side * rng * f for f in (0.27, 0.68, 1.0)]
            di = _day_idx(pr, pr.h1.start.iloc[k])
            tol = p.fib_tol * (pr.adr5[di] if di >= 0 and pr.adr5[di] == pr.adr5[di] else rng)
            ok = np.array([min(abs(x - q) for q in proj) <= tol for x in prices])
            if not ok.any():
                return None
            idx, prices = idx[ok], prices[ok]
        obj = float(prices[np.argmin((prices - entry) * side)])
    inter = m & ((near - entry) * side > 0) & ((obj - near) * side > 0) & (b.tf <= TF_RANK["4h"])
    mids = sorted(set(near[inter].tolist()), key=lambda x: (x - entry) * side)
    fr = p.partials
    levels = []
    for x, f in zip(mids[:len(fr) - 1], fr[:-1]):
        levels.append((float(x), f))
    levels.append((obj, round(1.0 - sum(f for _, f in levels), 6)))
    return obj, levels


def _seek_destroy(pr: Prepared, wk_days: list, di_mon: int, di_tue: int) -> bool:
    """[our interpretation] Seek & Destroy conditions (cc07_003 ~00:33:00): a week waiting on
    FOMC or NFP, or a July/August week, whose Mon+Tue range is below 1x ADR5."""
    p = pr.p
    d = pr.f["D"]
    days = [x.date() for x in wk_days]
    news = any(C.DT.events(x) & {"fomc", "jobs"} for x in days)
    summer = days[0].month in (7, 8)
    if not (news or summer) or di_mon < 0 or di_tue < 0:
        return False
    rng = d.high.iloc[di_mon:di_tue + 1].max() - d.low.iloc[di_mon:di_tue + 1].min()
    adr = pr.adr5[di_mon - 1] if di_mon >= 1 else np.nan
    return bool(rng < adr)


def run(frames: dict, p: Params | None = None) -> pd.DataFrame:
    p = p or Params()
    pr = Prepared(frames, p)
    rows = []
    W, D, h1 = frames["W"], frames["D"], frames["1h"]
    for w in range(len(W)):
        t0 = W.start.iloc[w]
        k_a = int(h1.start.searchsorted(t0, side="left"))
        k_b = int(h1.start.searchsorted(W.end.iloc[w], side="left"))
        if k_b - k_a < 10:
            continue
        tr = _week(pr, w, k_a, k_b)
        if tr is not None:
            rows.append(_row(pr, tr))
    return pd.DataFrame(rows)


def _week(pr: Prepared, w: int, k_a: int, k_b: int) -> Trade | None:
    p, b, F = pr.p, pr.book, pr.f
    W, D = F["W"], F["D"]
    t0 = W.start.iloc[w]
    md, _, _ = Bi.at(pr.st["M"], F["M"], t0)
    wd, wvia, wcorr = Bi.at(pr.st["W"], F["W"], t0)
    side = md if md != 0 else wd
    if side == 0 or wd == -side:
        return None
    wk_days = list(D.day[(D.day >= W.first_day.iloc[w]) & (D.day <= W.last_day.iloc[w])])
    sd_checked, sd = False, False
    pending = None          # armed stop-entry: dict(j, arm_k, ext)
    tr: Trade | None = None
    for k in range(k_a, k_b):
        t = pr.h1.start.iloc[k]
        wday = pr.wd[k]
        if tr is None:
            in_days = wday <= 2 if p.entry_days == "mon_wed" else wday <= 4
            if not in_days:
                if wday > 2 and p.entry_days == "mon_wed":
                    return None
                continue
            if wday == 2 and p.skip_seek_destroy and not sd_checked:
                sd_checked = True
                mon = [i for i, x in enumerate(D.day) if x == (wk_days[0] if wk_days else None)]
                di_mon = mon[0] if mon else -1
                sd = _seek_destroy(pr, wk_days, di_mon, di_mon + 1 if di_mon >= 0 else -1)
            if sd:
                return None
            # pending stop entry: trigger on a kill-zone bar trading back through the array
            if pending is not None:
                j = pending["j"]
                trig = (b.top[j] + p.tick) if side > 0 else (b.bottom[j] - p.tick)
                ext = pending["ext"]
                if pr.hour[k] in p.kill_zones and (pr.h[k] >= trig if side > 0 else pr.l[k] <= trig):
                    fill = max(trig, pr.o[k]) if side > 0 else min(trig, pr.o[k])
                    stop = ext - p.tick if side > 0 else ext + p.tick
                    tr = _open(pr, w, k, side, j, fill, stop, pending["case"], pending["frame"])
                    if tr is None:
                        pending = None
                        continue
                    if _manage(pr, tr, k, same_bar=True):
                        return tr
                    continue
                pending["ext"] = min(ext, pr.l[k]) if side > 0 else max(ext, pr.h[k])
                if (side > 0 and pr.c[k] < b.bottom[j]) or (side < 0 and pr.c[k] > b.top[j]):
                    pending = None          # closed through the array: idea failed
                continue
            if pr.hour[k] not in p.kill_zones:
                continue
            cand = _candidate(pr, k, t, side, wcorr)
            if cand is None:
                continue
            j, case, frame_tf = cand
            if p.order == "by_array" and b.typ[j] in STOP_TYPES:
                touched = (pr.l[k] <= b.top[j]) if side > 0 else (pr.h[k] >= b.bottom[j])
                if touched:
                    pending = {"j": j, "ext": pr.l[k] if side > 0 else pr.h[k], "case": case, "frame": frame_tf}
                continue
            lvl = b.entry[j]
            hit = pr.l[k] <= lvl if side > 0 else pr.h[k] >= lvl
            if not hit:
                continue
            fill = min(lvl, pr.o[k]) if side > 0 else max(lvl, pr.o[k])
            stop = _stop_for(pr, k, j, side)
            if stop is None:
                continue
            tr = _open(pr, w, k, side, j, fill, stop, case, frame_tf)
            if tr is None:
                continue
            if _manage(pr, tr, k, same_bar=True):
                return tr
            continue
        # scale-in: add half at the close of the first later session (Mon-Wed) that fails to
        # extend beyond the entry session's extreme
        ke = tr.tags["k_entry"]
        if p.scale_in and len(tr.lots) == 1 and wday <= 2 and pr.hour[k] == 16 and pr.wd[k] != pr.wd[ke]:
            di = _day_idx(pr, pr.h1.end.iloc[k])
            dl, dh = D.low.iloc[di], D.high.iloc[di]
            sess = D.day == pr.h1.day.iloc[ke]
            el, eh = float(D.low[sess].iloc[0]), float(D.high[sess].iloc[0])
            failed = dl > el if side > 0 else dh < eh
            px = pr.c[k]
            if failed and (px - tr.stop) * side > p.tick:
                tr.lots.append([px, 0.5 * p.risk_usd / abs(px - tr.stop)])
                tr.tags["added"] = True
        if _manage(pr, tr, k):
            return tr
        if pr.wd[k] == 4 and pr.hour[k] == p.friday_exit_hour - 1:
            tr.exits.append((pr.h1.end.iloc[k], pr.c[k], tr.units, "friday"))
            return tr
    if tr is not None and tr.units > 1e-12:
        k = k_b - 1
        tr.exits.append((pr.h1.end.iloc[k], pr.c[k], tr.units, "week_end"))
        return tr
    return tr


def _candidate(pr: Prepared, k: int, t, side: int, wcorr: bool):
    """Best discount array (premium for shorts) for a resting order at 1h bar k."""
    p, b, F = pr.p, pr.book, pr.f
    dd, dvia, dcorr = Bi.at(pr.st["D"], F["D"], t)
    if wcorr:
        case = "C"
    elif dd == side and not dcorr:
        case = "A"
    else:
        case = "B"
        if dd == -side and dvia == "breaker":
            return None              # daily bearish breaker forming: avoid (cc06_004 ~5:51)
    if case not in p.cases:
        return None
    di = _day_idx(pr, t)
    if di < 0 or pr.r60_hi[di] != pr.r60_hi[di]:
        return None
    lo, hi = pr.r60_lo[di], pr.r60_hi[di]
    px = pr.c[k - 1] if k > 0 else pr.o[k]
    bull = side > 0
    m = b.fresh(k) & (b.bull == bull) & np.isin(b.tf, [TF_RANK[x] for x in p.tfs])
    lvl = b.entry
    m &= (lvl < px) if bull else (lvl > px)
    pos = (lvl - lo) / max(hi - lo, 1e-9)
    m &= (pos < p.cutoff) if bull else (pos > 1 - p.cutoff)
    if not m.any():
        return None
    idx = np.flatnonzero(m)
    idx = idx[np.argsort(-(lvl[idx]) if bull else lvl[idx], kind="stable")]   # nearest first
    for j in idx:
        tf = RANK_TF[b.tf[j]]
        in_m = tf == "M" or _nested(pr, j, k, "M", bull)
        in_w = tf == "W" or _nested(pr, j, k, "W", bull)
        if case == "C" and not in_m:
            continue
        if case == "B" and not (in_w or in_m):
            continue
        frame = "M" if in_m else ("W" if in_w else "D")
        return int(j), case, frame
    return None


def _stop_for(pr: Prepared, k: int, j: int, side: int) -> float | None:
    p, b = pr.p, pr.book
    edge = b.bottom[j] if side > 0 else b.top[j]
    if b.typ[j] == "old":
        edge = b.entry[j]
    if p.stop == "array":
        return edge - p.tick if side > 0 else edge + p.tick
    s = _sweep_stop(pr, k, edge, side)
    if s is None:
        s = edge - p.tick if side > 0 else edge + p.tick
    return s


def _widen(pr: Prepared, k: int, fill: float, stop: float, side: int) -> float:
    """[our interpretation] swing stops sit beyond the liquidity, never a few ticks away:
    at least `min_stop_adr` x ADR5 from the fill."""
    p = pr.p
    di = _day_idx(pr, pr.h1.start.iloc[k])
    adr = pr.adr5[di] if di >= 0 else np.nan
    if adr != adr:
        return stop
    far = fill - side * p.min_stop_adr * adr
    far = np.floor(far / p.tick) * p.tick if side > 0 else np.ceil(far / p.tick) * p.tick
    return float(min(stop, far) if side > 0 else max(stop, far))


def _open(pr: Prepared, w: int, k: int, side: int, j: int, fill: float, stop: float,
          case: str, frame_tf: str) -> Trade | None:
    p, F = pr.p, pr.f
    stop = _widen(pr, k, fill, stop, side)
    risk = (fill - stop) * side
    if risk <= p.tick:
        return None
    # early-week swing for the projection: fulcrum = intra-week extreme against the trade so
    # far (long: the week's high before this bar), swing extreme = the low into the entry
    W = F["W"]
    ka = int(pr.h1.start.searchsorted(W.start.iloc[w], side="left"))
    if k > ka:
        fulcrum = float(pr.h[ka:k].max() if side > 0 else pr.l[ka:k].min())
    else:
        fulcrum = None
    ext = float(min(pr.l[ka:k + 1].min(), fill) if side > 0 else max(pr.h[ka:k + 1].max(), fill))
    tg = _targets(pr, k, fill, stop, side, frame_tf, w, fulcrum, ext)
    if tg is None:
        return None
    obj, levels = tg
    units = (0.5 if p.scale_in else 1.0) * p.risk_usd / risk
    b = pr.book
    tr = Trade(side, w, pr.h1.start.iloc[k], f"{RANK_TF[b.tf[j]]}:{b.typ[j]}", case, frame_tf,
               [[fill, units]], stop, risk, obj, levels)
    tr.conviction = _conviction(pr, k, fill)
    tr.tags["k_entry"] = k
    tr.tags["entry_stop"] = stop
    return tr


def _manage(pr: Prepared, tr: Trade, k: int, same_bar: bool = False) -> bool:
    """Process 1h bar k for an open trade; True when flat."""
    p = pr.p
    s = tr.side
    hi, lo, op = pr.h[k], pr.l[k], pr.o[k]
    t_end = pr.h1.end.iloc[k]
    e0 = tr.lots[0][0]
    if (lo <= tr.stop) if s > 0 else (hi >= tr.stop):
        px = tr.stop if same_bar else (min(tr.stop, op) if s > 0 else max(tr.stop, op))
        tr.exits.append((t_end, px, tr.units, "stop" if not tr.partial_done else "stop_after_partial"))
        return True
    total = sum(u for _, u in tr.lots)
    while tr.levels:
        lvl, f = tr.levels[0]
        if (hi >= lvl) if s > 0 else (lo <= lvl):
            last = len(tr.levels) == 1
            u = tr.units if last else min(tr.units, f * total)
            tr.exits.append((t_end, lvl, u, "objective" if last else "partial"))
            tr.levels.pop(0)
            tr.partial_done = True
            if last or tr.units <= 1e-12:
                return True
        else:
            break
    dist = (tr.objective - e0) * s
    best = (hi - e0) * s if s > 0 else (e0 - lo)
    if p.be_third and tr.partial_done and best >= dist / 3:
        tr.stop = max(tr.stop, e0) if s > 0 else min(tr.stop, e0)
    if best >= p.trail_at * dist:
        swings = pr.l4 if s > 0 else pr.h4hi
        f4 = pr.f["4h"]
        kn = int(f4.end.searchsorted(t_end, side="right"))
        cand = [q.price for q in swings if q.known < kn]
        if cand:
            q = cand[-1]
            new = q - p.tick if s > 0 else q + p.tick
            tr.stop = max(tr.stop, new) if s > 0 else min(tr.stop, new)
    return False


def _row(pr: Prepared, tr: Trade) -> dict:
    p = pr.p
    s = tr.side
    gross = 0.0
    cost = 0.0
    entry_units = sum(u for _, u in tr.lots)
    avg = sum(px * u for px, u in tr.lots) / entry_units
    for _, px, u, _ in tr.exits:
        gross += (px - avg) * u * s
    cost = p.cost_pts * 2 * entry_units
    net = gross - cost
    risk_usd = sum(abs(px - tr.tags["entry_stop"]) * u for px, u in tr.lots)
    W, D = pr.f["W"], pr.f["D"]
    wk = D[(D.day >= W.first_day.iloc[tr.week]) & (D.day <= W.last_day.iloc[tr.week])]
    ext_day = wk.day.iloc[int(np.argmin(wk.low.values) if s > 0 else np.argmax(wk.high.values))]
    last = tr.exits[-1]
    return {"week": str(W.first_day.iloc[tr.week].date()), "side": s,
            "entry_time": tr.entry_time, "entry": round(tr.lots[0][0], 2),
            "stop": round(tr.tags["entry_stop"], 2), "objective": round(tr.objective, 2),
            "exit_time": last[0], "exit_reason": last[3], "array": tr.array, "case": tr.case,
            "frame_tf": tr.frame_tf, "added": bool(tr.tags.get("added")),
            "conviction": tr.conviction, "entry_weekday": tr.entry_time.strftime("%a"),
            "week_extreme_day": pd.Timestamp(ext_day).strftime("%a"),
            "hold_days": round((last[0] - tr.entry_time).total_seconds() / 86400, 2),
            "gross": round(gross, 2), "costs": round(cost, 2), "net": round(net, 2),
            "R": round(net / p.risk_usd, 3), "risk_usd": round(risk_usd, 2)}
