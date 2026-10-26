"""Caption-gap pass (digests/rulebook_gaps/*.md), package entries_stops_sizing, chunk 3 of 3: the engine glue of its 34 specs - stops_sizing_scaling_in.md items 11, 12, 13, 14, 15, 17, 18, 19, 23, 25, 26, 27,
29, 30, 31, 32, 33, 36, 37, 40, 44, 45, 48, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62.

Same conventions as es1.py / es2.py: side space (shorts run mirrored prices), a bar is used only after it closes (`i` = the last CLOSED bar, an order armed on it fills from bar i+1), an object only from the bar
that completes it. Every function sits behind a Params switch of the "caption-gap pass, entries_stops_sizing #3/3" block; interpretations the sources do not pin down are marked [our interpretation]. `HITS`
is sm2's counter dict (tests: proof that a switch's code path RAN).

Sections: 1 validation - 2 sizing (alloc / leverage / fixed units / daily loss / exposure / risk multipliers / trader mode) - 3 adds (E12 / X8) - 4 stops (E6 / M2 / A12) - 5 position hooks (fill, exits, probe).
"""
from __future__ import annotations

import warnings
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pandas as pd

from . import levels as L
from . import sm2

HITS = sm2.HITS
hit = sm2.hit
MIN1 = 1e-9

CLASSES = ("scalp", "day", "swing", "position")


def _S():
    from . import strategy as S
    return S


# --- 1. validation -----------------------------------------------------------------------------------------------------------------------------------

def check_params(p) -> None:
    """Validation (and the two aliases) of the chunk's Params (strategy.Params.__post_init__)."""
    for name, ok in (("stop_gap_edge", ("", "own", "all")), ("bpr75_ref", ("upper", "lower")), ("trader_mode", ("", "new", "experienced")), ("ob_stop_kind", ("", "body", "wick")),
                     ("ob_anchor", ("highest_open", "last_open")), ("prop_stop", ("", "mt"))):
        if getattr(p, name) not in ok:
            raise ValueError(f"{name} {getattr(p, name)!r}: expected one of {ok}")
    bad = set(p.class_risk) - set(CLASSES)
    if bad or any(not 0 < float(v) <= 1 for v in p.class_risk.values()):
        raise ValueError(f"class_risk {p.class_risk!r}: keys from {CLASSES}, risk fractions in (0, 1]")
    if p.class_risk and set(p.class_risk) & {"swing", "position"}:
        warnings.warn("class_risk keys 'swing' / 'position' have no consumer yet (only 'scalp' / 'day' act in the engine; es3.class_risk_pct is for the daily study engines)", RuntimeWarning, stacklevel=2)
    if (not 0 < p.add_dig_mult <= 1 or p.add_mom_r <= 0 or not 0 < p.add_mom_frac <= 1 or p.add_wick_tf < 1 or p.mohawk_add_ticks < 0 or not 0 <= p.daily_loss_pct < 1
            or not 0 <= p.max_exposure_pct < 1 or p.alloc_frac <= 0 or p.htf_near_risk_pct < 0 or p.htf_near_pts < 0 or p.htf_near_cap_pct < 0 or p.max_lev < 0 or p.stop_fixed_pts < 0
            or p.fixed_units < 0 or p.t1_fixed_r < 0 or p.grad_block < 1 or p.grad_max < 1 or p.deep_run_mult <= 0 or p.deep_run_weeks < 1 or p.freq_ref < 0 or p.freq_recent < 0
            or not 0 <= p.probe_mult <= 1 or not 570 <= p.probe_t <= 960 or not 0 < p.probe_cut <= 1 or p.wick_ce_tol_ticks < 0 or p.mt_pad_ticks < 0 or p.three_pd_n < 1
            or p.new_max_risk_pts <= 0 or p.tight_stop_pts < 0):
        raise ValueError("entries_stops_sizing #3/3: add_dig_mult, add_mom_frac, probe_cut in (0, 1]; add_mom_r, alloc_frac, deep_run_mult, new_max_risk_pts > 0; add_wick_tf, grad_block, grad_max, deep_run_weeks, "
                         "three_pd_n >= 1; daily_loss_pct, max_exposure_pct in [0, 1); probe_mult in [0, 1]; probe_t in 570..960; the other sizes / ticks / points >= 0")
    if p.trader_mode == "new":
        if p.fixed_units == 0:
            p.fixed_units = 1                             # E8-new-trader-graduation: 1 contract (backtest.run raises it with the track record)
        p.max_risk_pts = p.new_max_risk_pts               # E6-new-trader-wide-stops: wider stops at micro size
    if p.mit_entries and "mitigation" not in p.entry_arrays:
        p.entry_arrays = tuple(p.entry_arrays) + ("mitigation",)       # E6-mitigation-block-stop: the built mitigation entry array, with the candle-extreme stop


# --- 2. sizing --------------------------------------------------------------------------------------------------------------------------------------

def class_risk_pct(p, cls: str, default: float) -> float:
    """E8-risk-by-trade-class: the per-unit risk of a trade class ("scalp" / "day" / "swing" / "position"); the study engines for swing / position trades (daily bars) read their risk here, `default` when the
    class is not configured (0.015 swing, 0.01 position in the spec)."""
    return float(p.class_risk.get(cls, default))


def per_contract(p) -> int:
    return max(p.units_per_contract or p.lot, 1)


def fixed_first_units(p) -> int:
    """E8-new-trader-drill (042 ~00:32:11): the first unit is exactly `fixed_units` contracts, whatever the equity / risk percent."""
    return int(p.fixed_units) * per_contract(p)


def notional_cap(p, eq: float) -> float:
    """E8-leverage-cap-3x (cc06_006 ~00:15:32): min(max_notional, max_lev x equity)."""
    if p.max_lev > 0 and eq:
        hit("max_lev")
        return min(p.max_notional, p.max_lev * eq)
    return p.max_notional


def lev_room_units(p, eq: float, held: float, px: float) -> float | None:
    """The units an add may still hold under the leverage cap (None = no cap)."""
    if p.max_lev <= 0 or not eq or px <= 0:
        return None
    return max(0.0, p.max_lev * eq / px - held)


