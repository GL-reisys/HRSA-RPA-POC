<#
.SYNOPSIS
    One-shot diagnostic for HRSA-RPA-POC IIS deployments. Run this when
    deploy-prod.ps1 hangs at the health check (or anytime the site is
    misbehaving).

.DESCRIPTION
    Gathers the signals you actually need to root-cause a silent worker:
      - W3SVC + WAS service state
      - App pool state (running? recycling? worker process up?)
      - IIS site state + bindings
      - Hosts file entry for the configured hostname
      - Cert presence + binding
      - netstat for the bound ports (is anything actually listening?)
      - HttpPlatformHandler stdout logs (where Node/Python startup errors land)
      - Recent W3SVC / HTTPSYS event log errors
      - Direct invoke against backend (loopback) and frontend (public)
      - Final summary with likely-cause hints

    Reads the same local.env that deploy-prod.ps1 uses (or pass -EnvFile).
    Read-only -- changes nothing.

.PARAMETER EnvFile
    Path to local.env. Defaults to local.env next to this script.

.PARAMETER TailLines
    How many lines to print from each HPH stdout log. Default 40.

.EXAMPLE
    .\Diagnose.ps1

.EXAMPLE
    .\Diagnose.ps1 -TailLines 100 | Tee-Object diag.log
#>

[CmdletBinding()]
param(
    [string] $EnvFile = '',
    [int]    $TailLines = 40
)

$ErrorActionPreference = 'Continue'   # keep going even when individual checks fail
$ProgressPreference    = 'SilentlyContinue'

function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Write-OK      { param([string]$Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Bad     { param([string]$Msg) Write-Host "  [BAD]  $Msg" -ForegroundColor Red }
function Write-Info    { param([string]$Msg) Write-Host "  [info] $Msg" -ForegroundColor DarkGray }

# Load local.env if present (same loader as deploy-prod.ps1).
if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $PSScriptRoot 'local.env'
}
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#')) { return }
        $p = $line -split '=', 2
        if ($p.Length -ne 2) { return }
        $n = $p[0].Trim(); $v = $p[1].Trim()
        if (($v.StartsWith('"') -and $v.EndsWith('"')) -or
            ($v.StartsWith("'") -and $v.EndsWith("'"))) { $v = $v.Substring(1, $v.Length - 2) }
        if (-not [Environment]::GetEnvironmentVariable($n, 'Process')) {
            [Environment]::SetEnvironmentVariable($n, $v, 'Process')
        }
    }
}

$SiteHostname = $env:SITE_HOSTNAME
$BackendPort  = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { '5000' }
$DeployRoot   = if ($env:DEPLOY_ROOT)  { $env:DEPLOY_ROOT  } else { 'C:\inetpub\HRSA-RPA-POC' }
$CertThumb    = $env:CERT_THUMBPRINT

$FrontSite = 'HRSA-RPA-POC-Frontend'
$BackSite  = 'HRSA-RPA-POC-Backend'
$FrontPool = 'HRSA-RPA-POC-Frontend'
$BackPool  = 'HRSA-RPA-POC-Backend'

Write-Section 'Context'
Write-Info "SITE_HOSTNAME:    $SiteHostname"
Write-Info "BACKEND_PORT:     $BackendPort"
Write-Info "DEPLOY_ROOT:      $DeployRoot"
Write-Info "CERT_THUMBPRINT:  $CertThumb"

# -----------------------------------------------------------------------------
# IIS services
# -----------------------------------------------------------------------------
Write-Section 'IIS services'
foreach ($svc in @('W3SVC', 'WAS')) {
    $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if (-not $s)                 { Write-Bad "$svc service not present" }
    elseif ($s.Status -ne 'Running') { Write-Bad "$svc service is $($s.Status)" }
    else                              { Write-OK "$svc running" }
}

Import-Module WebAdministration -ErrorAction SilentlyContinue

