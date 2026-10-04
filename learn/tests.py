import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils.html import escape

from . import gamification, notebook, tutor
from .exercises import get_exercise, list_tests, load_exercises, run_selection, run_tests
from .models import ExerciseProgress, NotebookEntry, TutorMessage, XPEvent


class ExerciseContentTests(TestCase):
    """Every reference solution passes its grader and every starter does not."""

    def test_solutions_pass(self):
        for exercise in load_exercises():
            with self.subTest(exercise=exercise.slug):
                result = run_tests(exercise, exercise.solution)
                failures = [t for t in result['tests'] if t['outcome'] != 'passed']
                self.assertTrue(result['all_passed'], result.get('error') or failures)
                self.assertEqual({t['id'] for t in result['tests']}, {t['id'] for t in list_tests(exercise)})

    def test_starters_fail(self):
        for exercise in load_exercises():
            with self.subTest(exercise=exercise.slug):
                result = run_tests(exercise, exercise.starter)
                self.assertFalse(result['all_passed'])

    def test_syntax_error_is_reported(self):
        exercise = load_exercises()[0]
        result = run_tests(exercise, 'def broken(:\n    pass\n')
        self.assertEqual(result['status'], 'load_error')
        self.assertIn('SyntaxError', result['error'])

    def test_every_exercise_has_quiz_and_hints(self):
        for exercise in load_exercises():
            with self.subTest(exercise=exercise.slug):
                self.assertTrue(exercise.hints)
                self.assertTrue(exercise.quiz)
                for question in exercise.quiz:
                    self.assertLess(question['answer'], len(question['options']))


