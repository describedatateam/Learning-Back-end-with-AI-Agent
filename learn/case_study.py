"""The case study page (/case-study/, Day 10): how Describe was built, open without signing in.

The words come from plans/case-study-log.md, shortened. The "results" numbers
are counted live from the site, never typed in, and leave out staff accounts and
the demo learner (learn/demo.py), so they only ever show real learners.
"""
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils.translation import gettext_lazy as _

from . import demo
from .models import CardReview, Chapter, ExerciseProgress, LabProject, LearningEvent, Path, Portfolio, Project

FACTS = [
    {'icon': 'users', 'title': _('Who it is for'),
     'text': _('A back-end cohort of classmates with mixed levels. Some learn only on a phone, and some prefer Arabic.')},
    {'icon': 'target', 'title': _('The ask'),
     'text': _('The lead instructor wanted a place to practise between classes: real code checked automatically, '
               'a path from basics to a job, and help when stuck.')},
    {'icon': 'lock', 'title': _('The limits'),
     'text': _('Two weeks, no budget, free hosting that blocks most outside websites, and code from learners '
               'running on a shared server.')},
]

TIMELINE = [
    {'day': '1', 'title': _('Design system and home page'),
     'text': _('Shared design tokens, icons with no emojis, and an English and Arabic switch with right-to-left layout.')},
    {'day': '2', 'title': _('Accounts and safety'),
     'text': _('Invite-only sign-up, progress per learner, an activity log, and a code runner with no secrets and hard limits.')},
    {'day': '3', 'title': _('Paths and the learning cockpit'),
     'text': _('A DataCamp-style catalog of job and skill paths from a reviewed course map, with a "you are here" journey.')},
    {'day': '4', 'title': _('Placement tests and AI paths'),
     'text': _('Tests that skip what a learner already knows, and Gemini-written skill paths for any topic.')},
    {'day': '5', 'title': _('Bring it to life'),
     'text': _('A capstone illustration on every path card, light motion, the AI tutor on every chapter, and Mermaid diagrams.')},
    {'day': '6', 'title': _('Flashcards'),
     'text': _('Spaced repetition with hands-on cards: predict the output or complete the code, then run it.')},
    {'day': '7', 'title': _('My project (SRS)'),
     'text': _('Describe a project or upload its requirements, then follow it as milestones, alone or as a team.')},
    {'day': '8', 'title': _('Browser code runner and the Lab'),
     'text': _('HTML, CSS, JavaScript, React and Tailwind run in the learner\'s browser; the Lab is a phone-friendly playground.')},
    {'day': '9', 'title': _('Portfolio and GitHub'),
     'text': _('A public page per learner, Lab projects pushed to their own GitHub, and NotebookLM videos per chapter.')},
    {'day': '10', 'title': _('Polish and this case study'),
     'text': _('Phone-width checks on every page, friendly error pages, a one-command demo account and this page.')},
]

DECISIONS = [
    {'icon': 'layers', 'title': _('Follow DataCamp\'s structure'),
     'text': _('Job paths, skill paths, courses, chapters and exercises: a shape learners already know, '
               'so the cohort could start without a tour.')},
    {'icon': 'sparkles', 'title': _('Gemini inside the app, NotebookLM by hand'),
     'text': _('NotebookLM has no public API, so Gemini writes quizzes, slides and flashcards in the app, '
               'and short NotebookLM videos are linked per chapter.')},
    {'icon': 'circle-check', 'title': _('Never trust AI output'),
     'text': _('Every AI reply is checked before it is saved. An AI-written exercise only appears after its own '
               'solution passes and its starter fails.')},
    {'icon': 'globe', 'title': _('Run front-end code in the browser'),
     'text': _('Learner code runs in a sandboxed frame on their own device, so it costs the free server nothing '
               'and cannot touch the site.')},
    {'icon': 'lock', 'title': _('Invite-only with a safety net'),
     'text': _('Testers are trusted classmates, so accounts need an invite and Python runs behind an audit hook '
               'instead of a paid sandbox.')},
    {'icon': 'languages', 'title': _('One stylesheet for both directions'),
     'text': _('Logical CSS (start and end instead of left and right) means Arabic is never a separate design; '
               'code always stays left to right.')},
]

PROBLEMS = [
    {'title': _('AI answers that look right but are not'),
     'text': _('Flashcard outputs and exercise tests written by AI were often slightly wrong. Every Python card and '
               'exercise is now run before saving, and the real output becomes the answer.')},
    {'title': _('Phones hide the symbols code needs'),
     'text': _('Phone keyboards bury { } ( ) ; and Tab, and tapping a helper button closed the keyboard. A key bar '
               'that keeps focus in the editor fixed both.')},
    {'title': _('Mixed Arabic and English text'),
     'text': _('Names like Python and Django rendered in a jumbled order inside Arabic sentences; isolating them '
               'with bidi markup fixed the reading order.')},
    {'title': _('A test helper that vanished'),
     'text': _('JavaScript\'s replace() treats $$ as a pattern, which silently broke every browser test at first; '
               'all inserts now use a replacement function.')},
]

NEXT = [
    _('Review the course map with the instructor, using what the activity log shows about where learners get stuck.'),
    _('Generate a whole job path from a job title.'),
    _('Exercises generated for each learner\'s level.'),
    _('Arabic versions of the hand-written lessons.'),
    _('A real code sandbox if the cohort grows beyond trusted classmates.'),
]

SHOTS = [
    {'file': 'home', 'caption': _('The learning cockpit: one clear next step')},
    {'file': 'lab-phone', 'caption': _('The Lab on a phone: code, preview and tutor')},
    {'file': 'exercise', 'caption': _('A browser exercise with preview and tests')},
    {'file': 'portfolio', 'caption': _('A learner\'s public portfolio')},
]


def numbers():
    """Live counts from the site, real learners only."""
    learners = get_user_model().objects.filter(is_active=True, is_staff=False).exclude(username=demo.USERNAME)
    real = Q(user__in=learners)
    catalog = Path.objects.filter(owner__isnull=True)
    return {
        'learners': learners.count(),
        'active': LearningEvent.objects.filter(real).values('user').distinct().count(),
        'passed': ExerciseProgress.objects.filter(real, passed=True).count(),
        'events': LearningEvent.objects.filter(real).count(),
        'generated': Path.objects.filter(owner__in=learners, ai_generated=True).count(),
        'reviews': CardReview.objects.filter(real).aggregate(n=Sum('reviews'))['n'] or 0,
        'projects': Project.objects.filter(real).count(),
        'labs': LabProject.objects.filter(real).count(),
        'portfolios': Portfolio.objects.filter(real, public=True).count(),
        'job_paths': catalog.filter(kind=Path.JOB).count(),
        'skill_paths': catalog.filter(kind=Path.SKILL).count(),
        'chapters': Chapter.objects.filter(course__path__owner__isnull=True).count(),
    }


def demo_handle():
    """The demo learner's portfolio handle, when `make_demo` has been run and the page is public."""
    return demo.USERNAME if Portfolio.objects.filter(handle=demo.USERNAME, public=True).exists() else ''
