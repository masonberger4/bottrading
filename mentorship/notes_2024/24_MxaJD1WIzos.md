# 2024 Mentorship Lecture 24 (MxaJD1WIzos): NFP Friday: news is manual intervention (no trade until 08:45+), 15m liquidity bellwether, weekly objective reached = done for the week; review of the OSOK short: OB validated on a lower TF, stop above the OB +1 tick, FVG wick tolerance = one standard deviation of the gap
Live Fri Sep 6 2024 (NFP), ~08:20-12:20 ET, NQ, 15m/1h/1m, daily. ~4h02m (long stretches of stories and rants; skipped). Captions only.
Source tier: 2024 Mentorship. No trade on the NFP; detailed review of ICT's Thursday-to-Friday OSOK short (L23, 14 contracts cover, "almost 360 handles").

## Summary
ICT watches NFP only to see which liquidity it runs: NFP, FOMC, CPI and PPI are manual interventions, not the algorithm; don't position ahead; earliest trade 15-30 minutes after (08:45). Frame the 15m key highs/lows (relative equal highs = buy-side, the slightly lower low = sell-side) before 08:30 and see which side the release takes; that is a clue for 09:30. After a week of decline into the Aug 13 daily FVG (his weekly objective, already hit by his short), the odds favour a run to buy-side, and he is done for the week. Review of the short: a daily FVG IOFED, turtle soup above an hourly high into a bearish OB (all consecutive up-close candles), validated when lower-TF bodies respected its open; entry at the candle high minus 1 tick, stop above the OB high plus 1 tick; adds; limit cover finessed a few points before the target so all 14 contracts fill. New: an FVG's wick tolerance outside its range is one standard deviation of the gap's width.

## Rules
- NEWS = MANUAL INTERVENTION: NFP, FOMC, CPI, PPI; don't position ahead; trade 20-30 minutes after, or 15 minutes if very skilled (NFP: 08:45 earliest) ~8:00-9:30
  - If already in a trade before the release, you may leave a small partial on ~9:00
  - After the shock, look at what was left behind (smooth highs/lows): that is the next target ~9:30
  - First ~3 minutes after the release: expect no fills or bad slippage; the 09:30 open after NFP may not let you in either ~55:00, ~1:20-1:21
- 15m BELLWETHER: before 09:30 (and before 08:30 news) mark the 15m key relative equal highs/lows; which one the release takes is a clue for the 09:30 session; log it in the journal every day ~11:00, ~20:00-22:00
  - Without news the same levels apply; they just take longer to reach ~38:00
  - If 08:30 runs both sides before 09:30, expect a fade and a mid-range close (example narrative) ~31:00-32:00
- WEEKLY OBJECTIVE: once the HTF target for the week is hit (here the Aug 13 daily FVG low), ICT is done for the week ("my weekly candle expired"); on a Friday after a week down into the target, odds favour a buy-side run, not a prolonged move lower ~12:00, ~46:00-49:00, ~1:22, ~1:33-1:34
- Be content with 5 handles ES / 10-15 handles NQ consistently ~1:22
- Lunch macro 11:30-13:30: always a retracement against the AM move (trailed stops); PM session from 13:30, its first 30 minutes (13:30-14:00) also form FVGs and all PD arrays ~1:44-1:46
- FIRST PRESENTATION is not limited to 09:30-10:00: any first FVG after a time anchor ~2:27
- BEARISH OB = the whole run of consecutive up-close candles, not just the last up-close candle ~2:06
  - Change of state = opening price of the lowest up-close candle in the run ~2:25
  - Validation: lower-time-frame bodies respect the OB (wicks may poke) and price trades below that opening price ~2:26, ~2:29
  - Entry range: from the opening price up to the mean threshold (half); ideally price never goes above half ~3:00-3:03
  - Stop: above the OB high + 1 tick; entry at the FVG candle high - 1 tick (to get filled) ~2:27-2:29
  - Stop can be the OB or the swing high, depending on account size ~3:03
- Bearish FVG / IOFED: price should go in only a little and not close it; trade it after 10:00 when it's above the OR ~2:42, ~2:55
- FVG WICK TOLERANCE: a wick may extend outside the FVG by up to one standard deviation of the gap's own width and the gap is still valid ("supposed to be in the book") ~2:47
- TURTLE SOUP: a reversal and a continuation pattern; enter it via an FVG; wait for a short-term high at the time of day you trade, then its pierce ~2:33-2:36
- Not every three-candle gap is a tradable FVG; in a bearish OB context, gaps above the change of state should not be traded to ~2:20
- Limit cover: place it a little before the exact level so the full size clears (18,770 vs 18,765.25) ~1:35-1:37
- Pyramid then "let it ride", stop not chased through the range ~2:57, ~3:02
- Fundamentals "left the chat" after the 90s ~54:00

## Risk / Process [beginner]
- Entry routine: exhale, pause when price enters the FVG, fire; stop below/above the imbalance candle ~1:01-1:02
- Prop firm accounts: ICT remarks he could drain them; not a recommendation ~1:07

## Trade examples
- 2024-09-06 NFP (no trade): 15m relative equal highs (buy-side) and a slightly lower low; release ran buy-side; Aug 13 daily FVG low already hit.
- 2024-09-05/06 OSOK short review (ICT): daily FVG IOFED, turtle soup above an hourly high, bearish OB validated on lower TF, entry candle high - 1 tick, stop OB high + 1 tick, pyramided; 14 contracts covered by limit near the Aug 13 daily FVG low (target 18,765.25, limit ~18,770); "almost 360 handles".

## Definitions
- FVG one-standard-deviation tolerance: wick excursion beyond an FVG of up to its own width.
- Bellwether chart: the 15m time frame for obvious pools of liquidity.

## Open questions / conflict checks
- [conflict check] NFP/news: trade no earlier than 15-30 min after the release vs rulebook N1/N4 and conflict 17 NEWS-WAIT (L08 15-30 min). More evidence for that position.
- [conflict check] Bearish OB = whole run of consecutive up-closes, stop above its high + 1 tick, entry range up to its mean threshold vs rulebook OB rules and owner #11 (conflict 12 not scored). Switch `ob_full_run_stop_high_plus1` default off.
- [new] `fvg_wick_tolerance_1sd` (allow wicks beyond an FVG up to its width before invalidating); default off.
- [new] `weekly_objective_done` (stop trading the week once the HTF target is hit); default off.
- [new] `bellwether_15m_news_side` (side taken by 08:30 news as the 09:30 bias clue); study.
- [conflict check] Holding into the next day (OSOK) vs force-flat (see L23).
