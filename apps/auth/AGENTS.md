# AGENTS.md — apps/auth

> Go service. Port 8000. JWT auth, user management, HMAC downstream signing.
> This file overrides root AGENTS.md for anything auth-specific.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Single responsibility: authenticate users and issue credentials. This service
does NOT own farm data, market data, or ML inference. It owns:
- `users` table
- `refresh_tokens` table
- JWT issuance and verification
- HMAC header signing for downstream services

## Layout

```
apps/auth/
├── cmd/server/main.go          # wire deps, start Gin on :8000
├── internal/
│   ├── domain/                 # user.go, token.go — no framework imports
│   ├── handler/                # auth_handler.go + auth_handler_test.go
│   ├── service/                # auth_service.go + auth_service_test.go
│   └── repository/             # user_repo.go, token_repo.go + tests
├── .golangci.yml
├── Dockerfile
├── go.mod                      # module: github.com/khetibadi/auth
└── go.sum
```

## Key Invariants

- **JWT payload:** `sub` (UUID), `email`, `iat`, `exp` only. No roles, no permissions.
- **Refresh token rotation:** every `/auth/refresh` call issues a new token and revokes the old one.
- **Reuse detection:** if a rotated (already-used) refresh token is presented, revoke the entire family.
- **HMAC signing:** `HMAC-SHA256(key=HMAC_SECRET, message="<user_id>:<unix_timestamp>")`. Replay window ±5 min.
- **bcrypt cost:** 12. Never lower.
- **Rate limit:** 5 failed login attempts per IP per 10 minutes → 429 with `Retry-After`.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /health | none | DB + Redis ping |
| POST | /auth/register | none | Create user |
| POST | /auth/login | none | Issue JWT + refresh cookie |
| POST | /auth/refresh | cookie | Rotate refresh token |
| POST | /auth/logout | cookie | Revoke refresh token |
| PUT | /auth/password | JWT | Change password |

## HMAC Headers Emitted

```
X-User-ID: <uuid>
X-HMAC-Signature: <hex>
X-Timestamp: <unix_seconds>
```

All downstream Go and Python services verify these. Do NOT change the signing
formula without updating `packages/go-shared/middleware/hmac_auth.go` and all
Python `hmac_auth.py` middleware files in the same commit.

## Critical Pitfalls

- **NEVER** return different errors for "wrong password" vs "unknown email" — both must return
  `401 invalid_credentials` to prevent email enumeration.
- **NEVER** store the raw refresh token — store its bcrypt hash.
- **NEVER** issue a new refresh token without revoking the previous one in the same DB transaction.
- **NEVER** expose the JWT secret or HMAC secret in logs or error responses.

## Dev Commands

```bash
cd apps/auth
go run ./cmd/server          # start on :8000
go test ./... -race -count=1 # run tests
golangci-lint run ./...      # lint
```

## Spec Reference

`openspec/specs/auth/spec.md` — all endpoint behaviour is defined there.
