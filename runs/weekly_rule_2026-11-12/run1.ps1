$env:FUNNEL_OUT = "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/out"
Set-Location C:\Users\mason\bottrading\.worktrees\scb
& C:\Users\mason\bottrading\.venv\Scripts\python.exe -W ignore C:\Users\mason\bottrading\runs\trade_count_2026-11-11\funnel.py "wd_nearest=dict(week_done_on_draw='skip',week_done_pick='nearest',week_done_levels=('pwh','pwl'))" "wd_pwhl=dict(week_done_on_draw='skip',week_done_levels=('pwh','pwl'))" *> "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/run1.log"
