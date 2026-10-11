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
