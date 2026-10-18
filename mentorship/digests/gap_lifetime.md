# Gap lifetime: how long ICT keeps NWOG / NDOG / ORG and PD arrays live

Question: does ICT keep only the NWOGs from the last 20 trading days and forget the rest? And
what are the lifetimes for NDOG, ORG and the IPDA 20/40/60-day look-back?

Sources: every note matching the grep in the task brief, plus the transcript lines
(`data/mentorship/captions/<basename>.txt`) around each timestamp. Quotes are verbatim from the
auto-captions (caption typos kept), each under 15 words. Episode numbers give the order in the 2023
series; `cc*` files are the 2016-17 Core Content.

## Short answer

- **"20 trading days" is never stated for NWOGs.** The only "20 days" rule in the 2023 series
  is 015 (~4:35-4:57), and it covers PD arrays in general: the last 20 days are the most sensitive.
  It does not say older levels are forgotten ("After 20 days, the market may respect those levels").
- **The NWOG count is 4-5 weeks** (030, 039, 050, 092), which is about 20-25 trading days. ICT
  calls this a minimum, not a cut-off: "no real limit" (039 ~11:07). From 051 on, the stated
  maximum is **every NWOG from the last 60 days** (the IPDA 60-day look-back).
- **The owner's memory probably mixes two rules:** 015's "20-day sensitivity" and 039's "four,
  preferably five, a rolling 30 days". ICT never says that anything beyond 20 days is forgotten. In
  every episode he stresses the opposite: old gaps keep working after they are filled.
- **NDOG:** kept for the current week only (052), or 5 days (068). It is short-lived.
- **ORG:** kept 3 days (060), then 5 days (068), then "a few weeks", about a month to 1.5 months,
  about 60 days at the outside (092).

## 1. NWOG statements (in series order)

