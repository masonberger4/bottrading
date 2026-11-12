$env:FUNNEL_OUT = "C:/Users/mason/bottrading/runs/trade_count_2026-11-11/out_fn"
$env:FUNNEL_YEARS = "2021,2024"
Set-Location C:\Users\mason\bottrading\.worktrees\scb
& C:\Users\mason\bottrading\.venv\Scripts\python.exe -W ignore C:\Users\mason\bottrading\runs\trade_count_2026-11-11\funnel.py @args *> "$env:TEMP\bt\funnel2.log"
