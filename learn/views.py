import json
import math
import re
from itertools import groupby
from pathlib import Path as FilePath

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language, gettext
from django.views.decorators.http import require_POST

import markdown

from . import catalog, flashcards, gamification, generator, languages, notebook, placement, projects, tutor
from .exercises import get_exercise, list_tests, load_exercises, run_selection, run_snippet, run_tests
from .models import (
    CardReview, Chapter, ChapterProgress, ExerciseProgress, LearningEvent, NotebookEntry, Path, PathChoice, Project,
    SkippedPath, TutorMessage, XPEvent,
)

MAX_SECONDS_SPENT = 6 * 60 * 60  # ignore page timers left open overnight
WEEK_TITLES = {
    1: 'Python, HTTP & Django basics',
    2: 'Building REST APIs',
    3: 'Databases, safety & settings',
    4: 'Capstone: a real API',
}


def _exercise_or_404(slug):
    exercise = get_exercise(slug)
    if exercise is None:
        raise Http404('No such exercise')
    return exercise


def _can_run(request):
    # The runner executes submitted Python (and the tutor spends AI credit), so
    # only signed-in learners can use it. Accounts need an invite code.
    return request.user.is_authenticated


def _seconds_spent(data):
    """Seconds the learner had the page open before this action, as the browser reports it."""
    try:
        seconds = int(data.get('seconds'))
    except (TypeError, ValueError):
        return None
    return seconds if 0 <= seconds <= MAX_SECONDS_SPENT else None


def log_event(request, kind, slug='', seconds_spent=None, **data):
    LearningEvent.objects.create(user=request.user, kind=kind, slug=slug, seconds_spent=seconds_spent, data=data)


@login_required
def dashboard(request):
    exercises = load_exercises()
    progress = {p.slug: p for p in ExerciseProgress.objects.filter(user=request.user)}
    earned = gamification.xp_by_exercise(request.user)
    for exercise in exercises:
        exercise.progress = progress.get(exercise.slug)
        exercise.xp_earned = earned.get(exercise.slug, 0)
        exercise.xp_max = sum(gamification.exercise_rewards(exercise).values())
    weeks = [
        {'number': week, 'title': WEEK_TITLES.get(week, ''), 'exercises': list(items)}
        for week, items in groupby(exercises, key=lambda e: e.week)
    ]
    done = sum(1 for p in progress.values() if p.passed)
    earned_badges = gamification.earned_badge_ids(request.user)
    return render(request, 'learn/dashboard.html', {
        'weeks': weeks,
        'done': done,
        'total': len(exercises),
        'percent': round(100 * done / len(exercises)) if exercises else 0,
        'player': gamification.player_state(request.user),
        'badges': [{'badge': b, 'earned': b.id in earned_badges} for b in gamification.BADGES],
        'badges_earned': len(earned_badges),
        'recent_xp': XPEvent.objects.filter(user=request.user, amount__gt=0)[:8],
    })


ACTIVITY_KINDS = [LearningEvent.PASSED, LearningEvent.RUN, LearningEvent.QUIZ, LearningEvent.HINT,
                  LearningEvent.SOLUTION_VIEWED, LearningEvent.PATH_SKIPPED, LearningEvent.PATH_CHOSEN,
                  LearningEvent.PLACEMENT, LearningEvent.PATH_GENERATED]


def _recent_activity(user, limit=5):
    events = list(LearningEvent.objects.filter(user=user, kind__in=ACTIVITY_KINDS)[:limit])
    passed_xp = {x.slug: x.amount for x in XPEvent.objects.filter(
        user=user, key__in=[f'pass:{e.slug}' for e in events if e.kind == LearningEvent.PASSED])}
    slugs = [e.slug for e in events]
    paths = {p.slug: p.title for p in Path.objects.filter(slug__in=slugs)}
    paths.update({c.slug: c.title for c in Chapter.objects.filter(slug__in=slugs)})
    for event in events:
        exercise = get_exercise(event.slug)
        event.topic = exercise.title if exercise else paths.get(event.slug, event.slug)
        event.xp = passed_xp.get(event.slug) if event.kind == LearningEvent.PASSED else None
    return events


def home(request):
    """The learning cockpit: where you are in your path and the one next step."""
    path = catalog.current_job_path(request.user)
    job = catalog.job_view(path, request.user) if path else None
    player = gamification.player_state(request.user)
    context = {'job': job, 'player': player, 'cards_due': flashcards.due_count(request.user),
               'generated_count': Path.objects.filter(owner=request.user).count() if request.user.is_authenticated else 0}
    if job and request.user.is_authenticated:
        passed, total = job.exercises_passed
        chapters_done = job.done + sum(s.done for s in job.prerequisites)
        chapters_total = job.total + sum(s.total for s in job.prerequisites)
        context.update({
            'exercises_passed': passed, 'exercises_total': total,
            'exercises_percent': round(100 * passed / total) if total else 0,
            'chapters_done': chapters_done, 'chapters_total': chapters_total,
            'chapters_percent': round(100 * chapters_done / chapters_total) if chapters_total else 0,
            'activity': _recent_activity(request.user),
        })
    return render(request, 'learn/home.html', context)


