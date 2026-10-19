"""T14 / X16a / X16c weekly study (package day_week_context): where do the weekly high and low form?

    python -m mentorship.study_week [--symbol ES] [--minutes 5] [--source databento] [--out runs/mentorship]

Writes `week_extremes.csv` (one row per Monday-Friday week: the weekday and the kill-zone session of the weekly
high / low), `day_ranges.csv` (X16a: each session's range vs ADR5) and `week_study.json` (the T14 claims as
numbers). Whole weeks, all-hours bars (the Sunday-evening reopen counts to Monday): this is a REPORT, never an
input of a decision. The claims it tests (mentorship_rules.md T14, N10):
  mon_wed_extreme   the weekly high / low forms Monday-Wednesday ~70% of the time (cc07_008 ~1:35)
  bulk_tue_thu      the bulk of the weekly range is made Tuesday-Thursday
  by_wed_london     30-50% of the weekly range is done by Wednesday's London close (cc12_003 ~13:57; cc07_006 ~23:35)
  tue_london_low    Tuesday London makes the week's low in ~77% of bullish weeks [fx] (cc08_001 ~20:43)
  bear_high_tue     a bearish week's high is often Tuesday (070 ~4:23)
Params.tue_week_extreme ("tag" / "side") is the switch built on the Tuesday-London claim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import daycontext as DW


def week_table(df: pd.DataFrame) -> pd.DataFrame:
    """X16c: the weekly extremes with weekday and session labels (daycontext.weekly_extremes)."""
    return DW.weekly_extremes(df)


def _by_wed_london(df: pd.DataFrame) -> pd.Series:
    """For each week the share of the whole week's high-low range already made by the end of Wednesday's London
    session (05:00 New York on the trading day Wednesday)."""
    lab = DW.trading_label(df.index)
    wk = pd.Series(lab.to_period("W-FRI"), index=df.index)
    wd = pd.Series(lab.dayofweek, index=df.index)
    m = pd.Series(df.index.hour * 60 + df.index.minute, index=df.index)
    out = {}
    for key, g in df.groupby(wk.values):
        if len(g) < 10:
            continue
        w = wd.loc[g.index]
        mm = m.loc[g.index]
        # trading-day Wednesday 05:00: the evening bars (>= 18:00) already belong to the next trading day
        cut = (w < 2) | ((w == 2) & ((mm < 300) | (mm >= 18 * 60)))
        part = g[cut.values]
        full = float(g.high.max() - g.low.min())
        if len(part) and full > 0:
            out[str(key)] = float(part.high.max() - part.low.min()) / full
    return pd.Series(out, dtype=float)


def summarize(wk: pd.DataFrame, df: pd.DataFrame | None = None) -> dict:
    """The T14 / N10 claims as numbers from the weekly table (and the bars, for the by-Wednesday share)."""
    n = len(wk)
    if not n:
        return dict(weeks=0)
    hi_mw = float(wk.mon_wed_high.mean())
    lo_mw = float(wk.mon_wed_low.mean())
    either = float((wk.mon_wed_high | wk.mon_wed_low).mean())
    bull = wk[wk.bullish]
    bear = wk[~wk.bullish]
    out = dict(
        weeks=n,
        high_by_weekday={int(k): int(v) for k, v in wk.high_day.value_counts().sort_index().items()},
        low_by_weekday={int(k): int(v) for k, v in wk.low_day.value_counts().sort_index().items()},
        high_by_session=wk.high_session.value_counts().to_dict(),
        low_by_session=wk.low_session.value_counts().to_dict(),
        mon_wed_high=round(hi_mw, 3), mon_wed_low=round(lo_mw, 3), mon_wed_either=round(either, 3),
        mon_wed_claim_holds=bool(either >= 0.6 or (hi_mw + lo_mw) / 2 >= 0.6),
        tue_london_low_bullish=round(float(((bull.low_day == 1) & (bull.low_session == "london")).mean()), 3) if len(bull) else None,
        tue_low_bullish=round(float((bull.low_day == 1).mean()), 3) if len(bull) else None,
        bear_high_tuesday=round(float((bear.high_day == 1).mean()), 3) if len(bear) else None,
        bullish_weeks=int(len(bull)), bearish_weeks=int(len(bear)),
    )
    # the bulk of the range Tue-Thu: the high and the low both formed Tuesday-Thursday
    out["bulk_tue_thu"] = round(float(((wk.high_day.between(1, 3)) & (wk.low_day.between(1, 3))).mean()), 3)
    if df is not None:
        s = _by_wed_london(df)
        if len(s):
            out["by_wed_london_mean"] = round(float(s.mean()), 3)
            out["by_wed_london_30_50"] = round(float(((s >= 0.3) & (s <= 0.5)).mean()), 3)
    t = out["tue_london_low_bullish"]
    out["tue_week_extreme_claim_holds"] = bool(t is not None and t >= 0.5)
    return out


def main(symbol: str = "ES", minutes: int = 5, source: str = "databento", out: str = "runs/mentorship") -> dict:
    from . import backtest as B
    df = B.load(symbol, minutes, source=source)
    Path(out).mkdir(parents=True, exist_ok=True)
    wk = week_table(df)
    wk.drop(columns=["high_ts", "low_ts"], errors="ignore").to_csv(f"{out}/week_extremes.csv", index=False)
    frames = [B.rth(g) for g in B.days(df, minutes, False, 975)]
    DW.day_ranges(frames).to_csv(f"{out}/day_ranges.csv", index=False)
    rep = summarize(wk, df)
    Path(f"{out}/week_study.json").write_text(json.dumps(rep, indent=1, default=str))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="ES")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--source", default="databento")
    ap.add_argument("--out", default="runs/mentorship")
    a = ap.parse_args()
    print(json.dumps(main(a.symbol, a.minutes, a.source, a.out), indent=1, default=str))
