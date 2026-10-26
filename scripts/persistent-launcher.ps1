[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom

$InstallRoot = $PSScriptRoot
$ManifestPath = Join-Path $InstallRoot "install.json"

function Write-LauncherFailure([string]$Code, [string]$Message, [hashtable]$Details = @{}) {
    @{
        ok = $false
        schema_version = "persistent_launcher.v0.1"
        error = @{
            code = $Code
            message = $Message
            retryable = $true
            details = $Details
        }
    } | ConvertTo-Json -Depth 6 -Compress
    exit 2
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
    Write-LauncherFailure "install_manifest_missing" "Persistent install metadata was not found." @{
        manifest = $ManifestPath
    }
}

try {
    $Manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
} catch {
    Write-LauncherFailure "install_manifest_invalid" "Persistent install metadata is invalid." @{
        manifest = $ManifestPath
    }
}

$RecordedRoot = [string]$Manifest.install_root
# Load the helper adjacent to this installed version. Legacy manifests may still
# contain a virtual LocalAppData prefix, so locate the version relative to us.
$VersionName = [string]$Manifest.current_version
if ($VersionName -notmatch '^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$') {
    Write-LauncherFailure 'install_manifest_invalid' 'The active version identifier is invalid.'
}
$Helper = Join-Path $InstallRoot "versions\$VersionName\skills\wechat-visual-director\scripts\windows-install-paths.ps1"
try {
    . $Helper
    $ActualRoot = Get-WvdCanonicalInstallRoot $InstallRoot
    if ($Manifest.physical_install_root -and
        -not $ActualRoot.Equals([string]$Manifest.physical_install_root, [StringComparison]::OrdinalIgnoreCase)) {
        Write-LauncherFailure 'install_location_changed' 'The installation now resolves to a different location. Confirm the original installation before continuing.' @{
            expected_root = [string]$Manifest.physical_install_root
            actual_root = $ActualRoot
        }
    }
    $ProjectRoot = Resolve-WvdStoredPath ([string]$Manifest.current_root) $RecordedRoot $ActualRoot
    $DataRoot = Resolve-WvdStoredPath ([string]$Manifest.data_root) $RecordedRoot $ActualRoot
    $RuntimeRoot = Resolve-WvdStoredPath ([string]$Manifest.runtime_root) $RecordedRoot $ActualRoot
    $ConfigFile = Resolve-WvdStoredPath ([string]$Manifest.config_file) $RecordedRoot $ActualRoot
    $InstallRoot = $ActualRoot
    if ($Manifest.user_data_home) {
        $Profile = Read-WvdUserProfile ([string]$Manifest.user_data_home)
        if (-not $Profile) { throw 'The shared history registry is missing. No empty database was created.' }
        if ($Manifest.user_profile_id -and $Manifest.user_profile_id -ne $Profile.profile_id) { throw 'Shared history identity changed. No empty replacement was opened.' }
        $ActiveRoot = [string]$Profile.active_install_root
        if (-not $ActiveRoot) { throw 'No active program is registered for shared history.' }
        $ActiveRoot = Get-WvdCanonicalInstallRoot $ActiveRoot
        if (-not $ActiveRoot.Equals($InstallRoot, [StringComparison]::OrdinalIgnoreCase)) {
            $ActiveLauncher = Join-Path $ActiveRoot 'visual-director.ps1'
            if (-not (Test-Path -LiteralPath $ActiveLauncher -PathType Leaf)) { throw 'The registered program is missing. Reinstall it without resetting shared history.' }
            & $ActiveLauncher @CliArgs
            exit $LASTEXITCODE
        }
        $DataRoot = [string]$Profile.data_root
        $RuntimeRoot = [string]$Profile.runtime_root
        $ConfigFile = [string]$Profile.config_file
        $env:VISUAL_DIRECTOR_API_BASE = [string]$Profile.api_base
        $env:VISUAL_DIRECTOR_WEB_BASE = [string]$Profile.web_base
    }
} catch {
    Write-LauncherFailure 'install_location_check_failed' $_.Exception.Message
}
$VersionLauncher = Join-Path $ProjectRoot "scripts\visual-director.ps1"
if (-not (Test-Path -LiteralPath $VersionLauncher -PathType Leaf)) {
    Write-LauncherFailure "installed_version_missing" "The active Visual Director version is incomplete." @{
        version = [string]$Manifest.current_version
        current_root = $ProjectRoot
    }
}

$env:VISUAL_DIRECTOR_INSTALL_ROOT = $InstallRoot
$env:VISUAL_DIRECTOR_PROJECT_ROOT = $ProjectRoot
$env:VISUAL_DIRECTOR_DATA_ROOT = $DataRoot
$env:VISUAL_DIRECTOR_HOME = $RuntimeRoot
$env:VISUAL_DIRECTOR_DB = Join-Path $DataRoot "visual-director.db"
$env:VISUAL_DIRECTOR_ENV_FILE = $ConfigFile
$env:VISUAL_DIRECTOR_WECHAT_ENV_FILE = $ConfigFile

& $VersionLauncher @CliArgs
exit $LASTEXITCODE
