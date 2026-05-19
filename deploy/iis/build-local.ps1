<#
.SYNOPSIS
    Build an IIS deploy package locally -- mirrors the azure-pipelines.yml build
    stage so you can run deploy-prod.ps1 without going through ADO.

.DESCRIPTION
    Produces the same package layout the ADO pipeline produces:
        <OutputDir>/
            frontend/                  (Next.js standalone build)
            backend/                   (Flask source, no venv/uploads/cache)
            wheelhouse/                (pre-downloaded win_amd64 wheels)
            web.config.frontend.tpl
            web.config.backend.tpl
            deploy-prod.ps1
            build-info.json

    After this completes, run deploy-prod.ps1 with PACKAGE_ROOT pointed at the
    output directory. Or just `cd` into it and run `.\deploy-prod.ps1`.

.PARAMETER OutputDir
    Where to assemble the package. Defaults to <repo-root>\.local-build\iis.

.PARAMETER RepoRoot
    Repo root. Defaults to two levels above this script (deploy\iis -> repo).

.PARAMETER SkipNpm
    Skip the npm ci + next build step (useful for iterating on backend only).

.PARAMETER SkipWheels
    Skip the pip download step (useful for iterating on frontend only).

.EXAMPLE
    # Default -- full build into .local-build\iis
    .\build-local.ps1

.EXAMPLE
    # Build into a custom dir, then deploy from it
    .\build-local.ps1 -OutputDir C:\stage\rpa
    cd C:\stage\rpa
    .\deploy-prod.ps1

.NOTES
    Requires Node 20+, Python 3.12+, and npm on PATH. Run
    Install-Prereqs.ps1 first if any of those are missing.
#>

[CmdletBinding()]
param(
    [string] $OutputDir,
    [string] $RepoRoot,
    [switch] $SkipNpm,
    [switch] $SkipWheels
)

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'

function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Write-OK      { param([string]$Msg) Write-Host "  [OK] $Msg" -ForegroundColor Green }
function Write-Do      { param([string]$Msg) Write-Host "  [do] $Msg" -ForegroundColor Yellow }
function Fail          { param([string]$Msg) Write-Host "ERROR: $Msg" -ForegroundColor Red; exit 1 }

# Resolve paths
$ScriptDir = $PSScriptRoot
if (-not $RepoRoot)  { $RepoRoot  = Resolve-Path (Join-Path $ScriptDir '..\..') }
if (-not $OutputDir) { $OutputDir = Join-Path $RepoRoot '.local-build\iis' }

$AppRoot      = Join-Path $RepoRoot 'RPA-POC-AVA-app'
$FrontendSrc  = Join-Path $AppRoot 'frontend'
$BackendSrc   = Join-Path $AppRoot 'backend'

# Preflight
Write-Section 'Preflight'
foreach ($p in @($FrontendSrc, $BackendSrc)) {
    if (-not (Test-Path $p)) { Fail "Source path missing: $p" }
}
foreach ($cmd in @('node', 'npm', 'python')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Fail "'$cmd' not on PATH. Run Install-Prereqs.ps1 first."
    }
}
Write-OK "RepoRoot:  $RepoRoot"
Write-OK "OutputDir: $OutputDir"
Write-OK "node $((node -v))"
Write-OK "npm  $((npm -v))"
Write-OK "python $((python -V) 2>&1)"

# Fresh output dir
Write-Section 'Resetting output directory'
if (Test-Path $OutputDir) {
    Write-Do "Removing $OutputDir"
    Remove-Item -Path $OutputDir -Recurse -Force
}
$FrontendOut  = Join-Path $OutputDir 'frontend'
$BackendOut   = Join-Path $OutputDir 'backend'
$WheelhouseOut = Join-Path $OutputDir 'wheelhouse'
New-Item -ItemType Directory -Path $FrontendOut, $BackendOut, $WheelhouseOut -Force | Out-Null
Write-OK 'Clean'

