"""Discrete event simulation engine benchmarking AI Restock Dispatcher vs Naive restocking strategies."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
import random
from typing import Dict, List, Optional, Tuple

from src.engine.batcher import RestockBatcher
from src.engine.digital_twin import DigitalTwin
from src.engine.dispatcher import RestockDispatcher
from src.engine.document_parser import PurchaseOrderParser
from src.engine.theft_guard import TheftGuard
from src.models.events import DeliveryOrderEvent, DeliveryOrderItem, POSSaleEvent, POSSaleItem
from src.models.sku import Category, PhysicalLocation, SKU, StorageZone


class StrategyType(str, Enum):
    IMMEDIATE = "immediate"      # Restock after every single customer purchase (exhausting, leaves counter)
    END_OF_SHIFT = "end_of_shift"# Never restock until shift ends (lots of stockouts)
    AI_DISPATCHER = "ai_copilot" # Optimal batching + safe quiet window + loss prevention inhibit


class CustomerIntent(str, Enum):
    HONEST_SHOPPER = "honest_shopper"
    OPPORTUNISTIC_THIEF = "opportunistic_thief"


@dataclass
class SimCustomer:
    customer_id: str
    intent: CustomerIntent
    target_sku_id: str
    target_zone: str
    is_high_theft: bool
    arrival_minute: int
    browse_duration_minutes: int
    checkout_duration_seconds: int = 45
    dwell_minutes: int = 0
    state: str = "BROWSING"  # BROWSING, IN_LINE, CHECKING_OUT, EXITED, STOLE_ITEM


@dataclass
class SimulationMetrics:
    total_sales_dollars: float = 0.0
    lost_sales_dollars: float = 0.0
    stockout_minutes: int = 0
    restock_trips_made: int = 0
    clerk_counter_abandoned_minutes: int = 0
    theft_attempts: int = 0
    thefts_deterred: int = 0
    thefts_succeeded: int = 0
    dollars_lost_to_theft: float = 0.0
    cross_dock_units_routed: int = 0


class StoreSimulator:
    """Simulates a realistic 8-hour retail shift with customers, rushes, thefts, and deliveries."""

    def __init__(
        self,
        strategy: StrategyType = StrategyType.AI_DISPATCHER,
        shift_duration_minutes: int = 480,  # 8 hours
        random_seed: int = 42,
    ):
        self.strategy = strategy
        self.shift_duration_minutes = shift_duration_minutes
        self.random = random.Random(random_seed)
        
        # State engines
        self.dt = DigitalTwin()
        self.theft_guard = TheftGuard(high_theft_dwell_limit_seconds=40.0)
        self.batcher = RestockBatcher(max_bottles_per_trip=6, max_weight_lbs=24.0)
        self.dispatcher = RestockDispatcher(
            digital_twin=self.dt,
            theft_guard=self.theft_guard,
            batcher=self.batcher,
            min_urgency_threshold=0.8,
        )

        self.metrics = SimulationMetrics()
        self._init_standard_catalog()

    def _init_standard_catalog(self):
        """Initializes standard liquor store SKUs with realistic velocities."""
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
                sku_id="SKU-HENNESSY-VS-375",
                upc="088110551025",
                name="Hennessy VS Cognac 375ml",
                category=Category.COGNAC,
                shelf_capacity=6,
                pack_size=24,
                unit_weight_lbs=1.8,
                wholesale_unit_cost=18.50,
                retail_price=26.99,
                is_high_theft=True,
                theft_dwell_threshold_seconds=35,
                shelf_location=PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 2 (Top Shelf)", 4, "Slot 2"),
                backroom_location=PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack B", 2, "Bin 1"),
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

        # Register SKUs with realistic initial backroom stock
        self.dt.register_sku(skus[0], initial_shelf=5, initial_cases=4, initial_loose=3)
        self.dt.register_sku(skus[1], initial_shelf=4, initial_cases=3, initial_loose=1)
        self.dt.register_sku(skus[2], initial_shelf=6, initial_cases=2, initial_loose=4)
        self.dt.register_sku(skus[3], initial_shelf=8, initial_cases=2, initial_loose=15)
        self.dt.register_sku(skus[4], initial_shelf=6, initial_cases=6, initial_loose=0)

    def run_shift(self) -> SimulationMetrics:
        """Executes the simulation across the entire shift duration minute by minute."""
        active_customers: List[SimCustomer] = []
        counter_queue: List[SimCustomer] = []
        clerk_in_backroom_until_minute = -1
        supplier_delivery_minute = 180  # Delivery truck arrives at hour 3 (minute 180)

        # SKU popularity weights
        sku_keys = list(self.dt.catalog.keys())
        sku_weights = [0.35, 0.20, 0.15, 0.20, 0.10]

        for current_min in range(self.shift_duration_minutes):
            is_clerk_at_counter = current_min >= clerk_in_backroom_until_minute

            # Check for stockout penalty
            for sku_id, inv in self.dt.inventory.items():
                if inv.shelf_units == 0:
                    self.metrics.stockout_minutes += 1

            # 1. Weekly Supplier Delivery at Minute 180
            if current_min == supplier_delivery_minute:
                po = PurchaseOrderParser.create_mock_delivery_invoice("SGWS")
                cross_docks = self.dt.receive_purchase_order(po)
                for cd in cross_docks:
                    self.metrics.cross_dock_units_routed += cd.suggested_cross_dock_units

            # 2. Stochastic Customer Arrivals (Poisson process)
            # Rush hours: 120-180 (Hour 2-3) and 360-440 (Hour 6-7)
            is_rush = (120 <= current_min <= 180) or (360 <= current_min <= 440)
            arrival_rate = 0.50 if is_rush else 0.15  # Avg customers arriving per minute

            if self.random.random() < arrival_rate:
                chosen_sku = self.random.choices(sku_keys, weights=sku_weights, k=1)[0]
                sku_obj = self.dt.catalog[chosen_sku]

                # 5% chance of an opportunistic thief
                is_thief = self.random.random() < 0.05 and sku_obj.is_high_theft
                intent = CustomerIntent.OPPORTUNISTIC_THIEF if is_thief else CustomerIntent.HONEST_SHOPPER

                cust = SimCustomer(
                    customer_id=f"CUST-{current_min:03d}-{len(active_customers)}",
                    intent=intent,
                    target_sku_id=chosen_sku,
                    target_zone=sku_obj.shelf_location.aisle_or_cooler,
                    is_high_theft=sku_obj.is_high_theft,
                    arrival_minute=current_min,
                    browse_duration_minutes=self.random.randint(1, 3),
                )
                active_customers.append(cust)

            # 3. Process Active Customers in Aisles
            for cust in list(active_customers):
                cust.dwell_minutes += 1
                
                # Update theft guard
                if cust.is_high_theft:
                    self.theft_guard.update_customer_dwell(
                        customer_id=cust.customer_id,
                        zone=cust.target_zone,
                        is_high_theft_zone=True,
                        dwell_seconds=cust.dwell_minutes * 60.0,
                    )

                # Shoplifting Opportunist Behavior
                if cust.intent == CustomerIntent.OPPORTUNISTIC_THIEF:
                    self.metrics.theft_attempts += 1
                    sku_target = self.dt.catalog[cust.target_sku_id]
                    inv = self.dt.inventory[cust.target_sku_id]

                    # Shoplifter succeeds ONLY if the clerk is NOT at the counter and item is on shelf!
                    if not is_clerk_at_counter and inv.shelf_units > 0:
                        cust.state = "STOLE_ITEM"
                        self.dt.record_shrink_anomaly(cust.target_sku_id, 1, "Theft while clerk in backroom")
                        self.metrics.thefts_succeeded += 1
                        self.metrics.dollars_lost_to_theft += sku_target.retail_price
                        self.theft_guard.clear_customer_track(cust.customer_id)
                        active_customers.remove(cust)
                    else:
                        # Clerk was at counter! Shoplifter deterred
                        self.metrics.thefts_deterred += 1
                        if cust.dwell_minutes >= 2:
                            self.theft_guard.clear_customer_track(cust.customer_id)
                            active_customers.remove(cust)
                    continue

                # Honest Shopper Behavior
                if cust.dwell_minutes >= cust.browse_duration_minutes and cust.state == "BROWSING":
                    cust.state = "IN_LINE"
                    self.theft_guard.clear_customer_track(cust.customer_id)
                    counter_queue.append(cust)
                    active_customers.remove(cust)

            # 4. Service Customer at POS Register
            if is_clerk_at_counter and counter_queue:
                serving_cust = counter_queue.pop(0)
                inv = self.dt.inventory[serving_cust.target_sku_id]
                sku_target = self.dt.catalog[serving_cust.target_sku_id]

                if inv.shelf_units > 0:
                    # Successful sale!
                    self.dt.process_pos_sale(
                        POSSaleEvent(
                            event_id=f"POS-{current_min}",
                            timestamp=datetime.now(),
                            register_id="REG-1",
                            items=[POSSaleItem(serving_cust.target_sku_id, 1, sku_target.retail_price)],
                            total_amount=sku_target.retail_price,
                        )
                    )
                    self.theft_guard.record_checkout(serving_cust.customer_id)
                    self.theft_guard.clear_customer_track(serving_cust.customer_id)
                    self.metrics.total_sales_dollars += sku_target.retail_price
                else:
                    # Stockout! Lost sale
                    self.metrics.lost_sales_dollars += sku_target.retail_price

            # 5. Restock Decision Strategy Execution
            if self.strategy == StrategyType.IMMEDIATE:
                # Naive 1: Restock immediately after any sale if any shelf is depleted
                any_depleted = any(inv.shelf_deficit > 0 and inv.total_backroom_units > 0 for inv in self.dt.inventory.values())
                if any_depleted and is_clerk_at_counter:
                    # Clerk leaves for backroom for 2 minutes
                    clerk_in_backroom_until_minute = current_min + 2
                    self.metrics.restock_trips_made += 1
                    self.metrics.clerk_counter_abandoned_minutes += 2
                    # Restock top depleted item
                    for inv in self.dt.inventory.values():
                        if inv.shelf_deficit > 0 and inv.total_backroom_units > 0:
                            inv.shelf_units = min(inv.shelf_capacity, inv.shelf_units + 2)
                            break

            elif self.strategy == StrategyType.AI_DISPATCHER:
                # Optimal AI Batcher + Safe Arrival Gate + Theft Inhibit
                if is_clerk_at_counter:
                    dispatch, reason = self.dispatcher.evaluate_dispatch(
                        counter_queue_length=len(counter_queue),
                        estimated_arrival_rate_per_min=arrival_rate,
                    )
                    if dispatch:
                        # 45-second trip (simulated as 1 minute)
                        clerk_in_backroom_until_minute = current_min + 1
                        self.metrics.restock_trips_made += 1
                        self.metrics.clerk_counter_abandoned_minutes += 1
                        self.dt.execute_restock_trip(dispatch)

            elif self.strategy == StrategyType.END_OF_SHIFT:
                # Naive 2: Clerk never leaves register until end of shift
                pass

        return self.metrics
