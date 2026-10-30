# News-day test summary (N1, N5a, N5b)

Source: `runs/news_test.py`, output `mentorship/digests/news_test_summary.csv` (copy of `runs/news_test_summary.csv`).

## Setup

- Data: 5-minute SPY and QQQ bars, 2019-2026, with the VI default applied.
- Each variant is a `Params()` copy with the switches below. `htf_bias="combo"` is set for N1, N5a and N5b.
- Pair run: SPY on its own bars, QQQ with `es_pt = 0.10 * median(QQQ close) / median(SPY close)`, then `B.combine` with the study pick.
- Baseline: `base_2023_default` (no news switches).

| Variant | Switches |
|---|---|
| base_2023_default | none |
| N1_nfp_release_fvg | `nfp_release_fvg=True`, `htf_bias="combo"` |
| N5a_post_news_continuation | `post_news_continuation=True`, `htf_bias="combo"` |
| N5b_release_ob_entry | `release_ob_entry=True`, `htf_bias="combo"` |

## Run command

```bash
python runs/news_test.py
```

It writes `runs/news_test_summary.csv` and prints `DONE`.

## Result (net, trades)

base -413 (53); N1 -780 (18); N5a -1009 (20); N5b +540 (21, PF 1.16). Only N5b clears the acceptance check.
