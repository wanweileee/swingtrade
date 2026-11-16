"""Position sizing and hard risk rules. Pure code, no AI: the AI can never
override anything in here. Change limits in config.yaml → account.
"""
from __future__ import annotations

import math

from .config import account_usd


def size_position(entry: float, stop: float, cfg: dict) -> dict:
    a = cfg["account"]
    equity = account_usd(cfg)
    risk_usd = equity * a["risk_pct"] / 100
    per_share = entry - stop
    if per_share <= 0:
        return {"error": "stop is not below entry"}
    shares = risk_usd / per_share
    cap_usd = equity * a["max_position_pct"] / 100
    capped = False
    if shares * entry > cap_usd:
        shares, capped = cap_usd / entry, True
    if not a.get("allow_fractional", True):
        shares = math.floor(shares)
    shares = round(shares, 4)
    return {
        "account_usd": equity,
        "risk_budget_usd": round(risk_usd, 2),
        "risk_per_share": round(per_share, 2),
        "shares": shares,
        "position_usd": round(shares * entry, 2),
        "actual_risk_usd": round(shares * per_share, 2),
        "stop_pct_below_entry": round(per_share / entry * 100, 2),
        "capped_by_max_position": capped,
        "needs_fractional": shares < 1 or shares != int(shares),
        "target_1R": round(entry + per_share, 2),
        "target_2R": round(entry + 2 * per_share, 2),
    }


def hard_checks(state: dict) -> list[dict]:
    """Rules that must all pass. Each returns name, passed, detail."""
    cfg = state["config"]
    a = cfg["account"]
    pf = state.get("portfolio", {}) or {}
    positions = pf.get("positions", []) or []
    sector = (state.get("fundamentals") or {}).get("sector", "Unknown")
    plan = state.get("plan", {})
    earn = state.get("earnings", {})
    out = []

    def add(name, passed, detail):
        out.append({"name": name, "passed": bool(passed), "detail": detail})

    add("Strategy signal", state["signal"]["signal"],
        f"{state['signal']['checks_passed']}/{state['signal']['checks_total']} rules passed")
    add("Market filter", state["market"]["ok"], state["market"]["detail"])

    days = earn.get("days_away")
    if days is None:
        add("Earnings clear", False, "earnings date unknown — check manually before trading")
    else:
        add("Earnings clear", days > a["earnings_blackout_days"] or days < 0,
            f"next earnings {earn.get('next_date')} ({days} days; blackout {a['earnings_blackout_days']})")

    tickers = [p.get("ticker") for p in positions]
    add("Not already held", state["ticker"] not in tickers, f"open: {tickers or 'none'}")
    add("Position slots", len(positions) < a["max_positions"], f"{len(positions)}/{a['max_positions']} used")
    same = sum(1 for p in positions if p.get("sector") == sector)
    add("Sector limit", same < a["max_per_sector"], f"{same} open in {sector} (max {a['max_per_sector']})")

    peak, eq = pf.get("peak_equity_sgd"), pf.get("equity_sgd")
    if peak and eq:
        dd = (1 - eq / peak) * 100
        add("Drawdown", dd < a["drawdown_pause_pct"], f"{dd:.1f}% from peak (pause at {a['drawdown_pause_pct']}%)")

    if "error" in plan:
        add("Valid sizing", False, plan["error"])
    else:
        add("Valid sizing", plan.get("shares", 0) > 0,
            f"{plan.get('shares')} sh, ${plan.get('position_usd')} position, ${plan.get('actual_risk_usd')} at risk")
        if not a.get("allow_fractional", True):
            add("Whole shares affordable", plan.get("shares", 0) >= 1, "fractional shares disabled in config")
    return out
