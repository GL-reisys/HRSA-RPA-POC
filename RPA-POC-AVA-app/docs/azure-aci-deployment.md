# Azure Container Instance Deployment

This project includes a GitHub Actions pipeline that builds the frontend and backend Docker images, pushes them to Azure Container Registry, and deploys a new Azure Container Instance container group for the app.

For a direct local-machine deployment path, see [azure-aci-local-deploy.md](/Users/leohein/Documents/Github/HRSA-RPA-POC/RPA-POC-AVA-app/docs/azure-aci-local-deploy.md).

## Azure defaults

- Subscription: `f1aaa597-6b5b-4a14-9ea0-275f389739a2`
- Region: `eastus`
- Resource group: `RG-OpenSourcePOC`
- Recommended Azure Container Registry: `reiopensourcepoc`

## Required GitHub configuration

### GitHub secrets

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`

### GitHub repository variables

- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `AZURE_LOCATION`
- `AZURE_ACR_NAME`
- `AZURE_ACR_LOGIN_SERVER`
- `AZURE_CONTAINER_GROUP_NAME`
- `AZURE_DNS_LABEL`

## Azure prerequisites

1. Create or choose an Azure app registration / service principal for GitHub Actions.
2. Add a federated credential on that app registration for this GitHub repository and branch/workflow scope.
3. Add these GitHub Actions settings:
   - Secrets:
     - `AZURE_CLIENT_ID`
     - `AZURE_TENANT_ID`
   - Variables:
     - `AZURE_SUBSCRIPTION_ID`
     - `AZURE_RESOURCE_GROUP`
     - `AZURE_LOCATION`
     - `AZURE_ACR_NAME`
     - `AZURE_ACR_LOGIN_SERVER`
     - `AZURE_CONTAINER_GROUP_NAME`
     - `AZURE_DNS_LABEL`
4. Ensure the target resource group already exists.
5. Enable the ACR admin user because the workflow fetches deployment credentials for Azure Container Instances:

```bash
az acr update \
  --name reiopensourcepoc \
  --resource-group RG-OpenSourcePOC \
  --admin-enabled true
```

## Common login failure

If the workflow fails at Azure login with a message like `Using auth-type: SERVICE_PRINCIPAL. Not all values are present`, the repository is missing one or both of these GitHub secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`

The workflow now checks for those values before `azure/login`, but Azure sign-in will still fail later unless the Azure app registration also has the correct federated credential for this GitHub repository.

## Workaround with current permissions

If you only have `Contributor` on the target resource group and cannot create RBAC role assignments for a service principal, you can still run this deployment pipeline by using a self-hosted GitHub Actions runner on a machine where you are already signed in with Azure CLI.

Setup for that mode:

1. Register a self-hosted runner for this repository.
2. On the runner machine, sign in once:

```bash
az login
az account set --subscription f1aaa597-6b5b-4a14-9ea0-275f389739a2
az acr login --name reiopensourcepoc
```

3. Set this GitHub repository variable:

```text
GITHUB_RUNNER=self-hosted
```

In self-hosted mode, the workflow skips `azure/login` and uses the local Azure CLI session on the runner instead. This avoids the need to create a new service principal or assign new RBAC roles.

## Runtime behavior

- The frontend is the only public endpoint and listens on port `3000`.
- The backend stays internal to the container group and listens on port `5000`.
- Browser traffic uses same-origin `/api/...` requests, and the frontend forwards those requests to the backend inside the container group.
- Uploaded files and JSON metadata are stored in the container filesystem and will be lost if the container group is replaced.

## Local verification

Run the stack locally with Docker Compose:

```bash
cd RPA-POC-AVA-app
docker-compose up --build
```

Then open:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:5000/health`

## Workflow behavior

The deployment workflow:

1. Builds both Docker images.
2. Pushes commit SHA and `latest` tags to ACR.
3. Renders the ACI YAML manifest from checked-in templates.
4. Replaces only the named app container group if it already exists.
5. Runs smoke checks against the deployed frontend and proxied `/api/documents` endpoint.
