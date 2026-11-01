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
2. Only writers may change top-level files; everyone else uses scratch/ or `propose` (see Permissions below).
3. Update the "NOW" line in MEMORY.md only for status that other threads need; keep MEMORY.md under ~3 KB.
4. Put detail in the topic file, not in MEMORY.md. Never store secrets.
5. Long sections that become stale: summarize in place and mark with the date; don't delete decisions.

## Versioning and safe saves (required for every edit)
All edits go through `tools/memsave.py` (a git repo lives in this folder; CHANGELOG.md has one row per version: who, when, why, link, hash before->after).
1. Pull + hash: `H=$(python3 tools/memsave.py hash FILE)` and read FILE.
2. Draft your edit in a scratch file (or text for append).
3. Save: `python3 tools/memsave.py save FILE --base $H --draft DRAFT --agent "thread / human name" --reason "why" --link "conversation or incident link"` (or `append ... < text`).
   The tool re-hashes FILE under a lock. If it changed since step 1 it exits 3 with STALE and writes nothing: re-pull, redraft, take a new hash, retry.
4. --reason and --link say what conversation or incident caused the change (message id, thread link, PR). --agent names the thread/agent or the human (e.g. "Mase").
5. History: `memsave.py log [FILE]`; old version: `memsave.py show FILE v3`; roll back: `memsave.py rollback FILE v3 --agent ... --reason ... --link ...` (restores old content as a NEW version, nothing erased).
Don't edit files here by hand. MEMORY.md (project memory index) is a separate store whose own tool rejects stale revisions; note meaningful index changes in the reason of the related topic-file edit.

Full spec for reuse in other repos: MEMORY_SYSTEM_SPEC.md. GitHub: branch `memory` in masonberger4/bottrading is a mirror (see spec section 7 for limits).

## Permissions (who may write what)
`ACL.json` lists "writers" (Mase, coordinator, named curator threads). Rules, enforced by `memsave.py` (refusal = "DENIED", exit 4):
- Top-level files (index topic files, README, ACL.json, tools/, skill_drafts/): writers only. Everyone else reads.
- `scratch/<your-slug>/`: your own free scratch pad. Edit it any time with `memsave.py save scratch/<slug>/FILE --base $(memsave.py hash ...) ...` (unversioned, git-ignored). Slug = your thread name lowercased, non-alphanumerics to "-" (e.g. "Run full backtests in cloud" -> run-full-backtests-in-cloud). Other agents' scratch pads are not yours to edit.
- Want a top-level change? `echo "text" | python3 tools/memsave.py propose decisions.md --agent "<you>" --reason "why" --link "..."` creates versioned `proposals/<slug>__decisions.md`. A writer reviews, merges with `save`, and notes "merged vN" in the proposal.
- `python3 tools/memsave.py verify` lists any file edited outside the tool (exit 5).
Honest limits: identity is self-declared via --agent (not authenticated); the shared mount ignores chmod so file permissions cannot enforce read-only; a raw `echo >> file` works but `verify` and git expose it and `rollback` repairs it; the platform project-memory index tool is writable by every thread and cannot be restricted by us.
