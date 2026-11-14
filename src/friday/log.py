"""Logging structuré JSON (structlog)."""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(level: str = "INFO", json: bool = True) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str = "friday") -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)
