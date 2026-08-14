[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [string]$HostHome = "",
    [switch]$SkipDependencies,
    [switch]$MigrateLegacyData
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$SourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Write-Failure([string]$Code, [string]$Message, [hashtable]$Details = @{}) {
    @{
        ok = $false
        schema_version = "skill_install_result.v0.2"
        error = @{
            code = $Code
            message = $Message
            retryable = $true
            details = $Details
        }
    } | ConvertTo-Json -Depth 7 -Compress
    exit 2
}

function Resolve-AbsolutePath([string]$PathValue) {
    if ([IO.Path]::IsPathRooted($PathValue)) {
        return [IO.Path]::GetFullPath($PathValue)
    }
    return [IO.Path]::GetFullPath((Join-Path (Get-Location).Path $PathValue))
}

function Assert-ChildPath([string]$Parent, [string]$Child) {
    $ParentFull = [IO.Path]::GetFullPath($Parent).TrimEnd("\") + "\"
    $ChildFull = [IO.Path]::GetFullPath($Child)
    if (-not $ChildFull.StartsWith($ParentFull, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Failure "unsafe_install_path" "The computed install path escaped the selected install root." @{
            install_root = $Parent
            computed_path = $Child
        }
    }
}

function Remove-OldVersionDirectories(
    [string]$VersionsDirectory,
    [string[]]$KeepVersions,
    [string]$ProtectedSourceRoot
) {
    $Removed = @()
    $Failed = @()
    $VersionsFull = [IO.Path]::GetFullPath($VersionsDirectory).TrimEnd("\")
    $SourceFull = [IO.Path]::GetFullPath($ProtectedSourceRoot).TrimEnd("\")
    $Keep = @($KeepVersions | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Unique)

    if (-not (Test-Path -LiteralPath $VersionsFull -PathType Container)) {
        return [ordered]@{ removed = $Removed; failed = $Failed }
    }

    foreach ($Directory in Get-ChildItem -LiteralPath $VersionsFull -Directory) {
        if ($Keep -contains $Directory.Name) {
            continue
        }
        $Candidate = [IO.Path]::GetFullPath($Directory.FullName).TrimEnd("\")
        $Parent = [IO.Path]::GetFullPath($Directory.Parent.FullName).TrimEnd("\")
        if (
            -not $Parent.Equals($VersionsFull, [StringComparison]::OrdinalIgnoreCase) -or
            $Candidate.Equals($SourceFull, [StringComparison]::OrdinalIgnoreCase)
        ) {
            $Failed += [ordered]@{ path = $Candidate; reason = "unsafe_cleanup_path" }
            continue
        }
        try {
            Remove-Item -LiteralPath $Candidate -Recurse -Force
            $Removed += $Candidate
        } catch {
            $Failed += [ordered]@{ path = $Candidate; reason = $_.Exception.Message }
        }
    }
    return [ordered]@{ removed = $Removed; failed = $Failed }
}

function Copy-ApplicationSource(
    [string]$CurrentSource,
    [string]$CurrentDestination,
    [string]$RelativePath = ""
) {
    $ExcludedDirectoryPaths = @(
        ".git",
        ".tmp",
        ".pnpm-store",
        "artifacts",
        "apps/api/.venv",
        "apps/api/data",
        "apps/web/node_modules",
        "apps/web/.next"
    )
    if (-not [string]::IsNullOrWhiteSpace($script:InstallSourceExclusion)) {
        $ExcludedDirectoryPaths += $script:InstallSourceExclusion
    }
    $ExcludedDirectoryNames = @(
        ".runtime",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache"
    )
    $ExcludedFileNames = @(
        ".env",
        ".env.local",
        ".env.production.local"
    )

    New-Item -ItemType Directory -Force -Path $CurrentDestination | Out-Null
    foreach ($Item in Get-ChildItem -Force -LiteralPath $CurrentSource) {
        $ChildRelativePath = if ([string]::IsNullOrWhiteSpace($RelativePath)) {
            $Item.Name
        } else {
            "$RelativePath/$($Item.Name)"
        }
        $NormalizedRelativePath = $ChildRelativePath.Replace("\", "/")

        if ($Item.PSIsContainer) {
            if (
                ($ExcludedDirectoryPaths -contains $NormalizedRelativePath) -or
                ($ExcludedDirectoryNames -contains $Item.Name) -or
                $Item.Name.StartsWith(".pytest-tmp", [StringComparison]::OrdinalIgnoreCase)
            ) {
                continue
            }
            Copy-ApplicationSource `
                -CurrentSource $Item.FullName `
                -CurrentDestination (Join-Path $CurrentDestination $Item.Name) `
                -RelativePath $NormalizedRelativePath
            continue
        }

        if (
            ($ExcludedFileNames -contains $Item.Name) -or
            $Item.Name.EndsWith(".pyc", [StringComparison]::OrdinalIgnoreCase) -or
            $Item.Name.EndsWith(".log", [StringComparison]::OrdinalIgnoreCase)
        ) {
            continue
        }
        Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $CurrentDestination $Item.Name) -Force
    }
}

function Copy-SkillRegistration(
    [string]$ApplicationRoot,
    [string]$DestinationRoot
) {
    $SkillFile = Join-Path $ApplicationRoot "SKILL.md"
    $ReferencesRoot = Join-Path $ApplicationRoot "references"
    $AgentsRoot = Join-Path $ApplicationRoot "agents"
    $InstallGuide = Join-Path $ApplicationRoot "INSTALL_FOR_AGENT.md"
    if (-not (Test-Path -LiteralPath $SkillFile -PathType Leaf)) {
        Write-Failure "skill_file_missing" "SKILL.md was not found in the installed application." @{
            application_root = $ApplicationRoot
        }
    }
    New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
    Copy-Item -LiteralPath $SkillFile -Destination (Join-Path $DestinationRoot "SKILL.md") -Force
    if (Test-Path -LiteralPath $ReferencesRoot -PathType Container) {
        $TargetReferences = Join-Path $DestinationRoot "references"
        New-Item -ItemType Directory -Force -Path $TargetReferences | Out-Null
        foreach ($Item in Get-ChildItem -Force -LiteralPath $ReferencesRoot) {
            Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $TargetReferences $Item.Name) -Recurse -Force
        }
    }
    if (Test-Path -LiteralPath $InstallGuide -PathType Leaf) {
        Copy-Item -LiteralPath $InstallGuide -Destination (Join-Path $DestinationRoot "INSTALL_FOR_AGENT.md") -Force
    }
    if (Test-Path -LiteralPath $AgentsRoot -PathType Container) {
        $TargetAgents = Join-Path $DestinationRoot "agents"
        New-Item -ItemType Directory -Force -Path $TargetAgents | Out-Null
        foreach ($Item in Get-ChildItem -Force -LiteralPath $AgentsRoot) {
            Copy-Item -LiteralPath $Item.FullName -Destination (Join-Path $TargetAgents $Item.Name) -Recurse -Force
        }
    }
}

function Register-HostSkill(
    [string]$ApplicationRoot,
    [string]$UserHomeOverride = ""
) {
    $UserHome = $UserHomeOverride
    if ([string]::IsNullOrWhiteSpace($UserHome)) {
        $UserHome = [Environment]::GetFolderPath("UserProfile")
    }
    if ([string]::IsNullOrWhiteSpace($UserHome)) {
        $UserHome = $HOME
    }
    if ([string]::IsNullOrWhiteSpace($UserHome)) {
        Write-Failure "user_home_missing" "A user home directory is required to register the Agent Skill."
    }
    $UserHome = [IO.Path]::GetFullPath($UserHome)
    $GenericSkillRoot = Join-Path $UserHome ".agents\skills\wechat-visual-director"
    $OpenCodeSkillRoot = Join-Path $UserHome ".config\opencode\skills\wechat-visual-director"
    $OpenCodeCommandRoot = Join-Path $UserHome ".config\opencode\commands"
    $OpenCodeCommand = Join-Path $OpenCodeCommandRoot "wechat-visual-director.md"

    try {
        Copy-SkillRegistration -ApplicationRoot $ApplicationRoot -DestinationRoot $GenericSkillRoot
        Copy-SkillRegistration -ApplicationRoot $ApplicationRoot -DestinationRoot $OpenCodeSkillRoot
        New-Item -ItemType Directory -Force -Path $OpenCodeCommandRoot | Out-Null
        @'
---
description: 创建、排版或继续处理微信公众号视觉主编任务
---

加载并使用 `wechat-visual-director` Skill 处理下面的请求。严格遵守 Skill 的人工确认与密钥安全门禁。

$ARGUMENTS
'@ | Set-Content -Encoding UTF8 -LiteralPath $OpenCodeCommand
    } catch {
        Write-Failure "host_skill_registration_failed" "The application was installed, but the host Agent Skill could not be registered." @{
            generic_skill_root = $GenericSkillRoot
            opencode_skill_root = $OpenCodeSkillRoot
            reason = $_.Exception.Message
        }
    }
    return [ordered]@{
        generic_skill_root = $GenericSkillRoot
        opencode_skill_root = $OpenCodeSkillRoot
        opencode_command = $OpenCodeCommand
    }
}

$VersionFile = Join-Path $SourceRoot "VERSION"
if (-not (Test-Path -LiteralPath $VersionFile -PathType Leaf)) {
    Write-Failure "version_file_missing" "VERSION was not found in the source package." @{ root = $SourceRoot }
}
$Version = (Get-Content -Raw -Encoding UTF8 -LiteralPath $VersionFile).Trim()
if ($Version -notmatch "^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$") {
    Write-Failure "version_invalid" "VERSION contains an unsupported value." @{ version = $Version }
}

if ([string]::IsNullOrWhiteSpace($InstallRoot)) {
    if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        Write-Failure "local_app_data_missing" "LOCALAPPDATA is required for the default persistent install."
    }
    $InstallRoot = Join-Path $env:LOCALAPPDATA "wechat-visual-director"
}
$InstallRoot = Resolve-AbsolutePath $InstallRoot
$SourcePrefix = [IO.Path]::GetFullPath($SourceRoot).TrimEnd("\") + "\"
$InstallRootFull = [IO.Path]::GetFullPath($InstallRoot).TrimEnd("\")
if ($InstallRootFull.Equals([IO.Path]::GetFullPath($SourceRoot).TrimEnd("\"), [StringComparison]::OrdinalIgnoreCase)) {
    Write-Failure "install_root_is_source" "The persistent install root cannot be the source repository itself." @{
        source_root = $SourceRoot
        install_root = $InstallRoot
    }
}
$script:InstallSourceExclusion = $null
if ($InstallRootFull.StartsWith($SourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    $script:InstallSourceExclusion = $InstallRootFull.Substring($SourcePrefix.Length).Replace("\", "/")
}
$VersionsRoot = Join-Path $InstallRoot "versions"
$VersionRoot = Join-Path $VersionsRoot $Version
$DataRoot = Join-Path $InstallRoot "data"
$ConfigRoot = Join-Path $InstallRoot "config"
$RuntimeRoot = Join-Path $InstallRoot "runtime"
$ConfigFile = Join-Path $ConfigRoot ".env.local"
$StableLauncher = Join-Path $InstallRoot "visual-director.ps1"
$StableCmdLauncher = Join-Path $InstallRoot "visual-director.cmd"
$StableUninstaller = Join-Path $InstallRoot "uninstall.ps1"
$ManifestPath = Join-Path $InstallRoot "install.json"
$HistoryPath = Join-Path $ConfigRoot "install-history.json"

Assert-ChildPath $InstallRoot $VersionsRoot
Assert-ChildPath $InstallRoot $VersionRoot
Assert-ChildPath $InstallRoot $DataRoot
Assert-ChildPath $InstallRoot $ConfigRoot
Assert-ChildPath $InstallRoot $RuntimeRoot

if (Test-Path -LiteralPath $VersionRoot) {
    try {
        Remove-Item -LiteralPath $VersionRoot -Recurse -Force
    } catch {
        Write-Failure "version_root_cleanup_failed" "Could not refresh the existing installed version directory." @{
            version_root = $VersionRoot
            reason = $_.Exception.Message
        }
    }
}
New-Item -ItemType Directory -Force -Path $VersionRoot, $DataRoot, $ConfigRoot, $RuntimeRoot | Out-Null

try {
    Copy-ApplicationSource -CurrentSource $SourceRoot -CurrentDestination $VersionRoot
} catch {
    Write-Failure "source_copy_failed" "Could not copy the application into the persistent version directory." @{
        source_root = $SourceRoot
        version_root = $VersionRoot
        reason = $_.Exception.Message
    }
}

$MigratedDatabase = $false
$MigratedImages = $false
$MigratedPublicationAssets = $false
$MigratedConfig = $false
$TargetDatabase = Join-Path $DataRoot "visual-director.db"
$LegacyDatabase = Join-Path $SourceRoot "apps\api\data\visual-director.db"
if ($MigrateLegacyData -and -not (Test-Path -LiteralPath $TargetDatabase) -and (Test-Path -LiteralPath $LegacyDatabase -PathType Leaf)) {
    Copy-Item -LiteralPath $LegacyDatabase -Destination $TargetDatabase
    $MigratedDatabase = $true
}

$TargetImages = Join-Path $DataRoot "image-assets"
$LegacyImages = Join-Path $SourceRoot "apps\api\data\image-assets"
if ($MigrateLegacyData -and -not (Test-Path -LiteralPath $TargetImages) -and (Test-Path -LiteralPath $LegacyImages -PathType Container)) {
    Copy-Item -LiteralPath $LegacyImages -Destination $TargetImages -Recurse
    $MigratedImages = $true
}

$TargetPublicationAssets = Join-Path $DataRoot "publication-assets"
$LegacyPublicationAssets = Join-Path $SourceRoot "apps\api\data\publication-assets"
if ($MigrateLegacyData -and -not (Test-Path -LiteralPath $TargetPublicationAssets) -and (Test-Path -LiteralPath $LegacyPublicationAssets -PathType Container)) {
    Copy-Item -LiteralPath $LegacyPublicationAssets -Destination $TargetPublicationAssets -Recurse
    $MigratedPublicationAssets = $true
}

$LegacyConfig = Join-Path $SourceRoot ".env.local"
if (-not (Test-Path -LiteralPath $ConfigFile) -and (Test-Path -LiteralPath $LegacyConfig -PathType Leaf)) {
    Copy-Item -LiteralPath $LegacyConfig -Destination $ConfigFile
    $MigratedConfig = $true
}
if (-not (Test-Path -LiteralPath $ConfigFile)) {
    $ExampleConfig = Join-Path $VersionRoot ".env.example"
    if (Test-Path -LiteralPath $ExampleConfig -PathType Leaf) {
        Copy-Item -LiteralPath $ExampleConfig -Destination $ConfigFile
    } else {
        New-Item -ItemType File -Path $ConfigFile | Out-Null
    }
}

$ApiDir = Join-Path $VersionRoot "apps\api"
$WebDir = Join-Path $VersionRoot "apps\web"
$VenvDir = Join-Path $ApiDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PythonVersion = $null

if (-not $SkipDependencies) {
    if (-not (Test-Path -LiteralPath (Join-Path $ApiDir "pyproject.toml") -PathType Leaf)) {
        Write-Failure "project_layout_missing" "apps/api/pyproject.toml was not found." @{ root = $VersionRoot }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $WebDir "package.json") -PathType Leaf)) {
        Write-Failure "project_layout_missing" "apps/web/package.json was not found." @{ root = $VersionRoot }
    }

    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $Python) {
        Write-Failure "python_not_found" "Python 3.11 or newer is required."
    }
    $PythonVersion = (& $Python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
    $VersionParts = $PythonVersion.Split(".")
    if ([int]$VersionParts[0] -lt 3 -or ([int]$VersionParts[0] -eq 3 -and [int]$VersionParts[1] -lt 11)) {
        Write-Failure "python_version_unsupported" "Python 3.11 or newer is required." @{ detected = $PythonVersion }
    }

    if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
        & $Python.Source -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Failure "venv_create_failed" "Could not create the Python virtual environment."
        }
    }
    & $VenvPython -m pip install --quiet --disable-pip-version-check -e $ApiDir
    if ($LASTEXITCODE -ne 0) {
        Write-Failure "python_install_failed" "Could not install the Visual Director API package."
    }

}

$StaticWorkbench = Join-Path $WebDir "dist\index.html"
if (-not (Test-Path -LiteralPath $StaticWorkbench -PathType Leaf)) {
    Write-Failure "prebuilt_workbench_missing" "The release package does not contain the prebuilt workbench." @{
        expected = $StaticWorkbench
        action = "Download a complete tagged release or rebuild the workbench in CI. Normal installation never invokes npm or pnpm."
    }
}

$PreviousVersion = $null
if (Test-Path -LiteralPath $ManifestPath -PathType Leaf) {
    try {
        $PreviousManifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
        if ([string]$PreviousManifest.current_version -eq $Version) {
            $PreviousVersion = [string]$PreviousManifest.previous_version
        } else {
            $PreviousVersion = [string]$PreviousManifest.current_version
        }
    } catch {
        Write-Failure "existing_manifest_invalid" "The existing persistent install metadata is invalid." @{
            manifest = $ManifestPath
        }
    }
} elseif (Test-Path -LiteralPath $HistoryPath -PathType Leaf) {
    try {
        $InstallHistory = Get-Content -Raw -Encoding UTF8 -LiteralPath $HistoryPath | ConvertFrom-Json
        $PreviousVersion = [string]$InstallHistory.last_version
    } catch {
        Write-Failure "install_history_invalid" "The preserved installation history is invalid." @{ history = $HistoryPath }
    }
}

Copy-Item -LiteralPath (Join-Path $VersionRoot "scripts\persistent-launcher.ps1") -Destination $StableLauncher -Force
Copy-Item -LiteralPath (Join-Path $VersionRoot "scripts\persistent-launcher.cmd") -Destination $StableCmdLauncher -Force
Copy-Item -LiteralPath (Join-Path $VersionRoot "scripts\uninstall.ps1") -Destination $StableUninstaller -Force
$HostRegistration = Register-HostSkill -ApplicationRoot $VersionRoot -UserHomeOverride $HostHome
$InstalledAt = [DateTimeOffset]::UtcNow.ToString("o")
$Manifest = [ordered]@{
    schema_version = "persistent_install.v0.2"
    current_version = $Version
    previous_version = $PreviousVersion
    install_root = $InstallRoot
    current_root = $VersionRoot
    data_root = $DataRoot
    config_file = $ConfigFile
    runtime_root = $RuntimeRoot
    launcher = $StableLauncher
    launcher_cmd = $StableCmdLauncher
    uninstaller = $StableUninstaller
    host_registration = $HostRegistration
    installed_at = $InstalledAt
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $ManifestPath
$InstallHistory = [ordered]@{
    schema_version = "install_history.v0.1"
    last_version = $Version
    data_root = $DataRoot
    last_install_at = $InstalledAt
    last_uninstall_at = $null
}
$InstallHistory | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $HistoryPath
$VersionCleanup = Remove-OldVersionDirectories `
    -VersionsDirectory $VersionsRoot `
    -KeepVersions @($Version, $PreviousVersion) `
    -ProtectedSourceRoot $SourceRoot
$InstallWarnings = @()
if ($VersionCleanup.failed.Count -gt 0) {
    $InstallWarnings += "old_versions_cleanup_failed"
}
$RetainedVersions = @($Version)
if (-not [string]::IsNullOrWhiteSpace($PreviousVersion) -and $PreviousVersion -ne $Version) {
    $RetainedVersions += $PreviousVersion
}

@{
    ok = $true
    schema_version = "skill_install_result.v0.2"
    install_mode = "persistent"
    version = $Version
    previous_version = $PreviousVersion
    install_root = $InstallRoot
    app_root = $VersionRoot
    data_root = $DataRoot
    config_file = $ConfigFile
    runtime_root = $RuntimeRoot
    launcher = $StableLauncher
    launcher_cmd = $StableCmdLauncher
    uninstaller = $StableUninstaller
    skill_root = $HostRegistration.generic_skill_root
    host_registration = $HostRegistration
    dependencies_installed = -not $SkipDependencies
    production_workbench_built = (Test-Path -LiteralPath (Join-Path $WebDir "dist\index.html") -PathType Leaf)
    retained_versions = $RetainedVersions
    removed_versions = $VersionCleanup.removed
    warnings = $InstallWarnings
    migrated = @{
        database = $MigratedDatabase
        image_assets = $MigratedImages
        publication_assets = $MigratedPublicationAssets
        config = $MigratedConfig
    }
    legacy_data_migration_requested = [bool]$MigrateLegacyData
    next_action = "run_doctor"
} | ConvertTo-Json -Depth 6 -Compress
