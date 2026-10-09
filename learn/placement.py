"""Placement tests for prerequisite skill paths (Python basics, JavaScript fundamentals).

The test lives in the path's `placement_test` (from catalog.json): multiple-choice
questions and coding tasks, each tagged with the chapter it checks. Coding tasks
are graded by the same runner as the exercises, with tests in
learn/placement_tasks/<path slug>/<task id>/.

Passing (enough questions right and every coding task passing) marks the whole
path as known. Otherwise each chapter whose questions and tasks were all right
is skipped, so the learner only studies what they missed.
"""
import math
from dataclasses import dataclass
from pathlib import Path as FilePath

from django.db import transaction
from django.utils.text import slugify

from .exercises import list_tests, run_tests
from .models import Chapter, PlacementAttempt, SkippedPath

TASKS_DIR = FilePath(__file__).resolve().parent / 'placement_tasks'
MAX_CODE_CHARS = 20000


@dataclass
class Task:
    """A coding task. It has what the grader needs from an Exercise: `path` and `file`."""
    id: int
    prompt: str
    chapter: str
    path: FilePath
    file: str = 'task.py'

    @property
    def starter(self):
        return (self.path / 'starter.py').read_text(encoding='utf-8')

    @property
    def tests(self):
        return list_tests(self)


def has_test(path):
    return bool(path.placement_test.get('multiple_choice_questions'))


def questions(path):
    """The questions without their answers, for the test page."""
    return [{'id': q['id'], 'question': q['question'], 'options': q['options'], 'chapter': q.get('chapter_tagged', '')}
            for q in path.placement_test.get('multiple_choice_questions', [])]


def tasks(path):
    """Coding tasks that have grader tests. A task without tests yet is left out rather than ungradable."""
    found = []
    for task in path.placement_test.get('coding_tasks', []):
        folder = TASKS_DIR / path.slug / str(task['id'])
        if (folder / 'grader_tests.py').exists():
            found.append(Task(task['id'], task['prompt'], task.get('chapter_tagged', ''), folder))
    return found


def pass_mark(path):
    total = len(path.placement_test.get('multiple_choice_questions', []))
    return path.placement_test.get('pass_correct') or math.ceil(0.8 * total)


def grade(path, answers, code):
    """Mark one attempt. `answers` maps question id to the chosen option text, `code` maps task id to code."""
    test = path.placement_test
    results, by_chapter = [], {}
    for q in test.get('multiple_choice_questions', []):
        chosen = answers.get(str(q['id']))
        right = chosen == q['correct_option']
        results.append({'id': q['id'], 'question': q['question'], 'chosen': chosen, 'right': right,
                        'answer': q['correct_option'], 'explanation': q.get('explanation', '')})
        by_chapter.setdefault(slugify(q.get('chapter_tagged', '')), []).append(right)
    task_results = []
    for task in tasks(path):
        result = run_tests(task, str(code.get(str(task.id), ''))[:MAX_CODE_CHARS])
        task_results.append({'task': task, 'passed': result['passed'], 'total': result['total'],
                             'all_passed': result['all_passed'], 'error': result.get('error', '')})
        by_chapter.setdefault(slugify(task.chapter), []).append(result['all_passed'])

    correct = sum(r['right'] for r in results)
    tasks_passed = sum(r['all_passed'] for r in task_results)
    passed = correct >= pass_mark(path) and (
        not test.get('coding_tasks_required', True) or tasks_passed == len(task_results))
    chapters = list(Chapter.objects.filter(course__path=path).values_list('slug', flat=True))
    known = chapters if passed else [slug for slug in chapters if by_chapter.get(slug) and all(by_chapter[slug])]
    return {'questions': results, 'tasks': task_results, 'correct': correct, 'total': len(results),
            'tasks_passed': tasks_passed, 'tasks_total': len(task_results), 'passed': passed,
            'pass_mark': pass_mark(path), 'skipped_chapters': known}


@transaction.atomic
def save_attempt(user, path, outcome, answers, code):
    attempt = PlacementAttempt.objects.create(
        user=user, path=path, correct=outcome['correct'], total=outcome['total'],
        tasks_passed=outcome['tasks_passed'], tasks_total=outcome['tasks_total'], passed=outcome['passed'],
        skipped_chapters=outcome['skipped_chapters'], answers={'mcq': answers, 'code': code},
    )
    if outcome['passed']:
        SkippedPath.objects.get_or_create(user=user, path=path)
    return attempt


def latest_attempt(user, path):
    if not user.is_authenticated:
        return None
    return PlacementAttempt.objects.filter(user=user, path=path).first()
