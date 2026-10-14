"""Hands-on exercises inside AI-generated chapters.

Gemini writes each chapter's exercise along with its lesson: instructions,
starter code, a reference solution and tests. An exercise is only shown when
its own solution passes every test and the starter does not, so learners never
meet a broken or already-solved task.

    Python                  checked on the server with the Python runner, right after the path is generated.
    HTML, CSS, JavaScript,  checked in the path owner's browser with the browser runner the first time
    React, Tailwind         they open the path (the server can't lay out a page); the result is sent back.

The exercise lives in Chapter.content['exercise'] with a status: 'pending', 'ok'
or 'broken'. Once it is 'ok', its slug (the chapter slug plus its suffix) goes in
Chapter.exercises, so progress, XP, the tutor and the exercise pages treat it
like a featured exercise.

"Check the AI" exercises (Chapter.content['check_ai']) work the same way: the
starter is code an AI assistant "wrote" with one planted flaw, the solution is
the fixed code, and the same check proves the flaw is real (the tests fail on
it) and fixable (the fix passes them).
"""
from django.utils.translation import gettext
import re
from dataclasses import dataclass, field

from . import web_exercises
from .exercises import Exercise, list_tests, run_tests
from .web_exercises import WebExercise

EXERCISE, CHECK_AI = 'exercise', 'check_ai'   # keys in Chapter.content
SUFFIXES = {EXERCISE: '-ex', CHECK_AI: '-check'}
SUFFIX = SUFFIXES[EXERCISE]
FLAW_KINDS = ('bug', 'edge_case', 'security', 'design')
PENDING, OK, BROKEN = 'pending', 'ok', 'broken'
PYTHON_FILE = 'exercise.py'
WEB_LANGUAGES = {'html', 'css', 'javascript', 'react', 'tailwind'}
LANGUAGES = WEB_LANGUAGES | {'python'}
LIBS = {'react': ['react'], 'tailwind': ['tailwind']}  # extra libraries the browser runner loads
MAX_CODE_CHARS = 8000

PROMPT = """

Hands-on exercise (add "exercise" to a chapter when its idea can be practised in code):
"exercise": {
  "language": "python" | "html" | "css" | "javascript" | "react" | "tailwind",
  "title": "short task title",
  "instructions": "Markdown, 60 to 200 words: what to build and what the tests check. No solution code.",
  "hints": ["2 or 3 short hints that lead to the answer without giving it"],
  ... then, for python:
  "starter": "exercise.py with the function or class to complete (signatures and TODO comments, no working logic)",
  "solution": "the complete exercise.py",
  "tests": "unittest code: import unittest, from exercise import ..., one TestCase class, 3 to 5 methods \
named test_01_..., test_02_..., each with a one-line docstring that says what it checks in {language}"
  ... or, for the browser languages:
  "files": ["index.html", "style.css", "script.js"] (only the ones the task needs; always index.html),
  "starter": {"index.html": "...", ...}, "solution": {"index.html": "...", ...} (same file names),
  "tests": [{"id": "short-id", "description": "what it checks, in {language}"}],
  "tests_js": "test('short-id', async () => { ... }); one call per test id"
}
Exercise rules:
- Use it only for python, html, css, javascript, react or tailwind. For anything else (SQL, Django \
settings, PHP, mobile, C#) leave "exercise" out: those chapters stay reading and quizzes.
- Python: plain Python 3 with the standard library only; no input(), files, network or Django.
- The solution must pass every test and the starter must fail at least one. Tests check behaviour, \
not exact wording or formatting the instructions don't ask for.
- tests_js runs in the page after it loads, with these helpers: test(id, fn), expect(x).toBe(y), \
.toEqual(y), .toContain(y), .toBeTruthy(), .toBeAtLeast(n), await waitFor(() => condition), \
$(selector), $$(selector) (an array) and css(element, 'property') (the computed value, colours as rgb()). \
No other libraries, no network: fetch() is not available.
- react: React 18 and ReactDOM are globals (no imports or exports). script.js holds JSX and ends with \
ReactDOM.createRoot(document.getElementById('root')).render(<App />); index.html has <div id="root"></div>. \
Tests wait for rendering with waitFor and click with element.click().
- tailwind: the page loads Tailwind CSS v4, so index.html uses utility classes (no style.css). \
Tests check computed styles, for example css($('h1'), 'font-weight') is '700'.
- Starter code should run without errors and leave clear TODO comments.

Check the AI (add "check_ai" to every chapter that has an "exercise"):
"check_ai": {
  "language": same as the chapter's exercise,
  "title": "short title, e.g. Check the AI: a login form",
  "instructions": "Markdown, 40 to 120 words: an AI assistant was asked for <a task like the exercise>; \
this is what it wrote. Say that one thing is wrong, the tests show it, and the learner should find and fix it. \
Don't say what or where the flaw is.",
  "flaw_kind": "bug" | "edge_case" | "security" | "design",
  "explanation": "1 or 2 sentences, shown after they pass: what was wrong, why AI often writes it, how to spot it",
  "hints": ["2 short hints that point to where to look, not the fix"],
  "starter": the AI's code, which runs but has exactly one flaw (same format as an exercise starter),
  "solution": the same code with only the flaw fixed,
  "tests" (and "files", "tests_js" for browser languages): as for an exercise
}
Check the AI rules:
- Keep it short so the whole path stays quick to write: under 30 lines of code and 2 or 3 tests.
- The code looks finished and plausible, like a real AI answer: no TODO comments, no hint in comments or names.
- Plant one flaw that this chapter or an earlier one taught the learner to notice. Prefer mistakes AI assistants \
really make: a missed edge case (empty list, zero, missing key), an off-by-one, trusting user input, \
building SQL or HTML from strings, showing other users' data, secrets in code, a wrong status code, \
unescaped text in innerHTML. Use "security" only when the chapter's topic touches it.
- The solution must pass every test and the starter must fail at least one, as for exercises.\
"""


