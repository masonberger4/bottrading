# ch34 ICT Charter Price Action Model 13 \ 2022 YouTube Model Amplified for Index Futures (kNlySn81dmo)
Recorded ~2022 / slides / 23 min. Captions only.
Source tier: Charter. 2023 wins on conflicts. INDEX FUTURES (ES/NQ) - no pip mapping needed.

## Summary
Model 13 = the 2022 YouTube mentorship model, amplified for index futures: trade intraday market structure that targets opposing PD-array-matrix objectives. Windows: FX 07:00-10:00 NY; index AM 08:30-11:00 NY, plus PM session setups. Monitor 5m down to 1m after a liquidity raid: bearish = buy-side raid (single high or relative equal highs) then rapid MSS below a recent 5m-1m low with displacement + FVG (ideally FVG at/above equilibrium of the leg). Entry = sell limit at the high of the FVG's discount-low candle (i.e. the near edge); stop = high of the premium-high candle (far edge of the FVG), exactly, no tick added. Use the first FVG found going down from 5m to 1m. Risk <= 2%, ideally 0.5-1%; halve after a loss until 50% recovered. Targets: discount PD arrays at/below equilibrium of the dealing range, previous session low, previous day low, FVGs below those.

## Rules
- Logic: intraday MSS that targets the opposing PD array (bearish -> discount arrays, bullish -> premium arrays) ~1:00-1:30
- Time windows: FX 07:00-10:00 NY; index futures AM 08:30-11:00 NY ~1:30-2:02
- Charts: 5m down to 1m after a liquidity raid and short-term MSS; the model is fractal (15m/1h/4h allowed) ~2:02-2:33
- Bearish setup: buy-side raid (relative equal highs or a single high), then rapid MSS below a recent 5m-1m low = displacement; FVG in the drop is ideal ~2:33-3:48
- Bullish setup: sell-side raid, rapid MSS above a recent 5m-1m high with displacement + FVG ~3:48-4:22
- FVG ideally at or above equilibrium of the displacement leg (bearish) / at or below (bullish) ~4:22
- Bearish entry: sell limit at the high of the FVG's lowest candle (near edge), not above it, to ensure a fill ~4:22-5:52
- Bearish stop: at the high of the FVG's first (upper) candle - not one tick above ~5:52-6:27
- Bullish entry: buy limit at the low of the FVG's upper candle; stop at the high... [ICT: "stop at the high of the discount low"] i.e. far edge of the gap (low of the first candle) ~6:27-7:04, ~12:21-12:55
- Use the FVG that forms first going down 5m -> 4m -> 3m -> 2m -> 1m ~7:04-7:40
- Risk 2% max, ideally 1% or 0.5% (frequent setups) ~7:40-8:11
- Drawdown: after a full loss halve risk until 50% recovered; keep halving on further losses (2, 1, 0.5, 0.25...) ~8:11-9:42
- PM session: bearish = buy-side raid on AM session highs or lunch-hour (12:00-13:00) highs; bullish = sell-side raid on AM lows or lunch lows; AM relative equal highs/lows take precedence over lunch-hour swings ~9:42-11:45
- Targets short: discount PD array at/nearest below equilibrium of the dealing range; below previous session low; below previous day low; FVGs below equilibrium; FVGs below those levels (multiple targets for partials) ~12:55-14:21
- Targets long: premium arrays above equilibrium; above previous session high (PM -> AM session; AM -> prior PM session); above previous day high; FVGs above; may need prior days' levels in strong moves ~15:30-16:43
- Timing (look sequentially): 08:30 news; 09:30 equities open; 10:00 (after first 30 min, Judas); 10:30 (first 60-min opening range established); 11:00 only on Thu/Fri reversal conditions (TGIF / London close alignment); 13:30 after lunch; 14:00 PM trends / AM stops purged; 14:30 final 2 hours; 15:00 final hour; 15:30 market-on-close ~16:43-20:39
- One choice setup per session (AM, PM), aligned with bias and the weekly profile; not one at every time ~21:06-22:20
- Partials are personal; no hard rule ~14:21-15:06

## Trade examples
- None on chart (slides only)

## Definitions
- Premium high / discount low of a FVG: the upper / lower candle boundaries of the three-candle gap
- Lunch hour: 12:00-13:00 NY

## Open questions
- Entry at near edge vs 2023 entry location: [conflict check] switch `m13_entry_edge = {near_edge, ce}`
- Stop exactly at FVG far edge (no tick) vs 2023 stop placement: [conflict check] switch `m13_stop = {fvg_far_edge, swing}`
- First FVG from 5m down to 1m: switch `m13_tf_cascade` [new]
- Timing ladder (08:30/09:30/10:00/10:30/11:00 Thu-Fri/13:30/14:00/14:30/15:00/15:30): compare with 2023 macros
- PM raid of AM/lunch highs/lows: switch `pm_raid_source = {am_eqh_first, lunch}`
