"""How much a set's result depends on the estimated call time: shift every same-day call's ref time and rescore."""
import sys, pandas as pd, score
c = pd.read_csv(sys.argv[1], sep='|', dtype=str).fillna('')
c = c[c.end_day == '0']
print('| ref shift (min) | calls | right at horizon end | first to +0.25%% | right at 16:00 |'); print('|---|---|---|---|---|')
for sh in (-30, -15, 0, 15, 30):
    w = []; f = []; dc = []
    for _, r in c.iterrows():
        t = (pd.Timestamp('2000-01-01 ' + r.ref) + pd.Timedelta(minutes=sh)).strftime('%H:%M')
        if t >= r.end: continue
        sym = (r.get('sym', '') or 'NQ')
        o = score.one(sym, r.date, t, r.dir, 0, r.end)
        o2 = score.one(sym, r.date, t, r.dir, 0, '16:00') if t < '16:00' else None
        if o and o2: w.append(o['win_end']); f.append(o['ft']); dc.append(o2['win_end'])
    ff = [x for x in f if x]
    print('| %+d | %d | %d (%.0f%%) | %d of %d | %d (%.0f%%) |' % (sh, len(w), sum(w), 100 * sum(w) / len(w), sum(x > 0 for x in ff), len(ff), sum(dc), 100 * sum(dc) / len(dc)))
