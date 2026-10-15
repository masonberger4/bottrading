"""What kind of day it is: scheduled macro events, expirations, and month/quarter turns.

Dates are from the official 2026 schedules (BLS for CPI and jobs at 08:30 ET; the Fed for
FOMC, decision at 14:00 ET on the meeting's second day). Extend the sets each year.
Expirations are computed: monthly equity options expire the third Friday, and the third
Friday of Mar/Jun/Sep/Dec is quad witching, when index futures and their options expire too
(moved to the prior trading day when that Friday is a market holiday, as in June 2026).
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

D = date.fromisoformat
CPI = {D(x) for x in ("2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12",
                      "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14",
                      "2026-11-10", "2026-12-10")}
JOBS = {D(x) for x in ("2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08",
                       "2026-06-05", "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02",
                       "2026-11-06", "2026-12-04")}
FOMC = {D(x) for x in ("2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
                       "2026-09-16", "2026-10-28", "2026-12-09")}
HOLIDAYS = {D(x) for x in ("2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
                           "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
                           "2027-01-01")}

# Day types in priority order: a day carries the first one that applies. A strategy routes
# each type to its normal playbook, its event playbook, or sits the day out.
DAY_TYPES = ("fomc", "cpi", "jobs", "quad_witching", "opex", "quarter_end", "month_end",
             "quarter_start", "month_start", "roll_week", "mon", "tue", "wed", "thu", "fri")


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def _step(d: date, n: int) -> date:
    """The n-th trading day after (n > 0) or before (n < 0) d."""
    s = 1 if n > 0 else -1
    while n:
        d += timedelta(days=s)
        if is_trading_day(d):
            n -= s
    return d


def expiration(year: int, month: int) -> date:
    d = date(year, month, 15)
    d += timedelta(days=(4 - d.weekday()) % 7)          # third Friday
    return d if is_trading_day(d) else _step(d, -1)


@lru_cache(maxsize=None)
def day_type(d: date) -> str:
    exp = expiration(d.year, d.month)
    quarterly = d.month in (3, 6, 9, 12)
    if d in FOMC:
        return "fomc"
    if d in CPI:
        return "cpi"
    if d in JOBS:
        return "jobs"
    if d == exp:
        return "quad_witching" if quarterly else "opex"
    nxt, prv = _step(d, 1), _step(d, -1)
    if nxt.month != d.month or _step(d, 2).month != d.month:     # last two trading days
        return "quarter_end" if quarterly else "month_end"
    if prv.month != d.month or _step(d, -2).month != d.month:    # first two trading days
        return "quarter_start" if d.month in (1, 4, 7, 10) else "month_start"
    if quarterly and exp - timedelta(days=11) <= d < exp:        # index futures roll period
        return "roll_week"
    return DAY_TYPES[10 + d.weekday()]
