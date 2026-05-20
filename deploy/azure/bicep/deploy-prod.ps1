<#
.SYNOPSIS
    One-shot production deployment of the HRSA-RPA-AVA stack (PowerShell).

.DESCRIPTION
    PowerShell equivalent of deploy-prod.sh — intended for Octopus Windows workers.
    Octopus invokes this AFTER it has already:
      1. Pulled the Docker TAR from Azure DevOps
      2. Loaded the image
      3. Pushed the image to ACR

    It does everything else: preflight checks, Bicep deploy, post-deploy RBAC
    and private DNS wiring, and final verification.

.NOTES
    Octopus token substitution runs on this file BEFORE PowerShell parses it,
    so the literal `#{...}` tokens are replaced with their variable values.
    For standalone use, set the corresponding env vars (see .EXAMPLE).

.EXAMPLE
    # Standalone manual run (PowerShell 7+):
    $env:SUBSCRIPTION             = '<sub-id>'
    $env:RESOURCE_GROUP           = 'RG-HRSA-RPA-AVA-PRIV'
    $env:LOCATION                 = 'usgovvirginia'
    $env:REGION_ABBR              = 'usgv'
    $env:DEPLOYMENT_ENVIRONMENT   = 'dev'        # 2-3 chars
    $env:ENVIRONMENT_NAME         = 'dev'
    $env:INFRA_SUBNET_ID          = '/subscriptions/.../subnets/snet-aca-infra'
    $env:PE_SUBNET_ID             = '/subscriptions/.../subnets/snet-aca-pe'
    $env:LAW_ID                   = '/subscriptions/.../workspaces/log-...'
    $env:ACR_LOGIN_SERVER         = 'creusdgpsehbssecrpa.azurecr.us'
    $env:FRONTEND_IMAGE_TAG       = 'latest'
    $env:BACKEND_IMAGE_TAG        = 'latest'
    $env:AZURE_OPENAI_ENDPOINT    = 'https://...openai.azure.us/'
    $env:AZURE_OPENAI_API_KEY     = '<secret>'
    $env:AZURE_OPENAI_DEPLOYMENT  = 'gpt-4'
    $env:PEERED_VNET_IDS          = '<vnet-id-1> <vnet-id-2>'   # optional, space-separated
    ./deploy-prod.ps1

.OUTPUTS
    Exit codes:
      0 — deploy succeeded
      1 — preflight failure
      2 — bicep deploy failed
      3 — post-deploy step failed (deploy itself was OK, follow-ups need attention)
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # keep `az` output clean

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
function Write-Section { param([string]$Msg) Write-Host ""; Write-Host "=== $Msg ===" -ForegroundColor Cyan }
function Fail { param([string]$Msg, [int]$Code = 1) Write-Host "ERROR: $Msg" -ForegroundColor Red; exit $Code }

# Resolve an Octopus token or env var. Treats unsubstituted `#{...}` as missing.
function Resolve-Input {
    param([string]$Name, [string]$OctopusValue)
    $envVal = [Environment]::GetEnvironmentVariable($Name)
    if ($envVal) { return $envVal }
    if ($OctopusValue -and -not $OctopusValue.StartsWith('#{')) { return $OctopusValue }
    return $null
}

function Require-Input {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { Fail "Missing required input: $Name" 1 }
}

# Run `az` and return parsed JSON. Throws on non-zero exit.
function Invoke-AzJson {
    param([Parameter(ValueFromRemainingArguments)]$Args)
    $raw = & az @Args 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "az $($Args -join ' ') failed:`n$raw"
    }
    if ([string]::IsNullOrWhiteSpace($raw)) { return $null }
    return ($raw | Out-String | ConvertFrom-Json)
}

# Run `az` without parsing JSON (for commands that don't return JSON).
function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments)]$Args)
    & az @Args 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "az $($Args -join ' ') failed (exit $LASTEXITCODE)" }
}

