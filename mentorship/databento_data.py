"""CME index futures 1-minute bars from Databento (GLBX.MDP3, ohlcv-1m), the real 17:00 close /
18:00 reopen that ICT's NDOG / NWOG need. Market data only; the paid download needs the
account owner's go-ahead because it spends Databento credit (cost is quoted first).

Continuous front contract rolled by volume (ES.v.0 / NQ.v.0 / YM.v.0). <S>_1min_dbraw.csv keeps
the raw contract prices; <S>_1min_db.csv (used by the backtests) is difference back-adjusted at
each roll so old levels line up with the current contract (the roll jump is measured from the
old contract's last close to the new one's first open, so it also absorbs that bar's move).

The API key is read from the DATABENTO_API_KEY user environment variable (never printed).

    python -m mentorship.databento_data --quote          # cost only, spends nothing
    python -m mentorship.databento_data --buy ES NQ      # download (spends credit)
    python -m mentorship.databento_data --build ES NQ YM # rebuild the CSVs (2016-18 history from data/databento_extra joined)
"""
from __future__ import annotations

import argparse
import os

import pandas as pd

from .backtest import DATA, NY

ROOT = {"ES": "ES.v.0", "NQ": "NQ.v.0", "YM": "YM.v.0"}
START, DATASET = "2019-01-01", "GLBX.MDP3"


def _key() -> str:
    k = os.environ.get("DATABENTO_API_KEY")
    if not k:
        import winreg
        k = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment"),
                                "DATABENTO_API_KEY")[0]
    return k


def _client():
    import databento as db
    return db.Historical(_key())


def quote(symbols=("ES", "NQ", "YM"), end: str | None = None) -> dict[str, float]:
    c = _client()
    end = end or pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    out = {}
    for s in symbols:
        out[s] = sum(c.metadata.get_cost(dataset=DATASET, symbols=[ROOT[s]], stype_in="continuous",
                                         schema="ohlcv-1m", start=a, end=b)
                     for a, b in ((START, "2023-01-01"), ("2023-01-01", end)))
    return out


def buy(symbols=("ES", "NQ"), end: str | None = None) -> None:
    c = _client()
    end = end or pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
    for s in symbols:
        raw = DATA / "databento" / f"{s}_ohlcv1m.dbn.zst"
        raw.parent.mkdir(parents=True, exist_ok=True)
        if not raw.exists():
            c.timeseries.get_range(dataset=DATASET, symbols=[ROOT[s]], stype_in="continuous",
                                   schema="ohlcv-1m", start=START, end=end, path=str(raw))
        build(s)


def back_adjust(df: pd.DataFrame) -> pd.DataFrame:
    """Difference-adjust the rolled series so a contract roll leaves no artificial gap: at
    each change of instrument_id, everything before it is shifted by (first open of the new
    contract - last close of the old one). The newest contract keeps its real prices, so
    levels on recent data match the chart. `roll` marks the first bar of each new contract;
    `adj` is the shift applied to each bar (real contract price = adjusted - adj; #13 DATA1)."""
    df = df.copy()
    roll = df.instrument_id.ne(df.instrument_id.shift()) & df.instrument_id.shift().notna()
    adj = pd.Series(0.0, index=df.index)
    for t in df.index[roll.values]:
        k = df.index.get_loc(t)
        jump = df.open.iloc[k] - df.close.iloc[k - 1]
        adj.iloc[:k] += jump
    for c in ("open", "high", "low", "close"):
        df[c] = df[c] + adj
    df["roll"] = roll
    df["adj"] = adj
    return df


def build(s: str, history: bool = True) -> pd.DataFrame:
    """The main 2019-onward ES.v.0 / NQ.v.0 / YM.v.0 file, with `history` the 2016-2018 front-month bars from
    data/databento_extra (databento_extra.minute_history) joined in front of it, so the engine loads January 2016 to now.
    Back-adjusting runs over the joined series: a roll only shifts the bars BEFORE it, so 2019-onward prices are unchanged."""
    import databento as db
    raw = DATA / "databento" / f"{s}_ohlcv1m.dbn.zst"
    df = db.DBNStore.from_file(str(raw)).to_df()
    df.index = pd.DatetimeIndex(df.index).tz_convert(NY)
    df = df[["open", "high", "low", "close", "volume", "instrument_id"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    if history:
        from .databento_extra import minute_history
        old = minute_history(s)
        if old is not None:
            df = pd.concat([old[old.index < df.index[0]], df])
    return _write(s, df)


def _write(s: str, df: pd.DataFrame) -> pd.DataFrame:
    """Raw front-month bars -> the raw CSV, the back-adjusted 1-minute and 5-minute CSVs."""
    df.to_csv(DATA / f"{s}_1min_dbraw.csv")
    df = back_adjust(df)
    g = df.groupby(df.index.floor("5min"))
    five = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last(), "volume": g.volume.sum(),
                         "instrument_id": g.instrument_id.last(), "adj": g.adj.last(),
                         "roll": g.roll.any()})
    df.to_csv(DATA / f"{s}_1min_db.csv")
    five.to_csv(DATA / f"{s}_5min_db.csv")
    print(s, len(df), "1-min bars", df.index[0], "->", df.index[-1],
          "| contracts:", df.instrument_id.nunique())
    return df


def extend_2016(s: str) -> pd.DataFrame:
    """Prepend the 2016-18 front-month bars (databento_extra.minute_history) to the 2019-onward raw CSV, then rebuild
    the raw, back-adjusted 1-minute and 5-minute files. Needs no credit."""
    from .databento_extra import minute_history
    cols = ["open", "high", "low", "close", "volume", "instrument_id"]
    old = pd.read_csv(DATA / f"{s}_1min_dbraw.csv", index_col=0)
    old.index = pd.to_datetime(old.index, utc=True).tz_convert(NY)
    ext = minute_history(s)
    df = pd.concat([ext[cols], old[cols]]).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return _write(s, df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote", action="store_true")
    ap.add_argument("--buy", nargs="*")
    ap.add_argument("--extend2016", nargs="*")
    a = ap.parse_args()
    if a.quote:
        for s, v in quote().items():
            print(s, f"${v:.2f}")
    if a.buy:
        buy(a.buy)
    for s_ in a.extend2016 or []:
        extend_2016(s_)


if __name__ == "__main__":
    main()
