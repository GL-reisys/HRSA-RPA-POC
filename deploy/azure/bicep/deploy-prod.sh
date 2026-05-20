#!/usr/bin/env bash
#
# deploy-prod.sh — One-shot production deployment of the HRSA-RPA-AVA stack.
#
# This is the script Octopus invokes after it has already:
#   1. Pulled the Docker TAR from Azure DevOps
#   2. Loaded the image
#   3. Pushed the image to ACR
#
# It does everything else: preflight checks, Bicep deploy, post-deploy RBAC
# and private DNS wiring, and final verification.
#
# Usage:
#
#   # In Octopus, #{...} tokens are substituted before this runs.
#   # Standalone (manual), export the env vars below first:
#
#     export SUBSCRIPTION=...                  # subscription ID
#     export RESOURCE_GROUP=...
#     export LOCATION=usgovvirginia            # or eastus2 for commercial test
#     export REGION_ABBR=usgv
#     export DEPLOYMENT_ENVIRONMENT=dev        # 2-3 chars (32-char container-app name limit)
#     export ENVIRONMENT_NAME=dev              # tag value (dev/sbx/nonprod/prod)
#     export INFRA_SUBNET_ID=/subscriptions/.../subnets/<name>   # /23+, delegated Microsoft.App/environments
#     export PE_SUBNET_ID=/subscriptions/.../subnets/<name>       # no delegation
#     export LAW_ID=/subscriptions/.../workspaces/<name>          # pre-existing Log Analytics
#     export ACR_LOGIN_SERVER=creusdgpsehbssecrpa.azurecr.us
#     export FRONTEND_IMAGE_TAG=$(git rev-parse --short HEAD)     # or "latest"
#     export BACKEND_IMAGE_TAG=$(git rev-parse --short HEAD)
#     export AZURE_OPENAI_ENDPOINT=https://...openai.azure.us/
#     export AZURE_OPENAI_API_KEY=...                              # @secure, never echoed
#     export AZURE_OPENAI_DEPLOYMENT=gpt-4
#     # Optional — link the env's private DNS zone into peered VNets (EHB Web / EHB DB per OIT):
#     export PEERED_VNET_IDS="<vnet-id-1> <vnet-id-2>"             # space-separated
#
#     ./deploy-prod.sh
#
# Exit codes:
#   0 — deploy succeeded
#   1 — preflight failure
#   2 — bicep deploy failed
#   3 — post-deploy step failed (deploy itself was OK, follow-ups need attention)

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Inputs — Octopus tokens fall through to env vars for manual use.
# -----------------------------------------------------------------------------
SUBSCRIPTION="${SUBSCRIPTION:-#{Subscription}}"
RESOURCE_GROUP="${RESOURCE_GROUP:-#{ResourceGroup}}"
LOCATION="${LOCATION:-#{Location}}"
REGION_ABBR="${REGION_ABBR:-#{RegionAbbr}}"
DEPLOYMENT_ENVIRONMENT="${DEPLOYMENT_ENVIRONMENT:-#{DeploymentEnvironment}}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-#{environmentName}}"

INFRA_SUBNET_ID="${INFRA_SUBNET_ID:-#{InfrastructureSubnetId}}"
PE_SUBNET_ID="${PE_SUBNET_ID:-#{PrivateEndpointSubnetId}}"
LAW_ID="${LAW_ID:-#{LogAnalyticsWorkspaceId}}"

ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER:-#{AcrLoginServer}}"
FRONTEND_IMAGE_TAG="${FRONTEND_IMAGE_TAG:-#{FrontendImageTag}}"
BACKEND_IMAGE_TAG="${BACKEND_IMAGE_TAG:-#{BackendImageTag}}"

AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-#{AzureOpenAiEndpoint}}"
AZURE_OPENAI_API_KEY="${AZURE_OPENAI_API_KEY:-#{AzureOpenAiApiKey}}"
AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-#{AzureOpenAiDeployment}}"

CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-}"
PEERED_VNET_IDS="${PEERED_VNET_IDS:-}"

