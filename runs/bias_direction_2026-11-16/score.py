"""Direction test (PR #82 option A): does any codable ICT daily bias call the day's direction?

Inputs: the engine's 09:30 bias tables (build_tables.py) and the fixed-roll 5m bars. Every rule is known at 09:30.
Outcomes, from the 09:30 open:  AM = to the 11:30 price,  DAY = to the 16:00 price.  Flat days are dropped.
Per rule: days with a call (non-neutral), hit rate, the hit rate its long / short mix would get by chance in that period
(markets drift up, so an always-long rule scores above 50% with no skill), edge = hit - chance, and a t-stat on the edge.
"All" pools ES, NQ, YM by day (the three are one bet, so the t-stat is over days, not over market-days).
Choose on 2019-22, check on 2023-26.   python score.py TABLE_DIR OUT_DIR"""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd

DATA = Path("/mnt/project-files/mentorship/data/fixed_roll_2026-11-10/")
COT = Path("/mnt/project-files/mentorship/data/cot/legacy_es_nq_ym_raw.json")
COT_CODE = {"ES": "13874A", "NQ": "209742", "YM": "124603"}
HERE = Path(__file__).resolve().parent
SYMS = ("ES", "NQ", "YM")
ENGINE = {  # engine htf.table columns (mentorship/htf.py, bias_htf.py), sign = the bias
    "react": "reaction from daily/weekly arrays", "draw": "nearest draw on liquidity", "pd": "premium/discount of dealing range",
    "combo": "react+draw+pd combined", "flip": "stateful bias flip (OB mean threshold / weekly close)",
    "draw_ord": "ordered draw (inefficiency first)", "bc_D": "daily candle: nearest unreached draw from open",
    "bc_W": "weekly candle: nearest unreached draw", "pd20": "premium/discount of 20-day range", "iof": "daily order flow",
    "combo2": "combo with order flow", "wk_bias": "weekly bias", "ob_mt": "daily order-block mean threshold",
    "mwd": "month-week-day sequence", "mwd_w": "weekly leg of MWD", "mwd_d": "daily leg of MWD", "wk_dir": "week direction vs weekly open",
    "nwog_bias": "above/below new week opening gap", "draw_pd": "draw and premium/discount agree", "qs_trend": "quarterly shift trend"}
OWN = {     # coded here from the bars (simple readings of rules ICT states; not engine columns)
    "howlow": "high/low of week judged in (engine how_in/low_in)", "mid_above": "09:30 price above the midnight open",
    "o830_above": "09:30 price above the 08:30 open", "wo_above": "09:30 price above the weekly (Sunday) open",
    "bias_mid": "combo bias AND price on the cheap side of midnight open", "bias_830": "combo bias AND price on the cheap side of 08:30 open",
    "prev_candle": "previous daily candle direction", "pdhl": "previous day closed beyond / swept-and-rejected prior day's high or low",
    "agree3": "ordered draw, order flow and weekly bias all agree", "cot": "COT commercials above/below 52-week midpoint",
    "always_long": "(reference) always long"}
RULES = {**ENGINE, **OWN}


def cot_series(sym, days):
    rows = [r for r in json.load(open(COT)) if r.get("cftc_contract_market_code") == COT_CODE[sym]]
    t = pd.DataFrame({"rep": pd.to_datetime([r["report_date_as_yyyy_mm_dd"] for r in rows]),
                      "net": [float(r["comm_positions_long_all"]) - float(r["comm_positions_short_all"]) for r in rows]})
    t = t.dropna().drop_duplicates("rep").sort_values("rep")
    t["usable"] = t.rep + pd.Timedelta(days=6)                  # Tuesday report, Friday release, usable Monday (as bias_htf.load_cot)
    hi, lo = t.net.rolling(52, min_periods=8).max(), t.net.rolling(52, min_periods=8).min()
    t["s"] = np.sign(t.net - (hi + lo) / 2).fillna(0)
    t["usable"] = t.usable.astype("datetime64[ns]")
    s = pd.merge_asof(pd.DataFrame({"d": pd.to_datetime(days).astype("datetime64[ns]")}), t[["usable", "s"]], left_on="d", right_on="usable")
    return s.s.fillna(0).astype(int).values


