#!/usr/bin/env bash
#
# Deploy JobSeeker to Azure App Service as plain code.
#
# Why not a container: this engine has no Python dependencies, so there is
# nothing to build. App Service runs it directly from a zip, which means no
# container registry to pay for and no image build step to be blocked by. Azure
# for Students does not permit ACR Tasks, so the container route cannot build
# server side anyway.
#
# Persistence: /home on App Service Linux is a durable share, so the SQLite
# database and the generated PDFs survive restarts and redeploys.

set -euo pipefail

LOCATION="${LOCATION:-francecentral}"
GROUP="${GROUP:-jobseeker-rg}"
APP="${APP:-jobseeker-$(az account show --query id -o tsv | tr -d '-' | cut -c1-8)}"
PLAN="${PLAN:-jobseeker-plan}"
SKU="${SKU:-F1}"
RUNTIME="${RUNTIME:-PYTHON:3.13}"

say() { printf "\n\033[36m==>\033[0m %s\n" "$1"; }
warn() { printf "\033[33m !\033[0m %s\n" "$1"; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Read .env without letting the shell touch it. `source` expands $ inside
# unquoted values, which silently destroys a scrypt hash, so the file is parsed
# in Python and the values are exported verbatim.
if [[ -f .env ]]; then
  while IFS= read -r assignment; do
    [[ -n "$assignment" ]] && export "${assignment?}"
  done < <(python3 - <<'PYEOF'
import pathlib
for raw in pathlib.Path(".env").read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    # Only fill gaps: anything already exported by the caller wins.
    import os
    if not os.environ.get(key):
        print(f"{key}={value}")
PYEOF
)
fi

if [[ -z "${API_TOKEN:-}" ]]; then
  echo "API_TOKEN is not set. Generate one and export it first:"
  echo "  export API_TOKEN=\$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  exit 1
fi
if [[ -z "${AUTH_PASSWORD_HASH:-}" ]]; then
  echo "AUTH_PASSWORD_HASH is not set, so the dashboard would have no sign in."
  echo "Set a password first:  ./run set-password"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say "Building the dashboard"
if [[ ! -d dashboard/node_modules ]]; then
  (cd dashboard && npm install --no-audit --no-fund)
fi
(cd dashboard && npm run build)

say "Packaging"
PACKAGE="$(mktemp -d)/jobseeker.zip"
# Only what the server needs at runtime. No .env, no local database, no secrets.
python3 - "$PACKAGE" <<'PYEOF'
import pathlib, sys, zipfile

root = pathlib.Path.cwd()
target = pathlib.Path(sys.argv[1])
skip_parts = {"__pycache__", "node_modules", ".git", ".vite"}

def include(path: pathlib.Path) -> bool:
    if any(part in skip_parts for part in path.parts):
        return False
    if path.suffix in {".pyc", ".db", ".db-wal", ".db-shm"}:
        return False
    return True

with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
    for source in ("jobseeker", "dashboard/dist"):
        for path in pathlib.Path(source).rglob("*"):
            if path.is_file() and include(path):
                bundle.write(path, path.as_posix())
    # Every JSON in data/ is configuration the engine reads at runtime. Listing
    # them by hand meant a new one (companies.json) shipped without its data.
    for path in sorted(pathlib.Path("data").glob("*.json")):
        bundle.write(path, path.as_posix())
    # The master CV is attached to every application, so it has to travel too.
    for path in sorted(pathlib.Path("data").glob("*.pdf")):
        bundle.write(path, path.as_posix())

size = target.stat().st_size
print(f"  packaged {size/1024:.0f} KiB")
PYEOF

say "Resource group: $GROUP ($LOCATION)"
az group create --name "$GROUP" --location "$LOCATION" --output none

say "App Service plan: $PLAN ($SKU, Linux)"
az appservice plan create --name "$PLAN" --resource-group "$GROUP" \
  --location "$LOCATION" --is-linux --sku "$SKU" --output none

say "Web app: $APP"
if ! az webapp show --name "$APP" --resource-group "$GROUP" --output none 2>/dev/null; then
  az webapp create --name "$APP" --resource-group "$GROUP" --plan "$PLAN" \
    --runtime "$RUNTIME" --output none
fi

# A new deployment ships disarmed. A redeploy must not silently re-arm or
# disarm something the owner already decided, so the existing value is kept.
EXISTING_SEND=$(az webapp config appsettings list --name "$APP" --resource-group "$GROUP" \
  --query "[?name=='SEND_ENABLED'].value" -o tsv 2>/dev/null || echo "")
# The deployed value is the source of truth: it reflects a decision made on the
# running service. A local .env must not reach across and change it, so an
# override has to be explicit and differently named.
SEND_ENABLED_VALUE="${DEPLOY_SEND_ENABLED:-${EXISTING_SEND:-false}}"

say "Configuration (live sending: $SEND_ENABLED_VALUE)"
# Secrets are app settings, which are encrypted at rest and never in the zip.
az webapp config appsettings set --name "$APP" --resource-group "$GROUP" --output none \
  --settings \
    API_TOKEN="$API_TOKEN" \
    AUTH_PASSWORD_HASH="$AUTH_PASSWORD_HASH" \
    ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}" \
    SMTP_PASSWORD="${SMTP_PASSWORD:-}" \
    SENDER_EMAIL="${SENDER_EMAIL:-}" \
    SENDER_NAME="${SENDER_NAME:-}" \
    IMAP_USER="${IMAP_USER:-}" \
    IMAP_PASSWORD="${IMAP_PASSWORD:-${SMTP_PASSWORD:-}}" \
    DIGEST_TO="${DIGEST_TO:-}" \
    SEND_ENABLED="$SEND_ENABLED_VALUE" \
    AUTO_REPLY=draft \
    AUTO_APPROVE_SCORE=0 \
    DB_PATH=/home/data/jobseeker.db \
    LETTERS_DIR=/home/data/letters \
    CV_DIR=/home/data/cv \
    PROFILE_PATH=data/profile.illona.json \
    CV_MODE="${CV_MODE:-master}" \
    BOARDS_PATH=data/boards.json \
    SQLITE_JOURNAL_MODE=TRUNCATE \
    PYTHONPATH=/home/site/wwwroot \
    PYTHONUNBUFFERED=1 \
    SCM_DO_BUILD_DURING_DEPLOYMENT=false \
    WEBSITES_ENABLE_APP_SERVICE_STORAGE=true

