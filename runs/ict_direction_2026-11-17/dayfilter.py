"""Option C: how he picks the day and the moment. Day filters from what he says on his no-trade days, and the
'kind of call' condition (trade only back across the overnight range), tested on his days and on every day."""
import glob, numpy as np, pandas as pd
from feat import Mkt
V = ['s_settle', 's_first', 's_gapcl', 's_req']
out = open("out/report_c.txt", "w")
def P(*a):
    print(*a); print(*a, file=out)
def st(x, money=True):
    x = x.dropna(); n = len(x)
    if n < 6: return f"{n:5d}" + " " * 45
    e = (x * 1000).cumsum()
    return f"{n:5d} {x.mean():+.3f} t={x.mean() / x.std() * np.sqrt(n):+.1f} ${1000 * x.sum():>8,.0f} DD ${min((e - e.cummax()).min(), 0):>8,.0f}"

d = pd.read_csv('out/days.csv', parse_dates=['date']); d['half'] = np.where(d.date.dt.year <= 2022, '19-22', '23-26')
news = pd.read_csv("/mnt/project-files/mentorship/data/macro_risk_dates.csv", comment="#", parse_dates=['date'])
tags = news.groupby('date').tag.apply(set)
for k in ('nfp', 'cpi', 'fomc', 'ppi', 'holiday_eve'):
    d['c_' + k] = d.date.map(lambda x: int(k in tags.get(x, ())))
d['c_news'] = d[['c_nfp', 'c_cpi', 'c_fomc', 'c_ppi']].max(axis=1)
# previous day's range and the overnight range, in ADR
ex = []
for s in ('NQ', 'ES'):
    m = Mkt(s)
    for j, dt in enumerate(m.dates):
        if dt.year < 2019 or j < 25: continue
        a, b = m.ix(m.days[j], -360), m.ix(m.days[j], 570)
        ex.append(dict(sym=s, date=pd.Timestamp(dt), prev_rng=m.rth[j - 1] / m.adr[j], on_rng=(m.h[a:b].max() - m.l[a:b].min()) / m.adr[j] if b > a else np.nan))
d = d.merge(pd.DataFrame(ex), on=['sym', 'date'], how='left')
d['c_prev_big'] = (d.prev_rng > 1.5).astype(int); d['c_small_gap'] = (d.gap.abs() < 0.10).astype(int)
d['c_on_big'] = (d.on_rng > 0.8).astype(int); d['c_fri'] = (d.date.dt.dayofweek == 4).astype(int)
d['vote'] = d[V].fillna(0).sum(axis=1); d['side'] = np.sign(d.vote)
d['R'] = np.where(d.vote > 0, d.R_long, np.where(d.vote < 0, d.R_short, np.nan))
d['ext'] = np.where(d.side > 0, d.on_pos, 1 - d.on_pos)            # 0 = far side of the overnight range from the read's target
FL = ['c_news', 'c_nfp', 'c_cpi', 'c_fomc', 'c_ppi', 'c_holiday_eve', 'c_fri', 'c_prev_big', 'c_small_gap', 'c_on_big']

# ---- 1. his call days against his stated no-trade days
c = pd.read_csv('out/calls_feats.csv', parse_dates=['date']); c = c[(c.same_day == 1) & (c.new == 0)]  # the calls report_c.txt was built on
call = set(zip(c.sym, c.date))
nt = pd.concat([pd.read_csv(f, sep='|') for f in sorted(glob.glob('../ict_calls_2026-11-17/nocall_20??.csv'))])
nt = nt[nt.kind == 'no trade']; nt['date'] = pd.to_datetime(nt.date); nt['sym'] = np.where(nt.date.dt.year == 2023, 'ES', 'NQ')
notr = set(zip(nt.sym, nt.date)) - call
x = d[(d['T'] == 570) & (d.half == '23-26')].copy()
x['grp'] = [('call' if k in call else 'no-trade' if k in notr else 'other') for k in zip(x.sym, x.date)]
P("== 1. Share of days with each condition: his call days / his stated no-trade days / all other days 2023-26")
P(f"   days: {dict(x.grp.value_counts())}")
for f in FL:
    g = x.groupby('grp')[f].mean(); P(f"   {f:14s} call {g.get('call', np.nan):4.0%}  no-trade {g.get('no-trade', np.nan):4.0%}  other {g.get('other', np.nan):4.0%}")