def _visible_paths(user):
    """Catalog paths, plus the learner's own generated ones."""
    if user.is_authenticated:
        return Path.objects.filter(Q(owner__isnull=True) | Q(owner=user))
    return Path.objects.filter(owner__isnull=True)


def path_catalog(request):
    current = catalog.current_job_path(request.user)  # also loads the catalog into an empty database
    states = catalog.exercise_states(request.user)
    chosen = request.user.is_authenticated and PathChoice.objects.filter(user=request.user).exists()
    jobs = [catalog.job_view(p, request.user, states) for p in Path.objects.filter(kind=Path.JOB)]
    skipped = catalog.skipped_ids(request.user)
    marks = catalog.chapter_marks(request.user)
    prerequisite_ids = set(Path.objects.filter(in_jobs__prerequisite=True).values_list('id', flat=True))
    skills = [catalog.skill_view(p, states, skipped, p.id in prerequisite_ids, marks)
              for p in Path.objects.filter(kind=Path.SKILL, owner__isnull=True).prefetch_related('courses__chapters')]
    generated = []
    if request.user.is_authenticated:
        generated = [catalog.skill_view(p, states, skipped, False, marks) for p in
                     Path.objects.filter(owner=request.user).order_by('-created_at').prefetch_related('courses__chapters')]
    tab = 'mine' if request.GET.get('tab') == 'mine' and request.user.is_authenticated else 'featured'
    return render(request, 'learn/catalog.html', {
        'jobs': jobs, 'skills': skills, 'generated': generated, 'current': current if chosen else None, 'tab': tab,
        'player': gamification.player_state(request.user),
    })


def path_detail(request, slug):
    path = get_object_or_404(_visible_paths(request.user), slug=slug)
    context = {'path': path, 'player': gamification.player_state(request.user)}
    if path.kind == Path.JOB:
        context['job'] = catalog.job_view(path, request.user)
        context['is_current'] = (request.user.is_authenticated
                                 and PathChoice.objects.filter(user=request.user).values_list('path_id', flat=True).first() == path.id)
    else:
        prerequisite = path.in_jobs.filter(prerequisite=True).exists()
        context['skill'] = catalog.skill_view(path, catalog.exercise_states(request.user),
                                              catalog.skipped_ids(request.user), prerequisite,
                                              catalog.chapter_marks(request.user))
        context['current_chapter'] = catalog.mark_current(context['skill'])
        context['jobs'] = Path.objects.filter(steps__skill=path).distinct()
        context['attempt'] = placement.latest_attempt(request.user, path)
    return render(request, 'learn/path.html', context)


@login_required
@require_POST
def choose_path(request, slug):
    path = get_object_or_404(Path, slug=slug, kind=Path.JOB)
    PathChoice.objects.create(user=request.user, path=path)
    log_event(request, LearningEvent.PATH_CHOSEN, path.slug)
    return redirect('home')


@login_required
@require_POST
def skip_path(request, slug):
    """Tick or untick "I already know this" on a prerequisite."""
    path = get_object_or_404(Path.objects.filter(in_jobs__prerequisite=True).distinct(), slug=slug)
    skip = request.POST.get('skip') == '1'
    if skip:
        SkippedPath.objects.get_or_create(user=request.user, path=path)
    else:
        SkippedPath.objects.filter(user=request.user, path=path).delete()
    log_event(request, LearningEvent.PATH_SKIPPED, path.slug, skipped=skip)
    next_url = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('learn:path', path.slug)


@login_required
def placement_test(request, slug):
    """A prerequisite's placement test: questions plus coding tasks. Passing marks the path as known."""
    path = get_object_or_404(Path, slug=slug, owner__isnull=True)
    if not placement.has_test(path):
        raise Http404('This path has no placement test')
    questions, tasks = placement.questions(path), placement.tasks(path)
    context = {'path': path, 'questions': questions, 'pass_mark': placement.pass_mark(path),
               'tasks': [{'task': t, 'code': t.starter, 'result': None} for t in tasks],
               'player': gamification.player_state(request.user)}
    if request.method == 'POST':
        answers = {str(q['id']): request.POST.get(f'q{q["id"]}') for q in questions}
        code = {str(t.id): request.POST.get(f'task{t.id}', '') for t in tasks}
        before = placement.latest_attempt(request.user, path)
        outcome = placement.grade(path, answers, code)
        placement.save_attempt(request.user, path, outcome, answers, code)
        log_event(request, LearningEvent.PLACEMENT, path.slug, correct=outcome['correct'], total=outcome['total'],
                  tasks_passed=outcome['tasks_passed'], tasks_total=outcome['tasks_total'], passed=outcome['passed'])
        for chapter in set(outcome['skipped_chapters']) - set(before.skipped_chapters if before else []):
            log_event(request, LearningEvent.CHAPTER_SKIPPED, chapter, reason='placement')
        by_id = {r['id']: r for r in outcome['questions']}
        for q in questions:
            q['result'] = by_id.get(q['id'])
        by_task = {r['task'].id: r for r in outcome['tasks']}
        context['tasks'] = [{'task': t, 'code': code[str(t.id)], 'result': by_task.get(t.id)} for t in tasks]
        context.update(outcome=outcome,
                       skipped_titles=list(Chapter.objects.filter(slug__in=outcome['skipped_chapters'])
                                           .order_by('course__order', 'order').values_list('title', flat=True)))
    return render(request, 'learn/placement.html', context)


