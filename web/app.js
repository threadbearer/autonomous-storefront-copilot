/**
 * Autonomous Retail Copilot - 2D Store & Logistics Simulator
 * Client-side digital twin mirroring the Python backend models.
 */

// --- 1. Product Catalog & Physical Facings ---
const CATALOG = [
  {
    id: "SKU-ENERGY-16OZ",
    name: "Vitality Energy Drink 16oz",
    category: "Beverages",
    capacity: 5,
    packSize: 12,
    retailPrice: 3.49,
    unitCost: 1.80,
    isHighTheft: false,
    shelfLoc: "Aisle 1 - Facing 1",
    rackLoc: "Backroom Rack A-2",
    shelfCoords: { x: 170, y: 270 },
    backroomCoords: { x: 740, y: 260 }
  },
  {
    id: "SKU-USB-CHARGER",
    name: "Braided 65W Fast Charger Kit",
    category: "Electronics",
    capacity: 4,
    packSize: 6,
    retailPrice: 29.99,
    unitCost: 14.00,
    isHighTheft: true,
    shelfLoc: "Aisle 2 - High-Value Tech",
    rackLoc: "Backroom Rack B-3",
    shelfCoords: { x: 390, y: 230 },
    backroomCoords: { x: 820, y: 260 }
  },
  {
    id: "SKU-BT-EARBUDS",
    name: "Pro Wireless Bluetooth Earbuds",
    category: "Electronics",
    capacity: 6,
    packSize: 10,
    retailPrice: 49.99,
    unitCost: 25.00,
    isHighTheft: true,
    shelfLoc: "Aisle 2 - High-Value Tech",
    rackLoc: "Backroom Rack B-2",
    shelfCoords: { x: 390, y: 310 },
    backroomCoords: { x: 820, y: 330 }
  },
  {
    id: "SKU-PROTEIN-BARS",
    name: "Artisan Protein Bars 10-Pack",
    category: "Snacks",
    capacity: 8,
    packSize: 24,
    retailPrice: 15.99,
    unitCost: 8.50,
    isHighTheft: true,
    shelfLoc: "Register Counter Tier 1",
    rackLoc: "Backroom Rack A-1",
    shelfCoords: { x: 440, y: 430 },
    backroomCoords: { x: 740, y: 330 }
  },
  {
    id: "SKU-SPARKLING-12PK",
    name: "Craft Sparkling Water 12pk",
    category: "Beverages",
    capacity: 6,
    packSize: 2,
    retailPrice: 10.99,
    unitCost: 6.00,
    isHighTheft: false,
    shelfLoc: "Cold Vault Door 2",
    rackLoc: "Backroom Floor Pallet C",
    shelfCoords: { x: 670, y: 120 },
    backroomCoords: { x: 780, y: 440 }
  }
];

// --- 2. Simulation State ---
const State = {
  isRunning: true,
  speed: 1,
  simTimeMinutes: 540, // 09:00 AM (9 * 60)
  
  // Metrics
  totalSales: 0.0,
  lostSales: 0.0,
  tripsMade: 0,
  theftsDeterred: 0,
  theftsSucceeded: 0,
  theftDollarsLost: 0.0,
  crossDockUnits: 0,
  
  // Inventory (SKU ID -> { shelf, fullCases, looseUnits })
  inventory: {},
  
  // Entities
  clerk: {
    x: 470,
    y: 470,
    targetX: 470,
    targetY: 470,
    state: "AT_COUNTER", // AT_COUNTER, MOVING_TO_BACK, IN_BACKROOM, MOVING_TO_SHELF, RESTOCKING
    basket: [],
    timer: 0
  },
  customers: [],
  truck: { active: false, x: 980, y: 340, timer: 0 },
  
  // Dispatch & Security Gate
  currentDispatch: null,
  isTheftInhibited: false,
  inhibitReason: null,
  securityAlertTime: 0
};

// Initialize Inventory
CATALOG.forEach(sku => {
  State.inventory[sku.id] = {
    shelf: sku.capacity,
    fullCases: sku.id.includes("SPARKLING") ? 5 : (sku.id.includes("ENERGY") ? 4 : 2),
    looseUnits: sku.id.includes("PROTEIN") ? 14 : 2
  };
});

// --- 3. Canvas & Map Rendering ---
const canvas = document.getElementById("storeCanvas");
const ctx = canvas.getContext("2d");

