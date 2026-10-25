"""PD-array detectors from the ICT Mentorship rules (mentorship_rules.md).

Every detector reports the bar index at which its object became *known* (`Zone.i`,
`Pivot.known`), so a bar-by-bar caller can use an object at bar i only when its known
index is <= i. Nothing here reads a bar after the one it reports as known.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _same(a, b) -> bool:
    """Field equality where NaN equals NaN (an unset mean threshold)."""
    return a == b or (a != a and b != b)


@dataclass(frozen=True, eq=False)
class Zone:
    kind: str       # "bull" or "bear"
    top: float
    bottom: float
    i: int          # bar index at which the zone is known (the bar that completes it)
    src: int = -1   # index of the candle the zone is built from (blocks), or the gap's middle candle
    mt: float = float("nan")   # blocks: body mean threshold (see order_block_blend)
    # caption-gap pass (levels_detectors#1/3): optional extras, all defaulted. Equality and hashing ignore them (a rejection block with
    # its `levels`, a BPR with its `bi` is the same zone as before), so older code and tests are unchanged
    bi: int = -1               # bpr2: the bar at which the band is balanced (a later bar fully beyond it); -1 = not (yet)
    levels: tuple = ()         # named exact prices (inversions: (lo, mt, hi); rejection blocks: (level1, level2, W))
    tag: str = ""              # free tag ("single_bar", "void", "reclaimed", "bull"/"bear" role of a bpr2 / inversion)
    n: int = 0                 # a count (converged arrays)

    # Equality and hashing treat a NaN mean threshold as equal to NaN. Python 3.13's dataclass
    # __eq__ compares fields with == (NaN != NaN), while 3.11/3.12 compared tuples, whose
    # identity shortcut made the shared NaN default compare equal; this keeps both the same.
    def _key(self):
        return (self.kind, self.top, self.bottom, self.i, self.src, None if self.mt != self.mt else self.mt)

    def __eq__(self, other):
        if not isinstance(other, Zone):
            return NotImplemented
        return all(_same(x, y) for x, y in zip(
            (self.kind, self.top, self.bottom, self.i, self.src, self.mt),
            (other.kind, other.top, other.bottom, other.i, other.src, other.mt)))

    def __hash__(self):
        return hash(self._key())

    @property
    def mid(self) -> float:
        """Consequent encroachment (gaps) or mean threshold (blocks): 50% of the zone."""
        return (self.top + self.bottom) / 2

    def overlaps(self, other: "Zone") -> bool:
        return self.bottom < other.top and self.top > other.bottom

    def q(self, frac: float) -> float:
        """A5 quadrant level (020 ~8:21; 029 ~30:44): `frac` of the way from the bottom to the
        top (0.25 / 0.5 = CE / 0.75)."""
        return self.bottom + frac * (self.top - self.bottom)


@dataclass(frozen=True)
class Pivot:
    i: int          # bar of the swing high/low
    price: float
    known: int      # first bar at which it is confirmed (i + n)


def fvgs(h, l, o=None, c=None, c2_dir: bool = False, single_bar: float = 0.0, single_bar_n: int = 20) -> list[Zone]:
    """Fair value gaps (3-candle). BISI: low[i] > high[i-2]; SIBI: high[i] < low[i-2].
    Known at the third candle i. A5 `c2_dir` (Params.fvg_c2_dir; 001 ~13:02, 024 ~23:22: "c2 is
    the displacement candle"): the middle candle must close in the gap's direction (up-close for
    a BISI, down-close for a SIBI); needs o and c.
    Caption-gap A5 caffeine bar (006 ~12:34): `single_bar` > 0 tags (Zone.tag = "single_bar") a gap whose
    middle candle is ONE large displacement candle [our interpretation]: its range >= `single_bar` x the
    mean range of the `single_bar_n` bars before it (at least 5 bars are needed)."""
    out = []
    chk = c2_dir and o is not None and c is not None
    for i in range(2, len(h)):
        if l[i] > h[i - 2]:
            if chk and not c[i - 1] > o[i - 1]:
                continue
            out.append(Zone("bull", l[i], h[i - 2], i, i - 1, tag=_sb_tag(h, l, i, single_bar, single_bar_n)))
        elif h[i] < l[i - 2]:
            if chk and not c[i - 1] < o[i - 1]:
                continue
            out.append(Zone("bear", l[i - 2], h[i], i, i - 1, tag=_sb_tag(h, l, i, single_bar, single_bar_n)))
    return out


def _sb_tag(h, l, i: int, mult: float, n: int) -> str:
    """"single_bar" when the FVG's middle candle (i-1) is >= `mult` x the mean range of the `n` bars before it."""
    if mult <= 0 or i - 1 < 5:
        return ""
    a = max(0, i - 1 - n)
    prior = np.asarray(h[a:i - 1], float) - np.asarray(l[a:i - 1], float)
    if len(prior) < 5 or not prior.mean() > 0:
        return ""
    return "single_bar" if float(h[i - 1] - l[i - 1]) >= mult * float(prior.mean()) else ""


def volume_imbalances(o, h, l, c, min_gap: float = 0.0, wick_overlap: bool = True, multi: bool = False,
                      multi_k: int = 3) -> list[Zone]:
    """Gap between two consecutive candle bodies. Default (A9 as first built): only the wicks overlap.
    min_gap (Params.vi_min_gap_pts, price units): body gaps narrower than this are ignored.
    Caption-gap A9 definition (009 ~7:18; 036 ~22:55; 027 ~22:24: "there may or may not be an overlap between
    two candles with their wicks"):
      wick_overlap=False  the wick-overlap test is dropped (ICT: bodies only). When the wicks do not overlap
                          either the zone is ALSO a liquidity void: Zone.tag = "void".
      multi=True          a VI may span a run of up to `multi_k` candles [our interpretation of "between candle
                          i-k and i"]: the zone's near edge is the highest body top (lowest body bottom for a
                          bearish VI) over the candles i-k..i-1, so a band that an earlier body in the run
                          occupies is not part of the imbalance. Needs the adjacent two-candle gap to exist.
    Zone = [far body edge of the run, near body edge of candle i]; known at candle i."""
    out = []
    for i in range(1, len(o)):
        pb_hi, pb_lo = max(o[i - 1], c[i - 1]), min(o[i - 1], c[i - 1])
        cb_hi, cb_lo = max(o[i], c[i]), min(o[i], c[i])
        if cb_lo > pb_hi and (not wick_overlap or l[i] <= h[i - 1]):
            bot = pb_hi
            if multi and i >= 2:
                a = max(0, i - multi_k)
                bot = max(max(o[j], c[j]) for j in range(a, i))
            if cb_lo > bot and cb_lo - bot >= min_gap:
                out.append(Zone("bull", cb_lo, bot, i, i, tag="void" if l[i] > h[i - 1] else ""))
        elif cb_hi < pb_lo and (not wick_overlap or h[i] >= l[i - 1]):
            top = pb_lo
            if multi and i >= 2:
                a = max(0, i - multi_k)
                top = min(min(o[j], c[j]) for j in range(a, i))
            if top > cb_hi and top - cb_hi >= min_gap:
                out.append(Zone("bear", top, cb_hi, i, i, tag="void" if h[i] < l[i - 1] else ""))
    return out


def vi_body_dead(o, c, z: Zone, start: int | None = None, end: int | None = None,
                 rule: str = "full_span") -> int | None:
    """A9 / Ep03.3 VI death rule (035 ~5:50; 090 ~13:01): a VI is dead once a LATER candle body on
    its own timeframe closes fully across it - the body spans the whole VI, bottom to top. Returns
    the first such candle index in [start (default z.i + 1), end] (known at its close) or None.
    Wicks never kill it. Caption-gap A9 `rule` (Params.vi_dead_rule): "full_span" (the default, 046 / 090) or
    "overlap" (035: any later body that overlaps the zone kills it)."""
    a = z.i + 1 if start is None else start
    b = len(c) - 1 if end is None else min(end, len(c) - 1)
    for k in range(a, b + 1):
        lo_, hi_ = min(o[k], c[k]), max(o[k], c[k])
        if rule == "overlap":
            if lo_ < z.top and hi_ > z.bottom:
                return k
        elif lo_ <= z.bottom and hi_ >= z.top:
            return k
    return None


def vi_state(o, h, l, c, z: Zone, tick: float = 0.0, end: int | None = None, rule: str = "full_span") -> str:
    """Caption-gap A9 delivery state of a volume imbalance on its PARENT timeframe (035 ~21:01; 046 ~28:33;
    050 ~33:20; 077 ~3:23; 090 ~14:07) as of bar `end` (default: all bars), counting bars after z.i only:
      "dead"        a later body lays over the whole zone (rule "full_span", 046 / 090), or any body overlapping
                    it (rule "overlap", 035)
      "target_hit"  a later body overlaps the zone (wicks do not count)
      "reached"     a later WICK went through the zone to the far edge by one tick: bullish VI (price above it):
                    low <= bottom - tick; bearish: high >= top + tick [our interpretation of 050: "a later high >=
                    the earlier candle's close + 1 tick"]
      "open"        none of these
    Until "dead" a daily / weekly VI is a two-sided draw that may be revisited many times."""
    b = len(c) - 1 if end is None else min(end, len(c) - 1)
    if vi_body_dead(o, c, z, None, b, rule) is not None:
        return "dead"
    for k in range(z.i + 1, b + 1):
        if min(o[k], c[k]) < z.top and max(o[k], c[k]) > z.bottom:
            return "target_hit"
    seg_l, seg_h = l[z.i + 1:b + 1], h[z.i + 1:b + 1]
    if len(seg_l) and ((z.kind == "bull" and seg_l.min() <= z.bottom - tick) or
                       (z.kind == "bear" and seg_h.max() >= z.top + tick)):
        return "reached"
    return "open"


def pivots(h, l, n: int = 2) -> tuple[list[Pivot], list[Pivot]]:
    """Swing highs/lows: the bar's high (low) is strictly above (below) the n bars on each
    side. Confirmed n bars later."""
    highs, lows = [], []
    for k in range(n, len(h) - n):
        if h[k] > max(h[k - n:k]) and h[k] > max(h[k + 1:k + n + 1]):
            highs.append(Pivot(k, float(h[k]), k + n))
        if l[k] < min(l[k - n:k]) and l[k] < min(l[k + 1:k + n + 1]):
            lows.append(Pivot(k, float(l[k]), k + n))
    return highs, lows


def swing_tiers(h, l, n: int = 1) -> dict:
    """A1 swing hierarchy (014 ~0:12; cc05_002 ~20:14). STL = plain swing (pivots(n)); ITL low =
    an STL low with a HIGHER STL low on each side (its neighbours in the STL-low sequence); LTL low
    = an ITL low with higher ITL lows on each side; highs mirror it. A tier is known only once its
    right neighbour is known: Pivot.known = max(own known, right neighbour's known).
    Returns {"stl": (highs, lows), "itl": (highs, lows), "ltl": (highs, lows)}, sorted by bar."""
    ph, pl = pivots(h, l, n)

    def up(seq, lows: bool):
        out = []
        for k in range(1, len(seq) - 1):
            a, b, r = seq[k - 1], seq[k], seq[k + 1]
            ok = (b.price < a.price and b.price < r.price) if lows else (b.price > a.price and b.price > r.price)
            if ok:
                out.append(Pivot(b.i, b.price, max(b.known, r.known)))
        return out

    ih, il = up(ph, False), up(pl, True)
    return {"stl": (ph, pl), "itl": (ih, il), "ltl": (up(ih, False), up(il, True))}


IR_DEFS = ("a7", "open_space", "zero_width")


def immediate_rebalances_ex(o, h, l, c, tick: float, mode: str = "a7", overshoot_ticks: float = 2.0, body_mult: float = 1.5,
                            avg_n: int = 20, max_back: int = 60) -> list[tuple]:
    """A7 immediate rebalance (048 ~39:02; 060 ~7:20; 092 ~1:41:14) [our interpretation of the bar
    test, the same as sb_model.immediate_rebalance]: an up-close displacement candle k-1 whose NEXT
    candle k trades straight back to the high of the candle before it, h[k-2], within one tick and
    leaves no gap (an FVG is the deferred rebalance) -> (k, "bull"); bearish mirror (down-close
    k-1, h[k] back up to l[k-2]) -> (k, "bear"). Known at candle k's close. `immediate_rebalances_ex` returns (k, kind, bound, d): the level that was rebalanced to (the bounding candle's high / low) and the
    displacement candle d (review fix #85: the entry's level and EQ come from them, not from the a7 geometry); `immediate_rebalances` keeps (k, kind).
    Caption-gap A7-immediate-rebalance-definition (`mode` = Params.ir_def; 059 ~4:16, 060 ~7:29, 061 ~1:23:38, 078 ~1:15:05,
    100 ~44:46, 099 ~1:04:01):
      "a7"          as above (yesterday's high, the next candle, within a tick)
      "open_space"  059 / 060: "it doesn't mean it's the previous day immediately to the left". The displacement candle d is
                    up-close; its open space below is bounded by the high of the most recent earlier candle j < d whose high lies
                    below every low from j+1 through d (nothing traded in between) [our interpretation of "the candle that bounds
                    the open space - yesterday's, otherwise the older one"]. Candle d+1 (or d+2, when d+1 stayed above) opens above
                    that high B and trades down to it - within one tick above up to `overshoot_ticks` ticks beyond - with no body
                    close through it (the close stays above B); stopping short is a breakaway gap (060), not this. Known at the
                    retrace candle. Bearish mirrors it.
      "zero_width"  100 ~44:46: in a displacement leg take c1, c2, c3 with c2 a large bias-direction candle (body >= `body_mult` x
                    the mean body of the `avg_n` bars before it); it counts when low[c3] == high[c1] to the tick (bullish) or
                    high[c3] == low[c1] (bearish) - the legs do not leave a single price of room [our reading of "to the tick":
                    within half a tick]."""
    if mode not in IR_DEFS:
        raise ValueError(f"ir mode {mode!r}: expected one of {IR_DEFS}")
    out = []
    n = len(c)
    if mode == "a7":
        for k in range(2, n):
            if c[k - 1] > o[k - 1] and abs(l[k] - h[k - 2]) <= tick and l[k] <= h[k - 2] + 1e-12:
                out.append((k, "bull", float(h[k - 2]), k - 1))
            elif c[k - 1] < o[k - 1] and abs(h[k] - l[k - 2]) <= tick and h[k] >= l[k - 2] - 1e-12:
                out.append((k, "bear", float(l[k - 2]), k - 1))
        return out
    if mode == "zero_width":
        half = 0.5 * tick + 1e-12
        for k in range(2, n):
            a = max(0, k - 1 - avg_n)
            prior = np.abs(np.asarray(c[a:k - 1], float) - np.asarray(o[a:k - 1], float))
            if len(prior) < 3 or not prior.mean() > 0:
                continue
            big = abs(c[k - 1] - o[k - 1]) >= body_mult * prior.mean()
            if big and c[k - 1] > o[k - 1] and abs(l[k] - h[k - 2]) <= half:
                out.append((k, "bull", float(h[k - 2]), k - 1))
            elif big and c[k - 1] < o[k - 1] and abs(h[k] - l[k - 2]) <= half:
                out.append((k, "bear", float(l[k - 2]), k - 1))
        return out
    os_ = overshoot_ticks * tick
    for d in range(1, n - 1):
        up = c[d] > o[d]
        dn = c[d] < o[d]
        if not (up or dn):
            continue
        # the bounding candle of the open space below (above for a down displacement)
        bound = None
        for j in range(d - 1, max(-1, d - 1 - max_back), -1):
            if up and h[j] < min(l[j + 1:d + 1]) - 1e-12:
                bound = h[j]
                break
            if dn and l[j] > max(h[j + 1:d + 1]) + 1e-12:
                bound = l[j]
                break
        if bound is None:
            continue
        for k in (d + 1, d + 2):
            if k >= n:
                break
            if k == d + 2 and not ((l[d + 1] > bound + tick) if up else (h[d + 1] < bound - tick)):
                break                                    # candle d+1 already reached it (or crossed): d+2 is not the first retrace
            if up and o[k] > bound + tick and bound - os_ <= l[k] <= bound + tick and c[k] > bound:
                out.append((k, "bull", float(bound), d))
                break
            if dn and o[k] < bound - tick and bound - tick <= h[k] <= bound + os_ and c[k] < bound:
                out.append((k, "bear", float(bound), d))
                break
    best = {}
    for k, kd, b_, d_ in out:                   # one answer per (k, kind): the NEAREST displacement candle (largest d) [our interpretation]
        if (k, kd) not in best or d_ > best[(k, kd)][3]:
            best[(k, kd)] = (k, kd, b_, d_)
    return sorted(best.values())


def immediate_rebalances(o, h, l, c, tick: float, mode: str = "a7", overshoot_ticks: float = 2.0, body_mult: float = 1.5,
                         avg_n: int = 20, max_back: int = 60) -> list[tuple[int, str]]:
    """(k, kind) of immediate_rebalances_ex - see there for the three definitions."""
    return [(k, kd) for k, kd, *_ in immediate_rebalances_ex(o, h, l, c, tick, mode, overshoot_ticks, body_mult, avg_n, max_back)]


def vacuum_block(o, c, k: int, min_gap: float = 0.0) -> Zone | None:
    """L8 vacuum block (cc04_009 ~3:58-10:05): the gap between the last close before an event
    (bar k-1) and the first open after it (bar k), treated as a candle with high / low / MT.
    "bull" when the open is above the prior close (the gap lies below price). Known at bar k (the
    caller uses it from bar k's close). None when the gap is not wider than `min_gap`."""
    if k < 1 or k >= len(o):
        return None
    a, b = float(c[k - 1]), float(o[k])
    if abs(b - a) <= max(min_gap, 0.0) or a == b:
        return None
    return Zone("bull" if b > a else "bear", max(a, b), min(a, b), k, k)


