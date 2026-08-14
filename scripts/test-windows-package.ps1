[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath
)

$ErrorActionPreference = "Stop"
$ArchivePath = [IO.Path]::GetFullPath($ArchivePath)
if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) {
    throw "Release archive not found: $ArchivePath"
}
$TestRoot = Join-Path ([IO.Path]::GetTempPath()) ("wechat-visual-director-package-test-" + [Guid]::NewGuid().ToString("N"))
$ExtractRoot = Join-Path $TestRoot "extracted"
$InstallRoot = Join-Path $TestRoot "installed"
$HostHome = Join-Path $TestRoot "host"
New-Item -ItemType Directory -Force -Path $ExtractRoot, $HostHome | Out-Null

try {
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractRoot -Force
    $PackageRoot = Join-Path $ExtractRoot "wechat-visual-director"
    $Manifest = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PackageRoot "release-manifest.json") | ConvertFrom-Json
    if ([bool]$Manifest.requires_system_python) { throw "Manifest does not declare zero system Python dependency." }
    $BundledPython = Join-Path $PackageRoot "runtime\python\python.exe"
    & $BundledPython -c "import fastapi, PIL, uvicorn, visual_director, yaml"
    if ($LASTEXITCODE -ne 0) { throw "Bundled runtime import probe failed." }

    $Bootstrap = Join-Path $PackageRoot "scripts\bootstrap.ps1"
    $Raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -InstallRoot $InstallRoot -HostHome $HostHome
    $BootstrapResult = (@($Raw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $BootstrapResult.ok) { throw "Bootstrap failed: $($BootstrapResult | ConvertTo-Json -Compress -Depth 8)" }
    if (-not $BootstrapResult.installation.runtime_match) { throw "Installed runtime identity mismatch." }
    if ($BootstrapResult.runtime_mode -ne "bundled_python" -or -not $BootstrapResult.bundled_runtime) {
        throw "Installer did not select bundled Python."
    }

    $Launcher = [string]$BootstrapResult.launcher
    $DoctorRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher doctor --json
    $Doctor = (@($DoctorRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Doctor.ok -or -not $Doctor.core_ready -or -not $Doctor.workbench_ready) { throw "Doctor failed." }

    $Sample = Join-Path $PackageRoot "samples\skill-alpha\canonical-article.md"
    $TaskRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher task create --file $Sample --no-plan --json
    $Task = (@($TaskRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Task.ok -or [string]::IsNullOrWhiteSpace([string]$Task.task_id)) { throw "Sample task creation failed." }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher stop --json | Out-Null
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallRoot "uninstall.ps1") -InstallRoot $InstallRoot -HostHome $HostHome -Purge | Out-Null

    [ordered]@{
        ok = $true
        schema_version = "windows_release_smoke_test.v0.1"
        version = $Manifest.application_version
        runtime = $Manifest.python_runtime
        task_id = $Task.task_id
        archive = $ArchivePath
    } | ConvertTo-Json -Depth 5 -Compress
} finally {
    if (Test-Path -LiteralPath $InstallRoot) {
        $StableLauncher = Join-Path $InstallRoot "visual-director.ps1"
        if (Test-Path -LiteralPath $StableLauncher) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $StableLauncher stop --json 2>$null | Out-Null
        }
    }
    if (Test-Path -LiteralPath $TestRoot) {
        Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
