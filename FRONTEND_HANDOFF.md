# Singapore Bus App Frontend Handoff

## Base URLs

- Local Swagger: `http://127.0.0.1:8000/docs`
- Local OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Local API base: `http://127.0.0.1:8000`

All business APIs are under:

- `http://127.0.0.1:8000/v1`

## Current running local services

- API: `http://127.0.0.1:8000`
- PostgreSQL: `localhost:5432`
- Redis: `localhost:16379`

## Auth model

There is currently no login token system.

The app identifies a user by:

- `user_device_id`

Frontend should generate and persist a stable device identifier locally, then pass
it to user-specific endpoints.

## Response envelope

Successful responses use:

```json
{
  "data": {},
  "meta": {
    "request_id": null,
    "updated_at": null,
    "stale": false
  }
}
```

Error responses use:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "request_id": "req_xxx"
  }
}
```

## Important field rules

- `description`: official LTA bus stop name
- `display_name`: current user's alias if set, otherwise same as `description`
- `is_favorite`: user-specific flag for one `bus_stop_code + service_no`
- `meta.stale = true`: response came from fallback cache because live LTA request failed

## Core endpoints

### 1. Search bus stops

`GET /v1/bus-stops/search?q=marina&limit=20&user_device_id=device-demo`

Purpose:

- search by bus stop code
- search by stop name
- search by road name

Response item:

```json
{
  "bus_stop_code": "83139",
  "description": "Opp Example Stop",
  "display_name": "Office Stop",
  "road_name": "Marine Parade Rd",
  "latitude": 1.3001,
  "longitude": 103.9001,
  "distance_m": null,
  "distance_label": null,
  "has_arrival_data": false
}
```

### 2. Nearby bus stops

`GET /v1/bus-stops/nearby?lat=1.2839&lng=103.8607&radius=800&limit=20&user_device_id=device-demo`

Purpose:

- fetch nearby bus stops ordered by distance

Notes:

- `distance_m` is available
- `distance_label` is available for direct rendering like `120m` or `1.2km`
- `display_name` already respects alias

### 3. Real-time arrivals for one bus stop

`GET /v1/bus-stops/83139/arrivals?user_device_id=device-demo`

Optional:

- `service_no`

Purpose:

- fetch bus stop metadata
- fetch all service arrivals for that stop
- include user-specific alias and favorite flags

Response shape:

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
        "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
        "group_id": "7d5b7f8e-caa2-4d57-9f82-b0f6a65cb1cb",
        "group_name": "Home",
        "display_order": 0,
        "arrivals": [
          {
            "sequence": 1,
            "visit_number": 1,
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
            "estimated_arrival": "2026-05-20T14:33:00+08:00",
            "vehicle_latitude": 1.30123,
            "vehicle_longitude": 103.84002
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

Frontend display suggestions:

- use `display_name` as main station title
- use `description` only when needing official name or debug info
- use `display` directly for ETA chip text
- use `load_color` for crowdedness color
- use `wheelchair` for accessibility icon
- use `is_favorite` for favorite toggle state
- if `favorite_id` is present, frontend can remove or reorder without another lookup
- `visit_number` maps LTA arrival slots directly:
  - `1 = NextBus`
  - `2 = NextBus2`
  - `3 = NextBus3`
- `vehicle_latitude` and `vehicle_longitude` can be used by the route detail layer to place up to 3 live vehicles approximately on the stop sequence
- if `vehicle_latitude` or `vehicle_longitude` is `null`, frontend should skip map placement for that vehicle

### 4. Home payload

`GET /v1/home?user_device_id=device-demo&lat=1.2839&lng=103.8607`

Purpose:

- return one aggregated payload for the home screen

Includes:

- `location_label`
- `updated_at`
- `favorite_groups`
- each favorite item with latest arrivals
- `nearby_bus_stops`

Frontend should prioritize this endpoint for the main landing page.

### 5. Favorite groups

List groups:

- `GET /v1/favorite-groups?user_device_id=device-demo`

Create group:

- `POST /v1/favorite-groups`

```json
{
  "user_device_id": "device-demo",
  "name": "Home",
  "emoji": "H",
  "display_order": 0
}
```

Update group:

- `PATCH /v1/favorite-groups/{group_id}`

```json
{
  "user_device_id": "device-demo",
  "name": "Work",
  "emoji": "W",
  "display_order": 1
}
```

Delete group:

- `DELETE /v1/favorite-groups/{group_id}?user_device_id=device-demo`

### 6. Favorites

Favorite model:

- one bus stop = one favorite card
- one favorite card can contain multiple favorited `service_no` values for the same `bus_stop_code`
- different bus stops never share the same favorite card, even if the `service_no` is the same

Create favorite:

- `POST /v1/favorites`

```json
{
  "user_device_id": "device-demo",
  "bus_stop_code": "83139",
  "service_no": "36",
  "display_order": 0
}
```

Behavior:

- if `group_id` is provided, backend adds the favorite into that specific group
- if `group_id` is omitted, backend first checks whether this user already has a favorite card for the current `bus_stop_code`
- if the current `bus_stop_code` already has a favorite card, backend adds this `service_no` under that same card
- if the current `bus_stop_code` does not have a favorite card yet, backend automatically creates a new favorite group
- the default new group name is the current bus stop name
- if the exact same `bus_stop_code + service_no` already exists, backend returns the existing favorite instead of creating a duplicate

Create favorite response now also includes:

- `group_name`
- `created_group`
- `already_exists`

Reorder favorites:

- `PATCH /v1/favorites/reorder`

```json
{
  "user_device_id": "device-demo",
  "items": [
    {
      "favorite_id": "2f80f65a-cd0f-4af6-a4e4-2405511bd6df",
      "display_order": 0
    }
  ]
}
```

Delete favorite:

- `DELETE /v1/favorites/{favorite_id}?user_device_id=device-demo`

Delete behavior:

- if other services still remain under the same station card, backend deletes only that one favorite item
- if the deleted service was the last item under that station card, backend also deletes the now-empty favorite card automatically

Rename behavior:

- renaming a favorite card also updates the current user's bus stop alias for that station
- updating a bus stop alias also refreshes the corresponding favorite card name
- this keeps favorite card title, search display name, and stop detail title consistent

### 7. Bus stop aliases

List aliases:

- `GET /v1/bus-stop-aliases?user_device_id=device-demo`

Create or update alias:

- `PUT /v1/bus-stop-aliases`

```json
{
  "user_device_id": "device-demo",
  "bus_stop_code": "83139",
  "alias": "Office Stop"
}
```

Delete alias:

- `DELETE /v1/bus-stop-aliases/83139?user_device_id=device-demo`

Alias object shape:

```json
{
  "bus_stop_code": "83139",
  "alias": "Office Stop",
  "updated_at": "2026-05-20T15:30:00+08:00"
}

