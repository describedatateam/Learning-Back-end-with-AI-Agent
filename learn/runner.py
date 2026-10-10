"""Standalone grader: runs an exercise's tests against the learner's code.

Executed in a subprocess (never imported by the web app) as:

    python runner.py <workdir> <learner_file>                  # all grader tests
    python runner.py <workdir> <learner_file> --test Class.m   # one grader test
    python runner.py <workdir> <learner_file> --scratch F      # run selected code
    python runner.py <workdir> <learner_file> --snippet        # run a plain script (flashcards)

The workdir contains the learner's file, any support files, and
``grader_tests.py``. For --scratch, F is a JSON file with the selected text and
its line range. The result is printed to stdout as one JSON object on the last
line, prefixed with RESULT_MARKER.
"""
import argparse
import ast
import contextlib
import io
import json
import os
import sys
import textwrap
import traceback
import types
import unittest

RESULT_MARKER = '@@LEARN_RESULT@@'
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CPU_SECONDS = 20                 # the web app also stops the run after 20 seconds of wall time
MEMORY_BYTES = 512 * 1024 ** 2   # Django and the tests need about 60 MB
FILE_BYTES = 10 * 1024 ** 2      # largest file the code may write
BLOCKED_EVENTS = {
    # Starting programs, loading C libraries and opening network connections.
    'os.system', 'os.exec', 'os.posix_spawn', 'os.spawn', 'os.fork', 'os.forkpty', 'subprocess.Popen',
    'ctypes.dlopen', 'ctypes.dlsym', 'ctypes.call_function', 'socket.connect', 'socket.bind', 'socket.getaddrinfo',
}
SELECTION = '<selection>'
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def short_traceback(err, workdir, sources=None):
    """Keep only the frames that point at the learner's code.

    `sources` maps pseudo-filenames such as "<selection>" to their text, so
    those frames can show the offending line too.
    """
    sources = sources or {}
    exc_type, exc_value, tb = err
    lines = []
    for frame in traceback.extract_tb(tb):
        if frame.filename in sources:
            code_lines = sources[frame.filename].splitlines()
            text = code_lines[frame.lineno - 1].strip() if 0 < frame.lineno <= len(code_lines) else ''
            lines.append(f'  {frame.filename}, line {frame.lineno}\n    {text}')
        elif frame.filename.startswith(workdir):
            lines.append(f'  {os.path.relpath(frame.filename, workdir)}, line {frame.lineno}, in {frame.name}\n    {frame.line}')
    message = ''.join(traceback.format_exception_only(exc_type, exc_value)).strip()
    return message, '\n'.join(lines[-3:])


class JsonResult(unittest.TestResult):
    def __init__(self, workdir):
        super().__init__()
        self.workdir = workdir
        self.records = []

    def _record(self, test, outcome, err=None):
        doc = (test._testMethodDoc or '').strip().splitlines()
        record = {
            'id': f'{type(test).__name__}.{test._testMethodName}',
            'name': test._testMethodName,
            'description': doc[0] if doc else test._testMethodName.replace('_', ' '),
            'outcome': outcome,
            'message': '',
            'trace': '',
        }
        if err is not None:
            if outcome == 'failed':
                # Assertion messages are the useful part; skip the frames.
                record['message'] = str(err[1]).strip()
            else:
                record['message'], record['trace'] = short_traceback(err, self.workdir)
        self.records.append(record)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, 'passed')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, 'failed', err)

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, 'error', err)


def configure_django():
    import django
    from django.conf import settings

    settings.configure(
        DEBUG=True,
        SECRET_KEY='learn-sandbox-not-secret',
        ALLOWED_HOSTS=['*'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'rest_framework',
            'sandbox',
        ],
        MIDDLEWARE=[],
        ROOT_URLCONF='sandbox',
        USE_TZ=True,
        TIME_ZONE='UTC',
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
        REST_FRAMEWORK={
            'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.BasicAuthentication'],
            'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
        },
    )
    django.setup()


def limit_resources():
    """Cap CPU time, memory and file size, so one run can't slow the server down (Linux and macOS)."""
    try:
        import resource
    except ImportError:  # Windows: only the web app's timeout applies
        return
    for limit, value in ((resource.RLIMIT_CPU, CPU_SECONDS), (resource.RLIMIT_AS, MEMORY_BYTES),
                         (resource.RLIMIT_FSIZE, FILE_BYTES)):
        try:
            soft, hard = resource.getrlimit(limit)
            capped = value if hard == resource.RLIM_INFINITY else min(value, hard)
            resource.setrlimit(limit, (capped, hard))
        except (ValueError, OSError):
            pass  # some hosts don't allow a limit (e.g. RLIMIT_AS on macOS)


