# Implementation Tasks: Khetibadi v2 — Initial Build

## ID: v2-initial-build
## Status: In Progress

---

## Phase 0 — Repository & Tooling Setup

- [ ] 0.1 `git init` with `laughingman` as default branch
- [ ] 0.2 Create root `.gitignore` (Go, Python, Node, Docker, IDE artefacts)
- [ ] 0.3 Create `turbo.json` with task graph (`build`, `dev`, `lint`, `test`)
- [ ] 0.4 Create root `package.json` with Bun workspaces pointing to `apps/dashboard` and `packages/ui`, `packages/types`
- [ ] 0.5 Create `go.work` referencing `apps/auth`, `apps/farm-service`, `apps/market-service`, `apps/workers`, `packages/go-shared`
- [ ] 0.6 Create root `docker-compose.yml` (postgres:16-postgis, redis:7-alpine, all services)
- [ ] 0.7 Create root `.env.example` with all required env vars
- [ ] 0.8 Create root `Makefile` with targets: `dev`, `build`, `test`, `lint`, `migrate`, `train`
- [ ] 0.9 Add `commitlint.config.js` + `husky` pre-commit hook (lint + test before commit)
- [ ] 0.10 Add `.editorconfig` (indent_size=2, end_of_line=lf, charset=utf-8)

---

## Phase 1 — Database & Migrations

- [ ] 1.1 Create `migrations/` directory with `golang-migrate` SQL files
- [ ] 1.2 Write `001_create_users.sql` — `users` table + `soft_delete` index
- [ ] 1.3 Write `002_create_refresh_tokens.sql` — `refresh_tokens` table + `family_id` index
- [ ] 1.4 Write `003_create_farms.sql` — PostGIS extension + `farms` table + spatial index
- [ ] 1.5 Write `004_create_soil_samples.sql` — `soil_samples` table
- [ ] 1.6 Write `005_create_market_prices.sql` — `market_prices` table + composite index
- [ ] 1.7 Write `006_create_price_alerts.sql` — `price_alerts` table
- [ ] 1.8 Write `007_create_chat_tables.sql` — `chat_sessions` + `chat_messages` tables
- [ ] 1.9 Write `008_create_knowledge_chunks.sql` — `pgvector` extension + `knowledge_chunks` table + HNSW index
- [ ] 1.10 Write `009_create_notifications.sql` — `notifications` table
- [ ] 1.11 Add `migrate.sh` helper script and document in `Makefile`

---

## Phase 2 — `packages/go-shared`

- [ ] 2.1 Init Go module `github.com/khetibadi/go-shared`
- [ ] 2.2 Implement `middleware.RequestID` — inject UUID request_id into Gin context + header
- [ ] 2.3 Implement `middleware.Logger` — zerolog structured JSON request logger for Gin
- [ ] 2.4 Implement `middleware.HMACAuth` — validate `X-User-ID` + `X-HMAC-Signature` + `X-Timestamp` (±5 min replay window)
- [ ] 2.5 Implement `middleware.RateLimiter` — Redis sliding-window rate limiter
- [ ] 2.6 Implement `response.Success(c, data)` — `{"success": true, "data": ...}`
- [ ] 2.7 Implement `response.Error(c, status, code, message)` — `{"success": false, "error": {"code": ..., "message": ...}}`
- [ ] 2.8 Implement `response.Paginated(c, data, total, page, pageSize)` — adds pagination metadata
- [ ] 2.9 Write unit tests for HMAC middleware (valid, expired, wrong signature, missing headers)
- [ ] 2.10 Write unit tests for response helpers

---

## Phase 3 — Auth Service

