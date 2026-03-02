"""Backward-compat shim — real logic lives in engine.orchestrator."""

from engine.orchestrator import run_model, run_entity  # noqa: F401

__all__ = ["run_model", "run_entity"]
