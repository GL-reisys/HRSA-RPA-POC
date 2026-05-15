# Private-network Bicep deployment (Azure Government)

Provisions a fully private deployment of HRSA-RPA-AVA into an Azure Government subscription. No public IPs are created; the app is reachable only from inside the VNet, from peered VNets, or from on-prem via ExpressRoute / S2S VPN.

## Topology

```
                   Pre-existing VNet (created outside BICEP)
                   ┌──────────────────────────────────────────────┐
                   │  VNet (e.g., 10.40.0.0/20)                    │
                   │   ├── infrastructure subnet (min /23)         │
                   │   │     └── Container Apps managed env        │
                   │   │           internal=true, no public IP     │
                   │   │           ├── frontend (ingress.external) │
                   │   │           └── backend  (internal only)    │
                   │   └── private-endpoints subnet                │
                   │         └── ACR private endpoint              │
                   └──────────────────────────────────────────────┘
                   
                   Resource Group (BICEP creates these)
                   ┌──────────────────────────────────────────────┐
                   │  ACR (Premium, publicNetworkAccess=Disabled)  │
                   │  Container Apps Environment                   │
                   │  Container Apps (frontend, backend)           │
                   │  Log Analytics workspace                      │
                   │  Application Insights                         │
                   │  Managed Identity                             │
                   └──────────────────────────────────────────────┘
```

## Files

| File | Purpose |
| --- | --- |
| `README.md` | This file - deployment instructions and prerequisites. |
| `RELEASE.md` | Release notes and change history. |
| `main.bicep` | Top-level template, wires modules together. |
| `main.gov.bicepparam` | Example parameter file with Azure Gov defaults. |
| `deploy.sh` | Validates, runs `what-if`, and deploys. |
| **Modules** | |
| `modules/acr.bicep` | Premium ACR with integrated private endpoint. |
| `modules/container-apps-env.bicep` | Internal Container Apps environment. |
| `modules/container-app.bicep` | One Container App + user-assigned MI with AcrPull. |
| **Shared Modules** (EHBs-IaC Pattern) | |
| `shared/managed-identity/main.bicep` | Managed identity (create new or use existing). |
| `shared/application-insights/main.bicep` | Application Insights with Log Analytics. |

## Prereqs

1. **VNet and subnets created outside of this deployment:**
   - **Infrastructure subnet** for Container Apps:
     - Minimum /23 CIDR (e.g., 10.40.0.0/23)
     - **Must be delegated to `Microsoft.App/environments`**
     - Command to delegate:
       ```bash
       az network vnet subnet update \
         --resource-group <rg> \
         --vnet-name <vnet> \
         --name <subnet-name> \
         --delegations Microsoft.App/environments
       ```
   - **Private endpoints subnet**:
     - No delegation required
     - Recommended /26 or larger (e.g., 10.40.2.0/26)
   - Subnet IDs will be passed as parameters to the BICEP deployment
   
2. Azure CLI pointed at the Gov cloud:
   ```bash
   az cloud set --name AzureUSGovernment
   az login
   az account set --subscription <gov-subscription-id>
   ```
3. Resource group exists in your chosen Gov region (`usgovvirginia`, `usgovtexas`, `usgovarizona`, or `usgoviowa`):
   ```bash
   az group create --name RG-HRSA-RPA-AVA-PRIV --location usgovvirginia
   ```
4. Resource providers registered on the subscription. The deploy script handles this, but you can do it manually:
   ```bash
   az provider register --namespace Microsoft.App --wait
   az provider register --namespace Microsoft.OperationalInsights --wait
   az provider register --namespace Microsoft.ContainerRegistry --wait
   ```
5. Container Apps must be GA in your chosen Gov region. Verify with `az provider show --namespace Microsoft.App --query "resourceTypes[?resourceType=='managedEnvironments'].locations" -o tsv`.

## Deploy

