# Ideas parked for later

## After all mentorship transcripts are uploaded

- **Swing version on 1-hour / 4-hour / daily bars.** Same pattern as the intraday model
  (sweep of the previous day's or week's high/low, structure break, FVG entry) with no
  session window, holding for days, targeting the previous week's high/low. The current
  transcripts (Ep 01-08) only teach intraday trades, so build this from whatever the later
  episodes say about swing/position trading rather than guessing. Use the weekly range
  objective ("once the weekly objective is delivered, stop for the week") as well.
  Data: HistData SPX/NDX 1-minute since 2019, resampled; trade SPY/QQQ.
- **Re-test new rules on the same 2019-2026 data** (`study.py`) so results stay comparable.
- **Forward paper test of the 5-minute AM model** on live Schwab bars (paper.py, simulated
  fills only): the backtest's +0.50R over 100 trades is not yet trustworthy (top 5 trades
  carry it; 1-minute loses; many variants tried).
