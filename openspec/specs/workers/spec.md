# Workers Service Specification

## Purpose

Provide background job processing and scheduled tasks for Khetibadi v2 using the
`hibiken/asynq` library (Redis-backed). All long-running, periodic, or non-critical
tasks are offloaded to workers to keep API services fast and responsive.
Asynqmon dashboard is exposed on port 8080 for monitoring.

---

## Queue Definitions

| Queue | Priority | Description |
|-------|----------|-------------|
| `critical` | 6 | Price alert notifications |
| `default` | 3 | Market sync, weather prefetch, report generation |
| `low` | 1 | Analytics, cleanup, model warmup |

---

## Requirements

### Requirement: Market Price Sync Job

The system MUST periodically fetch the latest commodity prices from the AGMARKNET API
and upsert them into the `market_prices` table.

#### Job: `market:sync_prices`

- **Schedule:** Every 6 hours (cron: `0 */6 * * *`)
- **Queue:** `default`
- **Retry policy:** 3 retries with exponential backoff (30s, 2min, 8min)
- **Timeout:** 5 minutes per run

#### Scenario: Successful Sync

- GIVEN the AGMARKNET API is reachable
- WHEN the `market:sync_prices` job runs
- THEN all commodity+market combinations are fetched from AGMARKNET
- AND rows are upserted into `market_prices` on conflict `(commodity, market_name, price_date)`
- AND Redis cache keys matching `market:price:*` are invalidated (DEL by pattern)
- AND the job completes with `{ "upserted": N, "skipped": M }` logged at INFO

#### Scenario: AGMARKNET API Failure

- GIVEN the AGMARKNET API returns 5xx or times out
- WHEN the job runs
- THEN the error is logged with the response status
- AND the job is retried according to retry policy
- AND after all retries exhausted, the job is marked failed (visible in Asynqmon)

#### Scenario: Partial Failure

- GIVEN some commodity fetches succeed and others fail
- WHEN the job runs
- THEN successful upserts are committed
- AND failed commodity syncs are logged individually
- AND the job is marked completed (partial success) with a warning log

---

### Requirement: Price Alert Detection Job

The system MUST check user-defined price alerts after every market sync and notify
users when their threshold conditions are met.

#### Job: `market:check_price_alerts`

- **Trigger:** Enqueued by `market:sync_prices` upon successful completion
- **Queue:** `critical`
- **Retry policy:** 3 retries with 10s backoff
- **Timeout:** 2 minutes

#### Scenario: Alert Threshold Breached

- GIVEN a user has an alert: commodity = "Wheat", market = "Delhi", threshold_price = 2000, condition = "above"
- AND the latest synced price for Wheat in Delhi is 2100
- WHEN `market:check_price_alerts` runs
- THEN a notification is queued via `notifications:send` job
- AND the alert's `last_triggered_at` is updated in `price_alerts` table

#### Scenario: Alert Already Triggered Recently

- GIVEN an alert was triggered less than 6 hours ago (cooldown period)
- WHEN `market:check_price_alerts` runs
- THEN the alert is skipped (no duplicate notification)

#### Scenario: No Alerts Breached

- GIVEN no user alert thresholds are exceeded by current prices
- WHEN `market:check_price_alerts` runs
- THEN the job completes with `{ "alerts_checked": N, "triggered": 0 }` logged at INFO

---

### Requirement: Weather Data Prefetch Job

The system MUST proactively prefetch weather data for all farms into Redis cache
so that API requests are fast (cache hit guaranteed during normal operation).

#### Job: `farm:prefetch_weather`

- **Schedule:** Every 3 hours (cron: `0 */3 * * *`)
- **Queue:** `default`
- **Retry policy:** 2 retries with 60s backoff
- **Timeout:** 10 minutes

#### Scenario: Successful Prefetch

