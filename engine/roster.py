"""Formula roster — global defaults + per-entity overrides with DAG validation.

The roster is the execution plan for the big loop. It merges:
1. Global formulas (project-agnostic defaults)
2. Infrastructure formulas (project finance primitives)
3. Per-entity overrides (entity-specific formulae that replace globals)

The merged roster is topologically sorted — formulas run in dependency order.
If an entity override creates a cycle, the roster loader rejects it.

Usage:
    roster = load_roster("nwl")
    # roster.execution_order -> ["volume", "price", "revenue", "opex", "ebitda", ...]
    # roster.formulas["revenue"] -> FormulaEntry(expr="q * p * util", depends_on=["q", "p", "util"])
    # roster.resolve("revenue", {"q": 1000, "p": 62.05, "util": 0.8}) -> FormulaRef(...)

See engine/DAG.md for why acyclicity is critical.
"""

from __future__ import annotations

import json
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Safe Expression Evaluator ───────────────────────────────────

_SAFE_NAMES: dict[str, Any] = {"max": max, "min": min, "abs": abs, "round": round, "sum": sum}


def _safe_eval(expr: str, variables: dict[str, float]) -> float:
    """Evaluate a formula string safely (no builtins, no imports)."""
    for banned in ("import", "__", "exec", "eval", "open", "compile", "getattr"):
        if _re.search(r"\b" + _re.escape(banned) + r"\b", expr):
            raise ValueError(f"Disallowed construct in formula: {banned}")
    ns = dict(_SAFE_NAMES)
    ns.update(variables)
    try:
        return float(eval(compile(expr, "<formula>", "eval"), {"__builtins__": {}}, ns))  # noqa: S307
    except ZeroDivisionError:
        return 0.0
    except Exception as e:
        raise ValueError(f"Formula eval failed: {expr!r} -> {e}") from e


# ── FormulaRef — Audit Trail Atom ───────────────────────────────

@dataclass(frozen=True)
class FormulaRef:
    """A resolved formula with inputs and result — the audit trail atom."""
    name: str
    formula: str
    inputs: dict[str, Any]
    result: float
    unit: str = "EUR"
    period: int | None = None

    def tooltip(self) -> str:
        parts = [f"{k}={v:,.2f}" if isinstance(v, (int, float)) else f"{k}={v}"
                 for k, v in self.inputs.items()]
        return f"{self.name} = {self.formula} = {self.result:,.2f} [{', '.join(parts)}]"

    def to_dict(self) -> dict:
        return {"name": self.name, "formula": self.formula, "inputs": self.inputs,
                "result": self.result, "unit": self.unit, "period": self.period}


# ── Formula Entry ───────────────────────────────────────────────

@dataclass(frozen=True)
class FormulaEntry:
    """A single formula in the roster."""
    name: str
    expr: str                          # Evaluable expression, e.g. "q * p"
    depends_on: tuple[str, ...]        # Input variable/formula names
    unit: str = "EUR"                  # Output unit
    description: str = ""              # Human-readable, for UI tooltip
    source: str = "global"             # "global", "infra", or entity key

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "expr": self.expr,
            "depends_on": list(self.depends_on),
            "unit": self.unit,
            "description": self.description,
            "source": self.source,
        }


