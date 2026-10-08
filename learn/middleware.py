from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    """On a public server (LEARN_REQUIRE_LOGIN=True), the whole site needs a staff login.

    Dev Lab runs the Python you submit and stores one person's progress, so a
    deployed copy must not be usable by strangers. The login page itself, the
    API (which has its own authentication) and the health check stay open.
    """

    OPEN_PREFIXES = ('/admin/', '/api/', '/health/', '/static/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (settings.LEARN_REQUIRE_LOGIN
                and not (request.user.is_authenticated and request.user.is_staff)
                and not request.path.startswith(self.OPEN_PREFIXES)):
            return redirect(f'{settings.LOGIN_URL}?{urlencode({"next": request.get_full_path()})}')
        return self.get_response(request)
