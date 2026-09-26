import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST


@require_GET
def greet(request):
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "name is required"}, status=400)
    return JsonResponse({"message": f"Hello, {name}!"})


@require_POST
def add(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "invalid JSON"}, status=400)

    a, b = data.get("a"), data.get("b")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return JsonResponse({"error": "a and b must be numbers"}, status=400)
    return JsonResponse({"result": a + b})
