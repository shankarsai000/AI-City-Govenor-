"""
Structured JSON logging configuration using structlog.

Design decision: structlog over stdlib logging because:
1. Every log line is a JSON object — directly parseable by log aggregators (Loki, ELK)
2. Context binding (agent_id, action_id, request_id) travels across call stack automatically
3. Development renderer gives human-readable colored output
4. Production renderer outputs clean JSON without changing call sites
"""
import logging
import sys
from typing import Any

import structlog


def configure_logging(log_level: str = "INFO", is_production: bool = False) -> None:
    """
    Configure structlog with appropriate processors for environment.
    Call once at application startup.
    """
    def add_logger_name(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        if hasattr(logger, "name"):
            event_dict["logger"] = logger.name
        elif hasattr(logger, "_logger") and hasattr(logger._logger, "name"):
            event_dict["logger"] = logger._logger.name
        return event_dict

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        # JSON output for log aggregators in production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable colored output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a named logger. Use module __name__ as the name."""
    return structlog.get_logger(name)
