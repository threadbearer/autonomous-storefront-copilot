"""Unit tests for the DigitalTwin inventory state machine."""

from datetime import datetime
import unittest

from src.engine.digital_twin import DigitalTwin
from src.models.events import POSSaleEvent, POSSaleItem
from src.models.inventory import PaperPurchaseOrder, POLineItem
from src.models.sku import SKU, Category, PhysicalLocation, StorageZone


class TestDigitalTwin(unittest.TestCase):
    def setUp(self):
        self.dt = DigitalTwin()
        self.sample_item = SKU(
            sku_id="SKU-ENERGY-16OZ",
            upc="088004144694",
            name="Vitality Energy Drink 16oz",
            category=Category.BEVERAGES,
            shelf_capacity=5,
            pack_size=12,
            unit_weight_lbs=1.1,
            wholesale_unit_cost=1.80,
            retail_price=3.49,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 3, "Slot 2"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 2, "Bin 1"),
        )
        self.dt.register_sku(self.sample_item, initial_shelf=5, initial_cases=2, initial_loose=3)

    def test_pos_sale_depletes_shelf(self):
        inv = self.dt.inventory["SKU-ENERGY-16OZ"]
        self.assertEqual(inv.shelf_units, 5)

        event = POSSaleEvent(
            event_id="SALE-001",
            timestamp=datetime.now(),
            register_id="REG-1",
            items=[POSSaleItem(sku_id="SKU-ENERGY-16OZ", quantity=2, unit_price=3.49)],
            total_amount=6.98,
        )
        alerts = self.dt.process_pos_sale(event)
        self.assertEqual(inv.shelf_units, 3)
        self.assertEqual(len(alerts), 0)

        # Another sale causing critical deficit (<= 40%)
        event2 = POSSaleEvent(
            event_id="SALE-002",
            timestamp=datetime.now(),
            register_id="REG-1",
            items=[POSSaleItem(sku_id="SKU-ENERGY-16OZ", quantity=2, unit_price=3.49)],
            total_amount=6.98,
        )
        alerts2 = self.dt.process_pos_sale(event2)
        self.assertEqual(inv.shelf_units, 1)
        self.assertEqual(len(alerts2), 1)
        self.assertIn("[SHELF LOW]", alerts2[0])

    def test_supplier_po_with_cross_docking(self):
        inv = self.dt.inventory["SKU-ENERGY-16OZ"]
        # Deplete shelf to 0
        inv.shelf_units = 0

        po = PaperPurchaseOrder(
            distributor_name="Apex National Distribution",
            invoice_number="INV-1001",
            invoice_date="2026-10-30",
            line_items=[
                POLineItem(
                    sku_id="SKU-ENERGY-16OZ",
                    upc="088004144694",
                    description="Vitality Energy Drink 16oz",
                    pack_size=12,
                    cases_invoiced=3,
                    unit_cost=1.80,
                    case_cost=21.60,
                )
            ],
        )

        cross_dock_alerts = self.dt.receive_purchase_order(po)
        self.assertEqual(len(cross_dock_alerts), 1)
        self.assertEqual(cross_dock_alerts[0].suggested_cross_dock_units, 5)
        # Shelf immediately restored to capacity without backroom trip!
        self.assertEqual(inv.shelf_units, 5)
        # Remaining cases in backroom: 3 cases received - 1 cracked for cross-dock = 2 full cases
        # plus the initial 2 full cases = 4 full cases
        self.assertEqual(inv.backroom_full_cases, 4)
        # Leftovers from the cracked case: 12 - 5 = 7 loose + initial 3 loose = 10 loose
        self.assertEqual(inv.backroom_loose_units, 10)


if __name__ == "__main__":
    unittest.main()
