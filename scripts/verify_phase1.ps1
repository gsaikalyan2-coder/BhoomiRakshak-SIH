# BhoomiRakshak - Phase 1 verification, Windows PowerShell.
#
#   cd "C:\Users\saika\Land Acquisition"
#   powershell -ExecutionPolicy Bypass -File .\scripts\verify_phase1.ps1
#
# Creates .venv if absent, installs the Phase 1 tooling, applies migrations, seeds,
# and runs the 17 exit checks. Safe to re-run: the venv and pip install are no-ops
# once satisfied, and seeding uses --truncate so counts never double.
#
# Flags:
#   -SkipSeed     verify only, do not reload the CSVs
#   -SkipInstall  skip the pip step (fast re-runs)

param(
    [switch]$SkipSeed,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

# The scripts print em dashes; a legacy console codepage turns that into a
# UnicodeEncodeError instead of output.
$env:PYTHONUTF8 = "1"

Set-Location (Split-Path $PSScriptRoot -Parent)
Write-Host "Repo: $(Get-Location)" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env not found. Copy .env.example to .env and fill POSTGRES_* and DATABASE_URL." -ForegroundColor Red
    exit 1
}

# --- python ------------------------------------------------------------------
$py = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3" } else { "python" }

if (-not (Test-Path ".venv")) {
    Write-Host "`nCreating .venv ..." -ForegroundColor Cyan
    Invoke-Expression "$py -m venv .venv"
}
$venvPy = ".\.venv\Scripts\python.exe"

if (-not $SkipInstall) {
    Write-Host "Installing Phase 1 tooling ..." -ForegroundColor Cyan
    & $venvPy -m pip install --quiet --upgrade pip
    & $venvPy -m pip install --quiet -r requirements-phase1.txt
    if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }
}

# --- target ------------------------------------------------------------------
$dbUrl = (Select-String -Path ".env" -Pattern '^DATABASE_URL=' | Select-Object -First 1).Line
if (-not $dbUrl) {
    Write-Host "ERROR: DATABASE_URL is not set in .env" -ForegroundColor Red
    exit 1
}
$isSupabase = $dbUrl -match "supabase"

if ($isSupabase) {
    Write-Host "`nTarget: Supabase (shared dev database)" -ForegroundColor Yellow
    if ($dbUrl -match ":6543") {
        Write-Host "ERROR: DATABASE_URL uses port 6543 (transaction pooler). Alembic needs the" -ForegroundColor Red
        Write-Host "       SESSION pooler on port 5432. Copy it from Connect -> Session pooler." -ForegroundColor Red
        exit 1
    }
    if ($dbUrl -match "@db\.") {
        Write-Host "WARNING: this looks like the direct connection, which is IPv6-only on the" -ForegroundColor Yellow
        Write-Host "         free tier and will hang. Prefer the session pooler string." -ForegroundColor Yellow
    }
} else {
    Write-Host "`nTarget: local container" -ForegroundColor Yellow
    Write-Host "Starting the database ..." -ForegroundColor Cyan
    docker compose up -d db
    if ($LASTEXITCODE -ne 0) { Write-Host "docker compose failed - is Docker Desktop running?" -ForegroundColor Red; exit 1 }

    Write-Host "Waiting for healthy ..." -NoNewline
    $healthy = $false
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 2
        if ((docker compose ps db 2>$null) -match "healthy") { $healthy = $true; break }
        Write-Host "." -NoNewline
    }
    Write-Host ""
    if (-not $healthy) { Write-Host "Database did not become healthy. Run: docker compose logs db" -ForegroundColor Red; exit 1 }
    Write-Host "Database healthy." -ForegroundColor Green
}

# --- migrate, seed, verify ---------------------------------------------------
Write-Host "`nApplying migrations ..." -ForegroundColor Cyan
& $venvPy -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Host "alembic upgrade head failed" -ForegroundColor Red; exit 1 }

if (-not $SkipSeed) {
    Write-Host "`nSeeding ..." -ForegroundColor Cyan
    & $venvPy scripts\seed.py --truncate
    if ($LASTEXITCODE -ne 0) { Write-Host "seed failed" -ForegroundColor Red; exit 1 }
}

Write-Host "`nVerifying ..." -ForegroundColor Cyan
& $venvPy scripts\verify_phase1.py
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Host "PHASE 1 VERIFIED." -ForegroundColor Green
} else {
    Write-Host "PHASE 1 NOT VERIFIED - see the FAIL lines above." -ForegroundColor Red
}
exit $code
