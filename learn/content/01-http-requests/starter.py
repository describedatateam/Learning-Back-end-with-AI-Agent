from urllib.parse import parse_qsl, urlsplit


def parse_request(raw):
    """Turn a raw HTTP request string into a dict (see the lesson)."""
    # `raw` is the request text. The tests pass it in when they call your function.
    # TODO 1: split `raw` at the first blank line ("\r\n\r\n") into head and body
    # TODO 2: split the head into lines; the first line is the request line
    # TODO 3: split the request line into method, target and version
    # TODO 4: use urlsplit(target) to get the path and the query dict
    # TODO 5: make a headers dict: lower-case name -> stripped value
    # TODO 6: return a dict with method, path, query, version, headers and body
    raise NotImplementedError("parse_request is not written yet")


def is_safe_method(method):
    """Return True for methods that only read data (GET, HEAD, OPTIONS)."""
    # TODO 7: compare in upper case, so "get" and "GET" both count
    raise NotImplementedError("is_safe_method is not written yet")
