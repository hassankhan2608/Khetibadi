"""ai-chat FastAPI entrypoint.

Phase 2 skeleton: structured JSON logging via structlog, env-driven settings,
a ``lifespan`` hook for startup/shutdown logs, and a ``/health`` endpoint.
Groq LLM streaming, LangChain RAG, pgvector retrieval, SSE message routes,
and HMAC auth are wired in subsequent commits per ``apps/ai-chat/AGENTS.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ai-chat"

logger = structlog.get_logger(SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "service starting",
        service=SERVICE_NAME,
        env=settings.app_env,
        port=settings.port,
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", service=SERVICE_NAME)


app = FastAPI(title="khetibadi-ai-chat", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
