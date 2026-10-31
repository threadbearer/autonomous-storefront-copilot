#!/bin/bash
# ==============================================================================
# 🛡️  KNIGHT SHIFT AGENT GUARDRAILS & FORTIFICATION PROTOCOL  🛡️
# ==============================================================================
set -e

echo "======================================================"
echo "🛡️  Running Knight Shift Guardrails Protocol 🛡️"
echo "======================================================"

echo ""
echo "[1/3] Running Architecture & Health Scanner..."
./scripts/audit-health.sh

echo ""
echo "[2/3] Running Security & Secret Guard..."
./scripts/audit-security.sh

echo ""
echo "[3/3] Initializing The Crucible Method..."
python3 scripts/crucible.py

echo ""
echo "======================================================"
echo "✅ All Knight Shift Guardrails passed! Repository fortified."
echo "======================================================"
