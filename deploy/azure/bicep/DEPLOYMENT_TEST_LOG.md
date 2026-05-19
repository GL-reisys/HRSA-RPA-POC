# Deployment Test Log — `deploy/azure/bicep`

**Session date:** 2026-05-15 — 2026-05-18
**Goal:** Validate the private-network Container Apps Bicep stack end-to-end under the currently logged-in Azure session before promoting it to a real Gov deploy.

This document captures every issue surfaced during manual testing, the fix applied, and what still needs to be addressed before a production / Gov rollout.

---

## Production Gov deployment pipeline (per OM / OIT)

This is the target flow once the template is ready to ship:

```
Azure DevOps  ─►  Build Docker image
Azure DevOps  ─►  Save image as TAR
Azure DevOps  ─►  Push TAR package to Octopus
   Octopus    ─►  Load image
   Octopus    ─►  Push image to ACR
   Octopus    ─►  az deployment group create  (substitutes #{...} variables, runs this Bicep)
```

Implications for the template:

- **Octopus tokens are part of the contract.** The pipeline relies on `#{environmentName}` (and similar) being substituted before Bicep runs. The change to `${environmentName}` in [main.gov.bicepparam](main.gov.bicepparam) is **compatible with both** modes — Octopus substitution happens first on the raw text, and any leftover `${...}` is evaluated by Bicep. Keep that form so manual / CLI testing also works.
- **Images exist in ACR before Container Apps start.** Step "Octopus → Push to ACR" must complete before the `az deployment group create` step, otherwise Container Apps will fail to pull. Worth gating this explicitly in the Octopus runbook.

## OIT network prerequisites (Gov)

OIT provides the VNet; the bicep stack consumes it. Required topology:

| # | Resource | Requirement |
|---|---|---|
| 1 | Infrastructure subnet | Delegated to `Microsoft.App/environments`, **minimum /23 CIDR**. Passed as `infrastructureSubnetId`. |
| 2 | Private endpoint subnet | **No delegation**. PE network policies should be `Disabled`. Passed as `privateEndpointSubnetId`. |
| 3 | VNet peerings | VNet must be peered with **EHB Web** and **EHB DB** VNets so the apps can reach existing EHB services and so EHB workloads can reach the frontend via its internal FQDN. |

Operational consequences:

- **DNS forwarders are mandatory.** Because the VNet is peered into the EHB topology, it almost certainly uses on-prem / EHB DNS resolvers (matching what we saw on `VNET-HRSA-SHARED-DEV`). Those resolvers must forward unresolvable names to Azure DNS `168.63.129.16` — otherwise the ACA env can't reach the ACR token endpoint, AAD, or its own control plane. See [issue 8 below](#8-custom-dns-on-the-shared-vnet-cant-resolve-public-hostnames).
- **Private DNS zone linking.** The ACA env auto-creates `privatelink.<region>.azurecontainerapps.us`. To resolve the frontend FQDN from EHB Web/DB VNets after peering, that zone must be **linked to each peered VNet** (peering doesn't carry private DNS — it's a separate step).
- **ACR private endpoint reachability across peerings.** Same story — peered VNets must have `privatelink.azurecr.us` linked.

## Environments used

| # | Subscription | RG | Notes |
|---|---|---|---|
| 1 | `SUB-DGPS-EHB-PAAS-SDBX` (commercial sandbox) | `RG-EUS-DGPS-EHBS-PAAS-SDBX-DME` | First-pass validation. Deploy succeeded end-to-end after fixes. All test resources later cleaned up. |
| 2 | `ee913830-9d92-4f0d-a605-793467f1ea8d` (commercial dev) | `rei-hrsa-eastus2-rg-shared-dev` | Second-pass validation against a more realistic shared VNet. Surfaced DNS + subnet sizing issues. |

Both runs use the **commercial** cloud (`AzureCloud`); the bundled [deploy.sh](deploy.sh) hard-refuses anything other than `AzureUSGovernment`, so it was bypassed and `az deployment group create` was called directly.

---

## Issues encountered, in order

### 1. `deploy.sh` aborts in any non-Gov cloud

**Symptom:** `Active cloud is AzureCloud, expected AzureUSGovernment.`

**Cause:** The wrapper script enforces `AzureUSGovernment`. Reasonable for prod, but blocks any commercial-cloud sandbox test.

**Fix applied:** Bypassed for testing — called `az deployment group create` directly with explicit `--parameters`.

**Recommendation:** Add a `--allow-commercial` (or equivalent) flag, or document the direct `az` invocation in the README so testers don't have to read the script.

