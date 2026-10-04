import json
from itertools import groupby
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from . import gamification, notebook, tutor
from .exercises import get_exercise, list_tests, load_exercises, run_selection, run_tests
from .models import ExerciseProgress, NotebookEntry, TutorMessage, XPEvent

LOCAL_ADDRESSES = {'127.0.0.1', '::1', 'localhost'}
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
    # only allow it from this machine or for a logged-in staff account, which is
    # how the site owner uses it on a public server.
    if request.META.get('REMOTE_ADDR') in LOCAL_ADDRESSES and not settings.LEARN_REQUIRE_LOGIN:
        return True
    return bool(request.user.is_authenticated and request.user.is_staff)


def dashboard(request):
    exercises = load_exercises()
    progress = {p.slug: p for p in ExerciseProgress.objects.all()}
    earned = gamification.xp_by_exercise()
    for exercise in exercises:
        exercise.progress = progress.get(exercise.slug)
        exercise.xp_earned = earned.get(exercise.slug, 0)
        exercise.xp_max = sum(gamification.exercise_rewards(exercise).values())
    weeks = [
        {'number': week, 'title': WEEK_TITLES.get(week, ''), 'exercises': list(items)}
        for week, items in groupby(exercises, key=lambda e: e.week)
    ]
    done = sum(1 for p in progress.values() if p.passed)
    earned_badges = gamification.earned_badge_ids()
    return render(request, 'learn/dashboard.html', {
        'weeks': weeks,
        'done': done,
        'total': len(exercises),
        'percent': round(100 * done / len(exercises)) if exercises else 0,
        'player': gamification.player_state(),
        'badges': [{'badge': b, 'earned': b.id in earned_badges} for b in gamification.BADGES],
        'badges_earned': len(earned_badges),
        'recent_xp': XPEvent.objects.filter(amount__gt=0)[:8],
    })


def exercise_detail(request, slug):
    exercise = _exercise_or_404(slug)
    exercises = load_exercises()
    index = exercises.index(exercise)
    progress = ExerciseProgress.objects.filter(slug=slug).first()
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
        'player': gamification.player_state(),
        'rewards': gamification.exercise_rewards(exercise),
        'quiz_taken': XPEvent.objects.filter(key=f'quiz:{slug}').exists(),
        'tutor_history': _chat_history(slug),
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

    progress, _ = ExerciseProgress.objects.get_or_create(slug=slug)
    progress.code = code
    progress.attempts += 1  # single-test runs count too, so the first-try bonus stays honest
    if test_id:
        # Running one test is for checking your work: it saves the code but
        # doesn't complete the exercise or pay XP. A full run does that.
        progress.save()
        result['single'] = True
        return JsonResponse(result)
    progress.tests_passed = result['passed']
    progress.tests_total = result['total']
    progress.passed = progress.passed or result['all_passed']
    progress.save()
    result['xp'] = gamification.reward_run(exercise, progress, result)
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
    return JsonResponse(result)


def _slides_path(exercise):
    return Path(settings.BASE_DIR) / 'materials' / 'out' / 'pdf' / f'{exercise.path.name}.pdf'


def slides(request, slug):
    """The exercise's slide deck as a PDF (built by materials/export_pdfs.py)."""
    path = _slides_path(_exercise_or_404(slug))
    if not path.exists():
        raise Http404('No slides for this exercise yet')
    return FileResponse(path.open('rb'), content_type='application/pdf', filename=path.name)


@require_POST
def quiz(request, slug):
    exercise = _exercise_or_404(slug)
    answers = json.loads(request.body or '{}').get('answers', [])
    results = []
    for i, question in enumerate(exercise.quiz):
        chosen = answers[i] if i < len(answers) else None
        results.append({
            'correct': chosen == question['answer'],
            'answer': question['answer'],
            'explanation': question.get('explanation', ''),
        })
    correct = sum(r['correct'] for r in results)
    progress, _ = ExerciseProgress.objects.get_or_create(slug=slug)
    progress.quiz_correct = max(correct, progress.quiz_correct or 0)
    progress.quiz_total = len(results)
    progress.save()
    xp = gamification.reward_quiz(exercise, correct, len(results))
    return JsonResponse({'results': results, 'correct': correct, 'total': len(results), 'xp': xp})