def session_block(minute: int) -> int:
    """A13.5 time blocks [our interpretation of "the wrong time of day" (070 ~6:24)]: 0 Asia
    (18:00-02:00), 1 London (02:00-07:00), 2 NY AM (07:00-12:00), 3 lunch (12:00-13:30), 4 NY PM
    (13:30-18:00). A breaker's H, L2 and break must sit in one block."""
    m = int(minute) % 1440
    if m >= 1080 or m < 120:
        return 0
    if m < 420:
        return 1
    if m < 720:
        return 2
    if m < 810:
        return 3
    return 4


def order_block(o, h, l, c, start: int, end: int, kind: str) -> Zone | None:
    """Bullish OB: the last down-close candle in [start, end]; bearish: last up-close.
    Its mean threshold is `Zone.mid`."""
    for k in range(min(end, len(o) - 1), max(start, 0) - 1, -1):
        if (kind == "bull" and c[k] < o[k]) or (kind == "bear" and c[k] > o[k]):
            return Zone(kind, float(h[k]), float(l[k]), end, k)
    return None


OB_PICKS = ("blend", "original", "largest_body", "blend_in_htf")


def order_block_blend(o, h, l, c, start: int, end: int, kind: str, pick: str = "blend", s: float | None = None,
                      skip_encap: bool = False, htf_zone: tuple | None = None, outside: tuple | None = None) -> Zone | None:
    """ICT order block: the last down-close candle in [start, end] (bullish; up-close for
    bearish) together with the consecutive same-colour candles right before it, blended into
    one block (002 ~4:14; 029 ~29:28; 032 ~23:06). Zone = the series' full range; `mt` = the
    body mean threshold, midway between the series' highest body and lowest body
    (bullish: (max open + min close) / 2). `src` = the first (anchor) candle.
    Caption-gap A12 (`pick` = Params.ob_pick; bullish terms, bearish mirrors):
      "blend"         as above (A12, 032; the default)
      "original"      the first / highest candle of the run only (012 ~14:06: "go back to that original High
                      candle"); mt = its body midpoint; later candles of the run never replace it
      "largest_body"  the lowest down candle of the run at or through the HTF support `s` (cc03_004 / cc04_003),
                      tie-break on the largest |open - close|; [our interpretation] "at or through" = `s` inside
                      the candle's range or within one body height of it; no `s` (or none qualifies) = all candles
      "blend_in_htf"  065 ~1:21:02: blend only when the whole run lies inside the pre-called HTF array
                      `htf_zone` ((lo, hi), or a list of them); level = the open of the first candle (Zone.levels[0]), mt = (low of the
                      first + high of the last) / 2; otherwise the last candle alone (mt = its body midpoint)
    skip_encap (Params.ob_skip_encapsulated, cc06_005 ~19:10, all modes): a last candle whose body lies fully
    inside the previous same-colour candle's body and is clearly smaller [our interpretation: at most half of
    it] is skipped - the previous candle is the last candle of the block.
    Caption-gap A12-entry-ob-outside-fvg (levels_detectors #3/3; 065 ~4:04:05: "we have to use the out outside of the range"; `outside` =
    (bottom, top) of the FVG / shaded zone, bullish terms): candles whose whole range lies inside the zone are IGNORED - the block is the
    last down-close candle OUTSIDE the zone (and the run before it); the blend still stops at an opposite-close candle. `outside=None`
    is the old behaviour exactly."""
    if pick not in OB_PICKS:
        raise ValueError(f"ob pick {pick!r}: expected one of {OB_PICKS}")
    down = (lambda k: c[k] < o[k]) if kind == "bull" else (lambda k: c[k] > o[k])
    body = lambda k: (min(o[k], c[k]), max(o[k], c[k]))
    start = max(start, 0)
    inside = (lambda k: False) if outside is None else (lambda k: l[k] >= outside[0] - 1e-9 and h[k] <= outside[1] + 1e-9)
    for k in range(min(end, len(o) - 1), start - 1, -1):
        if down(k) and not inside(k):
            while skip_encap and k - 1 >= start and down(k - 1):
                (bl, bh), (pl_, ph_) = body(k), body(k - 1)
                if bl >= pl_ and bh <= ph_ and (bh - bl) <= 0.5 * (ph_ - pl_):
                    k -= 1
                else:
                    break
            j = k
            if outside is None:
                while j - 1 >= start and down(j - 1):
                    j -= 1
            else:                                     # the zone's candles are skipped, an opposite-close candle ends the run
                q = k - 1
                while q >= start:
                    if inside(q):
                        q -= 1
                    elif down(q):
                        j, q = q, q - 1
                    else:
                        break
            mem = [q for q in range(j, k + 1) if not inside(q)]      # (outside=None: the whole run)
            if pick == "blend":
                hi, lo = float(max(h[q] for q in mem)), float(min(l[q] for q in mem))
                if kind == "bull":
                    mt = (max(o[q] for q in mem) + min(c[q] for q in mem)) / 2
                else:
                    mt = (min(o[q] for q in mem) + max(c[q] for q in mem)) / 2
                return Zone(kind, hi, lo, end, j, float(mt))
            run = mem
            if pick == "blend_in_htf":
                hi, lo = float(max(h[j:k + 1])), float(min(l[j:k + 1]))
                zs = [] if not htf_zone else (list(htf_zone) if isinstance(htf_zone[0], (tuple, list)) else [htf_zone])
                if any(a <= lo and hi <= b for a, b in zs):
                    mt = (l[j] + h[k]) / 2 if kind == "bull" else (h[j] + l[k]) / 2
                    return Zone(kind, hi, lo, end, j, float(mt), levels=(float(o[j]),))
                m = k
            elif pick == "original":
                m = max(run, key=lambda q: h[q]) if kind == "bull" else min(run, key=lambda q: l[q])
            else:                                                   # largest_body
                cand = run
                if s is not None:
                    near = [q for q in run if l[q] - abs(o[q] - c[q]) <= s <= h[q] + abs(o[q] - c[q])]
                    cand = near or run
                m = min(cand, key=lambda q: ((l[q] if kind == "bull" else -h[q]), -abs(o[q] - c[q])))
            return Zone(kind, float(h[m]), float(l[m]), end, m, float((o[m] + c[m]) / 2), levels=(float(o[m]),))
    return None


BREAKER_MODES = ("range", "body", "leg", "last", "blend", "leg_disruptor")
BREAKER_CANDLES = ("extreme_close", "last", "extreme_body")


def breaker_candle(o, c, a0: int, ext_i: int, kind: str = "bull", pick: str = "extreme_close",
                   body_swing: bool = False) -> int | None:
    """The breaker candle of a bullish breaker: by default the up-close candle with the HIGHEST close in
    [a0, ext_i] (the leg from the swing low L1 before the high to the sweep extreme L2; 029 ~24:13; 048).
    Bearish: the down-close candle with the lowest close. Closed bars only: the caller passes ext_i <= the
    current bar. None when there is no such candle.
    Caption-gap A13 (`pick` = Params.breaker_candle; owner question: the spec lists "last" as the default,
    the built behaviour has always been the extreme close, which stays the default):
      "extreme_close"  the highest close (lowest for bearish); first on ties (032 ~41:26, 063 ~3:49, 081 ~12:52)
      "last"           the last up-close (down-close) candle of the leg (015 ~21:17, 043 ~18:03)
      "extreme_body"   the highest close, ties to the LARGEST body (029 / 048 / 096; 081 pairs the extreme with
                       the biggest body); never the largest body alone (032)
    body_swing (Params.breaker_body_swing, 060 / 081 "the wicks do the damage"): the extreme is judged on bodies -
    only candidates whose close is the extreme of ALL bodies of the leg (any colour, within one part in 1e9)
    qualify, so a wick-only extreme is discarded; with no such candidate the plain pick applies."""
    if pick not in BREAKER_CANDLES:
        raise ValueError(f"breaker_candle {pick!r}: expected one of {BREAKER_CANDLES}")
    a0 = max(int(a0), 0)
    rng = range(a0, int(ext_i) + 1)
    if kind == "bull":
        cand = [k for k in rng if c[k] > o[k]]
        key = lambda k: c[k]
        ext_body = max((max(o[k], c[k]) for k in rng), default=None)
        on_ext = lambda k: ext_body is not None and abs(c[k] - ext_body) <= 1e-9 * max(1.0, abs(ext_body))
    else:
        cand = [k for k in rng if c[k] < o[k]]
        key = lambda k: -c[k]
        ext_body = min((min(o[k], c[k]) for k in rng), default=None)
        on_ext = lambda k: ext_body is not None and abs(c[k] - ext_body) <= 1e-9 * max(1.0, abs(ext_body))
    if not cand:
        return None
    if body_swing:
        cb = [k for k in cand if on_ext(k)]
        cand = cb or cand
    if pick == "last":
        return cand[-1]
    if pick == "extreme_body":
        return max(cand, key=lambda k: (key(k), abs(c[k] - o[k]), -k))
    return max(cand, key=lambda k: (key(k), -k))            # first on ties (as before)


def breaker_mt(o, h, l, c, k: int, mode: str = "range") -> float:
    """Breaker mean threshold (A13.3, owner directive #6): 50% of the breaker candle's FULL
    high-low ("range", Ep 02 ~3:37-3:54 "half of that range from the candle's high and low";
    007 ~1:22-1:58) or of its body ("body" switch)."""
    if mode == "range":
        return float((h[k] + l[k]) / 2)
    if mode == "body":
        return float((o[k] + c[k]) / 2)
    raise ValueError(f"breaker mt mode {mode!r}: expected 'range' or 'body'")


def breaker_zone(o, h, l, c, a0: int, ext_i: int, i: int, kind: str = "bull",
                 mode: str = "range", mt_mode: str | None = None, pick: str = "extreme_close",
                 body_swing: bool = False) -> Zone | None:
    """Shared breaker-zone helper (A13; owner directive #14). The breaker candle is
    `breaker_candle` (highest-close up-close candle between L1 and the sweep extreme for a
    bullish breaker). Zone extent:
      "range"  the candle's full high-low (default; Ep 02 ~3:37, Ep 05 ~11:34/~15:20/~22:49,
               Ep 07's OB "entire range" [our interpretation])
      "body"   open-close only (Ep 01 ~56:19 switch)
      "leg"    D6 C (070): the whole A->B leg, from the swing low L1 (A, bar a0) to the swing high
               H (B = the highest high in [a0, ext_i]): low of L1's bar .. high of H's bar; MT =
               its midpoint [our interpretation of "inside the A-B leg"]
      "last"   D6 D (cc05_014): the LAST up-close candle before the sweep extreme (not the highest
               close), its full range [our interpretation]
      "blend"  caption-gap D6 (025 ~12:13, 042, 044 ~37:47: "these two down closed candles together it's all one"):
               the UNION of the consecutive same-colour candles around the chosen breaker candle (within
               [a0, ext_i]); MT = 50% of the union's range
      "leg_disruptor"  caption-gap D6 (070 ~46:45): from the first OPPOSITE-colour candle that disrupts the A->B
               run (a down-close candle in a bullish leg) to B: low of the leg from the disruptor .. high of B
               (bullish); falls back to the whole leg when nothing disrupts it
    `mt` = breaker_mt(mt_mode) - by default it follows the zone mode, so the default MT is 50%
    of the full range (the leg's midpoint for "leg"). Known at bar i (the caller's bar).
    `pick` / `body_swing`: the breaker candle selection (see breaker_candle)."""
    if mode not in BREAKER_MODES:
        raise ValueError(f"breaker_zone mode {mode!r}: expected one of {BREAKER_MODES}")
    a0, ext_i = max(int(a0), 0), int(ext_i)
    if mode == "leg":
        if ext_i <= a0:
            return None
        hk = a0 + int(np.argmax(h[a0:ext_i + 1])) if kind == "bull" else a0 + int(np.argmin(l[a0:ext_i + 1]))
        if kind == "bull":
            top, bot = float(h[hk]), float(min(l[a0:hk + 1]))
        else:
            top, bot = float(max(h[a0:hk + 1])), float(l[hk])
        mt = (top + bot) / 2 if (mt_mode or "range") in ("range", "leg") else breaker_mt(o, h, l, c, hk, mt_mode)
        return Zone(kind, top, bot, i, hk, mt)
    if mode == "last":
        up = (lambda k: c[k] > o[k]) if kind == "bull" else (lambda k: c[k] < o[k])
        cand = [k for k in range(a0, ext_i + 1) if up(k)]
        if not cand:
            return None
        k = cand[-1]
        mt = breaker_mt(o, h, l, c, k, "range" if (mt_mode or "range") in ("range", "last") else mt_mode)
        return Zone(kind, float(h[k]), float(l[k]), i, k, mt)
    if mode == "leg_disruptor":
        if ext_i <= a0:
            return None
        hk = a0 + int(np.argmax(h[a0:ext_i + 1])) if kind == "bull" else a0 + int(np.argmin(l[a0:ext_i + 1]))
        opp = (lambda q: c[q] < o[q]) if kind == "bull" else (lambda q: c[q] > o[q])
        d = next((q for q in range(a0 + 1, hk) if opp(q)), a0)
        if kind == "bull":
            top, bot = float(h[hk]), float(min(l[d:hk + 1]))
        else:
            top, bot = float(max(h[d:hk + 1])), float(l[hk])
        mt = (top + bot) / 2 if (mt_mode or "range") in ("range", "leg", "leg_disruptor") else breaker_mt(o, h, l, c, hk, mt_mode)
        return Zone(kind, top, bot, i, hk, mt)
    k = breaker_candle(o, c, a0, ext_i, kind, pick, body_swing)
    if k is None:
        return None
    if mode == "blend":
        same = (lambda q: c[q] > o[q]) if kind == "bull" else (lambda q: c[q] < o[q])
        j, m = k, k
        while j - 1 >= a0 and same(j - 1):
            j -= 1
        while m + 1 <= ext_i and same(m + 1):
            m += 1
        top, bot = float(max(h[j:m + 1])), float(min(l[j:m + 1]))
        if (mt_mode or "range") == "body":
            bt, bb = float(max(max(o[j:m + 1]), max(c[j:m + 1]))), float(min(min(o[j:m + 1]), min(c[j:m + 1])))
            mt = (bt + bb) / 2
        else:
            mt = (top + bot) / 2
        return Zone(kind, top, bot, i, k, mt, levels=(float(o[j]),))
    mt = breaker_mt(o, h, l, c, k, mt_mode or mode)
    if mode == "range":
        return Zone(kind, float(h[k]), float(l[k]), i, k, mt)
    return Zone(kind, float(max(o[k], c[k])), float(min(o[k], c[k])), i, k, mt)


def breakers(o, h, l, c, n: int = 2, mode: str = "range") -> list[Zone]:
    """Bullish breaker: swing low L1, swing high H, lower low (the sweep), then a candle *body*
    closes above H. The zone is the breaker candle from `breaker_zone` (highest-close up-close
    candle between L1 and the sweep extreme, full range by default) - the same rule `_scan`
    uses, so both agree. Bearish mirrors it. Known (emitted) at the closing break."""
    import bisect
    ph, pl = pivots(h, l, n)
    out = []
    used = set()
    known = {id(ph): [p.known for p in ph], id(pl): [p.known for p in pl]}
    at = {id(ph): [p.i for p in ph], id(pl): [p.i for p in pl]}
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            # in "bull" terms: hs = swing highs, ls = swing lows (mirrored for bear)
            k = bisect.bisect_right(known[id(hs)], i)         # pivots known by bar i (sorted)
            if not k:
                continue
            H = hs[k - 1]
            if (kind, H.i) in used:
                continue
            j = bisect.bisect_left(at[id(ls)], H.i)          # swing lows before H (known by H.known)
            if not j:
                continue
            L1 = ls[j - 1]
            seg = l[H.i + 1:i] if sign > 0 else h[H.i + 1:i]
            if not len(seg):
                continue
            swept = seg.min() < L1.price if sign > 0 else seg.max() > L1.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if swept and broke:
                ext_i = H.i + 1 + int(np.argmin(seg) if sign > 0 else np.argmax(seg))
                z = breaker_zone(o, h, l, c, L1.i, ext_i, i, kind, mode)
                if z is not None:
                    out.append(z)
                used.add((kind, H.i))
    return out


def turtle_soup(l, c, level: float, ext_i: int, i: int, max_depth: float,
                back_bars: int) -> bool:
    """Turtle-soup core (M12, shared by M12.x / M4.4 / D10 / Ep08.15), bullish terms: a false
    break of an old low `level` "by a little" - the extreme l[ext_i] is below the level by no more
    than `max_depth` - then a fast reversal: a candle CLOSES back above the level within
    `back_bars` bars of the extreme, at the latest at bar i (closed bars only). No MSS needed
    (022 ~2:47:29; cc05_004 ~6:45). Bearish = mirrored prices."""
    if not (l[ext_i] < level and level - l[ext_i] <= max_depth):
        return False
    if i <= ext_i or i - ext_i > back_bars:
        return False
    return bool((c[ext_i:i + 1] > level).any()) and bool(l[ext_i + 1:i + 1].min(initial=np.inf) >= l[ext_i])


def equal_clusters(prices, tol: float, bars=None, min_sep: int = 0) -> list[list[int]]:
    """A3: the clusters of equal_levels (>= 2 prices within `tol` of the cluster's lowest price),
    as lists of indices into `prices`, each ascending by price.
    Caption-gap A3-clean-high (cc01_003 ~15:33: "it trades away from that for a little while and comes right back to it"):
    with `bars` (the bar index of each price) and `min_sep` > 0 a cluster counts only when its swings are separated in time -
    the first and last member at least `min_sep` bars apart (two adjacent equal bars are one swing, not a clean high)."""
    order = sorted(range(len(prices)), key=lambda k: prices[k])
    out, k = [], 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and prices[order[j + 1]] - prices[order[k]] <= tol:
            j += 1
        if j > k:
            idx = order[k:j + 1]
            if not (bars is not None and min_sep > 0 and max(bars[q] for q in idx) - min(bars[q] for q in idx) < min_sep):
                out.append(idx)
        k = j + 1
    return out