| File | Time | Exact words (<15) | Paraphrase |
|---|---|---|---|
| 020 | ~00:03:50-10:06 | (chart label "Draw On Liquidity") | First NWOG lesson. The NWOG is a target: near edge, then CE, then far edge. Its lifetime is not discussed (the note's open question). |
| 025 | ~1:44-4:27 | (note) extend through the whole week | Current-week NWOG: high, CE and low extended through the week as magnets/S-R. |
| 030 | 00:31:36-31:47 | "the last four you want to have on your charts" | Keep the last four NWOGs. Today he is "only using the previous week". |
| 030 | 01:32:16-32:34 | "previous week new week opening gap for the last four weeks" | Save a template showing the current NWOG plus the previous four weeks. |
| 031 | ~0:33:20 | (chart) older NWOG as deeper draw | An older NWOG below price is treated as the deeper downside draw. |
| 037 | 00:22:17-22:31 | "traded to and through multiple times but it's acting like a magnet" | An old NWOG that has been filled many times still pulls price. |
| 037 | 00:24:40-24:46 | "Sunday Gap being referred to after it's been used multiple times and weeks ago" | Same point: a gap from weeks ago, already used, is still referred to. |
| 038 | ~0:27:22-27:42 | "label them by date using the Sunday gap opening price" | Label each NWOG by its Sunday date. This implies he keeps several. |
| 039 | 00:03:39-03:51 | "it can refer back to it weeks ago a month ago or more" | Price returns to NWOGs from weeks to more than a month back. |
| 039 | 00:03:49-03:53 | "I like to have a minimum of five weeks worth of it" | Minimum is five weeks. |
| 039 | 00:04:17-04:37 | "minimum four new week opening gaps on your chart" | At least four for "large fund fair valuation". Five gives overlap, "not just the blanket four weeks look back". (He also says "dynamic four months perspective" here, probably a slip for about one month.) |
| 039 | 00:10:52-10:59 | "many times are treated as support and resistance" | Old NWOGs act as S/R. |
| 039 | 00:11:01-11:14 | "at least four preferably five it gives you a rolling 30 days" | 4-5 NWOGs = a rolling ~1-month look-back. "there's no real limit as to how many you want to keep." |
| 046 | 00:16:32-16:45 | "closest new week opening Gap in the last 60 days" | Holiday-distorted week: skip it and use the closest normal NWOG from the last 60 days. If there is none, use nothing. |
| 048 | ~00:02:51-03:18 | "taking it back to an old new week opening Gap" | Holiday week again: he uses the old NWOG as the draw (CE as target). |
| 050 | 00:14:46-15:01 | "using these gaps through an extended period of time casting forward" | Gaps are extended forward. A fill does not end them. |
| 050 | 00:15:07-15:18 | "will refer back to that same area again ... for weeks and months" | The algorithm revisits NWOGs for weeks and months. |
| 050 | 00:16:01-16:05 | "try to have at least five of the most recent" | Beginner baseline: at least 5. |
| 051 | 00:16:51-17:07 | "series of the last several weeks and months" of NWOGs | Chain rule: reaching 50% between two NWOGs means price will probably reach the next one. Uses NWOGs going back "weeks and months". |
| 051 | 00:17:37-17:54 | "see what new week opening Gap extends through that area" | In a consolidation, look back for the old NWOG that runs through the cluster. |
| 051 | 00:17:58-18:02 | "whatever today is in trading I look back 60 days" | Answers "how many NWOGs?": 60 days. |
| 051 | 00:18:30-18:41 | "formed in the last 60 days ... that's the maximum I have" | Maximum = every NWOG formed in the last 60 days (IPDA 60-day look-back). |
| 051 | 00:18:45-18:51 | "you want to have at least five" | Beginners: at least 5. Experienced: the full 60 days. |
| 052 | 00:03:53-04:01 | "as many as many weeks and multiple months looking back 60 days" | Restates the NWOG look-back as 60 days (contrasted with the NDOG). |
| 053 | ~01:31, ~08:50 | (note) converging NWOGs -> consolidation | An old NWOG close to the current one signals a sideways week. |
| 058 | ~53:46 | (note) bearish until back above NWOG low | The NWOG used as a bias line. |
| 068 | 00:10:31-10:36 | "new week opening gaps I can hold on to them and use them for months" | NWOGs last months (contrasted with the 5-day ORG/NDOG). |
| 092 | 01:57:27-01:57:34 | "keep the last five weeks or so on there" | Template: the last ~5 weeks of NWOGs. |
| 092 | 01:57:35-01:57:41 | "you can keep them on there longer" | Keep older ones too, but make the last five stand out by colour (older ones dimmed). |

### Old NWOGs: draws or levels?

Both. ICT uses them three ways:
1. **Draw/target:** 020 (near edge -> CE -> far edge), 031 (older NWOG as the deeper draw), 048
   (old NWOG CE as the objective), 051 chain rule (passing 50% toward the next NWOG -> it will be
   reached), and 038 (a sell-side run should stop at the nearest NWOG/NDOG/ORG).
2. **S/R and reaction levels:** 039 ~10:58 ("treated as support and resistance"), 037 ("magnet").
3. **Context:** 051 (an old NWOG that runs through a consolidation "explains" the range), 053
   (converging NWOGs -> sideways), 025/058 (bias above or below the current NWOG).

The older the gap, the more ICT uses it as context or as the deeper "next" target, not as the first
draw. The first draw is the current or most recent NWOG, or the next one in price order.

## 2. NDOG statements

| File | Time | Exact words (<15) | Paraphrase |
|---|---|---|---|
| 031 | 00:13:50-13:53 | "a level that you want to have annotated in your charts all the time" | First mention. Keep it marked, even a 1-tick gap. |
| 032 | 00:03:24-04:18 | "new day opening Gap is the difference between where we close at 5 PM" | Definition. In the example he keeps it through the next day. |
| 033 | 00:03:44-03:55 | "extend that out through the time of the trading day" | Extend it through the trading day. Price reprices to it many times. |
| 050 | 00:53:38-53:58 | "that's the new day opening Gap extend that forward folks" | Thursday trade off Wednesday's NDOG. It survives at least into the next day. |
| 052 | 00:04:23-04:31 | "if it's not showing a meaningful separation ... I won't even utilize it" | Size filter: preferably more than 1 handle. |
| 052 | 00:05:03-05:12 | "casting it throughout the entire week once that week closes I'm not interested" | **Lifetime = rest of the current week.** Discard when the week ends. |
| 052 | 00:05:24-05:36 | "utilize the very first new day opening Gap ... throughout the entirety of the week" | Use the first meaningful NDOG of the week and carry it to Friday. |
| 052 | 00:05:50-05:58 | "once it closes the gap that's not a point of abandoning" | A fill does not end it within that week. |
| 068 | 00:10:41-10:53 | "opening range gaps and new day opening ... expiration date and it's five days" | **5-day expiry**, the same as the ORG. |

The NDOG is never kept beyond about a week. 052 (week-bounded) and 068 (5 days) roughly agree:
5 trading days is about one week.

## 3. ORG (RTH opening range gap) statements

| File | Time | Exact words (<15) | Paraphrase |
|---|---|---|---|
| 033 | ~00:11:36-14:57 | (note) expect intraday price to reach into it | The ORG is a same-day draw unless it is a breakaway gap. |
| 060 | 00:30:33-30:35 | "I'd like to keep opening range gaps on my chart for three days" | **3 days.** |
| 060 | 00:50:32-50:41 | "use three days as general rule of thumb ... after three days take it off" | Same rule. "sometimes it'll refer to it beyond three days." |
| 068 | 00:09:51-10:01 | "I don't like to take them Beyond five days" | **5 days.** |
| 068 | 00:10:01-10:12 | "doesn't mean that you won't find examples ... respected them" | Admits older ORGs sometimes work. 5 days is his filter. |
| 072 | 00:24:56-25:20 | "they're not looking at gaps multiple times in the future" | Filled gaps stay live: low, CE and high are referred to again. |
| 080 | 00:03:51-03:58 | "these gaps will be referred to by the algorithm they don't just fill and forget" | A partly filled ORG is referred to later. |
| 092 | 01:58:07-01:58:27 | "when they close you change the color" ... "dim it out" | Track ORGs in a template. Dim them once filled, do not delete. |
| 092 | 01:58:47-01:58:57 | "they're useful for a few weeks they expire after about a month" | **About 1 month, sometimes 1.5 months.** |
| 092 | 01:58:58-01:59:06 | "old gaps you know three months ago will still work" | Sometimes 3 months, "beyond that I won't be interested". |
| 092 | 02:00:36-02:00:41 | "repeatedly used in the future with an expiration date of about 60 days" | **About 60 days.** |
| 092 | 01:59:48-01:59:56 | "not by itself with other PD arrays" | Old ORG levels are confluence at the right time of day, not standalone signals. |

The ORG lifetime grows across the series: 3 days (060) -> 5 days (068) -> ~1-1.5 months / ~60 days
(092). The late 092 statement is a level used for confluence (dimmed once filled). The 3-5-day
rule is about a gap you expect price to *return into* ("return back into it as support or
resistance", 068 ~10:20).

## 4. IPDA data ranges and the general PD-array look-back

| File | Time | Exact words (<15) | Paraphrase |
|---|---|---|---|
| 015 | 00:04:25-04:33 | "look back with PD array matrix ... 20, 40, 60 days" | PD array matrix over 20/40/60 days. |
| 015 | 00:04:35-04:46 | "highest form of sensitivity ... within the last 20 days. After 20 days" | **Last 20 days most sensitive.** "After 20 days, the market may respect those levels." |
| 015 | 00:04:48-05:00 | "newer PD arrays within the last constant 20 days look back" | His preferred setups use FVG/OB/breaker/old highs-lows from the last 20 days. **This is the source of the "20 days" idea. It covers PD arrays in general, not NWOGs, and it ranks levels; it does not delete older ones.** |
| 038 | 00:49:15-49:27 | "it could be as far as 60 days back" | Price goes up for stops or for a premium FVG up to ~60 days old. |
| 051 | 00:19:34-19:43 | "fair value Gap 60 days to me still valid ... even if it's already been filled" | Any PD array up to 60 days old is valid, filled or not. |
| 065 | 00:59:59-01:00:14 | "60 Market Days not 60 calendar days" | **60 trading days.** Highest high, lowest low and inefficiencies inside that window. |
| 065 | 03:58:25-03:58:40 | "I'm holding on to them for months ... I keep a 60-day look back" | Old gaps and PD arrays: 60-day look-back. |
| cc05_001 | 00:22:50-23:41 | "the algorithm will reach back about three trading months" | 20/40/60 trading days, "not calendar days", anchored on the first trading day of the last full month. Sometimes it reaches further. |
| cc05_003 | 00:28:30-29:21 | "go outside that normal parameter of 60 days" | Once every 60-day high and low is cleared, expect a fast run to the nearest older level beyond 60 days. |
| cc06_008 | 00:12:40-13:01 | "exhausted or traded to for the 20-day look back move out to the 40" | Go 20 -> 40 -> 60 as arrays get used up. |
| cc07_004 | 00:03:50-04:36 | "looking back over the last 20 days ... which PD array exists" | Short-term: list premium and discount arrays in the last 20 days. An array already used is "exhausted"; look further out. |
| cc07_005 | 00:01:01-01:08 | "range of the last three months so the IPDA data range of 60 days" | One-shot-one-kill look-back = 60 days, the maximum. |
| cc09_008 | 00:06:03-06:30 | "count yesterday's days one and go backwards" | Roll the 20/40/60 window forward daily from yesterday. |
| cc09_008 | 00:08:47-09:21 | "for day trading you're going to operate in those last 20 days" | Day trading uses the 20-day range. Go to 40 only if every 20-day PD array has been traded through. |

## 5. How the rule changes across the series

1. **020-025 (Jan-Feb 2023):** only the current week's NWOG, extended through the week. No
   multi-week rule yet.
2. **030 (Feb 2023):** "last four" weeks.
3. **037-039 (Mar 2023):** old NWOGs that have been filled still work for "weeks ... a month ago or
   more". Count: at least 4, preferably 5, about a rolling 30 days, "no real limit".
4. **046/048 (Apr 2023):** a "last 60 days" window first appears (holiday fallback).
5. **050-052 (spring 2023):** "at least five" for beginners. **051 makes it formal: maximum = all
   NWOGs from the last 60 days (IPDA).** 052 contrasts the NWOG (60 days) with the NDOG (this week only).
6. **060-068 (May-Jun 2023):** ORG 3 days -> 5 days. NDOG 5 days. NWOG "for months".
7. **092 (autumn 2023):** last ~5 NWOGs highlighted, older ones kept but dimmed. ORG about 1 to 1.5
   months, about 60 days.
8. **Core Content (2016-17):** the general frame. 20/40/60 trading days, the 20 days most used for
   day trading, 40/60 only once the 20-day arrays are used up, and beyond 60 only after the whole
   60-day range has been cleared.

Across the series, the NWOG window only gets longer (current week -> 4 -> 5 -> 60 days). He never
narrows it to 20 days.

## 6. Recommended bot rule

What the code does now: `mentorship/htf.py` keeps the last 5 NWOGs (`[-5:]`, `gaps_for_day
nwog_keep=5`) and the current week's NDOGs. It never retires a gap on a fill. `strategy.py` keeps
the last 4 RTH "NWOGs" (really Monday ORGs).

**Default:**
- **NWOG as a draw/target:** the last **5** NWOGs (~25 trading days), never retired by a fill. The
  primary draw is the nearest unreached NWOG edge/CE in the bias direction.
- **NWOG as a level (S/R, sweep/stop reference, consolidation context):** every NWOG formed in the
  last **60 trading days** (051, 065). Older ones are not used as entries or first targets.
- **Holiday week:** skip a NWOG with a short Friday or Sunday session and fall back to the
  nearest one within 60 trading days (046).
- **NDOG:** the first NDOG of the week that is more than 1 ES point, kept until the Friday close
  (052). Confluence only.
- **ORG:** a draw for **5 trading days** (068). After that, keep it as a dimmed level up to **60
  trading days** (092). Confluence only.
- **Generic PD arrays (FVG/OB):** targets from the 20-day look-back first. Step out to 40, then 60,
  only when nothing unused is left inside 20 (cc09_008, cc06_008).

**Alternatives to test (one at a time):**
1. NWOG draw count 4 (030, and the current `strategy.py` value) vs 5 (039/050/092) vs every NWOG
   in the last 20 trading days (the owner's recollection; about the same as 4).
2. NWOG draw window = all NWOGs in the last 60 trading days (051's "maximum") vs the 5-count
   default.
3. 60 trading days vs 60 calendar days (~8-9 NWOGs vs ~12). 065 says market days.
4. NDOG: through Friday (052) vs a rolling 5 trading days (068) vs next day only (032/033).
5. ORG as a draw for 3 (060) vs 5 (068) vs about 20-30 days (092 "about a month").
6. Recency weighting: score levels from the last 20 days above those from 21-60 days (015)
   instead of a hard cut-off.

## Open points
- The Core Content anchors 20/40/60 on the first trading day of the last full month (cc05_001).
  Later material rolls it daily from yesterday (cc09_008). For gap lifetime, roll daily.
- 039's "dynamic four months" at 00:04:30 conflicts with "rolling 30 days" at 00:11:07. It is
  treated as a slip.
- No statement says when an old NWOG stops being a *draw* and becomes only a *level*. The 5 vs 60
  split above is our reading of 092's "last five pop, keep older dimmed" together with 051's
  60-day maximum.