---

### 2. `main.gov.bicepparam` ships with empty placeholder values

**Symptom:** `validate` succeeds but the deployment fails with malformed resource IDs (see issue 5).

**Cause:** The bicepparam file had empty defaults for `infrastructureSubnetId`, `privateEndpointSubnetId`, `logAnalyticsWorkspaceId`. Empty strings are valid Bicep inputs but propagate into ARM as malformed resource IDs.

**Fix applied:** Filled the params for the target subscription:

```bicep
param infrastructureSubnetId = '/subscriptions/.../virtualNetworks/.../subnets/snet-aca-infra'
param privateEndpointSubnetId = '/subscriptions/.../virtualNetworks/.../subnets/default'
param logAnalyticsWorkspaceId = '/subscriptions/.../workspaces/log-hrsa-ent-int'
```

**Recommendation:** Remove the `''` defaults so missing values fail parameter validation immediately rather than during template execution.

---

### 3. Subnet prerequisites not stated in the template

**Symptom (sandbox run):** The supplied VNet only had `/24` subnets — none qualified as the infrastructure subnet.

**Cause:** The Container Apps managed environment module is **Consumption-only** ([modules/container-apps-env.bicep:2-3](modules/container-apps-env.bicep#L2)), which requires a **/23 minimum** infrastructure subnet delegated to `Microsoft.App/environments`. The template assumes this exists but does not validate it.

**Fix applied (sandbox):** Created `snet-aca-infra` (10.0.16.0/23, delegated `Microsoft.App/environments`) and `snet-aca-pe` (10.0.18.0/24, PE policies disabled) in the existing VNet.

**Recommendation:** Either (a) document the subnet sizing/delegation requirements at the top of [main.bicep](main.bicep), or (b) ship a companion `network.bicep` module that provisions them.

---

### 4. Container App name overflows the 32-char limit

**Symptom:** `ContainerAppInvalidName … must be between 2 and 32 characters inclusive` (with the shipped `deploymentEnvironment='sbx02'`, the frontend app name was 35 chars).

**Cause:** Naming scheme in [main.bicep:88-98](main.bicep#L88) produces:

```
ca-{regionAbbr}-dgps-ehbs-{deploymentEnvironment}-rpa-{ui|svc|frontend|backend}
```

With multi-char env tokens, the leaf name exceeds the Container Apps 32-char hard limit.

**Fix applied:** Shortened suffixes from `-frontend`/`-backend` to `-ui`/`-svc` in [main.bicep:91-92](main.bicep#L91). Result: `ca-eus-dgps-ehbs-dev-rpa-ui` (27 chars) ✓, `ca-eus-dgps-ehbs-dev-rpa-svc` (28 chars) ✓.

**Recommendation:** Add an `@minLength(1)/@maxLength(N)` decorator on `deploymentEnvironment` so this fails at parameter validation, not preflight.

---

### 5. Log Analytics workspace param accepted as a malformed ID

**Symptom:** `The resource identifier '/subscriptions/.../providers/Microsoft.OperationalInsights/' is malformed.`

**Cause:** When `logAnalyticsWorkspaceId` is empty, the workspace-name split in [modules/container-apps-env.bicep:20-24](modules/container-apps-env.bicep#L20) produces an empty workspace name and ARM rejects the constructed ID.

**Fix applied:** Filled the param with the real LAW resource ID.

**Recommendation:** Add `@minLength(1)` on `logAnalyticsWorkspaceId` in [main.bicep](main.bicep) so empty inputs fail at param validation.

---

### 6. Octopus variable tokens (`#{environmentName}`) break direct `az` invocation

**Symptom:** `ContainerAppInvalidImageFormat … 'creusdgpsehbssecrpa.azurecr.us/ehbs-#{environmentName}-svc:latest'`.

**Cause:** The bicepparam stored the image references with Octopus Deploy tokens (`#{...}`), which the Octopus pipeline substitutes before invoking Bicep. When run directly via `az deployment group create`, those tokens pass through unchanged.

**Fix applied:** Replaced `#{environmentName}` with Bicep interpolation `${environmentName}` in [main.gov.bicepparam:22-23](main.gov.bicepparam#L22). Octopus's substitution is a superset, so this still works in CI — but the file is now also directly runnable.

**Recommendation:** Keep `${environmentName}`. Octopus runs token substitution on the raw text *before* Bicep compilation; any `#{...}` tokens it owns will still be substituted, and any leftover `${...}` is resolved by Bicep at deploy time. Net result: the file works both for the Octopus pipeline (per the Gov flow above) and for direct `az deployment` invocations during development.

---

### 7. ACR `publicNetworkAccess=Disabled` + ACA control plane → 403

**Symptom:** `Failed to construct registry secret for registry 'creusdgpsehbssbrpa.azurecr.io' … 403 … client with IP '20.241.175.196' is not allowed access`.

**Cause:** The container app's `registries` config makes ACA's control plane fetch an AAD token from the ACR. The control-plane traffic originates from an Azure-managed public IP, not from inside the VNet. With `publicNetworkAccess=Disabled` and `networkRuleBypassOptions=AzureServices` set, the token endpoint still rejected the request.

Compounded by: the user-assigned Managed Identity created by the template has **no AcrPull role** on the ACR. The bicep README notes RBAC is "configured outside BICEP" but ships no companion script.

**Fix applied (sandbox):** Added a new `useAcrRegistry` toggle (default `true`, behavior unchanged) to:
- [main.bicep:72-73](main.bicep#L72)
- [modules/container-app.bicep:61-62](modules/container-app.bicep#L61)
- [modules/container-app.bicep:118-123](modules/container-app.bicep#L118)

Setting `useAcrRegistry=false` removes the ACR-linkage from the `registries` config and lets ACA pull anonymously from public registries (used in testing with `mcr.microsoft.com/azuredocs/aci-helloworld:latest`).

**Recommendation for prod:**
1. Add an automated AcrPull grant step (either a separate "RBAC" Bicep module run by a higher-privileged principal, or a `roleAssignments` resource in this template).
2. Decide on the production control-plane auth path: keep `publicNetworkAccess=Disabled` (which requires a workload-profile environment + trusted-services bypass) **or** allow public ACR access with `defaultAction=Deny` + explicit allowlist.

---

### 8. Custom DNS on the shared VNet can't resolve public hostnames

**Symptom:** `Failed to provision revision … failed to resolve registry 'mcr.microsoft.com': lookup mcr.microsoft.com on 100.100.247.68:53: server misbehaving`.

**Cause:** `VNET-HRSA-SHARED-DEV` has custom DNS servers configured (`10.10.0.4`, `192.168.4.121`, `10.96.3.123`, `10.96.3.126` — internal/on-prem resolvers). The Container Apps env inherits VNet DNS. Those resolvers don't forward unknown queries upstream, so `mcr.microsoft.com`, `*.azurecr.io`, `login.microsoftonline.com`, and ACA control-plane hostnames all return SERVFAIL.

**Workaround applied for testing:** Provisioned an isolated test VNet (`vnet-aca-test`, `10.50.0.0/20`) in the same RG, with no custom DNS and no peerings, and the two correctly-sized subnets. This avoids the DNS dependency entirely.

**Required for production (template doesn't depend on this — your network does):**
1. Configure the custom DNS servers to forward unresolvable queries to **Azure DNS `168.63.129.16`**, or another resolver that can answer public hostnames.
2. Link these private DNS zones to the production VNet:
   - `privatelink.azurecr.us` (Gov) or `privatelink.azurecr.io` (commercial) — so ACR's private endpoint name resolves to its private IP.
   - `privatelink.<region>.azurecontainerapps.us` (Gov) / `.io` (commercial) — auto-created by the ACA env; **must be linked to peered VNets** that need to resolve the frontend FQDN.
3. Confirm that `login.microsoftonline.us` / `.com` and `*.azurecontainerapps.us` resolve from inside the VNet before deploying.

---

### 9. ACA private DNS zone is NOT auto-created in this subscription

**Symptom:** From a jumpbox VM inside the same VNet as the ACA env, browser/SOCKS connections to the frontend FQDN failed with `channel N: open failed: connect failed: Name or service not known`. The jumpbox resolver returned NXDOMAIN for `<env-default-domain>` even though the env was internal and in the same VNet.

**Cause:** An internal Container Apps environment is *supposed* to auto-create a private DNS zone for its `defaultDomain` (e.g. `salmonriver-d05a35ea.eastus2.azurecontainerapps.io`) and auto-link it to the infrastructure-subnet VNet. In this test deploy, **no such private DNS zone exists in the subscription** (`az network private-dns zone list` returns `[]`). Likely causes:
- The subscription has an Azure Policy that blocks `Microsoft.Network/privateDnsZones` creation (common in Gov / regulated subs).
- The deploying principal lacks `Microsoft.Network/privateDnsZones/write` and the auto-create silently no-op'd.
- A previously-orphaned zone was hard-deleted; the env keeps cached references.

**Workaround used for the test (jumpbox):** Manually added `/etc/hosts` entries on the jumpbox pointing both the frontend and backend FQDNs to the env's `staticIp` (`10.50.0.200`). The env's ingress routes by `Host:` header, so a single IP serves both apps.

**Required for production (template doesn't currently handle this):**

The bicep should **explicitly create the private DNS zone and link it to the VNet** rather than relying on auto-create. Add to `modules/container-apps-env.bicep` (or a new `private-dns.bicep` module) something like:

```bicep
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: managedEnv.properties.defaultDomain
  location: 'global'
}

resource privateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: 'link-${last(split(infrastructureSubnetId, '/'))}'  // unique per VNet
  location: 'global'
  properties: {
    virtualNetwork: { id: <vnet-id-derived-from-subnet> }
    registrationEnabled: false
  }
}

resource appWildcardRecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = {
  parent: privateDnsZone
  name: '*'
  properties: {
    ttl: 3600
    aRecords: [ { ipv4Address: managedEnv.properties.staticIp } ]
  }
}
```

The same zone (or equivalent records) must also be **linked to every peered VNet** that needs to reach the apps (EHB Web, EHB DB per OIT requirement).

**Recommendation:** Add this as an explicit step in the deployment, both because auto-create is unreliable and because Gov subs often block the silent path entirely.

---

## What ended up working

In the sandbox subscription, with all the fixes above applied and using `useAcrRegistry=false` + public test images, the full stack deployed and both apps reached `Healthy`:

- Managed Identity ✓
- App Insights (workspace-linked) ✓
- ACR (Premium) + Private Endpoint ✓
- Container Apps managed environment (internal, VNet-injected) ✓
- Backend Container App (internal ingress) ✓
- Frontend Container App (VNet-reachable) ✓

All sandbox test resources were deleted after verification.

---

## Outstanding work before Gov rollout

| # | Item | Owner |
|---|---|---|
| 1 | Add automated AcrPull role assignment to the deployment story (template + RBAC step) | App team |
| 2 | Decide ACR control-plane auth path: workload-profile env vs. public-with-allowlist | App + Network team |
| 3 | Provision the two required subnets in the production VNet (/23 infra + PE subnet) | Network team |
| 4 | Configure custom DNS resolvers to forward unresolvable queries to Azure DNS | Network team |
| 5 | Link `privatelink.azurecr.us` and `privatelink.<region>.azurecontainerapps.us` to the Gov VNet **and** to the peered EHB Web / EHB DB VNets | Network team |
| 6 | Confirm OIT's VNet is peered with EHB Web and EHB DB (per OIT requirement) | Network team |
| 7 | Get an Azure OpenAI endpoint provisioned (currently a placeholder in [main.gov.bicepparam:18](main.gov.bicepparam#L18)) | OM / App team |
| 8 | Octopus pipeline: ensure ACR push step completes before the Bicep deploy step (apps fail to pull otherwise) | DevOps / App team |
| 9 | Tighten parameter validation in the template (min-length on string params; sized constraint on `deploymentEnvironment`) | App team |
| 10 | Explicitly create the ACA private DNS zone in Bicep (auto-create is unreliable; see [issue 9](#9-aca-private-dns-zone-is-not-auto-created-in-this-subscription)). Link it to the deploy VNet **and** to each peered VNet that needs to resolve the apps. | App + Network team |

---

## Production deployment scripts (added after testing)

To roll the lessons above into the actual pipeline, two one-shot orchestrators
were added. They are intended to be the *only* entry point Octopus invokes
after it has built the image and pushed the TAR to ACR.

| Script | Use from |
|---|---|
| [deploy-prod.sh](deploy-prod.sh)   | bash (Linux Octopus workers, manual macOS/WSL test) |
| [deploy-prod.ps1](deploy-prod.ps1) | PowerShell 5.1+/7+ (Windows Octopus workers) |

Both scripts do the same thing, with identical input variables and exit codes:

1. **Preflight (fails fast):**
   - All required inputs present (no leftover `#{...}` tokens).
   - Container app name ≤32 chars (catches issue 4 from above before ARM sees it).
   - Logged into Azure, correct subscription set, Gov cloud matches Gov location.
   - All required resource providers registered.
   - Infrastructure subnet is `/23` or larger and delegated `Microsoft.App/environments`.
   - Private-endpoint subnet exists.
2. **Bicep deploy:** `validate` → `what-if` → `create`, with parameters passed
   inline (so Octopus's `#{...}` token substitution and Bicep's `${...}`
   interpolation both work and don't fight).
3. **Post-deploy** (the stuff not in the bicep, surfaced by issues 7 & 9):
   - Grants `AcrPull` on the deployed ACR to the deployed managed identity.
     If RBAC fails, prints the exact command for a User Access Administrator
     to run and continues.
   - Provisions the ACA env's private DNS zone *explicitly* (auto-create is
     unreliable — see issue 9). Wildcard `A` record → env static IP.
   - Links the zone to the deploy VNet **and** every VNet in
     `PEERED_VNET_IDS` (the EHB Web/DB requirement from OIT).
4. **Verification:** polls until both apps report `Running` + `Healthy`, or
   exits with a clear warning after 5 minutes.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Deploy succeeded end-to-end. |
| 1 | Preflight failure — nothing was deployed. |
| 2 | Bicep deploy failed. |
| 3 | Bicep succeeded but a post-deploy step needs attention (RBAC, DNS link, or health check). |

The non-zero exit codes are meant to be distinguishable by Octopus so the
runbook can branch on them (e.g. fail-the-release vs. notify-and-continue).

### Required environment variables (or Octopus tokens)

`SUBSCRIPTION`, `RESOURCE_GROUP`, `LOCATION`, `REGION_ABBR`,
`DEPLOYMENT_ENVIRONMENT`, `ENVIRONMENT_NAME`,
`INFRA_SUBNET_ID`, `PE_SUBNET_ID`, `LAW_ID`,
`ACR_LOGIN_SERVER`, `FRONTEND_IMAGE_TAG`, `BACKEND_IMAGE_TAG`,
`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`.

Optional: `CORS_ALLOWED_ORIGINS`, `PEERED_VNET_IDS` (space-separated full
resource IDs of EHB Web/DB VNets).

The `.EXAMPLE` block at the top of [deploy-prod.ps1](deploy-prod.ps1) and
the comment block at the top of [deploy-prod.sh](deploy-prod.sh) have
copy-paste-ready setup blocks for manual runs.

---

## Template diffs introduced during testing (kept)

| File | Change |
|---|---|
| [main.bicep](main.bicep) | Added `useAcrRegistry` parameter and wired through both apps. Default `true` — behavior unchanged for existing callers. |
| [modules/container-app.bicep](modules/container-app.bicep) | Made `registries` config conditional on `useAcrRegistry`. Also accepts bare-name `managedIdentityId` (not just full resource ID). |
| [modules/container-apps-env.bicep](modules/container-apps-env.bicep) | Accepts bare-name `logAnalyticsWorkspaceId` (not just full resource ID). |
| [main.gov.bicepparam](main.gov.bicepparam) | Replaced Octopus `#{environmentName}` tokens with Bicep `${environmentName}` interpolation. Filled in real subscription-specific subnet / LAW IDs. |
| [deploy-prod.sh](deploy-prod.sh) | New — bash orchestrator: preflight + bicep + post-deploy RBAC/DNS + verification. See above. |
| [deploy-prod.ps1](deploy-prod.ps1) | New — PowerShell equivalent of `deploy-prod.sh`. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | New — Mermaid topology diagram + reachability/ops notes for tech support. |
| [DEPLOYMENT_TEST_LOG.md](DEPLOYMENT_TEST_LOG.md) | This file. |

---

## Reproducing the working deploy (commercial test path)

```bash
RG=<your-rg>
SUB=$(az account show --query id -o tsv)
INFRA="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/snet-aca-infra"
PE="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/snet-aca-pe"
LAW="/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.OperationalInsights/workspaces/<law-name>"

az deployment group create \
  --resource-group "$RG" \
  --name "hrsa-rpa-ava-test-$(date -u +%Y%m%d%H%M%S)" \
  --template-file main.bicep \
  --parameters \
      location=eastus2 regionAbbr=eus deploymentEnvironment=dev environmentName=sbx \
      logAnalyticsWorkspaceId="$LAW" \
      infrastructureSubnetId="$INFRA" privateEndpointSubnetId="$PE" \
      frontendImage="mcr.microsoft.com/azuredocs/aci-helloworld:latest" \
      backendImage="mcr.microsoft.com/azuredocs/aci-helloworld:latest" \
      frontendTargetPort=80 backendTargetPort=80 \
      azureOpenAiEndpoint="https://dummy.openai.azure.com/" \
      azureOpenAiDeployment="gpt-4" \
      useAcrRegistry=false
```

For the real Gov deploy, set `useAcrRegistry=true` (default), use real Gov ACR image references, and ensure all outstanding-work items above are addressed first.