def equal_levels(prices, tol: float, bars=None, min_sep: int = 0) -> list[float]:
    """Relative equal highs (or lows): clusters of >= 2 swing prices within `tol` of each
    other. Returns the extreme of each cluster (max for highs; pass negated lows).
    Caption-gap A3 `bars` / `min_sep`: see equal_clusters (the pool is the cluster's most extreme price - the "slightly
    above" allowance of a clean high)."""
    if bars is not None and min_sep > 0:
        return sorted(max(prices[q] for q in idx) for idx in equal_clusters(prices, tol, bars, min_sep))
    p = sorted(prices)
    out, k = [], 0
    while k < len(p):
        j = k
        while j + 1 < len(p) and p[j + 1] - p[k] <= tol:
            j += 1
        if j > k:
            out.append(p[j])
        k = j + 1
    return out


def opens(index, o, src: str = "data") -> dict[str, float]:
    """Opening prices for one day: midnight, 08:30, 09:30, 13:30 (first bar at or after).
    SPY has no bars at midnight, so its first pre-market bar (04:00) stands in for it.
    D22 `src` ("spy"): use that 04:00 stand-in even when the frame has bars from midnight (a futures / CFD frame), the old SPY
    reading kept for comparison (rulebook P1 "bias_open_src")."""
    t = index.hour * 60 + index.minute
    out = {}
    for name, m in (("midnight", 240 if src == "spy" else 0), ("0830", 510), ("0930", 570), ("1330", 810)):
        k = np.flatnonzero(t >= m)
        if len(k):
            out[name] = float(o[k[0]])
    return out


def map_midnight(ref, df) -> dict:
    """D22 (rulebook P1 "live midnight from the CFD / ES mapped to SPY"): the midnight open of a futures / CFD frame `ref` mapped to
    the traded instrument's price level, per trading date of `df`: ref's first bar from 00:00 of that calendar day times the
    ratio df.close / ref.close at the PRIOR session's last bar of `df` at or before 16:00 (known before the day starts). Returns
    {date: mapped open}; dates without a ref midnight bar or a prior overlap are absent."""
    import pandas as pd
    out = {}
    lab = df.index.date
    days = sorted(set(lab))
    rm = ref.groupby(ref.index.date).open.first()
    rm_t = ref.groupby(ref.index.date).apply(lambda x: x.index[0])
    for k in range(1, len(days)):
        d, pd_ = days[k], days[k - 1]
        if d not in rm.index or rm_t[d].hour * 60 + rm_t[d].minute > 120:
            continue                                   # the reference frame has no bar near midnight that day
        prev = df[lab == pd_]
        prev = prev[(prev.index.hour * 60 + prev.index.minute) < 960]
        if not len(prev):
            continue
        t0 = prev.index[-1]
        rc = ref.close.asof(t0)
        if rc != rc or rc <= 0:
            continue
        out[d] = float(rm[d]) * float(prev.close.iloc[-1]) / float(rc)
    return out


def rejection_blocks(o, h, l, c, n: int = 2, min_wick_frac: float = 0.0, level: str = "open_close") -> list[Zone]:
    """Rejection block (A17; cc04_006 ~5:04-10:43): a swing high of long-upper-wick candles; the zone runs
    from the highest open / close of the swing (any candle colour) up to the highest wick. A bearish
    block sits at a swing high; the bullish mirror at a swing low. Known when the swing is confirmed.
    Review fix (targets_partials A17): the swing is the pivot candle plus its `n` neighbours each side
    (it was a fixed +-1), and the pivot candle itself must show the wick - its wick at least
    `min_wick_frac` of its range (0 = any wick, the old test). Default arguments keep the old zones for
    pivot_n = 1.
    Caption-gap A17 (`level` = Params.rb_level; 015 ~2:18, 038 ~4:15, 059 ~10:11, 080 ~5:41, 090 ~34:21,
    cc04_006 ~9:23): "open_close" (the old rule) = level1 is the highest open / close of any candle of the swing;
    "close" = the highest CLOSE of the up-close candles of the swing (the lowest close of the down-close candles
    for the bullish mirror; with no such candle, the highest / lowest close of any candle). Every zone carries
    `levels` = (level1, level2, W): level2 = the wick CE = (level1 + W) / 2, W = the highest high (bullish: the
    lowest low); the targets run level1, level2, W."""
    ph, pl = pivots(h, l, n)
    out = []
    w = max(n, 1)
    for p in ph:
        a, b = max(0, p.i - w), min(len(h), p.i + w + 1)
        if level == "close":
            ups = [c[k] for k in range(a, b) if c[k] > o[k]]
            body = max(ups) if ups else max(c[a:b])
        else:
            body = max(max(o[k], c[k]) for k in range(a, b))
        rng = h[p.i] - l[p.i]
        wick = h[p.i] - max(o[p.i], c[p.i])
        if body < p.price and (min_wick_frac <= 0 or (rng > 0 and wick >= min_wick_frac * rng)):
            out.append(Zone("bear", p.price, float(body), p.known, p.i,
                            levels=(float(body), float((body + p.price) / 2), float(p.price))))
    for p in pl:
        a, b = max(0, p.i - w), min(len(h), p.i + w + 1)
        if level == "close":
            dns = [c[k] for k in range(a, b) if c[k] < o[k]]
            body = min(dns) if dns else min(c[a:b])
        else:
            body = min(min(o[k], c[k]) for k in range(a, b))
        rng = h[p.i] - l[p.i]
        wick = min(o[p.i], c[p.i]) - l[p.i]
        if body > p.price and (min_wick_frac <= 0 or (rng > 0 and wick >= min_wick_frac * rng)):
            out.append(Zone("bull", float(body), p.price, p.known, p.i,
                            levels=(float(body), float((body + p.price) / 2), float(p.price))))
    return sorted(out, key=lambda z: z.i)


def balanced_ranges(h, l, max_gap_bars: int = 0, o=None, c=None, c2_dir: bool = False) -> list[Zone]:
    """Balanced price range: where a bullish and a bearish FVG overlap, price has been
    delivered both ways. Kind follows the later gap; known when the later gap forms.
    A11 `max_gap_bars` (Params.bpr_max_gap_bars): the two gaps must form within this many bars of
    each other [our interpretation: one delivery up and back]; 0 = any pair (the old rule).
    o / c / c2_dir (review fix): the gaps follow the same A5 c2 rule as every other FVG."""
    g = fvgs(h, l, o, c, c2_dir)
    out = []
    for k, b in enumerate(g):
        for a in g[:k]:
            if max_gap_bars and b.i - a.i > max_gap_bars:
                continue
            if a.kind != b.kind and a.overlaps(b):
                out.append(Zone(b.kind, min(a.top, b.top), max(a.bottom, b.bottom), b.i, a.i))
    return out


def wick_midpoints(o: float, h: float, l: float, c: float, quarters: bool = False) -> dict[str, float]:
    """50% of a daily candle's upper and lower wicks. Caption-gap A23 (`quarters`, Params.wick_quarters; 025 ~34:43,
    028 ~15:24, 103 ~24:07: "we do gradients on wicks 75 of the wick 50 of the wick"): also the 25% / 75% levels
    measured from the body edge - "upper_q25" / "upper_q75" (body top + 25% / 75% of the upper wick) and
    "lower_q25" / "lower_q75" (body bottom - 25% / 75% of the lower wick), plus the wick extremes "upper_w" /
    "lower_w" (the high / the low) and the body edges "upper_body" / "lower_body"."""
    out = {"upper": max(o, c) + (h - max(o, c)) / 2, "lower": min(o, c) - (min(o, c) - l) / 2}
    if quarters:
        bt, bb = max(o, c), min(o, c)
        out.update(upper_q25=bt + 0.25 * (h - bt), upper_q75=bt + 0.75 * (h - bt),
                   lower_q25=bb - 0.25 * (bb - l), lower_q75=bb - 0.75 * (bb - l), upper_w=float(h), lower_w=float(l),
                   upper_body=float(bt), lower_body=float(bb))
    return out


WICK_TIERS = ("very_bearish", "normal", "overshoot", "failed")


def wick_tier(extreme: float, body_edge: float, wick_end: float, tol: float = 0.0) -> str:
    """Caption-gap A23 [our tiers]: how far a retrace into an UPPER wick got before it turned (bearish terms; mirror the
    prices for a lower wick). `body_edge` = body top, `wick_end` = the high, `extreme` = the retrace's highest price.
      <= q25 (+tol)   "very_bearish"  (turned at the 25% level: 025 / 028 heavy stance)
      <= CE  (+tol)   "normal"
      <= q75 (+tol)   "overshoot"     (103: overshoots CE but stays valid)
      beyond q75      "failed"        (also: a body close above CE - the caller tests that separately)
    A retrace that never reached the wick is "none"."""
    if extreme < body_edge - tol:
        return "none"
    w = wick_end - body_edge
    if w <= 0:
        return "none"
    for name, f in (("very_bearish", 0.25), ("normal", 0.5), ("overshoot", 0.75)):
        if extreme <= body_edge + f * w + tol:
            return name
    return "failed"


def inversion_fvgs(h, l, c, min_gap: float = 0.0) -> list[Zone]:
    """Inversion FVGs (015 ~21:00; 048 ~21:32; 102 ~1:02:03): a bearish FVG that a candle body
    closes above becomes bullish support (and a bullish FVG closed below becomes resistance).
    Same top/bottom as the original gap; known at the closing candle. A later candle must
    trade back into it for an entry, which a limit order placed after `i` guarantees."""
    out = []
    for z in fvgs(h, l):
        if z.top - z.bottom < min_gap:
            continue
        after = c[z.i + 1:]
        if z.kind == "bear":
            k = np.flatnonzero(after > z.top)
            if len(k):
                out.append(Zone("bull", z.top, z.bottom, z.i + 1 + int(k[0]), z.src))
        else:
            k = np.flatnonzero(after < z.bottom)
            if len(k):
                out.append(Zone("bear", z.top, z.bottom, z.i + 1 + int(k[0]), z.src))
    return sorted(out, key=lambda z: z.i)


def two_way_range(o, h, l, c, i: int, lookback: int = 60):
    """E6-bpr-75-stop (075 ~01:07:19) [our interpretation of "a range traded both ways"]: the most recent pair of adjacent opposite-colour legs (maximal runs of up-close / down-close candles, bars before
    i) whose ranges overlap and whose combined span [lo, hi] the close of bar i is ABOVE -> (lo, hi, last bar of the pair), else None. Known at bar i's close; bullish terms (shorts run mirrored)."""
    a = max(0, int(i) - int(lookback))
    legs = []
    for k in range(a, int(i)):
        up = bool(c[k] >= o[k])
        if legs and legs[-1][4] == up:
            legs[-1][1] = k
            legs[-1][2] = min(legs[-1][2], float(l[k]))
            legs[-1][3] = max(legs[-1][3], float(h[k]))
        else:
            legs.append([k, k, float(l[k]), float(h[k]), up])
    for q in range(len(legs) - 1, 0, -1):
        A, B = legs[q - 1], legs[q]
        if not (A[2] < B[3] and B[2] < A[3]):
            continue
        lo, hi = min(A[2], B[2]), max(A[3], B[3])
        if c[i] > hi:
            return float(lo), float(hi), int(B[1])
    return None


def voids(h, l) -> list[Zone]:
    """Liquidity voids: a true price gap between two consecutive candles, no overlap at all
    (028 ~36:17). Bullish: low[i] > high[i-1]. Known at candle i."""
    out = []
    for i in range(1, len(h)):
        if l[i] > h[i - 1]:
            out.append(Zone("bull", l[i], h[i - 1], i, i))
        elif h[i] < l[i - 1]:
            out.append(Zone("bear", l[i - 1], h[i], i, i))
    return out


MIT_DEFS = ("a15", "stoprun")
STOPRUN_X_MAX = 6


def mitigation_blocks(o, h, l, c, n: int = 1, legacy: bool = False, with_mt: bool = False, variant: str = "a15") -> list[Zone]:
    """Bullish mitigation block (A15; 033 ~1:03:50, the mirror of cc04_004 ~2:42-14:35): swing low
    A, then swing high X, then a HIGHER swing low B (no stop run below A: the breaker's failure-swing
    twin), then a body close above X; the zone is the last up-close candle at X (the failed high).
    Bearish mirrors it (high A, low X, lower high B, close below X). Known at the closing break.
    Review fix (rule_coverage A15): the old code took two lows AFTER X and never checked the A low
    before X; `legacy=True` keeps the old order.
    Caption-gap A12 (`with_mt` = Params.mit_mt_invalid; 021 ~21:06: "whether it be a breaker mitigation block or just a standard order
    block"): each zone also carries its MT - the block candle's body mean ((open + close) / 2, per D4) - in `Zone.mt`; a CE is
    `Zone.mid` on every gap and void already.
    Caption-gap A15-stoprun-variant (`variant` = Params.mit_def; cc03_002 ~19:11: "this wick down to the body is a mitigation
    block"), bullish terms: "stoprun" - U is the last up-close candle at the swing high X that starts a down leg RUNNING a prior
    swing low A's sell stops (the leg's low B is below A), and price later CLOSES back above U's high [our interpretation of "trades
    back above"]; the zone is U's upper wick, U.high down to U's body top, known at that close (Zone.src = U). The a15 variant (the
    failure swing, no stop run) is the default; the two definitions are different blocks."""
    if variant not in MIT_DEFS:
        raise ValueError(f"mit_def {variant!r}: expected one of {MIT_DEFS}")
    ph, pl = pivots(h, l, n)
    out, used = [], set()
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            hk = [p for p in hs if p.known <= i]
            if variant == "stoprun":
                # review fix: every confirmed swing high X (the last `STOPRUN_X_MAX` of them [our interpretation]) can be the failed high U,
                # not only the newest one - an intermediate pivot formed during the rally back to U must not hide it
                for H in hk[-STOPRUN_X_MAX:]:
                    if (kind, H.i) in used:
                        continue
                    before = [p for p in ls if p.i < H.i]
                    later = [p for p in ls if p.i > H.i and p.known <= i]
                    if not before or not later:
                        continue
                    A, B = before[-1], (min if sign > 0 else max)(later, key=lambda p: p.price)
                    stopped = B.price < A.price if sign > 0 else B.price > A.price
                    blk = order_block(o, h, l, c, H.i - n, H.i, "bear" if sign > 0 else "bull")
                    if not stopped or blk is None:
                        continue
                    broke = (c[i] > blk.top if sign > 0 else c[i] < blk.bottom) and i > B.i
                    if broke:
                        body = max(o[blk.src], c[blk.src]) if sign > 0 else min(o[blk.src], c[blk.src])
                        top, bot = (blk.top, float(body)) if sign > 0 else (float(body), blk.bottom)
                        out.append(Zone(kind, float(top), float(bot), i, blk.src,
                                        float((o[blk.src] + c[blk.src]) / 2) if with_mt else float("nan")))
                        used.add((kind, H.i))
                continue
            if not hk or (kind, hk[-1].i) in used:
                continue
            H = hk[-1]                                 # X: the swing high the close breaks
            if legacy:
                later = [p for p in ls if p.i > H.i and p.known <= i]
                if len(later) < 2:
                    continue
                L0, L1 = later[-2], later[-1]
            else:
                before = [p for p in ls if p.i < H.i]
                later = [p for p in ls if p.i > H.i and p.known <= i]
                if not before or not later:
                    continue
                L0, L1 = before[-1], later[0]          # A (before X), then B (after X)
                seg = l[H.i + 1:i] if sign > 0 else h[H.i + 1:i]
                if len(seg) and (seg.min() < L0.price if sign > 0 else seg.max() > L0.price):
                    used.add((kind, H.i))              # A's stops were run: a breaker, not this
                    continue
            higher_low = L1.price > L0.price if sign > 0 else L1.price < L0.price
            broke = c[i] > H.price if sign > 0 else c[i] < H.price
            if higher_low and broke:
                blk = order_block(o, h, l, c, H.i - n, H.i, "bear" if sign > 0 else "bull")
                if blk is not None:
                    out.append(Zone(kind, blk.top, blk.bottom, i, blk.src,
                                    float((o[blk.src] + c[blk.src]) / 2) if with_mt else float("nan")))
                used.add((kind, H.i))
    return out


def mitigation_alive(c, z: Zone, i: int, use_mt: bool = False) -> bool:
    """A15 `mit_body_respect` (bodies respect the block, wicks may poke) [our interpretation]: no
    close after the block formed, through bar i, beyond its far side (bullish block: below its
    bottom; bearish: above its top). Caption-gap A12 `use_mt` (Params.mit_mt_invalid, E6 / X8 for
    mitigation blocks): the line is the block's MT instead (bodies must not close through it) when it has one."""
    seg = c[z.i + 1:i + 1]
    if not len(seg):
        return True
    far = z.mt if (use_mt and z.mt == z.mt) else (z.bottom if z.kind == "bull" else z.top)
    return bool(seg.min() >= far) if z.kind == "bull" else bool(seg.max() <= far)


PB_DEFS = ("a16", "cc04_008", "cc09_008")


