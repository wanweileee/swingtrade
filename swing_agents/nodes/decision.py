"""Trade plan (code), risk check (code + AI veto), final decision (code).

The final action is decided by plain rules below, so you always know why:
the AI can turn a trade down (WAIT/SKIP/VETO) but can never force one.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import risk as R
from ..llm import ask, parse_verdict
from ..prompts import render
from ..recorder import step

NASDAQ = {"MSFT", "GOOGL", "GOOG", "AAPL", "AMZN", "META", "NVDA", "AVGO", "COST", "NFLX",
          "ADBE", "LIN", "AMD", "INTC", "QCOM", "TSLA", "PEP", "CSCO", "TXN", "AMAT", "QQQ"}


def tv_link(ticker: str) -> str:
    ex = "NASDAQ" if ticker.upper() in NASDAQ else "NYSE"
    return f"https://www.tradingview.com/chart/?symbol={ex}:{ticker.upper()}&interval=D"


@step("trade_plan", "Trade plan & position size (code)", reads=["signal"])
def trade_plan(state: dict) -> dict:
    """Entry and stop come from the strategy; size comes from risk.py
    (account × risk% ÷ distance to stop, capped at max position %)."""
    s = state["signal"]
    plan = {"entry_type": s["entry_type"], "entry": s["entry"], "stop": s["stop"],
            **R.size_position(s["entry"], s["stop"], state["config"])}
    return {"plan": plan}


@step("risk_check", "Risk check: hard rules (code) + reviewer (AI)", reads=["plan", "research", "portfolio"])
def risk_check(state: dict) -> dict:
    """Hard rules from risk.py must all pass. If they do, an AI reviewer may
    still VETO (never enlarge) the trade."""
    checks = R.hard_checks(state)
    passed = all(c["passed"] for c in checks)
    review, veto = "skipped: hard rules failed", False
    if passed and state["config"]["flow"].get("rules_only"):
        review = "skipped: rules-only mode (no AI)"
    elif passed:
        research = state.get("research") or {}
        prompt = render("risk_reviewer", "the Risk Reviewer", state,
                        plan=json.dumps(state["plan"], indent=1),
                        hard_checks="\n".join(f"- [{'x' if c['passed'] else ' '}] {c['name']}: {c['detail']}" for c in checks),
                        research_verdict=research.get("verdict", "n/a"),
                        research_text=research.get("text", ""),
                        positions=json.dumps((state.get("portfolio") or {}).get("positions", []), default=str))
        review = ask(state["config"], prompt, deep=True)
        veto = parse_verdict(review, ("APPROVE", "VETO"), "VETO") == "VETO"
    return {"risk": {"hard_checks": checks, "passed": passed, "review": review, "veto": veto}}


@step("final_decision", "Final decision (code)", reads=["signal", "market", "research", "risk", "plan"])
def final_decision(state: dict) -> dict:
    """BUY = every gate passed. WATCH = valid or nearly valid, wait a week.
    SKIP = a rule or reviewer said no. Reasons list every gate."""
    sig, mkt = state["signal"], state["market"]
    research, risk, plan = state.get("research"), state.get("risk"), state.get("plan")
    reasons, action = [], "BUY"

    if not sig["signal"]:
        failed = [c["name"] for c in sig["checks"] if not c["passed"]]
        near = sig["checks_total"] - sig["checks_passed"] <= 1
        action = "WATCH" if near and mkt["ok"] else "SKIP"
        reasons.append(f"Strategy rules not met ({sig['checks_passed']}/{sig['checks_total']}); failed: {', '.join(failed)}")
    if not mkt["ok"]:
        action = "SKIP"
        reasons.append(f"Market filter RED: {mkt['detail']}")
    if risk and not risk["passed"]:
        action = "SKIP"
        reasons += [f"{c['name']}: {c['detail']}" for c in risk["hard_checks"] if not c["passed"]]
    if research:
        v = research["verdict"]
        reasons.append(f"Research manager: {v}")
        if v == "SKIP":
            action = "SKIP"
        elif v == "WAIT" and action == "BUY":
            action = "WATCH"
    rules_only = state["config"]["flow"].get("rules_only")
    if rules_only and risk and risk["passed"]:
        reasons.append("Rules-only mode: every rule and hard check passed (no AI review)")
    elif risk and risk["passed"]:
        reasons.append("Risk reviewer: " + ("VETO" if risk["veto"] else "APPROVE"))
        if risk["veto"]:
            action = "SKIP"
    if action == "BUY" and not risk:
        action = "WATCH"  # never buy without the full flow having run
        reasons.append("Flow did not run all steps")

    t = state["ticker"]
    lines = [f"# {t} — {action}", f"As of {state['as_of']} close · strategy: {state['strategy']['name']}",
             f"Chart: {tv_link(t)}", ""]
    if action == "BUY" and plan:
        kind = "Buy-stop" if plan["entry_type"] == "buy_stop" else "Buy at open ~"
        lines += ["## Order ticket",
                  f"- {kind} {plan['entry']}  ·  stop-loss {plan['stop']} ({plan['stop_pct_below_entry']}% below)",
                  f"- Size {plan['shares']} shares ≈ ${plan['position_usd']}  ·  risk ${plan['actual_risk_usd']}",
                  f"- +1R at {plan['target_1R']} (move stop to breakeven) · +2R at {plan['target_2R']}",
                  f"- Valid {state['strategy']['params'].get('valid_days', 5)} trading days", ""]
    lines += ["## Why"] + [f"- {r}" for r in reasons]
    summary = "\n".join(lines)
    Path(state["run_dir"], "report.md").write_text(summary + _appendix(state), encoding="utf-8")
    return {"decision": {"action": action, "reasons": reasons, "summary": summary, "chart": tv_link(t)}}


def _appendix(state: dict) -> str:
    out = ["", "", "---", "## Rule checks"]
    out += [f"- [{'x' if c['passed'] else ' '}] {c['name']}: {c['rule']} ({c['value']})" for c in state["signal"]["checks"]]
    for k, v in (state.get("reports") or {}).items():
        out += ["", f"## {k.title()} analyst", v]
    for d in state.get("debate") or []:
        out += ["", f"## {d['speaker']}", d["text"]]
    if state.get("research"):
        out += ["", "## Research manager", state["research"]["text"]]
    if state.get("risk"):
        out += ["", "## Risk review", str(state["risk"]["review"])]
    return "\n".join(out)
