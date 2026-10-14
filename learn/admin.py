from django import forms
from django.contrib import admin

from .models import (
    Chapter, ChapterMedia, ExerciseProgress, GitHubAccount, InviteCode, LearningEvent, Portfolio, Project, XPEvent,
)


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


class ChapterMediaForm(forms.ModelForm):
    """Pick the chapter by its title; the slug is what's stored, so the links survive `load_catalog`."""

    chapter_slug = forms.ChoiceField(label='Chapter')

    class Meta:
        model = ChapterMedia
        fields = ('chapter_slug', 'video_url', 'audio_url', 'note')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        chapters = Chapter.objects.select_related('course__path').order_by('course__path__order', 'course__path__title',
                                                                            'course__order', 'order')
        self.fields['chapter_slug'].choices = [('', '---------')] + [
            (c.slug, f'{c.course.path.title} / {c.title}') for c in chapters]


@admin.register(ChapterMedia)
class ChapterMediaAdmin(admin.ModelAdmin):
    """NotebookLM overviews: make the video or audio in NotebookLM, share it, and paste the link here."""

    form = ChapterMediaForm
    list_display = ('chapter_slug', 'video_url', 'audio_url', 'updated_at')
    search_fields = ('chapter_slug',)


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ('handle', 'user', 'public', 'updated_at')
    list_filter = ('public',)
    search_fields = ('handle', 'user__username')


@admin.register(GitHubAccount)
class GitHubAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'login', 'connected_at')
    fields = ('user', 'login', 'connected_at')  # never the token
    readonly_fields = fields

    def has_add_permission(self, request):
        return False
