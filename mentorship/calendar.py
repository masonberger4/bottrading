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


# --- coverage gap 1: the news calendar source (Params.news_cal; build spec coverage_build_2026-10-31 package 1) --------
# NYSE full closures 2016-2018 (2018-12-05: the Bush mourning closure). Calendar facts, added for both sources (the
# legacy event lists start in 2019, so nothing from 2019 on changes).
HOLIDAYS_2016_18 = _dates("""2016-01-01 2016-01-18 2016-02-15 2016-03-25 2016-05-30 2016-07-04 2016-09-05 2016-11-24 2016-12-26
2017-01-02 2017-01-16 2017-02-20 2017-04-14 2017-05-29 2017-07-04 2017-09-04 2017-11-23 2017-12-25 2018-01-01 2018-01-15
2018-02-19 2018-03-30 2018-05-28 2018-07-04 2018-09-03 2018-11-22 2018-12-05 2018-12-25""")
DT.HOLIDAYS |= HOLIDAYS_2016_18
DT.day_type.cache_clear()

EV_KEYS = ("fomc", "cpi", "jobs", "pce", "ppi", "retail_sales", "gdp", "jolts")
EV: dict = {k: set() for k in EV_KEYS}        # the mentorship-owned event sets (claude_hf.daytypes is never mutated by the source switch); refilled IN PLACE by use()
JOBS_SET = EV["jobs"]                          # (modules import the set object itself)
TIMES: dict = {}                               # csv source: {date: {event: release minute ET}} from the file's time_et column
CSV_DEFAULT = "data/mentorship/macro_risk_dates.csv"
CSV_MAP = {"cpi": ("cpi",), "jobs": ("nfp",), "fomc": ("fomc",), "pce": ("pce",), "retail_sales": ("retail",), "jolts": ("jolts",), "ppi": ("ppi",)}
_ACTIVE: list = [None]


@lru_cache(maxsize=4)
def load_csv(path: str) -> dict:
    """macro_risk_dates.csv (columns date,time_et,event,tag,...; `#` lines skipped) -> {tag: {date: minute or None}} (a blank time = a date-only tag)."""
    import csv
    out: dict = {}
    with open(path, newline="", encoding="utf8") as f:
        rows = csv.DictReader(line for line in f if not line.startswith("#"))
        for r in rows:
            t = (r.get("time_et") or "").strip()
            m = int(t[:2]) * 60 + int(t[3:5]) if (len(t) == 5 and t[2] == ":") else None     # ("notation" / "unscheduled" FOMC rows: no time)
            out.setdefault(r["tag"].strip(), {})[D(r["date"].strip())] = m
    return out


def _clear_caches() -> None:
    for f in (DT.day_type, is_jobless_claims, nfp_date, fomc_info, eve_of, two_drivers, day_type):
        f.cache_clear()


def use(source: str = "csv", path: str = CSV_DEFAULT, gdp_tags: tuple = ("gdp_adv",)) -> str:
    """Select the event calendar (Params.news_cal): "csv" = macro_risk_dates.csv (2016 on; PPI adds the built 2019+ list; GDP = `gdp_tags`) /
    "legacy" = the built 2019-2025 lists plus claude_hf 2026. Falls back to "legacy" (with a warning) when the file is missing. Returns the source in force."""
    import os
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)     # relative to the repository root
    if source == "csv" and not os.path.exists(path):
        import warnings
        warnings.warn(f"news_cal='csv': {path} not found - the legacy calendar is used", stacklevel=2)
        source = "legacy"
    key = (source, path, tuple(gdp_tags))
    if _ACTIVE[0] == key:
        return source
    if source == "legacy":
        src = {"fomc": DT.FOMC, "cpi": DT.CPI, "jobs": DT.JOBS, "pce": DT.PCE, "ppi": DT.PPI, "retail_sales": DT.RETAIL, "gdp": DT.GDP, "jolts": DT.JOLTS}
        times: dict = {}
    else:
        rows = load_csv(path)
        tags = {**CSV_MAP, "gdp": tuple(gdp_tags)}
        src = {k: set().union(*(rows.get(t, {}) for t in ts)) for k, ts in tags.items()}
        src["ppi"] = src["ppi"] | set(DT.PPI)               # the file has PPI 2016-2018 only; the built list carries 2019 on
        times = {}
        for k, ts in tags.items():
            for t in ts:
                for d_, m in rows.get(t, {}).items():
                    if m is not None:
                        times.setdefault(d_, {})[k] = m
    for k in EV_KEYS:
        EV[k].clear()
        EV[k].update(src[k])
    TIMES.clear()
    TIMES.update(times)
    _ACTIVE[0] = key
    if "FOMC_MINUTES" in globals():
        FOMC_MINUTES.clear()
        FOMC_MINUTES.update(_minutes_dates())
    if "day_type" in globals():
        _clear_caches()
    return source


