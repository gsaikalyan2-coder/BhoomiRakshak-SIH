# BhoomiRakshak - point .env at the shared Supabase database.
#
#   cd "C:\Users\saika\Land Acquisition"
#   powershell -ExecutionPolicy Bypass -File .\scripts\use_supabase.ps1
#
# Prompts for the connection string from the Supabase dashboard's Connect button,
# validates it, converts it to the SQLAlchemy driver form, and rewrites .env.
# The previous .env is backed up so the local-docker demo path can be restored
# with scripts\use_local.ps1.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Supabase Connect -> Session pooler -> copy the URI." -ForegroundColor Cyan
Write-Host "It looks like:" -ForegroundColor DarkGray
Write-Host "  postgresql://postgres.tayflaukyjtcsyuivpxl:YOURPASSWORD@aws-1-ap-south-1.pooler.supabase.com:5432/postgres" -ForegroundColor DarkGray
Write-Host ""

$uri = Read-Host "Paste the session pooler URI"
$uri = $uri.Trim().Trim('"').Trim("'")

if ([string]::IsNullOrWhiteSpace($uri)) { Write-Host "Nothing pasted." -ForegroundColor Red; exit 1 }

# --- validate -----------------------------------------------------------------
if ($uri -notmatch '^postgres(ql)?(\+psycopg)?://') {
    Write-Host "ERROR: that does not start with postgresql:// - paste the URI, not the psql command." -ForegroundColor Red
    exit 1
}
if ($uri -match ':6543/') {
    Write-Host "ERROR: port 6543 is the TRANSACTION pooler. Alembic needs the SESSION pooler on 5432." -ForegroundColor Red
    exit 1
}
if ($uri -match '@db\.[a-z0-9]+\.supabase\.co') {
    Write-Host "ERROR: that is the DIRECT connection, which is IPv6-only on the free tier and will time out." -ForegroundColor Red
    Write-Host "       Go back and choose 'Session pooler'." -ForegroundColor Red
    exit 1
}
if ($uri -match '\[YOUR-PASSWORD\]' -or $uri -match '\[PASSWORD\]') {
    Write-Host "ERROR: the password placeholder is still in the string. Replace it with the real password" -ForegroundColor Red
    Write-Host "       (Project Settings -> Database -> Reset database password)." -ForegroundColor Red
    exit 1
}
if ($uri -notmatch 'pooler\.supabase\.com') {
    Write-Host "WARNING: host does not look like a Supabase pooler. Continuing anyway." -ForegroundColor Yellow
}

# --- SQLAlchemy needs the driver named explicitly, or it reaches for psycopg2 --
if ($uri -notmatch '\+psycopg://') {
    $uri = $uri -replace '^postgresql://', 'postgresql+psycopg://'
    $uri = $uri -replace '^postgres://',   'postgresql+psycopg://'
    Write-Host "Rewrote the scheme to postgresql+psycopg:// for SQLAlchemy." -ForegroundColor DarkGray
}

# --- pull the parts back out for the POSTGRES_* lines -------------------------
if ($uri -notmatch '^postgresql\+psycopg://([^:]+):([^@]+)@([^:/]+):(\d+)/(.+)$') {
    Write-Host "ERROR: could not parse the URI into user/password/host/port/database." -ForegroundColor Red
    Write-Host "       If the password contains @ : / # or ?, percent-encode it, or reset it to an" -ForegroundColor Red
    Write-Host "       alphanumeric one in the dashboard." -ForegroundColor Red
    exit 1
}
$user = $Matches[1]; $pass = $Matches[2]; $dbHost = $Matches[3]; $port = $Matches[4]; $dbName = $Matches[5]

# --- back up, then rewrite ----------------------------------------------------
if (Test-Path ".env") {
    $backup = ".env.local-docker.bak"
    Copy-Item ".env" $backup -Force
    Write-Host "Previous .env backed up to $backup" -ForegroundColor DarkGray
}

$lines = Get-Content ".env"
$out = foreach ($line in $lines) {
    switch -Regex ($line) {
        '^POSTGRES_HOST='  { "POSTGRES_HOST=$dbHost";  break }
        '^POSTGRES_PORT='  { "POSTGRES_PORT=$port";    break }
        '^POSTGRES_DB='    { "POSTGRES_DB=$dbName";    break }
        '^POSTGRES_USER='  { "POSTGRES_USER=$user";    break }
        '^POSTGRES_PASSWORD=' { "POSTGRES_PASSWORD=$pass"; break }
        '^DATABASE_URL='   { "DATABASE_URL=$uri";      break }
        default            { $line }
    }
}
Set-Content ".env" $out -Encoding UTF8

Write-Host ""
Write-Host "Wrote .env -> $dbHost`:$port/$dbName as $user" -ForegroundColor Green
Write-Host ""
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe -m alembic upgrade head"
Write-Host "  .\.venv\Scripts\python.exe scripts\seed.py --truncate"
Write-Host "  .\.venv\Scripts\python.exe scripts\verify_phase1.py"
