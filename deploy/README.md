# Deploying JobSeeker

Two ways to run this in Azure. The first is the one to use.

---

## Option 1: one Container App (recommended)

The container serves the API and the dashboard on the same origin, so there is
one thing to deploy, one URL, and one login to configure. It scales to zero when
nobody is using it, so an idle month costs roughly the price of the storage.

### What gets created

| Resource | Why |
| --- | --- |
| Resource group | everything in one place, easy to delete |
| Storage account + file share | the SQLite database and the generated PDFs, mounted at `/data` |
| Container registry (Basic) | holds the image, built in Azure so you do not need Docker locally |
| Container Apps environment + app | 0.5 vCPU, 1 GiB, scaled to zero |

### Steps

```bash
az login
az account set --subscription "<your subscription>"

export API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
export ANTHROPIC_API_KEY=...      # optional
export SENDER_EMAIL=...           # optional, only needed to send
export SMTP_PASSWORD=...          # a Gmail app password, not your account password

./deploy/azure.sh
```

The script prints the URL and the API token when it finishes. Open the URL, go
to **Profile, API access**, paste the token, save.

### Lock it down before you use it

The deployed app can send email as you. Do not leave it reachable by anyone with
the URL. Container Apps has built in authentication, so no code changes are
needed:

1. Create an app registration in Microsoft Entra ID with the redirect URI
   `https://<your-app-url>/.auth/login/aad/callback`.
2. Then:

```bash
az containerapp auth microsoft update \
  --name jobseeker --resource-group jobseeker-rg \
  --client-id <application-id> --tenant-id <tenant-id> --yes

az containerapp auth update \
  --name jobseeker --resource-group jobseeker-rg \
  --unauthenticated-client-action RedirectToLoginPage
```

Now the whole app is behind your Microsoft login, and the API token is a second
layer for anything calling it directly, such as the scheduled workflow.

### Changing or resetting the password

Three ways, in the order you should reach for them.

**1. You are signed in and want a new password.**
Dashboard, Profile, Sign in password. It stores the new hash in the database on
the mounted volume, so it survives restarts and redeploys, and it ends every
other signed in session immediately.

**2. You are locked out.** Run the CLI inside the running container:

```bash
az containerapp exec --name jobseeker --resource-group jobseeker-rg \
  --command "python3 -m jobseeker set-password --db"
```

It prompts twice and takes effect at once, with no restart. For a scripted
version, pipe it in:

```bash
az containerapp exec --name jobseeker --resource-group jobseeker-rg \
  --command "sh -c 'echo my-new-password | python3 -m jobseeker set-password --db --stdin'"
```

**3. You want to go back to the deployed secret.** A password set from the
dashboard lives in the database and takes precedence over `AUTH_PASSWORD_HASH`,
so changing the Azure secret alone does nothing until the database value is
removed:

```bash
# clear the database value
az containerapp exec --name jobseeker --resource-group jobseeker-rg \
  --command "python3 -m jobseeker set-password --clear-db"

# then set the secret it falls back to
./run set-password                      # generates the hash locally, into .env
az containerapp secret set --name jobseeker --resource-group jobseeker-rg \
  --secrets auth-password-hash="<the AUTH_PASSWORD_HASH line from .env>"
```

There is deliberately no reset by email. The whole point of the password is that
the mailbox is what it protects.

### Turning on live sending

It ships off. Turn it on when you have read a few drafts and trust them:

```bash
az containerapp update --name jobseeker --resource-group jobseeker-rg \
  --set-env-vars SEND_ENABLED=true
```

Approval is still required per application. The switch only allows an approved
application to leave the building.

### Deploying updates

Either re run `./deploy/azure.sh`, or let GitHub Actions do it. For the workflow
in `.github/workflows/deploy.yml`:

```bash
az ad sp create-for-rbac --name jobseeker-deploy --role contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/jobseeker-rg --sdk-auth
```

Put the JSON in the repository secret `AZURE_CREDENTIALS`, and set the repository
variables `AZURE_RESOURCE_GROUP`, `AZURE_CONTAINER_APP` and `AZURE_REGISTRY`.

### The scheduled run

`.github/workflows/daily.yml` runs discover, score, draft, replies and follow up
checks every weekday at 06:00 Ghana time, against the deployed API. It never
sends: drafts wait in the dashboard for you.

Set the repository variable `JOBSEEKER_URL` to your app URL and the secret
`JOBSEEKER_API_TOKEN` to the token. If you put Entra ID in front of the app, give
the workflow its own path by adding the token check only, or run the schedule as
a Container Apps job instead:

```bash
az containerapp job create \
  --name jobseeker-daily --resource-group jobseeker-rg \
  --environment jobseeker-env --trigger-type Schedule \
  --cron-expression "0 6 * * 1-5" \
  --image <registry>.azurecr.io/jobseeker:latest \
  --command "/bin/sh" --args "-c","python3 -m jobseeker daily"
```

---

## Option 2: Static Web Apps for the dashboard only

Useful if you want the dashboard on a custom domain and the engine somewhere
else. Build the dashboard, deploy `dashboard/dist` to Static Web Apps, and point
it at the API with `VITE_API_TARGET`. You then have two origins and two things to
secure, which is why option 1 is the default.

---

## Running the container locally

```bash
docker build -f deploy/Dockerfile -t jobseeker .
docker run --rm -p 8000:8000 \
  -e API_TOKEN=local-token \
  -v "$PWD/.data:/data" \
  jobseeker
```

## Cost, roughly

With scale to zero and a 5 GiB file share, an idle deployment on a student
subscription is a few pence a month. The cost that matters is the Anthropic API,
which is a fraction of a cent per drafted application, and only if you use the
Claude writer.
