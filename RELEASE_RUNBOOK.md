# Release Runbook

This document is the standard production release flow for `singaporeBusService`.

Use it when you want a single, repeatable answer to:

- what to run before release
- how to deploy the newest code on the server
- how to verify the result
- what to do when a release needs a lighter path

## Standard release path

After the latest code is already on the server:

```bash
chmod +x scripts/release_prod.sh scripts/deploy/*.sh scripts/backup/*.sh
./scripts/release_prod.sh
```

Default release flow:

1. Create backups
2. Leave PostgreSQL and Redis unchanged
3. Apply Alembic migrations
4. Leave project-specific LTA static data unchanged
5. Build and start the API
6. Verify container status and `GET /health`
7. Review `./logs/app.log` on the server if you want the request/response trace

The release entrypoint is:

- [scripts/release_prod.sh](D:\developwork\singaporeBusService\scripts\release_prod.sh)

Supporting scripts:

- [scripts/deploy/up_infra.sh](D:\developwork\singaporeBusService\scripts\deploy\up_infra.sh)
- [scripts/deploy/migrate.sh](D:\developwork\singaporeBusService\scripts\deploy\migrate.sh)
- [scripts/deploy/sync_static_data.sh](D:\developwork\singaporeBusService\scripts\deploy\sync_static_data.sh)
- [scripts/deploy/up_api.sh](D:\developwork\singaporeBusService\scripts\deploy\up_api.sh)
- [scripts/deploy/verify_health.sh](D:\developwork\singaporeBusService\scripts\deploy\verify_health.sh)
- [scripts/backup/backup_all.sh](D:\developwork\singaporeBusService\scripts\backup\backup_all.sh)

## Release options

Skip backups:

```bash
./scripts/release_prod.sh --skip-backup
```

Start PostgreSQL and Redis during this release only when needed:

```bash
./scripts/release_prod.sh --with-infra
```

Run the project-specific static data sync during this release only when needed:

```bash
./scripts/release_prod.sh --with-sync-static-data
```

Override the health check URL:

```bash
./scripts/release_prod.sh --health-url https://trackbusapi.sgbtt.top/health
```

## Recommended operator flow

Use this sequence when running a real production release:

1. Review incoming changes and confirm the target branch or commit.
2. Update the server checkout to the intended code version.
3. Run `./scripts/release_prod.sh`.
4. Confirm `docker compose ... ps` shows healthy containers.
5. Confirm `/health` returns a successful response.
6. If the change affects public traffic, confirm the domain endpoint too.

## When to use a lighter path

Use the full release path by default. Use lighter paths only when you are sure they fit the change.

API-only update:

```bash
./scripts/deploy/up_api.sh
```

Migration-only update:

```bash
./scripts/deploy/migrate.sh
```

Static data bootstrap only:

```bash
./scripts/deploy/sync_static_data.sh
```

Weekly static data sync rule:

```bash
0 3 * * 3 cd /home/<deploy_user>/<project_name> && docker compose --env-file .env.production -f docker-compose.prod.yml run --rm --build api python -m app.tasks.sync_lta_data >> /home/<deploy_user>/<project_name>/logs/static-sync.log 2>&1
```

If the upstream static dataset does not change, `sync_lta_data` keeps the existing version
unchanged. A new version is written only when the package checksum changes.

Verification only:

```bash
./scripts/deploy/verify_health.sh
```

HTTP request/response logs are written to `./logs/app.log` on the VPS, which maps
to `/app/logs/app.log` inside the API container.

## Release checklist for future deployment chats

When a deployment-only conversation says `release singaporeBusService` or `publish singaporeBusService`, the expected workflow is:

1. Check git status and identify the target revision.
2. Pull or upload the latest code to the server.
3. Run the standard release script unless there is a clear reason to use a lighter path.
4. Report back:
   - deployed revision
   - whether backup ran
   - whether migrations ran
   - whether static data sync ran
   - whether PostgreSQL/Redis were left unchanged or restarted
   - health check result
   - any manual follow-up needed

## Related docs

- [DEPLOYMENT.md](D:\developwork\singaporeBusService\DEPLOYMENT.md)
- [BACKUP_AND_RECOVERY.md](D:\developwork\singaporeBusService\BACKUP_AND_RECOVERY.md)
- [SERVER_BASELINE.md](D:\developwork\singaporeBusService\SERVER_BASELINE.md)
- [GITHUB_ACTIONS_SETUP.md](D:\developwork\singaporeBusService\GITHUB_ACTIONS_SETUP.md)
- [.github/workflows/README.md](D:\developwork\singaporeBusService\.github\workflows\README.md)

## GitHub Actions automation

Automatic production deployment is defined in:

- [.github/workflows/release-prod.yml](D:\developwork\singaporeBusService\.github\workflows\release-prod.yml)

Default behavior:

1. Trigger on push to `main`
2. Or run manually from GitHub Actions
3. Sync code to the production server with `rsync`
4. Keep `.env.production` and `backups/` on the server
5. Run `./scripts/release_prod.sh` remotely

Required repository secrets:

- `PROD_SSH_HOST`
- `PROD_SSH_PORT`
- `PROD_SSH_USER`
- `PROD_SSH_PRIVATE_KEY`
- `PROD_DEPLOY_PATH`
- `PROD_HEALTH_URL`
