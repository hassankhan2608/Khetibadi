# Farm Specification

## Purpose

Farm management — creating and editing farm boundaries using GIS polygons, storing soil data, and fetching weather conditions for each farm location.

## Requirements

### Requirement: Farm CRUD

The system SHALL allow authenticated users to create, read, update, and delete their farms.

#### Scenario: Create farm with boundary
- GIVEN an authenticated user
- WHEN `POST /farms` is called with a name and a valid GeoJSON polygon
- THEN the farm is created with the boundary stored as PostGIS geometry
- AND `area_ha` is calculated server-side from the polygon area
- AND `201 Created` is returned with the full farm object

#### Scenario: List own farms
- GIVEN an authenticated user with 3 farms
- WHEN `GET /farms` is called
- THEN only that user's farms are returned (other users' farms are never included)
- AND each farm includes `id`, `name`, `area_ha`, `soil_type`, `created_at`

#### Scenario: Get farm by ID
- GIVEN a farm belonging to the requesting user
- WHEN `GET /farms/:id` is called
- THEN the full farm object is returned including the boundary as GeoJSON

#### Scenario: Farm not owned by user
- GIVEN a farm ID belonging to a different user
- WHEN `GET /farms/:id` is called
- THEN `404 Not Found` is returned (not 403 — do not reveal existence)

#### Scenario: Update farm name or soil type
- GIVEN an authenticated user and their farm ID
- WHEN `PATCH /farms/:id` is called with updated fields
- THEN only the provided fields are updated
- AND `updated_at` is refreshed

#### Scenario: Delete farm
- GIVEN an authenticated user and their farm ID
- WHEN `DELETE /farms/:id` is called
- THEN the farm and all its soil samples are deleted (CASCADE)
- AND `204 No Content` is returned

---

### Requirement: Boundary Validation

The system SHALL reject farm boundaries that are geometrically invalid or unreasonably large.

#### Scenario: Self-intersecting polygon
- GIVEN a GeoJSON polygon whose rings self-intersect
- WHEN `POST /farms` is called
- THEN `400 Bad Request` is returned with `{"error": "invalid_geometry"}`

#### Scenario: Area too large
- GIVEN a polygon whose calculated area exceeds 10,000 hectares
- WHEN `POST /farms` is called
- THEN `400 Bad Request` is returned with `{"error": "area_exceeds_limit"}`

---

### Requirement: Soil Sample Management

The system SHALL allow adding soil sample readings to a farm.

#### Scenario: Add soil sample
- GIVEN an authenticated user and their farm ID
- WHEN `POST /farms/:id/soil-samples` is called with N, P, K, pH values
- THEN the sample is created linked to the farm
- AND `201 Created` is returned

#### Scenario: List soil samples
- GIVEN a farm with multiple soil samples
- WHEN `GET /farms/:id/soil-samples` is called
- THEN samples are returned sorted by `sampled_at` descending
- AND the response includes pagination with `limit` and `offset` query params (default limit: 20)

#### Scenario: Latest sample for ML input
- GIVEN a farm with at least one soil sample
- WHEN the crop recommendation service requests soil data
- THEN `GET /farms/:id/soil-samples?limit=1` returns the most recent sample

---

### Requirement: Weather Data

The system SHALL fetch and cache current weather conditions for each farm's coordinates.

#### Scenario: Weather fetch on demand
- GIVEN a farm with a valid boundary polygon
- WHEN `GET /farms/:id/weather` is called
- THEN the centroid of the farm boundary is computed
- AND OpenWeatherMap Current Weather API is queried using the centroid lat/lng
- AND the result is cached in Redis at key `weather:<farm_id>` with 3-hour TTL

#### Scenario: Cache hit
- GIVEN weather for a farm was fetched within the last 3 hours
- WHEN `GET /farms/:id/weather` is called again
- THEN the cached result is returned without calling OpenWeatherMap

#### Scenario: OpenWeatherMap unavailable
- GIVEN the OpenWeatherMap API returns a non-200 response
- WHEN weather is requested
- THEN `502 Bad Gateway` is returned with `{"error": "weather_service_unavailable"}`
- AND the error is logged with the upstream response code

#### Scenario: Weather response shape
- WHEN weather data is returned successfully
- THEN the response includes: `temperature_c`, `humidity_pct`, `rainfall_mm_last_1h`, `wind_speed_ms`, `description`, `fetched_at`

---

### Requirement: Spatial Queries

The system SHALL support querying farms by geographic area.

#### Scenario: Farms within bounding box
- GIVEN a bounding box as `?bbox=minLng,minLat,maxLng,maxLat`
- WHEN `GET /farms?bbox=...` is called
- THEN only farms whose boundary intersects the bounding box are returned
- AND the PostGIS `ST_Intersects` function is used with the spatial index
