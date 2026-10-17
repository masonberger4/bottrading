# cc10_011 ICT Mentorship Core Content - Month 10 - Index Futures - AM Trend (wWCKTEhVp2o)
June 2017 lesson ("ICT Index Trading Concepts, lesson 2"). Markets: ES (ESM17/ESU17), YM (YMM17), NQ (NQM17), all 15m barchart.com charts. Slide deck, no live trade. 19 min.
Note: the barchart.com charts are in Central time (one hour behind New York); ICT converts verbally. Times below are New York unless marked CT.

## Summary
Defines the New York AM session (9:30-noon) and the "AM trend": one main price swing that usually starts at the 9:30 open off a PD array (order block / breaker / FVG, often after a run on London lows) and puts in the day's high or low between 9:30 and 10:30. Introduces the **index SMT** filter: compare ES, NQ and YM relative lows (bullish) or highs (bearish) between 5:00 and 9:30; the one index that fails to confirm signals the AM trend.

## Rules
- NY AM session for index trading = 9:30 to 12:00 (not 08:30-11:00 as in the 2023 notes; equities open is the anchor). ~00:00:52 [chart] [conflict: mentorship_rules.md uses AM session 08:30-11:00]
- The true day high or low tends to form between 9:30 and 10:30. ~00:00:52 [chart] [new]
- Between 9:30 and noon there is typically one trend/price swing daily = the AM trend. It can continue the overnight (London) direction or reverse it right from the open. ~00:01:12 [chart] [new]
- The AM trend can end 10:30-11:00, but anticipate it continuing up to noon (NY lunch). ~00:01:27 [chart] [new]
- Typical start: at/just after 9:30, price trades into a PD array (bearish OB for a down swing; previous down-close candle = bullish OB, or the FVG left in London, for an up swing) and then expands away. ~00:02:38-00:05:48 [chart] [new]
- FVG "filled" only counts when bodies trade through it; wicks into it alone are not efficient delivery. ~00:04:29 [new]
- London precursor: if London runs sell stops below an old low and leaves a bullish breaker (last up-close candles before the drop), expect expansion up from the breaker at the 9:30 open. ~00:06:25 [chart] [new]
- **Index SMT (AM):** between 5:00 and 9:30 compare relative lows (bullish order flow) or relative highs (bearish order flow) across NQ, YM, ES. One index failing to make the lower low (bullish) / higher high (bearish) that the others make = confirmation for the AM trend. ~00:08:01-00:10:27 [chart] [new] (rules file only has 2-index NQ-vs-ES or ES-vs-MES SMT)
- The 5:00 and 9:30 bounds are a scouting window, not exact pivot times; the compared swing points can be e.g. a 7:00 low vs a 9:30 low. ~00:10:41-00:13:04 [new]
- Why 5:00: London traders' lunch; European order flow builds into the US indices afterward. ~00:13:47 [new]
- Higher-timeframe bias first: daily bullish, then look on 4h/1h for PD arrays, then use SMT as the footprint. ~00:11:25 [new]
- Two entry styles once SMT is present (bullish): (a) buy on a stop above the high of a down-close candle (future bullish OB), or (b) on the index that made the lower low, treat it as a turtle soup and buy below the old low. Neither is preferred; all three indices move together after. ~00:15:32-00:16:46 [new]
- The index that ran the stops tends to move fastest afterwards (speed, not necessarily magnitude). ~00:18:36 [new]
- Frequency: a qualifying index SMT for AM trend setups shows up a few times per week. If it is not obvious, assume it is not there. ~00:16:59-00:17:37 [chart] [new]

## Trade examples (illustrations, no fills)
- ES (ESU17) 15m, down day: London drifts lower; AM session red-shaded 9:30-12:00 shows a drop from ~2,445 toward ~2,438, continuing into PM to ~2,434. "AM Trend Begin"/"AM Trend End" labels at the 9:30 and 12:00 lines. ~00:02:38 [chart]
- ES (ESM17) 15m: price opens into a bearish OB and swings down (described, not shown in detail). ~00:02:53
- ES 15m, up day: AM session spikes from ~2,440 to ~2,448 right after the open. ~00:03:48 [chart]
- ES (ESM17) 15m: London rally leaves an FVG (blue box ~2,392); at the open price wicks down into it (only wicks), then rallies off a bullish OB from 2,394.50 to 2,399.50. ~00:04:29 [chart]
- ES 15m: open drops into the previous down-close candle (bullish OB, red line ~2,351.5) and rallies 2,352 to 2,367. ~00:05:31 [chart]
- YM (YMM17) 15m: London clears sell stops (~20,865) and leaves a "Bullish Breaker" at ~20,892; AM session expands from ~20,890 to ~20,950+. ~00:06:25 [chart]
- NQ (NQM17) 15m: price runs the London low (~5,683.5, red line + starburst at ~9:30) as turtle soup, then rallies to ~5,706. ~00:07:44 [chart]
- Index SMT slide: NQ makes a lower low at the 9:30 open vs its ~5:00 low; YM and ES make higher lows (trendlines drawn under the lows from ~5:00 to ~9:30). All three rally in the AM session. ~00:08:31 [chart]

## Definitions
- AM trend / morning swing: the one main swing between 9:30 and noon. ~00:01:12
- Index SMT: crack in correlation among the three US index futures (ES, NQ, YM) at relative highs/lows within a time window; "Dow theory with timing". ~00:13:31
- Buying on a stop: buy-stop entry above a down-close candle's high so the fill happens as it becomes a bullish OB. ~00:15:45

## Seen only on the charts
- London session shaded 1:00-4:00 CT = 2:00-5:00 NY; NY AM session shaded 8:30-11:00 CT = 9:30-12:00 NY. [chart]
- Slide text: "Typically there will be an Index SMT divergence to qualify the Am Trend setups a few times per week. When it is not obvious, assume it's not there." [chart]
- In several examples the AM swing extreme (day high/low) printed around 10:30 NY.

## Open questions
- "Fail to confirm": compare against which earlier swing point? The slide implies the lowest low from about 5:00 onward vs the 9:30-area low; a coder needs a lookback rule (e.g. lowest low 5:00-9:00 vs low after 9:00).
- We cannot trade YM/NQ via Schwab, but SPY/QQQ/DIA (or ES/NQ/YM data) could serve as the three legs.
- Order-flow bias (bullish/bearish) must be set before SMT; this lesson gives no mechanical rule for it.
- Entry precision (stop/target) is deferred to lesson 5 (cc10_014).
