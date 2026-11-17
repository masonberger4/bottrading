"""Stop-side guard (Mase 2026-11-17; PR #95 finding): an order whose fill price is at or beyond its own stop is
cancelled, not filled. Without it the "stop" is hit at once at a profit (ob_arm='touch': 1,168 such trades, +861 R)."""
from test_entries_stops import scen_a
from test_review_fixes import A_ROWS
from mentorship.strategy import Params


def gap(open_):
    r = list(A_ROWS)
    o, h, l, c = r[2]
    r[2] = (open_, h, min(l, open_), c)              # the 09:40 bar opens lower: the resting limit fills at that open
    return r


def test_guard_is_on_by_default():
    assert Params().fill_stop_guard is True


def test_fill_above_the_stop_is_unchanged():
    a, b = scen_a(rows=gap(98.6), ob_arm="touch"), scen_a(rows=gap(98.6), ob_arm="touch", fill_stop_guard=False)
    assert a == b and a[0].entry == 98.6 and a[0].entry > a[0].stop


def test_fill_past_the_stop_is_cancelled():
    old = scen_a(rows=gap(98.2), ob_arm="touch", fill_stop_guard=False)[0]
    assert old.entry == 98.2 and old.stop == 98.25             # the old behaviour: long filled UNDER its own stop
    new = scen_a(rows=gap(98.2), ob_arm="touch")
    assert all(t.entry > t.stop for t in new)                  # no trade with the stop on the profit side
    assert not any(str(t.entry_time)[11:16] == "09:40" for t in new)   # that fill is gone
