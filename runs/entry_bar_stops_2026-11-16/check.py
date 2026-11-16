"""Audit of trades stopped out inside their own entry bar (2026-11-16). Results only, no engine change.

Replays every trade whose stop exit has the same 5m timestamp as its entry against the raw Databento 1-minute bars and
checks the order of events: was the limit traded through first, and was the stop reached at or after that minute?

    pip install databento
    python check.py TRADES_DIR DBN_DIR [VARIANT]

TRADES_DIR = the unpacked /mnt/project-files/mentorship/runs/bt_base_2026-11-13/trades_and_skips.tgz
DBN_DIR    = /mnt/project-files/mentorship/data/databento          VARIANT default wd_off (week rule off: most trades)
Writes same_bar_all.csv, hand_check_20.md and prints the tables used in README.md.
"""
import glob, sys, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
TR, DBN, VAR = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else "wd_off")
TICK = {"ES": .25, "NQ": .25, "YM": 1.0}


def one_min(s):
    import databento as db
    d = db.DBNStore.from_file(f"{DBN}/{s}_ohlcv1m.dbn.zst").to_df()
    d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York")
    d = d[["open", "high", "low", "close"]].sort_index()
    return d[~d.index.duplicated(keep="last")]


df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{TR}/trades_*_{VAR}_*.csv"))], ignore_index=True).copy()
M = {s: one_min(s) for s in TICK}
F = {s: m.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
     for s, m in M.items()}
df["same"] = (df.entry_time == df.exit_time) & (df.exit_reason == "stop")
print("trades", len(df), "| stopped in entry bar", int(df.same.sum()), f"({df.same.mean():.1%})")
print("fills on the bar the order was armed on:", int((df.armed == df.entry_time).sum()))
print(df.groupby("setup").agg(n=("same", "size"), same_bar=("same", "mean"), net=("net", "sum"),
                              net_same_bar=("net", lambda s: s[df.loc[s.index, "same"]].sum())).sort_values("n", ascending=False).round(3))

# typical 5m range before the entry, and whether the trade's prices are in the raw file's frame (roll weeks / scalp rows are not)
ctx = []
for _, r in df.iterrows():
    f, t0 = F[r.symbol], pd.Timestamp(r.entry_time)
    prev = f.loc[t0 - pd.Timedelta(minutes=60):t0 - pd.Timedelta(minutes=5)]
    if len(prev) < 6 or t0 not in f.index:
        ctx.append((np.nan, False)); continue
    b = f.loc[t0]
    ctx.append(((prev.high - prev.low).median(), bool(b.low <= r.entry <= b.high)))
df[["rng", "px_ok"]] = ctx
df["risk"] = (df.entry - df.stop).abs()
df["risk_vs_bar"] = df.risk / df.rng

rows = []
for k, r in df[df.same].iterrows():
    m, t0, sg = M[r.symbol], pd.Timestamp(r.entry_time), (1 if r.side == "long" else -1)
    bar = m.loc[t0:t0 + pd.Timedelta(minutes=4)]
    adv = bar.low if sg > 0 else bar.high                       # the adverse extreme of each minute
    filled = (adv < r.entry) if sg > 0 else (adv > r.entry)     # engine rule: a limit fills when price trades through it
    stopped = (adv <= r.stop) if sg > 0 else (adv >= r.stop)    # engine rule: a stop is hit on a touch
    fm = int(filled.values.argmax()) if filled.any() else -1
    sm = fm + int(stopped.values[fm:].argmax()) if fm >= 0 and stopped.values[fm:].any() else -1
    rows.append(dict(k=k, symbol=r.symbol, setup=r.setup, kind=r.entry_kind, side=r.side, entry_time=r.entry_time[:16], entry=r.entry, stop=r.stop,
                     risk_ticks=round(abs(r.entry - r.stop) / TICK[r.symbol], 1), bar_open=bar.open.iloc[0] if len(bar) else np.nan,
                     fill_min=fm, stop_min=sm, verdict="price frame differs" if (not r.px_ok or fm < 0) else ("ok" if sm >= 0 else "stop not reached"),
                     mins=" ".join(f"{a:g}" for a in adv.values), R=r.R))
c = pd.DataFrame(rows)
c.to_csv("same_bar_all.csv", index=False)
print(c.verdict.value_counts().to_dict())
ok = c[c.verdict == "ok"]
print("minute of the entry bar the limit filled in:", ok.fill_min.value_counts().sort_index().to_dict())
print("minutes from fill to stop:", (ok.stop_min - ok.fill_min).value_counts().sort_index().to_dict())
print("risk in ticks (median) by market:", ok.groupby("symbol").risk_ticks.median().to_dict())

ob = df[(df.entry_kind == "ob_pre") & df.px_ok].copy()
ob["bucket"] = pd.cut(ob.risk_vs_bar, [0, .5, .75, 1, 1.5, 2, 99])
print("pre-break order-block entries by stop size / typical 5m bar range (median range of the 12 bars before the entry)")
print(ob.groupby("bucket").agg(n=("R", "size"), same_bar=("same", "mean"), mean_R=("R", "mean"), net=("net", "sum")).round(2))
for name, d in (("2019-22", ob[ob.year <= 2022]), ("2023-26", ob[ob.year >= 2023])):
    print(name); print(d.groupby("bucket").agg(n=("R", "size"), same_bar=("same", "mean"), mean_R=("R", "mean")).round(2))

pick = pd.concat([ok[ok.kind == "ob_pre"].sample(16, random_state=7), ok[ok.kind != "ob_pre"].sample(4, random_state=7)]).sort_values(["symbol", "entry_time"])
with open("hand_check_20.md", "w") as fh:
    fh.write("| market | setup | side | entry bar (NY) | limit | stop | risk (ticks) | bar open | 1m " + "lows (long) / highs (short)" + " | filled in min | stopped in min |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
    for _, r in pick.iterrows():
        fh.write(f"| {r.symbol} | {r.setup} | {r.side} | {r.entry_time} | {r.entry:g} | {r.stop:g} | {r.risk_ticks:g} | {r.bar_open:g} | {r.mins} | {r.fill_min + 1} | {r.stop_min + 1} |\n")
