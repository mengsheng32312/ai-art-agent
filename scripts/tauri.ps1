$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$tauri = Join-Path $projectRoot "frontend\node_modules\.bin\tauri.cmd"

function Add-PathFirst {
    param([Parameter(Mandatory = $true)][string]$PathToAdd)

    if (-not (Test-Path -LiteralPath $PathToAdd)) {
        return
    }

    $parts = @($env:Path -split ';' | Where-Object { $_ -and $_ -ne $PathToAdd })
    $env:Path = (@($PathToAdd) + $parts) -join ';'
}

function Test-WorkingCargo {
    $cargo = Get-Command cargo -ErrorAction SilentlyContinue
    if (-not $cargo) {
        return $false
    }

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $cargo.Source --version *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Use-StandaloneRustIfNeeded {
    if (Test-WorkingCargo) {
        return
    }

    $cargo = Get-Command cargo -ErrorAction SilentlyContinue
    $cargoUserHome = $null
    if ($cargo -and $cargo.Source -match '\\\.cargo\\bin\\cargo\.exe$') {
        $cargoUserHome = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $cargo.Source))
    }

    $candidateRoots = @(
        $(if ($cargoUserHome) { Join-Path $cargoUserHome "AppData\Local\Programs\Rust stable MSVC 1.97\bin" }),
        $(if ($cargoUserHome) { Join-Path $cargoUserHome "AppData\Local\Programs\Rust stable MSVC\bin" }),
        "C:\Users\19213\AppData\Local\Programs\Rust stable MSVC 1.97\bin",
        (Join-Path $env:LOCALAPPDATA "Programs\Rust stable MSVC 1.97\bin"),
        (Join-Path $env:LOCALAPPDATA "Programs\Rust stable MSVC\bin"),
        "C:\Program Files\Rust stable MSVC 1.97\bin",
        "C:\Program Files\Rust stable MSVC\bin"
    ) | Where-Object { $_ }

    foreach ($candidate in $candidateRoots) {
        $candidateCargo = Join-Path $candidate "cargo.exe"
        $candidateRustc = Join-Path $candidate "rustc.exe"
        if ((Test-Path -LiteralPath $candidateCargo) -and (Test-Path -LiteralPath $candidateRustc)) {
            Add-PathFirst $candidate
            $env:RUSTC = $candidateRustc
            $env:RUSTDOC = Join-Path $candidate "rustdoc.exe"
            if (Test-WorkingCargo) {
                Write-Host "Using Rust toolchain: $candidate"
                return
            }
        }
    }

    throw "Cargo is not usable. Install Rust stable MSVC, or fix rustup with: rustup default stable"
}

function Import-VisualStudioEnvironment {
    $cl = Get-Command cl.exe -ErrorAction SilentlyContinue
    if ($cl) {
        return
    }

    $vsDevCmdCandidates = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Professional\Common7\Tools\VsDevCmd.bat",
        "${env:ProgramFiles}\Microsoft Visual Studio\2022\Enterprise\Common7\Tools\VsDevCmd.bat"
    )

    $vsDevCmd = $vsDevCmdCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $vsDevCmd) {
        return
    }

    $environmentLines = & cmd.exe /s /c "`"$vsDevCmd`" -arch=x64 -host_arch=x64 >nul && set"
    if ($LASTEXITCODE -ne 0) {
        return
    }

    foreach ($line in $environmentLines) {
        $separator = $line.IndexOf('=')
        if ($separator -le 0) {
            continue
        }

        $name = $line.Substring(0, $separator)
        $value = $line.Substring($separator + 1)
        Set-Item -Path "Env:$name" -Value $value
    }

    Write-Host "Using Visual Studio build environment: $vsDevCmd"
}

function Ensure-BackendEnvironment {
    $backend = Join-Path $projectRoot "backend"
    $python = Join-Path $backend ".venv\Scripts\python.exe"

    if (-not (Test-Path -LiteralPath $python)) {
        $systemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $systemPython) {
            throw "Python is not available. Install Python 3.11 or newer."
        }
        & $systemPython.Source -m venv (Join-Path $backend ".venv")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create the backend virtual environment."
        }
    }

    & $python -c "import fastapi, httpx, multipart, pydantic, uvicorn" 2>$null
    if ($LASTEXITCODE -eq 0) {
        return
    }

    Write-Host "Installing backend dependencies..."
    & $python -m pip install -e $backend
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install backend dependencies."
    }
}

if (-not (Test-Path -LiteralPath $tauri)) {
    throw "Tauri CLI not found. Run npm install in frontend first."
}

Use-StandaloneRustIfNeeded
Import-VisualStudioEnvironment
Ensure-BackendEnvironment

Push-Location $projectRoot
try {
    & $tauri @args
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
