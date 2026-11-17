"""Option C groundwork (PR #82): one row per market per trading day, 2016-2026, with
  - the things ICT cites when he picks a side (signed columns s_*, + = bullish) and a day (unsigned columns c_*),
    all known at 09:30 New York (nothing after the 09:30 open is used),
  - what the market then did (o_* columns), for scoring.
Standalone: reads the fixed-roll 5-minute bars, no engine import, about a minute for ES + NQ + YM.

    python runs/learn_ict_2026-11-16/build_days.py [--data DIR] [--out runs/learn_ict_2026-11-16/out/days.csv]

Every column is listed with its ICT source in FEATURES.md. Columns are in ADR units (5-day average daily range of the
market) where they are distances, so ES, NQ and YM can be pooled."""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
PF = Path("/mnt/project-files/mentorship/data")
SYMS = ("ES", "NQ", "YM")
COT_CODE = {"ES": "13874A", "NQ": "209742", "YM": "124603"}
SEAS_B63 = {1: -1, 2: 1, 4: 1, 5: -1, 7: 1, 10: 1, 11: 1, 12: 1}        # bias digest B63, months with a stated lean
SEAS_AGREED = {2: 1, 4: 1, 11: 1, 12: 1}                                # digest C10 default: months all sources agree on


def _win(g, a, b):
    """high, low, first open, last close of bars with a <= minute-of-day < b (bars are labelled by their start)."""
    m = g[(g.mn >= a) & (g.mn < b)]
    if not len(m):
        return (np.nan,) * 4
    return m.high.max(), m.low.min(), m.open.iloc[0], m.close.iloc[-1]