# -----------------------------------------------------------------------------
# App pools
# -----------------------------------------------------------------------------
Write-Section 'App pools'
foreach ($pool in @($BackPool, $FrontPool)) {
    if (-not (Test-Path "IIS:\AppPools\$pool")) {
        Write-Bad "$pool does not exist (deploy-prod.ps1 was not run, or it failed before site config)"
        continue
    }
    $p = Get-Item "IIS:\AppPools\$pool"
    $state = (Get-WebAppPoolState -Name $pool).Value
    $identity = $p.processModel.identityType
    Write-Info "$pool : state=$state, identity=$identity, managedRuntime='$($p.managedRuntimeVersion)', startMode=$($p.startMode)"
    if ($state -ne 'Started') { Write-Bad "$pool is $state -- worker won't be running" }

    # Worker process actually up? Look for w3wp.exe whose CommandLine references this pool.
    $w3wp = Get-CimInstance Win32_Process -Filter "Name='w3wp.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match "-ap `"$([Regex]::Escape($pool))`"" }
    if ($w3wp) {
        Write-OK "  worker w3wp.exe PID=$($w3wp.ProcessId) running"
    } else {
        Write-Info "  no w3wp.exe yet -- normal until first request, unless startMode=AlwaysRunning"
    }
}

# -----------------------------------------------------------------------------
# Sites + bindings
# -----------------------------------------------------------------------------
Write-Section 'Sites + bindings'
foreach ($site in @($BackSite, $FrontSite)) {
    if (-not (Test-Path "IIS:\Sites\$site")) {
        Write-Bad "$site does not exist"
        continue
    }
    $s = Get-Website -Name $site
    Write-Info "$site : state=$($s.State), physicalPath=$($s.PhysicalPath)"
    if ($s.State -ne 'Started') { Write-Bad "$site is $($s.State)" }
    Get-WebBinding -Name $site | ForEach-Object {
        Write-Info "  binding: protocol=$($_.protocol) bindingInformation=$($_.bindingInformation)"
    }
    if (-not (Test-Path (Join-Path $s.PhysicalPath 'Web.config'))) {
        Write-Bad "  Web.config MISSING at $($s.PhysicalPath) -- HttpPlatformHandler has no config"
    }
}

# -----------------------------------------------------------------------------
# Web.config unsubstituted tokens (very common silent failure)
# -----------------------------------------------------------------------------
Write-Section 'Web.config token substitution'
foreach ($site in @($FrontSite, $BackSite)) {
    $cfg = Join-Path (Get-Website -Name $site -ErrorAction SilentlyContinue).PhysicalPath 'Web.config'
    if (-not (Test-Path $cfg)) { continue }
    # Strip XML comments before checking -- the templates have literal "#{...}"
    # in comments explaining what the tokens are, which produced false positives.
    $raw = Get-Content -Raw $cfg
    $noComments = [regex]::Replace($raw, '<!--[\s\S]*?-->', '')
    $tokenMatches = [regex]::Matches($noComments, '#\{[^}]+\}')
    if ($tokenMatches.Count -gt 0) {
        Write-Bad "$site Web.config has unsubstituted tokens (HPH cannot start the worker):"
        $tokenMatches | ForEach-Object { Write-Host "      $($_.Value)" -ForegroundColor Red }
    } else {
        Write-OK "$site Web.config has no leftover #{...} tokens"
    }
}

# Parse each Web.config as XML -- catches malformed files (the IIS HTTP 500.19
# "configuration file is not well-formed XML" case). Most common cause: a "--"
# sequence inside an XML comment, which the spec forbids.
Write-Section 'Web.config XML well-formedness'
foreach ($site in @($FrontSite, $BackSite)) {
    $cfg = Join-Path (Get-Website -Name $site -ErrorAction SilentlyContinue).PhysicalPath 'Web.config'
    if (-not (Test-Path $cfg)) { continue }
    try {
        [xml](Get-Content -Raw $cfg) | Out-Null
        Write-OK "$site Web.config parses as XML"
    } catch {
        Write-Bad "$site Web.config FAILED to parse: $($_.Exception.Message)"
        # Pinpoint -- inside comments since that's the usual culprit.
        $raw = Get-Content -Raw $cfg
        foreach ($m in [regex]::Matches($raw, '<!--([\s\S]*?)-->')) {
            if ($m.Groups[1].Value -match '--') {
                $lineNo = ($raw.Substring(0, $m.Index) -split "`n").Count
                Write-Bad "  -> line $lineNo : XML comment contains forbidden '--' sequence (IIS 500.19)"
            }
        }
    }
}

