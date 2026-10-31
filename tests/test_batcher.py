"""Unit tests for the RestockBatcher and RestockDispatcher."""

import unittest
from src.engine.batcher import RestockBatcher
from src.engine.digital_twin import DigitalTwin
from src.engine.dispatcher import RestockDispatcher
from src.engine.theft_guard import TheftGuard
from src.models.sku import SKU, Category, PhysicalLocation, StorageZone


class TestBatcherAndDispatcher(unittest.TestCase):
    def setUp(self):
        self.dt = DigitalTwin()
        self.theft_guard = TheftGuard()
        self.batcher = RestockBatcher(max_bottles_per_trip=4, max_weight_lbs=15.0)
        self.dispatcher = RestockDispatcher(
            digital_twin=self.dt,
            theft_guard=self.theft_guard,
            batcher=self.batcher,
            min_urgency_threshold=0.5,
        )

        # SKU 1: High velocity vodka
        self.vodka = SKU(
            sku_id="SKU-VODKA-1",
            upc="0111111",
            name="Top Vodka 750ml",
            category=Category.VODKA,
            shelf_capacity=6,
            unit_weight_lbs=3.0,
            wholesale_unit_cost=15.0,
            retail_price=25.0,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 2, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 1"),
        )
        self.dt.register_sku(self.vodka, initial_shelf=1, initial_cases=2, initial_loose=3)

    def test_knapsack_respects_limits(self):
        basket, score = self.batcher.assemble_optimal_trip(self.dt)
        self.assertGreater(len(basket), 0)
        total_bottles = sum(item.quantity for item in basket)
        self.assertLessEqual(total_bottles, 4)  # max_bottles_per_trip is 4
        self.assertGreater(score, 0.0)

    def test_dispatcher_blocked_by_counter_queue(self):
        # When queue length is 1
        dispatch, reason = self.dispatcher.evaluate_dispatch(counter_queue_length=1)
        self.assertIsNone(dispatch)
        self.assertIn("Counter busy", reason)

    def test_dispatcher_blocked_by_theft_inhibit(self):
        # Trigger theft loitering in high-theft zone
        self.theft_guard.update_customer_dwell(
            customer_id="SUSPECT-1",
            zone="Cognac Aisle",
            is_high_theft_zone=True,
            dwell_seconds=40.0,
        )
        dispatch, reason = self.dispatcher.evaluate_dispatch(counter_queue_length=0)
        self.assertIsNone(dispatch)
        self.assertIn("INHIBIT", reason)

    def test_dispatcher_triggers_in_quiet_window(self):
        # Counter is clear, no theft, inventory low
        dispatch, reason = self.dispatcher.evaluate_dispatch(
            counter_queue_length=0, estimated_arrival_rate_per_min=0.1
        )
        self.assertIsNotNone(dispatch)
        self.assertEqual(dispatch.items[0].sku_id, "SKU-VODKA-1")
        self.assertGreater(dispatch.quiet_window_estimate_seconds, 60)


if __name__ == "__main__":
    unittest.main()
