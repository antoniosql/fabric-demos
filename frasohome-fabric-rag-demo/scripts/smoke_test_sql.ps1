$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_SQL_SERVER"
Require-Env "FABRIC_SQL_DATABASE_NAME"

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    throw "sqlcmd no está instalado. Instálalo y vuelve a ejecutar."
}

$arguments = @(
    "-S", $FABRIC_SQL_SERVER,
    "-d", $FABRIC_SQL_DATABASE_NAME,
    "-C",
    "-b",
    "-i", "database/sql/99_smoke_test.sql"
) + (Get-SqlCmdAuthArguments)

Invoke-CheckedCommand -Command "sqlcmd" -Arguments $arguments