# -----------------------------------------------------------------------------
# Rendered Web.config dump (with secrets masked)
# -----------------------------------------------------------------------------
Write-Section 'Rendered <httpPlatform> elements (secrets masked)'
foreach ($site in @($BackSite, $FrontSite)) {
    $cfg = Join-Path (Get-Website -Name $site -ErrorAction SilentlyContinue).PhysicalPath 'Web.config'
    if (-not (Test-Path $cfg)) { continue }
    Write-Host ""
    Write-Host "  --- $site : $cfg ---" -ForegroundColor Yellow
    $raw = Get-Content -Raw $cfg
    # Mask anything that looks like an API key (alnum 24+ chars) inside value="..."
    $masked = [regex]::Replace($raw,
        '(value=")(sk-[^"]+|[A-Za-z0-9_\-]{24,})(")',
        '$1<masked>$3')
    # Print only the <httpPlatform>...</httpPlatform> block to keep output short.
    $m = [regex]::Match($masked, '<httpPlatform[\s\S]*?</httpPlatform>')
    if ($m.Success) {
        $m.Value -split "`n" | ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Bad "  no <httpPlatform> element found"
    }
}

# -----------------------------------------------------------------------------
# Verify the processPath / venv python exists and waitress is importable
# -----------------------------------------------------------------------------
Write-Section 'Backend venv sanity'
$backendCfg = Join-Path $DeployRoot 'backend\Web.config'
if (Test-Path $backendCfg) {
    $procPath = ([regex]::Match((Get-Content -Raw $backendCfg), 'processPath="([^"]+)"')).Groups[1].Value
    if ($procPath) {
        Write-Info "processPath: $procPath"
        if (Test-Path $procPath) {
            Write-OK 'python.exe exists at processPath'
            try {
                $pyver = (& $procPath -V 2>&1)
                Write-OK "python responds: $pyver"
                # `import waitress` is the actual smoke test -- waitress doesn't expose __version__ uniformly.
                $waitressCheck = (& $procPath -c "import waitress; print('waitress imported OK')" 2>&1)
                if ($LASTEXITCODE -eq 0) {
                    Write-OK "$waitressCheck"
                } else {
                    Write-Bad "waitress NOT importable in venv. Output: $waitressCheck"
                }
                $appCheck = (& $procPath -c "import sys; sys.path.insert(0, r'$(Join-Path $DeployRoot 'backend')'); import app; print('OK')" 2>&1)
                if ($LASTEXITCODE -eq 0) {
                    Write-OK 'backend app.py imports cleanly'
                } else {
                    Write-Bad "backend app.py FAILED to import. This is likely the root cause."
                    Write-Host $appCheck -ForegroundColor DarkGray
                }
            } catch {
                Write-Bad "python invocation failed: $($_.Exception.Message)"
            }
        } else {
            Write-Bad "python.exe NOT found at $procPath -- HPH cannot launch the worker"
        }
    }
}

# -----------------------------------------------------------------------------
# Hosts file + cert (frontend)
# -----------------------------------------------------------------------------
Write-Section "Hosts file entry for $SiteHostname"
if ($SiteHostname) {
    $hosts = Get-Content "$env:WINDIR\System32\drivers\etc\hosts" -ErrorAction SilentlyContinue
    $match = $hosts | Where-Object { $_ -match "^\s*[^#\s]\S*\s+$([Regex]::Escape($SiteHostname))(\s|$)" }
    if ($match) { Write-OK "hosts: $($match -join '; ')" }
    else        { Write-Bad "No hosts entry for $SiteHostname -- the frontend health check (https://$SiteHostname/) will fail DNS." }
}

Write-Section 'TLS cert binding (frontend :443)'
if ($CertThumb) {
    $cert = Get-ChildItem Cert:\LocalMachine\My | Where-Object Thumbprint -eq $CertThumb
    if ($cert) { Write-OK "cert in LocalMachine\My: $($cert.Subject), expires $($cert.NotAfter.ToString('yyyy-MM-dd'))" }
    else       { Write-Bad "Cert $CertThumb NOT in LocalMachine\My" }

    $sslBindings = & "$env:windir\system32\netsh.exe" http show sslcert 2>&1 | Out-String
    if ($sslBindings -match [Regex]::Escape($CertThumb)) {
        Write-OK 'cert is SSL-bound to a port'
    } else {
        Write-Bad "cert $CertThumb is NOT bound to any port -- HTTPS will refuse connections"
    }
}