# --- Checking Gemini's JSON ----------------------------------------------------

def _code(value, where, errors):
    if not isinstance(value, str) or not value.strip():
        errors.append(f'{where} must be non-empty code.')
        return ''
    if len(value) > MAX_CODE_CHARS:
        errors.append(f'{where} is too long.')
    return value[:MAX_CODE_CHARS]


def clean_exercise(data, where, errors, key=EXERCISE):
    """The chapter's exercise (or Check the AI task), cleaned, or None when it has none. Problems go in `errors`."""
    if data in (None, {}, ''):
        return None
    where = f'{where} {key}'
    if not isinstance(data, dict):
        errors.append(f'{where} must be an object.')
        return None
    language = str(data.get('language', '')).lower()
    if language not in LANGUAGES:
        return None  # a language with no runner: the chapter just stays reading and quizzes
    title, instructions = data.get('title'), data.get('instructions')
    if not isinstance(title, str) or not title.strip() or not isinstance(instructions, str) or not instructions.strip():
        errors.append(f'{where} needs a title and instructions.')
        return None
    hints = [h.strip()[:300] for h in data.get('hints', []) if isinstance(h, str) and h.strip()][:4] \
        if isinstance(data.get('hints'), list) else []
    exercise = {'language': language, 'title': title.strip()[:120], 'instructions': instructions.strip()[:3000],
                'hints': hints, 'status': PENDING}
    if key == CHECK_AI:
        flaw_kind, explanation = data.get('flaw_kind'), data.get('explanation')
        if flaw_kind not in FLAW_KINDS:
            errors.append(f'{where} flaw_kind must be one of {", ".join(FLAW_KINDS)}.')
        if not isinstance(explanation, str) or not explanation.strip():
            errors.append(f'{where} needs an explanation.')
        exercise.update(flaw_kind=flaw_kind if flaw_kind in FLAW_KINDS else 'bug',
                        explanation=explanation.strip()[:600] if isinstance(explanation, str) else '')
    if language == 'python':
        exercise['starter'] = _code(data.get('starter'), f'{where} starter', errors)
        exercise['solution'] = _code(data.get('solution'), f'{where} solution', errors)
        exercise['tests'] = _code(data.get('tests'), f'{where} tests', errors)
        if exercise['tests'] and not re.search(r'def test', exercise['tests']):
            errors.append(f'{where} tests must be unittest methods named test_...')
        return exercise
    files = [name for name in web_exercises.FILE_ORDER if name in (data.get('files') or [])]
    if 'index.html' not in files:
        errors.append(f'{where} files must include index.html.')
        return None
    for key in ('starter', 'solution'):
        given = data.get(key) if isinstance(data.get(key), dict) else {}
        exercise[key] = {name: _code(given.get(name), f'{where} {key} {name}', errors) for name in files}
    tests = []
    for i, test in enumerate(data.get('tests') if isinstance(data.get('tests'), list) else [], 1):
        if isinstance(test, dict) and isinstance(test.get('id'), str) and isinstance(test.get('description'), str):
            tests.append({'id': test['id'].strip()[:60], 'description': test['description'].strip()[:200]})
    tests_js = _code(data.get('tests_js'), f'{where} tests_js', errors)
    if not 1 <= len(tests) <= 8:
        errors.append(f'{where} tests must be a list of 1 to 8 {{id, description}} objects.')
    elif any(f"'{t['id']}'" not in tests_js and f'"{t["id"]}"' not in tests_js for t in tests):
        errors.append(f'{where} tests_js must call test() once for every test id.')
    exercise.update(files=files, tests=tests, tests_js=tests_js)
    return exercise


# --- Exercises the rest of the site can use ------------------------------------

@dataclass
class GeneratedPythonExercise(Exercise):
    data: dict = field(default_factory=dict)
    chapter: object = None
    generated = True

    @property
    def instructions(self):
        return self.data['instructions']

    @property
    def grader_source(self):
        return self.data['tests']

    @property
    def starter(self):
        return self.data['starter']

    @property
    def solution(self):
        return self.data['solution']


@dataclass
class GeneratedWebExercise(WebExercise):
    data: dict = field(default_factory=dict)
    chapter: object = None
    generated = True

    @property
    def instructions(self):
        return self.data['instructions']

    @property
    def starter_files(self):
        return dict(self.data['starter'])

    @property
    def solution_files(self):
        return dict(self.data['solution'])

    @property
    def tests_source(self):
        return self.data['tests_js']

    @property
    def libs(self):
        return LIBS.get(self.data['language'], [])

    def localized(self, language):
        return self  # generated in the learner's own language already


