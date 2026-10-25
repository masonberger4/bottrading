"""The strategy genome and a fast, cost-aware backtest of it.

A genome is a plain dict. Every `hold` minutes inside its trading window it scores each
stock as a weighted sum of signals, takes up to `slots` positions whose score clears
`threshold`, enters at the next bar's open, and exits at the close `hold` minutes later.
It runs on 1-minute or 5-minute bars (holds shorter than a bar round up to one bar).

The genome carries two playbooks, A and B, each a full set of the genes above, plus a route
for every group of day types (top-tier news, second-tier news, minor news, expirations,
month/quarter turns, futures roll week, plain days): trade playbook A, trade playbook B, or
sit the day out. Routes are per group rather than per day type because single event types
have too few days to learn from. Each playbook also decides what to do with stocks on their
earnings reaction day: trade them like the rest, leave them alone, or trade only them, and
how much weight to give the earnings gap.
Each position is 1/slots of capital, and every round trip pays `cost_bps` per side plus the
SEC fee on the sell. Nothing is held overnight.
"""
from __future__ import annotations

import math
import random

import numpy as np

from .daytypes import DAY_TYPES
from .features import LOOKBACKS, Features

HOLDS = (1, 2, 3, 5, 10, 15, 20, 30, 45, 60, 90, 120)      # minutes
MODES = ("neutral", "directional", "long", "short")
WEIGHTS = ("w_rev", "w_mom", "w_vwap", "w_orb", "w_vol", "w_day", "w_gap", "w_earn",
           "w_imb", "w_depth", "w_flow")      # the last three use recorded order-book data
EARNINGS = ("include", "exclude", "only")
SEC_FEE_BPS = 0.278       # $27.80 per $1M sold

ROUTES = ("skip", "A", "B")
DAY_GROUPS = {
    "top_news": ("fomc", "cpi", "jobs"),
    "news": ("pce", "ppi", "retail_sales", "gdp"),
    "minor_news": ("ism_manufacturing", "ism_services", "jolts", "sentiment"),
    "expiration": ("quad_witching", "opex"),
    "month_turn": ("quarter_end", "month_end", "quarter_start", "month_start"),
    "roll_week": ("roll_week",),
    "plain": ("mon", "tue", "wed", "thu", "fri"),
}
GROUP_OF = {t: grp for grp, ts in DAY_GROUPS.items() for t in ts}
assert set(GROUP_OF) == set(DAY_TYPES)

# gene -> (kind, low, high); "f" = float, "i" = int, "c" = index into a choice list
PLAYBOOK = {
    **{w: ("f", -2.0, 2.0) for w in WEIGHTS},
    "k_rev": ("c", 0, len(LOOKBACKS) - 1),
    "k_mom": ("c", 0, len(LOOKBACKS) - 1),
    "threshold": ("f", 0.0, 4.0),
    "hold": ("c", 0, len(HOLDS) - 1),
    "slots": ("i", 1, 10),
    "start": ("i", 0, 330),       # minutes after 09:30
    "length": ("i", 30, 390),     # minutes
    "mode": ("c", 0, len(MODES) - 1),
    "earnings": ("c", 0, len(EARNINGS) - 1),
}
GENES = {**{f"{p}.{k}": v for p in "AB" for k, v in PLAYBOOK.items()},
         **{f"r.{grp}": ("c", 0, len(ROUTES) - 1) for grp in DAY_GROUPS}}


def playbook(g: dict, p: str) -> dict:
    return {k[2:]: v for k, v in g.items() if k.startswith(p + ".")}


def route(g: dict, day_type: str) -> str:
    return ROUTES[g[f"r.{GROUP_OF[day_type]}"]]


def random_genome(rng: random.Random) -> dict:
    g = {}
    for name, (kind, lo, hi) in GENES.items():
        g[name] = round(rng.uniform(lo, hi), 3) if kind == "f" else rng.randint(lo, hi)
    return g


def describe(g: dict, bar_minutes: int = 1) -> str:
    used = {p: [grp for grp in DAY_GROUPS if ROUTES[g[f"r.{grp}"]] == p] for p in ROUTES}
    parts = [f"playbook {p} ({', '.join(used[p])}): {describe_playbook(playbook(g, p), bar_minutes)}"
             for p in "AB" if used[p]]
    return "; ".join(parts + [f"sits out: {', '.join(used['skip']) or 'nothing'}"])


def describe_playbook(g: dict, bar_minutes: int = 1) -> str:
    w = ", ".join(f"{k[2:]} {g[k]:+.2f}" for k in WEIGHTS if abs(g[k]) >= 0.05)
    start = g["start"]
    end = min(start + g["length"], 390)
    hm = lambda m: f"{9 + (30 + m) // 60}:{(30 + m) % 60:02d}"
    lb = lambda k: f"{LOOKBACKS[k] * bar_minutes} min"
    return (f"{MODES[g['mode']]}, hold {max(HOLDS[g['hold']], bar_minutes)} min, "
            f"{g['slots']} slots, threshold {g['threshold']:.2f}, entries {hm(start)}-{hm(end)}, "
            f"rev lookback {lb(g['k_rev'])}, mom lookback {lb(g['k_mom'])}, "
            f"earnings-day stocks: {EARNINGS[g['earnings']]}; weights: {w or 'none'}")