// Layout zones
const MAP = {
  counter: { x: 380, y: 430, w: 180, h: 50, label: "POS REGISTER COUNTER" },
  queueArea: { x: 420, y: 485, w: 100, h: 60 },
  aisle1: { x: 110, y: 180, w: 130, h: 220, label: "AISLE 1: SNACKS & ESSENTIALS" },
  aisle2: { x: 330, y: 180, w: 130, h: 220, label: "AISLE 2: HIGH-VALUE TECH" },
  cooler: { x: 530, y: 70, w: 320, h: 60, label: "BEVERAGE & REFRIGERATED WALL" },
  backroom: { x: 690, y: 180, w: 220, h: 350, label: "BACKROOM CARTON STORAGE" },
  entrance: { x: 70, y: 500, w: 110, h: 50, label: "ENTRANCE / EXIT" }
};

function drawStore() {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // Background Grid / Store Floor Tiles
  ctx.fillStyle = "#0c111d";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "rgba(255, 255, 255, 0.02)";
  ctx.lineWidth = 1;
  for (let x = 0; x < canvas.width; x += 30) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, canvas.height);
    ctx.stroke();
  }
  for (let y = 0; y < canvas.height; y += 30) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  // Draw Zones
  drawAisle(MAP.aisle1, false);
  drawAisle(MAP.aisle2, true); // High-Theft Zone!
  drawCooler(MAP.cooler);
  drawBackroom(MAP.backroom);
  drawCounter(MAP.counter);
  drawEntrance(MAP.entrance);

  // Draw Truck if active
  if (State.truck.active) {
    drawDeliveryTruck(State.truck.x, State.truck.y);
  }

  // Draw Customers
  State.customers.forEach(drawCustomer);

  // Draw Clerk
  drawClerk(State.clerk);
}

function drawAisle(zone, isHighTheft) {
  // Aisle Floor / Shelf Base
  ctx.fillStyle = isHighTheft ? "rgba(245, 158, 11, 0.05)" : "rgba(30, 41, 59, 0.5)";
  ctx.fillRect(zone.x, zone.y, zone.w, zone.h);

  // Border (Glowing amber if high-theft)
  ctx.strokeStyle = isHighTheft ? "rgba(245, 158, 11, 0.5)" : "rgba(255, 255, 255, 0.1)";
  ctx.lineWidth = isHighTheft ? 2 : 1;
  if (isHighTheft) {
    ctx.setLineDash([5, 5]);
  } else {
    ctx.setLineDash([]);
  }
  ctx.strokeRect(zone.x, zone.y, zone.w, zone.h);
  ctx.setLineDash([]);

  // Label
  ctx.fillStyle = isHighTheft ? "#f59e0b" : "#94a3b8";
  ctx.font = "bold 10px JetBrains Mono";
  ctx.fillText(zone.label, zone.x + 8, zone.y - 8);

  if (isHighTheft) {
    ctx.fillStyle = "rgba(245, 158, 11, 0.25)";
    ctx.fillRect(zone.x + 4, zone.y + 4, zone.w - 8, 18);
    ctx.fillStyle = "#fbbf24";
    ctx.font = "9px Outfit";
    ctx.fillText("⚠ CCTV THEFT SENSOR ACTIVE", zone.x + 10, zone.y + 16);
  }

  // Draw Individual Shelf bays with bottle counts
  const skusInAisle = CATALOG.filter(s => s.shelfLoc.includes(isHighTheft ? "Aisle 2" : "Aisle 1"));
  skusInAisle.forEach((sku, idx) => {
    const inv = State.inventory[sku.id];
    const shelfY = zone.y + 45 + (idx * 75);

    // Shelf slot box
    ctx.fillStyle = "rgba(15, 23, 42, 0.8)";
    ctx.fillRect(zone.x + 10, shelfY, zone.w - 20, 50);
    ctx.strokeStyle = inv.shelf === 0 ? "#ff3366" : "rgba(255, 255, 255, 0.1)";
    ctx.strokeRect(zone.x + 10, shelfY, zone.w - 20, 50);

    // Bottle icons
    const maxFacings = sku.capacity;
    const bottleW = (zone.w - 30) / maxFacings;
    for (let b = 0; b < maxFacings; b++) {
      ctx.fillStyle = b < inv.shelf ? (isHighTheft ? "#f59e0b" : "#00f2fe") : "rgba(255, 255, 255, 0.08)";
      ctx.fillRect(zone.x + 15 + (b * bottleW), shelfY + 22, bottleW - 3, 20);
    }

    // Text Label
    ctx.fillStyle = "#fff";
    ctx.font = "9px Outfit";
    ctx.fillText(`${sku.name.split(" ")[0]} (${inv.shelf}/${sku.capacity})`, zone.x + 14, shelfY + 15);
  });
}

