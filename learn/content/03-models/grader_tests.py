from django.db import models
from django.test import TestCase

from sandbox.models import Book


class BookModelTests(TestCase):
    def field(self, name):
        try:
            return Book._meta.get_field(name)
        except Exception:
            self.fail(f"Book has no field called {name!r}")

    def test_01_title_and_author(self):
        """title and author are CharFields with max lengths 200 and 100"""
        self.assertIsInstance(self.field("title"), models.CharField)
        self.assertEqual(self.field("title").max_length, 200)
        self.assertIsInstance(self.field("author"), models.CharField)
        self.assertEqual(self.field("author").max_length, 100)

    def test_02_published_year_optional(self):
        """published_year is an optional PositiveIntegerField (null and blank)"""
        field = self.field("published_year")
        self.assertIsInstance(field, models.PositiveIntegerField)
        self.assertTrue(field.null, "published_year needs null=True")
        self.assertTrue(field.blank, "published_year needs blank=True")

    def test_03_is_available_default(self):
        """is_available is a BooleanField that defaults to True"""
        self.assertIsInstance(self.field("is_available"), models.BooleanField)
        book = Book.objects.create(title="Dune", author="Frank Herbert")
        self.assertTrue(book.is_available)

    def test_04_created_at_automatic(self):
        """created_at is set automatically on create"""
        self.assertIsInstance(self.field("created_at"), models.DateTimeField)
        book = Book.objects.create(title="Dune", author="Frank Herbert")
        self.assertIsNotNone(book.created_at)

    def test_05_str(self):
        """str(book) is 'Title by Author'"""
        self.assertEqual(str(Book(title="Dune", author="Frank Herbert")), "Dune by Frank Herbert")

    def test_06_ordering(self):
        """Books are ordered by title by default"""
        for title in ["Neuromancer", "Dune", "Foundation"]:
            Book.objects.create(title=title, author="Someone")
        self.assertEqual(list(Book.objects.values_list("title", flat=True)), ["Dune", "Foundation", "Neuromancer"])

    def test_07_is_classic(self):
        """is_classic() is True only for books published before 1950"""
        self.assertTrue(Book(title="1984", author="Orwell", published_year=1949).is_classic())
        self.assertFalse(Book(title="Dune", author="Herbert", published_year=1965).is_classic())
        self.assertFalse(Book(title="X", author="Y", published_year=1950).is_classic())
        self.assertFalse(Book(title="Unknown", author="Anon").is_classic())
