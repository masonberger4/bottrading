# 078 ICT Mentorship 2023 - Proper Learning & The Importance Of Journaling (FQqwmDJOtxk)
Recorded ~Aug 5-6 2023 (weekend), reviewing NQ week of Jul 31 - Aug 4 2023 (Fri Aug 4 = NFP).
Market: NQ1! continuous contract (TradingView). Timeframes: 1M, 1W, 1D, 4h, 60m. Duration 86 min.
Static annotated slides (one image per timeframe); no live trade.

## Summary
Mostly a lecture on journaling/back-testing: annotate every PD array after the fact, label each
with the timeframe it came from, show it on all lower timeframes, and write entries as if you
foresaw the move (positive language only). The worked example is a top-down NQ bearish week:
monthly bearish breaker + monthly SIBI -> weekly premium wick CE -> daily inversion FVG whose CE
became Friday's high -> 4h immediate rebalance -> 60m premium SIBI. Bot-relevant content is a
set of new PD-array definitions and invalidation rules.

## Rules
- Every PD array must be labelled with its source timeframe (e.g. "Monthly FVG SIBI", "Daily
  IFVG CE") and drawn on all lower timeframes; levels carried as a plain numeric list is enough
  to trade from (~27:00, ~37:30, ~1:20:53). [new] [chart]
- Bearish breaker: price should trade to the breaker low or its mean threshold, not up to the
  breaker high. If price trades through the breaker high while he is short, he scales some off
  (less bearish than wanted) (~19:27, ~55:36). [new]
- When strongly bearish, premium arrays above should NOT be reached; discount arrays should
  attract price, with down-close candles smashing through levels (~56:47). [new]
- "Three PD arrays" rule: list three premium arrays above a short. Breach of the first is
  tolerated; the second is a line of defence; through all three = probably wrong, close the
  trade even if the stop was not hit. He collapsed a live NQ short as price neared the second
  with the third just above it (~1:02:38-1:03:45). [new]
- "Mohawk" / coloring outside the lines: a wick slightly beyond a level (OB open, CE, FVG edge)
  is permissible if bodies respect it; do not exit or flip bias on it; don't put the stop just
  past that level (~58:00-58:42, ~1:02:09, ~1:11:13). [new]
- Bodies tell the narrative: weekly bodies stayed below the premium-wick CE while wicks took the
  prior weekly high (~31:20, ~57:55). [chart]
- Inversion FVG trade: once a down move passes through a bullish FVG (BISI) in a bearish narrative,
  expect a retrace to the IFVG's CE (or a bit above) and sell there; reaching the IFVG high is
  unlikely (~50:28-55:20). [new] [chart]
- Short in the 60m premium SIBI that overlaps a 4h immediate rebalance, even when price spikes
  just past the gap; stop above the swing high, not just above the FVG, which is allowed to be
  touched (~1:22:14-1:23:06). [new] [chart]
- Balanced price range (price went back and forth on the 4h) inside a daily FVG makes a full
  retrace through it unlikely, so it caps the retrace (~1:12:40-1:14:00, ~1:16:47). [chart]
- NFP Friday runs both sides: buy-side first, then sell-side (~1:25:47). (Consistent with Ep 04;
  new students should not trade it, ~1:10:05.)
- Specialise in one market; DXY can be a supporting reference (~15:15). Volume, VWAP, DOM,
  market/volume profile are not used (~8:11, ~57:17, ~1:06:59).
- Higher TFs give bias/draw; lower TFs give precision, not noise (~1:17:27).

## Trade examples
- NQ week Jul 31 - Aug 4 2023, bearish (journal, no fills shown) [chart]:
  - Monthly: bearish breaker = Sep 2021 down-close candle, high 16237.75, low 15207.75; monthly
    SIBI (Jan 2022) ~15,800-16,020; July 2023 traded into it. Monthly BISI (Jun 2023) ~14,750-15,060
    is the target if the breaker low breaks.
  - Weekly: premium-wick CE of week of Jul 17 (~15,880) capped price; target = weekly bullish OB /
    propulsion block of week of Jul 3 (~15,335).
  - Daily: Mon Jul 31 rallied into the daily SIBI (~15,720-15,910) = Monday high of week. Tue gap
    lower + bearish OB started the sell program. Wed lower gap open, large range down day through
    the daily IFVG low (~15,510). Fri (NFP) rallied to the IFVG CE (~15,590) / daily -OB open /
    IOFED (~15,550), reversed at the lower quadrant of the daily SIBI around noon, closed ~15,360
    inside the daily BISI (~15,280-15,460). Sell-side relative equal lows taken.
  - 60m: Wed Aug 2 ~02:00 ET premium SIBI (~15,700) coincided with the 4h immediate rebalance;
    short there, stop above the swing high.

## Definitions
- SIBI = FVG made by a down-close candle (sell-side delivery); BISI = made by an up-close
  candle (~13:51, ~1:05:07). "Buy-side delivery" (candles painting higher) differs from
  buy-side liquidity (~17:51).
- Consequent encroachment = midpoint of any gap, including a wick/tail (wicks treated as gaps);
  mean threshold = midpoint of an order block/breaker (~27:50-28:35). Premium wick CE = 50% of
  an upper wick (~27:42).
- Breakers are mitigation blocks by default; monthly breaker high/low = high/low of that candle
  (~13:16-13:46). [new]
- Propulsion block: an order block (down-close candle) followed by a second down-close candle
  that trades into the first but does not close through its mean threshold; zone = wick high down
  to the open, with its own CE/MT (~29:14-29:50). [new]
- Inversion FVG: an FVG that price passes fully through against it; narrative-based (only an IFVG
  once price trades through, ~53:07). Three levels: high, CE, low (not a zone) (~51:00-52:06). [new]
- Order block = change in state of delivery: the candle whose opening price is pierced; it need
  not engulf the prior candle (~53:53-54:21). [new] (refines Ep 02 "last up-close candle")
- Immediate rebalance: a gap is rebalanced at once by the next candle (wick just past its edge),
  then price runs off; one of the strongest signs of a fast move (~1:14:47-1:15:42). [new]
- Lower quadrant: 25%/75% level of an FVG via fib; Friday's bodies respected the daily SIBI's
  lower quadrant (~1:23:45). [new] [chart]
- Weekly profile = template/roadmap, e.g. "Monday high of week bearish profile" (~1:07:18). [new]
- Breakaway gap: an FVG above the IFVG high that should stay open (~1:04:12, ~1:09:35).

## Seen only on the charts
- 60m lower-quadrant line ~15,600 and daily -OB ~15,580; the Friday high wicked just above them
  (Mohawk) before the NFP sell-off.
- The 4h balanced price range is a grey box ~15,580-15,720 between the IFVG CE and daily SIBI.
- Weekly propulsion-block line ~15,335; Friday's close (~15,360) was just above it.
- Exact prices beyond the two labelled breaker values are read off the axis (~+/-20 pts).

## Open questions
- Propulsion block: which candle's MT must hold, and is it bullish-only here?
- "Three PD arrays": how far apart? does the breaker high count as one?
- Mohawk tolerance: how many ticks past a level is "a little"? Body-close test only?
- Immediate rebalance: must the wick come from the very next candle, and how far past is allowed?
- IFVG: does a single candle body closing through it qualify, or must the range pass fully?
