// Generic private endpoint with private DNS zone group.

@description('Azure region.')
param location string

@description('Private endpoint resource name.')
param name string

@description('Subnet ID to deploy the private endpoint into.')
param subnetId string

@description('Resource ID of the private-link-enabled service (e.g. ACR).')
param privateLinkResourceId string

@description('Private link group ID (e.g. "registry" for ACR).')
param groupId string

@description('Private DNS zone ID for automatic record creation.')
param privateDnsZoneId string

@description('Resource tags.')
param tags object

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${name}-conn'
        properties: {
          privateLinkServiceId: privateLinkResourceId
          groupIds: [
            groupId
          ]
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'default'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

output privateEndpointId string = privateEndpoint.id
