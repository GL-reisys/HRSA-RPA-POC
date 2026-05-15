@description('Name of the Application Insights instance')
param applicationInsightsName string

@description('Location for the Application Insights')
param location string

@description('Application type')
@allowed([
  'web'
  'other'
])
param applicationType string = 'web'

@description('Log Analytics workspace ID')
param workspaceId string

@description('Retention period in days')
@minValue(30)
@maxValue(730)
param retentionInDays int = 90

@description('Public network access for ingestion')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccessForIngestion string = 'Enabled'

@description('Public network access for query')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccessForQuery string = 'Enabled'

@description('Tags to apply to resources')
param tags object = {}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: location
  tags: tags
  kind: applicationType
  properties: {
    Application_Type: applicationType
    WorkspaceResourceId: workspaceId
    RetentionInDays: retentionInDays
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: publicNetworkAccessForIngestion
    publicNetworkAccessForQuery: publicNetworkAccessForQuery
  }
}

output applicationInsightsId string = applicationInsights.id
output applicationInsightsName string = applicationInsights.name
output instrumentationKey string = applicationInsights.properties.InstrumentationKey
output connectionString string = applicationInsights.properties.ConnectionString
