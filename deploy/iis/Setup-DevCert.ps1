<#
.SYNOPSIS
    One-shot dev-only TLS cert + hosts entry helper for local IIS testing.

.DESCRIPTION
    Creates a self-signed TLS certificate for the dev hostname, imports it
    into LocalMachine\My (where deploy-prod.ps1 looks), trusts it in
    LocalMachine\Root so the browser doesn't warn, and adds an
    entry to %WINDIR%\System32\drivers\etc\hosts mapping the hostname to
    127.0.0.1.

    DEV USE ONLY. Real environments get a real cert from a CA -- this
    helper exists so the IIS deploy pipeline can be smoke-tested on a
    developer machine without having to source one.

    Idempotent: if a cert with the same subject already exists, it's reused.
    Re-running won't add duplicate hosts entries.

.PARAMETER Hostname
    The hostname to use. Defaults to rpa-poc.local. Whatever you pick,
    set the same value as SITE_HOSTNAME in deploy/iis/local.env.

.PARAMETER ValidityDays
    Cert validity period. Defaults to 365.

.PARAMETER UpdateLocalEnv
    If supplied, writes/updates SITE_HOSTNAME and CERT_THUMBPRINT in
    deploy/iis/local.env (creates the file from local.env.example if it
    doesn't exist).

.EXAMPLE
    .\Setup-DevCert.ps1
    # Creates rpa-poc.local cert, prints the thumbprint to paste into local.env.

.EXAMPLE
    .\Setup-DevCert.ps1 -Hostname rpa-dev.localhost -UpdateLocalEnv
    # Cert + hosts entry + writes the values into local.env automatically.
#>

[CmdletBinding()]
param(
    [string] $Hostname = 'rpa-poc.local',
    [int]    $ValidityDays = 365,
    [switch] $UpdateLocalEnv
)

$ErrorActionPreference = 'Stop'

function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Write-OK      { param([string]$Msg) Write-Host "  [OK]   $Msg" -ForegroundColor Green }
function Write-Do      { param([string]$Msg) Write-Host "  [do]   $Msg" -ForegroundColor Yellow }
function Write-Skip    { param([string]$Msg) Write-Host "  [skip] $Msg" -ForegroundColor DarkGray }
function Fail          { param([string]$Msg) Write-Host "ERROR: $Msg" -ForegroundColor Red; exit 1 }

# Admin check (cert + hosts need it)
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail "Must run as Administrator."
}

# -----------------------------------------------------------------------------
# Cert
# -----------------------------------------------------------------------------
Write-Section "Self-signed cert for $Hostname"
$subject = "CN=$Hostname"
$existing = Get-ChildItem -Path Cert:\LocalMachine\My |
    Where-Object { $_.Subject -eq $subject -and $_.NotAfter -gt (Get-Date) } |
    Sort-Object NotAfter -Descending | Select-Object -First 1

if ($existing) {
    Write-Skip "Cert already in LocalMachine\My (expires $($existing.NotAfter.ToString('yyyy-MM-dd')))"
    $cert = $existing
} else {
    Write-Do "Creating cert (valid $ValidityDays days)"
    $cert = New-SelfSignedCertificate `
        -DnsName $Hostname, 'localhost', '127.0.0.1' `
        -Subject $subject `
        -CertStoreLocation 'Cert:\LocalMachine\My' `
        -KeyExportPolicy Exportable `
        -KeyUsage DigitalSignature, KeyEncipherment `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -NotAfter (Get-Date).AddDays($ValidityDays) `
        -FriendlyName "HRSA-RPA-POC dev cert ($Hostname)"
    Write-OK "Created (thumbprint: $($cert.Thumbprint))"
}

# Also drop it into Trusted Root so the local browser doesn't complain.
$rootStore = Get-ChildItem -Path Cert:\LocalMachine\Root |
    Where-Object Thumbprint -eq $cert.Thumbprint
if ($rootStore) {
    Write-Skip 'Cert already trusted in LocalMachine\Root'
} else {
    Write-Do 'Adding cert to LocalMachine\Root (trusts it for this box only)'
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
    $store.Open('ReadWrite')
    $store.Add($cert)
    $store.Close()
    Write-OK 'Trusted'
}

# -----------------------------------------------------------------------------
# hosts entry
# -----------------------------------------------------------------------------
Write-Section "hosts entry: 127.0.0.1 $Hostname"
$hostsPath = "$env:WINDIR\System32\drivers\etc\hosts"
$hostsContent = Get-Content -Path $hostsPath -Raw
# Match a line that ends with the hostname (whitespace-separated).
$pattern = "(?m)^\s*[^#\s]\S*\s+$([Regex]::Escape($Hostname))\s*$"
if ($hostsContent -match $pattern) {
    Write-Skip "hosts already maps $Hostname"
} else {
    Write-Do "Appending '127.0.0.1 $Hostname' to $hostsPath"
    $line = "127.0.0.1`t$Hostname`t# HRSA-RPA-POC dev"
    # Make sure we start on a new line.
    if ($hostsContent -and -not $hostsContent.EndsWith("`n")) {
        Add-Content -Path $hostsPath -Value '' -Encoding ASCII
    }
    Add-Content -Path $hostsPath -Value $line -Encoding ASCII
    Write-OK 'Added'
}

# -----------------------------------------------------------------------------
# Optional: update local.env in place
# -----------------------------------------------------------------------------
if ($UpdateLocalEnv) {
    Write-Section 'Updating deploy/iis/local.env'
    $envPath = Join-Path $PSScriptRoot 'local.env'
    if (-not (Test-Path $envPath)) {
        $examplePath = Join-Path $PSScriptRoot 'local.env.example'
        if (-not (Test-Path $examplePath)) {
            Fail "Neither local.env nor local.env.example found at $PSScriptRoot."
        }
        Write-Do "Bootstrapping from local.env.example"
        Copy-Item -Path $examplePath -Destination $envPath
    }
    $envContent = Get-Content -Path $envPath -Raw
    $envContent = $envContent -replace '(?m)^SITE_HOSTNAME=.*$',   "SITE_HOSTNAME=$Hostname"
    $envContent = $envContent -replace '(?m)^CERT_THUMBPRINT=.*$', "CERT_THUMBPRINT=$($cert.Thumbprint)"
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8 -NoNewline
    Write-OK "SITE_HOSTNAME=$Hostname"
    Write-OK "CERT_THUMBPRINT=$($cert.Thumbprint)"
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
Write-Section 'Done'
Write-Host "Hostname:   $Hostname  (maps to 127.0.0.1 in hosts)" -ForegroundColor Green
Write-Host "Thumbprint: $($cert.Thumbprint)" -ForegroundColor Green
Write-Host ""
if (-not $UpdateLocalEnv) {
    Write-Host "Paste these into deploy/iis/local.env:" -ForegroundColor Yellow
    Write-Host "  SITE_HOSTNAME=$Hostname"
    Write-Host "  CERT_THUMBPRINT=$($cert.Thumbprint)"
    Write-Host ""
    Write-Host "Or re-run with -UpdateLocalEnv to write them automatically." -ForegroundColor DarkGray
}
exit 0
