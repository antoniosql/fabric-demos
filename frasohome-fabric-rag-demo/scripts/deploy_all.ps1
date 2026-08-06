$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

& (Join-Path $PSScriptRoot "deploy_fabric_sql.ps1")

if ([string]::IsNullOrWhiteSpace($FABRIC_SQL_SERVER) -or $FABRIC_SQL_SERVER.Contains("<server>")) {
    Write-Error "Pausa necesaria: copia FABRIC_SQL_SERVER desde Connection strings de la SQL Database y vuelve a ejecutar .\scripts\deploy_all.ps1"
    exit 2
}

& (Join-Path $PSScriptRoot "apply_sql.ps1")
& (Join-Path $PSScriptRoot "publish_udf.ps1")

if ([string]::IsNullOrWhiteSpace($VITE_UDF_FUNCTION_URL)) {
    Write-Error "Pausa necesaria: copia la URL pública de answerReturnCase en VITE_UDF_FUNCTION_URL y luego ejecuta .\scripts\deploy_app.ps1"
    exit 2
}

& (Join-Path $PSScriptRoot "deploy_app.ps1")