def install_guard(workdir):
    """Stop learner code from reading the site's files, starting programs or using the network.

    An audit hook can't be removed once added. Files are allowed in the run's own
    folder and in Python's installation (so imports work); anything else inside
    the project (the .env secrets, the database, the reference solutions) or the
    home folder is refused. This is a safety net for invited learners, not a full
    sandbox: see the plan's "real code sandbox" item.
    """
    allowed = [os.path.realpath(p) for p in {workdir, sys.prefix, sys.base_prefix, sys.exec_prefix} if p]
    try:
        import site
        allowed.append(os.path.realpath(site.getusersitepackages()))
    except Exception:
        pass
    try:
        import pwd
        home = pwd.getpwuid(os.getuid()).pw_dir  # HOME isn't passed to the runner
    except ImportError:  # Windows
        home = os.path.expanduser('~')
    protected = [PROJECT_DIR] + ([os.path.realpath(home)] if os.path.isabs(home) else [])

    def inside(path, folders):
        return any(path == f or path.startswith(f + os.sep) for f in folders)

    def hook(event, args):
        if event in BLOCKED_EVENTS:
            raise PermissionError(f'Exercises cannot do this ({event}).')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = os.path.realpath(os.fsdecode(args[0]))
            if inside(path, protected) and not inside(path, allowed):
                raise PermissionError(f'Exercises can only open files in their own folder, not {os.fsdecode(args[0])}.')

    sys.addaudithook(hook)


def prepare(workdir):
    workdir = os.path.abspath(workdir)
    sys.path.insert(0, workdir)
    os.chdir(workdir)
    # `sandbox` is a throwaway Django app so learner/support models get tables.
    os.makedirs('sandbox', exist_ok=True)
    init = os.path.join('sandbox', '__init__.py')
    if not os.path.exists(init):
        with open(init, 'w') as fh:
            fh.write('urlpatterns = []\n')
    limit_resources()
    install_guard(workdir)
    return workdir


def syntax_error(source, filename):
    try:
        compile(source, filename, 'exec')
    except SyntaxError as exc:
        return f'SyntaxError in {filename}, line {exc.lineno}: {exc.msg}\n    {(exc.text or "").rstrip()}'
    return None


def run(workdir, learner_file, test_id=None):
    workdir = prepare(workdir)
    captured = io.StringIO()
    result = {'status': 'ok', 'tests': [], 'stdout': '', 'error': None}

    # 1. Syntax check gives a friendlier message than an import traceback.
    with open(learner_file, encoding='utf-8') as fh:
        error = syntax_error(fh.read(), learner_file)
    if error:
        result['status'], result['error'] = 'load_error', error
        return result

    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        # 2. Boot Django and import the grader (which imports the learner's code).
        try:
            configure_django()
            import grader_tests
            from django.core.management import call_command
            call_command('migrate', run_syncdb=True, verbosity=0)
        except Exception:
            message, trace = short_traceback(sys.exc_info(), workdir)
            result['status'] = 'load_error'
            result['error'] = f'Your code could not be loaded:\n{message}' + (f'\n\n{trace}' if trace else '')
            result['stdout'] = captured.getvalue()
            return result

        # 3. Run the tests (named test_01_..., so alphabetical = written order).
        loader = unittest.TestLoader()
        try:
            suite = loader.loadTestsFromName(test_id, grader_tests) if test_id else loader.loadTestsFromModule(grader_tests)
        except (AttributeError, ImportError):
            result['status'], result['error'] = 'load_error', f'There is no test called {test_id}.'
            return result
        json_result = JsonResult(workdir)
        suite.run(json_result)

    result['tests'] = json_result.records
    result['stdout'] = captured.getvalue()
    return result


def load_file_context(learner_file, start_line, end_line, notes):
    """Make the learner's file importable and return its namespace.

    Every top-level statement runs except the ones inside the selection, so
    selected code is not run twice. Definitions (def/class) always load, since
    re-running them is harmless. A failing statement is reported and skipped.
    """
    module_name = learner_file[:-3].replace('/', '.').replace('\\', '.')
    if module_name in sys.modules:  # e.g. sandbox/models.py, imported by Django
        return vars(sys.modules[module_name])

    path = os.path.abspath(learner_file)
    with open(path, encoding='utf-8') as fh:
        source = fh.read()
    module = types.ModuleType(module_name)
    module.__file__ = path
    sys.modules[module_name] = module
    for node in ast.parse(source, path).body:
        overlaps = node.lineno <= end_line and node.end_lineno >= start_line
        if overlaps and not isinstance(node, DEFINITIONS):
            continue
        try:
            exec(compile(ast.Module([node], type_ignores=[]), path, 'exec'), vars(module))
        except Exception as exc:
            notes.append(f'Line {node.lineno} of {learner_file} was skipped: {type(exc).__name__}: {exc}')
    return vars(module)


