from datetime import date

ALLOWED_ORDERING = {"title", "-title", "due_date", "-due_date", "priority", "-priority"}


def filter_tasks(queryset, params):
    # `queryset` is all the tasks and `params` is a dict of query parameters.
    # The tests pass both in when they call your function.
    # TODO 1: if params has a "status", keep only tasks with that status
    # TODO 2: the same for "priority"
    # TODO 3: if params has a "search", keep titles that contain it (title__icontains)
    # TODO 4: if params has a "due_before", turn it into a date with date.fromisoformat
    #         and keep tasks due on or before it (due_date__lte)
    # TODO 5: sort by params["ordering"] if it's in ALLOWED_ORDERING, otherwise by "id"
    # TODO 6: return the sorted queryset
    return queryset
