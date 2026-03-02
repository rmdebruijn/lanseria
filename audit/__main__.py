"""CLI entry: python -m audit"""

from pathlib import Path

from audit.runner import run_all_checks
from audit.report import write_json_report, format_text_report


def main():
    print("Running model...")
    audit_data = run_all_checks()

    # Print text report
    print(format_text_report(audit_data))

    # Write JSON
    output_dir = Path(__file__).resolve().parent.parent / "output"
    json_path = write_json_report(
        audit_data, output_dir / "audit_report.json")
    print(f"\nJSON report written to: {json_path}")


if __name__ == "__main__":
    main()
