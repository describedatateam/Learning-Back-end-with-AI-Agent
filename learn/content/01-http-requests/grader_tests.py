import unittest

from http_parser import is_safe_method, parse_request

GET_REQUEST = (
    "GET /api/tasks/?status=done&page=2 HTTP/1.1\r\n"
    "Host: localhost:8000\r\n"
    "Accept:   application/json  \r\n"
    "\r\n"
)
POST_REQUEST = (
    "POST /api/tasks/ HTTP/1.1\r\n"
    "Host: localhost\r\n"
    "Content-Type: application/json\r\n"
    "\r\n"
    '{"title": "Write tests"}'
)


class ParseRequestTests(unittest.TestCase):
    def test_01_method_and_version(self):
        """Reads the method and HTTP version from the request line"""
        parsed = parse_request(GET_REQUEST)
        self.assertEqual(parsed["method"], "GET")
        self.assertEqual(parsed["version"], "HTTP/1.1")
        self.assertEqual(parse_request(POST_REQUEST)["method"], "POST")

    def test_02_path_without_query(self):
        """`path` excludes the query string"""
        self.assertEqual(parse_request(GET_REQUEST)["path"], "/api/tasks/")

    def test_03_query_dict(self):
        """`query` is a dict of query parameters"""
        self.assertEqual(parse_request(GET_REQUEST)["query"], {"status": "done", "page": "2"})

    def test_04_empty_query(self):
        """`query` is {} when there is no query string"""
        self.assertEqual(parse_request(POST_REQUEST)["query"], {})

    def test_05_headers_lowercase_and_stripped(self):
        """Header names are lower-case and values are stripped"""
        headers = parse_request(GET_REQUEST)["headers"]
        self.assertEqual(headers.get("accept"), "application/json")

    def test_06_header_value_with_colon(self):
        """A header value that contains ':' is kept whole (Host: localhost:8000)"""
        self.assertEqual(parse_request(GET_REQUEST)["headers"].get("host"), "localhost:8000")

    def test_07_body(self):
        """`body` holds everything after the blank line ('' for GET)"""
        self.assertEqual(parse_request(POST_REQUEST)["body"], '{"title": "Write tests"}')
        self.assertEqual(parse_request(GET_REQUEST)["body"], "")


class SafeMethodTests(unittest.TestCase):
    def test_08_safe_methods(self):
        """GET, HEAD and OPTIONS are safe (any capitalisation)"""
        for method in ["GET", "HEAD", "OPTIONS", "get", "Head"]:
            self.assertTrue(is_safe_method(method), f"{method!r} should be safe")

    def test_09_unsafe_methods(self):
        """POST, PUT, PATCH and DELETE are not safe"""
        for method in ["POST", "PUT", "PATCH", "DELETE", "delete"]:
            self.assertFalse(is_safe_method(method), f"{method!r} should not be safe")
