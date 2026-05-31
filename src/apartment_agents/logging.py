from __future__ import annotations

import logging
from typing import Any


_CONFIGURED = False


def configure_logging(level: str = "INFO") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        logging.getLogger("apartment_agents").setLevel(level.upper())
        return

    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"apartment_agents.{name}")


def log_kv(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    rendered_fields = " ".join(f"{key}={value!r}" for key, value in sorted(fields.items()))
    if rendered_fields:
        logger.log(level, "%s %s", message, rendered_fields)
    else:
        logger.log(level, "%s", message)
