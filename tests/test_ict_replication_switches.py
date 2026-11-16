"""ICT video-trade replication switches (2026-11-16): session_trades and mss_on_fvg. Both default to the built behaviour."""
import pytest
from mentorship.strategy import Params


def test_defaults_keep_built_behaviour():
    p = Params()
    assert p.session_trades == 1 and p.mss_on_fvg is False


def test_session_trades_validation():
    with pytest.raises(ValueError):
        Params(session_trades=0)
    assert Params(session_trades=4).session_trades == 4

