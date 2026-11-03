# ch28 ICT Charter Price Action Model 10 \ Swing Trading, External Range Liquidity (CTS27DsveNs)
Recorded 2019-02-16 / slides + GBPUSD 4h/15m, USDCAD / 32 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 10 (swing, stalk 50-75 pips/week, any TF): stage = weekly range expansion; setup = anchor point Mon/Tue/Wed; pattern = external range liquidity runs for BOTH entry and exit ("counterparty liquidity theory"). Sell short only above an old high / short-term high (turtle soup) in a bearish market, during a kill zone; cover only below an old low or newly formed short-term low. Three exits: partial, partial, then full exit on the third. Old lows to the left take precedence over fresh short-term lows.

## Rules
- Stage: weekly range expansion direction of the next weekly candle; setup: anchor Monday/Tuesday/Wednesday ~1:34-2:34
- Pattern: enter on external range liquidity (above old high when bearish) and exit on opposing external range liquidity (below old low) ~2:34-3:21, ~19:38-20:43
- Short entry level: an institutional level (big figure, mid figure, nearest 10 or 5 level) inside the FVG / liquidity void above the old high ~9:38-11:35
- Bearish context example: weekly bearish OB, MSS, OTE closes the liquidity void, run above the short-term high = sell ~3:21-4:28
- Exits: cover only below old lows / new short-term lows; a low forming below the equilibrium of the parent swing is a good full exit ~7:34-9:07
- Rule: you cannot sell short unless above a previous short-term high; you cannot cover unless below an old low or new short-term low (reverse for longs) ~20:11-20:43, ~61:22-62:00
- Partials: one at each new short-term low taken; two partials, the third exit closes everything; or one partial then full ~20:43-23:43, ~26:59-27:34, ~44:50-45:20
- After two partials trail the stop tightly, but not 5-10 pip stops; think three drives ~24:12-25:25
- Ignore minor highs/lows too close to the entry; wait for a meaningful one ~25:25-26:59, ~46:22-46:46
- Entry timing: raid of single high / double top during a kill zone (London or NY open), on Mon/Tue/Wed of a bearish week ~29:54-31:44
- OSOK cover: generally Thursday NY open makes the low of a bearish week; London close for day traders ~34:58-35:46
- Sell 10/15/20/30 pips above an old high in a bearish market ~19:38-20:03
- Big figure targets: price can reach 10/20/30 pips below a big figure; ICT rarely holds beyond 20 pips below ~40:58-42:42
- Old lows to the left (untouched liquidity) take precedence over new short-term lows ~27:31-27:58
- Alternative scaling: 50% / 25% / 25%, or 25% at +25 pips, 25% at +50, rest to target ~44:22-45:20, ~52:25-52:57
- Homework: find 10 sell and 10 buy examples across FX, stocks, commodities ~29:25-30:24

## Trade examples
- GBPUSD 4h Sept 2018: weekly bearish OB, short above the short-term high, partials at each new low below equilibrium ~6:40-13:34
- GBPUSD 15m week ending 2019-02-15: Wednesday run above Sunday open and equal highs, short; partials at short-term lows toward 1.2800 big figure ~28:02-42:42
- EURUSD Feb 2019 short above old high, covered at double bottom (ICT live trade) ~31:44-33:16
- USDCAD: long below equal lows, three exits at short-term highs ~45:20-48:16

## Definitions
- Counterparty liquidity theory: enter at stops on one side, exit at stops on the other

## Open questions
- Exit-only-at-external-liquidity rule with "third exit closes": switch `exit_mode = {fixed_R, external_liquidity_3step}` [new]
- Entry at institutional level inside the FVG above the old high: index mapping (big figure -> 100/50 point levels on NQ) is our interpretation
- Thursday NY open as weekly low (bearish week): testable statistic
