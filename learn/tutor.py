"""The study tutor: a Claude-powered chat that knows the current exercise.

Each request sends a stable system prompt (the tutor's role + the exercise),
the saved conversation, and a new learner turn that carries a snapshot of their
code and latest test results.

Two ways to reach Claude, chosen automatically:
- "api": the Anthropic API, when ANTHROPIC_API_KEY is set. Turns are sent exactly
  as stored, so the history only grows at the end and prompt caching keeps working.
- "claude_code": the Claude Code CLI (claude.exe) with the learner's existing
  Claude login, so no API key is needed.
Set LEARN_TUTOR_BACKEND=api or claude_code to force one.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import anthropic

from .exercises import load_exercises

TUTOR_MODEL = os.environ.get('LEARN_TUTOR_MODEL', 'claude-opus-5')
CLI_TIMEOUT_SECONDS = 300
MAX_TOKENS = 16000
MAX_HISTORY = 40          # messages kept in the prompt (older ones stay in the DB)
MAX_QUESTION_CHARS = 4000
MAX_CODE_CHARS = 20000
GENERAL_TOPIC = 'general'

TUTOR_PROMPT = """\
You are the study tutor inside Describe, a self-paced course where a beginner learns \
backend development with Python, Django and Django REST Framework. The course has 17 small \
exercises over four weeks: each has a short lesson, starter code the learner edits in the \
browser, and hidden grader tests. Learners earn XP for passing tests, with a bonus for \
passing without opening the reference solution.

About this learner: they are new to backend development and web concepts (HTTP, \
servers, APIs, databases). They taught themselves Python through data analysis, so they \
know strings, string methods, lists, dictionaries, loops and numpy/pandas/matplotlib, but \
are less sure about functions and parameters, tuple unpacking, classes and reading \
unfamiliar syntax. Define every new term the first time it comes up. When a function or \
method is new to them, show how to call it (a function like f(x) or a method like \
x.f(), and which brackets) with a tiny example and its output. Take one small step per \
reply and let them try it before moving on. Where it helps, connect ideas to data analysis.

Your goal is for the learner to understand, not just to finish. How to help:

- Concept questions ("what is a queryset?", "why do we hash passwords?") are always \
welcome, whether or not they relate to the current exercise. Explain in plain language for \
someone new to backend work, use a small example or analogy, and connect the idea to what \
they are building when you can.
- When they are stuck on the exercise, guide them there instead of handing over the \
answer: point to the line or idea that is off, explain what the failing test expects, ask a \
question that leads to the fix, or show a small example that uses different names and data \
from the exercise. Do not write the finished solution or paste the reference solution. If \
they ask outright for the answer, tell them the "Show reference solution" button in the \
Hints tab has it (opening it before passing gives up the no-peek bonus), and offer one more \
hint in case they would like to try again first.
- Once the exercise is passed (the learner state says so), you can discuss the solution \
openly, compare approaches, and suggest improvements.
- If their code is already correct, say so plainly. Be encouraging, and honest about \
mistakes.
- Keep replies short and focused: a few short paragraphs or a brief list, Markdown \
formatting, and fenced code blocks with a language tag. When you have just taught a \
concept, you can end with one short question they can answer to check their understanding.

