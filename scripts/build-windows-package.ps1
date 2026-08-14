[CmdletBinding()]
param(
    [string]$OutputDirectory = "",
    [string]$PythonVersion = "3.11.9",
    [switch]$SkipWorkbenchBuild
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Write-BuildFailure([string]$Code, [string]$Message, [hashtable]$Details = @{}) {
    [ordered]@{
        ok = $false
        schema_version = "windows_release_build.v0.1"
        error = [ordered]@{ code = $Code; message = $Message; details = $Details }
    } | ConvertTo-Json -Depth 7 -Compress
    exit 2
}

function Resolve-AbsolutePath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) { return [IO.Path]::GetFullPath($Value) }
    return [IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Value))
}

function Assert-ChildPath([string]$Parent, [string]$Child) {
    $ParentFull = [IO.Path]::GetFullPath($Parent).TrimEnd("\") + "\"
    $ChildFull = [IO.Path]::GetFullPath($Child)
    if (-not $ChildFull.StartsWith($ParentFull, [StringComparison]::OrdinalIgnoreCase)) {
        Write-BuildFailure "unsafe_build_path" "A build path escaped the selected output directory." @{
            output_directory = $Parent
            computed_path = $Child
        }
    }
}

function Copy-ReleasePath([string]$RelativePath, [switch]$Optional) {
    $Source = Join-Path $RepositoryRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Source)) {
        if ($Optional) { return }
        Write-BuildFailure "release_input_missing" "A required release input is missing." @{ path = $Source }
    }
    $Destination = Join-Path $PackageRoot $RelativePath
    $DestinationParent = Split-Path -Parent $Destination
    if (-not [string]::IsNullOrWhiteSpace($DestinationParent)) {
        New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force
}

$Version = (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepositoryRoot "VERSION")).Trim()
if ($Version -notmatch "^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$") {
    Write-BuildFailure "version_invalid" "VERSION contains an unsupported value." @{ version = $Version }
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $RepositoryRoot "artifacts\release"
}
$OutputDirectory = Resolve-AbsolutePath $OutputDirectory
$BuildRoot = Join-Path $OutputDirectory ".build-windows-x64-$Version"
$PackageRoot = Join-Path $BuildRoot "wechat-visual-director"
Assert-ChildPath $OutputDirectory $BuildRoot

if (Test-Path -LiteralPath $BuildRoot) {
    Remove-Item -LiteralPath $BuildRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $PackageRoot, $OutputDirectory | Out-Null

if (-not $SkipWorkbenchBuild) {
    $Pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
    if ($null -eq $Pnpm) {
        Write-BuildFailure "pnpm_missing" "pnpm is required only while building the release workbench."
    }
    & $Pnpm.Source --dir (Join-Path $RepositoryRoot "apps\web") install --frozen-lockfile
    if ($LASTEXITCODE -ne 0) { Write-BuildFailure "workbench_install_failed" "Workbench dependencies could not be restored." }
    & $Pnpm.Source --dir (Join-Path $RepositoryRoot "apps\web") build
    if ($LASTEXITCODE -ne 0) { Write-BuildFailure "workbench_build_failed" "The production workbench build failed." }
}

$RequiredFiles = @(
    "VERSION",
    "SKILL.md",
    "INSTALL_FOR_AGENT.md",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    ".env.example",
    "scripts\bootstrap.ps1",
    "scripts\install.ps1",
    "scripts\persistent-launcher.ps1",
    "scripts\persistent-launcher.cmd",
    "scripts\visual-director.ps1",
    "scripts\visual-director.cmd",
    "scripts\uninstall.ps1",
    "apps\api\pyproject.toml",
    "apps\api\.env.example",
    "apps\web\dist",
    "references",
    "agents",
    "assets",
    "contracts",
    "samples\skill-alpha"
)
foreach ($RelativePath in $RequiredFiles) { Copy-ReleasePath $RelativePath }

$PythonArchiveName = "python-$PythonVersion-embed-amd64.zip"
$PythonArchive = Join-Path $BuildRoot $PythonArchiveName
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/$PythonArchiveName"
$PythonRoot = Join-Path $PackageRoot "runtime\python"
New-Item -ItemType Directory -Force -Path $PythonRoot | Out-Null
try {
    Invoke-WebRequest -UseBasicParsing -Uri $PythonUrl -OutFile $PythonArchive
    Expand-Archive -LiteralPath $PythonArchive -DestinationPath $PythonRoot -Force
} catch {
    Write-BuildFailure "python_runtime_download_failed" "The pinned Python embeddable runtime could not be downloaded." @{
        url = $PythonUrl
        reason = $_.Exception.Message
    }
}

$PthFile = Get-ChildItem -LiteralPath $PythonRoot -Filter "python*._pth" -File | Select-Object -First 1
if ($null -eq $PthFile) {
    Write-BuildFailure "python_runtime_invalid" "The Python embeddable runtime is missing its path configuration."
}
$PthLines = @(Get-Content -LiteralPath $PthFile.FullName | Where-Object {
    $_ -notmatch "^\s*#?\s*import site\s*$" -and $_ -notmatch "^\s*Lib[\\/]site-packages\s*$"
})
$PthLines += "Lib\site-packages"
$PthLines += "import site"
[IO.File]::WriteAllLines($PthFile.FullName, $PthLines, $Utf8NoBom)

$RuntimePython = Join-Path $PythonRoot "python.exe"
$GetPip = Join-Path $BuildRoot "get-pip.py"
try {
    Invoke-WebRequest -UseBasicParsing -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip
    & $RuntimePython $GetPip --disable-pip-version-check --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw "get-pip exited with code $LASTEXITCODE" }
    & $RuntimePython -m pip install --disable-pip-version-check --no-compile --no-warn-script-location (Join-Path $RepositoryRoot "apps\api")
    if ($LASTEXITCODE -ne 0) { throw "pip install exited with code $LASTEXITCODE" }
    & $RuntimePython -c "import fastapi, PIL, uvicorn, visual_director, yaml; print('runtime-ok')"
    if ($LASTEXITCODE -ne 0) { throw "runtime import check exited with code $LASTEXITCODE" }
} catch {
    Write-BuildFailure "python_runtime_build_failed" "The bundled Python runtime dependencies could not be prepared." @{
        reason = $_.Exception.Message
    }
}

