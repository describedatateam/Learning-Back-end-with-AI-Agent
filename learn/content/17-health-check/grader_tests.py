import json
from unittest import mock

from django.db import OperationalError
from django.test import RequestFactory, TestCase

import views


def broken_connection():
    conn = mock.MagicMock()
    conn.cursor.side_effect = OperationalError("could not connect to server: password=hunter2")
    return conn


class HealthTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def call(self, method="get"):
        return views.health(getattr(self.factory, method)("/health/"))

    def test_01_healthy(self):
        """Returns 200 with database 'ok' when the database works"""
        response = self.call()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content), {"status": "ok", "checks": {"database": "ok"}})

    def test_02_really_queries(self):
        """Actually runs a query (not just returning 'ok')"""
        with mock.patch.object(views, "connection", broken_connection()):
            response = self.call()
        self.assertNotEqual(response.status_code, 200, "The database was down but health said OK")

    def test_03_unhealthy(self):
        """Returns 503 with database 'error' when the database is down"""
        with mock.patch.object(views, "connection", broken_connection()), self.assertLogs("views", "ERROR"):
            response = self.call()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(json.loads(response.content), {"status": "error", "checks": {"database": "error"}})

    def test_04_logs_with_traceback(self):
        """Logs the failure at ERROR level with the traceback"""
        with mock.patch.object(views, "connection", broken_connection()), self.assertLogs("views", "ERROR") as logs:
            self.call()
        self.assertTrue(any(record.exc_info for record in logs.records), "Use logger.exception() inside the except block")

    def test_05_no_leaks(self):
        """The error details are NOT in the response body"""
        with mock.patch.object(views, "connection", broken_connection()), self.assertLogs("views", "ERROR"):
            response = self.call()
        self.assertNotIn(b"hunter2", response.content)

    def test_06_get_only(self):
        """POST returns 405"""
        self.assertEqual(self.call("post").status_code, 405)
