# Versioned agent-memory system: build spec

Purpose: give any repo's AI agents a shared, durable memory that is (a) small to load, (b) versioned with a rollback path, (c) annotated with who changed what and why, and (d) safe against two agents overwriting each other. Project-neutral; adapt names freely, keep the behaviors.

## 1. Layout
```
MEMORY.md (or your platform's memory index)   short index, <3 KB: current status, standing rules, pointers
memory/                                       shared folder, one git repo
  README.md          how agents read and write (section 6 rules)
  ACL.json           writers list (section 6b); scratch/<agent>/ free per agent; proposals/ for requested changes
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

## 6b. Permissions (who may write what)
`ACL.json` lists "writers" (Mase, coordinator, named curator threads). Rules, enforced by `memsave.py` (refusal = "DENIED", exit 4):
- Top-level files (index topic files, README, ACL.json, tools/, skill_drafts/): writers only. Everyone else reads.
- `scratch/<your-slug>/`: your own free scratch pad. Edit it any time with `memsave.py save scratch/<slug>/FILE --base $(memsave.py hash ...) ...` (unversioned, git-ignored). Slug = your thread name lowercased, non-alphanumerics to "-" (e.g. "Run full backtests in cloud" -> run-full-backtests-in-cloud). Other agents' scratch pads are not yours to edit.
- Want a top-level change? `echo "text" | python3 tools/memsave.py propose decisions.md --agent "<you>" --reason "why" --link "..."` creates versioned `proposals/<slug>__decisions.md`. A writer reviews, merges with `save`, and notes "merged vN" in the proposal.
- `python3 tools/memsave.py verify` lists any file edited outside the tool (exit 5).
Honest limits: identity is self-declared via --agent (not authenticated); the shared mount ignores chmod so file permissions cannot enforce read-only; a raw `echo >> file` works but `verify` and git expose it and `rollback` repairs it; the platform project-memory index tool is writable by every thread and cannot be restricted by us.
ACL.json example: {"writers": ["Human", "coordinator", "curator-thread"]}. Lock files and scratch/ go in .gitignore.

## 7. Remote store (GitHub) and the platform index
Goal: an enforced read-only store that agents cannot bypass, plus off-machine backup, without loading history into agent context.
1. One-time seed (human, on a machine where `git push` works): create an ORPHAN branch `memory` holding the memory folder at its root (`memsave.py bundle` writes `memory-export/memory.bundle`; `git fetch memory.bundle memory:memory-seed; git push origin memory-seed:refs/heads/memory`). Do not push tags.
2. Lock it: repo Settings > Rules > Rulesets > New branch ruleset; enforcement Active; target pattern `memory`; empty bypass list; rules: Restrict updates, Restrict deletions, Block force pushes. To merge a reviewed change the human sets enforcement to Disabled, merges, sets it back to Active.
3. Agents change top-level memory by pull request: create a branch from `memory`, push changed files, open PR into `memory`. Agents cannot merge. (Caveat: if agents authenticate as the same GitHub user as the human, "require PR/approval" rules cannot tell them apart, which is why the ruleset blocks all updates and the human unlocks it.)
4. The folder is a mirror: `memsave.py sync` fetches and fast-forwards; reports AHEAD (local writer edits not yet on GitHub) or DIVERGED (exit 6, writer reconciles).
5. Platform memory index: if it cannot be permissioned, add a project rule that only the human and coordinator write it, keep an approved copy in `INDEX.md`, and have the coordinator run `memsave.py indexcheck LIVEFILE` regularly (exit 7 = drift; restore). A rule can be ignored by a misbehaving agent; the drift check is what catches it.
Sandbox limits seen: cloud agents had read-only git (fetch works; push and git-data API writes returned 403), so seeding and unlocking need the human; the GitHub MCP file-push tool creates branches from the default branch (not orphan) and passes file content through agent context, so use it only for small proposal PRs.

## 8. Script source (memsave.py)
```python
#!/usr/bin/env python3
"""memsave.py - versioned, hash-checked saves for the project memory folder.

Usage (run from anywhere; paths are relative to the memory folder):
  memsave.py hash FILE                      print sha256 of FILE (take this BEFORE drafting)
  memsave.py save FILE --base HASH --draft DRAFTFILE --agent WHO --reason WHY [--link URL]
        re-hashes FILE under a lock; if it differs from HASH -> exit 3 (STALE): re-pull, redraft, retry.
  memsave.py append FILE --base HASH --agent WHO --reason WHY [--link URL]   (text on stdin; same check)
  memsave.py sync                           fetch GitHub branch `memory`; fast-forward this folder, or report AHEAD/DIVERGED
  memsave.py indexcheck LIVEFILE            compare live project-memory index text (in LIVEFILE) with INDEX.md; exit 7 on drift
  memsave.py bundle                         write /mnt/project-files/memory-export/memory.bundle (for a one-time seed push from a machine with git push)
  memsave.py verify                         exit 5 + list if any file was edited outside this tool (raw writes)
  memsave.py log [FILE]                     version history
  memsave.py show FILE VERSION              print FILE as of version (e.g. v3)
  memsave.py rollback FILE VERSION --agent WHO --reason WHY [--link URL]   restore as a NEW version
  memsave.py propose FILE --agent WHO --reason WHY [--link URL]   (proposed text on stdin) -> proposals/<agent>__<file>.md
Permissions (ACL.json): top-level files are writable only by ACL "writers"; scratch/<agent>/ is free for that agent
(unversioned, git-ignored); proposals/<agent>__* is free for that agent. Violations exit 4 (DENIED).
Every change = new version vN, a git commit, and a CHANGELOG.md row (who, when, why, link, hash before->after).
Exit codes: 0 ok, 2 usage/error, 3 stale hash (conflict), 4 DENIED by ACL, 5 verify found raw edits, 6 DIVERGED.
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

def vref(v):
    """tag vN if present, else the commit whose subject starts 'vN ' (tags are local-only)."""
    r = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "rev-parse", "-q", "--verify", v + "^{commit}"], capture_output=True, text=True)
    if r.returncode == 0: return v
    out = git("log", "--format=%H", "--grep", "^%s " % v, "-1", check=False).strip()
    if not out: sys.exit("unknown version " + v)
    return out

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
    elif a.cmd == "sync":
        # GitHub branch `memory` is the approved store; this folder is a working mirror.
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "fetch", "-q", "origin", "memory"], capture_output=True, text=True)
        if r.returncode: sys.exit("fetch failed: " + r.stderr.strip())
        def anc(x, y): return subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "merge-base", "--is-ancestor", x, y]).returncode == 0
        if anc("FETCH_HEAD", "HEAD"):
            n = git("rev-list", "--count", "FETCH_HEAD..HEAD").strip()
            print("IN SYNC" if n == "0" else "AHEAD: %s local version(s) not on GitHub; propose them by PR (see README)" % n)
        elif anc("HEAD", "FETCH_HEAD"):
            if git("status", "--porcelain").strip(): sys.exit("local files edited outside the tool; run verify first")
            git("merge", "-q", "--ff-only", "FETCH_HEAD"); print("UPDATED folder from GitHub branch memory")
        else:
            print("DIVERGED: local and GitHub both have new versions; a writer must reconcile", file=sys.stderr); sys.exit(6)
    elif a.cmd == "indexcheck":
        # drift check: compare the live project-memory index (saved by caller to a file) with INDEX.md
        import difflib
        live = open(a.file).read().strip().splitlines(); want = open(os.path.join(ROOT, "INDEX.md")).read().strip().splitlines()
        d = list(difflib.unified_diff(want, live, "INDEX.md (approved)", "live index", lineterm=""))
        print("NO DRIFT" if not d else "DRIFT: restore the live index to INDEX.md text:\n" + "\n".join(d)); sys.exit(0 if not d else 7)
    elif a.cmd == "bundle":
        out = "/mnt/project-files/memory-export/memory.bundle"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        git("bundle", "create", out, "--branches"); print("wrote " + out)
    elif a.cmd == "verify":
        out = git("status", "--porcelain").strip()
        print("CLEAN: every top-level file matches its last versioned save" if not out else "TAMPERED/UNSAVED (edited outside memsave):\n" + out)
        sys.exit(0 if not out else 5)
    elif a.cmd == "log":
        print(git("log", "--format=%h %s | %b", "--", a.file) if a.file else open(CHANGELOG).read())
    elif a.cmd == "show":
        sys.stdout.write(git("show", "%s:%s" % (vref(a.version), target(a.file)[1])))
    elif a.cmd == "rollback":
        p, rel = target(a.file)
        old = subprocess.run(["git", "-c", "safe.directory=*", "-C", ROOT, "show", "%s:%s" % (vref(a.version), rel)], capture_output=True)
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

## 10. Dreaming (periodic curation batch)
Goal: memory improves without agents spending turns on it. Loop (from Mase's reference diagram "How dreaming works"):
1. Agents' daily sessions produce transcripts (threads, project chat).
2. A scheduled batch, the dreamer, takes those transcripts plus the CURRENT memory state.
3. It outputs an UPDATED memory state: new insights (facts, lessons, corrected rules) and an organized structure (split/merge/archive files, one home per rule, a thin index, pointers).
4. The next sessions read that state, so they start smarter. This arrow is the part that must exist: proposals are not the end. Proposal-only until the owner approves; then a writer from ACL.json applies them with memsave save (versioned, reasoned, linked, rollback-able); the platform index is changed only by owner/coordinator; the GitHub memory branch is updated through the usual reviewed PR. Next dream measures whether merged items stopped the re-asks.
Components: (a) skill draft skill_drafts/dream.md (the prompt); (b) scratch/dreamer/cursor.json {last_dream_utc, seen{thread_id:last_message_id}} so each run reads only new transcripts; (c) proposals/dreamer__*.md plus a ranked report proposals/dreamer__dream_<date>.md; (d) ACL: the dreamer is NOT a writer; (e) trigger: routine/scheduled task, daily, or after N finished threads.
Rules: proposal-only; never reverse an owner decision (flag it); sample newest and summaries first; cap each run to the transcripts newer than the cursor; no helper agents unless the owner asks.
What it looks for: re-asked facts, repeated stalls/errors, stale/duplicate/contradicting rules, missing pointers, slow lookups, plus structure (oversized files, rules in 3+ places, drifting index).
Approval UX: the report ends with "apply D1,L2"; owner replies in thread; coordinator or a writer thread applies and writes "merged vN" in the proposal.
