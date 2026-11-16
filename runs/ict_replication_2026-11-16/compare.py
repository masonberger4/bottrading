"""Line up ICT's video trades (ict_trades.csv) with traced engine runs (rep_run.py outputs).
    python compare.py OUTDIR VARIANT [VARIANT ...]     -> compare_<VARIANT>.csv + a count per variant
Match = same side, entry inside ICT's stated minutes +/- 30 min (AM = 09:30-12:00, PM = 12:00-16:00, no time = any time
that day) and within 6 ES / 25 NQ points of his entry (no price check when his price is unreadable).
"same day, same side" is the looser count: the engine was on his side that day at another time or price.
"opposite" is a chance check: an engine trade the OTHER way inside the same minutes and price band.  When the engine
trades many times a day this count comes close to the match count, and the matches say little."""
import sys, re, pandas as pd
OUT, VARS = sys.argv[1], sys.argv[2:]
HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
ict = pd.read_csv(f"{HERE}/ict_trades.csv", sep="|", dtype=str).fillna("")
TOL = {"ES": 6.0, "NQ": 25.0}


def mins(s):
    h, m = s.split(":"); return int(h) * 60 + int(m)


def window(t):
    ts = re.findall(r"\d\d:\d\d", t)
    if ts:
        return mins(ts[0]) - 30, mins(ts[-1]) + 30
    return {"AM": (570, 720), "PM": (720, 960)}.get(t, (0, 1440))


def rd(k, sym, v, y):
    try:
        return pd.read_csv(f"{OUT}/{k}_{sym}_{v}_{y}.csv")
    except Exception:
        return pd.DataFrame()


for v in VARS:
    rows, n_match, n_side, n_run, n_opp = [], 0, 0, 0, 0
    for _, x in ict.iterrows():
        y = x.date[:4]
        t, f = rd("trades", x.sym, v, y), rd("funnel", x.sym, v, y)
        line = {"id": x.id, "date": x.date, "sym": x.sym, "ict": f"{x.side} {x.t_entry} @{x.entry}", "match": "", "engine": "not run", "funnel": ""}
        if not len(f) and not len(t):
            rows.append(line); continue
        n_run += 1
        t = t[t.date == x.date] if len(t) else t
        f = f[f.day == x.date] if len(f) else f
        lo, hi = window(x.t_entry)
        px = float(x.entry) if x.entry else None
        m = s = opp = False
        tr = []
        for r in t.itertuples():
            tm = mins(str(r.entry_time)[11:16])
            ok = r.side == x.side and lo <= tm <= hi and (px is None or abs(r.entry - px) <= TOL[x.sym])
            m |= ok; s |= r.side == x.side
            opp |= r.side != x.side and lo <= tm <= hi and (px is None or abs(r.entry - px) <= TOL[x.sym])
            tr.append(f"{'*' if ok else ''}{r.setup}/{r.entry_kind} {r.side} {str(r.entry_time)[11:16]} @{r.entry:.2f} stop {r.stop:.2f} out {str(r.exit_time)[11:16]} {r.exit_reason} {r.R:+.2f}R")
        n_match += m; n_side += s; n_opp += opp
        st = {r.key: r.n for r in f.itertuples()}
        xs = sorted(((n, key) for key, n in st.items() if key.startswith("x_")), reverse=True)[:6]
        line.update(match="MATCH" if m else "side" if s else "", engine="; ".join(tr) or "no trade",
                    funnel="sweep/mss/fvg/order " + "/".join(str(st.get(k, 0)) for k in ("1_sweep", "2_mss", "3_fvg", "4_order")) + " | " + ", ".join(f"{key[2:]} {n}" for n, key in xs))
        rows.append(line)
    pd.DataFrame(rows).to_csv(f"{HERE}/compare_{v}.csv", index=False)
    print(f"{v}: {n_match} of {n_run} matched; same day and side {n_side}; opposite trade in his window {n_opp}")
    if "-v" in sys.argv or len(VARS) == 1:
        for r in rows:
            print(f"{r['id']} {r['date']} {r['sym']} ICT {r['ict']} [{r['match']}]\n    {r['engine']}\n    {r['funnel']}")
