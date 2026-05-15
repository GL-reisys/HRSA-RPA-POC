# HRSA-RPA-POC BICEP Deployment - Release Notes

## Version 2.0

### Overview
BICEP deployment for HRSA-RPA-POC Container Apps with private networking, managed identity, and observability.

### Key Features

- **Private networking** - VNet-injected Container Apps with no public endpoints
- **Managed identity authentication** - User-assigned identity for secure, keyless authentication to Azure OpenAI and ACR
- **Application Insights** - Built-in observability and monitoring
- **Modular design** - Reusable shared modules for common resources
- **Azure Government support** - Designed for Gov cloud deployment

### Required Parameters

```bicep
deploymentEnvironment: string          // Environment suffix (dev, prod, sbx, etc.)
namePrefix: string                     // Resource name prefix
acrName: string                        // Azure Container Registry name
infrastructureSubnetId: string         // Subnet ID for Container Apps (min /23)
privateEndpointSubnetId: string        // Subnet ID for private endpoints
frontendImage: string                  // Frontend container image
backendImage: string                   // Backend container image
azureOpenAiEndpoint: string            // Azure OpenAI endpoint URL
```

### Prerequisites

1. **Pre-existing VNet with subnets:**
   - **Infrastructure subnet** (minimum /23, **must be delegated to `Microsoft.App/environments`**)
   - **Private endpoints subnet** (no delegation required)

2. **Resource providers registered:**
   - Microsoft.App
   - Microsoft.OperationalInsights
   - Microsoft.ContainerRegistry

### Deployment Example

```bash
az deployment group create \
  --resource-group rg-hrsa-rpa-poc \
  --template-file main.bicep \
  --parameters \
    deploymentEnvironment='dev' \
    namePrefix='hrsa-rpa-dev' \
    acrName='hrsarpoacrdev' \
    environmentName='dev' \
    infrastructureSubnetId='/subscriptions/.../subnets/aca-infra' \
    privateEndpointSubnetId='/subscriptions/.../subnets/private-endpoints' \
    frontendImage='hrsarpoacrdev.azurecr.us/frontend:latest' \
    backendImage='hrsarpoacrdev.azurecr.us/backend:latest' \
    azureOpenAiEndpoint='https://your-openai.openai.azure.us/'
```

### Module Structure

```
deploy/azure/bicep/
├── main.bicep                          # Main deployment template
├── modules/
│   ├── acr.bicep                       # ACR with integrated private endpoint
│   ├── container-apps-env.bicep        # Container Apps Environment
│   └── container-app.bicep             # Container App definition
└── shared/                             # Reusable modules (EHBs-IaC pattern)
    ├── managed-identity/main.bicep
    └── application-insights/main.bicep
```

### Resources Deployed

- **Azure Container Registry** (Premium, private endpoint)
- **Container Apps Environment** (internal, VNet-injected)
- **Container Apps** (frontend, backend)
- **Log Analytics Workspace**
- **Application Insights**
- **Managed Identity** (user-assigned)

### Required RBAC Configuration

**Important**: All RBAC assignments must be configured outside of BICEP after deployment. The application uses managed identity authentication (no API keys).

The deployment creates a managed identity but does not configure any role assignments. You **must** configure the following RBAC for the managed identity before the application will function:

| Resource Type | Role | Purpose |
|---------------|------|---------|
| **Azure Container Registry** | `AcrPull` | Pull container images |
| **Azure OpenAI** | `Cognitive Services OpenAI User` | Access OpenAI API |

#### Configuration Commands

```bash
# Get Managed Identity Principal ID from deployment output
PRINCIPAL_ID=$(az deployment group show \
  --resource-group <rg-name> \
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

**Note**: The Managed Identity Principal ID is available in deployment outputs as `managedIdentityPrincipalId`.

### Known Limitations

- Container Apps must be GA in your Azure Government region
- Infrastructure subnet must be minimum /23 CIDR and delegated to `Microsoft.App/environments`
- ACR requires Premium SKU for private endpoints
- VNet and subnets must be created before deployment
- Subnet delegation cannot be changed after Container Apps Environment is deployed

### Support

For issues or questions, refer to:
- `README.md` - Deployment instructions and prerequisites
- Azure Container Apps documentation
