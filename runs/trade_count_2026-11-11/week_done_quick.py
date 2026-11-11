"""Independent check of X15d (week_done_on_draw="skip"): on which weekday is each weekly objective first delivered?
ES 5m (fixed-roll data), 2019-26. Objectives: prior-week all-hours high / low, and this week's NWOG CE (the midpoint of
Friday's last price and Sunday's first price). A session is blocked once an objective was delivered in an EARLIER session."""
import pandas as pd
NY = "America/New_York"
df = pd.read_parquet("data/mentorship/ES_5min_db.parquet")
df = df[df.index >= "2018-12-20"]
sd = (df.index + pd.Timedelta(hours=6))                       # CME session date (18:00 ET opens the next date)
df["sd"] = sd.date
df["wk"] = (sd - pd.to_timedelta(sd.weekday, unit="D")).date  # Monday of the session week
rows = []
weeks = list(df.groupby("wk"))
for k in range(1, len(weeks)):
    (pw, p), (w, g) = weeks[k - 1], weeks[k]
    if pd.Timestamp(w).year < 2019: continue
    pwh, pwl = p.high.max(), p.low.min()
    ce = (p.close.iloc[-1] + g.open.iloc[0]) / 2
    up = g.open.iloc[0] < ce                                  # opened below the CE: the CE is above
    first = {}
    for d, s in g.groupby("sd"):
        wd = pd.Timestamp(d).weekday()
        if "pwh" not in first and s.high.max() >= pwh: first["pwh"] = wd
        if "pwl" not in first and s.low.min() <= pwl: first["pwl"] = wd
        if "ce" not in first and ((up and s.high.max() >= ce) or (not up and s.low.min() <= ce)): first["ce"] = wd
    any_ = min(first.values()) if first else None
    rows.append(dict(week=w, gap=abs(p.close.iloc[-1] - g.open.iloc[0]), **{f"first_{n}": first.get(n) for n in ("pwh", "pwl", "ce")}, first_any=any_,
                     first_hl=min([first[n] for n in ("pwh", "pwl") if n in first], default=None)))
r = pd.DataFrame(rows)
names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
for c in ["first_ce", "first_pwh", "first_pwl", "first_hl", "first_any"]:
    v = r[c].value_counts().reindex(range(5)).fillna(0).astype(int)
    print(f"{c:10s}", dict(zip(names, v.tolist())), "never", int(r[c].isna().sum()), "of", len(r))
# sessions open to trade under the rule: a session (Mon-Fri) is open if no objective was delivered in an earlier session
def open_sessions(col):
    return int(sum((5 if pd.isna(x) else int(x) + 1) for x in r[col]))
tot = 5 * len(r)
print("sessions open under X15d (any of pwh/pwl/nwog_ce):", open_sessions("first_any"), "of", tot)
print("  if only pwh/pwl count:", open_sessions("first_hl"), "of", tot)
print("median NWOG size (pt):", round(r.gap.median(), 2))
