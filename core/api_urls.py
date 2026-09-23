from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api_views import ProjectViewSet, TaskViewSet
from .views import health

router = DefaultRouter()
router.register('projects', ProjectViewSet, basename='project')
router.register('tasks', TaskViewSet, basename='task')

urlpatterns = [
    path('health/', health, name='health'),
    path('', include(router.urls)),
]

