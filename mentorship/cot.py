"""Caption-gap pass, package bias_htf#3/7: CFTC Commitments of Traders loader (item 148, B20-cot-data-spec) and the two COT states (item 147, B20-cot-zero-line-vs-hedging).

Data spec (cc10_001 ~00:01:20 "the Futures Contract only in the short format"): the legacy FUTURES-ONLY report (options excluded), commercials only (large and small speculators ignored),
net = commercial long - commercial short, at least 12 months of weekly history for the range and its midpoint. The files are the CFTC annual archives `deacot{year}.zip` (legacy futures-only, the
member `annual.txt` is a CSV) in data/mentorship/cot/ (the download is an owner step; nothing here touches the network). A market is picked by its CFTC contract market code (E-mini S&P 500
13874A, E-mini Nasdaq-100 209742). [our interpretation] each report is dated by its public RELEASE, not by its Tuesday: `known` = report_date + 3 days (the Friday release), and the report is
usable from the next trading session after `known` (the Tuesday report of 2023-03-07 is released Friday 2023-03-10 and first usable on Monday 2023-03-13) - never on the Tuesday it describes.

Two states (item 147), both from the commercial net as known on a day:
  cot_program  sign(net)                                      above the zero line = a buy program, below = a sell program (macro)
  cot_hedge    sign(net - MID52)                              the net against the midpoint of its 52-week (12-month) range; MID26 (the 26-week range) when the 52-week range is narrower than
                                                              NARROW x the mean |net| [our interpretation]
A hedging reading against the program (net below zero but above MID and rising) still permits trades in the hedging direction when the daily institutional order flow agrees (Params.cot_gate).
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

COT_DIR = Path("data/mentorship/cot")
MARKET_CODES = {"E-MINI S&P 500": "13874A", "E-MINI NASDAQ-100": "209742", "NASDAQ-100 STOCK INDEX (MINI)": "209742", "E-MINI NASDAQ 100": "209742"}
NARROW = 0.10                        # a 52-week range narrower than this share of the mean |net| falls back to the 26-week range [our interpretation]
MIN_REPORTS = 8                      # fewer reports than this: no state (as bias_htf.cot_state)
_CACHE: dict = {}


def market_code(market: str) -> str | None:
    """The CFTC contract market code of a Params.cot_market name (None when unknown: then the name is matched against 'Market and Exchange Names')."""
    return MARKET_CODES.get(str(market).strip().upper())


def known_date(rep) -> pd.Timestamp:
    """The public release of a report dated `rep` (Tuesday positions, released Friday): rep + 3 days."""
    return pd.Timestamp(rep).normalize() + pd.Timedelta(days=3)


def first_usable(rep) -> pd.Timestamp:
    """The first trading session strictly after the release (the tag is usable from the next session)."""
    from .calendar import is_trading_day
    d = known_date(rep) + pd.Timedelta(days=1)
    for _ in range(10):
        if is_trading_day(d.date()):
            return d
        d += pd.Timedelta(days=1)
    return d


def parse_legacy(src, code: str | None = None, name: str | None = None) -> pd.DataFrame | None:
    """Rows of one legacy futures-only file (a path, bytes, a file object or a DataFrame) for one market: report_date, comm_long, comm_short, net. The market is picked by the CFTC contract market
    code `code` when the file has that column, else by `name` inside 'Market and Exchange Names'. None when the file lacks the columns or the market."""
    if isinstance(src, pd.DataFrame):
        x = src
    else:
        if isinstance(src, (bytes, bytearray)):
            src = io.BytesIO(src)
        x = pd.read_csv(src, low_memory=False)
    cols = {str(c).strip().lower(): c for c in x.columns}
    dt = next((cols[c] for c in cols if c.startswith("report_date_as_yyyy-mm-dd") or ("as of date" in c and "yyyy-mm-dd" in c) or c == "report_date"), None)
    lg = next((cols[c] for c in cols if c.startswith("commercial positions-long") or c in ("comm_positions_long_all", "comm_long")), None)
    sh = next((cols[c] for c in cols if c.startswith("commercial positions-short") or c in ("comm_positions_short_all", "comm_short")), None)
    if None in (dt, lg, sh):
        return None
    cc = next((cols[c] for c in cols if c in ("cftc contract market code", "cftc_contract_market_code")), None)
    nm = next((cols[c] for c in cols if c.startswith("market and exchange") or c == "market_and_exchange_names"), None)
    if code and cc is not None:
        x = x[x[cc].astype(str).str.strip().str.upper() == str(code).upper()]
    elif name and nm is not None:
        x = x[x[nm].astype(str).str.upper().str.contains(str(name).upper(), regex=False)]
    if not len(x):
        return None
    out = pd.DataFrame({"report_date": pd.to_datetime(x[dt]), "comm_long": pd.to_numeric(x[lg], errors="coerce"), "comm_short": pd.to_numeric(x[sh], errors="coerce")})
    out = out.dropna()
    out["net"] = out.comm_long - out.comm_short
    return out.reset_index(drop=True)


def read_zip(src, code: str | None = None, name: str | None = None) -> pd.DataFrame | None:
    """The market's rows of a deacot{year}.zip (a path, bytes or a file object): every CSV / TXT member is parsed."""
    if isinstance(src, (bytes, bytearray)):
        src = io.BytesIO(src)
    parts = []
    with zipfile.ZipFile(src) as z:
        for m in z.namelist():
            if m.lower().endswith((".txt", ".csv")):
                with z.open(m) as f:
                    r = parse_legacy(io.BytesIO(f.read()), code, name)
                if r is not None:
                    parts.append(r)
    return pd.concat(parts, ignore_index=True) if parts else None