# Image references — the Octopus pipeline pushed these tags already.
FRONTEND_IMAGE="${ACR_LOGIN_SERVER}/ehbs-${ENVIRONMENT_NAME}-ui:${FRONTEND_IMAGE_TAG}"
BACKEND_IMAGE="${ACR_LOGIN_SERVER}/ehbs-${ENVIRONMENT_NAME}-svc:${BACKEND_IMAGE_TAG}"

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date -u +%Y%m%d%H%M%S)"
DEPLOYMENT_NAME="hrsa-rpa-ava-${DEPLOYMENT_ENVIRONMENT}-${TIMESTAMP}"

log() { printf '\n=== %s ===\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit "${2:-1}"; }

require() {
  local var="$1"
  local val="${!var:-}"
  if [[ -z "$val" || "$val" == "#{"* ]]; then
    fail "Missing required input: $var" 1
  fi
}

# -----------------------------------------------------------------------------
# Preflight
# -----------------------------------------------------------------------------
log "Preflight: required inputs"
for v in SUBSCRIPTION RESOURCE_GROUP LOCATION REGION_ABBR \
         DEPLOYMENT_ENVIRONMENT ENVIRONMENT_NAME \
         INFRA_SUBNET_ID PE_SUBNET_ID LAW_ID \
         ACR_LOGIN_SERVER FRONTEND_IMAGE_TAG BACKEND_IMAGE_TAG \
         AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_KEY AZURE_OPENAI_DEPLOYMENT; do
  require "$v"
done

# Container Apps name limit — fail fast on overflow
APP_NAME_PREFIX="ca-${REGION_ABBR}-dgps-ehbs-${DEPLOYMENT_ENVIRONMENT}-rpa"
for suffix in -ui -svc; do
  full="${APP_NAME_PREFIX}${suffix}"
  if [[ ${#full} -gt 32 ]]; then
    fail "Container app name '${full}' is ${#full} chars (limit 32). Shorten DEPLOYMENT_ENVIRONMENT or REGION_ABBR." 1
  fi
done
echo "  Container app names: ${APP_NAME_PREFIX}-ui, ${APP_NAME_PREFIX}-svc — within limit."

log "Preflight: Azure CLI session"
az account show -o tsv --query "{user:user.name, sub:name, cloud:environmentName}" || fail "Not logged in. Run 'az login' first." 1
az account set --subscription "$SUBSCRIPTION"

ACTIVE_CLOUD=$(az cloud show --query name -o tsv)
if [[ "$LOCATION" =~ ^usgov ]] && [[ "$ACTIVE_CLOUD" != "AzureUSGovernment" ]]; then
  fail "LOCATION=$LOCATION (Gov region) but active cloud is $ACTIVE_CLOUD.
  Run: az cloud set --name AzureUSGovernment && az login" 1
fi
echo "  Active cloud: $ACTIVE_CLOUD"

log "Preflight: resource providers"
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry \
          Microsoft.Network Microsoft.Insights Microsoft.ManagedIdentity; do
  state=$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)
  if [[ "$state" != "Registered" ]]; then
    echo "  Registering $ns..."
    az provider register --namespace "$ns" --wait
  fi
done

log "Preflight: subnet validation"
INFRA_PREFIX=$(az network vnet subnet show --ids "$INFRA_SUBNET_ID" \
                --query "addressPrefix || addressPrefixes[0]" -o tsv) \
  || fail "infrastructureSubnetId '$INFRA_SUBNET_ID' not found" 1
INFRA_DELEGATION=$(az network vnet subnet show --ids "$INFRA_SUBNET_ID" \
                --query "delegations[0].serviceName" -o tsv)
[[ "$INFRA_DELEGATION" == "Microsoft.App/environments" ]] \
  || fail "infrastructure subnet must be delegated to Microsoft.App/environments (got: '${INFRA_DELEGATION:-none}')" 1
PREFIX_SIZE=${INFRA_PREFIX##*/}
[[ -n "$PREFIX_SIZE" && "$PREFIX_SIZE" -le 23 ]] \
  || fail "infrastructure subnet $INFRA_PREFIX is smaller than /23 (Container Apps requires /23 minimum)" 1
echo "  infra subnet:  $INFRA_PREFIX, delegated $INFRA_DELEGATION ✓"

PE_PREFIX=$(az network vnet subnet show --ids "$PE_SUBNET_ID" \
            --query "addressPrefix || addressPrefixes[0]" -o tsv) \
  || fail "privateEndpointSubnetId '$PE_SUBNET_ID' not found" 1
echo "  PE subnet:     $PE_PREFIX ✓"

# -----------------------------------------------------------------------------
# Bicep deploy
# -----------------------------------------------------------------------------
declare -a BICEP_PARAMS=(
  location="$LOCATION"
  regionAbbr="$REGION_ABBR"
  deploymentEnvironment="$DEPLOYMENT_ENVIRONMENT"
  environmentName="$ENVIRONMENT_NAME"
  logAnalyticsWorkspaceId="$LAW_ID"
  infrastructureSubnetId="$INFRA_SUBNET_ID"
  privateEndpointSubnetId="$PE_SUBNET_ID"
  frontendImage="$FRONTEND_IMAGE"
  backendImage="$BACKEND_IMAGE"
  azureOpenAiEndpoint="$AZURE_OPENAI_ENDPOINT"
  azureOpenAiDeployment="$AZURE_OPENAI_DEPLOYMENT"
  corsAllowedOrigins="$CORS_ALLOWED_ORIGINS"
)

log "Validating Bicep template"
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "${BICEP_PARAMS[@]}" \
  >/dev/null || fail "validate failed" 2

log "What-if preview"
az deployment group what-if \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "${BICEP_PARAMS[@]}" \
  --no-pretty-print \
  --result-format ResourceIdOnly | grep -E '^\s*[+~-]' || true

log "Deploying ${DEPLOYMENT_NAME}"
DEPLOY_OUT=$(az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DEPLOYMENT_NAME" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "${BICEP_PARAMS[@]}" \
  --query properties.outputs -o json) || fail "deploy failed" 2

echo "$DEPLOY_OUT" | jq -r '
  to_entries[] | "  \(.key): \(.value.value)"
'

# -----------------------------------------------------------------------------
# Post-deploy — RBAC + private DNS + verification
# -----------------------------------------------------------------------------
MI_ID=$(echo "$DEPLOY_OUT" | jq -r '.managedIdentityId.value')
MI_PRINCIPAL_ID=$(echo "$DEPLOY_OUT" | jq -r '.managedIdentityPrincipalId.value')
ACR_ID=$(echo "$DEPLOY_OUT" | jq -r '.acrId.value')
CAE_DOMAIN=$(echo "$DEPLOY_OUT" | jq -r '.containerAppsEnvironmentDefaultDomain.value')
CAE_STATIC_IP=$(echo "$DEPLOY_OUT" | jq -r '.containerAppsEnvironmentStaticIp.value')
FE_FQDN=$(echo "$DEPLOY_OUT" | jq -r '.frontendFqdn.value')
BE_FQDN=$(echo "$DEPLOY_OUT" | jq -r '.backendFqdn.value')
FE_NAME=$(echo "$FE_FQDN" | cut -d. -f1)
BE_NAME=$(echo "$BE_FQDN" | cut -d. -f1)

POST_FAILED=0

log "Granting AcrPull to managed identity"
if az role assignment list \
    --assignee "$MI_PRINCIPAL_ID" --scope "$ACR_ID" --role AcrPull \
    --query "[0].id" -o tsv 2>/dev/null | grep -q .; then
  echo "  AcrPull already in place."
else
  if az role assignment create \
       --assignee-object-id "$MI_PRINCIPAL_ID" \
       --assignee-principal-type ServicePrincipal \
       --role AcrPull --scope "$ACR_ID" >/dev/null 2>&1; then
    echo "  AcrPull granted."
  else
    cat >&2 <<EOF
  WARNING: AcrPull grant failed (likely RBAC). Have a User Access Administrator run:
    az role assignment create \\
      --assignee-object-id $MI_PRINCIPAL_ID \\
      --assignee-principal-type ServicePrincipal \\
      --role AcrPull \\
      --scope $ACR_ID
EOF
    POST_FAILED=1
  fi
fi

log "Provisioning private DNS zone for ACA env"
# Auto-create is unreliable in regulated subscriptions; do it explicitly.
DNS_ZONE_RG="$RESOURCE_GROUP"
if ! az network private-dns zone show -g "$DNS_ZONE_RG" -n "$CAE_DOMAIN" >/dev/null 2>&1; then
  az network private-dns zone create -g "$DNS_ZONE_RG" -n "$CAE_DOMAIN" >/dev/null
  echo "  Zone $CAE_DOMAIN created."
else
  echo "  Zone $CAE_DOMAIN already exists."
fi

# Wildcard A record so every app FQDN under the zone resolves to the env's static IP.
az network private-dns record-set a delete -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n '*' --yes >/dev/null 2>&1 || true
az network private-dns record-set a create  -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n '*' --ttl 3600 >/dev/null
az network private-dns record-set a add-record -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n '*' -a "$CAE_STATIC_IP" >/dev/null
echo "  Wildcard A → $CAE_STATIC_IP."

# Link the zone into the deploy VNet (so apps in the env can resolve each other)
DEPLOY_VNET_ID=$(az network vnet subnet show --ids "$INFRA_SUBNET_ID" --query id -o tsv \
                  | awk -F'/subnets/' '{print $1}')
DEPLOY_VNET_NAME=${DEPLOY_VNET_ID##*/}
DEPLOY_LINK="link-${DEPLOY_VNET_NAME}"
if ! az network private-dns link vnet show -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n "$DEPLOY_LINK" >/dev/null 2>&1; then
  az network private-dns link vnet create -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n "$DEPLOY_LINK" \
    --virtual-network "$DEPLOY_VNET_ID" --registration-enabled false >/dev/null
  echo "  Linked deploy VNet ($DEPLOY_VNET_NAME)."
else
  echo "  Deploy VNet already linked."
fi

# Link into peered VNets (EHB Web, EHB DB per OIT requirement) so they can resolve the app FQDNs.
if [[ -n "$PEERED_VNET_IDS" ]]; then
  for peer in $PEERED_VNET_IDS; do
    pname=${peer##*/}
    plink="link-${pname}"
    if ! az network private-dns link vnet show -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n "$plink" >/dev/null 2>&1; then
      if az network private-dns link vnet create -g "$DNS_ZONE_RG" -z "$CAE_DOMAIN" -n "$plink" \
          --virtual-network "$peer" --registration-enabled false >/dev/null 2>&1; then
        echo "  Linked peered VNet ($pname)."
      else
        echo "  WARNING: failed to link $pname (cross-sub peerings may need permissions in the target sub)"
        POST_FAILED=1
      fi
    fi
  done
else
  echo "  PEERED_VNET_IDS empty — only the deploy VNet was linked. EHB Web/DB users won't resolve the FQDN until linked."
fi

# -----------------------------------------------------------------------------
# Verification
# -----------------------------------------------------------------------------
log "Verification"
echo "  Deployment:     $DEPLOYMENT_NAME"
echo "  ACA env domain: $CAE_DOMAIN"
echo "  Env static IP:  $CAE_STATIC_IP"
echo "  Frontend FQDN:  $FE_FQDN"
echo "  Backend FQDN:   $BE_FQDN"
echo "  ACR:            $ACR_LOGIN_SERVER"
echo "  Images:         $FRONTEND_IMAGE"
echo "                  $BACKEND_IMAGE"

# Wait for the latest revisions to report Healthy (or fail with a clear log message)
for app in "$FE_NAME" "$BE_NAME"; do
  for attempt in $(seq 1 30); do
    state=$(az containerapp show -g "$RESOURCE_GROUP" -n "$app" \
              --query "properties.runningStatus" -o tsv 2>/dev/null || echo Unknown)
    health=$(az containerapp revision list -g "$RESOURCE_GROUP" -n "$app" \
              --query "[?properties.active] | [0].properties.healthState" -o tsv 2>/dev/null || echo Unknown)
    if [[ "$state" == "Running" && "$health" == "Healthy" ]]; then
      echo "  $app — Running / Healthy"
      break
    fi
    if [[ "$attempt" == "30" ]]; then
      echo "  WARNING: $app not Healthy after 5 min (state=$state health=$health)"
      POST_FAILED=1
    fi
    sleep 10
  done
done

if [[ "$POST_FAILED" == "1" ]]; then
  exit 3
fi

log "Deployment complete."
