// VNet with two subnets: infrastructure (Container Apps) and private-endpoints.
// Consumption-only ACA does NOT require subnet delegation; infra subnet must be /23 or larger.

@description('Azure region.')
param location string

@description('Resource name prefix (3-12 lowercase alphanumeric).')
param namePrefix string

@description('VNet CIDR (e.g. 10.40.0.0/20).')
param vnetAddressPrefix string

@description('Subnet for the Container Apps managed environment. Minimum /23 for Consumption-only.')
param infraSubnetPrefix string

@description('Subnet for private endpoints (ACR, etc).')
param peSubnetPrefix string

@description('Resource tags.')
param tags object

resource nsgInfra 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${namePrefix}-infra-nsg'
  location: location
  tags: tags
  properties: {
    // Container Apps manages east-west traffic via its environment; leave NSG open
    // by default and tighten with explicit deny rules from your hub firewall policy.
    securityRules: []
  }
}

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2023-11-01' = {
  name: '${namePrefix}-pe-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'Allow-VNet-HTTPS-Inbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '443'
        }
      }
      {
        name: 'Deny-Internet-Inbound'
        properties: {
          priority: 4000
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-11-01' = {
  name: '${namePrefix}-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'infrastructure'
        properties: {
          addressPrefix: infraSubnetPrefix
          networkSecurityGroup: {
            id: nsgInfra.id
          }
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: peSubnetPrefix
          networkSecurityGroup: {
            id: nsgPe.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output infraSubnetId string = '${vnet.id}/subnets/infrastructure'
output peSubnetId string = '${vnet.id}/subnets/private-endpoints'
