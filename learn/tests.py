import io
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.html import escape

from . import gamification, notebook, tutor
from .exercises import get_exercise, list_tests, load_exercises, run_selection, run_tests
from .models import ExerciseProgress, InviteCode, LearningEvent, NotebookEntry, TutorMessage, XPEvent


class SignedInTestCase(TestCase):
    """Progress belongs to an account, so most tests run signed in."""

    def setUp(self):
        self.user = User.objects.create_user('learner', password='pw')
        self.client.force_login(self.user)


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


class LearnViewTests(SignedInTestCase):
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
        progress = ExerciseProgress.objects.get(user=self.user, slug=exercise.slug)
        self.assertTrue(progress.passed)
        self.assertEqual(progress.attempts, 1)

    def test_run_blocked_when_signed_out(self):
        exercise = load_exercises()[0]
        self.client.logout()
        response = self.client.post(
            f'/learn/{exercise.slug}/run/', {'code': ''}, content_type='application/json', REMOTE_ADDR='203.0.113.5',
        )
        self.assertEqual(response.status_code, 403)

    def test_quiz_scores_answers(self):
        exercise = load_exercises()[0]
        answers = [q['answer'] for q in exercise.quiz]
        response = self.client.post(f'/learn/{exercise.slug}/quiz/', {'answers': answers}, content_type='application/json')
        self.assertEqual(response.json()['correct'], len(answers))
        self.assertEqual(ExerciseProgress.objects.get(user=self.user, slug=exercise.slug).quiz_correct, len(answers))


class GamificationTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
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


class TutorTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.exercise = load_exercises()[0]
        self.client_fake = FakeClient()
        for patcher in [
            mock.patch('learn.tutor.get_client', return_value=self.client_fake),
            mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'api', 'GEMINI_API_KEY': '', 'GOOGLE_API_KEY': ''}),
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
        self.client.logout()
        response, _ = self.ask()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client_fake.calls, [])

    def test_clear_and_exercise_tab(self):
        self.ask()
        self.client.post(f'/learn/tutor/{self.exercise.slug}/clear/')
        self.assertFalse(TutorMessage.objects.exists())
        self.assertContains(self.client.get(f'/learn/{self.exercise.slug}/'), 'data-tab="tutor">Tutor<')


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
        patcher = mock.patch.dict('os.environ', {'LEARN_TUTOR_BACKEND': 'claude_code', 'LEARN_CLAUDE_CLI': 'claude.exe', 'GEMINI_API_KEY': '', 'GOOGLE_API_KEY': ''})
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
    """A public deployment (LEARN_REQUIRE_LOGIN=True) is locked to signed-in accounts."""

    def setUp(self):
        self.exercise = get_exercise('http-requests')
        self.learner = User.objects.create_user('learner', password='pw')

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_pages_need_login(self):
        response = self.client.get('/learn/')
        self.assertRedirects(response, '/accounts/login/?next=%2Flearn%2F', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/accounts/login/').status_code, 200)
        self.assertEqual(self.client.get('/accounts/signup/').status_code, 200)

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_running_code_needs_login_even_from_localhost(self):
        url = f'/learn/{self.exercise.slug}/run-selection/'
        body = {'code': '', 'selection': '1 + 1', 'start_line': 1, 'end_line': 1}
        response = self.client.post(url, body, content_type='application/json')
        self.assertEqual(response.status_code, 302)

    @override_settings(LEARN_REQUIRE_LOGIN=True)
    def test_signed_in_learners_can_use_everything(self):
        self.client.force_login(self.learner)
        self.assertEqual(self.client.get('/learn/').status_code, 200)
        url = f'/learn/{self.exercise.slug}/run-selection/'
        body = {'code': '', 'selection': '1 + 1', 'start_line': 1, 'end_line': 1}
        response = self.client.post(url, body, content_type='application/json', REMOTE_ADDR='203.0.113.5')
        self.assertEqual(response.json()['output'], '2\n')

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


class SiteNavigationTests(SignedInTestCase):
    def test_home_shows_next_step(self):
        response = self.client.get('/')
        self.assertContains(response, '<html lang="en" dir="ltr">')
        self.assertContains(response, 'Backend Developer (Python, Django)')  # the catalog loads itself if empty
        self.assertContains(response, f'/learn/{load_exercises()[0].slug}/')

    def test_arabic_is_right_to_left(self):
        self.client.cookies['django_language'] = 'ar'
        response = self.client.get('/')
        self.assertContains(response, '<html lang="ar" dir="rtl">')
        self.assertContains(response, 'الرئيسية')

    def test_language_switch(self):
        response = self.client.post('/i18n/setlang/', {'language': 'ar', 'next': '/learn/'})
        self.assertRedirects(response, '/learn/', fetch_redirect_response=False)
        self.assertEqual(response.cookies['django_language'].value, 'ar')

    def test_slides_pdf(self):
        exercise = get_exercise('http-requests')
        pdf = Path(settings.BASE_DIR) / 'materials' / 'out' / 'pdf' / '01-http-requests.pdf'
        response = self.client.get(f'/learn/{exercise.slug}/slides/')
        if pdf.exists():
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertContains(self.client.get(f'/learn/{exercise.slug}/'), 'Slides</a>')
        else:
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/learn/no-such-exercise/slides/').status_code, 404)


class NotebookTests(SignedInTestCase):
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
        super().setUp()
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
        ExerciseProgress.objects.create(user=self.user, slug=self.exercise.slug, passed=True, attempts=7, code='def parse_request(raw): ...')
        TutorMessage.objects.create(user=self.user, topic=self.exercise.slug, role='user', content='x', display='where is raw?')
        XPEvent.objects.create(user=self.user, key=f'tests:{self.exercise.slug}:1', slug=self.exercise.slug, label='Tests passing', amount=5)
        evidence = notebook.build_evidence(self.user, self.exercise)
        self.assertIn('Test runs before passing: 7', evidence)
        self.assertIn('where is raw?', evidence)
        self.assertIn('Tests passing', evidence)
        self.assertIn('def parse_request(raw)', evidence)

    def test_generate_requires_passing(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)

    def test_generate_saves_page(self):
        ExerciseProgress.objects.create(user=self.user, slug=self.exercise.slug, passed=True)
        with self.fake_reply('Here you go:\n```json\n' + json.dumps(self.PAGE) + '\n```'):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(NotebookEntry.objects.get(slug=self.exercise.slug).data['summary'], self.PAGE['summary'])
        page = self.client.get('/learn/notebook/')
        self.assertContains(page, 'You parsed a raw HTTP request.')

    def test_bad_reply_is_reported(self):
        ExerciseProgress.objects.create(user=self.user, slug=self.exercise.slug, passed=True)
        with self.fake_reply('Sorry, no JSON here'):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 502)
        self.assertFalse(NotebookEntry.objects.exists())

    def test_page_lists_locked_exercises(self):
        response = self.client.get('/learn/notebook/')
        self.assertContains(response, 'My notebook')
        self.assertContains(response, 'Kill the N+1 query')