@dataclass
class Roster:
    """Merged, validated formula roster — ready for execution.

    Attributes:
        formulas: name -> FormulaEntry mapping
        execution_order: topologically sorted formula names
        entity_key: which entity this roster was built for (or "global")
        overrides_applied: which formula names were overridden by entity config
    """
    formulas: dict[str, FormulaEntry]
    execution_order: list[str]
    entity_key: str = "global"
    overrides_applied: list[str] = field(default_factory=list)

    def resolve(
        self,
        name: str,
        inputs: dict[str, float],
        period: int | None = None,
    ):
        """Evaluate a formula with audit trail. Returns FormulaRef."""
        entry = self.formulas[name]
        result = _safe_eval(entry.expr, inputs)
        return FormulaRef(
            name=name,
            formula=entry.expr,
            inputs=dict(inputs),
            result=result,
            unit=entry.unit,
            period=period,
        )

    def resolve_chain(
        self,
        inputs: dict[str, float],
        period: int | None = None,
        names: list[str] | None = None,
    ) -> list:
        """Resolve formulas in execution order, feeding results forward.

        If names is None, resolves ALL formulas in execution_order.
        Returns list of FormulaRef.
        """
        refs = []
        running = dict(inputs)
        resolve_names = names if names is not None else self.execution_order

        for name in resolve_names:
            if name not in self.formulas:
                continue
            entry = self.formulas[name]
            # Only resolve if all dependencies are available
            if all(d in running for d in entry.depends_on):
                result = _safe_eval(entry.expr, running)
                ref = FormulaRef(
                    name=name,
                    formula=entry.expr,
                    inputs={d: running.get(d, 0) for d in entry.depends_on},
                    result=result,
                    unit=entry.unit,
                    period=period,
                )
                refs.append(ref)
                running[name] = result

        return refs

    def dependency_chain(self, name: str) -> list[str]:
        """Walk backward from a formula to its root inputs.

        Returns the dependency chain in resolution order (roots first).
        Used by UI click-to-trace.
        """
        visited = set()
        order = []

        def _walk(n: str):
            if n in visited:
                return
            visited.add(n)
            if n in self.formulas:
                for dep in self.formulas[n].depends_on:
                    _walk(dep)
            order.append(n)

        _walk(name)
        return order


# ── DAG Validation ──────────────────────────────────────────────


class CycleError(ValueError):
    """Raised when formula dependencies form a cycle."""
    pass


