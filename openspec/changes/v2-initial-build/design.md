# Technical Design: Khetibadi v2 — Initial Build

## ID: v2-initial-build
## Status: Draft
## Date: 2025-05-24

---

## Context

Khetibadi v1 was a monolithic Flask + React application built for a college demonstration.
It served all 7 modules from a single Python process with no separation of concerns,
no background jobs, no caching layer, and no deployment strategy.

Khetibadi v2 is a production-grade reimplementation of the same agricultural intelligence
platform using a modern, well-separated service architecture.

---

## Goals

1. Separate ML inference from API serving (FastAPI for ML, Go for data APIs)
2. Replace the keyword chatbot with a real LLM-powered AI assistant
3. Add background job infrastructure for market sync and weather prefetch
4. Use typed, contract-driven development across all services
5. Enable a single Docker Compose command to start the full platform locally
6. Keep all original ML models and datasets — only replace the serving layer

---

## Non-Goals

- Multi-tenant SaaS architecture
- OAuth / social login
- Mobile app
- Data migration from v1
- Real-time websocket chat (SSE is sufficient)

---

## Architecture Decisions

### Decision 1: Go for Data Services, Python for ML Services

**Decision:** Use Go (Gin) for auth, farm-service, market-service, and workers.
Use Python (FastAPI) for ml-crop, ml-vision, and ai-chat.

**Reasoning:**
- Go is statically typed, compiles fast, has excellent standard library HTTP handling,
  and the Go services never touch ML libraries — so Python is not needed there.
- Python FastAPI is the natural choice for ML inference: scikit-learn, PyTorch, and
  LangChain are Python-native. FastAPI gives async I/O and Pydantic v2 validation.
- This avoids running unnecessary Python processes for non-ML work.

**Trade-off:** Two languages to maintain. Accepted — they are cleanly separated with
no shared code except HTTP contracts.

---

### Decision 2: Hono Replaced by Gin for Auth Gateway

**Decision:** Auth service uses Gin v1 (Go), not Hono (Bun/TS) as originally considered.

**Reasoning:**
- All data services (farm, market, workers) are already in Go.
- Sharing the `go-shared` middleware package for HMAC verification and zerolog logging
  is cleaner than a TS/Go split at the gateway layer.
- Gin is battle-tested, has lower cold-start latency than Bun, and the team is already
  writing Go for other services.

---

### Decision 3: TanStack Router over Next.js

**Decision:** Dashboard uses TanStack Router v1 (file-based, typed) instead of Next.js.

**Reasoning:**
- No SSR or SSG is needed — this is a fully authenticated SPA.
- Next.js adds complexity (server components, API routes) that is not required here.
- TanStack Router gives type-safe route parameters and search params with less overhead.
- Aligns with the React 19 + Vite 6 SPA model used in the FlosBridge 2.0 reference.

---

### Decision 4: Single PostgreSQL Database with PostGIS + pgvector

**Decision:** One PostgreSQL 16 instance with PostGIS and pgvector extensions.
No separate vector database.

**Reasoning:**
- pgvector supports HNSW indexes sufficient for a knowledge base of thousands of chunks.
- Avoiding a separate Pinecone/Weaviate/Qdrant reduces operational complexity.
- PostGIS for farm boundary geometry lives naturally in the same DB.
- All services connect to the same PostgreSQL instance with isolated schema access.

---

### Decision 5: Asynq over BullMQ for Workers

**Decision:** Background jobs use `hibiken/asynq` (Go, Redis-backed), not BullMQ (TS).

**Reasoning:**
- Workers service is in Go alongside the other data services.
- Asynq has built-in Asynqmon UI, cron scheduling, priority queues, and retry policies.
- Avoids running a separate Bun/TS process just for job handling.

---

### Decision 6: Groq Llama 3.3 70B for AI Chat

**Decision:** AI chat uses Groq API (Llama 3.3 70B via `ChatGroq` LangChain integration).