@login_required
def generate_path(request):
    """Generate a skill path with AI for a topic outside the course map."""
    form = {'skill': '', 'level': 'beginner', 'hours': 5}
    context = {'levels': generator.LEVELS, 'ai_available': generator.ai_available(),
               'left_today': max(0, generator.DAILY_LIMIT - generator.generated_today(request.user)),
               'mine': Path.objects.filter(owner=request.user).order_by('-created_at'),
               'lang_groups': languages.grouped(), 'lang_hint': languages.hint_data(),
               'player': gamification.player_state(request.user)}
    if request.method == 'POST':
        form['skill'] = ' '.join(request.POST.get('skill', '').split())[:generator.MAX_SKILL_CHARS]
        form['level'] = request.POST.get('level', '')
        try:
            form['hours'] = max(1, min(40, int(request.POST.get('hours', 5))))
        except (TypeError, ValueError):
            form['hours'] = 5
        match = None if request.POST.get('anyway') else generator.catalog_match(form['skill'])
        if not form['skill']:
            context['error'] = gettext('Write the skill you want to learn.')
        elif form['level'] not in generator.LEVELS:
            context['error'] = gettext('Pick a level.')
        elif not context['ai_available']:
            context['error'] = gettext('AI generation is not set up on this server yet. Add GEMINI_API_KEY to the .env file.')
        elif not context['left_today']:
            context['error'] = gettext('You have generated the most paths allowed today. Try again tomorrow.')
        elif match:
            context['match'] = match
        else:
            request_data = {'skill': form['skill'], 'level': form['level'], 'hours_per_week': form['hours'],
                            'language': 'ar' if get_language() == 'ar' else 'en'}
            try:
                data = generator.generate(form['skill'], form['level'], form['hours'], request_data['language'])
            except Exception as exc:  # unreachable AI, a blocked network or an unusable reply: say so, save nothing
                context['error'] = generator.friendly_error(exc)
            else:
                path = generator.save_path(request.user, data, request_data)
                log_event(request, LearningEvent.PATH_GENERATED, path.slug, skill=form['skill'],
                          level=form['level'], hours_per_week=form['hours'])
                return redirect('learn:path', path.slug)
    context['form'] = form
    return render(request, 'learn/generate.html', context)


@login_required
@require_POST
def delete_path(request, slug):
    get_object_or_404(Path, slug=slug, owner=request.user).delete()
    return redirect('learn:generate')


def lesson_html(text):
    """Markdown from the AI as HTML, with raw HTML shown as text and only web links kept."""
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'sane_lists'])
    md.preprocessors.deregister('html_block')
    for pattern in ('html', 'image_link', 'image_reference'):
        md.inlinePatterns.deregister(pattern)
    html = md.convert(text)
    return re.sub(r'href="(?!https?://)[^"]*"', 'href="#"', html)


QUIZ_PASS_SHARE = 2 / 3  # a generated chapter is finished with two thirds of its quiz right


