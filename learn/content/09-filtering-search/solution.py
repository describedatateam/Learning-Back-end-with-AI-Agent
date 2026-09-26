from datetime import date

ALLOWED_ORDERING = {"title", "-title", "due_date", "-due_date", "priority", "-priority"}


def filter_tasks(queryset, params):
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("priority"):
        queryset = queryset.filter(priority=params["priority"])
    if params.get("search"):
        queryset = queryset.filter(title__icontains=params["search"])
    if params.get("due_before"):
        queryset = queryset.filter(due_date__lte=date.fromisoformat(params["due_before"]))

    ordering = params.get("ordering")
    return queryset.order_by(ordering if ordering in ALLOWED_ORDERING else "id")
