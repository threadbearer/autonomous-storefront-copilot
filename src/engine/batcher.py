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
        min_item_urgency: float = 0.2,
        weight_resolution_lbs: float = 0.1,
    ):
        self.min_item_urgency = min_item_urgency
        self.weight_resolution_lbs = weight_resolution_lbs
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

        # Skip items that are barely depleted
        candidates = [c for c in scored_candidates if c.urgency_score >= self.min_item_urgency]
        if not candidates:
            return [], 0.0

        quantities = self.solve_bounded_knapsack(candidates)

        basket: List[RestockPickItem] = []
        total_trip_score = 0.0
        # Present the basket in descending urgency order for the clerk HUD
        for candidate, qty in sorted(
            zip(candidates, quantities), key=lambda pair: pair[0].urgency_score, reverse=True
        ):
            if qty <= 0:
                continue
            sku = candidate.sku
            basket.append(
                RestockPickItem(
                    sku_id=sku.sku_id,
                    sku_name=sku.name,
                    quantity=qty,
                    source_location=candidate.backroom_source,
                    target_shelf=str(sku.shelf_location),
                    is_from_partial_case=candidate.from_partial_case,
                    is_cross_dock=False,
                )
            )
            # A SKU contributes urgency in proportion to how much of its deficit the trip covers
            total_trip_score += candidate.urgency_score * qty / candidate.units_to_restock

        return basket, round(total_trip_score, 2)

    def solve_bounded_knapsack(self, candidates: List[ScoredSKU]) -> List[int]:
        """Exact bounded knapsack via dynamic programming.

        Each candidate SKU may contribute 0..units_to_restock units. A unit of SKU i is worth
        urgency_i / units_to_restock_i, so covering a SKU's full shelf deficit earns its full RUI.
        Constraints: total units <= max_units_per_trip and total weight <= max_weight_lbs.
        Weights are discretized to `weight_resolution_lbs` (rounded up, so limits are never exceeded).

        Returns the optimal quantity per candidate, in the same order as `candidates`.
        """
        unit_cap = self.max_units_per_trip
        weight_cap = int(self.max_weight_lbs / self.weight_resolution_lbs + 1e-9)

        def unit_weight(c: ScoredSKU) -> int:
            raw = c.sku.unit_weight_lbs / self.weight_resolution_lbs
            return max(0, int(raw) if abs(raw - round(raw)) < 1e-9 else int(raw) + 1)

        NEG = float("-inf")
        # best[u][w] = max value using exactly-or-fewer u units and w weight across processed items
        best = [[0.0] * (weight_cap + 1) for _ in range(unit_cap + 1)]
        choices: List[List[List[int]]] = []

        for c in candidates:
            w_i = unit_weight(c)
            v_i = c.urgency_score / c.units_to_restock
            max_k = c.units_to_restock
            new_best = [[NEG] * (weight_cap + 1) for _ in range(unit_cap + 1)]
            pick = [[0] * (weight_cap + 1) for _ in range(unit_cap + 1)]
            for u in range(unit_cap + 1):
                for w in range(weight_cap + 1):
                    for k in range(0, min(max_k, u) + 1):
                        if k * w_i > w:
                            break
                        prev = best[u - k][w - k * w_i]
                        if prev == NEG:
                            continue
                        val = prev + k * v_i
                        # Tie-break toward fewer units (lighter carry) for equal value
                        if val > new_best[u][w] + 1e-12:
                            new_best[u][w] = val
                            pick[u][w] = k
            best = new_best
            choices.append(pick)

        # Backtrack from the full-capacity cell (values are monotone in capacity)
        quantities = [0] * len(candidates)
        u, w = unit_cap, weight_cap
        for idx in range(len(candidates) - 1, -1, -1):
            k = choices[idx][u][w]
            quantities[idx] = k
            u -= k
            w -= k * unit_weight(candidates[idx])
        return quantities
