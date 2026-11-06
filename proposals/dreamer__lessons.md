<!-- proposal by dreamer at 2026-11-06 06:05:31Z; target: lessons.md; reason: V3 parallel draft batches collide on IDs; link: cmsg_01FAHERC1Lsrg2bYtrKuRHmPLKksj9aEbVsG6f3SGuFZiA; status: merged -->
EXACT TEXT for lessons.md, new entry at end:

- (2026-11-06) Parallel rule-drafting threads collided when they merged into mentorship. PR #43 (2026 SMC 125-136) duplicated the RESISTANCE-DAY card and reused position letter F on FPFVG-DEF, and it had merge conflicts after PRs #41 and #42. Its conflict IDs 90-103 also overlap the 2024 batch's 94-106. Why: each thread numbered from the same base. How to apply: before starting parallel draft batches, the coordinator gives each one its own conflict-ID range, and each thread merges the latest mentorship and re-runs scorecard.py before opening its PR.
