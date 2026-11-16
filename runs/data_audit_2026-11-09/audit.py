import sys, numpy as np, pandas as pd
sys.path.insert(0, ".worktrees/scb")
NY = "America/New_York"; D = "data/mentorship/"
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 400)
raw = pd.read_parquet(D + "ES_1min_dbraw.parquet"); adj1 = pd.read_parquet(D + "ES_1min_db.parquet")
f5 = pd.read_parquet(D + "ES_5min_db.parquet"); m1 = pd.read_parquet(D + "ES_1min_dbmeta.parquet"); m5 = pd.read_parquet(D + "ES_5min_dbmeta.parquet")
P = lambda *a: print(*a, flush=True)

P("== A. fresh rebuild from the Databento downloads vs the parquet")
import databento as db
from mentorship.databento_extra import minute_history
from mentorship.databento_data import back_adjust
fr = db.DBNStore.from_file(D + "databento/ES_ohlcv1m.dbn.zst").to_df()
fr.index = pd.DatetimeIndex(fr.index).tz_convert(NY)
fr = fr[["open", "high", "low", "close", "volume", "instrument_id"]].sort_index(); fr = fr[~fr.index.duplicated(keep="last")]
old = minute_history("ES"); fr = pd.concat([old[old.index < fr.index[0]], fr])
P("rebuild rows", len(fr), "parquet rows", len(raw), "index equal", fr.index.equals(raw.index))
j = raw.join(fr, rsuffix="_f", how="outer")
for c in ["open", "high", "low", "close", "volume"]:
    P(c, "max abs diff", (j[c] - j[c + "_f"]).abs().max(), "nan mismatch", (j[c].isna() != j[c + "_f"].isna()).sum())
P("instrument_id equal", (m1.instrument_id.values == fr.instrument_id.reindex(m1.index).values).mean())
ba = back_adjust(fr)
for c in ["open", "close"]:
    P("adjusted", c, "max diff vs engine", (ba[c].reindex(adj1.index) - adj1[c]).abs().max())

P("\n== B. index integrity")
for n, x in [("raw1", raw), ("adj1", adj1), ("adj5", f5)]:
    P(n, "unique", x.index.is_unique, "monotonic", x.index.is_monotonic_increasing, "NaN rows", x.isna().any(axis=1).sum())
P("5m stamps on 5-min grid", (f5.index.minute % 5 == 0).all(), "seconds==0", (adj1.index.second == 0).all())

P("\n== C. bad prices (raw 1m)")
r = raw
px = r[["open", "high", "low", "close"]]
P("nonpositive", (px <= 0).any(axis=1).sum())
P("high<low", (r.high < r.low).sum(), "high<max(o,c)", (r.high < px[["open", "close"]].max(axis=1) - 1e-9).sum(),
  "low>min(o,c)", (r.low > px[["open", "close"]].min(axis=1) + 1e-9).sum())
P("off 0.25 tick", (((px * 4) % 1) > 1e-6).any(axis=1).sum())
P("zero volume", (r.volume <= 0).sum())
same = m1.instrument_id.eq(m1.instrument_id.shift())
ret = (r.close / r.close.shift() - 1)[same]
rng = (r.high - r.low) / r.close
nxt = r.close.shift(-1) / r.close - 1
spk = ret[ret.abs() > 0.01]
P("1m close-to-close moves >1% (same contract):", len(spk))
nx = nxt.reindex(spk.index)
rev = spk[(np.sign(nx) == -np.sign(spk)) & (nx.abs() > 0.7 * spk.abs())]
P("  of which reversed >70% next bar (spike-like):", len(rev))
P(pd.DataFrame({"ret": spk, "next": nx, "range": rng.reindex(spk.index)}).round(4).to_string())
big = rng[rng > 0.015]; P("1m bars with range >1.5%:", len(big)); P(big.round(4).to_string())
w = (r.high - px[["open", "close"]].max(axis=1)) / r.close; lw = (px[["open", "close"]].min(axis=1) - r.low) / r.close
P("wicks >0.5% beyond body:", int((w > 0.005).sum() + (lw > 0.005).sum()))
P(pd.concat([w[w > 0.005], -lw[lw > 0.005]]).sort_index().round(4).to_string())

P("\n== D. sessions, DST, halts (NY time)")
t = r.index.hour * 60 + r.index.minute; wd = r.index.weekday
P("bars 17:00-17:59 Mon-Fri:", int(((t >= 1020) & (t < 1080) & (wd < 5)).sum()), "Saturday bars:", int((wd == 5).sum()),
  "Sunday before 18:00:", int(((wd == 6) & (t < 1080)).sum()))
odd = r[(t >= 1020) & (t < 1080) & (wd < 5)]
P("17:xx bars by date:", odd.groupby(odd.index.date).size().to_dict())
sun = r[wd == 6]; fs = sun.groupby(sun.index.date).apply(lambda g: g.index[0].strftime("%H:%M"))
P("Sunday first-bar time counts:", fs.value_counts().to_dict())
day = r.index.normalize(); v = r.volume
def vol_at(m):
    s = t == m
    return v[s].groupby(day[s]).sum()
