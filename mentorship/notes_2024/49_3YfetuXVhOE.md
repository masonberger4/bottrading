# 2024 Mentorship Lecture 49 (3YfetuXVhOE): high vs low resistance market profiles: no-news Monday = trade pre-market 07:00-09:30 only, clustered NWOG/NDOG as the draw, ORG mid-gap still hit in 19 min, candle-1 vs candle-2 stop by condition, reclaimed FVGs/OBs mark high resistance, the low resistance recipe (news + not Monday + clustered gaps + ORG 45/75)
Live Mon Oct 28 2024, afternoon review of the morning (~13:00-15:50 ET, approx.), NQ (Dec), 15m/5m/1m/15s. ~2h48m (influencers, payouts, Monday amateurs, models history; skipped). Captions only.
Source tier: 2024 Mentorship. ICT's pre-market short (posted on X, London lows / NWOGs as draws) and a hindsight walkthrough of Caleb's model on today's open.

## Summary
"Market profile" here means how price will deliver (high vs low resistance), not volume profile. No medium/high-impact news Monday: trade the pre-market session (07:00 to the 09:30 bell), not 09:30 onward; the AM is likely high resistance. Lunch usually consolidates or reverses the morning, then the AM direction resumes after 13:30. Mondays: ICT does trade them, with rules; every NFP-week Monday (cleanest, with Tuesday); done by Wednesday AM; if Monday was profitable he does nothing Tue/Wed. Today: large premium ORG; below the mid-gap sat two clustered NWOGs (this week's and last week's), so the bias was lower from the open; mid-gap hit in 19 minutes, but the run to the NWOG high was slow and back-and-forth (high resistance), first reached 11:43. Caleb's model: displacement off a 1m SIBI, enter at the low of the gap (not CE, not the high), one contract on a high resistance day; stop above candle 1 + 1 tick (near the range low a candle-2 stop would be retraded); target the highest level of the clustered gaps. Reclaimed FVGs/OBs (used twice) are a signature of high resistance; seek & destroy is its aggressive form. Low resistance recipe: medium/high news at 08:30 or in the first hour, not a Monday, clear draws (clustered gaps), ORG over 45 handles (75 preferred).

## Rules
- NO-NEWS MONDAY [new]: with no medium/high-impact news at 08:30 or after 09:30, trade the pre-market session 07:00-09:30 and not the AM session; expect high resistance after 09:30 ~6:00-12:00, ~1:34 (MONDAY, PREMARKET-ENTRY)
- MONDAYS: ICT trades Mondays with rules; Monday is "amateur hour" so he is leery right at the open; NFP-week Monday always (with Tuesday), done by Wednesday AM, Thu/Fri only if extremely obvious; if Monday paid, nothing Tue/Wed ~9:00-12:00 (MONDAY, NFP-THU-FRI)
- LUNCH: consolidation or reversal of the AM move; AM direction resumes after 13:30 ~7:00-8:00 (LUNCH-WINDOW)
- CLUSTERED OPENING GAPS [new]: NWOGs/NDOGs whose ranges overlap are a magnet; the target is the nearest extreme of the cluster (shorts: the highest level of the cluster; longs: the lowest); a mid-gap with a cluster beyond it = expect more than half the ORG (3/4, full) ~1:14, ~1:28-1:30, ~1:52 (GAP-LIFE / ORG-CE-WINDOW)
- ORG MID-GAP [in rulebook]: 70% in the first 30 minutes, hit in 19 minutes today; if it hits later (e.g. 11:00) it's still the same draw ~1:19, ~1:33, ~1:36 (ORG-CE-WINDOW)
- NO 15-MINUTE OPENING RANGE: the algorithm respects the first 30 and first 60 minutes, not 15; the day's high/low can often be framed from them ~1:44-1:46
- CALEB'S ENTRY [beginner]: after displacement off a 1m FVG (SIBI), enter at the gap's low (bearish), not its CE or high, no Mohawks; accept some heat ~1:47
- STOP BY CONDITION [new detail]: bearish FVG stop = candle 2 high + 1 tick (low risk) in low resistance; in high resistance, or when the entry is near the range low and likely to be retraded, use candle 1 high + 1 tick ~1:40-1:42 (STOP-PLACE)
- SIZE IN HIGH RESISTANCE [beginner]: one contract only ~1:40
- RECLAIMED ARRAYS [new]: an FVG or OB used twice (reclaimed) is characteristic of high resistance runs; seek & destroy is the aggressive form ~1:57-2:00 (FVG-VALID)
- HIGH RESISTANCE MANAGEMENT: don't trail the stop ("a death knell"); cover costs (commissions + ~$100) or hold; re-enter if stopped rather than strangling the trade ~1:54, ~2:45 (STOP-MGMT)
- LOW RESISTANCE RECIPE [new]: medium/high news at 08:30 or within the first hour, not a Monday, obvious clustered NWOG/NDOG draws, ORG at least 45 handles (75 preferred) = probabilities "off the charts" for low resistance; news alone does not guarantee it ~2:08, ~2:29 (ORG-SIZE)
- EXIT STRATEGY: have an early exit you hit 90%+ of the time; low-threshold daily goal (10-20 NQ / 5-10 ES handles), one trade on 15m context ~53:00, ~59:00, ~2:30 (MIN-ROOM)
- "If I do this, I know..." mid-trade = no model, go back to demo ~2:19

## Trade examples
- 2024-10-28 pre-market (ICT, posted on X): short toward London relative equal lows and the clustered NWOGs.
- 2024-10-28 AM (hindsight, Caleb's model): large premium ORG; mid-gap in 19 minutes; 1m SIBI short at the gap low, stop candle 1 high + 1 tick; price retraced near the entry, reclaimed FVG, NWOG high first reached 11:43.

## Open questions / conflict checks
- [conflict check] No-news Monday: pre-market only, skip 09:30+ (L37 always trade NFP Monday; L06 skip Mondays): MONDAY.
- [conflict check] Candle-1 vs candle-2 stop by resistance condition (L28, L36): STOP-PLACE.
- [conflict check] Low resistance needs news + ORG 45/75 (L40, L44): ORG-SIZE / resistance card candidate.
- [conflict check] Clustered NWOG/NDOG as the day's draw: GAP-LIFE.
- [new] `no_news_monday_premarket_only`; `clustered_gap_draw`; `stop_candle_by_resistance`; `resistance_condition_filter`; default off.
