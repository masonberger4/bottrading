"""Study material for the 2023 Mentorship playlist: captions plus chart frames.

For each video: English auto-captions as timestamped text, and a still frame every
`every` seconds from a 720p copy. The video file is deleted as soon as its frames are
saved, so only one video is on disk at a time. Everything lands in data/mentorship2023/
(gitignored): captions/<idx>_<id>.txt and frames/<idx>_<id>/<hh-mm-ss>.jpg.

Needs yt-dlp and imageio-ffmpeg (a private ffmpeg binary). Study use only.

    python -m mentorship2023.videos --items 11-20
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLAYLIST = "https://www.youtube.com/playlist?list=PLVgHx4Z63pabpjlduWBaEsn8VMtALhjGV"
ROOT = Path("data/mentorship2023")
CAP, FRAMES, TMP = ROOT / "captions", ROOT / "frames", ROOT / "tmp_video"


def ytdlp(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings", *args],
                          capture_output=True, text=True, encoding="utf8")


def playlist() -> list[tuple[int, str, int, str]]:
    r = ytdlp("--flat-playlist", "--print", "%(playlist_index)s|%(id)s|%(duration)s|%(title)s", PLAYLIST)
    out = []
    for line in r.stdout.splitlines():
        i, vid, dur, title = line.split("|", 3)
        out.append((int(i), vid, int(float(dur or 0)), title))
    return out


def vtt_to_text(path: Path) -> str:
    """One line per caption cue, '[hh:mm:ss] text', with rolling duplicates removed."""
    lines, stamp, last = [], None, ""
    for raw in path.read_text(encoding="utf8").splitlines():
        m = re.match(r"(\d\d:\d\d:\d\d)\.\d+ -->", raw)
        if m:
            stamp = m.group(1)
            continue
        t = re.sub(r"<[^>]+>", "", raw).strip()
        if not t or t.startswith(("WEBVTT", "Kind:", "Language:")) or t == last or t in last:
            continue
        lines.append(f"[{stamp}] {t}")
        last = t
    return "\n".join(lines)


def captions(idx: int, vid: str) -> Path | None:
    out = CAP / f"{idx:03d}_{vid}.txt"
    if out.exists():
        return out
    CAP.mkdir(parents=True, exist_ok=True)
    tmp = TMP / vid
    tmp.mkdir(parents=True, exist_ok=True)
    ytdlp("--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en-orig,en",
          "--sub-format", "vtt", "-o", str(tmp / "c.%(ext)s"), f"https://www.youtube.com/watch?v={vid}")
    vtts = sorted(tmp.glob("*.vtt"), key=lambda p: ("en-orig" not in p.name, p.name))
    if not vtts:
        return None
    out.write_text(vtt_to_text(vtts[0]), encoding="utf8")
    return out


def frames(idx: int, vid: str, every: int = 20) -> Path | None:
    out = FRAMES / f"{idx:03d}_{vid}"
    if out.exists() and any(out.iterdir()):
        return out
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = TMP / vid
    tmp.mkdir(parents=True, exist_ok=True)
    # smallest 720p video-only stream: charts are mostly static, so low bitrate reads fine
    r = ytdlp("-f", "bv*[height<=720][height>=720]/bv*[height<=720]", "-S", "+size",
              "-o", str(tmp / "v.%(ext)s"), f"https://www.youtube.com/watch?v={vid}")
    vids = [p for p in tmp.glob("v.*") if p.suffix in (".mp4", ".webm", ".mkv")]
    if not vids:
        print(f"  video download failed: {r.stderr[-300:]}")
        return None
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([ff, "-loglevel", "error", "-i", str(vids[0]), "-vf", f"fps=1/{every}",
                    "-q:v", "4", str(out / "f_%05d.jpg")], check=True)
    for k, p in enumerate(sorted(out.glob("f_*.jpg"))):      # name frames by video time
        s = k * every
        p.rename(out / f"{s // 3600:02d}-{s % 3600 // 60:02d}-{s % 60:02d}.jpg")
    shutil.rmtree(tmp, ignore_errors=True)                  # the video itself is not kept
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="1-105", help="playlist positions, e.g. 11-20")
    ap.add_argument("--every", type=int, default=20, help="seconds between frames")
    ap.add_argument("--no-frames", action="store_true")
    a = ap.parse_args()
    lo, hi = map(int, a.items.split("-"))
    seen = set()
    for idx, vid, dur, title in playlist():
        if not lo <= idx <= hi or vid in seen:
            continue
        seen.add(vid)
        c = captions(idx, vid)
        f = None if a.no_frames else frames(idx, vid, a.every)
        n = len(list(f.iterdir())) if f else 0
        print(f"{idx:03d} {vid} {dur // 60}m captions={'yes' if c else 'NONE'} frames={n} | {title}", flush=True)


if __name__ == "__main__":
    main()
