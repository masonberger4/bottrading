"""Narrow morning engine (Params.narrow="am", PR #89) with ICT's own dated calls as the direction (2026-11-17).

    python <this file> OUTDIR        (run from the root of an engine checkout: mentorship branch, with the 1m fixed-roll bars)

No engine change: the side and the "not before the call" gate are applied from here by wrapping narrow._bias_ok and
narrow._target for one day at a time. $1,000 risk a trade, no sizing cap, $5 a side per contract (as runs/nq_am_2026-11-16).

Per call day and market, the engine is run long-only, short-only and with no side; "his side" / "opposite" pick from
those. Controls enter his side at a plain time (09:30, or the call time when that is later) with a stop the same
distance away as the engine's, target 2R, flat at 12:00. Also: both sides on every day 2019-26, for the hindsight
ceiling (the side of the 09:30 -> 12:00 move, known only afterwards)."""
import sys, warnings
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, str(Path.cwd()))
from mentorship import strategy as ST, backtest as B, narrow as N   # noqa: E402

HERE = Path(__file__).resolve().parent
CALLS = HERE.parent / "ict_calls_2026-11-17"
COST = {"ES": 0.10, "NQ": 0.25}
GATE = dict(sign=0, after=0, until=9999)          # set per run: side allowed (0 = both), entries only from / before these minutes
_bias0, _target0 = N._bias_ok, N._target


def _bias(s, kind, entry, t, hist):
    return (GATE["sign"] == 0 or s.sign == GATE["sign"]) and _bias0(s, kind, entry, t, hist)


def _target(s, t, hist, p, i, entry, risk, tick):
    if t[i] < GATE["after"] or t[i] >= GATE["until"]:
        return None, ""
    return _target0(s, t, hist, p, i, entry, risk, tick)


N._bias_ok, N._target = _bias, _target


def mins(x):
    h, m = str(x).split(":")[:2]
    return int(h) * 60 + int(m)


def load_calls():
    rows = []
    for y in (2023, 2024, 2025, 2026):
        c = pd.read_csv(CALLS / f"calls_{y}_scored.csv", sep="|")
        rows.append(c[["id", "date", "ref", "dir", "end_day", "end", "before", "sym", "win_end"]])
    c = pd.concat(rows, ignore_index=True)
    c["date"] = pd.to_datetime(c.date).dt.date
    c["sign"] = c.dir.map({"up": 1, "down": -1})
    c["ref_m"], c["end_m"] = c.ref.map(mins), c.end.map(mins)
    return c[c.sign.notna()].reset_index(drop=True)


