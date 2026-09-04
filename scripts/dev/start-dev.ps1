[CmdletBinding()]
param([switch]$SkipDocker, [switch]$Migrate, [switch]$Full)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $repoRoot

function Invoke-Checked {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "`n==> $Label" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

Write-Host "Starting local development preflight..." -ForegroundColor Green
Write-Host "Repository: $repoRoot"
Write-Host "No live scraping will be run."
Invoke-Checked "Install/sync dependencies" { uv sync --all-groups }
Invoke-Checked "Run Ruff" { uv run ruff check . }
Invoke-Checked "Run Mypy" { uv run mypy src/nba_data }
Invoke-Checked "Run Pytest" { uv run pytest }

if (-not $SkipDocker -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    Invoke-Checked "Start local PostgreSQL container" { docker compose up -d postgres }
    if ($Migrate -or $Full) { Invoke-Checked "Apply Alembic migrations" { uv run alembic upgrade head } }
} else {
    Write-Host "Docker checks skipped." -ForegroundColor Yellow
}