$PackageInventory = Join-Path $PackageRoot "runtime\THIRD_PARTY_PACKAGES.json"
$InventoryScriptPath = Join-Path $BuildRoot "write-package-inventory.py"
$InventoryScript = @'
import importlib.metadata as md, json, pathlib, sys
rows=[]
for dist in md.distributions():
    name=dist.metadata.get("Name")
    if name:
        rows.append({"name":name,"version":dist.version,"license":dist.metadata.get("License") or None})
pathlib.Path(sys.argv[1]).write_text(json.dumps(sorted(rows,key=lambda x:x["name"].lower()),ensure_ascii=False,indent=2),encoding="utf-8")
'@
[IO.File]::WriteAllText($InventoryScriptPath, $InventoryScript, $Utf8NoBom)
& $RuntimePython $InventoryScriptPath $PackageInventory
if ($LASTEXITCODE -ne 0) {
    Write-BuildFailure "runtime_inventory_failed" "The bundled dependency inventory could not be generated."
}

Get-ChildItem -LiteralPath $PythonRoot -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -LiteralPath $PythonRoot -File -Recurse -Filter "*.pyc" | Remove-Item -Force

$RuntimeVersion = (& $RuntimePython -c "import platform; print(platform.python_version())").Trim()
$PayloadBytes = (Get-ChildItem -LiteralPath $PackageRoot -Recurse -File | Measure-Object Length -Sum).Sum
$Manifest = [ordered]@{
    schema_version = "release_package.v0.1"
    application = "wechat-visual-director"
    application_version = $Version
    platform = "windows"
    architecture = "x64"
    python_runtime = $RuntimeVersion
    runtime_mode = "bundled_python"
    requires_git = $false
    requires_system_python = $false
    requires_node = $false
    requires_wenyan = $false
    payload_bytes = $PayloadBytes
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $PackageRoot "release-manifest.json")

$AssetName = "wechat-visual-director-windows-x64-v$Version.zip"
$AssetPath = Join-Path $OutputDirectory $AssetName
$ChecksumPath = "$AssetPath.sha256"
if (Test-Path -LiteralPath $AssetPath) { Remove-Item -LiteralPath $AssetPath -Force }
if (Test-Path -LiteralPath $ChecksumPath) { Remove-Item -LiteralPath $ChecksumPath -Force }
Compress-Archive -LiteralPath $PackageRoot -DestinationPath $AssetPath -CompressionLevel Optimal
$Hash = (Get-FileHash -LiteralPath $AssetPath -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText($ChecksumPath, "$Hash  $AssetName`n", $Utf8NoBom)
$AssetBytes = (Get-Item -LiteralPath $AssetPath).Length

Remove-Item -LiteralPath $BuildRoot -Recurse -Force

[ordered]@{
    ok = $true
    schema_version = "windows_release_build.v0.1"
    version = $Version
    asset = $AssetPath
    checksum_file = $ChecksumPath
    sha256 = $Hash
    asset_bytes = $AssetBytes
    payload_bytes = $PayloadBytes
    python_version = $RuntimeVersion
} | ConvertTo-Json -Depth 5 -Compress
