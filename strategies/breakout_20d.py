"""Example of a second strategy, to show swapping: 20-day breakout.

Set `strategy: breakout_20d` in config.yaml to use it. Not backtested — treat
it as a template, and test it in TradingView before trusting it.
"""
from __future__ import annotations

import pandas as pd

from swing_agents import indicators as ta

from .base import Check, SignalResult, Strategy


class Breakout20(Strategy):
    NAME = "20-day Breakout"

    PARAMS = {
        "lookback": 20,
        "sma_long": 200,
        "vol_mult": 1.5,
        "atr_len": 14,
        "atr_stop_mult": 2.0,
    }

    DESCRIPTION = """
Strategy: 20-day Breakout (daily chart, decided on Friday close).
Idea: buy strength when price breaks out of its recent range on heavy volume,
in a stock that is already in a long-term uptrend.

ENTRY — all must be true on the decision day:
  1. Close > highest close of the previous {lookback} days (new breakout).
  2. Close > SMA{sma_long} (long-term uptrend).
  3. Volume > {vol_mult} x its {lookback}-day average (real demand).
  Order: buy at Monday's open.

STOP AND EXITS:
  - Initial stop: entry - {atr_stop_mult} x ATR({atr_len}).
  - Exit if price closes back below the breakout level within a week (failed breakout).
  - Otherwise trail the stop under the {lookback}-day low.
"""

    SHOW = ["Close", "Volume", "prior_high", "vol_avg", "sma_long", "atr"]

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = df.copy()
        df["prior_high"] = ta.highest(df["Close"], p["lookback"]).shift(1)
        df["vol_avg"] = ta.sma(df["Volume"], p["lookback"]).shift(1)
        df["sma_long"] = ta.sma(df["Close"], p["sma_long"])
        df["atr"] = ta.atr(df, p["atr_len"])
        return df

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        p = self.params
        r = df.iloc[-1]
        checks = [
            Check("Breakout", f"close > prior {p['lookback']}-day high", r["Close"] > r["prior_high"],
                  f"{r['Close']:.2f} vs {r['prior_high']:.2f}"),
            Check("Long-term uptrend", f"close > SMA{p['sma_long']}", r["Close"] > r["sma_long"],
                  f"{r['Close']:.2f} vs {r['sma_long']:.2f}"),
            Check("Volume surge", f"volume > {p['vol_mult']} x avg", r["Volume"] > p["vol_mult"] * r["vol_avg"],
                  f"{r['Volume']:,.0f} vs {p['vol_mult'] * r['vol_avg']:,.0f}"),
        ]
        entry = round(float(r["Close"]), 2)
        stop = round(entry - p["atr_stop_mult"] * float(r["atr"]), 2)
        return SignalResult(signal=all(c.passed for c in checks), checks=checks, entry=entry,
                            stop=stop, entry_type="market_open",
                            notes=f"Buy at Monday open (~{entry}); stop {stop}.")


STRATEGY = Breakout20
