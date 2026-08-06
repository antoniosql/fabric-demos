$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_SQL_SERVER"
Require-Env "FABRIC_SQL_DATABASE_NAME"

if (-not (Get-Command sqlcmd -ErrorAction SilentlyContinue)) {
    throw "sqlcmd no está instalado. Instálalo y vuelve a ejecutar."
}

$sourceDir = if (Test-EnvValue "RAG_POLICY_MARKDOWN_DIR") { $RAG_POLICY_MARKDOWN_DIR } else { "docs/policies" }
$outPath = "database/generated/ingest_policy_markdown.sql"
$outDir = Split-Path -Parent $outPath
if (-not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

Invoke-CheckedCommand -Command "python" -Arguments @(
    "tools/ingest_policy_markdown.py",
    "--source-dir", $sourceDir,
    "--out", $outPath
)

$arguments = @(
    "-S", $FABRIC_SQL_SERVER,
    "-d", $FABRIC_SQL_DATABASE_NAME,
    "-C",
    "-b",
    "-i", $outPath
) + (Get-SqlCmdAuthArguments)

Invoke-CheckedCommand -Command "sqlcmd" -Arguments $arguments

$smokeTest = "database/sql/98_smoke_test_markdown_ingestion.sql"
if (Test-Path -LiteralPath $smokeTest) {
    Write-Host "Ejecutando smoke test de ingesta Markdown..."
    $smokeArguments = @(
        "-S", $FABRIC_SQL_SERVER,
        "-d", $FABRIC_SQL_DATABASE_NAME,
        "-C",
        "-b",
        "-i", $smokeTest
    ) + (Get-SqlCmdAuthArguments)
    Invoke-CheckedCommand -Command "sqlcmd" -Arguments $smokeArguments
}
