"""Option C groundwork (PR #82): the tests that sit on top of out/days.csv (build_days.py).

    python runs/learn_ict_2026-11-16/model.py [--days out/days.csv] [--calls FILE] [--a-cols FILE] [--out out/report.txt]

Four parts, all "choose on 2019-22, check on 2023-26" unless said otherwise:
  1. each signed column alone against what the market did next (a cross-check for option A, not a replacement),
  2. a direction model on all columns (logistic regression and small boosted trees),
  3. a day model: can the one-way mornings be told apart at 09:30,
  4. learning ICT's own picks from a calls file, then testing that model on the MARKET in 2019-22, years his calls
     do not touch.
Hooks:
  --calls   option B's log: CSV with columns date, market, side (long / short / none), and optionally before (1 = said
            before the move), source. Default: the 41 dated trades (runs/ict_replication_2026-11-13/ict_trades.csv).
  --a-cols  option A's per-day columns: CSV with day, (market), and any columns named s_* (signed, + = bullish) or
            c_* (unsigned). They are joined on and used like the built-in ones.
Outcomes are in ADR units (1.0 = one 5-day average daily range). No entries, stops or costs here: this measures
whether the side and the day can be picked at all, which PR #82 names as the missing piece."""
import argparse, warnings
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

warnings.filterwarnings("ignore")
HERE = Path(__file__).resolve().parent
CHOOSE, CHECK = (2019, 2022), (2023, 2026)
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a); print(s); OUT.append(s)


def load(days, a_cols=None):
    F = pd.read_csv(days, parse_dates=["day"])
    if a_cols:
        A = pd.read_csv(a_cols); A["day"] = pd.to_datetime(A[[c for c in A.columns if c in ("day", "date")][0]])
        keep = [c for c in A.columns if c.startswith(("s_", "c_"))]
        A = A[["day"] + (["market"] if "market" in A else []) + keep].rename(columns={c: c[:2] + "a_" + c[2:] for c in keep})
        F = F.merge(A, on=["day", "market"] if "market" in A else ["day"], how="left")
        say(f"joined {len(keep)} columns from option A: {a_cols}")
    F["year"] = F.day.dt.year
    return F


def cols(F):
    s = [c for c in F.columns if c.startswith("s_")]; c = [c for c in F.columns if c.startswith("c_")]
    return s, c


def per(F, p):
    return F[(F.year >= p[0]) & (F.year <= p[1])]


def score(side, out, day):
    """side = +1 / -1 / 0 per row, out = what the market did (ADR). Rows are averaged per day first, because ES, NQ
    and YM on the same day are nearly one observation. Returns n days, hit %, mean ADR per day, t-stat."""
    d = pd.DataFrame({"day": day.values, "r": np.asarray(side) * np.asarray(out), "on": np.asarray(side) != 0})
    d = d[d.on & d.r.notna()]
    if not len(d):
        return 0, np.nan, np.nan, np.nan
    g = d.groupby("day").r.mean()
    t = g.mean() / (g.std(ddof=1) / np.sqrt(len(g))) if len(g) > 2 and g.std() > 0 else np.nan
    return len(g), 100 * (g > 0).mean(), g.mean(), t


def fmt(x):
    n, h, m, t = x
    return f"{n:5d} {h:5.1f}% {m:+.3f} t={t:+.1f}" if n else "    0     -      -      -"


def design(F, use, mu=None, sd=None):
    X = F[use].astype(float).clip(-5, 5)
    if mu is None:
        mu, sd = X.mean(), X.std().replace(0, 1)
    return ((X - mu) / sd).fillna(0.0).values, mu, sd


# ---- 1. single columns ---------------------------------------------------------------------------------------------
def part1(F):
    s, _ = cols(F)
    say("\n== 1. Each signed column alone: trade its side every day it is not zero ==")
    say("   09:30 to 11:30 (o_am), days / hit % / mean ADR / t-stat.  Both halves must agree for a column to count.")
    say(f"   {'column':15s} {'2019-22':>32s}   {'2023-26':>32s}   same sign")
    rows = []
    for c in s:
        a = score(np.sign(per(F, CHOOSE)[c].fillna(0)), per(F, CHOOSE).o_am, per(F, CHOOSE).day)
        b = score(np.sign(per(F, CHECK)[c].fillna(0)), per(F, CHECK).o_am, per(F, CHECK).day)
        rows.append((c, a, b))
        ok = "yes" if a[2] * b[2] > 0 else "no"
        say(f"   {c:15s} {fmt(a):>32s}   {fmt(b):>32s}   {ok}")
    for nm, sd in (("always long", 1),):
        a = score(np.full(len(per(F, CHOOSE)), sd), per(F, CHOOSE).o_am, per(F, CHOOSE).day)
        b = score(np.full(len(per(F, CHECK)), sd), per(F, CHECK).o_am, per(F, CHECK).day)
        say(f"   {nm:15s} {fmt(a):>32s}   {fmt(b):>32s}")
    n = len(rows); big = [r for r in rows if abs(r[1][3]) > 2]
    say(f"   {len(big)} of {n} columns have |t| > 2 in 2019-22 (about {0.05 * n:.1f} expected by chance); "
        f"{sum(1 for r in big if r[1][2] * r[2][2] > 0 and abs(r[2][3]) > 2)} of those repeat with |t| > 2 in 2023-26.")
    return rows


