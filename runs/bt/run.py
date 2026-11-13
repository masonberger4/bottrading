"""Standard backtest runner (2026-11-13). One engine commit, per-year trade files cached, any market, any switch set.

Run from an engine checkout (cwd = repo root of the pinned mentorship commit):
    python <path>/runs/bt/run.py --out OUTDIR [--sym ES,NQ,YM] [--years 2019-2026] [--workers 4] name="dict(...)" ...
"defaults" always runs. A variant dict may hold "_excl": a tuple of setup names whose orders are dropped before they
are placed (runner-side, no engine change), e.g.  pwhl_x="dict(week_done_on_draw='skip',week_done_levels=('pwh','pwl'),_excl=('am_mm','pm_sb'))".

Markets: ES is the engine's own setup (ES traded, NQ and YM as partners). NQ / YM runs put that market first, scale
es_pt by the price ratio to ES (what the engine's own two-market combine does) and charge the same $5 a side per
contract (ES 0.10 pt, NQ 0.25 pt, YM 1.0 pt). Each market keeps its own table cache (runs/mentorship under
OUTDIR/_work/<SYM>), because the engine's cache file name does not include the symbol.
Output: OUTDIR/trades_<SYM>_<name>_<year>.csv (+ skips_...). Finished jobs are skipped on a rerun. Report: report.py."""
import argparse, os, sys, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
COST = {"ES": 0.10, "NQ": 0.25, "YM": 1.0}                 # price points per side = $5 a contract
ORDER = {"ES": ("ES", "NQ", "YM"), "NQ": ("NQ", "ES", "YM"), "YM": ("YM", "ES", "NQ")}


def job(j):
    sym, year, name, kw = j
    import pandas as pd
    from dataclasses import replace  # noqa
    from mentorship import study as S, backtest as B, strategy as ST
    S.SYMS = ORDER[sym]
    kw = dict(kw); excl = set(kw.pop("_excl", ()))
    if excl and not getattr(ST, "_bt_excl", None):
        fo0 = ST._finish_order
        def fo(*a, **k):
            o = fo0(*a, **k)
            return None if o is not None and o.get("setup") in ST._bt_excl else o
        ST._finish_order = fo
    ST._bt_excl = excl
    base = dict(risk_dollars=1000.0)
    if sym != "ES":
        es, me = B.load("ES", 5, source="databento"), B.load(sym, 5, source="databento")
        base.update(es_pt=round(float(me.close.median() / es.close.median()), 2), cost_per_share=COST[sym])
    S.DEC_BASE.update(base)
    S.DECISIONS[name] = kw
    cap = {}
    if not getattr(B, "_bt_wrapped", False):
        run0 = B.run
        def run(*a, **k):
            t = run0(*a, **k); B._bt_cap.setdefault("attrs", t.attrs); return t
        B.run, B._bt_wrapped = run, True
    B._bt_cap = cap
    t = S._dec_job((5, year, name))
    at = cap.get("attrs", {})
    sk = at.get("skips") or []
    sk = pd.DataFrame(sk, columns=["day", "symbol", "stage", "reason"][:len(sk[0])] if sk else ["day", "symbol", "stage", "reason"])
    if len(t):
        t["market"] = sym
    return t, sk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--sym", default="ES"); ap.add_argument("--years", default="2019-2026")
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--one-sym", default=None, help=argparse.SUPPRESS)
    ap.add_argument("variants", nargs="*")
    a = ap.parse_args()
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    if a.one_sym is None:                                   # parent: one child process per market, each in its own work dir
        eng = Path.cwd()
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "mentorship"], capture_output=True, text=True).stdout.strip()
        (out / "ENGINE.txt").write_text(f"{commit}{' +local changes' if dirty else ''}\n")
        for sym in a.sym.split(","):
            w = out / "_work" / sym; (w / "runs" / "mentorship").mkdir(parents=True, exist_ok=True)
            for d in sorted(x.name for x in eng.iterdir() if x.is_dir() and x.name != "runs" and not x.name.startswith(".")):
                if not (w / d).exists():
                    try:
                        os.symlink(eng / d, w / d, target_is_directory=True)
                    except OSError:                         # Windows without symlink rights: a junction
                        subprocess.run(["cmd", "/c", "mklink", "/J", str(w / d), str(eng / d)], check=True)
            r = subprocess.run([sys.executable, "-W", "ignore", str(Path(__file__).resolve()), "--out", str(out), "--one-sym", sym,
                                "--years", a.years, "--workers", str(a.workers), *a.variants], cwd=w)
            if r.returncode:
                sys.exit(r.returncode)
        return
    sym = a.one_sym
    os.environ["MENTORSHIP_SRC"] = "databento"
    sys.path.insert(0, os.getcwd())
    y0, _, y1 = a.years.partition("-"); years = range(int(y0), int(y1 or y0) + 1)
    variants = {"defaults": {}}
    for v in a.variants:
        n, e = v.split("=", 1); variants[n] = eval(e)
    jobs = [(sym, y, n, kw) for n, kw in variants.items() for y in years]
    path = lambda j, k="trades": out / f"{k}_{j[0]}_{j[2]}_{j[1]}.csv"
    todo = [j for j in jobs if not path(j).exists()]
    print(f"{sym}: {len(jobs)} jobs, {len(todo)} to do", flush=True)
    if not todo:
        return
    from concurrent.futures import ProcessPoolExecutor, as_completed
    from mentorship import study as S
    S.SYMS = ORDER[sym]
    S._bias_cache(5, kw=S.B.table_kw(S.Params()))           # build this market's bias table once, before the workers
    bad = 0
    with ProcessPoolExecutor(a.workers, max_tasks_per_child=1) as ex:
        futs = {ex.submit(job, j): j for j in todo}
        for k, f in enumerate(as_completed(futs), 1):
            j = futs[f]
            try:
                t, sk = f.result()
                sk.to_csv(path(j, "skips"), index=False); t.to_csv(path(j), index=False)
                print(f"{k}/{len(todo)} {sym} {j[2]} {j[1]}: {len(t)} trades", flush=True)
            except Exception as e:
                import traceback; traceback.print_exc(); bad += 1
                print(f"{k}/{len(todo)} {sym} {j[2]} {j[1]} FAILED {type(e).__name__}: {e}", flush=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