# -----------------------------------------------------------------------------
# Listeners on the bound ports
# -----------------------------------------------------------------------------
Write-Section 'Listening ports'
foreach ($port in @(443, [int]$BackendPort)) {
    $listen = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    if (-not $listen) {
        Write-Bad "Nothing listening on TCP $port"
    } else {
        foreach ($l in $listen) {
            $procName = (Get-Process -Id $l.OwningProcess -ErrorAction SilentlyContinue).ProcessName
            Write-OK "TCP $port  LocalAddress=$($l.LocalAddress)  PID=$($l.OwningProcess) ($procName)"
        }
    }
}

# -----------------------------------------------------------------------------
# AppPool identity write-access on logs/. If HPH can't write its stdoutLogFile,
# it will refuse to launch the worker and return 500 with NO log -- which is
# exactly the symptom we're seeing.
# -----------------------------------------------------------------------------
Write-Section 'AppPool identity write-access on logs/'
foreach ($pair in @(
    @{ Identity="IIS AppPool\$BackPool";  Dir=(Join-Path $DeployRoot 'backend\logs') }
    @{ Identity="IIS AppPool\$FrontPool"; Dir=(Join-Path $DeployRoot 'frontend\logs') }
)) {
    if (-not (Test-Path $pair.Dir)) {
        Write-Bad "$($pair.Dir) does not exist"
        continue
    }
    try {
        $acl = Get-Acl $pair.Dir
        $rules = $acl.Access | Where-Object {
            $_.IdentityReference.Value -eq $pair.Identity -or
            $_.IdentityReference.Value -eq 'BUILTIN\IIS_IUSRS' -or
            $_.IdentityReference.Value -eq 'NT AUTHORITY\IIS_IUSRS'
        }
        if ($rules) {
            $rules | ForEach-Object {
                Write-OK "$($pair.Dir): $($_.IdentityReference.Value) has $($_.FileSystemRights) ($($_.AccessControlType))"
            }
        } else {
            Write-Bad "$($pair.Dir): no ACE found for $($pair.Identity) or IIS_IUSRS. HPH will fail to write stdout and silently 500."
            Write-Info "  Fix: icacls `"$($pair.Dir)`" /grant `"$($pair.Identity):(OI)(CI)M`" /T"
        }
    } catch {
        Write-Bad "ACL read failed for $($pair.Dir): $($_.Exception.Message)"
    }
}

# -----------------------------------------------------------------------------
# AppPool identity Read & Execute on the python.exe / node.exe install dirs.
# When HPH can't load the worker's DLLs, it dies silent in the kernel loader
# -- returns 500 with NO stdout log. Most-overlooked cause of "HPH won't
# launch the worker".
# -----------------------------------------------------------------------------
Write-Section 'Runtime install dir permissions for AppPool identity'
$backendCfg = Join-Path $DeployRoot 'backend\Web.config'
$frontCfg   = Join-Path $DeployRoot 'frontend\Web.config'
$probes = @()
if (Test-Path $backendCfg) {
    $venvPy = ([regex]::Match((Get-Content -Raw $backendCfg), 'processPath="([^"]+)"')).Groups[1].Value
    if ($venvPy -and (Test-Path $venvPy)) {
        $cfgFile = Join-Path (Split-Path -Parent $venvPy) '..\pyvenv.cfg'
        $cfgFile = [IO.Path]::GetFullPath($cfgFile)
        if (Test-Path $cfgFile) {
            $homeLine = (Get-Content $cfgFile | Where-Object { $_ -match '^home\s*=' }) -replace '^home\s*=\s*', ''
            if ($homeLine) {
                $probes += @{ Pool=$BackPool;  Dir=$homeLine.Trim(); What='Python base install' }
            }
        }
    }
}
if (Test-Path $frontCfg) {
    $nodeExe = ([regex]::Match((Get-Content -Raw $frontCfg), 'processPath="([^"]+)"')).Groups[1].Value
    if ($nodeExe) {
        $probes += @{ Pool=$FrontPool; Dir=(Split-Path -Parent $nodeExe); What='Node install' }
    }
}
foreach ($p in $probes) {
    if (-not (Test-Path $p.Dir)) {
        Write-Bad "$($p.What) dir does not exist: $($p.Dir)"
        continue
    }
    # icacls output is the simplest readable form of effective permissions.
    $aclText = (& icacls $p.Dir 2>$null) -join "`n"
    $poolAce = $aclText -match [Regex]::Escape("IIS AppPool\$($p.Pool)")
    $iisUsr  = $aclText -match 'IIS_IUSRS'
    $users   = $aclText -match 'BUILTIN\\Users|\\Users:'
    if ($poolAce -or $iisUsr -or $users) {
        $who = @()
        if ($poolAce) { $who += "IIS AppPool\$($p.Pool)" }
        if ($iisUsr)  { $who += 'IIS_IUSRS' }
        if ($users)   { $who += 'Users' }
        Write-OK "$($p.What) ($($p.Dir)) readable by: $($who -join ', ')"
    } else {
        Write-Bad "$($p.What) ($($p.Dir)) has NO grant for the pool identity, IIS_IUSRS, or Users."
        Write-Info "  Fix: icacls `"$($p.Dir)`" /grant `"IIS AppPool\$($p.Pool):(OI)(CI)RX`" /T"
        Write-Info "  Then: Restart-WebAppPool $($p.Pool)"
    }
}

