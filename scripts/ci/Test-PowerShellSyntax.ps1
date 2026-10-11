<#
.SYNOPSIS
    Comprueba que todos los .ps1/.psm1 del repositorio se pueden analizar sin errores de sintaxis.
    No ejecuta nada ni necesita acceso a Fabric.
#>
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$files = Get-ChildItem -Path $root -Recurse -Include *.ps1, *.psm1 -File |
    Where-Object { $_.FullName -notmatch '[\\/](node_modules|\.git|\.venv)[\\/]' }
$failed = 0
foreach ($file in $files) {
    $tokens = $null; $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$errors) | Out-Null
    $rel = [IO.Path]::GetRelativePath($root, $file.FullName)
    if ($errors.Count -gt 0) {
        $failed++
        foreach ($e in $errors) { Write-Host "::error file=$rel,line=$($e.Extent.StartLineNumber)::$($e.Message)" }
    } else {
        Write-Host "OK  $rel"
    }
}
if ($failed -gt 0) { throw "$failed fichero(s) PowerShell con errores de sintaxis." }
Write-Host "$($files.Count) ficheros PowerShell analizados sin errores."
