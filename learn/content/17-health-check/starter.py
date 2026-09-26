import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


# TODO 1: put @require_GET on the line directly above `def health`
def health(request):
    # TODO 2: inside try:, open `with connection.cursor() as cursor:` and run "SELECT 1"
    # TODO 3: except DatabaseError: call logger.exception(...), then return
    #         {"status": "error", "checks": {"database": "error"}} with status=503
    #         (never put the error message in the response)
    # TODO 4: otherwise return {"status": "ok", "checks": {"database": "ok"}} (status 200)
    return JsonResponse({"status": "ok"})
