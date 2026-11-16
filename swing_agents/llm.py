"""One place that talks to the language model.

ask(role, prompt) sends a prompt and returns text. Every call is logged by the
recorder, so the viewer shows exactly what each agent was asked.

Model names come from config.yaml (llm.quick_model / llm.deep_model) in the
form "provider:model", e.g. "anthropic:claude-sonnet-4-5" or "openai:gpt-4o-mini".
API keys are read from environment variables (.env): ANTHROPIC_API_KEY,
OPENAI_API_KEY ...  Set the model to "offline" to run with no key at all.
"""
from __future__ import annotations

import re
import time
from functools import lru_cache

from .recorder import log_llm_call

VERDICT_RE = re.compile(r"VERDICT:\s*([A-Z_]+)")


@lru_cache(maxsize=8)
def _client(model: str, temperature: float, max_tokens: int):
    from langchain.chat_models import init_chat_model
    return init_chat_model(model, temperature=temperature, max_tokens=max_tokens)


def ask(cfg: dict, prompt: str, deep: bool = False) -> str:
    llm_cfg = cfg["llm"]
    model = llm_cfg["deep_model" if deep else "quick_model"]
    t0 = time.time()
    if model == "offline":
        text = _offline_answer(prompt)
    else:
        resp = _client(model, llm_cfg.get("temperature", 0.2), llm_cfg.get("max_tokens", 1200)).invoke(prompt)
        text = resp.content if isinstance(resp.content, str) else "".join(
            b.get("text", "") for b in resp.content if isinstance(b, dict))
    log_llm_call(model, prompt, text, time.time() - t0)
    return text


def parse_verdict(text: str, allowed: tuple[str, ...], default: str) -> str:
    """Read the last 'VERDICT: X' line an agent wrote."""
    found = VERDICT_RE.findall(text or "")
    for v in reversed(found):
        if v in allowed:
            return v
    return default


def _offline_answer(prompt: str) -> str:
    """Stub answer so the whole flow can be tested without an API key."""
    role = re.search(r"^You are (?:the |a |an )?([^.\n]+)", prompt, re.M)
    role = role.group(1) if role else "agent"
    signal = "SIGNAL: YES" in prompt
    lines = [f"[offline stub — {role}]",
             "This text is a placeholder. Set llm.quick_model / deep_model in config.yaml "
             "to a real model to get actual analysis.",
             f"Strategy signal seen in prompt: {'YES' if signal else 'NO'}."]
    if "VERDICT: APPROVE" in prompt:       # risk reviewer format
        lines.append("VERDICT: APPROVE")
    elif "VERDICT: TAKE" in prompt:        # research manager format
        lines.append("VERDICT: " + ("TAKE" if signal else "SKIP"))
    return "\n".join(lines)
