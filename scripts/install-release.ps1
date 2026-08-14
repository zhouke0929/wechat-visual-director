[CmdletBinding()]
param(
    [string]$Version = "0.1.0-alpha.20",
    [string]$InstallRoot = "",
    [string]$HostHome = "",
    [switch]$KeepDownload
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$Repository = "zhouke0929/wechat-visual-director"

function Write-InstallFailure([string]$Code, [string]$Message, [hashtable]$Details = @{}) {
    [ordered]@{
        ok = $false
        schema_version = "release_install_result.v0.1"
        error = [ordered]@{ code = $Code; message = $Message; retryable = $true; details = $Details }
    } | ConvertTo-Json -Depth 8 -Compress
    exit 2
}

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-InstallFailure "windows_x64_required" "The current release package supports 64-bit Windows only."
}
if ($Version -notmatch "^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$") {
    Write-InstallFailure "version_invalid" "The requested release version is invalid." @{ version = $Version }
}

$AssetName = "wechat-visual-director-windows-x64-v$Version.zip"
$ReleaseBase = "https://github.com/$Repository/releases/download/v$Version"
$DownloadRoot = Join-Path ([IO.Path]::GetTempPath()) ("wechat-visual-director-release-" + [Guid]::NewGuid().ToString("N"))
$ArchivePath = Join-Path $DownloadRoot $AssetName
$ChecksumPath = "$ArchivePath.sha256"
$ExtractRoot = Join-Path $DownloadRoot "extracted"
New-Item -ItemType Directory -Force -Path $DownloadRoot, $ExtractRoot | Out-Null

try {
    [Console]::Error.WriteLine("[wechat-visual-director] Downloading the verified Windows release package.")
    Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseBase/$AssetName" -OutFile $ArchivePath
    Invoke-WebRequest -UseBasicParsing -Uri "$ReleaseBase/$AssetName.sha256" -OutFile $ChecksumPath
    $ExpectedHash = ((Get-Content -Raw -Encoding UTF8 -LiteralPath $ChecksumPath).Trim() -split "\s+")[0].ToLowerInvariant()
    $ActualHash = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($ExpectedHash) -or $ExpectedHash -ne $ActualHash) {
        Write-InstallFailure "release_checksum_mismatch" "The downloaded release package failed SHA-256 verification." @{
            expected = $ExpectedHash
            actual = $ActualHash
            asset = $AssetName
        }
    }
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $ExtractRoot -Force
    $PackageRoot = Join-Path $ExtractRoot "wechat-visual-director"
    $Bootstrap = Join-Path $PackageRoot "scripts\bootstrap.ps1"
    if (-not (Test-Path -LiteralPath $Bootstrap -PathType Leaf)) {
        Write-InstallFailure "release_package_invalid" "The release package does not contain the expected bootstrap entry." @{
            asset = $AssetName
        }
    }
    $BootstrapArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Bootstrap)
    if (-not [string]::IsNullOrWhiteSpace($InstallRoot)) { $BootstrapArgs += @("-InstallRoot", $InstallRoot) }
    if (-not [string]::IsNullOrWhiteSpace($HostHome)) { $BootstrapArgs += @("-HostHome", $HostHome) }
    $Raw = & powershell @BootstrapArgs
    $ExitCode = $LASTEXITCODE
    try { $Result = (@($Raw) -join [Environment]::NewLine) | ConvertFrom-Json } catch {
        Write-InstallFailure "bootstrap_invalid_output" "The packaged bootstrap did not return valid JSON." @{
            exit_code = $ExitCode
        }
    }
    if ($ExitCode -ne 0 -or -not $Result.ok) {
        Write-InstallFailure "bootstrap_failed" "The packaged installation did not complete." @{ bootstrap = $Result }
    }
    $Result | Add-Member -NotePropertyName install_source -NotePropertyValue "github_release" -Force
    $Result | Add-Member -NotePropertyName release_asset -NotePropertyValue $AssetName -Force
    $Result | Add-Member -NotePropertyName archive_sha256 -NotePropertyValue $ActualHash -Force
    $Result | ConvertTo-Json -Depth 9 -Compress
} catch {
    Write-InstallFailure "release_install_failed" "The release package could not be downloaded or installed." @{
        reason = $_.Exception.Message
        release = "v$Version"
    }
} finally {
    if (-not $KeepDownload -and (Test-Path -LiteralPath $DownloadRoot)) {
        Remove-Item -LiteralPath $DownloadRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
