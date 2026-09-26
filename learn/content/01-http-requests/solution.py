from urllib.parse import parse_qsl, urlsplit

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def parse_request(raw):
    """Turn a raw HTTP request string into a dict (see the lesson)."""
    head, _, body = raw.partition("\r\n\r\n")
    request_line, *header_lines = head.split("\r\n")
    method, target, version = request_line.split(" ")

    url = urlsplit(target)
    headers = {}
    for line in header_lines:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()

    return {
        "method": method,
        "path": url.path,
        "query": dict(parse_qsl(url.query)),
        "version": version,
        "headers": headers,
        "body": body,
    }


def is_safe_method(method):
    """Return True for methods that only read data."""
    return method.upper() in SAFE_METHODS
