"""Load config.yaml, portfolio.yaml and the knowledge notes."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["_root"] = str(ROOT)
    return cfg


def load_portfolio(cfg: dict) -> dict:
    path = ROOT / cfg.get("portfolio_file", "portfolio.yaml")
    if not path.exists():
        return {"positions": []}
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("positions", [])
    return data


def load_knowledge(cfg: dict) -> str:
    """Concatenate the knowledge files listed in config into one text block."""
    parts = []
    for name in cfg.get("knowledge", {}).get("files", []):
        p = ROOT / "knowledge" / name
        if p.exists():
            parts.append(f"### {name}\n{p.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) or "(no knowledge notes)"


def account_usd(cfg: dict) -> float:
    a = cfg["account"]
    return round(a["capital_sgd"] * a["usd_per_sgd"], 2)
