"""Records what every step read, wrote and asked the LLM, so you can inspect it.

Each step is wrapped with @step(...). When it runs, a file like
    runs/<run_id>/<TICKER>/05_technical_analyst.json
is written with:
    reads      – the state keys the step used (snapshot before it ran)
    writes     – what the step returned (the new state keys)
    llm_calls  – every prompt sent and the raw answer, with the model name
    duration_s, status, error
index.json in the same folder lists the steps in the order they ran.
viewer.py (Streamlit) reads these files.
"""
from __future__ import annotations

import contextvars
import functools
import json
import time
import traceback
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

# LLM calls made during the current step are appended here (see llm.py).
_current_calls: contextvars.ContextVar[list | None] = contextvars.ContextVar("calls", default=None)


def log_llm_call(model: str, prompt: str, response: str, seconds: float) -> None:
    calls = _current_calls.get()
    if calls is not None:
        calls.append({"model": model, "prompt": prompt, "response": response,
                      "seconds": round(seconds, 2)})


def to_jsonable(obj, depth: int = 0):
    """Make state values safe for JSON (DataFrames become a short preview)."""
    if isinstance(obj, pd.DataFrame):
        tail = obj.tail(5).copy()
        tail.index = tail.index.astype(str)
        return {"_type": "DataFrame", "rows": len(obj), "columns": list(map(str, obj.columns)),
                "first_date": str(obj.index[0])[:10] if len(obj) else None,
                "last_date": str(obj.index[-1])[:10] if len(obj) else None,
                "tail": json.loads(tail.round(4).to_json(orient="index"))}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v, depth + 1) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return None if np.isnan(obj) else round(float(obj), 6)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (datetime, date, pd.Timestamp)):
        return str(obj)[:19]
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def step(name: str, title: str, reads: list[str] | None = None):
    """Decorator for a flow step.

    name   – machine name, also the LangGraph node name
    title  – what the viewer shows
    reads  – state keys to snapshot as the step's inputs
    """
    reads = reads or []

    def wrap(fn):
        @functools.wraps(fn)
        def node(state: dict) -> dict:
            run_dir = Path(state["run_dir"])
            run_dir.mkdir(parents=True, exist_ok=True)
            index_path = run_dir / "index.json"
            index = json.loads(index_path.read_text()) if index_path.exists() else []
            num = len(index) + 1

            calls: list = []
            token = _current_calls.set(calls)
            t0 = time.time()
            status, error, out = "ok", None, {}
            try:
                out = fn(state) or {}
            except Exception as e:  # keep the flow inspectable even on failure
                status, error = "error", "".join(traceback.format_exception(e))
                raise
            finally:
                _current_calls.reset(token)
                record = {
                    "num": num, "name": name, "title": title, "doc": (fn.__doc__ or "").strip(),
                    "started": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
                    "duration_s": round(time.time() - t0, 2),
                    "status": status, "error": error,
                    "reads": {k: to_jsonable(state.get(k)) for k in reads},
                    "writes": to_jsonable(out),
                    "llm_calls": calls,
                }
                fname = f"{num:02d}_{name}.json"
                (run_dir / fname).write_text(json.dumps(record, indent=2, default=str))
                index.append({"num": num, "name": name, "title": title, "file": fname,
                              "status": status, "duration_s": record["duration_s"],
                              "llm_calls": len(calls)})
                index_path.write_text(json.dumps(index, indent=2))
            return out

        node.step_name = name
        node.step_title = title
        return node

    return wrap
