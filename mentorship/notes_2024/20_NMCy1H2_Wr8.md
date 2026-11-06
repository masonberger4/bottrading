# 2024 Mentorship Lecture 20 (NMCy1H2_Wr8): re-entry after a stop-out (pre-stream short), lowest open of consecutive up-close candles, too-expensive premium open = don't chase, layered NDOG/NWOG = high-resistance liquidity run, 50/50 = no trade, stop at the imbalance candle and cover costs at half the first partial
Live Thu Aug 29 2024, ~09:25-11:30 ET, NQ (ES for SMT), 1m + 15s on phone. ~1h55m (normal-latency stream; rants on Nvidia earnings, elections). Captions only.
Source tier: 2024 Mentorship. Pre-stream short reviewed (with a re-entry); no trade live; a "devil's advocate" hindsight long from an FVG.

## Summary
Overnight NQ gapped up hugely after Nvidia earnings and graded beautifully by quadrants; it rallied back to Tuesday's daily low. Pre-session: ICT shorted a turtle soup above relative equal highs using a bearish OB (lowest open of the consecutive up-close candles), added, partialed, was stopped out on an over-tight stop, then re-entered short in the inversion FVG (market maker sell model) and pyramided. At 09:30 NQ opened at a large premium ORG and ran straight up into layered NDOGs/NWOG and toward buy-side at 19,694; ICT would not chase: "too expensive", and layered gaps make a high-resistance liquidity run (price tangled like a fly in a web). ES failed to make the higher high (SMT). A 50/50 picture = no trade; Caleb's model gave nothing (first presentation never retraded). The devil's-advocate long from an FVG shows his stop placement (below the imbalance candle) and moving the stop to cover costs once price is halfway to the first partial. The 10:00-hour SB reached the old high (CE of the premium wick 694.50 hit to the tick +1).

## Rules
- Grading a price swing with quadrants (not "quarters theory") ~6:30-7:30
- BEARISH OB change of state = the LOWEST opening price of the consecutive up-close candles ~8:30-9:00
- RE-ENTRY AFTER A STOP-OUT: if a stop is hit (trailed too tight) but the idea is still valid (market maker sell model, second stage of redistribution not delivered yet), re-enter at the inversion FVG and keep pyramiding ~5:30-6:00, ~10:00-11:00, ~17:00
  - Don't trail the stop aggressively inside a market maker sell model before the second-stage redistribution delivers ~10:30
- TOO EXPENSIVE: price far above the ORG low/settlement right out of the open with no retracement = don't chase longs; let it run, it comes back for a low-risk entry; prefer shorts from expensive levels ~18:00-19:00, ~29:00, ~37:00, ~48:00
  - "If you miss the bus, wait 20 minutes": another macro is coming ~19:00
  - PM alternatives: 14:00-15:00 and 15:00-16:00 SB, four macros in the last hour ~48:00
- LAYERED (nested) NDOG/NWOG above an open = magnet first ("black hole"), but many layers in the way = high-resistance liquidity run: price gets held back and chops; if it cuts through 2 candles, expect a run to the buy-side beyond ~26:00, ~30:00-31:00, ~38:00, ~1:48-1:53
  - Low-resistance liquidity run = one-sided, quick, sudden; high-resistance = back and forth; study both ~1:17-1:19
- SMT: NQ higher high with no ES higher high = waning continuation, not a top by itself; combine with a technical break down ~34:00-35:00
- 50/50 RULE: if you can frame the setup both ways, it is low probability by ICT's definition; do not trade; turn charts off ~52:00-54:00, ~1:02-1:03, ~1:06-1:07
- Caleb: once price has "done too much" without retracing to the first presentation FVG, it is an improbable condition: no trade that day ~1:05
- Trendline phantoms (CC 2017): perfect diagonal lows are retail support to fade when our tools point to an easy run ~58:00-1:00
- STOP on an FVG entry (bullish): below the imbalance (middle) candle's low minus 1 tick; conservative = first candle's low minus 1 tick ~1:39-1:40
  - Example gearing: 18 handles risk for 60-100 handle partials = ~5:1 ~1:40-1:41
- COVER COSTS: decide the first partial before entry; when price is halfway to it (e.g. 20 of 40 handles), move the stop to cover costs (commission included, not "break even"); then sit still ~1:42-1:44
- Partials are always profitable; prefer partials at forming highs into premium arrays over jamming the stop up ~1:20, ~1:51
- First partial = high of a premium SIBI above (SIBIs are down-close FVGs) ~1:26-1:27
- Bodies should stay inside a PD array; one or two ticks out on NQ allowed (L18) ~1:31

## Risk / Process [beginner]
- Back-test, forward-test, tape-read, then demo at least 3-6 months; "move slow when trying to make money, fast when protecting it" (Larry Williams) ~50:00
- Don't trade to prove anything on social media ~1:03
- Live stream latency note: normal latency to allow subtitles ~3:00

## Trade examples
- 2024-08-29 pre-session short (ICT): turtle soup above relative equal highs, bearish OB (lowest open of consecutive up-closes), adds at a VI, small partial, stopped on a tight trail, re-entered at the inversion FVG, pyramided, partial below the original consolidation; draw Tuesday's daily low.
- 2024-08-29 AM (no trade): premium ORG, straight run through layered gaps toward 19,694.25 buy-side; ES SMT; first presentation not retraded; 10:00 SB to the old high; premium wick CE 694.50 hit +1 tick.
- Devil's-advocate long (hindsight): FVG entry ~19,588-590, stop below the imbalance candle (~18 handles), first partial at the SIBI high, then the wick CE.

## Definitions
- High-resistance liquidity run: delivery held back by layered arrays/gaps; low-resistance: one-sided, fast.
- Trendline phantom: a retail diagonal trendline that ICT fades.
- Cover costs: stop moved to entry plus commission/slippage.

## Open questions / conflict checks
- [conflict check] Re-entry after a stop-out while the model is intact vs E10 / REENTRY card. New evidence for re-entry.
- [conflict check] Stop below the imbalance candle (middle candle) of the FVG vs rulebook FVG stops. Switch `stop_below_imbalance_candle` default off.
- [conflict check] Move stop to cover costs at 50% of the way to the first partial vs rulebook stop management (STOP-MGMT card). Switch `cover_costs_at_half_first_partial` default off.
- [new] `no_chase_premium_open` (skip longs when the open runs straight up from a large premium ORG with no retrace); default off.
- [new] `layered_gap_high_resistance` (count NDOG/NWOG layers between price and target as a filter); default off.
- [new] `fifty_fifty_no_trade` (discretionary; needs a proxy, ours).
- [conflict check] SMT as a "waning continuation" qualifier only: supports the rulebook "SMT is a qualifier only" side of conflict 8.
