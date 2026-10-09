import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _owner():
    return models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')


class ExerciseProgress(models.Model):
    """One learner's work on one exercise."""

    user = _owner()
    slug = models.SlugField()
    code = models.TextField(blank=True)
    passed = models.BooleanField(default=False)
    tests_passed = models.PositiveIntegerField(default=0)
    tests_total = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    quiz_correct = models.PositiveIntegerField(null=True, blank=True)
    quiz_total = models.PositiveIntegerField(null=True, blank=True)
    solution_viewed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'slug'], name='unique_progress_per_user')]

    def __str__(self):
        return f'{self.slug} ({"passed" if self.passed else "in progress"})'


class XPEvent(models.Model):
    """A ledger of XP rewards. `key` is unique per learner, so every reward is paid once."""

    user = _owner()
    key = models.CharField(max_length=120)  # e.g. "pass:models", "daily:2026-09-25"
    slug = models.SlugField(blank=True)
    label = models.CharField(max_length=120)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'key'], name='unique_xp_key_per_user')]

    def __str__(self):
        return f'+{self.amount} {self.label}'


class TutorMessage(models.Model):
    """One turn of a tutor conversation. `topic` is an exercise slug or "general"."""

    ROLE_CHOICES = [('user', 'Learner'), ('assistant', 'Tutor')]

    user = _owner()
    topic = models.SlugField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()   # exactly what was sent to / returned by the model
    display = models.TextField()   # what the chat shows (the question without the code context)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.topic} {self.role}: {self.display[:40]}'


class NotebookEntry(models.Model):
    """An AI-written study-journal page for one passed exercise."""

    user = _owner()
    slug = models.SlugField()
    data = models.JSONField()  # summary, tools, use_case, difficulties, takeaways, next_step
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'slug'], name='unique_notebook_per_user')]

    def __str__(self):
        return f'Notebook: {self.slug}'


def new_invite_code():
    return secrets.token_hex(4).upper()  # e.g. "3F9A0C1B"


class InviteCode(models.Model):
    """Sign-up needs one of these, so only people you invite can make an account."""

    code = models.CharField(max_length=40, unique=True, default=new_invite_code)
    note = models.CharField(max_length=120, blank=True, help_text='Who it is for, e.g. "Cohort 1".')
    max_uses = models.PositiveIntegerField(default=1)
    uses = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_usable(self):
        expired = self.expires_at is not None and self.expires_at <= timezone.now()
        return self.active and not expired and self.uses < self.max_uses

    def __str__(self):
        return f'{self.code} ({self.uses}/{self.max_uses} used)'


class LearningEvent(models.Model):
    """One row per learner action, for the home page numbers and for reviewing the course map."""

    RUN = 'run'                   # full grader run (data: passed, total, all_passed)
    TEST_RUN = 'test_run'         # one grader test
    SELECTION_RUN = 'selection_run'
    PASSED = 'passed'             # first time an exercise passes
    QUIZ = 'quiz'
    HINT = 'hint'                 # asked the tutor about an exercise
    SOLUTION_VIEWED = 'solution_viewed'
    LESSON_FINISHED = 'lesson_finished'
    CHAPTER_SKIPPED = 'chapter_skipped'
    KIND_CHOICES = [
        (RUN, 'Ran the tests'),
        (TEST_RUN, 'Ran one test'),
        (SELECTION_RUN, 'Ran selected code'),
        (PASSED, 'Passed an exercise'),
        (QUIZ, 'Took a quiz'),
        (HINT, 'Asked the tutor'),
        (SOLUTION_VIEWED, 'Opened the solution'),
        (LESSON_FINISHED, 'Finished a lesson'),
        (CHAPTER_SKIPPED, 'Skipped a chapter'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_events')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    slug = models.SlugField(blank=True)  # the exercise, lesson or chapter
    seconds_spent = models.PositiveIntegerField(null=True, blank=True)  # time on the page before this action
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['user', 'created_at'])]

    def __str__(self):
        return f'{self.user} {self.kind} {self.slug}'