def chapter_detail(request, slug, chapter):
    """A generated chapter: lesson, slides and quiz. Passing the quiz finishes the chapter."""
    path = get_object_or_404(_visible_paths(request.user), slug=slug)
    chapter = get_object_or_404(Chapter, course__path=path, slug=chapter)
    if not chapter.content:
        raise Http404('This chapter has no lesson yet')
    quiz = chapter.content.get('quiz', [])
    chapters = list(Chapter.objects.filter(course__path=path).order_by('course__order', 'order'))
    index = chapters.index(chapter)
    progress = None
    if request.user.is_authenticated:
        progress = ChapterProgress.objects.filter(user=request.user, chapter=chapter).first()
    context = {
        'path': path, 'chapter': chapter, 'lesson': lesson_html(chapter.content.get('lesson', '')),
        'slides': chapter.content.get('slides', []), 'quiz': quiz, 'progress': progress,
        'mind_map': chapter.content.get('mind_map', ''),
        'previous': chapters[index - 1] if index > 0 else None,
        'next': chapters[index + 1] if index + 1 < len(chapters) else None,
        'number': index + 1, 'count': len(chapters), 'pass_needed': math.ceil(QUIZ_PASS_SHARE * len(quiz)),
        'player': gamification.player_state(request.user),
        'tutor_topic': tutor.chapter_topic(chapter), 'tutor_backend': tutor.backend_label(),
        'tutor_history': _chat_history(request.user, tutor.chapter_topic(chapter)) if request.user.is_authenticated else [],
        'can_run': _can_run(request),
        'deck_added': request.user.is_authenticated and CardReview.objects.filter(
            user=request.user, card__chapter=chapter).exists(),
    }
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f'{reverse("login")}?next={request.path}')
        results = []
        for i, question in enumerate(quiz):
            try:
                chosen = int(request.POST.get(f'q{i}', ''))
            except ValueError:
                chosen = None
            results.append({'chosen': chosen, 'right': chosen == question['answer']})
        correct = sum(r['right'] for r in results)
        progress, _created = ChapterProgress.objects.get_or_create(user=request.user, chapter=chapter)
        finished_before = progress.done
        progress.quiz_correct = max(progress.quiz_correct, correct)
        progress.quiz_total = len(quiz)
        progress.done = progress.done or correct >= context['pass_needed']
        progress.save()
        log_event(request, LearningEvent.QUIZ, chapter.slug, _seconds_spent(request.POST), correct=correct, total=len(quiz))
        if progress.done and not finished_before:
            log_event(request, LearningEvent.LESSON_FINISHED, chapter.slug)
        context.update(progress=progress, correct=correct,
                       quiz=[dict(q, result=r) for q, r in zip(quiz, results)], checked=True,
                       just_finished=progress.done and not finished_before)
    context['skill'] = catalog.skill_view(path, catalog.exercise_states(request.user), catalog.skipped_ids(request.user),
                                          marks=catalog.chapter_marks(request.user))
    return render(request, 'learn/chapter.html', context)


def supported_languages(request):
    """What learners can practise in each language, from learn/languages.py."""
    return render(request, 'learn/languages.html', {
        'lang_groups': languages.grouped(), 'player': gamification.player_state(request.user),
    })


def _deck_chapter(request, chapter):
    chapter = get_object_or_404(Chapter.objects.select_related('course__path'), slug=chapter)
    if chapter.course.path.owner_id not in (None, request.user.id):
        raise Http404('No such chapter')
    return chapter


def _back_to(request, fallback):
    target = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return fallback


@login_required
def flashcards_page(request):
    """Today's queue, the learner's decks, and chapters they can add."""
    due = flashcards.due_count(request.user)
    return render(request, 'learn/flashcards.html', {
        'due': due, 'next_due': None if due else flashcards.next_due(request.user),
        'reviewed_today': flashcards.reviewed_today(request.user),
        'decks': flashcards.decks(request.user), 'choices': flashcards.deck_choices(request.user),
        'added': request.GET.get('added'), 'error': request.session.pop('deck_error', ''),
        'player': gamification.player_state(request.user),
    })


@login_required
@require_POST
def flashcards_add(request, chapter):
    chapter = _deck_chapter(request, chapter)
    try:
        count, written = flashcards.add_deck(request.user, chapter)
    except flashcards.DeckError as exc:
        request.session['deck_error'] = str(exc)
        return redirect(f'{reverse("learn:flashcards")}#add')
    log_event(request, LearningEvent.CARDS_ADDED, chapter.slug, cards=count, written=written)
    return redirect(_back_to(request, f'{reverse("learn:flashcards")}?added={chapter.slug}'))


@login_required
@require_POST
def flashcards_remove(request, chapter):
    flashcards.remove_deck(request.user, _deck_chapter(request, chapter))
    return redirect(f'{reverse("learn:flashcards")}#decks')


@login_required
@require_POST
def flashcards_run(request):
    """Run the code in a Python flashcard's code box and say whether it prints what the card expects."""
    data = json.loads(request.body or '{}')
    review = get_object_or_404(CardReview.objects.select_related('card'), user=request.user, id=data.get('review') or 0)
    card = review.card
    if card.language != 'python':
        return JsonResponse({'error': 'Only Python cards run on the server.'}, status=400)
    code = str(data.get('code', ''))[:5000]
    if flashcards.BLANK in code:
        return JsonResponse({'status': 'error', 'output': '',
                             'error': gettext('Fill in the ____ first, then run the code.')})
    result = run_snippet(code)
    output = result.get('output', '')
    return JsonResponse({
        'status': result.get('status'), 'output': output, 'error': result.get('error'),
        'correct': bool(card.expected) and result.get('status') == 'ok' and output.rstrip() == card.expected.rstrip(),
    })


