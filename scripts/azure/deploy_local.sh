#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/azure/deploy_local.sh [path-to-env-file]

Description:
  Builds linux/amd64 frontend and backend images, pushes them to Azure Container Registry,
  renders the Azure Container Instance manifest, and deploys the container group.

Defaults:
  If no env file is supplied, the script looks for scripts/azure/local.env.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ENV_FILE="${1:-$SCRIPT_DIR/local.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  echo "Copy scripts/azure/local.env.example to scripts/azure/local.env and fill in the values." >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

required_vars=(
  AZURE_SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  AZURE_ACR_NAME
  AZURE_ACR_LOGIN_SERVER
  AZURE_CONTAINER_GROUP_NAME
  AZURE_DNS_LABEL
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required variable in $ENV_FILE: $var_name" >&2
    exit 1
  fi
done

FRONTEND_IMAGE_TAG="${FRONTEND_IMAGE_TAG:-manual-amd64}"
BACKEND_IMAGE_TAG="${BACKEND_IMAGE_TAG:-manual-amd64}"
FRONTEND_CPU="${FRONTEND_CPU:-0.5}"
FRONTEND_MEMORY_GB="${FRONTEND_MEMORY_GB:-1.0}"
BACKEND_CPU="${BACKEND_CPU:-0.5}"
BACKEND_MEMORY_GB="${BACKEND_MEMORY_GB:-1.0}"
API_INTERNAL_URL="${API_INTERNAL_URL:-http://127.0.0.1:5000}"
CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:3000,http://127.0.0.1:3000,http://${AZURE_DNS_LABEL}.${AZURE_LOCATION}.azurecontainer.io:3000}"
ACI_MANIFEST_PATH="${ACI_MANIFEST_PATH:-${TMPDIR:-/tmp}/hrsa-rpa-ava-aci.yaml}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-$AZURE_ACR_LOGIN_SERVER/hrsa-rpa-ava-frontend:$FRONTEND_IMAGE_TAG}"
BACKEND_IMAGE="${BACKEND_IMAGE:-$AZURE_ACR_LOGIN_SERVER/hrsa-rpa-ava-backend:$BACKEND_IMAGE_TAG}"

command -v az >/dev/null 2>&1 || { echo "Azure CLI is required." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }

active_subscription="$(az account show --query id -o tsv)"
if [[ "$active_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI is logged into subscription $active_subscription, expected $AZURE_SUBSCRIPTION_ID." >&2
  echo "Run: az account set --subscription $AZURE_SUBSCRIPTION_ID" >&2
  exit 1
fi

AZURE_ACR_USERNAME="${AZURE_ACR_USERNAME:-$(az acr credential show --name "$AZURE_ACR_NAME" --query username -o tsv)}"
AZURE_ACR_PASSWORD="${AZURE_ACR_PASSWORD:-$(az acr credential show --name "$AZURE_ACR_NAME" --query 'passwords[0].value' -o tsv)}"

export AZURE_SUBSCRIPTION_ID
export AZURE_RESOURCE_GROUP
export AZURE_LOCATION
export AZURE_ACR_NAME
export AZURE_ACR_LOGIN_SERVER
export AZURE_CONTAINER_GROUP_NAME
export AZURE_DNS_LABEL
export FRONTEND_CPU
export FRONTEND_MEMORY_GB
export BACKEND_CPU
export BACKEND_MEMORY_GB
export API_INTERNAL_URL
export CORS_ALLOWED_ORIGINS
export FRONTEND_IMAGE
export BACKEND_IMAGE
export AZURE_ACR_USERNAME
export AZURE_ACR_PASSWORD

BACKEND_IMAGE_REPO_TAG="${BACKEND_IMAGE#*/}"
FRONTEND_IMAGE_REPO_TAG="${FRONTEND_IMAGE#*/}"

echo "Building backend image in ACR Tasks: $BACKEND_IMAGE"
az acr build \
  --registry "$AZURE_ACR_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "$BACKEND_IMAGE_REPO_TAG" \
  --platform linux/amd64 \
  --file "$REPO_ROOT/RPA-POC-AVA-app/backend/Dockerfile" \
  --only-show-errors \
  "$REPO_ROOT/RPA-POC-AVA-app/backend"

echo "Building frontend image in ACR Tasks: $FRONTEND_IMAGE"
az acr build \
  --registry "$AZURE_ACR_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "$FRONTEND_IMAGE_REPO_TAG" \
  --platform linux/amd64 \
  --file "$REPO_ROOT/RPA-POC-AVA-app/frontend/Dockerfile" \
  --build-arg API_INTERNAL_URL="$API_INTERNAL_URL" \
  --only-show-errors \
  "$REPO_ROOT/RPA-POC-AVA-app/frontend"

echo "Rendering ACI manifest to $ACI_MANIFEST_PATH"
python3 "$SCRIPT_DIR/render_aci_manifest.py" \
  --template "$REPO_ROOT/deploy/azure/aci-container-group.yaml.template" \
  --output "$ACI_MANIFEST_PATH"

echo "Deploying Azure Container Instance $AZURE_CONTAINER_GROUP_NAME"
bash "$SCRIPT_DIR/deploy_aci.sh" "$ACI_MANIFEST_PATH"

echo "Deployment completed."
echo "Frontend URL: http://${AZURE_DNS_LABEL}.${AZURE_LOCATION}.azurecontainer.io:3000"

