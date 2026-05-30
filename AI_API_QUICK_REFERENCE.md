# Singapore Bus API Quick Reference

## Best URLs for AI

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- Frontend handoff: [FRONTEND_HANDOFF.md](D:\developwork\singaporeBusService\FRONTEND_HANDOFF.md:1)
- Static sync design: [STATIC_DATA_SYNC_DESIGN.md](D:\developwork\singaporeBusService\STATIC_DATA_SYNC_DESIGN.md:1)
- Frontend migration doc: [FRONTEND_STATIC_DATA_MIGRATION.md](D:\developwork\singaporeBusService\FRONTEND_STATIC_DATA_MIGRATION.md:1)

## Required user field

User-scoped APIs require:

- `user_device_id`

This is the stable client-side user identifier used for:

- favorites
- favorite groups
- bus stop aliases
- user-specific `display_name`
- user-specific `is_favorite`

## Important response fields

- `description`: official LTA bus stop name
- `display_name`: current user's alias if present, otherwise same as `description`
- `is_favorite`: whether the current user has favorited this `bus_stop_code + service_no`
- `favorite_id`: favorite record id, present when already favorited
- `group_id`: favorite group id, present when already favorited
- `group_name`: favorite group name, present when already favorited
- `display_order`: sort order for favorite item
- `created_group`: whether backend auto-created a new favorite group for this create action
- `already_exists`: whether this exact stop + service favorite already existed and was returned as-is
- `meta.stale = true`: live LTA call failed and fallback cache was used
- `distance_label`: ready-to-render distance, for example `120m` or `1.2km`

## Enum values

### Arrival status

- `ARRIVING`
- `ESTIMATED`
- `NO_ESTIMATE`
- `NOT_IN_OPERATION`

### Bus load

- `SEA`
  - Seats Available
- `SDA`
  - Standing Available
- `LSD`
  - Limited Standing

### Load color

- `green`
- `yellow`
- `red`
- `gray`

### Bus type

- `SD`
  - Single Deck
- `DD`
  - Double Deck
- `BD`
  - Bendy

## Business error codes

### Arrivals

- `INVALID_BUS_STOP_CODE`
  - bus stop code is not a 5-digit number
- `LTA_REQUEST_FAILED`
  - live LTA request failed and no fallback cache was available
- `LTA_ACCOUNT_KEY_MISSING`
  - backend LTA key is missing

### Favorites

- `FAVORITE_GROUP_NOT_FOUND`
  - favorite group does not exist or does not belong to this user
- `FAVORITE_NOT_FOUND`
  - favorite item does not exist or does not belong to this user
- `BUS_STOP_NOT_FOUND`
  - bus stop code does not exist in backend data
- `FAVORITE_ALREADY_EXISTS`
  - same `group_id + bus_stop_code + service_no` already exists

## Most important endpoints

### Search bus stops

- `GET /v1/bus-stops/search?q=...&limit=...&user_device_id=...`

### Nearby bus stops

- `GET /v1/bus-stops/nearby?lat=...&lng=...&radius=...&limit=...&user_device_id=...`

### Real-time arrivals

- `GET /v1/bus-stops/{bus_stop_code}/arrivals?user_device_id=...`

Optional query:

- `service_no`

### Home payload

- `GET /v1/home?user_device_id=...&lat=...&lng=...`

### Favorite groups

- `GET /v1/favorite-groups?user_device_id=...`
- `POST /v1/favorite-groups`
- `PATCH /v1/favorite-groups/{group_id}`
- `DELETE /v1/favorite-groups/{group_id}?user_device_id=...`

### Favorites

- `POST /v1/favorites`
- `PATCH /v1/favorites/reorder`
- `DELETE /v1/favorites/{favorite_id}?user_device_id=...`

`POST /v1/favorites` smart behavior:

- with `group_id`: add to that exact group
- without `group_id`: reuse the user's existing favorite card for the same `bus_stop_code`
- if no card exists for that `bus_stop_code`: auto-create a new group named after the current bus stop

### Bus stop aliases

- `GET /v1/bus-stop-aliases?user_device_id=...`
- `PUT /v1/bus-stop-aliases`
- `DELETE /v1/bus-stop-aliases/{bus_stop_code}?user_device_id=...`

## AI prompt tip

If you want another AI to generate frontend code safely, give it these two files together:

- [AI_API_QUICK_REFERENCE.md](D:\developwork\singaporeBusService\AI_API_QUICK_REFERENCE.md:1)
- [FRONTEND_HANDOFF.md](D:\developwork\singaporeBusService\FRONTEND_HANDOFF.md:1)

If you want another AI to generate API types or a client SDK, also give it:

- [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
