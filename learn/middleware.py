from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, resolve_url


class LoginRequiredMiddleware:
    """On a public server (LEARN_REQUIRE_LOGIN=True), the whole site needs a signed-in account.

    Describe runs the Python you submit, so a deployed copy must not be usable
    by strangers; accounts need an invite code. The sign-in and sign-up pages,
    the language switch, the API (which has its own authentication) and the
    health check stay open.
    """

    OPEN_PREFIXES = ('/accounts/', '/i18n/', '/admin/', '/api/', '/health/', '/static/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (settings.LEARN_REQUIRE_LOGIN
                and not request.user.is_authenticated
                and not request.path.startswith(self.OPEN_PREFIXES)):
            return redirect(f'{resolve_url(settings.LOGIN_URL)}?{urlencode({"next": request.get_full_path()})}')
        return self.get_response(request)
