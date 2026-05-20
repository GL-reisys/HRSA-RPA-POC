# Azure Container Apps Deployment

This guide deploys the HRSA RPA-POC app (frontend + backend) to **Azure Container Apps** using **ACR Tasks** for cloud-side image builds. No local Docker is required.

> Use this path when `Microsoft.ContainerInstance` is **not** registered in your subscription (the typical blocker for the ACI path documented in [`azure-aci-local-deploy.md`](./azure-aci-local-deploy.md)). It is also a strict upgrade for production-style workloads — managed scaling, internal service-to-service ingress, no public-IP awkwardness.

---

## Topology

```
                  Internet (HTTPS)
                         │
                         ▼
   ┌─────────────────────────────────────────────────┐
   │ Container Apps Environment                      │
   │ cae-eus-dgps-ehbs-rpa-sbx                       │
   │                                                 │
   │ ┌──────────────────┐    ┌──────────────────┐    │
   │ │ Frontend (ext.)  │ ─▶ │ Backend (int.)   │    │
   │ │ Next.js, :3000   │    │ Flask, :5000     │    │
   │ │ ca-eus-dgps-     │    │ ca-eus-dgps-     │    │
   │ │  ehbs-rpa-fe-sbx │    │  ehbs-rpa-be-sbx │    │
   │ └──────────────────┘    └──────────────────┘    │
   │                                  │              │
   └──────────────────────────────────┼──────────────┘
                                      │
                                      ▼
                         ┌───────────────────────────┐
                         │ Azure OpenAI (in-RG)      │
                         │ oai-eus-dgps-ehbs-rpa-sbx │
                         │ deployment: gpt-4-1-mini  │
                         └───────────────────────────┘
```

- Frontend → backend uses the env-internal DNS: `http://ca-eus-dgps-ehbs-rpa-be-sbx`
- The internal hostname is **baked into the frontend image at build time** because `next.config.js` uses `API_INTERNAL_URL` in its rewrite map. Changing the backend app name ⇒ rebuild frontend image.

---

## Prerequisites

| Tool | Notes |
| --- | --- |
| Azure CLI (`az`) | logged in to the target tenant/subscription |
| `containerapp` extension | auto-installed by the deploy script if missing |
| Bash | macOS / Linux / WSL |

You do **not** need Docker installed.

**Azure permissions:** Contributor on the target resource group is sufficient. The Container Apps Environment uses an existing Log Analytics workspace in the same RG (no extra RBAC).

---

## 1. Authenticate

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
az account show
```

## 2. Verify resource provider state

Container Apps requires `Microsoft.App` registered. ACR build requires `Microsoft.ContainerRegistry`. Both are usually already registered in modern subscriptions, but worth checking:

```bash
az provider show --namespace Microsoft.App --query registrationState -o tsv
az provider show --namespace Microsoft.ContainerRegistry --query registrationState -o tsv
```

If either says `NotRegistered` and you have subscription-level rights:
```bash
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.ContainerRegistry
```

If you don't have rights, ask a subscription Owner to register them.

## 3. Discover existing resources to reuse / match conventions

```bash
RG=<your-resource-group>

az group show --name "$RG" --query "{location:location,tags:tags}" -o json
az resource list --resource-group "$RG" --query "[].{name:name,type:type}" -o table
az monitor log-analytics workspace list --resource-group "$RG" -o table
az acr list --query "[].{name:name,loginServer:loginServer,rg:resourceGroup,adminEnabled:adminUserEnabled}" -o table
az cognitiveservices account list --resource-group "$RG" -o table
```

Pick names that match the RG's CAF convention (e.g. `*-eus-dgps-ehbs-*-sbx`). Sample values used for HRSA RPA-POC:

| Resource | Name | Constraint |
| --- | --- | --- |
| ACR | `creusdgpsehbsrpasbx` | alphanumeric, 5–50 chars, globally unique |
| Container Apps env | `cae-eus-dgps-ehbs-rpa-sbx` | ≤ 32 chars |
| Backend app | `ca-eus-dgps-ehbs-rpa-be-sbx` | ≤ 32 chars |
| Frontend app | `ca-eus-dgps-ehbs-rpa-fe-sbx` | ≤ 32 chars |
| Azure OpenAI account | `oai-eus-dgps-ehbs-rpa-sbx` | 2–64 chars, must be globally unique (becomes a subdomain) |

## 4. One-time infrastructure setup

If these don't already exist in your RG:

### 4a. Azure Container Registry

```bash
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic \
  --location "$LOCATION" \
  --admin-enabled true \
  --tags CostCenter=<...> Owner=<...> Project=<...> app=hrsa-rpa-ava
