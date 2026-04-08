#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <rendered-aci-manifest-path>" >&2
  exit 1
fi

manifest_path="$1"
existing_manifest_path=""
existing_manifest_exported="false"
deployment_started="false"
new_container_created="false"

restore_previous_container_group() {
  if [[ "$existing_manifest_exported" != "true" || ! -f "$existing_manifest_path" ]]; then
    return
  fi

  echo "Restoring previous container group definition for $AZURE_CONTAINER_GROUP_NAME." >&2
  az container create \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --file "$existing_manifest_path" \
    --only-show-errors >/dev/null
}

handle_deploy_failure() {
  exit_code=$?
  if [[ $exit_code -eq 0 || "$deployment_started" != "true" ]]; then
    exit $exit_code
  fi

  if [[ "$new_container_created" == "true" ]]; then
    az container delete \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$AZURE_CONTAINER_GROUP_NAME" \
      --yes >/dev/null 2>&1 || true
  fi

  restore_previous_container_group || true
  exit $exit_code
}

trap handle_deploy_failure EXIT

required_vars=(
  AZURE_RESOURCE_GROUP
  AZURE_CONTAINER_GROUP_NAME
  AZURE_LOCATION
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required environment variable: $var_name" >&2
    exit 1
  fi
done

if az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" >/dev/null 2>&1; then
  existing_manifest_path="$(mktemp "${TMPDIR:-/tmp}/aci-backup.XXXXXX.yaml")"
  az container export \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_CONTAINER_GROUP_NAME" \
    --file "$existing_manifest_path" \
    --only-show-errors
  existing_manifest_exported="true"

  echo "Replacing existing container group $AZURE_CONTAINER_GROUP_NAME in $AZURE_RESOURCE_GROUP."
  az container delete \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_CONTAINER_GROUP_NAME" \
    --yes

  for _ in $(seq 1 30); do
    if ! az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" >/dev/null 2>&1; then
      break
    fi
    sleep 10
  done
fi

deployment_started="true"
az container create \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --file "$manifest_path" \
  --only-show-errors
new_container_created="true"

for _ in $(seq 1 30); do
  state="$(az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --query instanceView.state -o tsv)"
  if [[ "$state" == "Running" ]]; then
    new_container_created="false"
    break
  fi
  sleep 10
done

final_state="$(az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --query instanceView.state -o tsv)"
if [[ "$final_state" != "Running" ]]; then
  echo "Container group $AZURE_CONTAINER_GROUP_NAME failed to reach Running state. Final state: $final_state" >&2
  exit 1
fi

fqdn="$(az container show --resource-group "$AZURE_RESOURCE_GROUP" --name "$AZURE_CONTAINER_GROUP_NAME" --query ipAddress.fqdn -o tsv)"
echo "Azure Container Instance is available at: http://$fqdn:3000"

trap - EXIT