# -----------------------------------------------------------------------------
# Inputs — Octopus tokens fall through to env vars.
# -----------------------------------------------------------------------------
$Subscription            = Resolve-Input 'SUBSCRIPTION'             '#{Subscription}'
$ResourceGroup           = Resolve-Input 'RESOURCE_GROUP'           '#{ResourceGroup}'
$Location                = Resolve-Input 'LOCATION'                 '#{Location}'
$RegionAbbr              = Resolve-Input 'REGION_ABBR'              '#{RegionAbbr}'
$DeploymentEnvironment   = Resolve-Input 'DEPLOYMENT_ENVIRONMENT'   '#{DeploymentEnvironment}'
$EnvironmentName         = Resolve-Input 'ENVIRONMENT_NAME'         '#{environmentName}'

$InfraSubnetId           = Resolve-Input 'INFRA_SUBNET_ID'          '#{InfrastructureSubnetId}'
$PeSubnetId              = Resolve-Input 'PE_SUBNET_ID'             '#{PrivateEndpointSubnetId}'
$LawId                   = Resolve-Input 'LAW_ID'                   '#{LogAnalyticsWorkspaceId}'

$AcrLoginServer          = Resolve-Input 'ACR_LOGIN_SERVER'         '#{AcrLoginServer}'
$FrontendImageTag        = Resolve-Input 'FRONTEND_IMAGE_TAG'       '#{FrontendImageTag}'
$BackendImageTag         = Resolve-Input 'BACKEND_IMAGE_TAG'        '#{BackendImageTag}'

$AzureOpenAiEndpoint     = Resolve-Input 'AZURE_OPENAI_ENDPOINT'    '#{AzureOpenAiEndpoint}'
$AzureOpenAiApiKey       = Resolve-Input 'AZURE_OPENAI_API_KEY'     '#{AzureOpenAiApiKey}'
$AzureOpenAiDeployment   = Resolve-Input 'AZURE_OPENAI_DEPLOYMENT'  '#{AzureOpenAiDeployment}'

$CorsAllowedOrigins      = Resolve-Input 'CORS_ALLOWED_ORIGINS'     ''
$PeeredVnetIds           = Resolve-Input 'PEERED_VNET_IDS'          ''

# Image references (Octopus pushed these tags already).
$FrontendImage = "$AcrLoginServer/ehbs-$EnvironmentName-ui:$FrontendImageTag"
$BackendImage  = "$AcrLoginServer/ehbs-$EnvironmentName-svc:$BackendImageTag"

$ScriptDir      = $PSScriptRoot
$Timestamp      = (Get-Date -AsUTC -Format 'yyyyMMddHHmmss')
$DeploymentName = "hrsa-rpa-ava-$DeploymentEnvironment-$Timestamp"

# -----------------------------------------------------------------------------
# Preflight
# -----------------------------------------------------------------------------
Write-Section 'Preflight: required inputs'
@(
    @{ Name='SUBSCRIPTION';            Value=$Subscription }
    @{ Name='RESOURCE_GROUP';          Value=$ResourceGroup }
    @{ Name='LOCATION';                Value=$Location }
    @{ Name='REGION_ABBR';             Value=$RegionAbbr }
    @{ Name='DEPLOYMENT_ENVIRONMENT';  Value=$DeploymentEnvironment }
    @{ Name='ENVIRONMENT_NAME';        Value=$EnvironmentName }
    @{ Name='INFRA_SUBNET_ID';         Value=$InfraSubnetId }
    @{ Name='PE_SUBNET_ID';            Value=$PeSubnetId }
    @{ Name='LAW_ID';                  Value=$LawId }
    @{ Name='ACR_LOGIN_SERVER';        Value=$AcrLoginServer }
    @{ Name='FRONTEND_IMAGE_TAG';      Value=$FrontendImageTag }
    @{ Name='BACKEND_IMAGE_TAG';       Value=$BackendImageTag }
    @{ Name='AZURE_OPENAI_ENDPOINT';   Value=$AzureOpenAiEndpoint }
    @{ Name='AZURE_OPENAI_API_KEY';    Value=$AzureOpenAiApiKey }
    @{ Name='AZURE_OPENAI_DEPLOYMENT'; Value=$AzureOpenAiDeployment }
) | ForEach-Object { Require-Input $_.Name $_.Value }