def frame(sym, tdir):
    df = pd.read_parquet(DATA / f"{sym}_5min_db.parquet")
    t = pd.read_pickle(Path(tdir) / f"table_{sym}.pkl")
    t.index = pd.to_datetime(t.index)
    mins = df.index.hour * 60 + df.index.minute
    day = pd.to_datetime(df.index.date)
    at = lambda m, col: df[mins == m].groupby(day[mins == m])[col].first()
    o930, mid, o830 = at(570, "open"), at(0, "open"), at(510, "open")
    p1130, p1600 = at(685, "close"), at(955, "close")           # the 11:25 and 15:55 bars close at 11:30 and 16:00
    f = pd.DataFrame(index=t.index)
    for k in ENGINE:
        f[k] = pd.to_numeric(t[k], errors="coerce").fillna(0).astype(int).clip(-1, 1)
    f["howlow"] = t.low_in.astype(int) - t.how_in.astype(int)
    f["o930"], f["mid"], f["o830"] = o930.reindex(f.index), mid.reindex(f.index), o830.reindex(f.index)
    f["mid_above"] = np.sign(f.o930 - f.mid).fillna(0).astype(int)
    f["o830_above"] = np.sign(f.o930 - f.o830).fillna(0).astype(int)
    f["wo_above"] = np.sign(f.o930 - pd.to_numeric(t.wo_sun, errors="coerce")).fillna(0).astype(int)
    f["bias_mid"] = np.where(f.combo * f.mid_above == -1, f.combo, 0)       # long bias below the open, short bias above it
    f["bias_830"] = np.where(f.combo * f.o830_above == -1, f.combo, 0)
    lab = (df.index + pd.Timedelta(hours=7)).date                             # engine sessions (htf.sessions): 18:00 to the close
    g = df.groupby(lab)
    d = pd.DataFrame({"o": g.open.first(), "h": g.high.max(), "l": g.low.min(), "c": g.close.last(), "n": g.close.size()})
    d.index = pd.to_datetime(d.index); d = d[d.n >= 60]
    pc = np.sign(d.c - d.o)
    ph, pl = d.h.shift(1), d.l.shift(1)
    pdhl = np.where(d.c > ph, 1, np.where(d.c < pl, -1, np.where((d.h > ph) & (d.l >= pl), -1, np.where((d.l < pl) & (d.h <= ph), 1, 0))))
    f["prev_candle"] = pc.shift(1).reindex(f.index).fillna(0).astype(int)     # yesterday's values only
    f["pdhl"] = pd.Series(pdhl, d.index).shift(1).reindex(f.index).fillna(0).astype(int)
    a = f[["draw_ord", "iof", "wk_bias"]]
    f["agree3"] = np.where((a.nunique(axis=1) == 1), a.draw_ord, 0)
    f["cot"] = cot_series(sym, f.index)
    f["always_long"] = 1
    f["AM"] = (p1130.reindex(f.index) / f.o930 - 1) * 1e4                     # basis points
    f["DAY"] = (p1600.reindex(f.index) / f.o930 - 1) * 1e4
    f["sym"] = sym
    return f[(f.index >= "2019-01-01") & f.o930.notna() & f.DAY.notna() & f.AM.notna()]


def stat(parts, rule, out):
    """parts: list of per-market frames of one period. Returns n calls, hit, chance, edge (pp), t over days, mean signed bp."""
    rows = []
    for f in parts:
        r = f[out]; ok = (r != 0)
        up = float((r[ok] > 0).mean())
        b = f[rule]; m = ok & (b != 0)
        hit = (np.sign(r[m]) == b[m]).astype(float)
        exp = np.where(b[m] > 0, up, 1 - up)
        rows.append(pd.DataFrame({"hit": hit, "exp": exp, "bp": b[m] * (r[m] - r[ok].mean())}))
    x = pd.concat(rows)
    if len(x) < 30:
        return dict(n=len(x), hit=np.nan, chance=np.nan, edge=np.nan, t=np.nan, bp=np.nan)
    byday = (x.hit - x.exp).groupby(level=0).mean()                           # one number per day: markets are not independent
    sd = byday.std(ddof=1)
    t = byday.mean() / (sd / np.sqrt(len(byday))) if sd > 0 else 0.0
    return dict(n=len(x), hit=100 * x.hit.mean(), chance=100 * x.exp.mean(), edge=100 * (x.hit - x.exp).mean(), t=t, bp=x.bp.mean())


