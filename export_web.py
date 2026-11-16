"""Turn runs/ into the JSON the phone app (docs/) reads.

    python export_web.py            # after python run.py ...

Writes:
  docs/data/index.json             list of runs, newest first, with each ticker's action
  docs/data/<run_id>.json          every step of every ticker in that run
Keeps the newest KEEP runs so the site stays small.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"
OUT = ROOT / "docs" / "data"
KEEP = 20


def load_ticker(folder: Path) -> dict:
    index = json.loads((folder / "index.json").read_text())
    steps = [json.loads((folder / s["file"]).read_text()) for s in index]
    final = next((s for s in steps if s["name"] == "final_decision"), None)
    strat = next((s for s in steps if s["name"] == "strategy_rules"), None)
    dec = final["writes"]["decision"] if final else {"action": "ERROR", "reasons": [], "summary": ""}
    sig = strat["writes"]["signal"] if strat else {}
    plan = next((s["writes"].get("plan") for s in steps if s["name"] == "trade_plan"), None)
    return {
        "ticker": folder.name,
        "action": dec["action"],
        "reasons": dec.get("reasons", []),
        "summary": dec.get("summary", ""),
        "chart": dec.get("chart"),
        "checks": f"{sig.get('checks_passed', '?')}/{sig.get('checks_total', '?')}",
        "plan": plan,
        "error": next((s["error"] for s in steps if s["status"] != "ok"), None),
        "steps": steps,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    existing = json.loads((OUT / "index.json").read_text()) if (OUT / "index.json").exists() else []
    known = {r["id"]: r for r in existing}

    for run in sorted(p for p in RUNS.glob("*") if p.is_dir()):
        tickers = [load_ticker(t) for t in sorted(run.iterdir()) if (t / "index.json").exists()]
        if not tickers:
            continue
        first = tickers[0]["steps"][0]
        as_of = next((s["reads"].get("as_of") for s in tickers[0]["steps"] if s["reads"].get("as_of")), "")
        strategy = next((s["writes"]["strategy"]["name"] for s in tickers[0]["steps"]
                         if s["name"] == "strategy_rules"), "")
        model = next((c["model"] for t in tickers for s in t["steps"] for c in s["llm_calls"]), "rules only")
        meta = {"id": run.name, "as_of": as_of, "started": first["started"], "strategy": strategy,
                "model": model,
                "tickers": [{"ticker": t["ticker"], "action": t["action"], "checks": t["checks"]} for t in tickers]}
        known[run.name] = meta
        (OUT / f"{run.name}.json").write_text(json.dumps({**meta, "results": tickers}, default=str))

    runs = sorted(known.values(), key=lambda r: r["id"], reverse=True)
    for old in runs[KEEP:]:
        (OUT / f"{old['id']}.json").unlink(missing_ok=True)
    runs = runs[:KEEP]
    (OUT / "index.json").write_text(json.dumps(runs, indent=1))
    print(f"Exported {len(runs)} runs to {OUT}")


if __name__ == "__main__":
    main()
