# 101 ICT Mentorship 2023 - October 04, 2023 Market Commentary & Review (VElIka5sk0E)
Recorded Wednesday evening Oct 4 2023 (~19:30-21:00 ET), NFP week (NFP Fri Oct 6). Markets: DXY (weekly/daily/1h), EURUSD and GBPUSD (daily/weekly), ES (daily/1h), NQ (daily/1h/15m/5m/1m). Duration 91 min. Mostly a higher-timeframe recap and a long talk on trading psychology and how often to trade. The bot-relevant parts are the NFP-week rules, FVG quadrant levels, the daily mean-threshold invalidation, and a short NQ AM trade at the end.

## Summary
DXY reached the low of the weekly SIBI (107.274) that he called the week before, after taking the buy-side at 105.883. EURUSD took the sell-side below its January low, and ES reached its 4259 sell-side. He restates the NFP-week rule: trade Monday to Wednesday 11:00, then stop. He is not trading Thursday or Friday. He lists five reference levels inside an imbalance (high, low, CE, two quadrants). He calls a 1h ES unicorn a stand-alone model. At the end he reviews a live NQ long on Oct 4 off a 1m/5m BISI, targeting buy-side at 14864.50.

## Rules
- NFP week: setups are best Monday, Tuesday and up to the end of the Wednesday AM session. At 11:00 ET Wednesday new traders "close up shop": no live or demo trades, just watch the tape. Thursday and Friday are prone to manipulation ~25:12, ~28:19, ~39:39. (Already in rules; he adds that this is a "training wheels" rule for new traders, and veterans may trade those days.)
- Mondays of NFP week are always a trading day ~30:41 [new]. Outside NFP weeks he is willing to skip Monday (an accumulation day) unless the setup is obvious, or trade only the Monday PM session ~30:53-32:05 [new].
- Check the economic calendar before every trading week and before opening charts each day ~24:32 (already implied by the news rules).
- No positions over the weekend or across the 17:00-18:00 settlement because of gap risk; intraday only ~4:27-5:21, ~85:45 [new as an explicit rule; fits our intraday bot].
- The weekly opening price can't be forecast. Plan if/then responses for it before the open ~3:41, ~22:10, ~26:16.
- Gap-open protocol (bullish bias): if price opens below the support wick, it must be erased quickly and move higher. If it gaps up, look for a retrace into the prior candle's high or close and require it to hold. Then wait for lower-timeframe bullish structure: down-close candles supporting price, up-close candle highs broken, sell-side stop runs followed by displacement up ~26:16-27:16 [new].
- Daily mean-threshold invalidation for the weekly high/low: a daily close below 50% of the last down-close daily candle (bullish OB) means the high of the week is probably in. Trading through it intraday is fine; only the close counts. This does not mean go short ~32:58-34:19 [chart] [new]. In the DXY example the OB ran 106.021-106.755, so the MT was 106.388 [chart].
- When a spike through the daily MT is allowed, the deepest acceptable level is the lower-timeframe (1h) order block that has an FVG; it was 106.324 here ~37:51-38:57 [chart] [new].
- Once the weekly target is met, be content and don't look for more trades that week, especially in NFP Thursday/Friday ~34:21-35:05 [new]. (Rules line 149 calls "done for the week" a personal remark; this video states it as advice.)
- High probability = one-sided framing: if you can make any case for the opposite direction, the setup is not high probability. This gives fewer trades and a higher hit rate ~40:33-41:24 [new].
- Use the daily/weekly draw on liquidity. Once a higher-timeframe level is traded, drop to lower timeframes in the London or NY session and trade toward the next HTF level. Counter-trend scalps into nearby liquidity are allowed, but don't treat them as the turn ~65:43-66:31 [new].
- Wicks and tails are treated like gaps: their 50% is a CE level, and overshooting it slightly is allowed ~78:20-78:38 [chart] [new].
- FVG reference levels: the high, the low and the CE are primary. On a large enough gap also use the upper and lower quadrants (25% and 75%). Skip the quadrants on small gaps (his example: under ~10 pips in FX) ~51:58-53:47 [chart] [new].
- Inversion FVG: a weekly bullish FVG that price closes through becomes resistance. Use its low or CE as a sell reference if dollar strength continues ~78:57-79:37 [chart] [new].