# Container app name length check (32-char limit)
$AppNamePrefix = "ca-$RegionAbbr-dgps-ehbs-$DeploymentEnvironment-rpa"
foreach ($suffix in @('-ui', '-svc')) {
    $full = "$AppNamePrefix$suffix"
    if ($full.Length -gt 32) {
        Fail "Container app name '$full' is $($full.Length) chars (limit 32). Shorten DEPLOYMENT_ENVIRONMENT or REGION_ABBR." 1
    }
}
Write-Host "  Container app names: $AppNamePrefix-ui, $AppNamePrefix-svc — within limit."

Write-Section 'Preflight: Azure CLI session'
try {
    $acct = Invoke-AzJson account show
    Write-Host "  Signed in as: $($acct.user.name) ($($acct.user.type))"
    Write-Host "  Subscription: $($acct.name) ($($acct.id))"
} catch {
    Fail "Not logged in. Run 'az login' first." 1
}
Invoke-Az account set --subscription $Subscription | Out-Null

$activeCloud = (Invoke-AzJson cloud show --query name -o json)
if ($Location -like 'usgov*' -and $activeCloud -ne 'AzureUSGovernment') {
    Fail "LOCATION=$Location (Gov region) but active cloud is $activeCloud. Run: az cloud set --name AzureUSGovernment && az login" 1
}
Write-Host "  Active cloud: $activeCloud"

Write-Section 'Preflight: resource providers'
foreach ($ns in 'Microsoft.App', 'Microsoft.OperationalInsights', 'Microsoft.ContainerRegistry',
                'Microsoft.Network', 'Microsoft.Insights', 'Microsoft.ManagedIdentity') {
    $state = (& az provider show --namespace $ns --query registrationState -o tsv 2>$null)
    if ($state -ne 'Registered') {
        Write-Host "  Registering $ns..."
        & az provider register --namespace $ns --wait | Out-Null
    }
}

Write-Section 'Preflight: subnet validation'
try {
    $infraPrefix = (Invoke-AzJson network vnet subnet show --ids $InfraSubnetId `
                    --query "addressPrefix || addressPrefixes[0]")
    $infraDelegation = (Invoke-AzJson network vnet subnet show --ids $InfraSubnetId `
                    --query "delegations[0].serviceName")
} catch { Fail "infrastructureSubnetId '$InfraSubnetId' not found" 1 }
if ($infraDelegation -ne 'Microsoft.App/environments') {
    Fail "infrastructure subnet must be delegated to Microsoft.App/environments (got: '$infraDelegation')" 1
}
$prefixSize = [int]($infraPrefix -split '/')[-1]
if ($prefixSize -gt 23) {
    Fail "infrastructure subnet $infraPrefix is smaller than /23 (Container Apps requires /23 minimum)" 1
}
Write-Host "  infra subnet: $infraPrefix, delegated $infraDelegation OK"

