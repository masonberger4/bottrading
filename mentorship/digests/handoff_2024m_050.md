# Handoff: 2024 Mentorship lectures 50+ and leftovers (playlist PLVgHx4Z63paaM41aubnHOmqfeNjSAoBCV)

Written 2026-11-06, after L15 and L40-L49 were drafted (PR into `mentorship` from branch
`claude/project-thread-x1kvp6`; only Mase merges). L15 was a whisper transcript (sparse, long silences).

## Still to draft
| # | id | Title / date | Length | Status |
|---|---|---|---|---|
| 34 | -M-RAtxB-bE | NDOGs & tape reading, Sep 24 2024 | | waiting on whisper |
| 50 | 1m5yz6Vh_Dw | New Week Commentary, Dec 1 2024 | 9m | captions not synced |
| 51 | 403Dzt_Vl5Y | Dec 5 2024 Seek & Destroy Review | 13m | captions not synced |
The playlist has 51 videos, so 51 is the last. Check `data/ict_no_commentary.txt` first. These are small: hold and combine them
into one batch (about 3 files) rather than one PR each.

## Where things are
- Captions: `data/ict_captions/PLVgHx4Z63paaM41aubnHOmqfeNjSAoBCV/` on branch `origin/claude/project-thread-dqjjol`
  (`git show origin/claude/project-thread-dqjjol:<path>`); 40-49 came via PR #39 (merged) and PR #40.
- Notes: `mentorship/notes_2024/NN_<videoid>.md`. Done: L01-L29, L31-L33, L35-L49 (L30 silent).
- Digest: `mentorship/digests/m2024_draft_rules.md`. L40-L49 rules are in Part A section **A14** (grouped by topic),
  trades in Part B, conflicts 67-93 in Part C, switches at the end of Part D.
- Scorecard: `mentorship/scorecard/` (README "Appending a new batch").

## Method (worked well, low usage)
1. Branch off `origin/mentorship` (if this batch's PR is not merged, branch off `claude/project-thread-x1kvp6` and say so).
2. Clean VTT to text with `[h:mm]` markers (drop `<c>` lines). For long lectures, pick the first ~12 minutes plus the
   highest keyword-density minutes up to ~35-40 KB (keywords: entry, stop, partial, mid gap, quadrant, first presented,
   news, handles, resistance, decoupled, inversion, order block, limit, Caleb, macro, settlement). Short ones: read all.
3. Template: copy any L40-L49 note. Header "Live/Recorded <Dow> <Mon> <D> <YYYY>, ..."; check `lectures.csv` dates after
   `build_lectures.py`.
4. All rules DRAFT, switches off. 2023 Mentorship wins. "For Caleb" = [beginner]. Don't ask Mase about conflicts.

## Numbering
- m2024 digest conflicts used: 1-93. **Next is 94.**
- Not scored: 16, 19, 30, 40-43, 65, 66, 83, 88-93. C41 (weekly objective done) and C43 (Jackson Hole) now have a
  second, agreeing source (L40/L42, L15) but no opposing position, so still unscored.
- Cards this series keeps hitting: ORG-SIZE (D/E), ORG-CE-WINDOW (A/C), OPEN-RANGE-TRADE B, FPFVG-DEF, STOP-PLACE
  (B/C/E/G), STOP-MGMT (H), NEWS-WAIT (B/F), NFP-THU-FRI, MONDAY (B/C), PREMARKET-ENTRY B, RESISTANCE-DAY (new),
  EXIT-STYLE, SMT-USE, MIN-ROOM B, MACRO-GRID B.

## Scorecard gotchas
- `evidence.csv`, `positions.csv`, `conflicts.csv` CRLF; `digest_map.csv` LF. Use the csv module, keep each file's
  line ending (this batch's script read raw, detected `\r\n`, appended with matching `lineterminator`; re-writing
  conflicts.csv through csv only changed the digest_refs cells).
- Keys `M2024:L50`. Append "2024 C<n>" to the card's `digest_refs`.
- `build_lectures.py`, then `scorecard.py`; commit CSVs + `SCORECARD.md` + `summary.csv`; add a README batch line.

## Themes to watch in L50+
- Seek & destroy (L51) vs high resistance (L43, L49 say S&D is the aggressive form of high resistance).
- New-week commentary (L50): weekly profile, NWOG use, clustered gaps.
- Any follow-up on the "reclaimed FVG vs inversion FVG" presentation promised in L36/L37 (not yet given in L40-L49).
