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

@description('Secrets to register on the Container App. Items: { name, value } (value is @secure on the parent).')
@secure()
param secrets object = {
  items: []
}

@description('Env vars sourced from secrets. Items: { name, secretRef }.')
param secretEnvVars array = []

@description('Resource tags.')
param tags object

var acrPullRoleDefinitionId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${name}-mi'
  location: location
  tags: tags
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: last(split(acrId, '/'))
}

resource acrPullAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, managedIdentity.id, acrPullRoleDefinitionId)
  properties: {
    principalId: managedIdentity.properties.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleDefinitionId)
    principalType: 'ServicePrincipal'
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
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
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentity.id
        }
      ]
      secrets: secrets.items
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
          env: concat(envVars, secretEnvVars)
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
      }
    }
  }
  dependsOn: [
    acrPullAssignment
  ]
}

output fqdn string = containerApp.properties.configuration.ingress.fqdn
output containerAppId string = containerApp.id
output identityPrincipalId string = managedIdentity.properties.principalId
