# IIS deployment — HRSA-RPA-POC

Windows / IIS deployment path for the HRSA-RPA AVA stack. Sits alongside the
Azure Container Apps Bicep stack ([deploy/azure/bicep](../azure/bicep/README.md))
and follows the same Octopus contract (`#{token}` substitution before invocation,
`deploy-prod.ps1` as the single entry point).

## Topology

One externally-facing IIS site, one loopback-only IIS site for the backend,
two app pools. No external CORS surface — frontend and API are same-origin.

```
                  ┌──────────────────────────────────────────┐
   Browser  ─────►│  IIS site: HRSA-RPA-POC-Frontend         │
   (HTTPS)        │  binding *:443 (HTTPS, cert from store)  │
                  │  App pool: HRSA-RPA-POC-Frontend (NoMC)  │
                  │                                          │
                  │  ┌────────────────────────────────────┐  │
                  │  │ HttpPlatformHandler                │  │
                  │  │   node .\server.js                 │  │
                  │  │   PORT=%HTTP_PLATFORM_PORT%        │  │
                  │  │   HOSTNAME=127.0.0.1               │  │
                  │  └────────────────────────────────────┘  │
                  │                                          │
                  │  URL Rewrite (runs before handlers):     │
                  │   /api/*   ──► http://127.0.0.1:5000/api/* │
                  │   /static/* ──► http://127.0.0.1:5000/static/* │
                  └──────────────────┬───────────────────────┘
                                     │ ARR proxy (loopback)
                                     ▼
                  ┌──────────────────────────────────────────┐
                  │  IIS site: HRSA-RPA-POC-Backend          │
                  │  binding 127.0.0.1:5000 (HTTP only)      │
                  │  App pool: HRSA-RPA-POC-Backend (NoMC)   │
                  │                                          │
                  │  ┌────────────────────────────────────┐  │
                  │  │ HttpPlatformHandler                │  │
                  │  │   python -m waitress               │  │
                  │  │     --listen=127.0.0.1:%PORT%      │  │
                  │  │     app:app                        │  │
                  │  │   AZURE_OPENAI_API_KEY=#{...}      │  │
                  │  │   AZURE_OPENAI_ENDPOINT=#{...}     │  │
                  │  └────────────────────────────────────┘  │
                  └──────────────────────────────────────────┘
```

Key properties:
- **Same-origin.** Browser hits `/api/*` relative — no CORS, no preflight, no cross-site cookies. The Next.js `next.config.js` rewrites are bypassed in prod (URL Rewrite picks them off before Node sees them); they remain for `npm run dev`.
- **Backend not externally reachable.** Bound to `127.0.0.1` only. Even if firewall rules slip, port 5000 isn't exposed.
- **Two app pools** so frontend and backend recycle independently. Both `NoManagedCode` — neither hosts .NET.
- **Secrets in `<environmentVariables>` in Web.config**, populated by Octopus token substitution before the file lands on disk.

## Layout

```
deploy/iis/
├── README.md                   ← this file
├── ARCHITECTURE.md             ← topology + request flow + reachability matrix
├── Install-Prereqs.ps1         ← one-shot server bootstrap (idempotent)
├── Setup-DevCert.ps1           ← dev-only self-signed cert + hosts entry
├── build-local.ps1             ← assemble a deploy package from source (local equivalent of ADO build)
├── deploy-prod.ps1             ← Octopus entry point
├── Diagnose.ps1                ← read-only health/config check
├── web.config.frontend.tpl     ← Next.js site Web.config template
├── web.config.backend.tpl      ← Flask site Web.config template
├── azure-pipelines.yml         ← ADO build stage → publishes deploy package
├── octopus-runbook.md          ← Octopus project setup + variables
└── local.env.example           ← env-var template for local / manual runs
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full topology diagram, request
flow sequence diagrams, disk layout, and reachability matrix.

## The pipeline contract

Mirrors the Container Apps flow from [DEPLOYMENT_TEST_LOG.md](../azure/bicep/DEPLOYMENT_TEST_LOG.md),
swapping ACR/Bicep for an IIS package:

```
Azure DevOps  ─►  npm ci + next build (standalone) + pip download (wheelhouse)
Azure DevOps  ─►  zip into HRSA-RPA-POC-iis-<version>.zip
Azure DevOps  ─►  publish artifact (Octopus picks it up)
   Octopus    ─►  push package to target IIS server (WinRM / Tentacle)
   Octopus    ─►  substitute #{...} variables in Web.config templates + deploy-prod.ps1
   Octopus    ─►  run deploy-prod.ps1 (preflight, swap, health check)
