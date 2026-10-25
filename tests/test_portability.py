"""Platform / library-version independence of things the tests rely on."""
import math

import numpy as np

from mentorship import levels as L


def test_zone_equality_with_nan_mean_threshold():
    a = L.Zone("bull", 12.0, 11.0, 2, 1)                                   # default mt = NaN
    b = L.Zone("bull", np.float64(12.0), 11.0, 2, 1, float("nan"))          # a different NaN object
    assert a == b and hash(a) == hash(b) and len({a, b}) == 1
    assert a != L.Zone("bear", 12.0, 11.0, 2, 1)
    assert L.Zone("bull", 12.0, 11.0, 2, 1, 11.5) != a
    assert math.isnan(a.mt)


def test_zone_membership_unchanged():
    zs = [L.Zone("bull", 12.0, 11.0, 2, 1), L.Zone("bull", 14.0, 13.0, 5, 4)]
    assert L.Zone("bull", 14.0, 13.0, 5, 4, np.nan) in zs
    assert L.Zone("bear", 14.0, 13.0, 5, 4) not in zs
