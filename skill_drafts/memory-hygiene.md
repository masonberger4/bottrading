---
name: memory-hygiene
description: Use at the start and end of any thread in the Stock trading algorithm project to read and update the memory folder correctly.
---

0. Check threads.md for active threads and the current laptop writer; run remote_control_status before touching the laptop.
1. Read MEMORY.md (the index), then only the topic file you need in /mnt/project-files/memory/ (decisions, results, data, laptop_ops, lessons); grep by keyword.
2. Before asking Mase a question, grep decisions.md; his answers are final and every one is a backtestable switch.
3. Top-level files are read-only unless you are a writer in ACL.json. Your own scratch pad is scratch/<your-slug>/ (free). For a top-level change run `memsave.py propose FILE --agent ... --reason ... --link ...` (text on stdin); a writer merges it. Change files ONLY with `python3 /mnt/project-files/memory/tools/memsave.py`:
   a. `H=$(python3 tools/memsave.py hash FILE)` and read the file.
   b. Draft your edit.
   c. `memsave.py save FILE --base $H --draft DRAFT --agent "<your thread or human name>" --reason "<why>" --link "<message/thread/incident link>"` (or `append` with text on stdin).
   d. Exit code 3 = STALE (someone else edited): re-pull, redraft, new hash, retry. Never force.
   e. Always say which conversation or incident caused the change. Roll back with `memsave.py rollback FILE vN ...`; history with `memsave.py log`.
4. Save what a new thread would re-ask. Writers: `memsave.py append`. Everyone else: in the same turn write it to scratch/<slug>/notes.md AND run `memsave.py propose` with the same text so the coordinator merges it. Use UTC date and who decided. Keep the MEMORY.md index short; no secrets.
5. Work over 30 min: check in and commit+push at least every 30 min.
6. When finishing, list in your final reply any fact you learned that is not in memory (one line each); the coordinator proposes them.
