[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$HostHome = "",
    [string]$ApiBase = "http://127.0.0.1:8000/api/v1",
    [string]$WebBase = "http://127.0.0.1:8000",
    [switch]$SkipDependencies
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Write-ProgressMessage([string]$Message) {
    [Console]::Error.WriteLine("[wechat-visual-director] $Message")
}

function Write-BootstrapFailure(
    [string]$Code,
    [string]$Message,
    [hashtable]$Details = @{},
    [int]$ExitCode = 2
) {
    [ordered]@{
        ok = $false
        schema_version = "bootstrap_result.v0.1"
        error = [ordered]@{
            code = $Code
            message = $Message
            retryable = $true
            details = $Details
        }
    } | ConvertTo-Json -Depth 8 -Compress
    exit $ExitCode
}

function Parse-JsonResult([object[]]$Lines, [string]$Step) {
    $Text = (@($Lines) -join [Environment]::NewLine).Trim()
    if ([string]::IsNullOrWhiteSpace($Text)) {
        Write-BootstrapFailure "${Step}_empty_output" "$Step returned no structured result."
    }
    try {
        return $Text | ConvertFrom-Json
    } catch {
        Write-BootstrapFailure "${Step}_invalid_output" "$Step did not return valid JSON." @{
            action = "Read the installer logs under the persistent runtime directory."
        }
    }
}

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        Write-BootstrapFailure "local_app_data_missing" "LOCALAPPDATA is required for the default install."
    }
    $InstallRoot = Join-Path $env:LOCALAPPDATA "wechat-visual-director"
}
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$StableLauncher = Join-Path $InstallRoot "visual-director.ps1"
$Installer = Join-Path $SourceRoot "scripts\install.ps1"

if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    Write-BootstrapFailure "installer_missing" "The repository installer is missing." @{
        expected = $Installer
    }
}

if (Test-Path -LiteralPath $StableLauncher -PathType Leaf) {
    Write-ProgressMessage "Stopping the currently installed runtime before upgrade."
    $StopRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $StableLauncher stop --json
    $StopExitCode = $LASTEXITCODE
    $StopResult = Parse-JsonResult $StopRaw "stop"
    if ($StopExitCode -ne 0 -or @($StopResult.refused.PSObject.Properties).Count -gt 0) {
        Write-BootstrapFailure "existing_runtime_stop_failed" "The previous runtime could not be stopped safely." @{
            stop_result = $StopResult
        } 3
    }
}

Write-ProgressMessage "Installing the repository into the persistent local application directory."
$InstallArgs = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Installer,
    "-InstallRoot", $InstallRoot
)
if (-not [string]::IsNullOrWhiteSpace($HostHome)) {
    $InstallArgs += @("-HostHome", $HostHome)
}
if ($SkipDependencies) {
    $InstallArgs += "-SkipDependencies"
}
$InstallRaw = & powershell @InstallArgs
$InstallExitCode = $LASTEXITCODE
$InstallResult = Parse-JsonResult $InstallRaw "install"
if ($InstallExitCode -ne 0 -or -not $InstallResult.ok) {
    Write-BootstrapFailure "install_failed" "The persistent installation did not complete." @{
        install_result = $InstallResult
    } 2
}

$Launcher = [string]$InstallResult.launcher
Write-ProgressMessage "Starting the installed production services."
$ServeRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher serve --api-base $ApiBase --web-base $WebBase --json
$ServeExitCode = $LASTEXITCODE
$ServeResult = Parse-JsonResult $ServeRaw "serve"
if ($ServeExitCode -ne 0 -or -not $ServeResult.ok) {
    Write-BootstrapFailure "serve_failed" "The installed services did not become ready." @{
        serve_result = $ServeResult
        launcher = $Launcher
    } 3
}

Write-ProgressMessage "Checking the installed runtime contract."
$DoctorRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher doctor --api-base $ApiBase --web-base $WebBase --json
$DoctorExitCode = $LASTEXITCODE
$DoctorResult = Parse-JsonResult $DoctorRaw "doctor"
if ($DoctorExitCode -ne 0 -or -not $DoctorResult.ok) {
    Write-BootstrapFailure "doctor_failed" "The installed runtime failed its health check." @{
        doctor_result = $DoctorResult
        launcher = $Launcher
    } 3
}

$NextAction = [string]$DoctorResult.setup.next_action
if ([string]::IsNullOrWhiteSpace($NextAction)) {
    $NextAction = "create_article"
}

[ordered]@{
    ok = $true
    schema_version = "bootstrap_result.v0.1"
    install_mode = [string]$InstallResult.install_mode
    version = [string]$InstallResult.version
    launcher = $Launcher
    launcher_cmd = [string]$InstallResult.launcher_cmd
    uninstaller = [string]$InstallResult.uninstaller
    api_base = [string]$ServeResult.api_base
    web_base = [string]$ServeResult.web_base
    settings_url = [string]$DoctorResult.setup.settings_url
    next_action = $NextAction
    installation = $DoctorResult.installation
    capabilities = $DoctorResult.capabilities
    setup = $DoctorResult.setup
    warnings = @($InstallResult.warnings) + @($DoctorResult.warnings)
} | ConvertTo-Json -Depth 8 -Compress
