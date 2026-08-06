$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_WORKSPACE_NAME"
Require-Env "FABRIC_SQL_DATABASE_NAME"

$target = "$FABRIC_WORKSPACE_NAME.Workspace/$FABRIC_SQL_DATABASE_NAME.SQLDatabase"

Write-Host "Comprobando SQL Database: $target"
& fab get $target *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "SQL Database ya existe: $target"
}
else {
    Write-Host "Creando SQL Database: $target"
    Invoke-CheckedCommand -Command "fab" -Arguments @("create", $target)
}

Write-Host "SQL Database lista. Copia el TDS endpoint desde Fabric > SQL Database > Settings > Connection strings."
Write-Host "Actualiza FABRIC_SQL_SERVER en .env antes de ejecutar scripts/apply_sql.ps1"
