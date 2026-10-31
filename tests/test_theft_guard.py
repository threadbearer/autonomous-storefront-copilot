"""Unit tests for the TheftGuard engine and restock inhibit lock."""

import unittest
from src.engine.theft_guard import TheftGuard


class TestTheftGuard(unittest.TestCase):
    def setUp(self):
        self.guard = TheftGuard(
            high_theft_dwell_limit_seconds=40.0,
            standard_dwell_limit_seconds=120.0,
            checkout_grace_period_seconds=60.0,
        )

    def test_high_theft_dwell_alert_and_inhibit(self):
        # Customer enters high theft zone (Top shelf tequila)
        alert = self.guard.update_customer_dwell(
            customer_id="CUST-99",
            zone="Top-Shelf Tequila",
            is_high_theft_zone=True,
            dwell_seconds=15.0,
        )
        self.assertIsNone(alert)

        # Approaching threshold (32s is >= 40 * 0.75) -> Inhibit lock should activate!
        self.guard.update_customer_dwell(
            customer_id="CUST-99",
            zone="Top-Shelf Tequila",
            is_high_theft_zone=True,
            dwell_seconds=32.0,
        )
        is_inhibited, reason = self.guard.evaluate_restock_inhibit()
        self.assertTrue(is_inhibited)
        self.assertIn("INHIBIT", reason)
        self.assertIn("Top-Shelf Tequila", reason)

        # Exceeding threshold (45s >= 40s) -> raises alert
        alert = self.guard.update_customer_dwell(
            customer_id="CUST-99",
            zone="Top-Shelf Tequila",
            is_high_theft_zone=True,
            dwell_seconds=45.0,
        )
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "SUSPICIOUS_DWELL")
        self.assertEqual(alert.severity, "HIGH")

    def test_unpaid_exit_tripwire(self):
        # Customer spent 30s in high theft aisle
        self.guard.update_customer_dwell(
            customer_id="CUST-42",
            zone="Bourbon Aisle",
            is_high_theft_zone=True,
            dwell_seconds=30.0,
        )
        # Exits without paying
        exit_alert = self.guard.check_exit_tripwire("CUST-42")
        self.assertIsNotNone(exit_alert)
        self.assertEqual(exit_alert.alert_type, "UNPAID_EXIT")
        self.assertEqual(exit_alert.severity, "CRITICAL")


if __name__ == "__main__":
    unittest.main()