**Reasoning:**
- Groq provides free-tier API access with fast inference (hundreds of tokens/second).
- Llama 3.3 70B has strong agricultural domain knowledge.
- LangChain provides clean streaming + RAG chain abstractions.
- No GPU infrastructure required for the chat service.

**Risk:** Groq API is an external dependency. Mitigated by:
- Graceful degradation (503 with descriptive error if Groq is down)
- Health check endpoint exposes Groq reachability status

---

### Decision 7: uv as Python Package Manager

**Decision:** All Python services (ml-crop, ml-vision, ai-chat) use `uv` for package management.

**Reasoning:**
- uv is 10-100x faster than pip for installs.
- `pyproject.toml` + `uv.lock` provides reproducible builds.
- Works naturally with Docker multi-stage builds.

---

## Full Technology Stack

### Frontend: `apps/dashboard/`

| Library | Version | Purpose |
|---------|---------|---------|
| React | 19 | UI framework |
| Vite | 6 | Build tool + dev server |
| TypeScript | 5.9 (strict) | Type safety |
| TanStack Router | v1 | File-based typed routing |
| TanStack Query | v5 | Server state management |
| TanStack Table | v8 | Market prices table |
| Shadcn/UI | latest | Component library (from @khetibadi/ui) |
| Tailwind CSS | 4 | Utility CSS |
| Radix UI | latest | Headless primitives |
| React Hook Form | v7 | Form management |
| Zod | v4 | Schema validation |
| Recharts | 3 | Data charts |
| Leaflet | 1.9 | Farm map |
| React-Leaflet | 4 | React bindings for Leaflet |
| Leaflet-Draw | 1.0 | Farm boundary drawing |
| Turf.js | 6 | Client-side GIS calculations |
| Zustand | v5 | Global client state |
| Axios | 1.x | HTTP client (with interceptors) |
| Sonner | 2 | Toast notifications |
| Motion | 12 | Animations |

### Auth Service: `apps/auth/`

| Library | Version | Purpose |
|---------|---------|---------|
| Go | 1.24+ | Runtime |
| Gin | v1 | HTTP framework |
| golang-jwt/jwt | v5 | JWT signing/verification |
| bcrypt (crypto/bcrypt) | stdlib | Password hashing |
| go-redis | v9 | Redis client (rate limiting, token blocklist) |
| pgx | v5 | PostgreSQL driver |
| zerolog | latest | JSON structured logging |
| go-playground/validator | v10 | Request validation |

### Farm Service: `apps/farm-service/`

| Library | Version | Purpose |
|---------|---------|---------|
| Go | 1.24+ | Runtime |
| Gin | v1 | HTTP framework |
| sqlc | v2 | Type-safe SQL codegen |
| pgx | v5 | PostgreSQL + PostGIS driver |
| go-redis | v9 | Weather cache (3h TTL) |
| zerolog | latest | Logging |

### Market Service: `apps/market-service/`

| Library | Version | Purpose |
|---------|---------|---------|
| Go | 1.24+ | Runtime |
| Gin | v1 | HTTP framework |
| sqlc | v2 | Type-safe SQL codegen |
| pgx | v5 | PostgreSQL driver |
| go-redis | v9 | Price cache (6h TTL) |
| zerolog | latest | Logging |

### Workers: `apps/workers/`

| Library | Version | Purpose |
|---------|---------|---------|
| Go | 1.24+ | Runtime |
| hibiken/asynq | v0.24+ | Job queue (Redis-backed) |
| hibiken/asynqmon | latest | Web dashboard (:8080) |
| go-redis | v9 | Redis client |
| robfig/cron | v3 | Cron job scheduler |
| zerolog | latest | Logging |

### ML Crop Service: `apps/ml-crop/`

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | 0.115+ | HTTP framework |
| uvicorn | 0.34+ | ASGI server |
| scikit-learn | 1.6+ | RandomForest + GBR inference |
| joblib | 1.4+ | Model serialization |
| pandas | 2.2+ | Data manipulation |
| numpy | 2.0+ | Numerical ops |
| Pydantic | v2 | Request/response validation |

