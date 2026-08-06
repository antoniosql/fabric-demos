$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_WORKSPACE_ID"
Require-Env "VITE_ENTRA_CLIENT_ID"
Require-Env "VITE_ENTRA_TENANT_ID"

if ([string]::IsNullOrWhiteSpace($VITE_UDF_FUNCTION_URL)) {
    Write-Warning "VITE_UDF_FUNCTION_URL no está configurada. La app se desplegará, pero mostrará instrucciones hasta que añadas la URL de la UDF."
}

$appDir = "app/frasohome-returnops-app"
$envLocal = @(
    "VITE_UDF_FUNCTION_URL=$VITE_UDF_FUNCTION_URL",
    "VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID",
    "VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID"
)
$envLocal | Set-Content -LiteralPath (Join-Path $appDir ".env.local") -Encoding utf8

Push-Location $appDir
try {
    Invoke-CheckedCommand -Command "npm" -Arguments @("install")
    Invoke-CheckedCommand -Command "npm" -Arguments @("run", "build")
    Write-Host "Installing Rayfin CLI locally..."
    Invoke-CheckedCommand -Command "npm" -Arguments @("install", "--save-dev", "@microsoft/rayfin-cli")
    $rayfinArguments = @("rayfin", "up", "--workspace-id", $FABRIC_WORKSPACE_ID, "--yes")
    if (Test-EnvValue "FABRIC_TENANT_ID") {
        $rayfinArguments += @("--tenant", $FABRIC_TENANT_ID)
    }
    Invoke-CheckedCommand -Command "npx" -Arguments $rayfinArguments
}
finally {
    Pop-Location
}

Write-Host "Fabric App desplegada. Ejecuta npx rayfin up status desde $appDir para ver el estado."
