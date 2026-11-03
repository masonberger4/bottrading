# ch30 ICT Charter Price Action Model 11 \ Day Trading, 30 Pips Per Trade (UtdXo9HJHKU)
Recorded 2019-04-27 / slides + NZDUSD weekly/daily/1h/15m / 59 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units.

## Summary
Model 11 (day trading, 30 pips/trade): stage = weekly range expansion with at least 50 (ideally ~100) pips of room to the weekly draw; setup = old DAILY highs/lows as the draw (bearish week -> old daily lows); pattern = internal range liquidity entries (FVG, void, SIBI/BISI, OB, volume imbalance) in a retracement into premium, targeting external range liquidity (below old daily low). Mon/Tue/Wed preferred; seasonal tendency helps. Take 30 pips, move stop to break-even, optional runner; exit 10-15 pips ahead of the hard level because of spread. After terminus is reached, the same model can be run in reverse (contrarian) via a MM buy model.

## Rules
- Weekly bias by institutional order flow on the weekly; target old daily lows (bearish) / old daily highs (bullish) within the weekly expansion ~1:11-3:19
- Higher odds: seasonal tendency; targets on Mon/Tue/Wed ~3:19-3:50
- Entry is not a stop run / turtle soup: enter inside a retracement once the range has started to expand, at internal range liquidity (FVG, void, OB); exit as price trades outside the daily range ~3:50-4:53
- Daily high/low need not be run for profit; objective is 30 pips ~4:18-4:53
- Probability filter: weekly chart must show a likely 50-100 pip expansion still available; if within 30 pips of the old weekly low, not this model ~9:12-10:11
- Check at Sunday open that >= 50 pips remain to the draw ~21:39-22:13, ~33:51-34:44
- Use intermarket (DXY bullish -> foreign currencies bearish) and the calendar ~19:42-20:41
- After the target (terminus) is reached the narrative can flip: trade the reversal with the same model via MM buy model (carry sell-side order blocks across the curve) ~24:26-29:29
- SIBI definition from the candle whose high starts the delivery (not the prior swing), single pass; retracement into it must be in premium (above 50% of the swing) ~34:44-36:44
- Fast fills into FVGs/SIBI = institutional liquidity pool (retail chasing); speed is the hallmark ~36:44-38:42
- 1:1 R with a high strike rate is fine; no need for 2:1 ~39:05-40:34
- Management: at +30 pips take profit, stop to break-even; newer traders may take 15 pips first; next level: first profit at 30, leave a portion for terminus; advanced: re-add the size taken off on a secondary entry ~43:19-46:34
- Break of a session low inside institutional order flow: the void above need not be filled ("support broken is resistance" only works then) ~41:33-42:21
- 15m bearish OB after the turn: sell at the OB, stop above it (~12 pips) ~46:34-47:26
- Minimum stop 12 pips; ICT prefers 15-30 ~47:04-47:51
- Volume imbalance (no candle body overlap) rebalanced = entry ~47:51-48:18
- Exit 10-15 pips ahead of the hard target level (retail spread / everyone sees it); leave a small "tracer" runner ~49:21-52:33
- 50-100 pip weekly move = minimum institutional displacement (ICT's experience, no statistics) ~56:44-57:39

## Trade examples
- NZDUSD week of 2019-04-22: DXY bullish into weekly SIBI CE; Sunday open ~100 pips above the old weekly/daily low near 0.6585; daily SIBI fill; 1h/15m short entries at SIBI, FVG, volume imbalance, bearish OB, each 30 pips; sweep of old low by 1 pip then MM buy model reversal; Thursday NY made the weekly low ~38:06-50:22

## Definitions
- SIBI: sell-side imbalance buy-side inefficiency; BISI: buy-side imbalance sell-side inefficiency
- Terminus: where the anticipated move ends

## Open questions
- Exit 10-15 pips ahead of target: switch `target_front_run_pts` (index mapping is our interpretation)
- Weekly room filter (>= 50 pips to draw at the weekly open): switch `min_weekly_room` [new]
- Contrarian reversal after terminus: switch `allow_post_terminus_reversal` (default off)
- 12-pip minimum stop: index mapping is our interpretation
