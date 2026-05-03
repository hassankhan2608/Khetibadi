"""ml-crop FastAPI entrypoint.

Phase 2 skeleton: structured JSON logging, env-driven settings, a ``lifespan``
hook for startup/shutdown logs, and a ``/health`` endpoint. Model loading,
routes, and HMAC auth are wired in subsequent commits per
``apps/ml-crop/AGENTS.md``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ml-crop"

logger = logging.getLogger(SERVICE_NAME)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    configure_logging(settings.log_level)
    logger.info(
        "service starting",
        extra={"service": SERVICE_NAME, "env": settings.app_env, "port": settings.port},
    )
    try:
        yield
    finally:
        logger.info("service stopped cleanly", extra={"service": SERVICE_NAME})


app = FastAPI(title="khetibadi-ml-crop", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe used by Docker and load balancers."""

    return {"status": "ok", "service": SERVICE_NAME}
