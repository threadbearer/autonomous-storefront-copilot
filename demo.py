#!/usr/bin/env python3
"""Interactive demonstration of the Autonomous Storefront Logistics & Copilot Engine."""

import time
from datetime import datetime

from src.engine.batcher import RestockBatcher
from src.engine.digital_twin import DigitalTwin
from src.engine.dispatcher import RestockDispatcher
from src.engine.document_parser import PurchaseOrderParser
from src.engine.theft_guard import TheftGuard
from src.models.events import DeliveryOrderEvent, DeliveryOrderItem, POSSaleEvent, POSSaleItem
from src.models.sku import Category, PhysicalLocation, SKU, StorageZone

# ANSI Color codes for clean terminal output
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def header(title: str):
    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")


def print_shelf_status(dt: DigitalTwin):
    print(f"{BOLD}Current Shelf Facings (Single-Facing Physical Constraint):{RESET}")
    print(f"{'SKU Name':<32} | {'Shelf':<8} | {'Backroom':<14} | {'Status'}")
    print("-" * 75)
    for sku_id, sku in dt.catalog.items():
        inv = dt.inventory[sku_id]
        ratio = inv.shelf_fill_ratio
        if ratio == 0:
            status = f"{RED}[OUT OF STOCK]{RESET}"
        elif ratio <= sku.restock_trigger_ratio:
            status = f"{YELLOW}[LOW - DEFICIT {inv.shelf_deficit}]{RESET}"
        else:
            status = f"{GREEN}[HEALTHY]{RESET}"

        shelf_str = f"{inv.shelf_units}/{inv.shelf_capacity}"
        backroom_str = f"{inv.backroom_full_cases}cs + {inv.backroom_loose_units} loose"
        print(f"{sku.name:<32} | {shelf_str:<8} | {backroom_str:<14} | {status}")
    print("-" * 75)


