"""Shared paths and the job list for the split runs."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

SHARED = Path(os.environ.get("MENTORSHIP_SHARED", "/mnt/project-files/mentorship"))
SHARED_DATA = SHARED / "data"                 # raw Databento files + Yahoo dailies, kept between sessions
SHARED_RUNS = SHARED / "runs"                 # job CSVs written by cloud shards, one folder per tag
LOCAL_RUNS = Path("runs/mentorship")
RESULTS_BRANCH = "backtest-results"           # where the laptop pushes its job CSVs (cloud/push_results.py)
YEARS = range(2019, 2027)


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def stamp() -> str:
    """Commit on the first line (must match across shards), library versions on the second."""
    import numpy
    import pandas
    return f"{commit()}\npandas {pandas.__version__} numpy {numpy.__version__}\n"


def jobs(tfs, variants, years=YEARS) -> list[tuple[int, int, str]]:
    """Same (tf, year, variant) jobs and file names as study.main_decisions, so laptop and cloud
    caches mix. Sorted by timeframe, then variant, then year."""
    return [(tf, y, v) for tf in tfs for v in variants for y in years]


def shard(js: list, i: int, n: int) -> list:
    """Shard i of n (1-based), round robin, so each shard gets the same mix of 1m and 5m jobs."""
    return [j for k, j in enumerate(js) if k % n == i - 1]


def job_name(j) -> str:
    return "{}m_{}_{}.csv".format(*j)
