// One Container App with a user-assigned managed identity granted AcrPull on the registry.
// AcrPull role assignment happens here so each app can be deployed independently.

@description('Azure region.')
param location string

@description('Container App resource name.')
param name string

@description('Managed environment resource ID.')
param environmentId string

@description('ACR resource ID (must be in the same resource group as this deployment).')
param acrId string

@description('ACR login server (e.g. myacr.azurecr.us).')
param acrLoginServer string

@description('Full image reference, e.g. myacr.azurecr.us/frontend:tag.')
param image string

@description('Container target port.')
param targetPort int

@description('External ingress. In an internal env, true = reachable from the VNet, false = only reachable from inside the env.')
param ingressExternal bool = false

@description('CPU as a string like "0.5", "1.0".')
param cpu string = '0.5'

@description('Memory as a quantity like "1.0Gi", "2.0Gi". Must align with the CPU tier.')
param memory string = '1.0Gi'

@description('Min replica count.')
param minReplicas int = 1

@description('Max replica count.')
param maxReplicas int = 3

@description('Plain environment variables. Items: { name, value }.')
param envVars array = []

@description('Secrets to register on the Container App. Must be { items: [ { name, value }, ... ] }; pass { items: [] } if none.')
@secure()
param secrets object

@description('Env vars sourced from secrets. Items: { name, secretRef }.')
param secretEnvVars array = []

@description('Resource tags.')
param tags object

@description('Managed Identity resource ID (optional - will create new if not provided)')
param managedIdentityId string = ''

@description('Application Insights connection string (optional)')
param appInsightsConnectionString string = ''

@description('Wire the ACR into the container app `registries` config (required for private ACR pulls; set false when using a public registry like mcr.microsoft.com).')
param useAcrRegistry bool = true

var shouldCreateManagedIdentity = empty(managedIdentityId)

// Create new managed identity if not provided
resource newManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (shouldCreateManagedIdentity) {
  name: '${name}-mi'
  location: location
  tags: tags
}

// Reference existing managed identity if provided. Accepts a full resource ID or a bare name in the current RG.
var managedIdentityIdParts = split(managedIdentityId, '/')
var managedIdentityIsFullId = length(managedIdentityIdParts) >= 9
var existingManagedIdentityName = managedIdentityIsFullId ? last(managedIdentityIdParts) : managedIdentityId
var existingManagedIdentitySubscriptionId = managedIdentityIsFullId ? managedIdentityIdParts[2] : subscription().subscriptionId
var existingManagedIdentityResourceGroup = managedIdentityIsFullId ? managedIdentityIdParts[4] : resourceGroup().name

resource existingManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = if (!shouldCreateManagedIdentity) {
  name: existingManagedIdentityName
  scope: resourceGroup(existingManagedIdentitySubscriptionId, existingManagedIdentityResourceGroup)
}

// Use the appropriate managed identity
var actualManagedIdentityId = shouldCreateManagedIdentity ? newManagedIdentity.id : existingManagedIdentity.id
var actualManagedIdentityPrincipalId = shouldCreateManagedIdentity ? newManagedIdentity.properties.principalId : existingManagedIdentity.properties.principalId

// Note: RBAC assignments (including AcrPull) must be configured outside BICEP
// See RELEASE.md for required role assignments

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${actualManagedIdentityId}': {}
    }
  }
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: ingressExternal
        targetPort: targetPort
        transport: 'auto'
        allowInsecure: false
        traffic: [
          {
            weight: 100
            latestRevision: true
          }
        ]
      }
      registries: useAcrRegistry ? [
        {
          server: acrLoginServer
          identity: actualManagedIdentityId
        }
      ] : []
      secrets: secrets.items
      dapr: !empty(appInsightsConnectionString) ? {
        enabled: false
      } : null
    }
    template: {
      containers: [
        {
          name: name
          image: image
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: concat(envVars, secretEnvVars, !empty(appInsightsConnectionString) ? [
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionString
            }
          ] : [])
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppId string = containerApp.id
output identityPrincipalId string = actualManagedIdentityPrincipalId
output managedIdentityId string = actualManagedIdentityId
