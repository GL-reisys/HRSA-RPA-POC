<#
.SYNOPSIS
    One-shot production IIS deployment of the HRSA-RPA-POC stack (PowerShell).

.DESCRIPTION
    PowerShell entry point invoked by Octopus on the target IIS server
    AFTER Octopus has:
      1. Pulled the build artifact (HRSA-RPA-POC-iis-<version>.zip)
         from Azure DevOps
      2. Unzipped it to a staging directory ($PACKAGE_ROOT)
      3. Substituted #{...} tokens in this script AND in
         web.config.frontend.tpl / web.config.backend.tpl

    What this script does:
      - Preflight (fails fast -- no changes on disk).
      - Snapshots current deployment to <DEPLOY_ROOT>.previous for rollback.
      - Copies new frontend + backend payloads in.
      - Rebuilds the backend venv from the bundled wheelhouse, installs
        waitress, then drops the substituted Web.config files in place.
      - Creates / updates the two IIS app pools and two sites.
      - Health-checks both endpoints. On failure, swaps back to the
        previous snapshot.

.NOTES
    Octopus token substitution runs on this file BEFORE PowerShell parses it,
    so the literal `#{...}` tokens below are replaced with their values.
    For a manual run, set the corresponding env vars (see .EXAMPLE).

    Pair with [octopus-runbook.md](octopus-runbook.md) for the full Octopus
    variable list and project setup.

.PARAMETER EnvFile
    Path to a `name=value` env file (same format as scripts/azure/local.env).
    If omitted, the script looks for `local.env` next to itself. Values from
    the file populate process env vars only if not already set, so explicit
    `$env:NAME = ...` assignments and Octopus token substitution still win.
    Ignored under Octopus (Octopus substitutes tokens directly into this
    script and provides env vars).

.EXAMPLE
    # Manual local run on the target server (as Administrator):
    #   1. Copy local.env.example to local.env and fill in the values.
    #   2. Run:
    .\deploy-prod.ps1
    #
    # Or point at a non-default env file:
    .\deploy-prod.ps1 -EnvFile C:\stage\my-test.env

.EXAMPLE
    # Pure-env-var form (no file):
    $env:SITE_HOSTNAME           = 'rpa-poc.example.gov'
    $env:CERT_THUMBPRINT         = 'A1B2C3D4...'
    $env:DEPLOY_ROOT             = 'C:\inetpub\HRSA-RPA-POC'
    $env:BACKEND_PORT            = '5000'
    $env:AZURE_OPENAI_ENDPOINT   = 'https://...openai.azure.us/'
    $env:AZURE_OPENAI_API_KEY    = '<secret>'
    $env:AZURE_OPENAI_DEPLOYMENT = 'gpt-4'
    $env:PACKAGE_ROOT            = '.\package'    # where the unzipped artifact lives
    .\deploy-prod.ps1

.OUTPUTS
    Exit codes:
      0 -- deploy succeeded, both sites healthy
      1 -- preflight failure (nothing changed)
      2 -- artifact swap failed (rollback to previous version attempted)
      3 -- deploy completed but health checks did not pass within timeout
#>

