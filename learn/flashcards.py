"""Flashcards with spaced repetition.

Each chapter has one deck, written once by the AI (Gemini, or the tutor's Claude
connection) from the chapter's title, goal and lesson, and shared by every learner
who adds it. Most cards are hands-on: "what does this print?" and "complete the
code", with only a couple of key-concept cards. Python cards are run before saving,
so their expected output is what Python really prints. When no AI is reachable, the
deck is made from the chapter's quiz.

Each learner has their own schedule per card, in Leitner boxes: a right answer
moves the card to a later box (due again in more days), "Again" sends it back to
the first box so it comes back later in the same session and then tomorrow.
"""
import os
import re
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Min, Q
from django.utils import timezone
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext

from . import generator
from .exercises import get_exercise
from .models import CardReview, Chapter, Flashcard, LearningEvent

BOX_DAYS = [0, 1, 3, 7, 16, 35, 70]  # days until a card in each box is due again
AGAIN, GOOD, EASY = 'again', 'good', 'easy'
RATINGS = (AGAIN, GOOD, EASY)
DAILY_WRITE_LIMIT = int(os.environ.get('LEARN_FLASHCARD_DAILY_LIMIT', 15))  # new decks written per learner per day
REVIEW_XP = 15  # finishing the day's queue

BLANK = '____'
RUNNABLE = {'python': 'server', 'javascript': 'browser', 'html': 'preview'}  # how a card's code box runs
MAX_CONCEPT_CARDS = 2

CARDS_PROMPT = """\
You write practice flashcards for Describe, a self-paced learning platform for beginner and junior \
web developers. The learner has studied the chapter below and will review the cards over the coming \
weeks in a page with a code box they can run, so most cards make them read and write code.

Reply with a single JSON object and nothing else, in exactly this shape:
{"cards": [{"kind": "output" | "complete" | "concept", "language": "python", "front": "the question",
            "code": "...", "solution": "...", "expected": "...", "back": "the explanation"}]}

Card kinds:
- "output": front asks what the code prints (or returns). code is 2 to 8 lines that print something. \
expected is exactly what it prints. solution is empty.
- "complete": front says what the finished code should do. code has exactly one ____ (four underscores) \
where the learner types a missing part. solution is the same code with the blank filled in. expected is \
exactly what the solution prints (empty for HTML and CSS).
- "concept": only for a really important idea or rule the chapter depends on. code and solution are empty.

Rules:
- 8 to 10 cards, in the order the chapter teaches. At most {max_concept} concept cards; the rest are \
output and complete cards, roughly half each.
- language is the card's code language: python, javascript, html, css or sql. Use the chapter's language.
- Code is short, self-contained and runs on its own with no input(), files, network or extra packages. \
For Python and JavaScript, the code must print with print() or console.log() so there is output to check. \
In JavaScript, print arrays and objects as JSON, e.g. [2,4,6]. \
No comments in the code.
- Make a card test one thing the chapter teaches; mix easy and tricky cases (off-by-one, types, common mistakes).
- front is one clear sentence under 140 characters. back explains why in 1 or 2 short sentences, \
under 280 characters. Put code names in `backticks`.
- No emojis, no HTML outside code, no links.
- Write front and back in {language}. Code, output, file names and technical names stay in English.\
"""


class DeckError(Exception):
    """Something the learner can read: the deck could not be written."""


# --- Schedule ----------------------------------------------------------------

