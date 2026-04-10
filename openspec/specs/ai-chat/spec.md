# AI Chat Service Specification

## Purpose

Provide an intelligent agricultural assistant powered by Groq's Llama 3.3 70B LLM with
LangChain orchestration, retrieval-augmented generation (RAG) from a pgvector knowledge base,
and context injection from user farms, live weather, and live market prices. Chat history is
persisted in PostgreSQL. Responses stream via Server-Sent Events (SSE).

---

## Requirements

### Requirement: Start Chat Session

The system MUST create a new chat session scoped to the authenticated user before the first message exchange.

#### Scenario: Valid Session Creation

- GIVEN an authenticated user (X-User-ID header present and HMAC valid)
- WHEN POST /ai/chat/sessions is called with optional `{ "title": "..." }`
- THEN a new row is inserted into `chat_sessions` with status = "active"
- AND the response is `{ "session_id": "<uuid>", "created_at": "<iso8601>" }`

#### Scenario: Unauthenticated Request

- GIVEN no valid X-User-ID / X-HMAC-Signature headers
- WHEN POST /ai/chat/sessions is called
- THEN HTTP 401 is returned with `{ "error": "unauthorized" }`

---

### Requirement: List Chat Sessions

The system MUST return all chat sessions for the authenticated user, ordered by last activity descending.

#### Scenario: Sessions Exist

- GIVEN a user has 3 active sessions
- WHEN GET /ai/chat/sessions is called
- THEN HTTP 200 is returned with array of `{ session_id, title, created_at, last_message_at, message_count }`

#### Scenario: No Sessions

- GIVEN the user has no sessions
- WHEN GET /ai/chat/sessions is called
- THEN HTTP 200 is returned with `{ "sessions": [] }`

---

### Requirement: Send Message and Stream Response

The system MUST accept a user message and return the LLM response as a Server-Sent Events stream.

#### Scenario: Valid Message with Full Context

- GIVEN an active session_id, authenticated user who has at least one farm
- WHEN POST /ai/chat/sessions/{session_id}/messages is called with `{ "content": "What crop should I plant?" }`
- THEN the service fetches context:
  - user's farms (names, soil type, area) from farm-service
  - current weather at primary farm centroid from farm-service
  - market prices for user's crops from market-service
  - last 10 chat turns from `chat_messages` table
  - top-k (k=5) RAG chunks from `knowledge_chunks` via pgvector cosine similarity
- AND the assembled prompt is sent to Groq Llama 3.3 70B via LangChain
- AND the response streams as `text/event-stream` with events:
  - `event: token` — one per LLM output token
  - `event: done` — signals end of stream with full message metadata
- AND the user message is saved to `chat_messages` (role = "user")
- AND the assistant response is saved to `chat_messages` (role = "assistant") after stream completes
- AND `chat_sessions.last_message_at` is updated

#### Scenario: Session Not Found

- GIVEN a session_id that does not belong to the authenticated user
- WHEN POST /ai/chat/sessions/{session_id}/messages is called
- THEN HTTP 404 is returned with `{ "error": "session_not_found" }`

#### Scenario: Empty Message Content

- GIVEN a valid session_id
- WHEN POST /ai/chat/sessions/{session_id}/messages is called with `{ "content": "" }`
- THEN HTTP 422 is returned with `{ "error": "validation_error", "detail": "content cannot be empty" }`

#### Scenario: Context Fetch Failure (Degraded Mode)

- GIVEN farm-service or market-service is unreachable
- WHEN a message is sent
- THEN the service MUST proceed with available context (no hard failure on context fetches)
- AND missing context is noted in the system prompt as "unavailable"
- AND the stream proceeds normally

#### Scenario: Groq API Failure

- GIVEN the Groq API returns a non-2xx error
- WHEN a message is sent
- THEN the SSE stream emits `event: error` with `{ "error": "llm_unavailable" }`
- AND HTTP connection closes gracefully

---

### Requirement: Retrieve Chat History

The system MUST return paginated message history for a session.

#### Scenario: Valid Session History

- GIVEN a session with 30 messages
- WHEN GET /ai/chat/sessions/{session_id}/messages?page=1&page_size=20 is called
- THEN HTTP 200 is returned with messages ordered by `created_at` ascending
- AND pagination metadata: `{ "total": 30, "page": 1, "page_size": 20, "pages": 2 }`

#### Scenario: History for Another User's Session

- GIVEN session_id belongs to user B but user A sends the request
- WHEN GET /ai/chat/sessions/{session_id}/messages is called
- THEN HTTP 404 is returned

