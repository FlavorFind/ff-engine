"""
E38 — Usage metering.

Records one RequestLog row after every authenticated API request.
Wired as a DRF response signal via a custom APIView mixin, called from
the process_response hook in MeteringMiddleware.

Architecture:
  request  →  view  →  MeteringMiddleware.process_response()
                         └─ _log_request() writes RequestLog row

The daily Celery beat task rolls up RequestLog rows into UsageRecord.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

REQUEST_START_ATTR = "_metering_start_ms"


class MeteringMiddleware:
    """
    Django middleware that:
      1. Records request start time.
      2. After the view returns, writes a RequestLog row if the request
         was authenticated with an ApiKey.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Record start time in milliseconds
        setattr(request, REQUEST_START_ATTR, int(time.monotonic() * 1000))
        response = self.get_response(request)
        self._log_request(request, response)
        return response

    def _log_request(self, request, response) -> None:
        try:
            # Only log authenticated API key requests
            api_key = getattr(request, "auth", None)
            if api_key is None:
                return

            from apps.clients.models import RequestLog

            start_ms = getattr(request, REQUEST_START_ATTR, None)
            elapsed = 0
            if start_ms is not None:
                elapsed = max(0, int(time.monotonic() * 1000) - start_ms)

            endpoint = request.path

            RequestLog.objects.create(
                client=api_key.client,
                endpoint=endpoint,
                status_code=response.status_code,
                response_ms=elapsed,
            )
        except Exception:
            # Never let metering errors affect the response
            logger.exception("metering: failed to log request")