def _day_start(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def schedule(review, rating, now=None):
    """Move a card to its next box after an answer. Returns the review, saved."""
    now = now or timezone.now()
    if rating == AGAIN:
        if review.box > 1:
            review.lapses += 1
        review.box = 0
        review.due_at = now  # back of today's queue
    else:
        days = days_after(review, rating)
        review.box = min(review.box + (2 if rating == EASY else 1), len(BOX_DAYS) - 1)
        review.due_at = _day_start(timezone.localdate(now) + timedelta(days=days))
    review.reviews += 1
    review.last_reviewed_at = now
    review.save()
    return review


def days_after(review, rating):
    """How many days until the card comes back if answered with this rating (shown on the buttons)."""
    if rating == AGAIN:
        return 0
    box = min(review.box + (2 if rating == EASY else 1), len(BOX_DAYS) - 1)
    return max(BOX_DAYS[box], 1)


def due_reviews(user, now=None):
    return CardReview.objects.filter(user=user, due_at__lte=now or timezone.now()).select_related(
        'card__chapter__course__path')


def next_due(user, now=None):
    """When the next card that isn't due yet comes back, or None."""
    return CardReview.objects.filter(user=user, due_at__gt=now or timezone.now()).aggregate(at=Min('due_at'))['at']


def reviewed_today(user):
    return LearningEvent.objects.filter(user=user, kind=LearningEvent.CARD_REVIEWED,
                                        created_at__gte=_day_start(timezone.localdate())).count()


def due_count(user):
    if not user.is_authenticated:
        return 0
    return due_reviews(user).count()


def decks(user):
    """The learner's decks: chapter, cards, due now, learned (box 3 or later)."""
    now = timezone.now()
    rows = (CardReview.objects.filter(user=user).values('card__chapter')
            .annotate(cards=Count('id'), due=Count('id', filter=Q(due_at__lte=now)),
                      learned=Count('id', filter=Q(box__gte=3)), first=Min('created_at'))
            .order_by('-first'))
    chapters = Chapter.objects.select_related('course__path').in_bulk([r['card__chapter'] for r in rows])
    return [dict(r, chapter=chapters[r['card__chapter']]) for r in rows]


# --- Writing a deck ----------------------------------------------------------------

def chapter_language(chapter):
    return chapter.course.path.request.get('language', 'en') if chapter.course.path.ai_generated else 'en'


def source_text(chapter):
    """What the AI reads to write the cards: the chapter and any lesson text it has."""
    path = chapter.course.path
    parts = [f'Path: {path.title}', f'Course: {chapter.course.title}', f'Chapter: {chapter.title}',
             f'Learning goal: {chapter.learning_goal}']
    if chapter.exercise_idea:
        parts.append(f'Hands-on task: {chapter.exercise_idea}')
    if chapter.content.get('lesson'):
        parts.append('Lesson:\n' + chapter.content['lesson'][:5000])
    for slug in chapter.exercises:
        exercise = get_exercise(slug)
        if exercise:
            text = (exercise.path / 'instructions.md').read_text(encoding='utf-8')
            parts.append(f'Exercise "{exercise.title}":\n' + text[:3000])
    return '\n\n'.join(parts)


def _text(value, limit):
    return value.strip()[:limit] if isinstance(value, str) else ''


def _code(value, lines=12):
    return '\n'.join(_text(value, 1200).splitlines()[:lines]).strip('\n') if isinstance(value, str) else ''


def clean_cards(data, default_language=''):
    """Return (cards, problems) from the AI's JSON."""
    if not isinstance(data, dict) or not isinstance(data.get('cards'), list):
        return [], ['The reply must be a JSON object with a "cards" list.']
    cards, errors, fronts = [], [], set()
    for i, card in enumerate(data['cards'], 1):
        if not isinstance(card, dict):
            errors.append(f'card {i} must be an object.')
            continue
        kind = card.get('kind')
        front, back = _text(card.get('front'), 300), _text(card.get('back'), 600)
        code, solution = _code(card.get('code')), _code(card.get('solution'))
        expected = _text(card.get('expected'), 600) if isinstance(card.get('expected'), str) else ''
        language = (_text(card.get('language'), 20) or default_language).lower()
        if kind not in ('output', 'complete', 'concept'):
            errors.append(f'card {i} kind must be output, complete or concept.')
            continue
        if not front or not back:
            errors.append(f'card {i} needs a front and a back.')
            continue
        if front.lower() in fronts:
            errors.append(f'card {i} repeats the question "{front}".')
            continue
        if kind == 'output' and not code:
            errors.append(f'card {i} is an output card, so it needs code.')
            continue
        if kind == 'complete' and (code.count(BLANK) != 1 or not solution or BLANK in solution):
            errors.append(f'card {i} is a complete card: code needs exactly one ____ and solution the filled-in code.')
            continue
        fronts.add(front.lower())
        if kind == 'concept':
            solution = expected = ''
        elif kind == 'output':
            solution = ''
        cards.append({'kind': kind, 'language': language, 'front': front, 'code': code, 'solution': solution,
                      'expected': expected, 'back': back})
    if sum(c['kind'] == 'concept' for c in cards) > MAX_CONCEPT_CARDS:
        errors.append(f'Use at most {MAX_CONCEPT_CARDS} concept cards; turn the others into output or complete cards.')
    if not 5 <= len(cards) <= 12:
        errors.append(f'Write 8 to 10 cards (got {len(cards)} usable ones).')
    return cards[:12], errors


def check_by_running(cards):
    """Run every Python card and keep what it really prints. Returns (cards, problems)."""
    from .exercises import run_snippet

    kept, errors = [], []
    for i, card in enumerate(cards, 1):
        if card['language'] != 'python' or card['kind'] == 'concept':
            kept.append(card)
            continue
        result = run_snippet(card['solution'] or card['code'])
        if result.get('status') != 'ok':
            errors.append(f'card {i} ("{card["front"][:60]}") does not run: {str(result.get("error"))[:200]}')
            continue
        output = result.get('output', '').rstrip()
        if not output:
            errors.append(f'card {i} ("{card["front"][:60]}") prints nothing, so there is no output to check.')
            continue
        kept.append(dict(card, expected=output[:600]))
    return kept, errors


def write_cards(chapter):
    """Ask the AI for a deck, run the Python cards, and return the ones that work. Raises DeckError."""
    language = 'Arabic' if chapter_language(chapter) == 'ar' else 'English'
    system = CARDS_PROMPT.replace('{language}', language).replace('{max_concept}', str(MAX_CONCEPT_CARDS))
    messages = [{'role': 'user', 'content': source_text(chapter) + '\n\nWrite the flashcards.'}]
    errors = []
    for attempt in range(2):
        reply = generator.ask(system, messages)
        try:
            cards, errors = clean_cards(generator.parse_json(reply), (chapter.course.language or '').lower())
        except ValueError as exc:
            cards, errors = [], [str(exc)]
        if not errors:
            checked, run_errors = check_by_running(cards)
            if len(checked) >= 5 and (not run_errors or attempt == 1):
                return checked  # on the last try, broken cards are dropped rather than failing the deck
            errors = run_errors or [f'Only {len(checked)} cards work; write 8 to 10.']
        messages += [
            {'role': 'assistant', 'content': reply},
            {'role': 'user', 'content': 'Your reply had these problems:\n- ' + '\n- '.join(errors[:10])
                + '\nReply again with the whole corrected JSON object.'},
        ]
    raise DeckError(gettext("The AI's cards didn't pass the checks. Please try again."))


def quiz_cards(chapter):
    """A deck from the chapter's quiz (and its exercises' quizzes), for when no AI is reachable."""
    questions = list(chapter.content.get('quiz', []))
    for slug in chapter.exercises:
        exercise = get_exercise(slug)
        if exercise:
            questions += exercise.quiz
    cards = []
    for q in questions:
        try:
            answer = q['options'][q['answer']]
        except (KeyError, IndexError, TypeError):
            continue
        back = answer + (f' {q["explanation"]}' if q.get('explanation') else '')
        cards.append({'kind': Flashcard.CONCEPT, 'front': q['question'][:300], 'code': '', 'back': back[:600]})
    return cards[:12]


def written_today(user):
    since = timezone.now() - timedelta(days=1)
    return LearningEvent.objects.filter(user=user, kind=LearningEvent.CARDS_ADDED, created_at__gte=since,
                                        data__written=True).count()


def ensure_deck(chapter, user):
    """The chapter's cards, writing them first if nobody has yet. Returns (cards, written now)."""
    cards = list(chapter.flashcards.all())
    if cards:
        return cards, False
    made, source = [], Flashcard.AI
    if generator.ai_available():
        if written_today(user) >= DAILY_WRITE_LIMIT:
            raise DeckError(gettext('You have added a lot of new decks today. Please come back tomorrow.'))
        try:
            made = write_cards(chapter)
        except DeckError:
            raise
        except Exception as exc:  # unreachable AI: fall back to the quiz below
            made, error = [], generator.friendly_error(exc)
        else:
            error = ''
    else:
        error = gettext('No AI service is set up on this server.')
    if not made:
        made, source = quiz_cards(chapter), Flashcard.QUIZ
    if not made:
        raise DeckError(error or gettext('This chapter has nothing to make cards from yet.'))
    with transaction.atomic():
        if chapter.flashcards.exists():  # someone else wrote it meanwhile
            return list(chapter.flashcards.all()), False
        Flashcard.objects.bulk_create(Flashcard(chapter=chapter, order=i, source=source, **card)
                                      for i, card in enumerate(made))
    return list(chapter.flashcards.all()), True


def add_deck(user, chapter):
    """Put a chapter's cards in the learner's queue, due now. Returns (cards added, written now)."""
    cards, written = ensure_deck(chapter, user)
    have = set(CardReview.objects.filter(user=user, card__in=cards).values_list('card_id', flat=True))
    now = timezone.now()
    CardReview.objects.bulk_create(CardReview(user=user, card=card, due_at=now) for card in cards if card.id not in have)
    return len(cards) - len(have), written


def remove_deck(user, chapter):
    CardReview.objects.filter(user=user, card__chapter=chapter).delete()


# --- Showing a card --------------------------------------------------------------

def card_html(text):
    """Card text with `backticks` as inline code; everything else shown as typed."""
    parts = re.split(r'`([^`\n]+)`', escape(text))
    return mark_safe(''.join(f'<code dir="ltr">{p}</code>' if i % 2 else p for i, p in enumerate(parts)))


def deck_choices(user):
    """Chapters the learner can add, grouped by skill path: their job path's, then their generated paths.

    Each group is (path, [(chapter, studied, added)]); chapters they have worked on count as studied.
    """
    from . import catalog
    from .models import Path

    job = catalog.current_job_path(user)
    paths = [step.skill for step in job.steps.select_related('skill').order_by('order')] if job else []
    paths += list(Path.objects.filter(owner=user, ai_generated=True).order_by('-created_at'))
    marks = catalog.chapter_marks(user)
    states = catalog.exercise_states(user)
    added = set(CardReview.objects.filter(user=user).values_list('card__chapter_id', flat=True))
    chapters = Chapter.objects.filter(course__path__in=paths).select_related('course').order_by('course__order', 'order')
    by_path = {}
    for chapter in chapters:
        studied = chapter.slug in marks or any(slug in states for slug in chapter.exercises)
        by_path.setdefault(chapter.course.path_id, []).append((chapter, studied, chapter.id in added))
    return [(path, by_path[path.id]) for path in paths if by_path.get(path.id)]
