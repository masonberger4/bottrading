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


def variants() -> dict[str, dict]:
    """Every non-default built position as a study.DECISIONS variant (overrides over Params())."""
    d, pend = card_defaults(), pending_ties()
    out: dict[str, dict] = {}
    for card, ps in CARDS.items():
        base = None if card in pend else ps.get(d[card])
        for pos, kw in ps.items():
            if (pos != d[card] or card in pend) and kw and kw != base:
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
        "A": dict(pre_0700=False, pre_0900=False),
        "B": dict(pre_0700=True, pre_0900=True),
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
    "FED-SPEECH": {                            # tie open: the engine keeps trading the AM until Mase picks
        "A": dict(fed_chair_skip_am=True),
    },
    "MONDAY": {                                # tie open
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
        "A": dict(holiday_week_skip=False, holiday_week_thu_fri="off"),
        "B": dict(holiday_week_skip=True, holiday_week_thu_fri="off"),
        "C": dict(holiday_week_skip=False, holiday_week_thu_fri="trade"),
    },
    "TGIF-DEPTH": {                            # acts with the TGIF model (tgif_model, off by default)
        "A": dict(tgif_cap=0.30, tgif_stand_down=0.40),
        "B": dict(tgif_cap=0.40, tgif_stand_down=0.45),   # [our interpretation] up to 40%
    },
    "TGIF-TIMING": {"A": {}},
    "WEEK-PROFILE": {                          # C: Thursday caps the week (N10 thu_cap)
        "C": dict(thu_cap=True),
        "A": dict(thu_cap=False),              # [our interpretation] no Thursday cap; the Tue/Wed low is the wk_profile tag
    },
})
SAME_AS_ENGINE.update({
    ("NEWS-WAIT", "H"): "the release dealing range applies to 10:00 releases too",
    ("RANGE-REGIME", "B"): "continuation through the break is the engine's default",
    ("TGIF-TIMING", "A"): "TGIF is a Friday model in the engine",
})
NOT_BUILT.update({
    ("NEWS-WAIT", "E"): "fade the release's first leg on range-bound days after 10:00: no range-day release fade yet; queued",
    ("NEWS-WAIT", "G"): Q,
    ("FOMC-DAY", "A"): "an FOMC AM cut-off at 10:30 is not built; queued",
    ("FOMC-DAY", "D"): "beginner version (avoid FOMC day); experienced default stands",
    ("FED-SPEECH", "B"): Q, ("FED-SPEECH", "C"): Q,
    ("MONDAY", "C"): "Monday pre-market only needs a per-day session list; queued",
    ("CPI-WEEK", "B"): Q,
    ("AFTER-BIG-DAY", "C"): "'keep expectations low' has no exact rule",
    ("TWO-SIDED", "A"): Q, ("TWO-SIDED", "B"): Q,
    ("RANGE-REGIME", "A"): Q,
    ("SEASON-ACTIVITY", "C"): Q,
    ("HOLIDAY-WEEK", "D"): Q,
    ("TGIF-DEPTH", "C"): Q,
    ("TGIF-TIMING", "B"): Q, ("TGIF-TIMING", "C"): Q,
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
    "SMT-USE": {"A": dict(smt_partial="off"), "B": dict(smt_partial="a")},
    "SMT-SET": {"A": dict(smt_ym=True), "B": dict(smt_ym=False)},
    "BIAS-SOURCE": {"A": {}},
    "CONTRACT": {                              # tie open: the engine keeps front-month prices
        "A": dict(price_frame="front_month"),
        "B": dict(price_frame="back_adjusted"),
    },
    "FVG-ENTRY": {"A": dict(entry="edge"), "B": dict(entry="ce")},
})
SAME_AS_ENGINE.update({
    ("UNICORN", "A"): "the engine's unicorn is an FVG inside a breaker",
    ("LIQ-LOCATION", "A"): "the engine's pools are wick extremes and relative equal highs / lows",
    ("SHORT-LOCATION", "B"): "the engine has no deep-discount short block",
    ("BIAS-SOURCE", "A"): "the engine's bias is the HTF draw (daily table) that intraday trades follow",
})
NOT_BUILT.update({
    ("OB-CANDLE", "C"): Q, ("OB-CLOSE", "A"): Q, ("OB-CLOSE", "B"): Q,
    ("IFVG-CONFIRM", "C"): Q, ("IFVG-CONFIRM", "D"): "anticipation from structure is judgment; no exact rule yet",
    ("UNICORN", "B"): "market maker model stages are not built", ("UNICORN", "C"): Q,
    ("FVG-VALID", "A"): Q, ("FVG-VALID", "B"): Q, ("FVG-VALID", "C"): Q, ("FVG-VALID", "D"): Q,
    ("WICK-PRIORITY", "A"): Q, ("WICK-PRIORITY", "B"): Q,
    ("TF-CHOP", "A"): Q, ("TF-CHOP", "B"): "sub-1m entries; the engine runs 1m / 5m bars",
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
    ("ATH-RULE", "A"): Q, ("ATH-RULE", "B"): Q, ("ATH-RULE", "C"): Q,
    ("CONTRACT", "C"): Q, ("CONTRACT", "D"): Q,
    ("VENOM-STOP", "A"): "the Venom model is not in the engine", ("VENOM-STOP", "B"): "the Venom model is not in the engine",
})
