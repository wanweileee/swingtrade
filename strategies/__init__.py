"""Strategy loader: config.yaml `strategy: <file name>` picks strategies/<file>.py."""
from __future__ import annotations

import importlib
from pathlib import Path

from .base import Strategy


def load_strategy(name: str, overrides: dict | None = None) -> Strategy:
    module = importlib.import_module(f"strategies.{name}")
    cls = getattr(module, "STRATEGY", None)
    if cls is None:
        raise ValueError(f"strategies/{name}.py must define STRATEGY = <YourClass>")
    return cls(overrides)


def available() -> list[str]:
    here = Path(__file__).parent
    return sorted(p.stem for p in here.glob("*.py") if p.stem not in ("__init__", "base"))
