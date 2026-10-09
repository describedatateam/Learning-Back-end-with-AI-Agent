"""XP, levels, streaks and badges.

Every reward is an XPEvent with a unique key, so re-running the same code or
re-taking a quiz can never pay the same reward twice.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from .exercises import load_exercises
from .models import XPEvent

PASS_XP = {1: 100, 2: 150, 3: 200, 4: 250}  # harder weeks pay more
TEST_XP = 5            # per test passing (best result counts)
NO_PEEK_XP = 50        # passed without opening the solution
FIRST_TRY_XP = 25      # passed on the very first run
QUIZ_ANSWER_XP = 10    # per correct answer, first attempt only
PERFECT_QUIZ_XP = 20   # all answers right on the first attempt
DAILY_XP = 10          # first activity of the day

LEVELS = [
    (0, 'Intern'),
    (150, 'Junior Developer'),
    (400, 'Endpoint Builder'),
    (800, 'Query Wrangler'),
    (1300, 'API Crafter'),
    (2000, 'Backend Engineer'),
    (2900, 'Senior Engineer'),
    (4000, 'Staff Engineer'),
    (5200, 'Backend Architect'),
]


@dataclass
class Badge:
    id: str
    icon: str
    name: str
    description: str
    xp: int = 50


BADGES = [
    Badge('first-pass', '🚀', 'Hello, World', 'Pass your first exercise'),
    Badge('week-1', '🌱', 'Foundations', 'Complete every Week 1 exercise', 100),
    Badge('week-2', '🔌', 'API Builder', 'Complete every Week 2 exercise', 100),
    Badge('week-3', '🛡️', 'Guardian', 'Complete every Week 3 exercise', 100),
    Badge('week-4', '🏗️', 'Shipper', 'Complete every Week 4 exercise', 100),
    Badge('sharpshooter', '🎯', 'Sharpshooter', 'Pass 3 exercises on the first run'),
    Badge('no-peeking', '🙈', 'Look, No Hands', 'Pass 5 exercises without opening the solution'),
    Badge('quiz-whiz', '🧠', 'Quiz Whiz', 'Get 5 perfect quizzes on the first try'),
    Badge('streak-3', '🔥', 'On Fire', 'Practise 3 days in a row'),
    Badge('streak-7', '⚡', 'Unstoppable', 'Practise 7 days in a row', 100),
    Badge('graduate', '🎓', 'Backend Graduate', 'Pass every exercise', 200),
]


def exercise_rewards(exercise):
    """The most XP an exercise can give, split by source (shown before starting)."""
    quiz = len(exercise.quiz) * QUIZ_ANSWER_XP + PERFECT_QUIZ_XP
    return {
        'pass': PASS_XP.get(exercise.week, 100),
        'no_peek': NO_PEEK_XP,
        'first_try': FIRST_TRY_XP,
        'quiz': quiz,
    }


def total_xp(user):
    return XPEvent.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or 0


def level_for(xp):
    index = max(i for i, (threshold, _) in enumerate(LEVELS) if xp >= threshold)
    floor, title = LEVELS[index]
    ceiling = LEVELS[index + 1][0] if index + 1 < len(LEVELS) else None
    return {
        'number': index + 1,
        'title': title,
        'floor': floor,
        'next': ceiling,
        'to_next': None if ceiling is None else ceiling - xp,
        'percent': 100 if ceiling is None else round(100 * (xp - floor) / (ceiling - floor)),
    }


def active_days(user):
    keys = XPEvent.objects.filter(user=user, key__startswith='daily:').values_list('key', flat=True)
    return sorted(date.fromisoformat(key.split(':', 1)[1]) for key in keys)


def streaks(days, today=None):
    """(current, best) runs of consecutive active days.

    The current streak stays alive until the end of the day after the last
    activity, so it doesn't reset at midnight before you've had a chance to practise.
    """
    today = today or timezone.localdate()
    best = run = 0
    previous = None
    for day in days:
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    current = run if previous and today - previous <= timedelta(days=1) else 0
    return current, best


def player_state(user, xp=None):
    if not user.is_authenticated:
        return None
    xp = total_xp(user) if xp is None else xp
    current, best = streaks(active_days(user))
    return {'xp': xp, 'level': level_for(xp), 'streak': current, 'best_streak': best}


def earned_badge_ids(user):
    keys = XPEvent.objects.filter(user=user, key__startswith='badge:').values_list('key', flat=True)
    return {key.split(':', 1)[1] for key in keys}


def xp_by_exercise(user):
    rows = XPEvent.objects.filter(user=user).exclude(slug='').values('slug').annotate(total=Sum('amount'))
    return {row['slug']: row['total'] for row in rows}


class Rewards:
    """Collects the XP earned during one request and reports it to the UI."""

    def __init__(self, user):
        self.user = user
        self.xp_before = total_xp(user)
        self.gained = []
        self.badges = []

    def award(self, key, amount, label, slug=''):
        _, created = XPEvent.objects.get_or_create(
            user=self.user, key=key, defaults={'amount': amount, 'label': label, 'slug': slug},
        )
        if created and amount:
            self.gained.append({'label': label, 'amount': amount})
        return created

    def daily(self):
        self.award(f'daily:{timezone.localdate().isoformat()}', DAILY_XP, 'Daily practice')

    def _check_badges(self):
        earned = earned_badge_ids(self.user)
        keys = set(XPEvent.objects.filter(user=self.user).values_list('key', flat=True))
        passed = {k.split(':', 1)[1] for k in keys if k.startswith('pass:')}
        exercises = load_exercises()
        _, best_streak = streaks(active_days(self.user))

        def count(prefix):
            return sum(1 for k in keys if k.startswith(prefix))

        unlocked = {
            'first-pass': len(passed) >= 1,
            'sharpshooter': count('firsttry:') >= 3,
            'no-peeking': count('nopeek:') >= 5,
            'quiz-whiz': count('perfect:') >= 5,
            'streak-3': best_streak >= 3,
            'streak-7': best_streak >= 7,
            'graduate': bool(exercises) and all(e.slug in passed for e in exercises),
        }
        for week in {e.week for e in exercises}:
            unlocked[f'week-{week}'] = all(e.slug in passed for e in exercises if e.week == week)

        for badge in BADGES:
            if unlocked.get(badge.id) and badge.id not in earned:
                if self.award(f'badge:{badge.id}', badge.xp, f'Badge: {badge.name}'):
                    self.badges.append({'icon': badge.icon, 'name': badge.name, 'description': badge.description})

    def summary(self):
        self._check_badges()
        after = total_xp(self.user)
        level_before = level_for(self.xp_before)['number']
        player = player_state(self.user, after)
        return {
            'gained': self.gained,
            'total_gained': after - self.xp_before,
            'badges': self.badges,
            'level_up': player['level']['number'] > level_before,
            'player': player,
        }


def reward_run(user, exercise, progress, result):
    rewards = Rewards(user)
    rewards.daily()
    slug = exercise.slug
    new_tests = 0
    for n in range(1, result['passed'] + 1):
        if rewards.award(f'tests:{slug}:{n}', TEST_XP, 'Tests passing', slug):
            new_tests += 1
    # Merge the per-test rewards into one line for the UI.
    if new_tests:
        rewards.gained = [g for g in rewards.gained if g['label'] != 'Tests passing']
        rewards.gained.append({'label': f'{new_tests} new test{"s" if new_tests > 1 else ""} passing', 'amount': new_tests * TEST_XP})

    if result['all_passed']:
        rewards.award(f'pass:{slug}', PASS_XP.get(exercise.week, 100), f'Completed “{exercise.title}”', slug)
        if progress.attempts == 1:
            rewards.award(f'firsttry:{slug}', FIRST_TRY_XP, 'First-try bonus', slug)
        if not progress.solution_viewed:
            rewards.award(f'nopeek:{slug}', NO_PEEK_XP, 'No-peek bonus', slug)
    return rewards.summary()


def reward_quiz(user, exercise, correct, total):
    rewards = Rewards(user)
    rewards.daily()
    slug = exercise.slug
    first_attempt = not XPEvent.objects.filter(user=user, key=f'quiz:{slug}').exists()
    if first_attempt:
        # Recorded even when 0 are right, so that retakes (after the answers
        # have been revealed) don't pay out.
        rewards.award(f'quiz:{slug}', correct * QUIZ_ANSWER_XP, f'Quiz: {correct}/{total} correct', slug)
        if correct == total:
            rewards.award(f'perfect:{slug}', PERFECT_QUIZ_XP, 'Perfect quiz', slug)
    summary = rewards.summary()
    summary['first_attempt'] = first_attempt
    return summary
