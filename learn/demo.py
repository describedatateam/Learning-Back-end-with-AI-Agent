"""A ready-made demo learner, so Describe can be shown in minutes (Day 10).

`python manage.py make_demo` creates (or rebuilds) the account "demo" with a
week of practice: passed back-end exercises, XP and a streak, the Backend job
path chosen, a project walkthrough with some ticks, a Lab page and a public
portfolio at /p/demo/. Nothing here calls Gemini, so it works on free hosting.
The demo account is left out of the case study's numbers.
"""
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import gamification, lab, projects
from .exercises import load_exercises
from .models import ExerciseProgress, LabProject, LearningEvent, Path, PathChoice, Portfolio, Project

USERNAME = 'demo'
PASSED = 5  # the first five back-end exercises

SAMPLE_SRS = {
    'title': 'Study group tracker',
    'summary': 'An API where a study group plans sessions, tracks who attends and shares notes after each one.',
    'goals': ['Plan study sessions with a time and topic', 'See who attended each session',
              'Keep the notes from every session in one place'],
    'users': [{'name': 'Organiser', 'needs': 'Creates sessions and invites members'},
              {'name': 'Member', 'needs': 'Joins sessions and reads the notes'}],
    'stories': [
        {'role': 'organiser', 'want': 'to create a session with a date and topic', 'benefit': 'everyone knows when to meet', 'priority': 'must'},
        {'role': 'member', 'want': 'to mark that I attended', 'benefit': 'the group sees who was there', 'priority': 'must'},
        {'role': 'member', 'want': 'to add notes to a past session', 'benefit': 'people who missed it can catch up', 'priority': 'should'},
    ],
    'data_models': [
        {'name': 'Session', 'fields': ['topic: text', 'starts_at: datetime', 'organiser: user'], 'relations': 'has many Attendance and Note'},
        {'name': 'Attendance', 'fields': ['session', 'member: user'], 'relations': 'one per member per session'},
        {'name': 'Note', 'fields': ['session', 'author: user', 'text'], 'relations': 'belongs to a Session'},
    ],
    'endpoints': [
        {'method': 'GET', 'path': '/api/sessions/', 'purpose': 'List upcoming sessions'},
        {'method': 'POST', 'path': '/api/sessions/', 'purpose': 'Create a session (organisers only)'},
        {'method': 'POST', 'path': '/api/sessions/{id}/attend/', 'purpose': 'Mark yourself as attending'},
        {'method': 'POST', 'path': '/api/sessions/{id}/notes/', 'purpose': 'Add a note to a session'},
    ],
    'done_checks': ['Members cannot edit sessions they did not create', 'Every endpoint has a test'],
    'gaps': [],
    'milestones': [
        {'title': 'Models and admin', 'goal': 'Store sessions, attendance and notes',
         'tasks': ['Write the Session, Attendance and Note models', 'Run the migrations', 'Register the models in admin'],
         'chapters': [], 'skill': ''},
        {'title': 'Read and create sessions', 'goal': 'The first API endpoints',
         'tasks': ['List sessions as JSON', 'Create a session with validation', 'Only organisers can create'],
         'chapters': [], 'skill': ''},
        {'title': 'Attendance and notes', 'goal': 'Members take part',
         'tasks': ['Mark attendance once per member', 'Add notes to a session', 'Write tests for both'],
         'chapters': [], 'skill': ''},
    ],
}

