"""Laptop side: publish this machine's finished job files for a tag to the `backtest-results`
branch, so a cloud session can merge them with its own shard. Only trade CSVs and the commit
stamp are added (no data, keys or other files).

    python -m cloud.push_results --tag rerun

It works in a separate worktree (../bottrading-results), so the branch you are on is untouched.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from .common import LOCAL_RUNS, RESULTS_BRANCH


def git(*a, cwd=None, check=True):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=check)


def main():
    ap = argparse.ArgumentParser(prog="cloud.push_results")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--worktree", default="../bottrading-results")
    a = ap.parse_args()
    src = LOCAL_RUNS / f"{a.tag}_jobs"
    files = sorted(src.glob("*.csv")) + sorted(src.glob("_commit_*.txt"))
    if not files:
        raise SystemExit(f"nothing in {src}")
    wt = Path(a.worktree)
    if not wt.exists():
        have_remote = git("ls-remote", "--exit-code", "--heads", "origin", RESULTS_BRANCH, check=False).returncode == 0
        if have_remote:
            git("fetch", "origin", RESULTS_BRANCH)
            git("worktree", "add", "-B", RESULTS_BRANCH, str(wt), f"origin/{RESULTS_BRANCH}")
        else:                                   # first push: an empty branch with no code on it
            git("worktree", "add", "--detach", str(wt))
            git("checkout", "--orphan", RESULTS_BRANCH, cwd=wt)
            git("rm", "-rf", "-q", "--ignore-unmatch", ".", cwd=wt)
    else:
        git("pull", "-q", "origin", RESULTS_BRANCH, cwd=wt, check=False)
    dst = wt / f"{a.tag}_jobs"
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dst / f.name)
    git("add", "-f", f"{a.tag}_jobs", cwd=wt)
    if git("diff", "--cached", "--quiet", cwd=wt, check=False).returncode == 0:
        print("nothing new to push")
        return
    git("commit", "-q", "-m", f"Results: {a.tag} ({len(files)} files from the laptop)", cwd=wt)
    git("push", "-q", "-u", "origin", RESULTS_BRANCH, cwd=wt)
    print(f"pushed {len(files)} files to {RESULTS_BRANCH}/{a.tag}_jobs")


if __name__ == "__main__":
    main()
