"""Compare the fixed-roll series with the engine's current files (raw prices, rolls, thin sessions, missing minutes)."""
import sys, datetime as dt, pandas as pd
NY = "America/New_York"; D = "data/mentorship/"; N = D + "roll_fix_2026-11-10/"
P = lambda *a: print(*a, flush=True)
pd.set_option("display.width", 200)


def raw_of(path_db, path_meta):
    a, m = pd.read_parquet(path_db), pd.read_parquet(path_meta)
    if len(m) != len(a): P("  note:", path_meta, "covers", m.index[0], "->", m.index[-1], "only;", len(a) - len(m), "bars without meta")
    m = m.reindex(a.index)
    r = a[["open", "high", "low", "close"]].sub(m.adj, axis=0); r["volume"] = a.volume; r["iid"] = m.instrument_id; i = m.instrument_id.astype("float").ffill(); r["roll"] = (i.ne(i.shift()) & i.shift().notna()).values
    return r


def rth_ratio(r):
    """For each roll: RTH volume of the last session before it / median RTH volume of the 20 sessions before that."""
    t = r.index.hour * 60 + r.index.minute
    rth = r[(t >= 570) & (t < 960)]
    dv = rth.volume.groupby(rth.index.date).sum()
    out = []
    for ts in r.index[r.roll.values]:
        prev = dv[dv.index < (ts + pd.Timedelta(hours=6)).date()]
        if len(prev) > 21: out.append(prev.iloc[-1] / prev.iloc[-21:-1].median())
    return pd.Series(out)


for S in sys.argv[1:] or ["ES", "NQ", "YM"]:
    P(f"===== {S}")
    o = raw_of(D + f"{S}_1min_db.parquet", D + f"{S}_1min_dbmeta.parquet"); P("old iid NaN:", int(o.iid.isna().sum()))
    n = raw_of(N + f"{S}_1min_db.parquet", N + f"{S}_1min_dbmeta.parquet")
    P("bars old", len(o), "new", len(n), "| raw-price check vs dbraw:", float((n[["open", "close"]] - pd.read_parquet(N + f"{S}_1min_dbraw.parquet")[["open", "close"]]).abs().max().max()))
    same = o.index.intersection(n.index)
    eq = (o.loc[same, "iid"] == n.loc[same, "iid"])
    P("same contract on", f"{eq.mean():.4%}", "of shared minutes; minutes that changed contract:", int((~eq).sum()))
    d = (o.loc[same][eq][["open", "high", "low", "close", "volume"]] - n.loc[same][eq][["open", "high", "low", "close", "volume"]]).abs().max()
    P("same-contract minutes, max raw diff:", d.to_dict())
    miss, extra = o.index.difference(n.index), n.index.difference(o.index)
    P("minutes only in old:", len(miss), "only in new:", len(extra))
    if len(miss): P("  old-only by session date:", pd.Series(1, index=miss).groupby((miss + pd.Timedelta(hours=6)).date).size().sort_values().tail(8).to_dict())
    t = miss.hour * 60 + miss.minute; P("  old-only inside 09:30-16:15 RTH:", int(((t >= 570) & (t < 975)).sum()))
    rolls = n.index[n.roll.values]
    P("new roll times (first 4 / last 2):", [str(x) for x in rolls[:4]], [str(x) for x in rolls[-2:]], "weekdays:", pd.Series(rolls.day_name()).value_counts().to_dict())
    ro, rn = rth_ratio(o), rth_ratio(n)
    P("last pre-roll session RTH volume / normal: old median %.2f min %.2f | new median %.2f min %.2f" % (ro.median(), ro.min(), rn.median(), rn.min()))
    m = pd.read_parquet(N + f"{S}_1min_dbmeta.parquet"); ch = m.roll.values
    P("adj at start: old %.2f new %.2f | roll jumps (new) min %.2f max %.2f" % (pd.read_parquet(D + f"{S}_1min_dbmeta.parquet").adj.iloc[0], m.adj.iloc[0],
      (m.adj.shift() - m.adj)[ch].min(), (m.adj.shift() - m.adj)[ch].max()))
    for day in ["2019-03-13"]:
        a, b = o.loc[day], n.loc[day]
        P(day, "(Databento: degraded) bars old", len(a), "new", len(b), "contracts old", a.iid.unique().tolist(), "new", b.iid.unique().tolist(),
          "max close diff where same minute:", float((a.close - b.close.reindex(a.index)).abs().max()))
