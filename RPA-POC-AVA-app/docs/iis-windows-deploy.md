# Deploying AVA to Windows / IIS

This guide describes how to host the AVA application on a Windows Server using
**IIS as a TLS-terminating reverse proxy** in front of the Python (Flask) backend
and the Next.js frontend, both running as Windows services on `localhost`.

> AVA is built as two containers (see [../backend/Dockerfile](../backend/Dockerfile)
> and [../frontend/Dockerfile](../frontend/Dockerfile)). IIS has no native Python
> or Node runtime, so the application itself runs as standalone processes and
> IIS only proxies to them.

## Topology

```
Browser ──HTTPS──> IIS (ava.example.com:443)
                    │
                    ├── /api/*   ──reverse proxy──> http://127.0.0.1:5000  (Python / waitress)
                    └── /*       ──reverse proxy──> http://127.0.0.1:3000  (next start)
```

| Tier      | Process               | Port  | Service name (NSSM) |
| --------- | --------------------- | ----- | ------------------- |
| Backend   | `waitress-serve app:app` | 5000  | `AvaBackend`        |
| Frontend  | `next start -p 3000`  | 3000  | `AvaFrontend`       |
| Edge      | IIS site `AVA`        | 443   | (IIS)               |

## Prerequisites (one-time, on the Windows host)

1. Install IIS with these role features:
   `Web-Server`, `Web-Http-Redirect`, `Web-WebSockets`, `Web-Static-Content`.
2. Install [URL Rewrite 2.1](https://www.iis.net/downloads/microsoft/url-rewrite).
3. Install [Application Request Routing 3.0](https://www.iis.net/downloads/microsoft/application-request-routing).
4. In **IIS Manager → server node → Application Request Routing Cache →
   Server Proxy Settings** check **Enable proxy**.
   *Without this toggle the rewrite rules silently 404.*
5. Install **Python 3.11+** and **Node 20+**.
6. Install **NSSM** (`choco install nssm`) to run Python and Node as services.
7. Allow the forwarded-host server variables (once, at server scope):
   **IIS Manager → server node → Configuration Editor →
   `system.webServer/rewrite/allowedServerVariables`** → add
   `HTTP_X_FORWARDED_PROTO`, `HTTP_X_FORWARDED_HOST`, `HTTP_X_FORWARDED_FOR`.

## Run the backend as a Windows service

`gunicorn` does not run on Windows; use **waitress** instead.

In `RPA-POC-AVA-app\backend`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt waitress
```

Register the service:

```powershell
nssm install AvaBackend "C:\path\to\backend\.venv\Scripts\waitress-serve.exe" `
  "--listen=127.0.0.1:5000" "--threads=8" "app:app"
nssm set AvaBackend AppDirectory "C:\path\to\backend"
nssm set AvaBackend AppEnvironmentExtra `
  "PORT=5000" "FLASK_ENV=production" "ALLOWED_ORIGINS=https://ava.example.com"
nssm start AvaBackend
```

## Run the frontend as a Windows service

In `RPA-POC-AVA-app\frontend`:

```powershell
npm ci
npm run build
nssm install AvaFrontend "C:\Program Files\nodejs\node.exe" `
  "node_modules\next\dist\bin\next" "start" "-p" "3000"
nssm set AvaFrontend AppDirectory "C:\path\to\frontend"
nssm set AvaFrontend AppEnvironmentExtra `
  "NODE_ENV=production" "NEXT_PUBLIC_API_BASE=/api"
nssm start AvaFrontend
```

The frontend must call the API via a **relative path** (`/api/...`), not
`http://localhost:5000`, so both tiers share one origin and CORS is not needed.

## IIS site `web.config`

Create an IIS site `AVA`, bound to `https://ava.example.com`, whose physical
path is an empty folder containing only this `web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>

    <rewrite>
      <rules>
        <!-- 1. API traffic goes to Flask/waitress on :5000 -->
        <rule name="ProxyAPI" stopProcessing="true">
          <match url="^api/(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:5000/api/{R:1}" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST"  value="{HTTP_HOST}" />
            <set name="HTTP_X_FORWARDED_FOR"   value="{REMOTE_ADDR}" />
          </serverVariables>
        </rule>

        <!-- 2. Next.js static chunks (optional explicit rule) -->
        <rule name="ProxyNextStatic" stopProcessing="true">
          <match url="^(_next/.*|favicon\.ico|.*\.(?:js|css|map|png|jpg|svg|woff2?))$" />
          <action type="Rewrite" url="http://127.0.0.1:3000/{R:0}" />
        </rule>

        <!-- 3. Everything else -> Next.js SSR -->
        <rule name="ProxyApp" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:3000/{R:1}" />
          <serverVariables>
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST"  value="{HTTP_HOST}" />
          </serverVariables>
        </rule>
      </rules>

      <outboundRules>
        <preConditions>
          <preCondition name="IsRedirect">
            <add input="{RESPONSE_STATUS}" pattern="3\d\d" />
          </preCondition>
        </preConditions>
      </outboundRules>
    </rewrite>

    <!-- Upload size: bump if your PDF flow exceeds 100 MB -->
    <security>
      <requestFiltering>
        <requestLimits maxAllowedContentLength="104857600" />
      </requestFiltering>
    </security>

    <!-- Long-running PDF validation; raise proxy timeout -->
    <proxy enabled="true"
           preserveHostHeader="true"
           reverseRewriteHostInResponseHeaders="true"
           timeout="00:05:00" />

    <httpProtocol>
      <customHeaders>
        <add name="X-Content-Type-Options" value="nosniff" />
        <add name="X-Frame-Options" value="SAMEORIGIN" />
      </customHeaders>
    </httpProtocol>

  </system.webServer>
</configuration>
```

Notes:

- `<proxy …>` is read by ARR for the per-site timeout. Raise it above the
  default 30 s because some PDF validation calls take longer.
- The `ProxyNextStatic` rule is not strictly required (rule 3 catches it), but
  separating it makes access logs easier to read and lets you add caching
  headers for `_next/*` later.

## File / folder permissions

The IIS AppPool identity only proxies, so its permissions don't matter much.
The **NSSM service accounts** running Python and Node must have read/write on:

- `RPA-POC-AVA-app\backend\data\sessions.json`
- `RPA-POC-AVA-app\backend\uploads\`
- whatever path `config.runtime.resolve_app_path()` returns for logs.

## Sanity test order

1. `curl http://127.0.0.1:5000/api/health` from the box → backend works.
2. `curl http://127.0.0.1:3000/` from the box → frontend works.
3. `curl -k https://ava.example.com/api/health` → proves rule 1.
4. Browse `https://ava.example.com/` → proves rule 3 and React hydration.

| Symptom                                    | Likely cause                                          |
| ------------------------------------------ | ----------------------------------------------------- |
| `404.0 IIS Web Core` on step 3             | ARR *Enable proxy* toggle is off (prerequisite #4).   |
| `502.3` from IIS                           | Upstream Windows service not running — `nssm status`. |
| Rule fails to load on site start           | Server variables not whitelisted (prerequisite #7).   |
| API works, frontend assets 404             | Frontend service is down or built without `npm run build`. |

## When *not* to use IIS

If the target environment allows containers, prefer the existing Docker-based
deploy paths instead — they already solve process management, TLS, logging,
and rolling updates:

- [azure-containerapp-deploy.md](azure-containerapp-deploy.md)
- [azure-aci-deployment.md](azure-aci-deployment.md)
- [azure-aci-local-deploy.md](azure-aci-local-deploy.md)

Use IIS only when the deployment target is a Windows Server VM with no
container runtime available.
