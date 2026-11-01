# Memory CHANGELOG

One row per version. Roll back with `tools/memsave.py rollback FILE vN ...` (creates a new version; nothing is erased).

| version | when (UTC) | who | file | action | reason | link | hash before -> after |
|---|---|---|---|---|---|---|---|
| v1 | 2026-11-01 21:25:00Z | thread "Organize project memory into folder" (Claude) | all files | initial import | Moved 24 old memory files + MEMORY.md facts into topic files; requested by Mase | project thread cmsg_01FAHERC1Lsrg2bYtrKuRHmPAaEeNFoXfpyv66jykt6WDD | - |
| v2 | 2026-11-01 21:31:43Z | thread: Organize project memory into folder | README.md | edit (git commit failed, file written; superseded by v4) | Document versioning and hash-check workflow (Mase request) | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2vv54HUwmTNJAtbgR8PMqQ | eed6553725 -> 96153656b1 |
| v3 | 2026-11-01 21:31:44Z | thread: Organize project memory into folder | skill_drafts/memory-hygiene.md | edit (git commit failed, file written; superseded by v5) | Update skill for versioned saves | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2vv54HUwmTNJAtbgR8PMqQ | c87304304e -> 20a37e1ed5 |
| v4 | 2026-11-01 21:32:08Z | thread: Organize project memory into folder | README.md | edit | Document versioning and hash-check workflow (Mase request) | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2vv54HUwmTNJAtbgR8PMqQ | 96153656b1 -> 627f437f30 |
| v5 | 2026-11-01 21:32:09Z | thread: Organize project memory into folder | skill_drafts/memory-hygiene.md | edit | Update skill for versioned saves | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2vv54HUwmTNJAtbgR8PMqQ | 20a37e1ed5 -> 099b515fa3 |
| v6 | 2026-11-01 21:34:39Z | thread: Organize project memory into folder | MEMORY_SYSTEM_SPEC.md | edit | Project-neutral spec of the memory system for other repos (Mase request) | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2G4qzvaEW34Wka6N1WLR2M | ABSENT -> 195180d9e6 |
| v7 | 2026-11-01 21:34:58Z | thread: Organize project memory into folder | README.md | edit | Remove duplicated versioning section left by a failed first save; link spec | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmP2G4qzvaEW34Wka6N1WLR2M | 627f437f30 -> bcc60e52b9 |
| v8 | 2026-11-01 21:36:52Z | thread: Organize project memory into folder | ACL.json | edit | Add permission model: writers list (Mase request) | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmPSGxnAdrLYfjNbK5EV4eiTH | ABSENT -> ac6be684bf |
| v9 | 2026-11-01 21:36:54Z | thread: Organize project memory into folder | tools/memsave.py | edit | Enforce ACL (DENIED exit 4), scratch/, propose command, read-only file mode | project msg cmsg_01FAHERC1Lsrg2bYtrKuRHmPSGxnAdrLYfjNbK5EV4eiTH | 32ad5b9c4e -> 527016dd7b |
| v10 | 2026-11-01 21:36:56Z | thread: Run full backtests in cloud | proposals/run-full-backtests-in-cloud__decisions.md | proposal | test proposal | l | ABSENT -> 90f1f56f95 |
| v11 | 2026-11-01 21:36:57Z | Mase | lessons.md | edit | acl test edit | l | 9c4d5c2adf -> 318990d504 |
| v12 | 2026-11-01 21:37:08Z | Mase | lessons.md | rollback-to-v10 | undo ACL test line | l | 318990d504 -> 9c4d5c2adf |
| v13 | 2026-11-01 21:37:10Z | Mase | README.md | edit | verify tool still writes to 444 files | l | bcc60e52b9 -> 944222becb |
| v14 | 2026-11-01 21:37:10Z | Mase | README.md | rollback-to-v7 | revert perm test | l | 944222becb -> bcc60e52b9 |
