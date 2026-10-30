"""Structured JSON logging for ff-engine."""

import contextvars
import json
import logging
import traceback

# Context variable that holds the request_id for the current request.
# Set by RequestIDMiddleware, read by RequestIDFilter so every log line
# in the same request carries the same request_id.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class RequestIDFilter(logging.Filter):
    """Inject the current request_id from the contextvar into every log record.

    This lets the JSONFormatter include request_id on all log lines — including
    Django's built-in request logging (django.request) which does not attach
    request_id on its own.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


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

        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)
