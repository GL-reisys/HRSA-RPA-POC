# Octopus runbook — HRSA-RPA-POC IIS deployment

This documents the Octopus side of the IIS deployment. Pair it with the
templates and scripts in this folder.

## Project setup (one-time)

### 1. External feed

Add the Azure DevOps build artifact feed (or the Octopus built-in feed if you
push from ADO via `OctopusPush`). The package id is `HRSA-RPA-POC-iis`.

### 2. Lifecycle

The pipeline does not depend on a specific lifecycle. A typical shape:

```
Dev  →  Test  →  Stage  →  Prod-Gov
```

Each environment maps to one IIS server (or set of servers) deployed in
parallel by the Octopus role tagged below.

### 3. Deployment target

Tag the IIS server target with the role `hrsa-rpa-iis`. The deployment
process step (below) is scoped to that role.

The Tentacle service account must be local Administrator on the target —
`deploy-prod.ps1` provisions IIS sites and app pools, which require admin.

### 4. Variables

| Name | Scope | Sensitive | Example | Notes |
|---|---|---|---|---|
| `SiteHostname` | per env | no | `rpa-poc.example.gov` | Public host header for the frontend site. |
| `CertThumbprint` | per env | no | `A1B2C3D4...` | Thumbprint of an HTTPS cert already imported into `LocalMachine\My` on the target. |
| `DeployRoot` | global | no | `C:\inetpub\HRSA-RPA-POC` | Physical path for the deployment. |
| `BackendPort` | global | no | `5000` | Loopback port the backend site binds to. Frontend ARR rules proxy here. |
| `AzureOpenAiEndpoint` | per env | no | `https://...openai.azure.us/` | |
| `AzureOpenAiApiKey` | per env | **yes** | `<secret>` | Stored as Octopus sensitive variable. |
| `AzureOpenAiDeployment` | per env | no | `gpt-4` | |
| `DatabaseUrl` | per env | yes | `postgresql://...` | Optional. Leave blank if backend runs without DB. |
| `KeepDefaultSite` | per env | no | `0` (default) | Optional. Set to `1` only on shared servers where the IIS Default Web Site is genuinely in use. Default behavior stops it so it cannot intercept `http://<host>/` requests with the IIS welcome page. |

Octopus substitutes these into `web.config.frontend.tpl`, `web.config.backend.tpl`,
and `deploy-prod.ps1` before any of them lands on the target.

## Deployment process steps

### Step 1 — Deploy a package (built-in)

| Field | Value |
|---|---|
| Step type | Deploy a package |
| Package feed | (the feed configured above) |
| Package ID | `HRSA-RPA-POC-iis` |
| On targets in role | `hrsa-rpa-iis` |
| Custom installation directory | `#{PackageRoot}` (e.g., `C:\Octopus\Stage\HRSA-RPA-POC`) |
| Feature: substitute variables in files | **enabled** |
| Files to substitute | `web.config.frontend.tpl`<br>`web.config.backend.tpl`<br>`deploy-prod.ps1` |

This step:
1. Pulls the latest `HRSA-RPA-POC-iis-<build>.zip` from the feed.
2. Unzips it into `#{PackageRoot}`.
3. Runs Octopus' variable substitution on the three files listed —
   replacing every `#{...}` with the matching variable value.

Add an Octopus variable named `PackageRoot` (global) so the next step can
locate the unzipped package:

```
PackageRoot = #{Octopus.Action[Deploy a package].Output.Package.InstallationDirectoryPath}
```

### Step 2 — Run deploy-prod.ps1

| Field | Value |
|---|---|
| Step type | Run a script |
| On targets in role | `hrsa-rpa-iis` |
| Script source | Script file inside a package |
| Package | `HRSA-RPA-POC-iis` (the same package) |
| Script file path | `deploy-prod.ps1` |
| Run as user | (default — Tentacle service identity, which must be admin) |

The script reads its inputs from the `#{...}` tokens that Octopus already
substituted into it. No arguments needed.

Branch on exit code in the Octopus runbook:

| Exit | Action |
|---|---|
| 0 | Pass the release. |
| 1 | Fail loudly — config error. |
| 2 | Auto-rolled back. Investigate logs at `<DEPLOY_ROOT>.previous` and the package staging directory. |
| 3 | Sites running but unhealthy. Alert on-call; manual rollback via `Rename-Item` of `.previous` snapshot. |

### Step 3 (optional) — Smoke test

```powershell
$ErrorActionPreference = 'Stop'
$resp = Invoke-WebRequest -UseBasicParsing -Uri "https://#{SiteHostname}/api/health" -TimeoutSec 10
if ($resp.StatusCode -ne 200) { throw "smoke test failed: $($resp.StatusCode)" }
Write-Host "Smoke test passed."
```

