"""python -m swing [--data PATH] [--out DIR] [key=value ...]: run One Shot One Kill on ES 1m data
and write trades.csv + report.json (all, 2019-22, 2023-26, by year/case/array/weekday/exit)."""
from __future__ import annotations

import argparse
import json
from dataclasses import fields, replace
from pathlib import Path

import pandas as pd

from . import bars, osok, swing_model


def stats(t: pd.DataFrame) -> dict:
    if t is None or not len(t):
        return {"trades": 0}
    eq = t.sort_values("entry_time").net.cumsum()
    wins, losses = t.net[t.net > 0].sum(), -t.net[t.net < 0].sum()
    return {"trades": int(len(t)), "net": round(float(t.net.sum()), 2),
            "win_rate": round(float((t.net > 0).mean()), 3),
            "profit_factor": round(float(wins / losses), 2) if losses else None,
            "avg_R": round(float(t.R.mean()), 3), "costs": round(float(t.costs.sum()), 2),
            "max_dd": round(float((eq.cummax().clip(lower=0) - eq).max()), 2),
            "avg_hold_days": round(float(t.hold_days.mean()), 2)}


def report(t: pd.DataFrame) -> dict:
    out = {"all": stats(t)}
    if not len(t):
        return out
    yr = pd.to_datetime(t.week).dt.year
    out["2019-22"] = stats(t[yr <= 2022])
    out["2023-26"] = stats(t[yr >= 2023])
    t = t.assign(year=yr, conv=pd.cut(t.conviction, [-1, 5, 10, 15, 1000], labels=["0-5", "6-10", "11-15", "16+"]))
    for col in ("year", "side", "case", "frame_tf", "array", "entry_weekday", "week_extreme_day",
                "exit_reason", "added", "conv"):
        out[f"by_{col}"] = {str(k): stats(g) for k, g in t.groupby(t[col].astype(str))}
    return out


def _cast(v: str, typ):
    if typ in (bool, "bool"):
        return v.lower() in ("1", "true", "yes")
    if typ in (tuple, "tuple"):
        return tuple(_num(x) for x in v.split(",") if x)
    return _num(v) if typ in (int, float, "int", "float") else v


def _num(x: str):
    try:
        return int(x)
    except ValueError:
        try:
            return float(x)
        except ValueError:
            return x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/mentorship/ES_1min_db.csv")
    ap.add_argument("--out", default="runs/swing/osok_default")
    ap.add_argument("--model", default="osok", choices=("osok", "swing"))
    ap.add_argument("set", nargs="*", help="Params overrides, e.g. target=prev_week fib_gate=false")
    a = ap.parse_args()
    p = swing_model.defaults() if a.model == "swing" else osok.Params()
    types = {f.name: f.type for f in fields(p)}
    kw = {}
    for s in a.set:
        k, v = s.split("=", 1)
        kw[k] = _cast(v, types[k])
    p = replace(p, **kw)
    f = bars.resample(bars.load(a.data))
    t = swing_model.run(f, p) if a.model == "swing" else osok.run(f, p)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / "trades.csv", index=False)
    rep = report(t)
    rep["params"] = {k: str(v) for k, v in p.__dict__.items()}
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
    print(json.dumps({k: rep[k] for k in ("all", "2019-22", "2023-26") if k in rep}, indent=1))


if __name__ == "__main__":
    main()
