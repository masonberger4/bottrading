#!/usr/bin/env python3
"""memsave.py - versioned, hash-checked saves for the project memory folder.

Usage (run from anywhere; paths are relative to the memory folder):
  memsave.py hash FILE                      print sha256 of FILE (take this BEFORE drafting)
  memsave.py save FILE --base HASH --draft DRAFTFILE --agent WHO --reason WHY [--link URL]
        re-hashes FILE under a lock; if it differs from HASH -> exit 3 (STALE): re-pull, redraft, retry.
  memsave.py append FILE --base HASH --agent WHO --reason WHY [--link URL]   (text on stdin; same check)
  memsave.py log [FILE]                     version history
  memsave.py show FILE VERSION              print FILE as of version (e.g. v3)
  memsave.py rollback FILE VERSION --agent WHO --reason WHY [--link URL]   restore as a NEW version
  memsave.py propose FILE --agent WHO --reason WHY [--link URL]   (proposed text on stdin) -> proposals/<agent>__<file>.md
Permissions (ACL.json): top-level files are writable only by ACL "writers"; scratch/<agent>/ is free for that agent
(unversioned, git-ignored); proposals/<agent>__* is free for that agent. Violations exit 4 (DENIED).
Every change = new version vN, a git commit, and a CHANGELOG.md row (who, when, why, link, hash before->after).
Exit codes: 0 ok, 2 usage/error, 3 stale hash (conflict), 4 DENIED by ACL.
NOTE: --agent is self-declared; the ACL stops mistakes and honest agents, not a malicious one.
"""
import argparse, hashlib, json, os, subprocess, sys, time, shutil, re, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK = os.path.join(ROOT, ".memsave.lock")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

def sha(path):
    if not os.path.exists(path): return "ABSENT"
    return hashlib.sha256(open(path, "rb").read()).hexdigest()

def git(*a, check=True):
    r = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, *a], capture_output=True, text=True)
    if check and r.returncode: sys.exit("git error: " + r.stderr.strip())
    return r.stdout

def init():
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        git("init", "-q"); git("config", "user.name", "memory-folder"); git("config", "user.email", "memory@localhost")
        open(os.path.join(ROOT, ".gitignore"), "w").write(".memsave.lock\n__pycache__/\n")

class Lock:
    def __enter__(self):
        for _ in range(100):
            try: os.mkdir(LOCK); return self
            except FileExistsError: time.sleep(0.1)
        sys.exit("could not get lock (stale? remove %s if no save is running)" % LOCK)
    def __exit__(self, *a): shutil.rmtree(LOCK, ignore_errors=True)

def next_version():
    nums = [int(m) for m in re.findall(r"^\| v(\d+) ", open(CHANGELOG).read(), re.M)] if os.path.exists(CHANGELOG) else []
    return (max(nums) if nums else 0) + 1

def commit(rel, before, agent, reason, link, kind):
    v = next_version()
    ts = time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime())
    after = sha(os.path.join(ROOT, rel))
    if not os.path.exists(CHANGELOG):
        open(CHANGELOG, "w").write("# Memory CHANGELOG\n\nOne row per version. Roll back with `tools/memsave.py rollback FILE vN ...` (creates a new version; nothing is erased).\n\n| version | when (UTC) | who | file | action | reason | link | hash before -> after |\n|---|---|---|---|---|---|---|---|\n")
    row = "| v%d | %s | %s | %s | %s | %s | %s | %s -> %s |\n" % (v, ts, agent, rel, kind, reason.replace("|", "/"), link or "-", before[:10], after[:10])
    open(CHANGELOG, "a").write(row)
    git("add", "-A")
    git("commit", "-q", "-m", "v%d %s %s: %s" % (v, kind, rel, reason), "-m", "Who: %s\nLink: %s\nHash: %s -> %s" % (agent, link or "-", before, after))
    git("tag", "v%d" % v)
    print("saved %s as v%d (%s -> %s)" % (rel, v, before[:10], after[:10]))

