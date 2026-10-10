"""What learners can practise in each language or framework, and the picture on each path card.

LANGUAGES is the one list behind the hands-on/reading badge on every path card,
the live hint under the Generate page's skill box, the "What you can practise"
panel and the Supported languages page. Change a language here and all four follow.

`mode` says where its code will run: SERVER (the Python runner), BROWSER (the
browser runner, learn/static/learn/js/web-runner.js) or READING (no runner: lessons, slides and
quizzes only). `ready` is True once featured exercises exist for it today.
Frameworks without a runner (Laravel, Flutter, C++, C# and so on) can still be
generated; they just stay reading and quizzes until a sandbox is wanted.
"""
import re

from django.utils.translation import gettext_lazy as _

SERVER, BROWSER, READING = 'server', 'browser', 'reading'
HANDS_ON, SOON = 'hands-on', 'soon'  # a path's badge: HANDS_ON, SOON or READING

LANGUAGES = [
    # key, name, mode, ready, art, aliases (lower case; Arabic names too, since learners type in Arabic)
    {'key': 'python', 'name': 'Python', 'mode': SERVER, 'ready': True, 'art': 'terminal',
     'aliases': ['python', 'py', 'pandas', 'numpy', 'بايثون']},
    {'key': 'django', 'name': 'Django', 'mode': SERVER, 'ready': True, 'art': 'tasks',
     'aliases': ['django', 'جانغو', 'دجانغو']},
    {'key': 'drf', 'name': 'Django REST Framework', 'mode': SERVER, 'ready': True, 'art': 'api',
     'aliases': ['django rest framework', 'rest framework', 'drf', 'rest api']},
    {'key': 'sql', 'name': 'SQL', 'mode': BROWSER, 'ready': False, 'art': 'table',
     'aliases': ['sql', 'sqlite', 'postgres', 'postgresql', 'mysql', 'database', 'databases', 'قواعد البيانات']},
    {'key': 'html', 'name': 'HTML', 'mode': BROWSER, 'ready': True, 'art': 'page',
     'aliases': ['html', 'html5', 'web page', 'semantic html']},
    {'key': 'css', 'name': 'CSS', 'mode': BROWSER, 'ready': True, 'art': 'style',
     'aliases': ['css', 'css3', 'tailwind', 'tailwind css', 'bootstrap', 'sass', 'scss', 'flexbox', 'grid layout']},
    {'key': 'javascript', 'name': 'JavaScript', 'mode': BROWSER, 'ready': True, 'art': 'quiz',
     'aliases': ['javascript', 'js', 'dom', 'es6', 'جافاسكربت', 'جافا سكربت']},
    {'key': 'react', 'name': 'React', 'mode': BROWSER, 'ready': False, 'art': 'components',
     'aliases': ['react', 'reactjs', 'react.js', 'jsx', 'رياكت']},
    {'key': 'git', 'name': 'Git and GitHub', 'mode': READING, 'ready': False, 'art': 'git',
     'aliases': ['git', 'github', 'version control']},
    {'key': 'typescript', 'name': 'TypeScript', 'mode': READING, 'ready': False, 'art': 'code',
     'aliases': ['typescript', 'ts']},
    {'key': 'node', 'name': 'Node.js and Express', 'mode': READING, 'ready': False, 'art': 'api',
     'aliases': ['node', 'nodejs', 'node.js', 'express', 'expressjs']},
    {'key': 'vue', 'name': 'Vue and Angular', 'mode': READING, 'ready': False, 'art': 'components',
     'aliases': ['vue', 'vuejs', 'angular', 'svelte', 'next.js', 'nextjs']},
    {'key': 'php', 'name': 'PHP and Laravel', 'mode': READING, 'ready': False, 'art': 'app',
     'aliases': ['php', 'laravel', 'لارافيل']},
    {'key': 'mobile', 'name': 'Flutter, React Native, Kotlin, Swift', 'mode': READING, 'ready': False, 'art': 'mobile',
     'aliases': ['flutter', 'dart', 'react native', 'kotlin', 'swift', 'android', 'ios', 'mobile', 'فلاتر']},
    {'key': 'compiled', 'name': 'C, C++, C#, Java, Go, Rust', 'mode': READING, 'ready': False, 'art': 'code',
     'aliases': ['c', 'c++', 'cpp', 'c#', 'csharp', '.net', 'dotnet', 'java', 'spring', 'golang', 'go language', 'rust']},
    {'key': 'data', 'name': 'Data analysis', 'mode': READING, 'ready': False, 'art': 'dashboard',
     'aliases': ['data analysis', 'data analytics', 'excel', 'power bi', 'tableau', 'statistics']},
]
BY_KEY = {lang['key']: lang for lang in LANGUAGES}

