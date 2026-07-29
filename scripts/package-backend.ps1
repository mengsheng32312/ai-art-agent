$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $projectRoot "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$workflowData = "$projectRoot\workflows\text-to-image.json;workflows"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Backend virtual environment not found. Create backend\.venv and install .[package] first."
}

& $python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'PyInstaller is not installed. Run: backend\.venv\Scripts\python.exe -m pip install -e "backend[package]"'
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --name "ai-art-agent-backend" `
    --paths $backend `
    --add-data $workflowData `
    --collect-all uvicorn `
    --distpath (Join-Path $backend "dist") `
    --workpath (Join-Path $backend "build\pyinstaller") `
    --specpath (Join-Path $backend "build") `
    (Join-Path $backend "desktop_entry.py")

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
