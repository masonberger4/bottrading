"""Look up unadjusted ES contract prices for ICT chart checks.
usage: lk.py day YYYY-MM-DD            -> CME session (18:00 prev - 17:00) OHLC + contract
       lk.py bar YYYY-MM-DD HH:MM TF   -> OHLC of the TF-minute bar starting at HH:MM ET
       lk.py rng YYYY-MM-DD HH:MM HH:MM -> high/low (and times) between two ET times
"""
import os
import sys
import pandas as pd

D = 'C:/Users/mason/bottrading/data/mentorship/'
SYM = os.environ.get('SYM', 'ES')
m = pd.read_parquet(D + f'{SYM}_1min_dbmeta.parquet')
if SYM == 'ES':
    r = pd.read_parquet(D + 'ES_1min_dbraw.parquet').join(m)
else:  # no raw parquet: unadjust the engine series (raw = adjusted - adj)
    r = pd.read_parquet(D + f'{SYM}_1min_db.parquet')[['open', 'high', 'low', 'close']].join(m)
    for c in ('open', 'high', 'low', 'close'):
        r[c] = r[c] - r.adj
CODES = {3: 'M', 6: 'U', 9: 'Z', 12: 'H'}


def contract(ts):
    rolls = m[m.roll].index
    prev = rolls[rolls <= ts]
    if len(prev) == 0:
        return SYM + 'H6'
    t = prev[-1]
    y = t.year + (1 if t.month == 12 else 0)
    return SYM + CODES[t.month] + str(y)[-1]


def fmt(df):
    return (f"O{df.open.iloc[0]:.2f} H{df.high.max():.2f} L{df.low.min():.2f} C{df.close.iloc[-1]:.2f}"
            f"  hi@{df.high.idxmax():%m-%d %H:%M} lo@{df.low.idxmin():%m-%d %H:%M}"
            f"  {contract(df.index[-1])} adj={df.adj.iloc[-1]}")


cmd = sys.argv[1]
d = pd.Timestamp(sys.argv[2], tz='America/New_York')
if cmd == 'day':
    df = r[(r.index >= d - pd.Timedelta(hours=6)) & (r.index < d + pd.Timedelta(hours=17))]
elif cmd == 'bar':
    s = pd.Timestamp(sys.argv[2] + ' ' + sys.argv[3], tz='America/New_York')
    df = r[(r.index >= s) & (r.index < s + pd.Timedelta(minutes=int(sys.argv[4])))]
else:
    s = pd.Timestamp(sys.argv[2] + ' ' + sys.argv[3], tz='America/New_York')
    e = pd.Timestamp(sys.argv[2] + ' ' + sys.argv[4], tz='America/New_York')
    df = r[(r.index >= s) & (r.index < e)]
print(sys.argv[1:], fmt(df) if len(df) else 'NO DATA')
