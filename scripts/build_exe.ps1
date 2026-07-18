$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

$app = Join-Path $Root "app\main.py"
$assets = Join-Path $Root "app\assets"
$paths = Join-Path $Root "app"

Write-Host "==> Building OpSDigitaisDados.exe..." -ForegroundColor Cyan
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name "OpSDigitaisDados" `
  --paths $paths `
  --add-data "$assets;assets" `
  --distpath (Join-Path $Root "dist") `
  --workpath (Join-Path $Root "build") `
  --specpath (Join-Path $Root "build") `
  $app

$exe = Join-Path $Root "dist\OpSDigitaisDados\OpSDigitaisDados.exe"
if (Test-Path $exe) {
  Write-Host "OK: $exe" -ForegroundColor Green
  @"
@echo off
cd /d "%~dp0OpSDigitaisDados"
start "" "OpSDigitaisDados.exe"
"@ | Set-Content (Join-Path $Root "dist\Abrir_OpSDigitaisDados.bat") -Encoding ASCII
} else {
  Write-Error "EXE not found"
}
