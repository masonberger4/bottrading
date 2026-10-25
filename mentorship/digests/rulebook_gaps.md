# Rulebook gaps: index

This file indexes the per-topic rulebook gap files in `mentorship/digests/rulebook_gaps/`. Each item in those files is a gap between ICT's captions and `mentorship_rules.md` that the checker confirmed. Every item has a rulebook text fix. Items scoped `index`, `general` or `stocks` also get a build spec, unless `rule_coverage.md` already lists the same content. Build specs name a work package from `rule_coverage.md` section 3. New Params switches default off unless the spec says otherwise.

## Pipeline counts

| Stage | Count |
|---|---|
| Raw findings | 2424 |
| After merging duplicates | 1484 |
| Confirmed by the checker | 1313 |
| Rejected by the checker | 171 |

## Confirmed items by kind

| Kind | Items |
|---|---|
| missing_rule | 651 |
| missing_condition | 313 |
| shortened | 169 |
| unlisted_contradiction | 135 |
| wrong | 45 |
| **Total** | **1313** |

## Confirmed items by scope

| Scope | Items |
|---|---|
| general | 716 |
| index | 403 |
| fx_only | 83 |
| needs_unavailable_data | 73 |
| bonds_only | 24 |
| stocks | 14 |
| **Total** | **1313** |

Items scoped `fx_only`, `bonds_only` or `needs_unavailable_data` get the rulebook text fix only.

## Topic files

| File | Items | New build specs | missing_rule | missing_condition | shortened | unlisted_contradiction | wrong |
|---|---|---|---|---|---|---|---|
| [models_setups_entries.md](rulebook_gaps/models_setups_entries.md) | 229 | 202 | 146 | 52 | 20 | 10 | 1 |
| [bias_htf_intermarket.md](rulebook_gaps/bias_htf_intermarket.md) | 227 | 168 | 110 | 59 | 31 | 22 | 5 |
| [definitions_pd_arrays_structure.md](rulebook_gaps/definitions_pd_arrays_structure.md) | 214 | 190 | 87 | 55 | 30 | 28 | 14 |
| [levels_liquidity_targets.md](rulebook_gaps/levels_liquidity_targets.md) | 180 | 149 | 103 | 32 | 27 | 12 | 6 |
| [management_partials_trailing_exits.md](rulebook_gaps/management_partials_trailing_exits.md) | 145 | 129 | 72 | 34 | 19 | 17 | 3 |
| [day_selection_news_calendar.md](rulebook_gaps/day_selection_news_calendar.md) | 92 | 75 | 37 | 23 | 11 | 14 | 7 |
| [stops_sizing_scaling_in.md](rulebook_gaps/stops_sizing_scaling_in.md) | 72 | 57 | 31 | 20 | 10 | 10 | 1 |
| [times_sessions_macros.md](rulebook_gaps/times_sessions_macros.md) | 66 | 42 | 25 | 17 | 13 | 9 | 2 |
| [session_day_week_stops_frequency.md](rulebook_gaps/session_day_week_stops_frequency.md) | 41 | 35 | 17 | 10 | 5 | 6 | 3 |
| [other.md](rulebook_gaps/other.md) | 25 | 15 | 19 | 1 | 0 | 3 | 2 |
| [silver_bullet.md](rulebook_gaps/silver_bullet.md) | 22 | 19 | 4 | 10 | 3 | 4 | 1 |
| **Total** | **1313** | **1081** | **651** | **313** | **169** | **135** | **45** |

## New build specs by work package

Each spec is counted once, under the first package its `BUILD SPEC` / `Build` line names. A spec that spans two packages is counted under the first one only.

| Work package | Specs |
|---|---|
| setups_models | 251 |
| bias_htf | 243 |
| targets_partials | 132 |
| entries_stops_sizing | 104 |
| management_exits | 101 |
| day_week_context | 101 |
| levels_detectors | 84 |
| news_calendar_times | 37 |
| silver_bullet | 27 |
| No package (parked `mentorship/stocks.py`, bias_htf_intermarket item 220) | 1 |
| **Total** | **1081** |

Per file, by package (first package named):

| File | LD | SM | ESS | TP | ME | NCT | DWC | BH | SB | none |
|---|---|---|---|---|---|---|---|---|---|---|
| models_setups_entries | 5 | 129 | 16 | 6 | 5 | 1 | 5 | 34 | 1 | |
| bias_htf_intermarket | 5 | 23 | 2 | 7 | 4 | 1 | 21 | 104 | | 1 |
| definitions_pd_arrays_structure | 45 | 36 | 39 | 16 | 14 | | 3 | 37 | | |
| levels_liquidity_targets | 25 | 23 | 3 | 57 | 4 | 1 | 6 | 29 | 1 | |
| management_partials_trailing_exits | | 11 | 2 | 35 | 58 | 1 | 4 | 16 | 2 | |
| day_selection_news_calendar | 1 | 7 | | 5 | 2 | 19 | 36 | 5 | | |
| stops_sizing_scaling_in | | 4 | 42 | 2 | 2 | | 1 | 4 | 2 | |
| times_sessions_macros | 3 | 8 | | 2 | 3 | 12 | 8 | 5 | 1 | |
| session_day_week_stops_frequency | | 5 | | 1 | 9 | 2 | 12 | 5 | 1 | |
| other | | 5 | | 1 | | | 5 | 4 | | |
| silver_bullet | | | | | | | | | 19 | |

Package keys: LD = levels_detectors, SM = setups_models, ESS = entries_stops_sizing, TP = targets_partials, ME = management_exits, NCT = news_calendar_times, DWC = day_week_context, BH = bias_htf, SB = silver_bullet.

Notes on the counts:
- definitions_pd_arrays_structure has 191 `Build (...)` lines. Item 167 reuses item 90's switch, so levels_detectors counts 45 there, not 46.
- Many bias_htf specs are research studies (`study.py` / `htf.py`) for the swing and position models that are parked under M17, not live `run_day` branches.

## Open points raised by the topic writers

- **Possible owner conflict** (definitions item 20, N-opposing-fvg-speed-bump): ICT treats an opposing FVG between price and the draw as a speed bump. Owner directive #7 instead uses an overhead 15m FVG as resistance (`htf_resist_cap`). This is a question for the owner.
- **Defaults that are not off** (definitions): `ts_skip_reswept=True` (item 53), `ir_need_draw=True` / `ir_need_window=True` (item 86, opt-in IR paths only), `ifvg_depth` becomes modes (item 121), and `bpr_limit` (item 2) defaults to the current `bpr_abort`.
- **Code issue, off-Friday NFP** (day_selection, N2-nfp-date-from-calendar): `strategy.blocked()` treats Thursday as the day before NFP, so 2025-07-03, 2025-11-20 and 2025-12-16 block the wrong days.
- **Missing calendars** (day_selection): jobless claims and FOMC minutes dates are not in `calendar.py`.
- **Section 3 correction** (times item 27, M9-fomc-1430): M9.2's 14:25 becomes 14:30, because no source for 14:25 was found.
- **Shared helpers to build first:** management_exits `pos_r`, `raise_stop`, `partial_close`, `pos["trade_mode"]`, and targets_partials `exit_px_mode`. From session_day_week_stops_frequency: the `week` state dict, `state["idea"]`, `setups.reentry_ok` and `state["day_net"]`.
- **Deferred:** definitions items 196, 197 and 199 need a multi-day or swing engine.
