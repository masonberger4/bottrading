"""python summary.py OUTDIR -> OUTDIR/summary.txt. Tables for the ICT-calls morning engine test (see README.md)."""
import sys
import numpy as np, pandas as pd
pd.set_option("display.width", 300)
rng = np.random.default_rng(7)


def ts(x):
    return x.mean() / x.std() * len(x) ** .5 if len(x) > 1 and x.std() else 0.0


def stat(t, days):
    if not len(t):
        return dict(call_days=days, trades=0)
    t = t.sort_values("entry_time"); eq = t.net.cumsum().values
    dd = (eq - np.maximum.accumulate(np.maximum(eq, 0))).min()
    b = [rng.choice(t.R.values, len(t)).mean() for _ in range(4000)]
    d = dict(call_days=days, trades=len(t), win=f"{(t.net > 0).mean() * 100:.0f}%", R=round(t.R.mean(), 2), t=round(ts(t.R), 1),
             R_range=f"{np.percentile(b, 2.5):+.2f} to {np.percentile(b, 97.5):+.2f}", total=round(t.net.sum()), maxdd=round(dd))
    if "shares" in t and t.shares.notna().any():
        d["med_risk"] = round(((t.entry - t.stop).abs() * t.shares).median())
    return d


def luck(T, D, suffix=""):
    """His side against a coin-flip side on the same days: share of 20,000 random side choices that did at least as well."""
    lo, sh = (T[T.variant == v].groupby("id").R.sum() for v in ("long_only", "short_only"))
    ids = D.id.values
    L, S = lo.reindex(ids).fillna(0).values, sh.reindex(ids).fillna(0).values
    his = np.where(D.sign.values > 0, L, S).sum()
    flips = rng.integers(0, 2, (20000, len(ids))).astype(bool)
    sims = np.where(flips, L, S).sum(1)
    return his, sims.mean(), np.percentile(sims, 2.5), np.percentile(sims, 97.5), (sims >= his).mean()


def main():
    out = sys.argv[1]
    T, D, A = (pd.read_csv(f"{out}/{f}.csv") for f in ("trades_calls", "call_days", "trades_alldays"))
    groups = {
        "MAIN: morning calls that end by 12:00, clearly before the move": D[(D.kind == "am_end") & (D.before == "yes")],
        "morning calls that end by 12:00, all": D[D.kind == "am_end"],
        "  of those, NQ": D[(D.kind == "am_end") & (D.sym == "NQ")],
        "  of those, ES": D[(D.kind == "am_end") & (D.sym == "ES")],
        "  of those, the call was right at his horizon": D[(D.kind == "am_end") & (D.win_end == 1)],
        "  of those, the call was wrong": D[(D.kind == "am_end") & (D.win_end == 0)],
        "morning calls with a longer horizon (to 16:00 or beyond)": D[D.kind == "am_longer"],
        "evening calls and outlooks, traded the next morning": D[D.kind == "prior_eve"],
        "every call that has a morning to trade": D,
    }
    order = ["his_side", "no_side", "opposite", "his_side_after_call", "no_side_after_call", "opposite_after_call",
             "plain_same_stop", "plain_typical_stop", "plain_opposite", "plain_late15", "plain_late30", "plain_other_days",
             "plain_half_stop", "plain_double_stop", "plain_1R", "plain_3R", "plain_hold_to_noon"]
    txt = ("R = average result a trade in units of its own risk (x $1,000 = $ a trade). t under about 2 cannot be told from zero.\n"
           "R_range = 95% range for R by resampling the trades. total and maxdd in $ at $1,000 risk a trade, no cap. med_risk = $ risked.\n"
           "his_side / opposite / no_side: the narrow morning engine allowed to trade only his side / only the other side / either.\n"
           "..._after_call: same, no entry before the call's time (and none after a later opposite call that morning).\n"
           "plain_same_stop: his side at the 09:30 open (or the call time if later), stop as far away as the engine's trade that day, 2R, flat 12:00 (only days the engine traded his side).\n"
           "plain_typical_stop / plain_opposite: the same plain entry on every call day, stop 0.25% (NQ) / 0.21% (ES) away, his side / the other side.\n"
           "plain_late15 / plain_late30: plain_typical_stop entered 15 / 30 minutes later (call times are estimates).\n"
           "plain_other_days: chance. The same side, time and stop on every other day within 60 days of the call (not a call day).\n"
           "plain_half_stop / double_stop / 1R / 3R: plain_typical_stop with one setting changed. plain_hold_to_noon: no stop or target, held to 12:00, in units of the typical stop.\n")
    for name, d in groups.items():
        t = T[T.id.isin(d.id)]
        rows = [dict(variant=v, **stat(t[t.variant == v], len(d))) for v in order]
        txt += f"\n{name}: {len(d)} calls on {d[['day', 'sym']].drop_duplicates().shape[0]} market-days, {d.win_end.mean() * 100:.0f}% right at his horizon\n"
        txt += pd.DataFrame(rows).to_string(index=False) + "\n"
        if len(d) >= 10:
            h, m, a, b, pv = luck(t, d)
            txt += f"  his side {h:+.1f} R in total; a coin-flip side on the same days averages {m:+.1f} R (95% range {a:+.1f} to {b:+.1f}); {pv * 100:.0f}% of coin-flip runs did at least as well\n"
    # --- all days, and the hindsight ceiling
    txt += "\nEvery day 2019-26 (reference). hindsight = the engine allowed only the side of the 09:30 -> 12:00 move, which is known only afterwards.\n"
    A["year"] = pd.to_datetime(A.date).dt.year
    rows = []
    for sym in ("NQ", "ES"):
        a = A[A.symbol == sym]
        hind = a[((a.variant == "long_only") & (a.am_move > 0)) | ((a.variant == "short_only") & (a.am_move < 0))]
        anti = a[((a.variant == "long_only") & (a.am_move < 0)) | ((a.variant == "short_only") & (a.am_move > 0))]
        for nm, x in (("no_side", a[a.variant == "no_side"]), ("hindsight side", hind), ("hindsight wrong side", anti)):
            for per, y in (("2019-26", x), ("2023-26", x[x.year >= 2023])):
                rows.append(dict(market=sym, variant=nm, period=per, **stat(y, y.date.nunique())))
    txt += pd.DataFrame(rows).rename(columns={"call_days": "days_traded"}).to_string(index=False) + "\n"
    his = T[(T.variant == "his_side") & (T.kind == "am_end")]
    txt += "\nMorning calls ending by 12:00, his side, by exit: " + "; ".join(
        f"{k} {int(v['count'])} trades {v['mean']:+.2f} R" for k, v in his.groupby("exit_reason").R.agg(["count", "mean"]).iterrows()) + "\n"
    txt += "By year: " + "; ".join(f"{k} {int(v['count'])} trades {v['sum']:+,.0f} $" for k, v in
                                  his.groupby(pd.to_datetime(his.date).dt.year).net.agg(["count", "sum"]).iterrows()) + "\n"
    open(f"{out}/summary.txt", "w").write(txt); print(txt)


if __name__ == "__main__":
    main()
