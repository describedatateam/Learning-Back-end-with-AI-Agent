import re

MAX_LENGTH = 50


def make_slug(text):
    """Turn a title into a URL-friendly slug.

    make_slug("  Hello, World!  ")  -> "hello-world"
    make_slug("Django & DRF 101")   -> "django-drf-101"
    Slugs are at most 50 characters and never end with "-".
    Raises ValueError if nothing usable is left.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = slug[:MAX_LENGTH].rstrip("-")
    if not slug:
        raise ValueError("cannot make a slug from an empty title")
    return slug
