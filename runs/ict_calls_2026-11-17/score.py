"""Score ICT's before-the-fact calls against 1-minute futures data.
usage: python score.py calls_2024.csv [more.csv ...]   (env ICT_PX = folder with <SYM>_1min_dbraw.parquet)
Measures per call (dir = +1 up, -1 down; ref = time the call was in force, ET):
  win_end  : price at the horizon end is beyond the price at ref, in the called direction
  ft       : first touch of +0.25% (in the called direction) or -0.25% after ref and before the horizon end
  tgt_hit  : the stated price target traded between ref and its deadline (only when a price is given or computable)
  chance   : share of all other sessions in the same calendar window where the same direction, ref and end would have won
"""
import os, sys, pandas as pd, numpy as np
PX = os.environ.get('ICT_PX', '/mnt/project-files/mentorship/data/fixed_roll_2026-11-10/')
TZ = 'America/New_York'
_c = {}
def px(sym):
    if sym not in _c:
        _c[sym] = pd.read_parquet(os.path.join(PX, sym + '_1min_dbraw.parquet'))
    return _c[sym]
def ts(d, t): return pd.Timestamp(str(d)[:10] + ' ' + t, tz=TZ)
_d = {}
def days(sym):
    if sym not in _d:
        d = px(sym); r = d.between_time('09:30', '15:59')
        _d[sym] = sorted(set(r.index.normalize()))
    return _d[sym]
def add_days(sym, date, n):
    ds = days(sym); d0 = pd.Timestamp(date, tz=TZ)
    later = [d for d in ds if d >= d0]
    if n == 0: return d0
    i = min(n - 1 if d0 not in ds else n, len(later) - 1)   # n trading days later
    return later[i]
def target_px(sym, date, key):
    d = px(sym)
    if key == 'open930':
        return float(d.loc[ts(date, '09:30')].open)
    if key == 'org_mid':
        prev = d.loc[:ts(date, '00:00')].between_time('16:14', '16:14')
        return (float(prev.close.iloc[-1]) + float(d.loc[ts(date, '09:30')].open)) / 2
    if key == 'london_low':
        return float(d.loc[ts(date, '02:00'):ts(date, '04:59')].low.min())
    return float(key)
def one(sym, date, ref, dirn, end_day, end, tgt='', tgt_by=''):
    d = px(sym); t0 = ts(date, ref)
    if ref >= '18:00': t0 = ts(date, ref)
    de = add_days(sym, date, int(end_day)) if int(end_day) else pd.Timestamp(date, tz=TZ)
    t1 = ts(de, end)
    w = d.loc[t0:t1 - pd.Timedelta(minutes=1)]
    if len(w) < 2: return None
    p0 = float(w.open.iloc[0]); p1 = float(w.close.iloc[-1]); s = 1 if dirn == 'up' else -1
    k = 0.0025 * p0
    up = w.index[(w.high >= p0 + k)]; dn = w.index[(w.low <= p0 - k)]
    fu = up[0] if len(up) else None; fd = dn[0] if len(dn) else None
    if fu is None and fd is None: ft = 0
    elif fd is None or (fu is not None and fu < fd): ft = s
    elif fu is None or fd < fu: ft = -s
    else: ft = 0
    out = dict(p_ref=p0, p_end=p1, move_pts=round(s * (p1 - p0), 2), move_pct=round(100 * s * (p1 - p0) / p0, 2),
               win_end=int(s * (p1 - p0) > 0), ft=ft,
               mfe_pct=round(100 * (w.high.max() - p0 if s > 0 else p0 - w.low.min()) / p0, 2),
               mae_pct=round(100 * (p0 - w.low.min() if s > 0 else w.high.max() - p0) / p0, 2))
    if tgt not in ('', None) and str(tgt) != 'nan':
        tp = target_px(sym, date, str(tgt))
        tb = ts(de if not tgt_by or int(end_day) else date, tgt_by or end)
        w2 = d.loc[t0:tb - pd.Timedelta(minutes=1)]
        already = (p0 >= tp) if s > 0 else (p0 <= tp)
        hit = (w2.high.max() >= tp) if s > 0 else (w2.low.min() <= tp)
        out.update(tgt=round(tp, 2), tgt_dist_pct=round(100 * s * (tp - p0) / p0, 2), tgt_hit=int(hit), tgt_already=int(already))
        if not hit:
            out['tgt_miss_pts'] = round((tp - w2.high.max()) if s > 0 else (w2.low.min() - tp), 2)
    return out
