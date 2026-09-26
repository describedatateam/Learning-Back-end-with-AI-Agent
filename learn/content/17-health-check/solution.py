import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        logger.exception("Health check failed: database unavailable")
        return JsonResponse({"status": "error", "checks": {"database": "error"}}, status=503)
    return JsonResponse({"status": "ok", "checks": {"database": "ok"}})