[CmdletBinding()]
param(
    [string] $EnvFile = ''
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Write-OK      { param([string]$Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Do      { param([string]$Msg) Write-Host "  [do]   $Msg" -ForegroundColor Yellow }
function Write-Warn    { param([string]$Msg) Write-Host "  [warn] $Msg" -ForegroundColor Yellow }
function Fail          { param([string]$Msg, [int]$Code = 1) Write-Host "ERROR: $Msg" -ForegroundColor Red; exit $Code }

# Resolve an Octopus token or env var. Treats unsubstituted `#{...}` as missing.
function Resolve-Input {
    param([string]$Name, [string]$OctopusValue)
    $envVal = [Environment]::GetEnvironmentVariable($Name)
    if ($envVal) { return $envVal }
    if ($OctopusValue -and -not $OctopusValue.StartsWith('#{')) { return $OctopusValue }
    return $null
}

function Require-Input {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        $hint  = "Missing required input: $Name`n"
        $hint += "       Looked in:`n"
        $hint += "         - process env var `$env:$Name`n"
        $hint += "         - local.env at $EnvFile $(if (Test-Path $EnvFile) { '(present)' } else { '(not found)' })`n"
        if (Test-Path $EnvFile) {
            $hasVar = (Get-Content $EnvFile | Where-Object { $_ -match "^\s*$Name\s*=" }) -ne $null
            $hint += "         - line `"$Name=...`" in that file $(if ($hasVar) { '(present)' } else { '(missing -- add it)' })`n"
        }
        $hint += "       Fix:`n"
        $hint += "         - add `"$Name=<value>`" to $EnvFile, OR`n"
        $hint += "         - `$env:$Name = '<value>'  before invoking the script, OR`n"
        $hint += "         - re-run with -EnvFile <path-to-your-env-file>"
        Fail $hint 1
    }
}

# Load name=value pairs from a .env-style file into process env vars.
# Mirrors scripts/azure/deploy_local.ps1's Import-DotEnv. Does NOT overwrite
# already-set values, so explicit `$env:X = ...` and Octopus substitution win.
function Import-DotEnv {
    param([string]$Path)
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $parts = $line -split '=', 2
        if ($parts.Length -ne 2) { return }
        $name  = $parts[0].Trim()
        $value = $parts[1].Trim()
        # Strip optional surrounding quotes.
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not [Environment]::GetEnvironmentVariable($name, 'Process')) {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

# -----------------------------------------------------------------------------
# local.env loader (manual / dev runs only)
# Octopus does not need this -- it substitutes #{...} into this script directly
# and sets the deploy-time env vars on the Tentacle process.
# -----------------------------------------------------------------------------
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $PSScriptRoot 'local.env'
}
if (Test-Path $EnvFile) {
    Write-Host "Loading env vars from $EnvFile" -ForegroundColor DarkGray
    Import-DotEnv -Path $EnvFile
} else {
    # Not an error -- Octopus runs won't have this file. The required-input
    # check below will fail loudly if anything is actually missing.
    Write-Host "No local.env at $EnvFile (skipping -- expected under Octopus)" -ForegroundColor DarkGray
}

# -----------------------------------------------------------------------------
# Inputs -- Octopus tokens fall through to env vars (now populated from local.env).
# -----------------------------------------------------------------------------
$SiteHostname          = Resolve-Input 'SITE_HOSTNAME'           '#{SiteHostname}'
$CertThumbprint        = Resolve-Input 'CERT_THUMBPRINT'         '#{CertThumbprint}'
$DeployRoot            = Resolve-Input 'DEPLOY_ROOT'             '#{DeployRoot}'
$BackendPort           = Resolve-Input 'BACKEND_PORT'            '#{BackendPort}'
$AzureOpenAiEndpoint   = Resolve-Input 'AZURE_OPENAI_ENDPOINT'   '#{AzureOpenAiEndpoint}'
$AzureOpenAiApiKey     = Resolve-Input 'AZURE_OPENAI_API_KEY'    '#{AzureOpenAiApiKey}'
$AzureOpenAiDeployment = Resolve-Input 'AZURE_OPENAI_DEPLOYMENT' '#{AzureOpenAiDeployment}'
$DatabaseUrl           = Resolve-Input 'DATABASE_URL'            '#{DatabaseUrl}'    # optional
$PackageRoot           = Resolve-Input 'PACKAGE_ROOT'            '#{PackageRoot}'

if (-not $PackageRoot) { $PackageRoot = $PSScriptRoot }     # default: this script's folder
if (-not $BackendPort) { $BackendPort = '5000' }

$FrontendSiteName = 'HRSA-RPA-POC-Frontend'
$BackendSiteName  = 'HRSA-RPA-POC-Backend'
$FrontendPoolName = 'HRSA-RPA-POC-Frontend'
$BackendPoolName  = 'HRSA-RPA-POC-Backend'

# -----------------------------------------------------------------------------
# Preflight
# -----------------------------------------------------------------------------
Write-Section 'Preflight: required inputs'
@(
    @{ Name='SITE_HOSTNAME';           Value=$SiteHostname }
    @{ Name='CERT_THUMBPRINT';         Value=$CertThumbprint }
    @{ Name='DEPLOY_ROOT';             Value=$DeployRoot }
    @{ Name='BACKEND_PORT';            Value=$BackendPort }
    @{ Name='AZURE_OPENAI_ENDPOINT';   Value=$AzureOpenAiEndpoint }
    @{ Name='AZURE_OPENAI_API_KEY';    Value=$AzureOpenAiApiKey }
    @{ Name='AZURE_OPENAI_DEPLOYMENT'; Value=$AzureOpenAiDeployment }
) | ForEach-Object { Require-Input $_.Name $_.Value }

Write-Section 'Preflight: admin context'
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "deploy-prod.ps1 must run as Administrator (Octopus Tentacle service account needs admin rights)." 1
}

Write-Section 'Preflight: WebAdministration module'
try {
    Import-Module WebAdministration -ErrorAction Stop
    Write-OK 'WebAdministration available'
} catch {
    Fail "WebAdministration module unavailable. Run Install-Prereqs.ps1 first." 1
}

Write-Section 'Preflight: required IIS extensions'
# Check by IIS module registration (authoritative) rather than registry, since
# HttpPlatformHandler does not create a marker key under HKLM\...\IIS Extensions.
$requiredModules = @(
    @{ ModuleName = 'RewriteModule';             FriendlyName = 'URL Rewrite';                 Installer = 'rewrite_amd64_en-US.msi' }
    @{ ModuleName = 'ApplicationRequestRouting'; FriendlyName = 'Application Request Routing'; Installer = 'requestRouter_amd64.msi' }
    @{ ModuleName = 'httpPlatformHandler';       FriendlyName = 'HttpPlatformHandler';         Installer = 'HttpPlatformHandler_amd64.msi' }
)
foreach ($m in $requiredModules) {
    $module = Get-WebGlobalModule -Name $m.ModuleName -ErrorAction SilentlyContinue
    if (-not $module) {
        Fail "Missing IIS module '$($m.ModuleName)' ($($m.FriendlyName)). Re-run Install-Prereqs.ps1 -- if it claims '[skip] already installed' but this check still fails, delete the partial install and try again." 1
    }
}
$arrEnabled = (& "$env:windir\system32\inetsrv\appcmd.exe" list config -section:system.webServer/proxy /text:enabled).Trim()
if ($arrEnabled -ne 'true') { Fail "ARR proxy not enabled. Re-run Install-Prereqs.ps1." 1 }
Write-OK 'URL Rewrite + ARR (enabled) + HttpPlatformHandler present'

Write-Section 'Preflight: TLS certificate'
$cert = Get-ChildItem -Path Cert:\LocalMachine\My | Where-Object Thumbprint -eq $CertThumbprint
if (-not $cert) {
    Fail "Cert thumbprint $CertThumbprint not found in LocalMachine\My. Import it before deploying." 1
}
Write-OK "Cert: $($cert.Subject), expires $($cert.NotAfter.ToString('yyyy-MM-dd'))"

Write-Section 'Preflight: package payload'
$frontendStage   = Join-Path $PackageRoot 'frontend'
$backendStage    = Join-Path $PackageRoot 'backend'
$wheelhouseStage = Join-Path $PackageRoot 'wheelhouse'
$reqFile         = Join-Path $backendStage 'requirements.txt'
foreach ($p in @($frontendStage, $backendStage, $wheelhouseStage, $reqFile)) {
    if (-not (Test-Path $p)) { Fail "Expected payload missing: $p" 1 }
}
if (-not (Test-Path (Join-Path $frontendStage 'server.js'))) {
    Fail "Frontend payload missing server.js -- was 'next build' run with output:'standalone'?" 1
}
if (-not (Test-Path (Join-Path $backendStage 'app.py'))) {
    Fail "Backend payload missing app.py" 1
}
Write-OK 'Package looks well-formed'

# Resolve runtime exe paths now so we can substitute into Web.configs.
$NodeExePath = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $NodeExePath) { Fail "node.exe not on PATH. Run Install-Prereqs.ps1." 1 }
$SystemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $SystemPython) { Fail "python.exe not on PATH. Run Install-Prereqs.ps1." 1 }
Write-OK "Node: $NodeExePath"
Write-OK "Python (system): $SystemPython"

