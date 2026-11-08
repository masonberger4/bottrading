"""Scorecard cards in the engine (Mase 2026-11-08: build the scorecard defaults into the engine,
every other position a backtestable switch).

Each card in mentorship/scorecard/defaults.csv maps its positions to Params overrides. Every
position of a card sets the SAME keys, so any position can be switched on over the defaults.
The default position's values ARE the Params() defaults (tests/test_cards.py checks it).

A position that the engine cannot express yet is listed in NOT_BUILT with the reason, never
silently dropped. A position that is the engine's behaviour with no parameter (a label, or a
judgment the bot already follows) maps to {} and is listed in SAME_AS_ENGINE.

Switch variants for the backtest screen are named "SC-<card>-<pos>" (study.DECISIONS).
One-source rules (scorecard/singles.csv) map the same way under "SG-<digest>-<num>", with
positions "on" (the draft default) and "off" (the old engine behaviour).
"""
from __future__ import annotations

import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent / "scorecard"

# {card: {pos: {param: value}}} - filled stage by stage
CARDS: dict[str, dict[str, dict]] = {}
# {(card, pos): reason}
NOT_BUILT: dict[tuple, str] = {}
# {(card, pos): note} - positions that need no parameter (the engine already does it)
SAME_AS_ENGINE: dict[tuple, str] = {}

# {card: note} - built cards whose switches only change tags while another switch is off; their variants are
# left out of the screen (variants(screen=True)) until that switch is on
TAG_ONLY: dict[str, str] = {}

# {(digest, num): {"on": {...}, "off": {...}}} - one-source rules
SINGLES: dict[tuple, dict[str, dict]] = {}
SINGLES_NOT_BUILT: dict[tuple, str] = {}


def card_defaults() -> dict[str, str]:
    """{card: default position} from scorecard/defaults.csv."""
    with open(HERE / "defaults.csv", encoding="utf-8") as f:
        return {r["conflict"]: r["default"] for r in csv.DictReader(f)}


def pending_ties() -> set[str]:
    """Cards whose tie Mase has not picked yet: every position is a switch and the engine keeps its
    current behaviour as the default until he decides (coordinator 2026-11-08)."""
    with open(HERE / "defaults.csv", encoding="utf-8") as f:
        return {r["conflict"] for r in csv.DictReader(f) if "TIE PENDING" in r["flags"]}


