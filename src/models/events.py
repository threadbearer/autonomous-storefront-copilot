"""Event models for POS transactions, delivery apps, camera feeds, and restock actions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from src.models.inventory import PaperPurchaseOrder


class EventType(str, Enum):
    POS_SALE = "pos_sale"
    DELIVERY_ORDER_RECEIVED = "delivery_order_received"
    DELIVERY_ORDER_PICKED = "delivery_order_picked"
    CAMERA_QUEUE_UPDATE = "camera_queue_update"
    CAMERA_AISLE_DWELL = "camera_aisle_dwell"
    EXIT_TRIPWIRE = "exit_tripwire"
    SUPPLIER_DELIVERY_ARRIVED = "supplier_delivery_arrived"
    RESTOCK_TRIP_DISPATCHED = "restock_trip_dispatched"
    RESTOCK_TRIP_COMPLETED = "restock_trip_completed"
    THEFT_INHIBIT_TRIGGERED = "theft_inhibit_triggered"
    SHRINK_ANOMALY_RECORDED = "shrink_anomaly_recorded"


@dataclass
class POSSaleItem:
    sku_id: str
    quantity: int
    unit_price: float


@dataclass
class POSSaleEvent:
    event_id: str
    timestamp: datetime
    register_id: str
    items: List[POSSaleItem]
    total_amount: float


@dataclass
class DeliveryOrderItem:
    sku_id: str
    quantity: int


@dataclass
class DeliveryOrderEvent:
    order_id: str
    platform: str  # e.g., "Uber Eats", "DoorDash", "Drizly"
    timestamp: datetime
    items: List[DeliveryOrderItem]
    is_picked: bool = False


@dataclass
class CameraQueueEvent:
    timestamp: datetime
    queue_length: int  # Number of people waiting at the front counter
    cashier_present: bool = True


@dataclass
class CameraAisleDwellEvent:
    customer_id: str
    aisle_zone: str
    dwell_duration_seconds: float
    is_high_theft_zone: bool
    suspicious_motion_flag: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExitTripwireEvent:
    customer_id: str
    timestamp: datetime
    has_recent_pos_checkout: bool  # False means potential grab-and-dash!
    aisle_origin: Optional[str] = None


@dataclass
class RestockPickItem:
    sku_id: str
    sku_name: str
    quantity: int
    source_location: str       # e.g. "Rack A-2, Bin 1"
    target_shelf: str          # e.g. "Aisle 1, Slot 4"
    is_from_partial_case: bool
    is_cross_dock: bool = False # If grabbed directly from fresh supplier delivery pallet


@dataclass
class RestockDispatch:
    dispatch_id: str
    timestamp: datetime
    items: List[RestockPickItem]
    estimated_trip_duration_seconds: int
    quiet_window_estimate_seconds: int
    restock_urgency_score: float
    safety_score: float
    rationale: str

    @property
    def total_bottles(self) -> int:
        return sum(item.quantity for item in self.items)