function drawCooler(zone) {
  ctx.fillStyle = "rgba(6, 182, 212, 0.08)";
  ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
  ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
  ctx.strokeRect(zone.x, zone.y, zone.w, zone.h);

  ctx.fillStyle = "#38bdf8";
  ctx.font = "bold 10px JetBrains Mono";
  ctx.fillText(zone.label, zone.x + 10, zone.y - 6);

  // Cooler doors
  const doorW = zone.w / 4;
  for (let d = 0; d < 4; d++) {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
    ctx.strokeRect(zone.x + (d * doorW), zone.y, doorW, zone.h);
    ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
    ctx.fillRect(zone.x + (d * doorW) + 4, zone.y + 4, doorW - 8, zone.h - 8);
  }

  // Sparkling Water facing
  const sparklingInv = State.inventory["SKU-SPARKLING-12PK"];
  ctx.fillStyle = "#fff";
  ctx.font = "9px Outfit";
  ctx.fillText(`Sparkling 12pk [Door 2]: ${sparklingInv.shelf}/6`, zone.x + doorW + 8, zone.y + 35);
}

function drawBackroom(zone) {
  ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
  ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
  ctx.strokeStyle = "rgba(99, 102, 241, 0.35)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(zone.x, zone.y, zone.w, zone.h);

  ctx.fillStyle = "#818cf8";
  ctx.font = "bold 10px JetBrains Mono";
  ctx.fillText(zone.label, zone.x + 10, zone.y - 8);

  // Backroom Doorway
  ctx.fillStyle = "rgba(99, 102, 241, 0.2)";
  ctx.fillRect(zone.x - 10, zone.y + 120, 20, 45);
  ctx.fillStyle = "#c7d2fe";
  ctx.font = "8px JetBrains Mono";
  ctx.fillText("DOOR", zone.x - 8, zone.y + 145);

  // Racks A & B
  drawRack(zone.x + 20, zone.y + 30, 80, 120, "RACK A (Beverages/Snacks)");
  drawRack(zone.x + 115, zone.y + 30, 80, 120, "RACK B (High-Value Tech)");
  drawRack(zone.x + 20, zone.y + 190, 175, 120, "FLOOR PALLET (Multi-Pack Cases)");
}

function drawRack(x, y, w, h, title) {
  ctx.fillStyle = "rgba(30, 41, 59, 0.6)";
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = "rgba(255, 255, 255, 0.1)";
  ctx.strokeRect(x, y, w, h);

  ctx.fillStyle = "#94a3b8";
  ctx.font = "8px JetBrains Mono";
  ctx.fillText(title, x + 6, y + 14);

  // Box shapes
  ctx.fillStyle = "rgba(180, 83, 9, 0.4)";
  ctx.fillRect(x + 8, y + 24, w - 16, h - 34);
  ctx.strokeStyle = "rgba(245, 158, 11, 0.4)";
  ctx.strokeRect(x + 8, y + 24, w - 16, h - 34);
}

function drawCounter(zone) {
  ctx.fillStyle = "rgba(30, 41, 59, 0.9)";
  ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
  ctx.strokeStyle = "rgba(0, 242, 254, 0.4)";
  ctx.strokeRect(zone.x, zone.y, zone.w, zone.h);

  // Register Screen
  ctx.fillStyle = "#00f2fe";
  ctx.fillRect(zone.x + 70, zone.y + 12, 35, 24);
  ctx.fillStyle = "#000";
  ctx.font = "bold 8px JetBrains Mono";
  ctx.fillText("POS", zone.x + 78, zone.y + 27);

  // Protein bars impulse bin
  const proteinInv = State.inventory["SKU-PROTEIN-BARS"];
  ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
  ctx.fillRect(zone.x + 12, zone.y + 10, 45, 30);
  ctx.fillStyle = "#fca5a5";
  ctx.font = "8px Outfit";
  ctx.fillText(`Protein: ${proteinInv.shelf}/8`, zone.x + 14, zone.y + 28);
}

