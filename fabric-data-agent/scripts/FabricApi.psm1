Set-StrictMode -Version 1.0

# Helper module for Microsoft Fabric REST API + OneLake uploads.
# Auth uses Azure CLI tokens (run `az login` first).

$script:FabricApiRoot = "https://api.fabric.microsoft.com/v1"

function Get-AzureCliAccessToken {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [string]$Resource,

        [string]$Tenant
    )

    $az = Get-Command az -ErrorAction SilentlyContinue
    if (-not $az) {
        throw "Azure CLI no está disponible. Instálalo y ejecuta 'az login' antes del despliegue."
    }

    $args = @("account", "get-access-token", "--resource", $Resource, "--query", "accessToken", "-o", "tsv")
    if ($Tenant) { $args += @("--tenant", $Tenant) }

    $token = & $az.Source @args 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($token)) {
        throw "No se pudo obtener un token para $Resource. Ejecuta 'az login' y comprueba el tenant activo."
    }

    return $token.Trim()
}

function Invoke-FabricApi {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
        [string]$Method,

        [Parameter(Mandatory)]
        [string]$Uri,

        [Parameter(Mandatory)]
        [string]$Token,

        [AllowNull()]
        [object]$Body,

        [int]$JsonDepth = 100
    )

    $headers = @{
        Authorization = "Bearer $Token"
    }

    $statusCode = 0
    $responseHeaders = $null
    $parameters = @{
        Method                  = $Method
        Uri                     = $Uri
        Headers                 = $headers
        ErrorAction             = "Stop"
        StatusCodeVariable      = "statusCode"
        ResponseHeadersVariable = "responseHeaders"
    }

    if ($PSBoundParameters.ContainsKey("Body") -and $null -ne $Body) {
        $parameters.ContentType = "application/json; charset=utf-8"
        $parameters.Body = if ($Body -is [string]) {
            $Body
        }
        else {
            $Body | ConvertTo-Json -Depth $JsonDepth -Compress
        }
    }

    try {
        $result = Invoke-RestMethod @parameters
    }
    catch {
        $details = $_.ErrorDetails.Message
        if ([string]::IsNullOrWhiteSpace($details)) {
            $details = $_.Exception.Message
        }
        throw "Fabric API $Method $Uri falló: $details"
    }

    [pscustomobject]@{
        StatusCode = [int]$statusCode
        Headers    = $responseHeaders
        Body       = $result
    }
}

function Wait-FabricOperation {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [psobject]$InitialResponse,

        [Parameter(Mandatory)]
        [string]$Token,

        [int]$TimeoutSeconds = 1800
    )

    if ($InitialResponse.StatusCode -ne 202) {
        return $InitialResponse.Body
    }

    $location = $InitialResponse.Headers.Location | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($location)) {
        throw "Fabric devolvió 202 sin cabecera Location."
    }

    $retryAfter = 5
    if ($InitialResponse.Headers."Retry-After") {
        $retryAfter = [Math]::Max(2, [int]($InitialResponse.Headers."Retry-After" | Select-Object -First 1))
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds ([Math]::Min($retryAfter, 30))
        $poll = Invoke-FabricApi -Method GET -Uri $location -Token $Token
        $state = [string]$poll.Body.status

        if ($state -in @("Succeeded", "Completed")) {
            if ($location -match "/operations/[0-9a-f-]+$" -and $state -eq "Succeeded") {
                try {
                    return (Invoke-FabricApi -Method GET -Uri "$location/result" -Token $Token).Body
                }
                catch {
                    return $poll.Body
                }
            }
            return $poll.Body
        }

        if ($state -in @("Failed", "Cancelled", "Canceled", "Disabled")) {
            $reason = if ($poll.Body.failureReason) { $poll.Body.failureReason } elseif ($poll.Body.error) { $poll.Body.error } else { $poll.Body }
            throw "La operación de Fabric terminó en estado ${state}: $($reason | ConvertTo-Json -Depth 20 -Compress)"
        }

        if ($poll.Headers."Retry-After") {
            $retryAfter = [Math]::Max(2, [int]($poll.Headers."Retry-After" | Select-Object -First 1))
        }
    }

    throw "Tiempo de espera agotado al consultar $location."
}

function Wait-FabricWorkspaceCapacity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorkspaceId,
        [Parameter(Mandatory)][string]$CapacityId,
        [Parameter(Mandatory)][string]$Token,
        [int]$TimeoutSeconds = 300
    )

    # A diferencia de la creación de items, assignToCapacity devuelve 202 sin
    # cabecera Location (no expone una operación consultable): hay que sondear
    # el propio workspace hasta que capacityId refleje el cambio.
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ($true) {
        $workspace = (Invoke-FabricApi -Method GET -Uri "$script:FabricApiRoot/workspaces/$WorkspaceId" -Token $Token).Body
        if ($workspace.capacityId -ieq $CapacityId) {
            return $workspace
        }
        if ((Get-Date) -ge $deadline) {
            throw "Tiempo de espera agotado esperando a que el workspace $WorkspaceId quede asignado a la capacidad $CapacityId."
        }
        Start-Sleep -Seconds 5
    }
}