ratio = (vol_at(570) / vol_at(569)).dropna(); alt = (vol_at(630) / vol_at(629)).dropna(); alt2 = (vol_at(510) / vol_at(509)).dropna()
dst = pd.Series([d.dst() != pd.Timedelta(0) for d in ratio.index], index=ratio.index)
P("median vol(09:30)/vol(09:29): EDT", round(ratio[dst].median(), 2), "EST", round(ratio[~dst].median(), 2),
  "| days ratio<1.5:", int((ratio < 1.5).sum()), "of", len(ratio))
P("median vol(10:30)/vol(10:29):", round(alt.median(), 2), "| vol(08:30)/vol(08:29):", round(alt2.median(), 2))
lowr = ratio[ratio < 1.5]; P("days with no 09:30 surge:", [str(d.date()) for d in lowr.index][:80])
# DST week check: the week after each US DST switch vs the week before (Europe switches later, a 1h-off feed would show here)
mid = r[(t >= 975) & (t < 990) & (wd < 5)]; P("bars 16:15-16:29 by year:", mid.groupby(mid.index.year).size().to_dict())

P("\n== E. missing days and RTH gaps (raw 1m)")
rt = r[(t >= 570) & (t < 960)]; per = rt.groupby(rt.index.date).size()
alld = pd.bdate_range("2016-01-04", "2026-10-16")
nob = [d.date() for d in alld if d.date() not in per.index]
P("weekdays with NO RTH bars:", len(nob)); P([str(d) for d in nob])
part = per[per < 390]; P("RTH days with <390 1m bars:", len(part), "| <351 (fails engine 90% rule):", int((per < 351).sum()))
P("distribution of missing RTH minutes:", pd.cut(390 - per, [-1, 0, 1, 5, 20, 39, 389]).value_counts().sort_index().to_dict())
P("days with >=1 missing RTH minute, by year:", part.groupby(pd.to_datetime(pd.Series(part.index)).dt.year.values).size().to_dict())
lastb = rt.groupby(rt.index.date).apply(lambda g: g.index[-1].hour * 60 + g.index[-1].minute)
short = per[(per < 351) | (lastb < 959)]
P("days excluded by engine days() (<90% RTH or ends before 15:59):", len(short)); P(", ".join(f"{d}:{n}" for d, n in short.items()))
gaps = rt.index.to_series().groupby(rt.index.date).apply(lambda s: s.diff().max())
gg = gaps[gaps >= pd.Timedelta("5min")]
P("RTH days with an internal gap >=5 min:", len(gg)); P(gg.astype(str).to_string())
gd = r.index.to_series().diff()
bad = gd[(gd > pd.Timedelta("30min")) & ~((r.index.hour == 18) & (r.index.minute == 0))]
P("globex gaps >30min not ending at 18:00:", len(bad)); P(bad.astype(str).to_string()[:8000])

P("\n== F. rollovers")
iid = m1.instrument_id; ch = iid.ne(iid.shift()) & iid.shift().notna()
rolls = iid[ch]; P("instrument changes:", len(rolls))
seq = pd.concat([iid.iloc[:1], rolls])
P("distinct contracts:", iid.nunique(), "| returns to an earlier id:", int(seq.duplicated().sum()))
rd = pd.DataFrame({"from": iid.shift()[ch].astype(int), "to": rolls})
rd["new_open_minus_old_close"] = (r.open.values[ch.values] - r.close.shift().values[ch.values]).round(2)
rd["adj_step"] = (m1.adj.shift()[ch] - m1.adj[ch]).round(2)
def third_fri(d):
    m = d.month + (-d.month % 3); y = d.year
    if m > 12: m -= 12; y += 1
    fr_ = [x for x in pd.date_range(pd.Timestamp(y, m, 1), periods=21) if x.weekday() == 4][2]
    if fr_ < d: return third_fri(pd.Timestamp(y, m, 1) + pd.DateOffset(months=3))
    return fr_
rd["days_to_expiry"] = [(third_fri(pd.Timestamp(i.date())) - pd.Timestamp(i.date())).days for i in rd.index]
rd["wkday"] = rd.index.day_name().str[:3]
P(rd.to_string())
k = adj1.close - raw.close; seg = ch.cumsum()
P("adj constant within contracts:", bool((k.groupby(seg.values).agg(lambda s: s.max() - s.min()) < 1e-6).all()),
  "| meta adj vs adj-raw max diff:", float((k - m1.adj).abs().max()))
P("cumulative back-adjust at 2016 start:", round(float(m1.adj.iloc[0]), 2))

P("\n== G. 5m bars vs fresh resample of 1m")
g = adj1.groupby(adj1.index.floor("5min"))
rs = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(), "volume": g.volume.sum()})
P("rows", len(rs), len(f5), "index equal", rs.index.equals(f5.index))
for c in rs:
    P(c, "max abs diff", float((rs[c] - f5[c]).abs().max()))
P("5m meta adj vs last 1m adj:", float((m1.adj.groupby(m1.index.floor("5min")).last() - m5.adj).abs().max()))
P("5m bars mixing two contracts:", int(m1.instrument_id.groupby(m1.index.floor("5min")).nunique().gt(1).sum()))
