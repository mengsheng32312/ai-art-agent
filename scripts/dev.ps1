$projectRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $projectRoot "backend"
$frontend = Join-Path $projectRoot "frontend"

Start-Process -WindowStyle Hidden -WorkingDirectory $backend -FilePath (Join-Path $backend ".venv\Scripts\python.exe") -ArgumentList "-m", "uvicorn", "app.main:app", "--reload"
Start-Process -WindowStyle Hidden -WorkingDirectory $frontend -FilePath "npm.cmd" -ArgumentList "run", "dev"