def chance(sym, date, ref, dirn, end_day, end, span=60):
    """same call applied to every other session within +-span calendar days"""
    ds = [x for x in days(sym) if abs((x - pd.Timestamp(date, tz=TZ)).days) <= span and str(x)[:10] != str(date)[:10]]
    if ref >= '18:00': return np.nan, np.nan
    wins = []; fts = []
    for x in ds:
        r = one(sym, str(x)[:10], ref, dirn, end_day, end)
        if r: wins.append(r['win_end']); fts.append(r['ft'])
    f = [v for v in fts if v != 0]
    return round(float(np.mean(wins)), 3), (round(float(np.mean([v > 0 for v in f])), 3) if f else np.nan)
def run(path):
    c = pd.read_csv(path, sep='|', dtype=str).fillna('')
    rows = []
    for _, r in c.iterrows():
        sym = r.get('sym', '') or 'NQ'
        o = one(sym, r.date, r.ref, r.dir, r.end_day, r.end, r.tgt_px, r.tgt_by) or {}
        ch = chance(sym, r.date, r.ref, r.dir, r.end_day, r.end)
        rows.append({**r.to_dict(), 'sym': sym, **o, 'chance_end': ch[0], 'chance_ft': ch[1]})
    return pd.DataFrame(rows)
def summary(df, label):
    L = ['## ' + label, '']
    def line(name, d):
        n = len(d)
        if not n: return
        w = int(d.win_end.sum()); f = d[d.ft != 0]; fw = int((f.ft > 0).sum())
        se = (0.25 / n) ** 0.5
        L.append('| %s | %d | %d (%.0f%%) | %.0f%% | %d of %d (%.0f%%) | %+.2f%% | %+.2f%% |' % (
            name, n, w, 100 * w / n, 100 * d.chance_end.astype(float).mean(), fw, len(f), 100 * fw / max(len(f), 1),
            d.move_pct.mean(), d.move_pct.median()))
    L += ['| group | calls | right at the horizon end | same call on other days | first to +0.25% vs -0.25% | mean move | median move |',
          '|---|---|---|---|---|---|---|']
    line('all calls', df); line('clearly before the move', df[df.before == 'yes'])
    line('up calls', df[df.dir == 'up']); line('down calls', df[df.dir == 'down'])
    line('with a live trade', df[df.trade.str.contains('live')]); line('no trade taken', df[~df.trade.str.contains('live')])
    line('same-day horizon', df[df.end_day == '0']); line('morning window only (end by 12:00)', df[(df.end_day == '0') & (df.end <= '12:00')])
    t = df[df.get('tgt_hit').notna()] if 'tgt_hit' in df else df.iloc[0:0]
    if len(t):
        t2 = t[t.tgt_already == 0]
        L += ['', 'Price targets: %d given, %d not yet reached at the call; of those %d hit by the deadline (%.0f%%). Median distance %.2f%%.' % (
            len(t), len(t2), int(t2.tgt_hit.sum()), 100 * t2.tgt_hit.mean() if len(t2) else 0, t2.tgt_dist_pct.median() if len(t2) else 0)]
    return '\n'.join(L)
if __name__ == '__main__':
    allr = []
    for p in sys.argv[1:]:
        df = run(p); df.to_csv(p.replace('.csv', '_scored.csv'), sep='|', index=False); allr.append(df)
        print(summary(df, os.path.basename(p))); print()
    if len(allr) > 1: print(summary(pd.concat(allr), 'all sets'))
