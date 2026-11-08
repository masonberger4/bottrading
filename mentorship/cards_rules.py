"""Scorecard cards (mentorship/cards.py): the engine concepts the cards needed that the engine did not have yet (Mase 2026-11-08: build every card default).

Each function sits behind its Params switch; interpretations the card does not pin down are marked [our interpretation]. `HITS` counts the code paths that ran (tests)."""
from __future__ import annotations

HITS: dict[str, int] = {}


def hit(k: str) -> None:
    HITS[k] = HITS.get(k, 0) + 1


# --- ATH-RULE -------------------------------------------------------------------------------------------------
def ath_map(ds: list) -> dict:
    """{date: the highest high of every day frame before it} (the first day has none). The history is what the run loaded, so the first
    days of a run see a lower "all-time" high than the market's [our interpretation]."""
    out, top = {}, None
    for g in ds:
        d = g.index[0].date()
        if top is not None:
            out[d] = top
        h = float(g.high.max())
        top = h if top is None else max(top, h)
    return out


def ath_block(ctx, sd, o: dict, p) -> str | None:
    """ATH-RULE: a funnel key for a short armed near the all-time high, else None. "no_top_pick" (A, "don't pick the top: daily bias stays long; shorts
    only intraday") blocks the setups that pick a high (turtle soup, three drives, reversal: bh1e._is_top_pick); "longs_only" (C) blocks every short."""
    ath = getattr(ctx, "ath", None)
    if sd.sign > 0 or ath is None:
        return None
    hit("eval_ath")
    if sd.x(o["entry"]) < ath * (1.0 - p.ath_near_frac) - 1e-9:
        return None
    if p.ath_rule == "longs_only":
        hit("ath_no_short")
        return "x_ath_no_short"
    if _top_pick(o):
        hit("ath_top_pick")
        return "x_ath_top_pick"
    return None


def _top_pick(o: dict) -> bool:
    """bh1e._is_top_pick with whole tags (its substring test also matched lc_reversal / td_reversal, S1 review)."""
    from . import sm7 as _SM7
    from .bh1e import TOP_KINDS
    tags = set(str(o.get("lv_tags") or "").split("|"))
    return bool(_SM7.is_ts_kind(o) or {"three_drives", "reversal"} & tags or str(o.get("entry_kind") or "") in TOP_KINDS)


def check_params(p) -> None:
    """Validation (strategy.Params.__post_init__)."""
    if p.ath_rule not in ("off", "no_top_pick", "longs_only"):
        raise ValueError(f"ath_rule {p.ath_rule!r}: expected off / no_top_pick / longs_only")
    if not 0 <= p.ath_near_frac < 1:
        raise ValueError("ath_near_frac in [0, 1)")
