[CmdletBinding()]
param(
    [string]$InstallRoot = "",
    [switch]$SkipDependencies
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
                ($ExcludedDirectoryNames -contains $Item.Name)
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
$ManifestPath = Join-Path $InstallRoot "install.json"

Assert-ChildPath $InstallRoot $VersionsRoot
Assert-ChildPath $InstallRoot $VersionRoot
Assert-ChildPath $InstallRoot $DataRoot
Assert-ChildPath $InstallRoot $ConfigRoot
Assert-ChildPath $InstallRoot $RuntimeRoot

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
$MigratedConfig = $false
$TargetDatabase = Join-Path $DataRoot "visual-director.db"
$LegacyDatabase = Join-Path $SourceRoot "apps\api\data\visual-director.db"
if (-not (Test-Path -LiteralPath $TargetDatabase) -and (Test-Path -LiteralPath $LegacyDatabase -PathType Leaf)) {
    Copy-Item -LiteralPath $LegacyDatabase -Destination $TargetDatabase
    $MigratedDatabase = $true
}

$TargetImages = Join-Path $DataRoot "image-assets"
$LegacyImages = Join-Path $SourceRoot "apps\api\data\image-assets"
if (-not (Test-Path -LiteralPath $TargetImages) -and (Test-Path -LiteralPath $LegacyImages -PathType Container)) {
    Copy-Item -LiteralPath $LegacyImages -Destination $TargetImages -Recurse
    $MigratedImages = $true
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

    $Pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
    if ($null -ne $Pnpm) {
        & $Pnpm.Source --dir $WebDir install --frozen-lockfile --reporter=silent
    } else {
        $Corepack = Get-Command corepack -ErrorAction SilentlyContinue
        if ($null -eq $Corepack) {
            Write-Failure "pnpm_not_found" "pnpm or corepack is required to install the workbench."
        }
        & $Corepack.Source pnpm --dir $WebDir install --frozen-lockfile --reporter=silent
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Failure "web_install_failed" "Could not install the Web workbench dependencies."
    }
}

$PreviousVersion = $null
if (Test-Path -LiteralPath $ManifestPath -PathType Leaf) {
    try {
        $PreviousManifest = Get-Content -Raw -Encoding UTF8 -LiteralPath $ManifestPath | ConvertFrom-Json
        $PreviousVersion = [string]$PreviousManifest.current_version
    } catch {
        Write-Failure "existing_manifest_invalid" "The existing persistent install metadata is invalid." @{
            manifest = $ManifestPath
        }
    }
}

Copy-Item -LiteralPath (Join-Path $VersionRoot "scripts\persistent-launcher.ps1") -Destination $StableLauncher -Force
$InstalledAt = [DateTimeOffset]::UtcNow.ToString("o")
$Manifest = [ordered]@{
    schema_version = "persistent_install.v0.1"
    current_version = $Version
    previous_version = $PreviousVersion
    install_root = $InstallRoot
    current_root = $VersionRoot
    data_root = $DataRoot
    config_file = $ConfigFile
    runtime_root = $RuntimeRoot
    launcher = $StableLauncher
    installed_at = $InstalledAt
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $ManifestPath

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
    skill_root = $VersionRoot
    dependencies_installed = -not $SkipDependencies
    migrated = @{
        database = $MigratedDatabase
        image_assets = $MigratedImages
        config = $MigratedConfig
    }
    next_action = "run_doctor"
} | ConvertTo-Json -Depth 6 -Compress
