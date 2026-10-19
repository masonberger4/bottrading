"""Event dates for 2019-2025, merged into claude_hf.daytypes (which covers 2026) on import.

Release dates come from the BLS archived news release lists (CPI, the employment
situation report with nonfarm payrolls, PPI), read 2026-10-15; FOMC decision days from the
Federal Reserve calendars (2020 includes the 03 March emergency cut). PCE, advance GDP,
retail sales and JOLTS dates are only known for 2026 (NOT YET BUILT for 2019-2025: N5 is PARTIAL - the dealing-range
wait, two_drivers, vacuum blocks and lock times miss those releases before 2026); ISM / PMI are rule-based and the
Conference Board consumer confidence (10:00) is the last Tuesday of the month, for every year.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from claude_hf import daytypes as DT

D = date.fromisoformat

CPI = """2019-01-11 2019-02-13 2019-03-12 2019-04-10 2019-05-10 2019-06-12 2019-07-11 2019-08-13
2019-09-12 2019-10-10 2019-11-13 2019-12-11 2020-01-14 2020-02-13 2020-03-11 2020-04-10 2020-05-12
2020-06-10 2020-07-14 2020-08-12 2020-09-11 2020-10-13 2020-11-12 2020-12-10 2021-01-13 2021-02-10
2021-03-10 2021-04-13 2021-05-12 2021-06-10 2021-07-13 2021-08-11 2021-09-14 2021-10-13 2021-11-10
2021-12-10 2022-01-12 2022-02-10 2022-03-10 2022-04-12 2022-05-11 2022-06-10 2022-07-13 2022-08-10
2022-09-13 2022-10-13 2022-11-10 2022-12-13 2023-01-12 2023-02-14 2023-03-14 2023-04-12 2023-05-10
2023-06-13 2023-07-12 2023-08-10 2023-09-13 2023-10-12 2023-11-14 2023-12-12 2024-01-11 2024-02-13
2024-03-12 2024-04-10 2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13
2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12
2025-09-11 2025-10-24 2025-12-18"""

JOBS = """2019-01-04 2019-02-01 2019-03-08 2019-04-05 2019-05-03 2019-06-07 2019-07-05 2019-08-02
2019-09-06 2019-10-04 2019-11-01 2019-12-06 2020-01-10 2020-02-07 2020-03-06 2020-04-03 2020-05-08
2020-06-05 2020-07-02 2020-08-07 2020-09-04 2020-10-02 2020-11-06 2020-12-04 2021-01-08 2021-02-05
2021-03-05 2021-04-02 2021-05-07 2021-06-04 2021-07-02 2021-08-06 2021-09-03 2021-10-08 2021-11-05
2021-12-03 2022-01-07 2022-02-04 2022-03-04 2022-04-01 2022-05-06 2022-06-03 2022-07-08 2022-08-05
2022-09-02 2022-10-07 2022-11-04 2022-12-02 2023-01-06 2023-02-03 2023-03-10 2023-04-07 2023-05-05
2023-06-02 2023-07-07 2023-08-04 2023-09-01 2023-10-06 2023-11-03 2023-12-08 2024-01-05 2024-02-02
2024-03-08 2024-04-05 2024-05-03 2024-06-07 2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01
2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01
2025-09-05 2025-11-20 2025-12-16"""

PPI = """2019-01-15 2019-02-14 2019-03-13 2019-04-11 2019-05-09 2019-06-11 2019-07-12 2019-08-09
2019-09-11 2019-10-08 2019-11-14 2019-12-12 2020-01-15 2020-02-19 2020-03-12 2020-04-09 2020-05-13
2020-06-11 2020-07-10 2020-08-11 2020-09-10 2020-10-14 2020-11-13 2020-12-11 2021-01-15 2021-02-17
2021-03-12 2021-04-09 2021-05-13 2021-06-15 2021-07-14 2021-08-12 2021-09-10 2021-10-14 2021-11-09
2021-12-14 2022-01-13 2022-02-15 2022-03-15 2022-04-13 2022-05-12 2022-06-14 2022-07-14 2022-08-11
2022-09-14 2022-10-12 2022-11-15 2022-12-09 2023-01-18 2023-02-16 2023-03-15 2023-04-13 2023-05-11
2023-06-14 2023-07-13 2023-08-11 2023-09-14 2023-10-11 2023-11-15 2023-12-13 2024-01-12 2024-02-16
2024-03-14 2024-04-11 2024-05-14 2024-06-13 2024-07-12 2024-08-13 2024-09-12 2024-10-11 2024-11-14
2024-12-12 2025-01-14 2025-02-13 2025-03-13 2025-04-11 2025-05-15 2025-06-12 2025-07-16 2025-08-14
2025-09-10 2025-11-25"""

FOMC = """2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-03-03 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18
2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10"""

HOLIDAYS = """2019-01-01 2019-01-21 2019-02-18 2019-04-19 2019-05-27 2019-07-04 2019-09-02 2019-11-28
2019-12-25 2020-01-01 2020-01-20 2020-02-17 2020-04-10 2020-05-25 2020-07-03 2020-09-07 2020-11-26
2020-12-25 2021-01-01 2021-01-18 2021-02-15 2021-04-02 2021-05-31 2021-07-05 2021-09-06 2021-11-25
2021-12-24 2022-01-17 2022-02-21 2022-04-15 2022-05-30 2022-06-20 2022-07-04 2022-09-05 2022-11-24
2022-12-26 2023-01-02 2023-01-16 2023-02-20 2023-04-07 2023-05-29 2023-06-19 2023-07-04 2023-09-04
2023-11-23 2023-12-25 2024-01-01 2024-01-15 2024-02-19 2024-03-29 2024-05-27 2024-06-19 2024-07-04
2024-09-02 2024-11-28 2024-12-25 2025-01-01 2025-01-09 2025-01-20 2025-02-17 2025-04-18 2025-05-26
2025-06-19 2025-07-04 2025-09-01 2025-11-27 2025-12-25"""


def _dates(s: str) -> set:
    return {D(x) for x in s.split()}


DT.CPI |= _dates(CPI)
DT.JOBS |= _dates(JOBS)
DT.PPI |= _dates(PPI)
DT.FOMC |= _dates(FOMC)
DT.HOLIDAYS |= _dates(HOLIDAYS)
DT.day_type.cache_clear()


# --- trading-day helpers (shared: day_week_context; used by news, targets, exits) ---------
# claude_hf.daytypes.HOLIDAYS carries 2019-2025 (above) plus the 2026 NYSE list incl.
# 2026-12-25 and 2027-01-01, so these helpers are exact through 2026.

def is_trading_day(d: date) -> bool:
    return DT.is_trading_day(d)


def next_trading_day(d: date, n: int = 1) -> date:
    """The n-th NYSE trading day after d (holidays skipped; n < 0 walks back)."""
    return DT._step(d, n)


def prev_trading_day(d: date, n: int = 1) -> date:
    return DT._step(d, -n)


def last_n_trading_days(year: int, n: int) -> list[date]:
    """The last n trading days of `year`, oldest first, walking back from Dec 31."""
    d, out = date(year, 12, 31), []
    while len(out) < n:
        if is_trading_day(d):
            out.append(d)
        d = date.fromordinal(d.toordinal() - 1)
    return out[::-1]


def last_trading_day_of_year(d: date) -> bool:
    """True if d is the last trading day of its year."""
    return is_trading_day(d) and last_n_trading_days(d.year, 1)[0] == d


# --- release times (owner directive #4; N5, N5.2, Ep02.1) ---------------------------------
# PCE, GDP, retail sales and JOLTS dates exist for 2026 only (N5 PARTIAL before 2026) (claude_hf.daytypes); ISM, PMI
# and sentiment are rule-based (ISM manufacturing = 1st trading day, services = 3rd; S&P
# Global final PMIs come out at 09:45 on the same days; flash PMI dates are not available).
NEWS_0830 = {"cpi", "jobs", "ppi", "pce", "retail_sales", "gdp"}
NEWS_0945 = {"pmi_mfg", "pmi_svc"}
NEWS_1000 = {"ism_manufacturing", "ism_services", "jolts", "sentiment", "conf_board"}
PMI = NEWS_0945                                       # Ep02.1: the 'pmi' event set


def pmi_events(d: date) -> set:
    tags = set()
    if d == DT.nth_trading_day(d.year, d.month, 1):
        tags.add("pmi_mfg")
    if d == DT.nth_trading_day(d.year, d.month, 3):
        tags.add("pmi_svc")
    return tags


# --- news_calendar_times: the minor releases (N5), derived from the rules ----------------------
@lru_cache(maxsize=None)
def is_jobless_claims(d: date) -> bool:
    """Initial jobless claims: every Thursday 08:30; on the Wednesday before when that Thursday
    is a market holiday (Thanksgiving, July 4 and Juneteenth on a Thursday). Derived from the
    NYSE holiday list (claude_hf.daytypes.HOLIDAYS), 2019-2026."""
    if d.weekday() == 3:
        return d not in DT.HOLIDAYS
    if d.weekday() == 2:
        return (d + timedelta(days=1)) in DT.HOLIDAYS
    return False


def _minutes_dates() -> set:
    # FOMC minutes: 14:00 on the Wednesday three weeks (21 days) after the decision; the
    # unscheduled 2020-03-03 cut has none (its follow-up is the 03-15 emergency meeting).
    return {d + timedelta(days=21) for d in DT.FOMC if d != date(2020, 3, 3)
            and (d + timedelta(days=21)) not in DT.HOLIDAYS}


FOMC_MINUTES = _minutes_dates()

# Fed chair testimony / speeches at 10:00 (N5.5; 037 ~3:09; 038 ~39:59; 067 ~0:34): the semi-annual
# monetary-policy testimony to Congress (two days: one chamber each). [UNVERIFIED - typed from
# memory of the public record, 2019-2025; 2026 unknown. Extend or correct before relying on it.]
FED_CHAIR = _dates("""2019-02-26 2019-02-27 2019-07-10 2019-07-11 2020-02-11 2020-02-12 2020-06-16 2020-06-17
2021-02-23 2021-02-24 2021-07-14 2021-07-15 2022-03-02 2022-03-03 2022-06-22 2022-06-23 2023-03-07
2023-03-08 2023-06-21 2023-06-22 2024-03-06 2024-03-07 2024-07-09 2024-07-10 2025-02-11 2025-02-12
2025-06-24 2025-06-25""")
FED_CHAIR_EXTRA: set = set()                          # a place for the owner's own dates

# Treasury note / bond auctions (N5.6; cc10_008 ~7:29 "bond auction days": the AM consolidates).
# [our interpretation] The quarterly-refunding style 3-, 10- and 30-year auctions fall on the
# Tuesday / Wednesday / Thursday of the week holding the second Wednesday of the month (13:00 ET);
# a holiday shifts a day. Exact dates differ in some months - AUCTION_EXTRA adds / AUCTION_SKIP removes.
AUCTION_EXTRA: set = set()
AUCTION_SKIP: set = set()


# [our interpretation] Explicit auction list overlay: AUCTIONS holds known 13:00 ET auction dates (month-end 2-, 5-,
# 7-year, 20-year, TIPS ...) that the 3 / 10 / 30-year rule below does not cover; none is built in (the owner can
# add dates). is_auction_day reads the sets on every call (no cache), so edits take effect at once.
AUCTIONS: set = set()


def is_auction_day(d: date) -> bool:
    if d in AUCTION_SKIP:
        return False
    if d in AUCTION_EXTRA or d in AUCTIONS:
        return True
    if d.weekday() not in (1, 2, 3) or not DT.is_trading_day(d):
        return False
    wed = date(d.year, d.month, 8)
    wed += timedelta(days=(2 - wed.weekday()) % 7)              # the second Wednesday
    if wed.month != d.month:
        return False
    return abs((d - wed).days) <= 1


def is_consumer_confidence(d: date) -> bool:
    """Conference Board consumer confidence (10:00): the last Tuesday of the month. [our interpretation]
    rule-based for every year (the Conference Board's calendar is this rule, a holiday shifting it rarely)."""
    if d.weekday() != 1 or not DT.is_trading_day(d):
        return False
    return (d + timedelta(days=7)).month != d.month


def minor_events(d: date) -> set:
    """Tags of the minor scheduled releases on d: claims (08:30), minutes (14:00), conf_board (10:00)."""
    out = set()
    if is_consumer_confidence(d):
        out.add("conf_board")
    if is_jobless_claims(d):
        out.add("claims")
    if d in FOMC_MINUTES:
        out.add("minutes")
    return out


def release_times(d: date, claims: bool = False, minutes: bool = False, pmi: bool = True, conf: bool = False) -> list[int]:
    """Scheduled release minutes (ET) on day d, sorted: 510 (08:30 data), 585 (09:45 PMI),
    600 (10:00 data), 840 (FOMC decision). claims adds the 08:30 jobless claims, minutes the
    14:00 FOMC minutes (both off by default - low impact); pmi=False drops the 09:45 PMI; conf adds the 10:00 Conference Board consumer confidence (off by default)."""
    tags = DT.events(d) | pmi_events(d)
    mn = minor_events(d)
    tags |= {t for t in mn if (t == "claims" and claims) or (t == "minutes" and minutes) or (t == "conf_board" and conf)}
    out = []
    if tags & NEWS_0830 or "claims" in tags:
        out.append(510)
    if pmi and tags & NEWS_0945:
        out.append(585)
    if tags & NEWS_1000:
        out.append(600)
    if "fomc" in tags or "minutes" in tags:
        out.append(840)
    return out


# --- NFP week helpers (the verified blocked() bug: NFP is not always a Friday) -------------
@lru_cache(maxsize=None)
def nfp_date(d: date):
    """The employment-situation release in d's Monday-Friday week, or None (2025-07-03 was a
    Thursday; 2025-11-20 and 2025-12-16 were shifted by the shutdown)."""
    mon = d - timedelta(days=d.weekday())
    for k in range(5):
        x = mon + timedelta(days=k)
        if x in DT.JOBS:
            return x
    return None


def nfp_shift(d: date) -> int:
    """Days the week's NFP sits before a Friday (0 Friday, 1 Thursday), or -1 when the week has
    no NFP or it is not on Thu / Fri (then the beginner NFP-week blocks do not apply)."""
    n = nfp_date(d)
    if n is None or n.weekday() not in (3, 4):
        return -1
    return 4 - n.weekday()


@lru_cache(maxsize=None)
def fomc_info(d: date) -> dict:
    """FOMC context of d: fomc (the decision day), eve (the next trading day is one), after (the
    previous trading day was one), only (the decision is the day's only scheduled release)."""
    fo = "fomc" in DT.events(d)
    nxt, prv = next_trading_day(d), prev_trading_day(d)
    return dict(fomc=fo, eve="fomc" in DT.events(nxt), after="fomc" in DT.events(prv),
                only=fo and release_times(d) == [840])


@lru_cache(maxsize=None)
def eve_of(d: date, tag: str) -> bool:
    """The next trading day carries event `tag` (cpi / jobs / fomc ...)."""
    return tag in DT.events(next_trading_day(d))


@lru_cache(maxsize=None)
def two_drivers(d: date, claims: bool = False, conf: bool = False) -> bool:
    """Two scheduled morning releases (08:30 data and a 09:45 / 10:00 one, or 09:45 and 10:00 - the
    PMI and ISM pair counts as one driver). N5.4 (100 ~50:59-1:40:56)."""
    rt = [r for r in release_times(d, claims=claims, conf=conf) if r < 840]
    return (510 in rt and any(r in rt for r in (585, 600)))
