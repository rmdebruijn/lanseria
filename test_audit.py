#!/usr/bin/env python3
"""
Offline Audit: SCLCA Financial Model
-------------------------------------
Runs all audit checks via the engine (no Streamlit mock needed).

Usage: python test_audit.py
"""

import sys
from pathlib import Path

# Ensure model/ is on the path
MODEL_DIR = Path(__file__).parent
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

from audit.runner import run_all_checks
from audit.report import format_text_report, write_json_report


def main():
    print("=" * 72)
    print("SCLCA FINANCIAL MODEL - OFFLINE AUDIT")
    print("=" * 72)
    print()

    print("Running engine model + audit checks...", flush=True)
    audit_data = run_all_checks()
    print()

    # Print text report
    print(format_text_report(audit_data))

    # Write JSON report
    output_dir = MODEL_DIR / "output"
    json_path = write_json_report(audit_data, output_dir / "audit_report.json")
    print(f"\nJSON report written to: {json_path}")

    # Return exit code: 0 if all arithmetic checks pass, 1 otherwise
    summary = audit_data["summary"]
    if summary["arithmetic_fail"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
