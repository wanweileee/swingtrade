"""Pullback Swing v2 — the same rules as your TradingView Pine script.

Buy a pullback inside an established uptrend, on the daily chart, decided on
the week's close. Market filter (SPY > its 200-day SMA) is checked in its own
flow step, so it isn't repeated here.
"""
from __future__ import annotations

import pandas as pd

from swing_agents import indicators as ta

from .base import Check, SignalResult, Strategy


class PullbackV2(Strategy):
    NAME = "Pullback Swing v2"

    PARAMS = {
        "ema_fast": 20,
        "ema_mid": 50,
        "sma_long": 200,
        "rsi_len": 14,
        "rsi_max": 50,          # v1 used 45
        "near_pct": 0.02,       # close within 2% above EMA20 counts as "at" it
        "atr_len": 14,
        "atr_stop_mult": 2.0,   # initial stop = entry - 2 x ATR
        "trail_atr_mult": 3.0,  # trailing stop after +1R
        "valid_days": 5,        # buy-stop order lives 5 trading days
        "stall_weeks": 6,
    }

    DESCRIPTION = """
Strategy: Pullback Swing v2 (daily chart, decisions on Friday close, orders for Monday).
Idea: buy a short dip inside a healthy uptrend, when momentum has cooled, and only
once price starts bouncing.

ENTRY — all must be true on the decision day:
  1. Uptrend: close > SMA{sma_long}, EMA{ema_mid} > SMA{sma_long}, EMA{ema_fast} > EMA{ema_mid}.
  2. Pullback: close <= EMA{ema_fast} x (1 + {near_pct}) and close > EMA{ema_mid}.
  3. Momentum cooled: RSI({rsi_len}) < {rsi_max}.
  4. Market filter: SPY above its 200-day SMA (checked separately).
  5. No earnings within the blackout window (checked by the risk step).
  Order: buy-stop at the setup day's high + 1 tick, valid {valid_days} trading days,
  so we only buy if price bounces.

STOP AND EXITS:
  - Initial stop: entry - {atr_stop_mult} x ATR({atr_len}).
  - At +1R profit: move stop to breakeven.
  - Beyond +1R: trail stop at highest high since entry - {trail_atr_mult} x ATR (only moves up).
  - Weekly close below EMA{ema_mid}: exit next open (trend broke).
  - After {stall_weeks} weeks with less than +1R: exit (stalled).

What this strategy avoids: stocks below their 200-day average (downtrends, not
pullbacks), chasing extended stocks far above EMA{ema_fast}, and earnings gaps.
"""

    SHOW = ["Open", "High", "Low", "Close", "Volume", "ema_fast", "ema_mid",
            "sma_long", "rsi", "atr", "dist_ema_fast_pct"]

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        df = df.copy()
        df["ema_fast"] = ta.ema(df["Close"], p["ema_fast"])
        df["ema_mid"] = ta.ema(df["Close"], p["ema_mid"])
        df["sma_long"] = ta.sma(df["Close"], p["sma_long"])
        df["rsi"] = ta.rsi(df["Close"], p["rsi_len"])
        df["atr"] = ta.atr(df, p["atr_len"])
        df["dist_ema_fast_pct"] = (df["Close"] / df["ema_fast"] - 1) * 100
        return df

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        p = self.params
        r = df.iloc[-1]
        c, ef, em, sl = r["Close"], r["ema_fast"], r["ema_mid"], r["sma_long"]
        checks = [
            Check("Above 200-day", f"close > SMA{p['sma_long']}", c > sl, f"{c:.2f} vs {sl:.2f}"),
            Check("Mid above long", f"EMA{p['ema_mid']} > SMA{p['sma_long']}", em > sl, f"{em:.2f} vs {sl:.2f}"),
            Check("Fast above mid", f"EMA{p['ema_fast']} > EMA{p['ema_mid']}", ef > em, f"{ef:.2f} vs {em:.2f}"),
            Check("In pullback zone", f"close <= EMA{p['ema_fast']} x {1 + p['near_pct']:.2f}",
                  c <= ef * (1 + p["near_pct"]), f"{c:.2f} vs {ef * (1 + p['near_pct']):.2f}"),
            Check("Trend intact", f"close > EMA{p['ema_mid']}", c > em, f"{c:.2f} vs {em:.2f}"),
            Check("Momentum cooled", f"RSI < {p['rsi_max']}", r["rsi"] < p["rsi_max"], f"{r['rsi']:.1f}"),
        ]
        signal = all(ch.passed for ch in checks)
        tick = 0.01
        entry = round(float(r["High"]) + tick, 2)
        stop = round(entry - p["atr_stop_mult"] * float(r["atr"]), 2)
        notes = (f"Buy-stop {entry} valid {p['valid_days']} trading days; stop {stop} "
                 f"({p['atr_stop_mult']} x ATR {r['atr']:.2f}).")
        return SignalResult(signal=signal, checks=checks, entry=entry, stop=stop,
                            entry_type="buy_stop", notes=notes)


STRATEGY = PullbackV2
