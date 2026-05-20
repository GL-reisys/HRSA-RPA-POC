#!/usr/bin/env bash
#
# Deploy the HRSA RPA-POC app to Azure Container Apps.
#
# Pipeline:
#   1. Validate Azure CLI context against scripts/azure/local.env
#   2. Build & push backend and frontend images via ACR Tasks (no local Docker)
#   3. Ensure the Container Apps Environment exists
#   4. Create or update the backend Container App (internal ingress, port 5000)
#   5. Create or update the frontend Container App (external ingress, port 3000)
#   6. Print the public URL
#
# Usage:
#   bash scripts/azure/deploy_containerapp.sh [path-to-env-file]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/azure/deploy_containerapp.sh [path-to-env-file]

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
  AZURE_CONTAINERAPPS_ENV
  AZURE_CONTAINERAPP_BACKEND
  AZURE_CONTAINERAPP_FRONTEND
  AZURE_LOG_ANALYTICS_WORKSPACE
  API_INTERNAL_URL
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required variable in $ENV_FILE: $var_name" >&2
    exit 1
  fi
done

BACKEND_IMAGE_TAG="${BACKEND_IMAGE_TAG:-manual-amd64}"
FRONTEND_IMAGE_TAG="${FRONTEND_IMAGE_TAG:-containerapp-amd64}"
FRONTEND_CPU="${FRONTEND_CPU:-0.5}"
FRONTEND_MEMORY_GB="${FRONTEND_MEMORY_GB:-1.0}"
BACKEND_CPU="${BACKEND_CPU:-0.5}"
BACKEND_MEMORY_GB="${BACKEND_MEMORY_GB:-1.0}"

BACKEND_IMAGE="$AZURE_ACR_LOGIN_SERVER/hrsa-rpa-ava-backend:$BACKEND_IMAGE_TAG"
FRONTEND_IMAGE="$AZURE_ACR_LOGIN_SERVER/hrsa-rpa-ava-frontend:$FRONTEND_IMAGE_TAG"

TAG_ARGS=()
for tag_var in AZURE_TAG_COSTCENTER:CostCenter AZURE_TAG_OWNER:Owner AZURE_TAG_PROJECT:Project; do
  var_name="${tag_var%%:*}"
  tag_key="${tag_var##*:}"
  if [[ -n "${!var_name:-}" ]]; then
    TAG_ARGS+=("$tag_key=${!var_name}")
  fi
done
TAG_ARGS+=("app=hrsa-rpa-ava")

command -v az >/dev/null 2>&1 || { echo "Azure CLI is required." >&2; exit 1; }

