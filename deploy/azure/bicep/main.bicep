// HRSA-RPA-POC Container Apps deployment
// Private network deployment for HRSA-RPA-AVA on Azure Government.
//
// Topology:
//   VNet
//     ├── infrastructure subnet     -> Container Apps managed environment (internal=true)
//     └── private-endpoints subnet  -> private endpoints (ACR, future Key Vault, etc.)
//
//   ACR (Premium, publicNetworkAccess=Disabled) reachable only over private endpoint.
//   Container Apps Environment with internal ingress only — no public IP exists anywhere.
//
// Reachability: the frontend app is reachable only from inside the VNet, from peered VNets,
// or from on-prem via ExpressRoute / S2S VPN. To resolve the env's default domain from
// peered networks, link the auto-created `privatelink.<region>.azurecontainerapps.us`-style
// private DNS zone to those VNets as well.
//
// Notes for Azure Government:
//   - ACR private DNS zone in Gov is `privatelink.azurecr.us` (overridable below).
//   - Confirm Container Apps regional availability in your Gov region before deploying.

targetScope = 'resourceGroup'

// -----------------------------------------------------------------------------
// Parameters
// -----------------------------------------------------------------------------

@description('Azure region. Use a Gov region: usgovvirginia, usgovtexas, usgovarizona, usgoviowa.')
param location string = resourceGroup().location

@description('Region abbreviation (e.g., eus, wus, usgv)')
param regionAbbr string = 'eus'

@description('Deployment environment (e.g., dev, sec, uat, prod)')
param deploymentEnvironment string

@description('Tag value for environment (e.g. dev, prod).')
param environmentName string = 'prod'

@description('Managed Identity resource ID (optional - leave empty to create new)')
param managedIdentityId string = ''

@description('Log Analytics Workspace ID (required - must be pre-existing)')
param logAnalyticsWorkspaceId string

@description('Subnet ID for Container Apps infrastructure (must be /23 or larger, delegated to Microsoft.App/environments)')
param infrastructureSubnetId string

@description('Subnet ID for private endpoints')
param privateEndpointSubnetId string

@description('Frontend container image reference (full ACR path + tag).')
param frontendImage string

@description('Backend container image reference (full ACR path + tag).')
param backendImage string

@description('Frontend container target port.')
param frontendTargetPort int = 3000

@description('Backend container target port.')
param backendTargetPort int = 5000

@description('Azure OpenAI endpoint URL.')
param azureOpenAiEndpoint string

@description('Azure OpenAI deployment name.')
param azureOpenAiDeployment string = 'gpt-4'

@description('CORS allowed origins for the backend (comma-separated).')
param corsAllowedOrigins string = ''

@description('Wire ACR into container app `registries` config. Set false to deploy with public images (e.g. mcr.microsoft.com) without needing AcrPull/ACR access.')
param useAcrRegistry bool = true

@description('Create Application Insights')
param createApplicationInsights bool = true

@description('Application Insights public network access for ingestion')
param appInsightsPublicNetworkAccessForIngestion string = 'Enabled'

@description('Application Insights public network access for query')
param appInsightsPublicNetworkAccessForQuery string = 'Enabled'

// -----------------------------------------------------------------------------
// Locals
// -----------------------------------------------------------------------------

// Naming convention: {service-abbr}-{region}-dgps-ehbs-{env}-rpa
var baseResourceName = '${regionAbbr}-dgps-ehbs-${deploymentEnvironment}-rpa'
var resourceNames = {
  containerAppFrontend: 'ca-${baseResourceName}-ui'
  containerAppBackend: 'ca-${baseResourceName}-svc'
  containerAppEnvironment: 'cae-${baseResourceName}'
  containerRegistry: 'cr${replace(baseResourceName, '-', '')}' // ACR requires alphanumeric only
  managedIdentity: 'id-${baseResourceName}'
  logAnalytics: 'law-${baseResourceName}'
  applicationInsights: 'appi-${baseResourceName}'
}

// Add environment tags following EHBs-IaC pattern
var baseTags = {
  Project: 'HRSA-ENTERPRISE-RPA'
  CostCenter: 'DGPS-EHBS'
  DT_Monitoring: 'True'
  Env: deploymentEnvironment
  Environment: deploymentEnvironment
}

var tags = baseTags

// Managed Identity Logic:
// - If managedIdentityId is provided (resource ID) -> Use existing identity
// - If managedIdentityId is empty -> Create new identity with auto-generated name
var actualMIName = !empty(managedIdentityId) ? managedIdentityId : resourceNames.managedIdentity
var shouldUseExisting = !empty(managedIdentityId)

// -----------------------------------------------------------------------------
// Managed Identity
// -----------------------------------------------------------------------------

module managedIdentity 'shared/managed-identity/main.bicep' = {
  name: 'managed-identity-deployment'
  params: {
    managedIdentity: actualMIName
    useExisting: shouldUseExisting
    location: location
    tags: tags
  }
}

// Note: VNet and subnets are created outside of this BICEP deployment
// Subnet IDs are passed as parameters

// Note: Log Analytics workspace is pre-existing and passed as parameter
// Note: Managed Identity is created by this deployment (or use existing if ID provided)

