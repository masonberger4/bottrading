"""Price check and larger sample for the overnight-gap scalp (`ndog_scalp`), 2026-11-16. Results only, no engine change.

Run from an engine checkout (cwd = repo root of the pinned mentorship commit, data/mentorship holding the fixed-roll
<S>_5min_db / <S>_1min_db / <S>_1min_dbraw / <S>_1min_dbmeta files):
    python <path>/runs/ndog_check_2026-11-16/ndog.py OUTDIR [TRADES_DIR]

1. Calls the engine's own `sm4.ndog_scalp` on EVERY complete session's evening, ES / NQ / YM, 2016-26 (the engine only
   reaches it on days its daytime rules did not skip), with the runner's settings ($1,000 risk, no size cap, NQ / YM
   scaled by the price ratio to ES, $5 a side per contract).
2. Replays each trade on the 1-minute bars (same adjusted series) and on the raw front-month prices, under three fill models:
     eng   the engine's own result (5m bars, target filled on a touch, costs only)
     thru  1m bars, the target limit fills only when price trades through it; stop first when both are in one minute
     slip  thru + one tick of slippage on the market entry and on every stop / time exit
3. TRADES_DIR (the unpacked bt_nocap_2026-11-16 trades) marks which of these the full engine run took, and checks they match.
"""
import glob, sys, types, warnings
from dataclasses import replace
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
sys.path.insert(0, ".")
from mentorship import study as S, backtest as B, sm4

OUT = sys.argv[1]; TR = sys.argv[2] if len(sys.argv) > 2 else None
COST = {"ES": 0.10, "NQ": 0.25, "YM": 1.0}; TICK = {"ES": .25, "NQ": .25, "YM": 1.0}
es5 = B.load("ES", 5, source="databento")
rows = []
for sym in ("ES", "NQ", "YM"):
    df, m1, meta = B.load(sym, 5, source="databento"), B.load(sym, 1, source="databento"), B.load_meta(sym, 1)
    raw = B.load_raw(sym, 1)
    base = dict(S.DEC_BASE, risk_dollars=1000.0, max_notional=1e12)
    if sym != "ES":
        base.update(es_pt=round(float(df.close.median() / es5.close.median()), 2), cost_per_share=COST[sym])
    p = replace(S.Params(), **base)
    ctx = types.SimpleNamespace(tf=5, equity=1e9)
    cost, tick = p.cost_per_share, TICK[sym]
    for g in B.days(df, 5):
        d = g.index[0].date()
        for tr in sm4.ndog_scalp(ctx, sm4.post_evening(df, d), p, d, sym, {}):
            sg = 1 if tr.side == "long" else -1
            et, xt, xpx, _, why = pd.Timestamp(tr.entry_time), *tr.exits[0]
            entry, stop, tgt = float(tr.entry), float(tr.stop), float(tr.t1)
            risk = (entry - stop) * sg
            sh = int(1000.0 / risk)
            day0 = pd.Timestamp(d, tz=df.index.tz)
            path = m1.loc[et:day0 + pd.Timedelta(hours=24) - pd.Timedelta(minutes=1)]
            mm = meta.loc[day0 + pd.Timedelta(hours=16):path.index[-1]]
            adj = float(mm.adj.loc[path.index[0]])
            rb = raw.loc[path.index[0]] if path.index[0] in raw.index else None
            res = {}
            for mode in ("touch", "thru"):                       # 1m replay
                r_ = None
                for ts, b in path.iterrows():
                    if (b.open - stop) * sg <= 0: r_ = (ts, "stop_gap", float(b.open)); break
                    if (b.low <= stop) if sg > 0 else (b.high >= stop): r_ = (ts, "stop", stop); break
                    far = b.high if sg > 0 else b.low
                    if ((far - tgt) * sg >= 0) if mode == "touch" else ((far - tgt) * sg > 1e-9): r_ = (ts, "t1", tgt); break
                res[mode] = r_ or (path.index[-1], "asia_end", float(path.close.iloc[-1]))
            def R(px, why_, slip=0.0):
                s_ = slip * (1 + (why_ != "t1"))                 # entry always; exit unless it is the target limit
                return ((px - entry) * sg - 2 * cost - s_) / risk
            pre, e18 = m1.loc[day0 + pd.Timedelta(hours=16):day0 + pd.Timedelta(hours=16, minutes=59)], m1.loc[day0 + pd.Timedelta(hours=18):]
            rows.append(dict(date=str(d), market=sym, side=tr.side, signal=str(tr.armed), entry_time=str(et), entry=entry, stop=stop, t1=tgt, risk=round(risk, 2),
                             gap=round(float(e18.open.iloc[0] - pre.close.iloc[-1]), 2), shares=sh, exit_time=str(xt), exit_reason=why, exit=float(xpx),
                             R_eng=round(R(float(xpx), why), 4), m1_touch=res["touch"][1], m1_touch_t=str(res["touch"][0])[11:16],
                             m1_thru=res["thru"][1], R_thru=round(R(res["thru"][2], res["thru"][1]), 4), R_slip=round(R(res["thru"][2], res["thru"][1], tick), 4),
                             adj=adj, raw_entry=entry - adj, raw_open_1m=(float(rb.open) if rb is not None else np.nan),
                             entry_px_ok=bool(abs(float(path.open.iloc[0]) - entry) < 1e-9), entry_lag_min=int((path.index[0] - et).seconds // 60),
                             roll_evening=bool(mm.instrument_id.nunique() > 1), vol_entry_min=int(path.volume.iloc[0]),
                             cost_R=round(2 * cost / risk, 4), tick_R=round(tick / risk, 4)))
    print(sym, "done", len(rows), flush=True)
t = pd.DataFrame(rows)
t["year"] = t.date.str[:4].astype(int)
t["period"] = np.where(t.year <= 2018, "2016-18", np.where(t.year <= 2022, "2019-22", "2023-26"))
t["in_engine"] = False
if TR:
    e = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(f"{TR}/trades_*_wd_off_*.csv"))], ignore_index=True)
    e = e[e.setup == "ndog_scalp"]
    k = t.merge(e[["date", "market", "entry", "stop", "t1", "R", "exit_reason"]], on=["date", "market"], how="left", suffixes=("", "_e"))
    t["in_engine"] = k.entry_e.notna().values
    ok = k[k.entry_e.notna()]
    print(f"engine run's scalp trades: {len(e)} | found here: {len(ok)} | same entry/stop/target: "
          f"{int(((ok.entry == ok.entry_e) & ((ok.stop - ok.stop_e).abs() < .011) & ((ok.t1 - ok.t1_e).abs() < .011)).sum())} | same exit: {int((ok.exit_reason == ok.exit_reason_e).sum())}"
          f" | max |R diff|: {(ok.R_eng - ok.R).abs().max():.3f}")
t.to_csv(f"{OUT}/ndog_all_trades.csv", index=False)