for f in ('prev_rng', 'on_rng'):
    g = x.groupby('grp')[f].median(); P(f"   {f:14s} median  call {g['call']:.2f}  no-trade {g['no-trade']:.2f}  other {g['other']:.2f}")
x['gabs'] = x.gap.abs(); g = x.groupby('grp').gabs.median(); P(f"   |gap|          median  call {g['call']:.2f}  no-trade {g['no-trade']:.2f}  other {g['other']:.2f}")
x['skip'] = x[['c_news', 'c_holiday_eve', 'c_prev_big', 'c_small_gap']].max(axis=1)
g = x.groupby('grp').skip.mean(); P(f"   any of news / holiday eve / day after a big range / small gap: call {g['call']:.0%}  no-trade {g['no-trade']:.0%}  other {g['other']:.0%}")

# ---- 2. the read on every day with each condition on and off
P("\n== 2. The read on every day ($1k risk): trades, R a trade, t, total, max drawdown.  2019-22 | 2023-26")
d['c_skip'] = d[['c_news', 'c_holiday_eve', 'c_prev_big', 'c_small_gap']].max(axis=1)
for T in (570, 600):
    for sym in ('NQ', 'ES'):
        y = d[(d['T'] == T) & (d.sym == sym)].sort_values('date')
        P(f"-- {sym} entry {T // 60:02d}:{T % 60:02d}")
        P("   all days                   ", ' | '.join(st(y.R[y.half == h]) for h in ('19-22', '23-26')))
        for f in ['c_news', 'c_fri', 'c_prev_big', 'c_small_gap', 'c_on_big', 'c_skip']:
            for v in (1, 0):
                P(f"   {f:12s} {'yes' if v else 'no '}           ", ' | '.join(st(y.R[(y.half == h) & (y[f] == v)]) for h in ('19-22', '23-26')))
        for lo, hi, nm in ((0, .33, 'back across the range  '), (.33, .67, 'from the middle        '), (.67, 1.01, 'toward the extreme     ')):
            P(f"   read is {nm}    ", ' | '.join(st(y.R[(y.half == h) & (y.ext >= lo) & (y.ext < hi)]) for h in ('19-22', '23-26')))
        k = (y.ext < .33) & (y.c_skip == 0)
        P("   back across + none of his skip conditions", ' | '.join(st(y.R[(y.half == h) & k]) for h in ('19-22', '23-26')))
out.close()

# ---- 3. the one combination positive in all four cells: the read at 09:30 on days with none of his skip conditions
out = open("out/report_c.txt", "a")
P("\n== 3. The read at 09:30, days with none of his skip conditions, by day (NQ and ES averaged) and by year")
y = d[(d['T'] == 570) & (d.c_skip == 0)]
z = y.groupby('date').R.mean().dropna()
for a, b in ((2019, 2022), (2023, 2026), (2019, 2026)):
    q = z[(z.index.year >= a) & (z.index.year <= b)]; P(f"   {a}-{b}: {len(q)} days, {q.mean():+.3f} R a day, t={q.mean() / q.std() * np.sqrt(len(q)):+.1f}")
P(y.assign(y=y.date.dt.year).pivot_table(index='y', columns='sym', values='R', aggfunc='mean').round(3).T.to_string())
y = d[(d['T'] == 570) & (d.c_skip == 1)]; z = y.groupby('date').R.mean().dropna()
P(f"   the skipped days, 2019-26: {len(z)} days, {z.mean():+.3f} R a day, t={z.mean() / z.std() * np.sqrt(len(z)):+.1f}")
out.close()
