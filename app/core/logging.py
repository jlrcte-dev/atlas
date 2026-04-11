"""Logging configuration for Atlas AI Assistant."""

import json
import logging
from datetime import UTC, datetime

from app.core.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger: atlas.<name>."""
    return logging.getLogger(f"atlas.{name}")


def log_action(
    logger: logging.Logger,
    action: str,
    user_id: str = "",
    **kwargs: object,
) -> None:
    """Emit a structured JSON action log entry."""
    entry = {
        "action": action,
        "user_id": user_id,
        "ts": datetime.now(UTC).isoformat(),
        **kwargs,
    }
    logger.info(json.dumps(entry, ensure_ascii=False, default=str))
