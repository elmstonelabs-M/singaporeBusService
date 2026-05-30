# Frontend Static Data Migration

## Purpose

This document describes the new frontend direction:

- static transit data should be downloaded once and stored locally
- frontend should query local data for stop search, nearby stop lookup, and route browsing
- backend should be reserved for real-time and user-specific data

## Data to store locally

Frontend should download and persist these datasets:

- `bus_stops`
- `bus_routes`
- `bus_services`

These are low-change static datasets from LTA sync jobs.

## Keep using backend for

- real-time arrivals
- favorites
- favorite groups
- bus stop aliases
- home payload

Current backend APIs that remain important:

- `GET /v1/bus-stops/{bus_stop_code}/arrivals`
- `GET /v1/home`
- `POST /v1/favorites`
- `PATCH /v1/favorites/reorder`
- `DELETE /v1/favorites/{favorite_id}`
- `GET/POST/PATCH/DELETE /v1/favorite-groups`
- `GET/PUT/DELETE /v1/bus-stop-aliases`

Static bootstrap APIs now available:

- `GET /v1/static-data/version`
- `GET /v1/static-data/package`

## New sync flow

### First launch

1. Read current local static data version
2. Call `GET /v1/static-data/version`
3. If no local package exists, or versions differ:
   - download full package from `GET /v1/static-data/package`
   - replace local SQLite data
4. Mark local version as current

### Later launches

1. Call `GET /v1/static-data/version`
2. If version unchanged:
   - do nothing
3. If version changed:
   - download package again
   - replace local static data

Recommended check timing:

- app launch
- app resume after long inactivity
- manual refresh in settings is optional

## Recommended local database schema

### bus_stops

- `bus_stop_code` TEXT PRIMARY KEY
- `road_name` TEXT
- `description` TEXT
- `latitude` REAL
- `longitude` REAL
- `search_text` TEXT

### bus_routes

- `service_no` TEXT
- `direction` INTEGER
- `stop_sequence` INTEGER
- `bus_stop_code` TEXT
- `distance_km` REAL
- `wd_first_bus` TEXT
- `wd_last_bus` TEXT
- `sat_first_bus` TEXT
- `sat_last_bus` TEXT
- `sun_first_bus` TEXT
- `sun_last_bus` TEXT

### bus_services

- `service_no` TEXT
- `direction` INTEGER
- `operator` TEXT
- `category` TEXT
- `origin_code` TEXT
- `destination_code` TEXT
- `am_peak_freq` TEXT
- `am_offpeak_freq` TEXT
- `pm_peak_freq` TEXT
- `pm_offpeak_freq` TEXT
- `loop_desc` TEXT

## Recommended local indexes

- `bus_stops(bus_stop_code)`
- `bus_stops(search_text)`
- `bus_routes(service_no, direction, stop_sequence)`
- `bus_routes(bus_stop_code)`
- `bus_services(service_no, direction)`

## Frontend feature mapping

### Stop search

Old:

- `GET /v1/bus-stops/search`

New:

- query local `bus_stops`

Render rules remain:

- use alias-aware display name when available
- fallback to `description`

Frontend merge rule:

- local static stop data provides `description`, `road_name`, `latitude`, `longitude`
- backend alias data provides user-specific override for `display_name`

### Nearby stops

Old:

- `GET /v1/bus-stops/nearby`

New:

- query local `bus_stops`
- compute bounding box + Haversine on device

Frontend should sort by:

- nearest distance first

### Route detail

New preferred source:

- local `bus_routes`
- local `bus_services`

Suggested UX:

- route base info from `bus_services`
- ordered stop list from `bus_routes`

### Stop detail page

Still call:

- `GET /v1/bus-stops/{bus_stop_code}/arrivals`

But static header fields may also be available locally.

### Home page

Still call:

- `GET /v1/home`

Reason:

- includes real-time arrivals
- includes user-specific favorites
- includes alias-aware names

## Alias merge rule

Frontend local static data should not permanently overwrite official stop names.

Recommended display rule:

- official stop name comes from local `bus_stops.description`
- alias comes from backend alias data
- render:
  - `display_name = alias ?? description`

This matches the current backend behavior.

## Favorites impact

Favorites still belong to backend because they are user-specific.

Frontend should continue using:

- `favorite_id`
- `group_id`
- `group_name`
- `is_favorite`

Static local data only helps enrich station metadata around those favorites.

## Recommended rollout

### Stage 1

Add local static package download.

Frontend still keeps old backend search/nearby as fallback.

### Stage 2

Switch to local:

- search
- nearby
- route detail

### Stage 3

Treat backend `/search` and `/nearby` as compatibility fallback only.

## Backend URLs to keep handy

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Main handoff: [FRONTEND_HANDOFF.md](D:\developwork\singaporeBusService\FRONTEND_HANDOFF.md:1)
- Static sync design: [STATIC_DATA_SYNC_DESIGN.md](D:\developwork\singaporeBusService\STATIC_DATA_SYNC_DESIGN.md:1)
