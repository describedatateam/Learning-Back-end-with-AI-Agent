from django.db.models import Count, Q

from sandbox.models import Project, Task


def task_labels():
    tasks = Task.objects.select_related("project").order_by("id")
    return [f"{task.project.name}: {task.title}" for task in tasks]


def project_summaries():
    projects = (
        Project.objects
        .annotate(task_count=Count("tasks"), done_count=Count("tasks", filter=Q(tasks__done=True)))
        .order_by("name")
        .values("name", "task_count", "done_count")
    )
    return list(projects)
