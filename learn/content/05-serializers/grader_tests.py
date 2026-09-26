from datetime import date, timedelta

from django.test import SimpleTestCase

from serializers import TaskSerializer

TOMORROW = (date.today() + timedelta(days=1)).isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


class TaskSerializerTests(SimpleTestCase):
    def check(self, data):
        serializer = TaskSerializer(data=data)
        serializer.is_valid()
        return serializer

    def assertInvalid(self, data, field, message=None):
        serializer = self.check(data)
        self.assertIn(field, serializer.errors, f"Expected an error on {field!r} for {data}; got {serializer.errors}")
        if message:
            self.assertIn(message, [str(m) for m in serializer.errors[field]])

    def test_01_valid_task(self):
        """A valid task passes and exposes validated_data"""
        serializer = self.check({"title": "Write docs", "priority": "low", "due_date": TOMORROW})
        self.assertEqual(serializer.errors, {})
        self.assertEqual(serializer.validated_data["title"], "Write docs")
        self.assertEqual(serializer.validated_data["due_date"], date.today() + timedelta(days=1))

    def test_02_default_priority(self):
        """priority defaults to 'medium'"""
        serializer = self.check({"title": "Write docs"})
        self.assertEqual(serializer.errors, {})
        self.assertEqual(serializer.validated_data.get("priority"), "medium")

    def test_03_title_required(self):
        """title is required"""
        self.assertInvalid({"priority": "low"}, "title")

    def test_04_title_min_length(self):
        """A title shorter than 3 characters (after stripping) is rejected"""
        self.assertInvalid({"title": "  ab  "}, "title", "Title must be at least 3 characters.")

    def test_05_title_trimmed(self):
        """The title is stripped of surrounding whitespace"""
        self.assertEqual(self.check({"title": "  Deploy  "}).validated_data["title"], "Deploy")

    def test_06_invalid_priority(self):
        """priority must be low, medium or high"""
        self.assertInvalid({"title": "Write docs", "priority": "urgent"}, "priority")

    def test_07_due_date_optional(self):
        """due_date can be omitted or null"""
        serializer = self.check({"title": "Write docs", "due_date": None})
        self.assertEqual(serializer.errors, {})
        self.assertIn("due_date", serializer.fields, "TaskSerializer needs a due_date field")

    def test_08_due_date_not_in_past(self):
        """A due_date in the past is rejected"""
        self.assertInvalid({"title": "Write docs", "due_date": YESTERDAY}, "due_date", "Due date cannot be in the past.")

    def test_09_high_needs_due_date(self):
        """High priority without a due_date is rejected on the due_date field"""
        self.assertInvalid({"title": "Fix outage", "priority": "high"}, "due_date", "High priority tasks need a due date.")
        self.assertEqual(self.check({"title": "Fix outage", "priority": "high", "due_date": TOMORROW}).errors, {})
