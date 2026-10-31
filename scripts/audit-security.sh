#!/bin/bash
# ==============================================================================
# 🛡️  Knight Shift Security Scanner v1.0  🛡️
# ==============================================================================
set -e

echo "=========================================="
echo "🛡️  Knight Shift Security Scanner v1.0  🛡️"
echo "=========================================="

ERRORS=0

echo "── 1. Checking .gitignore covers sensitive credentials ──"
if [ -f ".gitignore" ]; then
  if grep -q "\.env" .gitignore; then
    echo "  ✓ .gitignore properly ignores .env files"
  else
    echo "  ✗ ERROR: .gitignore missing .env"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "  ✗ ERROR: Missing .gitignore file"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "── 2. Scanning for leaked API keys or credentials in tracked files ──"
SECRET_MATCHES=$(git grep -EI '(AIzaSy[0-9A-Za-z_-]{33}|sk_live_[0-9a-zA-Z]{24}|ghp_[0-9a-zA-Z]{36})' || true)
if [ -z "$SECRET_MATCHES" ]; then
  echo "  ✓ No live API keys, Stripe secrets, or GitHub tokens found"
else
  echo "  ✗ ERROR: Potential secret detected:"
  echo "$SECRET_MATCHES"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "── 3. Checking for forbidden hardcoded secrets in source code ──"
HARDCODED_PASS=$(git grep -Ei 'password\s*=\s*["'"'"'][^"'"'"']{8,}["'"'"']' -- ':!tests/*' || true)
if [ -z "$HARDCODED_PASS" ]; then
  echo "  ✓ No hardcoded plaintext passwords in source code"
else
  echo "  ✗ ERROR: Hardcoded password detected:"
  echo "$HARDCODED_PASS"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "=========================================="
echo "Security Scan Complete"
echo "  Errors: $ERRORS"
echo "=========================================="

if [ "$ERRORS" -gt 0 ]; then
  echo "❌ FAILED — Security violations detected"
  exit 1
else
  echo "✅ SECURE — All security invariants intact"
  exit 0
fi