active_subscription="$(az account show --query id -o tsv)"
if [[ "$active_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI is logged into subscription $active_subscription, expected $AZURE_SUBSCRIPTION_ID." >&2
  echo "Run: az account set --subscription $AZURE_SUBSCRIPTION_ID" >&2
  exit 1
fi

# Ensure containerapp extension is installed
if ! az extension show --name containerapp >/dev/null 2>&1; then
  echo "Installing containerapp Azure CLI extension..."
  az extension add --name containerapp --only-show-errors
fi

# === 1. Build & push images via ACR Tasks ===

echo "[1/5] Building backend image: $BACKEND_IMAGE"
az acr build \
  --registry "$AZURE_ACR_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "hrsa-rpa-ava-backend:$BACKEND_IMAGE_TAG" \
  --platform linux/amd64 \
  --file "$REPO_ROOT/RPA-POC-AVA-app/backend/Dockerfile" \
  --only-show-errors \
  "$REPO_ROOT/RPA-POC-AVA-app/backend"

echo "[2/5] Building frontend image: $FRONTEND_IMAGE"
echo "       (API_INTERNAL_URL=$API_INTERNAL_URL is baked in at build time)"
az acr build \
  --registry "$AZURE_ACR_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "hrsa-rpa-ava-frontend:$FRONTEND_IMAGE_TAG" \
  --platform linux/amd64 \
  --file "$REPO_ROOT/RPA-POC-AVA-app/frontend/Dockerfile" \
  --build-arg API_INTERNAL_URL="$API_INTERNAL_URL" \
  --only-show-errors \
  "$REPO_ROOT/RPA-POC-AVA-app/frontend"

ACR_USERNAME="$(az acr credential show --name "$AZURE_ACR_NAME" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show --name "$AZURE_ACR_NAME" --query 'passwords[0].value' -o tsv)"

# === 2. Ensure the Container Apps Environment exists ===

echo "[3/5] Ensuring Container Apps Environment $AZURE_CONTAINERAPPS_ENV"
if ! az containerapp env show --name "$AZURE_CONTAINERAPPS_ENV" --resource-group "$AZURE_RESOURCE_GROUP" >/dev/null 2>&1; then
  LA_ID="$(az monitor log-analytics workspace show --resource-group "$AZURE_RESOURCE_GROUP" --workspace-name "$AZURE_LOG_ANALYTICS_WORKSPACE" --query customerId -o tsv)"
  LA_KEY="$(az monitor log-analytics workspace get-shared-keys --resource-group "$AZURE_RESOURCE_GROUP" --workspace-name "$AZURE_LOG_ANALYTICS_WORKSPACE" --query primarySharedKey -o tsv)"
  az containerapp env create \
    --name "$AZURE_CONTAINERAPPS_ENV" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --logs-workspace-id "$LA_ID" \
    --logs-workspace-key "$LA_KEY" \
    --tags "${TAG_ARGS[@]}" \
    --only-show-errors \
    -o none
fi

# === 3. Backend Container App ===

BACKEND_ENV_VARS=(
  "PORT=5000"
  "FLASK_ENV=production"
  "FLASK_DEBUG=0"
  "UPLOAD_DIR=/app/uploads"
  "DATA_DIR=/app/database"
  "CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000"
)
BACKEND_SECRETS=()
if [[ -n "${AZURE_OPENAI_ENDPOINT:-}" ]]; then
  BACKEND_ENV_VARS+=("AZURE_OPENAI_ENDPOINT=$AZURE_OPENAI_ENDPOINT")
fi
# Resolve the OpenAI key, prefer explicit env var, fall back to looking it up
# from AZURE_OPENAI_ACCOUNT. The key is registered as a Container Apps *secret*
# and the env var is exposed via secretref so it never lands in plaintext.
RESOLVED_OPENAI_KEY=""
if [[ -n "${AZURE_OPENAI_API_KEY:-}" ]]; then
  RESOLVED_OPENAI_KEY="$AZURE_OPENAI_API_KEY"
elif [[ -n "${AZURE_OPENAI_ACCOUNT:-}" ]]; then
  RESOLVED_OPENAI_KEY="$(az cognitiveservices account keys list --name "$AZURE_OPENAI_ACCOUNT" --resource-group "$AZURE_RESOURCE_GROUP" --query key1 -o tsv 2>/dev/null || true)"
fi
if [[ -n "$RESOLVED_OPENAI_KEY" ]]; then
  BACKEND_SECRETS+=("azure-openai-key=$RESOLVED_OPENAI_KEY")
  BACKEND_ENV_VARS+=("AZURE_OPENAI_API_KEY=secretref:azure-openai-key")
fi
if [[ -n "${AZURE_OPENAI_DEPLOYMENT:-}" ]]; then
  BACKEND_ENV_VARS+=("AZURE_OPENAI_DEPLOYMENT=$AZURE_OPENAI_DEPLOYMENT")
fi

echo "[4/5] Deploying backend Container App $AZURE_CONTAINERAPP_BACKEND"
if az containerapp show --name "$AZURE_CONTAINERAPP_BACKEND" --resource-group "$AZURE_RESOURCE_GROUP" >/dev/null 2>&1; then
  if [[ ${#BACKEND_SECRETS[@]} -gt 0 ]]; then
    az containerapp secret set \
      --name "$AZURE_CONTAINERAPP_BACKEND" \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --secrets "${BACKEND_SECRETS[@]}" \
      --only-show-errors \
      -o none
  fi
  az containerapp update \
    --name "$AZURE_CONTAINERAPP_BACKEND" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --image "$BACKEND_IMAGE" \
    --set-env-vars "${BACKEND_ENV_VARS[@]}" \
    --only-show-errors \
    -o none
else
  CREATE_ARGS=(
    --name "$AZURE_CONTAINERAPP_BACKEND"
    --resource-group "$AZURE_RESOURCE_GROUP"
    --environment "$AZURE_CONTAINERAPPS_ENV"
    --image "$BACKEND_IMAGE"
    --registry-server "$AZURE_ACR_LOGIN_SERVER"
    --registry-username "$ACR_USERNAME"
    --registry-password "$ACR_PASSWORD"
    --ingress internal
    --target-port 5000
    --transport http
    --cpu "$BACKEND_CPU" --memory "${BACKEND_MEMORY_GB}Gi"
    --min-replicas 1 --max-replicas 2
    --env-vars "${BACKEND_ENV_VARS[@]}"
    --tags "${TAG_ARGS[@]}" role=backend
    --only-show-errors
    -o none
  )
  if [[ ${#BACKEND_SECRETS[@]} -gt 0 ]]; then
    CREATE_ARGS+=(--secrets "${BACKEND_SECRETS[@]}")
  fi
  az containerapp create "${CREATE_ARGS[@]}"
fi

# === 4. Frontend Container App ===

FRONTEND_ENV_VARS=(
  "PORT=3000"
  "API_INTERNAL_URL=$API_INTERNAL_URL"
)

echo "[5/5] Deploying frontend Container App $AZURE_CONTAINERAPP_FRONTEND"
if az containerapp show --name "$AZURE_CONTAINERAPP_FRONTEND" --resource-group "$AZURE_RESOURCE_GROUP" >/dev/null 2>&1; then
  az containerapp update \
    --name "$AZURE_CONTAINERAPP_FRONTEND" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --image "$FRONTEND_IMAGE" \
    --set-env-vars "${FRONTEND_ENV_VARS[@]}" \
    --only-show-errors \
    -o none
else
  az containerapp create \
    --name "$AZURE_CONTAINERAPP_FRONTEND" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --environment "$AZURE_CONTAINERAPPS_ENV" \
    --image "$FRONTEND_IMAGE" \
    --registry-server "$AZURE_ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USERNAME" \
    --registry-password "$ACR_PASSWORD" \
    --ingress external \
    --target-port 3000 \
    --transport http \
    --cpu "$FRONTEND_CPU" --memory "${FRONTEND_MEMORY_GB}Gi" \
    --min-replicas 1 --max-replicas 2 \
    --env-vars "${FRONTEND_ENV_VARS[@]}" \
    --tags "${TAG_ARGS[@]}" role=frontend \
    --only-show-errors \
    -o none
fi

FE_FQDN="$(az containerapp show --name "$AZURE_CONTAINERAPP_FRONTEND" --resource-group "$AZURE_RESOURCE_GROUP" --query "properties.configuration.ingress.fqdn" -o tsv)"

echo ""
echo "Deployment completed."
echo "Frontend URL: https://$FE_FQDN"
