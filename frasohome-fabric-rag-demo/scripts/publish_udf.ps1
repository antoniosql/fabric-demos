$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot "_env.ps1")

Require-Env "FABRIC_WORKSPACE_ID"
Require-Env "FABRIC_SQL_DATABASE_NAME"

Import-DotEnv -Path ".fabric.generated.env"

if ([string]::IsNullOrWhiteSpace($FABRIC_SQL_DATABASE_ITEM_ID)) {
    Write-Host "Resolviendo item id de SQL Database con fab api..."
    & python "scripts/get_item_ids.py" "--workspace-id" $FABRIC_WORKSPACE_ID "--sql-database-name" $FABRIC_SQL_DATABASE_NAME "--out" ".fabric.generated.env"
    Import-DotEnv -Path ".fabric.generated.env"
}

if ([string]::IsNullOrWhiteSpace($FABRIC_SQL_DATABASE_ITEM_ID)) {
    throw "No se pudo resolver FABRIC_SQL_DATABASE_ITEM_ID. Añádelo a .env o .fabric.generated.env."
}

Invoke-CheckedCommand -Command "python" -Arguments @(
    "scripts/render_udf_definition.py",
    "--workspace-id", $FABRIC_WORKSPACE_ID,
    "--sql-database-item-id", $FABRIC_SQL_DATABASE_ITEM_ID,
    "--sql-alias", $(if ([string]::IsNullOrWhiteSpace($FABRIC_UDF_SQL_ALIAS)) { "frasohomesql" } else { $FABRIC_UDF_SQL_ALIAS })
)

$sourceItemDir = "fabric/items/FrasoHome_RAG_UDF.UserDataFunction"
$stagingDir = "fabric/.deploy"
$stagingItemDir = Join-Path $stagingDir "FrasoHome_RAG_UDF.UserDataFunction"

if (Test-Path -LiteralPath $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}

New-Item -ItemType Directory -Path (Join-Path $stagingItemDir ".resources") -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceItemDir ".platform") -Destination $stagingItemDir -Force
Copy-Item -LiteralPath (Join-Path $sourceItemDir "definition.json") -Destination $stagingItemDir -Force
Copy-Item -LiteralPath (Join-Path $sourceItemDir "function_app.py") -Destination $stagingItemDir -Force
Copy-Item -LiteralPath (Join-Path $sourceItemDir ".resources/functions.json") -Destination (Join-Path $stagingItemDir ".resources/functions.json") -Force

@"
core:
  workspace_id: "$FABRIC_WORKSPACE_ID"
  repository_directory: "."
  item_type_in_scope:
    - UserDataFunction
"@ | Set-Content -LiteralPath (Join-Path $stagingDir "config.yml") -Encoding utf8

Push-Location $stagingDir
try {
    Invoke-CheckedCommand -Command "fab" -Arguments @("deploy", "--config", "config.yml")
}
finally {
    Pop-Location
}

& python "scripts/get_item_ids.py" "--workspace-id" $FABRIC_WORKSPACE_ID "--sql-database-name" $FABRIC_SQL_DATABASE_NAME "--udf-name" $(if ([string]::IsNullOrWhiteSpace($FABRIC_UDF_ITEM_NAME)) { "FrasoHome_RAG_UDF" } else { $FABRIC_UDF_ITEM_NAME }) "--out" ".fabric.generated.env"
Import-DotEnv -Path ".fabric.generated.env"

if ([string]::IsNullOrWhiteSpace($FABRIC_UDF_ITEM_ID)) {
    throw "No se pudo resolver FABRIC_UDF_ITEM_ID tras fab deploy."
}

Invoke-CheckedCommand -Command "python" -Arguments @(
    "scripts/update_udf_definition.py",
    "--workspace-id", $FABRIC_WORKSPACE_ID,
    "--udf-item-id", $FABRIC_UDF_ITEM_ID
)

Write-Host "UDF publicada con fab deploy."
Write-Host "Siguiente paso: abre el item FrasoHome_RAG_UDF en Fabric, confirma la conexión/alias y copia la URL pública de answerReturnCase en .env."
