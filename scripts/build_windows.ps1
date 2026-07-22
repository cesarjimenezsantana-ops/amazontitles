param(
    [string]$AppVersion = "1.1.1"
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "build_windows_electron.ps1") -AppVersion $AppVersion