```

## Exit codes (same convention as the Bicep path)

| Code | Meaning |
|---|---|
| 0 | Deploy succeeded, both sites healthy. |
| 1 | Preflight failure — nothing was changed. |
| 2 | Artifact swap failed — automatic rollback to previous version completed. |
| 3 | Deploy succeeded but post-deploy health check did not pass within the timeout. Manual intervention required. |

## Local / manual test

End-to-end local recipe (all from an **elevated** PowerShell):

```powershell
cd deploy\iis

# 1. One-time: install IIS + URL Rewrite + ARR + HPH + Python + Node.
.\Install-Prereqs.ps1

# 2. Dev-only: self-signed cert + hosts entry, written straight into local.env.
.\Setup-DevCert.ps1 -Hostname rpa-poc.local -UpdateLocalEnv

# 3. Fill in the remaining secrets (Azure OpenAI key etc.):
notepad .\local.env

# 4. Build the deploy package from source (same shape ADO produces).
.\build-local.ps1
# -> writes <repo>\.local-build\iis\{frontend, backend, wheelhouse, ...}

# 5. Deploy. deploy-prod.ps1 auto-loads local.env from this folder.
cd ..\..\.local-build\iis
.\deploy-prod.ps1
```

When it finishes, browse to `https://rpa-poc.local/` — same-origin, browser
gets a healthy cert (because step 2 trusted it), `/api/*` proxies to the
loopback backend.

Octopus runs do **not** need any of `Setup-DevCert.ps1`, `build-local.ps1`,
or `local.env` — Octopus runs the ADO-built package, substitutes `#{...}`
tokens directly into the script, and supplies env vars from its project
variable set. The dev helpers exist only so you can smoke-test the pipeline
on your machine before pushing.

### What's required vs. what's just convenient

| Script | When | Required? |
|---|---|---|
| `Install-Prereqs.ps1` | Once per machine | Yes — without it, deploy preflight fails. |
| `Setup-DevCert.ps1` | Once per dev machine | Dev only. Prod uses a real CA-issued cert imported by hand. |
| `build-local.ps1` | Every time backend or frontend source changes | Dev only. ADO does the equivalent in CI. |
| `deploy-prod.ps1` | Every deploy | Yes — same script Octopus invokes. |

## Required server prereqs (Install-Prereqs.ps1 handles all of this)

| Component | Why |
|---|---|
| IIS + ASP.NET role + Management Service | Base web server. |
| URL Rewrite 2.1 | Pattern-matches `/api/*` and `/static/*`. |
| Application Request Routing 3.0 | Performs the actual proxy hop. Must have `proxy enabled` toggled on. |
| HttpPlatformHandler 1.2 | Launches Node and Python as managed worker processes. |
| Python 3.12 (machine-wide) | Backend runtime. |
| Node 20 LTS (machine-wide) | Frontend runtime (`.next/standalone/server.js`). |

## Cross-references

- Sister deploy: [deploy/azure/bicep](../azure/bicep/README.md) (Container Apps / Linux path)
- Octopus contract docs: [octopus-runbook.md](octopus-runbook.md)
- Pre-deploy analysis that led to this design: [DEPLOYMENT_TEST_LOG.md](../azure/bicep/DEPLOYMENT_TEST_LOG.md) (Azure side — IIS is a parallel target, not a replacement)
