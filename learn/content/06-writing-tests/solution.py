import unittest

from slugs import make_slug


class MakeSlugTests(unittest.TestCase):
    def test_basic_title(self):
        self.assertEqual(make_slug("hello world"), "hello-world")

    def test_lowercases_and_trims(self):
        self.assertEqual(make_slug("  Hello, World!  "), "hello-world")

    def test_collapses_symbol_runs(self):
        self.assertEqual(make_slug("Django & DRF 101"), "django-drf-101")

    def test_limits_length(self):
        slug = make_slug("word " * 30)
        self.assertLessEqual(len(slug), 50)
        self.assertFalse(slug.endswith("-"))

    def test_rejects_empty_result(self):
        with self.assertRaises(ValueError):
            make_slug("!!!")
