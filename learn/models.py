from django.db import models


class ExerciseProgress(models.Model):
    """One learner per local install, so progress is keyed by exercise slug."""

    slug = models.SlugField(unique=True)
    code = models.TextField(blank=True)
    passed = models.BooleanField(default=False)
    tests_passed = models.PositiveIntegerField(default=0)
    tests_total = models.PositiveIntegerField(default=0)
    attempts = models.PositiveIntegerField(default=0)
    quiz_correct = models.PositiveIntegerField(null=True, blank=True)
    quiz_total = models.PositiveIntegerField(null=True, blank=True)
    solution_viewed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.slug} ({"passed" if self.passed else "in progress"})'


class XPEvent(models.Model):
    """A ledger of XP rewards. `key` is unique, so every reward is paid once."""

    key = models.CharField(max_length=120, unique=True)  # e.g. "pass:models", "daily:2026-09-25"
    slug = models.SlugField(blank=True)
    label = models.CharField(max_length=120)
    amount = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'+{self.amount} {self.label}'


class TutorMessage(models.Model):
    """One turn of a tutor conversation. `topic` is an exercise slug or "general"."""

    ROLE_CHOICES = [('user', 'Learner'), ('assistant', 'Tutor')]

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

    slug = models.SlugField(unique=True)
    data = models.JSONField()  # summary, tools, use_case, difficulties, takeaways, next_step
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Notebook: {self.slug}'
