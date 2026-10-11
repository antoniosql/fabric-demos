<#
.SYNOPSIS
    Despliega desde cero la demo 1 de Fabric AI Functions (caso FraSoHome):
    workspace, asignación a capacidad, lakehouse, carga de datos e importación del notebook.

.DESCRIPTION
    Requisitos previos:
      - Azure CLI (`az`) y haber ejecutado `az login` con un usuario que sea
        administrador de la capacidad Fabric y pueda crear workspaces.
      - PowerShell 7+ (pwsh).
      - Copiar config.example.json a config.local.json y ajustarlo si hace falta.

.EXAMPLE
    az login --tenant <tu-tenant-id>
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

$dataDir      = Join-Path $root "data"
$notebookFile = Join-Path $root "notebooks/01_ai_functions_feedback.ipynb"
$dfsEndpoint  = "https://onelake.dfs.fabric.microsoft.com"

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
        description = "Demo Fabric AI Functions - FraSoHome (Gira Speakers LatAm 2026)"
    }
    $workspace = Wait-FabricOperation -InitialResponse $resp -Token $fabricToken
}
$workspaceId = $workspace.id
Write-Host "  Workspace: $($cfg.workspaceName)  ($workspaceId)" -ForegroundColor DarkGray

# Asignar el workspace a la capacidad
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
        description = "Datos FraSoHome para la demo de AI Functions"
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

# --- 5) Importar el notebook (con el lakehouse por defecto ya asociado) -----
Write-Host "Importando el notebook '$($cfg.notebookName)'..." -ForegroundColor Cyan
$nb = Get-Content -LiteralPath $notebookFile -Raw | ConvertFrom-Json -Depth 100
if (-not $nb.metadata) { $nb | Add-Member -NotePropertyName metadata -NotePropertyValue (@{}) }
$nb.metadata.dependencies = @{
    lakehouse = @{
        default_lakehouse              = $lakehouseId
        default_lakehouse_name         = $cfg.lakehouseName
        default_lakehouse_workspace_id = $workspaceId
    }
}
$nbJson  = $nb | ConvertTo-Json -Depth 100
$payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($nbJson))

$existing = Get-FabricItemByName -WorkspaceId $workspaceId -Type "Notebook" -DisplayName $cfg.notebookName -Token $fabricToken
$definition = @{
    format = "ipynb"
    parts  = @(@{ path = "notebook-content.ipynb"; payload = $payload; payloadType = "InlineBase64" })
}

if ($existing) {
    $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/notebooks/$($existing.id)/updateDefinition" -Token $fabricToken -Body @{
        definition = $definition
    }
}
else {
    $resp = Invoke-FabricApi -Method POST -Uri "https://api.fabric.microsoft.com/v1/workspaces/$workspaceId/notebooks" -Token $fabricToken -Body @{
        displayName = $cfg.notebookName
        definition  = $definition
    }
}
Wait-FabricOperation -InitialResponse $resp -Token $fabricToken | Out-Null

# --- Resumen ---------------------------------------------------------------
Write-Host ""
Write-Host "Despliegue completado." -ForegroundColor Green
Write-Host "  Workspace : $($cfg.workspaceName)  ($workspaceId)"
Write-Host "  Lakehouse : $($cfg.lakehouseName)"
Write-Host "  Notebook  : $($cfg.notebookName)"
Write-Host "  Portal    : https://app.fabric.microsoft.com/groups/$workspaceId" -ForegroundColor Yellow
Write-Host ""
Write-Host "Abre el notebook en el portal y ejecútalo de arriba a abajo." -ForegroundColor Cyan