class LearnViewTests(TestCase):
    def test_dashboard_lists_exercises(self):
        response = self.client.get('/learn/')
        self.assertEqual(response.status_code, 200)
        for exercise in load_exercises():
            self.assertContains(response, escape(exercise.title))

    def test_exercise_page(self):
        exercise = load_exercises()[0]
        response = self.client.get(f'/learn/{exercise.slug}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, exercise.file)

    def test_unknown_exercise_404(self):
        self.assertEqual(self.client.get('/learn/does-not-exist/').status_code, 404)

    def test_run_saves_progress(self):
        exercise = load_exercises()[0]
        response = self.client.post(
            f'/learn/{exercise.slug}/run/', {'code': exercise.solution}, content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['all_passed'])
        progress = ExerciseProgress.objects.get(slug=exercise.slug)
        self.assertTrue(progress.passed)
        self.assertEqual(progress.attempts, 1)

    def test_run_blocked_for_remote_clients(self):
        exercise = load_exercises()[0]
        response = self.client.post(
            f'/learn/{exercise.slug}/run/', {'code': ''}, content_type='application/json', REMOTE_ADDR='203.0.113.5',
        )
        self.assertEqual(response.status_code, 403)

    def test_quiz_scores_answers(self):
        exercise = load_exercises()[0]
        answers = [q['answer'] for q in exercise.quiz]
        response = self.client.post(f'/learn/{exercise.slug}/quiz/', {'answers': answers}, content_type='application/json')
        self.assertEqual(response.json()['correct'], len(answers))
        self.assertEqual(ExerciseProgress.objects.get(slug=exercise.slug).quiz_correct, len(answers))


class GamificationTests(TestCase):
    def setUp(self):
        self.exercise = load_exercises()[0]  # week 1
        self.url = f'/learn/{self.exercise.slug}'

    def run_code(self, code):
        return self.client.post(f'{self.url}/run/', {'code': code}, content_type='application/json').json()

    def test_passing_awards_xp_once(self):
        xp = self.run_code(self.exercise.solution)['xp']
        labels = [g['label'] for g in xp['gained']]
        self.assertIn('Daily practice', labels)
        self.assertIn('First-try bonus', labels)
        self.assertIn('No-peek bonus', labels)
        self.assertTrue(any(label.startswith('Completed') for label in labels))
        self.assertIn('Badge: Hello, World', labels)
        self.assertEqual(xp['badges'][0]['name'], 'Hello, World')
        # Running the same passing code again pays nothing new.
        self.assertEqual(self.run_code(self.exercise.solution)['xp']['total_gained'], 0)

    def test_partial_progress_earns_test_xp(self):
        xp = self.run_code(self.exercise.starter)['xp']
        self.assertEqual(xp['total_gained'], gamification.DAILY_XP)  # starter passes 0 tests
        partial = self.exercise.solution.replace('return method.upper() in SAFE_METHODS', 'return False')
        xp = self.run_code(partial)['xp']
        self.assertTrue(any('new tests passing' in g['label'] for g in xp['gained']))
        self.assertEqual(ExerciseProgress.objects.get(slug=self.exercise.slug).passed, False)

    def test_peeking_forfeits_no_peek_bonus(self):
        self.client.post(f'{self.url}/solution/')
        labels = [g['label'] for g in self.run_code(self.exercise.solution)['xp']['gained']]
        self.assertNotIn('No-peek bonus', labels)
        self.assertTrue(any(label.startswith('Completed') for label in labels))

    def test_first_try_only_on_first_run(self):
        self.run_code(self.exercise.starter)
        labels = [g['label'] for g in self.run_code(self.exercise.solution)['xp']['gained']]
        self.assertNotIn('First-try bonus', labels)

    def test_quiz_xp_only_first_attempt(self):
        answers = [q['answer'] for q in self.exercise.quiz]
        first = self.client.post(f'{self.url}/quiz/', {'answers': answers}, content_type='application/json').json()
        expected = len(answers) * gamification.QUIZ_ANSWER_XP + gamification.PERFECT_QUIZ_XP + gamification.DAILY_XP
        self.assertEqual(first['xp']['total_gained'], expected)
        again = self.client.post(f'{self.url}/quiz/', {'answers': answers}, content_type='application/json').json()
        self.assertEqual(again['xp']['total_gained'], 0)
        self.assertFalse(again['xp']['first_attempt'])

    def test_levels(self):
        self.assertEqual(gamification.level_for(0)['number'], 1)
        self.assertEqual(gamification.level_for(149)['to_next'], 1)
        self.assertEqual(gamification.level_for(150)['title'], 'Junior Developer')
        top = gamification.level_for(99_999)
        self.assertEqual((top['number'], top['next'], top['percent']), (len(gamification.LEVELS), None, 100))

    def test_streaks(self):
        from datetime import date
        days = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 10), date(2026, 9, 11)]
        self.assertEqual(gamification.streaks(days, today=date(2026, 9, 11)), (2, 3))
        self.assertEqual(gamification.streaks(days, today=date(2026, 9, 12)), (2, 3))  # still alive until the day ends
        self.assertEqual(gamification.streaks(days, today=date(2026, 9, 13)), (0, 3))
        self.assertEqual(gamification.streaks([], today=date(2026, 9, 13)), (0, 0))

    def test_dashboard_shows_player(self):
        self.run_code(self.exercise.solution)
        response = self.client.get('/learn/')
        self.assertContains(response, 'Hello, World')
        self.assertContains(response, 'id="hud-xp"')


class FakeStream:
    def __init__(self, chunks, stop_reason):
        self.chunks, self.stop_reason = chunks, stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @property
    def text_stream(self):
        return iter(self.chunks)

    def get_final_message(self):
        return SimpleNamespace(stop_reason=self.stop_reason)


class FakeClient:
    """Stands in for anthropic.Anthropic() and records each request."""

    def __init__(self, chunks=('Great ', 'question!'), stop_reason='end_turn', error=None):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))
        self.chunks, self.stop_reason, self.error = chunks, stop_reason, error

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return FakeStream(self.chunks, self.stop_reason)


