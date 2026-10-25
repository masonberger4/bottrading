# Keeps the Silver Bullet SPY paper bot (simulated fills, never sends orders) running.
# Started at Windows logon by the "Silver Bullet paper bot" scheduled task; restarts the
# bot a minute after it exits. Output is appended to paper_log.txt.
Set-Location $PSScriptRoot
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONWARNINGS = 'ignore'
$log = Join-Path $PSScriptRoot 'paper_log.txt'

function Test-BotRunning {
    @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
      Where-Object { $_.CommandLine -match 'silver_bullet paper' }).Count -gt 0
}

while ($true) {
    if (-not (Test-BotRunning)) {
        Add-Content $log "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') starting paper bot ==="
        cmd /c ".venv\Scripts\python -m silver_bullet paper --symbol SPY < NUL >> paper_log.txt 2>&1"
        Add-Content $log "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') paper bot exited (code $LASTEXITCODE), restarting in 60s ==="
    }
    Start-Sleep -Seconds 60
}
