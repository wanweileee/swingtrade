"""Prompt templates live as .md files in this folder so you can edit them
without touching code. {placeholders} are filled by render().
_header.md is shared by every agent (role, strategy, playbook, signal).
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent


class _Safe(dict):
    def __missing__(self, key):  # leave unknown {placeholders} visible
        return "{" + key + "}"


def render(name: str, role: str, state: dict, **extra) -> str:
    sig = state.get("signal", {})
    checks = "\n".join(
        f"  [{'x' if c['passed'] else ' '}] {c['name']}: {c['rule']} ({c['value']})"
        for c in sig.get("checks", []))
    base = _Safe(
        role=role,
        strategy_description=state.get("strategy", {}).get("description", ""),
        knowledge=state.get("knowledge", ""),
        ticker=state["ticker"], as_of=state["as_of"],
        signal_word="YES" if sig.get("signal") else "NO",
        checks_passed=sig.get("checks_passed", 0), checks_total=sig.get("checks_total", 0),
        checks_table=checks,
    )
    header = (HERE / "_header.md").read_text(encoding="utf-8").format_map(base)
    body = (HERE / f"{name}.md").read_text(encoding="utf-8")
    return body.format_map(_Safe({**base, "header": header, **extra}))
