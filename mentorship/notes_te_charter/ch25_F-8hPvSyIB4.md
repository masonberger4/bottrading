# ch25 ICT Charter Price Action Model 8 \ 25 Pips Trade Plan + Algorithmic Theory (F-8hPvSyIB4)
Trade plan Nov 2020 + lecture ~May 2022 / slides + GBPUSD 5m / 29 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. FX units; ICT says 25 handles/ticks for index futures.

## Summary
Model 8 trade plan: 20-day IPDA dealing range only (no Sundays); look for 25-pip ranges that allow a run to buy-side (bullish order flow) or sell-side (bearish). Buy discount / sell premium FVGs or stop raids in stage-1/2 (re)accumulation at a calendar volatility injection; 5m institutional order flow entry drill in London/NY kill zones. ONE order, limit at convergence +/- 5 pips, TP 25 pips, stop 15 pips; then stop trading for the week. Lecture: for ES/NQ, 25 handles/week or 5 handles/day in one session; you may skip Monday and use it as intel.

## Rules
- Preparation: medium and high impact events; weekly profile from structure + calendar ~0:49-1:17
- IPDA range: last 20 trading days only (not 40/60), no Sundays; highest high / lowest low = dealing range ~1:17-1:52
- Draw: next old low/high; PD array in the direction of weekly bias on a day with a news release ~1:52-2:24
- Opportunity: a 25-pip range that frames a run above an old high (bullish) or below an old low (bearish) on 15m ~2:24-3:28
- Trade planning: convergence of manipulation opposite your bias at a calendar volatility time; buy discount FVG / sell stops in stage 1/2 reaccumulation (bullish), or short premium FVG / buy stops in stage 1/2 redistribution (bearish) ~3:28-4:35
- Execution: 5m institutional order flow entry drill inside a retracement in London open and/or NY open kill zones, or a stop raid ~4:35-5:12
- Orders: buy limit at PD array convergence + 5 pips (long) / sell limit at convergence - 5 pips (short) ~5:12
- One position, one limit TP at 25 pips; close and wait for the next opportunity ~5:47-6:18
- Stop management: at 50% of objective reduce stop 25%; at 75% move to break-even ~6:18-6:51
- Stop 15 pips (5m chart); size = equity x risk% / stop; round down ~6:51-8:43
- Loss -> halve risk until 50% recovered; 5 straight wins -> halve risk ~8:43-9:45
- Index futures version: 25 handles per week, or 5 handles per day in one chosen session, then sidelines; micros for tiny risk ~9:45-12:16
- Option: let Monday trade without you (intel), then trade Tuesday/Wednesday ~15:08-16:34
- Bias may need to change intra-week; you only need one session in alignment with the expected weekly candle ~17:39-19:45
- SMT confirmation: DXY lower low while GBPUSD makes a lower high at OTE -> short ~20:19-20:58
- Entry at FVG + 1 pipette, stop a pipette or so above the high; target 10-20 pips below the sell-side ~20:58-21:40
- After one winning setup, stop trading for the week (discipline drill) ~22:31-24:02

## Trade examples
- GBPUSD May 2022: rally into the April 26 2022 15m SIBI after BSL run, broke the swing low; NY session FVG/OTE short with USDX SMT; $5k account, 1% risk ($50) -> $300 (6%) ~16:34-22:31

## Definitions
- Volatility injection: news event on the calendar used to time the run

## Open questions
- Model 8 TP 25 / stop 15 is a fixed-R variant; index points mapping (25 handles NQ/ES) is ICT's own statement but sizing per instrument is our interpretation: switch `m8_tp_pts`, `m8_stop_pts`
- "One trade per week" cap: switch `max_trades_per_week=1`
- Skip-Monday option: switch `skip_monday`
- 25% stop reduction at 50% (here) vs 25/50/75 protocol (other plans): [internal conflict] switch
