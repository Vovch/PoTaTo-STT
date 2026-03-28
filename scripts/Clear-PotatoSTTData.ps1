#Requires -Version 5.1
<#
.SYNOPSIS
    Remove Potato STT local data: Parakeet install cache, Hugging Face ONNX model cache, Qt/registry settings, and startup Run entries.

.DESCRIPTION
    Quit Potato STT before running. Default actions:
    - Delete %LOCALAPPDATA%\potato_stt and legacy %LOCALAPPDATA%\pipit_clone
    - Delete Hugging Face Hub folders for istupakov/parakeet-* ONNX models (default ASR downloads)
    - Remove HKCU\Software\PotatoSTT and legacy HKCU\Software\PipitClone (QSettings)
    - Remove HKCU\...\Run values PotatoSTT and PipitClone
    - Remove leftover $env:TEMP\potato-stt-* directories

    Use -AllHuggingfaceHub to delete the entire user Hugging Face hub cache (affects all HF tools, not only Potato STT).

.EXAMPLE
    .\Clear-PotatoSTTData.ps1 -Yes

.EXAMPLE
    .\Clear-PotatoSTTData.ps1 -WhatIf

.NOTES
    Shipped next to PotatoSTT.exe; also runnable from the repository scripts\ folder.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [switch] $Yes,
    [switch] $SkipParakeetLocalAppData,
    [switch] $SkipOnnxHubParakeetModels,
    [switch] $SkipRegistry,
    [switch] $SkipRunKey,
    [switch] $SkipTempLeftovers,
    [switch] $AllHuggingfaceHub,
    [switch] $Force
)

$ErrorActionPreference = "Stop"