```

`--admin-enabled true` is required because the deploy script passes ACR credentials to Container Apps. (Production: switch to managed-identity-based pulls.)

### 4b. Azure OpenAI account + model deployment (optional but recommended)

```bash
az cognitiveservices account create \
  --name "$OAI_ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --kind OpenAI \
  --sku S0 \
  --custom-domain "$OAI_ACCOUNT" \
  --yes \
  --tags CostCenter=<...> Owner=<...> Project=<...>

az cognitiveservices account deployment create \
  --resource-group "$RG" \
  --name "$OAI_ACCOUNT" \
  --deployment-name gpt-4-1-mini \
  --model-name gpt-4.1-mini \
  --model-version "2025-04-14" \
  --model-format OpenAI \
  --sku-name Standard \
  --sku-capacity 10
```

> ⚠️ **Model versions get deprecated.** As of mid-2026, `gpt-4o-mini:2024-07-18` is deprecated even though the model registry still labels it `GenerallyAvailable`. Verify the current GA version with:
> ```bash
> az cognitiveservices model list --location "$LOCATION" --query "[?model.format=='OpenAI' && contains(model.name,'mini')].{name:model.name,version:model.version,status:model.lifecycleStatus}" -o table
> ```

## 5. Configure `scripts/azure/local.env`

```bash
cp scripts/azure/local.env.example scripts/azure/local.env
```

Fill in (Container Apps section):

```bash
AZURE_SUBSCRIPTION_ID=<sub-id>
AZURE_RESOURCE_GROUP=<rg>
AZURE_LOCATION=eastus

AZURE_ACR_NAME=<acr-name>
AZURE_ACR_LOGIN_SERVER=<acr-name>.azurecr.io

AZURE_CONTAINERAPPS_ENV=cae-...
AZURE_CONTAINERAPP_BACKEND=ca-...-be-...
AZURE_CONTAINERAPP_FRONTEND=ca-...-fe-...
AZURE_LOG_ANALYTICS_WORKSPACE=<existing-workspace-name>

# Frontend → backend internal URL (within the CAE)
API_INTERNAL_URL=http://<backend-app-name>

# Image tags — keep these distinct from the ACI path because the frontend image
# bakes API_INTERNAL_URL at build time
BACKEND_IMAGE_TAG=manual-amd64
FRONTEND_IMAGE_TAG=containerapp-amd64

# Optional Azure OpenAI
AZURE_OPENAI_ACCOUNT=<oai-account-name>
AZURE_OPENAI_ENDPOINT=https://<oai-account-name>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4-1-mini
```

> If `AZURE_OPENAI_API_KEY` is omitted but `AZURE_OPENAI_ACCOUNT` is set, the deploy script auto-resolves the key via `az cognitiveservices account keys list`.

> **Security:** `local.env` contains secrets. It is `.gitignore`d — never commit it.

## 6. Deploy

```bash
bash scripts/azure/deploy_containerapp.sh
```

To use a non-default env file:
```bash
bash scripts/azure/deploy_containerapp.sh /path/to/your.env
```

### What the script does

1. Validates the active Azure subscription matches `AZURE_SUBSCRIPTION_ID`
2. Auto-installs the `containerapp` Azure CLI extension if missing
3. Runs **ACR Tasks** to build & push:
   - `hrsa-rpa-ava-backend:$BACKEND_IMAGE_TAG`
   - `hrsa-rpa-ava-frontend:$FRONTEND_IMAGE_TAG` (with `API_INTERNAL_URL` baked in)
4. Creates the Container Apps Environment if it doesn't exist (using the named Log Analytics workspace)
5. Creates the **backend** Container App (internal ingress, port 5000) — or `update`s it if it already exists
6. Creates the **frontend** Container App (external ingress, port 3000) — or `update`s it
7. Prints the public HTTPS URL

Total runtime: typically **5–12 minutes** end-to-end on a clean RG.

## 7. Verify

```bash
FE_FQDN=$(az containerapp show -g "$RG" -n "$AZURE_CONTAINERAPP_FRONTEND" --query "properties.configuration.ingress.fqdn" -o tsv)

