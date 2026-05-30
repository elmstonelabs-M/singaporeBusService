# GitHub Actions Setup

This guide explains how to connect the repository to the production server release workflow.

Main workflow:

- [.github/workflows/release-prod.yml](D:\developwork\singaporeBusService\.github\workflows\release-prod.yml)

## 1. Open repository settings

In GitHub:

1. Open the `singaporeBusService` repository
2. Go to `Settings`
3. Go to `Secrets and variables`
4. Open `Actions`

Create the following repository secrets.

## 2. Required secrets

### `PROD_SSH_HOST`

Production server IP or hostname.

Current value:

```text
35.197.135.48
```

### `PROD_SSH_PORT`

SSH port for the production server.

Current value:

```text
22
```

### `PROD_SSH_USER`

Deployment user on the production server.

Current value:

```text
devlop
```

### `PROD_SSH_PRIVATE_KEY`

Paste the full private key content for the deployment user.

Example format:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

Notes:

- keep line breaks intact
- do not wrap it in quotes
- use a deployment-only key if you want tighter separation later

### `PROD_DEPLOY_PATH`

Absolute path to the deployed repository on the server.

Current value:

```text
/home/devlop/singaporeBusService
```

### `PROD_HEALTH_URL`

Health check URL used after release.

Recommended current value:

```text
http://127.0.0.1:8000/health
```

Why local health is recommended:

- it verifies the app directly on the server
- it avoids Cloudflare or external DNS being the reason a deployment job fails
- Nginx and public-domain checks can still be done as a second-step verification

## 3. Recommended GitHub environment

Create a GitHub environment named:

```text
production
```

This matches the workflow configuration and gives you a place to add:

- required reviewers before deployment
- environment-scoped secrets later if needed
- deployment history in GitHub UI

## 4. Recommended branch rule

If you want safer production releases, protect `main` and require:

- pull request merge instead of direct push
- passing checks before merge
- at least one reviewer

The current workflow triggers automatically on push to `main`, so branch protection is the cleanest way to keep release quality stable.

## 5. How to trigger a release

### Automatic release

Push or merge to:

```text
main
```

GitHub Actions will run the production workflow automatically.

### Manual release

In GitHub:

1. Open `Actions`
2. Open `Release Production`
3. Click `Run workflow`
4. Choose the branch
5. Optionally set:
   - `skip_backup`
   - `skip_sync_static_data`
6. Run it

## 6. What the workflow does

The release workflow will:

1. Check out the latest repository code
2. Load the SSH private key from GitHub Secrets
3. Trust the server host key
4. `rsync` the repository to the production server
5. Preserve `.env.production` and `backups/` on the server
6. Run [scripts/release_prod.sh](D:\developwork\singaporeBusService\scripts\release_prod.sh)

## 7. First-run checklist

Before the first GitHub-triggered release, confirm on the server:

1. `.env.production` already exists
2. Docker, Compose, and Nginx are already installed
3. `trackbusapi.sgbtt.top` is already serving the current deployment
4. `/home/devlop/singaporeBusService` already exists
5. the SSH key in `PROD_SSH_PRIVATE_KEY` can log in as `devlop`

## 8. Recommended first test

Use a manual run first.

Recommended first test settings:

- branch: the branch containing this workflow
- `skip_backup`: `false`
- `skip_sync_static_data`: `true`

This gives you a safer first validation:

- backup still runs
- migration and API deploy still run
- static data sync is skipped for speed and lower noise

After the first manual run succeeds, normal push-to-`main` release is much lower risk.

## 9. Common failure points

### SSH authentication failure

Usually means:

- private key content is wrong
- wrong server user
- public key is not installed in `authorized_keys`

### `rsync` path failure

Usually means:

- `PROD_DEPLOY_PATH` is wrong
- target directory does not exist
- target user cannot write to that directory

### Release script fails on server

Usually means:

- `.env.production` is missing or outdated
- Docker service is not running
- migration failed
- application startup failed

### Health check failure

Usually means:

- API container did not come up correctly
- app boot failed after code sync
- local `127.0.0.1:8000/health` is not returning success

## 10. Suggested release conversation command

In your dedicated deployment chat, use:

```text
release singaporeBusService
```

Expected assistant behavior:

1. identify target code version
2. choose standard release unless there is a reason for a lighter path
3. run backup, deploy, and verify
4. return a concise release report