def day_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per trading day (18:00 the evening before to 17:00): session pieces needed for the features and outcomes."""
    df = df.copy()
    ts = df.index
    df["mn"] = ts.hour * 60 + ts.minute
    df["tday"] = (ts + pd.Timedelta(hours=6)).normalize().tz_localize(None)       # 18:00 starts the next trading day
    rows = []
    for d, g in df.groupby("tday", sort=True):
        if d.weekday() > 4:
            continue
        eve = g[g.mn >= 1080]; day = g[g.mn < 1080]
        rth = day[(day.mn >= 570) & (day.mn < 960)]
        if len(rth) < 70:                                    # holiday or half day: 78 five-minute bars in a full session
            continue
        pre = pd.concat([eve, day[day.mn < 570]])           # everything before 09:30
        r = dict(day=d, d_open=g.open.iloc[0], d_high=g.high.max(), d_low=g.low.min(), d_close=day.close.iloc[-1],
                 sun_open=eve.open.iloc[0] if len(eve) else np.nan,
                 pre_high=pre.high.max() if len(pre) else np.nan, pre_low=pre.low.min() if len(pre) else np.nan,
                 rth_open=rth.open.iloc[0], rth_high=rth.high.max(), rth_low=rth.low.min(), rth_close=rth.close.iloc[-1])
        r["asia_high"], r["asia_low"] = (eve.high.max(), eve.low.min()) if len(eve) else (np.nan, np.nan)
        r["lon_high"], r["lon_low"], _, _ = _win(day, 120, 300)                   # London 02:00-05:00
        _, _, r["mid_open"], _ = _win(day, 0, 5)                                  # midnight open
        _, _, r["o830"], _ = _win(day, 510, 515)
        _, _, _, r["settle"] = _win(day, 960, 975)                                # 16:15 close (opening range gap anchor)
        am = rth[rth.mn < 690]                                                   # 09:30-11:30
        r["am_high"], r["am_low"], r["am_close"] = am.high.max(), am.low.min(), am.close.iloc[-1]
        r["am_hi_first"] = int(am.high.values.argmax() < am.low.values.argmin())
        rows.append(r)
    return pd.DataFrame(rows).set_index("day")


def _fvg_draw(h, l, c, k, look=60):
    """Nearest unfilled daily fair value gap above vs below yesterday's close, using days up to k-1.
    +1 = the nearer one is above (draw up), -1 = below, 0 = none. Sized by closeness (1 = at the gap)."""
    px = c[k - 1]; up = dn = np.inf
    for i in range(max(2, k - look), k):
        if l[i] > h[i - 2]:                                  # bullish gap (BISI) between h[i-2] and l[i]
            lo, hi = h[i - 2], l[i]
            lo2 = min(l[i + 1:k].min(), hi) if i + 1 < k else hi
            if lo2 > lo and px > lo:                         # part of it still open and below price
                dn = min(dn, max(px - lo2, 0.0))
        if h[i] < l[i - 2]:                                  # bearish gap (SIBI) between h[i] and l[i-2]
            lo, hi = h[i], l[i - 2]
            hi2 = max(h[i + 1:k].max(), lo) if i + 1 < k else lo
            if hi2 < hi and px < hi:
                up = min(up, max(hi2 - px, 0.0))
    if not np.isfinite(up) and not np.isfinite(dn):
        return 0.0
    if not np.isfinite(dn):
        return 1.0
    if not np.isfinite(up):
        return -1.0
    return float((dn - up) / (dn + up)) if dn + up > 0 else 0.0


def cot_table(sym: str) -> pd.Series:
    """Commercial net position against the midpoint of its own 52-week range (B60), +1 above (buying), -1 below.
    Indexed by the first day the report is public (the Monday after the Friday release)."""
    f = PF / "cot" / "legacy_es_nq_ym_raw.json"
    if not f.exists():
        return pd.Series(dtype=float)
    j = [r for r in json.load(open(f)) if r.get("cftc_contract_market_code") == COT_CODE[sym]]
    t = pd.DataFrame({"d": pd.to_datetime([r["report_date_as_yyyy_mm_dd"][:10] for r in j]),
                      "net": [float(r["comm_positions_long_all"]) - float(r["comm_positions_short_all"]) for r in j]})
    t = t.drop_duplicates("d").sort_values("d").set_index("d")
    mid = (t.net.rolling(52).max() + t.net.rolling(52).min()) / 2
    s = np.sign(t.net - mid)
    s.index = s.index + pd.Timedelta(days=6)                 # Tuesday as-of -> usable from the next Monday
    return s.dropna()


def dxy_bond() -> pd.DataFrame:
    """Daily 5-day change sign of the dollar (spot, 17:00 close) and of the 30-year bond future (front contract)."""
    out = pd.DataFrame()
    f = PF / "dxy" / "spot_dxy_1m_close_2019-2025_NYtime.csv.gz"
    if f.exists():
        x = pd.read_csv(f, parse_dates=["ts_ny"]).set_index("ts_ny").dxy_spot_close
        dc = x[x.index.hour < 17].groupby(lambda t: t.normalize()).last()
        out["dxy5"] = np.sign(dc.diff(5))
    try:
        import databento as db
        z = pd.concat([db.DBNStore.from_file(str(p)).to_df() for p in sorted((PF / "databento").glob("ZB_ohlcv1d*.dbn.zst"))])
        z = z[~z.symbol.str.contains("-")].copy()
        z["d"] = z.index.tz_localize(None).normalize()
        z = z.sort_values(["symbol", "d"]); z["chg"] = z.groupby("symbol").close.diff()
        front = z.sort_values("volume").groupby("d").tail(1).set_index("d").sort_index()
        out = out.join(np.sign(front.chg.rolling(5).sum()).rename("zb5"), how="outer")
    except Exception as e:                                   # databento not installed: bond column left empty
        print("bond column skipped:", e)
    return out


def news_table() -> pd.DataFrame:
    f = PF / "macro_risk_dates.csv"
    t = pd.read_csv(f, comment="#")
    t["date"] = pd.to_datetime(t.date)
    return t


def features(sym: str, D: pd.DataFrame, others: dict, news: pd.DataFrame, im: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c = (D[k].values for k in ("d_open", "d_high", "d_low", "d_close"))
    n = len(D); days = D.index
    rng = h - l
    adr = pd.Series(rng).rolling(5).mean().shift(1).values             # 5-day ADR from completed days
    adr60 = pd.Series(rng).rolling(60).mean().shift(1).values
    px = D.rth_open.values                                             # the price at 09:30
    F = pd.DataFrame(index=days)
    F["market"] = sym; F["adr5"] = adr
    hi20 = pd.Series(h).rolling(20).max().shift(1).values; lo20 = pd.Series(l).rolling(20).min().shift(1).values
    hi60 = pd.Series(h).rolling(60).max().shift(1).values; lo60 = pd.Series(l).rolling(60).min().shift(1).values
    ph, pl, pc = np.roll(h, 1), np.roll(l, 1), np.roll(c, 1)
    # ---- signed (direction) columns, + = bullish --------------------------------------------------------------
    F["s_pd20"] = 1 - 2 * (px - lo20) / (hi20 - lo20)                  # B31/B35: discount of the 20-day range = buy side
    F["s_pd60"] = 1 - 2 * (px - lo60) / (hi60 - lo60)                  # B33: 60-day range
    F["s_draw20"] = ((px - lo20) - (hi20 - px)) / adr                  # B1/B34: nearer 20-day pool is the draw (+ = high nearer)
    brk = (c > ph).astype(int) - (c < pl).astype(int); brk[0] = 0
    F["s_iof5"] = pd.Series(brk).rolling(5).sum().shift(1).values      # B13/B19: daily order flow, closes through prior highs minus lows
    F["s_pday"] = np.sign(pc - np.roll(o, 1))                          # prior day's candle
    up = (c > pc).astype(int); up[0] = 0; dn = (c < pc).astype(int); dn[0] = 0
    u3 = pd.Series(up).rolling(3).sum().shift(1).values == 3; d3 = pd.Series(dn).rolling(3).sum().shift(1).values == 3
    F["s_3close"] = d3.astype(int) - u3.astype(int)                    # B28: after 3 up closes no longs, mirror
    h2, l2, c2, o2 = np.roll(h, 2), np.roll(l, 2), np.roll(c, 2), np.roll(o, 2)
    outside = (ph > h2) & (pl < l2)
    F["s_outside"] = np.where(outside, np.sign(pc - np.roll(o, 1)), 0) # B28: down-close outside day -> lower
    F["s_fvg_d"] = [(_fvg_draw(h, l, c, k) if k >= 3 else 0.0) for k in range(n)]   # B1/B2/B30: nearest open daily gap is the draw
    wk = pd.Series(days.to_period("W-FRI"), index=days)
    W = D.groupby(wk.values).agg(w_open=("d_open", "first"), w_high=("d_high", "max"), w_low=("d_low", "min"), w_close=("d_close", "last"))
    Wp = W.shift(1)
    wbrk = ((W.w_close > Wp.w_high).astype(int) - (W.w_close < Wp.w_low).astype(int)).rolling(4).sum().shift(1)
    F["s_wk_iof"] = wbrk.reindex(wk.values).values                     # B3/B23: weekly direction, closes through prior week's high/low
    F["s_wk_last"] = np.sign(Wp.w_close - Wp.w_open).reindex(wk.values).values      # last week's candle
    wopen = W.w_open.reindex(wk.values).values
    F["s_wk_open"] = (px - wopen) / adr                                # B37: above / below the week's opening price
    pwh, pwl = Wp.w_high.reindex(wk.values).values, Wp.w_low.reindex(wk.values).values
    F["s_pw_draw"] = ((px - pwl) - (pwh - px)) / adr                   # previous week's high or low nearer
    F["s_mid"] = (px - D.mid_open.values) / adr                        # B36: above / below the midnight open
    F["s_830"] = (px - D.o830.values) / adr                            # B36: above / below the 08:30 open
    pset = np.roll(D.settle.values, 1)
    F["s_org"] = (px - pset) / adr                                     # B43: opening range gap (prior 16:15 close to 09:30)
    wk_first = wk.values != np.roll(wk.values, 1)
    fri_close = pd.Series(np.where(wk_first, pc, np.nan)).ffill().values
    sun_open = pd.Series(np.where(wk_first, D.sun_open.values, np.nan)).ffill().values
    F["s_nwog"] = (px - (fri_close + sun_open) / 2) / adr              # B41: above / below the new week opening gap
    took_h, took_l = D.pre_high.values > ph, D.pre_low.values < pl
    F["s_pre_raid"] = took_l.astype(int) - took_h.astype(int)          # B13/B20: overnight ran yesterday's low (bullish) / high (bearish)
    lh, ll, ah, al = D.lon_high.values, D.lon_low.values, D.asia_high.values, D.asia_low.values
    F["s_lon_pos"] = 1 - 2 * (px - np.fmin(ll, al)) / (np.fmax(lh, ah) - np.fmin(ll, al))   # where 09:30 sits in the Asia+London range
    F["s_lon_dir"] = np.sign(lh - ah).clip(0, 1) - np.sign(al - ll).clip(0, 1)      # London took the Asia high (+1) / low (-1): Judas side (B11)
    # SMT (B51): a market that refuses the overnight break of yesterday's low while a partner makes it = bullish
    tl = pd.DataFrame({s: (T.pre_low < T.d_low.shift(1)) for s, T in others.items()}).reindex(days)
    th = pd.DataFrame({s: (T.pre_high > T.d_high.shift(1)) for s, T in others.items()}).reindex(days)
    smt_b = tl.any(axis=1) & ~tl.all(axis=1); smt_s = th.any(axis=1) & ~th.all(axis=1)
    F["s_smt"] = smt_b.astype(int).values - smt_s.astype(int).values
    F["s_seas"] = [SEAS_B63.get(d.month, 0) for d in days]             # B63 monthly map
    F["s_seas_agreed"] = [SEAS_AGREED.get(d.month, 0) for d in days]
    cot = cot_table(sym)
    F["s_cot"] = cot.reindex(cot.index.union(days)).ffill().reindex(days).values if len(cot) else np.nan     # B60
    wr_hi, wr_lo = pd.Series(h).rolling(15).max().shift(1).values, pd.Series(l).rolling(15).min().shift(1).values
    F["s_wr15"] = 1 - 2 * (pc - wr_lo) / (wr_hi - wr_lo)               # B62: daily Williams %R, oversold = long
    imr = im.reindex(im.index.union(days)).ffill().shift(1).reindex(days) if len(im) else pd.DataFrame(index=days)
    F["s_dxy"] = -imr["dxy5"].values if "dxy5" in imr else np.nan      # B55: dollar down = risk on
    F["s_zb"] = imr["zb5"].values if "zb5" in imr else np.nan          # B57: bonds and stocks together
    c250 = pd.Series(c).shift(250).values
    F["s_trend250"] = np.sign(pc - c250)                               # B27: 9-18 month trend
    # ---- unsigned (day selection) columns ----------------------------------------------------------------------
    F["c_dow"] = [d.weekday() for d in days]                           # B8/B44: day of week
    tags = news.groupby("date").tag.apply(set)
    tg = [tags.get(d, set()) for d in days]
    for name, keys in dict(nfp=("nfp",), cpi=("cpi",), fomc=("fomc",), ppi=("ppi",), holiday_eve=("holiday_eve",),
                           roll_week=("roll_week",), mid_news=("pce", "gdp", "retail", "jolts")).items():
        F[f"c_{name}"] = [int(any(any(k in str(t).lower() for k in keys) for t in s)) for s in tg]
    F["c_news830"] = (F[["c_nfp", "c_cpi", "c_ppi"]].sum(axis=1) > 0).astype(int)
    wkn = F.groupby(wk.values)[["c_nfp", "c_fomc"]].transform("max")
    F["c_nfp_week"], F["c_fomc_week"] = wkn.c_nfp.values, wkn.c_fomc.values       # weeks he tells students to skip
    F["c_prev_rng"] = np.roll(rng, 1) / adr                            # B28: day after > 2x ADR = chop
    F["c_inside"] = ((ph < h2) & (pl > l2)).astype(int)                # B28: inside day -> expansion
    F["c_regime"] = adr / adr60                                        # B49: range regime (quiet vs wide)
    r5 = pd.Series(h).rolling(5).max().shift(1).values - pd.Series(l).rolling(5).min().shift(1).values
    F["c_consol5"] = r5 / (5 * adr)                                    # B49: 5-day box small against 5 daily ranges = sideways
    F["c_pre_rng"] = (D.pre_high.values - D.pre_low.values) / adr      # overnight range already used (ADR spent)
    F["c_gap_abs"] = np.abs(F.s_org)
    F["c_pool_dist"] = np.minimum(hi20 - px, px - lo20) / adr          # distance to the nearer 20-day pool
    F["c_pre_both"] = (took_h & took_l).astype(int)                    # overnight ran both sides of yesterday
    F["c_pre_none"] = (~took_h & ~took_l).astype(int)                  # 09:30 opens inside yesterday's range, nothing taken
    F["c_smt_both"] = (smt_b & smt_s).astype(int).values               # B52: SMT both ways = do not trade
    dow = F.c_dow.values
    wk_h = D.groupby(wk.values).d_high.cummax().shift(1).values; wk_l = D.groupby(wk.values).d_low.cummin().shift(1).values
    wk_h = np.where(wk_first, np.nan, wk_h); wk_l = np.where(wk_first, np.nan, wk_l)
    F["c_wk_obj"] = ((np.fmax(wk_h, D.pre_high.values) > pwh) | (np.fmin(wk_l, D.pre_low.values) < pwl)).astype(int)   # B48: last week's high or low already taken this week
    F["c_wk_used"] = np.where(wk_first, 0.0, (wk_h - wk_l)) / (5 * adr)    # share of a normal week's range already made
    sg = [k for k in F.columns if k.startswith("s_")]
    sgn = np.sign(F[sg].fillna(0).values)
    F["c_agree"] = np.abs(sgn.sum(axis=1)) / np.maximum((sgn != 0).sum(axis=1), 1)   # B47: how one-sided the picture is (0 = 50/50)
    core = np.sign(F[["s_iof5", "s_wk_iof", "s_fvg_d", "s_draw20"]].fillna(0).values)
    F["c_htf_agree"] = np.abs(core.sum(axis=1)) / 4                    # B25: weekly and daily pointing the same way
    # ---- outcomes (after 09:30; never used as inputs) ----------------------------------------------------------
    F["o_am"] = (D.am_close.values - px) / adr                         # 09:30 -> 11:30, in ADR
    F["o_day"] = (D.rth_close.values - px) / adr                       # 09:30 -> 16:00
    upx, dnx = (D.rth_high.values - px) / adr, (px - D.rth_low.values) / adr
    F["o_big"] = upx - dnx                                             # B11: side of the day's largest move from the open
    F["o_am_rng"] = (D.am_high.values - D.am_low.values) / adr
    F["o_am_eff"] = np.abs(F.o_am) / F.o_am_rng.replace(0, np.nan)     # how one-way the morning was (1 = straight line)
    F = F.iloc[260:]                                                   # warm-up for the 250-day column
    return F.replace([np.inf, -np.inf], np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(PF / "fixed_roll_2026-11-10"))
    ap.add_argument("--out", default=str(HERE / "out" / "days.csv"))
    a = ap.parse_args()
    T = {}
    for s in SYMS:
        p = Path(a.data) / f"{s}_5min_db.parquet"
        df = pd.read_parquet(p) if p.exists() else pd.read_csv(Path(a.data) / f"{s}_5min_db.csv", index_col=0, parse_dates=True)
        T[s] = day_table(df); print(s, len(T[s]), "days", T[s].index[0].date(), T[s].index[-1].date())
    news, im = news_table(), dxy_bond()
    F = pd.concat([features(s, T[s], T, news, im) for s in SYMS])
    F.index.name = "day"
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    F.round(4).to_csv(out)
    print("wrote", out, F.shape, "| empty share by column (top):")
    print(F.isna().mean().sort_values(ascending=False).head(8).round(3).to_string())


if __name__ == "__main__":
    main()
