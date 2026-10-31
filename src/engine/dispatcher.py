"""Dispatcher engine: evaluates safety gates, quiet windows, and triggers batch restock dispatches."""

from datetime import datetime
import uuid
from typing import Optional, Tuple
from src.engine.batcher import RestockBatcher
from src.engine.digital_twin import DigitalTwin
from src.engine.theft_guard import TheftGuard
from src.models.events import RestockDispatch


class RestockDispatcher:
    """Orchestrates when a single clerk should be notified to leave the register to restock."""

    def __init__(
        self,
        digital_twin: DigitalTwin,
        theft_guard: TheftGuard,
        batcher: Optional[RestockBatcher] = None,
        min_urgency_threshold: float = 1.0,
        estimated_trip_seconds: int = 45,
    ):
        self.digital_twin = digital_twin
        self.theft_guard = theft_guard
        self.batcher = batcher or RestockBatcher()
        self.min_urgency_threshold = min_urgency_threshold
        self.estimated_trip_seconds = estimated_trip_seconds

    def evaluate_dispatch(
        self,
        counter_queue_length: int = 0,
        estimated_arrival_rate_per_min: float = 0.2,
    ) -> Tuple[Optional[RestockDispatch], Optional[str]]:
        """Evaluates whether to trigger a restock trip.
        Returns:
            (dispatch: Optional[RestockDispatch], status_reason: Optional[str])
        """
        # 1. HARD GATE: Register Queue
        if counter_queue_length > 0:
            return None, f"Counter busy ({counter_queue_length} customers in line). Restock deferred."

        # 2. HARD GATE: Theft Guard & Security Inhibit
        is_inhibited, inhibit_reason = self.theft_guard.evaluate_restock_inhibit()
        if is_inhibited:
            return None, inhibit_reason

        # 3. Assemble candidate batch basket
        basket, trip_score = self.batcher.assemble_optimal_trip(self.digital_twin)
        if not basket or trip_score < self.min_urgency_threshold:
            return None, "Shelf stocks healthy. No high-urgency batch needed."

        # 4. SAFETY GATE: Restock Window Safety Score (RWSS)
        # Poisson probability of NO arrivals during the trip: P(k=0) = exp(-lambda * t)
        trip_minutes = self.estimated_trip_seconds / 60.0
        expected_arrivals = estimated_arrival_rate_per_min * trip_minutes
        
        # Approximate quiet window in seconds
        quiet_window_sec = int((1.0 / max(0.05, estimated_arrival_rate_per_min)) * 60)
        safety_score = max(0.1, min(1.0, 1.0 - expected_arrivals))

        if safety_score < 0.40:
            return None, f"Store arrival pace too rapid (Safety score: {safety_score:.2f}). Waiting for quieter window."

        # All gates passed: Trigger Dispatch!
        dispatch_id = f"DSP-{uuid.uuid4().hex[:6].upper()}"
        dispatch = RestockDispatch(
            dispatch_id=dispatch_id,
            timestamp=datetime.now(),
            items=basket,
            estimated_trip_duration_seconds=self.estimated_trip_seconds,
            quiet_window_estimate_seconds=quiet_window_sec,
            restock_urgency_score=trip_score,
            safety_score=round(safety_score, 2),
            rationale=(
                f"Restock window open (~{quiet_window_sec}s quiet). "
                f"Urgency score {trip_score} exceeds threshold {self.min_urgency_threshold}."
            ),
        )
        return dispatch, "Dispatch triggered successfully."