@login_required
def flashcards_review(request):
    """One due card at a time: think of the answer, show it, then say how it went."""
    if request.method == 'POST':
        review = get_object_or_404(CardReview, user=request.user, id=request.POST.get('review') or 0)
        rating = request.POST.get('rating')
        if rating in flashcards.RATINGS and review.due_at <= timezone.now():
            flashcards.schedule(review, rating)
            log_event(request, LearningEvent.CARD_REVIEWED, review.card.chapter.slug,
                      _seconds_spent(request.POST), rating=rating, box=review.box)
            rewards = gamification.Rewards(request.user)
            rewards.daily()
            if not flashcards.due_reviews(request.user).exists():
                rewards.award(f'cards:{timezone.localdate().isoformat()}', flashcards.REVIEW_XP, 'Flashcard review')
        return redirect('learn:flashcards_review')
    queue = flashcards.due_reviews(request.user)
    review = queue.first()
    context = {'review': review, 'left': queue.count(), 'player': gamification.player_state(request.user),
               'reviewed_today': flashcards.reviewed_today(request.user)}
    if review:
        card = review.card
        context.update(card=card, front=flashcards.card_html(card.front), back=flashcards.card_html(card.back),
                       card_dir='rtl' if flashcards.chapter_language(card.chapter) == 'ar' else 'ltr',
                       run_mode=flashcards.RUNNABLE.get(card.language, ''),
                       code_rows=min(max(card.code.count('\n') + 2, 3), 14),
                       tutor_topic=tutor.FLASHCARD_TOPIC, tutor_backend=tutor.backend_label(),
                       tutor_history=_chat_history(request.user, tutor.FLASHCARD_TOPIC), can_run=_can_run(request),
                       good_days=flashcards.days_after(review, flashcards.GOOD),
                       easy_days=flashcards.days_after(review, flashcards.EASY))
    else:
        context['next_due'] = flashcards.next_due(request.user)
        context['xp'] = flashcards.REVIEW_XP if XPEvent.objects.filter(
            user=request.user, key=f'cards:{timezone.localdate().isoformat()}').exists() else 0
    return render(request, 'learn/review.html', context)


def coming_soon(request, section):
    """Sections from the plan that aren't built yet show what will appear there."""
    return render(request, 'learn/coming_soon.html', {
        'section': section, 'player': gamification.player_state(request.user),
    })


MILESTONE_XP = 20  # first time each milestone of the learner's own project is ticked off


def _project_or_404(request, project_id):
    if not request.user.is_authenticated:
        raise Http404('Log in to see your projects')
    return get_object_or_404(Project, id=project_id, user=request.user)


@login_required
def project_home(request):
    """The learner's projects, and the two ways to start one: describe it, or upload an SRS."""
    mine = list(Project.objects.filter(user=request.user))
    form = {'title': '', 'what': '', 'who': '', 'tech': ''}
    context = {'ai_available': generator.ai_available(),
               'left_today': max(0, projects.DAILY_LIMIT - projects.written_today(request.user)),
               'mode': 'upload' if request.GET.get('mode') == 'upload' else 'describe',
               'player': gamification.player_state(request.user)}
    if request.method == 'POST':
        mode = 'upload' if request.POST.get('mode') == 'upload' else 'describe'
        context['mode'] = mode
        for key in form:
            form[key] = request.POST.get(key, '').strip()[:projects.MAX_FIELD_CHARS]
        language = 'ar' if get_language() == 'ar' else 'en'
        prompt, brief, error = None, {}, ''
        if not context['ai_available']:
            error = gettext('AI is not set up on this server yet. Add GEMINI_API_KEY to the .env file.')
        elif not context['left_today']:
            error = gettext('You have written the most SRS documents allowed today. Try again tomorrow.')
        elif mode == 'describe':
            if len(form['what']) < 20:
                error = gettext('Describe what your project does in a sentence or two.')
            else:
                brief = dict(form)
                prompt = projects.describe_prompt(brief)
        else:
            upload = request.FILES.get('srs')
            if not upload:
                error = gettext('Choose your SRS file first.')
            else:
                try:
                    text = projects.read_upload(upload)
                except projects.UploadError as exc:
                    error = str(exc)
                else:
                    brief = {'file': upload.name[:120]}
                    prompt = projects.upload_prompt(text, upload.name)
        if prompt:
            source = Project.UPLOADED if mode == 'upload' else Project.DESCRIBED
            try:
                srs = projects.write_srs(request.user, source, prompt, language)
            except Exception as exc:  # unreachable AI, a blocked network or an unusable reply: say so, save nothing
                error = generator.friendly_error(exc)
            else:
                project = Project.objects.create(user=request.user, title=form['title'][:120] or srs['title'],
                                                 source=source, brief=brief, srs=srs, language=language)
                log_event(request, LearningEvent.PROJECT_SRS, '', source=source, gaps=len(srs['gaps']))
                return redirect('learn:project_detail', project.id)
        context['error'] = error
    context.update(form=form, mine=[(p, projects.progress(p)) for p in mine])
    return render(request, 'learn/projects.html', context)