# ---- 2. direction model --------------------------------------------------------------------------------------------
def fit_dir(tr, use, y):
    X, mu, sd = design(tr, use)
    half = tr.year <= (CHOOSE[0] + CHOOSE[1]) // 2                      # pick the penalty on 2019-20 -> 2021-22
    best = None
    for C in (0.001, 0.003, 0.01, 0.03, 0.1, 1.0):
        m = LogisticRegression(C=C, max_iter=500).fit(X[half.values], y[half.values])
        ll = -np.mean(np.log(np.where(y[~half.values] == 1, m.predict_proba(X[~half.values])[:, 1], m.predict_proba(X[~half.values])[:, 0])))
        if best is None or ll < best[0]:
            best = (ll, C)
    lr = LogisticRegression(C=best[1], max_iter=500).fit(X, y)
    gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.03, max_iter=150, min_samples_leaf=60, l2_regularization=1.0,
                                        random_state=0).fit(X, y)
    return dict(lr=lr, gb=gb, mu=mu, sd=sd, C=best[1], use=use)


def part2(F):
    s, c = cols(F)
    use = s + c
    say("\n== 2. Direction model on all columns (fit 2019-22, checked 2023-26) ==")
    say("   'all days' = take the model's side every day; 'surest fifth' = only days as confident as the top 20% of 2019-22.")
    models = {}
    for tgt, label in (("o_am", "09:30-11:30"), ("o_day", "09:30-16:00"), ("o_big", "side of the day's largest move")):
        tr, te = per(F, CHOOSE).dropna(subset=[tgt]), per(F, CHECK).dropna(subset=[tgt])
        M = fit_dir(tr, use, (tr[tgt] > 0).astype(int).values)
        models[tgt] = M
        say(f"   target {label}  (logistic penalty C={M['C']})")
        for k in ("lr", "gb"):
            ptr = M[k].predict_proba(design(tr, use, M["mu"], M["sd"])[0])[:, 1]
            pte = M[k].predict_proba(design(te, use, M["mu"], M["sd"])[0])[:, 1]
            thr = np.quantile(np.abs(ptr - 0.5), 0.8)
            auc = roc_auc_score((te[tgt] > 0).astype(int), pte)
            say(f"     {'logistic' if k == 'lr' else 'trees   '}  2019-22 fit {fmt(score(np.sign(ptr - 0.5), tr[tgt], tr.day))}"
                f" | 2023-26 all days {fmt(score(np.sign(pte - 0.5), te[tgt], te.day))}  AUC {auc:.3f}"
                f" | surest fifth {fmt(score(np.where(np.abs(pte - 0.5) >= thr, np.sign(pte - 0.5), 0), te[tgt], te.day))}")
        say(f"     always long        2023-26 all days {fmt(score(np.ones(len(te)), te[tgt], te.day))}")
    lr = models["o_am"]["lr"]
    w = pd.Series(lr.coef_[0], index=use).sort_values(key=np.abs, ascending=False).head(8)
    say("   largest logistic weights (09:30-11:30): " + ", ".join(f"{k} {v:+.2f}" for k, v in w.items()))
    return models


