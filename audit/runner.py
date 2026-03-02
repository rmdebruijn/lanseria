"""Audit runner -- orchestrates all checks against engine output."""

from __future__ import annotations

from engine.config import ModelConfig, ScenarioInputs
from engine.convergence import run_model
from engine.types import ModelResult
from audit.checks import (
    check_entity_pnl,
    check_entity_cf,
    check_entity_bs,
    check_entity_facility,
    check_entity_waterfall_consistency,
    check_sclca,
    check_ic_reconciliation,
    classify_check,
)


def run_all_checks(
    result: ModelResult | None = None,
    cfg: ModelConfig | None = None,
    inputs: ScenarioInputs | None = None,
) -> dict:
    """Run all audit checks. If result is None, runs the model first.

    Returns dict with:
        results: list of (section, name, expected, actual, delta, passed)
        summary: dict with counts
        model_result: the ModelResult used
    """
    if result is None:
        if cfg is None:
            cfg = ModelConfig.load()
        if inputs is None:
            inputs = ScenarioInputs.defaults()
        result = run_model(cfg, inputs)

    all_results: list[tuple] = []

    # Per-entity checks
    for entity_key, er in result.entities.items():
        all_results.extend(check_entity_pnl(entity_key, er.annual))
        all_results.extend(check_entity_cf(entity_key, er.annual))
        all_results.extend(check_entity_bs(
            entity_key, er.annual, er.depreciable_base))
        all_results.extend(check_entity_facility(
            entity_key, er.sr_schedule, er.mz_schedule,
            er.waterfall_semi, er.annual))
        all_results.extend(check_entity_waterfall_consistency(
            entity_key, er.annual, er.waterfall_semi))

    # SCLCA holding company
    if result.holding:
        all_results.extend(check_sclca(result.holding, result.entities))
        all_results.extend(check_ic_reconciliation(
            result.holding, result.entities))

    # Summary
    arith = [r for r in all_results
             if classify_check(r[0], r[1]) == "arithmetic"]
    design = [r for r in all_results
              if classify_check(r[0], r[1]) == "model_design"]

    return {
        "results": all_results,
        "summary": {
            "total": len(all_results),
            "arithmetic_pass": sum(1 for r in arith if r[5]),
            "arithmetic_fail": sum(1 for r in arith if not r[5]),
            "design_pass": sum(1 for r in design if r[5]),
            "design_fail": sum(1 for r in design if not r[5]),
        },
        "model_result": result,
    }