1. Edit `main.gov.bicepparam` — set subnet IDs, `namePrefix`, `acrName`, region, and Azure OpenAI endpoint to your values.
2. Run the script (it does validate → what-if → confirm → deploy):
   ```bash
   ./deploy.sh RG-HRSA-RPA-AVA-PRIV
   ```
   
   Or deploy directly:
   ```bash
   az deployment group create \
     --resource-group RG-HRSA-RPA-AVA-PRIV \
     --template-file main.bicep \
     --parameters main.gov.bicepparam
   ```

## After the first deploy: build and push images

ACR has `publicNetworkAccess=Disabled`, so you cannot push from your laptop unless your machine has a route into the VNet. Use one of:

- **`az acr build`** (recommended). Runs the build inside ACR using the registry's task agent, which has private access to itself:
  ```bash
  az acr build \
    --registry hrsarpaavaacr \
    --image hrsa-rpa-ava-backend:gov-amd64 \
    --platform linux/amd64 \
    ../../RPA-POC-AVA-app/backend

  az acr build \
    --registry hrsarpaavaacr \
    --image hrsa-rpa-ava-frontend:gov-amd64 \
    --platform linux/amd64 \
    --build-arg API_INTERNAL_URL=https://<backend-fqdn-from-output> \
    ../../RPA-POC-AVA-app/frontend
  ```
- A self-hosted runner / jumpbox attached to the VNet that runs `docker push` over the private endpoint.

After images are in ACR, redeploy (or `az containerapp update --image ...`) to roll the new revisions.

## Post-Deployment: Configure RBAC (Required)

**Critical**: The application uses **managed identity authentication** (no API keys). You **must** configure RBAC before the application will function.

The deployment does NOT configure any RBAC assignments. Configure the following role assignments manually:

### Required RBAC Assignments

| Resource | Role | Purpose |
|----------|------|---------|
| Azure Container Registry | `AcrPull` | Pull container images |
| Azure OpenAI | `Cognitive Services OpenAI User` | Access OpenAI API (managed identity auth) |

### Configuration Commands

```bash
# Get Managed Identity Principal ID from deployment output
PRINCIPAL_ID=$(az deployment group show \
  --resource-group RG-HRSA-RPA-AVA-PRIV \
  --name <deployment-name> \
  --query properties.outputs.managedIdentityPrincipalId.value -o tsv)

# Grant AcrPull to ACR
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "AcrPull" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.ContainerRegistry/registries/<acr-name>

# Grant access to Azure OpenAI
az role assignment create \
  --assignee $PRINCIPAL_ID \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai-name>
```

## Accessing the app

The frontend has `ingress.external = true` within the internal ACA environment, so it's reachable at `https://<frontend-app>.<env-default-domain>` from anywhere on the linked VNet. To reach it from on-prem:

1. Peer the spoke VNet (this stack) to your hub or directly to your ExpressRoute gateway VNet.
2. Link the auto-created ACA private DNS zone (`<random>.<region>.azurecontainerapps.us`) to the hub VNet as well, or use a central DNS forwarder.
3. From on-prem, resolve and hit `https://<frontend-app>.<env-default-domain>` over the private route.

## Tightening further (optional follow-ups)

- **Put secrets in Key Vault** with another private endpoint; reference them via Container Apps' Key Vault secret integration instead of a plain secret.
- **Egress lockdown**: today, outbound traffic from the ACA env can reach the internet. To force egress through a hub firewall, add a UDR on the infrastructure subnet pointing `0.0.0.0/0` at your Azure Firewall.
- **NSG hardening**: the PE subnet NSG already denies inbound from `Internet`. The infra subnet NSG is intentionally open since Container Apps manages east-west traffic; layer your hub firewall rules on top via UDR.
- **Diagnostic settings**: send Container Apps, ACR, and NSG flow logs to the Log Analytics workspace via `Microsoft.Insights/diagnosticSettings` resources.

## Commercial cloud port (if needed)

Only two values change:
- `acrPrivateDnsZoneName`: `privatelink.azurecr.io` instead of `.us`
- `azureOpenAiEndpoint`: `.openai.azure.com` instead of `.openai.azure.us`

Region values become commercial regions (`eastus`, etc.).
