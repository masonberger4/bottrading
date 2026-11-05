"""Build lectures.csv: one row per noted ICT video (key, playlist, video id, date, title, note path).

Run from the repo root:  python mentorship/scorecard/build_lectures.py
Dates are parsed from the first lines of each note. Hand fixes go in
lecture_overrides.csv (same columns; non-empty cells win) and survive rebuilds.
"""
import csv, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
NOTES = ROOT / "mentorship"
OUT = pathlib.Path(__file__).with_name("lectures.csv")
OVR = pathlib.Path(__file__).with_name("lecture_overrides.csv")
COLS = ["key", "playlist", "lecture", "video_id", "date", "year", "title", "note"]

MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}


def parse_date(text):
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text)
    if m:
        return m.group(0)
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2}),? (20\d\d)\b", text)
    if m:
        return f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (20\d\d)\b", text)
    if m:
        return f"{m.group(2)}-{MONTHS[m.group(1).lower()]:02d}"
    m = re.search(r"\b(201\d|202\d)\b", text)
    return m.group(1) if m else ""


def rows():
    specs = [  # folder, file regex, playlist, lecture formatter
        ("notes", r"^(cc\d\d_\d\d\d)_(.+)$", "CC", lambda g: g),
        ("notes", r"^(\d\d\d)_(.+)$", "M2023", lambda g: g),
        ("notes_te_charter", r"^(te\d\d)_(.+)$", "TE", lambda g: g),
        ("notes_te_charter", r"^(ch\d\d)_(.+)$", "CH", lambda g: g),
        ("notes_2024", r"^(\d\d)_(.+)$", "M2024", lambda g: "L" + g),
        ("notes_2025", r"^(\d\d)_(.+)$", "L2025", lambda g: "L" + g),
        ("notes_2026smc", r"^(\d\d\d)_(.+)$", "SMC2026", lambda g: g),
    ]
    for folder, rx, playlist, fmt in specs:
        for f in sorted((NOTES / folder).glob("*.md")):
            m = re.match(rx, f.stem)
            if not m:
                continue
            head = f.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
            title = head[0].lstrip("# ").strip() if head else ""
            cands = [parse_date(title), parse_date(" ".join(head[1:2]))]
            date = max(cands, key=len)  # most specific wins; title on a tie
            lec = fmt(m.group(1))
            yield {"key": f"{playlist}:{lec}", "playlist": playlist, "lecture": lec,
                   "video_id": "" if m.group(2) == "note" else m.group(2), "date": date, "year": date[:4],
                   "title": title[:140], "note": str(f.relative_to(ROOT)).replace("\\", "/")}


def main():
    out = {r["key"]: r for r in rows()}
    if OVR.exists():
        with OVR.open(newline="", encoding="utf-8") as fh:
            for o in csv.DictReader(fh):
                r = out.setdefault(o["key"], {c: "" for c in COLS})
                r.update({k: v for k, v in o.items() if v})
                if o.get("date") and not o.get("year"):
                    r["year"] = o["date"][:4]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        w.writerows(out.values())
    print(f"{len(out)} lectures -> {OUT}")


if __name__ == "__main__":
    main()
