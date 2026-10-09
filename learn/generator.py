"""Generate a skill path with AI, for a topic that isn't in the course map.

The learner picks a skill, a level and hours per week. Gemini (or the tutor's
Claude connection when no Gemini key is set) returns the path as JSON in the
catalog's own shape: courses, chapters, and for each chapter a short lesson,
slides and a quiz in the exercise quiz format. The JSON is checked and cleaned
before anything is saved; a reply that doesn't pass is sent back once with the
problems listed, then the learner gets a readable error.

The path belongs to the learner who made it and is marked AI-generated.
"""
import json
import os
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext

from . import diagrams, tutor
from .models import Chapter, Course, Path

LEVELS = ('beginner', 'intermediate', 'advanced')
DAILY_LIMIT = int(os.environ.get('LEARN_GENERATE_DAILY_LIMIT', 5))  # per learner, to protect the free Gemini quota
MAX_SKILL_CHARS = 80
TIMEOUT_SECONDS = 150
MAX_OUTPUT_TOKENS = 32000
STOP_WORDS = {'a', 'an', 'and', 'the', 'with', 'for', 'to', 'of', 'in', 'basics', 'basic', 'fundamentals',
              'foundations', 'intro', 'introduction', 'beginner', 'beginners', 'programming', 'learn', 'course'}

GENERATE_PROMPT = """\
You design short, practical skill paths for Describe, a self-paced learning platform \
for a cohort of beginner and junior web developers (Python, Django, HTML, CSS, JavaScript, SQL). \
A skill path is made of courses, a course of chapters. Each chapter teaches one idea with a \
short lesson, a few slides and a quiz.

Reply with a single JSON object and nothing else, in exactly this shape:
{
  "title": "sentence-case title, under 60 characters",
  "summary": "one sentence on what the learner will be able to do",
  "level": "beginner" | "intermediate" | "advanced",
  "hours": total hours as a whole number,
  "project": {"title": "...", "brief": "2 sentences on a small project that uses the whole path",
              "skills_used": ["...", "..."]},
  "courses": [
    {"title": "...", "hours": whole number, "language": "the main language or tool, e.g. css",
     "chapters": [
       {"title": "...",
        "learning_goal": "starts with 'you can', one sentence",
        "exercise_idea": "one sentence describing a hands-on task",
        "mind_map": "a Mermaid mindmap of the chapter's main ideas (see Diagrams below)",
        "lesson": "Markdown, 150 to 350 words: explain the idea plainly, then one short fenced code example with a language tag, then one sentence on when to use it. Where a process, flow or structure is easier to see than read, add one ```mermaid diagram",
        "slides": [{"title": "...", "points": ["short point", "short point", "short point"],
                    "diagram": "optional Mermaid diagram that replaces long points on at most one slide"}],
        "quiz": [{"question": "...", "options": ["...", "...", "...", "..."], "answer": index of the right option (0-3),
                  "explanation": "one sentence on why"}]}
     ]}
  ]
}

Rules:
- 2 or 3 courses, each with 2 to 4 chapters, in the order a learner should take them.
- Each chapter has 3 slides and 3 quiz questions with 4 options each and exactly one right answer.
- Size the path for the learner's hours per week so it takes about 2 to 4 weeks.
- Match the learner's level: don't re-teach basics to an advanced learner.
- Plain, friendly language, sentence-case titles, no emojis, no HTML tags, no links.
- Write all prose in {language}. Code, file names and technical names stay in English.

Diagrams (Mermaid syntax, drawn on the page):
- mind_map: a "mindmap" with the chapter topic as root((...)) and 3 to 5 branches of 1 to 3 short leaves each.
- In lessons and slides use "flowchart LR" for steps and flows, "sequenceDiagram" for two sides talking \
(browser and server), and "erDiagram" for data that links together.
- Labels are 1 to 4 words in {language}. Put a label in double quotes if it has brackets, colons or other symbols.
- No styling, no classDef, no click, no %% directives, no HTML. At most 12 nodes per diagram.\
"""


class GenerationError(Exception):
    """Something the learner can read: the AI was unreachable or its reply wasn't usable."""


def ai_available():
    return bool(tutor.gemini_key() or os.environ.get('ANTHROPIC_API_KEY') or tutor.backend() == 'claude_code')


def generated_today(user):
    since = timezone.now() - timedelta(days=1)
    return Path.objects.filter(owner=user, ai_generated=True, created_at__gte=since).count()


def _words(text):
    return {w for w in slugify(text).split('-') if w and w not in STOP_WORDS}


