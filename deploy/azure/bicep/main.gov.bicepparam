// Example parameters for Azure Government deployment.
// Replace placeholder values, then deploy with:
//   az deployment group create \
//     --resource-group RG-HRSA-RPA-AVA-PRIV \
//     --template-file main.bicep \
//     --parameters main.gov.bicepparam

using 'main.bicep'

//Expose as Octopus Variable for CI/CD
param infrastructureSubnetId = '' // Infrastructure subnet (minimum /23, must be delegated to `Microsoft.App/environments`)
param privateEndpointSubnetId = '' // Private endpoint subnet (no delegation required)
param logAnalyticsWorkspaceId = '' // Pre-existing Log Analytics workspace resource ID
param location = 'eastus' // Azure region
param regionAbbr = 'eus' // Region abbreviation (eus, wus, usgv, etc.)
param deploymentEnvironment = 'sbx02' // Environment: dev, utl01, uat02, sec, prod
param environmentName = 'sbx' // Tag value: dev, sbx, nonprod, prod
param azureOpenAiEndpoint   = 'https://your-openai-gov.openai.azure.us/' // TODO: check with OM whether they can create Open AI and provide us the endpoints
param azureOpenAiDeployment = 'gpt-4'

// Container images - must already exist in the registry (push them after ACR is provisioned)
param frontendImage = 'creusdgpsehbssecrpa.azurecr.us/ehbs-${environmentName}-ui:latest'
param backendImage  = 'creusdgpsehbssecrpa.azurecr.us/ehbs-${environmentName}-svc:latest'
param frontendTargetPort = 3000
param backendTargetPort  = 5000

// Internal app — no public origins. Add the env's default domain if browser CORS calls
// will originate from a different subdomain of the same env.
param corsAllowedOrigins = ''
