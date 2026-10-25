# Starts the Claude HF order-book recorder in the background, unless it's already running.
# Launched at Windows login from the Startup folder.
$repo = Split-Path -Parent $PSScriptRoot
$running = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -match 'claude_hf record' }
if ($running) { exit 0 }
New-Item -ItemType Directory -Force (Join-Path $repo 'runs\claude_hf') | Out-Null
$env:PYTHONUNBUFFERED = '1'
Start-Process -FilePath (Join-Path $repo '.venv\Scripts\python.exe') `
    -ArgumentList '-W', 'ignore', '-m', 'claude_hf', 'record' `
    -WorkingDirectory $repo -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $repo 'runs\claude_hf\record.out.log') `
    -RedirectStandardError (Join-Path $repo 'runs\claude_hf\record.log')
