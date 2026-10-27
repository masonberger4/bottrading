"""T14 / X16a / X16c weekly study (package day_week_context): where do the weekly high and low form?

    python -m mentorship.study_week [--symbol ES] [--minutes 5] [--source databento] [--out runs/mentorship]

Writes `week_extremes.csv` (one row per Monday-Friday week: the weekday and the kill-zone session of the weekly
high / low), `day_ranges.csv` (X16a: each session's range vs ADR5) and `week_study.json` (the T14 claims as
numbers). Whole weeks, all-hours bars (the Sunday-evening reopen counts to Monday): this is a REPORT, never an
input of a decision. The claims it tests (mentorship_rules.md T14, N10):
  mon_wed_extreme   the weekly high / low forms Monday-Wednesday ~70% of the time (cc07_008 ~1:35)
  bulk_tue_thu      the bulk of the weekly range is made Tuesday-Thursday
  by_wed_london     30-50% of the weekly range is done by Wednesday's London close (cc12_003 ~13:57; cc07_006 ~23:35)
  tue_london_low    Tuesday London makes the week's low in ~77% of bullish weeks [fx] (cc08_001 ~20:43)
  bear_high_tue     a bearish week's high is often Tuesday (070 ~4:23)
Params.tue_week_extreme ("tag" / "side") is the switch built on the Tuesday-London claim.

Caption-gap pass, package day_week_context#2/3: `profile_table` / `classify_week` / `first_driver` add the weekly PROFILE classifier (week_profiles.csv, `profiles` in week_study.json; statistics
only, M17): the weekly template fields (item 59), the Tuesday / Wednesday weekly extreme (61, 62), the Thursday false-break reversal (63), the midweek rally (64), the Wednesday weekly reversal
(65), the weekday / session of the weekly extremes vs the bias (68), the Tuesday-to-Thursday excursion (69), the first scheduled driver of the week (70) and the PBR return (levels 122).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import daycontext as DW


def week_table(df: pd.DataFrame) -> pd.DataFrame:
    """X16c: the weekly extremes with weekday and session labels (daycontext.weekly_extremes)."""
    return DW.weekly_extremes(df)


def _by_wed_london(df: pd.DataFrame, cut_min: int = 300) -> pd.Series:
    """For each week the share of the whole week's high-low range already made by the end of Wednesday's London
    session: cut_min minutes New York on the trading day Wednesday - 300 = the 05:00 London kill-zone end, 600 =
    the 10:00 London close that M14.3 / the rulebook use (the study reports both)."""
    lab = DW.trading_label(df.index)
    wk = pd.Series(lab.to_period("W-FRI"), index=df.index)
    wd = pd.Series(lab.dayofweek, index=df.index)
    m = pd.Series(df.index.hour * 60 + df.index.minute, index=df.index)
    out = {}
    for key, g in df.groupby(wk.values):
        if len(g) < 10:
            continue
        w = wd.loc[g.index]
        mm = m.loc[g.index]
        # trading-day Wednesday 05:00: the evening bars (>= 18:00) already belong to the next trading day
        cut = (w < 2) | ((w == 2) & ((mm < cut_min) | (mm >= 18 * 60)))
        part = g[cut.values]
        full = float(g.high.max() - g.low.min())
        if len(part) and full > 0:
            out[str(key)] = float(part.high.max() - part.low.min()) / full
    return pd.Series(out, dtype=float)


def summarize(wk: pd.DataFrame, df: pd.DataFrame | None = None) -> dict:
    """The T14 / N10 claims as numbers from the weekly table (and the bars, for the by-Wednesday share)."""
    n = len(wk)
    if not n:
        return dict(weeks=0)
    hi_mw = float(wk.mon_wed_high.mean())
    lo_mw = float(wk.mon_wed_low.mean())
    either = float((wk.mon_wed_high | wk.mon_wed_low).mean())
    bull = wk[wk.bullish]
    bear = wk[~wk.bullish]
    out = dict(
        weeks=n,
        high_by_weekday={int(k): int(v) for k, v in wk.high_day.value_counts().sort_index().items()},
        low_by_weekday={int(k): int(v) for k, v in wk.low_day.value_counts().sort_index().items()},
        high_by_session=wk.high_session.value_counts().to_dict(),
        low_by_session=wk.low_session.value_counts().to_dict(),
        mon_wed_high=round(hi_mw, 3), mon_wed_low=round(lo_mw, 3), mon_wed_either=round(either, 3),
        mon_wed_claim_holds=bool(either >= 0.6 or (hi_mw + lo_mw) / 2 >= 0.6),
        tue_london_low_bullish=round(float(((bull.low_day == 1) & (bull.low_session == "london")).mean()), 3) if len(bull) else None,
        tue_low_bullish=round(float((bull.low_day == 1).mean()), 3) if len(bull) else None,
        bear_high_tuesday=round(float((bear.high_day == 1).mean()), 3) if len(bear) else None,
        bullish_weeks=int(len(bull)), bearish_weeks=int(len(bear)),
    )
    # the bulk of the range Tue-Thu: the high and the low both formed Tuesday-Thursday
    out["bulk_tue_thu"] = round(float(((wk.high_day.between(1, 3)) & (wk.low_day.between(1, 3))).mean()), 3)
    if df is not None:
        s = _by_wed_london(df)
        if len(s):
            out["by_wed_london_mean"] = round(float(s.mean()), 3)
            out["by_wed_london_30_50"] = round(float(((s >= 0.3) & (s <= 0.5)).mean()), 3)
        s10 = _by_wed_london(df, 600)                                  # the 10:00 London close of M14.3
        if len(s10):
            out["by_wed_london_close_mean"] = round(float(s10.mean()), 3)
            out["by_wed_london_close_30_50"] = round(float(((s10 >= 0.3) & (s10 <= 0.5)).mean()), 3)
    t = out["tue_london_low_bullish"]
    out["tue_week_extreme_claim_holds"] = bool(t is not None and t >= 0.5)
    return out


# --------------------------------------------------------------------------------------------------------------
# Caption-gap pass, package day_week_context#2/3: the weekly PROFILE classifier (day_selection_news_calendar items 59, 61, 62, 63, 64, 65, 68, 69, 70; levels_liquidity_targets 122).
# One row per Monday-Friday week: the weekly bias (the weekly tone of the completed weeks, B8c), the nearest HTF discount (premium) array below (above) the Monday open (an alive daily FVG; [our
# interpretation] of "old M/W/D low, broken high retested, M/W/D/4h OB"), and the profile flags. Statistics only (M17): no engine switch reads them. `classify_week` is a pure function of
# the five day dicts so it can be tested on hand-made weeks.
# --------------------------------------------------------------------------------------------------------------

TICK = 0.25


def _sess_bucket(minute: int) -> str:
    """Session buckets of item 68: London 120-300, NY 510-660, PM 810-960, else other."""
    if 120 <= minute < 300:
        return "london"
    if 510 <= minute < 660:
        return "ny"
    if 810 <= minute < 960:
        return "pm"
    return "other"


def weekly_tone(weeks: list) -> int:
    """The weekly tone (B8c, the same definition as dwc1.weekly_state) from completed weeks [(o, h, l, c), ...] oldest first."""
    state, dn_hi, up_lo = 0, None, None
    for o, h, l, c in weeks:
        if dn_hi is not None and c > dn_hi:
            state = 1
        elif up_lo is not None and c < up_lo:
            state = -1
        if c < o:
            dn_hi = h
        elif c > o:
            up_lo = l
    return state


def nearest_array(daily: list, bias: int, ref: float):
    """The nearest alive daily FVG of the bias side before the week: a bullish one with its top below `ref` (bias +1, the discount array), a bearish one with its bottom above it (bias -1).
    `daily` = [(o, h, l, c), ...] of the sessions before the week. Returns (bottom, top) or None."""
    from . import levels as L
    if len(daily) < 3 or not bias:
        return None
    a = np.array(daily, float)
    o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    best = None
    for z in L.fvgs(h, l, o, c):
        after = c[z.i + 1:]
        if z.kind == "bull" and bias > 0 and z.top < ref and not (len(after) and after.min() < z.bottom):
            if best is None or z.top > best[1]:
                best = (float(z.bottom), float(z.top))
        elif z.kind == "bear" and bias < 0 and z.bottom > ref and not (len(after) and after.max() > z.top):
            if best is None or z.bottom < best[0]:
                best = (float(z.bottom), float(z.top))
    return best


def classify_week(days: list, bias: int, arr, a5, tick: float = TICK) -> dict:
    """The profile flags of one week from its day dicts. Each day dict: o, h, l, c, hi_min, lo_min (the NY minute of the high / low bar), rel (the release minutes of the day), and optionally lon_l,
    lon_h (London 120-300 extremes), ny_l, ny_h (NY 570-720 extremes), h1100, l1100 (extremes up to 11:00, Thursday). `bias` = the weekly bias (+1 / -1 / 0), `arr` = (bottom, top) of the
    nearest HTF array of the bias side or None, `a5` = ADR5 before the week. days[k] is the k-th trading day of the week (a holiday week is shorter)."""
    n = len(days)
    out = dict(bias=bias, days=n)
    if n < 3:
        return out
    wk_hi = max(x["h"] for x in days)
    wk_lo = min(x["l"] for x in days)
    hi_day = max(range(n), key=lambda k: days[k]["h"])
    lo_day = min(range(n), key=lambda k: days[k]["l"])
    out.update(wk_high=wk_hi, wk_low=wk_lo, high_day=hi_day, low_day=lo_day,
               high_sess=_sess_bucket(int(days[hi_day].get("hi_min", -1))), low_sess=_sess_bucket(int(days[lo_day].get("lo_min", -1))))
    # item 68: where the weekly extremes form vs the bias
    if bias > 0:
        by_thu = hi_day < 3 or (hi_day == 3 and 0 <= int(days[3].get("hi_min", 9999)) < 720)
        out["bull_low_mon_wed_high_by_thu720"] = int(lo_day <= 2 and by_thu)
    elif bias < 0:
        by_thu = lo_day < 3 or (n > 3 and lo_day == 3 and 0 <= int(days[3].get("lo_min", 9999)) < 720)
        out["bear_high_tue_low_thu_ny"] = int(n > 3 and hi_day == 1 and lo_day == 3 and 510 <= int(days[3].get("lo_min", -1)) < 660)
        out["bear_high_mon_wed_low_by_thu720"] = int(hi_day <= 2 and by_thu)
    if not bias:
        return out
    sg = bias

    # side space: for a bearish week the prices mirror (higher = more in the bias direction)
    def hi_(x):
        return x["h"] if sg > 0 else -x["l"]

    def lo_(x):
        return x["l"] if sg > 0 else -x["h"]

    def cl_(x):
        return x["c"] if sg > 0 else -x["c"]

    zt = zb = None
    if arr is not None:
        zt = arr[1] if sg > 0 else -arr[0]               # the array's near edge (the top of the discount array) in side space
        zb = arr[0] if sg > 0 else -arr[1]
    mon, tue, wed = days[0], days[1], days[2]
    mw = days[:3]
    mw_hi = max(hi_(x) for x in mw)
    mw_lo = min(lo_(x) for x in mw)
    open_mon = mon["o"] if sg > 0 else -mon["o"]
    late = days[3:]
    ext_lo = min(lo_(x) for x in days)
    ext_lo_day = min(range(n), key=lambda k: lo_(days[k]))
    # item 59 the weekly template
    out["impulse"] = mw_hi - open_mon
    out["retrace_into_array"] = int(zt is not None and mw_lo <= zt)
    out["expansion"] = int(bool(late) and max(hi_(x) for x in late) > mw_hi)
    # item 61 Tuesday weekly extreme
    out["tue_ext"] = int(zt is not None and ext_lo_day == 1 and lo_(mon) > zt and lo_(tue) <= zt)
    k_l, k_h = ("lon_l", "ny_l") if sg > 0 else ("lon_h", "ny_h")
    if k_l in tue and k_h in tue:
        out["tue_ny_undercut_london"] = int((tue[k_h] < tue[k_l]) if sg > 0 else (tue[k_h] > tue[k_l]))
    ext_hi_day = max(range(n), key=lambda k: hi_(days[k]))
    min_key = "hi_min" if sg > 0 else "lo_min"
    out["ext_high_by_thu720"] = int(ext_hi_day < 3 or (n > 3 and ext_hi_day == 3 and 0 <= int(days[3].get(min_key, 9999)) < 720))
    # item 62 Wednesday weekly extreme
    out["wed_ext"] = int(zt is not None and lo_(mon) > zt and lo_(tue) > zt and lo_(wed) <= zt and ext_lo_day == 2)
    # item 63 Thursday reversal (consolidation Mon-Wed, the false break of its low, a release)
    if n >= 4 and a5:
        th = days[3]
        mw_range = mw_hi - mw_lo
        broke = lo_(th) <= mw_lo - tick
        closed_back = cl_(th) > mw_lo
        has_rel = any(r in (510, 840) for r in th.get("rel", ()))
        out["thu_reversal"] = int(mw_range <= 1.5 * a5 and broke and closed_back and has_rel)
    # item 64 midweek rally (decline)
    if arr is not None:
        mon_up = cl_(mon) > (mon["o"] if sg > 0 else -mon["o"])
        in_arr = zb - 1e-9 <= min(lo_(tue), lo_(wed)) <= zt + 1e-9
        out["midweek_rally"] = int(mon_up and in_arr and bool(wed.get("rel")) and cl_(days[-1]) > max(hi_(mon), hi_(tue)))
        out["midweek_expansion"] = int(bool(late) and max(hi_(x) for x in late) > max(hi_(x) for x in mw))
    # item 65 Wednesday weekly reversal
    if a5 and arr is not None:
        mt_range = max(hi_(mon), hi_(tue)) - min(lo_(mon), lo_(tue))
        below = lo_(wed) < min(lo_(mon), lo_(tue))
        w_rng = hi_(wed) - lo_(wed)
        top_third = w_rng > 0 and (cl_(wed) - lo_(wed)) >= 2.0 * w_rng / 3.0 - 1e-9
        out["wed_weekly_reversal"] = int(mt_range <= a5 and below and lo_(wed) <= zt and top_third and ext_lo_day == 2)
    # item 122 PBR: a small Monday range, a Tuesday sell-off (rally in a bearish week) of more than 1 x ADR5, Thursday / Friday returns into Monday's range
    if a5 and late:
        mon_rng = mon["h"] - mon["l"]
        sell = (tue["o"] - tue["l"]) if sg > 0 else (tue["h"] - tue["o"])
        if mon_rng < 0.6 * a5 and sell > a5:
            out["pbr_week"] = 1
            late_h = max(x["h"] for x in late)
            late_l = min(x["l"] for x in late)
            if sg > 0:
                out["pbr_return"] = int(late_h >= mon["l"])
                out["pbr_exceed"] = int(late_h > mon["h"])
            else:
                out["pbr_return"] = int(late_l <= mon["h"])
                out["pbr_exceed"] = int(late_l < mon["l"])
        else:
            out["pbr_week"] = 0
    # item 69 Tuesday-to-Thursday horizon: an OTE entry (62-79 % of Monday's low -> high leg) on Tuesday, else Wednesday off Tuesday's low; the excursion to Thursday 11:00
    if a5 and n >= 4 and mon["h"] > mon["l"]:
        r = mon["h"] - mon["l"]
        if sg > 0:
            lvl = mon["h"] - 0.62 * r
            tue_fill = tue["l"] <= lvl
            entry = min(lvl, tue["o"]) if tue_fill else (tue["l"] if wed["l"] <= tue["l"] else None)
        else:
            lvl = mon["l"] + 0.62 * r
            tue_fill = tue["h"] >= lvl
            entry = max(lvl, tue["o"]) if tue_fill else (tue["h"] if wed["h"] >= tue["h"] else None)
        if entry is not None:
            day_in = 1 if tue_fill else 2
            th = days[3]
            pts = [days[k]["h"] if sg > 0 else days[k]["l"] for k in range(day_in, 3)]
            pts.append(th.get("h1100", th["h"]) if sg > 0 else th.get("l1100", th["l"]))
            best = max(pts) if sg > 0 else min(pts)
            out["tue_thu_entry_day"] = day_in
            out["tue_thu_excursion_adr"] = round(((best - entry) if sg > 0 else (entry - best)) / a5, 4)
    return out


def first_driver(days: list, a5=None, bias: int = 0) -> dict:
    """Item 70 DS2-weekend-first-driver (cc12_003 ~00:18:01): the earliest (day, minute R) of the week with a scheduled release (`rel`); whether the week's AGAINST-bias extreme (the low of a bullish
    week, the high of a bearish one) formed within [R, R + 120] of that day, and the range of the days before it vs ADR5. Stats only."""
    for k, x in enumerate(days):
        if x.get("rel"):
            r = min(x["rel"])
            out = dict(first_driver_day=k, first_driver_min=int(r))
            if bias:
                hi_day = max(range(len(days)), key=lambda q: days[q]["h"])
                lo_day = min(range(len(days)), key=lambda q: days[q]["l"])
                if bias > 0:
                    out["against_ext_in_driver"] = int(lo_day == k and r <= int(x.get("lo_min", -1)) < r + 120)
                else:
                    out["against_ext_in_driver"] = int(hi_day == k and r <= int(x.get("hi_min", -1)) < r + 120)
            if k > 0 and a5:
                pre = days[:k]
                out["pre_driver_range_adr"] = round((max(y["h"] for y in pre) - min(y["l"] for y in pre)) / a5, 4)
            return out
    return dict(first_driver_day=None)


def week_days(df: pd.DataFrame) -> list:
    """[(week key, [day dicts])] of the all-hours bars: the evening reopen counts to the next trading day (Monday 00:00-17:00 plus the Sunday 18:00 evening)."""
    from . import calendar as CAL
    lab = DW.trading_label(df.index)
    m = (df.index.hour * 60 + df.index.minute).values
    wk = np.array([str(x) for x in lab.to_period("W-FRI")])
    out = []
    for key in sorted(set(wk)):
        sel_w = wk == key
        g = df[sel_w]
        ld = lab[sel_w]
        mm = m[sel_w]
        days = []
        for d in sorted(set(ld)):
            sel = np.asarray(ld == d)
            if sel.sum() < 5 or d.dayofweek > 4:
                continue
            gd = g[sel]
            md = mm[sel]
            ih, il = int(np.argmax(gd.high.values)), int(np.argmin(gd.low.values))
            x = dict(o=float(gd.open.iloc[0]), h=float(gd.high.max()), l=float(gd.low.min()), c=float(gd.close.iloc[-1]), hi_min=int(md[ih]), lo_min=int(md[il]),
                     rel=list(CAL.release_times(d.date())), weekday=int(d.dayofweek), date=d.date())
            lon = (md >= 120) & (md < 300)
            ny = (md >= 570) & (md < 720)
            if lon.any() and ny.any():
                x.update(lon_l=float(gd.low.values[lon].min()), lon_h=float(gd.high.values[lon].max()), ny_l=float(gd.low.values[ny].min()), ny_h=float(gd.high.values[ny].max()))
            if d.dayofweek == 3:
                c11 = md < 660
                if c11.any():
                    x.update(h1100=float(gd.high.values[c11].max()), l1100=float(gd.low.values[c11].min()))
            days.append(x)
        if len(days) >= 3:
            out.append((key, days))
    return out


def profile_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per week with the weekly bias, the array, ADR5 and every profile flag of `classify_week` / `first_driver`. Whole weeks: a REPORT, never an input of a decision."""
    rows, prior, daily_hist = [], [], []
    for key, days in week_days(df):
        a5 = float(np.mean([h - l for _o, h, l, _c in daily_hist[-5:]])) if len(daily_hist) >= 5 else None
        bias = weekly_tone(prior) if prior else 0
        arr = nearest_array(daily_hist, bias, days[0]["o"]) if daily_hist else None
        r = classify_week(days, bias, arr, a5)
        r.update(first_driver(days, a5, bias))
        r["week"] = key
        r["array"] = None if arr is None else f"{arr[0]:.2f}-{arr[1]:.2f}"
        rows.append(r)
        prior.append((days[0]["o"], max(x["h"] for x in days), min(x["l"] for x in days), days[-1]["c"]))
        daily_hist += [(x["o"], x["h"], x["l"], x["c"]) for x in days]
    return pd.DataFrame(rows)


