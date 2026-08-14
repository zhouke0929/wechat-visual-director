[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BundledPython = Join-Path $Root "runtime\python\python.exe"
$VenvPython = Join-Path $Root "apps\api\.venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $BundledPython -PathType Leaf) {
    $BundledPython
} else {
    $VenvPython
}

if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $payload = @{
        ok = $false
        schema_version = "skill_launcher.v0.1"
        error = @{
            code = "core_not_installed"
            message = "Visual Director is not installed. Run scripts/install.ps1 first."
            retryable = $true
            details = @{ installer = (Join-Path $Root "scripts\install.ps1") }
        }
    }
    $payload | ConvertTo-Json -Depth 5 -Compress
    exit 2
}

$env:VISUAL_DIRECTOR_PROJECT_ROOT = $Root
& $Python -m visual_director.cli @CliArgs
exit $LASTEXITCODE
