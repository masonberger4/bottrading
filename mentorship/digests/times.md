# Digest: TIMES (time-of-day, sessions, macros, weekly/day templates)

Sources: all 218 notes in `mentorship/notes/` (001-105, cc01-cc12), `mentorship_rules.md`, `strategy.py`, `levels.py`.
All times are New York local time, daylight saving included. Tags: [2023] / [CC] / [both]; [chart] = seen only on charts;
[fx-only] / [bonds-only] = does not transfer to ES/NQ.

## 1. Rules

### A. Clock conventions
- Set charts to New York time (UTC-5 in winter, UTC-4 in summer). Ignore the platform's GMT daily dividers. (mentorship_rules Ep01 ~25:15; 023 ~16:40; 082 chart; 105 chart; cc08_002 ~0:31-1:54) [both]
- Barchart charts in the 2017 index/bond lessons are on Central time: NY = CT + 1h. The 08:30-09:30 CT shading is the 09:30-10:30 NY opening range. (cc10_009 ~5:11; cc10_010; cc10_011 chart; cc10_012 chart; cc10_014 chart) [CC][chart]
- Some 2016 charts are on MT4 server time (GMT or GMT+2), not NY: 00:00 NY shows as 04:00 and 07:00 NY as 11:00. Example clock times from cc01_004, cc02_002/003, cc04_008/010/011 and cc09_003 are therefore not NY times. (cc01_008 chart; cc04_010) [CC][fx-only]
- Use time-based charts only, no range/renko/Heikin Ashi. (mentorship_rules Ep03 ~44:23) [2023]

### B. Daily opening prices and the "true day"
- **Midnight NY open** (open of the 00:00 15m/1h candle) is the true daily open, not the exchange daily open. Extend its line to about 11:00. (006 ~5:51, ~22:49; 069 ~4:37; 060 ~15:20; cc08_002 ~5:15) [both]
- Bullish day: buy at or below the midnight open. Bearish day: sell at or above it. Best shorts are above it and best longs below it in both the AM and the PM. (006 ~23:28; 010 ~38:31; 043 ~4:11, ~18:49; 060 ~17:30; 069 ~8:38; cc03_003 ~31:25; cc03_005 ~19:41; cc09_001 ~0:31; cc09_008 ~33:25) [both]
- Three daily opens: midnight (preferred), 08:30 and 09:30. The PM uses 13:30 the same way: a rally above the 13:30 open into a premium array is the PM Judas, so sell it. (010 ~38:31, ~56:30; mentorship_rules Ep08) [2023]
- 08:30 is the "trigger time". Ideal bullish day: after 08:30 and the 09:30 open, price trades below the midnight open into sell-side, where longs are built. (013 ~4:52-9:26) [2023]
- After a release, bodies in the retracement stop at the 08:30 opening price (wicks may pass it). Day-trade stop goes below the 08:30 open / the CE of the 08:30 1m wick. (064 ~0:55:13, ~1:38:44) [2023]
- 0 GMT open (19:00 ET winter / 20:00 ET summer) is a second reset in the FX material. ICT prefers midnight NY to avoid overtrading. (cc08_008 ~4:02; cc09_001 ~2:24; cc09_008 ~33:25) [CC][fx-only]
- True-day definitions:
  - IPDA true day = 00:00-15:00 (cc08_002 ~5:15). Daily OHLC is framed from the midnight open to the 15:00 close (cc08_002 ~10:22).
  - Bulk of the volume falls 03:00-10:00 (cc12_004 ~7:19).
  - Index true day for day trading = 09:30-16:00; ignore the 24h session (cc10_010 ~1:04, ~8:14).
  - Bond true day = 08:00-15:00 (cc10_006 ~3:22) [bonds-only].
  - [CC]; see Conflict 7.
- Weekly opens: the Sunday 18:00 open and the Monday 00:00 NY open. Bullish week: want price below one or both, into a discount. Bearish: above. (cc12_003 ~19:03-21:26; cc08_001 ~22:58; 048 ~1:00:10; 051 ~3:01) [both]

### C. Kill zones (sessions)
- **Asian range** 20:00-00:00. (cc08_002 ~2:31; cc08_005 ~1:53; cc09_003 ~0:06:30) [CC][fx-only for trading]
  - Asia moves too little to trade indices; the trading day starts at midnight NY. (095 ~20:23)
  - Asian scalps (20:00-00:00) are only for JPY/AUD/NZD. (cc07_001 ~30:15; cc09_003)
- **London open**: 02:00-05:00 (mentorship_rules Ep06; 008 ~1:34; 065A ~1:51:40). He personally uses 01:00-05:00 to absorb DST shifts (cc08_001 ~11:51; cc08_002 ~3:07; 065A). HOD/LOD usually forms 02:00-04:00 (cc08_001; cc08_005 ~3:28). Frankfurt opens ~01:00 (cc08_007 ~21:19). [both][fx-leaning]
- **London lunch** 05:00-07:00: retrace or quiet. Take partials on London trades at or before 05:00. (cc08_001 ~17:10; cc08_002 ~7:48; cc09_007 ~5:13; 065A) [CC][fx-only]
- **NY open kill zone**: 07:00-09:00 for FX (008 ~1:34; 073 table) or 07:00-10:00 with 07:00-09:00 as the sweet spot (cc08_002 ~4:01; 065A ~1:51:40). ICT's own futures kill zone (bonds/ES/currency futures) is 08:20-11:00 (cc10_007 ~4:35). 08:20 = CME open, where NY Judas lows/highs form (cc08_001 ~42:38; cc08_002 ~7:22; cc09_006 ~19:07). [both]
- **London close** 10:00-12:00 (mentorship_rules Ep06; cc08_002 ~4:32; 065A; 084). [both]
  - Also given as 10:00-11:00 (cc01_002 ~16:36; cc09_005 ~12:25).
  - The London-close counter-trend scalp window is 10:30-13:00 (cc09_006 ~23:06; cc09_007 ~9:25).
  - FX trades should be mostly closed 10:00-12:00 (065A ~2:56:30).