class TutorTests(TestCase):
    def setUp(self):
        self.exercise = load_exercises()[0]
        self.client_fake = FakeClient()
        for patcher in [
            mock.patch('learn.tutor.get_client', return_value=self.client_fake),
            mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'api'}),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def ask(self, question='What is a query string?', topic=None, remote_addr='127.0.0.1', **extra):
        topic = topic or self.exercise.slug
        response = self.client.post(
            f'/learn/tutor/{topic}/ask/', {'question': question, **extra},
            content_type='application/json', REMOTE_ADDR=remote_addr,
        )
        if response.streaming:
            events = [json.loads(line) for line in b''.join(response.streaming_content).decode().splitlines() if line]
            return response, events
        return response, None

    def test_streams_and_saves_answer(self):
        _, events = self.ask(code='def parse_request(raw): ...')
        self.assertEqual([e['type'] for e in events], ['text', 'text', 'done'])
        self.assertEqual(events[-1]['text'], 'Great question!')
        user, assistant = TutorMessage.objects.filter(topic=self.exercise.slug)
        self.assertEqual(user.display, 'What is a query string?')
        self.assertIn('def parse_request(raw)', user.content)
        self.assertEqual(assistant.content, 'Great question!')

    def test_request_shape(self):
        result = {'passed': 1, 'total': 2, 'tests': [
            {'outcome': 'passed', 'description': 'Reads the method'},
            {'outcome': 'failed', 'description': 'Parses the query', 'message': "{} != {'a': '1'}"},
        ]}
        self.ask(code='print("hi")', result=result)
        call = self.client_fake.calls[0]
        self.assertEqual(call['model'], tutor.TUTOR_MODEL)
        self.assertEqual(call['fallbacks'], 'default')
        self.assertIn('server-side-fallback-2026-07-01', call['betas'])
        system_text = ''.join(block['text'] for block in call['system'])
        self.assertIn(self.exercise.title, system_text)
        self.assertIn('<reference_solution>', system_text)
        turn = call['messages'][-1]['content']
        self.assertIn('<learner_state>', turn)
        self.assertIn('print("hi")', turn)
        self.assertIn('[failed] Parses the query', turn)
        self.assertIn('not passed yet', turn)

    def test_history_is_sent_in_order(self):
        self.ask('First question')
        self.ask('Second question')
        messages = self.client_fake.calls[1]['messages']
        self.assertEqual([m['role'] for m in messages], ['user', 'assistant', 'user'])
        self.assertTrue(messages[0]['content'].endswith('First question'))
        self.assertTrue(messages[2]['content'].endswith('Second question'))

    def test_refusal_is_not_saved(self):
        self.client_fake.stop_reason = 'refusal'
        _, events = self.ask()
        self.assertEqual(events[-1]['type'], 'error')
        self.assertTrue(events[-1]['discard'])
        self.assertFalse(TutorMessage.objects.exists())

    def test_missing_api_key_message(self):
        self.client_fake.error = TypeError('Could not resolve authentication method. Expected one of api_key')
        _, events = self.ask()
        self.assertEqual(events, [{'type': 'error', 'error': tutor.friendly_error(self.client_fake.error)}])
        self.assertIn('ANTHROPIC_API_KEY', events[0]['error'])

    def test_general_tutor(self):
        _, events = self.ask('What is REST?', topic='general')
        self.assertEqual(events[-1]['type'], 'done')
        call = self.client_fake.calls[0]
        self.assertIn('<course>', call['system'][1]['text'])
        self.assertEqual(call['messages'][-1]['content'], 'What is REST?')
        self.assertContains(self.client.get('/learn/tutor/'), 'What is REST?')

    def test_validation_and_access(self):
        response, _ = self.ask('   ')
        self.assertEqual(response.status_code, 400)
        response, _ = self.ask(topic='no-such-exercise')
        self.assertEqual(response.status_code, 404)
        response, _ = self.ask(remote_addr='203.0.113.5')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client_fake.calls, [])

    def test_clear_and_exercise_tab(self):
        self.ask()
        self.client.post(f'/learn/tutor/{self.exercise.slug}/clear/')
        self.assertFalse(TutorMessage.objects.exists())
        self.assertContains(self.client.get(f'/learn/{self.exercise.slug}/'), 'Tutor ✨')