- [ ] 3.1 Init Go module `github.com/khetibadi/auth` + Gin server on `:8000`
- [ ] 3.2 Implement `GET /health` — DB ping + Redis ping, 200/503
- [ ] 3.3 Implement `POST /auth/register` — validate email + password, bcrypt, insert user
- [ ] 3.4 Add duplicate email handling — 409 with `"email_taken"` code
- [ ] 3.5 Add password strength validation — min 8 chars, 1 upper, 1 digit
- [ ] 3.6 Implement `POST /auth/login` — lookup user, bcrypt compare, issue JWT + refresh token
- [ ] 3.7 Add login rate limiting — 10 attempts per IP per minute (Redis)
- [ ] 3.8 Implement `POST /auth/refresh` — validate refresh token family, rotate token, revoke old
- [ ] 3.9 Add refresh token reuse detection — revoke entire family on reuse
- [ ] 3.10 Implement `POST /auth/logout` — revoke refresh token from DB
- [ ] 3.11 Implement `POST /auth/password/change` — verify current password, update hash
- [ ] 3.12 Implement HMAC signing helper — build `X-User-ID`, `X-HMAC-Signature`, `X-Timestamp` for outgoing requests
- [ ] 3.13 Write integration tests (register/login/refresh/logout happy paths + error cases)
- [ ] 3.14 Write `Dockerfile` for auth service (multi-stage, distroless, <20MB)

---

## Phase 4 — Farm Service

- [ ] 4.1 Init Go module `github.com/khetibadi/farm-service` + Gin server on `:8001`
- [ ] 4.2 Run `sqlc generate` for all farm queries
- [ ] 4.3 Implement `GET /health`
- [ ] 4.4 Implement `POST /farms` — accept GeoJSON polygon, validate, compute area_ha via PostGIS, insert
- [ ] 4.5 Add self-intersecting polygon validation via `ST_IsSimple`
- [ ] 4.6 Add maximum area validation — reject farms > 10,000 ha
- [ ] 4.7 Implement `GET /farms` — list farms owned by `X-User-ID` with pagination
- [ ] 4.8 Implement `GET /farms/:id` — return farm with ownership check (404 if not owner)
- [ ] 4.9 Implement `PUT /farms/:id` — update name/soil_type/primary_crop + optional boundary update
- [ ] 4.10 Implement `DELETE /farms/:id` — cascade delete soil_samples (DB constraint)
- [ ] 4.11 Implement `POST /farms/:id/soil-samples` — add soil sample with GPS coords
- [ ] 4.12 Implement `GET /farms/:id/soil-samples` — paginated list, ordered by collected_at desc
- [ ] 4.13 Implement `GET /farms/:id/soil-samples/latest` — single latest sample (for ML pre-fill)
- [ ] 4.14 Implement `GET /farms/:id/weather` — fetch OpenWeatherMap by centroid, cache 3h in Redis
- [ ] 4.15 Add weather 502 fallback when OpenWeatherMap is unreachable
- [ ] 4.16 Implement `GET /farms?bbox=...` — spatial filter with `ST_Intersects`
- [ ] 4.17 Write integration tests (all endpoints, ownership checks, boundary validation)
- [ ] 4.18 Write `Dockerfile` (multi-stage, distroless, <20MB)

---

## Phase 5 — Market Service

- [ ] 5.1 Init Go module `github.com/khetibadi/market-service` + Gin server on `:8002`
- [ ] 5.2 Run `sqlc generate` for market queries
- [ ] 5.3 Implement `GET /health`
- [ ] 5.4 Implement `GET /market/prices` — paginated commodity price list, Redis 6h cache with `X-Cache` header
- [ ] 5.5 Implement `GET /market/prices/history` — date range query, enforce 2-year max range
- [ ] 5.6 Implement `GET /market/commodities` — distinct commodity list
- [ ] 5.7 Implement `POST /market/alerts` — create price alert, enforce 20-alert limit per user
- [ ] 5.8 Implement `GET /market/alerts` — list user's alerts
- [ ] 5.9 Implement `DELETE /market/alerts/:id` — ownership check, delete
- [ ] 5.10 Implement internal `POST /internal/market/sync` — AGMARKNET fetch + upsert (called by workers)
- [ ] 5.11 Write integration tests (price lookup, cache hit/miss, alert CRUD, limit enforcement)
- [ ] 5.12 Write `Dockerfile` (multi-stage, distroless, <20MB)

---

## Phase 6 — Workers Service