@login_required
def project_detail(request, project_id):
    """The SRS and its milestone walkthrough, with the tutor that knows the project."""
    project = _project_or_404(request, project_id)
    topic = tutor.project_topic(project)
    return render(request, 'learn/project.html', {
        'project': project, 'srs': project.srs, 'milestones': projects.milestones(project),
        'progress': projects.progress(project), 'srs_dir': 'rtl' if project.language == 'ar' else 'ltr',
        'updated': request.GET.get('updated'), 'error': request.session.pop('project_error', ''),
        'ai_available': generator.ai_available(),
        'player': gamification.player_state(request.user),
        'tutor_topic': topic, 'tutor_backend': tutor.backend_label(),
        'tutor_history': _chat_history(request.user, topic), 'can_run': _can_run(request),
    })


@login_required
@require_POST
def project_check(request, project_id):
    """Tick or untick one task of the walkthrough."""
    project = _project_or_404(request, project_id)
    data = json.loads(request.body or '{}')
    if not projects.toggle(project, str(data.get('task', '')), bool(data.get('done'))):
        return JsonResponse({'error': 'Unknown task.'}, status=400)
    rewards = gamification.Rewards(request.user)
    for milestone in projects.milestones(project):
        if milestone['finished']:
            rewards.award(f'project:{project.id}:{milestone["id"]}', MILESTONE_XP, 'Project milestone')
    return JsonResponse({'progress': projects.progress(project),
                         'finished': [m['id'] for m in projects.milestones(project) if m['finished']]})


@login_required
@require_POST
def project_update(request, project_id):
    """Work the learner's answers to the gaps (or any new details) into the SRS."""
    project = _project_or_404(request, project_id)
    answers = request.POST.get('answers', '').strip()[:projects.MAX_FIELD_CHARS * 2]
    url = reverse('learn:project_detail', args=[project.id])
    if not answers:
        request.session['project_error'] = gettext('Write your answers or new details first.')
        return redirect(f'{url}#gaps')
    if projects.written_today(request.user) >= projects.DAILY_LIMIT:
        request.session['project_error'] = gettext('You have written the most SRS documents allowed today. Try again tomorrow.')
        return redirect(f'{url}#gaps')
    try:
        srs = projects.write_srs(request.user, project.source, projects.update_prompt(project, answers), project.language)
    except Exception as exc:
        request.session['project_error'] = generator.friendly_error(exc)
        return redirect(f'{url}#gaps')
    project.done = projects.carry_ticks(project.srs, project.done, srs)
    project.srs = srs
    project.save()
    log_event(request, LearningEvent.PROJECT_SRS, '', source='update', gaps=len(srs['gaps']))
    return redirect(f'{url}?updated=1')


@login_required
@require_POST
def project_delete(request, project_id):
    project = _project_or_404(request, project_id)
    TutorMessage.objects.filter(user=request.user, topic=tutor.project_topic(project)).delete()
    project.delete()
    return redirect('learn:project')


@login_required
def exercise_detail(request, slug):
    exercise = _exercise_or_404(slug)
    exercises = load_exercises()
    index = exercises.index(exercise)
    progress = ExerciseProgress.objects.filter(user=request.user, slug=slug).first()
    public_quiz = [{'question': q['question'], 'options': q['options']} for q in exercise.quiz]
    return render(request, 'learn/exercise.html', {
        'exercise': exercise,
        'progress': progress,
        'code': progress.code if progress and progress.code else exercise.starter,
        'starter': exercise.starter,
        'quiz': public_quiz,
        'previous': exercises[index - 1] if index > 0 else None,
        'next': exercises[index + 1] if index + 1 < len(exercises) else None,
        'can_run': _can_run(request),
        'player': gamification.player_state(request.user),
        'rewards': gamification.exercise_rewards(exercise),
        'quiz_taken': XPEvent.objects.filter(user=request.user, key=f'quiz:{slug}').exists(),
        'tutor_history': _chat_history(request.user, slug),
        'tutor_backend': tutor.backend_label(),
        'tests': list_tests(exercise),
        'has_slides': _slides_path(exercise).exists(),
    })


@require_POST
def run(request, slug):
    exercise = _exercise_or_404(slug)
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to run code.'}, status=403)
    data = json.loads(request.body or '{}')
    code = data.get('code', '')
    test_id = data.get('test')
    if test_id and test_id not in {t['id'] for t in list_tests(exercise)}:
        return JsonResponse({'error': 'Unknown test.'}, status=400)
    result = run_tests(exercise, code, test_id)
    seconds = _seconds_spent(data)

    progress, _ = ExerciseProgress.objects.get_or_create(user=request.user, slug=slug)
    progress.code = code
    progress.attempts += 1  # single-test runs count too, so the first-try bonus stays honest
    if test_id:
        # Running one test is for checking your work: it saves the code but
        # doesn't complete the exercise or pay XP. A full run does that.
        progress.save()
        log_event(request, LearningEvent.TEST_RUN, slug, seconds, test=test_id, passed=result['all_passed'])
        result['single'] = True
        return JsonResponse(result)
    passed_before = progress.passed
    progress.tests_passed = result['passed']
    progress.tests_total = result['total']
    progress.passed = progress.passed or result['all_passed']
    progress.save()
    log_event(request, LearningEvent.RUN, slug, seconds, status=result['status'],
              passed=result['passed'], total=result['total'], all_passed=result['all_passed'], attempt=progress.attempts)
    if progress.passed and not passed_before:
        log_event(request, LearningEvent.PASSED, slug, seconds, attempts=progress.attempts,
                  solution_viewed=progress.solution_viewed)
    result['xp'] = gamification.reward_run(request.user, exercise, progress, result)
    return JsonResponse(result)