def propulsion_blocks(o, h, l, c, obs: list[Zone], pb_def: str = "a16", need_confirm: bool = False,
                      bias: int | None = None) -> list[Zone]:
    """Bullish propulsion block (cc04_008 ~0:30-5:40; 027 ~11:31): a down-close candle that
    trades down into an earlier bullish order block without a body close below that block's
    mean threshold; it becomes the new support. Zone = that candle's range, `mt` = its body
    midpoint (losing it = the idea is wrong). Known at that candle.
    Caption-gap A16 (`pb_def` = Params.pb_def; cc04_008 ~3:58, cc09_008 ~14:45):
      "a16"       as above (the default)
      "cc04_008"  the full event order: (1) bullish context (`bias` == +1 when given; None = not tested), (2) a
                  bullish OB, (3) the OB is CONFIRMED when a later candle trades above its highest high, (4) price
                  moves higher, (5) a LATER down-close candle trades back into the OB (low <= OB high) with no body
                  close below the OB MT in between - that candle is the PB (the separated case [our
                  interpretation]: it comes after the confirming candle)
      "cc09_008"  the looser rule: the first down-close candle after the OB, followed by a higher high; level = its
                  OPEN (mt = open); valid - known - once a later candle trades above its high
    `need_confirm` (also with "a16") applies step (3) to the a16 rule: an unconfirmed OB yields no PB."""
    if pb_def not in PB_DEFS:
        raise ValueError(f"pb_def {pb_def!r}: expected one of {PB_DEFS}")
    out = []
    n = len(c)
    for ob in obs:
        if ob.kind != "bull":
            continue
        mt = ob.mt if ob.mt == ob.mt else ob.mid
        if pb_def == "cc09_008":
            k = next((q for q in range(ob.i + 1, n) if c[q] < o[q]), None)
            if k is None:
                continue
            m = next((q for q in range(k + 1, n) if h[q] > h[k]), None)
            if m is not None:
                out.append(Zone("bull", float(h[k]), float(l[k]), m, k, float(o[k]), levels=(float(o[k]),)))
            continue
        if pb_def == "cc04_008" and bias is not None and bias != 1:
            continue
        start = ob.i + 1
        if pb_def == "cc04_008" or need_confirm:
            ci = next((q for q in range(ob.i + 1, n) if h[q] > ob.top), None)
            if ci is None:
                continue
            start = ci + 1
            if pb_def == "cc04_008" and (c[ob.i + 1:ci + 1] < mt).any():
                continue                           # the block failed before it was confirmed
        for k in range(start, n):
            if c[k] < mt:
                break                              # the order block failed
            if c[k] < o[k] and l[k] <= ob.top:
                out.append(Zone("bull", float(h[k]), float(l[k]), k, k, float((o[k] + c[k]) / 2)))
                break
    return out


# --- package setups_models detectors (rule_coverage.md section 3 "setups_models") ------------
# All in bullish terms (the engine mirrors prices for shorts); every one reads closed bars only,
# up to the index the caller passes.

OTE_LO, OTE_HI, OTE_SWEET = 0.62, 0.79, 0.705      # M13 (cc01_004 ~9:44-53:45)


def ote_band(ext: float, hi: float) -> tuple[float, float, float]:
    """M13 OTE of the impulse leg ext (swing low) -> hi: the 62-79% retracement as prices
    (lower, upper) and the 70.5% sweet spot. Bullish: lower = hi - 0.79 x leg."""
    leg = hi - ext
    return hi - OTE_HI * leg, hi - OTE_LO * leg, hi - OTE_SWEET * leg


def three_drives(lows: list, ext: float, ext_i: int, i: int, min_i: int = 0, level: float | None = None, tol: float = 0.0) -> bool:
    """M2.7 three drives ("three Indians", 093 ~10:37; 074 ~32:49) [our interpretation of the bar
    test]: the last two confirmed swing lows (Pivot list `lows`, known by bar i, before the sweep
    extreme ext_i, at or after bar min_i) and the extreme are three successively LOWER lows, and
    the pushes fail - the third drive extends below the second by less than the second extended
    below the first. Bullish: drives down into the swept level.
    Caption-gap M2-three-drives-breaker-fallback (093 ~00:11:14; `td_same_level`): with `level` given all three drives (the two swings and the extreme) must lie within `tol` of that level -
    the same sensitive level driven into three times."""
    pl = [q for q in lows if min_i <= q.i < ext_i and q.known <= i]
    if len(pl) < 2:
        return False
    a, b = pl[-2], pl[-1]
    if not (a.price > b.price > ext):
        return False
    if level is not None and not (abs(a.price - level) <= tol and abs(b.price - level) <= tol and abs(ext - level) <= tol):
        return False
    return (b.price - ext) < (a.price - b.price)


def wick_ce(o, l, c, k: int) -> float:
    """M11c / M0.5: the CE (50%) of candle k's lower wick (body low -> low)."""
    b = min(o[k], c[k])
    return float((b + l[k]) / 2)


def leg_sibi(h, l, o, c, a: int, ext_i: int, c2_dir: bool = False) -> Zone | None:
    """M1.3 / Ep07.6: the last bearish FVG (SIBI) formed in the leg down into the low - third
    candle in [a, ext_i]. None when the leg left none."""
    a = max(int(a), 2)
    last = None
    for k in range(a, int(ext_i) + 1):
        if h[k] < l[k - 2] and (not c2_dir or c[k - 1] < o[k - 1]):
            last = Zone("bear", float(l[k - 2]), float(h[k]), k, k - 1)
    return last


def ifvg_passes(h, l, top: float, bottom: float, a: int, b: int) -> str:
    """A8 depth rule (102 ~1:09:00) for an inversion FVG, bullish terms (an old bearish gap
    top/bottom that a later close went above): how price used the gap between its formation
    (bar a) and the inverting close (bar b), exclusive. "none" = untouched (one pass: the
    inversion itself -> may reach the far edge), "partial" = traded into it, "both" = traded
    through it and back (near edge, CE at most)."""
    if b - a <= 1:
        return "none"
    hh = h[a + 1:b].max()
    if hh > top:
        return "both"
    return "partial" if hh >= bottom else "none"


def reaper(o, h, l, c, a0: int, hk: int, ext_i: int, c2_dir: bool = False) -> Zone | None:
    """A24.2 Reaper (076 ~18:30-22:20) [our interpretation of the bar test]: of a bullish breaker,
    the FVG in the DISCOUNT half of its impulse leg L1 (bar a0) -> H (bar hk) - CE at or below the
    leg's midpoint - that price cut through (a close below its bottom) on the way to the lower low
    (bars hk+1 .. ext_i). The newest such gap; None if none."""
    if hk <= a0:
        return None
    mid = (float(l[a0]) + float(h[hk])) / 2
    out = None
    for z in fvgs(h[:hk + 1], l[:hk + 1], o[:hk + 1], c[:hk + 1], c2_dir):
        if z.kind != "bull" or z.i - 2 < a0 or z.i > hk or z.mid > mid:
            continue
        seg = c[hk + 1:ext_i + 1]
        if len(seg) and seg.min() < z.bottom:
            out = z
    return out


def reclaimed_obs(o, h, l, c, a: int, ext_i: int, i: int) -> list[Zone]:
    """A18 reclaimed OB (cc04_007 ~0:50-5:00; 104 ~46:56): down-close candles on the sell side of
    the curve (bars a .. ext_i-1) each followed by a bounce (the next candle closes up), reclaimed
    after the low - a close above the candle's high in ext_i+1 .. i. Zone = the candle's range,
    known at the reclaiming close."""
    out = []
    for k in range(max(int(a), 0), int(ext_i)):
        if not (c[k] < o[k] and k + 1 <= ext_i and c[k + 1] > o[k + 1]):
            continue
        seg = c[ext_i + 1:i + 1]
        hit = np.flatnonzero(seg > h[k])
        if len(hit):
            out.append(Zone("bull", float(h[k]), float(l[k]), int(ext_i + 1 + hit[0]), k,
                            float((o[k] + c[k]) / 2)))
    return out


def tf_pivots(idx, h, l, base: int, m: int, n: int = 1) -> tuple[list, list]:
    """Ep08.16: swing highs/lows on clock-aligned m-minute bars built from base-minute bars
    (h / l arrays, side space). Pivot.i = the base bar holding the m-minute extreme, Pivot.known =
    the last base bar of the m-minute bar that confirms it (n bars later), only buckets that are
    complete. Returns (highs, lows) sorted by bar."""
    import pandas as pd
    b = pd.Series(np.arange(len(idx)), index=idx).groupby(idx.floor(f"{m}min"))
    first, last = b.min().values, b.max().values
    done = np.asarray((idx[last] - b.min().index) >= pd.Timedelta(minutes=m - base))
    hh = np.array([h[a:z + 1].max() for a, z in zip(first, last)])
    ll = np.array([l[a:z + 1].min() for a, z in zip(first, last)])
    ph, pl = pivots(hh, ll, n)
    out_h = [Pivot(int(first[q.i] + np.argmax(h[first[q.i]:last[q.i] + 1])), q.price, int(last[q.known]))
             for q in ph if done[q.known]]
    out_l = [Pivot(int(first[q.i] + np.argmin(l[first[q.i]:last[q.i] + 1])), q.price, int(last[q.known]))
             for q in pl if done[q.known]]
    return out_h, out_l


FS_DEFS = ("m4", "no_new_extreme")


def failure_swing(highs: list, lows: list, level: float, max_above: float, i: int,
                  min_i: int = 0, fs_def: str = "m4") -> tuple | None:
    """M4.5 failure swing (cc05_005) [CC], bullish terms: the last confirmed swing low B (known by
    bar i, at or after min_i) sits above the key level `level` by at most `max_above` - it failed
    to reach it - and the swing high H before B is the breaking point. Returns (B, H) or None.
    Caption-gap M4-failure-swing-no-new-extreme (`fs_def` = Params.fs_def; cc05_005 ~19:40: "it can't make another pass through"):
    "no_new_extreme" drops the "B fails to reach K" requirement - the defining fact is only that the retracement makes NO NEW
    EXTREME: an earlier swing low L1 reached, touched or traded through the key level (L1 <= level + max_above), price rallied to
    the swing high H, and the last swing low B is HIGHER than L1. Where K sits relative to B is irrelevant (B may be above or below
    it). Same return (B, H); the break above H or its retest is the trade."""
    if fs_def not in FS_DEFS:
        raise ValueError(f"fs_def {fs_def!r}: expected one of {FS_DEFS}")
    pl = [q for q in lows if q.i >= min_i and q.known <= i]
    if not pl:
        return None
    B = pl[-1]
    if fs_def == "m4":
        if not (level < B.price <= level + max_above):
            return None
        hs = [q for q in highs if q.i < B.i and q.known <= i]
        if not hs:
            return None
        return B, hs[-1]
    hs = [q for q in highs if q.i < B.i and q.known <= i]
    if not hs:
        return None
    H = hs[-1]
    prior = [q for q in lows if q.i < H.i and q.known <= i and q.i >= min_i]
    if not prior:
        return None
    L1 = prior[-1]
    if L1.price <= level + max_above and B.price > L1.price:
        return B, H
    return None


def implied_fvgs(o, h, l, c) -> list[Zone]:
    """A24.1 implied FVG (035 ~29:46: "the consequent encroachment of this wick and this wick,
    that range projected out"; named once, never defined) [our interpretation of the bar test]:
    three candles with a displacement middle candle (bullish: up-close) whose outer wicks overlap
    (no real FVG: low[k] <= high[k-2]); the implied gap runs from the CE of candle 1's upper wick
    (between its body top and high) up to the CE of candle 3's lower wick (between its low and
    body bottom), when the latter is higher. Bearish mirrors it. Known at the third candle k."""
    out = []
    for k in range(2, len(h)):
        a, b = k - 2, k
        if c[k - 1] > o[k - 1] and l[b] <= h[a]:
            lo_ = (max(o[a], c[a]) + h[a]) / 2          # candle 1 upper-wick CE
            hi_ = (min(o[b], c[b]) + l[b]) / 2          # candle 3 lower-wick CE
            if hi_ > lo_:
                out.append(Zone("bull", float(hi_), float(lo_), k, k - 1))
        elif c[k - 1] < o[k - 1] and h[b] >= l[a]:
            hi_ = (min(o[a], c[a]) + l[a]) / 2          # candle 1 lower-wick CE
            lo_ = (max(o[b], c[b]) + h[b]) / 2          # candle 3 upper-wick CE
            if hi_ > lo_:
                out.append(Zone("bear", float(hi_), float(lo_), k, k - 1))
    return out


# --- caption-gap pass, package levels_detectors #1/3 (digests/rulebook_gaps/*.md) -------------------------------------
# Pure detectors in bullish terms (the engine mirrors prices for shorts); each reports the bar at which its object is known.

def pass_state(h, l, z: Zone, a: int, b: int, side0: int | None = None) -> tuple[int, int]:
    """Caption-gap A5 (026 ~1:58:21, 050 ~30:29, 060 ~1:06:21: "every price is offered at least two times"): the
    number of (up, down) passes of the band `z` = [z.bottom, z.top] over bars a..b (wicks count; the caller picks `a`:
    z.src to count an FVG's own formation candle, z.i + 1 for the passes after it).
    Price starts on `side0` (-1 below the band, +1 above; default: -1 for a "bull" band - formed by a move up - and
    +1 for a "bear" one); a bar whose high reaches the top while price is below is an UP pass (price is then above),
    a bar whose low reaches the bottom while price is above is a DOWN pass. A bar spanning the whole band counts
    the pass that leaves the current side. Pass states: (0, 0) open draw; one side only = one-sided (still a target,
    the missing side is the next delivery); both >= 1 = efficient (not a target)."""
    side = side0 if side0 is not None else (-1 if z.kind == "bull" else 1)
    up = down = 0
    for k in range(max(a, 0), min(b, len(h) - 1) + 1):
        if side < 0 and h[k] >= z.top:
            up += 1
            side = 1
        elif side > 0 and l[k] <= z.bottom:
            down += 1
            side = -1
    return up, down


def is_efficient(up: int, down: int) -> bool:
    """A5: both passes seen = efficient delivery (not a target)."""
    return up >= 1 and down >= 1


def single_pass_bprs(o, h, l, c, forms: tuple = ("gap", "range"), pivot_n: int = 2) -> list[Zone]:
    """Caption-gap A11 Type 2 BPR (001 ~15:17, 003 ~29:37, 032 ~51:23, 075 ~54:50: "one single pass one single pass"):
    a gap Z = [lo, hi] that price crossed fully in one direction and then fully in the other in ONE pass, then left.
    Forms (`forms`):
      "gap"         Z = an FVG or a void (both kinds). Price crossed it once forming it (a bullish FVG: up). The
                    return pass is the first later bar whose range reaches the far edge (a bullish FVG: low <=
                    bottom); a touch that does not cross is repricing, not balancing, and sets nothing. The gap is
                    BALANCED at the first bar at or after the return pass whose whole range lies beyond the gap on the
                    far side (high < bottom after a return pass down; low > top after one up). Another crossing back
                    before that bar spoils the single pass: nothing is set.
      "range"       075 ~54:50: swing high H, sell-side delivery to the lowest low L before price trades above H -
                    then [L, H] is the BPR (a pivot_n-confirmed low); balanced when a bar's low is above H. Bearish
                    mirror: swing low, buy-side delivery to H1, a trade below the low.
      "two_candle"  variant (a): adjacent opposite-colour candles i, i+1 with overlapping ranges; Z = [max(low),
                    min(high)] (extended right; midpoint = EQ); balanced at the first later bar fully beyond it.
    The zone's role follows the pass that LEFT: left above = "bull" (support), left below = "bear" (resistance).
    Returned as Zone(kind="bpr2", tag="bull"/"bear", i = the bar the return pass completed (the zone is known then),
    bi = the balanced bar or -1 while it has not been left; callers use `bi` only when bi <= the current bar).
    All timeframes."""
    n = len(c)
    out: list[Zone] = []
    seen = set()
    if "gap" in forms:
        cands = list(fvgs(h, l)) + list(voids(h, l))
        for z in cands:
            key = (round(float(z.top), 9), round(float(z.bottom), 9), z.kind)
            if key in seen:
                continue
            seen.add(key)
            bull = z.kind == "bull"                     # formed by a move up: the return pass is DOWN
            kp = None
            for k in range(z.i + 1, n):
                if (l[k] <= z.bottom) if bull else (h[k] >= z.top):
                    kp = k
                    break
            if kp is None:
                continue
            bi, spoiled = -1, False
            for j in range(kp, n):
                if (h[j] < z.bottom) if bull else (l[j] > z.top):
                    bi = j
                    break
                if j > kp and ((h[j] >= z.top) if bull else (l[j] <= z.bottom)):
                    spoiled = True                      # crossed back before leaving: not one pass
                    break
            if spoiled:
                continue
            out.append(Zone("bpr2", float(z.top), float(z.bottom), kp, z.src, tag="bear" if bull else "bull", bi=bi))
    if "range" in forms:
        ph, pl = pivots(h, l, pivot_n)
        for H in ph:
            kb = next((k for k in range(H.i + 1, n) if h[k] > H.price), None)
            if kb is None or kb - H.i < 2 * pivot_n + 1:
                continue
            m = H.i + 1 + int(np.argmin(l[H.i + 1:kb]))
            if m + pivot_n >= kb or l[m] >= H.price:
                continue                                 # the low must be a confirmed swing before the break
            bi = next((j for j in range(kb, n) if l[j] > H.price), -1)
            out.append(Zone("bpr2", float(H.price), float(l[m]), kb, H.i, tag="bull", bi=bi))
        for Lw in pl:
            kb = next((k for k in range(Lw.i + 1, n) if l[k] < Lw.price), None)
            if kb is None or kb - Lw.i < 2 * pivot_n + 1:
                continue
            m = Lw.i + 1 + int(np.argmax(h[Lw.i + 1:kb]))
            if m + pivot_n >= kb or h[m] <= Lw.price:
                continue
            bi = next((j for j in range(kb, n) if h[j] < Lw.price), -1)
            out.append(Zone("bpr2", float(h[m]), float(Lw.price), kb, Lw.i, tag="bear", bi=bi))
    if "two_candle" in forms:
        for i in range(n - 1):
            down_up = c[i] < o[i] and c[i + 1] > o[i + 1]
            up_down = c[i] > o[i] and c[i + 1] < o[i + 1]
            if not (down_up or up_down):
                continue
            lo_, hi_ = max(l[i], l[i + 1]), min(h[i], h[i + 1])
            if hi_ <= lo_:
                continue
            if down_up:
                bi = next((j for j in range(i + 2, n) if l[j] > hi_), -1)
            else:
                bi = next((j for j in range(i + 2, n) if h[j] < lo_), -1)
            out.append(Zone("bpr2", float(hi_), float(lo_), i + 1, i, tag="bull" if down_up else "bear", bi=bi))
    return sorted(out, key=lambda z: (z.i, z.top))


