#!/usr/bin/env bash
#
# One shot Azure deployment for JobSeeker on a student subscription.
#
# Creates a resource group, a storage account with a file share (so the SQLite
# database and the generated PDFs survive a restart), a container registry, a
# Container Apps environment, and one app scaled to zero when idle.
#
# Safe to re run: it reuses anything that already exists and rolls the app onto
# a freshly built image.
#
# Before you start:  az login  &&  az account set --subscription "<subscription>"

set -euo pipefail

# Azure for Students restricts which regions a subscription may deploy into.
# On this subscription the permitted set is francecentral, germanywestcentral,
# switzerlandnorth and italynorth. francecentral is the closest to Accra.
# Probe your own with: az storage account create --location <region> ...
LOCATION="${LOCATION:-francecentral}"
GROUP="${GROUP:-jobseeker-rg}"
APP="${APP:-jobseeker}"
ENVIRONMENT="${ENVIRONMENT:-jobseeker-env}"
SHARE="${SHARE:-jobseeker-data}"
STORAGE_LINK="${STORAGE_LINK:-jobseekerdata}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"

say() { printf "\n\033[36m==>\033[0m %s\n" "$1"; }
warn() { printf "\033[33m !\033[0m %s\n" "$1"; }

if [[ -z "${API_TOKEN:-}" ]]; then
  echo "API_TOKEN is not set. Generate one and export it first:"
  echo "  export API_TOKEN=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  exit 1
fi

# A deployment without a sign in password would put a dashboard that can send
# email as you on a public URL. Refuse, rather than deploy something open.
if [[ -z "${AUTH_PASSWORD_HASH:-}" ]]; then
  echo "AUTH_PASSWORD_HASH is not set, so the dashboard would have no sign in."
  echo "Set a password first:"
  echo "  ./run set-password"
  echo "then re run this script from the same shell (it reads .env)."
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Storage account and registry names must be globally unique and alphanumeric.
# They are derived from the subscription id so re running picks the same names
# rather than leaking a new resource on every run.
SUFFIX=$(az account show --query id -o tsv | tr -d '-' | cut -c1-8)
STORAGE="${STORAGE:-jobseeker${SUFFIX}}"
REGISTRY="${REGISTRY:-jobseekeracr${SUFFIX}}"

say "Making sure the containerapp extension is present"
az extension add --name containerapp --upgrade --only-show-errors >/dev/null 2>&1 || true

say "Registering resource providers (first run only, this can take a few minutes)"
for provider in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.Storage; do
  state=$(az provider show --namespace "$provider" --query registrationState -o tsv 2>/dev/null || echo "NotRegistered")
  if [[ "$state" != "Registered" ]]; then
    echo "    registering $provider"
    az provider register --namespace "$provider" --wait
  fi
done

say "Resource group: $GROUP ($LOCATION)"
az group create --name "$GROUP" --location "$LOCATION" --output none

say "Storage account: $STORAGE"
az storage account create \
  --name "$STORAGE" --resource-group "$GROUP" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --output none
STORAGE_KEY=$(az storage account keys list --account-name "$STORAGE" \
  --resource-group "$GROUP" --query "[0].value" -o tsv)

say "File share: $SHARE"
az storage share create --name "$SHARE" --account-name "$STORAGE" \
  --account-key "$STORAGE_KEY" --quota 5 --output none

say "Container registry: $REGISTRY"
az acr create --name "$REGISTRY" --resource-group "$GROUP" --sku Basic \
  --admin-enabled true --output none

say "Building the image in Azure (no local Docker needed). This takes a few minutes."
az acr build --registry "$REGISTRY" \
  --image "jobseeker:$IMAGE_TAG" --image "jobseeker:latest" \
  --file deploy/Dockerfile . --output none

REGISTRY_SERVER="$REGISTRY.azurecr.io"
REGISTRY_PASSWORD=$(az acr credential show --name "$REGISTRY" --query "passwords[0].value" -o tsv)

say "Container Apps environment: $ENVIRONMENT"
if ! az containerapp env show --name "$ENVIRONMENT" --resource-group "$GROUP" --output none 2>/dev/null; then
  az containerapp env create --name "$ENVIRONMENT" --resource-group "$GROUP" \
    --location "$LOCATION" --output none
fi

say "Attaching the file share to the environment"
az containerapp env storage set --name "$ENVIRONMENT" --resource-group "$GROUP" \
  --storage-name "$STORAGE_LINK" \
  --azure-file-account-name "$STORAGE" \
  --azure-file-account-key "$STORAGE_KEY" \
  --azure-file-share-name "$SHARE" \
  --access-mode ReadWrite --output none

ENVIRONMENT_ID=$(az containerapp env show --name "$ENVIRONMENT" --resource-group "$GROUP" --query id -o tsv)

# The app is described by a complete manifest rather than a pile of flags,
# because the volume mount can only be expressed this way, and because a full
# manifest makes a re run idempotent.
MANIFEST="$(mktemp -t jobseeker-app).yaml"
say "Writing the app manifest"
LOCATION="$LOCATION" APP="$APP" ENVIRONMENT_ID="$ENVIRONMENT_ID" \
REGISTRY_SERVER="$REGISTRY_SERVER" REGISTRY="$REGISTRY" \
REGISTRY_PASSWORD="$REGISTRY_PASSWORD" IMAGE_TAG="$IMAGE_TAG" \
API_TOKEN="$API_TOKEN" STORAGE_LINK="$STORAGE_LINK" \
AUTH_PASSWORD_HASH="$AUTH_PASSWORD_HASH" \
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" SMTP_PASSWORD="${SMTP_PASSWORD:-}" \
SENDER_EMAIL="${SENDER_EMAIL:-}" SENDER_NAME="${SENDER_NAME:-}" \
IMAP_PASSWORD="${IMAP_PASSWORD:-}" \
python3 - "$MANIFEST" <<'PYEOF'
import json, os, sys