- GIVEN there are N active farms in the database
- WHEN `farm:prefetch_weather` runs
- THEN the centroid (ST_Centroid) is computed for each farm
- AND OpenWeatherMap current weather API is called for each centroid (rate-limited to 1 req/sec)
- AND results are written to Redis as `weather:farm:<farm_id>` with TTL = 3 hours
- AND `{ "farms_prefetched": N, "failed": M }` is logged at INFO

#### Scenario: OpenWeatherMap Rate Limit

- GIVEN too many farm weather requests are sent quickly
- WHEN the API returns HTTP 429
- THEN the job pauses for 60 seconds before retrying that batch
- AND does not fail the entire job

---

### Requirement: ML Disease Detection Async Processing

The system MUST support async plant disease detection for large images or batch requests
submitted by the ml-vision FastAPI service.

#### Job: `vision:detect_disease`

- **Trigger:** Enqueued by ml-vision service when async detection is requested
- **Queue:** `default`
- **Retry policy:** 1 retry (no retry on model error)
- **Timeout:** 30 seconds per image

#### Scenario: Async Job Enqueued

- GIVEN a user submits a plant image for disease detection via POST /ml/vision/detect?async=true
- WHEN ml-vision enqueues `vision:detect_disease` with `{ "job_id": "<uuid>", "image_path": "<s3_or_local_path>", "user_id": "<uuid>" }`
- THEN the workers service picks up the job
- AND runs the ResNet34 inference pipeline (OpenCV preprocessing + model inference)
- AND saves the result to Redis as `vision:result:<job_id>` with TTL = 1 hour
- AND enqueues `notifications:send` to notify the user

#### Scenario: Job Result Poll

- GIVEN a job_id from a previously enqueued detection
- WHEN GET /ml/vision/jobs/{job_id} is called on ml-vision service
- THEN ml-vision checks Redis for `vision:result:<job_id>`
- AND returns `{ "status": "completed", "result": {...} }` if found
- AND returns `{ "status": "pending" }` if not yet in Redis

---

### Requirement: Chat Knowledge Base Indexing Job

The system MUST asynchronously generate and store vector embeddings for new knowledge
chunks added to the agricultural knowledge base.

#### Job: `ai:index_knowledge_chunk`

- **Trigger:** Enqueued by ai-chat service when POST /ai/chat/knowledge is called
- **Queue:** `low`
- **Retry policy:** 3 retries with 30s backoff
- **Timeout:** 60 seconds

#### Scenario: Successful Chunk Indexing

- GIVEN a new knowledge chunk with content = "Wheat grows best in well-drained loamy soil..."
- WHEN `ai:index_knowledge_chunk` is enqueued with `{ "chunk_id": "<uuid>", "content": "..." }`
- THEN the worker calls the embedding model (configured provider)
- AND stores the resulting 1536-dim vector in `knowledge_chunks.embedding` column
- AND updates `knowledge_chunks.indexed_at` timestamp

---

### Requirement: Notification Dispatch Job

The system MUST send in-app notifications (and optionally email) to users when triggered
by price alerts or async job completions.

#### Job: `notifications:send`

- **Trigger:** Enqueued by `market:check_price_alerts` and `vision:detect_disease` jobs
- **Queue:** `critical`
- **Retry policy:** 5 retries with exponential backoff
- **Timeout:** 30 seconds

#### Scenario: In-App Notification

- GIVEN `{ "user_id": "<uuid>", "type": "price_alert", "title": "Wheat Price Alert", "body": "...", "metadata": {...} }`
- WHEN `notifications:send` runs
- THEN a notification row is inserted into `notifications` table
- AND the notification is pushed to user's active WebSocket connection (if connected)
- AND HTTP 201 is returned internally

---

### Requirement: Stale Data Cleanup Job

The system MUST periodically clean up old data to prevent unbounded database growth.

#### Job: `cleanup:stale_data`

- **Schedule:** Daily at 2:00 AM IST (cron: `30 20 * * *` UTC)
- **Queue:** `low`
- **Retry policy:** 1 retry
- **Timeout:** 15 minutes

