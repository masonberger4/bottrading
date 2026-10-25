# cc05_011 ICT Mentorship Core Content - Month 05 - How To Use Bearish Seasonal Tendencies In HTF Analysis (Vb6ueaPqut0)
Recorded Jan 2017 ("lesson 4.2", ~0:13) / forex only: NZD (CME) 19-year vs 15-year seasonal chart (1997-2015), NZDUSD weekly candles one slide per year 2007-2016 / timeframes: seasonal (daily-resolution annual curve), weekly / 35m. Static slides with shaded red boxes; no intraday content, no trades with entries/stops.

## Summary
Uses the New Zealand dollar futures seasonal chart as a 12-month road map. Bearish windows (mid-Feb to mid-Mar, May, mid-Aug to Oct) can be traded short, or used to anticipate the bullish "quarterly shift" lows that follow (Mar-Apr, Jun-Jul, Sep-Oct). Then walks every year 2007-2016 on weekly charts. For an ES/NQ bot this is at most a calendar bias filter; the specific months are NZD-only.

## Rules
- A seasonal tendency is high-probability only where the long-sample line (19y, blue) and the short-sample line (15y, red) move the same direction with a sizable swing; when they chop or diverge, skip that window ~4:01-4:25, ~11:20-11:40 [new] [chart]
- Seasonals come from the futures contract. A forex pair moves with it only if that currency is the base (NZDUSD); if quoted second (USDCAD) the tendency is inverted ~0:55-1:46, ~1:01 slide [chart] (FX-only)
- Never force the seasonal. Trade it only when price technically supports it: bearish HTF market, rally into a bearish order block, an old high run, a market structure break, or a 2-3 month rally into "premium" ~12:46-13:56 [new]
- Two uses of a bearish seasonal: (a) trade the decline itself; (b) do not trade it, but treat it as the drop that delivers price into the next bullish quarterly-shift low, then buy ~15:23-15:55 [new]
- Market context picks which seasonal is favored: in a bullish HTF market the bullish windows are the trades; in a bearish market the bearish windows are ~17:43-18:11 [new]
- Bearish seasonals that line up with a quarterly shift target a move lasting 2-3 months on monthly/weekly/daily charts ~5:00-5:15 [new]
- Big macro regimes override seasonals (2008: NZD fell all year regardless of the bullish windows) ~22:08-22:35 [new] [chart]
- Retracements inside bearish windows often stop at a bullish order block (last down candle in an uptrend) or old resistance turned support, then the bullish window rallies off it ~24:20-24:38, ~25:31-25:53, ~29:16-29:22 [chart]
- Confluence he wants: seasonal agrees + HTF market already trending that way + time of day agrees + interest rates support + dollar index supports ~30:48-31:20 [new]
- Seasonals supply the "when" that indicators (e.g. divergence) cannot ~29:57-30:19 [new]

## Trade examples
No executed trades; weekly-chart retrospectives of NZDUSD (red boxes = mid-Feb to mid-Mar and May windows):
- 2007: small Feb-Mar dip, Mar-Apr low, rally to ~0.81 by July; May dip, Sep low ~0.66-0.67 then rally ~19:02-20:38 [chart]
- 2008: Feb-Mar made the yearly high (~0.82), May lower high, then collapse to ~0.52 ~21:43-22:35 [chart]
- 2009: Feb-Mar decline ~600 pips to ~0.49-0.50 low, then Mar-Apr rally all year to ~0.76 in Oct ~22:41-23:28 [chart]
- 2010: flat Feb-Mar; May drop ~700 pips to ~0.66; Jun-Jul rally; Aug retrace into a bullish OB, then 0.70 -> 0.7950 (~950 pips) ~23:34-24:55 [chart; OB not drawn on slide]
- 2011: Feb-Mar decline to ~0.72-0.73, Mar-Apr rally; May dip ~350 pips back to January highs (old resistance as support), Jun-Jul low at ~0.80 bullish OB, rally to ~0.88 ~25:02-26:00 [chart]
- 2012: Feb-Mar ~400 pip drop; May ~800 pips down to ~0.75; June low rallies to ~0.845 ~26:22-27:00 [chart]
- 2013/2014: Feb-Mar and May declines into June lows (2013); 2014 consolidation in Feb-Mar breaks up, May retrace, June high ~0.88, mid-Aug to Oct sell-off ~27:07-28:13 [chart]
- 2015: Feb-Mar dip, May decline, weak through Jun-Jul, Sep-Oct rally ~0.6050 -> ~0.6850 ~28:17-28:57
- 2016: flat Feb-Mar; May decline to ~0.67 (mid-consolidation / prior bullish OBs), then higher high ~0.745 ~29:05-29:38, ~32:49-33:07 [chart]

## Definitions
- Seasonal tendency chart: compiled annual price path of the futures contract over N years; two lengths overlaid (blue long sample, red short sample) ~3:47-4:04, ~5:43-5:58
- Quarterly shift: a HTF turn whose move unfolds over 2-3 months, the target of position trading ~4:58-5:07
- NZD contract months: Mar, Jun, Sep, Dec; June and December contracts show the strongest swings ~6:05-6:44
- Kiwi 12-month map: bearish mid-Feb->mid-Mar, May->Jun/Jul, mid-Aug->Sep/Oct, early Jan->Feb; bullish lows Mar-Apr, Jun-Jul, Sep-Oct; small long late Nov->first week Dec ~14:28-18:20

## Seen only on the charts
- The zoomed seasonal slide (~17:40) marks green boxes at the low windows (late Mar-early Apr, late May-early Jul, Sep-early Oct) and brown arrows at mid-Jan, mid-Jun, mid-Aug and late Sep peaks [chart]
- In the seasonal chart the May decline is the largest swing on the blue line (high in early May, down into early June) [chart]
- Year slides show only the two red boxes; the order blocks and pip counts he mentions are not drawn [chart]
- Slide text: "Futures or Commodity markets are not the same as Forex" (point 1 of 3) ~0:40 [chart]

## Open questions
- No equivalent seasonal map is given for ES/NQ; a bot would need to compute its own (e.g. 15y vs 20y+ average path) and apply the same "both lines agree" filter.
- "Agree" is visual; no threshold for how large a swing or how much agreement qualifies.
- Window edges ("mid-February", "around May") are loose; exact calendar dates to use are unstated.
- How the seasonal combines with the 20/40/60-day IPDA ranges (cc05_003) is not explained here.