# ---- 3. day model --------------------------------------------------------------------------------------------------
def part3(F):
    s, c = cols(F)
    F = F.copy()
    for k in s:
        F["m_" + k[2:]] = F[k].abs()
    use = c + ["m_" + k[2:] for k in s]
    tr, te = per(F, CHOOSE).dropna(subset=["o_am_eff"]), per(F, CHECK).dropna(subset=["o_am_eff"])
    say("\n== 3. Day model: can a one-way morning be told apart at 09:30? (fit 2019-22, checked 2023-26) ==")
    res = {}
    for name, f in (("one-way morning (ends 60%+ of its range from the open)", lambda d: (d.o_am_eff >= 0.6)),
                    ("big morning (range above the 2019-22 median)", lambda d: (d.o_am_rng >= tr.o_am_rng.median()))):
        ytr, yte = f(tr).astype(int).values, f(te).astype(int).values
        X, mu, sd = design(tr, use)
        m = LogisticRegression(C=0.03, max_iter=500).fit(X, ytr)
        p = m.predict_proba(design(te, use, mu, sd)[0])[:, 1]
        thr = np.quantile(m.predict_proba(X)[:, 1], 0.8)
        say(f"   {name}: base rate {100 * yte.mean():.1f}%, AUC 2023-26 {roc_auc_score(yte, p):.3f}, "
            f"rate on the model's top fifth {100 * yte[p >= thr].mean():.1f}% ({(p >= thr).sum()} rows)")
        res[name] = (m, mu, sd, use, thr)
    return res


# ---- 4. learn ICT's picks ------------------------------------------------------------------------------------------
def read_calls(path):
    p = Path(path)
    if p.name == "ict_trades.csv":
        t = pd.read_csv(p, sep="|"); t = t.rename(columns={"sym": "market"})[["date", "market", "side"]]; t["before"] = 0
    else:
        t = pd.read_csv(p)
        if "before" not in t:
            t["before"] = 1
    t["day"] = pd.to_datetime(t.date); t["side"] = t.side.str.lower().str.strip()
    return t


