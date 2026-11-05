# 2026 SMC 070: Holiday Monday is a no-touch day; opening at equilibrium of the dealing range means no bias (Monday Jul 6 2026 follow-up)
Full read (3.8k words). Clean caption. Frames laptop-only. Monday after July 4 (Saturday; observed Friday Jul 3). Earliest-dated lecture in this batch.
## Summary
ICT traded with no bias in front of Caleb, took a loss, mitigated it, then stopped. Price opened right at the 50% of the 15m dealing range (equilibrium), rallied into the upper 15m inefficiency (just past its CE), returned to the FPFVG, reached the lower quadrant but failed at the next octant, and failed again in the PM session. Main lesson: low-participation days after a US bank holiday on a weekend; stay out. Plan for Tuesday: if price sustains below the relative equal lows, the lower inefficiency is the draw; if it climbs back, the upper area.
## Rules in ICT's wording
- **Holiday rule**: "if Saturday or Sunday has a US holiday that would usually close the banks down, then Monday is a no touch day." "Tape read it. Don't demo it. Just stay out of it." Normal delivery returns "by Tuesday or Wednesday."
- Low participation days = major bank holidays (not e.g. St Patrick's Day).
- After a second loss in such conditions, stop ("Don't try to go back in and force the hand").
- **Equilibrium open**: measure the dealing range high to low; "We opened right just above [50%]. We're at equilibrium. So, nobody's going to know really with a great deal of certainty." Submit to time and wait for data.
- **Lay of the land** = "A dealing range low and a dealing range high and a very small minor buy side and a minor sell side" plus the two extreme inefficiencies (lowest and highest in the range). That's all.
- Algorithm as auctioneer: on low-participation days the market is "offered at higher prices"; dealers "are miscalled as market makers ... they're not creating the high and low of the day."
- FPFVG anchor: VI between two candles' close/open plus the next candle's high (no VI at the low).
- Wick CE without a close below = not continuation; switch to the opposite target.
- Bodies sitting exactly at an FPFVG CE on a retest = respected.
- **If-then planning**: "I'm not saying if it goes up I'm right. If it goes down I'm wrong ... If the market proves to me that it wants to do specific things, then that will align me." A sustained run below lows (not a poke) is required.
- Summer (July/August) "dog days": dial back participation; look only for one-directional setups with few opposing factors.
- "If you're not really willing to lose on that trading idea and you don't feel one-sided about your analysis, then it's not high probability."
- A demo probe that fails tells you the read isn't panning out: change opinion or step aside, not the model.
## Our interpretation / switches (all off)
- [off] skip_monday_after_weekend_bank_holiday [new; conflict check: 2023 holiday rules]
- [off] no_trade_when_open_at_dealing_range_equilibrium (within X% of 50%) [new, backtestable]
- [off] summer_reduced_participation (Jul-Aug: size down or A+ only) [new, seasonal switch]
- [off] max_two_losses_then_stop [same as 055]
- [off] sustained_break_required (body run, not poke) before targeting the next inefficiency [refines 055 bodies rule]