def trader_units(nets, p) -> int:
    """E8-new-trader-graduation (042 ~00:21:02; 048 ~02:26:37) [our interpretation]: start at 1 contract; after each COMPLETE block of `grad_block` closed trades whose net P&L is positive, +1 (up to
    `grad_max`); a losing block keeps the size."""
    units = 1
    nets = list(nets)
    for b in range(len(nets) // p.grad_block):
        if sum(nets[b * p.grad_block:(b + 1) * p.grad_block]) > 0:
            units = min(units + 1, p.grad_max)
    return units


def day_params(p, rows: list, recent_dates: set):
    """backtest.run: the day's Params with the runtime inputs of this chunk - trader_mode 'new' (fixed_units from the track record so far), freq_ref (trades of the last 5 sessions)."""
    q = p
    if p.trader_mode == "new":
        q = replace(q, fixed_units=trader_units([r["net"] for r in rows], p))
        hit("trader_mode_new")
    if p.freq_ref > 0:
        q = replace(q, freq_recent=sum(1 for r in rows if r["date"] in recent_dates))
    return q


def deploy_gate(trades, months_min: float = 6.0, share_min: float = 0.70) -> dict:
    """E8-new-trader-graduation (048 ~02:26:37): the paper / demo deployment gate as a REPORT: months of history at 1 micro and the share of non-negative weeks (the "70 % consistent" reading [our
    interpretation]); passed at >= 6 months and >= 70 %. `trades` = a backtest book (columns date, net)."""
    if trades is None or not len(trades):
        return dict(months=0.0, weeks=0, nonneg_share=0.0, passed=False)
    d = pd.DatetimeIndex(pd.to_datetime(trades["date"]).values)
    months = (d.max() - d.min()).days / 30.4375
    wk = pd.Series(trades["net"].values, index=d).groupby(d.to_period("W-FRI")).sum()
    share = float((wk >= 0).mean())
    return dict(months=round(months, 2), weeks=int(len(wk)), nonneg_share=round(share, 3), passed=bool(months >= months_min and share >= share_min))


def deep_run_column(wh, wl, wc, wlast, ks, n: int) -> list:
    """E9-deep-discount-reduced (099 ~00:28:59), htf.table column `deep_run` (bias_htf.add_columns): per day (session index k in `ks`) over the weeks completed before it (`wlast` = the session index of each
    week's last session): +1 = a deep PREMIUM - n straight higher weekly closes with the latest close in the top quarter of the last-13-week range; -1 = deep DISCOUNT (n lower closes, bottom quarter);
    0 otherwise. Fewer than 13 weeks: the range of those available [our interpretation of "3-4 weeks of steady one-direction"]."""
    vals = []
    for k in ks:
        done = np.flatnonzero(np.asarray(wlast) < k)
        if len(done) < n + 1:
            vals.append(0)
            continue
        seg = wc[done][-(n + 1):]
        rg = done[-13:]
        hh, ll = wh[rg].max(), wl[rg].min()
        pos_ = (wc[done[-1]] - ll) / (hh - ll) if hh > ll else 0.5
        vals.append(-1 if (np.all(np.diff(seg) < 0) and pos_ <= 0.25) else 1 if (np.all(np.diff(seg) > 0) and pos_ >= 0.75) else 0)
    return vals


def exposure_filter(t, cap: float):
    """E11-portfolio-exposure-cap (cc05_013 ~00:26:39; cc06_002 ~00:12:27): walk the trades in entry order with a running open-risk total (the ENTRY risk of each trade - adds filled later are not counted -, released at its exit time) and
    drop the one whose risk would push the total over `cap` (never exceed the cap to take a setup; no swap - the bot only skips [our interpretation]). Dropped rows are kept in `attrs["x_exposure"]`.
    Review fix (look-ahead): the decision at the new entry uses ENTRY risk only - the new trade's entry_risk_pct, and for the earlier open trades their entry_risk_pct (adds filled after the decision are
    not known then; the peak column is never read)."""
    if cap <= 0 or t is None or not len(t) or "entry_time" not in t.columns:
        return t
    col = "entry_risk_pct" if "entry_risk_pct" in t.columns else "peak_risk_pct"
    open_: list = []
    drop = []
    for idx, r in t.sort_values("entry_time", kind="stable").iterrows():
        et = r["entry_time"]
        open_ = [(x, rk) for x, rk in open_ if pd.isna(x) or x > et]
        rk = r.get(col)
        rk = 0.0 if rk is None or pd.isna(rk) else float(rk)
        if rk > 0 and sum(v for _, v in open_) + rk > cap + 1e-12:
            drop.append(idx)
            continue
        open_.append((r.get("exit_time"), rk))
    if not drop:
        return t
    hit("exposure_drop")
    out = t.drop(index=drop)
    out.attrs = dict(t.attrs)
    out.attrs["x_exposure"] = t.loc[drop]
    return out


def mark_net(tr, pos, sd, i: int, ts, p) -> float:
    """The trade's net P&L if everything left were closed at bar i's close (partials taken so far included)."""
    t2 = replace(tr, exits=list(tr.exits) + [(ts, sd.x(float(sd.c[i])), pos["left"], "mark")])
    g, c = t2.pnl(p.cost_per_share)
    return g - c


def dl_limit(ctx, p) -> float:
    return p.daily_loss_pct * float(ctx.equity or 0.0)


def dl_room(ctx, state: dict, p, pos=None, tr=None, sd=None, i: int = 0, ts=None) -> float:
    """E11-funded-account-caps: the dollars of loss still allowed today = the limit - the closed losses - the open loss of the current position."""
    lost = max(0.0, -float(state.get("day_net", 0.0)))
    open_loss = 0.0
    if pos is not None and tr is not None:
        open_loss = max(0.0, -mark_net(tr, pos, sd, i, ts, p))
    return dl_limit(ctx, p) - lost - open_loss


def dl_blocks_order(pending: dict, ctx, state: dict, p) -> bool:
    """A new order whose risk would reach the limit (closed loss + its risk >= limit) is skipped."""
    risk = float(pending["shares"]) * max(0.0, float(pending["entry"]) - float(pending["stop"]))
    if risk >= dl_room(ctx, state, p) - 1e-9:
        hit("daily_loss_block")
        return True
    return False


def daily_loss_hit(ctx, state: dict, pos, tr, sd, i: int, ts, p) -> bool:
    """The closed losses of the day + the trade's marked P&L at bar i's close reached the limit."""
    return dl_room(ctx, state, p, pos, tr, sd, i, ts) <= 1e-9


def extras_loss_gate(trades: list, n_main: int, ctx, p) -> list:
    """E11-funded-account-caps (review fix): the rows after index n_main (Ma Deuce, Silver Bullet, NDOG scalp) are produced after the main bar loop, so the loop's `state["day_net"]` never saw them. Walk all rows in entry
    order; an extra row whose entry comes after the day's REALIZED net (every row closed before its entry) reached -limit is dropped (its order would have been refused) [our interpretation: post hoc on the extras only;
    the main-engine rows are not re-decided]."""
    lim = dl_limit(ctx, p)
    if lim <= 0 or len(trades) <= n_main:
        return trades
    ext = {id(t) for t in trades[n_main:]}
    keep = []
    done: list = []                                     # (exit_time, net) of the rows taken so far
    for t in sorted(trades, key=lambda t_: t_.entry_time):
        if id(t) in ext:
            net = sum(n for x, n in done if x is not None and x <= t.entry_time)
            if net <= -lim + 1e-9:
                hit("daily_loss_extra_block")
                continue
        g, c = t.pnl(p.cost_per_share)
        done.append((max((e[0] for e in t.exits), default=None), g - c))
        keep.append(t)
    order = {id(t): k for k, t in enumerate(trades)}
    return sorted(keep, key=lambda t: order[id(t)])


def order_risk(ctx, sd, sw, i: int, p, entry: float, risk: float, scalp: bool, draw, tags: dict, lvt: list) -> tuple:
    """_finish_order: the risk multiplier of this chunk's sizing rules and the extra total-risk cap (fraction of equity), tags/lvt updated.
    E8-risk-by-trade-class (class_risk): the per-unit risk of the class replaces risk_pct (scalp = a single fixed exit at <= 1.5R);
    E8-E9-5pct-near-htf (htf_near_risk_pct): toward a stored 4h / D / W / M level within htf_near_pts ES points the per-unit risk is htf_near_risk_pct and the total cap htf_near_cap_pct, else min(risk_pct, 0.015);
    E9-deep-discount-reduced (deep_run_mult): the with-trend trade after a one-way weekly run into deep discount / premium (htf.table `deep_run`) is sized down and takes no adds;
    E9-frequency-small-size (freq_ref): x min(1, freq_ref / trades in the last 5 sessions)."""
    S = _S()
    m, extra = 1.0, 0.0
    base = max(p.risk_pct, 1e-12)
    if p.class_risk:
        cls = "day"
        if scalp or (p.t1_fixed_all and ((0 < p.t1_fixed_r <= 1.5) or (p.t1_fixed_pts > 0 and p.t1_fixed_pts * p.es_pt <= 1.5 * risk + 1e-9))):
            cls = "scalp"
        if cls in p.class_risk:
            m *= float(p.class_risk[cls]) / base
            lvt.append("class_" + cls)
            hit("class_risk")
    if p.htf_near_risk_pct > 0:
        if htf_near(ctx, sd, i, p, entry, draw):
            m *= p.htf_near_risk_pct / base
            extra = max(0.0, p.htf_near_cap_pct - p.max_total_risk_pct)
            tags["es3"] = dict(tags.get("es3") or {}, near_cap=float(extra))
            lvt.append("htf_near_risk")
            hit("htf_near")
        else:
            m *= min(1.0, 0.015 / base)
    if p.deep_run_mult != 1.0:
        row = S._EN.bias_row_known(ctx, i)
        dr = 0
        if row is None:                                   # review fix: no htf table (SPY-only frames) - the switch is inert; say so once instead of silently
            hit("deep_run_no_table")
            if not _WARNED.get("deep_run"):
                _WARNED["deep_run"] = True
                warnings.warn("deep_run_mult != 1 but this frame has no htf table (no `deep_run` column): E9-deep-discount-reduced is inert here", RuntimeWarning, stacklevel=2)
        if row is not None:
            try:
                dr = int(row["deep_run"])
            except Exception:
                dr = 0
        if dr and dr == sd.sign:
            m *= p.deep_run_mult
            tags["no_adds"] = True
            lvt.append("deep_run")
            hit("deep_run")
    if p.freq_ref > 0 and p.freq_recent > p.freq_ref:
        m *= p.freq_ref / p.freq_recent
        lvt.append("freq_small")
        hit("freq_ref")
    return m, extra


_WARNED: dict = {}                    # once-per-process warning flags


def htf_near(ctx, sd, i: int, p, entry: float, draw=None) -> bool:
    """E8-E9-5pct-near-htf (review fix): the trade's DRAW is a stored 4h / D / W / M level (a Confluence array edge / CE of those timeframes, within 2 ES points of the draw price - the draw is pulled a pad
    short of its level) that lies within htf_near_pts ES points of the entry [our interpretation: the engine's level kinds carry no timeframe, so the draw is matched to the Confluence HTF levels].
    `htf_near_any` = the broader reading (ANY such level beyond the entry within htf_near_pts, draw or not) [our interpretation of "when trading toward a stored level"]."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return False
    now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
    near = cf.targets(now, sd.x(entry), sd.sign, ("4h", "D", "W", "M"), False)
    if not near:
        return False
    for v in near:
        if 0 < sd.sign * (v - sd.x(entry)) <= p.htf_near_pts * p.es_pt and (p.htf_near_any or draw is None or abs(sd.sign * (v - sd.x(draw))) <= 2 * p.es_pt + 1e-9):
            return True
    return False


# --- 3. adds (E12 / X8) -----------------------------------------------------------------------------------------------------------------------------

def dig_count(sd, top: float, z_i: int, i: int) -> int:
    """E12-repeat-dig-smaller-add (003 ~00:44:27) [our interpretation]: a "dig" = a bar whose low trades below the FVG top after a bar that closed above it; bars z_i + 1 .. i."""
    n = 0
    above = bool(sd.c[z_i] > top)
    for k in range(z_i + 1, i + 1):
        if above and sd.l[k] < top:
            n += 1
        above = bool(sd.c[k] > top)
    return n


def entry_zone(pos):
    """E12-repeat-dig-smaller-add: the ENTRY zone as a gap-like object (top, bottom, i = the fill bar) - the zone the retest add rests at; digs count after the fill."""
    top = pos.get("zone_top")
    if top is None:
        top = 2 * pos["fvg_ce"] - pos["fvg_bottom"]
    return SimpleNamespace(top=float(top), bottom=float(pos["fvg_bottom"]), i=int(pos["fill_i"]))


def dig_mult(sd, px: float, g, i: int, p, pos=None) -> float:
    """The size multiplier of an add at an FVG that price has dug into twice before (1.0 otherwise). `g` = the add's OWN FVG; no FVG passed (an OB / wick-CE / void / VI add) = 1.0 - no gap is guessed
    (review fix). Digs are counted on the bars after the gap formed; when `g` is the ENTRY FVG only the bars after the fill count (the entry retrace itself is not a repeat dig).
    Known deviation (build_log): the new-FVG add is armed on the gap's formation bar (no digs yet), so the multiplier bites the adds that name an older FVG (sm5 FVG add, `pos_g` re-adds); an add with an explicit
    size bypasses it."""
    if g is None or g.i >= i:
        return 1.0
    z_i = int(g.i)
    if pos is not None and pos.get("fvg_bottom") is not None and abs(float(g.bottom) - float(pos["fvg_bottom"])) <= 1e-9:
        z_i = max(z_i, int(pos["fill_i"]))
    if dig_count(sd, float(g.top), z_i, i) >= 2:
        hit("add_dig_mult")
        return float(p.add_dig_mult)
    return 1.0


def bars_tf(ctx, sd, lo: int, i: int, m: int) -> list:
    """Closed m-minute bars (clock-aligned) built from the base bars lo .. i (side space): [(first, last, O, H, L, C)] - a bar counts once its LAST base bar closed and only when its first base bar is the
    window's start (a window already running at `lo` is partial and skipped)."""
    out = []
    t = ctx.t
    k = lo
    while k <= i:
        g = int(t[k]) // m
        j = k
        while j + 1 <= i and int(t[j + 1]) // m == g:
            j += 1
        if int(t[k]) % m == 0 and (int(t[j]) + ctx.tf) % m == 0:
            out.append((k, j, float(sd.o[k]), float(sd.h[k:j + 1].max()), float(sd.l[k:j + 1].min()), float(sd.c[j])))
        k = j + 1
    return out


def lower_wick_ce(O: float, L_: float, C: float) -> float:
    """Side space: the CE of the lower wick, (low + body low) / 2 (the engine mirrors shorts, so the upper wick of a short is this one)."""
    return (L_ + min(O, C)) / 2


def latest_wick(ctx, sd, pos, i: int, p, used: set):
    """E12-wick-ce-add-5m (010 ~00:58:28): the latest complete add_wick_tf-minute bar since the fill with a lower wick of >= 2 ticks -> (ce, low, first_bar, last_bar, body_low), else None."""
    for k0, k1, O, H, L_, C in reversed(bars_tf(ctx, sd, pos["fill_i"] + 1, i, p.add_wick_tf)):          # bars formed AFTER the fill bar
        if min(O, C) - L_ >= 2 * p.tick - 1e-12:
            return None if k0 in used else (lower_wick_ce(O, L_, C), L_, k0, k1, min(O, C))      # the MOST RECENT wick only [our interpretation]; once per wick
    return None


def _band_5m(ctx, sd, i: int, p) -> list:
    """The same-side 5m FVGs of the Confluence valid at bar i's close, side space [(top, bottom, ce)]."""
    cf = getattr(ctx, "conf", None)
    if cf is None:
        return []
    out = []
    for top, bot, tf, sc, kn in cf.valid(sm2.now_ts(ctx, i), sd.sign, ("5m",), (0,), None):
        a, b = sd.x(top), sd.x(bot)
        out.append((max(a, b), min(a, b), (a + b) / 2))
    return out


def void_add_px(ctx, sd, pos, i: int, p):
    """E12-liquidity-void-add (018 ~00:04:01): a void formed on this bar (low[i] > high[i-1], after the fill) that overlaps the band CE +/- 25 % of a 5m FVG and sits above the entry OB MT ->
    (limit = void bottom + 1 tick, hold floor = the OB MT), else None. [our interpretation]: without an OB MT the entry zone's CE stands in for it."""
    if i < pos["fill_i"] + 2 or not sd.l[i] > sd.h[i - 1]:
        return None
    vb, vt = float(sd.h[i - 1]), float(sd.l[i])
    ob_mt = (pos.get("es3") or {}).get("ob_mt")
    ref = float(ob_mt) if ob_mt is not None else float(pos.get("fvg_ce") or pos["stop"])
    if vb <= ref:
        return None
    for top, bot, ce in _band_5m(ctx, sd, i, p):
        h = 0.25 * (top - bot)
        if vb <= ce + h + MIN1 and vt >= ce - h - MIN1:
            return vb + p.tick, ref
    return None


def reclaimed_add(sd, pos, i: int, p):
    """E12-mm-sell-model-adds (104 ~00:53:29): the A18 reclaimed OB (levels.reclaimed_obs; side space, so both directions) from before the fill that price closed beyond; a retest from the trade side whose
    closes stay beyond the candle's body low -> a limit at its body top, once. Returns (px, floor) or None."""
    e = pos["ext_i"]
    a = max(0, e - 48)
    best = None
    for z in L.reclaimed_obs(sd.o, sd.h, sd.l, sd.c, a, e, i):
        k = int(z.src)
        if k >= pos["fill_i"] or z.i > i:
            continue
        body_top, body_low = float(max(sd.o[k], sd.c[k])), float(min(sd.o[k], sd.c[k]))
        if sd.c[z.i:i + 1].min() < body_top - MIN1:          # review fix: the bodies must stay beyond the LIMIT level (the body top in side space; 104's "body bottom" of a short mirrors to it)
            continue
        if best is None or z.i > best[2]:
            best = (body_top, body_low, int(z.i))
    if best is None or not best[0] < sd.c[i]:
        return None
    return best[0], best[1]


def gate_candle(sd, ctx, entry: float, t1: float, fill_i: int):
    """X8-downclose-wickce-add (085 ~00:10:04), at the fill: the nearest opposing-close candle between the entry and T1 (side space: an up-close candle whose body lies in (entry, t1)) ->
    dict(open, ce, k), else None. ce = the CE of its target-side wick (high + body top) / 2."""
    best = None
    for k in range(max(ctx.start, 0), fill_i):
        if not sd.c[k] > sd.o[k]:
            continue
        lo, hi = float(min(sd.o[k], sd.c[k])), float(max(sd.o[k], sd.c[k]))
        if lo > entry and hi < t1 and sd.h[k] > hi:
            if best is None or lo < best[0]:
                best = (lo, dict(open=float(sd.o[k]), ce=float((sd.h[k] + hi) / 2), k=int(k)))
    return None if best is None else best[1]


def add_locs3_on(p) -> bool:
    return bool(p.add_wick_ce or p.add_void or p.add_gate_wick or p.add_reclaimed_ob or p.vi_ladder)


def add_locations3(ctx, sd, pos, tr, i: int, p, arm) -> None:
    """The new add locations of this chunk (at most one add armed on bar i's close); `arm(px, floor=None, size=None)` is the caller's arming function (True when armed).
      vi_ladder        026 ~01:48:03: rung 1 = a VI formed after the fill, rung 2 = the latest wick CE; both only beyond the entry zone's top; a wick-CE reaction that already flirted with the CE caps the add at 1 contract
      add_wick_ce      010 ~00:58:28: the CE of the latest add_wick_tf-minute wick since the fill
      add_void         018 ~00:04:01: a 1m void overlapping the 5m FVG CE band above the entry OB MT
      add_gate_wick    085 ~00:10:04: a body close through the open of the opposing-close candle in the way -> a stop-direction add at its wick CE
      add_reclaimed_ob 104 ~00:53:29: one add at the retest of a reclaimed OB"""
    S = _S()
    f = pos["fill_i"]
    if i <= f:
        return
    if p.vi_ladder and not pos["t1_done"]:
        rung = pos.get("vi_rung", 0)
        if pos.get("vi_wait") is not None and pos["add"] is None:       # review fix: a rung counts when its add FILLED; an add that expired / was cancelled leaves the ladder where it was
            n_, back_ = pos.pop("vi_wait")
            if len(tr.adds) <= n_:
                rung = pos["vi_rung"] = back_
                hit("vi_rung_unfilled")
        if rung == 0:
            vs = [z for z in sd.vis("bull") if z.i == i and z.i > f + 1]
            if vs and arm(float(vs[-1].top), floor=float(vs[-1].bottom)):
                pos["vi_rung"], pos["vi_wait"] = 1, (len(tr.adds), 0)
                hit("vi_ladder_vi")
                return
        elif rung == 1:
            w = latest_wick(ctx, sd, pos, i, p, pos.setdefault("wickce_used", set()))
            if w is not None and w[0] < sd.c[i] and (pos.get("zone_top") is None or w[0] > pos["zone_top"]):
                ce, low, k0, k1, blow = w
                weak = bool((sd.l[k1 + 1:i + 1] <= ce + p.tick).any() and (sd.c[k1 + 1:i + 1] > ce).any()) if k1 < i else False
                size = per_contract(p) if weak else None
                if arm(float(ce), floor=float(low), size=size):
                    pos["wickce_used"].add(k0)
                    pos["vi_rung"], pos["vi_wait"] = 2, (len(tr.adds), 1)
                    hit("vi_ladder_wick_weak" if weak else "vi_ladder_wick")
                    return
    if p.add_wick_ce and not p.vi_ladder:
        w = latest_wick(ctx, sd, pos, i, p, pos.setdefault("wickce_used", set()))
        if w is not None and w[0] < sd.c[i] and w[0] > pos["stop"]:
            if arm(float(w[0]), floor=float(w[1])):
                pos["wickce_used"].add(w[2])
                hit("add_wick_ce")
                return
    if p.add_void and not pos.get("void_used"):
        v = void_add_px(ctx, sd, pos, i, p)
        if v is not None and v[0] < sd.c[i] and arm(float(v[0]), floor=float(v[1])):
            pos["void_used"] = True
            pos["add"]["hold_es2"] = float(v[1])           # a body close under the entry OB's MT cancels the add (the OB MT stop is the built stop mode)
            hit("add_void")
            return
    if p.add_gate_wick and not pos.get("gate_done") and pos.get("es3_gate"):
        g = pos["es3_gate"]
        if sd.c[i] > g["open"] and g["ce"] > sd.c[i] and arm(float(g["ce"])):
            pos["gate_done"] = True
            pos["add"]["up"] = True                       # a stop-direction add: filled when price runs UP to the wick CE (side space)
            hit("add_gate_wick")
            return
    if p.add_reclaimed_ob and not pos.get("mm_add_done"):
        r = reclaimed_add(sd, pos, i, p)
        if r is not None:
            fr = _ES2_fracs(p)[0]
            q = max(p.lot, S._lots(min(1.0, fr) * (pos.get("plan_shares") or tr.shares), p.lot))
            if arm(float(r[0]), floor=float(r[1]), size=int(q)):
                pos["mm_add_done"] = True
                hit("add_reclaimed_ob")
                return


def _ES2_fracs(p) -> tuple:
    return _S()._ES2.add_size_fracs(p)


def momentum_add(pos, tr, sd, i: int, p, eq: float) -> bool:
    """E12-single-add-variants (020 ~00:01:40): after an OB-before-break entry and before T1, the first bar that CLOSES >= fill + add_mom_r x the initial risk arms ONE add of add_mom_frac x the first unit at
    market (filled at the next open); then no more adds (later OB retests included). [our interpretation of "runs away"]: measured from the OB body top (the order's `es3.ob_top`; the fill price when the
    tag is absent) + add_mom_r x the initial risk; only while no add has been made yet (review fix). Returns True when armed."""
    S = _S()
    if not pos.get("ob_pre") or pos["add"] is not None or pos.get("mom_done") or pos["t1_done"] or i <= pos["fill_i"]:
        return False
    r0 = pos.get("es3_r0")
    ref = (pos.get("es3") or {}).get("ob_top")
    ref = pos["fill_px"] if ref is None else float(ref)
    if not r0 or S._nadds(pos, tr) != 0 or sd.c[i] < ref + p.add_mom_r * r0:
        return False
    q = max(p.lot, S._lots(p.add_mom_frac * (pos.get("plan_shares") or tr.shares), p.lot))
    S._arm_add(pos, tr, float(sd.c[i]), i, p, eq, size=int(q))
    if pos["add"] is None:
        return False
    pos["add"]["now"] = True
    pos["mom_done"] = True
    pos["no_adds"] = True
    hit("add_momentum")
    return True


def mohawk_rung(shares: int, rung_px: float, stop: float, first_risk: float, p, eq: float):
    """E12-mohawk-add-ifvg (102 ~01:14:30): the smaller resting add beyond the IFVG far edge -> (px, q) or None. q = add fraction 0 x the first unit, shrunk so the first unit's risk plus the rung's stays in the
    total-risk cap; the stop must sit beyond the rung (else skipped)."""
    S = _S()
    if not stop < rung_px:
        return None
    fr = _ES2_fracs(p)
    if not fr:
        return None                                       # adds are off: no add, no mohawk rung
    q = S._lots(shares * fr[0], p.lot)
    room = S._total_cap(p, eq) - first_risk
    if (rung_px - stop) * q > room:
        q = S._lots(max(room, 0.0) / (rung_px - stop), p.lot)
    return (float(rung_px), int(q)) if q >= max(p.lot, 1) else None


# --- 4. stops (E6 / M2 / A12) -----------------------------------------------------------------------------------------------------------------------

def wick_ce_stop(sd, sw, i: int, entry: float, p):
    """E6-wick-ce-stop (022 ~01:14:11; 085 ~00:27:39; 089 ~00:06:48): stop_mode "wick_ce" - the bar between the sweep extreme and bar i with the longest lower wick (side space): its CE minus the pad and
    wick_ce_tol_ticks ticks (a trade a tick through the CE is tolerated). None when no bar has a wick of >= 2 ticks or the risk is outside min / max risk (the caller keeps its stop)."""
    best = None
    for k in range(int(sw["ext_i"]), i + 1):
        w = float(min(sd.o[k], sd.c[k]) - sd.l[k])
        if w >= 2 * p.tick - 1e-12 and (best is None or w > best[0]):
            best = (w, k)
    if best is None:
        return None
    k = best[1]
    s = lower_wick_ce(float(sd.o[k]), float(sd.l[k]), float(sd.c[k])) - p.pad - p.wick_ce_tol_ticks * p.tick
    if not (p.min_risk_pts * p.es_pt <= entry - s <= p.max_risk_pts * p.es_pt):
        return None
    hit("stop_wick_ce")
    return float(s)


def m2_confluence(sd, g, ob, p) -> bool:
    """M2-stop-by-fvg-choice: the FVG has a VI within one bar of its middle candle AND the OB touches it (the fvg_pick "2022" first choice)."""
    if ob is None:
        return False
    tk = 0.25 * p.es_pt
    return any(abs(z.i - g.src) <= 1 for z in sd.vis("bull")) and ob.top >= g.bottom - tk and ob.bottom <= g.top


def m2_auto_stop(sd, sw, g, ob, mt, p):
    """M2-stop-by-fvg-choice (022 ~00:53:59): stop_mode "m2_auto" - confluence FVG (VI + OB): the OB MT minus mt_pad_ticks ticks (4131.50 -> 4132); a plain FVG: the leg extreme - 1 tick (wide, so be selective)."""
    if m2_confluence(sd, g, ob, p) and mt is not None:
        hit("m2_auto_conf")
        return float(mt) - p.mt_pad_ticks * p.tick
    hit("m2_auto_plain")
    return float(sw["ext"]) - p.tick


def protect_levels(sd, sw, g, mt, entry: float, i: int, p, ob_near=None, swings: bool = False) -> list:
    """The PD arrays protecting a trade from the stop side, side space: [(top, bottom)] below the entry, nearest first - the entry OB MT, the OB nearest the sweep low (`ob_near`), the mitigation blocks' MTs
    of the leg, the FVG and VI far edges formed in the leg (the entry gap included), and (swings) the swing highs below the entry (levels.swing_tiers)."""
    e = int(sw.get("ext_i", 0))
    lv = []
    if mt is not None:
        lv.append((float(mt), float(mt)))
    if ob_near is not None:
        lv.append((float(ob_near), float(ob_near)))
    for z in sd.mitigations():
        if z.i <= i and z.i >= e:
            m = float(z.mt) if z.mt == z.mt else float((z.top + z.bottom) / 2)
            lv.append((m, m))
    for z in sd.gaps:
        if e <= z.i <= i:
            lv.append((float(z.top), float(z.bottom)))
    if g is not None and not any(abs(g.bottom - b) < MIN1 and abs(g.top - t) < MIN1 for t, b in lv):
        lv.append((float(g.top), float(g.bottom)))
    for z in sd.vis("bull"):
        if e <= z.i <= i:
            lv.append((float(z.top), float(z.bottom)))
    if swings:
        for q in sd.tiers()["stl"][0]:
            if q.known <= i:
                lv.append((float(q.price), float(q.price)))
    seen, out = set(), []
    for t, b in sorted(lv, key=lambda x: -x[1]):
        if b < entry - p.tick + MIN1 and (round(t / p.tick), round(b / p.tick)) not in seen:
            seen.add((round(t / p.tick), round(b / p.tick)))
            out.append((t, b))
    return out


def three_pd_stop(levels: list, n: int, pad: float):
    """E6-three-pd-arrays (098 ~00:47:02): behind the n-th protecting array (the outermost found when fewer) + the pad."""
    if not levels:
        return None
    return float(levels[min(n, len(levels)) - 1][1]) - pad


def next_pd_stop(levels: list, g_bottom: float, forming_low: float, pad: float):
    """E6-next-pd-array (cc12_004 ~00:55:21): the first array fully below the entry array that the entry array's forming candles did not trade below (its top under their lowest low), stop = its
    bottom - pad."""
    for t, b in levels:
        if t < g_bottom - MIN1 and t < forming_low - MIN1:
            return float(b) - pad
    return None


def bpr75_stop(lo: float, hi: float, ref: str, pad: float) -> float:
    """E6-bpr-75-stop (075 ~01:07:19): inside the cleared range at its 75 % level - "upper": H - 25 % of the range, "lower": L + 25 % - minus the pad."""
    return (hi - 0.25 * (hi - lo) if ref == "upper" else lo + 0.25 * (hi - lo)) - pad


def cleared_range(sd, i: int, p):
    """E6-bpr-75-stop: the most recent range [L, H] traded both ways that the close of bar i is above: an A11 BPR (sd.bprs) or levels.two_way_range. Returns (lo, hi) or None."""
    best = None
    for z in sd.bprs(p.bpr_max_gap_bars):
        if z.i <= i and sd.c[i] > z.top and (best is None or z.i > best[2]):
            best = (float(z.bottom), float(z.top), int(z.i))
    r = L.two_way_range(sd.o, sd.h, sd.l, sd.c, i)
    if r is not None and (best is None or r[2] > best[2]):
        best = r
    return None if best is None else (best[0], best[1])


def stop_adjust(ctx, sd, sw, g, ob, mt, entry: float, stop: float, i: int, p, prop_exit=None) -> float:
    """_scan_core, after the stop_mode choice: the stop of this chunk's stop modes (wick_ce / m2_auto / three_pd / next_pd / bpr75) and the propulsion-block MT stop (prop_stop "mt")."""
    S = _S()
    mode = p.stop_mode
    if mode == "wick_ce":
        s = wick_ce_stop(sd, sw, i, entry, p)
        stop = stop if s is None else s
    elif mode == "m2_auto":
        stop = m2_auto_stop(sd, sw, g, ob, mt, p)
    elif mode in ("three_pd", "next_pd"):
        ob_n = S._ob_at_low(sd, sw, i, p, ctx)
        lv = protect_levels(sd, sw, g, mt, entry, i, p, None if ob_n is None else ob_n["mt"], swings=mode == "next_pd")
        if mode == "three_pd":
            s = three_pd_stop(lv, p.three_pd_n, p.pad)
            hit("stop_three_pd")
        else:
            lows = sd.l[max(0, g.i - 2):g.i + 1]
            s = next_pd_stop(lv, float(g.bottom), float(lows.min()), p.pad)
            hit("stop_next_pd")
        stop = stop if s is None else s
    elif mode == "bpr75":
        r = cleared_range(sd, i, p)
        if r is not None:
            s = bpr75_stop(r[0], r[1], p.bpr75_ref, p.pad)
            if s < entry - p.min_risk_pts * p.es_pt:             # [our interpretation] an entry inside the cleared range (the 75 % level at / over the entry) keeps the built stop
                stop = s
                hit("stop_bpr75")
    if p.prop_stop == "mt" and p.prop_entry and prop_exit is not None and prop_exit < entry:
        stop = float(prop_exit) - p.pad                 # E6-propulsion-mt (cc04_008 ~00:05:21): the resting stop at the propulsion candle's MT (the X8 invalidation level), minus a tick
        hit("prop_stop_mt")
    return stop


def old_low_body_stop(sd, i: int, entry: float, stop: float, p):
    """E6-old-low-rejection-body (022 ~02:50:25) [our interpretation]: the old low = the nearest confirmed swing low under the entry that nothing traded through since; when it lies under the stop and within
    the max risk, the stop goes under the lowest open / close of its swing candles (the rejection body) - 1 tick. Returns the new stop or None."""
    best = None
    for q in sd.tiers()["stl"][1]:
        if q.known > i or q.price >= entry:
            continue
        if q.i + 1 <= i and sd.l[q.i + 1:i + 1].min() < q.price - MIN1:
            continue
        if best is None or q.price > best.price:
            best = q
    if best is None or not best.price < stop or entry - best.price > p.max_risk_pts * p.es_pt:
        return None
    n = max(int(sd.n), 1)
    k0, k1 = max(best.i - n, 0), min(best.i + n, i)
    body = min(float(min(sd.o[k], sd.c[k])) for k in range(k0, k1 + 1))
    return body - p.tick


def gap_bands(ctx, sd, i: int) -> list:
    """The opening gaps (NWOG / NDOG) known at bar i, side space [(top, bottom)] (ctx.gaps when gap_mode is "ict", else the NWOG table)."""
    S = _S()
    out = []
    if getattr(ctx, "gaps", None) is not None:
        for _, hi, lo, _ce in ctx.gaps:
            a, b = sd.x(hi), sd.x(lo)
            out.append((max(a, b), min(a, b)))
    else:
        for a_, b_ in S._nwogs(ctx, i):
            a, b = sd.x(a_), sd.x(b_)
            out.append((max(a, b), min(a, b)))
    return out


def gap_edge_stop(bands: list, zone: tuple, entry: float, stop: float, p):
    """E6-nwog-stop (050 ~00:54:56): "own" = beyond the far edge of the opening gap the entry zone (bottom, top) sits in, "all" = beyond every opening gap under the entry within the max risk. + 1 tick."""
    zb, zt = zone
    if p.stop_gap_edge == "own":
        own = [b for t, b in bands if b <= zt + MIN1 and t >= zb - MIN1]
        return None if not own else float(min(own)) - p.pad
    near = [b for t, b in bands if b < entry and entry - b <= p.max_risk_pts * p.es_pt]
    return None if not near else min(float(min(near)) - p.pad, stop)


def htf_floor(ctx, sd, i: int, price: float, p):
    """E6-refined-stop-htf: the lowest bottom (side space) of the 15m .. W arrays (FVG / OB / VI of the Confluence, or the DayCtx HTF FVGs) that the sweep price traded into - inside the array or up to
    2 x eq_tol_pts under its bottom (a wick that overshoots the HTF level) [our interpretation of "the sweep traded into an HTF array"]."""
    tol = 2 * p.eq_tol_pts * p.es_pt
    lows = []
    cf = getattr(ctx, "conf", None)
    if cf is not None:
        for top, bot, tf, sc, kn in cf.valid(sm2.now_ts(ctx, i), sd.sign, ("15m", "30m", "1h", "4h", "D", "W"), (0, 1, 3), None):
            a, b = sd.x(top), sd.x(bot)
            t_, b_ = max(a, b), min(a, b)
            if b_ - tol <= price <= t_ + tol:
                lows.append(b_)
    elif getattr(ctx, "hzones", None):
        S = _S()
        now = ctx.idx[i] + pd.Timedelta(minutes=ctx.tf)
        j = ctx.full_off + i
        for z, known, m in ctx.hzones:
            if known > now or z.kind != ("bull" if sd.sign > 0 else "bear"):
                continue
            top, bot = (z.top, z.bottom) if sd.sign > 0 else (-z.bottom, -z.top)
            k = int(ctx.full_idx.searchsorted(known))
            if len(ctx.full_c[k:j + 1]) and (sd.sign * ctx.full_c[k:j + 1]).min() < bot:
                continue
            if bot - tol <= price <= top + tol:
                lows.append(bot)
    return min(lows) if lows else None


def widen_stop(cands: list, entry: float, stop: float, p):
    """E6-new-trader-wide-stops (102 ~01:52:49): a structural stop tighter than tight_stop_pts is pushed out to the next structural level (the nearest candidate whose stop - pad leaves >= tight_stop_pts of
    risk) instead of skipped. `cands` = [(top, bottom)] nearest first. Returns the new stop or None."""
    need = p.tight_stop_pts * p.es_pt
    for t, b in cands:
        s = b - p.pad
        if entry - s >= need - MIN1:
            return float(s)
    return None


def stop_post(ctx, sd, sw, i: int, p, entry: float, stop: float, tags: dict) -> float:
    """_finish_order, after the structural stop: stop_old_low_body (E6-old-low-rejection-body), stop_gap_edge (E6-nwog-stop), stop_htf_anchor (E6-refined-stop-htf), stop_widen_new (E6-new-trader-wide-stops)."""
    if p.stop_old_low_body:
        s = old_low_body_stop(sd, i, entry, stop, p)
        if s is not None:
            stop = s
            hit("stop_old_low_body")
    if p.stop_gap_edge:
        zb = float(tags.get("fvg_bottom", entry))
        zt = float(tags.get("zone_top", entry))
        s = gap_edge_stop(gap_bands(ctx, sd, i), (min(zb, entry), max(zt, entry)), entry, stop, p)
        if s is not None:
            stop = s
            hit("stop_gap_edge")
    if p.stop_htf_anchor and sw.get("ext") is not None:
        fl = htf_floor(ctx, sd, i, float(sw["ext"]), p)
        if fl is not None:
            stop = min(stop, min(float(sw["ext"]), fl) - p.pad)
            hit("stop_htf_anchor")
    if p.stop_widen_new and p.trader_mode == "new" and entry - stop < p.tight_stop_pts * p.es_pt:
        lv = protect_levels(sd, sw, None, None, entry, i, p, swings=True)
        s = widen_stop(lv, entry, stop, p)
        if s is not None:
            stop = s
            hit("stop_widen_new")
    return stop


def ob_stop_for(ob: dict, p):
    """E6-ob-body-stop (cc04_003 ~00:10:44): the OB-before-break stop - "body": under the OB body low (the close of its lowest candle) - pad, "wick": under the OB wick low - pad."""
    if not p.ob_stop_kind:
        return None
    return float(ob["body_low"] if p.ob_stop_kind == "body" else ob["lo"]) - p.pad


def ob_top_last_open(sd, j: int, k: int) -> float:
    """A12-ob-anchor (cc05_015 ~00:16:48): the "last_open" anchor = the open of the last down-close candle of the series (the highest open by default)."""
    return float(sd.o[k])


def trail_wick(sd, pos, i: int, p) -> None:
    """E6-wick-ce-stop, managed variant (022 ~01:14:11): each new defending wick (lower wick of >= 2 ticks) of bar i after the fill raises the stop to its CE - pad (never lowers; kept under the market)."""
    if i <= pos["fill_i"]:
        return
    w = float(min(sd.o[i], sd.c[i]) - sd.l[i])
    if w < 2 * p.tick - 1e-12:
        return
    s = lower_wick_ce(float(sd.o[i]), float(sd.l[i]), float(sd.c[i])) - p.pad
    if s > pos["stop"] and s < sd.c[i] - p.tick:
        _S()._MG.raise_stop(pos, s, trail=True)
        hit("trail_wick_ce")


# --- 5. position hooks -----------------------------------------------------------------------------------------------------------------------------

def tight_loss(tr, p, pos=None) -> bool:
    """E6-new-trader-wide-stops: a stop-out from a tight stop (risk < tight_stop_pts) in trader_mode "new" allows no immediate same-direction re-entry (experienced only) [our interpretation of "tight"]."""
    r0 = (pos or {}).get("es3_r0")                       # review fix: the INITIAL risk (tr.entry is the average price once adds exist)
    r0 = abs(tr.entry - tr.stop) if r0 is None else float(r0)
    return bool(p.trader_mode == "new" and r0 < p.tight_stop_pts * p.es_pt - MIN1)


def on_fill(ctx, sd, pos, tr, o: dict, i: int, p, fill: float) -> None:
    """run_day, at the fill: the per-position data of this chunk (initial risk, the OB MT exit, the gate candle, the leverage / near-HTF room, the probe cut)."""
    es = o.get("es3") or {}
    pos["fill_px"] = float(fill)
    pos["es3_r0"] = float(fill - o["stop"])
    if es:
        pos["es3"] = dict(es)
    if es.get("near_cap"):
        pos["es3_room"] = float(es["near_cap"])
    ex = []
    if p.vi_ladder_exit and es.get("ob_mt") is not None and es["ob_mt"] < fill:
        ex.append((float(es["ob_mt"]), "ob_mt_inval", True))
    if es.get("probe_cut") is not None:
        ex.append((float(fill - es["probe_cut"] * (fill - o["stop"])), "probe_cut", False))
        pos["no_adds"] = True
    if ex:
        pos["es3_exits"] = ex
    if p.add_gate_wick:
        pos["es3_gate"] = gate_candle(sd, ctx, float(fill), float(o["t1"]), i)


def exit_hit(pos, o: float, l: float):
    """The position loop, before the stop test: a resting early exit of this chunk was traded (low <= level) -> (price, reason). Entries (level, reason, before_t1_only)."""
    for lvl, why, pre_t1 in pos.get("es3_exits") or ():
        if pre_t1 and pos["t1_done"]:
            continue
        if l <= lvl:
            return min(o, lvl), why
    return None


def probe_order(ctx, sides, i: int, p, state: dict, trades: list, done: dict, want_side: int, lock):
    """new-probe-position (026 ~00:16:16): an indecisive session - the bias is set (want_side), nothing traded and no order by probe_t (the first AM bar at / after it) - a market probe of probe_mult x the
    normal size toward the bias at bar i's close: stop = the session's extreme against the bias so far - pad, one target = the locked draw (else the nearest HTF draw of the row), no adds, closed when
    price trades probe_cut x the stop distance against it. Once a day. Returns an order dict or None."""
    S = _S()
    t = ctx.t[i]
    if state.get("probe_done") or t < p.probe_t or done.get("AM") or trades or not want_side:
        return None
    sd = sides[0] if want_side > 0 else sides[1]
    k0 = S._idx_at(ctx, 570)
    if k0 > i:
        return None
    entry = float(sd.c[i])
    stop = float(sd.l[k0:i + 1].min()) - p.pad
    if lock is not None and lock.get("side") == sd.sign and lock.get("target") is not None:
        tgt = float(sd.x(lock["target"]))
    else:
        row = ctx.bias_row if ctx.bias_row is not None else {}
        v = row.get("draw_up" if sd.sign > 0 else "draw_dn") if hasattr(row, "get") else None
        tgt = None if v is None or v != v else float(sd.x(v))
    if tgt is None or tgt <= entry + p.min_risk_pts * p.es_pt:
        return None
    state["probe_done"] = True
    sw = dict(session="AM", name="probe", level=entry, key="probe", ext=stop + p.pad, ext_i=i, broke=i, sweep_i=i, smt=None, smt2=None, **{S._SM.SYNTH: True})
    tags = dict(unicorn=False, fvg_bottom=stop, fvg_ce=entry, entry_kind="probe", mitigation=False, propulsion=False, market=True, no_leg_wait=True, skip_po3=True, no_adds=True,
                lv_tags=["probe"], es3=dict(probe_cut=float(p.probe_cut)))
    o = S._finish_order(ctx, sd, i, p, "AM", sw, entry, stop, p.probe_mult, entry, tags, skip_leg_pd=True, fixed=[(tgt, "pool")])
    if o is not None:
        hit("probe")
    return o


# --- re-entry after an OB-MT stop-out (E6-attempt-based-stop) ---------------------------------------------------------------------------------------

def ob_low_order(ctx, sd, i: int, p, session: str, risk_mult: float):
    """E6-attempt-based-stop (cc02_005 ~00:01:47; reentry_stop "ob_low"): after the stop-out, the first NEW order block - a down-close candle (side space) formed after the stop-out whose high a later closed bar
    traded above - is bought at its open (body top), the stop under its full low - 1 tick; the risk is the re-entry risk (reentry_risk_mult, half by default). Once per re-entry context. Returns an order or None."""
    S = _S()
    rc = getattr(ctx, "re_ctx_now", None)
    sidename = "long" if sd.sign > 0 else "short"
    if not rc or not rc.get("pending") or rc.get("armed_ob") or rc.get("side") != sidename:
        return None
    si = int(rc["stop_i"])
    for k in range(si + 1, i):
        if not sd.c[k] < sd.o[k] or not sd.h[k + 1:i + 1].max() > sd.h[k]:
            continue
        cc_ = p.reentry_mode == "cc_ob" and p.reentry_cc_entry == "high"          # caption-gap X13-reentry-mechanics: the limit at the validated candle's HIGH (the variant: its open), the stop under its whole low
        entry, stop = (float(sd.h[k]) if cc_ else float(sd.o[k])), float(sd.l[k]) - p.pad
        if not entry < sd.c[i] or entry - stop < p.min_risk_pts * p.es_pt:
            continue
        o = S._SM4._order(ctx, sd, i, p, session, risk_mult, "ob_low", entry, stop, level=entry, ext=float(sd.l[k]), ext_i=int(k), broke=i, fvg_bottom=float(sd.l[k]),
                          lv=("ob_low",), sm7=dict(kind="ob_low"))
        if o is not None:                                  # review fix: a candidate the risk filters reject does not end the context - the next candidate is tried
            rc["armed_ob"] = True
            hit("reentry_ob_low")
            return o
    return None
