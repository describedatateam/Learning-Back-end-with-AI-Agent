import json

from django.test import RequestFactory, SimpleTestCase

from views import add, greet


def body(response):
    return json.loads(response.content)


class GreetTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_01_greets_by_name(self):
        """GET /greet/?name=Ada returns 200 and a greeting"""
        response = greet(self.factory.get("/greet/", {"name": "Ada"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body(response), {"message": "Hello, Ada!"})

    def test_02_strips_name(self):
        """The name is stripped of surrounding whitespace"""
        response = greet(self.factory.get("/greet/", {"name": "  Grace  "}))
        self.assertEqual(body(response), {"message": "Hello, Grace!"})

    def test_03_missing_name(self):
        """A missing or blank name returns 400 with an error"""
        for params in [{}, {"name": "   "}]:
            response = greet(self.factory.get("/greet/", params))
            self.assertEqual(response.status_code, 400, f"params={params}")
            self.assertEqual(body(response), {"error": "name is required"})

    def test_04_greet_rejects_post(self):
        """greet only accepts GET (POST returns 405)"""
        self.assertEqual(greet(self.factory.post("/greet/")).status_code, 405)


class AddTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, raw):
        return add(self.factory.post("/add/", data=raw, content_type="application/json"))

    def test_05_adds_numbers(self):
        """POST {"a": 2, "b": 3.5} returns {"result": 5.5}"""
        response = self.post(json.dumps({"a": 2, "b": 3.5}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body(response), {"result": 5.5})

    def test_06_invalid_json(self):
        """An invalid JSON body returns 400 'invalid JSON'"""
        response = self.post("{not json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(body(response), {"error": "invalid JSON"})

    def test_07_not_numbers(self):
        """A missing or non-numeric a/b returns 400"""
        for payload in [{"a": 1}, {"a": "1", "b": 2}, {"a": None, "b": 2}]:
            response = self.post(json.dumps(payload))
            self.assertEqual(response.status_code, 400, f"payload={payload}")
            self.assertEqual(body(response), {"error": "a and b must be numbers"})

    def test_08_add_rejects_get(self):
        """add only accepts POST (GET returns 405)"""
        self.assertEqual(add(self.factory.get("/add/")).status_code, 405)
