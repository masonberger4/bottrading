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
