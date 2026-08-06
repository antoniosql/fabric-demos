<#
.SYNOPSIS
    Despliega desde cero la demo de Fabric Data Agent (caso FraSoHome):
    workspace, asignación a capacidad, lakehouse, carga de datos e importación de los notebooks
    de setup del agente y de evaluación.

.DESCRIPTION
    Requisitos previos:
      - Azure CLI (`az`) y `az login` con un usuario administrador de la capacidad Fabric.
      - PowerShell 7+ (pwsh).
      - Copiar config.example.json a config.local.json y rellenar tenantId, subscriptionId,
        capacityResourceId y capacityName.

    Tras el despliegue, abre el notebook 00_setup_data_agent en el portal y ejecútalo para
    construir las tablas y crear/publicar el Data Agent. Luego usa 01_evaluate_agent.

.EXAMPLE
    az login --tenant <TU_TENANT_ID>
    ./scripts/deploy.ps1
#>
[CmdletBinding()]
param(
    [string]$ConfigPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot "FabricApi.psm1") -Force

# --- Configuración ---------------------------------------------------------
if (-not $ConfigPath) {
    $local = Join-Path $root "config.local.json"
    $ConfigPath = if (Test-Path $local) { $local } else { Join-Path $root "config.example.json" }
}
Write-Host "Usando configuración: $ConfigPath" -ForegroundColor Cyan
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

$dataDir     = Join-Path $root "data"
$notebookDir = Join-Path $root "notebooks"
$dfsEndpoint = "https://onelake.dfs.fabric.microsoft.com"

foreach ($k in @("tenantId", "subscriptionId", "capacityName")) {
    if ([string]::IsNullOrWhiteSpace($cfg.$k)) {
        throw "Falta '$k' en $ConfigPath. Copia config.example.json a config.local.json y complétalo."
    }
}

# --- Autenticación (Azure CLI) --------------------------------------------
Write-Host "Obteniendo tokens de acceso..." -ForegroundColor Cyan
& az account set --subscription $cfg.subscriptionId | Out-Null
$fabricToken  = Get-AzureCliAccessToken -Resource "https://api.fabric.microsoft.com" -Tenant $cfg.tenantId
$storageToken = Get-AzureCliAccessToken -Resource "https://storage.azure.com" -Tenant $cfg.tenantId

# --- 1) Resolver la capacidad ---------------------------------------------
Write-Host "Buscando la capacidad '$($cfg.capacityName)'..." -ForegroundColor Cyan
$capacity = Get-FabricCapacityByName -DisplayName $cfg.capacityName -Token $fabricToken
if (-not $capacity) {
    throw "No se encontró la capacidad '$($cfg.capacityName)'. Comprueba que existe, está activa y que tu usuario es administrador de capacidad."
}
Write-Host "  Capacidad: $($capacity.displayName)  ($($capacity.id))" -ForegroundColor DarkGray

# --- 2) Workspace ----------------------------------------------------------
Write-Host "Creando/recuperando el workspace '$($cfg.workspaceName)'..." -ForegroundColor Cyan
$workspace = Get-FabricWorkspaceByName -DisplayName $cfg.workspaceName -Token $fabricToken
if (-not $workspace) {
    $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces" -Token $fabricToken -Body @{
        displayName = $cfg.workspaceName
        description = "Demo Fabric Data Agent - FraSoHome (Gira Speakers LatAm 2026)"
    }
    $workspace = Wait-FabricOperation -InitialResponse $resp -Token $fabricToken
}
$workspaceId = $workspace.id
Write-Host "  Workspace: $($cfg.workspaceName)  ($workspaceId)" -ForegroundColor DarkGray

# Asignar el workspace a la capacidad.
# NOTA: assignToCapacity devuelve 202 SIN cabecera Location (no expone una operación
# consultable), así que sondeamos el propio workspace hasta que refleje la capacidad.
Write-Host "Asignando el workspace a la capacidad..." -ForegroundColor Cyan
$assign = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/assignToCapacity" -Token $fabricToken -Body @{
    capacityId = $capacity.id
}
if ($assign.StatusCode -eq 202) {
    Wait-FabricWorkspaceCapacity -WorkspaceId $workspaceId -CapacityId $capacity.id -Token $fabricToken | Out-Null
}