def fvg_continuation_trigger(h, l, z: Zone, start: int, end: int, at_ce: bool = True) -> int | None:
    """Caption-gap A11 continuation trigger (056 ~7:24): after a retrace into a bullish FVG `z` to at least its CE
    (`at_ce`; else its high[c1] = z.bottom), a trade ABOVE the FVG high is permission toward the next buy-side draw.
    Returns the first bar in [start, end] that trades above z.top after such a retrace (the retrace and the trade
    above may share a bar only when the bar opens below; a high above the top after a low into the zone counts at
    that bar), else None. Bearish: mirror the prices."""
    reach = z.mid if at_ce else z.bottom
    seen = False
    for k in range(max(start, 0), min(end, len(h) - 1) + 1):
        if l[k] <= reach:
            seen = True
        if seen and h[k] > z.top:
            return k
    return None


def consolidation_ob_opens(o, h, l, c, min_bars: int = 4, width_mult: float = 1.5, lead: int = 3) -> list[Zone]:
    """Caption-gap A12 (008 ~4:09, EUR/USD 1h, one example): on the bars passed in (the caller passes 60-minute bars),
    the last down-close candle before a consolidation range, in a bullish context - its OPEN extended to the right
    is support; the bearish mirror (the last up-close candle before the range, bearish context) is resistance.
    [our interpretation] consolidation = a run of >= `min_bars` consecutive bars whose total range (max high - min
    low) is at most `width_mult` x their mean bar range, extended while it holds; the candle is searched within
    `lead` bars before the run; bullish context = the bar before the run closed above the close `lead` bars earlier
    (the move into the range was up). A body close below the open (bullish) invalidates it - tested by the caller.
    Zone(kind="bull"/"bear", top = bottom = the open, i = the bar at which the range reached `min_bars`, src = the
    candle, tag="cons_ob_open", levels=(open,))."""
    n = len(c)
    out = []
    s = 0
    while s <= n - min_bars:
        e = s + min_bars - 1
        rngs = h[s:e + 1] - l[s:e + 1]
        if not (h[s:e + 1].max() - l[s:e + 1].min() <= width_mult * rngs.mean() + 1e-12):
            s += 1
            continue
        known = e
        while e + 1 < n and (max(h[s:e + 2]) - min(l[s:e + 2])) <= width_mult * (h[s:e + 2] - l[s:e + 2]).mean() + 1e-12:
            e += 1
        if s >= 1:
            bull = c[s - 1] > c[max(0, s - 1 - lead)]
            if bull:
                k = next((q for q in range(s - 1, max(s - 1 - lead, -1), -1) if c[q] < o[q]), None)
            else:
                k = next((q for q in range(s - 1, max(s - 1 - lead, -1), -1) if c[q] > o[q]), None)
            if k is not None:
                out.append(Zone("bull" if bull else "bear", float(o[k]), float(o[k]), known, k,
                                tag="cons_ob_open", levels=(float(o[k]),)))
        s = e + 1
    return out


def invert(z: Zone, i_close: int, role_kind: str, src_kind: str = "ob") -> Zone:
    """Caption-gap A8 (090 ~2:11:45, 068 ~13:37, 086 ~11:30, 035 ~1:02:55: "any PD array can be inversion levels but
    they're not zones"): a body close at `i_close` through a PD array flips it to the opposite role. Only THREE
    prices are kept: high, low and MT / CE (the zone's MT when it has one - an OB per D4, a breaker's 50% of
    high-low - else the CE = 50%). `role_kind` is the NEW role ("bull" = support after a body close above a bearish
    array, "bear" = resistance after a body close below a bullish one). Returns Zone(kind="inv_<src_kind>", tag=role,
    i = i_close, levels=(lo, mt, hi))."""
    mt = z.mt if z.mt == z.mt else z.mid
    return Zone("inv_" + src_kind, float(z.top), float(z.bottom), int(i_close), z.src, float(mt),
                tag=role_kind, levels=(float(z.bottom), float(mt), float(z.top)))


def inverted_arrays(o, h, l, c, zones: list, src_kind: str, start_at: int = 0) -> list[Zone]:
    """The inversions (see `invert`) of `zones`: a bullish zone that a LATER candle closes below (its close under the
    zone's bottom) takes the "bear" role, a bearish zone that a candle closes above takes the "bull" role. The first such
    candle after the zone formed (and at or after `start_at`) is the inversion bar; the caller drops the new role again
    on a body close back through its MT."""
    out = []
    for z in zones:
        a = max(z.i + 1, start_at)
        if z.kind == "bull":
            k = next((q for q in range(a, len(c)) if c[q] < z.bottom), None)
            role = "bear"
        else:
            k = next((q for q in range(a, len(c)) if c[q] > z.top), None)
            role = "bull"
        if k is not None:
            out.append(invert(z, k, role, src_kind))
    return sorted(out, key=lambda q: q.i)


def reclaimed_fvgs(h, l, c, zones: list, swing_n: int = 2, min_bars: int = 4) -> list[Zone]:
    """Caption-gap A5 (027 ~22:24, 091 ~20:18: "then it can be reclaimed"): a BROKEN bullish FVG is invalid; it is
    reclaimed as a bullish discount array only if (1) price first moves away below it, then (2) comes back above the
    FVG high. [our interpretation] broken = a body close below its bottom (bar b); "moves away" = a confirmed swing
    low (pivot, `swing_n` bars each side) below the bottom made after the break; the reclaim = the FIRST close above
    the FVG high after the break (the return), valid only when that swing was confirmed by then and the return comes at
    least `min_bars` bars after the break - chop across the gap (a return within `min_bars` - 1 bars of the break) does
    not reclaim it, and the zone is then judged again from the next break. Returns Zone(kind, top, bottom, i = the
    reclaim bar, src, tag="reclaimed", bi = the break bar). Bearish zones mirror (a close above the top, a swing high
    above it, then a close below the bottom). Bias (not in premium) is the caller's gate."""
    ph, pl = pivots(h, l, swing_n)
    out = []
    for z in zones:
        bull = z.kind == "bull"
        piv = pl if bull else ph
        start = z.i + 1
        while start < len(c):
            b = next((k for k in range(start, len(c)) if (c[k] < z.bottom if bull else c[k] > z.top)), None)
            if b is None:
                break
            r0 = next((k for k in range(b + 1, len(c)) if (c[k] > z.top if bull else c[k] < z.bottom)), None)
            if r0 is None:
                break
            sw = [q for q in piv if q.i > b and (q.price < z.bottom if bull else q.price > z.top) and q.known <= r0]
            if sw and r0 - b >= min_bars:
                out.append(Zone(z.kind, z.top, z.bottom, r0, z.src, tag="reclaimed", bi=b))
                break
            start = r0
    return sorted(out, key=lambda q: q.i)


def converged_count(z: Zone, others: list, wick_ces: list, tol: float) -> int:
    """Caption-gap confluence (100 ~6:05, 103 ~4:38/~25:04, 011 ~7:19: "that's three PD arrays then you see the
    reaction"): how many OTHER arrays converge on the PD-array level `z`:
      (a) each array in `others` (OBs / VIs / FVGs, any `.top` / `.bottom`) that overlaps it - an OB that also holds
          an FVG and / or a VI;
      (b) each wick CE in `wick_ces` that lies inside `z`, especially near its CE [our interpretation of "near":
          within `tol` of the CE] - the wick CE counts once, and a second time when it is near the CE."""
    n = 0
    for o_ in others:
        if o_ is not z and o_.bottom < z.top and o_.top > z.bottom:
            n += 1
    for w in wick_ces:
        if z.bottom <= w <= z.top:
            n += 1
            if abs(w - z.mid) <= tol:
                n += 1
    return n


def diagonal_lows(lows: list, tol: float, i: int | None = None, min_swings: int = 3):
    """Caption-gap A3 (045 ~26:02, cc03_007 ~2:12/~23:18: "diagonal support which I don't have any faith in"): a smooth
    diagonal run of HIGHER lows on the execution timeframe is retail stop liquidity beneath it - expect a spike
    through. `lows` = [(bar, price)] swing lows, oldest first, each known; the LAST `min_swings` or more strictly
    rising lows within `tol` of one straight line (through the first and the last of the chain) qualify
    [our interpretation: >= 3 swings]. Returns (level_at_i, slope, n_swings) - the extrapolated line at bar `i`
    (default the last swing) - or None. The longest recent chain wins."""
    if len(lows) < min_swings:
        return None
    best = None
    last = lows[-1]
    for s in range(0, len(lows) - min_swings + 1):
        chain = lows[s:]
        (x0, y0), (x1, y1) = chain[0], chain[-1]
        if x1 <= x0 or y1 <= y0:
            continue
        slope = (y1 - y0) / (x1 - x0)
        if all(chain[q][1] > chain[q - 1][1] for q in range(1, len(chain))) and \
                all(abs(y - (y0 + slope * (x - x0))) <= tol for x, y in chain):
            best = (chain, slope, x0, y0)
            break
    if best is None:
        return None
    chain, slope, x0, y0 = best
    at = last[0] if i is None else i
    return (float(y0 + slope * (at - x0)), float(slope), len(chain))


def dealing_range(h, l, o, c, i: int, mode: str = "energetic", n_disp: int = 5, atr_n: int = 14,
                  impulse_frac: float = 0.6, atr_mult: float = 1.0, close_tol_atr: float = 0.25, lookback: int = 600,
                  consol_atr: float = 3.0):
    """Caption-gap A21 / M13 dealing range anchor (028 ~1:07:33, 044 ~40:26, cc01_005 ~2:20/~9:40/~19:23, cc04_002 ~18:44:
    "obvious price swings are the ones we look at"), bullish terms, closed bars up to `i`. Among the candidate swing
    lows (3-candle pivots, confirmed by bar i) pick the most recent one FOLLOWED BY DISPLACEMENT - consecutive
    same-direction candles leaving >= 1 bullish FVG within `n_disp` bars of the low - whose leg (the low to the highest
    high after it) is IMPULSIVE [our thresholds]: >= `impulse_frac` of its bars close up, or an FVG inside the leg, or a
    size >= `atr_mult` x ATR(`atr_n`) (a leg that passes none of the three is not a candidate); a low that is an inner swing low of
    a consolidation (window of 8 bars tighter than `consol_atr` x ATR, an earlier lower low in it) is skipped. If the two latest
    candidates are close (lows within `close_tol_atr` x ATR) take the one with more bars clustered around it (bars whose
    low is within that band). Older rounded lows (no pivot, no displacement) and pivots inside a consolidation never
    qualify: the anchor is where the impulse departs. Range = that low .. the leg high (wicks); EQ = 50%. Returns
    (low_bar, high_bar, low, high) or None. mode "mss_leg" returns None (the caller keeps the sweep-extreme leg)."""
    if mode != "energetic" or i < 3:
        return None
    a = max(0, i - lookback)
    hh, ll = np.asarray(h[a:i + 1], float), np.asarray(l[a:i + 1], float)
    oo, cc = np.asarray(o[a:i + 1], float), np.asarray(c[a:i + 1], float)
    atr = float((hh - ll)[-atr_n:].mean()) if len(hh) else 0.0
    if not atr > 0:
        return None
    pl_ = [q for q in pivots(hh, ll, 1)[1] if q.known <= len(hh) - 1]
    gaps = [g for g in fvgs(hh, ll) if g.kind == "bull"]
    cands = []
    for q in pl_:
        hk = q.i + int(np.argmax(hh[q.i:]))
        if hk <= q.i or not hh[hk] > q.price:
            continue
        disp = [g for g in gaps if q.i <= g.i - 1 <= q.i + n_disp]
        if not disp:                                      # not followed by displacement (an older rounded low)
            continue
        seg = slice(q.i, hk + 1)
        # impulsive leg, the three tests of the spec (any one): >= impulse_frac of its bars close up / a bullish FVG inside the leg
        # (its third candle at or before the leg high) / a size >= atr_mult x ATR
        frac = float((cc[seg] > oo[seg]).mean())
        big = (hh[hk] - q.price) >= atr_mult * atr
        fvg_in = any(g.i <= hk for g in disp)
        if not (frac >= impulse_frac or big or fvg_in):
            continue
        # a pivot INSIDE a consolidation: an earlier low in the 8 bars before it lies lower while that whole window is tighter than
        # `consol_atr` x ATR (an inner swing low of a chop, not where the impulse departs) [our interpretation]
        w0 = max(0, q.i - 8)
        if q.i > w0 and (hh[w0:q.i + 1].max() - ll[w0:q.i + 1].min()) < consol_atr * atr and ll[w0:q.i].min() < q.price:
            continue
        cands.append((q, hk))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0].i)
    pick = cands[-1]
    if len(cands) >= 2 and abs(cands[-1][0].price - cands[-2][0].price) <= close_tol_atr * atr:
        near = lambda q: int((np.abs(ll - q.price) <= close_tol_atr * atr).sum())
        pick = max(cands[-2:], key=lambda x: (near(x[0]), x[0].i))
    q, hk = pick
    return (a + q.i, a + hk, float(q.price), float(hh[hk]))


def vb_context(kind: str, near: float, far: float, closes, highs, lows, want: int | None = None,
               n_days: int = 5, ex_highs=None, ex_lows=None) -> str:
    """Caption-gap L8 (cc04_009 ~00:02:48: "this could potentially be an exhaustion gap"): validity of a vacuum block
    (a gap between two sessions' prices). `kind` "bull" = the gap opens UP (the open `near` above the last close
    `far`), "bear" = down. `closes` = the prior daily closes (oldest first, at least `n_days` + 1); `highs` / `lows` =
    the prior 20 daily highs / lows (the 20-day range, EQ = its midpoint).
      "exhaustion"   a gap up after `n_days` consecutive up-close days (each close above the one before) or a last close
                     above the 20-day high: tagged exhaustion and NOT used (bearish mirror: gap down after down days or
                     below the 20-day low). `ex_highs` / `ex_lows` = the 20 sessions BEFORE the last close's session
                     (the range that close can break out of; default = highs / lows, which is only right when the
                     last close is not itself part of them)
      "invalid"      a bullish VB is valid only when the bias is bullish (`want` == +1, when given) and the gap's lower
                     edge lies BELOW the 20-day EQ (discount); the bearish VB needs the mirror
      "valid"        otherwise"""
    closes = list(closes)
    if len(closes) >= n_days + 1:
        run = closes[-(n_days + 1):]
        ups = all(run[k] > run[k - 1] for k in range(1, len(run)))
        dns = all(run[k] < run[k - 1] for k in range(1, len(run)))
    else:
        ups = dns = False
    hi20 = max(highs) if len(highs) else None
    lo20 = min(lows) if len(lows) else None
    xh = hi20 if ex_highs is None else (max(ex_highs) if len(ex_highs) else None)
    xl = lo20 if ex_lows is None else (min(ex_lows) if len(ex_lows) else None)
    last = closes[-1] if closes else None
    if kind == "bull":
        if ups or (xh is not None and last is not None and last > xh):
            return "exhaustion"
        if want is not None and want != 1:
            return "invalid"
        if hi20 is not None and lo20 is not None and not min(near, far) < (hi20 + lo20) / 2:
            return "invalid"
        return "valid"
    if dns or (xl is not None and last is not None and last < xl):
        return "exhaustion"
    if want is not None and want != -1:
        return "invalid"
    if hi20 is not None and lo20 is not None and not max(near, far) > (hi20 + lo20) / 2:
        return "invalid"
    return "valid"


def ipda_month_end(dates: list, day) -> int | None:
    """Caption-gap B21 (cc05_001 ~00:53:44: "the 60 the 40 and the 20 trading days left of the most recent calendar
    month"): the index into `dates` (the prior sessions, oldest first, all before `day`) of the FIRST trading day of the
    most recent CLOSED calendar month. The IPDA windows then end on the session before it (index - 1). None when the
    history does not reach that day."""
    y, m = day.year, day.month
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    for k, d in enumerate(dates):
        if (d.year, d.month) == (y, m):
            return k
    return None


def ipda_end_index(dates: list, day, anchor: str, h=None, l=None, c=None) -> int:
    """The number of completed sessions (of `dates`, all before `day`) the IPDA windows of `anchor` cover - their END (exclusive) - the shared rule of
    ld2.ipda_windows and the htf.table array window (caption-gap B21 ipda_arrays): "rolling" = all of them (yesterday is day 1); "month" = the
    session before the first trading day of the last CLOSED month; "current_month" = through the first trading day of the CURRENT month (fixed
    all month; 0 when the history does not reach it, all of them on that first day itself); "swing" = through the last daily MSS (`h`, `l`, `c`
    = the daily arrays of `dates`). 0 when the anchor cannot be placed."""
    n = len(dates)
    if anchor in ("rolling", "daily", None):
        return n
    if anchor == "month":
        k = ipda_month_end(dates, day)
        return k if k is not None else 0
    if anchor == "current_month":
        k = next((j for j, d in enumerate(dates) if (d.year, d.month) == (day.year, day.month)), None)
        if k is None:
            return n
        return k + 1 if (k > 0 and (dates[k - 1].year, dates[k - 1].month) != (day.year, day.month)) else 0
    if anchor == "swing" and n:
        k = daily_mss_end(h, l, c)
        return (k + 1) if k is not None else 0
    return n


