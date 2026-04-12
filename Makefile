.PHONY: help dev build test lint type-check clean \
        go-test go-lint go-build \
        py-test py-lint \
        fe-build fe-lint fe-type-check \
        docker-up docker-down docker-build \
        db-migrate sqlc-gen

# ─── Default ──────────────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ─── Top-level ────────────────────────────────────────────────────────────────
dev: ## Start all services via docker-compose
	docker compose up

build: go-build fe-build ## Build all services

test: go-test py-test ## Run all tests

lint: go-lint py-lint fe-lint ## Lint all services

type-check: fe-type-check ## TypeScript type-check

clean: ## Remove build artifacts
	find . -name 'bin' -type d -not -path './.git/*' | xargs rm -rf
	bun run clean

# ─── Go ───────────────────────────────────────────────────────────────────────
go-test: ## Run Go tests (all services)
	go test ./apps/auth/... ./apps/farm-service/... ./apps/market-service/... \
	         ./apps/workers/... ./packages/go-shared/... \
	         -race -count=1 -timeout=120s

go-lint: ## Run golangci-lint (all Go services)
	golangci-lint run ./apps/auth/... ./apps/farm-service/... \
	                   ./apps/market-service/... ./apps/workers/... \
	                   ./packages/go-shared/...

go-build: ## Build all Go service binaries
	go build -o apps/auth/bin/server ./apps/auth/cmd/server
	go build -o apps/farm-service/bin/server ./apps/farm-service/cmd/server
	go build -o apps/market-service/bin/server ./apps/market-service/cmd/server
	go build -o apps/workers/bin/worker ./apps/workers/cmd/worker

sqlc-gen: ## Regenerate sqlc for all Go services
	sqlc generate --file apps/farm-service/sqlc.yaml
	sqlc generate --file apps/market-service/sqlc.yaml

# ─── Python ───────────────────────────────────────────────────────────────────
py-test: ## Run Python tests (all services)
	cd apps/ml-crop   && uv run pytest tests/ -v
	cd apps/ml-vision && uv run pytest tests/ -v
	cd apps/ai-chat   && uv run pytest tests/ -v

py-lint: ## Ruff + mypy (all Python services)
	cd apps/ml-crop   && uv run ruff check . && uv run mypy .
	cd apps/ml-vision && uv run ruff check . && uv run mypy .
	cd apps/ai-chat   && uv run ruff check . && uv run mypy .

# ─── Frontend ─────────────────────────────────────────────────────────────────
fe-build: ## Build dashboard + packages
	bun run build

fe-lint: ## ESLint (dashboard + packages)
	bun run lint

fe-type-check: ## TypeScript type-check (dashboard + packages)
	bun run type-check

# ─── Docker ───────────────────────────────────────────────────────────────────
docker-up: ## Start all containers (detached)
	docker compose up -d

docker-down: ## Stop all containers
	docker compose down

docker-build: ## Build all Docker images
	docker compose build

# ─── Database ─────────────────────────────────────────────────────────────────
db-migrate: ## Run all pending migrations (goose)
	@echo "Run goose migrations per service — see each service's db/migrations/"
