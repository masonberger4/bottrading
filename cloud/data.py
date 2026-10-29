"""Put the Databento ES / NQ / YM bars in data/mentorship/ for this session.

    python -m cloud.data            # from the shared folder; download only if it isn't there yet
    python -m cloud.data --quote    # what a fresh download would cost (spends nothing)
    python -m cloud.data --buy      # download from Databento (spends credit), then keep a shared copy

The raw .dbn.zst files and the Yahoo dailies live in /mnt/project-files/mentorship/data/, so later
sessions copy them instead of downloading. The CSVs the backtests read are rebuilt locally
(mentorship.databento_data.build), which needs no key or network. The key is read from the
DATABENTO_API_KEY environment variable only and is never printed or written anywhere.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

from mentorship import databento_data as D
from mentorship.backtest import DATA

from .common import SHARED_DATA

SYMS = ("ES", "NQ", "YM")


def _need_key():
    if not os.environ.get("DATABENTO_API_KEY"):
        sys.exit("DATABENTO_API_KEY is not set in this cloud environment (see cloud/README.md).")


def sync(symbols=SYMS) -> None:
    raw = DATA / "databento"
    raw.mkdir(parents=True, exist_ok=True)
    for s in symbols:
        f = f"{s}_ohlcv1m.dbn.zst"
        if not (raw / f).exists():
            if not (SHARED_DATA / "databento" / f).exists():
                sys.exit(f"{f} is not in {SHARED_DATA}/databento yet: run `python -m cloud.data --buy` "
                         "once (after --quote), or copy it there from the laptop.")
            shutil.copy2(SHARED_DATA / "databento" / f, raw / f)
        if not (DATA / f"{s}_1min_db.csv").exists():
            D.build(s)
    y = SHARED_DATA / "yahoo"
    if y.exists():
        shutil.copytree(y, DATA / "yahoo", dirs_exist_ok=True)
    else:
        print("note: no Yahoo DXY/TNX dailies in the shared folder; the dxy/tnx labels will be blank")


def buy(symbols=SYMS, end: str | None = None) -> None:
    _need_key()
    D.buy(symbols, end)                       # writes data/mentorship/databento/*.dbn.zst + CSVs
    (SHARED_DATA / "databento").mkdir(parents=True, exist_ok=True)
    for s in symbols:
        f = f"{s}_ohlcv1m.dbn.zst"
        shutil.copy2(DATA / "databento" / f, SHARED_DATA / "databento" / f)
    print("raw files copied to", SHARED_DATA / "databento")


def main():
    ap = argparse.ArgumentParser(prog="cloud.data")
    ap.add_argument("--quote", action="store_true")
    ap.add_argument("--buy", action="store_true")
    ap.add_argument("--end", default=None, help="last day (exclusive), e.g. 2026-10-17 to match the laptop")
    a = ap.parse_args()
    if a.quote:
        _need_key()
        for s, v in D.quote(SYMS, a.end).items():
            print(s, f"${v:.2f}")
    elif a.buy:
        buy(SYMS, a.end)
    else:
        sync()


if __name__ == "__main__":
    main()