# -----------------------------------------------------------------------------
# Stop sites (if they exist) so files aren't locked during the swap
# -----------------------------------------------------------------------------
Write-Section 'Stopping sites + app pools (if they exist)'
foreach ($s in @($FrontendSiteName, $BackendSiteName)) {
    if (Test-Path "IIS:\Sites\$s") {
        Write-Do "Stop-Website $s"
        Stop-Website -Name $s -ErrorAction SilentlyContinue
    }
}
foreach ($p in @($FrontendPoolName, $BackendPoolName)) {
    if (Test-Path "IIS:\AppPools\$p") {
        Write-Do "Stop-WebAppPool $p"
        Stop-WebAppPool -Name $p -ErrorAction SilentlyContinue
        # Wait for worker process to release file handles (max ~30s).
        $deadline = (Get-Date).AddSeconds(30)
        while ((Get-WebAppPoolState -Name $p).Value -ne 'Stopped' -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
        }
    }
}

# -----------------------------------------------------------------------------
# Backup + swap
# -----------------------------------------------------------------------------
$frontendTarget = Join-Path $DeployRoot 'frontend'
$backendTarget  = Join-Path $DeployRoot 'backend'
$logsTarget     = Join-Path $DeployRoot 'logs'
$snapshotRoot   = "$DeployRoot.previous"

