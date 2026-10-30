"""Core middleware for ff-engine."""

import uuid

from django.utils.deprecation import MiddlewareMixin

from apps.core.logging import request_id_var


class RequestIDMiddleware(MiddlewareMixin):
    """Attach a unique request ID to every request and response.

    The ID is stored in a contextvar so that the RequestIDFilter can add it
    to every log line for the same request — including Django's built-in
    request logging.
    """

    def process_request(self, request):
        request.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request.request_id)

    def process_response(self, request, response):
        request_id = getattr(request, "request_id", str(uuid.uuid4()))
        response["X-Request-ID"] = request_id
        # Do not clear the contextvar here — Django's request logger
        # (django.request) fires AFTER middleware process_response, so
        # clearing would wipe request_id before it reaches the filter.
        # The next request's process_request overwrites it.
        return response
