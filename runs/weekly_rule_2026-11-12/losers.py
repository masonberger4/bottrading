"""Why pm_sb and am_mm lose (week-done off, ES 5m, $1k risk, 2019-26). Prints splits of $ / win rate / avg R by trade features.
Usage: python losers.py [variant] [setup ...]"""
import sys, glob, warnings
import pandas as pd, numpy as np
warnings.filterwarnings("ignore")
O = "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/out"
v = sys.argv[1] if len(sys.argv) > 1 else "wd_off"
setups = sys.argv[2:] or ["pm_sb", "am_mm", "lunch", "pm_last_hour"]
T = pd.concat([pd.read_csv(f, low_memory=False) for f in glob.glob(f"{O}/trades_{v}_*.csv")]).copy()
T["y"] = T.year
T["half"] = np.where(T.y <= 2022, "19-22", "23-26")
sd = np.where(T.side == "long", 1, -1)
T["risk_pts"] = (T.entry - T.stop).abs()
T["rr_t1"] = ((T.t1 - T.entry) * sd / T.risk_pts).round(1)
T["bias_ok"] = np.sign(T.b_draw) == sd
T["react_ok"] = np.sign(T.b_react) == sd
T["pd_ok"] = np.sign(T.b_pd) == sd
T["hhmm"] = pd.to_datetime(T.entry_time.str[:16]).dt.strftime("%H:%M").str[:4] + "0"
T["cost_R"] = T.costs / (T.net.abs() + 1e-9)
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 300)


def agg(g):
    return pd.Series({"n": len(g), "net": round(g.net.sum()), "win": round((g.net > 0).mean(), 2), "avgR": round(g.R.mean(), 2),
                      "costs": round(g.costs.sum())})


for s in setups:
    G = T[T.setup == s]
    print(f"\n===================== {s}: {len(G)} trades, ${G.net.sum():,.0f}, win {(G.net > 0).mean():.2f}, avg R {G.R.mean():.2f}, costs ${G.costs.sum():,.0f}")
    for col in ["half", "y", "side", "exit_reason", "entry_kind", "setup_model", "entry_style", "bias_ok", "react_ok", "pd_ok", "news",
                "day_type", "hhmm", "smt", "sb_win", "judas", "unicorn", "delivery", "rr_t1"]:
        if col not in G or G[col].isna().all():
            continue
        x = G.groupby(G[col].astype(str)).apply(agg)
        if len(x) > 25:
            x = x.sort_values("n", ascending=False).head(15)
        print(f"--- by {col}"); print(x.T.to_string())
    print("--- R distribution:", G.R.describe().round(2).to_dict())
    print("--- risk pts:", G.risk_pts.describe().round(2).to_dict())