### 8. Send feedback

Submit feedback:

- `POST /v1/feedback`

```json
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

Notes:

- backend stores the feedback even if email forwarding fails
- response contains `email_status`
- current delivery target is configured by backend and defaults to `elmstonelabs@gmail.com`
```

## Recommended frontend flows

### Home page

1. Read persisted `user_device_id`
2. Read current location if user granted permission
3. Call `/v1/home`
4. Render:
   - `location_label`
   - favorite groups
   - favorite arrivals
   - nearby stops

### Search flow

1. User types keyword
2. Call `/v1/bus-stops/search`
3. Render `display_name` as primary title
4. Navigate to stop detail page with `bus_stop_code`

### Stop detail page

1. Call `/v1/bus-stops/{code}/arrivals`
2. Render station title from `display_name`
3. Render service list and arrivals
4. Favorite toggle should use `is_favorite`

### Alias editing

1. User opens stop rename UI
2. Submit `PUT /v1/bus-stop-aliases`
3. Refresh:
   - stop detail
   - search results if needed
   - home payload if needed

## Current business error codes

### Arrivals

- `INVALID_BUS_STOP_CODE`
- `LTA_REQUEST_FAILED`
- `LTA_ACCOUNT_KEY_MISSING`

### Favorites

- `FAVORITE_GROUP_NOT_FOUND`
- `FAVORITE_NOT_FOUND`
- `BUS_STOP_NOT_FOUND`
- `FAVORITE_ALREADY_EXISTS`

## Integration notes

- Real-time arrivals are fetched on demand, not by scheduled full-city polling
- Redis caches public arrival data only
- user-specific fields like `display_name` and `is_favorite` are injected after cache lookup
- this avoids alias/favorite leakage across users
- static `bus_stops` are now preloaded into backend process memory for lower DB read pressure
- frontend is expected to migrate low-change static data (`bus_stops`, `bus_routes`, `bus_services`) into local SQLite over time
- after that migration, `/v1/bus-stops/search` and `/v1/bus-stops/nearby` can be treated as compatibility fallback endpoints instead of primary data sources

## Static data migration direction

Recommended new frontend architecture:

- download static transit data package on first launch
- store `bus_stops`, `bus_routes`, and `bus_services` in local SQLite
- use local data for:
  - stop search
  - nearby stop lookup
  - route detail and route-stop list
- keep backend for:
  - arrivals
  - favorites
  - aliases
  - home aggregation

Related docs:

- [STATIC_DATA_SYNC_DESIGN.md](D:\developwork\singaporeBusService\STATIC_DATA_SYNC_DESIGN.md:1)
- [FRONTEND_STATIC_DATA_MIGRATION.md](D:\developwork\singaporeBusService\FRONTEND_STATIC_DATA_MIGRATION.md:1)

## Recommended URLs for the frontend engineer

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Handoff doc: [FRONTEND_HANDOFF.md](D:\developwork\singaporeBusService\FRONTEND_HANDOFF.md:1)
