#!/usr/bin/env bash
# Deploys the private-network Bicep stack to an Azure Government subscription.
#
# Prereqs:
#   - az cli logged in to the gov cloud:  az cloud set --name AzureUSGovernment && az login
#   - az account set --subscription <gov-subscription-id>
#   - Microsoft.ContainerInstance and Microsoft.App providers registered on the subscription
#   - Resource group already created in the chosen Gov region
#
# Usage:
#   AZURE_OPENAI_API_KEY=... ./deploy.sh <resource-group>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RESOURCE_GROUP="${1:-}"
if [[ -z "$RESOURCE_GROUP" ]]; then
  echo "Usage: $0 <resource-group>" >&2
  exit 1
fi

if [[ -z "${AZURE_OPENAI_API_KEY:-}" ]]; then
  echo "AZURE_OPENAI_API_KEY must be set in the environment." >&2
  exit 1
fi

active_cloud="$(az cloud show --query name -o tsv)"
if [[ "$active_cloud" != "AzureUSGovernment" ]]; then
  echo "Active cloud is $active_cloud, expected AzureUSGovernment." >&2
  echo "Run: az cloud set --name AzureUSGovernment && az login" >&2
  exit 1
fi

# Ensure required providers are registered (idempotent; skips if already done).
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.Network; do
  state="$(az provider show --namespace "$ns" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)"
  if [[ "$state" != "Registered" ]]; then
    echo "Registering provider $ns ..."
    az provider register --namespace "$ns" --wait
  fi
done

echo "Validating Bicep template..."
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "$SCRIPT_DIR/main.gov.bicepparam" \
  --parameters "azureOpenAiApiKey=$AZURE_OPENAI_API_KEY" \
  >/dev/null

echo "Running what-if (preview changes)..."
az deployment group what-if \
  --resource-group "$RESOURCE_GROUP" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "$SCRIPT_DIR/main.gov.bicepparam" \
  --parameters "azureOpenAiApiKey=$AZURE_OPENAI_API_KEY"

read -r -p "Proceed with deployment? [y/N] " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
  echo "Aborted."
  exit 0
fi

echo "Deploying..."
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name "hrsa-rpa-ava-priv-$(date -u +%Y%m%d%H%M%S)" \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --parameters "$SCRIPT_DIR/main.gov.bicepparam" \
  --parameters "azureOpenAiApiKey=$AZURE_OPENAI_API_KEY"

echo "Deployment complete."
