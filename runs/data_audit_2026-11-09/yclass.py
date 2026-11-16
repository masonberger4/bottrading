import pandas as pd, yfinance as yf
NY = "America/New_York"; D = "data/mentorship/"
raw = pd.read_parquet(D + "ES_1min_dbraw.parquet"); m1 = pd.read_parquet(D + "ES_1min_dbmeta.parquet"); raw["iid"] = m1.instrument_id
y = yf.download("ES=F", start="2016-01-01", end="2026-10-17", interval="1d", auto_adjust=False, progress=False)
if isinstance(y.columns, pd.MultiIndex): y.columns = y.columns.get_level_values(0)
y.index = pd.to_datetime(y.index).date
sd = (raw.index + pd.Timedelta(hours=6)).date; g = raw.groupby(sd)
es = pd.DataFrame({"h": g.high.max(), "l": g.low.min(), "n": g.iid.nunique()})
j = es.join(y[["High", "Low"]], how="inner"); j = j[j.n == 1]
d = (j.h - j.High).abs().combine((j.l - j.Low).abs(), max); bad = j[d > 5]
rolls = m1.index[m1.instrument_id.ne(m1.instrument_id.shift()) & m1.instrument_id.shift().notna()]
rolldays = set()
for r in rolls:
    s = (r + pd.Timedelta(hours=6)).normalize().tz_localize(None)
    for k in range(0, 8): rolldays.add((s + pd.Timedelta(days=k)).date())
bd = pd.Series(sorted(es.index)); prev = dict(zip(bd[1:], bd[:-1]))
def cls(day):
    if day in rolldays: return "roll week (Yahoo stays on the expiring contract)"
    p = prev.get(day)
    if p and (pd.Timestamp(day) - pd.Timestamp(p)).days >= 1 and pd.Timestamp(p).weekday() < 5 and es.loc[p, "h"] and day not in y.index: return "x"
    if p and p not in y.index: return "day after a holiday session (Yahoo merges it)"
    return "other"
bad = bad.assign(cls=[cls(x) for x in bad.index], dh=(bad.h - bad.High).round(2), dl=(bad.l - bad.Low).round(2))
print(bad.cls.value_counts().to_string())
print(bad[bad.cls == "other"][["h", "High", "l", "Low", "dh", "dl"]].to_string())