- [ ] 6.1 Init Go module `github.com/khetibadi/workers` + Asynq server
- [ ] 6.2 Register `market:sync_prices` handler — AGMARKNET fetch + upsert + cache invalidation
- [ ] 6.3 Register `market:check_price_alerts` handler — threshold evaluation + trigger notifications
- [ ] 6.4 Register `farm:prefetch_weather` handler — OpenWeatherMap batch prefetch for all farms
- [ ] 6.5 Register `vision:detect_disease` handler — async ResNet34 inference, write result to Redis
- [ ] 6.6 Register `ai:index_knowledge_chunk` handler — embed chunk + save vector to pgvector
- [ ] 6.7 Register `notifications:send` handler — insert notification row
- [ ] 6.8 Register `cleanup:stale_data` handler — delete old chat messages + market prices
- [ ] 6.9 Register `ml:warmup_models` handler — send dummy requests to all ML services
- [ ] 6.10 Set up cron scheduler: `market:sync_prices` every 6h, `farm:prefetch_weather` every 3h, `cleanup:stale_data` daily 2AM IST
- [ ] 6.11 Set up Asynqmon UI on `:8080`
- [ ] 6.12 Enqueue `ml:warmup_models` on worker startup
- [ ] 6.13 Write `Dockerfile` (multi-stage, distroless, <20MB)

---

## Phase 7 — ML Crop Service

- [ ] 7.1 Init FastAPI app with `uv`, `pyproject.toml`, `uvicorn` on `:8010`
- [ ] 7.2 Implement `GET /health` — model load status + version
- [ ] 7.3 Implement model loader — load `crop_model.pkl`, `yield_model.pkl`, `fertilizer_model.pkl` at startup via `lifespan`
- [ ] 7.4 Implement `POST /ml/crop/recommend` — 7-feature inference, return top crop + top_3 + confidence
- [ ] 7.5 Add request validation with Pydantic v2 (range checks: N 0-140, P 5-145, K 5-205, pH 3.5-9.9, etc.)
- [ ] 7.6 Implement `POST /ml/crop/yield` — GBR inference, return yield_t_ha + total_production + confidence_interval
- [ ] 7.7 Add low-confidence warning when yield variance is high
- [ ] 7.8 Implement `POST /ml/crop/fertilizer` — 8-feature inference, return primary + 2 alternatives
- [ ] 7.9 Implement `GET /ml/crop/info` — feature names + importance from crop model
- [ ] 7.10 Implement `POST /ml/crop/batch` — up to 50 records, <500ms
- [ ] 7.11 Add HMAC validation middleware for all endpoints
- [ ] 7.12 Write `tests/` — all inference endpoints + validation edge cases
- [ ] 7.13 Write `scripts/train_crop.py` — reproduce crop model
- [ ] 7.14 Write `scripts/train_yield.py` — reproduce yield model
- [ ] 7.15 Write `scripts/train_fertilizer.py` — reproduce fertilizer model
- [ ] 7.16 Write `Dockerfile` (multi-stage, python:3.12-slim, ~600MB with models)

---

## Phase 8 — ML Vision Service

- [ ] 8.1 Init FastAPI app with `uv`, `pyproject.toml`, `uvicorn` on `:8011`
- [ ] 8.2 Implement `GET /health` — model load status + CUDA availability
- [ ] 8.3 Implement model loader — load `resnet34_plantvillage.pth` + class mapping at startup via `lifespan`
- [ ] 8.4 Implement background removal step using `rembg` (U2Net) — white background composite
- [ ] 8.5 Add `rembg` fallback — if `rembg` fails, proceed without removal + set `background_removed: false`
- [ ] 8.6 Implement OpenCV preprocessing pipeline (LAB → Otsu → morphological → distance → Canny → contour → 128×128 → normalize)
- [ ] 8.7 Add fallback resize (128×128) when no contour found + `fallback_resize: true` flag
- [ ] 8.8 Implement `POST /ml/vision/detect` — full sync pipeline, return annotated base64 image + class + confidence
- [ ] 8.9 Add confidence threshold check (0.60) — return `uncertain` if below
- [ ] 8.10 Implement `POST /ml/vision/detect/async` — enqueue asynq job, return 202 + job_id
- [ ] 8.11 Implement `GET /ml/vision/detect/:job_id` — poll Redis for job result
- [ ] 8.12 Implement `GET /ml/vision/classes` — return all 38 class names grouped by plant
- [ ] 8.13 Add input validation (format: JPG/PNG only; max size: 10MB; min dimensions: 64×64)
- [ ] 8.14 Add HMAC validation middleware
- [ ] 8.15 Write `tests/` — pipeline stages, confidence threshold, input validation, async flow
- [ ] 8.16 Write `scripts/preprocess_bg_remove.py` — rembg preprocessing for PlantVillage dataset
- [ ] 8.17 Write `scripts/train_vision.py` — reproduce ResNet34 training (reads from processed/ folder)
- [ ] 8.18 Write `Dockerfile` (multi-stage, python:3.12-slim with torch CPU or CUDA variant, ~2GB)