@require_POST
def run_code_selection(request, slug):
    exercise = _exercise_or_404(slug)
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to run code.'}, status=403)
    data = json.loads(request.body or '{}')
    text = str(data.get('selection', ''))
    if not text.strip():
        return JsonResponse({'error': 'Select some code to run first.'}, status=400)
    try:
        start_line, end_line = int(data.get('start_line', 1)), int(data.get('end_line', 1))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid line numbers.'}, status=400)
    result = run_selection(exercise, str(data.get('code', '')), text, start_line, end_line)
    log_event(request, LearningEvent.SELECTION_RUN, slug, _seconds_spent(data), status=result['status'])
    return JsonResponse(result)


def _slides_path(exercise):
    return FilePath(settings.BASE_DIR) / 'materials' / 'out' / 'pdf' / f'{exercise.path.name}.pdf'


@login_required
def slides(request, slug):
    """The exercise's slide deck as a PDF (built by materials/export_pdfs.py)."""
    path = _slides_path(_exercise_or_404(slug))
    if not path.exists():
        raise Http404('No slides for this exercise yet')
    return FileResponse(path.open('rb'), content_type='application/pdf', filename=path.name)


@login_required
@require_POST
def quiz(request, slug):
    exercise = _exercise_or_404(slug)
    data = json.loads(request.body or '{}')
    answers = data.get('answers', [])
    results = []
    for i, question in enumerate(exercise.quiz):
        chosen = answers[i] if i < len(answers) else None
        results.append({
            'correct': chosen == question['answer'],
            'answer': question['answer'],
            'explanation': question.get('explanation', ''),
        })
    correct = sum(r['correct'] for r in results)
    progress, _ = ExerciseProgress.objects.get_or_create(user=request.user, slug=slug)
    progress.quiz_correct = max(correct, progress.quiz_correct or 0)
    progress.quiz_total = len(results)
    progress.save()
    log_event(request, LearningEvent.QUIZ, slug, _seconds_spent(data), correct=correct, total=len(results))
    xp = gamification.reward_quiz(request.user, exercise, correct, len(results))
    return JsonResponse({'results': results, 'correct': correct, 'total': len(results), 'xp': xp})


@login_required
@require_POST
def solution(request, slug):
    exercise = _exercise_or_404(slug)
    progress, _ = ExerciseProgress.objects.get_or_create(user=request.user, slug=slug)
    if not progress.passed and not progress.solution_viewed:
        # Peeking before passing forfeits this exercise's no-peek bonus.
        progress.solution_viewed = True
        progress.save(update_fields=['solution_viewed', 'updated_at'])
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        data = {}
    log_event(request, LearningEvent.SOLUTION_VIEWED, slug, _seconds_spent(data), passed=progress.passed)
    return JsonResponse({'solution': exercise.solution})


def _chat_history(user, topic):
    return [{'role': m.role, 'text': m.display} for m in TutorMessage.objects.filter(user=user, topic=topic)]


def _topic_target(request, topic):
    """What a tutor topic refers to: (exercise, chapter), both None for the general tutor."""
    if topic in (tutor.GENERAL_TOPIC, tutor.FLASHCARD_TOPIC):
        return None, None
    if tutor.project_id(topic) is not None:
        _project_or_404(request, tutor.project_id(topic))
        return None, None
    chapter_id = tutor.chapter_id(topic)
    if chapter_id is not None:
        chapter = get_object_or_404(Chapter.objects.select_related('course__path'), id=chapter_id,
                                    course__path__in=_visible_paths(request.user))
        if not chapter.content:
            raise Http404('This chapter has no lesson yet')
        return None, chapter
    return _exercise_or_404(topic), None


@login_required
def tutor_page(request):
    return render(request, 'learn/tutor.html', {
        'player': gamification.player_state(request.user),
        'tutor_history': _chat_history(request.user, tutor.GENERAL_TOPIC),
        'tutor_backend': tutor.backend_label(),
        'can_run': _can_run(request),
    })