# -----------------------------------------------------------------------------
# Full Web.config dump (sanity-check the <handlers> section is intact)
# -----------------------------------------------------------------------------
Write-Section 'Full Web.config (handlers + httpPlatform, secrets masked)'
foreach ($site in @($BackSite, $FrontSite)) {
    $cfg = Join-Path (Get-Website -Name $site -ErrorAction SilentlyContinue).PhysicalPath 'Web.config'
    if (-not (Test-Path $cfg)) { continue }
    Write-Host ""
    Write-Host "  --- $cfg ---" -ForegroundColor Yellow
    $raw = Get-Content -Raw $cfg
    $masked = [regex]::Replace($raw, '(value=")(sk-[^"]+|[A-Za-z0-9_\-]{24,})(")', '$1<masked>$3')
    $masked -split "`n" | ForEach-Object { Write-Host "  $_" }
}

# -----------------------------------------------------------------------------
# HTTPERR log (HTTP.sys's own error log -- HPH worker launch failures land here
# when HPH itself can't open its stdout log)
# -----------------------------------------------------------------------------
Write-Section 'HTTP.sys error log (last 30 lines, filtered)'
$httpErrDir = "$env:WINDIR\System32\LogFiles\HTTPERR"
if (Test-Path $httpErrDir) {
    $latest = Get-ChildItem $httpErrDir -Filter 'httperr*.log' -ErrorAction SilentlyContinue |
              Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        Write-Info "$($latest.FullName) (modified $($latest.LastWriteTime))"
        Get-Content $latest.FullName -Tail 30 |
            Where-Object { $_ -match $BackendPort -or $_ -match '443' -or $_ -match 'HRSA-RPA-POC' } |
            ForEach-Object { Write-Host "  $_" }
    } else {
        Write-Info 'no httperr*.log files'
    }
} else {
    Write-Info "$httpErrDir not present"
}

# -----------------------------------------------------------------------------
# Fetch the actual 500 response body -- sometimes contains the real cause
# -----------------------------------------------------------------------------
Write-Section 'Backend 500 response body'
try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5 -ErrorAction SilentlyContinue
    Write-OK "200 -- backend is now responding ($($resp.StatusCode))"
} catch [System.Net.WebException] {
    if ($_.Exception.Response) {
        $stream = $_.Exception.Response.GetResponseStream()
        $reader = New-Object System.IO.StreamReader($stream)
        $body = $reader.ReadToEnd()
        $reader.Close()
        Write-Info "Response body (first 1.5KB):"
        $bodySnippet = if ($body.Length -gt 1500) { $body.Substring(0, 1500) } else { $body }
        Write-Host $bodySnippet -ForegroundColor DarkGray
    } else {
        Write-Bad "request failed with no response: $($_.Exception.Message)"
    }
}

