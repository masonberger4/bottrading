# ICT video fetch/transcribe handoff (2026-11-02 16:35Z)

Steps: 1 inspect ✓ | 2 prep + clear stuck videos (in progress) | 3 download remaining playlists | 4 report counts.

State
- ict_fetch at C:\Users\mason\ict_fetch (outside the repo). Cloud "box" sync is dead since Oct 23 and won't ack.
- ffmpeg 9 rejects -vsync, so prep had failed on everything. Fixed: prep_win.py now uses -fps_mode vfr (backup: data/prep_win.py.bak_vsync).
- Mase restarted at 16:12Z. New PIDs: supervisor 5100, fetch 2928, transcribe 7044, prep 11072. Prep reprocessing 147 folders (13 done at 16:24Z, ~25 s each, ~22 MB of frames per video, no failures).
- Captions (.vtt) for 147 un-acked videos are in data/ict_captions (pushed on branch claude/project-thread-f3l2g4).
- The fetcher is paused (WAITING_SYNC) because un-acked out\ folders count toward its 8 GB cap. To un-pause: after prep finishes, ack the folders with sync_tool.py ack <PL/NN_id ...> (deletes media and keeps DONE). That needs Mase's PowerShell (the session can't delete).
- 2024 Mentorship videos 01 and 02 failed rejoin (joined file ~40% too long); not investigated. Video 03 downloaded on Nov 2.

Playlists in fetch_win.py PLAYLISTS (in order)
- PLVgHx4Z63paYhYt0DTyeBBxQomkeCEIq1 ICT Trade Executions: 71, all downloaded
- PLVgHx4Z63paasvEhegIwtiaGalrQphFg3 ICT Charter Content: 34, all downloaded
- PLVgHx4Z63paaM41aubnHOmqfeNjSAoBCV ICT 2024 Mentorship: 51, 3 downloaded
- PLVgHx4Z63paYf6xk2a8KKuf2CYJ8SX0Wy 2025 Lecture Series: 83, none
- PLVgHx4Z63paaja3GW0dYSr6y_V2Sttx4- 2026 ICT Smart Money Concept Lecture: 143, none
- Separate: PLVgHx4Z63pabpjlduWBaEsn8VMtALhjGV 2023 Mentorship: 58, all downloaded (mt23 path)
- Core Content Month 01 PLVgHx4Z63paYzh3KwUFX0UHQUf31CAEXk (8 videos) is not in the fetcher. Rulebook coverage is unverified because the rulebook sources aren't on the laptop.

Pending decisions (Mase)
- Local auto-ack (copy verified frames and captions into the repo, then clear the folder) vs cloud processing. Recommended: auto-ack. Show the diff before enabling it.
- Keep the 2026 SMC lecture playlist (143 videos)?
- Add Core Content Month 01 if it's not in the rulebook.

Update 16:45Z
- Captions re-pulled from YouTube for 11 of the 18 box-acked videos (in data/ict_captions). 7 have no YouTube captions, so they need a video re-download and local whisper: Trade Executions 01-05 (o5NP6VOfNnI TqECSMsuswI 779jcCqyldY qW0_Mxfp_Z4 7IttD8JmDIo) and 2023 Mentorship 004 (AUbdCTzc19k) and 023 (wyqayqwoIhA). Their out\ folders hold DONE+SYNCED, so the fetcher skips them; to re-fetch, delete those 7 folders (Mase) and the fetcher redownloads.
- The 2023 Mentorship playlist has 105 videos. The box did 001-049 except 004 and 023; the laptop has 004, 023 and 050-105 (58). README says 005, 016, 017 are missing from the rulebook's 102, so those 3 also need fetching.
- Core Content Month 01 IDs appear in mentorship/digests/rulebook_gaps, so it's covered.
- No-commentary videos (Mase): ICT sometimes posts silent chart videos. Before whisper on the 7 caption-less videos, check for speech (ffmpeg silencedetect, or a near-empty whisper result). For silent ones, keep all frames and write a NO_COMMENTARY marker so the rulebook uses them as chart examples, not rules. Also flag any captioned video whose .vtt is near-empty.
- Empty captions (7-byte .vtt) = no commentary: 41 of 66 Trade Executions + 2023 Mentorship 083, 088, 097. List: data/ict_no_commentary.txt. Frames are their only content; never clear them without the frames saved.

