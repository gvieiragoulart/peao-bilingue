<#
.SYNOPSIS
Builds PeaoBilingue.exe and installs it over the current installation.

.DESCRIPTION
Runs the tests, builds dist\PeaoBilingue with PyInstaller and replaces
%LOCALAPPDATA%\Programs\PeaoBilingue with it. The previous installation is kept
as PeaoBilingue.previous, so -Rollback can bring it back. The data
(%LOCALAPPDATA%\PeaoBilingue), the Start menu shortcut and the scheduled task
point at the same paths and are left alone.

Run it from your own terminal, not from the Claude desktop app: Claude is an
MSIX app, and a folder its processes create under AppData goes to a private
copy only they see (that is how the first migration "vanished").

.PARAMETER SkipTests
Builds without running the test suite first (nor checking Playwright's Chromium,
which only the tests use).

.PARAMETER BuildOnly
Builds dist\PeaoBilingue and stops: nothing is installed.

.PARAMETER Force
Closes the running app (or a collection in progress) instead of stopping.

.PARAMETER Rollback
Puts the previous installation back. Nothing is built.

.PARAMETER InstallDir
Where the program is installed; %LOCALAPPDATA%\Programs\PeaoBilingue by default.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File packaging\deploy.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$BuildOnly,
    [switch]$Force,
    [switch]$Rollback,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\PeaoBilingue')
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$install = [IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
$previousName = (Split-Path -Leaf $install) + '.previous'
$previous = Join-Path (Split-Path -Parent $install) $previousName
$built = Join-Path $root 'dist\PeaoBilingue'
$taskName = 'Peao Bilingue - daily collection'

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

function Stop-RunningApp {
    # Only the installed copy: a window opened from the project's .venv doesn't lock it.
    $running = @(Get-Process -Name PeaoBilingue -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($install, 'OrdinalIgnoreCase') })
    if ($running.Count -eq 0) {
        return
    }
    $collecting = $false
    try {
        $collecting = (Get-ScheduledTask -TaskName $taskName -ErrorAction Stop).State -eq 'Running'
    } catch {
        # No task registered: nothing is collecting on schedule.
    }
    $what = if ($collecting) { 'The daily collection is running' } else { 'The app is open' }
    if (-not $Force) {
        throw "$what. Close it (or wait for the collection) and run again, or pass -Force."
    }
    Write-Step "$what; closing it (-Force)"
    $running | Stop-Process -Force
    $running | Wait-Process -Timeout 30 -ErrorAction SilentlyContinue
}

function Restore-Previous {
    if (-not (Test-Path -LiteralPath $previous)) {
        throw "There is no previous installation at $previous."
    }
    Stop-RunningApp
    Write-Step "Restoring $previous"
    if (Test-Path -LiteralPath $install) {
        Remove-Item -LiteralPath $install -Recurse -Force
    }
    Rename-Item -LiteralPath $previous -NewName (Split-Path -Leaf $install)
}

function Install-Build {
    if (-not (Test-Path -LiteralPath (Join-Path $built 'PeaoBilingue.exe'))) {
        throw "No build at $built."
    }
    Stop-RunningApp
    if (Test-Path -LiteralPath $previous) {
        Remove-Item -LiteralPath $previous -Recurse -Force
    }
    $hadInstall = Test-Path -LiteralPath $install
    if ($hadInstall) {
        Write-Step "Keeping the current installation as $previousName"
        Rename-Item -LiteralPath $install -NewName $previousName
    }
    Write-Step "Installing to $install"
    try {
        Copy-Item -LiteralPath $built -Destination $install -Recurse
    } catch {
        # Half a copy is worse than the old version: put it back.
        if (Test-Path -LiteralPath $install) {
            Remove-Item -LiteralPath $install -Recurse -Force
        }
        if ($hadInstall) {
            Rename-Item -LiteralPath $previous -NewName (Split-Path -Leaf $install)
        }
        throw
    }
}

function Invoke-Build {
    if (-not $SkipTests) {
        # The integration tests launch Playwright's own Chromium (the app uses the
        # installed Chrome). Each Playwright update wants a new revision; with it in
        # place this only checks, without downloading.
        Write-Step "Checking Playwright's Chromium (for the tests)"
        Invoke-Native "Installing Playwright's Chromium" { uv run playwright install chromium }
        Write-Step 'Running the tests'
        Invoke-Native 'The tests' { uv run pytest -q }
    }
    Write-Step 'Building dist\PeaoBilingue'
    Invoke-Native 'The build' {
        uv run --group packaging pyinstaller packaging/peao_bilingue.spec --noconfirm
    }
    $version = uv run --no-sync python -c 'from peao_bilingue import __version__; print(__version__)'
    return "$version".Trim()
}

Push-Location $root
try {
    if ($Rollback) {
        Restore-Previous
        Write-Step 'Done: the previous version is back.'
    } elseif ($BuildOnly) {
        $version = Invoke-Build
        Write-Step "Done: version $version built in $built (not installed)."
    } else {
        $version = Invoke-Build
        Install-Build
        Write-Step "Done: version $version installed. Undo with -Rollback."
    }
} finally {
    Pop-Location
}
# Without it, a native command's last exit code could become the script's.
exit 0
