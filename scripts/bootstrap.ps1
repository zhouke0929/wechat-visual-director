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
$InstallManifest = Join-Path $InstallRoot "install.json"
$InstallHistory = Join-Path $InstallRoot "config\install-history.json"
$FirstInstallation = -not (
    (Test-Path -LiteralPath $StableLauncher -PathType Leaf) -or
    (Test-Path -LiteralPath $InstallManifest -PathType Leaf) -or
    (Test-Path -LiteralPath $InstallHistory -PathType Leaf)
)
$Installer = Join-Path $SourceRoot "scripts\install.ps1"

if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
    Write-BootstrapFailure "installer_missing" "The repository installer is missing." @{
        expected = $Installer
    }
}

# The new package owns this helper; old cores need not know the new command.
$CheckScript = Join-Path $SourceRoot "scripts\check-upgrade-data.py"
$CheckPython = Join-Path $SourceRoot "runtime\python\python.exe"
if (-not (Test-Path -LiteralPath $CheckPython -PathType Leaf)) {
    $SourcePython = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $SourcePython) {
        Write-BootstrapFailure "upgrade_check_runtime_missing" "The package Python required for data continuity checks is missing."
    }
    $CheckPython = $SourcePython.Source
}
$Snapshot = Join-Path $InstallRoot ("runtime\upgrade-data-" + [Guid]::NewGuid().ToString("N") + ".json")
Write-ProgressMessage "Checking the current data source before installation."
$CheckRaw = & $CheckPython $CheckScript capture --install-root $InstallRoot --snapshot $Snapshot --api-base $ApiBase --candidate (Join-Path $SourceRoot "apps\api\data")
$CheckExit = $LASTEXITCODE
$CheckResult = Parse-JsonResult $CheckRaw "data_continuity"
if ($CheckExit -ne 0 -or -not $CheckResult.ok) {
    Write-BootstrapFailure $CheckResult.error.code $CheckResult.error.message @{ data_check = $CheckResult; next_action = "review_data_migration" }
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
Write-ProgressMessage "Verifying tasks and assets were preserved."
$CheckRaw = & $CheckPython $CheckScript verify --install-root $InstallRoot --snapshot $Snapshot
$CheckExit = $LASTEXITCODE
$CheckResult = Parse-JsonResult $CheckRaw "data_continuity"
if ($CheckExit -ne 0 -or -not $CheckResult.ok) {
    Write-BootstrapFailure $CheckResult.error.code $CheckResult.error.message @{ data_check = $CheckResult; snapshot = $Snapshot }
}
$DataContinuity = $CheckResult.data_continuity
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
if ([int]$DoctorResult.installation.running_task_count -lt [int]$DataContinuity.before_task_count) {
    Write-BootstrapFailure "upgrade_running_data_incomplete" "The running workbench cannot see all previous tasks." @{ data_continuity = $DataContinuity } 3
}

$NextAction = [string]$DoctorResult.setup.next_action
if ([string]::IsNullOrWhiteSpace($NextAction)) {
    $NextAction = "create_article"
}

$FirstRunGuide = $DoctorResult.setup.first_run_guide
# Compatibility for a package whose core predates persistent onboarding.
if ($FirstInstallation -and $null -eq $FirstRunGuide -and $null -eq $DoctorResult.setup.onboarding_pending) {
    $FirstRunGuide = [ordered]@{
        schema_version = "first_run_guide.v0.1"
        language = "respond_in_user_language"
        title = "WeChat Visual Director is ready"
        lines = @(
            "Give your Agent a topic, source material, or an existing article; it organizes the content and plans the layout before opening the workbench.",
            "Edit text, review themes and mobile previews in the workbench; if your Agent supports native image generation, ask it for article and cover candidates to review.",
            "Give your Agent a component reference image or style description to create a complete custom theme; review it in the gallery and a real article before use.",
            "Enter image API and WeChat credentials only in Local Settings; the product creates drafts and never mass publishes automatically."
        )
    }
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
    workbench_url = [string]$ServeResult.web_base
    settings_url = [string]$DoctorResult.setup.settings_url
    next_action = $NextAction
    first_install = [bool]$FirstInstallation
    onboarding_pending = [bool]($DoctorResult.setup.onboarding_pending -or $null -ne $FirstRunGuide)
    first_run_guide = $FirstRunGuide
    background = $true
    process_mode = "detached"
    command_completed = $true
    runtime_mode = [string]$InstallResult.runtime_mode
    python_version = [string]$InstallResult.python_version
    bundled_runtime = [bool]$InstallResult.bundled_runtime
    installation = $DoctorResult.installation
    data_continuity = $DataContinuity
    capabilities = $DoctorResult.capabilities
    setup = $DoctorResult.setup
    warnings = @($InstallResult.warnings) + @($DoctorResult.warnings)
} | ConvertTo-Json -Depth 8 -Compress
