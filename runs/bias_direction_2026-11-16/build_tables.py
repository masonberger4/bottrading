"""Build the engine's 09:30 daily bias table (htf.table with every bias_htf column on) for ES, NQ, YM on fixed-roll 5m data.
Run from an engine checkout (branch mentorship):  python <this file> OUTDIR [SYM ...]"""
import sys, json, time
from pathlib import Path
import pandas as pd
from mentorship import htf, backtest as B, bias_htf as BH
from mentorship.strategy import Params

DATA = Path("/mnt/project-files/mentorship/data/fixed_roll_2026-11-10/")
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
for sym in (sys.argv[2:] or ["ES", "NQ", "YM"]):
    df = pd.read_parquet(DATA / f"{sym}_5min_db.parquet")
    es = pd.read_parquet(DATA / "ES_5min_db.parquet")
    p = Params()
    es_pt = 1.0 if sym == "ES" else round(float(df.close.median() / es.close.median()), 2)
    bx = dict(ord=1, iof=[p.iof_days, p.iof_min],
              pd20=[p.pd_day_range, int(p.pd_body_multiday), p.pd_zone, list(p.ote_band), 0, int(p.pd60_only_consol), float(p.consol_ratio)],
              wk=1, obmt=1, obj=1, mwd=p.mwd_disp_mult, wo=p.weekly_open_early_days, woa=p.weekly_open_array_days,
              nwog=[p.nwog_leave_adr, p.nwog_returns_cons, p.nwog_converge_pts, p.nwog_bias_reclaim or p.nwog_flip_edge, p.nwog_converge_mode, p.nwog_ref, p.nwog_bias_basis],
              bc=1, dpd=1, qs=[p.qs_turn_pct, p.qs_cons_pct, p.qs_due_lo, p.qs_due_hi], wpr=p.wpr_len)
    bx = {**bx, **json.loads(BH.bx_string(p) or "{}")}          # the default engine columns keep their default settings
    kw = B.table_kw(p); kw["bx"] = json.dumps(bx, sort_keys=True, separators=(",", ":"))
    t0 = time.time()
    t = htf.table(df, es_pt, vi=p.vi_arrays, flip_triggers=p.flip_triggers, **kw)
    t.to_pickle(out / f"table_{sym}.pkl")
    print(sym, es_pt, t.shape, round(time.time() - t0), "s", flush=True)
    if sym == "ES":
        print(list(t.columns)); print(t.tail(3).T.to_string())
