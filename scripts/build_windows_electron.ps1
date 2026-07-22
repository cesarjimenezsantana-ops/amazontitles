param(
    [string]$AppVersion = "1.1.1"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$VenvDir = Join-Path $ProjectDir ".build-venv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$PyInstaller = Join-Path $VenvDir "Scripts\pyinstaller.exe"

Set-Location $ProjectDir

if (-not (Test-Path $Python)) {
    py -3.12 -m venv $VenvDir
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-build.txt
& $Python packaging/create_icons.py
& $PyInstaller --noconfirm --clean packaging/FocusAmazonService.spec

if (-not (Test-Path "package-lock.json")) {
    throw "package-lock.json is required. Run npm install once before building."
}
npm ci
npm version $AppVersion --no-git-tag-version --allow-same-version
npm run electron:pack:windows

$Installer = Join-Path $ProjectDir "release\windows\FocusAmazonTools-Setup-$AppVersion.exe"
$Portable = Join-Path $ProjectDir "release\windows\FocusAmazonTools-Portable-$AppVersion-Windows-x64.exe"
if (-not (Test-Path $Installer) -or -not (Test-Path $Portable)) {
    throw "Electron did not create both Windows artifacts."
}
Copy-Item $Installer (Join-Path $ProjectDir "dist") -Force
Copy-Item $Portable (Join-Path $ProjectDir "dist") -Force
Write-Host "Created $Installer"
Write-Host "Created $Portable"