def summarize_profiles(tab: pd.DataFrame) -> dict:
    """Hit rates of the profile flags over the weeks (frequency, the Thursday / Friday expansion rate of the midweek rally, the PBR return / exceed rates)."""
    if not len(tab) or "bias" not in tab:
        return dict(weeks=0)
    b = tab[tab.bias != 0]
    out = dict(weeks=int(len(tab)), weeks_with_bias=int(len(b)))
    for k in ("retrace_into_array", "expansion", "tue_ext", "tue_ny_undercut_london", "ext_high_by_thu720", "wed_ext", "thu_reversal", "midweek_rally", "wed_weekly_reversal",
              "bull_low_mon_wed_high_by_thu720", "bear_high_tue_low_thu_ny", "bear_high_mon_wed_low_by_thu720", "against_ext_in_driver"):
        if k in tab and tab[k].notna().any():
            col = tab[k].dropna()
            out[k] = dict(n=int(col.sum()), rate=round(float(col.mean()), 4), of=int(len(col)))
    if "midweek_rally" in tab and (tab.midweek_rally == 1).any():
        out["midweek_rally_expansion_rate"] = round(float(tab[tab.midweek_rally == 1].midweek_expansion.mean()), 4)
    if "pbr_week" in tab and (tab.pbr_week == 1).any():
        p_ = tab[tab.pbr_week == 1]
        out["pbr_weeks"] = int(len(p_))
        out["pbr_return_rate"] = round(float(p_.pbr_return.mean()), 4)
        out["pbr_exceed_rate"] = round(float(p_.pbr_exceed.mean()), 4)
    for k in ("tue_thu_excursion_adr", "pre_driver_range_adr"):
        if k in tab and tab[k].notna().any():
            out[k + "_mean"] = round(float(tab[k].dropna().mean()), 4)
    return out