def catalog_match(skill):
    """A catalog skill path that already covers this topic, if there is one."""
    words = _words(skill)
    if not words:
        return None
    for path in Path.objects.filter(kind=Path.SKILL, owner__isnull=True):
        if words <= _words(path.title) | _words(path.slug):
            return path
    return None


# --- Asking the model ----------------------------------------------------

def build_request(skill, level, hours_per_week, language='en'):
    system = GENERATE_PROMPT.replace('{language}', 'Arabic' if language == 'ar' else 'English')
    prompt = (f'Skill: {skill}\nLearner level: {level}\nHours per week: {hours_per_week}\n'
              'Design the skill path.')
    return system, prompt


def _ask_gemini(system, messages):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=tutor.gemini_key(), http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))
    contents = [{'role': 'user' if m['role'] == 'user' else 'model', 'parts': [{'text': m['content']}]}
                for m in messages]
    response = client.models.generate_content(
        model=tutor.GEMINI_MODEL, contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=MAX_OUTPUT_TOKENS,
                                           response_mime_type='application/json'),
    )
    return response.text or ''


def _ask_tutor_backend(system, messages):
    chunks = []
    for kind, value in tutor.stream_reply([{'type': 'text', 'text': system}], messages):
        if kind == 'text':
            chunks.append(value)
        elif kind == 'final' and value.stop_reason == 'refusal':
            raise GenerationError(gettext('The AI declined to write this path. Try wording the skill differently.'))
    return ''.join(chunks)


def ask(system, messages):
    return _ask_gemini(system, messages) if tutor.gemini_key() else _ask_tutor_backend(system, messages)


def friendly_error(exc):
    if isinstance(exc, GenerationError):
        return str(exc)
    name = type(exc).__name__.lower()
    if any(word in name for word in ('connect', 'proxy', 'timeout', 'network')):
        return gettext('Could not reach the AI service from this server. On a free PythonAnywhere account, '
                       'outside sites may be blocked. Please try again later.')
    return tutor.friendly_error(exc)


def generate(skill, level, hours_per_week, language='en'):
    """Ask the model for a path and return it checked and cleaned. Raises GenerationError."""
    system, prompt = build_request(skill, level, hours_per_week, language)
    messages = [{'role': 'user', 'content': prompt}]
    errors = []
    for _ in range(2):
        reply = ask(system, messages)
        try:
            data = parse_json(reply)
        except ValueError as exc:
            errors = [str(exc)]
        else:
            cleaned, errors = clean_path(data)
            if not errors:
                return cleaned
        messages += [
            {'role': 'assistant', 'content': reply},
            {'role': 'user', 'content': 'Your reply had these problems:\n- ' + '\n- '.join(errors[:15])
                + '\nReply again with the whole corrected JSON object.'},
        ]
    raise GenerationError(gettext('The AI\'s path didn\'t pass the checks, so nothing was saved. Please try again.')
                          + f' ({"; ".join(errors[:3])})')


# --- Checking the JSON -----------------------------------------------------

def parse_json(text):
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end == -1:
        raise ValueError('The reply did not contain a JSON object.')
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f'The reply was not valid JSON ({exc.msg}).') from None


def _text(value, where, errors, limit, required=True):
    if not isinstance(value, str) or (required and not value.strip()):
        errors.append(f'{where} must be non-empty text.')
        return ''
    return value.strip()[:limit]


def _number(value, where, errors, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f'{where} must be a number.')
        return low
    return max(low, min(high, round(value)))


def _list(value, where, errors, low, high):
    if not isinstance(value, list) or not low <= len(value) <= high:
        errors.append(f'{where} must be a list of {low} to {high} items.')
        return []
    return value


def _quiz(items, where, errors):
    quiz = []
    for i, q in enumerate(_list(items, f'{where} quiz', errors, 2, 5), 1):
        here = f'{where} question {i}'
        if not isinstance(q, dict):
            errors.append(f'{here} must be an object.')
            continue
        options = [_text(o, f'{here} option', errors, 300) for o in _list(q.get('options'), f'{here} options', errors, 2, 5)]
        answer = q.get('answer')
        if isinstance(answer, bool) or not isinstance(answer, int) or not 0 <= answer < len(options):
            errors.append(f'{here} answer must be the index of one of its options.')
            answer = 0
        elif len(set(options)) != len(options):
            errors.append(f'{here} has duplicate options.')
        quiz.append({'question': _text(q.get('question'), here, errors, 500), 'options': options,
                     'answer': answer, 'explanation': _text(q.get('explanation', ''), f'{here} explanation', errors, 500, False)})
    return quiz


