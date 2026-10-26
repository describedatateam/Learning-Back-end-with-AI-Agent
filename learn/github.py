"""Push a Lab project to a GitHub repo of the learner's own (Day 9).

A learner signs in with GitHub once (a free GitHub OAuth app; its id and secret go
in .env as GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET). The token only has the
`public_repo` scope, so it can create and write public repos and nothing else.
A push makes one commit with all the project's files through the Git Data API:
new repos start with a README, and existing repos keep their other files.
Only the standard library is used, so nothing new to install on the server.
"""
import base64
import json
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext

from . import lab
from .models import GitHubAccount

API = 'https://api.github.com'
AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
TOKEN_URL = 'https://github.com/login/oauth/access_token'
SCOPE = 'public_repo'
TIMEOUT = 20
PAUSE = 1.5  # seconds to wait for a new repo's first commit
REPO_NAME = re.compile(r'^[A-Za-z0-9._-]{1,100}$')


class GitHubError(Exception):
    """Something the learner can read. `reconnect` means the sign-in no longer works."""

    def __init__(self, message, reconnect=False, status=None):
        super().__init__(message)
        self.reconnect = reconnect
        self.status = status


def client_id():
    return os.environ.get('GITHUB_CLIENT_ID', '')


def available():
    return bool(client_id() and os.environ.get('GITHUB_CLIENT_SECRET'))


def new_state():
    return secrets.token_urlsafe(24)


def authorize_url(redirect_uri, state):
    return f'{AUTHORIZE_URL}?' + urlencode({
        'client_id': client_id(), 'redirect_uri': redirect_uri, 'scope': SCOPE, 'state': state, 'allow_signup': 'true',
    })


def _send(request):
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except HTTPError as error:
        try:
            detail = json.loads(error.read() or b'{}')
        except ValueError:
            detail = {}
        error.detail = detail
        raise
    except (URLError, TimeoutError, OSError) as error:
        raise GitHubError(gettext("This server can't reach GitHub right now. Try again later, or download the .zip instead.")) from error