---

## Phase 9 — AI Chat Service

- [ ] 9.1 Init FastAPI app with `uv`, `pyproject.toml`, `uvicorn` on `:8012`
- [ ] 9.2 Implement `GET /health` — Groq API ping + DB + Redis status
- [ ] 9.3 Set up pgvector connection using `langchain-postgres`
- [ ] 9.4 Implement `POST /ai/chat/sessions` — create session + insert into `chat_sessions`
- [ ] 9.5 Implement `GET /ai/chat/sessions` — list user sessions ordered by `last_message_at`
- [ ] 9.6 Implement `DELETE /ai/chat/sessions/:id` — ownership check, delete cascade
- [ ] 9.7 Implement `GET /ai/chat/sessions/:id/messages` — paginated history
- [ ] 9.8 Implement context fetcher — fetch farms/weather/market via HTTP with 2s timeout per service
- [ ] 9.9 Implement RAG retrieval — embed query, fetch top-5 knowledge_chunks via pgvector cosine
- [ ] 9.10 Implement system prompt builder — role + farms + weather + market + RAG + instructions
- [ ] 9.11 Implement `POST /ai/chat/sessions/:id/messages` — SSE stream using `StreamingResponse`
- [ ] 9.12 Add degraded mode — proceed if context services are unreachable
- [ ] 9.13 Implement save-on-stream-complete — persist user message + full assistant response to DB
- [ ] 9.14 Add rate limiting — 30 messages/min per user via Redis
- [ ] 9.15 Implement `POST /ai/chat/knowledge` — receive chunk + enqueue `ai:index_knowledge_chunk`
- [ ] 9.16 Add HMAC validation middleware
- [ ] 9.17 Write `tests/` — session CRUD, rate limiting, prompt construction, streaming response structure
- [ ] 9.18 Write `Dockerfile` (multi-stage, python:3.12-slim, ~400MB)

---

## Phase 10 — `packages/ui` (Shadcn Component Library)

- [ ] 10.1 Init Bun package `@khetibadi/ui` with Tailwind CSS 4 + Shadcn/UI base
- [ ] 10.2 Export: Button, Card, CardHeader, CardContent, CardFooter
- [ ] 10.3 Export: Dialog, DialogContent, DialogHeader, DialogTrigger, DialogFooter
- [ ] 10.4 Export: Form, FormField, FormItem, FormLabel, FormControl, FormMessage
- [ ] 10.5 Export: Input, Select, Textarea, Checkbox, RadioGroup
- [ ] 10.6 Export: Table, TableHeader, TableBody, TableRow, TableCell, TableHead
- [ ] 10.7 Export: Tabs, TabsList, TabsTrigger, TabsContent
- [ ] 10.8 Export: Badge, Skeleton, Separator, Tooltip
- [ ] 10.9 Export: Sonner (toast provider)
- [ ] 10.10 Export: Sheet (sidebar on mobile)
- [ ] 10.11 Configure Tailwind CSS 4 theme tokens (green primary palette for agricultural theme)
- [ ] 10.12 Add Storybook (optional) or `packages/ui/README.md` with component usage examples

---

## Phase 11 — Dashboard (`apps/dashboard`)