def part4(F, calls_path, dir_models):
    s, c = cols(F)
    t = read_calls(calls_path)
    say(f"\n== 4. Learning ICT's own picks  (calls file: {calls_path}) ==")
    g = t[t.side.isin(["long", "short"])].groupby(["day", "market"]).side.agg(lambda x: x.iloc[0] if x.nunique() == 1 else "both").reset_index()
    none = t[t.side == "none"][["day", "market"]].drop_duplicates()
    say(f"   {len(t)} rows -> {len(g)} market-days with a side ({(g.side == 'both').sum()} with both sides, left out of the side model), "
        f"{len(none)} stated no-trade days, {int(t.before.sum())} rows marked as said before the move.")
    L = F.merge(g, on=["day", "market"], how="left")
    one = L[L.side.isin(["long", "short"])].copy()
    say(f"   matched to the day table: {len(one)} one-sided market-days, {one.day.min().date() if len(one) else '-'} to {one.day.max().date() if len(one) else '-'}")
    if len(one) < 20:
        say("   too few to fit anything."); return
    y = (one.side == "long").astype(int).values
    # 4a. do the built-in columns agree with the side he took?
    say("   4a. Share of his one-sided days where each signed column pointed his way (zero days left out):")
    agree = []
    for k in s:
        v = np.sign(one[k].fillna(0).values); on = v != 0
        if on.sum() >= 10:
            agree.append((k, on.sum(), 100 * (v[on] == np.where(y[on] == 1, 1, -1)).mean()))
    agree.sort(key=lambda r: -abs(r[2] - 50))
    say("       " + "; ".join(f"{k} {p:.0f}% of {n}" for k, n, p in agree[:10]))
    say(f"       (with {len(one)} days, anything between about {50 - 100 / np.sqrt(len(one)):.0f}% and {50 + 100 / np.sqrt(len(one)):.0f}% is indistinguishable from a coin)")
    for tgt in ("o_am", "o_day"):
        M = dir_models[tgt]
        p = M["lr"].predict_proba(design(one, M["use"], M["mu"], M["sd"])[0])[:, 1]
        say(f"       the part-2 market model ({tgt}) picks his side on {100 * ((p > 0.5) == (y == 1)).mean():.0f}% of them")
    say(f"       he was long on {100 * y.mean():.0f}% of them; the market's 09:30-11:30 move went his way on "
        f"{100 * (np.sign(one.o_am) == np.where(y == 1, 1, -1)).mean():.0f}% and 09:30-16:00 on {100 * (np.sign(one.o_day) == np.where(y == 1, 1, -1)).mean():.0f}%")
    # 4b. side model, leave-one-day-out
    X, mu, sd = design(one, s)
    dd = one.day.values; hit = []
    for d in np.unique(dd):
        tr_, te_ = dd != d, dd == d
        if len(np.unique(y[tr_])) < 2:
            continue
        m = LogisticRegression(C=0.03, max_iter=500).fit(X[tr_], y[tr_])
        hit += list(m.predict(X[te_]) == y[te_])
    say(f"   4b. Side model (signed columns only, heavy penalty), each day predicted from the others: {100 * np.mean(hit):.0f}% of {len(hit)} right"
        f" (always-{'long' if y.mean() >= 0.5 else 'short'} gets {100 * max(y.mean(), 1 - y.mean()):.0f}%)")
    side_m = LogisticRegression(C=0.03, max_iter=500).fit(X, y)
    # 4c. day model: his days against the other trading days in the months he was posting
    L["ym"] = L.day.dt.to_period("M")
    months = L[L.side.notna()].ym.unique()
    pool = L[L.ym.isin(months)].copy()
    his_days = set(pool[pool.side.notna()].day)
    pool = pool[pool.side.notna() | ~pool.day.isin(his_days)]          # on his days keep only the market he traded
    if len(none):
        pool = pool.merge(none.assign(no_trade=1), on=["day", "market"], how="left")
        if pool.no_trade.sum() >= 30:                                   # enough stated passes: use only those as the "no" days
            pool = pool[pool.side.notna() | (pool.no_trade == 1)]
    yd = pool.side.notna().astype(int).values
    for k in s:
        pool["m_" + k[2:]] = pool[k].abs(); F["m_" + k[2:]] = F[k].abs()
    used = c + ["m_" + k[2:] for k in s]
    Xd, mud, sdd = design(pool, used)
    pr = np.full(len(pool), np.nan)
    for mth in pool.ym.unique():
        tr_, te_ = (pool.ym != mth).values, (pool.ym == mth).values
        if yd[tr_].sum() < 5 or yd[te_].sum() == 0 and te_.sum() == 0:
            continue
        pr[te_] = LogisticRegression(C=0.03, max_iter=500, class_weight="balanced").fit(Xd[tr_], yd[tr_]).predict_proba(Xd[te_])[:, 1]
    ok = ~np.isnan(pr)
    auc = roc_auc_score(yd[ok], pr[ok]) if len(np.unique(yd[ok])) == 2 else np.nan
    say(f"   4c. Day model: {yd.sum()} of his market-days against {len(yd) - yd.sum()} market-days on the other dates of the same months, each month predicted from the others: AUC {auc:.3f} (0.5 = no better than chance)")
    day_m = LogisticRegression(C=0.03, max_iter=500, class_weight="balanced").fit(Xd, yd)
    # 4d. the test that matters: use both models on market days his calls do not touch
    first = one.day.min().year
    clean = F[(F.year >= CHOOSE[0]) & (F.year < first)].copy() if first > CHOOSE[0] else per(F, CHOOSE).copy()
    say(f"   4d. Both models run on the market in {clean.year.min()}-{clean.year.max()} (years with none of his calls in them):")
    ps = side_m.predict_proba(design(clean, s, mu, sd)[0])[:, 1]
    pdy = day_m.predict_proba(design(clean, used, mud, sdd)[0])[:, 1]
    sd_ = np.sign(ps - 0.5); top = pdy >= np.quantile(pdy, 0.8)
    for tgt in ("o_am", "o_day"):
        say(f"       {tgt}: his-side model every day {fmt(score(sd_, clean[tgt], clean.day))} | on the fifth of days most like his "
            f"{fmt(score(np.where(top, sd_, 0), clean[tgt], clean.day))} | on the rest {fmt(score(np.where(~top, sd_, 0), clean[tgt], clean.day))}")
    say(f"       mornings on the days most like his: one-way {100 * (clean.o_am_eff[top] >= 0.6).mean():.1f}% vs {100 * (clean.o_am_eff[~top] >= 0.6).mean():.1f}% on the rest; "
        f"range {clean.o_am_rng[top].mean():.2f} vs {clean.o_am_rng[~top].mean():.2f} ADR")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", default=str(HERE / "out" / "days.csv"))
    ap.add_argument("--calls", default=str(HERE.parent / "ict_replication_2026-11-13" / "ict_trades.csv"))
    ap.add_argument("--a-cols", default=None)
    ap.add_argument("--out", default=str(HERE / "out" / "report.txt"))
    a = ap.parse_args()
    F = load(a.days, a.a_cols)
    say(f"day table: {len(F)} market-days, {F.day.nunique()} days, {F.day.min().date()} to {F.day.max().date()}, "
        f"{len(cols(F)[0])} signed and {len(cols(F)[1])} day columns")
    part1(F); M = part2(F); part3(F); part4(F, a.calls, M)
    Path(a.out).write_text("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
