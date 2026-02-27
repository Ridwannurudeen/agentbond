"""Structured JSON log formatter for AgentBond."""

import json
import logging
import traceback
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object.

    Standard fields:
        ts        — ISO-8601 UTC timestamp
        level     — DEBUG / INFO / WARNING / ERROR / CRITICAL
        logger    — logger name
        msg       — formatted message
        exc       — exception traceback (only when an exception is present)

    Any keys passed via ``extra=`` are merged into the top-level object.
    """

    def format(self, record: logging.LogRecord) -> str:
        record.getMessage()  # ensure args are interpolated into record.message

        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Merge any extra fields the caller supplied
        skip = logging.LogRecord.__dict__.keys() | {
            "message", "asctime", "args", "exc_info", "exc_text", "stack_info",
        }
        for key, value in record.__dict__.items():
            if key not in skip and not key.startswith("_"):
                payload[key] = value

        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)
