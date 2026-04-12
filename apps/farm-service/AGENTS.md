# AGENTS.md — apps/farm-service

> Go service. Port 8001. Farm CRUD, PostGIS boundaries, soil samples, weather cache.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Owns all farm and soil data. Does NOT call auth's database — it trusts the HMAC
headers forwarded by the frontend (via auth). Calls OpenWeatherMap for weather.

Owns:
- `farms` table (PostGIS GEOMETRY POLYGON)
- `soil_samples` table
- Weather cache in Redis (`weather:farm:<id>`, TTL 3h)

## Layout

```
apps/farm-service/
├── cmd/server/main.go
├── internal/
│   ├── domain/                 # farm.go, soil_sample.go
│   ├── handler/                # farm_handler.go, soil_handler.go, weather_handler.go
│   ├── service/                # farm_service.go, weather_service.go
│   └── repository/             # farm_repo.go (sqlc-generated + wrappers)
├── db/
│   └── queries/                # .sql files for sqlc
├── .golangci.yml
├── Dockerfile
├── go.mod                      # module: github.com/khetibadi/farm-service
└── go.sum
```

## Key Invariants

- **Ownership check:** every handler reads `X-User-ID` from context (set by HMACAuth middleware).
  Return `404` (not `403`) when a farm exists but belongs to another user — do not reveal existence.
- **Area calculation:** use `ST_Area(ST_Transform(boundary, 3857)) / 10000` for hectares. Never compute client-side.
- **Boundary validation:** `ST_IsSimple` for self-intersection; reject if area > 10,000 ha.
- **Weather cache key:** `weather:farm:<farm_id>` — TTL 3h. Return cached result with no upstream call on hit.
- **sqlc:** all SQL queries go through sqlc-generated code. No raw string queries.

## PostGIS Notes

- Store boundaries as `GEOMETRY(POLYGON, 4326)` (WGS84).
- Use `ST_GeomFromGeoJSON` to parse incoming GeoJSON.
- Use `ST_AsGeoJSON` to serialize outgoing boundaries.
- Spatial index: `CREATE INDEX ON farms USING GIST(boundary)`.
- Bbox filter: `ST_Intersects(boundary, ST_MakeEnvelope($minLng, $minLat, $maxLng, $maxLat, 4326))`.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | DB + Redis ping |
| POST | /farms | Create farm with GeoJSON polygon |
| GET | /farms | List user's farms (+ ?bbox= filter) |
| GET | /farms/:id | Get farm with boundary |
| PUT | /farms/:id | Update farm fields |
| DELETE | /farms/:id | Delete farm + cascade soil samples |
| POST | /farms/:id/soil-samples | Add soil sample |
| GET | /farms/:id/soil-samples | List soil samples (paginated) |
| GET | /farms/:id/weather | Current weather (Redis-cached) |

## Critical Pitfalls

- **NEVER** call auth service's database directly — trust HMAC headers only.
- **NEVER** use `SELECT *` — sqlc enforces explicit columns.
- **NEVER** skip the ownership check before any mutation.
- Weather 502: when OpenWeatherMap is unreachable, return `502` with `weather_service_unavailable`.
  Do NOT return 500 — the upstream failure is not our fault.

## Dev Commands

```bash
cd apps/farm-service
go run ./cmd/server
go test ./... -race -count=1
golangci-lint run ./...
# Regenerate sqlc after changing db/queries/*.sql:
sqlc generate
```

## Spec Reference

`openspec/specs/farm/spec.md`
