"""Cross-check the HistData index CFD bars against independent sources (Yahoo Finance
^GSPC / ^NDX cash indices and ES=F / NQ=F futures).

For each overlapping period: share of bars present in both, correlation of bar returns,
the time shift (-90..+90 min) that best lines the two series up (month by month, so a
mis-stamped stretch shows up as a non-zero best shift), and the typical difference in
bar range (high - low).

    python -m mentorship.crosscheck
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import backtest as B

Y = Path("data/mentorship/yahoo")


def _yahoo(name: str, iv: str) -> pd.DataFrame:
    d = pd.read_csv(Y / f"{name}_{iv}.csv", index_col=0)
    d.columns = [c.lower() for c in d.columns]
    idx = pd.to_datetime(d.index, utc=True)
    d.index = idx.tz_convert(B.NY) if iv != "1d" else pd.to_datetime(d.index.str[:10])
    return d[["open", "high", "low", "close"]].astype(float)


def _bars(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    g = df.groupby(df.index.floor(f"{minutes}min"))
    return pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last()})


def compare(a: pd.DataFrame, b: pd.DataFrame, minutes: int, rth: bool) -> pd.DataFrame:
    """Month-by-month agreement of two bar series of the same bar size."""
    if rth:
        keep = lambda x: x[((x.index.hour * 60 + x.index.minute) >= 570) & (x.index.hour < 16)]
        a, b = keep(a), keep(b)
    rows = []
    for m, am in a.groupby(a.index.to_period("M")):
        bm = b[b.index.to_period("M") == m]
        if len(bm) < 20:
            continue
        ra, rb = am.close.diff(), bm.close.diff()
        best, bestc = 0, -2.0
        for k in range(-90 // minutes, 90 // minutes + 1):
            s = rb.copy()
            s.index = s.index + pd.Timedelta(minutes=k * minutes)
            j = pd.concat([ra, s], axis=1, join="inner").dropna()
            if len(j) > 10:
                c = j.iloc[:, 0].corr(j.iloc[:, 1])
                if c > bestc:
                    best, bestc = k * minutes, c
        j = pd.concat([am, bm], axis=1, join="inner", keys=["a", "b"]).dropna()
        c0 = j["a"].close.diff().corr(j["b"].close.diff()) if len(j) > 10 else np.nan
        rng = ((j["a"].high - j["a"].low) - (j["b"].high - j["b"].low)).abs().median()
        rows.append(dict(month=str(m), bars_a=len(am), bars_b=len(bm), both=len(j),
                         corr=round(c0, 3), best_shift_min=best, corr_at_best=round(bestc, 3),
                         range_diff_med=round(float(rng), 2)))
    return pd.DataFrame(rows)


def daily(sym: str, yname: str) -> pd.DataFrame:
    """09:30-16:00 OHLC from HistData vs the official daily bar of the cash index."""
    df = B.load(sym, 1, source="histdata")
    t = df.index.hour * 60 + df.index.minute
    r = df[(t >= 570) & (t < 960)]
    g = r.groupby(r.index.date)
    h = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                      "close": g.close.last()})
    h.index = pd.to_datetime(h.index)
    y = _yahoo(yname, "1d")
    j = h.join(y, rsuffix="_y", how="inner")
    j = j[j.index >= "2019-01-01"]
    out = pd.DataFrame({"close_diff": j.close - j.close_y, "range_ratio": (j.high - j.low) / (j.high_y - j.low_y),
                        "ret_h": j.close / j.open - 1, "ret_y": j.close_y / j.open_y - 1})
    return out


def main():
    for sym, idx, fut in (("SPX", "GSPC", "ESF"), ("NDX", "NDX", "NQF")):
        df = B.load(sym, 1, source="histdata")
        print(f"\n######## {sym} ########")
        d = daily(sym, idx)
        print("daily 09:30-16:00 vs official index: days", len(d),
              "| return corr", round(d.ret_h.corr(d.ret_y), 4),
              "| median |close diff| pts", round(d.close_diff.abs().median(), 2),
              "| median range ratio", round(d.range_ratio.median(), 3))
        bad = d[(d.range_ratio < 0.8) | (d.range_ratio > 1.25)]
        print("days with range off by >20-25%:", len(bad), bad.index.year.value_counts().sort_index().to_dict())
        for name, iv, m, rth in ((idx, "1h", 60, True), (fut, "1h", 60, False), (idx, "5m", 5, True),
                                 (fut, "5m", 5, False), (fut, "1m", 1, False)):
            y = _yahoo(name, iv)
            h = _bars(df, m)
            if iv == "1h" and rth:                   # Yahoo's index hours start at 09:30
                h = _bars(df.shift(freq="-30min"), 60).shift(freq="30min")
            c = compare(h, y, m, rth)
            if not len(c):
                continue
            print(f"\n--- {name} {iv} ({'09:30-16:00' if rth else 'all hours'}) ---")
            print("months with best shift != 0:", c[c.best_shift_min != 0][["month", "best_shift_min", "corr", "corr_at_best"]].to_string(index=False) if (c.best_shift_min != 0).any() else "none")
            print("median corr", c["corr"].median(), "| min corr", c["corr"].min(), "| median range diff", c.range_diff_med.median())


if __name__ == "__main__":
    main()
