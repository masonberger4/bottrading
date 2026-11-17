"""Single ICT ideas tested on their own (2026-11-16, option E of PR #82). No engine: each idea is one plain rule on
ES / NQ / YM fixed-roll Databento bars, patterns on closed 5-minute bars, fills and exits followed on 1-minute bars.

    python ideas.py [--data DIR] [--out DIR]      -> DIR/trades.parquet      (then report.py)

Common to every idea
- One trade per idea variant per market per day (the first signal). Every trade risks $1,000 (no size cap,
  fractional contracts), so $ = R x 1,000. Costs $5 a side per contract (ES 0.10, NQ 0.25, YM 1.0 points a side).
- Market entries fill at the next 1-minute open. Limit entries need price to trade one tick through. A stop and a
  target in the same minute count as the stop. A limit fill cannot also hit its target in the fill minute.
- Risk floor: a stop closer than the 20-day median 5-minute bar range (09:30-16:00, earlier days only) is moved out
  to that distance, so costs cannot swamp tiny stops.
- r1 = the same trade with one extra tick of slippage on market entries and on stop and time exits.
- amb marks a trade whose stop and target were both inside one minute; r_best counts those as targets (upper bound).

Ideas (variants in brackets)
- sweep: a 5m bar trades through a level and closes back inside it, with no earlier close beyond the level that day.
  Enter against the sweep at the next open, stop one tick beyond the day's extreme.
  [level: previous day / previous week / Asia 18:00-00:00 / London 02:00-05:00 / AM 09:30-12:00 high and low]
  [window: London 02:00-05:00, AM 09:30-11:30, PM 13:30-15:30] [target 1R, 2R, 3R]
- fvg: three 5m bars leave a gap (bar 3 low above bar 1 high, or the mirror) and the middle bar is at least 1.5x the
  median bar. Limit order in the direction of the move, good for an hour, stop one tick beyond bars 1 and 2.
  [entry: gap edge / gap midpoint] [window] [target]
- ob: a 5m bar closes beyond the latest 3-bar swing high (low) for the first time. The order block is the last
  opposite-colour bar before it (within 10 bars). Limit order at the block, good for an hour, stop one tick beyond
  the lowest low (highest high) from the block to the break. [entry: block high-low edge / middle of body] [window] [target]
- time: no pattern, direction from an earlier move, stop = 20-day average size of the holding-window move.
  [lunch_rev: fade the 09:30-12:00 move from 13:30 to 16:00] [london_rev: fade the 02:00-05:00 move from 09:30 to 11:30]
  [lasthour_cont: follow the 09:30-15:00 move from 15:00 to 16:00] [tgif: Fridays, fade the week's move from 13:30 to 16:00]
- gap: fade an opening gap back toward the old close. Stop = one gap size (at least the risk floor).
  [ndog: 17:00 close to 18:00 open, Mon-Thu, out by 09:30] [nwog: Friday close to Sunday open, out by 09:30]
  [org: 16:14 close to 09:30 open, out by 16:00; org30: out by 10:00] [target: half fill / full fill]
  [_1805: the evening gaps measured and entered at the 18:05 open instead of the first print]
- gapgo: the mirror of gap (not an ICT idea, added because the Sunday fade lost heavily): trade with the gap, same
  stop distance, target half a gap or one gap further.
"""
import argparse
from pathlib import Path
import numpy as np, pandas as pd

NY = "America/New_York"
TICK = {"ES": 0.25, "NQ": 0.25, "YM": 1.0}
COST = {"ES": 0.10, "NQ": 0.25, "YM": 1.0}
WIN = {"LON": (480, 660, 930), "AM": (930, 1050, 1320), "PM": (1170, 1290, 1320)}   # session minutes from 18:00: start, end, time exit
RS = (1.0, 2.0, 3.0)


