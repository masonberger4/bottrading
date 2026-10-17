"""CME index futures 1-minute bars from Databento (GLBX.MDP3, ohlcv-1m), the real 17:00 close /
18:00 reopen that ICT's NDOG / NWOG need. Market data only; the paid download needs the
account owner's go-ahead because it spends Databento credit (cost is quoted first).

Continuous front contract rolled by volume (ES.v.0 / NQ.v.0 / YM.v.0). Prices are the raw
contract's, not back-adjusted, as on ICT's charts; `instrument_id` changes on roll days so
those can be flagged.

The API key is read from the DATABENTO_API_KEY user environment variable (never printed).

    python -m mentorship.databento_data --quote          # cost only, spends nothing
    python -m mentorship.databento_data --buy ES NQ      # download (spends credit)
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


def build(s: str) -> pd.DataFrame:
    import databento as db
    raw = DATA / "databento" / f"{s}_ohlcv1m.dbn.zst"
    df = db.DBNStore.from_file(str(raw)).to_df()
    df.index = pd.DatetimeIndex(df.index).tz_convert(NY)
    df = df[["open", "high", "low", "close", "volume", "instrument_id"]].sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df.to_csv(DATA / f"{s}_1min_db.csv")
    g = df.groupby(df.index.floor("5min"))
    five = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last(), "volume": g.volume.sum(),
                         "instrument_id": g.instrument_id.last()})
    five.to_csv(DATA / f"{s}_5min_db.csv")
    print(s, len(df), "1-min bars", df.index[0], "->", df.index[-1],
          "| contracts:", df.instrument_id.nunique())
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quote", action="store_true")
    ap.add_argument("--buy", nargs="*")
    a = ap.parse_args()
    if a.quote:
        for s, v in quote().items():
            print(s, f"${v:.2f}")
    if a.buy:
        buy(a.buy)


if __name__ == "__main__":
    main()
