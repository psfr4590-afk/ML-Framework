[CmdletBinding()]
param(
    [string]$RepoRoot = (Split-Path -Parent (Split-Path -Parent $PSCommandPath))
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)] [string]$Exe,
        [Parameter(Mandatory = $false)] [string[]]$Arguments = @()
    )

    Write-Host "`n> $Exe $($Arguments -join ' ')" -ForegroundColor Cyan
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE: $Exe $($Arguments -join ' ')"
    }
}

$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Bootstrap = Join-Path $RepoRoot "bootstrap.py"
$Pipeline = Join-Path $RepoRoot "run_pipeline.py"
$Verifier = Join-Path $RepoRoot "scripts\verify_release.py"
$SmokeConfig = Join-Path $RepoRoot "config\pipeline_config.smoke.yaml"
$Venv = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Bootstrap)) { throw "bootstrap.py not found. Expected repository root: $RepoRoot" }
if (-not (Test-Path -LiteralPath $Pipeline)) { throw "run_pipeline.py not found. Expected repository root: $RepoRoot" }
if (-not (Test-Path -LiteralPath $SmokeConfig)) { throw "Smoke config not found: $SmokeConfig" }
if (-not (Test-Path -LiteralPath $Verifier)) { throw "Release verifier not found: $Verifier" }

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher (py.exe) is not on PATH. Install Python 3.12+ with the Python Launcher enabled."
}

$pythonVersion = & py -3.12 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.12 was not found. Install it with: winget install Python.Python.3.12"
}

Write-Host "Using Python $pythonVersion" -ForegroundColor Green
Write-Host "Repository: $RepoRoot" -ForegroundColor Green

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Invoke-Step "py" @("-3.12", "-m", "venv", $Venv)
}

Invoke-Step $VenvPython @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
Invoke-Step $VenvPython @($Bootstrap, "--install")
Invoke-Step $VenvPython @($Bootstrap, "--doctor")
Invoke-Step $VenvPython @($Pipeline, "--config", $SmokeConfig, "--no-resume")
Invoke-Step $VenvPython @($Verifier)

Write-Host "`nWindows smoke verification completed successfully." -ForegroundColor Green
