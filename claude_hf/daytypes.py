"""What kind of day it is: scheduled macro events, expirations, and month/quarter turns.

Release dates are the official 2026 schedules, after the post-shutdown reshuffle: BLS (CPI,
jobs report with nonfarm payrolls and the unemployment rate, PPI, JOLTS), BEA (PCE in
personal income and outlays, advance GDP), Census (retail sales) and the Fed (FOMC, decision
at 14:00 ET on the meeting's second day). ISM dates follow ISM's fixed rule (manufacturing
on the first business day, services on the third). The University of Michigan doesn't
publish its calendar in a fetchable form, so its preliminary sentiment read is approximated
as the second Friday. Extend the sets each year.
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
PPI = {D(x) for x in ("2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18", "2026-04-14",
                      "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10",
                      "2026-10-15", "2026-11-13", "2026-12-15")}
PCE = {D(x) for x in ("2026-02-20", "2026-03-13", "2026-04-09", "2026-05-05", "2026-06-09",
                      "2026-07-07", "2026-08-04", "2026-09-03", "2026-10-06", "2026-11-04",
                      "2026-12-02", "2026-12-23")}
GDP = {D(x) for x in ("2026-02-20", "2026-04-30", "2026-07-30", "2026-10-29")}   # advance reads
RETAIL = {D(x) for x in ("2026-04-01", "2026-04-21", "2026-05-14", "2026-06-17", "2026-07-16",
                         "2026-08-14", "2026-09-16")}
JOLTS = {D(x) for x in ("2026-01-07", "2026-02-05", "2026-03-13", "2026-03-31", "2026-05-05",
                        "2026-06-02", "2026-06-30", "2026-08-04", "2026-09-01", "2026-09-29",
                        "2026-11-03", "2026-12-01")}
FOMC = {D(x) for x in ("2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
                       "2026-09-16", "2026-10-28", "2026-12-09")}
HOLIDAYS = {D(x) for x in ("2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
                           "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
                           "2027-01-01")}

# Day types in priority order, roughly by how much they usually move stocks: a day carries
# the first one that applies. A strategy routes each type to playbook A, playbook B, or
# sits the day out. "jobs" is the Employment Situation: nonfarm payrolls + unemployment.
EVENTS = ("fomc", "cpi", "jobs", "pce", "ppi", "retail_sales", "gdp", "quad_witching",
          "ism_manufacturing", "ism_services", "jolts", "sentiment", "opex")
DAY_TYPES = EVENTS + ("quarter_end", "month_end", "quarter_start", "month_start", "roll_week",
                      "mon", "tue", "wed", "thu", "fri")
WEEKDAYS = DAY_TYPES[-5:]


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


def nth_trading_day(year: int, month: int, n: int) -> date:
    return _step(date(year, month, 1) - timedelta(days=1), n)


def second_friday(year: int, month: int) -> date:
    d = date(year, month, 8)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def events(d: date) -> set:
    """Every event on day d (several can coincide)."""
    exp = expiration(d.year, d.month)
    quarterly = d.month in (3, 6, 9, 12)
    tags = {name for name, days in (("fomc", FOMC), ("cpi", CPI), ("jobs", JOBS), ("pce", PCE),
                                     ("ppi", PPI), ("retail_sales", RETAIL), ("gdp", GDP),
                                     ("jolts", JOLTS)) if d in days}
    if d == exp:
        tags.add("quad_witching" if quarterly else "opex")
    if d == nth_trading_day(d.year, d.month, 1):
        tags.add("ism_manufacturing")
    if d == nth_trading_day(d.year, d.month, 3):
        tags.add("ism_services")
    if d == second_friday(d.year, d.month):
        tags.add("sentiment")
    return tags


@lru_cache(maxsize=None)
def day_type(d: date) -> str:
    tags = events(d)
    for e in EVENTS:
        if e in tags:
            return e
    exp = expiration(d.year, d.month)
    quarterly = d.month in (3, 6, 9, 12)
    nxt, prv = _step(d, 1), _step(d, -1)
    if nxt.month != d.month or _step(d, 2).month != d.month:     # last two trading days
        return "quarter_end" if quarterly else "month_end"
    if prv.month != d.month or _step(d, -2).month != d.month:    # first two trading days
        return "quarter_start" if d.month in (1, 4, 7, 10) else "month_start"
    if quarterly and exp - timedelta(days=11) <= d < exp:        # index futures roll period
        return "roll_week"
    return WEEKDAYS[d.weekday()]
