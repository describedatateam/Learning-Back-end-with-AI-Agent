"""Mutation testing: your tests must pass on the real code and fail on bugs."""
import importlib
import io
import re
import sys
import unittest

import slugs

CORRECT = slugs.make_slug


def no_lowercase(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")[:50].rstrip("-")
    if not slug:
        raise ValueError("empty")
    return slug


def no_collapse(text):
    slug = re.sub(r"[^a-z0-9]", "-", text.lower()).strip("-")[:50].rstrip("-")
    if not slug:
        raise ValueError("empty")
    return slug


def no_length_limit(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise ValueError("empty")
    return slug


def no_error_on_empty(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50].rstrip("-")


def run_learner_tests(implementation):
    """Load test_slugs.py with `implementation` as make_slug and run it."""
    slugs.make_slug = implementation
    try:
        sys.modules.pop("test_slugs", None)
        module = importlib.import_module("test_slugs")
        suite = unittest.defaultTestLoader.loadTestsFromModule(module)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        return suite.countTestCases(), result
    finally:
        slugs.make_slug = CORRECT


class YourTestsTests(unittest.TestCase):
    def assertCatches(self, mutant, bug):
        _, result = run_learner_tests(mutant)
        self.assertFalse(result.wasSuccessful(), f"None of your tests noticed this bug: {bug}")

    def test_01_enough_tests(self):
        """test_slugs.py has at least 4 test methods"""
        count, _ = run_learner_tests(CORRECT)
        self.assertGreaterEqual(count, 4, f"Found {count} test(s); write at least 4.")

    def test_02_pass_on_correct_code(self):
        """All your tests pass against the correct make_slug"""
        _, result = run_learner_tests(CORRECT)
        problems = [f"{test.id().split('.')[-1]}: {trace.strip().splitlines()[-1]}" for test, trace in result.failures + result.errors]
        self.assertTrue(result.wasSuccessful(), "These tests fail on correct code:\n" + "\n".join(problems))

    def test_03_catches_missing_lowercase(self):
        """Catches the bug: slug is not lower-cased"""
        self.assertCatches(no_lowercase, "'Hello World' -> 'Hello-World'")

    def test_04_catches_no_collapse(self):
        """Catches the bug: each symbol becomes its own '-'"""
        self.assertCatches(no_collapse, "'Django & DRF' -> 'django---drf'")

    def test_05_catches_no_length_limit(self):
        """Catches the bug: slugs longer than 50 characters"""
        self.assertCatches(no_length_limit, "long titles are not shortened")

    def test_06_catches_no_error(self):
        """Catches the bug: '!!!' returns '' instead of raising ValueError"""
        self.assertCatches(no_error_on_empty, "make_slug('!!!') returns ''")
