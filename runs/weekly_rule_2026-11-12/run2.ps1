while (Get-Process -Id 4168 -ErrorAction SilentlyContinue) { Start-Sleep 20 }
$env:FUNNEL_OUT = "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/out"
Set-Location C:\Users\mason\bottrading\.worktrees\scb
& C:\Users\mason\bottrading\.venv\Scripts\python.exe -W ignore C:\Users\mason\bottrading\runs\trade_count_2026-11-11\funnel.py "wd_off=dict(week_done_on_draw='off')" "off_stop_ext=dict(week_done_on_draw='off',ob_stop='ext')" "off_stop_wick=dict(week_done_on_draw='off',ob_stop_kind='wick')" "off_mt_close=dict(week_done_on_draw='off',mt_break='close')" "off_minrisk4=dict(week_done_on_draw='off',min_risk_pts=4.0)" *> "C:/Users/mason/bottrading/runs/weekly_rule_2026-11-12/run2.log"
