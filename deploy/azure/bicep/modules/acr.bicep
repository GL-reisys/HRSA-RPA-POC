// Azure Container Registry, Premium SKU, fully private (publicNetworkAccess disabled).
// Private endpoint integrated following EHBs-IaC pattern.

@description('Azure region.')
param location string

@description('ACR name (5-50 lowercase alphanumeric, globally unique).')
@minLength(5)
@maxLength(50)
param name string

@description('Resource tags.')
param tags object

@description('Subnet ID for private endpoint (optional)')
param privateEndpointSubnetId string = ''

@description('Enable private endpoint')
param enablePrivateEndpoint bool = false

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

// Private Endpoint for ACR (following EHBs-IaC pattern - inline, not separate module)
resource acrPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-05-01' = if (enablePrivateEndpoint && !empty(privateEndpointSubnetId)) {
  name: 'pep-${name}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'pep-${name}-conn'
        properties: {
          privateLinkServiceId: acr.id
          groupIds: [ 'registry' ]
        }
      }
    ]
  }
}

output acrId string = acr.id
output acrName string = acr.name
output loginServer string = acr.properties.loginServer
output privateEndpointId string = enablePrivateEndpoint ? acrPrivateEndpoint.id : ''
