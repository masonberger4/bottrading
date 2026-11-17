"""Features built from what ICT says he is looking at when he calls the morning's direction.

Each feature is signed (+1 up, -1 down, 0 no opinion) and uses only bars that closed before minute T of the day.
Prices: back-adjusted fixed-roll 1-minute bars (levels carry across rolls); the raw file gives the price for % stops.
"""
import numpy as np, pandas as pd

DATA = "/home/user/data"
COST = {"ES": 0.10, "NQ": 0.25}
FRAC = {"NQ": 0.0025, "ES": 0.0021}       # same stop distance as PR #97
TICK = 0.25


class Mkt:
    def __init__(self, sym):
        self.sym = sym
        d = pd.read_parquet(f"{DATA}/{sym}_1min_db.parquet")
        r = pd.read_parquet(f"{DATA}/{sym}_1min_dbraw.parquet")
        w = d.index.tz_localize(None)                       # New York wall clock
        self.t = w.values.astype("datetime64[m]").astype(np.int64)
        self.o, self.h, self.l, self.c = (d[x].to_numpy(float) for x in ("open", "high", "low", "close"))
        self.raw = r["close"].reindex(d.index).ffill().to_numpy(float)
        mod = self.t % 1440
        day = self.t // 1440
        i930 = np.flatnonzero(mod == 570)
        self.days = day[i930]                               # day number of every day with a 09:30 bar
        self.dates = pd.to_datetime(self.days * 1440, unit="m").date
        self.k = {d_: n for n, d_ in enumerate(self.dates)}
        # per day: RTH range, settlement (close of the 16:14 bar), 09:30 open, midnight open
        n = len(self.days)
        self.rth = np.full(n, np.nan); self.settle = np.full(n, np.nan); self.o930 = np.full(n, np.nan)
        for j, dd in enumerate(self.days):
            a, b = self.ix(dd, 570), self.ix(dd, 960)
            if b > a:
                self.rth[j] = self.h[a:b].max() - self.l[a:b].min()
            s = self.ix(dd, 975)
            self.settle[j] = self.c[s - 1] if s > a else np.nan
            self.o930[j] = self.o[a]
        self.adr = pd.Series(self.rth).shift(1).rolling(20, min_periods=10).mean().to_numpy()

    def ix(self, day, minute):
        """index of the first bar at or after `minute` of `day` (minute may be negative = previous evening)"""
        return int(np.searchsorted(self.t, day * 1440 + minute))

    # ---- helpers -------------------------------------------------------------------------------------------
    def pivots(self, a, b, k=3):
        """5-minute swing highs and lows in bars [a, b). Returns (hi_lvl, hi_conf_ix, lo_lvl, lo_conf_ix): the level
        and the 1m index from which the swing is known (k five-minute bars later)."""
        g = self.t[a:b] // 5
        u, st = np.unique(g, return_index=True)
        H = np.maximum.reduceat(self.h[a:b], st); L = np.minimum.reduceat(self.l[a:b], st)
        end = np.r_[st[1:], b - a] + a                       # 1m index one past each 5m bar
        n = len(H); hi = []; lo = []
        for i in range(k, n - k):
            if H[i] > H[i - k:i].max() and H[i] >= H[i + 1:i + k + 1].max():
                hi.append((H[i], end[i + k], end[i]))
            if L[i] < L[i - k:i].min() and L[i] <= L[i + 1:i + k + 1].min():
                lo.append((L[i], end[i + k], end[i]))
        return hi, lo

    def feats(self, date, T, look=3, tol=0.02):
        """dict of signed features for `date` at minute T (bars before T only). None if the day is unusable."""
        j = self.k.get(date)
        if j is None or j < 25 or not np.isfinite(self.adr[j]):
            return None
        dd = self.days[j]; adr = self.adr[j]
        e = self.ix(dd, T)                                   # first bar NOT known
        s0 = self.ix(dd, -360)                               # 18:00 the evening before
        if e - s0 < 60 or self.t[e - 1] < dd * 1440 + T - 30:
            return None
        p = self.c[e - 1]
        f = dict(date=date, T=T, p=p, adr=adr, raw=self.raw[e - 1])

        # --- 1. opening range gap: premium gap -> down to the half gap, discount gap -> up (he says by 10:00)
        gap = self.o930[j] - self.settle[j - 1]
        f["gap"] = gap / adr
        mid = self.settle[j - 1] + gap / 2
        f["gap_mid"] = mid
        if T >= 570:
            a = self.ix(dd, 570)
            done = e > a and ((self.l[a:e].min() <= mid) if gap > 0 else (self.h[a:e].max() >= mid))
            f["s_gap"] = 0 if (done or gap == 0) else -np.sign(gap)
        else:
            f["s_gap"] = 0
            f["gap"] = (p - self.settle[j - 1]) / adr         # the gap as it stands before the bell
            f["s_gapnow"] = -np.sign(f["gap"])

        # --- 2. relative equal highs / lows still untouched (last `look` sessions), the nearer one is the draw
        a0 = self.ix(self.days[j - look + 1], -360)
        hi, lo = self.pivots(a0, e)
        hi = [x for x in hi if x[1] <= e]; lo = [x for x in lo if x[1] <= e]
        tl = tol * adr
        reh = self._req(hi, e, tl, +1); rel = self._req(lo, e, tl, -1)
        du = reh - p if reh is not None else np.inf
        dn = p - rel if rel is not None else np.inf
        f["req_up"] = du / adr; f["req_dn"] = dn / adr
        f["s_req"] = 0 if min(du, dn) > adr else (1 if du < dn else -1)
        f["s_req1"] = f["s_req"] if (np.isinf(du) != np.isinf(dn)) else 0      # only one side has them

        # --- 3. the side whose stops were just run (swing taken in the last 60 minutes, price back inside)
        last = (-1, 0)
        w0 = self.ix(dd, T - 60)
        for lvl, conf, _ in hi:
            m = np.flatnonzero(self.h[conf:e] > lvl)
            if len(m) and conf + m[0] >= w0 and p < lvl and conf + m[0] > last[0]:
                last = (conf + m[0], -1)
        for lvl, conf, _ in lo:
            m = np.flatnonzero(self.l[conf:e] < lvl)
            if len(m) and conf + m[0] >= w0 and p > lvl and conf + m[0] > last[0]:
                last = (conf + m[0], +1)
        f["s_sweep"] = last[1]

        # --- 4. which side of the overnight range went first (session high vs low since 18:00; later one = taken last)
        ih = s0 + int(np.argmax(self.h[s0:e])); il = s0 + int(np.argmin(self.l[s0:e]))
        rng = self.h[ih] - self.l[il]
        pos = (p - self.l[il]) / rng if rng > 0 else 0.5
        f["on_pos"] = pos
        f["s_first"] = 0 if ih == il else (-1 if ih > il else 1)   # the high came last -> the lows are next
        f["s_onpos"] = 1 if pos < 0.5 else -1                       # in the lower half of the overnight range -> up

        # --- 5. old gap levels as the draw: new day opening gaps (last 5), new week opening gap (last 4),
        #        yesterday's settlement, midnight open. Nearest one not yet traded to since it formed.
        lv = []
        for q in range(0, 5):
            dq = self.days[j - q]; i18 = self.ix(dq, -360)
            if i18 > 0 and i18 < e:
                lv.append(((self.c[i18 - 1] + self.o[i18]) / 2, i18 + 1,
                           "nwog" if self.t[i18] - self.t[i18 - 1] > 1440 else "ndog"))
        lv.append((self.settle[j - 1], self.ix(dd, -360), "settle"))
        im = self.ix(dd, 0)
        if im < e:
            lv.append((self.o[im], im + 1, "mid"))
        best = (np.inf, 0); up = dn_ = 0
        for L, frm, kind in lv:
            if frm >= e or not np.isfinite(L):
                continue
            touched = self.l[frm:e].min() <= L <= self.h[frm:e].max()
            d = L - p
            if kind in ("ndog", "nwog") and abs(d) <= adr:
                up += d > 0; dn_ += d < 0
            if not touched and abs(d) < best[0] and abs(d) <= adr:
                best = (abs(d), np.sign(d))
            if kind == "mid":
                f["s_mid_rev"] = np.sign(d)                  # toward the midnight opening price
            if kind == "settle":
                f["s_settle"] = np.sign(d)
        f["s_oldgap"] = best[1]
        f["s_gapcl"] = np.sign(up - dn_)

        # --- 6. the opening move as a false move (after 09:30 only), and the 08:30 move faded
        if T > 570:
            mv = (p - self.o930[j]) / adr
            f["open_mv"] = mv
            f["s_judas"] = -np.sign(mv) if abs(mv) >= 0.10 else 0
        else:
            f["s_judas"] = 0
        if T >= 520:
            a8 = self.ix(dd, 510); b8 = self.ix(dd, 520)
            if b8 > a8:
                mv = (self.c[b8 - 1] - self.o[a8]) / adr
                f["s_830fade"] = -np.sign(mv) if abs(mv) >= 0.10 else 0
        f.setdefault("s_830fade", 0); f.setdefault("s_mid_rev", 0); f.setdefault("s_settle", 0)
        return f

    def _req(self, piv, e, tl, sgn):
        """nearest untouched pair of equal swing highs (sgn=+1) or lows (sgn=-1); level or None"""
        best = None
        x = self.h if sgn > 0 else self.l
        for a in range(len(piv)):
            for b in range(a + 1, len(piv)):
                la, ca, ea = piv[a]; lb, cb, eb = piv[b]
                if eb - ea < 30 or abs(la - lb) > tl:
                    continue
                lvl = max(la, lb) if sgn > 0 else min(la, lb)
                seg = x[ea:e]
                ext = seg.max() if sgn > 0 else seg.min()
                if (ext - lvl) * sgn > 0:                    # something traded beyond the pair: gone
                    continue
                if best is None or (lvl - best) * sgn < 0:
                    best = lvl
        return best

    # ---- outcome: the PR #97 plain entry -----------------------------------------------------------------
    def plain(self, date, T, sign, end=720, tgt_r=2.0):
        j = self.k[date]; dd = self.days[j]
        i0, i1 = self.ix(dd, T), self.ix(dd, end)
        if i0 >= i1 or sign == 0:
            return np.nan
        dist = FRAC[self.sym] * self.raw[i0]
        o, h, l = self.o[i0:i1 + 1] * sign, self.h[i0:i1 + 1] * sign, self.l[i0:i1 + 1] * sign
        if sign < 0:
            h, l = l, h
        e = o[0]; stop = e - dist; tgt = e + tgt_r * dist; pts = None
        for i in range(i1 - i0):
            if l[i] <= stop:
                pts = min(stop, o[i]) - e; break
            if h[i] >= tgt:
                pts = max(tgt, o[i]) - e; break
        if pts is None:
            pts = o[i1 - i0] - e if i1 - i0 < len(o) else self.c[i1 - 1] * sign - e
        return (pts - COST[self.sym]) / dist

    def move(self, date, T, end):
        j = self.k[date]; dd = self.days[j]
        i0, i1 = self.ix(dd, T), self.ix(dd, end)
        return (self.o[i1] - self.o[i0]) / self.adr[j] if i1 > i0 and i1 < len(self.o) else np.nan


