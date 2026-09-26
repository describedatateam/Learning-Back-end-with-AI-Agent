from datetime import date

from django.test import TestCase

from filters import filter_tasks
from sandbox.models import Task


class FilterTasksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Task.objects.create(title="Deploy API", status="todo", priority="high", due_date=date(2025, 3, 1))
        Task.objects.create(title="Write docs", status="done", priority="low", due_date=date(2025, 2, 1))
        Task.objects.create(title="Fix deploy script", status="todo", priority="low", due_date=None)
        Task.objects.create(title="Answer email", status="in_progress", priority="medium", due_date=date(2025, 4, 1))

    def titles(self, params):
        return [t.title for t in filter_tasks(Task.objects.all(), params)]

    def test_01_no_params(self):
        """No params returns every task ordered by id"""
        self.assertEqual(self.titles({}), ["Deploy API", "Write docs", "Fix deploy script", "Answer email"])

    def test_02_status(self):
        """?status= filters by exact status"""
        self.assertEqual(self.titles({"status": "todo"}), ["Deploy API", "Fix deploy script"])

    def test_03_priority(self):
        """?priority= filters by exact priority"""
        self.assertEqual(self.titles({"priority": "low"}), ["Write docs", "Fix deploy script"])

    def test_04_combined(self):
        """Filters combine (AND)"""
        self.assertEqual(self.titles({"status": "todo", "priority": "low"}), ["Fix deploy script"])

    def test_05_search(self):
        """?search= matches titles case-insensitively"""
        self.assertEqual(self.titles({"search": "DEPLOY"}), ["Deploy API", "Fix deploy script"])

    def test_06_due_before(self):
        """?due_before= keeps tasks due on or before the date"""
        self.assertEqual(self.titles({"due_before": "2025-03-01"}), ["Deploy API", "Write docs"])

    def test_07_bad_date(self):
        """An invalid due_before raises ValueError"""
        with self.assertRaises(ValueError):
            self.titles({"due_before": "next friday"})

    def test_08_ordering(self):
        """?ordering= sorts by an allowed field (with optional '-')"""
        self.assertEqual(self.titles({"ordering": "title"}), ["Answer email", "Deploy API", "Fix deploy script", "Write docs"])
        self.assertEqual(self.titles({"ordering": "-title"}), ["Write docs", "Fix deploy script", "Deploy API", "Answer email"])

    def test_09_ordering_whitelist(self):
        """Unknown ordering values are ignored (falls back to id)"""
        self.assertEqual(self.titles({"ordering": "status"}), ["Deploy API", "Write docs", "Fix deploy script", "Answer email"])
        self.assertEqual(self.titles({"ordering": "nonexistent_field"}), ["Deploy API", "Write docs", "Fix deploy script", "Answer email"])

    def test_10_empty_values_ignored(self):
        """Empty parameter values are ignored"""
        self.assertEqual(len(self.titles({"status": "", "search": "", "ordering": ""})), 4)
