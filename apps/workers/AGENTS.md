# AGENTS.md — apps/workers

> Go service. Port 8080 (Asynqmon UI only). Asynq background jobs + cron scheduler.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Runs all background and scheduled jobs. Does NOT expose a public HTTP API — only
the Asynqmon monitoring UI on :8080. All job handlers communicate with other services
via their HTTP APIs (never directly to their databases).

## Layout

```
apps/workers/
├── cmd/worker/main.go          # register handlers, start Asynq server + Asynqmon
├── internal/
│   ├── handlers/               # one file per job type
│   │   ├── market_sync.go
│   │   ├── price_alerts.go
│   │   ├── weather_prefetch.go
│   │   ├── vision_detect.go
│   │   ├── knowledge_index.go
│   │   ├── notifications.go
│   │   ├── cleanup.go
│   │   └── ml_warmup.go
│   └── scheduler/              # cron job registration
│       └── scheduler.go
├── .golangci.yml
├── Dockerfile
├── go.mod                      # module: github.com/khetibadi/workers
└── go.sum
```

## Queue Priorities

| Queue | Priority | Jobs |
|-------|----------|------|
| `critical` | 6 | `notifications:send`, `market:check_price_alerts` |
| `default` | 3 | `market:sync_prices`, `farm:prefetch_weather`, `vision:detect_disease` |
| `low` | 1 | `ai:index_knowledge_chunk`, `cleanup:stale_data`, `ml:warmup_models` |

## Job Registry

| Job Key | Trigger | Cron |
|---------|---------|------|
| `market:sync_prices` | Cron | `0 */6 * * *` |
| `market:check_price_alerts` | After market sync | — |
| `farm:prefetch_weather` | Cron | `0 */3 * * *` |
| `vision:detect_disease` | ml-vision enqueue | — |
| `ai:index_knowledge_chunk` | ai-chat enqueue | — |
| `notifications:send` | Alert/vision jobs | — |
| `cleanup:stale_data` | Cron | `30 20 * * *` (UTC = 2AM IST) |
| `ml:warmup_models` | Startup once | — |

## Key Invariants

- **No direct DB access to other services.** Workers call service HTTP APIs only.
- **Idempotent handlers.** Every job handler must be safe to retry. Use upsert, not insert.
- **Alert cooldown:** skip `notifications:send` if `last_triggered_at` < 6h ago.
- **Weather rate limit:** 1 req/sec to OpenWeatherMap in `farm:prefetch_weather`.
- **Cleanup batching:** delete market_prices in batches of 10,000 rows to avoid lock contention.
- **Warmup on startup:** enqueue `ml:warmup_models` once in `main.go` after server starts.

## Critical Pitfalls

- **NEVER** call another service's PostgreSQL directly — use HTTP APIs.
- **NEVER** make `market:sync_prices` and `farm:prefetch_weather` run at the same minute
  (they both hit external APIs — stagger them).
- **NEVER** retry vision jobs on model errors (only on transient network errors).

## Dev Commands

```bash
cd apps/workers
go run ./cmd/worker
go test ./... -race -count=1
golangci-lint run ./...
# Asynqmon UI: http://localhost:8080
```

## Spec Reference

`openspec/specs/workers/spec.md`
