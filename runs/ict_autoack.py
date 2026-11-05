"""Local replacement for the dead box sync (Mase approved "auto-ack", 2026-11-02).
For each ict_fetch\\out\\<pl>\\<NN_id> folder that is PREPPED and not SYNCED:
  1. caption .vtt -> data/ict_captions/<pl>/<NN_id>.en.vtt (pushed to git)
  2. empty caption -> needs a row in data/ict_speech_check.csv (full-audio whisper) first, else skipped
  3. frames shrunk (near-duplicates dropped, WebP q55, ~5-8x smaller) -> data/ict_frames/<pl>/<NN_id>/ (laptop only, gitignored)
  4. verified (>=1 frame, every source frame mapped) -> sync_tool.py ack (clears the folder, keeps DONE) and the keep\\ video removed
Usage: python runs/ict_autoack.py [--loop MINUTES] [--dry]"""
import os, sys, glob, json, csv, shutil, subprocess, time, io
from PIL import Image, ImageChops, ImageStat

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICT = r"C:\Users\mason\ict_fetch"; OUT = os.path.join(ICT, "out"); KEEP = os.path.join(ICT, "keep")
CAP = os.path.join(REPO, "data", "ict_captions"); FR = os.path.join(REPO, "data", "ict_frames")
SPEECH = os.path.join(REPO, "data", "ict_speech_check.csv")
DIFF, Q = 1.5, 55

def log(*a): print(time.strftime("%Y-%m-%dT%H:%M:%S"), *a, flush=True)

def checked():
    if not os.path.exists(SPEECH): return set()
    return {r["video"] for r in csv.DictReader(open(SPEECH, encoding="utf-8"))}

def shrink(src, dst):
    fs = sorted(glob.glob(os.path.join(src, "*.jpg")))
    if not fs: return 0, 0
    tmp = dst + ".tmp"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    prev = None; kept = 0
    for f in fs:
        im = Image.open(f).convert("RGB"); sm = im.convert("L").resize((160, 90))
        if prev is not None and ImageStat.Stat(ImageChops.difference(sm, prev)).mean[0] < DIFF: continue
        prev = sm; kept += 1
        im.save(os.path.join(tmp, os.path.basename(f)[:-4] + ".webp"), "WEBP", quality=Q, method=4)
    shutil.rmtree(dst, ignore_errors=True); os.replace(tmp, dst)
    return len(fs), kept

def one_pass(dry):
    done_speech = checked(); acked = []
    for d in sorted(glob.glob(os.path.join(OUT, "*", "*_*"))):
        if not os.path.exists(os.path.join(d, "PREPPED")) or os.path.exists(os.path.join(d, "SYNCED")): continue
        pl, nm = os.path.basename(os.path.dirname(d)), os.path.basename(d); rel = f"{pl}/{nm}"
        vtts = glob.glob(os.path.join(d, "*.vtt"))
        if not vtts: log("skip (no vtt)", rel); continue
        capdst = os.path.join(CAP, pl, nm + ".en.vtt"); os.makedirs(os.path.dirname(capdst), exist_ok=True)
        if not os.path.exists(capdst): shutil.copy2(vtts[0], capdst)
        if os.path.getsize(vtts[0]) < 8192 and rel not in done_speech:
            log("skip (empty caption, speech check pending)", rel); continue
        prep = os.path.join(d, "prep"); fdst = os.path.join(FR, pl, nm)
        n, kept = shrink(os.path.join(prep, "frames"), fdst)
        if kept == 0: log("skip (no frames)", rel); continue
        for f in ("PREP.json", "transcript.txt"):
            if os.path.exists(os.path.join(prep, f)): shutil.copy2(os.path.join(prep, f), fdst)
        if len(glob.glob(os.path.join(fdst, "*.webp"))) != kept: log("skip (frame copy mismatch)", rel); continue
        log(f"saved {rel}: {n} -> {kept} frames"); acked.append(rel)
    if not acked: return 0
    subprocess.run(["git", "-C", REPO, "add", "data/ict_captions"], check=True)
    if subprocess.run(["git", "-C", REPO, "diff", "--cached", "--quiet"]).returncode:
        subprocess.run(["git", "-C", REPO, "commit", "-qm", f"ICT auto-ack: captions for {len(acked)} videos"], check=True)
        subprocess.run(["git", "-C", REPO, "push", "-q"])
    if dry: log("dry run, not acking", len(acked)); return len(acked)
    subprocess.run([sys.executable, os.path.join(ICT, "sync_tool.py"), "ack", *acked], cwd=ICT, check=True)
    for rel in acked: shutil.rmtree(os.path.join(KEEP, *rel.split("/")), ignore_errors=True)
    log("acked", len(acked)); return len(acked)

if __name__ == "__main__":
    dry = "--dry" in sys.argv
    if "--loop" in sys.argv:
        m = float(sys.argv[sys.argv.index("--loop") + 1])
        while True:
            try: one_pass(dry)
            except Exception as e: log("error", repr(e))
            time.sleep(m * 60)
    else: one_pass(dry)
