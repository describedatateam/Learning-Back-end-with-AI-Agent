from django.contrib import admin
from .models import Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'owner__username')
    list_filter = ('created_at',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'owner', 'status', 'priority', 'due_date')
    search_fields = ('title', 'description', 'owner__username', 'project__name')
    list_filter = ('status', 'priority', 'project')
