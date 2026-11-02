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
