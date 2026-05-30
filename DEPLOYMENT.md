# Production Deployment

This project can be deployed on a Linux server with Docker Engine and Docker Compose.

## 1. Server prerequisites

- Ubuntu 22.04/24.04 or another modern Linux distribution
- Docker Engine
- Docker Compose plugin (`docker compose`)
- Open ports:
  - `22` for SSH
  - `80/443` for Nginx

## 2. Prepare environment variables

```bash
cp .env.production.example .env.production
```

Update these values before first start:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `REDIS_PASSWORD`
- `REDIS_URL`
- `LTA_ACCOUNT_KEY`
- `CORS_ORIGINS`
- `LOG_FILE_PATH` if you want to override the default production log file path

Note:

- In Docker Compose, `DATABASE_URL` should keep the hostname `postgres`
- `REDIS_URL` should keep the hostname `redis`
- `REDIS_URL` should include the Redis password, for example `redis://:your_password@redis:6379/0`

## 3. First deployment

```bash
chmod +x scripts/deploy_prod.sh
./scripts/deploy_prod.sh
```

This will:

- start PostgreSQL and Redis
- run Alembic migrations
- sync the latest LTA static data
- start the API container

Layered deploy scripts:

- `scripts/deploy/up_infra.sh`: start PostgreSQL and Redis
- `scripts/deploy/migrate.sh`: run Alembic migrations
- `scripts/deploy/sync_static_data.sh`: run project-specific LTA bootstrap
- `scripts/deploy/up_api.sh`: build and start the API
- `scripts/deploy/deploy_full.sh`: run the full sequence
- `scripts/deploy/verify_health.sh`: verify container state and `/health`
- `scripts/release_prod.sh`: backup + deploy + verify in one entrypoint

## 4. Verify

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl http://127.0.0.1:8000/health
```

Request and response logs are written to `./logs/app.log` on the VPS, which maps to
`/app/logs/app.log` inside the API container.

## 5. Routine updates

After pulling new code on the server:

```bash
./scripts/release_prod.sh
```

Useful release options:

```bash
./scripts/release_prod.sh --skip-backup
./scripts/release_prod.sh --skip-sync-static-data
./scripts/release_prod.sh --health-url https://trackbusapi.sgbtt.top/health
```

For GitHub Actions based release automation, see:

- [RELEASE_RUNBOOK.md](D:\developwork\singaporeBusService\RELEASE_RUNBOOK.md)
- [.github/workflows/README.md](D:\developwork\singaporeBusService\.github\workflows\README.md)

If the update only changes application code and does not require infra or bootstrap changes, you can use:

```bash
./scripts/deploy/up_api.sh
```

## 6. Recommended reverse proxy

For public production use, place Nginx or Caddy in front of port `8000`, terminate TLS there, and expose only `80/443` publicly. In `docker-compose.prod.yml`, the API is bound to `127.0.0.1:8000` so it is reachable only from the server itself.

## 7. Network and credential safety

- PostgreSQL is not published to the host, so it is reachable only inside the Docker network
- Redis is not published to the host, so it is reachable only inside the Docker network
- PostgreSQL should always use a non-default `POSTGRES_PASSWORD`
- Redis should always use a non-default `REDIS_PASSWORD`

## 8. Important operational note

The repository includes a scheduler definition in `app/tasks/scheduler.py`, but it is not wired into the API process. For now, use cron if you want recurring nightly syncs, for example:

```bash
10 3 * * * cd /home/<deploy_user>/<project_name> && docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api python -m app.tasks.sync_lta_data >> /var/log/<project_name>-sync.log 2>&1
```

## 9. Backup and recovery

Use the repository backup scripts for PostgreSQL and key config files:

- `scripts/backup/backup_postgres.sh`
- `scripts/backup/backup_configs.sh`
- `scripts/backup/backup_all.sh`
- `scripts/backup/restore_postgres.sh`

Detailed instructions:

- [BACKUP_AND_RECOVERY.md](D:\developwork\singaporeBusService\BACKUP_AND_RECOVERY.md)
- [RELEASE_RUNBOOK.md](D:\developwork\singaporeBusService\RELEASE_RUNBOOK.md)