def source() -> str:
    return _ACTIVE[0][0] if _ACTIVE[0] else "legacy"


def events(d: date) -> set:
    """Every event on day d (claude_hf.daytypes.events on the mentorship-owned sets of the active source)."""
    exp = DT.expiration(d.year, d.month)
    tags = {k for k in EV_KEYS if d in EV[k]}
    if d == exp:
        tags.add("quad_witching" if d.month in (3, 6, 9, 12) else "opex")
    if d == DT.nth_trading_day(d.year, d.month, 1):
        tags.add("ism_manufacturing")
    if d == DT.nth_trading_day(d.year, d.month, 3):
        tags.add("ism_services")
    if d == DT.second_friday(d.year, d.month):
        tags.add("sentiment")
    return tags


@lru_cache(maxsize=None)
def day_type(d: date) -> str:
    """claude_hf.daytypes.day_type on this module's events."""
    tags = events(d)
    for e in DT.EVENTS:
        if e in tags:
            return e
    exp = DT.expiration(d.year, d.month)
    quarterly = d.month in (3, 6, 9, 12)
    nxt, prv = DT._step(d, 1), DT._step(d, -1)
    if nxt.month != d.month or DT._step(d, 2).month != d.month:
        return "quarter_end" if quarterly else "month_end"
    if prv.month != d.month or DT._step(d, -2).month != d.month:
        return "quarter_start" if d.month in (1, 4, 7, 10) else "month_start"
    if quarterly and exp - timedelta(days=11) <= d < exp:
        return "roll_week"
    return DT.WEEKDAYS[d.weekday()]


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
    return {d + timedelta(days=21) for d in EV["fomc"] if d != date(2020, 3, 3)
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
    tags = events(d) | pmi_events(d)
    mn = minor_events(d)
    tags |= {t for t in mn if (t == "claims" and claims) or (t == "minutes" and minutes) or (t == "conf_board" and conf)}
    if TIMES or source() == "csv":                  # coverage gap 1: the csv source - each release at its own time_et (PCE is 10:00 on some dates)
        out_ = set()
        t_ = TIMES.get(d, {})
        for e in tags & (set(EV_KEYS) - {"fomc"}):
            out_.add(t_.get(e) or (600 if e in NEWS_1000 else 510))
        if "claims" in tags:
            out_.add(510)
        if pmi and tags & NEWS_0945:
            out_.add(585)
        if tags & (NEWS_1000 - set(EV_KEYS)):
            out_.add(600)
        if "fomc" in tags or "minutes" in tags:
            out_.add(840)
        return sorted(out_)
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
        if x in EV["jobs"]:
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
    fo = "fomc" in events(d)
    nxt, prv = next_trading_day(d), prev_trading_day(d)
    return dict(fomc=fo, eve="fomc" in events(nxt), after="fomc" in events(prv),
                only=fo and release_times(d) == [840])


@lru_cache(maxsize=None)
def eve_of(d: date, tag: str) -> bool:
    """The next trading day carries event `tag` (cpi / jobs / fomc ...)."""
    return tag in events(next_trading_day(d))


@lru_cache(maxsize=None)
def two_drivers(d: date, claims: bool = False, conf: bool = False) -> bool:
    """Two scheduled morning releases (08:30 data and a 09:45 / 10:00 one, or 09:45 and 10:00 - the
    PMI and ISM pair counts as one driver). N5.4 (100 ~50:59-1:40:56)."""
    rt = [r for r in release_times(d, claims=claims, conf=conf) if r < 840]
    return (510 in rt and any(r in rt for r in (585, 600)))


# --- day_week_context: holidays, weeks, early closes, roll (N7 family) --------------------------------
# Pure calendar functions of the date (no bars). [our interpretation] throughout: "a holiday" is a NYSE
# weekday holiday (claude_hf.daytypes.HOLIDAYS); the Columbus / Veterans Day bank holidays (market open) are
# an opt-in extra (N7.1 "and bank holidays").

def is_market_holiday(d: date) -> bool:
    """A weekday on which the exchange is closed."""
    return d.weekday() < 5 and d in DT.HOLIDAYS


def prev_weekday(d: date) -> date:
    x = d - timedelta(days=1)
    while x.weekday() > 4:
        x -= timedelta(days=1)
    return x


def next_weekday(d: date) -> date:
    x = d + timedelta(days=1)
    while x.weekday() > 4:
        x += timedelta(days=1)
    return x


def bank_holiday(d: date) -> bool:
    """Columbus Day (2nd Monday of October) and Veterans Day (Nov 11, observed on the nearest weekday): bank
    holidays on which the stock market is open (N7.1)."""
    if d.month == 10 and d.weekday() == 0 and 8 <= d.day <= 14:
        return True
    if d.month == 11:
        v = date(d.year, 11, 11)
        obs = v - timedelta(days=1) if v.weekday() == 5 else (v + timedelta(days=1) if v.weekday() == 6 else v)
        return d == obs
    return False


def is_holiday_eve(d: date, bank: bool = False) -> bool:
    """N7.1 the last trading day before a long weekend / market holiday: a weekday holiday lies between d and
    the next trading day (Friday before a Monday holiday, Thursday before Good Friday, the day before a
    midweek holiday). bank=True also counts the day before a bank holiday."""
    if not is_trading_day(d):
        return False
    x = next_weekday(d)
    if x in DT.HOLIDAYS:
        return True
    return bool(bank and bank_holiday(x))


def is_post_holiday(d: date) -> bool:
    """N7.2 the previous weekday was a market holiday (the morning after: Tuesday after a Monday holiday, Monday
    after a Friday holiday, the Friday after Thanksgiving ...)."""
    return is_trading_day(d) and prev_weekday(d) in DT.HOLIDAYS


def week_dates(d: date) -> list[date]:
    mon = d - timedelta(days=d.weekday())
    return [mon + timedelta(days=k) for k in range(5)]


def holiday_in_week(d: date) -> bool:
    """N7.3 the Monday-Friday week holds a weekday market holiday."""
    return any(x in DT.HOLIDAYS for x in week_dates(d))


def week_day_index(d: date) -> int:
    """1-based place of d among the trading days of its Monday-Friday week (a Monday holiday makes Tuesday 1)."""
    return 1 + sum(1 for x in week_dates(d) if x < d and is_trading_day(x))


def is_week_start(d: date) -> bool:
    """d is the first trading day of its week (Monday, or Tuesday after a Monday holiday: it 'acts like Monday')."""
    return is_trading_day(d) and week_day_index(d) == 1


def after_monday_holiday(d: date) -> bool:
    """N7.2 the week's Monday was a holiday (Tuesday acts like Monday, Wednesday is the likely reversal day)."""
    return week_dates(d)[0] in DT.HOLIDAYS


def first_trading_day_of_year(d: date) -> bool:
    return is_trading_day(d) and next_trading_day(date(d.year - 1, 12, 31)) == d


def _thanksgiving(year: int) -> date:
    x = date(year, 11, 1)
    x += timedelta(days=(3 - x.weekday()) % 7)
    return x + timedelta(days=21)


def early_close_min(d: date) -> int:
    """N7.1 EARLY_CLOSE: the cash-session close of a shortened day in minutes (13:00 = 780), else 0: the day
    after Thanksgiving, Christmas Eve (a trading weekday) and July 3 when July 4 is a weekday holiday."""
    if not is_trading_day(d):
        return 0
    if d == _thanksgiving(d.year) + timedelta(days=1):
        return 780
    if d.month == 12 and d.day == 24:
        return 780
    if d.month == 7 and d.day == 3 and date(d.year, 7, 4) in DT.HOLIDAYS and date(d.year, 7, 4).weekday() < 5:
        return 780
    return 0


def roll_week(d: date) -> bool:
    """N7.5 the index-futures roll week, independent of the other day types (claude_hf day_type gives the tag away
    to any event): in a quarterly month (Mar / Jun / Sep / Dec) the Monday-Friday week that holds the roll Thursday,
    8 days before the quarterly expiry (the third Friday). [our interpretation] The roll week is the week BEFORE
    expiry week; the real roll day of the data is the meta `roll` flag (Trade.roll_day)."""
    if d.month not in (3, 6, 9, 12):
        return False
    exp = DT.expiration(d.year, d.month)
    roll_thu = exp - timedelta(days=8)
    return week_dates(d)[0] == roll_thu - timedelta(days=3)


def trading_days_between(a: date, b: date) -> int:
    """Trading days strictly after a up to and including b (b <= a gives 0)."""
    n, x = 0, a
    while x < b:
        x += timedelta(days=1)
        if is_trading_day(x):
            n += 1
    return n


def month_trading_day(d: date) -> int:
    """1-based trading-day number of d in its month."""
    return trading_days_between(date(d.year, d.month, 1) - timedelta(days=1), d)


# --- Caption-gap pass, package day_week_context#1/3 (digests/rulebook_gaps; dwc1.py) --------------------------------------------------
# US presidential election days (N7-election, cc04_002 ~00:26:40; cc04_003 ~00:32:20: ICT's personal practice, not a stated rule).
ELECTIONS = {date(2016, 11, 8), date(2020, 11, 3), date(2024, 11, 5), date(2028, 11, 7)}


def election_block(d: date, mode: str) -> bool:
    """skip_election: "two_weeks" = Nov 1 of an election year to election day + 9 calendar days ("the first two weeks of November",
    [our interpretation]); "narrow" = election day and the next trading day [our interpretation]."""
    if mode == "off":
        return False
    for e in ELECTIONS:
        if e.year != d.year:
            continue
        if mode == "two_weeks":
            if date(e.year, 11, 1) <= d <= e + timedelta(days=9):
                return True
        elif mode == "narrow":
            if d == e or d == next_trading_day(e):
                return True
    return False


def holiday_eve_b(d: date) -> bool:
    """DS2-holiday-eve-friday-before-tue-holiday (cc10_019 ~00:23:45): case (b) - a Friday whose following Monday or Tuesday is a weekday
    market holiday (July 4 on a Tuesday: the Monday in between is an early-close / thin session). Case (a) is is_holiday_eve."""
    if d.weekday() != 4 or not is_trading_day(d):
        return False
    return any((d + timedelta(days=k)) in DT.HOLIDAYS for k in (3, 4))


def holiday_eve(d: date, cases: str = "a", bank: bool = False) -> bool:
    """skip_holiday_eve cases: "a" = the trading day before a market holiday, "ab" = also the Friday before a Monday / Tuesday holiday."""
    return bool(is_holiday_eve(d, bank) or (cases == "ab" and holiday_eve_b(d)))


def holiday_mon_wed(d: date) -> bool:
    """A weekday market holiday on Monday-Wednesday of d's week (N7-holiday-week: 072, Tuesday July 4 of NFP week)."""
    return any(x in DT.HOLIDAYS for x in week_dates(d)[:3])


RELEASES_LANDMINE = {"cpi", "jobs", "fomc", "pce", "ppi"}


def landmine_count(d: date) -> int:
    """D20-landmine-week-monday (064 ~00:10:18): the high-impact release days among Tuesday-Friday of d's week."""
    return sum(bool(events(x) & RELEASES_LANDMINE) for x in week_dates(d)[1:])


# B23 seasonal windows (tags only; 050 ~00:02:22; 074 ~00:18:21; cc10_015 ~00:02:03; cc10_016 ~00:02:11; cc10_017 ~00:01:54; cc10_018 ~00:23:16).
# (name, direction, (month, day) first, (month, day) last, wrap?) - inclusive calendar windows; win_long_fall wraps the year end.
SEASON_WINDOWS = (
    ("win_buy_june", 1, (5, 15), (6, 21)),            # the 3rd week of May to the 3rd week of June (the June low, 074)
    ("win_short_may", -1, (5, 1), (6, 14)),           # May into the 1st-2nd week of June (050)
    ("win_short_jan", -1, (1, 1), (1, 31)),           # January (cc10_017)
    ("win_short_summer", -1, (6, 15), (9, 15)),       # through July to about Aug 1 (cc10_017) or mid-Sep (cc10_018)
    ("win_long_fall", 1, (9, 15), (2, 7)),            # mid-Sep/Oct to year end, about the first week of Feb (050)
    ("win_long_spring", 1, (2, 1), (5, 31)),          # Feb to May (cc10_016/018)
)                                                      # [our interpretation] the priority order: the more specific (shorter) window wins where they overlap


def _in_window(d: date, a: tuple, b: tuple) -> bool:
    k, ka, kb = (d.month, d.day), a, b
    return (ka <= k <= kb) if ka <= kb else (k >= ka or k <= kb)


def season_tags(d: date) -> set:
    """B23-index-seasonal-windows: the regime layer (regime_hi_bull Jan-Apr, regime_range May-Oct, regime_q4 Oct-Dec) and every window the date
    falls in. Tags only (no gate)."""
    t = set()
    if d.month <= 4:
        t.add("regime_hi_bull")
    if 5 <= d.month <= 10:
        t.add("regime_range")
    if d.month >= 10:
        t.add("regime_q4")
    for name, _dr, a, b in SEASON_WINDOWS:
        if _in_window(d, a, b):
            t.add(name)
    return t


def season_window(d: date):
    """The primary (most specific) window of d as (name, direction), or None - the priority order of SEASON_WINDOWS."""
    for name, dr, a, b in SEASON_WINDOWS:
        if _in_window(d, a, b):
            return name, dr
    return None


def window_instance(name: str, d: date):
    """(first, last) dates of the most recent instance of window `name` that ended before d (None if the table has no such window)."""
    for nm, _dr, a, b in SEASON_WINDOWS:
        if nm != name:
            continue
        best = None
        for y in (d.year, d.year - 1, d.year - 2):
            last = date(y, b[0], b[1])
            first = date(y - 1 if a > b else y, a[0], a[1])
            if last < d and (best is None or last > best[1]):
                best = (first, last)
        return best
    return None


# B23-intramonth-detail (cc10_015 ~00:05:47): (month, week of month 1-4) -> direction. Weeks: days 1-7, 8-14, 15-21, 22+.
SEASON_DIR_TABLE = {(9, 1): 1, (9, 2): 1, (9, 3): -1, (9, 4): -1, (3, 2): -1, (3, 3): -1, (3, 4): 1, (4, 1): -1, (4, 2): -1, (4, 3): 1, (4, 4): 1,
                    (5, 1): -1, (5, 2): -1, (5, 3): -1, (5, 4): 1}
for _w in (1, 2, 3, 4):
    SEASON_DIR_TABLE.update({(7, _w): 1, (11, _w): 1, (12, _w): 1})            # Jul bullish into the mid-year high, Nov bullish, Dec Santa Claus


def week_of_month(d: date) -> int:
    return min(4, (d.day - 1) // 7 + 1)


def season_dir(d: date) -> int:
    """+1 / -1 / 0: the intramonth seasonal direction (Aug and the unlisted weeks are 0)."""
    return SEASON_DIR_TABLE.get((d.month, week_of_month(d)), 0)


# B23-daily-seasonal-review (cc05_012 ~00:13:05): the precomputed per-instrument month direction list (from the B23 map: bull +1, bear -1, else 0).
SEASONAL_MONTHS = {"ES": {m + 1: {"bull": 1, "bear": -1}.get(v, 0) for m, v in enumerate(
    ("bear", "bull", "cons", "bull", "bear", "cons", "bull", "cons", "split", "bull", "bull", "bull"))}}


def season_quality(d: date, autumn_start: int = 9) -> str:
    """B23-seasonal-quality (079 ~00:24:47; 100 ~00:29:55; 102 ~00:10:24): "prime" = (Sep 1 or Oct 1) to Dec 10 plus Feb 1-May 31,
    "poor" = August and Dec 11-31, "off" = everything else."""
    m, day = d.month, d.day
    if m == 8 or (m == 12 and day >= 11):
        return "poor"
    if 2 <= m <= 5:
        return "prime"
    if (m >= autumn_start and m <= 11) or (m == 12 and day <= 10):
        return "prime"
    return "off"


use("csv")                                             # coverage gap 1 default (Params.news_cal="csv"); run / run_day re-select per Params