Each learner message may start with a <learner_state> block holding a snapshot of their \
current code and latest test results when they asked. The reference solution and grader \
tests in the exercise context are for your understanding only; the learner cannot see them.\
"""


def _exercise_context(exercise):
    instructions = (exercise.path / 'instructions.md').read_text(encoding='utf-8')
    grader = (exercise.path / 'grader_tests.py').read_text(encoding='utf-8')
    return (
        f'<exercise number="{exercise.number}" week="{exercise.week}" title="{exercise.title}">\n'
        f'The learner edits the file `{exercise.file}`.\n\n'
        f'<lesson>\n{instructions}\n</lesson>\n\n'
        f'<starter_code>\n{exercise.starter}\n</starter_code>\n\n'
        f'<reference_solution>\n{exercise.solution}\n</reference_solution>\n\n'
        f'<grader_tests>\n{grader}\n</grader_tests>\n'
        f'</exercise>'
    )


def _course_context():
    lines = [f'- #{e.number:02d} (week {e.week}) {e.title}: {e.summary}' for e in load_exercises()]
    return (
        '<course>\nThe learner is not on a specific exercise right now. The exercises are:\n'
        + '\n'.join(lines) + '\n</course>'
    )


def build_system(exercise):
    context = _exercise_context(exercise) if exercise else _course_context()
    return [
        {'type': 'text', 'text': TUTOR_PROMPT},
        {'type': 'text', 'text': context},
    ]


def _format_results(result):
    if not result:
        return 'They have not run the tests in this session yet.'
    if result.get('error') and not result.get('tests'):
        return f'Their code failed to load:\n{str(result["error"])[:2000]}'
    lines = [f'{result.get("passed", 0)}/{result.get("total", 0)} tests passing.']
    for test in result.get('tests', [])[:30]:
        line = f'- [{test.get("outcome")}] {test.get("description")}'
        if test.get('outcome') != 'passed' and test.get('message'):
            line += f'\n  {str(test["message"])[:500]}'
        lines.append(line)
    return '\n'.join(lines)


def build_learner_turn(question, *, exercise=None, code=None, result=None, progress=None):
    """The content sent to the model for one learner question."""
    if exercise is None:
        return question
    status = 'passed' if progress and progress.passed else 'not passed yet'
    code = (code or '')[:MAX_CODE_CHARS]
    return (
        '<learner_state>\n'
        f'Exercise status: {status}.\n'
        f'Current `{exercise.file}`:\n```python\n{code}\n```\n'
        f'Latest test run: {_format_results(result)}\n'
        '</learner_state>\n\n'
        f'{question}'
    )


_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


class TutorError(Exception):
    """A problem with a message that is already fit to show the learner."""


def find_claude_cli():
    """Path to the Claude Code CLI, preferring the newest editor-bundled copy."""
    if os.environ.get('LEARN_CLAUDE_CLI'):
        return os.environ['LEARN_CLAUDE_CLI']
    found = shutil.which('claude')
    if found:
        return found
    candidates = []
    for editor in ('.vscode', '.vscode-insiders', '.cursor', '.windsurf'):
        extensions = Path.home() / editor / 'extensions'
        for name in ('claude.exe', 'claude'):
            candidates.extend(extensions.glob(f'anthropic.claude-code-*/resources/native-binary/{name}'))

    def version(path):
        match = re.search(r'claude-code-(\d+)\.(\d+)\.(\d+)', str(path))
        return tuple(int(n) for n in match.groups()) if match else (0, 0, 0)

    candidates = [c for c in candidates if c.is_file()]
    return str(max(candidates, key=version)) if candidates else None


def gemini_key():
    return os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')


def backend():
    choice = os.environ.get('LEARN_TUTOR_BACKEND', 'auto')
    if choice in ('api', 'claude_code', 'gemini'):
        return choice
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'api'
    if find_claude_cli():
        return 'claude_code'
    return 'gemini' if gemini_key() else 'api'


def backend_label():
    label = {
        'api': 'your Anthropic API key',
        'claude_code': 'your Claude Code login',
        'gemini': 'Google Gemini',
    }[backend()]
    if backend() != 'gemini' and gemini_key():
        label += ', with Gemini as a backup'
    return label


def stream_reply(system, messages):
    """Yield ('text', chunk) as the answer streams, then ('final', message).

    If Claude fails before any text arrives (not signed in, usage limit, no key,
    no connection) and a Gemini key is set, Gemini answers instead, announced
    with a ('notice', message) event first.
    """
    primary = backend()
    if primary == 'gemini':
        yield from _stream_via_gemini(system, messages)
        return
    started = False
    try:
        for kind, value in _stream_via_claude(primary, system, messages):
            started = started or kind == 'text'
            yield kind, value
    except Exception as exc:
        if started or not gemini_key():
            raise
        yield 'notice', f'Claude wasn\'t available ({friendly_error(exc)}) Gemini answered instead.'
        yield from _stream_via_gemini(system, messages)


def _stream_via_claude(primary, system, messages):
    if primary == 'claude_code':
        yield from _stream_via_claude_code(system, messages)
        return
    messages = [{'role': m['role'], 'content': m['content']} for m in messages]
    client = get_client()
    with client.beta.messages.stream(
        model=TUTOR_MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=messages,
        output_config={'effort': 'medium'},
        cache_control={'type': 'ephemeral'},
        # If a safety classifier declines, the API retries on a recommended model.
        fallbacks='default',
        betas=['server-side-fallback-2026-07-01'],
    ) as stream:
        for text in stream.text_stream:
            yield 'text', text
        yield 'final', stream.get_final_message()


def _transcript(messages):
    """Flatten the conversation into one prompt for the CLI.

    Earlier learner turns are shown without their code snapshots to keep the
    prompt small; the newest turn keeps its full <learner_state>.
    """
    *earlier, latest = messages
    if not earlier:
        return latest['content']
    lines = ['<conversation_so_far>']
    for message in earlier:
        role = 'learner' if message['role'] == 'user' else 'tutor'
        lines.append(f"<{role}>\n{message.get('display') or message['content']}\n</{role}>")
    lines.append('</conversation_so_far>')
    lines.append("\nThe learner's new message:\n")
    lines.append(latest['content'])
    return '\n'.join(lines)


def _stream_via_claude_code(system, messages):
    cli = find_claude_cli()
    if not cli:
        raise TutorError('Could not find Claude Code on this computer. Install the Claude Code extension, '
                         'or set LEARN_CLAUDE_CLI to the path of claude.exe.')
    command = [
        cli, '-p',
        '--safe-mode',                 # ignore plugins, hooks, MCP servers and CLAUDE.md files
        '--tools', '',                 # the tutor only talks: no file, shell or web access
        '--strict-mcp-config',
        '--no-session-persistence',
        '--system-prompt', '\n\n'.join(block['text'] for block in system),
        '--effort', 'medium',
        '--output-format', 'stream-json', '--include-partial-messages', '--verbose',
    ]
    if os.environ.get('LEARN_TUTOR_MODEL'):
        command += ['--model', os.environ['LEARN_TUTOR_MODEL']]

    workdir = tempfile.mkdtemp(prefix='learn-tutor-')
    stderr = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        command, cwd=workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    timer = threading.Timer(CLI_TIMEOUT_SECONDS, proc.kill)
    timer.start()
    try:
        proc.stdin.write(_transcript(messages).encode('utf-8'))
        proc.stdin.close()
        result = None
        for raw in proc.stdout:
            try:
                event = json.loads(raw)
            except ValueError:
                continue
            if event.get('type') == 'stream_event':
                delta = event['event'].get('delta') or {}
                if delta.get('type') == 'text_delta':
                    yield 'text', delta['text']
            elif event.get('type') == 'result':
                result = event
        proc.wait()
        if result is None:
            if not timer.is_alive():
                raise TutorError('The tutor took too long to answer. Please try again.')
            stderr.seek(0)
            detail = stderr.read().decode('utf-8', 'replace').strip()[-500:]
            raise TutorError(f'Claude Code stopped unexpectedly. {detail}'.strip())
        if result.get('is_error'):
            message = str(result.get('result') or result.get('subtype') or 'unknown error')
            if 'log in' in message.lower() or 'login' in message.lower():
                message = 'Claude Code is not signed in. Open Claude Code in VS Code and sign in, then try again.'
            raise TutorError(message)
        yield 'final', SimpleNamespace(stop_reason=result.get('stop_reason') or 'end_turn')
    finally:
        timer.cancel()
        if proc.poll() is None:  # the learner left mid-answer, or something failed
            proc.kill()
            proc.wait()
        stderr.close()
        shutil.rmtree(workdir, ignore_errors=True)


GEMINI_MODEL = os.environ.get('LEARN_GEMINI_MODEL', 'gemini-flash-latest')
GEMINI_MAX_TOKENS = 8192
# Gemini finish reasons that mean "declined", like Claude's refusal stop reason.
GEMINI_DECLINED = {'SAFETY', 'PROHIBITED_CONTENT', 'BLOCKLIST', 'SPII', 'RECITATION'}


def _stream_via_gemini(system, messages):
    """Ask Google Gemini (free API key from Google AI Studio)."""
    from google import genai
    from google.genai import types

    if not gemini_key():
        raise TutorError('No Gemini key: add GEMINI_API_KEY=... to the .env file, then restart the server.')
    client = genai.Client(api_key=gemini_key())
    contents = [
        {'role': 'user' if m['role'] == 'user' else 'model', 'parts': [{'text': m['content']}]}
        for m in messages
    ]
    config = types.GenerateContentConfig(
        system_instruction='\n\n'.join(block['text'] for block in system),
        max_output_tokens=GEMINI_MAX_TOKENS,
    )
    finish = None
    for chunk in client.models.generate_content_stream(model=GEMINI_MODEL, contents=contents, config=config):
        if chunk.text:
            yield 'text', chunk.text
        if chunk.candidates and chunk.candidates[0].finish_reason:
            finish = chunk.candidates[0].finish_reason
    name = getattr(finish, 'name', str(finish or ''))
    stop = 'refusal' if name in GEMINI_DECLINED else 'max_tokens' if name == 'MAX_TOKENS' else 'end_turn'
    yield 'final', SimpleNamespace(stop_reason=stop)


def _gemini_error(exc):
    """A readable message for google-genai errors, or None if it isn't one."""
    try:
        from google.genai import errors
    except ImportError:
        return None
    if not isinstance(exc, errors.APIError):
        return None
    if exc.code == 429:
        return 'Gemini\'s free daily limit is used up. Try again later (it resets every day).'
    if exc.code in (400, 401, 403) and 'key' in str(exc).lower():
        return 'Gemini rejected the API key. Check GEMINI_API_KEY in the .env file.'
    if exc.code == 404:
        return f'Gemini has no model called "{GEMINI_MODEL}". Set LEARN_GEMINI_MODEL in .env to a current model name.'
    if exc.code >= 500:
        return 'Gemini is having trouble right now. Please try again in a moment.'
    return f'Gemini rejected the request ({exc.code}): {exc.message}'


def friendly_error(exc):
    """Turn SDK exceptions into a message a learner can act on."""
    if isinstance(exc, TutorError):
        return str(exc)
    gemini_message = _gemini_error(exc)
    if gemini_message:
        return gemini_message
    missing_credentials = isinstance(exc, TypeError) and 'authentication method' in str(exc)
    if missing_credentials or isinstance(exc, (anthropic.AuthenticationError, anthropic.CredentialsError)):
        return ('The tutor needs an Anthropic API key. Add ANTHROPIC_API_KEY=... to the .env file '
                'in the project folder, then restart the server.')
    if isinstance(exc, anthropic.PermissionDeniedError):
        return 'Your API key does not have access to this model. Check LEARN_TUTOR_MODEL or your key.'
    if isinstance(exc, anthropic.RateLimitError):
        return 'The tutor is getting too many requests right now. Wait a minute and try again.'
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return 'The AI service is having trouble right now. Please try again in a moment.'
        return f'The tutor request was rejected ({exc.status_code}): {exc.message}'
    if isinstance(exc, anthropic.APIConnectionError):
        return 'Could not reach the AI service. Check your internet connection.'
    return f'The tutor ran into a problem: {exc}'
