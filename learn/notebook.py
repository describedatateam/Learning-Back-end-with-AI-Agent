"""The learner's notebook: one AI-written study page per passed exercise.

Each page is grounded in real evidence: the lesson, the learner's tutor chat,
when each test first passed, and their final code. It is generated through the
same Claude connection as the tutor (API key or Claude Code login).
"""
import json
import re

from . import tutor
from .models import ExerciseProgress, TutorMessage, XPEvent

MAX_CHAT_MESSAGES = 60
MAX_REPLY_CHARS = 700

NOTEBOOK_PROMPT = """\
You write study-journal pages for a beginner learning backend development with Python, \
Django and Django REST Framework. The learner taught themselves Python through data \
analysis (strings, dictionaries, loops, pandas), and is new to web and backend concepts.

You get one exercise they have passed: its lesson, the tools the lesson teaches, their \
chat with the study tutor, when each grader test first passed, and their final code. \
Write a page that helps them remember what they learned and use it again later.

Reply with a single JSON object and nothing else, with these keys:
- "summary": 1-2 sentences, addressed to the learner as "you", on what they built.
- "tools": 3-6 items, one per function, method or piece of syntax the exercise taught, \
each {"name": "...", "what_it_does": "one plain sentence", "example": "a short, \
runnable Python example on different data from the exercise, printing its result", \
"output": "exactly what the example prints"}.
- "use_case": 2-3 sentences describing a realistic situation in a real backend where \
this is used.
- "difficulties": the parts they found hard, each {"what": "...", "why_it_was_hard": \
"...", "how_you_solved_it": "..."}. Base these only on evidence in the chat and the test \
timeline, and quote or paraphrase their own words where you can. If there is no \
evidence of a difficulty, return an empty list rather than guessing.
- "takeaways": 3 short bullet-style sentences worth remembering.
- "next_step": one sentence suggesting what to practise or read next.
Write in plain, warm language, and keep every field short.\
"""


def lesson_tools(exercise):
    """Tool names from the lesson's "Tools you'll use" section (### headings)."""
    text = (exercise.path / 'instructions.md').read_text(encoding='utf-8')
    section = re.search(r"^## Tools you'll use\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not section:
        return []
    return [h.strip().replace('`', '') for h in re.findall(r'^### (.+)$', section.group(1), re.M)]


def build_evidence(exercise):
    progress = ExerciseProgress.objects.filter(slug=exercise.slug).first()
    lines = [f'Exercise: #{exercise.number:02d} {exercise.title} (week {exercise.week}, file {exercise.file})']
    if progress:
        lines.append(f'Test runs before passing: {progress.attempts}. '
                     f'Opened the reference solution: {"yes" if progress.solution_viewed else "no"}.')

    events = XPEvent.objects.filter(slug=exercise.slug).order_by('created_at')
    timeline = [f'{e.created_at:%H:%M} {e.label}' for e in events if not e.key.startswith(('daily:', 'badge:'))]
    if timeline:
        lines.append('Timeline (when each reward was first earned):\n' + '\n'.join(timeline))

    chat = []
    for message in TutorMessage.objects.filter(topic=exercise.slug).order_by('created_at', 'id')[:MAX_CHAT_MESSAGES]:
        text = message.display if message.role == 'user' else message.display[:MAX_REPLY_CHARS]
        who = 'learner' if message.role == 'user' else 'tutor'
        chat.append(f'<{who} time="{message.created_at:%H:%M}">\n{text}\n</{who}>')
    lines.append('<tutor_chat>\n' + ('\n'.join(chat) if chat else '(no tutor conversation)') + '\n</tutor_chat>')

    lines.append(f'<final_code>\n{progress.code if progress and progress.code else "(not saved)"}\n</final_code>')
    return '\n\n'.join(lines)


def build_prompt(exercise):
    lesson = (exercise.path / 'instructions.md').read_text(encoding='utf-8')
    tools = ', '.join(lesson_tools(exercise)) or '(see the lesson)'
    system = [
        {'type': 'text', 'text': NOTEBOOK_PROMPT},
        {'type': 'text', 'text': f'<lesson>\n{lesson}\n</lesson>\n\nTools the lesson teaches: {tools}'},
    ]
    return system, build_evidence(exercise)


def parse_page(text):
    """Pull the JSON object out of the model's reply (tolerating code fences)."""
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError('The reply did not contain a JSON object.')
    page = json.loads(text[start:end + 1])
    for key in ('summary', 'use_case', 'next_step'):
        page[key] = str(page.get(key, ''))
    for key in ('tools', 'difficulties', 'takeaways'):
        page[key] = page.get(key) if isinstance(page.get(key), list) else []
    return page


def generate_page(exercise):
    system, evidence = build_prompt(exercise)
    chunks, final = [], None
    for kind, value in tutor.stream_reply(system, [{'role': 'user', 'content': evidence}]):
        if kind == 'text':
            chunks.append(value)
        elif kind == 'final':
            final = value
    if final is not None and final.stop_reason == 'refusal':
        raise tutor.TutorError('The notebook page could not be written for this exercise. Please try again.')
    return parse_page(''.join(chunks))