def run_demo():
    header("AUTONOMOUS STOREFRONT COPILOT: SINGLE-OPERATOR RETAIL LOGISTICS")

    # 1. Setup store catalog
    dt = DigitalTwin()
    theft_guard = TheftGuard(high_theft_dwell_limit_seconds=40.0)
    batcher = RestockBatcher(max_units_per_trip=6, max_weight_lbs=24.0)
    dispatcher = RestockDispatcher(
        digital_twin=dt,
        theft_guard=theft_guard,
        batcher=batcher,
        min_urgency_threshold=0.8,
    )

    skus = [
        SKU(
            sku_id="SKU-ENERGY-16OZ",
            upc="088004144694",
            name="Vitality Energy Drink 16oz",
            category=Category.BEVERAGES,
            shelf_capacity=5,
            pack_size=12,
            unit_weight_lbs=1.1,
            wholesale_unit_cost=1.80,
            retail_price=3.49,
            is_high_theft=False,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 3, "Slot 2"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 2, "Bin 1"),
        ),
        SKU(
            sku_id="SKU-USB-CHARGER",
            upc="858000005018",
            name="Braided 65W Fast Charger Kit",
            category=Category.ELECTRONICS,
            shelf_capacity=4,
            pack_size=6,
            unit_weight_lbs=0.6,
            wholesale_unit_cost=14.0,
            retail_price=29.99,
            is_high_theft=True,
            theft_dwell_threshold_seconds=40,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 2 (High-Value Tech)", 4, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack B", 3, "Bin 2"),
        ),
        SKU(
            sku_id="SKU-PROTEIN-BARS",
            upc="088004000303",
            name="Artisan Protein Bars 10-Pack",
            category=Category.SNACKS_GRAB_AND_GO,
            shelf_capacity=8,
            pack_size=24,
            unit_weight_lbs=1.2,
            wholesale_unit_cost=8.50,
            retail_price=15.99,
            is_high_theft=True,
            theft_dwell_threshold_seconds=30,
            shelf_location=PhysicalLocation(StorageZone.REGISTER_COUNTER, "Counter Tier 1", 1, "Bin A"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 4"),
        ),
        SKU(
            sku_id="SKU-SPARKLING-12PK",
            upc="033544000138",
            name="Craft Sparkling Water 12-Pack",
            category=Category.BEVERAGES,
            shelf_capacity=6,
            pack_size=2,
            unit_weight_lbs=9.5,
            wholesale_unit_cost=6.0,
            retail_price=10.99,
            is_high_theft=False,
            shelf_location=PhysicalLocation(StorageZone.COLD_VAULT, "Cold Vault Door 2", 2, "Facing 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_FLOOR, "Floor Pallet", 1, "Skid C"),
        ),
    ]

    # Initialize physical store state
    dt.register_sku(skus[0], initial_shelf=5, initial_cases=3, initial_loose=2)
    dt.register_sku(skus[1], initial_shelf=4, initial_cases=2, initial_loose=1)
    dt.register_sku(skus[2], initial_shelf=8, initial_cases=1, initial_loose=10)
    dt.register_sku(skus[3], initial_shelf=6, initial_cases=5, initial_loose=0)

    print(f"{YELLOW}Initial Shift State: 1 Associate at POS Register. Shelves fully stocked.{RESET}")
    print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 1: Sales Rush depletes single facings
    # -------------------------------------------------------------
    header("SCENARIO 1: Consecutive Customers Deplete Single-Faced Shelves")
    print("Customer 1 buys 4 Vitality Energy Drinks for office workers.")
    print("Customer 2 buys 3 Fast Charger Kits.")
    print("Customer 3 buys 6 Protein Bar packs.")

    dt.process_pos_sale(
        POSSaleEvent(
            event_id="POS-01",
            timestamp=datetime.now(),
            register_id="POS-1",
            items=[
                POSSaleItem("SKU-ENERGY-16OZ", 4, 3.49),
                POSSaleItem("SKU-USB-CHARGER", 3, 29.99),
                POSSaleItem("SKU-PROTEIN-BARS", 6, 15.99),
            ],
            total_amount=199.87,
        )
    )
    theft_guard.record_checkout("CUST-01")

    print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 2: Register Queue blocks hasty restock
    # -------------------------------------------------------------
    header("SCENARIO 2: Register Queue Blocks Unsafe Restock Trip")
    print("Associate notices Energy Drinks and Chargers are down to 1 item remaining.")
    print("Associate is tempted to run to the back immediately, BUT 2 customers are waiting in line.")

    dispatch, reason = dispatcher.evaluate_dispatch(counter_queue_length=2)
    print(f"{YELLOW}[DISPATCH EVALUATION]{RESET}: {reason}")
    print(f"{GREEN}Outcome:{RESET} Associate stays at register, finishes checking out line.")

    # -------------------------------------------------------------
    # SCENARIO 3: Quiet Window Opens -> Intelligent Batch Dispatch
    # -------------------------------------------------------------
    header("SCENARIO 3: Quiet Window Opens -> Automated Batch Dispatch")
    print("Counter queue cleared to 0. Store entry pace is slow.")
    dispatch, reason = dispatcher.evaluate_dispatch(counter_queue_length=0, estimated_arrival_rate_per_min=0.15)

    if dispatch:
        print(f"{GREEN}{BOLD}>>> [SMARTWATCH / REGISTER NOTIFICATION] <<<{RESET}")
        print(f"Dispatch ID: {dispatch.dispatch_id}")
        print(f"Window: ~{dispatch.quiet_window_estimate_seconds}s quiet window | Estimated Trip: {dispatch.estimated_trip_duration_seconds}s")
        print(f"Urgency Score: {dispatch.restock_urgency_score} (Safety Score: {dispatch.safety_score})")
        print(f"\n{BOLD}Optimal Pick Batch (Carrying {dispatch.total_units} units):{RESET}")
        for item in dispatch.items:
            print(f"  • Grab {item.quantity}x {item.sku_name}")
            print(f"    Source: {item.source_location} -> Target: {item.target_shelf}")
        
        # Execute restock
        print(f"\n{CYAN}Associate walks to backroom, grabs items from mapped coordinates, and stocks shelves.{RESET}")
        dt.execute_restock_trip(dispatch)
        print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 4: Shoplifting Threat -> Restock Inhibit Lock
    # -------------------------------------------------------------
    header("SCENARIO 4: Shoplifting Behavior -> Restock Inhibit Lock")
    print("Store is quiet, but camera detects Customer X loitering in the High-Value Tech aisle.")
    theft_guard.update_customer_dwell(
        customer_id="CUST-SUSPECT-X",
        zone="Aisle 2 (High-Value Tech)",
        is_high_theft_zone=True,
        dwell_seconds=35.0,  # Approaching 40s limit
    )

    dispatch, reason = dispatcher.evaluate_dispatch(counter_queue_length=0)
    print(f"{RED}{BOLD}>>> [SECURITY ALERT: RESTOCK INHIBITED] <<<{RESET}")
    print(f"System Message: {reason}")
    print(f"{YELLOW}Action:{RESET} Associate does NOT enter backroom. Maintains visual eye contact on sales floor.")

    print("\nCustomer X notices associate is watching, puts item back, and heads to exit.")
    exit_alert = theft_guard.check_exit_tripwire("CUST-SUSPECT-X")
    if exit_alert:
        print(f"{YELLOW}[EXIT TRIPWIRE AUDIT]: {exit_alert.message}{RESET}")

    # -------------------------------------------------------------
    # SCENARIO 5: Supplier Truck Delivery & Paper PO Digitization
    # -------------------------------------------------------------
    header("SCENARIO 5: Supplier Weekly Truck Delivery (Paper PO & Cross-Docking)")
    print("Apex National delivery driver carts in 9 cases into backroom and hands associate a paper invoice.")
    mock_po = PurchaseOrderParser.create_mock_delivery_invoice("APEX")
    print(f"Digitized Invoice: {mock_po.invoice_number} from {mock_po.distributor_name}")
    print(f"Total Cases on Manifest: {mock_po.total_cases} cases | Invoice Total: ${mock_po.total_invoice_amount:,.2f}")

    print(f"\n{CYAN}Running Automated Cross-Dock Analysis...{RESET}")
    cross_dock_alerts = dt.receive_purchase_order(mock_po)
    for alert in cross_dock_alerts:
        print(f"{MAGENTA}{BOLD}>>> [CROSS-DOCK DIRECTIVE] <<<{RESET}")
        print(f"SKU: {alert.sku_name}")
        print(f"Directive: Take {alert.suggested_cross_dock_units} units straight from inbound pallet to {alert.target_shelf_location}!")
        print(f"Rationale: {alert.rationale}")

    print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 6: Delivery App Order (DoorDash / Courier)
    # -------------------------------------------------------------
    header("SCENARIO 6: On-Demand Courier Order Gathering & Reservation")
    print("Courier fulfillment tablet rings: Order #ORD-789 (1x Fast Charger Kit, 1x Sparkling Water 12-Pack).")
    courier_order = DeliveryOrderEvent(
        order_id="ORD-789",
        platform="DoorDash",
        timestamp=datetime.now(),
        items=[
            DeliveryOrderItem("SKU-SPARKLING-12PK", 1),
            DeliveryOrderItem("SKU-USB-CHARGER", 1),
        ],
    )
    dt.process_delivery_order(courier_order)
    print("Items reserved in system for courier driver pickup.")
    dt.complete_delivery_order("ORD-789")
    print(f"{GREEN}Order picked, bagged, and handed to courier.{RESET}")
    print_shelf_status(dt)

    header("SIMULATION COMPLETE")
    print(f"{GREEN}The system successfully balanced single-worker labor, shelf facings, loss prevention, and receiving!{RESET}\n")


if __name__ == "__main__":
    run_demo()