- [ ] 11.1 Scaffold Vite 6 + React 19 + TypeScript 5.9 app with TanStack Router file-based routing
- [ ] 11.2 Set up TanStack Router dev tools + route tree codegen
- [ ] 11.3 Set up TanStack Query v5 with global QueryClient + error boundary
- [ ] 11.4 Set up Zustand `authStore` (access token in memory, user info)
- [ ] 11.5 Set up Axios instance with baseURL from `VITE_API_BASE_URL` + 401 interceptor for token refresh
- [ ] 11.6 Implement route guard (`beforeLoad`) — redirect to `/login` if not authenticated
- [ ] 11.7 Build `/login` page — React Hook Form + Zod validation + POST /auth/login
- [ ] 11.8 Build `/register` page — form with password strength indicator
- [ ] 11.9 Build `DashboardLayout` — sidebar nav (mobile: Sheet, desktop: fixed sidebar), header with user avatar
- [ ] 11.10 Build `/dashboard` home page — stats row + weather card + market highlights + quick actions
- [ ] 11.11 Add empty state for `/dashboard` (no farms)
- [ ] 11.12 Build `/dashboard/farm-map` — Leaflet map + farm polygon overlays + sidebar panel
- [ ] 11.13 Add farm boundary drawing with Leaflet-Draw
- [ ] 11.14 Add soil samples overlay layer toggle
- [ ] 11.15 Build `/dashboard/crop-advisor` — 3-tab layout (Recommend / Yield / Fertilizer)
- [ ] 11.16 Add "Use values from farm" pre-fill from latest soil sample
- [ ] 11.17 Add Recharts feature importance horizontal bar chart on crop recommendation result
- [ ] 11.18 Build `/dashboard/disease-scan` — drag-drop upload + preview + annotated result display
- [ ] 11.19 Add async polling UI (3s interval) for large image jobs
- [ ] 11.20 Build `/dashboard/market-prices` — TanStack Table + Recharts history modal + alert creation
- [ ] 11.21 Build `/dashboard/ai-assistant` — SSE streaming chat UI + session sidebar
- [ ] 11.22 Implement SSE client with `EventSource` for streaming token-by-token rendering
- [ ] 11.23 Add mobile collapse for chat sidebar (Sheet component)
- [ ] 11.24 Build `/dashboard/settings` — profile display + change password form
- [ ] 11.25 Add error boundaries on all route pages
- [ ] 11.26 Add Skeleton loading states on all async-fetching components
- [ ] 11.27 Write `Dockerfile` (Bun build stage → nginx:alpine serving static, <50MB)

---

## Phase 12 — Docker Compose & Infrastructure

- [ ] 12.1 Write optimised `docker-compose.yml`:
  - `postgres:16-postgis` with PostGIS + pgvector extensions enabled on init
  - `redis:7-alpine` with `--maxmemory 256mb --maxmemory-policy allkeys-lru`
  - All Go services with `restart: unless-stopped` + health checks
  - Both Python services with model volume mounts
  - dashboard nginx static
- [ ] 12.2 Publish only dashboard and auth gateway for browser HTTP traffic; keep downstream service ports internal via Docker networking
- [ ] 12.3 Write `docker-compose.override.yml` for local hot-reload (volume mounts for code)
- [ ] 12.4 Add `postgres/init/` — SQL scripts to create PostGIS + pgvector extensions on first run
- [ ] 12.5 Add `.dockerignore` for each service (exclude `tests/`, `*.md`, `scripts/`, etc.)
- [ ] 12.6 Test full `docker compose up` — verify all health checks pass

---

## Phase 13 — CI/CD

- [ ] 13.1 Create `.github/workflows/ci.yml` — run `golangci-lint` + `go test` for all Go services
- [ ] 13.2 Add Python lint step — `ruff check .` + `mypy .` for ml-crop, ml-vision, ai-chat
- [ ] 13.3 Add TypeScript check — `bun run type-check` + `bun run lint` for dashboard
- [ ] 13.4 Add `docker build` dry-run for all services (no push)
- [ ] 13.5 Run migrations test against ephemeral PostgreSQL

---

## Commit Plan

Each task above maps to one commit following `<type>(<scope>): <short description>` format.

Example sequence:
```
chore: init repo with laughingman as default branch
docs(specs): add architecture spec
docs(specs): add auth spec
docs(specs): add database spec
docs(specs): add farm spec
docs(specs): add market spec
docs(specs): add ml-crop spec
docs(specs): add ml-vision spec with background removal pipeline
docs(specs): add ml-training spec with rembg preprocessing
docs(specs): add ai-chat spec
docs(specs): add workers spec
docs(specs): add dashboard spec
docs(specs): add v2-initial-build proposal
docs(specs): add v2-initial-build design
docs(specs): add v2-initial-build tasks
docs: add AGENTS.md with coding standards and commit conventions
chore: add turbo.json and root package.json
chore: add go.work workspace
chore: add root Makefile
chore: add docker-compose.yml base
...
```

Target: ≥ 100 commits by end of Phase 13.