# -----------------------------------------------------------------------------
# HttpPlatformHandler stdout logs (where Node/Python startup errors land)
# -----------------------------------------------------------------------------
Write-Section "HttpPlatformHandler stdout logs (last $TailLines lines each)"
foreach ($pair in @(
    @{ Label='backend (waitress)'; Dir=(Join-Path $DeployRoot 'backend\logs'); Pattern='waitress-stdout*' }
    @{ Label='frontend (node)';   Dir=(Join-Path $DeployRoot 'frontend\logs'); Pattern='node-stdout*' }
)) {
    if (-not (Test-Path $pair.Dir)) {
        Write-Info "$($pair.Label): log dir does not exist ($($pair.Dir)) -- worker never started, or no requests yet"
        continue
    }
    $logs = Get-ChildItem -Path $pair.Dir -Filter $pair.Pattern -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $logs) {
        Write-Info "$($pair.Label): no logs matching $($pair.Pattern) in $($pair.Dir)"
        continue
    }
    Write-Host ""
    Write-Host "  --- $($pair.Label): $($logs.FullName) (modified $($logs.LastWriteTime)) ---" -ForegroundColor Yellow
    Get-Content $logs.FullName -Tail $TailLines | ForEach-Object { Write-Host "  $_" }
}

# -----------------------------------------------------------------------------
# Recent IIS / HTTPSYS event log errors
# -----------------------------------------------------------------------------
Write-Section 'Recent W3SVC / HTTPSYS / HPH errors (last hour)'
$since = (Get-Date).AddHours(-1)
$events = Get-WinEvent -FilterHashtable @{
    LogName='System'; ProviderName=@('Microsoft-Windows-WAS','Microsoft-Windows-IIS-W3SVC','HTTPSYS','HTTP'); StartTime=$since
} -ErrorAction SilentlyContinue
# Application log: HPH writes events here on worker failures. Cast a wider net
# and filter -- ProviderName filtering on Get-WinEvent is unreliable for HPH.
$appEvents = Get-WinEvent -FilterHashtable @{
    LogName='Application'; StartTime=$since; Level=@(1,2,3)   # Critical, Error, Warning
} -ErrorAction SilentlyContinue | Where-Object {
    $_.ProviderName -match 'IIS|HttpPlatform|ASP.NET|w3wp|Application Error' -or
    $_.Message      -match 'HttpPlatform|httpPlatformHandler|w3wp|HRSA-RPA-POC'
}
$all = @($events) + @($appEvents) | Sort-Object TimeCreated -Descending | Select-Object -First 15
if (-not $all) {
    Write-Info 'No relevant errors in the last hour.'
} else {
    $all | ForEach-Object {
        Write-Host ""
        Write-Host "  [$($_.LevelDisplayName)] $($_.TimeCreated) $($_.ProviderName) (id=$($_.Id))" -ForegroundColor Yellow
        Write-Host "    $($_.Message -replace '\s+', ' ')" -ForegroundColor DarkGray
    }
}

# -----------------------------------------------------------------------------
# Direct probes
# -----------------------------------------------------------------------------
Write-Section 'Direct probes'
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
Write-Info "GET http://127.0.0.1:$BackendPort/health"
try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 5
    Write-OK "backend /health -> $($r.StatusCode)"
    Write-Host "      $($r.Content -replace '\s+', ' ')" -ForegroundColor DarkGray
} catch { Write-Bad "backend /health failed: $($_.Exception.Message)" }

if ($SiteHostname) {
    # PS 5.1-safe cert bypass (the -SkipCertificateCheck flag exists only in PS 7+).
    if (-not ('TrustAllCertsPolicy' -as [type])) {
        Add-Type -TypeDefinition @'
public class TrustAllCertsPolicy : System.Net.ICertificatePolicy {
    public bool CheckValidationResult(System.Net.ServicePoint sp, System.Security.Cryptography.X509Certificates.X509Certificate cert, System.Net.WebRequest req, int problem) { return true; }
}
'@
    }
    [System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy

    Write-Info "GET https://$SiteHostname/ (cert validation disabled for diagnostic)"
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "https://$SiteHostname/" -TimeoutSec 10
        Write-OK "frontend / -> $($r.StatusCode)"
    } catch {
        Write-Bad "frontend / failed: $($_.Exception.Message)"
    }
}

Write-Section 'Done'
Write-Host 'If the cause is not obvious from the above, paste the whole output back and I can help.' -ForegroundColor Green
