<#
.SYNOPSIS
    Elimina el workspace de la demo del Data Agent (y con él lakehouse, tablas, datos,
    notebooks y el propio Data Agent). No elimina la capacidad Fabric.

.EXAMPLE
    ./scripts/cleanup.ps1
#>
[CmdletBinding()]
param(
    [string]$ConfigPath,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot "FabricApi.psm1") -Force

if (-not $ConfigPath) {
    $local = Join-Path $root "config.local.json"
    $ConfigPath = if (Test-Path $local) { $local } else { Join-Path $root "config.example.json" }
}
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json

& az account set --subscription $cfg.subscriptionId | Out-Null
$fabricToken = Get-AzureCliAccessToken -Resource "https://api.fabric.microsoft.com" -Tenant $cfg.tenantId

$workspace = Get-FabricWorkspaceByName -DisplayName $cfg.workspaceName -Token $fabricToken
if (-not $workspace) {
    Write-Host "No existe el workspace '$($cfg.workspaceName)'. Nada que borrar." -ForegroundColor Yellow
    return
}

if (-not $Force) {
    $answer = Read-Host "¿Eliminar el workspace '$($cfg.workspaceName)' y todo su contenido? (escribe 'si')"
    if ($answer -ne "si") { Write-Host "Cancelado." -ForegroundColor Yellow; return }
}

Invoke-FabricApi -Method DELETE -Uri "https://api.fabric.microsoft.com/v1/workspaces/$($workspace.id)" -Token $fabricToken | Out-Null
Write-Host "Workspace '$($cfg.workspaceName)' eliminado." -ForegroundColor Green