MODE_LABELS = {
    SERVER: _('Hands-on, checked on the server'),
    BROWSER: _('Hands-on in your browser'),
    READING: _('Lessons, slides and quizzes'),
}

# The capstone picture on each catalog path card. Generated paths use their language's picture.
ART_BY_SLUG = {
    'backend-developer': 'api', 'frontend-developer': 'page', 'fullstack-developer': 'app',
    'python-basics': 'terminal', 'javascript-fundamentals': 'quiz', 'git-github': 'git', 'sql-basics': 'table',
    'django-foundations': 'tasks', 'django-rest-framework': 'api', 'advanced-django': 'shield',
    'html-css-foundations': 'page', 'dynamic-javascript': 'dashboard', 'fullstack-integration': 'app',
}
ARTS = {'api', 'page', 'app', 'terminal', 'git', 'table', 'quiz', 'dashboard', 'tasks', 'style', 'components',
        'mobile', 'code', 'shield'}


def _pattern(alias):
    # Whole words only, so "c" doesn't match "css" and "go" doesn't match "django".
    return re.compile(r'(?<![\w+#.])' + re.escape(alias) + r'(?![\w+#])')


_ALIASES = sorted(((alias, lang) for lang in LANGUAGES for alias in lang['aliases']), key=lambda a: -len(a[0]))
_PATTERNS = [(_pattern(alias), lang) for alias, lang in _ALIASES]


def find_languages(text):
    """The languages named in some text, in the order they appear. Longer names win ("react native" over "react")."""
    text = (text or '').lower()
    found = {}
    for pattern, lang in _PATTERNS:
        match = pattern.search(text)
        if match:
            if lang['key'] not in found or match.start() < found[lang['key']][0]:
                found[lang['key']] = (match.start(), lang)
            text = text[:match.start()] + ' ' * len(match.group()) + text[match.end():]  # don't count it twice
    return [lang for _, lang in sorted(found.values(), key=lambda f: f[0])]


def path_languages(path):
    """Languages a path teaches, from its courses (and for a generated path, what the learner asked for)."""
    texts = [course.language for course in path.courses.all()]
    if path.ai_generated:  # what the learner asked for comes first: it picks the picture
        texts.insert(0, (path.request or {}).get('skill', ''))
    langs = []
    for lang in find_languages(' , '.join(texts)) or find_languages(path.title):
        if lang not in langs:
            langs.append(lang)
    return langs


def practice(path, exercise_count=0):
    """The badge for a path card: HANDS_ON today, hands-on SOON, or READING (lessons, slides and quizzes)."""
    if exercise_count:
        return HANDS_ON
    if path.kind == path.JOB:
        return SOON
    langs = path_languages(path)
    return SOON if any(lang['mode'] != READING for lang in langs) else READING


def art_for(path):
    if path.slug in ART_BY_SLUG:
        return ART_BY_SLUG[path.slug]
    langs = path_languages(path)
    return langs[0]['art'] if langs else 'code'


def hint_data():
    """What the Generate page's live hint needs: every alias with its language's name and mode."""
    return {'languages': [{'name': lang['name'], 'mode': lang['mode'], 'ready': lang['ready'],
                           'aliases': lang['aliases']} for lang in LANGUAGES]}


def grouped():
    """LANGUAGES grouped by mode, for the panel and the page."""
    return [(mode, MODE_LABELS[mode], [lang for lang in LANGUAGES if lang['mode'] == mode])
            for mode in (SERVER, BROWSER, READING)]
