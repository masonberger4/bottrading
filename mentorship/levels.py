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


def immediate_rebalances(o, h, l, c, tick: float) -> list[tuple[int, str]]:
    """A7 immediate rebalance (048 ~39:02; 060 ~7:20; 092 ~1:41:14) [our interpretation of the bar
    test, the same as sb_model.immediate_rebalance]: an up-close displacement candle k-1 whose NEXT
    candle k trades straight back to the high of the candle before it, h[k-2], within one tick and
    leaves no gap (an FVG is the deferred rebalance) -> (k, "bull"); bearish mirror (down-close
    k-1, h[k] back up to l[k-2]) -> (k, "bear"). Known at candle k's close."""
    out = []
    for k in range(2, len(c)):
        if c[k - 1] > o[k - 1] and abs(l[k] - h[k - 2]) <= tick and l[k] <= h[k - 2] + 1e-12:
            out.append((k, "bull"))
        elif c[k - 1] < o[k - 1] and abs(h[k] - l[k - 2]) <= tick and h[k] >= l[k - 2] - 1e-12:
            out.append((k, "bear"))
    return out


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
                      skip_encap: bool = False, htf_zone: tuple | None = None) -> Zone | None:
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
    it] is skipped - the previous candle is the last candle of the block."""
    if pick not in OB_PICKS:
        raise ValueError(f"ob pick {pick!r}: expected one of {OB_PICKS}")
    down = (lambda k: c[k] < o[k]) if kind == "bull" else (lambda k: c[k] > o[k])
    body = lambda k: (min(o[k], c[k]), max(o[k], c[k]))
    start = max(start, 0)
    for k in range(min(end, len(o) - 1), start - 1, -1):
        if down(k):
            while skip_encap and k - 1 >= start and down(k - 1):
                (bl, bh), (pl_, ph_) = body(k), body(k - 1)
                if bl >= pl_ and bh <= ph_ and (bh - bl) <= 0.5 * (ph_ - pl_):
                    k -= 1
                else:
                    break
            j = k
            while j - 1 >= start and down(j - 1):
                j -= 1
            if pick == "blend":
                hi, lo = float(max(h[j:k + 1])), float(min(l[j:k + 1]))
                if kind == "bull":
                    mt = (max(o[j:k + 1]) + min(c[j:k + 1])) / 2
                else:
                    mt = (min(o[j:k + 1]) + max(c[j:k + 1])) / 2
                return Zone(kind, hi, lo, end, j, float(mt))
            run = list(range(j, k + 1))
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


def equal_clusters(prices, tol: float) -> list[list[int]]:
    """A3: the clusters of equal_levels (>= 2 prices within `tol` of the cluster's lowest price),
    as lists of indices into `prices`, each ascending by price."""
    order = sorted(range(len(prices)), key=lambda k: prices[k])
    out, k = [], 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and prices[order[j + 1]] - prices[order[k]] <= tol:
            j += 1
        if j > k:
            out.append(order[k:j + 1])
        k = j + 1
    return out


def equal_levels(prices, tol: float) -> list[float]:
    """Relative equal highs (or lows): clusters of >= 2 swing prices within `tol` of each
    other. Returns the extreme of each cluster (max for highs; pass negated lows)."""
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


def mitigation_blocks(o, h, l, c, n: int = 1, legacy: bool = False, with_mt: bool = False) -> list[Zone]:
    """Bullish mitigation block (A15; 033 ~1:03:50, the mirror of cc04_004 ~2:42-14:35): swing low
    A, then swing high X, then a HIGHER swing low B (no stop run below A: the breaker's failure-swing
    twin), then a body close above X; the zone is the last up-close candle at X (the failed high).
    Bearish mirrors it (high A, low X, lower high B, close below X). Known at the closing break.
    Review fix (rule_coverage A15): the old code took two lows AFTER X and never checked the A low
    before X; `legacy=True` keeps the old order.
    Caption-gap A12 (`with_mt` = Params.mit_mt_invalid; 021 ~21:06: "whether it be a breaker mitigation block or just a standard order
    block"): each zone also carries its MT - the block candle's body mean ((open + close) / 2, per D4) - in `Zone.mt`; a CE is
    `Zone.mid` on every gap and void already."""
    ph, pl = pivots(h, l, n)
    out, used = [], set()
    for i in range(len(c)):
        for kind, hs, ls, sign in (("bull", ph, pl, 1), ("bear", pl, ph, -1)):
            hk = [p for p in hs if p.known <= i]
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


def three_drives(lows: list, ext: float, ext_i: int, i: int, min_i: int = 0) -> bool:
    """M2.7 three drives ("three Indians", 093 ~10:37; 074 ~32:49) [our interpretation of the bar
    test]: the last two confirmed swing lows (Pivot list `lows`, known by bar i, before the sweep
    extreme ext_i, at or after bar min_i) and the extreme are three successively LOWER lows, and
    the pushes fail - the third drive extends below the second by less than the second extended
    below the first. Bullish: drives down into the swept level."""
    pl = [q for q in lows if min_i <= q.i < ext_i and q.known <= i]
    if len(pl) < 2:
        return False
    a, b = pl[-2], pl[-1]
    if not (a.price > b.price > ext):
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


def failure_swing(highs: list, lows: list, level: float, max_above: float, i: int,
                  min_i: int = 0) -> tuple | None:
    """M4.5 failure swing (cc05_005) [CC], bullish terms: the last confirmed swing low B (known by
    bar i, at or after min_i) sits above the key level `level` by at most `max_above` - it failed
    to reach it - and the swing high H before B is the breaking point. Returns (B, H) or None."""
    pl = [q for q in lows if q.i >= min_i and q.known <= i]
    if not pl:
        return None
    B = pl[-1]
    if not (level < B.price <= level + max_above):
        return None
    hs = [q for q in highs if q.i < B.i and q.known <= i]
    if not hs:
        return None
    return B, hs[-1]


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
                  impulse_frac: float = 0.6, atr_mult: float = 1.0, close_tol_atr: float = 0.25, lookback: int = 600):
    """Caption-gap A21 / M13 dealing range anchor (028 ~1:07:33, 044 ~40:26, cc01_005 ~2:20/~9:40/~19:23, cc04_002 ~18:44:
    "obvious price swings are the ones we look at"), bullish terms, closed bars up to `i`. Among the candidate swing
    lows (3-candle pivots, confirmed by bar i) pick the most recent one FOLLOWED BY DISPLACEMENT - consecutive
    same-direction candles leaving >= 1 bullish FVG within `n_disp` bars of the low - whose leg (the low to the highest
    high after it) is IMPULSIVE [our thresholds]: >= `impulse_frac` of its bars close up, or a displacement FVG, or a
    size >= `atr_mult` x ATR(`atr_n`) (a leg that passes none of the three is not a candidate). If the two latest
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
        if not disp:
            continue
        seg = slice(q.i, hk + 1)
        frac = float((cc[seg] > oo[seg]).mean())
        big = (hh[hk] - q.price) >= atr_mult * atr
        if frac >= impulse_frac or big or bool(disp):
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
               n_days: int = 5) -> str:
    """Caption-gap L8 (cc04_009 ~00:02:48: "this could potentially be an exhaustion gap"): validity of a vacuum block
    (a gap between two sessions' prices). `kind` "bull" = the gap opens UP (the open `near` above the last close
    `far`), "bear" = down. `closes` = the prior daily closes (oldest first, at least `n_days` + 1); `highs` / `lows` =
    the prior 20 daily highs / lows (the 20-day range, EQ = its midpoint).
      "exhaustion"   a gap up after `n_days` consecutive up-close days (each close above the one before) or a last close
                     above the 20-day high: tagged exhaustion and NOT used (bearish mirror: gap down after down days or
                     below the 20-day low)
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
    last = closes[-1] if closes else None
    if kind == "bull":
        if ups or (hi20 is not None and last is not None and last > hi20):
            return "exhaustion"
        if want is not None and want != 1:
            return "invalid"
        if hi20 is not None and lo20 is not None and not min(near, far) < (hi20 + lo20) / 2:
            return "invalid"
        return "valid"
    if dns or (lo20 is not None and last is not None and last < lo20):
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
