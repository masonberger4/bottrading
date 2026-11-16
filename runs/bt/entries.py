"""Entry study from saved trades.   python entries.py OUTDIR ENGINE_DIR [--variant wd_off]
Everything is in R (a trade's result divided by its own entry risk), all markets pooled unless shown.
Part 1  anatomy per setup and market: trades, win rate, average R, total R, t-stat, share stopped out, cost in R.
Part 2  price path after the entry, from the 5m bars, ignoring the engine's own exits: with the trade's own stop and
        a fixed target of 1R / 2R / 3R (flat at 16:00 otherwise), how often is the target hit, against the hit rate a
        coin-flip entry needs to break even (1/(1+k)); and the average signed move 30 / 60 minutes later and at 16:00.
        Also the same entry with the stop 2x / 3x further away and a target at that same distance (a coin flip hits 50%;
        result in units of the wider risk). Rules: the entry bar can stop the trade but cannot hit the target; stop and
        target in one bar counts as a stop.
Part 3  what separates winners from losers: for each setup, each entry-time feature level is compared with the rest
        on 2019-22 and, separately, on 2023-26. A split counts as found when |t| >= 2 on 2019-22, and as confirmed
        when 2023-26 has the same sign with |t| >= 1.64. Chance alone confirms about 5% of the found ones."""
import sys
import numpy as np, pandas as pd
from report import load

OUTCOME_FREE = ["side", "weekday", "news", "htf", "macro", "wbias", "b_react", "b_draw", "b_pd", "conf_n", "td_agree", "judas", "smt_n", "lh_sweet",
                "org_dir", "setup_model", "delivery", "entry_style", "week_idx", "taken_3d", "roll_day", "reentry", "conf_top", "market", "swept", "entry_array_tf"]

def tstat(x):
    x = np.asarray(x, float); return x.mean() / x.std() * len(x) ** .5 if len(x) > 2 and x.std() > 0 else np.nan

def dt(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 2 or len(b) < 2: return np.nan
    se = (a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)) ** .5
    return (a.mean() - b.mean()) / se if se > 0 else np.nan

def features(A):
    F = A[OUTCOME_FREE].copy()
    s = np.where(A.side == "long", 1, -1)
    for c in ("wbias", "b_react", "b_draw", "b_pd", "draw_side"):
        F[c + "_vs_side"] = np.sign(A[c].values * s)
    F["org_vs_side"] = np.where(A.org_dir.isna(), None, np.where((A.org_dir == "discount") == (s > 0), "with", "against"))
    F["delivery_vs_side"] = np.where(A.delivery.isna(), None, np.where((A.delivery == "up") == (s > 0), "with", "against"))
    et = pd.to_datetime(A.entry_time.astype(str).str[:19])
    F["entry_half_hour"] = et.dt.strftime("%H:") + np.where(et.dt.minute < 30, "00", "30")
    A = A.assign(risk_bp=(A.entry - A.stop).abs() / A.entry * 1e4)
    for c in ("risk_bp", "adr5_prev", "adr_prev"):
        F[c + "_third"] = A.groupby("market")[c].transform(lambda x: pd.qcut(x, 3, labels=["low", "mid", "high"], duplicates="drop").astype(object))
    F["conf_n"] = F.conf_n.clip(upper=3); F["swept"] = F.swept.where(F.swept.isin(F.swept.value_counts().head(8).index))
    return F.astype(object)

