"""Column registry — single source of truth for all DataFrame column metadata.

Loads config/columns.json and provides typed access to column definitions.
Cross-validates against the engine's runtime metadata (stock keys, template
line IDs, ops table ColDefs) to catch mismatches at startup.

Usage:
    from engine.registry import ColumnRegistry, validate_model_metadata

    registry = ColumnRegistry.load()
    col = registry.get("opco_dsra_bal")
    # col.nature == "stock", col.unit == "EUR", col.family == "reserve"

    # Cross-check against engine's waterfall stock keys
    mismatches = registry.validate_against_stock_keys(_WATERFALL_STOCK_KEYS)
    assert not mismatches, f"Stock key mismatches: {mismatches}"

    # Run ALL cross-checks at once
    issues = validate_model_metadata()
    # issues is a list of strings — empty means all layers agree
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# ── ColumnDef ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ColumnDef:
    """Metadata for a single column across all DataFrames."""
    key: str
    label: str
    nature: str       # "flow" | "stock" | "parameter"
    unit: str         # EUR, ZAR, MLD, m3, kWh, %, x, bool, etc.
    sign: str         # "positive" | "negative" | "neutral"
    family: str       # accounting family
    account: str = "" # parent account for grouping (empty = standalone)
    fmt: str = ""     # format hint: money, money_zar, volume, pct, int, ratio
    entity: tuple[str, ...] = ()  # empty = all entities

    @property
    def is_stock(self) -> bool:
        return self.nature == "stock"

    @property
    def is_flow(self) -> bool:
        return self.nature == "flow"

    @property
    def is_parameter(self) -> bool:
        return self.nature == "parameter"


# ── ColumnRegistry ───────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "columns.json"

# Module-level singleton
_registry: ColumnRegistry | None = None


class ColumnRegistry:
    """Loaded from config/columns.json. Provides typed lookup and validation."""

    __slots__ = ("_columns", "_stock_keys", "_flow_keys",
                 "_by_family", "_by_account")

    def __init__(self, columns: dict[str, ColumnDef]) -> None:
        self._columns = columns

        # Pre-compute indices
        self._stock_keys = frozenset(
            k for k, c in columns.items() if c.is_stock
        )
        self._flow_keys = frozenset(
            k for k, c in columns.items() if c.is_flow
        )
        self._by_family: dict[str, list[ColumnDef]] = {}
        self._by_account: dict[str, list[ColumnDef]] = {}
        for c in columns.values():
            self._by_family.setdefault(c.family, []).append(c)
            if c.account:
                self._by_account.setdefault(c.account, []).append(c)

    # ── Factory ──

    @classmethod
    def load(cls, path: Path | str | None = None) -> ColumnRegistry:
        """Load from JSON file. Returns cached singleton if already loaded."""
        global _registry
        if _registry is not None and path is None:
            return _registry

        if path is None:
            path = _CONFIG_PATH
        path = Path(path)

        with open(path) as f:
            raw = json.load(f)

        columns: dict[str, ColumnDef] = {}
        for key, entry in raw.items():
            if key.startswith("_"):
                continue  # skip _meta
            entity_raw = entry.get("entity", [])
            columns[key] = ColumnDef(
                key=key,
                label=entry["label"],
                nature=entry["nature"],
                unit=entry.get("unit", ""),
                sign=entry.get("sign", "neutral"),
                family=entry["family"],
                account=entry.get("account", ""),
                fmt=entry.get("fmt", ""),
                entity=tuple(entity_raw) if entity_raw else (),
            )

        registry = cls(columns)
        if path == _CONFIG_PATH:
            _registry = registry  # cache default path only
        return registry

    @classmethod
    def reset(cls) -> None:
        """Clear the cached singleton (for testing)."""
        global _registry
        _registry = None

    # ── Lookups ──

    def get(self, key: str) -> ColumnDef | None:
        """Look up a column definition by key. Returns None if unknown."""
        return self._columns.get(key)

    def __getitem__(self, key: str) -> ColumnDef:
        """Look up a column definition by key. Raises KeyError if unknown."""
        return self._columns[key]

    def __contains__(self, key: str) -> bool:
        return key in self._columns

    def __len__(self) -> int:
        return len(self._columns)

    def __iter__(self) -> Iterator[str]:
        return iter(self._columns)

    def keys(self) -> frozenset[str]:
        """All registered column keys."""
        return frozenset(self._columns.keys())

    def values(self) -> list[ColumnDef]:
        """All ColumnDef objects."""
        return list(self._columns.values())

    def stock_keys(self) -> frozenset[str]:
        """All keys with nature == 'stock'."""
        return self._stock_keys

    def flow_keys(self) -> frozenset[str]:
        """All keys with nature == 'flow'."""
        return self._flow_keys

    def by_family(self, family: str) -> list[ColumnDef]:
        """All columns in a given accounting family."""
        return self._by_family.get(family, [])

    def by_account(self, account: str) -> list[ColumnDef]:
        """All columns sharing a parent account."""
        return self._by_account.get(account, [])

    def for_entity(self, entity_key: str) -> list[ColumnDef]:
        """Columns applicable to a specific entity (or to all entities)."""
        return [
            c for c in self._columns.values()
            if not c.entity or entity_key in c.entity
        ]

    # ── Cross-Validation ──

    def validate_against_stock_keys(
        self, stock_keys: frozenset[str] | set[str],
        *,
        label: str = "",
    ) -> list[str]:
        """Check that engine stock keys match registry nature.

        Forward check only: every key in stock_keys must have nature="stock"
        in the registry. If a key is in stock_keys but the registry says
        it's a flow or parameter, that's a real mismatch (error).

        The reverse check (registry stocks not in engine stock_keys) is NOT
        done here because different frozensets cover different namespaces
        (waterfall vs PnL vs facility). Use validate_completeness() for that.

        Args:
            stock_keys: frozenset from engine code (_WATERFALL_STOCK_KEYS etc.)
            label: Name for error messages (e.g. "waterfall")

        Returns:
            List of mismatch descriptions (empty = all good).
        """
        prefix = f"[{label}] " if label else ""
        issues: list[str] = []
        for key in sorted(stock_keys):
            col = self.get(key)
            if col is None:
                issues.append(f"{prefix}Stock key '{key}' not found in registry")
            elif col.nature != "stock":
                issues.append(
                    f"{prefix}Stock key '{key}' has nature='{col.nature}' "
                    f"in registry (expected 'stock')"
                )
        return issues

    def validate_account_units(self) -> list[str]:
        """Check that all columns in the same account share the same unit.

        Returns list of mismatch descriptions.
        """
        issues: list[str] = []
        for account, cols in self._by_account.items():
            units = {c.unit for c in cols if c.unit}
            if len(units) > 1:
                detail = ", ".join(f"{c.key}={c.unit}" for c in cols)
                issues.append(
                    f"Account '{account}' has mixed units: {detail}"
                )
        return issues

    def validate_schema(self) -> list[str]:
        """Run all internal consistency checks.

        Returns list of issues (empty = all good).
        """
        issues: list[str] = []

        valid_natures = {"flow", "stock", "parameter"}
        valid_signs = {"positive", "negative", "neutral"}

        for col in self._columns.values():
            if col.nature not in valid_natures:
                issues.append(f"'{col.key}': invalid nature '{col.nature}'")
            if col.sign not in valid_signs:
                issues.append(f"'{col.key}': invalid sign '{col.sign}'")

        issues.extend(self.validate_account_units())
        return issues


# ── Startup Validation ───────────────────────────────────────────────


def validate_model_metadata(
    template_dir: str | Path | None = None,
) -> list[str]:
    """Run all cross-layer validation checks.

    This is the single entry point for startup validation. It checks:
    1. Registry internal schema consistency
    2. Stock keys match between code and registry (Layer 1 ↔ Engine)
    3. Template line IDs exist in registry (Layer 2 ↔ Layer 1)

    Args:
        template_dir: Path to template JSONs. If None, tries the global
            engine config/templates/ directory.

    Returns:
        List of all issues found. Empty = all three layers agree.
    """
    issues: list[str] = []

    # 1. Load and validate registry schema
    try:
        registry = ColumnRegistry.load()
    except (FileNotFoundError, OSError) as e:
        return [f"Cannot load column registry: {e}"]

    schema_issues = registry.validate_schema()
    issues.extend(f"[schema] {i}" for i in schema_issues)

    # 2. Cross-check stock keys
    try:
        from engine.loop import (
            _WATERFALL_STOCK_KEYS, _PNL_STOCK_KEYS, _FACILITY_STOCK_KEYS,
        )
        issues.extend(
            registry.validate_against_stock_keys(
                _WATERFALL_STOCK_KEYS, label="waterfall",
            )
        )
        issues.extend(
            registry.validate_against_stock_keys(
                _PNL_STOCK_KEYS, label="pnl",
            )
        )
        issues.extend(
            registry.validate_against_stock_keys(
                _FACILITY_STOCK_KEYS, label="facility",
            )
        )
    except ImportError:
        issues.append("[stock_keys] Cannot import engine.loop — skipping")

    # 3. Cross-check templates
    try:
        from engine.template_validator import validate_all_templates

        if template_dir is None:
            # Try global engine templates
            global_dir = (
                Path(__file__).parent.parent.parent.parent
                / "Linux Documents" / "financial model" / "config" / "templates"
            )
            if global_dir.exists():
                template_dir = global_dir

        if template_dir is not None:
            template_issues = validate_all_templates(
                template_dir=template_dir, registry=registry,
            )
            issues.extend(f"[template] {i}" for i in template_issues)
    except ImportError:
        issues.append("[templates] Cannot import template_validator — skipping")

    return issues
