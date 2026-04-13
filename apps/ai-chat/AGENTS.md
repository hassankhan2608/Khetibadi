# AGENTS.md — apps/ai-chat

> Python/FastAPI service. Port 8012. Groq Llama 3.3 70B chat + LangChain RAG + SSE streaming.
> Read root AGENTS.md first, then this file.

## Service Responsibility

Provides the AI agricultural assistant. Assembles context from farm-service and
market-service, retrieves relevant knowledge chunks from pgvector, builds a structured
system prompt, and streams the LLM response via SSE.

Owns:
- `chat_sessions` table
- `chat_messages` table
- `knowledge_chunks` table (pgvector 1536-dim embeddings)
- Redis rate limiting (`chat:ratelimit:<user_id>`, 30 msg/min sliding window)

## Layout

```
apps/ai-chat/
├── app/
│   ├── main.py                 # FastAPI app + lifespan
│   ├── routes/
│   │   ├── sessions.py         # CRUD for chat sessions
│   │   ├── messages.py         # POST (SSE stream) + GET (history)
│   │   └── knowledge.py        # POST /ai/chat/knowledge (internal)
│   ├── services/
│   │   ├── context_fetcher.py  # HTTP calls to farm + market services (2s timeout each)
│   │   ├── rag.py              # pgvector similarity search
│   │   ├── prompt_builder.py   # system prompt assembly
│   │   └── chat_service.py     # LangChain chain orchestration
│   ├── schemas/
│   │   └── chat.py
│   └── middleware/
│       └── hmac_auth.py
├── tests/
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## LangChain Chain

```
UserMessage
  → embed query (1536-dim)
  → pgvector top-5 cosine similarity search
  → context_fetcher (farms + weather + market, 2s timeout each)
  → prompt_builder (role + user ctx + weather + market + RAG + instructions)
  → ChatGroq(model="llama-3.3-70b-versatile", streaming=True)
  → SSE token stream (event: token / event: done / event: error)
  → save user msg + assistant msg to chat_messages
```

## SSE Event Format

```
event: token
data: {"token": "The", "index": 0}

event: done
data: {"message_id": "<uuid>", "session_id": "<uuid>", "total_tokens": 142}

event: error
data: {"error": "llm_unavailable"}
```

## Key Invariants

- **Degraded mode:** if farm-service or market-service is unreachable (timeout 2s), proceed
  with available context. Mark missing context as "unavailable" in system prompt. Never 5xx.
- **Groq failure:** emit `event: error` and close the SSE connection gracefully. Never hang.
- **Rate limit:** 30 messages/min per user_id in Redis. Return `429` with `retry_after: 60`.
- **Session ownership:** always verify `chat_sessions.user_id == X-User-ID` before any operation.
  Return `404` (not `403`) for sessions belonging to other users.
- **Save after stream:** persist user message before streaming. Persist assistant message after
  `event: done`. If stream fails mid-way, save partial response with `status: "incomplete"`.
- **RAG threshold:** skip chunks with cosine distance > 0.8 (no relevant knowledge).

## System Prompt Structure (in order)

1. Role: "You are Khetibadi AI, an expert agricultural assistant for Indian farmers."
2. User context: farms (name, area_ha, soil_type), current season
3. Weather context (if available)
4. Market context (if available)
5. Relevant knowledge (RAG chunks, if any)
6. Instructions: respond in user's language (Hindi/English), be practical, cite sources

## Critical Pitfalls

- **NEVER** hard-fail on context fetch errors — degraded mode is required.
- **NEVER** store the Groq API key in code — read from `GROQ_API_KEY` env var.
- **NEVER** expose `/ai/chat/knowledge` to the public internet — internal admin only.
- **NEVER** return chat history from another user's session.

## Dev Commands

```bash
cd apps/ai-chat
uv run uvicorn app.main:app --reload --port 8012
uv run pytest tests/ -v
uv run ruff check .
uv run mypy .
```

## Spec Reference

`openspec/specs/ai-chat/spec.md`
