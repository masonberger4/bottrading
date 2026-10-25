"""Caption-gap pass, entries_stops_sizing #2/3, round 2 review fixes: the Friday shallow entry (breaker edge, Thursday keeps the default) and the market-order dead-gap multiple. Hand-made bars only."""
from types import SimpleNamespace

import pandas as pd
import pytest

from mentorship import es2, levels as L
from mentorship.strategy import Params

from test_caption_gap_sm1a import sd_of

ROWS = [(100.0, 100.5, 99.5, 100.2), (100.2, 100.4, 99.0, 99.1), (99.1, 100.9, 99.0, 100.8), (100.8, 102.0, 100.7, 101.9), (101.9, 103.0, 101.8, 102.9)]
SW = dict(ext_i=1, ext=99.0)


def _ctx(day):
    return SimpleNamespace(day=pd.Timestamp(day).date(), cur_lock=dict(side=1, target=104.0))


def test_fri_shallow_breaker_edge_and_thursday_default():
    sd = sd_of(ROWS)
    g = L.Zone("bull", 100.0, 99.2, 2, 1, float("nan"))
    bz = L.Zone("bull", 101.0, 100.2, 1, 1, float("nan"))
    fri, thu = _ctx("2026-06-26"), _ctx("2026-06-25")            # a Friday / a Thursday; leg 4.0 > the draw distance 1.1
    pf = Params(es_pt=1.0, fri_shallow=True)
    pb = Params(es_pt=1.0, fri_shallow=True, fri_shallow_edge="breaker")
    assert es2.fri_shallow_pick(fri, sd, SW, [g], 4, pf, bz) is g                      # fvg: the first gap of the leg
    assert es2.fri_shallow_pick(fri, sd, SW, [g], 4, pb, bz) is bz                     # breaker: its upper edge
    assert es2.fri_shallow_pick(fri, sd, SW, [g], 4, pb, None) is g                    # no breaker: the FVG
    assert es2.fri_shallow_pick(thu, sd, SW, [g], 4, pb, bz) is None                   # Thursday keeps the default entry
    assert es2.fri_shallow_pick(thu, sd, SW, [g], 4, pf, bz) is None
    with pytest.raises(ValueError):
        Params(fri_shallow_edge="x")


def test_mot_dead_mult():
    sd = sd_of([(100.0, 100.4, 99.6, 100.3), (100.3, 100.5, 99.0, 99.5), (101.2, 101.8, 101.0, 101.6), (101.6, 101.7, 101.0, 101.2)])
    o = dict(i=0, entry=99.0, stop=98.5, mot=True)                                   # planned risk 0.5; the open (101.2) lies 2.2 over the entry
    assert es2.convert_pending(o, sd, 2, Params(es_pt=1.0)).get("es2_dead") is True
    assert es2.convert_pending(o, sd, 2, Params(es_pt=1.0, mot_dead_mult=5.0)).get("market") is True
    with pytest.raises(ValueError):
        Params(mot_dead_mult=0)
