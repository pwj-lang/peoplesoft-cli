# Read-only local discovery. Never read process CommandLine or credential values.
$ErrorActionPreference = 'SilentlyContinue'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$paths = @{}
function Add-AdPath([string]$candidate, [string]$source) {
    if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        if ([IO.Path]::GetFileName($resolved) -ieq 'pside.exe') {
            if (-not $paths.ContainsKey($resolved)) { $paths[$resolved] = @() }
            $paths[$resolved] += $source
        }
    }
}
Get-Process -Name pside | ForEach-Object { Add-AdPath $_.Path 'running_process' }
Get-Command pside.exe | ForEach-Object { Add-AdPath $_.Source 'PATH' }
foreach ($key in @('HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\pside.exe',
                  'HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths\pside.exe',
                  'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\pside.exe')) {
    Add-AdPath (Get-ItemProperty -LiteralPath $key).'(default)' 'registry_app_path'
}
$roots = @($env:PS_HOME)
foreach ($drive in (Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3')) {
    foreach ($folder in @('Program Files', 'Program Files (x86)', 'PeopleSoft', 'PeopleTools', 'PT')) {
        $base = Join-Path ($drive.DeviceID + '\') $folder
        if (Test-Path -LiteralPath $base) {
            $roots += Get-ChildItem -LiteralPath $base -Directory |
                Where-Object Name -Match '^(PT|PS|People|Oracle)' | Select-Object -ExpandProperty FullName
        }
    }
    $roots += Get-ChildItem -LiteralPath ($drive.DeviceID + '\') -Directory |
        Where-Object Name -Match '^(PT|PS_HOME|PeopleSoft|PeopleTools)' | Select-Object -ExpandProperty FullName
}
foreach ($root in ($roots | Where-Object { $_ } | Sort-Object -Unique)) {
    foreach ($suffix in @('bin\client\winx86\pside.exe', 'bin\client\winx64\pside.exe',
                          'client\winx86\pside.exe', 'client\winx64\pside.exe', 'pside.exe')) {
        Add-AdPath (Join-Path $root $suffix) 'known_install_location'
    }
}
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'),
                       [Environment]::GetFolderPath('CommonDesktopDirectory'),
                       [Environment]::GetFolderPath('StartMenu'),
                       [Environment]::GetFolderPath('CommonStartMenu'))) {
    if ($folder -and (Test-Path -LiteralPath $folder)) {
        Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -Recurse | ForEach-Object {
            Add-AdPath ($shell.CreateShortcut($_.FullName).TargetPath) 'shortcut'
        }
    }
}
$rows = @(foreach ($path in ($paths.Keys | Sort-Object)) {
    $version = (Get-Item -LiteralPath $path).VersionInfo
    $hint = [regex]::Match($path, '(?i)PT(8\.\d{2}(?:\.\d+)?)').Groups[1].Value
    [pscustomobject]@{
        path = $path
        file_version = $version.FileVersion
        product_version = $version.ProductVersion
        directory_version_hint = $hint
        sources = @($paths[$path] | Sort-Object -Unique)
    }
})
ConvertTo-Json -InputObject $rows -Depth 4 -Compress