def daily_mss_end(h, l, c, n: int = 2) -> int | None:
    """Caption-gap B21 "swing_date" anchor (cc05_001 ~26:56: "the intermediate high/low or MSS within the last 60
    days"): the index of the LAST daily MSS in the daily arrays (closed days only): the last day whose close breaks
    the most recent confirmed daily swing high (close above it) or low (close below it), the swings being `n`-day
    pivots known before that close. The IPDA windows then end on that day. None when there is none."""
    ph, pl = pivots(h, l, n)
    last = None
    for k in range(len(c)):
        hs = [q.price for q in ph if q.known <= k - 1]
        ls = [q.price for q in pl if q.known <= k - 1]
        if (hs and c[k] > hs[-1] and (k == 0 or c[k - 1] <= hs[-1])) or (ls and c[k] < ls[-1] and (k == 0 or c[k - 1] >= ls[-1])):
            last = k
    return last


# --- caption-gap pass, package levels_detectors #2/3 (digests/rulebook_gaps/*.md) -------------------------------------------
# Pure detectors (arrays in, objects out), bullish terms unless a function says otherwise; each reports the bar at which its
# object is known. The engine glue is in ld3.py.

def first_old_beyond(pivs, h_today: float):
    """Caption-gap A2-which-old-high (002 ~00:34: "this is the first one you go to that would be higher than this one"): walk the
    higher-timeframe swing highs from the NEWEST to the oldest and return the first price above `h_today` (the highest high since
    today's open) - the active buy-side pool. `pivs` = Pivot objects or plain prices, oldest first. The sell side is the mirror (pass
    negated lows and negate the result). None when no older swing high is above."""
    for q in reversed(list(pivs)):
        px = float(q.price if hasattr(q, "price") else q)
        if px > h_today:
            return px
    return None


def engineered_pools(highs: list, lows: list, i: int, short_pts: float, h=None, fvg_bottoms=(), fvg_tol: float = 1.0) -> list:
    """Caption-gap A3-engineered-liquidity (035 ~49:54: "falls short of it, drops down, and traders do - they go short"): an old swing
    high H1, then a LATER LOWER high H2 that falls short of it (0 < H1 - H2 <= `short_pts`, no higher high between them), and price
    drops away from H2: a swing low after H2 below the lowest swing low between H1 and H2 (none between: any later swing low).
    The new shorts' buy stops rest above H2 and H1, so the pool is at H1. created = the
    bar at which the confirming swing low is known (<= i); score = bars between H1 and H2, +1 when an opposing (bearish) FVG
    bottom lies within `fvg_tol` above H1. With `h` (the bar highs) a pool traded through since H2 (high > H1 through bar i) is
    dropped. [our interpretation: the ranking weights]. Mirror for the sell side by passing negated prices. Returns
    [(price, score, created_bar, H2's bar)]."""
    ph = [q for q in highs if q.known <= i]
    pl = [q for q in lows if q.known <= i]
    out = []
    for b, H2 in enumerate(ph):
        H1 = None
        for H in reversed(ph[:b]):
            if H.price > H2.price:
                H1 = H
                break
        if H1 is None or H1.price - H2.price > short_pts or H1.i >= H2.i:
            continue
        if any(q.price >= H1.price for q in ph[:b] if H1.i < q.i < H2.i):
            continue
        between = [q.price for q in pl if H1.i < q.i < H2.i]
        ref = min(between) if between else float("inf")
        drop = next((q for q in pl if q.i > H2.i and q.price < ref), None)
        if drop is None:
            continue
        if h is not None and len(h) > H2.i + 1 and np.max(np.asarray(h[H2.i + 1:i + 1], float), initial=-np.inf) > H1.price:
            continue
        score = float(H2.i - H1.i) + (1.0 if any(0 <= fb - H1.price <= fvg_tol for fb in fvg_bottoms) else 0.0)
        out.append((float(H1.price), score, int(max(drop.known, H2.known)), int(H2.i)))
    return out


def nwog_redelivery(o, h, l, c, start: int, near: float, far: float, tick: float, pts: float = 1.0, end: int | None = None,
                    until_end: int | None = None):
    """Caption-gap L5-partial-redelivery (019 ~16:36: "it does not need to come back to Friday's close"): the both-way redelivery
    state machine of one NWOG over the bars from `start` (the Sunday open bar), causal - each step completes at a bar's close.
    `near` = the Sunday open (the gap edge price starts at), `far` = Friday's close. s = +1 when the far edge is above the open.
      (a) far_hit      price trades to the far edge (within a tick)
      (b) back_through then trades back through the gap to the open side (to the near edge)
      (c) ce_fail      a later return reaches the CE (within a tick), stays short of the far edge and the bar closes back out of
                       the CE
      (d) exit_fvg     the exit leg leaves a LONE FVG whose near edge (the one facing the gap) is within `pts` of the gap edge `near`
                       and the bar completing it closes outside the gap (at / beyond the near edge, within `pts`)
    Reaching the far edge again after (a)/(b)/(c) restarts at (b) (a full redelivery). Review fixes (#18): the gap must be at least
    2 x `pts` tall (below that every FVG is "at the edge" and the CE / far / near tolerances collapse); an FVG on the exit leg that
    is NOT at the gap edge makes the leg not lone (that CE failure is abandoned, the machine waits for another); `end` bounds the
    sequence in time (htf.nwog_rebalanced: the first trading week after the Sunday open [our interpretation of "the first
    session(s)"]); a LATER full redelivery to the far edge un-rebalances the gap (`until`).
    Returns None, or (bar, exit_edge, until): the bar at whose close the sequence is met, the price of the exit FVG's near edge and the
    first bar (through `until_end`) at whose close the far edge was reached again - or None."""
    n = len(c) if end is None else min(end, len(c) - 1) + 1
    s = 1 if far > near else -1
    if abs(far - near) < 2 * pts - 1e-9:
        return None
    ce = (far + near) / 2
    stage = 0
    ce_i = -1
    done = None
    for k in range(max(start, 0), n):
        hit_far = h[k] >= far - tick if s > 0 else l[k] <= far + tick
        if stage == 0:
            if hit_far:
                stage = 1
            continue
        if hit_far:
            stage = 1
            continue
        if stage == 1:
            if (l[k] <= near + tick) if s > 0 else (h[k] >= near - tick):
                stage = 2
            continue
        if stage == 2:
            reach_ce = h[k] >= ce - tick if s > 0 else l[k] <= ce + tick
            out = c[k] < ce if s > 0 else c[k] > ce
            if reach_ce and out:
                stage, ce_i = 3, k
            continue
        # stage 3: the exit leg - an FVG against the far edge formed after the CE failure
        if k >= ce_i + 2 and k >= 2 and k - 2 >= ce_i:
            if s > 0 and h[k] < l[k - 2]:
                if abs(l[k - 2] - near) <= pts and c[k] <= near + pts:
                    done = (k, float(l[k - 2]))
                    break
                stage = 2                                  # an FVG elsewhere on the leg: not a lone exit FVG
            elif s < 0 and l[k] > h[k - 2]:
                if abs(h[k - 2] - near) <= pts and c[k] >= near - pts:
                    done = (k, float(h[k - 2]))
                    break
                stage = 2
    if done is None:
        return None
    k, edge = done
    until = None
    for q in range(k + 1, (len(c) if until_end is None else min(until_end, len(c) - 1) + 1)):
        if h[q] >= far - tick if s > 0 else l[q] <= far + tick:
            until = q
            break
    return k, edge, until


def ob_anchor_state(o, h, l, c, j: int, k: int, i: int, passes: int = 2, lead: int = 3) -> str:
    """Caption-gap A12-open-vs-wick-gap-criterion + A5-twice-traded-not-fvg (cc05_015 ~11:32 / ~11:38, cc04_013 ~16:17: "there's an
    absence of a gap"), bullish terms, the order block = the down-close run [j, k]: the wick area [highest body top, highest
    high] of the run. It is "closed in" when it has been traded through at least `passes` times - the run's own candle counts as
    one pass, every other bar from `lead` bars before the run through bar i (the displacement candle right after the run excluded: it
    only leaves the area) whose range overlaps the area as another [our interpretation: 2 bars] - or when the run has no upper wick:
      "closed_in"  no FVG remains there: anchor on the BODY (level = the open, zone = the body)
      "gap"        untraded by any other bar and the displacement left an FVG above the block (low[k+2] > high[k]): the wick extreme /
                   the gap is the anchor
      "rule"       neither: the A12 stubby / long-wick rule decides
    Only closed bars up to `i` are read."""
    body_top = float(np.max(np.asarray(o[j:k + 1], float)))
    hi = float(np.max(np.asarray(h[j:k + 1], float)))
    if hi - body_top <= 1e-12:
        return "closed_in"
    others = 0
    for q in range(max(0, j - lead), min(i, len(h) - 1) + 1):
        if j <= q <= k + 1:                    # the run itself and its displacement candle (the move that LEAVES the area) are not extra passes
            continue
        if h[q] > body_top and l[q] < hi:
            others += 1
    if 1 + others >= passes:
        return "closed_in"
    if others == 0 and k + 2 <= i and l[k + 2] > h[k]:
        return "gap"
    return "rule"


def bk_state(h, l, z: Zone, i: int, depth: str = "ce", bprs=(), bpr_ce: bool = False, c=None) -> tuple:
    """Caption-gap A6-breakaway-depth-qualification (062 ~37:12 / ~39:01, 065 ~4:39:02, cc04_009 ~13:37), a BULLISH gap z (known at
    z.i), state after the closed bar `i`. candidate -> retraced (price trades into the gap, the far edge z.bottom untouched) ->
    QUALIFIED when price then trades above the highest high printed since the gap formed (up to the bar before the retrace) with the far
    edge still untouched. Only a qualified gap is a protected / trail level. dead = the far edge was touched (a full fill: not
    breakaway) - or, with depth "ce" (A6: at most 50%), a trade at / below the CE. `depth` "any_open" (062, cc04_009: any portion
    left open, then a move away). `bpr_ce` (065): when a BPR sits directly beyond the gap's far edge (a zone in `bprs` that
    overlaps the far edge or ends within a tick of it) the retrace must stay on the near side of the CE even under any_open - past it
    is a downgrade (dead). `c` (closes): the far-edge death test of a non-CE depth reads the CLOSE (a body filling the gap) instead of the wick
    (A6-measuring-gap-confirmation: only bodies filling the gap drop the label). Returns (state, bar of the last transition or -1)."""
    if depth not in ("ce", "any_open"):
        raise ValueError(f"bk_depth {depth!r}: expected 'ce' or 'any_open'")
    ce_limit = depth == "ce" or (bpr_ce and any(b.bottom <= z.bottom + 1e-9 and b.top >= z.bottom - 1e-9 for b in bprs))
    state, ev, hh0 = "candidate", -1, None
    n = min(i, len(l) - 1)
    for k in range(z.i + 1, n + 1):
        if (l[k] <= z.mid - 1e-9) if ce_limit else ((c[k] <= z.bottom + 1e-9) if c is not None else (l[k] <= z.bottom + 1e-9)):
            return "dead", k
        if state == "candidate" and l[k] <= z.top:
            state, ev = "retraced", k
            hh0 = float(np.max(np.asarray(h[z.i:k], float)))
        elif state == "retraced" and h[k] > hh0:
            state, ev = "qualified", k              # review fix: keep scanning - a qualified gap that is LATER fully filled is dead
    return state, ev


def vi_breakaway(o, h, l, c, z: Zone, cons_n: int = 6, cons_k: float = 2.5, broke: int | None = None, ext: float | None = None,
                 ext_i: int | None = None, leg_hi: float | None = None) -> str:
    """Caption-gap A9-vi-breakaway (079 ~14:20, 103 ~25:18: "the volume imbalance can act much like a breakaway gap"), a BULLISH VI z
    (z.i = its second candle): the reason it is a breakaway VI, or "". [our interpretation of the context tests]
      "consolidation"  it sits on the candles LEAVING a consolidation: the `cons_n` candles before the VI form a range no taller than
                       `cons_k` x their mean bar range, and the VI starts at or above all of their bodies
      "mss"            it is on the candle(s) right after the MSS: the structure-break bar `broke` is one of the VI's two candles
      "leg"            it lies inside the displacement leg (after the sweep extreme `ext_i`) beyond the retrace limit - the leg's 50%
                       between `ext` and `leg_hi`
    A body close through the VI weakens the bias; a later full body across it = it was not breakaway (the caller drops the tag)."""
    a = z.i - 1 - cons_n
    if a >= 0:
        w_h, w_l = np.asarray(h[a:z.i - 1], float), np.asarray(l[a:z.i - 1], float)
        mean_r = float((w_h - w_l).mean())
        top_b = float(np.max(np.maximum(np.asarray(o[a:z.i - 1], float), np.asarray(c[a:z.i - 1], float))))
        if mean_r > 0 and (w_h.max() - w_l.min()) <= cons_k * mean_r and z.bottom >= top_b - 1e-12:
            return "consolidation"
    if broke is not None and broke in (z.i - 1, z.i):
        return "mss"
    if ext is not None and ext_i is not None and leg_hi is not None and z.i - 1 > ext_i and z.bottom > ext + 0.5 * (leg_hi - ext):
        return "leg"
    return ""


def common_gaps_cc(o, h, l, c) -> list[Zone]:
    """Caption-gap A6-gap-hierarchy-common (cc04_010 ~12:25), the CC "common gap": a BODY gap with no range closing the space. Bearish:
    open[i] < close[i-1] and the whole candle i sits below that close (high[i] < close[i-1]) [our interpretation of "no range closing the
    space": the entire candle, wicks included, stays on the far side of the prior close]; zone [open[i], close[i-1]], expected to be
    closed by bodies; bullish mirror (open[i] > close[i-1], low[i] > close[i-1]). Zone.tag "cc_common"; known at candle i. (The 062
    "common gap" = an ordinary FVG is a different thing, tagged by ld3.gap_class.)"""
    out = []
    for i in range(1, len(c)):
        if o[i] < c[i - 1] and h[i] < c[i - 1]:
            out.append(Zone("bear", float(c[i - 1]), float(o[i]), i, i, tag="cc_common"))
        elif o[i] > c[i - 1] and l[i] > c[i - 1]:
            out.append(Zone("bull", float(o[i]), float(c[i - 1]), i, i, tag="cc_common"))
    return out


def single_pass_ranges(o, h, l, c, big_mult: float = 1.5, n: int = 20, lookback: int = 5) -> list[Zone]:
    """Caption-gap new-single-candle-daily-inefficiency (091 ~25:37: "only one candle went higher"): a single-pass inefficiency = a LARGE
    candle (range >= `big_mult` x the mean range of the up to `n` bars before it, at least 5) that closes up and whose range no
    other candle traded through: none of the `lookback` bars before it printed above its low [our interpretation of "no other candle"
    + "large"]. Zone = the candle's whole range, `levels` = its 0 / 25 / 50 / 75 / 100% prices (low .. high), `src` = the candle,
    known at its close (later bars only kill it: the caller retires it once a later low trades to the candle's low, "through it").
    Until then it "needs sell-side delivery": expect the CE, then the lower quadrant. Bearish mirror (a large down candle in clear
    air below): kind "bear", levels from the high down."""
    out = []
    for k in range(max(5, lookback), len(c)):
        a = max(0, k - n)
        mean_r = float((np.asarray(h[a:k], float) - np.asarray(l[a:k], float)).mean())
        if not mean_r > 0 or h[k] - l[k] < big_mult * mean_r:
            continue
        w = slice(k - lookback, k)
        if c[k] > o[k] and float(np.max(np.asarray(h[w], float))) <= l[k] + 1e-12:
            lv = tuple(float(l[k] + q * (h[k] - l[k])) for q in (0.0, 0.25, 0.5, 0.75, 1.0))
            out.append(Zone("bull", float(h[k]), float(l[k]), k, k, tag="spr", levels=lv))
        elif c[k] < o[k] and float(np.min(np.asarray(l[w], float))) >= h[k] - 1e-12:
            lv = tuple(float(h[k] - q * (h[k] - l[k])) for q in (0.0, 0.25, 0.5, 0.75, 1.0))
            out.append(Zone("bear", float(h[k]), float(l[k]), k, k, tag="spr", levels=lv))
    return out


def balanced_bodies(o, h, l, c, n: int = 3, ovl: float = 0.5, disp_mult: float = 1.5) -> list[Zone]:
    """Caption-gap A11-balanced-range-body-filled (098 ~34:57 / ~1:00:35, 099 ~11:14: "its range is balanced so a midpoint of that is
    equilibrium"): a body-filled balanced range = a run of at least `n` consecutive candles each overlapping the previous one by
    >= `ovl` of the smaller range [our interpretation], that traded both ways (candles of both colours), then LEFT by displacement: the
    next candle's body is >= `disp_mult` x the run's mean body and closes beyond all of the run's bodies. Zone = the bodies' range
    (bodies cover the zone height = equilibrium; the midpoint is `Zone.mid` and `levels` = (EQ,)), `kind` the departure direction
    ("bull" = left upward), `tag` "balanced_range", known at the departure candle's close. Kept apart from the A11 BPR (FVG
    overlap): a gap/void midpoint is a CE, a body-filled range's is an EQ. On a return price is REDELIVERED, not rebalanced:
    expect a slowdown at its edge / EQ."""
    out = []
    N = len(c)
    a = 0
    while a < N - 1:
        b = a
        dep = None
        while b + 1 < N:
            d = b + 1
            if b - a + 1 >= n:                                  # long enough: is the next candle the departure?
                seg = slice(a, b + 1)
                mean_body = float(np.abs(np.asarray(c[seg], float) - np.asarray(o[seg], float)).mean())
                top = float(np.max(np.maximum(o[seg], c[seg])))
                bot = float(np.min(np.minimum(o[seg], c[seg])))
                if mean_body > 0 and abs(c[d] - o[d]) >= disp_mult * mean_body and (c[d] > top or c[d] < bot) and top > bot:
                    dep = d
                    break
            lo_, hi_ = max(l[b], l[d]), min(h[b], h[d])
            small = min(h[b] - l[b], h[d] - l[d])
            if small > 0 and (hi_ - lo_) >= ovl * small:
                b += 1
            else:
                break
        if dep is not None:
            seg = slice(a, b + 1)
            if bool((c[seg] > o[seg]).any() and (c[seg] < o[seg]).any()):
                top = float(np.max(np.maximum(o[seg], c[seg])))
                bot = float(np.min(np.minimum(o[seg], c[seg])))
                kind = "bull" if c[dep] > top else "bear"
                out.append(Zone(kind, top, bot, dep, a, tag="balanced_range", levels=((top + bot) / 2,)))
            a = dep
        else:
            a = b + 1 if b > a else a + 1
    return out


