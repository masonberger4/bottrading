"""Synthetic 1m futures bars on the CME session (Sun 18:00 - Fri 17:00 ET, daily 17-18 halt)
for tests and smoke runs."""
from __future__ import annotations

import numpy as np
import pandas as pd

NY = "America/New_York"


def bars(start="2021-01-03", end="2022-06-30", seed=0, price=4000.0, vol=0.6, drift=0.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(pd.Timestamp(start, tz=NY), pd.Timestamp(end, tz=NY), freq="1min")
    wd, hr = idx.weekday, idx.hour
    open_ = ~((hr == 17) | ((wd == 4) & (hr >= 17)) | (wd == 5) | ((wd == 6) & (hr < 18)))
    idx = idx[open_]
    # regime drift that flips every ~3 months so the bias has trends to find
    reg = np.sign(np.sin(np.arange(len(idx)) / (60 * 23 * 63 / np.pi))) * 0.004 + drift
    r = rng.normal(reg, vol, len(idx))
    c = price + np.cumsum(r)
    o = np.r_[price, c[:-1]]
    sp = np.abs(rng.normal(0, vol * 0.6, len(idx)))
    h = np.maximum(o, c) + sp
    l = np.minimum(o, c) - np.abs(rng.normal(0, vol * 0.6, len(idx)))
    q = lambda x: np.round(x * 4) / 4
    return pd.DataFrame({"open": q(o), "high": q(h), "low": q(l), "close": q(c)}, index=idx)
