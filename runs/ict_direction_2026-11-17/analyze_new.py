"""The two-kinds split of README point 3, on calls logged AFTER the read was built (ids CTE-*, CX-*). Writes out/report_new.txt."""
import numpy as np, pandas as pd
V = ['s_settle', 's_first', 's_gapcl', 's_req']
out = open("out/report_new.txt", "w")
def P(*a):
    print(*a); print(*a, file=out)
def st(x):
    x = x.dropna(); n = len(x)
    if not n: return "    0"
    e = (x * 1000).cumsum()
    return f"{n:3d} trades {x.mean():+.2f}R  ${1000 * x.sum():>7,.0f}  maxDD ${min((e - e.cummax()).min(), 0):>7,.0f}"
c = pd.read_csv('out/calls_feats.csv', parse_dates=['date'])
for name, q in (("NEW calls", c[c.new == 1]), ("OLD calls (for comparison)", c[c.new == 0]), ("ALL calls", c)):
    s = q[(q.same_day == 1) & q.p.notna()].sort_values(['date', 'T']).copy()
    s['vote'] = s[V].fillna(0).sum(axis=1); s['ag'] = np.sign(s.vote) == s.side
    s['ext'] = np.where(s.side > 0, s.on_pos, 1 - s.on_pos)
    P(f"== {name}: {len(q)} logged, {len(s)} same-day 07:00-15:00 with data; right {int(s.win.sum())} of {len(s)}")
    a, b = s[s.ag], s[~s.ag]
    P(f"   read agrees: right {int(a.win.sum())} of {len(a)} | read disagrees: right {int(b.win.sum())} of {len(b)}")
    m = s[s['T'] < 690]
    P("   plain entry, $1k risk  agrees:", st(m.R_his[m.ag]), "| disagrees:", st(m.R_his[~m.ag]))
    for lo, hi, lab in ((0, .33, "back across the overnight range"), (.33, .67, "from the middle third"), (.67, 9, "toward the extreme price is at")):
        x = s[(s.ext >= lo) & (s.ext < hi)]
        P(f"   {lab:32s}: right {int(x.win.sum())} of {len(x)} | plain entry", st(x.R_his))
    if name.startswith("NEW"):
        P(s[['id', 'date', 'sym', 'ref', 'side', 'win', 'vote', 'ag', 'ext', 'R_his']].round(2).to_string(index=False))
out.close()
