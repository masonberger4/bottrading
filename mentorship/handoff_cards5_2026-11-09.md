# Handoff: card defaults finished, 2021 cards screen (2026-11-09)

Standing rules from the earlier card handoffs still hold (one laptop writer, `C:\Users\mason\bottrading` only, leave ict_fetch and the Silver Bullet bot alone, one pytest at a time, second-agent review per stage, commit + push every 30 min, only Mase merges).

## Where it is
- PR #57 (card defaults S1-S5) is merged into `mentorship` (16aea32). Follow-up PR #59, branch `claude/project-thread-kekmm5`, head 918c2ed: two look-ahead fixes and two stale tests. Worktree `C:\Users\mason\bottrading\.worktrees\scb` is on that branch.
- Temp dirs to delete: `.worktrees\bis` (a git worktree: `git worktree remove --force .worktrees\bis`), `.worktrees\oldcards` (plain copy with data junctions; remove the junctions first).

## Done in this thread
- Tests: the 143 legacy failures came from test modules' own `@dataclass class Params(Params)` subclasses, which dropped the old defaults. `tests/_legacy.py` LegacyParams is now a `make_dataclass` subclass; `tests/conftest.py` runs every `test_*` module through an import hook that binds LegacyParams for the modules in LEGACY_MODULES (any run order or subset) and the real Params otherwise, after preloading the engine. A fixture asserts each module got the right one.
- CONTRACT B is the default (`htf_series="raw"`). `study._bias_cache` keeps the raw table on disk as a pickle keyed by the raw file's last bar, the adj hash and a hash of the engine source; it falls back to the adjusted table when the raw file ends before the frame.
- Venom model (`mentorship/venom.py`, `venom_model=True`) with VENOM-STOP B (`venom_stop="bpr_ce"`, `venom_entry="open"`). Its own AM book next to the NDOG scalp. Variants SC-VENOM-STOP-A and SC-VENOM-off.
- Full suite on f5dbfe0: 5315 passed, 3 skipped, 2 failed (both stale tests, fixed in 918c2ed).

## 2021 cards screen (engine f5dbfe0, ES 5m databento, $1,000 risk per trade)
Script `%TEMP%\bt\cards_screen.py cards_f5dbfe0`; output `runs\mentorship\cards_f5dbfe0\summary.csv` / `summary_2021.csv` (laptop only, untracked).

Defaults baseline by year (trades / $):
2019 13 / +459, 2020 21 / -3,442, 2021 17 / +101, 2022 28 / -3,019, 2023 32 / +847, 2024 15 / -1,656, 2025 22 / +6,354, 2026 20 / +1,166.
Total 168 trades / +$810; 2019-22 -$5,901, 2023-26 +$6,711. The Venom model fired twice in eight years (2020, 2022).

2021, 72 card variants: 43 equal the defaults (the engine trades ~17 times a year, so most cards never bite). Best vs defaults: PREMARKET-ENTRY A +$1,120 (16 trades), STOP-MGMT B +$697, OB-VALID A +$357, LUNCH-WINDOW D +$343, MIN-ROOM C +$322, GAP-LIFE B +$309. Worst: LUNCH-TRADE A -$824 (4 trades), ORG-CE-WINDOW B -$407, HOLIDAY-WEEK A -$271. SG-m2024-41-off trades 104 times (-$50). With 15-20 trades a year these gaps are noise-sized; none is a clear mover yet.

## Next
1. Expand the top few (PREMARKET-ENTRY A, STOP-MGMT B) to 2019-22 per the screen plan, then check 2023-26.
2. Trade count is the real problem (168 trades in eight years). Worth a look before more card screens.
3. `data\mentorship\ES_1min_dbraw.csv` is cut to its first week (425 KB); only the parquet copy is full. If the CSV's mtime ever changes, `backtest._read` rebuilds the parquet from the cut file. Re-copy the full CSV.
