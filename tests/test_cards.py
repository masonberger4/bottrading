"""Scorecard cards built into the engine (mentorship/cards.py)."""
from dataclasses import fields, replace

import pytest

from mentorship import cards as C
from mentorship.strategy import Params

DEF = C.card_defaults()
POS = C.card_positions()
PEND = C.pending_ties()
P0 = Params()
FIELDS = {f.name for f in fields(Params)}


def test_cards_are_scorecard_cards():
    assert set(C.CARDS) <= set(DEF)
    for card, ps in C.CARDS.items():
        assert set(ps) <= set(POS[card]), card


def test_every_position_accounted_for():
    """A card in CARDS lists every scorecard position: built, same as engine, or not built (with a reason)."""
    for card, ps in C.CARDS.items():
        for pos in POS[card]:
            assert pos in ps or (card, pos) in C.NOT_BUILT, (card, pos)
            if pos in ps and pos != DEF[card] and card not in PEND and ps[pos] == ps.get(DEF[card]):
                assert (card, pos) in C.SAME_AS_ENGINE, (card, pos)     # the default already does it
            if pos in ps and not ps[pos]:
                assert (card, pos) in C.SAME_AS_ENGINE, (card, pos)
    for (card, pos), why in C.NOT_BUILT.items():
        assert why and pos not in C.CARDS.get(card, {}), (card, pos)


def test_positions_set_the_same_keys():
    for card, ps in C.CARDS.items():
        keys = {k for kw in ps.values() for k in kw}
        for pos, kw in ps.items():
            assert set(kw) <= FIELDS, (card, pos, set(kw) - FIELDS)
            assert set(kw) == keys, (card, pos, keys ^ set(kw))


def test_default_position_is_params_default():
    for card, ps in C.CARDS.items():
        if card in PEND:
            continue                       # tie open: the engine keeps its behaviour, every position a switch
        for k, v in ps.get(DEF[card], {}).items():
            assert getattr(P0, k) == v, (card, k, getattr(P0, k), v)
    for key, ps in C.SINGLES.items():
        for k, v in ps["on"].items():
            assert getattr(P0, k) == v, (key, k, getattr(P0, k), v)


def test_no_two_defaults_disagree():
    seen = {}
    for card, ps in C.CARDS.items():
        if card in PEND:
            continue
        for k, v in ps.get(DEF[card], {}).items():
            assert seen.setdefault(k, (card, v))[1] == v, (k, seen[k], card)


def test_variants_differ_from_defaults_and_build():
    for name, kw in C.variants().items():
        p = replace(P0, **kw)
        if name.startswith("SC-") and name.split("-", 1)[1].rsplit("-", 1)[0] in PEND:
            continue                       # a pending tie's engine-matching position is listed too
        assert any(getattr(p, k) != getattr(P0, k) for k in kw), name


def test_singles_keys_match():
    st = C.singles_status()
    for key, ps in C.SINGLES.items():
        assert key in st and st[key] != "excluded", key
        assert set(ps) == {"on", "off"} and set(ps["on"]) == set(ps["off"]) and ps["on"] != ps["off"], key


def test_variants_registered_in_study():
    from mentorship import study
    for name in C.variants():
        assert name in study.DECISIONS, name


def test_every_single_accounted_for():
    st = C.singles_status()
    for key, status in st.items():
        if status in ("excluded", "agrees"):
            continue
        assert key in C.SINGLES or key in C.SINGLES_NOT_BUILT, key


def test_every_card_accounted_for():
    for card in DEF:
        for pos in POS[card]:
            assert pos in C.CARDS.get(card, {}) or (card, pos) in C.NOT_BUILT, (card, pos)
