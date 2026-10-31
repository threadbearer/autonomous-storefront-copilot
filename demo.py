#!/usr/bin/env python3
"""Interactive demonstration of the Autonomous Liquor Store Logistics & Copilot Engine."""

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
    header("LIQUOR STORE LOGISTICS & SINGLE-CLERK COPILOT SIMULATION")

    # 1. Setup store catalog
    dt = DigitalTwin()
    theft_guard = TheftGuard(high_theft_dwell_limit_seconds=40.0)
    batcher = RestockBatcher(max_bottles_per_trip=6, max_weight_lbs=24.0)
    dispatcher = RestockDispatcher(
        digital_twin=dt,
        theft_guard=theft_guard,
        batcher=batcher,
        min_urgency_threshold=0.8,
    )

    skus = [
        SKU(
            sku_id="SKU-TITOS-750",
            upc="088004144694",
            name="Tito's Vodka 750ml",
            category=Category.VODKA,
            shelf_capacity=5,
            pack_size=12,
            unit_weight_lbs=3.0,
            wholesale_unit_cost=16.0,
            retail_price=24.99,
            is_high_theft=False,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 3, "Slot 2"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 2, "Bin 1"),
        ),
        SKU(
            sku_id="SKU-CASAMIGOS-BLANCO-750",
            upc="858000005018",
            name="Casamigos Blanco 750ml",
            category=Category.TEQUILA,
            shelf_capacity=4,
            pack_size=6,
            unit_weight_lbs=3.2,
            wholesale_unit_cost=42.0,
            retail_price=56.99,
            is_high_theft=True,
            theft_dwell_threshold_seconds=40,
            shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 2 (Top Shelf)", 4, "Slot 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack B", 3, "Bin 2"),
        ),
        SKU(
            sku_id="SKU-FIREBALL-50",
            upc="088004000303",
            name="Fireball 50ml Sleeves (10pk)",
            category=Category.SHOOTERS,
            shelf_capacity=8,
            pack_size=120,
            unit_weight_lbs=1.2,
            wholesale_unit_cost=7.50,
            retail_price=11.99,
            is_high_theft=True,
            theft_dwell_threshold_seconds=30,
            shelf_location=PhysicalLocation(StorageZone.REGISTER_COUNTER, "Counter Tier 1", 1, "Bin A"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 1, "Bin 4"),
        ),
        SKU(
            sku_id="SKU-MODELO-12PK",
            upc="033544000138",
            name="Modelo Especial 12-Pack Cans",
            category=Category.BEER,
            shelf_capacity=6,
            pack_size=2,
            unit_weight_lbs=10.0,
            wholesale_unit_cost=15.0,
            retail_price=20.99,
            is_high_theft=False,
            shelf_location=PhysicalLocation(StorageZone.COOLER_DOOR, "Cooler Door 2", 2, "Facing 1"),
            backroom_location=PhysicalLocation(StorageZone.BACKROOM_FLOOR, "Floor Pallet", 1, "Skid C"),
        ),
    ]

    # Initialize physical store state
    dt.register_sku(skus[0], initial_shelf=5, initial_cases=3, initial_loose=2)
    dt.register_sku(skus[1], initial_shelf=4, initial_cases=2, initial_loose=1)
    dt.register_sku(skus[2], initial_shelf=8, initial_cases=1, initial_loose=10)
    dt.register_sku(skus[3], initial_shelf=6, initial_cases=5, initial_loose=0)

    print(f"{YELLOW}Initial Shift State: 1 Clerk at POS Register. Shelves fully stocked.{RESET}")
    print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 1: Sales Rush depletes single facings
    # -------------------------------------------------------------
    header("SCENARIO 1: Consecutive Customers Deplete Single-Faced Shelves")
    print(f"Customer 1 buys 4 Tito's 750ml bottles for a party.")
    print(f"Customer 2 buys 3 Casamigos Blanco bottles.")
    print(f"Customer 3 buys 6 Fireball 50ml sleeves.")

    dt.process_pos_sale(
        POSSaleEvent(
            event_id="POS-01",
            timestamp=datetime.now(),
            register_id="POS360-1",
            items=[
                POSSaleItem("SKU-TITOS-750", 4, 24.99),
                POSSaleItem("SKU-CASAMIGOS-BLANCO-750", 3, 56.99),
                POSSaleItem("SKU-FIREBALL-50", 6, 11.99),
            ],
            total_amount=342.91,
        )
    )
    theft_guard.record_checkout("CUST-01")

    print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 2: Register Queue blocks hasty restock
    # -------------------------------------------------------------
    header("SCENARIO 2: Register Queue Blocks Unsafe Restock Trip")
    print("Clerk notices Tito's and Casamigos are at 1 bottle remaining.")
    print("Clerk is tempted to run to the back immediately, BUT 2 customers are waiting in line.")

    dispatch, reason = dispatcher.evaluate_dispatch(counter_queue_length=2)
    print(f"{YELLOW}[DISPATCH EVALUATION]{RESET}: {reason}")
    print(f"{GREEN}Outcome:{RESET} Clerk stays at register, finishes checking out line.")

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
        print(f"\n{BOLD}Optimal Pick Batch (Carrying {dispatch.total_bottles} bottles):{RESET}")
        for item in dispatch.items:
            print(f"  • Grab {item.quantity}x {item.sku_name}")
            print(f"    Source: {item.source_location} -> Target: {item.target_shelf}")
        
        # Execute restock
        print(f"\n{CYAN}Clerk walks to backroom, grabs items from mapped coordinates, and stocks shelves.{RESET}")
        dt.execute_restock_trip(dispatch)
        print_shelf_status(dt)

    # -------------------------------------------------------------
    # SCENARIO 4: Shoplifting Threat -> Restock Inhibit Lock
    # -------------------------------------------------------------
    header("SCENARIO 4: Shoplifting Behavior -> Restock Inhibit Lock")
    print("Store is quiet, but camera detects Customer X loitering in the Top-Shelf Tequila aisle.")
    theft_guard.update_customer_dwell(
        customer_id="CUST-SUSPECT-X",
        zone="Aisle 2 (Top-Shelf Tequila)",
        is_high_theft_zone=True,
        dwell_seconds=35.0,  # Approaching 40s limit
    )

    dispatch, reason = dispatcher.evaluate_dispatch(counter_queue_length=0)
    print(f"{RED}{BOLD}>>> [SECURITY ALERT: RESTOCK INHIBITED] <<<{RESET}")
    print(f"System Message: {reason}")
    print(f"{YELLOW}Action:{RESET} Clerk does NOT enter backroom. Maintains visual eye contact on sales floor.")

    print("\nCustomer X notices clerk is watching, puts bottle back, and heads to exit.")
    exit_alert = theft_guard.check_exit_tripwire("CUST-SUSPECT-X")
    if exit_alert:
        print(f"{YELLOW}[EXIT TRIPWIRE AUDIT]: {exit_alert.message}{RESET}")

    # -------------------------------------------------------------
    # SCENARIO 5: Supplier Truck Delivery & Paper PO Digitization
    # -------------------------------------------------------------
    header("SCENARIO 5: Supplier Weekly Truck Delivery (Paper PO & Cross-Docking)")
    print("Southern Glazer's delivery driver carts in 9 cases into backroom and hands clerk a paper invoice.")
    mock_po = PurchaseOrderParser.create_mock_delivery_invoice("SGWS")
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
    # SCENARIO 6: Delivery App Order (Uber Eats)
    # -------------------------------------------------------------
    header("SCENARIO 6: Uber Eats Order Gathering & Piggyback Restock")
    print("Uber Eats tablet rings: Order #UBER-789 (1x Modelo 12-Pack, 1x Casamigos Blanco).")
    uber_order = DeliveryOrderEvent(
        order_id="UBER-789",
        platform="Uber Eats",
        timestamp=datetime.now(),
        items=[
            DeliveryOrderItem("SKU-MODELO-12PK", 1),
            DeliveryOrderItem("SKU-CASAMIGOS-BLANCO-750", 1),
        ],
    )
    dt.process_delivery_order(uber_order)
    print("Items reserved in system for delivery driver pickup.")
    dt.complete_delivery_order("UBER-789")
    print(f"{GREEN}Order picked, bagged, and handed to courier.{RESET}")
    print_shelf_status(dt)

    header("SIMULATION COMPLETE")
    print(f"{GREEN}The system successfully balanced single-worker labor, shelf facings, loss prevention, and receiving!{RESET}\n")


if __name__ == "__main__":
    run_demo()
