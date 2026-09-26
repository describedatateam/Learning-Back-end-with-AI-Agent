from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import SimpleTestCase
from rest_framework import exceptions

from exceptions import api_exception_handler


class ExceptionHandlerTests(SimpleTestCase):
    def handle(self, exc):
        return api_exception_handler(exc, {})

    def test_01_validation_error(self):
        """ValidationError -> 400 with message 'Invalid input.' and field details"""
        response = self.handle(exceptions.ValidationError({"title": ["This field is required."]}))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": {
            "status": 400, "message": "Invalid input.", "details": {"title": ["This field is required."]},
        }})

    def test_02_not_found(self):
        """NotFound -> 404 with the detail as message and empty details"""
        response = self.handle(exceptions.NotFound())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"error": {"status": 404, "message": "Not found.", "details": {}}})

    def test_03_not_authenticated(self):
        """NotAuthenticated -> 401 in the same envelope"""
        response = self.handle(exceptions.NotAuthenticated())
        self.assertEqual(response.data["error"]["status"], 401)
        self.assertEqual(response.data["error"]["message"], "Authentication credentials were not provided.")

    def test_04_django_exceptions(self):
        """Django's Http404 / PermissionDenied are wrapped too"""
        self.assertEqual(self.handle(Http404()).data["error"]["status"], 404)
        self.assertEqual(self.handle(PermissionDenied()).data["error"]["status"], 403)

    def test_05_status_matches(self):
        """The body status always matches the HTTP status code"""
        for exc in [exceptions.MethodNotAllowed("POST"), exceptions.Throttled(wait=5), exceptions.ParseError()]:
            response = self.handle(exc)
            self.assertEqual(response.data["error"]["status"], response.status_code, type(exc).__name__)

    def test_06_unexpected_errors(self):
        """Non-API exceptions return None (so they become a 500)"""
        self.assertIsNone(self.handle(KeyError("boom")))
