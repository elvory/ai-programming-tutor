param(
    [string]$Python = 'D:\anaconda\envs\ai-study\python.exe',
    [int]$Port = 8000
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python not found: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Build the workbench first: cd frontend; npm install; npm run build'
}
Push-Location -LiteralPath $projectRoot
try {
    & $Python -m uvicorn backend.app:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) { throw "Workbench exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
