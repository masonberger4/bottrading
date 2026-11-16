import sys, pandas as pd, databento as db
sys.path.insert(0, ".worktrees/scb")
from mentorship.databento_extra import _raw, outrights, session_date
NY = "America/New_York"
r = outrights(_raw("ES_ohlcv1m_2016-18"))
sd = session_date(r.index, False)
v = r.groupby([sd, r.symbol.values]).volume.sum().unstack().fillna(0)
for exp in ["2017-03-17", "2017-06-16", "2018-09-21"]:
    e = pd.Timestamp(exp).date()
    w = v.loc[[d for d in v.index if 0 <= (e - d).days <= 14]]
    print(w.loc[:, w.sum() > w.sum().max() * 0.05].astype(int).to_string(), "\n")
m = pd.read_parquet("data/mentorship/ES_1min_dbmeta.parquet")
ch = m.instrument_id.ne(m.instrument_id.shift()) & m.instrument_id.shift().notna()
print(m.index[ch][:14].tolist())
s = db.DBNStore.from_file("data/databento_extra/roll_next_2019-26/" + "ESM92019_2019-03-01_2019-03-16.ohlcv1m.dbn.zst").to_df()
print(s.head(2).to_string()); print(len(s))