Same role + same package — no need to ship the script separately.

## Target machine prereqs

Run **once** per target server, as Administrator:

```powershell
.\Install-Prereqs.ps1
```

This installs IIS, URL Rewrite, ARR (with proxy enabled), HttpPlatformHandler,
Python 3.12, and Node 20 LTS. Idempotent.

For air-gapped Gov targets, pre-stage installers and pass `-OfflineInstallerDir`:

```powershell
.\Install-Prereqs.ps1 -OfflineInstallerDir 'C:\stage\installers'
```

Expected filenames in that directory:
- `rewrite_amd64_en-US.msi`
- `requestRouter_amd64.msi`
- `HttpPlatformHandler_amd64.msi` (case-insensitive — `httpPlatformHandler_*` also matches)
- `python-3.12.*-amd64.exe`
- `node-v20.*-x64.msi`

Additionally, import the TLS cert into `LocalMachine\My` and note its
thumbprint — Octopus needs it in the `CertThumbprint` variable.

## Rollback

`deploy-prod.ps1` keeps the previous deployment at `<DEPLOY_ROOT>.previous`.
On exit code 2, rollback is already done — sites are back on the previous
version.

For manual rollback after the fact (e.g., a bad deploy that returned exit 0
but turned out broken):

```powershell
Import-Module WebAdministration
Stop-Website 'HRSA-RPA-POC-Frontend'
Stop-Website 'HRSA-RPA-POC-Backend'
Stop-WebAppPool 'HRSA-RPA-POC-Frontend'
Stop-WebAppPool 'HRSA-RPA-POC-Backend'

$root = 'C:\inetpub\HRSA-RPA-POC'
Rename-Item -Path $root             -NewName 'HRSA-RPA-POC.broken'
Rename-Item -Path "$root.previous"  -NewName 'HRSA-RPA-POC'

Start-WebAppPool 'HRSA-RPA-POC-Backend'
Start-WebAppPool 'HRSA-RPA-POC-Frontend'
Start-Website   'HRSA-RPA-POC-Backend'
Start-Website   'HRSA-RPA-POC-Frontend'
```

Only one previous snapshot is retained — two deploys after a bad one and you
lose the ability to roll back this way.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `502.5 - ANCM Out-Of-Process Startup Failure` | Wrong `processPath` in Web.config — Octopus token wasn't substituted, or Node/Python isn't on PATH. Check `<DEPLOY_ROOT>\frontend\Web.config` for any leftover `#{...}`. |
| `500.19` on first request | Web.config malformed. URL Rewrite or ARR not installed. Re-run `Install-Prereqs.ps1`. |
| Browser hits `/api/foo` and gets 404 from Next.js | URL Rewrite rule didn't fire. ARR proxy not enabled at server level. Run `appcmd list config -section:system.webServer/proxy` — should show `enabled:true`. |
| Backend logs `ImportError: ...` after deploy | Wheelhouse missing a wheel (likely a non-binary package). On the ADO build agent, drop `--only-binary=:all:` from the pip download step OR add `--prefer-binary` to the deploy-time install. |
| Backend logs `OSError: [WinError 10013]` | Two processes fighting for the same port. Either another backend instance didn't shut down (check `tasklist /fi "imagename eq python.exe"`) or the IIS site is misconfigured. Restart the backend app pool. |
| Health check times out, sites running | App started but `/health` not reachable. Check the loopback binding (`Get-WebBinding -Name HRSA-RPA-POC-Backend`) and that nothing else is listening on `#{BackendPort}`. |
| Cert binding fails (`A specified logon session does not exist`) | The cert was imported without "mark private key exportable" or the pool identity lacks read access to the private key. Use `winhttpcertcfg` or the IIS Manager cert dialog to grant access. |

## Related files

- [README.md](README.md) — topology and design rationale
- [Install-Prereqs.ps1](Install-Prereqs.ps1) — server bootstrap
- [deploy-prod.ps1](deploy-prod.ps1) — what this runbook runs
- [web.config.frontend.tpl](web.config.frontend.tpl) — token-substituted before deploy
- [web.config.backend.tpl](web.config.backend.tpl) — ditto
- [azure-pipelines.yml](azure-pipelines.yml) — the ADO build that feeds this Octopus project
- [../azure/bicep/DEPLOYMENT_TEST_LOG.md](../azure/bicep/DEPLOYMENT_TEST_LOG.md) — the parallel Container Apps target's test log (different runtime, same pipeline contract)
