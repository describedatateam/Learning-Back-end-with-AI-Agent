from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    # `exc` is the exception and `context` is a dict. The tests pass both in.
    response = exception_handler(exc, context)
    # TODO 1: if response is None (not a web error), return None
    # TODO 2: for a ValidationError: message "Invalid input.", details = response.data
    # TODO 3: for anything else: message str(response.data["detail"]), details {}
    # TODO 4: set response.data to {"error": {"status": ..., "message": ..., "details": ...}}
    #         using response.status_code for "status"
    # TODO 5: return the same response
    return response