- **NY AM session (indices)** — four definitions; see Conflict 1:
  - 08:30-11:00 (mentorship_rules Ep01; 044 ~0:55:47, can stretch to 12:00);
  - 09:30-12:00 (cc10_011 ~0:52; 013 ~12:39 chart; 067 ~0:12:40);
  - 08:20-11:00 (cc10_007);
  - 08:30-12:00 (073 table). [both]
- **NY PM session** — four definitions; see Conflict 2:
  - 13:30-16:00 (031 ~1:04:22; 033 ~0:13:27; 037 ~0:06:03; 067 ~0:42:30);
  - 14:00-16:00 (mentorship_rules Ep01; 056 ~0:14:57; 047 "sweet spot");
  - 13:00-16:00 (cc10_012 ~0:34);
  - 12:00-15:00 for bonds (cc10_007) [bonds-only]. [both]
- Time of day can make a trade valid when the HTF gives nothing, but a setup also needs a "valid time of day" on top of displacement, FVG and retrace. (cc02_006 ~46:47; 063 ~12:22) [both]
- A breaker shape outside the right time is "time distortion", not a breaker. Chop between session windows (e.g. 12:00-14:00) is not a signal. (070 ~6:24; 075 ~1:40:00; 048 ~1:04:26) [2023]
- Time-of-day tools are for daily-and-below only, not monthly/weekly. (cc12_002 ~46:41) [CC]

### D. Opening range (OR) and opening range gap (ORG)
- **OR = 09:30-10:00** ("always"). Do not trade it: it is erratic and the first move is often a Judas. Bias is set from how price delivers in it; take an earlier setup only if obvious. (029 ~11:44; 031 ~0:04:52; 036 ~0:27:30; 042 ~4:29, ~24:45; 044 ~0:04:54; 065B ~4:53:40; 067 ~0:26:00; 073 ~25:00, usable after ~20 min; 090 ~49:00; 092 ~1:45:24 "amateur hour") [2023]
- **CC: OR = 09:30-10:30 (60 min)** for ES/NQ/YM. 09:30-10:00 is only its highest-volume half. (cc10_010 ~3:07-3:23, ~11:09) [CC][chart: full hour shaded]
  - The OR tends to make the HOD or LOD.
  - Wide OR: the opposite end gets run later.
  - Turtle soup below the OR low late in the morning, then run to the OR high.
  - In all examples the HOD/LOD formed inside the OR or within ~30 min after it. (cc10_010 ~3:18, ~6:08-7:05, chart)
- Bonds: OR = 08:00-09:00; it builds the liquidity the 09:30 stock open raids. (cc10_006 ~3:46, ~4:02) [bonds-only; the 09:30 raid idea transfers]
- Exceptions to waiting out the OR:
  - Entries at 09:37-09:46 when price is already deep in discount (034; 041; 053 ~10:03).
  - On a 2-release day, skip entries at or before 09:30 (100 ~1:26:48).
  - [2023]
- **ORG** = prior RTH close to today's 09:30 open, marked on an RTH chart.
  - Levels: high, 75%, CE, 25%, low.
  - Price usually trades back into it; a quarter or half fill that holds shows strength.
  - (033 ~11:36; 036 ~0:28:30, ~0:53:00; 041 ~0:15; 042 ~11:20; 043 ~11:47; 044 ~0:07:12; 055 ~16:48; 058 ~53:24; 059 ~13:46; 092 ~1:55:54) [2023]
  - Close time: 16:15 settlement (16:14 1m candle) in 030, 043, 044, 055, 060, 069, 092; 16:00 in 045, 059, 067. See Conflict 9.
- 09:30 opens below the prior close and makes no attempt back to it within 30 min = very bearish (mirror for a gap up). (030 ~1:27:01) [2023]
- Large ORG or a very large prior-day range: the first 30-45 min chop; a run often starts near 11:00; the PM (13:30-16:00) is better. Sacrifice the AM. (033 ~13:27) [2023]
- Reprice macro: after the 09:30 Judas away from the ORG, expect price back into the ORG. (069 ~14:50) [2023]
- Gap timing: a gap at or near 08:30 or the early NY open tends to fill the same day. A gap at 10:00-11:00 or in the PM tends to stay partly open and fill later. (cc04_009 ~8:25) [CC]
- Index SMT scouting window for the AM is 05:00-09:30 (cc10_011 ~8:01-13:04) or "London into 09:30" (cc10_014 ~1:15). 05:00 is London's lunch. [CC]

### E. Silver Bullet (SB)
- **Windows**:
  - AM 10:00-11:00 in every SB video (044 ~0:50:05; 045; 046; 047 ~08:00; 048 ~57:36; 049; 054; 055; 057; 058; 060; 063; 065A; 068; 072; 090 ~2:00:22; 092; 093; 099).
  - PM 14:00-15:00 (054 ~12:41; 058 ~55:21; 060 ~56:50; 065A; 066 ~0:42:23; 068; 072; 080; 081; 092; 099).
  - London 03:00-04:00 (054 ~08:51; 060; 092 ~20:04; 099).
  - 092 and 099 also list 15:00-16:00.
  - 099 adds an optional 07:00-08:30.
  - FX-only extras: 03:00-05:00 and 07:00-09:00 (065A ~55:55).
  - [2023]
- Setup: in the window, wait for displacement in the bias direction, then an FVG. Enter on the retrace into it; target the opposing untapped pool. (044 ~0:50:05, ~1:06:34; 048) [2023]
  - Minimum: >5 ES handles of room; the goal is 5 handles, not the pool (044 ~0:57:16; 047; 072 "4-5").
  - New traders need ~10 handles of room to aim for 5 (046 ~0:32:40).
