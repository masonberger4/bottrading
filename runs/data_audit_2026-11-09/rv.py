import pandas as pd
D="data/mentorship/"
r=pd.read_parquet(D+"ES_1min_dbraw.parquet"); m=pd.read_parquet(D+"ES_1min_dbmeta.parquet")
t=r.index.hour*60+r.index.minute; rt=r[(t>=570)&(t<960)]
v=rt.volume.groupby(rt.index.date).sum(); v.index=pd.to_datetime(v.index)
med=v.rolling(20,min_periods=10).median().shift(1)
rolls=m.index[m.instrument_id.ne(m.instrument_id.shift())&m.instrument_id.shift().notna()]
rows=[]
for x in rolls:
    d=pd.Timestamp((x+pd.Timedelta(hours=6)).date())
    before=v[v.index<d].tail(4); after=v[v.index>=d].head(2)
    rows.append(dict(roll=d.date(),yr=d.year,b4=round((before/med.reindex(before.index)).iloc[0],2),b1=round((before/med.reindex(before.index)).iloc[-1],2),a1=round((after/med.reindex(after.index)).iloc[0],2)))
df=pd.DataFrame(rows); print(df.to_string())
