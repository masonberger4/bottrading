# data.md — data sources, paths, purchases

## From the old MEMORY.md index
- Data: Databento ES/NQ/YM 1m Jan 2016-Oct 16 2026, DXY 1h+1d 2019-2026, ZN/ZB 1d 2016-2026; laptop bottrading\data\databento_extra\ and shared /mnt/project-files/mentorship/data/databento/.
- Spot DXY file copied by Mase to bottrading\data\dxy\ and verified 20:59 UTC 2026-11-01.
- DXY 1m (thread "Find free 1-minute DXY data", cmsg_01FAHERC1Lsrg2bYtrKuRHmPNsqWLqNfTMRBGcyadS1Ste): in /mnt/project-files/mentorship/data/dxy/. USE spot_dxy_1m_close_2019-2025_NYtime.csv.gz (six-pair ICE rebuild from free HistData, close-only, NY time, README_spot.md) for ICT levels: matched 5 of 6 ICT examples. 2023 ~9% fewer rows (scattered short gaps). HistData UDX/USD is a futures-type series, kept for reference. No 2026. Paid Databento DX 1m ($64.48) not bought. Coverage audit: /mnt/project-files/mentorship/coverage_gaps_2026-10-31.md.
- DOWNLOADS rule (Mase, 00:45 UTC 2026-10-31): any FREE download is pre-approved. Paid purchases need Mase's OK in the thread that buys. Databento ~$26 left est.
- Cloud access: 457 mentorship text files in /mnt/project-files/mentorship/laptop/. Code: private repo https://github.com/masonberger4/bottrading.
- Project upgraded from a classic claude.ai project on 2026-10-10. Files under /mnt/project-files/ (UPGRADE-NOTES.md); imported memory under /imported/ (old Silver Bullet overview, kept in place in project memory).
- Cloud shared files in /mnt/project-files/mentorship/: rules.md, decisions.md, full_detail_check_ep01-08.md, handoff.md, handoff_wiring_2026-10-30.md, owner_answers_build_2026-10-29.md, dxy_intraday_spec_2026-10-31.md, coverage_gaps_2026-10-31.md, coverage_build_2026-10-31.md. Latest repo handoffs: mentorship/digests/handoff_2026-11-01.md, handoff_backtests_2026-11-02.md.

# Detailed memory files moved here verbatim (one section each)

## databento-extra-data — Extra Databento data bought 2026-10-24 (DXY 1h/1d, ZN/ZB daily), prices, credit left, and 2016 extension pricing
(source: databento-extra-data.md, modified 2026-10-24T18:24:16.323Z)

Bought 2026-10-24 (Mase approved, $20.11 total; ~$43 credit left of $63): DX.FUT ohlcv-1h ($17.86) and ohlcv-1d ($2.08), ZN and ZB ohlcv-1d ($0.09, $0.08), 2019-01-02 to 2026-10-16. Laptop: bottrading\data\databento_extra\; cloud copy: /mnt/project-files/mentorship/data/databento/ (DX_ohlcv1h/1d, ZN/ZB_ohlcv1d .dbn.zst). ZN/ZB are bond PRICES (invert for yield rules). Databento flagged a few degraded days (2019-01-15/16/18, 02-01, 02-22, 03-13 ...).

Why only daily/hourly: Mase wanted the cheapest timeframes that serve the rules; DX 1m would be $64.24 (2023-26 only $30.62). Hourly keeps direction for the DXY gate (ES lower low vs DXY higher high), blurs 5m/15m timing. Other prices: gold daily $0.73, crude 1m $195 (skip), ZF skip.

IFUS.IMPACT (DXY) starts 2018-12-23: no DXY before that. GLBX.MDP3 starts 2010. Extending ES/NQ/YM 1m + ZN/ZB daily to 2016-01-01..2019-01-01 priced at $15.34 (ES 5.95, NQ 4.82, YM 4.49, ZN/ZB 0.03 each); BOUGHT 2026-10-24 for $15.32 (files *_2016-18.dbn.zst, laptop data\databento_extra and cloud shared folder); ~$28 credit left. Degraded days 2017-11-13, 2018-10-21.

Credit balance is only visible on the Databento portal (Billing), not the API. Free data still free: COT (CFTC), Treasury auction/Fed-speaker/early-close calendars. Engine already has dxy_gate/bond_range/bond_dir switches (bias_htf.py) reading Yahoo daily DXY/TNX; they are OFF by default and still need wiring to the new files.

## mentorship-laptop-copy — Where the cloud copy of the Mentorship bot's video notes, captions, digests and rulebook lives (readable with the laptop off)
(source: mentorship-laptop-copy.md, modified 2026-10-18T16:43:14.091Z)

Snapshot copied 2026-10-18 ~16:50 UTC from C:\Users\mason\bottrading to /mnt/project-files/mentorship/laptop/ (README.md there maps each folder to its laptop path). 457 text files, ~12 MB: mentorship_rules.md, mentorship/digests/ (17), mentorship/notes/ (217 videos + PROMPT/BATCH), data/mentorship/captions/ (217; 6 have no YouTube captions: 004, 023, 034, 083, 088, 097), playlists.txt, IDEAS.md. Key frames, price data, code, runs not copied.

**Why:** Mase wants every session to read these when the laptop is off; no GitHub repo needed for that.
**How to apply:** read from the shared folder first; the laptop stays the source of truth, so re-copy (same paths) after the rulebook/digests change. See [[mentorship-bot]].

## data-wiring-state — Databento data wiring DONE and pushed (origin/mentorship ed54858, 2026-10-31); lessons for laptop test runs
(source: data-wiring-state.md)

Wiring thread finished 2026-10-31 ~00:35 UTC: origin/mentorship = ed54858 (fast-forward from d318279). Params.im_source/im_bond default databento, Yahoo kept as a switch; ES/NQ/YM 1m 2016-2026 rebuilt from raw dbn (extend_2016 bug fixed, per-year coverage test). Full suite: 5,062 tests, 0 failed, 1 skipped. Next step: owner_answers_build_2026-10-29.md, built on the laptop in a NEW thread; handoff at /mnt/project-files/mentorship/handoff_wiring_2026-10-30.md.

Laptop test-run lessons:
- A suite started inside the RC Claude session is its child, so ending the session can kill it. Launch long runs detached (Start-Process powershell, minimized, log under %TEMP%\bt\).
- Check for an existing pytest (Get-CimInstance Win32_Process) before any rerun. Duplicates happened twice from misread checks.
- The xdist tail on test_bias_htf_lookahead variants can crawl on one core. Rerunning just the remaining IDs (runs\run_remaining.py, repo root on sys.path) finished 354 tests in 22 min.
- The RC session goes quiet while waiting and can park when idle; parking did NOT kill the run.
- Mase runs taskkill himself (the laptop is blocked from killing processes).

**Why:** next threads must not re-diagnose. **How to apply:** for laptop suites, launch detached, one run at a time. Related: [[databento-extra-data]].
