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
