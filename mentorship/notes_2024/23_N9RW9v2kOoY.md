# 2024 Mentorship Lecture 23 (N9RW9v2kOoY): "NQ Live Execution Sep 6 2024 100k [OSOK]": one-shot one-kill short held overnight from Thursday's high to the daily FVG CE
Execution video (screen capture of ~18 hours, Thu Sep 5 2024 into Fri Sep 6 2024 Asia session), NQ, 1m. ~9m. Captions only.
Source tier: 2024 Mentorship. Real execution (ICT's own fills shown; caption says "$100,000", one trade).

## Summary
ICT sold short near Thursday's high: a turtle soup above swept highs, fading a "retail bull flag", working a bearish order block. Target: the CE of the Aug 13 2024 daily FVG, with sell-side just below it. He held through the afternoon and overnight (5-6 pm break), adding was allowed in the same day only in the final hour (14:30-15:00, as long as Thursday's high held) or after midnight the next day. Price ran a market maker sell model down to the daily FVG CE in Friday's Asia session, where the limit cover filled (~$100,000). Thursday's first FVG (09:30-10:00) and the Sep 4 first FVG were used as reference levels; small intraday bull flags were all fakes.

## Rules
- OSOK (one shot one kill): one entry at the day's high, held for the daily range target (daily FVG CE) rather than intraday targets ~0:00-1:00, ~7:00
  - Entry: turtle soup above highs into a bearish order block; stop placed where the algorithm "will absolutely say I'm not going to go here" ~0:00, ~2:00, ~3:30
- PYRAMID windows for a swing-in-day short: same-day add only in the final hour (14:30-15:00) if the high is not taken; otherwise add after midnight on the next trading day ~1:00-3:00, ~6:00
  - Any return to an NDOG is an add opportunity while the high holds ~3:00
- Daily range target: the CE of a daily FVG; sell-side below it ~0:45, ~5:00
- Prior first presentation FVGs (Thursday's and Sep 4's) act as references the next day(s) (cf. L21 three-day life) ~3:30, ~5:30
- Small bull flags inside a market maker sell model are retail traps ~6:00-7:00

## Trade examples
- 2024-09-05/06 NQ short (ICT): entry near Thursday's high, adds of 4 and 4 shown, limit cover at the Aug 13 daily FVG CE in Friday's Asia session; ~$100,000 (caption). Exact prices not legible in captions.

## Open questions / conflict checks
- [conflict check] Holding a day trade overnight to a daily FVG CE vs rulebook flat by session end / force-flat 16:00 (engine). Switch `hold_overnight_to_daily_target` default off.
- [new] `pyramid_window_final_hour_or_after_midnight`; default off.
