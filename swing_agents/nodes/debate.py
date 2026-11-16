"""Bull vs Bear debate, then the Research Manager judges it."""
from __future__ import annotations

from ..llm import ask, parse_verdict
from ..prompts import render
from ..recorder import step


def _reports(state: dict) -> str:
    r = state.get("reports") or {}
    return "\n\n".join(f"### {k.title()} report\n{v}" for k, v in r.items()) or "(no reports)"


def _debate(state: dict) -> str:
    d = state.get("debate") or []
    return "\n\n".join(f"{x['speaker']}: {x['text']}" for x in d) or "(debate not started)"


@step("bull", "Bull researcher (AI)", reads=["reports", "debate"])
def bull(state: dict) -> dict:
    """Argues for the trade, answering the Bear."""
    text = ask(state["config"], render("bull", "the Bull Researcher", state,
                                       reports=_reports(state), debate=_debate(state)))
    return {"debate": (state.get("debate") or []) + [{"speaker": "Bull", "text": text}]}


@step("bear", "Bear researcher (AI)", reads=["reports", "debate"])
def bear(state: dict) -> dict:
    """Argues against the trade, answering the Bull."""
    text = ask(state["config"], render("bear", "the Bear Researcher", state,
                                       reports=_reports(state), debate=_debate(state)))
    return {"debate": (state.get("debate") or []) + [{"speaker": "Bear", "text": text}]}


@step("research_manager", "Research manager verdict (AI)", reads=["reports", "debate", "signal"])
def research_manager(state: dict) -> dict:
    """Judges the debate against the written rules: TAKE, WAIT or SKIP."""
    text = ask(state["config"], render("research_manager", "the Research Manager", state,
                                       reports=_reports(state), debate=_debate(state)), deep=True)
    return {"research": {"verdict": parse_verdict(text, ("TAKE", "WAIT", "SKIP"), "WAIT"), "text": text}}


def more_debate(state: dict) -> str:
    """Router after each Bear turn: another round, or on to the judge."""
    rounds = state["config"]["flow"].get("debate_rounds", 1)
    bear_turns = sum(1 for x in state.get("debate") or [] if x["speaker"] == "Bear")
    return "bull" if bear_turns < rounds else "research_manager"
