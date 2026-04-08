# Database Specification

## Purpose

PostgreSQL 16 schema with PostGIS (spatial data) and pgvector (embeddings). All services share one database; each owns its own tables. Redis 7 handles caching, rate limiting, and job queues.

## Requirements

### Requirement: User Table

The system SHALL store user accounts with bcrypt-hashed passwords and soft-delete support.

#### Scenario: Schema
```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       TEXT UNIQUE NOT NULL,
  password    TEXT NOT NULL,
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at  TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users (email) WHERE deleted_at IS NULL;
```

#### Scenario: Soft delete
- GIVEN a user is deleted
- WHEN `deleted_at` is set
- THEN all queries filter `WHERE deleted_at IS NULL`
- AND the email is freed for re-registration

---

### Requirement: Refresh Token Table

The system SHALL store hashed refresh tokens with family-based revocation support.

#### Scenario: Schema
```sql
CREATE TABLE refresh_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  TEXT NOT NULL,
  family      UUID NOT NULL,
  expires_at  TIMESTAMPTZ NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_rt_user_id   ON refresh_tokens (user_id);
CREATE INDEX idx_rt_token_hash ON refresh_tokens (token_hash);
```

#### Scenario: Family revocation
- WHEN a refresh token is reused after rotation
- THEN `DELETE FROM refresh_tokens WHERE family = $1` revokes the entire session family

---

### Requirement: Farm Table

The system SHALL store farm records with PostGIS geometry for field boundaries.

#### Scenario: Schema
```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE farms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        TEXT NOT NULL,
  boundary    GEOMETRY(POLYGON, 4326),
  area_ha     NUMERIC(10, 4),
  soil_type   TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_farms_user_id  ON farms (user_id);
CREATE INDEX idx_farms_boundary ON farms USING GIST (boundary);
```

#### Scenario: Area calculation
- GIVEN a farm boundary polygon in WGS84
- WHEN the farm is saved
- THEN `area_ha` is computed as `ST_Area(ST_Transform(boundary, 32643)) / 10000`

---

### Requirement: Soil Data Table

The system SHALL store per-farm soil sample readings.

#### Scenario: Schema
```sql
CREATE TABLE soil_samples (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  farm_id       UUID NOT NULL REFERENCES farms(id) ON DELETE CASCADE,
  sampled_at    DATE NOT NULL,
  nitrogen      NUMERIC(6,2),
  phosphorus    NUMERIC(6,2),
  potassium     NUMERIC(6,2),
  ph            NUMERIC(4,2),
  organic_carbon NUMERIC(6,2),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_soil_farm_id ON soil_samples (farm_id);
```

---

### Requirement: Market Price Table

The system SHALL persist AGMARKNET commodity prices with market location and date.

#### Scenario: Schema
```sql
CREATE TABLE market_prices (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  commodity     TEXT NOT NULL,
  market        TEXT NOT NULL,
  state         TEXT NOT NULL,
  min_price     NUMERIC(10,2),
  max_price     NUMERIC(10,2),
  modal_price   NUMERIC(10,2),
  price_date    DATE NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX idx_mp_unique ON market_prices (commodity, market, price_date);
CREATE INDEX idx_mp_commodity   ON market_prices (commodity);
CREATE INDEX idx_mp_state       ON market_prices (state);
CREATE INDEX idx_mp_price_date  ON market_prices (price_date);
```

---

### Requirement: Chat Session and Message Tables

The system SHALL persist AI chat history per user with session grouping.

#### Scenario: Schema
```sql
CREATE TABLE chat_sessions (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cm_session_id ON chat_messages (session_id);
CREATE INDEX idx_cs_user_id    ON chat_sessions (user_id);
```

---

### Requirement: Knowledge Base Embeddings Table

The system SHALL store pgvector embeddings for the RAG knowledge base.

#### Scenario: Schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE knowledge_chunks (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source      TEXT NOT NULL,
  content     TEXT NOT NULL,
  embedding   vector(1536),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_kc_embedding ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
```

#### Scenario: Similarity search
- GIVEN a user message is embedded
- WHEN a cosine similarity search is run with `k=5`
- THEN the top 5 most relevant knowledge chunks are returned
- AND the query uses the HNSW index with `ef_search=40`

---

### Requirement: Price Alerts Table

The system SHALL store user-defined commodity price alert thresholds.

#### Scenario: Schema
```sql
CREATE TABLE price_alerts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  commodity   TEXT NOT NULL,
  threshold   NUMERIC(10,2) NOT NULL,
  direction   TEXT NOT NULL CHECK (direction IN ('above', 'below')),
  triggered   BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_pa_user_id   ON price_alerts (user_id);
CREATE INDEX idx_pa_commodity ON price_alerts (commodity);
```

---

### Requirement: Redis Usage

Redis SHALL be used for rate limiting, session caching, job queues, and weather cache — not as a primary data store.

#### Scenario: Key namespaces
- Rate limiting: `rl:<ip>:<endpoint>` with TTL = window duration
- Weather cache: `weather:<farm_id>` with TTL = 3 hours
- Market cache: `market:<commodity>:<state>` with TTL = 6 hours
- Asynq job queues: managed by Asynq client (keys prefixed `asynq:`)

#### Scenario: Cache invalidation on sync
- GIVEN the market sync worker runs
- WHEN new prices are written to PostgreSQL
- THEN all `market:*` keys are deleted from Redis