def hold_bars(g: dict, bar_minutes: int) -> int:
    return max(1, round(HOLDS[g["hold"]] / bar_minutes))


def score(g: dict, f: Features, rows: np.ndarray) -> np.ndarray:
    """Composite score (rows x symbols). Positive = expect the stock to rise. Stocks the
    playbook won't trade today score 0, which never clears the threshold."""
    s = (g["w_rev"] * -f.idio[LOOKBACKS[g["k_rev"]]][rows]
            + g["w_mom"] * f.z[LOOKBACKS[g["k_mom"]]][rows]
            + g["w_vwap"] * -f.vwap[rows]
            + g["w_orb"] * f.orb[rows]
            + g["w_vol"] * f.volshock[rows]
            + g["w_day"] * f.dayret[rows]
            + g["w_gap"] * f.gap[rows]
            + g["w_earn"] * f.gap[rows] * f.earn[f.day[rows]]
            + g["w_imb"] * f.imb[rows]
            + g["w_depth"] * f.depth[rows]
            + g["w_flow"] * f.flow[rows])
    rule = EARNINGS[g.get("earnings", 0)]
    if rule == "exclude":
        s = np.where(f.earn[f.day[rows]], 0.0, s)
    elif rule == "only":
        s = np.where(f.earn[f.day[rows]], s, 0.0)
    return s


def decision_bars(g: dict, f: Features) -> np.ndarray:
    """Bars within the day at whose close the strategy decides, given its window and hold.
    Every position is closed by the session's last bar."""
    hold = hold_bars(g, f.bar_minutes)
    start = g["start"] // f.bar_minutes
    end = min((g["start"] + g["length"]) // f.bar_minutes, f.bars_per_day - 1 - hold)
    return np.arange(start, end, hold) if end > start else np.array([], int)


def select(g: dict, s: np.ndarray) -> np.ndarray:
    """Turn scores into positions: +1 long, -1 short, 0 flat (rows x symbols)."""
    k, thr, mode = g["slots"], g["threshold"], MODES[g["mode"]]
    pos = np.zeros_like(s)
    order = np.argsort(s, axis=1)
    rr = np.arange(len(s))[:, None]
    if mode == "neutral":
        n = max(1, k // 2)
        top, bot = order[:, -n:], order[:, :n]
        pos[rr, top] = np.where(s[rr, top] > thr, 1.0, 0.0)
        pos[rr, bot] = np.where(s[rr, bot] < -thr, -1.0, pos[rr, bot])
    elif mode == "directional":
        mag = np.argsort(np.abs(s), axis=1)[:, -k:]
        pos[rr, mag] = np.where(np.abs(s[rr, mag]) > thr, np.sign(s[rr, mag]), 0.0)
    elif mode == "long":
        top = order[:, -k:]
        pos[rr, top] = np.where(s[rr, top] > thr, 1.0, 0.0)
    else:
        bot = order[:, :k]
        pos[rr, bot] = np.where(s[rr, bot] < -thr, -1.0, 0.0)
    return pos


def backtest(g: dict, f: Features, days: range, cost_bps: float = 1.5) -> dict:
    """Simulate the genome over the given day numbers (each day routed to its playbook or
    skipped). Returns daily returns and stats; skipped days count as flat days."""
    daily = np.zeros(len(days))
    n = wins = 0
    if len(days) == 0:
        return _stats(daily, 0, 0.0)
    d0 = days[0]
    days = np.asarray(days)
    for p in "AB":
        pd_ = days[[route(g, f.day_type[d]) == p for d in days]]
        b = playbook(g, p)
        bars = decision_bars(b, f)
        if len(pd_) == 0 or len(bars) == 0:
            continue
        hold = hold_bars(b, f.bar_minutes)
        rows = (pd_[:, None] * f.bars_per_day + bars[None, :]).ravel()
        pos = select(b, score(b, f, rows))
        gross = np.log(f.close[rows + hold] / f.open[rows + 1])
        cost = (2 * cost_bps + SEC_FEE_BPS) / 1e4
        pnl = (pos * gross - np.abs(pos) * cost).sum(axis=1) / b["slots"]
        np.add.at(daily, f.day[rows] - d0, pnl)
        n += int(np.abs(pos).sum())
        wins += int((pos * gross > 0).sum())
    return _stats(daily, n, wins / n if n else 0.0)


def _stats(daily: np.ndarray, trades: int, hit: float) -> dict:
    mu, sd = float(daily.mean()), float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    sharpe = mu / sd * math.sqrt(252) if sd > 0 else 0.0
    return {"daily": daily, "trades": trades, "hit_rate": hit, "sharpe": sharpe,
            "mean_bps_day": mu * 1e4, "total_pct": float(np.expm1(daily.sum()) * 100),
            "worst_day_bps": float(daily.min() * 1e4) if len(daily) else 0.0}


def fitness(st: dict, n_days: int) -> float:
    """Annualized Sharpe of daily returns, shrunk when the sample of trades is small, so a
    handful of lucky trades can't win."""
    if st["trades"] < 3 * n_days:
        return -10.0 + st["trades"] / max(1, 3 * n_days)
    return st["sharpe"] * min(1.0, st["trades"] / (20 * n_days)) ** 0.5
