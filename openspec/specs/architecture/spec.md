# Architecture Specification

## Purpose

System topology, service boundaries, inter-service communication, and monorepo layout for Khetibadi 2.0.

## Requirements

### Requirement: Monorepo Layout

The project SHALL use a single Turborepo-managed monorepo with a `go.work` workspace for Go services and a Bun workspace for the TypeScript dashboard.

#### Scenario: Go workspace resolution
- GIVEN the monorepo is cloned fresh
- WHEN `go work sync` is run from the root
- THEN all Go services resolve shared `packages/go-shared` module without a registry publish

#### Scenario: TypeScript workspace resolution
- GIVEN the monorepo is cloned fresh
- WHEN `bun install` is run from the root
- THEN `@khetibadi/ui` and `@khetibadi/types` resolve from `packages/` without publishing to npm

#### Scenario: Turborepo task graph
- WHEN `turbo run build` is called
- THEN services build in dependency order: `packages/` first, then `apps/`
- AND Go services run `go build`, Python services run `uv run`, TypeScript runs `bun run build`

---

### Requirement: Service Boundaries

Each service SHALL own exactly one responsibility. No service calls another service's database directly.

#### Scenario: Auth as API gateway
- GIVEN a dashboard request targets a protected backend capability
- WHEN the browser sends the request to the public API gateway
- THEN the auth service validates the user session before proxying downstream
- AND it attaches HMAC-signed identity headers for the target Go or Python service
- AND the target service processes the request without re-calling auth
- AND the user ID is read directly from the HMAC header payload

#### Scenario: No cross-database access
- GIVEN farm-service needs market prices
- WHEN it requires price context for a response
- THEN it calls market-service's HTTP API, not market-service's PostgreSQL tables directly

---

### Requirement: Port Allocation

Each service SHALL bind to a fixed, non-overlapping internal container port in all environments.
Only the dashboard and the public API gateway SHALL be published for browser traffic.

#### Scenario: Port map
- GIVEN all services start in Docker Compose
- THEN internal service ports are allocated as follows:
  - `auth` / public API gateway: 8000
  - `farm-service`: 8001
  - `market-service`: 8002
  - `ml-crop`: 8010
  - `ml-vision`: 8011
  - `ai-chat`: 8012
  - `workers (Asynqmon UI)`: 8080
  - `dashboard (nginx)`: 3000
  - `PostgreSQL`: 5432
  - `Redis`: 6379
- AND browser-facing API traffic is published only through `auth` on port 8000
- AND the dashboard is published on port 3000
- AND downstream application services are reachable only on the Compose network by service name

---

### Requirement: Single Public API Origin

The dashboard SHALL communicate with one public API origin. The gateway SHALL route
requests to downstream services by path and SHALL hide backend service ports from
browser code.

#### Scenario: Dashboard calls one API domain
- GIVEN the dashboard is loaded in a browser
- WHEN it calls any backend capability
- THEN the request uses `VITE_API_BASE_URL` as the only API origin
- AND no `VITE_*` variable exposes `farm-service`, `market-service`, `ml-crop`, `ml-vision`, or `ai-chat` directly

#### Scenario: Gateway route map
- GIVEN a request arrives at the public API gateway
- WHEN the path starts with `/auth/`
- THEN auth handles the request locally
- WHEN the path starts with `/farms/`
- THEN auth proxies the request to `farm-service:8001`
- WHEN the path starts with `/market/`
- THEN auth proxies the request to `market-service:8002`
- WHEN the path starts with `/ml/crop/`
- THEN auth proxies the request to `ml-crop:8010`
- WHEN the path starts with `/ml/vision/`
- THEN auth proxies the request to `ml-vision:8011`
- WHEN the path starts with `/ai/chat/`
- THEN auth proxies the request to `ai-chat:8012`

---

### Requirement: Inter-Service Authentication

Go and Python services SHALL verify requests using HMAC-SHA256 signed headers set by the auth service.

#### Scenario: HMAC header forwarding
- GIVEN a user is authenticated and makes a dashboard request
- WHEN the dashboard calls the public API gateway
- THEN auth routes the request to the target downstream service
- AND auth attaches `X-User-ID` and `X-HMAC-Signature` headers
- AND farm-service verifies the signature using the shared HMAC secret before processing

#### Scenario: Missing HMAC header
- GIVEN a request arrives at farm-service without HMAC headers
- WHEN the middleware checks
- THEN the request is rejected with `401 Unauthorized`
- AND no business logic executes

---

### Requirement: Health Checks

Every service SHALL expose a `GET /health` endpoint that returns `200 OK` with service name and uptime.

#### Scenario: Health check passes
- GIVEN a service is running and DB/Redis connections are live
- WHEN Docker Compose health check polls `/health`
- THEN `{"status": "ok", "service": "<name>", "uptime": <seconds>}` is returned

#### Scenario: Health check fails on dependency down
- GIVEN PostgreSQL is unreachable
- WHEN `/health` is called on farm-service
- THEN `503 Service Unavailable` is returned
- AND the response body includes `{"status": "degraded", "reason": "db unreachable"}`

---

### Requirement: Error Response Format

All HTTP services SHALL return errors in a consistent JSON envelope.

#### Scenario: Validation error
- WHEN a request body fails validation
- THEN the response is `400 Bad Request` with:
  ```json
  { "error": "validation_failed", "details": [{ "field": "email", "message": "required" }] }
  ```

#### Scenario: Internal server error
- WHEN an unhandled error occurs
- THEN the response is `500 Internal Server Error` with:
  ```json
  { "error": "internal_error", "request_id": "<uuid>" }
  ```
- AND the full stack trace is logged server-side only, never exposed to the client

---

### Requirement: Structured Logging

All services SHALL emit structured JSON logs with `level`, `service`, `request_id`, `msg`, and `ts` fields.

#### Scenario: Request log
- WHEN an HTTP request completes
- THEN a log line is emitted with method, path, status code, latency, and user_id (if authenticated)

#### Scenario: Error log
- WHEN a handler returns a 5xx error
- THEN the log includes `"level": "error"` and a full `"error"` string with cause
