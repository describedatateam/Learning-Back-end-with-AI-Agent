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
    PATH_SKIPPED = 'path_skipped'  # ticked "I already know this" on a prerequisite (data: skipped)
    PATH_CHOSEN = 'path_chosen'
    PLACEMENT = 'placement'           # took a placement test (data: correct, total, tasks_passed, tasks_total, passed)
    PATH_GENERATED = 'path_generated'  # generated a skill path with AI (data: skill, level, hours_per_week)
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
        (PATH_SKIPPED, 'Skipped a prerequisite'),
        (PATH_CHOSEN, 'Chose a job path'),
        (PLACEMENT, 'Took a placement test'),
        (PATH_GENERATED, 'Generated a skill path'),
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


# The catalog: job paths are made of skill paths, skill paths of courses, courses of chapters.
# It is loaded from learn/catalog.json with `python manage.py load_catalog`.

class Path(models.Model):
    JOB = 'job'
    SKILL = 'skill'
    KIND_CHOICES = [(JOB, 'Job path'), (SKILL, 'Skill path')]

    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    level = models.CharField(max_length=20, blank=True)
    hours = models.PositiveSmallIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)
    project = models.JSONField(default=dict, blank=True)         # skill path project: title, brief, skills_used
    capstone = models.JSONField(default=dict, blank=True)        # job path capstone: title, brief, milestones, exercises
    placement_test = models.JSONField(default=dict, blank=True)  # prerequisites only
    # Skill paths a learner generated with AI belong to them; catalog paths have no owner.
    ai_generated = models.BooleanField(default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                              related_name='generated_paths')
    request = models.JSONField(default=dict, blank=True)  # what the learner asked for: skill, level, hours_per_week
    created_at = models.DateTimeField(null=True, blank=True, auto_now_add=True)

    class Meta:
        ordering = ['kind', 'order', 'id']

    def __str__(self):
        return self.title


class PathStep(models.Model):
    """One skill path inside a job path, in order. Prerequisites can be skipped."""

    job = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='steps')
    skill = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='in_jobs')
    order = models.PositiveSmallIntegerField()
    prerequisite = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.job} > {self.skill}'


class Course(models.Model):
    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='courses')
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    hours = models.PositiveSmallIntegerField(default=0)
    language = models.CharField(max_length=20, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class Chapter(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='chapters')
    order = models.PositiveSmallIntegerField()
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    learning_goal = models.TextField(blank=True)
    exercise_idea = models.TextField(blank=True)
    exercises = models.JSONField(default=list, blank=True)  # slugs of exercises in learn/content/
    # Generated chapters carry their own lesson (Markdown), quiz and slides instead of exercises.
    content = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class PathChoice(models.Model):
    """The job path a learner picked. The latest one is their current path."""

    user = _owner()
    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class SkippedPath(models.Model):
    """A prerequisite the learner said they already know."""

    user = _owner()
    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'path'], name='unique_skip_per_user')]


class ChapterProgress(models.Model):
    """A learner's quiz result on a generated chapter. Passing the quiz finishes the chapter."""

    user = _owner()
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='+')
    quiz_correct = models.PositiveIntegerField(default=0)
    quiz_total = models.PositiveIntegerField(default=0)
    done = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'chapter'], name='unique_chapter_progress_per_user')]


class PlacementAttempt(models.Model):
    """One go at a prerequisite's placement test. The latest attempt decides which chapters are skipped."""

    user = _owner()
    path = models.ForeignKey(Path, on_delete=models.CASCADE, related_name='+')
    correct = models.PositiveIntegerField()        # multiple-choice questions answered right
    total = models.PositiveIntegerField()
    tasks_passed = models.PositiveIntegerField(default=0)  # coding tasks whose tests all pass
    tasks_total = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    skipped_chapters = models.JSONField(default=list, blank=True)  # chapter slugs proven known
    answers = models.JSONField(default=dict, blank=True)           # {"mcq": {...}, "code": {...}}
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.user} {self.path} {self.correct}/{self.total}'
