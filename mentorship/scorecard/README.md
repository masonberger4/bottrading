# Rule conflict scorecard

An aid for Mase's deferred full review of the draft-rule conflicts. For each conflict it states one
question, lists each distinct position with ICT's words and the source video, and counts how many
separate videos support each position, with the 2023 Mentorship count and the newest date shown
next to it (Mase's rule: 2023 beats older videos). **It never picks a winner and does not touch the
engine.** Read `SCORECARD.md`; `summary.csv` is the same table for a spreadsheet.

## Files

| File | What it holds |
|---|---|
| `conflicts.csv` | `id, topic, question, in_force, digest_refs`. One row per merged conflict. `in_force` = the 2023 rule or owner directive that stays in force meanwhile. |
| `positions.csv` | `conflict, pos, position`. The distinct answers (A, B, C...). |
| `evidence.csv` | `conflict, pos, lecture, quote, ts`. One row = one video supporting one position. `lecture` is a key from `lectures.csv`. |
| `lectures.csv` | Built by `build_lectures.py` from the note headers: key, playlist, video id, date, note path. Hand fixes go in `lecture_overrides.csv` (same columns; non-empty cells win). |
| `digest_map.csv` | Where every numbered conflict in the draft digests went (card id, or "not scored" with the reason). |
| `scorecard.py` | Validates the CSVs and writes `SCORECARD.md` and `summary.csv`. |

Lecture keys: `M2023:064`, `CC:cc08_002`, `TE:te62`, `CH:ch18`, `M2024:L06`, `L2025:L57`,
`SMC2026:088`.

## How the counts work

- **Videos** counts distinct YouTube videos. Several TE videos are the same video as a 2026 SMC
  lecture (te57-te64 = SMC 021-024 and 039-042), and 2023 105 = te10; those count once, credited to the
  higher tier.
- A statement and a live trade count the same (one video, one vote). The quote says which it is.
- **2023** is the 2023 Mentorship share of that count. CC = 2016-17 Core Content.
- Dates come from the note headers; some are year-only or approximate (2026 SMC playlist order is
  not chronological).
- Quotes are ICT's words where they are in quotation marks; otherwise they are the note's
  paraphrase. Rows that end in a digest name, e.g. "(pd_arrays C2)" or "(execution D5)", carry that
  topic digest's citation and were not re-read from the note.
- Positions with no evidence row are rulebook/engine defaults with no lecture found yet.

## Appending a new batch

1. Draft the batch's notes and digest as usual (`mentorship/notes_*/`, `digests/*_draft_rules.md`).
2. `python mentorship/scorecard/build_lectures.py` (picks up the new notes; check its date).
3. For each conflict in the new digest:
   - If it matches an existing card, add `evidence.csv` rows to the right position, or add a new
     position to `positions.csv` if it is a new answer.
   - If it is new, add a row to `conflicts.csv` (reuse a topic name so it lands in the right
     section) and its positions.
   - Add a `digest_map.csv` row for it either way.
4. `python mentorship/scorecard/scorecard.py`. It stops with a message on an unknown lecture,
   position or card id.
5. Commit the CSVs and the regenerated `SCORECARD.md` / `summary.csv` together.

Sources used for the first build (2026-11-05): the Part C conflict lists of
`te_charter_draft_rules.md`, `m2024_draft_rules.md`, `m2025_draft_rules.md` and
`m2026smc_draft_rules.md` plus batches b2-b6 (100 conflicts, merged into 46 cards); the 2023
rulebook topic digests (`times.md`, `levels.md`, `pd_arrays.md`, `execution.md`, `filters.md`,
`bias.md`, `models.md`, `pre_open_entries.md`, `owner_directives.md`); per-lecture notes for the
quotes.

Batch 7 append (2026-11-05): 2026 SMC 113-124 (`m2026smc_b7_draft_rules.md`, conflicts 56-72). Seven new
cards (WICK-PRIORITY, EXIT-DEPTH, SHORT-LOCATION, PARTIAL-TRIGGER, TWO-SIDED, TF-CHOP, OB-VALID), new
positions on STOP-MGMT, FVG-VALID, GAP-LIFE, NEWS-WAIT, and evidence rows on ten existing cards; 67 and 72
are "not scored" (one source each). 53 cards in all.

2024 Mentorship L14, L16-L25 append (2026-11-06): `m2024_draft_rules.md` conflicts 20-43. One new card
(OVERNIGHT-HOLD), new positions on ORG-SIZE (D), STOP-MGMT (F), CPI-WEEK (C), FPFVG-DEF (D), and evidence
rows on seventeen cards; 30 and 39-43 are "not scored". 55 cards in all (with batch 8).

2024 Mentorship L26-L29, L31-L33, L35-L39 append (2026-11-06): `m2024_draft_rules.md` conflicts 44-66. One new card
(STOP-PLACE, which also scores 2024 C12 and C39), new positions on STOP-MGMT (G), ORG-SIZE (E), FPFVG-DEF (E), FOMC-DAY (D),
and evidence rows on twenty existing cards; 65 and 66 are "not scored". 56 cards in all.

2024 Mentorship L15, L40-L49 append (2026-11-06): `m2024_draft_rules.md` conflicts 67-93. One new card (RESISTANCE-DAY:
stand aside / adapt / forecast the high vs low resistance condition, with L36), new positions on MONDAY (C), NEWS-WAIT (F),
ORG-CE-WINDOW (C), FPFVG-DEF (F), STOP-MGMT (H), and evidence rows on nineteen existing cards; 83 and 88-93 are "not scored"
(one source each). 57 cards in all.

2024 Mentorship L34, L50-L51 append (2026-11-06): `m2024_draft_rules.md` conflicts 94-106 (playlist complete). One new card
(NDOG-DEF: 17:00 -> 18:00 only vs also the 16:14 RTH settlement -> 18:00 NDOG), and evidence rows on ORG-CLOSE, FVG-VALID,
ATH-RULE, NFP-THU-FRI, EXIT-STYLE, STOP-PLACE; 97-99 and 102-104 are "not scored". 58 cards in all. Next m2024 number: 107.