class Mkt:
    def __init__(self, sym, es5):
        self.sym = sym
        df = B.load(sym, 1, source="databento")
        df = df[df.index >= "2018-12-20"]
        self.ds = B.days(df, 1, False, 975)
        self.hist = [[B.rth(x) for x in self.ds[max(0, k - 3):k]] for k in range(len(self.ds))]
        self.k = {d.index[0].date(): k for k, d in enumerate(self.ds)}
        self.dates = sorted(self.k)
        es_pt = 1.0 if sym == "ES" else round(float(B.load(sym, 5, source="databento").close.median() / es5.close.median()), 2)
        self.p = replace(ST.Params(), narrow="am", risk_dollars=1000.0, max_notional=1e12, es_pt=es_pt,
                         cost_per_share=COST[sym], session_close=975)

    def eng(self, day, sign=0, after=0, until=9999):
        k = self.k.get(day)
        if k is None or k < 3:
            return []
        GATE.update(sign=sign, after=after, until=until)
        out = [tr.row(self.p.cost_per_share) for tr in ST.run_day(self.ds[k], self.hist[k], self.sym, self.p, 1)]
        GATE.update(sign=0, after=0, until=9999)
        return out

    def plain(self, day, sign, start, dist, until=9999, tgt_r=2.0, stop_on=True):
        """His side at the open of the first bar at / after `start`, stop `dist` points away, 2R, flat 12:00. R net."""
        df = self.ds[self.k[day]]
        t = (df.index.hour * 60 + df.index.minute).to_numpy()
        i0, i1 = int(np.searchsorted(t, start)), int(np.searchsorted(t, 720))
        if i0 >= i1 or start >= 690 or start >= until:
            return None
        o, h, l, c = (df[x].to_numpy(dtype=float) * sign for x in ("open", "high", "low", "close"))
        if sign < 0:
            h, l = l, h
        e = o[i0]
        stop, tgt, pts, why = e - dist, e + tgt_r * dist, None, "time"
        for i in range(i0, i1):
            if stop_on and l[i] <= stop:
                pts, why = min(stop, o[i]) - e, "stop"; break
            if h[i] >= tgt:
                pts, why = max(tgt, o[i]) - e, "target"; break
        if pts is None:
            pts = (o[i1] if i1 < len(o) else c[-1]) - e
        R = (pts - COST[self.sym]) / dist
        return dict(date=day, symbol=self.sym, side="long" if sign > 0 else "short", entry_time=df.index[i0], entry=e * sign,
                    stop=stop * sign, R=round(R, 3), net=round(1000 * R, 2), exit_reason=why, exit_time=df.index[i0])

    def am_move(self, day):
        df = self.ds[self.k[day]]
        t = (df.index.hour * 60 + df.index.minute).to_numpy()
        i0, i1 = int(np.searchsorted(t, 570)), int(np.searchsorted(t, 720))
        if i0 >= len(df) or i1 >= len(df) or i1 <= i0:
            return 0
        return int(np.sign(df.open.iloc[i1] - df.open.iloc[i0]))


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    (out / "ENGINE.txt").write_text(f"{commit} (light runner, 1m fixed-roll, narrow='am' base settings)\n")
    es5 = B.load("ES", 5, source="databento")
    M = {s: Mkt(s, es5) for s in ("NQ", "ES")}
    calls = load_calls()
    # --- where each call is applied: same morning (ref before 11:30), else the next trading morning
    rows = []
    for c in calls.itertuples():
        m = M[c.sym]
        if c.ref_m < 690 and c.date in m.k:
            day, after, kind = c.date, c.ref_m, ("am_end" if c.end_day == 0 and c.end_m <= 720 else "am_longer")
        elif c.end_day >= 1 or c.ref_m >= 960:              # evening call or an outlook: the next trading morning only
            nxt = [d for d in m.dates if d > c.date]
            if not nxt or (nxt[0] - c.date).days > 4:
                continue
            day, after, kind = nxt[0], 0, "prior_eve"
        else:                                               # an afternoon call that ended the same day: no morning to trade
            continue
        rows.append(dict(id=c.id, call_date=c.date, day=day, sym=c.sym, sign=int(c.sign), after=after, until=9999, kind=kind,
                         before=c.before, win_end=c.win_end, ref=c.ref, end=c.end, end_day=c.end_day))
    D = pd.DataFrame(rows)
    for (day, sym), g in D[D.kind != "prior_eve"].groupby(["day", "sym"]):      # a later opposite call the same morning ends the earlier one
        g = g.sort_values("after")
        for a, b in zip(g.index[:-1], g.index[1:]):
            if D.sign[a] != D.sign[b]:
                D.loc[a, "until"] = D.after[b]
    D.to_csv(out / "call_days.csv", index=False)
    T = []
    call_days = set(zip(D.day, D.sym))

    def add(tr, variant, c):
        for r in tr:
            T.append(dict(r, variant=variant, id=c.id, kind=c.kind, before=c.before, call_sign=c.sign, win_end=c.win_end))

    for c in D.itertuples():
        m = M[c.sym]
        for nm, sg in (("long_only", 1), ("short_only", -1), ("no_side", 0)):
            add(m.eng(c.day, sg), nm, c)
        his = m.eng(c.day, c.sign)
        add(his, "his_side", c)
        add(m.eng(c.day, -c.sign), "opposite", c)
        add(m.eng(c.day, c.sign, c.after, c.until), "his_side_after_call", c)
        add(m.eng(c.day, 0, c.after, c.until), "no_side_after_call", c)
        add(m.eng(c.day, -c.sign, c.after, c.until), "opposite_after_call", c)
        start = max(570, c.after)
        if his:                                             # control 1: same day, same stop distance as the engine's trade
            x = m.plain(c.day, c.sign, start, abs(his[0]["entry"] - his[0]["stop"]), c.until)
            if x:
                add([x], "plain_same_stop", c)
        for nm, sg, late in (("plain_typical_stop", c.sign, 0), ("plain_opposite", -c.sign, 0), ("plain_late15", c.sign, 15),
                             ("plain_late30", c.sign, 30)):
            px = float(m.ds[m.k[c.day]].close.iloc[-1])
            x = m.plain(c.day, sg, start + late, round(px * FRAC[c.sym] / 0.25) * 0.25, c.until + late)
            if x:
                add([x], nm, c)
        px = float(m.ds[m.k[c.day]].close.iloc[-1])
        d0 = round(px * FRAC[c.sym] / 0.25) * 0.25
        for nm, kw in (("plain_half_stop", dict(dist=d0 / 2)), ("plain_double_stop", dict(dist=d0 * 2)), ("plain_1R", dict(dist=d0, tgt_r=1.0)),
                       ("plain_3R", dict(dist=d0, tgt_r=3.0)), ("plain_hold_to_noon", dict(dist=d0, tgt_r=99.0, stop_on=False))):
            x = m.plain(c.day, c.sign, start, until=c.until, **kw)   # settings not used for the main number; shown as a robustness check
            if x:
                add([x], nm, c)
        if c.kind != "prior_eve":                           # chance: the same side and time on the other days within 60 days
            for d in m.dates:
                if abs((d - c.day).days) <= 60 and (d, c.sym) not in call_days and m.k[d] >= 3:
                    x = m.plain(d, c.sign, start, round(float(m.ds[m.k[d]].close.iloc[-1]) * FRAC[c.sym] / 0.25) * 0.25)
                    if x:
                        add([x], "plain_other_days", c)
    pd.DataFrame(T).to_csv(out / "trades_calls.csv", index=False)
    # --- every day 2019-26, NQ and ES: long-only and short-only, for the hindsight ceiling and the all-days reference
    A = []
    for sym, m in M.items():
        for d in m.dates:
            if d.year < 2019:
                continue
            mv = m.am_move(d)
            for nm, sg in (("long_only", 1), ("short_only", -1), ("no_side", 0)):
                for r in m.eng(d, sg):
                    A.append(dict(r, variant=nm, am_move=mv))
    pd.DataFrame(A).to_csv(out / "trades_alldays.csv", index=False)


FRAC = {"NQ": 0.0025, "ES": 0.0021}      # the engine's median stop distance as a fraction of price (base, every day 2019-26: 48.6 NQ / 10.75 ES points)
if __name__ == "__main__":
    main()
