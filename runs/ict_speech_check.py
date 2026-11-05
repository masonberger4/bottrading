"""Whisper (with VAD) over the whole audio of each video in data/ict_no_commentary.txt.
Speech found -> writes data/ict_captions/<pl>/<NN_id>.en.vtt; results -> data/ict_speech_check.csv. Resumable."""
import os, sys, glob, csv, time
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICT = r"C:\Users\mason\ict_fetch"
VEXT = (".webm", ".mp4", ".mkv", ".m4v")
LIST = os.path.join(REPO, "data", "ict_no_commentary.txt"); RES = os.path.join(REPO, "data", "ict_speech_check.csv")

def fmt(t):
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

def videos(pl, folder):
    for base in (os.path.join(ICT, "out", pl, folder), os.path.join(ICT, "keep", pl, folder)):
        v = sorted(f for f in glob.glob(os.path.join(base, "*")) if f.lower().endswith(VEXT))
        if v: return v
    return []

def main():
    from faster_whisper import WhisperModel
    try:
        import psutil; psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception: pass
    done = set()
    if os.path.exists(RES):
        done = {r["video"] for r in csv.DictReader(open(RES, encoding="utf-8"))}
    model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=max(1, (os.cpu_count() or 4) - 2))
    new = not os.path.exists(RES)
    with open(RES, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new: w.writerow(["video", "speech_segments", "speech_seconds", "first_speech_s", "words", "note"])
        for line in open(LIST, encoding="utf-8"):
            rel = line.strip().replace(".en.vtt", "")
            if not rel or rel in done: continue
            pl, folder = rel.split("/")
            parts = videos(pl, folder)
            if not parts:
                w.writerow([rel, "", "", "", "", "video not on disk"]); fh.flush(); continue
            t0 = time.time(); cues = []; off = 0.0
            for p in parts:  # parts keep their own timestamps from 0; offset by running end
                segs, info = model.transcribe(p, vad_filter=True, beam_size=1)
                last = 0.0
                for s in segs:
                    if s.text.strip(): cues.append((s.start + off, s.end + off, s.text.strip()))
                    last = s.end
                off += max(last, info.duration)
            words = sum(len(c[2].split()) for c in cues)
            sp = sum(c[1] - c[0] for c in cues)
            if words >= 20:
                out = os.path.join(REPO, "data", "ict_captions", pl, folder + ".en.vtt")
                with open(out, "w", encoding="utf-8", newline="\n") as f:
                    f.write("WEBVTT\nKind: captions\nLanguage: en\nNOTE machine-transcribed (faster-whisper small.en, VAD)\n\n")
                    for a, b, t in cues: f.write(f"{fmt(a)} --> {fmt(b)}\n{t}\n\n")
            w.writerow([rel, len(cues), round(sp), round(cues[0][0]) if cues else "", words,
                        "speech" if words >= 20 else "no commentary", ]); fh.flush()
            print(rel, words, "words", round(time.time() - t0), "s", flush=True)

if __name__ == "__main__":
    main()
