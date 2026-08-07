$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

Push-Location (Join-Path $projectRoot "backend")
try {
    $pytestTemp = Join-Path $projectRoot ".tmp\pytest-$PID"
    New-Item -ItemType Directory -Force -Path (Split-Path $pytestTemp) | Out-Null
    & ".\.venv\Scripts\python.exe" -m pytest tests -v `
        -p no:cacheprovider `
        --basetemp $pytestTemp
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd test -- --run
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$cargo = Get-Command cargo -ErrorAction SilentlyContinue
if ($cargo) {
    & $cargo.Source test --manifest-path (Join-Path $projectRoot "src-tauri\Cargo.toml")
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} else {
    Write-Warning "Rust/Cargo is unavailable; skipped Tauri unit tests."
}

Get-Content -Raw (Join-Path $projectRoot "src-tauri\tauri.conf.json") |
    ConvertFrom-Json |
    Out-Null

Write-Host "Available verification steps completed successfully."
