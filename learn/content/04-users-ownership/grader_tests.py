from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from sandbox.models import Note
from services import create_note, notes_for, register_user


class RegisterUserTests(TestCase):
    def test_01_creates_user(self):
        """register_user creates and returns a user"""
        user = register_user("ada", "ada@example.com", "s3cret-pass!")
        self.assertIsInstance(user, User)
        self.assertTrue(User.objects.filter(username="ada", email="ada@example.com").exists())

    def test_02_password_is_hashed(self):
        """The password is hashed, not stored as plain text"""
        user = register_user("ada", "ada@example.com", "s3cret-pass!")
        user.refresh_from_db()
        self.assertNotEqual(user.password, "s3cret-pass!", "The password was stored as plain text!")
        self.assertTrue(user.check_password("s3cret-pass!"))

    def test_03_duplicate_username(self):
        """A duplicate username (any case) raises ValueError"""
        register_user("ada", "ada@example.com", "s3cret-pass!")
        with self.assertRaisesRegex(ValueError, "username already taken"):
            register_user("ADA", "other@example.com", "another-pass!")
        self.assertEqual(User.objects.count(), 1)


class OwnershipTests(TestCase):
    def setUp(self):
        self.ada = User.objects.create_user("ada", password="x")
        self.bob = User.objects.create_user("bob", password="x")

    def test_04_create_note(self):
        """create_note saves a note owned by the user"""
        note = create_note(self.ada, "Buy milk")
        self.assertIsInstance(note, Note)
        self.assertEqual(Note.objects.get(pk=note.pk).owner, self.ada)

    def test_05_only_own_notes(self):
        """notes_for(user) never returns other users' notes"""
        Note.objects.create(owner=self.ada, text="ada 1")
        Note.objects.create(owner=self.bob, text="bob 1")
        Note.objects.create(owner=self.ada, text="ada 2")
        self.assertEqual(sorted(n.text for n in notes_for(self.ada)), ["ada 1", "ada 2"])
        self.assertEqual([n.text for n in notes_for(self.bob)], ["bob 1"])

    def test_06_newest_first(self):
        """notes_for(user) returns the newest note first"""
        now = timezone.now()
        for days_ago, text in [(3, "old"), (1, "new"), (2, "middle")]:
            note = Note.objects.create(owner=self.ada, text=text)
            Note.objects.filter(pk=note.pk).update(created_at=now - timedelta(days=days_ago))
        self.assertEqual([n.text for n in notes_for(self.ada)], ["new", "middle", "old"])