### ML Vision Service: `apps/ml-vision/`

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | 0.115+ | HTTP framework |
| PyTorch | 2.4+ | ResNet34 inference |
| TorchVision | 0.19+ | Model + transforms |
| OpenCV | 4.10+ | Image preprocessing pipeline |
| Pillow | 10+ | Image loading |
| Pydantic | v2 | Validation |

### AI Chat Service: `apps/ai-chat/`

| Library | Version | Purpose |
|---------|---------|---------|
| Python | 3.12 | Runtime |
| FastAPI | 0.115+ | HTTP framework + SSE |
| LangChain | 0.3+ | LLM chain orchestration |
| langchain-groq | 0.2+ | Groq ChatGroq integration |
| langchain-postgres | latest | pgvector retriever |
| psycopg | 3.x | PostgreSQL driver |
| Pydantic | v2 | Validation |
| redis-py | 5.x | Rate limiting |

### Shared Go Package: `packages/go-shared/`

| Provides | Description |
|----------|-------------|
| `middleware.HMACAuth` | Validates X-User-ID + X-HMAC-Signature on incoming requests |
| `middleware.RequestID` | Injects request_id into context and response headers |
| `middleware.Logger` | zerolog request logger middleware for Gin |
| `response.Success` | Standard JSON success envelope helper |
| `response.Error` | Standard JSON error envelope helper |
| `models.User` | Shared user model struct |

---

## Database Schema Summary

See `openspec/specs/database/spec.md` for full DDL.

Key tables:
- `users` — UUID PK, soft delete, bcrypt password
- `refresh_tokens` — family-based revocation for token rotation
- `farms` — PostGIS GEOMETRY POLYGON, area_ha computed column
- `soil_samples` — linked to farms, used as ML pre-fill
- `market_prices` — commodity+market upsert, indexed for fast lookups
- `chat_sessions` + `chat_messages` — persistent AI chat history
- `knowledge_chunks` — pgvector 1536-dim, HNSW index for RAG
- `price_alerts` — user-configured price thresholds

---

## HMAC Inter-Service Authentication

All Go services verify downstream requests using HMAC-SHA256:

```
Signature = HMAC-SHA256(key=HMAC_SECRET, message="<user_id>:<unix_timestamp>")
```

Headers sent by auth service (and forwarded by frontend via Axios):
- `X-User-ID: <uuid>`
- `X-HMAC-Signature: <hex_signature>`
- `X-Timestamp: <unix_timestamp>` (replay attack window: ±5 minutes)

Python FastAPI services use a shared `hmac_auth` middleware that replicates the same logic.

---

## ML Model Artifacts

| Artifact | Path in Service | Format |
|----------|----------------|--------|
| `crop_model.pkl` | `ml-crop/models/` | joblib |
| `yield_model.pkl` | `ml-crop/models/` | joblib |
| `fertilizer_model.pkl` | `ml-crop/models/` | joblib |
| `resnet34_plantvillage.pth` | `ml-vision/models/` | PyTorch checkpoint |

Model files are NOT committed to git. They are generated by training scripts in
`ml-crop/scripts/` and `ml-vision/scripts/` and stored locally.

---

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| Groq API downtime | Low | Graceful 503, health check |
| AGMARKNET API rate limits | Medium | 6h Redis cache, cron not on-demand |
| PlantVillage model overfitting | Low | Same training procedure as v1 (95% val acc) |
| PostgreSQL PostGIS extension missing | Low | Docker Compose pins postgres:16-postgis |
| pgvector dimension mismatch | Low | Schema enforces `vector(1536)` at DB level |
| Redis data loss (job queue) | Low | Asynq persists jobs in Redis RDB; acceptable for non-critical jobs |
