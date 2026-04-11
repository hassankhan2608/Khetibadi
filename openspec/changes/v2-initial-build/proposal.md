# Change Proposal: Khetibadi v2 — Initial Build

## ID: v2-initial-build
## Status: Draft
## Date: 2025-05-24

---

## Why

Khetibadi v1 was built as a college project using a fragile single-server Flask backend,
React 18 + Material UI frontend, and an NLTK-based chatbot that only matched canned responses.
The codebase had no separation of concerns, no background job infrastructure, no structured
logging, and no clear deployment path.

This change builds Khetibadi v2 from scratch with production-grade architecture:
- Proper service separation with well-defined API contracts
- Typed, testable Go backends (replacing Python Flask)
- FastAPI for all ML inference (keeping the same models and datasets)
- A modern React 19 frontend with full TypeScript type safety
- A real AI assistant (Groq Llama 3.3 70B) replacing the keyword chatbot
- Background job infrastructure for market sync, weather prefetch, and alerts
- A single PostgreSQL database with PostGIS + pgvector extensions instead of ad-hoc storage

---

## What Changes

### Services Introduced (all new)

| Service | Language | Replaces |
|---------|----------|---------|
| `auth/` | Go (Gin) | Flask auth routes + Express auth middleware |
| `farm-service/` | Go (Gin) | Flask farm routes + PostGIS queries |
| `market-service/` | Go (Gin) | Flask AGMARKNET proxy |
| `workers/` | Go (asynq) | No equivalent (v1 had no background jobs) |
| `ml-crop/` | Python (FastAPI) | Flask ML inference routes |
| `ml-vision/` | Python (FastAPI) | Flask image upload + ResNet inference |
| `ai-chat/` | Python (FastAPI) | NLTK + Keras intent classifier |
| `dashboard/` | TypeScript (React 19 + Vite 6) | React 18 + Material UI |
| `packages/go-shared/` | Go | No equivalent |
| `packages/ui/` | TypeScript (Shadcn) | Material UI components |

### Infrastructure Introduced

- **Turborepo 2.8+** monorepo orchestration (replaces uncoordinated scripts)
- **go.work** workspace for Go services
- **Bun 1.3+** as TS/JS runtime and package manager
- **uv** as Python package manager for ML services
- **Redis 7** for background queues, caching, and rate limiting
- **Asynq + Asynqmon** for job scheduling and monitoring
- **pgvector** for AI chat knowledge base embeddings
- **Docker Compose** for local development

### Models and Datasets (unchanged from v1)

All ML models are retrained from the same datasets:
- Crop recommendation: Kaggle, 2200 rows, RandomForest
- Yield prediction: Govt of India, 1.5M rows, GradientBoostingRegressor
- Fertilizer: Kaggle, 99 rows, RandomForest
- Disease detection: PlantVillage, 54,305 images, ResNet34 (PyTorch)

---

## New Capabilities

| Capability | Details |
|------------|---------|
| Real AI Chat | Groq Llama 3.3 70B with farm/weather/market context injection and RAG |
| SSE Streaming | AI responses stream token-by-token |
| Async Disease Detection | Large images processed in background via asynq |
| Price Alerts | Users set commodity price thresholds; alerts trigger via cron |
| Weather Prefetch | Hourly background prefetch for all farm locations |
| Chat History | Full persistent chat history per user session |
| Knowledge RAG | Agricultural knowledge base embedded in pgvector |
| Typed API Contracts | All routes defined with Zod (TS) and Pydantic v2 (Python) |
| Structured Logging | JSON logs with request_id, service name, level across all services |

---

## Impact

### Breaking Changes

This is a full rewrite. There is no migration path from v1 data.
- v1 database schema is incompatible (UUIDs, PostGIS, pgvector)
- v1 React frontend is replaced entirely
- v1 API endpoints do not carry over

### Risk Surface

- ML model performance must be re-validated after retraining on the same datasets
- Groq API dependency (if Groq is unavailable, AI chat degrades — not fatal)
- OpenWeatherMap API key required for weather features

### Deployment Target

- Local development via Docker Compose
- Future: single-server VPS (4vCPU, 8GB RAM minimum for ML services)
