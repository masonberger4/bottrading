# 2024 Mentorship Lecture 11 (aONkyy-HTqE): Jackson Hole week Monday, NWOG calibration, IOFED live long, targets via NWOG quadrants, FOMC two-stage
Live 2024-08-19 (Mon, Jackson Hole week), ~09:25-12:30 ET, NQ, 1m + 15s. ~3h52m. Captions only.
Source tier: 2024 Mentorship. Live executions shown (demo per ICT's usual practice): long via IOFED in a 10:00 FVG after a sell-side sweep into Aug 16 NDOG; exit at the NWOG lower quadrant + 1 tick. A pre-stream morning trade was also shown.

## Summary
Monday, with NQ inside the opening range gap and below this week's NWOG low. ICT calibrates the NWOG (Friday settlement → Sunday 18:00 open; no CE marked because it is under 20 handles), lets price sweep the sell-side and reach Friday's NDOG, then calls the FVG before it forms and enters with IOFED (2 handles of heat). Targets are set as "beyond the relative equal highs, the nearest NDOG/NWOG, split into quadrants; exit at the first quadrant + 1 tick". Also: Caleb's 07:00 framework, FOMC's two-stage delivery, and graduated holding rules.

## Rules
- NWOG CALIBRATION: Friday's last tick (17:00 settlement) to Sunday 18:00 open; label "NWOG <date>"; mark CE only if the gap is 20+ handles ~6:00-8:01
- ORG: 16:15 RTH settlement to the 09:30 first print (not electronic hours); use RTH view to see it; quadrants apply ~10:00, ~16:02-18:02, ~52:00
- Opening range = 30 min (09:30-10:00), "there is no 15-minute opening range" ~18:02, ~1:42:01
- Jackson Hole week (Wed-Fri): lots of overlapping, back-and-forth delivery before targets; take first partials at the first easy level; trailed "cover costs" stops tend to get hit ~30:03-34:00, ~40:00
- How far below sell-side: to the next NDOG/NWOG (e.g., Aug 16 NDOG) ~12:01, ~16:02, ~50:01
- After the sweep: want a technical sign (short-term breaker, MSS, FVG) before longs ~14:00
- Stop placement (trailing): below a balanced price range / wick CE that price passed back and forth through ~1:02:00
- IOFED (CALEB'S ENTRY MODEL): FVG called while candle 2 is still forming; buy at the FVG high + 1 tick (a long's near edge); the gap must not fully fill; heat allowed (here 2 handles = $40/contract ES-equivalent... ICT's figure) ~1:08:01-1:22:02, ~1:30:02, ~2:00:03
  - Don't demand the low end of the gap; knowing the draw matters more than a perfect fill ~1:30:02
  - Never let price close below the CE of the sweep wick; ideally don't trade to it at all ~1:20:01, ~1:58:03-2:00:03
  - This was a 10:00 Silver Bullet FVG ~1:20:01 (SB is OFF in our rulebook)
- The level the bodies respected is the one the algorithm returns to (use the NDOG the bodies respected, not the one they ignored) ~2:00:03
- CALEB'S FRAMEWORK (07:00 rule): wait for 07:00; mark relative equal highs/lows that form after 07:00; if you start watching at 08:00 or 09:00, look back to 07:00 only; the first side taken is the trap (Judas); the second side is taken later ("the first shall be last") ~1:46:00-1:50:01, ~2:08:00, ~2:42:01
  - Advanced students may use pre-07:00 (London, daily power of three) ranges ~1:48:00
- Session draw on liquidity is dynamic (above and below); daily bias comes after you can read the session bias ~1:32:00, ~1:40:00
- VALID RELATIVE EQUAL HIGH: a high with a slightly lower high to its right; if the right one prints a higher high only with a wick while the body closes lower, it still counts ~2:56:01
- TARGETING: (1) where are the relative equal highs/lows; (2) how far beyond: the nearest NDOG/NWOG beyond them; (3) split that gap into quadrants; the easiest exit is the first (nearest) quadrant + 1 tick; CE is the stretch ~3:04:03-3:18:00
- GAP + ORDER BLOCK (bullish): a true opening gap (no wick overlap) right after a down-close candle is a strong PD array; buy when price trades into it ~3:14:00
- Breakaway FVG: didn't trade back into it → strength ~3:14:00
- Price delivery continuum: on the 15s chart, the IOFED/breaker/FVG show earlier than on 1m ~2:46:03-2:54:03, ~3:26:03
- Short management: pyramid at a touch of an FVG candle's low if liquidity hasn't been taken yet; first partial when the next level breaks with speed ~3:24:00
- FOMC: two-stage delivery: the move into 14:00, then 14:00-14:30; ~70% of the time the 14:30 move goes the OPPOSITE way and is more exaggerated; hold till ~15:15, which starts the last-hour macros (four macros in 15:00-16:00; no "20-40" macros) ~58:01-1:00:00
- Minutes releases are less impactful than rate decisions ~58:01

## Risk / Process [beginner]
- One contract (Caleb); after a winning day (all partials done), close the charts and don't reopen until end of day ~1:22:02-1:24:02
- Losing streak: change nothing but risk (reduce leverage) ~1:22:02
- Graduated holding: first close at the target; next step, hold through lunch and close everything at 13:30 if in profit ~2:30:02

## Trade examples
- 2024-08-19 long (demo): sell-side swept below relative equal lows into Aug 16 NDOG; back above the NDOG high; IOFED at the 10:00 FVG (fill ~19,580.50, low 19,578.50 = 2 handles heat); rallied through the NWOG low/CE to the NWOG high. Later long: gap + OB entry, exit at NWOG lower quadrant + 1 tick (19,060.25 as captioned; caption prices are partial).

## Definitions
- NWOG: Friday 17:00 settlement to Sunday 18:00 open.
- IOFED: entry at the near edge of an FVG expected to stay partly open.
- Valid relative equal high: left high slightly above the right high.

## Open questions / conflict checks
- [conflict check] 10:00 SB FVG used here; SB is OFF (owner) → keep off; but `iofed_entry` is testable in any window.
- [conflict check] 07:00 framework (relative equal highs/lows after 07:00, first side = Judas, second side = target) vs rulebook session framing; switch `bias_0700_judas_second_side`; default off.
- [new] `nwog_ce_min_20_handles`; default off.
- [new] `target_first_quadrant_of_next_gap` (exit at first quadrant of the NDOG/NWOG beyond the relative equal highs/lows + 1 tick); default off.
- [new] `gap_plus_ob_entry`; default off.
- [new] `fomc_1430_reversal` (study only; pre-14:00 flat; ~70% claim testable); default off.
- [new] `stop_trading_after_win_day`; default off.
- [new] `hold_to_1330_exit`; default off.
