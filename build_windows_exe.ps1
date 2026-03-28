# Build a Windows one-folder executable bundle (dist/PotatoSTT/).
# Uses a dedicated .venv under the repo so PyInstaller does not bundle unrelated
# packages from your global Python install.
#
# Run from the repository root:
#   .\build_windows_exe.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating .venv ..." -ForegroundColor Cyan
    python -m venv "$Root\.venv"
}

Write-Host "Installing dependencies into .venv ..." -ForegroundColor Cyan
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r "$Root\requirements.txt" -r "$Root\requirements-build.txt"

Write-Host "Running PyInstaller ..." -ForegroundColor Cyan
& $VenvPython -m PyInstaller "$Root\potato_stt.spec" --clean --noconfirm

$DistOut = Join-Path $Root "dist\PotatoSTT"
$CpuBatSrc = Join-Path $Root "PotatoSTTCPU.bat"
$CpuBatDst = Join-Path $DistOut "PotatoSTTCPU.bat"
if (Test-Path $DistOut) {
    Copy-Item -Path $CpuBatSrc -Destination $CpuBatDst -Force
    Write-Host "Copied PotatoSTTCPU.bat next to PotatoSTT.exe." -ForegroundColor Cyan
    $ClearScriptSrc = Join-Path $Root "scripts\Clear-PotatoSTTData.ps1"
    $ClearScriptDst = Join-Path $DistOut "Clear-PotatoSTTData.ps1"
    if (Test-Path $ClearScriptSrc) {
        Copy-Item -Path $ClearScriptSrc -Destination $ClearScriptDst -Force
        Write-Host "Copied Clear-PotatoSTTData.ps1 next to PotatoSTT.exe." -ForegroundColor Cyan
    } else {
        Write-Warning "scripts\Clear-PotatoSTTData.ps1 not found - skipping copy."
    }
} else {
    Write-Warning "dist\PotatoSTT not found - skipping PotatoSTTCPU.bat copy."
}

Write-Host ""
Write-Host "Done. Run: $($Root)\dist\PotatoSTT\PotatoSTT.exe" -ForegroundColor Green
Write-Host "CPU-only: $($Root)\dist\PotatoSTT\PotatoSTTCPU.bat (sets POTATO_STT_CPU_ONLY=1)" -ForegroundColor Green
Write-Host 'Ship the entire dist\PotatoSTT folder (DLLs live next to PotatoSTT.exe).' -ForegroundColor Yellow
