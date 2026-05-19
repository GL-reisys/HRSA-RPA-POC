# Manual Azure Container Instance Deployment

This guide walks a developer through deploying the HRSA RPA-POC app (frontend + backend) to **Azure Container Instances (ACI)** from any Azure subscription/resource group they have access to.

The pipeline uses **ACR Tasks** for cloud-side image builds, so a local Docker installation is **not required**.

---

## When to use this path

Use this path when:

- you have at least **Contributor** rights on the target resource group
- you do **not** want to (or cannot) build Docker images locally
- you want a self-contained deploy from your laptop without the GitHub Actions pipeline

## Prerequisites

| Tool | Notes |
| --- | --- |
| Azure CLI (`az`) | logged in to the target tenant/subscription |
| Python 3 | used by `render_aci_manifest.py` |
| Bash | macOS/Linux/WSL; the Windows PowerShell script still uses local Docker — see [Windows note](#windows) |

You do **not** need Docker installed.

---

## 1. Authenticate against the target subscription

```bash
az login                                            # interactive
# or for a service principal
az login --service-principal -u <APP_ID> -p <SECRET> --tenant <TENANT_ID>

az account set --subscription <SUBSCRIPTION_ID>
az account show
```

Verify the active subscription matches the one you want to deploy into.

## 2. Discover what already exists in the target RG

Before naming or creating anything, look at the conventions and resources already in the resource group.

```bash
RG=<your-resource-group>

# RG location and tags (apply the same tags to new resources)
az group show --name "$RG" --query "{location:location,tags:tags}" -o json

# Existing resources (helps you match the naming convention)
az resource list --resource-group "$RG" --query "[].{name:name,type:type}" -o table

# Existing ACRs in this subscription (you may be able to reuse one)
az acr list --query "[].{name:name,loginServer:loginServer,rg:resourceGroup,adminEnabled:adminUserEnabled}" -o table

# Existing AI / Cognitive Services in the RG (if you want backend AI features)
az cognitiveservices account list --resource-group "$RG" -o table
```

**Pick names that match the RG's convention.** For example, an RG that uses `*-eus-dgps-ehbs-*-sbx` patterns suggests:

| Resource | Recommended name pattern | Constraint |
| --- | --- | --- |
| Azure Container Registry | `cr<region><project>sbx` (alphanumeric only, lowercase) | 5–50 chars, globally unique |
| Container group | `aci-<region>-<project>-sbx` | ≤ 63 chars |
| DNS label | `aci-<region>-<project>-sbx` | globally unique within region |

Verify availability before committing:

```bash
az acr check-name --name <proposed-acr-name>
nslookup <proposed-dns-label>.<region>.azurecontainer.io   # NXDOMAIN means free
```

## 3. Configure `scripts/azure/local.env`

Copy the example and fill in values for **your** subscription:

```bash
cp scripts/azure/local.env.example scripts/azure/local.env
```

Edit `scripts/azure/local.env`:

```bash
AZURE_SUBSCRIPTION_ID=<your-sub-id>
AZURE_RESOURCE_GROUP=<your-rg>
AZURE_LOCATION=<eastus|westus2|...>
AZURE_ACR_NAME=<acr-name>                       # alphanumeric only
AZURE_ACR_LOGIN_SERVER=<acr-name>.azurecr.io
AZURE_CONTAINER_GROUP_NAME=<aci-name>
AZURE_DNS_LABEL=<dns-label>

# Optional: cross-subscription Azure OpenAI access (key-based)
AZURE_OPENAI_ENDPOINT=https://<your-openai>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
```

> **Security note:** `local.env` contains secrets (ACR creds, OpenAI key). It is `.gitignore`d — keep it that way and **never commit it**.

## 4. Create the Azure Container Registry (one-time)

If you don't already have an ACR you can reuse, create one. Admin user must be enabled because the ACI manifest authenticates to ACR with username/password (Basic SKU is sufficient for POC workloads):

```bash
az acr create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_ACR_NAME" \
  --sku Basic \
  --location "$AZURE_LOCATION" \
  --admin-enabled true \
  --tags CostCenter=<...> Owner=<...> Project=<...> app=hrsa-rpa-ava
```

If reusing an existing ACR, verify admin is enabled:

```bash
az acr update --name "$AZURE_ACR_NAME" --admin-enabled true
```

## 5. Run the deploy script

From the repository root:

```bash
bash scripts/azure/deploy_local.sh
```

To use a non-default env file:

```bash
bash scripts/azure/deploy_local.sh /path/to/your.env
```

### What it does

1. Sources `scripts/azure/local.env` and validates required variables
2. Verifies the active Azure subscription matches `AZURE_SUBSCRIPTION_ID`
3. Reads ACR admin credentials via `az acr credential show`
4. Submits a **cloud build** for the backend image via `az acr build` (linux/amd64)
5. Submits a **cloud build** for the frontend image via `az acr build` (linux/amd64), passing `API_INTERNAL_URL` as a build arg
6. Renders the ACI YAML manifest from `deploy/azure/aci-container-group.yaml.template`
7. Calls `scripts/azure/deploy_aci.sh`, which:
   - exports the existing container group definition (if any) to a temp file as a backup
   - deletes the existing container group
   - creates the new container group from the rendered manifest
   - polls until state is `Running` (up to ~5 min)
   - **rolls back** to the previous definition if creation fails
8. Prints the public URL: `http://<DNS_LABEL>.<REGION>.azurecontainer.io:3000`

Total runtime: typically **5–12 minutes** (most of it backend + frontend image builds).

## 6. Verify the deployment

```bash
# Frontend
curl -fsS "http://${AZURE_DNS_LABEL}.${AZURE_LOCATION}.azurecontainer.io:3000/" | head

# Backend health (proxied via Next.js API route)
curl -fsS "http://${AZURE_DNS_LABEL}.${AZURE_LOCATION}.azurecontainer.io:3000/api/documents"

# Container group state
az container show \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --name "$AZURE_CONTAINER_GROUP_NAME" \
  --query "{state:instanceView.state,fqdn:ipAddress.fqdn,events:instanceView.events[-3:]}" \
  -o json

# Stream container logs
az container logs --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --container-name backend --follow
az container logs --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --container-name frontend --follow
```

## 7. Tear down

```bash
# Delete just the container group (keeps the ACR + images)
az container delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --yes

# Delete the ACR too (destroys all built images)
az acr delete --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_ACR_NAME" --yes
```

---

## Defaults

| Setting | Default |
| --- | --- |
| Frontend CPU / memory | `0.5 vCPU` / `1.0 GB` |
| Backend CPU / memory | `0.5 vCPU` / `1.0 GB` |
| Frontend port | `3000` (publicly exposed) |
| Backend port | `5000` (cluster-internal only) |
| Frontend → backend URL | `http://127.0.0.1:5000` (same container group) |
| Image tag | `manual-amd64` |
| Restart policy | `Always` |

Override any of these in `scripts/azure/local.env`.

---

## Troubleshooting

### `InaccessibleImage` on the container group

The ACI cannot pull the image. Check:

- ACR admin user is enabled (`az acr show -n $AZURE_ACR_NAME --query adminUserEnabled`)
- The image actually exists: `az acr repository show-tags -n $AZURE_ACR_NAME --repository hrsa-rpa-ava-backend`
- Image tag in `local.env` matches what was pushed
- ACR username/password were valid at deploy time (rotate via `az acr credential renew`)

### `az acr build` fails with `denied: requested access to the resource is denied`

Your account doesn't have `AcrPush` on the registry. Either grant it:
```bash
az role assignment create --assignee <your-upn-or-sp-id> --role AcrPush --scope $(az acr show -n $AZURE_ACR_NAME --query id -o tsv)
```
or have someone with permission run the build.

### `Subscription mismatch` from `deploy_local.sh`

The script enforces that the active `az` context matches `AZURE_SUBSCRIPTION_ID` in `local.env`. Run:
```bash
az account set --subscription <id>
```

### DNS label already taken

`AZURE_DNS_LABEL` must be globally unique within the region. Pick a different label and re-run.

### Existing container group will be replaced

`deploy_aci.sh` deletes any existing container group with the same name before recreating it (with rollback on failure). If you want to deploy a side-by-side environment, change `AZURE_CONTAINER_GROUP_NAME` and `AZURE_DNS_LABEL` in `local.env`.

### Container starts but backend AI features fail

The Azure OpenAI vars in `local.env` are passed into the backend container. If they're empty or invalid, AI features will fail at runtime even though the container is healthy. Check backend logs and verify the endpoint/key.

<a id="windows"></a>
### Windows note

`scripts/azure/deploy_local.ps1` currently still uses local `docker buildx` (the legacy flow). To get the Docker-free ACR Tasks flow on Windows, either:

- run `scripts/azure/deploy_local.sh` under WSL2, or
- use Docker Desktop with buildx and follow the PowerShell script's prompts.
