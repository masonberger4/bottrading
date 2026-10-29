"""Run one shard of a version list on Databento ES (NQ / YM partners), one job per (timeframe,
year, version), with the same job files as mentorship.study.main_decisions.

    python -m cloud.run --tag rerun --shard 2/2 --plan        # list this shard's jobs only
    python -m cloud.run --tag rerun --shard 2/2               # all versions in study.DECISIONS
    python -m cloud.run --tag rerun --shard 2/2 --tfs 1 --variants defaults D3_mss_wick

Every machine must use the same --tag, --shard n, --tfs and --variants and the same commit;
shard i runs jobs i, i+n, i+2n, ... Finished jobs are skipped, so a stopped run resumes.
In the cloud, each finished job is also copied to /mnt/project-files/mentorship/runs/<tag>_jobs/.
"""
from __future__ import annotations

import argparse
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed

os.environ.setdefault("MENTORSHIP_SRC", "databento")

from .common import LOCAL_RUNS, SHARED, SHARED_RUNS, commit, job_name, jobs, shard, stamp   # noqa: E402


def main():
    ap = argparse.ArgumentParser(prog="cloud.run")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--shard", default="1/1", help="i/n, e.g. 1/2 on the laptop and 2/2 in the cloud")
    ap.add_argument("--tfs", type=int, nargs="+", default=[5, 1])
    ap.add_argument("--years", type=int, nargs=2, default=(2019, 2026), help="first and last year")
    ap.add_argument("--variants", nargs="*", default=None, help="default: every version in study.DECISIONS")
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--no-publish", action="store_true", help="don't copy job files to the shared folder")
    a = ap.parse_args()

    from mentorship import backtest as B, study
    from mentorship.strategy import Params

    i, n = map(int, a.shard.split("/"))
    variants = a.variants or list(study.DECISIONS)
    unknown = [v for v in variants if v not in study.DECISIONS]
    if unknown:
        raise SystemExit(f"not in study.DECISIONS at this commit: {unknown}")
    mine = shard(jobs(a.tfs, variants, range(a.years[0], a.years[1] + 1)), i, n)
    cache = LOCAL_RUNS / f"{a.tag}_jobs"
    cache.mkdir(parents=True, exist_ok=True)
    todo = [j for j in mine if not (cache / job_name(j)).exists()]
    print(f"shard {i}/{n}: {len(mine)} jobs, {len(todo)} to run, commit {commit()[:7]}", flush=True)
    if a.plan:
        for j in todo:
            print(" ", job_name(j))
        return

    publish = not a.no_publish and SHARED.exists()
    out = SHARED_RUNS / f"{a.tag}_jobs"
    if publish:
        out.mkdir(parents=True, exist_ok=True)
    st = stamp()
    for d in [cache] + ([out] if publish else []):
        f = d / f"_commit_shard{i}of{n}.txt"
        if f.exists() and f.read_text().split("\n")[0] != st.split("\n")[0]:
            raise SystemExit(f"{d} has jobs from another commit ({f.read_text()[:7]}); use a new --tag")
        f.write_text(st)

    for tf in a.tfs:                      # build the shared htf tables once, before the workers start
        study._bias_cache(tf, kw=B.htf_kw(Params()))
    with ProcessPoolExecutor(a.workers) as ex:
        futs = {ex.submit(study._dec_job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            p = cache / job_name(j)
            f.result().to_csv(p, index=False)
            if publish:
                shutil.copy2(p, out / p.name)
            print(f"{k}/{len(todo)} {j}", flush=True)


if __name__ == "__main__":
    main()
