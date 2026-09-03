[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$HostHome = "",
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
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
        if (-not $env:LOCALAPPDATA) { throw "LOCALAPPDATA is unavailable." }
        $InstallRoot = Join-Path $env:LOCALAPPDATA "wechat-visual-director"
    }
    $InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
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
        $Raw = & powershell @InstallArgs
        $Result = Read-Result $Raw $LASTEXITCODE "install"
        if ($Result.runtime_mode -ne "bundled_python" -or $Result.bundled_runtime -ne $true) {
            throw "The release did not provide its bundled runtime."
        }
    } else {
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
            first_run_guide = $null
        }
    }
    if ($Result.installation.persistent -ne $true -or
        $Result.installation.version_match -ne $true -or
        $Result.installation.runtime_match -ne $true -or
        $Result.capabilities.host_skill_registered -ne $true) {
        throw "Workbench identity or Skill registration could not be verified."
    }
    # Use the expected local launcher, not an arbitrary path from subprocess output.
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
    $Result | Add-Member -NotePropertyName schema_version -NotePropertyValue "workbench_ready.v0.1" -Force
    $Result | Add-Member -NotePropertyName launcher -NotePropertyValue $Launcher -Force
    $Result | Add-Member -NotePropertyName workbench_ready -NotePropertyValue $true -Force
    $Result | Add-Member -NotePropertyName browser_opened -NotePropertyValue $Opened -Force
    $Result | Add-Member -NotePropertyName command_completed -NotePropertyValue $true -Force
    $Result | ConvertTo-Json -Depth 10 -Compress
} catch {
    [ordered]@{
        ok = $false
        schema_version = "workbench_ready.v0.1"
        workbench_ready = $false
        next_action = "retry_workbench_setup"
        error = @{ code = "workbench_setup_failed"; message = $_.Exception.Message }
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
