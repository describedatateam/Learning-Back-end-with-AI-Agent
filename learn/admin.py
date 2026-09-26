from django.contrib import admin

from .models import ExerciseProgress, XPEvent


@admin.register(ExerciseProgress)
class ExerciseProgressAdmin(admin.ModelAdmin):
    list_display = ('slug', 'passed', 'tests_passed', 'tests_total', 'attempts', 'quiz_correct', 'updated_at')


@admin.register(XPEvent)
class XPEventAdmin(admin.ModelAdmin):
    list_display = ('label', 'amount', 'key', 'created_at')
    search_fields = ('key', 'label')
