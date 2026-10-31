#!/bin/bash
# ==============================================================================
# 🏗️  Knight Shift Dev Health Scanner v1.0  🏗️
# ==============================================================================
set -e

SCAN_TIME=$(date -Iseconds)
echo "=========================================="
echo "🏗️  Knight Shift Dev Health Scanner v1.0  🏗️"
echo "=========================================="
echo "Scan time: $SCAN_TIME"
echo ""

ERRORS=0
WARNINGS=0

echo "── 1. Checking CONTEXT.md documents all core modules ──"
MODULES=(
  "src/models/sku.py"
  "src/models/inventory.py"
  "src/models/events.py"
  "src/engine/digital_twin.py"
  "src/engine/theft_guard.py"
  "src/engine/batcher.py"
  "src/engine/dispatcher.py"
  "src/engine/document_parser.py"
  "src/simulation/store_sim.py"
  "web/app.js"
)

for mod in "${MODULES[@]}"; do
  if grep -q "$mod" CONTEXT.md; then
    echo "  ✓ Module '$mod' is documented in CONTEXT.md"
  else
    echo "  ✗ WARNING: Module '$mod' is NOT documented in CONTEXT.md"
    WARNINGS=$((WARNINGS + 1))
  fi
done

echo ""
echo "── 2. Verifying Python compilation across all modules ──"
if python3 -m compileall -q src/ tests/ scripts/ 2>/dev/null; then
  echo "  ✓ All Python modules compiled cleanly with zero syntax errors"
else
  echo "  ✗ ERROR: Python syntax compilation error detected"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "── 3. Checking for orphaned debug/scratch files in project root ──"
ORPHANS=$(find . -maxdepth 1 -name "test_*.py" -o -name "scratch_*.py" -o -name "temp_*.py" | grep -v "tests/" || true)
if [ -z "$ORPHANS" ]; then
  echo "  ✓ No orphaned debug scripts in project root"
else
  echo "  ✗ WARNING: Found loose scratch files: $ORPHANS"
  WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "── 4. Executing automated test suite ──"
TEST_OUTPUT=$(python3 -m unittest discover -s tests 2>&1)
if echo "$TEST_OUTPUT" | grep -q "OK"; then
  COUNT=$(echo "$TEST_OUTPUT" | grep "Ran" | awk '{print $2}')
  echo "  ✓ All $COUNT unit tests passed with 100% success rate"
else
  echo "  ✗ ERROR: Unit tests failed"
  echo "$TEST_OUTPUT"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "── 5. Checking Web Application Static Assets ──"
if [ -f "web/index.html" ] && [ -f "web/style.css" ] && [ -f "web/app.js" ]; then
  echo "  ✓ Core web visualizer bundle present (index.html, style.css, app.js)"
else
  echo "  ✗ ERROR: Missing web bundle files"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "=========================================="
echo "Health Scan Complete"
echo "  Errors:   $ERRORS (must fix)"
echo "  Warnings: $WARNINGS (review)"
echo "=========================================="

if [ "$ERRORS" -gt 0 ]; then
  echo "❌ FAILED — Critical health issues found"
  exit 1
else
  echo "✅ HEALTHY — No critical issues found"
  exit 0
fi