def main(symbol: str = "ES", minutes: int = 5, source: str = "databento", out: str = "runs/mentorship") -> dict:
    from . import backtest as B
    df = B.load(symbol, minutes, source=source)
    Path(out).mkdir(parents=True, exist_ok=True)
    wk = week_table(df)
    wk.drop(columns=["high_ts", "low_ts"], errors="ignore").to_csv(f"{out}/week_extremes.csv", index=False)
    frames = [B.rth(g) for g in B.days(df, minutes, False, 975)]
    DW.day_ranges(frames).to_csv(f"{out}/day_ranges.csv", index=False)
    rep = summarize(wk, df)
    prof = profile_table(df)                                       # day_week_context#2/3: the weekly profile classifier (items 59-70, 122)
    prof.to_csv(f"{out}/week_profiles.csv", index=False)
    rep["profiles"] = summarize_profiles(prof)
    Path(f"{out}/week_study.json").write_text(json.dumps(rep, indent=1, default=str))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="ES")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--source", default="databento")
    ap.add_argument("--out", default="runs/mentorship")
    a = ap.parse_args()
    print(json.dumps(main(a.symbol, a.minutes, a.source, a.out), indent=1, default=str))


def week_state_labels(days: list) -> dict:
    """T14-weekly-template (cc01_002 ~24:06; caption-gap pass day_week_context#3/3): the weekday states (consol / expansion / reversal), the weekday of the weekly high and low and the template
    count, as stats only - see dwc3.week_state_labels. `days` = daily regular-session frames, oldest first."""
    from . import dwc3
    return dwc3.week_state_labels(days)