def slug_for(chapter, key=EXERCISE):
    return chapter.slug + SUFFIXES[key]


def split_slug(slug):
    """('chapter-slug', key) for a generated exercise slug, or (None, None)."""
    for key, suffix in SUFFIXES.items():
        if slug.startswith('ai-') and slug.endswith(suffix):
            return slug[:-len(suffix)], key
    return None, None


def build(chapter, data=None, key=EXERCISE):
    """An exercise object for a chapter's generated exercise or Check the AI task, whatever its status."""
    from .views import lesson_html  # Markdown from the AI, with raw HTML shown as text

    data = data or chapter.content.get(key)
    if not data:
        return None
    instructions_html = lesson_html(data['instructions'])
    if key == CHECK_AI:
        intro = gettext('Check the AI: this code came from an AI assistant. It runs, but one thing is wrong. '
                        'Run the tests, find the flaw and fix it, changing as little as you can.')
        instructions_html = f'<p class="check-ai-intro"><strong>{intro}</strong></p>' + instructions_html
    common = dict(slug=slug_for(chapter, key), title=data['title'], concept=chapter.title,
                  summary=chapter.learning_goal, instructions_html=instructions_html,
                  hints=[web_exercises.code_spans(h) for h in data.get('hints', [])], quiz=[], data=data, chapter=chapter)
    if data['language'] == 'python':
        return GeneratedPythonExercise(number=0, week=0, file=PYTHON_FILE, lesson='', **common)
    return GeneratedWebExercise(files=data['files'], tests_meta=data['tests'], **common)


def get_generated(slug):
    """The ready exercise behind a slug like 'ai-flexbox-1a2b3c-2-ex' (or '...-check'), or None."""
    from .models import Chapter

    chapter_slug, key = split_slug(slug)
    if not chapter_slug:
        return None
    chapter = Chapter.objects.select_related('course__path').filter(slug=chapter_slug).first()
    data = chapter and chapter.content.get(key)
    return build(chapter, key=key) if data and data.get('status') == OK else None


def owner_id(exercise):
    """Who may open a generated exercise (its path's owner); None for featured exercises."""
    chapter = getattr(exercise, 'chapter', None)
    return chapter.course.path.owner_id if chapter else None


# --- Proving each exercise works -------------------------------------------------

def _set_status(chapter, status, key=EXERCISE):
    content = dict(chapter.content)
    content[key] = dict(content[key], status=status)
    chapter.content = content
    slug = slug_for(chapter, key)
    others = [s for s in chapter.exercises if s != slug]
    chapter.exercises = others + [slug] if status == OK else others
    chapter.save(update_fields=['content', 'exercises'])
    return status


def check_python(chapter, key=EXERCISE):
    """Run the tests against the solution (all must pass) and the starter (one must fail)."""
    exercise = build(chapter, key=key)
    try:
        listed = list_tests(exercise)
        solved = run_tests(exercise, exercise.solution)
        started = run_tests(exercise, exercise.starter)
    except (SyntaxError, ValueError):
        return _set_status(chapter, BROKEN, key)
    works = listed and solved['all_passed'] and solved['total'] == len(listed) and not started['all_passed']
    return _set_status(chapter, OK if works else BROKEN, key)


def browser_check_data(chapter, key=EXERCISE):
    """What the owner's browser needs to check a pending web exercise."""
    data = chapter.content[key]
    return {'chapter': slug_for(chapter, key), 'title': data['title'], 'starter': data['starter'],
            'solution': data['solution'], 'tests': data['tests_js'], 'ids': [t['id'] for t in data['tests']],
            'libs': LIBS.get(data['language'], [])}


def record_browser_check(chapter, solution_results, starter_results, key=EXERCISE):
    """Mark a pending web exercise from the browser's two test runs."""
    ids = [t['id'] for t in chapter.content[key]['tests']]

    def passed(results):
        outcomes = {str(r.get('id')): r.get('outcome') for r in results if isinstance(r, dict)} \
            if isinstance(results, list) else {}
        return [outcomes.get(i) == 'passed' for i in ids]

    works = all(passed(solution_results)) and not all(passed(starter_results))
    return _set_status(chapter, OK if works else BROKEN, key)


def check_new_path(path):
    """Right after saving a generated path: check its Python exercises now; web ones wait for the browser."""
    from .models import Chapter

    for chapter in Chapter.objects.filter(course__path=path):
        for key in SUFFIXES:
            exercise = chapter.content.get(key)
            if exercise and exercise['language'] == 'python':
                check_python(chapter, key)


def pending(path):
    """[(chapter, key)] for the web exercises and Check the AI tasks still waiting for the owner's browser."""
    from .models import Chapter

    return [(ch, key) for ch in Chapter.objects.filter(course__path=path).order_by('course__order', 'order')
            for key in SUFFIXES if (ch.content.get(key) or {}).get('status') == PENDING]
