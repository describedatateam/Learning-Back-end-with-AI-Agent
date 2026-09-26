import unittest

from slugs import make_slug


class MakeSlugTests(unittest.TestCase):
    def test_basic_title(self):
        self.assertEqual(make_slug("hello world"), "hello-world")

    # Step 1 is done: keep test_basic_title above.
    # Each new test is a method whose name starts with "test_". Give each one a new name.
    # TODO 2: test that capital letters come out lower-case, e.g. "  Hello, World!  "
    # TODO 3: test that a run of symbols becomes ONE "-", e.g. "Django & DRF 101"
    # TODO 4: test that a long title gives at most 50 characters and doesn't end with "-"
    # TODO 5: test that make_slug("!!!") raises ValueError (use self.assertRaises)
