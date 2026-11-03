import unittest

from analytics import enrich_products, rank_products
from main import _normalize_row


class AnalyticsTests(unittest.TestCase):
    def test_anomaly_uses_within_category_median(self):
        products = [
            self.product(1, "Bike A", 100),
            self.product(2, "Bike B", 110),
            self.product(3, "Bike C", 500),
        ]
        enriched = enrich_products(products)

        self.assertFalse(enriched[0]["is_unusual"])
        self.assertTrue(enriched[2]["is_unusual"])
        self.assertIn("not proof of fraud", enriched[2]["anomaly_reason"])

    def test_small_category_is_not_flagged(self):
        products = [
            self.product(1, "Bike A", 100),
            self.product(2, "Bike B", 1000),
        ]
        enriched = enrich_products(products)

        self.assertTrue(all(not item["is_unusual"] for item in enriched))
        self.assertTrue(all("at least 3" in item["anomaly_reason"] for item in enriched))

    def test_priority_changes_top_recommendation(self):
        products = [
            self.product(1, "Low Price", 100, age=3, condition="Poor"),
            self.product(2, "Great Condition", 700, age=1, condition="Excellent"),
            self.product(3, "Middle", 500, age=2, condition="Good"),
        ]

        affordable = rank_products(products, 1000, "affordability")
        quality = rank_products(products, 1000, "condition")

        self.assertEqual(affordable["recommendations"][0]["title"], "Low Price")
        self.assertEqual(quality["recommendations"][0]["title"], "Great Condition")

    def test_missing_values_receive_neutral_scores(self):
        products = [self.product(1, "Incomplete", 400, age=None, condition=None)]
        result = rank_products(products, 1000)
        recommendation = result["recommendations"][0]

        self.assertEqual(recommendation["component_scores"]["age"], 50.0)
        self.assertEqual(recommendation["component_scores"]["condition"], 50.0)
        self.assertIn("age", recommendation["missing_fields"])
        self.assertIn("condition", recommendation["missing_fields"])

    def test_budget_and_category_define_eligibility(self):
        products = [
            self.product(1, "Bike", 900, category="Bicycle"),
            self.product(2, "Laptop", 900, category="Laptop"),
            self.product(3, "Expensive Bike", 1200, category="Bicycle"),
        ]
        result = rank_products(products, 1000, category="Bicycle")

        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["recommendations"][0]["title"], "Bike")

    def test_ties_are_deterministic(self):
        products = [
            self.product(9, "Later ID", 500),
            self.product(2, "Earlier ID", 500),
        ]
        result = rank_products(products, 1000)

        self.assertEqual(result["recommendations"][0]["id"], 2)

    def test_exact_duplicate_is_not_repeated_in_top_three(self):
        products = [
            self.product(1, "Same Laptop", 500, category="Laptop"),
            self.product(2, "Same Laptop", 500, category="Laptop"),
            self.product(3, "Different Laptop", 650, category="Laptop"),
        ]

        result = rank_products(products, 1000, category="Laptop")

        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual(
            [item["title"] for item in result["recommendations"]],
            ["Same Laptop", "Different Laptop"],
        )

    def test_pdf_style_import_headers_are_normalized(self):
        row = {
            "ID": "P01",
            "Item": "Laptop A",
            "Price ₹": "22000",
            "Age (years)": 0,
            "Condition": "Good",
            "Original ₹": "45000",
            "Category": "Laptop",
        }

        normalized = _normalize_row(row)

        self.assertEqual(normalized["title"], "Laptop A")
        self.assertEqual(normalized["price"], 22000)
        self.assertEqual(normalized["age"], 0)
        self.assertEqual(normalized["original_price"], 45000)

    @staticmethod
    def product(
        product_id,
        title,
        price,
        age=2,
        condition="Good",
        category="Bicycle",
    ):
        return {
            "id": product_id,
            "category": category,
            "title": title,
            "price": price,
            "age": age,
            "condition": condition,
            "original_price": price * 2,
        }


if __name__ == "__main__":
    unittest.main()
