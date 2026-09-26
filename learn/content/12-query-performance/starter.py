from django.db.models import Count, Q

from sandbox.models import Project, Task


def task_labels():
    # Correct, but one extra query per task to load task.project!
    # TODO 1: add .select_related("project") to the queryset (keep .order_by("id"))
    return [f"{task.project.name}: {task.title}" for task in Task.objects.order_by("id")]


def project_summaries():
    # Correct, but two extra queries per project!
    # Replace this whole loop with one queryset:
    # TODO 2: Project.objects.annotate(task_count=Count("tasks"), ...)
    # TODO 3: in the same annotate, add done_count: Count only tasks where done is True
    # TODO 4: sort by name with .order_by("name")
    # TODO 5: keep only name, task_count and done_count with .values(...), return list(...)
    summaries = []
    for project in Project.objects.order_by("name"):
        summaries.append({
            "name": project.name,
            "task_count": project.tasks.count(),
            "done_count": project.tasks.filter(done=True).count(),
        })
    return summaries