def card_positions() -> dict[str, list[str]]:
    """{card: [positions]} from scorecard/positions.csv."""
    out: dict[str, list[str]] = {}
    with open(HERE / "positions.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["conflict"], []).append(r["pos"])
    return out


def singles_status() -> dict[tuple, str]:
    """{(digest, num): status} from scorecard/singles.csv."""
    with open(HERE / "singles.csv", encoding="utf-8") as f:
        return {(r["digest"], r["num"]): r["status"] for r in csv.DictReader(f)}


def default_overrides() -> dict:
    """The default position's params of every built card and every built single ("on")."""
    d, pend = card_defaults(), pending_ties()
    out: dict = {}
    for card, ps in CARDS.items():
        if card not in pend:
            out.update(ps.get(d[card], {}))
    for key, ps in SINGLES.items():
        out.update(ps["on"])
    return out


def _is_engine(kw: dict) -> bool:
    """True when every key already has this value in Params() (no switch needed)."""
    from .strategy import Params
    p = Params()
    return all(getattr(p, k) == v for k, v in kw.items())


def variants(screen: bool = False) -> dict[str, dict]:
    """Every non-default built position as a study.DECISIONS variant (overrides over Params()); screen=True leaves out TAG_ONLY cards."""
    d, pend = card_defaults(), pending_ties()
    out: dict[str, dict] = {}
    for card, ps in CARDS.items():
        if screen and card in TAG_ONLY:
            continue
        base = None if card in pend else ps.get(d[card])
        for pos, kw in ps.items():
            if (pos != d[card] or card in pend) and kw and kw != base and not _is_engine(kw):
                out[f"SC-{card}-{pos}"] = dict(kw)
    for (dig, num), ps in SINGLES.items():
        if ps["off"]:
            out[f"SG-{dig}-{num}-off"] = dict(ps["off"])
    return out


# --- stage b: times, opening range, opening gaps -----------------------------------------------------
Q = "queued: new engine concept, built in the new-concepts stage"   # placeholder reason until built

CARDS.update({
    "LUNCH-WINDOW": {                     # the lunch range (its high / low are PM pools, known from its end)
        "A": dict(lunch_range=(720, 780)),
        "B": dict(lunch_range=(720, 810)),
        "C": dict(lunch_range=(690, 810)),
        "D": dict(lunch_range=(630, 810)),    # [our interpretation] the lunch retracement from 10:30
    },
    "LUNCH-TRADE": {                      # T8 lunch-macro entry: a retrace against the AM move
        "A": dict(lunch_macro_entry=False),
        "B": dict(lunch_macro_entry=True),
    },
    "LUNCH-TARGET": {                     # T8 lunch pool L (nct2.lunch_pools)
        "A": dict(lunch_raid="recent"),
        "B": dict(lunch_raid="after_1000"),
        "C": dict(lunch_raid="macro_0950"),
    },
    "MACRO-GRID": {
        "A": dict(macro_grid="fixed"),
        "B": dict(macro_grid="hourly"),
    },
    "LAST-HOUR": {                        # B: the 15:45-15:50 MOC macro too, runner held into it
        "A": dict(pm_macro_runner=False),
        "B": dict(pm_macro_runner=True),
    },
    "LONDON-MACRO": {"B": {}},
    "ASIA": {                             # the Asia NDOG protocol (needs the 18:00-24:00 window)
        "A": dict(asia_session=False, ndog_scalp=False),
        "B": dict(asia_session=True, ndog_scalp=True),
    },
    "PREMARKET-ENTRY": {
        "A": dict(pre_0700=False),
        "B": dict(pre_0700=True),              # 07:00-08:30 (flat before an 08:30 release); 09:00-09:29 (pre_0900) is not in the card
    },
    "OPEN-RANGE-TRADE": {
        "A": dict(or_no_entry=True, or_end=600),
        "B": dict(or_no_entry=False, or_end=600),
        "C": dict(or_no_entry=True, or_end=630),   # first hour; grading its range is not built
    },
    "ORG-CLOSE": {
        "A": dict(org_close=975),
        "B": dict(org_close=960),
    },
    "GAP-LIFE": {
        "A": dict(nwog_days=60, ndog_life="friday", org_days=5),
        "B": dict(nwog_days=25, ndog_life="5d", org_days=5),
        "C": dict(nwog_days=60, ndog_life="friday", org_days=5),
        "E": dict(nwog_days=60, ndog_life="friday", org_days=4),   # today + the last three; the ATH carry-on is not built
    },
    "NDOG-DEF": {"A": {}},
})
SAME_AS_ENGINE.update({
    ("LONDON-MACRO", "B"): "no London macro time; the engine has none",
    ("NDOG-DEF", "A"): "the engine's NDOG is 17:00 settlement -> 18:00 reopen",
    ("GAP-LIFE", "C"): "the last five ORGs (org_days=5) is the engine's default",
})
NOT_BUILT.update({
    ("LONDON-MACRO", "A"): "London entries are off (london_kz); a 03:30 macro gate has nothing to gate",
    ("PREMARKET-RANGE", "A"): Q, ("PREMARKET-RANGE", "B"): Q, ("PREMARKET-RANGE", "C"): Q,
    ("PREMARKET-RANGE", "D"): Q, ("PREMARKET-RANGE", "E"): Q, ("PREMARKET-RANGE", "F"): Q,
    ("PREMARKET-RANGE", "G"): Q, ("PREMARKET-RANGE", "H"): Q,
    ("OPEN-RANGE-TRADE", "D"): "needs a 'clean pre-market read' rule (judgment); no exact rule yet",
    ("FPFVG-DEF", "A"): Q, ("FPFVG-DEF", "B"): Q, ("FPFVG-DEF", "C"): Q, ("FPFVG-DEF", "D"): Q,
    ("FPFVG-DEF", "E"): "sub-1m charts; the engine runs 1m / 5m bars",
    ("FPFVG-DEF", "F"): Q, ("FPFVG-DEF", "G"): Q, ("FPFVG-DEF", "H"): Q,
    ("ORG-CE-WINDOW", "A"): Q, ("ORG-CE-WINDOW", "B"): Q, ("ORG-CE-WINDOW", "C"): Q, ("ORG-CE-WINDOW", "D"): Q,
    ("ORG-AFTER-CE", "A"): Q, ("ORG-AFTER-CE", "B"): Q,
    ("ORG-SIZE", "A"): Q, ("ORG-SIZE", "B"): Q, ("ORG-SIZE", "C"): Q, ("ORG-SIZE", "D"): Q, ("ORG-SIZE", "E"): Q,
    ("GAP-LIFE", "D"): "NDOG / ORG two-week life keyed to Mon / Fri only; queued",
    ("NDOG-DEF", "B"): Q,
})


# --- stage c: news, day filters, weekly profile -----------------------------------------------------------
_NW = lambda w, m, two, j: dict(news_wait=w, news_wait_min=m, news_two_sided=two, news_judas=j)
CARDS.update({
    "NEWS-WAIT": {
        "A": _NW("fixed", 30, False, "off"),
        "B": _NW("fixed", 15, False, "off"),
        "C": _NW("fixed", 2, False, "off"),
        "D": _NW("range", 30, False, "block"),   # trade off the release: its dealing range, the first run is the Judas
        "F": _NW("range", 30, True, "wait"),     # several reports: both sides of the release range taken first
        "H": _NW("range", 30, False, "block"),
    },
    "NEWS-HOLD": {
        "A": dict(hold_through_0830=False),
        "B": dict(hold_through_0830=True),
    },
    "FOMC-DAY": {                              # PM entries from: B the first FVG after 14:00; C after 14:45
        "B": dict(fomc_pm_from=840),
        "C": dict(fomc_pm_from=885),
    },
    "NFP-THU-FRI": {
        "A": dict(nfp_day=False, nfp_thu=False, nfp_week_block=True),
        "B": dict(nfp_day=True, nfp_thu=True, nfp_week_block=False),
    },
    "FED-SPEECH": {                            # Mase's tie pick 2026-11-08: A (changed from D at 21:34 UTC)
        "A": dict(fed_chair_skip_am=True),
    },
    "MONDAY": {                                # Mase's tie pick 2026-11-08: A
        "A": dict(monday_mode="trade"),
        "B": dict(monday_mode="obvious"),
    },
    "CPI-WEEK": {
        "A": dict(pre_cpi="small"),
        "C": dict(pre_cpi="off"),
    },
    "AFTER-BIG-DAY": {
        "A": dict(big_day_am_skip=True, big_day_am_resume=0),     # sacrifice the AM, keep the PM
        "B": dict(big_day_am_skip=True, big_day_am_resume=630),   # no trades 09:30-10:30 [the down-day condition is not built: any very large day]
    },
    "RANGE-REGIME": {"B": {}},
    "TWO-SIDED": {                             # A: both sides armed in one window = stand aside for the rest of it (B17.1 neutral_5050 "armed")
        "A": dict(neutral_5050="armed"),       # the rollover-week "trade very light" part is not built (queued)
    },
    "SEASON-ACTIVITY": {
        "A": dict(season_quality="size"),
        "B": dict(season_quality="off"),
    },
    "INSIDE-DAY": {
        "A": dict(inside_day_def="wick"),
        "B": dict(inside_day_def="body"),
        "C": dict(inside_day_def="body_in_range"),
    },
    "HOLIDAY-WEEK": {
        "A": dict(holiday_week_skip=False),
        "B": dict(holiday_week_skip=True),
    },
    "TGIF-DEPTH": {                            # acts with the TGIF model (tgif_model, off by default)
        "A": dict(tgif_cap=0.30, tgif_stand_down=0.40),
        "B": dict(tgif_cap=0.40, tgif_stand_down=0.45),   # [our interpretation] up to 40%
    },
    "TGIF-TIMING": {                           # acts with the TGIF model (tgif_model, off by default)
        "A": dict(tgif_thu=False),             # Friday only
        "B": dict(tgif_thu=True),              # the TGIF side block from Thursday PM once Thursday holds the week's extreme after 10:00 (dwc3 #33)
    },
    "WEEK-PROFILE": {                          # C: Thursday caps the week (N10 thu_cap)
        "C": dict(thu_cap=True),
        "A": dict(thu_cap=False),              # [our interpretation] no Thursday cap; the Tue/Wed low is the wk_profile tag
    },
})
SAME_AS_ENGINE.update({
    ("NEWS-WAIT", "H"): "the release dealing range applies to 10:00 releases too",
})
NOT_BUILT.update({
    ("NEWS-WAIT", "E"): "fade the release's first leg on range-bound days after 10:00: no range-day release fade yet; queued",
    ("NEWS-WAIT", "G"): Q,
    ("FOMC-DAY", "A"): "an FOMC AM cut-off at 10:30 is not built; queued",
    ("FOMC-DAY", "D"): "beginner version (avoid FOMC day); experienced default stands",
    ("FED-SPEECH", "B"): Q, ("FED-SPEECH", "C"): Q,
    ("FED-SPEECH", "D"): "dropped: Mase changed his pick to A (2026-11-08); needs each speech's end time, which calendar.FED_CHAIR lacks",
    ("MONDAY", "C"): "Monday pre-market only needs a per-day session list; queued",
    ("CPI-WEEK", "B"): Q,
    ("AFTER-BIG-DAY", "C"): "'keep expectations low' has no exact rule",
    ("RANGE-REGIME", "A"): "queued (S1 review): a PDH / PDL turtle soup back into a multi-week daily range, target the FVG inside the old extreme; drange_scalp is not it",
    ("TWO-SIDED", "B"): "pick a side at small size and scratch fast: no rule for which side; queued",
    ("SEASON-ACTIVITY", "C"): Q,
    ("HOLIDAY-WEEK", "D"): Q,
    ("HOLIDAY-WEEK", "C"): "holiday_week_thu_fri only lifts the NFP-week Thu/Fri block, which is off; a Thu/Fri preference is queued",
    ("TGIF-DEPTH", "C"): Q,
    ("TGIF-TIMING", "C"): Q,
    ("WEEK-PROFILE", "B"): Q,
})


# --- stage d: PD arrays, levels, bias and SMT, data, entries -------------------------------------------------
CARDS.update({
    "MSS-CLOSE": {"A": dict(mss_mode="wick"), "B": dict(mss_mode="close")},
    "OB-CANDLE": {"A": dict(ob_pick="original"), "B": dict(ob_pick="largest_body")},
    "IFVG-CONFIRM": {"A": dict(ifvg_hold=False), "B": dict(ifvg_hold=True)},
    "BREAKER-ZONE": {"A": dict(breaker_zone="body"), "B": dict(breaker_zone="range")},
    "UNICORN": {"A": {}},
    "PDA-LOOKBACK": {"B": dict(ipda_pools=True)},
    "LIQ-LOCATION": {"A": {}},
    "SHORT-LOCATION": {"B": {}},
    "SMT-USE": {"A": dict(smt_partial="off", smt_ym=False), "B": dict(smt_partial="a", smt_ym=True)},   # B needs the sister indices (YM too)
    "SMT-SET": {"A": dict(smt_ym=True), "B": dict(smt_ym=False)},
    "BIAS-SOURCE": {"A": {}},
    "CONTRACT": {                              # Mase picked B (2026-11-08), which is not built yet: the engine keeps front-month prices
        "A": dict(price_frame="front_month"),
    },
    "FVG-ENTRY": {"A": dict(entry="edge"), "B": dict(entry="ce")},
    "ATH-RULE": {                              # near the all-time high (cards_rules.ath_block; ath_near_frac)
        "A": dict(ath_rule="no_top_pick"),     # no turtle-soup / three-drive / reversal shorts; structure shorts stay
        "B": dict(ath_rule="off"),
        "C": dict(ath_rule="longs_only"),
    },
    "TF-CHOP": {"A": {}},
})
SAME_AS_ENGINE.update({
    ("UNICORN", "A"): "the engine's unicorn is an FVG inside a breaker",
    ("LIQ-LOCATION", "A"): "the engine's pools are wick extremes and relative equal highs / lows",
    ("SHORT-LOCATION", "B"): "the engine has no deep-discount short block",
    ("BIAS-SOURCE", "A"): "the engine's bias is the HTF draw (daily table) that intraday trades follow",
    ("RANGE-REGIME", "B"): "continuation through the break is the engine's default",
    ("TF-CHOP", "A"): "the engine reads the draw from the higher timeframes (5m / 15m / 1h / 4h / D arrays); it never drops below 1m",
})
NOT_BUILT.update({
    ("OB-CANDLE", "C"): Q, ("OB-CLOSE", "A"): Q, ("OB-CLOSE", "B"): Q,
    ("IFVG-CONFIRM", "C"): Q, ("IFVG-CONFIRM", "D"): "anticipation from structure is judgment; no exact rule yet",
    ("UNICORN", "B"): "market maker model stages are not built", ("UNICORN", "C"): Q,
    ("FVG-VALID", "A"): Q, ("FVG-VALID", "B"): Q, ("FVG-VALID", "C"): Q, ("FVG-VALID", "D"): Q,
    ("WICK-PRIORITY", "A"): Q, ("WICK-PRIORITY", "B"): Q,
    ("TF-CHOP", "B"): "sub-1m entries; the engine runs 1m / 5m bars",
    ("OB-VALID", "A"): Q, ("OB-VALID", "B"): Q,
    ("FVG-CARRY", "A"): Q, ("FVG-CARRY", "B"): Q, ("FVG-CARRY", "C"): Q, ("FVG-CARRY", "D"): Q,
    ("WICK-SELECT", "A"): Q, ("WICK-SELECT", "B"): Q, ("WICK-SELECT", "C"): Q,
    ("WICK-SELECT", "D"): "judgment (the wick price respects); no exact rule",
    ("PDA-LOOKBACK", "A"): Q,
    ("RANGE-ANCHOR", "A"): Q, ("RANGE-ANCHOR", "B"): Q,
    ("LIQ-LOCATION", "B"): Q, ("LIQ-LOCATION", "C"): Q,
    ("SHORT-LOCATION", "A"): Q,
    ("SMT-USE", "C"): Q, ("SMT-USE", "D"): Q, ("SMT-USE", "E"): Q,
    ("BIAS-SOURCE", "B"): Q, ("BIAS-SOURCE", "C"): Q, ("BIAS-SOURCE", "D"): Q, ("BIAS-SOURCE", "E"): Q,
    ("CONTRACT", "C"): Q, ("CONTRACT", "D"): Q,
    ("CONTRACT", "B"): "back-adjusted prices only for old highs / lows at ATHs and to reveal VIs (front month otherwise): a per-level frame; queued",
    ("VENOM-STOP", "A"): "the Venom model is not in the engine", ("VENOM-STOP", "B"): "the Venom model is not in the engine",
})


# --- stage e: management --------------------------------------------------------------------------------------
_LF = lambda a, b: dict(ladder_fracs=a, ladder_fracs_slow=b)
CARDS.update({
    "PYRAMID-WHERE": {"A": dict(add_cut="eq")},   # Mase's tie pick 2026-11-08: no adds past EQ of the range (E12e)
    "PYRAMID-SIZES": {"A": dict(add_ladder="631")},
    "REENTRY": {
        "A": dict(reentry_half=True, reentry_risk_mult=1.0),
        "B": dict(reentry_half=True, reentry_risk_mult=0.5),
        "C": dict(reentry_half=False, reentry_risk_mult=0.5),
    },
    "MIN-ROOM": {
        "A": dict(min_draw_pts=10.0),
        "B": dict(min_draw_pts=5.0),
        "C": dict(min_draw_pts=7.5),           # [our interpretation] 15 NQ handles ~ 7.5 ES points
    },
    "FIXED-RR": {"A": {}},                     # tie open; A (targets at the draw) is the engine
    "STOP-MGMT": {
        "A": dict(be_on="expansion", trail_wick_ce=False),
        "B": dict(be_on="expansion", trail_wick_ce=True),
        "E": dict(be_on="t1", trail_wick_ce=False),
    },
    "EXIT-DEPTH": {                            # [our interpretation] applied every day (the card's "difficult climate" has no exact rule)
        "A": dict(depth_trail=0.0),            # hold for the full target
        "B": dict(depth_trail=0.75),           # from 75 % of the way to the final rung the stop trails under each closed bar's low (me2._depth_trail)
    },
    "PARTIAL-TRIGGER": {"A": dict(mgmt="t1t2"), "C": dict(mgmt="ladder")},
    "EXIT-STYLE": {
        "A": _LF((1.0,), (1.0,)),
        "B": _LF((0.5, 0.25, 0.25), (0.8, 0.2)),
    },
    "OVERNIGHT-HOLD": {"A": {}},               # tie open; flat by the close is the engine
    "STOP-PLACE": {
        "A": dict(stop_mode="ob_near"),        # the MT of the OB nearest the sweep low
        "B": dict(stop_mode="fvg_candle"),
        "C": dict(stop_mode="fvg_c1_low"),
        "E": dict(stop_mode="wick_ce"),
        "G": dict(stop_mode="ce2"),
    },
    "RESISTANCE-DAY": {
        "A": dict(resistance_mode="off", resist_def="struct", resist_filter=True),
        "B": dict(resistance_mode="high_run", resist_def="off", resist_filter=False),   # high-resistance runs pay at the nearer arrays; wider stops / one contract / no trail: not built
    },
})
SAME_AS_ENGINE.update({
    ("FIXED-RR", "A"): "targets are the draw / PD arrays",
    ("OVERNIGHT-HOLD", "A"): "flat at the session close",
})
NOT_BUILT.update({
    ("PYRAMID-WHERE", "B"): Q, ("PYRAMID-WHERE", "C"): Q, ("PYRAMID-WHERE", "D"): Q,
    ("PYRAMID-SIZES", "B"): Q,
    ("MIN-ROOM", "D"): Q,
    ("FIXED-RR", "B"): Q,
    ("STOP-MGMT", "C"): Q, ("STOP-MGMT", "D"): Q, ("STOP-MGMT", "F"): Q, ("STOP-MGMT", "G"): Q,
    ("STOP-MGMT", "H"): Q, ("STOP-MGMT", "I"): Q, ("STOP-MGMT", "J"): Q, ("STOP-MGMT", "K"): Q,
    ("PARTIAL-TRIGGER", "B"): Q,
    ("EXIT-STYLE", "C"): Q,
    ("OVERNIGHT-HOLD", "B"): Q,
    ("STOP-PLACE", "D"): Q, ("STOP-PLACE", "F"): Q, ("STOP-PLACE", "H"): Q, ("STOP-PLACE", "I"): Q,
    ("RESISTANCE-DAY", "C"): Q,
})


# --- stage f: one-source rules (scorecard/singles.csv; "on" = the draft default) -------------------------------
SINGLES.update({
    ("m2024", "30"): {"on": dict(skip_holiday_eve=True), "off": dict(skip_holiday_eve=False)},   # pre-holiday Friday out; post-holiday AM skip stays (skip_post_holiday_am)
    ("m2024", "41"): {"on": dict(week_done_on_draw="skip"), "off": dict(week_done_on_draw="off")},
    ("m2024", "93"): {"on": dict(or_extra=True), "off": dict(or_extra=False)},                  # the first 30 and 60 minutes both frame the day
})
_SQ = "queued: no engine rule yet; built in the new-concepts stage"
SINGLES_NOT_BUILT.update({
    ("m2024", "89"): "already the engine: London 02:00-05:00 high / low are AM pools and targets (extra_pools)",
    ("m2024", "97"): "already the engine: the release dealing-range wait covers 10:00 releases",
    ("m2026smc", "17"): "IOFED 1 tick past candle 1 is an entry mode (entry='iofed', iofed_ref='tick'); FVG-ENTRY B (CE) is the card default, so it stays a switch",
    ("m2026smc", "83"): "switch only (widest nested ORG); queued",
    ("m2026smc", "19"): "needs a numeric threshold first",
    ("m2025", "17"): "decided with m2026smc 17",
    ("m2026smc", "82"): "a report-only tag (seasonal_tag, no trade change) that adds a bias-table column and rebuilds the bias cache; stays a switch",
})
for _k in [("m2024", "40"), ("m2024", "42"), ("m2024", "43"), ("m2025", "2"), ("m2026smc", "6"), ("m2026smc", "12"),
           ("m2026smc", "28"), ("m2026smc", "29"), ("m2026smc", "30"), ("m2026smc", "49"), ("m2026smc", "67"),
           ("m2026smc", "72"), ("m2024", "65"), ("m2026smc", "92"), ("m2026smc", "101"), ("m2024", "83"), ("m2024", "88"),
           ("m2024", "90"), ("m2024", "91"), ("m2024", "98"), ("m2024", "99"), ("m2024", "103"), ("m2024", "104"),
           ("m2026smc", "108"), ("m2026smc", "115"), ("m2026smc", "116"), ("m2026smc", "117"), ("m2026smc", "119"),
           ("m2025", "13"), ("m2025", "23"), ("m2025", "27"), ("m2025", "29")]:
    SINGLES_NOT_BUILT.setdefault(_k, _SQ)


# review fixes (second-agent review of stages b-f, 2026-11-08)
TAG_ONLY.update({
    "LUNCH-TARGET": "the lunch pool L feeds lunch_raid_wait / lunch_trail_guard (off) and a tag; not yet the lunch-macro target",
    "MACRO-GRID": "the macro windows gate only with macro_gate / macro_only / macro_done_skip (off)",
    "TGIF-DEPTH": "acts only with the TGIF model (tgif_model, off)",
    "TGIF-TIMING": "acts only with the TGIF model (tgif, off)",
})
