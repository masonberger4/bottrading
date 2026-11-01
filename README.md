# Project memory folder

Layout (all in /mnt/project-files/memory/):
- decisions.md — owner answers and standing rules, with date and who decided. Check here before asking Mase anything.
- results.md — every backtest/audit result, baselines, build status, bot histories.
- data.md — data sources, file paths, purchases, credit, DXY/COT notes.
- laptop_ops.md — laptop and cloud rules: folders, processes to leave alone, how runs are started, monitoring cadence.
- lessons.md — stalls, drops, what fixed them.
- skill_drafts/ — draft skills for Mase to add in claude.ai settings (threads cannot install skills).

Project memory (MEMORY.md) is now a short index: current status, standing rules, pointers here. Old per-topic memory files were moved verbatim into these files, one section each, with their source name and date; nothing was dropped.

How threads use it:
1. Read MEMORY.md, then only the file(s) your task needs (grep for a keyword; the files are long).
2. Append new facts to the right file, under the right section, with date (UTC) and who decided. Never overwrite another thread's text; re-read the file right before appending (other threads write too, last write wins).
3. Update the "NOW" line in MEMORY.md only for status that other threads need; keep MEMORY.md under ~3 KB.
4. Put detail in the topic file, not in MEMORY.md. Never store secrets.
5. Long sections that become stale: summarize in place and mark with the date; don't delete decisions.

## Versioning and safe saves (required for every edit)
All edits go through `tools/memsave.py` (a git repo lives in this folder; CHANGELOG.md has one row per version: who, when, why, link, hash before->after).
1. Pull + hash: `H=$(python3 tools/memsave.py hash FILE)` and read FILE.
2. Draft your edit in a scratch file (or text for append).
3. Save: `python3 tools/memsave.py save FILE --base $H --draft DRAFT --agent "thread name / human" --reason "why" --link "conversation or incident link"` (or `append ... < text`).
   The tool re-hashes FILE under a lock. If it changed since step 1 it exits 3 with STALE and writes nothing: re-pull, redraft, take a new hash, retry.
4. `--reason` and `--link` are mandatory in spirit: say what conversation or incident caused the change (message id, thread link, PR). `--agent` names the thread/agent or the human (e.g. "Mase").
5. History: `memsave.py log [FILE]`; view an old version: `memsave.py show FILE v3`; roll back: `memsave.py rollback FILE v3 --agent ... --reason ... --link ...` (restores old content as a NEW version, nothing erased).
Do not edit files here by hand without the tool. MEMORY.md (project memory index) is a separate store: its tool already rejects stale revisions; log changes to it in CHANGELOG via a note file entry when the index changes meaningfully.

## Versioning and safe saves (required for every edit)
All edits go through `tools/memsave.py` (a git repo lives in this folder; CHANGELOG.md has one row per version: who, when, why, link, hash before->after).
1. Pull + hash: `H=$(python3 tools/memsave.py hash FILE)` and read FILE.
2. Draft your edit in a scratch file (or text for append).
3. Save: `python3 tools/memsave.py save FILE --base $H --draft DRAFT --agent "thread / human name" --reason "why" --link "conversation or incident link"` (or `append ... < text`).
   The tool re-hashes FILE under a lock. If it changed since step 1 it exits 3 with STALE and writes nothing: re-pull, redraft, take a new hash, retry.
4. --reason and --link say what conversation or incident caused the change (message id, thread link, PR). --agent names the thread/agent or the human (e.g. "Mase").
5. History: `memsave.py log [FILE]`; old version: `memsave.py show FILE v3`; roll back: `memsave.py rollback FILE v3 --agent ... --reason ... --link ...` (restores old content as a NEW version, nothing erased).
Don't edit files here by hand. MEMORY.md (project memory index) is a separate store whose own tool rejects stale revisions; note meaningful index changes in the reason of the related topic-file edit.
