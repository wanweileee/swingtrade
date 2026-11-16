"""Market data loading. Each function returns plain data and never raises on
missing extras (fundamentals/news): it returns an 'unavailable' note instead,
so one missing source doesn't stop the flow.

Sources (config.yaml → data.source):
  yfinance – free Yahoo data, needs internet
  csv      – data/csv/<TICKER>.csv with Date,Open,High,Low,Close,Volume
             (export from TradingView: chart → ⋯ → Export chart data)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .config import ROOT

COLS = ["Open", "High", "Low", "Close", "Volume"]


def load_prices(ticker: str, as_of: str, cfg: dict) -> pd.DataFrame:
    src = cfg["data"].get("source", "yfinance")
    end = pd.Timestamp(as_of)
    start = end - timedelta(days=cfg["data"].get("lookback_days", 600))
    if src == "csv":
        df = _from_csv(ticker)
    else:
        df = _from_yfinance(ticker, start, end)
    df = df[(df.index >= start) & (df.index <= end)]
    if len(df) < 210:
        raise ValueError(f"{ticker}: only {len(df)} daily bars up to {as_of}; need ~210 for a 200-day average")
    return df


def _from_csv(ticker: str) -> pd.DataFrame:
    path = ROOT / "data" / "csv" / f"{ticker.upper()}.csv"
    if not path.exists():
        raise FileNotFoundError(f"No CSV for {ticker} at {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().capitalize() for c in df.columns]
    date_col = "Date" if "Date" in df.columns else "Time"
    df[date_col] = pd.to_datetime(df[date_col], utc=False, errors="coerce")
    df = df.set_index(date_col).sort_index()
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    return df[COLS].astype(float)


def _from_yfinance(ticker: str, start, end) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(ticker, start=start.strftime("%Y-%m-%d"),
                     end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
                     auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"yfinance returned no data for {ticker}")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df[COLS].astype(float)


def load_fundamentals(ticker: str, cfg: dict) -> dict:
    if cfg["data"].get("source") == "csv":
        return _from_extra_yaml(ticker, "fundamentals") or {"note": "unavailable (csv mode)"}
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        keys = ["longName", "sector", "industry", "marketCap", "trailingPE", "forwardPE",
                "revenueGrowth", "earningsGrowth", "profitMargins", "debtToEquity",
                "returnOnEquity", "freeCashflow", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
                "averageVolume", "recommendationKey", "targetMeanPrice", "exDividendDate"]
        return {k: info.get(k) for k in keys if info.get(k) is not None}
    except Exception as e:
        return {"note": f"unavailable: {e}"}


def load_earnings(ticker: str, as_of: str, cfg: dict) -> dict:
    nxt = None
    if cfg["data"].get("source") == "csv":
        nxt = (_from_extra_yaml(ticker, "earnings") or {}).get("next_date")
    else:
        try:
            import yfinance as yf
            cal = yf.Ticker(ticker).calendar
            dates = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if dates:
                nxt = str(dates[0])[:10]
        except Exception as e:
            return {"next_date": None, "days_away": None, "note": f"unavailable: {e}"}
    if not nxt:
        return {"next_date": None, "days_away": None, "note": "unknown — check manually"}
    days = (datetime.strptime(str(nxt)[:10], "%Y-%m-%d").date()
            - datetime.strptime(as_of, "%Y-%m-%d").date()).days
    return {"next_date": str(nxt)[:10], "days_away": days}


def load_news(ticker: str, cfg: dict) -> list:
    n = cfg["data"].get("news_items", 8)
    if cfg["data"].get("source") == "csv":
        return (_from_extra_yaml(ticker, "news") or [])[:n]
    try:
        import yfinance as yf
        items = yf.Ticker(ticker).news or []
        out = []
        for it in items[:n]:
            c = it.get("content", it)  # yfinance changed formats over time
            out.append({"title": c.get("title"),
                        "publisher": (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher"),
                        "date": str(c.get("pubDate") or c.get("providerPublishTime") or "")[:10],
                        "summary": (c.get("summary") or "")[:300]})
        return out
    except Exception as e:
        return [{"title": f"news unavailable: {e}"}]


def _from_extra_yaml(ticker: str, key: str):
    """csv mode: optional data/csv/<TICKER>.yaml with fundamentals/earnings/news."""
    import yaml
    p = ROOT / "data" / "csv" / f"{ticker.upper()}.yaml"
    if not p.exists():
        return None
    return (yaml.safe_load(p.read_text()) or {}).get(key)


def last_trading_day(today: date | None = None) -> str:
    d = today or date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()
