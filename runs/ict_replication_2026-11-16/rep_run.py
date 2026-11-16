"""Replication runner (2026-11-16): one engine year on ES or NQ at 5m or 1m with a per-day setup funnel, no sizing cap.
    python runs/ict_replication_2026-11-16/rep_run.py YEAR SYM NAME "dict(...)" OUTDIR [TF]
NQ is run as its own book (es_pt scaled by the price ratio, ES as the SMT partner), as in the 11-13 check."""
import os, sys, time
os.environ["MENTORSHIP_SRC"] = "databento"
sys.path.insert(0, os.getcwd())
from collections import Counter
from dataclasses import replace
import pandas as pd
if os.environ.get("ICT_TRACE"):            # diagnostic: the traced copy of strategy.py (trace_patch.py) takes the module's place
    import importlib.util, mentorship
    _sp = importlib.util.spec_from_file_location("mentorship.strategy", "mentorship/strategy_traced.py")
    _m = importlib.util.module_from_spec(_sp); sys.modules["mentorship.strategy"] = _m; _sp.loader.exec_module(_m)
    mentorship.strategy = _m
from mentorship import study as S, backtest as B, strategy as ST

year, sym, name = int(sys.argv[1]), sys.argv[2], sys.argv[3]
kw = eval(sys.argv[4]) if len(sys.argv) > 4 else {}
out = sys.argv[5] if len(sys.argv) > 5 else "."
tf = int(sys.argv[6]) if len(sys.argv) > 6 else 5
S.DEC_BASE.update(risk_dollars=1000.0, max_notional=1e12)          # Mase 2026-11-16: no sizing cap in backtests
ST.FUNNEL = Counter()
if os.environ.get("ICT_TRACE"):
    _ict = pd.read_csv(os.path.dirname(os.path.abspath(__file__)) + "/ict_trades.csv", sep="|", dtype=str)
    ST.TRACE_DAYS |= set(_ict.date[_ict.sym == sym])
rows, cap = [], {}
run_day0, run0 = B.run_day, B.run


def run_day(*a, **k):
    before = Counter(ST.FUNNEL)
    r = run_day0(*a, **k)
    d = k["df"].index[-1].date() if "df" in k else a[0].index[-1].date()
    for key, n in (ST.FUNNEL - before).items():
        rows.append((str(d), k.get("symbol", ""), key, n))
    return r


def run(*a, **k):
    t = run0(*a, **k)
    cap.setdefault("attrs", t.attrs)
    return t


B.run_day, B.run = run_day, run
if os.environ.get("ICT_ORACLE"):
    # Entry-model test: the sweep / shift / entry scan runs ONLY on ICT's days, on HIS side, from 45 minutes before his
    # entry to 15 minutes after it.  It takes the direction and the time from him, so what is left is whether the
    # engine's entry model finds his entry.  Runner-side only (no engine switch): this is a measurement, not a strategy.
    import re
    _i2 = pd.read_csv(os.path.dirname(os.path.abspath(__file__)) + "/ict_trades.csv", sep="|", dtype=str).fillna("")
    _win = {}
    for _x in _i2[_i2.sym == sym].itertuples():
        _ts = re.findall(r"\d\d:\d\d", _x.t_entry)
        _m = [int(v[:2]) * 60 + int(v[3:]) for v in _ts]
        _lo, _hi = (_m[0] - 45, _m[-1] + 15) if _m else {"AM": (525, 720), "PM": (720, 960)}.get(_x.t_entry, (480, 960))
        _win.setdefault(_x.date, []).append((1 if _x.side == "long" else -1, _lo, _hi))
    _scan0, _orders = ST._scan, []

    def _scan(ctx, sd, i, *a, **k):
        w = _win.get(str(ctx.day))
        if not w or not any(sg == sd.sign and lo <= ctx.t[i] <= hi for sg, lo, hi in w):
            return None
        o = _scan0(ctx, sd, i, *a, **k)
        if o is not None:                    # every order the scan armed on his side (filled or not), in contract prices
            adj = float(ctx.adj[i]) if getattr(ctx, "adj", None) is not None else 0.0
            _orders.append((str(ctx.day), f"{int(ctx.t[i]) // 60:02d}:{int(ctx.t[i]) % 60:02d}", sd.sign, o.get("setup"), o.get("entry_kind"),
                            round(float(sd.x(o["entry"])) - adj, 2), round(float(sd.x(o["stop"])) - adj, 2)))
        return o

    ST._scan = _scan
t0 = time.time()
if sym == "ES":
    S.DECISIONS[name] = kw
    t = S._dec_job((tf, year, name))
else:
    df, pa = B.load("ES", tf, source="databento"), B.load("NQ", tf, source="databento")
    a, b = pd.Timestamp(f"{year}-01-01", tz=B.NY), pd.Timestamp(f"{year + 1}-01-01", tz=B.NY)
    lo = a - pd.Timedelta(days=45)
    p = replace(ST.Params(), **{**S.DEC_BASE, **kw})
    q = replace(p, es_pt=round(p.es_pt * float(pa.close.median() / df.close.median()), 2), cost_per_share=0.25)
    t = B.run(pa[(pa.index >= lo) & (pa.index < b)], tf, "NQ", q, df[(df.index >= lo) & (df.index < b)],
              meta=B.load_meta("NQ", tf, "databento"), lock_cuts={} if p.draw_lock == "off" else None)
    if len(t):
        t = t[pd.to_datetime(t.entry_time.astype(str).str[:10]) >= f"{year}-01-01"].copy()
tag = f"{sym}_{name}_{year}"
t.to_csv(f"{out}/trades_{tag}.csv", index=False)
pd.DataFrame(cap.get("attrs", {}).get("skips", [])).to_csv(f"{out}/skips_{tag}.csv", index=False)
pd.DataFrame(rows, columns=["day", "symbol", "key", "n"]).to_csv(f"{out}/funnel_{tag}.csv", index=False)
if os.environ.get("ICT_TRACE"):
    tr = pd.DataFrame(ST.TRACE, columns=["day", "t", "session", "side", "label"])
    tr.groupby(["day", "t", "session", "side", "label"], dropna=False).size().rename("n").reset_index().to_csv(f"{out}/trace_{tag}.csv", index=False)
if os.environ.get("ICT_ORACLE"):
    pd.DataFrame(_orders, columns=["day", "armed", "side", "setup", "entry_kind", "entry", "stop"]).to_csv(f"{out}/orders_{tag}.csv", index=False)
print(tag, f"tf{tf}", len(t), "trades", round(time.time() - t0), "s", flush=True)
