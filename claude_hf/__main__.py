"""Command line.

  python -m claude_hf fetch --minutes 5            # ~9 months of 5-minute bars, 40 stocks
  python -m claude_hf fetch --minutes 1            # ~7 weeks of 1-minute bars
  python -m claude_hf evolve --minutes 5 --seeds 5 # run the self-improvement loop
  python -m claude_hf paper                        # paper trade the saved champion
  python -m claude_hf record                       # record live quotes + order book daily
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path


def cmd_fetch(a):
    from . import data
    data.fetch(minutes=a.minutes, days=a.days)


def cmd_evolve(a):
    from . import data, features
    from .evolve import Search, random_baseline
    f = features.build(data.load_panel(a.minutes))
    out = Path(a.out) / f"{a.minutes}min"
    best = None
    for seed in range(1, a.seeds + 1):
        s = Search(f, seed=seed, cost_bps=a.cost, out=out / f"seed{seed}")
        s.run(generations=a.generations, patience=a.patience, quiet=True)
        r = s.report()
        json.dump(r, open(out / f"seed{seed}" / "report.json", "w"), indent=1, default=float)
        print(f"seed {seed}: " + "  ".join(
            f"{k} sharpe {r[k]['sharpe']:6.2f} ({r[k]['mean_bps_day']:+.1f} bps/day, {r[k]['trades']} trades)"
            for k in ("train", "val", "test")))
        # the champion is chosen on validation only; test never influences the choice
        if best is None or r["val"]["sharpe"] > best["val"]["sharpe"]:
            best = r
    best["random_baseline_test"] = random_baseline(f, s.test, cost_bps=a.cost)
    print(f"\npicked on validation: {best['describe']}")
    print(f"test: sharpe {best['test']['sharpe']:.2f}, {best['test']['mean_bps_day']:+.1f} bps/day; "
          f"at 2x costs sharpe {best['test']['sharpe_at_2x_cost']:.2f}; random genomes on the same "
          f"days: median {best['random_baseline_test']['median']:.2f}")
    if a.save:
        json.dump(best, open(a.save, "w"), indent=1, default=float)
        print(f"champion -> {a.save}")


def cmd_paper(a):
    from . import paper
    paper.run(a.champion, a.journal, a.cost)


def cmd_record(a):
    from . import recorder
    recorder.run(days=a.days)


def main():
    ap = argparse.ArgumentParser(prog="claude_hf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--minutes", type=int, default=5, choices=[1, 5])
    p.add_argument("--days", type=int)
    p = sub.add_parser("evolve")
    p.add_argument("--minutes", type=int, default=5, choices=[1, 5])
    p.add_argument("--seeds", type=int, default=5)
    p.add_argument("--generations", type=int, default=1000)
    p.add_argument("--patience", type=int, default=200)
    p.add_argument("--cost", type=float, default=1.5, help="bps per side for spread + slippage")
    p.add_argument("--out", default="runs/claude_hf")
    p.add_argument("--save", help="write the validation-picked champion here")
    p = sub.add_parser("paper")
    p.add_argument("--champion", default="claude_hf/champion.json")
    p.add_argument("--journal", default="runs/claude_hf/paper_trades.csv")
    p.add_argument("--cost", type=float, default=1.5)
    p = sub.add_parser("record")
    p.add_argument("--days", type=int, help="stop after this many sessions (default: run on)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    {"fetch": cmd_fetch, "evolve": cmd_evolve, "paper": cmd_paper, "record": cmd_record}[a.cmd](a)


if __name__ == "__main__":
    main()
