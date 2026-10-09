import unittest

from task import filter_products

PRODUCTS = [
    {"name": "Widget", "price": 10.0},
    {"name": "Gadget", "price": 25.0},
    {"name": "Gizmo", "price": 15.0},
]


class FilterProductsTests(unittest.TestCase):
    def test_01_cheaper_products(self):
        """Keeps only the names of products at or under the price"""
        self.assertEqual(filter_products(PRODUCTS[:2], 15.0), ["Widget"])

    def test_02_price_is_inclusive(self):
        """A product that costs exactly max_price is kept, in the original order"""
        self.assertEqual(filter_products(PRODUCTS, 15.0), ["Widget", "Gizmo"])

    def test_03_nothing_matches(self):
        """Returns an empty list when nothing is cheap enough, or the list is empty"""
        self.assertEqual(filter_products(PRODUCTS, 5.0), [])
        self.assertEqual(filter_products([], 5.0), [])
