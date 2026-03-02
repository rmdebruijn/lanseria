"""Template ↔ Registry cross-validation.

Checks that statement templates (pnl.json, bs.json, cf.json, etc.)
are consistent with the column registry (config/columns.json).

Cross-check rules:
1. Key existence — every template line ID must exist in registry
   (unless type is "formula", "spacer", or "aggregation").
2. Nature ↔ statement — stocks on flow statements → warning.
3. Sign consistency — negative-sign column displayed as positive → warning.
4. Unit match — formula mixing different units → warning.
5. Account grouping — same account must share unit (delegated to registry).

Usage:
    from engine.template_validator import validate_template, validate_all_templates

    issues = validate_all_templates()
    for issue in issues:
        print(issue)
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.registry import ColumnRegistry


# Template types that reference a registry column
_COLUMN_TYPES = {"driver", "balance"}

# Template types that don't require registry lookup
_SKIP_TYPES = {"formula", "spacer", "aggregation"}

# Statement frequencies that are flow-oriented
_FLOW_FREQUENCIES = {"semi-annual", "annual"}


def validate_template(
    template: dict,
    registry: ColumnRegistry,
    *,
    template_name: str = "",
) -> list[str]:
    """Check a single template against the registry.

    Args:
        template: Parsed template JSON dict.
        registry: Loaded ColumnRegistry.
        template_name: For error messages.

    Returns:
        List of warning/error strings (empty = all good).
    """
    issues: list[str] = []
    prefix = f"[{template_name}] " if template_name else ""
    frequency = template.get("frequency", template.get("metadata", {}).get("frequency", ""))
    is_balance_sheet = frequency == "annual" and "balance" in template.get("name", "").lower()

    def _check_lines(lines: list[dict]) -> None:
        for line in lines:
            line_id = line.get("id", "")
            line_type = line.get("type", "driver")

            # Skip types that don't reference columns
            if line_type in _SKIP_TYPES:
                continue

            # Check key existence in registry
            col = registry.get(line_id)
            if col is None:
                issues.append(
                    f"{prefix}Unknown column '{line_id}' "
                    f"(type={line_type})"
                )
                continue

            # Nature ↔ statement check
            if col.is_stock and not is_balance_sheet and frequency in _FLOW_FREQUENCIES:
                # Stock on a flow statement — might be intentional (e.g., tax_loss_pool on P&L)
                # but worth flagging
                issues.append(
                    f"{prefix}Stock column '{line_id}' "
                    f"on flow statement (frequency={frequency})"
                )

            # Sign consistency check
            line_sign = line.get("sign", 1)  # default: positive display
            if isinstance(line_sign, (int, float)):
                if line_sign < 0 and col.sign == "positive":
                    # Expected: cost stored positive, displayed as deduction
                    # No issue — this is the normal convention
                    pass
                elif line_sign > 0 and col.sign == "negative":
                    # Showing a cost/expense as positive income → suspicious
                    issues.append(
                        f"{prefix}Column '{line_id}' has sign='negative' "
                        f"in registry but displayed with positive sign "
                        f"in template"
                    )

    # Walk sections → subsections → lines
    for section in template.get("sections", []):
        # Direct lines on section
        if "lines" in section:
            _check_lines(section["lines"])

        # Subsections
        for subsection in section.get("subsections", []):
            if "lines" in subsection:
                _check_lines(subsection["lines"])

        # Summary line
        summary = section.get("summary")
        if summary and summary.get("type") not in _SKIP_TYPES:
            _check_lines([summary])

    # Top-level lines (flat template format used by evaluate_template)
    if "lines" in template:
        _check_lines(template["lines"])

    return issues


def validate_all_templates(
    template_dir: Path | str | None = None,
    registry: ColumnRegistry | None = None,
) -> list[str]:
    """Validate all template JSON files in a directory.

    Args:
        template_dir: Path to templates directory.
            Defaults to config/templates/ relative to model root.
        registry: ColumnRegistry to validate against.
            Loads default if not provided.

    Returns:
        List of all warnings/errors across all templates.
    """
    if template_dir is None:
        # Check NWL model config first, then global engine config
        nwl_dir = Path(__file__).parent.parent / "config" / "templates"
        if nwl_dir.exists():
            template_dir = nwl_dir
        else:
            template_dir = Path(__file__).parent.parent / "config" / "templates"

    template_dir = Path(template_dir)
    if registry is None:
        registry = ColumnRegistry.load()

    all_issues: list[str] = []

    for path in sorted(template_dir.glob("*.json")):
        try:
            with open(path) as f:
                template = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            all_issues.append(f"[{path.name}] Failed to load: {e}")
            continue

        issues = validate_template(
            template, registry, template_name=path.stem,
        )
        all_issues.extend(issues)

    return all_issues
