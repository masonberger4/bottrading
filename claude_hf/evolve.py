"""The recursive self-improvement loop.

Days are split in time order into train / validation / test. Each generation mutates the
current champion into a batch of candidates. A candidate replaces the champion only if it
beats it on training days AND on validation days, after costs. The test days are never
looked at during the search; they are scored once, at the end.

The loop also improves how it searches. It keeps a step size and a mutation rate for every
gene and a success score for every mutation operator; changes that led to an accepted
champion get used more and bigger, the rest shrink. Each generation is logged to JSONL.
"""
from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path

import numpy as np

from . import strategy as S
from .features import Features

OPERATORS = ("tweak", "reset_gene", "cross_random", "cross_archive")


class Search:
    def __init__(self, f: Features, seed: int = 1, split=(0.6, 0.2), cost_bps: float = 1.5,
                 batch: int = 24, out: Path | None = None):
        self.f, self.cost, self.batch = f, cost_bps, batch
        self.rng = random.Random(seed)
        n = f.days
        a, b = int(n * split[0]), int(n * (split[0] + split[1]))
        self.train, self.val, self.test = range(0, a), range(a, b), range(b, n)
        self.step = {g: (hi - lo) * (0.15 if k == "f" else 0.1) for g, (k, lo, hi) in S.GENES.items()}
        self.rate = {g: 1.5 / len(S.GENES) for g in S.GENES}
        self.op_score = {o: 1.0 for o in OPERATORS}
        self.archive: list[dict] = []
        self.out = out
        if out:
            out.mkdir(parents=True, exist_ok=True)
            self.log = open(out / "generations.jsonl", "w")

    # --- evaluation -------------------------------------------------------------------
    def fit(self, g: dict, days: range) -> tuple[float, dict]:
        st = S.backtest(g, self.f, days, self.cost)
        return S.fitness(st, len(days)), st

    # --- mutation operators -----------------------------------------------------------
    def _clip(self, name, x):
        kind, lo, hi = S.GENES[name]
        x = min(max(x, lo), hi)
        return round(x, 3) if kind == "f" else int(round(x))

    def mutate(self, g: dict) -> tuple[dict, str, list]:
        ops, w = zip(*self.op_score.items())
        op = self.rng.choices(ops, weights=w)[0]
        c = copy.deepcopy(g)
        if op == "cross_random" or (op == "cross_archive" and not self.archive):
            op, donor = "cross_random", S.random_genome(self.rng)
        elif op == "cross_archive":
            donor = self.rng.choice(self.archive)
        changed = []
        for name in S.GENES:
            if self.rng.random() >= self.rate[name]:
                continue
            if op == "tweak":
                c[name] = self._clip(name, c[name] + self.rng.gauss(0, self.step[name]))
            elif op == "reset_gene":
                c[name] = S.random_genome(self.rng)[name]
            else:
                c[name] = donor[name]
            changed.append(name)
        if not changed:                       # always change something
            name = self.rng.choice(list(S.GENES))
            c[name] = self._clip(name, c[name] + self.rng.gauss(0, self.step[name]) + 1e-3)
            changed.append(name)
        return c, op, changed

    def _learn(self, op: str, changed: list, won: bool):
        """Self-tuning of the search itself (the 'recursive' part)."""
        self.op_score[op] = 0.9 * self.op_score[op] + (1.0 if won else 0.05)
        self.op_score[op] = max(self.op_score[op], 0.05)
        for name in changed:
            kind, lo, hi = S.GENES[name]
            if won:
                self.step[name] = min(self.step[name] * 1.3, (hi - lo) / 2)
                self.rate[name] = min(self.rate[name] * 1.15, 0.6)
            else:
                self.step[name] = max(self.step[name] * 0.995, (hi - lo) * 0.01)
                self.rate[name] = max(self.rate[name] * 0.998, 0.02)

    # --- main loop --------------------------------------------------------------------
    def run(self, generations: int = 300, init: int = 400, patience: int = 120, quiet=False):
        t0 = time.time()
        seeds = [S.random_genome(self.rng) for _ in range(init)]
        scored = sorted(((self.fit(g, self.train)[0], g) for g in seeds), key=lambda x: -x[0])
        champ = scored[0][1]
        champ_tr, champ_va = scored[0][0], self.fit(champ, self.val)[0]
        self.archive.append(champ)
        self._write({"gen": 0, "accepted": True, "train": champ_tr, "val": champ_va, "genome": champ})
        stale = 0
        for gen in range(1, generations + 1):
            cands = [self.mutate(champ) for _ in range(self.batch)]
            evals = sorted(((self.fit(c, self.train)[0], c, op, ch) for c, op, ch in cands),
                           key=lambda x: -x[0])
            accepted = None
            for tr, c, op, ch in evals:
                if tr <= champ_tr:
                    break
                va = self.fit(c, self.val)[0]
                if va > champ_va:
                    accepted = (tr, va, c, op, ch)
                    break
            for tr, c, op, ch in evals:
                self._learn(op, ch, accepted is not None and c is accepted[2])
            if accepted:
                champ_tr, champ_va, champ = accepted[0], accepted[1], accepted[2]
                self.archive.append(champ)
                stale = 0
            else:
                stale += 1
            self._write({"gen": gen, "accepted": bool(accepted), "train": champ_tr, "val": champ_va,
                         "op": accepted[3] if accepted else None,
                         "changed": accepted[4] if accepted else None,
                         "op_score": {k: round(v, 3) for k, v in self.op_score.items()},
                         "genome": champ if accepted else None})
            if accepted and not quiet:
                print(f"gen {gen:4d}  train {champ_tr:6.2f}  val {champ_va:6.2f}  via {accepted[3]}")
            if stale >= patience:
                break
        self.champion = champ
        self.elapsed = time.time() - t0
        return champ

    def report(self, g: dict | None = None) -> dict:
        g = g or self.champion
        out = {"genome": g, "describe": S.describe(g, self.f.bar_minutes),
               "bar_minutes": self.f.bar_minutes, "cost_bps_per_side": self.cost,
               "days": {"train": len(self.train), "val": len(self.val), "test": len(self.test)},
               "dates": {k: [str(self.f.index[r[0] * self.f.bars_per_day].date()),
                             str(self.f.index[r[-1] * self.f.bars_per_day].date())]
                         for k, r in (("train", self.train), ("val", self.val), ("test", self.test))}}
        for name, days in (("train", self.train), ("val", self.val), ("test", self.test)):
            st = S.backtest(g, self.f, days, self.cost)
            stress = S.backtest(g, self.f, days, self.cost * 2)
            out[name] = {k: v for k, v in st.items() if k != "daily"}
            out[name]["daily_bps"] = [round(x * 1e4, 1) for x in st["daily"]]
            out[name]["sharpe_at_2x_cost"] = stress["sharpe"]
            out[name]["mean_bps_day_at_2x_cost"] = stress["mean_bps_day"]
        # how each kind of day did outside the training period
        held = np.r_[np.asarray(self.val), np.asarray(self.test)]
        daily = S.backtest(g, self.f, range(held[0], held[-1] + 1), self.cost)["daily"]
        out["held_out_by_day_type"] = {
            t: {"days": int(sum(m)), "route": S.route(g, t),
                "mean_bps": round(float(daily[np.array(m)].mean() * 1e4), 1)}
            for t in sorted(set(self.f.day_type[d] for d in held))
            for m in [[self.f.day_type[d] == t for d in held]]}
        return out

    def _write(self, rec):
        if self.out:
            self.log.write(json.dumps(rec, default=float) + "\n")
            self.log.flush()


def random_baseline(f: Features, days: range, n: int = 300, seed: int = 99, cost_bps=1.5):
    """Test-period Sharpe of random genomes: what 'no skill' looks like on these days."""
    rng = random.Random(seed)
    sh = [S.backtest(S.random_genome(rng), f, days, cost_bps)["sharpe"] for _ in range(n)]
    return {"median": float(np.median(sh)), "p90": float(np.percentile(sh, 90)),
            "p10": float(np.percentile(sh, 10))}
