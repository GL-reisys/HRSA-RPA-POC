<#
.SYNOPSIS
    One-shot server bootstrap for the HRSA-RPA-POC IIS deployment target.

.DESCRIPTION
    Idempotent. Safe to re-run after partial installs.

    Installs:
      - IIS + ASP.NET role + Management Service
      - URL Rewrite 2.1
      - Application Request Routing 3.0 (and enables proxy)
      - HttpPlatformHandler 1.2
      - Python 3.12  (machine-wide)
      - Node 20 LTS  (machine-wide)

    Uses winget when available, falls back to direct MSI downloads when not.
    Run as Administrator. Reboot is NOT required.

.PARAMETER PythonVersion
    Python version to install if missing. Defaults to 3.12.

.PARAMETER NodeMajor
    Node major version. Defaults to 20 (LTS).

.PARAMETER OfflineInstallerDir
    Optional directory containing pre-staged installer MSIs/EXEs (for air-gapped
    servers). If supplied, downloads are skipped and the named files are used:
      - rewrite_amd64_en-US.msi
      - requestRouter_amd64.msi
      - HttpPlatformHandler_amd64.msi   (case-insensitive match; either casing works)
      - python-3.12.x-amd64.exe         (matched by glob)
      - node-v20.x.x-x64.msi            (matched by glob)

.EXAMPLE
    .\Install-Prereqs.ps1

.EXAMPLE
    .\Install-Prereqs.ps1 -OfflineInstallerDir C:\stage\installers
#>

