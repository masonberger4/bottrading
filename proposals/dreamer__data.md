<!-- proposal by dreamer at 2026-11-10 06:09:24Z; target: data.md; reason: S2 Databento holdings and roll facts; link: cmsg_01FAHERC1Lsrg2bYtrKuRHmPDbwftrPdo3nKjgAAR3KTLm; status: open -->
EXACT TEXT for data.md, new section at end:

## databento-holdings-and-roll (2026-11-10)
- 2016-18: every ES contract (ES.FUT) is on disk, so the next contract's bars for each roll week are already there and the roll fix is free.
- 2019-26: only the continuous series ES.v.0 (and the NQ and YM equivalents). It holds one contract at a time and rolls late, on the Tuesday of expiry week, so the next contract's bars from before the roll were never downloaded.
- Open-interest batch of 2026-10-31: no price bars, but enough to pick each roll date.
- Effect: ICT is sometimes already on the next contract while our series hasn't rolled, so levels are off by exactly the roll spread (2023-06-13: 45 points; 2024-09-17: 61 points). Report: PR #64.
- Roll-fix quotes (Databento get_cost, 2019 to 2026-10-16): the next contract's 1-minute bars for the 2 weeks before each expiry cost $1.57 for ES only or $4.12 for ES, NQ and YM. ES.v.1 in full costs $3.61. Every contract's 1-minute bars for the whole period cost $15.98 for ES or $42.43 for all three. Daily bars per contract cost $0.15 for ES or $0.34 for all three. The credit left is about $28, which is unverified (the balance shows only on the portal's Billing page).
- Chart notes: ICT's opening range gap uses the 16:14 close, not 16:00, and a video's upload date can be a day after the session it shows.
