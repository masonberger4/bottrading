# 2024 Mentorship Lecture 38 (DnuCB5Stk-0): "Limit orders & volatility pinball drills": one-contract limit-order drill on every 15s/1m FVG to an old high/low, the "Indigo" entry (order block with a volume imbalance on it trading into a liquidity purge), OB valid once price crosses its open, breakaway vs measuring gap, scale out one contract per new swing high
Live Tue Oct 1 2024, ~07:20-11:15 ET (approx.), NQ (Dec), 15s + 1m, 15m, 60m, daily. ~3h57m (Asia trade review, Fight Club / "don't tell Carl", private group rant, charity, forex brokers; skipped). Captions only.
Source tier: 2024 Mentorship. Live: an Asia-session long (Sep 30 night) reviewed (8 contracts, scaled out on higher highs); then about ten "volatility pinball" drill trades on one contract with limit orders (wins and losses, explicitly not signals).

## Summary
NFP week Tuesday. First ICT reviews last night's Asia long: relative equal lows purged into a common gap / NDOG low, a down-close candle with a volume imbalance on top (the "Indigo entry model": an order block with a volume imbalance trading into a purge of liquidity), entry once price crossed the candle's opening price (that validates the OB; no engulfing close needed), stop at the lowest low (~13 handles), then one contract off each time price broke a new swing high. The rest of the stream is the volatility pinball drill: one contract, limit entry, stop and target set at entry, one and done (no partials, whichever trips first), engage every FVG on the 15s/1m chart after the market has made some jaggedness, aim for an old high/low, and log time-in-trade, max open profit, time to stop or target. Annotate hypothetical partials below each broken low and at wick CEs. Previous day's FPFVG high worked as a reaction level; the 09:31 FPFVG delivered fast.

## Rules
- ORDERS: entries and exits on limits; market orders only to exit a trade you know is offside ("from my mentor"); ICT uses market entries on stream only to prove it isn't market replay ~3:00-6:00, ~21:00
  - A limit at the exact price may not fill with size; price must trade through ~2:08
- NFP WEEK: new students don't trade Wed, Thu (08:30 preliminary employment) or Fri (NFP); experienced traders can trade after the 08:30 release ~12:00 (NFP-THU-FRI)
- INDIGO ENTRY [new]: bullish = liquidity purge (relative equal lows / trailing stops below a breakout) into a down-close order block that has a volume imbalance on top; bearish mirror ~51:00-53:00, ~1:30
  - Validated as soon as price crosses the OB candle's opening price; no close or engulfing needed ~1:18 (OB-CANDLE / OB-CLOSE)
  - Stop at the lowest low of the purge (~13 handles in the example) ~1:15
  - Simpler alternative: wait for price to trade above a real gap, enter on the retrace into it, stop at the lowest low; "a wonderful model, just not sexy" ~1:15
- SCALE OUT (multi-contract runner): each time price breaks above a new swing high, take one contract off (8 contracts, one per break) rather than trailing all ~1:27
- BREAKAWAY vs MEASURING GAP: a gap at 50% of a move = measuring gap, project an equal second leg; a gap that is not at the midpoint = breakaway, expect more; when leaving an HTF PD array, want the BISI/SIBI left open (not a classic S/R retest) ~1:23-1:28
- Previous day's FPFVG high worked as a reaction level the next day (gaps last several days) ~1:29 (GAP-LIFE)
- VOLATILITY PINBALL DRILL [beginner]: one contract only, no pyramiding; limit entry, stop and target placed at entry; one and done; every FVG (or your chosen PD array) on 15s/1m after jaggedness, aiming for an old high/low; log entry, stop, target, max unrealized profit, time to stop/target; daily for weeks to months ~11:00-18:00, ~1:33, ~2:04-2:13, ~3:07
  - Annotate a partial below each broken low and at every large wick's CE, even with one contract ~2:21, ~2:27-2:30, ~2:43-2:44
  - After a stop-out, wait for a displacement below the rejection block close and the next FVG ~2:36
- INVERSION FVG STOP: when an inversion sits under a higher stacked FVG (Model 2022), the stop must allow price into the higher gap; at minimum beyond its CE ~2:42-2:44, ~3:13
- One contract "retires you"; if you can't quit your job with one contract, more contracts only guarantee a blown account ~1:33-1:34

## Risk / Process [beginner]
- Three-ring binder section for price action drills ~25:00
- Compute your own KPIs (average trade length, profit, risk) ~2:09

## Trade examples
- 2024-09-30 Asia (live, reviewed): relative equal lows purged near the Oct 1 NDOG low / common gap; Indigo long (down-close OB + volume imbalance), stop ~13 handles at the low, 8 contracts scaled off on successive higher highs; distribution reached the high of Sep 30's FPFVG.
- 2024-10-01 AM (drills, 1 contract each): ~10 volatility pinball trades on 15s/1m FVGs toward 15m relative equal lows and a 60m wick CE; e.g. short from ~20,116.75 with hypothetical partial ~20,066; several stopped out.

## Definitions
- Indigo entry model: order block with a volume imbalance on top (bullish) or below (bearish) trading into a liquidity purge.
- Measuring gap: gap at the 50% of a price leg; predicts an equal second leg.
- Volatility pinball: one-contract limit-order drill on every FVG.

## Open questions / conflict checks
- [conflict check] OB valid once price crosses the candle open (no close needed): OB-CLOSE card.
- [conflict check] Scale out one contract per new swing high: PARTIAL-TRIGGER / EXIT-STYLE cards.
- [conflict check] New students skip Wed-Fri of NFP week: NFP-THU-FRI card.
- [new] `indigo_entry`; `scale_out_per_swing_break`; `measuring_gap_projection`; default off.
