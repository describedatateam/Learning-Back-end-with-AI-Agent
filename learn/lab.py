"""The Lab: a free-play playground where a learner builds their own idea.

A Lab project is a few files of one kind. Web kinds run in the learner's browser
(learn/static/learn/js/web-runner.js); Python runs on the server in the same
guarded runner as the flashcards. The tutor coaches the project as a whole.
"""
import re

from django.utils.translation import gettext_lazy as _

MAX_PROJECTS = 50          # per learner
MAX_FILE_CHARS = 50000
MAX_TITLE_CHARS = 80
TOPIC_PREFIX = 'lab-'

WEB_PAGE = """<!doctype html>
<html>
<head>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <h1>Hello!</h1>
  <p>Change this page, then open Preview.</p>
  <button id="hello">Click me</button>
  <script src="script.js"></script>
</body>
</html>
"""

KINDS = {
    'web': {
        'name': 'HTML, CSS and JavaScript', 'label': _('HTML, CSS and JavaScript'),
        'blurb': _('A web page with live preview.'), 'icon': 'globe', 'libs': [], 'browser': True,
        'files': {
            'index.html': WEB_PAGE,
            'style.css': 'body {\n  font-family: system-ui, sans-serif;\n  margin: 24px;\n}\n\nh1 {\n  color: #4f46e5;\n}\n',
            'script.js': "document.querySelector('#hello').addEventListener('click', () => {\n  console.log('Hello from script.js');\n});\n",
        },
    },
    'react': {
        'name': 'React', 'label': 'React',
        'blurb': _('Components and state, written in JSX.'), 'icon': 'atom', 'libs': ['react'], 'browser': True,
        'files': {
            'index.html': '<div id="root"></div>\n',
            'style.css': 'body {\n  font-family: system-ui, sans-serif;\n  margin: 24px;\n}\n',
            'script.js': (
                'function App() {\n'
                '  const [count, setCount] = React.useState(0);\n'
                '  return (\n'
                '    <div>\n'
                '      <h1>My React app</h1>\n'
                '      <button onClick={() => setCount(count + 1)}>Clicked {count} times</button>\n'
                '    </div>\n'
                '  );\n'
                '}\n\n'
                "ReactDOM.createRoot(document.getElementById('root')).render(<App />);\n"
            ),
        },
    },
    'tailwind': {
        'name': 'Tailwind CSS', 'label': 'Tailwind CSS',
        'blurb': _('Style a page with utility classes.'), 'icon': 'palette', 'libs': ['tailwind'], 'browser': True,
        'files': {
            'index.html': (
                '<main class="p-6 font-sans">\n'
                '  <h1 class="text-3xl font-bold text-indigo-600">Hello Tailwind</h1>\n'
                '  <p class="mt-2 text-gray-600">Style with utility classes.</p>\n'
                '</main>\n'
            ),
            'script.js': '',
        },
    },
    'python': {
        'name': 'Python', 'label': 'Python',
        'blurb': _('A script that prints its output.'), 'icon': 'terminal', 'libs': [], 'browser': False,
        'files': {
            'main.py': 'def greet(name):\n    return f"Hello, {name}!"\n\n\nprint(greet("Describe"))\n',
        },
    },
}

# The extension of each file, as the editor names its mode.
MODES = {'.html': 'htmlmixed', '.css': 'css', '.js': 'javascript', '.py': 'python-plus'}


def starter_files(kind):
    return dict(KINDS[kind]['files'])


def clean_files(kind, files):
    """Keep only this kind's files, as text, cut to the size limit. Missing files come back empty."""
    files = files if isinstance(files, dict) else {}
    return {name: str(files.get(name) or '')[:MAX_FILE_CHARS] for name in KINDS[kind]['files']}


def clean_title(title):
    return re.sub(r'\s+', ' ', str(title or '')).strip()[:MAX_TITLE_CHARS]


def topic(lab):
    return f'{TOPIC_PREFIX}{lab.id}'


def lab_id(topic_name):
    rest = topic_name[len(TOPIC_PREFIX):] if topic_name.startswith(TOPIC_PREFIX) else ''
    return int(rest) if rest.isdigit() else None


def tutor_context(lab):
    """What the tutor knows about the Lab project: its kind and its idea. The code comes with each question."""
    kind = KINDS[lab.kind]
    where = 'in the learner\'s browser' if kind['browser'] else 'on the server with Python 3 (no input(), no network)'
    extra = {
        'react': ' React 18 and ReactDOM are globals (no imports or exports); script.js holds JSX.',
        'tailwind': ' The page loads Tailwind CSS v4, so index.html uses utility classes.',
    }.get(lab.kind, '')
    return (
        f'<lab title="{lab.title}" kind="{kind["name"]}">\n'
        'Right now the learner is in the Lab, a free-play playground where they build their own idea, not a '
        f'graded exercise. Their files run {where}.{extra} There are no tests to pass.\n'
        'Be a project coach: help them shape the idea into small steps, suggest the next step that fits what '
        'they have, explain errors in plain words, and review their code when they ask. Show short examples '
        'with different names rather than writing the whole project for them; write a full file only if they '
        'ask for it outright. Many learners use a phone, so keep code examples short. '
        'Reply in the language the learner writes in; code and technical names stay in English.\n'
        + (f'<idea>{lab.idea}</idea>\n' if lab.idea else '')
        + '</lab>'
    )


def build_turn(question, files=None, output=None, max_chars=20000):
    """The learner's question with a snapshot of their files and the latest output."""
    if not isinstance(files, dict) or not files:
        return question
    code = '\n\n'.join(f'--- {name} ---\n{str(text)}' for name, text in files.items())[:max_chars]
    state = f'<lab_files>\n{code}\n</lab_files>\n'
    if output:
        state += f'<last_output>\n{str(output)[:4000]}\n</last_output>\n'
    return f'{state}\n{question}'