# Public landing page
curl -fsS "https://$FE_FQDN/" | head

# Backend reachable via the frontend's Next.js rewrite
curl -fsS "https://$FE_FQDN/api/documents"

# Container app revisions
az containerapp revision list -g "$RG" -n "$AZURE_CONTAINERAPP_BACKEND" -o table
az containerapp revision list -g "$RG" -n "$AZURE_CONTAINERAPP_FRONTEND" -o table

# Stream logs
az containerapp logs show -g "$RG" -n "$AZURE_CONTAINERAPP_BACKEND" --follow
az containerapp logs show -g "$RG" -n "$AZURE_CONTAINERAPP_FRONTEND" --follow
```

## 8. Re-deploy after code changes

The deploy script is idempotent. After committing changes:

```bash
bash scripts/azure/deploy_containerapp.sh
```

It will rebuild both images and push them under the same tags, then `containerapp update` rolls each app to the new image. Each update creates a new revision; in single-revision mode (default) the new revision takes 100% traffic and old revisions deactivate.

## 9. Tear down

```bash
# Container apps only (keep ACR + OpenAI)
az containerapp delete -g "$RG" -n "$AZURE_CONTAINERAPP_FRONTEND" --yes
az containerapp delete -g "$RG" -n "$AZURE_CONTAINERAPP_BACKEND" --yes
az containerapp env delete -g "$RG" -n "$AZURE_CONTAINERAPPS_ENV" --yes

# Drop the registry (destroys all images)
az acr delete -g "$RG" -n "$AZURE_ACR_NAME" --yes

# Drop the OpenAI account (note: 48-hour soft-delete window)
az cognitiveservices account delete -g "$RG" -n "$AZURE_OPENAI_ACCOUNT"
az cognitiveservices account purge -g "$RG" -n "$AZURE_OPENAI_ACCOUNT" -l "$LOCATION"
```

---

## Defaults

| Setting | Default |
| --- | --- |
| Frontend CPU / memory | `0.5 vCPU` / `1.0 Gi` |
| Backend CPU / memory | `0.5 vCPU` / `1.0 Gi` |
| Frontend ingress | `external`, port `3000` (HTTPS) |
| Backend ingress | `internal`, port `5000` |
| Min / max replicas | `1` / `2` |
| Container Apps revision mode | `single` (default) |

Override any of these in `scripts/azure/local.env`.

---

## Troubleshooting

### `Microsoft.App` not registered

Ask a subscription Owner to run:
```bash
az provider register --namespace Microsoft.App --subscription <sub-id>
```

### `az acr build` denied

You lack `AcrPush`. Either grant it:
```bash
az role assignment create --assignee <upn-or-sp-id> --role AcrPush \
  --scope $(az acr show -n "$ACR_NAME" --query id -o tsv)
```
…or have someone with permission run the build.

### Frontend returns 200 but `/api/...` is 5xx

Likely the frontend image was built with the wrong `API_INTERNAL_URL`. Confirm:
```bash
az acr repository show-manifests --name "$ACR_NAME" --repository hrsa-rpa-ava-frontend --orderby time_desc -o table
```
…and rebuild via `bash scripts/azure/deploy_containerapp.sh` with `API_INTERNAL_URL=http://<backend-app-name>` in `local.env`.

### Backend container app keeps restarting

Stream logs:
```bash
az containerapp logs show -g "$RG" -n "$AZURE_CONTAINERAPP_BACKEND" --follow --tail 200
```
Common causes: missing `AZURE_OPENAI_*` env vars, unreachable OpenAI endpoint, or schema drift in `data/`.

### Model deployment says `ServiceModelDeprecated`

The model version you specified has been retired even though the model registry still lists it as GA. Look up a current version:
```bash
az cognitiveservices model list -l "$LOCATION" \
  --query "[?model.format=='OpenAI' && model.lifecycleStatus=='GenerallyAvailable'].{name:model.name,version:model.version}" \
  -o table
```

### State persistence

Container Apps default storage is **ephemeral** — uploads in `/app/uploads` and SQLite in `/app/database` are lost on revision swap or replica restart. For a real persistence layer, add an Azure Files volume mount or migrate the backend to Postgres / Cosmos DB.

### `az containerapp` extension warnings

The CLI prints `WARNING: The behavior of this command has been altered by the following extension: containerapp`. This is informational — the extension provides the `containerapp` namespace and is expected.