def smooth_edge_range(o, h, l, c, tol: float, touches: int = 3, a: int = 0, b: int | None = None):
    """Caption-gap M1-original-consolidation (104 ~27:53: "a repetitive overlapping or reoccurrence of a level"), bullish example: the
    ORIGINAL consolidation's bounds over the bars [a, b]: the upper bound is a SMOOTH-EDGE level - the highest BODY top U that at least
    `touches` bars touch with their body top or their high within `tol` while no body top is above U + tol - and the lower bound is
    the range's lowest low. Returns (U, low, touches_found) or None. [our interpretation: >= 3 touches]. Bearish mirror: negate the
    arrays (the upper bound becomes the lower)."""
    b = len(c) - 1 if b is None else min(b, len(c) - 1)
    if b < a:
        return None
    tops = np.maximum(np.asarray(o[a:b + 1], float), np.asarray(c[a:b + 1], float))
    hi = np.asarray(h[a:b + 1], float)
    cand = sorted(set(float(x) for x in tops), reverse=True)           # the edge is a BODY level; the wicks only add touches
    for u in cand:
        if tops.max() > u + tol:
            continue
        n_t = int(((np.abs(tops - u) <= tol) | (np.abs(hi - u) <= tol)).sum())
        if n_t >= touches:
            return float(u), float(np.min(np.asarray(l[a:b + 1], float))), n_t
    return None


def consolidation_box(o, h, l, c, bodies: bool = True, eq_touches: int = 2) -> dict:
    """Caption-gap A21-consolidation-range-def (cc01_001 ~11:50 / ~17:54: "defined specifically by the bodies of the candles, not the
    wicks"): the consolidation range = high = the max BODY, low = the min BODY over the range candles (`bodies` False: the wicks, the
    impulse-leg rule of A21); EQ = the midpoint. ICT's check-yourself test: price touches or crosses the EQ from both sides several
    times while it stays in the range - `up` = bars that came from above and reached the EQ (low <= EQ after a close above it),
    `down` = bars that came from below and reached it; valid = both >= `eq_touches` [our interpretation: 2 each side]
    (eq_touches 0: always valid, a range with a clear high and low). Returns dict(high, low, eq, up, down, valid)."""
    oo, cc, hh, ll = (np.asarray(x, float) for x in (o, c, h, l))
    if not len(cc):
        return dict(high=float("nan"), low=float("nan"), eq=float("nan"), up=0, down=0, valid=False)
    if bodies:
        hi, lo = float(np.maximum(oo, cc).max()), float(np.minimum(oo, cc).min())
    else:
        hi, lo = float(hh.max()), float(ll.min())
    eq = (hi + lo) / 2
    up = dn = 0
    for k in range(1, len(cc)):
        if cc[k - 1] > eq and ll[k] <= eq:
            up += 1
        elif cc[k - 1] < eq and hh[k] >= eq:
            dn += 1
    return dict(high=hi, low=lo, eq=float(eq), up=up, down=dn, valid=bool(hi > lo and (eq_touches <= 0 or (up >= eq_touches and dn >= eq_touches))))


def daily_consolidations(o, h, l, c, min_bars: int = 5, height_mult: float = 1.5, eq_touches: int = 2) -> list[dict]:
    """Caption-gap B21-data-range-fv-eq (cc05_003 ~1:18:00: "that's where your equilibrium price points are"), [our interpretation] on
    daily bars: a consolidation = a run of at least `min_bars` consecutive bars whose body range (consolidation_box, bodies) is no
    taller than `height_mult` x their mean daily range and whose EQ was touched from both sides (valid box). Greedy, longest run from
    each start. Returns [dict(a, b, high, low, eq, known = b)] oldest first; the EQ of a run is known at its last bar's close."""
    out = []
    n = len(c)
    a = 0
    while a < n:
        best = None
        for b in range(a + 1, n):
            seg = slice(a, b + 1)
            box = consolidation_box(o[seg], h[seg], l[seg], c[seg], True, eq_touches)
            mean_r = float((np.asarray(h[seg], float) - np.asarray(l[seg], float)).mean())
            if not (box["high"] - box["low"] <= height_mult * mean_r):
                break
            if b - a + 1 >= min_bars and box["valid"]:
                best = (b, box)
        if best is not None:
            b, box = best
            out.append(dict(a=a, b=b, high=box["high"], low=box["low"], eq=box["eq"], known=b))
            a = b + 1
        else:
            a += 1
    return out


def leg_is_impulsive(o, h, l, c, a: int, b: int, up: bool, atr: float, impulse_frac: float = 0.6, atr_mult: float = 1.0) -> bool:
    """Caption-gap A21 (item 54) / A1-impulse-swing-unit (cc01_008 ~1:52: "you need to be thinking in terms of impulse price swings"):
    the leg between bars a and b (an up leg when `up`) is IMPULSIVE when any one of: >= `impulse_frac` of its bars close in its
    direction; an FVG of its direction lies inside it (its third candle within [a+2, b]); or its size >= `atr_mult` x ATR."""
    oo, cc, hh, ll = (np.asarray(x[a:b + 1], float) for x in (o, c, h, l))
    if len(cc) < 2:
        return False
    frac = float((cc > oo).mean() if up else (cc < oo).mean())
    size = float(hh.max() - ll.min())
    fv = any(g.kind == ("bull" if up else "bear") for g in fvgs(hh, ll))
    return bool(frac >= impulse_frac or fv or (atr > 0 and size >= atr_mult * atr))


def impulse_legs(h, l, o, c, n: int = 1, atr_n: int = 14, impulse_frac: float = 0.6, atr_mult: float = 1.0) -> list[tuple]:
    """Caption-gap A1-impulse-swing-unit (cc01_008 ~1:52): the impulse swings = the clear one-directional legs between ALTERNATING swing
    extremes (`pivots(n)`, same-type neighbours collapsed to the more extreme), kept only when impulsive (leg_is_impulsive: item 54's
    test). Returns [(i0, i1, p0, p1, up, known)] oldest first, known = the bar at which the leg's end swing is confirmed. A
    drifting, overlapping leg is excluded. A leg starts at the most extreme swing of the opposite-type run before it and ends at the
    FIRST swing of the other type [our interpretation, review fix #134: causal - the answer at a bar never changes with later bars].
    NOT wired into ote / leg_pd (they keep their own leg search, build_log #134); the active PARENT leg - item 130 - is not built.)"""
    ph, pl = pivots(h, l, n)
    seq = sorted([(q.i, q.price, 1, q.known) for q in ph] + [(q.i, q.price, -1, q.known) for q in pl])
    out = []
    run: list = []                       # the run of same-type swings just before the current one
    for m, q in enumerate(seq):
        if m and seq[m - 1][2] != q[2]:
            # q is the FIRST swing of its type after a run of the opposite type: it ends a leg that starts at the run's extreme
            # (review fix #134: the end is the first-confirmed swing, never replaced by a later, more extreme one, so the answer
            # at a bar does not depend on later bars)
            p0 = (max if q[2] < 0 else min)(run, key=lambda x: x[1])
            up = q[2] > 0
            a_ = max(0, q[0] - atr_n)
            atr = float((np.asarray(h[a_:q[0] + 1], float) - np.asarray(l[a_:q[0] + 1], float)).mean())
            if leg_is_impulsive(o, h, l, c, p0[0], q[0], up, atr, impulse_frac, atr_mult):
                out.append((p0[0], q[0], float(p0[1]), float(q[1]), up, int(q[3])))
            run = [q]
        else:
            run.append(q)
    return out


def void_round_trip_obs(o, h, l, c, min_run: int = 3) -> list[Zone]:
    """Caption-gap A12-void-up-down-ob (cc02_007 ~13:33: "this entire range is going to be viewed in the scope of a bearish order
    block"), for 4h and higher bars: a ONE-SIDED rally (a run of at least `min_run` up-close bars, each bar's low above the previous bar's
    high: a void up) followed IMMEDIATELY by a one-sided drop (down-close bars, each high below the previous low: a void down) back
    through the same range (the drop reaches the rally's first low) = ONE bearish order block: the rally's whole range, MT = its 50%
    (`Zone.mt`; `mid`). Known at the FIRST bar at which the drop is `min_run` bars long and has reached the rally's low (so the answer at a
    bar never depends on later bars). Bullish mirror (void down, then void up through it): kind "bull". [our interpretation: the strict
    no-overlap run test]. The LTF refinement (the last up candles' body range and its EQ) is not built."""
    out = []
    N = len(c)
    for sign, kind in ((1, "bear"), (-1, "bull")):
        oo, cc = np.asarray(o, float) * sign, np.asarray(c, float) * sign
        hh, ll = (np.asarray(h, float), np.asarray(l, float)) if sign > 0 else (-np.asarray(l, float), -np.asarray(h, float))
        a = 0
        while a < N:
            if not cc[a] > oo[a]:
                a += 1
                continue
            b = a                                                     # the rally: up-close bars, each low above the previous high
            while b + 1 < N and cc[b + 1] > oo[b + 1] and ll[b + 1] > hh[b]:
                b += 1
            if b - a + 1 >= min_run and b + 1 < N and cc[b + 1] < oo[b + 1]:
                d0 = b + 1
                k = d0                                                # the drop: down-close bars, each high below the previous low
                while k < N and cc[k] < oo[k] and (k == d0 or hh[k] < ll[k - 1]):
                    if k - d0 + 1 >= min_run and ll[d0:k + 1].min() <= ll[a]:
                        top, bot = float(hh[a:b + 1].max()), float(ll[a])
                        z = (top, bot) if sign > 0 else (-bot, -top)
                        out.append(Zone(kind, float(max(z)), float(min(z)), k, a, float((max(z) + min(z)) / 2), tag="void_rt"))
                        break
                    k += 1
            a = b + 1
    return sorted(out, key=lambda z: z.i)


# --- caption-gap pass, package levels_detectors #3/3 (digests/rulebook_gaps/*.md) -------------------------------------------
# Pure detectors (arrays in, objects out), bullish terms (the engine mirrors a short's prices); each reports the bar at which its
# object is known. The engine glue is in ld4.py.

def reactionary_highs(o, h, l, c, pivs, disp_mult: float = 1.5, leg_bars: int = 3, end: int | None = None) -> list[tuple]:
    """Caption-gap new-reactionary-high-liquidity (046 ~56:01; 099 ~51:16: "this is exactly where everybody's trailed stop losses are
    sitting"): a REACTIONARY high = a pivot high whose following leg is a displacement down - within `leg_bars` bars after the pivot candle
    a down-close candle whose body is at least `disp_mult` x the mean body of the (up to 10) bars before it (the A20 test), and the leg
    trades below the pivot candle's low [our interpretation]. Returns [(price, bar, known)] for every such pivot, oldest first; known = the
    later of the pivot's confirmation and the displacement bar. `end` limits the scan to bars <= end (the answer at a bar never depends on
    later bars). The caller keeps the latest UNTAKEN one (no later high at or above the price). Mirror: pass negated lows as `h`
    (and negated opens / closes)."""
    n = len(c) if end is None else min(len(c), end + 1)
    out = []
    for q in pivs:
        if q.known >= n:
            continue
        for b in range(q.i + 1, min(q.i + leg_bars, n - 1) + 1):
            if not c[b] < o[b]:
                continue
            a = max(0, b - 10)
            body = abs(c[b] - o[b])
            prev = np.abs(np.asarray(c[a:b], float) - np.asarray(o[a:b], float))
            if len(prev) and body < disp_mult * float(prev.mean()):
                continue
            if float(np.min(l[q.i + 1:b + 1])) < float(l[q.i]):
                out.append((float(q.price), int(q.i), int(max(q.known, b))))
                break
    return [r for r in out if r[2] < n]


def parent_pools(o, h, l, c, lows, n_min: int = 2, band: float = 0.0, end: int | None = None) -> list[tuple]:
    """Caption-gap new-parent-pool-bodies-short (050 ~56:39: "the parent price swing and liquidity pool is this one"): an earlier swing low
    L0 with at least `n_min` LATER swing lows in the same area (within `band` above L0) whose candle bodies all stop short of it
    (min(open, close) above L0's low) is the PARENT swing and the real sell-side pool - the later ones are intermediates (partial
    levels at most). L0 must be untaken (no later bar's low below it, through `end`). Returns [(price, bar, known)] - known = the bar
    at which the n_min-th later low is confirmed. Bullish terms; the buy-side mirror is the same call on negated highs."""
    n = len(c) if end is None else min(len(c), end + 1)
    out = []
    lows = [q for q in lows if q.known < n]
    for k, q0 in enumerate(lows):
        later = [q for q in lows[k + 1:] if q.i > q0.i and q0.price < q.price <= q0.price + band
                 and min(o[q.i], c[q.i]) > q0.price]
        if len(later) < n_min:
            continue
        known = int(sorted(q.known for q in later)[n_min - 1])
        if known >= n or (n > q0.i + 1 and float(np.min(l[q0.i + 1:n])) < q0.price):      # (review fix: untaken through `end`, not only up to `known`)
            continue
        out.append((float(q0.price), int(q0.i), known))
    return out


def trendline_highs(pivs, tol: float, l=None, last: int = 12) -> dict | None:
    """Caption-gap new-trendline-trap(-target) (cc03_007 ~8:18-11:26: "that's where a lot of the buy stops are going to be residing"): the LATEST
    three-touch down-trendline of retail's - three swing highs H1 > H2 > H3 (Pivot objects, oldest first) with the middle touch within `tol` of
    the straight line through H1 and H3 [our interpretation]. The newest H3 wins, then the newest H2, then the newest H1. Returns
    dict(h1, h2, h3 = the Pivots, l23, l23_i = the lowest low (and its bar) between H2 and H3 when the lows `l` are given, known =
    H3's confirmation bar) or None. Bullish terms; the up-trendline of lows (rising L1 < L2 < L3, H23 between L2 and L3) is the mirror:
    `trendline_touches`."""
    pv = list(pivs)[-last:]
    for c_ in range(len(pv) - 1, 1, -1):
        for b_ in range(c_ - 1, 0, -1):
            for a_ in range(b_ - 1, -1, -1):
                pa, pb, pc = pv[a_], pv[b_], pv[c_]
                if not (pa.price > pb.price > pc.price and pa.i < pb.i < pc.i):
                    continue
                line = pa.price + (pc.price - pa.price) * (pb.i - pa.i) / (pc.i - pa.i)
                if abs(pb.price - line) <= tol + 1e-9:
                    out = dict(h1=pa, h2=pb, h3=pc, known=int(pc.known))
                    if l is not None and pc.i > pb.i + 1:
                        seg = np.asarray(l[pb.i + 1:pc.i], float)
                        out["l23"] = float(seg.min())
                        out["l23_i"] = int(pb.i + 1 + int(np.argmin(seg)))
                    return out
    return None


def trendline_touches(lows, tol: float, h=None, last: int = 12) -> dict | None:
    """The mirror of `trendline_highs` for an UP-trendline: three swing lows L1 < L2 < L3 (Pivot objects) on a line within `tol`; H23 = the
    highest high between L2 and L3 when the highs `h` are given. Returns dict(l1, l2, l3, h23, h23_i, known) or None."""
    neg = [Pivot(q.i, -q.price, q.known) for q in lows]
    r = trendline_highs(neg, tol, None if h is None else -np.asarray(h, float), last)
    if r is None:
        return None
    out = dict(l1=Pivot(r["h1"].i, -r["h1"].price, r["h1"].known), l2=Pivot(r["h2"].i, -r["h2"].price, r["h2"].known),
               l3=Pivot(r["h3"].i, -r["h3"].price, r["h3"].known), known=r["known"])
    if "l23" in r:
        out["h23"], out["h23_i"] = -r["l23"], r["l23_i"]
    return out


def head_shoulders(h, l, n: int, tol: float, end: int | None = None) -> dict | None:
    """Caption-gap new-hs-fade (cc03_008 ~6:30-7:11: "i see that as a turtle soup long that took out two previous lows"): the latest
    head-and-shoulders on the bars (h, l): three consecutive swing highs S1, H, S2 with H above both shoulders, and the lows between them
    (l1 = the lowest low between S1 and H, l2 = between H and S2) relatively equal (within `tol`) - the neckline LOWS. Returns
    dict(s1, head, s2 = the Pivots, neck = min(l1, l2), neck_hi = max(l1, l2), known = S2's confirmation bar) or None. `end` limits the
    scan to bars <= end (the shape is known only when S2 is confirmed). The inverse shape (sell the neckline highs) is the same call
    on mirrored prices."""
    ph, _ = pivots(h, l, n)
    ph = [q for q in ph if end is None or q.known <= end]
    for k in range(len(ph) - 1, 1, -1):
        s1, hd, s2 = ph[k - 2], ph[k - 1], ph[k]
        if not (hd.price > s1.price and hd.price > s2.price):
            continue
        l1 = float(np.min(l[s1.i:hd.i + 1]))
        l2 = float(np.min(l[hd.i:s2.i + 1]))
        if abs(l1 - l2) <= tol + 1e-9:
            return dict(s1=s1, head=hd, s2=s2, neck=min(l1, l2), neck_hi=max(l1, l2), known=int(s2.known))
    return None


