# cc01_003 ICT Mentorship Core Content - Month 1 - What To Focus On Right Now (B7_cjybYQ0g)
2016-17 Private Mentorship, Month 01, teaching 3 of 8 (slides say "September 2016").
Market: USD/CHF (forex) only. Timeframes shown: daily, 4h, 1h, 15m. Duration ~25 min.
No trades; this is a homework/charting-method lesson.

## Summary
Mindset first: smart money (liquidity provider) vs speculative uninformed money; everyone
else's resting orders are liquidity. Then the Month 1 homework: keep a daily price-action
log on four timeframes with fixed lookbacks, marking fast-move origins, untested
highs/lows, "too clean" equal highs/lows, and when (day, kill zone) daily and weekly highs
and lows form. Do not forecast yet. A 15m example shows each day raiding the prior day's high or low.

## Rules
- Liquidity = buy stops / sell stops / pending orders resting above and below the most
  recently formed highs and lows ~6:40 [chart]. (Same idea as Ep 01 buy/sell-side liquidity.)
- Four price-delivery states the course is built on: retracement, expansion, reversal,
  consolidation ~9:13 [chart] [new]. A bot regime classifier could use these labels.
- Indicators (overbought/oversold) show what uninformed traders think, not where price goes; keep them off the chart ~3:26 [new].
- Chart lookbacks: daily 9-12 months (not multiple years), 4h 3 months, 1h ~3 weeks,
  15m 3-4 days ~13:38-14:12 [chart] [new]. For a bot: the window for scanning reference
  highs/lows on each timeframe.
- Mark levels price moved away from quickly (big displacement candles); they matter for
  where price should and should not go ~14:45, ~18:37 [chart: yellow "Speed" boxes] [new].
- Mark recent highs/lows that have not been retested; they will draw price later ~14:56 [new].
- "Clean" highs/lows: two roughly equal highs (or the second just short of / barely above
  the first) close together -> buy stops above; equal lows -> sell stops below. Price
  usually comes back to run them, then may continue or reverse ~15:23-16:27 [chart: gray "Too
  Clean" labels]. Matches Ep 04 / Ep 06 relative equal highs/lows.
- Log, for every week, which day the weekly high and low formed and in which kill zone
  (London vs New York) ~16:36 [chart: slide] [new].
- Log every day's high and low and the time each formed ~16:56 [new].
- Top-down transfer: mark daily levels, carry them onto 4h, add the new 4h levels, carry
  both to 1h, then do the same on 15m for the last 3-4 days ~18:04-20:35 [chart].
- The 1h chart is the intraday "bellwether" for buy vs sell, the way the daily is for
  swing trading ~19:10 [new].
- On the 15m chart, draw the previous day's high and low out to the day boundary, which
  he puts at 0:00 GMT (8 pm NY in summer) ~20:51 [chart] [conflict, see Open questions].
- Keep the analysis chart separate from the execution chart. Don't marry the analysis; if live price contradicts it, switch or stand aside ~23:46-24:30 [new].

## Trade examples
None traded. Illustration (USDCHF 15m, week of 12-16 Sep 2016) ~21:46-23:13 [chart]:
- Wed: ran Tuesday's high (~0.9790, his figure) by a little, did not continue, sold off to
  Tuesday's low, poked a pip or two under it, then consolidated.
- Thu: traded back inside Wednesday's range, rallied, then sold just below Wednesday's
  low and consolidated.
- Fri: rallied straight through Thursday's high and above the week's high (set Wed),
  taking the buy stops; Friday high ~0.9818 on the axis.
- Point: prior-day high and low are the first targets each day, and stop runs there are often only 1-2 pips deep.

## Definitions
- Smart money / liquidity provider: knows what the uninformed crowd believes and sets price; its trades are later offset at a premium ~5:00-5:35.
- Speculative uninformed money: "willing and/or unwilling liquidity" (slide) ~1:40 [chart].
- Market efficiency paradigm: the two opposing views together; price is delivered "to engineer efficiency" for smart money ~6:23, ~7:00 [chart].
- Clean high / clean low: equal or near-equal highs/lows close together ~15:23.

## Seen only on the charts
- Daily chart spans Jul 2015-Sep 2016 (~14 months). Four recent swing levels are drawn as
  horizontal rays (two highs ~0.9955/0.9890, two lows ~0.9640/0.9530; approximate,
  small text) ~17:40.
- 4h chart: rays from the Jul high (~0.9950), the end-Aug high (~0.9885), the early-Sep
  low (~0.9650) and the Aug low (~0.9530); "Speed" marks the drop from the end-Aug high
  and the mid-Sep rally; "Too Clean" marks equal highs (~0.9790) and equal lows (~0.9690)
  in the Sep range ~18:00.
- 1h chart has vertical day separators; same marks shown larger ~19:20.
- 15m chart: dotted day separators labelled Tuesday...Friday. Each day's high (red) and
  low (black) is drawn from where it formed to the next separator ~21:00.

## Open questions
- Day boundary: forex 0:00 GMT (8 pm NY in summer) here vs the 2023 midnight-NY open
  (Ep 04/Ep 08). For ES, use the 18:00 ET Globex day, midnight NY, or the RTH session for "previous day high/low"?
- "Too clean" tolerance: how equal is equal (ticks? % of ATR?) and how close in time?
  Not quantified.
- "Quick movement from a level": no candle-size or speed threshold is given.
- "Not retested": how long counts as "recent"? Probably the lookback window per timeframe.
- Weekly high/low kill-zone logging: kill zones are the forex ones (London 02-05,
  NY 07-09 in Ep 06); for ES we would also need the 08:30/09:30 windows. This is a stats
  task (which day / which window the weekly H/L forms), worth computing from our data.
- Forex-only: currency-pair choice (avoid EUR and GBP, which ICT uses), the central-bank
  pricing argument and the 0 GMT boundary. Everything else carries over to index futures.
