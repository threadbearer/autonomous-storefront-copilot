"""Inventory models managing the 3-tier hierarchy: front shelf, backroom full cases, and partial loose units."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class PartialCase:
    """Tracks an opened box in the backroom so loose bottles aren't lost or duplicated."""
    sku_id: str
    remaining_units: int
    max_case_capacity: int
    rack_coordinate: str
    opened_at: datetime = field(default_factory=datetime.now)

    @property
    def is_empty(self) -> bool:
        return self.remaining_units <= 0

    @property
    def fill_ratio(self) -> float:
        if self.max_case_capacity == 0:
            return 0.0
        return self.remaining_units / self.max_case_capacity


@dataclass
class SKUInventory:
    """Tracks real-time stock across the 3 physical states in the liquor store."""
    sku_id: str
    shelf_units: int
    shelf_capacity: int
    backroom_full_cases: int
    backroom_loose_units: int
    pack_size: int
    reserved_delivery_units: int = 0  # Units locked for Uber Eats / DoorDash picks

    @property
    def total_backroom_units(self) -> int:
        return (self.backroom_full_cases * self.pack_size) + self.backroom_loose_units

    @property
    def total_store_units(self) -> int:
        return self.shelf_units + self.total_backroom_units

    @property
    def available_shelf_units(self) -> int:
        """Units on shelf that are not currently reserved for a delivery order."""
        return max(0, self.shelf_units - self.reserved_delivery_units)

    @property
    def shelf_fill_ratio(self) -> float:
        if self.shelf_capacity == 0:
            return 0.0
        return self.shelf_units / self.shelf_capacity

    @property
    def shelf_deficit(self) -> int:
        """How many units are missing from the front shelf facing."""
        return max(0, self.shelf_capacity - self.shelf_units)

    @property
    def is_out_of_stock_on_shelf(self) -> bool:
        return self.available_shelf_units == 0


@dataclass
class POLineItem:
    """A line item on a supplier delivery purchase order / invoice."""
    sku_id: str
    upc: str
    description: str
    pack_size: int
    cases_invoiced: int
    bottle_cost: float
    case_cost: float
    cases_received: Optional[int] = None  # None until verified by clerk

    @property
    def total_units(self) -> int:
        return (self.cases_received if self.cases_received is not None else self.cases_invoiced) * self.pack_size


@dataclass
class PaperPurchaseOrder:
    """Structured representation of a physical paper invoice from a liquor/beer distributor."""
    distributor_name: str  # e.g., "Southern Glazer's Wine & Spirits", "RNDC", "Breakthru"
    invoice_number: str
    invoice_date: str
    line_items: List[POLineItem] = field(default_factory=list)
    raw_ocr_confidence: float = 0.95
    verified_by_clerk: bool = False

    @property
    def total_cases(self) -> int:
        return sum(item.cases_invoiced for item in self.line_items)

    @property
    def total_invoice_amount(self) -> float:
        return sum(item.case_cost * item.cases_invoiced for item in self.line_items)
