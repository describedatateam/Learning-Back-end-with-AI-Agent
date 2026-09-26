from django.test import TestCase

from reports import project_summaries, task_labels
from sandbox.models import Project, Task


class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        website = Project.objects.create(name="Website")
        api = Project.objects.create(name="API")
        Project.objects.create(name="Zine")  # no tasks
        Task.objects.create(project=website, title="Design homepage", done=True)
        Task.objects.create(project=api, title="Add auth")
        Task.objects.create(project=website, title="Write copy")
        Task.objects.create(project=api, title="Paginate", done=True)
        Task.objects.create(project=website, title="Launch")

    def test_01_task_labels_correct(self):
        """task_labels() returns 'Project: Task' ordered by task id"""
        self.assertEqual(task_labels(), [
            "Website: Design homepage", "API: Add auth", "Website: Write copy", "API: Paginate", "Website: Launch",
        ])

    def test_02_task_labels_one_query(self):
        """task_labels() runs exactly 1 query"""
        with self.assertNumQueries(1):
            task_labels()

    def test_03_summaries_correct(self):
        """project_summaries() returns name, task_count, done_count ordered by name"""
        summaries = [dict(s) for s in project_summaries()]
        self.assertEqual(summaries, [
            {"name": "API", "task_count": 2, "done_count": 1},
            {"name": "Website", "task_count": 3, "done_count": 1},
            {"name": "Zine", "task_count": 0, "done_count": 0},
        ])

    def test_04_summaries_one_query(self):
        """project_summaries() runs exactly 1 query"""
        with self.assertNumQueries(1):
            list(project_summaries())

    def test_05_scales(self):
        """Still 1 query each with 20 more projects and tasks"""
        for i in range(20):
            project = Project.objects.create(name=f"Extra {i:02d}")
            Task.objects.create(project=project, title=f"Task {i}")
        with self.assertNumQueries(1):
            task_labels()
        with self.assertNumQueries(1):
            list(project_summaries())
