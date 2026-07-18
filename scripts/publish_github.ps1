$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not (Test-Path ".git")) {
  git init
  git branch -M main
}

git add -A
$staged = git diff --cached --name-only
if ($staged) {
  git commit -m "OpS Digitais Dados v1.0.0 - por Joaquim Pedro de Morais Filho"
}

$remote = git remote 2>$null
if (-not $remote) {
  gh repo create OpSDigitaisDados --public --source=. --remote=origin `
    --description "OpS Digitais Dados - fingerprint reader and local user database by Joaquim Pedro de Morais Filho" `
    --push
} else {
  git push -u origin main
}

$url = gh repo view --json url -q .url
Write-Host "GitHub: $url" -ForegroundColor Green
Set-Content -Path (Join-Path $Root "docs\GITHUB_URL.txt") -Value $url -Encoding UTF8
