"""What every strategy file must provide.

To make a new strategy:
  1. Copy pullback_v2.py to strategies/my_idea.py
  2. Change NAME, DESCRIPTION, PARAMS and the two methods
  3. Set `strategy: my_idea` in config.yaml

The flow calls:
  prepare(df)            -> df with your indicator columns added
  evaluate(df, params)   -> SignalResult for the LAST bar (the analysis date)

DESCRIPTION is plain text the AI analysts read, so write your rules (entry,
stop, exits, what you avoid) the way you'd explain them to a person.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd


@dataclass
class Check:
    name: str          # short label, e.g. "Uptrend"
    rule: str          # the rule in words, e.g. "close > SMA200"
    passed: bool
    value: str = ""    # the actual numbers, e.g. "523.9 > 441.0"


@dataclass
class SignalResult:
    signal: bool                      # True = setup is valid today
    checks: list[Check] = field(default_factory=list)
    entry: float | None = None        # suggested entry trigger price
    stop: float | None = None         # initial stop price
    entry_type: str = "buy_stop"      # buy_stop | market_open | limit
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["checks_passed"] = sum(c.passed for c in self.checks)
        d["checks_total"] = len(self.checks)
        return d


class Strategy:
    NAME = "base"
    DESCRIPTION = ""
    PARAMS: dict = {}
    # Indicator columns to show the analysts (latest values)
    SHOW = ["Close"]

    def __init__(self, overrides: dict | None = None):
        self.params = {**self.PARAMS, **(overrides or {})}

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        raise NotImplementedError

    def evaluate(self, df: pd.DataFrame) -> SignalResult:
        raise NotImplementedError

    def describe(self) -> str:
        """Description with the current parameter values filled in."""
        return self.DESCRIPTION.format(**self.params).strip()

    def latest(self, df: pd.DataFrame) -> dict:
        row = df.iloc[-1]
        return {c: round(float(row[c]), 4) for c in self.SHOW if c in df.columns}
