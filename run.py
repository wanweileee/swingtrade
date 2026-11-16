"""Run the flow from the terminal.

    python run.py MSFT XOM                 # analyse two tickers as of last trading day
    python run.py MSFT --date 2026-11-13   # a specific Friday
    python run.py MSFT --offline           # no API key: stub AI answers
    python run.py MSFT --strategy breakout_20d
    python run.py --watchlist              # every ticker in watchlist.txt

Each step prints as it finishes; full outputs are saved under runs/<time>/<TICKER>/.
View them with:  streamlit run viewer.py
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from swing_agents.config import ROOT, load_config, load_knowledge, load_portfolio
from swing_agents.data import last_trading_day
from swing_agents.graph import build_graph

console = Console()


def short(name: str, out: dict) -> str:
    """One-line summary of what a step produced, for the terminal."""
    if name == "fetch_data":
        p = out["prices"]
        return f"{len(p)} bars to {str(p.index[-1])[:10]}, earnings {out['earnings'].get('next_date')}, {len(out['news'])} headlines"
    if name == "market_regime":
        return out["market"]["detail"]
    if name == "strategy_rules":
        s = out["signal"]
        return f"SIGNAL {'YES' if s['signal'] else 'NO'} ({s['checks_passed']}/{s['checks_total']}) — entry {s['entry']} stop {s['stop']}"
    if name in ("technical_analyst", "fundamentals_analyst", "news_analyst"):
        key = name.split("_")[0]
        return out["reports"][key].strip().splitlines()[-1][:110]
    if name in ("bull", "bear"):
        return out["debate"][-1]["text"].strip().splitlines()[0][:110]
    if name == "research_manager":
        return f"VERDICT {out['research']['verdict']}"
    if name == "trade_plan":
        p = out["plan"]
        return f"{p.get('shares')} sh ≈ ${p.get('position_usd')}, risk ${p.get('actual_risk_usd')}"
    if name == "risk_check":
        r = out["risk"]
        bad = [c["name"] for c in r["hard_checks"] if not c["passed"]]
        return f"hard rules {'PASS' if r['passed'] else 'FAIL: ' + ', '.join(bad)}; reviewer {'VETO' if r['veto'] else 'ok'}"
    if name == "final_decision":
        return out["decision"]["action"]
    return ""


def main():
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--date", help="analysis date YYYY-MM-DD (default: last weekday)")
    ap.add_argument("--offline", action="store_true", help="no AI calls (stub answers)")
    ap.add_argument("--rules-only", action="store_true", help="skip all AI steps")
    ap.add_argument("--strategy", help="override config strategy")
    ap.add_argument("--config", help="path to another config.yaml")
    ap.add_argument("--watchlist", action="store_true", help="use watchlist.txt")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.offline:
        cfg["llm"]["quick_model"] = cfg["llm"]["deep_model"] = "offline"
    import os
    model = cfg["llm"]["quick_model"]
    provider = model.split(":")[0]
    key_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider)
    if args.rules_only or (not args.offline and key_var and not os.getenv(key_var)):
        if not args.rules_only:
            console.print(f"[yellow]No {key_var} found → rules-only mode (no AI steps).[/]")
        cfg["flow"]["rules_only"] = True
    if args.strategy:
        cfg["strategy"] = args.strategy
    tickers = [t.upper() for t in args.tickers]
    if args.watchlist:
        for line in (ROOT / "watchlist.txt").read_text().splitlines():
            line = line.split("#", 1)[0]          # drop comments
            tickers += [t.strip(",").upper() for t in line.split() if t.strip(",")]
    if not tickers:
        ap.error("give tickers or --watchlist")

    as_of = args.date or last_trading_day()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_root = Path(ROOT, cfg["output"]["runs_dir"], stamp)
    graph = build_graph(cfg)
    knowledge, portfolio = load_knowledge(cfg), load_portfolio(cfg)

    results = []
    for t in tickers:
        console.rule(f"[bold]{t}[/] · {as_of} · {cfg['strategy']} · {'rules only' if cfg['flow'].get('rules_only') else cfg['llm']['quick_model']}")
        state = {"ticker": t, "as_of": as_of, "config": cfg, "knowledge": knowledge,
                 "portfolio": portfolio, "run_dir": str(run_root / t)}
        final = {}
        try:
            for update in graph.stream(state, stream_mode="updates"):
                for name, out in update.items():
                    if name == "setup":
                        continue
                    final.update(out or {})
                    console.print(f"  [cyan]✓ {name:<22}[/] {escape(short(name, out or {}))}")
            d = final["decision"]
            console.print(Panel(escape(d["summary"]), border_style="green" if d["action"] == "BUY" else "yellow"))
            results.append((t, d["action"], d["reasons"][0] if d["reasons"] else ""))
        except Exception as e:
            console.print(f"  [red]✗ failed: {e}[/]")
            results.append((t, "ERROR", str(e)[:80]))

    table = Table(title=f"Summary · {as_of}")
    for c in ("Ticker", "Action", "Main reason"):
        table.add_column(c)
    for r in results:
        table.add_row(*r)
    console.print(table)
    (run_root).mkdir(parents=True, exist_ok=True)
    (run_root / "summary.md").write_text(
        f"# Run {stamp} · as of {as_of} · {cfg['strategy']}\n\n| Ticker | Action | Main reason |\n|---|---|---|\n"
        + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in results))
    console.print(f"Saved to {run_root}  ·  view: [bold]streamlit run viewer.py[/]")


if __name__ == "__main__":
    main()
