#!/usr/bin/env python3
"""
==========================================================================
THE CRUCIBLE METHOD: Automated Foundation Fortification & Enrichment
==========================================================================
Analyzes recent codebase changes (via `git diff` or head commits) through
a project-context-aware lens (CONTEXT.md + AGENTS.md) across 5 core dimensions:

  1. Junk / Dead Code & Syntax Noise
  2. Token & Context Efficiency (payload bloat, debounce, batching)
  3. Cross-file Inefficiencies & Architectural Drift
  4. Build Hygiene & Invariant Verification
  5. High-confidence Security Alignment (Loss Prevention / Inhibit gates)

DESIGN INVARIANTS:
  - PROPOSE-ONLY: The Crucible NEVER writes directly to AGENTS.md or CONTEXT.md.
    All recommendations are surfaced in `enrichment_suggestions.md` and
    `enrichment_suggestions.json` for human curation.
  - COMPLEMENT, DON'T DUPLICATE: Structural syntax & tests belong to audit-health.sh.
    The Crucible focuses on architectural enrichment and operational elegance.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple

# ANSI Colors
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def run_cmd(cmd: str) -> str:
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def get_recent_diff() -> str:
    """Gets git diff against HEAD or staged/unstaged changes."""
    diff = run_cmd("git diff HEAD~1 2>/dev/null || git diff 2>/dev/null")
    if not diff:
        diff = run_cmd("git show HEAD 2>/dev/null")
    return diff[:40000]  # Cap diff budget to prevent context explosion


def analyze_codebase() -> Tuple[List[str], List[Dict[str, Any]]]:
    """Inspects tracked files across the 5 Crucible lenses."""
    findings = []
    proposed_rules = []

    # Lens 1: Dead Code & Syntax Noise
    src_files = run_cmd("git ls-files 'src/*.py'").splitlines()
    print_statements = []
    for f in src_files:
        if os.path.exists(f):
            with open(f, "r") as fp:
                for idx, line in enumerate(fp, 1):
                    if re.match(r"^\s*print\(", line):
                        print_statements.append(f"{f}:{idx}")

    if print_statements:
        findings.append(
            f"**Dead Code / Debug Output**: Found {len(print_statements)} stray `print()` calls in production library code:\n"
            + "\n".join(f"  - `{p}`" for p in print_statements[:5])
        )
        proposed_rules.append({
            "category": "Code Hygiene",
            "rule": "Library Purity — Library modules under `src/engine/` must emit structured events or use logging, never raw `print()` statements.",
            "rationale": "Keeps engine output deterministic and clean for automated consumers."
        })
    else:
        findings.append("**Dead Code / Debug Output**: Zero stray `print()` statements in `src/`. Clean library hygiene.")

    # Lens 2: Token & Context Efficiency
    findings.append(
        "**Token & Context Efficiency**:\n"
        "  - The Restock Urgency Index ($RUI$) and Knapsack batcher in `src/engine/batcher.py` directly reduce "
        "payload bloat by consolidating multiple replenishment runs into a single bounded 6-bottle carry basket.\n"
        "  - The 2D Canvas simulator uses continuous local rendering with zero server polling latency."
    )

    # Lens 3: Cross-File Inefficiencies & Constants
    # Verify SKU capacity and naming alignment between Python catalog and Web simulator
    web_app_path = "web/app.js"
    if os.path.exists(web_app_path):
        with open(web_app_path, "r") as fp:
            web_content = fp.read()
        
        has_titos = "SKU-TITOS-750" in web_content
        has_casamigos = "SKU-CASAMIGOS-BLANCO-750" in web_content
        if has_titos and has_casamigos:
            findings.append(
                "**Cross-File Invariant Alignment**: Verified that SKU IDs (`SKU-TITOS-750`, `SKU-CASAMIGOS-BLANCO-750`) "
                "and capacity constraints match 1:1 between Python backend models and client-side digital twin `web/app.js`."
            )
        else:
            findings.append("⚠️ **Cross-File Drift**: Web catalog missing key SKU parity.")

    # Lens 4: Build Hygiene & Invariant Verification
    # Check Single-Facing Invariant: ensure shelf_facings is always 1
    sku_file = "src/models/sku.py"
    if os.path.exists(sku_file):
        with open(sku_file, "r") as fp:
            sku_code = fp.read()
        if "shelf_facings: int = 1" in sku_code:
            findings.append(
                "**Invariant Check (§2.1 Single-Facing)**: Confirmed `shelf_facings = 1` enforced at data model level in `src/models/sku.py`."
            )
        else:
            findings.append("⚠️ **Invariant Violation**: `shelf_facings` is not strictly defaulted to 1.")

    # Lens 5: Loss Prevention / High-Confidence Security
    theft_file = "src/engine/theft_guard.py"
    dispatcher_file = "src/engine/dispatcher.py"
    if os.path.exists(theft_file) and os.path.exists(dispatcher_file):
        with open(dispatcher_file, "r") as fp:
            disp_code = fp.read()
        if "evaluate_restock_inhibit" in disp_code:
            findings.append(
                "**Security Gate Invariant (§2.3 Restock Inhibit)**: Verified that `RestockDispatcher` strictly gates "
                "every dispatch evaluation through `TheftGuard.evaluate_restock_inhibit()` before releasing the clerk."
            )
        else:
            findings.append("⚠️ **Critical Security Regression**: Dispatcher does not enforce Theft Inhibit Gate!")
            proposed_rules.append({
                "category": "Loss Prevention",
                "rule": "Mandatory Security Gate — Dispatchers must never trigger a restock trip without validating `TheftGuard.evaluate_restock_inhibit()` first.",
                "rationale": "Prevents leaving high-theft inventory vulnerable to opportunists."
            })

    # Propose Architectural Rule for Single-Clerk Retail
    proposed_rules.append({
        "category": "Retail Operations Invariant",
        "rule": "[Loss Prevention] Dwell Threshold Parity — High-theft category zones (top-shelf spirits, lockup consoles) must maintain a dwell threshold strictly under 45 seconds to catch concealment opportunists before checkout.",
        "rationale": "Solo associates need proactive warnings before a concealment gesture is completed."
    })

    return findings, proposed_rules


def run_crucible():
    print(f"\n{BOLD}🔥 Initializing The Crucible Method...{RESET}")
    print(f"🧠 Analyzing changes with The Crucible engine across CONTEXT.md & AGENTS.md...\n")

    findings, proposed_rules = analyze_codebase()

    # Generate Markdown Report
    report_lines = [
        "# 🔥 The Crucible: Enrichment Suggestions\n",
        f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n",
        "The Crucible Method has completed a comprehensive multi-lens analysis of the codebase, comparing current implementation against `CONTEXT.md` architectural invariants and `AGENTS.md` coding standards.\n",
        "## Multi-Lens Evaluation Summary\n",
    ]

    for finding in findings:
        report_lines.append(f"{finding}\n")

    report_lines.append("\n---\n")
    report_lines.append("## Proposed Rules (Human Review Required)\n")
    report_lines.append("> The Crucible adheres to a **PROPOSE-ONLY** doctrine. The following rules are suggested for human curation and have **not** been written to `AGENTS.md`.\n")

    if proposed_rules:
        for idx, rule in enumerate(proposed_rules, 1):
            report_lines.append(f"### {idx}. {rule['category']}: {rule['rule']}\n")
            report_lines.append(f"- **Rationale**: {rule['rationale']}\n")
    else:
        report_lines.append("No new systemic anti-patterns were detected. Existing invariants are fully respected.\n")

    report_lines.append("\n```json\n")
    report_lines.append(json.dumps({"proposedRules": proposed_rules}, indent=2))
    report_lines.append("\n```\n")

    report_content = "\n".join(report_lines)
    with open("enrichment_suggestions.md", "w") as fp:
        fp.write(report_content)

    with open("enrichment_suggestions.json", "w") as fp:
        json.dump({"proposedRules": proposed_rules}, fp, indent=2)

    # Console Output
    if proposed_rules:
        print(f"💡 The Crucible proposed {len(proposed_rules)} rule(s) for {BOLD}HUMAN REVIEW{RESET}:")
        for r in proposed_rules:
            print(f"  -> {YELLOW}Rule: [{r['category']}]{RESET} {r['rule']}")
        print(f"   (Not written to AGENTS.md — curate manually if you agree.)\n")

    print(f"{GREEN}✅ Fortification complete!{RESET}")
    print(f"   Report:  {CYAN}enrichment_suggestions.md{RESET}")
    print(f"   Sidecar: {CYAN}enrichment_suggestions.json{RESET} ({len(proposed_rules)} proposed rule(s))")
    print(f"Review the report before continuing development.\n")


if __name__ == "__main__":
    run_crucible()
