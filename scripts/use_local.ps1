# BhoomiRakshak - point .env back at the local docker database (the demo path).
#
#   cd "C:\Users\saika\Land Acquisition"
#   powershell -ExecutionPolicy Bypass -File .\scripts\use_local.ps1
#
# Restores the .env that scripts\use_supabase.ps1 backed up, then starts the
# container. Run this before rehearsing the Thursday 2026-08-27 demo.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$backup = ".env.local-docker.bak"
if (-not (Test-Path $backup)) {
    Write-Host "No $backup found - nothing to restore." -ForegroundColor Red
    Write-Host "Set POSTGRES_HOST=localhost and the matching DATABASE_URL in .env by hand." -ForegroundColor Red
    exit 1
}

Copy-Item ".env" ".env.supabase.bak" -Force
Copy-Item $backup ".env" -Force
Write-Host "Restored local .env (the Supabase one is now .env.supabase.bak)." -ForegroundColor Green

Write-Host "`nStarting the database container ..." -ForegroundColor Cyan
docker compose up -d db
if ($LASTEXITCODE -ne 0) {
    Write-Host "docker compose failed - start Docker Desktop and wait for it to say Running." -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for healthy ..." -NoNewline
$healthy = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    if ((docker compose ps db 2>$null) -match "healthy") { $healthy = $true; break }
    Write-Host "." -NoNewline
}
Write-Host ""
if (-not $healthy) {
    Write-Host "Not healthy yet. Check: docker compose logs db" -ForegroundColor Red
    exit 1
}
Write-Host "Database healthy." -ForegroundColor Green
Write-Host "`nNext:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe -m alembic upgrade head"
Write-Host "  .\.venv\Scripts\python.exe scripts\seed.py --truncate"
Write-Host "  .\.venv\Scripts\python.exe scripts\verify_phase1.py"
