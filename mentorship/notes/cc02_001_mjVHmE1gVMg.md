# cc02_001 ICT Mentorship Core Content - Month 02 - Growing Small Accounts (mjVHmE1gVMg)
2016-17 Private Mentorship, Month 02, teaching 1 of 8 (slides dated October 2016). Market: forex (AUDUSD); no index futures. Timeframes: daily, 1h. Duration ~29 min. Mostly slides on risk and reward-to-risk; one worked trade.

## Summary
How to grow a small account: low fixed risk per trade, a reward-to-risk floor, and compounding. Starter target is 6% a month (about 1.5% a week), framed as one 1:1 trade a week. Worked example: AUDUSD long from a daily bullish order block after a turtle-soup sweep of an old 1h low, scaled out at R multiples 1-5 into buy stops.

## Rules
- Risk per trade: ideally 2% of equity for new traders, and no more than 2% on average ~3:41 [chart] [new] (Ep 07 uses ~1-1.3%, Ep 03 ~2.1%; 2% acts as a cap)
- Starter model: 1.5% risk per trade, 1:1 minimum, one such trade a week, about 6% a month compounded (doubles in a year) ~15:27-17:00 [chart] [new]
- Look for setups that allow 3R or more; for each $1 risked aim for $3 ~5:22 [chart] [new]
- Plan the risk before the reward. Keep size small enough that a losing streak cannot end the account ~4:15, ~5:47 [chart] [new]
- Breakeven win-rate table (minimum R:R for a given win rate): 75%: 0.3, 60%: 0.7, 50%: 1, 40%: 1.5, 33%: 2, 25%: 3 ~7:40-9:08 [chart] [new]. This is the standard (1-w)/w and works as a sanity check on backtest results.
- Be highly selective; don't force a trade every day ("inviting losses") ~16:30 [new]. Goal 50-75 pips a week; trying for more leads to losses ~14:36 (forex units; the index equivalent is the "5 handles / 1 setup per week" goal in Ep 03)
- Easiest setups for the 6% model are framed on the daily chart: an institutional order block that price returns to ~17:41, ~18:00 [chart]
- Do not buy just because price touches the daily level; wait for lower-timeframe confirmation ~18:50 [new]
- Confirmation used: on the 1h chart, price sweeps an old low (sell stops = turtle soup) into the daily OB, then trades back up through the 1h bullish OB (last down candle). Buy with a limit at that candle's open on the retrace ~19:16-21:30 [chart]
- Pick profit targets (buy stops above old highs / equal highs) before entering ~20:27 [chart]
- Stop placement: below the midpoint of the OB down candle (its mean threshold); here that came to 20 pips ~22:02-22:33 [chart] (matches Ep 07)
- Scale out at R multiples. Example: take half off at 1R, which banks 0.75% ~23:16 [new]
- Move the stop to breakeven after 2R is reached ~24:46 [new] (Ep 03 moves to breakeven after buy-side is run; a different trigger, but not a direct conflict)
- Take more off when a liquidity pool is swept (3R cleared the nearer buy stops); let a remainder run to the next pool ~24:10, ~25:21 [chart]
- Add the spread to a limit entry: forex-only (he adds 5 pips) ~21:13. For futures, use about one tick.

## Trade examples
- AUDUSD, setup on 13 Oct 2016 (1h chart), framed on the daily chart. Daily bullish OB: the down candle about 15-16 Sep 2016 (marked with arrows); level 0.7512 [chart]. On the 1h chart the old low at 0.7533 (11 Oct, labeled "Sell Stops Under Old Low - Buy Orders Paired") was swept down into 0.7512 (cyan box "Turtle Soup Long Setup") ~19:40 [chart]. Entry: buy limit 0.7542 at the open of the 1h bullish OB plus spread. Stop 0.7522 (20 pips) [chart]. Targets as drawn: 1R 0.7562, 2R 0.7582, 3R 0.7602, 4R 0.7622, 5R 0.7642. Buy stops above two old highs (about 0.759 on 12 Oct and about 0.763 on 10 Oct) [chart]. Result: 5R reached on 14 Oct, sweeping the higher buy stops (shaded box near 0.764) ~28:00 [chart]. His math: half off at 1R, the rest to 5R, comes to just over 4% on a 1.5% risk ~27:02. Called a "one shot one kill", 5:1.
- Account stats slide (labeled "Hypothetical Example Only"), October 2016 FX account: $5,000 grew to about $7,580; 10 trades, all winners (8 long, 2 short); 518 pips; average 51.8 pips; +51.54% for the month ~12:40-14:50 [chart]. Not a reproducible benchmark.

## Definitions
- Order block (bullish): the down candle just before a quick move up. Zone = from the candle's open (body top) up to its high; price returning into it is the entry area ~18:00-18:37. Note: at ~18:37 he also calls this zone a "fair value gap", which looks like a slip.
- Turtle soup: price breaks below an old low (taking sell stops), then is expected to run higher ~19:47
- "Bank sponsorship": the daily level holds and price reverses from it; this is the confirmation he waits for ~20:04
- R multiple: profit in units of the initial stop distance (shown on the chart).

## Seen only on the charts
- The daily OB level 0.7512 sits at the top of the body of the marked September down candle. On 13 Oct the 1h wick tags it almost exactly.
- The 1h entry box (cyan, about 0.7535-0.7542) is the body of the down candle inside the reversal leg, after the rally from the low.
- The R-multiple boxes are 20 pips tall each, with the stop box (red) the same height.

## Open questions
- Is the OB zone the body (open to close) or open to high? The words say open to high, which is odd for a down candle (its high is above its open, and he means the top part). Our code uses open to high, plus mean threshold.
- Is the "stop at midpoint of the down candle" the daily OB or the 1h OB? The chart shows 0.7522, which is above the daily 0.7512, so it is likely the 1h candle's midpoint, and the 20-pip size was chosen first.
- Breakeven after 2R vs the existing rule (breakeven after liquidity is run): which takes priority for the bot?
- How do 1.5%/2% caps combine with pyramiding (Ep 03/04/08)? Is total risk across adds capped at 2%?
- Scale-out fractions are left open ("not giving you structure yet"); later Month 02 teachings may define them.
