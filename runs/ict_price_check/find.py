"""Find bars (any TF in 1,2,3,5,15,60) on a session date whose OHLC equals the given header values.
usage: find.py YYYY-MM-DD O H L C [sym]"""
import sys
import pandas as pd
sym = sys.argv[6] if len(sys.argv) > 6 else 'ES'
D = 'C:/Users/mason/bottrading/data/mentorship/'
if sym == 'ES':
    r = pd.read_parquet(D + 'ES_1min_dbraw.parquet')
else:  # no raw parquet: unadjust the engine series
    r = pd.read_parquet(D + f'{sym}_1min_db.parquet')[['open', 'high', 'low', 'close']]
    r = r.sub(pd.read_parquet(D + f'{sym}_1min_dbmeta.parquet').adj, axis=0)
d = pd.Timestamp(sys.argv[1], tz='America/New_York')
x = r[(r.index >= d - pd.Timedelta(hours=30)) & (r.index < d + pd.Timedelta(hours=24))]
o, h, l, c = map(float, sys.argv[2:6])
for tf in (1, 2, 3, 5, 15, 60):
    b = x.resample(f'{tf}min', offset='0min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    hit = b[(b.open == o) & (b.high == h) & (b.low == l)]
    for t, row in hit.iterrows():
        print(f'tf={tf} {t} C={row.close} {"exact" if row.close == c else "C differs"}')
