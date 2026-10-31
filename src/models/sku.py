"""SKU models and retail physical constraints for the liquor store logistics system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Category(str, Enum):
    VODKA = "vodka"
    TEQUILA = "tequila"
    WHISKEY = "whiskey"
    COGNAC = "cognac"
    BEER = "beer"
    WINE = "wine"
    SHOOTERS = "shooters"
    SELTZERS = "seltzers"


class StorageZone(str, Enum):
    FRONT_SHELF = "front_shelf"
    COOLER_DOOR = "cooler_door"
    REGISTER_COUNTER = "register_counter"
    BACKROOM_RACK = "backroom_rack"
    BACKROOM_FLOOR = "backroom_floor"


@dataclass(frozen=True)
class PhysicalLocation:
    """Represents precise physical coordinates within the store or backroom."""
    zone: StorageZone
    aisle_or_cooler: str  # e.g., "Aisle 1", "Cooler Door 3", "Backroom Rack A"
    shelf_level: int       # 1 = bottom shelf, 4 = top shelf (Golden zone = 2-3)
    bin_or_slot: str       # e.g., "Slot 4", "Pallet B"

    def __str__(self) -> str:
        return f"[{self.zone.value.upper()}] {self.aisle_or_cooler} - Level {self.shelf_level} ({self.bin_or_slot})"


@dataclass
class SKU:
    """Represents a product SKU with sales velocity, physical dimensions, and security attributes."""
    sku_id: str
    upc: str
    name: str
    category: Category
    
    # Shelf & Packaging constraints
    shelf_capacity: int           # Maximum bottles/units facing depth (store has NO double-facing)
    shelf_facings: int = 1        # Strictly 1 in this retail environment
    pack_size: int = 12           # Units per master case from supplier (e.g., 12/750ml, 24/12oz)
    unit_weight_lbs: float = 3.0  # Weight per retail unit
    case_weight_lbs: float = 36.0 # Total weight per sealed case
    
    # Financial metrics
    wholesale_unit_cost: float = 15.00
    retail_price: float = 24.99
    
    # Loss Prevention & Security
    is_high_theft: bool = False
    theft_dwell_threshold_seconds: int = 45  # Loitering past this raises theft flag
    
    # Physical Storage Coordinates
    shelf_location: PhysicalLocation = field(
        default_factory=lambda: PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 3, "Slot 1")
    )
    backroom_location: PhysicalLocation = field(
        default_factory=lambda: PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 2, "Bin 1")
    )
    
    # Target restocking trigger: e.g. when shelf falls to <= 35% of capacity
    restock_trigger_ratio: float = 0.40

    @property
    def margin(self) -> float:
        """Dollar gross profit margin."""
        return self.retail_price - self.wholesale_unit_cost

    @property
    def margin_percentage(self) -> float:
        """Percentage gross profit margin."""
        if self.retail_price == 0:
            return 0.0
        return (self.margin / self.retail_price) * 100.0