---

### Requirement: Delete Chat Session

The system MUST allow users to delete a chat session and all its messages.

#### Scenario: Successful Delete

- GIVEN a valid session owned by the user
- WHEN DELETE /ai/chat/sessions/{session_id} is called
- THEN all `chat_messages` rows for the session are deleted
- AND the `chat_sessions` row is deleted
- AND HTTP 204 is returned

---

### Requirement: RAG Knowledge Base

The system MUST store agricultural knowledge as vector embeddings and retrieve relevant
chunks at inference time.

#### Scenario: Chunk Indexing

- GIVEN a knowledge document (crop guide, pest management article, soil science text)
- WHEN POST /ai/chat/knowledge (internal admin endpoint) is called with `{ "content": "...", "source": "...", "category": "..." }`
- THEN the text is embedded via the configured embedding model (1536-dim)
- AND stored in `knowledge_chunks` table with the embedding vector
- AND HTTP 201 is returned with the chunk_id

#### Scenario: RAG Retrieval at Inference Time

- GIVEN a user query "best fertilizer for wheat in Punjab"
- WHEN the message handler runs context assembly
- THEN the query is embedded
- AND top-5 chunks are fetched via `knowledge_chunks ORDER BY embedding <=> $query_embedding LIMIT 5`
- AND chunk content is injected into the LLM system prompt under "Relevant Knowledge"

#### Scenario: No Relevant Chunks Found

- GIVEN a query with no close embeddings (cosine distance > 0.8 for all chunks)
- WHEN RAG retrieval runs
- THEN no chunks are injected (empty knowledge section)
- AND the LLM proceeds with general knowledge only

---

### Requirement: System Prompt Construction

The system MUST build a structured system prompt for every LLM call.

#### Scenario: Full Context System Prompt

The system MUST assemble the system prompt in this order:
1. **Role definition** — "You are Khetibadi AI, an expert agricultural assistant for Indian farmers."
2. **User context** — farms owned (name, area_ha, soil type), current season
3. **Weather context** — temperature, humidity, rainfall at primary farm (if available)
4. **Market context** — current prices for commodities the user grows (if available)
5. **Relevant knowledge** — top-k RAG chunks (if any)
6. **Instructions** — respond in the user's preferred language (Hindi/English), keep answers practical, cite knowledge sources when used

---

### Requirement: Message Rate Limiting

The system MUST enforce rate limits on message sending to prevent abuse.

#### Scenario: Rate Limit Exceeded

- GIVEN a user has sent 30 messages in the last minute
- WHEN another message is sent
- THEN HTTP 429 is returned with `{ "error": "rate_limit_exceeded", "retry_after": 60 }`
- AND the rate limit is tracked per user_id in Redis with a 60-second sliding window

---

### Requirement: Service Health Check

The system MUST expose a health check endpoint.

#### Scenario: Healthy State

- GIVEN all dependencies (PostgreSQL, Redis, Groq API) are reachable
- WHEN GET /ai/chat/health is called
- THEN HTTP 200 is returned with `{ "status": "ok", "groq": "connected", "db": "connected" }`

#### Scenario: Degraded State

- GIVEN the Groq API is unreachable
- WHEN GET /ai/chat/health is called
- THEN HTTP 503 is returned with `{ "status": "degraded", "groq": "unreachable" }`

---

## API Endpoints Summary

| Method | Path | Description |
|--------|------|-------------|
| POST | /ai/chat/sessions | Create new session |
| GET | /ai/chat/sessions | List user sessions |
| POST | /ai/chat/sessions/{id}/messages | Send message (SSE stream) |
| GET | /ai/chat/sessions/{id}/messages | Get paginated history |
| DELETE | /ai/chat/sessions/{id} | Delete session |
| POST | /ai/chat/knowledge | Index knowledge chunk (internal) |
| GET | /ai/chat/health | Health check |

---

## SSE Event Format

```
event: token
data: {"token": "The", "index": 0}

event: token
data: {"token": " best", "index": 1}

event: done
data: {"message_id": "<uuid>", "session_id": "<uuid>", "total_tokens": 142, "model": "llama-3.3-70b-versatile"}
```

---

## LangChain Chain Design

```
UserMessage
    → EmbeddingModel (embed query)
    → pgvector similarity search (top-5 chunks)
    → ContextFetcher (farms + weather + market via HTTP)
    → SystemPromptBuilder
    → ChatGroq(model="llama-3.3-70b-versatile", streaming=True)
    → SSE token stream
    → PostgreSQL save (user msg + assistant msg)
```
