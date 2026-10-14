"""A learner's public portfolio page (Day 9): finished paths, projects and Lab work.

The page lives at /p/<handle>/ and opens without signing in once the learner
makes it public. It only ever shows what they chose: projects and Lab projects
are listed by id in Portfolio.project_ids / lab_ids, and nothing else of theirs
(code of exercises, tutor chats, flashcards) appears.
"""
import re

from django.db.models import Q
from django.utils.text import slugify

from . import catalog, gamification, lab, projects
from .models import GitHubAccount, LabProject, Path, Portfolio

HANDLE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$')
RESERVED = {'admin', 'api', 'learn', 'accounts', 'static', 'describe', 'me', 'new', 'settings'}
MAX_ABOUT = 600


def clean_handle(value):
    value = slugify(str(value or '')).lower()[:40].strip('-')
    return value if HANDLE.match(value) and value not in RESERVED else ''


def free_handle(wanted, user=None):
    """`wanted`, or wanted-2, wanted-3... if someone else has it."""
    base = clean_handle(wanted) or 'learner'
    taken = Portfolio.objects.exclude(user=user) if user else Portfolio.objects.all()
    handle, n = base, 1
    while taken.filter(handle=handle).exists() or handle in RESERVED:
        n += 1
        handle = f'{base[:36]}-{n}'
    return handle


def for_user(user):
    """The learner's portfolio settings, made (private) the first time they open the page."""
    portfolio = Portfolio.objects.filter(user=user).first()
    if portfolio:
        return portfolio
    account = GitHubAccount.objects.filter(user=user).first()
    return Portfolio.objects.create(
        user=user, handle=free_handle(user.get_username(), user),
        name=user.get_full_name(), github=account.login if account else '')


def finished_paths(user):
    """Skill paths the learner finished (catalog or their own generated ones), and their job path's progress."""
    states = catalog.exercise_states(user)
    skipped = catalog.skipped_ids(user)
    marks = catalog.chapter_marks(user)
    media = {}
    skills = Path.objects.filter(Q(owner__isnull=True) | Q(owner=user), kind=Path.SKILL).prefetch_related('courses__chapters')
    done = []
    for path in skills:
        view = catalog.skill_view(path, states, skipped, marks=marks, media=media)
        if view.total and not view.skipped and view.status == catalog.DONE:
            done.append(view)
    job = None
    current = catalog.current_job_path(user)
    if current:
        view = catalog.job_view(current, user, states)
        if view.started:
            job = view
    return done, job


def stats(user):
    player = gamification.player_state(user)
    passed = sum(1 for state in catalog.exercise_states(user).values() if state == 'passed')
    return {'level': player['level'], 'xp': player['xp'], 'best_streak': player['best_streak'],
            'exercises': passed, 'badges': len(gamification.earned_badge_ids(user))}


def shown_projects(portfolio):
    ids = [i for i in portfolio.project_ids if isinstance(i, int)]
    rows = []
    for project in projects.visible_projects(portfolio.user).filter(id__in=ids).select_related('user'):
        milestones = projects.milestones(project)
        rows.append({'project': project, 'progress': projects.progress(project), 'milestones': milestones,
                     'team': len(projects.team(project)) > 1,
                     'summary': project.srs.get('summary', ''),
                     'stories': len(project.srs.get('stories', [])),
                     'models': len(project.srs.get('data_models', [])),
                     'endpoints': len(project.srs.get('endpoints', []))})
    return rows


def shown_labs(portfolio):
    ids = [i for i in portfolio.lab_ids if isinstance(i, int)]
    rows = []
    for item in LabProject.objects.filter(user=portfolio.user, id__in=ids):
        kind = lab.KINDS.get(item.kind)
        if not kind:
            continue
        files = lab.clean_files(item.kind, item.files)
        rows.append({'lab': item, 'kind': kind, 'files': files, 'script_id': f'lab-{item.id}',
                     'data': {'files': files, 'libs': kind['libs']}})
    return rows


def page(portfolio):
    """Everything the public page shows."""
    done, job = finished_paths(portfolio.user)
    return {
        'portfolio': portfolio, 'paths': done, 'job': job,
        'stats': stats(portfolio.user) if portfolio.show_stats else None,
        'projects': shown_projects(portfolio), 'labs': shown_labs(portfolio),
        'display_name': portfolio.name or portfolio.user.get_username(),
    }


def save_settings(portfolio, data, user):
    """Apply the settings form. Returns a list of problems (empty when saved)."""
    errors = []
    handle = clean_handle(data.get('handle'))
    if not handle:
        errors.append('handle')
    elif Portfolio.objects.exclude(user=user).filter(handle=handle).exists():
        errors.append('taken')
    else:
        portfolio.handle = handle
    portfolio.name = str(data.get('name', '')).strip()[:80]
    portfolio.headline = str(data.get('headline', '')).strip()[:120]
    portfolio.about = str(data.get('about', '')).strip()[:MAX_ABOUT]
    portfolio.github = re.sub(r'[^A-Za-z0-9-]', '', str(data.get('github', '')).strip().removeprefix('@'))[:39]
    website = str(data.get('website', '')).strip()[:200]
    if website and not re.match(r'^https?://[^\s/$.?#].[^\s]*$', website):
        errors.append('website')
    else:
        portfolio.website = website
    portfolio.public = data.get('public') == 'on'
    portfolio.show_stats = data.get('show_stats') == 'on'
    allowed_projects = set(projects.visible_projects(user).values_list('id', flat=True))
    portfolio.project_ids = sorted(i for i in _ids(data.getlist('projects')) if i in allowed_projects)
    allowed_labs = set(LabProject.objects.filter(user=user).values_list('id', flat=True))
    portfolio.lab_ids = sorted(i for i in _ids(data.getlist('labs')) if i in allowed_labs)
    portfolio.save()
    return errors


def _ids(values):
    return {int(v) for v in values if str(v).isdigit()}
