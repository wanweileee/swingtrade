"""Step-by-step viewer for saved runs.

    streamlit run viewer.py

Pick a run and a ticker on the left. You'll see the flow with each step's
status, then every step: what it read, what it wrote, and (for AI steps)
the exact prompt and answer.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
RUNS = ROOT / "runs"

st.set_page_config(page_title="swing-agents runs", layout="wide")

runs = sorted([p for p in RUNS.glob("*") if p.is_dir()], reverse=True) if RUNS.exists() else []
if not runs:
    st.info("No runs yet. Run e.g. `python run.py MSFT --offline` first.")
    st.stop()

with st.sidebar:
    run = st.selectbox("Run", runs, format_func=lambda p: p.name)
    if (run / "summary.md").exists():
        st.markdown((run / "summary.md").read_text())
    tickers = sorted(p.name for p in run.iterdir() if p.is_dir())
    if not tickers:
        st.warning("This run has no ticker folders.")
        st.stop()
    ticker = st.radio("Ticker", tickers)

folder = run / ticker
index = json.loads((folder / "index.json").read_text())
steps = [json.loads((folder / s["file"]).read_text()) for s in index]
final = next((s for s in steps if s["name"] == "final_decision"), None)

# ── header: decision ────────────────────────────────────────────
action = final["writes"]["decision"]["action"] if final else "INCOMPLETE"
colour = {"BUY": "green", "WATCH": "orange", "SKIP": "gray"}.get(action, "red")
st.markdown(f"## {ticker} · :{colour}[{action}]")
if final:
    body = final["writes"]["decision"]["summary"].split("\n", 1)[1]
    st.markdown(body.replace("## ", "#### ").replace("\nChart: ", "  \nChart: "))

# ── flow strip (one box per step, in run order) ────────────────
boxes = []
for s in steps:
    ai = bool(s["llm_calls"])
    bg = "#fde2e1" if s["status"] != "ok" else ("#e3ecfb" if ai else "#e6f4ea")
    boxes.append(f'<div style="background:{bg};color:#1f2328;border-radius:8px;padding:6px 10px;'
                 f'font-size:12px;line-height:1.3;white-space:nowrap">'
                 f'<b>{s["num"]:02d}</b> {s["name"]}<br><span style="opacity:.65">{s["duration_s"]}s'
                 f'{" · AI" if ai else ""}</span></div>')
st.markdown('<div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0">'
            + '<span style="opacity:.4">→</span>'.join(boxes) + "</div>", unsafe_allow_html=True)
st.caption("Green = code step · Blue = AI step · Red = error. Totals: "
           f"{sum(s['duration_s'] for s in steps):.1f}s, {sum(len(s['llm_calls']) for s in steps)} AI calls")


# ── each step ───────────────────────────────────────────────────
def show_value(key: str, val):
    if isinstance(val, dict) and val.get("_type") == "DataFrame":
        st.caption(f"`{key}` · DataFrame {val['rows']} rows, {val['first_date']} → {val['last_date']} (last 5 shown)")
        st.dataframe(pd.DataFrame(val["tail"]).T, use_container_width=True)
    elif key == "signal" and isinstance(val, dict):
        st.caption(f"`signal` · {'✅ YES' if val['signal'] else '❌ NO'} "
                   f"({val['checks_passed']}/{val['checks_total']}) · entry {val['entry']} · stop {val['stop']}")
        st.dataframe(pd.DataFrame(val["checks"]), use_container_width=True, hide_index=True)
    elif key == "strategy" and isinstance(val, dict):
        st.caption(f"`strategy` · {val['name']} (strategies/{val['file']}.py)")
        st.code(val["description"], language="markdown")
        st.json(val["params"], expanded=False)
    elif key == "reports" and isinstance(val, dict):
        for k, v in val.items():
            st.markdown(f"**{k}**")
            st.markdown(v)
    elif key == "debate" and isinstance(val, list):
        for d in val:
            st.markdown(f"**{d['speaker']}:** {d['text']}")
    elif key == "risk" and isinstance(val, dict):
        st.dataframe(pd.DataFrame(val["hard_checks"]), use_container_width=True, hide_index=True)
        st.markdown(f"**Reviewer** ({'VETO' if val['veto'] else 'approve'}):\n\n{val['review']}")
    elif key == "decision" and isinstance(val, dict):
        st.markdown(val["summary"].replace("# ", "#### ", 1).replace("## ", "##### "))
    elif isinstance(val, (dict, list)):
        st.caption(f"`{key}`")
        st.json(val, expanded=1)
    else:
        st.caption(f"`{key}`")
        st.write(val)


for s in steps:
    icon = "🤖" if s["llm_calls"] else "⚙️"
    bad = " ❗" if s["status"] != "ok" else ""
    with st.expander(f"{s['num']:02d} · {icon} {s['title']} · {s['duration_s']}s{bad}",
                     expanded=s["name"] in ("strategy_rules", "final_decision")):
        if s["doc"]:
            st.caption(s["doc"])
        if s["error"]:
            st.error(s["error"])
        tabs = st.tabs(["Output (writes)", "Input (reads)"] + (["AI prompt & answer"] if s["llm_calls"] else []) + ["Raw JSON"])
        with tabs[0]:
            for k, v in s["writes"].items():
                show_value(k, v)
        with tabs[1]:
            for k, v in s["reads"].items():
                show_value(k, v)
        i = 2
        if s["llm_calls"]:
            with tabs[i]:
                for c in s["llm_calls"]:
                    st.caption(f"model `{c['model']}` · {c['seconds']}s")
                    st.markdown("**Answer**")
                    st.markdown(c["response"])
                    st.markdown("**Prompt sent**")
                    st.code(c["prompt"], language="markdown")
            i += 1
        with tabs[i]:
            st.json(s, expanded=False)
