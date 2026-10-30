"""Databento files in data/databento_extra/ (bought 2026-10-24): the 2016-2018 ES / NQ / YM 1-minute bars that extend the
main ES.v.0 / NQ.v.0 / YM.v.0 files back to January 2016, and the intermarket futures that replace the free Yahoo series:
  DX  US dollar index futures, 1h and 1d, 2019 onward only (no 2016-18 file)
  ZN  10-year T-note futures, 1d, 2016 onward (ZN_ohlcv1d_2016-18 + ZN_ohlcv1d)
  ZB  30-year T-bond futures, 1d, 2016 onward (ZB_ohlcv1d_2016-18 + ZB_ohlcv1d)

These files use parent symbology (ES.FUT, DX.FUT ...): every outright and every calendar spread in one stream. The front
contract is picked per session as the outright with the highest volume in the PRIOR session (Databento's volume roll for
`.v.0`, which the main files use; the first session uses its own volume), and the series is difference back-adjusted at
each roll (databento_data.back_adjust), so the newest contract keeps its real prices.

ZN / ZB are bond PRICES. The yield rules (bond_range, bond_dir, tnx_slow, bond_lt, notes_dxy, spx_tnx_corr ...) were written
for the 10-year yield (Yahoo ^TNX), so `yield_proxy` inverts the price: y = 10,000 / price [our interpretation - a
monotone decreasing transform; signs, slopes, ranges and the bond-price return -y.pct_change() keep their meaning, the level
is not a yield in percent]. Market data only; nothing here downloads or spends Databento credit.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

NY = "America/New_York"
EXTRA = Path("data/databento_extra")
PARTS = {"DX": ("DX_ohlcv1d",), "ZN": ("ZN_ohlcv1d_2016-18", "ZN_ohlcv1d"), "ZB": ("ZB_ohlcv1d_2016-18", "ZB_ohlcv1d")}
_CACHE: dict = {}


def _raw(name: str) -> pd.DataFrame:
    import databento as db
    df = db.DBNStore.from_file(str(EXTRA / f"{name}.dbn.zst")).to_df()
    return df[["open", "high", "low", "close", "volume", "instrument_id", "symbol"]]


def outrights(df: pd.DataFrame) -> pd.DataFrame:
    """Keep outright futures only: CME style 'ESH6' / 'ZNZ19', and the dollar index's 'DX  FMZ0021!'. Calendar spreads
    ('ESH6-ESM6'), user-defined instruments ('UD:ZN: TL ...') and the '_Z' / '_A' variants are dropped."""
    sym = df["symbol"].astype(str)
    ok = sym.str.fullmatch(r"[A-Z]{1,3}[FGHJKMNQUVXZ]\d{1,2}") | sym.str.fullmatch(r"DX\s+FM[FGHJKMNQUVXZ]\d{4}!")
    return df[ok.values]


def session_date(idx: pd.DatetimeIndex, daily: bool) -> pd.Index:
    """CME trading date: daily bars are stamped 00:00 UTC of the trading date; intraday bars belong to the session that
    opens at 18:00 New York the evening before (18:00 ET onward counts as the next date)."""
    if daily:
        return pd.Index(idx.tz_convert("UTC").date)
    t = idx.tz_convert(NY)
    return pd.Index((t + pd.Timedelta(hours=6)).date)


def front(df: pd.DataFrame, daily: bool) -> pd.DataFrame:
    """Keep only the front contract's bars: per session, the outright with the highest volume in the prior session.
    Weekend stubs (daily bars stamped Saturday / Sunday, a handful of contracts) are dropped, and the pick never steps back to
    a contract that expires earlier than the one already held (a thin session cannot flip the series back and forth)."""
    df = outrights(df)
    sd = session_date(df.index, daily)
    if daily:
        wk = pd.to_datetime(pd.Series(sd)).dt.weekday.values < 5
        df, sd = df[wk], sd[wk]
    last_seen = pd.Series(sd, index=df.instrument_id.values).groupby(level=0).max()   # expiry order proxy: the last session traded
    vol = df.groupby([sd, df.instrument_id.values]).volume.sum()
    lead = vol.groupby(level=0).idxmax().map(lambda x: x[1])            # session -> the session's own volume leader
    pick = lead.shift(1)                                                # use the PRIOR session's leader
    pick.iloc[0] = lead.iloc[0]
    held = []
    for inst in pick.astype("int64").values:                            # no roll back to an earlier-expiring contract
        if held and last_seen[inst] < last_seen[held[-1]]:
            inst = held[-1]
        held.append(inst)
    want = pd.Series(held, index=lead.index).reindex(sd).values
    out = df[df.instrument_id.values == want]
    out = out[~out.index.duplicated(keep="first")].sort_index()
    med = out.close.rolling(21, center=True, min_periods=1).median()      # bad prints (DX has daily bars near 0): drop bars
    good = (out[["open", "high", "low", "close"]].div(med, axis=0) - 1).abs().max(axis=1) < 0.2   # more than 20% off the median
    return out[good.values]


def adjust_same_bar(df: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    """Difference back-adjust at each roll by the spread between the new and the old contract on the LAST bar before the
    roll (both closes of the same timestamp, from the raw outrights), so the roll adds no bar move; falls back to the new
    contract's first open minus the old contract's last close when the new contract has no bar at that timestamp. Same
    columns as databento_data.back_adjust (roll, adj)."""
    df = df.copy()
    roll = df.instrument_id.ne(df.instrument_id.shift()) & df.instrument_id.shift().notna()
    adj = pd.Series(0.0, index=df.index)
    by = raw.set_index([raw.index, raw.instrument_id.values]).close
    by = by[~by.index.duplicated(keep="last")]
    for t in df.index[roll.values]:
        k = df.index.get_loc(t)
        t0, new = df.index[k - 1], df.instrument_id.iloc[k]
        jump = by.get((t0, new))
        if jump is None or pd.isna(jump):
            jump = df.open.iloc[k] - df.close.iloc[k - 1]
        else:
            jump = float(jump) - df.close.iloc[k - 1]
        adj.iloc[:k] += jump
    for c in ("open", "high", "low", "close"):
        df[c] = df[c] + adj
    df["roll"] = roll
    df["adj"] = adj
    return df


def continuous(parts: tuple[str, ...], daily: bool) -> pd.DataFrame:
    """Front-month bars of the given files, joined (a later file wins on overlap) and back-adjusted at each roll."""
    raws = [outrights(_raw(n)) for n in parts]
    frames = [front(r, daily) for r in raws]
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    raw = pd.concat(raws)
    return adjust_same_bar(df[["open", "high", "low", "close", "volume", "instrument_id"]], raw)


def _cached(key: str, parts: tuple[str, ...], daily: bool) -> pd.DataFrame | None:
    """Built once and kept as <key>.parquet next to the raw files (rebuilt when a raw file is newer)."""
    if key in _CACHE:
        return _CACHE[key]
    srcs = [EXTRA / f"{n}.dbn.zst" for n in parts]
    if not all(s.exists() for s in srcs):
        _CACHE[key] = None
        return None
    pq = EXTRA / f"{key}.parquet"
    if pq.exists() and pq.stat().st_mtime >= max(s.stat().st_mtime for s in srcs):
        df = pd.read_parquet(pq)
    else:
        df = continuous(parts, daily)
        try:
            tmp = pq.with_suffix(f".{os.getpid()}.tmp")
            df.to_parquet(tmp)
            os.replace(tmp, pq)
        except OSError:
            pass
    _CACHE[key] = df
    return df


def daily(name: str) -> pd.DataFrame | None:
    """DX / ZN / ZB daily bars as a frame indexed by trading date (naive Timestamp) with open / high / low / close, or None
    when the files are missing."""
    df = _cached(f"{name}_1d_cont", PARTS[name], True)
    if df is None:
        return None
    out = df[["open", "high", "low", "close"]].copy()
    out.index = pd.to_datetime(session_date(df.index, True))
    out.index.name = "date"
    return out[~out.index.duplicated(keep="last")]


def dx_hourly() -> pd.DataFrame | None:
    """DX 1-hour bars (2019 onward), New York time, front month back-adjusted."""
    df = _cached("DX_1h_cont", ("DX_ohlcv1h",), False)
    if df is None:
        return None
    out = df[["open", "high", "low", "close", "volume"]].copy()
    out.index = out.index.tz_convert(NY)
    return out


def yield_proxy(px: pd.DataFrame) -> pd.DataFrame:
    """Bond price bars -> a yield-direction series (10,000 / price): high and low swap places."""
    y = pd.DataFrame(index=px.index)
    y["open"], y["close"] = 1e4 / px.open, 1e4 / px.close
    y["high"], y["low"] = 1e4 / px.low, 1e4 / px.high
    return y


def intermarket_daily(name: str, bond: str = "ZN") -> pd.DataFrame | None:
    """The daily frame the intermarket rules read, by the old Yahoo name: 'DXY' -> DX futures, 'TNX' -> the `bond` futures
    (ZN 10-year by default, ZB 30-year) inverted to a yield direction. Other names -> None (they stay on Yahoo)."""
    if name == "DXY":
        return daily("DX")
    if name == "TNX":
        b = daily(bond)
        return None if b is None else yield_proxy(b)
    return None


def minute_history(symbol: str) -> pd.DataFrame | None:
    """The 2016-2018 1-minute front-month bars of ES / NQ / YM (raw contract prices, instrument_id), or None when the file is
    missing. databento_data.build joins them in front of the main file before back-adjusting."""
    f = EXTRA / f"{symbol}_ohlcv1m_2016-18.dbn.zst"
    if not f.exists():
        return None
    df = front(_raw(f"{symbol}_ohlcv1m_2016-18"), False)
    df.index = df.index.tz_convert(NY)
    return df[["open", "high", "low", "close", "volume", "instrument_id"]]