# Frontend: npm ci + next build + assemble standalone payload
if ($SkipNpm) {
    Write-Section 'Frontend (SKIPPED)'
} else {
    Write-Section 'Frontend: npm ci'
    Push-Location $FrontendSrc
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { Fail "npm ci failed (exit $LASTEXITCODE)" }
        Write-OK 'npm ci'

        Write-Section 'Frontend: next build'
        & npm run build
        if ($LASTEXITCODE -ne 0) { Fail "next build failed (exit $LASTEXITCODE)" }
        Write-OK 'next build'
    } finally {
        Pop-Location
    }

    Write-Section 'Frontend: assemble standalone payload'
    # Next.js standalone output sits in .next/standalone; .next/static and
    # public/ have to be merged in manually (per Vercel docs).
    Copy-Item -Path (Join-Path $FrontendSrc '.next\standalone\*') -Destination $FrontendOut -Recurse -Force
    New-Item -ItemType Directory -Path (Join-Path $FrontendOut '.next\static') -Force | Out-Null
    Copy-Item -Path (Join-Path $FrontendSrc '.next\static\*') `
              -Destination (Join-Path $FrontendOut '.next\static') -Recurse -Force
    $publicSrc = Join-Path $FrontendSrc 'public'
    if (Test-Path $publicSrc) {
        New-Item -ItemType Directory -Path (Join-Path $FrontendOut 'public') -Force | Out-Null
        Copy-Item -Path "$publicSrc\*" -Destination (Join-Path $FrontendOut 'public') -Recurse -Force
    }
    if (-not (Test-Path (Join-Path $FrontendOut 'server.js'))) {
        Fail "Frontend payload missing server.js after assembly. Is `output:'standalone'` set in next.config.js?"
    }
    Write-OK "Assembled at $FrontendOut"
}

# Backend: copy source (excluding dev junk), then pip download
Write-Section 'Backend: copy source'
$exclude = @('venv', '.venv', '__pycache__', 'uploads', 'data', 'database', '.pytest_cache')
Get-ChildItem $BackendSrc -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $BackendOut -Recurse -Force
}
if (-not (Test-Path (Join-Path $BackendOut 'app.py'))) { Fail "Backend payload missing app.py" }
Write-OK "Copied to $BackendOut"

if ($SkipWheels) {
    Write-Section 'Wheelhouse (SKIPPED)'
} else {
    Write-Section 'Wheelhouse: pip download'
    $reqFile = Join-Path $BackendOut 'requirements.txt'

    # Bootstrap wheels (pip / setuptools / wheel) so the offline install on
    # the target IIS box can upgrade them.
    Write-Do 'pip download pip setuptools wheel'
    & python -m pip download --dest $WheelhouseOut pip setuptools wheel
    if ($LASTEXITCODE -ne 0) { Fail "pip download (bootstrap) failed" }

    # App wheels + waitress. Pinning platform/python-version ensures only
    # win_amd64 wheels matching the target runtime are pulled.
    $pyver = ((& python -V) -replace 'Python ', '').Split('.')[0..1] -join '.'
    Write-Do "pip download -r requirements.txt waitress (platform=win_amd64, python=$pyver)"
    & python -m pip download `
        --dest $WheelhouseOut `
        --platform win_amd64 `
        --python-version $pyver `
        --only-binary=:all: `
        --implementation cp `
        -r $reqFile `
        waitress==3.0.0
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "Hint: a package may lack a win_amd64 wheel for Python $pyver." -ForegroundColor Yellow
        Write-Host "      Try dropping '--only-binary=:all:' to allow sdists (slower, needs a C toolchain on the target)." -ForegroundColor Yellow
        Fail "pip download failed"
    }
    $wheelCount = (Get-ChildItem $WheelhouseOut -File).Count
    Write-OK "$wheelCount files in wheelhouse"
}

# Pipeline files (templates + orchestrator + diagnostic)
Write-Section 'Bundling Web.config templates + scripts'
Copy-Item -Path (Join-Path $ScriptDir 'web.config.frontend.tpl') -Destination $OutputDir -Force
Copy-Item -Path (Join-Path $ScriptDir 'web.config.backend.tpl')  -Destination $OutputDir -Force
Copy-Item -Path (Join-Path $ScriptDir 'deploy-prod.ps1')         -Destination $OutputDir -Force
$diagnose = Join-Path $ScriptDir 'Diagnose.ps1'
if (Test-Path $diagnose) {
    Copy-Item -Path $diagnose -Destination $OutputDir -Force
}

