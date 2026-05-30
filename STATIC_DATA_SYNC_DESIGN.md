# Static Data Sync Design

## Goal

Move low-change static transit data from server-side query paths to client-side local storage,
so the backend focuses on:

- real-time arrivals
- favorites
- bus stop aliases
- lightweight aggregation

Static datasets in scope:

- `bus_stops`
- `bus_routes`
- `bus_services`

## Why

These datasets change infrequently compared with arrival traffic.

Benefits:

- fewer API calls for search and route lookup
- lower PostgreSQL read pressure
- lower Redis pressure
- faster in-app search and route pages
- partial offline capability for static browsing

## Recommended architecture

### Backend responsibilities

Keep serving:

- `GET /v1/bus-stops/{bus_stop_code}/arrivals`
- `GET /v1/home`
- favorites endpoints
- alias endpoints
- static data version and package endpoints

Reduce or eventually de-emphasize:

- `GET /v1/bus-stops/search`
- `GET /v1/bus-stops/nearby`

These can remain as fallback or compatibility APIs during frontend migration.

### Frontend responsibilities

On first install or first launch:

- download static data package from backend
- store it in local SQLite
- build local query/index helpers

After that:

- stop search uses local SQLite data
- route detail and route-stop lookup use local SQLite data
- nearby stop lookup uses local SQLite data plus device location
- only real-time arrivals and user-specific data still call backend

## Implemented backend APIs

### 1. Static data version

`GET /v1/static-data/version`

Purpose:

- tell the app whether local static data is outdated

Recommended response:

```json
{
  "data": {
    "version": "2026-05-21T00:00:00+08:00",
    "package_url": "/v1/static-data/package",
    "checksum": "sha256:demo",
    "min_supported_app_version": "1.0.0"
  },
  "meta": {
    "request_id": null,
    "updated_at": "2026-05-21T00:00:00+08:00",
    "stale": false
  }
}
```

### 2. Full static data package

`GET /v1/static-data/package`

Purpose:

- return one complete package for client bootstrap

Recommended response shape:

```json
{
  "data": {
    "version": "2026-05-21T00:00:00+08:00",
    "bus_stops": [],
    "bus_routes": [],
    "bus_services": []
  },
  "meta": {
    "request_id": null,
    "updated_at": "2026-05-21T00:00:00+08:00",
    "stale": false
  }
}
```

### 3. Optional split endpoints

If package size becomes too large, split into:

- `GET /v1/static-data/bus-stops`
- `GET /v1/static-data/bus-routes`
- `GET /v1/static-data/bus-services`

### 4. Optional delta endpoint later

If static updates become more frequent:

- `GET /v1/static-data/delta?since_version=...`

Not required for MVP.

## Versioning strategy

Recommended first versioning rule:

- use backend sync timestamp as the static data version
- update version whenever any of these tables changes:
  - `bus_stops`
  - `bus_routes`
  - `bus_services`

Recommended source of truth:

- a new backend metadata table or one Redis key persisted after sync

MVP shortcut:

- derive version from latest `updated_at` across the three tables

## Recommended client storage

Use local SQLite on the device.

Recommended local tables:

- `bus_stops`
  - `bus_stop_code`
  - `road_name`
  - `description`
  - `latitude`
  - `longitude`
  - `search_text`
- `bus_routes`
  - `service_no`
  - `direction`
  - `stop_sequence`
  - `bus_stop_code`
  - `distance_km`
- `bus_services`
  - `service_no`
  - `direction`
  - `operator`
  - `category`
  - `origin_code`
  - `destination_code`
  - frequency fields

Recommended local indexes:

- `bus_stops.bus_stop_code`
- `bus_stops.search_text`
- `bus_routes.service_no`
- `bus_routes.bus_stop_code`
- `bus_routes.service_no + direction + stop_sequence`
- `bus_services.service_no`

## Recommended frontend migration plan

### Phase 1

Backend adds:

- `GET /v1/static-data/version`
- `GET /v1/static-data/package`

Frontend:

- downloads package on first launch
- stores it locally
- keeps using existing backend search/nearby temporarily

### Phase 2

Frontend switches these features to local data:

- stop search
- route detail
- route stop list
- nearby stop lookup

Backend remains compatible.

### Phase 3

Backend can treat these as fallback-only:

- `/v1/bus-stops/search`
- `/v1/bus-stops/nearby`

## Impact on existing endpoints

### Still required

- `/v1/bus-stops/{bus_stop_code}/arrivals`
- `/v1/home`
- `/v1/favorites`
- `/v1/favorite-groups`
- `/v1/bus-stop-aliases`

### Can be gradually de-emphasized

- `/v1/bus-stops/search`
- `/v1/bus-stops/nearby`

## Resource savings expectation

Most likely savings come from removing repeated static reads for:

- search page
- nearby page
- route/station metadata lookup

The server will still need to handle:

- real-time arrival requests
- user-specific favorites and aliases
- home aggregation

## Recommendation

Best next step:

1. add static data version endpoint
2. add full package endpoint
3. let frontend migrate search and route browsing to local SQLite
4. keep arrivals, favorites, aliases, and home on backend
