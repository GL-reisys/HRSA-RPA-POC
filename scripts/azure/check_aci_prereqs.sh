#!/usr/bin/env bash

set -euo pipefail

required_vars=(
  AZURE_SUBSCRIPTION_ID
  AZURE_RESOURCE_GROUP
  AZURE_LOCATION
  AZURE_ACR_NAME
  AZURE_ACR_LOGIN_SERVER
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: $var_name" >&2
    exit 1
  fi
done

active_subscription="$(az account show --query id -o tsv)"
if [[ "$active_subscription" != "$AZURE_SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI is targeting subscription $active_subscription, expected $AZURE_SUBSCRIPTION_ID." >&2
  exit 1
fi

if [[ "$(az group exists --name "$AZURE_RESOURCE_GROUP")" != "true" ]]; then
  echo "Azure resource group $AZURE_RESOURCE_GROUP does not exist." >&2
  exit 1
fi

acr_login_server="$(az acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query loginServer -o tsv)"
if [[ "$acr_login_server" != "$AZURE_ACR_LOGIN_SERVER" ]]; then
  echo "Azure Container Registry login server mismatch. Expected $AZURE_ACR_LOGIN_SERVER, got $acr_login_server." >&2
  exit 1
fi

acr_admin_enabled="$(az acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query adminUserEnabled -o tsv)"
if [[ "$acr_admin_enabled" != "true" ]]; then
  echo "Azure Container Registry $AZURE_ACR_NAME must have the admin user enabled for this pipeline." >&2
  echo "Run: az acr update --name $AZURE_ACR_NAME --resource-group $AZURE_RESOURCE_GROUP --admin-enabled true" >&2
  exit 1
fi

echo "Azure deployment prerequisites validated for $AZURE_RESOURCE_GROUP in $AZURE_LOCATION."

