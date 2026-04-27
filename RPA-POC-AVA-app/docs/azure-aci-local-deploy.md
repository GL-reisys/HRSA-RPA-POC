# Manual Azure Container Instance Deployment

This guide is for developers who want to deploy the app to Azure Container Instance directly from a local machine instead of using GitHub Actions.

## When to use this path

Use this path when:

- you have Azure Contributor access to the target resource group
- you can build and push Docker images from your machine
- you do not have permission to configure GitHub repository secrets, variables, runners, or Azure RBAC for a service principal

## Prerequisites

- Azure CLI installed and authenticated
- Docker installed and running
- Python 3 installed
- Access to push images into `reiopensourcepoc`
- ACR admin user enabled for `reiopensourcepoc`

## One-time setup

1. Log into Azure:

```bash
az login
az account set --subscription f1aaa597-6b5b-4a14-9ea0-275f389739a2
```

2. Log into Azure Container Registry:

```bash
az acr login --name reiopensourcepoc
```

3. Create your local env file:

```bash
cp scripts/azure/local.env.example scripts/azure/local.env
```

4. Edit `scripts/azure/local.env` if you need a different container group name, DNS label, or image tag.

## Deploy

Run this from the repository root:

### macOS / Linux

```bash
bash scripts/azure/deploy_local.sh
```

If you want to use a different env file:

```bash
bash scripts/azure/deploy_local.sh /path/to/your.env
```

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File scripts/azure/deploy_local.ps1
```

If you want to use a different env file:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/azure/deploy_local.ps1 -EnvFile C:\path\to\local.env
```

## What the script does

The script:

1. verifies your Azure subscription context
2. logs Docker into ACR
3. builds backend and frontend images for `linux/amd64`
4. pushes the images to ACR
5. renders the ACI manifest from the checked-in template
6. deploys or replaces the target ACI container group
7. restores the previous container group definition if deployment fails after replacement

The PowerShell script follows the same flow as the Bash script, but runs natively on Windows.

## Why it uses `linux/amd64`

Azure Container Instance expects Linux x64-compatible images in this setup. If you build directly on Apple Silicon with plain `docker build`, you will often produce `arm64` images that ACI cannot run. The script uses `docker buildx build --platform linux/amd64` to avoid that problem.

## Defaults

- Subscription: `f1aaa597-6b5b-4a14-9ea0-275f389739a2`
- Resource group: `RG-OpenSourcePOC`
- Region: `eastus`
- ACR: `reiopensourcepoc`
- Frontend CPU/memory: `0.5 vCPU / 1.0 GB`
- Backend CPU/memory: `0.5 vCPU / 1.0 GB`

## Verify deployment

After deployment:

```bash
curl "http://hrsa-rpa-ava.eastus.azurecontainer.io:3000/"
curl "http://hrsa-rpa-ava.eastus.azurecontainer.io:3000/api/documents"
```

If you changed the DNS label in `local.env`, use that DNS label instead of `hrsa-rpa-ava`.

## Troubleshooting

### `InaccessibleImage`

Usually means one of:

- the image was not pushed to ACR
- the image tag in `local.env` does not match what was pushed
- the image was built for `arm64` instead of `amd64`
- the ACR username/password used by ACI is invalid

### Windows notes

- Use Docker Desktop with `buildx` support enabled.
- Run the PowerShell deploy command from the repository root.
- The PowerShell script reads the same `scripts/azure/local.env` file format as the Bash script.

### `AuthorizationFailed` when assigning roles

This manual local deployment flow avoids the need to create Azure RBAC role assignments for a new service principal. If you can deploy resources in `RG-OpenSourcePOC` and push to ACR from your local machine, you can use this path without additional RBAC setup.

### Existing container group replaced

The deploy step is a replace operation for the configured `AZURE_CONTAINER_GROUP_NAME`. Use a unique name in `local.env` if you want to avoid touching another developer's test deployment.
