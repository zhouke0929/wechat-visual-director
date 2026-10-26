[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ArchivePath,
    [string]$ApiBase = "http://127.0.0.1:8000/api/v1",
    [string]$WebBase = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"
$ArchivePath = [IO.Path]::GetFullPath($ArchivePath)
if (-not (Test-Path -LiteralPath $ArchivePath -PathType Leaf)) {
    throw "Release archive not found: $ArchivePath"
}
$TempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd("\")
$TestRoot = [IO.Path]::GetFullPath((Join-Path $TempParent ("wechat-visual-director-package-test-" + [Guid]::NewGuid().ToString("N"))))
if (-not $TestRoot.StartsWith($TempParent + "\", [StringComparison]::OrdinalIgnoreCase)) {
    throw "The package-test cleanup path escaped its temporary parent."
}
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
    $Raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -Isolated -InstallRoot $InstallRoot -HostHome $HostHome -ApiBase $ApiBase -WebBase $WebBase
    $BootstrapResult = (@($Raw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $BootstrapResult.ok) { throw "Bootstrap failed: $($BootstrapResult | ConvertTo-Json -Compress -Depth 8)" }
    if (-not $BootstrapResult.installation.runtime_match) { throw "Installed runtime identity mismatch." }
    if (-not $BootstrapResult.data_continuity.checked -or -not $BootstrapResult.data_continuity.preserved) {
        throw "Package installation did not verify data continuity."
    }
    if ($BootstrapResult.runtime_mode -ne "bundled_python" -or -not $BootstrapResult.bundled_runtime) {
        throw "Installer did not select bundled Python."
    }
    if (-not $BootstrapResult.first_install) { throw "Fresh package install was not marked as first_install." }
    if ($BootstrapResult.first_run_guide.schema_version -ne "first_run_guide.v0.1") {
        throw "Fresh package install did not return the first-run guide."
    }
    if (@($BootstrapResult.first_run_guide.lines).Count -ne 4) {
        throw "First-run guide must remain concise."
    }
    if ($BootstrapResult.onboarding_pending -ne $true) { throw "Fresh guide must remain pending until user acknowledgement." }
    foreach ($SkillRoot in @(
        (Join-Path $HostHome ".codex\skills\wechat-visual-director"),
        (Join-Path $HostHome ".agents\skills\wechat-visual-director"),
        (Join-Path $HostHome ".config\opencode\skills\wechat-visual-director")
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $SkillRoot "SKILL.md") -PathType Leaf)) {
            throw "Lightweight Skill registration is missing: $SkillRoot"
        }
        foreach ($Forbidden in @("apps", "docs", ".github")) {
            if (Test-Path -LiteralPath (Join-Path $SkillRoot $Forbidden)) {
                throw "Source directory leaked into lightweight Skill registration: $Forbidden"
            }
        }
    }

    $Launcher = [string]$BootstrapResult.launcher
    $DoctorRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher doctor --api-base $ApiBase --web-base $WebBase --json
    $Doctor = (@($DoctorRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Doctor.ok -or -not $Doctor.core_ready -or -not $Doctor.workbench_ready) { throw "Doctor failed." }
    if ($Doctor.setup.onboarding_pending -ne $true -or @($Doctor.setup.first_run_guide.lines).Count -ne 4) {
        throw "A repeated health check lost the pending first-run guide."
    }

    # Source-only paths can pass unit tests but fail from bundled site-packages.
    $Gallery = Invoke-RestMethod -Uri ($ApiBase.TrimEnd("/") + "/theme-gallery")
    if ($Gallery.schema_version -ne "theme_gallery.v0.5" -or @($Gallery.themes).Count -ne 12) {
        throw "The packaged theme gallery is incomplete."
    }
    foreach ($Theme in $Gallery.themes) {
        if (@($Theme.foundation_specimens).Count -ne 14 -or @($Theme.components).Count -ne 12 -or
            [string]::IsNullOrWhiteSpace([string]$Theme.article_preview_html)) {
            throw "The packaged gallery lost production specimens: $($Theme.id)"
        }
    }

    $Sample = Join-Path $PackageRoot "samples\skill-alpha\canonical-article.md"
    $TaskRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher task create --file $Sample --no-plan --api-base $ApiBase --web-base $WebBase --json
    $Task = (@($TaskRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Task.ok -or [string]::IsNullOrWhiteSpace([string]$Task.task_id)) { throw "Sample task creation failed." }
    $ListRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher task list --api-base $ApiBase --web-base $WebBase --json
    $TaskList = (@($ListRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $TaskList.ok -or $TaskList.total -ne 1 -or $TaskList.items[0].id -ne $Task.task_id) {
        throw "Packaged CLI could not find the existing sample task."
    }

    # Reinstall an occupied dataset, not just an empty first installation.
    $Raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $Bootstrap -Isolated -InstallRoot $InstallRoot -HostHome $HostHome -ApiBase $ApiBase -WebBase $WebBase
    $Upgrade = (@($Raw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Upgrade.ok -or -not $Upgrade.data_continuity.preserved -or
        $Upgrade.data_continuity.before_task_count -ne 1 -or $Upgrade.installation.running_task_count -ne 1) {
        throw "Reinstall did not preserve the sample task."
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File $Launcher stop --json | Out-Null
    $DatabasePath = Join-Path $InstallRoot "data\visual-director.db"
    $DatabaseHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $DatabasePath).Hash
    $UninstallRaw = & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallRoot "uninstall.ps1") -InstallRoot $InstallRoot -HostHome $HostHome
    $Uninstall = (@($UninstallRaw) -join [Environment]::NewLine) | ConvertFrom-Json
    if (-not $Uninstall.ok -or $Uninstall.mode -ne "preserve_data" -or
        -not (Test-Path -LiteralPath $DatabasePath -PathType Leaf) -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $DatabasePath).Hash -ne $DatabaseHash) {
        throw "Default uninstall did not preserve the existing database."
    }
    if (Test-Path -LiteralPath (Join-Path $HostHome ".codex\skills\wechat-visual-director")) {
        throw "Codex Skill registration survived uninstall."
    }

    [ordered]@{
        ok = $true
        schema_version = "windows_release_smoke_test.v0.1"
        version = $Manifest.application_version
        runtime = $Manifest.python_runtime
        task_id = $Task.task_id
        default_uninstall_preserved_database = $true
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
