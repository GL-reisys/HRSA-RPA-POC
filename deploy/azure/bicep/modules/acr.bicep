// Azure Container Registry, Premium SKU, fully private (publicNetworkAccess disabled).
// Private endpoint and DNS are provisioned by the caller.

@description('Azure region.')
param location string

@description('ACR name (5-50 lowercase alphanumeric, globally unique).')
@minLength(5)
@maxLength(50)
param name string

@description('Resource tags.')
param tags object

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Disabled'
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
    policies: {
      quarantinePolicy: {
        status: 'disabled'
      }
      trustPolicy: {
        type: 'Notary'
        status: 'disabled'
      }
      retentionPolicy: {
        days: 30
        status: 'enabled'
      }
    }
  }
}

output acrId string = acr.id
output acrName string = acr.name
output loginServer string = acr.properties.loginServer
