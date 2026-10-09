"""The path catalog: loading it from catalog.json and working out a learner's progress through it.

Progress comes from the exercises a learner has passed. A chapter is done when
all its exercises pass; chapters without exercises yet can't be finished, so
they show as "coming soon". A prerequisite marked "I already know this" (or a
passed placement test) counts as done, and chapters proven in a placement test
are skipped. AI-generated chapters have a lesson and quiz instead of exercises:
passing the quiz finishes them.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path as FilePath

from django.db import transaction
from django.utils.text import slugify

from .models import (
    Chapter, ChapterProgress, Course, ExerciseProgress, Path, PathChoice, PathStep, PlacementAttempt, SkippedPath,
)

CATALOG_FILE = FilePath(__file__).resolve().parent / 'catalog.json'
DEFAULT_JOB_PATH = 'backend-developer'  # the existing exercises belong to it

DONE, PROGRESS, TODO, SOON, SKIPPED = 'done', 'progress', 'todo', 'soon', 'skipped'


@transaction.atomic
def load_catalog(data=None):
    """Create or update every path from catalog.json. Safe to run again after editing the file."""
    data = data or json.loads(CATALOG_FILE.read_text(encoding='utf-8'))
    skills = {}
    for order, item in enumerate(data['skill_paths']):
        path, _ = Path.objects.update_or_create(slug=item['slug'], defaults={
            'kind': Path.SKILL, 'title': item['title'], 'summary': item.get('summary', ''),
            'level': item.get('level', ''), 'hours': item.get('hours', 0), 'order': order,
            'project': item.get('project') or {}, 'placement_test': item.get('placement_test') or {},
        })
        path.courses.all().delete()  # chapters hold no learner data, so rebuilding them is safe
        for c_order, course_data in enumerate(item['courses']):
            course = Course.objects.create(path=path, order=c_order, title=course_data['title'],
                                           hours=course_data.get('hours', 0), language=course_data.get('language', ''))
            for ch_order, chapter in enumerate(course_data['chapters']):
                Chapter.objects.create(
                    course=course, order=ch_order, slug=slugify(chapter['title']), title=chapter['title'],
                    learning_goal=chapter.get('learning_goal', ''), exercise_idea=chapter.get('exercise_idea', ''),
                    exercises=chapter.get('exercises', []),
                )
        skills[path.slug] = path
    for order, item in enumerate(data['job_paths']):
        job, _ = Path.objects.update_or_create(slug=item['slug'], defaults={
            'kind': Path.JOB, 'title': item['title'], 'summary': item.get('summary', ''),
            'level': item.get('level', ''), 'hours': item.get('hours', 0), 'order': order,
            'capstone': item.get('capstone') or {},
        })
        job.steps.all().delete()
        for s_order, step in enumerate(item['steps']):
            PathStep.objects.create(job=job, skill=skills[step['skill']], order=s_order,
                                    prerequisite=step.get('prerequisite', False))
    return len(data['job_paths']), len(skills)


# --- Progress -------------------------------------------------------------

def exercise_states(user):
    """{exercise slug: 'passed' | 'started'} for one learner."""
    if not user.is_authenticated:
        return {}
    return {p.slug: 'passed' if p.passed else 'started' for p in ExerciseProgress.objects.filter(user=user)}


def chapter_marks(user):
    """{chapter slug: DONE | 'started' | SKIPPED} from generated-chapter quizzes and placement tests."""
    if not user.is_authenticated:
        return {}
    marks = {slug: DONE if done else 'started' for slug, done in
             ChapterProgress.objects.filter(user=user).values_list('chapter__slug', 'done')}
    seen = set()
    for path_id, skipped in PlacementAttempt.objects.filter(user=user).values_list('path_id', 'skipped_chapters'):
        if path_id not in seen:  # newest first: only the latest attempt per path counts
            seen.add(path_id)
            for slug in skipped:
                marks.setdefault(slug, SKIPPED)
    return marks


def skipped_ids(user):
    if not user.is_authenticated:
        return set()
    return set(SkippedPath.objects.filter(user=user).values_list('path_id', flat=True))


@dataclass
class ChapterView:
    chapter: Chapter
    status: str
    exercises: list  # [(exercise, state)]
    current: bool = False

    @property
    def has_work(self):
        """Something to do here: exercises, or a generated lesson and quiz."""
        return bool(self.exercises or self.chapter.content)

    @property
    def next_exercise(self):
        unpassed = [e for e, state in self.exercises if state != 'passed']
        started = [e for e, state in self.exercises if state == 'started']
        return (started or unpassed or [None])[0]


@dataclass
class SkillView:
    path: Path
    prerequisite: bool
    skipped: bool
    courses: list  # [(course, [ChapterView])]
    chapters: list = field(default_factory=list)

    def __post_init__(self):
        self.chapters = [ch for _, chapters in self.courses for ch in chapters]

    @property
    def done(self):
        return sum(1 for ch in self.chapters if ch.status in (DONE, SKIPPED))

    @property
    def total(self):
        return len(self.chapters)

    @property
    def percent(self):
        return round(100 * self.done / self.total) if self.total else 0

    @property
    def exercise_count(self):
        return sum(len(ch.exercises) for ch in self.chapters)

    @property
    def has_work(self):
        return any(ch.has_work for ch in self.chapters)

    @property
    def status(self):
        if self.skipped:
            return SKIPPED
        if self.total and self.done == self.total:
            return DONE
        if any(ch.status in (DONE, PROGRESS) for ch in self.chapters):
            return PROGRESS
        if not self.has_work:
            return SOON
        return TODO

    @property
    def current(self):
        return any(ch.current for ch in self.chapters)

    @property
    def course_progress(self):
        """One row per course, for the journey on the home page."""
        rows = []
        for course, chapters in self.courses:
            done = sum(1 for ch in chapters if ch.status in (DONE, SKIPPED))
            exercises = sum(len(ch.exercises) for ch in chapters)
            if chapters and done == len(chapters):
                status = DONE
            elif any(ch.status in (DONE, PROGRESS) for ch in chapters):
                status = PROGRESS
            else:
                status = TODO if any(ch.has_work for ch in chapters) else SOON
            rows.append({'course': course, 'chapters': chapters, 'done': done, 'total': len(chapters), 'exercises': exercises,
                         'percent': round(100 * done / len(chapters)) if chapters else 0, 'status': status,
                         'current': any(ch.current for ch in chapters)})
        return rows


def _chapter_status(chapter, exercises, skipped, mark=None):
    if skipped or mark == SKIPPED:
        return SKIPPED
    if chapter.content:
        return DONE if mark == DONE else PROGRESS if mark else TODO
    if not exercises:
        return SOON
    states = [state for _, state in exercises]
    if all(state == 'passed' for state in states):
        return DONE
    if any(states):
        return PROGRESS
    return TODO


def mark_current(skill):
    """Mark "you are here" on a skill path's first chapter that has work left. Returns that chapter."""
    for chapter in skill.chapters:
        if chapter.status in (TODO, PROGRESS):
            chapter.current = True
            return chapter
    return None


