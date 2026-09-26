from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser, User
from django.test import RequestFactory, TestCase

from permissions import IsOwnerOrReadOnly, IsStaffForDelete


class PermissionTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = User.objects.create_user("owner", password="x")
        self.other = User.objects.create_user("other", password="x")
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.note = SimpleNamespace(owner=self.owner)

    def request(self, method, user):
        request = getattr(self.factory, method.lower())("/notes/1/")
        request.user = user
        return request


class IsOwnerOrReadOnlyTests(PermissionTestCase):
    def setUp(self):
        super().setUp()
        self.perm = IsOwnerOrReadOnly()

    def test_01_anonymous_blocked(self):
        """Anonymous users are denied (has_permission)"""
        self.assertFalse(self.perm.has_permission(self.request("GET", AnonymousUser()), None))

    def test_02_authenticated_allowed(self):
        """Logged-in users pass has_permission"""
        self.assertTrue(self.perm.has_permission(self.request("GET", self.other), None))

    def test_03_anyone_can_read(self):
        """Non-owners can read (GET/HEAD/OPTIONS) an object"""
        for method in ["GET", "HEAD", "OPTIONS"]:
            self.assertTrue(self.perm.has_object_permission(self.request(method, self.other), None, self.note), method)

    def test_04_owner_can_write(self):
        """The owner can PATCH, PUT and DELETE"""
        for method in ["PATCH", "PUT", "DELETE"]:
            self.assertTrue(self.perm.has_object_permission(self.request(method, self.owner), None, self.note), method)

    def test_05_others_cannot_write(self):
        """Non-owners cannot PATCH, PUT or DELETE"""
        for method in ["PATCH", "PUT", "DELETE"]:
            self.assertFalse(self.perm.has_object_permission(self.request(method, self.other), None, self.note), method)


class IsStaffForDeleteTests(PermissionTestCase):
    def setUp(self):
        super().setUp()
        self.perm = IsStaffForDelete()

    def test_06_non_delete_allowed(self):
        """Non-DELETE methods are allowed for everyone"""
        for method in ["GET", "POST", "PATCH"]:
            self.assertTrue(self.perm.has_permission(self.request(method, self.other), None), method)

    def test_07_delete_needs_staff(self):
        """DELETE is allowed for staff only"""
        self.assertTrue(self.perm.has_permission(self.request("DELETE", self.staff), None))
        self.assertFalse(self.perm.has_permission(self.request("DELETE", self.other), None))
        self.assertFalse(self.perm.has_permission(self.request("DELETE", AnonymousUser()), None))
