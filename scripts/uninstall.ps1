[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$HostHome = "",
    [switch]$Purge
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

function Write-UninstallFailure(
    [string]$Code,
    [string]$Message,
    [hashtable]$Details = @{},
    [int]$ExitCode = 2
) {
    [ordered]@{
        ok = $false
        schema_version = "uninstall_result.v0.1"
        error = [ordered]@{
            code = $Code
            message = $Message
            retryable = $true
            details = $Details
        }
    } | ConvertTo-Json -Depth 8 -Compress
    exit $ExitCode
}

function Assert-DirectChild([string]$Parent, [string]$Child) {
    $ParentFull = [IO.Path]::GetFullPath($Parent).TrimEnd("\")
    $ChildFull = [IO.Path]::GetFullPath($Child).TrimEnd("\")
    $ChildParent = [IO.Path]::GetFullPath((Split-Path -Parent $ChildFull)).TrimEnd("\")
    if (-not $ChildParent.Equals($ParentFull, [StringComparison]::OrdinalIgnoreCase)) {
        Write-UninstallFailure "unsafe_uninstall_path" "An uninstall target escaped the install root." @{
            install_root = $ParentFull
            target = $ChildFull
        }
    }
}

function Remove-KnownPath([string]$PathValue, [ref]$Removed, [ref]$Failed) {
    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }
    try {
        $Item = Get-Item -Force -LiteralPath $PathValue
        if ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $Failed.Value += [ordered]@{ path = $PathValue; reason = "reparse_point_refused" }
            return
        }
        Remove-Item -LiteralPath $PathValue -Recurse -Force
        $Removed.Value += $PathValue
    } catch {
        $Failed.Value += [ordered]@{ path = $PathValue; reason = $_.Exception.Message }
    }
}

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    $AdjacentManifest = Join-Path $PSScriptRoot "install.json"
    if (Test-Path -LiteralPath $AdjacentManifest -PathType Leaf) {
        $InstallRoot = $PSScriptRoot
    } else {
        if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            Write-UninstallFailure "local_app_data_missing" "LOCALAPPDATA is required for the default install."
        }
        $InstallRoot = Join-Path $env:LOCALAPPDATA "wechat-visual-director"
    }
}
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot).TrimEnd("\")
$ManifestPath = Join-Path $InstallRoot "install.json"

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    Write-UninstallFailure "install_manifest_missing" "No valid persistent installation was found at this path." @{
        install_root = $InstallRoot
        preserved_source = $true
    }
}
try {
    $Manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
} catch {
    Write-UninstallFailure "install_manifest_invalid" "The persistent install manifest is invalid." @{
        manifest = $ManifestPath
    }
}

