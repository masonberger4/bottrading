# What ICT cites when he picks a side and a day

Source: `mentorship/digests/bias.md` (rule ids B1-B68, built from all 218 notes), `filters.md`, `times.md`. Each row is
a thing he says he looks at before trading, the column in `out/days.csv` that stands for it, and how faithful that
column is. All columns use only what is known at 09:30 New York. Signed columns: + = bullish.

## Side (direction)

| What he cites | Rule | Column | Note |
|---|---|---|---|
| Premium / discount of the 20-day range | B31, B35 | `s_pd20` | discount = +; wicks |
| Same, 60-day range | B33 | `s_pd60` | |
| Draw on liquidity: the nearer 20-day high or low | B1, B34 | `s_draw20` | distance, in ADR |
| Daily order flow (highs or lows being closed through) | B13, B19 | `s_iof5` | simplified: 5-day count of closes beyond the prior day's high minus low |
| Prior day's candle | B13 | `s_pday` | |
| No longs after 3 up closes, mirror | B28 | `s_3close` | |
| Down-close outside day means lower | B28 | `s_outside` | |
| Nearest open daily fair value gap as the draw | B1, B2, B30 | `s_fvg_d` | 60-day look-back, closeness-weighted |
| Weekly direction (closes through the prior week's high or low) | B3, B23 | `s_wk_iof`, `s_wk_last` | 4-week count; last week's candle |
| Above or below the week's opening price | B37 | `s_wk_open` | Sunday 18:00 open |
| Previous week's high or low as the draw | B44, B48 | `s_pw_draw` | |
| Above or below the midnight open | B36 | `s_mid` | |
| Above or below the 08:30 open | B36 | `s_830` | |
| Opening range gap (16:15 close to 09:30 open) | B43 | `s_org` | |
| Above or below the new week opening gap | B40, B41 | `s_nwog` | Friday close to Sunday open, mid-point |
| Overnight ran yesterday's low (buy) or high (sell) | B13, B20 | `s_pre_raid` | |
| Where 09:30 sits in the Asia + London range | B36 | `s_lon_pos` | |
| London took the Asia high or low (Judas side) | B11 | `s_lon_dir` | |
| Index SMT: one of ES/NQ/YM refuses the others' overnight break | B51 | `s_smt` | against yesterday's high and low only |
| Seasonal month map | B63, C10 | `s_seas`, `s_seas_agreed` | all stated months; only months every source agrees on |
| COT commercial hedging program (12-month midpoint) | B60 | `s_cot` | legacy report, usable from the Monday after release |
| Sentiment: Williams %R | B62 | `s_wr15` | daily 15-period; headlines not codable |
| Dollar as risk barometer | B55 | `s_dxy` | 5-day change, sign flipped; spot file ends 2025 |
| Bonds with stocks | B57 | `s_zb` | 30-year future, 5-day change |
| 9-18 month trend (quarterly shift context) | B27 | `s_trend250` | |

## Day (trade today or pass)

| What he cites | Rule | Column |
|---|---|---|
| Day of week (Monday, Friday rules) | B8, B44 | `c_dow` |
| NFP, CPI, FOMC, PPI days; other mid-tier releases | filters | `c_nfp`, `c_cpi`, `c_fomc`, `c_ppi`, `c_mid_news`, `c_news830` |
| NFP and FOMC weeks | filters | `c_nfp_week`, `c_fomc_week` |
| Day before a holiday; rollover week | filters | `c_holiday_eve`, `c_roll_week` |
| Day after a range over 2x ADR is chop | B28 | `c_prev_rng` |
| Inside day means expansion next | B28 | `c_inside` |
| Range regime, multi-day sideways box | B49 | `c_regime`, `c_consol5` |
| Overnight already used the day's range | B8 | `c_pre_rng` |
| Size of the opening gap | B43 | `c_gap_abs` |
| Distance to the nearer 20-day pool | B34 | `c_pool_dist` |
| Overnight ran both sides, or neither, of yesterday | B46 | `c_pre_both`, `c_pre_none` |
| SMT both ways at once: do not trade | B52 | `c_smt_both` |
| Weekly objective already delivered | B48 | `c_wk_obj`, `c_wk_used` |
| "If both sides can be framed, skip" | B47 | `c_agree` (how one-sided the signed columns are) |
| Month, week and day pointing the same way | B25 | `c_htf_agree` |

## Outcomes (never inputs)

`o_am` 09:30 to 11:30, `o_day` 09:30 to 16:00, `o_big` side of the day's largest move from the open (B11), `o_am_rng`
morning range, `o_am_eff` how one-way the morning was. All in ADR units.

## Cited but not coded here

- "Narrative", "obvious" arrays, which of several draws he means on the day (B12, B33 parent range): by eye.
- Order-block validity and mean-threshold closes (B14-B16), three-array invalidation, breaker precedence (B38), MWD
  cases A/B/C (B25): the engine has versions of these; option A scores them and they join through `--a-cols`.
- Weekly profile choice (B44), TGIF (B45), IPDA cast-forward windows (B34): need a judgement on where the week is.
- Headlines and "big story" sentiment (B62), open interest at an HTF array (B61, roll distorts it), gold and CRB (B56,
  B58): no data in the pipeline.
- What he sees after 09:30 (the reaction on 15 s to 1 m charts): by design not in a 09:30 table. PR #82 names this as
  the least codable part.