def _slides(items, where, errors):
    slides = []
    for i, slide in enumerate(_list(items, f'{where} slides', errors, 2, 8), 1):
        here = f'{where} slide {i}'
        if not isinstance(slide, dict):
            errors.append(f'{here} must be an object.')
            continue
        diagram = diagrams.clean_diagram(slide.get('diagram', ''))
        if diagram and not slide.get('points'):  # a slide can be just a diagram
            points = []
        else:
            points = [_text(p, f'{here} point', errors, 300) for p in _list(slide.get('points'), f'{here} points', errors, 1, 6)]
        slides.append({'title': _text(slide.get('title'), f'{here} title', errors, 120), 'points': points,
                       'diagram': diagram})
    return slides


def clean_path(data):
    """Return (cleaned path, problems). Only known keys are kept, and text is trimmed to sensible lengths."""
    errors = []
    if not isinstance(data, dict):
        return None, ['The reply must be one JSON object.']
    level = data.get('level')
    if level not in LEVELS:
        errors.append(f'level must be one of {", ".join(LEVELS)}.')
    project = data.get('project') if isinstance(data.get('project'), dict) else {}
    path = {
        'title': _text(data.get('title'), 'title', errors, 120),
        'summary': _text(data.get('summary'), 'summary', errors, 400),
        'level': level if level in LEVELS else 'beginner',
        'hours': _number(data.get('hours'), 'hours', errors, 1, 200),
        'project': {
            'title': _text(project.get('title', ''), 'project title', errors, 120, False),
            'brief': _text(project.get('brief', ''), 'project brief', errors, 600, False),
            'skills_used': [s.strip()[:60] for s in project.get('skills_used', []) if isinstance(s, str)][:8]
            if isinstance(project.get('skills_used'), list) else [],
        },
        'courses': [],
    }
    titles = set()
    for c, course in enumerate(_list(data.get('courses'), 'courses', errors, 1, 4), 1):
        where = f'course {c}'
        if not isinstance(course, dict):
            errors.append(f'{where} must be an object.')
            continue
        chapters = []
        for n, chapter in enumerate(_list(course.get('chapters'), f'{where} chapters', errors, 1, 5), 1):
            here = f'{where} chapter {n}'
            if not isinstance(chapter, dict):
                errors.append(f'{here} must be an object.')
                continue
            title = _text(chapter.get('title'), f'{here} title', errors, 120)
            if title.lower() in titles:
                errors.append(f'{here} repeats the title "{title}".')
            titles.add(title.lower())
            lesson = diagrams.clean_lesson(_text(chapter.get('lesson'), f'{here} lesson', errors, 8000))
            if lesson and len(lesson) < 200:
                errors.append(f'{here} lesson is too short.')
            chapters.append({
                'title': title,
                'learning_goal': _text(chapter.get('learning_goal'), f'{here} learning_goal', errors, 300),
                'exercise_idea': _text(chapter.get('exercise_idea', ''), f'{here} exercise_idea', errors, 400, False),
                'mind_map': diagrams.clean_diagram(chapter.get('mind_map', '')),
                'lesson': lesson,
                'slides': _slides(chapter.get('slides'), here, errors),
                'quiz': _quiz(chapter.get('quiz'), here, errors),
            })
        path['courses'].append({
            'title': _text(course.get('title'), f'{where} title', errors, 120),
            'hours': _number(course.get('hours'), f'{where} hours', errors, 1, 100),
            'language': _text(course.get('language', ''), f'{where} language', errors, 20, False),
            'chapters': chapters,
        })
    return path, errors


# --- Saving ---------------------------------------------------------------------

@transaction.atomic
def save_path(user, data, request):
    """Store a cleaned path as the learner's own skill path."""
    slug = f'ai-{slugify(data["title"])[:30].strip("-") or "path"}-{secrets.token_hex(3)}'
    path = Path.objects.create(
        slug=slug, kind=Path.SKILL, title=data['title'], summary=data['summary'], level=data['level'],
        hours=data['hours'], order=0, project=data['project'], ai_generated=True, owner=user, request=request,
    )
    number = 0
    for c_order, course_data in enumerate(data['courses']):
        course = Course.objects.create(path=path, order=c_order, title=course_data['title'],
                                       hours=course_data['hours'], language=course_data['language'])
        for ch_order, chapter in enumerate(course_data['chapters']):
            number += 1
            Chapter.objects.create(
                course=course, order=ch_order, slug=f'{slug}-{number}', title=chapter['title'],
                learning_goal=chapter['learning_goal'], exercise_idea=chapter['exercise_idea'],
                content={'lesson': chapter['lesson'], 'slides': chapter['slides'], 'quiz': chapter['quiz'],
                         'mind_map': chapter['mind_map']},
            )
    return path
