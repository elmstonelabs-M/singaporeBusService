# Singapore Bus Service Backend

FastAPI backend for a Singapore real-time bus arrival app. It follows the supplied design doc and includes:

- `GET /health`
- `GET /v1/bus-stops/{bus_stop_code}/arrivals`
- `GET /v1/bus-stops/nearby`
- `GET /v1/bus-stops/search`
- favorite group and favorite create/delete endpoints
- `GET /v1/home`
- `POST /v1/feedback`
- LTA DataMall client with timeout, retry, cache, and stale fallback
- PostgreSQL + Redis deployment with lightweight nearby lookup

Reusable deployment references:

- [DEPLOYMENT.md](D:\developwork\singaporeBusService\DEPLOYMENT.md)
- [RELEASE_RUNBOOK.md](D:\developwork\singaporeBusService\RELEASE_RUNBOOK.md)
- [GITHUB_ACTIONS_SETUP.md](D:\developwork\singaporeBusService\GITHUB_ACTIONS_SETUP.md)
- [BACKUP_AND_RECOVERY.md](D:\developwork\singaporeBusService\BACKUP_AND_RECOVERY.md)
- [SERVER_BASELINE.md](D:\developwork\singaporeBusService\SERVER_BASELINE.md)
- [.github/workflows/README.md](D:\developwork\singaporeBusService\.github\workflows\README.md)
- [.env.production.shared.example](D:\developwork\singaporeBusService\.env.production.shared.example)
- [nginx/reverse-proxy-template.conf](D:\developwork\singaporeBusService\nginx\reverse-proxy-template.conf)

## Running services

- `api`: FastAPI on `http://127.0.0.1:8000`
- `postgres`: PostgreSQL on `localhost:5432`
- `redis`: Redis on `localhost:16379`

## First-time setup

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
copy .env.example .env
docker compose up -d postgres redis
alembic upgrade head
```

Fill `LTA_ACCOUNT_KEY` in `.env` before syncing static LTA data.

## Sync static LTA data

```bash
python -m app.tasks.sync_lta_data
```

## Start the API

Use Docker:

```bash
docker compose up -d --build api
```

Or run directly on Windows:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Verify locally

```bash
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Production release

Standard server-side release:

```bash
./scripts/release_prod.sh
```

This runs backup, deployment, and health verification in one flow. For the full operator checklist, see [RELEASE_RUNBOOK.md](D:\developwork\singaporeBusService\RELEASE_RUNBOOK.md).

Production HTTP request/response logs are written to `./logs/app.log` on the server,
which maps to `/app/logs/app.log` inside the container.

Example endpoints:

```bash
http://127.0.0.1:8000/v1/bus-stops/search?q=marina&limit=5
http://127.0.0.1:8000/v1/bus-stops/nearby?lat=1.2839&lng=103.8607&radius=800&limit=5
http://127.0.0.1:8000/v1/bus-stops/83139/arrivals?user_device_id=device-demo
http://127.0.0.1:8000/v1/feedback
```

## Arrivals response

`GET /v1/bus-stops/{bus_stop_code}/arrivals` now returns both station metadata and
real-time service arrivals. For user-facing screens, prefer `display_name`. When
the user has not set an alias, `display_name` is the same as `description`.

Example:

```json
{
  "data": {
    "bus_stop_code": "83139",
    "description": "Opp Example Stop",
    "display_name": "Office Stop",
    "road_name": "Marine Parade Rd",
    "latitude": 1.3001,
    "longitude": 103.9001,
    "updated_at": "2026-05-20T14:30:00+08:00",
    "services": [
      {
        "service_no": "36",
        "operator": "SBST",
        "is_favorite": true,
        "arrivals": [
          {
            "sequence": 1,
            "display": "3m",
            "minutes": 3,
            "status": "ARRIVING",
            "load": "SEA",
            "load_label": "Seats Available",
            "load_color": "green",
            "wheelchair": true,
            "bus_type": "DD",
            "bus_type_label": "Double Deck",
            "monitored": true,
            "estimated_arrival": "2026-05-20T14:33:00+08:00"
          }
        ]
      }
    ]
  },
  "meta": {
    "updated_at": "2026-05-20T14:30:00+08:00",
    "stale": false
  }
}
```

Notes:

- `description`: official LTA station name
- `display_name`: current user's alias if present, otherwise the official name
- `is_favorite`: calculated per `user_device_id`, not shared across users
- real-time arrival cache stores only public arrival data; user-specific fields are
  applied after cache lookup
- if LTA is temporarily unavailable and `last_good` cache exists, the response will
  still be returned with `meta.stale = true`

## Bus stop aliases

Users can assign their own alias to a bus stop. The backend keeps the official
station name in `description` and returns the user-facing name in `display_name`.

Create or update an alias:

```bash
PUT /v1/bus-stop-aliases
{
  "user_device_id": "device-demo",
  "bus_stop_code": "83139",
  "alias": "Office Stop"
}
```

List aliases for a user:

```bash
GET /v1/bus-stop-aliases?user_device_id=device-demo
```

Delete an alias:

```bash
DELETE /v1/bus-stop-aliases/83139?user_device_id=device-demo
```

Alias-aware endpoints:

- `/v1/bus-stops/search`
- `/v1/bus-stops/nearby`
- `/v1/bus-stops/{bus_stop_code}/arrivals`
- `/v1/home`

## Feedback

Frontend can submit user feedback with:

```bash
POST /v1/feedback
{
  "user_device_id": "device-demo",
  "contact_email": "user@example.com",
  "category": "bug",
  "subject": "Arrival list issue",
  "message": "Favorite card did not refresh.",
  "app_version": "1.0.0",
  "device_info": "Pixel 8 / Android 15"
}
```

Behavior:

- feedback is always stored in PostgreSQL
- backend then attempts to forward the message to `FEEDBACK_TO_EMAIL`
- response includes `email_status`
  - `sent`
  - `failed`

Required email environment variables for delivery:

- `FEEDBACK_TO_EMAIL`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

## Test

```bash
pytest
```

If `pytest` is not installed locally yet, first run `pip install -e .[dev]`.

## Notes

- Default development is now PostgreSQL + Redis.
- Static `bus_stops` data is preloaded into application memory on startup. `get_by_code`, `search`, and `nearby` now prefer the in-memory catalog and only fall back to PostgreSQL when needed.
- Nearby lookup no longer depends on PostGIS. It uses a latitude/longitude bounding box in SQL and Haversine distance filtering in the app layer.
- `/v1/home` now uses a short Redis cache (`DEFAULT_HOME_CACHE_TTL_SECONDS`, default `15`) and invalidates that cache automatically when favorites or bus stop aliases change.
- Existing local databases can be upgraded in place with `alembic upgrade head`; the PostGIS `location` column and related extensions are removed by migration `0004_remove_postgis_dependency`.
- The local Docker stack now uses `postgres:16` instead of a PostGIS image. Collation metadata has also been refreshed for the current local environment after the image switch.
- SQLite remains only as a fallback for tests and lightweight execution.
- `LTA_ACCOUNT_KEY` must come from environment variables only.
- `.env` is ignored by git and should hold real local credentials only.
- The Docker `api` service uses container-internal hostnames `postgres` and `redis`.