# --- 3) Lakehouse ----------------------------------------------------------
Write-Host "Creando/recuperando el lakehouse '$($cfg.lakehouseName)'..." -ForegroundColor Cyan
$lakehouse = Get-FabricItemByName -WorkspaceId $workspaceId -Type "Lakehouse" -DisplayName $cfg.lakehouseName -Token $fabricToken
if (-not $lakehouse) {
    $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/lakehouses" -Token $fabricToken -Body @{
        displayName = $cfg.lakehouseName
        description = "Datos FraSoHome (modelo retail) para el Data Agent"
    }
    $lakehouse = Wait-FabricOperation -InitialResponse $resp -Token $fabricToken
}
$lakehouseId = $lakehouse.id
Write-Host "  Lakehouse: $($cfg.lakehouseName)  ($lakehouseId)" -ForegroundColor DarkGray

# --- 4) Subir los CSV a OneLake (Files/<dataFolder>) -----------------------
Write-Host "Subiendo datos a OneLake (Files/$($cfg.dataFolder))..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath $dataDir -Filter *.csv | ForEach-Object {
    $target = "Files/$($cfg.dataFolder)/$($_.Name)"
    Write-Host "  -> $target" -ForegroundColor DarkGray
    Set-OneLakeFile -DfsEndpoint $dfsEndpoint -WorkspaceId $workspaceId -LakehouseId $lakehouseId `
        -OneLakePath $target -LocalPath $_.FullName -Token $storageToken
}

# --- 5) Importar los notebooks (con el lakehouse por defecto asociado) ------
foreach ($nbName in $cfg.notebooks) {
    Write-Host "Importando el notebook '$nbName'..." -ForegroundColor Cyan
    $notebookFile = Join-Path $notebookDir "$nbName.ipynb"
    if (-not (Test-Path $notebookFile)) { throw "No existe el notebook: $notebookFile" }

    $nb = Get-Content -LiteralPath $notebookFile -Raw | ConvertFrom-Json -Depth 100
    if (-not $nb.metadata) { $nb | Add-Member -NotePropertyName metadata -NotePropertyValue (@{}) }
    $nb.metadata.dependencies = @{
        lakehouse = @{
            default_lakehouse              = $lakehouseId
            default_lakehouse_name         = $cfg.lakehouseName
            default_lakehouse_workspace_id = $workspaceId
        }
    }
    $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(($nb | ConvertTo-Json -Depth 100)))
    $definition = @{
        format = "ipynb"
        parts  = @(@{ path = "notebook-content.ipynb"; payload = $payload; payloadType = "InlineBase64" })
    }

    $existing = Get-FabricItemByName -WorkspaceId $workspaceId -Type "Notebook" -DisplayName $nbName -Token $fabricToken
    if ($existing) {
        $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/notebooks/$($existing.id)/updateDefinition" -Token $fabricToken -Body @{
            definition = $definition
        }
    }
    else {
        $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/notebooks" -Token $fabricToken -Body @{
            displayName = $nbName
            definition  = $definition
        }
    }
    Wait-FabricOperation -InitialResponse $resp -Token $fabricToken | Out-Null
}

# --- Resumen ---------------------------------------------------------------
Write-Host ""
Write-Host "Despliegue de infraestructura completado." -ForegroundColor Green
Write-Host "  Workspace : $($cfg.workspaceName)  ($workspaceId)"
Write-Host "  Lakehouse : $($cfg.lakehouseName)"
Write-Host "  Notebooks : $($cfg.notebooks -join ', ')"
Write-Host "  Portal    : https://app.fabric.microsoft.com/groups/$workspaceId" -ForegroundColor Yellow
Write-Host ""
Write-Host "Siguiente paso: abre '00_setup_data_agent' en el portal y ejecútalo para crear tablas" -ForegroundColor Cyan
Write-Host "y crear/publicar el Data Agent. Después, usa '01_evaluate_agent' para evaluarlo." -ForegroundColor Cyan
