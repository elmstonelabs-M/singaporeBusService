# GitHub Actions Deployment Notes

This directory contains the production release workflow for `singaporeBusService`.

Main workflow:

- [release-prod.yml](D:\developwork\singaporeBusService\.github\workflows\release-prod.yml)

Required GitHub Actions secrets:

- `PROD_SSH_HOST`
- `PROD_SSH_PORT`
- `PROD_SSH_USER`
- `PROD_SSH_PRIVATE_KEY`
- `PROD_DEPLOY_PATH`
- `PROD_HEALTH_URL`

Recommended values for the current production server:

- `PROD_SSH_HOST`: `35.197.135.48`
- `PROD_SSH_PORT`: `22`
- `PROD_SSH_USER`: `devlop`
- `PROD_DEPLOY_PATH`: `/home/devlop/singaporeBusService`
- `PROD_HEALTH_URL`: `http://127.0.0.1:8000/health`

`PROD_SSH_PRIVATE_KEY` should be the private key content for the deployment user.

Behavior:

1. Check out the repository on the GitHub runner
2. Open an SSH connection to the production server
3. `rsync` the repository into the deployment directory
4. Preserve server-only files such as `.env.production` and `backups/`
5. Run [scripts/release_prod.sh](D:\developwork\singaporeBusService\scripts\release_prod.sh) on the server

Triggers:

- push to `main`
- manual `workflow_dispatch`

Manual inputs:

- `skip_backup`
- `skip_sync_static_data`