try {
    $pePrefix = (Invoke-AzJson network vnet subnet show --ids $PeSubnetId `
                  --query "addressPrefix || addressPrefixes[0]")
} catch { Fail "privateEndpointSubnetId '$PeSubnetId' not found" 1 }
Write-Host "  PE subnet:    $pePrefix OK"

# -----------------------------------------------------------------------------
# Bicep deploy
# -----------------------------------------------------------------------------
$BicepParams = @(
    "location=$Location"
    "regionAbbr=$RegionAbbr"
    "deploymentEnvironment=$DeploymentEnvironment"
    "environmentName=$EnvironmentName"
    "logAnalyticsWorkspaceId=$LawId"
    "infrastructureSubnetId=$InfraSubnetId"
    "privateEndpointSubnetId=$PeSubnetId"
    "frontendImage=$FrontendImage"
    "backendImage=$BackendImage"
    "azureOpenAiEndpoint=$AzureOpenAiEndpoint"
    "azureOpenAiDeployment=$AzureOpenAiDeployment"
    "corsAllowedOrigins=$CorsAllowedOrigins"
)

Write-Section 'Validating Bicep template'
try {
    Invoke-AzJson deployment group validate `
        --resource-group $ResourceGroup `
        --template-file (Join-Path $ScriptDir 'main.bicep') `
        --parameters @BicepParams | Out-Null
    Write-Host '  validate passed.'
} catch { Fail "validate failed: $_" 2 }

Write-Section 'What-if preview'
& az deployment group what-if `
    --resource-group $ResourceGroup `
    --template-file (Join-Path $ScriptDir 'main.bicep') `
    --parameters @BicepParams `
    --no-pretty-print `
    --result-format ResourceIdOnly 2>$null | Select-String -Pattern '^\s*[+~\-]' | ForEach-Object { Write-Host $_.Line }

Write-Section "Deploying $DeploymentName"
try {
    $deployOut = Invoke-AzJson deployment group create `
        --resource-group $ResourceGroup `
        --name $DeploymentName `
        --template-file (Join-Path $ScriptDir 'main.bicep') `
        --parameters @BicepParams `
        --query properties.outputs
} catch { Fail "deploy failed: $_" 2 }

$deployOut.PSObject.Properties | ForEach-Object { Write-Host "  $($_.Name): $($_.Value.value)" }

# -----------------------------------------------------------------------------
# Post-deploy — RBAC + private DNS + verification
# -----------------------------------------------------------------------------
$MiId            = $deployOut.managedIdentityId.value
$MiPrincipalId   = $deployOut.managedIdentityPrincipalId.value
$AcrId           = $deployOut.acrId.value
$CaeDomain       = $deployOut.containerAppsEnvironmentDefaultDomain.value
$CaeStaticIp     = $deployOut.containerAppsEnvironmentStaticIp.value
$FeFqdn          = $deployOut.frontendFqdn.value
$BeFqdn          = $deployOut.backendFqdn.value
$FeName          = $FeFqdn.Split('.')[0]
$BeName          = $BeFqdn.Split('.')[0]

$PostFailed = $false

