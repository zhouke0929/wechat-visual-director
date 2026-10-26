# Shared by the Skill, packaged installer and persistent launcher. No data migration.
function Get-WvdPhysicalPath([string]$Path) {
    if (-not ('WvdInstallPaths.Native' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
namespace WvdInstallPaths {
    [StructLayout(LayoutKind.Sequential)]
    public struct FileInfo {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
        public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    public static class Native {
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern SafeFileHandle CreateFile(string path, uint access, uint share,
            IntPtr security, uint disposition, uint flags, IntPtr template);
        [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
        public static extern uint GetFinalPathNameByHandle(SafeFileHandle handle,
            StringBuilder path, uint length, uint flags);
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool GetFileInformationByHandle(SafeFileHandle handle, out FileInfo info);
    }
}
'@
    }
    $Full = [IO.Path]::GetFullPath($Path)
    $Existing = $Full
    $Tail = @()
    while (-not (Test-Path -LiteralPath $Existing)) {
        $Parent = [IO.Path]::GetDirectoryName($Existing.TrimEnd('\'))
        if (-not $Parent -or $Parent -eq $Existing) { throw "Cannot resolve installation path: $Full" }
        $Tail = @([IO.Path]::GetFileName($Existing)) + $Tail
        $Existing = $Parent
    }
    $Handle = [WvdInstallPaths.Native]::CreateFile($Existing, 0, 7, [IntPtr]::Zero, 3, 0x02000000, [IntPtr]::Zero)
    if ($Handle.IsInvalid) {
        $Handle.Dispose()
        throw "Cannot inspect the actual installation path: $Existing"
    }
    try {
        $Buffer = New-Object Text.StringBuilder 32768
        $Length = [WvdInstallPaths.Native]::GetFinalPathNameByHandle($Handle, $Buffer, $Buffer.Capacity, 0)
        if ($Length -eq 0 -or $Length -ge $Buffer.Capacity) { throw "Cannot inspect the actual installation path: $Existing" }
        $Actual = $Buffer.ToString()
        if ($Actual.StartsWith('\\?\UNC\')) { $Actual = '\\' + $Actual.Substring(8) }
        elseif ($Actual.StartsWith('\\?\')) { $Actual = $Actual.Substring(4) }
        foreach ($Part in $Tail) { $Actual = Join-Path $Actual $Part }
        return [IO.Path]::GetFullPath($Actual)
    } finally { $Handle.Dispose() }
}

function Get-WvdDirectoryIdentity([string]$Path) {
    $null = Get-WvdPhysicalPath $Path
    $Handle = [WvdInstallPaths.Native]::CreateFile($Path, 0, 7, [IntPtr]::Zero, 3, 0x02000000, [IntPtr]::Zero)
    try {
        $Info = New-Object WvdInstallPaths.FileInfo
        if ($Handle.IsInvalid -or -not [WvdInstallPaths.Native]::GetFileInformationByHandle($Handle, [ref]$Info)) {
            throw "Cannot identify the actual installation directory: $Path"
        }
        return ('{0:X8}:{1:X8}{2:X8}' -f $Info.Volume, $Info.IndexHigh, $Info.IndexLow)
    } finally { $Handle.Dispose() }
}

function Test-WvdInstallState([string]$Root) {
    foreach ($Relative in @('install.json', 'visual-director.ps1', 'config\install-history.json', 'data\visual-director.db')) {
        if (Test-Path -LiteralPath (Join-Path $Root $Relative) -PathType Leaf) { return $true }
    }
    # Retained assets/configuration must not be silently abandoned either.
    foreach ($Relative in @('data', 'config')) {
        $Directory = Join-Path $Root $Relative
        if ((Test-Path -LiteralPath $Directory -PathType Container) -and
            @(Get-ChildItem -Force -LiteralPath $Directory -ErrorAction Stop | Select-Object -First 1).Count -gt 0) { return $true }
    }
    return $false
}

function Get-WvdCanonicalInstallRoot([string]$Root) {
    $Actual = Get-WvdPhysicalPath $Root
    if (-not $env:LOCALAPPDATA -or -not (Test-Path -LiteralPath $Actual -PathType Container)) { return $Actual }
    $Default = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'wechat-visual-director'))
    if (-not $Actual.Equals($Default, [StringComparison]::OrdinalIgnoreCase)) { return $Actual }
    $Packages = Join-Path $env:LOCALAPPDATA 'Packages'
    if (Test-Path -LiteralPath $Packages -PathType Container) {
        $Identity = Get-WvdDirectoryIdentity $Actual
        foreach ($Package in Get-ChildItem -LiteralPath $Packages -Directory -Filter 'OpenAI.Codex_*' -ErrorAction Stop) {
            $Cache = Join-Path $Package.FullName 'LocalCache\Local\wechat-visual-director'
            if ((Test-Path -LiteralPath $Cache -PathType Container) -and
                (Get-WvdDirectoryIdentity $Cache) -eq $Identity) { return Get-WvdPhysicalPath $Cache }
        }
    }
    return $Actual
}

function Resolve-WvdInstallLocation([string]$InstallRoot = '', [string]$UserDataHome = '') {
    $Explicit = -not [string]::IsNullOrWhiteSpace($InstallRoot)
    if (-not $Explicit -and $UserDataHome) {
        $Profile = Read-WvdUserProfile $UserDataHome
        if ($Profile -and $Profile.active_install_root) {
            $Selected = Get-WvdCanonicalInstallRoot $Profile.active_install_root
            return [pscustomobject]@{requested_root=$Selected; actual_root=$Selected; existing_install=(Test-WvdInstallState $Selected);
                explicit_selection=$false; redirected=$false; candidates=@($Selected); shared_profile=$true}
        }
    }
    if (-not $Explicit) {
        if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is unavailable.' }
        $InstallRoot = Join-Path $env:LOCALAPPDATA 'wechat-visual-director'
    }
    $Requested = [IO.Path]::GetFullPath($InstallRoot)
    $Roots = @($Requested)
    if (-not $Explicit) {
        # Bounded discovery of our own application, not a recursive disk/data scan.
        $Packages = Join-Path $env:LOCALAPPDATA 'Packages'
        if (Test-Path -LiteralPath $Packages -PathType Container) {
            foreach ($Package in Get-ChildItem -LiteralPath $Packages -Directory -Filter 'OpenAI.Codex_*' -ErrorAction Stop) {
                $Roots += Join-Path $Package.FullName 'LocalCache\Local\wechat-visual-director'
            }
        }
    }
    $Candidates = @()
    $Identities = @()
    foreach ($Root in $Roots) {
        if (-not (Test-WvdInstallState $Root)) { continue }
        $Actual = Get-WvdCanonicalInstallRoot $Root
        $Identity = Get-WvdDirectoryIdentity $Actual
        $Index = [Array]::IndexOf($Identities, $Identity)
        if ($Index -lt 0) {
            $Candidates += $Actual
            $Identities += $Identity
        } elseif ($Root -match '\\Packages\\OpenAI\.Codex_[^\\]+\\LocalCache\\Local\\wechat-visual-director$') {
            # Some packaged hosts report the virtual name even from a file
            # handle. The volume/file ID proves these are aliases, not two DBs.
            $Candidates[$Index] = $Actual
        }
    }
    if ($Candidates.Count -gt 1) {
        $Exception = New-Object InvalidOperationException 'Multiple independent installations found. Select an install root; no services or data have been changed.'
        $Exception.Data['code'] = 'install_location_ambiguous'
        $Exception.Data['candidates'] = $Candidates
        throw $Exception
    }
    $Selected = if ($Candidates.Count -eq 1) { $Candidates[0] } else { Get-WvdCanonicalInstallRoot $Requested }
    $ManifestFile = Join-Path $Selected 'install.json'
    if (Test-Path -LiteralPath $ManifestFile -PathType Leaf) {
        $Metadata = Get-Content -LiteralPath $ManifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Metadata.physical_install_root -and
            -not $Selected.Equals([string]$Metadata.physical_install_root, [StringComparison]::OrdinalIgnoreCase)) {
            $Exception = New-Object InvalidOperationException 'The installation location differs from its recorded physical root. Confirm the original installation before continuing.'
            $Exception.Data['code'] = 'install_location_changed'
            $Exception.Data['candidates'] = @($Selected, [string]$Metadata.physical_install_root)
            throw $Exception
        }
    }
    return [pscustomobject]@{
        requested_root = $Requested
        actual_root = $Selected
        existing_install = ($Candidates.Count -eq 1)
        explicit_selection = $Explicit
        redirected = (-not $Requested.Equals($Selected, [StringComparison]::OrdinalIgnoreCase))
        candidates = @($Candidates)
    }
}

function Get-WvdUserDataHome([string]$Value = '', [string]$HostHome = '', [switch]$Isolated) {
    if ($Isolated) { return '' }
    if (-not $Value) {
        $HomeDirectory = if ($HostHome) { $HostHome } else { [Environment]::GetFolderPath('UserProfile') }
        if (-not $HomeDirectory) { throw 'A user profile is required for shared history.' }
        $Value = Join-Path $HomeDirectory '.wechat-visual-director'
    }
    $Actual = Get-WvdPhysicalPath $Value
    if ($Actual.TrimEnd('\') -eq ([IO.Path]::GetPathRoot($Actual)).TrimEnd('\') -or
        $Actual.TrimEnd('\') -eq ([Environment]::GetFolderPath('UserProfile')).TrimEnd('\')) {
        throw 'The shared history home must be a dedicated application directory, not the disk or user profile root.'
    }
    return $Actual
}

function Assert-WvdDataHomeSeparation([string]$HomeDirectory, [string]$ProgramRoot) {
    if (-not $HomeDirectory) { return }
    $DataHome = [IO.Path]::GetFullPath($HomeDirectory).TrimEnd('\')
    $Program = [IO.Path]::GetFullPath($ProgramRoot).TrimEnd('\')
    if ($DataHome.Equals($Program, [StringComparison]::OrdinalIgnoreCase) -or
        $DataHome.StartsWith($Program + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Shared history must be outside the removable program directory.'
    }
}

function Read-WvdUserProfile([string]$HomeDirectory) {
    $File = Join-Path $HomeDirectory 'profile.json'
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { return $null }
    try {
        $Profile = Get-Content -LiteralPath $File -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($Profile.schema_version -ne 'user_profile.v1' -or -not $Profile.profile_id) { throw 'Invalid shared history registry.' }
        foreach ($Pair in @(@('data_root','data'), @('runtime_root','runtime'), @('config_file','config\.env.local'))) {
            $Name = $Pair[0]
            $Expected = Get-WvdPhysicalPath (Join-Path $HomeDirectory $Pair[1])
            if (-not $Expected.Equals((Get-WvdPhysicalPath $Profile.$Name), [StringComparison]::OrdinalIgnoreCase)) { throw 'The shared history path does not match its registry.' }
        }
        if (-not (Test-Path -LiteralPath (Join-Path $Profile.data_root 'visual-director.db') -PathType Leaf)) {
            throw 'The registered history database is missing. No empty database was created.'
        }
        return $Profile
    } catch {
        $Exception = New-Object InvalidOperationException $_.Exception.Message
        $Exception.Data['code'] = 'shared_data_unavailable'
        throw $Exception
    }
}

function Resolve-WvdStoredPath([string]$Value, [string]$RecordedRoot, [string]$ActualRoot) {
    # Old releases recorded virtual paths. Rebind only paths inside that installation.
    # External/custom data paths are not automatically moved or substituted.
    if ([string]::IsNullOrWhiteSpace($Value)) { throw 'The installation manifest contains an empty path.' }
    $Full = [IO.Path]::GetFullPath($Value)
    if (-not [string]::IsNullOrWhiteSpace($RecordedRoot)) {
        $Prefix = [IO.Path]::GetFullPath($RecordedRoot).TrimEnd('\') + '\'
        if ($Full.StartsWith($Prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return Get-WvdPhysicalPath (Join-Path $ActualRoot $Full.Substring($Prefix.Length))
        }
    }
    return Get-WvdPhysicalPath $Full
}

function Get-WvdPathFailure($Exception) {
    $Code = 'install_location_check_failed'
    $Candidates = @()
    if ($Exception.Data.Contains('code')) { $Code = [string]$Exception.Data['code'] }
    if ($Exception.Data.Contains('candidates')) { $Candidates = @($Exception.Data['candidates']) }
    return @{ code = $Code; message = $Exception.Message; details = @{ candidates = $Candidates; action = 'select_install_root' } }
}

function Assert-WvdLegacyLauncher([string]$Root) {
    $File = Join-Path $Root 'install.json'
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { return }
    $Manifest = Get-Content -LiteralPath $File -Raw -Encoding UTF8 | ConvertFrom-Json
    $Version = [string]$Manifest.current_version
    if ($Version -notmatch '^[0-9A-Za-z][0-9A-Za-z.-]{0,63}$') { throw 'The installed version identifier is invalid.' }
    $Helper = Join-Path $Root "versions\$Version\skills\wechat-visual-director\scripts\windows-install-paths.ps1"
    if (Test-Path -LiteralPath $Helper -PathType Leaf) { return }
    $Recorded = [string]$Manifest.install_root
    if ($Recorded -and ((-not (Test-Path -LiteralPath $Recorded)) -or
        (Get-WvdDirectoryIdentity $Recorded) -ne (Get-WvdDirectoryIdentity $Root))) {
        $Exception = New-Object InvalidOperationException 'The old launcher points to a different location. Upgrade this selected installation before starting; no data was moved.'
        $Exception.Data['code'] = 'install_location_upgrade_required'
        $Exception.Data['candidates'] = @($Root)
        throw $Exception
    }
}

function Update-WvdLegacyManifestPaths([string]$Root) {
    # Called only by an authorized upgrade, after its data snapshot/backup.
    # This repairs metadata, not database/assets/config contents or their location.
    $File = Join-Path $Root 'install.json'
    if (-not (Test-Path -LiteralPath $File -PathType Leaf)) { return }
    $Manifest = Get-Content -LiteralPath $File -Raw -Encoding UTF8 | ConvertFrom-Json
    $Recorded = [string]$Manifest.install_root
    if (-not $Recorded) { return }
    $Actual = Get-WvdCanonicalInstallRoot $Root
    $Values = @{}
    foreach ($Name in @('current_root', 'data_root', 'runtime_root', 'config_file', 'launcher', 'launcher_cmd', 'uninstaller')) {
        if ($Manifest.$Name) { $Values[$Name] = Resolve-WvdStoredPath ([string]$Manifest.$Name) $Recorded $Actual }
    }
    # Resolve every field before making a single metadata change.
    foreach ($Name in $Values.Keys) { $Manifest.$Name = $Values[$Name] }
    $Manifest.install_root = $Actual
    $Manifest | Add-Member -NotePropertyName physical_install_root -NotePropertyValue $Actual -Force
    $Temporary = "$File.location-$([Guid]::NewGuid().ToString('N')).tmp"
    try {
        $Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Temporary -Encoding UTF8
        Move-Item -LiteralPath $Temporary -Destination $File -Force
    } finally {
        if (Test-Path -LiteralPath $Temporary) { Remove-Item -LiteralPath $Temporary -Force }
    }
}