@require_POST
def solution(request, slug):
    exercise = _exercise_or_404(slug)
    progress, _ = ExerciseProgress.objects.get_or_create(slug=slug)
    if not progress.passed and not progress.solution_viewed:
        # Peeking before passing forfeits this exercise's no-peek bonus.
        progress.solution_viewed = True
        progress.save(update_fields=['solution_viewed', 'updated_at'])
    return JsonResponse({'solution': exercise.solution})


def _chat_history(topic):
    return [{'role': m.role, 'text': m.display} for m in TutorMessage.objects.filter(topic=topic)]


def _topic_exercise(topic):
    """The exercise a tutor topic refers to, or None for the general tutor."""
    return None if topic == tutor.GENERAL_TOPIC else _exercise_or_404(topic)


def tutor_page(request):
    return render(request, 'learn/tutor.html', {
        'player': gamification.player_state(),
        'tutor_history': _chat_history(tutor.GENERAL_TOPIC),
        'tutor_backend': tutor.backend_label(),
        'can_run': _can_run(request),
    })


@require_POST
def tutor_ask(request, topic):
    exercise = _topic_exercise(topic)
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to use the tutor.'}, status=403)
    data = json.loads(request.body or '{}')
    question = str(data.get('question', '')).strip()[:tutor.MAX_QUESTION_CHARS]
    if not question:
        return JsonResponse({'error': 'Ask a question first.'}, status=400)

    progress = ExerciseProgress.objects.filter(slug=topic).first() if exercise else None
    turn = tutor.build_learner_turn(
        question, exercise=exercise, code=data.get('code'), result=data.get('result'), progress=progress,
    )
    history = list(TutorMessage.objects.filter(topic=topic).order_by('-created_at', '-id')[:tutor.MAX_HISTORY])[::-1]
    while history and history[0].role != 'user':  # the conversation must start with the learner
        history.pop(0)
    messages = [{'role': m.role, 'content': m.content, 'display': m.display} for m in history]
    messages.append({'role': 'user', 'content': turn})
    system = tutor.build_system(exercise)

    def events():
        # One JSON object per line: {"type": "text" | "done" | "error", ...}
        chunks, final = [], None
        try:
            for kind, value in tutor.stream_reply(system, messages):
                if kind == 'text':
                    chunks.append(value)
                    yield json.dumps({'type': 'text', 'text': value}) + '\n'
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
        TutorMessage.objects.create(topic=topic, role='user', content=turn, display=question)
        TutorMessage.objects.create(topic=topic, role='assistant', content=answer, display=answer)
        yield json.dumps({'type': 'done', 'text': answer}) + '\n'

    response = StreamingHttpResponse(events(), content_type='application/x-ndjson')
    response['Cache-Control'] = 'no-cache'
    return response


@require_POST
def tutor_clear(request, topic):
    _topic_exercise(topic)
    TutorMessage.objects.filter(topic=topic).delete()
    return JsonResponse({'cleared': True})


def notebook_page(request):
    progress = {p.slug: p for p in ExerciseProgress.objects.all()}
    entries = {e.slug: e for e in NotebookEntry.objects.all()}
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
        'player': gamification.player_state(),
        'can_run': _can_run(request),
    })


@require_POST
def notebook_generate(request, slug):
    exercise = _exercise_or_404(slug)
    if not _can_run(request):
        return JsonResponse({'error': 'Log in to use the notebook.'}, status=403)
    if not ExerciseProgress.objects.filter(slug=slug, passed=True).exists():
        return JsonResponse({'error': 'Pass this exercise first, then it can go in your notebook.'}, status=400)
    try:
        page = notebook.generate_page(exercise)
    except Exception as exc:  # SDK, CLI or JSON problems all become a readable message
        return JsonResponse({'error': tutor.friendly_error(exc)}, status=502)
    entry, _ = NotebookEntry.objects.update_or_create(slug=slug, defaults={'data': page})
    return JsonResponse({'page': entry.data})
