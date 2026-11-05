"""Restock batcher: computes Restock Urgency Index (RUI) and optimizes batch trips using knapsack constraints."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from src.engine.digital_twin import DigitalTwin
from src.models.events import RestockPickItem
from src.models.inventory import SKUInventory
from src.models.sku import SKU


@dataclass
class ScoredSKU:
    sku: SKU
    inventory: SKUInventory
    urgency_score: float
    units_to_restock: int
    from_partial_case: bool
    backroom_source: str


class RestockBatcher:
    """Calculates restock urgency and assembles optimal carry baskets to minimize transit trips."""

    def __init__(
        self,
        max_units_per_trip: Optional[int] = None,
        max_weight_lbs: float = 24.0,
        partial_case_clear_bonus: float = 1.5,
        max_bottles_per_trip: Optional[int] = None,
    ):
        if max_units_per_trip is not None:
            self.max_units_per_trip = max_units_per_trip
        elif max_bottles_per_trip is not None:
            self.max_units_per_trip = max_bottles_per_trip
        else:
            self.max_units_per_trip = 6

        # Alias for backward compatibility
        self.max_bottles_per_trip = self.max_units_per_trip
        self.max_weight_lbs = max_weight_lbs
        self.partial_case_clear_bonus = partial_case_clear_bonus

    def calculate_rui(
        self,
        sku: SKU,
        inv: SKUInventory,
        velocity_units_per_hour: float,
    ) -> float:
        """Calculates Restock Urgency Index (RUI).
        High score = single facing nearly empty, fast mover, good profit margin.
        """
        if inv.shelf_capacity == 0:
            return 0.0

        # Facing deficit fraction: 1.0 when completely empty, 0.0 when full
        deficit_ratio = (inv.shelf_capacity - inv.shelf_units) / inv.shelf_capacity
        if deficit_ratio <= 0.0:
            return 0.0

        # Baseline velocity (at least 0.5 units/hr for active items to avoid 0)
        eff_velocity = max(0.5, velocity_units_per_hour)

        # Margin multiplier (normalized around $5.00 margin)
        margin_factor = max(1.0, sku.margin / 5.0)

        # Probability of stockout within next 30 mins
        projected_demand_30m = eff_velocity * 0.5
        stockout_risk = 1.0 if inv.available_shelf_units <= projected_demand_30m else 0.5

        rui = (deficit_ratio ** 1.5) * eff_velocity * margin_factor * stockout_risk
        return round(rui, 3)

    def assemble_optimal_trip(
        self,
        digital_twin: DigitalTwin,
    ) -> Tuple[List[RestockPickItem], float]:
        """Solves a bounded knapsack problem to find the highest-value batch of items to fetch."""
        scored_candidates: List[ScoredSKU] = []

        for sku_id, sku in digital_twin.catalog.items():
            inv = digital_twin.inventory.get(sku_id)
            if not inv:
                continue

            # If shelf has a deficit and we actually have units in the back
            if inv.shelf_deficit > 0 and inv.total_backroom_units > 0:
                vel = digital_twin.get_rolling_velocity(sku_id)
                base_rui = self.calculate_rui(sku, inv, vel)

                # Prioritize partial loose cases
                partials = digital_twin.partial_cases.get(sku_id, [])
                has_partials = len(partials) > 0 and inv.backroom_loose_units > 0
                
                # Bonus if this trip can clean up an already-opened box
                final_score = base_rui * (self.partial_case_clear_bonus if has_partials else 1.0)

                # Cap restock quantity by what can physically fit on the front shelf and what is in backroom
                units_to_bring = min(inv.shelf_deficit, inv.total_backroom_units)

                source_loc = str(sku.backroom_location)
                if has_partials:
                    source_loc += f" [Open Partial: {inv.backroom_loose_units} loose]"

                scored_candidates.append(
                    ScoredSKU(
                        sku=sku,
                        inventory=inv,
                        urgency_score=final_score,
                        units_to_restock=units_to_bring,
                        from_partial_case=has_partials,
                        backroom_source=source_loc,
                    )
                )

        # Sort descending by urgency score
        scored_candidates.sort(key=lambda x: x.urgency_score, reverse=True)

        # Pack into trip basket respecting payload limits
        basket: List[RestockPickItem] = []
        current_bottles = 0
        current_weight = 0.0
        total_trip_score = 0.0

        for candidate in scored_candidates:
            if candidate.urgency_score < 0.2:
                continue  # Skip items that are barely depleted

            sku = candidate.sku
            units_wanted = candidate.units_to_restock

            # Fit as many units of this SKU as capacity allows
            for _ in range(units_wanted):
                if (current_bottles + 1 <= self.max_bottles_per_trip) and (
                    current_weight + sku.unit_weight_lbs <= self.max_weight_lbs
                ):
                    current_bottles += 1
                    current_weight += sku.unit_weight_lbs
                else:
                    break

            # Calculate how many we actually packed for this SKU
            packed_for_sku = current_bottles - sum(item.quantity for item in basket)
            if packed_for_sku > 0:
                basket.append(
                    RestockPickItem(
                        sku_id=sku.sku_id,
                        sku_name=sku.name,
                        quantity=packed_for_sku,
                        source_location=candidate.backroom_source,
                        target_shelf=str(sku.shelf_location),
                        is_from_partial_case=candidate.from_partial_case,
                        is_cross_dock=False,
                    )
                )
                total_trip_score += candidate.urgency_score

            if current_bottles >= self.max_bottles_per_trip:
                break

        return basket, round(total_trip_score, 2)
