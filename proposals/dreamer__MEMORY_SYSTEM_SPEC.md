<!-- proposal by dreamer at 2026-11-01 21:58:44Z; target: MEMORY_SYSTEM_SPEC.md; reason: Add section 10: dreaming (closed loop, cursor, apply path, structure); link: Dream 2026-11-01 (Mase request, dreaming diagram); status: open -->
## 10. Dreaming (periodic curation batch)  [proposed addition; append after section 9]
Goal: memory improves without agents spending turns on it. Loop (from Mase's reference diagram "How dreaming works"):
1. Agents' daily sessions produce transcripts (threads, project chat).
2. A scheduled batch, the dreamer, takes those transcripts plus the CURRENT memory state.
3. It outputs an UPDATED memory state: new insights (facts, lessons, corrected rules) and an organized structure (split/merge/archive files, one home per rule, a thin index, pointers).
4. The next sessions read that state, so they start smarter. This arrow is the part that must exist: proposals are not the end. Proposal-only until the owner approves; then a writer from ACL.json applies them with memsave save (versioned, reasoned, linked, rollback-able); the platform index is changed only by owner/coordinator; the GitHub memory branch is updated through the usual reviewed PR. Next dream measures whether merged items stopped the re-asks.
Components: (a) skill draft skill_drafts/dream.md (the prompt); (b) scratch/dreamer/cursor.json {last_dream_utc, seen{thread_id:last_message_id}} so each run reads only new transcripts; (c) proposals/dreamer__*.md plus a ranked report proposals/dreamer__dream_<date>.md; (d) ACL: the dreamer is NOT a writer; (e) trigger: routine/scheduled task, daily, or after N finished threads.
Rules: proposal-only; never reverse an owner decision (flag it); sample newest and summaries first; cap each run to the transcripts newer than the cursor; no helper agents unless the owner asks.
What it looks for: re-asked facts, repeated stalls/errors, stale/duplicate/contradicting rules, missing pointers, slow lookups, plus structure (oversized files, rules in 3+ places, drifting index).
Approval UX: the report ends with "apply D1,L2"; owner replies in thread; coordinator or a writer thread applies and writes "merged vN" in the proposal.
