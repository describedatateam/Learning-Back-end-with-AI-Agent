import hmac

from django.db import connection
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(url, allowed_hosts):
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts=set(allowed_hosts)):
        return url
    return "/"


def api_key_matches(provided, expected):
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


def mask_email(email):
    local, at, domain = (email or "").partition("@")
    if not at or not local or not domain:
        return "***"
    return f"{local[0]}***@{domain}"


def find_tasks_by_title(title):
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM sandbox_task WHERE title = %s", [title])
        return [row[0] for row in cursor.fetchall()]