def api(token, method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(f'{API}{path}', data=body, method=method, headers={
        'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'Describe-Learn',
        **({'Content-Type': 'application/json'} if body else {}),
    })
    try:
        return _send(request)
    except HTTPError as error:
        message = error.detail.get('message', '') if isinstance(error.detail, dict) else ''
        if error.code == 401:
            raise GitHubError(gettext('Your GitHub sign-in has expired or was removed. Connect GitHub again.'),
                              reconnect=True, status=401) from error
        raise GitHubError(message or gettext('GitHub said %(code)s.') % {'code': error.code}, status=error.code) from error


def exchange_code(code, redirect_uri):
    """Trade the code GitHub sent back for a token. Returns the token."""
    request = Request(TOKEN_URL, method='POST', data=urlencode({
        'client_id': client_id(), 'client_secret': os.environ.get('GITHUB_CLIENT_SECRET', ''),
        'code': code, 'redirect_uri': redirect_uri,
    }).encode(), headers={'Accept': 'application/json', 'User-Agent': 'Describe-Learn'})
    try:
        data = _send(request)
    except HTTPError as error:
        raise GitHubError(gettext('GitHub said %(code)s.') % {'code': error.code}) from error
    if not data.get('access_token'):
        raise GitHubError(data.get('error_description') or gettext('GitHub did not send a sign-in token.'))
    return data['access_token']


def connect(user, token):
    login = api(token, 'GET', '/user')['login']
    account, _ = GitHubAccount.objects.update_or_create(user=user, defaults={'login': login, 'token': token})
    return account


def revoke(account):
    """Best effort: remove the app's access on GitHub too, so the token stops working everywhere."""
    secret = os.environ.get('GITHUB_CLIENT_SECRET', '')
    if not (client_id() and secret):
        return
    basic = base64.b64encode(f'{client_id()}:{secret}'.encode()).decode()
    request = Request(f'{API}/applications/{client_id()}/grant', method='DELETE',
                      data=json.dumps({'access_token': account.token}).encode(), headers={
                          'Authorization': f'Basic {basic}', 'Accept': 'application/vnd.github+json',
                          'Content-Type': 'application/json', 'User-Agent': 'Describe-Learn'})
    try:
        _send(request)
    except (HTTPError, GitHubError):
        pass


# --- Pushing a Lab project -------------------------------------------------------

def suggested_repo(project):
    """A repo name from the project title; Arabic titles fall back to describe-lab-<id>."""
    if project.github_repo:
        return project.github_repo.rstrip('/').rsplit('/', 1)[-1]
    name = slugify(project.title)[:60].strip('-')
    return name if REPO_NAME.match(name or '') else f'describe-lab-{project.id}'


def clean_repo(name):
    name = str(name or '').strip().replace(' ', '-')
    if not REPO_NAME.match(name) or name in ('.', '..') or name.endswith('.git'):
        return ''
    return name


RUN_NOTES = {
    'web': 'Open `index.html` in a browser. To put it online for free, turn on GitHub Pages in this repo\'s '
           'Settings > Pages (branch: the default branch, folder: root).',
    'react': 'The Describe Learn Lab loads React for you. To run it anywhere else, add these lines to `index.html` and '
             'change `<script src="script.js">` to `<script type="text/babel" src="script.js">`:\n\n'
             '```html\n'
             '<script src="https://unpkg.com/react@18/umd/react.development.js"></script>\n'
             '<script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>\n'
             '<script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>\n'
             '<link rel="stylesheet" href="style.css">\n'
             '<script type="text/babel" src="script.js"></script>\n'
             '```',
    'tailwind': 'The Describe Learn Lab loads Tailwind CSS for you. To run it anywhere else, add this line to the top of '
                '`index.html`:\n\n```html\n<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>\n```',
    'python': 'Run it with `python main.py` (Python 3).',
}


def readme(project):
    kind = lab.KINDS[project.kind]
    parts = [f'# {project.title}', '']
    if project.idea:
        parts += [project.idea.strip(), '']
    parts += [f'A {kind["name"]} project built in the Describe Learn Lab.', '', '## Run it', '', RUN_NOTES[project.kind], '']
    return '\n'.join(parts)


def _head(token, owner, repo, branch):
    """The branch's latest commit and tree, or None for an empty repo."""
    try:
        ref = api(token, 'GET', f'/repos/{owner}/{repo}/git/ref/heads/{branch}')
    except GitHubError as error:
        if error.status in (404, 409):  # 409: "Git Repository is empty"
            return None
        raise
    commit = api(token, 'GET', f'/repos/{owner}/{repo}/git/commits/{ref["object"]["sha"]}')
    return {'sha': commit['sha'], 'tree': commit['tree']['sha']}


def push(account, project, repo, allow_existing=False):
    """Commit the project's saved files to github.com/<login>/<repo>.

    Returns {'url': ..., 'created': bool}. Raises GitHubError with `status == 'exists'`
    when the repo is already there and the learner hasn't said to add to it.
    """
    token, owner = account.token, account.login
    files = lab.clean_files(project.kind, project.files)
    try:
        info = api(token, 'GET', f'/repos/{owner}/{repo}')
        created = False
    except GitHubError as error:
        if error.status != 404:
            raise
        info = api(token, 'POST', '/user/repos', {
            'name': repo, 'description': (project.idea or f'{project.title}, built in the Describe Learn Lab')[:300],
            'auto_init': True, 'private': False,
        })
        created = True
    pushed_before = project.github_repo.rstrip('/') == info['html_url'].rstrip('/')
    if not created and not pushed_before and not allow_existing:
        raise GitHubError('exists', status='exists')
    branch = info.get('default_branch') or 'main'
    head = _head(token, owner, repo, branch)
    if head is None and created:  # GitHub writes the first README a moment after creating the repo
        time.sleep(PAUSE)
        head = _head(token, owner, repo, branch)
    if head is None:  # an empty repo has no branch to commit on: start it with the README
        api(token, 'PUT', f'/repos/{owner}/{repo}/contents/README.md', {
            'message': 'Add README', 'content': base64.b64encode(readme(project).encode()).decode()})
        head = _head(token, owner, repo, branch)
    if created:
        files = {'README.md': readme(project), **files}
    tree = api(token, 'POST', f'/repos/{owner}/{repo}/git/trees', {
        'base_tree': head['tree'],  # files already in the repo stay
        'tree': [{'path': name, 'mode': '100644', 'type': 'blob', 'content': text} for name, text in files.items()],
    })
    commit = api(token, 'POST', f'/repos/{owner}/{repo}/git/commits', {
        'message': f'Update from the Describe Learn Lab: {project.title}', 'tree': tree['sha'], 'parents': [head['sha']],
    })
    api(token, 'PATCH', f'/repos/{owner}/{repo}/git/refs/heads/{branch}', {'sha': commit['sha']})
    project.github_repo = info['html_url']
    project.pushed_at = timezone.now()
    project.save(update_fields=['github_repo', 'pushed_at'])
    return {'url': info['html_url'], 'created': created}
