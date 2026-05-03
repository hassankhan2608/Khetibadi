"""ml-vision FastAPI entrypoint.

Phase 2 skeleton: structured JSON logging, env-driven settings, a ``lifespan``
hook for startup/shutdown logs, and a ``/health`` endpoint. ResNet34 model
loading, OpenCV preprocessing, rembg, HMAC auth, and the Redis-backed async
job cache are wired in subsequent commits per ``apps/ml-vision/AGENTS.md``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.logging_config import configure_logging

SERVICE_NAME = "ml-vision"

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


app = FastAPI(title="khetibadi-ml-vision", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}
