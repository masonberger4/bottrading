"""Merge the shards of a split run and summarise it.

    python -m cloud.merge --tag rerun

Collects <tag>_jobs/ from this machine, the shared folder (cloud shards) and the
`backtest-results` branch (laptop shards, see push_results.py), refuses to mix commits, lists any
missing jobs, and writes <tag>_trades.csv and <tag>_summary.md to the shared folder
(runs/mentorship/ when there is no shared folder).
"""
from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path

import pandas as pd

from .common import LOCAL_RUNS, RESULTS_BRANCH, SHARED, SHARED_RUNS, job_name, jobs

RISK = 1000.0          # report $ at $1k risk per trade


def _branch_files(tag: str) -> dict[str, bytes]:
    if subprocess.run(["git", "fetch", "-q", "origin", RESULTS_BRANCH], capture_output=True).returncode:
        return {}
    ls = subprocess.run(["git", "ls-tree", "-r", "--name-only", "FETCH_HEAD", f"{tag}_jobs/"],
                        capture_output=True, text=True).stdout.split()
    return {Path(p).name: subprocess.run(["git", "show", f"FETCH_HEAD:{p}"], capture_output=True).stdout
            for p in ls}


def collect(tag: str) -> tuple[dict[str, bytes], set[str]]:
    files: dict[str, bytes] = {}
    for d in (LOCAL_RUNS / f"{tag}_jobs", SHARED_RUNS / f"{tag}_jobs"):
        if d.exists():
            files.update({f.name: f.read_bytes() for f in d.iterdir() if f.is_file()})
    files.update(_branch_files(tag))
    stamps = [v.decode().split("\n") for k, v in files.items() if k.startswith("_commit_")]
    commits = {x[0].strip() for x in stamps}
    libs = {x[1].strip() for x in stamps if len(x) > 1 and x[1].strip()}
    if len(libs) > 1:
        print("warning: shards used different library versions:", "; ".join(sorted(libs)))
    return {k: v for k, v in files.items() if k.endswith(".csv")}, commits


def dollars(g: pd.DataFrame) -> float:
    return round(float(g.R.sum()) * RISK)


def summary(t: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (tf, v), g in t.groupby(["tf", "variant"]):
        a, b = g[g.year <= 2022], g[g.year >= 2023]
        yr = g.groupby("year").R.sum()
        rows.append(dict(tf=tf, variant=v, trades=len(g), usd=dollars(g), usd_2019_22=dollars(a),
                         usd_2023_26=dollars(b), years_up=f"{int((yr > 0).sum())}/{len(yr)}",
                         win_rate=round(float((g.R > 0).mean()), 2)))
    return pd.DataFrame(rows).sort_values(["tf", "usd_2019_22"], ascending=[True, False])


def by_day_type(t: pd.DataFrame, s: pd.DataFrame, top: int = 5) -> pd.DataFrame:
    """$ by day type for the defaults and the best `top` versions on 2019-22, per timeframe."""
    keep = {(tf, v) for tf, g in s.groupby("tf") for v in ["defaults"] + list(g.variant.head(top))}
    t = t[[k in keep for k in zip(t.tf, t.variant)]]
    d = t.groupby(["tf", "variant", "day_type"]).R.sum().mul(RISK).round().astype(int).unstack(fill_value=0)
    return d.reset_index()


def _md(s: pd.DataFrame) -> str:
    rows = [list(s.columns), ["---"] * len(s.columns)] + s.astype(str).values.tolist()
    return "\n".join("| " + " | ".join(map(str, r)) + " |" for r in rows)


def main():
    ap = argparse.ArgumentParser(prog="cloud.merge")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--tfs", type=int, nargs="+", default=None, help="to check for missing jobs")
    ap.add_argument("--years", type=int, nargs=2, default=(2019, 2026), help="first and last year")
    ap.add_argument("--variants", nargs="*", default=None)
    a = ap.parse_args()
    files, commits = collect(a.tag)
    if len(commits) > 1:
        raise SystemExit(f"shards ran on different commits {sorted(c[:7] for c in commits)}; re-run one side")
    if a.tfs and a.variants:
        missing = [job_name(j) for j in jobs(a.tfs, a.variants, range(a.years[0], a.years[1] + 1)) if job_name(j) not in files]
        print(f"{len(missing)} jobs missing" + (": " + ", ".join(missing[:20]) if missing else ""))
    parts = [pd.read_csv(io.BytesIO(b)) for b in files.values() if len(b) > 2]
    t = pd.concat([x for x in parts if len(x)], ignore_index=True)
    out = SHARED_RUNS if SHARED.exists() else LOCAL_RUNS
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out / f"{a.tag}_trades.csv", index=False)
    s = summary(t)
    head = (f"# {a.tag}: {len(files)} job files, commit {next(iter(commits), 'unknown')[:7]}\n\n"
            f"$ at ${RISK:,.0f} risk per trade (sum of R x {RISK:,.0f}). Pick on 2019-22, check on 2023-26.\n\n")
    dt = by_day_type(t, s)
    (out / f"{a.tag}_summary.md").write_text(head + _md(s) + "\n\n## By day type ($)\n\n" + _md(dt) + "\n")
    print(head + s.to_string(index=False) + "\n\nBy day type ($):\n" + dt.to_string(index=False))
    print("wrote", out / f"{a.tag}_trades.csv", "and", out / f"{a.tag}_summary.md")


if __name__ == "__main__":
    main()
