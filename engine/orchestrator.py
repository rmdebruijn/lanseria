"""Model orchestrator — entity execution + inter-company correction plugins.

Architecture:
    PASS 1: All entities run independently (no IC).
            LanRED and TWX could run in parallel; NWL needs LanRED deficit.
    PASS 2: IC correction plugins patch specific cross-entity items.
            Currently: NWL ↔ LanRED overdraft.
    PASS 3: SCLCA aggregation.

IC plugins are functions that:
    1. Read outputs from 2+ entity results
    2. Patch specific waterfall/reserve fields
    3. Re-run ONLY affected entity if material changes found
    4. Return patched results

See engine/DAG.md for why this is a forward pass, not a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from engine.config import ModelConfig, ScenarioInputs
from engine.types import EntityResult, ModelResult


# ── IC Plugin Protocol ──────────────────────────────────────────


@dataclass
class ICCorrection:
    """Result of an IC correction plugin."""
    name: str
    entities_patched: list[str]   # Which entity keys were modified
    material: bool                # Whether changes were material (> EUR 1)
    details: dict | None = None   # Plugin-specific diagnostic info


ICPlugin = Callable[
    [dict[str, EntityResult], ModelConfig, ScenarioInputs],
    tuple[dict[str, EntityResult], ICCorrection],
]


# ── IC Plugin: NWL ↔ LanRED Overdraft ──────────────────────────


def ic_nwl_lanred_overdraft(
    entities: dict[str, EntityResult],
    cfg: ModelConfig,
    inputs: ScenarioInputs,
) -> tuple[dict[str, EntityResult], ICCorrection]:
    """NWL-LanRED overdraft correction.

    1. Extract LanRED deficit vector from baseline waterfall
    2. Re-run NWL with deficit vector (NWL lends OD to LanRED)
    3. Extract NWL OD lent vector
    4. Re-run LanRED with OD received (if material)

    This is the cross-entity OD flow:
        LanRED deficit → NWL lends → LanRED receives → LanRED repays over time
    """
    # Extract LanRED deficit vector from baseline run
    lr_baseline = entities["lanred"]
    deficit_vector = [
        row.get("deficit", 0.0)
        for row in lr_baseline.waterfall_semi
    ]

    total_deficit = sum(abs(d) for d in deficit_vector)
    if total_deficit < 1.0:
        # No material deficit — skip IC correction
        return entities, ICCorrection(
            name="nwl_lanred_od",
            entities_patched=[],
            material=False,
            details={"total_deficit": total_deficit},
        )

    # Re-run NWL with LanRED deficit vector
    inputs._lanred_deficit_vector = deficit_vector
    nwl_result = _run_entity("nwl", cfg, inputs)

    # Extract OD lent from NWL waterfall
    od_lent_vector = [
        row.get("od_lent", 0.0)
        for row in nwl_result.waterfall_semi
    ]
    total_od_lent = sum(od_lent_vector)

    entities_patched = ["nwl"]

    if total_od_lent > 1.0:
        # Material OD lending — re-run LanRED with OD received
        inputs._nwl_od_lent_vector = od_lent_vector
        lr_result = _run_entity("lanred", cfg, inputs)
        entities["lanred"] = lr_result
        entities_patched.append("lanred")

    entities["nwl"] = nwl_result

    return entities, ICCorrection(
        name="nwl_lanred_od",
        entities_patched=entities_patched,
        material=True,
        details={
            "total_deficit": total_deficit,
            "total_od_lent": total_od_lent,
        },
    )


# ── IC Plugin Registry ──────────────────────────────────────────


# Add new IC plugins here. Order matters — they run sequentially.
IC_PLUGINS: list[ICPlugin] = [
    ic_nwl_lanred_overdraft,
    # Future: ic_nwl_ca_guarantee, ic_swap_cross_entity, etc.
]


# ── Entity Runner ───────────────────────────────────────────────


def _run_entity(
    entity_key: str,
    cfg: ModelConfig,
    inputs: ScenarioInputs,
) -> EntityResult:
    """Run a single entity through the full pipeline."""
    if entity_key == "nwl":
        from entities.nwl import build_nwl_entity
        return build_nwl_entity(cfg, inputs)
    elif entity_key == "lanred":
        from entities.lanred import build_lanred_entity
        return build_lanred_entity(cfg, inputs)
    elif entity_key == "timberworx":
        from entities.timberworx import build_twx_entity
        return build_twx_entity(cfg, inputs)
    else:
        raise ValueError(f"Unknown entity: {entity_key}")


# ── Model Orchestrator ──────────────────────────────────────────


def run_model(
    cfg: ModelConfig | None = None,
    inputs: ScenarioInputs | None = None,
) -> ModelResult:
    """Orchestrate the full model.

    PASS 1: Run all entities independently (no IC).
    PASS 2: Run IC correction plugins (sequential, plugin order).
    PASS 3: SCLCA aggregation.
    """
    if cfg is None:
        cfg = ModelConfig.load()
    if inputs is None:
        inputs = ScenarioInputs.defaults()

    # ═══ PASS 1: All entities independently ═══
    # LanRED and TWX have no dependencies on each other.
    # NWL baseline also runs without IC (deficit vector applied in PASS 2).
    entities: dict[str, EntityResult] = {}
    for key in ["lanred", "timberworx", "nwl"]:
        entities[key] = _run_entity(key, cfg, inputs)

    # ═══ PASS 2: IC correction plugins ═══
    corrections: list[ICCorrection] = []
    for plugin in IC_PLUGINS:
        entities, correction = plugin(entities, cfg, inputs)
        corrections.append(correction)

    # ═══ PASS 3: SCLCA aggregation ═══
    from entities.sclca import build_sclca_holding
    holding = build_sclca_holding(entities, cfg)

    result = ModelResult(
        entities=entities,
        holding=holding,
        ic_semi=holding.get("ic_semi"),
    )

    # Attach IC correction diagnostics (for debugging / UI)
    result._ic_corrections = corrections

    return result


# Backward-compat aliases
run_entity = _run_entity