- **Entry must be inside the window**; 09:57 or 11:01 is outside the rules (058 ~44:37). The target can be hit after the window (047; 054 ~11:27). 068 lets a fill a few minutes after 11:00 run. [2023]
- FVG timing is inconsistent (Conflict 3):
  - It may form before the window and be traded into during it (058; 059 ~8:56; 060 ~56:50; 065B ~4:48:40; 047 example formed 09:40-09:55; 054 charts start at the 09:55/13:55 bar).
  - Or it must form in the window (047 words; 054 ~9:31; 066 ~0:42:23 PM).
  - 048: the first FVG in the hour in the bias direction.
  - 057: if price leaves the first FVG, move the limit to a newer FVG in the same window.
- The SB fires "every day"; if London has none, wait for AM, then PM. If none in your market, don't trade elsewhere. (046 ~0:55:21; 054 ~18:18; 090; 044) [2023]
- An immediate rebalance seen during 10:00-11:00 means expect more than the normal 5-handle target. (048 ~39:02) [2023]
- Supercharge: align with the weekly profile (Tue/Wed low of week when bullish) and seasonal; take most off at target and keep 1 runner. (048 ~2:02:12) [2023]
- SB stop: below the candle whose low forms the FVG's low end, also below the OB mean threshold. (090 ~2:14:00; 086 ~11:35: below the entry candle) [2023]

### F. Macros (20-minute algorithmic windows; timing, never direction — 073 ~14:54)
- **09:50-10:10**: run to liquidity or an inefficiency (mentorship_rules Ep07; 009 ~18:24; 015 ~27:13; 029; 036 ~0:23:30; 043 ~9:00; 073 ~19:41). [2023]
  - Reading: the run only needs to start in the window (044 ~0:55:47).
  - It may mark the reversal, not just continuation (073).
  - 031's "10 o'clock macro" sweep came at 10:10-10:12, just outside.
- **10:50-11:10**: run on liquidity not yet taken. It is the end of the first 90 min and the London-close peak, the last hour before lunch. (022 ~3:06:14; 025 ~53:12; 044; 073 ~27:57) [2023]
  - Called both the "NY lunch macro" (022) and its own macro (073).
