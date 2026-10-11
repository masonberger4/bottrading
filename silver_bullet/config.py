"""Instrument specs and strategy parameters for the ICT Silver Bullet model.

All prices are in instrument points. For index futures one "handle" is one point
(ES/MES: 4 ticks of 0.25). For SPY, one SPY point is roughly ten ES points, so the
SPY preset scales the 10-handle framework and 5-handle target down by 10x.
"""
from dataclasses import dataclass, field, replace
from datetime import time


@dataclass(frozen=True)
class Instrument:
    symbol: str
    tick_size: float
    point_value: float          # dollars per 1.0 point per contract (or per share x qty)
    commission_per_side: float  # dollars per contract (or per order for equities)
    default_qty: int = 1
    is_future: bool = True


INSTRUMENTS = {
    "ES":  Instrument("ES", 0.25, 50.0, 2.25),
    "MES": Instrument("MES", 0.25, 5.0, 0.62),
    "NQ":  Instrument("NQ", 0.25, 20.0, 2.25),
    "MNQ": Instrument("MNQ", 0.25, 2.0, 0.62),
    # SPY: point_value 1.0 per share; qty 100 shares ~ 2 MES contracts of exposure.
    "SPY": Instrument("SPY", 0.01, 1.0, 0.0, default_qty=100, is_future=False),
    "QQQ": Instrument("QQQ", 0.01, 1.0, 0.0, default_qty=100, is_future=False),
}


@dataclass(frozen=True)
class Window:
    name: str
    start: time
    end: time


# The three Silver Bullet windows, New York local time (DST-aware via tz conversion).
WINDOWS = (
    Window("London", time(3, 0), time(4, 0)),
    Window("AM", time(10, 0), time(11, 0)),
    Window("PM", time(14, 0), time(15, 0)),
)


@dataclass(frozen=True)
class Params:
    # Framework: the draw on liquidity must sit at least this far from the entry.
    min_framework_pts: float = 10.0
    # Profit target. "fixed" books target_pts; "draw" exits at the liquidity level itself.
    target_mode: str = "fixed"
    target_pts: float = 5.0
    # Stop goes just beyond the swing that started the displacement leg.
    stop_buffer_ticks: int = 2
    max_stop_pts: float = 10.0
    min_stop_pts: float = 1.0
    # Swing pivots: a swing high needs `swing_len` lower highs on each side.
    swing_len: int = 2
    # Which windows to trade.
    windows: tuple = ("London", "AM", "PM")
    # "auto" trades whichever way structure shifts; "long"/"short" imposes your own bias.
    bias: str = "auto"
    # Also treat today's unswept intraday swing points as draws (not just session highs/lows).
    include_swing_levels: bool = False
    max_trades_per_window: int = 1
    # Everything is flat by this time (NY). London trades can ride into the NY session.
    flat_time: time = time(15, 55)
    # Costs (on top of commission): adverse ticks on stop / market exits.
    slippage_ticks: int = 1
    # A limit target only fills if price trades through it by this many ticks.
    target_through_ticks: int = 0


def params_for(symbol: str, **overrides) -> Params:
    """Default params scaled to the instrument."""
    p = Params()
    if symbol in ("SPY",):
        p = replace(p, min_framework_pts=1.0, target_pts=0.5, max_stop_pts=1.0,
                    min_stop_pts=0.10, windows=("AM", "PM"))
    elif symbol in ("QQQ",):
        p = replace(p, min_framework_pts=2.5, target_pts=1.25, max_stop_pts=2.5,
                    min_stop_pts=0.20, windows=("AM", "PM"))
    elif symbol in ("NQ", "MNQ"):
        # NQ moves ~3.5x ES in points.
        p = replace(p, min_framework_pts=35.0, target_pts=17.5, max_stop_pts=35.0, min_stop_pts=4.0)
    return replace(p, **overrides)
