"""Analyst team. Each analyst gets the shared header (strategy, playbook,
rule result) plus its own data, and writes a short report.

To add an analyst: write a prompt in prompts/<name>.md, add a function here
like the ones below, register it in ANALYSTS, and list it in config.yaml →
flow.analysts.
"""
from __future__ import annotations

import json

from ..llm import ask
from ..prompts import render
from ..recorder import step


def _merge(state: dict, key: str, text: str) -> dict:
    return {"reports": {**(state.get("reports") or {}), key: text}}


@step("technical_analyst", "Technical analyst (AI)", reads=["indicators", "signal", "market"])
def technical_analyst(state: dict) -> dict:
    """Reads the chart numbers and judges if the setup is a clean pullback."""
    df = state["prices"][["Open", "High", "Low", "Close", "Volume"]].tail(10).round(2)
    bars = "\n".join(f"{i.date()}  {r.Open} {r.High} {r.Low} {r.Close} {int(r.Volume):,}"
                     for i, r in df.iterrows())
    prompt = render("technical_analyst", "the Technical Analyst", state,
                    indicators=json.dumps(state["indicators"], indent=1),
                    recent_bars=bars,
                    market_symbol=state["market"]["symbol"],
                    market_detail=state["market"]["detail"],
                    stop=state["signal"].get("stop"))
    return _merge(state, "technical", ask(state["config"], prompt))


@step("fundamentals_analyst", "Fundamentals analyst (AI)", reads=["fundamentals", "earnings"])
def fundamentals_analyst(state: dict) -> dict:
    """Looks for swing-trade risks: earnings gaps, stretched valuation, volatility."""
    prompt = render("fundamentals_analyst", "the Fundamentals Analyst", state,
                    fundamentals=json.dumps(state.get("fundamentals"), indent=1, default=str),
                    earnings=json.dumps(state.get("earnings"), default=str))
    return _merge(state, "fundamentals", ask(state["config"], prompt))


@step("news_analyst", "News analyst (AI)", reads=["news"])
def news_analyst(state: dict) -> dict:
    """Checks recent headlines for events that could gap the stock."""
    news = state.get("news") or []
    lines = "\n".join(f"- {n.get('date', '')} {n.get('publisher') or ''}: {n.get('title')}"
                      + (f" — {n['summary']}" if n.get("summary") else "") for n in news) or "(none)"
    prompt = render("news_analyst", "the News Analyst", state, news=lines)
    return _merge(state, "news", ask(state["config"], prompt))


ANALYSTS = {
    "technical": technical_analyst,
    "fundamentals": fundamentals_analyst,
    "news": news_analyst,
}
