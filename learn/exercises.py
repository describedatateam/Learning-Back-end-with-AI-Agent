"""Loads exercises from learn/content/<NN-slug>/ and grades submissions.

Each exercise folder contains:
    meta.json          title, week, file the learner edits, hints, quiz
    instructions.md    the mini-lesson and task
    starter.py         code the learner starts from
    solution.py        reference solution
    grader_tests.py    tests run against the learner's code
    support/           optional extra files copied next to the learner's code
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import markdown

from .runner import RESULT_MARKER

CONTENT_DIR = Path(__file__).resolve().parent / 'content'
RUNNER = Path(__file__).resolve().parent / 'runner.py'
TIMEOUT_SECONDS = 20
RUNNER_ENV = {'PATH', 'LANG', 'LC_ALL', 'LC_CTYPE', 'SYSTEMROOT', 'WINDIR', 'TZ'}  # copied into the grader's environment


@dataclass
class Exercise:
    slug: str
    number: int
    title: str
    week: int
    concept: str
    file: str
    lesson: str
    summary: str
    instructions_html: str
    hints: list = field(default_factory=list)
    quiz: list = field(default_factory=list)
    path: Path = None

    @property
    def starter(self):
        return (self.path / 'starter.py').read_text(encoding='utf-8')

    @property
    def solution(self):
        return (self.path / 'solution.py').read_text(encoding='utf-8')


@lru_cache(maxsize=1)
def load_exercises():
    exercises = []
    for folder in sorted(p for p in CONTENT_DIR.iterdir() if p.is_dir()):
        meta = json.loads((folder / 'meta.json').read_text(encoding='utf-8'))
        number, slug = folder.name.split('-', 1)
        instructions = (folder / 'instructions.md').read_text(encoding='utf-8')
        exercises.append(Exercise(
            slug=slug,
            number=int(number),
            path=folder,
            instructions_html=markdown.markdown(instructions, extensions=['fenced_code', 'tables', 'sane_lists']),
            **meta,
        ))
    return exercises


def get_exercise(slug):
    for exercise in load_exercises():
        if exercise.slug == slug:
            return exercise
    return None


def list_tests(exercise):
    """The grader tests in display order: [{'id': 'Class.test_x', 'description': ...}]."""
    return _list_tests(exercise.path / 'grader_tests.py')


@lru_cache(maxsize=None)
def _list_tests(grader_path):
    tree = ast.parse(grader_path.read_text(encoding='utf-8'))
    tests = []
    for cls in tree.body:
        if not isinstance(cls, ast.ClassDef):
            continue
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test'):
                doc = (ast.get_docstring(node) or '').strip().splitlines()
                tests.append({
                    'id': f'{cls.name}.{node.name}',
                    'name': node.name,
                    'description': doc[0] if doc else node.name.replace('_', ' '),
                })
    return sorted(tests, key=lambda t: t['name'])


def _run_runner(exercise, code, extra_args=(), extra_files=None):
    """Copy the exercise into a temp dir, run runner.py there and return its JSON."""
    with tempfile.TemporaryDirectory(prefix='learn-') as workdir:
        workdir = Path(workdir)
        support = exercise.path / 'support'
        if support.exists():
            shutil.copytree(support, workdir, dirs_exist_ok=True)
        shutil.copy(exercise.path / 'grader_tests.py', workdir / 'grader_tests.py')
        learner_file = workdir / exercise.file
        learner_file.parent.mkdir(parents=True, exist_ok=True)
        learner_file.write_text(code, encoding='utf-8')
        for name, content in (extra_files or {}).items():
            (workdir / name).write_text(content, encoding='utf-8')

        # Only what Python needs: the site's secrets (API keys, SECRET_KEY) stay out.
        env = {k: v for k, v in os.environ.items() if k in RUNNER_ENV}
        env.update(PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(workdir))
        try:
            proc = subprocess.run(
                [python_executable(), str(RUNNER), str(workdir), exercise.file, *extra_args],
                capture_output=True, text=True, encoding='utf-8', timeout=TIMEOUT_SECONDS,
                cwd=workdir, env=env,
            )
        except subprocess.TimeoutExpired:
            return {
                'status': 'load_error', 'tests': [], 'stdout': '', 'output': '',
                'error': f'Your code took longer than {TIMEOUT_SECONDS} seconds. Is there an infinite loop?',
            }

    marker_at = proc.stdout.rfind(RESULT_MARKER)
    if marker_at == -1:
        return {'status': 'load_error', 'tests': [], 'stdout': proc.stdout, 'output': proc.stdout,
                'error': proc.stderr or 'The grader crashed.'}
    return json.loads(proc.stdout[marker_at + len(RESULT_MARKER):])


def python_executable():
    """The Python that runs the grader.

    Under a web server (uWSGI on PythonAnywhere, for example) sys.executable can
    be the server binary rather than Python, so fall back to the virtualenv's
    own interpreter. LEARN_PYTHON overrides both.
    """
    if os.environ.get('LEARN_PYTHON'):
        return os.environ['LEARN_PYTHON']
    if Path(sys.executable).name.lower().startswith('python'):
        return sys.executable
    prefix = Path(sys.prefix)
    for candidate in (prefix / 'bin' / 'python3', prefix / 'bin' / 'python', prefix / 'Scripts' / 'python.exe'):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def run_selection(exercise, code, text, start_line, end_line):
    """Run highlighted code (with the rest of the file loaded) and return its output."""
    request = json.dumps({'text': text, 'start_line': start_line, 'end_line': end_line})
    return _run_runner(exercise, code, ['--scratch', '__selection__.json'], {'__selection__.json': request})


def run_tests(exercise, code, test_id=None):
    """Run the exercise's grader tests (or just `test_id`) against `code` in a fresh subprocess."""
    result = _run_runner(exercise, code, ['--test', test_id] if test_id else [])
    result.setdefault('tests', [])
    passed = sum(1 for t in result['tests'] if t['outcome'] == 'passed')
    result['passed'] = passed
    result['total'] = len(result['tests'])
    result['all_passed'] = result['status'] == 'ok' and result['total'] > 0 and passed == result['total']
    return result