# App Service hands the port in as $PORT and expects the process to bind 0.0.0.0.
az webapp config set --name "$APP" --resource-group "$GROUP" --output none \
  --startup-file 'python -m jobseeker serve --host 0.0.0.0 --port $PORT' \
  --always-on false

say "Deploying the package"
az webapp deploy --name "$APP" --resource-group "$GROUP" \
  --src-path "$PACKAGE" --type zip --output none

URL="https://$(az webapp show --name "$APP" --resource-group "$GROUP" --query defaultHostName -o tsv)"

say "Setting the dashboard URL for the digest emails"
az webapp config appsettings set --name "$APP" --resource-group "$GROUP" --output none \
  --settings DASHBOARD_URL="$URL" >/dev/null

say "Deployed"
cat <<SUMMARY

  Dashboard   $URL
  Sign in     with the password you set locally
  API token   $API_TOKEN

  Live sending is OFF. Turn it on deliberately, later:
    az webapp config appsettings set --name $APP --resource-group $GROUP \\
      --settings SEND_ENABLED=true

  Logs:
    az webapp log tail --name $APP --resource-group $GROUP

SUMMARY

warn "This app can send email as you. Put a login in front of it before you rely on it."
echo "  az webapp auth microsoft update --name $APP --resource-group $GROUP \\"
echo "    --client-id <application-id> --tenant-id <tenant-id> \\"
echo "    --allowed-audiences \"$URL/.auth/login/aad/callback\""
echo
echo "Save for the GitHub Actions workflow:  AZURE_WEBAPP=$APP  AZURE_RESOURCE_GROUP=$GROUP"
