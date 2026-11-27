import unittest
from unittest.mock import patch

from backend.agentic_chat.services import agents


CATALOGUE = [
    {"product_name": "Laptop", "unit_price": 8200, "available_stock": 24},
    {"product_name": "PS5 CONTROLLER", "unit_price": 600, "available_stock": 87},
]


class ChatbotRegressionTests(unittest.TestCase):
    def test_stock_question_shows_only_stock(self):
        self.assertEqual(
            agents._requested_inventory_fields("What is the stock of Laptop?"),
            ["available_stock"],
        )

    def test_price_question_shows_only_price(self):
        self.assertEqual(
            agents._requested_inventory_fields("What is the price of Laptop?"),
            ["unit_price"],
        )

    def test_stock_and_price_question_shows_both(self):
        self.assertEqual(
            agents._requested_inventory_fields("Show Laptop stock and price"),
            ["unit_price", "available_stock"],
        )

    @patch.object(agents, "list_catalogue", return_value=CATALOGUE)
    def test_unknown_product_does_not_return_laptop(self, _catalogue):
        result = agents._inventory_agent({
            "query": "What is the stock of ZetaPad 9000?",
            "matched_products": [],
        })
        self.assertEqual(result["details"]["products"], [])
        self.assertIn("couldn't match", result["answer"])

    @patch.object(agents, "list_catalogue", return_value=CATALOGUE)
    def test_unknown_product_does_not_inherit_old_product(self, _catalogue):
        result = agents._supervisor({
            "query": "What is the stock of ZetaPad 9000?",
            "history": [{"role": "user", "content": "Check stock of Laptop"}],
        })
        self.assertEqual(result["route"], "inventory")
        self.assertEqual(result.get("matched_products", []), [])

    @patch.object(agents, "list_catalogue", return_value=CATALOGUE)
    def test_short_follow_up_keeps_previous_product_context(self, _catalogue):
        result = agents._supervisor({
            "query": "And its price?",
            "history": [{"role": "user", "content": "Check stock of Laptop"}],
        })
        self.assertEqual(result["route"], "inventory")
        self.assertEqual(result["matched_products"], ["Laptop"])

    @patch.object(agents, "list_catalogue", return_value=CATALOGUE)
    @patch.object(agents, "forecast_product_demand")
    def test_forecast_table_contains_only_estimate(self, forecast, _catalogue):
        forecast.return_value = {
            "product_name": "Laptop",
            "unit_price": 8200,
            "available_stock": 24,
            "period_days": 30,
            "observed_days": 7,
            "estimated_daily_demand": 0.9,
            "estimated_next_7_day_demand": 6.3,
            "estimated_stock_after_7_days": 17.7,
            "method": "baseline",
        }
        result = agents._forecast_agent({
            "query": "Forecast demand for Laptop next week",
            "matched_products": ["Laptop"],
        })
        self.assertEqual(
            list(result["details"]["estimates"][0]),
            ["product_name", "estimated_next_7_day_demand"],
        )

    def test_common_forest_typo_routes_to_forecast(self):
        self.assertEqual(agents._fallback_route("forest demand for Laptop"), "forecast")


if __name__ == "__main__":
    unittest.main()
