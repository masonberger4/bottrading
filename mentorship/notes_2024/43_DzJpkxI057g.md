# 2024 Mentorship Lecture 43 (DzJpkxI057g): high resistance liquidity run morning: Caleb's FPFVG inversion setup not given, stand aside, cut bait at 10:15, volume imbalance as the fallback reach in high resistance
Live Mon Oct 7 2024, ~09:25-10:30 ET, NQ (Dec), 1m + 15s, 5m/15m. ~1h04m (ICT ill, very little talking). Captions only.
Source tier: 2024 Mentorship. No live trade; describes a London-session short (15m inversion FVG, one partial, stopped on the balance).

## Summary
Monday after NFP, no news Monday or Tuesday, so price should be slow. Discount ORG (opened below Friday's settlement); mid-gap ~20,179.5 is the morning target; bias bullish toward it, shorts filtered out. Caleb's setup for the day: price trades above the first presented 1m FVG (09:31-10:00), comes back to it, uses it as an inversion (support), displaces higher, and the next 15s FVG is the entry toward mid-gap. Not just a retrace into it: it needs to displace away. The setup never formed: price sat inside its FVGs, which marks a high resistance liquidity run day; ICT stands aside and cuts bait at 10:15 if nothing forms. In high resistance conditions PD arrays deliver without precision, so instead of returning to the FPFVG, price reached into a 1m volume imbalance (body stopped at its low, one tick off ~20,163.25) and then ran to the mid-gap. A quiet morning implies cleaner lunch / PM setups.

## Rules
- CALEB'S FPFVG INVERSION SETUP [beginner]: first presented 1m FVG between 09:31 and 10:00; price must trade above (bullish) it, come back to it, hold it as support (inversion), displace higher, and form a 15s FVG = the entry, target the ORG mid-gap; a plain retrace into the FVG is not the trade ~18:00-19:00, ~24:00, ~33:00-35:00, ~1:01-1:02 (FPFVG-DEF, OPEN-RANGE-TRADE)
- ORG BIAS: discount ORG (open below previous settlement) = first 30 minutes bullish toward mid-gap; filter out shorts while aiming at mid-gap ("if it goes lower it goes without me") ~1:01-1:02 (ORG-CE-WINDOW)
  - If price returns to the 09:30 opening price and displaces lower, that hints weakness, but not a short ~34:00
- CUT BAIT: if nothing materializes by 10:15, done for the morning ~39:00
- SLOW AFTER A WEEKEND: Monday open, everyone wants a trade; be slow to act ~20:00
- No news Monday/Tuesday = slow, weak price ~2:00 (CPI-WEEK / MONDAY: Monday after NFP)
- HIGH vs LOW RESISTANCE LIQUIDITY RUN [in rulebook?]: price spending a lot of time inside FVGs (15m) = high resistance; expect no precision, deferred deliveries, deep retracements in each run, more stop-outs; a low resistance run delivers cleanly to PD arrays, fast to targets, partials easy; Caleb trades only low resistance ~51:00-53:00, ~57:00, ~1:00-1:01
  - In high resistance, don't expect the return to the FPFVG; frame the nearer inefficiency (a volume imbalance) instead ~55:00, ~1:02-1:03
- VOLUME IMBALANCE: least rigid PD array; let price trade through it, then come back above it; the body/close of the VI candle is the level (one tick variance) ~59:00-1:00
- QUIET MORNING: if the AM offers nothing, the lunch macro and PM should be cleaner ~40:00 (AFTER-BIG-DAY context)
- Afternoon plan (personal): below the FPFVG, return to it as inversion, displace lower, 15s FVG short ~54:00-55:00
- London short: 15m inversion FVG (a BISI traded through), entry inside it, one partial, stopped on the balance ~45:00

## Trade examples
- 2024-10-07 London (ICT, described): short at a 15m inversion FVG after the NWOG CE; one contract covered, balance stopped.
- 2024-10-07 AM: no trade; low ~20,163.25 at a 1m VI body, rally to the ORG mid-gap ~20,179.5 after 10:00.

## Open questions / conflict checks
- [conflict check] FPFVG must become an inversion and displace, entry on the next 15s FVG (Caleb's model detail): FPFVG-DEF / OPEN-RANGE-TRADE.
- [conflict check] 10:15 cut-off for the morning: OPEN-RANGE-TRADE / ORG-SIZE timing.
- [conflict check] High resistance = stand aside (Caleb) or frame nearer PD arrays: new card candidate RESISTANCE-DAY (with L36, L44, L49).
- [new] `fpfvg_inversion_entry`; `cut_bait_1015`; `resistance_condition_filter`; default off.
