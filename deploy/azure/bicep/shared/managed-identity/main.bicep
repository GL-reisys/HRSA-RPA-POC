@description('Managed Identity: For new identity provide name, for existing identity provide full resource ID')
param managedIdentity string

@description('Set to true to reference an existing Managed Identity, false to create new')
param useExisting bool = false

@description('Location for the Managed Identity (only used when creating new)')
param location string = resourceGroup().location

@description('Tags to apply to the Managed Identity (only used when creating new)')
param tags object = {}

// For new identity: use the name as-is
// For existing identity: extract name from resource ID
var identityName = useExisting ? last(split(managedIdentity, '/')) : managedIdentity
var identityResourceGroup = useExisting ? split(managedIdentity, '/')[4] : ''

// Create new MI when useExisting = false
resource newManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (!useExisting) {
  name: identityName
  location: location
  tags: tags
}

// Reference existing MI when useExisting = true
resource existingManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = if (useExisting) {
  name: identityName
  scope: resourceGroup(identityResourceGroup)
}

// Outputs - Return MI details for downstream deployments
output managedIdentityId string = useExisting ? existingManagedIdentity!.id : newManagedIdentity!.id
output managedIdentityPrincipalId string = useExisting ? existingManagedIdentity!.properties.principalId : newManagedIdentity!.properties.principalId
output managedIdentityClientId string = useExisting ? existingManagedIdentity!.properties.clientId : newManagedIdentity!.properties.clientId
