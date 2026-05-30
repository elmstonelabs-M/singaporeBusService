# Reusable Linux Production Baseline

This document captures the production-server baseline we validated on `2026-05-21` for this project and can be reused by other API/backend projects with small substitutions.

## Baseline summary

- OS: Ubuntu `24.04 LTS`
- App runtime: Docker Engine + Docker Compose plugin
- Public entrypoint: `Nginx`
- TLS: `Certbot` with Let's Encrypt
- App exposure model:
  - public: `80/443`
  - private on host: `127.0.0.1:<app_port>`
  - internal only: PostgreSQL and Redis on the Docker network
- Process model:
  - `api` container
  - `postgres` container
  - `redis` container
  - optional cron-based maintenance jobs

## What this baseline is optimizing for

- Fast setup on a single VM
- Reasonable security defaults
- Easy rollback and troubleshooting
- Minimal moving parts
- Reusable across Python, Node, and other containerized backends

## Required server packages

Install these packages on a fresh Ubuntu server:

- `docker.io`
- `docker-compose-v2`
- `nginx`
- `certbot`
- `python3-certbot-nginx`

Example:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx
```

## Directory convention

Recommended layout per project:

```text
/home/<deploy_user>/<project_name>/
```

Keep at least:

- source code
- `docker-compose.prod.yml`
- `.env.production`
- deployment scripts
- reverse-proxy template references

## Network model

Use this exposure pattern:

- Nginx listens on `0.0.0.0:80` and `0.0.0.0:443`
- app container publishes only to `127.0.0.1:<app_port>`
- PostgreSQL publishes no host port
- Redis publishes no host port

Why:

- only the reverse proxy is reachable from the internet
- the app is reachable from the host for local proxying and health checks
- data stores remain isolated inside Docker networking

## Credential model

Always set non-default secrets for:

- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- app/API provider keys
- SMTP credentials if email is used

Recommended connection-string patterns:

```text
DATABASE_URL=postgresql+asyncpg://<db_user>:<db_password>@postgres:5432/<db_name>
REDIS_URL=redis://:<redis_password>@redis:6379/0
```

## Reverse proxy model

Use Nginx in front of the app:

- terminate TLS at Nginx
- proxy traffic to `127.0.0.1:<app_port>`
- preserve `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`
- redirect HTTP to HTTPS after the certificate is installed

Reusable template:

- [nginx/reverse-proxy-template.conf](D:\developwork\singaporeBusService\nginx\reverse-proxy-template.conf)

## Certificate model

Recommended flow:

1. Point the domain to the VM.
2. Make sure inbound `80/443` is open at the cloud firewall layer.
3. Verify public HTTP works first.
4. Request the certificate with Certbot.
5. Enable redirect from HTTP to HTTPS.

Example:

```bash
sudo certbot --nginx -d api.example.com --non-interactive --agree-tos --register-unsafely-without-email --redirect
```

## Cloud firewall checklist

Opening ports in Nginx is not enough. Also confirm the cloud provider allows:

- `tcp:22`
- `tcp:80`
- `tcp:443`

Keep these closed publicly unless there is a specific reason:

- `5432`
- `6379`
- raw app port such as `8000`

## Health-check model

Recommended checks:

- app: HTTP request to `/health`
- PostgreSQL: `pg_isready`
- Redis: `redis-cli -a "$REDIS_PASSWORD" ping`

These should be embedded into Docker health checks where possible.

## Deployment flow

Recommended first deploy:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build postgres redis
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api alembic upgrade head
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build api
```

If the project has a static-data bootstrap step, run it between migration and final API start.

## Routine update flow

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api alembic upgrade head
```

Prefer layered scripts in real projects:

- `up_infra`
- `migrate`
- project-specific bootstrap
- `up_api`
- optional full wrapper

## Scheduled jobs

If the app needs periodic jobs but does not run an internal scheduler, prefer `cron` on the host for simple single-VM deployments.

Example pattern:

```bash
10 3 * * * root cd /home/<deploy_user>/<project_name> && /usr/bin/docker compose --env-file .env.production -f docker-compose.prod.yml run --rm api <job_command> >> /var/log/<project_name>.log 2>&1
```

## Backup and restore baseline

At minimum, each project should provide:

- a PostgreSQL backup script
- a config backup script
- a restore procedure
- a cron example

Back up at least:

- database dump
- `.env.production`
- compose file
- Nginx site config

## File-permission recommendations

- `.env.production`: readable only by the deploy user and root
- private SSH keys: owner-read only
- scripts: executable only when needed

Useful hardening commands:

```bash
chmod 600 .env.production
chmod 700 ~/.ssh
chmod 600 ~/.ssh/<private_key>
```

## Reusable checklist for new projects

1. Create `.env.production` from template.
2. Set strong `POSTGRES_PASSWORD` and `REDIS_PASSWORD`.
3. Bind the app only to `127.0.0.1`.
4. Do not publish database or Redis ports.
5. Confirm cloud firewall opens only `22/80/443`.
6. Verify public HTTP before requesting a certificate.
7. Install TLS and enable redirect.
8. Add one health endpoint and wire it into checks.
9. Add cron jobs only if the app truly needs them.
10. Document the deploy and rollback commands in the repo.

## Project-specific files in this repository

This repo already contains concrete examples of the baseline:

- [docker-compose.prod.yml](D:\developwork\singaporeBusService\docker-compose.prod.yml)
- [.env.production.example](D:\developwork\singaporeBusService\.env.production.example)
- [scripts/deploy_prod.sh](D:\developwork\singaporeBusService\scripts\deploy_prod.sh)
- [nginx/singapore-bus-service.conf](D:\developwork\singaporeBusService\nginx\singapore-bus-service.conf)
- [DEPLOYMENT.md](D:\developwork\singaporeBusService\DEPLOYMENT.md)