Write-Section 'Granting AcrPull to managed identity'
$existing = & az role assignment list --assignee $MiPrincipalId --scope $AcrId --role AcrPull --query "[0].id" -o tsv 2>$null
if ($existing) {
    Write-Host '  AcrPull already in place.'
} else {
    & az role assignment create `
        --assignee-object-id $MiPrincipalId `
        --assignee-principal-type ServicePrincipal `
        --role AcrPull --scope $AcrId 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host '  AcrPull granted.'
    } else {
        Write-Host '  WARNING: AcrPull grant failed (likely RBAC). Have a User Access Administrator run:' -ForegroundColor Yellow
        Write-Host "    az role assignment create ``" -ForegroundColor Yellow
        Write-Host "      --assignee-object-id $MiPrincipalId ``" -ForegroundColor Yellow
        Write-Host "      --assignee-principal-type ServicePrincipal ``" -ForegroundColor Yellow
        Write-Host "      --role AcrPull ``" -ForegroundColor Yellow
        Write-Host "      --scope $AcrId" -ForegroundColor Yellow
        $PostFailed = $true
    }
}

Write-Section 'Provisioning private DNS zone for ACA env'
$DnsZoneRg = $ResourceGroup
$zoneExists = & az network private-dns zone show -g $DnsZoneRg -n $CaeDomain --query name -o tsv 2>$null
if (-not $zoneExists) {
    & az network private-dns zone create -g $DnsZoneRg -n $CaeDomain 2>$null | Out-Null
    Write-Host "  Zone $CaeDomain created."
} else {
    Write-Host "  Zone $CaeDomain already exists."
}

# Wildcard A record → env static IP
& az network private-dns record-set a delete -g $DnsZoneRg -z $CaeDomain -n '*' --yes 2>$null | Out-Null
& az network private-dns record-set a create -g $DnsZoneRg -z $CaeDomain -n '*' --ttl 3600 2>$null | Out-Null
& az network private-dns record-set a add-record -g $DnsZoneRg -z $CaeDomain -n '*' -a $CaeStaticIp 2>$null | Out-Null
Write-Host "  Wildcard A -> $CaeStaticIp."

# Link to deploy VNet
$deployVnetId = (& az network vnet subnet show --ids $InfraSubnetId --query id -o tsv) -split '/subnets/' | Select-Object -First 1
$deployVnetName = $deployVnetId.Split('/')[-1]
$deployLink = "link-$deployVnetName"
$linkExists = & az network private-dns link vnet show -g $DnsZoneRg -z $CaeDomain -n $deployLink --query name -o tsv 2>$null
if (-not $linkExists) {
    & az network private-dns link vnet create `
        -g $DnsZoneRg -z $CaeDomain -n $deployLink `
        --virtual-network $deployVnetId --registration-enabled false 2>$null | Out-Null
    Write-Host "  Linked deploy VNet ($deployVnetName)."
} else {
    Write-Host '  Deploy VNet already linked.'
}

# Link to peered VNets (EHB Web / EHB DB per OIT)
if ($PeeredVnetIds) {
    foreach ($peer in $PeeredVnetIds.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)) {
        $pName = $peer.Split('/')[-1]
        $pLink = "link-$pName"
        $exists = & az network private-dns link vnet show -g $DnsZoneRg -z $CaeDomain -n $pLink --query name -o tsv 2>$null
        if (-not $exists) {
            & az network private-dns link vnet create `
                -g $DnsZoneRg -z $CaeDomain -n $pLink `
                --virtual-network $peer --registration-enabled false 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Linked peered VNet ($pName)."
            } else {
                Write-Host "  WARNING: failed to link $pName (cross-sub peerings may need permissions in the target sub)" -ForegroundColor Yellow
                $PostFailed = $true
            }
        }
    }
} else {
    Write-Host '  PEERED_VNET_IDS empty — only the deploy VNet was linked. EHB Web/DB users will not resolve the FQDN until linked.' -ForegroundColor Yellow
}

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
Write-Section 'Verification'
Write-Host "  Deployment:     $DeploymentName"
Write-Host "  ACA env domain: $CaeDomain"
Write-Host "  Env static IP:  $CaeStaticIp"
Write-Host "  Frontend FQDN:  $FeFqdn"
Write-Host "  Backend FQDN:   $BeFqdn"
Write-Host "  ACR:            $AcrLoginServer"
Write-Host "  Images:         $FrontendImage"
Write-Host "                  $BackendImage"

foreach ($app in @($FeName, $BeName)) {
    $healthy = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $state  = & az containerapp show -g $ResourceGroup -n $app --query "properties.runningStatus" -o tsv 2>$null
        $health = & az containerapp revision list -g $ResourceGroup -n $app --query "[?properties.active] | [0].properties.healthState" -o tsv 2>$null
        if ($state -eq 'Running' -and $health -eq 'Healthy') {
            Write-Host "  $app — Running / Healthy"
            $healthy = $true
            break
        }
        Start-Sleep -Seconds 10
    }
    if (-not $healthy) {
        Write-Host "  WARNING: $app not Healthy after 5 min (state=$state health=$health)" -ForegroundColor Yellow
        $PostFailed = $true
    }
}

if ($PostFailed) { exit 3 }

Write-Section 'Deployment complete.'