LAB_FILES = {
    'index.html': '<!doctype html>\n<html>\n<head>\n  <link rel="stylesheet" href="style.css">\n</head>\n<body>\n'
                  '  <main class="card">\n    <h1>Study timer</h1>\n    <p id="time">25:00</p>\n'
                  '    <button id="start">Start</button>\n  </main>\n  <script src="script.js"></script>\n</body>\n</html>\n',
    'style.css': 'body { font-family: system-ui, sans-serif; display: grid; place-items: center; min-height: 100vh; margin: 0; background: #eef2ff; }\n'
                 '.card { background: white; padding: 2rem 3rem; border-radius: 16px; text-align: center; }\n'
                 '#time { font-size: 3rem; font-weight: 700; margin: .5rem 0 1rem; }\n'
                 'button { font: inherit; padding: .6rem 1.4rem; border: 0; border-radius: 8px; background: #4f46e5; color: white; }\n',
    'script.js': "let left = 25 * 60;\nlet timer = null;\nconst time = document.getElementById('time');\n"
                 "document.getElementById('start').addEventListener('click', () => {\n"
                 "  if (timer) return;\n  timer = setInterval(() => {\n    left = Math.max(0, left - 1);\n"
                 "    const m = String(Math.floor(left / 60)).padStart(2, '0');\n    const s = String(left % 60).padStart(2, '0');\n"
                 "    time.textContent = `${m}:${s}`;\n    console.log('tick', left);\n  }, 1000);\n});\n",
}


def build(password=None):
    """(user, password). Rebuilds the demo learner from scratch each time."""
    password = password or secrets.token_urlsafe(9)
    User = get_user_model()
    with transaction.atomic():
        User.objects.filter(username=USERNAME).delete()
        user = User.objects.create_user(USERNAME, password=password, first_name='Demo', last_name='Learner')
        _practice(user)
        backend = Path.objects.filter(slug='backend-developer').first()
        if backend:
            PathChoice.objects.create(user=user, path=backend)
        project = _project(user)
        web = _lab(user)
        Portfolio.objects.create(
            user=user, handle=USERNAME, public=True, name='Demo Learner',
            headline='Learning back-end development with Python and Django',
            about='A sample learner made for demos. Everything here was built on Describe.',
            project_ids=[project.id], lab_ids=[web.id])
    return user, password


def _practice(user):
    """Five passed exercises spread over the last five days, with the XP the real runs would give."""
    today = timezone.localdate()
    exercises = load_exercises()[:PASSED]
    for n, exercise in enumerate(exercises):
        day = today - timedelta(days=len(exercises) - 1 - n)
        when = timezone.now() - timedelta(days=(today - day).days)
        total = 4
        ExerciseProgress.objects.create(user=user, slug=exercise.slug, passed=True, tests_passed=total,
                                        tests_total=total, attempts=2)
        rewards = gamification.Rewards(user)
        rewards.award(f'daily:{day.isoformat()}', gamification.DAILY_XP, 'Daily practice')
        rewards.award(f'pass:{exercise.slug}', gamification.PASS_XP.get(exercise.week, 100),
                      f'Completed “{exercise.title}”', exercise.slug)
        rewards.award(f'nopeek:{exercise.slug}', gamification.NO_PEEK_XP, 'No-peek bonus', exercise.slug)
        rewards.summary()  # unlocks the badges these passes earn
        events = [LearningEvent(user=user, kind=LearningEvent.RUN, slug=exercise.slug, seconds_spent=600,
                                data={'passed': total, 'total': total, 'all_passed': True}),
                  LearningEvent(user=user, kind=LearningEvent.PASSED, slug=exercise.slug)]
        for event in LearningEvent.objects.bulk_create(events):
            LearningEvent.objects.filter(pk=event.pk).update(created_at=when)


def _project(user):
    srs, errors = projects.clean_srs(SAMPLE_SRS)
    assert not errors, errors
    project = Project.objects.create(user=user, title=srs['title'], source=Project.DESCRIBED,
                                     brief={'idea': srs['summary']}, srs=srs, done=['m1-t1', 'm1-t2', 'm1-t3', 'm2-t1'],
                                     repo_url='https://github.com/describedatateam/Learning-Back-end-with-AI-Agent')
    projects.ensure_join_code(project)
    return project


def _lab(user):
    return LabProject.objects.create(user=user, title='Study timer', kind='web',
                                     idea='A 25-minute study timer for my study group.',
                                     files=lab.clean_files('web', LAB_FILES))