function Get-FabricCapacityByName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$DisplayName,
        [Parameter(Mandatory)][string]$Token
    )

    $uri = "$script:FabricApiRoot/capacities"
    while ($uri) {
        $response = Invoke-FabricApi -Method GET -Uri $uri -Token $Token
        $match = @($response.Body.value) | Where-Object { $_.displayName -ieq $DisplayName } | Select-Object -First 1
        if ($match) { return $match }
        $uri = [string]$response.Body.continuationUri
    }
    return $null
}

function Get-FabricWorkspaceByName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$DisplayName,
        [Parameter(Mandatory)][string]$Token
    )

    $uri = "$script:FabricApiRoot/workspaces"
    while ($uri) {
        $response = Invoke-FabricApi -Method GET -Uri $uri -Token $Token
        $values = if ($response.Body.value) { @($response.Body.value) } else { @($response.Body.workspaces) }
        $match = $values | Where-Object { $_.displayName -ceq $DisplayName -or $_.name -ceq $DisplayName } | Select-Object -First 1
        if ($match) { return $match }
        $uri = [string]$response.Body.continuationUri
    }
    return $null
}

function Get-FabricItemByName {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$WorkspaceId,
        [Parameter(Mandatory)][string]$Type,
        [Parameter(Mandatory)][string]$DisplayName,
        [Parameter(Mandatory)][string]$Token
    )

    $uri = "$script:FabricApiRoot/workspaces/$WorkspaceId/items?type=$([Uri]::EscapeDataString($Type))"
    while ($uri) {
        $response = Invoke-FabricApi -Method GET -Uri $uri -Token $Token
        $match = @($response.Body.value) | Where-Object { $_.displayName -ceq $DisplayName } | Select-Object -First 1
        if ($match) { return $match }
        $uri = [string]$response.Body.continuationUri
    }
    return $null
}

function ConvertTo-EncodedOneLakePath {
    param([Parameter(Mandatory)][string]$Path)
    return (($Path -split "/" | Where-Object { $_ -ne "" } | ForEach-Object { [Uri]::EscapeDataString($_) }) -join "/")
}

function New-OneLakeDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$DfsEndpoint,
        [Parameter(Mandatory)][string]$WorkspaceId,
        [Parameter(Mandatory)][string]$LakehouseId,
        [Parameter(Mandatory)][string]$DirectoryPath,
        [Parameter(Mandatory)][string]$Token
    )

    $encoded = ConvertTo-EncodedOneLakePath -Path $DirectoryPath
    $uri = "$($DfsEndpoint.TrimEnd('/'))/$WorkspaceId/$LakehouseId/$encoded`?resource=directory"
    $headers = @{
        Authorization  = "Bearer $Token"
        "x-ms-version" = "2021-06-08"
    }

    try {
        Invoke-WebRequest -Method PUT -Uri $uri -Headers $headers -ErrorAction Stop | Out-Null
    }
    catch {
        $status = [int]$_.Exception.Response.StatusCode
        if ($status -ne 409) {
            throw "No se pudo crear el directorio OneLake '$DirectoryPath': $($_.Exception.Message)"
        }
    }
}

function Set-OneLakeFile {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$DfsEndpoint,
        [Parameter(Mandatory)][string]$WorkspaceId,
        [Parameter(Mandatory)][string]$LakehouseId,
        [Parameter(Mandatory)][string]$OneLakePath,
        [Parameter(Mandatory)][string]$LocalPath,
        [Parameter(Mandatory)][string]$Token
    )

    if (-not (Test-Path -LiteralPath $LocalPath -PathType Leaf)) {
        throw "No existe el archivo local: $LocalPath"
    }

    $parent = Split-Path -Path ($OneLakePath -replace "/", [IO.Path]::DirectorySeparatorChar) -Parent
    $segments = ($parent -replace "\\", "/") -split "/" | Where-Object { $_ }
    $current = ""
    foreach ($segment in $segments) {
        $current = if ($current) { "$current/$segment" } else { $segment }
        New-OneLakeDirectory -DfsEndpoint $DfsEndpoint -WorkspaceId $WorkspaceId -LakehouseId $LakehouseId -DirectoryPath $current -Token $Token
    }

    $encodedPath = ConvertTo-EncodedOneLakePath -Path $OneLakePath
    $baseUri = "$($DfsEndpoint.TrimEnd('/'))/$WorkspaceId/$LakehouseId/$encodedPath"
    $headers = @{
        Authorization  = "Bearer $Token"
        "x-ms-version" = "2021-06-08"
    }

    Invoke-WebRequest -Method PUT -Uri "$baseUri`?resource=file" -Headers $headers -ErrorAction Stop | Out-Null

    $length = (Get-Item -LiteralPath $LocalPath).Length
    if ($length -gt 0) {
        Invoke-WebRequest -Method PATCH -Uri "$baseUri`?action=append&position=0" -Headers $headers -InFile $LocalPath -ContentType "application/octet-stream" -ErrorAction Stop | Out-Null
    }
    Invoke-WebRequest -Method PATCH -Uri "$baseUri`?action=flush&position=$length" -Headers $headers -ContentType "application/octet-stream" -ErrorAction Stop | Out-Null
}

Export-ModuleMember -Function @(
    "Get-AzureCliAccessToken",
    "Invoke-FabricApi",
    "Wait-FabricOperation",
    "Wait-FabricWorkspaceCapacity",
    "Get-FabricCapacityByName",
    "Get-FabricWorkspaceByName",
    "Get-FabricItemByName",
    "New-OneLakeDirectory",
    "Set-OneLakeFile"
)
