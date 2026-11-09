param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    Write-Host 'Creating isolated Python environment...'
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv .venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv .venv
    } else {
        throw 'Python 3.10+ is required. Install Python from python.org, then run start.cmd again.'
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $projectPython)) { throw 'Could not create Python environment. Install Python 3.10+ from python.org.' }
}
& $projectPython -c 'import importlib.util,sys; sys.exit(not all(importlib.util.find_spec(name) for name in sys.argv[1:]))' fastapi uvicorn sherlock_project
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing dependencies (first run only)...'
    & $projectPython -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'pip setup failed.' }
    & $projectPython -m pip install .
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your internet connection.' }
}
$launchArgs = @('-m', 'sherlock_local', '--port', $Port)
if ($NoBrowser) { $launchArgs += '--no-browser' }
& $projectPython @launchArgs
exit $LASTEXITCODE