// -----------------------------------------------------------------------------
// Observability
// -----------------------------------------------------------------------------

module applicationInsights 'shared/application-insights/main.bicep' = if (createApplicationInsights) {
  name: 'application-insights-deployment'
  params: {
    applicationInsightsName: resourceNames.applicationInsights
    location: location
    workspaceId: logAnalyticsWorkspaceId
    publicNetworkAccessForIngestion: appInsightsPublicNetworkAccessForIngestion
    publicNetworkAccessForQuery: appInsightsPublicNetworkAccessForQuery
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Azure Container Registry with integrated private endpoint
// -----------------------------------------------------------------------------

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: resourceNames.containerRegistry
    tags: tags
    privateEndpointSubnetId: privateEndpointSubnetId
    enablePrivateEndpoint: true
  }
}

// -----------------------------------------------------------------------------
// Container Apps environment (internal, VNet-injected)
// -----------------------------------------------------------------------------

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'cae-deployment'
  params: {
    location: location
    name: resourceNames.containerAppEnvironment
    infrastructureSubnetId: infrastructureSubnetId
    logAnalyticsWorkspaceId: logAnalyticsWorkspaceId
    tags: tags
  }
}

// Note: Container Apps Environment creates its own private DNS zone automatically
// when deployed with internal=true. No manual DNS zone needed following EHBs-IaC pattern.

// -----------------------------------------------------------------------------
// Backend container app (internal-only; reachable only from inside the env)
// -----------------------------------------------------------------------------

module backendApp 'modules/container-app.bicep' = {
  name: 'ca-backend-deployment'
  params: {
    location: location
    name: resourceNames.containerAppBackend
    environmentId: containerAppsEnv.outputs.environmentId
    acrId: acr.outputs.acrId
    acrLoginServer: acr.outputs.loginServer
    image: backendImage
    targetPort: backendTargetPort
    ingressExternal: false
    useAcrRegistry: useAcrRegistry
    cpu: '0.5'
    memory: '1.0Gi'
    minReplicas: 1
    maxReplicas: 3
    managedIdentityId: managedIdentity.outputs.managedIdentityId
    appInsightsConnectionString: createApplicationInsights ? applicationInsights.outputs.connectionString : ''
    envVars: [
      {
        name: 'FLASK_ENV'
        value: 'production'
      }
      {
        name: 'FLASK_DEBUG'
        value: '0'
      }
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: azureOpenAiEndpoint
      }
      {
        name: 'AZURE_OPENAI_DEPLOYMENT'
        value: azureOpenAiDeployment
      }
      {
        name: 'CORS_ALLOWED_ORIGINS'
        value: corsAllowedOrigins
      }
      {
        name: 'UPLOAD_DIR'
        value: '/app/uploads'
      }
      {
        name: 'DATA_DIR'
        value: '/app/database'
      }
      {
        name: 'AZURE_CLIENT_ID'
        value: managedIdentity.outputs.managedIdentityClientId
      }
    ]
    secrets: {
      items: []
    }
    secretEnvVars: []
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Frontend container app (internal env => reachable from VNet/peered networks)
// -----------------------------------------------------------------------------

module frontendApp 'modules/container-app.bicep' = {
  name: 'ca-frontend-deployment'
  params: {
    location: location
    name: resourceNames.containerAppFrontend
    environmentId: containerAppsEnv.outputs.environmentId
    acrId: acr.outputs.acrId
    acrLoginServer: acr.outputs.loginServer
    image: frontendImage
    targetPort: frontendTargetPort
    ingressExternal: true
    useAcrRegistry: useAcrRegistry
    cpu: '0.5'
    memory: '1.0Gi'
    minReplicas: 1
    maxReplicas: 3
    managedIdentityId: managedIdentity.outputs.managedIdentityId
    appInsightsConnectionString: createApplicationInsights ? applicationInsights.outputs.connectionString : ''
    envVars: [
      // Reachable inter-app via the env's internal FQDN. Note: next.config.js bakes
      // API_INTERNAL_URL at build time, so this only matters if the frontend image
      // is rebuilt to read it at runtime.
      {
        name: 'API_INTERNAL_URL'
        value: 'https://${backendApp.outputs.fqdn}'
      }
    ]
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------

output acrLoginServer string = acr.outputs.loginServer
output acrId string = acr.outputs.acrId
output containerAppsEnvironmentId string = containerAppsEnv.outputs.environmentId
output containerAppsEnvironmentDefaultDomain string = containerAppsEnv.outputs.defaultDomain
output containerAppsEnvironmentStaticIp string = containerAppsEnv.outputs.staticIp
output frontendFqdn string = frontendApp.outputs.fqdn
output backendFqdn string = backendApp.outputs.fqdn
output managedIdentityId string = managedIdentity.outputs.managedIdentityId
output managedIdentityClientId string = managedIdentity.outputs.managedIdentityClientId
output managedIdentityPrincipalId string = managedIdentity.outputs.managedIdentityPrincipalId
output applicationInsightsId string = createApplicationInsights ? applicationInsights.outputs.applicationInsightsId : ''
