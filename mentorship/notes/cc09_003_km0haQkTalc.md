# cc09_003 ICT Mentorship Core Content - Month 09 - 20 Pips Per Day (km0haQkTalc)
Recorded for the May 2017 mentorship ("ICT Amplified Day Trading & Scalping", lesson 3). Market: forex (GBPJPY, USDJPY, AUDJPY, NZDUSD, AUDUSD, EURUSD, USDCAD), examples from Mar-May 2017; all 5-minute charts. Duration ~19 min. Slide deck with annotated MT4 charts (axis in broker server time; from the "New York Midnight" marker the server clock looks like NY+4, so NY times below are approximate).

## Summary
Two fixed-risk scalps aimed at a daily 20-pip objective, both turtle-soup style (fade a run on a 5m short-term high/low): (1) Asian-session fade of late-NY short-term highs/lows, 20:00-00:00 NY, yen/Aussie/Kiwi crosses only; (2) NY-open fade of a 5m short-term high/low before 10:00 NY, in the direction London already set, while the 5-day ADR is unfilled. Fixed 20-pip target and 20-pip stop. He says pattern 2 also works on ES, Dow futures, QQQ and stocks.

## Rules
- Always bank at least a partial at +20 pips on any day trade. Bot reading: the first partial goes at a fixed distance, scaled to the instrument ~0:01:16 [new]
- Before applying either setup, decide the market environment: consolidation, reversal or expansion ("market profiling") ~0:01:51 [new]
- **Setup 1, Asian range fade (forex only: JPY, AUD, NZD crosses)** ~0:02:38 [chart] [new]
  - Mark short-term highs/lows formed late in the NY session, before the Asian session starts (slide label "Late NY Stops").
  - Sell: during Asia, up to 00:00 NY, price trades above a late-NY short-term high, so fade it. Buy: price trades below a late-NY short-term low, so buy it (turtle soup).
  - Window is 20:00-00:00 NY; the setup usually completes before midnight ~0:06:30, ~0:07:28, ~0:11:22
  - Entry ideally 5 pips beyond the short-term high/low; aggressive traders use 1-2 pips. If price never reaches +5, skip the trade (no chasing) ~0:09:02
  - Timing on the 5m chart. Fixed target 20 pips, fixed stop 20 pips, no scaling ~0:04:51
  - Premise: Asia is normally a consolidation, so the first poke above a short-term high usually becomes the Asian range high ~0:05:51, ~0:06:41
  - Works even against higher-TF continuation. Selling the Asian high on a bullish day prices in the Judas swing ~0:10:17
- **Setup 2, NY expansion (all pairs; also ES/YM/QQQ/stocks on 5m)** ~0:11:36 [chart] [new]
  - Buy: in the NY session up to 10:00 NY, price trades below a 5m short-term low formed in the NY open. Conditions: London already posted the daily low (price has rallied from London), and the 5-day ADR is not yet reached. Buy below the low as a turtle soup and target expansion toward the ADR ~0:11:52
  - Sell: mirror. London posted the daily high (or very likely did), NY retraces up and runs a 5m short-term high's buy stops before 10:00, 5-day ADR still pending ~0:12:41
  - Timing on 5m, fixed 20-pip target and fixed 20-pip stop ~0:13:35 [chart: slide text]
  - Confluence in his example: the sweep also traded into a 5m FVG and an order block ~0:14:01 [chart]
  - Several setups can occur on one choppy day, each a fresh 5m low sweep ~0:15:39 [chart]
  - Requires strong conviction about what London did; the trade is a continuation of London's move ~0:16:58
  - The sweep below the 5m low is meant to lure breakout shorts and shake out existing longs ~0:17:08
- Not every day offers a setup. Scan 10-15 markets to find one daily; treat it as practice ~0:18:23

## Trade examples
- GBPJPY 5m, May 11-12 2017: late-NY short-term high (red x), Asia trades just above it after "Asian Session Start" (dotted line, ~20:00 NY), sell arrow, blue 20-pip box completed well before the NY midnight line; price later fell much further ~0:05:11 [chart]
- USDJPY 5m, May 11-12: same pattern; a 20-pip drop before midnight. He points to an older FVG on the far left as the real draw ~0:07:15 [chart]
- USDJPY 5m, Apr 27-28: probe above the late-NY high right at the Asian open, 20 pips down before midnight ~0:08:22 [chart]
- AUDJPY 5m, May 8-9: rally above the short-term high creates the Asian high; sharp drop, a 20-pip box and much more ~0:09:30 [chart]
- NZDUSD 5m, May 9-10: long. Asia probes below the late-NY low (up arrow), and 20 pips are done around midnight ~0:11:00 [chart]
- AUDUSD 5m, May 12 2017: London low, rally, NY retraces under a 5m short-term low into a 5m FVG/OB, then long; it ran well past 20 pips (the move he called live that Friday) ~0:13:47 [chart]
- AUDUSD 5m (second example): London low, NY dips under a 5m low, sharp rejection ~0:14:33 [chart]
- EURUSD 5m, Mar 30 2017: London open made the high; NY retraces above a 5m short-term high (trailed buy stops), sell, 20 pips quickly ~0:15:02 [chart]
- USDCAD 5m, May 4 2017: low labelled "London". Two longs: the NY open sweeps a 5m low, then a later sweep of another 5m low. From the axis, the second entry looks to be just after 10:00 NY, but it is not clearly legible ~0:15:42 [chart]

## Definitions
- Asian range: the 20:00-00:00 NY consolidation. Its high/low typically forms when price runs a late-NY short-term high/low ~0:05:51
- Late NY stops: the small stop pocket above/below short-term highs/lows that formed just before the Asian session; a low-volume liquidity run ~0:05:30
- 5-day ADR "pending": today's range has not yet reached the 5-day average daily range ~0:12:09

## Seen only on the charts
- The 20-pip boxes are drawn from the sweep extreme (the entry arrow sits at the probe), not from the 5-pips-beyond entry.
- In Asia examples, the probe beyond the short-term high is only a few pips. Entry arrows sit 0-2 candles after the Asian-session-start line.
- In NY examples, the swept 5m low/high is a small swing a few bars old, marked with a horizontal line and a red x.

## Open questions
- Exact Asian-session start: he says 20:00 NY verbally; the chart line is consistent with that.
- Is the 20-pip stop measured from the entry or from the swept extreme? Not said.
- What counts as a 5m "short-term" low (fractal size, lookback)? Not defined.
- For ES, what replaces 20 pips? Not given. Earlier eps use 5 handles as the low-hanging target.
- How to judge "London posted the daily low" in real time: "highly favorable of being" the daily high suggests a judgement call.
- ADR condition: is it measured from the day's low (longs) to the target, or as today's total range vs the 5-day average?
