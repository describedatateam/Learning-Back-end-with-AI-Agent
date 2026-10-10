"""HTML, CSS and JavaScript exercises that run and are graded in the learner's browser.

Each exercise is a folder in learn/web_content/<slug>/:
    meta.json            title, chapter concept, files, tests, hints, quiz, fake API, and an "ar" block
    instructions.md      the mini-lesson and task (instructions.ar.md for Arabic)
    starter/<file>       what the learner starts from (index.html, style.css, script.js)
    solution/<file>      reference solution
    tests.js             test('id', async () => { ... }) calls, run by learn/static/learn/js/web-runner.js

They share the slug space, progress table, XP and tutor with the Python
exercises in learn/content/, so a catalog chapter can list either kind.
"""
import dataclasses
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import markdown
from django.utils.html import escape
from django.utils.safestring import mark_safe

CONTENT_DIR = Path(__file__).resolve().parent / 'web_content'
FILE_ORDER = ('index.html', 'style.css', 'script.js')
MAX_FILE_CHARS = 20000


@dataclass
class WebExercise:
    slug: str
    title: str
    concept: str
    summary: str
    files: list
    tests_meta: list
    instructions_html: str
    hints: list = field(default_factory=list)
    quiz: list = field(default_factory=list)
    api: dict = field(default_factory=dict)
    preview: bool = True
    ar: dict = field(default_factory=dict)
    path: Path = None
    kind = 'web'
    number = 0
    week = 0          # PASS_XP falls back to its default for week 0
    code_language = 'html'

    @property
    def file(self):
        return ', '.join(self.files)

    def _read(self, folder):
        return {name: (self.path / folder / name).read_text(encoding='utf-8')
                for name in self.files if (self.path / folder / name).exists()}

    @property
    def starter_files(self):
        return self._read('starter')

    @property
    def solution_files(self):
        return self._read('solution')

    @property
    def starter(self):
        return join_files(self.starter_files)

    @property
    def solution(self):
        return join_files(self.solution_files)

    @property
    def tests_source(self):
        return (self.path / 'tests.js').read_text(encoding='utf-8')

    @property
    def grader_source(self):
        return self.tests_source

    def localized(self, language):
        """A copy with the Arabic title, lesson, hints, quiz and test names when there are some."""
        if language != 'ar' or not self.ar:
            return self
        changes = {key: self.ar[key] for key in ('title', 'summary', 'hints', 'quiz') if self.ar.get(key)}
        arabic = self.path / 'instructions.ar.md'
        if arabic.exists():
            changes['instructions_html'] = _markdown(arabic.read_text(encoding='utf-8'))
        changes['tests_meta'] = [{**t, 'description': t.get('description_ar') or t['description']} for t in self.tests_meta]
        return dataclasses.replace(self, **changes)


def join_files(files):
    """Several files as one text block (for the tutor and for saving)."""
    return '\n\n'.join(f'<!-- {name} -->\n{text}' for name, text in files.items())


def _markdown(text):
    return markdown.markdown(text, extensions=['fenced_code', 'tables', 'sane_lists'])


@lru_cache(maxsize=1)
def load_web_exercises():
    exercises = []
    if not CONTENT_DIR.exists():
        return exercises
    for folder in sorted(p for p in CONTENT_DIR.iterdir() if p.is_dir()):
        meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        exercises.append(WebExercise(
            slug=folder.name, path=folder,
            title=meta['title'], concept=meta.get('concept', ''), summary=meta.get('summary', ''),
            files=[name for name in FILE_ORDER if name in meta['files']],
            tests_meta=meta['tests'], hints=meta.get('hints', []), quiz=meta.get('quiz', []),
            api=meta.get('api', {}), preview=meta.get('preview', True), ar=meta.get('ar', {}),
            instructions_html=_markdown((folder / 'instructions.md').read_text(encoding='utf-8')),
        ))
    return exercises


def get_web_exercise(slug):
    return next((e for e in load_web_exercises() if e.slug == slug), None)


def list_tests(exercise):
    return [{'id': t['id'], 'name': t['id'], 'description': t['description'], 'html': code_spans(t['description'])}
            for t in exercise.tests_meta]


def code_spans(text):
    """Escape a test description and show its `backticked` parts as left-to-right code (they stay readable in Arabic)."""
    return mark_safe(re.sub(r'`([^`]+)`', r'<code dir="ltr">\1</code>', str(escape(text))))


def clean_files(exercise, files):
    """The learner's files from a request: only this exercise's file names, size-capped."""
    files = files if isinstance(files, dict) else {}
    return {name: str(files.get(name, ''))[:MAX_FILE_CHARS] for name in exercise.files}


def score(exercise, reported):
    """Turn the browser's test report into the same shape as the Python runner's result.

    The tests run in the learner's own browser, so this trusts what it reports:
    fine for practice and XP, not for anything that needs proof.
    """
    by_id = {}
    for item in reported if isinstance(reported, list) else []:
        if isinstance(item, dict) and item.get('outcome') in ('passed', 'failed', 'error'):
            by_id[str(item.get('id'))] = item
    tests = []
    for t in exercise.tests_meta:
        item = by_id.get(t['id'], {})
        tests.append({'id': t['id'], 'name': t['id'], 'description': t['description'],
                      'outcome': item.get('outcome', 'error'), 'message': str(item.get('message', ''))[:500]})
    passed = sum(t['outcome'] == 'passed' for t in tests)
    return {'status': 'ok', 'tests': tests, 'passed': passed, 'total': len(tests),
            'all_passed': bool(tests) and passed == len(tests)}