def secret(name, value):
    return {"name": name, "value": value} if value else None

secrets = [
  secret("api-token", os.environ["API_TOKEN"]),
    secret("auth-password-hash", os.environ["AUTH_PASSWORD_HASH"]),
    secret("registry-password", os.environ["REGISTRY_PASSWORD"]),
    secret("anthropic-key", os.environ.get("ANTHROPIC_API_KEY")),
    secret("smtp-password", os.environ.get("SMTP_PASSWORD")),
    secret("imap-password", os.environ.get("IMAP_PASSWORD") or os.environ.get("SMTP_PASSWORD")),
]
secrets = [s for s in secrets if s]
names = {s["name"] for s in secrets}

env = [
    {"name": "API_TOKEN", "secretRef": "api-token"},
    {"name": "AUTH_PASSWORD_HASH", "secretRef": "auth-password-hash"},
    {"name": "DB_PATH", "value": "/data/jobseeker.db"},
    {"name": "LETTERS_DIR", "value": "/data/letters"},
    {"name": "CV_DIR", "value": "/data/cv"},
    # Azure Files is SMB, which cannot support SQLite's WAL shared memory.
    {"name": "SQLITE_JOURNAL_MODE", "value": "TRUNCATE"},
    # Live sending stays off on a fresh deployment, always.
    {"name": "SEND_ENABLED", "value": "false"},
    {"name": "PORT", "value": "8000"},
]
if "anthropic-key" in names:
    env.append({"name": "ANTHROPIC_API_KEY", "secretRef": "anthropic-key"})
if "smtp-password" in names:
    env.append({"name": "SMTP_PASSWORD", "secretRef": "smtp-password"})
if "imap-password" in names:
    env.append({"name": "IMAP_PASSWORD", "secretRef": "imap-password"})
for key in ("SENDER_EMAIL", "SENDER_NAME"):
    if os.environ.get(key):
        env.append({"name": key, "value": os.environ[key]})

manifest = {
    "location": os.environ["LOCATION"],
    "type": "Microsoft.App/containerApps",
    "name": os.environ["APP"],
    "properties": {
        "managedEnvironmentId": os.environ["ENVIRONMENT_ID"],
        "configuration": {
            "activeRevisionsMode": "Single",
            "ingress": {
                "external": True,
                "targetPort": 8000,
                "transport": "auto",
                "allowInsecure": False,
                "traffic": [{"latestRevision": True, "weight": 100}],
            },
            "registries": [
                {
                    "server": os.environ["REGISTRY_SERVER"],
                    "username": os.environ["REGISTRY"],
                    "passwordSecretRef": "registry-password",
                }
            ],
            "secrets": secrets,
        },
        "template": {
            "containers": [
                {
                    "image": f"{os.environ['REGISTRY_SERVER']}/jobseeker:{os.environ['IMAGE_TAG']}",
                    "name": "jobseeker",
                    "env": env,
                    "resources": {"cpu": 0.5, "memory": "1.0Gi"},
                    "volumeMounts": [{"volumeName": "data", "mountPath": "/data"}],
                }
            ],
            "scale": {"minReplicas": 0, "maxReplicas": 1},
            "volumes": [
                {
                    "name": "data",
                    "storageName": os.environ["STORAGE_LINK"],
                    "storageType": "AzureFile",
                }
            ],
        },
    },
}

# YAML is a superset of JSON, and the CLI parses either, so emitting JSON avoids
# needing a YAML library in a zero dependency project.
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)
PYEOF

if az containerapp show --name "$APP" --resource-group "$GROUP" --output none 2>/dev/null; then
  say "Updating the existing app"
  az containerapp update --name "$APP" --resource-group "$GROUP" \
    --yaml "$MANIFEST" --output none
else
  say "Creating the app"
  az containerapp create --name "$APP" --resource-group "$GROUP" \
    --yaml "$MANIFEST" --output none
fi
rm -f "$MANIFEST"

URL=$(az containerapp show --name "$APP" --resource-group "$GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

say "Deployed"
cat <<SUMMARY

  Dashboard   https://$URL
  API token   $API_TOKEN

  Sign in with the password you set with ./run set-password.
  The API token is only for machine access, such as the scheduled workflow.
  Paste it under Profile, API access if you want the dashboard to use it too.

  Live sending is OFF. Turn it on deliberately, later:
    az containerapp update --name $APP --resource-group $GROUP \\
      --set-env-vars SEND_ENABLED=true

SUMMARY

warn "This app can send email as you. Put a login in front of it before you rely on it."
cat <<'NEXT'
    Create an Entra ID app registration with redirect URI
      https://<the url above>/.auth/login/aad/callback
    then:
      az containerapp auth microsoft update --name jobseeker --resource-group jobseeker-rg \
        --client-id <application-id> --tenant-id <tenant-id> --yes
      az containerapp auth update --name jobseeker --resource-group jobseeker-rg \
        --unauthenticated-client-action RedirectToLoginPage

NEXT

echo "Save these for the GitHub Actions deploy workflow:"
echo "  AZURE_REGISTRY=$REGISTRY   AZURE_RESOURCE_GROUP=$GROUP   AZURE_CONTAINER_APP=$APP"