def _topological_sort(formulas: dict[str, FormulaEntry]) -> list[str]:
    """Kahn's algorithm for topological sort.

    Returns formula names in execution order (dependencies before dependents).
    Raises CycleError if a cycle is detected.
    """
    # Build adjacency: for each formula, track its in-degree
    # (how many of its dependencies are other formulas in the roster)
    in_degree: dict[str, int] = {}
    dependents: dict[str, list[str]] = {}  # dep -> [formulas that depend on it]

    for name, entry in formulas.items():
        in_degree.setdefault(name, 0)
        for dep in entry.depends_on:
            if dep in formulas:
                # This dependency is another formula (not an external input)
                in_degree[name] = in_degree.get(name, 0) + 1
                dependents.setdefault(dep, []).append(name)

    # Start with formulas that have no formula dependencies
    queue = [n for n, deg in in_degree.items() if deg == 0]
    order: list[str] = []

    while queue:
        # Sort for deterministic order
        queue.sort()
        node = queue.pop(0)
        order.append(node)
        for dependent in dependents.get(node, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(order) != len(formulas):
        # Find the cycle
        remaining = set(formulas.keys()) - set(order)
        raise CycleError(
            f"Formula dependency cycle detected among: {sorted(remaining)}. "
            f"Check depends_on fields for circular references."
        )

    return order


# ── Roster Loading ──────────────────────────────────────────────


# Default global formulas (from engine/formulas.py, expressed as FormulaEntry)
_GLOBAL_FORMULAS: dict[str, FormulaEntry] = {
    "ebitda": FormulaEntry(
        "ebitda", "revenue - opex", ("revenue", "opex"),
        unit="EUR", description="Earnings before interest, tax, depreciation, amortisation",
    ),
    "ebit": FormulaEntry(
        "ebit", "ebitda - depreciation", ("ebitda", "depreciation"),
        unit="EUR", description="Earnings before interest and tax",
    ),
    "pbt": FormulaEntry(
        "pbt", "ebit - interest_expense + fd_income", ("ebit", "interest_expense", "fd_income"),
        unit="EUR", description="Profit before tax",
    ),
    "pat": FormulaEntry(
        "pat", "pbt - tax", ("pbt", "tax"),
        unit="EUR", description="Profit after tax",
    ),
    "cfads": FormulaEntry(
        "cfads", "ebitda - tax", ("ebitda", "tax"),
        unit="EUR", description="Cash flow available for debt service",
    ),
    "debt_service": FormulaEntry(
        "debt_service", "sr_interest + sr_principal + mz_interest + mz_principal",
        ("sr_interest", "sr_principal", "mz_interest", "mz_principal"),
        unit="EUR", description="Total debt service (Sr + Mz interest + principal)",
    ),
    "interest": FormulaEntry(
        "interest", "opening_balance * annual_rate / 2",
        ("opening_balance", "annual_rate"),
        unit="EUR", description="Semi-annual interest on facility balance",
        source="infra",
    ),
    "idc": FormulaEntry(
        "idc", "opening_balance * annual_rate / 2",
        ("opening_balance", "annual_rate"),
        unit="EUR", description="Interest during construction (capitalised)",
        source="infra",
    ),
    "p_constant": FormulaEntry(
        "p_constant", "opening_balance / remaining_periods",
        ("opening_balance", "remaining_periods"),
        unit="EUR", description="Equal principal repayment per period",
        source="infra",
    ),
    "depreciation_s12c": FormulaEntry(
        "depreciation_s12c", "depreciable_base * s12c_rate",
        ("depreciable_base", "s12c_rate"),
        unit="EUR", description="Section 12C accelerated depreciation (40/20/20/20)",
        source="infra",
    ),
}


def _load_entity_overrides(entity_key: str) -> dict[str, FormulaEntry]:
    """Load per-entity formula overrides from JSON.

    Looks for: config/formulas/{entity_key}.json
    Returns empty dict if file doesn't exist (no overrides).
    """
    config_dir = Path(__file__).resolve().parent.parent / "config" / "formulas"
    path = config_dir / f"{entity_key}.json"

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    overrides: dict[str, FormulaEntry] = {}
    for name, spec in data.get("formulas", {}).items():
        overrides[name] = FormulaEntry(
            name=name,
            expr=spec["expr"],
            depends_on=tuple(spec.get("depends_on", [])),
            unit=spec.get("unit", "EUR"),
            description=spec.get("description", ""),
            source=entity_key,
        )

    return overrides


def load_roster(entity_key: str = "global") -> Roster:
    """Load and validate a formula roster for an entity.

    1. Start with global defaults
    2. Apply entity-specific overrides (replace by name)
    3. Topological sort (validates no cycles)
    4. Return ready-to-execute Roster

    Raises CycleError if entity overrides introduce a dependency cycle.
    """
    # Start with global defaults
    merged = dict(_GLOBAL_FORMULAS)

    # Apply entity overrides
    overrides = {}
    if entity_key != "global":
        overrides = _load_entity_overrides(entity_key)
        merged.update(overrides)

    # Validate DAG and get execution order
    execution_order = _topological_sort(merged)

    return Roster(
        formulas=merged,
        execution_order=execution_order,
        entity_key=entity_key,
        overrides_applied=list(overrides.keys()),
    )


# ── Entity Config Loading ───────────────────────────────────────


def load_entity_config(entity_key: str) -> dict:
    """Load per-entity assumptions from config/entities/{entity_key}.json.

    Returns the full config dict. Entity builders read variables from this
    instead of hardcoding values.

    Returns empty dict if the entity config file doesn't exist.
    """
    config_dir = Path(__file__).resolve().parent.parent / "config" / "entities"
    path = config_dir / f"{entity_key}.json"

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    # Strip metadata
    return {k: v for k, v in data.items() if not k.startswith("_")}


def get_entity_var(
    entity_cfg: dict,
    *keys: str,
    default: Any = None,
) -> Any:
    """Drill into nested entity config with a fallback default.

    Usage: get_entity_var(cfg, "operations", "greenfield", "growth_pct", default=7.7)
    """
    node = entity_cfg
    for k in keys:
        if isinstance(node, dict) and k in node:
            node = node[k]
        else:
            return default
    return node
