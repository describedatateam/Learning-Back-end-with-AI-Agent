from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from sandbox.models import Task


@override_settings(ROOT_URLCONF="api")
class PrivateTaskApiTests(TestCase):
    def setUp(self):
        self.ada = User.objects.create_user("ada", password="x")
        self.bob = User.objects.create_user("bob", password="x")
        self.ada_task = Task.objects.create(owner=self.ada, title="Ada's task")
        self.bob_task = Task.objects.create(owner=self.bob, title="Bob's task")
        self.client = APIClient()

    def login(self, user):
        self.client.force_authenticate(user)

    def test_01_requires_login(self):
        """Anonymous requests get 401"""
        self.assertEqual(self.client.get("/tasks/").status_code, 401)

    def test_02_list_only_own(self):
        """GET /tasks/ lists only my tasks"""
        self.login(self.ada)
        response = self.client.get("/tasks/")
        self.assertEqual(response.status_code, 200, "Is the viewset registered at 'tasks'?")
        self.assertEqual([t["title"] for t in response.json()], ["Ada's task"])

    def test_03_owner_field(self):
        """Tasks show the owner's username"""
        self.login(self.ada)
        task = self.client.get(f"/tasks/{self.ada_task.id}/").json()
        self.assertEqual(task, {"id": self.ada_task.id, "title": "Ada's task", "done": False, "owner": "ada"})

    def test_04_create_sets_owner(self):
        """POST /tasks/ makes me the owner, even if the body says otherwise"""
        self.login(self.ada)
        response = self.client.post("/tasks/", {"title": "New", "owner": self.bob.id}, format="json")
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(Task.objects.get(title="New").owner, self.ada)

    def test_05_cannot_read_others(self):
        """Another user's task is a 404"""
        self.login(self.ada)
        self.assertEqual(self.client.get(f"/tasks/{self.bob_task.id}/").status_code, 404)

    def test_06_cannot_change_others(self):
        """PATCH/DELETE on another user's task is a 404 and changes nothing"""
        self.login(self.ada)
        self.assertEqual(self.client.patch(f"/tasks/{self.bob_task.id}/", {"done": True}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"/tasks/{self.bob_task.id}/").status_code, 404)
        self.bob_task.refresh_from_db()
        self.assertFalse(self.bob_task.done)

    def test_07_update_and_delete_own(self):
        """I can update and delete my own task"""
        self.login(self.ada)
        self.assertEqual(self.client.patch(f"/tasks/{self.ada_task.id}/", {"done": True}, format="json").status_code, 200)
        self.ada_task.refresh_from_db()
        self.assertTrue(self.ada_task.done)
        self.assertEqual(self.client.delete(f"/tasks/{self.ada_task.id}/").status_code, 204)

    def test_08_title_required(self):
        """POST without a title is a 400"""
        self.login(self.ada)
        self.assertEqual(self.client.post("/tasks/", {}, format="json").status_code, 400)