function drawEntrance(zone) {
  ctx.fillStyle = "rgba(255, 255, 255, 0.03)";
  ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
  ctx.strokeStyle = "rgba(16, 185, 129, 0.4)";
  ctx.setLineDash([4, 4]);
  ctx.strokeRect(zone.x, zone.y, zone.w, zone.h);
  ctx.setLineDash([]);

  ctx.fillStyle = "#10b981";
  ctx.font = "bold 9px JetBrains Mono";
  ctx.fillText("EXIT TRIPWIRE", zone.x + 10, zone.y + 28);
}

function drawClerk(clerk) {
  // Smooth position lerp
  clerk.x += (clerk.targetX - clerk.x) * 0.12;
  clerk.y += (clerk.targetY - clerk.y) * 0.12;

  // Outer glow
  ctx.fillStyle = "rgba(0, 242, 254, 0.25)";
  ctx.beginPath();
  ctx.arc(clerk.x, clerk.y, 16, 0, Math.PI * 2);
  ctx.fill();

  // Core circle
  ctx.fillStyle = "#00f2fe";
  ctx.beginPath();
  ctx.arc(clerk.x, clerk.y, 9, 0, Math.PI * 2);
  ctx.fill();

  // Label
  ctx.fillStyle = "#fff";
  ctx.font = "bold 10px Outfit";
  ctx.textAlign = "center";
  ctx.fillText("ASSOCIATE", clerk.x, clerk.y - 18);
  ctx.textAlign = "left";

  // Carrying payload indicator
  if (clerk.basket.length > 0) {
    const totalUnits = clerk.basket.reduce((a, b) => a + b.qty, 0);
    ctx.fillStyle = "#10b981";
    ctx.fillRect(clerk.x - 18, clerk.y + 14, 36, 14);
    ctx.fillStyle = "#000";
    ctx.font = "bold 8px JetBrains Mono";
    ctx.fillText(`📦 ${totalUnits} Units`, clerk.x - 16, clerk.y + 24);
  }
}

