# AGENTS.md — apps/market-service

> Go service. Port 8002. AGMARKNET commodity prices, Redis cache, price alerts.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Owns all market price data. Prices are populated by the workers service (not on-demand
from AGMARKNET). This service serves reads from PostgreSQL with a 6h Redis cache layer.

Owns:
- `market_prices` table
- `price_alerts` table
- Redis cache (`market:<commodity>:<state>`, TTL 6h)

## Layout

```
apps/market-service/
├── cmd/server/main.go
├── internal/
│   ├── domain/                 # price.go, alert.go
│   ├── handler/                # price_handler.go, alert_handler.go
│   ├── service/                # price_service.go, alert_service.go
│   └── repository/             # price_repo.go, alert_repo.go (sqlc)
├── db/
│   └── queries/
├── .golangci.yml
├── Dockerfile
├── go.mod                      # module: github.com/khetibadi/market-service
└── go.sum
```

## Key Invariants

- **Cache key format:** `market:<commodity>:<state>` (lowercase, URL-encoded).
- **Cache header:** always set `X-Cache: HIT` or `X-Cache: MISS` on price responses.
- **Alert limit:** max 20 active alerts per user. Return `422 alert_limit_reached` on the 21st.
- **Alert ownership:** always verify `X-User-ID` matches `price_alerts.user_id` before delete.
- **History range:** reject `from`–`to` ranges > 730 days with `400 range_too_large`.
- **Internal sync endpoint:** `POST /internal/market/sync` is called only by the workers service.
  It must NOT be exposed to the public internet (Docker network only).

## Cache Invalidation

The workers service invalidates all `market:*` keys after a successful sync.
This service does NOT invalidate its own cache — it only reads and writes.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | none | DB + Redis ping |
| GET | /market/prices | HMAC | Paginated prices (cached) |
| GET | /market/prices/history | HMAC | Date-range trend data |
| GET | /market/commodities | HMAC | Distinct commodity list |
| GET | /market/commodities/:name/states | HMAC | States for a commodity |
| POST | /market/alerts | HMAC | Create price alert |
| GET | /market/alerts | HMAC | List user's alerts |
| DELETE | /market/alerts/:id | HMAC | Delete alert |
| POST | /internal/market/sync | internal | Upsert prices (workers only) |

## Critical Pitfalls

- **NEVER** call AGMARKNET directly from this service — that is the workers service's job.
- **NEVER** expose `/internal/market/sync` outside the Docker network.
- Empty result for unknown commodity is `200 []` not `404` — AGMARKNET treats unknown as empty.

## Dev Commands

```bash
cd apps/market-service
go run ./cmd/server
go test ./... -race -count=1
golangci-lint run ./...
sqlc generate
```

## Spec Reference

`openspec/specs/market/spec.md`