def main():
    tdir, odir = sys.argv[1], Path(sys.argv[2]); odir.mkdir(parents=True, exist_ok=True)
    F = {s: frame(s, tdir) for s in SYMS}
    H = {"2019-22": lambda f: f[f.index < "2023-01-01"], "2023-26": lambda f: f[f.index >= "2023-01-01"]}
    res = []
    for out in ("AM", "DAY"):
        for rule in RULES:
            for mk in SYMS + ("All",):
                for hn, cut in H.items():
                    parts = [cut(F[s]) for s in (SYMS if mk == "All" else (mk,))]
                    res.append(dict(outcome=out, rule=rule, market=mk, half=hn, **stat(parts, rule, out)))
    R = pd.DataFrame(res); R.to_csv(odir / "hit_rates.csv", index=False, float_format="%.3f")
    lines = []
    for out, lab in (("AM", "09:30 to 11:30"), ("DAY", "09:30 to 16:00")):
        A = R[(R.outcome == out) & (R.market == "All")].pivot(index="rule", columns="half")
        E = R[(R.outcome == out) & (R.market != "All")].pivot_table(index="rule", columns=["half", "market"], values="edge")
        lines += [f"\n## {lab}, ES + NQ + YM pooled by day\n",
                  "| rule | calls 19-22 | hit % | chance % | edge pp | t | calls 23-26 | hit % | chance % | edge pp | t | edge by market 19-22 (ES/NQ/YM) | 23-26 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        order = A["t"]["2019-22"].abs().sort_values(ascending=False).index
        for r in order:
            g = lambda k, h: A[k][h][r]
            em = lambda h: "/".join(f"{E[h][s][r]:+.1f}" if r in E.index and not np.isnan(E[h][s][r]) else "n/a" for s in SYMS)
            lines.append(f"| {r} | " + " | ".join(f"{int(g('n', h))} | {g('hit', h):.1f} | {g('chance', h):.1f} | {g('edge', h):+.1f} | {g('t', h):+.2f}"
                                                 for h in H) + f" | {em('2019-22')} | {em('2023-26')} |")
    n = len(RULES) - 1
    A = R[(R.market == "All") & (R.rule != "always_long")]
    a, b = A[A.half == "2019-22"].set_index(["outcome", "rule"]), A[A.half == "2023-26"].set_index(["outcome", "rule"])
    pick = a[a.t.abs() >= 1.96].index
    lines += ["\n## Chosen on 2019-22 (|t| >= 1.96), checked on 2023-26\n", "| outcome | rule | 19-22 edge pp (t) | 23-26 edge pp (t) | same sign and |t| >= 1.96 in 23-26 |", "|---|---|---|---|---|"]
    for k in pick:
        keep = np.sign(a.edge[k]) == np.sign(b.edge[k]) and abs(b.t[k]) >= 1.96
        lines.append(f"| {k[0]} | {k[1]} | {a.edge[k]:+.1f} ({a.t[k]:+.2f}) | {b.edge[k]:+.1f} ({b.t[k]:+.2f}) | {'YES' if keep else 'no'} |")
    j = a.join(b, lsuffix="_a", rsuffix="_b").dropna(subset=["edge_a", "edge_b"])
    lines.append(f"\n{len(pick)} of {len(a)} rule-outcome tests pass |t| >= 1.96 in 2019-22; about {0.05 * len(a):.1f} are expected by chance alone. "
                 f"Bonferroni bar for {len(a)} tests: |t| >= {abs(__import__('scipy.stats').stats.norm.ppf(0.025 / len(a))):.2f}. "
                 f"Correlation of the edge between the halves across all tests: {np.corrcoef(j.edge_a, j.edge_b)[0, 1]:+.2f}. "
                 f"Largest |t| in 2023-26: {b.t.abs().max():.2f} ({b.t.abs().idxmax()}).")
    # ICT's own dated trades
    ict = pd.read_csv(HERE.parent / "ict_replication_2026-11-13" / "ict_trades.csv", sep="|")
    ict = ict[ict.sym.isin(SYMS)].drop_duplicates(["date", "sym", "side"])
    lines += ["\n## Against ICT's own dated trades (side he took, same market, same day)\n", "| rule | calls | agree | agree % |", "|---|---|---|---|"]
    tot = []
    for rule in RULES:
        k = m = 0
        for _, x in ict.iterrows():
            f = F[x.sym]; d = pd.Timestamp(x.date)
            if d in f.index and f[rule][d] != 0:
                k += 1; m += int(f[rule][d] == (1 if x.side == "long" else -1))
        tot.append((rule, k, m))
    for rule, k, m in sorted(tot, key=lambda z: -(z[2] / z[1] if z[1] else 0)):
        lines.append(f"| {rule} | {k} | {m} | {100 * m / k:.0f} |" if k else f"| {rule} | 0 | | |")
    lines.append(f"\n{len(ict)} trade-sides on {ict.date.nunique()} days ({(ict.side == 'long').sum()} long, {(ict.side == 'short').sum()} short).")
    days = {s: (len(H['2019-22'](F[s])), len(H['2023-26'](F[s]))) for s in SYMS}
    head = [f"Days scored: {days}. Up-day share from 09:30 (ES): AM {100 * (F['ES'].AM > 0).mean():.1f}%, DAY {100 * (F['ES'].DAY > 0).mean():.1f}%.",
            "", "Rules:"] + [f"- `{k}`: {v}" for k, v in RULES.items()]
    (odir / "report.md").write_text("\n".join(head + lines) + "\n")
    print("\n".join(head[:1] + lines))


if __name__ == "__main__":
    main()
