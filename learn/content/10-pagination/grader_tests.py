import unittest

from pagination import paginate

ITEMS = list(range(1, 43))  # 42 items


class PaginateTests(unittest.TestCase):
    def test_01_first_page(self):
        """Page 1 returns the first page_size items and metadata"""
        result = paginate(ITEMS, page=1, page_size=10)
        self.assertEqual(result["results"], list(range(1, 11)))
        self.assertEqual(result["count"], 42)
        self.assertEqual(result["total_pages"], 5)
        self.assertEqual((result["previous_page"], result["next_page"]), (None, 2))

    def test_02_middle_page(self):
        """A middle page links to its neighbours"""
        result = paginate(ITEMS, page=3, page_size=10)
        self.assertEqual(result["results"], list(range(21, 31)))
        self.assertEqual((result["page"], result["previous_page"], result["next_page"]), (3, 2, 4))

    def test_03_last_page(self):
        """The last page may be shorter and has no next_page"""
        result = paginate(ITEMS, page=5, page_size=10)
        self.assertEqual(result["results"], [41, 42])
        self.assertIsNone(result["next_page"])

    def test_04_strings(self):
        """page and page_size can be strings (query params)"""
        result = paginate(ITEMS, page="2", page_size="20")
        self.assertEqual(result["page"], 2)
        self.assertEqual(result["results"], list(range(21, 41)))

    def test_05_invalid_numbers(self):
        """Non-numbers, zero and negatives raise ValueError"""
        for page, size in [("abc", 10), (0, 10), (-1, 10), (1, "ten"), (1, 0), (None, 10)]:
            with self.assertRaises(ValueError, msg=f"page={page!r}, page_size={size!r}"):
                paginate(ITEMS, page=page, page_size=size)

    def test_06_clamps_page_size(self):
        """page_size above max_page_size is clamped"""
        result = paginate(list(range(200)), page=1, page_size=1000, max_page_size=50)
        self.assertEqual(len(result["results"]), 50)
        self.assertEqual(result["total_pages"], 4)

    def test_07_page_out_of_range(self):
        """A page past the end raises ValueError('Invalid page.')"""
        with self.assertRaisesRegex(ValueError, "Invalid page."):
            paginate(ITEMS, page=6, page_size=10)

    def test_08_empty_list(self):
        """An empty list has one empty page"""
        result = paginate([], page=1)
        self.assertEqual((result["count"], result["total_pages"], result["results"]), (0, 1, []))
        self.assertEqual((result["previous_page"], result["next_page"]), (None, None))
