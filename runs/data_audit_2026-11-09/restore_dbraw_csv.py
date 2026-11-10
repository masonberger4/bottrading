import os, pandas as pd
D="data/mentorship/"
f=D+"ES_1min_dbraw.csv"; bk=D+"ES_1min_dbraw.truncated_2026-11-09.csv"
st=os.stat(f); os.rename(f,bk)
r=pd.read_parquet(D+"ES_1min_dbraw.parquet"); m=pd.read_parquet(D+"ES_1min_dbmeta.parquet")
assert r.index.equals(m.index)
r["volume"]=r.volume.astype("int64"); r["instrument_id"]=m.instrument_id.astype("int64")
r.index=r.index.astype("datetime64[ns, America/New_York]"); r.index.name="ts_event"
tmp=f+".tmp"; r.to_csv(tmp); os.replace(tmp,f)
os.utime(f,(st.st_atime,st.st_mtime))   # keep the engine reading the existing (complete) parquet
print(len(r))