[CmdletBinding()]
param(
    [string] $PythonVersion = '3.12',
    [int]    $NodeMajor = 20,
    [string] $OfflineInstallerDir
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Write-OK      { param([string]$Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Skip    { param([string]$Msg) Write-Host "  [skip] $Msg" -ForegroundColor DarkGray }
function Write-Do      { param([string]$Msg) Write-Host "  [do]   $Msg" -ForegroundColor Yellow }
function Fail          { param([string]$Msg) Write-Host "ERROR: $Msg" -ForegroundColor Red; exit 1 }

# Admin check
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "Must run as Administrator."
}

function Get-OfflineInstaller {
    param([string]$Pattern)
    if (-not $OfflineInstallerDir) { return $null }
    $hit = Get-ChildItem -Path $OfflineInstallerDir -Filter $Pattern -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) { return $hit.FullName }
    return $null
}

function Invoke-MsiInstall {
    param([string]$Path, [string]$Label)
    Write-Do "Installing $Label ($Path)"
    $proc = Start-Process msiexec.exe -ArgumentList @('/i', "`"$Path`"", '/qn', '/norestart') -Wait -PassThru
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        Fail "msiexec failed for $Label (exit $($proc.ExitCode))."
    }
    Write-OK "$Label installed."
}

function Invoke-ExeInstall {
    param([string]$Path, [string[]]$Args, [string]$Label)
    Write-Do "Installing $Label ($Path)"
    $proc = Start-Process $Path -ArgumentList $Args -Wait -PassThru
    if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
        Fail "$Label installer failed (exit $($proc.ExitCode))."
    }
    Write-OK "$Label installed."
}

function Download-File {
    param([string]$Url, [string]$Out, [string]$Label)
    Write-Do "Downloading $Label"
    Write-Host "         from $Url" -ForegroundColor DarkGray
    Write-Host "         to   $Out" -ForegroundColor DarkGray
    try {
        # TLS 1.2 + follow redirects (fwlink URLs redirect to the actual MSI).
        [System.Net.ServicePointManager]::SecurityProtocol = `
            [System.Net.SecurityProtocolType]::Tls12 -bor `
            [System.Net.SecurityProtocolType]::Tls13
        Invoke-WebRequest -Uri $Url -OutFile $Out -UseBasicParsing -MaximumRedirection 10
    } catch {
        Fail "Failed to download $Label from $Url`n       $($_.Exception.Message)`n       If this server is air-gapped, re-run with -OfflineInstallerDir <path>."
    }
}

# -----------------------------------------------------------------------------
# IIS roles
# -----------------------------------------------------------------------------
Write-Section 'IIS role + features'
$features = @(
    'IIS-WebServerRole',
    'IIS-WebServer',
    'IIS-CommonHttpFeatures',
    'IIS-StaticContent',
    'IIS-DefaultDocument',
    'IIS-HttpErrors',
    'IIS-HttpRedirect',
    'IIS-ApplicationDevelopment',
    'IIS-NetFxExtensibility45',
    'IIS-HealthAndDiagnostics',
    'IIS-HttpLogging',
    'IIS-LoggingLibraries',
    'IIS-RequestMonitor',
    'IIS-Security',
    'IIS-RequestFiltering',
    'IIS-Performance',
    'IIS-HttpCompressionStatic',
    'IIS-WebServerManagementTools',
    'IIS-ManagementConsole',
    'IIS-ManagementService'
)
foreach ($f in $features) {
    $state = (Get-WindowsOptionalFeature -Online -FeatureName $f -ErrorAction SilentlyContinue).State
    if ($state -eq 'Enabled') {
        Write-Skip "$f already enabled"
    } else {
        Write-Do "Enabling $f"
        Enable-WindowsOptionalFeature -Online -FeatureName $f -All -NoRestart | Out-Null
        Write-OK "$f enabled"
    }
}

Import-Module WebAdministration -ErrorAction Stop

# Authoritative install check -- look for the IIS module registration itself.
# Registry markers under HKLM\SOFTWARE\Microsoft\IIS Extensions are unreliable
# (HttpPlatformHandler does not create one), so use Get-WebGlobalModule.
function Test-IisModuleInstalled {
    param([string]$ModuleName)
    return $null -ne (Get-WebGlobalModule -Name $ModuleName -ErrorAction SilentlyContinue)
}

# -----------------------------------------------------------------------------
# URL Rewrite
# -----------------------------------------------------------------------------
Write-Section 'URL Rewrite 2.1'
if (Test-IisModuleInstalled 'RewriteModule') {
    Write-Skip 'URL Rewrite already installed'
} else {
    $offline = Get-OfflineInstaller 'rewrite_amd64_en-US.msi'
    if (-not $offline) {
        $tmp = Join-Path $env:TEMP 'rewrite_amd64_en-US.msi'
        Download-File `
            -Url 'https://download.microsoft.com/download/1/2/8/128E2E22-C1B9-44A4-BE2A-5859ED1D4592/rewrite_amd64_en-US.msi' `
            -Out $tmp -Label 'URL Rewrite 2.1 MSI'
        $offline = $tmp
    }
    Invoke-MsiInstall -Path $offline -Label 'URL Rewrite 2.1'
}

# -----------------------------------------------------------------------------
# Application Request Routing
# -----------------------------------------------------------------------------
Write-Section 'Application Request Routing 3.0'
if (Test-IisModuleInstalled 'ApplicationRequestRouting') {
    Write-Skip 'ARR already installed'
} else {
    $offline = Get-OfflineInstaller 'requestRouter_amd64.msi'
    if (-not $offline) {
        $tmp = Join-Path $env:TEMP 'requestRouter_amd64.msi'
        # fwlink -- stable; Microsoft re-points it as they shuffle the underlying paths.
        Download-File `
            -Url 'https://go.microsoft.com/fwlink/?LinkID=615136' `
            -Out $tmp -Label 'ARR 3.0 MSI'
        $offline = $tmp
    }
    Invoke-MsiInstall -Path $offline -Label 'Application Request Routing 3.0'
}

# Enable ARR proxy at the server level (off by default after install).
Write-Do 'Enabling ARR proxy at server level'
& "$env:windir\system32\inetsrv\appcmd.exe" set config -section:system.webServer/proxy /enabled:true /commit:apphost | Out-Null
Write-OK 'ARR proxy enabled'

# -----------------------------------------------------------------------------
# HttpPlatformHandler
# -----------------------------------------------------------------------------
Write-Section 'HttpPlatformHandler 1.2'
if (Test-IisModuleInstalled 'httpPlatformHandler') {
    Write-Skip 'HttpPlatformHandler already installed'
} else {
    # Match either casing -- Microsoft has shipped both `httpPlatformHandler` and `HttpPlatformHandler`.
    $offline = Get-OfflineInstaller '*ttpPlatformHandler*amd64.msi'
    if (-not $offline) {
        $tmp = Join-Path $env:TEMP 'HttpPlatformHandler_amd64.msi'
        # fwlink -- stable; the underlying download.microsoft.com URLs for HPH
        # have 404'd repeatedly over the years, but the fwlink id is constant.
        Download-File `
            -Url 'https://go.microsoft.com/fwlink/?LinkId=690721' `
            -Out $tmp -Label 'HttpPlatformHandler 1.2 MSI'
        $offline = $tmp
    }
    Invoke-MsiInstall -Path $offline -Label 'HttpPlatformHandler 1.2'
}

# -----------------------------------------------------------------------------
# Pinned fallback installer URLs (used when winget is unavailable or fails).
# Direct downloads from the official upstream. Update these as new releases
# come out -- the script logs which one it used so drift is visible.
# -----------------------------------------------------------------------------
$PythonFallbackVersion = '3.12.7'
$PythonFallbackUrl     = "https://www.python.org/ftp/python/$PythonFallbackVersion/python-$PythonFallbackVersion-amd64.exe"
$NodeFallbackVersion   = '20.18.1'   # current Node 20 LTS at time of writing
$NodeFallbackUrl       = "https://nodejs.org/dist/v$NodeFallbackVersion/node-v$NodeFallbackVersion-x64.msi"

# Run winget and capture its output so failure messages are useful.
# Returns $true on success, prints captured output on failure and returns $false.
function Try-WingetInstall {
    param([string]$Id, [string]$Label)
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "  [info] winget not available." -ForegroundColor DarkGray
        return $false
    }
    Write-Do "winget install --id $Id"
    $stdoutFile = New-TemporaryFile
    $stderrFile = New-TemporaryFile
    $proc = Start-Process winget `
        -ArgumentList @('install', '--id', $Id, '--silent',
                        '--accept-package-agreements', '--accept-source-agreements',
                        '--scope', 'machine') `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
    $stdout = Get-Content -Raw $stdoutFile -ErrorAction SilentlyContinue
    $stderr = Get-Content -Raw $stderrFile -ErrorAction SilentlyContinue
    Remove-Item $stdoutFile, $stderrFile -ErrorAction SilentlyContinue

    if ($proc.ExitCode -eq 0) {
        Write-OK "$Label installed via winget"
        return $true
    }
    # Exit -1978335189 (0x8A150011) = "No applicable upgrade found" -- already at latest.
    # Exit -1978335212 (0x8A15002C) = "Package already installed" -- treat as success.
    if ($proc.ExitCode -in @(-1978335189, -1978335212)) {
        Write-OK "$Label already at latest version (winget exit $($proc.ExitCode))"
        return $true
    }

    Write-Host "  [warn] winget install of $Id failed (exit $($proc.ExitCode)). Output:" -ForegroundColor Yellow
    if ($stdout) { Write-Host $stdout.TrimEnd() -ForegroundColor DarkGray }
    if ($stderr) { Write-Host $stderr.TrimEnd() -ForegroundColor DarkGray }
    return $false
}

# -----------------------------------------------------------------------------
# Python
# -----------------------------------------------------------------------------
Write-Section "Python $PythonVersion"
$pythonOk = $false
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($pythonExe) {
    $detected = (& $pythonExe -V 2>&1) -replace 'Python ', ''
    if ($detected -like "$PythonVersion.*") {
        Write-Skip "Python $detected already on PATH ($pythonExe)"
        $pythonOk = $true
    } else {
        Write-Host "  [warn] Found Python $detected on PATH, but $PythonVersion.x requested. Installing alongside."
    }
}
if (-not $pythonOk) {
    $offline = Get-OfflineInstaller "python-$PythonVersion.*-amd64.exe"
    if ($offline) {
        Invoke-ExeInstall -Path $offline `
            -Args @('/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_pip=1', 'Include_launcher=1') `
            -Label "Python $PythonVersion (offline)"
    } elseif (Try-WingetInstall -Id "Python.Python.$PythonVersion" -Label "Python $PythonVersion") {
        # winget handled it.
    } else {
        Write-Host "  [info] Falling back to python.org direct download." -ForegroundColor DarkGray
        $tmp = Join-Path $env:TEMP "python-$PythonFallbackVersion-amd64.exe"
        Download-File -Url $PythonFallbackUrl -Out $tmp -Label "Python $PythonFallbackVersion installer"
        Invoke-ExeInstall -Path $tmp `
            -Args @('/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_pip=1', 'Include_launcher=1') `
            -Label "Python $PythonFallbackVersion (direct download)"
    }
}

# -----------------------------------------------------------------------------
# Node.js
# -----------------------------------------------------------------------------
Write-Section "Node.js $NodeMajor LTS"
$nodeOk = $false
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
if ($nodeExe) {
    $detected = (& $nodeExe -v 2>&1).TrimStart('v')
    if ($detected -like "$NodeMajor.*") {
        Write-Skip "Node $detected already on PATH ($nodeExe)"
        $nodeOk = $true
    } else {
        Write-Host "  [warn] Found Node $detected on PATH, but $NodeMajor.x requested. Installing alongside."
    }
}
if (-not $nodeOk) {
    $offline = Get-OfflineInstaller "node-v$NodeMajor.*-x64.msi"
    if ($offline) {
        Invoke-MsiInstall -Path $offline -Label "Node $NodeMajor LTS (offline)"
    } elseif (Try-WingetInstall -Id 'OpenJS.NodeJS.LTS' -Label "Node $NodeMajor LTS") {
        # winget handled it.
    } else {
        Write-Host "  [info] Falling back to nodejs.org direct download." -ForegroundColor DarkGray
        $tmp = Join-Path $env:TEMP "node-v$NodeFallbackVersion-x64.msi"
        Download-File -Url $NodeFallbackUrl -Out $tmp -Label "Node v$NodeFallbackVersion installer"
        Invoke-MsiInstall -Path $tmp -Label "Node v$NodeFallbackVersion (direct download)"
    }
}

# -----------------------------------------------------------------------------
# Refresh PATH for the current session
# -----------------------------------------------------------------------------
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

# -----------------------------------------------------------------------------
# Sanity checks
# -----------------------------------------------------------------------------
Write-Section 'Post-install sanity'
$pythonVer = & python -V 2>&1
$nodeVer   = & node -v 2>&1
Write-Host "  python: $pythonVer"
Write-Host "  node:   $nodeVer"

$arrEnabled = (& "$env:windir\system32\inetsrv\appcmd.exe" list config -section:system.webServer/proxy /text:enabled).Trim()
if ($arrEnabled -ne 'true') { Fail "ARR proxy is not enabled at server level (got: '$arrEnabled')." }
Write-Host "  ARR proxy: enabled"

# Verify each module actually registered with IIS. An MSI can exit 0 without
# having properly registered (rare, but happens with partial uninstalls).
foreach ($mod in @(
    @{ Name='RewriteModule';             Friendly='URL Rewrite' }
    @{ Name='ApplicationRequestRouting'; Friendly='ARR' }
    @{ Name='httpPlatformHandler';       Friendly='HttpPlatformHandler' }
)) {
    if (-not (Test-IisModuleInstalled $mod.Name)) {
        Fail "$($mod.Friendly) MSI ran but IIS module '$($mod.Name)' is not registered. Try: appcmd.exe list modules, then reinstall manually from $env:TEMP\$($mod.Name)*.msi."
    }
    Write-Host "  IIS module: $($mod.Name) registered"
}

Write-Section 'Done'
Write-Host "Server is ready. Next step: run deploy-prod.ps1 (or let Octopus invoke it)." -ForegroundColor Green
exit 0
