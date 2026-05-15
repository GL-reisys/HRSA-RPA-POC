// Private DNS zone, VNet link, and optional A records.

@description('DNS zone name (e.g. privatelink.azurecr.us).')
param zoneName string

@description('VNet ID to link the zone to.')
param vnetId string

@description('VNet link resource name.')
param vnetLinkName string

@description('Resource tags.')
param tags object

@description('Optional A records to create in this zone. Items: { name, ipv4Address }.')
param aRecords array = []

resource zone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: zoneName
  location: 'global'
  tags: tags
}

resource vnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: zone
  name: vnetLinkName
  location: 'global'
  tags: tags
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}

resource records 'Microsoft.Network/privateDnsZones/A@2024-06-01' = [for record in aRecords: {
  parent: zone
  name: record.name
  properties: {
    ttl: 3600
    aRecords: [
      {
        ipv4Address: record.ipv4Address
      }
    ]
  }
}]

output zoneId string = zone.id
output zoneName string = zone.name
