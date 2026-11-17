"""ICT's opening range gap rule: premium gap -> short to the half gap, discount gap -> long, in the first 30 minutes."""
import numpy as np, pandas as pd
from feat import Mkt, plain_px
rows = []
for s in ("NQ", "ES"):
    m = Mkt(s)
    for j, d in enumerate(m.dates):
        if d.year < 2019 or j < 25 or not np.isfinite(m.adr[j]) or not np.isfinite(m.settle[j - 1]):
            continue
        gap = m.o930[j] - m.settle[j - 1]
        if gap == 0:
            continue
        sg = -int(np.sign(gap)); mid = m.settle[j - 1] + gap / 2
        r = dict(sym=s, date=d, gap=gap / m.adr[j], gap_pct=abs(gap) / m.raw[m.ix(m.days[j], 570)] * 100, side=sg)
        for name, kw in dict(half_1000=dict(end=600, tgt_px=mid), half_1130=dict(end=690, tgt_px=mid), half_1200=dict(end=720, tgt_px=mid),
                             r2_1200=dict(end=720, tgt_r=2.0), r2_1000=dict(end=600, tgt_r=2.0),
                             full_1200=dict(end=720, tgt_px=m.settle[j - 1])).items():
            r[name], r[name + "_why"] = plain_px(m, d, 570, sg, **kw)
        i0, i1 = m.ix(m.days[j], 570), m.ix(m.days[j], 600)
        r["hit_half_1000"] = int((m.l[i0:i1].min() <= mid) if gap > 0 else (m.h[i0:i1].max() >= mid))
        r["mv1000"] = (m.o[i1] - m.o[i0]) * sg / m.adr[j]
        rows.append(r)
pd.DataFrame(rows).to_csv("out/gap.csv", index=False)
