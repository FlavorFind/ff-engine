"""Structured JSON logging for ff-engine."""
import json
import logging
import traceback


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }

        if record.exc_info:
            log_data["exception"] = traceback.format_exception(*record.exc_info)

        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)
