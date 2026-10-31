# CONTEXT.md — Architectural Invariants & System Blueprint

## 1. System Mission & Operational Scope
The **Autonomous Retail Copilot** is a real-time logistics, labor optimization, and loss prevention engine designed for single-clerk high-velocity retail environments (liquor stores, convenience stores, and single-coverage specialty retail like GameStop).

It solves the **asymmetric multi-tasking problem**: balancing front-counter checkout speed, stochastic customer arrival risks, single-facing shelf replenishment, backroom partial-case slotting, and high-value asset security.

---

## 2. Core Architectural Invariants (Non-Negotiable)

1. **The Single-Facing Invariant**:  
   Every SKU on the sales floor has strictly `shelf_facings = 1`. When units sell, visible inventory drops linearly toward 0. The system must never assume safety from duplicate facings.

2. **The 3-Tier Inventory Conservation Invariant**:  
   For every SKU $i$:  
   $$\text{Total Units} = \text{shelf\_units} + (\text{backroom\_full\_cases} \times \text{pack\_size}) + \text{backroom\_loose\_units}$$  
   State transitions (sales, delivery picks, supplier receiving, restock cracking) must strictly preserve this conservation law.

3. **The Restock Inhibit Security Gate**:  
   If any customer exhibits lingering dwell time ($\ge \text{threshold}$, e.g. $30\text{s}-40\text{s}$) in a `is_high_theft` zone or triggers concealment gestures, all restock dispatches are **strictly locked**. The clerk must remain at the counter as a visible deterrent.

4. **The Exit Tripwire Invariant**:  
   Any customer exiting the store without a registered POS transaction within the grace period ($120\text{s}$) after spending $>20\text{s}$ in merchandising aisles triggers an automatic `UNPAID_EXIT` audit flag.

5. **The Cross-Dock Directives Invariant**:  
   When a supplier delivery is received, if an arriving SKU has an existing shelf deficit ($S_i < C_i$), the system must generate a **Cross-Dock Alert** instructing the clerk to stock units directly onto the floor before moving remaining cases into backroom racks.

---

## 3. Module Registry & Component Map

| Path | Purpose | Key Classes / Functions |
| :--- | :--- | :--- |
| `src/models/sku.py` | Physical SKU metadata & facing limits | `SKU`, `Category`, `PhysicalLocation`, `StorageZone` |
| `src/models/inventory.py` | 3-tier inventory hierarchy & PO schemas | `SKUInventory`, `PartialCase`, `PaperPurchaseOrder`, `POLineItem` |
| `src/models/events.py` | Real-time event streams | `POSSaleEvent`, `DeliveryOrderEvent`, `CameraQueueEvent`, `TheftAlert`, `RestockDispatch` |
| `src/engine/digital_twin.py` | State machine governing floor & backroom | `DigitalTwin`, `CrossDockAlert`, `ShrinkRecord` |
| `src/engine/theft_guard.py` | Loss prevention & security gating | `TheftGuard`, `CustomerTrack`, `TheftAlert` |
| `src/engine/batcher.py` | Restock Urgency Index ($RUI$) & Knapsack | `RestockBatcher`, `ScoredSKU` |
| `src/engine/dispatcher.py` | Poisson arrival safety gate & dispatch HUD | `RestockDispatcher` |
| `src/engine/document_parser.py` | Paper invoice OCR / VLM parsing | `PurchaseOrderParser` |
| `src/simulation/store_sim.py` | 8-hour discrete event simulation engine | `StoreSimulator`, `StrategyType`, `SimCustomer` |
| `web/app.js` | 2D Canvas simulator & reactive UI | Canvas renderer, entity state machines, dispatch HUD |