class RunSelectionTests(SignedInTestCase):
    """Running highlighted code: the rest of the file loads, then the selection runs."""

    def setUp(self):
        super().setUp()
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
        self.client.logout()
        self.assertEqual(self.client.post(url, body, content_type='application/json').status_code, 403)


class SingleTestRunTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
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


class FakeGemini:
    """Stands in for google.genai.Client and records each request."""

    def __init__(self, chunks=('Gemini ', 'says hi'), finish='STOP', error=None):
        self.calls = []
        self.chunks, self.finish, self.error = chunks, finish, error
        self.models = SimpleNamespace(generate_content_stream=self._stream)

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        for i, text in enumerate(self.chunks):
            last = i == len(self.chunks) - 1
            reason = SimpleNamespace(name=self.finish) if last else None
            yield SimpleNamespace(text=text, candidates=[SimpleNamespace(finish_reason=reason)])


class GeminiTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.fake = FakeGemini()
        for patcher in [
            mock.patch('google.genai.Client', return_value=self.fake),
            mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key', 'GOOGLE_API_KEY': '',
                                           'ANTHROPIC_API_KEY': '', 'LEARN_TUTOR_BACKEND': 'auto'}),
        ]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.system = tutor.build_system(load_exercises()[0])

    def test_gemini_is_used_when_it_is_the_only_option(self):
        with mock.patch('learn.tutor.find_claude_cli', return_value=None):
            self.assertEqual(tutor.backend(), 'gemini')
            self.assertEqual(tutor.backend_label(), 'Google Gemini')
            output = list(tutor.stream_reply(self.system, [
                {'role': 'user', 'content': 'Hi'},
                {'role': 'assistant', 'content': 'Hello!'},
                {'role': 'user', 'content': 'What is HTTP?'},
            ]))
        self.assertEqual([v for k, v in output if k == 'text'], ['Gemini ', 'says hi'])
        self.assertEqual(output[-1][1].stop_reason, 'end_turn')
        call = self.fake.calls[0]
        self.assertEqual([c['role'] for c in call['contents']], ['user', 'model', 'user'])
        self.assertIn('<reference_solution>', call['config'].system_instruction)

    def test_falls_back_when_claude_fails_before_answering(self):
        def broken_claude(*args):
            raise tutor.TutorError('Claude Code is not signed in.')
            yield  # pragma: no cover  (makes this a generator)

        with mock.patch('learn.tutor.find_claude_cli', return_value='claude.exe'), \
                mock.patch('learn.tutor._stream_via_claude_code', side_effect=broken_claude):
            self.assertIn('Gemini as a backup', tutor.backend_label())
            output = list(tutor.stream_reply(self.system, [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(output[0][0], 'notice')
        self.assertIn('not signed in', output[0][1])
        self.assertEqual([v for k, v in output if k == 'text'], ['Gemini ', 'says hi'])

    def test_no_fallback_once_claude_has_started_answering(self):
        def half_answer(*args):
            yield 'text', 'Partial'
            raise tutor.TutorError('connection dropped')

        with mock.patch('learn.tutor.find_claude_cli', return_value='claude.exe'), \
                mock.patch('learn.tutor._stream_via_claude_code', side_effect=half_answer):
            with self.assertRaises(tutor.TutorError):
                list(tutor.stream_reply(self.system, [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(self.fake.calls, [])

    def test_safety_block_counts_as_refusal(self):
        self.fake.finish = 'SAFETY'
        with mock.patch('learn.tutor.find_claude_cli', return_value=None):
            output = list(tutor.stream_reply(self.system, [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(output[-1][1].stop_reason, 'refusal')

    def test_daily_limit_message(self):
        from google.genai import errors
        error = errors.ClientError(429, {'error': {'code': 429, 'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
        self.assertIn('free daily limit', tutor.friendly_error(error))

    def test_view_streams_notice_and_saves_answer(self):
        def broken_claude(*args):
            raise tutor.TutorError('Claude Code is not signed in.')
            yield  # pragma: no cover

        exercise = load_exercises()[0]
        with mock.patch('learn.tutor.find_claude_cli', return_value='claude.exe'), \
                mock.patch('learn.tutor._stream_via_claude_code', side_effect=broken_claude):
            response = self.client.post(f'/learn/tutor/{exercise.slug}/ask/', {'question': 'Hi'},
                                        content_type='application/json')
            events = [json.loads(line) for line in b''.join(response.streaming_content).decode().splitlines() if line]
        self.assertEqual([e['type'] for e in events], ['notice', 'text', 'text', 'done'])
        self.assertEqual(TutorMessage.objects.get(role='assistant').content, 'Gemini says hi')


class SignUpTests(TestCase):
    def setUp(self):
        self.invite = InviteCode.objects.create(code='COHORT1', max_uses=2)

    def sign_up(self, username='sara', code='COHORT1'):
        return self.client.post('/accounts/signup/', {
            'username': username, 'password1': 'a-long-passphrase-1', 'password2': 'a-long-passphrase-1',
            'invite_code': code,
        })

    def test_invite_code_creates_account_and_signs_in(self):
        response = self.sign_up(code='cohort1')  # not case sensitive
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(username='sara').exists())
        self.assertEqual(InviteCode.objects.get().uses, 1)
        self.assertContains(self.client.get('/'), 'Sign out')

    def test_wrong_code_is_refused(self):
        response = self.sign_up(code='NOPE')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This invite code is not valid')
        self.assertFalse(User.objects.filter(username='sara').exists())

    def test_used_up_inactive_and_expired_codes_are_refused(self):
        for name in ('one', 'two'):
            self.sign_up(name)
            self.client.logout()
        self.assertContains(self.sign_up('three'), 'This invite code is not valid')
        InviteCode.objects.create(code='OFF', active=False)
        self.assertContains(self.sign_up('four', 'OFF'), 'This invite code is not valid')
        InviteCode.objects.create(code='OLD', expires_at=timezone.now() - timedelta(days=1))
        self.assertContains(self.sign_up('five', 'OLD'), 'This invite code is not valid')
        self.assertEqual(User.objects.count(), 2)

    def test_sign_in_and_out(self):
        User.objects.create_user('sara', password='pw')
        response = self.client.post('/accounts/login/', {'username': 'sara', 'password': 'pw'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.client.post('/accounts/logout/')
        self.assertRedirects(self.client.get('/learn/'), '/accounts/login/?next=/learn/', fetch_redirect_response=False)

    def test_new_invite_codes_get_a_random_code(self):
        self.assertRegex(InviteCode.objects.create().code, r'^[0-9A-F]{8}$')


class SeparateProgressTests(TestCase):
    """Two accounts on one site keep their own progress, XP and tutor chats."""

    def test_two_learners_see_separate_progress(self):
        exercise = load_exercises()[0]
        sara, omar = User.objects.create_user('sara'), User.objects.create_user('omar')
        self.client.force_login(sara)
        self.client.post(f'/learn/{exercise.slug}/run/', {'code': exercise.solution}, content_type='application/json')
        self.assertContains(self.client.get('/learn/'), 'id="hud-xp">0 XP', count=0)

        self.client.force_login(omar)
        self.assertContains(self.client.get('/learn/'), 'id="hud-xp">0 XP')
        page = self.client.get(f'/learn/{exercise.slug}/')
        self.assertEqual(page.context['progress'], None)
        self.assertEqual(page.context['code'], exercise.starter)
        self.client.post(f'/learn/{exercise.slug}/run/', {'code': exercise.starter}, content_type='application/json')

        self.assertTrue(ExerciseProgress.objects.get(user=sara, slug=exercise.slug).passed)
        self.assertFalse(ExerciseProgress.objects.get(user=omar, slug=exercise.slug).passed)
        self.assertGreater(gamification.total_xp(sara), gamification.total_xp(omar))


class ActivityLogTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        self.exercise = get_exercise('http-requests')
        self.url = f'/learn/{self.exercise.slug}'

    def post(self, path, body):
        return self.client.post(f'{self.url}/{path}/', body, content_type='application/json')

    def test_running_an_exercise_adds_rows(self):
        self.post('run', {'code': self.exercise.starter, 'seconds': 42})
        self.post('run', {'code': self.exercise.solution, 'seconds': 90})
        self.post('run', {'code': self.exercise.solution, 'seconds': 95})
        kinds = list(LearningEvent.objects.filter(user=self.user).order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, ['run', 'run', 'passed', 'run'])  # "passed" only the first time
        first = LearningEvent.objects.filter(user=self.user).order_by('id').first()
        self.assertEqual((first.slug, first.seconds_spent, first.data['all_passed']), (self.exercise.slug, 42, False))

    def test_hints_quiz_solution_and_single_tests_are_logged(self):
        self.post('run', {'code': self.exercise.solution, 'test': list_tests(self.exercise)[0]['id']})
        self.post('quiz', {'answers': [q['answer'] for q in self.exercise.quiz]})
        self.post('solution', {})
        with mock.patch('learn.tutor.stream_reply', return_value=iter([])):
            b''.join(self.client.post(f'/learn/tutor/{self.exercise.slug}/ask/', {'question': 'Why?'},
                                      content_type='application/json').streaming_content)
        kinds = set(LearningEvent.objects.values_list('kind', flat=True))
        self.assertEqual(kinds, {'test_run', 'quiz', 'solution_viewed', 'hint'})

    def test_silly_timers_are_ignored(self):
        self.post('run', {'code': '', 'seconds': 10 ** 9})
        self.post('run', {'code': '', 'seconds': 'soon'})
        self.assertEqual(set(LearningEvent.objects.values_list('seconds_spent', flat=True)), {None})


class RunnerSafetyTests(TestCase):
    """Learner code can't see the site's secrets or files, or start programs."""

    def setUp(self):
        self.exercise = get_exercise('http-requests')

    def run_sel(self, text):
        return run_selection(self.exercise, self.exercise.solution, text, 1, 1)

    def test_secrets_are_not_passed_to_learner_code(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'secret-key', 'DJANGO_SECRET_KEY': 'secret'}):
            result = self.run_sel('import os\nsorted(k for k in os.environ if "KEY" in k)')
        self.assertEqual(result['output'], '[]\n', result)

    def test_project_files_cannot_be_read(self):
        for path in [settings.BASE_DIR / 'manage.py', self.exercise.path / 'solution.py']:
            result = self.run_sel(f'open({str(path)!r}).read()')
            self.assertEqual(result['status'], 'error')
            self.assertIn('PermissionError', result['error'])

    def test_programs_cannot_be_started(self):
        result = self.run_sel('import subprocess\nsubprocess.run(["ls"])')
        self.assertIn('PermissionError', result['error'])
        result = self.run_sel('import os\nos.system("ls")')
        self.assertIn('PermissionError', result['error'])

    def test_memory_is_capped(self):
        result = self.run_sel('x = bytearray(2 * 1024 ** 3)')
        self.assertIn('MemoryError', result['error'])

    def test_own_folder_still_works(self):
        result = self.run_sel('open("notes.txt", "w").write("hi")\nopen("notes.txt").read()')
        self.assertEqual(result['output'], "'hi'\n", result)


class CatalogTests(SignedInTestCase):
    """The path catalog loads from catalog.json and tracks progress from passed exercises."""

    def setUp(self):
        super().setUp()
        from .catalog import load_catalog
        load_catalog()

    def test_catalog_has_the_three_job_paths_and_valid_exercises(self):
        from .models import Chapter, Path
        self.assertEqual(set(Path.objects.filter(kind=Path.JOB).values_list('slug', flat=True)),
                         {'backend-developer', 'frontend-developer', 'fullstack-developer'})
        known = {e.slug for e in load_exercises()}
        linked = [slug for ch in Chapter.objects.all() for slug in ch.exercises]
        linked += [slug for p in Path.objects.filter(kind=Path.JOB) for slug in p.capstone.get('exercises', [])]
        self.assertEqual(set(linked), known)  # every exercise appears, and only real ones

    def test_loading_twice_is_safe(self):
        from .catalog import load_catalog
        from .models import Chapter
        count = Chapter.objects.count()
        load_catalog()
        self.assertEqual(Chapter.objects.count(), count)

    def test_catalog_and_path_pages(self):
        response = self.client.get('/learn/paths/')
        self.assertContains(response, 'Frontend Developer (HTML, CSS, JavaScript)')
        self.assertContains(response, 'Full Stack Developer')
        response = self.client.get('/learn/paths/backend-developer/')
        self.assertContains(response, 'Admin, ownership and first APIs')
        self.assertContains(response, '/learn/http-requests/')
        self.assertEqual(self.client.get('/learn/paths/python-basics/').status_code, 200)
        self.assertEqual(self.client.get('/learn/paths/nope/').status_code, 404)

    def test_progress_and_you_are_here(self):
        from .catalog import job_view
        from .models import Path
        for slug in ('http-requests', 'json-views'):
            ExerciseProgress.objects.create(user=self.user, slug=slug, passed=True)
        job = job_view(Path.objects.get(slug='backend-developer'), self.user)
        self.assertEqual(job.done, 2)
        self.assertEqual(job.current_chapter.chapter.title, 'Models and migrations')
        self.assertEqual(job.next_exercise.slug, 'models')
        self.assertEqual(job.exercises_passed, (2, 17))

    def test_home_cockpit(self):
        ExerciseProgress.objects.create(user=self.user, slug='http-requests', passed=True)
        LearningEvent.objects.create(user=self.user, kind=LearningEvent.PASSED, slug='http-requests')
        response = self.client.get('/')
        self.assertContains(response, 'Backend Developer (Python, Django)')
        self.assertContains(response, 'Continue learning')
        self.assertContains(response, 'Recent activity')
        self.assertContains(response, '/learn/json-views/')

    def test_choose_path_changes_home(self):
        response = self.client.post('/learn/paths/frontend-developer/choose/')
        self.assertRedirects(response, '/')
        self.assertContains(self.client.get('/'), 'Frontend Developer (HTML, CSS, JavaScript)')
        self.assertTrue(LearningEvent.objects.filter(user=self.user, kind=LearningEvent.PATH_CHOSEN).exists())

    def test_skip_prerequisite(self):
        from .catalog import job_view
        from .models import Path
        response = self.client.post('/learn/paths/python-basics/skip/', {'skip': '1', 'next': '/learn/paths/backend-developer/'})
        self.assertRedirects(response, '/learn/paths/backend-developer/')
        job = job_view(Path.objects.get(slug='backend-developer'), self.user)
        self.assertTrue(job.prerequisites[0].skipped)
        self.assertEqual(job.prerequisites[0].percent, 100)
        self.client.post('/learn/paths/python-basics/skip/', {'skip': '0'})
        self.assertFalse(job_view(Path.objects.get(slug='backend-developer'), self.user).prerequisites[0].skipped)
        # Only prerequisites can be skipped.
        self.assertEqual(self.client.post('/learn/paths/sql-basics/skip/', {'skip': '1'}).status_code, 404)

    def test_coming_soon_sections_and_arabic_shell(self):
        for url in ('/learn/flashcards/', '/learn/project/', '/learn/portfolio/'):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.client.cookies['django_language'] = 'ar'
        response = self.client.get('/learn/paths/')
        self.assertContains(response, 'dir="rtl"')


PYTHON_TASK_SOLUTIONS = {
    '1': 'def filter_products(products, max_price):\n    return [p["name"] for p in products if p["price"] <= max_price]\n',
    '2': ('class BankAccount:\n    def __init__(self, owner, balance=0.0):\n        self.owner = owner\n'
          '        self.balance = balance\n\n    def deposit(self, amount):\n        self.balance += amount\n\n'
          '    def withdraw(self, amount):\n        if amount > self.balance:\n'
          '            raise ValueError("Insufficient funds")\n        self.balance -= amount\n'),
}


class PlacementTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        from .catalog import load_catalog
        from .models import Path
        load_catalog()
        self.path = Path.objects.get(slug='python-basics')
        self.questions = self.path.placement_test['multiple_choice_questions']

    def answers(self, wrong=()):
        """Form data with every question right except the ids in `wrong`."""
        data = {}
        for q in self.questions:
            options = [o for o in q['options'] if o != q['correct_option']]
            data[f'q{q["id"]}'] = options[0] if q['id'] in wrong else q['correct_option']
        return data

    def test_page_hides_answers(self):
        response = self.client.get('/learn/paths/python-basics/placement/')
        self.assertContains(response, self.questions[0]['question'])
        self.assertContains(response, 'filter_products')
        self.assertNotContains(response, self.questions[0]['explanation'])
        self.assertContains(self.client.get('/learn/paths/backend-developer/'), '/learn/paths/python-basics/placement/')

    def test_task_tests_pass_with_solutions_and_fail_with_starters(self):
        from .placement import tasks
        for task in tasks(self.path):
            with self.subTest(task=task.id):
                self.assertTrue(run_tests(task, PYTHON_TASK_SOLUTIONS[str(task.id)])['all_passed'])
                self.assertFalse(run_tests(task, task.starter)['all_passed'])

    def test_passing_marks_the_path_done(self):
        from .catalog import job_view
        from .models import Path, PlacementAttempt
        data = self.answers(wrong={1, 2})  # 8 of 10 is the pass mark
        data.update({f'task{k}': v for k, v in PYTHON_TASK_SOLUTIONS.items()})
        response = self.client.post('/learn/paths/python-basics/placement/', data)
        self.assertContains(response, 'You passed')
        attempt = PlacementAttempt.objects.get(user=self.user)
        self.assertEqual((attempt.correct, attempt.tasks_passed, attempt.passed), (8, 2, True))
        job = job_view(Path.objects.get(slug='backend-developer'), self.user)
        self.assertTrue(job.prerequisites[0].skipped)
        self.assertEqual(job.prerequisites[0].percent, 100)
        self.assertTrue(LearningEvent.objects.filter(user=self.user, kind=LearningEvent.PLACEMENT,
                                                     data__passed=True).exists())

    def test_failing_skips_only_the_chapters_answered_right(self):
        from .catalog import SKIPPED, TODO, SOON, job_view
        from .models import Path
        # Question 1 (variables) wrong, coding tasks left as the starter code.
        response = self.client.post('/learn/paths/python-basics/placement/', self.answers(wrong={1}))
        self.assertContains(response, 'Not this time')
        job = job_view(Path.objects.get(slug='backend-developer'), self.user)
        python = job.prerequisites[0]
        self.assertFalse(python.skipped)
        statuses = {ch.chapter.slug: ch.status for ch in python.chapters}
        self.assertNotEqual(statuses['variables-and-primitive-types'], SKIPPED)
        self.assertEqual(statuses['strings-and-string-formatting'], SKIPPED)
        self.assertEqual(statuses['lists-and-dictionaries'], SKIPPED)  # both of its questions right
        self.assertIn(statuses['functions-and-parameters'], (TODO, SOON))  # its coding task failed
        self.assertIn(statuses['first-look-at-classes'], (TODO, SOON))
        skipped_events = LearningEvent.objects.filter(user=self.user, kind=LearningEvent.CHAPTER_SKIPPED)
        self.assertEqual(skipped_events.count(), 6)
        # Shown on the path page too.
        self.assertContains(self.client.get('/learn/paths/python-basics/'), 'chapters you already know are skipped')

    def test_javascript_test_is_questions_only(self):
        response = self.client.get('/learn/paths/javascript-fundamentals/placement/')
        self.assertContains(response, 'typeof null')
        self.assertNotContains(response, 'Coding tasks')
        from .models import Path
        js = Path.objects.get(slug='javascript-fundamentals')
        for q in js.placement_test['multiple_choice_questions']:
            self.assertIn(q['correct_option'], q['options'])
        response = self.client.post('/learn/paths/javascript-fundamentals/placement/', {
            f'q{q["id"]}': q['correct_option'] for q in js.placement_test['multiple_choice_questions']})
        self.assertContains(response, 'You passed')

    def test_paths_without_a_test(self):
        self.assertEqual(self.client.get('/learn/paths/sql-basics/placement/').status_code, 404)


def sample_generated_path(title='Tailwind basics'):
    chapter = lambda n: {
        'title': f'Chapter {n}', 'learning_goal': 'you can style a card with utility classes',
        'exercise_idea': 'Style a profile card.',
        'lesson': 'Tailwind gives you small classes. ' * 10 + '\n\n```html\n<div class="p-4">Hi</div>\n```\n<script>x()</script>',
        'slides': [{'title': 'Utilities', 'points': ['One class, one job']}, {'title': 'Spacing', 'points': ['p-4']}],
        'quiz': [{'question': f'Q{i}?', 'options': ['a', 'b', 'c', 'd'], 'answer': 1, 'explanation': 'Because b.'}
                 for i in range(3)],
    }
    return {
        'title': title, 'summary': 'Style pages with utility classes.', 'level': 'beginner', 'hours': 9,
        'project': {'title': 'A landing page', 'brief': 'Build one.', 'skills_used': ['Tailwind']},
        'courses': [{'title': 'Getting started', 'hours': 4, 'language': 'css', 'chapters': [chapter(1), chapter(2)]},
                    {'title': 'Layout', 'hours': 5, 'language': 'css', 'chapters': [chapter(3)]}],
    }


class GeneratorTests(SignedInTestCase):
    def setUp(self):
        super().setUp()
        from .catalog import load_catalog
        load_catalog()
        patcher = mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def generate(self, replies, **data):
        replies = list(replies)
        with mock.patch('learn.generator._ask_gemini', side_effect=lambda system, messages: replies.pop(0)) as ask:
            response = self.client.post('/learn/paths/generate/', {'skill': 'Tailwind basics', 'level': 'beginner',
                                                                   'hours': 3, **data})
        return response, ask

    def test_clean_path_accepts_good_json_and_lists_problems(self):
        from .generator import clean_path
        cleaned, errors = clean_path(sample_generated_path())
        self.assertEqual(errors, [])
        bad = sample_generated_path()
        bad['level'] = 'expert'
        bad['courses'][0]['chapters'][0]['quiz'][0]['answer'] = 7
        del bad['courses'][1]['chapters'][0]['slides']
        _, errors = clean_path(bad)
        self.assertEqual(len(errors), 3, errors)
        self.assertEqual(clean_path([])[1], ['The reply must be one JSON object.'])

    def test_generates_a_clickable_ai_path(self):
        from .models import Path
        response, ask = self.generate([json.dumps(sample_generated_path())])
        path = Path.objects.get(owner=self.user)
        self.assertRedirects(response, f'/learn/paths/{path.slug}/')
        self.assertTrue(path.ai_generated)
        self.assertEqual(path.request['hours_per_week'], 3)
        self.assertIn('Hours per week: 3', ask.call_args[0][1][0]['content'])
        page = self.client.get(f'/learn/paths/{path.slug}/')
        self.assertContains(page, 'AI-generated')
        chapter = path.courses.first().chapters.first()
        self.assertContains(page, f'/learn/paths/{path.slug}/chapters/{chapter.slug}/')
        self.assertContains(self.client.get('/learn/paths/'), 'Tailwind basics')
        lesson = self.client.get(f'/learn/paths/{path.slug}/chapters/{chapter.slug}/')
        self.assertContains(lesson, 'Tailwind gives you small classes')
        self.assertContains(lesson, '&lt;script&gt;')  # raw HTML from the AI shows as text
        self.assertNotContains(lesson, '<script>x()')
        self.assertNotContains(lesson, 'Because b.')  # explanations wait until the quiz is answered
        self.assertTrue(LearningEvent.objects.filter(user=self.user, kind=LearningEvent.PATH_GENERATED).exists())

    def test_quiz_finishes_a_generated_chapter(self):
        from .catalog import DONE, skill_view, chapter_marks
        from .models import ChapterProgress, Path
        self.generate([json.dumps(sample_generated_path())])
        path = Path.objects.get(owner=self.user)
        chapter = path.courses.first().chapters.first()
        url = f'/learn/paths/{path.slug}/chapters/{chapter.slug}/'
        response = self.client.post(url, {'q0': '1', 'q1': '0', 'q2': '0'})
        self.assertContains(response, '1 of 3 right')
        self.assertFalse(ChapterProgress.objects.get(user=self.user, chapter=chapter).done)
        response = self.client.post(url, {'q0': '1', 'q1': '1', 'q2': '0'})
        self.assertContains(response, 'Chapter completed')
        view = skill_view(path, {}, set(), marks=chapter_marks(self.user))
        self.assertEqual(view.chapters[0].status, DONE)
        self.assertEqual(view.done, 1)
        self.assertTrue(LearningEvent.objects.filter(user=self.user, kind=LearningEvent.LESSON_FINISHED).exists())

    def test_bad_reply_is_retried_once_then_refused(self):
        from .models import Path
        good = json.dumps(sample_generated_path())
        response, ask = self.generate(['not json', good])
        self.assertEqual(ask.call_count, 2)
        self.assertIn('problems', ask.call_args[0][1][-1]['content'])
        self.assertEqual(Path.objects.filter(owner=self.user).count(), 1)
        response, ask = self.generate(['{"title": 1}', '{"title": 2}'])
        self.assertContains(response, 'nothing was saved')
        self.assertEqual(Path.objects.filter(owner=self.user).count(), 1)

    def test_blocked_network_fails_gracefully(self):
        class ConnectError(Exception):
            pass
        from .models import Path
        with mock.patch('learn.generator._ask_gemini', side_effect=ConnectError('proxy said no')):
            response = self.client.post('/learn/paths/generate/', {'skill': 'Tailwind basics', 'level': 'beginner', 'hours': 3})
        self.assertContains(response, 'Could not reach the AI service')
        self.assertFalse(Path.objects.filter(owner=self.user).exists())

    def test_no_ai_configured(self):
        with mock.patch.dict('os.environ', {'GEMINI_API_KEY': '', 'GOOGLE_API_KEY': '', 'ANTHROPIC_API_KEY': '',
                                            'LEARN_TUTOR_BACKEND': 'api'}):
            response = self.client.get('/learn/paths/generate/')
        self.assertContains(response, 'not set up on this server')

    def test_catalog_topics_point_to_the_catalog(self):
        response, ask = self.generate([], skill='SQL')
        self.assertContains(response, 'The catalog already has')
        self.assertEqual(ask.call_count, 0)
        response, ask = self.generate([json.dumps(sample_generated_path('SQL tricks'))], skill='SQL', anyway='1')
        self.assertEqual(ask.call_count, 1)

    def test_generated_paths_are_private_and_deletable(self):
        from .models import Path
        self.generate([json.dumps(sample_generated_path())])
        path = Path.objects.get(owner=self.user)
        other = User.objects.create_user('other', password='pw')
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/learn/paths/{path.slug}/').status_code, 404)
        self.assertNotContains(self.client.get('/learn/paths/'), 'Tailwind basics')
        self.assertEqual(self.client.post(f'/learn/paths/{path.slug}/delete/').status_code, 404)
        self.client.force_login(self.user)
        self.assertRedirects(self.client.post(f'/learn/paths/{path.slug}/delete/'), '/learn/paths/generate/')
        self.assertFalse(Path.objects.filter(pk=path.pk).exists())

    def test_daily_limit(self):
        from . import generator
        with mock.patch.object(generator, 'DAILY_LIMIT', 1):
            self.generate([json.dumps(sample_generated_path())])
            response, ask = self.generate([json.dumps(sample_generated_path())])
        self.assertContains(response, 'most paths allowed today')
        self.assertEqual(ask.call_count, 0)


class Day5Tests(SignedInTestCase):
    """Capstone pictures, practice badges, the supported languages list and the tutor on generated chapters."""

    def setUp(self):
        super().setUp()
        from .catalog import load_catalog
        load_catalog()
        patcher = mock.patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def generated_path(self):
        from .models import Path
        with mock.patch('learn.generator._ask_gemini', return_value=json.dumps(sample_generated_path())):
            self.client.post('/learn/paths/generate/', {'skill': 'Tailwind basics', 'level': 'beginner', 'hours': 3})
        return Path.objects.get(owner=self.user)

    def test_finds_languages_by_whole_word(self):
        from .languages import find_languages
        keys = lambda text: [lang['key'] for lang in find_languages(text)]
        self.assertEqual(keys('Tailwind basics'), ['css'])
        self.assertEqual(keys('React Native apps'), ['mobile'])  # the longer name wins
        self.assertEqual(keys('HTML then JavaScript'), ['html', 'javascript'])
        self.assertEqual(keys('Django forms'), ['django'])  # "go" is not found inside "django"
        self.assertEqual(keys('C# for games'), ['compiled'])
        self.assertEqual(keys('بايثون للمبتدئين'), ['python'])
        self.assertEqual(keys('Cooking'), [])

    def test_badges_and_pictures(self):
        from .languages import HANDS_ON, READING, SOON, art_for, practice
        from .models import Path
        backend, frontend = Path.objects.get(slug='backend-developer'), Path.objects.get(slug='frontend-developer')
        self.assertEqual(art_for(backend), 'api')
        self.assertEqual(practice(backend, 10), HANDS_ON)
        self.assertEqual(practice(frontend, 0), SOON)
        self.assertEqual(practice(Path.objects.get(slug='git-github'), 0), READING)
        generated = self.generated_path()
        self.assertEqual(art_for(generated), 'style')  # Tailwind is CSS
        self.assertEqual(practice(generated), SOON)
        page = self.client.get('/learn/paths/')
        self.assertContains(page, 'art-api')
        self.assertContains(page, 'art-style')
        self.assertContains(page, 'Hands-on soon')
        self.assertContains(page, 'Reading and quizzes')
        path_page = self.client.get(f'/learn/paths/{generated.slug}/')
        self.assertContains(path_page, 'class="journey"')
        first = generated.courses.first().chapters.first()
        self.assertContains(path_page, f'class="btn primary" href="/learn/paths/{generated.slug}/chapters/{first.slug}/"')

    def test_languages_page_and_generate_hint(self):
        page = self.client.get('/learn/languages/')
        self.assertContains(page, 'What you can practise')
        self.assertContains(page, 'Flutter')
        generate = self.client.get('/learn/paths/generate/')
        self.assertContains(generate, 'id="lang-data"')
        self.assertContains(generate, 'tailwind')
        self.assertContains(self.client.get('/'), '/learn/languages/')

    def test_tutor_on_a_generated_chapter(self):
        generated = self.generated_path()
        chapter = generated.courses.first().chapters.first()
        page = self.client.get(f'/learn/paths/{generated.slug}/chapters/{chapter.slug}/')
        topic = tutor.chapter_topic(chapter)
        self.assertContains(page, f'/learn/tutor/{topic}/ask/')
        reply = mock.patch('learn.tutor.stream_reply', return_value=iter([
            ('text', 'Utility classes are small.'), ('final', SimpleNamespace(stop_reason='end_turn'))]))
        with reply as stream:
            response = self.client.post(f'/learn/tutor/{topic}/ask/', {'question': 'What is a utility class?'},
                                        content_type='application/json')
            body = b''.join(response.streaming_content).decode()
        self.assertIn('Utility classes are small.', body)
        system = stream.call_args[0][0][1]['text']
        self.assertIn('Tailwind gives you small classes', system)  # the lesson
        self.assertIn('right answer', system)  # the quiz, for the tutor only
        self.assertEqual(TutorMessage.objects.filter(user=self.user, topic=topic).count(), 2)
        self.assertTrue(LearningEvent.objects.filter(user=self.user, kind=LearningEvent.HINT, slug=chapter.slug).exists())
        # Someone else's generated chapter stays private.
        other = User.objects.create_user('other', password='pw')
        self.client.force_login(other)
        self.assertEqual(self.client.post(f'/learn/tutor/{topic}/ask/', {'question': 'Hi'},
                                          content_type='application/json').status_code, 404)
        self.assertEqual(self.client.post(f'/learn/tutor/{topic}/clear/').status_code, 404)

    def test_finishing_a_chapter_celebrates_once(self):
        generated = self.generated_path()
        chapter = generated.courses.first().chapters.first()
        url = f'/learn/paths/{generated.slug}/chapters/{chapter.slug}/'
        self.assertContains(self.client.post(url, {'q0': '1', 'q1': '1', 'q2': '0'}), 'celebrate')
        self.assertNotContains(self.client.post(url, {'q0': '1', 'q1': '1', 'q2': '0'}), 'success celebrate')


class MakeInvitesTests(TestCase):
    def test_prints_working_codes(self):
        from django.core.management import call_command
        out = io.StringIO()
        call_command('make_invites', '2', '--note', 'Testers', stdout=out)
        codes = InviteCode.objects.filter(note='Testers')
        self.assertEqual(codes.count(), 2)
        self.assertIn('/accounts/signup/', out.getvalue())
        self.assertIn(codes.first().code, out.getvalue())


class DiagramTests(SignedInTestCase):
    """Mind maps and diagrams the AI writes are checked before saving, and drawn on the page."""

    def test_clean_diagram_keeps_safe_kinds_only(self):
        from .diagrams import clean_diagram, clean_lesson
        self.assertEqual(clean_diagram('```mermaid\nflowchart LR\n  A --> B\n```'), 'flowchart LR\n  A --> B')
        self.assertTrue(clean_diagram('mindmap\n  root((Tailwind))\n    Utilities'))
        self.assertEqual(clean_diagram('pie title Pets\n "Dogs" : 3'), '')  # not a kind we draw
        self.assertEqual(clean_diagram('%%{init: {"theme": "dark"}}%%\nflowchart LR\n A --> B'), '')
        self.assertEqual(clean_diagram('flowchart LR\n A --> B\n click A "https://x.test"'), '')
        self.assertEqual(clean_diagram('flowchart LR\n A["<img src=x onerror=y>"] --> B'), '')
        self.assertEqual(clean_diagram('flowchart LR\n' + ' A --> B\n' * 50), '')
        self.assertEqual(clean_diagram(42), '')
        lesson = 'Intro\n```mermaid\nflowchart LR\n A --> B\n```\nMore\n```mermaid\nnot a diagram\n```\nEnd'
        self.assertEqual(clean_lesson(lesson), 'Intro\n```mermaid\nflowchart LR\n A --> B\n```\nMore\n\nEnd')

    def test_generated_chapter_shows_mind_map_and_slide_diagram(self):
        from .generator import clean_path, save_path
        data = sample_generated_path()
        chapter = data['courses'][0]['chapters'][0]
        chapter['mind_map'] = 'mindmap\n  root((Tailwind))\n    Utilities\n    Layout'
        chapter['slides'][0] = {'title': 'Flow', 'diagram': 'flowchart LR\n  A[Class] --> B[Style]'}
        chapter['slides'][1]['diagram'] = 'pie\n "x" : 1'  # dropped, the slide keeps its points
        cleaned, errors = clean_path(data)
        self.assertEqual(errors, [])
        saved = cleaned['courses'][0]['chapters'][0]
        self.assertEqual(saved['slides'][0]['points'], [])
        self.assertEqual(saved['slides'][1]['diagram'], '')
        path = save_path(self.user, cleaned, {'skill': 'Tailwind basics', 'language': 'en'})
        first = path.courses.first().chapters.first()
        page = self.client.get(f'/learn/paths/{path.slug}/chapters/{first.slug}/')
        self.assertContains(page, 'The big picture')
        self.assertContains(page, 'root((Tailwind))')
        self.assertContains(page, 'A[Class] --&gt; B[Style]')
        self.assertContains(page, 'mermaid-11.4.1.min.js')

    def test_backend_lessons_have_diagrams(self):
        page = self.client.get('/learn/http-requests/')
        self.assertContains(page, 'class="language-mermaid"')
        self.assertContains(page, 'mermaid-11.4.1.min.js')

    def test_prompt_asks_for_diagrams(self):
        from .generator import build_request
        system, _ = build_request('Tailwind', 'beginner', 3, 'ar')
        self.assertIn('mind_map', system)
        self.assertIn('Labels are 1 to 4 words in Arabic', system)


class HowThisWorksTests(SignedInTestCase):
    def test_each_step_links_to_where_it_happens(self):
        page = self.client.get('/')
        for url in ('/learn/paths/', '/learn/flashcards/', '/learn/project/', '/learn/portfolio/'):
            self.assertContains(page, f'class="how-step" href="{url}"')
        self.assertContains(page, 'Five steps, in any order')
