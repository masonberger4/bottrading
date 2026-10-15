# bottrading: ICT Silver Bullet bot

This is a mechanical version of the ICT Silver Bullet model. It runs in Python on the
Schwab Trader API, the API behind thinkorswim.

Rules: entries only in the 3-4am, 10-11am and 2-3pm New York windows. The draw is the
nearest unswept prior-day, prior-week, Asia, London or NY session high/low. A market
structure shift, then a fair value gap, gives a limit entry at the gap edge. The draw
must be at least 10 points away on ES/MES, the target is 5 points, the stop sits beyond
the swing, and everything is flat by 15:55.

Schwab's API can't trade or chart futures, and it can't reach paperMoney. So
`paper` mode trades SPY on live Schwab bars with simulated fills. Real orders need
--live AND SB_ALLOW_LIVE=1. Don't use those yet.

## Commands (Windows, from this folder)

    .venv\Scripts\python -m pytest -q tests
    .venv\Scripts\python -m silver_bullet backtest --synthetic --symbol MES
    .venv\Scripts\python -m silver_bullet backtest --schwab --symbol SPY --days 45 --out spy_trades.csv
    .venv\Scripts\python -m silver_bullet paper --symbol SPY

The Schwab commands need SCHWAB_APP_KEY and SCHWAB_APP_SECRET from a developer.schwab.com
app with the callback URL https://127.0.0.1:8182. The first run opens a browser so you can log in.

Not financial advice.

# Claude HF: intraday stock bot found by a self-improving search

Package `claude_hf`. Trades 40 liquid large-cap stocks (no ETFs) on 1- or 5-minute bars,
holds for minutes, and is flat every night. A retail Schwab API can't do true
microsecond HFT, so this is the fastest version it supports.

The strategy is a genome: two playbooks (signal weights for short-term reversal, momentum,
VWAP distance, opening-range breakout, volume shocks, day return and overnight gap, plus
hold time, slots, threshold, entry window and long/short mode) and a route for every kind
of day (FOMC, CPI, jobs, PCE, PPI, retail sales, GDP, quad witching, ISM, JOLTS, sentiment,
opex, month/quarter turns, futures roll week, weekdays): playbook A, playbook B, or sit out.
Event dates live in `claude_hf/daytypes.py`; extend them each year.

`evolve` splits days in time order into train / validation / test. Each generation mutates
the champion; a change is kept only if it beats the champion on training AND validation
days after 1.5 bps per side of spread/slippage plus the SEC fee. The loop also tunes its own
mutation step sizes and operator choice from what worked. Every generation is logged to
`runs/claude_hf/<N>min/seed<k>/generations.jsonl`. Test days are scored once, at the end.

    .venv\Scripts\python -m claude_hf fetch --minutes 5      # ~9 months of 5-minute bars
    .venv\Scripts\python -m claude_hf evolve --minutes 5 --seeds 5 --save claude_hf\champion.json
    .venv\Scripts\python -m claude_hf paper                  # simulated fills, never sends orders

Paper trades go to `runs/claude_hf/paper_trades.csv`. There is no live mode.

## 2023 Mentorship bot (`mentorship2023/`)

The ICT 2023 Mentorship rules in `mentorship2023_rules.md`, implemented bar-by-bar with no
lookahead (New York time). Paper/backtest only: it has no order-sending code.

- `levels.py`: PD arrays: FVG (BISI/SIBI) with CE, order blocks with mean threshold, breakers,
  volume imbalances, swing pivots, relative equal highs/lows, midnight/08:30/09:30/13:30 opens.
- `strategy.py`: AM (09:30-11:00) and PM (13:30-15:50, last hour 15:15-15:45 tagged) market
  maker models: sweep of previous-3-day / pre-market / AM-session liquidity or relative equal
  levels, structure shift with an FVG, limit at the FVG (unicorn preferred), longs below the
  midnight open (PM: 13:30 open), stop beyond the order block's mean threshold, targets at the
  next liquidity 0.5 ES pt early, half off at T1, flat by 16:00. One AM + one PM trade, no
  reversal after a loss, NFP/FOMC day filter. QQQ is the SMT partner (tagged, not a filter).
- SPY has no overnight bars, so the first pre-market bar (04:00) stands in for the midnight
  open, and previous-day highs/lows are regular-session. 1 ES point = 0.10 SPY.

- Optional rules, each a `Params` switch (off by default): `require_htf` (sweep into an open
  15m/60m FVG; always tagged), `trail` (stop under each new FVG), `adds` (pyramid smaller
  units on new FVGs, 2% total risk cap), `weekly_bias`, `sd_targets` (standard-deviation
  projections of the manipulation leg), `wick_levels` (50% of yesterday's wicks).
  `levels.py` also has rejection blocks and balanced price ranges.
- `backtest.combine` trades one instrument per session (first SPY/QQQ setup to fill).
  `study.py` runs every rule alone and together on SPY, QQQ, the combination and the
  random-walk control. `paper.py` runs on live Schwab bars and logs simulated fills only.
- 5-minute history: extended hours from late March, regular session only back to late
  January (09:30 open stands in for midnight there).

    .venv\Scripts\python -m mentorship2023 fetch
    .venv\Scripts\python -m mentorship2023 backtest --minutes 5
    .venv\Scripts\python -m mentorship2023 synthetic --seeds 5
    .venv\Scripts\python -m mentorship2023.study
    .venv\Scripts\python -m mentorship2023 paper --minutes 1
    .venv\Scripts\python -m pytest -q tests\test_mentorship2023.py
