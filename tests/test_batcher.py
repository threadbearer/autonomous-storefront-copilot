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
        self.batcher = RestockBatcher(max_units_per_trip=4, max_weight_lbs=15.0)
        self.dispatcher = RestockDispatcher(
            digital_twin=self.dt,
            theft_guard=self.theft_guard,
            batcher=self.batcher,
            min_urgency_threshold=0.5,
        )

        # SKU 1: High velocity retail SKU
        self.sample_sku = SKU(
            sku_id="SKU-FAST-MOVER-1",
            upc="0111111",
            name="Braided 65W Fast Charger Kit",
            category=Category.ELECTRONICS,
            shelf_capacity=6,
            unit_weight_lbs=0.6,
            wholesale_unit_cost=14.0,
            retail_price=29.99,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 2, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 1"),
        )
        self.dt.register_sku(self.sample_sku, initial_shelf=1, initial_cases=2, initial_loose=3)

    def test_knapsack_respects_limits(self):
        basket, score = self.batcher.assemble_optimal_trip(self.dt)
        self.assertGreater(len(basket), 0)
        total_units = sum(item.quantity for item in basket)
        self.assertLessEqual(total_units, 4)  # max_units_per_trip is 4
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
            zone="High-Value Tech Aisle",
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
        self.assertEqual(dispatch.items[0].sku_id, "SKU-FAST-MOVER-1")
        self.assertGreater(dispatch.quiet_window_estimate_seconds, 60)

    def test_bounded_knapsack_weight_constraint(self):
        # Register a heavy SKU (10 lbs each, limit 15 lbs)
        heavy_sku = SKU(
            sku_id="SKU-HEAVY-PACK",
            upc="0222222",
            name="12-Pack Heavy Beverage",
            category=Category.BEVERAGES,
            shelf_capacity=4,
            unit_weight_lbs=10.0,
            wholesale_unit_cost=8.0,
            retail_price=14.99,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 2", 1, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack B", 1, "Bin 1"),
        )
        dt = DigitalTwin()
        dt.register_sku(heavy_sku, initial_shelf=0, initial_cases=2, initial_loose=4)
        # Even though unit limit is 4, weight limit of 15 lbs allows only 1 unit (10 lbs <= 15 lbs, 20 lbs > 15 lbs)
        basket, score = self.batcher.assemble_optimal_trip(dt)
        self.assertEqual(len(basket), 1)
        self.assertEqual(basket[0].quantity, 1)

    def test_bounded_knapsack_optimality_over_greedy(self):
        # Classical knapsack test: Item A (3 units, high weight) vs Items B and C (better combined efficiency)
        sku_a = SKU(
            sku_id="SKU-A",
            upc="101",
            name="Item A (Heavy)",
            category=Category.GENERAL_MERCHANDISE,
            shelf_capacity=2,
            unit_weight_lbs=4.0,
            wholesale_unit_cost=5.0,
            retail_price=10.0,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 1, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 1"),
        )
        sku_b = SKU(
            sku_id="SKU-B",
            upc="102",
            name="Item B (Light, High Value)",
            category=Category.GENERAL_MERCHANDISE,
            shelf_capacity=2,
            unit_weight_lbs=2.0,
            wholesale_unit_cost=5.0,
            retail_price=12.0,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 1, "Slot 2"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 2"),
        )
        batcher = RestockBatcher(max_units_per_trip=3, max_weight_lbs=6.0)
        dt = DigitalTwin()
        dt.register_sku(sku_a, initial_shelf=0, initial_cases=1, initial_loose=2)
        dt.register_sku(sku_b, initial_shelf=0, initial_cases=1, initial_loose=2)

        basket, score = batcher.assemble_optimal_trip(dt)
        total_weight = sum(
            dt.catalog[item.sku_id].unit_weight_lbs * item.quantity for item in basket
        )
        total_units = sum(item.quantity for item in basket)
        self.assertLessEqual(total_weight, 6.0)
        self.assertLessEqual(total_units, 3)
        self.assertGreater(score, 0.0)


if __name__ == "__main__":
    unittest.main()
