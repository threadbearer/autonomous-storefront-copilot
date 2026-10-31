# Autonomous Retail Copilot: Single-Clerk Liquor Store Logistics & Restock Optimization Engine

An intelligent retail co-pilot designed to solve the single-employee multi-tasking problem in high-velocity liquor stores. 

It balances **front-counter POS checkout**, **stochastic customer arrivals**, **single-facing shelf depletion**, **loss prevention (anti-theft)**, and **weekly inbound supplier deliveries (paper PO processing)**.

---

## The Core Operational Problem

In a single-clerk store:
- **No Double-Facing**: Shelves only have space for 1 facing per SKU. Fast movers (e.g. Tito's 750ml, Casamigos Blanco, Fireball sleeves, Modelo 12pk) quickly deplete, leading to silent lost sales.
- **The Immediate Restock Trap**: Restocking immediately after every customer purchase causes physical fatigue, transit inefficiency, and leaves the register unattended when customer arrival clusters hit.
- **The Theft Vulnerability**: Shoplifters often wait until the lone clerk steps into the backroom before pocketing high-end bottles or running out the door.
- **Backroom Fragmentation**: Limited storage causes opened partial cases to clutter walkways and slow down picks.
- **Supplier Deliveries**: Weekly distributors (Southern Glazer's, RNDC, Breakthru) drop off 30–100 cases with a physical paper purchase order while customers continue arriving.

---

## System Architecture & Features

### 1. Digital Twin & Inventory Hierarchy (`src/engine/digital_twin.py`)
Tracks stock across 3 physical states:
- `shelf_units`: Facing count on sales floor.
- `backroom_full_cases`: Sealed master cartons.
- `backroom_loose_units`: Opened partial cases with mapped rack/shelf/bin coordinates.

### 2. Restock Urgency Index ($RUI$) & Knapsack Batcher (`src/engine/batcher.py`)
Calculates real-time urgency:
$$RUI_i(t) = \left( 1 - \frac{S_i(t)}{C_i} \right) \times V_i(t) \times M_i \times P_{\text{out}}(i, \Delta t)$$
Assembles optimal 45-second pick batches respecting payload limits (e.g., max 6 bottles or 24 lbs) while rewarding consolidation of open partial boxes.

### 3. Restock Dispatcher & Quiet Window Gate (`src/engine/dispatcher.py`)
Evaluates Poisson customer arrival pacing. Triggers dispatch alerts only when:
1. Register queue is 0.
2. Estimated quiet window $> \text{trip duration}$.
3. Urgency score exceeds batch threshold.
4. No security inhibit lock is active.

### 4. Loss Prevention & Theft Guard (`src/engine/theft_guard.py`)
- **Restock Inhibit Lock**: If a customer lingers in a high-theft zone (e.g., top-shelf scotch or tequila for $>40\text{s}$), all restock trips are immediately locked. Keeps the clerk at the counter as a visible deterrent.
- **Exit Tripwire Audit**: Flags customers who spent meaningful time in aisles and crossed the exit door without a corresponding POS checkout.

### 5. Inbound Paper Delivery & Cross-Docking (`src/engine/document_parser.py`)
- Parses digitized paper purchase orders and invoices.
- **Cross-Dock Directives**: If an arriving SKU is depleted on the floor shelf, instructs the clerk to crack 1 case immediately and stock the shelf before storing the rest, saving an entire backroom trip.

---

## Quick Start

### 1. Run Unit Tests
```bash
python3 -m unittest discover -s tests
```

### 2. Run the 8-Hour Comparative Benchmark
Compares Strategy A (Never Restock), Strategy B (Immediate Restock after every sale), and Strategy C (AI Copilot Dynamic Batching & Safety Gates):
```bash
python3 benchmark.py
```

### 3. Run the Interactive 2D Simulator Web App
Start the local server:
```bash
python3 -m http.server 8080 --directory web
```
Open your browser at: **`http://localhost:8080/`**

Features in the Web App:
- **2D Digital Twin Floor Plan**: Real-time canvas showing aisles, cooler doors, register counter, exit tripwire, and backroom racks with live moving clerk and customer avatars.
- **Smartwatch / Register HUD**: Shows quiet window countdowns, safety scores, and recommended 45-second batch pick lists with exact rack coordinates.
- **Loss Prevention Radar**: Pulsing security aura and instant **Restock Inhibit Lock** when a loiterer dwells $>30\text{s}$ in the top-shelf spirits aisle.
- **Paper Purchase Order & Cross-Dock Hub**: View digitized distributor invoices (Southern Glazer's) and apply automated cross-docking to restock floor shelves directly from inbound pallets.
- **Interactive Scenarios**: Buttons to trigger Customer Rush Hour, Shoplifter Loitering, Weekly Truck Delivery, and Uber Eats order pickups.
