from datetime import date
import json

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Project, Task


class TaskApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ada', password='strong-pass-123')
        self.other = User.objects.create_user(username='grace', password='strong-pass-123')
        self.project = Project.objects.create(owner=self.user, name='Website')
        self.other_project = Project.objects.create(owner=self.other, name='Private')
        self.client.force_authenticate(self.user)

    def test_health_is_public(self):
        self.client.force_authenticate(None)
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(response.content), {'status': 'ok'})

    def test_unauthenticated_api_is_rejected(self):
        self.client.force_authenticate(None)
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_projects_are_owned_and_paginated(self):
        Project.objects.create(owner=self.other, name='Not visible')
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['name'], 'Website')

    def test_task_crud_and_filtering(self):
        response = self.client.post('/api/tasks/', {
            'project': self.project.id, 'title': 'Write tests',
            'status': 'in_progress', 'priority': 'high', 'due_date': '2026-10-01',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task_id = response.data['id']
        response = self.client.get('/api/tasks/?status=in_progress')
        self.assertEqual(response.data['count'], 1)
        response = self.client.patch(f'/api/tasks/{task_id}/', {'status': 'done'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'done')
        self.assertEqual(Task.objects.get(id=task_id).due_date, date(2026, 10, 1))
        self.assertEqual(self.client.delete(f'/api/tasks/{task_id}/').status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_create_task_in_another_users_project(self):
        response = self.client.post('/api/tasks/', {
            'project': self.other_project.id, 'title': 'Should fail',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
