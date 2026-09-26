import hmac

from django.db import connection
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next_url(url, allowed_hosts):
    # Unsafe on purpose: this redirects to ANY address, including an attacker's site.
    # TODO 1: if url is not empty and url_has_allowed_host_and_scheme(...) says it's
    #         safe, return url unchanged
    # TODO 2: otherwise return "/"
    return url


def api_key_matches(provided, expected):
    # Unsafe on purpose: == can leak the secret through timing, and "" == "" is True.
    # TODO 3: if either key is empty or None, return False
    # TODO 4: return hmac.compare_digest(...) on both keys, turned into bytes with .encode()
    return provided == expected


def mask_email(email):
    # TODO 5: split (email or "") at the "@" with partition: local, at, domain
    # TODO 6: if any of the three pieces is empty, return "***"
    # TODO 7: return the first letter of local + "***@" + domain,
    #         so "ada@example.com" -> "a***@example.com"
    return email


def find_tasks_by_title(title):
    # DANGER: SQL injection! The f-string glues the title into the SQL text.
    # TODO 8: use a plain string with a bare %s where the title goes,
    #         and pass [title] as the second argument of cursor.execute
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT id FROM sandbox_task WHERE title = '{title}'")
        return [row[0] for row in cursor.fetchall()]
