"""The coded ICT direction read inside the narrow engine (option B after PR #101; the 09:30 day filter of PR #103).
Light runner as runs/nq_am_2026-11-16/run.py: strategy.run_day day by day, Params.narrow="am", 1-minute fixed-roll
bars, $1,000 risk a trade, no sizing cap, $5 a side per contract.

The engine's bars are back-adjusted (2019 prices sit about 1.4x above what traded), so for the "open" variants the
stop % is scaled each day by traded price / adjusted price at the last bar before 09:30: the stop is then 0.25%
(NQ) / 0.21% (ES) of the price that actually traded, as in PR #103. RAW = the unadjusted 1-minute closes.

    python runs/ict_read_engine_2026-11-17/run.py OUTDIR [--sym NQ,ES]        (from the repo root)
"""
import sys, warnings
from dataclasses import replace
from pathlib import Path
import pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, str(Path.cwd()))
from mentorship import strategy as ST, backtest as B, narrow as N, ict_read as R   # noqa: E402

COST = {"ES": 0.10, "NQ": 0.25}
RAW = "/home/user/data/{}_1min_dbraw.parquet"
PCT = {"NQ": 0.25, "ES": 0.21}                     # the option C stop, % of price
SKIP = dict(nar_day_skip=("news", "holiday_eve", "prev_big", "small_gap"), nar_skip_news=("jobs", "cpi", "fomc"))   # the four option C conditions


def variants(sym):
    op = dict(nar_entry="open", nar_open_stop_pct=PCT[sym])
    return {
        # the sweep / shift / gap engine of PR #89 with the new filters
        "base": {},
        "read": dict(nar_bias="read"),
        "block67": dict(nar_on_block=0.67),
        "read_block67": dict(nar_bias="read", nar_on_block=0.67),
        "skip": SKIP,
        "read_skip": dict(nar_bias="read", **SKIP),
        "block67_skip": dict(nar_on_block=0.67, **SKIP),
        # option C: the read's side at the open, no setup
        "open": op,
        "open_skip": {**op, **SKIP},
        "open_skip_fri": {**op, **SKIP, "nar_day_skip": SKIP["nar_day_skip"] + ("friday",)},
        "open_block67": {**op, "nar_on_block": 0.67},
        "open_skip_block67": {**op, **SKIP, "nar_on_block": 0.67},
        "open1000": {**op, "nar_win": (600, 690)},
        "open1000_skip": {**op, **SKIP, "nar_win": (600, 690)},
        "open1000_block67": {**op, "nar_win": (600, 690), "nar_on_block": 0.67},
    }


def run(sym, ds, hist, past, kw, es_pt, ratio):
    p = replace(ST.Params(), narrow="am", risk_dollars=1000.0, max_notional=1e12, es_pt=es_pt, cost_per_share=COST[sym],
                session_close=975, **kw)
    N.FUNNEL.clear()
    rows, skips = [], []
    need = N.needs_past(p)
    for k in range(3, len(ds)):
        q = p
        if p.nar_entry == "open":
            q = replace(p, nar_open_stop_pct=p.nar_open_stop_pct * ratio[k])
        for tr in ST.run_day(ds[k], hist[k], sym, q, 1, nar_past=past[k] if need else None, skips=skips):
            rows.append(tr.row(p.cost_per_share))
    t = pd.DataFrame(rows)
    if len(t):
        t["year"] = pd.to_datetime(t.date).dt.year
        t = t[t.year >= 2019]
    sk = pd.Series([s[-1] for s in skips if s[0].year >= 2019]).value_counts().to_dict()
    return t, sk


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    syms = sys.argv[sys.argv.index("--sym") + 1].split(",") if "--sym" in sys.argv else ["NQ", "ES"]
    es5 = B.load("ES", 5, source="databento")
    sk_rows = []
    for sym in syms:
        df = B.load(sym, 1, source="databento")
        df = df[df.index >= "2018-10-01"]
        ds = B.days(df, 1, False, 975)
        hist = [[B.rth(x) for x in ds[max(0, k - 3):k]] for k in range(len(ds))]
        past = [R.past_bars(df, g.index[0].date()) for g in ds]
        raw = pd.read_parquet(RAW.format(sym)).close
        ratio = []
        for g in ds:
            b = g.index[g.index < g.index[0].normalize() + pd.Timedelta(minutes=570)]
            ratio.append(float(raw.get(b[-1], float("nan")) / g.close.loc[b[-1]]) if len(b) else 1.0)
        ratio = [x if x == x else 1.0 for x in ratio]
        es_pt = 1.0 if sym == "ES" else round(float(B.load(sym, 5, source="databento").close.median() / es5.close.median()), 2)
        only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else ""
        for name, kw in variants(sym).items():
            if not name.startswith(only):
                continue
            t, sk = run(sym, ds, hist, past, kw, es_pt, ratio)
            sk_rows.append(dict(market=sym, variant=name, trades=len(t), **sk))
            print(sym, name, len(t), sk, flush=True)
            for y in range(2019, 2027):
                (t[t.year == y] if len(t) else t).to_csv(out / f"trades_{sym}_{name}_{y}.csv", index=False)
    pd.DataFrame(sk_rows).to_csv(out / "skips.csv", index=False)


if __name__ == "__main__":
    main()