# Carry over local.env if present so deploy-prod.ps1 finds it next to itself.
# This is a LOCAL build only -- the file is gitignored, the .local-build/ dir
# is gitignored, and Octopus uses its own variable substitution (no local.env).
$localEnv = Join-Path $ScriptDir 'local.env'
if (Test-Path $localEnv) {
    Copy-Item -Path $localEnv -Destination $OutputDir -Force
    Write-OK "local.env carried over from $ScriptDir"
} else {
    Write-Host "  [warn] No local.env at $ScriptDir -- deploy-prod.ps1 will fail preflight unless you set env vars or pass -EnvFile." -ForegroundColor Yellow
}

Write-OK 'Done'

# Sanity: deploy-prod.ps1 must be pure ASCII. PowerShell 5.1 reads files
# without a BOM as Windows-1252 by default, so UTF-8 multibyte chars (em-dash,
# smart quotes, etc.) turn into mojibake and break the parser. Catch it here.
$bytes = [IO.File]::ReadAllBytes((Join-Path $OutputDir 'deploy-prod.ps1'))
$nonAscii = $bytes | Where-Object { $_ -gt 127 }
if ($nonAscii) {
    Fail "deploy-prod.ps1 contains non-ASCII bytes -- will fail to parse under Windows PowerShell 5.1. Strip smart quotes / em-dashes from the source."
}

# Sanity: Web.config templates must be well-formed XML. The XML spec forbids
# the sequence of two consecutive hyphens (--) anywhere inside <!-- ... -->,
# which is easy to violate accidentally (e.g., pasting a shell flag like
# --listen into a comment). IIS rejects the whole file with HTTP 500.19.
foreach ($tpl in @('web.config.frontend.tpl', 'web.config.backend.tpl')) {
    $path = Join-Path $OutputDir $tpl
    try {
        [xml](Get-Content -Raw $path) | Out-Null
    } catch {
        Fail "$tpl is not well-formed XML: $($_.Exception.Message)"
    }
    # Belt-and-suspenders: explicitly check for `--` inside any XML comment.
    $raw = Get-Content -Raw $path
    foreach ($m in [regex]::Matches($raw, '<!--([\s\S]*?)-->')) {
        if ($m.Groups[1].Value -match '--') {
            $lineNo = ($raw.Substring(0, $m.Index) -split "`n").Count
            Fail "$tpl line ${lineNo}: XML comment contains forbidden '--' sequence. IIS will reject this with HTTP 500.19."
        }
    }
}

# build-info.json so we can tell what's deployed at runtime
$buildInfo = [ordered]@{
    appName     = 'HRSA-RPA-POC'
    buildId     = 'local'
    buildNumber = (Get-Date -Format 'yyyyMMdd.HHmmss')
    sourceBranch = (& git -C $RepoRoot rev-parse --abbrev-ref HEAD 2>$null)
    sourceCommit = (& git -C $RepoRoot rev-parse HEAD 2>$null)
    builtBy     = "$env:USERDOMAIN\$env:USERNAME"
    builtOn     = $env:COMPUTERNAME
    builtAtUtc  = (Get-Date).ToUniversalTime().ToString('o')
}
$buildInfo | ConvertTo-Json | Set-Content -Path (Join-Path $OutputDir 'build-info.json') -Encoding UTF8

Write-Section 'Done'
Write-Host "Package ready: $OutputDir" -ForegroundColor Green
Write-Host ""
Write-Host "Next:" -ForegroundColor Green
Write-Host "  1. Make sure deploy/iis/local.env is filled in (or set env vars)" -ForegroundColor Green
Write-Host "  2. From an elevated PowerShell:" -ForegroundColor Green
Write-Host "       cd '$OutputDir'" -ForegroundColor Green
Write-Host "       .\deploy-prod.ps1" -ForegroundColor Green
exit 0