#### Scenario: Chat Message Cleanup

- GIVEN chat messages older than 90 days in sessions marked for archival
- WHEN `cleanup:stale_data` runs
- THEN messages older than 90 days (configurable via env `CHAT_RETENTION_DAYS=90`) are deleted
- AND `{ "chat_messages_deleted": N }` is logged

#### Scenario: Expired Vision Job Cleanup

- GIVEN Redis keys `vision:result:*` with TTL already expired
- WHEN cleanup runs
- THEN no explicit action needed (Redis TTL handles this automatically)
- AND the job verifies no orphan job rows exist without results

#### Scenario: Old Market Price Data Cleanup

- GIVEN market_prices rows older than 2 years
- WHEN cleanup runs
- THEN rows with `price_date < NOW() - INTERVAL '2 years'` are deleted in batches of 10,000
- AND `{ "market_prices_deleted": N }` is logged

---

### Requirement: Model Warmup Job

The system MUST warm up ML model endpoints after deployment or restart to ensure
the first real user request is fast.

#### Job: `ml:warmup_models`

- **Trigger:** Enqueued once at worker startup (not a cron job)
- **Queue:** `low`
- **Retry policy:** 2 retries with 30s backoff
- **Timeout:** 5 minutes

#### Scenario: Warmup Successful

- GIVEN ml-crop service is running at :8010
- WHEN `ml:warmup_models` runs
- THEN a dummy inference request is sent to:
  - POST /ml/crop/recommend (with synthetic valid inputs)
  - POST /ml/crop/yield (with synthetic valid inputs)
  - POST /ml/crop/fertilizer (with synthetic valid inputs)
  - POST /ml/vision/detect (with a 1×1 pixel test image)
- AND each service's model is loaded into memory
- AND `{ "service": "ml-crop", "warmup_ms": 1200, "status": "ok" }` is logged

---

### Requirement: Asynqmon Dashboard

The system MUST expose the Asynqmon web dashboard for job monitoring.

#### Scenario: Dashboard Access

- GIVEN the workers service is running
- WHEN http://localhost:8080 is accessed
- THEN the Asynqmon UI is served showing:
  - Active, pending, scheduled, retry, archived queues
  - Per-queue statistics (throughput, latency, error rate)
  - Individual job details (payload, retry count, error message)

---

## Job Registry Summary

| Job Type Key | Trigger | Queue | Cron |
|---|---|---|---|
| `market:sync_prices` | Cron | default | `0 */6 * * *` |
| `market:check_price_alerts` | After market sync | critical | — |
| `farm:prefetch_weather` | Cron | default | `0 */3 * * *` |
| `vision:detect_disease` | ml-vision enqueue | default | — |
| `ai:index_knowledge_chunk` | ai-chat enqueue | low | — |
| `notifications:send` | Alert/vision jobs | critical | — |
| `cleanup:stale_data` | Cron | low | `30 20 * * *` |
| `ml:warmup_models` | Startup once | low | — |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Asynq Redis connection |
| `DATABASE_URL` | — | PostgreSQL for job results |
| `ML_CROP_URL` | `http://localhost:8010` | ml-crop service base URL |
| `ML_VISION_URL` | `http://localhost:8011` | ml-vision service base URL |
| `AI_CHAT_URL` | `http://localhost:8012` | ai-chat service base URL |
| `FARM_SERVICE_URL` | `http://localhost:8001` | farm-service base URL |
| `MARKET_SERVICE_URL` | `http://localhost:8002` | market-service base URL |
| `OPENWEATHERMAP_API_KEY` | — | Weather API key |
| `CHAT_RETENTION_DAYS` | `90` | Chat message retention |
| `ASYNQMON_PORT` | `8080` | Asynqmon UI port |
| `HMAC_SECRET` | — | For inter-service calls |
