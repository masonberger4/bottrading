# 052 NDOG - New Day Opening Gap - Part 1 (Sh-bDHWNpsk)
Discussed: ES (E-mini S&P, JUN 2023 contract), gap formed Wed May 3 2023, tracked through NFP Friday May 5 2023. Timeframe shown: 5m only. Duration ~9 min.

## Summary
Defines the New Day Opening Gap (NDOG): the range between the 17:00 ET futures close and the 18:00 ET reopen. Only meaningful gaps (more than ~1 handle) are used; they are extended forward as support/resistance/equilibrium levels for the rest of that week only, and dropped when the week ends. Used as confluence with other PD arrays, plus a simple Asian-session scalp to reprice the gap.

## Rules
- NDOG = the price range between the previous session's closing price at 17:00 ET and the first traded price at the 18:00 ET reopen (the 1-hour futures break). Both prices count as levels (high and low of the gap). ~0:46-1:58 [chart] [new]
- NDOGs form Mon-Thu evenings only. The Friday 17:00 close to Sunday 18:00 open is the NWOG, not an NDOG. ~1:35-1:50 [new] (this also fills in the NWOG definition, which the rules file says was missing in Ep 05)
- Labelling: ICT names the gap by the calendar date of the 17:00/18:00 prints (his "May 3"), while TradingView counts it as the May 4 session. A bot must be consistent; using the close date is ICT's convention. ~2:00-2:14 [chart] [new]
- Minimum size: ignore gaps of 1-2 ticks; there is no fixed handle count, but he prefers more than one handle (ES points). ~4:03-5:01 [new]
- Lifetime: extend the NDOG levels forward through the rest of the current week; once the week closes, discard them (not used in the next week). ~5:03-5:28 [new]
- How many: he uses the first meaningful NDOG of the week and extends it through the week (in the example it was the only meaningful one; the Thu May 4 17:00/18:00 gap was not drawn). ~5:29-5:46 [chart] [new]
- A gap being traded through/closed does not invalidate it; price keeps returning to and gravitating around its high, low and middle. ~5:50-6:14 [chart] [new]
- Use: support, resistance and equilibrium (price consolidates around the gap's levels/midpoint). Strongest when it coincides with another PD array (FVG, OTE, breaker); not a standalone signal, only confirmation of an idea already formed. ~2:56-3:04, ~6:16-6:55, ~7:58-8:15 [chart] [new]
- Body rule at the level: wicks can pierce the NDOG high/low, but candle bodies not closing beyond it confirms support. ~7:36-7:52 [chart] (echoes the existing body-respect rules)
- Repricing trade: if price gaps down at 18:00 and hasn't yet traded up to the NDOG high (the prior 17:00 close), expect it to; consolidation around the NDOG low after the open -> buy for a scalp to the NDOG high. Mirror when it gaps up (sell toward the NDOG low). Described as an easy Asian-session scalp. ~8:18-8:48 [chart] [new]

## Trade examples
- ES 5m, Wed May 3 2023 (no live trade, illustration). 17:00 close = NDOG high 4096.25; 18:00 open = NDOG low 4087.00 (gap down ~9.25 handles) [chart]. After the open price dipped to ~4075, held around the low, then rallied through 4096.25 by ~20:00-21:00 ET: the gap repriced the same evening (the Asian scalp example). ~8:18-8:44 [chart]
- Thu May 4: 4096.25 acted as resistance several times (~07:00-09:00 and ~13:00); price dropped to ~4064 midday, then consolidated around 4087 during the evening session. ~2:56-3:47 [chart]
- Fri May 5 (NFP): during London (~04:00-05:00) price swept relative equal lows just under the NDOG low (~4085-4086) inside an FVG/OTE, then rallied. A low-high-lower-low bullish breaker formed. Around the 08:30 release price dug back down to the NDOG high (wick to ~4093, bodies held above 4096.25) and then ran to ~4162 by ~14:00-15:00. ~6:30-7:58 [chart]. No entry/stop/size was given.

## Definitions
- NDOG: range between the 17:00 ET close and the 18:00 ET reopen of CME futures, Mon-Thu. "NDOG High" / "NDOG Low" are the gap's two edges. ~0:46-2:24 [chart]
- NWOG (restated): the gap between Friday's close and Sunday's open. ~1:43
- Equilibrium of the gap: price gravitating around the middle of the high/low. ~2:58 (implies the midpoint is a level, like CE; not stated)

## Seen only on the charts
- Levels are drawn as horizontal lines from the 17:00/18:00 bars to the right edge, labelled ":: May 03, 2023 NDOG High ::" 4096.25 and "NDOG Low" 4087.00. The chart is in UTC-4 (New York) with ETH (extended hours) on.
- The 18:00 open bar's wick reached ~4075 below the NDOG low before the gap repriced.
- No NDOG drawn for May 4 17:00->18:00; the separation there looks small.

## Open questions
- "First NDOG of the week" vs. the example using Wednesday's: is it the first meaningful one (>1 handle), or always Monday's? Our reading: the first one that passes the size filter, then keep it through Friday. Should later meaningful NDOGs be added too? Part 2 may clarify.
- Size threshold: ">1 handle" for ES; how to scale for NQ or for SPY/QQQ (SPY has no 17:00-18:00 break; the equity analogue is unclear: 16:00 close vs. 04:00 pre-market or 09:30 open).
- Is the gap's midpoint (CE) an official level? Implied by "equilibrium", not stated.
- Which price counts as the close: the last trade of the 16:55 5m bar (17:00 settle) or the official settlement price? He uses the chart's last traded price.
- Repricing scalp: no entry trigger, stop or session cutoff given beyond "Asian session".
