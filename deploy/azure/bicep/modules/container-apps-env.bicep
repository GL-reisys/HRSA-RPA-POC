// Container Apps managed environment, VNet-injected, internal-only ingress.
// Consumption-only (no workload profiles). Reads Log Analytics keys via existing reference,
// so the workspace must live in the same resource group.

@description('Azure region.')
param location string

@description('Managed environment resource name.')
param name string

@description('Subnet ID for environment infrastructure. Must be /23 or larger for Consumption-only.')
param infrastructureSubnetId string

@description('Log Analytics workspace. Accepts a full resource ID (/subscriptions/.../workspaces/<name>) or a bare workspace name in the current resource group.')
param logAnalyticsWorkspaceId string

@description('Resource tags.')
param tags object

var workspaceIdParts = split(logAnalyticsWorkspaceId, '/')
var workspaceIsFullId = length(workspaceIdParts) >= 9
var workspaceName = workspaceIsFullId ? last(workspaceIdParts) : logAnalyticsWorkspaceId
var workspaceSubscriptionId = workspaceIsFullId ? workspaceIdParts[2] : subscription().subscriptionId
var workspaceResourceGroup = workspaceIsFullId ? workspaceIdParts[4] : resourceGroup().name

resource workspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: workspaceName
  scope: resourceGroup(workspaceSubscriptionId, workspaceResourceGroup)
}

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
