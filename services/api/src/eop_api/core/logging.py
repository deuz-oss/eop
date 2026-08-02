import logging
import sys

import structlog

from eop_api.core.config import settings
from eop_api.core.request_context import current_request_id, current_user_id


def configure_logging() -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer()
        if settings.environment == "development"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger(name)


def log_event(
    event: str,
    level: int = logging.INFO,
    name: str | None = None,
    **fields: object,
) -> None:
    """Logs a structured event through the project's configured logger.

    Thin wrapper around `get_logger()`: automatically attaches the current
    request/user context (from request_context) alongside any caller-supplied
    fields. Timestamps are already stamped by the configured logger's
    TimeStamper processor.
    """
    get_logger(name).log(
        level,
        event,
        request_id=current_request_id(),
        user_id=current_user_id(),
        **fields,
    )
