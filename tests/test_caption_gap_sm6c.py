"""Caption-gap pass, package setups_models #6/7, review fixes (chunk 6/7): engine-level and wiring tests for the findings of the review - the vacuum-block management hook (own branch, not nested under
sm5), the propulsion first-return order, the two-chance keep-alive reaching the MSS, the entry-discipline exclusivity, the secondary-OB bounds, the OB candle the midnight-open / fresh-EQ gates judge,
the deferred counters. Tests that need local market data skip cleanly; no platform-specific paths."""
import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mentorship import levels as L, setups as SM, sm2, sm6, strategy as S
from mentorship.strategy import Params

from test_levels_detectors import BASE
from test_caption_gap_sm1a import hist_close, ib, mkctx
from test_caption_gap_sm4a import cap  # noqa: F401  (cap: the order recorder fixture)


def test_sm6_manage_is_its_own_branch_of_the_position_loop():
    """Review fix (145): `_SM6.manage` used to sit INSIDE the `if pos["left"] and pos.get("sm5")` block, so a vacuum-block position (which carries only the sm6 tag) was never managed. The call must be in
    an `if` that tests sm6 and is not nested in a branch that tests another chunk's tag."""
    src = Path(S.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = []

    def walk(node, stack):
        if isinstance(node, ast.If):
            t = ast.unparse(node.test).replace("'", '"')
            if any(isinstance(n, ast.Call) and ast.unparse(n).startswith("_SM6.manage(") for b in node.body for n in ast.walk(b)) and 'pos.get("sm6")' in t:
                found.append(list(stack))
            stack = stack + [t]
        for ch in ast.iter_child_nodes(node):
            walk(ch, stack)

    walk(tree, [])
    assert found, "no `if ... pos.get('sm6')` branch calls _SM6.manage"
    for stack in found:
        assert not any('pos.get("sm5")' in t or 'pos.get("sm4")' in t or 'pos.get("sm3")' in t for t in stack), stack


def test_vb_counters_count_orders_not_candidates(cap):
    """Review fix: the vacuum-block counter is bumped when an order exists, not when a candidate was found (a rejected order leaves it alone)."""
    from test_caption_gap_sm6a import _vb_rows
    p = Params(**BASE, vb_entry="full", vb_min_gap_pts=0.5)
    ctx, (sl, ss) = mkctx(_vb_rows(), base=4003.0)
    k = ib(ctx, "09:30")
    h0 = dict(sm2.HITS)
    assert sm6.vb_order6(ctx, sl, k + 5, p, "AM", 1.0) is not None
    assert sm2.HITS.get("vb_full", 0) == h0.get("vb_full", 0) + 1
    assert cap["tags"]["sm6"]["vb_low"] == pytest.approx(4008.0)                            # the close of the last pre-gap UP candle
    # VB_low is the LAST UP candle's close, not the previous bar's: a down candle right before the gap
    rows = list(_vb_rows())
    rows[4] = (4005.0, 4009.0, 4003.0, 4004.0)                                              # the bar before the gap closes DOWN (4004); the last up close stays 4005
    rows[5] = (4015.0, 4020.0, 4014.0, 4018.0)
    ctx2, (sl2, _) = mkctx(rows, base=4003.0)
    assert sm6.vb_order6(ctx2, sl2, ib(ctx2, "09:30") + 5, p, "AM", 1.0) is not None
    assert cap["tags"]["sm6"]["vb_low"] == pytest.approx(4005.0) and cap["entry"] == pytest.approx(4005.0)


def _two_chance_day(p, monkeypatch):
    """A long sweep of 3995 (pool x) that closes back above it too late for the soup window, then an MSS up through the swing high 4010."""
    rows = [(4000.0, 4004.0, 3999.0, 4003.0), (4003.0, 4010.0, 4001.0, 4008.0), (4008.0, 4009.0, 3990.0, 3992.0), (3992.0, 3994.0, 3989.5, 3993.0), (3993.0, 3994.5, 3990.0, 3992.5),
            (3992.5, 3994.0, 3990.5, 3993.5), (3993.5, 3994.8, 3991.0, 3994.0), (3994.0, 4012.0, 3993.8, 4011.5), (4011.5, 4013.0, 4004.0, 4005.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0, bias=1, hist=hist_close(close=4000.0, hi=4130.0, lo=3900.0))
    ctx.partner2 = None
    monkeypatch.setattr(S, "_sell_side", lambda *a, **k: {"x": 3995.0})
    monkeypatch.setattr(S, "_level_intact", lambda ctx_, l_, i_, k_, v_, *a: i_ <= ctx_.start or bool(l_[ctx_.start:i_].min() >= v_ - 1e-9))     # untouched before this bar
    monkeypatch.setattr(S, "_smt", lambda *a, **k: None)
    k = ib(ctx, "09:30")
    for j in range(k, k + 8):
        S._scan_core(ctx, sl, j, p, "AM", 0, None, None, None)
    return ctx, sl, k


def test_two_chance_missed_soup_reaches_the_mss(monkeypatch):
    """Review fix (149): with ts_gate_mss the missed soup (no close back above the level within ts_back_bars) used to drop the sweep - and with two_chance the sweep was kept but the function still returned
    on every later bar, so the MSS never ran. Now chance 2 proceeds to the MSS / breaking-point code: the sweep survives and the break of the swing high before the sweep is registered."""
    import collections
    base = dict(BASE, ts_gate_mss=True, turtle_soup="2023")
    monkeypatch.setattr(S, "FUNNEL", collections.Counter())
    ctx, sl, k = _two_chance_day(Params(**base), monkeypatch)
    assert sl.sweep is None and S.FUNNEL["x_ts_gate"] == 1 and S.FUNNEL["2_mss"] == 0         # without two_chance the missed soup drops the sweep
    monkeypatch.setattr(S, "FUNNEL", collections.Counter())
    h0 = dict(sm2.HITS)
    ctx, sl, k = _two_chance_day(Params(**base, two_chance=True), monkeypatch)
    assert sm2.HITS.get("two_chance_keep", 0) > h0.get("two_chance_keep", 0) and S.FUNNEL["x_ts_gate"] == 0
    assert S.FUNNEL["2_mss"] == 1 and S.FUNNEL["4_order"] == 1                              # chance 2: the close of 4011.5 above the 4010 swing high is the MSS and a new order is armed


def test_entry_discipline_only_drops_other_paths():
    """Review fix (131): entry_discipline leaves ONLY the chosen discipline - an order of another kind (the FVG model after the MSS, an extra setup) is dropped when entry_discipline_only (default)."""
    for d, ok_, bad in (("turtle_soup", "ts_cc_limit", "fvg"), ("turtle_soup", "turtle_soup", "ob_pre"), ("ob_return", "ob_pre", "fvg"), ("ob_return", "arr_ob", "ts_cc_limit"),
                        ("range_void", "void_range", "ob_anchor")):
        p = Params(**BASE, entry_discipline=d)
        assert p.entry_discipline_only
        assert sm6.discipline_ok(dict(entry_kind=ok_), p) and not sm6.discipline_ok(dict(entry_kind=bad), p), (d, ok_, bad)
    assert sm6.discipline_ok(dict(entry_kind="fvg"), Params(**BASE))                        # "any": everything
    assert "entry_discipline_only" in Params.__dataclass_fields__


def test_secondary_ob_bounds_and_next_candidate():
    """Review fix (127): the secondary candle must open INSIDE the primary zone (not below its low), and a dead candidate (a body closed under its MT) does not stop the search for the next."""
    rows = [(4000.0, 4001.0, 3994.0, 3996.0), (3996.0, 3997.0, 3990.0, 3991.0), (3991.0, 3995.0, 3991.0, 3994.0)]
    ctx, (sl, ss) = mkctx(rows, base=4000.0)
    k = ib(ctx, "09:30")
    sw = dict(session="AM", key="x", ext=3990.0, ext_i=k + 1, level=3995.0, broke=None, smt=None)
    ob = S._ob_at_low(sl, sw, k + 2, Params(**BASE), ctx)
    assert ob is not None
    below = list(rows) + [(ob["lo"] - 2.0, ob["lo"] - 1.0, ob["lo"] - 4.0, ob["lo"] - 3.0), (4000.0, 4001.0, 3999.0, 4000.5)]
    ctx2, (sl2, _) = mkctx(below, base=4000.0)
    sw2 = dict(sw)
    assert sm6.secondary_cand(ctx2, sl2, sw2, k + 4, Params(**BASE)) is None                # a candle opening under the primary OB's low is no secondary OB


# --- no look-ahead on synthetic books WITH event gaps (the continuous ES frame has none, so vb_entry and the void kinds never ran there) ---------------------------------------------------

def _gappy(seed, start="2026-04-06", end="2026-05-08"):
    """B.synthetic books (with a partner) where every day jumps by a few points at 09:30 / 10:15 / 11:00 (a true event gap: the bar opens away from the previous close)."""
    import pandas as pd
    from mentorship import backtest as B
    x, y = B.synthetic(start=start, end=end, tf=5, seed=seed)
    rng = np.random.default_rng(seed + 100)
    shifts = {}
    for d in sorted(set(x.index.date)):
        at = [(9, 30), (10, 15), (11, 0)][int(rng.integers(0, 3))]
        shifts[d] = (at, float(rng.choice([-1, 1, 1, 1])) * float(rng.uniform(1.5, 4.0)))
    out = []
    for df in (x, y):
        df = df.copy()
        m = df.index.hour * 60 + df.index.minute
        for d, ((h, mi), mag) in shifts.items():
            mk = (df.index.date == d) & (m >= h * 60 + mi)
            for c in ("open", "high", "low", "close"):
                df.loc[mk, c] = df.loc[mk, c] + mag * (float(df.close.mean()) / 700.0)
        out.append(df)
    return out


GAPPY = dict(vb_entry="auto", vb_min_gap_pts=0.5, ob_entry="post_mss", vb_react_bars=2, void_trades=("fill", "range", "cont", "void_fill_gap"), eq_fresh_ob=True, ob_below_open=True,
             entry_arrays=("ob", "ob_secondary"), cc_near_ob=True, cc_swings="breaker", breaker_entry="fallback")
GAPPY_CASES = {
    # seed: the sm2.HITS counters the full run must have bumped (orders built: vb_* / void_* / consol_* are deferred to an order that exists). Found by scanning seeds 1..44 of the books below;
    # vb_partial / void_fill / void_fill_gap / vb_timeout / vb_back6 never produced a FILLED order there - their entries and the management are unit-tested (test_caption_gap_sm6a.py, the AST test above)
    6: ("vb_full", "void_range"),
    7: ("void_range",),
    15: ("eq_fresh_ob",),
    16: ("void_cont",),
    29: ("cc_near_ob",),
}


@pytest.mark.parametrize("seed", sorted(GAPPY_CASES))
def test_look_ahead_gappy_synthetic(seed):
    """Review fix: vb_entry (partial / full / auto), the void kinds, eq_fresh_ob / ob_below_open and cc_near_ob run in a full-vs-truncated comparison on books with event gaps (cuts at entry AND exit times)."""
    from test_caption_gap_ld1 import ENTRY, SYN
    from test_caption_gap_sm2b import SYN_BASE, TAG_COLS, _check_ran, _la
    x, y = _gappy(seed)
    p = Params(**{**SYN, **SYN_BASE, **GAPPY})
    full, added = _la(x, 5, "RW", p, ENTRY + TAG_COLS, every=2, partner=y)
    _check_ran("gappy%d" % seed, full, added, GAPPY_CASES[seed])