def slug(name):
    n = re.sub(r"^(thread|agent|human)\s*:\s*", "", name.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-") or "unknown"

def acl_kind(rel, agent):
    """returns 'scratch' | 'open' | 'writer' (allowed) or exits 4."""
    try: writers = [slug(w) for w in json.load(open(os.path.join(ROOT, "ACL.json")))["writers"]]
    except Exception: writers = []
    me, parts = slug(agent), rel.split(os.sep)
    is_writer = me in writers
    if parts[0] == "scratch":
        if len(parts) >= 3 and (parts[1] == me or is_writer): return "scratch"
        deny(rel, agent, "scratch/ is per-agent: use scratch/%s/..." % me)
    if parts[0] == "proposals":
        if is_writer or os.path.basename(rel).startswith(me + "__"): return "open"
        deny(rel, agent, "proposals files must be named %s__<name>.md" % me)
    if is_writer: return "writer"
    deny(rel, agent, "top-level memory is read-only for you; write scratch/%s/ or run: memsave.py propose FILE ..." % me)

def deny(rel, agent, why):
    print("DENIED: %s may not write %s. %s" % (agent, rel, why), file=sys.stderr); sys.exit(4)

def target(f):
    p = os.path.normpath(os.path.join(ROOT, f))
    if not p.startswith(ROOT + os.sep) or ".git" in p.split(os.sep): sys.exit("path must be inside the memory folder")
    return p, os.path.relpath(p, ROOT)

def do_write(f, base, data, a, kind):
    p, rel = target(f)
    kind_acl = acl_kind(rel, a.agent)
    if kind_acl == "scratch":
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p)); os.write(fd, data); os.close(fd); os.replace(tmp, p)
        print("scratch write %s (unversioned, git-ignored)" % rel); return
    with Lock():
        cur = sha(p)
        if cur != base:
            print("STALE: %s changed since you hashed it (yours %s, now %s). Re-pull the file, redraft, take a new hash, retry." % (rel, base[:10], cur[:10]), file=sys.stderr)
            sys.exit(3)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p)); os.write(fd, data); os.close(fd)
        os.replace(tmp, p); os.chmod(p, 0o444)
        commit(rel, cur, a.agent, a.reason, a.link, kind)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("file", nargs="?"); ap.add_argument("version", nargs="?")
    ap.add_argument("--base"); ap.add_argument("--draft"); ap.add_argument("--agent"); ap.add_argument("--reason"); ap.add_argument("--link")
    a = ap.parse_args(); init()
    if a.cmd in ("save", "append", "rollback", "propose") and not (a.agent and a.reason): sys.exit("--agent and --reason are required")
    if a.cmd == "hash": print(sha(target(a.file)[0]))
    elif a.cmd == "save":
        if not (a.base and a.draft): sys.exit("--base and --draft required")
        do_write(a.file, a.base, open(a.draft, "rb").read(), a, "edit")
    elif a.cmd == "append":
        if not a.base: sys.exit("--base required")
        p, _ = target(a.file); old = open(p, "rb").read() if os.path.exists(p) else b""
        add = sys.stdin.buffer.read()
        if old and not old.endswith(b"\n"): old += b"\n"
        do_write(a.file, a.base, old + add, a, "append")
    elif a.cmd == "propose":
        text = sys.stdin.buffer.read()
        name = "proposals/%s__%s" % (slug(a.agent), a.file.replace("/", "_"))
        hdr = ("<!-- proposal by %s at %s; target: %s; reason: %s; link: %s; status: open -->\n" % (a.agent, time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), a.file, a.reason, a.link or "-")).encode()
        p, _ = target(name)
        do_write(name, sha(p), hdr + text, a, "proposal")
    elif a.cmd == "log":
        print(git("log", "--format=%h %s | %b", "--", a.file) if a.file else open(CHANGELOG).read())
    elif a.cmd == "show":
        sys.stdout.write(git("show", "%s:%s" % (a.version, target(a.file)[1])))
    elif a.cmd == "rollback":
        p, rel = target(a.file)
        old = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "show", "%s:%s" % (a.version, rel)], capture_output=True)
        if old.returncode: sys.exit("no such file/version")
        do_write(a.file, sha(p), old.stdout, a, "rollback-to-" + a.version)
    else: sys.exit(__doc__)
main()
