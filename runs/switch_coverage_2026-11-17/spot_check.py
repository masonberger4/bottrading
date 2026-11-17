"""Spot-check table: each variant against the saved 'week rule off' base (5m, ES+NQ+YM, 2019-26, true $1k risk).
Usage: python spot_check.py OUTDIR BASEDIR name ...   'bad' = trades whose stop is on the profit side of the entry."""
import pandas as pd, numpy as np, glob, sys, warnings
warnings.filterwarnings('ignore')
out, base, names = sys.argv[1], sys.argv[2], sys.argv[3:]
def load(d, v):
    fs = glob.glob(f'{d}/trades_*_{v}_20*.csv')
    t = pd.concat([pd.read_csv(f) for f in fs if len(open(f).readline()) > 2], ignore_index=True)
    t['bad'] = (t.side.map({'long': 1, 'short': -1}) * (t.entry - t.stop) <= 0)
    t['h'] = np.where(t.year <= 2022, 'a', 'b'); t['wk'] = pd.to_datetime(t.date).dt.to_period('W').astype(str)
    return t, len(fs)
def st(x):
    return f"{x.mean():+.2f} ({x.mean() / x.std() * len(x) ** .5:+.1f})" if len(x) > 2 else 'n/a'
B, _ = load(base, 'wd_off')
print(f"{'variant':10s} {'files':>5s} {'trades':>6s} {'bad':>4s} {'bad R':>7s} | clean trades: {'n':>5s} {'total $':>9s} {'R/trade (t)':>14s} {'2019-22':>14s} {'2023-26':>14s} {'ES':>7s} {'NQ':>7s} {'YM':>7s} {'vs base wk t':>12s}")
def row(v, t, n):
    c = t[~t.bad]; bw = B.groupby('wk').R.sum(); cw = c.groupby('wk').R.sum(); d = cw.sub(bw, fill_value=0)
    m = c.groupby('market').R.sum()
    print(f"{v:10s} {n:5d} {len(t):6d} {int(t.bad.sum()):4d} {t.R[t.bad].sum():+7.1f} | {'':13s} {len(c):5d} {c.net.sum():9,.0f} {st(c.R):>14s} {st(c.R[c.h == 'a']):>14s} {st(c.R[c.h == 'b']):>14s} {m.get('ES', 0):+7.0f} {m.get('NQ', 0):+7.0f} {m.get('YM', 0):+7.0f} {(d.mean() / d.std() * len(d) ** .5 if v != 'base' else 0):+12.1f}")
row('base', B, 24)
for v in names:
    try:
        t, n = load(out, v); row(v, t, n)
    except Exception as e:
        print(v, 'not ready', e)
