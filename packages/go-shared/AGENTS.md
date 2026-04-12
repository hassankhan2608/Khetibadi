# AGENTS.md — packages/go-shared

> Go shared library. Imported by all Go services (auth, farm-service, market-service, workers).
> Read root AGENTS.md first, then this file.

## Purpose

Zero-business-logic shared code only. If a package here starts importing service-specific
types, it belongs in the service, not here.

## Layout

```
packages/go-shared/
├── middleware/
│   ├── hmac_auth.go            # Gin middleware: verify X-HMAC-Signature + X-User-ID + X-Timestamp
│   ├── hmac_auth_test.go
│   ├── request_id.go           # inject X-Request-ID (UUID v4) if absent
│   └── logger.go               # structured slog request logger
├── response/
│   ├── response.go             # JSON envelope helpers: OK(), Error(), Paginated()
│   └── errors.go               # sentinel error codes (string constants)
├── pagination/
│   └── pagination.go           # ParsePage(c *gin.Context) → Page{Limit, Offset, Page}
├── validate/
│   └── validate.go             # go-playground/validator v10 singleton + helpers
├── config/
│   └── config.go               # envconfig loader (kelseyhightower/envconfig)
├── go.mod                      # module: github.com/khetibadi/go-shared
└── go.sum
```

## HMAC Verification Contract

```go
// middleware/hmac_auth.go
// Expected headers:
//   X-User-ID:        <uuid>
//   X-HMAC-Signature: hex(HMAC-SHA256(key=HMAC_SECRET, msg="<user_id>:<unix_timestamp>"))
//   X-Timestamp:      <unix_seconds>
//
// Replay window: ±300 seconds from server time.
// On success: sets gin context key "user_id" (string UUID).
// On failure: aborts with 401 {"error": "unauthorized"}.
```

**This is the single source of truth for HMAC verification.** All Go services import
this middleware. Do NOT copy-paste the verification logic into individual services.

## Response Envelope

```go
// response/response.go
// Success:
//   {"data": <T>, "meta": <M>}          // OK(c, data, meta)
//   {"data": <T>}                        // OK(c, data, nil)
// Error:
//   {"error": "<code>", "message": "<human>"}  // Error(c, status, code, msg)
// Paginated:
//   {"data": [...], "meta": {"page": 1, "limit": 20, "total": 100}}
```

## Key Invariants

- **No Gin imports in `response/`, `pagination/`, `validate/`, `config/`** — keep them
  framework-agnostic for testability.
- **HMAC_SECRET** is read from env inside the middleware, not passed as a parameter.
  Services do not need to know the secret — they just mount the middleware.
- **Replay window is ±300 seconds** — do not change without updating auth service and all
  Python `hmac_auth.py` files in the same commit.
- **Pagination defaults:** `limit` default 20, max 100. Clamp silently (no error on >100).
- **No global state** except the validator singleton (initialized once via `sync.Once`).

## Adding New Shared Code

Before adding anything here, ask:
1. Is it used by ≥2 Go services? If no → put it in the service.
2. Does it import any service-specific domain type? If yes → it does not belong here.
3. Does it have tests? If no → write them before merging.

## Dev Commands

```bash
cd packages/go-shared
go test ./... -race -count=1
golangci-lint run ./...
```

## Consumers

- `apps/auth` — imports `middleware`, `response`, `config`
- `apps/farm-service` — imports `middleware`, `response`, `pagination`, `config`
- `apps/market-service` — imports `middleware`, `response`, `pagination`, `config`
- `apps/workers` — imports `config`
