// Container Apps managed environment, VNet-injected, internal-only ingress.
// Consumption-only (no workload profiles). Reads Log Analytics keys via existing reference,
// so the workspace must live in the same resource group.

@description('Azure region.')
param location string

@description('Managed environment resource name.')
param name string

@description('Subnet ID for environment infrastructure. Must be /23 or larger for Consumption-only.')
param infrastructureSubnetId string

@description('Log Analytics workspace resource ID.')
param logAnalyticsWorkspaceId string

@description('Resource tags.')
param tags object

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: last(split(logAnalyticsWorkspaceId, '/'))
  scope: resourceGroup(split(logAnalyticsWorkspaceId, '/')[4])
}

// TODO: check this again the logAnalyticsConfiguration 
resource managedEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: infrastructureSubnetId
      internal: true
    }
    zoneRedundant: false
  }
}

output environmentId string = managedEnv.id
output defaultDomain string = managedEnv.properties.defaultDomain
output staticIp string = managedEnv.properties.staticIp
