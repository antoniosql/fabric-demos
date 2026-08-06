$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string[]]$Arguments = @()
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "El comando falló con código ${LASTEXITCODE}: $Command $($Arguments -join ' ')"
    }
}

Invoke-CheckedCommand -Command "python" -Arguments @("-m", "pip", "install", "--upgrade", "pip")
Invoke-CheckedCommand -Command "python" -Arguments @("-m", "pip", "install", "-r", "requirements.txt")

if (Get-Command node -ErrorAction SilentlyContinue) {
    Write-Host "Node version: $(node --version)"
}
else {
    Write-Warning "Node.js no está instalado. Instala Node.js 20+ antes de desplegar la Fabric App."
}

if (Get-Command npm -ErrorAction SilentlyContinue) {
    npm --version
}
else {
    Write-Warning "npm no está instalado."
}

if (Get-Command sqlcmd -ErrorAction SilentlyContinue) {
    sqlcmd "-?" | Select-Object -First 2
}
else {
    Write-Warning "sqlcmd no está instalado. Instala sqlcmd para aplicar scripts T-SQL."
}

if (Get-Command fab -ErrorAction SilentlyContinue) {
    fab --version
}
else {
    Write-Warning "fab no está instalado o no está en el PATH."
}

Write-Host "Bootstrap finalizado. Configura FABRIC_TENANT_ID y las variables FAB_* de identidad en .env para autenticación no interactiva."
