# cc03_002 ICT Mentorship Core Content - Month 03 - Institutional Order Flow (PQkcFbr61FI)
Recorded 2016-17 (Core Content, Nov / month 3, lesson 2) / EURUSD only (forex) / monthly, weekly, daily (MT4) / ~30 min.
Examples span EURUSD mid-2008 to mid-2012; no intraday content.

## Summary
Institutional order flow (IOF) = the direction in which price is seeking the next pool of large (fund-level) liquidity. Mark order blocks and the liquidity beyond candle *bodies* on the monthly, then shade the chart into bullish / bearish IOF regimes and carry those regimes and levels down to weekly and daily. Inside a regime, only trade order blocks / breakers / mitigation blocks in that direction. Wicks are treated as noise; bodies carry the institutional levels.

## Rules
- Work top-down: find OBs and liquidity on monthly, transfer them to weekly, then trade the daily inside that frame. The biggest moves come from monthly/weekly levels ~11:51, ~27:57 [chart] [new]
- Label each leg as a regime: bearish IOF from a bearish OB until the target liquidity / bullish OB is reached, then bullish IOF until the next bearish OB or buy-side target is reached ~10:12, ~11:29 [chart] (red = bearish, blue = bullish boxes) [new]
- Liquidity sits beyond candle bodies, not wicks. A sweep only needs to trade beyond the cluster of bodies; it does not need to take the wick extreme ~2:01, ~6:12, ~11:29 [new]
- An OB is "reached" once price trades into the OB candle's body; wicking through it is allowed ~8:25 [new]
- Mean threshold (middle of the OB candle) is the level bodies should respect; allow extra wick overrun past it ~4:58 (consistent with Ep 02 / Ep 07)
- After a down-leg, price is expected to return up and close back into that range (a void of down candles must be rebalanced by up candles) before seeking the next liquidity ~3:15, ~4:31 [new]
- Bearish trigger in a bearish-IOF zone: price breaks below the last up candle (bearish OB) when bearishness is expected; then sell the return to a breaker, a bearish OB, or a run above an old high ~14:17, ~25:17 [new]
- Bullish in bullish-IOF zone: wait for a break above a short-term high first, then buy the return into the higher-TF bullish OB ~22:41 [new]
- During a bullish regime on daily, every down candle (or cluster of down candles = one OB) before an up move is a re-buy; buy at the OB's halfway point ~23:36-24:07 [chart]
- Bullish objectives in order: the last up candle (bearish OB) first, then the stops above that high, then expansion into the higher-TF bearish OB ~20:14 [new]
- The daily always seeks the liquidity found on monthly/weekly charts; draw targets from those ~28:00 [new]

## Trade examples
- EURUSD monthly, 2008 top: bearish OB high/low area quoted as roughly 1.5151 / 1.5143 (captions garbled; open read as 1.51987). Price later returns into it in late 2009 ~0:54 [chart: 2008.03 candle tooltip O 1.5197 H 1.5903 L 1.5145 C 1.5762]
- Monthly 2008-2012 sequence [chart ~11:40]: red (bearish) mid-2008 to ~Oct 2008; blue (bullish) to late 2009 top at ~1.51; red to June 2010 low (~1.19); blue to May 2011 (~1.49); red to mid-2012 (~1.21). Tan bands at the bearish OBs (~1.51, ~1.47), tan boxes at the bullish lows (~1.24-1.27 in early 2009; ~1.19-1.23 in 2010-12).
- Weekly 2009-2010 ~17:44: bullish OB low read as ~1.2151 (captions "21.51"), price wicks into the down candle and expands up.
- Daily Dec 2008 ~22:12: small drop hits the high of a prior candle; high 1.2802 / low 1.2795 quoted [chart tooltip 2008.12.09 O 1.2962 H 1.3000 L 1.2795 C 1.2924]; rally into bearish OB.
- Daily 2009 ~23:36: down candle OB with high 1.3436 / low 1.3423 bought again; later OB below ~1.4626.
- Daily late 2009 top ~25:40 [chart]: break of the last up candle at ~1.51 triggers the red regime; olive boxes at bearish OB/breaker ~1.45-1.46 resold.

## Definitions
- Institutional order flow: the market seeking large institutional (fund) liquidity; bullish when it is reaching for buy-side / a bearish OB above, bearish when reaching for sell-side / a bullish OB below ~27:57
- Mitigation block: price returns into the last up candle (high down to its body) that was used to drive price lower; banks close losing shorts there, then expand ~19:01. Also: a monthly OB revisited on the daily acts as a mitigation block ~25:42 [new]
- Breaker (here): the down candle that broke highs, revisited from below to add shorts ~14:41
- Propulsion candle: named in passing at ~21:51, not defined [new]
- Bodies = interbank/institutional pricing; wicks = retail/broker spread noise ~6:12
- Market maker sell profile mentioned: consolidation, accumulation, smart money reversal, short, redistribution ~16:56

## Seen only on the charts
- Regime boxes are drawn from OB to target: red box top at the bearish OB, bottom at the swept lows; blue box from that low to the next bearish OB [chart 11:40, 14:20].
- White boxes mark bullish OB / FVG-like gaps; olive boxes mark bearish OBs / breakers inside red regimes [chart 19:20, 25:40, 27:20].
- Tan horizontal bands at each monthly bearish OB remain on the weekly/daily charts as targets.

## Open questions
- Exactly when a regime flips: on touch of the target OB, or on the break of the last up/down candle afterward? He uses both.
- "Liquidity beyond bodies" is not quantified: cluster of how many bodies, and what tolerance?
- How to define OB extent when several down candles are merged ("all one order block").
- Forex-only: broker spread excuse for wicks; how this applies to exchange-traded futures (ES/NQ) is unstated.
