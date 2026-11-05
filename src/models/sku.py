"""SKU models and retail physical constraints for the single-operator retail logistics engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Category(str, Enum):
    BEVERAGES = "beverages"
    ELECTRONICS = "electronics"
    ACCESSORIES = "accessories"
    SNACKS_GRAB_AND_GO = "snacks_grab_and_go"
    PREMIUM_GOODS = "premium_goods"
    HEALTH_BEAUTY = "health_beauty"
    GENERAL_MERCHANDISE = "general_merchandise"

    # Domain aliases for backward compatibility
    VODKA = "beverages"
    TEQUILA = "beverages"
    WHISKEY = "beverages"
    COGNAC = "beverages"
    BEER = "beverages"
    WINE = "beverages"
    SHOOTERS = "snacks_grab_and_go"
    SELTZERS = "beverages"


class StorageZone(str, Enum):
    FRONT_SHELF = "front_shelf"
    COLD_VAULT = "cold_vault"
    REGISTER_COUNTER = "register_counter"
    BACKROOM_RACK = "backroom_rack"
    BACKROOM_FLOOR = "backroom_floor"
    SECURE_LOCKUP = "secure_lockup"

    # Backward-compatible alias
    COOLER_DOOR = "cold_vault"


@dataclass(frozen=True)
class PhysicalLocation:
    """Represents precise physical coordinates within the store or backroom."""
    zone: StorageZone
    aisle_or_section: str  # e.g., "Aisle 1", "Zone B - Electronics", "Cold Vault Door 2", "Backroom Rack A"
    shelf_level: int       # 1 = bottom shelf, 4 = top shelf (Golden zone = 2-3)
    bin_or_slot: str       # e.g., "Slot 4", "Pallet B", "Bin 2"

    def __init__(
        self,
        zone: StorageZone,
        aisle_or_section: Optional[str] = None,
        shelf_level: int = 1,
        bin_or_slot: str = "Slot 1",
        aisle_or_cooler: Optional[str] = None,
    ):
        object.__setattr__(self, "zone", zone)
        section = aisle_or_section if aisle_or_section is not None else (aisle_or_cooler or "Aisle 1")
        object.__setattr__(self, "aisle_or_section", section)
        object.__setattr__(self, "shelf_level", shelf_level)
        object.__setattr__(self, "bin_or_slot", bin_or_slot)

    @property
    def aisle_or_cooler(self) -> str:
        """Backward-compatible accessor for section location."""
        return self.aisle_or_section

    def __str__(self) -> str:
        return f"[{self.zone.value.upper()}] {self.aisle_or_section} - Level {self.shelf_level} ({self.bin_or_slot})"


@dataclass
class SKU:
    """Represents a product SKU with sales velocity, physical dimensions, and security attributes."""
    sku_id: str
    upc: str
    name: str
    category: Category
    
    # Shelf & Packaging constraints
    shelf_capacity: int           # Maximum units facing depth (store has NO double-facing)
    shelf_facings: int = 1        # Strictly 1 in this retail environment
    pack_size: int = 12           # Units per master case from supplier (e.g., 12/pack, 24/pack)
    unit_weight_lbs: float = 1.5  # Weight per retail unit
    case_weight_lbs: float = 18.0 # Total weight per sealed case
    
    # Financial metrics
    wholesale_unit_cost: float = 10.00
    retail_price: float = 19.99
    
    # Loss Prevention & Security
    is_high_theft: bool = False
    theft_dwell_threshold_seconds: int = 40  # Loitering past this raises theft flag
    
    # Physical Storage Coordinates
    shelf_location: PhysicalLocation = field(
        default_factory=lambda: PhysicalLocation(StorageZone.FRONT_SHELF, "Aisle 1", 3, "Slot 1")
    )
    backroom_location: PhysicalLocation = field(
        default_factory=lambda: PhysicalLocation(StorageZone.BACKROOM_RACK, "Rack A", 2, "Bin 1")
    )
    
    # Target restocking trigger: e.g. when shelf falls to <= 40% of capacity
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
