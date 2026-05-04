"""structlog-based JSON logging for the ai-chat service.

``structlog`` is already a dependency for this service (used by request
correlation via ``asgi-correlation-id`` in later commits). Configure it to
emit single-line JSON to stdout so logs are uniform across the stack.
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str) -> None:
    """Wire stdlib ``logging`` through structlog with a JSON renderer."""

    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
        force=True,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
