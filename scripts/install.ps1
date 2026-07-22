[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$VenvDir = Join-Path $ApiDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

function Write-Failure([string]$Code, [string]$Message, [hashtable]$Details = @{}) {
    @{
        ok = $false
        schema_version = "skill_install_result.v0.1"
        error = @{
            code = $Code
            message = $Message
            retryable = $true
            details = $Details
        }
    } | ConvertTo-Json -Depth 6 -Compress
    exit 2
}

if (-not (Test-Path -LiteralPath (Join-Path $ApiDir "pyproject.toml") -PathType Leaf)) {
    Write-Failure "project_layout_missing" "apps/api/pyproject.toml was not found." @{ root = $Root }
}
if (-not (Test-Path -LiteralPath (Join-Path $WebDir "package.json") -PathType Leaf)) {
    Write-Failure "project_layout_missing" "apps/web/package.json was not found." @{ root = $Root }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Python) {
    Write-Failure "python_not_found" "Python 3.11 or newer is required."
}

$VersionText = & $Python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$VersionParts = $VersionText.Trim().Split(".")
if ([int]$VersionParts[0] -lt 3 -or ([int]$VersionParts[0] -eq 3 -and [int]$VersionParts[1] -lt 11)) {
    Write-Failure "python_version_unsupported" "Python 3.11 or newer is required." @{ detected = $VersionText.Trim() }
}

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    & $Python.Source -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Failure "venv_create_failed" "Could not create the Python virtual environment." }
}

& $VenvPython -m pip install --quiet --disable-pip-version-check -e $ApiDir
if ($LASTEXITCODE -ne 0) { Write-Failure "python_install_failed" "Could not install the Visual Director API package." }

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
if ($LASTEXITCODE -ne 0) { Write-Failure "web_install_failed" "Could not install the Web workbench dependencies." }

@{
    ok = $true
    schema_version = "skill_install_result.v0.1"
    root = $Root
    python = $VersionText.Trim()
    launcher = (Join-Path $Root "scripts\visual-director.ps1")
    next_action = "run_doctor"
} | ConvertTo-Json -Depth 4 -Compress
