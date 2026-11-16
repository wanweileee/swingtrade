"""The flow, wired as a LangGraph StateGraph.

    setup → fetch_data → market_regime → strategy_rules ─┬─(no signal)──────────────┐
                                                          └─(signal) analysts…       │
        technical → fundamentals → news → bull ⇄ bear → research_manager             │
        → trade_plan → risk_check → final_decision ◄──────────────────────────────────┘

Change the order, add or remove steps here. Each step is a plain function
(state) -> dict of new keys, defined in swing_agents/nodes/.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .config import load_config, load_knowledge, load_portfolio
from .data import last_trading_day
from .nodes.analysts import ANALYSTS
from .nodes.data_nodes import fetch_data, market_regime, strategy_rules
from .nodes.debate import bear, bull, more_debate, research_manager
from .nodes.decision import final_decision, risk_check, trade_plan
from .state import FlowState


def setup(state: dict) -> dict:
    """Fills in anything the caller didn't pass, so only {'ticker': 'MSFT'} is required."""
    cfg = state.get("config") or load_config()
    as_of = state.get("as_of") or last_trading_day()
    run_dir = state.get("run_dir") or str(
        Path(cfg["_root"], cfg["output"]["runs_dir"],
             datetime.now().strftime("%Y%m%d-%H%M%S"), state["ticker"].upper()))
    return {"ticker": state["ticker"].upper(), "config": cfg, "as_of": as_of, "run_dir": run_dir,
            "knowledge": state.get("knowledge") or load_knowledge(cfg),
            "portfolio": state.get("portfolio") or load_portfolio(cfg),
            "reports": {}, "debate": []}


def build_graph(cfg: dict | None = None):
    cfg = cfg or load_config()
    analysts = [a for a in cfg["flow"].get("analysts", []) if a in ANALYSTS]

    g = StateGraph(FlowState)
    g.add_node("setup", setup)
    for fn in (fetch_data, market_regime, strategy_rules, bull, bear, research_manager,
               trade_plan, risk_check, final_decision):
        g.add_node(fn.step_name, fn)
    for a in analysts:
        g.add_node(ANALYSTS[a].step_name, ANALYSTS[a])

    g.add_edge(START, "setup")
    g.add_edge("setup", "fetch_data")
    g.add_edge("fetch_data", "market_regime")
    g.add_edge("market_regime", "strategy_rules")

    first_ai = ANALYSTS[analysts[0]].step_name if analysts else "bull"

    def after_rules(state: dict) -> str:
        flow = state["config"]["flow"]
        valid = state["signal"]["signal"] and state["market"]["ok"]
        if flow.get("rules_only"):                     # no AI: rules → plan → hard checks
            return "trade_plan" if valid else "final_decision"
        if flow.get("skip_llm_if_no_signal", True) and not valid:
            return "final_decision"
        return first_ai

    g.add_conditional_edges("strategy_rules", after_rules, [first_ai, "trade_plan", "final_decision"])

    chain = [ANALYSTS[a].step_name for a in analysts] + ["bull"]
    for a, b in zip(chain, chain[1:]):
        g.add_edge(a, b)
    g.add_edge("bull", "bear")
    g.add_conditional_edges("bear", more_debate, ["bull", "research_manager"])
    g.add_edge("research_manager", "trade_plan")
    g.add_edge("trade_plan", "risk_check")
    g.add_edge("risk_check", "final_decision")
    g.add_edge("final_decision", END)
    return g.compile()


# For LangGraph Studio (`langgraph dev`): input {"ticker": "MSFT"}
graph = build_graph()
