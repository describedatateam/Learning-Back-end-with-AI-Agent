from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from sandbox.models import Book


@override_settings(ROOT_URLCONF="api")
class BookApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("tester", password="x"))
        self.dune = Book.objects.create(title="Dune", author="Frank Herbert", published_year=1965)
        self.emma = Book.objects.create(title="Emma", author="Jane Austen", published_year=1815)

    def test_01_list(self):
        """GET /books/ returns 200 and all books ordered by id"""
        response = self.client.get("/books/")
        self.assertEqual(response.status_code, 200, "Is the router registered at 'books'?")
        self.assertEqual([b["title"] for b in response.json()], ["Dune", "Emma"])

    def test_02_fields(self):
        """Each book has exactly id, title, author and published_year"""
        book = self.client.get(f"/books/{self.dune.id}/").json()
        self.assertEqual(set(book), {"id", "title", "author", "published_year"})

    def test_03_create(self):
        """POST /books/ creates a book and returns 201"""
        response = self.client.post("/books/", {"title": "Beloved", "author": "Toni Morrison"}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertTrue(Book.objects.filter(title="Beloved").exists())
        self.assertIn("id", response.json())

    def test_04_create_validation(self):
        """POST without a title returns 400"""
        response = self.client.post("/books/", {"author": "Anonymous"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.json())

    def test_05_partial_update(self):
        """PATCH /books/{id}/ changes only the fields sent"""
        response = self.client.patch(f"/books/{self.dune.id}/", {"published_year": 1966}, format="json")
        self.assertEqual(response.status_code, 200)
        self.dune.refresh_from_db()
        self.assertEqual((self.dune.title, self.dune.published_year), ("Dune", 1966))

    def test_06_delete(self):
        """DELETE /books/{id}/ returns 204 and removes the book"""
        response = self.client.delete(f"/books/{self.emma.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Book.objects.filter(id=self.emma.id).exists())

    def test_07_missing_book(self):
        """GET /books/999/ returns 404"""
        self.assertEqual(self.client.get("/books/999/").status_code, 404)
