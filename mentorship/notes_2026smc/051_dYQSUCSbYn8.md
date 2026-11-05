# 2026 SMC 051: "Chain of custody for price" lecture: ORG CEs through the week and grading an implied dealing range (Friday evening, NQ Sep 2026, date not stated)
Full read (9.2k words). Clean caption. Frames laptop-only. ICT calls it advanced; it assumes you know most PD arrays. A trade replay without commentary followed (not in the caption).
## Summary
A bearish week on NQ. Daily map: two discount wicks (graded, CE), last Thursday's daily SIBI (pink), and the upper VI of a daily BISI suspension block (purple), whose CE is the deeper target. Intraday: collect every day's RTH ORG CE plus Monday's FPFVG and carry them through the week. Overlapping CEs form a range: above it is premium, below it is discount. Main teaching: on Thursday, define an **implied (unrealized) dealing range** from a SIBI *body* high down to Monday's relative equal lows (28,701, which was Tuesday's ETH sell side). Grade it in octants. Each PD array touching a grade is valid, the 50% level forms a measuring gap, and price walks down to the target. "Chain of custody": how price moves from one PD array to the next.
## Rules in ICT's wording
- Know all PD arrays at least casually: one array is "your strength ... the cornerstone of your model," but awareness of the rest builds the ongoing narrative.
- **Daily wicks**: pick "the lowest stretched out candlestick wick". The wick CE alone "is not enough". A *close* below the CE of the wick shows willingness to go lower. Prefer a **body** below relative equal lows over a wick ("a more pronounced or protracted delivery").
- Premium sensitivity: "If it's bearish, we want to see the bodies stay heavy in the lower half, but if it goes up in the upper half, it needs to show strong rejection out of there." Bullish uses the upper half and bearish trades to the lower half "and lower" of an inefficiency or wick.
- Below a VI target, the next target is the CE of the suspension block it belongs to.
- **Daily data collection**: "When we have large regular trading hours opening range gaps ... we annotate that ... get the midpoint." "We're collecting all of the consequent encroachment levels on the opening range gaps. Moving into the future." Once price trades through an ORG CE, "now it's going to act as a premium array." A small part of the gap left unfilled leads to a move away (Wednesday).
- **Monday's FPFVG**: "crucial information. You want to carry it through the entirety of the week," extended right. "Coloring outside the lines is okay."
- **CE convergence**: in trading-range environments the ORG CEs of Mon/Tue/Thu converge. "What's the highest one, what's the lowest one. There's your range. So, if we can be above this, the market's going to be likely to sell off. When we're below it, it's likely to want to rally." Combine this with the higher-timeframe bias.
- Smooth lows: Monday's low "is a little too smooth ... this is not how markets bottom. They're going to come back later in the week for that." Expect a Wed/Thu change in direction and an aggressive move lower.
- **TGIF canceled**: "if it were to go up to take out buy side and then break lower aggressively, then it cancels out TGIF because we're part of a larger higher time frame decline."
- **Implied dealing range anchor**: "I can't use the high of the wick because that's allowed to do the damage. The bodies tell you the real narrative." Anchor at the SIBI candle-body high down to the draw (Monday's REQL, 28,701). "Do we do a projection off of a wick? No, because the wick is a gap that's allowed to do the damage." "If you do this part wrong, everything ... will not work for you."
- Defining the inception: "if you know where it's starting from ... When the inception of the price run begins you have to be able to define that. You only learn that from back testing."
- The SIBI lay on the upper octant. Its low (28,941) matched the next candle's high to the tick. On retrace, "it cannot leave a body in the upper half".
- **Bearish OB on a grade**: an up-close candle "has to touch or lay on [the grade] to validate this PD array". Once a candle trades down through its open, "it need not close below it ... that validates this as a change in the state of delivery." Retraces into it are sell or add points (pyramiding).
- **First-utilization wick**: a wick sitting on a key level (here Monday's ORG CE) is the one to grade. "If there's a wick on that level there, any other wick ... would be considered a candle with a wick ... Don't use those."
- VI zone: bodies stay between the candle low and the VI low.
- **Measuring gap at 50%**: "That's half of the range that's defined by my bearish order block's high down to the draw ... a fair value gap forms right there and it acts as a measuring gap ... I'm the only guy on the planet that tells you exactly where they're going to form before they form." After it, "price should accelerate ... It can consolidate, but retracements should not be seen ... drop, consolidate, and drop harder."
- A gap whose wick "can't even touch the consequent encroachment" is bearish (when bearish). An inefficiency is valid "because it's touching an octant on a unrealized dealing range."
- Holding: "Submit yourself to time. If you get scared ... take one off. Satisfy that urge."
- Exit: his limit at 28,700 didn't fill, so he got out at 28,717 (17 handles short). Then he went long the swept gap, now an IFVG, plus an OB.
- **Higher-TF retracement**: last Wednesday's 1H BISI (noon ET) lines up with the 50% of the swing range, so it is the retracement target. Treat it as an IFVG (first utilization buy side) showing premium sensitivity. "Mohawks" are allowed on higher TFs.
- **Time-frame multiples of 4**: 15m (a "really nice bellwether time frame") x4 = 1H, x4 = 4H, x2 = 8H. "Blend time frames appropriately and go to the next higher time frame key level."
- "PD array matrix" = the notepad of daily levels. Weekly range called in advance: one more small buy-side pool, then nothing higher.
- Next week: no analysis in advance, daily hindsight reviews only.
## Our interpretation / switches (all off)
- [off] org_ce_ledger (carry every day's ORG CE + Monday FPFVG through the week; CE traded through flips to premium/discount) [new]
- [off] org_ce_convergence_range (above cluster = sell, below = buy, filtered by HTF bias) [new]
- [off] implied_dealing_range_body_anchor (SIBI/OB body high to draw; never wick) [new; conflict check: 2023 dealing-range anchors]
- [off] measuring_gap_at_idr_50 -> no deep retrace expected [see 045, 049]
- [off] bearish_ob_validated_by_trade_through_open on a grade [refines 2023 OB]
- [off] first_wick_on_key_level only [new]
- [off] smooth_low_revisited_later_in_week [new]
- [off] tgif_cancel_in_htf_sell_program [refines 2023 TGIF]
- [off] tf_multiple_of_4 blending (15m bellwether) [conflict check: 2023 TF pairs]
- [off] require_body_close_beyond_daily_wick_ce [new]
