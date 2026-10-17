# 054 2023 ICT Mentorship - ICT Silver Bullet Time Based Trading Model (tRq1hyGGtl4)
Recorded ~May 2023 (chart clock UTC-4). Market: ES (E-mini S&P, JUN 2023), 5-minute charts, one 15m FVG referenced. Duration ~19 min. Examples: likely Tue 9 May 2023 (London), Thu 11 May (PM; its 15m FVG is labelled "May 10, 2023"), Fri 12 May (AM).

## Summary
Defines the ICT Silver Bullet: three fixed 60-minute NY-time windows (03-04, 10-11, 14-15). Inside the window, take an FVG entry toward the next draw on liquidity. A trade needs a 10-handle best-case "framework" (15 pips FX), but the actual aim is about 5 handles. Entry must happen inside the window; the trade may be held after it. One market is enough; he says one window fires every trading day.

## Rules
- Windows, NY local time with DST observed: London open 03:00-04:00, AM 10:00-11:00, PM 14:00-15:00 ~08:51, ~12:41, ~14:14 [chart] [new]
- Setup: a classic FVG that forms inside the 60-minute window, traded in the direction of the next draw on liquidity ~09:31 [new]
- PM wording: take the first FVG that forms inside the window and that price reprices to (retraces into) during it ~15:26 [new]
- Entry: short/long "inside" the FVG on the retrace. Wicks may poke through, but bodies staying inside the gap confirm it ~10:33, ~14:50 [chart] [new]
- MSS shown in both London and PM examples, before the FVG (London: break below a short-term low; PM: a swing broken upside after tagging a 15m discount FVG) ~10:21, ~14:41 [chart]
- Only the entry has to be in the window. The exit can run past it, e.g. a London trade held into 05:00 or the 07:00-08:00 NY open ~11:27, ~13:45 [new]
- Framework: the setup must offer at least 10 handles (40 ticks) for indices, or 15 pips for FX. Below that, skip it ~00:36, ~01:50 [chart] [new]
- The framework is the best-case price delivery you expect, not the trade's own entry-to-exit distance ~00:56 [chart] [new]
- The actual take is about 5 handles. He does not require 10 to be captured, e.g. cover at the old low ~12:00, ~13:35 [new]
- Equivalences: 10 handles = 20 pips and 5 handles = 10 pips. So the slide's 15-pip FX minimum is looser than its 10-handle index minimum ~00:50 [chart] [new]
- Draw candidates (his list is not exhaustive): previous day high/low; previous session high/low (e.g. the London H/L for the AM session); previous week high/low; a return to the current/old NWOG; expansion away from the NWOG; a classic OTE; 2022-model confluence (FVG/BISI/SIBI above or below price) ~04:02-06:40 [chart] [new]
- If a draw was already raided earlier that morning, use a higher-timeframe pool or inefficiency instead ~06:50 [new]
- The main skill is picking the next draw. The direction comes from that draw, not from a separate "bias" ~07:45, ~09:52
- If London gives no setup, wait for AM, then PM. He says one setup forms every trading day in any one market ~18:18 [new]