if ($Force) {
    $ConfirmPreference = "None"
}

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Stop-PotatoSTTProcess {
    Get-Process -Name "PotatoSTT" -ErrorAction SilentlyContinue | ForEach-Object {
        if ($PSCmdlet.ShouldProcess($_.Path, "Stop Potato STT process")) {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Remove-LiteralPathTree {
    param(
        [Parameter(Mandatory = $true)]
        [string] $LiteralPath,
        [Parameter(Mandatory = $true)]
        [string] $Operation
    )
    if (-not (Test-Path -LiteralPath $LiteralPath)) {
        return $false
    }
    if ($PSCmdlet.ShouldProcess($LiteralPath, $Operation)) {
        Remove-Item -LiteralPath $LiteralPath -Recurse -Force
        return $true
    }
    return $false
}

if (-not $Yes -and -not $PSBoundParameters.ContainsKey("WhatIf")) {
    Write-Host ""
    Write-Host "Potato STT - clear local data" -ForegroundColor Cyan
    Write-Host "------------------------------"
    if (-not $SkipParakeetLocalAppData) {
        Write-Host "  - Parakeet / app data: LOCALAPPDATA\potato_stt and LOCALAPPDATA\pipit_clone"
    }
    if (-not $SkipOnnxHubParakeetModels -and -not $AllHuggingfaceHub) {
        Write-Host "  - ONNX ASR (onnx-asr): Hugging Face hub models--istupakov--parakeet-*"
    }
    if ($AllHuggingfaceHub) {
        Write-Host "  - ENTIRE Hugging Face hub cache (all models for this user profile)"
    }
    if (-not $SkipRegistry) {
        Write-Host "  - Registry: HKCU\Software\PotatoSTT, HKCU\Software\PipitClone"
    }
    if (-not $SkipRunKey) {
        Write-Host "  - Startup Run entries: PotatoSTT, PipitClone"
    }
    if (-not $SkipTempLeftovers) {
        Write-Host "  - Temp folders: potato-stt-* under `$env:TEMP"
    }
    Write-Host ""
    Write-Host "Quit the app first. This does not uninstall Python or the PotatoSTT program folder." -ForegroundColor Yellow
    Write-Host ""
    $answer = Read-Host "Continue? [y/N]"
    if ($answer -notmatch "^[yY]") {
        Write-Host "Aborted."
        exit 0
    }
}

if (Test-Admin) {
    Write-Warning "Running elevated is not required. Data is per-user under your profile."
}

Stop-PotatoSTTProcess

$didAnything = $false

if (-not $SkipParakeetLocalAppData) {
    $parakeetPaths = @(
        (Join-Path $env:LOCALAPPDATA "potato_stt"),
        (Join-Path $env:LOCALAPPDATA "pipit_clone")
    )
    foreach ($p in $parakeetPaths) {
        if (Remove-LiteralPathTree -LiteralPath $p -Operation "Remove Parakeet / Potato STT app data") {
            $didAnything = $true
            Write-Host "Removed: $p" -ForegroundColor Green
        }
    }
}

$hubRoot = $null
if ($env:HUGGINGFACE_HUB_CACHE) {
    $hubRoot = $env:HUGGINGFACE_HUB_CACHE
} elseif ($env:HF_HOME) {
    $hubRoot = Join-Path $env:HF_HOME "hub"
} else {
    $hubRoot = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
}

if ($AllHuggingfaceHub) {
    if (Remove-LiteralPathTree -LiteralPath $hubRoot -Operation "Remove entire Hugging Face hub cache") {
        $didAnything = $true
        Write-Host "Removed Hugging Face hub: $hubRoot" -ForegroundColor Green
    }
} elseif (-not $SkipOnnxHubParakeetModels) {
    if (Test-Path -LiteralPath $hubRoot) {
        Get-ChildItem -LiteralPath $hubRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "models--istupakov--parakeet-*" } |
            ForEach-Object {
                if (Remove-LiteralPathTree -LiteralPath $_.FullName -Operation "Remove ONNX ASR Hugging Face model cache") {
                    $didAnything = $true
                    Write-Host "Removed: $($_.FullName)" -ForegroundColor Green
                }
            }
    }
}

if (-not $SkipRegistry) {
    foreach ($key in @("HKCU:\Software\PotatoSTT", "HKCU:\Software\PipitClone")) {
        if (Test-Path -LiteralPath $key) {
            if ($PSCmdlet.ShouldProcess($key, "Remove application settings registry key")) {
                Remove-Item -LiteralPath $key -Recurse -Force
                $didAnything = $true
                Write-Host "Removed registry: $key" -ForegroundColor Green
            }
        }
    }
}

if (-not $SkipRunKey) {
    $runKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    if (-not (Test-Path -LiteralPath $runKey)) {
        # Extremely unusual; skip
    } else {
        $runNames = (Get-Item -LiteralPath $runKey).Property
        foreach ($name in @("PotatoSTT", "PipitClone")) {
            if ($runNames -notcontains $name) {
                continue
            }
            if ($PSCmdlet.ShouldProcess("$runKey\$name", "Remove startup Run value")) {
                Remove-ItemProperty -LiteralPath $runKey -Name $name
                $didAnything = $true
                Write-Host "Removed Run value: $name" -ForegroundColor Green
            }
        }
    }
}

if (-not $SkipTempLeftovers) {
    foreach ($pattern in @("potato-stt-*", "potato_stt_*")) {
        Get-ChildItem -Path $env:TEMP -Directory -Filter $pattern -ErrorAction SilentlyContinue |
            ForEach-Object {
                if (Remove-LiteralPathTree -LiteralPath $_.FullName -Operation "Remove temp directory") {
                    $didAnything = $true
                    Write-Host "Removed temp: $($_.FullName)" -ForegroundColor Green
                }
            }
    }
}

if (-not $didAnything -and -not $PSBoundParameters.ContainsKey("WhatIf")) {
    Write-Host "Nothing to remove (paths already absent or -WhatIf)." -ForegroundColor DarkGray
} elseif (-not $PSBoundParameters.ContainsKey("WhatIf")) {
    Write-Host ""
    Write-Host "Done. You can start Potato STT again; models and Parakeet data will re-download if needed." -ForegroundColor Cyan
}

exit 0
