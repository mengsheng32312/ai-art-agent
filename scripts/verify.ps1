$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $projectRoot "backend")
try {
    & ".\.venv\Scripts\python.exe" -m pytest tests -v
} finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm run build
} finally {
    Pop-Location
}
