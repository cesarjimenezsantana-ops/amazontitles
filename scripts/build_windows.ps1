param(
    [string]$AppVersion = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($AppVersion)) {
    $ProjectDir = Split-Path -Parent $PSScriptRoot
    $AppVersion = (& py -3.12 -c "import sys; sys.path.insert(0, r'$ProjectDir'); from version import APP_VERSION; print(APP_VERSION)").Trim()
}
& (Join-Path $PSScriptRoot "build_windows_electron.ps1") -AppVersion $AppVersion