def table(reports: pd.DataFrame | None) -> pd.DataFrame | None:
    """The usable-date table of report rows: index = the first trading session each report is usable (see first_usable), columns report_date, known, comm_long, comm_short, net; sorted, one row
    per report date. None without reports."""
    if reports is None or not len(reports):
        return None
    r = reports.drop_duplicates("report_date").sort_values("report_date").reset_index(drop=True)
    r["known"] = [known_date(x) for x in r.report_date]
    r["usable"] = [first_usable(x) for x in r.report_date]
    return r.set_index("usable")[["report_date", "known", "comm_long", "comm_short", "net"]]


def load_reports(market: str = "E-MINI S&P 500", folder: Path | None = None) -> pd.DataFrame | None:
    """The raw report rows (report_date, comm_long, comm_short, net) of the market from every deacot*.zip (and legacy CSV / TXT) of the folder; None when there is none."""
    folder = Path(folder) if folder is not None else COT_DIR
    code, parts = market_code(market), []
    if folder.exists():
        for f in sorted(folder.glob("deacot*.zip")):
            try:
                r = read_zip(f, code, market)
            except Exception:
                continue
            if r is not None:
                parts.append(r)
        for f in sorted(list(folder.glob("*.csv")) + list(folder.glob("*.txt"))):
            try:
                r = parse_legacy(f, code, market)
            except Exception:
                continue
            if r is not None:
                parts.append(r)
    return pd.concat(parts, ignore_index=True) if parts else None


def load_dir(market: str = "E-MINI S&P 500", folder: Path | None = None) -> pd.DataFrame | None:
    """Every deacot*.zip (and legacy CSV / TXT) of the folder for the market, as table(); None when the folder has no usable file. Cached per (market, folder)."""
    folder = Path(folder) if folder is not None else COT_DIR
    key = (str(market), str(folder))
    if key in _CACHE:
        return _CACHE[key]
    out = table(load_reports(market, folder))
    _CACHE[key] = out
    return out


def states(tbl: pd.DataFrame | None, day, weeks: int = 52, fallback: int = 26) -> tuple:
    """(cot_program, cot_hedge) of the reports usable at `day` (usable <= day): program = sign of the latest commercial net; hedge = sign(net - MID52) with the MID26 fallback when the 52-week range
    is under NARROW x the mean |net|. (0, 0) without data or with fewer than MIN_REPORTS reports."""
    if tbl is None or not len(tbl):
        return 0, 0
    t = tbl[tbl.index <= pd.Timestamp(day)]
    if len(t) < MIN_REPORTS:
        return 0, 0
    net = t.net.iloc[-weeks:].astype(float)
    last = float(net.iloc[-1])
    program = int(np.sign(last))
    hi, lo = float(net.max()), float(net.min())
    mean_abs = float(net.abs().mean())
    if mean_abs > 0 and (hi - lo) < NARROW * mean_abs:                       # narrow: the 6-month range instead
        n2 = net.iloc[-fallback:]
        hi, lo = float(n2.max()), float(n2.min())
    if hi <= lo:
        return program, 0
    mid = (hi + lo) / 2
    return program, int(np.sign(last - mid))


def states_of_series(net, weeks: int = 52, fallback: int = 26) -> tuple:
    """The same two states from a plain sequence of weekly nets (the last element is the latest report) - for tests and what-if checks."""
    s = pd.Series(list(net), dtype=float)
    idx = pd.date_range("2000-01-03", periods=len(s), freq="7D")
    t = pd.DataFrame({"net": s.values}, index=idx)
    return states(t, idx[-1], weeks, fallback)
