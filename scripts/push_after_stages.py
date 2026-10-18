"""Push the mentorship branch to GitHub after each build-workflow stage finishes.

Watches the workflow journal; when a "test:<package>" agent (the last step of a stage) has a
result, waits for a clean working tree, runs the secrets / data check on every commit not yet
on origin, and pushes only if the check passes. Otherwise it stops and leaves a note in
runs/push_after_stages.log for the owner.

    .venv/Scripts/python scripts/push_after_stages.py <journal.jsonl>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LOG = REPO / "runs" / "push_after_stages.log"
BAD_PATH = re.compile(r"(^|/)(data|runs)/|\.env($|\.)|token.*\.json$|credentials.*\.json$|\.(pem|key|csv|parquet|dbn|zst|zip)$",
                      re.I)
BAD_TEXT = r"(db-[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|\"refresh_token\"\s*:|\"access_token\"\s*:|" \
           r"(app_secret|api_key|app_key)\s*=\s*['\"][A-Za-z0-9_\-]{12,})"


def git(*a) -> str:
    return subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True).stdout


def log(msg: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def check(rng: str) -> list[str]:
    bad = [p for p in git("log", "--pretty=format:", "--name-only", rng).split() if BAD_PATH.search(p)]
    for c in git("rev-list", rng).split():
        hits = git("grep", "-I", "-n", "-i", "-E", BAD_TEXT, c)
        bad += [h for h in hits.splitlines() if h.strip()]
    return bad


def finished_tests(journal: Path) -> set[str]:
    labels, done = {}, set()
    for line in journal.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "started":
            labels[e["key"]] = e.get("label", "")
        elif e.get("type") == "result" and labels.get(e.get("key"), "").startswith("test:"):
            done.add(labels[e["key"]])
    return done


def main():
    journal = Path(sys.argv[1])
    seen = finished_tests(journal)
    log(f"watching {journal.name}; stages already done: {sorted(seen)}")
    while True:
        time.sleep(60)
        now = finished_tests(journal)
        for stage in sorted(now - seen):
            for _ in range(30):                      # let the stage's last commit land
                if not [l for l in git("status", "--porcelain").splitlines() if not l.startswith("??")]:
                    break
                time.sleep(60)
            git("fetch", "origin", "mentorship")
            rng = "origin/mentorship..mentorship"
            bad = check(rng)
            if bad:
                log(f"{stage}: CHECK FAILED, not pushing: {bad[:10]}")
                print(f"STOP {stage}: {bad[:10]}", flush=True)
                return
            out = subprocess.run(["git", "push", "origin", "mentorship"], cwd=REPO, capture_output=True, text=True)
            log(f"{stage}: pushed {git('rev-parse', '--short', 'mentorship').strip()} rc={out.returncode} {out.stderr.strip()[-200:]}")
            print(f"PUSHED {stage}", flush=True)
        seen = now


if __name__ == "__main__":
    main()
