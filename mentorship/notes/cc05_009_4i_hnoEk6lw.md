# cc05_009 ICT Mentorship Core Content - Month 05 - How To Use Intermarket Analysis (4i_hnoEk6lw)
Recorded Jan 2017 (lesson 3 of the January 2017 content, ~0:12) / markets: bonds, commodities, stocks, currencies in general / no price charts, slides only / 21m. Conceptual long-term (macro) material; ICT warns it is "dry" and chart-free.

## Summary
Lays out the four intermarket groups (bonds/interest rates, commodities, stocks, currencies) and their directional relationships, with 6-12 month lead/lag between them. Bonds lead stocks; commodities move against bonds and against the dollar. A list of key cross-asset relationships (DXY/gold, oil/USDCAD, Dow/Nikkei, yields/currency) is given as confirmation for long-term bias. ICT uses these relationships instead of reading economic data. Nothing here is an intraday entry rule; for an ES/NQ bot it is at most a slow higher-timeframe bias filter.

## Rules
- Use intermarket relationships only as confirmation of long-term (daily/weekly) bias, never as timing; lead/lag can be 6-12 months ~2:32-2:57, ~10:21-10:51 [chart] [new]
- Bond prices (not yields) and stocks move together; rising T-bonds support a stock bull market, falling bonds weigh on stocks and stocks eventually "pay the piper" ~5:02-5:55 [chart] [new]
- 30-year T-bond is a leading indicator for stock direction (lead up to ~a year) ~13:36-14:09 [chart] [new]
- Exception: in deflation (rare; late 1998 cited) bonds rally while stocks and commodities fall ~14:09-14:55 [chart] [new]
- Commodities move opposite to bonds; bond yields up = commodities up, yields down = commodities down ~5:55, ~12:49-13:06 [chart] [new]
- USDX inverse to commodities; strong dollar hurts grain/ag exports ~7:21-8:20 [chart] [new]
- USDX up = stocks and bonds up; USDX down = stocks and bonds down ~8:20-8:56 [chart] [new] [conflict] (rules file, Ep 06, records DXY bearish = risk-on with "indices up" already marked as our addition; this slide says the dollar and stocks rise together, so do not hard-code a DXY-down = ES-up filter)
- USDX up = commodity currencies down, and vice versa ~8:56-9:11 [chart] (forex-only)
- If several relationships line up with your long-term analysis, the bias is probably right; wide disagreement is rare ~16:06-16:49 [new]
- HTF traders who execute off daily charts must accept larger stops and more time ~16:49-17:36 [new]

## Trade examples
None. No charts are shown.

## Definitions
- Four intermarket groups: bonds & interest rates, commodities, stock market, currencies ~1:44-2:02 [chart]
- CRB index (Commodity Research Bureau, crbtrader.com): ag/grain-heavy (soybeans, wheat, corn, cattle, hogs); use with T-bonds ~9:11, ~11:20-11:53 [chart]
- Goldman Sachs Commodity Index: energy-weighted; Goldman Sachs Industrial Metal Index: zinc, tin, copper, aluminum, for global trends (not precious metals) ~11:53-12:37 [chart]
- Commodities = leading indication of inflation ~10:03-10:21 [chart]

## Seen only on the charts
- Slide "Key Intermarket Relationships": 1 USDX up = gold down; 2 gold up = AUD & NZD up (gold exports); 3 oil up = USDCAD down (Canada export leader); 4 Dow up = Nikkei up; 5 Nikkei down = USDJPY down; 6 yields down = currency down (money seeks yield); 7 gold down = USDCAD up [chart]
- The overview slide reads "Bonds & Stocks move together" under Bonds & Interest Rates, with a four-circle diagram of the groups around "Intermarket Analysis" [chart]

## Open questions
- No tie-in to intraday index trading; how (or whether) to turn the bond-leads-stocks idea into a filter (e.g. ZB/ZN trend vs ES) with a 6-12 month lag is unspecified.
- The USDX/stocks direction here (same direction) differs from the risk-on reading elsewhere; correlation regime is not addressed.
- Measurement windows for "trending higher/lower" in bonds or CRB are not given.
