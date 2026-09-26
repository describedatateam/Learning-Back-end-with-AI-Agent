import os
import unittest
from unittest import mock

from django.core.exceptions import ImproperlyConfigured

from env import env_bool, env_int, env_list, env_str


def environ(**values):
    return mock.patch.dict(os.environ, values)


class EnvTests(unittest.TestCase):
    def setUp(self):
        for name in ["APP_NAME", "APP_DEBUG", "APP_PORT", "APP_HOSTS"]:
            os.environ.pop(name, None)

    def test_01_env_str(self):
        """env_str returns the stripped value, or the default when unset/blank"""
        with environ(APP_NAME="  backend-lab "):
            self.assertEqual(env_str("APP_NAME"), "backend-lab")
        self.assertEqual(env_str("APP_NAME", "fallback"), "fallback")
        with environ(APP_NAME="   "):
            self.assertEqual(env_str("APP_NAME", "fallback"), "fallback")

    def test_02_env_str_required(self):
        """env_str raises ImproperlyConfigured (naming the variable) when required and unset"""
        with self.assertRaisesRegex(ImproperlyConfigured, "APP_NAME"):
            env_str("APP_NAME")

    def test_03_env_bool_true(self):
        """env_bool understands 1/true/yes/on in any case"""
        for raw in ["1", "true", "True", " YES ", "on"]:
            with environ(APP_DEBUG=raw):
                self.assertIs(env_bool("APP_DEBUG"), True, repr(raw))

    def test_04_env_bool_false(self):
        """env_bool understands 0/false/no/off: 'False' must be False!"""
        for raw in ["0", "false", "False", "no", " OFF "]:
            with environ(APP_DEBUG=raw):
                self.assertIs(env_bool("APP_DEBUG", default=True), False, repr(raw))

    def test_05_env_bool_default_and_invalid(self):
        """env_bool uses the default when unset and rejects nonsense"""
        self.assertIs(env_bool("APP_DEBUG"), False)
        self.assertIs(env_bool("APP_DEBUG", default=True), True)
        with environ(APP_DEBUG="maybe"), self.assertRaises(ImproperlyConfigured):
            env_bool("APP_DEBUG")

    def test_06_env_int(self):
        """env_int parses integers, falls back to the default, and rejects non-numbers"""
        with environ(APP_PORT=" 8000 "):
            self.assertEqual(env_int("APP_PORT", 80), 8000)
        self.assertEqual(env_int("APP_PORT", 80), 80)
        with environ(APP_PORT="eighty"), self.assertRaises(ImproperlyConfigured):
            env_int("APP_PORT", 80)

    def test_07_env_list(self):
        """env_list splits on commas, strips and drops empty items"""
        with environ(APP_HOSTS=" localhost, 127.0.0.1 ,,example.com, "):
            self.assertEqual(env_list("APP_HOSTS"), ["localhost", "127.0.0.1", "example.com"])

    def test_08_env_list_default(self):
        """env_list returns the default (or []) when unset"""
        self.assertEqual(env_list("APP_HOSTS"), [])
        self.assertEqual(env_list("APP_HOSTS", ["localhost"]), ["localhost"])
