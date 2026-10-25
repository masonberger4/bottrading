# cc11_003 ICT Mentorship Core Content - Month 11 - Stock Mega-Trades (kny8Kpisvoc)
Recorded July 2017 (charts dated Jul 21 2017), labelled "lesson three" of the stock mega-trades series. Markets: US stocks and the cash indices (Dow $DOWI, S&P cash, Nasdaq Composite $NASX). Timeframe: daily only (1-year barchart.com comparison charts). Duration 53m.
Note: this is a stock-selection and swing/position lesson (holds of months, executed with options), not a day-trading lesson. Very little transfers to an intraday ES/NQ bot. The useful parts are the daily index SMT, the seasonal/quarterly timing and the "don't buy a gapped-away move" filter.

## Summary
A "mega trade" is a stock move that lasts months, usually 6-9 or more. ICT's process: anticipate new earnings leaders around the quarterly earnings shifts, line them up with seasonal tendencies, require the three major averages to be rising or poised to rise, use IBD (Investor's Business Daily) lists as the fundamental and relative-strength screen, then buy only stocks that made a higher low while the Dow made a lower low (index SMT). He would express the trade with call options. Long side only.

## Rules
- Mega trades are long only, because the stock market is predisposed to go up. Short selling is moves that are fast, short and abrupt, and is left for a later lesson (~5:30, ~52:07). [new]
- Quarterly shifts: about every three months the market tends to form an intermediate-term turning point. For stocks these line up with the quarterly earnings releases (~0:44-1:45, [chart] slide with vertical lines near Jan, Apr and Jul). [new]
- Seasonal tendency for stocks: a low early in the year, a rally into spring, consolidation through summer, then the best buying opportunity in Sep-Nov leading into a year-end rally. Q1 (around March) and Q3 (fall) earnings are the key overlaps (~2:06-4:20, [chart] 20-yr and 15-yr seasonal curve). [new]
- Major market direction filter: are the Nasdaq, S&P and Dow rising together, or poised to? Strong stocks can rally alone, but they accelerate when the broad market rises (~4:26-6:55). [new]
- Index SMT on the daily chart: when one of the three averages makes a higher low while the other two make lower lows, expect higher prices. Example: Dow and S&P made lower lows on Apr 19 2017 versus Mar 27 2017, while the Nasdaq held a higher low (~18:59-19:12, ~29:08-30:13, [chart] the $DOWI chart shows a lower April low; the $NASX tooltip shows the Apr 19 low at 5,856.34). This extends the Ep 03/04 ES-vs-NQ and ES-vs-MES SMT to a three-index daily form. [new]
- The average that refuses the lower low shows where the buying is: Nasdaq holding means technology leads (~48:46-48:56). [new]
- These SMTs show up at the logical quarterly times, about every 3-4 months (~51:53-52:03). Between spring and fall (usually consolidation), an index SMT can still time short-term buys (~23:26-24:03). [new]
- Stock entry filter: the stock itself must make a higher low (relative strength against the Dow) at the same time the Dow makes its lower low. If the stock made a lower low, it is rejected even if it later rallied (LITE, STMP, YY, AAOI) (~30:42-31:23, ~33:16, ~38:13, ~45:48, [chart] LITE fell from ~60 to ~42 in Apr-May). [new]
- Prefer stocks basing or consolidating during the SMT. Skip one that has already gapped away from its consolidation, because the gap may fill. NTRI was skipped; it pulled back exactly to the top of its gap and held (~31:47-32:45, ~46:00). For a bot: don't chase price that has left a large open gap above its base. [new]
- An extended run with no consolidations is suspect. MASI rose a little more, then fell; he calls it a turtle soup (~43:23-43:53). [new]
- Price filter: prefer shares above $20, ideally above $25. A price above $100 is fine because options supply the leverage (~35:31-35:49, ~46:24). Stock-only. [new]
- Leaders only: in a bullish market, pick the strongest sector, the strongest industry group inside it and the strongest stock inside that group (~14:23-15:15, ~16:55). [new]
- IBD screen: use the IBD 50 or Sector Leaders lists and require a SmartSelect Composite Rating of 98 or higher. That rating blends EPS, RS, industry-group RS and accumulation/distribution ratings (~36:06-36:28). Being on the list does not mean the stock will perform (MKS Instruments fell). The SMT is the deciding test (~47:38-47:52). [new]

## Trade examples (hindsight paper picks, daily charts, entry near the April 2017 SMT higher low)
- FB: higher low in April while the Dow made a lower low; about 140 to 164-165, a $24 move ([chart] slide "24 Dollar Move", with red lines marking the Dow lower low against the FB higher low) (~18:46-19:51, ~44:50).
- TAL: about 100 to 150 ([chart] Mar 29 2017 low 100.88, Apr 7 low 105.73, Jul 21 close 145.73) (~27:23-27:50).
- ANET: based in consolidation; 130 to 162 ([chart] Apr 12 2017 low 130.09) (~33:53-34:39).
- FOXF 27 to 37; PAYC 58 to 73; PYPL 42 to 59, gapping up after the SMT; CNC 70 to 86; PLAY 60 to 73; PRAH up 16-17; ATVI 49 to 62; BABA 112 to 155 ([chart] Apr 18 2017 low 110.87) (~37:07-46:53).
- CTRL: technically valid but under $20 (+$10) (~35:18-35:49).
- Rejected: LITE, STMP, YY, AAOI made lower lows; NTRI had gapped away; MASI was over-extended and could have lost.

## Definitions
- Mega trade: a large stock move lasting months, usually 6-9 or more (~0:22-0:43).
- Quarterly shift: an intermediate-term turning point about every 3 months, tied to earnings in stocks (~0:44, slide).
- Index SMT (stock form): divergence among the Nasdaq, S&P and Dow lows on the daily chart. One average makes a higher low while the others make lower lows (~23:38-23:49).
- Relative strength divergence: a stock makes a higher low while the Dow makes a lower low. He credits the idea to Larry Williams, combined with O'Neil's CAN SLIM, and calls it his "silver bullet" for stocks (~25:12-25:23, ~47:58-48:13).

## Seen only on the charts
- Slide "Seeking Megatrades" lists 6 steps: anticipate new earnings leaders, plan seasonal overlaps annually, check the major index direction, run a fundamental screen, filter leaders by relative strength, and use option prices for paper trades too ([chart] 23:40).
- The comparison charts are barchart.com daily OHLC charts of the stock with $DOWI overlaid in green on a left-hand scale.
- The IBD 50 table (Jul 21 2017) shows composite, EPS and RS ratings of 96-99 and A/B accumulation grades.

## Open questions
- No intraday rules. The only bot-relevant ideas are daily three-index SMT as a bias filter (Nasdaq vs S&P vs Dow; for us QQQ vs SPY vs DIA) and the quarterly/seasonal timing. Should these become a daily or weekly long-bias filter for the intraday bot?
- How should a "lower low" be measured: by wick or by close, and against which prior swing? He compares the Apr 19 lows with the Mar 27 lows without a lookback rule.
- No entry trigger, stop or exit is given for the stock or option trades; he defers those to the August options and Greeks material and the PDFs.