def compressed_run(pivots, adr: float, k: float, n: int, eq: float | None = None, end: int | None = None) -> list:
    """Caption-gap BH-compressed-higher-highs (028 ~1:26:02: "it's just constantly reaching for liquidity"): the latest run of at least `n`
    CONSECUTIVE pivot highs (the Pivots of `pivots`, known by bar `end`), each higher than the previous one by less than `k` x `adr` (marginal,
    compressed extensions), all of them above the dealing-range equilibrium `eq` (None = no location test). A run is as long as it stays
    compressed: a bigger jump (or a lower high) ends it and a new one starts at that pivot. Returns the pivots of the latest qualifying run
    (the whole run, newest last) or []. [our interpretation: the source gives no numbers; k = 0.1, n = 3 are Params.]"""
    if adr is None or adr <= 0:
        return []
    ps = [q for q in pivots if end is None or q.known <= end]
    best, run = [], []
    for q in ps:
        if run and 0 < q.price - run[-1].price < k * adr and (eq is None or q.price > eq):
            run.append(q)
        else:
            run = [q] if (eq is None or q.price > eq) else []
        if len(run) >= n:
            best = list(run)
    return best


def compressed_highs(h, pivots, adr: float, k: float, n: int, eq: float | None = None, end: int | None = None):
    """The bar index of the LAST high of the latest compressed run (`compressed_run`), or None. `h` (the bar highs) is only read to
    confirm each pivot's price (h[q.i]); pass None to trust the Pivot prices."""
    run = compressed_run(pivots, adr, k, n, eq, end)
    if not run:
        return None
    if h is not None and any(abs(float(h[q.i]) - q.price) > 1e-9 for q in run):
        return None
    return int(run[-1].i)


def ipda_forward(days: list, d_idx: int, size: int = 20) -> dict:
    """Caption-gap B21-open-float-forward-windows (cc05_004 ~25:15: "you look back 60 and you look forward 60"): the FORWARD intervals of
    the data range anchored at session `d_idx` of `days` ([(high, low)] of the completed sessions, oldest first). Each COMPLETED interval
    D..D+19, D+20..D+39, D+40..D+59 (all its sessions already closed) is returned as ("f20", "f40", "f60") -> (high, low); the large-fund
    pool "float" = the high / low of D-60..D+59, the REALISED part only (sessions up to the last completed one; absent when the history does
    not reach D-60). No interval is returned before it is complete, so the answer at a day never depends on later days."""
    out = {}
    n = len(days)
    for m, name in enumerate(("f20", "f40", "f60")):
        a, b = d_idx + size * m, d_idx + size * m + size - 1
        if a >= 0 and b <= n - 1:
            seg = days[a:b + 1]
            out[name] = (max(x[0] for x in seg), min(x[1] for x in seg))
    if d_idx - 60 >= 0 and d_idx <= n - 1:
        seg = days[d_idx - 60:min(d_idx + 59, n - 1) + 1]
        out["float"] = (max(x[0] for x in seg), min(x[1] for x in seg))
    return out


def ipda_markers(days: list, d_idx: int, windows=(20, 40, 60), size: int = 20) -> dict:
    """Caption-gap B21-open-float-forward-windows (cc05_004 ~25:15: "at each forward marker ... recompute the 20/40/60 look-backs ending there"): for
    every forward marker M_j = D + 20 j (j = 1..3, the anchor session D = `d_idx` of `days` = [(high, low)] of the completed sessions) that has been
    reached (M_j <= len(days): today is the marker day or later) the look-back windows of `windows` sessions ending the session BEFORE the marker.
    Returns {"m<j>w<n>": (high, low)}; windows the history cannot fill are left out. Nothing here depends on sessions after the marker."""
    out = {}
    n = len(days)
    for j in (1, 2, 3):
        m = d_idx + size * j
        if m > n:
            break
        for w in sorted(windows):
            if m - w >= 0:
                seg = days[m - w:m]
                out[f"m{j}w{w}"] = (max(x[0] for x in seg), min(x[1] for x in seg))
    return out


def ipda_sequence(wins: dict, seen: float, tick: float, exhausted20: bool = False, beyond: float | None = None) -> list[tuple]:
    """Caption-gap B21-progression-20-40-60-beyond (cc05_004 ~26:38; cc06_008 ~12:50; cc07_004 ~7:43; cc05_003 ~28:40): the IPDA buy-side draw
    sequence. `wins` = {window: high} (e.g. 20 / 40 / 60); `seen` = the highest high traded (today's so far). The near-term draw is the 20-day
    high; it rolls out to the 40-day window when the 20-day extreme is taken (`seen` at or above it) or - `exhausted20` - every PD array of the
    20-day window has been traded to; a window whose extreme equals the previous one's adds nothing and is skipped (the 60-day is next);
    when all the extremes are taken the nearest older swing `beyond` (a price above `seen`) is the draw, named "expansion". Returns
    [(level, name)] - at most one level; [] when there is none. Bullish terms."""
    seq, last = [], None
    for n_ in sorted(wins):
        v = wins[n_]
        if last is not None and abs(v - last) <= 1e-9:
            continue                                                   # the window adds nothing beyond the previous one
        seq.append((float(v), n_))
        last = v
    if exhausted20 and len(seq) > 1:
        seq = seq[1:]
    live = [(v, n_) for v, n_ in seq if not seen >= v + tick - 1e-9]
    if live:
        return [(live[0][0], f"ipda{live[0][1]}")]
    if beyond is not None and beyond > seen:
        return [(float(beyond), "expansion")]
    return []


def monthly_candles(dates: list, o, h, l, c, day, n: int = 3, first_month_full: bool = False) -> list[tuple]:
    """Caption-gap L3-monthly-ohlc-3m (cc03_004 ~1:46: "the opens the highs the close and the low of every single candle on a monthly chart"):
    the last `n` COMPLETED monthly candles (months before `day`'s month) from the daily arrays (oldest first): [((year, month), open, high,
    low, close)]. A month the history only partly covers (the history starts inside it and `first_month_full` is False) is left out."""
    keys = [(d.year, d.month) for d in dates]
    cur = (day.year, day.month)
    months = []
    for k, key in enumerate(keys):
        if key >= cur:
            break
        if not months or months[-1][0] != key:
            months.append([key, k, k])
        else:
            months[-1][2] = k
    if months and keys and not first_month_full and months[0][1] == 0:
        months = months[1:]                                            # the first month in the history may be cut off
    out = []
    for key, a, b in months[-n:]:
        out.append((key, float(o[a]), float(np.max(h[a:b + 1])), float(np.min(l[a:b + 1])), float(c[b])))
    return out


def monthly_range_frame(mc: list) -> tuple | None:
    """Caption-gap L3-monthly-ohlc-3m (cc03_004 ~2:30): frame the monthly range from the most recent DOWN-close monthly candle D and the up-close
    candle above its high U [our interpretation: the most recent up-close candle whose high exceeds D's high]. `mc` = the completed monthly candles
    [((year, month), open, high, low, close)], oldest first. Returns (D's low, U's high) or None when there is no such pair."""
    dn = [k for k, (_, o, h, l, c) in enumerate(mc) if c < o]
    if not dn:
        return None
    d = mc[dn[-1]]
    ups = [k for k, (_, o, h, l, c) in enumerate(mc) if c > o and h > d[2]]
    if not ups:
        return None
    return float(d[3]), float(mc[max(ups)][2])


def time_distortion_mask(t, releases, td_lunch: bool = True, pre_release_min: int = 15, close_min: int = 960,
                         lunch: tuple = (730, 840)) -> np.ndarray:
    """Caption-gap new-time-distortion (060 ~24:12; 100 ~42:21; 075 ~1:40:05: "it's being held for a news event ... being held for a session
    close"): True for the bars (minute of day `t`) where no swing / MSS / breaker / FVG signal is read: (b) the `pre_release_min` minutes
    before each scheduled release (`releases` = minutes of day), (c) from `close_min` (16:00) on, (d) the lunch chop `lunch` (12:10-14:00)
    when `td_lunch`. Case (a) - bodies holding inside an FVG - is `fvg_body_hold`."""
    t = np.asarray(t)
    m = t >= close_min
    for r in releases:
        m |= (t >= r - pre_release_min) & (t < r)
    if td_lunch:
        m |= (t >= lunch[0]) & (t < lunch[1])
    return m


def fvg_body_hold(o, h, l, c, bottom: float, top: float, a: int, b: int, min_bars: int = 5) -> bool:
    """Caption-gap new-time-distortion (a) (060 ~24:12: "the Wicks will go just outside that fair value Gap but that's okay"): within bars
    a..b the last `min_bars` (several bars: 5+ [our interpretation]) bodies all stay inside the gap [bottom, top] while at least one wick
    pokes outside it - the gap is held and stays valid."""
    if b - a + 1 < min_bars or b >= len(c):
        return False
    bodies_in = [(min(o[k], c[k]) >= bottom - 1e-9 and max(o[k], c[k]) <= top + 1e-9) for k in range(a, b + 1)]
    run = 0
    for ok in reversed(bodies_in):
        if not ok:
            break
        run += 1
    if run < min_bars:
        return False
    k0 = b - run + 1
    return bool((np.asarray(l[k0:b + 1]) < bottom - 1e-9).any() or (np.asarray(h[k0:b + 1]) > top + 1e-9).any())


# --- caption-gap pass, setups_models #2/7 --------------------------------------------------------------------------------------------------------

def reclaimed_obs_loose(o, h, l, c, a: int, i: int) -> list[Zone]:
    """A18-reclaimed-ob-codeable, the LOOSE definition (006 / Ep 02 ~49:57, ~55:24: "it becomes what a reclaimed order block"): a down-close candle k (bars
    a .. i) that price LEAVES (a later close above its high), RE-TRADES (a later bar whose low is back inside its range) and LEAVES AGAIN (a later close above
    its high). Zone = the candle's range, known at the second leaving close; the next return into it is the entry (one per block on its first retrace
    [our interpretation]). Bullish terms; bars after i are never read."""
    out = []
    for k in range(max(int(a), 0), int(i)):
        if not c[k] < o[k]:
            continue
        up1 = np.flatnonzero(c[k + 1:i + 1] > h[k])
        if not len(up1):
            continue
        j1 = k + 1 + int(up1[0])
        back = np.flatnonzero(l[j1 + 1:i + 1] <= h[k])
        if not len(back):
            continue
        j2 = j1 + 1 + int(back[0])
        up2 = np.flatnonzero(c[j2 + 1:i + 1] > h[k])
        if not len(up2):
            continue
        out.append(Zone("bull", float(h[k]), float(l[k]), int(j2 + 1 + up2[0]), k, float((o[k] + c[k]) / 2), tag="reclaimed_loose"))
    return out


DELIVERY_STATES = ("CONSOLIDATION", "EXPANSION", "RETRACEMENT", "REVERSAL")


def delivery_state(o, h, l, c, i: int, adr: float, consol_bars: int = 20, consol_adr: float = 0.3, disp_mult: float = 1.5) -> str:
    """new-delivery-states-machine (cc01_001 ~2:33, ~7:51; cc01_002 ~18:35; cc01_003 ~9:15): the state of the leg at closed bar i, from the bars up to i only
    (all thresholds [our interpretation]; `adr` = ADR5 in price units, 0 / None = unknown -> "").
      CONSOLIDATION - the last `consol_bars` bars' whole range is under consol_adr x ADR (a clear range)
      REVERSAL      - bar i or i-1 ran PAST the preceding `consol_bars`-bar extreme by its wick and closed back inside the old range (an old high / low run, then rejection)
      EXPANSION     - a bar within the last 3 closed beyond the preceding range, or a displacement bar (body >= disp_mult x the mean body of the 10 before) in the last 3
      RETRACEMENT   - anything else: back inside the recently created range."""
    n = int(consol_bars)
    if not adr or i < n + 2:                                                  # (the EXPANSION loop reads the n bars before bar i-2)
        return ""
    w_h, w_l = np.asarray(h[i - n + 1:i + 1]), np.asarray(l[i - n + 1:i + 1])
    if float(w_h.max() - w_l.min()) < consol_adr * adr:
        return "CONSOLIDATION"
    for j in (i, i - 1):
        ph, pl = float(np.max(h[j - n:j])), float(np.min(l[j - n:j]))
        if (h[j] > ph and c[j] <= ph) or (l[j] < pl and c[j] >= pl):
            return "REVERSAL"
    for j in (i, i - 1, i - 2):
        ph, pl = float(np.max(h[j - n:j])), float(np.min(l[j - n:j]))
        body = abs(c[j] - o[j])
        prev = np.abs(np.asarray(c[max(0, j - 10):j]) - np.asarray(o[max(0, j - 10):j]))
        if c[j] > ph or c[j] < pl or (len(prev) and body >= disp_mult * float(prev.mean()) > 0):
            return "EXPANSION"
    return "RETRACEMENT"


def stochastic_k(h, l, c, k: int = 14) -> np.ndarray:
    """Raw stochastic %K (0..100) per bar over the last k bars (NaN before k bars exist); only bars up to each index are read."""
    h, l, c = (np.asarray(x, float) for x in (h, l, c))
    out = np.full(len(c), np.nan)
    for j in range(k - 1, len(c)):
        hh, ll = h[j - k + 1:j + 1].max(), l[j - k + 1:j + 1].min()
        out[j] = 50.0 if hh == ll else 100.0 * (c[j] - ll) / (hh - ll)
    return out


def stoch_divergence(h, l, c, i: int, n: int = 2, k: int = 14) -> str:
    """new-divergence-types (cc04_013 ~2:41, ~12:15, ~13:52), bullish terms, the last two swing lows (confirmed by bar i) against the stochastic %K at them:
    "type1" = the classic divergence (price LOWER low, momentum HIGHER low), "type2" = the hidden one (price HIGHER low, momentum LOWER low = continuation),
    "" = neither. Confirmation only, never a trigger. Bearish = mirrored arrays."""
    ph, pl = pivots(np.asarray(h, float), np.asarray(l, float), n)
    lows = [q for q in pl if q.known <= i]
    if len(lows) < 2:
        return ""
    st = stochastic_k(h[:i + 1], l[:i + 1], c[:i + 1], k)
    a, b = lows[-2], lows[-1]
    sa, sb = st[a.i], st[b.i]
    if sa != sa or sb != sb:
        return ""
    if b.price < a.price and sb > sa:
        return "type1"
    if b.price > a.price and sb < sa:
        return "type2"
    return ""


# --- caption-gap new-swing-grades (cc07_003 ~17:26): the four grades of a swing --------------------------------------------------------------------

def swing_grades(o_px: float, t_px: float) -> dict:
    """Caption-gap new-swing-grades (cc07_003 ~17:26: "the fourth is Terminus"): the four levels of a swing from its origin O to its terminus T
    {1: the first retracement entry, 2: EQ, 3: O + 0.75 (T - O), 4: T (the final profit)}. [our interpretation] grade 1 = O + 0.25 (T - O): the
    first of the quarter steps along the swing (the source does not give its depth); a bullish swing has O < T, a bearish one O > T (the
    formulas hold either way). At grade 3 no stop run is expected - only a short pullback (a smaller order block), still tradable."""
    r = t_px - o_px
    return {1: o_px + 0.25 * r, 2: o_px + 0.5 * r, 3: o_px + 0.75 * r, 4: t_px}


def swing_grade_of(px: float, o_px: float, t_px: float) -> int:
    """The grade (1-4) of a price in the swing O..T: the nearest of `swing_grades` (ties to the lower grade); 0 when O == T."""
    r = t_px - o_px
    if not r:
        return 0
    g = swing_grades(o_px, t_px)
    return min(g, key=lambda k: (abs(g[k] - px), k))


# --- caption-gap pass, targets_partials #2/4 -------------------------------------------------------------------------------------------------------

def consolidation_band(h, l, i: int, n: int, max_w: float):
    """L5-old-nwog-in-consolidation (044 ~01:18:34; 051 ~00:17:37) [our interpretation]: a consolidation = the last `n` bars (ending at the closed bar i) overlap
    inside one band no wider than `max_w`. Returns (low, high) of the band or None."""
    if n < 2 or i + 1 < n:
        return None
    lo, hi = float(np.min(l[i + 1 - n:i + 1])), float(np.max(h[i + 1 - n:i + 1]))
    return (lo, hi) if hi - lo <= max_w + 1e-12 else None


def long_wick_ces(o, h, l, c, upper: bool = True, min_ratio: float = 1.0, n_med: int = 20):
    """L10-intraday-wick-ce (062 ~00:25:01; 058 ~00:17:40) [our interpretation]: the CEs (body edge + half the wick) of the LONG wicks of completed candles - wick >= min_ratio x
    body and >= the median wick of the last `n_med` candles up to and including it. `upper` = the upper wicks (premium arrays above), else the lower ones.
    Returns [(index, ce, wick length)] in bar order."""
    o, h, l, c = (np.asarray(x, float) for x in (o, h, l, c))
    top, bot = np.maximum(o, c), np.minimum(o, c)
    w = (h - top) if upper else (bot - l)
    out = []
    for k in range(len(c)):
        seg = w[max(0, k + 1 - n_med):k + 1]
        if w[k] > 0 and w[k] >= min_ratio * (top[k] - bot[k]) and w[k] >= float(np.median(seg)):
            out.append((k, float((top[k] + h[k]) / 2 if upper else (bot[k] + l[k]) / 2), float(w[k])))
    return out
