# Market Specification

## Purpose

Agricultural commodity price data — fetching from AGMARKNET, caching, historical trends, and user-defined price alerts.

## Requirements

### Requirement: Current Price Lookup

The system SHALL serve commodity prices by market, state, and date from the local database (populated by the sync worker).

#### Scenario: Get prices by commodity
- GIVEN prices for "Wheat" exist in the database for today
- WHEN `GET /market/prices?commodity=Wheat&state=Punjab` is called
- THEN a list of market records is returned, each with `market`, `min_price`, `max_price`, `modal_price`, `price_date`
- AND results are sorted by `price_date` descending

#### Scenario: No data for commodity
- GIVEN no prices exist for the requested commodity and state
- WHEN the endpoint is called
- THEN `200 OK` is returned with an empty array
- AND `{"meta": {"last_sync": "<timestamp>"}}` is included to indicate when data was last refreshed

#### Scenario: Redis cache hit
- GIVEN a price query was made in the last 6 hours for the same commodity + state
- WHEN the same query is made again
- THEN the response is served from Redis without hitting PostgreSQL
- AND a `X-Cache: HIT` header is present in the response

#### Scenario: Cache miss on first query
- GIVEN no cached result exists
- WHEN a price query is made
- THEN PostgreSQL is queried and the result is stored in Redis at `market:<commodity>:<state>` with 6-hour TTL

---

### Requirement: Historical Price Trends

The system SHALL provide price history for a commodity over a date range for chart rendering.

#### Scenario: Trend query
- GIVEN "Rice" prices exist in the database from Jan to Dec 2024
- WHEN `GET /market/prices/history?commodity=Rice&state=AP&from=2024-01-01&to=2024-12-31` is called
- THEN daily modal prices are returned as an array of `{date, modal_price}` objects sorted by date ascending

#### Scenario: Date range too wide
- GIVEN a `from`–`to` range exceeding 2 years
- WHEN the history endpoint is called
- THEN `400 Bad Request` is returned with `{"error": "range_too_large", "max_days": 730}`

---

### Requirement: Supported Commodities List

The system SHALL expose the list of commodities and states available in the database.

#### Scenario: Commodity list
- WHEN `GET /market/commodities` is called
- THEN a distinct sorted list of commodity names is returned
- AND it reflects only commodities that have at least one price record in the last 30 days

#### Scenario: State list for commodity
- WHEN `GET /market/commodities/:name/states` is called
- THEN the states where that commodity has price records are returned

---

### Requirement: Price Alerts

Authenticated users SHALL be able to set alerts that fire when a commodity price crosses a threshold.

#### Scenario: Create alert
- GIVEN an authenticated user
- WHEN `POST /market/alerts` is called with `{commodity, threshold, direction}` where direction is `"above"` or `"below"`
- THEN the alert is stored in the database
- AND `201 Created` is returned

#### Scenario: Alert limit per user
- GIVEN a user already has 20 active alerts
- WHEN they try to create a 21st
- THEN `422 Unprocessable Entity` is returned with `{"error": "alert_limit_reached"}`

#### Scenario: Delete alert
- GIVEN an authenticated user and their alert ID
- WHEN `DELETE /market/alerts/:id` is called
- THEN the alert is deleted and `204 No Content` is returned

#### Scenario: Alert triggers
- GIVEN a user has an alert for "Tomato" above ₹5000
- WHEN the market sync worker finds modal price for "Tomato" = ₹5200
- THEN the notification worker is enqueued with this user's alert ID
- AND `triggered = true` is set on the alert record

---

### Requirement: AGMARKNET Sync

The system SHALL sync commodity prices from the AGMARKNET API (data.gov.in) at least every 6 hours via the background worker.

#### Scenario: Sync inserts new prices
- GIVEN new price data is returned by AGMARKNET for today
- WHEN the sync worker runs
- THEN new records are inserted using `INSERT ... ON CONFLICT DO UPDATE` (upsert)
- AND records that already exist with the same `(commodity, market, price_date)` are updated

#### Scenario: AGMARKNET API down
- GIVEN the AGMARKNET API returns a non-200 status
- WHEN the sync worker runs
- THEN the job is retried with exponential backoff (3 retries max)
- AND an error is logged with the HTTP status and response body
- AND the last successful sync timestamp is NOT updated

#### Scenario: Cache invalidation after sync
- GIVEN the sync worker successfully writes new prices
- WHEN the sync completes
- THEN all `market:*` Redis keys are deleted to force fresh reads
