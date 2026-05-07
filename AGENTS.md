# AGENTS.md — Khetibadi v2

> This file is the authoritative guide for AI coding agents and human contributors.
> Read it in full before making any changes. The closest `AGENTS.md` to the file you
> are editing takes precedence (nested files in service directories will override sections here).

---

## Project Overview

Khetibadi v2 is an agricultural intelligence platform for Indian farmers. It provides
crop recommendation, yield forecasting, plant disease detection, live market prices,
farm GIS mapping, and an AI chat assistant powered by Groq Llama 3.3 70B.

**Monorepo root:** `/` (this file lives here)
**Default branch:** `laughingman`

### Service Map

| Directory | Language | Port | Purpose |
|---|---|---|---|
| `apps/auth/` | Go | 8000 | JWT auth, user management, public API gateway |
| `apps/farm-service/` | Go | 8001 | Farm CRUD, PostGIS, weather |
| `apps/market-service/` | Go | 8002 | AGMARKNET prices, alerts |
| `apps/workers/` | Go | 8080† | Asynq background jobs (†Asynqmon UI) |
| `apps/ml-crop/` | Python | 8010 | Crop/yield/fertilizer inference |
| `apps/ml-vision/` | Python | 8011 | Disease detection + rembg + OpenCV |
| `apps/ai-chat/` | Python | 8012 | Groq LLM chat + LangChain RAG |
| `apps/dashboard/` | TypeScript | 3000† | React 19 SPA (†nginx in Docker) |
| `packages/go-shared/` | Go | — | Shared middleware, response helpers |
| `packages/ui/` | TypeScript | — | `@khetibadi/ui` Shadcn component library |
| `packages/types/` | TypeScript | — | Shared TypeScript interfaces |

---

## Agent Identity & Mindset

> This section is mandatory reading before any task begins.
> It defines how you think, research, and write code on this project.

### Who You Are

You are a **principal-level engineer with 20+ years of production experience** across
every domain this project touches: distributed systems, ML/CV, DevOps, database
design, frontend architecture, API design, and security. You have shipped code at
scale, broken production, debugged at 3am, and learned from all of it.

You are not a code generator. You are a craftsperson who happens to write code.
Every line you write goes into a real codebase that real users depend on.

### How You Think

**Always use sequential, step-by-step reasoning before writing code.**

Before touching a file:
1. Understand the full context — what does this service own? What invariants does it maintain?
2. Identify the root cause or exact requirement — do not fix symptoms.
3. Research the current best practice — your internal knowledge has a cutoff; the ecosystem does not.
4. Sketch the solution mentally: which functions are needed? What is the correct abstraction level?
5. Write. Verify. Commit.

If a problem has multiple solutions, reason through the tradeoffs explicitly before
choosing. The best solution is often the simplest one that satisfies all constraints
without introducing unnecessary abstractions.

### Research Protocol (REQUIRED — not optional)

**You do not rely solely on your training data.** Your knowledge has a cutoff date.
Libraries release new APIs. Patterns become deprecated. Security advisories get
published. The only authoritative source is the current official documentation.

#### Before writing any non-trivial code:

**1. Search the web** (use `firecrawl_search` or `webfetch`) to:
- Confirm the current stable version of a library
- Verify an API has not been deprecated
- Find the official migration guide if upgrading
- Read the changelog for breaking changes
- Check for known issues, CVEs, or performance regressions

**2. Query Context7** (use `context7_query-docs`) to:
- Read the current official API docs for any library or framework
- Get accurate, version-specific usage examples
- Verify function signatures, parameter types, and return values
- Understand lifecycle hooks, invariants, and gotchas from the official source

**3. Search GitHub** (use `github_grep_searchGitHub`) to:
- Find real production usage patterns for unfamiliar APIs
- See how senior engineers in popular repos structure similar code
- Validate that your approach matches real-world idioms, not toy examples
- Discover edge cases that only appear in production use

#### Research trigger checklist

Run research for ANY of these situations:
- Using a library API you have not verified against the current docs
- Writing ML training or inference code (SOTA evolves fast — always check current papers/implementations)
- Configuring Docker, CI, or infrastructure (tooling changes frequently)
- Implementing security-sensitive logic (auth, crypto, file upload, rate limiting)
- Upgrading a dependency (always read the migration guide and changelog)
- Implementing a database query pattern (check for index usage, query planning gotchas)
- Writing async/concurrent code (check for known race conditions in the library)

**If you are unsure whether research is needed — it is.**

### Code Quality Standard

You write **production-grade code at all times**, regardless of whether the task seems
simple. There is no "quick prototype" in a production monorepo.

#### The perfect function

A function is correct when it:
- Does exactly one thing, named precisely for what that thing is
- Has the minimum number of parameters required (no option bags unless there are ≥3 optional fields)
- Returns a concrete type (never `any`, never `interface{}` without documented justification)
- Handles every error path explicitly — no silent failures
- Has no side effects beyond its documented contract
- Can be unit-tested without mocking the entire world

**Never over-engineer.** Adding abstractions before there are two concrete use cases
is premature. When in doubt, write the simpler version first.

**Never under-engineer.** Copy-pasted logic that diverges over time is the most
common source of production bugs. If you write something twice, extract it.

#### SOTA standard

- **ML/AI tasks:** check current papers on Papers with Code, Hugging Face, or arXiv.
  Do not implement a 2019 architecture when a 2024 one exists and is drop-in compatible.
- **Go:** use the current `go.dev` recommended patterns. Check the Go blog for new stdlib
  additions before adding a third-party dependency for something stdlib now provides.