Write-Section 'Snapshotting current deployment'
if (Test-Path $DeployRoot) {
    if (Test-Path $snapshotRoot) {
        Write-Do "Removing stale snapshot $snapshotRoot"
        Remove-Item -Path $snapshotRoot -Recurse -Force
    }
    Write-Do "Renaming $DeployRoot -> $snapshotRoot"
    Rename-Item -Path $DeployRoot -NewName ([IO.Path]::GetFileName($snapshotRoot))
    Write-OK 'Snapshot taken (rollback available)'
} else {
    Write-Host '  No prior deployment found -- fresh install.'
}

# Wrap the rest in try/catch so we can roll back atomically on failure.
$swapSucceeded = $false
try {
    Write-Section 'Provisioning new deploy root'
    New-Item -ItemType Directory -Path $DeployRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $frontendTarget -Force | Out-Null
    New-Item -ItemType Directory -Path $backendTarget -Force | Out-Null
    New-Item -ItemType Directory -Path $logsTarget -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $frontendTarget 'logs') -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $backendTarget 'logs') -Force | Out-Null

    Write-Section 'Copying payload'
    Write-Do "frontend: $frontendStage -> $frontendTarget"
    Copy-Item -Path (Join-Path $frontendStage '*') -Destination $frontendTarget -Recurse -Force
    Write-Do "backend:  $backendStage -> $backendTarget"
    Copy-Item -Path (Join-Path $backendStage '*') -Destination $backendTarget -Recurse -Force

    # Preserve uploads + sessions across deploys if a snapshot exists.
    if (Test-Path $snapshotRoot) {
        foreach ($persist in @('backend\uploads', 'backend\database', 'backend\data')) {
            $src = Join-Path $snapshotRoot $persist
            $dst = Join-Path $DeployRoot   $persist
            if (Test-Path $src) {
                Write-Do "carry over $persist"
                if (Test-Path $dst) { Remove-Item -Path $dst -Recurse -Force }
                Copy-Item -Path $src -Destination $dst -Recurse -Force
            }
        }
    }
    # Make sure they exist even on a fresh install.
    foreach ($d in @('uploads', 'database', 'data\uploads')) {
        New-Item -ItemType Directory -Path (Join-Path $backendTarget $d) -Force | Out-Null
    }

    Write-Section 'Building backend venv from wheelhouse'
    $venv = Join-Path $backendTarget 'venv'
    & $SystemPython -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed (exit $LASTEXITCODE)" }
    $venvPython = Join-Path $venv 'Scripts\python.exe'

    Write-Do 'pip install (offline, from wheelhouse)'
    & $venvPython -m pip install --upgrade --no-index --find-links $wheelhouseStage pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed (exit $LASTEXITCODE)" }
    & $venvPython -m pip install --no-index --find-links $wheelhouseStage -r $reqFile waitress
    if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt failed (exit $LASTEXITCODE)" }
    Write-OK 'venv ready'

    Write-Section 'Rendering Web.config files'
    # Octopus substituted the secret-bearing tokens in the .tpl files before
    # the package landed here. This pass folds in the runtime-discovered
    # paths (Node exe, venv Python) and re-applies the non-secret tokens so
    # a manual run from the unzipped package also works.
    #
    # Using String.Replace (not -replace) so backslashes and $ in paths are
    # treated literally. PowerShell 5.1 compatible.
    $frontendTpl = Join-Path $PackageRoot 'web.config.frontend.tpl'
    $backendTpl  = Join-Path $PackageRoot 'web.config.backend.tpl'
    $dbUrlValue  = if ([string]::IsNullOrEmpty($DatabaseUrl)) { '' } else { $DatabaseUrl }

    $frontendXml = (Get-Content -Raw $frontendTpl).
        Replace('#{NodeExePath}',  $NodeExePath).
        Replace('#{BackendPort}',  $BackendPort).
        Replace('#{SiteHostname}', $SiteHostname).
        Replace('#{DeployRoot}',   $DeployRoot)
    Set-Content -Path (Join-Path $frontendTarget 'Web.config') -Value $frontendXml -Encoding UTF8 -NoNewline

    $backendXml = (Get-Content -Raw $backendTpl).
        Replace('#{BackendPythonExe}',     $venvPython).
        Replace('#{BackendPort}',          $BackendPort).
        Replace('#{SiteHostname}',         $SiteHostname).
        Replace('#{DeployRoot}',           $DeployRoot).
        Replace('#{AzureOpenAiEndpoint}',  $AzureOpenAiEndpoint).
        Replace('#{AzureOpenAiApiKey}',    $AzureOpenAiApiKey).
        Replace('#{AzureOpenAiDeployment}',$AzureOpenAiDeployment).
        Replace('#{DatabaseUrl}',          $dbUrlValue)
    Set-Content -Path (Join-Path $backendTarget 'Web.config') -Value $backendXml -Encoding UTF8 -NoNewline
    Write-OK 'Web.configs written'

    # -------------------------------------------------------------------------
    # IIS app pools
    # -------------------------------------------------------------------------
    Write-Section 'Configuring IIS app pools'
    foreach ($pool in @($FrontendPoolName, $BackendPoolName)) {
        if (-not (Test-Path "IIS:\AppPools\$pool")) {
            Write-Do "New app pool $pool"
            New-WebAppPool -Name $pool | Out-Null
        }
        Set-ItemProperty -Path "IIS:\AppPools\$pool" -Name managedRuntimeVersion -Value ''
        Set-ItemProperty -Path "IIS:\AppPools\$pool" -Name enable32BitAppOnWin64 -Value $false
        Set-ItemProperty -Path "IIS:\AppPools\$pool" -Name 'processModel.identityType' -Value 'ApplicationPoolIdentity'
        Set-ItemProperty -Path "IIS:\AppPools\$pool" -Name 'processModel.idleTimeout' -Value '00:00:00'   # never idle-recycle
        Set-ItemProperty -Path "IIS:\AppPools\$pool" -Name 'startMode' -Value 'AlwaysRunning'
        Write-OK "$pool configured"
    }

    # Grant pool identities Modify on the deploy root. Use icacls /T (not
    # Set-Acl) so the grant propagates to existing files immediately --
    # Set-Acl only updates the parent ACE and relies on inheritance, which
    # doesn't always flow to files created before the grant.
    foreach ($pool in @($FrontendPoolName, $BackendPoolName)) {
        & icacls $DeployRoot /grant "IIS AppPool\${pool}:(OI)(CI)M" /T /Q | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "icacls grant on $DeployRoot for IIS AppPool\$pool failed" }
    }
    Write-OK "ACLs granted on $DeployRoot (via icacls /T)"

    # Grant pool identities Read & Execute on the Python and Node install dirs.
    # HPH launches python.exe / node.exe AS the pool identity. The venv
    # python.exe is just a launcher that LoadLibrary's python312.dll from the
    # base install. If the pool identity can't read that DLL, the worker dies
    # in the kernel loader BEFORE producing any stdout -- which is exactly the
    # silent 500 symptom HPH presents.
    $pythonRuntimeDir = Split-Path -Parent $SystemPython     # e.g. C:\Program Files\Python312
    $nodeRuntimeDir   = Split-Path -Parent $NodeExePath      # e.g. C:\Program Files\nodejs
    foreach ($pair in @(
        @{ Pool=$BackendPoolName;  Dir=$pythonRuntimeDir; Label='Python install dir' }
        @{ Pool=$FrontendPoolName; Dir=$nodeRuntimeDir;   Label='Node install dir' }
    )) {
        if (Test-Path $pair.Dir) {
            & icacls $pair.Dir /grant "IIS AppPool\$($pair.Pool):(OI)(CI)RX" /T /Q | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-OK "$($pair.Label) read/execute granted to $($pair.Pool): $($pair.Dir)"
            } else {
                Write-Warn "icacls grant on $($pair.Dir) returned $LASTEXITCODE -- you may need to grant manually."
            }
        }
    }

    # -------------------------------------------------------------------------
    # IIS sites
    # -------------------------------------------------------------------------
    Write-Section 'Configuring backend site (loopback only)'
    if (Test-Path "IIS:\Sites\$BackendSiteName") { Remove-Website -Name $BackendSiteName }
    New-Website `
        -Name $BackendSiteName `
        -PhysicalPath $backendTarget `
        -ApplicationPool $BackendPoolName `
        -IPAddress '127.0.0.1' `
        -Port ([int]$BackendPort) `
        -Force | Out-Null
    Set-ItemProperty -Path "IIS:\Sites\$BackendSiteName" -Name 'applicationDefaults.preloadEnabled' -Value $true
    Write-OK "$BackendSiteName bound to 127.0.0.1:$BackendPort"

    # -------------------------------------------------------------------------
    # Default Web Site: stop it so it cannot intercept requests. By default
    # it ships bound to *:80: (empty host header), which is a catch-all that
    # serves the IIS welcome page for ANY hostname on port 80 that doesn't
    # match a more specific binding. Anyone hitting http://<our-host>/ would
    # land there instead of being redirected to HTTPS.
    #
    # This is appropriate for a dedicated app server (the Octopus contract).
    # If running on a shared box where Default Web Site is in use, override
    # by setting KEEP_DEFAULT_SITE=1 in local.env or as an Octopus variable.
    # -------------------------------------------------------------------------
    $keepDefault = Resolve-Input 'KEEP_DEFAULT_SITE' '#{KeepDefaultSite}'
    if ($keepDefault -eq '1' -or $keepDefault -eq 'true') {
        Write-Section 'Default Web Site: leaving alone (KEEP_DEFAULT_SITE set)'
    } else {
        Write-Section 'Default Web Site: stopping (prevents catch-all intercept)'
        # Each step is wrapped because the site / pool can be in a half-deleted
        # state on machines where someone has tinkered with them; we do not
        # want any of these to fail the whole deploy.
        try {
            if (Get-Website -Name 'Default Web Site' -ErrorAction SilentlyContinue) {
                Stop-Website -Name 'Default Web Site' -ErrorAction SilentlyContinue
                try {
                    Set-ItemProperty 'IIS:\Sites\Default Web Site' `
                        -Name serverAutoStart -Value $false -ErrorAction Stop
                } catch {
                    Write-Warn "Could not set serverAutoStart on Default Web Site: $($_.Exception.Message)"
                }
                Write-OK 'Default Web Site stopped'
            } else {
                Write-Host '  Default Web Site not present -- nothing to do.'
            }
        } catch {
            Write-Warn "Default Web Site handling failed (non-fatal): $($_.Exception.Message)"
        }
        try {
            if (Get-WebAppPoolState -Name 'DefaultAppPool' -ErrorAction SilentlyContinue) {
                Stop-WebAppPool -Name 'DefaultAppPool' -ErrorAction SilentlyContinue
                Write-OK 'DefaultAppPool stopped'
            }
        } catch {
            Write-Warn "DefaultAppPool handling failed (non-fatal): $($_.Exception.Message)"
        }
    }

    Write-Section 'Configuring frontend site (public *:443 + *:80 redirect)'
    if (Get-Website -Name $FrontendSiteName -ErrorAction SilentlyContinue) {
        Remove-Website -Name $FrontendSiteName
    }
    New-Website `
        -Name $FrontendSiteName `
        -PhysicalPath $frontendTarget `
        -ApplicationPool $FrontendPoolName `
        -HostHeader $SiteHostname `
        -Port 443 `
        -Ssl `
        -Force | Out-Null
    Write-OK "Site created: $FrontendSiteName"

    # Add a port 80 binding for the same hostname so plain HTTP requests don't
    # vanish into the void. The rewrite rule in Web.config 301s them to HTTPS.
    # Wrap in try/catch -- if the binding already exists from a previous half-
    # completed run, New-WebBinding throws.
    try {
        New-WebBinding -Name $FrontendSiteName -Protocol http -Port 80 `
            -HostHeader $SiteHostname -ErrorAction Stop | Out-Null
        Write-OK "Added :80 binding for $SiteHostname"
    } catch {
        # Already present? Check and move on.
        $has80 = Get-WebBinding -Name $FrontendSiteName -Protocol http -Port 80 `
                    -HostHeader $SiteHostname -ErrorAction SilentlyContinue
        if ($has80) {
            Write-Host "  :80 binding already present -- ok"
        } else {
            Write-Warn ":80 binding add failed: $($_.Exception.Message). HTTP->HTTPS redirect will not work; HTTPS will."
        }
    }

    # Bind the cert. Use netsh as a fallback if the .NET cmdlet path fails --
    # AddSslCertificate() throws 0x800710D8 if the binding hasn't fully
    # propagated to HTTP.sys yet (a known race in PS 5.1).
    try {
        $binding = Get-WebBinding -Name $FrontendSiteName -Protocol 'https' -ErrorAction Stop
        if (-not $binding) { throw "no https binding found on $FrontendSiteName" }
        $binding.AddSslCertificate($CertThumbprint, 'My') | Out-Null
        Write-OK "Cert bound via WebAdministration"
    } catch {
        Write-Warn "AddSslCertificate failed: $($_.Exception.Message)"
        Write-Host "  Retrying via netsh http..."
        # netsh wants the cert hash without spaces and the appid (a GUID; IIS uses a known one).
        $appId = '{4dc3e181-e14b-4a21-b022-59fc669b0914}'
        & "$env:WINDIR\System32\netsh.exe" http delete sslcert hostnameport="${SiteHostname}:443" 2>$null | Out-Null
        & "$env:WINDIR\System32\netsh.exe" http add sslcert `
            hostnameport="${SiteHostname}:443" `
            certhash=$CertThumbprint `
            appid=$appId `
            certstorename=MY 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { throw "netsh sslcert bind failed (exit $LASTEXITCODE)" }
        Write-OK "Cert bound via netsh"
    }

    try {
        Set-ItemProperty -Path "IIS:\Sites\$FrontendSiteName" `
            -Name 'applicationDefaults.preloadEnabled' -Value $true -ErrorAction Stop
    } catch {
        Write-Warn "preloadEnabled set failed (non-fatal): $($_.Exception.Message)"
    }
    Write-OK "$FrontendSiteName bound to *:443 + *:80 (host=$SiteHostname, cert=$CertThumbprint)"

    Write-Section 'Starting app pools + sites'
    Start-WebAppPool -Name $BackendPoolName
    Start-WebAppPool -Name $FrontendPoolName
    Start-Website -Name $BackendSiteName
    Start-Website -Name $FrontendSiteName

    $swapSucceeded = $true

} catch {
    Write-Host ""
    Write-Host "ERROR during artifact swap: $_" -ForegroundColor Red
    if ($_.InvocationInfo) {
        Write-Host "  at: $($_.InvocationInfo.PositionMessage)" -ForegroundColor Red
    }
    if ($_.Exception.InnerException) {
        Write-Host "  inner: $($_.Exception.InnerException.Message)" -ForegroundColor Red
    }
    if ($_.ScriptStackTrace) {
        Write-Host "  stack:" -ForegroundColor Red
        $_.ScriptStackTrace -split "`n" | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }
    if (Test-Path $snapshotRoot) {
        Write-Section 'Rolling back to previous deployment'
        if (Test-Path $DeployRoot) { Remove-Item -Path $DeployRoot -Recurse -Force }
        Rename-Item -Path $snapshotRoot -NewName ([IO.Path]::GetFileName($DeployRoot))
        try {
            Start-WebAppPool -Name $BackendPoolName -ErrorAction SilentlyContinue
            Start-WebAppPool -Name $FrontendPoolName -ErrorAction SilentlyContinue
            Start-Website -Name $BackendSiteName -ErrorAction SilentlyContinue
            Start-Website -Name $FrontendSiteName -ErrorAction SilentlyContinue
        } catch { Write-Warn "Rollback restart partial: $_" }
        Write-Host "Rollback complete." -ForegroundColor Yellow
    } else {
        Write-Warn "No snapshot available -- rollback skipped."
    }
    exit 2
}

# -----------------------------------------------------------------------------
# Post-deploy verification
# -----------------------------------------------------------------------------
Write-Section 'Health check'
# Allow Self-Signed cert in case the public cert is not trusted by the local box.
add-type @"
    using System.Net;
    using System.Security.Cryptography.X509Certificates;
    public class TrustAllCertsPolicy : ICertificatePolicy {
        public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
    }
"@ -ErrorAction SilentlyContinue
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

$deadline = (Get-Date).AddMinutes(5)
$backendOk = $false
$frontendOk = $false
while ((Get-Date) -lt $deadline -and -not ($backendOk -and $frontendOk)) {
    if (-not $backendOk) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5
            if ($r.StatusCode -eq 200) { $backendOk = $true; Write-OK "backend /health -> 200" }
        } catch { }
    }
    if (-not $frontendOk) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri "https://$SiteHostname/" -TimeoutSec 5 -Headers @{Host=$SiteHostname}
            if ($r.StatusCode -lt 500) { $frontendOk = $true; Write-OK "frontend / -> $($r.StatusCode)" }
        } catch { }
    }
    if (-not ($backendOk -and $frontendOk)) { Start-Sleep -Seconds 3 }
}

if (-not ($backendOk -and $frontendOk)) {
    Write-Host ""
    Write-Host "WARN: Deploy completed but health checks did not pass within 5 min." -ForegroundColor Yellow
    Write-Host "      backend  /health (loopback): $(if($backendOk){'OK'}else{'FAIL'})" -ForegroundColor Yellow
    Write-Host "      frontend /        (public):  $(if($frontendOk){'OK'}else{'FAIL'})" -ForegroundColor Yellow
    Write-Host "      Snapshot at $snapshotRoot is still available for manual rollback." -ForegroundColor Yellow
    exit 3
}

Write-Section 'Done'
Write-Host "Deploy succeeded. Both sites healthy." -ForegroundColor Green
Write-Host "  Public:  https://$SiteHostname/" -ForegroundColor Green
Write-Host "  Backend: http://127.0.0.1:$BackendPort/health (loopback only)" -ForegroundColor Green
Write-Host "  Snapshot kept at $snapshotRoot for one cycle." -ForegroundColor Green
exit 0
