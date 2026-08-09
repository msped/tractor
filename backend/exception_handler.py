import logging
import uuid

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """
    DRF exception handler that guarantees a ``detail`` key and logs the cause.

    Two gaps in the default handler made production failures hard to diagnose:

    1. Unhandled exceptions return ``None`` from the default handler, so DRF
       re-raises and Django renders an HTML 500 page. The frontend's
       ``extractApiError`` finds no ``detail`` and falls back to a generic
       "please try again", losing the reason entirely.
    2. Handled 4xx responses are never logged, so a rejected upload or a
       throttled login leaves no server-side trail.

    Unhandled exceptions get a short reference id that appears both in the
    response and the log line, so a user-reported error can be tied back to a
    stack trace without asking them to reproduce it.
    """
    response = drf_exception_handler(exc, context)
    view = context.get("view")
    request = context.get("request")
    view_name = type(view).__name__ if view else "unknown"
    path = getattr(request, "path", "unknown")

    if response is None:
        reference = uuid.uuid4().hex[:8]
        logger.exception(
            "Unhandled exception in %s (%s) [ref=%s]",
            view_name,
            path,
            reference,
            exc_info=exc,
        )
        return Response(
            {
                "detail": (
                    "An unexpected server error occurred. Quote reference "
                    f"{reference} when reporting this."
                ),
                "reference": reference,
            },
            status=500,
        )

    # 5xx that DRF *did* handle still warrants a stack trace; 4xx is expected
    # traffic, so log it at INFO with just enough context to spot patterns
    # (repeated 403s, a client hammering a throttled endpoint).
    if response.status_code >= 500:
        logger.error(
            "%s in %s (%s): %s",
            response.status_code,
            view_name,
            path,
            exc,
            exc_info=exc,
        )
    else:
        logger.info(
            "%s in %s (%s): %s", response.status_code, view_name, path, exc
        )

    # Field-validation errors serialise as {"field": ["msg"]} with no `detail`,
    # so the frontend's fallback chain misses them. Add one without discarding
    # the per-field data the forms rely on.
    if isinstance(response.data, dict) and "detail" not in response.data:
        first_field = next(iter(response.data), None)
        if first_field is not None:
            value = response.data[first_field]
            message = value[0] if isinstance(value, list) and value else value
            if isinstance(message, str):
                response.data["detail"] = message

    return response
