$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

& (Join-Path $PSScriptRoot "package-backend.ps1")
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
