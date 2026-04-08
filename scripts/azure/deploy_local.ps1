param(
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

function Write-Usage {
    @"
Usage:
  powershell -ExecutionPolicy Bypass -File scripts/azure/deploy_local.ps1 [-EnvFile path]

Description:
  Builds linux/amd64 frontend and backend images, pushes them to Azure Container Registry,
  renders the Azure Container Instance manifest, and deploys the container group.

Defaults:
  If -EnvFile is not supplied, the script looks for scripts/azure/local.env.
"@
}

if ($EnvFile -eq "-h" -or $EnvFile -eq "--help") {
    Write-Usage
    exit 0
}

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $ScriptDir "local.env"
}

if (-not (Test-Path $EnvFile)) {
    Write-Error "Environment file not found: $EnvFile`nCopy scripts/azure/local.env.example to scripts/azure/local.env and fill in the values."
}

function Import-DotEnv {
    param([string]$Path)

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }

        $parts = $line -split "=", 2
        if ($parts.Length -ne 2) {
            return
        }

        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        [Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is required."
    }
}

function Require-Env {
    param([string]$Name)

    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required variable in $EnvFile: $Name"
    }

    return $value
}

Import-DotEnv -Path $EnvFile

Require-Command -Name "az"
Require-Command -Name "docker"
Require-Command -Name "python"

$requiredVars = @(
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_RESOURCE_GROUP",
    "AZURE_LOCATION",
    "AZURE_ACR_NAME",
    "AZURE_ACR_LOGIN_SERVER",
    "AZURE_CONTAINER_GROUP_NAME",
    "AZURE_DNS_LABEL"
)

foreach ($varName in $requiredVars) {
    [void](Require-Env -Name $varName)
}

