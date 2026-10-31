# AGENTS.md — Agent Constitution & Operational Invariants

## 1. Prime Directive
Every agent or developer working in this repository must maintain the structural integrity, physical reality, and loss prevention guarantees of the retail logistics copilot.

---

## 2. Coding & Architectural Standards

1. **Deterministic Operations Research**:
   - Dispatch decisions, knapsack packaging, and Poisson arrival probabilities must be mathematically sound, deterministic, and unit-tested.
   - No arbitrary magic numbers. Thresholds must be exposed as configurable parameters in class constructors.

2. **Strict Inventory Conservation**:
   - Any code modifying inventory must update `shelf_units`, `backroom_full_cases`, or `backroom_loose_units` atomically.
   - Partial cases must always track remaining loose units so bottles are never lost or orphaned in the backroom.

3. **Loss Prevention Gating Integrity**:
   - The Restock Dispatcher must NEVER bypass the `TheftGuard.evaluate_restock_inhibit()` check.
   - Security always supersedes restocking: an unattended counter with a loitering suspect is an unacceptable failure mode.

4. **Testing Rigor**:
   - All changes must pass `python3 -m unittest discover -s tests`.
   - Any new feature (e.g., a new event type or dispatch rule) must include corresponding unit tests.

5. **The Crucible Propose-Only Policy**:
   - The Crucible method analyzes code changes and suggests rules, but NEVER writes directly to `AGENTS.md` or `CONTEXT.md`.
   - New rules must be curated and approved by a human engineer in `enrichment_suggestions.md` / `enrichment_suggestions.json`.
