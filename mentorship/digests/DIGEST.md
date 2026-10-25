# Topic digest instructions

You condense ONE topic across all per-video notes in `mentorship/notes/` (218 files:
`001..105_*.md` = 2023 Mentorship playlist, `cc01..cc12_*` = Core Content Months 01-12, 2016-17).
Read every notes file (skip PROMPT.md, BATCH.md). Read them whole: topic items are spread across
Summary, Rules, Trade examples, Definitions, Seen only on charts and Open questions. Also read
`mentorship_rules.md` (verified rules for 2023 Ep 01-08) and `mentorship/strategy.py` +
`mentorship/levels.py` so you know what the bot already does.

Write `mentorship/digests/{TOPIC}.md`. Do not edit any other file.

Context: the bot is backtest/paper only. It reads ES/NQ (SPX/NDX 1-min) to time trades and
trades SPY/QQQ. It cannot use COT, open interest, bonds, DXY or forex as inputs unless free daily
data exists; flag such items as "needs data: X" rather than dropping them.

Format:
1. **Rules** - one bullet per distinct rule, in operational form (thresholds, times in New York
   time, timeframes, exact conditions). Merge duplicates; cite every source as `(023 ~12:30;
   cc04_005 ~41:10)`. Mark each `[2023]`, `[CC]` or `[both]`. Mark `[chart]` if only visible
   on charts. Mark `[fx-only]`/`[bonds-only]` where it does not transfer to index futures.
2. **Conflicts** - every place ICT says different things (between videos, between 2023 and Core
   Content, or between what he says and what his charts show). For each: side A with sources,
   side B with sources, how often each appears, and which one his own trade examples follow.
   Recommend a default for the bot and say why, plus the alternative to test as a parameter.
3. **Bot implications** - what strategy.py/levels.py does now vs what the rules say: what to add,
   change or remove, and what is too discretionary to code (say why).
4. **Open questions** - undefined thresholds etc., deduplicated.

Be complete but compact: no narrative, no repeating the same rule per video. Aim for 2,000-5,000
words. End your reply with the 5 most important findings for the bot (under 200 words).