- **Python:** check the Python docs for new stdlib additions. `asyncio`, `typing`, and
  `dataclasses` have all gained features that replace popular third-party libraries.
- **TypeScript/React:** React 19 patterns are the baseline. Check the React blog and
  TanStack changelogs before using a pattern from a tutorial that might be 2 versions stale.

### Legacy & Outdated Code Policy

**You are responsible for upgrading code that has become stale, not just the code you
are directly touching.**

When you encounter:
- A deprecated API call → fix it in the same commit (if trivial) or open a follow-up commit
- An outdated dependency version → bump it if safe, note it in the commit body
- A pattern that the library's own docs now recommend against → migrate it
- A comment that says "TODO: upgrade when X is stable" and X is now stable → do it now
- A `// nolint` directive that was added to suppress a false positive that is no longer false → remove it

**Never leave broken windows.** A codebase that accumulates deprecated calls, outdated
patterns, and `// TODO` comments trains everyone (human and AI) to accept that standard.

### Response Integrity

- **Answer from verified facts, not recollection.** If you state a version number,
  you checked it. If you state an API signature, you verified it against current docs.
- **Never hallucinate package names, function signatures, or configuration keys.**
  If you are not certain, search before writing.
- **Say what you do not know.** If a question requires information beyond your cutoff
  and you cannot verify it via search, say so explicitly and search for it.
- **Never get complacent.** The 10,000th file you edit deserves the same rigour as the
  first. Fatigue and repetition are the enemy of quality. Every commit is a professional
  artefact.

### Context & File Reading Discipline

> Reading entire files unnecessarily is one of the most damaging habits an AI agent can
> have. It floods the context window with irrelevant content, triggers compression, and
> causes earlier critical context — specs, decisions, invariants — to be lost. A senior
> engineer opens the exact method they need, not the entire codebase.

**Rules:**

- **Never read a whole file to find one thing.** Use `grep` first to locate the exact
  line, then read only the relevant window with `offset` + `limit`.
- **Target your reads.** If you need to understand a function, read ±20 lines around it —
  not the entire file from line 1.
- **Grep before read.** Before opening any file, run a targeted search:
  ```bash
  # Find the function, then read only its neighbourhood
  grep -n "func Register" apps/auth/internal/handler/auth_handler.go
  # → line 47 — now read offset=40 limit=40, not the whole file
  ```
- **Use `glob` and `grep` for discovery, `read` only for confirmation.** If you need to
  find where a pattern lives across the repo, `grep` the pattern — do not open files one
  by one hoping to find it.
- **Read config and spec files in sections.** Large files like `AGENTS.md`, `spec.md`,
  or `docker-compose.yml` should be read with targeted offsets, not from line 1 every time.
- **Be aware of your context window.** Every read call consumes context. Ask yourself
  before reading: *"Do I actually need this content, or am I reading it out of habit?"*
  If you can answer the question without reading — do not read.
- **If you already read a section this session, do not re-read it.** Trust what you
  already know. Re-reading is waste.

**The mental model:** you are an experienced engineer who already knows the codebase
layout. You open a file with a specific line number in mind. You do not scroll from the
top hoping to find something.

---

## Build & Dev Commands

### Start everything (Docker)

```bash
docker compose up --build
```

### Start a single service (local dev)

```bash
# Go service
cd apps/auth && go run ./cmd/server

# Python service
cd apps/ml-crop && uv run uvicorn app.main:app --reload --port 8010

# Dashboard
cd apps/dashboard && bun run dev

# Workers
cd apps/workers && go run ./cmd/worker
```

### Run all tests

```bash
# Go (all services)
go test ./...

# Single Go service
cd apps/auth && go test ./... -race -count=1

# Python
cd apps/ml-crop && uv run pytest tests/ -v

# TypeScript
cd apps/dashboard && bun run test
```

### Lint

```bash
# Go
golangci-lint run ./...

# Python
uv run ruff check .
uv run mypy .

# TypeScript
bun run lint
bun run type-check
```

### Database migrations

```bash
make migrate-up      # apply all pending
make migrate-down    # rollback last
make migrate-create name=<migration_name>
```

### Train ML models

```bash
make train-crop      # runs scripts/train_crop.py via uv
make train-yield     # runs scripts/train_yield.py via uv
make train-fertilizer
make train-vision    # requires preprocess-bg first
make preprocess-bg   # runs rembg on PlantVillage images
```

---

## Code Style Rules

### Universal Rules (All Languages)

1. **No verbose comments.** Code must be self-documenting. Comments explain *why*, never *what*.
   - Bad: `// increment i by 1` before `i++`
   - Bad: `// returns 200 OK` above a route handler
   - Good: `// AGMARKNET returns 404 for unknown commodities; treat as empty, not error`
2. **No dead code.** Remove unused functions, variables, imports, and files immediately.
3. **Consistent patterns.** If a pattern exists in the codebase, follow it. Do not introduce a second way to do the same thing without updating all existing usages.
4. **No magic numbers.** Extract to named constants.
5. **Error handling is not optional.** Every error must be handled or explicitly propagated.
6. **No `TODO` comments in committed code.** Use GitHub Issues instead.
7. **Research before every fix.** Understand root cause fully before touching code. Do not guess.

---

### Go Code Style