if (-not [Environment]::GetEnvironmentVariable("FRONTEND_IMAGE_TAG", "Process")) {
    [Environment]::SetEnvironmentVariable("FRONTEND_IMAGE_TAG", "manual-amd64", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("BACKEND_IMAGE_TAG", "Process")) {
    [Environment]::SetEnvironmentVariable("BACKEND_IMAGE_TAG", "manual-amd64", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("FRONTEND_CPU", "Process")) {
    [Environment]::SetEnvironmentVariable("FRONTEND_CPU", "0.5", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("FRONTEND_MEMORY_GB", "Process")) {
    [Environment]::SetEnvironmentVariable("FRONTEND_MEMORY_GB", "1.0", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("BACKEND_CPU", "Process")) {
    [Environment]::SetEnvironmentVariable("BACKEND_CPU", "0.5", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("BACKEND_MEMORY_GB", "Process")) {
    [Environment]::SetEnvironmentVariable("BACKEND_MEMORY_GB", "1.0", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("API_INTERNAL_URL", "Process")) {
    [Environment]::SetEnvironmentVariable("API_INTERNAL_URL", "http://127.0.0.1:5000", "Process")
}

$azureLocation = [Environment]::GetEnvironmentVariable("AZURE_LOCATION", "Process")
$azureDnsLabel = [Environment]::GetEnvironmentVariable("AZURE_DNS_LABEL", "Process")

if (-not [Environment]::GetEnvironmentVariable("CORS_ALLOWED_ORIGINS", "Process")) {
    $defaultOrigins = "http://localhost:3000,http://127.0.0.1:3000,http://$azureDnsLabel.$azureLocation.azurecontainer.io:3000"
    [Environment]::SetEnvironmentVariable("CORS_ALLOWED_ORIGINS", $defaultOrigins, "Process")
}

$tempManifestPath = Join-Path ([System.IO.Path]::GetTempPath()) "hrsa-rpa-ava-aci.yaml"
if (-not [Environment]::GetEnvironmentVariable("ACI_MANIFEST_PATH", "Process")) {
    [Environment]::SetEnvironmentVariable("ACI_MANIFEST_PATH", $tempManifestPath, "Process")
}

$acrLoginServer = [Environment]::GetEnvironmentVariable("AZURE_ACR_LOGIN_SERVER", "Process")
$frontendTag = [Environment]::GetEnvironmentVariable("FRONTEND_IMAGE_TAG", "Process")
$backendTag = [Environment]::GetEnvironmentVariable("BACKEND_IMAGE_TAG", "Process")

if (-not [Environment]::GetEnvironmentVariable("FRONTEND_IMAGE", "Process")) {
    [Environment]::SetEnvironmentVariable("FRONTEND_IMAGE", "$acrLoginServer/hrsa-rpa-ava-frontend:$frontendTag", "Process")
}
if (-not [Environment]::GetEnvironmentVariable("BACKEND_IMAGE", "Process")) {
    [Environment]::SetEnvironmentVariable("BACKEND_IMAGE", "$acrLoginServer/hrsa-rpa-ava-backend:$backendTag", "Process")
}

$activeSubscription = az account show --query id -o tsv
$expectedSubscription = [Environment]::GetEnvironmentVariable("AZURE_SUBSCRIPTION_ID", "Process")
if ($activeSubscription.Trim() -ne $expectedSubscription.Trim()) {
    throw "Azure CLI is logged into subscription $activeSubscription, expected $expectedSubscription. Run: az account set --subscription $expectedSubscription"
}

$acrName = [Environment]::GetEnvironmentVariable("AZURE_ACR_NAME", "Process")
az acr login --name $acrName | Out-Null

if (-not [Environment]::GetEnvironmentVariable("AZURE_ACR_USERNAME", "Process")) {
    $acrUsername = az acr credential show --name $acrName --query username -o tsv
    [Environment]::SetEnvironmentVariable("AZURE_ACR_USERNAME", $acrUsername.Trim(), "Process")
}

if (-not [Environment]::GetEnvironmentVariable("AZURE_ACR_PASSWORD", "Process")) {
    $acrPassword = az acr credential show --name $acrName --query "passwords[0].value" -o tsv
    [Environment]::SetEnvironmentVariable("AZURE_ACR_PASSWORD", $acrPassword.Trim(), "Process")
}

$backendImage = [Environment]::GetEnvironmentVariable("BACKEND_IMAGE", "Process")
$frontendImage = [Environment]::GetEnvironmentVariable("FRONTEND_IMAGE", "Process")
$apiInternalUrl = [Environment]::GetEnvironmentVariable("API_INTERNAL_URL", "Process")
$aciManifestPath = [Environment]::GetEnvironmentVariable("ACI_MANIFEST_PATH", "Process")

Write-Host "Building backend image: $backendImage"
docker buildx build `
    --platform linux/amd64 `
    --tag $backendImage `
    --push `
    (Join-Path $RepoRoot "RPA-POC-AVA-app/backend")

Write-Host "Building frontend image: $frontendImage"
docker buildx build `
    --platform linux/amd64 `
    --build-arg "API_INTERNAL_URL=$apiInternalUrl" `
    --tag $frontendImage `
    --push `
    (Join-Path $RepoRoot "RPA-POC-AVA-app/frontend")

Write-Host "Rendering ACI manifest to $aciManifestPath"
python (Join-Path $ScriptDir "render_aci_manifest.py") `
    --template (Join-Path $RepoRoot "deploy/azure/aci-container-group.yaml.template") `
    --output $aciManifestPath

Write-Host "Deploying Azure Container Instance $([Environment]::GetEnvironmentVariable('AZURE_CONTAINER_GROUP_NAME', 'Process'))"
az account set --subscription $expectedSubscription | Out-Null

$resourceGroup = [Environment]::GetEnvironmentVariable("AZURE_RESOURCE_GROUP", "Process")
$containerGroupName = [Environment]::GetEnvironmentVariable("AZURE_CONTAINER_GROUP_NAME", "Process")

$existingManifestPath = $null
$existingManifestExported = $false
$newContainerCreated = $false

try {
    az container show --resource-group $resourceGroup --name $containerGroupName --only-show-errors | Out-Null
    $existingManifestPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "aci-backup-$([System.Guid]::NewGuid()).yaml")
    az container export --resource-group $resourceGroup --name $containerGroupName --file $existingManifestPath --only-show-errors | Out-Null
    $existingManifestExported = $true

    Write-Host "Replacing existing container group $containerGroupName in $resourceGroup."
    az container delete --resource-group $resourceGroup --name $containerGroupName --yes --only-show-errors | Out-Null

    for ($i = 0; $i -lt 30; $i++) {
        try {
            az container show --resource-group $resourceGroup --name $containerGroupName --only-show-errors | Out-Null
            Start-Sleep -Seconds 10
        }
        catch {
            break
        }
    }
}
catch {
}

try {
    az container create --resource-group $resourceGroup --file $aciManifestPath --only-show-errors | Out-Null
    $newContainerCreated = $true

    for ($i = 0; $i -lt 30; $i++) {
        $state = az container show --resource-group $resourceGroup --name $containerGroupName --query instanceView.state -o tsv
        if ($state.Trim() -eq "Running") {
            $newContainerCreated = $false
            break
        }
        Start-Sleep -Seconds 10
    }

    $finalState = az container show --resource-group $resourceGroup --name $containerGroupName --query instanceView.state -o tsv
    if ($finalState.Trim() -ne "Running") {
        throw "Container group $containerGroupName failed to reach Running state. Final state: $finalState"
    }
}
catch {
    if ($newContainerCreated) {
        try {
            az container delete --resource-group $resourceGroup --name $containerGroupName --yes --only-show-errors | Out-Null
        }
        catch {
        }
    }

    if ($existingManifestExported -and $existingManifestPath -and (Test-Path $existingManifestPath)) {
        Write-Warning "Restoring previous container group definition for $containerGroupName."
        az container create --resource-group $resourceGroup --file $existingManifestPath --only-show-errors | Out-Null
    }

    throw
}

$fqdn = az container show --resource-group $resourceGroup --name $containerGroupName --query ipAddress.fqdn -o tsv
Write-Host "Deployment completed."
Write-Host "Frontend URL: http://$fqdn:3000"

