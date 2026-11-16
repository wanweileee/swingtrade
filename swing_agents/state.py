"""The flow's shared state: every step reads from it and writes new keys to it.

Adding a step? Add the keys it writes here so it's obvious where data lives.
"""
from __future__ import annotations

from typing import Any, TypedDict


class FlowState(TypedDict, total=False):
    # ── inputs ───────────────────────────────────────────────
    ticker: str
    as_of: str                 # YYYY-MM-DD, analysis date (last bar used)
    run_dir: str               # where step outputs are written
    config: dict
    knowledge: str             # text from knowledge/*.md
    portfolio: dict            # portfolio.yaml (open positions, equity)

    # ── 01 fetch_data ────────────────────────────────────────
    prices: Any                # pandas DataFrame (OHLCV), not saved in full
    market_prices: Any
    fundamentals: dict
    earnings: dict             # {"next_date":..., "days_away":...}
    news: list                 # [{"title":..., "publisher":..., "date":...}]

    # ── 02 strategy_rules ────────────────────────────────────
    indicators: dict           # latest values the strategy computed
    strategy: dict             # {"name", "description", "params"}
    signal: dict               # {"signal": bool, "checks": [...], "entry", "stop", ...}

    # ── 03 market_regime ─────────────────────────────────────
    market: dict               # {"ok": bool, "close", "sma200", ...}

    # ── 04-06 analysts ───────────────────────────────────────
    reports: dict              # {"technical": str, "fundamentals": str, "news": str}

    # ── 07-08 debate ─────────────────────────────────────────
    debate: list               # [{"speaker": "Bull", "text": ...}, ...]

    # ── 09 research_manager ──────────────────────────────────
    research: dict             # {"verdict": TAKE|WAIT|SKIP, "text": ...}

    # ── 10 trade_plan ────────────────────────────────────────
    plan: dict                 # entry, stop, shares, risk_usd, position_usd ...

    # ── 11 risk_check ────────────────────────────────────────
    risk: dict                 # {"hard_checks": [...], "passed": bool, "review": str, "veto": bool}

    # ── 12 final_decision ────────────────────────────────────
    decision: dict             # {"action": BUY_STOP|WATCH|SKIP, "reasons": [...], "summary": str}
