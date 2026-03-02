"""Scenario runner + sensitivity sweep engine.

Single scenario: change ScenarioInputs → re-run DAG → get result.
Sensitivity sweep: run DAG N times with systematic variable changes → DataFrame.

The DAG is fast (single-pass, no convergence), so running 50+ scenarios
in a sweep is feasible for interactive tornado charts.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.config import ModelConfig, ScenarioInputs
from engine.analytics import extract_metrics, EntityMetrics


@dataclass
class SweepVariable:
    """A variable to sweep in sensitivity analysis.

    attr: ScenarioInputs attribute name (e.g. "nwl_greenfield_growth_pct")
    base: Base case value (e.g. 7.7)
    low: Low end of sweep range (e.g. 3.0)
    high: High end of sweep range (e.g. 12.0)
    steps: Number of steps (e.g. 9 → values at 3.0, 4.125, ..., 12.0)
    label: Human-readable label for charts (e.g. "NWL Growth %")
    """
    attr: str
    base: float
    low: float
    high: float
    steps: int = 9
    label: str = ""

    @property
    def values(self) -> list[float]:
        """Generate sweep values from low to high."""
        if self.steps <= 1:
            return [self.base]
        step_size = (self.high - self.low) / (self.steps - 1)
        return [self.low + i * step_size for i in range(self.steps)]


@dataclass
class SweepResult:
    """Result of a sensitivity sweep.

    Each row = one scenario run.
    rows[i] = {varied_inputs... + metrics...}
    """
    variable: SweepVariable
    entity_key: str
    rows: list[dict] = field(default_factory=list)

    @property
    def dataframe(self):
        """Convert to pandas DataFrame. Lazy import."""
        import pandas as pd
        return pd.DataFrame(self.rows)


def run_sweep(
    variable: SweepVariable,
    entity_key: str = "nwl",
    cfg: ModelConfig | None = None,
    base_inputs: ScenarioInputs | None = None,
    discount_rate: float = 0.052,
) -> SweepResult:
    """Run a single-variable sensitivity sweep.

    For each value in variable.values:
        1. Clone base_inputs
        2. Set the variable to the sweep value
        3. Run the full model
        4. Extract metrics for the specified entity
        5. Collect as a row

    Returns SweepResult with one row per scenario.
    """
    from engine.orchestrator import run_model

    if cfg is None:
        cfg = ModelConfig.load()
    if base_inputs is None:
        base_inputs = ScenarioInputs.defaults()

    result = SweepResult(variable=variable, entity_key=entity_key)

    for val in variable.values:
        # Clone inputs and set the sweep variable
        inputs = copy.copy(base_inputs)
        setattr(inputs, variable.attr, val)

        # Run the model
        model_result = run_model(cfg, inputs)

        # Extract metrics
        er = model_result.entities[entity_key]
        metrics = extract_metrics(entity_key, er.annual, discount_rate)

        # Build row
        row = {variable.attr: val, "is_base": abs(val - variable.base) < 1e-10}
        row.update(metrics.to_dict())
        result.rows.append(row)

    return result


def run_multi_sweep(
    variables: list[SweepVariable],
    entity_key: str = "nwl",
    cfg: ModelConfig | None = None,
    base_inputs: ScenarioInputs | None = None,
    discount_rate: float = 0.052,
) -> list[SweepResult]:
    """Run sweeps for multiple variables (one at a time, not grid).

    Returns one SweepResult per variable.
    Used for tornado charts: each variable swept independently.
    """
    if cfg is None:
        cfg = ModelConfig.load()
    if base_inputs is None:
        base_inputs = ScenarioInputs.defaults()

    return [
        run_sweep(v, entity_key, cfg, base_inputs, discount_rate)
        for v in variables
    ]


# ── Common Sweep Presets ────────────────────────────────────────


NWL_SWEEP_PRESETS: list[SweepVariable] = [
    SweepVariable(
        attr="nwl_greenfield_growth_pct",
        base=7.7, low=3.0, high=12.0, steps=5,
        label="NWL Growth %",
    ),
    SweepVariable(
        attr="nwl_greenfield_sewage_rate_2025",
        base=46.40, low=30.0, high=60.0, steps=5,
        label="Sewage Tariff (ZAR/kL)",
    ),
    SweepVariable(
        attr="nwl_greenfield_water_rate_2025",
        base=62.05, low=40.0, high=80.0, steps=5,
        label="Water Tariff (ZAR/kL)",
    ),
    SweepVariable(
        attr="nwl_greenfield_reuse_ratio",
        base=0.80, low=0.50, high=1.0, steps=5,
        label="Reuse Ratio",
    ),
    SweepVariable(
        attr="nwl_cash_sweep_pct",
        base=100.0, low=50.0, high=100.0, steps=5,
        label="Cash Sweep %",
    ),
]
