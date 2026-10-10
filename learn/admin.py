from django.contrib import admin

from .models import ExerciseProgress, InviteCode, LearningEvent, Project, XPEvent


@admin.register(ExerciseProgress)
class ExerciseProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'slug', 'passed', 'tests_passed', 'tests_total', 'attempts', 'quiz_correct', 'updated_at')
    list_filter = ('user', 'passed')


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'amount', 'key', 'created_at')
    list_filter = ('user',)
    search_fields = ('key', 'label')


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'note', 'uses', 'max_uses', 'active', 'expires_at', 'created_at')
    list_filter = ('active',)
    search_fields = ('code', 'note')


@admin.register(LearningEvent)
class LearningEventAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'kind', 'slug', 'seconds_spent', 'data')
    list_filter = ('kind', 'user')
    search_fields = ('slug',)
    date_hierarchy = 'created_at'

    def has_change_permission(self, request, obj=None):
        return False  # the log is a record of what happened


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'source', 'language', 'updated_at')
    list_filter = ('source',)
    search_fields = ('title', 'user__username')
