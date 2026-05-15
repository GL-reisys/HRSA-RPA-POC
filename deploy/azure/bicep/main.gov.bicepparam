// Example parameters for Azure Government deployment.
// Replace placeholder values, then deploy with:
//   az deployment group create \
//     --resource-group RG-HRSA-RPA-AVA-PRIV \
//     --template-file main.bicep \
//     --parameters main.gov.bicepparam

using 'main.bicep'

param location = 'usgovvirginia'
param namePrefix = 'hrsarpaava'
param acrName = 'hrsarpaavaacr'
param environmentName = 'prod'

// /20 VNet, ample headroom for additional subnets (firewall, jumpbox, future PEs).
param vnetAddressPrefix = '10.40.0.0/20'
param infraSubnetPrefix = '10.40.0.0/23'
param peSubnetPrefix    = '10.40.2.0/26'

// Azure Government private DNS zone for ACR.
param acrPrivateDnsZoneName = 'privatelink.azurecr.us'

// These must already exist in the registry (push them after ACR is provisioned).
param frontendImage = 'hrsarpaavaacr.azurecr.us/hrsa-rpa-ava-frontend:gov-amd64'
param backendImage  = 'hrsarpaavaacr.azurecr.us/hrsa-rpa-ava-backend:gov-amd64'

param frontendTargetPort = 3000
param backendTargetPort  = 5000

param azureOpenAiEndpoint   = 'https://your-openai-gov.openai.azure.us/'
param azureOpenAiDeployment = 'gpt-4'

// Supply at deploy time with --parameters azureOpenAiApiKey=...  (do NOT commit secrets).
param azureOpenAiApiKey = readEnvironmentVariable('AZURE_OPENAI_API_KEY', '')

// Internal app — no public origins. Add the env's default domain if browser CORS calls
// will originate from a different subdomain of the same env.
param corsAllowedOrigins = ''
