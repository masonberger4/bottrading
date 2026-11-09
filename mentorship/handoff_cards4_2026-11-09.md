# Handoff: card defaults build, after stages S3 and S4 (2026-11-09)

Read first: `mentorship/handoff_cards3_2026-11-09.md` (and the two before it). Their standing rules still hold: one laptop writer, work only in `C:\Users\mason\bottrading`, leave ict_fetch and the Silver Bullet bot alone, one pytest at a time (detached for long runs), a second-agent review per stage, commit + push every 30 min, only Mase merges.

## Where it is
- Branch `claude/project-thread-ufyth4`, PR https://github.com/masonberger4/bottrading/pull/57 into `mentorship` (open, mergeable). PRs #55 and #56 are merged.
- Worktree `C:\Users\mason\bottrading\.worktrees\scb`. Python `C:\Users\mason\bottrading\.venv\Scripts\python.exe`.
- Head 5c30935. `tests/test_cards.py`, `tests/test_cards_rules.py`, `tests/test_caption_gap_bh7.py` pass (65).

## Done
- S2 post-fix smoke (ES 5m 2023, `%TEMP%\bt\smoke2.py`): new defaults 3 trades / -$98.7, all S2 off 2 / -$21.9; the whole difference is OB-CLOSE (`ob_arm`). No FVG-path HITS at all on plain `B.run`.
- S3 (204840e, review fixes in 26c7358 / 5c30935). Rules in `cards_rules.py`:
  - PREMARKET-RANGE A `pm_window=(420,540)`, `pm_news_cut=True`: `premarket_range` rewrites `ctx.pd` pmh / pml from the 07:00-09:00 bars (08:30 on 08:30-release days), and `ctx.pre_at` for session starts after 07:00 (earlier ones keep the overnight range). E / H built; B C D F G queued with reasons.
  - ORG-SIZE B `org_size="buckets"`, ORG-AFTER-CE A `org_after_ce="continue"`, ORG-CE-WINDOW A `org_ce_by=600`, knob `org_handle=0.25` (ES pts per NQ handle). `org_play(ctx, p, i)` gives the AM draw: < 20 and 75-120 handles none, 20-75 the far edge (or the CE with "done"), > 120 the near quadrant; dropped (relock) from 10:00 unless the CE / q1 traded 09:30-10:00. Hooked in `mark_levels` prefs, the lock-loop relock next to `org_far`, and `_draw_prefs`. ORG-SIZE A / C / D / E, AFTER-CE B, WINDOW B built; WINDOW C / D queued.
  - Review notes left: the legacy `org_draw` / `org_half_draw` prefs ignore `org_size` and share the `org_pref=False` relock with the card play (matters only in combination runs).
  - Smoke (`%TEMP%\bt\smoke3.py`, ES 5m 2023): new 1 trade / -$9.0; S3 off 3 / -$98.7; PM window only 3 / +$25.0; ORG play only 1 / -$9.0; ORG-SIZE A 7 / -$340.4; AFTER-CE B and WINDOW B equal the default.
- S4 (26c7358, review fixes 5c30935):
  - OVERNIGHT-HOLD B `overnight_hold="osok"`, `osok_days=5`: `cards_rules.osok_hold` (called in `backtest.run`) keeps an "eod"-flattened trade's lots to the nearest untraded daily FVG CE ahead, walking the later day frames (stop = initial, or entry after a partial; gap fills at the open; time exit after 5 sessions). Held trades join `rows` only after their exit day (no future P&L in equity / week budgets); `max_trades_week` counts them. Not built: the adds after midnight, the 16:00-04:00 bars (not in the day frames), trailed stops, half-days dropped by `days()`; `risk_state` sees the eod P&L.
  - CONTRACT B stays NOT_BUILT: `htf_series="raw"` as the default makes `Params().bx` non-empty, which bypasses the bias CSV cache and breaks the `bx == ""` tests. Needs a cache key for the raw table first. `backtest.raw_series` now falls back to the adjusted table when the raw file ends before the frame (paper / live).
  - VENOM-STOP stays NOT_BUILT: the Venom model is not in the engine.
  - S4 smoke (`%TEMP%\bt\smoke4.py`, ES 5m 2023, run before the review fixes): 2 trades / -$12.4 with or without OSOK. Both exits were stops, so no trade reached the eod flatten and OSOK never ran (no `osok_*` HITS). It needs a run with more trades to be exercised.
- Old values: `tests/_legacy.py` LEGACY and `study.CARDS_S3_OLD` / `CARDS_S4_OLD`.

## Next
1. The engine trades only 1-3 times a year on plain `B.run` (ES 5m 2023), so the smokes barely exercise the cards. The screen in step 4 will be the real check; look at the `osok_*` / `org_*` HITS there.
2. Decide with Mase: CONTRACT B (build the raw-table cache key so it can be the default) and VENOM-STOP B (needs the Venom model built first).
3. Fix the tests: the 143 legacy-rerun failures (`mentorship/legacy_rerun_fail_ids_2026-11-08.txt`) plus whatever S2-S4 broke, then one full suite detached (start-laptop-run skill).
4. Fresh 2021 screen (run-backtest-screen skill, new tag), report in $ at $1k risk.
