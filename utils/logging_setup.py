"""Rotating application logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from utils import config


class RuntimePrivacyFilter(logging.Filter):
    """Drop verbose third-party inference records that may contain source text."""

    sensitive_loggers = ("argostranslate", "ctranslate2")

    def filter(self, record: logging.LogRecord) -> bool:
        is_sensitive = record.name.startswith(self.sensitive_loggers)
        return not is_sensitive or record.levelno >= logging.WARNING


def configure_logging() -> logging.Logger:
    config.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if not any(isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers):
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        file_handler.addFilter(RuntimePrivacyFilter())
        root_logger.addHandler(file_handler)

    # Apply the filter to an existing rotating handler too (for repeated calls
    # in tests or an embedded host process).
    for existing_handler in root_logger.handlers:
        if isinstance(existing_handler, RotatingFileHandler) and not any(
            isinstance(item, RuntimePrivacyFilter) for item in existing_handler.filters
        ):
            existing_handler.addFilter(RuntimePrivacyFilter())

    return logging.getLogger("vitra")