Follow the [Effective Go](https://go.dev/doc/effective_go) guide and the
[Google Go Style Guide](https://google.github.io/styleguide/go/). Key rules:

#### Naming

```go
// Package names: lowercase, no underscores, no mixedCaps
package middleware

// Variables/functions: camelCase
userID, refreshToken, parseRequest()

// Exported: PascalCase
type HMACMiddleware struct{}
func NewHMACMiddleware(secret string) *HMACMiddleware

// Constants: PascalCase for exported, camelCase for unexported
const MaxRetries = 3
const defaultTimeout = 5 * time.Second

// Acronyms uppercase: ID, URL, HTTP, JSON (not Id, Url, Http, Json)
func getUserByID(id string)
```

#### Error Handling

```go
// Always wrap errors with context
if err := db.QueryRow(ctx, query, id).Scan(&user); err != nil {
    return nil, fmt.Errorf("getUserByID %s: %w", id, err)
}

// Use sentinel errors for known conditions
var ErrNotFound = errors.New("not found")
var ErrUnauthorized = errors.New("unauthorized")

// Never swallow errors
_ = someFunc() // NEVER do this unless you have documented justification
```

#### Structs and Interfaces

```go
// Define interfaces where they are used, not where they are implemented
type UserRepository interface {
    FindByEmail(ctx context.Context, email string) (*User, error)
    Create(ctx context.Context, user *User) error
}

// Zero-value usability: structs should be usable in their zero state where possible
// Struct field alignment: group same-size fields to minimise padding
```

#### HTTP Handlers (Gin)

```go
// Use named handler functions, never anonymous funcs in route registration
r.POST("/auth/register", h.Register)

// Handler signature always
func (h *Handler) Register(c *gin.Context) {
    var req RegisterRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        response.Error(c, http.StatusBadRequest, "validation_error", err.Error())
        return
    }
    // ...
}

// Always use early return on error — no nested if-else chains
```

#### Import Ordering

```go
import (
    // 1. Standard library
    "context"
    "fmt"
    "net/http"

    // 2. External packages
    "github.com/gin-gonic/gin"
    "github.com/rs/zerolog/log"

    // 3. Internal packages
    "github.com/khetibadi/go-shared/middleware"
    "github.com/khetibadi/auth/internal/domain"
)
```

Use `goimports` (enforced by `golangci-lint`) to keep this sorted automatically.

#### Logging

```go
// Use zerolog. Never use fmt.Println, log.Println, or fmt.Printf for logging.
log.Info().
    Str("user_id", userID).
    Str("action", "login").
    Msg("user logged in")

log.Error().
    Err(err).
    Str("user_id", userID).
    Msg("failed to create refresh token")

// Context-aware logging
logger := zerolog.Ctx(ctx)
logger.Info().Str("farm_id", farmID).Msg("farm created")
```

#### Context

```go
// Always pass context.Context as the first parameter
func (r *userRepo) FindByEmail(ctx context.Context, email string) (*User, error)

// Set deadlines for all external calls
ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
defer cancel()
```

---

### Python Code Style

Follow [PEP 8](https://peps.python.org/pep-0008/). Enforced by `ruff` + `mypy` (strict).

#### Naming

```python
# Variables/functions: snake_case
user_id, refresh_token, parse_request()

# Classes: PascalCase
class CropRecommendationRequest(BaseModel): ...

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
MODEL_PATH = "models/crop_model.pkl"

# Private helpers: leading underscore
def _load_model(path: str) -> Pipeline: ...
```

#### Type Annotations (Required Everywhere)

```python
# All function signatures must have full type annotations
def predict_crop(features: CropFeatures) -> CropPrediction:
    ...

# Use Pydantic v2 for all request/response models
class CropFeatures(BaseModel):
    nitrogen: float = Field(ge=0, le=140)
    phosphorus: float = Field(ge=5, le=145)
    # ...
```

#### FastAPI Patterns

```python
# Lifespan for startup/shutdown (not @app.on_event — deprecated)
@asynccontextmanager
async def lifespan(app: FastAPI):
    models.load()
    yield
    models.unload()

app = FastAPI(lifespan=lifespan)

# Dependency injection for auth and DB
@router.post("/ml/crop/recommend")
async def recommend(
    req: CropFeatures,
    user: AuthUser = Depends(hmac_auth),
) -> CropPrediction:
    ...
```

#### Error Handling

```python
# Use HTTPException with detail dict, not strings
raise HTTPException(
    status_code=422,
    detail={"error": "validation_error", "field": "nitrogen", "message": "must be ≤ 140"}
)

# Never catch bare Exception without re-raising or logging
try:
    result = model.predict(X)
except Exception as e:
    logger.error("model inference failed", exc_info=True, extra={"error": str(e)})
    raise HTTPException(status_code=500, detail={"error": "inference_failed"})
```

#### Logging

```python
# Use structlog or Python logging with JSON formatter. Never print().
import logging
logger = logging.getLogger(__name__)

logger.info("crop predicted", extra={"crop": prediction.crop, "confidence": prediction.confidence})
```

#### Import Ordering (enforced by ruff)

```python
# 1. Standard library
import json
from pathlib import Path

# 2. Third-party
import numpy as np
import torch
from fastapi import FastAPI

# 3. Internal
from app.models import CropFeatures
from app.services import crop_service
```

---

### TypeScript / React Code Style

Follow the [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html).
Enforced by `ESLint 9` + `Prettier 3.8`.

#### Strict Mode

All TypeScript code MUST use `strict: true`. No `any` types. No `@ts-ignore`.

```typescript
// tsconfig.json: "strict": true, "noUncheckedIndexedAccess": true
```

#### Naming

```typescript
// Variables/functions: camelCase
const userId = '...';
function parseRequest() {}

// React components: PascalCase
function FarmMapPage() {}
export default FarmMapPage;

// Types/Interfaces: PascalCase with I-prefix ONLY for interfaces (prefer type aliases)
type FarmBoundary = { ... };
type CropRecommendation = { ... };

// Constants: UPPER_SNAKE_CASE for true constants, camelCase for config objects
const MAX_RETRIES = 3;
const queryConfig = { staleTime: 5 * 60 * 1000 };

// File names: kebab-case for files, PascalCase for React component files
// farm-map-page.tsx, use-farm-data.ts, FarmCard.tsx
```

#### React Patterns

```typescript
// Context-Hook pattern (from FlosBridge reference)
// 1. Create context
const FarmContext = createContext<FarmContextValue | null>(null);

// 2. Provider component
export function FarmProvider({ children }: PropsWithChildren) {
  const farms = useFarmsQuery();
  return <FarmContext.Provider value={{ farms }}>{children}</FarmContext.Provider>;
}

// 3. Hook
export function useFarm() {
  const ctx = useContext(FarmContext);
  if (!ctx) throw new Error('useFarm must be used within FarmProvider');
  return ctx;
}

// 4. Component consumes hook
function FarmList() {
  const { farms } = useFarm();
  // ...
}
```

```typescript
// TanStack Query: always use queryKey factories
const farmKeys = {
  all: ['farms'] as const,
  list: () => [...farmKeys.all, 'list'] as const,
  detail: (id: string) => [...farmKeys.all, 'detail', id] as const,
};

// Mutations: always invalidate related queries on success
const createFarm = useMutation({
  mutationFn: farmApi.create,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: farmKeys.all }),
  onError: (err) => toast.error(getErrorMessage(err)),
});
```

```typescript
// Forms: TanStack Form + Zod (Standard Schema — no adapter/resolver needed)
import { useForm } from '@tanstack/react-form';

const farmSchema = z.object({
  name: z.string().min(1, 'Farm name is required').max(100),
  soilType: z.enum(['clay', 'sandy', 'loamy', 'silty', 'peaty']),
});

function CreateFarmForm() {
  const form = useForm({
    defaultValues: { name: '', soilType: 'loamy' as const },
    validators: { onChange: farmSchema },
    onSubmit: async ({ value }) => { await createFarm(value); },
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit(); }}>
      <form.Field
        name="name"
        children={(field) => (
          <Input
            value={field.state.value}
            onChange={(e) => field.handleChange(e.target.value)}
            aria-invalid={field.state.meta.errors.length > 0}
          />
        )}
      />
      <form.Subscribe
        selector={(s) => s.errors}
        children={(errors) => errors.length > 0 && <p>{errors[0]}</p>}
      />
    </form>
  );
}
```

```typescript
// Client state: @tanstack/react-store (memory only — never localStorage for tokens)
import { Store } from '@tanstack/react-store';
import { useStore } from '@tanstack/react-store';

// Define once at module level
export const authStore = new Store({
  user: null as User | null,
  token: null as string | null,
});

// Read in components (re-renders only when selected slice changes)
const token = useStore(authStore, (s) => s.token);

// Update (actions defined alongside the store)
export function setAuth(user: User, token: string) {
  authStore.setState(() => ({ user, token }));
}
export function clearAuth() {
  authStore.setState(() => ({ user: null, token: null }));
}
```

```typescript
// Virtualization: @tanstack/react-virtual (long lists — market prices, farm list)
import { useVirtualizer } from '@tanstack/react-virtual';

function PriceList({ items }: { items: MarketPrice[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 56,
    overscan: 5,
  });
  return (
    <div ref={parentRef} className="h-[600px] overflow-auto">
      <div style={{ height: virtualizer.getTotalSize() }} className="relative w-full">
        {virtualizer.getVirtualItems().map((vi) => (
          <div
            key={vi.key}
            style={{ transform: `translateY(${vi.start}px)` }}
            className="absolute w-full"
          >
            <PriceRow price={items[vi.index]!} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

```typescript
// Debounced async: @tanstack/react-pacer (search inputs, API calls)
import { useDebouncer } from '@tanstack/react-pacer';

function CommoditySearch() {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebouncer(query, { wait: 300 });
  const { data } = useQuery(commoditySearchOptions(debouncedQuery));
  // ...
}
```

#### Import Ordering (enforced by ESLint import/order)

```typescript
// 1. React + core
import React, { useState, useRef } from 'react';

// 2. Third-party libraries
import { useQuery } from '@tanstack/react-query';
import { useVirtualizer } from '@tanstack/react-virtual';
import { MapContainer } from 'react-leaflet';

// 3. Internal packages
import { Button, Card } from '@khetibadi/ui';

// 4. Feature-local imports
import { useFarm } from '../context/FarmContext';
import { farmApi } from '../api/farm';

// 5. Types
import type { Farm } from '@khetibadi/types';
```

#### No Inline Styles

```typescript
// Never use style={{ }} — use Tailwind classes instead
// Bad
<div style={{ color: 'red', marginTop: '8px' }}>

// Good
<div className="text-red-500 mt-2">
```

---

## Linting Configuration

### Go — `.golangci.yml` (place in each Go service root)

```yaml
run:
  timeout: 5m
  tests: true

linters:
  enable:
    - errcheck
    - govet
    - staticcheck
    - gosimple
    - ineffassign
    - unused
    - revive
    - goimports
    - gofumpt
    - misspell
    - bodyclose
    - contextcheck
    - noctx
    - nolintlint
    - errorlint
    - prealloc
    - gocritic
    - gosec
    - nakedret

linters-settings:
  gocritic:
    enabled-tags: [diagnostic, performance, style]
  errcheck:
    check-type-assertions: true
    check-blank: true
  nakedret:
    max-func-lines: 1
  goimports:
    local-prefixes: github.com/khetibadi
```

### Python — `pyproject.toml` (in each Python service)

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "W", "F", "I", "N", "UP", "B", "C4", "SIM", "RET", "ANN"]
ignore = ["ANN101", "ANN102"]

[tool.ruff.isort]
known-first-party = ["app"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = false
```

### TypeScript — `eslint.config.js` (root, via `packages/eslint-config`)

```javascript
// Key rules enforced:
// - @typescript-eslint/no-explicit-any: error
// - @typescript-eslint/no-unused-vars: error
// - import/order: error (with group separation)
// - react-hooks/exhaustive-deps: warn
// - no-console: warn (use logger instead)
// - react/self-closing-comp: error
```

---

## Docker Build Guidelines

### Philosophy: Small, Fast, Reproducible

All Dockerfiles MUST follow these rules:
1. **Multi-stage builds** — separate `builder` and `runtime` stages
2. **Layer cache optimisation** — copy dependency files first, source last
3. **No debug tools in production image** — no `bash`, `curl`, `vim`
4. **Non-root user** — all services run as `nonroot` (UID 65532)
5. **.dockerignore required** — every service must have one

### Go Service Dockerfile Template

```dockerfile
# Stage 1: Build
FROM golang:1.26-alpine AS builder

WORKDIR /build

# Cache dependency layer separately
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -trimpath \
    -o /app ./cmd/server

# Stage 2: Runtime (distroless — no shell, no package manager)
FROM gcr.io/distroless/static-debian12:nonroot

COPY --from=builder /app /app

USER nonroot:nonroot
EXPOSE 8000
ENTRYPOINT ["/app"]
```

**Target image size:** < 20MB

Key flags:
- `CGO_ENABLED=0` — static binary, no C dependencies
- `-ldflags="-s -w"` — strip debug symbols and DWARF
- `-trimpath` — remove local build paths from binary
- `distroless/static-debian12:nonroot` — no shell, ~2MB base

### Python Service Dockerfile Template

```dockerfile
# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Non-root user
RUN useradd --uid 1001 --no-create-home appuser

# Copy only installed packages, not the build tooling
COPY --from=builder /build/.venv /app/.venv
COPY app/ ./app/
COPY models/ ./models/

USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

**Target image size:** ~400MB (ml-crop), ~2GB (ml-vision with PyTorch)

Key optimisations:
- `--no-dev` excludes test/dev dependencies from runtime image
- `--frozen` ensures reproducible builds from `uv.lock`
- Copy `.venv` not source — avoids re-installing on code changes
- Use `--no-cache-dir` in any direct pip calls

### Frontend Dockerfile Template

```dockerfile
# Stage 1: Build
FROM oven/bun:1.3-alpine AS builder

WORKDIR /build

# Cache deps
COPY package.json bun.lockb ./
COPY packages/ui/package.json packages/ui/
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

# Stage 2: Nginx static server
FROM nginx:1.27-alpine

COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000
```

**Target image size:** < 50MB

### .dockerignore Template (per service)

```
.git
**/*.md
**/tests/
**/scripts/
**/__pycache__/
**/*.pyc
**/.pytest_cache/
**/node_modules/
**/.env*
**/Makefile
```

---

## Git Commit Conventions

This project uses [Conventional Commits 1.0.0](https://www.conventionalcommits.org/).

### Format

```
<type>(<scope>): <short description>

[optional body — explain WHY, not WHAT]

[optional footer — breaking changes, issue refs]
```

### Rules

- **Subject line:** max 72 characters, lowercase, no trailing period, imperative mood
  - Good: `feat(auth): add refresh token rotation`
  - Bad: `Added refresh token rotation.`
- **Body:** wrap at 100 characters, explain motivation and what changed
- **Scope:** matches service/package name (`auth`, `farm`, `market`, `workers`, `ml-crop`, `ml-vision`, `ai-chat`, `dashboard`, `go-shared`, `ui`, `db`, `docker`, `ci`, `specs`)
- **One logical change per commit.** If you find yourself writing "and" in the subject, split the commit.

### Allowed Types

| Type | When to use |
|------|-------------|
| `feat` | New feature or endpoint |
| `fix` | Bug fix |
| `refactor` | Code restructure without behaviour change |
| `perf` | Performance improvement |
| `test` | Adding or fixing tests |
| `docs` | Documentation (specs, README, AGENTS.md) |
| `style` | Formatting changes only (no logic) |
| `chore` | Build, config, tooling, deps |
| `ci` | CI/CD workflow changes |
| `build` | Docker, Makefile, build system |
| `revert` | Revert a prior commit |

### Examples

```
feat(auth): add JWT access token issuance on login

Issues signed JWT (sub, email, iat, exp) using RS256 with 15-minute
expiry. Access token returned in response body; refresh token set
as HttpOnly cookie with SameSite=Strict.
```

```
fix(farm): return 404 on ownership mismatch instead of 500

ST_Intersects query was panicking on nil geometry when the farm_id
belonged to a different user. Added ownership check before spatial
query to fail fast with 404.
```

```
perf(market): add Redis 6h cache for commodity price lookups

Before: every request hit PostgreSQL (~30ms).
After: cache hit rate ~95% after warm-up (~2ms).
Cache key: market:price:<commodity>:<market>
```

```
chore(docker): switch Go runtime to distroless/static-debian12

Reduces auth service image from 18MB to 8MB. distroless has no shell
or package manager, improving security posture.
```

```
docs(specs): update ml-vision spec with rembg background removal

Adds Requirement: Background Removal Pre-Processing based on MDPI 2021
research showing +3-5% accuracy improvement on in-field images.
```

### Breaking Changes

```
feat(auth)!: change access token format to include role claim

BREAKING CHANGE: all downstream services must update their HMAC
middleware to validate the new `role` field in the token payload.
Farm-service and market-service updated in this commit.
```

### Commit Granularity Target

This project targets **≥ 250 commits** to reflect how a professional team actually
ships code — not one giant dump at the end, but a living history of incremental,
reviewable progress.

#### The Core Rule: Commit As You Go

> **Never accumulate.** The moment a logical unit of work is complete and the code
> compiles / lints clean, commit it. Do not wait until a feature is "fully done".

A real developer commits **multiple times per hour** during active work. An AI agent
must do the same — commit after every meaningful change, not once at the end of a
task. If you finish a session with more than 5 uncommitted files, something is wrong.

#### What Triggers a Commit (commit immediately after each)

**Go services:**
- Domain type defined (`internal/domain/user.go` created)
- Repository interface defined
- SQL query added to `db/queries/*.sql`
- `sqlc generate` run and output committed
- Single repository method implemented (`FindByEmail`)
- Single service method implemented (`CreateUser`)
- Single handler implemented (`POST /auth/register`)
- Handler test written and passing
- Service test written and passing
- Middleware added or updated
- Migration file created
- Error type or sentinel defined
- `.golangci.yml` rule added or updated

**Python services:**
- Pydantic schema added (`app/schemas/crop.py`)
- Single route function implemented
- Service function implemented
- HMAC middleware adapted
- Test written and passing
- `pyproject.toml` dependency added

**TypeScript / React:**
- Route file created (`src/routes/dashboard/farm-map.tsx`)
- Feature context + hook created
- Single API hook written (`useFarmsQuery`)
- Single component implemented (`FarmCard.tsx`)
- Component tests written
- Query key factory defined
- Store slice defined (`auth-store.ts`)
- `vite.config.ts` configured
- `tsconfig.json` updated

**Config / infra:**
- Single `Dockerfile` written
- `docker-compose.yml` service added
- `.env.example` entry added
- `Makefile` target added
- Migration file added

#### The Rhythm (example: implementing a Go handler)

```
feat(auth): add User domain type and repository interface

feat(auth): add sqlc queries for user create and find-by-email

chore(auth): run sqlc generate — add generated db layer

feat(auth): implement UserRepo.Create and FindByEmail

test(auth): add table-driven tests for UserRepo

feat(auth): implement AuthService.Register with bcrypt

test(auth): add AuthService.Register tests — duplicate email case

feat(auth): add POST /auth/register handler

test(auth): add handler integration test for register endpoint
```

That is **9 commits** for one endpoint. That is correct. That is professional.

#### How to Stage (never `git add .`)

Always stage specific files or directories:

```bash
# Good — intentional
git add apps/auth/internal/domain/user.go
git commit -m "feat(auth): add User domain type"

# Good — related files together
git add apps/auth/internal/repository/user_repo.go \
        apps/auth/internal/repository/user_repo_test.go
git commit -m "feat(auth): implement UserRepo with FindByEmail and Create"

# Bad — accumulating everything
git add .
git commit -m "add auth stuff"   # ← NEVER do this
```

#### What a 250+ Commit History Looks Like

By the time the project is feature-complete, the log should read like a timeline:

```
chore(go-shared): add HMAC middleware skeleton
feat(go-shared): implement HMAC-SHA256 signature verification
test(go-shared): add HMAC middleware replay window test
feat(auth): add User and RefreshToken domain types
feat(auth): add sqlc queries — create_user, find_by_email, upsert_token
chore(auth): run sqlc generate
feat(auth): implement UserRepo
feat(auth): implement AuthService.Register with bcrypt cost 12
test(auth): add Register duplicate email returns 409
feat(auth): add POST /auth/register handler
test(auth): add register handler integration test
feat(auth): implement AuthService.Login with JWT issuance
test(auth): add Login invalid password returns 401
feat(auth): add POST /auth/login handler
feat(auth): add refresh token rotation — POST /auth/refresh
feat(auth): add logout — DELETE /auth/logout clears cookie
feat(farm): scaffold farm domain types and GeoJSON helpers
...
```

Each commit is small, named, and self-contained. `git bisect` works. Code review
works. Rollback works. **This is the standard.**

#### Anti-Patterns (NEVER do these)

| Anti-pattern | Why it's wrong |
|---|---|
| `git add . && git commit -m "wip"` | Untraceable, unrollbackable, unprofessional |
| Committing at end of a session only | Loses granularity, hides the development process |
| `fix: misc fixes` | Meaningless — what was fixed? |
| One commit per file arbitrarily | Commit by **logical unit**, not by file count |
| Committing broken/unlinted code | Every commit must build and lint clean |
| `feat: add everything` | Split into individual features |

**Never batch multiple features into one commit.**

---

## Branch Naming

```
main/feature work  →  laughingman (default branch)
feature branches   →  feat/<scope>/<short-description>
bug fixes          →  fix/<scope>/<short-description>
chore/infra        →  chore/<description>

Examples:
  feat/auth/refresh-token-rotation
  fix/farm/ownership-check-null-geometry
  chore/docker/distroless-migration
```

---

## Security Conventions

1. **No secrets in source code.** Use `.env` files (gitignored) and Docker Compose env sections.
2. **All `.env` files are gitignored.** Only `.env.example` is committed.
3. **HMAC secret minimum 32 bytes.** Generate with `openssl rand -hex 32`.
4. **JWT signing key minimum 256 bits.** Generate with `openssl rand -hex 32`.
5. **Passwords are always bcrypt** (cost factor 12). Never MD5, SHA1, plain text.
6. **Rate limiting on all auth endpoints.** No exceptions.
7. **SQL queries via sqlc (Go) or parameterised queries (Python).** Never string interpolation.
8. **File upload validation:** check MIME type by content (magic bytes), not filename extension.

---

## ML Model Conventions

1. **Models are NOT committed to git.** Add `*.pkl`, `*.pth`, `*.onnx` to `.gitignore`.
2. **All training scripts are reproducible.** `random_state=42` and `torch.manual_seed(42)` always set.
3. **Model artifacts include metadata.** Each saved model must embed: trained_at, val_accuracy/r2, features list, class mapping (where applicable).
4. **Research before changing inference pipelines.** Any change to the OpenCV pipeline or ResNet34 transforms must be validated against the PlantVillage validation set first.
5. **Background removal is the first step** in ml-vision inference. rembg must run before OpenCV processing. If rembg fails, log WARN and continue without removal.
6. **Batch inference ≤ 50 records.** Reject larger batches with 413.
7. **Confidence threshold 0.60.** Below this, return `uncertain` in ml-vision.

---

## API Design Conventions

### Response Envelope

All APIs return a consistent JSON envelope:

```json
// Success
{ "success": true, "data": { ... } }

// Success with pagination
{ "success": true, "data": [...], "pagination": { "total": 100, "page": 1, "page_size": 20, "pages": 5 } }

// Error
{ "success": false, "error": { "code": "email_taken", "message": "A user with that email already exists" } }
```

### HTTP Status Codes

| Situation | Code |
|---|---|
| Successful read | 200 |
| Successful create | 201 |
| Accepted (async job) | 202 |
| No content (delete) | 204 |
| Bad request / validation | 400 |
| Unauthorised (no/bad token) | 401 |
| Forbidden (authenticated, wrong resource) | 403 |
| Not found | 404 |
| Conflict (duplicate) | 409 |
| Unprocessable entity | 422 |
| Too many requests | 429 |
| Service unavailable | 503 |

### Versioning

All API paths are un-versioned for v2 (single consumer). A `/v2/` prefix will be added
when a breaking change requires parallel support.

---

## Testing Conventions

1. **Test files sit beside source files**, not in a separate top-level `tests/` directory.
   - Go: `handler_test.go` beside `handler.go`
   - Python: `tests/test_recommend.py` beside `app/routes/recommend.py`
2. **No integration tests without a running dependency** (Postgres, Redis). Use `testcontainers` or Docker Compose for integration tests in CI.
3. **Table-driven tests** for Go. Parameterised tests (`@pytest.mark.parametrize`) for Python.
4. **Test names describe behaviour, not implementation:**
   - Good: `TestRegister_DuplicateEmail_Returns409`
   - Bad: `TestInsertUser`
5. **Coverage target: ≥ 80% on business logic.** HTTP handlers + domain services.
6. **ML model tests do not load models.** Mock the model loader and test the pipeline logic separately.

---

## Forbidden Patterns

The following are prohibited in this codebase:

| Pattern | Why | Correct Alternative |
|---|---|---|
| `fmt.Println` / `print()` in services | Not structured, not JSON | `zerolog` / `logging.getLogger` |
| `os.Exit` in library code | Prevents cleanup/defer | Return error to caller |
| Hardcoded IP addresses | Breaks in containers | Use service names from env |
| `time.Sleep` in production code | Masks real problems | Use proper retry logic |
| `SELECT *` in SQL | Fragile to schema changes | Explicit column list via sqlc |
| `interface{}` / `any` without type assertion | Loses type safety | Define concrete types |
| `//nolint` without comment explaining why | Hides issues silently | Fix the issue or document |
| Returning HTTP 200 for errors | Breaks client error handling | Use correct status codes |
| Comments that restate the code | Noise | Delete them |

---

## File Structure Conventions

### Go Service Layout

```
apps/auth/
├── cmd/
│   └── server/
│       └── main.go          # entry point only — wires deps and starts server
├── internal/
│   ├── domain/              # types, interfaces (no framework imports)
│   │   ├── user.go
│   │   └── token.go
│   ├── handler/             # HTTP handlers (Gin)
│   │   ├── auth_handler.go
│   │   └── auth_handler_test.go
│   ├── service/             # business logic
│   │   ├── auth_service.go
│   │   └── auth_service_test.go
│   └── repository/          # data access (sqlc generated + wrappers)
│       ├── user_repo.go
│       └── user_repo_test.go
├── .golangci.yml
├── Dockerfile
├── go.mod
└── go.sum
```

### Python Service Layout

```
apps/ml-crop/
├── app/
│   ├── main.py              # FastAPI app + lifespan
│   ├── routes/
│   │   ├── recommend.py
│   │   ├── yield_pred.py
│   │   └── fertilizer.py
│   ├── services/
│   │   └── inference.py     # model loading + prediction logic
│   ├── schemas/             # Pydantic v2 models
│   │   └── crop.py
│   └── middleware/
│       └── hmac_auth.py
├── models/                  # .pkl files (gitignored)
├── scripts/
│   ├── train_crop.py
│   └── train_yield.py
├── tests/
│   └── test_recommend.py
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

### React Feature Layout

```
apps/dashboard/src/features/farm-map/
├── index.ts                 # public exports only
├── FarmMapPage.tsx          # route-level component (thin, imports Provider)
├── FarmMapProvider.tsx      # context provider
├── useFarmMap.ts            # context hook
├── components/
│   ├── FarmPolygon.tsx
│   ├── SoilSampleMarker.tsx
│   └── FarmDetailsPanel.tsx
├── api/
│   └── farm-api.ts          # TanStack Query hooks
└── types.ts                 # feature-local types
```

---

## Environment Variables Reference

All services read from environment variables. Never from config files in source control.

```bash
# Shared
DATABASE_URL=postgres://khetibadi:secret@localhost:5432/khetibadi
REDIS_URL=redis://localhost:6379
HMAC_SECRET=<32-byte hex>

# Auth
JWT_SECRET=<32-byte hex>
JWT_ACCESS_EXPIRY=15m
JWT_REFRESH_EXPIRY=168h

# Farm
OPENWEATHERMAP_API_KEY=<key>
WEATHER_CACHE_TTL=10800   # 3 hours in seconds

# Market
AGMARKNET_API_URL=https://agmarknet.gov.in/...
PRICE_CACHE_TTL=21600     # 6 hours

# AI Chat
GROQ_API_KEY=<key>
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MAX_TOKENS=2048

# Workers
ML_CROP_URL=http://ml-crop:8010
ML_VISION_URL=http://ml-vision:8011
AI_CHAT_URL=http://ai-chat:8012
FARM_SERVICE_URL=http://farm-service:8001
MARKET_SERVICE_URL=http://market-service:8002
CHAT_RETENTION_DAYS=90

# Dashboard (prefix VITE_ for client exposure)
VITE_API_BASE_URL=http://localhost:8000
```

---

## Working with This Codebase (For AI Agents)

### Before Making Any Change

1. Read the relevant `openspec/specs/<domain>/spec.md` to understand intended behaviour.
2. Run `git log --oneline -20` to understand recent changes in the area you are touching.
3. Run the relevant linter (`golangci-lint run` / `ruff check` / `bun run lint`) to confirm baseline is clean.
4. **Search for the current library docs** — do not assume your training data is current.
5. Understand the existing pattern in the service before introducing a new one.

### Research Before You Write

Every non-trivial implementation requires at least one of:

```
firecrawl_search       — verify versions, changelogs, deprecation notices, CVEs
context7_query-docs    — read current official API docs and usage examples
github_grep_searchGitHub — find real production patterns in top repos
```

**Sequence:**
1. `context7_resolve-library-id` → `context7_query-docs` for any library API you're using
2. `firecrawl_search` or `webfetch` for version verification, changelogs, migration guides
3. `github_grep_searchGitHub` for real-world usage patterns when the docs example feels toy-like

Never write code against an API without verifying it against the current official docs.
Never copy a pattern from your training data without confirming it hasn't been deprecated.

### Sequential Thinking Protocol

Use `sequential-thinking` for any task that is:
- Non-trivial (more than 2 logical steps)
- Involves a tradeoff between approaches
- Touches security, performance, or data integrity
- Requires understanding an unfamiliar codebase area
- Has a risk of introducing subtle bugs

A senior engineer does not "just write the code". They reason first:
- What is the exact problem?
- What are the constraints?
- What are the 2-3 viable approaches?
- What are the failure modes of each?
- Which is simplest while satisfying all constraints?
- What could go wrong in production?

Then they write the code.

### After Making Any Change

1. Run the relevant linter — fix **all** issues before committing. Zero warnings is the standard.
2. Run the test suite for the changed service — fix all failures before committing.
3. Commit with a conventional commit message. **One logical change per commit.**
4. If a spec behaviour changes, update `openspec/specs/<domain>/spec.md` in the same commit.
5. If a dependency was bumped, verify the changelog for breaking changes first.

### Legacy & Outdated Code

When you encounter stale, deprecated, or outdated code **anywhere** in a file you open:

- **Deprecated API:** fix it immediately if the change is isolated; otherwise create a
  follow-up commit named `fix(<scope>): migrate <X> from deprecated <A> to <B>`.
- **Outdated pattern:** document why the new pattern is better in the commit body.
- **Stale comment / TODO:** either resolve it or delete it — no TODO comments in committed code.
- **Pinned version that is now significantly behind:** bump it, read the migration guide, update.

The bar is: when you leave a file, it should be in at least as modern a state as when
you found it. Ideally better.

### When Stuck

1. Search the web first — `firecrawl_search` the exact error message or behaviour.
2. Check `openspec/specs/` for the expected behaviour.
3. Check `openspec/changes/v2-initial-build/design.md` for architecture decisions.
4. Check the existing pattern in neighbouring services.
5. Query Context7 for the library's current recommended approach.
6. Search GitHub for how production codebases handle the same problem.
7. **Do NOT guess.** If the answer requires a fact you cannot verify, say so and search for it.

### Things You Must NOT Do

- Do not write code against an API without checking the current official docs.
- Do not change the JWT structure without updating all downstream HMAC validators.
- Do not add a new dependency without updating `go.mod` / `pyproject.toml` and the relevant `Dockerfile`.
- Do not change the PostgreSQL schema without adding a migration file.
- Do not change the OpenCV preprocessing pipeline without running the ResNet34 validation suite first.
- Do not commit `.env` files, `*.pkl` files, or `*.pth` files.
- Do not use `fmt.Println`, `print()`, or bare `console.log()` for logging.
- Do not introduce a new architectural pattern without a commit body explaining why.
- Do not leave a `// nolint`, `# type: ignore`, or `// @ts-ignore` without a comment explaining the root cause.
- Do not over-engineer. The simplest correct solution is the right solution.
- Do not under-engineer. If you copy-paste logic twice, extract it.
- Do not read entire files to find one function — grep for the line number first, then
  read only the relevant window. Full-file reads flood the context window, trigger
  compression, and cause earlier critical context to be forgotten.
