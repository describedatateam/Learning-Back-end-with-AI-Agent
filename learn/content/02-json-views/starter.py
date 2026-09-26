import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


def greet(request):
    # `request` is the request object. The tests build it and call your view with it.
    # TODO 1: allow only GET: put @require_GET on the line above `def greet`
    # TODO 2: read the "name" query parameter (default "") and strip it
    # TODO 3: if the name is empty, return {"error": "name is required"} with status=400
    # TODO 4: otherwise return {"message": "Hello, <name>!"} (replace the line below)
    return JsonResponse({"message": "Hello, world!"})


def add(request):
    # TODO 5: allow only POST: put @require_POST on the line above `def add`
    # TODO 6: json.loads(request.body) inside try/except json.JSONDecodeError;
    #         on error return {"error": "invalid JSON"} with status=400
    # TODO 7: if a or b is missing or not an int/float, return
    #         {"error": "a and b must be numbers"} with status=400
    # TODO 8: return {"result": a + b} (replace the line below)
    return JsonResponse({"result": 0})
