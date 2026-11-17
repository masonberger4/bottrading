$env:FUNNEL_OUT = "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/out"
Set-Location C:\Users\mason\bottrading\.worktrees\scb
& C:\Users\mason\bottrading\.venv\Scripts\python.exe -W ignore C:\Users\mason\bottrading\runs\weekly_rule_2026-11-12\funnel_x.py "pwhl_x=dict(week_done_levels=('pwh','pwl'),_excl=('am_mm','pm_sb'))" "off_x=dict(week_done_on_draw='off',_excl=('am_mm','pm_sb'))" *> "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/run3.log"
