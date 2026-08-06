$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_SQL_SERVER"
Require-Env "FABRIC_SQL_DATABASE_NAME"

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    throw "sqlcmd no está instalado. Instálalo y vuelve a ejecutar."
}

$sqlAuthArguments = Get-SqlCmdAuthArguments
$sqlAuthMode = if (Test-EnvValue "FABRIC_SQL_AUTH_MODE") { $FABRIC_SQL_AUTH_MODE.ToLowerInvariant() } else { "default" }

if ($sqlAuthMode -eq "service-principal") {
    Write-Host "Autenticación SQL: service principal. Debe existir un usuario en la base para el display name de esa identidad antes de ejecutar este script."
}

$sqlScripts = @()
$sqlScripts += Get-ChildItem -Path "database/sql/[0-8][0-9]_*.sql" | Sort-Object Name
$optionalVectorScript = "database/sql/90_optional_vector_preview.sql"
if (Test-Path -LiteralPath $optionalVectorScript) {
    $sqlScripts += Get-Item -LiteralPath $optionalVectorScript
}

foreach ($script in $sqlScripts) {
    Write-Host "Aplicando $($script.FullName)"
    $arguments = @(
        "-S", $FABRIC_SQL_SERVER,
        "-d", $FABRIC_SQL_DATABASE_NAME,
        "-C",
        "-b",
        "-i", $script.FullName
    ) + $sqlAuthArguments
    Invoke-CheckedCommand -Command "sqlcmd" -Arguments $arguments
}

Write-Host "SQL aplicado. Ejecutando smoke test..."
$smokeTestArguments = @(
    "-S", $FABRIC_SQL_SERVER,
    "-d", $FABRIC_SQL_DATABASE_NAME,
    "-C",
    "-b",
    "-i", "database/sql/99_smoke_test.sql"
) + $sqlAuthArguments
Invoke-CheckedCommand -Command "sqlcmd" -Arguments $smokeTestArguments