def paths(A, eng):
    bars = {m: pd.read_csv(f"{eng}/data/mentorship/{m}_5min_db.csv", index_col=0) for m in A.market.unique()}
    for m, b in bars.items():
        b.index = pd.to_datetime(b.index, utc=True); b.columns = [c.lower() for c in b.columns]
    out = []
    for r in A.itertuples():
        b = bars[r.market]; t0 = pd.Timestamp(r.entry_time).tz_convert("UTC")
        end = pd.Timestamp(r.entry_time).normalize() + pd.Timedelta(hours=16)
        i0, i1 = b.index.searchsorted(t0), b.index.searchsorted(end.tz_convert("UTC"))
        w = b.iloc[i0:i1]; s = 1 if r.side == "long" else -1; risk = abs(r.entry - r.stop)
        e = r.entry + r.adj                                    # trades are in contract prices, the bars are back-adjusted (bar = contract + adj)
        d = dict(idx=r.Index)
        if not len(w) or risk <= 0 or w.index[0] != t0:
            out.append(d); continue
        fav = (w.high.values - e) / risk if s > 0 else (e - w.low.values) / risk
        adv = (e - w.low.values) / risk if s > 0 else (w.high.values - e) / risk
        cl = s * (w.close.values - e) / risk
        fav[0] = -np.inf                                       # the entry bar cannot hit a target
        stop_i = np.argmax(adv >= 1) if (adv >= 1).any() else len(w)
        for k in (1, 2, 3):
            hit_i = np.argmax(fav >= k) if (fav >= k).any() else len(w)
            d[f"hit{k}"] = hit_i < stop_i
            d[f"res{k}"] = k if hit_i < stop_i else (-1.0 if stop_i < len(w) else cl[-1])
        d["stopped"] = stop_i < len(w); d["stop_in_entry_bar"] = stop_i == 0
        for m in (2, 3):                                       # wider stop, target the same distance away (1:1): a coin flip hits 50%
            si = np.argmax(adv >= m) if (adv >= m).any() else len(w); hi = np.argmax(fav >= m) if (fav >= m).any() else len(w)
            d[f"wide{m}_hit"] = hi < si; d[f"wide{m}_res"] = 1.0 if hi < si else (-1.0 if si < len(w) else cl[-1] / m)
        d["mfe_before_stop"] = max(0.0, np.max(fav[1:stop_i + 1], initial=0.0)) if stop_i >= 1 else 0.0
        for mins, nm in ((30, "m30"), (60, "m60")):
            j = min(mins // 5, len(w) - 1); d[nm] = cl[j]
        d["close"] = cl[-1]; d["cost_R"] = 2 * r.costs / max(r.shares, 1) / 2 / risk
        out.append(d)
    return pd.DataFrame(out).set_index("idx")

def main():
    out, eng = sys.argv[1], sys.argv[2]; var = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "wd_off"
    T = load(out); A = T[T.variant == var].reset_index(drop=True)
    A["h"] = np.where(A.year <= 2022, 1, 2); pd.set_option("display.width", 250)
    print(f"Variant {var}: {len(A)} trades, {A.market.nunique()} markets, engine {open(f'{out}/ENGINE.txt').read().strip()}\n\nPART 1: anatomy (R)\n")
    rows = []
    for (su, mk), g in list(A.groupby(["setup", "market"])) + [((su, "ALL"), g) for su, g in A.groupby("setup")]:
        rows.append(dict(setup=su, market=mk, trades=len(g), win=(g.R > 0).mean(), avg_R=g.R.mean(), total_R=g.R.sum(), t=tstat(g.R),
                         R_2019_22=g.R[g.h == 1].sum(), R_2023_26=g.R[g.h == 2].sum(), stopped=(g.exit_reason == "stop").mean(),
                         cost_R=(g.costs / ((g.entry - g.stop).abs() * g.shares)).mean()))
    P1 = pd.DataFrame(rows); P1["o"] = P1.setup.map(A.setup.value_counts()); P1 = P1.sort_values(["o", "setup", "market"], ascending=[False, True, True]).drop(columns="o")
    print(P1.round(2).to_string(index=False))
    big = [s for s, n in A.setup.value_counts().items() if n >= 150]
    print("\nPART 2: price path after entry, engine exits ignored (gross R, before costs)\n")
    P = paths(A, eng); A = A.join(P)
    ok = A[A.hit1.notna()]; print(f"(paths found for {len(ok)} of {len(A)} trades)")
    rows = []
    for su, g in [(s, ok[ok.setup == s]) for s in big] + [("ALL SETUPS", ok)]:
        r = dict(setup=su, trades=len(g), engine_avg_R=g.R.mean(), cost_R=g.cost_R.mean(), stopped=g.stopped.astype(float).mean())
        for k in (1, 2, 3):
            r[f"hit_{k}R"] = g[f"hit{k}"].astype(float).mean(); r[f"need_{k}R"] = 1 / (1 + k); r[f"avgR_{k}R_target"] = g[f"res{k}"].mean(); r[f"t_{k}R"] = tstat(g[f"res{k}"])
        r["stop_in_entry_bar"] = g.stop_in_entry_bar.astype(float).mean()
        for m in (2, 3):
            r[f"stop_{m}x_wide_1to1_hit"] = g[f"wide{m}_hit"].astype(float).mean(); r[f"stop_{m}x_wide_avg"] = g[f"wide{m}_res"].mean(); r[f"t_stop_{m}x"] = tstat(g[f"wide{m}_res"])
        for nm in ("m30", "m60", "close"):
            r[f"move_{nm}"] = g[nm].mean(); r[f"t_{nm}"] = tstat(g[nm])
        rows.append(r)
    print(pd.DataFrame(rows).round(2).T.to_string(header=False))
    print("\nSame, 3R target, by market (avg R, t):")
    print(ok[ok.setup.isin(big)].groupby(["setup", "market"]).res3.agg(n="size", avg_R="mean", t=tstat).round(2).unstack("market").to_string())
    print("\nPART 3: feature splits (engine result in R)\n")
    F = features(A); found = []; tested = 0
    for su in big:
        m = (A.setup == su).values
        for c in F.columns:
            for lv in F.loc[m, c].dropna().unique():
                sel = m & (F[c] == lv).values; rest = m & ~sel & F[c].notna().values
                n1, n2 = (sel & (A.h == 1)).sum(), (sel & (A.h == 2)).sum()
                if min(n1, n2, (rest & (A.h == 1)).sum(), (rest & (A.h == 2)).sum()) < 25:
                    continue
                tested += 1
                t1, t2 = dt(A.R[sel & (A.h == 1)], A.R[rest & (A.h == 1)]), dt(A.R[sel & (A.h == 2)], A.R[rest & (A.h == 2)])
                if abs(t1) >= 2:
                    mk = {k: round(A.R[sel & (A.market == k)].mean() - A.R[rest & (A.market == k)].mean(), 2) for k in sorted(A.market.unique())}
                    found.append(dict(setup=su, feature=c, level=lv, n=int(sel.sum()), avgR_level=A.R[sel].mean(), avgR_rest=A.R[rest].mean(), t_2019_22=t1, t_2023_26=t2,
                                      confirmed=bool(np.sign(t1) == np.sign(t2) and abs(t2) >= 1.64), **{f"diff_{k}": v for k, v in mk.items()},
                                      level_R_2023_26=A.R[sel & (A.h == 2)].mean(), level_n_2023_26=int(n2)))
    Fd = pd.DataFrame(found)
    nc = int(Fd.confirmed.sum()) if len(Fd) else 0
    print(f"{tested} splits tested; {len(Fd)} found on 2019-22 (chance alone: about {tested * .0455:.0f}); {nc} confirmed on 2023-26 (chance alone: about {len(Fd) * .05:.1f})\n")
    if len(Fd):
        print(Fd.sort_values(["confirmed", "setup"], ascending=[False, True]).round(2).to_string(index=False))
    P1.to_csv(f"{out}/entries_anatomy.csv", index=False); Fd.to_csv(f"{out}/entries_splits.csv", index=False)

if __name__ == "__main__":
    main()
