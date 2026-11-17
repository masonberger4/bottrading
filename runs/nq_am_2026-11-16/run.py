"""Narrow morning engine runs (PR #82 option D). Light runner: the same strategy.run_day the full engine calls, with
Params.narrow="am", fed day by day from the 1-minute fixed-roll bars. No bias tables are built (the narrow mode reads
none), so a variant takes seconds. $1,000 risk a trade, no sizing cap, $5 a side per contract, as runs/bt/run.py.

    python runs/nq_am_2026-11-16/run.py OUTDIR [--sym NQ,ES] [--only name,name]     (from the repo root)

Stage 1 runs the base and one-switch-at-a-time variants. Stage 2 builds "pick": per switch, the level with the best
2019-22 R a trade (base level kept unless another beats it), then runs it. 2023-26 is never used to choose.
Years 2016-18 are also written, as a second untouched check (the summary keeps them apart from 2019-26)."""
import sys, warnings
from dataclasses import replace
from pathlib import Path
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, str(Path.cwd()))
from mentorship import strategy as ST, backtest as B, narrow as N   # noqa: E402

COST = {"ES": 0.10, "NQ": 0.25, "YM": 1.0}
AXES = {                                    # switch -> {level name: params}; the first level is the base
    "entry": {"react": {}, "limit_edge": dict(nar_entry="limit", entry="edge"), "limit_ce": dict(nar_entry="limit", entry="ce")},
    "stop": {"ext": {}, "gap": dict(nar_stop="gap")},
    "target": {"2R": {}, "1R": dict(nar_target=1.0), "3R": dict(nar_target=3.0), "pool": dict(nar_target="pool")},
    "be": {"off": {}, "be1R": dict(nar_be_at=1.0)},
    "pools": {"pd_on_lon": {}, "plus_pre": dict(nar_pools=("pd", "on", "lon", "pre")), "plus_sw": dict(nar_pools=("pd", "on", "lon", "sw")),
              "pd_only": dict(nar_pools=("pd",)), "on_only": dict(nar_pools=("on",)), "sw_only": dict(nar_pools=("sw",))},
    "shift": {"n2": {}, "n1": dict(nar_shift_n=1), "n3": dict(nar_shift_n=3)},
    "gapmin": {"g1": {}, "g0.25": dict(nar_gap_min=0.25), "g2": dict(nar_gap_min=2.0)},
    "win": {"0930_1130": {}, "0930_1030": dict(nar_win=(570, 630)), "1000_1100": dict(nar_win=(600, 660))},
    "flat": {"1200": {}, "1600": dict(nar_flat=960)},
    "trades": {"one": {}, "two": dict(nar_max_trades=2)},
    "bias": {"none": {}, "midnight": dict(nar_bias="midnight"), "open830": dict(nar_bias="open830"),
             "prevday": dict(nar_bias="prevday"), "anti_prevday": dict(nar_bias="anti_prevday")},
}


def run(sym, ds, kw, es_pt):
    p = replace(ST.Params(), narrow="am", risk_dollars=1000.0, max_notional=1e12, es_pt=es_pt, cost_per_share=COST[sym],
                session_close=975, **kw)
    N.FUNNEL.clear()
    rows = []
    for k in range(3, len(ds)):
        for tr in ST.run_day(ds[k], HIST[sym][k], sym, p, 1):
            rows.append(tr.row(p.cost_per_share))
    t = pd.DataFrame(rows)
    if len(t):
        t["year"] = pd.to_datetime(t.date).dt.year
        t = t[t.year >= 2016]
    return t, dict(N.FUNNEL)


def h1_score(t):
    x = t[(t.year >= 2019) & (t.year <= 2022)].R if len(t) else pd.Series(dtype=float)
    return (x.mean(), len(x)) if len(x) >= 80 else (-9.0, len(x))


HIST = {}


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    syms = sys.argv[sys.argv.index("--sym") + 1].split(",") if "--sym" in sys.argv else ["NQ"]
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    (out / "ENGINE.txt").write_text(f"{commit} +narrow.py (light runner, 1m)\n")
    es5 = B.load("ES", 5, source="databento")
    variants = {"base": {}}
    for ax, lv in AXES.items():
        for nm, kw in list(lv.items())[1:]:
            variants[f"{ax}_{nm}"] = kw
    funnels = {}
    for sym in syms:
        df = B.load(sym, 1, source="databento")
        df = df[df.index >= "2015-12-20"]
        ds = B.days(df, 1, False, 975)
        HIST[sym] = [[B.rth(x) for x in ds[max(0, k - 3):k]] for k in range(len(ds))]
        es_pt = 1.0 if sym == "ES" else round(float(B.load(sym, 5, source="databento").close.median() / es5.close.median()), 2)
        res = {}
        for name, kw in variants.items():
            res[name], funnels[(sym, name)] = run(sym, ds, kw, es_pt)
            print(sym, name, len(res[name]), flush=True)
        if sym == syms[0]:                      # the pick is made once, on the first market's 2019-22
            pick, why = {}, []
            base = h1_score(res["base"])[0]
            for ax, lv in AXES.items():
                best, bs = None, base
                for nm, kw in list(lv.items())[1:]:
                    s = h1_score(res[f"{ax}_{nm}"])[0]
                    if s > bs:
                        best, bs = nm, s
                if best:
                    pick.update(lv[best]); why.append(f"{ax}={best} ({bs:+.3f} R vs base {base:+.3f})")
            (out / "PICK.txt").write_text("pick = " + repr(pick) + "\nchosen on " + syms[0] + " 2019-22, R a trade, one switch at a time:\n" + "\n".join(why) + "\n")
            variants["pick"] = pick
        res["pick"], funnels[(sym, "pick")] = run(sym, ds, variants["pick"], es_pt)
        for name, t in res.items():
            for y in range(2016, 2027):
                ty = t[t.year == y] if len(t) else t
                ty.to_csv(out / f"trades_{sym}_{name}_{y}.csv", index=False)
    pd.DataFrame([dict(market=k[0], variant=k[1], **v) for k, v in funnels.items()]).to_csv(out / "funnel.csv", index=False)


if __name__ == "__main__":
    main()
