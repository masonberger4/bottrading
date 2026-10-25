# cc08_004 ICT Mentorship Core Content - Month 08 - Projecting Daily Highs & Lows (JKzEhfwV1dY)
April 2017 Core Content, lesson 4 of the day trading model. Market: forex (GBPUSD daily and H1, 27-31 Mar 2017; chart server time appears to be NY+4, he calls the 18:00 candle "2 pm New York"). Duration ~30 min.

## Summary
Extends the CBDR (cc08_003). Once London has made the Judas swing ("protractionary" move against the day's direction) and the HOD/LOD, measure how far it went from the CBDR, in CBDR multiples. That distance becomes a unit that is stacked in the day's real direction from the opposite CBDR edge to project the daily low (sell day) or high (buy day). Projections only mark where time and price overlap; PD arrays (OB, FVG, rejection block) decide the actual turn.

## Rules
- Prerequisites, same as cc08_003: CBDR 14:00-20:00 NY, < 40 pips (ideal 20-30); > 40 pips -> stand aside from CBDR projections that day. Needs a directional bias from the daily PD array matrix (premium -> sell days, discount -> buy days) ~3:01-3:28, ~24:46-25:10 [chart] [new]
- Measure on bodies first (highest/lowest open or close in the window), also check wicks ~3:39-4:19 [new]
- Judas extension: on most days London moves 1-2 SDs against the daily direction to set the HOD (sell) / LOD (buy); rarely beyond 3 SD (SD4 = news) ~0:58-2:45 [new]
- You don't need to know the extension in advance; measure it after the London high/low has formed, then use it for New York continuation ~1:35-2:10 [new]
- Projection unit = the full distance used to make the London extreme: CBDR range plus the SDs price extended (CBDR low to London high on sell days; CBDR high to London low on buy days) ~9:37-10:13, ~15:49-16:13 [chart] [new]
- Sell day: stack that unit downward from the CBDR low, 1x, 2x, 3x. Buy day: stack it upward from the CBDR high ~12:43-13:15, ~17:05-17:29 [chart] [new]
- Each further unit is used only while price keeps going and the time window is still open; take profit at the unit that coincides with the time window and a PD array ~13:21-13:50, ~22:52-23:28 [new]
- Time windows for the projected low/high: London close kill zone 10:00-12:00 NY (projected London-close cap at the noon close); if price keeps trending past noon, 14:00 NY usually caps the day's extreme ~10:58-11:52, ~14:01-14:10 [new]
- PD arrays call the turn, not the projection: e.g. price closed a buy-side liquidity void / FVG and a bearish OB inside the 2nd unit and stopped there ~19:00-19:25, ~21:58-22:11 [chart] [new]
- Scale out: first partial at unit 1 if it lines up, another when the FVG is filled, leave a small piece for further range ~22:30-22:57 [new]
- Precision is mainly on the entry side (the London LOD on buy days / HOD on sell days); the far projection can be off by a few pips (1-6) ~24:12-24:46 [new]
- Do not apply every day; skipping days is part of the model ~25:39-26:00, ~28:46-29:20

## Trade examples
GBPUSD, H1, week of 27 Mar 2017 (daily premium after a rally, daily bullish OB below ~1.2380):
- Day 1 (sell, CBDR 13 pips bodies): London ran 2 SD up into the body of a bearish OB (low ~1.2593, high ~1.2597 as read aloud) and topped "to the pip". Unit (CBDR + 2 SD) stacked 3x below CBDR low. London-close candle closed at 2 units (~1.2476 low); 3rd unit projected 1.2441, actual low by 14:00 NY 1.2440 ~8:11-15:19 [chart]
- Day 2 (58-pip CBDR): no projection; price dropped into the daily bullish OB, New York session reversal, weekly low ~11:52-12:26, ~23:28-23:45 [chart]
- Day 3 (buy, CBDR 19 bodies): London LOD swept bodies of a rejection block/bullish OB, 2 pips short of SD1. Unit (CBDR + 1 SD) stacked 2x above CBDR high; high stopped at the 2nd unit around the 9-10 NY hour; target also matched filling an FVG/liquidity void of ~23 pips (1.2503-1.2526) ~16:18-20:03 [chart]
- Day 4 (buy, CBDR 16): LOD at 2 SD down, which matched three consecutive down candles (open = low 1.2436). Unit stacked 2x up; price closed into a bearish OB / FVG inside the 2nd unit by noon close and stopped ~20:03-23:00 [chart]

## Definitions
- Protractionary state / Judas swing: the counter-direction move away from the CBDR in London that makes the HOD/LOD ~1:01-1:31 [new]
- Buy-side liquidity void / "buy-side delivery vacancy": a run of candles with only sell-side delivery, to be refilled later (an FVG) ~18:20-19:15
- Sunday+Monday daily candles blended into one for the weekly range on FX (Sunday candle merged) ~7:08-7:25

## Seen only on the charts
- Pink boxes = the projection units; each box spans exactly CBDR + extension SDs (about 90 px on day 1, 85 px on day 3), stacked from the opposite CBDR edge ~13:20, ~17:40, ~21:00 [chart]
- Red squares mark the expected time windows (around the London-close/noon hours) where the projected extremes should print ~11:20 [chart]
- Vertical lines are midnight NY and 14:00 NY each day ~10:20 [chart]

## Open questions
- Is the unit measured to the London extreme wick or body? He projects with bodies first; day 1 counted the high hitting SD2 exactly.
- How many units to expect is decided on the fly (stop when time window closes or PD array hit) - no fixed count; a bot needs a rule, e.g. nearest unit inside 10:00-12:00 or by 14:00 NY.
- Index-futures mapping: CBDR window and pip thresholds are FX; would need an equivalent (e.g. ES range in handles) and re-validation.
