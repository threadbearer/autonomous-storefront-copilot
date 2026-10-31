"""Digital twin maintaining real-time physical store state: shelf facings, backroom cases, loose bottles, and deliveries."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.models.events import DeliveryOrderEvent, POSSaleEvent, RestockDispatch, RestockPickItem
from src.models.inventory import PaperPurchaseOrder, PartialCase, POLineItem, SKUInventory
from src.models.sku import SKU, StorageZone


@dataclass
class CrossDockAlert:
    """Alert triggered during supplier receiving when an inbound SKU should bypass backroom racks."""
    sku_id: str
    sku_name: str
    suggested_cross_dock_units: int
    target_shelf_location: str
    rationale: str


@dataclass
class ShrinkRecord:
    sku_id: str
    timestamp: datetime
    quantity: int
    estimated_retail_loss: float
    notes: str


class DigitalTwin:
    """Maintains the canonical state of inventory across front-shelf facings and backroom storage."""

    def __init__(self):
        self.catalog: Dict[str, SKU] = {}
        self.inventory: Dict[str, SKUInventory] = {}
        self.partial_cases: Dict[str, List[PartialCase]] = {}
        self.sales_history: List[Tuple[datetime, str, int]] = []  # (timestamp, sku_id, qty)
        self.active_delivery_orders: Dict[str, DeliveryOrderEvent] = {}
        self.shrink_ledger: List[ShrinkRecord] = []

    def register_sku(
        self,
        sku: SKU,
        initial_shelf: int,
        initial_cases: int = 0,
        initial_loose: int = 0,
    ) -> None:
        """Registers a SKU and sets its initial physical state."""
        self.catalog[sku.sku_id] = sku
        self.inventory[sku.sku_id] = SKUInventory(
            sku_id=sku.sku_id,
            shelf_units=min(initial_shelf, sku.shelf_capacity),
            shelf_capacity=sku.shelf_capacity,
            backroom_full_cases=initial_cases,
            backroom_loose_units=initial_loose,
            pack_size=sku.pack_size,
        )
        self.partial_cases[sku.sku_id] = []
        if initial_loose > 0:
            self.partial_cases[sku.sku_id].append(
                PartialCase(
                    sku_id=sku.sku_id,
                    remaining_units=initial_loose,
                    max_case_capacity=sku.pack_size,
                    rack_coordinate=str(sku.backroom_location),
                )
            )

    def process_pos_sale(self, event: POSSaleEvent) -> List[str]:
        """Deducts units directly from front shelf facings. Returns SKUs that hit critical low/out-of-stock."""
        critical_alerts: List[str] = []
        now = event.timestamp

        for item in event.items:
            sku = self.catalog.get(item.sku_id)
            inv = self.inventory.get(item.sku_id)
            if not sku or not inv:
                continue

            # Record sales history for velocity forecasting
            self.sales_history.append((now, item.sku_id, item.quantity))

            # Deduct from front shelf
            inv.shelf_units = max(0, inv.shelf_units - item.quantity)

            # Check if shelf is critically low
            if inv.shelf_fill_ratio <= sku.restock_trigger_ratio:
                critical_alerts.append(
                    f"[SHELF LOW] {sku.name}: {inv.shelf_units}/{inv.shelf_capacity} remaining (Deficit: {inv.shelf_deficit})"
                )

        return critical_alerts

    def process_delivery_order(self, order: DeliveryOrderEvent) -> None:
        """Locks inventory for an incoming delivery order (e.g., Uber Eats, DoorDash)."""
        self.active_delivery_orders[order.order_id] = order
        for item in order.items:
            inv = self.inventory.get(item.sku_id)
            if inv:
                inv.reserved_delivery_units += item.quantity

    def complete_delivery_order(self, order_id: str) -> None:
        """Finalizes a delivery order when the clerk packages and hands it to the courier."""
        order = self.active_delivery_orders.pop(order_id, None)
        if not order:
            return

        for item in order.items:
            inv = self.inventory.get(item.sku_id)
            if inv:
                # Deduct units from shelf and clear reservation
                inv.shelf_units = max(0, inv.shelf_units - item.quantity)
                inv.reserved_delivery_units = max(0, inv.reserved_delivery_units - item.quantity)
                self.sales_history.append((order.timestamp, item.sku_id, item.quantity))

    def receive_purchase_order(self, po: PaperPurchaseOrder) -> List[CrossDockAlert]:
        """Processes an inbound supplier delivery (weekly truck drop-off).
        Identifies cross-docking opportunities so goods needed on the floor bypass backroom storage racks."""
        cross_dock_alerts: List[CrossDockAlert] = []

        for line in po.line_items:
            sku = self.catalog.get(line.sku_id)
            inv = self.inventory.get(line.sku_id)
            cases_received = line.cases_received if line.cases_received is not None else line.cases_invoiced

            if not sku or not inv:
                continue

            # Check if shelf is empty or critically low
            shelf_deficit = inv.shelf_deficit
            if shelf_deficit > 0:
                # We can crack 1 case directly on arrival and stock the floor immediately!
                cross_dock_units = min(shelf_deficit, line.pack_size)
                remaining_in_first_case = line.pack_size - cross_dock_units
                
                # The rest of the cases go into backroom full cases
                full_cases_to_backroom = cases_received - 1
                inv.backroom_full_cases += max(0, full_cases_to_backroom)
                
                # Update shelf directly
                inv.shelf_units += cross_dock_units
                
                # If there are leftovers from the cracked case, track as partial case
                if remaining_in_first_case > 0:
                    inv.backroom_loose_units += remaining_in_first_case
                    self.partial_cases[sku.sku_id].append(
                        PartialCase(
                            sku_id=sku.sku_id,
                            remaining_units=remaining_in_first_case,
                            max_case_capacity=sku.pack_size,
                            rack_coordinate=str(sku.backroom_location),
                        )
                    )

                cross_dock_alerts.append(
                    CrossDockAlert(
                        sku_id=sku.sku_id,
                        sku_name=sku.name,
                        suggested_cross_dock_units=cross_dock_units,
                        target_shelf_location=str(sku.shelf_location),
                        rationale=(
                            f"Shelf was at {inv.shelf_units - cross_dock_units}/{sku.shelf_capacity}. "
                            f"Cross-docked {cross_dock_units} units straight from delivery pallet to shelf."
                        ),
                    )
                )
            else:
                # Shelf is already full; all cases go directly to backroom
                inv.backroom_full_cases += cases_received

        return cross_dock_alerts

    def execute_restock_trip(self, dispatch: RestockDispatch) -> None:
        """Executes a restocked batch trip. Depletes backroom loose units / cracks cases, fills shelf."""
        for item in dispatch.items:
            inv = self.inventory.get(item.sku_id)
            sku = self.catalog.get(item.sku_id)
            if not inv or not sku:
                continue

            needed = item.quantity

            # 1. First, satisfy from existing partial loose cases
            if inv.backroom_loose_units >= needed:
                inv.backroom_loose_units -= needed
                self._deduct_from_partial_cases(item.sku_id, needed)
            else:
                # Take whatever loose units exist
                from_loose = inv.backroom_loose_units
                remaining_needed = needed - from_loose
                inv.backroom_loose_units = 0
                self._clear_partial_cases(item.sku_id)

                # 2. Crack open full cases as needed
                while remaining_needed > 0 and inv.backroom_full_cases > 0:
                    inv.backroom_full_cases -= 1
                    case_units = sku.pack_size
                    taken = min(remaining_needed, case_units)
                    remaining_needed -= taken
                    leftover = case_units - taken

                    if leftover > 0:
                        inv.backroom_loose_units += leftover
                        self.partial_cases[sku.sku_id].append(
                            PartialCase(
                                sku_id=sku.sku_id,
                                remaining_units=leftover,
                                max_case_capacity=sku.pack_size,
                                rack_coordinate=str(sku.backroom_location),
                            )
                        )

            # Replenish shelf
            inv.shelf_units = min(sku.shelf_capacity, inv.shelf_units + needed)

    def record_shrink_anomaly(self, sku_id: str, missing_qty: int, notes: str) -> None:
        """Records an unrecorded inventory loss (shoplifting / breakage)."""
        sku = self.catalog.get(sku_id)
        inv = self.inventory.get(sku_id)
        if not sku or not inv:
            return

        inv.shelf_units = max(0, inv.shelf_units - missing_qty)
        loss_val = missing_qty * sku.retail_price
        self.shrink_ledger.append(
            ShrinkRecord(
                sku_id=sku_id,
                timestamp=datetime.now(),
                quantity=missing_qty,
                estimated_retail_loss=loss_val,
                notes=notes,
            )
        )

    def get_rolling_velocity(self, sku_id: str, window_minutes: int = 60) -> float:
        """Returns units sold per hour over the recent rolling window."""
        now = datetime.now()
        cutoff = now - timedelta(minutes=window_minutes)
        sales_in_window = [
            qty for ts, s_id, qty in self.sales_history if s_id == sku_id and ts >= cutoff
        ]
        total_sold = sum(sales_in_window)
        # Normalize to units per hour
        return (total_sold / window_minutes) * 60.0 if window_minutes > 0 else 0.0

    def _deduct_from_partial_cases(self, sku_id: str, qty: int) -> None:
        partials = self.partial_cases.get(sku_id, [])
        remaining_to_deduct = qty
        for p in partials:
            if p.remaining_units >= remaining_to_deduct:
                p.remaining_units -= remaining_to_deduct
                remaining_to_deduct = 0
                break
            else:
                remaining_to_deduct -= p.remaining_units
                p.remaining_units = 0

        # Remove emptied partial cases
        self.partial_cases[sku_id] = [p for p in partials if not p.is_empty]

    def _clear_partial_cases(self, sku_id: str) -> None:
        self.partial_cases[sku_id] = []
