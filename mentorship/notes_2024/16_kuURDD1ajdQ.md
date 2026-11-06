# 2024 Mentorship Lecture 16 (kuURDD1ajdQ): chart-logging drill on Fri Aug 23 (Powell day), first presentation FVG must form at 09:31 or later, balanced price range, event horizon between NDOG/NWOG, nested NDOG inside NWOG
Recorded Sat Aug 24 2024 (review of Fri 2024-08-23, Powell at Jackson Hole 10:00), NQ, daily + 1m. ~47m. Captions only.
Source tier: 2024 Mentorship. Review lecture (first video on Caleb's channel); no trade shown live here (ICT says he was trading behind the scenes on Friday's stream).

## Summary
ICT shows Caleb how to log each session (screenshot + typed notes). Daily: after reaching the RB and just missing the wick CE, NQ broke down; Friday worked into the mean threshold of a July 22 daily bearish OB and should not trade into the upper half of the daily SIBI/VI it had left. 1m: a balanced price range (back-and-forth delivery, then displacement out) is "guarded"; a return through it implies manual intervention. Friday's first FVG (formed at 09:31 or later) was carried through the day: price respected it at lunch and the 15:45 low printed at its bottom. During Powell's speech the opening run up was a Judas (buy-side taken first, then turtle soup and a bearish OB). Draw: the Aug 23 NDOG nested inside the Aug 18 NWOG, plus the "event horizon" (midpoint between NDOG/NWOG). The ORG's undelivered portion was filled at lunch. 200+ handles down.

## Rules
- DAILY: after leaving a daily VI decisively (went through it, then back below), price should NOT trade into its upper (premium) half; the up-close candle there becomes a daily bearish OB to trade intraday ~11:00-12:30
  - Missing a daily wick CE on the run up = underlying weakness ~7:30
  - Work daily PD arrays one level at a time ~7:00
- VOLUME IMBALANCE: two adjacent bodies that do not touch or overlap (any colour); even one tick counts; wicks may overlap ~9:00-10:00
- BALANCED PRICE RANGE: a range where price delivered up and down (buy side and sell side) back and forth, then left with displacement; extend it through the day ~14:00-17:00
  - Buy stops above it = high-resistance liquidity; reaching back through it takes something significant (manual intervention); if it happens, don't chase, stop for the day ~16:00, ~18:00
  - Propulsion block: an up-close candle inside the bearish delivery after the OB change of state; acts as an accelerator ~14:30
- FIRST PRESENTATION FVG (09:30-10:00): the imbalance candle must be 09:31 or later; an FVG that needs the 09:30 candle does not exist on RTH-session charts, so ignore it (must agree on ETH and RTH) ~20:00-21:00, ~38:00
  - Carry it all day to 15:45; it is respected at lunch and in the 15:15-15:45 macro (Friday's 15:45 low printed at its bottom) ~40:00-43:00
  - It is Caleb's "number one" level to log every day ~46:00
- OPENING RANGE SIDES: if both a clean relative-equal high (buy side) and relative-equal low (sell side) form in the opening range, wait for the first one to be taken; that run is the fake (Judas) ~21:30-22:00
  - No accumulation (several candles) at the CE of a BISI on the way down = expect a sharp drive higher again (another drive above the high) ~22:30, ~27:00
  - Failure to reach an NDOG above = weakness; the OB opening price crossed = change of state; anywhere between that open and the daily OB mean threshold is a short, add (pyramid) along the way ~24:00-25:00
  - Inversion FVG: should keep the upper half unfilled on the retrace; a return must be rejected sharply ~25:30-26:30
- NESTED GAPS: an NDOG sitting inside an NWOG = strong draw ("black hole") ~29:00
- EVENT HORIZON (private-mentorship PD array): midpoint (with quadrants) between two opening gaps above/below price: NDOG-NDOG, NDOG-NWOG or NWOG-NWOG, no preference; price is drawn into it; bodies stay inside it ~30:00-33:00
  - NWOG lookback for this: max 60 days; NWOG kept 5 weeks for beginners, older than 60 days not used ~32:30
- ORG: 70% midpoint statistic restated; undelivered portion (settlement to the 09:30 candle low) projected forward; filled later (here at lunch) ~34:00-36:00
- FED CHAIR SPEAKING: manual intervention likely; the first move is usually fake; don't chase; trade after high-impact news drivers (FOMC, NFP, CPI, PPI) ~16:30-17:00, ~41:30-42:00
- Final hour macro 15:15-15:45 ~42:00

## Risk / Process [beginner]
- Log every session: screenshots plus typed notes (PowerPoint or notes app), annotate your own charts, not ICT's ~1:00-2:00, ~44:00
- Notes should cover the high and low of the day, the levels outlined in advance and how price used them ~8:30, ~45:00

## Trade examples
- 2024-08-23 short (narrated, from Friday's stream): opening rally took buy-side (Judas during Powell), turtle soup, bearish OB below the July 22 daily OB MT (19,881.75 MT); daily SIBI/VI CE 19,943; inversion FVG; draw to the Aug 23 NDOG nested inside the Aug 18 NWOG and the event horizon; ORG undelivered part filled at lunch; low of the day at 15:45 at the bottom of the first presentation FVG. 200+ handles.

## Definitions
- Balanced price range: two-sided delivery inside a range, then displacement out of it.
- Event horizon: midpoint (quadrants) between two nearby opening gaps (NDOG/NWOG) above and below price.
- Propulsion block: an OB-type candle inside an established delivery that accelerates it.

## Open questions / conflict checks
- [conflict check] First presentation FVG at 09:31 or later: refines L14; check how the engine dates the 09:30 bar (ETH vs RTH). Switch `first_fvg_min_0931` default off.
- [new] `event_horizon_target` (midpoint between NDOG/NWOG gaps, 60-day NWOG lookback); default off.
- [new] `balanced_range_guard` (no long through a balanced price range; stop for the day if it is reclaimed); default off.
- [new] `nested_gap_draw` (NDOG inside NWOG); default off.
- [conflict check] NWOG lookback 60 days here vs L03/L08/L13 "5 weeks" (conflict 1 GAP-LIFE): this lecture says 5 weeks is the beginner baseline and 60 days the maximum. Evidence for both.
- [conflict check] Fed chair speech = skip the first move vs rulebook news handling (NEWS-WAIT).
