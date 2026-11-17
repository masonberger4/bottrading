"""Scores the features in out/days.csv and out/calls_feats.csv. Writes out/report.txt."""
import sys, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
F = ['s_gap', 's_req', 's_sweep', 's_first', 's_onpos', 's_settle', 's_mid_rev', 's_oldgap', 's_gapcl', 's_judas', 's_830fade']
V = ['s_settle', 's_first', 's_gapcl', 's_req']           # the four that lean his way most; the "read"
out = open("out/report.txt", "w")
def P(*a):
    print(*a); print(*a, file=out)
def st(x, money=False):
    x = x.dropna(); n = len(x)
    if n < 6: return f"{n:5d}"
    s = f"{n:5d} {x.mean():+.3f} t={x.mean() / x.std() * np.sqrt(n):+.1f}"
    if money:
        e = (x * 1000).cumsum(); s += f" ${1000 * x.sum():>9,.0f} maxDD ${min((e - e.cummax()).min(), 0):>9,.0f}"
    return s

c = pd.read_csv('out/calls_feats.csv', parse_dates=['date']); c = c[c.new == 0]  # the 114 calls the read was built on; new ones are in analyze_new.py
s = c[(c.same_day == 1) & c.p.notna()].sort_values(['date', 'T']).copy()
P(f"== 1. His calls: {len(c)} one-sided calls, {len(s)} same-day calls between 07:00 and 15:00 with data. Right at his horizon {s.win.mean():.0%}, long {np.mean(s.side > 0):.0%}")
P("feature      days it has a side / points his way / he was right when it agreed / when it did not")
for f in F:
    v = s[f].fillna(0); nz = v != 0; ag = (v == s.side) & nz
    P(f"{f:10s} {nz.sum():3d}  {ag.sum() / max(nz.sum(), 1):5.0%}  {s.win[ag].mean():.0%}  {s.win[nz & ~ag].mean():.0%}")
X = s[F].fillna(0).to_numpy(); y = (s.side > 0).astype(int).to_numpy(); days = s.date.to_numpy(); pred = np.zeros(len(s))
for C in (0.03, 0.1, 0.3):
    for d in np.unique(days):
        te = days == d; pred[te] = LogisticRegression(C=C, fit_intercept=False).fit(X[~te], y[~te]).decision_function(X[te])
    P(f"model on all 11, each day predicted from the others (penalty C={C}): his side on {np.mean((pred > 0) == (y == 1)):.0%} of {len(s)}")
s['vote'] = s[V].fillna(0).sum(axis=1); s['ag'] = np.sign(s.vote) == s.side
P(f"the read (sum of {V}): his side on {s.ag.mean():.0%} of {len(s)}; he was right {s.win[s.ag].mean():.0%} when it agreed ({s.ag.sum()}), {s.win[~s.ag].mean():.0%} when not ({(~s.ag).sum()})")
rng = np.random.default_rng(0); w = s.win.to_numpy(); g = s.ag.to_numpy(); obs = w[g].mean() - w[~g].mean()
sim = np.array([(lambda p: w[p].mean() - w[~p].mean())(rng.permutation(g)) for _ in range(20000)])
P(f"   that gap ({obs:+.0%}) arises by chance in {np.mean(sim >= obs):.1%} of shuffles")
m = s[s['T'] < 690]
P("his side, plain entry (stop 0.25% NQ / 0.21% ES, 2R, flat 12:00), $1k risk: trades, R a trade, t, total, max drawdown")
P("   all morning calls      ", st(m.R_his, 1)); P("   the read agrees        ", st(m.R_his[m.ag], 1)); P("   the read disagrees     ", st(m.R_his[~m.ag], 1))
s['ext'] = np.where(s.side > 0, s.on_pos, 1 - s.on_pos)
P("where price sits in the overnight range when he calls (0 = far side from his target, 1 = already at the side he calls):")
for lo, hi in ((0, .33), (.33, .67), (.67, 1.01)):
    x = s[(s.ext >= lo) & (s.ext < hi)]; P(f"   {lo:.2f}-{min(hi, 1):.2f}: {len(x):3d} calls, right {x.win.mean():.0%}, plain entry", st(x.R_his, 1))

d = pd.read_csv('out/days.csv', parse_dates=['date']); d['half'] = np.where(d.date.dt.year <= 2022, '19-22', '23-26'); d['y'] = d.date.dt.year
P("\n== 2. Each feature on every day (plain entry on its side). 2019-22 | 2023-26. NQ then ES")
for T in (570, 585, 600):
    P(f"-- entry {T // 60:02d}:{T % 60:02d}")
    for f in F + ['always long']:
        row = f"{f:11s}"
        for sym in ('NQ', 'ES'):
            x = d[(d['T'] == T) & (d.sym == sym)]
            v = x[f].fillna(0) if f in x else pd.Series(1, index=x.index)
            r = pd.Series(np.where(v > 0, x.R_long, np.where(v < 0, x.R_short, np.nan)), index=x.index)
            row += f" {sym} " + ' | '.join(st(r[x.half == h]) for h in ('19-22', '23-26'))
        P(row)
d['vote'] = d[V].fillna(0).sum(axis=1); d['R'] = np.where(d.vote > 0, d.R_long, np.where(d.vote < 0, d.R_short, np.nan))
P("\n== 3. The read on every day, $1k risk: trades, R a trade, t, total, max drawdown")
for T in (570, 585, 600):
    for sym in ('NQ', 'ES'):
        for h in ('19-22', '23-26'):
            x = d[(d['T'] == T) & (d.sym == sym) & (d.half == h)].sort_values('date')
            P(f"{T // 60:02d}:{T % 60:02d} {sym} {h}", st(x.R, 1))
P("R a trade by year (columns: entry time, market)")
P(d.pivot_table(index='y', columns=['T', 'sym'], values='R', aggfunc='mean').round(3).to_string())
cd = set(zip(s.sym, s.date)); d['callday'] = [(a, b) in cd for a, b in zip(d.sym, d.date)]
x = d[d.half == '23-26']
P("the read in 2023-26, on his call days against every other day")
for T in (570, 585, 600):
    y_ = x[x['T'] == T]; P(f"   {T // 60:02d}:{T % 60:02d} call days", st(y_.R[y_.callday]), "| other days", st(y_.R[~y_.callday]))

g = pd.read_csv('out/gap.csv', parse_dates=['date']); g['a'] = g.gap.abs(); g['half'] = np.where(g.date.dt.year <= 2022, '19-22', '23-26')
P("\n== 4. His opening gap rule on every day: short a gap up, long a gap down at 09:30, target the half gap")
P("gap size in ADR: days, half gap reached by 10:00, then R a trade for: half gap by 10:00 | half gap by 12:00 | 2R by 12:00")
for sym in ('NQ', 'ES'):
    for h in ('19-22', '23-26'):
        P(sym, h)
        for lo, hi in [(0, .1), (.1, .2), (.2, .35), (.35, .6), (.6, 1), (1, 99)]:
            x = g[(g.sym == sym) & (g.half == h) & (g.a >= lo) & (g.a < hi)]
            P(f"  {lo:.2f}-{hi:5.2f} {len(x):4d} reached {x.hit_half_1000.mean():4.0%} |", ' | '.join(st(x[k]) for k in ('half_1000', 'half_1200', 'r2_1200')))
out.close()
