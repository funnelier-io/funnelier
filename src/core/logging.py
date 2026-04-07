"""
Structured Logging Configuration.

Sets up structlog for JSON-formatted, context-rich log output.
Call ``setup_logging()`` once during app startup (lifespan).

Every log entry automatically includes:
- timestamp (ISO-8601)
- level
- logger name
- request_id, tenant_id, user_id (when bound via middleware)
"""

import logging
import sys
from typing import Any

import structlog


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
) -> None:
    """
    Configure structlog + stdlib logging pipeline.

    Parameters
    ----------
    log_level : root log level
    json_format : True for JSON output (production), False for coloured console
    """

    # Shared processors — run for both structlog and stdlib loggers
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog's formatter
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Quieten noisy third-party loggers
    for name in ("uvicorn.access", "sqlalchemy.engine", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger, optionally named."""
    return structlog.get_logger(name)

