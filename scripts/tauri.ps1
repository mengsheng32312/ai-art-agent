$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$tauri = Join-Path $projectRoot "frontend\node_modules\.bin\tauri.cmd"

if (-not (Test-Path -LiteralPath $tauri)) {
    throw "Tauri CLI not found. Run npm install in frontend first."
}

Push-Location $projectRoot
try {
    & $tauri @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
