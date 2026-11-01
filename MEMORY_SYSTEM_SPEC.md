# Versioned agent-memory system: build spec

Purpose: give any repo's AI agents a shared, durable memory that is (a) small to load, (b) versioned with a rollback path, (c) annotated with who changed what and why, and (d) safe against two agents overwriting each other. Project-neutral; adapt names freely, keep the behaviors.

## 1. Layout
```
MEMORY.md (or your platform's memory index)   short index, <3 KB: current status, standing rules, pointers
memory/                                       shared folder, one git repo
  README.md          how agents read and write (section 6 rules)
  decisions.md       owner/human decisions and standing rules, with date + who decided
  results.md         experiment/test/build results, baselines, status history
  data.md            data sources, paths, purchases
  ops.md             environment/machine operating rules
  lessons.md         incidents, stalls, fixes
  CHANGELOG.md       one row per version (section 3)
  tools/memsave.py   the only way to write (section 2)
  skill_drafts/      draft agent skills (e.g. memory-hygiene.md) for the human to install
```
Rules of thumb: the index is read every session, so keep it tiny and point to topic files; agents grep and read only the file they need. Topic files hold the detail, grouped by subject, never by date. Never store secrets. When migrating an old memory store, move every fact verbatim into a section headed `## <old-name> - <description> (source: <file>, modified <date>)` so nothing is lost.

## 2. The save tool
A single Python 3 script (full source in section 8) with these commands:
- `hash FILE` prints sha256 of the file (`ABSENT` if missing).
- `save FILE --base HASH --draft DRAFTFILE --agent WHO --reason WHY [--link URL]` replaces the file.
- `append FILE --base HASH --agent WHO --reason WHY [--link URL]` appends stdin.
- `log [FILE]`, `show FILE vN`, `rollback FILE vN --agent --reason [--link]`.
Behavior of save/append/rollback, all inside one critical section:
1. Take a lock (`mkdir .memsave.lock`, retry ~10 s, fail loudly).
2. Re-hash the file now. If it differs from `--base`, print `STALE ...` and exit code 3, writing nothing.
3. Write via temp file + atomic rename.
4. Allocate the next version number vN (max in CHANGELOG + 1), append a CHANGELOG row, `git add -A`, `git commit` (message: `vN kind file: reason`, body: who, link, hash before->after), `git tag vN`.
5. Release the lock.
`--agent` and `--reason` are mandatory; `--link` should point at the conversation, message id, PR or incident that caused the change.
Git needs `-c safe.directory=*` when several OS users touch a shared mount, and a local identity (`user.name`, `user.email`).

## 3. CHANGELOG.md format
Markdown table, one row per version, newest last:
`| version | when (UTC) | who | file | action | reason | link | hash before -> after |`
Example: `| v7 | 2026-11-01 21:32:29Z | thread: backtests | results.md | append | Added 2021 screen results | msg cmsg_123 | 4a968d6787 -> 0b047223e8 |`
`action` is edit, append, or rollback-to-vN (or initial import). Failed attempts are annotated, never deleted.

## 4. Compare-and-save flow (what an agent does)
1. Pull: read the file and take `H=$(memsave.py hash FILE)`.
2. Draft the edit in a scratch file (or text for append).
3. `memsave.py save FILE --base $H --draft DRAFT --agent ... --reason ... --link ...`
4. Exit 0: done. Exit 3 (STALE): someone else edited. Re-pull, redraft against the new content, take a new hash, retry. Never force, never edit by hand.
This is optimistic concurrency: the hash taken before drafting must still match the hash taken immediately before the write, under the lock. Tested: two agents hash the same version; A saves; B's save returns exit 3 and leaves the file untouched; B redrafts from A's version and saves; rollback to v1 restores old text as a new version.

## 5. Rollback
`memsave.py rollback FILE vN --agent ... --reason ... [--link ...]` reads the file as of tag vN and saves it as a NEW version through the same hash-checked path. History is never rewritten. `show FILE vN` previews first.

## 6. Rules agents follow (put in README and a skill)
1. Read the index, then only the topic file needed (grep by keyword).
2. Search decisions.md before asking the human a question already answered.
3. Write only through memsave.py; state the cause (conversation/incident) in `--reason` and `--link`; name yourself in `--agent`.
4. Add a fact the same turn you learn it if a future session would otherwise have to ask again. Include UTC date and who decided.
5. On STALE: re-pull, redraft, re-check. Do not retry blindly with the old draft.
6. Keep the index short; detail goes in topic files. No secrets.
7. If the platform's own memory index tool rejects stale revisions, read it right before saving and merge, same idea.

## 7. Remote mirror (GitHub), what actually works
Goal: off-machine backup and no extra context load. Preferred: a branch named `memory` in the project repo, ideally an ORPHAN branch (no code history), with the folder's files at the root. Push from a machine where `git push` works: `git remote add origin URL; git push origin HEAD:memory --tags`. A rejected non-fast-forward push is a second hash check across machines: fetch, rebase (`git pull --rebase origin memory`), re-run the memsave flow if files conflict, push again; never force-push.
Limits seen in a sandboxed cloud agent: `git push` and git-data API writes were blocked by the proxy (403), orphan branches could not be created, and the only write path was the GitHub MCP `push_files` tool, which creates the branch from the default branch (not orphan) and carries each file's full content through the agent's context, so mirroring large files costs tokens. Hence: the local folder is the source of truth, the remote branch is a mirror synced from an environment with real git (or only for small files), and the per-save safety check stays the local lock+hash.

## 8. Script source (memsave.py)
```python
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
Every change = new version vN, a git commit, and a CHANGELOG.md row (who, when, why, link, hash before->after).
Exit codes: 0 ok, 2 usage/error, 3 stale hash (conflict).
"""
import argparse, hashlib, os, subprocess, sys, time, shutil, re, tempfile

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

def target(f):
    p = os.path.normpath(os.path.join(ROOT, f))
    if not p.startswith(ROOT + os.sep) or ".git" in p.split(os.sep): sys.exit("path must be inside the memory folder")
    return p, os.path.relpath(p, ROOT)

def do_write(f, base, data, a, kind):
    p, rel = target(f)
    with Lock():
        cur = sha(p)
        if cur != base:
            print("STALE: %s changed since you hashed it (yours %s, now %s). Re-pull the file, redraft, take a new hash, retry." % (rel, base[:10], cur[:10]), file=sys.stderr)
            sys.exit(3)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p)); os.write(fd, data); os.close(fd)
        os.replace(tmp, p)
        commit(rel, cur, a.agent, a.reason, a.link, kind)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("file", nargs="?"); ap.add_argument("version", nargs="?")
    ap.add_argument("--base"); ap.add_argument("--draft"); ap.add_argument("--agent"); ap.add_argument("--reason"); ap.add_argument("--link")
    a = ap.parse_args(); init()
    if a.cmd in ("save", "append", "rollback") and not (a.agent and a.reason): sys.exit("--agent and --reason are required")
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
```

## 9. Bootstrap checklist
1. Create the folder, `git init`, set user.name/email, add `.gitignore` with `.memsave.lock`.
2. Add tools/memsave.py, README (section 6 rules), empty topic files, CHANGELOG with a v1 import row; commit and tag v1.
3. Trim the platform memory index to status + rules + pointers.
4. Install the memory-hygiene skill (section 6 as steps).
5. Test: two agents race a save (expect exit 3), redo succeeds, rollback restores.
