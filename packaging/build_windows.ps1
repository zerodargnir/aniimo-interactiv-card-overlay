# Build dist\AniimoOverlay.exe on Windows.
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    Write-Host "Creating the virtual environment..."
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { python -m venv .venv }
}
$python = ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

$env:QT_QPA_PLATFORM = "offscreen"
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
Remove-Item Env:\QT_QPA_PLATFORM

& $python -m PyInstaller --noconfirm --clean packaging\AniimoOverlay.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

& $python packaging\check_exe.py dist\AniimoOverlay.exe
if ($LASTEXITCODE -ne 0) { throw "QtWebEngine files missing from the exe" }

$size = [math]::Round((Get-Item dist\AniimoOverlay.exe).Length / 1MB, 1)
Write-Host "OK: dist\AniimoOverlay.exe ($size MB)"
