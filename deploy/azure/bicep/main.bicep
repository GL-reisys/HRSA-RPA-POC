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

@description('Resource name prefix (3-12 lowercase alphanumeric).')
@minLength(3)
@maxLength(12)
param namePrefix string

@description('ACR name (5-50 globally unique lowercase alphanumeric).')
@minLength(5)
@maxLength(50)
param acrName string

@description('Tag value for environment (e.g. dev, prod).')
param environmentName string = 'prod'

@description('VNet CIDR.')
param vnetAddressPrefix string = '10.40.0.0/20'

@description('Subnet for the Container Apps environment. Consumption-only requires /23 minimum.')
param infraSubnetPrefix string = '10.40.0.0/23'

@description('Subnet for private endpoints.')
param peSubnetPrefix string = '10.40.2.0/26'

@description('ACR private DNS zone name. Gov default: privatelink.azurecr.us.')
param acrPrivateDnsZoneName string = 'privatelink.azurecr.us'

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

@secure()
@description('Azure OpenAI API key (stored as a Container App secret).')
param azureOpenAiApiKey string

@description('CORS allowed origins for the backend (comma-separated).')
param corsAllowedOrigins string = ''

// -----------------------------------------------------------------------------
// Locals
// -----------------------------------------------------------------------------

var tags = {
  application: 'hrsa-rpa-ava'
  environment: environmentName
  'managed-by': 'bicep'
  networkProfile: 'private'
}

// -----------------------------------------------------------------------------
// Networking
// -----------------------------------------------------------------------------

module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    location: location
    namePrefix: namePrefix
    vnetAddressPrefix: vnetAddressPrefix
    infraSubnetPrefix: infraSubnetPrefix
    peSubnetPrefix: peSubnetPrefix
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Observability
// -----------------------------------------------------------------------------

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${namePrefix}-law'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// -----------------------------------------------------------------------------
// Azure Container Registry + private endpoint
// -----------------------------------------------------------------------------

module acr 'modules/acr.bicep' = {
  name: 'acr'
  params: {
    location: location
    name: acrName
    tags: tags
  }
}

module acrPrivateDnsZone 'modules/private-dns-zone.bicep' = {
  name: 'acr-pdz'
  params: {
    zoneName: acrPrivateDnsZoneName
    vnetId: network.outputs.vnetId
    vnetLinkName: '${namePrefix}-acr-vnetlink'
    tags: tags
  }
}

module acrPrivateEndpoint 'modules/private-endpoint.bicep' = {
  name: 'acr-pe'
  params: {
    location: location
    name: '${namePrefix}-acr-pe'
    subnetId: network.outputs.peSubnetId
    privateLinkResourceId: acr.outputs.acrId
    groupId: 'registry'
    privateDnsZoneId: acrPrivateDnsZone.outputs.zoneId
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Container Apps environment (internal, VNet-injected)
// -----------------------------------------------------------------------------

module containerAppsEnv 'modules/container-apps-env.bicep' = {
  name: 'aca-env'
  params: {
    location: location
    name: '${namePrefix}-aca-env'
    infrastructureSubnetId: network.outputs.infraSubnetId
    logAnalyticsWorkspaceName: logAnalytics.name
    tags: tags
  }
}

// Private DNS zone for the env's default domain so peered networks can resolve app FQDNs
// to the env's internal static IP. Wildcard record covers every app in the env.
module acaPrivateDnsZone 'modules/private-dns-zone.bicep' = {
  name: 'aca-pdz'
  params: {
    zoneName: containerAppsEnv.outputs.defaultDomain
    vnetId: network.outputs.vnetId
    vnetLinkName: '${namePrefix}-aca-vnetlink'
    tags: tags
    aRecords: [
      {
        name: '*'
        ipv4Address: containerAppsEnv.outputs.staticIp
      }
      {
        name: '@'
        ipv4Address: containerAppsEnv.outputs.staticIp
      }
    ]
  }
}

// -----------------------------------------------------------------------------
// Backend container app (internal-only; reachable only from inside the env)
// -----------------------------------------------------------------------------

module backendApp 'modules/container-app.bicep' = {
  name: 'backend-app'
  params: {
    location: location
    name: '${namePrefix}-backend'
    environmentId: containerAppsEnv.outputs.environmentId
    acrId: acr.outputs.acrId
    acrLoginServer: acr.outputs.loginServer
    image: backendImage
    targetPort: backendTargetPort
    ingressExternal: false
    cpu: '0.5'
    memory: '1.0Gi'
    minReplicas: 1
    maxReplicas: 3
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
    ]
    secrets: {
      items: [
        {
          name: 'azure-openai-api-key'
          value: azureOpenAiApiKey
        }
      ]
    }
    secretEnvVars: [
      {
        name: 'AZURE_OPENAI_API_KEY'
        secretRef: 'azure-openai-api-key'
      }
    ]
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Frontend container app (internal env => reachable from VNet/peered networks)
// -----------------------------------------------------------------------------

module frontendApp 'modules/container-app.bicep' = {
  name: 'frontend-app'
  params: {
    location: location
    name: '${namePrefix}-frontend'
    environmentId: containerAppsEnv.outputs.environmentId
    acrId: acr.outputs.acrId
    acrLoginServer: acr.outputs.loginServer
    image: frontendImage
    targetPort: frontendTargetPort
    ingressExternal: true
    cpu: '0.5'
    memory: '1.0Gi'
    minReplicas: 1
    maxReplicas: 3
    envVars: [
      // Reachable inter-app via the env's internal FQDN. Note: next.config.js bakes
      // API_INTERNAL_URL at build time, so this only matters if the frontend image
      // is rebuilt to read it at runtime.
      {
        name: 'API_INTERNAL_URL'
        value: 'https://${backendApp.outputs.fqdn}'
      }
    ]
    secrets: {
      items: []
    }
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------

output vnetId string = network.outputs.vnetId
output infraSubnetId string = network.outputs.infraSubnetId
output peSubnetId string = network.outputs.peSubnetId
output acrLoginServer string = acr.outputs.loginServer
output acrId string = acr.outputs.acrId
output containerAppsEnvironmentId string = containerAppsEnv.outputs.environmentId
output containerAppsEnvironmentDefaultDomain string = containerAppsEnv.outputs.defaultDomain
output containerAppsEnvironmentStaticIp string = containerAppsEnv.outputs.staticIp
output frontendFqdn string = frontendApp.outputs.fqdn
output backendFqdn string = backendApp.outputs.fqdn
