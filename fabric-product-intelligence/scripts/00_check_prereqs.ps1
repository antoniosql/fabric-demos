param(
    [string]$EnvPath = ".env"
)

$ErrorActionPreference = "Stop"

Write-Host "Checking repository prerequisites..." -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $EnvPath)) {
    Write-Warning ".env not found. Copy .env.example to .env and fill Fabric tenant/capacity values."
}

$commands = @("python", "node", "npm", "az")
foreach ($command in $commands) {
    $found = Get-Command $command -ErrorAction SilentlyContinue
    if ($null -eq $found) {
        Write-Warning "$command was not found in PATH."
    }
    else {
        Write-Host "$command -> $($found.Source)"
    }
}

$rayfin = npm view @microsoft/rayfin-cli version 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not resolve @microsoft/rayfin-cli from npm. Check npm/network access."
}
else {
    Write-Host "@microsoft/rayfin-cli npm package available: $rayfin"
}

python -m fabric_sessions check-prereqs --env $EnvPath