## Trade examples
- DXY (weekly/daily): the buy-side at 105.883 (March high) was the first draw (late Sept). The weekly SIBI ran from 107.274 (low) to 110.426 (high); its low of 107.274 was hit Tuesday Oct 3. A daily FVG (blue, ~105.78-105.88) had a wick fib of 105.782/105.682/105.582 [chart]. Price dipped into the wick CE and held ~22:57-23:38 [chart].
- EURUSD (daily): the FVG ran from 1.09007 to 1.09436 [chart]. Fib marks were 25% at 1.09329, CE at 1.09222 and 75% at ~1.0911 (partly legible). Bodies respected the CE ~55:13 [chart]. A daily FVG low at 1.0615 was overshot to 1.06172 (2.2 pips) before price ran the Jan 2023 low at 1.04829 ~63:20-65:07 [chart].
- GBPUSD (daily/weekly): the wick CE was 1.22658 (wick 1.22346-1.22970) and was hit on Friday [chart]. Price then broke the weekly March-2023 FVG (1.21137-1.21672), which should now act as an inversion FVG. The longer-term draw is 1.18032 ~78:17-79:37 [chart].
- ES Dec23 (daily): the sell-side at 4259 was hit. The next sell-side is 4194.75 (relabelled from 4188.50), and buy-side is at 4399 ~83:06 [chart]. On the 1h chart, from the weekly opening gap (Friday close to Sunday open, two purple lines ~4329 and ~4350) price went lower, then retraced into the gap's lower quadrant. It broke lower, leaving a SIBI inside a breaker, which he calls a unicorn. The target was the low below, which was hit Oct 3 ~84:15-84:52 [chart]. Exact entry/stop not given.
- NQ Dec23 Oct 4 (live, real money): the context is the weekly opening gap 14891.50-14965 and the equilibrium of the range. He went long in a 1m/5m BISI (blue box, about 14826-14833 [chart]) and noted that it included a volume imbalance. Chart labels: "Stop Loss Under Equilibrium", "Fast Reach For The Buyside Here" (~14857) and "Buyside Liquidity Above Here" at the old high of 14864.50 [chart]. His target was 14864.00, two ticks below the old high ~88:45-88:58. First entry about 11:15-11:45 ET; it came back and stopped him out. He re-entered and price ran to the objective (around noon on the 1m chart) ~89:18-89:26 [chart]. Size and P/L not stated.

## Definitions
- Imbalance has five levels: the high (the candle-1 low for a bearish gap), the low, CE (50%), and the upper and lower quadrants (25/75%) ~51:58. This is not quarters theory.
- A daily FVG that traded on both sides is "inefficient" rather than a liquidity void. Once price trades back across it, he does not call it a balanced price range ~54:10-54:52 (wording unclear in the captions).
- Mean threshold = midpoint of a down-close candle (here a daily candle) ~33:00.
- Unicorn: a breaker with an FVG (SIBI) inside it, formed after a run on liquidity. He calls it a model on its own that appears on many timeframes every week ~84:31.
- NFP week shorthand: "not for professionals" ~36:54 (joke).

## Seen only on the charts
- His chart clock runs in UTC-4 (NY) [chart].
- The DXY 1h chart shows the hourly OB/FVG level 106.324 as a blue line under Oct 2 [chart].
- NQ 1h: purple lines at 14965 and 14891.50 (most likely the weekly opening gap) and a red line at 14736.50 (a swing low) [chart]. The daily chart has a cyan FVG under 14618.75 (~14420-14590) [chart].
- ES 1h: a blue box at ~4367-4378 with a red line at ~4367 (the earlier high), and a pink SIBI at 4399-4440 [chart].

## Open questions
- NQ trade: stop "under equilibrium" of which range (the BISI, or the 11:00-12:00 leg)? Neither the exact stop price nor the re-entry price is legible.
- In the ES unicorn, it's unclear whether the "lower quadrant" retrace refers to the weekly opening gap or to the range. It may need the 1m chart to read.
- He says to stop on Wednesday at 11:00 of NFP week, yet he traded NQ on Wednesday at ~11:30. Does the cutoff apply only to new traders, or is it the end of the AM session?
- The daily MT-close invalidation is stated for DXY. Should the bot apply it to ES/NQ weekly profiles in general?
- What minimum FVG size should turn on the quadrant levels for ES/NQ? His only threshold is ~10 pips in FX.
