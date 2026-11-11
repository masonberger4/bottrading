"""Fixed-roll ES / NQ / YM 1-minute and 5-minute series (data audit 2026-11-09, finding 1).

Roll rule: the session that opens at 18:00 ET on the Thursday 8 days before expiry (the CME roll date) and every later
session trade the next quarterly contract. That is the session where the next contract's volume first leads (checked on
2016-18, where every outright is on disk). Calendar rule, no lookahead.

Sources: 2016-18 every outright (databento_extra/<S>_ohlcv1m_2016-18), 2019-26 the <S>.v.0 bars (databento/<S>_ohlcv1m) plus
the next-contract bars bought 2026-11-10 (databento_extra/roll_next_2019-26). Back-adjusted with
databento_extra.adjust_same_bar (same-timestamp spread, so a roll adds no bar move; audit finding 4).

Writes data/mentorship/roll_fix_2026-11-10/ with the same file names and layout as the engine's files
(<S>_1min_db / _dbmeta / _dbraw, <S>_5min_db / _dbmeta parquets). Never touches data/mentorship/*.parquet.
"""
import re, sys, glob, datetime as dt
import numpy as np, pandas as pd, databento as db
sys.path.insert(0, ".worktrees/scb")
from mentorship.databento_extra import _raw, outrights, session_date, adjust_same_bar

NY = "America/New_York"
OUT = "data/mentorship/roll_fix_2026-11-10/"
MC = {"H": 3, "M": 6, "U": 9, "Z": 12}
P = lambda *a: print(*a, flush=True)


def third_fri(y, m):
    d = dt.date(y, m, 15); return d + dt.timedelta((4 - d.weekday()) % 7)


EXP = [third_fri(y, m) for y in range(2015, 2028) for m in (3, 6, 9, 12)]


def first_exp_on_or_after(d):
    return next(e for e in EXP if e >= d)


def sym_exp(sym, year):
    """'ESM9' / 'ESZ16' + the bar's year -> expiry date (the first matching year at or after the bar's year)."""
    m = re.fullmatch(r"[A-Z]{2}([HMUZ])(\d{1,2})", sym)
    if not m: return None
    code, yy = m.group(1), int(m.group(2))
    y = next(y for y in range(year - 1, year + 11) if y % (10 ** len(m.group(2))) == yy and third_fri(y, MC[code]) >= dt.date(year, 1, 1))
    return third_fri(y, MC[code])


def tagged(df, sym_col=True):
    """Add `exp` (contract expiry) to each bar."""
    df = df.copy()
    if sym_col:
        key = pd.Series(list(zip(df.symbol.astype(str), df.index.year)))
        u = {k: sym_exp(*k) for k in set(key)}
        df["exp"] = key.map(u).values
    else:  # .v.0: one contract per run of the same instrument_id; its expiry is the first one on or after the run's last bar
        run = df.instrument_id.ne(df.instrument_id.shift()).cumsum()
        last = pd.Series(session_date(df.index, False), index=df.index).groupby(run.values).max()
        df["exp"] = run.map({k: first_exp_on_or_after(v) for k, v in last.items()}).values
    return df


def target(sd):
    """Session date -> expiry of the contract to hold: the expiring one until the session dated expiry-7 (Friday) opens."""
    return [next(e for e in EXP if d <= e - dt.timedelta(8)) for d in sd]


COLS = ["open", "high", "low", "close", "volume", "instrument_id", "exp"]


def build(S):
    old = tagged(outrights(_raw(f"{S}_ohlcv1m_2016-18")))
    v0 = db.DBNStore.from_file(f"data/databento/{S}_ohlcv1m.dbn.zst").to_df()
    v0 = v0[~v0.index.duplicated(keep="last")].sort_index()
    v0 = tagged(v0, sym_col=False)
    nxt = pd.concat([db.DBNStore.from_file(f).to_df() for f in sorted(glob.glob(f"data/databento_extra/roll_next_2019-26/{S}*.dbn.zst"))])
    nxt = tagged(nxt)
    start19 = v0.index[0]
    pool = pd.concat([old[old.index < start19][COLS], v0[COLS], nxt[COLS]])
    pool.index = pd.DatetimeIndex(pool.index).tz_convert(NY)
    pool = pool[~pool.set_index("instrument_id", append=True).index.duplicated(keep="first")].sort_index()
    assert pool.exp.notna().all()
    sd = pd.Index(session_date(pool.index, False))
    us = sd.unique(); tmap = dict(zip(us, target(us)))
    want = pd.Index(sd).map(tmap)
    out = pool[pool.exp.values == np.array(want)]
    assert out.index.is_unique
    df = adjust_same_bar(out[["open", "high", "low", "close", "volume", "instrument_id"]], pool)
    raw = out[["open", "high", "low", "close", "volume"]]
    g = df.groupby(df.index.floor("5min"))
    five = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                         "volume": g.volume.sum(), "instrument_id": g.instrument_id.last(), "adj": g.adj.last(), "roll": g.roll.any()})
    import os; os.makedirs(OUT, exist_ok=True)
    df[["open", "high", "low", "close", "volume"]].to_parquet(OUT + f"{S}_1min_db.parquet")
    df[["adj", "instrument_id", "roll"]].to_parquet(OUT + f"{S}_1min_dbmeta.parquet")
    raw.to_parquet(OUT + f"{S}_1min_dbraw.parquet")
    five[["open", "high", "low", "close", "volume"]].to_parquet(OUT + f"{S}_5min_db.parquet")
    five[["adj", "instrument_id", "roll"]].to_parquet(OUT + f"{S}_5min_dbmeta.parquet")
    P(S, "bars", len(df), df.index[0], "->", df.index[-1], "rolls", int(df.roll.sum()), "contracts", df.instrument_id.nunique())
    return df, pool, out


if __name__ == "__main__":
    for S in sys.argv[1:] or ["ES", "NQ", "YM"]:
        build(S)