class FakeProcess:
    """Stands in for the claude.exe subprocess."""

    def __init__(self, events):
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None  # keep what was written readable
        self.stdout = [json.dumps(e).encode() + b'\n' for e in events]
        self.returncode = 0

    def wait(self):
        return 0

    def poll(self):
        return 0

    def kill(self):
        pass


def text_event(text):
    return {'type': 'stream_event', 'event': {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': text}}}


class ClaudeCodeBackendTests(TestCase):
    def setUp(self):
        patcher = mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'claude_code', 'LEARN_CLAUDE_CLI': 'claude.exe'})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.system = tutor.build_system(load_exercises()[0])

    def run_cli(self, events, messages=None):
        process = FakeProcess(events)
        with mock.patch('learn.tutor.subprocess.Popen', return_value=process) as popen:
            output = list(tutor.stream_reply(self.system, messages or [{'role': 'user', 'content': 'What is HTTP?'}]))
        return output, popen.call_args, process

    def test_streams_text_and_final(self):
        events = [
            {'type': 'system', 'subtype': 'init'}, text_event('Hel'), text_event('lo'),
            {'type': 'result', 'subtype': 'success', 'is_error': False, 'stop_reason': 'end_turn', 'result': 'Hello'},
        ]
        output, _, process = self.run_cli(events)
        self.assertEqual([o for o in output if o[0] == 'text'], [('text', 'Hel'), ('text', 'lo')])
        self.assertEqual(output[-1][1].stop_reason, 'end_turn')
        self.assertEqual(process.stdin.getvalue().decode(), 'What is HTTP?')

    def test_command_is_locked_down(self):
        _, call, _ = self.run_cli([{'type': 'result', 'is_error': False, 'stop_reason': 'end_turn'}])
        command = call.args[0]
        self.assertEqual(command[:2], ['claude.exe', '-p'])
        self.assertIn('--safe-mode', command)
        self.assertEqual(command[command.index('--tools') + 1], '')
        self.assertIn('--no-session-persistence', command)
        self.assertIn('<reference_solution>', command[command.index('--system-prompt') + 1])

    def test_history_becomes_transcript(self):
        messages = [
            {'role': 'user', 'content': '<learner_state>old code</learner_state>\n\nFirst?', 'display': 'First?'},
            {'role': 'assistant', 'content': 'Answer one', 'display': 'Answer one'},
            {'role': 'user', 'content': '<learner_state>new code</learner_state>\n\nSecond?'},
        ]
        _, _, process = self.run_cli([{'type': 'result', 'is_error': False}], messages)
        prompt = process.stdin.getvalue().decode()
        self.assertIn('<learner>\nFirst?\n</learner>', prompt)
        self.assertIn('<tutor>\nAnswer one\n</tutor>', prompt)
        self.assertNotIn('old code', prompt)
        self.assertTrue(prompt.endswith('<learner_state>new code</learner_state>\n\nSecond?'))

    def test_errors_are_friendly(self):
        with self.assertRaisesRegex(tutor.TutorError, 'not signed in'):
            self.run_cli([{'type': 'result', 'is_error': True, 'result': 'Not logged in · Please run /login'}])
        with self.assertRaisesRegex(tutor.TutorError, 'usage limit'):
            self.run_cli([{'type': 'result', 'is_error': True, 'result': 'Claude usage limit reached'}])
        with self.assertRaisesRegex(tutor.TutorError, 'stopped unexpectedly'):
            self.run_cli([text_event('partial')])

    def test_backend_choice(self):
        with mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'auto', 'ANTHROPIC_API_KEY': 'sk-test'}):
            self.assertEqual(tutor.backend(), 'api')
        with mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'auto', 'ANTHROPIC_API_KEY': ''}), \
                mock.patch('learn.tutor.find_claude_cli', return_value='claude.exe'):
            self.assertEqual(tutor.backend(), 'claude_code')

    def test_finds_newest_bundled_cli(self):
        with tempfile.TemporaryDirectory() as home:
            for version in ['2.1.9', '2.1.282', '2.1.40']:
                folder = Path(home, '.vscode', 'extensions', f'anthropic.claude-code-{version}-win32-x64',
                              'resources', 'native-binary')
                folder.mkdir(parents=True)
                (folder / 'claude.exe').write_text('')
            with mock.patch.dict('os.environ', {'LEARN_CLAUDE_CLI': ''}), \
                    mock.patch('learn.tutor.shutil.which', return_value=None), \
                    mock.patch('learn.tutor.Path.home', return_value=Path(home)):
                self.assertIn('claude-code-2.1.282', tutor.find_claude_cli())


