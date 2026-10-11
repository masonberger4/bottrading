"""Historical backtest: replay bars through Strategy + PaperBroker and summarize."""
from __future__ import annotations

import pandas as pd

from .config import Instrument, Params
from .data import bar_minutes, iter_bars
from .execution import PaperBroker, step
from .strategy import Strategy


def run(df: pd.DataFrame, inst: Instrument, params: Params, qty: int | None = None):
    strat = Strategy(inst, params, bar_minutes=bar_minutes(df))
    broker = PaperBroker(inst, params, qty)
    setups = 0
    for bar in iter_bars(df):
        _, acts = step(strat, broker, bar)
        setups += sum(a.kind == "submit" for a in acts)
    trades = pd.DataFrame([t.as_dict() for t in broker.trades])
    return trades, summarize(trades, setups, df)


def _block(t: pd.DataFrame) -> dict:
    if t.empty:
        return {"trades": 0}
    wins, losses = t.pnl[t.pnl > 0], t.pnl[t.pnl <= 0]
    eq = t.pnl.cumsum()
    return {
        "trades": len(t),
        "win_rate_%": round(100 * len(wins) / len(t), 1),
        "avg_points": round(t.points.mean(), 2),
        "net_$": round(t.pnl.sum(), 2),
        "profit_factor": round(wins.sum() / -losses.sum(), 2) if losses.sum() < 0 else float("inf"),
        "avg_win_$": round(wins.mean(), 2) if len(wins) else 0.0,
        "avg_loss_$": round(losses.mean(), 2) if len(losses) else 0.0,
        "max_drawdown_$": round((eq - eq.cummax()).min(), 2),
    }


def summarize(t: pd.DataFrame, setups: int, df: pd.DataFrame) -> dict:
    days = df.index.normalize().nunique()
    out = {"period": f"{df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}", "days": days,
           "setups_signalled": setups, "overall": _block(t)}
    if not t.empty:
        out["by_window"] = {w: _block(g) for w, g in t.groupby("window")}
        out["by_side"] = {s: _block(g) for s, g in t.groupby("side")}
        out["exit_reasons"] = t.reason.value_counts().to_dict()
    return out


def format_summary(s: dict) -> str:
    lines = [f"Period {s['period']}  ({s['days']} days)  setups signalled: {s['setups_signalled']}"]

    def fmt(name, b):
        if b.get("trades", 0) == 0:
            return f"  {name:<8} no trades"
        return (f"  {name:<8} n={b['trades']:<4} win {b['win_rate_%']:>5}%  avg {b['avg_points']:+.2f} pts  "
                f"net ${b['net_$']:+,.0f}  PF {b['profit_factor']}  maxDD ${b['max_drawdown_$']:,.0f}")
    lines.append(fmt("ALL", s["overall"]))
    for k in ("by_window", "by_side"):
        for name, b in s.get(k, {}).items():
            lines.append(fmt(name, b))
    if "exit_reasons" in s:
        lines.append("  exits: " + ", ".join(f"{k} {v}" for k, v in s["exit_reasons"].items()))
    return "\n".join(lines)
