param(
    [string]$ReturnCaseId = "RET-2026-004219",
    [string]$Question = "El cliente Gold quiere devolver un sofá modular comprado online hace 34 días. Indica que llegó con una pata dañada, conserva fotos del embalaje y solicita reemplazo urgente. ¿Debemos aprobar devolución, reemplazo o revisión manual?",
    [int]$TopN = 8
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_SQL_SERVER"
Require-Env "FABRIC_SQL_DATABASE_NAME"

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    throw "sqlcmd no está instalado. Instálalo y vuelve a ejecutar."
}

$procArguments = @(
    "-S", $FABRIC_SQL_SERVER,
    "-d", $FABRIC_SQL_DATABASE_NAME,
    "-C",
    "-b",
    "-i", "database/sql/07_create_hybrid_search.sql"
) + (Get-SqlCmdAuthArguments)

Invoke-CheckedCommand -Command "sqlcmd" -Arguments $procArguments

$outPath = "database/generated/hybrid_search_query.sql"
$outDir = Split-Path -Parent $outPath
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

Invoke-CheckedCommand -Command "python" -Arguments @(
    "tools/render_hybrid_search_sql.py",
    "--out", $outPath,
    "--return-case-id", $ReturnCaseId,
    "--question", $Question,
    "--top-n", "$TopN"
)

$arguments = @(
    "-S", $FABRIC_SQL_SERVER,
    "-d", $FABRIC_SQL_DATABASE_NAME,
    "-C",
    "-b",
    "-i", $outPath
) + (Get-SqlCmdAuthArguments)

Invoke-CheckedCommand -Command "sqlcmd" -Arguments $arguments
