import hmac
from unittest import mock

from django.test import TestCase

from sandbox.models import Task
from security import api_key_matches, find_tasks_by_title, mask_email, safe_next_url

HOSTS = ["backendlab.test"]


class SafeNextUrlTests(TestCase):
    def test_01_allows_safe_urls(self):
        """Relative paths and allowed hosts pass through"""
        for url in ["/dashboard/", "/tasks/?page=2", "https://backendlab.test/account/"]:
            self.assertEqual(safe_next_url(url, HOSTS), url)

    def test_02_blocks_open_redirects(self):
        """Other hosts, protocol-relative and javascript: URLs become '/'"""
        for url in ["https://evil.example/login", "//evil.example", "javascript:alert(1)", "http://backendlab.test.evil.example/", "", None]:
            self.assertEqual(safe_next_url(url, HOSTS), "/", f"{url!r} should be blocked")


class ApiKeyTests(TestCase):
    def test_03_matches(self):
        """Equal keys match; different ones don't"""
        self.assertTrue(api_key_matches("sk_live_abc123", "sk_live_abc123"))
        self.assertFalse(api_key_matches("sk_live_abc124", "sk_live_abc123"))

    def test_04_empty_never_matches(self):
        """Empty or missing keys never match (not even each other)"""
        for provided, expected in [("", ""), (None, None), (None, "secret"), ("secret", "")]:
            self.assertFalse(api_key_matches(provided, expected), f"{provided!r} vs {expected!r}")

    def test_05_constant_time(self):
        """Uses hmac.compare_digest for the comparison"""
        with mock.patch("hmac.compare_digest", wraps=hmac.compare_digest) as spy, \
                mock.patch("secrets.compare_digest", wraps=hmac.compare_digest) as secrets_spy:
            api_key_matches("secret-a", "secret-b")
        self.assertTrue(spy.called or secrets_spy.called, "api_key_matches should call hmac.compare_digest(...)")


class MaskEmailTests(TestCase):
    def test_06_masks_local_part(self):
        """mask_email keeps the first character and the domain"""
        self.assertEqual(mask_email("ada.lovelace@example.com"), "a***@example.com")
        self.assertEqual(mask_email("b@x.io"), "b***@x.io")

    def test_07_invalid_email(self):
        """Values without a proper '@' become '***'"""
        for value in ["not-an-email", "", None, "@example.com"]:
            self.assertEqual(mask_email(value), "***", repr(value))


class SqlInjectionTests(TestCase):
    def setUp(self):
        self.task = Task.objects.create(title="Deploy")
        Task.objects.create(title="Secret task")

    def test_08_finds_by_title(self):
        """find_tasks_by_title still finds matching rows"""
        self.assertEqual(find_tasks_by_title("Deploy"), [self.task.id])

    def test_09_injection_blocked(self):
        """An injection payload matches nothing instead of every row"""
        self.assertEqual(find_tasks_by_title("x' OR '1'='1"), [])

    def test_10_quotes_are_data(self):
        """Titles containing quotes work (they are data, not SQL)"""
        tricky = Task.objects.create(title="Ada's task")
        self.assertEqual(find_tasks_by_title("Ada's task"), [tricky.id])
