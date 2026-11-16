"""Steps that load data and apply rules. No AI here."""
from __future__ import annotations

from strategies import load_strategy

from .. import data as D
from .. import indicators as ta
from ..recorder import step


@step("fetch_data", "Fetch prices, fundamentals, earnings, news", reads=["ticker", "as_of"])
def fetch_data(state: dict) -> dict:
    """Loads daily OHLCV for the ticker and the market symbol, plus fundamentals,
    next earnings date and recent headlines (see swing_agents/data.py)."""
    cfg, t, as_of = state["config"], state["ticker"], state["as_of"]
    return {
        "prices": D.load_prices(t, as_of, cfg),
        "market_prices": D.load_prices(cfg["data"]["market_symbol"], as_of, cfg),
        "fundamentals": D.load_fundamentals(t, cfg),
        "earnings": D.load_earnings(t, as_of, cfg),
        "news": D.load_news(t, cfg),
    }


@step("market_regime", "Market filter (SPY vs 200-day)", reads=["market_prices"])
def market_regime(state: dict) -> dict:
    """Green light for new entries only when the market symbol closes above its
    200-day SMA. Edit here to change the market filter."""
    m = state["market_prices"]
    close = float(m["Close"].iloc[-1])
    sma200 = float(ta.sma(m["Close"], 200).iloc[-1])
    rsi = float(ta.rsi(m["Close"]).iloc[-1])
    ok = close > sma200
    sym = state["config"]["data"]["market_symbol"]
    return {"market": {
        "symbol": sym, "ok": ok, "close": round(close, 2), "sma200": round(sma200, 2),
        "pct_vs_sma200": round((close / sma200 - 1) * 100, 2), "rsi": round(rsi, 1),
        "detail": f"{sym} {close:.2f} vs SMA200 {sma200:.2f} → {'GREEN' if ok else 'RED'}",
    }}


@step("strategy_rules", "Strategy rules (from strategies/)", reads=["prices"])
def strategy_rules(state: dict) -> dict:
    """Runs the strategy file named in config.yaml on the price data and reports
    every rule as passed/failed with the actual numbers."""
    cfg = state["config"]
    strat = load_strategy(cfg["strategy"], cfg.get("strategy_params"))
    df = strat.prepare(state["prices"])
    result = strat.evaluate(df)
    return {
        "strategy": {"file": cfg["strategy"], "name": strat.NAME,
                     "params": strat.params, "description": strat.describe()},
        "indicators": strat.latest(df),
        "signal": result.to_dict(),
        "prices": df,  # now includes the strategy's indicator columns
    }
