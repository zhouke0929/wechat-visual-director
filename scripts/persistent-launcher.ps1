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

$ProjectRoot = [string]$Manifest.current_root
$VersionLauncher = Join-Path $ProjectRoot "scripts\visual-director.ps1"
if (-not (Test-Path -LiteralPath $VersionLauncher -PathType Leaf)) {
    Write-LauncherFailure "installed_version_missing" "The active Visual Director version is incomplete." @{
        version = [string]$Manifest.current_version
        current_root = $ProjectRoot
    }
}

$env:VISUAL_DIRECTOR_INSTALL_ROOT = $InstallRoot
$env:VISUAL_DIRECTOR_PROJECT_ROOT = $ProjectRoot
$env:VISUAL_DIRECTOR_DATA_ROOT = [string]$Manifest.data_root
$env:VISUAL_DIRECTOR_HOME = [string]$Manifest.runtime_root
$env:VISUAL_DIRECTOR_DB = Join-Path ([string]$Manifest.data_root) "visual-director.db"
$env:VISUAL_DIRECTOR_ENV_FILE = [string]$Manifest.config_file
$env:VISUAL_DIRECTOR_WECHAT_ENV_FILE = [string]$Manifest.config_file

& $VersionLauncher @CliArgs
exit $LASTEXITCODE
