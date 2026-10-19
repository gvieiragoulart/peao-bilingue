<#
.SYNOPSIS
Builds the installer: dist\PeaoBilingue-Setup-<version>.exe.

.DESCRIPTION
Builds dist\PeaoBilingue with PyInstaller, stages the installer's license page
(packaging\installer_license.txt followed by LICENSE.md) and THIRD_PARTY_NOTICES.txt
in dist\installer\, and compiles packaging\installer.iss with Inno Setup. The
version is pyproject.toml's. The release workflow (.github\workflows\release.yml)
runs this same script.

Needs Inno Setup 6 (winget install JRSoftware.InnoSetup). Building works from any
shell; installing the result from the Claude desktop app's shell does not (it is an
MSIX app: see CLAUDE.md), so install it from your own terminal.

.PARAMETER SiteUrl
The download site, the publisher's link in Windows' list of apps. $env:SITE_URL by
default; without it, the project page on GitHub.

.PARAMETER SkipBuild
Reuses dist\PeaoBilingue as it is instead of running PyInstaller.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1
#>
[CmdletBinding()]
param(
    [string]$SiteUrl = $env:SITE_URL,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$staging = Join-Path $root 'dist\installer'

function Write-Step([string]$message) {
    Write-Host "==> $message" -ForegroundColor Cyan
}

function Invoke-Native([string]$what, [scriptblock]$command) {
    # To the screen: in a function's output it would mix with what it returns.
    & $command | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "$what failed (exit code $LASTEXITCODE)."
    }
}

function Get-ProjectVersion {
    $found = Select-String -LiteralPath (Join-Path $root 'pyproject.toml') `
        -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $found) {
        throw 'No version in pyproject.toml.'
    }
    $version = $found.Matches[0].Groups[1].Value
    # Windows' file version (VersionInfoVersion) only takes numbers.
    if ($version -notmatch '^\d+\.\d+\.\d+$') {
        throw "The version must be x.y.z for the installer, not '$version'."
    }
    return $version
}

function Find-Iscc {
    $command = Get-Command iscc -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $folders = @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA 'Programs'))
    foreach ($folder in ($folders | Where-Object { $_ })) {
        $candidate = Join-Path $folder 'Inno Setup 6\ISCC.exe'
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    throw 'Inno Setup 6 was not found. Install it with: winget install JRSoftware.InnoSetup'
}

function Write-LicensePage {
    # The summary in Portuguese, then the license itself. CRLF and a BOM: what the
    # installer's text box reads without surprises.
    $summary = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'installer_license.txt'), [Text.Encoding]::UTF8)
    $license = [IO.File]::ReadAllText((Join-Path $root 'LICENSE.md'), [Text.Encoding]::UTF8)
    $text = ($summary + $license) -replace "`r?`n", "`r`n"
    [IO.File]::WriteAllText((Join-Path $staging 'license.txt'), $text, (New-Object Text.UTF8Encoding $true))
}

Push-Location $root
try {
    $version = Get-ProjectVersion
    $iscc = Find-Iscc
    if (-not $SkipBuild) {
        Write-Step 'Building dist\PeaoBilingue'
        Invoke-Native 'The build' {
            uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm
        }
    }
    if (-not (Test-Path -LiteralPath 'dist\PeaoBilingue\PeaoBilingue.exe')) {
        throw 'No build at dist\PeaoBilingue.'
    }

    Write-Step 'Staging the license page and the third-party notices'
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    Write-LicensePage
    Invoke-Native 'The third-party notices' {
        uv run --group packaging python packaging/third_party_notices.py dist/installer/THIRD_PARTY_NOTICES.txt
    }

    Write-Step "Compiling the installer for version $version"
    $arguments = @('/Qp', "/DAppVersion=$version")
    if ($SiteUrl) {
        $arguments += "/DSiteUrl=$SiteUrl"
    }
    Invoke-Native 'Inno Setup' { & $iscc @arguments 'packaging\installer.iss' }

    $setup = Join-Path $root "dist\PeaoBilingue-Setup-$version.exe"
    $hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
    $megabytes = (Get-Item -LiteralPath $setup).Length / 1MB
    Write-Step ('Done: {0} ({1:N1} MB), SHA-256 {2}' -f $setup, $megabytes, $hash)
} finally {
    Pop-Location
}
# Without it, a native command's last exit code could become the script's.
exit 0
