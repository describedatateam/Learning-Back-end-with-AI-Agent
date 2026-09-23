from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Project, Task


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Project
        fields = ('id', 'owner', 'name', 'description', 'created_at', 'updated_at')
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at')


class TaskSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    project_name = serializers.ReadOnlyField(source='project.name')

    class Meta:
        model = Task
        fields = (
            'id', 'owner', 'project', 'project_name', 'title', 'description',
            'status', 'priority', 'due_date', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'owner', 'project_name', 'created_at', 'updated_at')

    def validate_project(self, project):
        if project.owner_id != self.context['request'].user.id:
            raise serializers.ValidationError('You can only use your own projects.')
        return project