State at 19:45Z (handoff to fresh thread)
- Laptop lost power ~19:06Z; no damage. ICT Fetch auto-restarted (PIDs changed; check tasklist). Prep: 4 pending of 147.
- Auto-ack (runs/ict_autoack.py --loop 10) is running in Mase's PowerShell window and logs to runs/ict_autoack.log (UTF-16; read with iconv -f UTF-16LE). First pass is still saving (~1 min/video). It acks in one batch at the end of the pass, so out\ is still ~8.7 GB unsynced until that pass ends. Two leftover *.tmp dirs in data/ict_frames from the power loss are harmless (overwritten).
- Speech check done: all 44 empty-caption videos have no speech (data/ict_speech_check.csv). keep_hours is temporarily 336 in ict_fetch/prep_config.json; set it back to 48 (auto-ack deletes keep\ copies itself).
- The 7 caption-less folders were deleted by Mase; the fetcher re-downloads them. They need local whisper (transcribe.py handles NEEDS_TRANSCRIPT) plus a speech check.
- Still to fetch: 2023 Mentorship 005, 016, 017 (not in the laptop's mt23 list; need adding).
- Fetcher BACKOFF: YouTube "Sign in to confirm you're not a bot" on 2024 video LMi_mO3AP08, still failing after 3 retries. Likely fix: yt-dlp --cookies-from-browser in fetch_win.py (needs Mase's OK; uses his browser login). It also warns about no JS runtime (deno).
- Open with Mase: keep the 2026 SMC lecture playlist (143)? Unconfirmed.

State at 2026-11-05 19:55Z (handoff to part 3)
- Downloads working via spare Google account cookies from Firefox (Store/MSIX build). ytdlp() in ict_fetch/fetch_win.py line 119 now passes --js-runtimes node:C:/Program Files/nodejs/node.exe and --cookies-from-browser firefox:<profile> where profile = C:/Users/mason/AppData/Local/Packages/Mozilla.MozillaFirefox_jag0gd4e3s9p2/LocalCache/Roaming/Mozilla/Firefox/Profiles/qba9tt87.default-release. Backup before this: fetch_win.py.bak_firefox. Mase must stay signed in to YouTube in that Firefox (never sign out). Chrome cookies fail (DPAPI app-bound encryption).
- yt-dlp-ejs installed (pip) for JS challenges. Pacing unchanged (5-10 s/request, 20-40 s between videos). ~30 videos/hour. Before cookies the IP was bot-blocked Nov 3 08:27 to Nov 5 (fetcher STOPPED_BLOCKED twice after 8 h).
- Fetcher running by hand (supervisor run_all.py PID 6632 does NOT reliably relaunch fetch/prep; check `Get-CimInstance Win32_Process` for fetch_win.py/prep_win.py and never start duplicates). At 19:52Z: 2026 SMC at #52/143; 28 downloads since 18:23Z.
- Auto-ack loop restarted by Mase at 19:34Z in his PowerShell window (`python -u runs\ict_autoack.py --loop 10 *>> runs\ict_autoack.log`, UTF-16 log). It had been dead since Nov 3 08:34; ~27 prepped folders were waiting. If it dies, the fetcher pauses at the 8 GB unsynced cap (WAITING_SYNC); only Mase can restart it (acks delete media).
- prep_win.py fixes (all with backups in ict_fetch): .bak_enctb (-enc_time_base 1:10 for build/mt23parts: ffmpeg 9 frame-pts units), .bak_parts (2024 multi-part -> mt23parts path), .bak_teoffset (te profile adds part start_time), .bak_mt23fallback (rejoin failure falls back to parts path). Prep passes now; 1 failure left: 2025 #46 28M9ouiKmSY (only a .f251 audio part downloaded; needs re-download: delete DONE in its folder or the folder, Mase).
- Synced (captions pushed to claude/project-thread-f3l2g4 data/ict_captions/<pl>/): 2024 Mentorship 01-13; 2025 Lecture 74/83 (missing 25,35,46,59,67,69,71,79,81); 2026 SMC 001-020 partial. Remaining to fetch: 2026 SMC #53-143, 2024 Mentorship #14-51 (FAILED from cookie error, retried on next pass: restart fetch_win.py once after the pass ends with ALL DONE), 2023 Mentorship 005/016/017 (not in mt23 list yet), whisper for caption-less (2025 #35 etc., transcribe.py handles NEEDS_TRANSCRIPT).
- Rule drafting runs in parallel: after each ack batch, send newly synced video numbers + path to the coordinator (claude-code-remote send_message @parent) for the rule-drafting threads.
- PRs (20:15Z): claude/project-thread-f3l2g4 is an ORPHAN branch (no history in common with mentorship/master), so GitHub can't open PRs from it. Its files were merged into mentorship via PR #15 (branch claude/project-thread-dqjjol). ict_autoack.py still commits to f3l2g4 (the working copy's branch; don't switch it while the loop runs). To publish new captions, run `sh runs/sync_captions_pr.sh` (Git Bash): it copies data/ict_captions + this handoff onto a mentorship-based commit, pushes claude/project-thread-dqjjol, then open a PR to mentorship if none is open. Only Mase merges.
- 23:33Z: 2026 SMC fetch finished (113 DONE, 10 NEEDS_TRANSCRIPT, 20 SKIP). A restarted fetcher skips any playlist with an out\<pl>\PLAYLIST_COMPLETE marker even if items FAILED, so to retry 2024 Mentorship #14-51 (38 FAILED from the old Chrome DPAPI cookie error) that marker was renamed to PLAYLIST_COMPLETE.bak_retry and fetch_win.py was relaunched detached (Start-Process powershell -WindowStyle Minimized, python PID 12008, appends to fetch_stdout.log/fetch_stderr.log).
- 00:50Z Nov 6: transcribe.py (whisper) is NOT running, so NEEDS_TRANSCRIPT folders never reach prep/ack. Full-length ffmpeg volumedetect on all 24: 21 are digital silence (-91 dB; 2026 SMC 003 009 010 026 033 048 052 061 083 090 094 130 137, 2024 #30, 2025 #25 35 59 67 69 71 79). For those: NEEDS_TRANSCRIPT renamed .silent, 7-byte WEBVTT .vtt + NO_COMMENTARY marker + DONE written, rows added to data/ict_speech_check.csv and data/ict_no_commentary.txt (65 lines), so prep makes frames and auto-ack saves + acks them. 3 have speech and still need whisper: 2024 #15 vfqyx8BYdNo, #34 -M-RAtxB-bE, 2025 #81 IqfB1v8aNIM.
- 02:10Z Nov 6: 2024 Mentorship retry finished (#14-51 all DONE, fetcher ALL DONE). Added 5, 16, 17 to ict_fetch/mt23_list.txt (backup .bak_005016017) and relaunched fetch_win.py (python PID 12536) for 2023 Mentorship 005/016/017. Started transcribe.py detached (python PID 13756, small.en, logs transcribe_stdout/stderr.log) for the 3 caption-less videos with speech; 2025 #81 done first.
- 03:15Z Nov 6: whisper did 2024 #15, #34, 2025 #81. Found 2023 Mentorship 004/023 still FAILED from the old Chrome DPAPI error (renamed FAILED -> FAILED.bak_retry) and 2025 #46 audio-only (renamed DONE/PREP_FAILED/.f251 webm to *.bak_redl / .bak_audioonly, and 2025 PLAYLIST_COMPLETE -> .bak_retry). Relaunched fetch_win.py and transcribe.py; 004 re-downloaded as NEEDS_TRANSCRIPT (whisper). Once all three are prepped and acked, the .bak files in those folders can go.
- FINISHED 04:50Z Nov 6. Every playlist downloaded, prepped and acked (only 2023 Mentorship 004 was waiting for its next auto-ack pass). Captions in data/ict_captions: Trade Executions 66 (25 speech, 41 no-commentary), Charter Content 34, 2024 Mentorship 51 (1 no-commentary: #30), 2025 Lectures 83 (8 no-commentary), 2026 SMC 143 (13 no-commentary), 2023 Mentorship laptop share 61 (4 no-commentary). 2023 Mentorship 001-049 captions/notes came from the old box (data/mentorship/captions). Frames: data/ict_frames (1.84 GB, laptop only), plus older 2023 Mentorship frames in data/mentorship/frames (217 dirs, covers 050-060 that the box acked). No-commentary list: data/ict_no_commentary.txt (67 lines). Fetcher, whisper exited (ALL DONE); prep_win.py and auto-ack loop still idle-running. Cleanup Mase can do: *.bak_* marker files in ict_fetch\out; keep_hours back to 48 in prep_config.json.
- Mase decisions Nov 5: no auto-ack parallel speedup; no multiple YouTube accounts; no VPN/IP switching; keep downloading video (frames show chart entries/exits; 44 no-commentary Trade Executions videos are frames-only). 2026 SMC playlist kept.