@require_POST
def tutor_ask(request, topic):
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to use the tutor.'}, status=403)
    exercise, chapter = _topic_target(request, topic)
    data = json.loads(request.body or '{}')
    question = str(data.get('question', '')).strip()[:tutor.MAX_QUESTION_CHARS]
    if not question:
        return JsonResponse({'error': 'Ask a question first.'}, status=400)

    progress = ExerciseProgress.objects.filter(user=request.user, slug=topic).first() if exercise else None
    if topic == tutor.FLASHCARD_TOPIC:
        review = CardReview.objects.filter(user=request.user, id=data.get('review') or 0).select_related(
            'card__chapter').first()
        turn = tutor.build_card_turn(question, review.card, data.get('code'), data.get('output'),
                                     bool(data.get('revealed'))) if review else question
    else:
        turn = tutor.build_learner_turn(
            question, exercise=exercise, code=data.get('code'), result=data.get('result'), progress=progress,
        )
    history = list(TutorMessage.objects.filter(user=request.user, topic=topic).order_by('-created_at', '-id')[:tutor.MAX_HISTORY])[::-1]
    while history and history[0].role != 'user':  # the conversation must start with the learner
        history.pop(0)
    messages = [{'role': m.role, 'content': m.content, 'display': m.display} for m in history]
    messages.append({'role': 'user', 'content': turn})
    project = _project_or_404(request, tutor.project_id(topic)) if tutor.project_id(topic) is not None else None
    system = tutor.build_system(exercise, chapter, flashcards=topic == tutor.FLASHCARD_TOPIC, project=project)
    user = request.user
    if exercise:
        log_event(request, LearningEvent.HINT, topic, _seconds_spent(data))
    elif chapter:
        log_event(request, LearningEvent.HINT, chapter.slug, _seconds_spent(data), chapter=True)

    def events():
        # One JSON object per line: {"type": "text" | "done" | "error", ...}
        chunks, final = [], None
        try:
            for kind, value in tutor.stream_reply(system, messages):
                if kind == 'text':
                    chunks.append(value)
                    yield json.dumps({'type': 'text', 'text': value}) + '\n'
                elif kind == 'notice':  # e.g. "Gemini answered instead"
                    yield json.dumps({'type': 'notice', 'text': value}) + '\n'
                else:
                    final = value
        except Exception as exc:  # any SDK or network failure becomes a chat message
            yield json.dumps({'type': 'error', 'error': tutor.friendly_error(exc)}) + '\n'
            return

        if final is None:
            yield json.dumps({'type': 'error', 'error': 'The answer stopped unexpectedly. Please try again.'}) + '\n'
            return
        if final.stop_reason == 'refusal':
            yield json.dumps({'type': 'error', 'discard': True,
                              'error': "The tutor can't help with that request. Try rephrasing your question."}) + '\n'
            return
        answer = ''.join(chunks)
        if final.stop_reason == 'max_tokens':
            answer += '\n\n*(The answer was cut off because it got too long. Ask me to continue.)*'
        TutorMessage.objects.create(user=user, topic=topic, role='user', content=turn, display=question)
        TutorMessage.objects.create(user=user, topic=topic, role='assistant', content=answer, display=answer)
        yield json.dumps({'type': 'done', 'text': answer}) + '\n'

    response = StreamingHttpResponse(events(), content_type='application/x-ndjson')
    response['Cache-Control'] = 'no-cache'
    return response


@login_required
@require_POST
def tutor_clear(request, topic):
    _topic_target(request, topic)
    TutorMessage.objects.filter(user=request.user, topic=topic).delete()
    return JsonResponse({'cleared': True})


@login_required
def notebook_page(request):
    progress = {p.slug: p for p in ExerciseProgress.objects.filter(user=request.user)}
    entries = {e.slug: e for e in NotebookEntry.objects.filter(user=request.user)}
    pages, data = [], []
    for exercise in load_exercises():
        p = progress.get(exercise.slug)
        entry = entries.get(exercise.slug)
        passed = bool(p and p.passed)
        pages.append({'exercise': exercise, 'passed': passed})
        data.append({
            'slug': exercise.slug,
            'number': exercise.number,
            'title': exercise.title,
            'url': reverse('learn:exercise', args=[exercise.slug]),
            'generate_url': reverse('learn:notebook_generate', args=[exercise.slug]),
            'passed': passed,
            'code': p.code if passed else '',
            'tools': notebook.lesson_tools(exercise),
            'data': entry.data if entry else None,
            'updated': date_format(timezone.localtime(entry.updated_at), 'M j, H:i') if entry else '',
        })
    return render(request, 'learn/notebook.html', {
        'pages': pages,
        'notebook_data': data,
        'passed_count': sum(1 for page in pages if page['passed']),
        'player': gamification.player_state(request.user),
        'can_run': _can_run(request),
    })


@require_POST
def notebook_generate(request, slug):
    exercise = _exercise_or_404(slug)
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to use the notebook.'}, status=403)
    if not ExerciseProgress.objects.filter(user=request.user, slug=slug, passed=True).exists():
        return JsonResponse({'error': 'Pass this exercise first, then it can go in your notebook.'}, status=400)
    try:
        page = notebook.generate_page(request.user, exercise)
    except Exception as exc:  # SDK, CLI or JSON problems all become a readable message
        return JsonResponse({'error': tutor.friendly_error(exc)}, status=502)
    entry, _ = NotebookEntry.objects.update_or_create(user=request.user, slug=slug, defaults={'data': page})
    return JsonResponse({'page': entry.data})
