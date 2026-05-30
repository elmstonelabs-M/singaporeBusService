# Backup And Recovery

This document describes the repository-backed backup and recovery workflow for production.

## What to back up

Minimum backup set:

- PostgreSQL data
- `.env.production`
- `docker-compose.prod.yml`
- Nginx site config
- `alembic.ini`

Optional backup set:

- uploaded files if the app later stores local media
- Docker named volumes beyond PostgreSQL and Redis if they become business-critical

## Script layout

- [scripts/backup/backup_postgres.sh](D:\developwork\singaporeBusService\scripts\backup\backup_postgres.sh)
- [scripts/backup/backup_configs.sh](D:\developwork\singaporeBusService\scripts\backup\backup_configs.sh)
- [scripts/backup/backup_all.sh](D:\developwork\singaporeBusService\scripts\backup\backup_all.sh)
- [scripts/backup/restore_postgres.sh](D:\developwork\singaporeBusService\scripts\backup\restore_postgres.sh)

## Create backups

Run from the repository root on the server:

```bash
chmod +x scripts/backup/*.sh
./scripts/backup/backup_all.sh
```

This writes outputs under:

```text
./backups/
```

Examples:

- `backups/postgres-20260522-031000.sql`
- `backups/config-20260522-031000/`

## Recommended cron

Example daily backup job:

```bash
0 4 * * * root cd /home/<deploy_user>/<project_name> && /bin/bash ./scripts/backup/backup_all.sh >> /var/log/<project_name>-backup.log 2>&1
```

## Restore PostgreSQL

Restore from a SQL dump:

```bash
./scripts/backup/restore_postgres.sh ./backups/postgres-20260522-031000.sql
```

## Restore configuration files

Copy the desired files back into place from the selected `config-*` directory:

- `.env.production`
- `docker-compose.prod.yml`
- `nginx-site.conf`
- `alembic.ini`

After restoring config, re-run the app:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d
```

## Notes

- Treat backup files as sensitive because they contain secrets and application data.
- Move long-term backups to secure remote storage outside the server.
- Test restore at least once before relying on the procedure in production.
