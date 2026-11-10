import numpy as np, pandas as pd
NY = "America/New_York"; D = "data/mentorship/"
P = lambda *a: print(*a, flush=True)
pd.set_option("display.width", 200)
raw = pd.read_parquet(D + "ES_1min_dbraw.parquet"); m1 = pd.read_parquet(D + "ES_1min_dbmeta.parquet")
raw["iid"] = m1.instrument_id

P("== H. ES vs Dukascopy S&P 500 CFD, 1-minute, 2019-2026 (independent vendor)")
dk = pd.read_csv(D + "SPX_1min_duka.csv", index_col=0)
dk.index = pd.to_datetime(dk.index, utc=True).tz_convert(NY)
t = lambda x: x.index.hour * 60 + x.index.minute
e = raw[(t(raw) >= 570) & (t(raw) < 960)]; k = dk[(t(dk) >= 570) & (t(dk) < 960)]
er = np.log(e.close).diff()[e.iid.eq(e.iid.shift())]; kr = np.log(k.close).diff()
er = er[er.index.normalize() == er.index.shift(-1, freq="min").normalize()]
both = pd.concat([er, kr], axis=1, keys=["es", "dk"]).dropna()
P("overlap minutes", len(both))
for lag in (-61, -60, -1, 0, 1, 60):
    s = pd.concat([er, kr.shift(lag, freq="min")], axis=1, keys=["es", "dk"]).dropna()
    P(f"lag {lag:+d} min corr", round(s.es.corr(s.dk), 3))
dc = both.groupby(both.index.date).apply(lambda g: g.es.corr(g.dk))
P("per-day 1m return corr: median", round(dc.median(), 3), "| days <0.6:", int((dc < 0.6).sum()), "of", len(dc))
P(dc[dc < 0.6].round(3).to_string())
# per-day lag test: days where lag +-60 beats lag 0 (a 1-hour clock error on that day)
sh = {L: pd.concat([er, kr.shift(L, freq="min")], axis=1, keys=["es", "dk"]).dropna() for L in (-60, 60)}
c60 = {L: s.groupby(s.index.date).apply(lambda g: g.es.corr(g.dk)) for L, s in sh.items()}
off = dc[(c60[-60].reindex(dc.index) > dc) | (c60[60].reindex(dc.index) > dc)]
P("days where a 1-hour shift matches better than no shift:", len(off), [str(d) for d in off.index][:40])
# RTH daily range agreement
eg = e.groupby(e.index.date).agg(h=("high", "max"), l=("low", "min")); kg = k.groupby(k.index.date).agg(h=("high", "max"), l=("low", "min"))
rr = ((eg.h - eg.l) / (kg.h - kg.l)).dropna()
P("RTH range ratio ES/CFD: median", round(rr.median(), 3), "| days outside 0.7-1.4:", int(((rr < 0.7) | (rr > 1.4)).sum()))
P(rr[(rr < 0.7) | (rr > 1.4)].round(2).to_string())
# time of RTH high / low agreement
th = lambda x: x.groupby(x.index.date).apply(lambda g: (g.high.idxmax(), g.low.idxmin()))
eh, kh = th(e), th(k)
cm = eh.index.intersection(kh.index)
dh = pd.Series([abs((eh[d][0] - kh[d][0]).total_seconds()) / 60 for d in cm], index=cm)
dl = pd.Series([abs((eh[d][1] - kh[d][1]).total_seconds()) / 60 for d in cm], index=cm)
P("RTH high time within 2 min of CFD:", round((dh <= 2).mean(), 3), "| low:", round((dl <= 2).mean(), 3))

P("\n== I. ES vs Yahoo ES=F daily, 2016-2026 (independent vendor, own roll)")
import yfinance as yf
y = yf.download("ES=F", start="2016-01-01", end="2026-10-17", interval="1d", auto_adjust=False, progress=False)
if isinstance(y.columns, pd.MultiIndex): y.columns = y.columns.get_level_values(0)
y.index = pd.to_datetime(y.index).date
P("yahoo days", len(y))
sd = (raw.index + pd.Timedelta(hours=6)).date          # session date: 18:00 previous day -> 17:00
g = raw.groupby(sd)
es = pd.DataFrame({"o": g.open.first(), "h": g.high.max(), "l": g.low.min(), "c": g.close.last(), "iid": g.iid.last(), "n_iid": g.iid.nunique()})
es = es[pd.to_datetime(pd.Series(es.index)).dt.weekday.values < 5]
j = es.join(y[["Open", "High", "Low", "Close"]], how="inner")
j = j[j.n_iid == 1]
for a, b in (("h", "High"), ("l", "Low"), ("c", "Close")):
    d = (j[a] - j[b]).abs()
    P(f"{a}: days {len(d)}, |diff|<=0.5pt {round((d <= 0.5).mean(), 3)}, <=2pt {round((d <= 2).mean(), 3)}, median {d.median()}")
d = (j.h - j.High).abs().combine((j.l - j.Low).abs(), max)
yr = pd.to_datetime(pd.Series(j.index)).dt.year.values
P("share of days with H and L both within 1pt, by year:", (d <= 1).groupby(yr).mean().round(3).to_dict())
bad = j[d > 5]; P("days with H or L more than 5pt off Yahoo:", len(bad))
P(bad.assign(dh=(bad.h - bad.High).round(2), dl=(bad.l - bad.Low).round(2))[["h", "High", "l", "Low", "dh", "dl"]].head(60).to_string())
