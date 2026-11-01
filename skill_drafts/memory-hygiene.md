---
name: memory-hygiene
description: Use at the start and end of any thread in the Stock trading algorithm project to read and update the memory folder correctly.
---

1. Read MEMORY.md (the index), then only the topic file you need in /mnt/project-files/memory/ (decisions, results, data, laptop_ops, lessons); grep by keyword.
2. Before asking Mase a question, grep decisions.md; his answers are final and every one is a backtestable switch.
3. Change files there ONLY with `python3 /mnt/project-files/memory/tools/memsave.py`:
   a. `H=$(python3 tools/memsave.py hash FILE)` and read the file.
   b. Draft your edit.
   c. `memsave.py save FILE --base $H --draft DRAFT --agent "<your thread or human name>" --reason "<why>" --link "<message/thread/incident link>"` (or `append` with text on stdin).
   d. Exit code 3 = STALE (someone else edited): re-pull, redraft, new hash, retry. Never force.
   e. Always say which conversation or incident caused the change. Roll back with `memsave.py rollback FILE vN ...`; history with `memsave.py log`.
4. Add what you learn that a new thread would otherwise re-ask, in the same turn, with UTC date and who decided. Keep the MEMORY.md index short. No secrets.
5. Work over 30 min: check in and commit+push at least every 30 min.