class Mkt:
    def __init__(s, sym, data):
        d = pd.read_parquet(Path(data) / f"{sym}_1min_db.parquet")
        d = d[d.index >= "2018-10-01"]
        s.sym, s.tick, s.cost = sym, TICK[sym], COST[sym]
        s.ts = d.index.asi8
        s.O, s.H, s.L, s.C = (d[c].to_numpy() for c in ("open", "high", "low", "close"))
        s.idx = d.index
        b = d.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        s.b = b
        s.bn = np.searchsorted(s.ts, (b.index + pd.Timedelta(minutes=5)).asi8)          # 1m index right after each 5m bar
        mins = b.index.hour * 60 + b.index.minute
        s.bsm = np.asarray((mins - 1080) % 1440)
        s.bday = np.asarray((b.index + pd.Timedelta(hours=6)).tz_localize(None).normalize())
        s.bo, s.bh, s.bl, s.bc = (b[c].to_numpy() for c in ("open", "high", "low", "close"))

    def at(s, days, hhmm, prev=False):
        """1m index of the first bar at or after clock time hh:mm on each day (prev: on the calendar day before)."""
        d = pd.DatetimeIndex(days) - pd.Timedelta(days=1) if prev else pd.DatetimeIndex(days)
        t = (d + pd.Timedelta(hours=hhmm // 100, minutes=hhmm % 100)).tz_localize(NY)
        return np.searchsorted(s.ts, t.asi8)

    def sim(s, i0, side, stop, i_end, min_risk, limit=None, i_exp=None, tgt_r=RS, tgt_px=None):
        O, H, L, C = s.O, s.H, s.L, s.C
        if i0 >= i_end:
            return []
        if limit is None:
            ie, entry, mkt = i0, O[i0], 1
        else:
            i_exp = min(i_exp, i_end)
            hit = (L[i0:i_exp] <= limit - s.tick) if side > 0 else (H[i0:i_exp] >= limit + s.tick)
            if not hit.any():
                return []
            ie = i0 + int(hit.argmax())
            entry, mkt = (min(limit, O[ie]) if side > 0 else max(limit, O[ie])), 0
        risk = (entry - stop) * side
        if risk < min_risk:
            risk = min_risk if risk > 0 or limit is None else None
            if risk is None:
                return []
            stop = entry - side * risk
        hs = (L[ie:i_end] <= stop) if side > 0 else (H[ie:i_end] >= stop)
        js = ie + int(hs.argmax()) if hs.any() else None
        a = ie if mkt else ie + 1
        out = []
        tg = [("%gR" % r, entry + side * r * risk) for r in tgt_r] if tgt_px is None else tgt_px
        for name, t in tg:
            if (t - entry) * side <= 0:
                continue
            ht = (H[a:i_end] >= t) if side > 0 else (L[a:i_end] <= t)
            jt = a + int(ht.argmax()) if ht.any() else None
            if js is not None and (jt is None or js <= jt):
                px = stop if js == ie else (min(stop, O[js]) if side > 0 else max(stop, O[js]))
                j, typ = js, "stop"
            elif jt is not None:
                px, j, typ = t, jt, "target"
            else:
                px, j, typ = C[i_end - 1], i_end - 1, "time"
            pts = (px - entry) * side
            amb = js is not None and jt is not None and js == jt          # stop and target in the same minute
            out.append(dict(tgt=name, side=side, entry_i=ie, entry=entry, stop=stop, exit_i=j, exit=px, how=typ, risk=risk, amb=amb,
                            r=(pts - 2 * s.cost) / risk, r_best=(((t - entry) * side if amb else pts) - 2 * s.cost) / risk, r1=(pts - 2 * s.cost - s.tick * (mkt + (typ != "target"))) / risk))
        return out


def run_market(sym, data):
    m = Mkt(sym, data)
    rows = []
    def add(res, day, idea, **kw):
        for r in res:
            r.update(market=sym, day=day, idea=idea, **kw)
            r["entry_ts"], r["exit_ts"] = m.idx[r.pop("entry_i")], m.idx[r.pop("exit_i")]
            rows.append(r)

    days = pd.DatetimeIndex(np.unique(m.bday))
    days = days[(days >= "2018-11-01") & (days.dayofweek < 5)]
    T = {k: m.at(days, k) for k in (0, 200, 500, 930, 1000, 1130, 1200, 1330, 1500, 1600, 1615, 1700)}
    T["p1800"] = m.at(days, 1800, prev=True)
    b0 = np.searchsorted(m.bday, days.values, "left"); b1 = np.searchsorted(m.bday, days.values, "right")
    n = len(days)
    full = (T[1600] - T[930]) >= 300                         # a full regular session (skips holidays and half days)
    rng = np.full(n, np.nan); dhi = np.full(n, np.nan); dlo = np.full(n, np.nan)
    for i in range(n):
        sl = slice(b0[i], b1[i]); sm = m.bsm[sl]
        if b1[i] > b0[i]:
            dhi[i], dlo[i] = m.bh[sl].max(), m.bl[sl].min()
        k = (sm >= 930) & (sm < 1320)
        if full[i] and k.any():
            rng[i] = np.median(m.bh[sl][k] - m.bl[sl][k])
    mr = pd.Series(rng).rolling(20, min_periods=10).median().shift(1).to_numpy()
    wk = np.asarray((days - pd.to_timedelta(days.dayofweek, unit="D")).values)
    wtab = pd.DataFrame({"wk": wk, "hi": dhi, "lo": dlo, "o": m.O[np.minimum(T["p1800"], len(m.O) - 1)]}).groupby("wk").agg(hi=("hi", "max"), lo=("lo", "min"), o=("o", "first"))
    pwh, pwl = wtab.hi.shift(1).reindex(wk).to_numpy(), wtab.lo.shift(1).reindex(wk).to_numpy()
    wopen = wtab.o.reindex(wk).to_numpy()
    px = lambda k: m.O[np.minimum(T[k], len(m.O) - 1)]
    P = {k: px(k) for k in (200, 500, 930, 1200, 1330, 1500)}
    c1600 = m.C[T[1600] - 1]
    mv = {"lunch_rev": np.abs(c1600 - P[1330]), "london_rev": np.abs(m.C[T[1130] - 1] - P[930]), "lasthour_cont": np.abs(c1600 - P[1500])}
    mv = {k: pd.Series(np.where(full, v, np.nan)).rolling(20, min_periods=10).mean().shift(1).to_numpy() for k, v in mv.items()}
    mv["tgif"] = mv["lunch_rev"]

    for i in range(1, n):
        if not full[i] or np.isnan(mr[i]) or b1[i] - b0[i] < 150:
            continue
        day, f = days[i], mr[i]
        sl = slice(b0[i], b1[i])
        sm, o, h, l, c, nx = m.bsm[sl], m.bo[sl], m.bh[sl], m.bl[sl], m.bc[sl], m.bn[sl]
        nb = len(sm)
        iend = {930: T[930][i], 1320: T[1600][i]}
        def band(a, z):
            k = (sm >= a) & (sm < z)
            return (h[k].max(), l[k].min()) if k.any() else (np.nan, np.nan)
        lev = {"PD": (dhi[i - 1], dlo[i - 1], 0), "PW": (pwh[i], pwl[i], 0), "ASIA": band(0, 360) + (360,),
               "LON": band(480, 660) + (660,), "AMS": band(930, 1080) + (1080,)}
        cummax, cummin = np.maximum.accumulate(h), np.minimum.accumulate(l)
        ccmax, ccmin = np.maximum.accumulate(c), np.minimum.accumulate(c)
        # swings (3-bar), confirmed one bar later
        sh = np.zeros(nb, bool); slo = np.zeros(nb, bool)
        sh[1:-1] = (h[1:-1] > h[:-2]) & (h[1:-1] > h[2:]); slo[1:-1] = (l[1:-1] < l[:-2]) & (l[1:-1] < l[2:])
        big = (h - l) >= 1.5 * f

        for w, (w0, w1, wx) in WIN.items():
            ks = np.where((sm >= w0) & (sm <= w1 - 5))[0]
            if not len(ks):
                continue
            ie = iend[wx]
            # ---- sweep
            for name, (hi, lo, ready) in lev.items():
                if np.isnan(hi) or ready > w0:
                    continue
                first = np.searchsorted(sm, ready)               # bars from which the level exists
                for k in ks:
                    prior_hi = ccmax[k - 1] if k > first else -np.inf
                    prior_lo = ccmin[k - 1] if k > first else np.inf
                    if h[k] > hi and c[k] < hi and prior_hi <= hi:
                        add(m.sim(nx[k], -1, h[first:k + 1].max() + m.tick, ie, f), day, "sweep", var=f"{name}_{w}"); break
                    if l[k] < lo and c[k] > lo and prior_lo >= lo:
                        add(m.sim(nx[k], 1, l[first:k + 1].min() - m.tick, ie, f), day, "sweep", var=f"{name}_{w}"); break
            # ---- fvg
            for k in ks:
                if k < 2 or not big[k - 1]:
                    continue
                if l[k] > h[k - 2]:
                    side, edge, far, stop = 1, l[k], h[k - 2], min(l[k - 2], l[k - 1]) - m.tick
                elif h[k] < l[k - 2]:
                    side, edge, far, stop = -1, h[k], l[k - 2], max(h[k - 2], h[k - 1]) + m.tick
                else:
                    continue
                for en, lim in (("edge", edge), ("mid", (edge + far) / 2)):
                    add(m.sim(nx[k], side, stop, ie, f, limit=lim, i_exp=nx[k] + 60), day, "fvg", var=f"{en}_{w}")
                break
            # ---- order block
            for k in ks:
                if k < 4:
                    continue
                done = False
                for side in (1, -1):
                    sw = np.where(sh[:k - 1] if side > 0 else slo[:k - 1])[0]      # swing at j confirmed at j+1 <= k-1
                    if not len(sw):
                        continue
                    j = sw[-1]; lvl = h[j] if side > 0 else l[j]
                    brk = c[k] > lvl if side > 0 else c[k] < lvl
                    prev = (c[j + 1:k] <= lvl).all() if side > 0 else (c[j + 1:k] >= lvl).all()
                    if not (brk and prev):
                        continue
                    opp = np.where((c[max(0, k - 10):k] < o[max(0, k - 10):k]) if side > 0 else (c[max(0, k - 10):k] > o[max(0, k - 10):k]))[0]
                    if not len(opp):
                        continue
                    q = max(0, k - 10) + opp[-1]
                    edge = h[q] if side > 0 else l[q]
                    if (c[k] - edge) * side <= 0:
                        continue
                    stop = (l[q:k + 1].min() - m.tick) if side > 0 else (h[q:k + 1].max() + m.tick)
                    for en, lim in (("edge", edge), ("mid", (o[q] + c[q]) / 2)):
                        add(m.sim(nx[k], side, stop, ie, f, limit=lim, i_exp=nx[k] + 60), day, "ob", var=f"{en}_{w}")
                    done = True; break
                if done:
                    break
        # ---- time windows
        def tw(name, sgn, t_in, t_out):
            d = mv[name][i]
            if sgn == 0 or np.isnan(d) or d <= 0:
                return
            e = m.O[T[t_in][i]]
            add(m.sim(T[t_in][i], int(sgn), e - sgn * d, T[t_out][i], f, tgt_px=[("none", e + sgn * 1e9)]), day, "time", var=name)
        tw("lunch_rev", -np.sign(P[1200][i] - P[930][i]), 1330, 1600)
        tw("london_rev", -np.sign(P[500][i] - P[200][i]), 930, 1130)
        tw("lasthour_cont", np.sign(P[1500][i] - P[930][i]), 1500, 1600)
        if day.dayofweek == 4:
            tw("tgif", -np.sign(P[1330][i] - wopen[i]), 1330, 1600)
        # ---- gaps
        def gap(name, old, i_in, i_out):
            e = m.O[i_in]; g = e - old
            if abs(g) < 4 * m.tick:
                return
            sgn = -int(np.sign(g)); risk = max(abs(g), f)
            add(m.sim(i_in, sgn, e - sgn * risk, i_out, f, tgt_px=[("half", e - g / 2), ("full", old)]), day, "gap", var=name)
            # the mirror: trade with the gap, same stop distance, target half a gap or one gap further
            add(m.sim(i_in, -sgn, e + sgn * risk, i_out, f, tgt_px=[("half", e + g / 2), ("full", e + g)]), day, "gapgo", var=name)
        i18 = T["p1800"][i]
        if i18 > 0 and m.ts[i18] - m.ts[i18 - 1] < 80 * 3600e9 and m.idx[i18].hour == 18 and m.idx[i18].minute == 0:
            nm = "nwog" if day.dayofweek == 0 else "ndog"
            gap(nm, m.C[i18 - 1], i18, T[930][i])
            i5 = np.searchsorted(m.ts, m.ts[i18] + 300e9)                # same gap measured and entered at 18:05
            gap(nm + "_1805", m.C[i18 - 1], i5, T[930][i])
        if full[i - 1]:
            old = m.C[T[1615][i - 1] - 1]
            gap("org", old, T[930][i], T[1600][i]); gap("org30", old, T[930][i], T[1000][i])
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/mnt/project-files/mentorship/data/fixed_roll_2026-11-10")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent))
    a = ap.parse_args()
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(3) as ex:
        t = pd.concat(ex.map(run_market, ("ES", "NQ", "YM"), [a.data] * 3), ignore_index=True)
    t = t[(t.day >= "2019-01-01")]
    t.to_parquet(Path(a.out) / "trades.parquet")
    print(len(t), "trades;", t.groupby("idea").size().to_dict())
