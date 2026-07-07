"""
logging_config.py — Structured logging setup.

Configures the root logger with either a human-readable text format
(for development) or a structured JSON format (for production / log aggregation).
"""

from __future__ import annotations

import logging
import logging.config
import sys


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        fmt:   Output format — 'text' for human-readable, 'json' for structured.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if fmt == "json":
        formatter_class = _JsonFormatter
    else:
        formatter_class = _TextFormatter

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": formatter_class,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stderr,
                    "formatter": "default",
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            # Silence noisy third-party loggers
            "loggers": {
                "httpx": {"level": "WARNING"},
                "httpcore": {"level": "WARNING"},
                "googleapiclient": {"level": "WARNING"},
                "google.auth": {"level": "WARNING"},
            },
        }
    )


class _TextFormatter(logging.Formatter):
    """Coloured plain-text formatter for development."""

    LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"\033[2m{record.name}\033[0m"
        return f"{level} {name}: {record.getMessage()}"


class _JsonFormatter(logging.Formatter):
    """Structured JSON formatter for production log aggregation."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)