class DeploymentTests(TestCase):
    """A public deployment (LEARN_REQUIRE_LOGIN=True) is locked to staff logins."""

    def setUp(self):
        self.exercise = get_exercise('http-requests')
        self.staff = User.objects.create_user('owner', password='pw', is_staff=True)

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_pages_need_login(self):
        response = self.client.get('/learn/')
        self.assertRedirects(response, '/admin/login/?next=%2Flearn%2F', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/admin/login/').status_code, 200)

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_running_code_needs_login_even_from_localhost(self):
        url = f'/learn/{self.exercise.slug}/run-selection/'
        body = {'code': '', 'selection': '1 + 1', 'start_line': 1, 'end_line': 1}
        response = self.client.post(url, body, content_type='application/json')
        self.assertEqual(response.status_code, 302)

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_staff_can_use_everything(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/learn/').status_code, 200)
        url = f'/learn/{self.exercise.slug}/run-selection/'
        body = {'code': '', 'selection': '1 + 1', 'start_line': 1, 'end_line': 1}
        response = self.client.post(url, body, content_type='application/json', REMOTE_ADDR='203.0.113.5')
        self.assertEqual(response.json()['output'], '2\n')

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_non_staff_users_are_kept_out(self):
        self.client.force_login(User.objects.create_user('visitor', password='pw'))
        self.assertEqual(self.client.get('/learn/').status_code, 302)

    def test_python_executable_under_a_web_server(self):
        from learn.exercises import python_executable
        with tempfile.TemporaryDirectory() as prefix:
            python = Path(prefix, 'bin', 'python3')
            python.parent.mkdir()
            python.write_text('')
            with mock.patch('learn.exercises.sys.executable', '/usr/local/bin/uwsgi'), \
                    mock.patch('learn.exercises.sys.prefix', prefix), \
                    mock.patch.dict('os.environ', {'LEARN_PYTHON': ''}):
                self.assertEqual(python_executable(), str(python))


class SiteNavigationTests(TestCase):
    def test_home_opens_backend_lab(self):
        self.assertRedirects(self.client.get('/'), '/learn/', fetch_redirect_response=False)

    def test_slides_pdf(self):
        exercise = get_exercise('http-requests')
        pdf = Path(settings.BASE_DIR) / 'materials' / 'out' / 'pdf' / '01-http-requests.pdf'
        response = self.client.get(f'/learn/{exercise.slug}/slides/')
        if pdf.exists():
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertContains(self.client.get(f'/learn/{exercise.slug}/'), '📑 Slides')
        else:
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/learn/no-such-exercise/slides/').status_code, 404)


class NotebookTests(TestCase):
    PAGE = {
        'summary': 'You parsed a raw HTTP request.',
        'tools': [{'name': 'str.partition', 'what_it_does': 'Splits once.', 'example': 'print("a:b".partition(":"))',
                   'output': "('a', ':', 'b')"}],
        'use_case': 'Reading requests in a server.',
        'difficulties': [{'what': 'Where raw comes from', 'why_it_was_hard': 'Parameters were new.',
                          'how_you_solved_it': 'The tutor explained the tests pass it in.'}],
        'takeaways': ['partition splits once'],
        'next_step': 'Try exercise 2.',
    }

    def setUp(self):
        self.exercise = get_exercise('http-requests')
        self.url = f'/learn/notebook/{self.exercise.slug}/generate/'

    def fake_reply(self, text):
        return mock.patch('learn.tutor.stream_reply', return_value=iter([
            ('text', text), ('final', SimpleNamespace(stop_reason='end_turn')),
        ]))

    def test_lesson_tools_are_read_from_the_lesson(self):
        tools = notebook.lesson_tools(self.exercise)
        self.assertIn('urlsplit(address)', tools)
        self.assertIn('text.partition(separator)', tools)

    def test_evidence_includes_chat_timeline_and_code(self):
        ExerciseProgress.objects.create(slug=self.exercise.slug, passed=True, attempts=7, code='def parse_request(raw): ...')
        TutorMessage.objects.create(topic=self.exercise.slug, role='user', content='x', display='where is raw?')
        XPEvent.objects.create(key=f'tests:{self.exercise.slug}:1', slug=self.exercise.slug, label='Tests passing', amount=5)
        evidence = notebook.build_evidence(self.exercise)
        self.assertIn('Test runs before passing: 7', evidence)
        self.assertIn('where is raw?', evidence)
        self.assertIn('Tests passing', evidence)
        self.assertIn('def parse_request(raw)', evidence)

    def test_generate_requires_passing(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_generate_saves_page(self):
        ExerciseProgress.objects.create(slug=self.exercise.slug, passed=True)
        with self.fake_reply('Here you go:\n```json\n' + json.dumps(self.PAGE) + '\n```'):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(NotebookEntry.objects.get(slug=self.exercise.slug).data['summary'], self.PAGE['summary'])
        page = self.client.get('/learn/notebook/')
        self.assertContains(page, 'You parsed a raw HTTP request.')

    def test_bad_reply_is_reported(self):
        ExerciseProgress.objects.create(slug=self.exercise.slug, passed=True)
        with self.fake_reply('Sorry, no JSON here'):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 502)
        self.assertFalse(NotebookEntry.objects.exists())

    def test_page_lists_locked_exercises(self):
        response = self.client.get('/learn/notebook/')
        self.assertContains(response, 'My notebook')
        self.assertContains(response, 'Kill the N+1 query')


class RunSelectionTests(TestCase):
    """Running highlighted code: the rest of the file loads, then the selection runs."""

    def setUp(self):
        self.exercise = get_exercise('http-requests')
        self.code = self.exercise.solution + '\nprint("context line")\nRAW = "GET /a/?x=1 HTTP/1.1\\r\\nHost: h\\r\\n\\r\\n"\n'
        self.lines = self.code.splitlines()

    def run_sel(self, text, start, end, code=None, exercise=None):
        return run_selection(exercise or self.exercise, code or self.code, text, start, end)

    def line_of(self, text):
        return self.lines.index(text) + 1

    def test_uses_file_definitions_and_echoes_value(self):
        extra = self.code + 'parse_request(RAW)["query"]\n'
        n = len(extra.splitlines())
        result = self.run_sel('parse_request(RAW)["query"]', n, n, code=extra)
        self.assertEqual(result['status'], 'ok', result)
        self.assertEqual(result['output'], "context line\n{'x': '1'}\n")

    def test_selected_statement_runs_once(self):
        line = self.line_of('print("context line")')
        result = self.run_sel('print("context line")', line, line)
        self.assertEqual(result['output'], 'context line\n')

    def test_indented_selection_is_dedented(self):
        result = self.run_sel('        x = 2 + 3\n        x * 10', 7, 8)
        self.assertEqual(result['status'], 'ok', result)
        self.assertTrue(result['output'].endswith('50\n'))

    def test_syntax_error_in_selection(self):
        result = self.run_sel('def broken(:', 1, 1)
        self.assertEqual(result['status'], 'error')
        self.assertIn('SyntaxError in your selection', result['error'])
        self.assertTrue(result['notes'])

    def test_error_points_at_selection_and_file(self):
        line = self.line_of('print("context line")')
        result = self.run_sel('parse_request("nonsense")', line, line)
        self.assertEqual(result['status'], 'error')
        self.assertIn('ValueError', result['error'])
        self.assertIn('<selection>, line 1', result['error'])
        self.assertIn('http_parser.py, line', result['error'])

    def test_parameter_name_error_is_explained(self):
        result = self.run_sel('head, _, body = raw.partition("x")', 7, 7)
        self.assertIn("NameError: name 'raw' is not defined", result['error'])
        self.assertIn('`raw` is a parameter of parse_request()', ' '.join(result['notes']))

    def test_file_with_syntax_error_still_runs_selection(self):
        result = self.run_sel('1 + 1', 1, 1, code='def broken(:\n')
        self.assertEqual(result['output'], '2\n')
        self.assertIn('syntax error', result['notes'][0])

    def test_model_exercise_can_use_database(self):
        models = get_exercise('models')
        result = self.run_sel('Book.objects.create(title="Dune", author="H")\nBook.objects.count()', 1, 1,
                              code=models.solution, exercise=models)
        self.assertEqual(result['output'], '1\n', result)

    def test_view(self):
        url = f'/learn/{self.exercise.slug}/run-selection/'
        body = {'code': self.code, 'selection': '2 ** 10', 'start_line': 1, 'end_line': 1}
        response = self.client.post(url, body, content_type='application/json')
        self.assertTrue(response.json()['output'].endswith('1024\n'))
        self.assertEqual(self.client.post(url, {**body, 'selection': '  '}, content_type='application/json').status_code, 400)
        remote = self.client.post(url, body, content_type='application/json', REMOTE_ADDR='203.0.113.5')
        self.assertEqual(remote.status_code, 403)


class SingleTestRunTests(TestCase):
    def setUp(self):
        self.exercise = get_exercise('http-requests')
        self.url = f'/learn/{self.exercise.slug}/run/'

    def test_list_tests_in_order(self):
        tests = list_tests(self.exercise)
        self.assertEqual(tests[0]['id'], 'ParseRequestTests.test_01_method_and_version')
        self.assertEqual(tests[-1]['id'], 'SafeMethodTests.test_09_unsafe_methods')
        self.assertEqual(tests[0]['description'], 'Reads the method and HTTP version from the request line')

    def test_runs_only_one_test_without_xp(self):
        body = {'code': self.exercise.solution, 'test': 'SafeMethodTests.test_08_safe_methods'}
        data = self.client.post(self.url, body, content_type='application/json').json()
        self.assertEqual([t['id'] for t in data['tests']], ['SafeMethodTests.test_08_safe_methods'])
        self.assertTrue(data['single'])
        self.assertNotIn('xp', data)
        progress = ExerciseProgress.objects.get(slug=self.exercise.slug)
        self.assertFalse(progress.passed)
        self.assertEqual(progress.attempts, 1)
        self.assertFalse(XPEvent.objects.exists())

    def test_unknown_test_rejected(self):
        body = {'code': self.exercise.solution, 'test': 'Nope.test_x'}
        self.assertEqual(self.client.post(self.url, body, content_type='application/json').status_code, 400)

    def test_page_shows_tests_and_run_selection(self):
        response = self.client.get(f'/learn/{self.exercise.slug}/')
        self.assertContains(response, 'Run selection')
        self.assertContains(response, 'SafeMethodTests.test_08_safe_methods')