- **11:50-12:10 lunch macro**: a run starts toward the liquidity protecting the AM move (against the AM's profitable side). It can set the day's key point. (046 ~2:03:21, ~2:27:20 [chart: verticals]; 070 ~29:40; 075 ~1:10:00) [2023]
- **13:30**: starts the PM session and a macro that sets up the 14:00-15:00 SB; trap above lunch REH at 13:30-13:35. (067 ~0:42:30; 068 ~0:12:42) [2023]
- **"2:00 macro"**: PM reversal setup ~13:39-14:00, only after lunch (015 ~31:57). [2023]
- **14:50-15:10**: a swing starts here; from premium it seeks discount (043 ~15:37; 075 ~1:45:00 [chart label "2:50 To 3:10 Macro"]). [2023]
- **15:15-15:45 last-hour / market-on-close (MOC) macro** (001 ~1:00:01 [chart]; 014 ~5:19; 030 ~20:06; 032 ~47:41; 047 ~11:15; 056 ~0:19:08). [2023]
  - It runs to untouched liquidity. With no clear setup, wait to 15:40-15:45 and expect a 5-8 (up to 10) handle run.
  - If the HTF target is already hit, no run; 15:45-16:00 gives only a 5-10 handle "sputter".
  - 15:45-15:50 can extend: keep a runner (027 ~40:10).
  - Pool taken before 15:50: expect a flurry, then a pullback; an up day rarely closes on its high (027 ~50:40).
  - 069 ~19:52: the 15:45 MOC run delivers the HTF target.
- 15:00-16:00 holds "three macros": usually two occur and at least one always (022 ~3:16:42). [2023]
- If the macro produces no move toward the draw, close the charts for that session. (073 ~30:51) [2023]
- A macro fails when the day's liquidity run is already done. (030 ~18:26) [2023]

### G. Lunch
- Lunch is 12:00-13:00 per 015 ~29:06, 025, 056 ~0:13:09, 012 chart (ends ~12:58) and cc10_012 ~2:42 (nominal). Other definitions — see Conflict 4:
  - 12:00-13:30 (064 ~1:45:41; 067; 068);
  - 11:00-13:00 (cc10_007 ~7:17; cc09_006 ~22:14 S&P aside);
  - stretches from 11:00 to 14:00 depending on morning speed (cc10_012).
  - [both]
- Lunch behaviour:
  - Usually consolidation or a retrace; take the last AM contract off before noon (003 ~1:12:15; 004).
  - Runs the buy stops above the AM's most recent high after a morning drop (025 ~1:00:20), or runs the stops below the low formed before 11:00/noon, which hits trailed AM stops (064 ~1:45:41).
  - Into 13:30 it runs the stops of traders who were right in the AM (046 ~2:03:21).
  - With an HTF draw, lunch runs the opposite liquidity, then a 13:30 trap (068).
  - [2023]
- If the move to the daily objective completes before lunch, skip the rest of the day. If the AM fails to reach the draw by lunch, it becomes the PM objective. (015 ~16:22; 031 ~1:04:22; cc10_007 ~9:05 [bonds]) [both]
- PM reversal targets lunch-hour lows or highs. (015 ~29:22; 067 ~0:46:00; cc10_013) [both]

### H. PM session, last hour, end of day
- The PM move usually starts ~14:00 (as early as 13:00) and from 13:20-13:30, with 14:00 more favourable. (cc10_012 ~1:59; 019 ~20:40) [both]
  - A short-term high or low almost always forms right after lunch (cc10_014 ~6:33).
  - PM index SMT window: 12:00-15:00 (cc10_012 ~7:25).
  - PM trader starts ~14:45 (026 ~1:26:37).
  - Divided day: if the AM is bad, return at 13:45; if nothing by 14:30, skip the PM (044 ~1:55:03).
- Last hour = 15:00-16:00, setup sweet spot 15:15-15:45. If there is no setup by 10 min before the close, no trade. A last-hour run to an old high, low or imbalance happens nearly every day. (001 ~50:00, ~1:00:01; 013 ~26:20; 024 ~20:55; 071 ~23:22) [2023]
- 010 uses 15:00-16:15 for last-hour setups at old daily highs/lows. [2023]
- If the target is hit by 15:00, be done: the last hour tends to retrace and leave a top wick. (006 ~41:45) [2023]
- Close before 16:00; don't hold past the close. If the day's final level is reached, be flat. No holding overnight or across the 17:00-18:00 settlement; no weekend holds. (026 ~1:24:30; 027 ~58:22; 065A ~1:40:30; 101 ~4:27; 103 ~9:31) [2023]
  - Yet 001 exited at 16:01 and 012's run printed just after 16:00.
- Don't fade an afternoon reversal or add to an all-day short in the last ~15 min. (026 ~1:59:50) [2023]
- PM hold (CC): hold PM trend trades to at least the 15:00 bond close, ideally 16:00; the range expands into the close (cc10_014 ~3:01). On consolidation profiles, exit by ~14:00 (cc10_014 ~13:17). [CC]
- 15:00 bond close is when the PM extreme usually forms (cc10_012 ~12:08). In FX the daily range is set by 15:00 and the 14:00-15:00 FOMC reaction is mostly done by then (cc08_001 ~15:32; cc08_002 ~9:54). [CC]
- Time distortion: sub-5m consolidation before news or after 16:00 tells nothing about direction (100 ~42:05). [2023]

### I. When the day's high/low forms
- Index (CC): the true-day high or low tends to form 09:30-10:30 (cc10_011 ~0:52). The opposite extreme forms 15:00-16:00 (cc10_012 ~1:08). If the AM/OR made the LOD, expect the HOD 15:00-16:00, and vice versa (cc10_012 ~11:27). [CC]
  - Charts show AM extremes around 10:30 NY (cc10_011, cc10_012 "10:30 am NY" arrow) and a last-hour HOD at ~15:15-15:30.
- Index (2023 examples):
  - Lows at 09:31-09:40 after the 09:30 sweep (009; 014; 015; 022; 029; 034; 080).
  - 10:00-10:20 extremes (003; 019; 093 ~10:20 low; 094).
  - Pre-open extremes at 08:20-09:00 (006 LOD 08:20-08:25; 087 HOD 08:45-09:00).
  - Last-minute highs (013 just before 16:00; 014 at 15:54; 069 LOD ~15:57).
  - Bullish-day template ends with the HOD in the last hour (076 ~26:32).
  - [2023][chart]
- FX/IPDA (CC):
  - Bullish day: LOD in London 02:00-04:00, NY continues, HOD in London close 10:00-12:00 (often at noon) (008 ~5:29; cc01_002 ~13:51; cc08_005 ~7:44; cc09_006 ~7:51).
  - Bearish mirror: ~70% of bearish days make the HOD 02:00-05:00 (065A ~1:37:00).
  - Intraday profile: bearish = HOD in London, bullish = LOD in London (cc12_004 ~15:43).
  - [CC][fx-only for the 02:00-05:00 timing]
- Bonds: the 08:00-09:00 OR or 08:00-08:20 makes the low on trending days (cc10_006; cc10_007 ~5:05). [bonds-only]
- NY reverses London only if NY opens into an unmet HTF array; otherwise NY continues London. (cc09_005 ~9:47-11:05; cc12_004) [CC]

### J. Intraday day templates
- **Power of three** (daily): open, Judas move against the bias, expansion, close near the opposite extreme. (mentorship_rules Ep04; cc08_008 ~1:34; cc09_006 ~7:51) [both]
- **London normal protraction**: the Judas starts right after 00:00 and runs into 02:00; by 01:00-01:30 price should exceed the Asian/CBDR range. **Delayed protraction**: no midnight Judas; the counter-move starts at or just after 02:00 (02:00-03:00) into an intraday PD array. Watch 00:00 to 02:30-03:00. (cc08_005 ~2:16-21:29) [CC][fx-only]
- **Market protraction** (time-based Judas) at 0 GMT, 00:00 NY and 07:00 NY: the first move after each mark against the swing direction is fake. (cc01_008 ~3:13-11:59) [CC]
- **Six index day profiles** (projected range; AM green / lunch / PM blue). (cc10_013 ~1:21-15:43; setups in cc10_014) [CC]
  1. Two-session up close: AM low just after the first hour; lunch shallow; PM runs the lunch low or dips into a discount array; HOD in the last hour. The PM leg ≈ the AM leg.
  2. Two-session down close: the mirror.
  3. AM rally, PM reversal: price is just under a 4h/daily premium array. The PM runs the lunch high (failure swing) or the intraday high, then reverses into the close.
  4. AM decline, PM reversal: the mirror.
  5. Consolidation, AM rally / PM decline: no news after 10:00. The PM runs the lunch high only if the AM high hit an HTF array; otherwise it runs the intraday high. It closes mid-range.
  6. Consolidation, AM decline / PM rally: the mirror.
  - NFP days are "seek and destroy" exceptions.
- **Setups by profile** (cc10_014):
  - AM: SMT on the 09:30-area swing; hold to at least 10:30, ideally 11:00.
  - PM: SMT on the lunch low/high plus the swing just after 13:00; hold to 15:00-16:00 on trend profiles, ~14:00 on consolidation profiles.
  - [CC]
- **Bond split session** (cc10_007): the AM makes the main swing. The PM continues, reverses or consolidates in less time. If the AM used most of the ADR, go flat before lunch and skip the PM. [CC][bonds; idea transferable]
- **Seek and Destroy** profile: morning consolidation running both sides, then a big reversing run; don't hold long. (024 ~13:57; 044 ~1:36:11) [2023]
- **NFP profile**: the side taken first right after 08:30 is usually false, then the opposite side, then the real move. (073 ~10:42; 078 ~1:25:47; 105 ~2:02) [2023]
- **Intraweek reversal**: Mon/Tue range far above the 5-day ADR into an HTF array means a reversal around the Tue-Wed changeover. (cc07_007 ~20:45) [CC]

### K. Day of week and weekly profiles
- Weekly range: the bulk forms Tue-Thu (cc12_003 ~13:57). 30-50% of the weekly range is done by Wednesday's London close (cc07_006 ~23:35). The weekly high/low forms Mon-Wed ~70% of the time (cc07_008 ~1:35). [CC]
- Best days: Tue and Wed ideal; Thursday ideal but can reverse, with the weekly range often capped in Thursday's NY session. Monday is typically small; Friday small unless the weekly objective is unmet. Sunday: opt out. (cc08_001 ~18:52-22:58; cc08_007 ~7:17; cc09_007 ~22:37; cc08_008 ~11:07) [CC]
- Bias by weekday: HTF bearish means shorts Mon/Tue/Wed, bullish means longs Mon-Wed. If the Mon-Wed move fails, switch to Thu/Fri templates. (cc12_004 ~6:21; cc09_008 ~41:53) [CC]
- Tuesday's London open forms the low of the week in ~77% of bullish weeks (~70% for highs in bearish weeks) (cc08_001 ~20:43) [CC][fx]. Bearish weeks: the weekly high on Tuesday ~60-70% of the time (070 ~4:23) [2023].
- Weekly templates:
  - Bullish: low Mon/Tue; rally late Tue, Wed and the first half of Thu to the weekly high; Friday retraces.
  - Bearish: Tuesday high, Thursday NY open makes the low.
  - ICT lets Monday go: entry Tue off Monday's low, or Wed off Tuesday's low.
  - Weekly read is ~60% accurate after Monday, ~70% after Tuesday.
  - (cc12_003 ~14:03-18:26) [CC]
- Twelve weekly profiles (cc07_002; cc07_003) [CC]:
  - Classic Tuesday low/high of week.
  - Wednesday low/high of week.
  - Consolidation Thursday reversal (on a 14:00 FOMC or 08:30 release).
  - Consolidation midweek rally/decline.
  - Seek & Destroy Friday (rate/NFP waits, July-August; avoid).
  - Wednesday weekly reversal.
  - Cue: Monday hovers near an HTF array without reaching it, so Tuesday drives into it.
- Break of the Mon-Wed high (bullish) or low (bearish) on Thu/Fri means aggressive expansion toward the target. (cc07_001 ~42:44) [CC]
- Sunday-open filter: in a bearish week, after an early Judas above the open, sell every day while price is below the week's open, until an opposing daily PD array is hit. Thursday crossing back through the open against the bias = likely weekly reversal. (cc08_001 ~22:58-26:04) [CC]
- Thursday often makes the opposite end of the weekly range or the low of week. (044 ~0:16:25; 060 ~1:11:50; 099 ~1:02:09; 100 ~8:24; cc09_001 ~6:33) [both]
- **TGIF**: Friday retraces 20-30% of the weekly range once the weekly high/low is confirmed.
  - Friday only (066 ~0:00:47) vs Thursday into Friday (084).
  - Timing: high of week in by ~13:30, retrace more likely in the PM (066 ~0:15:10), vs often London close 10:00-12:00, else the PM (084 ~15:45).
  - Uses fib 0.20/0.30. (074; 085; 089; 098 ~27:45) [2023]
- Monday:
  - New students don't trade Mondays (065B ~4:12:20).
  - Let Monday shape the week and start Tuesday (077 ~7:30; 068).
  - Outside NFP weeks Monday may be skipped (accumulation) or traded PM only (101 ~30:53).
  - Monday is always a trading day in NFP weeks and in weeks with FOMC later (100 ~33:00; 101 ~30:41; 105 ~44:25).
  - [2023]
- Sunday open: don't trade it; script gap-up/gap-down scenarios; wait for Monday 09:30 (011 ~4:20; 028 ~1:16:09; 084 ~3:21; 102; 103). [2023]
- Friday: take most at the first buy-side because the HTF target may not come (070 ~1:06:37). Friday after a trending week: profit taking and chop (cc04_011 ~17:59). Don't buy Friday after a strong Thursday (cc09_008 ~55:24). [both]
- After a Monday holiday, Tuesday acts like Monday and Wednesday is the likely reversal day (cc09_008 ~57:14). Holiday weeks deliver cleaner Thu/Fri (072 ~3:36). [both]
- Once the weekly objective is met, stop for the week (038 ~6:33; 101 ~34:21; cc10_019 ~15:47). [both]
- Monthly/quarterly time (bias filters only; detail belongs to a seasonals digest):
  - Quarterly shift every 3-4 months (cc05_001; cc12_001).
  - IPDA 20/40/60 trading-day ranges (cc05_003; cc07_004; cc09_008).
  - S&P month table: Jan bearish, Feb bullish, Mar consolidation, Apr bullish, May bearish, Jun consolidation, Jul bullish, Aug consolidation, Sep split, Oct-Dec bullish. Low-probability months Mar/Jun/Aug (cc10_015).
  - August is choppy; stand aside until September (079 ~8:54; 084; 087).
  - ES weak late Apr into May; low 3rd week May-3rd week Jun (074 ~16:54).
  - [both]

### L. News-time handling
- NFP week (mentorship_rules Ep03; 038 ~8:05; 101 ~25:12) [2023]:
  - Trade Mon, Tue and Wed until 11:00 (end of the NY AM).
  - No Wed PM, Thu or NFP Friday; if nothing is done by Wed 11:00, the week is done.
  - A "training wheels" rule (101).
- NFP Friday: no trade, especially the first hour after 08:30 (mentorship_rules Ep04; 105 ~11:50; cc08_001 ~6:37; cc08_006 ~4:45) [both]. Experienced traders wait out the first volatility (061 ~2:49:35).
- FOMC (14:00):
  - Don't trade the release; the PM is out (mentorship_rules Ep03; cc10_008 ~11:18; cc10_009 ~3:48, where the AM is allowed if the trend recipe holds).
  - Two-stage version: the 14:00 statement is the fake move, the 14:30 press conference the real one. No trading 14:00-14:45; after 14:45 the normal routine (021 ~2:40-27:51).
  - The real move starts ~14:25-14:30 (065B ~5:30:00).
  - FOMC week before Wed 14:00: fickle, trade light; clean price Thu/Fri (094 ~1:48).
  - Day before FOMC: slow and imprecise (042 ~3:50).
  - Day after FOMC: sit still in the AM (095 ~51:27).
  - After an FOMC whipsaw, skip the next London open (cc08_006 ~3:36).
  - [both]
- CPI (08:30): no position into the release; trade only after it, or skip the day (030 ~7:22; 047; 064 ~0:04:35; 065A ~2:03:30; 092 ~13:54). Day before CPI: don't trade ahead of it (028) or trade small, bread-and-butter only (029 ~5:22). [2023]
- Any high/medium-impact release: wait at least 30 min after it, then trade only with ~10 handles of room (065B ~4:07:00). The first pool run on the release is the losing side (064 ~0:52:12). [2023]
- No 08:30 news: wait for 09:30 (mentorship_rules Ep05; 007; 019 ~7:57). 09:45/10:00 releases: wait for the release, not just 09:30 (002 ~0:25). [2023]
- Two releases in one session (08:30 and 10:00): two-stage delivery with chop between; don't trade ahead of the second (100 ~50:59). [2023]
- Fed chair testimony/speech at 10:00: no AM trade, not even demo; use the chart 15 min after it ends; trade 13:30-16:00 only (037 ~0:03:09; 038 ~39:59; 067 ~0:34:00). Fed-speaker days: the usual rules may not apply (027). [2023]
- Pre-market trading on news days:
  - On an expected range day, trade 07:00-08:30 and let the 08:30 release run into the target, then stop (032 ~5:46).
  - Ma Deuce: don't short the first break; wait until 08:00, then sell the inverted FVG ahead of 08:30 (091 ~19:02).
  - [2023]
- Consolidation-day predictors: no NY reports today and reports later in the week; bank holidays and the day before; a 14:00 FOMC as the only event means AM consolidation (cc10_008 ~1:51-7:47; 053 ~0:38). Day before a long weekend: skip (cc08_006 ~5:06; cc10_019 ~15:02). [both]
- Rollover week is more volatile and choppy (093). After a holiday, or after a large-range day, the AM is choppy: no trade (090 ~8:00). [2023]

### M. Overnight ranges (CBDR, Asian, Flout)
- **CBDR** = 14:00-20:00. Use the body or wick range; it should be <40 pips (ideally 20-30). SD1-SD2 of it projects the London HOD (sell days) or LOD (buy days). (cc08_003 ~4:29-13:31) [CC][fx-only]
  - Projection unit = CBDR + Judas SDs, stacked in the day's direction.
  - The projected extreme comes in the London close window (10:00-12:00); if price keeps trending past noon, 14:00 usually caps it (cc08_004 ~10:58-14:10).
- **Asian range** 20:00-00:00; projections in Asian-range multiples. Bullish: buy below the Asian high, preferably below the Asian low (cc12_004 ~10:22; cc09_002 ~10:48). Avoid London if a sustained trend starts at 20:00 (cc08_006 ~9:45). [CC][fx-only]
- **Flout**: two inconsistent definitions (Conflict 12) [CC][fx-only]
  - 15:00-00:00, projected in half-range steps (cc09_002 ~11:50);
  - CBDR plus Asian combined, from the CBDR open to midnight (cc12_004 ~12:56; cc09_008 ~33:11).
- "Filling the numbers": expect ~4 projected levels per day from the entry; take 75-80% off at four (cc09_002 ~5:40). [CC]
- ORG can be projected in SDs like the CBDR/Flout/Asian range (056 ~0:17:10). [2023]

### N. Gap times (NDOG / NWOG)
- **NDOG** = 17:00 close to 18:00 reopen, Mon-Thu evenings (032 ~3:03; 033; 036; 045; 052 ~0:46-1:50; 060; 092). [2023]
  - Label it by the calendar date (052).
  - Lifetime: rest of the day (032), rest of the week (052), 5 trading days (068), or weeks (050).
  - Asian repricing scalp at 18:00-21:00 toward the NDOG (052 ~8:18).
- **NWOG** = Friday 16:59 1m close (or 17:00; 16:55 5m bar) to Sunday 18:00 open. Read it on 1m/5m, not the daily (039 ~0:57; 050; 020; 025). [2023]
  - Variant: Friday close to Monday 09:30 (039 ~14:41).
  - Keep 4-5 (039), the last 5 weeks (092), or all within 60 days (051).
  - Holiday-shortened week: ignore it and use the nearest normal NWOG within 60 days (046 ~0:16:01; 048).
- ORG/NDOG expire after 5 trading days (068) or 3 days (060); NWOGs last months. [2023]

### O. Time stops and speed
- Once price touches the expected PD array, it should deliver within 2-3 one-minute candles, else be suspicious or cut (022 ~1:43:27; 031 ~0:24:29). [2023]
- A 1m trade should show movement within ~10 min (025 ~17:17). [2023]
- After touching the far edge of a SIBI, price has 2 min to move back in your favour, else take half or all off (092 ~1:11:05). [2023]
- "This candle or the very next" (5m) for the break or delivery (048 ~32:46; 071 ~32:41). After an impulse, expansion should come on the next 1-2 candles (092 ~1:41:14). [2023]
- Lethargic entry or stalled sponsorship: cut half or exit; no bar count given (cc03_003 ~13:18; cc05_005 ~14:40). [CC]
- Close the bulk of intraday positions from 10:00-11:00 (cc12_004 ~8:25). If the ADR is hit before 10:00, take 80% off and keep a runner (cc09_006 ~19:33; cc09_007 ~8:42). If the session objective hits, stop for the day, e.g. at ~10:30 (029 ~1:03:57). [both]

## 2. Conflicts

1. **NY AM session window.**
   - A: 08:30-11:00 (mentorship_rules Ep01; 044, stretchable to 12:00; 065B "trade 08:30-11:00"; 073 08:30-12:00). About 4 sources.
   - B: 09:30-12:00 (cc10_011; 013 chart; 067). 3 sources.
   - C: 08:20-11:00 (cc10_007).
   - His 2023 trades: entries cluster 09:35-11:15, a few pre-open (018, 032, 040, 091, 096) and some 11:30-12:10 (050, 070, 101).
   - Default: 09:30-11:00 entries, keeping the 10:00 start on 10:00-release days. Parameter: AM end 11:00 vs 12:00.
2. **PM session start.**
   - A: 13:30 (031, 033, 037, 047 study, 067, 069; 010 13:30 open). ~7 sources.
   - B: 14:00-16:00 (mentorship_rules Ep01, 047 "sweet spot", 056). 3 sources.
   - C: 13:00 (cc10_012 and cc10_014, post-lunch swing straddling 13:00).
   - Examples: PM entries at 13:30-14:20 (015, 050, 058, 060, 066, 067, 068, 103) and 15:15-15:47 (001, 013, 020, 024, 027, 047).
   - Default: keep 13:30 (the bot already uses it) and tag 14:00-15:00 SB and 15:15-15:45 MOC sub-windows. Test 14:00.
3. **Silver Bullet FVG formation.**
   - A: the FVG may predate the window; only the entry is in 10:00-11:00 (058, 059, 060, 065B; the 047 and 054 charts). ~6.
   - B: the FVG must form inside the window (047 words, 054 words, 066 PM). 3.
   - Examples mostly show FVGs that begin at 09:55-10:05.
   - Default: entry time 10:00-11:00 (strict, per 058), FVG formed at or after 09:50. Parameter: allow any open FVG.
4. **Lunch.**
   - A: 12:00-13:00 (015, 025, 056, 012 chart, cc10_012 nominal).
   - B: 12:00-13:30 (064, 067, 068).
   - C: 11:00-13:00 (cc10_007, cc09_006).
   - The lunch macro 11:50-12:10 sits at the start in every version.
   - Default: no new entries 12:00-13:30, which is what the bot does. Parameter: 11:00 cutoff.
5. **Done by 15:00 vs hold into the close.**
   - A: target hit by 15:00 means be done; the last hour retraces (006). CC FX: the daily range is set by 15:00 (cc08_001).
   - B: hold PM trades to 15:00 and ideally 16:00 (cc10_014); 076 holds for the HOD at ~15:00.
   - C: flat before 16:00 (027) vs exits after 16:00 (001, 012).
   - His examples exit 15:50-16:01 when long into the MOC.
   - Default: flat at 15:55 for SPY, which closes at 16:00. Parameter: exit at 15:00 if T1 is already hit.
6. **Opening range length.**
   - A: 30 min, 09:30-10:00 (12+ 2023 videos).
   - B: 60 min, 09:30-10:30 (cc10_010).
   - These are nested, not opposed.
   - Default: OR30 as the no-trade window and the reference. Also compute OR60 high/low as a liquidity level.
7. **True day / day boundary.**
   - Midnight-15:00 (cc08_002) vs 09:30-16:00 (cc10_010) vs 03:00-10:00 volume (cc12_004) vs 0 GMT (cc01_003, cc08_008) vs midnight-open-based (2023).
   - The 2023 material uses midnight for opens and RTH for gaps.
   - Default: midnight NY for the open and power of three; RTH for prior-day high/low and the ORG.
8. **Kill-zone hours.**
   - London 02:00-05:00 (Ep06, 008) vs 01:00-05:00 (cc08_001/002, 065A personal).
   - NY 07:00-09:00 (Ep06, 073) vs 07:00-10:00 (cc08_002, 065A).
   - London close 10:00-12:00 vs 10:00-11:00 (cc01_002, cc09_005) vs scalp window 10:30-13:00 (cc09_006/007).
   - All FX-oriented. For ES only "London session high/low 02:00-05:00" matters, as a liquidity pool (067).
   - Default: London 02:00-05:00 as the pool window.
9. **ORG prior close.**
   - 16:15 settlement (7 videos) vs 16:00 (3).
   - For SPY the only close is 16:00. Since the bot reads SPX/NDX index data, 16:00 is the natural choice; ES-futures data would use 16:15.
10. **Macro meaning.**
    - Run inside the window (mentorship_rules Ep07, 009) vs the run starts inside the window (044, 046).
    - Example: the 031 sweep came at 10:10-10:12, after the window.
    - Default for tags: price leaves its range within the window. Treat macros as tags/filters, never triggers (073).
11. **News handling.**
    - Strict stand-aside: NFP week Thu/Fri, NFP Friday, FOMC PM, CPI pre-release, Fed speeches at 10:00.
    - His live trades break these: NFP Thursday (041, 050), NFP Friday (071, 088, 089, 105), FOMC-day short at 15:15 (097), FOMC two-stage buy at 14:25 (065B), a 10:00 release short (049), and a day-after-FOMC AM trade (097 vs 095).
    - He frames the strict rules as "new trader / training wheels" (101, 105).
    - Default: keep the strict filters (the bot is a "new trader"). Parameter: FOMC 14:45+ allowed; post-08:30 +30 min on CPI days.
12. **Flout window.**
    - 15:00-00:00 (cc09_002) vs CBDR+Asian 14:00-00:00 (cc12_004, cc09_008).
    - FX-only, so it does not affect the bot.
13. **TGIF timing.** Friday only, PM-leaning (066) vs Thu-Fri, often London close (084). No default; an untested idea.
14. **Weekly high/low day.**
    - Tuesday (cc08_001 77%; cc12_003; 070) vs Mon-Wed generally (cc07_001/006/008) vs Thursday often the opposite extreme (044, 060, 099, 100) vs Thursday HOW in weekly PO3 (072).
    - These are compatible: the first extreme Mon-Wed, the second on Thursday.
    - Test as stats before coding.

## 3. Bot implications

What strategy.py/levels.py do now: AM 09:30-11:00 (10:00 start on 10:00-release days); PM 13:30-15:50; last_hour tag 15:15-15:45; macro tag 09:50-10:10; flatten at 16:00; midnight-open (SPY: 04:00) and 13:30-open bias filters; blocks for NFP day, NFP-week Thu/Fri and Wed PM, and FOMC PM; overnight range = midnight/04:00-09:30; prior-day H/L from RTH bars.

Add / change:
1. **OR30 no-entry window.** Do not arm setups whose MSS completes before 10:00, unless the parameter allows. It is 12+ sources and the core of the SB. Test it against the current 09:30 start. Keep the 09:30 sweep as a valid sweep (the sweep can happen in the OR; the entry comes after).
2. **SB windows as the primary entry gates.** AM 10:00-11:00 and PM 14:00-15:00, by entry/arm time. Add a London 03:00-04:00 tag only if overnight data is used (SPX CFD has it, SPY doesn't trade then). Add a Params switch `sb_only`.
3. **More macro tags**: 10:50-11:10, 11:50-12:10, 13:30 (±10), 14:50-15:10, 15:15-15:45 (exists), 15:45-15:50. Tag the trades, then measure. ICT says macros give timing, not direction, so don't gate on them yet.
4. **ORG level.** Prior 16:00 RTH close to the 09:30 open, with CE and quarters, as a target and support/resistance (levels.py `opens` already has 09:30; add the prior close). 069's "reprice back into the ORG after the 09:30 Judas" is a candidate target.
5. **Session liquidity pools** (067): London 02:00-05:00 H/L (needs the overnight CFD bars), lunch 12:00-13:30 H/L, prior-day PM 13:30-16:00 H/L, AM 09:30-12:00 H/L. The PM already uses am_hl; add the lunch H/L as the PM sweep/target per cc10_013 and 015.
6. **Exit-time rules to test**:
   - (a) exit at 15:00 if T1 is already hit (006);
   - (b) AM trades closed by 11:00/12:00 instead of holding to 16:00 (cc10_014, cc12_004, 015);
   - (c) flat at 15:55.
   - Currently AM positions can run into the PM, which no source supports.
7. **Time stop.** If the price is not ≥ X in favour within N one-minute bars (2-3 bars per 022/031; 10 min per 025), exit. This is mechanical, so add it as a parameter.
8. **More news filters**:
   - Fed chair testimony at 10:00 → no AM (needs a calendar of speeches).
   - CPI: no trades before 09:30, already the case; optionally skip the day.
   - Two-release AM days (08:30 + 10:00) → AM starts after 10:30.
   - Day before FOMC → tag.
   - Pre-holiday day and the day after a holiday → tag/skip.
   - Rollover week → tag.
9. **Day-of-week tag and filter.** Add a weekday column and test Mon skip / Tue-Wed preference (065B, 077, cc08_001, cc12_003). Add a "weekly objective met → stop" flag only once a weekly draw is coded.
10. **Lunch.** Keep no entries 12:00-13:30 (the bot's AM ends at 11:00 and the PM starts at 13:30, so this already holds).
11. **Midnight open for SPY.** The 04:00 stand-in is a compromise. The SPX CFD has a real midnight; use the index bar for the bias and map it to SPY.

Too discretionary / not codeable now:
- Weekly profile classification (12 templates) needs a "hovering near an HTF array" judgement and an HTF array definition.
- The six day profiles need an HTF premium/discount array map (4h/daily) and "nested" arrays.
- The CBDR/Asian/Flout SD projections are FX-only; their pip thresholds have no ES analogue.
- Seasonals and quarterly shifts are weak bias weights. Needs data: monthly SPX returns are fine (free); COT/OI (needs data: CFTC/exchange OI).
- The TGIF 20-30% retrace could be coded as a Friday PM fade, but it is untested and the timing conflicts.
- Index SMT with YM (needs data: YM/DIA 1m) and DXY confirmation (needs data: DXY 1m).

## 4. Open questions

1. AM end: 11:00 or 12:00? PM start: 13:00, 13:30 or 14:00?
2. SB: must the FVG form inside the window? Is entry at the FVG edge or the CE? Is the stop below the FVG candle or below the dealing range?
3. Does a fill a few minutes after 11:00 count (068 says yes, 058 says no)?
4. Is the 10:00-11:00 window strict on 10:00-release days?
5. Macros: what counts as the macro "producing a move"? Is the 09:50-10:10 run the start or the whole move? Where do the three 15:00-16:00 macros fall exactly (14:50-15:10, 15:15-15:45, 15:45-15:50?)? What are the times of the London and the second lunch macro?
6. ORG: 16:00 or 16:15 close? Expiry 3 days, 5 days or never?
7. OR: 30 vs 60 min as the default reference. Is the OR measured on wicks or bodies?
8. "Large ORG" / "large prior range" (033) and "small range day" (cc10_008/009): no thresholds. Candidate: a fraction of the 5-day ADR.
9. Time stop: is it measured from the fill or from the trigger? 2-3 bars or 10 min?
10. NFP week: is the end at 11:00 Wednesday a strict cutoff for the bot? Does the holiday-week exception (072) override it?
11. Days after FOMC and after holidays: AM only or the whole day?
12. Which Fed speakers or testimonies count as "10:00 manual intervention"?
13. Weekly boundaries for ES/SPY: Sunday 18:00 vs Monday 00:00 vs Monday 09:30. Which defines the "Mon-Wed range" and the weekly open?
14. Day-of-week claims (77% Tuesday low, Mon-Wed 70%, Thursday opposite extreme) are FX or anecdotal; they need stats on SPX 2019-2026 before use.
15. Does "HOD/LOD forms 09:30-10:30 and the opposite extreme 15:00-16:00" hold on SPX data? It is easy to measure and would justify the AM/PM split.
16. CBDR/Asian/Flout: is there any index analogue (e.g. 13:30-16:00 range projections)? ICT never gives one.
17. Should the NDOG/NWOG use ES futures data (true 17:00-18:00 gaps)? SPX index data has no such session break.