function drawCustomer(cust) {
  // Lerp position
  cust.x += (cust.targetX - cust.x) * 0.08;
  cust.y += (cust.targetY - cust.y) * 0.08;

  const isThief = cust.isThief;
  const isSuspicious = isThief && cust.dwellSeconds > 25;

  if (isSuspicious) {
    // Pulsing danger aura
    ctx.fillStyle = "rgba(255, 51, 102, 0.35)";
    ctx.beginPath();
    ctx.arc(cust.x, cust.y, 20 + Math.sin(Date.now() / 150) * 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // Customer dot
  ctx.fillStyle = isThief ? "#ff3366" : "#10b981";
  ctx.beginPath();
  ctx.arc(cust.x, cust.y, 8, 0, Math.PI * 2);
  ctx.fill();

  // Dwell tag
  ctx.fillStyle = isSuspicious ? "#ff3366" : "#cbd5e1";
  ctx.font = "9px Outfit";
  ctx.textAlign = "center";
  const label = isSuspicious ? `LOITERING ${Math.floor(cust.dwellSeconds)}s!` : `Browsing (${Math.floor(cust.dwellSeconds)}s)`;
  ctx.fillText(label, cust.x, cust.y - 12);
  ctx.textAlign = "left";
}

function drawDeliveryTruck(x, y) {
  ctx.fillStyle = "#1e293b";
  ctx.fillRect(x, y, 90, 48);
  ctx.strokeStyle = "#00f2fe";
  ctx.strokeRect(x, y, 90, 48);

  ctx.fillStyle = "#00f2fe";
  ctx.font = "bold 8px JetBrains Mono";
  ctx.fillText("APEX TRUCK", x + 10, y + 26);
}

// --- 4. Simulation Engine Tick ---
let lastTickTime = performance.now();

function updateSimulation() {
  if (!State.isRunning) return;

  const now = performance.now();
  const deltaSeconds = ((now - lastTickTime) / 1000) * State.speed;
  lastTickTime = now;

  // Advance time
  State.simTimeMinutes += (deltaSeconds / 60) * 8; // 8x scale for demonstration
  updateShiftClock();

  // Spawn Customers
  if (Math.random() < 0.035 * State.speed && State.customers.length < 6) {
    spawnCustomer(false);
  }

  // Update Customers
  State.isTheftInhibited = false;
  State.inhibitReason = null;

  for (let i = State.customers.length - 1; i >= 0; i--) {
    const c = State.customers[i];
    c.dwellSeconds += deltaSeconds;

    // Check if in High-Theft Zone (Aisle 2)
    const inHighTheft = (c.x >= MAP.aisle2.x && c.x <= MAP.aisle2.x + MAP.aisle2.w &&
                         c.y >= MAP.aisle2.y && c.y <= MAP.aisle2.y + MAP.aisle2.h);

    if (inHighTheft && c.dwellSeconds >= 30) {
      State.isTheftInhibited = true;
      State.inhibitReason = `Customer lingering ${Math.floor(c.dwellSeconds)}s in High-Value Tech Aisle. Maintain presence at register.`;
    }

    // Customer State Machine
    if (c.state === "BROWSING") {
      if (c.dwellSeconds >= c.targetBrowseTime) {
        if (c.isThief) {
          // Attempt Shoplifting
          const clerkAtRegister = (Math.hypot(State.clerk.x - 470, State.clerk.y - 470) < 50);
          if (clerkAtRegister) {
            // Associate is watching! Thief is deterred
            State.theftsDeterred++;
            showToast("Theft Deterred: Associate visual eye-contact stopped concealment in High-Value Tech Aisle!", "success");
            c.state = "EXITING";
            c.targetX = MAP.entrance.x + 30;
            c.targetY = MAP.entrance.y + 20;
          } else {
            // Associate is in the backroom! Shoplifter steals
            const targetSku = CATALOG.find(s => s.id === c.targetSkuId);
            const inv = State.inventory[targetSku.id];
            if (inv.shelf > 0) {
              inv.shelf--;
              State.theftsSucceeded++;
              State.theftDollarsLost += targetSku.retailPrice;
              showToast(`CRITICAL SHRINK: ${targetSku.name} pocketed while associate in backroom!`, "alert");
            }
            c.state = "EXITING";
            c.targetX = MAP.entrance.x + 30;
            c.targetY = MAP.entrance.y + 20;
          }
        } else {
          // Honest customer moves to checkout line
          c.state = "IN_QUEUE";
          const queueIdx = State.customers.filter(cust => cust.state === "IN_QUEUE").indexOf(c);
          c.targetX = MAP.counter.x + 90;
          c.targetY = MAP.counter.y + 55 + (queueIdx * 18);
        }
      }
    } else if (c.state === "IN_QUEUE") {
      // Check if at front of counter
      const clerkAtRegister = (Math.hypot(State.clerk.x - 470, State.clerk.y - 470) < 50);
      if (clerkAtRegister && Math.hypot(c.x - (MAP.counter.x + 90), c.y - (MAP.counter.y + 55)) < 15) {
        // Complete checkout!
        const sku = CATALOG.find(s => s.id === c.targetSkuId);
        const inv = State.inventory[sku.id];
        if (inv.shelf > 0) {
          inv.shelf--;
          State.totalSales += sku.retailPrice;
          showToast(`Sold 1x ${sku.name} ($${sku.retailPrice.toFixed(2)})`, "success");
        } else {
          State.lostSales += sku.retailPrice;
          showToast(`Stockout: Customer wanted ${sku.name} but shelf was empty!`, "alert");
        }

        c.state = "EXITING";
        c.targetX = MAP.entrance.x + 30;
        c.targetY = MAP.entrance.y + 20;
      }
    } else if (c.state === "EXITING") {
      if (Math.hypot(c.x - (MAP.entrance.x + 30), c.y - (MAP.entrance.y + 20)) < 20) {
        State.customers.splice(i, 1);
      }
    }
  }

  // Update Clerk Restock Animation State
  updateClerkState(deltaSeconds);

  // Evaluate Restock Dispatch HUD
  evaluateDispatcher();

  // Render
  drawStore();
  updateUI();
  requestAnimationFrame(updateSimulation);
}

function spawnCustomer(forceThief = false) {
  const chosenSku = CATALOG[Math.floor(Math.random() * CATALOG.length)];
  const isThief = forceThief || (Math.random() < 0.08 && chosenSku.isHighTheft);

  State.customers.push({
    x: MAP.entrance.x + 20,
    y: MAP.entrance.y + 20,
    targetX: chosenSku.shelfCoords.x,
    targetY: chosenSku.shelfCoords.y + (Math.random() * 20 - 10),
    targetSkuId: chosenSku.id,
    isThief: isThief,
    state: "BROWSING",
    dwellSeconds: 0,
    targetBrowseTime: isThief ? 35 : (12 + Math.random() * 15)
  });
}

function updateClerkState(deltaSeconds) {
  const clerk = State.clerk;

  if (clerk.state === "MOVING_TO_BACK") {
    clerk.targetX = 740;
    clerk.targetY = 300;
    if (Math.hypot(clerk.x - 740, clerk.y - 300) < 15) {
      clerk.state = "PICKING_IN_BACKROOM";
      clerk.timer = 2.0; // 2 seconds fast-forward
    }
  } else if (clerk.state === "PICKING_IN_BACKROOM") {
    clerk.timer -= deltaSeconds;
    if (clerk.timer <= 0) {
      clerk.state = "MOVING_TO_SHELF";
    }
  } else if (clerk.state === "MOVING_TO_SHELF") {
    if (clerk.basket.length > 0) {
      const firstItem = clerk.basket[0];
      const sku = CATALOG.find(s => s.id === firstItem.skuId);
      clerk.targetX = sku.shelfCoords.x;
      clerk.targetY = sku.shelfCoords.y;

      if (Math.hypot(clerk.x - sku.shelfCoords.x, clerk.y - sku.shelfCoords.y) < 20) {
        // Restock shelf
        const inv = State.inventory[sku.id];
        inv.shelf = Math.min(sku.capacity, inv.shelf + firstItem.qty);
        clerk.basket.shift();
        showToast(`Restocked ${firstItem.qty}x ${sku.name} on facing.`, "success");
      }
    } else {
      // Done with all basket items, return to register counter
      clerk.targetX = 470;
      clerk.targetY = 470;
      if (Math.hypot(clerk.x - 470, clerk.y - 470) < 15) {
        clerk.state = "AT_COUNTER";
      }
    }
  }
}

// --- 5. Batcher & Dispatcher Logic ---
function evaluateDispatcher() {
  const queueCount = State.customers.filter(c => c.state === "IN_QUEUE").length;
  const overlayBanner = document.getElementById("canvas-overlay-banner");
  const overlayText = document.getElementById("overlay-banner-text");

  // Check Security Inhibit
  if (State.isTheftInhibited) {
    document.getElementById("dispatch-hud-card").classList.add("inhibited");
    document.getElementById("hud-safety-badge").className = "safety-score-badge danger";
    document.getElementById("hud-safety-badge").innerText = "Safety: 12% (LOCKED)";
    document.getElementById("hud-status-banner").className = "hud-status-banner danger";
    document.getElementById("hud-banner-title").innerText = "RESTOCK INHIBIT LOCK ACTIVE";
    document.getElementById("hud-banner-sub").innerText = State.inhibitReason;
    document.getElementById("btn-exec-dispatch").disabled = true;

    overlayBanner.classList.remove("hidden");
    overlayText.innerText = "SECURITY ALERT: RESTOCK INHIBITED (LOITERING DETECTED)";
    return;
  } else {
    overlayBanner.classList.add("hidden");
    document.getElementById("dispatch-hud-card").classList.remove("inhibited");
  }

  // Check Queue
  if (queueCount > 0) {
    document.getElementById("hud-safety-badge").className = "safety-score-badge";
    document.getElementById("hud-safety-badge").innerText = "Safety: 45%";
    document.getElementById("hud-status-banner").className = "hud-status-banner";
    document.getElementById("hud-banner-title").innerText = "Counter Busy";
    document.getElementById("hud-banner-sub").innerText = `${queueCount} customer(s) at register. Serving customer...`;
    document.getElementById("btn-exec-dispatch").disabled = true;
    return;
  }

  // Compute Deficits & Knapsack
  const batch = [];
  let totalUrgency = 0;

  CATALOG.forEach(sku => {
    const inv = State.inventory[sku.id];
    const deficit = sku.capacity - inv.shelf;
    if (deficit > 0) {
      const rui = (deficit / sku.capacity) * (sku.retailPrice / 15.0);
      totalUrgency += rui;
      batch.push({
        skuId: sku.id,
        name: sku.name,
        qty: Math.min(deficit, 3),
        source: sku.rackLoc,
        target: sku.shelfLoc
      });
    }
  });

  if (batch.length > 0 && totalUrgency >= 0.4 && State.clerk.state === "AT_COUNTER") {
    State.currentDispatch = batch.slice(0, 3); // Max 3 SKUs per carry payload
    document.getElementById("hud-safety-badge").className = "safety-score-badge";
    document.getElementById("hud-safety-badge").innerText = "Safety: 94%";
    document.getElementById("hud-status-banner").className = "hud-status-banner safe";
    document.getElementById("hud-banner-title").innerText = "Quiet Window Open (~180s)";
    document.getElementById("hud-banner-sub").innerText = "Register clear. Optimized 45-second batch ready.";
    document.getElementById("btn-exec-dispatch").disabled = false;
    renderHUDList(State.currentDispatch);
  } else {
    document.getElementById("hud-safety-badge").className = "safety-score-badge";
    document.getElementById("hud-safety-badge").innerText = "Safety: 98%";
    document.getElementById("hud-status-banner").className = "hud-status-banner safe";
    document.getElementById("hud-banner-title").innerText = State.clerk.state === "AT_COUNTER" ? "Shelves Optimal" : "Restock in Progress";
    document.getElementById("hud-banner-sub").innerText = State.clerk.state === "AT_COUNTER" ? "All single-faced shelves healthy." : "Clerk executing mapped pick path...";
    document.getElementById("btn-exec-dispatch").disabled = true;
    document.getElementById("hud-batch-list").innerHTML = `<div style="text-align:center; padding:18px; color:#64748b; font-size:11px;">No pending restock needed.</div>`;
  }
}

function renderHUDList(items) {
  const container = document.getElementById("hud-batch-list");
  container.innerHTML = items.map(item => `
    <div class="batch-item">
      <div class="batch-item-left">
        <div class="item-qty-bubble">${item.qty}x</div>
        <div class="item-text">
          <h4>${item.name}</h4>
          <p>${item.source} ➔ ${item.target}</p>
        </div>
      </div>
      <span style="font-size:10px; color:#00f2fe; font-family:var(--font-mono); font-weight:600;">45s pick</span>
    </div>
  `).join("");
}

// --- 6. UI & Heatmap Sync ---
function updateUI() {
  document.getElementById("kpi-sales").innerText = `$${State.totalSales.toFixed(2)}`;
  document.getElementById("kpi-lost-sales").innerText = `$${State.lostSales.toFixed(2)}`;
  document.getElementById("kpi-trips").innerHTML = `${State.tripsMade} <small>(~70% saved)</small>`;
  document.getElementById("kpi-thefts").innerText = `${State.theftsDeterred}`;
  document.getElementById("kpi-crossdock").innerText = `${State.crossDockUnits}`;

  // Shelf Grid
  const grid = document.getElementById("shelf-grid");
  grid.innerHTML = CATALOG.map(sku => {
    const inv = State.inventory[sku.id];
    const fillPercent = Math.round((inv.shelf / sku.capacity) * 100);
    const colorClass = inv.shelf === 0 ? "critical" : (inv.shelf <= 2 ? "low" : "healthy");

    return `
      <div class="shelf-row">
        <div class="shelf-row-top">
          <span class="shelf-name">
            ${sku.name}
            ${sku.isHighTheft ? `<span class="theft-pill">HIGH THEFT</span>` : ''}
          </span>
          <span class="shelf-counts">${inv.shelf}/${sku.capacity} on shelf (${inv.fullCases}cs back)</span>
        </div>
        <div class="shelf-meter">
          <div class="shelf-fill-bar ${colorClass}" style="width: ${fillPercent}%"></div>
        </div>
      </div>
    `;
  }).join("");

  const outOfStockCount = CATALOG.filter(s => State.inventory[s.id].shelf === 0).length;
  document.getElementById("shelf-stockout-count").innerText = `${outOfStockCount} Out-of-Stock`;
}

function updateShiftClock() {
  const hours = Math.floor(State.simTimeMinutes / 60);
  const mins = Math.floor(State.simTimeMinutes % 60);
  const ampm = hours >= 12 ? "PM" : "AM";
  const displayHours = hours > 12 ? hours - 12 : (hours === 0 ? 12 : hours);
  const timeStr = `${displayHours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")} ${ampm}`;
  document.getElementById("shift-clock").innerText = timeStr;
}

function showToast(message, type = "info") {
  const feed = document.getElementById("toast-feed");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerText = message;
  feed.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// --- 7. Interactive Event Listeners ---
document.getElementById("btn-exec-dispatch").addEventListener("click", () => {
  if (!State.currentDispatch || State.currentDispatch.length === 0) return;
  State.tripsMade++;
  State.clerk.state = "MOVING_TO_BACK";
  State.clerk.basket = [...State.currentDispatch];
  showToast(`Clerk dispatched on 45s batch trip (${State.currentDispatch.length} SKUs).`, "success");
});

document.getElementById("btn-play-pause").addEventListener("click", () => {
  State.isRunning = !State.isRunning;
  document.getElementById("play-pause-icon").innerText = State.isRunning ? "⏸" : "▶";
  document.getElementById("play-pause-text").innerText = State.isRunning ? "Pause" : "Play";
  if (State.isRunning) {
    lastTickTime = performance.now();
    requestAnimationFrame(updateSimulation);
  }
});

document.querySelectorAll(".btn-speed").forEach(btn => {
  btn.addEventListener("click", (e) => {
    document.querySelectorAll(".btn-speed").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    State.speed = parseInt(btn.dataset.speed, 10);
  });
});

// Scenario buttons
document.getElementById("btn-rush-hour").addEventListener("click", () => {
  showToast("Rush hour surge: 4 customers entering simultaneously!", "alert");
  for (let i = 0; i < 4; i++) {
    spawnCustomer(false);
  }
});

document.getElementById("btn-theft-attempt").addEventListener("click", () => {
  showToast("Security flag: Shoplifter entering, targeting High-Value Tech!", "alert");
  spawnCustomer(true);
});

document.getElementById("btn-truck-delivery").addEventListener("click", () => {
  State.truck.active = true;
  State.truck.x = 980;
  showToast("Supplier Delivery: Apex National truck rolled in with 9 cases!", "success");
  document.getElementById("po-modal").classList.remove("hidden");
  populateInvoiceModal();
});

document.getElementById("btn-uber-eats").addEventListener("click", () => {
  showToast("Courier Order #ORD-402: 1x Fast Charger Kit, 1x Sparkling Water 12pk", "success");
  CATALOG.forEach(s => {
    if (s.id.includes("CHARGER") || s.id.includes("SPARKLING")) {
      if (State.inventory[s.id].shelf > 0) {
        State.inventory[s.id].shelf--;
        State.totalSales += s.retailPrice;
      }
    }
  });
});

document.getElementById("btn-reset-sim").addEventListener("click", () => {
  CATALOG.forEach(sku => {
    State.inventory[sku.id].shelf = sku.capacity;
  });
  State.customers = [];
  State.totalSales = 0;
  State.lostSales = 0;
  State.tripsMade = 0;
  State.theftsDeterred = 0;
  showToast("Shift reset. All single facings restocked to capacity.", "info");
});

// Modal Logic
function populateInvoiceModal() {
  const tbody = document.getElementById("invoice-tbody");
  const invoiceItems = [
    { code: "APX-4821", name: "Vitality Energy Drink 16oz (12pk)", pack: 12, cases: 4, cost: 1.80, total: 86.40, crossDock: "1 unit ➔ Aisle 1" },
    { code: "APX-9012", name: "Braided 65W Fast Charger Kit", pack: 6, cases: 2, cost: 14.00, total: 168.00, crossDock: "Stored Rack B-3" },
    { code: "APX-1102", name: "Pro Wireless Bluetooth Earbuds", pack: 10, cases: 2, cost: 25.00, total: 500.00, crossDock: "Stored Rack B-2" },
    { code: "APX-0303", name: "Artisan Protein Bars 10-Pack", pack: 24, cases: 1, cost: 8.50, total: 204.00, crossDock: "6 units ➔ Counter" }
  ];

  tbody.innerHTML = invoiceItems.map(item => `
    <tr>
      <td>${item.code}</td>
      <td><strong>${item.name}</strong></td>
      <td>${item.pack}</td>
      <td><strong>${item.cases}</strong></td>
      <td>$${item.cost.toFixed(2)}</td>
      <td>$${item.total.toFixed(2)}</td>
      <td><span class="crossdock-tag">${item.crossDock}</span></td>
    </tr>
  `).join("");
}

document.getElementById("btn-open-po-modal").addEventListener("click", () => {
  document.getElementById("po-modal").classList.remove("hidden");
  populateInvoiceModal();
});

document.getElementById("btn-close-modal").addEventListener("click", () => {
  document.getElementById("po-modal").classList.add("hidden");
});

document.getElementById("btn-apply-crossdock").addEventListener("click", () => {
  // Apply cross-docking to inventory
  State.crossDockUnits += 7;
  State.inventory["SKU-ENERGY-16OZ"].shelf = Math.min(5, State.inventory["SKU-ENERGY-16OZ"].shelf + 1);
  State.inventory["SKU-PROTEIN-BARS"].shelf = Math.min(8, State.inventory["SKU-PROTEIN-BARS"].shelf + 6);
  document.getElementById("po-modal").classList.add("hidden");
  showToast("Cross-dock putaway applied! 7 units stocked straight to floor, saving 2 trips.", "success");
});

// Start loop
requestAnimationFrame(updateSimulation);