$ManifestRoot = [IO.Path]::GetFullPath([string]$Manifest.install_root).TrimEnd("\")
if (-not $ManifestRoot.Equals($InstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Write-UninstallFailure "install_manifest_root_mismatch" "The manifest does not belong to the requested install root." @{
        requested = $InstallRoot
        manifest_root = $ManifestRoot
    }
}

$InstallItem = Get-Item -Force -LiteralPath $InstallRoot
if ($InstallItem.Attributes -band [IO.FileAttributes]::ReparsePoint) {
    Write-UninstallFailure "install_root_reparse_point" "Refusing to uninstall through a redirected install root." @{
        install_root = $InstallRoot
    }
}

$VersionsRoot = Join-Path $InstallRoot "versions"
$CurrentRoot = [IO.Path]::GetFullPath([string]$Manifest.current_root).TrimEnd("\")
$VersionsPrefix = [IO.Path]::GetFullPath($VersionsRoot).TrimEnd("\") + "\"
if (-not $CurrentRoot.StartsWith($VersionsPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    Write-UninstallFailure "install_manifest_version_path_invalid" "The active program path is outside the versions directory." @{
        current_root = $CurrentRoot
        versions_root = $VersionsRoot
    }
}

# If this repository copy is itself passed as InstallRoot, preserve it even if
# a stray install.json exists there. The installed uninstaller lives directly
# under InstallRoot; the source uninstaller lives under InstallRoot\scripts.
$ScriptDirectory = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd("\")
if ((Split-Path -Leaf $ScriptDirectory) -eq "scripts") {
    $RepositoryRoot = [IO.Path]::GetFullPath((Split-Path -Parent $ScriptDirectory)).TrimEnd("\")
    if ($RepositoryRoot.Equals($InstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Write-UninstallFailure "source_repository_protected" "The source repository cannot be used as an uninstall target." @{
            source_root = $RepositoryRoot
        }
    }
}

$StableLauncher = Join-Path $InstallRoot "visual-director.ps1"
if (Test-Path -LiteralPath $StableLauncher -PathType Leaf) {
    $StopRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $StableLauncher stop --json
    $StopExitCode = $LASTEXITCODE
    try {
        $StopResult = (@($StopRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    } catch {
        Write-UninstallFailure "runtime_stop_invalid_output" "The runtime stop command returned invalid JSON." @{
            launcher = $StableLauncher
        } 3
    }
    if ($StopExitCode -ne 0 -or @($StopResult.refused.PSObject.Properties).Count -gt 0) {
        Write-UninstallFailure "runtime_stop_refused" "Running processes could not be stopped safely; nothing was removed." @{
            stop_result = $StopResult
        } 3
    }
}

if (-not $Purge) {
    $ConfigRoot = Join-Path $InstallRoot "config"
    $HistoryPath = Join-Path $ConfigRoot "install-history.json"
    New-Item -ItemType Directory -Force -Path $ConfigRoot | Out-Null
    $History = [ordered]@{
        schema_version = "install_history.v0.1"
        last_version = [string]$Manifest.current_version
        data_root = [string]$Manifest.data_root
        last_install_at = [string]$Manifest.installed_at
        last_uninstall_at = [DateTimeOffset]::UtcNow.ToString("o")
    }
    $History | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $HistoryPath
}

if ([string]::IsNullOrWhiteSpace($HostHome)) {
    $HostHome = [Environment]::GetFolderPath("UserProfile")
}
$HostHome = [IO.Path]::GetFullPath($HostHome)
$RegistrationTargets = @(
    (Join-Path $HostHome ".agents\skills\wechat-visual-director"),
    (Join-Path $HostHome ".config\opencode\skills\wechat-visual-director"),
    (Join-Path $HostHome ".config\opencode\commands\wechat-visual-director.md")
)

$ProgramTargets = @(
    $VersionsRoot,
    (Join-Path $InstallRoot "runtime"),
    (Join-Path $InstallRoot "visual-director.ps1"),
    (Join-Path $InstallRoot "visual-director.cmd"),
    (Join-Path $InstallRoot "uninstall.ps1"),
    $ManifestPath
)
if ($Purge) {
    $ProgramTargets += @(
        (Join-Path $InstallRoot "data"),
        (Join-Path $InstallRoot "config")
    )
}

foreach ($Target in $ProgramTargets) {
    Assert-DirectChild $InstallRoot $Target
}

$Removed = @()
$Failed = @()
foreach ($Target in $RegistrationTargets) {
    Remove-KnownPath $Target ([ref]$Removed) ([ref]$Failed)
}
foreach ($Target in $ProgramTargets) {
    Remove-KnownPath $Target ([ref]$Removed) ([ref]$Failed)
}

$Preserved = @()
if (-not $Purge) {
    foreach ($Name in @("data", "config", "backups")) {
        $PathValue = Join-Path $InstallRoot $Name
        if (Test-Path -LiteralPath $PathValue) {
            $Preserved += $PathValue
        }
    }
}

$SelfPath = [IO.Path]::GetFullPath($MyInvocation.MyCommand.Path)
if ($ScriptDirectory.Equals($InstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Remove-KnownPath $SelfPath ([ref]$Removed) ([ref]$Failed)
}
if ($Purge -and (Test-Path -LiteralPath $InstallRoot)) {
    try {
        if (@(Get-ChildItem -Force -LiteralPath $InstallRoot).Count -eq 0) {
            Remove-Item -LiteralPath $InstallRoot -Force
            $Removed += $InstallRoot
        }
    } catch {
        $Failed += [ordered]@{ path = $InstallRoot; reason = $_.Exception.Message }
    }
}

$Warnings = @()
if ($Failed.Count -gt 0) {
    $Warnings += "uninstall_cleanup_incomplete"
}
$RegistrationsRemoved = -not ($RegistrationTargets | Where-Object { Test-Path -LiteralPath $_ })

[ordered]@{
    ok = ($Failed.Count -eq 0)
    schema_version = "uninstall_result.v0.1"
    mode = if ($Purge) { "purge" } else { "preserve_data" }
    install_root = $InstallRoot
    source_repository_preserved = $true
    registrations_removed = $RegistrationsRemoved
    removed = $Removed
    preserved = $Preserved
    failed = $Failed
    warnings = $Warnings
    next_action = if ($Purge) { "installation_removed" } else { "reinstall_to_restore_program" }
} | ConvertTo-Json -Depth 8 -Compress

if ($Failed.Count -gt 0) {
    exit 7
}
