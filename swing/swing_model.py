"""Month 6 swing model (cc06_001-008; spec section 6): the switch `python -m swing --model swing`.

Differences from One Shot One Kill, all from the Month 6 notes: setups are framed at weekly /
monthly arrays (daily and 4h arrays only when nested at a higher-timeframe one, MWD cases A/B/C),
execution is on the 4h/1h chart at any hour (no weekday or kill-zone limit), the target is the
first opposing weekly/monthly array at least 3R away (cc06_003 ~22:25), holds run 2+ weeks (no
Friday flush), and the failure protocol halves the next position after each stop-out and resets
after a win (cc06_003 ~23:24). The stop stays beyond the swept liquidity (cc06_004 ~21:17).
Management is the shared Million Dollar management (osok._manage).
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from . import bias as Bi
from .arrays import STOP_TYPES
from . import osok
from .osok import Params, Prepared, _candidate, _manage, _open, _row, _stop_for


def defaults() -> Params:
    return Params(target_tfs=("W", "M"), min_rr=3.0, fib_gate=False, scale_in=False,
                  skip_seek_destroy=False, entry_days="any", kill_zones=tuple(range(24)),
                  tfs=("4h", "D", "W", "M"))


def run(frames: dict, p: Params | None = None) -> pd.DataFrame:
    p = p or defaults()
    pr = Prepared(frames, p)
    b, F = pr.book, frames
    W, h1 = F["W"], F["1h"]
    n = len(h1)
    rows, factor = [], 1.0
    pending, tr = None, None
    k = 0
    while k < n:
        t = h1.start.iloc[k]
        if tr is None:
            md, _, _ = Bi.at(pr.st["M"], F["M"], t)
            wd, _, wcorr = Bi.at(pr.st["W"], F["W"], t)
            side = md if md != 0 else wd
            if side == 0 or wd == -side:
                pending = None
                k += 1
                continue
            w = max(int(W.start.searchsorted(t, side="right")) - 1, 0)
            if pending is not None:
                j = pending["j"]
                if pending["side"] != side:
                    pending = None
                else:
                    trig = (b.top[j] + p.tick) if side > 0 else (b.bottom[j] - p.tick)
                    if (pr.h[k] >= trig) if side > 0 else (pr.l[k] <= trig):
                        fill = max(trig, pr.o[k]) if side > 0 else min(trig, pr.o[k])
                        ext = pending["ext"]
                        stop = ext - p.tick if side > 0 else ext + p.tick
                        tr = _open(pr, w, k, side, j, fill, stop, pending["case"], pending["frame"])
                        pending = None
                        if tr is not None:
                            tr.tags["factor"] = factor
                        else:
                            k += 1
                            continue
                    else:
                        pending["ext"] = min(pending["ext"], pr.l[k]) if side > 0 else max(pending["ext"], pr.h[k])
                        if (side > 0 and pr.c[k] < b.bottom[j]) or (side < 0 and pr.c[k] > b.top[j]):
                            pending = None
                        k += 1
                        continue
            else:
                cand = _candidate(pr, k, t, side, wcorr)
                if cand is None:
                    k += 1
                    continue
                j, case, frame_tf = cand
                if b.typ[j] in STOP_TYPES:
                    touched = (pr.l[k] <= b.top[j]) if side > 0 else (pr.h[k] >= b.bottom[j])
                    if touched:
                        pending = {"j": j, "side": side, "ext": pr.l[k] if side > 0 else pr.h[k],
                                   "case": case, "frame": frame_tf}
                    k += 1
                    continue
                lvl = b.entry[j]
                if not ((pr.l[k] <= lvl) if side > 0 else (pr.h[k] >= lvl)):
                    k += 1
                    continue
                fill = min(lvl, pr.o[k]) if side > 0 else max(lvl, pr.o[k])
                stop = _stop_for(pr, k, j, side)
                if stop is None:
                    k += 1
                    continue
                q = replace(p, risk_usd=p.risk_usd * factor)
                pr.p = q
                tr = _open(pr, w, k, side, j, fill, stop, case, frame_tf)
                pr.p = p
                if tr is None:
                    k += 1
                    continue
                tr.tags["factor"] = factor
            if tr is not None and _manage(pr, tr, k, same_bar=True):
                factor, tr = _done(pr, rows, tr, factor)
            k += 1
            continue
        if _manage(pr, tr, k):
            factor, tr = _done(pr, rows, tr, factor)
        k += 1
    if tr is not None and tr.units > 1e-12:
        tr.exits.append((h1.end.iloc[n - 1], pr.c[n - 1], tr.units, "data_end"))
        rows.append(_row(pr, tr))
    return pd.DataFrame(rows)


def _done(pr: Prepared, rows: list, tr, factor: float):
    r = _row(pr, tr)
    r["size_factor"] = tr.tags.get("factor", 1.0)
    rows.append(r)
    return (max(factor * 0.5, 1 / 16) if r["net"] < 0 else 1.0), None
