# Experienced-trader rules (owner decision: the bot follows the EXPERIENCED version)

Wherever ICT gives one rule for new students, beginners or funded-challenge traders and another for
experienced traders or himself, the bot follows the experienced one. Sources: `mentorship/notes`,
`mentorship_rules.md` and the digests, each checked against
`data/mentorship/captions/<file>.txt` near the timestamp. Timestamps are caption times. Quotes are
caption text and stay under 15 words.

"Bot today" is read from `mentorship/strategy.py` (Params, `blocked()`, the `lost_side`
no-reversal filter in `run_day`, the `min_draw_pts` check in `_scan`), `mentorship/htf.py`
(`gaps_for_day`) and `mentorship/backtest.py` (`combine`, the weekly cap).

**[inf]** marks a row where the split, or the experienced value, is my inference and not his words.

## Table

| # | topic | beginner rule (source, time, quote) | experienced rule (source, time, quote) | bot today | change needed |
|---|---|---|---|---|---|
| 1 | NFP Friday | 061 ~2:49:33 "should absolutely not trade on non-farm payroll" (new students). 065 ~4:12:31 "I teach my students don't try to trade non-farm payroll" | 061 ~2:50:02 "everybody knows I can trade on non-farm payroll". Wait out the first volatility. Nobody trades the release hour: 061 ~2:49:33 "nobody should be trading during the hour of non-farm payroll". 065 ~4:12:40 "you can trade after non-farm payroll about 30 minutes after" | `blocked()` returns `nfp_day` for the whole day (with `day_filter=True`). No param | Add `nfp_day: bool = True` (trade it). AM entries already start at 09:30, one hour after the print, so no extra delay is needed. Keep pyramiding off on NFP: add `nfp_no_adds = True` (105 ~9:13, he won't pyramid NFP). This only matters if `adds` is set |
| 2 | NFP week Thu / Fri | 050 ~20:32 "new students should not be Trading on Thursday and Friday". 101 ~28:33 "as a new Trader as a new student" | 101 ~7:58 "my well-versed veteran students we can trade these days". 101 ~9:42 calls the rule "training wheels" to "protect you if you're a new student" | `blocked()` returns `nfp_week_thu_fri` for weekday >= 3. `nfp_thu=False` | `nfp_thu=True`. Also add `nfp_week_block: bool = False` so the Friday block goes away when NFP falls on a Thursday (holiday weeks): today that Friday is blocked by `nfp_week_thu_fri` |
| 3 | NFP week Wed PM | 101 ~25:30 "close up shop if you're brand new" at 11:00 Wed | Same veteran quote (101 ~7:58). He traded NQ Wed ~11:30 in the same video (101 note, open question) | `blocked()` returns `nfp_week_wed_pm`. No param | Add `nfp_wed_pm: bool = True` (or fold it into `nfp_week_block=False`) |
| 4 | FOMC PM timing | 021 ~5:32 "I teach my students don't touch it at all". 021 ~17:22 "why I tell my students not to trade it" | 021 ~5:30 "can you trade it after like 2:45 ... I believe you can". 021 ~6:00 "misleading if I said I didn't ever trade it after 2:45". He still calls it a gamble | `fomc_pm_from=0`, so the FOMC PM is blocked (`fomc_pm`). AM open | `fomc_pm_from=885` (14:45). Test 865 (14:25), from 065B's two-stage notes **[inf]** |
| 5 | CPI | 030 ~7:22 "for those that are new not to trade this day" (at least not before 08:30) | 065 ~4:12:03 "I have to wait for CPI ... if I'm going to trade them". After the print is fine (028; 064). Nobody holds into the release | `skip_cpi=False`. AM entries start 09:30. Already experienced | None |
| 6 | Reversal after a loss | 001 ~47:32 "if you're new ... err on the side of ... staying out". Funded: 001 ~48:03 "never ever ever ever ever reverse" | 001 ~47:32 "with experience sometimes ... it's a good opportunity to reverse" | `run_day` sets `lost_side` on any losing close and skips the opposite side for the rest of the day (the PM). No param | Add `reverse_after_loss: bool = True`, which drops the `lost_side` filter. He gives no condition for "sometimes" **[inf]**: the normal sweep/MSS scan is the only gate. Same-session reversal stays impossible because `done[session]` is set at the fill |
| 7 | Trades per day / week, PM after an AM win | 065 ~4:16:03 "if you make money in the morning don't trade the afternoon as a new student"; "find one good setup per week" | 065 ~4:16:03 "that doesn't mean everybody stops trading" | One AM + one PM. `no_pm_after_am_win=False`, `max_trades_week=0`. Already experienced | None |
| 8 | Trading lunch | 065 ~4:16:03 "as a new Trader you shouldn't try to do that yet" | 065 ~4:16:03 "yes you can trade lunch you've watched me ... trade in that lunch hour". 046 ~2:30:30, lunch macro: "a little bit more nimble could you take that trade yes" | No lunch window: AM 09:30-11:00, PM 13:30-15:50 | Add `lunch: tuple = (710, 810)` (11:50-13:30), one setup with the same rules as AM/PM. The 11:50 start comes from the 046 11:50-12:10 lunch macro and the end from the rules' 12:00-13:30 lunch pool; the bounds are **[inf]** |
| 9 | Room to the draw (10 vs 5 handles) | 046 ~33:02 "it has to offer 10 handles". 046 ~33:33 "because you're new ... better for you just to observe" | 046 ~34:02 "the folks that know what they're doing ... don't need the 10 handle filter". 105 ~9:00 "the five handles minimum I preach and teach" | `min_draw_pts=10.0` (`x_room_lt_min`). `min_rr=1.0` | `min_draw_pts=5.0`. Keep `min_rr=1.0` |
| 10 | 2-3 handle scalps | 050 ~69:30 "high frequency trading is something that a new Trader should not be aspiring" | He doesn't do them himself: 050 ~69:03 "I'm not trying to do two to three handle moves". No experienced permission | Covered by row 9 | None. Keep the floor at 5 |
| 11 | NWOG lookback | 051 ~18:33 "you want to have at least five" ("as a new developing student") | 051 ~18:02 "I look back 60 days"; "that's the maximum I have on my charts" | `htf.gaps_for_day(nwog_keep=5)` keeps the last 5 NWOGs. Hard-coded: not in Params, and backtest.py:134 calls it with the default | Add `Params.nwog_days: int = 60` (trading days). `gaps_for_day` should keep every NWOG formed in the 60 trading days before `day` (about 12) instead of `tail(5)`, with backtest.py passing it through. NDOG (this week only): no split found |
| 12 | Monday | 065 ~4:12:31 "as a new student learning don't trade on Mondays" | 065 ~4:12:31 "once you know how to trade you can trade Mondays all day long" | `skip_monday=False`. Already experienced | None |
| 13 | Directional bias required | 095 ~12:01 "while you're learning it's advantageous ... determining a directional bias" | 095 ~11:46 "I can ... intraday on very very small time frames and not have a bias" | `htf_bias="off"` (no direction filter). `use_bias=True` is only the premium/discount-vs-open check, not direction. Already experienced | None |
| 14 | Turtle soup entry (no MSS) | 066 ~31:02 "a very very difficult thing to do for New Traders"; wait for the 2022 model instead | Implied: 066 ~31:02 "you have to really trust you know what you're doing" **[inf]** | No such entry. Every setup needs sweep -> MSS -> FVG | Add `turtle_soup: bool = True`: a limit at or just beyond the swept pool, stop beyond the run's extreme, same targets and room filter (D10 `early_entry` in mentorship_rules.md). New code |
| 15 | Risk % per trade | cc02_001 ~3:32 "two percent ideally if you're a new trader but no more". 022 ~1:38:50 "it's too high for someone that's new. 2% is too much" | ICT himself, 102 ~1:24:02 "I would likely be at my maximum risk which is 5%" when within 20-30 handles of a monthly, weekly, daily or 4h level. Otherwise "one and a half percent maximum". Each pyramid entry at 5% | `risk_dollars=1000` (1% of $100k), `max_total_risk=2000` (2%) | Keep `risk_dollars=1000` (inside his 1-1.5%). Add `htf_risk_dollars=5000` and `htf_risk_within_pts=30`: 5% when the trade's draw is an HTF (M/W/D/4h) level within 30 ES pts. Raise `max_total_risk` to match. Aggressive: run it as a separate sizing test before adopting it |
| 16 | First partial size | 065 ~2:34:32 "in the beginning when you're first learning take the most off" | 022 ~52:33 "someone that's seasoned ... you can go to full terminus" (the full target) | `partial=0.5`: half, not "the most" | No forced change: 0.5 is not the beginner rule. He gives no experienced number **[inf]**, so test `partial=0.25` and `partial=0` (full terminus) |
| 17 | Pyramiding | No beginner ban found. 022 ~52:00 bans adding past the leg threshold, a general rule | He pyramids himself (001; 102 ~1:25:03 "every new pyramid entry ... was 5% risk"). Not on NFP (105) | `adds=()` (off) | **[inf]** Test `adds=(0.5,)` with the existing add rules. Keep no adds past the leg midpoint (045; 092) |
| 18 | Re-entry after a stop | Re-entry at half risk is taught to everyone (cc02_005). Beginner exit: cc02_005 ~7:32 "this is one of those instances of your new Trader" -> take it off at 2R and go flat | cc02_005 ~11:33 "as you grow into the next stage ... start locking in your stop loss" at 2R. 10:03 "once we get a multiple of R3 ... take your profits" | `reentry_half=False`. No 2R lock or 3R target | `reentry_half=True` (the re-entry is not experienced-only **[inf]**). Add `reentry_lock_r=2.0` (at 2R, stop to the level that keeps the prior loss repaid) and `reentry_target_r=3.0` |
| 19 | One market vs several (SMT / sick sister) | 013 ~3:30 "if you just stick to one market it'll be perfectly fine" | 013 ~4:02 students "moving from one asset class to next ... a little bit more seasoned" | `combine()` keeps one fill per date and session across instruments. `smt_min=0` (tag only) | **[inf]** Add `one_market: bool = False`: allow one trade per instrument per session, total risk capped by `max_total_risk`. No beginner split was found for sick sister or SMT use itself (053: consolidation only). `smt_min` unchanged |
| 20 | Choppy, small-range conditions | 103 ~18:31 "conditions that I try to teach new students to avoid" | 103 ~18:31 "can some of my students ... trade it on the lower time frames yes" | `neutral_skip=False`. Already trades them | None |

## Topics checked with no beginner/experienced split

- **Opening range wait** (09:30-10:00): taught to everyone (065B ~4:53; Ep 05). `or_minutes=30` stays.
- **Stop size**: no split found. ICT's own 17.5-pt stop (003) is a single case. `min_risk_pts=1`, `max_risk_pts=15` stay **[inf]**.
- **Holding AM trades through lunch**: no split. `am_exit=720` stays.
- **August / funded challenges** (079 ~9:03; 084 ~10:31; 087): he applies it to himself: 079 ~9:03 "I've done a lot of damage to myself with real money". The funded part is about challenges. Not a beginner rule, so no change; the bot has no August filter.
- **Low-probability days** (010 ~1:17): beginners keep the charts on to study and seasoned students turn them off. Neither trades. No change.
- **Funded-account caps** (15 contracts, 040/041/050) and **6 months of paper** (048): account rules, not applicable.
- **Silver Bullet "new traders start there"** (045 ~9:34 in the notes): not confirmed in the captions near that time. Skipped.
- **Funded "never reverse"** (001 ~48:03): overridden by the owner's decision (row 6).

## Param changes (summary)

Change existing params:
- `nfp_thu=True`
- `fomc_pm_from=885`
- `min_draw_pts=5.0`
- `reentry_half=True`

Add new params (true for all of these):
- `nfp_day=True`
- `nfp_week_block=False` (or `nfp_wed_pm=True`)
- `reverse_after_loss=True`
- `lunch=(710, 810)`
- `nwog_days=60`, wired into `htf.gaps_for_day`
- `turtle_soup=True`
- `reentry_lock_r=2.0`, `reentry_target_r=3.0`

Tests, not defaults (the experienced value is **[inf]** or aggressive):
- `htf_risk_dollars=5000`, `htf_risk_within_pts=30`
- `partial` = 0.25 or 0
- `adds=(0.5,)`
- `one_market=False`
- `fomc_pm_from=865`

Already the experienced version, no change:
- CPI
- Mondays
- trades per day/week
- no directional-bias requirement
- choppy days
