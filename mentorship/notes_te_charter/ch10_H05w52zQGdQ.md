# ch10 ICT Charter Price Action Model 4 \ Trade Plan & Algorithmic Theory (H05w52zQGdQ)
Plan ~2020; algorithmic part May 2022 (uploaded 2024-01-11) / EURUSD, GBPUSD / slides, monthly, daily / 37 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Written plan for Model 4 (position trading, 500+ pips, ~2+ month moves on quarterly shifts). 20/40/60-day ranges with 60 often needed for a 500-pip target; seasonal tendency watch list; 4h premium/discount FVG converging with <= 3 SD in London/NY; European open filter on Mon/Tue/Wed; TP 100 / 250 / 500 with 80% closed at 500; 25 pip stop; re-entries allowed. Algorithmic example: EURUSD April 2022 short via sell stop at the up-close candle open after an old high run, SMT vs GBP, "offset distribution" target.

## Rules
- Preparation as in every plan; calendar events as the "smoke screen" for manipulation that starts long-term trades; lower-TF trade plans plug in to cut risk ~1:16-2:51
- Look back 20/40/60 trading days (60 max); target at least 500 pips -> often the 60-day range is needed ~3:23-4:36
- Seasonal tendencies: pre-plan per month (during the early-January holiday lull) which markets have the strongest seasonal for the coming month/quarter; only trade the highest-probability ones that can offer 500+ ~5:12-8:30
- Bearish: identify premium arrays inside the 20/40/60 window with COT hedging program bearish; expect monthly expansion down; bullish mirror ~8:30-9:47
- Entry zone: 4h premium FVG (shorts) / discount FVG (longs) converging with no more than +/-3 SD, in London or NY open; scalping protocols can cut risk to 1m ~9:47-10:56
- Targets: next logical old daily or WEEKLY low / FVG in the window that frames >= 500 pips ~10:56-12:04
- Day filter: European open on Mon/Tue/Wed (Tuesday is "70% chance" low of week in bullish weeks); longs at/below it, ideally overlapping the 4h discount FVG; 15m institutional order flow entry drill in London/NY or a sell-stop raid ~12:04-14:08
- If stopped on Monday re-enter Tuesday, then Wednesday, while the thesis holds ~13:08
- Orders: limit at SD/array convergence -/+ 5 pips; TP1 +100, TP2 +250; at +500 close 80% of the total position; let 20% run (with 4 orders: 100 / 250 / 500 / runner locked at +400) ~14:42-18:54
- Stop = array extreme +/- 25 pips; re-entries allowed ~15:45, ~18:54
- 25/50/75 stop protocol; partials pay you; gaps can jump stops ~19:25
- Risk: 1% suggested for position trading (1.5% "a little too high"); halving rules after a loss / after 5 wins ~20:31-21:39
- Seasons: work hardest in spring and fall; scale back January, December and July-August ~36:30-37:03
### Algorithmic example (EURUSD Apr 2022)
- COT 6-month hedging program bearish EUR; seasonal: EUR highs in April, down into May; target old monthly low ~22:06-25:41
- Daily: "three drives" stop runs, one more higher high, then: as soon as a candle trades through the old high, place a sell stop at the OPEN of that up-close candle (order block opening price), protective buy stop at that candle's high + 1 pip; no screen time needed ~27:11-30:45
- SMT: GBP failed to make the higher high EUR made ~30:45
- Entry 1.10865, stop 1.11850 (~99 pips) ~31:17
- Offset distribution targeting: after the old low breaks, wait for a short-term low + small retrace; the next drop targets just below that new short-term low (engineered sell stops); here the 1.0400 big figure; ~7R ~31:52-35:27

## Definitions
- Offset distribution = after a liquidity run, the consolidation/retrace that builds new stops under a fresh short-term low; the next leg runs it; use it as a cover target ~31:52-33:14

## Open questions
- 4h FVG entry (plan) vs daily OB open stop entry (algorithmic) - two entry modes for the same model (switch).
