[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$HostHome = "",
    [string]$UserDataHome = "",
    [switch]$Isolated,
    [switch]$Upgrade,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8
$OutputEncoding = $Utf8
$DownloadRoot = $null

function Read-Result([object[]]$Lines, [int]$Code, [string]$Step) {
    try { $Value = (@($Lines) -join [Environment]::NewLine) | ConvertFrom-Json }
    catch { throw "$Step returned invalid JSON." }
    if ($Value -isnot [pscustomobject]) { throw "$Step did not return a JSON object." }
    if ($Code -ne 0 -or $Value.ok -ne $true) {
        throw "$Step failed ($($Value.error.code))."
    }
    return $Value
}

try {
    . (Join-Path $PSScriptRoot 'windows-install-paths.ps1')
    $UserDataHome = Get-WvdUserDataHome $UserDataHome $HostHome -Isolated:$Isolated
    $Location = Resolve-WvdInstallLocation $InstallRoot $UserDataHome
    $InstallRoot = $Location.actual_root
    Assert-WvdDataHomeSeparation $UserDataHome $InstallRoot
    $Launcher = Join-Path $InstallRoot "visual-director.ps1"
    if ($HostHome) { $env:VISUAL_DIRECTOR_HOST_HOME = [IO.Path]::GetFullPath($HostHome) }

    if ($Upgrade -or -not (Test-Path -LiteralPath $Launcher -PathType Leaf)) {
        [Console]::Error.WriteLine("[wechat-visual-director] Preparing the local workbench for first use or upgrade.")
        $DownloadRoot = Join-Path ([IO.Path]::GetTempPath()) ("wechat-workbench-" + [Guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $DownloadRoot | Out-Null
        $Installer = Join-Path $DownloadRoot "install-release.ps1"
        Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/zhouke0929/wechat-visual-director/main/scripts/install-release.ps1" -OutFile $Installer -TimeoutSec 60
        $InstallArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Installer, "-InstallRoot", $InstallRoot)
        if ($HostHome) { $InstallArgs += @("-HostHome", $HostHome) }
        if ($UserDataHome) { $InstallArgs += @('-UserDataHome', $UserDataHome) }
        if ($Isolated) { $InstallArgs += '-Isolated' }
        $Raw = & powershell @InstallArgs
        $Result = Read-Result $Raw $LASTEXITCODE "install"
        if ($Result.runtime_mode -ne "bundled_python" -or $Result.bundled_runtime -ne $true) {
            throw "The release did not provide its bundled runtime."
        }
    } else {
        if ($UserDataHome -and -not (Read-WvdUserProfile $UserDataHome)) {
            $Exception = New-Object InvalidOperationException 'This older installation needs an explicit upgrade to connect shared history. Existing data was not changed.'
            $Exception.Data['code'] = 'shared_data_upgrade_required'
            throw $Exception
        }
        Assert-WvdLegacyLauncher $InstallRoot
        [Console]::Error.WriteLine("[wechat-visual-director] Starting and checking the existing workbench.")
        $Raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher serve --json
        $Serve = Read-Result $Raw $LASTEXITCODE "serve"
        $Raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher doctor --json
        $Doctor = Read-Result $Raw $LASTEXITCODE "doctor"
        $Result = [pscustomobject]@{
            ok = $true
            launcher = $Launcher
            version = $Doctor.installation.version
            workbench_url = $Serve.web_base
            settings_url = $Doctor.setup.settings_url
            next_action = $Doctor.setup.next_action
            installation = $Doctor.installation
            capabilities = $Doctor.capabilities
            first_install = $false
            onboarding_pending = [bool]$Doctor.setup.onboarding_pending
            first_run_guide = $Doctor.setup.first_run_guide
        }
    }
    if ($Result.installation.persistent -ne $true -or
        $Result.installation.version_match -ne $true -or
        $Result.installation.runtime_match -ne $true -or
        $Result.capabilities.host_skill_registered -ne $true) {
        throw "Workbench identity or Skill registration could not be verified."
    }
    # Creation itself may trigger virtualization. Re-resolve our chosen root,
    # not an arbitrary path from subprocess output.
    $InstallRoot = Get-WvdCanonicalInstallRoot $InstallRoot
    $Launcher = Join-Path $InstallRoot 'visual-director.ps1'
    if (-not (Test-Path -LiteralPath $Launcher -PathType Leaf)) { throw "The installed launcher is missing." }
    $WorkbenchUrl = [uri]$Result.workbench_url
    if ($WorkbenchUrl.Scheme -ne "http" -or $WorkbenchUrl.Host -notin @("127.0.0.1", "localhost", "[::1]")) {
        throw "The workbench did not return a local HTTP URL."
    }
    $Opened = $false
    if (-not $NoOpen) {
        try { Start-Process -FilePath $WorkbenchUrl.AbsoluteUri; $Opened = $true }
        catch { [Console]::Error.WriteLine("Open the workbench_url from the result in your browser.") }
    }
    $Location.actual_root = $InstallRoot
    $Location.redirected = (-not $Location.requested_root.Equals($InstallRoot, [StringComparison]::OrdinalIgnoreCase))
    $Result | Add-Member -NotePropertyName install_location -NotePropertyValue $Location -Force
    $Result | Add-Member -NotePropertyName schema_version -NotePropertyValue "workbench_ready.v0.1" -Force
    $Result | Add-Member -NotePropertyName launcher -NotePropertyValue $Launcher -Force
    $Result | Add-Member -NotePropertyName workbench_ready -NotePropertyValue $true -Force
    $Result | Add-Member -NotePropertyName browser_opened -NotePropertyValue $Opened -Force
    $Result | Add-Member -NotePropertyName command_completed -NotePropertyValue $true -Force
    $Result | ConvertTo-Json -Depth 10 -Compress
} catch {
    $Failure = @{ code = 'workbench_setup_failed'; message = $_.Exception.Message }
    $NextAction = 'retry_workbench_setup'
    if ($_.Exception.Data.Contains('code')) {
        $Failure = Get-WvdPathFailure $_.Exception
        $NextAction = if ($Failure.code -in @('install_location_upgrade_required','shared_data_upgrade_required')) { 'upgrade_selected_installation' } else { 'review_installation_and_history' }
        if ($Failure.code -eq 'install_location_ambiguous') { $NextAction = 'select_install_root' }
    }
    [ordered]@{
        ok = $false
        schema_version = "workbench_ready.v0.1"
        workbench_ready = $false
        next_action = $NextAction
        error = $Failure
    } | ConvertTo-Json -Depth 5 -Compress
    exit 2
} finally {
    if ($DownloadRoot -and (Test-Path -LiteralPath $DownloadRoot)) {
        $TempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\") + "\"
        $ResolvedDownload = [IO.Path]::GetFullPath($DownloadRoot)
        if ($ResolvedDownload.StartsWith($TempParent, [StringComparison]::OrdinalIgnoreCase)) {
            Remove-Item -LiteralPath $ResolvedDownload -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}
