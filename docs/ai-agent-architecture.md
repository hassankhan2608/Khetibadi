# Khetibadi AI Agent Architecture

This document explains how the AI assistant answers with farmer-specific context, calls tools on demand, uses model services, and supports image attachments.

## Goals

- Answer directly first, without sympathy/filler.
- Use the authenticated farmer's farms, weather, market prices, alerts, crop models, and disease model when needed.
- Allow an attached crop image so the assistant can call the plant disease detector.
- Keep browser traffic on the single public API gateway (`auth:8000`).
- Continue in degraded mode when a context tool is temporarily unavailable.

## High-level architecture

```mermaid
flowchart LR
  Browser[Dashboard AI tab] -->|JWT + optional image| Gateway[Auth service / API gateway]
  Gateway -->|HMAC user identity| Chat[ai-chat service]

  Chat -->|tool: farms / weather| Farm[farm-service]
  Chat -->|tool: mandi prices / alerts| Market[market-service]
  Chat -->|tool: crop/yield/fertilizer| MLCrop[ml-crop]
  Chat -->|tool: disease detection + image| MLVision[ml-vision]
  Chat -->|streaming model| Groq[Groq Llama]

  Farm --> OpenWeather[OpenWeatherMap]
  Market <-- Workers[workers]
  Workers --> DataGov[data.gov.in / AGMARKNET]
  MLCrop --> CropArtifacts[local .pkl model artifacts]
  MLVision --> VisionArtifact[local ResNet34 .pth artifact]
```

## Low-level request flow

```mermaid
sequenceDiagram
  participant UI as Dashboard
  participant GW as Auth Gateway
  participant AI as ai-chat
  participant Farm as farm-service
  participant Market as market-service
  participant Crop as ml-crop
  participant Vision as ml-vision
  participant LLM as Groq

  UI->>GW: POST /ai/chat/sessions/{id}/messages (Bearer, optional image)
  GW->>AI: Proxy with X-User-ID + HMAC headers
  AI->>AI: Save user message
  AI->>Farm: GET /farms (tool context)
  AI->>Market: GET /market/prices?limit=5 (tool context)
  AI->>LLM: Prompt + tool specs + context snapshot
  LLM-->>AI: Tool calls if more data/model predictions needed
  AI->>Farm: Optional weather/soil tool
  AI->>Market: Optional price/alert tool
  AI->>Crop: Optional crop/yield/fertilizer model tool
  AI->>Vision: Optional disease model tool with attached image
  AI->>LLM: Tool results + final-answer instruction
  LLM-->>AI: Streaming answer tokens
  AI-->>GW: SSE token/done/error events
  GW-->>UI: SSE token/done/error events
  AI->>AI: Save complete/incomplete assistant message
```

## Tool list

| Tool | Downstream service | Purpose |
|---|---|---|
| `get_farms` | `farm-service` | Fetch authenticated farmer's farms, crop, soil type, area, boundaries. |
| `get_farm_weather` | `farm-service` | Fetch current OpenWeatherMap weather for a farm. |
| `get_soil_samples` | `farm-service` | Fetch soil sample history for a farm. |
| `get_market_prices` | `market-service` | Fetch latest mandi prices filtered by commodity/state. |
| `get_market_alerts` | `market-service` | Fetch user's price alerts. |
| `recommend_crop` | `ml-crop` | Run crop recommendation model. |
| `predict_yield` | `ml-crop` | Run yield model. |
| `recommend_fertilizer` | `ml-crop` | Run fertilizer model. |
| `detect_plant_disease` | `ml-vision` | Run plant disease model on the attached image. |

## Agent loop

```mermaid
flowchart TD
  A[Receive farmer message] --> B[Persist user message]
  B --> C[Preload farms, market prices, alerts]
  C --> D{Groq key configured?}
  D -- No and fake disabled --> E[SSE error: llm_unavailable]
  D -- No and fake enabled --> F[Local deterministic fallback]
  D -- Yes --> G[Send prompt + tool specs to Groq]
  G --> H{Tool call returned?}
  H -- Yes --> I[Execute tool with HMAC user identity]
  I --> J[Append ToolMessage]
  J --> G
  H -- No/max rounds --> K[Ask Groq for final direct answer]
  K --> L[Stream token events]
  L --> M[Persist assistant message]
  M --> N[SSE done]
```

## Security and identity

- The browser sends only the access token to the public auth gateway.
- The auth gateway validates JWT and forwards internal requests with `X-User-ID`, `X-Timestamp`, and `X-HMAC-Signature`.
- The AI service re-signs tool calls with the same HMAC formula used by downstream services.
- Tool calls are scoped to the authenticated farmer's `user_id`.
- API keys remain in `.env` and container environment only; they are never committed.

## Image attachment flow

```mermaid
flowchart LR
  UI[AI composer with leaf image] --> GW[Auth gateway]
  GW --> AI[ai-chat multipart parser]
  AI --> LLM[Groq decides if image diagnosis matters]
  LLM -->|detect_plant_disease| AI
  AI --> Vision[ml-vision /ml/vision/detect]
  Vision --> Gate[non-plant OOD gate]
  Gate --> Model[ResNet34 PlantVillage model]
  Model --> AI
  AI --> LLM
  LLM --> UIAnswer[Direct farmer answer]
```

## Frontend behavior

- The AI tab supports text plus an optional JPEG/PNG leaf image.
- SSE events are parsed in the browser; only assistant text is shown.
- Raw `event:` / `data:` JSON is not displayed.
- When streaming finishes, the dashboard refreshes chat history and clears the transient stream bubble.

## Current implementation limits

- Chat sessions/messages are still in memory; Postgres persistence is planned.
- RAG knowledge is still in-memory text chunks; pgvector retrieval is planned.
- Redis-backed rate limiting is planned; current rate limiting is in memory.
- Tool-calling is real, but the model may choose not to call a tool if the prompt is general.
- Vision non-plant detection is a heuristic OOD gate; a production-grade gate needs negative examples and calibration.
