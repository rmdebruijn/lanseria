"""Audit report formatter -- JSON + text output."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from audit.checks import classify_check


def write_json_report(audit_data: dict, output_path: str | Path) -> Path:
    """Write audit results to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    results = audit_data["results"]
    summary = audit_data["summary"]

    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "verdict": ("BALANCED"
                     if summary["arithmetic_fail"] == 0
                     else "ARITHMETIC_ERRORS"),
        "checks": [
            {
                "section": r[0],
                "name": r[1],
                "expected": r[2],
                "actual": r[3],
                "delta": r[4],
                "passed": r[5],
                "category": classify_check(r[0], r[1]),
            }
            for r in results
        ],
    }

    with open(path, "w") as f:
        json.dump(report, f, indent=2)

    return path


def format_text_report(audit_data: dict) -> str:
    """Format audit results as human-readable text."""
    results = audit_data["results"]
    summary = audit_data["summary"]
    lines: list[str] = []

    lines.append("=" * 72)
    lines.append("SCLCA FINANCIAL MODEL - AUDIT REPORT")
    lines.append("=" * 72)
    lines.append("")

    # Group by section
    sections: OrderedDict[str, list] = OrderedDict()
    for r in results:
        sec = r[0]
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(r)

    # Arithmetic checks
    lines.append("ARITHMETIC CHECKS (internal consistency)")
    lines.append("-" * 72)
    for sec, checks in sections.items():
        arith = [r for r in checks
                 if classify_check(r[0], r[1]) == "arithmetic"]
        if not arith:
            continue
        fails = [r for r in arith if not r[5]]
        status = "ALL PASS" if not fails else f"{len(fails)} FAIL"
        lines.append(f"  {sec} ({len(arith)} checks, {status})")
        for r in fails:
            lines.append(f"    FAIL  {r[1]}")
            lines.append(f"          expected: {r[2]:>16,.2f}")
            lines.append(f"          actual:   {r[3]:>16,.2f}")
            lines.append(f"          delta:    {r[4]:>16,.2f}")
        if not fails and arith:
            max_d = max(r[4] for r in arith)
            lines.append(f"    (max delta: {max_d:,.6f})")
    lines.append("")

    if summary["arithmetic_fail"] == 0:
        lines.append(
            f"  >> ALL {summary['arithmetic_pass']} "
            f"ARITHMETIC CHECKS PASSED <<")
    else:
        lines.append(
            f"  >> {summary['arithmetic_fail']} "
            f"ARITHMETIC CHECK(S) FAILED <<")
    lines.append("")

    # Model design checks
    lines.append("MODEL DESIGN CHECKS (known structural limitations)")
    lines.append("-" * 72)
    for sec, checks in sections.items():
        design = [r for r in checks
                  if classify_check(r[0], r[1]) == "model_design"]
        if not design:
            continue
        fails = [r for r in design if not r[5]]
        status = "ALL PASS" if not fails else f"{len(fails)} known gap(s)"
        lines.append(f"  {sec} ({len(design)} checks, {status})")
        for r in fails:
            lines.append(f"    GAP   {r[1]}: delta {r[4]:>12,.2f}")
    lines.append("")
    lines.append(
        f"  {summary['design_pass']} passed, "
        f"{summary['design_fail']} known gap(s)")
    lines.append("")

    # Summary
    lines.append("=" * 72)
    lines.append("SUMMARY")
    lines.append("=" * 72)
    arith_total = summary["arithmetic_pass"] + summary["arithmetic_fail"]
    design_total = summary["design_pass"] + summary["design_fail"]
    lines.append(f"  Total checks:     {summary['total']}")
    lines.append(
        f"  Arithmetic:       {arith_total:>4} "
        f"({summary['arithmetic_pass']} pass, "
        f"{summary['arithmetic_fail']} fail)")
    lines.append(
        f"  Model design:     {design_total:>4} "
        f"({summary['design_pass']} pass, "
        f"{summary['design_fail']} known gaps)")
    lines.append("")
    if summary["arithmetic_fail"] == 0:
        lines.append("  VERDICT: MODEL IS BALANCED")
    else:
        lines.append("  VERDICT: MODEL HAS ARITHMETIC ERRORS")
    lines.append("=" * 72)

    return "\n".join(lines)