def explain_missing_name(name, learner_file):
    """If `name` only exists inside one of the learner's functions, say so."""
    try:
        with open(learner_file, encoding='utf-8') as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError):
        return None
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = [a.arg for a in func.args.posonlyargs + func.args.args + func.args.kwonlyargs]
        if name in params:
            return (f'`{name}` is a parameter of {func.name}(). It only has a value while that function '
                    f'is running, when the tests (or your code) call {func.name}(...) and pass it in. '
                    f'To try this line, first make a sample value, for example {name} = ..., '
                    f'or call {func.name}(...) with some data instead.')
        assigned = {t.id for node in ast.walk(func) if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign))
                    for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
                    if isinstance(t, ast.Name)}
        if name in assigned:
            return (f'`{name}` is a variable inside {func.name}(), so it only exists while that function runs. '
                    f'Highlight the lines that create it too, or give it a sample value first.')
    return None


def run_selection(workdir, learner_file, selection_path):
    """Run highlighted code like a Python shell: print the last expression's value."""
    workdir = prepare(workdir)
    with open(selection_path, encoding='utf-8') as fh:
        request = json.load(fh)
    selection = textwrap.dedent(request['text']).strip('\n')
    result = {'status': 'ok', 'output': '', 'error': None, 'notes': []}

    try:
        tree = ast.parse(selection, SELECTION)
    except SyntaxError as exc:
        result['status'] = 'error'
        result['error'] = f'SyntaxError in your selection, line {exc.lineno}: {exc.msg}\n    {(exc.text or "").rstrip()}'
        result['notes'].append('Tip: select whole statements, for example a full line or a whole function.')
        return result

    with open(learner_file, encoding='utf-8') as fh:
        file_error = syntax_error(fh.read(), learner_file)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        try:
            configure_django()
            from django.core.management import call_command
            call_command('migrate', run_syncdb=True, verbosity=0)
        except Exception:
            message, trace = short_traceback(sys.exc_info(), workdir)
            result['status'] = 'error'
            result['error'] = f'Your file could not be loaded:\n{message}' + (f'\n\n{trace}' if trace else '')
            result['output'] = captured.getvalue()
            return result

        if file_error:
            namespace = {'__name__': '__selection__'}
            result['notes'].append(f'Your file has a syntax error, so only the selection ran.\n{file_error}')
        else:
            namespace = load_file_context(learner_file, request['start_line'], request['end_line'], result['notes'])

        body, last = tree.body[:-1], tree.body[-1] if tree.body else None
        try:
            if isinstance(last, ast.Expr):
                exec(compile(ast.Module(body, type_ignores=[]), SELECTION, 'exec'), namespace)
                value = eval(compile(ast.Expression(last.value), SELECTION, 'eval'), namespace)
                if value is not None:
                    print(repr(value))
            else:
                exec(compile(tree, SELECTION, 'exec'), namespace)
        except Exception as exc:
            message, trace = short_traceback(sys.exc_info(), workdir, {SELECTION: selection})
            result['status'] = 'error'
            result['error'] = message + (f'\n\n{trace}' if trace else '')
            if isinstance(exc, NameError) and getattr(exc, 'name', None):
                hint = explain_missing_name(exc.name, learner_file)
                if hint:
                    result['notes'].append(hint)

    result['output'] = captured.getvalue()
    return result


def run_snippet(workdir, learner_file):
    """Run a short plain-Python file (a flashcard) and return what it printed."""
    workdir = prepare(workdir)
    with open(learner_file, encoding='utf-8') as fh:
        source = fh.read()
    result = {'status': 'ok', 'output': '', 'error': None}
    error = syntax_error(source, SNIPPET)
    if error:
        result['status'], result['error'] = 'error', error.replace(f'in {SNIPPET}, ', '')
        return result
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        try:
            exec(compile(source, SNIPPET, 'exec'), {'__name__': '__main__'})
        except BaseException:  # SystemExit and KeyboardInterrupt are the learner's too
            message, trace = short_traceback(sys.exc_info(), workdir, {SNIPPET: source})
            result['status'] = 'error'
            result['error'] = message + (f'\n\n{trace}' if trace else '')
    result['output'] = captured.getvalue()
    return result


SNIPPET = '<your code>'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('workdir')
    parser.add_argument('learner_file')
    parser.add_argument('--test')
    parser.add_argument('--scratch')
    parser.add_argument('--snippet', action='store_true')
    args = parser.parse_args()
    try:
        if args.snippet:
            outcome = run_snippet(args.workdir, args.learner_file)
        elif args.scratch:
            outcome = run_selection(args.workdir, args.learner_file, args.scratch)
        else:
            outcome = run(args.workdir, args.learner_file, args.test)
    except Exception:
        outcome = {'status': 'load_error', 'tests': [], 'stdout': '', 'output': '', 'error': traceback.format_exc()}
    sys.stdout.write('\n' + RESULT_MARKER + json.dumps(outcome) + '\n')