## Trade examples
1. London SB, ES 5m, ~9 May 2023. Bearish. A drop from ~4149 broke a short-term low (~4144.5) at about 03:05-03:15, MSS. Bearish FVG (red box) at ~4145.0-4146.0 formed ~03:20 and was extended to 04:00. Bodies stayed inside; at ~04:00 a wick pumped to ~4146.5, just above the box, which he says would not have stopped you. Draw: "Sellside Liquidity" line at ~4137.5, the prior afternoon's ~14:00 low. Entry ~4146, cover at the old low = 5+ handles; he says 10 was reasonable "to it and through it". Price fell to ~4136 by ~04:45 and a ~4135 wick ~06:00. [chart]
2. AM SB, ES 5m, ~12 May 2023. Bearish. Displacement down at ~09:55-10:05 from ~4156. Bearish FVG at ~4145-4148.25 (box starts on the candle at/just before the 10:00 line, extended to 11:00). Price retraced into its lower part ~10:10-10:25. He calls the entry "4146 or thereabouts". Draw: relative equal lows / "Sellside Liquidity" 4121.50 (prior day ~10:30 low). 4146→4136 (10 handles) does not even reach the lows, so the framework is met; 5 handles were available inside the hour. Price reached ~4128 by ~11:30, broke 4121.5 at ~12:45 and made ~4112 by ~13:45. [chart]
3. PM SB, ES 5m, ~11 May 2023. Bullish. The morning tagged the May 10 15m discount FVG (~4119.5-4124.5) and SSL 4121.50, then shifted higher. That rally left a 5m BISI at ~4126.5-4130.5, and bodies respected it. At ~13:50 price dropped into that BISI (wick ~4125). The rally into 14:00 left a small FVG at ~4131.75-4132.5 (green box, extended to 15:00), which was retested ~14:05-14:15. Draws: buy-side liquidity at the ~12:00 relative equal highs (~4144.5-4145) and a premium bearish FVG ~4143-4146.75 from ~09:00. Entry ~4132 to ~4144-4146 = "12 or more" handles. Price reached ~4146.5 by ~14:45-14:50. [chart]
No stop or size is drawn or stated in any example.

## Definitions
- Silver Bullet: a time-based model. The FVG entry forms in a specific 60-minute NY window ~08:21
- Framework: the best-case expected range of the move, not the entry-to-exit distance ~00:56 [chart]
- Handle = point (ES: 1 handle = 4 ticks) ~00:40

## Seen only on the charts
- His FVG boxes are extended right to the window's end line (04:00, 11:00, 15:00). Each window has vertical "New York Local Time" lines.
- In the AM and PM examples the FVG's first candle starts at or just before the window open (09:55/13:55 bars). So the gap may begin forming at the window start, with the retrace/entry inside the window.
- Liquidity lines start at a prior-session swing low/high and are drawn right until price hits them.
- The slide reads "but limited to"; the spoken words are "not limited to".

## Open questions
- Stop placement is never stated or drawn. The only hint: a wick through the FVG top would not stop you "with the rules I teach", so the stop sits beyond the FVG/swing, not at the FVG edge.
- Entry level inside the FVG (near edge vs CE vs far edge) is not specified. The examples' quoted entries (4146 in a 4145-4146 gap; ~4146 in 4145-4148.25; ~4132 in ~4131.75-4132.5) sit near the near edge or lower half.
- Does an FVG whose first candle is 09:55 or 13:55 count? The charts suggest yes.
- How the framework is measured: in example 1 the old low was only ~8.5 handles from entry. He counts a run "through" the low, so the framework reaches beyond the draw level.
- MSS is not stated as required for the AM example.

## Differences vs silver_bullet/strategy.py
- Windows match (03-04, 10-11, 14-15 NY).
- Draws: the code uses session/day/week highs and lows only. The video adds NWOG return/expansion, OTE, and HTF FVG/BISI/SIBI inefficiencies as draws, plus fallback to HTF pools if one was already raided.
- Framework: the code requires the draw >= 10 pts from entry. In the video the framework is the best-case run, which can extend through the level; example 1 (~8.5 pts to the low) would be rejected by the code.
- Target: the code's fixed 5 pts matches the "aim for 5 handles". The video also uses "cover at the old low" (the draw itself), i.e. the code's `draw` exit mode.
- Entry: the code places a limit at the FVG's near edge, valid until the window ends; the video says "inside" the gap, with bodies holding. It also says to take the first FVG formed in the window. The code may take later FVGs; check this.
- The code requires the FVG to form inside the window. The video's AM/PM gaps start on the bar at/just before the open.
- The code requires MSS. The video shows it in two of three examples but does not list it as a rule.
- The stop beyond the displacement-leg extreme is the code's own choice; the video gives none.
- The code goes flat at 15:55. The video lets London trades run into the NY open, which is compatible.
