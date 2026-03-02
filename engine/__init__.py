"""Calculation engine — pure Python, zero Streamlit."""


def run_model(*args, **kwargs):
    from engine.convergence import run_model as _run_model
    return _run_model(*args, **kwargs)


def run_entity(*args, **kwargs):
    from engine.convergence import run_entity as _run_entity
    return _run_entity(*args, **kwargs)


__all__ = ["run_entity", "run_model"]
