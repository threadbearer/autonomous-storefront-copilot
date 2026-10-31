"""Theft prevention engine: monitors aisle dwell times, exit tripwires, and enforces restock inhibit locks."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


@dataclass
class CustomerTrack:
    customer_id: str
    current_zone: str
    is_high_theft_zone: bool
    entry_time: datetime
    dwell_seconds: float = 0.0
    suspicious_motion_flag: bool = False
    has_pos_checkout: bool = False


@dataclass
class TheftAlert:
    alert_type: str  # "RESTOCK_INHIBIT", "SUSPICIOUS_DWELL", "UNPAID_EXIT"
    severity: str    # "MEDIUM", "HIGH", "CRITICAL"
    customer_id: str
    zone: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


class TheftGuard:
    """Monitors live store security feeds and guards against opportunistic shoplifting during solo shifts."""

    def __init__(
        self,
        high_theft_dwell_limit_seconds: float = 45.0,
        standard_dwell_limit_seconds: float = 180.0,
        checkout_grace_period_seconds: float = 120.0,
    ):
        self.high_theft_dwell_limit_seconds = high_theft_dwell_limit_seconds
        self.standard_dwell_limit_seconds = standard_dwell_limit_seconds
        self.checkout_grace_period_seconds = checkout_grace_period_seconds
        
        self.active_tracks: Dict[str, CustomerTrack] = {}
        self.recent_checkouts: List[Tuple[str, datetime]] = []  # (customer_id_or_tag, timestamp)
        self.alerts: List[TheftAlert] = []

    def update_customer_dwell(
        self,
        customer_id: str,
        zone: str,
        is_high_theft_zone: bool,
        dwell_seconds: float,
        suspicious_motion: bool = False,
    ) -> Optional[TheftAlert]:
        """Updates dwell telemetry from computer vision / CCTV tracker."""
        track = self.active_tracks.get(customer_id)
        now = datetime.now()

        if not track:
            track = CustomerTrack(
                customer_id=customer_id,
                current_zone=zone,
                is_high_theft_zone=is_high_theft_zone,
                entry_time=now - timedelta(seconds=dwell_seconds),
                dwell_seconds=dwell_seconds,
                suspicious_motion_flag=suspicious_motion,
            )
            self.active_tracks[customer_id] = track
        else:
            track.current_zone = zone
            track.is_high_theft_zone = is_high_theft_zone
            track.dwell_seconds = dwell_seconds
            track.suspicious_motion_flag = suspicious_motion

        # Evaluate loitering threshold
        threshold = (
            self.high_theft_dwell_limit_seconds
            if is_high_theft_zone
            else self.standard_dwell_limit_seconds
        )

        if dwell_seconds >= threshold or suspicious_motion:
            alert = TheftAlert(
                alert_type="SUSPICIOUS_DWELL" if not suspicious_motion else "CONCEALMENT_SUSPECTED",
                severity="HIGH" if is_high_theft_zone else "MEDIUM",
                customer_id=customer_id,
                zone=zone,
                message=(
                    f"Customer {customer_id} lingering {dwell_seconds:.0f}s in {zone} "
                    f"(Threshold: {threshold:.0f}s). Eyes on sales floor!"
                ),
                timestamp=now,
            )
            self.alerts.append(alert)
            return alert

        return None

    def record_checkout(self, customer_id: Optional[str] = None) -> None:
        """Registers a completed transaction at the counter, clearing recent unbilled flags."""
        now = datetime.now()
        cid = customer_id or f"cashier_scan_{int(now.timestamp())}"
        self.recent_checkouts.append((cid, now))
        if customer_id and customer_id in self.active_tracks:
            self.active_tracks[customer_id].has_pos_checkout = True

    def clear_customer_track(self, customer_id: str) -> None:
        """Removes customer from active tracking when they leave aisles or complete checkout."""
        self.active_tracks.pop(customer_id, None)

    def evaluate_restock_inhibit(self) -> Tuple[bool, Optional[str]]:
        """Determines if a clerk is safe to leave the register.
        Returns:
            (is_inhibited: bool, reason: str)
        """
        for cid, track in self.active_tracks.items():
            threshold = (
                self.high_theft_dwell_limit_seconds
                if track.is_high_theft_zone
                else self.standard_dwell_limit_seconds
            )
            # If someone is in a high-theft zone approaching or exceeding threshold
            if track.is_high_theft_zone and track.dwell_seconds >= (threshold * 0.75):
                return (
                    True,
                    f"INHIBIT: Customer {cid} in high-theft zone ({track.current_zone}) "
                    f"for {track.dwell_seconds:.0f}s. Maintain presence at register.",
                )

            # If suspicious gestures detected
            if track.suspicious_motion_flag:
                return (
                    True,
                    f"INHIBIT: Suspicious concealment motion detected on Customer {cid} in {track.current_zone}.",
                )

        return (False, None)

    def check_exit_tripwire(self, customer_id: str) -> Optional[TheftAlert]:
        """Fires when an optical tripwire or camera detects a customer passing through the exit door."""
        now = datetime.now()
        track = self.active_tracks.pop(customer_id, None)

        if not track:
            return None

        # Check if customer completed a checkout recently
        if track.has_pos_checkout:
            return None

        cutoff = now - timedelta(seconds=self.checkout_grace_period_seconds)
        any_recent_checkout = any(ts >= cutoff for _, ts in self.recent_checkouts)

        # If they spent meaningful time in aisles and no checkout recorded
        if track.dwell_seconds > 20.0 and not any_recent_checkout:
            alert = TheftAlert(
                alert_type="UNPAID_EXIT",
                severity="CRITICAL",
                customer_id=customer_id,
                zone=track.current_zone,
                message=(
                    f"SECURITY ALERT: Customer {customer_id} exited from {track.current_zone} "
                    f"without a registered POS checkout in the last {self.checkout_grace_period_seconds:.0f}s."
                ),
                timestamp=now,
            )
            self.alerts.append(alert)
            return alert

        return None
