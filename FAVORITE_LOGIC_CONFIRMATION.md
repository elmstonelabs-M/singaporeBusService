# Favorite Logic Confirmation

## Core rule

One bus stop corresponds to one favorite card.

In backend terms:

- one `favorite group/card` = one `bus_stop_code`
- one `favorite item` = one favorited `service_no` under that bus stop card

So the favorite UI is station-card based, not service-number based across stations.

## Create favorite behavior

When the client taps the favorite button for one line at one station:

### Case 1. The current station already has a favorite card

If the current user already has a favorite card for this `bus_stop_code`:

- backend reuses that same card
- backend adds the selected `service_no` under that card

Example:

- station `83139` already has a favorite card
- user already favorited `36`
- user now favorites `97`
- result: `36` and `97` are both under the same station card for `83139`

### Case 2. The current station does not have a favorite card yet

If the current user does not yet have a favorite card for this `bus_stop_code`:

- backend creates a new favorite card automatically
- the default card name is the current station name
- backend adds the selected `service_no` under that new card

Example:

- station `83139` has no favorite card yet
- user favorites `36`
- backend creates a new card named like `Opp Example Stop`
- backend adds `36` into that card

### Case 3. The exact station + line is already favorited

If the current user already favorited the same:

- `bus_stop_code`
- `service_no`

Then:

- backend returns the existing favorite record
- backend does not create a duplicate row
- backend does not create a second card

## Delete favorite behavior

When the client removes one favorited line:

### Case 1. Other lines still remain under the same station card

Then:

- backend deletes only that one `favorite item`
- backend keeps the station card

Example:

- station `83139` card contains `36` and `97`
- user removes `36`
- result: card still exists and still contains `97`

### Case 2. The deleted line was the last line under that station card

Then:

- backend deletes that `favorite item`
- backend also deletes the now-empty station card automatically

Example:

- station `83139` card contains only `36`
- user removes `36`
- result: the entire station card disappears

## Important non-rule

Backend does **not** reuse a favorite card across different stations, even if the service number is the same.

Example:

- user favorites `36` at station `83139`
- user favorites `36` again at station `65009`
- result: two different station cards
- because `83139` and `65009` are different bus stops

## API implication

For `POST /v1/favorites`:

- if `group_id` is explicitly provided, backend adds to that exact card
- if `group_id` is omitted, backend applies the automatic station-card rule above

Useful response fields:

- `group_id`
- `group_name`
- `favorite_id`
- `created_group`
- `already_exists`

## Final summary

The confirmed favorite model is:

- favorites are grouped by bus stop
- one station = one favorite card
- multiple lines at the same station share the same card
- different stations never share the same card
- removing the last line removes the empty card automatically