def plain_px(m, date, T, sign, end, tgt_px=None, stop_frac=None, tgt_r=None):
    """Like Mkt.plain but the target can be a price (his stated level). Returns (R, exit reason)."""
    j = m.k[date]; dd = m.days[j]
    i0, i1 = m.ix(dd, T), m.ix(dd, end)
    if i0 >= i1 or sign == 0:
        return np.nan, ""
    dist = (stop_frac or FRAC[m.sym]) * m.raw[i0]
    e = m.o[i0]; stop = e - sign * dist
    tgt = tgt_px if tgt_px is not None else e + sign * tgt_r * dist
    if (tgt - e) * sign <= 0:
        return np.nan, "no room"
    for i in range(i0, i1):
        lo, hi = m.l[i], m.h[i]
        if (sign > 0 and lo <= stop) or (sign < 0 and hi >= stop):
            x = min(stop, m.o[i]) if sign > 0 else max(stop, m.o[i]); return ((x - e) * sign - COST[m.sym]) / dist, "stop"
        if (sign > 0 and hi >= tgt) or (sign < 0 and lo <= tgt):
            x = max(tgt, m.o[i]) if sign > 0 else min(tgt, m.o[i]); return ((x - e) * sign - COST[m.sym]) / dist, "target"
    x = m.o[i1] if i1 < len(m.o) else m.c[i1 - 1]
    return ((x - e) * sign - COST[m.sym]) / dist, "time"