def skill_view(path, states, skipped, prerequisite=False, marks=None):
    from .exercises import get_exercise

    marks = marks or {}
    courses = []
    for course in path.courses.all():
        chapters = []
        for chapter in course.chapters.all():
            exercises = [(e, states.get(e.slug)) for e in map(get_exercise, chapter.exercises) if e]
            status = _chapter_status(chapter, exercises, path.id in skipped, marks.get(chapter.slug))
            chapters.append(ChapterView(chapter, status, exercises))
        courses.append((course, chapters))
    return SkillView(path, prerequisite, path.id in skipped, courses)


@dataclass
class JobView:
    path: Path
    prerequisites: list  # [SkillView]
    skills: list         # [SkillView]
    capstone_exercises: list
    current_chapter: ChapterView = None
    current_skill: SkillView = None

    @property
    def done(self):
        return sum(s.done for s in self.skills)

    @property
    def total(self):
        return sum(s.total for s in self.skills)

    @property
    def percent(self):
        return round(100 * self.done / self.total) if self.total else 0

    @property
    def hours_left(self):
        return round(self.path.hours * (100 - self.percent) / 100)

    @property
    def exercises_passed(self):
        every = [state for s in self.prerequisites + self.skills for ch in s.chapters for _, state in ch.exercises]
        every += [state for _, state in self.capstone_exercises]
        return sum(1 for state in every if state == 'passed'), len(every)

    @property
    def next_exercise(self):
        if self.current_chapter:
            return self.current_chapter.next_exercise
        unpassed = [e for e, state in self.capstone_exercises if state != 'passed']
        return unpassed[0] if unpassed else None

    @property
    def started(self):
        return any(ch.status in (DONE, PROGRESS) for s in self.skills for ch in s.chapters)

    @property
    def next_milestone(self):
        """The project at the end of the skill path you are in, or the capstone."""
        skill = self.current_skill
        if skill and skill.path.project.get('title'):
            return skill.path.project['title']
        return self.path.capstone.get('title', '')


def job_view(path, user, states=None):
    from .exercises import get_exercise

    states = exercise_states(user) if states is None else states
    skipped = skipped_ids(user)
    marks = chapter_marks(user)
    prerequisites, skills = [], []
    for step in path.steps.select_related('skill').prefetch_related('skill__courses__chapters'):
        view = skill_view(step.skill, states, skipped, step.prerequisite, marks)
        (prerequisites if step.prerequisite else skills).append(view)
    capstone = [(e, states.get(e.slug)) for e in map(get_exercise, path.capstone.get('exercises', [])) if e]
    job = JobView(path, prerequisites, skills, capstone)
    # "You are here": the first chapter, in path order, that has exercises left to pass.
    for skill in prerequisites + skills:
        for chapter in skill.chapters:
            if chapter.status in (TODO, PROGRESS):
                chapter.current = True
                job.current_chapter, job.current_skill = chapter, skill
                return job
    return job


def current_job_path(user):
    """The learner's chosen job path, else the Backend path (where the exercises are)."""
    if not Path.objects.exists():
        load_catalog()  # a fresh database (or a forgotten `load_catalog`) still gets the catalog
    if user.is_authenticated:
        choice = PathChoice.objects.filter(user=user).select_related('path').first()
        if choice:
            return choice.path
    return Path.objects.filter(slug=DEFAULT_JOB_PATH).first() or Path.objects.filter(kind=Path.JOB).first()
