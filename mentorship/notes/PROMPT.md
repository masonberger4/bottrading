# Per-video note prompt (used for each playlist video)

You are taking study notes on one ICT (Inner Circle Trader) mentorship YouTube video
so a trading bot can implement the rules. Inputs, all local:

- Captions: `data/mentorship/captions/{IDX}_{ID}.txt`, one auto-caption cue per line as
  `[hh:mm:ss] text` (no punctuation, recognition errors: "fair value Gap", "bizzy" = BISI,
  "cybie" = SIBI, etc.).
- Frames: `data/mentorship/frames/{IDX}_{ID}/hh-mm-ss.jpg`, a 720p still every 20 s.
  View them with the Read tool (it shows images).

Steps:
1. Read the whole caption file (in chunks if large).
2. Pick the moments that matter for a bot: trade entries/stops/targets/exits, definitions,
   "this low / this candle / right here" references, times of day, levels he marks, rules.
   For each, view the nearest frame(s). Budget about 20-40 frames per hour of video; skip
   frames that are just his face, a title card or a repeated chart. Read prices, times,
   labels and drawn boxes from the chart where legible; say so when it is not legible.
3. Write the notes file `mentorship/notes/{IDX}_{ID}.md` (create it with the Write tool)
   in this format, paraphrasing (no quote longer than 15 words, at most a few quotes):

   # {IDX} {TITLE} ({ID})
   Date discussed / market / timeframes shown / duration.
   ## Summary  (2-4 lines)
   ## Rules  (bot-relevant; each bullet ends with ~hh:mm:ss, and [chart] when it comes
      from or is confirmed by a frame; mark [new] if it is not already in
      mentorship_rules.md, [conflict] if it disagrees with that file)
   ## Trade examples  (instrument, date, times, entry/stop/targets/size/outcome as read
      from the chart, which PD array, which liquidity was swept, timeframe)
   ## Definitions  (any term defined or refined, with time)
   ## Seen only on the charts  (details the words leave out)
   ## Open questions  (ambiguities a coder would hit)

   Keep it under ~900 words. Skip chit-chat, marketing and life advice.
4. Also read `mentorship_rules.md` so you can tag [new] / [conflict] correctly.
{EXTRA}
Do not edit any other file. Finish by replying with: the notes path, the number of frames
you viewed, and the 3-5 most important [new] or [conflict] items.
