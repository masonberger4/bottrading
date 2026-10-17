"""Study material for ICT Mentorship playlists (the 2023 one first): captions plus chart frames.

For each video: English auto-captions as timestamped text, and a still frame every
`every` seconds from a 720p copy. The video file is deleted as soon as its frames are
saved, so only one video is on disk at a time. Everything lands in data/mentorship/
(gitignored): captions/<idx>_<id>.txt and frames/<idx>_<id>/<hh-mm-ss>.jpg.

Needs yt-dlp and imageio-ffmpeg (a private ffmpeg binary). Study use only.

    python -m mentorship.videos --items 11-20
    python -m mentorship.videos --playlist <url> --prefix m24_     # another playlist
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

PLAYLIST = "https://www.youtube.com/playlist?list=PLVgHx4Z63pabpjlduWBaEsn8VMtALhjGV"
ROOT = Path("data/mentorship")
CAP, FRAMES, TMP = ROOT / "captions", ROOT / "frames", ROOT / "tmp_video"


def ytdlp(*args: str) -> subprocess.CompletedProcess:
    # node solves YouTube's player challenges; without a JS runtime some downloads get 403
    js = ["--js-runtimes", "node"] if shutil.which("node") else []
    return subprocess.run([sys.executable, "-m", "yt_dlp", "--no-warnings", "--retries", "5", *js, *args],
                          capture_output=True, text=True, encoding="utf8")


def playlist(url: str = PLAYLIST) -> list[tuple[int, str, int, str]]:
    r = ytdlp("--flat-playlist", "--print", "%(playlist_index)s|%(id)s|%(duration)s|%(title)s", url)
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


def captions(idx: int, vid: str, prefix: str = "") -> Path | None:
    out = CAP / f"{prefix}{idx:03d}_{vid}.txt"
    if out.exists():
        return out
    CAP.mkdir(parents=True, exist_ok=True)
    tmp = TMP / vid
    tmp.mkdir(parents=True, exist_ok=True)
    ytdlp("--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en-orig,en",
          "--sub-format", "vtt", "-o", str(tmp / "c.%(ext)s"), f"https://www.youtube.com/watch?v={vid}")
    vtts = sorted(tmp.glob("*.vtt"), key=lambda p: ("en-orig" not in p.name, p.name))
    if not vtts:
        out.write_text("(no captions on YouTube for this video)", encoding="utf8")   # mark as done
        return None
    out.write_text(vtt_to_text(vtts[0]), encoding="utf8")
    return out


def frames(idx: int, vid: str, every: int = 20, prefix: str = "") -> Path | None:
    out = FRAMES / f"{prefix}{idx:03d}_{vid}"
    if out.exists() and any(out.iterdir()):
        return out
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    tmp = TMP / vid
    tmp.mkdir(parents=True, exist_ok=True)
    # smallest 720p video-only stream: charts are mostly static, so low bitrate reads fine
    import time
    for attempt in range(4):        # YouTube sometimes answers 403; a pause and retry usually works
        # H.264 decodes several times faster than AV1/VP9 on this laptop's CPU
        r = ytdlp("-f", "bv*[height=720][vcodec^=avc1]/bv*[height<=720][vcodec^=avc1]/bv*[height<=720]",
                  "-S", "+size",
                  "-o", str(tmp / "v.%(ext)s"), f"https://www.youtube.com/watch?v={vid}")
        vids = [p for p in tmp.glob("v.*") if p.suffix in (".mp4", ".webm", ".mkv")]
        if vids:
            break
        time.sleep(30 * (attempt + 1))
    if not vids:
        print(f"  video download failed: {r.stderr[-300:]}")
        return None
    part = out.with_name(out.name + ".part")                # renamed only when complete
    shutil.rmtree(part, ignore_errors=True)
    part.mkdir(parents=True)
    subprocess.run([ff, "-loglevel", "error", "-threads", "2", "-skip_frame", "nokey",   # keyframes only
                    "-i", str(vids[0]), "-vf", f"fps=1/{every}",
                    "-q:v", "4", str(part / "f_%05d.jpg")], check=True)
    for k, p in enumerate(sorted(part.glob("f_*.jpg"))):     # name frames by video time
        s = k * every
        p.rename(part / f"{s // 3600:02d}-{s % 3600 // 60:02d}-{s % 60:02d}.jpg")
    shutil.rmtree(out, ignore_errors=True)
    part.rename(out)
    shutil.rmtree(tmp, ignore_errors=True)                  # the video itself is not kept
    return out


def claim(prefix: str, idx: int, vid: str) -> Path | None:
    """Lock a video for this worker so parallel workers never take the same one.
    A lock older than 6 hours is treated as abandoned."""
    import os
    import time
    FRAMES.mkdir(parents=True, exist_ok=True)
    lock = FRAMES / f"{prefix}{idx:03d}_{vid}.lock"
    if lock.exists() and time.time() - lock.stat().st_mtime > 6 * 3600:
        lock.unlink(missing_ok=True)
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return lock
    except FileExistsError:
        return None


def work(playlists: list[tuple[str, str]], every: int = 20) -> None:
    """Process every video of every playlist, skipping finished ones and ones another
    worker holds. Run several of these at once to go faster."""
    for prefix, url in playlists:
        seen = set()
        for idx, vid, dur, title in playlist(url):
            if vid in seen:
                continue
            seen.add(vid)
            out = FRAMES / f"{prefix}{idx:03d}_{vid}"
            if out.exists() and any(out.iterdir()) and (CAP / f"{prefix}{idx:03d}_{vid}.txt").exists():
                continue
            lock = claim(prefix, idx, vid)
            if lock is None:
                continue
            try:
                c = captions(idx, vid, prefix)
                f = frames(idx, vid, every, prefix)
                n = len(list(f.iterdir())) if f else 0
                print(f"{prefix}{idx:03d} {vid} {dur // 60}m captions={'yes' if c else 'NONE'} frames={n} | {title}",
                      flush=True)
            finally:
                lock.unlink(missing_ok=True)


def queue(path: Path = ROOT / "playlists.txt") -> list[tuple[str, str]]:
    """The 2023 playlist (no prefix) then every 'prefix|url|title' line of playlists.txt."""
    out = [("", PLAYLIST)]
    for line in path.read_text(encoding="utf8").splitlines():
        if line.strip() and not line.startswith("#"):
            p, u = line.split("|")[:2]
            out.append((p, u))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="1-105", help="playlist positions, e.g. 11-20")
    ap.add_argument("--every", type=int, default=20, help="seconds between frames")
    ap.add_argument("--no-frames", action="store_true")
    ap.add_argument("--playlist", default=PLAYLIST, help="another mentorship playlist URL")
    ap.add_argument("--prefix", default="", help="file-name prefix for a playlist other than 2023's")
    ap.add_argument("--worker", action="store_true",
                    help="process the 2023 playlist and everything in playlists.txt, sharing work "
                         "with other --worker processes")
    a = ap.parse_args()
    if a.worker:
        work(queue(), a.every)
        print("worker done", flush=True)
        return
    lo, hi = map(int, a.items.split("-"))
    seen = set()
    for idx, vid, dur, title in playlist(a.playlist):
        if not lo <= idx <= hi or vid in seen:
            continue
        seen.add(vid)
        c = captions(idx, vid, a.prefix)
        f = None if a.no_frames else frames(idx, vid, a.every, a.prefix)
        n = len(list(f.iterdir())) if f else 0
        print(f"{idx:03d} {vid} {dur // 60}m captions={'yes' if c else 'NONE'} frames={n} | {title}", flush=True)


if __name__ == "__main__":
    main()
