from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, viewsets

from .models import Project, Task
from .serializers import ProjectSerializer, TaskSerializer


class OwnedViewSet(viewsets.ModelViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ProjectViewSet(OwnedViewSet):
    serializer_class = ProjectSerializer
    filterset_fields = ('name',)
    search_fields = ('name', 'description')
    ordering_fields = ('name', 'created_at', 'updated_at')

    def get_queryset(self):
        return Project.objects.filter(owner=self.request.user)


class TaskViewSet(OwnedViewSet):
    serializer_class = TaskSerializer
    filterset_fields = ('project', 'status', 'priority', 'due_date')
    search_fields = ('title', 'description')
    ordering_fields = ('title', 'status', 'priority', 'due_date', 'created_at', 'updated_at')

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user).select_related('project')
